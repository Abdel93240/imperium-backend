"""Règles métier Vector (doc 57 §4) et signal « règles seules » de la phase de démarrage (§3.1).

Règles codées, calculables sans donnée externe (codes postaux, créneau, type de course) :
- R1 : pas de 8e arrondissement (prise en charge ou dépose 75008) → rouge ;
- R2 : 18e / 19e en journée (prise en charge 75018, 75019, 10 h–16 h) → rouge ;
- R7 : retour vers Paris la nuit (dépose 75…, créneaux night / late_evening) → vert ;
- R8 : course programmée la nuit → vert.
R3, R5, R6, R10 attendent la géographie ou des flux externes ; R4, R9, R11 ne notent pas
une course (doc 57 §4.4, §4.9, §4.11).

Signal : une règle rouge déclenchée → rouge (prudence, même si une verte l'est aussi) ;
sinon une verte → vert ; sinon aucun signal : « Haute incertitude, à toi de juger. »
Une règle dont la donnée manque (code postal absent) ne se déclenche pas. Les règles se
révisent par l'utilisateur, avec un historique ; Vector conseille, l'utilisateur décide.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.rides import RidesBusinessRule, RidesRuleRevision
from app.schemas.rides import BusinessRuleListResponse, BusinessRuleRead, BusinessRuleUpdate
from app.services.events.emitter import build_event
from app.services.vector.scoring import VECTOR_ABSTENTION_MESSAGE

NIGHT = ["night", "late_evening"]
DEFAULT_RULES = (
    ("R1", "Éviter le 8e arrondissement", "Mauvais flux, faible rentabilité réelle, perte de temps.",
     {"zone_codes": ["75008"], "applies_to": ["pickup", "destination"]}, "red"),
    ("R2", "Éviter le 18e et le 19e en journée", "Zones peu rentables en journée : mieux vaut se repositionner.",
     {"zone_codes": ["75018", "75019"], "applies_to": ["pickup"], "time_blocks": ["daytime"]}, "red"),
    ("R7", "Retour vers Paris la nuit", "Revenir progressivement vers la zone dense, même après une course extérieure.",
     {"destination_prefixes": ["75"], "time_blocks": NIGHT}, "green"),
    ("R8", "Course programmée la nuit", "Une course programmée la nuit sécurise le chiffre d'affaires.",
     {"ride_types": ["scheduled"], "time_blocks": NIGHT}, "green"),
)
NOT_CODED = ["R3", "R4", "R5", "R6", "R9", "R10", "R11"]


class RuleNotFoundError(ValueError):
    pass


class RuleVersionConflictError(ValueError):
    def __init__(self, current: BusinessRuleRead) -> None:
        super().__init__("Cette règle a changé depuis ta lecture.")
        self.current = current


def ensure_rules(db: Session, user: User) -> list[RidesBusinessRule]:
    """Règles de départ créées à la première lecture (une fois par utilisateur)."""
    rules = list(db.scalars(select(RidesBusinessRule).where(RidesBusinessRule.user_id == user.id).order_by(RidesBusinessRule.rule_code)))
    known = {rule.rule_code for rule in rules}
    missing = [rule for rule in DEFAULT_RULES if rule[0] not in known]
    for code, name, description, conditions, action in missing:
        db.add(RidesBusinessRule(user_id=user.id, rule_code=code, name=name, description=description, conditions=conditions,
                                 action=action, is_active=True, version=1))
    if missing:
        db.flush()
        rules = list(db.scalars(select(RidesBusinessRule).where(RidesBusinessRule.user_id == user.id).order_by(RidesBusinessRule.rule_code)))
    return rules


def list_rules(db: Session, *, current_user: User) -> BusinessRuleListResponse:
    rules = ensure_rules(db, current_user)
    db.commit()
    return BusinessRuleListResponse(items=[BusinessRuleRead.model_validate(rule) for rule in rules], not_coded=NOT_CODED)


def update_rule(db: Session, *, current_user: User, rule_code: str, payload: BusinessRuleUpdate) -> BusinessRuleRead:
    ensure_rules(db, current_user)
    rule = db.scalar(
        select(RidesBusinessRule).where(RidesBusinessRule.user_id == current_user.id, RidesBusinessRule.rule_code == rule_code)
        .with_for_update()
    )
    if rule is None:
        raise RuleNotFoundError("Règle introuvable.")
    if rule.version != payload.version:
        raise RuleVersionConflictError(BusinessRuleRead.model_validate(rule))
    previous = _snapshot(rule)
    if payload.is_active is not None:
        rule.is_active = payload.is_active
    if payload.is_hard_rule is not None:
        rule.is_hard_rule = payload.is_hard_rule
    if payload.conditions is not None:
        rule.conditions = payload.conditions.model_dump(exclude_none=True)
    new = _snapshot(rule)
    if new == previous:
        return BusinessRuleRead.model_validate(rule)
    now = datetime.now(UTC)
    rule.version += 1
    rule.revision_count += 1
    rule.last_revised_at = now
    revision_type = _revision_type(previous, new)
    db.add(RidesRuleRevision(rule_id=rule.id, revised_at=now, revision_type=revision_type, reason=payload.reason.strip(),
                             previous=previous, new=new, proposed_by="user_manual", user_validated=True))
    db.flush()
    db.add(
        build_event(
            db, user_id=current_user.id, event_type="rides.rule.revised",
            payload={"rule_code": rule.rule_code, "revision_type": revision_type, "version": rule.version},
            idempotency_key=f"rides.rule.revised.{rule.id}.v{rule.version}", source_app=SourceApp.vector,
            privacy_level=PrivacyLevel.low,
        )
    )
    db.refresh(rule)
    read = BusinessRuleRead.model_validate(rule)
    db.commit()
    return read


def evaluate(rules: list[RidesBusinessRule], facts: dict) -> tuple[str | None, list[str], str]:
    """(signal, règles déclenchées, raison) pour une course ; les règles inactives sont ignorées."""
    fired = [rule for rule in rules if rule.is_active and _matches(rule.conditions, facts)]
    for rule in fired:
        rule.times_applied += 1
    red = [rule for rule in fired if rule.action == "red"]
    green = [rule for rule in fired if rule.action == "green"]
    codes = [rule.rule_code for rule in fired]
    if red:
        return "red", codes, " ; ".join(f"{rule.rule_code} : {rule.name}" for rule in red) + "."
    if green:
        return "green", codes, " ; ".join(f"{rule.rule_code} : {rule.name}" for rule in green) + "."
    return None, codes, VECTOR_ABSTENTION_MESSAGE


def _matches(conditions: dict, facts: dict) -> bool:
    if "zone_codes" in conditions:
        sides = [facts.get(f"{side}_zone_code") for side in conditions.get("applies_to", [])]
        if not any(code in conditions["zone_codes"] for code in sides if code):
            return False
    if "destination_prefixes" in conditions:
        destination = facts.get("destination_zone_code")
        if not destination or not any(destination.startswith(prefix) for prefix in conditions["destination_prefixes"]):
            return False
    if "time_blocks" in conditions and facts.get("time_block") not in conditions["time_blocks"]:
        return False
    if "ride_types" in conditions and facts.get("ride_type") not in conditions["ride_types"]:
        return False
    return True


def _snapshot(rule: RidesBusinessRule) -> dict:
    return {"is_active": rule.is_active, "is_hard_rule": rule.is_hard_rule, "conditions": rule.conditions}


def _revision_type(previous: dict, new: dict) -> str:
    if previous["is_active"] != new["is_active"]:
        return "enabled" if new["is_active"] else "disabled"
    if previous["is_hard_rule"] != new["is_hard_rule"]:
        return "hardened" if new["is_hard_rule"] else "softened"
    return "modified"
