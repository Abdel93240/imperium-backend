"""user category memory (label → category learned from the user)

Doc 42 §7.0 point 5 et §7.2 (décision utilisateur 2026-10-16) : une catégorie validée
pour un libellé inconnu rejoint la part utilisateur de la table ; 3 confirmations
identiques → confiance haute.

Revision ID: 20261017_0048
Revises: 20261017_0047
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261017_0048"
down_revision: str | None = "20261017_0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_category_memory",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("label_key", sa.Text(), nullable=False),
        sa.Column("sample_label", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("confirmations", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_confirmed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "label_key", name="user_label_unique"),
        sa.CheckConstraint("length(btrim(label_key)) > 0", name="label_key_not_blank"),
        sa.CheckConstraint("confirmations >= 1", name="confirmations_positive"),
    )


def downgrade() -> None:
    op.drop_table("user_category_memory")
