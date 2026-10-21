"""Interrupteurs des traitements IA (doc 73 §B.4bis) : quels slots sont servis, et par quel transport cloud.

Un slot `local_default` s'allume dans `ai.local_slot_modes`, un slot `cloud_forced` ou `routed` dans
`ai.cloud_slot_modes` ; le transport cloud est `ai.cloud_transport` (off | subscription ; `api` n'est pas codé).
Chaque changement est une nouvelle version du paramètre (origine `user`). Garde-fous : un slot du domaine vault
ne passe jamais au cloud ; un slot inconnu est refusé.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.toolbox import AISlotTransition
from app.schemas.ai_advanced import SlotRead, SlotsRead
from app.services.params import get_parameter, set_parameter

CLOUD_TIERS = ("cloud_forced", "routed")


class SlotSettingsError(ValueError):
    pass


def read(db: Session) -> SlotsRead:
    local = get_parameter(db, "ai.local_slot_modes", default={}) or {}
    cloud = get_parameter(db, "ai.cloud_slot_modes", default={}) or {}
    rows = db.execute(select(AISlotTransition.slot_code, AISlotTransition.domain, AISlotTransition.tier,
                             AISlotTransition.notes_fr).order_by(AISlotTransition.slot_code)).all()
    slots = []
    for code, domain, tier, note in rows:
        engine = "cloud" if tier in CLOUD_TIERS else "local"
        modes = cloud if engine == "cloud" else local
        slots.append(SlotRead(slot_code=code, domain=domain, engine=engine,
                              mode="live" if modes.get(code) == "live" else "off", note=note))
    transport = get_parameter(db, "ai.cloud_transport", default="off")
    return SlotsRead(transport=transport if transport in ("off", "subscription", "api") else "off", slots=slots)


def set_mode(db: Session, *, slot_code: str, mode: str) -> SlotsRead:
    row = db.execute(select(AISlotTransition.domain, AISlotTransition.tier)
                     .where(AISlotTransition.slot_code == slot_code)).first()
    if row is None:
        raise SlotSettingsError(f"Unknown slot '{slot_code}'.")
    engine_cloud = row.tier in CLOUD_TIERS
    if engine_cloud and row.domain == "vault" and mode == "live":
        raise SlotSettingsError("A vault slot never goes to the cloud.")
    code = "ai.cloud_slot_modes" if engine_cloud else "ai.local_slot_modes"
    current = dict(get_parameter(db, code, default={}) or {})
    wanted = {**current, slot_code: mode}
    if wanted != current:
        set_parameter(db, code=code, value=wanted, origin="user",
                      rationale_fr=f"Slot {slot_code} {'allumé' if mode == 'live' else 'éteint'} dans les paramètres avancés.")
        db.commit()
    return read(db)


def set_transport(db: Session, *, transport: str) -> SlotsRead:
    if get_parameter(db, "ai.cloud_transport", default="off") != transport:
        set_parameter(db, code="ai.cloud_transport", value=transport, origin="user",
                      rationale_fr=f"Transport cloud : {transport} (paramètres avancés).")
        db.commit()
    return read(db)
