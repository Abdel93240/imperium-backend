"""pulse: le cerveau qui revient seul (bloc 2, 2026-10-22)

- `pulse_programs.hydration_target` : fourchette d'eau personnalisée (min / bien / très bien, en ml) donnée par le
  spécialiste santé avec le programme (doc 40 §12), affichée sur l'accueil ; vide tant qu'aucun programme ne la donne.
- `pulse_program_requests.kind` : `create` (demande de l'utilisateur) ou `revision` (révision toutes les 4 semaines,
  doc 40 §13-REVISION, spec P7).
- Job `pulse.daily_cycle` (6 h de Paris, semé éteint) : le mardi (jour de la Weekly Review, décision utilisateur
  2026-10-22) prépare 7 jours de repas et dépose dans la revue ce qui mérite d'en parler (courses jamais achetées,
  séances non suivies) ; chaque jour, révision du programme quand elle est due, règles médicales proposées après
  une prise de sang validée.
- Slots `pulse.lab_rules` (rôle santé) et `pulse.lab_rules_local`, semés éteints.

Revision ID: 20261022_0136
Revises: 20261022_0135
Create Date: 2026-10-22
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261022_0136"
down_revision: str | None = "20261022_0135"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARAMETERS = [
    ("pulse.diet_auto_weekday", "pulse", "TU", None,
     "Jour où le cerveau prépare 7 jours de repas (le mardi, avec la Weekly Review — décision utilisateur 2026-10-22)."),
    ("pulse.program_revision_days", "pulse", 28, "jours",
     "Révision du programme d'entraînement par le spécialiste santé après ce nombre de jours (doc 40 §13-REVISION)."),
]
SLOTS = [
    ("pulse.lab_rules", "cloud_forced",
     "Règles médicales proposées après une prise de sang validée (valeurs hors norme du labo), à activer par l'utilisateur."),
    ("pulse.lab_rules_local", "local_default",
     "Règles médicales proposées par le modèle local, quand le rôle santé n'est pas disponible."),
]


def upgrade() -> None:
    op.add_column("pulse_programs", sa.Column("hydration_target", postgresql.JSONB(), nullable=True))
    op.add_column("pulse_program_requests", sa.Column("kind", sa.Text(), nullable=False, server_default="create"))
    op.create_check_constraint("kind_check", "pulse_program_requests", "kind IN ('create', 'revision')")
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
        "VALUES (gen_random_uuid(), 'pulse.daily_cycle', 'cron', '0 4,5 * * *', NULL, "
        "'app.services.pulse.cycle:daily_cycle_job', false, true, 600) "
        "ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING")


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("DELETE FROM job_definitions WHERE code = 'pulse.daily_cycle'")
    conn.exec_driver_sql("DELETE FROM ai_slot_transition WHERE slot_code = ANY(%s)", ([s[0] for s in SLOTS],))
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = ANY(%s)", ([p[0] for p in PARAMETERS],))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    op.drop_constraint("kind_check", "pulse_program_requests", type_="check")
    op.drop_column("pulse_program_requests", "kind")
    op.drop_column("pulse_programs", "hydration_target")
