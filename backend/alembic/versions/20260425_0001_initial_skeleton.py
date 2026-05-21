"""initial backend skeleton tables

Revision ID: 20260425_0001
Revises:
Create Date: 2026-04-25
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260425_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

source_app_enum = postgresql.ENUM(
    "imperium",
    "vector",
    "vault",
    "pulse",
    "path",
    "core",
    "external",
    "n8n",
    "ai_router",
    name="source_app",
)

privacy_level_enum = postgresql.ENUM(
    "low",
    "medium",
    "high",
    "very_high",
    name="privacy_level",
)

device_status_enum = postgresql.ENUM(
    "trusted",
    "revoked",
    name="device_status",
)

idempotency_status_enum = postgresql.ENUM(
    "processing",
    "completed",
    "failed",
    name="idempotency_status",
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    source_app_enum.create(op.get_bind(), checkfirst=True)
    privacy_level_enum.create(op.get_bind(), checkfirst=True)
    device_status_enum.create(op.get_bind(), checkfirst=True)
    idempotency_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("master_secret_hash", sa.Text(), nullable=True),
        sa.Column("timezone", sa.Text(), nullable=False, server_default="Europe/Paris"),
        sa.Column("locale", sa.Text(), nullable=True),
        sa.Column("single_user_mode", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("external_ai_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_unique_constraint("users_email_unique", "users", ["email"])
    op.create_index(
        "users_single_user_singleton_idx",
        "users",
        ["single_user_mode"],
        unique=True,
        postgresql_where=sa.text("single_user_mode IS TRUE"),
    )

    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_label", sa.Text(), nullable=False),
        sa.Column("device_fingerprint", sa.Text(), nullable=True),
        sa.Column("platform", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="device_status", create_type=False),
            nullable=False,
            server_default="trusted",
        ),
        sa.Column("trusted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="devices_user_id_fkey"),
    )
    op.create_index("devices_user_status_idx", "devices", ["user_id", "status"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_token_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="refresh_tokens_user_id_fkey"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], name="refresh_tokens_device_id_fkey"),
        sa.ForeignKeyConstraint(
            ["replaced_by_token_id"],
            ["refresh_tokens.id"],
            name="refresh_tokens_replaced_by_token_id_fkey",
        ),
    )
    op.create_index("refresh_tokens_user_device_idx", "refresh_tokens", ["user_id", "device_id"])
    op.create_index("refresh_tokens_expires_at_idx", "refresh_tokens", ["expires_at"])
    op.create_unique_constraint("refresh_tokens_token_hash_unique", "refresh_tokens", ["token_hash"])

    op.create_table(
        "auth_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("ip_address", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="auth_events_user_id_fkey"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], name="auth_events_device_id_fkey"),
    )
    op.create_index("auth_events_user_created_idx", "auth_events", ["user_id", "created_at"])
    op.create_index("auth_events_device_created_idx", "auth_events", ["device_id", "created_at"])
    op.create_index("auth_events_event_type_created_idx", "auth_events", ["event_type", "created_at"])

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("source_app", postgresql.ENUM(name="source_app", create_type=False), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("correlation_id", sa.Text(), nullable=False),
        sa.Column("causation_id", sa.Text(), nullable=True),
        sa.Column("privacy_level", postgresql.ENUM(name="privacy_level", create_type=False), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("duplicate_of_event_id", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="events_user_id_fkey"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], name="events_device_id_fkey"),
    )
    op.create_unique_constraint("events_event_id_unique", "events", ["event_id"])
    op.create_unique_constraint("events_user_idempotency_unique", "events", ["user_id", "idempotency_key"])
    op.create_index("events_user_event_type_occurred_idx", "events", ["user_id", "event_type", "occurred_at"])
    op.create_index("events_user_correlation_idx", "events", ["user_id", "correlation_id"])
    op.create_index("events_causation_id_idx", "events", ["causation_id"])

    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_method", sa.Text(), nullable=False),
        sa.Column("request_path", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="idempotency_status", create_type=False),
            nullable=False,
            server_default="processing",
        ),
        sa.Column("response_status_code", sa.Integer(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(), nullable=True),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="idempotency_keys_user_id_fkey"),
    )
    op.create_unique_constraint(
        "idempotency_keys_user_key_unique",
        "idempotency_keys",
        ["user_id", "idempotency_key"],
    )
    op.create_index("idempotency_keys_user_created_idx", "idempotency_keys", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idempotency_keys_user_created_idx", table_name="idempotency_keys")
    op.drop_constraint("idempotency_keys_user_key_unique", "idempotency_keys", type_="unique")
    op.drop_table("idempotency_keys")

    op.drop_index("events_causation_id_idx", table_name="events")
    op.drop_index("events_user_correlation_idx", table_name="events")
    op.drop_index("events_user_event_type_occurred_idx", table_name="events")
    op.drop_constraint("events_user_idempotency_unique", "events", type_="unique")
    op.drop_constraint("events_event_id_unique", "events", type_="unique")
    op.drop_table("events")

    op.drop_constraint("refresh_tokens_token_hash_unique", "refresh_tokens", type_="unique")
    op.drop_index("auth_events_event_type_created_idx", table_name="auth_events")
    op.drop_index("auth_events_device_created_idx", table_name="auth_events")
    op.drop_index("auth_events_user_created_idx", table_name="auth_events")
    op.drop_table("auth_events")
    op.drop_index("refresh_tokens_expires_at_idx", table_name="refresh_tokens")
    op.drop_index("refresh_tokens_user_device_idx", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")

    op.drop_index("devices_user_status_idx", table_name="devices")
    op.drop_table("devices")

    op.drop_index("users_single_user_singleton_idx", table_name="users")
    op.drop_constraint("users_email_unique", "users", type_="unique")
    op.drop_table("users")

    idempotency_status_enum.drop(op.get_bind(), checkfirst=True)
    device_status_enum.drop(op.get_bind(), checkfirst=True)
    privacy_level_enum.drop(op.get_bind(), checkfirst=True)
    source_app_enum.drop(op.get_bind(), checkfirst=True)
