"""Catégorie suggérée d'une transaction (doc 42 §7.0–§7.2).

Module séparé des routes du registre Vault : celles-ci restent sans IA ni mémoire
(invariants patch 9B–9D) ; la suggestion peut, elle, appeler le modèle local (§7.1).
"""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.vault import (
    VaultCategoryConfirmRequest,
    VaultCategoryConfirmResponse,
    VaultCategoryListResponse,
    VaultCategoryRead,
    VaultCategorySuggestionRead,
    VaultCategorySuggestRequest,
)
from app.services.vault import categorization

router = APIRouter()


@router.get("/categories", response_model=VaultCategoryListResponse)
def vault_categories_route(current_user: CurrentUserDep, db: SessionDep) -> VaultCategoryListResponse:
    """Référentiel des catégories ; le livre business/perso en est déduit."""
    referential = categorization.get_referential(db)
    return VaultCategoryListResponse(
        categories=[VaultCategoryRead(category=name, book=book, kind=kind) for name, (book, kind) in sorted(referential.items())]
    )


@router.post("/categories/suggest", response_model=VaultCategorySuggestionRead)
def suggest_vault_category_route(
    payload: VaultCategorySuggestRequest, current_user: CurrentUserDep, db: SessionDep
) -> VaultCategorySuggestionRead:
    """Préremplissage du champ Catégorie : part utilisateur, table en dur, puis modèle local."""
    suggestion = categorization.suggest_category(
        db,
        current_user=current_user,
        label=payload.label,
        amount_cents=payload.amount_cents,
        transaction_type=payload.transaction_type,
    )
    return VaultCategorySuggestionRead(**suggestion.__dict__)


@router.post("/categories/confirm", response_model=VaultCategoryConfirmResponse)
def confirm_vault_category_route(
    payload: VaultCategoryConfirmRequest, current_user: CurrentUserDep, db: SessionDep
) -> VaultCategoryConfirmResponse:
    """Catégorie validée pour un libellé : elle rejoint la part utilisateur de la table."""
    try:
        entry = categorization.confirm_category(db, current_user=current_user, label=payload.label, category=payload.category)
    except categorization.CategoryValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    book = categorization.get_referential(db)[entry.category][0]
    return VaultCategoryConfirmResponse(label_key=entry.label_key, category=entry.category, book=book, confirmations=entry.confirmations)
