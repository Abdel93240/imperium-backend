"""decision framework foundation

Revision ID: 20260504_0019
Revises: 20260503_0018
Create Date: 2026-05-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260504_0019"
down_revision: str | None = "20260503_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imperium_user_priorities",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("coefficient", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "domain IN ('religious', 'business', 'finance', 'health')",
            name=op.f("ck_imperium_user_priorities_imperium_user_priorities_domain_check"),
        ),
        sa.CheckConstraint(
            "position >= 1 AND position <= 4",
            name=op.f("ck_imperium_user_priorities_imperium_user_priorities_position_range"),
        ),
        sa.CheckConstraint(
            "(position = 1 AND coefficient = 10) OR "
            "(position = 2 AND coefficient = 8) OR "
            "(position = 3 AND coefficient = 5) OR "
            "(position = 4 AND coefficient = 4)",
            name=op.f("ck_imperium_user_priorities_imperium_user_priorities_position_coefficient_check"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_imperium_user_priorities_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_imperium_user_priorities")),
    )
    op.create_index(
        "imperium_user_priorities_active_domain_unique_idx",
        "imperium_user_priorities",
        ["user_id", "domain"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "imperium_user_priorities_active_position_unique_idx",
        "imperium_user_priorities",
        ["user_id", "position"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "imperium_user_priorities_user_active_position_idx",
        "imperium_user_priorities",
        ["user_id", "is_active", "position"],
        unique=False,
    )

    op.create_table(
        "imperium_mission_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("intrinsic_score", sa.Numeric(5, 2), nullable=False),
        sa.Column("domain_coefficient", sa.Integer(), nullable=False),
        sa.Column("weighted_score", sa.Numeric(7, 2), nullable=False),
        sa.Column("explanation", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("source", sa.Text(), server_default=sa.text("'decision_framework_v1'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "domain IN ('religious', 'business', 'finance', 'health')",
            name=op.f("ck_imperium_mission_scores_imperium_mission_scores_domain_check"),
        ),
        sa.CheckConstraint(
            "intrinsic_score >= 0 AND intrinsic_score <= 100",
            name=op.f("ck_imperium_mission_scores_imperium_mission_scores_intrinsic_range"),
        ),
        sa.CheckConstraint(
            "domain_coefficient IN (10, 8, 5, 4)",
            name=op.f("ck_imperium_mission_scores_imperium_mission_scores_coefficient_check"),
        ),
        sa.CheckConstraint(
            "weighted_score >= 0",
            name=op.f("ck_imperium_mission_scores_imperium_mission_scores_weighted_nonnegative"),
        ),
        sa.CheckConstraint(
            "source IN ('decision_framework_v1')",
            name=op.f("ck_imperium_mission_scores_imperium_mission_scores_source_check"),
        ),
        sa.ForeignKeyConstraint(["mission_id"], ["imperium_missions.id"], name=op.f("fk_imperium_mission_scores_mission_id_imperium_missions"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_imperium_mission_scores_user_id_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_imperium_mission_scores")),
    )
    op.create_index("imperium_mission_scores_user_weighted_idx", "imperium_mission_scores", ["user_id", "weighted_score"], unique=False)
    op.create_index("imperium_mission_scores_user_domain_idx", "imperium_mission_scores", ["user_id", "domain"], unique=False)
    op.create_index("imperium_mission_scores_mission_idx", "imperium_mission_scores", ["mission_id"], unique=False)


def downgrade() -> None:
    op.drop_index("imperium_mission_scores_mission_idx", table_name="imperium_mission_scores")
    op.drop_index("imperium_mission_scores_user_domain_idx", table_name="imperium_mission_scores")
    op.drop_index("imperium_mission_scores_user_weighted_idx", table_name="imperium_mission_scores")
    op.drop_table("imperium_mission_scores")

    op.drop_index("imperium_user_priorities_user_active_position_idx", table_name="imperium_user_priorities")
    op.drop_index("imperium_user_priorities_active_position_unique_idx", table_name="imperium_user_priorities")
    op.drop_index("imperium_user_priorities_active_domain_unique_idx", table_name="imperium_user_priorities")
    op.drop_table("imperium_user_priorities")
