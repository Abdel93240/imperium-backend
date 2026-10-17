"""Matériel possédé Pulse (doc 40 §13-EQUIP) : réglage « mettre à jour mon matériel »."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.pulse_workouts import EquipmentCreate, EquipmentListResponse, EquipmentRead
from app.services.pulse import equipment

router = APIRouter()


@router.get("/equipment", response_model=EquipmentListResponse)
def list_equipment_route(current_user: CurrentUserDep, db: SessionDep) -> EquipmentListResponse:
    """Matériel actif, par ordre alphabétique."""
    return equipment.list_equipment(db, current_user=current_user)


@router.post("/equipment", response_model=EquipmentRead, status_code=status.HTTP_201_CREATED)
def add_equipment_route(
    payload: EquipmentCreate, response: Response, current_user: CurrentUserDep, db: SessionDep
) -> EquipmentRead:
    """Naturellement idempotent : un nom déjà présent renvoie la ligne existante (200)."""
    read, existing = equipment.add_equipment(db, current_user=current_user, payload=payload)
    if existing:
        response.status_code = status.HTTP_200_OK
    return read


@router.delete("/equipment/{equipment_id}", response_model=EquipmentRead)
def remove_equipment_route(equipment_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> EquipmentRead:
    """Retrait sans suppression (status removed) ; déjà retiré → même réponse."""
    try:
        return equipment.remove_equipment(db, current_user=current_user, equipment_id=equipment_id)
    except equipment.EquipmentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
