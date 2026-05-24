import json
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
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
