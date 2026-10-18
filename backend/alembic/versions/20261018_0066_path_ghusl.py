"""path ghusl: required state and addresses (doc 41 §10)

État « ghusl requis » : une ligne par activation, posée et levée par l'utilisateur seulement
(un seul état requis à la fois). À l'activation, le backend crée la mission Imperium
« Faire le ghusl avant {prière} » et demande une replanification immédiate (hook
ghusl_required, hors délai). Adresses ghusl : libellé, type, adresse ou coordonnées
explicites, une seule par défaut, version pour les conflits.

Revision ID: 20261018_0066
Revises: 20261018_0065
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0066"
down_revision: str | None = "20261018_0065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "path_ghusl_addresses",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("address_type", sa.Text(), nullable=False),
        sa.Column("address_text", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(btrim(label)) BETWEEN 1 AND 100", name="label_length"),
        sa.CheckConstraint("address_type IN ('home', 'mosque', 'gym', 'work', 'other')", name="address_type_check"),
        sa.CheckConstraint("(latitude IS NULL) = (longitude IS NULL)", name="coordinates_pair"),
        sa.CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="latitude_range"),
        sa.CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="longitude_range"),
        sa.CheckConstraint("version >= 1", name="version_positive"),
    )
    op.create_index(
        "path_ghusl_addresses_one_default_idx", "path_ghusl_addresses", ["user_id"], unique=True,
        postgresql_where=sa.text("is_default"),
    )
    op.create_index(
        "path_ghusl_addresses_user_idempotency_idx", "path_ghusl_addresses", ["user_id", "idempotency_key"], unique=True
    )
    op.create_table(
        "path_ghusl_states",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("required_since", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_prayer", sa.Text(), nullable=True),
        sa.Column("mission_id", UUID, sa.ForeignKey("imperium_missions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("replan_event_id", UUID, nullable=True),
        sa.Column("replan_status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('required', 'completed')", name="status_check"),
        sa.CheckConstraint("status <> 'completed' OR completed_at IS NOT NULL", name="completed_has_time"),
        sa.CheckConstraint(
            "replan_status IN ('pending', 'requested', 'no_open_day', 'replan_in_progress', 'failed')",
            name="replan_status_check",
        ),
    )
    op.create_index(
        "path_ghusl_states_one_required_idx", "path_ghusl_states", ["user_id"], unique=True,
        postgresql_where=sa.text("status = 'required'"),
    )
    op.create_index("path_ghusl_states_user_idempotency_idx", "path_ghusl_states", ["user_id", "idempotency_key"], unique=True)


def downgrade() -> None:
    op.drop_index("path_ghusl_states_user_idempotency_idx", table_name="path_ghusl_states")
    op.drop_index("path_ghusl_states_one_required_idx", table_name="path_ghusl_states")
    op.drop_table("path_ghusl_states")
    op.drop_index("path_ghusl_addresses_user_idempotency_idx", table_name="path_ghusl_addresses")
    op.drop_index("path_ghusl_addresses_one_default_idx", table_name="path_ghusl_addresses")
    op.drop_table("path_ghusl_addresses")
