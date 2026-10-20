"""Slots IA locaux de la chaîne Pulse : interprète (§6) et choix du coup de P1 (§7 P1.3).

Assemblage en LISTE BLANCHE : seules les sources nommées dans `ALLOWED_SOURCES` entrent dans un prompt
(board figé, catalogue actif, contraintes résumées, séance résumée, menu des coups légaux) ; toute autre
source lève `AssemblerError` (jamais de données brutes de la montre, de document médical, d'historique de
conversation, ni de texte libre saisi). Entrée plafonnée (~3 000 tokens, estimés à 4 caractères par token).

Règles post-sortie (code) : interprète — procédure hors catalogue actif = invalide ; coup — hors menu
légal ou paramètres hors options = invalide. Invalide → un nouvel essai avec le rappel des erreurs ;
second échec (ou exécuteur injoignable) → le résultat dit `fallback`, l'appelant garde le déterministe.
"""

from dataclasses import dataclass, field

from app.services.ai import local_executor

ALLOWED_SOURCES = frozenset({"board", "catalogue", "constraints", "session", "menu"})
MAX_INPUT_CHARS = 12000
INTERPRETER_SLOT = "pulse.interpreter"
CHOOSE_MOVE_SLOT = "pulse.p1.choose_move"
URGENCY = ("now", "today", "this_week")
CONFIDENCE = ("high", "medium", "low")

INTERPRETER_SYSTEM = (
    "Tu es l'interprète Pulse d'un assistant personnel de santé. Tu lis un tableau de signaux et tu NOMMES "
    "les procédures du catalogue qui méritent d'être lancées ; tu ne les exécutes pas. N'utilise que les codes "
    "du catalogue. Si rien ne le justifie, none_needed=true et aucune procédure. Mets escalate=true si un "
    "signal te semble relever d'un avis médical. Réponds uniquement selon le schéma JSON."
)
CHOOSE_MOVE_SYSTEM = (
    "Tu choisis UN coup dans le menu des coups légaux pour adapter une séance d'entraînement à l'état du "
    "jour. Tu ne peux choisir qu'un coup du menu et des paramètres parmi ses options. Justifie en une phrase "
    "courte en français. Réponds uniquement selon le schéma JSON."
)


class AssemblerError(ValueError):
    pass


@dataclass
class SlotOutcome:
    mode: str
    output: dict | None = None
    valid: bool = False
    fallback: bool = False
    attempts: int = 0
    errors: list = field(default_factory=list)
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int = 0

    def record(self) -> dict:
        """Trace stockée à côté du résultat (jamais le prompt)."""
        return {"mode": self.mode, "output": self.output, "valid": self.valid, "fallback": self.fallback,
                "attempts": self.attempts, "errors": self.errors, "prompt_tokens": self.prompt_tokens,
                "output_tokens": self.output_tokens, "latency_ms": self.latency_ms}


def assemble(**sources) -> str:
    """Prompt utilisateur depuis des sources de la liste blanche ; tronqué au plafond d'entrée."""
    unknown = set(sources) - ALLOWED_SOURCES
    if unknown:
        raise AssemblerError(f"Source not allowed in a prompt: {sorted(unknown)}")
    blocks = [f"## {name}\n{text}" for name, text in sources.items() if text]
    prompt = "\n\n".join(blocks)
    return prompt[:MAX_INPUT_CHARS]


def board_lines(board: dict) -> str:
    """Une ligne par signal non vert ou informatif : `code=valeur (bande, âge min)`."""
    lines = []
    for signal in board.get("signals", []):
        if signal.get("state") != "fresh":
            continue
        if signal.get("band") == "green":
            continue
        lines.append(f"{signal['code']}={signal.get('value')} ({signal.get('band') or 'info'}, "
                     f"{signal.get('age_min')} min)")
    return "\n".join(lines) or "aucun signal frais hors vert"


def interpreter_schema(catalogue: list[str]) -> dict:
    procedures = ({"type": "array", "maxItems": 0} if not catalogue else {
        "type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["code", "urgency"],
                                   "properties": {"code": {"enum": catalogue}, "urgency": {"enum": list(URGENCY)}}}})
    return {"type": "object", "additionalProperties": False,
            "required": ["procedures", "signals_used", "confidence", "escalate", "none_needed", "rationale_fr"],
            "properties": {"procedures": procedures, "signals_used": {"type": "array", "items": {"type": "string"}},
                           "confidence": {"enum": list(CONFIDENCE)}, "escalate": {"type": "boolean"},
                           "none_needed": {"type": "boolean"}, "rationale_fr": {"type": "string", "maxLength": 400}}}


def move_schema(legal: list[str]) -> dict:
    nullable_move = {"anyOf": [{"enum": legal}, {"type": "null"}]}
    return {"type": "object", "additionalProperties": False,
            "required": ["move_code", "parameters", "fallback_move_code", "condition_fr", "rationale_fr", "confidence"],
            "properties": {
                "move_code": {"enum": legal},
                "parameters": {"type": "object", "additionalProperties": False, "properties": {
                    "new_time": {"type": "string"}, "target_date": {"type": "string"}, "percent": {"type": "integer"},
                    "new_session_type": {"type": "string"}, "debt_id": {"type": "string"}}},
                "fallback_move_code": nullable_move,
                "condition_fr": {"anyOf": [{"type": "string", "maxLength": 200}, {"type": "null"}]},
                "rationale_fr": {"type": "string", "maxLength": 300},
                "confidence": {"enum": list(CONFIDENCE)}}}


def run_slot(*, slot_code: str, mode: str, system: str, user: str, schema: dict, validate, related_id=None
             ) -> SlotOutcome:
    """Un appel, un nouvel essai si la sortie est invalide, puis repli. Ne lève jamais."""
    outcome = SlotOutcome(mode=mode)
    prompt = user
    for _ in range(2):
        outcome.attempts += 1
        try:
            result = local_executor.structured(slot_code=slot_code, app_name="pulse", system=system, user=prompt,
                                               schema=schema, related_entity_type="pulse_slot",
                                               related_entity_id=related_id)
        except local_executor.LocalExecutorError as exc:
            outcome.errors.append(f"executor:{str(exc)[:120]}")
            break
        outcome.output = result.output
        outcome.prompt_tokens = (outcome.prompt_tokens or 0) + (result.prompt_tokens or 0)
        outcome.output_tokens = (outcome.output_tokens or 0) + (result.output_tokens or 0)
        outcome.latency_ms += result.latency_ms
        errors = validate(result.output)
        if not errors:
            outcome.valid = True
            return outcome
        outcome.errors.extend(errors)
        prompt = f"{user}\n\n## rappel\nTa sortie précédente était invalide : {', '.join(errors)}. " \
                 "Respecte le schéma, le catalogue et les options."
    outcome.fallback = True
    return outcome
