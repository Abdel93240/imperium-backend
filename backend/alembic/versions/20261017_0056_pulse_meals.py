"""pulse meals (repas PUL-02/PUL-03, décompte du stock après repas)

Doc 40 §10.1–§10.3 et §8. Un repas naît brouillon (description, macros éventuelles,
proposition de décompte du stock) ; seule la validation l'enregistre et décompte le
stock, une seule fois (`stock_decrement_applied`, clé et empreinte de la validation).

Revision ID: 20261017_0056
Revises: 20261017_0055
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261017_0056"
down_revision: str | None = "20261017_0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)
MACROS = ("calories", "protein_g", "carbs_g", "fat_g")


def upgrade() -> None:
    op.create_table(
        "pulse_meals",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("eaten_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calories", sa.Numeric(7, 1), nullable=True),
        sa.Column("protein_g", sa.Numeric(6, 1), nullable=True),
        sa.Column("carbs_g", sa.Numeric(6, 1), nullable=True),
        sa.Column("fat_g", sa.Numeric(6, 1), nullable=True),
        sa.Column("proposal", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("warnings", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("stock_decrement_applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("confirm_idempotency_key", sa.Text(), nullable=True),
        sa.Column("confirm_request_hash", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('draft', 'confirmed', 'cancelled')", name="status_check"),
        sa.CheckConstraint("source IN ('text', 'voice', 'photo', 'manual', 'chatbot')", name="source_check"),
        sa.CheckConstraint("length(btrim(description)) > 0", name="description_not_blank"),
        *(sa.CheckConstraint(f"{column} IS NULL OR {column} >= 0", name=f"{column}_non_negative") for column in MACROS),
    )
    op.create_index("pulse_meals_user_eaten_idx", "pulse_meals", ["user_id", "eaten_at"])
    op.create_index("pulse_meals_user_idempotency_idx", "pulse_meals", ["user_id", "idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index("pulse_meals_user_idempotency_idx", table_name="pulse_meals")
    op.drop_index("pulse_meals_user_eaten_idx", table_name="pulse_meals")
    op.drop_table("pulse_meals")
