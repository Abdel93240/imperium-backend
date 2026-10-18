"""path registered mosques: one default per user, version, idempotency (PAT-09, doc 41 §6.3)

La table existe depuis le socle (0038) sans routes ; elle reçoit une mosquée par défaut au
plus par utilisateur (référence des horaires), la paire latitude/longitude, une version et
l'Idempotency-Key des créations.

Revision ID: 20261018_0075
Revises: 20261018_0074
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261018_0075"
down_revision: str | None = "20261018_0074"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("path_registered_mosques", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("path_registered_mosques", sa.Column("idempotency_key", sa.Text(), nullable=True))
    op.add_column("path_registered_mosques", sa.Column("request_hash", sa.Text(), nullable=True))
    op.create_index("path_registered_mosques_one_default_idx", "path_registered_mosques", ["user_id"], unique=True,
                    postgresql_where=sa.text("is_default"))
    op.create_check_constraint("coordinates_pair", "path_registered_mosques", "(latitude IS NULL) = (longitude IS NULL)")


def downgrade() -> None:
    op.drop_constraint("coordinates_pair", "path_registered_mosques", type_="check")
    op.drop_index("path_registered_mosques_one_default_idx", table_name="path_registered_mosques")
    op.drop_column("path_registered_mosques", "request_hash")
    op.drop_column("path_registered_mosques", "idempotency_key")
    op.drop_column("path_registered_mosques", "version")
