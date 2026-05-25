import json
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
DOCS_ROOT = REPO_ROOT / "docs_master"
INTERNAL_SECRET_HEADER = "X-Internal" + "-Secret"
N8N_DB_NAME = "n8n" + "_db"


def _python_files_under(*relative_roots: str) -> list[Path]:
    files: list[Path] = []
    for relative_root in relative_roots:
        files.extend((BACKEND_ROOT / relative_root).rglob("*.py"))
    return files


def test_no_plaintext_internal_secret_header_reference_in_backend_python() -> None:
    offenders = [
        path
        for path in _python_files_under("app", "tests")
        if INTERNAL_SECRET_HEADER in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_no_n8n_db_reference_in_backend_app_python() -> None:
    offenders = [
        path
        for path in _python_files_under("app")
        if N8N_DB_NAME in path.read_text(encoding="utf-8")
    ]

    assert offenders == []


def test_wr_mock_n8n_workflow_contract_is_safe_and_importable() -> None:
    workflow_path = REPO_ROOT / "ops" / "n8n" / "workflows" / "wr_interactive_start_mock.json"
    workflow_text = workflow_path.read_text(encoding="utf-8")
    workflow = json.loads(workflow_text)

    assert workflow["name"] == "IMPERIUM_WR_INTERACTIVE_START_MOCK"
    assert INTERNAL_SECRET_HEADER not in workflow_text
    assert N8N_DB_NAME not in workflow_text
    assert "createHmac" in workflow_text
    assert "INTERNAL_WEBHOOK_SECRET" in workflow_text
    assert "Idempotency-Key" in workflow_text
    assert "weekly_report.summary" in workflow_text
    assert "mock-n8n" in workflow_text
    assert "openai" not in workflow_text.lower()
    assert "anthropic" not in workflow_text.lower()
    assert "gemini" not in workflow_text.lower()


def test_wr_qwen_dry_run_n8n_workflow_contract_is_safe_and_importable() -> None:
    workflow_path = REPO_ROOT / "ops" / "n8n" / "workflows" / "wr_interactive_start_qwen_dry_run.json"
    workflow_text = workflow_path.read_text(encoding="utf-8")
    workflow = json.loads(workflow_text)
    lowered = workflow_text.lower()

    assert workflow["name"] == "IMPERIUM_WR_INTERACTIVE_START_QWEN_DRY_RUN"
    assert workflow["id"]
    assert INTERNAL_SECRET_HEADER not in workflow_text
    assert N8N_DB_NAME not in workflow_text
    assert "process.env" not in workflow_text
    assert "$env.INTERNAL_WEBHOOK_SECRET" in workflow_text
    assert "$env.IMPERIUM_API_BASE_URL" in workflow_text
    assert "createHmac" in workflow_text
    assert "INTERNAL_WEBHOOK_SECRET" in workflow_text
    assert "Idempotency-Key" in workflow_text
    assert "normalizeHttpJson" in workflow_text
    assert "/api/internal/ai/qwen/smoke" in workflow_text
    assert "/api/internal/ai/tasks/" in workflow_text
    assert "/api/internal/weekly-review/" in workflow_text
    assert "weekly_report.summary" in workflow_text
    assert "qwen-dry-run" in workflow_text
    assert "openai" not in lowered
    assert "anthropic" not in lowered
    assert "gemini" not in lowered
    assert "claude" not in lowered
    assert "opus" not in lowered
    assert "ollama" not in lowered
    assert "n8n-nodes-base.postgres" not in lowered
    assert "postgres" not in lowered
    assert "insert into" not in lowered
    assert "update " not in lowered
    assert "delete from" not in lowered
    assert "ai agent" not in lowered
    assert "aiagent" not in lowered
    assert "n8n-nodes-langchain.agent" not in lowered


def test_wr_answers_integrate_n8n_workflow_contract_is_safe_and_importable() -> None:
    workflow_path = REPO_ROOT / "ops" / "n8n" / "workflows" / "wr_answers_integrate_qwen_dry_run.json"
    workflow_text = workflow_path.read_text(encoding="utf-8")
    workflow = json.loads(workflow_text)
    lowered = workflow_text.lower()

    assert workflow["name"] == "IMPERIUM_WR_ANSWERS_INTEGRATE_QWEN_DRY_RUN"
    assert workflow["id"]
    assert INTERNAL_SECRET_HEADER not in workflow_text
    assert N8N_DB_NAME not in workflow_text
    assert "process.env" not in workflow_text
    assert "$env.INTERNAL_WEBHOOK_SECRET" in workflow_text
    assert "$env.IMPERIUM_API_BASE_URL" in workflow_text
    assert "createHmac" in workflow_text
    assert "Idempotency-Key" in workflow_text
    assert "normalizeHttpJson" in workflow_text
    assert "/api/internal/ai/tasks/" in workflow_text
    assert "/api/internal/weekly-review/" in workflow_text
    assert "weekly_report.answers.integrate" in workflow_text
    assert "weekly_report.draft" in workflow_text
    assert "qwen-dry-run" in workflow_text
    assert "openai" not in lowered
    assert "anthropic" not in lowered
    assert "gemini" not in lowered
    assert "claude" not in lowered
    assert "opus" not in lowered
    assert "ollama" not in lowered
    assert "database_url" not in lowered
    assert "db_password" not in lowered
    assert "n8n-nodes-base.postgres" not in lowered
    assert "postgres" not in lowered
    assert "insert into" not in lowered
    assert "update " not in lowered
    assert "delete from" not in lowered
    assert "ai agent" not in lowered
    assert "aiagent" not in lowered
    assert "n8n-nodes-langchain.agent" not in lowered


def test_wr_attach_does_not_auto_approve_or_write_memory() -> None:
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "weekly_review_conversation.py"
    service_text = service_path.read_text(encoding="utf-8")
    attach_section = service_text.split("def attach_initial_ai_result", maxsplit=1)[1].split(
        "def attach_ai_result_to_session",
        maxsplit=1,
    )[0]

    assert "ai_memories" not in attach_section
    assert "pgvector" not in service_text.lower()
    assert 'status = "approved"' not in attach_section
    assert 'status = "stored"' not in attach_section


def test_wr_draft_approval_path_does_not_write_memory_or_pgvector() -> None:
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "weekly_review_conversation.py"
    service_text = service_path.read_text(encoding="utf-8")
    approval_section = service_text.split("def approve_latest_draft_report", maxsplit=1)[1].split(
        "def store_approved_final_report",
        maxsplit=1,
    )[0]

    assert "ai_memories" not in approval_section
    assert "pgvector" not in approval_section.lower()
    assert "stored_at =" not in approval_section
    assert 'status = "stored"' not in approval_section


def test_wr_store_path_does_not_write_memory_or_pgvector() -> None:
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "weekly_review_conversation.py"
    service_text = service_path.read_text(encoding="utf-8")
    store_section = service_text.split("def store_approved_final_report", maxsplit=1)[1].split(
        "def reject_latest_draft_report",
        maxsplit=1,
    )[0]

    assert "ai_memories" not in store_section
    assert "pgvector" not in store_section.lower()
    assert "embedding" not in store_section.lower()
    assert "trigger_n8n" not in store_section
    assert "QwenClient" not in store_section


def test_wr_memory_projection_has_no_storage_or_vector_write_path() -> None:
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "weekly_review_conversation.py"
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py"
    service_text = service_path.read_text(encoding="utf-8")
    route_text = route_path.read_text(encoding="utf-8")
    projection_section = service_text.split("def get_weekly_review_memory_candidates", maxsplit=1)[1].split(
        "def approve_weekly_review_memory_candidate",
        maxsplit=1,
    )[0]

    assert "ai_memories" not in projection_section
    assert "pgvector" not in service_text.lower()
    assert "embedding" not in projection_section.lower()
    assert "db.add(" not in projection_section
    assert "db.commit" not in projection_section
    assert "trigger_n8n" not in projection_section
    assert "QwenClient" not in projection_section
    assert "/store-memory" not in route_text
    assert '@router.post("/weekly-review/{session_id}/memory' not in route_text


def test_wr_memory_commit_readiness_has_no_storage_or_vector_write_path() -> None:
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "weekly_review_conversation.py"
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py"
    service_text = service_path.read_text(encoding="utf-8")
    route_text = route_path.read_text(encoding="utf-8")
    commit_section = service_text.split("def get_weekly_review_memory_commit_ready_candidates", maxsplit=1)[1].split(
        "def commit_weekly_review_memory_candidates",
        maxsplit=1,
    )[0]

    assert "ai_memories" not in commit_section
    assert "pgvector" not in commit_section.lower()
    assert "embedding" not in commit_section.lower()
    assert "trigger_n8n" not in commit_section
    assert "QwenClient" not in commit_section
    assert "ImperiumMemoryCandidateDecision(" not in commit_section
    assert "AIResult(" not in commit_section
    assert "/store-memory" not in route_text
    assert "commit-dry-run" in route_text
    assert "commit-ready" in route_text


def test_wr_mission_history_read_has_no_ai_or_write_paths() -> None:
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "missions.py"
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py"
    service_text = service_path.read_text(encoding="utf-8")
    route_text = route_path.read_text(encoding="utf-8")
    history_section = service_text.split("def get_mission_history", maxsplit=1)[1].split(
        "def get_mission_decision_score",
        maxsplit=1,
    )[0]
    route_section = route_text.split('@router.get("/missions/history"', maxsplit=1)[1].split(
        '@router.get("/missions/recent"',
        maxsplit=1,
    )[0]

    assert "db.add(" not in history_section
    assert "db.flush" not in history_section
    assert "db.commit" not in history_section
    assert "pgvector" not in history_section.lower()
    assert "embedding" not in history_section.lower()
    assert "memory" not in history_section.lower()
    assert "calendar" not in history_section.lower()
    assert "n8n" not in history_section.lower()
    assert "ai agent" not in history_section.lower()
    assert "openai" not in history_section.lower()
    assert "anthropic" not in history_section.lower()
    assert "gemini" not in history_section.lower()
    assert "weighted_score" not in history_section
    assert "coefficient" not in history_section
    assert "Idempotency-Key" not in route_section


def test_patch_8i_mission_contract_docs_and_route_order_are_consolidated() -> None:
    contracts_text = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8")
    current_workflow_text = (DOCS_ROOT / "25_CURRENT_MISSION_WORKFLOW.md").read_text(encoding="utf-8")
    decision_framework_text = (DOCS_ROOT / "52_AI_DECISION_FRAMEWORK.md").read_text(encoding="utf-8")
    ai_tasks_text = (DOCS_ROOT / "31_AI_TASKS_AND_RESULTS_CONTRACT.md").read_text(encoding="utf-8")
    smoke_text = (DOCS_ROOT / "18_N8N_SMOKE_TEST.md").read_text(encoding="utf-8")
    route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py").read_text(encoding="utf-8")

    for endpoint in (
        "/api/imperium/missions/start",
        "/api/imperium/missions/backlog",
        "/api/imperium/missions/backlog/decision-preview",
        "/api/imperium/missions/backlog/{mission_id}/promote",
        "/api/imperium/missions/current",
        "/api/imperium/missions/active",
        "/api/imperium/missions/{mission_id}/complete",
        "/api/imperium/missions/{mission_id}/fail",
        "/api/imperium/missions/history",
        "/api/imperium/missions/recent",
        "/api/imperium/missions/{mission_id}",
        "/api/imperium/missions/{mission_id}/decision-score",
    ):
        assert f"`{endpoint}`" in contracts_text

    assert "/api/imperium/missions/{mission_id}/done" not in contracts_text
    assert "/api/imperium/missions/{mission_id}/not-done" not in contracts_text
    assert "`mission.abandoned`" in contracts_text
    assert "`backlog`, `active`, `completed`, `failed`, `abandoned`, or `cancelled`" in current_workflow_text
    assert "`mission.abandoned`" in current_workflow_text

    assert "| POST |" in contracts_text
    assert "| GET |" in contracts_text

    assert "CurrentUserDep" in contracts_text
    assert "Idempotency-Key" in contracts_text
    assert "no ai" in contracts_text.lower()
    assert "no n8n" in contracts_text.lower()
    assert "pgvector" in contracts_text.lower()
    assert "embedding" in contracts_text.lower()
    assert "memory" in contracts_text.lower()
    assert "calendar" in contracts_text.lower()

    lowered_decision_framework = " ".join(decision_framework_text.lower().split())
    assert "deterministic backend-only reads" in lowered_decision_framework
    assert "decision-preview" in lowered_decision_framework
    assert "decision-score" in lowered_decision_framework
    assert "do not expose `weighted_score`" in lowered_decision_framework
    assert "do not expose `domain_coefficient`" in lowered_decision_framework
    assert "reason_codes" in lowered_decision_framework
    assert "label" in lowered_decision_framework

    lowered_ai_tasks = ai_tasks_text.lower()
    assert "mission module 8a->8h does not create an ai task" in lowered_ai_tasks
    assert "ai_tasks" in lowered_ai_tasks
    assert "ai_results" in lowered_ai_tasks
    assert "n8n receives nothing" in lowered_ai_tasks

    lowered_smoke = smoke_text.lower()
    assert "routes mission" in lowered_smoke
    assert "must not trigger n8n" in lowered_smoke
    assert "n8n smoke tests must not depend on the mission routes" in lowered_smoke

    route_order = [
        route_text.index('@router.get("/missions/current"'),
        route_text.index('@router.get("/missions/active"'),
        route_text.index('@router.get("/missions/history"'),
        route_text.index('@router.get("/missions/recent"'),
        route_text.index('@router.get(\n    "/missions/{mission_id}"'),
        route_text.index('@router.get(\n    "/missions/{mission_id}/decision-score"'),
    ]
    assert route_order == sorted(route_order)


def test_contract_index_v1_is_static_metadata_only_and_not_dynamic_discovery() -> None:
    contracts_route_text = (
        BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_contracts.py"
    ).read_text(encoding="utf-8")
    contracts_service_text = (BACKEND_ROOT / "app" / "services" / "imperium" / "contracts.py").read_text(
        encoding="utf-8"
    )
    contracts_docs_text = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8").lower()
    lowered_route = contracts_route_text.lower()
    lowered_service = contracts_service_text.lower()

    assert '@router.get("/contracts/index"' in contracts_route_text
    assert "CurrentUserDep" in contracts_route_text
    assert "Idempotency-Key" not in contracts_route_text
    assert "contract_version=\"v1\"" in contracts_service_text
    assert "read_only=True" in contracts_service_text
    assert "db.add(" not in contracts_service_text
    assert "db.flush" not in contracts_service_text
    assert "db.commit" not in contracts_service_text
    assert "get_openapi" not in lowered_route
    assert "app.routes" not in lowered_route
    assert "for route in" not in lowered_route
    assert "health" not in lowered_service
    assert "internal" not in lowered_service

    for forbidden in ("n8n", "ocr", "scoring", "coaching", "recommendation", "openai", "gemini", "claude"):
        assert forbidden not in lowered_service

    assert "not a full openapi" in contracts_docs_text
    assert "not a health check" in contracts_docs_text
    assert "not a dynamic runtime discovery" in contracts_docs_text

def test_patch_11b_pulse_today_contract_docs_and_route_order_are_consolidated() -> None:
    contracts_text = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8")
    pulse_route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_pulse.py").read_text(
        encoding="utf-8"
    )
    pulse_service_text = (BACKEND_ROOT / "app" / "services" / "pulse" / "entries.py").read_text(encoding="utf-8")
    pulse_schema_text = (BACKEND_ROOT / "app" / "schemas" / "pulse.py").read_text(encoding="utf-8")
    combined = "\n".join([pulse_route_text, pulse_service_text, pulse_schema_text]).lower()

    assert "`/api/imperium/pulse/today`" in contracts_text
    assert "read-only" in contracts_text.lower()
    assert "entry: null" in contracts_text.lower()
    assert "no automatic entry creation" in contracts_text.lower()
    assert "no ai/n8n/scoring/coaching/calendar/memory/cross-module linkage" in contracts_text.lower()

    route_order = [
        pulse_route_text.index('@router.get("/today"'),
        pulse_route_text.index('@router.get("/entries/{entry_id}"'),
    ]
    assert route_order == sorted(route_order)

    today_route_section = pulse_route_text.split('@router.get("/today"', maxsplit=1)[1].split(
        '@router.post("/entries"',
        maxsplit=1,
    )[0]
    assert "Idempotency-Key" not in today_route_section

    for forbidden in (
        "qwenclient",
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
        "calendar",
        "replanning",
        "weighted_score",
        "coaching",
        "mission_id",
        "vault",
    ):
        assert forbidden not in combined


def test_patch_11c_pulse_stats_summary_is_read_only_deterministic_and_no_cross_module_linkage() -> None:
    contracts_text = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8")
    route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_pulse.py").read_text(encoding="utf-8")
    service_text = (BACKEND_ROOT / "app" / "services" / "pulse" / "entries.py").read_text(encoding="utf-8")
    schema_text = (BACKEND_ROOT / "app" / "schemas" / "pulse.py").read_text(encoding="utf-8")
    lowered_code = "\n".join([route_text, service_text, schema_text]).lower()
    lowered_docs = contracts_text.lower()
    summary_route = route_text.split('@router.get("/stats/summary"', maxsplit=1)[1].split(
        '@router.post("/entries"',
        maxsplit=1,
    )[0]
    summary_service = service_text.split("def get_pulse_stats_summary", maxsplit=1)[1].split(
        "def _get_existing_entry_for_date",
        maxsplit=1,
    )[0]

    route_order = [
        route_text.index('@router.get("/today"'),
        route_text.index('@router.get("/stats/summary"'),
        route_text.index('@router.post("/entries"'),
    ]
    assert route_order == sorted(route_order)
    assert "response_model=PulseStatsSummaryResponse" in route_text
    assert "current_user: CurrentUserDep" in summary_route
    assert "Idempotency-Key" not in summary_route
    assert "_validate_date_range" in summary_route
    assert "PulseStatsSummaryResponse" in schema_text
    assert "entry_count" in schema_text
    assert "average_sleep_hours" in schema_text
    assert "average_energy_level" in schema_text
    assert "average_fatigue_level" in schema_text
    assert "latest_weight_kg" in schema_text
    assert "workout_count" in schema_text
    assert "safe_explanation" in schema_text
    assert "Pulse summary statistics for current user." in service_text
    assert "Pulse summary statistics for current user." in schema_text
    assert "ImperiumPulseEntry.user_id == current_user.id" in summary_service
    assert "ImperiumPulseEntry.entry_date >= date_from" in summary_service
    assert "ImperiumPulseEntry.entry_date <= date_to" in summary_service
    assert "ImperiumPulseEntry.entry_date.desc()" in summary_service
    assert "ImperiumPulseEntry.created_at.desc()" in summary_service
    assert "ImperiumPulseEntry.id.asc()" in summary_service
    assert "entry.workout_done is True" in summary_service
    assert "entry.weight_kg is not None" in summary_service

    for read_only_section in (summary_route, summary_service):
        assert "db.add(" not in read_only_section
        assert "db.flush" not in read_only_section
        assert "db.commit" not in read_only_section

    for forbidden in (
        "qwenclient",
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
        "calendar",
        "replanning",
        "scoring",
        "weighted_score",
        "coaching",
        "recommendation",
        "mission_id",
        "vault",
    ):
        assert forbidden not in lowered_code

    assert "/api/imperium/pulse/stats/summary" in lowered_docs
    assert "pulse summary stats 11c" in lowered_docs
    assert "read-only" in lowered_docs
    assert "deterministic" in lowered_docs
    assert "no health score" in lowered_docs
    assert "no coaching" in lowered_docs
    assert "no recommendations" in lowered_docs
    assert "no cross-module linkage" in lowered_docs
    assert "no pgvector write" in lowered_docs
    assert "no embeddings" in lowered_docs
    assert "no automatic memory commit" in lowered_docs
    assert "no automatic replanning" in lowered_docs
    assert "no automatic scoring" in lowered_docs


def test_patch_11d_pulse_contract_consolidation_is_documented_and_locked_down() -> None:
    contracts_text = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8")
    schema_text = (DOCS_ROOT / "05_DATABASE_SCHEMA.md").read_text(encoding="utf-8")
    route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_pulse.py").read_text(
        encoding="utf-8"
    )
    service_text = (BACKEND_ROOT / "app" / "services" / "pulse" / "entries.py").read_text(encoding="utf-8")
    lowered_route_and_service = "\n".join([route_text, service_text]).lower()
    lowered_docs = "\n".join([contracts_text, schema_text]).lower()

    for endpoint in (
        "/api/imperium/pulse/entries",
        "/api/imperium/pulse/entries/{entry_id}",
        "/api/imperium/pulse/today",
        "/api/imperium/pulse/stats/summary",
    ):
        assert endpoint in contracts_text

    assert "| POST | `/api/imperium/pulse/entries`" in contracts_text
    assert "| GET | `/api/imperium/pulse/entries`" in contracts_text
    assert "| GET | `/api/imperium/pulse/entries/{entry_id}`" in contracts_text
    assert "| GET | `/api/imperium/pulse/today`" in contracts_text
    assert "| GET | `/api/imperium/pulse/stats/summary`" in contracts_text
    assert "CurrentUserDep" in contracts_text
    assert "Idempotency-Key" in contracts_text
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

    route_order = [
        route_text.index('@router.get("/today"'),
        route_text.index('@router.get("/stats/summary"'),
        route_text.index('@router.post("/entries"'),
        route_text.index('@router.get("/entries"'),
        route_text.index('@router.get("/entries/{entry_id}"'),
    ]
    assert route_order == sorted(route_order)

    post_route_section = route_text.split('@router.post("/entries"', maxsplit=1)[1].split(
        '@router.get("/entries"',
        maxsplit=1,
    )[0]
    get_section = route_text.split('@router.get("/entries"', maxsplit=1)[1]
    assert "Idempotency-Key" in post_route_section
    assert "CurrentUserDep" in post_route_section
    assert "db.add(" in lowered_route_and_service
    assert "db.flush" in lowered_route_and_service
    assert "db.commit" in lowered_route_and_service
    assert "db.add(" not in get_section
    assert "db.flush" not in get_section
    assert "db.commit" not in get_section

    for forbidden in (
        "openai",
        "anthropic",
        "gemini",
        "claude",
        "qwenclient",
        "n8n",
        "trigger_n8n",
        "n8n agent",
        "ai agent",
        "aiagent",
        "pgvector",
        "embedding",
        "memory commit",
        "calendar replanning",
        "scoring",
        "coaching",
        "recommendations",
        "mission_id",
        "vault",
        "path linkage",
    ):
        assert forbidden not in lowered_route_and_service


def test_patch_11f_pulse_docs_mark_future_surfaces_outside_v1_contract() -> None:
    contracts_text = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8")
    schema_text = (DOCS_ROOT / "05_DATABASE_SCHEMA.md").read_text(encoding="utf-8")
    lowered_docs = "\n".join([contracts_text, schema_text]).lower()

    active_contract = contracts_text.split("#### Pulse Foundation 11A", maxsplit=1)[1].split(
        "#### Future Pulse surfaces - FUTURE / NOT IMPLEMENTED",
        maxsplit=1,
    )[0]
    future_contract = contracts_text.split(
        "#### Future Pulse surfaces - FUTURE / NOT IMPLEMENTED",
        maxsplit=1,
    )[1].split("### The Path", maxsplit=1)[0]
    active_schema = schema_text.split("### Pulse Foundation 11A", maxsplit=1)[1].split(
        "### FUTURE / NOT IMPLEMENTED",
        maxsplit=1,
    )[0]

    implemented_endpoints = (
        "POST | `/api/imperium/pulse/entries`",
        "GET | `/api/imperium/pulse/entries`",
        "GET | `/api/imperium/pulse/entries/{entry_id}`",
        "GET | `/api/imperium/pulse/today`",
        "GET | `/api/imperium/pulse/stats/summary`",
    )
    for endpoint in implemented_endpoints:
        assert endpoint in contracts_text

    future_endpoints = (
        "/api/pulse/dashboard",
        "/api/pulse/workout/generate",
        "/api/pulse/workout/adapt",
        "/api/pulse/wearable/sync",
    )
    for endpoint in future_endpoints:
        assert endpoint not in active_contract
        future_lines = [line for line in future_contract.splitlines() if endpoint in line]
        assert future_lines
        assert all("FUTURE / NOT IMPLEMENTED" in line for line in future_lines)

    future_tables = (
        "pulse_biological_profiles",
        "pulse_health_scores",
        "pulse_workouts",
        "pulse_recommendations",
    )
    for table in future_tables:
        assert table not in active_schema
        assert f"future / not implemented in pulse v1 11a->11d: `{table}`" in lowered_docs

    assert "pulse v1 11a->11d active backend surface is only" in lowered_docs
    assert "pulse v1 11a->11d implemented schema surface is only `imperium_pulse_entries`" in lowered_docs
    assert "health score table" in lowered_docs
    assert "workout generation" in lowered_docs
    assert "wearable sync tables" in lowered_docs
    assert "no automatic scoring/coaching/recommendations" in lowered_docs


def test_patch_12a_imperium_dashboard_foundation_is_read_only_and_route_order_safe() -> None:
    contracts_text = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8")
    api_router_text = (BACKEND_ROOT / "app" / "api" / "v1" / "router.py").read_text(encoding="utf-8")
    dashboard_route_text = (
        BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_dashboard.py"
    ).read_text(encoding="utf-8")
    legacy_route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py").read_text(
        encoding="utf-8"
    )
    dashboard_service_text = (BACKEND_ROOT / "app" / "services" / "imperium" / "dashboard.py").read_text(
        encoding="utf-8"
    )
    dashboard_schema_text = (BACKEND_ROOT / "app" / "schemas" / "dashboard.py").read_text(encoding="utf-8")
    foundation_service = dashboard_service_text.split("def get_imperium_dashboard_foundation", maxsplit=1)[1].split(
        "def get_dashboard_snapshot",
        maxsplit=1,
    )[0]
    lowered_foundation_code = "\n".join([dashboard_route_text, foundation_service, dashboard_schema_text]).lower()
    lowered_docs = contracts_text.lower()

    assert "`/api/imperium/dashboard`" in contracts_text
    assert "imperium dashboard foundation 12b" in lowered_docs or "imperium dashboard foundation 12a" in lowered_docs
    assert "active mission" in lowered_docs
    assert "vault summary" in lowered_docs
    assert "path today" in lowered_docs
    assert "pulse today" in lowered_docs
    assert "no `idempotency-key` required" in lowered_docs
    assert "snapshot read-only" in lowered_docs
    assert "not the ai brain" in lowered_docs
    assert "no n8n ai agent" in lowered_docs
    assert "no n8n db write" in lowered_docs
    assert "no automatic memory commit" in lowered_docs
    assert "no automatic path check-in creation" in lowered_docs
    assert "no automatic pulse entry creation" in lowered_docs
    assert "no automatic creation of path/pulse rows" in lowered_docs
    assert "no mission/vault/path/pulse mutation" in lowered_docs
    assert "no cross-module write" in lowered_docs
    assert "no cross-module writes" in lowered_docs
    assert "readiness snapshot" in lowered_docs
    assert "readiness is not a score" in lowered_docs
    assert "readiness is not a recommendation" in lowered_docs
    assert "readiness is not a health score" in lowered_docs

    assert "imperium_dashboard" in api_router_text
    assert api_router_text.index("imperium_dashboard.router") < api_router_text.index("imperium.router")
    assert '@router.get("/dashboard"' in dashboard_route_text
    assert '@router.get("/dashboard"' not in legacy_route_text
    assert "response_model=ImperiumDashboardFoundationResponse" in dashboard_route_text
    assert "CurrentUserDep" in dashboard_route_text
    assert "SessionDep" in dashboard_route_text
    assert "Query(min_length=3, max_length=3, pattern=r\"^[A-Za-z]{3}$\")" in dashboard_route_text
    assert "Idempotency-Key" not in dashboard_route_text

    assert "get_current_active_mission" in foundation_service
    assert "get_vault_summary" in foundation_service
    assert "get_path_today_view" in foundation_service
    assert "get_pulse_today_entry" in foundation_service
    assert "currency.strip().upper()" in foundation_service
    assert "occurred_from=None" in foundation_service
    assert "occurred_to=None" in foundation_service
    assert "active_mission" in dashboard_schema_text
    assert "mission_available" in dashboard_schema_text
    assert "vault_transaction_count" in dashboard_schema_text
    assert "Dashboard readiness snapshot computed from read-only module data." in dashboard_schema_text
    assert "Dashboard metadata for current snapshot." in dashboard_schema_text
    assert "user_id" not in dashboard_schema_text

    for read_only_section in (dashboard_route_text, foundation_service):
        assert "db.add(" not in read_only_section
        assert "db.flush" not in read_only_section
        assert "db.commit" not in read_only_section

    for forbidden in (
        "qwenclient",
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
        "calendar",
        "replanning",
        "ocr",
        "health_score",
        "weighted_score",
        "coaching",
        "recommendation",
        "analytics",
        "telemetry",
        "tracking",
        "health score",
        "advice",
    ):
        assert forbidden not in lowered_foundation_code


def test_patch_12b_imperium_dashboard_contracts_and_invariants_are_consolidated() -> None:
    contracts_text = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8")
    schema_text = (DOCS_ROOT / "05_DATABASE_SCHEMA.md").read_text(encoding="utf-8")
    dashboard_route_text = (
        BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_dashboard.py"
    ).read_text(encoding="utf-8")
    dashboard_service_text = (BACKEND_ROOT / "app" / "services" / "imperium" / "dashboard.py").read_text(
        encoding="utf-8"
    )
    dashboard_schema_text = (BACKEND_ROOT / "app" / "schemas" / "dashboard.py").read_text(encoding="utf-8")
    snapshot_schema_text = (BACKEND_ROOT / "app" / "schemas" / "imperium.py").read_text(encoding="utf-8")
    snapshot_service = dashboard_service_text.split("def get_dashboard_snapshot", maxsplit=1)[1]
    lowered_service = dashboard_service_text.lower()
    lowered_docs = contracts_text.lower() + "\n" + schema_text.lower()

    assert "imperium dashboard foundation 12b" in lowered_docs
    assert "snapshot read-only" in lowered_docs
    assert "responses are public-safe for the current authenticated user only" in lowered_docs
    assert "no auto-creation of path rows" in lowered_docs
    assert "no auto-creation of pulse rows" in lowered_docs
    assert "readiness is not a score" in lowered_docs
    assert "readiness is not a recommendation" in lowered_docs
    assert "readiness is not a health score" in lowered_docs
    assert "GET /api/imperium/dashboard" in contracts_text
    assert "currentuserdep" in lowered_docs
    assert "idempotency-key" in lowered_docs
    assert "query params:" in lowered_docs
    assert "date` optional `date`" in lowered_docs
    assert "currency` optional string" in lowered_docs
    assert "readiness`" in lowered_docs
    assert "safe_explanation" in contracts_text
    assert "readiness: ImperiumDashboardReadinessSection" in snapshot_schema_text
    assert "Dashboard readiness snapshot computed from read-only module data." in dashboard_schema_text
    assert "Dashboard metadata for current snapshot." in dashboard_schema_text
    assert "snapshot_generated_at" in dashboard_schema_text
    assert "dashboard_version" in dashboard_schema_text
    assert "included_modules" in dashboard_schema_text
    assert "read_only" in dashboard_schema_text

    for forbidden in (
        "db.add(",
        "db.flush",
        "db.commit",
        "qwenclient",
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
        "calendar",
        "ocr",
        "health_score",
        "weighted_score",
        "coaching",
        "recommendation",
        "analytics",
        "telemetry",
        "tracking",
        "health score",
        "advice",
        "path check-in creation",
        "pulse entry creation",
        "automatic creation of path/pulse rows",
        "cross-module write",
    ):
        assert forbidden not in lowered_service

    assert "get_current_active_mission" in dashboard_service_text
    assert "get_vault_summary" in dashboard_service_text
    assert "get_path_today_view" in dashboard_service_text
    assert "get_pulse_today_entry" in dashboard_service_text
    assert "get_dashboard_snapshot" in dashboard_service_text
    assert "return ImperiumDashboardFoundationResponse" in dashboard_service_text
    assert "readiness=ImperiumDashboardReadinessSection" in dashboard_service_text
    assert "readiness=ImperiumDashboardReadinessSection" in snapshot_service
    assert "Query(min_length=3, max_length=3, pattern=r\"^[A-Za-z]{3}$\")" in dashboard_route_text
    assert "CurrentUserDep" in dashboard_route_text
    assert "Idempotency-Key" not in dashboard_route_text


def test_wr_memory_candidate_decision_migration_and_model_are_scoped() -> None:
    migration_path = BACKEND_ROOT / "alembic" / "versions" / "20260501_0015_memory_candidate_decisions.py"
    model_path = BACKEND_ROOT / "app" / "models" / "imperium.py"
    migration_text = migration_path.read_text(encoding="utf-8")
    model_text = model_path.read_text(encoding="utf-8")

    assert 'revision: str = "20260501_0015"' in migration_text
    assert 'down_revision: str | None = "20260430_0014"' in migration_text
    assert "imperium_memory_candidate_decisions" in migration_text
    assert "uq_mem_candidate_decision_user_report_candidate" in migration_text
    assert "decision IN ('approved', 'rejected', 'edited')" in migration_text
    assert "source IN ('weekly_review')" in migration_text
    assert "pgvector" not in migration_text.lower()
    assert "ai_memories" not in migration_text
    assert "class ImperiumMemoryCandidateDecision" in model_text


def test_ai_memories_commit_has_no_vector_embedding_or_n8n_path() -> None:
    migration_path = BACKEND_ROOT / "alembic" / "versions" / "20260502_0017_ai_memories_foundation.py"
    model_path = BACKEND_ROOT / "app" / "models" / "ai.py"
    service_path = BACKEND_ROOT / "app" / "services" / "ai" / "memories.py"
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py"
    migration_text = migration_path.read_text(encoding="utf-8")
    model_text = model_path.read_text(encoding="utf-8")
    service_text = service_path.read_text(encoding="utf-8")
    route_text = route_path.read_text(encoding="utf-8")

    assert 'revision: str = "20260502_0017"' in migration_text
    assert 'down_revision: str | None = "20260501_0016"' in migration_text
    assert "ai_memories" in migration_text
    assert "uq_ai_memories_source_decision" in migration_text
    assert "source_decision_id IS NOT NULL" in migration_text
    assert "confidence >= 0 AND confidence <= 1" in migration_text
    assert "pgvector" not in migration_text.lower()
    assert "embedding" not in migration_text.lower()
    assert "class AIMemory" in model_text
    assert "metadata_json" in model_text
    assert "mapped_column(\"metadata\"" in model_text
    assert "trigger_n8n" not in service_text
    assert "QwenClient" not in service_text
    assert "pgvector" not in service_text.lower().replace("pgvector_enabled", "")
    assert "embedding" not in service_text.lower().replace("embeddings_enabled", "")
    assert '@router.get("/memories/schema"' in route_text
    assert '@router.get("/memories"' in route_text
    assert '@router.get("/memories/{memory_id}"' in route_text
    assert 'post("/weekly-review/memory-candidates/commit"' in route_text.lower()
    assert 'post("/memories/{memory_id}/archive"' in route_text.lower()
    assert 'post("/memories/{memory_id}/supersede"' in route_text.lower()
    assert 'post("/weekly-review/memory-candidates/commit-dry-run"' in route_text.lower()
    assert "trigger_n8n" not in service_text
    assert "QwenClient" not in service_text


def test_wr_final_report_candidate_migration_uses_partial_active_unique_indexes() -> None:
    migration_path = BACKEND_ROOT / "alembic" / "versions" / "20260430_0014_wr_final_report_candidate_history.py"
    migration_text = migration_path.read_text(encoding="utf-8")

    assert "imperium_weekly_review_final_reports_session_unique" in migration_text
    assert "imperium_weekly_review_final_reports_user_week_unique" in migration_text
    assert "uq_wr_final_reports_active_session" in migration_text
    assert "uq_wr_final_reports_active_user_week" in migration_text
    assert "status IN ('draft', 'approved', 'stored')" in migration_text
    assert "postgresql_where=sa.text(ACTIVE_STATUS_SQL)" in migration_text


def test_n8n_client_has_no_unsigned_production_mode() -> None:
    client_path = BACKEND_ROOT / "app" / "services" / "integrations" / "n8n_client.py"
    client_text = client_path.read_text(encoding="utf-8")

    assert "N8N_WEBHOOK_SECRET is not configured." in client_text
    assert "X-Signature" in client_text
    assert "X-Timestamp" in client_text
    assert "if secret:" not in client_text


def test_wr_conversation_schema_uses_slim_ai_result_summary() -> None:
    schema_path = BACKEND_ROOT / "app" / "schemas" / "weekly_review.py"
    schema_text = schema_path.read_text(encoding="utf-8")
    conversation_section = schema_text.split("class WeeklyReviewConversationRead", maxsplit=1)[1].split(
        "class WeeklyReviewCurrentResponse",
        maxsplit=1,
    )[0]
    debug_section = schema_text.split("class WeeklyReviewDebugStatusRead", maxsplit=1)[1].split(
        "def week_end_for",
        maxsplit=1,
    )[0]
    debug_summary_section = schema_text.split("class WeeklyReviewAIResultDebugSummary", maxsplit=1)[1].split(
        "class WeeklyReviewDebugStatusRead",
        maxsplit=1,
    )[0]
    summary_section = schema_text.split("class WeeklyReviewAIResultSummary", maxsplit=1)[1].split(
        "class WeeklyReviewConversationRead",
        maxsplit=1,
    )[0]

    assert "AIResultRead" not in conversation_section
    assert "WeeklyReviewAIResultSummary" in conversation_section
    assert "AIResultRead" not in debug_section
    assert "raw_payload:" not in debug_section
    assert "raw_payload:" not in debug_summary_section
    assert "raw_payload_keys" in debug_summary_section
    assert "raw_payload" not in summary_section


def test_wr_finalization_read_export_does_not_use_ai_result_read_or_expose_raw_payload() -> None:
    schema_path = BACKEND_ROOT / "app" / "schemas" / "weekly_review.py"
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "weekly_review_conversation.py"
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py"
    schema_text = schema_path.read_text(encoding="utf-8")
    service_text = service_path.read_text(encoding="utf-8")
    route_text = route_path.read_text(encoding="utf-8")
    finalization_schema_section = schema_text.split("class WeeklyReviewFinalReportSummary", maxsplit=1)[1].split(
        "class WeeklyReviewConversationFlags",
        maxsplit=1,
    )[0]
    finalization_service_section = service_text.split("def get_weekly_review_history", maxsplit=1)[1].split(
        "def get_weekly_review_debug_status",
        maxsplit=1,
    )[0]
    finalization_route_section = route_text.split('@router.get("/weekly-review/history"', maxsplit=1)[1].split(
        '@router.get("/weekly-review/{session_id}/messages"',
        maxsplit=1,
    )[0]

    assert "AIResultRead" not in finalization_schema_section
    assert "AIResultRead" not in finalization_service_section
    assert "AIResultRead" not in finalization_route_section
    assert "raw_payload:" not in finalization_schema_section
    assert "raw_payload_keys" not in finalization_schema_section
    assert "raw_payload_keys" not in finalization_service_section
    assert "_final_report_read" in finalization_service_section
    assert "_markdown_from_final_report" in finalization_service_section


# ---- Audit Patch 1 additions ----------------------------------------------


def test_mock_ai_summary_route_has_environment_guard() -> None:
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "internal.py"
    route_text = route_path.read_text(encoding="utf-8")
    assert 'settings.environment not in {"local", "test"}' in route_text


def test_commit_memory_candidates_uses_sql_user_id_filter() -> None:
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "weekly_review_conversation.py"
    service_text = service_path.read_text(encoding="utf-8")
    # Slice the body of commit_weekly_review_memory_candidates from its def to
    # the next top-level def.
    after_def = service_text.split("def commit_weekly_review_memory_candidates", maxsplit=1)[1]
    function_body = after_def.split("\ndef ", maxsplit=1)[0]
    assert "ImperiumMemoryCandidateDecision.user_id == current_user.id" in function_body
    assert '"foreign"' not in function_body


def test_ai_ownership_not_null_migration_has_safe_backfill_and_constraints() -> None:
    migration_path = BACKEND_ROOT / "alembic" / "versions" / "20260503_0018_ai_user_id_not_null.py"
    migration_text = migration_path.read_text(encoding="utf-8")

    assert "current_setting('imperium.canonical_user_id', true)" in migration_text
    assert "user_count = 1" in migration_text
    assert "set imperium.canonical_user_id" in migration_text
    assert 'op.alter_column("ai_tasks", "user_id", nullable=False)' in migration_text
    assert 'op.alter_column("ai_results", "user_id", nullable=False)' in migration_text
    assert 'op.alter_column("ai_result_validations", "user_id", nullable=False)' in migration_text


def test_public_ai_result_read_schema_does_not_expose_raw_payload() -> None:
    schema_path = BACKEND_ROOT / "app" / "schemas" / "ai.py"
    schema_text = schema_path.read_text(encoding="utf-8")
    public_section = schema_text.split("class AIResultRead", maxsplit=1)[1].split("\n\nclass ", maxsplit=1)[0]
    internal_section = schema_text.split("class AIResultInternalRead", maxsplit=1)[1].split("\n\nclass ", maxsplit=1)[0]

    assert "raw_payload" not in public_section
    assert "raw_payload" in internal_section


def test_public_weekly_review_message_schema_is_user_only() -> None:
    schema_path = BACKEND_ROOT / "app" / "schemas" / "weekly_review.py"
    schema_text = schema_path.read_text(encoding="utf-8")
    public_section = schema_text.split("class WeeklyReviewMessageCreate", maxsplit=1)[1].split(
        "\n\nclass WeeklyReviewMessageCreateInternal",
        maxsplit=1,
    )[0]
    internal_section = schema_text.split("class WeeklyReviewMessageCreateInternal", maxsplit=1)[1].split(
        "\n\nclass ",
        maxsplit=1,
    )[0]

    assert 'role: Literal["user"]' in public_section
    assert 'message_type: Literal["user_answer", "chat_message", "revision_request"]' in public_section
    for forbidden in ("qwen", "system", "opus", "initial_summary", "assistant_followup", "final_report_draft"):
        assert forbidden not in public_section
    assert "qwen" in internal_section
    assert "backend" in internal_section


def test_debug_status_route_sanitizes_non_local_diagnostics() -> None:
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py"
    route_text = route_path.read_text(encoding="utf-8")
    route_section = route_text.split('"/weekly-review/{session_id}/debug-status"', maxsplit=1)[1].split(
        '@router.post(\n    "/weekly-review/{session_id}/chat/messages"',
        maxsplit=1,
    )[0]
    sanitize_section = route_text.split("def _sanitize_weekly_review_debug_status", maxsplit=1)[1].split(
        '@router.post(\n    "/weekly-review/{session_id}/chat/messages"',
        maxsplit=1,
    )[0]

    assert 'get_settings().environment not in {"local", "test"}' in route_section
    assert "_sanitize_weekly_review_debug_status" in route_section
    assert "raw_payload_keys = []" in sanitize_section
    assert "provider = None" in sanitize_section
    assert "model_used = None" in sanitize_section
    assert "result_payload = {}" in sanitize_section
    assert "error_message = None" in sanitize_section


def test_decision_framework_foundation_has_no_ai_n8n_or_vector_boundary_crossing() -> None:
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "decision_framework.py"
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py"
    schema_path = BACKEND_ROOT / "app" / "schemas" / "imperium.py"
    migration_path = BACKEND_ROOT / "alembic" / "versions" / "20260504_0019_decision_framework_foundation.py"
    service_text = service_path.read_text(encoding="utf-8")
    route_text = route_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    migration_text = migration_path.read_text(encoding="utf-8")
    lowered_service = service_text.lower()
    lowered_route = route_text.lower()
    lowered_migration = migration_text.lower()
    public_explanation_schema = schema_text.split("class DecisionFrameworkScoreExplanation", maxsplit=1)[1].split(
        "class DecisionFrameworkScoreBreakdownItem",
        maxsplit=1,
    )[0]
    public_preview_schema = schema_text.split("class DecisionFrameworkScorePreviewResponse", maxsplit=1)[1].split(
        "class PathItemStatus",
        maxsplit=1,
    )[0]

    assert 'revision: str = "20260504_0019"' in migration_text
    assert 'down_revision: str | None = "20260503_0018"' in migration_text
    assert "imperium_user_priorities" in migration_text
    assert "imperium_mission_scores" in migration_text
    assert "position = 1 AND coefficient = 10" in migration_text
    assert "imperium_user_priorities_active_domain_unique_idx" in migration_text
    assert "imperium_user_priorities_active_position_unique_idx" in migration_text
    assert "QwenClient" not in service_text
    assert "providers" not in service_text
    assert "n8n_client" not in service_text
    assert "trigger_n8n" not in service_text
    assert "ai_memories" not in service_text
    assert "db.add(ImperiumMissionScore" not in service_text
    assert "db.add_all([ImperiumMissionScore" not in service_text
    assert "pgvector" not in lowered_service
    assert "embedding =" not in lowered_service
    assert "embedding:" not in lowered_service
    assert "vector =" not in lowered_service
    assert "score-preview" in route_text
    assert "decision-framework" in route_text
    assert "n8n_client" not in lowered_route
    assert "qwenclient" not in lowered_route
    assert "pgvector" not in lowered_migration
    assert "embedding" not in lowered_migration
    assert "mission_type_points" in public_explanation_schema
    assert "recurrence_points" in public_explanation_schema
    assert "effort_points" not in public_explanation_schema
    assert "alignment_points" not in public_explanation_schema
    assert "domain_coefficient" not in public_explanation_schema
    assert "final_weighted_score" not in public_explanation_schema
    assert "priority_bucket" in public_preview_schema
    assert "domain_coefficient" not in public_preview_schema
    assert "weighted_score" not in public_preview_schema
    assert "position_to_coefficient" not in service_text


def test_patch_7f2_mission_score_storage_keeps_public_boundary_private() -> None:
    model_path = BACKEND_ROOT / "app" / "models" / "imperium.py"
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "missions.py"
    schema_path = BACKEND_ROOT / "app" / "schemas" / "imperium.py"
    migration_path = BACKEND_ROOT / "alembic" / "versions" / "20260511_0020_imperium_missions_decision_fields.py"
    unique_migration_path = BACKEND_ROOT / "alembic" / "versions" / "20260511_0021_imperium_mission_scores_unique_source.py"
    model_text = model_path.read_text(encoding="utf-8")
    service_text = service_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    migration_text = migration_path.read_text(encoding="utf-8")
    unique_migration_text = unique_migration_path.read_text(encoding="utf-8")
    mission_section = model_text.split("class ImperiumMission", maxsplit=1)[1].split(
        "class ImperiumPriorityRule",
        maxsplit=1,
    )[0]
    start_schema_section = schema_text.split("class StartMissionRequest", maxsplit=1)[1].split(
        "class CompleteMissionRequest",
        maxsplit=1,
    )[0]
    write_response_section = schema_text.split("class MissionWriteResponse", maxsplit=1)[1].split(
        "class PriorityRuleInput",
        maxsplit=1,
    )[0]
    score_read_section = schema_text.split("class MissionDecisionScoreRead", maxsplit=1)[1].split(
        "class PathItemStatus",
        maxsplit=1,
    )[0]

    assert 'revision: str = "20260511_0020"' in migration_text
    assert 'down_revision: str | None = "20260504_0019"' in migration_text
    assert 'op.add_column("imperium_missions", sa.Column("domain"' in migration_text
    assert "priority_level IS NULL OR (priority_level >= 1 AND priority_level <= 10)" in migration_text
    assert "status IN ('backlog', 'active', 'completed', 'failed', 'cancelled')" in migration_text
    assert "imperium_missions_user_backlog_priority_created_idx" in migration_text
    assert "domain: Mapped[str | None]" in mission_section
    assert "priority_level: Mapped[int | None]" in mission_section
    assert "mission_type_category: Mapped[str | None]" in mission_section
    assert "embedding" not in mission_section.lower()
    assert "vector" not in mission_section.lower()
    assert 'revision: str = "20260511_0021"' in unique_migration_text
    assert 'down_revision: str | None = "20260511_0020"' in unique_migration_text
    assert "imperium_mission_scores_user_mission_source_unique_idx" in unique_migration_text
    assert "domain: str | None" in start_schema_section
    assert "priority_level: int | None" in start_schema_section
    assert "mission_type_category: str | None" in start_schema_section
    assert "deadline_at: datetime | None" in start_schema_section
    assert "mission_type: int | str | None" in start_schema_section
    assert "recurrence: int | str | None" in start_schema_section
    assert "ImperiumMissionScore" in service_text
    assert "build_mission_score_from_start_request" in service_text
    assert "db.add(score)" in service_text
    assert "domain_coefficient" not in write_response_section
    assert "weighted_score" not in write_response_section
    assert "final_weighted_score" not in write_response_section
    assert "domain_coefficient" not in score_read_section
    assert "weighted_score" not in score_read_section
    assert "final_weighted_score" not in score_read_section
    assert "pgvector" not in service_text.lower()
    assert "embedding =" not in service_text.lower()
    assert "embedding:" not in service_text.lower()
    assert "trigger_n8n" not in service_text


def test_patch_7g_priority_reconciliation_uses_decision_framework_as_canonical_source() -> None:
    dashboard_path = BACKEND_ROOT / "app" / "services" / "imperium" / "dashboard.py"
    daily_plans_path = BACKEND_ROOT / "app" / "services" / "imperium" / "daily_plans.py"
    decision_framework_path = BACKEND_ROOT / "app" / "services" / "imperium" / "decision_framework.py"
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py"
    dashboard_text = dashboard_path.read_text(encoding="utf-8")
    daily_plans_text = daily_plans_path.read_text(encoding="utf-8")
    decision_framework_text = decision_framework_path.read_text(encoding="utf-8")
    route_text = route_path.read_text(encoding="utf-8")

    assert "ImperiumPriorityRule" not in dashboard_text
    assert "imperium_priority_rules" not in dashboard_text
    assert "get_canonical_priority_order" in dashboard_text

    assert "ImperiumPriorityRule" not in daily_plans_text
    assert "imperium_priority_rules" not in daily_plans_text
    assert "priority_rule_ids" not in daily_plans_text
    assert "get_canonical_priority_order" in daily_plans_text
    assert '"priority_source": "decision_framework"' in daily_plans_text

    assert "def get_canonical_priority_order" in decision_framework_text
    assert "ImperiumUserPriority" in decision_framework_text
    assert "imperium_user_priorities" in decision_framework_text

    legacy_get_section = route_text.split('@router.get("/priorities"', maxsplit=1)[1].split(
        '@router.post("/priorities"',
        maxsplit=1,
    )[0]
    legacy_post_section = route_text.split('@router.post("/priorities"', maxsplit=1)[1].split(
        '@router.get("/weekly-review/state"',
        maxsplit=1,
    )[0]

    assert "get_canonical_priority_order" in legacy_get_section
    assert "get_active_priority_rules" not in legacy_get_section
    assert "legacy_superseded" in legacy_get_section
    assert "imperium_user_priorities" in legacy_get_section
    assert "HTTP_410_GONE" in legacy_post_section
    assert "replace_priority_rules" not in legacy_post_section


def test_patch_7h_calendar_foundation_stays_minimal_and_backend_owned() -> None:
    migration_path = BACKEND_ROOT / "alembic" / "versions" / "20260512_0022_imperium_calendar_events_foundation.py"
    model_path = BACKEND_ROOT / "app" / "models" / "imperium.py"
    schema_path = BACKEND_ROOT / "app" / "schemas" / "imperium.py"
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "calendar.py"
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py"
    migration_text = migration_path.read_text(encoding="utf-8")
    model_text = model_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    service_text = service_path.read_text(encoding="utf-8")
    route_text = route_path.read_text(encoding="utf-8")
    model_section = model_text.split("class ImperiumCalendarEvent", maxsplit=1)[1].split(
        "class ImperiumMissionScore",
        maxsplit=1,
    )[0]
    schema_section = schema_text.split("class CalendarEventCreate", maxsplit=1)[1].split(
        "class DecisionFrameworkSchemaResponse",
        maxsplit=1,
    )[0]
    lowered_combined = "\n".join([migration_text, model_section, schema_section, service_text]).lower()

    assert 'revision: str = "20260512_0022"' in migration_text
    assert 'down_revision: str | None = "20260511_0021"' in migration_text
    assert "imperium_calendar_events" in migration_text
    assert "event_type IN ('event', 'deadline', 'vacation')" in migration_text
    assert "ends_at IS NULL OR ends_at >= starts_at" in migration_text
    assert "imperium_calendar_events_user_starts_at_idx" in migration_text
    assert "imperium_calendar_events_user_event_type_idx" in migration_text
    assert "class ImperiumCalendarEvent" in model_text
    assert "CalendarEventCreate" in schema_section
    assert "CalendarEventRead" in schema_section
    assert "extra=\"forbid\"" in schema_section
    assert "Idempotency-Key" in route_text
    assert '"/calendar/events"' in route_text
    assert "response_model=CalendarEventRead" in route_text
    assert 'get("/calendar/events"' in route_text.lower()
    assert 'delete("/calendar/events/{event_id}"' in route_text.lower()

    for forbidden in (
        "recurrence",
        "rrule",
        "repeat",
        "google",
        "apple",
        "sync_token",
        "notification",
        "reminder",
        "ai_metadata",
        "ai_schedule",
        "embedding",
        "pgvector",
    ):
        assert forbidden not in lowered_combined
        assert forbidden not in model_section.lower()

    assert "QwenClient" not in service_text
    assert "providers" not in service_text
    assert "n8n_client" not in service_text
    assert "trigger_n8n" not in service_text


def test_patch_9a_vault_ledger_routes_have_no_ai_n8n_or_memory_side_effects() -> None:
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_vault.py"
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "vault_transactions.py"
    schema_path = BACKEND_ROOT / "app" / "schemas" / "vault.py"
    migration_path = BACKEND_ROOT / "alembic" / "versions" / "20260525_0024_imperium_vault_ledger_foundation.py"
    route_text = route_path.read_text(encoding="utf-8")
    service_text = service_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    migration_text = migration_path.read_text(encoding="utf-8")
    create_schema_section = schema_text.split("class ImperiumVaultTransactionCreate", maxsplit=1)[1].split(
        "class ImperiumVaultTransactionRead",
        maxsplit=1,
    )[0]
    list_service_section = service_text.split("def list_vault_transactions", maxsplit=1)[1].split(
        "def _get_existing_idempotency",
        maxsplit=1,
    )[0]
    get_route_section = route_text.split('@router.get("/transactions"', maxsplit=1)[1].split(
        '@router.get("/transactions/{transaction_id}"',
        maxsplit=1,
    )[0]
    combined = "\n".join([route_text, service_text, create_schema_section, migration_text])
    lowered = combined.lower()

    assert 'revision: str = "20260525_0024"' in migration_text
    assert 'down_revision: str | None = "20260525_0023"' in migration_text
    assert "imperium_vault_transactions" in migration_text
    assert "amount_cents > 0" in migration_text
    assert "transaction_type IN ('income', 'expense')" in migration_text
    assert "extra=\"forbid\"" in create_schema_section
    assert "user_id" not in create_schema_section
    assert "Idempotency-Key" in route_text
    assert "Idempotency-Key" not in get_route_section
    assert "db.add(" not in list_service_section
    assert "db.flush" not in list_service_section
    assert "db.commit" not in list_service_section

    assert "QwenClient" not in combined
    assert "providers" not in combined
    assert "openai" not in lowered
    assert "anthropic" not in lowered
    assert "gemini" not in lowered
    assert "claude" not in lowered
    assert "n8n_client" not in combined
    assert "trigger_n8n" not in combined
    assert "ai agent" not in lowered
    assert "aiagent" not in lowered
    assert "n8n-nodes-langchain.agent" not in lowered
    assert "pgvector" not in lowered
    assert "embedding" not in lowered
    assert "ai_memories" not in combined
    assert "memory commit" not in lowered
    assert "calendar" not in lowered
    assert "replanning" not in lowered


def test_patch_9b_vault_summary_route_is_read_only_and_has_no_ai_n8n_or_persistent_wallet_side_effects() -> None:
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_vault.py"
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "vault.py"
    schema_path = BACKEND_ROOT / "app" / "schemas" / "imperium.py"
    route_text = route_path.read_text(encoding="utf-8")
    service_text = service_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    summary_route_section = route_text.split('@router.get("/summary"', maxsplit=1)[1].split(
        '@router.get("/summary/categories"',
        maxsplit=1,
    )[0]
    summary_schema_section = schema_text.split("class ImperiumVaultSummaryResponse", maxsplit=1)[1].split(
        "class MissionDecisionScoreRead",
        maxsplit=1,
    )[0]
    lowered = "\n".join([route_text, service_text, summary_schema_section]).lower()

    assert "class ImperiumVaultSummaryResponse" in schema_text
    assert "extra=\"forbid\"" in schema_text
    assert "safe_explanation: str = \"Vault summary computed from current user's ledger transactions.\"" in schema_text
    assert "get_vault_summary(" in service_text
    assert "ImperiumVaultTransaction" in service_text
    assert "db.add(" not in service_text
    assert "db.flush" not in service_text
    assert "db.commit" not in service_text
    assert "Idempotency-Key" not in summary_route_section
    assert "current_user: CurrentUserDep" in summary_route_section
    assert "currency" in summary_route_section
    assert "occurred_from" in summary_route_section
    assert "occurred_to" in summary_route_section
    assert "QwenClient" not in lowered
    assert "n8n_client" not in lowered
    assert "trigger_n8n" not in lowered
    assert "pgvector" not in lowered
    assert "embedding" not in lowered
    assert "memory" not in lowered
    assert "calendar" not in lowered
    assert "ocr" not in lowered
    assert "sadaqa" not in lowered
    assert "wallet" not in lowered
    assert "balance" not in lowered


def test_patch_9c_vault_category_summary_route_is_read_only_and_has_no_ai_n8n_or_persistent_wallet_side_effects() -> None:
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_vault.py"
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "vault.py"
    schema_path = BACKEND_ROOT / "app" / "schemas" / "imperium.py"
    docs_path = DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md"
    route_text = route_path.read_text(encoding="utf-8")
    service_text = service_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    docs_text = docs_path.read_text(encoding="utf-8")
    route_section = route_text.split('@router.get("/summary/categories"', maxsplit=1)[1].split(
        '@router.get("/summary/monthly"',
        maxsplit=1,
    )[0]
    schema_section = schema_text.split("class ImperiumVaultCategorySummaryItem", maxsplit=1)[1].split(
        "class MissionDecisionScoreRead",
        maxsplit=1,
    )[0]
    lowered_code = "\n".join([route_text, service_text, schema_section]).lower()
    lowered_docs = docs_text.lower()

    assert "class ImperiumVaultCategorySummaryItem" in schema_text
    assert "class ImperiumVaultCategorySummaryResponse" in schema_text
    assert "safe_explanation: str = \"Vault category summary computed from current user's ledger transactions.\"" in schema_text
    assert "get_vault_category_summary(" in service_text
    assert "ImperiumVaultTransaction" in service_text
    assert "db.add(" not in service_text
    assert "db.flush" not in service_text
    assert "db.commit" not in service_text
    assert "Idempotency-Key" not in route_section
    assert "current_user: CurrentUserDep" in route_section
    assert "transaction_type" in route_section
    assert "currency" in route_section
    assert "occurred_from" in route_section
    assert "occurred_to" in route_section
    assert "count" in schema_section
    assert "items" in schema_section
    assert "QwenClient" not in lowered_code
    assert "n8n_client" not in lowered_code
    assert "trigger_n8n" not in lowered_code
    assert "pgvector" not in lowered_code
    assert "embedding" not in lowered_code
    assert "memory" not in lowered_code
    assert "calendar" not in lowered_code
    assert "ocr" not in lowered_code
    assert "sadaqa" not in lowered_code
    assert "wallet" not in lowered_code
    assert "balance" not in lowered_code
    assert "uncategorized" in lowered_code
    assert "transaction_count desc" in lowered_docs
    assert "absolute net magnitude desc" in lowered_docs
    assert "no ai/n8n/ocr/sadaqa/wallet/balance workflows" in lowered_docs


def test_patch_9d_vault_monthly_summary_route_is_read_only_and_has_no_ai_n8n_or_persistent_wallet_side_effects() -> None:
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_vault.py"
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "vault.py"
    schema_path = BACKEND_ROOT / "app" / "schemas" / "imperium.py"
    docs_path = DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md"
    route_text = route_path.read_text(encoding="utf-8")
    service_text = service_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    docs_text = docs_path.read_text(encoding="utf-8")
    route_section = route_text.split('@router.get("/summary/monthly"', maxsplit=1)[1].split(
        '@router.get("/transactions"',
        maxsplit=1,
    )[0]
    schema_section = schema_text.split("class ImperiumVaultMonthlySummaryItem", maxsplit=1)[1].split(
        "class ImperiumVaultCategorySummaryItem",
        maxsplit=1,
    )[0]
    lowered_code = "\n".join([route_text, service_text, schema_section]).lower()
    lowered_docs = docs_text.lower()

    assert "class ImperiumVaultMonthlySummaryItem" in schema_text
    assert "class ImperiumVaultMonthlySummaryResponse" in schema_text
    assert "safe_explanation: str = \"Vault monthly summary computed from current user's ledger transactions.\"" in schema_text
    assert "get_vault_monthly_summary(" in service_text
    assert "ImperiumVaultTransaction" in service_text
    assert "db.add(" not in service_text
    assert "db.flush" not in service_text
    assert "db.commit" not in service_text
    assert "Idempotency-Key" not in route_section
    assert "current_user: CurrentUserDep" in route_section
    assert "currency" in route_section
    assert "occurred_from" in route_section
    assert "occurred_to" in route_section
    assert "month" in schema_section
    assert "count" in schema_section
    assert "items" in schema_section
    assert "yyyy-mm" in lowered_docs
    assert "utc `occurred_at` month and the public `yyyy-mm` format" in lowered_docs
    assert "groups by the utc month of `occurred_at` and returns `yyyy-mm`" in lowered_docs
    assert "patch 9d" in lowered_docs
    assert "read-only" in lowered_docs
    assert "grouped by month" in lowered_docs
    assert "no ai/n8n/ocr/sadaqa/wallet/balance workflows" in lowered_docs
    assert "QwenClient" not in lowered_code
    assert "n8n_client" not in lowered_code
    assert "trigger_n8n" not in lowered_code
    assert "pgvector" not in lowered_code
    assert "embedding" not in lowered_code
    assert "memory" not in lowered_code
    assert "calendar" not in lowered_code
    assert "ocr" not in lowered_code
    assert "sadaqa" not in lowered_code
    assert "wallet" not in lowered_code
    assert "balance" not in lowered_code


def test_backlog_path_has_no_ai_provider_imports() -> None:
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "missions.py"
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py"
    service_text = service_path.read_text(encoding="utf-8")
    route_text = route_path.read_text(encoding="utf-8")
    backlog_route_section = route_text.split('@router.post(\n    "/missions/backlog"', maxsplit=1)[1].split(
        '@router.get("/missions/{mission_id}/decision-score"',
        maxsplit=1,
    )[0]
    backlog_service_section = service_text.split("def create_backlog_mission", maxsplit=1)[1].split(
        "def complete_mission",
        maxsplit=1,
    )[0]
    backlog_text = "\n".join([backlog_route_section, backlog_service_section])

    assert "QwenClient" not in backlog_text
    assert "providers" not in backlog_text
    assert "openai" not in backlog_text.lower()
    assert "anthropic" not in backlog_text.lower()
    assert "gemini" not in backlog_text.lower()
    assert "claude" not in backlog_text.lower()
    assert "opus" not in backlog_text.lower()


def test_backlog_decision_preview_has_no_ai_n8n_pgvector_embedding_or_writes() -> None:
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "missions.py"
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py"
    schema_path = BACKEND_ROOT / "app" / "schemas" / "imperium.py"
    service_text = service_path.read_text(encoding="utf-8")
    route_text = route_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    preview_service_section = service_text.split("def get_backlog_decision_preview", maxsplit=1)[1].split(
        "def promote_backlog_mission",
        maxsplit=1,
    )[0]
    preview_route_section = route_text.split('"/missions/backlog/decision-preview"', maxsplit=1)[1].split(
        '@router.post("/missions/backlog/{mission_id}/promote"',
        maxsplit=1,
    )[0]
    preview_schema_section = schema_text.split("class BacklogDecisionScoreSummary", maxsplit=1)[1].split(
        "class PromotedBacklogMissionRead",
        maxsplit=1,
    )[0]
    preview_text = "\n".join([preview_service_section, preview_route_section, preview_schema_section])
    lowered = preview_text.lower()

    assert "QwenClient" not in preview_text
    assert "providers" not in preview_text
    assert "openai" not in lowered
    assert "anthropic" not in lowered
    assert "gemini" not in lowered
    assert "claude" not in lowered
    assert "n8n" not in lowered
    assert "pgvector" not in lowered
    assert "embedding" not in lowered
    assert "ai_memories" not in preview_text
    assert "calendar" not in lowered
    assert "db.add" not in preview_service_section
    assert "db.flush" not in preview_service_section
    assert "db.commit" not in preview_service_section
    assert "mission.status =" not in preview_service_section
    assert "started_at" not in preview_schema_section
    assert "ended_at" not in preview_schema_section


def test_active_mission_read_has_no_ai_n8n_pgvector_embedding_or_writes() -> None:
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py"
    schema_path = BACKEND_ROOT / "app" / "schemas" / "imperium.py"
    route_text = route_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    active_route_section = route_text.split('@router.get("/missions/active"', maxsplit=1)[1].split(
        '@router.get("/missions/recent"',
        maxsplit=1,
    )[0]
    active_schema_section = schema_text.split("class ActiveMissionRead", maxsplit=1)[1].split(
        "class MissionCompletionRead",
        maxsplit=1,
    )[0]
    combined = "\n".join([active_route_section, active_schema_section]).lower()

    assert "Idempotency-Key" not in active_route_section
    assert "QwenClient" not in active_route_section
    assert "providers" not in active_route_section
    assert "openai" not in combined
    assert "anthropic" not in combined
    assert "gemini" not in combined
    assert "claude" not in combined
    assert "n8n" not in combined
    assert "pgvector" not in combined
    assert "embedding" not in combined
    assert "ai agent" not in combined
    assert "aiagent" not in combined
    assert "memory commit" not in combined
    assert "replanning" not in combined
    assert "calendar" not in combined
    assert "db.add" not in active_route_section
    assert "db.flush" not in active_route_section
    assert "db.commit" not in active_route_section
    assert "weighted_score" not in active_schema_section
    assert "domain_coefficient" not in active_schema_section
    assert "coefficient" not in active_schema_section
    assert "ended_at" not in active_schema_section


def test_mission_detail_read_has_no_ai_n8n_pgvector_embedding_or_writes() -> None:
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "missions.py"
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py"
    schema_path = BACKEND_ROOT / "app" / "schemas" / "imperium.py"
    service_text = service_path.read_text(encoding="utf-8")
    route_text = route_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    detail_service_section = service_text.split("def get_mission_detail", maxsplit=1)[1].split(
        "def get_mission_decision_score",
        maxsplit=1,
    )[0]
    detail_route_section = route_text.split("def mission_detail_route(", maxsplit=1)[1].split(
        "def mission_decision_score_route",
        maxsplit=1,
    )[0]
    detail_schema_section = schema_text.split("class MissionDetailRead", maxsplit=1)[1].split(
        "class MissionDetailResponse",
        maxsplit=1,
    )[0]
    detail_text = "\n".join([detail_service_section, detail_route_section, detail_schema_section]).lower()

    assert "Idempotency-Key" not in detail_route_section
    assert "QwenClient" not in detail_text
    assert "providers" not in detail_text
    assert "openai" not in detail_text
    assert "anthropic" not in detail_text
    assert "gemini" not in detail_text
    assert "claude" not in detail_text
    assert "n8n" not in detail_text
    assert "pgvector" not in detail_text
    assert "embedding" not in detail_text
    assert "memory" not in detail_text
    assert "calendar" not in detail_text
    assert "db.add(" not in detail_service_section
    assert "db.flush" not in detail_service_section
    assert "db.commit" not in detail_service_section
    assert "weighted_score" not in detail_schema_section
    assert "domain_coefficient" not in detail_schema_section
    assert "coefficient" not in detail_schema_section
    assert "decision_score" not in detail_schema_section
    assert "started_at" in detail_schema_section
    assert "ended_at" in detail_schema_section


def test_backlog_path_has_no_n8n_client_imports() -> None:
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "missions.py"
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py"
    service_text = service_path.read_text(encoding="utf-8")
    route_text = route_path.read_text(encoding="utf-8")
    backlog_route_section = route_text.split('@router.post(\n    "/missions/backlog"', maxsplit=1)[1].split(
        '@router.get("/missions/{mission_id}/decision-score"',
        maxsplit=1,
    )[0]
    backlog_service_section = service_text.split("def create_backlog_mission", maxsplit=1)[1].split(
        "def complete_mission",
        maxsplit=1,
    )[0]
    backlog_text = "\n".join([backlog_route_section, backlog_service_section])

    assert "n8n_client" not in backlog_text
    assert "trigger_n8n" not in backlog_text
    assert "n8n" not in backlog_text.lower()


def test_backlog_path_introduces_no_pgvector_or_embedding_fields() -> None:
    model_path = BACKEND_ROOT / "app" / "models" / "imperium.py"
    schema_path = BACKEND_ROOT / "app" / "schemas" / "imperium.py"
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "missions.py"
    model_text = model_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    service_text = service_path.read_text(encoding="utf-8")
    mission_model_section = model_text.split("class ImperiumMission", maxsplit=1)[1].split(
        "class ImperiumPriorityRule",
        maxsplit=1,
    )[0]
    backlog_schema_section = schema_text.split("class BacklogMissionCreateRequest", maxsplit=1)[1].split(
        "class CompleteMissionRequest",
        maxsplit=1,
    )[0]
    backlog_service_section = service_text.split("def create_backlog_mission", maxsplit=1)[1].split(
        "def complete_mission",
        maxsplit=1,
    )[0]
    backlog_text = "\n".join([mission_model_section, backlog_schema_section, backlog_service_section]).lower()

    assert "pgvector" not in backlog_text
    assert "embedding" not in backlog_text
    assert "vector =" not in backlog_text
    assert "vector:" not in backlog_text


def test_backlog_public_response_has_no_score_coefficient_exposure() -> None:
    schema_path = BACKEND_ROOT / "app" / "schemas" / "imperium.py"
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "missions.py"
    schema_text = schema_path.read_text(encoding="utf-8")
    service_text = service_path.read_text(encoding="utf-8")
    backlog_read_section = schema_text.split("class MissionDecisionScoreSummary", maxsplit=1)[1].split(
        "class MissionWriteResponse",
        maxsplit=1,
    )[0]
    backlog_response_section = service_text.split("def _backlog_mission_read", maxsplit=1)[1].split(
        "def _promote_response",
        maxsplit=1,
    )[0]
    public_text = "\n".join([backlog_read_section, backlog_response_section])

    assert "priority_bucket" in backlog_read_section
    assert "domain_coefficient" not in public_text
    assert "weighted_score" not in public_text
    assert "final_weighted_score" not in public_text
    assert "position_to_coefficient" not in public_text


def test_backlog_promotion_guardrails_have_no_external_or_memory_side_effects() -> None:
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "missions.py"
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py"
    schema_path = BACKEND_ROOT / "app" / "schemas" / "imperium.py"
    service_text = service_path.read_text(encoding="utf-8")
    route_text = route_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    promote_service_section = service_text.split("def promote_backlog_mission", maxsplit=1)[1].split(
        "def complete_mission",
        maxsplit=1,
    )[0]
    promote_route_section = route_text.split('@router.post("/missions/backlog/{mission_id}/promote"', maxsplit=1)[
        1
    ].split('@router.post("/missions/{mission_id}/complete"', maxsplit=1)[0]
    promote_schema_section = schema_text.split("class PromotedBacklogMissionRead", maxsplit=1)[1].split(
        "class MissionWriteResponse",
        maxsplit=1,
    )[0]
    promote_text = "\n".join([promote_service_section, promote_route_section, promote_schema_section])
    lowered = promote_text.lower()

    assert "QwenClient" not in promote_text
    assert "providers" not in promote_text
    assert "openai" not in lowered
    assert "anthropic" not in lowered
    assert "gemini" not in lowered
    assert "claude" not in lowered
    assert "n8n" not in lowered
    assert "pgvector" not in lowered
    assert "embedding" not in lowered
    assert "ai_memories" not in promote_text
    assert "calendar" not in lowered
    assert "domain_coefficient" not in promote_schema_section
    assert "weighted_score" not in promote_schema_section
    assert "final_weighted_score" not in promote_schema_section
    assert "ended_at" not in promote_schema_section
    assert "guardrails_checked" in promote_schema_section

def test_patch_9e_vault_transaction_detail_route_is_read_only_and_user_scoped() -> None:
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_vault.py"
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "vault.py"
    schema_path = BACKEND_ROOT / "app" / "schemas" / "imperium.py"
    docs_path = DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md"
    route_text = route_path.read_text(encoding="utf-8")
    service_text = service_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    docs_text = docs_path.read_text(encoding="utf-8")
    route_section = route_text.split('@router.get("/transactions/{transaction_id}"', maxsplit=1)[1].split(
        '@router.post(\n    "/transactions"',
        maxsplit=1,
    )[0]
    service_section = service_text.split("def get_vault_transaction_detail", maxsplit=1)[1].split(
        "def get_vault_summary",
        maxsplit=1,
    )[0]
    lowered_code = "\n".join([route_section, service_section]).lower()
    lowered_docs = docs_text.lower()

    assert "class ImperiumVaultTransactionDetailResponse" in schema_text
    assert "safe_explanation: str = \"Vault transaction detail for current user.\"" in schema_text
    assert "CurrentUserDep" in route_section
    assert "Idempotency-Key" not in route_section
    assert "HTTP_404_NOT_FOUND" in route_section
    assert "ImperiumVaultTransaction.user_id == current_user.id" in service_section
    assert "db.add(" not in service_section
    assert "db.flush" not in service_section
    assert "db.commit" not in service_section
    assert "db.rollback" not in service_section
    assert "/api/imperium/vault/transactions/{transaction_id}" in docs_text
    assert "non-owned => 404" in lowered_docs
    assert "read-only" in lowered_docs
    assert "qwenclient" not in lowered_code
    assert "n8n_client" not in lowered_code
    assert "trigger_n8n" not in lowered_code
    assert "pgvector" not in lowered_code
    assert "embedding" not in lowered_code
    assert "memory" not in lowered_code
    assert "calendar" not in lowered_code
    assert "ocr" not in lowered_code
    assert "sadaqa" not in lowered_code


def test_patch_9f_vault_reversal_route_is_append_only_user_scoped_and_deterministic() -> None:
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_vault.py"
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "vault_transactions.py"
    schema_path = BACKEND_ROOT / "app" / "schemas" / "vault.py"
    migration_path = (
        BACKEND_ROOT / "alembic" / "versions" / "20260525_0025_imperium_vault_transaction_reversals.py"
    )
    docs_path = DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md"
    route_text = route_path.read_text(encoding="utf-8")
    service_text = service_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    migration_text = migration_path.read_text(encoding="utf-8")
    docs_text = docs_path.read_text(encoding="utf-8")
    route_section = route_text.split('@router.post(\n    "/transactions/{transaction_id}/reverse"', maxsplit=1)[
        1
    ].split('@router.get("/transactions"', maxsplit=1)[0]
    service_section = service_text.split("def reverse_vault_transaction", maxsplit=1)[1].split(
        "def list_vault_transactions",
        maxsplit=1,
    )[0]
    reverse_schema_section = schema_text.split("class ImperiumVaultTransactionReverseRequest", maxsplit=1)[1].split(
        "class ImperiumVaultTransactionReversalSummary",
        maxsplit=1,
    )[0]
    lowered_docs = docs_text.lower()

    assert 'revision: str = "20260525_0025"' in migration_text
    assert 'down_revision: str | None = "20260525_0024"' in migration_text
    assert "/api/imperium/vault/transactions/{transaction_id}/reverse" in docs_text
    assert "Patch 9F" in docs_text
    assert "CurrentUserDep" in route_section
    assert "Idempotency-Key" in route_section
    assert "VaultTransactionNotFoundError" in route_section
    assert "HTTP_404_NOT_FOUND" in route_section
    assert "HTTP_409_CONFLICT" in route_section
    assert "extra=\"forbid\"" in reverse_schema_section
    assert "amount_cents" not in reverse_schema_section
    assert "transaction_type" not in reverse_schema_section
    assert "currency" not in reverse_schema_section
    assert "user_id" not in reverse_schema_section
    assert "ImperiumVaultTransaction.user_id == current_user.id" in service_section
    assert "transaction_type=_opposite_transaction_type(original.transaction_type)" in service_section
    assert "amount_cents=original.amount_cents" in service_section
    assert "currency=original.currency" in service_section
    assert "source=\"reversal\"" in service_section
    assert "external_ref=None" in service_section
    assert "reversal_occurred_at = datetime.now(UTC)" in service_section
    assert "occurred_at=reversal_occurred_at" in service_section
    assert "occurred_at=original.occurred_at" not in service_section
    assert "is_reversal=True" in service_section
    assert "reversal_of_transaction_id=original.id" in service_section
    assert "db.add(reversal)" in service_section
    assert "db.delete" not in service_section
    assert "op.drop_table" not in migration_text
    assert "reversal_of_transaction_id" in migration_text
    assert "reversal_reason" in migration_text
    assert "is_reversal" in migration_text
    assert "postgresql_where=sa.text(\"is_reversal = true\")" in migration_text
    assert "append-only correction endpoint" in lowered_docs
    assert "the original transaction is never updated or deleted" in lowered_docs
    assert "one and only one reversal per original transaction" in lowered_docs


def test_patch_9g_vault_transaction_immutability_contract_is_preserved() -> None:
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_vault.py"
    write_service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "vault_transactions.py"
    read_service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "vault.py"
    docs_path = DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md"
    schema_docs_path = DOCS_ROOT / "05_DATABASE_SCHEMA.md"
    route_text = route_path.read_text(encoding="utf-8")
    write_service_text = write_service_path.read_text(encoding="utf-8")
    read_service_text = read_service_path.read_text(encoding="utf-8")
    docs_text = docs_path.read_text(encoding="utf-8")
    schema_docs_text = schema_docs_path.read_text(encoding="utf-8")
    lowered_docs = docs_text.lower()
    lowered_schema_docs = schema_docs_text.lower()

    assert '@router.put("/transactions"' not in route_text
    assert '@router.patch("/transactions"' not in route_text
    assert '@router.delete("/transactions"' not in route_text
    assert "/transactions/{transaction_id}/reverse" in route_text

    assert "def update_vault_transaction" not in write_service_text
    assert "def delete_vault_transaction" not in write_service_text
    assert "db.delete(" not in write_service_text
    assert "session.delete(" not in write_service_text
    assert "def update_vault_transaction" not in read_service_text
    assert "def delete_vault_transaction" not in read_service_text

    assert "patch 9g" in lowered_docs
    assert "vault ledger is append-only" in lowered_docs
    assert "transactions are immutable" in lowered_docs
    assert "no put/patch/delete endpoints exist under `/api/imperium/vault/transactions`" in lowered_docs
    assert "post /api/imperium/vault/transactions/{transaction_id}/reverse" in lowered_docs
    assert "original transaction must never be updated or deleted" in lowered_docs
    assert "reversal transaction is a new transaction linked to the original" in lowered_docs
    assert "one reversal per original" in lowered_docs
    assert "forbidden for the append-only ledger" in lowered_docs

    assert "vault ledger is append-only" in lowered_schema_docs
    assert "transactions are immutable" in lowered_schema_docs
    assert "no put/patch/delete endpoint is allowed for `/api/imperium/vault/transactions`" in lowered_schema_docs
    assert "corrections must be written by appending a reversal row through `post /api/imperium/vault/transactions/{transaction_id}/reverse`" in lowered_schema_docs
    assert "the original transaction must never be updated or deleted" in lowered_schema_docs
    assert "the reversal transaction is a new row linked to the original transaction" in lowered_schema_docs
    assert "patch 9f/9g allow one and only one reversal per original transaction" in lowered_schema_docs
    assert "`updated_at` remains a generic row timestamp" in lowered_schema_docs
    assert "legacy direct edit route" in lowered_docs


def test_patch_9h_vault_contract_consolidation_is_explicit_and_audit_ready() -> None:
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_vault.py"
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "vault.py"
    transaction_service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "vault_transactions.py"
    create_schema_path = BACKEND_ROOT / "app" / "schemas" / "vault.py"
    contracts_path = DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md"
    schema_path = DOCS_ROOT / "05_DATABASE_SCHEMA.md"
    route_text = route_path.read_text(encoding="utf-8")
    service_text = service_path.read_text(encoding="utf-8")
    transaction_service_text = transaction_service_path.read_text(encoding="utf-8")
    create_schema_text = create_schema_path.read_text(encoding="utf-8")
    contracts_text = contracts_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    create_schema_section = create_schema_text.split("class ImperiumVaultTransactionCreate", maxsplit=1)[1].split(
        "class ImperiumVaultTransactionRead",
        maxsplit=1,
    )[0]
    lowered_code = "\n".join([route_text, service_text, transaction_service_text, create_schema_section]).lower()
    lowered_docs = "\n".join([contracts_text, schema_text]).lower()

    for endpoint in (
        "/summary",
        "/summary/categories",
        "/summary/monthly",
        "/transactions",
        "/transactions/{transaction_id}",
        "/transactions/{transaction_id}/reverse",
    ):
        assert endpoint in route_text

    assert '@router.put("/transactions"' not in route_text
    assert '@router.patch("/transactions"' not in route_text
    assert '@router.delete("/transactions"' not in route_text

    assert "Idempotency-Key" in route_text
    assert "CurrentUserDep" in route_text
    assert "append-only" in lowered_docs
    assert "immutable once inserted" in lowered_docs
    assert "the vault ledger is append-only" in lowered_docs
    assert "transactions are immutable after insert" in lowered_docs
    assert "all vault endpoints are scoped through `currentuserdep`" in lowered_docs
    assert "vault v1 uses utc temporal semantics" in lowered_docs
    assert "`occurred_at` is the only authoritative temporal source for vault v1 summaries and filters" in lowered_docs
    assert "`occurred_at` is stored and interpreted as utc for vault v1" in lowered_docs
    assert "summary endpoints share the same currency contract" in lowered_docs
    assert "exactly three ascii letters are accepted" in lowered_docs
    assert "accepted values are normalized uppercase" in lowered_docs
    assert 'pattern=r"^[A-Za-z]{3}$"' in route_text
    assert route_text.count('pattern=r"^[A-Za-z]{3}$"') == 3
    assert 'pattern=r"^[A-Z]{3}$"' in create_schema_section
    assert "def normalize_currency" in create_schema_section
    assert "return value.strip().upper()" in create_schema_section
    assert "normalized_currency = currency.strip().upper()" in service_text
    assert "currency=original.currency" in transaction_service_text
    assert "none of the vault 9h routes persist ai, n8n, ocr, sadaqa, wallet, balance" in lowered_docs

    for forbidden in (
        "openai",
        "anthropic",
        "gemini",
        "claude",
        "ai agent",
        "aiagent",
        "n8n_client",
        "trigger_n8n",
        "pgvector",
        "embedding",
        "memory commit",
        "calendar replanning",
        "ocr",
        "sadaqa",
        "wallet",
        "balance",
        "wallet persistence",
    ):
        assert forbidden not in lowered_code


def test_patch_9k_alembic_head_includes_vault_local_date_timezone_migration() -> None:
    migration_path = BACKEND_ROOT / "alembic" / "versions" / "20260525_0026_imperium_vault_local_date_timezone.py"
    migration_text = migration_path.read_text(encoding="utf-8")

    assert migration_path.exists()
    assert 'revision: str = "20260525_0026"' in migration_text
    assert 'down_revision: str | None = "20260525_0025"' in migration_text
    assert "op.add_column(\"imperium_vault_transactions\", sa.Column(\"local_date\", sa.Date(), nullable=True))" in migration_text
    assert "op.add_column(\"imperium_vault_transactions\", sa.Column(\"timezone\", sa.Text(), nullable=True))" in migration_text
    assert "op.create_index(" in migration_text


def test_patch_12g_path_today_has_single_canonical_route() -> None:
    from fastapi import FastAPI
    from fastapi.routing import APIRoute

    from app.api.v1.router import api_router
    from app.api.v1.routes import imperium_path
    from app.schemas.path import PathTodayResponse

    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    matching_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path == "/api/imperium/path/today"
        and "GET" in route.methods
    ]

    assert len(matching_routes) == 1
    assert matching_routes[0].endpoint is imperium_path.path_today_route
    assert matching_routes[0].response_model is PathTodayResponse


def test_path_item_legacy_model_is_documented_as_deprecated_when_present() -> None:
    model_text = (BACKEND_ROOT / "app" / "models" / "imperium.py").read_text(encoding="utf-8")
    lowered_docs = "\n".join(
        [
            (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8"),
            (DOCS_ROOT / "05_DATABASE_SCHEMA.md").read_text(encoding="utf-8"),
        ]
    ).lower()

    if "class ImperiumPathItem" not in model_text:
        return

    assert "imperiumpathitem" in lowered_docs
    assert "imperium_path_items" in lowered_docs
    assert "legacy" in lowered_docs
    assert "deprecated" in lowered_docs
    assert "must not mask" in lowered_docs
    assert "no automatic mission/vault linkage" in lowered_docs


def test_patch_12g_default_today_uses_europe_paris_helper_for_dashboard_path_and_pulse() -> None:
    helper_text = (BACKEND_ROOT / "app" / "core" / "dates.py").read_text(encoding="utf-8")
    dashboard_text = (BACKEND_ROOT / "app" / "services" / "imperium" / "dashboard.py").read_text(encoding="utf-8")
    path_route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_path.py").read_text(
        encoding="utf-8"
    )
    pulse_route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_pulse.py").read_text(
        encoding="utf-8"
    )
    contracts_text = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8").lower()

    assert 'DEFAULT_LOCAL_TIMEZONE = "Europe/Paris"' in helper_text
    assert "datetime.now(ZoneInfo(DEFAULT_LOCAL_TIMEZONE)).date()" in helper_text

    for text in (dashboard_text, path_route_text, pulse_route_text):
        assert "get_default_local_date" in text
        assert "date.today()" not in text

    assert "default date convention is europe/paris" in contracts_text
    assert "query `date` overrides the europe/paris default" in contracts_text


def test_patch_12g_get_priorities_is_read_only_compatibility_projection() -> None:
    route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium.py").read_text(encoding="utf-8")
    service_text = (BACKEND_ROOT / "app" / "services" / "imperium" / "decision_framework.py").read_text(
        encoding="utf-8"
    )
    contracts_text = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8").lower()
    legacy_get_section = route_text.split('@router.get("/priorities"', maxsplit=1)[1].split(
        '@router.post("/priorities"',
        maxsplit=1,
    )[0]
    get_or_initialize_section = service_text.split("def get_or_initialize_user_priorities", maxsplit=1)[1].split(
        "def get_user_priority_context",
        maxsplit=1,
    )[0]
    canonical_read_section = service_text.split("def get_canonical_priority_order", maxsplit=1)[1].split(
        "def _build_default_priorities",
        maxsplit=1,
    )[0]

    assert "persist_defaults=True" not in legacy_get_section
    assert "persist_defaults=True" not in get_or_initialize_section
    assert "persist_defaults" not in canonical_read_section

    for read_only_section in (legacy_get_section, get_or_initialize_section, canonical_read_section):
        assert "db.add(" not in read_only_section
        assert "db.add_all" not in read_only_section
        assert "db.flush" not in read_only_section
        assert "db.commit" not in read_only_section

    assert "read-only compatibility projection" in contracts_text
    assert "persistent initialization must use an explicit post" in contracts_text


def test_patch_12g_dashboard_audit_notes_are_documented_and_no_forbidden_engines_added() -> None:
    dashboard_route_text = (
        BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_dashboard.py"
    ).read_text(encoding="utf-8")
    dashboard_service_text = (BACKEND_ROOT / "app" / "services" / "imperium" / "dashboard.py").read_text(
        encoding="utf-8"
    )
    contracts_text = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8").lower()
    lowered_code = "\n".join([dashboard_route_text, dashboard_service_text]).lower()

    assert "three-letter currency codes are accepted and normalized uppercase" in contracts_text
    assert "iso-4217 existence is not validated in v1" in contracts_text
    assert "unknown or unused currency with no transaction returns zero totals" in contracts_text
    assert "*_available means the section was wired and calculated successfully in the snapshot" in contracts_text
    assert "not an external health check" in contracts_text
    assert "not an availability score" in contracts_text

    for forbidden in (
        "qwenclient",
        "openai",
        "anthropic",
        "gemini",
        "claude",
        "n8n_client",
        "trigger_n8n",
        "ocr",
        "weighted_score",
        "coaching",
        "recommendation",
    ):
        assert forbidden not in lowered_code


def test_patch_13a_daily_plan_foundation_is_read_only_and_uses_existing_snapshots() -> None:
    route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_daily_plan.py").read_text(
        encoding="utf-8"
    )
    service_text = (BACKEND_ROOT / "app" / "services" / "imperium" / "daily_plan.py").read_text(encoding="utf-8")
    schema_text = (BACKEND_ROOT / "app" / "schemas" / "daily_plan.py").read_text(encoding="utf-8")
    router_text = (BACKEND_ROOT / "app" / "api" / "v1" / "router.py").read_text(encoding="utf-8")
    contracts_text = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8").lower()
    schema_docs_text = (DOCS_ROOT / "05_DATABASE_SCHEMA.md").read_text(encoding="utf-8").lower()
    lowered_code = "\n".join([route_text, service_text, schema_text]).lower()

    assert '@router.get("/daily-plan"' in route_text
    assert "get_default_local_date" in service_text
    assert "get_imperium_dashboard_foundation" in service_text
    assert "get_current_active_mission" in service_text
    assert "get_path_today_view" in service_text
    assert "get_pulse_today_entry" in service_text
    assert "get_dashboard_snapshot" not in service_text
    assert "DailyPlanSummarySection" in schema_text
    assert "DailyPlanReadinessSection" in schema_text
    assert "DailyPlanMetaSection" in schema_text
    assert "read_only: bool" in schema_text
    assert "daily_plan_version: str" in schema_text
    assert "snapshot_generated_at: datetime" in schema_text
    assert "dashboard_present: bool" in schema_text
    assert "mission_present: bool" in schema_text
    assert "path_items_count: int" in schema_text
    assert "pulse_entry_present: bool" in schema_text
    assert "readiness: DailyPlanReadinessSection" in schema_text
    assert 'api_router.include_router(imperium_daily_plan.router, prefix="/imperium", tags=["imperium-daily-plan"])' in router_text
    assert router_text.index("imperium_daily_plan.router") < router_text.index("imperium.router")

    assert "/api/imperium/daily-plan" in contracts_text
    assert "daily plan snapshot" in contracts_text
    assert "read-only consolidation layer" in contracts_text
    assert "no legacy dashboard aggregator" in contracts_text
    assert "readiness snapshot only" in contracts_text
    assert "bool/count only" in contracts_text
    assert "not a score" in contracts_text
    assert "not a recommendation" in contracts_text
    assert "read-only semantics" in contracts_text
    assert "/api/imperium/daily-plan" in schema_docs_text
    assert "does not persist a new plan row" in schema_docs_text
    assert "summary and meta are metadata-only sections" in schema_docs_text
    assert "readiness" in schema_docs_text

    for forbidden in (
        "qwenclient",
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
        "ocr",
        "replanning",
        "scoring",
        "coaching",
        "recommendation",
        "health_score",
        "coach",
        "db.add(",
        "db.flush",
        "db.commit",
        "calendar",
    ):
        assert forbidden not in lowered_code


def test_patch_13b_daily_plan_contract_is_explicit_and_write_free() -> None:
    route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_daily_plan.py").read_text(
        encoding="utf-8"
    )
    service_text = (BACKEND_ROOT / "app" / "services" / "imperium" / "daily_plan.py").read_text(encoding="utf-8")
    schema_text = (BACKEND_ROOT / "app" / "schemas" / "daily_plan.py").read_text(encoding="utf-8")
    router_text = (BACKEND_ROOT / "app" / "api" / "v1" / "router.py").read_text(encoding="utf-8")
    lowered = "\n".join([route_text, service_text, schema_text]).lower()

    assert router_text.index("imperium_daily_plan.router") < router_text.index("imperium.router")
    assert '@router.get("/daily-plan"' in route_text
    assert "date: date | None = Query(default=None, alias=\"date\")" in route_text
    assert "get_default_local_date" in service_text
    assert "datetime.now(UTC)" in service_text
    assert 'daily_plan_version="v1"' in service_text
    assert "read_only=True" in service_text
    assert "db.add(" not in lowered
    assert "db.flush" not in lowered
    assert "db.commit" not in lowered
    assert "legacy dashboard aggregator" not in lowered
    assert "get_dashboard_snapshot" not in lowered
    assert "dashboard_present" in lowered
    assert "mission_present" in lowered
    assert "DailyPlanModuleSection" in schema_text
    assert "modules: list[DailyPlanModuleSection]" in schema_text
    assert 'name="dashboard", status="included", read_only=True' in service_text
    assert 'name="mission", status="included", read_only=True' in service_text
    assert 'name="path", status="included", read_only=True' in service_text
    assert 'name="pulse", status="included", read_only=True' in service_text
    assert "read_only=True" in service_text
    assert "qwenclient" not in lowered
    assert "openai" not in lowered
    assert "anthropic" not in lowered
    assert "gemini" not in lowered
    assert "claude" not in lowered
    assert "n8n_client" not in lowered
    assert "trigger_n8n" not in lowered
    assert "ocr" not in lowered
    assert "pgvector" not in lowered
    assert "embedding" not in lowered
    assert "memory" not in lowered
    assert "scoring" not in lowered
    assert "coaching" not in lowered
    assert "recommendation" not in lowered
    assert "health_score" not in lowered
    assert "health_check" not in lowered
    assert "auto create" not in lowered
    assert "cross-module" not in lowered


def test_patch_13e_daily_plan_contract_consolidation_v2_is_read_only_and_non_canonical() -> None:
    route_text = (BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_daily_plan.py").read_text(
        encoding="utf-8"
    )
    service_text = (BACKEND_ROOT / "app" / "services" / "imperium" / "daily_plan.py").read_text(encoding="utf-8")
    schema_text = (BACKEND_ROOT / "app" / "schemas" / "daily_plan.py").read_text(encoding="utf-8")
    dashboard_service_text = (BACKEND_ROOT / "app" / "services" / "imperium" / "dashboard.py").read_text(
        encoding="utf-8"
    )
    contracts_text = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8").lower()
    schema_docs_text = (DOCS_ROOT / "05_DATABASE_SCHEMA.md").read_text(encoding="utf-8").lower()
    lowered = "\n".join([route_text, service_text, schema_text, dashboard_service_text]).lower()

    assert "legacy dashboard aggregator" not in service_text.lower()
    assert "legacy dashboard aggregator" not in dashboard_service_text.lower()
    assert "get_imperium_dashboard_foundation" in service_text
    assert "db.add(" not in service_text
    assert "db.flush" not in service_text
    assert "db.commit" not in service_text
    assert "ai router" not in service_text.lower()
    assert "ai agent" not in service_text.lower()
    assert "n8n" not in service_text.lower()
    assert "ocr" not in service_text.lower()
    assert "scoring" not in service_text.lower()
    assert "coaching" not in service_text.lower()
    assert "recommendation" not in service_text.lower()
    assert "health check" not in service_text.lower()
    assert "health_score" not in service_text.lower()
    assert "auto create" not in service_text.lower()
    assert "create path" not in service_text.lower()
    assert "create pulse" not in service_text.lower()
    assert "cross-module" not in service_text.lower()
    assert "dashboard" in lowered
    assert "mission" in lowered
    assert "path" in lowered
    assert "pulse" in lowered
    assert 'name="dashboard", status="included", read_only=True' in service_text
    assert 'name="mission", status="included", read_only=True' in service_text
    assert 'name="path", status="included", read_only=True' in service_text
    assert 'name="pulse", status="included", read_only=True' in service_text
    assert "readiness: DailyPlanReadinessSection" in schema_text
    assert "modules: list[DailyPlanModuleSection]" in schema_text
    assert "daily_plan_version=\"v1\"" in service_text
    assert "datetime.now(UTC)" in service_text
    assert "snapshot_generated_at" in schema_text
    assert "safe_explanation" in schema_text
    assert "not a score" in contracts_text
    assert "not a recommendation" in contracts_text
    assert "not a health check" in contracts_text
    assert "no orchestration" in contracts_text
    assert "summary" in schema_docs_text
    assert "meta" in schema_docs_text
    assert "readiness" in schema_docs_text
    assert "modules" in schema_docs_text
    assert "legacy dashboard aggregator" in contracts_text
    assert "no new endpoint" not in lowered


def test_path_foundation_10a_is_scoped_read_only_on_get_and_has_no_ai_or_workflow_side_effects() -> None:
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_path.py"
    service_path = BACKEND_ROOT / "app" / "services" / "path" / "habits.py"
    schema_path = BACKEND_ROOT / "app" / "schemas" / "path.py"
    migration_path = BACKEND_ROOT / "alembic" / "versions" / "20260525_0027_imperium_path_habits_check_ins.py"
    contracts_path = DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md"
    schema_docs_path = DOCS_ROOT / "05_DATABASE_SCHEMA.md"
    route_text = route_path.read_text(encoding="utf-8")
    service_text = service_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    migration_text = migration_path.read_text(encoding="utf-8")
    contracts_text = contracts_path.read_text(encoding="utf-8")
    schema_docs_text = schema_docs_path.read_text(encoding="utf-8")
    habit_create_schema = schema_text.split("class PathHabitCreate", maxsplit=1)[1].split(
        "class PathCheckInCreate",
        maxsplit=1,
    )[0]
    check_in_create_schema = schema_text.split("class PathCheckInCreate", maxsplit=1)[1].split(
        "class PathHabitRead",
        maxsplit=1,
    )[0]
    list_habits_service = service_text.split("def list_path_habits", maxsplit=1)[1].split(
        "def create_path_check_in",
        maxsplit=1,
    )[0]
    list_check_ins_service = service_text.split("def list_path_check_ins", maxsplit=1)[1].split(
        "def _get_user_habit",
        maxsplit=1,
    )[0]
    habit_get_route = route_text.split('@router.get("/habits"', maxsplit=1)[1].split(
        '@router.post("/habits/{habit_id}/archive"',
        maxsplit=1,
    )[0]
    check_ins_get_route = route_text.split('@router.get("/check-ins"', maxsplit=1)[1].split(
        "def _require_idempotency_key",
        maxsplit=1,
    )[0]
    combined_code = "\n".join([route_text, service_text, schema_text, migration_text])
    lowered_code = combined_code.lower()
    lowered_docs = "\n".join([contracts_text, schema_docs_text]).lower()

    assert 'revision: str = "20260525_0027"' in migration_text
    assert 'down_revision: str | None = "20260525_0026"' in migration_text
    assert "imperium_path_habits" in migration_text
    assert "imperium_path_check_ins" in migration_text
    assert "imperium_path_check_ins_user_habit_date_unique" in migration_text
    assert "extra=\"forbid\"" in habit_create_schema
    assert "extra=\"forbid\"" in check_in_create_schema
    assert "user_id" not in habit_create_schema
    assert "user_id" not in check_in_create_schema
    assert "Idempotency-Key" in route_text
    assert "Idempotency-Key" not in habit_get_route
    assert "Idempotency-Key" not in check_ins_get_route

    for read_only_section in (list_habits_service, list_check_ins_service, habit_get_route, check_ins_get_route):
        assert "db.add(" not in read_only_section
        assert "db.flush" not in read_only_section
        assert "db.commit" not in read_only_section

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
        "automatic memory",
        "memory commit",
        "calendar",
        "replanning",
        "calendar replanning",
        "ocr",
        "mission/vault",
        "mission",
        "vault",
        "discipline_score",
        "weighted_score",
        "automatic scoring",
    ):
        assert forbidden not in lowered_code

    assert "path foundation 10a" in lowered_docs
    assert "`post /api/imperium/path/habits`" in lowered_docs
    assert "`get /api/imperium/path/habits`" in lowered_docs
    assert "`post /api/imperium/path/habits/{habit_id}/check-ins`" in lowered_docs
    assert "`get /api/imperium/path/check-ins`" in lowered_docs
    assert "missed requires reason" in lowered_docs
    assert "no ai/n8n/scoring/calendar in 10a" in lowered_docs
    assert "no pgvector write" in lowered_docs
    assert "no embeddings" in lowered_docs
    assert "no automatic memory commit" in lowered_docs
    assert "no automatic mission/vault linkage" in lowered_docs
    assert "no automatic replanning" in lowered_docs
    assert "no automatic scoring" in lowered_docs
    assert "no automatic check-in creation" in lowered_docs


def test_path_today_view_10b_is_read_only_and_reports_pending_done_missed_only() -> None:
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_path.py"
    service_path = BACKEND_ROOT / "app" / "services" / "path" / "habits.py"
    schema_path = BACKEND_ROOT / "app" / "schemas" / "path.py"
    contracts_path = DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md"
    route_text = route_path.read_text(encoding="utf-8")
    service_text = service_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    contracts_text = contracts_path.read_text(encoding="utf-8")
    today_route = route_text.split('@router.get("/today"', maxsplit=1)[1].split(
        '@router.get("/stats/summary"',
        maxsplit=1,
    )[0]
    today_service = service_text.split("def get_path_today_view", maxsplit=1)[1].split(
        "def _get_user_habit",
        maxsplit=1,
    )[0]
    lowered_code = "\n".join([route_text, service_text, schema_text]).lower()
    lowered_docs = contracts_text.lower()

    assert "@router.get(\"/today\"" in route_text
    assert "response_model=PathTodayResponse" in route_text
    assert "current_user: CurrentUserDep" in today_route
    assert "Idempotency-Key" not in today_route
    assert "db.add(" not in today_route
    assert "db.flush" not in today_route
    assert "db.commit" not in today_route
    assert "db.add(" not in today_service
    assert "db.flush" not in today_service
    assert "db.commit" not in today_service
    assert "ImperiumPathHabit.is_active.is_(True)" in today_service
    assert "ImperiumPathHabit.created_at.asc()" in today_service
    assert "ImperiumPathHabit.id.asc()" in today_service
    assert "ImperiumPathCheckIn.user_id == current_user.id" in today_service
    assert "ImperiumPathCheckIn.check_date == local_date" in today_service
    assert "PathTodayStatus.pending" in today_service
    assert "PathTodayStatus.done" in today_service
    assert "PathTodayStatus.missed" in today_service
    assert "PathTodayResponse" in schema_text
    assert "PathTodayItemRead" in schema_text
    assert "pending" in schema_text
    assert "done" in schema_text
    assert "missed" in schema_text

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
        "automatic memory",
        "memory commit",
        "calendar",
        "replanning",
        "ocr",
        "discipline_score",
        "weighted_score",
        "mission",
        "mission_id",
        "vault",
    ):
        assert forbidden not in lowered_code

    assert "get /api/imperium/path/today" in lowered_docs
    assert "path today view 10b" in lowered_docs
    assert "read-only" in lowered_docs
    assert "pending/done/missed" in lowered_docs
    assert "no ai/n8n/scoring/calendar" in lowered_docs
    assert "no automatic check-in creation" in lowered_docs


def test_path_habit_detail_10d_is_read_only_user_scoped_and_no_ai_side_effects() -> None:
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_path.py"
    service_path = BACKEND_ROOT / "app" / "services" / "path" / "habits.py"
    schema_path = BACKEND_ROOT / "app" / "schemas" / "path.py"
    contracts_path = DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md"
    route_text = route_path.read_text(encoding="utf-8")
    service_text = service_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    contracts_text = contracts_path.read_text(encoding="utf-8")
    lowered_code = "\n".join([route_text, service_text, schema_text]).lower()
    lowered_docs = contracts_text.lower()
    detail_route = route_text.split('@router.get("/habits/{habit_id}"', maxsplit=1)[1].split(
        '@router.post("/habits/{habit_id}/archive"',
        maxsplit=1,
    )[0]
    detail_service = service_text.split("def get_path_habit_detail", maxsplit=1)[1].split(
        "def create_path_check_in",
        maxsplit=1,
    )[0]
    route_order = [
        route_text.index('@router.get("/habits"'),
        route_text.index('@router.get("/habits/{habit_id}"'),
        route_text.index('@router.post("/habits/{habit_id}/archive"'),
    ]

    assert "response_model=PathHabitDetailResponse" in route_text
    assert "current_user: CurrentUserDep" in detail_route
    assert "Idempotency-Key" not in detail_route
    assert "PathHabitNotFoundError" in detail_route
    assert "Path habit not found." in detail_service
    assert "_get_user_habit" in detail_service
    assert "HABIT_DETAIL_SAFE_EXPLANATION" in detail_service
    assert "PathHabitDetailResponse" in schema_text
    assert route_order == sorted(route_order)

    for read_only_section in (detail_route, detail_service):
        assert "db.add(" not in read_only_section
        assert "db.flush" not in read_only_section
        assert "db.commit" not in read_only_section

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
        "automatic memory",
        "memory commit",
        "calendar",
        "replanning",
        "discipline_score",
        "weighted_score",
        "scoring",
    ):
        assert forbidden not in lowered_code

    assert "get /api/imperium/path/habits/{habit_id}" in lowered_docs
    assert "path habit detail 10d" in lowered_docs
    assert "read-only" in lowered_docs
    assert "404" in lowered_docs
    assert "non-owned" in lowered_docs
    assert "never creates a check-in" in lowered_docs


def test_path_check_in_detail_10e_is_read_only_user_scoped_and_no_ai_side_effects() -> None:
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_path.py"
    service_path = BACKEND_ROOT / "app" / "services" / "path" / "habits.py"
    schema_path = BACKEND_ROOT / "app" / "schemas" / "path.py"
    contracts_path = DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md"
    route_text = route_path.read_text(encoding="utf-8")
    service_text = service_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    contracts_text = contracts_path.read_text(encoding="utf-8")
    lowered_code = "\n".join([route_text, service_text, schema_text]).lower()
    lowered_docs = contracts_text.lower()
    detail_route = route_text.split('@router.get("/check-ins/{check_in_id}"', maxsplit=1)[1].split(
        "def _require_idempotency_key",
        maxsplit=1,
    )[0]
    detail_service = service_text.split("def get_path_check_in_detail", maxsplit=1)[1].split(
        "def get_path_today_view",
        maxsplit=1,
    )[0]
    assert "response_model=PathCheckInDetailResponse" in route_text
    assert "current_user: CurrentUserDep" in detail_route
    assert "Idempotency-Key" not in detail_route
    assert "PathCheckInNotFoundError" in detail_route
    assert "Path check-in not found." in detail_service
    assert "ImperiumPathCheckIn.id == check_in_id" in detail_service
    assert "ImperiumPathCheckIn.user_id == current_user.id" in detail_service
    assert "CHECK_IN_DETAIL_SAFE_EXPLANATION" in detail_service
    assert "PathCheckInDetailResponse" in schema_text
    assert route_text.index('@router.get("/today"') < route_text.index('@router.get("/check-ins"')
    assert route_text.index('@router.get("/check-ins"') < route_text.index('@router.get("/check-ins/{check_in_id}"')

    for read_only_section in (detail_route, detail_service):
        assert "db.add(" not in read_only_section
        assert "db.flush" not in read_only_section
        assert "db.commit" not in read_only_section

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
        "automatic memory",
        "memory commit",
        "calendar",
        "replanning",
        "discipline_score",
        "weighted_score",
        "scoring",
    ):
        assert forbidden not in lowered_code

    assert "get /api/imperium/path/check-ins/{check_in_id}" in lowered_docs
    assert "path check-in detail 10e" in lowered_docs
    assert "read-only" in lowered_docs
    assert "404" in lowered_docs
    assert "non-owned" in lowered_docs
    assert "never modifies any habit or check-in" in lowered_docs


def test_path_stats_summary_10f_is_read_only_user_scoped_and_reports_only_existing_check_ins() -> None:
    route_path = BACKEND_ROOT / "app" / "api" / "v1" / "routes" / "imperium_path.py"
    service_path = BACKEND_ROOT / "app" / "services" / "path" / "habits.py"
    schema_path = BACKEND_ROOT / "app" / "schemas" / "path.py"
    contracts_path = DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md"
    route_text = route_path.read_text(encoding="utf-8")
    service_text = service_path.read_text(encoding="utf-8")
    schema_text = schema_path.read_text(encoding="utf-8")
    contracts_text = contracts_path.read_text(encoding="utf-8")
    lowered_code = "\n".join([route_text, service_text, schema_text]).lower()
    lowered_docs = contracts_text.lower()
    summary_route = route_text.split('@router.get("/stats/summary"', maxsplit=1)[1].split(
        '@router.post("/habits"',
        maxsplit=1,
    )[0]
    summary_service = service_text.split("def get_path_stats_summary", maxsplit=1)[1].split(
        "def get_path_today_view",
        maxsplit=1,
    )[0]

    assert route_text.index('@router.get("/today"') < route_text.index('@router.get("/stats/summary"')
    assert "response_model=PathStatsSummaryResponse" in route_text
    assert "current_user: CurrentUserDep" in summary_route
    assert "Idempotency-Key" not in summary_route
    assert "PathStatsSummaryResponse" in schema_text
    assert "date_from" in schema_text
    assert "date_to" in schema_text
    assert "domain" in schema_text
    assert "frequency" in schema_text
    assert "completion_rate_percent" in schema_text
    assert "safe_explanation" in schema_text
    assert "Path summary stats computed from current user's habits and check-ins." in service_text
    assert "path summary stats computed from current user's habits and check-ins." in lowered_docs
    assert "pending" not in summary_route
    assert "pending" not in summary_service
    assert "db.add(" not in summary_route
    assert "db.flush" not in summary_route
    assert "db.commit" not in summary_route
    assert "db.add(" not in summary_service
    assert "db.flush" not in summary_service
    assert "db.commit" not in summary_service
    assert "ImperiumPathHabit.user_id == current_user.id" in summary_service
    assert "ImperiumPathHabit.is_active.is_(True)" in summary_service
    assert "ImperiumPathCheckIn.user_id == current_user.id" in summary_service
    assert "ImperiumPathCheckIn.habit_id == ImperiumPathHabit.id" in summary_service
    assert "ImperiumPathCheckIn.check_date >= date_from" in summary_service
    assert "ImperiumPathCheckIn.check_date <= date_to" in summary_service
    assert "check_in.status == \"done\"" in summary_service
    assert "check_in.status == \"missed\"" in summary_service

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
        "automatic memory",
        "memory commit",
        "calendar",
        "replanning",
        "calendar replanning",
        "ocr",
        "mission/vault",
        "discipline_score",
        "weighted_score",
        "scoring",
        "automatic scoring",
        "mission",
        "vault",
    ):
        assert forbidden not in lowered_code

    assert "/api/imperium/path/stats/summary" in lowered_docs
    assert "read-only" in lowered_docs
    assert "deterministic" in lowered_docs
    assert "completion rate" in lowered_docs
    assert "pending implicits are excluded" in lowered_docs
    assert "no ai/n8n/scoring/calendar" in lowered_docs
    assert "no pgvector write" in lowered_docs
    assert "no embeddings" in lowered_docs
    assert "no automatic memory commit" in lowered_docs
    assert "no automatic mission/vault linkage" in lowered_docs
    assert "no automatic check-in creation" in lowered_docs
    assert "no automatic replanning" in lowered_docs
    assert "no automatic scoring" in lowered_docs


def test_home_bootstrap_service_has_no_db_write_or_business_service_dependency() -> None:
    service_path = BACKEND_ROOT / "app" / "services" / "imperium" / "home.py"
    service_text = service_path.read_text(encoding="utf-8")
    lowered = service_text.lower()

    assert "db.add(" not in service_text
    assert "db.flush" not in service_text
    assert "db.commit" not in service_text

    for forbidden in (
        "services.imperium.missions",
        "services.imperium.vault",
        "services.path",
        "services.pulse",
        "services.imperium.dashboard",
        "services.imperium.daily_plan",
        "openai",
        "anthropic",
        "gemini",
        "qwen",
        "n8n",
        "ocr",
        "scoring",
        "coaching",
        "recommendation",
    ):
        assert forbidden not in lowered


def test_home_bootstrap_docs_define_metadata_only_and_status_available_not_health_check() -> None:
    contracts_text = (DOCS_ROOT / "04_MVP_BACKEND_CONTRACTS.md").read_text(encoding="utf-8").lower()
    schema_text = (DOCS_ROOT / "05_DATABASE_SCHEMA.md").read_text(encoding="utf-8").lower()

    for text in (contracts_text, schema_text):
        assert "/api/imperium/home/bootstrap" in text
        assert "metadata only" in text
        assert "status available" in text
        assert "not a health check" in text
        assert "no business data read" in text
        assert "primary_endpoint" in text
