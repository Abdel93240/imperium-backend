"""Vector : sessions VTC et « Où aller ? » (doc 59 §14 ; doc 13, doc 33 §5) — conseil et mesure, jamais d'action sur l'appli VTC."""

from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.rides import (
    BusinessRuleListResponse,
    BusinessRuleRead,
    BusinessRuleUpdate,
    WeatherFeedRead,
    CurrentSessionRead,
    DropZoneCreate,
    DropZoneRead,
    ManualExpenseCreate,
    ManualRevenueCreate,
    RecommendationFeedback,
    RecommendationRead,
    RecommendationRequest,
    RideDecisionRequest,
    RideOfferCreate,
    RideOfferListResponse,
    RideOfferRead,
    RideOutcomeRequest,
    SessionComplete,
    SessionEntryResult,
    SessionListResponse,
    SessionRead,
    SessionReplanResponse,
    SessionStart,
    SessionUpdate,
    TrainingSummaryRead,
)
from app.services.imperium import replan, vault_transactions
from app.services.path.fasting import paris_today
from app.services.pulse import food_stock
from app.services.vector import offers, recommendations, rules, sessions, weather

router = APIRouter()


def _require_key(idempotency_key: str | None) -> str:
    if not idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Idempotency-Key header.")
    return idempotency_key


def _error(db: SessionDep, exc: Exception) -> JSONResponse:
    db.rollback()
    if isinstance(exc, sessions.RidesStateError):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={
            "detail": str(exc), "code": "RIDES_SESSION_STATE", "current": exc.current.model_dump(mode="json") if exc.current else None,
        })
    if isinstance(exc, sessions.RidesVersionConflictError):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={
            "detail": str(exc), "code": "RIDES_SESSION_VERSION_CONFLICT", "current": exc.current.model_dump(mode="json"),
        })
    if isinstance(exc, sessions.RidesNotFoundError):
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})
    if isinstance(exc, sessions.RidesInputError):
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": str(exc)})
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


_ERRORS = (
    sessions.RidesInputError,
    sessions.RidesNotFoundError,
    sessions.RidesStateError,
    sessions.RidesVersionConflictError,
    sessions.RidesIdempotencyConflictError,
    vault_transactions.VaultTransactionIdempotencyConflictError,
    food_stock.FoodStockIdempotencyConflictError,
)


@router.get("/sessions/current", response_model=CurrentSessionRead)
def current_session_route(current_user: CurrentUserDep, db: SessionDep) -> CurrentSessionRead:
    """Session en cours avec CA, dépenses, net, progression vers la cible ; `session: null` sinon."""
    return sessions.current_session(db, current_user=current_user)


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions_route(current_user: CurrentUserDep, db: SessionDep, from_day: date | None = None, to_day: date | None = None):
    """Sessions démarrées sur des jours de Paris (par défaut : les 30 derniers jours)."""
    end = to_day or paris_today()
    try:
        return sessions.list_sessions(db, current_user=current_user, from_day=from_day or end - timedelta(days=29), to_day=end)
    except _ERRORS as exc:
        return _error(db, exc)


@router.post("/sessions", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def start_session_route(
    payload: SessionStart,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """VEC-02 : démarre une session (une seule en cours)."""
    try:
        read, duplicate = sessions.start_session(db, current_user=current_user, payload=payload,
                                                 idempotency_key=_require_key(idempotency_key))
    except _ERRORS as exc:
        return _error(db, exc)
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.get("/sessions/{session_id}", response_model=SessionRead)
def get_session_route(session_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    """VEC-11 : revue de la session (en cours ou close)."""
    try:
        return sessions.get_session(db, current_user=current_user, session_id=session_id)
    except _ERRORS as exc:
        return _error(db, exc)


@router.patch("/sessions/{session_id}", response_model=SessionRead)
def update_session_route(
    session_id: UUID,
    payload: SessionUpdate,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Cible et direction stratégique d'une session en cours ; version lue obligatoire."""
    try:
        return sessions.update_session(db, current_user=current_user, session_id=session_id, payload=payload,
                                       idempotency_key=_require_key(idempotency_key), request_path=request.url.path)
    except _ERRORS as exc:
        return _error(db, exc)


@router.post("/sessions/{session_id}/manual-revenue", response_model=SessionEntryResult, status_code=status.HTTP_201_CREATED)
def manual_revenue_route(
    session_id: UUID,
    payload: ManualRevenueCreate,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """VEC-04 : revenu VTC écrit au Vault (catégorie vtc, source vector_manual)."""
    try:
        return sessions.add_revenue(db, current_user=current_user, session_id=session_id, payload=payload,
                                    idempotency_key=_require_key(idempotency_key), request_path=request.url.path)
    except _ERRORS as exc:
        return _error(db, exc)


@router.post("/sessions/{session_id}/manual-expense", response_model=SessionEntryResult, status_code=status.HTTP_201_CREATED)
def manual_expense_route(
    session_id: UUID,
    payload: ManualExpenseCreate,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """VEC-05 : dépense pro écrite au Vault (carburant, péage, parking, entretien, plateformes, autre)."""
    try:
        return sessions.add_expense(db, current_user=current_user, session_id=session_id, payload=payload,
                                    idempotency_key=_require_key(idempotency_key), request_path=request.url.path)
    except _ERRORS as exc:
        return _error(db, exc)


@router.get("/sessions/{session_id}/drop-zones", response_model=list[DropZoneRead])
def list_drop_zones_route(session_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    try:
        return sessions.list_drop_zones(db, current_user=current_user, session_id=session_id)
    except _ERRORS as exc:
        return _error(db, exc)


@router.post("/sessions/{session_id}/drop-zone", response_model=DropZoneRead, status_code=status.HTTP_201_CREATED)
def drop_zone_route(
    session_id: UUID,
    payload: DropZoneCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """VEC-10 : dépose confirmée par l'utilisateur (zone, GPS facultatif, durée réelle)."""
    try:
        read, duplicate = sessions.add_drop_zone(db, current_user=current_user, session_id=session_id, payload=payload,
                                                 idempotency_key=_require_key(idempotency_key))
    except _ERRORS as exc:
        return _error(db, exc)
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.post("/sessions/{session_id}/complete", response_model=SessionRead)
def complete_session_route(
    session_id: UUID,
    payload: SessionComplete,
    request: Request,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """VEC-11 : clôture ; CA et dépenses figés, objectif atteint comparé à la cible seulement."""
    try:
        return sessions.complete_session(db, current_user=current_user, session_id=session_id, payload=payload,
                                         idempotency_key=_require_key(idempotency_key), request_path=request.url.path)
    except _ERRORS as exc:
        return _error(db, exc)


@router.post("/sessions/{session_id}/pause", response_model=SessionRead)
def pause_session_route(session_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    """Mettre en pause (kit Vector) : le temps de pause ne compte pas dans la durée active ; rejouer est sans effet."""
    try:
        return sessions.pause_session(db, current_user=current_user, session_id=session_id)
    except _ERRORS as exc:
        return _error(db, exc)


@router.post("/sessions/{session_id}/resume", response_model=SessionRead)
def resume_session_route(session_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    """Reprendre une session en pause ; rejouer sur une session en cours est sans effet."""
    try:
        return sessions.resume_session(db, current_user=current_user, session_id=session_id)
    except _ERRORS as exc:
        return _error(db, exc)


@router.post("/sessions/{session_id}/replan", response_model=SessionReplanResponse, status_code=status.HTTP_201_CREATED)
def replan_after_session_route(session_id: UUID, response: Response, current_user: CurrentUserDep, db: SessionDep):
    """VEC-11 → Imperium : replan de la journée après la clôture, à la demande ; demande ouverte → 200."""
    try:
        result, created = sessions.request_replan(db, current_user=current_user, session_id=session_id)
    except _ERRORS as exc:
        return _error(db, exc)
    except replan.ReplanCooldownError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={
            "detail": str(exc), "code": "REPLAN_COOLDOWN", "eligible_at": exc.eligible_at.isoformat(),
        })
    except replan.ReplanStateConflictError as exc:
        db.rollback()
        code = "DAY_NOT_STARTED" if "No operational day" in str(exc) else "REPLAN_ALREADY_OPEN"
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc), "code": code})
    if not created:
        response.status_code = status.HTTP_200_OK
    return result


# ---------- « Où aller ? » ----------

@router.post("/recommendations", response_model=RecommendationRead, status_code=status.HTTP_201_CREATED)
def recommend_route(
    payload: RecommendationRequest,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """VEC-07 : zone conseillée sur l'historique du créneau, ou abstention ; toujours un conseil, jamais une action."""
    try:
        read, duplicate = recommendations.recommend(db, current_user=current_user, payload=payload,
                                                    idempotency_key=_require_key(idempotency_key))
    except _RECO_ERRORS as exc:
        return _reco_error(db, exc)
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.get("/recommendations/latest", response_model=RecommendationRead | None)
def latest_recommendation_route(current_user: CurrentUserDep, db: SessionDep):
    """Dernière recommandation (carte en cache de VEC-01), ou null."""
    return recommendations.latest(db, current_user=current_user)


@router.get("/recommendations/{recommendation_id}", response_model=RecommendationRead)
def get_recommendation_route(recommendation_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    """VEC-08 : détail, zones comparées et signaux non pris en compte."""
    try:
        return recommendations.get(db, current_user=current_user, recommendation_id=recommendation_id)
    except _RECO_ERRORS as exc:
        return _reco_error(db, exc)


@router.post("/recommendations/{recommendation_id}/feedback", response_model=RecommendationRead)
def recommendation_feedback_route(
    recommendation_id: UUID, payload: RecommendationFeedback, current_user: CurrentUserDep, db: SessionDep
):
    """VEC-09 : utile ou non, et ce que l'utilisateur a fait ; un seul retour par recommandation."""
    try:
        return recommendations.record_feedback(db, current_user=current_user, recommendation_id=recommendation_id,
                                               payload=payload)
    except _RECO_ERRORS as exc:
        return _reco_error(db, exc)


_RECO_ERRORS = (
    recommendations.RecommendationNotFoundError,
    recommendations.RecommendationIdempotencyConflictError,
    recommendations.RecommendationFeedbackConflictError,
)


def _reco_error(db: SessionDep, exc: Exception) -> JSONResponse:
    db.rollback()
    if isinstance(exc, recommendations.RecommendationNotFoundError):
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})
    if isinstance(exc, recommendations.RecommendationFeedbackConflictError):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={
            "detail": str(exc), "code": "RIDES_FEEDBACK_CONFLICT", "current": exc.current.model_dump(mode="json"),
        })
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


# ---------- courses proposées ----------

_OFFER_ERRORS = (
    offers.OfferNotFoundError,
    offers.OfferInputError,
    offers.OfferStateError,
    offers.OfferIdempotencyConflictError,
    offers.OfferVersionConflictError,
    sessions.RidesNotFoundError,
    sessions.RidesStateError,
    sessions.RidesIdempotencyConflictError,
    vault_transactions.VaultTransactionIdempotencyConflictError,
)


def _offer_error(db: SessionDep, exc: Exception) -> JSONResponse:
    if isinstance(exc, offers.OfferVersionConflictError):
        db.rollback()
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={
            "detail": str(exc), "code": "RIDES_OFFER_VERSION_CONFLICT", "current": exc.current.model_dump(mode="json"),
        })
    if isinstance(exc, offers.OfferNotFoundError):
        db.rollback()
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})
    if isinstance(exc, offers.OfferInputError):
        db.rollback()
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": str(exc)})
    return _error(db, exc)


@router.get("/feeds/weather", response_model=WeatherFeedRead)
def weather_feed_route(current_user: CurrentUserDep, db: SessionDep) -> WeatherFeedRead:  # noqa: ARG001
    """Dernier relevé météo (Open-Meteo, Météo-France) : maintenant et 12 prochaines heures ; jamais inventé."""
    return weather.feed(db)


@router.get("/training-summary", response_model=TrainingSummaryRead)
def training_summary_route(current_user: CurrentUserDep, db: SessionDep) -> TrainingSummaryRead:
    """Courses enregistrées, résultats réels disponibles, médiane €/h, phase d'apprentissage (doc 57 §3)."""
    return offers.training_summary(db, current_user=current_user)


@router.post("/sessions/{session_id}/offers", response_model=RideOfferRead, status_code=status.HTTP_201_CREATED)
def record_offer_route(
    session_id: UUID,
    payload: RideOfferCreate,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    """Course proposée (saisie) ; variables calculées, aucun verdict tant que le modèle n'est pas entraîné."""
    try:
        read, duplicate = offers.record_offer(db, current_user=current_user, session_id=session_id, payload=payload,
                                              idempotency_key=_require_key(idempotency_key))
    except _OFFER_ERRORS as exc:
        return _offer_error(db, exc)
    if duplicate:
        response.status_code = status.HTTP_200_OK
    return read


@router.get("/sessions/{session_id}/offers", response_model=RideOfferListResponse)
def list_offers_route(session_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    try:
        return offers.list_offers(db, current_user=current_user, session_id=session_id)
    except _OFFER_ERRORS as exc:
        return _offer_error(db, exc)


@router.get("/offers/{offer_id}", response_model=RideOfferRead)
def get_offer_route(offer_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    try:
        return offers.get_offer(db, current_user=current_user, offer_id=offer_id)
    except _OFFER_ERRORS as exc:
        return _offer_error(db, exc)


@router.post("/offers/{offer_id}/decision", response_model=RideOfferRead)
def decide_offer_route(offer_id: UUID, payload: RideDecisionRequest, current_user: CurrentUserDep, db: SessionDep):
    """Acceptée, refusée ou manquée : donnée de comportement, jamais cible d'apprentissage (doc 33 §8)."""
    try:
        return offers.decide(db, current_user=current_user, offer_id=offer_id, payload=payload)
    except _OFFER_ERRORS as exc:
        return _offer_error(db, exc)


@router.post("/offers/{offer_id}/outcome", response_model=RideOfferRead)
def offer_outcome_route(
    offer_id: UUID, payload: RideOutcomeRequest, request: Request, current_user: CurrentUserDep, db: SessionDep
):
    """Résultat réel d'une course acceptée : gain ÷ temps mobilisé ; revenu écrit au Vault par défaut."""
    try:
        return offers.record_outcome(db, current_user=current_user, offer_id=offer_id, payload=payload,
                                     request_path=request.url.path)
    except _OFFER_ERRORS as exc:
        return _offer_error(db, exc)


# ---------- règles métier ----------

@router.get("/rules", response_model=BusinessRuleListResponse)
def list_rules_route(current_user: CurrentUserDep, db: SessionDep) -> BusinessRuleListResponse:
    """Règles du doc 57 §4 codées (R1, R2, R7, R8) et celles qui attendent des données."""
    return rules.list_rules(db, current_user=current_user)


@router.patch("/rules/{rule_code}", response_model=BusinessRuleRead)
def update_rule_route(rule_code: str, payload: BusinessRuleUpdate, current_user: CurrentUserDep, db: SessionDep):
    """Activer, désactiver, rendre ferme ou modifier les conditions ; raison et version lue obligatoires."""
    try:
        return rules.update_rule(db, current_user=current_user, rule_code=rule_code, payload=payload)
    except rules.RuleNotFoundError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})
    except rules.RuleVersionConflictError as exc:
        db.rollback()
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={
            "detail": str(exc), "code": "RIDES_RULE_VERSION_CONFLICT", "current": exc.current.model_dump(mode="json"),
        })
