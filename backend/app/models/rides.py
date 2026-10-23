"""Sessions VTC (Vector, doc 13, doc 59 §14) : domaine `rides` (doc 77, jamais `vtc.*`).

Vector conseille et mesure ; il n'accepte ni ne refuse aucune course à la place de
l'utilisateur. Les revenus et dépenses d'une session sont des transactions Vault
(source vector_manual) reliées par `external_ref` ; la session ne garde que son cadre.
"""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, SmallInteger, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, UUIDPrimaryKeyMixin


class RidesSession(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rides_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'paused', 'completed')", name="status_check"),
        CheckConstraint("(status = 'paused') = (paused_at IS NOT NULL)", name="paused_has_time"),
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
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # pause en cours (0137)
    paused_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")  # pauses finies
    target_ca_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    strategic_direction: Mapped[str | None] = mapped_column(Text, nullable=True)
    mission_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("imperium_missions.id", ondelete="SET NULL"), nullable=True
    )
    final_revenue_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_expense_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Replan Imperium demandé par l'utilisateur après la clôture (VEC-11) ; sans clé étrangère.
    replan_event_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
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
        CheckConstraint("source IN ('manual', 'ocr', 'assistant')", name="source_check"),
        CheckConstraint(f"decision IS NULL OR decision IN ({', '.join(repr(d) for d in RIDE_DECISIONS)})", name="decision_check"),
        CheckConstraint("(decision IS NULL) = (decided_at IS NULL)", name="decision_has_time"),
        CheckConstraint("actual_hourly_rate_cents IS NULL OR decision = 'accepted'", name="outcome_only_accepted"),
        CheckConstraint("mobilized_minutes IS NULL OR mobilized_minutes > 0", name="mobilized_positive"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("signal IS NULL OR signal IN ('green', 'red')", name="signal_check"),
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
    pickup_zone_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_zone_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    pickup_address: Mapped[str | None] = mapped_column(Text, nullable=True)  # adresse lue sur l'offre, rue comprise
    destination_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    signal: Mapped[str | None] = mapped_column(Text, nullable=True)
    signal_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    signal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_rules: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)


class RidesBusinessRule(UUIDPrimaryKeyMixin, Base):
    """Règle métier de l'utilisateur (doc 57 §4) : point de départ, révisable, jamais un verdict définitif."""

    __tablename__ = "rides_business_rules"
    __table_args__ = (
        UniqueConstraint("user_id", "rule_code", name="rides_business_rules_user_code_unique"),
        CheckConstraint("action IN ('red', 'green')", name="action_check"),
        CheckConstraint("version >= 1", name="version_positive"),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rule_code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    conditions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_hard_rule: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    times_applied: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    revision_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_revised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RidesRuleRevision(UUIDPrimaryKeyMixin, Base):
    """Révision d'une règle (doc 57 §4.12, §10) : avant / après, raison, validée par l'utilisateur."""

    __tablename__ = "rides_rule_revisions"
    __table_args__ = (
        CheckConstraint("revision_type IN ('disabled', 'enabled', 'modified', 'hardened', 'softened')", name="revision_type_check"),
        CheckConstraint("proposed_by IN ('user_manual', 'weekly_review', 'auto_threshold')", name="proposed_by_check"),
        Index("rides_rule_revisions_rule_idx", "rule_id", "revised_at"),
    )

    rule_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("rides_business_rules.id", ondelete="CASCADE"), nullable=False
    )
    revised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revision_type: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    previous: Mapped[dict] = mapped_column(JSONB, nullable=False)
    new: Mapped[dict] = mapped_column(JSONB, nullable=False)
    proposed_by: Mapped[str] = mapped_column(Text, nullable=False)
    user_validated: Mapped[bool] = mapped_column(Boolean, nullable=False)


class RidesWeatherCellReading(UUIDPrimaryKeyMixin, Base):
    """Relevé météo d'une case de la grille (Open-Meteo, Météo-France) : pluie au quart d'heure (doc 57 §5.5, §17)."""

    __tablename__ = "rides_weather_cell_readings"
    __table_args__ = (
        CheckConstraint("ring IN ('A', 'B', 'airport')", name="ring_check"),
        Index("rides_weather_cell_readings_fetched_idx", text("fetched_at DESC")),
        Index("rides_weather_cell_readings_cell_idx", "cell_code", text("fetched_at DESC")),
    )

    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cell_code: Mapped[str] = mapped_column(Text, nullable=False)
    ring: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[float] = mapped_column(Numeric(8, 5), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(8, 5), nullable=False)
    current: Mapped[dict] = mapped_column(JSONB, nullable=False)
    minutely: Mapped[dict] = mapped_column(JSONB, nullable=False)


class RidesSchoolHoliday(UUIDPrimaryKeyMixin, Base):
    """Période de vacances scolaires (zone C, Paris) ; `end_day` est le jour de reprise, exclu."""

    __tablename__ = "rides_school_holidays"
    __table_args__ = (
        UniqueConstraint("zone", "label", "start_day", name="period_unique"),
        CheckConstraint("end_day >= start_day", name="period_order"),
    )

    label: Mapped[str] = mapped_column(Text, nullable=False)
    zone: Mapped[str] = mapped_column(Text, nullable=False)
    school_year: Mapped[str] = mapped_column(Text, nullable=False)
    start_day: Mapped[date] = mapped_column(Date, nullable=False)
    end_day: Mapped[date] = mapped_column(Date, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RidesEventScan(UUIDPrimaryKeyMixin, Base):
    """Un passage du scan web hebdomadaire `vector.event_scan` (doc 31 §10)."""

    __tablename__ = "rides_event_scans"
    __table_args__ = (CheckConstraint("status IN ('running', 'done', 'failed')", name="status_check"),)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    items: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class RidesEventSignal(UUIDPrimaryKeyMixin, Base):
    """Événement, fermeture routière ou travaux trouvés par le scan web ; signal passif (doc 31 §10)."""

    __tablename__ = "rides_event_signals"
    __table_args__ = (
        CheckConstraint("kind IN ('event', 'road_closure', 'rail_works')", name="kind_check"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="confidence_range"),
        CheckConstraint("ends_at IS NULL OR ends_at >= starts_at", name="period_order"),
        UniqueConstraint("fingerprint", name="fingerprint_unique"),
        Index("rides_event_signals_window_idx", "starts_at", "ends_at"),
    )

    scan_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rides_event_scans.id", ondelete="CASCADE"),
                                          nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    venue: Mapped[str | None] = mapped_column(Text, nullable=True)
    commune: Mapped[str | None] = mapped_column(Text, nullable=True)
    postal_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    road: Mapped[str | None] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_attendance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Numeric(3, 2), nullable=False)
    fingerprint: Mapped[str] = mapped_column(Text, nullable=False)


class RidesZoneScore(UUIDPrimaryKeyMixin, Base):
    """Note d'une zone (0 à 10) posée par l'utilisateur : code postal ou département, par créneau (ou « all »)."""

    __tablename__ = "rides_zone_scores"
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 10", name="score_range"),
        CheckConstraint("time_block IN ('night', 'morning', 'daytime', 'evening', 'late_evening', 'all')",
                        name="time_block_check"),
        UniqueConstraint("zone_key", "time_block", name="zone_block_unique"),
    )

    zone_key: Mapped[str] = mapped_column(Text, nullable=False)
    time_block: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Numeric(3, 1), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class RidesDropObservation(UUIDPrimaryKeyMixin, Base):
    """Après une dépose : attente, offres vues, course suivante, €/h du cycle — par zone fine et créneau de 10 min."""

    __tablename__ = "rides_drop_observations"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'closed', 'interrupted')", name="status_check"),
        CheckConstraint("slot BETWEEN 0 AND 143", name="slot_range"),
        UniqueConstraint("offer_id", name="offer_unique"),
        Index("rides_drop_observations_open_idx", "session_id", postgresql_where=text("status = 'open'")),
        Index("rides_drop_observations_zone_idx", "zone_code", "day_type", "slot"),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rides_sessions.id", ondelete="CASCADE"),
                                             nullable=False)
    offer_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("rides_offers.id", ondelete="CASCADE"),
                                           nullable=False)
    dropped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    drop_lat: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    drop_lng: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    zone_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    zone_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    slot: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    day_type: Mapped[str] = mapped_column(Text, nullable=False)
    school_holiday: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    next_offer_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    wait_first_offer_min: Mapped[float | None] = mapped_column(Numeric(6, 1), nullable=True)
    offers_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_offer_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    next_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    wait_to_accept_min: Mapped[float | None] = mapped_column(Numeric(6, 1), nullable=True)
    next_earning_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_mobilized_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cycle_hourly_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open", server_default="open")
    closed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
