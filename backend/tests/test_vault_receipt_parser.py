"""Lecture déterministe des tickets de caisse (doc 37 §3) — tests unitaires."""
from datetime import date, time

import pytest

from app.services.vault.receipt_parser import parse_receipt_text

SUPERMARCHE = """CARREFOUR MARKET
12 rue de la Paix 75002 Paris
TEL 01 23 45 67 89
Lait demi-écrémé      1,15
Poulet fermier x2     9,80
SOUS-TOTAL           10,95
TOTAL TTC            10,95
TVA 5,5%              0,57
CB SANS CONTACT      10,95
17/10/2026  18:42  CAISSE 04
"""

STATION = """TotalEnergies
Relais Porte d'Orly
Ticket n° 004512
Date : 16.10.26 Heure : 07h55
Gazole  38,21 L
MONTANT
       65,40
Paiement ESPECES
"""


def test_supermarket_receipt() -> None:
    parsed = parse_receipt_text(SUPERMARCHE)
    assert parsed.merchant == "CARREFOUR MARKET"
    assert parsed.total_cents == 1095
    assert parsed.purchase_date == date(2026, 10, 17) and parsed.purchase_time == time(18, 42)
    assert parsed.payment_method == "card" and parsed.warnings == []


def test_fuel_receipt_with_amount_on_next_line_and_short_year() -> None:
    parsed = parse_receipt_text(STATION)
    assert parsed.merchant == "TotalEnergies"
    assert parsed.total_cents == 6540
    assert parsed.purchase_date == date(2026, 10, 16) and parsed.purchase_time == time(7, 55)
    assert parsed.payment_method == "cash"


def test_net_a_payer_wins_over_plain_total_and_thousands_are_read() -> None:
    parsed = parse_receipt_text("GARAGE DUPONT\nTOTAL HT 1 000,00\nTOTAL 1 250,00\nNET A PAYER 1 200,00\n")
    assert parsed.total_cents == 120000


def test_missing_total_falls_back_to_largest_amount_with_a_warning() -> None:
    parsed = parse_receipt_text("BOULANGERIE MARIE\nBaguette 1,20\nCroissant 1,10\n")
    assert parsed.total_cents == 120
    assert any("plus grand montant" in warning for warning in parsed.warnings)


@pytest.mark.parametrize("raw", ["", "   \n  ", "illisible ### ~~"])
def test_unreadable_text_gives_empty_fields_and_warnings(raw) -> None:
    parsed = parse_receipt_text(raw)
    assert parsed.total_cents is None and parsed.purchase_date is None and parsed.payment_method == "unknown"
    assert any("Total non lu" in warning for warning in parsed.warnings)


def test_invalid_dates_are_skipped() -> None:
    assert parse_receipt_text("MAGASIN\n31/02/2026\n05/03/2026\nTOTAL 3,00").purchase_date == date(2026, 3, 5)


def test_line_items_stop_at_the_total_and_carry_quantities_and_hints() -> None:
    lines = parse_receipt_text(SUPERMARCHE).line_items
    assert [(line.description, line.quantity, line.unit, line.total_cents, line.category_hint) for line in lines] == [
        ("Lait demi-écrémé", 1.0, "piece", 115, "food"),
        ("Poulet fermier", 2.0, "piece", 980, "food"),
    ]


def test_line_item_quantity_forms() -> None:
    raw = ("LIDL\n2 x Yaourt nature  1,98\nRiz basmati 1kg   2,49 B\nEau 6x1,5L 0,50 x 6 3,00\nOeufs 3 x 1,20 3,60\n"
           "Lessive  7,90\nTOTAL 19,47\nCB 19,47\n")
    lines = {line.description: line for line in parse_receipt_text(raw).line_items}
    assert (lines["Yaourt nature"].quantity, lines["Yaourt nature"].category_hint) == (2.0, "food")
    assert (lines["Riz basmati 1kg"].quantity, lines["Riz basmati 1kg"].unit) == (1.0, "kg")
    assert (lines["Eau 6x1,5L"].quantity, lines["Eau 6x1,5L"].category_hint) == (6.0, "drink")
    assert lines["Oeufs"].quantity == 3.0
    assert lines["Lessive"].category_hint == "household" and "CB" not in " ".join(lines)


def test_fuel_receipt_has_no_food_lines() -> None:
    assert all(line.category_hint != "food" for line in parse_receipt_text(STATION).line_items)
