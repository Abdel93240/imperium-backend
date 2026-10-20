"""Règles rouges, signalements subjectifs et sentinelle Pulse (spec Pulse §3.2, §3.5, §5, §11, §14 ;
CHECK constraints live in migrations 0106, 0108, 0109)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

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


class PulseSubjectiveReport(UUIDPrimaryKeyMixin, Base):
    """Signalement fatigue | mood | stress, niveau 1 (bien) → 5 (mal) ; suppression réelle à la demande."""

    __tablename__ = "pulse_subjective_reports"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PulseSentinelRule(UUIDPrimaryKeyMixin, Base):
    """Règle S1-S7 globale semée inactive ; `active` ne bascule que par SQL."""

    __tablename__ = "pulse_sentinel_rules"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    rule_type: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    cooldown_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_dispatch_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description_fr: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PulseBoardSnapshot(UUIDPrimaryKeyMixin, Base):
    """Copie figée du board au réveil (reproductibilité), prise avant l'interprète."""

    __tablename__ = "pulse_board_snapshots"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    board: Mapped[dict] = mapped_column(JSONB, nullable=False)
    flags_count: Mapped[int] = mapped_column(Integer, nullable=False)
    max_severity: Mapped[str] = mapped_column(Text, nullable=False)


class PulseDispatchLog(UUIDPrimaryKeyMixin, Base):
    """Un réveil de la sentinelle : `queued` puis `done` par le runner (essai à blanc tant que l'IA est coupée)."""

    __tablename__ = "pulse_dispatch_log"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    triggered_by: Mapped[str] = mapped_column(Text, nullable=False)
    subject_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    board_snapshot_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("pulse_board_snapshots.id", ondelete="CASCADE"), nullable=False)
    flag_set: Mapped[dict] = mapped_column(JSONB, nullable=False)
    trigger_event_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    procedures_named: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_reaction: Mapped[str | None] = mapped_column(Text, nullable=True)
    reacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
