import hashlib
import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import IdempotencyStatus
from app.services.events.emitter import build_event
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumDayReview
from app.schemas.imperium import DayReviewResponse, FinishDayRequest, FinishDayResponse


class DayAlreadyFinishedError(ValueError):
    pass


class IdempotencyConflictError(ValueError):
    pass


def finish_day(
    db: Session,
    *,
    current_user: User,
    payload: FinishDayRequest,
    idempotency_key: str,
    request_method: str,
    request_path: str,
) -> tuple[FinishDayResponse, bool]:
    request_hash = _hash_payload(payload)
    existing_key = db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == current_user.id,
            IdempotencyKey.idempotency_key == idempotency_key,
        )
    )

    if existing_key is not None:
        if existing_key.request_hash != request_hash:
            raise IdempotencyConflictError("Idempotency key already used with different payload.")
        if existing_key.response_body is None:
            raise IdempotencyConflictError("Idempotency key is already processing.")
        return FinishDayResponse(**existing_key.response_body), True

    existing_review = db.scalar(
        select(ImperiumDayReview).where(
            ImperiumDayReview.user_id == current_user.id,
            ImperiumDayReview.local_date == payload.local_date,
        )
    )
    if existing_review is not None:
        raise DayAlreadyFinishedError(
            "Day review already exists for this local_date. V1 rejects second non-idempotent finishes."
        )

    event_id = f"evt_{uuid4().hex}"
    review = ImperiumDayReview(
        user_id=current_user.id,
        local_date=payload.local_date,
        timezone=payload.timezone,
        day_status=payload.day_status.value,
        energy_level=payload.energy_level,
        fatigue_level=payload.fatigue_level,
        sleep_quality=payload.sleep_quality,
        stress_level=payload.stress_level,
        mood=payload.mood,
        main_win=payload.main_win,
        main_problem=payload.main_problem,
        completed_items=[item.model_dump(mode="json", exclude_none=True) for item in payload.completed_items],
        missed_items=[item.model_dump(mode="json", exclude_none=True) for item in payload.missed_items],
        notes=payload.notes,
        free_text=payload.free_text,
        source_event_id=event_id,
    )
    db.add(review)
    db.flush()

    event_payload = payload.model_dump(mode="json", exclude_none=True)
    # E2 (passe 0): canonical planning.day.finished; the deterministic
    # corr_day_finish_{review.id} dossier is kept (doc 77 cites it as the one
    # non-random correlation of the legacy code).
    event = build_event(
        db,
        user_id=current_user.id,
        event_type="day.finished",
        payload=event_payload,
        idempotency_key=idempotency_key,
        event_id=event_id,
        correlation_id=f"corr_day_finish_{review.id}",
    )
    db.add(event)
    db.flush()

    response = FinishDayResponse(
        review=DayReviewResponse.model_validate(review),
        event_id=event_id,
        status="stored",
    )
    idempotency = IdempotencyKey(
        user_id=current_user.id,
        idempotency_key=idempotency_key,
        request_method=request_method,
        request_path=request_path,
        request_hash=request_hash,
        status=IdempotencyStatus.completed,
        response_status_code=201,
        response_body=response.model_dump(mode="json"),
    )
    db.add(idempotency)
    db.commit()
    return response, False


def get_latest_day_review(db: Session, *, current_user: User) -> ImperiumDayReview | None:
    return db.scalar(
        select(ImperiumDayReview)
        .where(ImperiumDayReview.user_id == current_user.id)
        .order_by(ImperiumDayReview.local_date.desc(), ImperiumDayReview.created_at.desc())
        .limit(1)
    )


def _hash_payload(payload: FinishDayRequest) -> str:
    canonical = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
