"""pulse sentinel S1-S7, board snapshots, dispatch log in dry-run (spec Pulse §3.1, §3.2, §5, §6 ; V10 ACT-PLS-10/13/15, V11 ACT-PLS-11/12/14)

1. `pulse_sentinel_rules` : S1-S7 du §5 semées INACTIVES (bascule SQL par code). Les heures des passes
   S4/S5 sont lues à l'heure de Paris (le cron du runner est en UTC).
2. `pulse_board_snapshots` : copie figée du board à chaque réveil, AVANT l'interprète.
3. `pulse_dispatch_log` : un réveil = une ligne `queued`, traitée par `pulse.dispatch_runner` en essai à
   blanc (`model_used='dry_run'`) ; passe programmée sur un board tout vert = `none_needed` / `skipped`
   sans file. `subject_ref` unique par règle (une passe par jour, une séance, un signalement).
4. Jobs `pulse.sentinel_tick` (cron */15) et `pulse.dispatch_runner` (cron */5), semés désactivés.

Revision ID: 20261020_0109
Revises: 20261020_0108
Create Date: 2026-10-20
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261020_0109"
down_revision: str | None = "20261020_0108"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)

# (code, type, config, cooldown, plafond, description) — spec Pulse §5 ; valeurs À VALIDER.
RULES = [
    ("S1_multi_flags", "flag_count", {"min_flags": 2, "min_band": "yellow", "window": "same_day"}, 90, None,
     "Au moins deux signaux frais en jaune ou pire."),
    ("S2_severe_signal", "severity", {"min_band": "orange"}, 60, None,
     "Un signal frais en orange ou rouge (le médical passe d'abord par les règles rouges)."),
    ("S3_user_report", "user_report", {"min_band": "yellow"}, 0, None,
     "Signalement douleur, fatigue, humeur ou stress en jaune ou pire : réveil immédiat."),
    ("S4_scheduled_am", "scheduled", {"cron": "30 7 * * *", "timezone": "Europe/Paris", "grace_minutes": 60},
     None, None, "Passe matinale systématique."),
    ("S5_scheduled_pm", "scheduled", {"cron": "30 18 * * *", "timezone": "Europe/Paris", "grace_minutes": 60},
     None, None, "Passe du soir."),
    ("S6_pre_session", "pre_session", {"lead_minutes": 180}, None, None,
     "Trois heures avant une séance prévue du jour."),
    ("S7_meta_guard", "meta", {"max_dispatch_per_day": 6, "dedup_window_min": 90}, None, 6,
     "Garde-fou global : plafond journalier et dédup des mêmes drapeaux."),
]

JOBS = [
    ("pulse.sentinel_tick", "*/15 * * * *", "app.services.pulse.sentinel:tick_job"),
    ("pulse.dispatch_runner", "*/5 * * * *", "app.services.pulse.sentinel:dispatch_job"),
]


def upgrade() -> None:
    op.create_table(
        "pulse_sentinel_rules",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("rule_type", sa.Text(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=True),
        sa.Column("max_dispatch_per_day", sa.Integer(), nullable=True),
        sa.Column("description_fr", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint("rule_type IN ('flag_count', 'severity', 'user_report', 'scheduled', 'pre_session', 'meta')",
                           name="pulse_sentinel_rules_type_check"),
        sa.CheckConstraint("cooldown_minutes IS NULL OR cooldown_minutes >= 0",
                           name="pulse_sentinel_rules_cooldown_check"),
    )
    op.create_table(
        "pulse_board_snapshots",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("board", postgresql.JSONB(), nullable=False),
        sa.Column("flags_count", sa.Integer(), nullable=False),
        sa.Column("max_severity", sa.Text(), nullable=False),
        sa.CheckConstraint("max_severity IN ('green', 'yellow', 'orange', 'red')",
                           name="pulse_board_snapshots_severity_check"),
    )
    op.create_index("pulse_board_snapshots_user_taken_idx", "pulse_board_snapshots", ["user_id", "taken_at"])
    op.create_table(
        "pulse_dispatch_log",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("triggered_by", sa.Text(), nullable=False),
        sa.Column("subject_ref", sa.Text(), nullable=True),
        sa.Column("board_snapshot_id", UUID, sa.ForeignKey("pulse_board_snapshots.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("flag_set", postgresql.JSONB(), nullable=False),
        sa.Column("trigger_event_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("model_used", sa.Text(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("output", postgresql.JSONB(), nullable=True),
        sa.Column("valid", sa.Boolean(), nullable=True),
        sa.Column("escalated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("procedures_named", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("user_reaction", sa.Text(), nullable=True),
        sa.Column("reacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('queued', 'done')", name="pulse_dispatch_log_status_check"),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('none_needed', 'dry_run', 'procedures_run', 'invalid_fallback', 'escalated')",
            name="pulse_dispatch_log_outcome_check"),
        sa.CheckConstraint("(status = 'done') = (outcome IS NOT NULL AND model_used IS NOT NULL AND valid IS NOT NULL)",
                           name="pulse_dispatch_log_done_check"),
        sa.CheckConstraint("user_reaction IS NULL OR user_reaction IN ('useful', 'useless', 'missed')",
                           name="pulse_dispatch_log_reaction_check"),
        sa.CheckConstraint("(user_reaction IS NULL) = (reacted_at IS NULL)", name="pulse_dispatch_log_reacted_check"),
    )
    op.create_index("pulse_dispatch_log_user_created_idx", "pulse_dispatch_log", ["user_id", "created_at"])
    op.create_index("pulse_dispatch_log_subject_idx", "pulse_dispatch_log", ["user_id", "triggered_by", "subject_ref"],
                    unique=True, postgresql_where=sa.text("subject_ref IS NOT NULL"))
    op.create_index("pulse_dispatch_log_queued_idx", "pulse_dispatch_log", ["created_at"],
                    postgresql_where=sa.text("status = 'queued'"))
    conn = op.get_bind()
    for code, rule_type, config, cooldown, cap, description in RULES:
        conn.exec_driver_sql(
            """
            INSERT INTO pulse_sentinel_rules
              (id, code, rule_type, config, cooldown_minutes, max_dispatch_per_day, description_fr, version, active)
            VALUES (gen_random_uuid(), %s, %s, %s::jsonb, %s, %s, %s, 1, false)
            ON CONFLICT (code) DO NOTHING
            """,
            (code, rule_type, json.dumps(config), cooldown, cap, description),
        )
    for code, schedule, handler in JOBS:
        conn.exec_driver_sql(
            """
            INSERT INTO job_definitions
              (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
            VALUES (gen_random_uuid(), %s, 'cron', %s, NULL, %s, false, true, 120)
            ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
            """,
            (code, schedule, handler),
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("DELETE FROM job_definitions WHERE code = ANY(%s)", ([job[0] for job in JOBS],))
    op.drop_table("pulse_dispatch_log")
    op.drop_table("pulse_board_snapshots")
    op.drop_table("pulse_sentinel_rules")
