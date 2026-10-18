"""Progression du Coran (doc 41 §12) : point de reprise validé, objectif, khatm, plans.

Le point de reprise est la dernière page lue validée par l'utilisateur (1–604, mushaf de
Médine). Il peut le donner en page, en sourate (début) ou en juz (début). Revenir en
arrière demande une confirmation ; rien n'est déduit du temps passé ou de l'écran, et un
jour manqué ne déclenche aucun rattrapage. Le khatm est confirmé par l'utilisateur, une
fois la page 604 validée. Un plan donne seulement la page visée du jour, comme repère.
"""

import math
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.path import PathQuranPlan, PathQuranProgress
from app.schemas.path_quran import (
    QuranContinuationRead,
    QuranKhatmRequest,
    QuranLocationRead,
    QuranObjectiveRequest,
    QuranPlanCreate,
    QuranPlanRead,
    QuranPlanTodayRead,
    QuranProgressRequest,
)
from app.services.events.emitter import build_event
from app.services.path import quran_index
from app.services.path.adhkar import paris_today
from app.services.pulse import food_stock

PAGES_PER_JUZ = 20


class QuranInputError(ValueError):
    pass


class QuranNotFoundError(ValueError):
    pass


class QuranConflictError(ValueError):
    def __init__(self, message: str, code: str, current: QuranContinuationRead) -> None:
        super().__init__(message)
        self.code = code
        self.current = current


def location(page: int) -> QuranLocationRead:
    return QuranLocationRead(
        page=page, juz=quran_index.juz_of(page), surah=quran_index.surah_of(page), surahs_on_page=quran_index.surahs_on(page)
    )


def continuation(db: Session, *, current_user: User, today: date | None = None) -> QuranContinuationRead:
    return _read(db, current_user, _progress(db, current_user), today or paris_today())


def record_progress(
    db: Session, *, current_user: User, payload: QuranProgressRequest, idempotency_key: str, request_path: str,
    now: datetime | None = None,
) -> QuranContinuationRead:
    fingerprint = food_stock.request_hash("path.quran.progress", payload.model_dump(mode="json"))
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, QuranContinuationRead)
    if previous is not None:
        return previous
    now = now or datetime.now(UTC)
    page = payload.page or (
        quran_index.SURAH_START_PAGES[payload.surah - 1] if payload.surah else quran_index.JUZ_START_PAGES[payload.juz - 1]
    )
    row = _progress(db, current_user, lock=True)
    previous_page = row.last_validated_page if row else None
    if row is None:
        if payload.base_version is not None:
            raise QuranConflictError("Le point de reprise a changé.", "QURAN_VERSION_CONFLICT", _read(db, current_user, None, paris_today(now)))
        row = PathQuranProgress(user_id=current_user.id, last_validated_page=page, last_validated_at=now, version=1)
        db.add(row)
    else:
        if payload.base_version != row.version:
            raise QuranConflictError("Le point de reprise a changé depuis ta lecture.", "QURAN_VERSION_CONFLICT",
                                     _read(db, current_user, row, paris_today(now)))
        if page < row.last_validated_page and not payload.confirm_regression:
            raise QuranConflictError(
                f"Page {page} avant ton point de reprise (page {row.last_validated_page}). Confirme pour revenir en arrière.",
                "QURAN_REGRESSION", _read(db, current_user, row, paris_today(now)),
            )
        row.last_validated_page, row.last_validated_at, row.version = page, now, row.version + 1
    db.flush()
    db.refresh(row)
    _event(db, current_user, "path.quran.progress.updated",
           {"page": page, "previous_page": previous_page, "regression": previous_page is not None and page < previous_page},
           f"{row.id}.v{row.version}")
    read = _read(db, current_user, row, paris_today(now))
    food_stock.remember(db, current_user, idempotency_key, "POST", request_path, fingerprint, 200, read)
    db.commit()
    return read


def set_objective(
    db: Session, *, current_user: User, payload: QuranObjectiveRequest, idempotency_key: str, request_path: str
) -> QuranContinuationRead:
    fingerprint = food_stock.request_hash("path.quran.objective", payload.model_dump(mode="json"))
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, QuranContinuationRead)
    if previous is not None:
        return previous
    row = _progress(db, current_user, lock=True)
    if row is None:
        raise QuranInputError("Valide d'abord ton point de reprise.")
    row.daily_objective_pages = payload.daily_objective_pages
    row.version += 1
    db.flush()
    db.refresh(row)
    read = _read(db, current_user, row, paris_today())
    food_stock.remember(db, current_user, idempotency_key, "PATCH", request_path, fingerprint, 200, read)
    db.commit()
    return read


def confirm_khatm(
    db: Session, *, current_user: User, payload: QuranKhatmRequest, idempotency_key: str, request_path: str
) -> QuranContinuationRead:
    fingerprint = food_stock.request_hash("path.quran.khatm", payload.model_dump(mode="json"))
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, QuranContinuationRead)
    if previous is not None:
        return previous
    row = _progress(db, current_user, lock=True)
    if row is None or row.last_validated_page != quran_index.PAGES:
        raise QuranInputError("Le khatm se confirme une fois la page 604 validée.")
    if payload.base_version != row.version:
        raise QuranConflictError("Le point de reprise a changé depuis ta lecture.", "QURAN_VERSION_CONFLICT",
                                 _read(db, current_user, row, paris_today()))
    row.khatm_count += 1
    row.version += 1
    db.flush()
    db.refresh(row)
    _event(db, current_user, "path.quran.khatm_confirmed", {"khatm_count": row.khatm_count}, f"{row.id}.v{row.version}")
    read = _read(db, current_user, row, paris_today())
    food_stock.remember(db, current_user, idempotency_key, "POST", request_path, fingerprint, 200, read)
    db.commit()
    return read


# ---------- plans ----------

def create_plan(
    db: Session, *, current_user: User, payload: QuranPlanCreate, idempotency_key: str, today: date | None = None
) -> tuple[QuranPlanRead, bool]:
    fingerprint = food_stock.request_hash("path.quran.plan", payload.model_dump(mode="json"))
    existing = db.scalar(
        select(PathQuranPlan).where(PathQuranPlan.user_id == current_user.id, PathQuranPlan.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise QuranInputError("Idempotency key already used with a different plan.")
        return QuranPlanRead.model_validate(existing), True
    today = today or paris_today()
    row = _progress(db, current_user)
    start = min(row.last_validated_page + 1, quran_index.PAGES) if row else 1
    pages_per_day = _pages_per_day(payload, start, today)
    for plan in db.scalars(
        select(PathQuranPlan).where(PathQuranPlan.user_id == current_user.id, PathQuranPlan.active.is_(True)).with_for_update()
    ):
        plan.active, plan.ended_at = False, datetime.now(UTC)
    db.flush()
    plan = PathQuranPlan(
        user_id=current_user.id, plan_type=payload.plan_type, pages_per_day=pages_per_day,
        end_date=payload.end_date if payload.plan_type == "finish_in_days" else None, start_page=start, started_on=today,
        active=True, idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    db.add(plan)
    db.flush()
    db.refresh(plan)
    _event(db, current_user, "path.quran.plan_updated",
           {"plan_id": str(plan.id), "plan_type": plan.plan_type, "pages_per_day": pages_per_day, "active": True}, str(plan.id))
    read = QuranPlanRead.model_validate(plan)
    db.commit()
    return read, False


def stop_plan(db: Session, *, current_user: User, plan_id: UUID) -> QuranPlanRead:
    plan = db.scalar(
        select(PathQuranPlan).where(PathQuranPlan.id == plan_id, PathQuranPlan.user_id == current_user.id).with_for_update()
    )
    if plan is None:
        raise QuranNotFoundError("Plan introuvable.")
    if plan.active:
        plan.active, plan.ended_at = False, datetime.now(UTC)
        _event(db, current_user, "path.quran.plan_updated", {"plan_id": str(plan.id), "active": False}, f"{plan.id}.stop")
        db.commit()
        db.refresh(plan)
    return QuranPlanRead.model_validate(plan)


def _pages_per_day(payload: QuranPlanCreate, start: int, today: date) -> int:
    if payload.plan_type == "daily_pages":
        if payload.pages_per_day is None:
            raise QuranInputError("Indique le nombre de pages par jour.")
        return payload.pages_per_day
    if payload.plan_type == "juz_based":
        if payload.juz_per_day is None:
            raise QuranInputError("Indique le nombre de juz par jour.")
        return min(payload.juz_per_day * PAGES_PER_JUZ, quran_index.PAGES)
    if payload.end_date is None or payload.end_date < today:
        raise QuranInputError("Choisis une date de fin à partir d'aujourd'hui.")
    days = (payload.end_date - today).days + 1
    return max(1, math.ceil((quran_index.PAGES - start + 1) / days))


# ---------- internes ----------

def _progress(db: Session, user: User, *, lock: bool = False) -> PathQuranProgress | None:
    query = select(PathQuranProgress).where(PathQuranProgress.user_id == user.id)
    return db.scalar(query.with_for_update() if lock else query)


def _read(db: Session, user: User, row: PathQuranProgress | None, today: date) -> QuranContinuationRead:
    plan = db.scalar(select(PathQuranPlan).where(PathQuranPlan.user_id == user.id, PathQuranPlan.active.is_(True)))
    plan_today = None
    if plan is not None:
        elapsed = max(0, (today - plan.started_on).days)
        planned = min(quran_index.PAGES, plan.start_page - 1 + plan.pages_per_day * (elapsed + 1))
        plan_today = QuranPlanTodayRead(plan=QuranPlanRead.model_validate(plan), page_planned_today=planned)
    if row is None:
        return QuranContinuationRead(
            started=False, location=None, resume_page=None, last_validated_at=None, daily_objective_pages=None,
            khatm_count=0, khatm_available=False, version=None, plan=plan_today,
        )
    return QuranContinuationRead(
        started=True, location=location(row.last_validated_page),
        resume_page=min(row.last_validated_page + 1, quran_index.PAGES), last_validated_at=row.last_validated_at,
        daily_objective_pages=row.daily_objective_pages, khatm_count=row.khatm_count,
        khatm_available=row.last_validated_page == quran_index.PAGES, version=row.version, plan=plan_today,
    )


def _event(db: Session, user: User, event_type: str, payload: dict, ref: str) -> None:
    db.add(
        build_event(
            db, user_id=user.id, event_type=event_type, payload={**payload, "source": "user_action"},
            idempotency_key=f"{event_type}.{ref}", source_app=SourceApp.path, privacy_level=PrivacyLevel.high,
        )
    )
