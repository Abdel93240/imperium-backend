"""pulse food stock (matières premières) + passage des articles des tickets validés

Doc 40 §10.5 et §11, doc 37 §3.3 point 4, doc 42 §15.2. À la validation d'un
justificatif, le backend écrit la dépense dans le Vault ET les lignes alimentaires
cochées dans le stock Pulse : deux écritures, chacune dans la table de son domaine.

Revision ID: 20261017_0052
Revises: 20261017_0051
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261017_0052"
down_revision: str | None = "20261017_0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "food_stock_items",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False, server_default=sa.text("'piece'")),
        sa.Column("expiry_type", sa.Text(), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("quantity > 0", name="quantity_positive"),
        sa.CheckConstraint("unit IN ('piece', 'kg', 'g', 'l', 'cl', 'ml')", name="unit_check"),
        sa.CheckConstraint("expiry_type IN ('DLC', 'DDM', 'unknown')", name="expiry_type_check"),
        sa.CheckConstraint("source IN ('manual', 'vault_receipt', 'pantry_scan', 'chatbot')", name="source_check"),
        sa.CheckConstraint("status IN ('active', 'consumed', 'removed')", name="status_check"),
    )
    op.create_index("food_stock_items_user_status_idx", "food_stock_items", ["user_id", "status"])
    op.create_index(
        "food_stock_items_user_source_ref_idx",
        "food_stock_items",
        ["user_id", "source_ref"],
        unique=True,
        postgresql_where=sa.text("source_ref IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("food_stock_items_user_source_ref_idx", table_name="food_stock_items")
    op.drop_index("food_stock_items_user_status_idx", table_name="food_stock_items")
    op.drop_table("food_stock_items")
