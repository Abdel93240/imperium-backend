"""W3 — extraction d'apprentissages (spec WR §4 W3, §6.1-6.2, §13.4-13.5 ; cartes V20 ACT-WR-10, V25 ACT-WR-16).

Clôtures d'épisode choisies par le code (`wr.episode_criteria`, éditable) : types d'events listés, ou
décision du docket validée ou refusée AVEC explication (hors auto-acceptation). Un épisode déjà
extrait n'est pas repris ; au plus `max_episodes_per_run` par passage.

Tant que `real_ai_enabled` est faux, l'extraction (§6.1) et le verdict d'identité (§6.2) sont
FACTICES : un pattern par épisode (`model_used=dry_run`), aucun voisin mémoire (recherche
vectorielle éteinte), donc une confrontation `unrelated` dont l'effet prévu est journalisé sans être
appliqué. Le code réel, lui, tourne déjà : règles de canonicité des statements (§6.1, constantes
testées §13.5) et validation du `context_predicate` contre le vocabulaire des rollups W1 (§13.4) ;
invalide → prédicat null. AUCUNE écriture dans ai_memories (DV-1, carte V25). W3 réel non codé :
avec `real_ai_enabled` vrai, le worker échoue sans avancer son curseur.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.auth import User
from app.models.event import Event
from app.models.wr import MemoryConfrontation, WrDocketItem, WrPatternExtraction
from app.services.params import get_parameter
from app.services.wr import causal

PARIS = ZoneInfo("Europe/Paris")
DRY_RUN = "dry_run"
DEFAULT_CRITERIA = {"event_types": [], "decided_with_note": False, "max_episodes_per_run": 20}

# §6.1 / §13.5 — canonicité d'un statement.
MAX_STATEMENT_CHARS = 240
RELATIVE_DATES = (
    "récemment", "dernièrement", "avant-hier", "hier", "aujourd'hui", "demain", "après-demain", "ce matin",
    "ce soir", "cette semaine", "ce mois-ci", "la semaine dernière", "le mois dernier", "l'an dernier",
    "bientôt", "tout à l'heure", "en ce moment", "actuellement", "ces jours-ci",
)
LEADING_PRONOUNS = frozenset({
    "il", "elle", "ils", "elles", "ça", "cela", "ceci", "c", "ce", "celui", "celle", "ceux", "celles", "on", "lui",
    "leur", "y", "en",
})

# §13.4 — vocabulaire des context_predicate, dérivé des rollups W1 (rollups.py) et du calendrier.
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
ROLLUP_FIELDS = {
    "finance": ("income_cents", "expense_cents", "net_cents", "transaction_count", "reversal_count", "pressure_score"),
    "rides": ("sessions_ended", "revenue_cents", "expense_cents", "worked_minutes", "net_per_hour_cents",
              "drop_zones"),
    "missions": ("started", "completed", "failed", "cancelled", "completed_late", "avg_deadline_drift_min",
                 "overdue_open_at_day_end"),
}
PREDICATE_FIELDS: dict[str, str] = {
    "day.day_of_week": "weekday",
    "day.is_weekend": "bool",
    **{f"{domain}.{metric}": "number" for domain, metrics in ROLLUP_FIELDS.items() for metric in metrics},
}
ORDER_OPS = frozenset({"<", "<=", ">", ">="})
PREDICATE_OPS = frozenset({"=", "!=", "in"}) | ORDER_OPS
MAX_CONDITIONS = 10

# §6.2 — effet appliqué par le code selon la relation (journalisé seulement en dry-run).
PLANNED_EFFECTS = {"duplicate": "increment", "reinforces": "increment", "refines": "refine_link",
                   "contradicts": "docket_contradiction", "unrelated": "new_pattern"}


class RealW3NotCodedError(RuntimeError):
    pass


@dataclass
class W3Stats:
    episodes: int = 0
    extractions: int = 0
    rejected: int = 0
    predicates_rejected: int = 0
    confrontations: int = 0


def canonical_errors(statement: str) -> list[str]:
    text = statement.strip()
    if not text:
        return ["empty"]
    errors = []
    if len(text) > MAX_STATEMENT_CHARS:
        errors.append("too_long")
    if "?" in text:
        errors.append("not_declarative")
    first = re.split(r"[\s'’]", text, maxsplit=1)[0].lower()
    if first in LEADING_PRONOUNS:
        errors.append("dangling_pronoun")
    lowered = text.lower().replace("’", "'")
    for term in RELATIVE_DATES:
        if re.search(rf"(?<![\w-]){re.escape(term)}(?![\w-])", lowered):
            errors.append(f"relative_date:{term}")
            break
    sentences = [part for part in re.split(r"[.!]\s+", text.rstrip(".! ")) if part.strip()]
    if ";" in text or len(sentences) > 1:
        errors.append("multiple_statements")
    return errors


def validate_predicate(predicate) -> dict | None:
    """Rend le prédicat s'il respecte le vocabulaire, sinon None (le pattern reste légal, §6.1)."""
    if not isinstance(predicate, dict) or len(predicate) != 1:
        return None
    (combinator, conditions), = predicate.items()
    if combinator not in ("all", "any") or not isinstance(conditions, list) or not 1 <= len(conditions) <= MAX_CONDITIONS:
        return None
    for condition in conditions:
        if not isinstance(condition, dict) or set(condition) != {"field", "op", "value"}:
            return None
        kind, op, value = PREDICATE_FIELDS.get(condition["field"]), condition["op"], condition["value"]
        if kind is None or op not in PREDICATE_OPS:
            return None
        values = value if op == "in" else [value]
        if op == "in" and (not isinstance(value, list) or not value):
            return None
        if kind == "number" and not all(isinstance(v, int | float) and not isinstance(v, bool) for v in values):
            return None
        if kind == "weekday" and (op in ORDER_OPS or not all(v in WEEKDAYS for v in values)):
            return None
        if kind == "bool" and (op not in ("=", "!=") or not isinstance(value, bool)):
            return None
    return predicate


def run_window(db: Session, *, user: User, window_from: datetime, window_to: datetime) -> W3Stats:
    if get_settings().real_ai_enabled:
        raise RealW3NotCodedError("W3 réel (extraction et identité par modèle) pas encore codé : carte V25.")
    criteria = {**DEFAULT_CRITERIA, **(get_parameter(db, "wr.episode_criteria", default={}) or {})}
    stats = W3Stats()
    for episode in episodes(db, user=user, window_from=window_from, window_to=window_to, criteria=criteria):
        stats.episodes += 1
        for pattern in _dry_run_extraction(episode):
            _record(db, user, episode, pattern, stats)
    db.flush()
    return stats


def episodes(db: Session, *, user: User, window_from: datetime, window_to: datetime, criteria: dict) -> list[Event]:
    events = db.scalars(
        select(Event).where(Event.user_id == user.id, Event.created_at > window_from, Event.created_at <= window_to)
        .order_by(Event.occurred_at)
    ).all()
    if not events:
        return []
    extracted = set(db.scalars(select(WrPatternExtraction.episode_event_id).where(
        WrPatternExtraction.episode_event_id.in_([event.id for event in events]))))
    selected = []
    for event in events:
        if event.id in extracted:
            continue
        if event.event_type in criteria["event_types"] or (
                criteria["decided_with_note"] and _explained_decision(db, event)):
            selected.append(event)
    return selected[: int(criteria["max_episodes_per_run"])]


def _explained_decision(db: Session, event: Event) -> bool:
    if event.event_type != "planning.docket.item_decided" or event.payload.get("status") not in ("validated", "refused"):
        return False
    item = db.get(WrDocketItem, event.payload.get("item_id"))
    return item is not None and item.autoaccept_class_id is None and bool((item.decision_note or "").strip())


def _dry_run_extraction(episode: Event) -> list[dict]:
    local = episode.occurred_at.astimezone(PARIS)
    return [{
        "statement_fr": f"L'épisode {episode.event_type} du {local.date().isoformat()} sert de pattern factice "
                        "à l'essai à blanc.",
        "domain": causal.DOCKET_DOMAINS.get(causal._family(episode.event_type), "wr"),
        "context_predicate": {"all": [{"field": "day.day_of_week", "op": "=", "value": WEEKDAYS[local.weekday()]}]},
        "evidence_event_ids": [episode.id],
        "suggested_confidence": 50,
    }]


def _record(db: Session, user: User, episode: Event, pattern: dict, stats: W3Stats) -> None:
    errors = canonical_errors(pattern["statement_fr"])
    predicate = validate_predicate(pattern.get("context_predicate"))
    rejected_predicate = pattern.get("context_predicate") is not None and predicate is None
    extraction = WrPatternExtraction(
        user_id=user.id, episode_event_id=episode.id, statement_fr=pattern["statement_fr"],
        pattern_domain=pattern["domain"], context_predicate=predicate, predicate_rejected=rejected_predicate,
        evidence_event_ids=list(pattern["evidence_event_ids"]),
        suggested_confidence=int(pattern["suggested_confidence"]), canonical_errors=errors, model_used=DRY_RUN,
        dry_run=True,
    )
    db.add(extraction)
    db.flush()
    stats.extractions += 1
    stats.predicates_rejected += int(rejected_predicate)
    if errors:
        stats.rejected += 1
        return
    # Voisins : top-K vectoriel sur ai_memories (§6.2) — éteint en dry-run (pas d'embeddings) : aucun voisin.
    db.add(MemoryConfrontation(
        user_id=user.id, extraction_id=extraction.id, new_statement=extraction.statement_fr, neighbor_memory_id=None,
        relation="unrelated", rationale_fr="[dry_run] aucun voisin : recherche vectorielle éteinte.",
        applied_effect=PLANNED_EFFECTS["unrelated"], model_used=DRY_RUN, dry_run=True,
    ))
    stats.confrontations += 1
