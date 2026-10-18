"""rides business rules (doc 57 §4) and rules-only signal on offers

Règles métier par utilisateur (R1, R2, R7, R8 calculables sur les codes postaux, le créneau
et le type de course), révisables avec historique ; les courses proposées gardent les codes
postaux, le signal « règles seules » (green|red|aucun), sa raison et les règles déclenchées.

Revision ID: 20261018_0072
Revises: 20261018_0071
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0072"
down_revision: str | None = "20261018_0071"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    for name in ("pickup_zone_code", "destination_zone_code", "signal", "signal_source", "signal_reason"):
        op.add_column("rides_offers", sa.Column(name, sa.Text(), nullable=True))
    op.add_column("rides_offers", sa.Column("triggered_rules", postgresql.JSONB(), nullable=False, server_default="[]"))
    op.create_check_constraint("signal_check", "rides_offers", "signal IS NULL OR signal IN ('green', 'red')")
    op.create_table(
        "rides_business_rules",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("conditions", postgresql.JSONB(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_hard_rule", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("times_applied", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revision_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_revised_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "rule_code", name="rides_business_rules_user_code_unique"),
        sa.CheckConstraint("action IN ('red', 'green')", name="action_check"),
        sa.CheckConstraint("version >= 1", name="version_positive"),
    )
    op.create_table(
        "rides_rule_revisions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("rule_id", UUID, sa.ForeignKey("rides_business_rules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revised_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision_type", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("previous", postgresql.JSONB(), nullable=False),
        sa.Column("new", postgresql.JSONB(), nullable=False),
        sa.Column("proposed_by", sa.Text(), nullable=False),
        sa.Column("user_validated", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "revision_type IN ('disabled', 'enabled', 'modified', 'hardened', 'softened')", name="revision_type_check"
        ),
        sa.CheckConstraint("proposed_by IN ('user_manual', 'weekly_review', 'auto_threshold')", name="proposed_by_check"),
    )
    op.create_index("rides_rule_revisions_rule_idx", "rides_rule_revisions", ["rule_id", "revised_at"])


def downgrade() -> None:
    op.drop_index("rides_rule_revisions_rule_idx", table_name="rides_rule_revisions")
    op.drop_table("rides_rule_revisions")
    op.drop_table("rides_business_rules")
    op.drop_constraint("signal_check", "rides_offers", type_="check")
    op.drop_column("rides_offers", "triggered_rules")
    for name in ("signal_reason", "signal_source", "signal", "destination_zone_code", "pickup_zone_code"):
        op.drop_column("rides_offers", name)
