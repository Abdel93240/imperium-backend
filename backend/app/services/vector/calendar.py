"""Jours fériés en France métropolitaine (doc 57 §5.2), calculés sans source externe.

Fixes : 1er janvier, 1er mai, 8 mai, 14 juillet, 15 août, 1er novembre, 11 novembre, 25 décembre.
Mobiles (Pâques, algorithme de Meeus) : lundi de Pâques, Ascension (+39), lundi de Pentecôte (+50).
"""

from datetime import date, timedelta
from functools import lru_cache

FIXED = ((1, 1), (5, 1), (5, 8), (7, 14), (8, 15), (11, 1), (11, 11), (12, 25))


def easter(year: int) -> date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month, day = divmod(h + m - 7 * n + 114, 31)
    return date(year, month, day + 1)


@lru_cache(maxsize=16)
def public_holidays(year: int) -> frozenset[date]:
    sunday = easter(year)
    mobile = (sunday + timedelta(days=1), sunday + timedelta(days=39), sunday + timedelta(days=50))
    return frozenset({date(year, month, day) for month, day in FIXED} | set(mobile))


def is_public_holiday(day: date) -> bool:
    return day in public_holidays(day.year)
