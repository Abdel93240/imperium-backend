"""Courses proposées (doc 57 §5, §6, §11 ; doc 33 §8) : la base d'apprentissage du scoring.

Chaque course proposée pendant une session est gardée avec ses variables : saisies (prix,
distances, durées, zones, majoration, paiement, type) et calculées au moment de l'offre
(€/h affiché, €/km, temps total, créneau, contexte de la session). Les variables liées au
culte ou à la santé du doc 57 §5.2 ne sont pas reprises : doc 13 §5 les exclut de Vector.

La décision (acceptée, refusée, manquée) est une donnée de comportement : elle n'est jamais
la cible d'apprentissage. La cible est le résultat réel d'une course acceptée : gain ÷ temps
mobilisé (approche + attente + course + retour), à la minute. Tant que le modèle n'est
pas entraîné, le signal vient des règles métier seules (doc 57 §3.1, services/vector/rules.py) ;
Vector n'agit jamais sur l'appli VTC.
"""

from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from statistics import median
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.rides import RidesOffer, RidesSession
from app.schemas.rides import (
    ManualRevenueCreate,
    RideDecisionRequest,
    RideOfferCreate,
    RideOfferListResponse,
    RideOfferRead,
    RideOutcomeRequest,
    TrainingSummaryRead,
)
from app.services.events.emitter import build_event
from app.services.pulse import food_stock
from app.services.vector import sessions
from app.services.vector.rules import ensure_rules, evaluate
from app.services.vector.zones import zone_key

PARIS = ZoneInfo("Europe/Paris")
CLOCK_SKEW = timedelta(minutes=5)
PHASES = ((100, "cold_start"), (500, "transition"))  # doc 57 §3 : < 100, 100–500, 500+
DECISION_EVENTS = {"accepted": "rides.ride.accepted", "refused": "rides.ride.refused", "missed": "rides.ride.missed"}


class OfferNotFoundError(ValueError):
    pass


class OfferInputError(ValueError):
    pass


class OfferStateError(ValueError):
    pass


class OfferIdempotencyConflictError(ValueError):
    pass


class OfferVersionConflictError(ValueError):
    def __init__(self, current: RideOfferRead) -> None:
        super().__init__("Cette course a changé depuis ta lecture.")
        self.current = current


def record_offer(
    db: Session, *, current_user: User, session_id: UUID, payload: RideOfferCreate, idempotency_key: str,
    now: datetime | None = None,
) -> tuple[RideOfferRead, bool]:
    fingerprint = food_stock.request_hash("rides.offer", {"session_id": str(session_id), **payload.model_dump(mode="json")})
    existing = db.scalar(
        select(RidesOffer).where(RidesOffer.user_id == current_user.id, RidesOffer.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise OfferIdempotencyConflictError("Idempotency key already used with a different offer.")
        return RideOfferRead.model_validate(existing), True
    now = now or datetime.now(UTC)
    offered_at = payload.offered_at or now
    if offered_at > now + CLOCK_SKEW:
        raise OfferInputError("L'heure de la course ne peut pas être dans le futur.")
    session = sessions._active(db, current_user, session_id)
    variables = features(db, session, payload, offered_at)
    rules = ensure_rules(db, current_user)
    signal, fired, reason = evaluate(rules, {
        "pickup_zone_code": payload.pickup_zone_code, "destination_zone_code": payload.destination_zone_code,
        "time_block": variables["time_block"], "ride_type": payload.ride_type,
    })
    # Variables dérivées des règles (doc 57 §5.7) : le modèle apprendra s'il faut les suivre.
    variables.update({f"rule_{rule.rule_code}_triggered": rule.rule_code in fired for rule in rules})
    offer = RidesOffer(
        user_id=current_user.id, session_id=session.id, offered_at=offered_at, source=payload.source, platform=payload.platform,
        price_cents=payload.price_cents, distance_km=payload.distance_km, estimated_duration_min=payload.estimated_duration_min,
        approach_distance_km=payload.approach_distance_km, approach_duration_min=payload.approach_duration_min,
        surge_multiplier=payload.surge_multiplier, pickup_zone=(payload.pickup_zone or "").strip() or None,
        destination_zone=(payload.destination_zone or "").strip() or None, payment_type=payload.payment_type,
        ride_type=payload.ride_type, features=variables, pickup_zone_code=payload.pickup_zone_code,
        destination_zone_code=payload.destination_zone_code, signal=signal, signal_source="rules_only",
        signal_reason=reason, triggered_rules=fired, version=1,
        idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    db.add(offer)
    db.flush()
    db.refresh(offer)
    read = RideOfferRead.model_validate(offer)
    db.commit()
    return read, False


def decide(
    db: Session, *, current_user: User, offer_id: UUID, payload: RideDecisionRequest, now: datetime | None = None
) -> RideOfferRead:
    """Décision de l'utilisateur ; même décision renvoyée = rejeu, correction avec la version lue."""
    offer = _get(db, current_user, offer_id)
    note = (payload.note or "").strip() or None
    if offer.decision == payload.decision and offer.decision_note == note:
        return RideOfferRead.model_validate(offer)
    if offer.version != payload.version:
        raise OfferVersionConflictError(RideOfferRead.model_validate(offer))
    if offer.actual_hourly_rate_cents is not None:
        raise OfferStateError("Le résultat de cette course est déjà enregistré : la décision ne change plus.")
    offer.decision, offer.decided_at, offer.decision_note = payload.decision, now or datetime.now(UTC), note
    offer.version += 1
    db.flush()
    db.add(
        build_event(
            db, user_id=current_user.id, event_type=DECISION_EVENTS[payload.decision],
            payload={"offer_id": str(offer.id), "session_id": str(offer.session_id), "price_cents": offer.price_cents,
                     "hourly_rate_offered_cents": offer.features.get("hourly_rate_offered_cents")},
            idempotency_key=f"{DECISION_EVENTS[payload.decision]}.{offer.id}.v{offer.version}", source_app=SourceApp.vector,
            privacy_level=PrivacyLevel.medium,
        )
    )
    db.refresh(offer)
    read = RideOfferRead.model_validate(offer)
    db.commit()
    return read


def record_outcome(
    db: Session, *, current_user: User, offer_id: UUID, payload: RideOutcomeRequest, request_path: str,
    now: datetime | None = None,
) -> RideOfferRead:
    offer = _get(db, current_user, offer_id)
    if offer.actual_hourly_rate_cents is not None:
        if offer.outcome == _outcome(payload) and offer.actual_earning_cents == payload.actual_earning_cents:
            return RideOfferRead.model_validate(offer)
        raise OfferStateError("Le résultat de cette course est déjà enregistré.")
    if offer.version != payload.version:
        raise OfferVersionConflictError(RideOfferRead.model_validate(offer))
    if offer.decision != "accepted":
        raise OfferStateError("Seule une course acceptée a un résultat.")
    if payload.record_revenue and db.get(RidesSession, offer.session_id).status not in ("active", "paused"):
        raise OfferStateError("Session close : enregistre le résultat avec record_revenue à false, le revenu est déjà au Vault.")
    mobilized = payload.approach_minutes + payload.wait_minutes + payload.ride_minutes + payload.return_minutes
    offer.actual_earning_cents, offer.mobilized_minutes = payload.actual_earning_cents, mobilized
    offer.actual_hourly_rate_cents = int(
        (Decimal(payload.actual_earning_cents) * 60 / Decimal(mobilized)).quantize(Decimal("1"), ROUND_HALF_UP)
    )
    offer.outcome = _outcome(payload)
    offer.version += 1
    db.flush()
    offer_id, session_id = offer.id, offer.session_id
    db.add(
        build_event(
            db, user_id=current_user.id, event_type="rides.ride.completed",
            payload={"offer_id": str(offer_id), "session_id": str(session_id), "earning_cents": payload.actual_earning_cents,
                     "mobilized_minutes": mobilized, "hourly_rate_cents": offer.actual_hourly_rate_cents},
            idempotency_key=f"rides.ride.completed.{offer_id}", source_app=SourceApp.vector, privacy_level=PrivacyLevel.medium,
        )
    )
    pickup_zone = offer.pickup_zone
    db.commit()
    if payload.record_revenue:
        entry = sessions.add_revenue(
            db, current_user=current_user, session_id=session_id,
            payload=ManualRevenueCreate(amount_cents=payload.actual_earning_cents, zone=pickup_zone, wallet=payload.wallet,
                                        occurred_at=now),
            idempotency_key=f"rides.offer.revenue.{offer_id}", request_path=request_path, now=now,
        )
        offer = db.get(RidesOffer, offer_id)
        offer.revenue_transaction_id = entry.transaction_id
        db.commit()
    return RideOfferRead.model_validate(db.get(RidesOffer, offer_id))


def list_offers(db: Session, *, current_user: User, session_id: UUID) -> RideOfferListResponse:
    session = sessions._get(db, current_user, session_id)
    rows = db.scalars(select(RidesOffer).where(RidesOffer.session_id == session.id).order_by(RidesOffer.offered_at))
    return RideOfferListResponse(items=[RideOfferRead.model_validate(row) for row in rows])


def get_offer(db: Session, *, current_user: User, offer_id: UUID) -> RideOfferRead:
    return RideOfferRead.model_validate(_get(db, current_user, offer_id, lock=False))


def training_summary(db: Session, *, current_user: User) -> TrainingSummaryRead:
    counts = {
        decision or "undecided": count
        for decision, count in db.execute(
            select(RidesOffer.decision, func.count()).where(RidesOffer.user_id == current_user.id).group_by(RidesOffer.decision)
        ).all()
    }
    rates = list(db.scalars(
        select(RidesOffer.actual_hourly_rate_cents).where(
            RidesOffer.user_id == current_user.id, RidesOffer.actual_hourly_rate_cents.is_not(None)
        )
    ))
    phase = next((name for limit, name in PHASES if len(rates) < limit), "autonomous")
    needed = next((limit for limit, _ in PHASES if len(rates) < limit), None)
    message = (f"{len(rates)} courses avec résultat réel ; le modèle n'est pas encore entraîné"
               + (f" (phase suivante à {needed})." if needed else "."))
    return TrainingSummaryRead(
        offers=sum(counts.values()), decided=sum(v for k, v in counts.items() if k != "undecided"),
        accepted=counts.get("accepted", 0), refused=counts.get("refused", 0), missed=counts.get("missed", 0),
        with_outcome=len(rates), median_hourly_rate_cents=int(median(rates)) if rates else None, phase=phase, message=message,
    )


# ---------- variables ----------

def features(db: Session, session: RidesSession, payload: RideOfferCreate, offered_at: datetime) -> dict:
    """Variables du doc 57 §5.1, §5.2 (sans culte ni santé) et §5.4, figées au moment de l'offre."""
    local = offered_at.astimezone(PARIS)
    duration = payload.estimated_duration_min
    approach = payload.approach_duration_min
    kpis = sessions._kpis(db, session, offered_at)
    previous = db.scalar(
        select(RidesOffer).where(RidesOffer.session_id == session.id, RidesOffer.decision == "accepted")
        .order_by(RidesOffer.offered_at.desc()).limit(1)
    )
    done = db.scalar(
        select(func.count()).select_from(RidesOffer).where(
            RidesOffer.session_id == session.id, RidesOffer.actual_hourly_rate_cents.is_not(None)
        )
    ) or 0
    return {
        "hourly_rate_offered_cents": round(payload.price_cents * 60 / duration) if duration else None,
        "price_per_km_cents": round(payload.price_cents / float(payload.distance_km)) if payload.distance_km else None,
        "total_ride_time_min": (approach or 0) + duration if duration else None,
        "pickup_zone_key": zone_key(payload.pickup_zone),
        "destination_zone_key": zone_key(payload.destination_zone),
        "hour_of_day": local.hour,
        "day_of_week": local.weekday(),
        "day_of_month": local.day,
        "month": local.month,
        "week_of_year": local.isocalendar().week,
        "is_weekend": local.weekday() >= 5,
        "is_friday_night": local.weekday() == 4 and local.hour >= 22,
        "time_block": _time_block(local.hour),
        "session_rides_done": done,
        "session_elapsed_hours": round(max(0.0, (offered_at - session.started_at).total_seconds()) / 3600, 2),
        "session_revenue_so_far_cents": kpis.revenue_cents,
        "session_target_pct": float(kpis.target_progress) if kpis.target_progress is not None else None,
        "time_since_last_ride_min": int((offered_at - previous.offered_at).total_seconds() // 60) if previous else None,
        "last_ride_destination_zone_key": zone_key(previous.destination_zone) if previous else None,
    }


def _time_block(hour: int) -> str:
    if hour < 6:
        return "night"
    if hour < 10:
        return "morning"
    if hour < 16:
        return "daytime"
    if hour < 20:
        return "evening"
    return "late_evening"


def _outcome(payload: RideOutcomeRequest) -> dict:
    return {"approach_minutes": payload.approach_minutes, "wait_minutes": payload.wait_minutes,
            "ride_minutes": payload.ride_minutes, "return_minutes": payload.return_minutes}


def _get(db: Session, user: User, offer_id: UUID, *, lock: bool = True) -> RidesOffer:
    query = select(RidesOffer).where(RidesOffer.id == offer_id, RidesOffer.user_id == user.id)
    offer = db.scalar(query.with_for_update() if lock else query)
    if offer is None:
        raise OfferNotFoundError("Course introuvable.")
    return offer
