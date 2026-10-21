"""PostgreSQL : paramètres avancés de l'IA (doc 73, doc 30 §3, brief B8)."""
from __future__ import annotations

import os
import stat
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("ai advanced settings DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.schemas.ai_advanced import RoleModelUpdate, ThresholdBand, ThresholdsUpdate  # noqa: E402
from app.services.ai import advanced  # noqa: E402
from app.services.ai.roles import resolve_role  # noqa: E402


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


@pytest.fixture()
def keys_dir(tmp_path, monkeypatch):
    path = tmp_path / "keys"
    monkeypatch.setattr(advanced, "keys_root", lambda: path)
    return path


# ---------- Rôles ----------

def test_the_eleven_fixed_roles_are_listed(db) -> None:
    roles = [row.role for row in advanced.list_roles(db).roles]
    assert roles == list(advanced.ROLES)
    assert len(roles) == 11 and "high_reasoning_safeguard" in roles


def test_update_creates_a_new_active_version(db) -> None:
    before = resolve_role(db, "first_cloud_tier")
    updated = advanced.update_role(db, role="first_cloud_tier",
                                   payload=RoleModelUpdate(provider="anthropic", model_id=f"claude-test-{uuid4().hex[:6]}", effort="medium"))
    after = resolve_role(db, "first_cloud_tier")
    assert after.version == before.version + 1 and after.model_id == updated.model_id and after.effort == "medium"
    assert after.sensitivity_route == before.sensitivity_route


def test_local_only_roles_refuse_cloud_providers(db) -> None:
    with pytest.raises(advanced.AdvancedValidationError):
        advanced.update_role(db, role="local_executor", payload=RoleModelUpdate(provider="openai", model_id="gpt-x"))


def test_direct_roles_refuse_openrouter(db) -> None:
    with pytest.raises(advanced.AdvancedValidationError):
        advanced.update_role(db, role="sustained_long_context", payload=RoleModelUpdate(provider="openrouter", model_id="x/y"))


def test_unknown_role_cannot_be_created(db) -> None:
    with pytest.raises(advanced.AdvancedNotFoundError):
        advanced.update_role(db, role="my_new_role", payload=RoleModelUpdate(provider="openai", model_id="x"))


def test_unseeded_role_gets_its_first_version(db) -> None:
    advanced.update_role(db, role="high_reasoning_safeguard", payload=RoleModelUpdate(provider="openai", model_id="gpt-safeguard-test"))
    row = resolve_role(db, "high_reasoning_safeguard")
    assert row.model_id == "gpt-safeguard-test" and row.sensitivity_route == "openrouter_allowed"


def test_catalog_is_honest_about_remote_refresh(db) -> None:
    catalog = advanced.catalog(db)
    assert catalog.remote_catalog_available is False
    assert "local" in catalog.providers and catalog.providers["local"]


# ---------- Seuils /200 ----------

def _bands(*edges):
    labels = ["IA locale", "Premier niveau cloud", "Raisonnement poussé", "Mécanique critique"]
    return ThresholdsUpdate(bands=[ThresholdBand(label=label, start=a, end=b) for label, (a, b) in zip(labels, edges, strict=True)])


def test_default_thresholds_follow_the_brief() -> None:
    assert [(b.start, b.end) for b in advanced.DEFAULT_THRESHOLDS.bands] == [(0, 99), (100, 139), (140, 179), (180, 200)]


def test_thresholds_are_saved_as_a_new_parameter_version(db) -> None:
    saved = advanced.update_thresholds(db, payload=_bands((0, 109), (110, 139), (140, 179), (180, 200)))
    assert [(b.start, b.end) for b in saved.bands][0] == (0, 109)
    assert advanced.get_thresholds(db).bands[0].end == 109
    advanced.update_thresholds(db, payload=_bands((0, 99), (100, 139), (140, 179), (180, 200)))


@pytest.mark.parametrize(
    "edges",
    [((0, 98), (100, 139), (140, 179), (180, 200)), ((0, 99), (99, 139), (140, 179), (180, 200)),
     ((1, 99), (100, 139), (140, 179), (180, 200)), ((0, 99), (100, 139), (140, 179), (180, 199)),
     ((0, 99), (100, 90), (91, 179), (180, 200))],
)
def test_gaps_overlaps_and_bounds_are_refused(db, edges) -> None:
    with pytest.raises(advanced.AdvancedValidationError):
        advanced.update_thresholds(db, payload=_bands(*edges))


# ---------- Clés API ----------

def test_api_keys_are_write_only_files_with_status(keys_dir) -> None:
    assert {k.provider: k.present for k in advanced.list_api_keys().keys} == {
        "openrouter": False, "openai": False, "anthropic": False, "google": False}
    advanced.replace_api_key("anthropic", "sk-ant-" + "x" * 30)
    status = {k.provider: k.present for k in advanced.list_api_keys().keys}
    path = keys_dir / "anthropic.key"
    assert status["anthropic"] is True and path.read_text() == "sk-ant-" + "x" * 30
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert stat.S_IMODE(os.stat(keys_dir).st_mode) == 0o700
    assert "sk-ant" not in advanced.list_api_keys().model_dump_json()

    advanced.delete_api_key("anthropic")
    assert not path.exists() and {k.provider: k.present for k in advanced.list_api_keys().keys}["anthropic"] is False


@pytest.mark.parametrize("provider", ["../etc", "local", "OpenAI ", "mistral"])
def test_unknown_providers_are_refused(keys_dir, provider) -> None:
    with pytest.raises(advanced.AdvancedNotFoundError):
        advanced.replace_api_key(provider, "k" * 30)


@pytest.mark.parametrize("key", ["", "short", "has space inside the key value 123", "x" * 5000])
def test_malformed_keys_are_refused(keys_dir, key) -> None:
    with pytest.raises(advanced.AdvancedValidationError):
        advanced.replace_api_key("openai", key)


def test_routes_never_expose_a_key_reading_endpoint() -> None:
    from app.api.v1.router import api_router

    paths = {(route.path, method) for route in api_router.routes for method in getattr(route, "methods", set())}
    assert ("/ai/advanced/api-keys", "GET") in paths and ("/ai/advanced/api-keys/{provider}", "PUT") in paths
    assert ("/ai/advanced/api-keys/{provider}", "GET") not in paths
    for expected in [("/ai/advanced/roles", "GET"), ("/ai/advanced/roles/{role}", "PUT"), ("/ai/advanced/catalog", "GET"),
                     ("/ai/advanced/thresholds", "GET"), ("/ai/advanced/thresholds", "PUT"), ("/ai/advanced/api-keys/{provider}", "DELETE")]:
        assert expected in paths, expected


@pytest.fixture()
def isolated_db(engine):
    """Les interrupteurs committent : transaction externe annulée, rien ne fuit dans la base de test."""
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


def test_slots_are_switched_on_and_off_with_their_guards(isolated_db) -> None:
    db = isolated_db
    from app.services.ai import slot_settings
    from app.services.params import get_parameter

    read = slot_settings.read(db)
    by_code = {slot.slot_code: slot for slot in read.slots}
    assert by_code["chat.converse"].engine == "local" and by_code["wr.exit_audit"].engine == "cloud"
    assert by_code["nexus.escalation"].engine == "cloud" and by_code["imperium.advice"].engine == "local"

    after = slot_settings.set_mode(db, slot_code="imperium.advice", mode="live")
    assert {s.slot_code: s.mode for s in after.slots}["imperium.advice"] == "live"
    assert get_parameter(db, "ai.local_slot_modes")["imperium.advice"] == "live"
    slot_settings.set_mode(db, slot_code="nexus.escalation", mode="live")
    assert get_parameter(db, "ai.cloud_slot_modes")["nexus.escalation"] == "live"
    assert slot_settings.set_transport(db, transport="subscription").transport == "subscription"
    with pytest.raises(slot_settings.SlotSettingsError):
        slot_settings.set_mode(db, slot_code="nope.slot", mode="live")
