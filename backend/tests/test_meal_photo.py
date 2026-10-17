"""Photo d'un repas (PUL-02, doc 37 §5.3) — lecture de la réponse et parcours complet."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.services.ai import ocr
from app.services.pulse import meal_photo as mp


def _payload(foods, macros=None, quality="good", confidence=0.8, warnings=None):
    return {"result_type": mp.TASK, "summary": "Assiette de riz et poulet", "confidence_score": confidence,
            "structured_result": {"detected_foods": foods, "image_quality": quality,
                                  "macros": macros if macros is not None else
                                  {"calories": 640, "protein_g": 42.5, "carbs_g": 70, "fat_g": 15}},
            "warnings": warnings or []}


def _food(name, quantity=None, unit="g", confidence=0.9):
    return {"name_fr": name, "estimated_quantity": quantity, "unit": unit, "confidence": confidence}


def test_parse_cleans_foods_and_macros() -> None:
    foods, macros, quality, confidence, summary, warnings = mp.parse_result(_payload(
        [_food("Riz", 200), _food(" "), {"name_fr": 4}, _food("Poulet", 1, unit="portion"), _food("Sauce", -2, unit="x", confidence=3)],
        macros={"calories": 640, "protein_g": "beaucoup", "carbs_g": -5, "fat_g": True}, warnings=["portion floue", 3]))
    assert [(f.name, f.quantity, f.unit, f.quantity_assumed) for f in foods] == [
        ("Riz", 200, "g", False), ("Poulet", 1, "piece", True), ("Sauce", 1, "piece", True)]
    assert [f.confidence for f in foods] == [0.9, 0.9, 1.0]
    assert macros == {"calories": 640, "protein_g": None, "carbs_g": None, "fat_g": None}
    assert (quality, confidence, summary, warnings) == ("good", 0.8, "Assiette de riz et poulet", ["portion floue"])


@pytest.mark.parametrize("payload", [None, {}, {"structured_result": {"detected_foods": "x"}},
                                     {"structured_result": {"detected_foods": [], "macros": "x"}}])
def test_parse_rejects_other_shapes(payload) -> None:
    assert mp.parse_result(payload) is None


def test_prompt_is_versioned_and_loaded_without_header() -> None:
    prompt = ocr.load_prompt(mp.PROMPT)
    assert prompt.startswith("You are estimating nutrition from a visible meal photo")
    assert "Never present the result as medical advice." in prompt and "# Prompt" not in prompt


# ---------- PostgreSQL ----------

@pytest.fixture()
def db():
    import os

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    url = os.environ.get("IMPERIUM_TEST_DATABASE_URL")
    if not url:
        pytest.skip("IMPERIUM_TEST_DATABASE_URL not set.")
    engine = create_engine(url, future=True)
    with Session(engine) as session:
        yield session
        session.rollback()
    engine.dispose()


def _user(db):
    from sqlalchemy import text

    from app.models.auth import User

    user_id = uuid4()
    db.execute(
        text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) VALUES (:id, :email, FALSE, now(), now())"),
        {"id": str(user_id), "email": f"mealphoto-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user, analyze):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_user, get_db
    from app.api.v1.routes import imperium_pulse_meals, imperium_pulse_stock

    default = mp._default_analyzer
    mp._default_analyzer = lambda: analyze
    app = FastAPI()
    app.include_router(imperium_pulse_stock.router, prefix="/api/imperium/pulse")
    app.include_router(imperium_pulse_meals.router, prefix="/api/imperium/pulse")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app), lambda: setattr(mp, "_default_analyzer", default)


MEALS = "/api/imperium/pulse/meals"
STOCK = "/api/imperium/pulse/food-stock"


def _photo(client, key=None, content=b"JPEGDATA", filename="assiette.jpg", eaten_at=None):
    params = {"eaten_at": eaten_at} if eaten_at else {}
    return client.post(f"{MEALS}/photo-drafts", params=params, content=content,
                       headers={"X-Filename": filename, "Content-Type": "image/jpeg", "Idempotency-Key": key or uuid4().hex})


@pytest.mark.postgres
def test_photo_draft_carries_estimated_macros_and_stock_proposal(db) -> None:
    from sqlalchemy import select

    from app.models.imperium import PulseMeal

    user = _user(db)
    analyze = lambda data, content_type: _payload([_food("Riz", 200), _food("Poulet", 1, unit="portion"),  # noqa: E731
                                                   _food("Riz basmati", 50, confidence=0.4)])
    client, restore = _client(db, user, analyze)
    try:
        rice = client.post(STOCK, headers={"Idempotency-Key": uuid4().hex}, json={"name": "Riz", "quantity": 1, "unit": "kg"}).json()
        response = _photo(client, eaten_at="2026-10-17T11:30:00+00:00")
        assert response.status_code == 201, response.text
        draft = response.json()
        assert (draft["status"], draft["source"], draft["description"], draft["label"]) == (
            "draft", "photo", "Assiette de riz et poulet", "Assiette de riz et poulet")
        assert (draft["calories"], draft["protein_g"], draft["macros_estimated"], draft["confidence"]) == ("640.0", "42.5", True, 0.8)
        assert draft["eaten_at"].startswith("2026-10-17T11:30:00")
        lines = {line["name"]: line for line in draft["stock_lines"]}
        assert (lines["Riz"]["stock_item_id"], lines["Riz"]["used_in_stock_unit"], lines["Riz"]["checked"]) == (rice["id"], "0.200", True)
        assert lines["Poulet"]["checked"] is False
        assert (lines["Riz basmati"]["confidence"], lines["Riz basmati"]["checked"]) == ("low", False)  # confiance du modèle 0,4
        assert draft["warnings"][0] == "Macros estimées depuis la photo : vérifie-les avant de valider."
        assert db.scalar(select(PulseMeal.photo_sha256).where(PulseMeal.id == draft["id"])) is not None
        confirmed = client.post(f"{MEALS}/{draft['id']}/confirm", headers={"Idempotency-Key": uuid4().hex}, json={
            "calories": 600, "stock_lines": [{"stock_item_id": rice["id"], "quantity": 200, "unit": "g"}]})
        assert confirmed.status_code == 200 and confirmed.json()["calories"] == "600.0"
        assert client.get(STOCK).json()["items"][0]["quantity"] == "0.800"
    finally:
        restore()


@pytest.mark.postgres
def test_blurry_or_uncertain_photo_warns_and_missing_macros_stay_empty(db) -> None:
    user = _user(db)
    client, restore = _client(db, user, lambda data, content_type: _payload(
        [], macros={"calories": None}, quality="poor", confidence=0.3, warnings=["éclairage faible"]))
    try:
        draft = _photo(client).json()
        assert draft["calories"] is None and draft["macros_estimated"] is False
        assert draft["warnings"] == ["Macros non estimées automatiquement : saisis-les pour le suivi.",
                                     "Photo trop floue. Reprendre une photo ?",
                                     "Estimation peu sûre : vérifie les portions.", "éclairage faible"]
    finally:
        restore()


@pytest.mark.postgres
@pytest.mark.parametrize(("analyze", "code", "message"), [
    (None, 503, "pas encore activée"), ("down", 503, "ne répond pas"), ("bad", 422, "illisible"),
    (lambda data, content_type: {"pas": "le format"}, 422, "illisible"),
])
def test_failures_are_readable_and_create_nothing(db, analyze, code, message) -> None:
    from sqlalchemy import func, select

    from app.models.imperium import PulseMeal

    def down(data, content_type):
        raise ocr.OcrServiceUnreachable("x")

    def bad(data, content_type):
        raise ocr.OcrError("x")

    analyze = {"down": down, "bad": bad}[analyze] if isinstance(analyze, str) else analyze
    user = _user(db)
    client, restore = _client(db, user, analyze)
    try:
        response = _photo(client)
        assert response.status_code == code and message in response.json()["detail"]
        assert db.scalar(select(func.count()).select_from(PulseMeal).where(PulseMeal.user_id == user.id)) == 0
    finally:
        restore()


@pytest.mark.postgres
def test_upload_rules_and_replay(db) -> None:
    user = _user(db)
    calls = []
    client, restore = _client(db, user, lambda data, content_type: calls.append(1) or _payload([_food("Riz", 100)]))
    try:
        assert _photo(client, filename="menu.pdf").status_code == 422
        assert _photo(client, content=b"").status_code == 422
        assert client.post(f"{MEALS}/photo-drafts", content=b"x", headers={"X-Filename": "a.jpg"}).status_code == 400
        first = _photo(client, key="p1")
        again = _photo(client, key="p1")
        assert first.status_code == 201 and again.status_code == 200 and again.json()["id"] == first.json()["id"]
        assert len(calls) == 1  # pas de seconde analyse
        assert _photo(client, key="p1", content=b"AUTRE").status_code == 409
    finally:
        restore()
