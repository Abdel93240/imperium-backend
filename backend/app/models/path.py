"""Path prayer-time tables (socle scope: doc 41 §20, minimal prayer engine).

Socle: mosques + MAWAQIT cache + calculated fallback times. Path pass: prayer
marks (PAT-02) and fasts (PAT-05). Ghusl addresses, adhkar, quran and sadaqa
state are still to come.
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
