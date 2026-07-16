"""toolbox.runner — the single execution mechanism of the ecosystem (n8n successor).

APScheduler (cron) + Postgres LISTEN/NOTIFY (event subscriptions) + advisory
locks (singleton jobs), with Postgres as the only state (job_definitions,
job_runs, job_cursors). No Celery, no Redis, no external queue.

Rules (generalised wr_worker_* pattern):
- a failed run never advances its cursor;
- singleton jobs take pg_try_advisory_lock(hashtext(code)) — a concurrent
  launch is recorded as skipped, never doubled;
- runner_enabled=False → every job registers, none executes (dry-run logged
  as a skipped job_run);
- an unreachable GPU service never fails a job: skip logged (+ notification
  when severity justifies it).
"""

from app.services.runner.engine import RunContext, Window, execute_job

__all__ = ["RunContext", "Window", "execute_job"]
