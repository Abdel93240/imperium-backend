"""Sessions VTC (Vector, doc 13, doc 59 §14) : domaine `rides` (doc 77, jamais `vtc.*`).

Vector conseille et mesure ; il n'accepte ni ne refuse aucune course à la place de
l'utilisateur. Les revenus et dépenses d'une session sont des transactions Vault
(source vector_manual) reliées par `external_ref` ; la session ne garde que son cadre.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, UUIDPrimaryKeyMixin


class RidesSession(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rides_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'completed')", name="status_check"),
        CheckConstraint("target_ca_cents IS NULL OR target_ca_cents BETWEEN 1 AND 10000000", name="target_range"),
        CheckConstraint("status <> 'completed' OR ended_at IS NOT NULL", name="completed_has_end"),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("rides_sessions_one_active_idx", "user_id", unique=True, postgresql_where=text("status = 'active'")),
        Index("rides_sessions_user_started_idx", "user_id", "started_at"),
        Index("rides_sessions_user_idempotency_idx", "user_id", "idempotency_key", unique=True),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active", server_default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    target_ca_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strategic_direction: Mapped[str | None] = mapped_column(Text, nullable=True)
    mission_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("imperium_missions.id", ondelete="SET NULL"), nullable=True
    )
    final_revenue_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_expense_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class RidesDropZone(UUIDPrimaryKeyMixin, Base):
    """Dépose confirmée par l'utilisateur (VEC-10) : donnée d'apprentissage des zones."""

    __tablename__ = "rides_drop_zones"
    __table_args__ = (
        CheckConstraint("length(btrim(zone)) BETWEEN 1 AND 120", name="zone_length"),
        CheckConstraint("(latitude IS NULL) = (longitude IS NULL)", name="coordinates_pair"),
        CheckConstraint("gps_confidence IS NULL OR gps_confidence BETWEEN 0 AND 1", name="confidence_range"),
        CheckConstraint("real_duration_minutes IS NULL OR real_duration_minutes BETWEEN 1 AND 600", name="duration_range"),
        Index("rides_drop_zones_session_idx", "session_id", "recorded_at"),
        Index("rides_drop_zones_user_idempotency_idx", "user_id", "idempotency_key", unique=True),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("rides_sessions.id", ondelete="CASCADE"), nullable=False
    )
    zone: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    gps_confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    real_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)


class RidesRevenueEntry(UUIDPrimaryKeyMixin, Base):
    """Revenu saisi en session avec sa zone (VEC-04) : la transaction reste au Vault, ici le contexte VTC."""

    __tablename__ = "rides_revenue_entries"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        Index("rides_revenue_entries_user_occurred_idx", "user_id", "occurred_at"),
        Index("rides_revenue_entries_transaction_idx", "transaction_id", unique=True),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("rides_sessions.id", ondelete="CASCADE"), nullable=False
    )
    transaction_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)  # sans FK : registre Vault
    zone: Mapped[str | None] = mapped_column(Text, nullable=True)
    zone_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RidesRecommendation(UUIDPrimaryKeyMixin, Base):
    """« Où aller ? » (VEC-07) : conseil déterministe sur l'historique, avec sa raison et le retour de l'utilisateur."""

    __tablename__ = "rides_recommendations"
    __table_args__ = (
        CheckConstraint("recommendation IN ('stay_here', 'move_to_zone', 'abstain')", name="recommendation_check"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
        CheckConstraint(
            "ride_user_action IS NULL OR ride_user_action IN ('accepted', 'refused', 'missed', 'ignored')",
            name="ride_user_action_check",
        ),
        CheckConstraint("(feedback_at IS NULL) = (feedback_useful IS NULL)", name="feedback_complete"),
        Index("rides_recommendations_user_requested_idx", "user_id", "requested_at"),
        Index("rides_recommendations_user_idempotency_idx", "user_id", "idempotency_key", unique=True),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("rides_sessions.id", ondelete="SET NULL"), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_zone: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    zone: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    inputs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    feedback_useful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ride_user_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)


RIDE_DECISIONS = ("accepted", "refused", "missed")


class RidesOffer(UUIDPrimaryKeyMixin, Base):
    """Course proposée pendant une session (doc 57 §5, §11) : variables, décision de l'utilisateur, résultat réel.

    La décision est gardée comme donnée de comportement, jamais comme cible d'apprentissage
    (doc 33 §8) ; la cible est le gain réel ÷ temps mobilisé, à la minute.
    """

    __tablename__ = "rides_offers"
    __table_args__ = (
        CheckConstraint("price_cents BETWEEN 1 AND 1000000", name="price_range"),
        CheckConstraint("platform IN ('bolt', 'uber', 'heetch', 'other')", name="platform_check"),
        CheckConstraint("ride_type IN ('immediate', 'scheduled')", name="ride_type_check"),
        CheckConstraint("source IN ('manual', 'ocr')", name="source_check"),
        CheckConstraint(f"decision IS NULL OR decision IN ({', '.join(repr(d) for d in RIDE_DECISIONS)})", name="decision_check"),
        CheckConstraint("(decision IS NULL) = (decided_at IS NULL)", name="decision_has_time"),
        CheckConstraint("actual_hourly_rate_cents IS NULL OR decision = 'accepted'", name="outcome_only_accepted"),
        CheckConstraint("mobilized_minutes IS NULL OR mobilized_minutes > 0", name="mobilized_positive"),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("rides_offers_session_idx", "session_id", "offered_at"),
        Index("rides_offers_user_offered_idx", "user_id", "offered_at"),
        Index("rides_offers_user_idempotency_idx", "user_id", "idempotency_key", unique=True),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("rides_sessions.id", ondelete="CASCADE"), nullable=False
    )
    offered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_km: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    estimated_duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approach_distance_km: Mapped[float | None] = mapped_column(Numeric(7, 2), nullable=True)
    approach_duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    surge_multiplier: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    pickup_zone: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_zone: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    ride_type: Mapped[str] = mapped_column(Text, nullable=False)
    features: Mapped[dict] = mapped_column(JSONB, nullable=False)
    decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    actual_earning_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mobilized_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_hourly_rate_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    revenue_transaction_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
