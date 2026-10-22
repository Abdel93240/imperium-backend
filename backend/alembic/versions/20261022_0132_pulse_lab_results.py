"""pulse: analyses de sang (2026-10-22) — valeurs validées venues de Nourrir l'IA

Une prise de sang déposée dans Nourrir l'IA est reconnue à l'analyse ; ses valeurs (nom, résultat, unité, norme du
labo, date) sont proposées dans le brouillon, corrigées puis validées par l'utilisateur vers la destination
`lab_results` (accord « medical » exigé) : elles entrent alors dans `pulse_lab_results`, jamais dans la mémoire
vectorisée. Santé affiche la dernière valeur de chaque analyse ; inconnu reste inconnu.

Lecture des valeurs : slots `pulse.lab_results_extract` (rôle santé) et `pulse.lab_results_extract_local`, semés
éteints ; sans eux l'utilisateur saisit les valeurs dans la même fenêtre.

Revision ID: 20261022_0132
Revises: 20261022_0131
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261022_0132"
down_revision: str | None = "20261022_0131"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
SLOTS = [
    ("pulse.lab_results_extract", "cloud_forced",
     "Valeurs d'une prise de sang (texte lu par l'OCR) : nom, résultat, unité, norme du labo — à valider."),
    ("pulse.lab_results_extract_local", "local_default",
     "Valeurs d'une prise de sang par le modèle local, quand le rôle santé n'est pas disponible."),
]


def upgrade() -> None:
    op.create_table(
        "pulse_lab_results",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("inbox_item_id", UUID, sa.ForeignKey("knowledge_inbox_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("analyte", sa.Text(), nullable=False),
        sa.Column("analyte_key", sa.Text(), nullable=False),
        sa.Column("value", sa.Numeric(14, 4), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("ref_low", sa.Numeric(14, 4), nullable=True),
        sa.Column("ref_high", sa.Numeric(14, 4), nullable=True),
        sa.Column("ref_text", sa.Text(), nullable=True),
        sa.Column("measured_on", sa.Date(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("value IS NOT NULL OR value_text IS NOT NULL", name="has_value"),
        sa.CheckConstraint("source IN ('inbox', 'manual')", name="source_check"),
        sa.CheckConstraint("length(btrim(analyte)) > 0", name="analyte_not_blank"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_pulse_lab_results_user_key"),
    )
    op.create_index("pulse_lab_results_user_key_idx", "pulse_lab_results", ["user_id", "analyte_key", "measured_on"])
    op.drop_constraint("destination_check", "knowledge_inbox_items", type_="check")
    op.create_check_constraint("destination_check", "knowledge_inbox_items",
                               "destination IS NULL OR destination IN ('memory', 'project', 'lab_results')")
    conn = op.get_bind()
    for slot, tier, notes in SLOTS:
        conn.exec_driver_sql(
            "INSERT INTO ai_slot_transition (id, slot_code, domain, tier, audit_sample_pct, agreement_target_pct, notes_fr) "
            "VALUES (gen_random_uuid(), %s, 'pulse', %s, 100, 92, %s) "
            "ON CONFLICT ON CONSTRAINT ai_slot_transition_slot_code_unique DO NOTHING", (slot, tier, notes))


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("DELETE FROM ai_slot_transition WHERE slot_code = ANY(%s)", ([s[0] for s in SLOTS],))
    op.execute("UPDATE knowledge_inbox_items SET destination = NULL WHERE destination = 'lab_results'")
    op.drop_constraint("destination_check", "knowledge_inbox_items", type_="check")
    op.create_check_constraint("destination_check", "knowledge_inbox_items",
                               "destination IS NULL OR destination IN ('memory', 'project')")
    op.drop_table("pulse_lab_results")
