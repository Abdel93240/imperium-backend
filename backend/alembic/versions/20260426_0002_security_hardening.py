"""security hardening for refresh tokens and append-only logs

Revision ID: 20260426_0002
Revises: 20260425_0001
Create Date: 2026-04-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260426_0002"
down_revision: str | None = "20260425_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("refresh_tokens", sa.Column("token_selector", sa.Text(), nullable=True))
    op.add_column("refresh_tokens", sa.Column("token_secret_hash", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE refresh_tokens
        SET
            token_selector = encode(gen_random_bytes(18), 'hex'),
            token_secret_hash = token_hash
        WHERE token_selector IS NULL
        """
    )
    op.alter_column("refresh_tokens", "token_selector", nullable=False)
    op.alter_column("refresh_tokens", "token_secret_hash", nullable=False)
    op.alter_column("refresh_tokens", "token_hash", nullable=True)
    op.create_index(
        "refresh_tokens_selector_idx",
        "refresh_tokens",
        ["token_selector"],
        unique=True,
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_append_only_update_delete()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'table % is append-only; UPDATE and DELETE are forbidden', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER events_append_only_guard
        BEFORE UPDATE OR DELETE ON events
        FOR EACH ROW EXECUTE FUNCTION prevent_append_only_update_delete();
        """
    )
    op.execute(
        """
        CREATE TRIGGER auth_events_append_only_guard
        BEFORE UPDATE OR DELETE ON auth_events
        FOR EACH ROW EXECUTE FUNCTION prevent_append_only_update_delete();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS auth_events_append_only_guard ON auth_events")
    op.execute("DROP TRIGGER IF EXISTS events_append_only_guard ON events")
    op.execute("DROP FUNCTION IF EXISTS prevent_append_only_update_delete")
    op.drop_index("refresh_tokens_selector_idx", table_name="refresh_tokens")
    op.alter_column("refresh_tokens", "token_hash", nullable=False)
    op.drop_column("refresh_tokens", "token_secret_hash")
    op.drop_column("refresh_tokens", "token_selector")
