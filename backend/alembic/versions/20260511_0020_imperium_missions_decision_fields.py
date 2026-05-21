"""add decision framework fields to imperium missions

Revision ID: 20260511_0020
Revises: 20260504_0019
Create Date: 2026-05-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260511_0020"
down_revision: str | None = "20260504_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MISSION_DOMAIN_CHECK = "domain IS NULL OR domain IN ('religious', 'business', 'finance', 'health')"
MISSION_PRIORITY_LEVEL_CHECK = "priority_level IS NULL OR (priority_level >= 1 AND priority_level <= 10)"
MISSION_TYPE_CATEGORY_CHECK = (
    "mission_type_category IS NULL OR mission_type_category IN "
    "('cat_a', 'cat_b', 'cat_c', 'cat_d', 'cat_e', 'cat_f', 'cat_g', 'cat_h', 'cat_i')"
)
MISSION_STATUS_CHECK = "status IN ('backlog', 'active', 'completed', 'failed', 'cancelled')"
LEGACY_MISSION_STATUS_CHECK = "status IN ('active', 'completed', 'failed', 'cancelled')"


def upgrade() -> None:
    op.add_column("imperium_missions", sa.Column("domain", sa.Text(), nullable=True))
    op.add_column("imperium_missions", sa.Column("mission_type_category", sa.Text(), nullable=True))

    op.drop_constraint(
        op.f("ck_imperium_missions_imperium_missions_status_check"),
        "imperium_missions",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_imperium_missions_imperium_missions_status_check"),
        "imperium_missions",
        MISSION_STATUS_CHECK,
    )
    op.create_check_constraint(
        op.f("ck_imperium_missions_imperium_missions_domain_check"),
        "imperium_missions",
        MISSION_DOMAIN_CHECK,
    )
    op.create_check_constraint(
        op.f("ck_imperium_missions_imperium_missions_priority_level_range"),
        "imperium_missions",
        MISSION_PRIORITY_LEVEL_CHECK,
    )
    op.create_check_constraint(
        op.f("ck_imperium_missions_imperium_missions_mission_type_category_check"),
        "imperium_missions",
        MISSION_TYPE_CATEGORY_CHECK,
    )

    op.create_index("imperium_missions_user_domain_idx", "imperium_missions", ["user_id", "domain"], unique=False)
    op.create_index(
        "imperium_missions_user_backlog_priority_created_idx",
        "imperium_missions",
        ["user_id", "priority_level", "created_at"],
        unique=False,
        postgresql_where=sa.text("status = 'backlog'"),
    )
    op.create_index(
        "imperium_missions_user_mission_type_category_idx",
        "imperium_missions",
        ["user_id", "mission_type_category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("imperium_missions_user_mission_type_category_idx", table_name="imperium_missions")
    op.drop_index("imperium_missions_user_backlog_priority_created_idx", table_name="imperium_missions")
    op.drop_index("imperium_missions_user_domain_idx", table_name="imperium_missions")

    op.drop_constraint(
        op.f("ck_imperium_missions_imperium_missions_mission_type_category_check"),
        "imperium_missions",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_imperium_missions_imperium_missions_priority_level_range"),
        "imperium_missions",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_imperium_missions_imperium_missions_domain_check"),
        "imperium_missions",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_imperium_missions_imperium_missions_status_check"),
        "imperium_missions",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_imperium_missions_imperium_missions_status_check"),
        "imperium_missions",
        LEGACY_MISSION_STATUS_CHECK,
    )

    op.drop_column("imperium_missions", "mission_type_category")
    op.drop_column("imperium_missions", "domain")
