"""Vacances scolaires de la zone C (Paris) pour Vector (doc 57 §5.2), open data de l'Éducation nationale.

Appel sortant autorisé par l'utilisateur (data.education.gouv.fr, sans clé). Le job
`vector.school_holidays_refresh` (lundi 03:30, semé éteint) relit le calendrier et garde les périodes ; une offre
lit `is_school_holiday` dans la table. Table vide : la variable reste vide (jamais « pas en vacances » par défaut).
Le jeu de données donne la veille du premier jour à minuit et le jour de reprise : la période est
[premier jour, jour de reprise[, en heure de Paris. Pour l'été, la ligne « Élèves » est gardée.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.rides import RidesSchoolHoliday

PARIS = ZoneInfo("Europe/Paris")
URL = "https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-calendrier-scolaire/records"
ZONE = "Zone C"
TIMEOUT_S = 20


class SchoolCalendarUnavailableError(RuntimeError):
    pass


def fetch(since: date) -> list[dict]:
    query = urllib.parse.urlencode({
        "where": f'location="Paris" and end_date>="{since.isoformat()}"', "order_by": "start_date", "limit": 100,
    })
    try:
        with urllib.request.urlopen(f"{URL}?{query}", timeout=TIMEOUT_S) as response:  # nosec B310 - URL fixe
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise SchoolCalendarUnavailableError(f"Calendrier scolaire injoignable : {exc}") from exc
    if not isinstance(body.get("results"), list):
        raise SchoolCalendarUnavailableError("Réponse du calendrier scolaire incomplète.")
    return body["results"]


def _day(value: str) -> date:
    return datetime.fromisoformat(value).astimezone(PARIS).date()


def refresh(db: Session, *, today: date | None = None, fetcher=None) -> int:
    today = today or datetime.now(PARIS).date()
    rows = (fetcher or fetch)(date(today.year - 2, 1, 1))
    now = datetime.now(UTC)
    kept = 0
    for row in rows:
        if row.get("population") == "Enseignants" or row.get("zones") != ZONE:
            continue
        start, end = _day(row["start_date"]), _day(row["end_date"])
        if end < start:
            continue
        db.execute(insert(RidesSchoolHoliday).values(
            id=uuid4(), label=str(row.get("description") or "Vacances").strip(), zone=ZONE,
            school_year=str(row.get("annee_scolaire") or ""), start_day=start, end_day=end, fetched_at=now,
        ).on_conflict_do_update(constraint="period_unique", set_={"end_day": end, "fetched_at": now}))
        kept += 1
    db.flush()
    return kept


def holiday_on(db: Session, day: date) -> tuple[bool | None, str | None]:
    """(en vacances ?, nom de la période) ; (None, None) tant que le calendrier n'a jamais été relevé."""
    if db.scalar(select(RidesSchoolHoliday.id).limit(1)) is None:
        return None, None
    period = db.scalar(select(RidesSchoolHoliday).where(RidesSchoolHoliday.start_day <= day, RidesSchoolHoliday.end_day > day))
    return (True, period.label) if period else (False, None)


def school_holidays_job(ctx, window) -> None:  # noqa: ARG001 - signature du runner
    try:
        kept = refresh(ctx.db)
        ctx.db.commit()
    except SchoolCalendarUnavailableError as exc:
        ctx.db.rollback()
        ctx.items_in = ctx.items_out = 0
        ctx.detail = {"error": str(exc)}
        return
    ctx.items_in = ctx.items_out = kept
    ctx.detail = {"periods": kept}
