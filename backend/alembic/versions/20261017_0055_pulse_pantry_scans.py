"""pulse pantry scans (scan du placard / frigo, PUL-13)

Doc 37 §5 (pulse.kitchen_inventory_photo), doc 40 §11.1, doc 59 §15.13. Le service
local d'analyse d'image propose une liste d'aliments ; le backend la compare au stock
et propose ajouts et mises à jour ; rien n'entre au stock avant la validation.
La photo n'est JAMAIS conservée côté serveur (plus strict que les 7 jours du doc 37
§9.3) : seuls l'empreinte, la proposition et la décision sont gardées.

Revision ID: 20261017_0055
Revises: 20261017_0054
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261017_0055"
down_revision: str | None = "20261017_0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "pulse_pantry_scans",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("image_quality", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("proposal", postgresql.JSONB(), nullable=True),
        sa.Column("warnings", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('ready', 'failed', 'validated', 'cancelled')", name="status_check"),
        sa.CheckConstraint("image_quality IS NULL OR image_quality IN ('good', 'acceptable', 'poor')", name="image_quality_check"),
        sa.CheckConstraint("size_bytes >= 0", name="size_non_negative"),
    )
    op.create_index("pulse_pantry_scans_user_created_idx", "pulse_pantry_scans", ["user_id", "created_at"])
    op.create_index("pulse_pantry_scans_user_idempotency_idx", "pulse_pantry_scans", ["user_id", "idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index("pulse_pantry_scans_user_idempotency_idx", table_name="pulse_pantry_scans")
    op.drop_index("pulse_pantry_scans_user_created_idx", table_name="pulse_pantry_scans")
    op.drop_table("pulse_pantry_scans")
