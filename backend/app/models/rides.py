"""Sessions VTC (Vector, doc 13, doc 59 §14) : domaine `rides` (doc 77, jamais `vtc.*`).

Vector conseille et mesure ; il n'accepte ni ne refuse aucune course à la place de
l'utilisateur. Les revenus et dépenses d'une session sont des transactions Vault
(source vector_manual) reliées par `external_ref` ; la session ne garde que son cadre.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, Text, text
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
