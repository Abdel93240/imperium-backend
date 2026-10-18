"""Calendrier hégirien (doc 41 §14, 14-V3) : calcul, confirmation par l'observation, dates.

Calcul : calendrier tabulaire (cycle de 30 ans, années longues 2, 5, 7, 10, 13, 16, 18, 21,
24, 26, 29 ; 1er muharram 1 = 16 juillet 622). Il donne une date à ± 1 jour près ; le
début réel d'un mois suit l'observation de la lune, confirmée par l'utilisateur.

Début d'un mois :
- confirmé par l'utilisateur → cette date (statut confirmed) ;
- mois précédent confirmé → ce début + 29 jours (J), ou + 30 (J+1) ;
- sinon, date tabulaire décalée de l'écart du dernier mois confirmé (12 mois au plus).
Une date non confirmée s'affiche en double (J et J+1) ; la confirmation retire le doublon.

Les jours blancs proposent un jeûne, jamais un jeûne automatique (doc 41 §8).
"""

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.enums import PrivacyLevel, SourceApp
from app.models.path import PathCalendarEvent, PathHijriMonthStart
from app.schemas.path_calendar import (
    CalendarEventListResponse,
    CalendarEventRead,
    HijriDayRead,
    MonthStartConfirm,
    MonthStartRead,
    PersonalEventCreate,
    PersonalEventRead,
)
from app.services.events.emitter import build_event
from app.services.pulse import food_stock

EPOCH_JDN = 1948440  # 1er muharram 1 (calendrier tabulaire civil)
ORDINAL_TO_JDN = 1721425
MONTH_NAMES = (
    "Muharram", "Safar", "Rabi al-awwal", "Rabi al-thani", "Joumada al-oula", "Joumada al-akhira",
    "Rajab", "Chaabane", "Ramadan", "Chawwal", "Dhou al-qi'da", "Dhou al-hijja",
)
SACRED_MONTHS = {1, 7, 11, 12}
RAMADAN = 9
WHITE_DAYS = (13, 14, 15)
RELIGIOUS_DATES = (  # (code, libellé, mois, jour)
    ("islamic_new_year", "Nouvel an de l'Hégire", 1, 1),
    ("ashura", "Achoura", 1, 10),
    ("mawlid", "Mawlid", 3, 12),
    ("ramadan_start", "Début du ramadan", 9, 1),
    ("eid_al_fitr", "Aïd al-Fitr", 10, 1),
    ("arafah", "Jour de Arafat", 12, 9),
    ("eid_al_adha", "Aïd al-Adha", 12, 10),
)
MAX_RANGE_DAYS = 400
DISPLAY_WINDOW_DAYS = 14


class CalendarInputError(ValueError):
    pass


class CalendarNotFoundError(ValueError):
    pass


# ---------- calcul tabulaire ----------

def tabular_to_jdn(year: int, month: int, day: int) -> int:
    return day + math.ceil(29.5 * (month - 1)) + (year - 1) * 354 + (3 + 11 * year) // 30 + EPOCH_JDN - 1


def tabular_from_date(day: date) -> tuple[int, int, int]:
    jdn = day.toordinal() + ORDINAL_TO_JDN
    year = (30 * (jdn - EPOCH_JDN) + 10646) // 10631
    month = min(12, math.ceil((jdn - (29 + tabular_to_jdn(year, 1, 1))) / 29.5) + 1)
    return year, month, jdn - tabular_to_jdn(year, month, 1) + 1


def tabular_first_day(year: int, month: int) -> date:
    return date.fromordinal(tabular_to_jdn(year, month, 1) - ORDINAL_TO_JDN)


def _index(year: int, month: int) -> int:
    return year * 12 + month - 1


def _from_index(index: int) -> tuple[int, int]:
    return index // 12, index % 12 + 1


# ---------- calendrier de l'utilisateur ----------

@dataclass
class MonthStart:
    first_day: date
    confirmed: bool


class Calendar:
    """Débuts de mois pour un utilisateur : confirmés, sinon prédits."""

    def __init__(self, confirmed: dict[tuple[int, int], date]) -> None:
        self.confirmed = confirmed

    @classmethod
    def load(cls, db: Session, user: User) -> "Calendar":
        rows = db.scalars(select(PathHijriMonthStart).where(PathHijriMonthStart.user_id == user.id))
        return cls({(row.hijri_year, row.hijri_month): row.first_day for row in rows})

    def start(self, year: int, month: int) -> MonthStart:
        if (year, month) in self.confirmed:
            return MonthStart(self.confirmed[(year, month)], True)
        index = _index(year, month)
        previous = self.confirmed.get(_from_index(index - 1))
        if previous is not None:
            return MonthStart(previous + timedelta(days=29), False)
        for back in range(2, 13):
            anchor = _from_index(index - back)
            if anchor in self.confirmed:
                offset = self.confirmed[anchor] - tabular_first_day(*anchor)
                return MonthStart(tabular_first_day(year, month) + offset, False)
        return MonthStart(tabular_first_day(year, month), False)

    def day(self, gregorian: date) -> HijriDayRead:
        year, month, _ = tabular_from_date(gregorian)
        index = _index(year, month)
        found = None
        for candidate in range(index - 2, index + 3):
            start = self.start(*_from_index(candidate))
            if start.first_day <= gregorian:
                found = (candidate, start)
        candidate, start = found
        year, month = _from_index(candidate)
        hijri_day = (gregorian - start.first_day).days + 1
        return HijriDayRead(
            gregorian=gregorian, hijri_year=year, hijri_month=month, hijri_day=hijri_day, month_name=MONTH_NAMES[month - 1],
            status="confirmed" if start.confirmed else "predicted", source="confirmed" if start.confirmed else "calculated",
            white_day=hijri_day in WHITE_DAYS, sacred_month=month in SACRED_MONTHS, ramadan=month == RAMADAN,
        )

    def dates_of(self, year: int, month: int, day: int) -> tuple[list[date], str]:
        start = self.start(year, month)
        first = start.first_day + timedelta(days=day - 1)
        return ([first], "confirmed") if start.confirmed else ([first, first + timedelta(days=1)], "predicted")

    def months_between(self, from_day: date, to_day: date) -> list[tuple[int, int]]:
        """Mois qui touchent la période, plus le précédent (doublon J+1 en début de période)."""
        first, last = self.day(from_day), self.day(to_day)
        start, end = _index(first.hijri_year, first.hijri_month), _index(last.hijri_year, last.hijri_month)
        return [_from_index(index) for index in range(start - 1, end + 1)]


# ---------- lecture ----------

def hijri_day(db: Session, *, current_user: User, day: date) -> HijriDayRead:
    return Calendar.load(db, current_user).day(day)


def list_events(db: Session, *, current_user: User, from_day: date, to_day: date) -> CalendarEventListResponse:
    """Dates religieuses et événements personnels qui tombent dans la période (doublons J / J+1 compris)."""
    if to_day < from_day or (to_day - from_day).days > MAX_RANGE_DAYS:
        raise CalendarInputError(f"Période invalide ({MAX_RANGE_DAYS} jours maximum).")
    calendar = Calendar.load(db, current_user)
    personal = list(db.scalars(select(PathCalendarEvent).where(PathCalendarEvent.user_id == current_user.id)))
    items: list[CalendarEventRead] = []
    for year, month in calendar.months_between(from_day, to_day):
        entries = [("religious", code, label, day, None) for code, label, m, day in RELIGIOUS_DATES if m == month]
        entries += [("religious", f"white_day_{day}", f"Jour blanc ({day} {MONTH_NAMES[month - 1]})", day, None)
                    for day in WHITE_DAYS]
        entries += [("personal", f"personal:{event.id}", event.label, event.hijri_day, event.id) for event in personal
                    if event.hijri_month == month and event.hijri_year in (None, year)]
        for kind, code, label, day, event_id in entries:
            dates, status = calendar.dates_of(year, month, day)
            if any(from_day <= candidate <= to_day for candidate in dates):
                items.append(CalendarEventRead(
                    kind=kind, code=code, label=label, hijri_year=year, hijri_month=month, hijri_day=day, status=status,
                    dates=dates, event_id=event_id,
                ))
    items.sort(key=lambda item: (item.dates[0], item.kind, item.code))
    return CalendarEventListResponse(from_day=from_day, to_day=to_day, items=items)


# ---------- écritures ----------

def confirm_month_start(
    db: Session, *, current_user: User, payload: MonthStartConfirm, idempotency_key: str, request_path: str,
    today: date | None = None,
) -> MonthStartRead:
    """Observation faite : le 1er du mois est fixé ; on peut corriger une confirmation."""
    fingerprint = food_stock.request_hash("path.calendar.confirm", payload.model_dump(mode="json"))
    previous = food_stock.replay(db, current_user, idempotency_key, fingerprint, request_path, MonthStartRead)
    if previous is not None:
        return previous
    today = today or datetime.now(UTC).date()
    calendar = Calendar.load(db, current_user)
    calendar.confirmed.pop((payload.hijri_year, payload.hijri_month), None)
    predicted = calendar.start(payload.hijri_year, payload.hijri_month).first_day
    if abs((payload.first_day - predicted).days) > 1:
        raise CalendarInputError(
            f"Le 1er {MONTH_NAMES[payload.hijri_month - 1]} attendu est le {predicted:%d/%m/%Y} ou le lendemain : "
            "un écart de plus d'un jour est refusé."
        )
    if payload.first_day > today + timedelta(days=1):
        raise CalendarInputError("Une observation ne se confirme pas plus d'un jour à l'avance.")
    row = db.scalar(
        select(PathHijriMonthStart).where(
            PathHijriMonthStart.user_id == current_user.id, PathHijriMonthStart.hijri_year == payload.hijri_year,
            PathHijriMonthStart.hijri_month == payload.hijri_month,
        ).with_for_update()
    )
    now = datetime.now(UTC)
    if row is None:
        row = PathHijriMonthStart(user_id=current_user.id, hijri_year=payload.hijri_year, hijri_month=payload.hijri_month,
                                  first_day=payload.first_day, confirmed_at=now)
        db.add(row)
    else:
        row.first_day, row.confirmed_at = payload.first_day, now
    db.flush()
    db.add(
        build_event(
            db, user_id=current_user.id, event_type="path.calendar.date_confirmed",
            payload={"hijri_year": payload.hijri_year, "hijri_month": payload.hijri_month,
                     "first_day": payload.first_day.isoformat(), "source": "user_action"},
            idempotency_key=f"path.calendar.date_confirmed.{row.id}.{now.isoformat()}", source_app=SourceApp.path,
            privacy_level=PrivacyLevel.medium,
        )
    )
    read = MonthStartRead(hijri_year=row.hijri_year, hijri_month=row.hijri_month, month_name=MONTH_NAMES[row.hijri_month - 1],
                          first_day=row.first_day, status="confirmed")
    food_stock.remember(db, current_user, idempotency_key, "POST", request_path, fingerprint, 200, read)
    db.commit()
    return read


def list_personal(db: Session, *, current_user: User) -> list[PersonalEventRead]:
    rows = db.scalars(
        select(PathCalendarEvent).where(PathCalendarEvent.user_id == current_user.id)
        .order_by(PathCalendarEvent.hijri_month, PathCalendarEvent.hijri_day, PathCalendarEvent.created_at)
    )
    return [PersonalEventRead.model_validate(row) for row in rows]


def add_personal(
    db: Session, *, current_user: User, payload: PersonalEventCreate, idempotency_key: str
) -> tuple[PersonalEventRead, bool]:
    fingerprint = food_stock.request_hash("path.calendar.event", payload.model_dump(mode="json"))
    existing = db.scalar(
        select(PathCalendarEvent).where(
            PathCalendarEvent.user_id == current_user.id, PathCalendarEvent.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise CalendarInputError("Idempotency key already used with a different event.")
        return PersonalEventRead.model_validate(existing), True
    row = PathCalendarEvent(
        user_id=current_user.id, label=payload.label, note=(payload.note or "").strip() or None, hijri_year=payload.hijri_year,
        hijri_month=payload.hijri_month, hijri_day=payload.hijri_day, idempotency_key=idempotency_key,
        request_hash=fingerprint,
    )
    db.add(row)
    db.flush()
    # Imperium lit les dates converties (GET /calendar/events) ; l'événement ne porte pas le libellé.
    db.add(
        build_event(
            db, user_id=current_user.id, event_type="path.calendar.event_added",
            payload={"event_id": str(row.id), "hijri_year": row.hijri_year, "hijri_month": row.hijri_month,
                     "hijri_day": row.hijri_day, "source": "user_action"},
            idempotency_key=f"path.calendar.event_added.{row.id}", source_app=SourceApp.path, privacy_level=PrivacyLevel.high,
        )
    )
    read = PersonalEventRead.model_validate(row)
    db.commit()
    return read, False


def delete_personal(db: Session, *, current_user: User, event_id: UUID) -> None:
    row = db.scalar(select(PathCalendarEvent).where(PathCalendarEvent.id == event_id, PathCalendarEvent.user_id == current_user.id))
    if row is None:
        raise CalendarNotFoundError("Événement introuvable.")
    db.delete(row)
    db.commit()
