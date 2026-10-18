"""« Où aller ? » (VEC-07–VEC-09, doc 33 §5) : recommandation de zone déterministe.

Base : les revenus saisis en session avec leur zone, sur les 90 derniers jours, au même
créneau (heure ± 1, semaine ou week-end, heure de Paris). Une transaction annulée au Vault
ne compte pas. Une zone n'est comparée qu'avec au moins 5 courses sur au moins 2 sessions.

Décision :
- aucune zone comparable → abstention, « Haute incertitude, à toi de juger. » (doc 33 §4.1) ;
- la meilleure zone est la zone actuelle, ou ne fait pas au moins 15 % de mieux → rester ;
- sinon → aller vers la meilleure zone.
La confiance reste plafonnée à 0,6 : événements, trains, aéroports et trafic ne sont pas
encore lus, et la raison le dit. Pas de taux horaire : le temps passé par zone n'est pas
mesuré. Vector ne lit ni fatigue, ni pression, ni objectif global (doc 13 §5).
"""

from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.rides import RidesRecommendation, RidesRevenueEntry, RidesSession
from app.models.vault import ImperiumVaultTransaction
from app.schemas.rides import RecommendationFeedback, RecommendationRead, RecommendationRequest, ZoneStatRead
from app.services.events.emitter import build_event
from app.services.pulse import food_stock
from app.services.vector.scoring import VECTOR_ABSTENTION_MESSAGE
from app.services.vector.zones import zone_key

PARIS = ZoneInfo("Europe/Paris")
HISTORY_DAYS = 90
MIN_RIDES = 5
MIN_SESSIONS = 2
MOVE_GAIN = Decimal("1.15")
MAX_CONFIDENCE = Decimal("0.60")
MISSING_CONTEXT = ["events", "rail", "airport", "traffic"]
MISSING_NOTE = "Événements, trains, aéroports et trafic non pris en compte."


class RecommendationNotFoundError(ValueError):
    pass


class RecommendationIdempotencyConflictError(ValueError):
    pass


class RecommendationFeedbackConflictError(ValueError):
    def __init__(self, current: RecommendationRead) -> None:
        super().__init__("Un retour est déjà enregistré pour cette recommandation.")
        self.current = current


def recommend(
    db: Session, *, current_user: User, payload: RecommendationRequest, idempotency_key: str, now: datetime | None = None
) -> tuple[RecommendationRead, bool]:
    fingerprint = food_stock.request_hash("rides.recommendation", payload.model_dump(mode="json"))
    existing = db.scalar(
        select(RidesRecommendation).where(
            RidesRecommendation.user_id == current_user.id, RidesRecommendation.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise RecommendationIdempotencyConflictError("Idempotency key already used with a different request.")
        return _read(existing), True
    now = now or datetime.now(UTC)
    local = now.astimezone(PARIS)
    weekend = local.weekday() >= 5
    hours = {(local.hour + delta) % 24 for delta in (-1, 0, 1)}
    stats = _zone_stats(db, current_user, now, weekend, hours)
    current = (payload.current_zone or "").strip() or None
    decision, zone, reason, confidence = _decide(stats, current)
    session = db.scalar(select(RidesSession.id).where(RidesSession.user_id == current_user.id, RidesSession.status == "active"))
    slot = f"{'week-end' if weekend else 'semaine'}, {(local.hour - 1) % 24} h–{(local.hour + 2) % 24} h"
    row = RidesRecommendation(
        user_id=current_user.id, session_id=session, requested_at=now, current_zone=current, recommendation=decision,
        zone=zone, reason=reason, confidence=confidence,
        inputs={"slot": slot, "zones": [stat.model_dump() for stat in stats[:5]], "missing_context": MISSING_CONTEXT,
                "history_days": HISTORY_DAYS},
        idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    db.add(
        build_event(
            db, user_id=current_user.id, event_type="rides.zone.recommended",
            payload={"recommendation_id": str(row.id), "recommendation": decision, "zone": zone,
                     "confidence": str(confidence), "session_id": str(session) if session else None},
            idempotency_key=f"rides.zone.recommended.{row.id}", source_app=SourceApp.vector, privacy_level=PrivacyLevel.medium,
        )
    )
    read = _read(row)
    db.commit()
    return read, False


def latest(db: Session, *, current_user: User) -> RecommendationRead | None:
    row = db.scalar(
        select(RidesRecommendation).where(RidesRecommendation.user_id == current_user.id)
        .order_by(RidesRecommendation.requested_at.desc()).limit(1)
    )
    return _read(row) if row else None


def get(db: Session, *, current_user: User, recommendation_id: UUID) -> RecommendationRead:
    return _read(_get(db, current_user, recommendation_id))


def record_feedback(
    db: Session, *, current_user: User, recommendation_id: UUID, payload: RecommendationFeedback, now: datetime | None = None
) -> RecommendationRead:
    """Un retour par recommandation ; le même retour renvoyé est accepté tel quel."""
    row = _get(db, current_user, recommendation_id, lock=True)
    reason = (payload.reason or "").strip() or None
    if row.feedback_at is not None:
        if (row.feedback_useful, row.ride_user_action, row.feedback_reason) == (payload.useful, payload.ride_user_action, reason):
            return _read(row)
        raise RecommendationFeedbackConflictError(_read(row))
    row.feedback_useful, row.ride_user_action, row.feedback_reason = payload.useful, payload.ride_user_action, reason
    row.feedback_at = now or datetime.now(UTC)
    db.flush()
    db.add(
        build_event(
            db, user_id=current_user.id, event_type="rides.recommendation.feedback_recorded",
            payload={"recommendation_id": str(row.id), "useful": payload.useful, "ride_user_action": payload.ride_user_action},
            idempotency_key=f"rides.recommendation.feedback_recorded.{row.id}", source_app=SourceApp.vector,
            privacy_level=PrivacyLevel.medium,
        )
    )
    read = _read(row)
    db.commit()
    return read


# ---------- calcul ----------

def _zone_stats(db: Session, user: User, now: datetime, weekend: bool, hours: set[int]) -> list[ZoneStatRead]:
    reversal = aliased(ImperiumVaultTransaction)
    rows = db.execute(
        select(RidesRevenueEntry.zone, RidesRevenueEntry.zone_key, RidesRevenueEntry.session_id, RidesRevenueEntry.amount_cents,
               RidesRevenueEntry.occurred_at)
        .where(
            RidesRevenueEntry.user_id == user.id, RidesRevenueEntry.zone_key.is_not(None),
            RidesRevenueEntry.occurred_at >= now - timedelta(days=HISTORY_DAYS), RidesRevenueEntry.occurred_at <= now,
            ~select(reversal.id).where(reversal.reversal_of_transaction_id == RidesRevenueEntry.transaction_id).exists(),
        )
    ).all()
    amounts: dict[str, list[int]] = defaultdict(list)
    sessions: dict[str, set] = defaultdict(set)
    labels: dict[str, Counter] = defaultdict(Counter)
    for zone, key, session_id, amount, occurred_at in rows:
        local = occurred_at.astimezone(PARIS)
        if (local.weekday() >= 5) != weekend or local.hour not in hours:
            continue
        amounts[key].append(amount)
        sessions[key].add(session_id)
        labels[key][zone] += 1
    stats = [
        ZoneStatRead(zone=labels[key].most_common(1)[0][0], rides=len(values), sessions=len(sessions[key]),
                     average_ride_cents=round(sum(values) / len(values)))
        for key, values in amounts.items()
        if len(values) >= MIN_RIDES and len(sessions[key]) >= MIN_SESSIONS
    ]
    return sorted(stats, key=lambda stat: (-stat.average_ride_cents, -stat.rides, stat.zone))


def _decide(stats: list[ZoneStatRead], current: str | None) -> tuple[str, str | None, str, Decimal]:
    if not stats:
        return "abstain", None, f"{VECTOR_ABSTENTION_MESSAGE} Pas assez de courses notées à ce créneau.", Decimal("0.00")
    best = stats[0]
    confidence = min(MAX_CONFIDENCE, Decimal(best.rides) / Decimal(40)).quantize(Decimal("0.01"))
    here = next((stat for stat in stats if zone_key(stat.zone) == zone_key(current)), None) if current else None
    evidence = f"{best.rides} courses notées à ce créneau, {_euros(best.average_ride_cents)} en moyenne."
    if here is not None and (here is best or Decimal(best.average_ride_cents) < Decimal(here.average_ride_cents) * MOVE_GAIN):
        return ("stay_here", here.zone,
                f"Rester à {here.zone} : {here.rides} courses notées à ce créneau, {_euros(here.average_ride_cents)} en moyenne. "
                f"{MISSING_NOTE}", confidence)
    return "move_to_zone", best.zone, f"Aller vers {best.zone} : {evidence} {MISSING_NOTE}", confidence


def _euros(cents: int) -> str:
    return f"{Decimal(cents) / 100:.2f} €".replace(".", ",")


def _read(row: RidesRecommendation) -> RecommendationRead:
    return RecommendationRead(
        id=row.id, session_id=row.session_id, requested_at=row.requested_at, current_zone=row.current_zone,
        recommendation=row.recommendation, zone=row.zone, reason=row.reason, confidence=row.confidence,
        hourly_rate_estimate_cents=None, slot=row.inputs["slot"], zones=[ZoneStatRead(**zone) for zone in row.inputs["zones"]],
        missing_context=row.inputs["missing_context"], feedback_useful=row.feedback_useful,
        ride_user_action=row.ride_user_action, feedback_reason=row.feedback_reason, feedback_at=row.feedback_at,
    )


def _get(db: Session, user: User, recommendation_id: UUID, *, lock: bool = False) -> RidesRecommendation:
    query = select(RidesRecommendation).where(
        RidesRecommendation.id == recommendation_id, RidesRecommendation.user_id == user.id
    )
    row = db.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise RecommendationNotFoundError("Recommandation introuvable.")
    return row
