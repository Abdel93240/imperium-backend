"""PostgreSQL : justificatifs du Vault (doc 37 §3) — OCR, brouillon, validation, annulation."""
from __future__ import annotations

import io
from datetime import UTC, datetime
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("vault receipts DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.vault import ImperiumVaultTransaction, UserCategoryMemory  # noqa: E402
from app.schemas.vault import VaultReceiptValidateRequest  # noqa: E402
from app.services.ai import ocr  # noqa: E402
from app.services.vault import receipts  # noqa: E402

TICKET = "TotalEnergies\nRelais Porte d'Orly\n16/10/2026 07:55\nGazole 38,21 L\nMONTANT TTC 65,40\nCB SANS CONTACT\n"


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        yield session
        session.rollback()


@pytest.fixture(autouse=True)
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(receipts, "storage_root", lambda: tmp_path)
    return tmp_path


def _user(db) -> User:
    user_id = uuid4()
    db.execute(
        text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) VALUES (:id, :email, FALSE, now(), now())"),
        {"id": str(user_id), "email": f"receipt-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _reads(raw=TICKET, confidence=0.93):
    return lambda data, filename, content_type: ocr.OcrResult(text=raw, confidence=confidence)


def _scan(db, user, *, recognize=None, name="ticket.jpg", data=b"JPEGDATA", key=None):
    return receipts.create_extraction(
        db, current_user=user, filename=name, content_type="image/jpeg", stream=io.BytesIO(data),
        idempotency_key=key or f"r-{uuid4().hex}", recognize_file=recognize, call_model=None,
    )


def _validate(db, user, extraction, *, category="carburant", key=None, amount=6540):
    return receipts.validate_extraction(
        db, current_user=user, extraction_id=extraction.id,
        payload=VaultReceiptValidateRequest(amount_cents=amount, occurred_at=datetime(2026, 10, 16, 5, 55, tzinfo=UTC),
                                            category=category, wallet="bank"),
        idempotency_key=key or f"v-{uuid4().hex}", request_method="POST", request_path="/api/imperium/vault/receipt-extractions",
    )


def test_scan_builds_a_draft_and_writes_nothing_to_the_ledger(db, storage) -> None:
    user = _user(db)
    extraction, duplicate = _scan(db, user, recognize=_reads())
    assert not duplicate and extraction.status == "ready" and extraction.ocr_confidence == pytest.approx(0.93)
    draft = extraction.draft
    assert (draft.merchant, draft.total_cents, draft.purchase_time) == ("TotalEnergies", 6540, "07:55")
    assert draft.purchase_date.isoformat() == "2026-10-16" and draft.payment_method == "card" and draft.wallet == "bank"
    assert draft.category == "carburant" and draft.category_source == "table"
    assert db.scalar(select(ImperiumVaultTransaction).where(ImperiumVaultTransaction.user_id == user.id)) is None
    path, mime = receipts.image_path(db, current_user=user, extraction_id=extraction.id)
    assert path.read_bytes() == b"JPEGDATA" and mime == "image/jpeg" and oct(path.stat().st_mode & 0o777) == "0o600"


def test_validation_writes_the_expense_and_keeps_the_receipt(db) -> None:
    user = _user(db)
    extraction, _ = _scan(db, user, recognize=_reads())
    result = _validate(db, user, extraction)
    transaction = db.get(ImperiumVaultTransaction, result.transaction.id)
    assert transaction.transaction_type == "expense" and transaction.amount_cents == 6540 and transaction.wallet == "bank"
    assert transaction.source == "scan_ticket" and transaction.external_ref == f"receipt:{extraction.id}"
    assert transaction.category == "carburant" and transaction.note == "TotalEnergies"
    assert result.extraction.status == "validated" and result.extraction.transaction_id == transaction.id
    receipts.image_path(db, current_user=user, extraction_id=extraction.id)  # justificatif conservé
    memory = db.scalar(select(UserCategoryMemory).where(UserCategoryMemory.user_id == user.id))
    assert memory is not None and memory.category == "carburant"  # le choix validé est appris
    types = set(db.scalars(select(Event.event_type).where(Event.user_id == user.id)))
    assert {"finance.receipt.extracted", "finance.receipt.validated", "finance.transaction.created"} <= types


def test_validation_is_idempotent(db) -> None:
    user = _user(db)
    extraction, _ = _scan(db, user, recognize=_reads())
    first = _validate(db, user, extraction, key="same")
    again = _validate(db, user, extraction, key="same")
    assert first.transaction.id == again.transaction.id
    count = db.scalar(text("SELECT count(*) FROM imperium_vault_transactions WHERE user_id = :u"), {"u": str(user.id)})
    assert count == 1


def test_upload_replay_returns_the_same_extraction(db) -> None:
    user = _user(db)
    first, _ = _scan(db, user, recognize=_reads(), key="scan-1")
    again, duplicate = _scan(db, user, recognize=_reads(), key="scan-1")
    assert duplicate and again.id == first.id


@pytest.mark.parametrize(
    ("recognize", "message"),
    [
        (None, "pas encore activée"),
        ("down", "ne répond pas"),
        ("bad", "illisible"),
        (_reads(raw="   "), "Aucun texte"),
    ],
)
def test_failures_give_a_readable_message_and_keep_no_image(db, storage, recognize, message) -> None:
    def down(data, filename, content_type):
        raise ocr.OcrServiceUnreachable("x")

    def bad(data, filename, content_type):
        raise ocr.OcrError("x")

    recognize = {"down": down, "bad": bad}.get(recognize, recognize) if isinstance(recognize, str) else recognize
    user = _user(db)
    extraction, _ = _scan(db, user, recognize=recognize)
    assert extraction.status == "failed" and message in extraction.error_message and extraction.draft is None
    assert not any(storage.rglob("*.jpg"))
    with pytest.raises(receipts.ReceiptStateError):
        _validate(db, user, extraction)


def test_low_confidence_adds_a_warning(db) -> None:
    user = _user(db)
    extraction, _ = _scan(db, user, recognize=_reads(confidence=0.4))
    assert any("peu sûre" in warning for warning in extraction.draft.warnings)


def test_cancel_deletes_the_image_and_blocks_validation(db, storage) -> None:
    user = _user(db)
    extraction, _ = _scan(db, user, recognize=_reads())
    cancelled = receipts.cancel_extraction(db, current_user=user, extraction_id=extraction.id)
    assert cancelled.status == "cancelled" and not any(storage.rglob("*.jpg"))
    with pytest.raises(receipts.ReceiptStateError):
        _validate(db, user, extraction)


def test_validated_receipt_cannot_be_cancelled(db) -> None:
    user = _user(db)
    extraction, _ = _scan(db, user, recognize=_reads())
    _validate(db, user, extraction)
    with pytest.raises(receipts.ReceiptStateError):
        receipts.cancel_extraction(db, current_user=user, extraction_id=extraction.id)


def test_file_type_and_size_are_enforced(db, monkeypatch) -> None:
    user = _user(db)
    with pytest.raises(receipts.ReceiptFileError):
        _scan(db, user, recognize=_reads(), name="ticket.exe")
    monkeypatch.setattr(receipts, "MAX_BYTES", 3)
    with pytest.raises(receipts.ReceiptFileError):
        _scan(db, user, recognize=_reads(), data=b"0123456")


def test_receipts_are_user_scoped(db) -> None:
    user, other = _user(db), _user(db)
    extraction, _ = _scan(db, user, recognize=_reads())
    with pytest.raises(receipts.ReceiptNotFoundError):
        receipts.get_extraction(db, current_user=other, extraction_id=extraction.id)


def test_http_flow(db, monkeypatch) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_user, get_db
    from app.api.v1.routes import imperium_vault_receipts as routes

    monkeypatch.setattr(receipts, "_default_recognizer", lambda: _reads())
    monkeypatch.setattr(receipts.categorization, "_default_model", lambda: None)
    user = _user(db)
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/imperium/vault")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    base = "/api/imperium/vault/receipt-extractions"

    missing_key = client.post(base, headers={"X-Filename": "t.jpg", "Content-Type": "image/jpeg"}, content=b"JPG")
    created = client.post(base, headers={"X-Filename": "t%C3%A9.jpg", "Content-Type": "image/jpeg", "Idempotency-Key": "h1"},
                          content=b"JPG")
    extraction_id = created.json()["id"]
    image = client.get(f"{base}/{extraction_id}/image")
    validated = client.post(f"{base}/{extraction_id}/validate", headers={"Idempotency-Key": "h2"},
                            json={"amount_cents": 6540, "occurred_at": "2026-10-16T07:55:00+02:00", "category": "carburant"})
    cancel = client.post(f"{base}/{extraction_id}/cancel")

    assert missing_key.status_code == 400
    assert created.status_code == 201 and created.json()["status"] == "ready" and created.json()["original_filename"] == "te.jpg"
    assert image.status_code == 200 and image.content == b"JPG"
    assert validated.status_code == 200 and validated.json()["transaction"]["amount_cents"] == 6540
    assert cancel.status_code == 409
