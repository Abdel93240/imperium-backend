"""pulse hydration logs (PUL-04, doc 40 §12)

Un appui (+250 ml, +500 ml, +1 L), une saisie ou une phrase du chatbot = une ligne ;
l'eau bue est décomptée du stock en même temps (lignes « eau » en ml/cl/l). Même
Idempotency-Key → même réponse ; clés distinctes → les quantités s'additionnent.

Revision ID: 20261017_0058
Revises: 20261017_0057
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261017_0058"
down_revision: str | None = "20261017_0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "pulse_hydration_logs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount_ml", sa.Integer(), nullable=False),
        sa.Column("logged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("stock_decrement_applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("result", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount_ml > 0 AND amount_ml <= 5000", name="amount_range"),
        sa.CheckConstraint("source IN ('quick', 'manual', 'chatbot')", name="source_check"),
    )
    op.create_index("pulse_hydration_logs_user_logged_idx", "pulse_hydration_logs", ["user_id", "logged_at"])
    op.create_index(
        "pulse_hydration_logs_user_idempotency_idx", "pulse_hydration_logs", ["user_id", "idempotency_key"], unique=True
    )


def downgrade() -> None:
    op.drop_index("pulse_hydration_logs_user_idempotency_idx", table_name="pulse_hydration_logs")
    op.drop_index("pulse_hydration_logs_user_logged_idx", table_name="pulse_hydration_logs")
    op.drop_table("pulse_hydration_logs")
