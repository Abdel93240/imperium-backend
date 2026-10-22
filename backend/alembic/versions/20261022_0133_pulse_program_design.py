"""pulse: programme d'entraînement conçu par le cerveau (P3, 2026-10-22)

Doc 40 §13.1 mode 1, spec Pulse P3 : l'utilisateur donne objectif, niveau, jours, durée et heure ; le spécialiste
santé propose un programme (semaines, séances types, exercices tirés du matériel possédé), relu par le code, que
l'utilisateur valide. La validation crée le programme, ses cibles hebdomadaires (calculées par le code) et les
séances de toutes ses semaines. `rest_seconds` par exercice reste dans le JSON des séances.

Semés éteints : job `pulse.program_designer`, slots `pulse.program_design` (rôle santé) et
`pulse.program_design_local` ; les routes restent fermées par `pulse.programs_enabled`.

Revision ID: 20261022_0133
Revises: 20261022_0132
Create Date: 2026-10-22
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261022_0133"
down_revision: str | None = "20261022_0132"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
SLOTS = [
    ("pulse.program_design", "cloud_forced",
     "Programme d'entraînement (P3) : semaines, séances types, exercices tirés du matériel possédé — à valider."),
    ("pulse.program_design_local", "local_default",
     "Programme d'entraînement par le modèle local, quand le rôle santé n'est pas disponible."),
]
PARAMETERS = [
    ("pulse.max_weekly_sets_group", "pulse", 25, "séries",
     "Plafond de séries par groupe musculaire et par semaine pour un programme proposé (garde-fou du code)."),
]


def upgrade() -> None:
    op.create_table(
        "pulse_program_requests",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("inputs", postgresql.JSONB(), nullable=False),
        sa.Column("design", postgresql.JSONB(), nullable=True),
        sa.Column("rationale_fr", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("trace", postgresql.JSONB(), nullable=True),
        sa.Column("program_id", UUID, sa.ForeignKey("pulse_programs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('generating', 'proposed', 'accepted', 'rejected', 'failed')", name="status_check"),
        sa.CheckConstraint("source IS NULL OR source IN ('cloud', 'local')", name="source_check"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_pulse_program_requests_user_key"),
    )
    op.create_index("pulse_program_requests_user_created_idx", "pulse_program_requests", ["user_id", "created_at"])
    conn = op.get_bind()
    for code, domain, value, unit, rationale in PARAMETERS:
        conn.exec_driver_sql(
            "INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version) "
            "VALUES (gen_random_uuid(), %s, %s, %s::jsonb, %s, %s, 'seed', 1) "
            "ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING",
            (code, domain, json.dumps(value), unit, rationale))
    for slot, tier, notes in SLOTS:
        conn.exec_driver_sql(
            "INSERT INTO ai_slot_transition (id, slot_code, domain, tier, audit_sample_pct, agreement_target_pct, notes_fr) "
            "VALUES (gen_random_uuid(), %s, 'pulse', %s, 100, 92, %s) "
            "ON CONFLICT ON CONSTRAINT ai_slot_transition_slot_code_unique DO NOTHING", (slot, tier, notes))
    conn.exec_driver_sql(
        "INSERT INTO job_definitions (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s) "
        "VALUES (gen_random_uuid(), 'pulse.program_designer', 'event_subscription', NULL, %s, "
        "'app.services.pulse.program_design:program_designer_job', false, true, 900) "
        "ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING", (["pulse.program.requested"],))


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("DELETE FROM job_definitions WHERE code = 'pulse.program_designer'")
    conn.exec_driver_sql("DELETE FROM ai_slot_transition WHERE slot_code = ANY(%s)", ([s[0] for s in SLOTS],))
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = ANY(%s)", ([p[0] for p in PARAMETERS],))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    op.drop_table("pulse_program_requests")
