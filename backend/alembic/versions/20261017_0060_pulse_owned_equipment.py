"""pulse owned equipment (matériel possédé, doc 40 §13-EQUIP)

Liste tenue par l'utilisateur dans les réglages (« mettre à jour mon matériel ») ;
entrée du futur programme de séances. Retrait = statut removed (jamais supprimé) ;
un même nom (sans accents ni casse) n'est actif qu'une fois.

Revision ID: 20261017_0060
Revises: 20261017_0059
Create Date: 2026-10-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261017_0060"
down_revision: str | None = "20261017_0059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "pulse_owned_equipment",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_key", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active', 'removed')", name="status_check"),
        sa.CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
    )
    op.create_index(
        "pulse_owned_equipment_user_active_name_idx", "pulse_owned_equipment", ["user_id", "name_key"], unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("pulse_owned_equipment_user_active_name_idx", table_name="pulse_owned_equipment")
    op.drop_table("pulse_owned_equipment")
