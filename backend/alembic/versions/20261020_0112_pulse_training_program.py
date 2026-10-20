"""pulse training program, weekly targets, volume debt, legal moves catalogue (spec Pulse §3.6, §8)

1. `pulse_programs` (+ user_id, nom, clé d'idempotence) : programme saisi à la main (P3 non codée) ; un
   seul programme `active` par utilisateur. Pas de fiche doctrine (corpus absent) : colonne nullable.
2. `pulse_program_targets` : séries cibles par groupe musculaire et semaine (lundi de Paris).
3. `pulse_workouts` ÉTENDUE plutôt que dupliquée en `pulse_sessions` (§0 étape 0) : `program_id`,
   `session_type`, `systemic_load` ; le groupe musculaire vit dans chaque exercice (`exercises[].muscle_group`).
4. `pulse_volume_debt` : séries dues par groupe, née d'un coup accepté (réduction, changement de type),
   remboursée par une séance ; le passage en perte (`written_off`) reste une décision du WR, non codée.
5. `pulse_legal_moves` : les 8 coups du §8 (préconditions, paramètres, effets documentés ; évalués en code).
6. Paramètres `pulse.programs_enabled` false, `pulse.max_debt_sets_group` 10.

Revision ID: 20261020_0112
Revises: 20261020_0111
Create Date: 2026-10-20
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261020_0112"
down_revision: str | None = "20261020_0111"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
SESSION_TYPES = "('strength', 'hypertrophy', 'cardio', 'mobility', 'technique', 'mental')"

# (code, nom, préconditions, schéma des paramètres, effets) — spec Pulse §8.
MOVES = [
    ("maintain", "Garder la séance", {"always": True},
     {"type": "object", "properties": {}}, {"none": True}),
    ("reduce_volume", "Réduire le volume", {"program": True, "percent_range": [40, 90], "debt_max_param": "pulse.max_debt_sets_group"},
     {"type": "object", "required": ["percent"], "properties": {"percent": {"type": "integer", "minimum": 40, "maximum": 90}}},
     {"sets_scaled": "percent", "debt_for_delta": True}),
    ("shift_time", "Décaler dans la journée", {"free_slot": True, "fasting_high_gate_h": 12},
     {"type": "object", "required": ["new_time"], "properties": {"new_time": {"type": "string"}}},
     {"planned_at": "same_day_new_time"}),
    ("reschedule", "Reporter", {"days_ahead_max": 6, "free_day": True, "no_consecutive_load_gte": 7},
     {"type": "object", "required": ["target_date"], "properties": {"target_date": {"type": "string", "format": "date"}}},
     {"planned_at": "target_date_same_time"}),
    ("swap_modality", "Changer de type de séance", {"program": True, "replacement_load_max": 4},
     {"type": "object", "required": ["new_session_type"],
      "properties": {"new_session_type": {"enum": ["technique", "mobility", "cardio"]}}},
     {"session_type": "new_session_type", "systemic_load": 3, "missing_sets_to_debt": True}),
    ("split_session", "Scinder la séance", {"program": True, "two_free_slots": True},
     {"type": "object", "required": ["part1", "part2", "split_ratio"]}, {"split": True}),
    ("repay_debt", "Rembourser la dette", {"program": True, "open_debt_on_session_groups": True, "week_volume_le_target_plus_tolerance": True},
     {"type": "object", "required": ["debt_id"], "properties": {"debt_id": {"type": "string", "format": "uuid"}}},
     {"sets_added": "min(debt, target + tolerance - week_volume)", "debt_status": "scheduled"}),
    ("deload_week", "Semaine allégée", {"program": True, "doctrine_criteria": True},
     {"type": "object", "required": ["percent"], "properties": {"percent": {"type": "integer"}}},
     {"week_sets_scaled": "percent"}),
]

PARAMETERS = [
    ("pulse.programs_enabled", "pulse", False, "bool", "Routes du programme d'entraînement servies."),
    ("pulse.max_debt_sets_group", "pulse", 10, "sets",
     "Dette de volume maximale par groupe musculaire (spec Pulse §15 ; défaut À VALIDER)."),
]


def upgrade() -> None:
    op.create_table(
        "pulse_programs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("objective_weights", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("mesocycle", postgresql.JSONB(), nullable=False),
        sa.Column("doctrine_sheet_code", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_by_run", UUID, sa.ForeignKey("pulse_procedure_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active', 'paused', 'completed', 'superseded')", name="pulse_programs_status_check"),
    )
    op.create_index("pulse_programs_one_active_idx", "pulse_programs", ["user_id"], unique=True,
                    postgresql_where=sa.text("status = 'active'"))
    op.create_index("pulse_programs_user_idempotency_idx", "pulse_programs", ["user_id", "idempotency_key"], unique=True)
    op.create_table(
        "pulse_program_targets",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("program_id", UUID, sa.ForeignKey("pulse_programs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("muscle_group", sa.Text(), nullable=False),
        sa.Column("target_sets", sa.Integer(), nullable=False),
        sa.Column("tolerance_sets", sa.Integer(), nullable=False, server_default="2"),
        sa.UniqueConstraint("program_id", "week_start", "muscle_group", name="pulse_program_targets_unique"),
        sa.CheckConstraint("target_sets >= 0 AND tolerance_sets >= 0", name="pulse_program_targets_positive"),
        sa.CheckConstraint("EXTRACT(ISODOW FROM week_start) = 1", name="pulse_program_targets_monday"),
    )
    op.add_column("pulse_workouts", sa.Column("program_id", UUID, sa.ForeignKey("pulse_programs.id", ondelete="SET NULL"),
                                              nullable=True))
    op.add_column("pulse_workouts", sa.Column("session_type", sa.Text(), nullable=True))
    op.add_column("pulse_workouts", sa.Column("systemic_load", sa.SmallInteger(), nullable=True))
    op.create_check_constraint("session_type_check", "pulse_workouts",
                               f"session_type IS NULL OR session_type IN {SESSION_TYPES}")
    op.create_check_constraint("systemic_load_range", "pulse_workouts",
                               "systemic_load IS NULL OR systemic_load BETWEEN 1 AND 10")
    op.create_table(
        "pulse_volume_debt",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("program_id", UUID, sa.ForeignKey("pulse_programs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("muscle_group", sa.Text(), nullable=False),
        sa.Column("debt_sets", sa.Integer(), nullable=False),
        sa.Column("origin_workout_id", UUID, sa.ForeignKey("pulse_workouts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("repayment_workout_id", UUID, sa.ForeignKey("pulse_workouts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_proposal", UUID, sa.ForeignKey("pulse_proposals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("debt_sets > 0", name="pulse_volume_debt_positive"),
        sa.CheckConstraint("status IN ('open', 'scheduled', 'repaid', 'written_off')", name="pulse_volume_debt_status_check"),
    )
    op.create_index("pulse_volume_debt_user_open_idx", "pulse_volume_debt", ["user_id", "muscle_group"],
                    postgresql_where=sa.text("status IN ('open', 'scheduled')"))
    op.create_table(
        "pulse_legal_moves",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name_fr", sa.Text(), nullable=False),
        sa.Column("preconditions", postgresql.JSONB(), nullable=False),
        sa.Column("parameters_schema", postgresql.JSONB(), nullable=False),
        sa.Column("effects", postgresql.JSONB(), nullable=False),
        sa.Column("doctrine_refs", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    conn = op.get_bind()
    for code, name, pre, schema, effects in MOVES:
        conn.exec_driver_sql(
            """
            INSERT INTO pulse_legal_moves (id, code, name_fr, preconditions, parameters_schema, effects)
            VALUES (gen_random_uuid(), %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
            ON CONFLICT (code) DO NOTHING
            """,
            (code, name, json.dumps(pre), json.dumps(schema), json.dumps(effects)),
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
    op.drop_table("pulse_legal_moves")
    op.drop_table("pulse_volume_debt")
    op.drop_constraint("systemic_load_range", "pulse_workouts", type_="check")
    op.drop_constraint("session_type_check", "pulse_workouts", type_="check")
    op.drop_column("pulse_workouts", "systemic_load")
    op.drop_column("pulse_workouts", "session_type")
    op.drop_column("pulse_workouts", "program_id")
    op.drop_table("pulse_program_targets")
    op.drop_table("pulse_programs")
