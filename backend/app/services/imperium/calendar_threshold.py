"""Règle des 7 jours du calendrier (doc 51 §6, §8, §11 ; doc 52 trigger 4).

Un événement à plus de 7 jours est seulement rangé. Dès qu'une occurrence tombe dans les 7 jours (ajout,
modification, suppression, ou entrée dans la fenêtre au contrôle du matin) :
- le hook `user.calendar.event_<change>` est émis (le recalcul du score des missions concernées s'y abonnera) ;
- la proposition du jour est recalculée si une journée est ouverte sans mission en cours (rien ne démarre) ;
- une échéance sans préparation reçoit un créneau proposé, à valider : par le slot cloud
  `calendar.deadline_plan` s'il est servi, sinon par règles (le premier créneau libre, de jour, avant l'échéance).

Contrôle du matin (job `calendar.morning_check`, 6 h de Paris, semé désactivé) : fenêtre des 7 jours ; la veille
et le jour d'une échéance sans préparation faite, une mission urgente (doc 51 §8.2) ; échéance passée sans
préparation faite → `deadline_missed` (la suite se décide avec l'utilisateur, comme une mission ratée).
"""

import logging
from datetime import UTC, datetime, time, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.imperium import ImperiumCalendarEvent, ImperiumMission
from app.schemas.imperium import CalendarConflictCheck
from app.services.ai import cloud
from app.services.events.emitter import build_event
from app.services.imperium import calendar, calendar_recurrence

logger = logging.getLogger(__name__)

PARIS = calendar.PARIS
WINDOW_DAYS = 7
PLAN_SLOT = "calendar.deadline_plan"
DAY_HOURS = (8, 20)  # créneaux de préparation proposés entre 8 h et 20 h
DEFAULT_PREP_MINUTES = 60
MORNING_HOUR = 6


def next_occurrence(event: ImperiumCalendarEvent, now: datetime) -> datetime | None:
    found = calendar_recurrence.occurrences(event.starts_at, event.recurrence_rrule, window_from=now,
                                            window_to=now + timedelta(days=366), limit=1)
    if found:
        return found[0]
    ongoing = event.ends_at is not None and event.starts_at <= now <= event.ends_at
    return event.starts_at if ongoing else None


def in_window(event: ImperiumCalendarEvent, now: datetime) -> bool:
    upcoming = next_occurrence(event, now)
    return upcoming is not None and upcoming <= now + timedelta(days=WINDOW_DAYS)


def after_change(db: Session, *, current_user: User, event: ImperiumCalendarEvent, change: str,
                 now: datetime | None = None) -> bool:
    """Après un changement : rien au-delà de 7 jours ; sinon hook, proposition du jour, préparation. Ne lève pas."""
    now = now or datetime.now(UTC)
    try:
        if change != "deleted" and not in_window(event, now):
            return False
        if change == "deleted" and not (now - timedelta(days=1) <= event.starts_at <= now + timedelta(days=WINDOW_DAYS)):
            return False
        db.add(build_event(db, user_id=current_user.id, event_type=f"user.calendar.event_{change}",
                           payload={"calendar_event_id": str(event.id), "event_type": event.event_type},
                           idempotency_key=f"user.calendar.event_{change}:{event.id}:{uuid4().hex}"))
        db.commit()
        if change != "deleted" and event.event_type == "deadline" and event.status == "active":
            propose_prep(db, current_user=current_user, event=event, now=now)
        _reselect(db, current_user, now)
        return True
    except Exception:  # noqa: BLE001 - un effet de bord du calendrier ne casse jamais l'écriture de l'utilisateur
        db.rollback()
        logger.exception("Calendar threshold failed.", extra={"calendar_event_id": str(event.id)})
        return False


def propose_prep(db: Session, *, current_user: User, event: ImperiumCalendarEvent, now: datetime) -> dict | None:
    """Créneau de préparation d'une échéance, à valider (doc 51 §8.1) ; rien si déjà décidé ou préparée."""
    if event.prep_mission_id is not None or (event.prep_proposal or {}).get("status") in ("proposed", "accepted"):
        return None
    minutes = event.prep_minutes or DEFAULT_PREP_MINUTES
    start = _cloud_slot(db, current_user, event, minutes, now) or _rules_slot(db, current_user, event, minutes, now)
    if start is None:
        proposal = {"status": "none", "rationale": "Plus assez de temps libre avant l'échéance : fais-la dès que possible.",
                    "source": "rules", "at": now.isoformat()}
    else:
        start, rationale, source = start
        proposal = {"status": "proposed", "starts_at": start.isoformat(),
                    "ends_at": (start + timedelta(minutes=minutes)).isoformat(), "rationale": rationale,
                    "source": source, "at": now.isoformat()}
    event = db.get(ImperiumCalendarEvent, event.id)
    event.prep_proposal = proposal
    db.commit()
    return proposal


def morning_check(db: Session, *, current_user: User, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    today = now.astimezone(PARIS).date()
    counts = {"entering": 0, "urgent": 0, "missed": 0, "completed": 0}
    events = list(db.scalars(select(ImperiumCalendarEvent).where(
        ImperiumCalendarEvent.user_id == current_user.id, ImperiumCalendarEvent.deleted_at.is_(None),
        ImperiumCalendarEvent.status == "active")))
    for event in events:
        upcoming = next_occurrence(event, now)
        if upcoming is not None and now + timedelta(days=WINDOW_DAYS - 1) < upcoming <= now + timedelta(days=WINDOW_DAYS):
            counts["entering"] += after_change(db, current_user=current_user, event=event, change="entering", now=now)
        if event.event_type != "deadline":
            continue
        mission = db.get(ImperiumMission, event.prep_mission_id) if event.prep_mission_id else None
        if mission is not None and mission.status == "completed":
            event.status = "completed"
            counts["completed"] += 1
        elif event.starts_at < now:
            event.status = "deadline_missed"
            counts["missed"] += 1
        elif event.starts_at.astimezone(PARIS).date() - today <= timedelta(days=1) and event.last_urgent_on != today:
            _urgent(db, current_user, event, mission, today)
            counts["urgent"] += 1
    db.commit()
    return counts


def morning_check_job(ctx, window) -> None:
    """Job `calendar.morning_check` : à 6 h de Paris (deux horaires UTC pour les deux heures légales)."""
    from app.services.wr.metrics import _job_user

    now = window.to_ts or datetime.now(UTC)
    if ctx.trigger != "manual" and now.astimezone(PARIS).hour != MORNING_HOUR:
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"skipped": "not_morning_hour"}
        return
    user = _job_user(ctx.db)
    if user is None:
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"skipped": "no_user"}
        return
    ctx.detail = morning_check(ctx.db, current_user=user, now=now)
    ctx.items_in = sum(ctx.detail.values())
    ctx.items_out = ctx.detail["urgent"]


# ---------- internes ----------

def _urgent(db: Session, user: User, event: ImperiumCalendarEvent, mission: ImperiumMission | None, today) -> None:
    """La veille ou le jour J sans préparation faite : la mission devient urgente pour aujourd'hui."""
    from app.schemas.operations import IntrinsicMissionCreate
    from app.services.imperium import operations

    when = "aujourd'hui" if event.starts_at.astimezone(PARIS).date() == today else "demain"
    title = f"URGENT : {calendar.prep_title(event)} (échéance {when} {event.starts_at.astimezone(PARIS):%H:%M})"[:200]
    start_of_today = datetime.combine(today, time.min, tzinfo=PARIS)
    if mission is not None and mission.status in ("backlog", "standby"):
        mission.title, mission.status = title, "backlog"
        mission.planned_start_at = min(mission.planned_start_at or start_of_today, start_of_today)
        mission.deadline_at = event.starts_at
    else:
        created = operations.create_intrinsic_mission(
            db, current_user=user, idempotency_key=f"calendar-urgent:{event.id}:{today.isoformat()}",
            payload=IntrinsicMissionCreate(title=title, notes=event.notes, deadline_at=event.starts_at,
                                           planned_start_at=start_of_today,
                                           estimated_minutes=event.prep_minutes))
        event = db.get(ImperiumCalendarEvent, event.id)
        event.prep_mission_id = created.id
    event.last_urgent_on = today


def _rules_slot(db: Session, user: User, event: ImperiumCalendarEvent, minutes: int,
                now: datetime) -> tuple[datetime, str, str] | None:
    """Le premier créneau libre (8 h-20 h, hors engagements du calendrier) qui finit avant l'échéance : d'abord
    à partir de la veille, pour garder une marge sans s'y prendre trop tôt, puis plus tôt si c'est plein."""
    deadline_day = event.starts_at.astimezone(PARIS).date()
    today = now.astimezone(PARIS).date()
    eve = max(today, deadline_day - timedelta(days=1))
    days = [eve + timedelta(days=i) for i in range((deadline_day - eve).days + 1)]
    days += [today + timedelta(days=i) for i in range((eve - today).days)]
    for day in days:
        for hour in range(*DAY_HOURS):
            start = datetime.combine(day, time(hour), tzinfo=PARIS).astimezone(UTC)
            end = start + timedelta(minutes=minutes)
            local_end = end.astimezone(PARIS)
            if start < now + timedelta(minutes=30) or end > event.starts_at:
                continue
            if local_end.date() != day or (local_end.hour, local_end.minute) > (DAY_HOURS[1], 0):
                continue
            if calendar.conflicts(db, current_user=user, check=CalendarConflictCheck(starts_at=start, ends_at=end)):
                continue
            label = ("aujourd'hui" if day == today else "demain" if day == today + timedelta(days=1)
                     else f"le {day:%d/%m}")
            return start, f"Premier créneau libre avant l'échéance : {label} à {hour} h.", "rules"
    return None


def _cloud_slot(db: Session, user: User, event: ImperiumCalendarEvent, minutes: int,
                now: datetime) -> tuple[datetime, str, str] | None:
    """Le rôle cloud propose le meilleur moment (doc 51 §8.1, §13) ; le créneau est vérifié libre, sinon règles."""
    if cloud.slot_mode(db, PLAN_SLOT) != "live":
        return None
    busy = [{"debut": o.starts_at.astimezone(PARIS).isoformat(timespec="minutes"),
             "fin": (o.ends_at or o.starts_at).astimezone(PARIS).isoformat(timespec="minutes"), "titre": o.title}
            for o in calendar.list_occurrences(db, current_user=user, starts_from=now, starts_to=event.starts_at,
                                               blocking_only=True)]
    prompt = (f"Maintenant : {now.astimezone(PARIS):%Y-%m-%d %H:%M} (Paris). Échéance : « {event.title} » le "
              f"{event.starts_at.astimezone(PARIS):%Y-%m-%d %H:%M}. Tâche : {event.task or event.title}. Temps estimé : "
              f"{minutes} min. Urgence : {event.urgency}. Précisions : {event.notes or 'aucune'}.\nCréneaux déjà pris : {busy}")
    schema = {"type": "object", "additionalProperties": False, "required": ["start_local", "rationale_fr"],
              "properties": {"start_local": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$"},
                             "rationale_fr": {"type": "string", "maxLength": 300}}}
    system = ("Tu proposes le meilleur moment pour préparer une échéance : assez tôt pour garder une marge, de jour, "
              "jamais sur un créneau déjà pris. Réponds en français, en tutoyant, une phrase de justification.")
    try:
        output = cloud.structured(db, slot_code=PLAN_SLOT, app_name="imperium", system=system, user=prompt,
                                  schema=schema, related_entity_type="calendar_event", related_entity_id=event.id).output
        start = datetime.fromisoformat(output["start_local"]).replace(tzinfo=PARIS).astimezone(UTC)
    except (cloud.CloudError, KeyError, ValueError):
        return None
    end = start + timedelta(minutes=minutes)
    if start < now or end > event.starts_at or calendar.conflicts(
            db, current_user=user, check=CalendarConflictCheck(starts_at=start, ends_at=end)):
        return None
    return start, str(output.get("rationale_fr") or "")[:300], "cloud"


def _reselect(db: Session, user: User, now: datetime) -> None:
    from app.services.daily import selection
    from app.services.imperium.planning_days import get_current_planning_day

    if not selection.selection_enabled(db) or get_current_planning_day(db, current_user=user) is None:
        return
    active = db.scalar(select(ImperiumMission.id).where(ImperiumMission.user_id == user.id,
                                                       ImperiumMission.status == "active"))
    if active is not None:
        return
    selection.select_next(db, current_user=user, trigger="calendar", now=now)
    db.commit()
