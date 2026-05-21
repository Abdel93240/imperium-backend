"""add truncate guards for append-only tables

Revision ID: 20260426_0003
Revises: 20260426_0002
Create Date: 2026-04-26
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260426_0003"
down_revision: str | None = "20260426_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_append_only_truncate()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'table % is append-only; TRUNCATE is forbidden', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER events_append_only_truncate_guard
        BEFORE TRUNCATE ON events
        FOR EACH STATEMENT EXECUTE FUNCTION prevent_append_only_truncate();
        """
    )
    op.execute(
        """
        CREATE TRIGGER auth_events_append_only_truncate_guard
        BEFORE TRUNCATE ON auth_events
        FOR EACH STATEMENT EXECUTE FUNCTION prevent_append_only_truncate();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS auth_events_append_only_truncate_guard ON auth_events")
    op.execute("DROP TRIGGER IF EXISTS events_append_only_truncate_guard ON events")
    op.execute("DROP FUNCTION IF EXISTS prevent_append_only_truncate")
