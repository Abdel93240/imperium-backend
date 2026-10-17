"""Stock alimentaire de Pulse (doc 40 §11) : lecture, ajout et modification manuels (PUL-12),
alertes de date limite, scan du placard (PUL-13), ajout par le chatbot."""

import io
from typing import Annotated
from urllib.parse import unquote
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.pulse import (
    FoodStockExpiryAlertRead,
    FoodStockExpiryRead,
    FoodStockItemCreate,
    FoodStockItemRead,
    FoodStockItemUpdate,
    FoodStockListResponse,
    PantryScanRead,
    PantryScanValidateRequest,
    StockDeclarationCreate,
    StockDeclarationPreviewRead,
    StockDeclarationPreviewRequest,
    StockDeclarationRead,
)
from app.services.pulse import expiry, food_stock, pantry_scan, stock_declaration

router = APIRouter()


def _require_key(idempotency_key: str | None) -> str:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    return idempotency_key


@router.get("/food-stock", response_model=FoodStockListResponse)
def list_food_stock_route(
    current_user: CurrentUserDep, db: SessionDep, include_inactive: bool = False
) -> FoodStockListResponse:
    """Stock actif, date limite la plus proche en premier."""
    return food_stock.list_stock(db, current_user=current_user, include_inactive=include_inactive)


@router.get("/food-stock/alerts", response_model=FoodStockExpiryRead)
def food_stock_alerts_route(current_user: CurrentUserDep, db: SessionDep) -> FoodStockExpiryRead:
    """Dates limites proches ou dépassées, calculées en direct (jour de Paris)."""
    report = expiry.compute_alerts(db, current_user=current_user)
    return FoodStockExpiryRead(
        today=report.today, level=report.level, to_consume=report.to_consume, message_fr=report.message_fr,
        alerts=[FoodStockExpiryAlertRead(**alert.__dict__) for alert in report.alerts],
    )


@router.post("/food-stock", response_model=FoodStockItemRead, status_code=status.HTTP_201_CREATED)
def create_food_stock_route(
    payload: FoodStockItemCreate,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> FoodStockItemRead:
    try:
        item, duplicate = food_stock.create_item(
            db, current_user=current_user, payload=payload, idempotency_key=_require_key(idempotency_key),
            request_path=request.url.path,
        )
    except food_stock.FoodStockIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return item


@router.patch("/food-stock/{item_id}", response_model=FoodStockItemRead)
def update_food_stock_route(
    item_id: UUID,
    payload: FoodStockItemUpdate,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Version dépassée → 409 avec la ligne actuelle (dialogue de conflit de PUL-12)."""
    try:
        return food_stock.update_item(
            db, current_user=current_user, item_id=item_id, payload=payload,
            idempotency_key=_require_key(idempotency_key), request_path=request.url.path,
        )
    except food_stock.FoodStockNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except food_stock.FoodStockVersionConflictError as exc:
        db.rollback()
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc), "code": "STOCK_VERSION_CONFLICT", "current": exc.current.model_dump(mode="json")},
        )
    except food_stock.FoodStockIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/food-stock/declarations/preview", response_model=StockDeclarationPreviewRead)
def preview_stock_declaration_route(
    payload: StockDeclarationPreviewRequest, current_user: CurrentUserDep, db: SessionDep
) -> StockDeclarationPreviewRead:
    """Phrase du chatbot → proposition de lignes ; rien n'est écrit."""
    return stock_declaration.preview(db, current_user=current_user, text=payload.text, today=expiry.paris_today())


@router.post("/food-stock/declarations", response_model=StockDeclarationRead, status_code=status.HTTP_201_CREATED)
def create_stock_declaration_route(
    payload: StockDeclarationCreate,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> StockDeclarationRead:
    """Lignes validées dans le chatbot → stock (source chatbot), une ligne par achat."""
    try:
        read, duplicate = stock_declaration.create_declaration(
            db, current_user=current_user, payload=payload, idempotency_key=_require_key(idempotency_key),
            request_path=request.url.path,
        )
    except food_stock.FoodStockIdempotencyConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.post("/food-stock/scans", response_model=PantryScanRead, status_code=status.HTTP_201_CREATED)
async def create_pantry_scan_route(
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    x_filename: Annotated[str, Header(alias="X-Filename")],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    content_length: Annotated[int | None, Header(alias="Content-Length")] = None,
) -> PantryScanRead:
    """Photo du placard en corps brut ; renvoie la proposition comparée au stock (photo non conservée)."""
    key = _require_key(idempotency_key)
    if content_length is not None and content_length > pantry_scan.MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Fichier refusé : 25 Mo maximum.")
    buffer = bytearray()
    async for chunk in request.stream():
        buffer.extend(chunk)
        if len(buffer) > pantry_scan.MAX_BYTES:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Fichier refusé : 25 Mo maximum.")
    try:
        # L'analyse peut prendre jusqu'à 60 s : hors de la boucle d'événements.
        scan, duplicate = await run_in_threadpool(
            pantry_scan.create_scan, db, current_user=current_user, filename=unquote(x_filename),
            content_type=request.headers.get("content-type"), stream=io.BytesIO(bytes(buffer)), idempotency_key=key,
        )
    except pantry_scan.PantryScanFileError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return scan


@router.get("/food-stock/scans/{scan_id}", response_model=PantryScanRead)
def get_pantry_scan_route(scan_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> PantryScanRead:
    try:
        return pantry_scan.get_scan(db, current_user=current_user, scan_id=scan_id)
    except pantry_scan.PantryScanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/food-stock/scans/{scan_id}/validate", response_model=PantryScanRead)
def validate_pantry_scan_route(
    scan_id: UUID,
    payload: PantryScanValidateRequest,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Lignes gardées seulement ; une ligne de stock modifiée entre-temps → 409 avec la ligne actuelle."""
    _require_key(idempotency_key)
    try:
        return pantry_scan.validate_scan(db, current_user=current_user, scan_id=scan_id, payload=payload)
    except pantry_scan.PantryScanNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except pantry_scan.PantryScanStateError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except pantry_scan.PantryScanVersionConflictError as exc:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc), "code": "STOCK_VERSION_CONFLICT", "current": exc.current.model_dump(mode="json")},
        )


@router.post("/food-stock/scans/{scan_id}/cancel", response_model=PantryScanRead)
def cancel_pantry_scan_route(scan_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> PantryScanRead:
    try:
        return pantry_scan.cancel_scan(db, current_user=current_user, scan_id=scan_id)
    except pantry_scan.PantryScanNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except pantry_scan.PantryScanStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
