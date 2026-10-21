"""wr conversation slot: P2 conducted by the local executor over the P1 agenda (spec WR §9 P2)

Slot `wr.conversation` (local_default, domaine wr) : la conversation du WR marche l'agenda de la passe
d'hypothèses. Servi seulement si `ai.local_slot_modes` le met en live (semé vide) ; sinon les questions
de l'agenda sont posées une à une par le code.

Revision ID: 20261021_0120
Revises: 20261021_0119
Create Date: 2026-10-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261021_0120"
down_revision: str | None = "20261021_0119"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO ai_slot_transition
          (id, slot_code, domain, tier, audit_sample_pct, agreement_target_pct, notes_fr)
        VALUES (gen_random_uuid(), 'wr.conversation', 'wr', 'local_default', 100, 92,
                'Conversation du WR : marche l''agenda de la passe d''hypothèses.')
        ON CONFLICT ON CONSTRAINT ai_slot_transition_slot_code_unique DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM ai_slot_transition WHERE slot_code = 'wr.conversation'")
