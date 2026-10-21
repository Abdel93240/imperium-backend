"""Escalade invisible (doc 72 §3, doc 30 §5) : le modèle local note sa propre capacité, le code décide.

À chaque message, le conducteur local (chatbot, Weekly Review) rend avec sa réponse une auto-évaluation : les
7 critères de doc 30 §5.2 (0-10), sa confiance (0-1), le domaine, et — s'il pense avoir besoin d'aide — une
question pour l'expert, générique et anonyme (aucun nom, lieu, date précise, identifiant ; « un homme de
35 ans qui… »). Le CODE calcule le score /200 (§5.3), lit la plage (`ai.routing_thresholds`, §5.6), applique
les règles d'escalade automatique (§5.8) et choisit le rôle. Tant que le slot cloud `nexus.escalation` est
éteint, la décision est seulement journalisée (mode ombre, pour calibrer). Allumé : le rôle choisi répond à la
question anonyme, en français, au nom de Nexus ; l'utilisateur ne change jamais d'interlocuteur. En échec
(quota, panne), la réponse locale reste.

Urgence vitale (règle fixe, au-dessus du score, doc 30 §7) : le score /200 mesure la DIFFICULTÉ ; une urgence
vitale est simple mais grave, elle sortait autour de 80 (urgente, donc « rapide »). Quand le modèle local la
signale (`vital_emergency`), le code la porte au palier critique (score ≥ 180, raisonnement poussé, jamais le
seul spécialiste de domaine), et la réponse commence par une ligne écrite par le CODE (`EMERGENCY_LINE`), qui ne
dépend d'aucun modèle. La question de l'expert est écrite à la première personne : l'expert répond à la personne
concernée elle-même, jamais comme à un témoin.

Pas encore : la vérification indépendante d'un score ≥ 180 (§5.6 étape 1, rôle `high_reasoning_safeguard`) ;
un tel score va au raisonnement poussé et le note. Le domaine finances détaillé (Vault) ne part jamais : la
question est générique, et le slot refuse le domaine vault.
"""

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.services.ai import cloud
from app.services.ai.advanced import get_thresholds

SLOT = "nexus.escalation"
CRITERIA = {"complexity": 5, "context_size": 3, "ambiguity": 3, "consequences": 2, "speed_tolerance": 2,
            "sensitivity": 3, "cost_justification": 2}
TIERS = ("local_executor", "first_cloud_tier", "high_reasoning")
SPECIALISTS = {"health": "health_specialist", "finance": "finance_specialist"}
# doc 30 §5.8 : argent, santé, droit → escalade même à score bas, dès que le modèle a une question pour l'expert.
SENSITIVE_DOMAINS = frozenset({"health", "finance", "legal"})
DOMAINS = ("general", "planning", "health", "finance", "religion", "business", "legal", "tech")
LOW_CONFIDENCE = 0.65
EMERGENCY_FLOOR = 180
EMERGENCY_LINE = ("Si c'est en train de t'arriver : appelle le 15 (SAMU) ou le 112 maintenant, ne conduis pas, "
                  "installe-toi assis ou allongé et laisse ta porte ouverte.")
# Anonymisation de dernier recours : adresses, numéros longs (téléphone, compte), liens.
_SCRUB = (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), re.compile(r"\+?\d[\d .-]{6,}\d"), re.compile(r"https?://\S+"))

SELF_ASSESSMENT_RULES = (
    "Auto-évaluation (« assessment ») : avant de répondre, note ta propre capacité à bien traiter ce message, "
    "chaque critère de 0 à 10 : complexity (0 trivial, 10 très complexe), context_size (contexte nécessaire), "
    "ambiguity (0 clair, 10 flou), consequences (gravité d'une erreur), speed_tolerance (0 urgent, 10 peut "
    "attendre), sensitivity (données sensibles), cost_justification (une réponse plus solide vaut-elle un coût). "
    "confidence : ta confiance (0 à 1) dans ta propre réponse. domain : le domaine du message. Si un modèle plus "
    "fort ferait nettement mieux (savoir spécialisé, calcul, raisonnement long, santé, argent, droit), écris "
    "expert_question : la question à lui poser, complète et compréhensible seule, à la PREMIÈRE PERSONNE, comme "
    "si l'utilisateur la posait lui-même (« J'ai 35 ans, je ressens… que dois-je faire ? »), et ANONYME (aucun "
    "nom, lieu, date précise, montant exact ni identifiant) ; sinon null. vital_emergency : true seulement si sa "
    "vie ou sa santé peut être en danger MAINTENANT (douleur ou oppression thoracique, palpitations avec malaise, "
    "membre qui ne répond plus, difficulté à respirer, perte de connaissance, idées suicidaires, accident en "
    "cours…) : consequences et sensitivity valent alors 10. Si tu ne "
    "peux pas répondre toi-même de façon fiable, ne refuse pas : ta confidence est basse (0,5 au plus), tu "
    "écris expert_question, et reply_fr dit simplement que tu regardes. Ne surévalue pas pour autant : la "
    "plupart des messages se traitent seul.")


@dataclass
class Decision:
    score: int
    role: str
    reasons: list[str] = field(default_factory=list)
    breakdown: dict = field(default_factory=dict)
    confidence: float = 1.0
    domain: str | None = None
    emergency: bool = False

    @property
    def escalates(self) -> bool:
        return self.role != "local_executor"

    def log(self) -> dict:
        return {"score": self.score, "role": self.role, "reasons": self.reasons, "breakdown": self.breakdown,
                "confidence": self.confidence, "domain": self.domain, "vital_emergency": self.emergency}


def assessment_schema() -> dict:
    """Bloc à ajouter à la sortie du conducteur local."""
    note = {"type": "integer", "minimum": 0, "maximum": 10}
    return {"type": "object", "additionalProperties": False,
            "required": ["vital_emergency", *CRITERIA, "confidence", "domain", "expert_question"],
            "properties": {"vital_emergency": {"type": "boolean"}, **{name: note for name in CRITERIA},
                           "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                           "domain": {"type": "string", "enum": list(DOMAINS)},
                           "expert_question": {"type": ["string", "null"], "maxLength": 1500}}}


def score(breakdown: dict) -> int:
    """Formule de doc 30 §5.3 : somme des critères (0-10) × coefficients, 0 à 200."""
    return sum(max(0, min(10, int(breakdown.get(name) or 0))) * weight for name, weight in CRITERIA.items())


def decide(db: Session, assessment: dict | None) -> Decision:
    """Rôle recommandé (doc 30 §5.6, §5.8). Sans auto-évaluation : local."""
    if not assessment:
        return Decision(score=0, role="local_executor", reasons=["no_assessment"])
    breakdown = {name: max(0, min(10, int(assessment.get(name) or 0))) for name in CRITERIA}
    confidence = max(0.0, min(1.0, float(assessment.get("confidence") if assessment.get("confidence") is not None else 1)))
    domain = assessment.get("domain")
    total = score(breakdown)
    bands = get_thresholds(db).bands
    band = next((i for i, b in enumerate(bands) if b.start <= total <= b.end), len(bands) - 1)
    tier = min(band, len(TIERS) - 1)
    reasons = [f"band:{bands[band].label}"]
    if band >= 3:
        reasons.append("critical_recheck_not_wired")
    if confidence < LOW_CONFIDENCE:
        tier = min(tier + 1, len(TIERS) - 1)
        reasons.append("low_confidence")
    if breakdown["consequences"] >= 8 and breakdown["ambiguity"] >= 7 and tier < 1:
        tier = 1
        reasons.append("consequences_and_ambiguity")
    if domain in SENSITIVE_DOMAINS and assessment.get("expert_question") and tier < 1:
        tier = 1
        reasons.append("sensitive_domain")
    role = TIERS[tier]
    if breakdown["consequences"] >= 9 and breakdown["sensitivity"] >= 8:
        role = SPECIALISTS.get(domain, "high_reasoning")
        reasons.append("grave_and_sensitive")
    elif role != "local_executor" and domain in SPECIALISTS:
        role = SPECIALISTS[domain]
        reasons.append("domain_specialist")
    emergency = bool(assessment.get("vital_emergency"))
    if emergency:  # règle fixe : la gravité prime sur la difficulté
        total, role = max(total, EMERGENCY_FLOOR), "high_reasoning"
        reasons.append("vital_emergency")
    return Decision(score=total, role=role, reasons=reasons, breakdown=breakdown, confidence=confidence, emergency=emergency,
                    domain=domain)


def live(db: Session) -> bool:
    return cloud.slot_mode(db, SLOT) == "live"


def scrub(text: str) -> str:
    for pattern in _SCRUB:
        text = pattern.sub("[…]", text)
    return text


def ask_expert(db: Session, decision: Decision, question: str, *, app_name: str = "imperium",
               related_entity_type: str | None = None, related_entity_id=None) -> cloud.CloudResult:
    """La question anonyme au rôle choisi ; réponse prête à être dite par Nexus. Lève cloud.CloudError."""
    system = ("Tu réponds à la place de Nexus, l'assistant personnel d'un utilisateur, qui te transmet la question "
              "anonymisée de l'utilisateur. La question vient de la personne concernée elle-même : réponds-LUI "
              "directement, jamais comme à un témoin ou à un proche. Réponds en français, en tutoyant, clairement et "
              "brièvement (dix phrases au plus), comme Nexus lui-même : ne dis jamais que tu es un autre modèle. Sois "
              "concret ; si une information manque, dis ce qu'il faudrait savoir. Santé : rappelle de consulter un "
              "professionnel quand c'est nécessaire.")
    if decision.emergency:
        system += (" URGENCE VITALE POSSIBLE : la personne est peut-être seule. Commence par ce qu'elle doit faire "
                   "elle-même tout de suite (appeler le 15 ou le 112, ne pas conduire, s'asseoir ou s'allonger, "
                   "déverrouiller sa porte), puis ce qu'il faut dire aux secours. Une ligne d'appel aux secours est "
                   "déjà affichée avant ta réponse : ne la répète pas mot pour mot.")
    schema = {"type": "object", "additionalProperties": False, "required": ["answer_fr"],
              "properties": {"answer_fr": {"type": "string", "maxLength": 4000}}}
    return cloud.structured(db, slot_code=SLOT, app_name=app_name, system=system, user=scrub(question)[:1500],
                            schema=schema, related_entity_type=related_entity_type,
                            related_entity_id=related_entity_id, role_code=decision.role)
