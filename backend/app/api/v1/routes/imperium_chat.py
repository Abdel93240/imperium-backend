"""Chatbot V1 (doc 72) : sessions, messages, validation explicite des propositions ; moteur local seulement."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.chat import ChatMessageCreate, ChatProposalRead, ChatSessionCreate, ChatSessionRead, ChatTurnRead
from app.services.chat import engine

router = APIRouter()


def _disabled() -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": "Disabled.", "code": "CHAT_DISABLED"})


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, engine.ChatNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/chat/sessions", response_model=ChatSessionRead, status_code=status.HTTP_201_CREATED)
def start_route(payload: ChatSessionCreate, current_user: CurrentUserDep, db: SessionDep):
    if not engine.enabled(db):
        return _disabled()
    try:
        return engine.start_session(db, current_user=current_user, payload=payload)
    except engine.ChatNotFoundError as exc:  # repère de projet ou de mission qui n'est pas à l'utilisateur
        raise _http(exc) from exc


@router.get("/chat/sessions/{session_id}", response_model=ChatSessionRead)
def get_route(session_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    try:
        return engine.get_session(db, current_user=current_user, session_id=session_id)
    except engine.ChatNotFoundError as exc:
        raise _http(exc) from exc


@router.post("/chat/sessions/{session_id}/messages", response_model=ChatTurnRead)
def message_route(session_id: UUID, payload: ChatMessageCreate, current_user: CurrentUserDep, db: SessionDep):
    """Un tour de conversation ; la proposition éventuelle n'est pas exécutée (elle attend une validation)."""
    if not engine.enabled(db):
        return _disabled()
    try:
        return engine.send_message(db, current_user=current_user, session_id=session_id, text=payload.text)
    except (engine.ChatNotFoundError, engine.ChatStateError) as exc:
        db.rollback()
        raise _http(exc) from exc


@router.post("/chat/sessions/{session_id}/resume", response_model=ChatTurnRead)
def resume_route(session_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    """Après un changement d'agent validé : le nouvel agent répond à la demande d'avant, sans la faire répéter."""
    if not engine.enabled(db):
        return _disabled()
    try:
        return engine.resume_after_switch(db, current_user=current_user, session_id=session_id)
    except (engine.ChatNotFoundError, engine.ChatStateError) as exc:
        db.rollback()
        raise _http(exc) from exc


@router.post("/chat/sessions/{session_id}/proposals/{proposal_id}/validate", response_model=ChatProposalRead)
def validate_route(session_id: UUID, proposal_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    """Seule écriture du chatbot : exécute l'action proposée (statut `failed` et raison si le serveur la refuse)."""
    try:
        return engine.validate_proposal(db, current_user=current_user, session_id=session_id, proposal_id=proposal_id)
    except (engine.ChatNotFoundError, engine.ChatStateError) as exc:
        db.rollback()
        raise _http(exc) from exc


@router.post("/chat/sessions/{session_id}/proposals/{proposal_id}/reject", response_model=ChatProposalRead)
def reject_route(session_id: UUID, proposal_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    try:
        return engine.reject_proposal(db, current_user=current_user, session_id=session_id, proposal_id=proposal_id)
    except (engine.ChatNotFoundError, engine.ChatStateError) as exc:
        db.rollback()
        raise _http(exc) from exc


@router.post("/chat/sessions/{session_id}/close", response_model=ChatSessionRead)
def close_route(session_id: UUID, current_user: CurrentUserDep, db: SessionDep):
    try:
        return engine.close_session(db, current_user=current_user, session_id=session_id)
    except engine.ChatNotFoundError as exc:
        raise _http(exc) from exc


@router.delete("/chat/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_route(session_id: UUID, current_user: CurrentUserDep, db: SessionDep) -> Response:
    """Suppression réelle, toujours possible (même chatbot éteint)."""
    try:
        engine.delete_session(db, current_user=current_user, session_id=session_id)
    except engine.ChatNotFoundError as exc:
        raise _http(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
