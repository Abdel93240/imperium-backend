"""Diète Pulse (doc 40 §10.4–§10.9) : recettes, semaine, préparations, courses. Fermé tant que `pulse.diet_enabled`."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.pulse_diet import (
    PlanRead,
    PulseAttentionRead,
    PlanRequest,
    PreparationComplete,
    PreparationDetailRead,
    PreparationRead,
    RecipeCreate,
    RecipeListRead,
    RecipeRead,
    ShoppingItemRead,
    ShoppingItemUpdate,
    ShoppingListRead,
    WeekRead,
)
from app.services.pulse import diet
from app.services.pulse.expiry import paris_today

router = APIRouter()


def _disabled() -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                        content={"detail": "Disabled.", "code": "PULSE_DIET_DISABLED"})


def _key(value: str | None) -> str:
    if not value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    return value


def _call(db, action):
    """Exécute l'action ; traduit les erreurs du service en réponses HTTP."""
    try:
        return action()
    except diet.DietNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except diet.IngredientsMissingError as exc:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={
            "detail": str(exc), "code": "INGREDIENTS_MISSING",
            "missing": [line.model_dump(mode="json") for line in exc.missing]})
    except (diet.DietStateError, diet.DietIdempotencyConflictError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


Key = Annotated[str | None, Header(alias="Idempotency-Key")]


@router.get("/diet/week", response_model=WeekRead)
def week_route(current_user: CurrentUserDep, db: SessionDep, day: date | None = Query(default=None)):
    """Semaine du jour donné (aujourd'hui par défaut) : plan validé, demande en cours, courses ouvertes."""
    if not diet.enabled(db):
        return _disabled()
    return diet.week(db, current_user=current_user, day=day or paris_today())


@router.get("/diet/attention", response_model=list[PulseAttentionRead])
def attention_route(current_user: CurrentUserDep, db: SessionDep):
    """Attention requise, lue par Imperium : préparations bloquées par un manque ; vide si la diète est éteinte."""
    return diet.attention(db, current_user=current_user) if diet.enabled(db) else []


@router.post("/diet/plans", response_model=PlanRead, status_code=status.HTTP_202_ACCEPTED)
def request_plan_route(payload: PlanRequest, response: Response, current_user: CurrentUserDep, db: SessionDep,
                       idempotency_key: Key = None):
    """Demande la semaine au cerveau ; la proposition arrive ensuite (statut `generating` → `proposed`)."""
    if not diet.enabled(db):
        return _disabled()
    read, replayed = _call(db, lambda: diet.request_plan(db, current_user=current_user, payload=payload,
                                                           idempotency_key=_key(idempotency_key)))
    if replayed:
        response.status_code = status.HTTP_200_OK
    return read


@router.get("/diet/plans/{plan_id}", response_model=PlanRead)
def plan_route(plan_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    if not diet.enabled(db):
        return _disabled()
    return _call(db, lambda: diet.get_plan(db, current_user=current_user, plan_id=plan_id))


@router.post("/diet/plans/{plan_id}/activate", response_model=PlanRead)
def activate_route(plan_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    """Validation : le plan devient la semaine, les courses sont calculées."""
    if not diet.enabled(db):
        return _disabled()
    return _call(db, lambda: diet.activate_plan(db, current_user=current_user, plan_id=plan_id))


@router.post("/diet/plans/{plan_id}/reject", response_model=PlanRead)
def reject_route(plan_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    if not diet.enabled(db):
        return _disabled()
    return _call(db, lambda: diet.reject_plan(db, current_user=current_user, plan_id=plan_id))


@router.get("/recipes", response_model=RecipeListRead)
def recipes_route(current_user: CurrentUserDep, db: SessionDep):
    if not diet.enabled(db):
        return _disabled()
    return diet.list_recipes(db, current_user=current_user)


@router.post("/recipes", response_model=RecipeRead, status_code=status.HTTP_201_CREATED)
def create_recipe_route(payload: RecipeCreate, response: Response, current_user: CurrentUserDep, db: SessionDep,
                        idempotency_key: Key = None):
    if not diet.enabled(db):
        return _disabled()
    read, replayed = _call(db, lambda: diet.create_recipe(db, current_user=current_user, payload=payload,
                                                            idempotency_key=_key(idempotency_key)))
    if replayed:
        response.status_code = status.HTTP_200_OK
    return read


@router.get("/recipes/{recipe_id}", response_model=RecipeRead)
def recipe_route(recipe_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    if not diet.enabled(db):
        return _disabled()
    return _call(db, lambda: diet.get_recipe(db, current_user=current_user, recipe_id=recipe_id))


@router.delete("/recipes/{recipe_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_recipe_route(recipe_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    if not diet.enabled(db):
        return _disabled()
    _call(db, lambda: diet.archive_recipe(db, current_user=current_user, recipe_id=recipe_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/preparations/{preparation_id}", response_model=PreparationDetailRead)
def preparation_route(preparation_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    """P05 : recette, étapes, conditionnement et conservation, ingrédients comparés au stock."""
    if not diet.enabled(db):
        return _disabled()
    return _call(db, lambda: diet.get_preparation(db, current_user=current_user, preparation_id=preparation_id))


@router.post("/preparations/{preparation_id}/start", response_model=PreparationRead)
def start_route(preparation_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    """Vérifie le stock ; il manque un ingrédient → 409 INGREDIENTS_MISSING (attention requise dans Imperium)."""
    if not diet.enabled(db):
        return _disabled()
    return _call(db, lambda: diet.start_preparation(db, current_user=current_user, preparation_id=preparation_id))


@router.post("/preparations/{preparation_id}/complete", response_model=PreparationRead)
def complete_route(preparation_id: UUID, payload: PreparationComplete, current_user: CurrentUserDep,
                   db: SessionDep, idempotency_key: Key = None):
    """P06 : consomme les ingrédients et crée les portions, en une fois."""
    if not diet.enabled(db):
        return _disabled()
    return _call(db, lambda: diet.complete_preparation(db, current_user=current_user, preparation_id=preparation_id,
                                                       payload=payload, idempotency_key=_key(idempotency_key)))


@router.post("/preparations/{preparation_id}/cancel", response_model=PreparationRead)
def cancel_route(preparation_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    if not diet.enabled(db):
        return _disabled()
    return _call(db, lambda: diet.cancel_preparation(db, current_user=current_user, preparation_id=preparation_id))


@router.get("/shopping-list", response_model=ShoppingListRead)
def shopping_route(current_user: CurrentUserDep, db: SessionDep):
    """P08 : ce qui manque encore ; une ligne couverte par le stock disparaît."""
    if not diet.enabled(db):
        return _disabled()
    return diet.shopping_list(db, current_user=current_user)


@router.patch("/shopping-list/{item_id}", response_model=ShoppingItemRead)
def check_route(item_id: UUID, payload: ShoppingItemUpdate, current_user: CurrentUserDep, db: SessionDep):
    """Cocher (ne crédite jamais le stock)."""
    if not diet.enabled(db):
        return _disabled()
    return _call(db, lambda: diet.check_item(db, current_user=current_user, item_id=item_id, checked=payload.checked))


@router.delete("/shopping-list/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_route(item_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    if not diet.enabled(db):
        return _disabled()
    _call(db, lambda: diet.remove_item(db, current_user=current_user, item_id=item_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
