"""harden imperium event db constraints

Revision ID: 20260526_0031
Revises: 20260526_0030
Create Date: 2026-05-26
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260526_0031"
down_revision: str | None = "20260526_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "imperium_events_event_type_format_check",
        "imperium_events",
        "event_type ~ '^[a-z][a-z0-9_]*$'",
    )
    op.create_check_constraint(
        "imperium_events_schema_version_v1_check",
        "imperium_events",
        "schema_version = 'v1'",
    )
    op.create_check_constraint(
        "imperium_events_payload_json_object_check",
        "imperium_events",
        "payload_json IS NULL OR jsonb_typeof(payload_json) = 'object'",
    )


def downgrade() -> None:
    op.drop_constraint("imperium_events_payload_json_object_check", "imperium_events", type_="check")
    op.drop_constraint("imperium_events_schema_version_v1_check", "imperium_events", type_="check")
    op.drop_constraint("imperium_events_event_type_format_check", "imperium_events", type_="check")
