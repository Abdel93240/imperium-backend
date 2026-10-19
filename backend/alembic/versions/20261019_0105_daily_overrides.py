"""daily overrides: captured choices against the proposal, weekly aggregation into the docket (spec Daily §3.4, §10.1-10.2, V29)

1. `daily_overrides` (§3.4) + user_id : l'utilisateur prend une autre mission que la proposée,
   raison obligatoire (CHECK non vide), contexte figé. Une seule par sélection.
2. Docket : type `ordering_override_pattern` et worker `w5` ajoutés aux CHECK (§10.2 : W5 dépose
   l'item). Le type n'entre PAS dans l'auto-acceptation : le réglage reste un acte utilisateur.
3. Job `daily.override_aggregation` (cron dimanche 17:00 UTC) semé désactivé.
4. Paramètres : `daily.override_enabled` false (ACT-DLY-07), `daily.override_pattern_min` 3 et
   `daily.override_window_days` 28 (spec §10.2, À VALIDER).

Revision ID: 20261019_0105
Revises: 20261019_0104
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261019_0105"
down_revision: str | None = "20261019_0104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)

ITEM_TYPES = (
    "chain_proposal", "pattern_new", "pattern_contradiction", "anomaly", "belief_review_due",
    "user_question", "plan_delta_proposal", "autoaccept_spotcheck", "investigation_result", "red_flag_ref",
)
SOURCE_WORKERS = ("w1", "w2", "w3", "w4", "phase1", "phase3", "manual")
ITEM_CHECK = "ck_wr_docket_items_wr_docket_items_item_type_check"
WORKER_CHECK = "ck_wr_docket_items_wr_docket_items_source_worker_check"

PARAMETERS = [
    ("daily.override_enabled", "daily", False, "bool",
     "Capture des overrides (POST /api/daily/override, raison obligatoire) ; carte ACT-DLY-07."),
    ("daily.override_pattern_min", "daily", 3, "count",
     "Overrides d'un même motif qui déposent un item au docket (spec Daily §10.2, À VALIDER)."),
    ("daily.override_window_days", "daily", 28, "days", "Fenêtre de l'agrégation des overrides (spec Daily §10.2, À VALIDER)."),
]


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _replace_check(name: str, condition: str) -> None:
    op.execute(f"ALTER TABLE wr_docket_items DROP CONSTRAINT {name}")
    op.execute(f"ALTER TABLE wr_docket_items ADD CONSTRAINT {name} CHECK ({condition})")


def upgrade() -> None:
    op.create_table(
        "daily_overrides",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("selection_log_id", UUID, sa.ForeignKey("daily_selection_log.id"), nullable=False),
        sa.Column("proposed_mission_id", UUID, sa.ForeignKey("imperium_missions.id"), nullable=False),
        sa.Column("chosen_mission_id", UUID, sa.ForeignKey("imperium_missions.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("context", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("selection_log_id", name="daily_overrides_selection_unique"),
        sa.CheckConstraint("char_length(btrim(reason)) > 0", name="daily_overrides_reason_check"),
        sa.CheckConstraint("proposed_mission_id <> chosen_mission_id", name="daily_overrides_distinct_check"),
        sa.CheckConstraint("jsonb_typeof(context) = 'object'", name="daily_overrides_context_object"),
    )
    op.create_index("daily_overrides_user_created_idx", "daily_overrides", ["user_id", "created_at"])
    _replace_check(ITEM_CHECK, _in("item_type", (*ITEM_TYPES, "ordering_override_pattern")))
    _replace_check(WORKER_CHECK, _in("source_worker", (*SOURCE_WORKERS, "w5")))
    op.execute(
        """
        INSERT INTO job_definitions
          (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
        VALUES
          (gen_random_uuid(), 'daily.override_aggregation', 'cron', '0 17 * * 0', NULL,
           'app.services.daily.overrides:aggregation_job', false, true, 300)
        ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
        """
    )
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


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = ANY(%s)", ([p[0] for p in PARAMETERS],))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    op.execute("DELETE FROM job_definitions WHERE code = 'daily.override_aggregation'")
    # Échoue si un item ordering_override_pattern existe déjà (attendu : le docket ne se supprime pas).
    _replace_check(WORKER_CHECK, _in("source_worker", SOURCE_WORKERS))
    _replace_check(ITEM_CHECK, _in("item_type", ITEM_TYPES))
    op.drop_table("daily_overrides")
