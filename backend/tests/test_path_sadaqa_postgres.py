"""PostgreSQL : sadaqa Path — réglages, objectif, report, dons et dépense Vault (doc 41 §9, doc 42 §15.1)."""
from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("path sadaqa DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_path_sadaqa  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.path import PathSadaqaDonation, PathSadaqaWeek  # noqa: E402
from app.models.vault import ImperiumVaultTransaction  # noqa: E402
from app.schemas.vault import ImperiumVaultTransactionCreate  # noqa: E402
from app.services.imperium import vault_transactions  # noqa: E402
from app.services.path import sadaqa  # noqa: E402

BASE = "/api/imperium/path/sadaqa"


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


def _user(db) -> User:
    user_id = uuid4()
    db.execute(
        text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) VALUES (:id, :email, FALSE, now(), now())"),
        {"id": str(user_id), "email": f"sadaqa-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_path_sadaqa.router, prefix="/api/imperium/path")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def _this_monday():
    return sadaqa.current_week(datetime.now(UTC))


def _at(day, hour=12):
    return datetime.combine(day, time(hour), tzinfo=sadaqa.PARIS)


def _vault(db, user, kind, cents, category, day) -> None:
    vault_transactions.create_vault_transaction(
        db, current_user=user,
        payload=ImperiumVaultTransactionCreate(transaction_type=kind, amount_cents=cents, occurred_at=_at(day),
                                               timezone="Europe/Paris", category=category),
        idempotency_key=uuid4().hex, request_method="POST", request_path="/t",
    )


def _donate(client, cents, **extra):
    return client.post(f"{BASE}/donations", headers=_key(), json={"amount_cents": cents, **extra})


# ---------- réglages ----------

def test_settings_default_then_prospective_change(db) -> None:
    client = _client(db, _user(db))
    assert client.get(f"{BASE}/settings").json() == {
        "percentage": "0.0500", "safety_margin": "0.1250", "applies_from": None, "pending": None,
        "changes_this_week": 0, "version": 0,
    }
    changed = client.patch(f"{BASE}/settings", headers=_key(), json={"percentage": "0.10", "base_version": 0})
    assert changed.status_code == 200, changed.text
    body = changed.json()
    assert (body["percentage"], body["version"], body["changes_this_week"]) == ("0.0500", 1, 1)
    assert body["pending"] == {"percentage": "0.1000", "safety_margin": "0.1250",
                               "applies_from": (_this_monday() + timedelta(days=7)).isoformat()}
    stale = client.patch(f"{BASE}/settings", headers=_key(), json={"percentage": "0.08", "base_version": 0})
    assert (stale.status_code, stale.json()["code"]) == (409, "SADAQA_SETTINGS_CONFLICT")
    second = client.patch(f"{BASE}/settings", headers=_key(), json={"percentage": "0.08", "base_version": 1})
    assert (second.status_code, second.json()["code"]) == (409, "SADAQA_SECOND_CHANGE")
    now_too = client.patch(f"{BASE}/settings", headers=_key(),
                           json={"percentage": "0.08", "base_version": 1, "confirm_second_change": True, "apply_to_current_week": True})
    assert now_too.status_code == 422
    confirmed = client.patch(f"{BASE}/settings", headers=_key(),
                             json={"safety_margin": "0.15", "base_version": 1, "confirm_second_change": True})
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["pending"]["percentage"] == "0.1000" and confirmed.json()["pending"]["safety_margin"] == "0.1500"
    out_of_range = client.patch(f"{BASE}/settings", headers=_key(), json={"percentage": "0.30", "base_version": 2})
    assert out_of_range.status_code == 422


def test_first_change_can_apply_to_the_current_week(db) -> None:
    client = _client(db, _user(db))
    body = client.patch(f"{BASE}/settings", headers=_key(),
                        json={"percentage": "0.10", "base_version": 0, "apply_to_current_week": True}).json()
    assert (body["percentage"], body["applies_from"], body["pending"]) == ("0.1000", _this_monday().isoformat(), None)


# ---------- objectif et dons ----------

def test_target_from_business_profit_and_vault_expense(db) -> None:
    user = _user(db)
    client = _client(db, user)
    monday = _this_monday()
    _vault(db, user, "income", 100_000, "vtc", monday)
    _vault(db, user, "expense", 20_000, "fuel", monday)
    _vault(db, user, "expense", 50_000, "loyer", monday)  # personnel : sans effet
    summary = client.get(f"{BASE}/summary").json()
    assert (summary["business_profit"], summary["profit_source"], summary["base_target"]) == ("800.00", "live", "45.00")
    assert (summary["carried_in"], summary["remaining"], summary["carry_message"]) == ("0.00", "45.00", None)
    created = _donate(client, 3000, destination="association du quartier", note="pour l'école")
    assert created.status_code == 201, created.text
    body = created.json()
    assert (body["donation"]["vault_status"], body["warnings"]) == ("recorded", [])
    assert body["donation"]["allocation"] == [{"part": "week_target", "amount_cents": 3000}]
    assert (body["week"]["donated"], body["week"]["remaining"]) == ("30.00", "15.00")
    transaction = db.get(ImperiumVaultTransaction, body["donation"]["vault_transaction_id"])
    assert (transaction.transaction_type, transaction.amount_cents, transaction.category, transaction.source, transaction.note) == (
        "expense", 3000, "sadaqa", "path_sadaqa", "Sadaqa",
    )
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "path.sadaqa.recorded"))
    assert "amount" not in str(event.payload) and "quartier" not in str(event.payload)
    assert client.get(f"{BASE}/summary").json()["business_profit"] == "800.00"  # la dépense sadaqa est personnelle


def test_carry_and_closed_week_are_frozen(db) -> None:
    user = _user(db)
    client = _client(db, user)
    last = _this_monday() - timedelta(days=7)
    _vault(db, user, "income", 80_000, "vtc", last)  # base 800 × 5 % × 1,125 = 45 €
    _donate(client, 2500, donated_at=_at(last + timedelta(days=2)).isoformat(), record_in_vault=False)
    summary = client.get(f"{BASE}/summary").json()
    assert (summary["carried_in"], summary["base_target"], summary["target"]) == ("20.00", "0.00", "20.00")
    assert summary["carry_message"] == "Montant reporté : 20,00 €."
    assert client.get(f"{BASE}/summary", params={"week_start": last.isoformat()}).json()["remaining"] == "20.00"
    assert sadaqa.close_weeks(db, user, datetime.now(UTC)) == 1
    db.commit()
    _vault(db, user, "income", 80_000, "vtc", last)  # registre modifié après la clôture : semaine figée
    closed = client.get(f"{BASE}/summary", params={"week_start": last.isoformat()}).json()
    assert (closed["closed"], closed["profit_source"], closed["remaining"]) == (True, "snapshot", "20.00")
    late = _donate(client, 500, donated_at=_at(last + timedelta(days=3)).isoformat(), record_in_vault=False).json()
    assert late["donation"]["related_week_start"] == _this_monday().isoformat()
    assert late["warnings"] == ["Cette semaine est close : le don compte pour la semaine en cours."]
    assert late["donation"]["allocation"] == [{"part": "carry", "amount_cents": 500}]
    assert late["week"]["remaining"] == "15.00"
    assert sadaqa.close_weeks(db, user, datetime.now(UTC)) == 0


def test_over_donation_leaves_no_negative_remaining(db) -> None:
    user = _user(db)
    client = _client(db, user)
    _vault(db, user, "income", 80_000, "vtc", _this_monday())
    body = _donate(client, 8000, record_in_vault=False).json()
    assert body["donation"]["allocation"] == [{"part": "week_target", "amount_cents": 4500},
                                              {"part": "beyond_target", "amount_cents": 3500}]
    assert (body["week"]["donated"], body["week"]["remaining"]) == ("80.00", "0.00")


def test_vault_failure_keeps_the_donation_pending_until_retry(db, monkeypatch) -> None:
    user = _user(db)
    client = _client(db, user)
    real = vault_transactions.create_vault_transaction

    def broken(*args, **kwargs):
        raise RuntimeError("vault down")

    monkeypatch.setattr(vault_transactions, "create_vault_transaction", broken)
    created = _donate(client, 1000)
    assert created.status_code == 201, created.text
    donation = created.json()["donation"]
    assert (donation["vault_status"], donation["vault_transaction_id"]) == ("pending", None)
    assert created.json()["warnings"] == [sadaqa.VAULT_PENDING]
    assert client.get(f"{BASE}/summary").json()["vault_pending"] == 1
    failed = client.post(f"{BASE}/donations/{donation['id']}/vault-retry")
    assert (failed.status_code, failed.json()["code"]) == (503, "VAULT_PENDING")
    monkeypatch.setattr(vault_transactions, "create_vault_transaction", real)
    retried = client.post(f"{BASE}/donations/{donation['id']}/vault-retry")
    assert retried.status_code == 200, retried.text
    assert retried.json()["vault_status"] == "recorded"
    again = client.post(f"{BASE}/donations/{donation['id']}/vault-retry").json()
    assert again["vault_transaction_id"] == retried.json()["vault_transaction_id"]
    assert len(list(db.scalars(select(ImperiumVaultTransaction).where(ImperiumVaultTransaction.user_id == user.id)))) == 1


def test_donation_without_vault(db) -> None:
    user = _user(db)
    client = _client(db, user)
    donation = _donate(client, 1000, record_in_vault=False).json()["donation"]
    assert donation["vault_status"] == "not_requested"
    assert client.post(f"{BASE}/donations/{donation['id']}/vault-retry").status_code == 409
    assert db.scalar(select(ImperiumVaultTransaction).where(ImperiumVaultTransaction.user_id == user.id)) is None


def test_delete_reverses_the_vault_expense(db) -> None:
    user = _user(db)
    client = _client(db, user)
    donation = _donate(client, 1200).json()["donation"]
    deleted = client.delete(f"{BASE}/donations/{donation['id']}")
    assert deleted.json() == {"deleted": True, "vault_reversed": True}
    assert db.get(PathSadaqaDonation, donation["id"]) is None
    reversal = db.scalar(select(ImperiumVaultTransaction).where(
        ImperiumVaultTransaction.reversal_of_transaction_id == donation["vault_transaction_id"]))
    assert (reversal.transaction_type, reversal.amount_cents) == ("income", 1200)
    assert client.delete(f"{BASE}/donations/{donation['id']}").status_code == 404
    assert client.get(f"{BASE}/donations").json()["items"] == []


def test_idempotency_and_input_checks(db) -> None:
    client = _client(db, _user(db))
    key = _key()
    first = client.post(f"{BASE}/donations", headers=key, json={"amount_cents": 700, "record_in_vault": False})
    replay = client.post(f"{BASE}/donations", headers=key, json={"amount_cents": 700, "record_in_vault": False})
    assert (first.status_code, replay.status_code) == (201, 200)
    assert replay.json()["donation"]["id"] == first.json()["donation"]["id"]
    assert client.post(f"{BASE}/donations", headers=key, json={"amount_cents": 800, "record_in_vault": False}).status_code == 409
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert _donate(client, 100, donated_at=future).status_code == 422
    assert _donate(client, 0).status_code == 422
    assert client.get(f"{BASE}/summary", params={"week_start": (_this_monday() + timedelta(days=1)).isoformat()}).status_code == 422
    assert client.get(f"{BASE}/summary", params={"week_start": (_this_monday() + timedelta(days=7)).isoformat()}).status_code == 422
    assert len(client.get(f"{BASE}/donations").json()["items"]) == 1


def test_week_close_job(db) -> None:
    user = _user(db)
    client = _client(db, user)
    last = _this_monday() - timedelta(days=7)
    _donate(client, 500, donated_at=_at(last).isoformat(), record_in_vault=False)
    ctx = SimpleNamespace(db=db, items_in=0, items_out=0, detail={})
    sadaqa.sadaqa_week_close_job(ctx, SimpleNamespace(to_ts=datetime.now(UTC)))
    assert ctx.items_out >= 1
    week = db.get(PathSadaqaWeek, (user.id, last))
    assert (week.donated_cents, week.remaining_cents, week.carried_in_cents) == (500, 0, 0)
