"""PostgreSQL : mémoire de catégories de l'utilisateur (doc 42 §7.0 point 5, §7.2)."""
from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("vault categorization DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.auth import User  # noqa: E402
from app.models.vault import UserCategoryMemory  # noqa: E402
from app.services.vault import categorization as cat  # noqa: E402


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    with Session(engine) as session:
        yield session
        session.rollback()


def _user(db) -> User:
    user_id = uuid4()
    db.execute(
        text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) VALUES (:id, :email, FALSE, now(), now())"),
        {"id": str(user_id), "email": f"cat-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def test_table_hit_needs_no_model(db) -> None:
    user = _user(db)

    def model(prompt: str) -> dict:
        raise AssertionError("the model must not be called for a known label")

    suggestion = cat.suggest_category(db, current_user=user, label="CB TOTAL ENERGIES 4471", call_model=model)
    assert (suggestion.category, suggestion.source, suggestion.confidence) == ("carburant", "table", "high")


def test_confirmed_unknown_label_becomes_a_hit_next_time(db) -> None:
    user = _user(db)
    first = cat.suggest_category(db, current_user=user, label="Boulangerie Paul 12", call_model=None)
    assert first.category is None

    cat.confirm_category(db, current_user=user, label="BOULANGERIE PAUL 98", category="courses")
    again = cat.suggest_category(db, current_user=user, label="boulangerie paul", call_model=None)

    assert (again.category, again.book, again.source, again.confidence) == ("courses", "personal", "user_memory", "medium")


def test_three_identical_confirmations_give_high_confidence(db) -> None:
    user = _user(db)
    for _ in range(3):
        cat.confirm_category(db, current_user=user, label="Garage Martin", category="entretien")
    suggestion = cat.suggest_category(db, current_user=user, label="GARAGE MARTIN", call_model=None)
    assert suggestion.confidence == "high" and suggestion.confirmations == 3


def test_user_memory_overrides_the_hard_table(db) -> None:
    user = _user(db)
    cat.confirm_category(db, current_user=user, label="Carrefour", category="restaurant")
    assert cat.suggest_category(db, current_user=user, label="CARREFOUR", call_model=None).category == "restaurant"


def test_changing_the_category_resets_confirmations(db) -> None:
    user = _user(db)
    cat.confirm_category(db, current_user=user, label="Shop", category="loisirs")
    cat.confirm_category(db, current_user=user, label="Shop", category="loisirs")
    memory = cat.confirm_category(db, current_user=user, label="Shop", category="vêtements")
    assert (memory.category, memory.confirmations) == ("vêtements", 1)


def test_memory_is_user_scoped(db) -> None:
    user, other = _user(db), _user(db)
    cat.confirm_category(db, current_user=user, label="Chez Ali", category="restaurant")
    assert cat.suggest_category(db, current_user=other, label="Chez Ali", call_model=None).category is None


def test_confirm_rejects_categories_outside_the_referential(db) -> None:
    user = _user(db)
    with pytest.raises(cat.CategoryValidationError):
        cat.confirm_category(db, current_user=user, label="X", category="astrologie")
    with pytest.raises(cat.CategoryValidationError):
        cat.confirm_category(db, current_user=user, label="  ", category="courses")


def test_one_memory_row_per_user_and_label(db) -> None:
    user = _user(db)
    db.add(UserCategoryMemory(user_id=user.id, label_key="dup", sample_label="dup", category="courses"))
    db.add(UserCategoryMemory(user_id=user.id, label_key="dup", sample_label="dup", category="loyer"))
    with pytest.raises(IntegrityError):
        db.commit()
