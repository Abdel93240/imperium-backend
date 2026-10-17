"""PostgreSQL : médical Pulse — documents et règles sous double consentement (doc 34, doc 08 PULSE-004)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse medical DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_dashboard  # noqa: E402
from app.api.v1.routes import imperium_pulse_health as routes  # noqa: E402
from app.services.pulse import medical  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402

P = "/api/imperium/pulse"
DOCS = f"{P}/medical-documents"
RULES = f"{P}/medical-rules"


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
        {"id": str(user_id), "email": f"med-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    for router in (routes.router, imperium_pulse_dashboard.router):
        app.include_router(router, prefix="/api/imperium/pulse")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


@pytest.fixture(autouse=True)
def _storage(tmp_path, monkeypatch):
    monkeypatch.setattr(medical, "storage_root", lambda: tmp_path)
    return tmp_path


def _version(client) -> str:
    return next(c for c in client.get(f"{P}/consents").json()["items"] if c["domain"] == "medical")["text_version"]


def _consent(client) -> None:
    assert client.post(f"{P}/consents/medical", json={"text_version": _version(client)}).status_code == 200


def _upload(client, content=b"%PDF-1.4 bilan", filename="bilan.pdf", key=None, **params):
    query = {"doc_type": "blood_test", "consent": True, "consent_version": _version(client), **params}
    return client.post(DOCS, params=query, content=content,
                       headers={"X-Filename": filename, "Content-Type": "application/pdf", "Idempotency-Key": key or uuid4().hex})


def _rule(client, **extra) -> dict:
    payload = {"rule_type": "nutrition_constraint", "rule_text": "Augmenter les apports en fer.", "severity": "warning", **extra}
    response = client.post(RULES, headers=_key(), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


CONFIRM = {"reviewed_source": True, "confirmed_text": True, "still_relevant": True}


def test_upload_needs_both_consents(db) -> None:
    client = _client(db, _user(db))
    refused = _upload(client)
    assert refused.status_code == 403 and refused.json()["domain"] == "medical"
    _consent(client)
    assert _upload(client, consent=False).status_code == 403  # accord de cet envoi manquant
    assert _upload(client, consent_version="ancienne").status_code == 409


def test_upload_stores_the_file_privately_and_lists_it(db, _storage) -> None:
    user = _user(db)
    client = _client(db, user)
    _consent(client)
    uploaded = _upload(client, doc_date="2026-10-01")
    assert uploaded.status_code == 201, uploaded.text
    doc = uploaded.json()
    assert (doc["status"], doc["doc_type"], doc["doc_date"], doc["original_name"]) == ("uploaded", "blood_test", "2026-10-01", "bilan.pdf")
    assert doc["message"] == "Analyse automatique pas encore active : ajoute les règles à la main."
    assert doc["retention_delete_after"].startswith((date.today() + timedelta(days=90)).isoformat()[:7])
    files = [p for p in _storage.rglob("*") if p.is_file()]
    assert len(files) == 1 and oct(files[0].stat().st_mode & 0o777) == "0o600"
    assert "bilan" not in files[0].name  # nom interne, jamais le nom d'origine
    assert client.get(f"{DOCS}/{doc['id']}/file").content == b"%PDF-1.4 bilan"
    assert [d["id"] for d in client.get(DOCS).json()["items"]] == [doc["id"]]
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.medical_document.uploaded"))
    assert event.payload == {"document_id": doc["id"]}


def test_upload_rules_and_replay(db) -> None:
    client = _client(db, _user(db))
    _consent(client)
    assert _upload(client, filename="scan.dcm").status_code == 422
    assert _upload(client, content=b"").status_code == 422
    assert _upload(client, doc_type="genetic").status_code == 422
    first = _upload(client, key="u1")
    again = _upload(client, key="u1")
    other = _upload(client, key="u1", content=b"%PDF autre")
    assert first.status_code == 201 and again.status_code == 200 and again.json()["id"] == first.json()["id"]
    assert other.status_code == 409


def test_rule_is_proposed_then_activated_with_explicit_confirmation(db) -> None:
    user = _user(db)
    client = _client(db, user)
    _consent(client)
    doc = _upload(client).json()
    rule = _rule(client, source_document_id=doc["id"], source_quote="Hb 12,4 g/dL", expires_at="2027-01-31")
    assert (rule["status"], rule["source_document_id"]) == ("proposed", doc["id"])
    assert client.get(f"{RULES}/active").json()["items"] == []
    assert client.post(f"{RULES}/{rule['id']}/activate", headers=_key(), json={**CONFIRM, "still_relevant": False}).status_code == 422
    active = client.post(f"{RULES}/{rule['id']}/activate", headers={"Idempotency-Key": "a1"}, json=CONFIRM)
    assert active.status_code == 200 and active.json()["status"] == "active" and active.json()["validated_at"]
    assert client.post(f"{RULES}/{rule['id']}/activate", headers={"Idempotency-Key": "a1"}, json=CONFIRM).json() == active.json()
    assert [r["id"] for r in client.get(f"{RULES}/active").json()["items"]] == [rule["id"]]
    event = db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.medical_rule.activated"))
    assert event.payload == {"rule_id": rule["id"], "rule_type": "nutrition_constraint", "severity": "warning"}
    banners = {b["kind"]: b for b in client.get(f"{P}/dashboard").json()["banners"]}
    assert banners["medical_rules"]["message"] == "1 règle médicale active."


def test_already_expired_rule_cannot_be_activated(db) -> None:
    client = _client(db, _user(db))
    _consent(client)
    rule = _rule(client, expires_at="2020-01-01")
    assert client.post(f"{RULES}/{rule['id']}/activate", headers=_key(), json=CONFIRM).status_code == 409


def test_critical_rule_needs_acknowledgement(db) -> None:
    client = _client(db, _user(db))
    _consent(client)
    rule = _rule(client, severity="critical", rule_type="workout_limit", rule_text="Pas d'effort intense.")
    refused = client.post(f"{RULES}/{rule['id']}/activate", headers=_key(), json=CONFIRM)
    assert refused.status_code == 409 and "médecin" in refused.json()["detail"]
    ok = client.post(f"{RULES}/{rule['id']}/activate", headers=_key(), json={**CONFIRM, "acknowledge_critical": True})
    assert ok.status_code == 200 and ok.json()["critical_acknowledged_at"] is not None


def test_new_rule_can_supersede_an_active_one(db) -> None:
    client = _client(db, _user(db))
    _consent(client)
    old = _rule(client)
    client.post(f"{RULES}/{old['id']}/activate", headers=_key(), json=CONFIRM)
    new = _rule(client, rule_text="Fer : 18 mg par jour.")
    client.post(f"{RULES}/{new['id']}/activate", headers=_key(), json={**CONFIRM, "supersedes_rule_id": old["id"]})
    rules = {r["id"]: r for r in client.get(RULES).json()["items"]}
    assert (rules[old["id"]]["status"], rules[old["id"]]["superseded_by"]) == ("superseded", new["id"])
    assert [r["id"] for r in client.get(f"{RULES}/active").json()["items"]] == [new["id"]]


def test_deactivate_and_writes_need_consent(db) -> None:
    client = _client(db, _user(db))
    _consent(client)
    rule = _rule(client)
    client.post(f"{RULES}/{rule['id']}/activate", headers=_key(), json=CONFIRM)
    client.delete(f"{P}/consents/medical")
    assert client.post(RULES, headers=_key(), json={"rule_type": "general_context", "rule_text": "x", "severity": "info"}).status_code == 403
    off = client.post(f"{RULES}/{rule['id']}/deactivate")  # retirer reste toujours possible
    assert off.status_code == 200 and off.json()["status"] == "inactive"
    assert client.get(f"{RULES}/active").json()["items"] == []


def test_deleting_a_document_deletes_its_file_and_rules(db, _storage) -> None:
    user = _user(db)
    client = _client(db, user)
    _consent(client)
    doc = _upload(client).json()
    rule = _rule(client, source_document_id=doc["id"])
    client.post(f"{RULES}/{rule['id']}/activate", headers=_key(), json=CONFIRM)
    kept = _rule(client)
    assert client.delete(f"{DOCS}/{doc['id']}").status_code == 204
    assert [p for p in _storage.rglob("*") if p.is_file()] == []
    assert [r["id"] for r in client.get(RULES).json()["items"]] == [kept["id"]]
    types = sorted(e.event_type for e in db.scalars(select(Event).where(Event.user_id == user.id, Event.event_type.like("pulse.medical%"))))
    assert "pulse.medical_document.deleted" in types and "pulse.medical_rule.deactivated" in types


def test_retention_job_purges_old_documents_and_expires_rules(db, _storage) -> None:
    from app.models.imperium import PulseMedicalDocument, PulseMedicalRule

    client = _client(db, _user(db))
    _consent(client)
    doc = _upload(client).json()
    rule = _rule(client, source_document_id=doc["id"], expires_at="2099-01-01")
    assert client.post(f"{RULES}/{rule['id']}/activate", headers=_key(), json=CONFIRM).status_code == 200
    db.get(PulseMedicalRule, rule["id"]).expires_at = date(2026, 10, 1)  # échue avant le passage du job
    db.get(PulseMedicalDocument, doc["id"]).retention_delete_after = datetime(2026, 1, 1, tzinfo=UTC)
    db.commit()
    ctx = SimpleNamespace(db=db, items_in=None, items_out=None, detail={})
    medical.medical_retention_job(ctx, SimpleNamespace(from_ts=None, to_ts=datetime(2026, 10, 17, 3, 0, tzinfo=UTC)))
    db.commit()
    db.expire_all()
    assert db.get(PulseMedicalDocument, doc["id"]) is None
    assert [p for p in _storage.rglob("*") if p.is_file()] == []
    kept = db.get(PulseMedicalRule, rule["id"])
    assert (kept.status, kept.source_document_id) == ("expired", None)  # la règle reste, le document est purgé
    assert ctx.detail["documents_purged"] >= 1 and ctx.detail["rules_expired"] >= 1


def test_other_users_cannot_reach_documents_or_rules(db) -> None:
    owner, other = _user(db), _user(db)
    client = _client(db, owner)
    _consent(client)
    doc = _upload(client).json()
    rule = _rule(client)
    stranger = _client(db, other)
    _consent(stranger)
    assert stranger.get(f"{DOCS}/{doc['id']}/file").status_code == 404
    assert stranger.delete(f"{DOCS}/{doc['id']}").status_code == 404
    assert stranger.post(f"{RULES}/{rule['id']}/activate", headers=_key(), json=CONFIRM).status_code == 404
    assert stranger.post(RULES, headers=_key(), json={"rule_type": "general_context", "rule_text": "x", "severity": "info",
                                                      "source_document_id": doc["id"]}).status_code == 404


def test_seeded_job_handler_resolves() -> None:
    from app.services.runner.engine import resolve_handler

    assert resolve_handler("app.services.pulse.medical:medical_retention_job") is medical.medical_retention_job
