"""Procédures Pulse : runner unique, P1 `adapt_training_session` et propositions (spec Pulse §3.3, §7, §8 ;
suite de la carte V10 ACT-PLS-15). Le code tient l'échiquier ; le slot IA ne fait que choisir un coup légal.

Runner (`pulse.procedure_runner`, semé désactivé) : une exécution `queued` passe `running`, chaque étape
logge dans `steps_log`, puis `completed` | `waiting_user` | `aborted` | `failed`. Seule P1 a ses étapes code
écrites ; une autre procédure nommée s'arrête en `aborted` (`not_coded`). Tant que `real_ai_enabled` est
faux, le slot `pulse.p1.choose_move` est FACTICE (premier coup légal hors `maintain`, sinon `maintain`) et
la proposition est écrite `dry_run`, jamais présentée ; avec `real_ai_enabled` vrai (chaînes cloud), le
runner échoue sans rien consommer. Slot LOCAL (`ai.local_slot_modes["pulse.p1.choose_move"]`) : en `shadow`,
le choix du modèle est journalisé à l'étape 3 sans servir ; en `live`, il sert (revalidé, repli `maintain`) et
les exécutions mises en file sont réelles : la proposition est présentée et attend ta décision.

P1 sans programme actif rattaché à la séance : seuls `maintain`, `shift_time` (même jour de Paris, par pas
de 30 min de 06:00 à 21:00) et `reschedule` (J+1 à J+6, même heure) peuvent être légaux. Créneau libre = aucun
chevauchement avec une autre séance prévue, une mission à heure fixe ou un événement calendrier bloquant ;
pas de séance lourde (charge >= 7, à défaut intensité `high`) dans un jeûne commencé depuis plus de 12 h ;
pas deux jours lourds d'affilée. Les coups qui exigent un programme sont alors illégaux (`no_program`).
Avec le programme : `reduce_volume` (50 à 80 %, dette résultante <= `pulse.max_debt_sets_group` par groupe),
`swap_modality` (technique, mobilité ou cardio léger, charge 3, toutes les séries en dette sous le même
plafond) et `repay_debt` (dette ouverte d'un groupe de la séance, dans cible + tolérance de la semaine) ;
`split_session` (non codé) et `deload_week` (pas de fiche doctrine) restent illégaux. Un coup désactivé
dans `pulse_legal_moves` est illégal (`inactive`). Un blocage santé actif (`v_pulse_active_blocks`)
arrête P1 : la règle rouge garde la main.

Décision (no-override) : seule une proposition présentée se décide. Refus : explication obligatoire, aucun
changement. Acceptation ou modification : le coup est revalidé sur un menu frais et la version de la séance
doit être celle de la proposition ; seul alors l'effet s'applique (heure, jour, séries, type de séance,
dette) et `pulse.program.adapted` est émis pour une séance du programme.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.event import Event
from app.models.imperium import ImperiumCalendarEvent, ImperiumMission, PulseWorkout
from app.models.pulse import (
    PulseBoardSnapshot,
    PulseDispatchLog,
    PulseLegalMove,
    PulseProcedure,
    PulseProcedureRun,
    PulseProgram,
    PulseProposal,
    PulseVolumeDebt,
)
from app.schemas.pulse_signals import ProposalDecisionRequest, ProposalListResponse, ProposalRead
from app.services.events.emitter import build_event
from app.services.params import get_parameter
from app.services.ai import local_executor
from app.services.path import fasting
from app.services.pulse import ai_slots, training

PARIS = ZoneInfo("Europe/Paris")
P1 = "adapt_training_session"
DRY_RUN = "dry_run"
LOCAL_MODEL = "local_executor"  # rôle, jamais un nom de modèle
LOCAL_PER_RUN = 3
STEP_MINUTES = 30
EARLIEST_START = time(6, 0)
LATEST_START = time(21, 0)
DEFAULT_MINUTES = 60
PROGRAM_MOVES = ("reduce_volume", "swap_modality", "split_session", "repay_debt", "deload_week")
PARAMETER_KEYS = {"shift_time": "new_time", "reschedule": "target_date", "reduce_volume": "percent",
                  "swap_modality": "new_session_type", "repay_debt": "debt_id"}
SWAP_TYPES = ("technique", "mobility", "cardio")
SWAP_LOAD = 3


class AdaptationUnavailableError(RuntimeError):
    """Adaptation demandée par l'utilisateur impossible maintenant (fonction ou modèle local éteints)."""


ADAPT_REASONS = {"fatigue": "fatigue déclarée", "pain": "douleur ou gêne déclarée", "short_time": "peu de temps aujourd'hui",
                 "other": "l'utilisateur veut alléger ou déplacer"}


class RealSlotNotCodedError(RuntimeError):
    pass


class ProposalNotFoundError(ValueError):
    pass


class ProposalStateError(ValueError):
    pass


class ProposalStaleError(ValueError):
    pass


@dataclass
class RunnerStats:
    processed: int = 0
    completed: int = 0
    aborted: int = 0
    failed: int = 0


def proposals_enabled(db: Session) -> bool:
    return bool(get_parameter(db, "pulse.proposals_enabled", default=False))


def active_catalogue(db: Session) -> set[str]:
    return set(db.scalars(select(PulseProcedure.code).where(PulseProcedure.active.is_(True))))


# --- File : une exécution par procédure nommée -----------------------------------------------------

def queue_from_dispatch(db: Session, *, dispatch: PulseDispatchLog, named: list[dict], trigger: Event,
                        now: datetime) -> list[PulseProcedureRun]:
    runs = []
    for item in named:
        procedure = db.scalar(select(PulseProcedure).where(PulseProcedure.code == item["code"],
                                                           PulseProcedure.active.is_(True)))
        if procedure is None:
            continue
        run = PulseProcedureRun(id=uuid4(), user_id=dispatch.user_id, procedure_id=procedure.id,
                                procedure_version=procedure.version, dispatch_id=dispatch.id,
                                trigger_event_id=trigger.event_id, correlation_id=trigger.correlation_id,
                                inputs={**(item.get("inputs") or {}), "urgency": item["urgency"]},
                                dry_run=local_executor.slot_mode(db, ai_slots.CHOOSE_MOVE_SLOT) != "live",
                                status="queued", steps_log=[], created_at=now)
        db.add(run)
        runs.append(run)
    db.flush()
    return runs


def adapt_now(db: Session, *, current_user: User, workout_id: UUID, reason: str,
              now: datetime | None = None) -> tuple[ProposalRead | None, str]:
    """« Adapter à mon état » (trigger pre_session, demandé par l'utilisateur) : P1 tout de suite sur cette séance.
    Jamais en essai à blanc : sans modèle local branché, rien n'est proposé (message clair). (proposition, raison)."""
    now = now or datetime.now(UTC)
    procedure = db.scalar(select(PulseProcedure).where(PulseProcedure.code == P1, PulseProcedure.active.is_(True)))
    if not proposals_enabled(db) or procedure is None:
        raise AdaptationUnavailableError("L'adaptation des séances n'est pas encore activée sur le serveur.")
    if local_executor.slot_mode(db, ai_slots.CHOOSE_MOVE_SLOT) != "live":
        raise AdaptationUnavailableError("Le modèle local qui adapte les séances n'est pas branché.")
    run = PulseProcedureRun(id=uuid4(), user_id=current_user.id, procedure_id=procedure.id,
                            procedure_version=procedure.version, inputs={"workout_id": str(workout_id), "urgency": "now",
                                                                       "trigger": "pre_session", "reason": reason},
                            dry_run=False, status="running", steps_log=[], created_at=now, started_at=now)
    db.add(run)
    db.flush()
    _run_p1(db, run, current_user, now)
    proposal = db.scalar(select(PulseProposal).where(PulseProposal.procedure_run_id == run.id))
    read = ProposalRead.model_validate(proposal) if proposal is not None else None
    outcome = "proposed" if read else (run.result or {}).get("reason", "aborted")
    db.commit()
    return read, outcome


def run_queued(db: Session, *, now: datetime | None = None, limit: int = 20) -> RunnerStats:
    """Exécute les procédures en file (flush seulement)."""
    if get_settings().real_ai_enabled:
        raise RealSlotNotCodedError("Slots IA réels des procédures pas encore codés : cartes V14+.")
    now = now or datetime.now(UTC)
    stats = RunnerStats()
    if local_executor.slot_mode(db, ai_slots.CHOOSE_MOVE_SLOT) != "off":
        limit = min(limit, LOCAL_PER_RUN)
    runs = db.scalars(select(PulseProcedureRun).where(PulseProcedureRun.status == "queued")
                      .order_by(PulseProcedureRun.created_at).limit(limit).with_for_update(skip_locked=True)).all()
    for run in runs:
        procedure = db.get(PulseProcedure, run.procedure_id)
        user = db.get(User, run.user_id)
        run.status, run.started_at = "running", now
        started = _emit(db, run, procedure, "pulse.procedure.started", causation_id=run.trigger_event_id)
        try:
            with db.begin_nested():  # une étape cassée annule ses écritures sans bloquer la file
                if procedure.code == P1:
                    _run_p1(db, run, user, now)
                else:
                    _abort(run, "not_coded", now)
        except Exception as exc:
            run.status, run.finished_at = "failed", now
            run.result = {"error": type(exc).__name__}
        stats.processed += 1
        stats.completed += run.status in ("completed", "waiting_user")
        stats.aborted += run.status == "aborted"
        stats.failed += run.status == "failed"
        event_type = "pulse.procedure.failed" if run.status == "failed" else "pulse.procedure.completed"
        _emit(db, run, procedure, event_type, causation_id=started.event_id)
    db.flush()
    return stats


def _log(run: PulseProcedureRun, order: int, kind: str, ref: str, status: str, **output) -> None:
    run.steps_log = [*run.steps_log, {"order": order, "type": kind, "ref": ref, "status": status, **output}]


def _abort(run: PulseProcedureRun, reason: str, now: datetime) -> None:
    run.status, run.finished_at, run.result = "aborted", now, {"reason": reason}


def _emit(db: Session, run: PulseProcedureRun, procedure: PulseProcedure, event_type: str, *,
          causation_id: str | None) -> Event:
    event = build_event(
        db, user_id=run.user_id, event_type=event_type,
        payload={"run_id": str(run.id), "procedure_code": procedure.code, "version": run.procedure_version,
                 "status": run.status},
        idempotency_key=f"{event_type}.{run.id}", source_app=SourceApp.pulse, privacy_level=PrivacyLevel.high,
        causation_id=causation_id,
    )
    db.add(event)
    db.flush()
    return event


# --- P1 : séance, menu des coups légaux, choix, validation, proposition ----------------------------

def _run_p1(db: Session, run: PulseProcedureRun, user: User, now: datetime) -> None:
    workout = db.get(PulseWorkout, UUID(run.inputs["workout_id"])) if run.inputs.get("workout_id") else None
    if workout is None or workout.user_id != user.id or workout.status != "planned" or workout.planned_at <= now:
        _log(run, 1, "code", "p1.load", "failed", reason="session_unavailable")
        return _abort(run, "session_unavailable", now)
    _log(run, 1, "code", "p1.load", "ok", workout_id=str(workout.id), workout_version=workout.version)
    blocks = db.execute(text("SELECT source_ref FROM v_pulse_active_blocks WHERE user_id = :u"), {"u": user.id}).all()
    if blocks:
        _log(run, 2, "code", "p1.legal_menu", "failed", reason="red_flag_block")
        return _abort(run, "red_flag_block", now)
    menu = legal_menu(db, user=user, workout=workout, now=now)
    _log(run, 2, "code", "p1.legal_menu", "ok", legal=[move["code"] for move in menu if move["legal"]])
    choice = dry_run_choice(menu)
    mode = local_executor.slot_mode(db, ai_slots.CHOOSE_MOVE_SLOT)
    if mode == "off":
        _log(run, 3, "llm_slot", ai_slots.CHOOSE_MOVE_SLOT, "ok", model_used=DRY_RUN, move_code=choice["move_code"])
    else:
        slot = _choose_move(db, run, workout, menu, mode)
        _log(run, 3, "llm_slot", ai_slots.CHOOSE_MOVE_SLOT, "ok" if slot.valid else "fallback",
             model_used=LOCAL_MODEL if mode == "live" else DRY_RUN, move_code=choice["move_code"], local=slot.record())
        if mode == "live":
            choice = _normalized(slot.output) if slot.valid else {**_maintain(),
                                                                   "rationale_fr": "Repli : sortie du modèle invalide."}
    errors = validate_choice(choice, menu)
    if errors:  # repli déterministe : sans programme, `reduce_volume` n'est jamais légal → `maintain`
        choice = {**_maintain(), "rationale_fr": "Repli : coup choisi invalide."}
    _log(run, 4, "code", "p1.validate", "ok" if not errors else "fallback", errors=errors)
    payload = {"procedure": P1, "workout_id": str(workout.id), "workout_version": workout.version, **choice}
    proposal = PulseProposal(id=uuid4(), user_id=user.id, procedure_run_id=run.id, kind="session_adaptation",
                             payload=payload, summary_fr=summary_fr(workout, choice), dry_run=run.dry_run,
                             created_at=now, presented_at=None if run.dry_run else now, expires_at=workout.planned_at)
    db.add(proposal)
    db.flush()
    _log(run, 5, "user_gate", "p1.proposal", "ok", proposal_id=str(proposal.id), presented=not run.dry_run)
    _log(run, 6, "code", "p1.apply", "skipped", reason="awaits_user_decision")
    run.status = "completed" if run.dry_run else "waiting_user"
    run.finished_at = now if run.dry_run else None
    run.result = {"proposal_id": str(proposal.id), "move_code": choice["move_code"], "dry_run": run.dry_run}
    if not run.dry_run:
        _proposal_event(db, proposal, "pulse.proposal.presented")


def _choose_move(db: Session, run: PulseProcedureRun, workout: PulseWorkout, menu: list[dict],
                 mode: str) -> ai_slots.SlotOutcome:
    """Slot local `pulse.p1.choose_move` : état résumé + menu légal (liste blanche, pas de texte libre)."""
    local = workout.planned_at.astimezone(PARIS)
    sets = training.workout_sets(workout)
    session = (f"type : {workout.session_type or 'non précisé'} ; intensité : {workout.intensity or 'non précisée'} ; "
               f"charge : {workout.systemic_load or 'non précisée'} ; durée : {workout.duration_minutes or DEFAULT_MINUTES} "
               f"min ; prévue le {local.strftime('%d/%m à %H:%M')} ; séries par groupe : "
               + (", ".join(f"{group}={count}" for group, count in sorted(sets.items())) or "non renseignées"))
    board = ""
    dispatch = db.get(PulseDispatchLog, run.dispatch_id) if run.dispatch_id else None
    if dispatch is not None:
        snapshot = db.get(PulseBoardSnapshot, dispatch.board_snapshot_id)
        board = ai_slots.board_lines(snapshot.board) if snapshot is not None else ""
    legal = [move for move in menu if move["legal"]]
    menu_text = "\n".join(f"{move['code']} — options : {move['options'] or 'aucun paramètre'}" for move in legal)
    reason = ADAPT_REASONS.get(run.inputs.get("reason") or "")  # code choisi dans une liste, jamais du texte libre
    user_prompt = ai_slots.assemble(session=session, board=board, constraints=f"demande : {reason}" if reason else "",
                                    menu=menu_text)
    return ai_slots.run_slot(slot_code=ai_slots.CHOOSE_MOVE_SLOT, mode=mode, system=ai_slots.CHOOSE_MOVE_SYSTEM,
                             user=user_prompt, schema=ai_slots.move_schema([move["code"] for move in legal]),
                             validate=lambda out: validate_choice(_normalized(out), menu), related_id=run.id)


def _normalized(output: dict) -> dict:
    """Garde seulement le paramètre utile au coup choisi (le schéma les rend tous facultatifs)."""
    key = PARAMETER_KEYS.get(output.get("move_code"))
    parameters = output.get("parameters") or {}
    return {"move_code": output.get("move_code"),
            "parameters": {key: parameters[key]} if key and key in parameters else {},
            "fallback_move_code": output.get("fallback_move_code"), "condition_fr": output.get("condition_fr"),
            "rationale_fr": output.get("rationale_fr"), "confidence": output.get("confidence")}


def inputs_for(db: Session, *, dispatch: PulseDispatchLog, code: str, now: datetime) -> dict | None:
    """Entrées d'une procédure nommée par l'interprète ; None = impossible à lancer (abandonnée)."""
    if code != P1:
        return {}
    if (dispatch.subject_ref or "").startswith("workout:"):
        return {"workout_id": dispatch.subject_ref.split(":", 1)[1]}
    end_of_day = datetime.combine(now.astimezone(PARIS).date() + timedelta(days=1), time.min, tzinfo=PARIS)
    workout_id = db.scalar(select(PulseWorkout.id).where(
        PulseWorkout.user_id == dispatch.user_id, PulseWorkout.status == "planned", PulseWorkout.planned_at > now,
        PulseWorkout.planned_at < end_of_day).order_by(PulseWorkout.planned_at).limit(1))
    return {"workout_id": str(workout_id)} if workout_id else None


def legal_menu(db: Session, *, user: User, workout: PulseWorkout, now: datetime) -> list[dict]:
    """Chaque coup du §8 avec sa légalité, ses raisons et ses options (fonction de lecture)."""
    local = workout.planned_at.astimezone(PARIS)
    minutes = workout.duration_minutes or DEFAULT_MINUTES
    menu = [{"code": "maintain", "legal": True, "reasons": [], "options": []}]

    times = []
    cursor = max(now.astimezone(PARIS), datetime.combine(local.date(), EARLIEST_START, tzinfo=PARIS)
                 - timedelta(minutes=STEP_MINUTES))
    cursor = _ceil(cursor + timedelta(minutes=STEP_MINUTES))
    last = datetime.combine(local.date(), LATEST_START, tzinfo=PARIS)
    while cursor <= last:
        if cursor != local and _slot_ok(db, user, workout, cursor, minutes):
            times.append(cursor.strftime("%H:%M"))
        cursor += timedelta(minutes=STEP_MINUTES)
    menu.append({"code": "shift_time", "legal": bool(times), "reasons": [] if times else ["no_free_slot"],
                 "options": times})

    dates = []
    for offset in range(1, 7):
        start = datetime.combine(local.date() + timedelta(days=offset), local.timetz().replace(tzinfo=None),
                                 tzinfo=PARIS)
        if _day_has_other_workout(db, user, workout, start.date()):
            continue
        if training.heavy(workout) and _high_next_door(db, user, workout, start.date()):
            continue
        if _slot_ok(db, user, workout, start, minutes):
            dates.append(start.date().isoformat())
    menu.append({"code": "reschedule", "legal": bool(dates), "reasons": [] if dates else ["no_free_day"],
                 "options": dates})
    menu += _program_moves(db, workout)
    inactive = set(db.scalars(select(PulseLegalMove.code).where(PulseLegalMove.active.is_(False))))
    for move in menu:
        if move["code"] in inactive and move["code"] != "maintain":
            move.update(legal=False, reasons=["inactive"], options=[])
    return menu


def _program_moves(db: Session, workout: PulseWorkout) -> list[dict]:
    """Coups qui exigent le programme actif de la séance (réduction, type, dette ; scission et décharge non codées)."""
    program = training.active_program(db, user_id=workout.user_id)
    if program is None or workout.program_id != program.id:
        return [{"code": code, "legal": False, "reasons": ["no_program"], "options": []} for code in PROGRAM_MOVES]
    groups = training.workout_sets(workout)
    debt, cap = training.debt_by_group(db, program=program), training.max_debt(db)

    def within_cap(delta: dict[str, int]) -> bool:
        return all(debt.get(group, 0) + count <= cap for group, count in delta.items())

    percents = [p for p in training.REDUCE_PERCENTS
                if (delta := training.reduced(workout.exercises, p)[1]) and within_cap(delta)]
    types = [t for t in SWAP_TYPES if t != workout.session_type] if groups and within_cap(groups) else []
    debts = [str(d.id) for d in training.open_debts(db, program=program)
             if d.muscle_group in groups and training.repay_room(db, program=program, workout=workout, debt=d) > 0]

    def entry(code: str, options: list, reason: str) -> dict:
        return {"code": code, "legal": bool(options), "reasons": [] if options else [reason], "options": options}

    return [
        entry("reduce_volume", percents, "no_muscle_groups" if not groups else "debt_max"),
        entry("swap_modality", types, "no_muscle_groups" if not groups else "debt_max"),
        {"code": "split_session", "legal": False, "reasons": ["not_coded"], "options": []},
        entry("repay_debt", debts, "no_repayable_debt"),
        {"code": "deload_week", "legal": False, "reasons": ["no_doctrine"], "options": []},
    ]


def dry_run_choice(menu: list[dict]) -> dict:
    """Choix FACTICE du slot (essai à blanc) : premier coup légal hors `maintain`, première option."""
    for move in menu:
        if move["legal"] and move["code"] != "maintain" and move["options"]:
            return {"move_code": move["code"], "parameters": {PARAMETER_KEYS[move["code"]]: move["options"][0]},
                    "fallback_move_code": None,
                    "condition_fr": None, "rationale_fr": "Essai à blanc : coup factice.", "confidence": "low"}
    return {**_maintain(), "rationale_fr": "Aucun coup légal hors maintien."}


def validate_choice(choice: dict, menu: list[dict]) -> list[str]:
    """Le coup doit être légal et ses paramètres pris dans ses options (fonction pure)."""
    move = next((m for m in menu if m["code"] == choice.get("move_code")), None)
    if move is None:
        return [f"unknown_move:{choice.get('move_code')}"]
    if not move["legal"]:
        return [f"illegal_move:{move['code']}"]
    parameters = choice.get("parameters") or {}
    key = PARAMETER_KEYS.get(move["code"])
    if key is not None and parameters.get(key) not in move["options"]:
        return [f"{move['code']}:{key}"]
    fallback = choice.get("fallback_move_code")
    if fallback is not None and fallback not in [m["code"] for m in menu if m["legal"]]:
        return [f"illegal_fallback:{fallback}"]
    return []


def summary_fr(workout: PulseWorkout, choice: dict) -> str:
    parameters = choice.get("parameters") or {}
    if choice["move_code"] == "shift_time":
        return f"Décaler la séance « {workout.title} » à {parameters['new_time']} le même jour."
    if choice["move_code"] == "reschedule":
        day = date.fromisoformat(parameters["target_date"])
        hour = workout.planned_at.astimezone(PARIS).strftime("%H:%M")
        return f"Reporter la séance « {workout.title} » au {day.strftime('%d/%m')} à {hour}."
    if choice["move_code"] == "reduce_volume":
        return (f"Ramener la séance « {workout.title} » à {parameters['percent']} % de ses séries ; "
                "les séries retirées passent en dette.")
    if choice["move_code"] == "swap_modality":
        return (f"Remplacer la séance « {workout.title} » par une séance légère ({parameters['new_session_type']}) ; "
                "ses séries passent en dette.")
    if choice["move_code"] == "repay_debt":
        return f"Ajouter à la séance « {workout.title} » des séries dues d'une séance précédente."
    return f"Garder la séance « {workout.title} » comme prévue."


def _maintain() -> dict:
    return {"move_code": "maintain", "parameters": {}, "fallback_move_code": None, "condition_fr": None,
            "confidence": "high"}


def _ceil(moment: datetime) -> datetime:
    moment = moment.replace(second=0, microsecond=0)
    extra = moment.minute % STEP_MINUTES
    return moment if extra == 0 else moment + timedelta(minutes=STEP_MINUTES - extra)


def _slot_ok(db: Session, user: User, workout: PulseWorkout, start: datetime, minutes: int) -> bool:
    end = start + timedelta(minutes=minutes)
    for busy_start, busy_end in _busy(db, user, workout, start - timedelta(hours=12), end + timedelta(hours=12)):
        if busy_start < end and start < busy_end:
            return False
    if training.heavy(workout):
        fast = fasting.window_fast(db, user, start)
        if fast is not None and (start - fast.suhoor_at) > timedelta(hours=12):
            return False
    return True


def _busy(db: Session, user: User, workout: PulseWorkout, start: datetime, end: datetime) -> list[tuple]:
    intervals = []
    for row in db.execute(select(PulseWorkout.planned_at, PulseWorkout.duration_minutes).where(
            PulseWorkout.user_id == user.id, PulseWorkout.id != workout.id, PulseWorkout.status == "planned",
            PulseWorkout.planned_at >= start, PulseWorkout.planned_at < end)):
        intervals.append((row.planned_at, row.planned_at + timedelta(minutes=row.duration_minutes or DEFAULT_MINUTES)))
    for row in db.execute(select(ImperiumMission.fixed_at, ImperiumMission.estimated_minutes).where(
            ImperiumMission.user_id == user.id, ImperiumMission.is_fixed_commitment.is_(True),
            ImperiumMission.status == "backlog", ImperiumMission.fixed_at >= start, ImperiumMission.fixed_at < end)):
        intervals.append((row.fixed_at, row.fixed_at + timedelta(minutes=row.estimated_minutes or DEFAULT_MINUTES)))
    for row in db.execute(select(ImperiumCalendarEvent.starts_at, ImperiumCalendarEvent.ends_at).where(
            ImperiumCalendarEvent.user_id == user.id, ImperiumCalendarEvent.blocks_time.is_(True),
            ImperiumCalendarEvent.deleted_at.is_(None), ImperiumCalendarEvent.starts_at < end,
            or_(ImperiumCalendarEvent.ends_at.is_(None), ImperiumCalendarEvent.ends_at > start))):
        intervals.append((row.starts_at, row.ends_at or row.starts_at + timedelta(minutes=DEFAULT_MINUTES)))
    return intervals


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=PARIS)
    return start, datetime.combine(day + timedelta(days=1), time.min, tzinfo=PARIS)


def _day_has_other_workout(db: Session, user: User, workout: PulseWorkout, day: date) -> bool:
    start, end = _day_bounds(day)
    return db.scalar(select(PulseWorkout.id).where(
        PulseWorkout.user_id == user.id, PulseWorkout.id != workout.id, PulseWorkout.status == "planned",
        PulseWorkout.planned_at >= start, PulseWorkout.planned_at < end).limit(1)) is not None


def _high_next_door(db: Session, user: User, workout: PulseWorkout, day: date) -> bool:
    start, _ = _day_bounds(day - timedelta(days=1))
    _, end = _day_bounds(day + timedelta(days=1))
    neighbours = db.scalars(select(PulseWorkout).where(
        PulseWorkout.user_id == user.id, PulseWorkout.id != workout.id,
        PulseWorkout.status.in_(("planned", "completed")), PulseWorkout.planned_at >= start,
        PulseWorkout.planned_at < end))
    return any(training.heavy(other) for other in neighbours)


# --- Couche propositions (no-override) ------------------------------------------------------------

def list_pending(db: Session, *, current_user: User, now: datetime | None = None) -> ProposalListResponse:
    now = now or datetime.now(UTC)
    rows = db.scalars(select(PulseProposal).where(
        PulseProposal.user_id == current_user.id, PulseProposal.presented_at.is_not(None),
        PulseProposal.decision.is_(None),
        or_(PulseProposal.expires_at.is_(None), PulseProposal.expires_at > now)).order_by(PulseProposal.presented_at))
    return ProposalListResponse(items=[ProposalRead.model_validate(row) for row in rows])


def decide(db: Session, *, current_user: User, proposal_id: UUID, payload: ProposalDecisionRequest,
           now: datetime | None = None) -> ProposalRead:
    now = now or datetime.now(UTC)
    proposal = db.get(PulseProposal, proposal_id, with_for_update=True)
    if proposal is None or proposal.user_id != current_user.id or proposal.presented_at is None:
        raise ProposalNotFoundError("Proposal not found.")
    if proposal.decision is not None:
        raise ProposalStateError("Proposal already decided.")
    explanation = (payload.user_explanation or "").strip() or None
    if proposal.expires_at is not None and proposal.expires_at <= now:
        _close(db, proposal, "expired", None, now)
        db.commit()
        raise ProposalStaleError("Proposal expired.")
    if payload.decision == "refused":
        if explanation is None:
            raise ProposalStateError("An explanation is required to refuse a proposal.")
        _close(db, proposal, "refused", explanation, now)
    else:
        move = {**proposal.payload, **(payload.modified_payload or {})} if payload.decision == "modified" else \
            proposal.payload
        if payload.decision == "modified":
            proposal.modified_payload = payload.modified_payload
        if not _apply(db, current_user, proposal, move, now):
            proposal.modified_payload = None
            _close(db, proposal, "expired", None, now)
            db.commit()
            raise ProposalStaleError("The session changed or the move is no longer legal.")
        _close(db, proposal, payload.decision, explanation, now)
        proposal.applied, proposal.applied_at = True, now
    read = ProposalRead.model_validate(proposal)
    db.commit()
    return read


def _apply(db: Session, user: User, proposal: PulseProposal, move: dict, now: datetime) -> bool:
    """Revalide le coup sur un menu frais puis applique son effet ; False si la séance a changé."""
    workout = db.get(PulseWorkout, UUID(proposal.payload["workout_id"]), with_for_update=True)
    if workout is None or workout.status != "planned" or workout.version != proposal.payload["workout_version"]:
        return False
    if validate_choice(move, legal_menu(db, user=user, workout=workout, now=now)):
        return False
    local = workout.planned_at.astimezone(PARIS)
    parameters = move.get("parameters") or {}
    if move["move_code"] == "shift_time":
        hour, minute = (int(part) for part in parameters["new_time"].split(":"))
        workout.planned_at = datetime.combine(local.date(), time(hour, minute), tzinfo=PARIS)
    elif move["move_code"] == "reschedule":
        workout.planned_at = datetime.combine(date.fromisoformat(parameters["target_date"]),
                                              local.timetz().replace(tzinfo=None), tzinfo=PARIS)
    elif move["move_code"] in ("reduce_volume", "swap_modality", "repay_debt"):
        _apply_program_move(db, workout, move, proposal, now)
    if move["move_code"] != "maintain":
        workout.version += 1
        program = db.get(PulseProgram, workout.program_id) if workout.program_id else None
        if program is not None:
            training.emit_program(db, program, "pulse.program.adapted", move_code=move["move_code"],
                                  session_id=str(workout.id))
    db.flush()
    return True


def _apply_program_move(db: Session, workout: PulseWorkout, move: dict, proposal: PulseProposal,
                        now: datetime) -> None:
    program = db.get(PulseProgram, workout.program_id)
    parameters = move.get("parameters") or {}
    if move["move_code"] == "reduce_volume":
        workout.exercises, delta = training.reduced(workout.exercises, int(parameters["percent"]))
        training.add_debts(db, program=program, workout=workout, delta=delta, proposal_id=proposal.id, now=now)
    elif move["move_code"] == "swap_modality":
        training.add_debts(db, program=program, workout=workout, delta=training.workout_sets(workout),
                           proposal_id=proposal.id, now=now)
        workout.session_type, workout.systemic_load, workout.intensity = parameters["new_session_type"], SWAP_LOAD, "low"
        workout.exercises = []
    else:
        debt = db.get(PulseVolumeDebt, UUID(parameters["debt_id"]), with_for_update=True)
        added = training.repay_room(db, program=program, workout=workout, debt=debt)
        training.schedule_repayment(db, debt=debt, workout=workout, added=added, proposal_id=proposal.id, now=now)


def _close(db: Session, proposal: PulseProposal, decision: str, explanation: str | None, now: datetime) -> None:
    proposal.decision, proposal.decided_at, proposal.user_explanation = decision, now, explanation
    run = db.get(PulseProcedureRun, proposal.procedure_run_id)
    if run.status == "waiting_user":
        run.status, run.finished_at = "completed", now
    _proposal_event(db, proposal, "pulse.proposal.decided")


def _proposal_event(db: Session, proposal: PulseProposal, event_type: str) -> None:
    db.add(build_event(
        db, user_id=proposal.user_id, event_type=event_type,
        payload={"proposal_id": str(proposal.id), "kind": proposal.kind, "decision": proposal.decision,
                 "has_explanation": proposal.user_explanation is not None},
        idempotency_key=f"{event_type}.{proposal.id}", source_app=SourceApp.pulse, privacy_level=PrivacyLevel.high,
    ))


def runner_job(ctx, window) -> None:
    """Job `pulse.procedure_runner` (semé désactivé) : vide la file en essai à blanc."""
    now = window.to_ts or datetime.now(UTC)
    ctx.cursor_ts = now
    stats = run_queued(ctx.db, now=now)
    ctx.db.commit()
    ctx.items_in, ctx.items_out = stats.processed, stats.completed
    ctx.detail = {"processed": stats.processed, "completed": stats.completed, "aborted": stats.aborted,
                  "failed": stats.failed, "model_used": DRY_RUN}
