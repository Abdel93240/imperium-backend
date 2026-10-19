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
    autoaccept_class_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("wr_autoaccept_classes.id"), nullable=True
    )


class WrAutoacceptClass(UUIDPrimaryKeyMixin, Base):
    """User-activated auto-accept class of docket items (migration 0089, spec WR §9 P4)."""

    __tablename__ = "wr_autoaccept_classes"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    item_type: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    slot_code: Mapped[str] = mapped_column(Text, ForeignKey("ai_slot_transition.slot_code"), nullable=False)
    min_confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    rationale_fr: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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


class WrWorkerRun(UUIDPrimaryKeyMixin, Base):
    """One worker pass of the WR factory (spec WR §3.2 + job_run_id ; CHECKs in migration 0090)."""

    __tablename__ = "wr_worker_runs"

    worker: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    session_ref: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    job_run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    window_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    items_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    items_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    llm_calls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WrWorkerCursor(Base):
    """Incremental cursor of one factory worker: it processes ]cursor, now] then advances."""

    __tablename__ = "wr_worker_cursors"

    worker: Mapped[str] = mapped_column(Text, primary_key=True)
    last_processed_event_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_processed_event_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
