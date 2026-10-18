"""Calendrier hégirien (doc 41 §14, 14-V3) — moteur, sans base."""
from datetime import date, timedelta

from app.services.path.hijri import Calendar, tabular_first_day, tabular_from_date


def test_tabular_matches_known_ramadan_starts() -> None:
    assert tabular_first_day(1445, 9) == date(2024, 3, 11)
    assert tabular_first_day(1446, 9) == date(2025, 3, 1)
    assert tabular_first_day(1447, 9) == date(2026, 2, 18)
    assert tabular_from_date(date(2026, 2, 18)) == (1447, 9, 1)


def test_round_trip_over_many_years() -> None:
    for year in range(1440, 1460):
        for month in range(1, 13):
            first = tabular_first_day(year, month)
            assert tabular_from_date(first) == (year, month, 1)


def test_unconfirmed_dates_are_duplicated() -> None:
    calendar = Calendar({})
    assert calendar.dates_of(1447, 10, 1) == ([date(2026, 3, 20), date(2026, 3, 21)], "predicted")
    day = calendar.day(date(2026, 2, 20))
    assert (day.hijri_month, day.hijri_day, day.status, day.ramadan) == (9, 3, "predicted", True)


def test_confirmation_moves_the_month_and_the_next_ones() -> None:
    calendar = Calendar({(1447, 9): date(2026, 2, 19)})
    assert calendar.dates_of(1447, 9, 1) == ([date(2026, 2, 19)], "confirmed")
    first = calendar.day(date(2026, 2, 19))
    assert (first.hijri_month, first.hijri_day, first.status) == (9, 1, "confirmed")
    before = calendar.day(date(2026, 2, 18))
    assert (before.hijri_month, before.status) == (8, "predicted")
    # Mois suivant : 29 ou 30 jours après le début confirmé.
    assert calendar.dates_of(1447, 10, 1) == ([date(2026, 3, 20), date(2026, 3, 21)], "predicted")
    # Plus loin : le calcul décalé de l'écart observé (+1 jour).
    assert calendar.start(1447, 12).first_day == tabular_first_day(1447, 12) + timedelta(days=1)


def test_white_days_and_sacred_months() -> None:
    day = Calendar({}).day(date.fromordinal(tabular_first_day(1448, 1).toordinal() + 12))
    assert (day.hijri_day, day.white_day, day.sacred_month, day.month_name) == (13, True, True, "Muharram")
