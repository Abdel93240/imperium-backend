"""daily replan: the day is replanned through the selection engine (decision 2026-10-21)

- `daily_selection_log.trigger` accepte `replan` (la sélection relancée par « Replanifier ») ;
- `daily.fatigue_max_minutes` = 30 : replanification pour fatigue, les missions courtes d'abord.

Revision ID: 20261021_0124
Revises: 20261021_0123
Create Date: 2026-10-21
"""

import json
from collections.abc import Sequence

from alembic import op

revision: str = "20261021_0124"
down_revision: str | None = "20261021_0123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BEFORE = "('mission_completed', 'day_start', 'disruption_resolved', 'manual')"
AFTER = "('mission_completed', 'day_start', 'disruption_resolved', 'manual', 'replan')"


def upgrade() -> None:
    op.drop_constraint("daily_selection_log_trigger_check", "daily_selection_log", type_="check")
    op.create_check_constraint("daily_selection_log_trigger_check", "daily_selection_log", f"trigger IN {AFTER}")
    op.get_bind().exec_driver_sql(
        """
        INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version)
        VALUES (gen_random_uuid(), 'daily.fatigue_max_minutes', 'daily', %s::jsonb, 'min',
                'Replanification pour fatigue : les missions de cette durée au plus passent d''abord.', 'seed', 1)
        ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING
        """,
        (json.dumps(30),),
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = 'daily.fatigue_max_minutes'")
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    op.execute("DELETE FROM daily_selection_log WHERE trigger = 'replan'")
    op.drop_constraint("daily_selection_log_trigger_check", "daily_selection_log", type_="check")
    op.create_check_constraint("daily_selection_log_trigger_check", "daily_selection_log", f"trigger IN {BEFORE}")
