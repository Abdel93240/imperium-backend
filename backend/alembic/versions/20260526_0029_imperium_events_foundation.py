"""imperium events foundation

Revision ID: 20260526_0029
Revises: 20260525_0028
Create Date: 2026-05-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260526_0029"
down_revision: str | None = "20260525_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = "20260426_0003"


def upgrade() -> None:
    op.create_table(
        "imperium_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("source_module", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("schema_version", sa.Text(), nullable=False, server_default="v1"),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "length(btrim(event_type)) > 0",
            name="imperium_events_event_type_non_empty",
        ),
        sa.CheckConstraint(
            "length(btrim(source_module)) > 0",
            name="imperium_events_source_module_non_empty",
        ),
        sa.CheckConstraint(
            "length(btrim(schema_version)) > 0",
            name="imperium_events_schema_version_non_empty",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="imperium_events_user_id_fkey"),
    )
    op.create_index(
        "imperium_events_user_occurred_at_desc_idx",
        "imperium_events",
        ["user_id", sa.text("occurred_at DESC")],
    )
    op.create_index(
        "imperium_events_user_source_module_occurred_at_desc_idx",
        "imperium_events",
        ["user_id", "source_module", sa.text("occurred_at DESC")],
    )
    op.create_index(
        "imperium_events_user_event_type_occurred_at_desc_idx",
        "imperium_events",
        ["user_id", "event_type", sa.text("occurred_at DESC")],
    )
    op.create_index(
        "imperium_events_user_idempotency_key_unique_idx",
        "imperium_events",
        ["user_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.execute(
        """
        CREATE TRIGGER imperium_events_append_only_guard
        BEFORE UPDATE OR DELETE ON imperium_events
        FOR EACH ROW EXECUTE FUNCTION prevent_append_only_update_delete();
        """
    )
    op.execute(
        """
        CREATE TRIGGER imperium_events_append_only_truncate_guard
        BEFORE TRUNCATE ON imperium_events
        FOR EACH STATEMENT EXECUTE FUNCTION prevent_append_only_truncate();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS imperium_events_append_only_truncate_guard ON imperium_events")
    op.execute("DROP TRIGGER IF EXISTS imperium_events_append_only_guard ON imperium_events")
    op.drop_index("imperium_events_user_idempotency_key_unique_idx", table_name="imperium_events")
    op.drop_index("imperium_events_user_event_type_occurred_at_desc_idx", table_name="imperium_events")
    op.drop_index("imperium_events_user_source_module_occurred_at_desc_idx", table_name="imperium_events")
    op.drop_index("imperium_events_user_occurred_at_desc_idx", table_name="imperium_events")
    op.drop_table("imperium_events")
