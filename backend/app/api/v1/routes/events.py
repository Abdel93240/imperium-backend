from fastapi import APIRouter, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUserDep, SessionDep
from app.schemas.events import EventEnvelope, EventIngestResponse
from app.services.events.ingestion import ingest_event

router = APIRouter()


@router.post("", response_model=EventIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_event_route(
    envelope: EventEnvelope,
    request: Request,
    response: Response,
    current_user: CurrentUserDep,
    db: SessionDep,
) -> EventIngestResponse:
    """Store an authenticated canonical event envelope.

    Authenticated app requests derive user_id from JWT.
    Internal n8n requests must use the HMAC/signature path.
    Client-supplied user_id is ignored for storage and never trusted blindly.
    """
    try:
        result, duplicate = ingest_event(
            db,
            envelope=envelope,
            current_user=current_user,
            request_method=request.method,
            request_path=request.url.path,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Event conflicts with an existing stored event.",
        ) from exc

    if duplicate:
        response.status_code = status.HTTP_200_OK
    return result
