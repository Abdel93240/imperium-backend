"""path invocations library, favorites and morning/evening checklist (doc 41 §11-bis, PAT-12)

Revision ID: 20261018_0078
Revises: 20261018_0077
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0078"
down_revision: str | None = "20261018_0077"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "path_invocations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("situation", sa.Text(), nullable=False),
        sa.Column("arabic_text", sa.Text(), nullable=False),
        sa.Column("translation_fr", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("audio_url", sa.Text(), nullable=True),
        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("daily_period", sa.Text(), nullable=True),
        sa.Column("daily_order", sa.Integer(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "situation IN ('quotidien', 'voyage', 'protection', 'difficulte', 'maladie', 'peur_anxiete')",
            name="situation_check",
        ),
        sa.CheckConstraint("daily_period IS NULL OR daily_period IN ('morning', 'evening')", name="daily_period_check"),
        sa.CheckConstraint("(daily_period IS NULL) = (daily_order IS NULL)", name="daily_order_pair"),
        sa.CheckConstraint("length(btrim(arabic_text)) > 0 AND length(btrim(translation_fr)) > 0", name="texts_present"),
        sa.CheckConstraint("length(btrim(source)) > 0", name="source_present"),
        sa.CheckConstraint("audio_url IS NULL OR audio_url LIKE 'https://%'", name="audio_url_https"),
    )
    op.create_index("path_invocations_user_situation_idx", "path_invocations", ["user_id", "situation"])
    op.create_index("path_invocations_user_idempotency_idx", "path_invocations", ["user_id", "idempotency_key"], unique=True)
    op.create_table(
        "path_invocation_checks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invocation_id", UUID, sa.ForeignKey("path_invocations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("invocation_id", "day", name="path_invocation_checks_invocation_day_unique"),
    )


def downgrade() -> None:
    op.drop_table("path_invocation_checks")
    op.drop_index("path_invocations_user_idempotency_idx", table_name="path_invocations")
    op.drop_index("path_invocations_user_situation_idx", table_name="path_invocations")
    op.drop_table("path_invocations")
