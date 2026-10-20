"""Programme d'entraînement Pulse, cibles hebdo et dette de volume (spec Pulse §3.6, §8). Code pur.

Programme saisi à la main tant que P3 (conception par modèle) n'est pas codée ; un seul `active` par
utilisateur, un nouveau remplace l'actif (`superseded`). Les séances du programme sont des `pulse_workouts`
rattachés (`program_id`) ; le volume se compte en séries planifiées par `exercises[].muscle_group`, hors
exercices sautés et séances sautées, sur la semaine de Paris (lundi → dimanche).

Dette : née d'un coup accepté (réduction, changement de type) ; `open` → `scheduled` quand un coup
`repay_debt` accepté la place sur une séance → `repaid` quand cette séance est terminée, de nouveau `open`
si elle est sautée. Le passage en perte (`written_off`) est une décision du WR, non codée ici.
"""

import math
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import PulseWorkout
from app.models.pulse import PulseProgram, PulseProgramTarget, PulseVolumeDebt
from app.schemas.pulse_training import (
    DebtRead,
    ProgramCreate,
    ProgramCurrentRead,
    ProgramRead,
    TargetRead,
    TargetsReplace,
)
from app.services.events.emitter import build_event
from app.services.params import get_parameter
from app.services.pulse import food_stock

PARIS = ZoneInfo("Europe/Paris")
REDUCE_PERCENTS = (50, 60, 70, 80)


class ProgramNotFoundError(ValueError):
    pass


class ProgramStateError(ValueError):
    pass


class ProgramIdempotencyConflictError(ValueError):
    pass


def programs_enabled(db: Session) -> bool:
    return bool(get_parameter(db, "pulse.programs_enabled", default=False))


def max_debt(db: Session) -> int:
    return int(get_parameter(db, "pulse.max_debt_sets_group", default=10))


def week_start_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def heavy(workout: PulseWorkout) -> bool:
    """Charge systémique >= 7 ; à défaut, intensité `high`."""
    return workout.systemic_load >= 7 if workout.systemic_load is not None else workout.intensity == "high"


# --- Volume ----------------------------------------------------------------------------------------

def workout_sets(workout: PulseWorkout) -> dict[str, int]:
    """Séries planifiées par groupe musculaire (fonction pure)."""
    sets: dict[str, int] = {}
    for exercise in workout.exercises or []:
        group, count = exercise.get("muscle_group"), exercise.get("sets")
        if group and count and not exercise.get("skipped"):
            sets[group] = sets.get(group, 0) + int(count)
    return sets


def reduced(exercises: list[dict], percent: int) -> tuple[list[dict], dict[str, int]]:
    """Séries ramenées à `percent` % (arrondi au-dessus, au moins 1) et séries retirées par groupe."""
    out, delta = [], {}
    for exercise in exercises:
        exercise = dict(exercise)
        group, count = exercise.get("muscle_group"), exercise.get("sets")
        if group and count:
            kept = max(1, math.ceil(int(count) * percent / 100))
            if kept < count:
                delta[group] = delta.get(group, 0) + int(count) - kept
            exercise["sets"] = kept
        out.append(exercise)
    return out, delta


def week_sets(db: Session, *, program: PulseProgram, week_start: date) -> dict[str, int]:
    start = datetime.combine(week_start, time.min, tzinfo=PARIS)
    totals: dict[str, int] = {}
    for workout in db.scalars(select(PulseWorkout).where(
            PulseWorkout.program_id == program.id, PulseWorkout.status != "skipped",
            PulseWorkout.planned_at >= start, PulseWorkout.planned_at < start + timedelta(days=7))):
        for group, count in workout_sets(workout).items():
            totals[group] = totals.get(group, 0) + count
    return totals


def targets(db: Session, *, program: PulseProgram, week_start: date) -> dict[str, PulseProgramTarget]:
    return {row.muscle_group: row for row in db.scalars(select(PulseProgramTarget).where(
        PulseProgramTarget.program_id == program.id, PulseProgramTarget.week_start == week_start))}


def open_debts(db: Session, *, program: PulseProgram) -> list[PulseVolumeDebt]:
    return list(db.scalars(select(PulseVolumeDebt).where(
        PulseVolumeDebt.program_id == program.id, PulseVolumeDebt.status == "open").order_by(PulseVolumeDebt.created_at)))


def debt_by_group(db: Session, *, program: PulseProgram) -> dict[str, int]:
    totals: dict[str, int] = {}
    for debt in db.scalars(select(PulseVolumeDebt).where(
            PulseVolumeDebt.program_id == program.id, PulseVolumeDebt.status.in_(("open", "scheduled")))):
        totals[debt.muscle_group] = totals.get(debt.muscle_group, 0) + debt.debt_sets
    return totals


def repay_room(db: Session, *, program: PulseProgram, workout: PulseWorkout, debt: PulseVolumeDebt) -> int:
    """Séries ajoutables : min(dette, cible + tolérance − volume de la semaine) ; 0 sans cible."""
    week = week_start_of(workout.planned_at.astimezone(PARIS).date())
    target = targets(db, program=program, week_start=week).get(debt.muscle_group)
    if target is None:
        return 0
    room = target.target_sets + target.tolerance_sets - week_sets(db, program=program, week_start=week).get(
        debt.muscle_group, 0)
    return max(0, min(debt.debt_sets, room))


def add_debts(db: Session, *, program: PulseProgram, workout: PulseWorkout, delta: dict[str, int],
              proposal_id: UUID | None, now: datetime) -> None:
    for group, count in sorted(delta.items()):
        if count > 0:
            db.add(PulseVolumeDebt(id=uuid4(), user_id=workout.user_id, program_id=program.id, muscle_group=group,
                                   debt_sets=count, origin_workout_id=workout.id, created_by_proposal=proposal_id,
                                   status="open", created_at=now))


def schedule_repayment(db: Session, *, debt: PulseVolumeDebt, workout: PulseWorkout, added: int,
                       proposal_id: UUID | None, now: datetime) -> None:
    """Place `added` séries de la dette sur la séance (le reste éventuel reste ouvert)."""
    exercises = [dict(exercise) for exercise in workout.exercises]
    target = next(exercise for exercise in exercises if exercise.get("muscle_group") == debt.muscle_group)
    target["sets"] = int(target.get("sets") or 0) + added
    workout.exercises = exercises
    if added < debt.debt_sets:
        debt.debt_sets -= added
        debt = PulseVolumeDebt(id=uuid4(), user_id=debt.user_id, program_id=debt.program_id,
                               muscle_group=debt.muscle_group, debt_sets=added, origin_workout_id=debt.origin_workout_id,
                               created_by_proposal=proposal_id, status="open", created_at=now)
        db.add(debt)
    debt.status, debt.repayment_workout_id = "scheduled", workout.id


def settle_debts(db: Session, *, workout: PulseWorkout) -> None:
    """Séance terminée : ses remboursements sont faits ; sautée : la dette redevient ouverte."""
    for debt in db.scalars(select(PulseVolumeDebt).where(PulseVolumeDebt.repayment_workout_id == workout.id,
                                                         PulseVolumeDebt.status == "scheduled")):
        if workout.status == "completed":
            debt.status, debt.resolved_at = "repaid", datetime.now(UTC)
        else:
            debt.status, debt.repayment_workout_id = "open", None


# --- Programme -------------------------------------------------------------------------------------

def active_program(db: Session, *, user_id: UUID) -> PulseProgram | None:
    return db.scalar(select(PulseProgram).where(PulseProgram.user_id == user_id, PulseProgram.status == "active"))


def create_program(db: Session, *, current_user: User, payload: ProgramCreate,
                   idempotency_key: str) -> tuple[ProgramRead, bool]:
    fingerprint = food_stock.request_hash("pulse.program.create", payload.model_dump(mode="json"))
    existing = db.scalar(select(PulseProgram).where(PulseProgram.user_id == current_user.id,
                                                    PulseProgram.idempotency_key == idempotency_key))
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise ProgramIdempotencyConflictError("Idempotency key already used with a different program.")
        return ProgramRead.model_validate(existing), True
    now = datetime.now(UTC)
    previous = active_program(db, user_id=current_user.id)
    if previous is not None:
        previous.status, previous.updated_at = "superseded", now
        db.flush()
    program = PulseProgram(id=uuid4(), user_id=current_user.id, name=payload.name,
                           objective_weights=payload.objective_weights, mesocycle=payload.mesocycle.model_dump(),
                           status="active", version=1, idempotency_key=idempotency_key, request_hash=fingerprint)
    db.add(program)
    db.flush()
    db.refresh(program)
    emit_program(db, program, "pulse.program.created")
    read = ProgramRead.model_validate(program)
    db.commit()
    return read, False


def set_status(db: Session, *, current_user: User, program_id: UUID, status: str) -> ProgramRead:
    program = _get(db, current_user, program_id)
    if program.status in ("superseded", "completed"):
        raise ProgramStateError("A superseded or completed program cannot change status.")
    if status == "active" and program.status != "active" and active_program(db, user_id=current_user.id):
        raise ProgramStateError("Another program is already active.")
    program.status, program.updated_at = status, datetime.now(UTC)
    read = ProgramRead.model_validate(program)
    db.commit()
    return read


def replace_targets(db: Session, *, current_user: User, program_id: UUID, payload: TargetsReplace) -> list[TargetRead]:
    program = _get(db, current_user, program_id)
    week = week_start_of(payload.week_start)
    for row in targets(db, program=program, week_start=week).values():
        db.delete(row)
    db.flush()
    for item in payload.targets:
        db.add(PulseProgramTarget(id=uuid4(), program_id=program.id, week_start=week, muscle_group=item.muscle_group,
                                  target_sets=item.target_sets, tolerance_sets=item.tolerance_sets))
    db.flush()
    read = _targets_read(db, program, week)
    db.commit()
    return read


def current(db: Session, *, current_user: User, now: datetime | None = None) -> ProgramCurrentRead:
    now = now or datetime.now(UTC)
    program = active_program(db, user_id=current_user.id)
    week = week_start_of(now.astimezone(PARIS).date())
    if program is None:
        return ProgramCurrentRead(program=None, week_start=week, targets=[], debts=[])
    debts = db.scalars(select(PulseVolumeDebt).where(
        PulseVolumeDebt.program_id == program.id, PulseVolumeDebt.status.in_(("open", "scheduled")))
        .order_by(PulseVolumeDebt.created_at))
    return ProgramCurrentRead(program=ProgramRead.model_validate(program), week_start=week,
                              targets=_targets_read(db, program, week),
                              debts=[DebtRead.model_validate(debt) for debt in debts])


def _targets_read(db: Session, program: PulseProgram, week: date) -> list[TargetRead]:
    planned = week_sets(db, program=program, week_start=week)
    return [TargetRead(muscle_group=group, target_sets=row.target_sets, tolerance_sets=row.tolerance_sets,
                       planned_sets=planned.get(group, 0))
            for group, row in sorted(targets(db, program=program, week_start=week).items())]


def _get(db: Session, current_user: User, program_id: UUID) -> PulseProgram:
    program = db.get(PulseProgram, program_id)
    if program is None or program.user_id != current_user.id:
        raise ProgramNotFoundError("Program not found.")
    return program


def emit_program(db: Session, program: PulseProgram, event_type: str, **extra) -> None:
    db.add(build_event(
        db, user_id=program.user_id, event_type=event_type, payload={"program_id": str(program.id), **extra},
        idempotency_key=f"{event_type}.{program.id}.{uuid4()}", source_app=SourceApp.pulse,
        privacy_level=PrivacyLevel.high,
    ))
