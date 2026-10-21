"""nexus escalation: per-message self-assessment /200 and invisible escalation (doc 72 §3, doc 30 §5)

- `chat_messages.routing` (JSONB, nullable) : décision d'escalade de chaque réponse (score, rôle, raisons) ;
- slot `nexus.escalation` (routed, domaine imperium) : le rôle cloud choisi par le score répond à la question
  anonyme du modèle local ; servi seulement si `ai.cloud_slot_modes` le met en live (semé éteint : mode ombre).

Revision ID: 20261021_0125
Revises: 20261021_0124
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261021_0125"
down_revision: str | None = "20261021_0124"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("routing", postgresql.JSONB(), nullable=True))
    op.execute(
        """
        INSERT INTO ai_slot_transition
          (id, slot_code, domain, tier, audit_sample_pct, agreement_target_pct, notes_fr)
        VALUES (gen_random_uuid(), 'nexus.escalation', 'imperium', 'routed', 100, 92,
                'Escalade invisible de Nexus : le rôle choisi par le score /200 répond à la question anonyme.')
        ON CONFLICT ON CONSTRAINT ai_slot_transition_slot_code_unique DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM ai_slot_transition WHERE slot_code = 'nexus.escalation'")
    op.drop_column("chat_messages", "routing")
