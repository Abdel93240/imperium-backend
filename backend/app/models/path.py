"""Path prayer-time tables (socle scope: doc 41 §20, minimal prayer engine).

Only the three tables the socle needs (mosques + MAWAQIT cache + calculated
fallback times). The rest of doc 41 §20 (ghusl addresses, adhkar, quran,
sadaqa state) belongs to the Path pass.
"""

from datetime import date, datetime, time
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, Text, Time, UniqueConstraint
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
