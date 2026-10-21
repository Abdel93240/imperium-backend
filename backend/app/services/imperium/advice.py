"""Conseil du jour du Dashboard (« Conseils IA », doc 65 §3) : une phrase utile tirée de l'état de la journée.

Le conseil est rangé sur la journée ouverte (`planning_days.advice`) avec la signature de l'état qui l'a produit
(mission en cours, proposition suivante, missions faites ou ratées, échéances, Weekly Review). À chaque lecture :
- même signature : le conseil rangé est rendu ;
- signature changée : un conseil écrit par des RÈGLES est calculé et rangé tout de suite (le Dashboard n'attend
  jamais), puis le modèle local (slot `imperium.advice`, live via `ai.local_slot_modes`) le réécrit en arrière-plan
  à partir du même contexte ; la lecture suivante rend sa version.
Contexte en liste blanche : la journée, les missions et leurs échéances, la Weekly Review ; jamais de santé, de
pratique religieuse ni de finances détaillées. Le modèle n'invente rien : il ne parle que de ce contexte.
"""

import hashlib
import json
import logging
import threading
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.imperium import ImperiumMission, ImperiumWeeklyReviewState
from app.services.ai import local_executor
from app.services.imperium import operations
from app.services.imperium.planning_days import get_current_planning_day

logger = logging.getLogger(__name__)

SLOT = "imperium.advice"
SOON_DAYS = 2
_refreshing: set[UUID] = set()
_lock = threading.Lock()

SYSTEM = (
    "Tu es Nexus, l'IA d'Imperium. Écris le conseil du jour affiché sur le tableau de bord de l'utilisateur : UN "
    "conseil concret et actionnable pour la suite de sa journée, tiré seulement du contexte fourni (n'invente "
    "aucune mission, échéance ni fait). Français, tutoiement, ton direct et bienveillant. title_fr : 40 "
    "caractères au plus. body_fr : une phrase, 160 caractères au plus. Ne répète pas mot pour mot le titre "
    "d'une mission si une reformulation suffit ; pas de liste, pas d'emoji."
)


def current(db: Session, *, current_user: User, now: datetime | None = None) -> tuple[dict | None, bool]:
    """(conseil à afficher, faut-il le faire réécrire par le modèle). None sans journée ouverte."""
    day = get_current_planning_day(db, current_user=current_user)
    if day is None:
        return None, False
    context = _context(db, current_user, now or datetime.now(UTC))
    # L'heure n'entre pas dans la signature : le conseil ne change qu'avec l'état de la journée.
    state = {key: value for key, value in context.items() if key != "heure"}
    signature = hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()[:16]
    stored = day.advice or {}
    if stored.get("signature") == signature:
        return stored, False
    title, body = _rules(context)
    advice = {"title": title, "body": body, "source": "rules", "signature": signature,
              "at": datetime.now(UTC).isoformat()}
    day.advice = advice
    db.commit()
    return advice, local_executor.slot_mode(db, SLOT) == "live"


def refresh_in_background(user_id: UUID) -> None:
    """Réécriture par le modèle local, hors de la requête ; une à la fois par utilisateur, ne lève jamais."""
    from app.db.session import SessionLocal

    with _lock:
        if user_id in _refreshing:
            return
        _refreshing.add(user_id)
    try:
        with SessionLocal() as db:
            user = db.get(User, user_id)
            if user is not None:
                rewrite(db, current_user=user)
    except Exception:  # noqa: BLE001 - le conseil ne doit jamais casser le Dashboard
        logger.exception("Daily advice rewrite failed.")
    finally:
        with _lock:
            _refreshing.discard(user_id)


def rewrite(db: Session, *, current_user: User, now: datetime | None = None) -> dict | None:
    """Le modèle local réécrit le conseil rangé (si l'état n'a pas changé entre-temps) ; None sinon."""
    day = get_current_planning_day(db, current_user=current_user)
    stored = (day.advice or {}) if day is not None else {}
    if day is None or stored.get("source") != "rules":
        return None
    context = _context(db, current_user, now or datetime.now(UTC))
    schema = {"type": "object", "additionalProperties": False, "required": ["title_fr", "body_fr"],
              "properties": {"title_fr": {"type": "string", "maxLength": 60},
                             "body_fr": {"type": "string", "maxLength": 220}}}
    prompt = ("Contexte de la journée :\n" + json.dumps(context, ensure_ascii=False, default=str)
              + f"\n\nConseil proposé par les règles : {stored['title']} — {stored['body']}\n"
              "Écris un meilleur conseil, ou garde l'idée des règles si c'est la plus utile.")
    try:
        output = local_executor.structured(slot_code=SLOT, app_name="imperium", system=SYSTEM, user=prompt,
                                           schema=schema, max_tokens=300, related_entity_type="planning_day",
                                           related_entity_id=day.id).output
    except local_executor.LocalExecutorError:
        return None
    db.refresh(day)
    if (day.advice or {}).get("signature") != stored["signature"]:
        return None  # l'état a changé pendant l'écriture : le prochain affichage recommencera
    title, body = str(output.get("title_fr") or "").strip()[:60], str(output.get("body_fr") or "").strip()[:220]
    if not title or not body:
        return None
    day.advice = {**stored, "title": title, "body": body, "source": "local", "at": datetime.now(UTC).isoformat()}
    db.commit()
    return day.advice


def _context(db: Session, user: User, now: datetime) -> dict:
    from app.services.daily import day_flow
    from app.services.imperium.weekly_review_state import reviewable_weeks

    local = now.astimezone(day_flow.PARIS)
    programme = day_flow.programme(db, current_user=user, now=now)
    active = next((i for i in programme.items if i.state == "active"), None)
    active_row = db.get(ImperiumMission, active.mission_id) if active else None
    upcoming = [m for m in operations.list_intrinsic_missions(db, current_user=user).missions if m.deadline_at
                and m.deadline_at.astimezone(day_flow.PARIS).date() <= local.date() + timedelta(days=SOON_DAYS)]
    week = reviewable_weeks(db, now)[0]
    wr = db.scalar(select(ImperiumWeeklyReviewState).where(ImperiumWeeklyReviewState.user_id == user.id,
                                                           ImperiumWeeklyReviewState.week_start == week))
    return {
        "date": local.date().isoformat(),
        "heure": local.strftime("%H:%M"),
        "mission_en_cours": {"titre": active.title, "fin_prevue": active_row.planned_end_at.astimezone(
            day_flow.PARIS).strftime("%H:%M") if active_row and active_row.planned_end_at else None} if active else None,
        "proposee_ensuite": next(({"titre": i.title, "minutes": i.estimated_minutes} for i in programme.items
                                  if i.state == "next"), None),
        "issue_du_moteur": programme.outcome,
        "faites_aujourdhui": [i.title for i in programme.items if i.state == "done"],
        "ratees_aujourdhui": [i.title for i in programme.items if i.state == "failed"],
        "echeances_proches": [{"titre": m.title, "echeance": m.deadline_at.astimezone(day_flow.PARIS).date().isoformat()}
                              for m in upcoming],
        "weekly_review_en_attente": bool(wr and wr.ready and not wr.launched),
    }


def _rules(context: dict) -> tuple[str, str]:
    """Le conseil sans modèle, par ordre d'importance."""
    soon = context["echeances_proches"]  # triées : la plus proche d'abord
    late = [item for item in soon if item["echeance"] <= context["date"]]
    if context["weekly_review_en_attente"]:
        return "Weekly Review en attente", "Prends un moment pour faire le point sur ta semaine : l'analyse est prête."
    if late and not context["mission_en_cours"]:
        return "Échéance aujourd'hui", f"« {late[0]['titre']} » est à faire aujourd'hui : garde-lui un créneau."
    if context["mission_en_cours"]:
        end = context["mission_en_cours"]["fin_prevue"]
        return "Reste concentré", (f"Termine « {context['mission_en_cours']['titre']} »"
                                   + (f" d'ici {end}" if end else "") + " avant de passer à la suite.")
    if context["ratees_aujourdhui"]:
        return "Repars sur du simple", "Une mission n'a pas abouti : enchaîne avec la suivante sans t'attarder."
    if context["proposee_ensuite"]:
        minutes = context["proposee_ensuite"]["minutes"]
        return "Prochaine étape", (f"« {context['proposee_ensuite']['titre']} » t'attend"
                                   + (f" ({minutes} min)" if minutes else "") + " : lance-la quand tu es prêt.")
    if soon:
        day = soon[0]["echeance"]
        return "À anticiper", f"« {soon[0]['titre']} » arrive à échéance le {day[8:10]}/{day[5:7]} : prépare-la."
    return "Journée libre", "Rien n'est prévu pour la suite : avance une mission de projet ou note une démarche avec Nexus."
