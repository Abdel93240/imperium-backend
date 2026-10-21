"""Routes des paramètres avancés de l'IA (doc 73, brief B8).

Aucune route ne lit une clé API : statut seulement, remplacement en écriture seule.
"""

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.ai_advanced import (
    ApiKeyListResponse,
    ApiKeyReplace,
    CatalogResponse,
    RoleModelListResponse,
    RoleModelRead,
    RoleModelUpdate,
    SlotsRead,
    SlotUpdate,
    ThresholdsRead,
    ThresholdsUpdate,
    TransportUpdate,
)
from app.services.ai import advanced, slot_settings

router = APIRouter()


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, advanced.AdvancedNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


_ERRORS = (advanced.AdvancedNotFoundError, advanced.AdvancedValidationError)


@router.get("/roles", response_model=RoleModelListResponse)
def list_roles_route(current_user: CurrentUserDep, db: SessionDep) -> RoleModelListResponse:
    return advanced.list_roles(db)


@router.put("/roles/{role}", response_model=RoleModelRead)
def update_role_route(role: str, payload: RoleModelUpdate, current_user: CurrentUserDep, db: SessionDep) -> RoleModelRead:
    try:
        return advanced.update_role(db, role=role, payload=payload)
    except _ERRORS as exc:
        db.rollback()
        raise _http(exc) from exc


@router.get("/catalog", response_model=CatalogResponse)
def catalog_route(current_user: CurrentUserDep, db: SessionDep) -> CatalogResponse:
    return advanced.catalog(db)


@router.get("/thresholds", response_model=ThresholdsRead)
def get_thresholds_route(current_user: CurrentUserDep, db: SessionDep) -> ThresholdsRead:
    return advanced.get_thresholds(db)


@router.put("/thresholds", response_model=ThresholdsRead)
def update_thresholds_route(payload: ThresholdsUpdate, current_user: CurrentUserDep, db: SessionDep) -> ThresholdsRead:
    try:
        return advanced.update_thresholds(db, payload=payload)
    except _ERRORS as exc:
        db.rollback()
        raise _http(exc) from exc


@router.get("/api-keys", response_model=ApiKeyListResponse)
def list_api_keys_route(current_user: CurrentUserDep) -> ApiKeyListResponse:
    return advanced.list_api_keys()


@router.put("/api-keys/{provider}", status_code=status.HTTP_204_NO_CONTENT)
def replace_api_key_route(provider: str, payload: ApiKeyReplace, current_user: CurrentUserDep) -> Response:
    try:
        advanced.replace_api_key(provider, payload.key)
    except _ERRORS as exc:
        raise _http(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/api-keys/{provider}", status_code=status.HTTP_204_NO_CONTENT)
def delete_api_key_route(provider: str, current_user: CurrentUserDep) -> Response:
    try:
        advanced.delete_api_key(provider)
    except _ERRORS as exc:
        raise _http(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Traitements IA (slots) et transport cloud ----------

@router.get("/slots", response_model=SlotsRead)
def list_slots_route(current_user: CurrentUserDep, db: SessionDep) -> SlotsRead:
    return slot_settings.read(db)


@router.put("/slots/{slot_code}", response_model=SlotsRead)
def update_slot_route(slot_code: str, payload: SlotUpdate, current_user: CurrentUserDep, db: SessionDep) -> SlotsRead:
    try:
        return slot_settings.set_mode(db, slot_code=slot_code, mode=payload.mode)
    except slot_settings.SlotSettingsError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.put("/transport", response_model=SlotsRead)
def update_transport_route(payload: TransportUpdate, current_user: CurrentUserDep, db: SessionDep) -> SlotsRead:
    return slot_settings.set_transport(db, transport=payload.transport)
