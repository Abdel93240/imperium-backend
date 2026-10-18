"""PostgreSQL : réglages Vault VAU-12 — synthèse en lecture seule, sadaqa lue dans Path."""
from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("vault settings DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_path_sadaqa, vault  # noqa: E402
from app.models.auth import User  # noqa: E402


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


def _client(db) -> TestClient:
    user_id = uuid4()
    db.execute(
        text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) VALUES (:id, :email, FALSE, now(), now())"),
        {"id": str(user_id), "email": f"vset-{user_id}@example.test"},
    )
    db.commit()
    user = db.get(User, user_id)
    app = FastAPI()
    app.include_router(vault.router, prefix="/api/vault")
    app.include_router(imperium_path_sadaqa.router, prefix="/api/imperium/path")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_settings_summary_follows_each_screen(db) -> None:
    client = _client(db)
    empty = client.get("/api/vault/settings").json()
    assert (empty["sadaqa_percentage"], empty["sadaqa_source"], empty["completion"]) == ("0.0500", "path", 2)
    assert [(r["key"], r["complete"], r["target"]) for r in empty["rows"]] == [
        ("sadaqa", True, "PAT-11d"), ("categories", True, "VAU-09"), ("wallet", False, "VAU-10"), ("upcoming", False, "VAU-11"),
    ]
    assert empty["rows"][0]["value"] == "5 %"
    client.patch("/api/imperium/path/sadaqa/settings", headers={"Idempotency-Key": uuid4().hex},
                 json={"percentage": "0.075", "base_version": 0, "apply_to_current_week": True})
    client.post("/api/vault/wallet/snapshots", headers={"Idempotency-Key": uuid4().hex}, json={"cash_cents": 1000, "bank_cents": 0})
    client.post("/api/vault/upcoming-expenses", json={"label_fr": "Loyer", "amount": "600.00", "due_date": "2026-11-01", "category": "loyer"})
    full = client.get("/api/vault/settings").json()
    assert (full["sadaqa_percentage"], full["rows"][0]["value"], full["completion"]) == ("0.0750", "7,5 %", 4)
    assert full["active_upcoming_expenses"] == 1 and full["last_wallet_snapshot_at"] is not None
    assert client.patch("/api/vault/settings", json={}).status_code == 405
