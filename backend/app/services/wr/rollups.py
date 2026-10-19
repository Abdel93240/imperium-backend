"""W1 — rollups quotidiens par domaine (spec WR §4 W1, carte V18 ACT-WR-03). Code pur.

Sources CANONIQUES seulement (AD-2) : ledger `imperium_vault_transactions` (mêmes règles que le
rapport hebdomadaire : income/expense par type, reversals comptés à part) et dernier
`pressure_snapshots` du jour ; `rides_sessions` / `rides_drop_zones` ; `imperium_missions`.
Pulse : stub neutre (aucune ligne, signalé dans le détail du run) tant que le consentement de
lecture des données de santé par l'usine n'est pas tranché.

Jours recalculés : ceux de la fenêtre ]from, to] (dates de Paris) ET ceux que touchent les lignes
créées ou modifiées dans la fenêtre (une transaction saisie aujourd'hui pour hier recalcule hier).
Chaque jour est réécrit en entier (upsert) : rejouer un lot ne double rien.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.imperium import ImperiumMission
from app.models.rides import RidesDropZone, RidesSession
from app.models.vault import ImperiumVaultTransaction, PressureSnapshot
from app.models.wr import WrRollupDaily

PARIS = ZoneInfo("Europe/Paris")
CLOSED_MISSION_STATUSES = ("completed", "failed", "cancelled")


def touched_days(db: Session, *, user: User, window_from: datetime, window_to: datetime) -> list[date]:
    days = set()
    day = _local(window_from).date()
    while day <= _local(window_to).date():
        days.add(day)
        day += timedelta(days=1)
    days.update(db.scalars(
        select(ImperiumVaultTransaction.local_date).where(
            ImperiumVaultTransaction.user_id == user.id,
            ImperiumVaultTransaction.updated_at > window_from, ImperiumVaultTransaction.updated_at <= window_to)
    ))
    for started_at, ended_at in db.execute(
        select(ImperiumMission.started_at, ImperiumMission.ended_at).where(
            ImperiumMission.user_id == user.id,
            ImperiumMission.updated_at > window_from, ImperiumMission.updated_at <= window_to)
    ):
        days.update(_local(value).date() for value in (started_at, ended_at) if value is not None)
    for started_at, ended_at in db.execute(
        select(RidesSession.started_at, RidesSession.ended_at).where(
            RidesSession.user_id == user.id,
            RidesSession.updated_at > window_from, RidesSession.updated_at <= window_to)
    ):
        days.update(_local(value).date() for value in (started_at, ended_at) if value is not None)
    return sorted(days)


def compute_day(db: Session, *, user: User, day: date) -> dict[str, dict]:
    start = datetime.combine(day, time.min, tzinfo=PARIS)
    end = start + timedelta(days=1)
    return {
        "finance": _finance(db, user, day, start, end),
        "rides": _rides(db, user, start, end),
        "missions": _missions(db, user, start, end),
    }


def rollup_days(db: Session, *, user: User, days: list[date], now: datetime) -> int:
    written = 0
    for day in days:
        for domain, metrics in compute_day(db, user=user, day=day).items():
            db.execute(
                insert(WrRollupDaily)
                .values(user_id=user.id, local_date=day, domain=domain, metrics=metrics, computed_at=now)
                .on_conflict_do_update(
                    constraint="wr_rollups_daily_user_date_domain_unique",
                    set_={"metrics": metrics, "computed_at": now},
                )
            )
            written += 1
    db.flush()
    return written


def _finance(db: Session, user: User, day: date, start: datetime, end: datetime) -> dict:
    rows = db.execute(
        select(ImperiumVaultTransaction.transaction_type, ImperiumVaultTransaction.is_reversal,
               func.count(), func.coalesce(func.sum(ImperiumVaultTransaction.amount_cents), 0))
        .where(ImperiumVaultTransaction.user_id == user.id, ImperiumVaultTransaction.local_date == day)
        .group_by(ImperiumVaultTransaction.transaction_type, ImperiumVaultTransaction.is_reversal)
    ).all()
    income = sum(int(total) for kind, _, _, total in rows if kind == "income")
    expense = sum(int(total) for kind, _, _, total in rows if kind == "expense")
    pressure = db.scalar(
        select(PressureSnapshot.score)
        .where(PressureSnapshot.user_id == user.id, PressureSnapshot.computed_at >= start,
               PressureSnapshot.computed_at < end)
        .order_by(PressureSnapshot.computed_at.desc()).limit(1)
    )
    return {
        "income_cents": income, "expense_cents": expense, "net_cents": income - expense,
        "transaction_count": sum(int(count) for _, _, count, _ in rows),
        "reversal_count": sum(int(count) for _, reversal, count, _ in rows if reversal),
        "pressure_score": pressure,
    }


def _rides(db: Session, user: User, start: datetime, end: datetime) -> dict:
    sessions = db.scalars(
        select(RidesSession).where(RidesSession.user_id == user.id, RidesSession.ended_at >= start,
                                   RidesSession.ended_at < end)
    ).all()
    revenue = sum(session.final_revenue_cents or 0 for session in sessions)
    expense = sum(session.final_expense_cents or 0 for session in sessions)
    minutes = sum(int((session.ended_at - session.started_at).total_seconds() // 60) for session in sessions)
    zones = db.execute(
        select(RidesDropZone.zone, func.count())
        .where(RidesDropZone.user_id == user.id, RidesDropZone.recorded_at >= start, RidesDropZone.recorded_at < end)
        .group_by(RidesDropZone.zone).order_by(func.count().desc(), RidesDropZone.zone).limit(5)
    ).all()
    return {
        "sessions_ended": len(sessions), "revenue_cents": revenue, "expense_cents": expense,
        "worked_minutes": minutes,
        "net_per_hour_cents": round((revenue - expense) * 60 / minutes) if minutes else None,
        "drop_zones": sum(int(count) for _, count in zones),
        "top_zones": [{"zone": zone, "count": int(count)} for zone, count in zones],
    }


def _missions(db: Session, user: User, start: datetime, end: datetime) -> dict:
    started = db.scalar(
        select(func.count()).select_from(ImperiumMission)
        .where(ImperiumMission.user_id == user.id, ImperiumMission.started_at >= start, ImperiumMission.started_at < end)
    )
    ended = db.execute(
        select(ImperiumMission.status, ImperiumMission.ended_at, ImperiumMission.deadline_at)
        .where(ImperiumMission.user_id == user.id, ImperiumMission.ended_at >= start, ImperiumMission.ended_at < end,
               ImperiumMission.status.in_(CLOSED_MISSION_STATUSES))
    ).all()
    late = [(ended_at - deadline).total_seconds() / 60 for status, ended_at, deadline in ended
            if status == "completed" and deadline is not None and ended_at > deadline]
    overdue_open = db.scalar(
        select(func.count()).select_from(ImperiumMission)
        .where(ImperiumMission.user_id == user.id, ImperiumMission.deadline_at < end,
               ImperiumMission.status.not_in(CLOSED_MISSION_STATUSES))
    )
    return {
        "started": started,
        "completed": sum(1 for status, *_ in ended if status == "completed"),
        "failed": sum(1 for status, *_ in ended if status == "failed"),
        "cancelled": sum(1 for status, *_ in ended if status == "cancelled"),
        "completed_late": len(late),
        "avg_deadline_drift_min": round(sum(late) / len(late)) if late else None,
        "overdue_open_at_day_end": overdue_open,
    }


def _local(value: datetime) -> datetime:
    return (value if value.tzinfo else value.replace(tzinfo=UTC)).astimezone(PARIS)
