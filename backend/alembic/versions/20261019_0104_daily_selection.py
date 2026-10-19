"""daily selection: feasibility attributes, mission dependencies, selection log, flags (spec Daily §3.1-3.3, §5-7, V28)

1. `imperium_missions` étendue (§3.2) : lieu, fenêtre d'exécution, engagement fixe, charges 1-5.
   La durée reste `estimated_minutes` (null → `daily.default_mission_duration`).
2. `mission_dependencies` (§3.1) : aucune arête existante, donc aucun backfill (DAILY_MAPPING §0.2).
   Cycles refusés à l'écriture par le service.
3. `daily_selection_log` (§3.3) + user_id, outcome, condition, scope, pulled_forward.
4. Paramètres semés éteints : `daily.selection_enabled` false (ACT-DLY-04), `daily.pullforward_enabled`
   false (ACT-DLY-06 : la carte corrige le défaut true de la spec), `daily.queue_debug_enabled` false,
   `toolbox.travel_enabled` false (ACT-SYS-08 : aucun appel au fournisseur de trajet sans bascule).

Revision ID: 20261019_0104
Revises: 20261019_0103
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261019_0104"
down_revision: str | None = "20261019_0103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)

PARAMETERS = [
    ("daily.selection_enabled", "daily", False, "bool",
     "Sélection Niveau 1 servie (POST complete/{id} répond la mission suivante) ; carte ACT-DLY-04."),
    ("daily.top_band_pct", "daily", 15, "pct", "Bande de tête du départage par moindre trajet (spec Daily §7, À VALIDER)."),
    ("daily.pullforward_enabled", "daily", False, "bool",
     "Avancer les missions de la semaine quand le jour est bouclé (spec Daily §7) ; carte ACT-DLY-06."),
    ("daily.pullforward_min_threshold", "daily", 45, "min",
     "Temps restant minimal pour avancer une mission de la semaine (spec Daily §7, À VALIDER)."),
    ("daily.default_mission_duration", "daily", 30, "min", "Durée d'une mission sans estimation (spec Daily §3.2, À VALIDER)."),
    ("daily.selection_latency_target_ms", "daily", 500, "ms", "Latence cible du Niveau 1 ; au-delà, journalisé (spec Daily §7)."),
    ("daily.queue_debug_enabled", "daily", False, "bool",
     "GET /api/daily/queue (admin/debug) ; la file reste invisible dans le produit (spec Daily §12)."),
    ("toolbox.travel_enabled", "toolbox", False, "bool",
     "Appel au fournisseur de trajet autorisé (clé requise en plus) ; sinon repli local marqué (carte ACT-SYS-08)."),
]


def upgrade() -> None:
    op.add_column("imperium_missions", sa.Column("location_lat", sa.Numeric(9, 6), nullable=True))
    op.add_column("imperium_missions", sa.Column("location_lng", sa.Numeric(9, 6), nullable=True))
    op.add_column("imperium_missions", sa.Column("location_label", sa.Text(), nullable=True))
    op.add_column("imperium_missions", sa.Column("window_start", sa.Time(), nullable=True))
    op.add_column("imperium_missions", sa.Column("window_end", sa.Time(), nullable=True))
    op.add_column("imperium_missions", sa.Column("window_days", postgresql.ARRAY(sa.Text()), nullable=True))
    op.add_column("imperium_missions", sa.Column("is_fixed_commitment", sa.Boolean(), nullable=False,
                                                 server_default=sa.false()))
    op.add_column("imperium_missions", sa.Column("fixed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("imperium_missions", sa.Column("physical_load", sa.Integer(), nullable=True))
    op.add_column("imperium_missions", sa.Column("cognitive_load", sa.Integer(), nullable=True))
    for name, condition in (
        ("location_pair", "(location_lat IS NULL) = (location_lng IS NULL)"),
        ("location_range", "location_lat IS NULL OR (location_lat BETWEEN -90 AND 90 AND location_lng BETWEEN -180 AND 180)"),
        ("window_order", "window_start IS NULL OR window_end IS NULL OR window_start < window_end"),
        ("window_days_codes", "window_days IS NULL OR window_days <@ ARRAY['mon','tue','wed','thu','fri','sat','sun']::text[]"),
        ("fixed_at_required", "NOT is_fixed_commitment OR fixed_at IS NOT NULL"),
        ("physical_load_range", "physical_load IS NULL OR physical_load BETWEEN 1 AND 5"),
        ("cognitive_load_range", "cognitive_load IS NULL OR cognitive_load BETWEEN 1 AND 5"),
    ):
        op.execute(f"ALTER TABLE imperium_missions ADD CONSTRAINT ck_imperium_missions_{name} CHECK ({condition})")
    op.create_index("imperium_missions_user_fixed_idx", "imperium_missions", ["user_id", "fixed_at"],
                    postgresql_where=sa.text("is_fixed_commitment"))

    op.create_table(
        "mission_dependencies",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("parent_mission_id", UUID, sa.ForeignKey("imperium_missions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("child_mission_id", UUID, sa.ForeignKey("imperium_missions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hard", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("parent_mission_id", "child_mission_id", name="mission_dependencies_pair_unique"),
        sa.CheckConstraint("parent_mission_id <> child_mission_id", name="mission_dependencies_not_self"),
    )
    op.create_index("mission_dependencies_child_idx", "mission_dependencies", ["child_mission_id"])

    op.create_table(
        "daily_selection_log",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("trigger_ref", UUID, nullable=True),
        sa.Column("at_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("remaining_min", sa.Integer(), nullable=False),
        sa.Column("next_fixed_ref", UUID, nullable=True),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("feasible_set", postgresql.JSONB(), nullable=False),
        sa.Column("mandatory_set", postgresql.JSONB(), nullable=False),
        sa.Column("chosen_mission_id", UUID, sa.ForeignKey("imperium_missions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tiebreak_applied", postgresql.JSONB(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("condition", sa.Text(), nullable=True),
        sa.Column("pulled_forward", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("trigger IN ('mission_completed', 'day_start', 'disruption_resolved', 'manual')",
                           name="daily_selection_log_trigger_check"),
        sa.CheckConstraint("scope IN ('day', 'week')", name="daily_selection_log_scope_check"),
        sa.CheckConstraint("outcome IN ('next_mission', 'arbitration_pending', 'day_done')",
                           name="daily_selection_log_outcome_check"),
        sa.CheckConstraint("condition IS NULL OR condition IN ('empty_feasible', 'mandatory_conflict')",
                           name="daily_selection_log_condition_check"),
        sa.CheckConstraint("level IN (1, 2, 3)", name="daily_selection_log_level_check"),
        sa.CheckConstraint("(outcome = 'next_mission') = (chosen_mission_id IS NOT NULL)",
                           name="daily_selection_log_chosen_check"),
        sa.CheckConstraint("jsonb_typeof(feasible_set) = 'array' AND jsonb_typeof(mandatory_set) = 'array'",
                           name="daily_selection_log_sets_array"),
    )
    op.create_index("daily_selection_log_user_at_idx", "daily_selection_log", ["user_id", "at_ts"])

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
    op.drop_table("daily_selection_log")
    op.drop_table("mission_dependencies")
    op.drop_index("imperium_missions_user_fixed_idx", table_name="imperium_missions")
    for name in ("location_pair", "location_range", "window_order", "window_days_codes", "fixed_at_required",
                 "physical_load_range", "cognitive_load_range"):
        op.execute(f"ALTER TABLE imperium_missions DROP CONSTRAINT ck_imperium_missions_{name}")
    for column in ("cognitive_load", "physical_load", "fixed_at", "is_fixed_commitment", "window_days", "window_end",
                   "window_start", "location_label", "location_lng", "location_lat"):
        op.drop_column("imperium_missions", column)
