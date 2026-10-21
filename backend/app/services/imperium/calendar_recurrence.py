"""Récurrences du calendrier (doc 51 §7) : sous-ensemble de RFC 5545, sans dépendance externe.

Pris en charge : FREQ (DAILY, WEEKLY, MONTHLY, YEARLY), INTERVAL, BYDAY (MO…SU ; en mensuel avec un rang :
« 3TU » = 3e mardi, « -1FR » = dernier vendredi), BYMONTHDAY (mensuel), UNTIL (date ou date-heure UTC) et
COUNT. L'heure locale (Paris) de la première occurrence est gardée d'une occurrence à l'autre, changements
d'heure compris. L'utilisateur ne voit jamais la règle : l'appli et le chatbot la construisent.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
DAYS = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
FREQS = ("DAILY", "WEEKLY", "MONTHLY", "YEARLY")
MAX_SCAN = 5000  # borne de sécurité : jamais plus de pas de calcul par série


class RecurrenceError(ValueError):
    pass


@dataclass(frozen=True)
class Rule:
    freq: str
    interval: int = 1
    by_day: tuple[tuple[int, int], ...] = ()  # (rang ou 0, jour 0-6)
    by_month_day: tuple[int, ...] = ()
    until: datetime | None = None
    count: int | None = None


def parse(text: str) -> Rule:
    """« FREQ=WEEKLY;BYDAY=FR » (avec ou sans le préfixe « RRULE: ») → Rule ; RecurrenceError sinon."""
    parts = {}
    for chunk in text.strip().removeprefix("RRULE:").split(";"):
        key, _, value = chunk.partition("=")
        if not key or not value:
            raise RecurrenceError(f"Morceau de règle illisible : {chunk!r}")
        parts[key.upper()] = value.upper()
    unknown = set(parts) - {"FREQ", "INTERVAL", "BYDAY", "BYMONTHDAY", "UNTIL", "COUNT"}
    if unknown:
        raise RecurrenceError(f"Non pris en charge : {', '.join(sorted(unknown))}")
    freq = parts.get("FREQ")
    if freq not in FREQS:
        raise RecurrenceError("FREQ doit valoir DAILY, WEEKLY, MONTHLY ou YEARLY.")
    try:
        interval = int(parts.get("INTERVAL", "1"))
        by_day = tuple(_day(value) for value in parts["BYDAY"].split(",")) if "BYDAY" in parts else ()
        by_month_day = tuple(int(value) for value in parts["BYMONTHDAY"].split(",")) if "BYMONTHDAY" in parts else ()
        count = int(parts["COUNT"]) if "COUNT" in parts else None
    except ValueError as exc:
        raise RecurrenceError("Nombre illisible dans la règle.") from exc
    if interval < 1 or (count is not None and count < 1):
        raise RecurrenceError("INTERVAL et COUNT doivent être positifs.")
    if any(rank and freq != "MONTHLY" for rank, _ in by_day):
        raise RecurrenceError("Un rang de jour (« 3TU ») n'existe qu'en mensuel.")
    if any(not 1 <= abs(day) <= 31 for day in by_month_day):
        raise RecurrenceError("BYMONTHDAY va de 1 à 31.")
    return Rule(freq=freq, interval=interval, by_day=by_day, by_month_day=by_month_day,
                until=_until(parts["UNTIL"]) if "UNTIL" in parts else None, count=count)


def occurrences(start: datetime, rrule: str | None, *, window_from: datetime, window_to: datetime,
                limit: int = 500) -> list[datetime]:
    """Débuts des occurrences dans [window_from, window_to] ; sans règle, l'événement seul s'il y tombe."""
    if not rrule:
        return [start] if window_from <= start <= window_to else []
    rule = parse(rrule)
    local = start.astimezone(PARIS)
    wall = local.timetz().replace(tzinfo=None)
    found, produced = [], 0
    for day in _days(rule, local.date()):
        at = datetime.combine(day, wall, tzinfo=PARIS).astimezone(UTC)
        if at < start:
            continue
        produced += 1
        if rule.count is not None and produced > rule.count:
            break
        if (rule.until is not None and at > rule.until) or at > window_to:
            break
        if at >= window_from:
            found.append(at)
            if len(found) >= limit:
                break
    return found


def describe(rrule: str | None) -> str | None:
    """Phrase en français (« Tous les vendredis ») pour l'écran et le chatbot."""
    if not rrule:
        return None
    rule = parse(rrule)
    names = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
    every = {"DAILY": ("Tous les jours", "Tous les {n} jours"), "WEEKLY": ("Toutes les semaines", "Toutes les {n} semaines"),
             "MONTHLY": ("Tous les mois", "Tous les {n} mois"), "YEARLY": ("Tous les ans", "Tous les {n} ans")}[rule.freq]
    text = every[0] if rule.interval == 1 else every[1].format(n=rule.interval)
    if rule.by_day:
        if rule.freq == "WEEKLY":
            text += " le " + ", ".join(names[day] for _, day in rule.by_day)
        else:
            ranks = {1: "1er", -1: "dernier"}
            text += " le " + ", ".join(f"{ranks.get(rank, f'{rank}e')} {names[day]}" if rank else names[day]
                                       for rank, day in rule.by_day)
    if rule.by_month_day:
        text += " le " + ", ".join(str(day) for day in rule.by_month_day)
    if rule.count:
        text += f", {rule.count} fois"
    elif rule.until:
        text += f", jusqu'au {rule.until.astimezone(PARIS):%d/%m/%Y}"
    return text


# ---------- internes ----------

def _day(value: str) -> tuple[int, int]:
    code, rank = value[-2:], value[:-2]
    if code not in DAYS:
        raise ValueError(value)
    return (int(rank) if rank else 0), DAYS.index(code)


def _until(value: str) -> datetime:
    try:
        if "T" in value:
            return datetime.strptime(value.rstrip("Z"), "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
        day = datetime.strptime(value, "%Y%m%d").date()
    except ValueError as exc:
        raise RecurrenceError("UNTIL illisible (AAAAMMJJ ou AAAAMMJJTHHMMSSZ).") from exc
    return datetime.combine(day, time(23, 59, 59), tzinfo=PARIS).astimezone(UTC)


def _days(rule: Rule, first: date):
    """Les jours candidats, dans l'ordre, à partir du premier jour de la série."""
    if rule.freq == "DAILY":
        for step in range(MAX_SCAN):
            yield first + timedelta(days=step * rule.interval)
    elif rule.freq == "WEEKLY":
        weekdays = sorted({day for _, day in rule.by_day}) or [first.weekday()]
        monday = first - timedelta(days=first.weekday())
        for step in range(MAX_SCAN):
            week = monday + timedelta(weeks=step * rule.interval)
            for weekday in weekdays:
                yield week + timedelta(days=weekday)
    elif rule.freq == "MONTHLY":
        for step in range(MAX_SCAN):
            year, month = divmod(first.month - 1 + step * rule.interval, 12)
            yield from _month_days(rule, first.year + year, month + 1, first.day)
    else:
        for step in range(MAX_SCAN):
            year = first.year + step * rule.interval
            try:
                yield first.replace(year=year)
            except ValueError:  # 29 février : pas d'occurrence les années non bissextiles
                continue


def _month_days(rule: Rule, year: int, month: int, default_day: int) -> list[date]:
    length = ((date(year + month // 12, month % 12 + 1, 1)) - timedelta(days=1)).day
    days = set()
    for value in rule.by_month_day or (() if rule.by_day else (default_day,)):
        day = value if value > 0 else length + value + 1
        if 1 <= day <= length:
            days.add(date(year, month, day))
    for rank, weekday in rule.by_day:
        matching = [date(year, month, d) for d in range(1, length + 1) if date(year, month, d).weekday() == weekday]
        if rank == 0:
            days.update(matching)
        elif -len(matching) <= rank <= len(matching) and rank != 0:
            days.add(matching[rank - 1 if rank > 0 else rank])
    return sorted(days)
