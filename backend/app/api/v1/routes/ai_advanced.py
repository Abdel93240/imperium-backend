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
    ThresholdsRead,
    ThresholdsUpdate,
)
from app.services.ai import advanced

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
