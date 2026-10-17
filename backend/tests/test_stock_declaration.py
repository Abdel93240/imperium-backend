"""Lecture des déclarations de stock en français (chatbot, doc 40 §11.1) — sans base."""
from datetime import date
from decimal import Decimal

from app.services.pulse.stock_declaration import parse_declaration

TODAY = date(2026, 10, 17)


def _lines(text: str):
    return [(line.name, line.quantity, line.unit) for line in parse_declaration(text, today=TODAY).lines]


def test_example_of_the_doc() -> None:
    assert _lines("J'ai acheté 2kg de riz, 6 oeufs et un litre de lait") == [
        ("riz", Decimal("2"), "kg"), ("oeufs", Decimal("6"), "piece"), ("lait", Decimal("1"), "l"),
    ]


def test_units_and_decimal_comma() -> None:
    assert _lines("500 g de pâtes ; 1,5 l de jus d'orange\n33 cl de soda, 250 grammes de beurre, 2 kilos de pommes") == [
        ("pâtes", Decimal("500"), "g"), ("jus d'orange", Decimal("1.5"), "l"), ("soda", Decimal("33"), "cl"),
        ("beurre", Decimal("250"), "g"), ("pommes", Decimal("2"), "kg"),
    ]


def test_number_words_containers_and_dozen() -> None:
    assert _lines("deux baguettes, 3 paquets de pâtes, une douzaine d'œufs, un demi-litre de crème") == [
        ("baguettes", Decimal("2"), "piece"), ("pâtes", Decimal("3"), "piece"), ("œufs", Decimal("12"), "piece"),
        ("crème", Decimal("0.5"), "l"),
    ]


def test_missing_quantity_is_one_and_flagged() -> None:
    parsed = parse_declaration("ajoute du pain et de la farine", today=TODAY)
    assert [(line.name, line.quantity, line.quantity_assumed) for line in parsed.lines] == [
        ("pain", Decimal("1"), True), ("farine", Decimal("1"), True),
    ]


def test_expiry_dates() -> None:
    parsed = parse_declaration("4 yaourts dlc 20/10, 1 kg de café ddm 03/02/2027, du jambon périme le 5/1", today=TODAY)
    assert [(line.name, line.expiry_type, line.expiry_date) for line in parsed.lines] == [
        ("yaourts", "DLC", date(2026, 10, 20)), ("café", "DDM", date(2027, 2, 3)), ("jambon", "DLC", date(2027, 1, 5)),
    ]


def test_invalid_date_is_reported_not_guessed() -> None:
    parsed = parse_declaration("du lait dlc 31/02", today=TODAY)
    assert (parsed.lines[0].name, parsed.lines[0].expiry_date, parsed.lines[0].expiry_type) == ("lait", None, "unknown")
    assert parsed.warnings == ["Date limite illisible pour « lait » : à compléter."]


def test_phrases_without_product_are_ignored() -> None:
    parsed = parse_declaration("j'ai acheté, et, dans le frigo", today=TODAY)
    assert parsed.lines == []
    assert parsed.warnings == ["Aucun produit compris. Écris par exemple « 2 kg de riz, 6 œufs »."]


def test_place_suffix_is_stripped() -> None:
    assert _lines("mets 3 tomates dans le frigo") == [("tomates", Decimal("3"), "piece")]


def test_lines_are_capped() -> None:
    parsed = parse_declaration(", ".join(f"{n} pommes" for n in range(1, 80)), today=TODAY)
    assert len(parsed.lines) == 50
    assert parsed.warnings == ["Seuls les 50 premiers produits sont repris."]
