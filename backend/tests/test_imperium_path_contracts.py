from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DOCS_ROOT = BACKEND_ROOT.parent / "docs_master"


def test_path_contract_inventory_and_route_order_are_consolidated() -> None:
    route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_path.py").read_text(encoding="utf-8")
    contracts_text = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8").lower()

    expected_routes = (
        '@router.get("/today"',
        '@router.get("/stats/summary"',
        '@router.post("/habits"',
        '@router.get("/habits"',
        '@router.get("/habits/{habit_id}"',
        '@router.post("/habits/{habit_id}/archive"',
        '@router.post("/habits/{habit_id}/reactivate"',
        '@router.post("/habits/{habit_id}/check-ins"',
        '@router.get("/check-ins"',
        '@router.get("/check-ins/{check_in_id}"',
    )
    route_positions = [route_text.index(route) for route in expected_routes]

    assert route_positions == sorted(route_positions)
    assert route_text.index('@router.get("/today"') < route_text.index('@router.get("/stats/summary"')
    assert route_text.index('@router.get("/stats/summary"') < route_text.index('@router.get("/habits"')
    assert route_text.index('@router.get("/habits"') < route_text.index('@router.get("/habits/{habit_id}"')
    assert route_text.index('@router.get("/habits/{habit_id}"') < route_text.index('@router.post("/habits/{habit_id}/archive"')
    assert route_text.index('@router.post("/habits/{habit_id}/archive"') < route_text.index('@router.post("/habits/{habit_id}/reactivate"')
    assert route_text.index('@router.post("/habits/{habit_id}/reactivate"') < route_text.index('@router.post("/habits/{habit_id}/check-ins"')
    assert route_text.index('@router.post("/habits/{habit_id}/check-ins"') < route_text.index('@router.get("/check-ins"')
    assert route_text.index('@router.get("/check-ins"') < route_text.index('@router.get("/check-ins/{check_in_id}"')

    assert "current_user: CurrentUserDep" in route_text
    assert "Idempotency-Key" in route_text
    assert 'Header(alias="Idempotency-Key")' in route_text
    assert 'alias="date"' in route_text
    assert "no automatic check-in creation" in contracts_text
    assert "no automatic scoring" in contracts_text
    assert "no automatic mission/vault linkage" in contracts_text


def test_path_contract_post_endpoints_require_idempotency_key_and_get_endpoints_do_not() -> None:
    route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_path.py").read_text(encoding="utf-8")

    post_sections = (
        route_text.split('@router.post("/habits"', maxsplit=1)[1].split('@router.get("/habits"', maxsplit=1)[0],
        route_text.split('@router.post("/habits/{habit_id}/check-ins"', maxsplit=1)[1].split(
            '@router.post("/habits/{habit_id}/archive"',
            maxsplit=1,
        )[0],
        route_text.split('@router.post("/habits/{habit_id}/archive"', maxsplit=1)[1].split(
            '@router.post("/habits/{habit_id}/reactivate"',
            maxsplit=1,
        )[0],
        route_text.split('@router.post("/habits/{habit_id}/reactivate"', maxsplit=1)[1].split(
            '@router.get("/check-ins"',
            maxsplit=1,
        )[0],
    )
    get_sections = (
        route_text.split('@router.get("/today"', maxsplit=1)[1].split('@router.get("/stats/summary"', maxsplit=1)[0],
        route_text.split('@router.get("/stats/summary"', maxsplit=1)[1].split('@router.post("/habits"', maxsplit=1)[0],
        route_text.split('@router.get("/habits"', maxsplit=1)[1].split('@router.get("/habits/{habit_id}"', maxsplit=1)[0],
        route_text.split('@router.get("/habits/{habit_id}"', maxsplit=1)[1].split(
            '@router.post("/habits/{habit_id}/archive"',
            maxsplit=1,
        )[0],
        route_text.split('@router.get("/check-ins"', maxsplit=1)[1].split(
            '@router.get("/check-ins/{check_in_id}"',
            maxsplit=1,
        )[0],
        route_text.split('@router.get("/check-ins/{check_in_id}"', maxsplit=1)[1].split(
            "def _require_idempotency_key",
            maxsplit=1,
        )[0],
    )

    for section in post_sections:
        assert "Idempotency-Key" in section
        assert "Missing Idempotency-Key header." in route_text

    for section in get_sections:
        if '@router.get("/today"' in section or '@router.get("/stats/summary"' in section:
            assert "Idempotency-Key" not in section
            assert "Header(alias=\"Idempotency-Key\")" not in section


def test_path_contract_get_sections_are_read_only_and_free_of_forbidden_side_effects() -> None:
    route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_path.py").read_text(encoding="utf-8")
    service_text = (BACKEND_ROOT / "app" / "services" / "path" / "habits.py").read_text(encoding="utf-8")
    docs_text = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8").lower()

    read_only_sections = (
        route_text.split('@router.get("/today"', maxsplit=1)[1].split('@router.get("/stats/summary"', maxsplit=1)[0],
        route_text.split('@router.get("/stats/summary"', maxsplit=1)[1].split('@router.post("/habits"', maxsplit=1)[0],
        route_text.split('@router.get("/habits"', maxsplit=1)[1].split('@router.get("/habits/{habit_id}"', maxsplit=1)[0],
        route_text.split('@router.get("/habits/{habit_id}"', maxsplit=1)[1].split(
            '@router.post("/habits/{habit_id}/check-ins"',
            maxsplit=1,
        )[0],
        route_text.split('@router.get("/check-ins"', maxsplit=1)[1].split(
            '@router.get("/check-ins/{check_in_id}"',
            maxsplit=1,
        )[0],
        route_text.split('@router.get("/check-ins/{check_in_id}"', maxsplit=1)[1].split(
            "def _require_idempotency_key",
            maxsplit=1,
        )[0],
    )

    for section in read_only_sections:
        assert "db.add(" not in section
        assert "db.flush" not in section
        assert "db.commit" not in section

    lowered = "\n".join([route_text, service_text]).lower()
    for forbidden in (
        "qwenclient",
        "providers",
        "openai",
        "anthropic",
        "gemini",
        "claude",
        "n8n_client",
        "trigger_n8n",
        "ai agent",
        "aiagent",
        "n8n-nodes-langchain.agent",
        "pgvector",
        "embedding",
        "ai_memories",
        "memory commit",
        "calendar replanning",
        "ocr",
        "mission/vault",
        "automatic scoring",
    ):
        assert forbidden not in lowered

    assert "no automatic check-in creation" in docs_text
    assert "no automatic scoring" in docs_text
    assert "no automatic mission/vault linkage" in docs_text
