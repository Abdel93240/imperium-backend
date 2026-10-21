"""WR continuous engine tables (spec WR §3).

wr_docket_items is shared from day one (doc 78 F2-11, R3): WR, Daily, Vector and
Pulse all drop items there; the user decides in the WR ritual (or at once for red).
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
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


class WrHypothesis(UUIDPrimaryKeyMixin, Base):
    """WR P1 hypothesis pass of one digest (spec WR §3.6, §9 P1 ; migration 0119)."""

    __tablename__ = "wr_hypotheses"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    digest_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("wr_digests.id", ondelete="CASCADE"), nullable=False
    )
    output: Mapped[dict] = mapped_column(JSONB, nullable=False)
    drill_log: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    model_used: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
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


class WrRollupDaily(UUIDPrimaryKeyMixin, Base):
    """W1 daily aggregate of one domain for one Paris day (migration 0091, recomputed by upsert)."""

    __tablename__ = "wr_rollups_daily"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    local_date: Mapped[date] = mapped_column(Date(), nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WrWalk(UUIDPrimaryKeyMixin, Base):
    """Docket walker session of one WR (migration 0093, spec WR §9 P4)."""

    __tablename__ = "wr_walks"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    review_session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("imperium_weekly_review_sessions.id", ondelete="CASCADE"), nullable=False
    )
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    budget_min: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlanVersion(UUIDPrimaryKeyMixin, Base):
    """Full version of the rolling strategic plan (migration 0095, spec WR §3.5) — never deleted."""

    __tablename__ = "plan_versions"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    horizon_start: Mapped[date] = mapped_column(Date, nullable=False)
    horizon_end: Mapped[date] = mapped_column(Date, nullable=False)
    plan: Mapped[dict] = mapped_column(JSONB, nullable=False)
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    origin_ref: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    model_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="proposed", server_default="proposed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_reason_fr: Mapped[str | None] = mapped_column(Text, nullable=True)


class PlanDelta(UUIDPrimaryKeyMixin, Base):
    """Operations on one plan version, applied in WR P5 (migration 0095, spec WR §3.5, §8.2)."""

    __tablename__ = "plan_deltas"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    plan_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("plan_versions.id"), nullable=False
    )
    operations: Mapped[list] = mapped_column(JSONB, nullable=False)
    origin: Mapped[str] = mapped_column(Text, nullable=False)
    proposal_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("wr_docket_items.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="proposed", server_default="proposed")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChainProbe(UUIDPrimaryKeyMixin, Base):
    """Divergent probe of W2 — a query, never knowledge (migration 0096, spec WR §3.3, §5.1)."""

    __tablename__ = "chain_probes"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    target_event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    probe_text: Mapped[str] = mapped_column(Text, nullable=False)
    probe_kind: Mapped[str] = mapped_column(Text, nullable=False)
    generated_by: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("wr_worker_runs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChainCandidate(UUIDPrimaryKeyMixin, Base):
    """Candidate cause found by the code search of W2 (migration 0096, spec WR §5.2)."""

    __tablename__ = "chain_candidates"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    target_event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    candidate_event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    channels: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    probe_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("chain_probes.id"), nullable=True)
    similarity: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    passed_hard_filters: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rerank_score: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    retained: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChainPairVerdict(UUIDPrimaryKeyMixin, Base):
    """Paired verdict on one retained candidate (migration 0096, spec WR §5.3)."""

    __tablename__ = "chain_pair_verdicts"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    candidate_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("chain_candidates.id"), nullable=False)
    verdict: Mapped[str] = mapped_column(Text, nullable=False)
    mechanism_fr: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    model_used: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ChainAssembly(UUIDPrimaryKeyMixin, Base):
    """Proposed causal links of one target event, awaiting the docket (migration 0096, spec WR §5.4)."""

    __tablename__ = "chain_assemblies"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    target_event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    proposed_links: Mapped[list] = mapped_column(JSONB, nullable=False)
    conflicts: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    docket_item_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("wr_docket_items.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WrPatternExtraction(UUIDPrimaryKeyMixin, Base):
    """Pattern extracted at an episode close, before any memory write (migration 0097, spec WR §6.1)."""

    __tablename__ = "wr_pattern_extractions"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    episode_event_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    statement_fr: Mapped[str] = mapped_column(Text, nullable=False)
    pattern_domain: Mapped[str] = mapped_column(Text, nullable=False)
    context_predicate: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    predicate_rejected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    evidence_event_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PG_UUID(as_uuid=True)), nullable=False)
    suggested_confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_errors: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    model_used: Mapped[str] = mapped_column(Text, nullable=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MemoryConfrontation(UUIDPrimaryKeyMixin, Base):
    """Identity confrontation of an extracted pattern with a memory neighbour (migration 0097, spec WR §6.2)."""

    __tablename__ = "memory_confrontations"

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    extraction_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("wr_pattern_extractions.id"), nullable=False
    )
    new_statement: Mapped[str] = mapped_column(Text, nullable=False)
    neighbor_memory_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ai_memories.id"), nullable=True
    )
    relation: Mapped[str] = mapped_column(Text, nullable=False)
    rationale_fr: Mapped[str] = mapped_column(Text, nullable=False)
    applied_effect: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
