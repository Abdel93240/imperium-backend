"""Overrides et leur agrégation hebdomadaire (spec Daily §3.4, §10.1-10.2 ; cartes ACT-DLY-07, ACT-DLY-08).

Capture : l'utilisateur prend une autre mission que la proposée → `daily_overrides` avec raison
obligatoire et contexte figé (heure, jour, tranche horaire, les deux missions telles que la sélection
les voyait, versions des barèmes `df.*`). L'override ne démarre rien : l'utilisateur démarre la mission
choisie comme d'habitude.

Agrégation (job `daily.override_aggregation`, semé désactivé) : motif déterministe (domaine proposé,
domaine choisi, tranche horaire) ; un motif qui atteint `daily.override_pattern_min` sur
`daily.override_window_days` dépose un item `ordering_override_pattern` au docket (worker w5) avec
les raisons verbatim et une cible suggérée quand elle est mécanique. AUCUN ajustement automatique :
le réglage reste un acte utilisateur (`PUT /api/daily/settings/scoring`).
"""

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.daily import DailyOverride, DailySelectionLog
from app.models.enums import PrivacyLevel, SourceApp
from app.models.event import Event
from app.models.imperium import ImperiumMission, ImperiumMissionScore
from app.models.wr import WrDocketItem
from app.schemas.daily import OverrideCreate
from app.services.events.emitter import build_event
from app.services.imperium import decision_framework as df
from app.services.params import get_parameter
from app.services.wr import docket

PARIS = ZoneInfo("Europe/Paris")
ITEM_TYPE = "ordering_override_pattern"
MAX_EXAMPLES = 5
# Tranches horaires du motif (heure de Paris, borne basse incluse).
TIME_SLOTS = ((5, "morning"), (12, "afternoon"), (18, "evening"), (23, "night"))


class OverrideError(RuntimeError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class AggregationStats:
    overrides: int = 0
    patterns: int = 0
    items: int = 0
    skipped_open: int = 0


def override_enabled(db: Session) -> bool:
    return bool(get_parameter(db, "daily.override_enabled", default=False))


def time_slot(hour: int) -> str:
    slot = "night"
    for start, name in TIME_SLOTS:
        if hour >= start:
            slot = name
    return slot


def record(db: Session, *, current_user: User, payload: OverrideCreate, now: datetime | None = None) -> DailyOverride:
    """Capture un override (commit). La raison est vérifiée par la route (400) et par la base (CHECK)."""
    now = now or datetime.now(UTC)
    reason = (payload.reason or "").strip()
    if not reason:
        raise OverrideError("A reason is required to override the proposal.", "OVERRIDE_REASON_REQUIRED")
    log = db.get(DailySelectionLog, payload.selection_log_id)
    if log is None or log.user_id != current_user.id:
        raise OverrideError("Selection not found.", "SELECTION_NOT_FOUND")
    if log.chosen_mission_id is None:
        raise OverrideError("This selection proposed no mission.", "OVERRIDE_NO_PROPOSAL")
    if payload.chosen_mission_id == log.chosen_mission_id:
        raise OverrideError("The chosen mission is the proposed one.", "OVERRIDE_SAME_MISSION")
    chosen = db.get(ImperiumMission, payload.chosen_mission_id)
    if chosen is None or chosen.user_id != current_user.id:
        raise OverrideError("Mission not found.", "MISSION_NOT_FOUND")
    if chosen.status != "backlog":
        raise OverrideError("Only a waiting mission can be chosen instead.", "MISSION_NOT_AVAILABLE")
    if db.scalar(select(DailyOverride.id).where(DailyOverride.selection_log_id == log.id)) is not None:
        raise OverrideError("This selection was already overridden.", "OVERRIDE_EXISTS")
    proposed = db.get(ImperiumMission, log.chosen_mission_id)
    row = DailyOverride(user_id=current_user.id, selection_log_id=log.id, proposed_mission_id=proposed.id,
                        chosen_mission_id=chosen.id, reason=reason,
                        context=_context(db, current_user, log, proposed, chosen, now), created_at=now)
    db.add(row)
    db.flush()
    cause = db.scalar(
        select(Event).where(Event.user_id == current_user.id, Event.event_type == "planning.daily.next_proposed",
                            Event.payload["selection_log_id"].astext == str(log.id)).limit(1)
    )
    db.add(build_event(
        db, user_id=current_user.id, event_type="planning.daily.override_recorded",
        payload={"override_id": str(row.id), "selection_log_id": str(log.id), "proposed": str(proposed.id),
                 "chosen": str(chosen.id)},
        idempotency_key=f"planning.daily.override_recorded.{row.id}", source_app=SourceApp.imperium,
        privacy_level=PrivacyLevel.low, causation_id=cause.event_id if cause is not None else None, occurred_at=now,
    ))
    db.commit()
    return row


def _context(db: Session, current_user: User, log: DailySelectionLog, proposed: ImperiumMission,
             chosen: ImperiumMission, now: datetime) -> dict:
    local = now.astimezone(PARIS)
    entries = {entry["mission_id"]: entry for entry in log.feasible_set}
    versions = dict(db.execute(text(
        "SELECT code, version FROM v_parameters_current WHERE code LIKE 'df.%' ORDER BY code")).all())
    return {
        "at_local": local.isoformat(), "hour": local.hour, "weekday": local.isoweekday(),
        "time_slot": time_slot(local.hour), "selection_at": log.at_ts.isoformat(), "scope": log.scope,
        "pulled_forward": log.pulled_forward, "remaining_min": log.remaining_min,
        "proposed": _snapshot(db, current_user, proposed, entries.get(str(proposed.id))),
        "chosen": _snapshot(db, current_user, chosen, entries.get(str(chosen.id))),
        "scale_versions": versions,
    }


def _snapshot(db: Session, current_user: User, mission: ImperiumMission, entry: dict | None) -> dict:
    score = db.scalar(select(ImperiumMissionScore.weighted_score).where(
        ImperiumMissionScore.user_id == current_user.id, ImperiumMissionScore.mission_id == mission.id,
        ImperiumMissionScore.source == df.SOURCE))
    return {
        "mission_id": str(mission.id), "domain": mission.domain, "mission_type_category": mission.mission_type_category,
        "score": float(score) if score is not None else None,
        "deadline_at": mission.deadline_at.isoformat() if mission.deadline_at else None,
        "in_selection": entry is not None, "blocked_by": entry.get("blocked_by") if entry else None,
        "mandatory": entry.get("mandatory") if entry else None, "travel_min": entry.get("travel_min") if entry else None,
    }


def pattern_key(context: dict) -> tuple[str, str, str]:
    return (context["proposed"].get("domain") or "none", context["chosen"].get("domain") or "none",
            context["time_slot"])


def suggested_target(contexts: list[dict]) -> dict:
    """Cible mécanique si elle existe (coefficient d'un domaine, critère C d'une catégorie), sinon discussion."""
    proposed_domain, chosen_domain, _ = pattern_key(contexts[0])
    if proposed_domain != chosen_domain and "none" not in (proposed_domain, chosen_domain):
        return {"kind": "domain_coefficient", "parameter": "df.coefficient_by_position",
                "preferred_domain": chosen_domain, "over_domain": proposed_domain}
    categories = {ctx["chosen"].get("mission_type_category") for ctx in contexts}
    proposed_categories = {ctx["proposed"].get("mission_type_category") for ctx in contexts}
    if len(categories) == 1 and None not in categories and categories.isdisjoint(proposed_categories):
        return {"kind": "criterion_c", "parameter": "df.mission_type_points", "category": categories.pop()}
    return {"kind": "discussion"}


def aggregate(db: Session, *, current_user: User, now: datetime | None = None) -> AggregationStats:
    """Dépose un item par motif au seuil (flush seulement). Un motif déjà ouvert au docket n'est pas redéposé ;
    après une décision, seuls les overrides postérieurs à l'item comptent."""
    now = now or datetime.now(UTC)
    window_days = int(get_parameter(db, "daily.override_window_days", default=28))
    minimum = int(get_parameter(db, "daily.override_pattern_min", default=3))
    rows = db.scalars(
        select(DailyOverride).where(DailyOverride.user_id == current_user.id,
                                    DailyOverride.created_at > now - timedelta(days=window_days),
                                    DailyOverride.created_at <= now)
        .order_by(DailyOverride.created_at)
    ).all()
    stats = AggregationStats(overrides=len(rows))
    groups: dict[tuple, list[DailyOverride]] = defaultdict(list)
    for row in rows:
        groups[pattern_key(row.context)].append(row)
    previous = _previous_items(db, current_user)
    for key, members in sorted(groups.items()):
        last = previous.get(key)
        if last is not None and last.status in docket.OPEN_STATUSES:
            stats.skipped_open += 1
            continue
        if last is not None:
            members = [row for row in members if row.created_at > last.created_at]
        if len(members) < minimum:
            continue
        stats.patterns += 1
        _deposit(db, current_user, key, members, now)
        stats.items += 1
    db.flush()
    return stats


def _previous_items(db: Session, current_user: User) -> dict[tuple, WrDocketItem]:
    latest: dict[tuple, WrDocketItem] = {}
    for item in db.scalars(select(WrDocketItem).where(WrDocketItem.user_id == current_user.id,
                                                      WrDocketItem.item_type == ITEM_TYPE)
                           .order_by(WrDocketItem.created_at)):
        pattern = item.payload.get("pattern") or {}
        latest[(pattern.get("proposed_domain"), pattern.get("chosen_domain"), pattern.get("time_slot"))] = item
    return latest


def _deposit(db: Session, current_user: User, key: tuple, members: list[DailyOverride], now: datetime) -> None:
    proposed_domain, chosen_domain, slot = key
    pattern = {"proposed_domain": proposed_domain, "chosen_domain": chosen_domain, "time_slot": slot}
    docket.create_item(
        db, current_user=current_user, item_type=ITEM_TYPE, domain="daily",
        title_fr=f"Tu choisis souvent {chosen_domain} plutôt que {proposed_domain} ({slot}) : {len(members)} fois",
        payload={"pattern": pattern, "count": len(members),
                 "examples": [row.reason for row in members[-MAX_EXAMPLES:]],
                 "suggested_target": suggested_target([row.context for row in members])},
        evidence_refs={"override_ids": [str(row.id) for row in members]},
        impact_estimate=min(5, 2 + len(members) // 3), source_worker="w5", now=now,
    )


def aggregation_job(ctx, window) -> None:
    """Job `daily.override_aggregation` (semé désactivé) : motifs des 28 derniers jours → docket."""
    from app.services.wr.metrics import _job_user

    now = window.to_ts or datetime.now(UTC)
    ctx.cursor_ts = now
    user = _job_user(ctx.db)
    if user is None:
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"skip": "no_user"}
        return
    stats = aggregate(ctx.db, current_user=user, now=now)
    ctx.db.commit()
    ctx.items_in, ctx.items_out = stats.overrides, stats.items
    ctx.detail = asdict(stats)
