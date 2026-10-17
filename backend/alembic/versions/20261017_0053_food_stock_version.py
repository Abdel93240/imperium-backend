"""pulse food stock : version de ligne pour l'ajout et la modification manuels

Doc 40 §8 (« Quantity is patched with version ») : chaque modification envoie la
version lue ; une version dépassée renvoie un conflit au lieu d'écraser en silence.

Revision ID: 20261017_0053
Revises: 20261017_0052
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261017_0053"
down_revision: str | None = "20261017_0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("food_stock_items", sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")))
    op.create_check_constraint("version_positive", "food_stock_items", "version >= 1")


def downgrade() -> None:
    op.drop_constraint("version_positive", "food_stock_items", type_="check")
    op.drop_column("food_stock_items", "version")
