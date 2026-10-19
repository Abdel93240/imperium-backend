"""ai call alerts: remaining analysis views, alert thresholds and disabled hourly job (doc 43 §17.4, §17.6)

Vues 5 à 10 du doc 43 §17.4 ; seuils du §17.6 en paramètres versionnés (défauts du doc,
À VALIDER) ; job `ai.call_alerts` (horaire, semé désactivé) qui notifie au plus une fois par
jour et par seuil via notify().

Revision ID: 20261019_0087
Revises: 20261019_0086
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence

from alembic import op

revision: str = "20261019_0087"
down_revision: str | None = "20261019_0086"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARAMETERS = [
    ("ai.alert_daily_spend_eur", "ai", 1.5, "EUR", "Dépense IA du jour au-delà de laquelle alerter (doc 43 §17.6)."),
    ("ai.alert_weekly_spend_eur", "ai", 7, "EUR", "Dépense IA sur 7 jours glissants au-delà de laquelle alerter (doc 43 §17.6)."),
    ("ai.alert_error_rate_pct", "ai", 5, "%", "Taux d'erreur des appels IA sur 24 h (doc 43 §17.6)."),
    ("ai.alert_error_min_calls", "ai", 20, "count",
     "Appels minimum sur 24 h avant de juger le taux d'erreur (ajout, À VALIDER)."),
    ("ai.alert_hallucination_pct", "ai", 15, "%",
     "Taux d'erreurs validées du modèle local par type de tâche, 30 jours (doc 43 §17.6)."),
    ("ai.alert_hallucination_min_checked", "ai", 10, "count",
     "Appels vérifiés minimum par type de tâche (doc 43 §17.5 : HAVING > 10)."),
    ("ai.alert_single_call_eur", "ai", 0.5, "EUR", "Coût d'un appel seul sur 24 h (doc 43 §17.6)."),
    ("ai.alert_p90_latency_ms", "ai", 30000, "ms", "p90 de latence par type de tâche, 30 jours (doc 43 §17.6)."),
    ("ai.alert_fallbacks_per_hour", "ai", 3, "count", "Repli sur un autre modèle dans la dernière heure (doc 43 §17.6)."),
]

VIEWS = {
    "ai_hallucination_tracker": """
        SELECT DATE_TRUNC('month', called_at)::DATE AS month, app_name, task_type, model_used,
               COUNT(*) FILTER (WHERE was_validated IS NOT NULL) AS validated_calls,
               COUNT(*) FILTER (WHERE was_validated = TRUE) AS correct_calls,
               COUNT(*) FILTER (WHERE was_validated = FALSE) AS wrong_calls,
               ROUND(100.0 * COUNT(*) FILTER (WHERE was_validated = FALSE)
                     / NULLIF(COUNT(*) FILTER (WHERE was_validated IS NOT NULL), 0), 1) AS error_rate_pct
        FROM ai_call_logs WHERE was_validated IS NOT NULL GROUP BY 1, 2, 3, 4
    """,
    "ai_error_analysis": """
        SELECT DATE_TRUNC('month', called_at)::DATE AS month, model_used, task_type, error_code,
               COUNT(*) AS error_count, ROUND(AVG(retry_attempt), 2) AS avg_retry_count,
               COUNT(*) FILTER (WHERE fallback_used) AS fallbacks_triggered
        FROM ai_call_logs WHERE success = FALSE GROUP BY 1, 2, 3, 4
    """,
    "ai_latency_profile": """
        SELECT task_type, model_used, COUNT(*) AS call_count, ROUND(MIN(duration_ms)) AS min_ms,
               ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY duration_ms)) AS p50_ms,
               ROUND(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY duration_ms)) AS p90_ms,
               ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY duration_ms)) AS p99_ms,
               ROUND(MAX(duration_ms)) AS max_ms
        FROM ai_call_logs
        WHERE duration_ms IS NOT NULL AND called_at > NOW() - INTERVAL '30 days'
        GROUP BY 1, 2
    """,
    "ai_6month_trend": """
        SELECT DATE_TRUNC('month', called_at)::DATE AS month, COUNT(*) AS total_calls,
               ROUND(SUM(cost_eur), 2) AS total_cost_eur,
               COUNT(DISTINCT related_entity_id) AS unique_entities_impacted,
               ROUND(100.0 * COUNT(*) FILTER (WHERE model_tier = 'local') / COUNT(*), 1) AS local_pct,
               ROUND(100.0 * COUNT(*) FILTER (WHERE success = FALSE) / COUNT(*), 2) AS error_rate_pct
        FROM ai_call_logs WHERE called_at > NOW() - INTERVAL '6 months' GROUP BY 1
    """,
    "ai_fallback_effectiveness": """
        SELECT original_model, model_used AS fallback_model, COUNT(*) AS fallback_count,
               COUNT(*) FILTER (WHERE success = TRUE) AS fallback_success,
               COUNT(*) FILTER (WHERE success = FALSE) AS fallback_also_failed,
               ROUND(100.0 * COUNT(*) FILTER (WHERE success = TRUE) / COUNT(*), 1) AS success_rate_pct,
               ROUND(AVG(cost_eur), 5) AS avg_cost_eur
        FROM ai_call_logs WHERE fallback_used = TRUE GROUP BY 1, 2
    """,
    "ai_vs_estimates": """
        SELECT DATE_TRUNC('month', called_at)::DATE AS month, ROUND(SUM(cost_eur), 2) AS actual_cost_eur,
               12.00 AS doc_estimate_low_eur, 14.00 AS doc_estimate_high_eur,
               ROUND(SUM(cost_eur) - 12.00, 2) AS vs_low_estimate,
               ROUND(SUM(cost_eur) - 14.00, 2) AS vs_high_estimate
        FROM ai_call_logs GROUP BY 1
    """,
}


def upgrade() -> None:
    for name, body in VIEWS.items():
        op.execute(f"CREATE VIEW {name} AS {body}")
    conn = op.get_bind()
    for code, domain, value, unit, rationale in PARAMETERS:
        conn.exec_driver_sql(
            """
            INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version)
            VALUES (gen_random_uuid(), %s, %s, %s::jsonb, %s, %s, 'seed', 1)
            ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING
            """,
            (code, domain, json.dumps(value), unit, rationale),
        )
    op.execute(
        """
        INSERT INTO job_definitions
          (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
        VALUES (gen_random_uuid(), 'ai.call_alerts', 'cron', '5 * * * *', NULL,
                'app.services.ai.call_alerts:ai_call_alerts_job', false, true, 120)
        ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM job_definitions WHERE code = 'ai.call_alerts'")
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = ANY(%s)", ([p[0] for p in PARAMETERS],))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    for name in reversed(list(VIEWS)):
        op.execute(f"DROP VIEW IF EXISTS {name}")
