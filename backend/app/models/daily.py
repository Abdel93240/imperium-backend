"""Daily orchestrator tables (spec Daily §3.1, §3.3 ; CHECK constraints live in migration 0104)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, UUIDPrimaryKeyMixin


class MissionDependency(UUIDPrimaryKeyMixin, Base):
    """Arête parent → enfant ; `hard` = porte G2, sinon simple préférence d'ordre."""

    __tablename__ = "mission_dependencies"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    parent_mission_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("imperium_missions.id", ondelete="CASCADE"), nullable=False
    )
    child_mission_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("imperium_missions.id", ondelete="CASCADE"), nullable=False
    )
    hard: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DailySelectionLog(UUIDPrimaryKeyMixin, Base):
    """Trace d'audit d'une sélection : chaque mission refusée porte la porte qui l'a bloquée."""

    __tablename__ = "daily_selection_log"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_ref: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    at_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    remaining_min: Mapped[int] = mapped_column(Integer, nullable=False)
    next_fixed_ref: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    next_fixed_kind: Mapped[str | None] = mapped_column(Text, nullable=True)  # mission | calendar_event
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    feasible_set: Mapped[list] = mapped_column(JSONB, nullable=False)
    mandatory_set: Mapped[list] = mapped_column(JSONB, nullable=False)
    chosen_mission_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("imperium_missions.id", ondelete="SET NULL"), nullable=True
    )
    tiebreak_applied: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    pulled_forward: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DailyOverride(UUIDPrimaryKeyMixin, Base):
    """L'utilisateur prend une autre mission que la proposée : raison obligatoire, contexte figé (§3.4)."""

    __tablename__ = "daily_overrides"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    selection_log_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("daily_selection_log.id"), nullable=False
    )
    proposed_mission_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("imperium_missions.id"), nullable=False
    )
    chosen_mission_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("imperium_missions.id"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
