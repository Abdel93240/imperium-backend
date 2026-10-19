"""daily G4: blocking calendar events as fixed commitments (spec Daily §5 G4, PATCH_DAILY D-8 partie calendrier)

1. `daily_selection_log.next_fixed_kind` (mission | calendar_event) : `next_fixed_ref` n'a pas de clé
   étrangère et peut désormais viser un événement calendrier. Lignes existantes : `mission`.
2. Paramètre `daily.calendar_commitments_enabled` false : quand il est vrai, le temps restant (G4)
   s'arrête aussi au prochain événement `imperium_calendar_events` à venir, `blocks_time`, non
   soft-supprimé. Les prières (Q6, ACT-DLY-10) restent hors de ce lot.

Revision ID: 20261019_0107
Revises: 20261019_0106
Create Date: 2026-10-19
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261019_0107"
down_revision: str | None = "20261019_0106"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARAMETERS = [
    ("daily.calendar_commitments_enabled", "daily", False, "bool",
     "G4 : les événements calendrier qui bloquent du temps bornent le temps restant (PATCH_DAILY D-8)."),
]


def upgrade() -> None:
    op.add_column("daily_selection_log", sa.Column("next_fixed_kind", sa.Text(), nullable=True))
    op.execute("UPDATE daily_selection_log SET next_fixed_kind = 'mission' WHERE next_fixed_ref IS NOT NULL")
    op.create_check_constraint("daily_selection_log_next_fixed_kind_check", "daily_selection_log",
                               "next_fixed_kind IS NULL OR next_fixed_kind IN ('mission', 'calendar_event')")
    op.create_check_constraint("daily_selection_log_next_fixed_pair", "daily_selection_log",
                               "(next_fixed_kind IS NULL) = (next_fixed_ref IS NULL)")
    conn = op.get_bind()
    for code, domain, value, unit, rationale in PARAMETERS:
        conn.exec_driver_sql(
            """
            INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version)
            VALUES (gen_random_uuid(), %s, %s, %s::jsonb, %s, %s, 'seed', 1)
            ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING
            """,
            (code, domain, json.dumps(value), unit, rationale),
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = ANY(%s)", ([p[0] for p in PARAMETERS],))
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
    op.drop_constraint("daily_selection_log_next_fixed_pair", "daily_selection_log", type_="check")
    op.drop_constraint("daily_selection_log_next_fixed_kind_check", "daily_selection_log", type_="check")
    op.drop_column("daily_selection_log", "next_fixed_kind")
