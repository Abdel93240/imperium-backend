"""wr factory: worker runs and incremental cursors, session-end and 23:30 fallback jobs (spec WR §3.2, §4)

`wr_worker_runs` / `wr_worker_cursors` : DDL de la spec §3.2, + `job_run_id` (le run du runner qui
a porté l'usine). Deux jobs semés désactivés : `wr.factory_on_session_end` (abonné à
`rides.session.ended`, la fin de session de travail du catalogue doc 77) et `wr.factory_fallback`
(cron UTC 21:30 et 22:30 : le handler ne tourne qu'à 23 h de Paris, et seulement si l'usine n'a pas
tourné ce jour-là).

Revision ID: 20261019_0090
Revises: 20261019_0089
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261019_0090"
down_revision: str | None = "20261019_0089"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WORKERS = ("w1_rollups", "w2_causal", "w3_learning", "w4_anomalies", "w5_docket")


def _in(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def upgrade() -> None:
    op.create_table(
        "wr_worker_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("worker", sa.Text(), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("session_ref", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("window_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("items_in", sa.Integer(), nullable=True),
        sa.Column("items_out", sa.Integer(), nullable=True),
        sa.Column("llm_calls", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(_in("worker", WORKERS), name="wr_worker_runs_worker_check"),
        sa.CheckConstraint(_in("trigger", ("session_end", "fallback_cron", "manual")), name="wr_worker_runs_trigger_check"),
        sa.CheckConstraint(_in("status", ("completed", "failed", "partial")), name="wr_worker_runs_status_check"),
        sa.CheckConstraint("window_from <= window_to", name="wr_worker_runs_window_check"),
    )
    op.create_index("wr_worker_runs_created_idx", "wr_worker_runs", ["created_at"])
    op.create_table(
        "wr_worker_cursors",
        sa.Column("worker", sa.Text(), primary_key=True),
        sa.Column("last_processed_event_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_processed_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(_in("worker", WORKERS), name="wr_worker_cursors_worker_check"),
    )
    op.execute(
        """
        INSERT INTO job_definitions
          (id, code, kind, schedule, event_types, handler_ref, enabled, singleton, timeout_s)
        VALUES
          (gen_random_uuid(), 'wr.factory_on_session_end', 'event_subscription', NULL,
           ARRAY['rides.session.ended'], 'app.services.wr.factory:factory_on_session_end_job', false, true, 900),
          (gen_random_uuid(), 'wr.factory_fallback', 'cron', '30 21,22 * * *', NULL,
           'app.services.wr.factory:factory_fallback_job', false, true, 900)
        ON CONFLICT ON CONSTRAINT job_definitions_code_unique DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM job_definitions WHERE code IN ('wr.factory_on_session_end', 'wr.factory_fallback')")
    op.drop_table("wr_worker_cursors")
    op.drop_index("wr_worker_runs_created_idx", table_name="wr_worker_runs")
    op.drop_table("wr_worker_runs")
