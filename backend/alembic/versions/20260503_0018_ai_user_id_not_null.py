"""ai ownership not null

Revision ID: 20260503_0018
Revises: 20260502_0017
Create Date: 2026-05-03
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260503_0018"
down_revision: str | None = "20260502_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            null_rows integer;
            user_count integer;
            canonical_setting text;
            canonical_id uuid;
        BEGIN
            SELECT
                (SELECT count(*) FROM ai_tasks WHERE user_id IS NULL)
                + (SELECT count(*) FROM ai_results WHERE user_id IS NULL)
                + (SELECT count(*) FROM ai_result_validations WHERE user_id IS NULL)
            INTO null_rows;

            IF null_rows > 0 THEN
                canonical_setting := nullif(current_setting('imperium.canonical_user_id', true), '');

                IF canonical_setting IS NOT NULL THEN
                    canonical_id := canonical_setting::uuid;
                    IF NOT EXISTS (SELECT 1 FROM users WHERE id = canonical_id) THEN
                        RAISE EXCEPTION
                            'Cannot backfill AI ownership user_id: configured imperium.canonical_user_id % does not exist.',
                            canonical_id;
                    END IF;
                ELSE
                    SELECT count(*) INTO user_count FROM users;
                    IF user_count = 1 THEN
                        SELECT id INTO canonical_id FROM users LIMIT 1;
                    ELSE
                        RAISE EXCEPTION
                            'Cannot backfill AI ownership user_id: set imperium.canonical_user_id when NULL AI rows exist and user count is %.',
                            user_count;
                    END IF;
                END IF;

                UPDATE ai_tasks SET user_id = canonical_id WHERE user_id IS NULL;
                UPDATE ai_results SET user_id = canonical_id WHERE user_id IS NULL;
                UPDATE ai_result_validations SET user_id = canonical_id WHERE user_id IS NULL;
            END IF;
        END $$;
        """
    )

    op.alter_column("ai_tasks", "user_id", nullable=False)
    op.alter_column("ai_results", "user_id", nullable=False)
    op.alter_column("ai_result_validations", "user_id", nullable=False)


def downgrade() -> None:
    op.alter_column("ai_result_validations", "user_id", nullable=True)
    op.alter_column("ai_results", "user_id", nullable=True)
    op.alter_column("ai_tasks", "user_id", nullable=True)
