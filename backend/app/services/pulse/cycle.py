"""Job `pulse.daily_cycle` — le cerveau de Pulse qui revient seul (bloc 2, 2026-10-22). Semé éteint.

Chaque jour à 6 h de Paris :
- révision du programme d'entraînement quand elle est due (`program_design.request_revision`, toutes les
  `pulse.program_revision_days`) — proposée, jamais appliquée sans l'utilisateur ;
- règles médicales PROPOSÉES après une prise de sang validée qui a des valeurs hors norme du labo (spécialiste
  santé, slot `pulse.lab_rules`, sinon modèle local `pulse.lab_rules_local`) ; elles restent `proposed` jusqu'aux
  trois confirmations de l'utilisateur (doc 34 §10.1). Sans cerveau branché, la prise de sang attend.
Le jour de la Weekly Review (`pulse.diet_auto_weekday`, mardi — décision utilisateur 2026-10-22) :
- 7 jours de repas demandés au cerveau à partir d'aujourd'hui (s'il n'y a rien pour aujourd'hui) ;
- dépôt dans la revue (docket, domaine pulse) de ce qui mérite d'en parler : articles de courses jamais achetés
  plusieurs semaines de suite (question à l'utilisateur), séances du programme peu suivies (anomalie). Données
  brutes gardées, l'utilisateur reste libre (doc 40 §10.7).
"""

import logging
from collections import Counter
from datetime import UTC, datetime, timedelta

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import KnowledgeInboxItem
from app.models.auth import User
from app.models.imperium import PulseWorkout
from app.models.pulse import PulseDietPlan, PulseLabResult, PulseShoppingItem
from app.models.wr import WrDocketItem
from app.schemas.pulse_diet import PlanRequest
from app.schemas.pulse_health import MedicalRuleCreate
from app.services.ai import cloud, local_executor
from app.services.params import get_parameter
from app.services.pulse import diet, goals, health_consent, labs, medical, program_design, training
from app.services.pulse.expiry import PARIS
from app.services.pulse.pantry_scan import normalize_name
from app.services.wr import docket

logger = logging.getLogger(__name__)

HOUR = 6
DAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
RULES_SLOT, RULES_LOCAL_SLOT = "pulse.lab_rules", "pulse.lab_rules_local"
NOT_BOUGHT_WEEKS = 2
ADHERENCE_FLOOR = 0.6
RULES_SYSTEM = (
    "Tu es le spécialiste santé d'un assistant personnel. À partir de valeurs d'une prise de sang hors de la norme du "
    "laboratoire, tu proposes au plus 5 règles pratiques et prudentes pour l'alimentation, l'entraînement ou le "
    "quotidien (types : nutrition_constraint, workout_limit, fasting_caution, general_context). Une valeur très "
    "éloignée de la norme donne une règle critical qui conseille de consulter son médecin. Pas de diagnostic, pas de "
    "médicament. source_quote = la valeur concernée telle qu'écrite. Réponds en français, en tutoyant, uniquement "
    "selon le schéma JSON."
)


def daily_cycle_job(ctx, window) -> None:  # noqa: ARG001 - signature du runner
    from app.services.wr.metrics import _job_user

    now = window.to_ts or datetime.now(UTC)
    if ctx.trigger != "manual" and now.astimezone(PARIS).hour != HOUR:
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"skipped": "not_cycle_hour"}
        return
    user = _job_user(ctx.db)
    detail = run(ctx.db, user, now) if user is not None else {"skipped": "no_user"}
    ctx.items_in = ctx.items_out = sum(v for v in detail.values() if isinstance(v, int))
    ctx.detail = detail


def run(db: Session, user: User, now: datetime, *, rules_call=None) -> dict:
    detail: dict = {}
    if training.programs_enabled(db):
        detail["revision_requested"] = int(program_design.request_revision(db, user, now) is not None)
        db.commit()
    detail["lab_rules_proposed"] = propose_lab_rules(db, user, call=rules_call)
    today = now.astimezone(PARIS).date()
    if DAYS[today.weekday()] == get_parameter(db, "pulse.diet_auto_weekday", default="TU"):
        detail["diet_requested"] = _request_week(db, user, today)
        detail["docket_items"] = _deposit_review_items(db, user, now)
        db.commit()
    return detail


# --- Semaine de repas -------------------------------------------------------------------------------------------

def _request_week(db: Session, user: User, today) -> int:
    if not diet.enabled(db):
        return 0
    exists = db.scalar(select(PulseDietPlan.id).where(PulseDietPlan.user_id == user.id, PulseDietPlan.week_start == today,
                                                      PulseDietPlan.status.in_(("generating", "proposed", "active"))))
    if exists is not None:
        return 0
    try:
        diet.request_plan(db, current_user=user, payload=PlanRequest(week_start=today, note=None),
                          idempotency_key=f"auto:{today.isoformat()}")
    except (diet.DietStateError, diet.DietIdempotencyConflictError):
        db.rollback()
        return 0
    return 1


# --- Weekly Review : ce qui mérite d'en parler ------------------------------------------------------------------

def _deposit_review_items(db: Session, user: User, now: datetime) -> int:
    deposited = 0
    since = now - timedelta(days=28)
    recent_titles = set(db.scalars(select(WrDocketItem.title_fr).where(
        WrDocketItem.user_id == user.id, WrDocketItem.domain == "pulse", WrDocketItem.created_at > now - timedelta(days=6))))
    for title, item_type, impact, payload in _review_findings(db, user, now, since):
        if title in recent_titles:
            continue
        docket.create_item(db, current_user=user, item_type=item_type, domain="pulse", title_fr=title, payload=payload,
                           evidence_refs={"source": "pulse.daily_cycle"}, impact_estimate=impact,
                           source_worker="phase1", now=now)
        deposited += 1
    return deposited


def _review_findings(db: Session, user: User, now: datetime, since: datetime) -> list[tuple[str, str, int, dict]]:
    findings = []
    # Courses jamais achetées : la même ligne laissée de côté sur plusieurs semaines (retirée ou jamais couverte).
    misses: set = set()  # (nom normalisé, plan) : une fois par semaine de repas
    names: dict = {}
    for item in db.scalars(select(PulseShoppingItem).where(
            PulseShoppingItem.user_id == user.id, PulseShoppingItem.created_at > since,
            PulseShoppingItem.status.in_(("removed", "superseded", "open")))):
        plan = db.get(PulseDietPlan, item.plan_id)
        if item.status == "open" and plan is not None and plan.week_start + timedelta(days=6) >= now.astimezone(PARIS).date():
            continue  # semaine en cours : il peut encore l'acheter
        key = normalize_name(item.name)
        misses.add((key, item.plan_id))
        names.setdefault(key, item.name)
    per_name = Counter(key for key, _plan in misses)
    skipped = sorted(names[key] for key, count in per_name.items() if count >= NOT_BOUGHT_WEEKS)
    if skipped:
        findings.append((f"Courses : « {', '.join(skipped[:4])} » jamais achetés depuis plusieurs semaines — une raison ?",
                         "user_question", 2, {"not_bought": skipped}))
    # Programme : séances de la semaine écoulée peu suivies.
    week = list(db.scalars(select(PulseWorkout).where(
        PulseWorkout.user_id == user.id, PulseWorkout.program_id.is_not(None),
        PulseWorkout.planned_at > now - timedelta(days=7), PulseWorkout.planned_at <= now)))
    done = sum(1 for w in week if w.status == "completed")
    if len(week) >= 2 and done / len(week) < ADHERENCE_FLOOR:
        reasons = sorted({w.skip_reason for w in week if w.status == "skipped" and w.skip_reason})
        findings.append((f"Sport : {done} séance{'s' if done > 1 else ''} faite{'s' if done > 1 else ''} sur {len(week)} "
                         "cette semaine", "anomaly", 3,
                         {"planned": len(week), "completed": done, "skip_reasons": reasons[:6],
                          "goals": goals.ranked_lines(db, user)[:3]}))
    return findings


# --- Règles médicales proposées après une prise de sang -----------------------------------------------------------

def rules_schema() -> dict:
    text = {"type": "string"}
    return {"type": "object", "additionalProperties": False, "required": ["rules"],
            "properties": {"rules": {"type": "array", "maxItems": 5, "items": {
                "type": "object", "additionalProperties": False,
                "required": ["rule_type", "rule_text", "severity", "source_quote"],
                "properties": {"rule_type": {"enum": ["nutrition_constraint", "workout_limit", "fasting_caution",
                                                      "general_context"]},
                               "rule_text": {"type": "string", "maxLength": 300},
                               "severity": {"enum": ["info", "warning", "critical"]}, "source_quote": text}}}}}


def propose_lab_rules(db: Session, user: User, *, call=None) -> int:
    """Prises de sang validées pas encore relues : règles proposées pour leurs valeurs hors norme du labo."""
    try:
        health_consent.require(db, user, "medical")
    except health_consent.ConsentRequiredError:
        return 0
    proposed = 0
    items = list(db.scalars(select(KnowledgeInboxItem).where(
        KnowledgeInboxItem.user_id == user.id, KnowledgeInboxItem.destination == labs.DESTINATION,
        KnowledgeInboxItem.status.in_(("validated", "vectorized")))))
    for item in items:
        final = dict(item.extraction_final or {})
        if final.get("rules_checked"):
            continue
        rows = list(db.scalars(select(PulseLabResult).where(PulseLabResult.inbox_item_id == item.id)))
        outside = [row for row in rows if labs.position(row) in ("below", "above")]
        if outside:
            lines = "\n".join(f"- {row.analyte} : {row.value} {row.unit or ''} (norme du labo {row.ref_low}–{row.ref_high}, "
                              f"{'sous' if labs.position(row) == 'below' else 'au-dessus de'} la norme, le {row.measured_on})"
                              for row in outside)
            prompt = ("## Objectifs de l'utilisateur (dans son ordre)\n" + ("\n".join(goals.ranked_lines(db, user)) or "aucun")
                      + f"\n\n## Valeurs hors norme du labo\n{lines}")
            output = (call or _default_rules_call(db, item))(RULES_SYSTEM, prompt, rules_schema())
            if output is None:  # aucun cerveau branché : la prise de sang attend
                continue
            for index, rule in enumerate((output.get("rules") or [])[:5]):
                try:
                    payload = MedicalRuleCreate(**rule)
                except (ValidationError, TypeError):
                    continue
                medical.create_rule(db, current_user=user, payload=payload, idempotency_key=f"labrule:{item.id}:{index}")
                proposed += 1
        item = db.get(KnowledgeInboxItem, item.id)
        item.extraction_final = {**(item.extraction_final or {}), "rules_checked": True}
        db.commit()
    return proposed


def _default_rules_call(db: Session, item: KnowledgeInboxItem):
    def call(system: str, prompt: str, schema: dict) -> dict | None:
        if cloud.slot_mode(db, RULES_SLOT) == "live":
            try:
                return cloud.structured(db, slot_code=RULES_SLOT, app_name="pulse", system=system, user=prompt,
                                        schema=schema, related_entity_type="knowledge_inbox_item",
                                        related_entity_id=item.id).output
            except cloud.CloudError as exc:
                logger.warning("pulse lab rules: cloud failed (%s)", str(exc)[:120])
        if local_executor.slot_mode(db, RULES_LOCAL_SLOT) == "live":
            try:
                return local_executor.structured(slot_code=RULES_LOCAL_SLOT, app_name="pulse", system=system, user=prompt,
                                                 schema=schema, max_tokens=1500, related_entity_type="knowledge_inbox_item",
                                                 related_entity_id=item.id).output
            except local_executor.LocalExecutorError:
                return None
        return None
    return call
