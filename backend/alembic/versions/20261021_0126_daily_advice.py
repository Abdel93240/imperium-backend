"""daily advice: the Dashboard « Conseils IA » block (doc 65 §3)

- `planning_days.advice` (JSONB, nullable) : conseil du jour rangé sur la journée ouverte, avec la signature de
  l'état qui l'a produit ;
- slot `imperium.advice` (local_default, domaine imperium) : réécriture du conseil par le modèle local ; servi
  seulement si `ai.local_slot_modes` le met en live (sinon le conseil des règles reste).

Revision ID: 20261021_0126
Revises: 20261021_0125
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261021_0126"
down_revision: str | None = "20261021_0125"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("planning_days", sa.Column("advice", postgresql.JSONB(), nullable=True))
    op.execute(
        """
        INSERT INTO ai_slot_transition
          (id, slot_code, domain, tier, audit_sample_pct, agreement_target_pct, notes_fr)
        VALUES (gen_random_uuid(), 'imperium.advice', 'imperium', 'local_default', 100, 92,
                'Conseil du jour du Dashboard, réécrit par le modèle local.')
        ON CONFLICT ON CONSTRAINT ai_slot_transition_slot_code_unique DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM ai_slot_transition WHERE slot_code = 'imperium.advice'")
    op.drop_column("planning_days", "advice")
