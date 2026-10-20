"""Sélection Niveau 1 (spec Daily §5-7 ; cartes V28 ACT-DLY-04, ACT-DLY-06, ACT-SYS-08). Code pur.

À chaque déclencheur (complétion, démarrage de journée, appel manuel) : temps restant avant le
prochain engagement fixe, portes G1-G5, ensemble obligatoire (échéance aujourd'hui ou en retard),
tri par `weighted_score`, puis départage de la bande de tête par moindre trajet. Aucun modèle,
aucun appel réseau tant que `toolbox.travel_enabled` est faux (repli local marqué). La mission
proposée n'est jamais démarrée ici : l'utilisateur la démarre.

Périmètre (G1) : missions `backlog` (ni annexe, ni engagement fixe) prévues ou échues au plus tard
aujourd'hui (Paris), plus celles du plan courant dont `params.day` est aujourd'hui si le plan WR
est servi. Pull-forward (`daily.pullforward_enabled`) : jour épuisé et temps restant ≥ seuil →
même pipeline sur le reste de la semaine (dates jusqu'à dimanche, plan : semaine courante). Sans
engagement fixe, le temps restant court jusqu'à minuit (Paris). Engagements fixes : missions
`is_fixed_commitment`, plus les événements calendrier `blocks_time` à venir si
`daily.calendar_commitments_enabled` (semé false).

Niveau 2 non codé : un ensemble faisable vide alors que le jour a des missions (C1) ou un conflit
d'obligatoires (C2) est journalisé `arbitration_pending` (level 2) sans arbitrage. G5 (Pulse) lit
la vue contractuelle `v_pulse_active_blocks` quand `daily.g5_enabled` est vrai (sinon porte passante
journalisée `stub`) : un red flag `advise_doctor_and_pause_training` ouvert rejette les missions de
charge physique ≥ `daily.pulse_block_load`, la porte et la source au log.
"""

import logging
import math
import time as clock
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.daily import DailySelectionLog, MissionDependency
from app.models.enums import PrivacyLevel, SourceApp
from app.models.event import Event
from app.models.imperium import ImperiumCalendarEvent, ImperiumMission, ImperiumMissionScore
from app.schemas.daily import DailyCurrentRead, NextMissionRead, QueueEntryRead, QueueRead, SelectionRead
from app.services.daily import prayers
from app.services.events.emitter import build_event
from app.services.imperium import decision_framework as df
from app.services.params import get_parameter
from app.services.travel import LatLng, estimate

logger = logging.getLogger(__name__)

PARIS = ZoneInfo("Europe/Paris")
WEEKDAY_CODES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
GATES = ("G1", "G2", "G3", "G4", "G5")
DEFAULTS = {"top_band_pct": 15, "pullforward_min_threshold": 45, "default_mission_duration": 30,
            "selection_latency_target_ms": 500}


class SelectionError(RuntimeError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class Candidate:
    mission: ImperiumMission
    score: float
    duration_min: int
    travel_min: int
    travel_source: str
    mandatory: bool
    blocked_by: str | None = None
    notes: dict = field(default_factory=dict)

    def entry(self) -> dict:
        passed = list(GATES) if self.blocked_by is None else list(GATES[:GATES.index(self.blocked_by)])
        return {"mission_id": str(self.mission.id), "gates_passed": passed, "blocked_by": self.blocked_by,
                "score": self.score, "duration_min": self.duration_min, "travel_min": self.travel_min,
                "travel_source": self.travel_source, "mandatory": self.mandatory, **self.notes}


@dataclass
class FixedCommitment:
    kind: str  # mission | calendar_event | prayer
    ref: UUID
    at: datetime


@dataclass
class Selection:
    outcome: str
    level: int
    scope: str
    remaining_min: int
    candidates: list[Candidate]
    chosen: Candidate | None = None
    condition: str | None = None
    pulled_forward: bool = False
    next_fixed: FixedCommitment | None = None
    tiebreak: dict | None = None
    ranking: list[Candidate] = field(default_factory=list)


def selection_enabled(db: Session) -> bool:
    return bool(get_parameter(db, "daily.selection_enabled", default=False))


def pullforward_enabled(db: Session) -> bool:
    return bool(get_parameter(db, "daily.pullforward_enabled", default=False))


def calendar_commitments_enabled(db: Session) -> bool:
    return bool(get_parameter(db, "daily.calendar_commitments_enabled", default=False))


def g5_enabled(db: Session) -> bool:
    return bool(get_parameter(db, "daily.g5_enabled", default=False))


def queue_debug_enabled(db: Session) -> bool:
    return bool(get_parameter(db, "daily.queue_debug_enabled", default=False))


def _setting(db: Session, name: str) -> int:
    return int(get_parameter(db, f"daily.{name}", default=DEFAULTS[name]))


# --- Portes : fonctions pures, testées isolément (§5) -------------------------------------------

def gate_status(mission: ImperiumMission) -> bool:
    """G1 : mission en attente, ni annexe (close avec sa porteuse), ni engagement fixe (ancre du temps)."""
    return mission.status == "backlog" and mission.annex_of_mission_id is None and not mission.is_fixed_commitment


def gate_dependencies(mission_id: UUID, open_hard_parents: dict[UUID, int]) -> bool:
    """G2 : tous les parents `hard` complétés."""
    return open_hard_parents.get(mission_id, 0) == 0


def gate_window(mission: ImperiumMission, *, now_local: datetime, travel_min: int, duration_min: int) -> bool:
    """G3 : arrivée (maintenant + trajet) dans [window_start, window_end − durée] un jour valide."""
    arrival = now_local + timedelta(minutes=travel_min)
    if mission.window_days and WEEKDAY_CODES[arrival.weekday()] not in mission.window_days:
        return False
    if mission.window_start is not None and arrival.time() < mission.window_start:
        return False
    if mission.window_end is not None:
        latest = datetime.combine(arrival.date(), mission.window_end, tzinfo=PARIS) - timedelta(minutes=duration_min)
        if arrival > latest:
            return False
    return True


def gate_time(*, travel_min: int, duration_min: int, remaining_min: int) -> bool:
    """G4 : trajet + durée tiennent avant le prochain engagement fixe."""
    return travel_min + duration_min <= remaining_min


def gate_pulse(mission: ImperiumMission, min_loads: list[int]) -> bool:
    """G5 : un blocage Pulse actif rejette les missions dont la charge physique atteint son seuil.

    Charge inconnue (null) : la porte passe. Sans blocage (ou flag G5 éteint) : porte passante."""
    if mission.physical_load is None:
        return True
    return all(mission.physical_load < minimum for minimum in min_loads)


# --- Pipeline -----------------------------------------------------------------------------------

def compute(db: Session, *, current_user: User, now: datetime, origin: LatLng | None) -> Selection:
    """Calcule la sélection sans rien écrire (sert aussi GET queue)."""
    now_local = now.astimezone(PARIS)
    today = now_local.date()
    next_fixed = next_commitment(db, current_user, now, origin=origin)
    horizon = next_fixed.at if next_fixed is not None else datetime.combine(
        today + timedelta(days=1), datetime.min.time(), tzinfo=PARIS)
    remaining_min = max(0, int((horizon - now).total_seconds() // 60))

    day_pool = _pool(db, current_user, today=today, scope="day")
    day = _evaluate(db, current_user, day_pool, now_local=now_local, today=today, remaining_min=remaining_min,
                    origin=origin)
    # Hors G1 (annexe, engagement fixe) : ce qui reste vraiment à faire aujourd'hui.
    day_open = [c for c in day if c.blocked_by != "G1"]
    feasible = [c for c in day_open if c.blocked_by is None]
    mandatory = [c for c in day_open if c.mandatory]
    result = Selection(outcome="day_done", level=1, scope="day", remaining_min=remaining_min, candidates=day,
                       next_fixed=next_fixed)

    blocked_mandatory = [c for c in mandatory if c.blocked_by is not None]
    feasible_mandatory = [c for c in mandatory if c.blocked_by is None]
    if blocked_mandatory or sum(c.travel_min + c.duration_min for c in feasible_mandatory) > remaining_min:
        result.outcome, result.level, result.condition = "arbitration_pending", 2, "mandatory_conflict"
        return result
    if feasible:
        _elect(db, result, feasible_mandatory or feasible, pool="mandatory" if feasible_mandatory else "feasible")
        return result
    if day_open:
        result.outcome, result.level, result.condition = "arbitration_pending", 2, "empty_feasible"
        return result

    if pullforward_enabled(db) and remaining_min >= _setting(db, "pullforward_min_threshold"):
        week_pool = _pool(db, current_user, today=today, scope="week")
        week = _evaluate(db, current_user, week_pool, now_local=now_local, today=today,
                         remaining_min=remaining_min, origin=origin)
        result.scope, result.candidates = "week", week
        week_feasible = [c for c in week if c.blocked_by is None]
        if week_feasible:
            result.pulled_forward = True
            _elect(db, result, week_feasible, pool="week")
    return result


def next_commitment(db: Session, current_user: User, now: datetime,
                    origin: LatLng | None = None) -> FixedCommitment | None:
    """Prochain engagement fixe à venir : mission `is_fixed_commitment`, et, si
    `daily.calendar_commitments_enabled`, événement calendrier `blocks_time` non supprimé. Un événement
    déjà commencé n'est pas une borne (l'appel montre que l'utilisateur est disponible). Si
    `daily.prayer_commitments_enabled`, le départ vers la prochaine prière (mosquée choisie depuis
    `origin`, ou l'adhan pour une prière seul) en est une aussi."""
    anchors = []
    mission = db.execute(
        select(ImperiumMission.id, ImperiumMission.fixed_at).where(
            ImperiumMission.user_id == current_user.id, ImperiumMission.is_fixed_commitment.is_(True),
            ImperiumMission.status == "backlog", ImperiumMission.fixed_at > now,
        ).order_by(ImperiumMission.fixed_at).limit(1)
    ).first()
    if mission is not None:
        anchors.append(FixedCommitment(kind="mission", ref=mission.id, at=mission.fixed_at))
    if calendar_commitments_enabled(db):
        event = db.execute(
            select(ImperiumCalendarEvent.id, ImperiumCalendarEvent.starts_at).where(
                ImperiumCalendarEvent.user_id == current_user.id, ImperiumCalendarEvent.blocks_time.is_(True),
                ImperiumCalendarEvent.deleted_at.is_(None), ImperiumCalendarEvent.starts_at > now,
            ).order_by(ImperiumCalendarEvent.starts_at, ImperiumCalendarEvent.id).limit(1)
        ).first()
        if event is not None:
            anchors.append(FixedCommitment(kind="calendar_event", ref=event.id, at=event.starts_at))
    if prayers.enabled(db):
        plan = prayers.next_prayer(db, user=current_user, now=now, origin=origin)
        if plan is not None:
            day = plan.reference_adhan.astimezone(PARIS).date()
            anchors.append(FixedCommitment(kind="prayer", ref=prayers.commitment_ref(current_user, day, plan.prayer),
                                           at=plan.bound))
    return min(anchors, key=lambda anchor: anchor.at) if anchors else None


def select_next(
    db: Session,
    *,
    current_user: User,
    trigger: str,
    trigger_ref: UUID | None = None,
    origin: LatLng | None = None,
    causation_event: Event | None = None,
    now: datetime | None = None,
) -> DailySelectionLog:
    """Sélectionne, journalise et émet ; flush seulement. Ne touche jamais la mission active."""
    started = clock.perf_counter()
    now = now or datetime.now(UTC)
    active = db.scalar(select(ImperiumMission.id).where(ImperiumMission.user_id == current_user.id,
                                                       ImperiumMission.status == "active"))
    if active is not None:
        raise SelectionError("A mission is already active; the selection never touches it.", "MISSION_ACTIVE")
    result = compute(db, current_user=current_user, now=now, origin=origin)
    latency_ms = int((clock.perf_counter() - started) * 1000)
    row = DailySelectionLog(
        user_id=current_user.id, trigger=trigger, trigger_ref=trigger_ref, at_ts=now,
        remaining_min=result.remaining_min, next_fixed_ref=result.next_fixed.ref if result.next_fixed else None,
        next_fixed_kind=result.next_fixed.kind if result.next_fixed else None,
        scope=result.scope, feasible_set=[c.entry() for c in result.candidates],
        mandatory_set=[str(c.mission.id) for c in result.candidates if c.mandatory],
        chosen_mission_id=result.chosen.mission.id if result.chosen else None, tiebreak_applied=result.tiebreak,
        outcome=result.outcome, condition=result.condition, pulled_forward=result.pulled_forward,
        level=result.level, latency_ms=latency_ms,
    )
    db.add(row)
    db.flush()
    if latency_ms > _setting(db, "selection_latency_target_ms"):
        logger.warning("Daily selection over latency target.", extra={"latency_ms": latency_ms})
    _emit(db, current_user, row, causation_event)
    return row


def _pool(db: Session, current_user: User, *, today: date, scope: str) -> list[ImperiumMission]:
    end_of_today = datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=PARIS)
    if scope == "day":
        start, end = None, end_of_today
    else:
        start, end = end_of_today, end_of_today + timedelta(days=6 - today.weekday())
    dated = []
    for column in (ImperiumMission.planned_start_at, ImperiumMission.deadline_at):
        condition = column < end if start is None else (column >= start) & (column < end)
        dated.append(condition)
    rows = db.scalars(
        select(ImperiumMission).where(ImperiumMission.user_id == current_user.id,
                                      ImperiumMission.status == "backlog", dated[0] | dated[1])
    ).all()
    missions = {mission.id: mission for mission in rows}
    for mission_id in _plan_mission_ids(db, current_user, today=today, scope=scope):
        if mission_id not in missions:
            mission = db.get(ImperiumMission, mission_id)
            if mission is not None and mission.user_id == current_user.id and mission.status == "backlog":
                missions[mission_id] = mission
    if scope == "week":
        # Une mission échue ou prévue aujourd'hui relève du jour, jamais de l'avance.
        missions = {key: m for key, m in missions.items()
                    if not any(value is not None and value < end_of_today for value in (m.planned_start_at, m.deadline_at))}
    return sorted(missions.values(), key=lambda m: (m.created_at, str(m.id)))


def _plan_mission_ids(db: Session, current_user: User, *, today: date, scope: str) -> list[UUID]:
    from app.services.wr import plan as wr_plan

    if not wr_plan.plan_enabled(db):
        return []
    current = wr_plan.current_plan(db, current_user=current_user)
    if current is None or not current.horizon_start <= today <= current.horizon_end:
        return []
    week = (today - current.horizon_start).days // 7 + 1
    ids = []
    for item in current.plan.get("items", []):
        kind, _, ref = item["ref"].partition(":")
        if kind != "mission":
            continue
        in_scope = (item.get("params") or {}).get("day") == today.isoformat() if scope == "day" else item["week"] == week
        if in_scope:
            try:
                ids.append(UUID(ref))
            except ValueError:
                continue
    return ids


def _evaluate(db: Session, current_user: User, missions: list[ImperiumMission], *, now_local: datetime, today: date,
              remaining_min: int, origin: LatLng | None) -> list[Candidate]:
    if not missions:
        return []
    ids = [mission.id for mission in missions]
    scores = dict(db.execute(
        select(ImperiumMissionScore.mission_id, ImperiumMissionScore.weighted_score)
        .where(ImperiumMissionScore.user_id == current_user.id, ImperiumMissionScore.source == df.SOURCE,
               ImperiumMissionScore.mission_id.in_(ids))
    ).all())
    parent = ImperiumMission.__table__.alias("parent")
    open_parents: dict[UUID, int] = {}
    for child_id, in db.execute(
        select(MissionDependency.child_mission_id)
        .join(parent, parent.c.id == MissionDependency.parent_mission_id)
        .where(MissionDependency.child_mission_id.in_(ids), MissionDependency.hard.is_(True),
               parent.c.status != "completed")
    ).all():
        open_parents[child_id] = open_parents.get(child_id, 0) + 1
    default_duration = _setting(db, "default_mission_duration")
    g5_status, blocks = _pulse_blocks(db, current_user)
    candidates = []
    for mission in missions:
        duration = mission.estimated_minutes or default_duration
        travel_min, travel_source = _travel(db, origin, mission, now_local)
        deadline_local = mission.deadline_at.astimezone(PARIS).date() if mission.deadline_at else None
        candidate = Candidate(mission=mission, score=float(scores.get(mission.id) or 0), duration_min=duration,
                              travel_min=travel_min, travel_source=travel_source,
                              mandatory=deadline_local is not None and deadline_local <= today,
                              notes={"g5": g5_status})
        if not gate_status(mission):
            candidate.blocked_by = "G1"
        elif not gate_dependencies(mission.id, open_parents):
            candidate.blocked_by = "G2"
        elif not gate_window(mission, now_local=now_local, travel_min=travel_min, duration_min=duration):
            candidate.blocked_by = "G3"
        elif not gate_time(travel_min=travel_min, duration_min=duration, remaining_min=remaining_min):
            candidate.blocked_by = "G4"
        elif not gate_pulse(mission, [block["min_physical_load"] for block in blocks]):
            candidate.blocked_by = "G5"
            candidate.notes["g5_blocks"] = [block["source_ref"] for block in blocks]
        candidates.append(candidate)
    return candidates


def _pulse_blocks(db: Session, current_user: User) -> tuple[str, list[dict]]:
    """G5 lit UNIQUEMENT la vue contractuelle `v_pulse_active_blocks` (FINDINGS C-4) ; flag éteint : stub."""
    if not g5_enabled(db):
        return "stub", []
    rows = db.execute(
        text("SELECT min_physical_load, source_ref FROM v_pulse_active_blocks WHERE user_id = :user_id "
             "AND block_kind = 'pause_training' ORDER BY since"),
        {"user_id": current_user.id},
    ).all()
    blocks = [{"min_physical_load": int(row.min_physical_load), "source_ref": str(row.source_ref)} for row in rows]
    return ("blocked" if blocks else "clear"), blocks


def _travel(db: Session, origin: LatLng | None, mission: ImperiumMission, now_local: datetime) -> tuple[int, str]:
    if origin is None or mission.location_lat is None:
        return 0, "none"
    dest = LatLng(float(mission.location_lat), float(mission.location_lng))
    result = estimate(origin, dest, now_local.astimezone(UTC), db=db)
    source = "cache" if result.cached else ("fallback" if result.provider == "local_fallback" else result.provider)
    return math.ceil(result.duration_s / 60), source


def _elect(db: Session, result: Selection, candidates: list[Candidate], *, pool: str) -> None:
    """Tri par score, bande de tête (≥ (1 − pct) × max), élu = moindre trajet ; égalité → score, échéance, création."""
    ranking = sorted(candidates, key=lambda c: (-c.score, _deadline_key(c), c.mission.created_at, str(c.mission.id)))
    top = ranking[0].score
    band_pct = _setting(db, "top_band_pct")
    floor = (1 - band_pct / 100) * top
    band = [c for c in ranking if c.score >= floor]
    chosen = min(band, key=lambda c: (c.travel_min, ranking.index(c)))
    reason = "only_candidate" if len(band) == 1 else ("least_travel" if chosen is not ranking[0] else "top_score")
    result.outcome, result.chosen, result.ranking = "next_mission", chosen, ranking
    result.tiebreak = {
        "band_pct": band_pct, "band_floor": round(floor, 2), "band_members": [str(c.mission.id) for c in band],
        "travel_costs": {str(c.mission.id): {"travel_min": c.travel_min, "travel_source": c.travel_source} for c in band},
        "winner_reason": reason, "pool": pool,
    }


def _deadline_key(candidate: Candidate) -> datetime:
    return candidate.mission.deadline_at or datetime.max.replace(tzinfo=UTC)


def _emit(db: Session, current_user: User, row: DailySelectionLog, causation_event: Event | None) -> None:
    causation = causation_event.event_id if causation_event is not None else None
    if row.outcome == "arbitration_pending":
        events = [("planning.daily.arbitration_required",
                   {"selection_log_id": str(row.id), "kind": row.condition, "level": row.level})]
    else:
        events = [("planning.daily.next_proposed",
                   {"selection_log_id": str(row.id),
                    "mission_id": str(row.chosen_mission_id) if row.chosen_mission_id else None,
                    "outcome": row.outcome, "level": row.level, "pulled_forward": row.pulled_forward})]
        if row.pulled_forward:
            events.append(("planning.daily.pullforward_applied",
                           {"selection_log_id": str(row.id), "mission_id": str(row.chosen_mission_id)}))
    parent = None
    for event_type, payload in events:
        event = build_event(
            db, user_id=current_user.id, event_type=event_type, payload=payload,
            idempotency_key=f"{event_type}.{row.id}", source_app=SourceApp.imperium, privacy_level=PrivacyLevel.low,
            causation_id=parent.event_id if parent is not None else causation,
        )
        db.add(event)
        db.flush()
        parent = event


# --- Lecture -------------------------------------------------------------------------------------

def to_read(db: Session, row: DailySelectionLog) -> SelectionRead:
    next_mission = None
    if row.chosen_mission_id is not None:
        mission = db.get(ImperiumMission, row.chosen_mission_id)
        entry = next((e for e in row.feasible_set if e["mission_id"] == str(row.chosen_mission_id)), {})
        if mission is not None:
            next_mission = NextMissionRead(id=mission.id, title=mission.title, domain=mission.domain,
                                           estimated_minutes=mission.estimated_minutes,
                                           location_label=mission.location_label,
                                           travel_source=entry.get("travel_source", "none"))
    return SelectionRead(selection_log_id=row.id, outcome=row.outcome, level=row.level, condition=row.condition,
                         pulled_forward=row.pulled_forward, next_mission=next_mission)


def last_for_trigger(db: Session, *, current_user: User, trigger: str, trigger_ref: UUID) -> DailySelectionLog | None:
    return db.scalar(
        select(DailySelectionLog).where(DailySelectionLog.user_id == current_user.id,
                                        DailySelectionLog.trigger == trigger, DailySelectionLog.trigger_ref == trigger_ref)
        .order_by(DailySelectionLog.created_at.desc()).limit(1)
    )


def current(db: Session, *, current_user: User, now: datetime | None = None) -> DailyCurrentRead:
    now = now or datetime.now(UTC)
    active = db.scalar(select(ImperiumMission.id).where(ImperiumMission.user_id == current_user.id,
                                                       ImperiumMission.status == "active"))
    start_of_day = datetime.combine(now.astimezone(PARIS).date(), datetime.min.time(), tzinfo=PARIS)
    last = db.scalar(
        select(DailySelectionLog).where(DailySelectionLog.user_id == current_user.id,
                                        DailySelectionLog.at_ts >= start_of_day)
        .order_by(DailySelectionLog.at_ts.desc(), DailySelectionLog.created_at.desc()).limit(1)
    )
    return DailyCurrentRead(active_mission_id=active, last_selection=to_read(db, last) if last else None)


def selection_log(db: Session, *, current_user: User, day: date) -> list[DailySelectionLog]:
    start = datetime.combine(day, datetime.min.time(), tzinfo=PARIS)
    return list(db.scalars(
        select(DailySelectionLog).where(DailySelectionLog.user_id == current_user.id,
                                        DailySelectionLog.at_ts >= start,
                                        DailySelectionLog.at_ts < start + timedelta(days=1))
        .order_by(DailySelectionLog.at_ts, DailySelectionLog.created_at)
    ))


def queue(db: Session, *, current_user: User, origin: LatLng | None = None, now: datetime | None = None) -> QueueRead:
    """Admin/debug : la sélection telle qu'elle serait faite maintenant, sans écrire."""
    result = compute(db, current_user=current_user, now=now or datetime.now(UTC), origin=origin)
    return QueueRead(
        outcome=result.outcome, scope=result.scope, condition=result.condition, remaining_min=result.remaining_min,
        next_fixed_ref=result.next_fixed.ref if result.next_fixed else None,
        next_fixed_kind=result.next_fixed.kind if result.next_fixed else None,
        chosen_mission_id=result.chosen.mission.id if result.chosen else None,
        ranking=[c.mission.id for c in result.ranking],
        entries=[QueueEntryRead(mission_id=c.mission.id, title=c.mission.title, score=c.score, mandatory=c.mandatory,
                                blocked_by=c.blocked_by, travel_min=c.travel_min, travel_source=c.travel_source,
                                duration_min=c.duration_min) for c in result.candidates],
    )


def day_start_selection(ctx) -> dict:
    """Sélection initiale du job `daily.day_start` (déclenché par le clic explicite « Démarrer la journée »)."""
    if not selection_enabled(ctx.db):
        return {"selection": "disabled"}
    from app.services.wr.metrics import _job_user

    user = _job_user(ctx.db)
    if user is None:
        return {"selection": "no_user"}
    trigger_event = ctx.db.get(Event, ctx.trigger_ref) if ctx.trigger_ref is not None else None
    try:
        row = select_next(ctx.db, current_user=user, trigger="day_start",
                          trigger_ref=trigger_event.id if trigger_event is not None else None,
                          causation_event=trigger_event)
    except SelectionError as exc:
        return {"selection": exc.code}
    ctx.db.commit()
    return {"selection": row.outcome, "selection_log_id": str(row.id)}
