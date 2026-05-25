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

    def add(self, obj) -> None:
        self.added.append(obj)

    def flush(self) -> None:
        self.flushed = True

    def commit(self) -> None:
        self.committed = True


def _client(db: FakeDb, current_user: SimpleNamespace) -> TestClient:
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4())


def test_frontend_theme_tokens_endpoint_present_and_jwt_scoped() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/theme-tokens")
    assert response.status_code == 200


def test_frontend_theme_tokens_get_only_no_idempotency_key_required() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/theme-tokens")
    assert response.status_code == 200


def test_frontend_theme_tokens_response_shape_and_deterministic_order() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/theme-tokens")
    assert response.status_code == 200
    body = response.json()

    assert set(body) == {
        "theme_version",
        "read_only",
        "style_name",
        "palette",
        "surfaces",
        "spacing_scale",
        "radius_scale",
        "typography_scale",
        "safe_explanation",
    }
    assert body["theme_version"] == "v1"
    assert body["read_only"] is True
    assert body["style_name"] == "imperium_luxury"
    assert body["safe_explanation"] == "Frontend theme token metadata for Imperium V1."

    assert body["palette"] == {
        "background": "matte_black",
        "surface": "deep_blue_black",
        "primary": "champagne_gold",
        "secondary": "premium_green",
        "danger": "controlled_red",
        "muted": "warm_gray",
    }

    assert [(item["key"], item["purpose"], item["token"]) for item in body["surfaces"]] == [
        ("base", "Main application background.", "surface.base"),
        ("card", "Primary content card surface.", "surface.card"),
        ("elevated", "Elevated premium panel surface.", "surface.elevated"),
    ]
    assert [(item["key"], item["value"]) for item in body["spacing_scale"]] == [
        ("xs", 4),
        ("sm", 8),
        ("md", 12),
        ("lg", 16),
        ("xl", 24),
    ]
    assert [(item["key"], item["value"]) for item in body["radius_scale"]] == [
        ("sm", 8),
        ("md", 14),
        ("lg", 20),
        ("xl", 28),
    ]
    assert [(item["key"], item["purpose"]) for item in body["typography_scale"]] == [
        ("caption", "Compact metadata labels."),
        ("body", "Default readable body text."),
        ("title", "Section titles."),
        ("hero", "Primary dashboard focus text."),
    ]


def test_frontend_theme_tokens_has_no_user_secret_provider_infra_business_or_assets_or_hex() -> None:
    response = _client(FakeDb(), _user()).get("/api/imperium/frontend/theme-tokens")
    assert response.status_code == 200
    payload_text = str(response.json()).lower()

    for forbidden in (
        "user_id",
        "secret",
        "provider",
        "infra",
        "host",
        "database",
        "postgres",
        "pgvector",
        "mission",
        "vault",
        "path",
        "pulse",
        "daily_plan",
        "home",
        "contract",
        "health",
        "dynamic discovery",
        "n8n",
        "ocr",
        "scoring",
        "coaching",
        "recommendation",
        "font",
        "asset",
        "http://",
        "https://",
        "#",
    ):
        assert forbidden not in payload_text


def test_frontend_theme_tokens_read_only_no_db_write() -> None:
    db = FakeDb()
    response = _client(db, _user()).get("/api/imperium/frontend/theme-tokens")
    assert response.status_code == 200
    assert db.added == []
    assert db.flushed is False
    assert db.committed is False


def test_frontend_theme_tokens_docs_metadata_only_static_v1_not_dynamic_theme_preference_health_or_discovery() -> None:
    contracts_docs = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8").lower()
    schema_docs = (DOCS_ROOT / "05_DATABASE_SCHEMA.md").read_text(encoding="utf-8").lower()

    for text in (contracts_docs, schema_docs):
        assert "/api/imperium/frontend/theme-tokens" in text
        assert "metadata only" in text
        assert "static deterministic v1" in text
        assert "not a dynamic theme" in text
        assert "not a user preference" in text
        assert "not a health check" in text
        assert "not a dynamic discovery" in text
        assert "no business data read" in text
        assert "no secrets/providers/infra metadata" in text
