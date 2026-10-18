"""Jeûne (PAT-05, doc 41 §8) et contraintes lues par Pulse (doc 40 §15.2).

Un jeûne ne démarre que sur confirmation de l'utilisateur, le jour même ; jamais
d'intention déduite du calendrier. La fenêtre est figée au démarrage : suhoor = fajr
− `path.suhoor_offset_min` (30 min par défaut), iftar = maghrib, depuis la source
d'horaires choisie (MAWAQIT puis calcul). La fin à l'iftar et la rupture demandent
toujours une action de l'utilisateur ; aucun job ne clôt un jeûne tout seul. Un jeûne
démarré par erreur peut être annulé tant qu'il est en cours : la ligne est supprimée.

Pulse lit `window_fast` : hydratation bloquée pendant la fenêtre (sauf choix contraire
au démarrage), repas notés pendant la fenêtre acceptés avec un avertissement.
La raison d'une rupture reste dans la ligne, jamais dans les événements.
"""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.path import PathFast
from app.schemas.path_worship import (
    FastBreakRequest,
    FastCancelRequest,
    FastCancelResult,
    FastEndRequest,
    FastingStateRead,
    FastListResponse,
    FastRead,
    FastStartRequest,
)
from app.services.events.emitter import build_event
from app.services.params import get_parameter
from app.services.path.prayer import prayer_times
from app.services.pulse import food_stock

PARIS = ZoneInfo("Europe/Paris")
CLOCK_SKEW = timedelta(minutes=5)
DEFAULT_SUHOOR_OFFSET_MIN = 30
HYDRATION_BLOCKED = "Jeûne en cours - hydratation hors fenêtre désactivée."
MEAL_DURING_FAST = "Repas noté pendant les heures de jeûne."


class FastInputError(ValueError):
    pass


class FastNotFoundError(ValueError):
    pass


class FastStateError(ValueError):
    def __init__(self, message: str, current: FastRead | None = None) -> None:
        super().__init__(message)
        self.current = current


class FastIdempotencyConflictError(ValueError):
    pass


def start_fast(
    db: Session, *, current_user: User, payload: FastStartRequest, idempotency_key: str, now: datetime | None = None
) -> tuple[FastRead, bool]:
    now = now or datetime.now(UTC)
    today = now.astimezone(PARIS).date()
    day = payload.fasting_date or today
    fingerprint = food_stock.request_hash("path.fasting.start", {**payload.model_dump(mode="json"), "fasting_date": day.isoformat()})
    existing = db.scalar(select(PathFast).where(PathFast.user_id == current_user.id, PathFast.idempotency_key == idempotency_key))
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise FastIdempotencyConflictError("Idempotency key already used with a different fast.")
        return FastRead.model_validate(existing), True
    if day != today:
        raise FastInputError("Un jeûne se démarre le jour même.")
    active = db.scalar(select(PathFast).where(PathFast.user_id == current_user.id, PathFast.status == "active").with_for_update())
    if active is not None:
        raise FastStateError(
            f"Un jeûne est déjà en cours (du {active.fasting_date:%d/%m}). Termine-le ou romps-le d'abord.",
            FastRead.model_validate(active),
        )
    same_day = db.scalar(select(PathFast).where(PathFast.user_id == current_user.id, PathFast.fasting_date == day))
    if same_day is not None:
        raise FastStateError("Un jeûne est déjà enregistré pour ce jour.", FastRead.model_validate(same_day))
    adhans, source = prayer_times(db, day)
    offset = int(get_parameter(db, "path.suhoor_offset_min", default=DEFAULT_SUHOOR_OFFSET_MIN))
    fast = PathFast(
        user_id=current_user.id, fasting_date=day, fasting_type=payload.fasting_type, status="active", started_at=now,
        suhoor_at=adhans["fajr"] - timedelta(minutes=offset), iftar_at=adhans["maghrib"], times_source=source,
        hydration_daytime_allowed=payload.hydration_daytime_allowed, version=1, idempotency_key=idempotency_key,
        request_hash=fingerprint,
    )
    db.add(fast)
    db.flush()
    db.refresh(fast)
    _event(db, current_user, fast, "path.fasting.started", {
        "suhoor_at": fast.suhoor_at.isoformat(), "iftar_at": fast.iftar_at.isoformat(),
        "hydration_limits": {"daytime": fast.hydration_daytime_allowed},
    })
    read = FastRead.model_validate(fast)
    db.commit()
    return read, False


def end_fast(
    db: Session, *, current_user: User, fast_id: UUID, payload: FastEndRequest, idempotency_key: str, request_path: str,
    now: datetime | None = None,
) -> tuple[FastRead, bool]:
    fingerprint = food_stock.request_hash("path.fasting.end", {"fast_id": str(fast_id), **payload.model_dump(mode="json")})
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, FastRead)
    if previous is not None:
        return previous, True
    now = now or datetime.now(UTC)
    fast = _active(db, current_user, fast_id)
    ended_at = payload.ended_at or now
    if ended_at > now + CLOCK_SKEW:
        raise FastInputError("L'heure de fin ne peut pas être dans le futur.")
    if ended_at < fast.iftar_at:
        raise FastInputError(
            f"L'iftar n'est pas encore passé ({_hhmm(fast.iftar_at)}). Pour arrêter avant, romps le jeûne."
        )
    fast.status, fast.ended_at, fast.version = "ended", ended_at, fast.version + 1
    return _finish(db, current_user, fast, "path.fasting.ended", {"ended_at": ended_at.isoformat()},
                   idempotency_key, request_path, fingerprint)


def break_fast(
    db: Session, *, current_user: User, fast_id: UUID, payload: FastBreakRequest, idempotency_key: str,
    request_path: str, now: datetime | None = None,
) -> tuple[FastRead, bool]:
    fingerprint = food_stock.request_hash("path.fasting.break", {"fast_id": str(fast_id), **payload.model_dump(mode="json")})
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, FastRead)
    if previous is not None:
        return previous, True
    now = now or datetime.now(UTC)
    fast = _active(db, current_user, fast_id)
    broken_at = payload.broken_at or now
    if broken_at > now + CLOCK_SKEW:
        raise FastInputError("L'heure de rupture ne peut pas être dans le futur.")
    if broken_at >= fast.iftar_at:
        raise FastInputError("L'iftar est passé : termine le jeûne normalement.")
    fast.status, fast.broken_at, fast.version = "broken", max(broken_at, fast.suhoor_at), fast.version + 1
    fast.break_reason = (payload.reason or "").strip() or None
    # Imperium propose un nouveau planning ; l'utilisateur le confirme (doc 41 §8).
    return _finish(db, current_user, fast, "path.fasting.broken",
                   {"broken_at": fast.broken_at.isoformat(), "replan_prompt": True},
                   idempotency_key, request_path, fingerprint)


def cancel_fast(
    db: Session, *, current_user: User, fast_id: UUID, payload: FastCancelRequest, idempotency_key: str, request_path: str,
) -> tuple[FastCancelResult, bool]:
    """Démarrage par erreur : le jeûne en cours est supprimé (un nouveau peut être démarré le jour même)."""
    fingerprint = food_stock.request_hash("path.fasting.cancel", {"fast_id": str(fast_id), **payload.model_dump(mode="json")})
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, FastCancelResult)
    if previous is not None:
        return previous, True
    fast = _active(db, current_user, fast_id)
    _event(db, current_user, fast, "path.fasting.cancelled", {})
    db.delete(fast)
    db.flush()
    read = FastCancelResult(cancelled=True, fast_id=fast_id)
    food_stock.remember(db, current_user, idempotency_key, "POST", request_path, fingerprint, 200, read)
    db.commit()
    return read, False


def list_fasts(db: Session, *, current_user: User, from_day: date, to_day: date) -> FastListResponse:
    if to_day < from_day or (to_day - from_day).days > 366:
        raise FastInputError("Période invalide (366 jours maximum).")
    fasts = db.scalars(
        select(PathFast)
        .where(PathFast.user_id == current_user.id, PathFast.fasting_date >= from_day, PathFast.fasting_date <= to_day)
        .order_by(PathFast.fasting_date.asc())
    )
    return FastListResponse(items=[FastRead.model_validate(fast) for fast in fasts])


def state(db: Session, *, current_user: User, at: datetime | None = None) -> FastingStateRead:
    at = at or datetime.now(UTC)
    in_window = window_fast(db, current_user, at)
    fast = in_window or db.scalar(select(PathFast).where(PathFast.user_id == current_user.id, PathFast.status == "active"))
    active = in_window is not None and in_window.status == "active"
    if active:
        message = f"Jeûne en cours — iftar à {_hhmm(fast.iftar_at)}."
    elif fast is not None and fast.status == "active" and at >= fast.iftar_at:
        message = "L'iftar est passé : confirme la fin du jeûne."
    else:
        message = None
    daytime = not active or fast.hydration_daytime_allowed
    return FastingStateRead(
        fasting_active=active, fast=FastRead.model_validate(fast) if fast else None,
        hydration_limits={"daytime": daytime}, message=message,
    )


def window_fast(db: Session, user: User, at: datetime) -> PathFast | None:
    """Jeûne dont la fenêtre suhoor → iftar contient `at` (une rupture ferme la fenêtre)."""
    fast = db.scalar(
        select(PathFast).where(PathFast.user_id == user.id, PathFast.suhoor_at <= at, PathFast.iftar_at > at).limit(1)
    )
    if fast is None or (fast.status == "broken" and fast.broken_at <= at):
        return None
    return fast


def hydration_blocked(db: Session, user: User, at: datetime) -> str | None:
    fast = window_fast(db, user, at)
    return HYDRATION_BLOCKED if fast is not None and not fast.hydration_daytime_allowed else None


def meal_warning(db: Session, user: User, at: datetime) -> str | None:
    return MEAL_DURING_FAST if window_fast(db, user, at) is not None else None


def day_message(db: Session, user: User, day: date, now: datetime | None = None) -> str | None:
    """Une seule ligne pour le tableau de bord Pulse (doc 40 §15.2 : une bannière jeûne au plus)."""
    now = now or datetime.now(UTC)
    fast = db.scalar(select(PathFast).where(PathFast.user_id == user.id, PathFast.fasting_date == day))
    if fast is None:
        return None
    if fast.status == "broken":
        return "Jeûne rompu ce jour."
    if fast.status == "ended":
        return f"Jeûne terminé à {_hhmm(fast.ended_at)}."
    if now >= fast.iftar_at:
        return "L'iftar est passé : confirme la fin du jeûne."
    return f"Jeûne en cours — iftar à {_hhmm(fast.iftar_at)}."


def paris_today() -> date:
    return datetime.now(PARIS).date()


def _active(db: Session, user: User, fast_id: UUID) -> PathFast:
    fast = db.scalar(select(PathFast).where(PathFast.id == fast_id, PathFast.user_id == user.id).with_for_update())
    if fast is None:
        raise FastNotFoundError("Jeûne introuvable.")
    if fast.status != "active":
        raise FastStateError("Ce jeûne est déjà clos.", FastRead.model_validate(fast))
    return fast


def _finish(
    db: Session, user: User, fast: PathFast, event_type: str, extra: dict, idempotency_key: str, request_path: str,
    fingerprint: str,
) -> tuple[FastRead, bool]:
    db.flush()
    db.refresh(fast)
    _event(db, user, fast, event_type, extra)
    read = FastRead.model_validate(fast)
    food_stock.remember(db, user, idempotency_key, "POST", request_path, fingerprint, 200, read)
    db.commit()
    return read, False


def _event(db: Session, user: User, fast: PathFast, event_type: str, extra: dict) -> None:
    db.add(
        build_event(
            db, user_id=user.id, event_type=event_type,
            payload={"fast_id": str(fast.id), "fasting_date": fast.fasting_date.isoformat(),
                     "fasting_type": fast.fasting_type, "source": "user_action", **extra},
            idempotency_key=f"{event_type}.{fast.id}", source_app=SourceApp.path, privacy_level=PrivacyLevel.high,
        )
    )


def _hhmm(moment: datetime) -> str:
    return moment.astimezone(PARIS).strftime("%H:%M")
