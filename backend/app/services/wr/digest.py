"""Digest du WR : instantané figé assemblé par le code à l'ouverture (spec WR §3.6, §9 P1).

Contenu : les items ouverts du docket, groupés par type, chaque type plafonné par
`wr.digest_caps` (un type sans plafond n'est limité que par le plafond de tokens), puis
plafond dur `wr.digest_token_cap` : on retire les items les moins prioritaires d'abord,
jamais au hasard ; rouges et décisions forcées ne sortent qu'en dernier recours.
Section `rollups` : totaux de la semaine par domaine depuis `wr_rollups_daily` (W1). Section
`anomalies` : journées hors green des signaux W4 de la semaine, |z| décroissant, au plus
`wr.digest_anomaly_signals_cap`. Section `plan_state` : le plan courant (v_plan_current, deltas
appliqués) quand `wr.plan_enabled` est vrai et qu'une version est active ; sinon `unavailable`.
Le job `wr.digest_on_open` (abonné à `planning.weekly_review.launched`, semé désactivé)
assemble le digest au lancement du WR.

Whitelist assembleur : seules les sections listées peuvent entrer, et jamais de brut
device, de contenu conversationnel ni de document médical — les références suffisent.
Une tentative lève DigestWhitelistError.
"""

import json
import math
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import ImperiumWeeklyReviewSession
from app.models.event import Event
from app.models.toolbox import SignalValue
from app.models.wr import WrDigest, WrRollupDaily
from app.services.events.emitter import build_event
from app.services.params import get_parameter
from app.services.wr import docket, plan

ALLOWED_SECTIONS = frozenset({
    "window", "docket", "counts", "rollups", "anomalies", "plan_state", "truncated", "unavailable",
})
FORBIDDEN_KEYS = frozenset({
    "conversation", "messages", "transcript", "raw", "raw_text", "device_raw", "sensor_samples",
    "document_text", "ocr_text", "medical_document", "medical_text", "file_bytes", "image", "audio",
})
ENTRY_FIELDS = (
    "id", "item_type", "domain", "title_fr", "payload", "evidence_refs", "confidence", "impact_estimate",
    "severity", "priority", "force_decision", "consecutive_defers",
)
CLOSED_SESSION_STATUSES = ("stored", "cancelled", "failed")
PARIS = ZoneInfo("Europe/Paris")
SUMMED = {
    "finance": ("income_cents", "expense_cents", "net_cents", "transaction_count", "reversal_count"),
    "rides": ("sessions_ended", "revenue_cents", "expense_cents", "worked_minutes", "drop_zones"),
    "missions": ("started", "completed", "failed", "cancelled", "completed_late"),
}


class DigestWhitelistError(ValueError):
    pass


class DigestStateError(RuntimeError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def check_section(name: str) -> None:
    if name not in ALLOWED_SECTIONS:
        raise DigestWhitelistError(f"Section '{name}' is not allowed in the WR digest.")


def current_digest(db: Session, *, current_user: User) -> WrDigest | None:
    session = _open_session(db, current_user)
    if session is None:
        return None
    return db.scalar(select(WrDigest).where(WrDigest.review_session_id == session.id))


def assemble_digest(db: Session, *, current_user: User) -> tuple[WrDigest, bool]:
    """Assemble le digest de la session WR ouverte ; rend l'existant s'il est déjà figé."""
    session = _open_session(db, current_user)
    if session is None:
        raise DigestStateError("No open weekly review: launch it before assembling the digest.", "WR_NOT_OPEN")
    existing = db.scalar(select(WrDigest).where(WrDigest.review_session_id == session.id))
    if existing is not None:
        return existing, False

    caps: dict[str, int] = get_parameter(db, "wr.digest_caps", default={})
    token_cap = int(get_parameter(db, "wr.digest_token_cap", default=40000))
    open_items = [
        item for item in docket.list_items(db, current_user=current_user) if item.status in docket.OPEN_STATUSES
    ]
    open_counts: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    for item in open_items:  # déjà triés : décisions forcées puis priorité
        open_counts[item.item_type] = open_counts.get(item.item_type, 0) + 1
        cap = caps.get(item.item_type)
        if cap is not None and open_counts[item.item_type] > cap:
            continue
        entry = item.model_dump(mode="json", include=set(ENTRY_FIELDS))
        _check_no_raw(entry["payload"])
        _check_no_raw(entry["evidence_refs"])
        selected.append(entry)

    extras = {
        "rollups": _rollups(db, current_user, session.week_start, session.week_end),
        "anomalies": _anomalies(db, current_user, session.week_start, session.week_end,
                                cap=int(get_parameter(db, "wr.digest_anomaly_signals_cap", default=20))),
        "plan_state": _plan_state(db, current_user),
    }
    _check_no_raw(extras)
    content = _build(session, selected, open_counts, extras, truncated=False)
    while selected and _estimate(content) > token_cap:
        selected.remove(_least_priority(selected))
        content = _build(session, selected, open_counts, extras, truncated=True)
    for name in content:
        check_section(name)

    row = WrDigest(
        id=uuid4(), user_id=current_user.id, review_session_id=session.id, window_from=session.week_start,
        window_to=session.week_end, digest=content, token_estimate=_estimate(content),
    )
    db.add(row)
    db.flush()
    db.add(build_event(
        db, user_id=current_user.id, event_type="planning.wr_digest.assembled",
        payload={"digest_id": str(row.id), "review_session_id": str(session.id),
                 "token_estimate": row.token_estimate, "items": len(selected)},
        idempotency_key=f"planning.wr_digest.assembled.{row.id}", source_app=SourceApp.imperium,
        privacy_level=PrivacyLevel.medium,
    ))
    db.commit()
    db.refresh(row)
    return row, True


def _open_session(db: Session, current_user: User) -> ImperiumWeeklyReviewSession | None:
    session = db.scalar(
        select(ImperiumWeeklyReviewSession)
        .where(ImperiumWeeklyReviewSession.user_id == current_user.id)
        .order_by(ImperiumWeeklyReviewSession.created_at.desc())
        .limit(1)
    )
    if session is None or session.launched_at is None or session.status in CLOSED_SESSION_STATUSES:
        return None
    return session


def _build(session: ImperiumWeeklyReviewSession, selected: list[dict], open_counts: dict[str, int], extras: dict,
           *, truncated: bool) -> dict:
    sections: dict[str, list[dict]] = {}
    for entry in selected:
        sections.setdefault(entry["item_type"], []).append(entry)
    return {
        "window": {"from": session.week_start.isoformat(), "to": session.week_end.isoformat()},
        "docket": sections,
        "counts": {
            item_type: {"open": total, "included": len(sections.get(item_type, []))}
            for item_type, total in sorted(open_counts.items())
        },
        "rollups": extras["rollups"],
        "anomalies": extras["anomalies"],
        **({"plan_state": extras["plan_state"]} if extras["plan_state"] is not None else {}),
        "truncated": truncated,
        "unavailable": [] if extras["plan_state"] is not None else ["plan_state"],
    }


def _plan_state(db: Session, current_user: User) -> dict | None:
    if not plan.plan_enabled(db):
        return None
    current = plan.current_plan(db, current_user=current_user)
    if current is None:
        return None
    return {"plan_version_id": str(current.plan_version_id), "origin": current.origin,
            "horizon_start": current.horizon_start.isoformat(), "horizon_end": current.horizon_end.isoformat(),
            "applied_deltas": len(current.applied_delta_ids), "plan": current.plan}


def _rollups(db: Session, current_user: User, first: date, last: date) -> dict:
    rows = db.execute(
        select(WrRollupDaily.domain, WrRollupDaily.local_date, WrRollupDaily.metrics)
        .where(WrRollupDaily.user_id == current_user.id, WrRollupDaily.local_date >= first,
               WrRollupDaily.local_date <= last)
        .order_by(WrRollupDaily.local_date)
    ).all()
    summary: dict[str, dict] = {}
    for domain, _day, metrics in rows:
        bucket = summary.setdefault(domain, {"days": 0, **{key: 0 for key in SUMMED.get(domain, ())}})
        bucket["days"] += 1
        for key in SUMMED.get(domain, ()):
            bucket[key] += int(metrics.get(key) or 0)
        if domain == "finance" and metrics.get("pressure_score") is not None:
            bucket["pressure_last"] = metrics["pressure_score"]
            bucket["pressure_max"] = max(bucket.get("pressure_max", 0), metrics["pressure_score"])
        if domain == "missions":
            bucket["overdue_open_last_day"] = metrics.get("overdue_open_at_day_end")
    rides = summary.get("rides")
    if rides is not None:
        rides["net_per_hour_cents"] = (
            round((rides["revenue_cents"] - rides["expense_cents"]) * 60 / rides["worked_minutes"])
            if rides["worked_minutes"] else None
        )
    return summary


def _anomalies(db: Session, current_user: User, first: date, last: date, *, cap: int) -> list[dict]:
    start = datetime.combine(first, time.min, tzinfo=PARIS)
    end = datetime.combine(last + timedelta(days=1), time.min, tzinfo=PARIS)
    rows = db.scalars(
        select(SignalValue).where(
            SignalValue.signal_code.like("wr.%"), SignalValue.band.is_not(None), SignalValue.band != "green",
            SignalValue.measured_at >= start, SignalValue.measured_at < end,
            SignalValue.detail["user_id"].astext == str(current_user.id))
    ).all()
    rows = sorted(rows, key=lambda row: (-abs(float(row.detail.get("z") or 0)), row.signal_code))[:cap]
    return [
        {"signal_code": row.signal_code, "local_date": row.detail.get("local_date"), "band": row.band,
         "value": float(row.value) if row.value is not None else None, "baseline": row.detail.get("baseline"),
         "z": row.detail.get("z"), "unexplained": bool((row.flags or {}).get("unexplained"))}
        for row in rows
    ]


def digest_on_open_job(ctx, window) -> None:
    """Job `wr.digest_on_open` : assemble le digest de la session WR qui vient d'être lancée."""
    ctx.cursor_ts = window.to_ts or datetime.now(UTC)
    event = ctx.db.scalar(select(Event).where(Event.id == ctx.trigger_ref)) if ctx.trigger_ref else None
    user = ctx.db.get(User, event.user_id) if event is not None else None
    if user is None:
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"skipped": "no_launch_event"}
        return
    try:
        row, created = assemble_digest(ctx.db, current_user=user)
    except DigestStateError as exc:
        ctx.items_in, ctx.items_out = 1, 0
        ctx.detail = {"skipped": exc.code}
        return
    ctx.items_in, ctx.items_out = 1, int(created)
    ctx.detail = {"digest_id": str(row.id), "created": created, "token_estimate": row.token_estimate}


def _least_priority(selected: list[dict]) -> dict:
    """Le moins prioritaire sort d'abord ; rouges et décisions forcées sortent en dernier."""
    unprotected = [entry for entry in selected if not (entry["severity"] == "red" or entry["force_decision"])]
    return (unprotected or selected)[-1]


def _estimate(content: dict) -> int:
    return math.ceil(len(json.dumps(content, ensure_ascii=False)) / 4)


def _check_no_raw(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in FORBIDDEN_KEYS:
                raise DigestWhitelistError(f"Raw content key '{key}' is not allowed in the WR digest.")
            _check_no_raw(nested)
    elif isinstance(value, list):
        for nested in value:
            _check_no_raw(nested)
