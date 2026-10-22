"""Programme d'entraînement conçu par le cerveau (doc 40 §13.1 mode 1, spec Pulse P3). Job `pulse.program_designer`.

1. Demande (`request`) : objectif, niveau, jours, durée d'une séance, heure, consigne → `generating` + événement.
2. Le job : rôle santé (slot `pulse.program_design`), sinon modèle local (`pulse.program_design_local`) ; aucun
   branché → `failed` avec la raison. Contexte en LISTE BLANCHE : la demande, le matériel possédé, les douleurs en
   cours (lieu, intensité, impact sur le sport), les règles médicales actives, les analyses hors norme du labo.
   Écart assumé à la spec P3 : pas de catalogue d'exercices validé (non semé) ; le cerveau compose les exercices
   à partir du matériel, comme le prévoit le doc 40 §13.1, et le code relit tout.
3. Relecture par le code : jours demandés seulement, une séance par jour, durée ≤ celle demandée, groupes
   musculaires connus, matériel possédé (ou poids du corps), séries/répétitions/repos bornés, séries par groupe
   et par semaine ≤ `pulse.max_weekly_sets_group`. Invalide → un nouvel essai avec les erreurs, puis échec.
4. Acceptation par l'utilisateur : le programme remplace l'actif (ses séances futures non faites sont retirées),
   cibles hebdomadaires = séries prévues par groupe (calculées par le code), séances créées pour toutes les
   semaines du programme à partir d'aujourd'hui, à l'heure demandée.
"""

import logging
from collections.abc import Callable
from datetime import UTC, datetime, time, timedelta
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import PulseMedicalRule, PulseOwnedEquipment, PulsePainLog, PulseWorkout
from app.models.pulse import PulseProgram, PulseProgramRequest, PulseProgramTarget
from app.schemas.pulse_training import MUSCLE_GROUPS, ProgramDesign, ProgramRequestCreate, ProgramRequestRead
from app.services.ai import cloud, local_executor
from app.services.events.emitter import build_event
from app.services.params import get_parameter
from app.services.pulse import food_stock, labs, training
from app.services.pulse.expiry import PARIS
from app.services.pulse.pantry_scan import normalize_name

logger = logging.getLogger(__name__)

SLOT = "pulse.program_design"
LOCAL_SLOT = "pulse.program_design_local"
REQUESTED = "pulse.program.requested"
LOCAL_MAX_TOKENS = 10000
DAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
DAYS_FR = dict(zip(DAYS, ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"), strict=True))
LEVELS_FR = {"beginner": "débutant", "intermediate": "intermédiaire", "advanced": "confirmé"}
NO_BRAIN = ("Aucun cerveau n'est branché pour le programme : allume le rôle santé (ou le modèle local) dans les "
            "paramètres avancés d'Imperium, puis redemande.")
SYSTEM = (
    "Tu es le spécialiste santé et entraînement d'un assistant personnel. Tu conçois un programme de plusieurs "
    "semaines pour un chauffeur VTC : séances types par jour de la semaine, exercices précis avec séries, "
    "répétitions ou durée, repos et une consigne d'exécution claire. Tu utilises le matériel possédé de façon "
    "créative (un même objet sert à plusieurs exercices) ou le poids du corps (equipment vide) ; jamais de "
    "matériel absent de la liste. Tu respectes les jours, la durée et le niveau demandés, et tu évites ce que les "
    "douleurs et règles médicales signalées déconseillent. muscle_group parmi la liste fournie, ou null pour le "
    "cardio et la mobilité. Pas de diagnostic ni de promesse de résultat. Réponds en français, en tutoyant, "
    "uniquement selon le schéma JSON."
)


class ProgramDesignStateError(ValueError):
    pass


class ProgramDesignNotFoundError(ValueError):
    pass


class ProgramDesignIdempotencyError(ValueError):
    pass


class PlannerUnavailableError(RuntimeError):
    pass


Caller = Callable[[str, str, dict], tuple[dict, str, dict]]


# --- Demande et décision ------------------------------------------------------------------------------------

def request(db: Session, *, current_user: User, payload: ProgramRequestCreate, idempotency_key: str
            ) -> tuple[ProgramRequestRead, bool]:
    inputs = payload.model_dump(mode="json")
    fingerprint = food_stock.request_hash("pulse.program.request", inputs)
    existing = db.scalar(select(PulseProgramRequest).where(PulseProgramRequest.user_id == current_user.id,
                                                           PulseProgramRequest.idempotency_key == idempotency_key))
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise ProgramDesignIdempotencyError("Idempotency key already used with a different request.")
        return read(existing), True
    if db.scalar(select(PulseProgramRequest.id).where(PulseProgramRequest.user_id == current_user.id,
                                                      PulseProgramRequest.status == "generating")) is not None:
        raise ProgramDesignStateError("A program is already being designed.")
    row = PulseProgramRequest(user_id=current_user.id, status="generating", inputs=inputs,
                              idempotency_key=idempotency_key, request_hash=fingerprint)
    db.add(row)
    db.flush()
    db.add(build_event(db, user_id=current_user.id, event_type=REQUESTED, payload={"request_id": str(row.id)},
                       idempotency_key=f"{REQUESTED}.{row.id}", source_app=SourceApp.pulse, privacy_level=PrivacyLevel.high))
    db.flush()
    db.refresh(row)
    result = read(row)
    db.commit()
    return result, False


def latest(db: Session, *, current_user: User) -> ProgramRequestRead | None:
    """Dernière demande pas encore tranchée (en cours, proposée ou échouée), sinon rien."""
    row = db.scalar(select(PulseProgramRequest).where(PulseProgramRequest.user_id == current_user.id)
                    .order_by(PulseProgramRequest.created_at.desc()).limit(1))
    return read(row) if row is not None and row.status in ("generating", "proposed", "failed") else None


def reject(db: Session, *, current_user: User, request_id: UUID) -> ProgramRequestRead:
    row = _get(db, current_user, request_id)
    if row.status not in ("proposed", "failed", "rejected"):
        raise ProgramDesignStateError("Only a proposed or failed program can be dismissed.")
    row.status = "rejected"
    db.commit()
    return read(row)


def accept(db: Session, *, current_user: User, request_id: UUID, now: datetime | None = None) -> ProgramRequestRead:
    """Validation : programme actif, cibles hebdomadaires calculées, séances de toutes les semaines du programme."""
    row = _get(db, current_user, request_id, lock=True)
    if row.status == "accepted":
        return read(row)
    if row.status != "proposed":
        raise ProgramDesignStateError("Only a proposed program can be accepted.")
    design = ProgramDesign(**row.design)
    now = now or datetime.now(UTC)
    previous = training.active_program(db, user_id=current_user.id)
    if previous is not None:
        previous.status, previous.updated_at = "superseded", now
        db.execute(delete(PulseWorkout).where(PulseWorkout.program_id == previous.id, PulseWorkout.status == "planned",
                                              PulseWorkout.planned_at > now))
    program = PulseProgram(id=uuid4(), user_id=current_user.id, name=design.name, objective_weights={},
                           mesocycle={"phase": design.phase, "week_current": 1, "weeks_total": design.weeks_total,
                                      "progression_model": design.progression_fr[:60]},
                           status="active", version=1, idempotency_key=f"program-request:{row.id}",
                           request_hash=row.request_hash)
    db.add(program)
    db.flush()
    today = now.astimezone(PARIS).date()
    monday = training.week_start_of(today)
    clock = time.fromisoformat(row.inputs["preferred_time"])
    sets = weekly_sets(design)
    created = 0
    for week in range(design.weeks_total):
        start = monday + timedelta(days=7 * week)
        for group, count in sets.items():
            db.add(PulseProgramTarget(id=uuid4(), program_id=program.id, week_start=start, muscle_group=group,
                                      target_sets=count, tolerance_sets=2))
        for index, session in enumerate(design.sessions):
            day = start + timedelta(days=DAYS.index(session.weekday))
            planned = datetime.combine(day, clock, tzinfo=PARIS)
            if planned <= now:
                continue
            db.add(_workout(current_user.id, program.id, session, planned, f"program:{program.id}:{day}:{index}"))
            created += 1
    row.status, row.program_id = "accepted", program.id
    training.emit_program(db, program, "pulse.program.created", source="design", request_id=str(row.id),
                          workouts=created)
    db.flush()
    db.refresh(row)
    result = read(row)
    db.commit()
    return result


def _workout(user_id: UUID, program_id: UUID, session, planned: datetime, key: str) -> PulseWorkout:
    exercises = [{"name": e.name, "sets": e.sets, "reps": e.reps, "duration_seconds": e.duration_seconds,
                  "rest_seconds": e.rest_seconds, "muscle_group": e.muscle_group, "notes": e.notes}
                 for e in session.exercises]
    equipment = list(dict.fromkeys(item for e in session.exercises for item in e.equipment))
    return PulseWorkout(user_id=user_id, title=session.title, status="planned", planned_at=planned,
                        duration_minutes=session.duration_minutes, intensity=session.intensity, exercises=exercises,
                        equipment=equipment, program_id=program_id, session_type=session.session_type,
                        systemic_load=session.systemic_load, idempotency_key=key, request_hash="program-design")


def weekly_sets(design: ProgramDesign) -> dict[str, int]:
    totals: dict[str, int] = {}
    for session in design.sessions:
        for exercise in session.exercises:
            if exercise.muscle_group:
                totals[exercise.muscle_group] = totals.get(exercise.muscle_group, 0) + exercise.sets
    return dict(sorted(totals.items()))


# --- Job -------------------------------------------------------------------------------------------------------

def program_designer_job(ctx, window) -> None:  # noqa: ARG001 - signature du runner
    done = process_requested(ctx.db)
    ctx.items_in = ctx.items_out = done


def process_requested(db: Session, *, call: Caller | None = None) -> int:
    ids = list(db.scalars(select(PulseProgramRequest.id).where(PulseProgramRequest.status == "generating")
                          .order_by(PulseProgramRequest.created_at).limit(5)))
    for request_id in ids:
        generate(db, request_id, call=call)
    return len(ids)


def generate(db: Session, request_id: UUID, *, call: Caller | None = None) -> None:
    row = db.get(PulseProgramRequest, request_id, with_for_update=True)
    if row is None or row.status != "generating":
        db.rollback()
        return
    user = db.get(User, row.user_id)
    owned = list(db.scalars(select(PulseOwnedEquipment.name).where(PulseOwnedEquipment.user_id == user.id,
                                                                   PulseOwnedEquipment.status == "active")))
    prompt = build_prompt(db, user, row.inputs, owned)
    schema = output_schema(row.inputs["days"])
    caller = call or _default_caller(db, row)
    trace: dict = {"attempts": 0, "errors": []}
    current, design, source = prompt, None, None
    for _ in range(2):
        trace["attempts"] += 1
        try:
            output, source, info = caller(SYSTEM, current, schema)
        except PlannerUnavailableError as exc:
            _fail(db, row, str(exc), trace)
            return
        trace.update(info)
        design, errors = check(db, output, row.inputs, owned)
        if not errors:
            break
        trace["errors"].extend(errors[:20])
        design = None
        current = (f"{prompt}\n\n## rappel\nTa proposition précédente était invalide : {' ; '.join(errors[:12])}. "
                   "Corrige-la en respectant le schéma et les règles.")
    if design is None:
        _fail(db, row, "Le cerveau n'a pas proposé de programme valable ; redemande-le ou précise ta demande.", trace)
        return
    row.status, row.source, row.design = "proposed", source, design.model_dump(mode="json")
    row.rationale_fr, row.trace, row.error = design.rationale_fr, trace, None
    db.commit()


def build_prompt(db: Session, user: User, inputs: dict, owned: list[str]) -> str:
    pains = db.scalars(select(PulsePainLog).where(PulsePainLog.user_id == user.id, PulsePainLog.resolved_at.is_(None))
                       .order_by(PulsePainLog.noted_at.desc()).limit(10))
    pain_lines = "\n".join(
        f"- {pain.location or pain.body_zone} : {pain.severity}/10"
        + (" ; gêne le sport" if pain.workout_impact else "") + (f" ; {pain.limitation_notes}" if pain.limitation_notes else "")
        for pain in pains) or "aucune"
    rules = "\n".join(f"- {rule.rule_text}" for rule in db.scalars(select(PulseMedicalRule).where(
        PulseMedicalRule.user_id == user.id, PulseMedicalRule.status == "active"))) or "aucune"
    blood = "\n".join(labs.out_of_range_lines(db, user)) or "aucune"
    days = ", ".join(DAYS_FR[d] for d in inputs["days"])
    return (
        f"Objectif : {inputs['goal']}\nNiveau : {LEVELS_FR[inputs['level']]}\nJours disponibles : {days}\n"
        f"Durée d'une séance : {inputs['session_minutes']} min au plus\nConsigne : {inputs.get('note') or 'aucune'}\n\n"
        f"## Matériel possédé (noms exacts)\n" + ("\n".join(f"- {name}" for name in owned) or "aucun : poids du corps")
        + f"\n\n## Groupes musculaires\n{', '.join(MUSCLE_GROUPS)}\n\n## Douleurs en cours\n{pain_lines}\n\n"
        f"## Règles médicales actives\n{rules}\n\n## Analyses de sang hors norme du labo\n{blood}\n\n"
        f"Plafond : {max_sets(db)} séries par groupe musculaire et par semaine. Une séance au plus par jour, "
        "seulement les jours disponibles."
    )


def output_schema(days: list[str]) -> dict:
    exercise = {
        "type": "object", "additionalProperties": False,
        "required": ["name", "muscle_group", "sets", "reps", "duration_seconds", "rest_seconds", "equipment", "notes"],
        "properties": {"name": {"type": "string", "maxLength": 120},
                       "muscle_group": {"anyOf": [{"enum": list(MUSCLE_GROUPS)}, {"type": "null"}]},
                       "sets": {"type": "integer"}, "reps": {"type": ["integer", "null"]},
                       "duration_seconds": {"type": ["integer", "null"]}, "rest_seconds": {"type": "integer"},
                       "equipment": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
                       "notes": {"type": "string", "maxLength": 300}}}
    session = {
        "type": "object", "additionalProperties": False,
        "required": ["weekday", "title", "session_type", "duration_minutes", "intensity", "systemic_load", "exercises"],
        "properties": {"weekday": {"enum": days}, "title": {"type": "string", "maxLength": 120},
                       "session_type": {"enum": ["strength", "hypertrophy", "cardio", "mobility", "technique", "mental"]},
                       "duration_minutes": {"type": "integer"}, "intensity": {"enum": ["low", "medium", "high"]},
                       "systemic_load": {"type": "integer"},
                       "exercises": {"type": "array", "minItems": 1, "maxItems": 12, "items": exercise}}}
    text = {"type": "string"}
    return {"type": "object", "additionalProperties": False,
            "required": ["name", "phase", "weeks_total", "progression_fr", "recovery_fr", "rationale_fr", "sessions"],
            "properties": {"name": text, "phase": text, "weeks_total": {"type": "integer"}, "progression_fr": text,
                           "recovery_fr": text, "rationale_fr": text,
                           "sessions": {"type": "array", "minItems": 1, "maxItems": 7, "items": session}}}


def max_sets(db: Session) -> int:
    return int(get_parameter(db, "pulse.max_weekly_sets_group", default=25))


def check(db: Session, output: dict | None, inputs: dict, owned: list[str]) -> tuple[ProgramDesign | None, list[str]]:
    """(programme relu, erreurs) : la sortie n'est acceptée que sans aucune erreur."""
    try:
        design = ProgramDesign(**(output or {}))
    except (ValidationError, TypeError) as exc:
        return None, [f"{'.'.join(str(p) for p in error['loc'])} : {error['msg']}" for error in exc.errors()[:8]] \
            if isinstance(exc, ValidationError) else ["sortie illisible"]
    errors = []
    owned_keys = {normalize_name(name): name for name in owned}
    seen = set()
    for session in design.sessions:
        if session.weekday not in inputs["days"]:
            errors.append(f"séance un jour non disponible ({DAYS_FR[session.weekday]})")
        if session.weekday in seen:
            errors.append(f"deux séances le {DAYS_FR[session.weekday]}")
        seen.add(session.weekday)
        if session.duration_minutes > inputs["session_minutes"]:
            errors.append(f"« {session.title} » dure {session.duration_minutes} min, plus que les {inputs['session_minutes']} demandées")
        for exercise in session.exercises:
            if exercise.muscle_group is not None and exercise.muscle_group not in MUSCLE_GROUPS:
                errors.append(f"groupe musculaire inconnu ({exercise.muscle_group})")
            if (exercise.reps is None) == (exercise.duration_seconds is None):
                errors.append(f"« {exercise.name} » : des répétitions OU une durée")
            for item in exercise.equipment:
                if normalize_name(item) not in owned_keys:
                    errors.append(f"« {exercise.name} » utilise « {item} », absent du matériel possédé")
    limit = max_sets(db)
    errors.extend(f"{group} : {count} séries par semaine, plus que {limit}"
                  for group, count in weekly_sets(design).items() if count > limit)
    if not errors:
        for session in design.sessions:  # matériel au nom exact de la liste de l'utilisateur
            for exercise in session.exercises:
                exercise.equipment = [owned_keys[normalize_name(item)] for item in exercise.equipment]
    return design, errors


def read(row: PulseProgramRequest) -> ProgramRequestRead:
    design = ProgramDesign(**row.design) if row.design else None
    return ProgramRequestRead(id=row.id, status=row.status, inputs=row.inputs, design=design,
                              weekly_sets=weekly_sets(design) if design else {}, rationale_fr=row.rationale_fr,
                              error=row.error, program_id=row.program_id, created_at=row.created_at)


def _fail(db: Session, row: PulseProgramRequest, message: str, trace: dict | None = None) -> None:
    row.status, row.error, row.trace = "failed", message, trace
    db.commit()


def _get(db: Session, user: User, request_id: UUID, *, lock: bool = False) -> PulseProgramRequest:
    row = db.get(PulseProgramRequest, request_id, with_for_update=lock)
    if row is None or row.user_id != user.id:
        raise ProgramDesignNotFoundError("Program request not found.")
    return row


def _default_caller(db: Session, row: PulseProgramRequest) -> Caller:
    def call(system: str, prompt: str, schema: dict) -> tuple[dict, str, dict]:
        if cloud.slot_mode(db, SLOT) == "live":
            try:
                result = cloud.structured(db, slot_code=SLOT, app_name="pulse", system=system, user=prompt, schema=schema,
                                          related_entity_type="pulse_program_request", related_entity_id=row.id)
                return result.output, "cloud", {"model": result.model}
            except cloud.CloudError as exc:
                logger.warning("pulse program design: cloud failed (%s)", str(exc)[:120])
        if local_executor.slot_mode(db, LOCAL_SLOT) == "live":
            try:
                result = local_executor.structured(slot_code=LOCAL_SLOT, app_name="pulse", system=system, user=prompt,
                                                   schema=schema, max_tokens=LOCAL_MAX_TOKENS,
                                                   related_entity_type="pulse_program_request", related_entity_id=row.id)
                return result.output, "local", {"model": "local"}
            except local_executor.LocalExecutorError as exc:
                raise PlannerUnavailableError("Le modèle local n'a pas répondu ; redemande plus tard.") from exc
        raise PlannerUnavailableError(NO_BRAIN)
    return call
