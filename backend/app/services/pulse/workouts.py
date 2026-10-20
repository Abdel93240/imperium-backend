"""Séances de sport Pulse (PUL-05/PUL-06, doc 40 §13.1–§13.2, §8).

Planification manuelle (Idempotency-Key), modification sous version (version
dépassée → conflit avec la séance actuelle, jamais d'écrasement), démarrage, fin
(séries faites, intensité ressentie, exercices sautés avec raison) ou séance sautée
avec raison. Une séance terminée ou sautée ne change plus.

Programme du spécialiste santé (modes 1 et 3), adaptation proposée (PUL-07),
fenêtre de récupération et matériel possédé : pas encore.
"""

from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import ImperiumMission, PulseWorkout
from app.models.pulse import PulseProgram
from app.schemas.pulse_workouts import (
    WorkoutCompleteRequest,
    WorkoutCreate,
    WorkoutListResponse,
    WorkoutRead,
    WorkoutSkipRequest,
    WorkoutStartRequest,
    WorkoutUpdate,
)
from app.services.events.emitter import build_event
from app.services.pulse import food_stock, training
from app.services.pulse.expiry import PARIS

MAX_RANGE_DAYS = 62


class WorkoutNotFoundError(ValueError):
    pass


class WorkoutStateError(ValueError):
    pass


class WorkoutInputError(ValueError):
    pass


class WorkoutIdempotencyConflictError(ValueError):
    pass


class WorkoutVersionConflictError(ValueError):
    def __init__(self, current: WorkoutRead) -> None:
        super().__init__("Workout was changed since it was read.")
        self.current = current


def create_workout(
    db: Session, *, current_user: User, payload: WorkoutCreate, idempotency_key: str
) -> tuple[WorkoutRead, bool]:
    fingerprint = food_stock.request_hash("pulse.workout.create", payload.model_dump(mode="json"))
    existing = db.scalar(
        select(PulseWorkout).where(PulseWorkout.user_id == current_user.id, PulseWorkout.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise WorkoutIdempotencyConflictError("Idempotency key already used with a different workout.")
        return WorkoutRead.model_validate(existing), True
    if payload.source_mission_id is not None:
        mission = db.get(ImperiumMission, payload.source_mission_id)
        if mission is None or mission.user_id != current_user.id:
            raise WorkoutNotFoundError("Mission not found.")
    if payload.program_id is not None:
        program = db.get(PulseProgram, payload.program_id)
        if program is None or program.user_id != current_user.id:
            raise WorkoutNotFoundError("Program not found.")
    workout = PulseWorkout(
        user_id=current_user.id, title=payload.title, status="planned", planned_at=payload.planned_at,
        duration_minutes=payload.duration_minutes, intensity=payload.intensity,
        exercises=[exercise.model_dump(mode="json") for exercise in payload.exercises], equipment=payload.equipment,
        source_mission_id=payload.source_mission_id, program_id=payload.program_id,
        session_type=payload.session_type, systemic_load=payload.systemic_load, version=1, idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    db.add(workout)
    db.flush()
    db.refresh(workout)
    read = WorkoutRead.model_validate(workout)
    db.commit()
    return read, False


def list_workouts(db: Session, *, current_user: User, from_day: date, to_day: date) -> WorkoutListResponse:
    if to_day < from_day or (to_day - from_day).days > MAX_RANGE_DAYS:
        raise WorkoutInputError(f"Range must be 0 to {MAX_RANGE_DAYS} days.")
    start = datetime.combine(from_day, time.min, tzinfo=PARIS)
    end = datetime.combine(to_day + timedelta(days=1), time.min, tzinfo=PARIS)
    rows = db.scalars(
        select(PulseWorkout)
        .where(PulseWorkout.user_id == current_user.id, PulseWorkout.planned_at >= start, PulseWorkout.planned_at < end)
        .order_by(PulseWorkout.planned_at.asc())
    )
    return WorkoutListResponse(items=[WorkoutRead.model_validate(row) for row in rows])


def get_workout(db: Session, *, current_user: User, workout_id: UUID) -> WorkoutRead:
    return WorkoutRead.model_validate(_get(db, current_user, workout_id))


def update_workout(
    db: Session, *, current_user: User, workout_id: UUID, payload: WorkoutUpdate, idempotency_key: str, request_path: str
) -> WorkoutRead:
    fingerprint = food_stock.request_hash(
        "pulse.workout.update", {"workout_id": str(workout_id), **payload.model_dump(mode="json", exclude_unset=True)}
    )
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, WorkoutRead)
    if previous is not None:
        return previous
    workout = _get(db, current_user, workout_id, lock=True)
    if workout.version != payload.version:
        raise WorkoutVersionConflictError(WorkoutRead.model_validate(workout))
    if workout.status != "planned":
        raise WorkoutStateError("Only a planned workout can be edited.")
    changes = payload.model_dump(mode="json", exclude_unset=True, exclude={"version"})
    for field in changes:
        setattr(workout, field, changes[field] if field in ("exercises", "equipment") else getattr(payload, field))
    workout.version += 1
    db.flush()
    db.refresh(workout)
    read = WorkoutRead.model_validate(workout)
    food_stock.remember(db, current_user, idempotency_key, "PATCH", request_path, fingerprint, 200, read)
    db.commit()
    return read


def start_workout(db: Session, *, current_user: User, workout_id: UUID, payload: WorkoutStartRequest) -> WorkoutRead:
    """Naturellement idempotent : une séance déjà démarrée est renvoyée telle quelle."""
    workout = _get(db, current_user, workout_id, lock=True)
    if workout.status == "planned":
        workout.status = "in_progress"
        workout.started_at = datetime.now(UTC)
        workout.body_state_at_start = (payload.body_state or "").strip() or None
        workout.version += 1
        db.flush()
        db.refresh(workout)
    elif workout.status != "in_progress":
        raise WorkoutStateError("Only a planned workout can be started.")
    read = WorkoutRead.model_validate(workout)
    db.commit()
    return read


def complete_workout(
    db: Session, *, current_user: User, workout_id: UUID, payload: WorkoutCompleteRequest, idempotency_key: str
) -> WorkoutRead:
    fingerprint = food_stock.request_hash("pulse.workout.complete", {"workout_id": str(workout_id), **payload.model_dump(mode="json")})
    workout = _get(db, current_user, workout_id, lock=True)
    replay = _closing_replay(workout, "completed", idempotency_key, fingerprint)
    if replay is not None:
        return replay
    exercises = [dict(exercise) for exercise in workout.exercises]
    for result in payload.results:
        if result.index >= len(exercises):
            raise WorkoutInputError(f"No exercise at index {result.index}.")
        exercises[result.index].update(
            done_sets=result.done_sets, done_reps=result.done_reps, skipped=result.skipped,
            skip_reason=result.skip_reason.strip() if result.skipped and result.skip_reason else None,
        )
    workout.exercises = exercises
    workout.status = "completed"
    workout.completed_at = datetime.now(UTC)
    workout.intensity_score = payload.intensity_score
    workout.actual_duration_minutes = payload.duration_minutes
    workout.notes_post_workout = (payload.notes or "").strip() or None
    skipped = sum(1 for exercise in exercises if exercise.get("skipped"))
    training.settle_debts(db, workout=workout)
    return _close(db, current_user, workout, idempotency_key, fingerprint, "pulse.workout.completed", {
        "intensity_score": workout.intensity_score, "duration_minutes": workout.actual_duration_minutes,
        "exercises_done": sum(1 for exercise in exercises if exercise.get("done_sets")), "exercises_skipped": skipped,
    })


def skip_workout(
    db: Session, *, current_user: User, workout_id: UUID, payload: WorkoutSkipRequest, idempotency_key: str
) -> WorkoutRead:
    fingerprint = food_stock.request_hash("pulse.workout.skip", {"workout_id": str(workout_id), **payload.model_dump(mode="json")})
    workout = _get(db, current_user, workout_id, lock=True)
    replay = _closing_replay(workout, "skipped", idempotency_key, fingerprint)
    if replay is not None:
        return replay
    workout.status = "skipped"
    workout.skip_reason = payload.reason
    training.settle_debts(db, workout=workout)
    return _close(db, current_user, workout, idempotency_key, fingerprint, "pulse.workout.skipped", {"reason": payload.reason})


# ---------- internes ----------

def _closing_replay(workout: PulseWorkout, target: str, idempotency_key: str, fingerprint: str) -> WorkoutRead | None:
    if workout.status in ("planned", "in_progress"):
        return None
    if workout.status == target and workout.closing_idempotency_key == idempotency_key:
        if workout.closing_request_hash != fingerprint:
            raise WorkoutIdempotencyConflictError("Idempotency key already used with a different request.")
        return WorkoutRead.model_validate(workout)
    raise WorkoutStateError(f"Workout is already {workout.status}.")


def _close(
    db: Session, current_user: User, workout: PulseWorkout, idempotency_key: str, fingerprint: str, event_type: str,
    extra: dict,
) -> WorkoutRead:
    workout.closing_idempotency_key, workout.closing_request_hash = idempotency_key, fingerprint
    workout.version += 1
    db.add(
        build_event(
            db, user_id=current_user.id, event_type=event_type,
            payload={"workout_id": str(workout.id), "planned_at": workout.planned_at.isoformat(), **extra},
            idempotency_key=f"{event_type}.{workout.id}", source_app=SourceApp.pulse, privacy_level=PrivacyLevel.medium,
        )
    )
    db.flush()
    db.refresh(workout)
    read = WorkoutRead.model_validate(workout)
    db.commit()
    return read


def _get(db: Session, current_user: User, workout_id: UUID, *, lock: bool = False) -> PulseWorkout:
    workout = db.get(PulseWorkout, workout_id, with_for_update=lock)
    if workout is None or workout.user_id != current_user.id:
        raise WorkoutNotFoundError("Workout not found.")
    return workout
