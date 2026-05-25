"""add imperium path habits and check-ins

Revision ID: 20260525_0027
Revises: 20260525_0026
Create Date: 2026-05-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260525_0027"
down_revision: str | None = "20260525_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imperium_path_habits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("domain", sa.String(length=80), nullable=True),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "frequency IN ('daily', 'weekly')",
            name="imperium_path_habits_frequency_check",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="imperium_path_habits_user_id_fkey"),
    )
    op.create_index(
        "imperium_path_habits_user_active_created_idx",
        "imperium_path_habits",
        ["user_id", "is_active", "created_at"],
    )
    op.create_index("imperium_path_habits_user_domain_idx", "imperium_path_habits", ["user_id", "domain"])

    op.create_table(
        "imperium_path_check_ins",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("habit_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("check_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('done', 'missed')",
            name="imperium_path_check_ins_status_check",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="imperium_path_check_ins_user_id_fkey"),
        sa.ForeignKeyConstraint(["habit_id"], ["imperium_path_habits.id"], name="imperium_path_check_ins_habit_id_fkey"),
        sa.UniqueConstraint(
            "user_id",
            "habit_id",
            "check_date",
            name="imperium_path_check_ins_user_habit_date_unique",
        ),
    )
    op.create_index(
        "imperium_path_check_ins_user_check_date_desc_idx",
        "imperium_path_check_ins",
        ["user_id", sa.text("check_date DESC")],
    )
    op.create_index(
        "imperium_path_check_ins_user_habit_check_date_idx",
        "imperium_path_check_ins",
        ["user_id", "habit_id", "check_date"],
    )


def downgrade() -> None:
    op.drop_index("imperium_path_check_ins_user_habit_check_date_idx", table_name="imperium_path_check_ins")
    op.drop_index("imperium_path_check_ins_user_check_date_desc_idx", table_name="imperium_path_check_ins")
    op.drop_table("imperium_path_check_ins")
    op.drop_index("imperium_path_habits_user_domain_idx", table_name="imperium_path_habits")
    op.drop_index("imperium_path_habits_user_active_created_idx", table_name="imperium_path_habits")
    op.drop_table("imperium_path_habits")
