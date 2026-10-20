"""Sentinelle Pulse S1-S7 et runner de dispatch en essai à blanc (spec Pulse §3.2, §5, §6 ; cartes V10
ACT-PLS-10, ACT-PLS-13, ACT-PLS-15 partielle, V11 ACT-PLS-11, ACT-PLS-12, ACT-PLS-14). Code pur.

La sentinelle ne comprend rien : elle réveille. Seules les règles `active` (bascule SQL par code) sont lues.
- S1 (flag_count) et S2 (severity) : drapeaux frais du board, lus par `pulse.sentinel_tick` (*/15).
- S3 (user_report) : juste après un signalement ou une douleur, si son signal est frais et >= `min_band`.
- S4/S5 (scheduled) : une passe par jour à l'heure de Paris de `config.cron`, rattrapable pendant
  `grace_minutes` ; un board sans drapeau écrit `none_needed` / `skipped` sans file (skip gratuit).
- S6 (pre_session) : une fois par séance `planned` qui commence dans les `lead_minutes`.
- S7 (meta) : plafond de dispatchs par jour de Paris et dédup des mêmes drapeaux dans la fenêtre (sauf
  montée de bande). Garde TOUJOURS appliquée, avec la config de S7 même inactive.

Un réveil retenu fige le board (`pulse_board_snapshots`) puis met en file une ligne `pulse_dispatch_log`.
`pulse.dispatch_runner` la traite : tant que `real_ai_enabled` est faux, sortie factice `dry_run` validée
par le contrat de l'interprète (§6) contre le catalogue actif ; elle ne nomme que P1, pour un réveil
pré-séance quand P1 est active (exécution mise en file pour `pulse.procedure_runner`). Rien n'est
proposé ni notifié. Avec `real_ai_enabled` vrai (chaînes cloud), le runner échoue sans rien consommer.

Interprète LOCAL (`ai.local_slot_modes["pulse.interpreter"]`) : en `shadow`, l'exécuteur local lit le board
figé (entrée en liste blanche) et sa sortie est rangée sous `output.local`, l'issue reste celle de l'essai à
blanc ; en `live`, la sortie validée décide (procédures nommées, `none_needed`, `escalated` si confiance
basse ou drapeau — sans second regard cloud, rien n'est lancé —, `invalid_fallback` après deux échecs).
Au plus 3 réveils par passe quand le slot est allumé.
"""

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, time, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.imperium import PulseWorkout
from app.models.pulse import PulseBoardSnapshot, PulseDispatchLog, PulseProcedure, PulseProposal, PulseSentinelRule
from app.schemas.pulse_signals import BoardRead, DispatchListResponse, DispatchRead
from app.services.events.emitter import build_event
from app.services.ai import local_executor
from app.services.pulse import ai_slots, procedures, signals

PARIS = ZoneInfo("Europe/Paris")
BAND_ORDER = signals.BAND_ORDER
DEFAULT_GUARD = {"max_dispatch_per_day": 6, "dedup_window_min": 90}
SKIPPED = "skipped"
LOCAL_MODEL = "local_executor"  # rôle, jamais un nom de modèle
LOCAL_PER_RUN = 3
DRY_RUN = "dry_run"
CONFIDENCE = ("high", "medium", "low")
URGENCY = ("now", "today", "this_week")
OUTPUT_KEYS = ("procedures", "signals_used", "confidence", "escalate", "none_needed", "rationale_fr")


class RealInterpreterNotCodedError(RuntimeError):
    pass


class DispatchNotFoundError(ValueError):
    pass


@dataclass
class WakeResult:
    fired: bool
    reason: str  # queued|all_green|already|cooldown|daily_cap|dedup|below_threshold
    dispatch_id: UUID | None = None


@dataclass
class TickStats:
    rules: int = 0
    queued: int = 0
    skipped_green: int = 0
    held: dict = field(default_factory=dict)


def rank(band: str | None) -> int:
    return BAND_ORDER.index(band) if band in BAND_ORDER else 0


def flag_set(board: BoardRead) -> dict[str, str]:
    """Drapeaux frais du board : {code: bande}. Un signal périmé n'a jamais de drapeau."""
    return {signal.code: signal.band for signal in board.signals if signal.flag}


def same_flags(new: dict[str, str], previous: dict[str, str]) -> bool:
    """Mêmes codes et aucune bande en hausse : le réveil n'apporte rien (dédup S7)."""
    return set(new) == set(previous) and all(rank(band) <= rank(previous[code]) for code, band in new.items())


def scheduled_due(config: dict, now: datetime) -> str | None:
    """Jour de Paris de la passe si `now` tombe dans [heure du cron, + grace[ ; None sinon (fonction pure)."""
    minute, hour = (int(part) for part in config["cron"].split()[:2])
    local = now.astimezone(ZoneInfo(config.get("timezone", "Europe/Paris")))
    target = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= local < target + timedelta(minutes=int(config.get("grace_minutes", 60))):
        return local.date().isoformat()
    return None


def _guard(db: Session) -> dict:
    config = db.scalar(select(PulseSentinelRule.config).where(PulseSentinelRule.rule_type == "meta").limit(1))
    return {**DEFAULT_GUARD, **(config or {})}


def _active(db: Session, *types: str) -> list[PulseSentinelRule]:
    return list(db.scalars(select(PulseSentinelRule).where(
        PulseSentinelRule.active.is_(True), PulseSentinelRule.rule_type.in_(types)).order_by(PulseSentinelRule.code)))


def _dispatched(user: User):
    """Réveils qui comptent pour le garde-fou : tout sauf les passes vertes gratuites."""
    return select(PulseDispatchLog).where(PulseDispatchLog.user_id == user.id, or_(
        PulseDispatchLog.model_used.is_(None), PulseDispatchLog.model_used != SKIPPED))


def wake(db: Session, *, user: User, rule: PulseSentinelRule, now: datetime, subject_ref: str | None = None,
         causation_id: str | None = None, board: BoardRead | None = None) -> WakeResult:
    """Réveil candidat (flush seulement) : cooldown de la règle, puis garde S7, puis snapshot et file."""
    if subject_ref is not None and db.scalar(select(PulseDispatchLog.id).where(
            PulseDispatchLog.user_id == user.id, PulseDispatchLog.triggered_by == rule.code,
            PulseDispatchLog.subject_ref == subject_ref).limit(1)) is not None:
        return WakeResult(False, "already")
    current = board or signals.board(db, current_user=user, now=now)
    flags = flag_set(current)
    if rule.rule_type == "scheduled" and not flags:
        dispatch = _record(db, user, rule, now, subject_ref, current, flags, status="done", model_used=SKIPPED,
                           valid=True, outcome="none_needed", procedures_named=[], completed_at=now)
        return WakeResult(False, "all_green", dispatch.id)
    if rule.cooldown_minutes and db.scalar(_dispatched(user).where(
            PulseDispatchLog.triggered_by == rule.code,
            PulseDispatchLog.created_at > now - timedelta(minutes=rule.cooldown_minutes)).limit(1)) is not None:
        return WakeResult(False, "cooldown")
    guard = _guard(db)
    day_start = datetime.combine(now.astimezone(PARIS).date(), time.min, tzinfo=PARIS)
    today = db.scalar(select(func.count()).select_from(
        _dispatched(user).where(PulseDispatchLog.created_at >= day_start).subquery()))
    if today >= int(guard["max_dispatch_per_day"]):
        return WakeResult(False, "daily_cap")
    previous = db.scalar(_dispatched(user).where(
        PulseDispatchLog.created_at > now - timedelta(minutes=int(guard["dedup_window_min"])))
        .order_by(PulseDispatchLog.created_at.desc()).limit(1))
    if previous is not None and same_flags(flags, previous.flag_set):
        return WakeResult(False, "dedup")
    dispatch = _record(db, user, rule, now, subject_ref, current, flags, status="queued")
    event = build_event(
        db, user_id=user.id, event_type="pulse.sentinel.triggered",
        payload={"rule_code": rule.code, "snapshot_id": str(dispatch.board_snapshot_id), "flags_count": len(flags),
                 "dispatch_id": str(dispatch.id)},
        idempotency_key=f"pulse.sentinel.triggered.{dispatch.id}", source_app=SourceApp.pulse,
        privacy_level=PrivacyLevel.high, causation_id=causation_id,
    )
    db.add(event)
    dispatch.trigger_event_id = event.event_id
    db.flush()
    return WakeResult(True, "queued", dispatch.id)


def _record(db: Session, user: User, rule: PulseSentinelRule, now: datetime, subject_ref: str | None,
            board: BoardRead, flags: dict, **fields) -> PulseDispatchLog:
    snapshot = PulseBoardSnapshot(id=uuid4(), user_id=user.id, taken_at=now, reason=rule.code,
                                  board=frozen(board), flags_count=len(flags),
                                  max_severity=max(flags.values(), key=rank, default="green"))
    db.add(snapshot)
    db.flush()
    dispatch = PulseDispatchLog(id=uuid4(), user_id=user.id, triggered_by=rule.code, subject_ref=subject_ref,
                                board_snapshot_id=snapshot.id, flag_set=flags, created_at=now, **fields)
    db.add(dispatch)
    db.flush()
    return dispatch


def frozen(board: BoardRead) -> dict:
    """Board figé : valeur, bande, âge par signal et red flags par référence ; jamais de `detail`."""
    return {
        "generated_at": board.generated_at.isoformat(),
        "signals": [{"code": s.code, "state": s.state, "value": s.value, "band": s.band, "flag": s.flag,
                     "age_min": s.age_min} for s in board.signals],
        "red_flags": [{"id": str(f.id), "rule_code": f.rule_code, "severity": f.severity,
                       "blocks_training": f.blocks_training} for f in board.red_flags],
    }


def on_user_report(db: Session, *, current_user: User, signal_code: str, subject_ref: str,
                   now: datetime | None = None, causation_id: str | None = None) -> WakeResult | None:
    """S3 : réveil immédiat sur un signalement frais >= `min_band` (cooldown 0, garde S7)."""
    rules = _active(db, "user_report")
    if not rules:
        return None
    now = now or datetime.now(UTC)
    current = signals.board(db, current_user=current_user, now=now)
    signal = next((s for s in current.signals if s.code == signal_code), None)
    rule = rules[0]
    if signal is None or not signal.flag or rank(signal.band) < rank(rule.config.get("min_band", "yellow")):
        return WakeResult(False, "below_threshold")
    return wake(db, user=current_user, rule=rule, now=now, subject_ref=subject_ref, causation_id=causation_id,
                board=current)


def tick(db: Session, *, current_user: User, now: datetime | None = None) -> TickStats:
    """Passe de la sentinelle (flush seulement) : S4/S5 dues, S6 imminentes, puis S1 et S2."""
    now = now or datetime.now(UTC)
    stats = TickStats()
    rules = _active(db, "scheduled", "pre_session", "flag_count", "severity")
    if not rules:
        return stats
    current = signals.board(db, current_user=current_user, now=now)
    flags = flag_set(current)
    for rule in sorted(rules, key=lambda r: ("scheduled", "pre_session", "flag_count", "severity").index(r.rule_type)):
        stats.rules += 1
        for subject_ref in _subjects(db, current_user, rule, flags, now):
            result = wake(db, user=current_user, rule=rule, now=now, subject_ref=subject_ref, board=current)
            if result.fired:
                stats.queued += 1
            elif result.reason == "all_green":
                stats.skipped_green += 1
            else:
                stats.held[result.reason] = stats.held.get(result.reason, 0) + 1
    return stats


def _subjects(db: Session, user: User, rule: PulseSentinelRule, flags: dict, now: datetime) -> list[str | None]:
    config = rule.config
    if rule.rule_type == "scheduled":
        day = scheduled_due(config, now)
        return [] if day is None else [day]
    if rule.rule_type == "pre_session":
        ids = db.scalars(select(PulseWorkout.id).where(
            PulseWorkout.user_id == user.id, PulseWorkout.status == "planned", PulseWorkout.planned_at > now,
            PulseWorkout.planned_at <= now + timedelta(minutes=int(config.get("lead_minutes", 180))),
        ).order_by(PulseWorkout.planned_at))
        return [f"workout:{workout_id}" for workout_id in ids]
    floor = rank(config.get("min_band", "yellow" if rule.rule_type == "flag_count" else "orange"))
    hits = [code for code, band in flags.items() if rank(band) >= floor]
    if rule.rule_type == "flag_count":
        return [None] if len(hits) >= int(config.get("min_flags", 2)) else []
    return [None] if hits else []


# --- Interprète : contrat de sortie (§6) et runner en essai à blanc ------------------------------

def validate_output(output: dict, *, catalogue: set[str]) -> list[str]:
    """Erreurs de la sortie de l'interprète (fonction pure) ; une procédure hors catalogue actif invalide."""
    errors = [f"missing:{key}" for key in OUTPUT_KEYS if key not in output]
    if errors:
        return errors
    if not isinstance(output["procedures"], list):
        return ["procedures:not_a_list"]
    for item in output["procedures"]:
        if not isinstance(item, dict) or "code" not in item or "urgency" not in item:
            errors.append("procedures:item_shape")
            continue
        if item["code"] not in catalogue:
            errors.append(f"procedures:unknown_code:{item['code']}")
        if item["urgency"] not in URGENCY:
            errors.append(f"procedures:urgency:{item['urgency']}")
    if output["confidence"] not in CONFIDENCE:
        errors.append("confidence")
    if not isinstance(output["escalate"], bool) or not isinstance(output["none_needed"], bool):
        errors.append("booleans")
    if not isinstance(output["signals_used"], list):
        errors.append("signals_used")
    if not isinstance(output["rationale_fr"], str) or len(output["rationale_fr"]) > 400:
        errors.append("rationale_fr")
    return errors


def dry_run_output(flags: dict[str, str], *, subject_ref: str | None = None, catalogue: set[str] = frozenset()) -> dict:
    """Sortie FACTICE : nomme P1 pour un réveil pré-séance quand P1 est active, sinon rien."""
    if subject_ref and subject_ref.startswith("workout:") and procedures.P1 in catalogue:
        return {"procedures": [{"code": procedures.P1, "urgency": "today",
                                "inputs": {"workout_id": subject_ref.split(":", 1)[1]}}],
                "signals_used": sorted(flags), "confidence": "high", "escalate": False, "none_needed": False,
                "rationale_fr": "Essai à blanc : séance imminente, adaptation à examiner."}
    return {"procedures": [], "signals_used": sorted(flags), "confidence": "high", "escalate": False,
            "none_needed": not flags, "rationale_fr": "Essai à blanc : aucun modèle appelé, aucune procédure nommée."}


def run_dispatches(db: Session, *, now: datetime | None = None, limit: int = 50) -> int:
    """Traite les réveils en file (flush seulement) ; renvoie le nombre traité."""
    if get_settings().real_ai_enabled:
        raise RealInterpreterNotCodedError("Interprète réel pas encore codé : cartes V13+.")
    now = now or datetime.now(UTC)
    queued = db.scalars(select(PulseDispatchLog).where(PulseDispatchLog.status == "queued")
                        .order_by(PulseDispatchLog.created_at).limit(limit).with_for_update(skip_locked=True)).all()
    catalogue = procedures.active_catalogue(db)
    mode = local_executor.slot_mode(db, ai_slots.INTERPRETER_SLOT)
    if mode != "off":
        queued = queued[:LOCAL_PER_RUN]  # un appel local coûte des secondes : la file se vide en plusieurs passes
    for dispatch in queued:
        output = dry_run_output(dispatch.flag_set, subject_ref=dispatch.subject_ref, catalogue=catalogue)
        dispatch.output = {**output, "dry_run": True}
        dispatch.valid = not validate_output(output, catalogue=catalogue)
        named = output["procedures"] if dispatch.valid else []
        dispatch.model_used, dispatch.procedures_named = DRY_RUN, [item["code"] for item in named]
        dispatch.outcome = "procedures_run" if named else DRY_RUN
        dispatch.escalated, dispatch.status, dispatch.completed_at = False, "done", now
        if mode != "off":
            slot = _interpret(db, dispatch, catalogue, mode)
            dispatch.output = {**dispatch.output, "local": slot.record()}
            if mode == "live":
                output, named = _apply_live(db, dispatch, slot, now)
        completed = build_event(
            db, user_id=dispatch.user_id, event_type="pulse.dispatch.completed",
            payload={"dispatch_id": str(dispatch.id), "outcome": dispatch.outcome,
                     "procedures_named": dispatch.procedures_named, "confidence": output.get("confidence"),
                     "escalated": dispatch.escalated},
            idempotency_key=f"pulse.dispatch.completed.{dispatch.id}", source_app=SourceApp.pulse,
            privacy_level=PrivacyLevel.high, causation_id=dispatch.trigger_event_id,
        )
        db.add(completed)
        db.flush()
        if named:
            procedures.queue_from_dispatch(db, dispatch=dispatch, named=named, trigger=completed, now=now)
    db.flush()
    return len(queued)


def _interpret(db: Session, dispatch: PulseDispatchLog, catalogue: set[str], mode: str) -> ai_slots.SlotOutcome:
    """Appel local de l'interprète sur le board figé du réveil (entrée en liste blanche)."""
    snapshot = db.get(PulseBoardSnapshot, dispatch.board_snapshot_id)
    procedures_rows = db.scalars(select(PulseProcedure).where(PulseProcedure.active.is_(True))
                                 .order_by(PulseProcedure.code)).all()
    catalogue_text = "\n".join(f"{p.code} — {p.purpose_fr} — déclencheurs : {', '.join(p.trigger_types)}"
                                for p in procedures_rows)
    red = [f"{flag['rule_code']} ({flag['severity']})" for flag in snapshot.board.get("red_flags", [])]
    pending = db.scalar(select(func.count()).select_from(PulseProposal).where(
        PulseProposal.user_id == dispatch.user_id, PulseProposal.decision.is_(None),
        PulseProposal.presented_at.is_not(None)))
    constraints = (f"réveil : {dispatch.triggered_by}" + (" (séance imminente)" if (dispatch.subject_ref or "")
                   .startswith("workout:") else "") + f"\nalertes santé ouvertes : {', '.join(red) or 'aucune'}"
                   f"\npropositions en attente : {pending}")
    user = ai_slots.assemble(board=ai_slots.board_lines(snapshot.board), catalogue=catalogue_text or "vide",
                             constraints=constraints)
    codes = sorted(catalogue)
    return ai_slots.run_slot(slot_code=ai_slots.INTERPRETER_SLOT, mode=mode, system=ai_slots.INTERPRETER_SYSTEM,
                             user=user, schema=ai_slots.interpreter_schema(codes),
                             validate=lambda out: validate_output(out, catalogue=catalogue), related_id=dispatch.id)


def _apply_live(db: Session, dispatch: PulseDispatchLog, slot: ai_slots.SlotOutcome, now: datetime
                ) -> tuple[dict, list[dict]]:
    """Mode live : la sortie validée remplace la factice. Escalade (confiance basse ou drapeau) : le
    second regard cloud n'est pas autorisé, rien n'est lancé et le réveil est marqué escaladé."""
    dispatch.model_used = LOCAL_MODEL
    dispatch.prompt_tokens, dispatch.output_tokens = slot.prompt_tokens, slot.output_tokens
    dispatch.latency_ms = slot.latency_ms
    if not slot.valid:
        dispatch.valid, dispatch.outcome, dispatch.procedures_named = False, "invalid_fallback", []
        return {}, []
    output = slot.output
    dispatch.valid = True
    if output["escalate"] or output["confidence"] == "low":
        dispatch.escalated, dispatch.outcome, dispatch.procedures_named = True, "escalated", []
        return output, []
    named = []
    for item in output["procedures"]:
        inputs = procedures.inputs_for(db, dispatch=dispatch, code=item["code"], now=now)
        if inputs is not None:
            named.append({**item, "inputs": inputs})
    dispatch.procedures_named = [item["code"] for item in named]
    dispatch.outcome = "procedures_run" if named else "none_needed"
    return output, named


# --- Lecture, annotation, oubli ----------------------------------------------------------------

def list_dispatches(db: Session, *, current_user: User, limit: int = 50) -> DispatchListResponse:
    rows = db.scalars(select(PulseDispatchLog).where(PulseDispatchLog.user_id == current_user.id)
                      .order_by(PulseDispatchLog.created_at.desc()).limit(limit))
    return DispatchListResponse(items=[DispatchRead.model_validate(row) for row in rows])


def react(db: Session, *, current_user: User, dispatch_id: UUID, reaction: str,
          now: datetime | None = None) -> DispatchRead:
    """Annotation a posteriori useful|useless|missed (remplace la précédente)."""
    dispatch = db.get(PulseDispatchLog, dispatch_id)
    if dispatch is None or dispatch.user_id != current_user.id:
        raise DispatchNotFoundError("Dispatch not found.")
    dispatch.user_reaction, dispatch.reacted_at = reaction, now or datetime.now(UTC)
    read = DispatchRead.model_validate(dispatch)
    db.commit()
    return read


def forget_history(db: Session, *, current_user: User) -> int:
    """Suppression réelle des réveils et des boards figés de l'utilisateur."""
    count = db.scalar(select(func.count()).select_from(PulseDispatchLog).where(
        PulseDispatchLog.user_id == current_user.id))
    db.execute(delete(PulseDispatchLog).where(PulseDispatchLog.user_id == current_user.id))
    db.execute(delete(PulseBoardSnapshot).where(PulseBoardSnapshot.user_id == current_user.id))
    db.commit()
    return count


# --- Jobs (semés désactivés) -------------------------------------------------------------------

def tick_job(ctx, window) -> None:
    """Job `pulse.sentinel_tick` : passe de la sentinelle pour l'utilisateur."""
    from app.services.wr.metrics import _job_user

    now = window.to_ts or datetime.now(UTC)
    ctx.cursor_ts = now
    user = _job_user(ctx.db)
    if user is None:
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"skip": "no_user"}
        return
    stats = tick(ctx.db, current_user=user, now=now)
    ctx.db.commit()
    ctx.items_in, ctx.items_out = stats.rules, stats.queued
    ctx.detail = asdict(stats)


def dispatch_job(ctx, window) -> None:
    """Job `pulse.dispatch_runner` : vide la file en essai à blanc."""
    now = window.to_ts or datetime.now(UTC)
    ctx.cursor_ts = now
    processed = run_dispatches(ctx.db, now=now)
    ctx.db.commit()
    ctx.items_in = ctx.items_out = processed
    ctx.detail = {"processed": processed, "model_used": DRY_RUN}
