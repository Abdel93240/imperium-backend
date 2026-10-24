"""vector: scan quotidien des événements des 48 h à venir (2026-10-24)

Job `vector.event_scan_daily` (12:00) : petites salles, clubs, soirées, réceptions, banlieue, et l'open data de la Ville
de Paris, pour aujourd'hui et demain — ce qui s'annonce tard. Allumé si le scan du lundi l'est.

Revision ID: 20261024_0147
Revises: 20261024_0146
Create Date: 2026-10-24
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261024_0147"
down_revision: str | None = "20261024_0146"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.get_bind().exec_driver_sql(
        "INSERT INTO job_definitions (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s) "
        "VALUES (gen_random_uuid(), 'vector.event_scan_daily', 'cron', '0 12 * * *', NULL, "
        "'app.services.vector.events:event_scan_daily_job', "
        "COALESCE((SELECT enabled FROM job_definitions WHERE code = 'vector.event_scan'), false), true, 1800) "
        "ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING")


def downgrade() -> None:
    op.get_bind().exec_driver_sql("DELETE FROM job_definitions WHERE code = 'vector.event_scan_daily'")
