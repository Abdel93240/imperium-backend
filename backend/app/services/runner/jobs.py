"""Socle-delivered runner jobs.

- events_heartbeat: the smoke consumer of the E2 consumption contract — the
  events journal finally has a reader, the cursor mechanism is proven.
- backup_nightly: restic wrapper (pg_dump + repo + docs + configs → dedicated
  USB disk + remote target over SSH). The monthly restore drill stays a user act.
"""

import logging
import subprocess
from pathlib import Path

from sqlalchemy import func, select

from app.models.event import Event
from app.services.runner.engine import RunContext, Window

logger = logging.getLogger(__name__)

BACKUP_SCRIPT = Path(__file__).resolve().parents[3].parent / "ops" / "backup" / "restic_nightly.sh"


def events_heartbeat(ctx: RunContext, window: Window) -> None:
    """Count events per type inside the window (metric), advance the cursor."""
    query = select(Event.event_type, func.count(), func.max(Event.occurred_at)).group_by(
        Event.event_type
    )
    if window.from_ts is not None:
        query = query.where(Event.occurred_at > window.from_ts)
    if window.to_ts is not None:
        query = query.where(Event.occurred_at <= window.to_ts)
    rows = ctx.db.execute(query).all()

    counts = {event_type: count for event_type, count, _ in rows}
    total = sum(counts.values())
    ctx.items_in = total
    ctx.items_out = len(counts)
    ctx.detail = {"counts_by_type": counts, "total": total}

    if total:
        latest = ctx.db.execute(
            select(Event.occurred_at, Event.id)
            .where(
                Event.occurred_at > window.from_ts if window.from_ts is not None else True,
                Event.occurred_at <= window.to_ts if window.to_ts is not None else True,
            )
            .order_by(Event.occurred_at.desc(), Event.created_at.desc())
            .limit(1)
        ).first()
        if latest is not None:
            ctx.cursor_ts, ctx.cursor_event_id = latest[0], latest[1]
    elif window.to_ts is not None:
        # Empty window: move the cursor to the window end (no hole, no re-read).
        ctx.cursor_ts = window.to_ts


def backup_nightly(ctx: RunContext, window: Window) -> None:
    if not BACKUP_SCRIPT.exists():
        raise FileNotFoundError(f"Backup script missing: {BACKUP_SCRIPT}")
    completed = subprocess.run(  # noqa: S603 - fixed repo-owned script path
        [str(BACKUP_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=ctx.job.timeout_s,
        check=False,
    )
    ctx.detail = {
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }
    if completed.returncode != 0:
        raise RuntimeError(f"restic_nightly.sh failed with code {completed.returncode}.")
