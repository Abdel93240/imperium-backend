"""Règles rouges Pulse (spec Pulse §3.5, §11 ; CHECK constraints live in migration 0106)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class PulseRedFlagRule(UUIDPrimaryKeyMixin, Base):
    """Règle globale semée ; `active` ne bascule que par SQL (jamais par une route ni par un modèle)."""

    __tablename__ = "pulse_red_flag_rules"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description_fr: Mapped[str] = mapped_column(Text, nullable=False)
    condition: Mapped[dict] = mapped_column(JSONB, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    message_fr: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PulseRedFlagEvent(UUIDPrimaryKeyMixin, Base):
    """Levée d'une règle : preuve sans texte libre, ouverte tant que l'utilisateur ne l'a pas résolue."""

    __tablename__ = "pulse_red_flag_events"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rule_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("pulse_red_flag_rules.id"), nullable=False)
    subject_ref: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    raised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    acknowledged_by_user_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
