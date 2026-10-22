"""Calendrier d'Imperium (doc 51 ; avancé en V1 à la demande de l'utilisateur, 2026-10-22).

Un événement saisi est une contrainte DURE (doc 52 §14.6). Types : événement (bloque un créneau), échéance
(réserve du temps AVANT ; sa préparation est proposée puis validée), vacances / voyage, période bloquée (applis
impactées rangées pour leur branchement). Récurrences au format RRULE (`calendar_recurrence`), occurrence par
occurrence sautée ou déplacée sans toucher la série. Pas d'événement dans le passé (le passé se raconte en Weekly
Review). Chaque création, modification ou suppression passe par la règle des 7 jours (`calendar_threshold`).
"""

import hashlib
import json
from datetime import UTC, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus
from app.models.event import Event
from app.services.events.emitter import build_event
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumCalendarEvent, ImperiumCalendarOverride, ImperiumMission
from app.schemas.imperium import (
    CalendarConflictCheck,
    CalendarEventCreate,
    CalendarEventRead,
    CalendarEventType,
    CalendarEventUpdate,
    CalendarOccurrenceOverride,
    CalendarOccurrenceRead,
)
from app.services.imperium import calendar_recurrence

PARIS = ZoneInfo("Europe/Paris")
PAST_GRACE = timedelta(minutes=5)
BLOCKING_TYPES = ("event", "vacation")


class CalendarEventNotFoundError(ValueError):
    pass


class CalendarEventIdempotencyConflictError(ValueError):
    pass


class CalendarEventValidationError(ValueError):
    pass


def create_calendar_event(
    db: Session,
    *,
    current_user: User,
    payload: CalendarEventCreate,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[CalendarEventRead, bool]:
    request_hash = _hash_request("calendar.event.created", payload.model_dump(mode="json"))
    existing_key = _get_existing_idempotency(db, current_user=current_user, idempotency_key=idempotency_key)
    if existing_key is not None:
        return _handle_existing_idempotency(existing_key, request_hash), True

    _validate(payload.event_type.value, payload.starts_at, payload.ends_at, payload.all_day, payload.recurrence_rrule)
    calendar_event = ImperiumCalendarEvent(
        user_id=current_user.id,
        event_type=payload.event_type.value,
        title=payload.title,
        starts_at=payload.starts_at,
        ends_at=None if payload.event_type == CalendarEventType.deadline else payload.ends_at,
        blocks_time=payload.blocks_time and payload.event_type in (CalendarEventType.event, CalendarEventType.vacation),
        location=payload.location,
        notes=payload.notes,
        all_day=payload.all_day,
        urgency=payload.urgency,
        task=_normalize_optional_text(payload.task),
        prep_minutes=payload.prep_minutes,
        pause_vtc=payload.pause_vtc,
        pause_pulse=payload.pause_pulse,
        pause_path=payload.pause_path,
        recurrence_rrule=_normalize_optional_text(payload.recurrence_rrule),
        status="active",
        created_by="user",
        updated_by="user",
    )
    db.add(calendar_event)
    db.flush()

    event_id = f"evt_{uuid4().hex}"
    db.add(
        _build_event(
            db,
            current_user=current_user,
            event_id=event_id,
            event_type="calendar.event.created",
            idempotency_key=idempotency_key,
            payload={
                "calendar_event_id": str(calendar_event.id),
                **payload.model_dump(mode="json", exclude_none=True),
            },
        )
    )
    db.flush()

    response = read(calendar_event)
    _store_idempotency(
        db,
        current_user=current_user,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        response=response,
    )
    db.commit()
    from app.services.imperium import calendar_threshold

    calendar_threshold.after_change(db, current_user=current_user, event=calendar_event, change="added")
    return read(calendar_event), False


def read(event: ImperiumCalendarEvent) -> CalendarEventRead:
    response = CalendarEventRead.model_validate(event)
    response.recurrence_text = calendar_recurrence.describe(event.recurrence_rrule)
    return response


def get_calendar_event(db: Session, *, current_user: User, event_id: UUID) -> CalendarEventRead:
    event = _get_user_calendar_event(db, current_user=current_user, event_id=event_id)
    if event is None:
        raise CalendarEventNotFoundError("Calendar event not found.")
    return read(event)


def update_calendar_event(db: Session, *, current_user: User, event_id: UUID,
                          payload: CalendarEventUpdate) -> CalendarEventRead:
    """Modification (« toute la série » pour une récurrence) ; une échéance garde sa préparation alignée."""
    event = _get_user_calendar_event(db, current_user=current_user, event_id=event_id)
    if event is None:
        raise CalendarEventNotFoundError("Calendar event not found.")
    fields = payload.model_dump(exclude_unset=True)
    for name in ("title",):
        if name in fields and fields[name] is None:
            raise CalendarEventValidationError(f"{name} cannot be cleared.")
    for name in ("event_type", "blocks_time", "all_day", "urgency", "pause_vtc", "pause_pulse", "pause_path", "status"):
        if name in fields and fields[name] is None:
            fields.pop(name)
    moved = "starts_at" in fields or "ends_at" in fields or "recurrence_rrule" in fields
    candidate = {**{column: getattr(event, column) for column in ("event_type", "starts_at", "ends_at", "all_day",
                                                                 "recurrence_rrule")}, **fields}
    if moved:
        _validate(str(candidate["event_type"]), candidate["starts_at"], candidate["ends_at"], candidate["all_day"],
                  candidate["recurrence_rrule"])
    for name, value in fields.items():
        setattr(event, name, value.value if hasattr(value, "value") else value)
    if event.event_type == "deadline":
        event.ends_at = None
    if event.event_type not in BLOCKING_TYPES:
        event.blocks_time = False
    event.updated_by = "user"
    event.updated_at = datetime.now(UTC)
    mission = db.get(ImperiumMission, event.prep_mission_id) if event.prep_mission_id else None
    if mission is not None and mission.status in ("backlog", "standby"):
        mission.deadline_at = event.starts_at
        mission.title = prep_title(event)
        if event.status == "cancelled":
            mission.status, mission.ended_at = "cancelled", datetime.now(UTC)
    if moved and event.prep_proposal and event.prep_proposal.get("status") == "proposed":
        event.prep_proposal = None  # le créneau proposé ne vaut plus : il sera recalculé
    db.add(_build_event(db, current_user=current_user, event_id=f"evt_{uuid4().hex}", event_type="calendar.event.updated",
                        idempotency_key=f"calendar.event.updated:{event.id}:{uuid4().hex}",
                        payload={"calendar_event_id": str(event.id), "fields": sorted(fields)}))
    db.commit()
    from app.services.imperium import calendar_threshold

    calendar_threshold.after_change(db, current_user=current_user, event=event, change="modified")
    return read(db.get(ImperiumCalendarEvent, event.id))


def list_occurrences(db: Session, *, current_user: User, starts_from: datetime, starts_to: datetime,
                     blocking_only: bool = False) -> list[CalendarOccurrenceRead]:
    """Les occurrences à afficher entre deux instants : événements simples, séries dépliées, occurrences sautées
    retirées, déplacées remises à leur nouvel horaire. Un événement en cours (commencé avant) y figure aussi."""
    if starts_to < starts_from:
        raise CalendarEventValidationError("to must be greater than or equal to from.")
    query = select(ImperiumCalendarEvent).where(
        ImperiumCalendarEvent.user_id == current_user.id, ImperiumCalendarEvent.deleted_at.is_(None),
        ImperiumCalendarEvent.status != "cancelled", ImperiumCalendarEvent.starts_at <= starts_to)
    if blocking_only:
        query = query.where(ImperiumCalendarEvent.blocks_time.is_(True),
                            ImperiumCalendarEvent.event_type.in_(BLOCKING_TYPES))
    events = list(db.scalars(query))
    overrides = {}
    if events:
        for row in db.scalars(select(ImperiumCalendarOverride).where(
                ImperiumCalendarOverride.event_id.in_([event.id for event in events]))):
            overrides[(row.event_id, row.occurrence_at)] = row
    found = []
    for event in events:
        length = (event.ends_at - event.starts_at) if event.ends_at else None
        # Les débuts d'occurrence assez tôt pour encore durer dans la fenêtre.
        lookback = starts_from - (length or timedelta(0))
        for at in calendar_recurrence.occurrences(event.starts_at, event.recurrence_rrule, window_from=lookback,
                                                  window_to=starts_to):
            override = overrides.get((event.id, at))
            if override is not None and override.override_type == "skip":
                continue
            start = override.new_starts_at if override is not None else at
            end = (override.new_ends_at if override is not None and override.new_ends_at
                   else (start + length if length else None))
            if (end or start) < starts_from:
                continue
            found.append(CalendarOccurrenceRead(
                event_id=event.id, occurrence_at=at, starts_at=start, ends_at=end, moved=override is not None,
                title=event.title, event_type=event.event_type, all_day=event.all_day, urgency=event.urgency,
                location=event.location, blocks_time=event.blocks_time, recurring=bool(event.recurrence_rrule),
                status=event.status))
        for (event_id, at), override in overrides.items():  # occurrence déplacée dans la fenêtre depuis l'extérieur
            if event_id == event.id and override.override_type == "move" and \
                    starts_from <= override.new_starts_at <= starts_to and \
                    not any(o.event_id == event.id and o.occurrence_at == at for o in found):
                found.append(CalendarOccurrenceRead(
                    event_id=event.id, occurrence_at=at, starts_at=override.new_starts_at, ends_at=override.new_ends_at,
                    moved=True, title=event.title, event_type=event.event_type, all_day=event.all_day,
                    urgency=event.urgency, location=event.location, blocks_time=event.blocks_time,
                    recurring=bool(event.recurrence_rrule), status=event.status))
    return sorted(found, key=lambda occurrence: (occurrence.starts_at, occurrence.title))


def conflicts(db: Session, *, current_user: User, check: CalendarConflictCheck) -> list[CalendarOccurrenceRead]:
    """Les créneaux bloquants déjà pris sur [début, fin] (doc 51 §15.2) ; l'écran demande quoi faire."""
    end = check.ends_at or check.starts_at + timedelta(minutes=1)
    return [occurrence for occurrence in list_occurrences(db, current_user=current_user, starts_from=check.starts_at,
                                                          starts_to=end, blocking_only=True)
            if occurrence.event_id != check.exclude_event_id
            and occurrence.starts_at < end and (occurrence.ends_at or occurrence.starts_at) > check.starts_at]


def override_occurrence(db: Session, *, current_user: User, event_id: UUID,
                        payload: CalendarOccurrenceOverride) -> CalendarEventRead:
    """« Cette occurrence uniquement » : sautée ou déplacée ; la série continue normalement (doc 51 §7.2)."""
    event = _get_user_calendar_event(db, current_user=current_user, event_id=event_id)
    if event is None:
        raise CalendarEventNotFoundError("Calendar event not found.")
    if not event.recurrence_rrule:
        raise CalendarEventValidationError("Only a recurring event has occurrences.")
    at = payload.occurrence_at.astimezone(UTC)
    if at not in calendar_recurrence.occurrences(event.starts_at, event.recurrence_rrule, window_from=at, window_to=at):
        raise CalendarEventValidationError("This date is not an occurrence of the series.")
    if payload.action == "move":
        _not_in_past(payload.new_starts_at, all_day=event.all_day)
        if payload.new_ends_at is not None and payload.new_ends_at < payload.new_starts_at:
            raise CalendarEventValidationError("new_ends_at must be after new_starts_at.")
    row = db.scalar(select(ImperiumCalendarOverride).where(ImperiumCalendarOverride.event_id == event.id,
                                                            ImperiumCalendarOverride.occurrence_at == at))
    if row is None:
        row = ImperiumCalendarOverride(id=uuid4(), user_id=current_user.id, event_id=event.id, occurrence_at=at,
                                       override_type=payload.action)
        db.add(row)
    row.override_type = payload.action
    row.new_starts_at = payload.new_starts_at if payload.action == "move" else None
    row.new_ends_at = payload.new_ends_at if payload.action == "move" else None
    db.commit()
    from app.services.imperium import calendar_threshold

    calendar_threshold.after_change(db, current_user=current_user, event=event, change="modified")
    return read(event)


def prep_title(event: ImperiumCalendarEvent) -> str:
    return (event.task or f"Préparer : {event.title}")[:200]


def decide_prep(db: Session, *, current_user: User, event_id: UUID, accept: bool) -> CalendarEventRead:
    """Le créneau de préparation proposé pour une échéance : validé, la mission hors projet est créée (doc 51
    §8.1) ; refusé, rien n'est créé (la veille, une mission urgente le sera si rien n'est fait)."""
    from app.schemas.operations import IntrinsicMissionCreate
    from app.services.imperium import operations

    event = _get_user_calendar_event(db, current_user=current_user, event_id=event_id)
    if event is None:
        raise CalendarEventNotFoundError("Calendar event not found.")
    proposal = dict(event.prep_proposal or {})
    if event.event_type != "deadline" or proposal.get("status") != "proposed":
        raise CalendarEventValidationError("There is no preparation slot to decide.")
    if accept:
        mission = operations.create_intrinsic_mission(
            db, current_user=current_user, idempotency_key=f"calendar-prep:{event.id}:{proposal.get('starts_at')}",
            payload=IntrinsicMissionCreate(
                title=prep_title(event), notes=event.notes, deadline_at=event.starts_at,
                planned_start_at=datetime.fromisoformat(proposal["starts_at"]), estimated_minutes=event.prep_minutes))
        event = db.get(ImperiumCalendarEvent, event_id)
        event.prep_mission_id = mission.id
    event.prep_proposal = {**proposal, "status": "accepted" if accept else "declined",
                           "decided_at": datetime.now(UTC).isoformat()}
    db.commit()
    return read(event)


def _validate(event_type: str, starts_at: datetime, ends_at: datetime | None, all_day: bool,
              rrule: str | None) -> None:
    if starts_at.tzinfo is None or (ends_at is not None and ends_at.tzinfo is None):
        raise CalendarEventValidationError("Dates must include their timezone.")
    if ends_at is not None and ends_at < starts_at:
        raise CalendarEventValidationError("ends_at must be after starts_at.")
    if event_type in ("vacation", "blocked_period") and ends_at is None:
        raise CalendarEventValidationError("A period needs its end date.")
    if rrule:
        try:
            calendar_recurrence.parse(rrule)
        except calendar_recurrence.RecurrenceError as exc:
            raise CalendarEventValidationError(f"Recurrence: {exc}") from exc
    _not_in_past(ends_at or starts_at, all_day=all_day)


def _not_in_past(moment: datetime, *, all_day: bool) -> None:
    """Pas de rétroactivité (doc 51 §15.1) ; un événement déjà commencé mais pas fini reste permis."""
    now = datetime.now(UTC)
    limit = datetime.combine(now.astimezone(PARIS).date(), time.min, tzinfo=PARIS) if all_day else now - PAST_GRACE
    if moment < limit:
        raise CalendarEventValidationError(
            "Tu ne peux pas créer un événement dans le passé. Si tu veux noter quelque chose qui est arrivé, "
            "attends ta prochaine Weekly Review.")


def list_calendar_events(
    db: Session,
    *,
    current_user: User,
    starts_from: datetime | None = None,
    starts_to: datetime | None = None,
    event_type: CalendarEventType | None = None,
) -> list[ImperiumCalendarEvent]:
    if starts_from is not None and starts_to is not None and starts_to < starts_from:
        raise CalendarEventValidationError("to must be greater than or equal to from.")

    query = select(ImperiumCalendarEvent).where(
        ImperiumCalendarEvent.user_id == current_user.id,
        ImperiumCalendarEvent.deleted_at.is_(None),
    )
    if starts_from is not None:
        query = query.where(ImperiumCalendarEvent.starts_at >= starts_from)
    if starts_to is not None:
        query = query.where(ImperiumCalendarEvent.starts_at <= starts_to)
    if event_type is not None:
        query = query.where(ImperiumCalendarEvent.event_type == event_type.value)
    query = query.order_by(ImperiumCalendarEvent.starts_at.asc(), ImperiumCalendarEvent.created_at.asc())
    return list(db.scalars(query))


def delete_calendar_event(
    db: Session,
    *,
    current_user: User,
    event_id: UUID,
    deleted_by: str = "user",
    reason: str | None = None,
) -> UUID:
    calendar_event = _get_user_calendar_event(db, current_user=current_user, event_id=event_id)
    if calendar_event is None:
        raise CalendarEventNotFoundError("Calendar event not found.")

    normalized_deleted_by = _normalize_actor(deleted_by)
    normalized_reason = _normalize_optional_text(reason)
    now = datetime.now(UTC)
    deleted_id = calendar_event.id
    calendar_event.deleted_at = now
    calendar_event.deleted_by = normalized_deleted_by
    calendar_event.deletion_reason = normalized_reason
    calendar_event.updated_by = normalized_deleted_by
    calendar_event.updated_at = now
    mission = db.get(ImperiumMission, calendar_event.prep_mission_id) if calendar_event.prep_mission_id else None
    if mission is not None and mission.status in ("backlog", "standby"):
        mission.status, mission.ended_at = "cancelled", now  # la préparation d'une échéance supprimée n'a plus lieu
    creation_event = db.scalar(
        select(Event)
        .where(
            Event.user_id == current_user.id,
            Event.event_type == "calendar.event.created",
            Event.payload["calendar_event_id"].astext == str(deleted_id),
        )
        .order_by(Event.occurred_at.desc())
        .limit(1)
    )
    db.add(
        _build_event(
            db,
            current_user=current_user,
            event_id=f"evt_{uuid4().hex}",
            event_type="calendar.event.deleted",
            idempotency_key=f"calendar.event.deleted:{deleted_id}:{uuid4().hex}",
            payload={
                "calendar_event_id": str(deleted_id),
                "deleted_by": normalized_deleted_by,
                "reason": normalized_reason,
            },
            causation_event=creation_event,
        )
    )
    db.commit()
    from app.services.imperium import calendar_threshold

    calendar_threshold.after_change(db, current_user=current_user, event=calendar_event, change="deleted")
    return deleted_id


def _get_existing_idempotency(
    db: Session,
    *,
    current_user: User,
    idempotency_key: str,
) -> IdempotencyKey | None:
    return db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == current_user.id,
            IdempotencyKey.idempotency_key == idempotency_key,
        )
    )


def _handle_existing_idempotency(
    existing_key: IdempotencyKey,
    request_hash: str,
) -> CalendarEventRead:
    if existing_key.request_hash != request_hash:
        raise CalendarEventIdempotencyConflictError("Idempotency key already used with different payload.")
    if existing_key.response_body is None:
        raise CalendarEventIdempotencyConflictError("Idempotency key is already processing.")
    return CalendarEventRead(**existing_key.response_body)


def _get_user_calendar_event(
    db: Session,
    *,
    current_user: User,
    event_id: UUID,
) -> ImperiumCalendarEvent | None:
    return db.scalar(
        select(ImperiumCalendarEvent).where(
            ImperiumCalendarEvent.id == event_id,
            ImperiumCalendarEvent.user_id == current_user.id,
            ImperiumCalendarEvent.deleted_at.is_(None),
        )
    )


def _build_event(
    db: Session,
    *,
    current_user: User,
    event_id: str,
    event_type: str,
    idempotency_key: str,
    payload: dict,
    causation_event: Event | None = None,
) -> Event:
    # E2 (passe 0): shared emitter. calendar.* is already a generic domain;
    # deletion links back to the creation event (soft-delete traceability 0035).
    return build_event(
        db,
        user_id=current_user.id,
        event_type=event_type,
        payload=payload,
        idempotency_key=idempotency_key,
        event_id=event_id,
        causation_id=causation_event.event_id if causation_event is not None else None,
    )


def _store_idempotency(
    db: Session,
    *,
    current_user: User,
    idempotency_key: str,
    request_method: str,
    request_path: str,
    request_hash: str,
    response: CalendarEventRead,
) -> None:
    db.add(
        IdempotencyKey(
            user_id=current_user.id,
            idempotency_key=idempotency_key,
            request_method=request_method,
            request_path=request_path,
            request_hash=request_hash,
            status=IdempotencyStatus.completed,
            response_status_code=201,
            response_body=response.model_dump(mode="json"),
        )
    )


def _hash_request(action: str, payload: dict) -> str:
    canonical = json.dumps(
        {"action": action, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize_actor(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in {"user", "ai"}:
        raise CalendarEventValidationError("deleted_by must be user or ai.")
    return normalized


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
