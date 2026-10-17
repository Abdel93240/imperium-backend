from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base, UUIDPrimaryKeyMixin


class ImperiumDayReview(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "imperium_day_reviews"
    __table_args__ = (
        UniqueConstraint("user_id", "local_date", name="imperium_day_reviews_user_local_date_unique"),
        Index("imperium_day_reviews_user_created_idx", "user_id", "created_at"),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    local_date: Mapped[date] = mapped_column(Date(), nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    day_status: Mapped[str] = mapped_column(Text, nullable=False)
    energy_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fatigue_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_quality: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stress_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mood: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_win: Mapped[str | None] = mapped_column(Text, nullable=True)
    main_problem: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_items: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    missed_items: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    free_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_event_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class PlanningDay(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "planning_days"
    __table_args__ = (
        CheckConstraint(
            "felt_energy >= 1 AND felt_energy <= 5",
            name="felt_energy_range",
        ),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="finished_after_started",
        ),
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="planning_days_user_idempotency_key_unique",
        ),
        Index(
            "planning_days_one_open_per_user_idx",
            "user_id",
            unique=True,
            postgresql_where=text("finished_at IS NULL"),
        ),
        Index("planning_days_user_started_at_idx", "user_id", "started_at"),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    start_local_date: Mapped[date] = mapped_column(Date(), nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    felt_energy: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    day_review_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("imperium_day_reviews.id"),
        nullable=True,
    )
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ImperiumEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "imperium_events"
    __table_args__ = (
        CheckConstraint("length(btrim(event_type)) > 0", name="imperium_events_event_type_non_empty"),
        CheckConstraint("event_type ~ '^[a-z][a-z0-9_]*$'", name="imperium_events_event_type_format_check"),
        CheckConstraint("length(btrim(source_module)) > 0", name="imperium_events_source_module_non_empty"),
        CheckConstraint("length(btrim(schema_version)) > 0", name="imperium_events_schema_version_non_empty"),
        CheckConstraint("schema_version = 'v1'", name="imperium_events_schema_version_v1_check"),
        CheckConstraint(
            "payload_json IS NULL OR jsonb_typeof(payload_json) = 'object'",
            name="imperium_events_payload_json_object_check",
        ),
        CheckConstraint(
            "source_module IN ('mission', 'vault', 'path', 'pulse', 'vector', "
            "'dashboard', 'daily_plan', 'system', 'manual')",
            name="imperium_events_source_module_allowed_check",
        ),
        Index("imperium_events_user_occurred_at_desc_idx", "user_id", text("occurred_at DESC")),
        Index(
            "imperium_events_user_source_module_occurred_at_desc_idx",
            "user_id",
            "source_module",
            text("occurred_at DESC"),
        ),
        Index(
            "imperium_events_user_event_type_occurred_at_desc_idx",
            "user_id",
            "event_type",
            text("occurred_at DESC"),
        ),
        Index(
            "imperium_events_user_idempotency_key_unique_idx",
            "user_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    source_module: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False, default="v1", server_default="v1")
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ImperiumMission(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "imperium_missions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('backlog', 'active', 'completed', 'failed', 'abandoned', 'cancelled', 'standby')",
            name="imperium_missions_status_check",
        ),
        CheckConstraint(
            "domain IS NULL OR domain IN ('religious', 'business', 'finance', 'health')",
            name="imperium_missions_domain_check",
        ),
        CheckConstraint(
            "priority_level IS NULL OR (priority_level >= 1 AND priority_level <= 10)",
            name="imperium_missions_priority_level_range",
        ),
        CheckConstraint(
            "mission_type_category IS NULL OR mission_type_category IN "
            "('cat_a', 'cat_b', 'cat_c', 'cat_d', 'cat_e', 'cat_f', 'cat_g', 'cat_h', 'cat_i')",
            name="imperium_missions_mission_type_category_check",
        ),
        CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes > 0",
            name="imperium_missions_estimated_minutes_positive",
        ),
        CheckConstraint(
            "failure_reason_code IS NULL OR failure_reason_code IN "
            "('no_time', 'too_tired', 'not_relevant', 'impediment')",
            name="imperium_missions_failure_reason_code_check",
        ),
        CheckConstraint(
            "annex_of_mission_id IS NULL OR annex_of_mission_id <> id",
            name="imperium_missions_annex_not_self",
        ),
        Index(
            "imperium_missions_user_standby_idx",
            "user_id",
            postgresql_where=text("status = 'standby'"),
        ),
        Index(
            "imperium_missions_annex_of_idx",
            "annex_of_mission_id",
            postgresql_where=text("annex_of_mission_id IS NOT NULL"),
        ),
        Index(
            "imperium_missions_one_active_per_user_idx",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("imperium_missions_user_status_idx", "user_id", "status"),
        Index("imperium_missions_started_at_idx", "started_at"),
        Index("imperium_missions_user_domain_idx", "user_id", "domain"),
        Index(
            "imperium_missions_user_backlog_priority_created_idx",
            "user_id",
            "priority_level",
            "created_at",
            postgresql_where=text("status = 'backlog'"),
        ),
        Index("imperium_missions_user_mission_type_category_idx", "user_id", "mission_type_category"),
        Index(
            "imperium_missions_project_position_idx",
            "project_id",
            "project_position",
            postgresql_where=text("project_id IS NOT NULL"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mission_type_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    planned_start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completion_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # doc 52 §10 : raison codée d'une mission non faite ; failure_reason garde les détails.
    failure_reason_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    # doc 71 §8 : mission d'un projet, ordonnée ; description et notes (maquettes 10, 11).
    project_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("imperium_projects.id"), nullable=True
    )
    project_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # doc 43 §5.4 : échéance ; dépassée à la clôture de journée → standby.
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # doc 43 §5.2 : durée estimée (proposée par l'IA, modifiable).
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # doc 53 §3.1 : mission annexe accrochée à une mission porteuse.
    annex_of_mission_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("imperium_missions.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_reported_signals: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_usable_reason: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Annexes encore en attente (backlog) accrochées à cette mission porteuse.
    pending_annexes: Mapped[list["ImperiumMission"]] = relationship(
        "ImperiumMission",
        primaryjoin=(
            "and_(ImperiumMission.id == remote(foreign(ImperiumMission.annex_of_mission_id)), "
            "remote(ImperiumMission.status) == 'backlog')"
        ),
        order_by="ImperiumMission.created_at",
        viewonly=True,
        lazy="select",
    )
    created_by_event_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("events.id"),
        nullable=True,
    )
    ended_by_event_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("events.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ImperiumPriorityRule(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "imperium_priority_rules"
    __table_args__ = (
        CheckConstraint("rank_order > 0", name="imperium_priority_rules_rank_order_positive"),
        CheckConstraint(
            "importance_score IS NULL OR (importance_score >= 1 AND importance_score <= 100)",
            name="imperium_priority_rules_importance_score_range",
        ),
        Index(
            "imperium_priority_rules_active_rank_unique_idx",
            "user_id",
            "rank_order",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
        Index(
            "imperium_priority_rules_active_key_unique_idx",
            "user_id",
            "priority_key",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
        Index(
            "imperium_priority_rules_user_active_rank_idx",
            "user_id",
            "is_active",
            "rank_order",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    priority_key: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    rank_order: Mapped[int] = mapped_column(Integer, nullable=False)
    importance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by_event_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("events.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ImperiumUserPriority(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "imperium_user_priorities"
    __table_args__ = (
        CheckConstraint(
            "domain IN ('religious', 'business', 'finance', 'health')",
            name="imperium_user_priorities_domain_check",
        ),
        CheckConstraint("position >= 1 AND position <= 4", name="imperium_user_priorities_position_range"),
        CheckConstraint(
            "(position = 1 AND coefficient = 10) OR "
            "(position = 2 AND coefficient = 8) OR "
            "(position = 3 AND coefficient = 5) OR "
            "(position = 4 AND coefficient = 4)",
            name="imperium_user_priorities_position_coefficient_check",
        ),
        Index(
            "imperium_user_priorities_active_domain_unique_idx",
            "user_id",
            "domain",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
        Index(
            "imperium_user_priorities_active_position_unique_idx",
            "user_id",
            "position",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
        Index("imperium_user_priorities_user_active_position_idx", "user_id", "is_active", "position"),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    coefficient: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ImperiumPulseEntry(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "imperium_pulse_entries"
    __table_args__ = (
        UniqueConstraint("user_id", "entry_date", name="imperium_pulse_entries_user_entry_date_unique"),
        CheckConstraint(
            "sleep_hours IS NULL OR (sleep_hours >= 0 AND sleep_hours <= 24)",
            name="imperium_pulse_entries_sleep_hours_range",
        ),
        CheckConstraint(
            "energy_level IS NULL OR (energy_level >= 1 AND energy_level <= 10)",
            name="imperium_pulse_entries_energy_level_range",
        ),
        CheckConstraint(
            "fatigue_level IS NULL OR (fatigue_level >= 1 AND fatigue_level <= 10)",
            name="imperium_pulse_entries_fatigue_level_range",
        ),
        CheckConstraint(
            "weight_kg IS NULL OR weight_kg > 0",
            name="imperium_pulse_entries_weight_kg_positive",
        ),
        CheckConstraint(
            "workout_done IS DISTINCT FROM false OR workout_type IS NULL",
            name="imperium_pulse_entries_workout_type_requires_workout_done",
        ),
        Index(
            "imperium_pulse_entries_user_entry_date_desc_idx",
            "user_id",
            text("entry_date DESC"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date(), nullable=False)
    sleep_hours: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    energy_level: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    fatigue_level: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    workout_done: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    workout_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ImperiumCalendarEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "imperium_calendar_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('event', 'deadline', 'vacation')",
            name="imperium_calendar_events_event_type_check",
        ),
        CheckConstraint(
            "ends_at IS NULL OR ends_at >= starts_at",
            name="imperium_calendar_events_date_range_check",
        ),
        Index("imperium_calendar_events_user_starts_at_idx", "user_id", "starts_at"),
        Index("imperium_calendar_events_user_event_type_idx", "user_id", "event_type"),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    blocks_time: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    deletion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ImperiumMissionScore(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "imperium_mission_scores"
    __table_args__ = (
        CheckConstraint(
            "domain IN ('religious', 'business', 'finance', 'health')",
            name="imperium_mission_scores_domain_check",
        ),
        CheckConstraint("intrinsic_score >= 0 AND intrinsic_score <= 100", name="imperium_mission_scores_intrinsic_range"),
        CheckConstraint("domain_coefficient IN (10, 8, 5, 4)", name="imperium_mission_scores_coefficient_check"),
        CheckConstraint("weighted_score >= 0", name="imperium_mission_scores_weighted_nonnegative"),
        CheckConstraint("source IN ('decision_framework_v1')", name="imperium_mission_scores_source_check"),
        Index("imperium_mission_scores_user_weighted_idx", "user_id", "weighted_score"),
        Index("imperium_mission_scores_user_domain_idx", "user_id", "domain"),
        Index("imperium_mission_scores_mission_idx", "mission_id"),
        Index(
            "imperium_mission_scores_user_mission_source_unique_idx",
            "user_id",
            "mission_id",
            "source",
            unique=True,
        ),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    mission_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("imperium_missions.id", ondelete="CASCADE"),
        nullable=False,
    )
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    intrinsic_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    domain_coefficient: Mapped[int] = mapped_column(Integer, nullable=False)
    weighted_score: Mapped[float] = mapped_column(Numeric(7, 2), nullable=False)
    explanation: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    source: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="decision_framework_v1",
        server_default=text("'decision_framework_v1'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ImperiumPathItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "imperium_path_items"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'in_progress', 'completed', 'skipped', 'cancelled')",
            name="imperium_path_items_status_check",
        ),
        CheckConstraint(
            "source IN ('manual', 'system', 'ai_planned')",
            name="imperium_path_items_source_check",
        ),
        Index("imperium_path_items_user_local_date_idx", "user_id", "local_date"),
        Index("imperium_path_items_user_status_idx", "user_id", "status"),
        Index("imperium_path_items_user_planned_start_idx", "user_id", "planned_start"),
        Index(
            "imperium_path_items_user_local_date_sort_idx",
            "user_id",
            "local_date",
            "sort_order",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    local_date: Mapped[date] = mapped_column(Date(), nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, default="Europe/Paris", server_default="Europe/Paris")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    planned_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="manual", server_default="manual")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    skip_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    skipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    item_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ImperiumPathHabit(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "imperium_path_habits"
    __table_args__ = (
        CheckConstraint(
            "frequency IN ('daily', 'weekly')",
            name="imperium_path_habits_frequency_check",
        ),
        Index("imperium_path_habits_user_active_created_idx", "user_id", "is_active", "created_at"),
        Index("imperium_path_habits_user_domain_idx", "user_id", "domain"),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(80), nullable=True)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ImperiumPathCheckIn(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "imperium_path_check_ins"
    __table_args__ = (
        CheckConstraint(
            "status IN ('done', 'missed')",
            name="imperium_path_check_ins_status_check",
        ),
        CheckConstraint(
            "status <> 'missed' OR (reason IS NOT NULL AND trim(reason) <> '')",
            name="imperium_path_check_ins_missed_requires_reason",
        ),
        UniqueConstraint(
            "user_id",
            "habit_id",
            "check_date",
            name="imperium_path_check_ins_user_habit_date_unique",
        ),
        Index(
            "imperium_path_check_ins_user_check_date_desc_idx",
            "user_id",
            text("check_date DESC"),
        ),
        Index(
            "imperium_path_check_ins_user_habit_check_date_idx",
            "user_id",
            "habit_id",
            "check_date",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    habit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("imperium_path_habits.id"),
        nullable=False,
    )
    check_date: Mapped[date] = mapped_column(Date(), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ImperiumDailyPlan(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "imperium_daily_plans"
    __table_args__ = (
        UniqueConstraint("user_id", "local_date", name="imperium_daily_plans_user_local_date_unique"),
        CheckConstraint(
            "plan_status IN ('draft', 'active', 'completed', 'cancelled')",
            name="imperium_daily_plans_status_check",
        ),
        CheckConstraint(
            "jsonb_typeof(plan_blocks) = 'array'",
            name="imperium_daily_plans_plan_blocks_array_check",
        ),
        Index("imperium_daily_plans_user_local_date_idx", "user_id", "local_date"),
        Index("imperium_daily_plans_user_status_idx", "user_id", "plan_status"),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    local_date: Mapped[date] = mapped_column(Date(), nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, default="Europe/Paris", server_default="Europe/Paris")
    plan_status: Mapped[str] = mapped_column(Text, nullable=False, default="draft", server_default="draft")
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    focus_priority_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_mission_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("imperium_missions.id"),
        nullable=True,
    )
    generated_from: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    plan_blocks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class PlanningReplanEvent(UUIDPrimaryKeyMixin, Base):
    """Demande de replanification et cycle de sa proposition (doc 43 §3.2–§3.4, doc 59 §12.6)."""

    __tablename__ = "planning_replan_events"
    __table_args__ = (
        CheckConstraint("trigger IN ('manual', 'hook')", name="trigger_check"),
        CheckConstraint(
            "status IN ('requested', 'proposed', 'revising', 'accepted', 'cancelled', 'failed')",
            name="status_check",
        ),
        CheckConstraint(
            "reason_category IS NULL OR reason_category IN "
            "('new_event', 'wrong_estimation', 'fatigue', 'priority_shift', 'other')",
            name="reason_category_check",
        ),
        CheckConstraint(
            "trigger <> 'manual' OR (reason_category IS NOT NULL AND length(btrim(coalesce(reason_detail, ''))) >= 3)",
            name="manual_reason_required",
        ),
        CheckConstraint(
            "reason_category IS DISTINCT FROM 'other' OR length(btrim(coalesce(other_reason, ''))) > 0",
            name="other_reason_required",
        ),
        CheckConstraint("trigger <> 'hook' OR hook_type IS NOT NULL", name="hook_type_required"),
        CheckConstraint("proposal IS NULL OR jsonb_typeof(proposal) = 'array'", name="proposal_array"),
        CheckConstraint("proposal_version >= 0", name="proposal_version_non_negative"),
        UniqueConstraint("user_id", "idempotency_key", name="user_idempotency_unique"),
        Index("planning_replan_events_user_requested_idx", "user_id", "requested_at"),
        Index(
            "planning_replan_events_one_open_per_user_idx",
            "user_id",
            unique=True,
            postgresql_where=text("status IN ('requested', 'proposed', 'revising')"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    planning_day_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("planning_days.id"), nullable=True)
    daily_plan_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("imperium_daily_plans.id"), nullable=True
    )
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    hook_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_category: Mapped[str | None] = mapped_column(Text, nullable=True)
    other_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    ai_task_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("ai_tasks.id"), nullable=True)
    proposal: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposal_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ImperiumProject(UUIDPrimaryKeyMixin, Base):
    """Projet d'Opérations (doc 71 §3) : les 2 premiers du classement sont actifs."""

    __tablename__ = "imperium_projects"
    __table_args__ = (
        CheckConstraint("status IN ('open', 'completed', 'deleted')", name="status_check"),
        CheckConstraint("source IN ('manual', 'chatbot')", name="source_check"),
        CheckConstraint("length(btrim(title)) > 0", name="title_not_blank"),
        CheckConstraint("rank_order > 0", name="rank_positive"),
        CheckConstraint(
            "progress_percent IS NULL OR (progress_percent >= 0 AND progress_percent <= 100)", name="progress_range"
        ),
        CheckConstraint(
            "completion_method IS NULL OR completion_method IN ('suggested', 'manual')", name="completion_method_check"
        ),
        Index("imperium_projects_user_status_rank_idx", "user_id", "status", "rank_order"),
        Index(
            "imperium_projects_user_idempotency_idx",
            "user_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rank_order: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="open", server_default=text("'open'"))
    source: Mapped[str] = mapped_column(Text, nullable=False, default="manual", server_default=text("'manual'"))
    # Estimée par l'IA pendant la Weekly Review (doc 71 §3.1) ; masquée tant que NULL.
    progress_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress_why: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completion_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ImperiumRoutine(UUIDPrimaryKeyMixin, Base):
    """Routine (doc 71 §4.1) : 4 fréquences fermées ; jour/heure forcés seulement via le chatbot."""

    __tablename__ = "imperium_routines"
    __table_args__ = (
        CheckConstraint("frequency IN ('daily', 'weekly', 'biweekly', 'monthly')", name="frequency_check"),
        CheckConstraint("priority IN ('low', 'medium', 'high')", name="priority_check"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        CheckConstraint("estimated_minutes IS NULL OR estimated_minutes > 0", name="estimated_minutes_positive"),
        CheckConstraint(
            "pinned_weekday IS NULL OR (pinned_weekday >= 1 AND pinned_weekday <= 7)", name="pinned_weekday_range"
        ),
        CheckConstraint(
            "pinned_month_day IS NULL OR (pinned_month_day >= 1 AND pinned_month_day <= 31)", name="pinned_month_day_range"
        ),
        Index("imperium_routines_user_active_idx", "user_id", "active"),
        Index(
            "imperium_routines_user_idempotency_idx",
            "user_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    frequency: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    priority: Mapped[str] = mapped_column(Text, nullable=False, default="medium", server_default=text("'medium'"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    pinned_weekday: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    pinned_month_day: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    pinned_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    # Ancre des périodes (quinzaine = 14 jours depuis la création, doc 71 §4.1).
    anchor_date: Mapped[date] = mapped_column(Date(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ImperiumRoutineCheck(UUIDPrimaryKeyMixin, Base):
    """Occurrence d'une routine sur une journée opérationnelle : planned | done | missed."""

    __tablename__ = "imperium_routine_checks"
    __table_args__ = (
        CheckConstraint("status IN ('planned', 'done', 'missed')", name="status_check"),
        UniqueConstraint("routine_id", "operational_date", name="routine_day_unique"),
        Index("imperium_routine_checks_user_date_idx", "user_id", "operational_date"),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    routine_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("imperium_routines.id"), nullable=False)
    planning_day_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("planning_days.id"), nullable=True)
    operational_date: Mapped[date] = mapped_column(Date(), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ImperiumUserSettings(UUIDPrimaryKeyMixin, Base):
    """Réglages Imperium d'un utilisateur (doc 43 §15, doc 65 §8.5) ; une ligne par utilisateur."""

    __tablename__ = "imperium_user_settings"
    __table_args__ = (
        UniqueConstraint("user_id", name="user_unique"),
        CheckConstraint("ai_mode IN ('strict', 'equilibre', 'souple')", name="ai_mode_check"),
        CheckConstraint("replan_on_failure_urgent IN ('replan', 'ask')", name="failure_urgent_check"),
        CheckConstraint("replan_on_failure_other IN ('replan', 'ask')", name="failure_other_check"),
        CheckConstraint("replan_debounce_minutes >= 1 AND replan_debounce_minutes <= 120", name="debounce_range"),
        CheckConstraint("chat_retention_days IN (30, 60, 90, 180, 365)", name="retention_choices"),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    bubble_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    notify_weekly_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    notify_mission_reminders: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    notify_red_alerts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    morning_popup_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    ai_mode: Mapped[str] = mapped_column(Text, nullable=False, default="equilibre", server_default=text("'equilibre'"))
    replan_on_failure_urgent: Mapped[str] = mapped_column(Text, nullable=False, default="replan", server_default=text("'replan'"))
    replan_on_failure_other: Mapped[str] = mapped_column(Text, nullable=False, default="ask", server_default=text("'ask'"))
    replan_debounce_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=5, server_default=text("5"))
    chat_retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90, server_default=text("90"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ImperiumWeeklyReviewState(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "imperium_weekly_review_states"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "week_start",
            name="imperium_weekly_review_states_user_week_start_unique",
        ),
        Index(
            "imperium_weekly_review_states_user_week_start_idx",
            "user_id",
            "week_start",
        ),
        Index(
            "imperium_weekly_review_states_user_ready_true_idx",
            "user_id",
            "ready",
            postgresql_where=text("ready = TRUE"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    week_start: Mapped[date] = mapped_column(Date(), nullable=False)
    ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    launched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("FALSE"))
    launched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    analysis_status: Mapped[str] = mapped_column(
        String(length=32),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )
    analysis_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ImperiumWeeklyReviewSession(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "imperium_weekly_review_sessions"
    __table_args__ = (
        UniqueConstraint("user_id", "week_start", name="imperium_weekly_review_sessions_user_week_unique"),
        CheckConstraint(
            "status IN ("
            "'ready', 'launched', 'preparing_initial_summary', 'initial_summary_ready', "
            "'waiting_for_user_answer', 'conversation_active', 'integrating_answers', 'draft_ready', "
            "'revision_requested', 'final_ready', 'approved', 'stored', 'cancelled', 'failed'"
            ")",
            name="imperium_weekly_review_sessions_status_check",
        ),
        Index("imperium_weekly_review_sessions_user_status_idx", "user_id", "status"),
        Index("imperium_weekly_review_sessions_user_week_start_idx", "user_id", "week_start"),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date(), nullable=False)
    week_end: Mapped[date] = mapped_column(Date(), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="ready", server_default=text("'ready'"))
    launched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_ai_task_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_tasks.id"),
        nullable=True,
    )
    initial_ai_result_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_results.id"),
        nullable=True,
    )
    final_ai_result_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_results.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ImperiumWeeklyReviewMessage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "imperium_weekly_review_messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'qwen', 'system', 'opus', 'backend')",
            name="imperium_weekly_review_messages_role_check",
        ),
        CheckConstraint(
            "message_type IN ("
            "'user_answer', 'clarification_question', 'initial_summary', 'draft', "
            "'revision_request', 'final_report', 'system_note', "
            "'chat_message', 'assistant_followup', 'final_report_draft'"
            ")",
            name="imperium_weekly_review_messages_type_check",
        ),
        Index("imperium_weekly_review_messages_session_created_idx", "session_id", "created_at"),
        Index("imperium_weekly_review_messages_user_created_idx", "user_id", "created_at"),
    )

    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("imperium_weekly_review_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ai_task_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_tasks.id"),
        nullable=True,
    )
    ai_result_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_results.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ImperiumWeeklyReviewFinalReport(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "imperium_weekly_review_final_reports"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'approved', 'stored', 'superseded')",
            name="imperium_weekly_review_final_reports_status_check",
        ),
        Index("imperium_weekly_review_final_reports_user_status_idx", "user_id", "status"),
        Index("imperium_weekly_review_final_reports_user_week_idx", "user_id", "week_start"),
        Index(
            "uq_wr_final_reports_active_session",
            "session_id",
            unique=True,
            postgresql_where=text("status IN ('draft', 'approved', 'stored')"),
        ),
        Index(
            "uq_wr_final_reports_active_user_week",
            "user_id",
            "week_start",
            unique=True,
            postgresql_where=text("status IN ('draft', 'approved', 'stored')"),
        ),
    )

    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("imperium_weekly_review_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    week_start: Mapped[date] = mapped_column(Date(), nullable=False)
    week_end: Mapped[date] = mapped_column(Date(), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft", server_default=text("'draft'"))
    report_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    report_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    memory_candidates: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_ai_result_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("ai_results.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ImperiumMemoryCandidateDecision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "imperium_memory_candidate_decisions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "report_id",
            "candidate_id",
            name="uq_mem_candidate_decision_user_report_candidate",
        ),
        CheckConstraint(
            "decision IN ('approved', 'rejected', 'edited')",
            name="imperium_memory_candidate_decisions_decision_check",
        ),
        CheckConstraint(
            "source IN ('weekly_review')",
            name="imperium_memory_candidate_decisions_source_check",
        ),
        Index("imperium_memory_candidate_decisions_user_created_idx", "user_id", text("created_at DESC")),
        Index("imperium_memory_candidate_decisions_user_decision_idx", "user_id", "decision"),
        Index("imperium_memory_candidate_decisions_report_idx", "report_id"),
        Index("imperium_memory_candidate_decisions_session_idx", "session_id"),
        Index("imperium_memory_candidate_decisions_candidate_idx", "candidate_id"),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    report_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("imperium_weekly_review_final_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("imperium_weekly_review_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[str] = mapped_column(Text, nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="weekly_review", server_default=text("'weekly_review'"))
    original_candidate: Mapped[dict] = mapped_column(JSONB, nullable=False)
    edited_candidate: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class FoodStockItem(UUIDPrimaryKeyMixin, Base):
    """Stock alimentaire de Pulse : matières premières (doc 40 §10.5, §11.2)."""

    __tablename__ = "food_stock_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit IN ('piece', 'kg', 'g', 'l', 'cl', 'ml')", name="unit_check"),
        CheckConstraint("expiry_type IN ('DLC', 'DDM', 'unknown')", name="expiry_type_check"),
        CheckConstraint("source IN ('manual', 'vault_receipt', 'pantry_scan', 'chatbot')", name="source_check"),
        CheckConstraint("status IN ('active', 'consumed', 'removed')", name="status_check"),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("food_stock_items_user_status_idx", "user_id", "status"),
        Index("food_stock_items_user_source_ref_idx", "user_id", "source_ref", unique=True,
              postgresql_where=text("source_ref IS NOT NULL")),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    unit: Mapped[str] = mapped_column(Text, nullable=False, default="piece", server_default=text("'piece'"))
    expiry_type: Mapped[str] = mapped_column(Text, nullable=False, default="unknown", server_default=text("'unknown'"))
    expiry_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active", server_default=text("'active'"))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PulsePantryScan(UUIDPrimaryKeyMixin, Base):
    """Scan du placard (PUL-13) : proposition comparée au stock, photo jamais conservée."""

    __tablename__ = "pulse_pantry_scans"
    __table_args__ = (
        CheckConstraint("status IN ('ready', 'failed', 'validated', 'cancelled')", name="status_check"),
        CheckConstraint("image_quality IS NULL OR image_quality IN ('good', 'acceptable', 'poor')", name="image_quality_check"),
        CheckConstraint("size_bytes >= 0", name="size_non_negative"),
        Index("pulse_pantry_scans_user_created_idx", "user_id", "created_at"),
        Index("pulse_pantry_scans_user_idempotency_idx", "user_id", "idempotency_key", unique=True),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    image_quality: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposal: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PulseMeal(UUIDPrimaryKeyMixin, Base):
    """Repas (PUL-02/PUL-03) : brouillon, puis validation qui décompte le stock une seule fois."""

    __tablename__ = "pulse_meals"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'confirmed', 'cancelled')", name="status_check"),
        CheckConstraint("source IN ('text', 'voice', 'photo', 'manual', 'chatbot')", name="source_check"),
        CheckConstraint("length(btrim(description)) > 0", name="description_not_blank"),
        CheckConstraint("calories IS NULL OR calories >= 0", name="calories_non_negative"),
        CheckConstraint("protein_g IS NULL OR protein_g >= 0", name="protein_g_non_negative"),
        CheckConstraint("carbs_g IS NULL OR carbs_g >= 0", name="carbs_g_non_negative"),
        CheckConstraint("fat_g IS NULL OR fat_g >= 0", name="fat_g_non_negative"),
        Index("pulse_meals_user_eaten_idx", "user_id", "eaten_at"),
        Index("pulse_meals_user_idempotency_idx", "user_id", "idempotency_key", unique=True),
    )

    user_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    eaten_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    calories: Mapped[Decimal | None] = mapped_column(Numeric(7, 1), nullable=True)
    protein_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 1), nullable=True)
    carbs_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 1), nullable=True)
    fat_g: Mapped[Decimal | None] = mapped_column(Numeric(6, 1), nullable=True)
    proposal: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    stock_decrement_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    confirm_idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirm_request_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
