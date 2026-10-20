"""pulse signals engine (non-device families), subjective reports, board (spec Pulse §3.1, §4, §14 ; V7 ACT-PLS-08, V8 ACT-PLS-05/03/04/07 partiels)

1. Signaux `pulse.*` semés INACTIFS dans la table partagée `signal_definitions` (doc 78 F2-13 : ni
   `pulse_signal_definitions` ni `pulse_signal_values`) ; seuls ceux calculables sans montre ni
   cible personnalisée : douleur, fatigue, humeur, stress, heures depuis le dernier repas, assiduité
   entraînement 7 j, charge de travail planifiée du jour. Bandes et fraîcheur (minutes) dans `bands`.
2. `pulse_subjective_reports` : fatigue | mood | stress, niveau 1 (bien) → 5 (mal), suppression réelle.
3. Job `pulse.signals_refresh` (cron */15, semé désactivé).
4. Paramètres `pulse.board_enabled` false (ACT-PLS-08), `pulse.reports_enabled` false (ACT-PLS-05).

Revision ID: 20261020_0108
Revises: 20261019_0107
Create Date: 2026-10-20
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261020_0108"
down_revision: str | None = "20261019_0107"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)

# (code, libellé, unité, source, bandes) — spec Pulse §4 ; bandes À VALIDER.
SIGNALS = [
    ("pulse.pain_active", "Douleur en cours (sévérité max)", "score_0_10", "user_event:pulse_pain_logs",
     {"kind": "high", "yellow": 1, "orange": 4, "red": 8, "freshness_minutes": 30}),
    ("pulse.fatigue_reported", "Fatigue déclarée du jour", "level_1_5", "user_event:pulse_subjective_reports",
     {"kind": "high", "yellow": 3, "orange": 4, "red": 5, "freshness_minutes": 30}),
    ("pulse.mood_reported", "Humeur déclarée du jour (1 bien → 5 mal)", "level_1_5", "user_event:pulse_subjective_reports",
     {"kind": "high", "yellow": 3, "orange": 4, "red": 5, "freshness_minutes": 30}),
    ("pulse.stress_reported", "Stress déclaré du jour", "level_1_5", "user_event:pulse_subjective_reports",
     {"kind": "high", "yellow": 3, "orange": 4, "red": 5, "freshness_minutes": 30}),
    ("pulse.last_meal_hours", "Heures depuis le dernier repas", "h", "computed:pulse_meals",
     {"kind": "high", "orange": 18, "freshness_minutes": 30, "fasting_neutral": True}),
    ("pulse.training_adherence_7d", "Séances faites / prévues (7 j)", "ratio", "computed:pulse_workouts",
     {"kind": "low", "green": 0.8, "yellow": 0.6, "floor": "orange", "freshness_minutes": 1440}),
    ("pulse.workload_today_h", "Heures de missions prévues aujourd'hui", "h", "cross_domain_read:imperium_missions",
     {"kind": "info", "freshness_minutes": 120}),
]

PARAMETERS = [
    ("pulse.board_enabled", "pulse", False, "bool", "Route GET board servie (carte ACT-PLS-08)."),
    ("pulse.reports_enabled", "pulse", False, "bool", "Route POST reports servie (carte ACT-PLS-05)."),
]


def upgrade() -> None:
    op.create_table(
        "pulse_subjective_reports",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("kind IN ('fatigue', 'mood', 'stress')", name="pulse_subjective_reports_kind_check"),
        sa.CheckConstraint("level BETWEEN 1 AND 5", name="pulse_subjective_reports_level_range"),
    )
    op.create_index("pulse_subjective_reports_user_reported_idx", "pulse_subjective_reports", ["user_id", "reported_at"])
    op.create_index("pulse_subjective_reports_user_idempotency_idx", "pulse_subjective_reports",
                    ["user_id", "idempotency_key"], unique=True)
    conn = op.get_bind()
    for code, label, unit, source, bands in SIGNALS:
        conn.exec_driver_sql(
            """
            INSERT INTO signal_definitions
              (id, domain, code, label_fr, unit, source, aggregation, bands, staleness_hours, active)
            VALUES (gen_random_uuid(), 'pulse', %s, %s, %s, %s, 'latest', %s::jsonb, %s, false)
            ON CONFLICT ON CONSTRAINT signal_definitions_code_unique DO NOTHING
            """,
            (code, label, unit, source, json.dumps(bands), max(1, bands["freshness_minutes"] // 60)),
        )
    op.execute(
        """
        INSERT INTO job_definitions
          (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
        VALUES
          (gen_random_uuid(), 'pulse.signals_refresh', 'cron', '*/15 * * * *', NULL,
           'app.services.pulse.signals:refresh_job', false, true, 120)
        ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
        """
    )
    for code, domain, value, unit, rationale in PARAMETERS:
        conn.exec_driver_sql(
            """
            INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version)
            VALUES (gen_random_uuid(), %s, %s, %s::jsonb, %s, %s, 'seed', 1)
            ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING
            """,
            (code, domain, json.dumps(value), unit, rationale),
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = ANY(%s)", ([p[0] for p in PARAMETERS],))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    op.execute("DELETE FROM job_definitions WHERE code = 'pulse.signals_refresh'")
    codes = [signal[0] for signal in SIGNALS]
    conn.exec_driver_sql("DELETE FROM signal_values WHERE signal_code = ANY(%s)", (codes,))
    conn.exec_driver_sql("DELETE FROM signal_definitions WHERE code = ANY(%s)", (codes,))
    op.drop_table("pulse_subjective_reports")
