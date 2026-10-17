"""Paramètres avancés de l'IA (doc 73 PARTS A–C, doc 30 §3, brief B8).

- Modèles par rôle : liste FERMÉE des 11 rôles (doc 30 §3) ; changer un modèle ajoute
  une nouvelle version dans ai_role_models (l'ancienne est désactivée). Garde-fous de
  confidentialité : local_only → fournisseur local ; direct → jamais OpenRouter (B.4).
- Seuils /200 : 4 plages continues couvrant 0..200, paramètre versionné
  `ai.routing_thresholds` (lu par le routage sur le VPS).
- Clés API : ÉCRITURE SEULE, un fichier 0600 par fournisseur dans PROVIDER_KEYS_DIR
  (dossier 0700, hors base et hors dépôt) ; l'API n'expose que présente / manquante.
"""

import os
import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.toolbox import AIRoleModel
from app.schemas.ai_advanced import (
    ApiKeyListResponse,
    ApiKeyStatus,
    CatalogResponse,
    RoleModelListResponse,
    RoleModelRead,
    RoleModelUpdate,
    ThresholdBand,
    ThresholdsRead,
    ThresholdsUpdate,
)
from app.services.params import get_parameter, set_parameter

ROLES = (
    "local_executor",
    "first_cloud_tier",
    "high_reasoning",
    "sustained_long_context",
    "health_specialist",
    "finance_specialist",
    "web_fresh_data",
    "high_reasoning_safeguard",
    "ocr_service",
    "transcription_service",
    "embedding_service",
)
LOCAL_ONLY_ROLES = frozenset({"local_executor", "ocr_service", "transcription_service", "embedding_service"})
DIRECT_ROLES = frozenset({"sustained_long_context", "health_specialist", "finance_specialist"})
KEY_PROVIDERS = ("openrouter", "openai", "anthropic", "google")
EFFORT_LEVELS = ["minimal", "low", "medium", "high", "xhigh"]
THRESHOLDS_CODE = "ai.routing_thresholds"
DEFAULT_THRESHOLDS = ThresholdsRead(
    bands=[
        ThresholdBand(label="IA locale", start=0, end=99),
        ThresholdBand(label="Premier niveau cloud", start=100, end=139),
        ThresholdBand(label="Raisonnement poussé", start=140, end=179),
        ThresholdBand(label="Mécanique critique", start=180, end=200),
    ]
)


class AdvancedNotFoundError(ValueError):
    pass


class AdvancedValidationError(ValueError):
    pass


# ---------- Modèles par rôle ----------

def list_roles(db: Session) -> RoleModelListResponse:
    return RoleModelListResponse(roles=[_role_read(role, _active_row(db, role)) for role in ROLES])


def update_role(db: Session, *, role: str, payload: RoleModelUpdate) -> RoleModelRead:
    if role not in ROLES:
        raise AdvancedNotFoundError("Unknown role: roles are fixed by doc 30 §3.")
    current = _active_row(db, role)
    route = current.sensitivity_route if current is not None else _default_route(role)
    if route == "local_only" and payload.provider != "local":
        raise AdvancedValidationError("Ce rôle reste local : seul le fournisseur local est autorisé.")
    if route != "local_only" and payload.provider == "local" and role not in LOCAL_ONLY_ROLES:
        raise AdvancedValidationError("Ce rôle est un rôle cloud : choisis un fournisseur cloud.")
    if route == "direct" and payload.provider == "openrouter":
        raise AdvancedValidationError("Ce rôle exige un accès direct (données sensibles) : OpenRouter est refusé.")
    last_version = db.scalar(
        select(AIRoleModel.version).where(AIRoleModel.role_code == role).order_by(AIRoleModel.version.desc()).limit(1)
    )
    for row in db.scalars(select(AIRoleModel).where(AIRoleModel.role_code == role, AIRoleModel.active.is_(True))):
        row.active = False
    new_row = AIRoleModel(
        role_code=role,
        provider=payload.provider,
        model_id=payload.model_id,
        effort=payload.effort,
        sensitivity_route=route,
        version=(last_version or 0) + 1,
        active=True,
    )
    db.add(new_row)
    db.commit()
    return _role_read(role, new_row)


def catalog(db: Session) -> CatalogResponse:
    providers: dict[str, set[str]] = {provider: set() for provider in ("local", *KEY_PROVIDERS)}
    for provider, model_id in db.execute(select(AIRoleModel.provider, AIRoleModel.model_id)):
        providers.setdefault(provider, set()).add(model_id)
    return CatalogResponse(
        providers={provider: sorted(models) for provider, models in providers.items()},
        effort_levels=EFFORT_LEVELS,
        remote_catalog_available=False,
        note="Catalogue distant non branché : modèles déjà utilisés + identifiant saisi à la main.",
    )


def _active_row(db: Session, role: str) -> AIRoleModel | None:
    return db.scalar(
        select(AIRoleModel)
        .where(AIRoleModel.role_code == role, AIRoleModel.active.is_(True))
        .order_by(AIRoleModel.version.desc())
        .limit(1)
    )


def _default_route(role: str) -> str:
    if role in LOCAL_ONLY_ROLES:
        return "local_only"
    if role in DIRECT_ROLES:
        return "direct"
    return "openrouter_allowed"


def _role_read(role: str, row: AIRoleModel | None) -> RoleModelRead:
    if row is None:
        return RoleModelRead(role=role, provider=None, model_id=None, effort=None, sensitivity_route=_default_route(role), version=None)
    return RoleModelRead(role=role, provider=row.provider, model_id=row.model_id, effort=row.effort,
                         sensitivity_route=row.sensitivity_route, version=row.version)


# ---------- Seuils /200 ----------

def get_thresholds(db: Session) -> ThresholdsRead:
    value = get_parameter(db, THRESHOLDS_CODE, default=None)
    if not isinstance(value, dict) or "bands" not in value:
        return DEFAULT_THRESHOLDS
    return ThresholdsRead(bands=[ThresholdBand(**band) for band in value["bands"]], version=value.get("version"))


def update_thresholds(db: Session, *, payload: ThresholdsUpdate) -> ThresholdsRead:
    bands = payload.bands
    if bands[0].start != 0 or bands[-1].end != 200:
        raise AdvancedValidationError("Les plages doivent couvrir 0 à 200.")
    for band in bands:
        if band.start > band.end:
            raise AdvancedValidationError(f"Plage « {band.label} » : le début dépasse la fin.")
    for previous, band in zip(bands, bands[1:], strict=False):
        if band.start != previous.end + 1:
            raise AdvancedValidationError(f"Trou ou chevauchement entre « {previous.label} » et « {band.label} ».")
    row = set_parameter(
        db,
        code=THRESHOLDS_CODE,
        value={"bands": [band.model_dump() for band in bands]},
        origin="user",
        rationale_fr="Seuils de score /200 modifiés dans les paramètres avancés (doc 73 PART C).",
        unit="score/200",
    )
    db.commit()
    return ThresholdsRead(bands=bands, version=row.version)


# ---------- Clés API (écriture seule) ----------

def keys_root() -> Path:
    root = Path(get_settings().provider_keys_dir)
    if not root.is_absolute():
        root = Path(__file__).resolve().parents[3] / root
    return root


def list_api_keys() -> ApiKeyListResponse:
    root = keys_root()
    return ApiKeyListResponse(
        keys=[ApiKeyStatus(provider=provider, present=_key_path(root, provider).is_file()) for provider in KEY_PROVIDERS]
    )


def replace_api_key(provider: str, key: str) -> None:
    if provider not in KEY_PROVIDERS:
        raise AdvancedNotFoundError("Unknown provider.")
    if len(key) < 20 or len(key) > 1000 or any(char.isspace() for char in key):
        raise AdvancedValidationError("Clé invalide : une seule chaîne sans espace, de 20 à 1000 caractères.")
    root = keys_root()
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    fd, tmp_name = tempfile.mkstemp(dir=root, prefix=f".{provider}.")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(key)
        os.replace(tmp_name, _key_path(root, provider))
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def delete_api_key(provider: str) -> None:
    if provider not in KEY_PROVIDERS:
        raise AdvancedNotFoundError("Unknown provider.")
    _key_path(keys_root(), provider).unlink(missing_ok=True)


def _key_path(root: Path, provider: str) -> Path:
    return root / f"{provider}.key"
