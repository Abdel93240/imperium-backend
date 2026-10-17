"""Catégorie suggérée d'une transaction (doc 42 §7.0–§7.2) — tests unitaires."""
import pytest

from app.services.vault import categorization as cat

REFERENTIAL = cat.referential_from_map(cat.DEFAULT_CATEGORY_MAP)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("CB TOTAL ENERGIES 4471 PARIS", "total energies paris"),
        ("Carrefour   Market", "carrefour market"),
        ("PRLV SEPA ÉLECTRICITÉ", "prlv sepa electricite"),
        ("BOLT.EU/O/2610171234", "bolt eu o"),
        ("   ", ""),
    ],
)
def test_normalize_label_ignores_case_accents_spacing_and_references(raw, expected) -> None:
    assert cat.normalize_label(raw) == expected


@pytest.mark.parametrize(
    ("label", "category", "book"),
    [
        ("CB TOTAL ENERGIES 4471 PARIS", "carburant", "business"),
        ("BOLT.EU/O/2610171234", "bolt", "business"),
        ("Uber BV", "uber", "business"),
        ("LECLERC DRIVE 4471", "courses", "personal"),
        ("CARREFOUR CITY", "courses", "personal"),
        ("Orange Mobile", "telephone", "personal"),
        ("NETFLIX.COM", "abonnements", "personal"),
        ("URSSAF ILE DE FRANCE", "urssaf", "business"),
    ],
)
def test_hard_table_resolves_known_labels(label, category, book) -> None:
    hit = cat.lookup_table(label, referential=REFERENTIAL)
    assert hit == (category, book)


def test_every_table_category_exists_in_the_default_referential() -> None:
    assert {category for category in cat.LABEL_TABLE.values()} <= set(REFERENTIAL)


def test_book_is_deduced_from_the_category_map() -> None:
    assert REFERENTIAL["vtc"] == ("business", "income")
    assert REFERENTIAL["courses"] == ("personal", "expense")


def test_unknown_label_uses_the_local_model_when_valid() -> None:
    def model(prompt: str) -> dict:
        assert "Boulangerie Paul" in prompt and "courses" in prompt
        return {"category": "Courses", "confidence": 0.8}

    suggestion = cat.suggest_from_model("Boulangerie Paul", referential=REFERENTIAL, call_model=model)
    assert (suggestion.category, suggestion.book, suggestion.source) == ("courses", "personal", "ai")


@pytest.mark.parametrize("output", [{"category": "astrologie"}, {"nope": 1}, "not a dict"])
def test_model_output_outside_the_referential_is_dropped(output) -> None:
    suggestion = cat.suggest_from_model("Boutique X", referential=REFERENTIAL, call_model=lambda prompt: output)
    assert suggestion.category is None and suggestion.source == "none"


def test_no_model_means_no_silent_category() -> None:
    suggestion = cat.suggest_from_model("Boutique X", referential=REFERENTIAL, call_model=None)
    assert suggestion.category is None and suggestion.source == "none"


def test_model_failure_means_no_category() -> None:
    def down(prompt: str) -> dict:
        raise RuntimeError("down")

    assert cat.suggest_from_model("Boutique X", referential=REFERENTIAL, call_model=down).source == "none"


def test_categorization_routes_are_registered() -> None:
    from app.api.v1.router import api_router

    paths = {(route.path, method) for route in api_router.routes for method in getattr(route, "methods", set())}
    for expected in [
        ("/imperium/vault/categories", "GET"),
        ("/imperium/vault/categories/suggest", "POST"),
        ("/imperium/vault/categories/confirm", "POST"),
    ]:
        assert expected in paths, expected
