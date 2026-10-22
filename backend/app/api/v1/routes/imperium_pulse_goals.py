"""Objectifs Pulse, écrits et classés par l'utilisateur (accueil) ; aucune IA, toujours ouverts."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Response, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.pulse_goals import GoalCreate, GoalList, GoalOrder, GoalRead, GoalUpdate
from app.services.pulse import goals

router = APIRouter()


def _call(db, action):
    try:
        return action()
    except goals.GoalNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except goals.GoalStateError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/goals", response_model=GoalList)
def list_route(current_user: CurrentUserDep, db: SessionDep):
    return goals.list_goals(db, current_user=current_user)


@router.post("/goals", response_model=GoalRead, status_code=status.HTTP_201_CREATED)
def create_route(payload: GoalCreate, response: Response, current_user: CurrentUserDep, db: SessionDep,
                 idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None):
    """Nouvel objectif, ajouté en dernier du classement."""
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    read, replayed = _call(db, lambda: goals.create(db, current_user=current_user, payload=payload,
                                                     idempotency_key=idempotency_key))
    if replayed:
        response.status_code = status.HTTP_200_OK
    return read


@router.put("/goals/order", response_model=GoalList)
def order_route(payload: GoalOrder, current_user: CurrentUserDep, db: SessionDep):
    """Classement décidé par l'utilisateur : tous les objectifs en cours, du plus au moins important."""
    return _call(db, lambda: goals.reorder(db, current_user=current_user, payload=payload))


@router.patch("/goals/{goal_id}", response_model=GoalRead)
def update_route(goal_id: UUID, payload: GoalUpdate, current_user: CurrentUserDep, db: SessionDep):
    """Modifier le titre ou la précision ; `status` achieved (atteint) ou active (remis en cours)."""
    return _call(db, lambda: goals.update(db, current_user=current_user, goal_id=goal_id, payload=payload))


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_route(goal_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    _call(db, lambda: goals.remove(db, current_user=current_user, goal_id=goal_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
