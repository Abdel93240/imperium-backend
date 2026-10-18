"""path settings: per-user prayer calculation method, madhhab and city (PAT-11, doc 41 §6.4)

Une ligne par utilisateur, créée au premier PATCH ; sans ligne, les paramètres globaux
path.calc_method / path.madhhab et Paris s'appliquent comme avant.

Revision ID: 20261018_0076
Revises: 20261018_0075
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0076"
down_revision: str | None = "20261018_0075"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "path_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("calculation_method", sa.Text(), nullable=False),
        sa.Column("madhhab", sa.Text(), nullable=False),
        sa.Column("city_name", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", name="path_settings_user_unique"),
        sa.CheckConstraint(
            "calculation_method IN ('MuslimWorldLeague', 'Karachi', 'Egypt', 'ISNA')", name="calculation_method_check"
        ),
        sa.CheckConstraint("madhhab IN ('Hanafi', 'Maliki', 'Shafii', 'Hanbali', 'Jafari')", name="madhhab_check"),
        sa.CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL) AND (latitude IS NULL) = (city_name IS NULL)",
            name="city_complete",
        ),
    )


def downgrade() -> None:
    op.drop_table("path_settings")
