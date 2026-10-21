"""wr week starts on a configurable weekday (Tuesday for the user) and a job marks the ended week ready

- `wr.week_start_weekday` = 1 (mardi, décision utilisateur 2026-10-21 : la nuit de lundi à mardi est le
  creux de sa semaine) : la semaine du WR va du mardi au lundi ; la revue porte sur celle qui vient de finir ;
- job `wr.week_ready` (horaire, semé désactivé) : dès 1 h de Paris le jour où la semaine suivante commence,
  la semaine finie devient prête (bannière « Weekly Review en attente »).

Revision ID: 20261021_0122
Revises: 20261021_0121
Create Date: 2026-10-21
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261021_0122"
down_revision: str | None = "20261021_0121"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO parameters (id, code, domain, value, unit, rationale_fr, origin, version)
        VALUES (gen_random_uuid(), 'wr.week_start_weekday', 'wr', '1'::jsonb, 'count',
                'Premier jour de la semaine du WR (0 = lundi, 1 = mardi …) ; la revue porte sur la semaine finie.',
                'seed', 1)
        ON CONFLICT ON CONSTRAINT parameters_code_version_unique DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO job_definitions
          (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
        VALUES (gen_random_uuid(), 'wr.week_ready', 'cron', '5 * * * *', NULL,
                'app.services.imperium.weekly_review_state:week_ready_job', false, true, 60)
        ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM job_definitions WHERE code = 'wr.week_ready'")
    conn = op.get_bind()
    conn.exec_driver_sql("ALTER TABLE parameters DISABLE TRIGGER parameters_append_only")
    try:
        conn.exec_driver_sql("DELETE FROM parameters WHERE code = 'wr.week_start_weekday'")
    finally:
        conn.exec_driver_sql("ALTER TABLE parameters ENABLE TRIGGER parameters_append_only")
