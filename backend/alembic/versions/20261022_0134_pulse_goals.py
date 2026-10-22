"""pulse: objectifs de l'utilisateur, classés par priorité (décision utilisateur 2026-10-22)

« La feature la plus importante de Pulse » : sur l'accueil, une liste d'objectifs écrits par l'utilisateur dans
l'ordre qu'il décide (ex. 1. abdos visibles, 2. 25 tractions d'affilée, 3. dos droit). Le programme d'entraînement
et la diète sont construits à partir de cette liste, dans cet ordre. Avance sur doc F01 (prévu V3) : décision
utilisateur. Aucune IA ici : l'utilisateur écrit, classe, marque atteint ou retire.

Revision ID: 20261022_0134
Revises: 20261022_0133
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261022_0134"
down_revision: str | None = "20261022_0133"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pulse_goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active', 'achieved', 'archived')", name="status_check"),
        sa.CheckConstraint("length(btrim(title)) > 0", name="title_not_blank"),
        sa.CheckConstraint("rank >= 1", name="rank_positive"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_pulse_goals_user_key"),
    )
    op.create_index("pulse_goals_user_status_rank_idx", "pulse_goals", ["user_id", "status", "rank"])


def downgrade() -> None:
    op.drop_table("pulse_goals")
