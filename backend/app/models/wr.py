"""WR continuous engine tables (spec WR §3).

wr_docket_items is shared from day one (doc 78 F2-11, R3): WR, Daily, Vector and
Pulse all drop items there; the user decides in the WR ritual (or at once for red).
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, UUIDPrimaryKeyMixin


class WrDocketItem(UUIDPrimaryKeyMixin, Base):
    """One point awaiting a user decision (CHECK constraints live in migration 0083)."""

    __tablename__ = "wr_docket_items"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    item_type: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    title_fr: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    evidence_refs: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    impact_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False, default="normal", server_default="normal")
    priority: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending", server_default="pending")
    consecutive_defers: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    force_decision: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    source_worker: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class WrDigest(UUIDPrimaryKeyMixin, Base):
    """Frozen digest of one WR session (one per session, migration 0084)."""

    __tablename__ = "wr_digests"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    review_session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("imperium_weekly_review_sessions.id", ondelete="CASCADE"), nullable=False
    )
    window_from: Mapped[date] = mapped_column(Date(), nullable=False)
    window_to: Mapped[date] = mapped_column(Date(), nullable=False)
    digest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WrMetricsWeekly(UUIDPrimaryKeyMixin, Base):
    """Weekly WR metrics (spec WR §3.8 + user_id ; one row per user and week, migration 0085).

    NULL = not measurable yet (the worker or engine feeding it is not coded).
    """

    __tablename__ = "wr_metrics_weekly"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date(), nullable=False)
    factory_runs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    events_processed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chain_proposals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    patterns_new: Mapped[int | None] = mapped_column(Integer, nullable=True)
    patterns_reinforced: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contradictions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    docket_created: Mapped[int | None] = mapped_column(Integer, nullable=True)
    docket_validated: Mapped[int | None] = mapped_column(Integer, nullable=True)
    docket_refused: Mapped[int | None] = mapped_column(Integer, nullable=True)
    docket_deferred: Mapped[int | None] = mapped_column(Integer, nullable=True)
    docket_forced_decisions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wr_duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wr_mode: Mapped[str | None] = mapped_column(Text, nullable=True)
    cloud_cost_estimate: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    agreement_by_slot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
