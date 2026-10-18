"""Path prayer-time tables (socle scope: doc 41 §20, minimal prayer engine).

Socle: mosques + MAWAQIT cache + calculated fallback times. Path pass: prayer
marks (PAT-02), fasts (PAT-05), sadaqa (settings, donations, closed weeks) and
ghusl (state + addresses), adhkar (routines, counts, increments) and quran
(progress, plans), hijri calendar (confirmed month starts, personal events).
"""

from datetime import date, datetime, time
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base, UUIDPrimaryKeyMixin


class PathRegisteredMosque(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "path_registered_mosques"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    mawaqit_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PathMawaqitCache(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "path_mawaqit_cache"
    __table_args__ = (
        UniqueConstraint("mosque_id", "date", name="path_mawaqit_cache_mosque_date_unique"),
    )

    mosque_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("path_registered_mosques.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    prayer_times: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PathCalculatedPrayerTime(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "path_calculated_prayer_times"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "date", name="path_calculated_prayer_times_user_date_unique"
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    fajr: Mapped[time | None] = mapped_column(Time, nullable=True)
    dhuhr: Mapped[time | None] = mapped_column(Time, nullable=True)
    asr: Mapped[time | None] = mapped_column(Time, nullable=True)
    maghrib: Mapped[time | None] = mapped_column(Time, nullable=True)
    isha: Mapped[time | None] = mapped_column(Time, nullable=True)
    calculation_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    madhhab: Mapped[str | None] = mapped_column(Text, nullable=True)
    city_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


PRAYER_NAMES = ("fajr", "dhuhr", "asr", "maghrib", "isha")
PRAYER_STATUSES = ("accomplished", "not_marked_as_accomplished")
FASTING_TYPES = ("monday_thursday", "white_days", "ramadan", "custom", "temporary")
FAST_STATUSES = ("active", "ended", "broken")


class PathPrayerLog(UUIDPrimaryKeyMixin, Base):
    """Prière marquée par l'utilisateur (PAT-02, doc 41 §7) : jamais déduite, une ligne par prière et par jour."""

    __tablename__ = "path_prayer_logs"
    __table_args__ = (
        UniqueConstraint("user_id", "prayer_date", "prayer_name", name="path_prayer_logs_user_day_prayer_unique"),
        CheckConstraint(f"prayer_name IN ({', '.join(repr(name) for name in PRAYER_NAMES)})", name="prayer_name_check"),
        CheckConstraint(f"status IN ({', '.join(repr(name) for name in PRAYER_STATUSES)})", name="status_check"),
        CheckConstraint("status = 'accomplished' OR prayed_at IS NULL", name="prayed_at_only_accomplished"),
        CheckConstraint("version >= 1", name="version_positive"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    prayer_date: Mapped[date] = mapped_column(Date, nullable=False)
    prayer_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    prayed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PathFast(UUIDPrimaryKeyMixin, Base):
    """Jeûne démarré par l'utilisateur (PAT-05, doc 41 §8) : un par jour, un seul en cours.

    Fenêtre du jeûne figée au démarrage : suhoor = fajr − décalage, iftar = maghrib.
    La fin et la rupture demandent toujours une action de l'utilisateur.
    """

    __tablename__ = "path_fasts"
    __table_args__ = (
        UniqueConstraint("user_id", "fasting_date", name="path_fasts_user_date_unique"),
        CheckConstraint(f"fasting_type IN ({', '.join(repr(name) for name in FASTING_TYPES)})", name="fasting_type_check"),
        CheckConstraint(f"status IN ({', '.join(repr(name) for name in FAST_STATUSES)})", name="status_check"),
        CheckConstraint("suhoor_at < iftar_at", name="window_order"),
        CheckConstraint("status <> 'ended' OR ended_at IS NOT NULL", name="ended_has_time"),
        CheckConstraint("status <> 'broken' OR broken_at IS NOT NULL", name="broken_has_time"),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("path_fasts_one_active_idx", "user_id", unique=True, postgresql_where=text("status = 'active'")),
        Index("path_fasts_user_idempotency_idx", "user_id", "idempotency_key", unique=True),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    fasting_date: Mapped[date] = mapped_column(Date, nullable=False)
    fasting_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active", server_default="active")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    suhoor_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    iftar_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    times_source: Mapped[str] = mapped_column(Text, nullable=False)
    hydration_daytime_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    broken_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    break_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PathSadaqaSetting(UUIDPrimaryKeyMixin, Base):
    """Réglage sadaqa (PAT-11d, doc 41 §9.2, §9.5) : une ligne par changement, valable à partir d'un lundi.

    Le calcul d'une semaine prend la dernière ligne dont `effective_from` est passé ;
    un changement vaut pour les semaines suivantes par défaut (jamais de recalcul du passé).
    """

    __tablename__ = "path_sadaqa_settings"
    __table_args__ = (
        CheckConstraint("percentage BETWEEN 0.01 AND 0.20", name="percentage_range"),
        CheckConstraint("safety_margin BETWEEN 0.10 AND 0.15", name="safety_margin_range"),
        CheckConstraint("extract(isodow from effective_from) = 1", name="effective_from_monday"),
        Index("path_sadaqa_settings_user_effective_idx", "user_id", "effective_from", "created_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    percentage: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    safety_margin: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PathSadaqaDonation(UUIDPrimaryKeyMixin, Base):
    """Don déclaré par l'utilisateur (PAT-03, doc 41 §9.4) ; dépense « sadaqa » écrite au Vault ensuite."""

    __tablename__ = "path_sadaqa_donations"
    __table_args__ = (
        CheckConstraint("amount_cents > 0 AND amount_cents <= 10000000", name="amount_range"),
        CheckConstraint("extract(isodow from related_week_start) = 1", name="related_week_monday"),
        CheckConstraint("vault_status IN ('not_requested', 'pending', 'recorded')", name="vault_status_check"),
        CheckConstraint("vault_status <> 'recorded' OR vault_transaction_id IS NOT NULL", name="recorded_has_transaction"),
        Index("path_sadaqa_donations_user_week_idx", "user_id", "related_week_start"),
        Index("path_sadaqa_donations_user_idempotency_idx", "user_id", "idempotency_key", unique=True),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    destination: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    donated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    related_week_start: Mapped[date] = mapped_column(Date, nullable=False)
    allocation: Mapped[list] = mapped_column(JSONB, nullable=False)
    record_in_vault: Mapped[bool] = mapped_column(Boolean, nullable=False)
    wallet: Mapped[str] = mapped_column(Text, nullable=False)
    vault_status: Mapped[str] = mapped_column(Text, nullable=False)
    # Lien sans clé étrangère : le registre Vault garde son garde-fou en ajout seul (TRUNCATE refusé).
    vault_transaction_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PathSadaqaWeek(Base):
    """Semaine close (doc 41 §9.3) : cible, dons et reste figés, base du report suivant."""

    __tablename__ = "path_sadaqa_weeks"
    __table_args__ = (
        CheckConstraint("extract(isodow from week_start) = 1", name="week_start_monday"),
        CheckConstraint("remaining_cents >= 0", name="remaining_not_negative"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    week_start: Mapped[date] = mapped_column(Date, primary_key=True)
    business_profit_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    profit_source: Mapped[str] = mapped_column(Text, nullable=False)
    percentage: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    safety_margin: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    base_target_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    carried_in_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    target_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    donated_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    closed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


GHUSL_ADDRESS_TYPES = ("home", "mosque", "gym", "work", "other")


class PathGhuslAddress(UUIDPrimaryKeyMixin, Base):
    """Adresse où faire le ghusl (PAT-10, doc 41 §10.4) ; lue par la replanification Imperium."""

    __tablename__ = "path_ghusl_addresses"
    __table_args__ = (
        CheckConstraint("length(btrim(label)) BETWEEN 1 AND 100", name="label_length"),
        CheckConstraint(f"address_type IN ({', '.join(repr(name) for name in GHUSL_ADDRESS_TYPES)})", name="address_type_check"),
        CheckConstraint("(latitude IS NULL) = (longitude IS NULL)", name="coordinates_pair"),
        CheckConstraint("latitude IS NULL OR latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude IS NULL OR longitude BETWEEN -180 AND 180", name="longitude_range"),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("path_ghusl_addresses_one_default_idx", "user_id", unique=True, postgresql_where=text("is_default")),
        Index("path_ghusl_addresses_user_idempotency_idx", "user_id", "idempotency_key", unique=True),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)
    address_type: Mapped[str] = mapped_column(Text, nullable=False)
    address_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PathGhuslState(UUIDPrimaryKeyMixin, Base):
    """Ghusl requis (PAT-04, doc 41 §10) : une ligne par activation, toujours posée et levée par l'utilisateur."""

    __tablename__ = "path_ghusl_states"
    __table_args__ = (
        CheckConstraint("status IN ('required', 'completed')", name="status_check"),
        CheckConstraint("status <> 'completed' OR completed_at IS NOT NULL", name="completed_has_time"),
        CheckConstraint(
            "replan_status IN ('pending', 'requested', 'no_open_day', 'replan_in_progress', 'failed')",
            name="replan_status_check",
        ),
        Index("path_ghusl_states_one_required_idx", "user_id", unique=True, postgresql_where=text("status = 'required'")),
        Index("path_ghusl_states_user_idempotency_idx", "user_id", "idempotency_key", unique=True),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    required_since: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_prayer: Mapped[str | None] = mapped_column(Text, nullable=True)
    mission_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("imperium_missions.id", ondelete="SET NULL"), nullable=True
    )
    replan_event_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    replan_status: Mapped[str] = mapped_column(Text, nullable=False, default="pending", server_default="pending")
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


ADHKAR_TYPES = ("morning", "evening", "istighfar", "salawat", "tasbih", "tahmid", "takbir", "personal")
ADHKAR_FREQUENCIES = ("daily", "weekly", "per_prayer")
QURAN_PLAN_TYPES = ("daily_pages", "finish_in_days", "juz_based")


class PathAdhkarRoutine(UUIDPrimaryKeyMixin, Base):
    """Routine de dhikr (PAT-06, doc 41 §11) : 8 actives au plus, activée par l'utilisateur."""

    __tablename__ = "path_adhkar_routines"
    __table_args__ = (
        CheckConstraint("length(btrim(label)) BETWEEN 1 AND 64", name="label_length"),
        CheckConstraint(f"adhkar_type IN ({', '.join(repr(name) for name in ADHKAR_TYPES)})", name="adhkar_type_check"),
        CheckConstraint(f"frequency IN ({', '.join(repr(name) for name in ADHKAR_FREQUENCIES)})", name="frequency_check"),
        CheckConstraint("target_count BETWEEN 1 AND 10000", name="target_range"),
        CheckConstraint("version >= 1", name="version_positive"),
        Index("path_adhkar_routines_user_active_idx", "user_id", "active"),
        Index("path_adhkar_routines_user_idempotency_idx", "user_id", "idempotency_key", unique=True),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)
    adhkar_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_count: Mapped[int] = mapped_column(Integer, nullable=False)
    frequency: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PathAdhkarCount(UUIDPrimaryKeyMixin, Base):
    """Compteur d'une routine sur sa période (jour, semaine ISO ou prière du jour)."""

    __tablename__ = "path_adhkar_counts"
    __table_args__ = (
        UniqueConstraint("routine_id", "period_key", name="path_adhkar_counts_routine_period_unique"),
        CheckConstraint("count >= 0", name="count_not_negative"),
        Index("path_adhkar_counts_user_period_idx", "user_id", "period_key"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    routine_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("path_adhkar_routines.id", ondelete="CASCADE"), nullable=False
    )
    period_key: Mapped[str] = mapped_column(Text, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    target_reached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PathAdhkarIncrement(UUIDPrimaryKeyMixin, Base):
    """Un appui (ou un lot d'appuis) validé ; clés distinctes = sommes, même clé = rejeu."""

    __tablename__ = "path_adhkar_increments"
    __table_args__ = (
        CheckConstraint("amount BETWEEN 1 AND 1000", name="amount_range"),
        CheckConstraint("source IN ('tap', 'voice')", name="source_check"),
        Index("path_adhkar_increments_user_idempotency_idx", "user_id", "idempotency_key", unique=True),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    routine_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("path_adhkar_routines.id", ondelete="CASCADE"), nullable=False
    )
    period_key: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PathQuranProgress(UUIDPrimaryKeyMixin, Base):
    """Point de reprise validé (PAT-07, doc 41 §12) : une ligne par utilisateur."""

    __tablename__ = "path_quran_progress"
    __table_args__ = (
        UniqueConstraint("user_id", name="path_quran_progress_user_unique"),
        CheckConstraint("last_validated_page BETWEEN 1 AND 604", name="page_range"),
        CheckConstraint("daily_objective_pages IS NULL OR daily_objective_pages BETWEEN 1 AND 604", name="objective_range"),
        CheckConstraint("khatm_count >= 0", name="khatm_not_negative"),
        CheckConstraint("version >= 1", name="version_positive"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    last_validated_page: Mapped[int] = mapped_column(Integer, nullable=False)
    last_validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    daily_objective_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    khatm_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class PathQuranPlan(UUIDPrimaryKeyMixin, Base):
    """Plan de lecture choisi (doc 41 §12) : un seul actif ; jamais de rattrapage imposé."""

    __tablename__ = "path_quran_plans"
    __table_args__ = (
        CheckConstraint(f"plan_type IN ({', '.join(repr(name) for name in QURAN_PLAN_TYPES)})", name="plan_type_check"),
        CheckConstraint("pages_per_day BETWEEN 1 AND 604", name="pages_per_day_range"),
        CheckConstraint("start_page BETWEEN 1 AND 604", name="start_page_range"),
        CheckConstraint("plan_type <> 'finish_in_days' OR end_date IS NOT NULL", name="finish_has_end_date"),
        Index("path_quran_plans_one_active_idx", "user_id", unique=True, postgresql_where=text("active")),
        Index("path_quran_plans_user_idempotency_idx", "user_id", "idempotency_key", unique=True),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    plan_type: Mapped[str] = mapped_column(Text, nullable=False)
    pages_per_day: Mapped[int] = mapped_column(Integer, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_page: Mapped[int] = mapped_column(Integer, nullable=False)
    started_on: Mapped[date] = mapped_column(Date, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PathHijriMonthStart(UUIDPrimaryKeyMixin, Base):
    """Début de mois hégirien confirmé par l'utilisateur après l'observation (doc 41 14-V3)."""

    __tablename__ = "path_hijri_month_starts"
    __table_args__ = (
        UniqueConstraint("user_id", "hijri_year", "hijri_month", name="path_hijri_month_starts_user_month_unique"),
        CheckConstraint("hijri_month BETWEEN 1 AND 12", name="month_range"),
        CheckConstraint("hijri_year BETWEEN 1300 AND 1700", name="year_range"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    hijri_year: Mapped[int] = mapped_column(Integer, nullable=False)
    hijri_month: Mapped[int] = mapped_column(Integer, nullable=False)
    first_day: Mapped[date] = mapped_column(Date, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PathCalendarEvent(UUIDPrimaryKeyMixin, Base):
    """Événement religieux personnel (dars, rappel, observance) daté dans le calendrier hégirien."""

    __tablename__ = "path_calendar_events"
    __table_args__ = (
        CheckConstraint("length(btrim(label)) BETWEEN 1 AND 120", name="label_length"),
        CheckConstraint("hijri_month BETWEEN 1 AND 12", name="month_range"),
        CheckConstraint("hijri_day BETWEEN 1 AND 30", name="day_range"),
        CheckConstraint("hijri_year IS NULL OR hijri_year BETWEEN 1300 AND 1700", name="year_range"),
        Index("path_calendar_events_user_idempotency_idx", "user_id", "idempotency_key", unique=True),
    )

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    hijri_year: Mapped[int | None] = mapped_column(Integer, nullable=True)  # vide : chaque année
    hijri_month: Mapped[int] = mapped_column(Integer, nullable=False)
    hijri_day: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
