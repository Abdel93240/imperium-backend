from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.router import api_router


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = BACKEND_ROOT.parent / "docs_master"


class FakeDb:
    def __init__(self) -> None:
        self.added = []
        self.flushed = False
        self.committed = False
        self.rolled_back = False
        self.queries = []

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def scalar(self, query):
        self.queries.append(query)
        return None

    def scalars(self, query):
        self.queries.append(query)
        return []


def _client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4())


def test_daily_plan_route_order_and_accessibility() -> None:
    router_text = (BACKEND_ROOT / "app" / "api" / "v1" / "router.py").read_text(encoding="utf-8")
    legacy_route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py").read_text(
        encoding="utf-8"
    )

    assert router_text.index("imperium_daily_plan.router") < router_text.index("imperium.router")
    assert '@router.get("/daily-plan"' not in legacy_route_text

    response = _client(FakeDb(), _user()).get("/api/imperium/daily-plan")
    assert response.status_code == 200

    mission_response = _client(FakeDb(), _user()).get("/api/imperium/missions/active")
    vault_response = _client(FakeDb(), _user()).get("/api/imperium/vault/summary")
    path_response = _client(FakeDb(), _user()).get("/api/imperium/path/today")
    pulse_response = _client(FakeDb(), _user()).get("/api/imperium/pulse/today")

    assert mission_response.status_code in {200, 404}
    assert vault_response.status_code in {200, 404}
    assert path_response.status_code in {200, 404}
    assert pulse_response.status_code in {200, 404}


def test_daily_plan_contract_shape_and_metadata_semantics() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/daily-plan")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "date",
        "dashboard",
        "mission",
        "path",
        "pulse",
        "readiness",
        "summary",
        "meta",
        "safe_explanation",
    }
    assert body["meta"]["daily_plan_version"] == "v1"
    assert body["meta"]["read_only"] is True
    snapshot_generated_at = datetime.fromisoformat(body["meta"]["snapshot_generated_at"].replace("Z", "+00:00"))
    assert snapshot_generated_at.tzinfo is not None
    assert snapshot_generated_at.utcoffset() is not None and snapshot_generated_at.utcoffset().total_seconds() == 0
    assert body["dashboard"]["meta"]["read_only"] is True
    assert body["dashboard"]["meta"]["dashboard_version"] == "v1"
    assert body["readiness"] == {
        "dashboard_present": True,
        "mission_present": False,
        "path_items_count": 0,
        "pulse_entry_present": False,
        "read_only": True,
        "safe_explanation": "Daily plan readiness snapshot computed from existing read-only data.",
    }
    assert body["summary"] == {
        "has_active_mission": False,
        "path_items_count": 0,
        "pulse_entry_present": False,
        "safe_explanation": "Daily plan summary computed from existing read-only snapshots.",
    }
    assert "score" not in str(body).lower()
    assert "recommendation" not in str(body).lower()
    assert "health_score" not in str(body).lower()


def test_daily_plan_is_read_only_and_does_not_require_idempotency_key() -> None:
    db = FakeDb()
    response = _client(db, _user()).get("/api/imperium/daily-plan")

    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_daily_plan_readiness_is_bool_count_only_and_snapshot_coherent() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/daily-plan")

    assert response.status_code == 200
    readiness = response.json()["readiness"]
    assert readiness == {
        "dashboard_present": True,
        "mission_present": False,
        "path_items_count": 0,
        "pulse_entry_present": False,
        "read_only": True,
        "safe_explanation": "Daily plan readiness snapshot computed from existing read-only data.",
    }
    for key, value in readiness.items():
        if key in {"dashboard_present", "mission_present", "pulse_entry_present", "read_only"}:
            assert isinstance(value, bool)
        elif key == "path_items_count":
            assert isinstance(value, int)
            assert value >= 0


def test_daily_plan_docs_explicitly_document_contract_rules() -> None:
    contracts_text = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8").lower()
    schema_text = (DOCS_ROOT / "05_DATABASE_SCHEMA.md").read_text(encoding="utf-8").lower()

    for text in (contracts_text, schema_text):
        assert "/api/imperium/daily-plan" in text
        assert "read-only" in text
        assert "europe/paris" in text
        assert "meta.daily_plan_version" in text
        assert "meta.read_only" in text
        assert "snapshot_generated_at" in text
        assert "readiness snapshot" in text
        assert "not a score" in text
        assert "not a recommendation" in text
        assert "ai" in text
        assert "n8n" in text
        assert "ocr" in text
        assert "scoring" in text
        assert "coaching" in text
        assert "recommendation" in text
