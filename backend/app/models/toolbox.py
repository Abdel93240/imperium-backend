"""Shared toolbox foundations (passe 0): runner, notifications, shared tables,
travel cache, AI role/model config.

Schema notes:
- job_* generalises the wr_worker_* pattern from the WR spec (audit FINDINGS T2/W-5).
- parameters follows the append-only pattern of spec Pulse §3.4 (no value UPDATE,
  supersession by new version). Enforced by a SQL trigger in migration 0038.
- signal_definitions/signal_values and ai_slot_transition/ai_audit_samples are the
  shared-from-day-one tables (DBL-2/3/4). The Pulse/WR passes seed them; the socle
  only creates them. Their verbatim spec source (specs Pulse §3.1 / WR §3.7) was no
  longer on disk at socle time: columns are reconstructed from the audit and the
  activation cards (see SOCLE_MAPPING.md §7) — later passes may EXTEND (additive),
  never fork per-domain copies.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, UUIDPrimaryKeyMixin


class JobDefinition(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "job_definitions"
    __table_args__ = (
        UniqueConstraint("code", name="job_definitions_code_unique"),
        CheckConstraint(
            "kind IN ('cron', 'event_subscription', 'manual')",
            name="job_definitions_kind_check",
        ),
        CheckConstraint(
            "kind != 'cron' OR schedule IS NOT NULL",
            name="job_definitions_cron_schedule_check",
        ),
        CheckConstraint("timeout_s > 0", name="job_definitions_timeout_positive"),
    )

    code: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    schedule: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_types: Mapped[list[str] | None] = mapped_column(ARRAY(Text), nullable=True)
    handler_ref: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    singleton: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    timeout_s: Mapped[int] = mapped_column(
        Integer, nullable=False, default=900, server_default="900"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class JobRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "job_runs"
    __table_args__ = (
        CheckConstraint(
            "trigger IN ('cron', 'event', 'manual', 'fallback')",
            name="job_runs_trigger_check",
        ),
        CheckConstraint(
            "status IN ('running', 'completed', 'failed', 'skipped')",
            name="job_runs_status_check",
        ),
        Index("job_runs_job_code_created_idx", "job_code", "created_at"),
    )

    job_code: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_ref: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    window_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    skip_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    items_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    items_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class JobCursor(Base):
    __tablename__ = "job_cursors"

    job_code: Mapped[str] = mapped_column(Text, primary_key=True)
    last_processed_event_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_processed_event_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Notification(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info', 'normal', 'red')",
            name="notifications_severity_check",
        ),
        CheckConstraint(
            "domain IN ('pulse', 'wr', 'daily', 'vector', 'path', 'vault', 'system')",
            name="notifications_domain_check",
        ),
        Index("notifications_created_idx", "created_at"),
        Index("notifications_ref_idx", "ref_type", "ref_id"),
    )

    severity: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    ref_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    ref_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    message_fr: Mapped[str] = mapped_column(Text, nullable=False)
    channels_sent: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationChannel(Base):
    __tablename__ = "notification_channels"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )


class Parameter(UUIDPrimaryKeyMixin, Base):
    """Append-only versioned parameters (spec Pulse §3.4 pattern).

    A value never changes in place: a new row with version+1 is inserted and the
    previous row's superseded_by points to it (trigger-enforced in migration 0038).
    """

    __tablename__ = "parameters"
    __table_args__ = (
        UniqueConstraint("code", "version", name="parameters_code_version_unique"),
        Index("parameters_code_idx", "code"),
    )

    code: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    origin: Mapped[str] = mapped_column(Text, nullable=False, default="seed", server_default="seed")
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    superseded_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("parameters.id"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SignalDefinition(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "signal_definitions"
    __table_args__ = (
        UniqueConstraint("code", name="signal_definitions_code_unique"),
        Index("signal_definitions_domain_idx", "domain"),
    )

    domain: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    label_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    aggregation: Mapped[str | None] = mapped_column(Text, nullable=True)
    baseline_window_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bands: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    staleness_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SignalValue(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "signal_values"
    __table_args__ = (
        Index("signal_values_code_ts_idx", "signal_code", "measured_at"),
    )

    signal_code: Mapped[str] = mapped_column(
        Text, ForeignKey("signal_definitions.code"), nullable=False
    )
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    band: Mapped[str | None] = mapped_column(Text, nullable=True)
    flags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    stale: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AISlotTransition(UUIDPrimaryKeyMixin, Base):
    """Registry + tier state of every AI slot (spec WR §3.7 generalisation).

    De facto the ai_task catalogue (audit T7): every namespaced slot must have a row.
    """

    __tablename__ = "ai_slot_transition"
    __table_args__ = (
        UniqueConstraint("slot_code", name="ai_slot_transition_slot_code_unique"),
        CheckConstraint(
            "tier IN ('local_default', 'cloud_forced', 'routed')",
            name="ai_slot_transition_tier_check",
        ),
        CheckConstraint(
            "audit_sample_pct >= 0 AND audit_sample_pct <= 100",
            name="ai_slot_transition_audit_pct_check",
        ),
    )

    slot_code: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[str] = mapped_column(
        Text, nullable=False, default="cloud_forced", server_default="cloud_forced"
    )
    audit_sample_pct: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, server_default="100"
    )
    agreement_target_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_schema_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes_fr: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AIAuditSample(UUIDPrimaryKeyMixin, Base):
    """Sampled cloud counter-readings of local slot outputs (audit loop F1-13)."""

    __tablename__ = "ai_audit_samples"
    __table_args__ = (
        Index("ai_audit_samples_slot_created_idx", "slot_code", "created_at"),
    )

    slot_code: Mapped[str] = mapped_column(
        Text, ForeignKey("ai_slot_transition.slot_code"), nullable=False
    )
    run_ref: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    input_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    local_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cloud_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    agreement: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    disagreement_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_reaction: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TravelCacheEntry(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "travel_cache"
    __table_args__ = (
        UniqueConstraint(
            "origin_h3",
            "dest_h3",
            "time_slot",
            "profile",
            name="travel_cache_key_unique",
        ),
    )

    origin_h3: Mapped[str] = mapped_column(Text, nullable=False)
    dest_h3: Mapped[str] = mapped_column(Text, nullable=False)
    time_slot: Mapped[str] = mapped_column(Text, nullable=False)
    profile: Mapped[str] = mapped_column(
        Text, nullable=False, default="planning", server_default="planning"
    )
    duration_s: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    multiplier_applied: Mapped[float] = mapped_column(Numeric, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AIRoleModel(UUIDPrimaryKeyMixin, Base):
    """Role → provider/model/effort mapping (doc 73 PART B, identifier-not-call)."""

    __tablename__ = "ai_role_models"
    __table_args__ = (
        UniqueConstraint("role_code", "version", name="ai_role_models_role_version_unique"),
        CheckConstraint(
            "sensitivity_route IN ('direct', 'openrouter_allowed', 'local_only')",
            name="ai_role_models_sensitivity_route_check",
        ),
        Index("ai_role_models_role_active_idx", "role_code", "active"),
    )

    role_code: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model_id: Mapped[str] = mapped_column(Text, nullable=False)
    effort: Mapped[str | None] = mapped_column(Text, nullable=True)
    sensitivity_route: Mapped[str] = mapped_column(
        Text, nullable=False, default="direct", server_default="direct"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
