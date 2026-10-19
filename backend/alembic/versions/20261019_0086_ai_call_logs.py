"""ai call logs: central AI call log, pricing grid, cost trigger and analysis views (doc 43 §17 ; doc 78 F2-14)

Chaque appel de modèle est journalisé (origine, modèle réellement utilisé, tokens, coût, durée,
issue) — jamais le prompt ni la réponse. La grille `ai_model_pricing` naît VIDE : le seed
historique du doc 43 §17.2 est périmé (DV-8) ; sans prix connu, le coût d'un appel cloud reste
NULL (inconnu), un appel local coûte 0.

Revision ID: 20261019_0086
Revises: 20261019_0085
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261019_0086"
down_revision: str | None = "20261019_0085"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VIEWS = {
    "ai_monthly_by_model": """
        SELECT DATE_TRUNC('month', called_at)::DATE AS month, model_used, model_tier,
               COUNT(*) AS call_count, SUM(input_tokens) AS total_input_tokens,
               SUM(output_tokens) AS total_output_tokens, SUM(total_tokens) AS total_tokens,
               ROUND(SUM(cost_eur), 4) AS total_cost_eur, ROUND(AVG(cost_eur), 6) AS avg_cost_per_call,
               ROUND(AVG(duration_ms)) AS avg_duration_ms,
               COUNT(*) FILTER (WHERE success = FALSE) AS error_count,
               COUNT(*) FILTER (WHERE fallback_used) AS fallback_count,
               ROUND(100.0 * COUNT(*) FILTER (WHERE was_validated = FALSE)
                     / NULLIF(COUNT(*) FILTER (WHERE was_validated IS NOT NULL), 0), 1) AS hallucination_pct
        FROM ai_call_logs GROUP BY 1, 2, 3
    """,
    "ai_monthly_by_app": """
        SELECT DATE_TRUNC('month', called_at)::DATE AS month, app_name, COUNT(*) AS call_count,
               ROUND(SUM(cost_eur), 4) AS total_cost_eur, ROUND(AVG(cost_eur) * 1000, 4) AS avg_cost_meur,
               COUNT(*) FILTER (WHERE success = FALSE) AS error_count,
               ROUND(100.0 * COUNT(*) FILTER (WHERE was_validated = FALSE)
                     / NULLIF(COUNT(*) FILTER (WHERE was_validated IS NOT NULL), 0), 1) AS hallucination_pct
        FROM ai_call_logs GROUP BY 1, 2
    """,
    "ai_monthly_by_task": """
        SELECT DATE_TRUNC('month', called_at)::DATE AS month, app_name, task_type, model_used,
               COUNT(*) AS call_count, ROUND(SUM(cost_eur), 4) AS total_cost_eur,
               ROUND(AVG(duration_ms)) AS avg_duration_ms,
               COUNT(*) FILTER (WHERE success = FALSE) AS error_count
        FROM ai_call_logs GROUP BY 1, 2, 3, 4
    """,
    "ai_daily_spend": """
        SELECT (called_at AT TIME ZONE 'Europe/Paris')::DATE AS day, COUNT(*) AS total_calls,
               COUNT(*) FILTER (WHERE model_tier = 'local') AS local_calls,
               COUNT(*) FILTER (WHERE model_tier = 'cloud_cheap') AS cheap_calls,
               COUNT(*) FILTER (WHERE model_tier = 'cloud_standard') AS standard_calls,
               COUNT(*) FILTER (WHERE model_tier = 'cloud_premium') AS premium_calls,
               ROUND(SUM(cost_eur), 4) AS total_cost_eur,
               ROUND(SUM(cost_eur) FILTER (WHERE model_tier = 'cloud_premium'), 4) AS premium_cost_eur,
               COUNT(*) FILTER (WHERE success = FALSE) AS errors
        FROM ai_call_logs GROUP BY 1
    """,
}


def upgrade() -> None:
    op.create_table(
        "ai_model_pricing",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("model_slug", sa.String(48), nullable=False, unique=True),
        sa.Column("input_cost_per_1m", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("output_cost_per_1m", sa.Numeric(10, 4), nullable=False, server_default="0"),
        sa.Column("is_local", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("valid_from", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_table(
        "ai_call_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("app_name", sa.String(32), nullable=False),
        sa.Column("task_type", sa.String(64), nullable=False),
        sa.Column("trigger_source", sa.String(64), nullable=True),
        sa.Column("model_used", sa.String(48), nullable=False),
        sa.Column("model_tier", sa.String(16), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(),
                  sa.Computed("COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)", persisted=True)),
        sa.Column("cost_eur", sa.Numeric(10, 6), nullable=True),
        sa.Column("was_validated", sa.Boolean(), nullable=True),
        sa.Column("validation_method", sa.String(32), nullable=True),
        sa.Column("quality_notes", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("queue_wait_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("original_model", sa.String(48), nullable=True),
        sa.Column("context_tokens_sent", sa.Integer(), nullable=True),
        sa.Column("related_entity_type", sa.String(32), nullable=True),
        sa.Column("related_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("parent_call_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_call_logs.id"), nullable=True),
        sa.CheckConstraint("app_name IN ('imperium', 'vector', 'vault', 'pulse', 'path')", name="ai_call_logs_app_check"),
        sa.CheckConstraint("model_tier IN ('local', 'cloud_cheap', 'cloud_standard', 'cloud_premium')",
                           name="ai_call_logs_tier_check"),
    )
    op.execute("CREATE INDEX ai_call_logs_time_idx ON ai_call_logs (called_at DESC)")
    op.execute("CREATE INDEX ai_call_logs_app_task_idx ON ai_call_logs (app_name, task_type, called_at DESC)")
    op.execute("CREATE INDEX ai_call_logs_model_idx ON ai_call_logs (model_used, called_at DESC)")
    op.execute("CREATE INDEX ai_call_logs_cost_idx ON ai_call_logs (cost_eur DESC, called_at DESC) WHERE cost_eur IS NOT NULL")
    op.execute("CREATE INDEX ai_call_logs_errors_idx ON ai_call_logs (called_at DESC) WHERE success = FALSE")
    op.execute("CREATE INDEX ai_call_logs_hallucinations_idx ON ai_call_logs (called_at DESC) WHERE was_validated = FALSE")
    op.execute("CREATE INDEX ai_call_logs_related_idx ON ai_call_logs (related_entity_type, related_entity_id) "
               "WHERE related_entity_id IS NOT NULL")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION compute_ai_call_cost(p_model_slug VARCHAR, p_input_tokens INTEGER,
                                                        p_output_tokens INTEGER)
        RETURNS NUMERIC(10, 6) AS $$
          SELECT ROUND((p_input_tokens::NUMERIC / 1000000 * input_cost_per_1m)
                       + (p_output_tokens::NUMERIC / 1000000 * output_cost_per_1m), 6)
          FROM ai_model_pricing
          WHERE model_slug = p_model_slug AND valid_from <= CURRENT_DATE
            AND (valid_until IS NULL OR valid_until >= CURRENT_DATE)
          LIMIT 1;
        $$ LANGUAGE SQL STABLE;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION ai_call_logs_compute_cost() RETURNS TRIGGER AS $$
        BEGIN
          IF NEW.cost_eur IS NULL AND NEW.input_tokens IS NOT NULL AND NEW.output_tokens IS NOT NULL THEN
            NEW.cost_eur := compute_ai_call_cost(NEW.model_used, NEW.input_tokens, NEW.output_tokens);
          END IF;
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        "CREATE TRIGGER ai_call_logs_auto_cost BEFORE INSERT ON ai_call_logs "
        "FOR EACH ROW EXECUTE FUNCTION ai_call_logs_compute_cost()"
    )
    for name, body in VIEWS.items():
        op.execute(f"CREATE VIEW {name} AS {body}")


def downgrade() -> None:
    for name in reversed(list(VIEWS)):
        op.execute(f"DROP VIEW IF EXISTS {name}")
    op.execute("DROP TRIGGER IF EXISTS ai_call_logs_auto_cost ON ai_call_logs")
    op.execute("DROP FUNCTION IF EXISTS ai_call_logs_compute_cost()")
    op.execute("DROP FUNCTION IF EXISTS compute_ai_call_cost(VARCHAR, INTEGER, INTEGER)")
    op.drop_table("ai_call_logs")
    op.drop_table("ai_model_pricing")
