from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = BACKEND_ROOT.parent / "docs_master"


def test_pulse_routes_inventory_and_order_are_stable() -> None:
    route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_pulse.py").read_text(
        encoding="utf-8"
    )

    assert route_text.index('@router.get("/today"') < route_text.index('@router.get("/stats/summary"')
    assert route_text.index('@router.get("/stats/summary"') < route_text.index('@router.post("/entries"')
    assert route_text.index('@router.post("/entries"') < route_text.index('@router.get("/entries"')
    assert route_text.index('@router.get("/entries"') < route_text.index('@router.get("/entries/{entry_id}"')

    for route in (
        '@router.get("/today"',
        '@router.get("/stats/summary"',
        '@router.post("/entries"',
        '@router.get("/entries"',
        '@router.get("/entries/{entry_id}"',
    ):
        assert route in route_text


def test_pulse_contract_docs_cover_all_endpoints_and_invariants() -> None:
    contracts_text = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8")
    schema_text = (DOCS_ROOT / "05_DATABASE_SCHEMA.md").read_text(encoding="utf-8")
    lowered_docs = "\n".join([contracts_text, schema_text]).lower()

    for endpoint in (
        "/api/imperium/pulse/entries",
        "/api/imperium/pulse/entries/{entry_id}",
        "/api/imperium/pulse/today",
        "/api/imperium/pulse/stats/summary",
    ):
        assert endpoint in contracts_text

    assert "required `idempotency-key`" in lowered_docs or "required idempotency-key" in lowered_docs
    assert "get /api/imperium/pulse/today" in lowered_docs
    assert "read-only" in lowered_docs
    assert "append-only" in lowered_docs
    assert "currentuserdep" in lowered_docs
    assert "no automatic entry creation" in lowered_docs
    assert "no automatic scoring" in lowered_docs
    assert "no automatic coaching" in lowered_docs
    assert "no automatic recommendations" in lowered_docs
    assert "no automatic mission/vault/path linkage" in lowered_docs
    assert "no ai" in lowered_docs
    assert "no n8n" in lowered_docs
    assert "pgvector" in lowered_docs
    assert "embedding" in lowered_docs
    assert "memory" in lowered_docs
    assert "calendar" in lowered_docs


def test_pulse_contract_does_not_add_new_behavioral_surface() -> None:
    route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_pulse.py").read_text(
        encoding="utf-8"
    )
    service_text = (BACKEND_ROOT / "app" / "services" / "pulse" / "entries.py").read_text(encoding="utf-8")
    lowered = "\n".join([route_text, service_text]).lower()

    for forbidden in (
        "openai",
        "anthropic",
        "gemini",
        "claude",
        "qwenclient",
        "n8n",
        "trigger_n8n",
        "ai agent",
        "aiagent",
        "pgvector",
        "embedding",
        "memory commit",
        "calendar replanning",
        "scoring",
        "coaching",
        "recommendation",
        "mission_id",
        "vault",
        "path linkage",
    ):
        assert forbidden not in lowered
