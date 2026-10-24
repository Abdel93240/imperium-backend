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

import math
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
from app.services.vector import calendar, drops, economics, events, feeds, geo, grid, priority, school, sessions, weather
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
    # L'arrivée d'une offre Bolt n'a presque jamais de code postal : la commune ou le quartier lu le donne.
    places = {side: geo.resolve(getattr(payload, f"{side}_address") or getattr(payload, f"{side}_zone"))
              for side in ("pickup", "destination")}
    sources = {side: "read" if getattr(payload, f"{side}_zone_code") else ("resolved" if places[side] and places[side].postal_code
                                                                          else None) for side in places}
    payload = payload.model_copy(update={
        f"{side}_zone_code": getattr(payload, f"{side}_zone_code") or (places[side].postal_code if places[side] else None)
        for side in places
    })
    variables = features(db, session, payload, offered_at, places=places)
    variables.update({"pickup_code_source": sources["pickup"], "destination_code_source": sources["destination"]})
    rules = ensure_rules(db, current_user)
    signal, fired, reason = evaluate(rules, {
        "pickup_zone_code": payload.pickup_zone_code, "destination_zone_code": payload.destination_zone_code,
        "destination_department": places["destination"].department if places["destination"] else None,
        "time_block": variables["time_block"], "ride_type": payload.ride_type,
    })
    # Variables dérivées des règles (doc 57 §5.7) : le modèle apprendra s'il faut les suivre.
    variables.update({f"rule_{rule.rule_code}_triggered": rule.rule_code in fired for rule in rules})
    # Règle économique (décision utilisateur 2026-10-23) : €/h global et note de la zone d'arrivée. Une règle rouge
    # l'emporte (prudence) ; sinon le verdict économique ; sans durée lue, la règle verte éventuelle ; sinon aucun avis.
    economic = economics.verdict(db, price_cents=payload.price_cents, approach_min=payload.approach_duration_min,
                                 trip_min=payload.estimated_duration_min, destination=places["destination"],
                                 offered_at=offered_at, destination_text=payload.destination_address)
    variables.update(economic.features)
    source = "rules_only"
    if signal != "red" and economic.signal is not None:
        signal, reason, source = economic.signal, economic.reason, "economic"
    offer = RidesOffer(
        user_id=current_user.id, session_id=session.id, offered_at=offered_at, source=payload.source, platform=payload.platform,
        price_cents=payload.price_cents, distance_km=payload.distance_km, estimated_duration_min=payload.estimated_duration_min,
        approach_distance_km=payload.approach_distance_km, approach_duration_min=payload.approach_duration_min,
        surge_multiplier=payload.surge_multiplier, pickup_zone=(payload.pickup_zone or "").strip() or None,
        destination_zone=(payload.destination_zone or "").strip() or None, payment_type=payload.payment_type,
        ride_type=payload.ride_type, features=variables, pickup_zone_code=payload.pickup_zone_code,
        destination_zone_code=payload.destination_zone_code, signal=signal,
        pickup_address=(payload.pickup_address or "").strip() or None,
        destination_address=(payload.destination_address or "").strip() or None, signal_source=source,
        signal_reason=reason, triggered_rules=fired, version=1,
        idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    db.add(offer)
    db.flush()
    drops.on_offer(db, session.id, offered_at)  # attente depuis la dernière dépose
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
    mobilized = max(1, payload.approach_minutes + payload.wait_minutes + payload.ride_minutes + payload.return_minutes)
    offer.actual_earning_cents, offer.mobilized_minutes = payload.actual_earning_cents, mobilized
    offer.actual_hourly_rate_cents = int(
        (Decimal(payload.actual_earning_cents) * 60 / Decimal(mobilized)).quantize(Decimal("1"), ROUND_HALF_UP)
    )
    offer.outcome = _outcome(payload)
    offer.version += 1
    db.flush()
    # Mesure après dépose : ferme celle qui attendait cette course, ouvre celle de sa propre dépose. Une annulation
    # payée n'a pas de dépose : aucune mesure de zone ne part de là.
    timeline = payload.timeline or {}
    if not payload.cancelled:
        drops.on_outcome(db, offer, accepted_at=timeline.get("accepted"), ended_at=timeline.get("ended") or now or datetime.now(UTC),
                         dropoff=(float(payload.dropoff_lat), float(payload.dropoff_lng))
                         if payload.dropoff_lat is not None and payload.dropoff_lng is not None else None)
    offer_id, session_id = offer.id, offer.session_id
    db.add(
        build_event(
            db, user_id=current_user.id, event_type="rides.ride.completed",
            payload={"offer_id": str(offer_id), "session_id": str(session_id), "earning_cents": payload.actual_earning_cents,
                     "mobilized_minutes": mobilized, "hourly_rate_cents": offer.actual_hourly_rate_cents,
                     "cancelled": payload.cancelled},
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

def features(db: Session, session: RidesSession, payload: RideOfferCreate, offered_at: datetime,
             places: dict | None = None) -> dict:
    """Variables du doc 57 §5.1, §5.2 (sans culte ni santé) et §5.4, figées au moment de l'offre."""
    places = places or {}
    pickup_place, dest_place = places.get("pickup"), places.get("destination")
    local = offered_at.astimezone(PARIS)
    cell = (weather.cell_at(float(payload.driver_lat), float(payload.driver_lng)).code
            if payload.driver_lat is not None and payload.driver_lng is not None else None)
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
        "last_ride_hourly_rate_cents": previous.actual_hourly_rate_cents if previous else None,
        # Majoration sous toutes ses formes, péage, gamme, paiement (doc 57 §5.1).
        "surge_multiplier": float(payload.surge_multiplier) if payload.surge_multiplier is not None else None,
        "surge_percent": payload.surge_percent,
        "surge_bonus_cents": payload.surge_bonus_cents,
        "has_surge": any(v is not None for v in (payload.surge_multiplier, payload.surge_percent, payload.surge_bonus_cents)),
        "toll_cents": payload.toll_cents,
        "ride_class": payload.ride_class,
        "payment_type": payload.payment_type,
        # Zones (doc 57 §5.3) depuis les codes postaux ; position de la tablette à l'offre.
        **_area("pickup", payload.pickup_zone_code),
        **_area("dest", payload.destination_zone_code),
        "driver_lat": float(payload.driver_lat) if payload.driver_lat is not None else None,
        "driver_lng": float(payload.driver_lng) if payload.driver_lng is not None else None,
        # Case de la grille où se trouve la tablette (découpage commun météo, Priority, majoration).
        "zone_cell": cell,
        # Découpage fin (zones 1 / 3 / 10 km², créneaux de 10 min) : où est la tablette, où arrive la course, quand.
        "driver_zone": grid.zone_at(float(payload.driver_lat), float(payload.driver_lng)).code
        if payload.driver_lat is not None and payload.driver_lng is not None else None,
        "dest_zone": grid.zone_at(dest_place.lat, dest_place.lng).code if dest_place else None,
        "slot_10min": grid.slot_of(offered_at),
        "day_type": grid.day_type(offered_at),
        # Perturbations IDFM, trafic TomTom, avions OpenSky : Île-de-France, autour de la tablette, autour de l'arrivée.
        **feeds.context(db, offered_at, {
            "pickup": (float(payload.driver_lat), float(payload.driver_lng))
            if payload.driver_lat is not None and payload.driver_lng is not None else None,
            "dest": (dest_place.lat, dest_place.lng) if dest_place else None,
        }),
        # Course Priority (le client paie plus pour être pris vite) et propension de la zone à cette heure.
        "is_priority": payload.is_priority,
        **priority.history_features(db, session.user_id, cell=cell, hour=local.hour, at=offered_at),
        # Calendrier (doc 57 §5.2) : jours fériés calculés ; vacances scolaires (zone C) relevées.
        "is_public_holiday": calendar.is_public_holiday(local.date()),
        "is_eve_of_holiday": calendar.is_public_holiday(local.date() + timedelta(days=1)),
        **dict(zip(("is_school_holiday", "school_holiday_label"), school.holiday_on(db, local.date()), strict=True)),
        # Événements, fermetures, travaux du scan web hebdomadaire (doc 57 §5.6) ; vides avant le premier scan.
        **events.offer_features(db, offered_at, pickup_code=payload.pickup_zone_code,
                                destination_code=payload.destination_zone_code),
        # Lieux résolus (commune ou quartier) : centre de la commune ou de l'arrondissement (doc 57 §5.3).
        "pickup_lat": pickup_place.lat if pickup_place else None, "pickup_lng": pickup_place.lng if pickup_place else None,
        "dest_lat": dest_place.lat if dest_place else None, "dest_lng": dest_place.lng if dest_place else None,
        "dest_department": dest_place.department if dest_place else None,
        "dest_zone_cell": weather.cell_at(dest_place.lat, dest_place.lng).code if dest_place else None,
        "distance_paris_center_km": round(_km(dest_place.lat, dest_place.lng, 48.8566, 2.3522), 1) if dest_place else None,
        # Météo de l'heure de l'offre (doc 57 §5.5) : case de la tablette, case d'arrivée, Paris, part sous la pluie.
        **weather.offer_features(db, offered_at, lat=float(payload.driver_lat) if payload.driver_lat is not None else None,
                                 lng=float(payload.driver_lng) if payload.driver_lng is not None else None,
                                 dest=(dest_place.lat, dest_place.lng) if dest_place else None),
    }


def _area(side: str, code: str | None) -> dict:
    """Paris, petite couronne (92, 93, 94), grande couronne (77, 78, 91, 95) ; inconnu sans code postal."""
    prefix = code[:2] if code else None
    known = prefix is not None
    return {
        f"{side}_in_paris": prefix == "75" if known else None,
        f"{side}_in_petite_couronne": prefix in ("92", "93", "94") if known else None,
        f"{side}_in_grande_couronne": prefix in ("77", "78", "91", "95") if known else None,
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
    """Temps mobilisé, et s'ils ont été relevés par l'assistant : étapes datées, positions, paiement, source du prix."""
    out = {"approach_minutes": payload.approach_minutes, "wait_minutes": payload.wait_minutes,
           "ride_minutes": payload.ride_minutes, "return_minutes": payload.return_minutes}
    if payload.timeline:
        out["timeline"] = {stage: at.isoformat() for stage, at in payload.timeline.items()}
    for key in ("pickup_lat", "pickup_lng", "dropoff_lat", "dropoff_lng"):
        if (value := getattr(payload, key)) is not None:
            out[key] = float(value)
    if payload.dropoff_lat is not None and payload.dropoff_lng is not None:
        out["dropoff_zone_cell"] = weather.cell_at(float(payload.dropoff_lat), float(payload.dropoff_lng)).code
    if payload.payment:
        out["payment"] = payload.payment
    if payload.cancelled:
        out["cancelled"] = True
    if payload.price_source:
        out["price_source"] = payload.price_source
    return out


def _km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dlat, dlng = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def _get(db: Session, user: User, offer_id: UUID, *, lock: bool = True) -> RidesOffer:
    query = select(RidesOffer).where(RidesOffer.id == offer_id, RidesOffer.user_id == user.id)
    offer = db.scalar(query.with_for_update() if lock else query)
    if offer is None:
        raise OfferNotFoundError("Course introuvable.")
    return offer
