"""PostgreSQL : diète Pulse — recettes, plan proposé puis validé, courses, préparation en portions (doc 40 §10.4–§10.9)."""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse diet DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_diet, imperium_pulse_meals, imperium_pulse_stock  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.imperium import ImperiumMission  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.pulse import diet, diet_planner  # noqa: E402

P = "/api/imperium/pulse"
PARIS = diet.PARIS


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


@pytest.fixture()
def enabled(db):
    set_parameter(db, code="pulse.diet_enabled", value=True, origin="user", rationale_fr="Test.")
    db.commit()
    yield
    set_parameter(db, code="pulse.diet_enabled", value=False, origin="user", rationale_fr="Test.")
    db.commit()


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"diet-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    for module in (imperium_pulse_diet, imperium_pulse_meals, imperium_pulse_stock):
        app.include_router(module.router, prefix=P)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _key() -> dict:
    return {"Idempotency-Key": uuid4().hex}


def _next_monday() -> date:
    today = datetime.now(PARIS).date()
    return today + timedelta(days=7 - today.weekday())


def _stock(client, name, quantity, unit, expiry: date | None = None) -> dict:
    body = {"name": name, "quantity": quantity, "unit": unit}
    if expiry:
        body |= {"expiry_type": "DLC", "expiry_date": expiry.isoformat()}
    response = client.post(f"{P}/food-stock", headers=_key(), json=body)
    assert response.status_code == 201, response.text
    return response.json()


CHILI = {"title": "Chili sin carne", "servings": 4, "portion_weight_g": 450,
         "ingredients": [{"name": "Haricots rouges", "quantity": 800, "unit": "g"},
                         {"name": "Riz basmati", "quantity": 400, "unit": "g"},
                         {"name": "Oignon", "quantity": 2, "unit": "piece"}],
         "steps": ["Faire revenir l'oignon.", "Ajouter les haricots, mijoter 30 min.", "Cuire le riz."],
         "packaging": ["Bocaux stérilisés 20 min à 100 °C.", "Refroidir avant de fermer le coffre."],
         "shelf_life_days": 6, "calories": 600, "protein_g": 25, "carbs_g": 90, "fat_g": 10}


def _plan_output(week: date, recipe_ref: str = "R1") -> dict:
    """Une préparation lundi (8 portions de R1 + 4 de N1), repas du lundi au mercredi."""
    soup = {"key": "N1", "title": "Soupe de lentilles", "servings": 4, "portion_weight_g": None,
            "ingredients": [{"name": "Lentilles corail", "quantity": 500, "unit": "g"}],
            "steps": ["Cuire les lentilles 20 min."], "packaging": ["Bocal stérilisé, se garde 5 jours."],
            "shelf_life_days": 5, "calories": None, "protein_g": None, "carbs_g": None, "fat_g": None}
    day = lambda i: (week + timedelta(days=i)).isoformat()  # noqa: E731
    return {"rationale_fr": "Deux plats simples, préparés lundi.", "new_recipes": [soup],
            "preparations": [{"recipe": recipe_ref, "day": day(0), "portions": 8},
                             {"recipe": "N1", "day": day(0), "portions": 4}],
            "meals": [{"day": day(0), "slot": "lunch", "recipe": recipe_ref, "portions": 1},
                      {"day": day(0), "slot": "dinner", "recipe": "N1", "portions": 1},
                      {"day": day(1), "slot": "lunch", "recipe": recipe_ref, "portions": 1.5},
                      {"day": day(2), "slot": "dinner", "recipe": "N1", "portions": 1}]}


def _fake(outputs: list[dict]):
    calls = []

    def call(system, prompt, schema):
        calls.append(prompt)
        return outputs[min(len(calls), len(outputs)) - 1], "cloud", {"model": "fake"}
    call.calls = calls
    return call


def _proposed(db, client, user, *, output=None) -> dict:
    week = _next_monday()
    if not client.get(f"{P}/recipes").json()["items"]:
        assert client.post(f"{P}/recipes", headers=_key(), json=CHILI).status_code == 201
    response = client.post(f"{P}/diet/plans", headers=_key(), json={"week_start": week.isoformat(), "note": "Peu de sucre"})
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "generating"
    now = datetime.combine(week, time(6), tzinfo=PARIS)
    diet_planner.generate(db, UUID(response.json()["id"]), call=_fake([output or _plan_output(week)]), now=now)
    plan = client.get(f"{P}/diet/plans/{response.json()['id']}").json()
    assert plan["status"] == "proposed", plan
    return plan


def test_routes_closed_until_enabled(db):
    client = _client(db, _user(db))
    response = client.get(f"{P}/diet/week")
    assert response.status_code == 409
    assert response.json()["code"] == "PULSE_DIET_DISABLED"
    assert client.get(f"{P}/diet/attention").json() == []  # lu par Imperium : vide, jamais une erreur


def test_recipe_catalogue_is_idempotent_and_archivable(db, enabled):
    client = _client(db, _user(db))
    key = _key()
    first = client.post(f"{P}/recipes", headers=key, json=CHILI)
    assert first.status_code == 201
    assert client.post(f"{P}/recipes", headers=key, json=CHILI).status_code == 200
    assert client.post(f"{P}/recipes", headers=key, json={**CHILI, "servings": 2}).status_code == 409
    assert client.post(f"{P}/recipes", headers=_key(), json={**CHILI, "steps": []}).status_code == 422
    recipe = first.json()
    assert recipe["packaging"][0].startswith("Bocaux") and recipe["calories"] == "600.0"
    assert [r["id"] for r in client.get(f"{P}/recipes").json()["items"]] == [recipe["id"]]
    assert client.delete(f"{P}/recipes/{recipe['id']}").status_code == 204
    assert client.get(f"{P}/recipes").json()["items"] == []


def test_planner_proposes_a_checked_week_and_retries_an_invalid_one(db, enabled):
    user = _user(db)
    client = _client(db, user)
    week = _next_monday()
    bad = _plan_output(week)
    bad["meals"].append({"day": (week + timedelta(days=6)).isoformat(), "slot": "lunch", "recipe": "N1", "portions": 1})
    good = _plan_output(week)
    client.post(f"{P}/recipes", headers=_key(), json=CHILI)
    plan_id = client.post(f"{P}/diet/plans", headers=_key(), json={"week_start": week.isoformat()}).json()["id"]
    fake = _fake([bad, good])
    diet_planner.generate(db, UUID(plan_id), call=fake, now=datetime.combine(week, time(6), tzinfo=PARIS))
    assert len(fake.calls) == 2 and "conservation" in fake.calls[1]
    plan = client.get(f"{P}/diet/plans/{plan_id}").json()
    assert plan["status"] == "proposed" and plan["source"] == "cloud"
    assert [(m["slot"], m["recipe_title"]) for m in plan["meals"][:2]] == [("lunch", "Chili sin carne"),
                                                                           ("dinner", "Soupe de lentilles")]
    assert plan["meals"][0]["calories"] == "600.0" and plan["meals"][1]["calories"] is None
    assert plan["meals"][2]["calories"] == "900.0"  # 1,5 portion
    assert {p["portions_planned"] for p in plan["preparations"]} == {8, 4}
    # Recette nouvelle : hors catalogue tant que le plan n'est pas validé.
    assert [r["title"] for r in client.get(f"{P}/recipes").json()["items"]] == ["Chili sin carne"]
    week_read = client.get(f"{P}/diet/week", params={"day": week.isoformat()}).json()
    assert week_read["active"] is None and week_read["pending"]["id"] == plan_id


def test_planner_without_brain_fails_honestly(db, enabled):
    user = _user(db)
    client = _client(db, user)
    week = _next_monday()
    plan_id = client.post(f"{P}/diet/plans", headers=_key(), json={"week_start": week.isoformat()}).json()["id"]
    assert client.post(f"{P}/diet/plans", headers=_key(), json={"week_start": week.isoformat()}).status_code == 409
    diet_planner.generate(db, UUID(plan_id), now=datetime.combine(week, time(6), tzinfo=PARIS))
    plan = client.get(f"{P}/diet/plans/{plan_id}").json()
    assert plan["status"] == "failed" and "Aucun cerveau" in plan["error"]
    assert client.post(f"{P}/diet/plans/{plan_id}/reject").json()["status"] == "rejected"


@pytest.mark.parametrize(("change", "expected"), [
    (lambda o, w: o["meals"].append({"day": w(1), "slot": "lunch", "recipe": "R1", "portions": 1}), "même créneau"),
    (lambda o, w: o["meals"].append({"day": w(3), "slot": "lunch", "recipe": "R9", "portions": 1}), "inconnue"),
    (lambda o, w: o["meals"].append({"day": w(6), "slot": "lunch", "recipe": "N1", "portions": 1}), "conservation"),
    (lambda o, w: o["meals"].append({"day": w(4), "slot": "lunch", "recipe": "R1", "portions": 6}), "hors de 0 à 4"),
    (lambda o, w: [o["meals"].append({"day": w(d), "slot": "breakfast", "recipe": "R1", "portions": 2})
                   for d in range(4)], "portions mangées"),
    (lambda o, w: o["preparations"].__setitem__(1, {"recipe": "N1", "day": w(2), "portions": 4}), "sans préparation"),
    (lambda o, w: o["preparations"].pop(1), "jamais préparée"),
])
def test_validation_rejects_impossible_weeks(change, expected):
    week = _next_monday()
    days = [week + timedelta(days=i) for i in range(7)]
    output = _plan_output(week)
    change(output, lambda i: (week + timedelta(days=i)).isoformat())

    class Recipe:
        id, shelf_life_days = uuid4(), 6
    errors = diet_planner.validate(output, days, {"R1": Recipe}, {})
    assert any(expected in error for error in errors), errors


def test_ready_portions_count_as_supply():
    week = _next_monday()
    days = [week + timedelta(days=i) for i in range(7)]

    class Recipe:
        id, shelf_life_days = uuid4(), 6
    output = {"rationale_fr": "", "new_recipes": [], "preparations": [],
              "meals": [{"day": days[0].isoformat(), "slot": "lunch", "recipe": "R1", "portions": 2}]}
    assert any("sans préparation" in e for e in diet_planner.validate(output, days, {"R1": Recipe}, {}))
    assert diet_planner.validate(output, days, {"R1": Recipe}, {Recipe.id: Decimal(3)}) == []


def test_activation_builds_a_shopping_list_that_empties_with_the_stock(db, enabled):
    user = _user(db)
    client = _client(db, user)
    _stock(client, "Riz basmati", 1, "kg")
    _stock(client, "Haricots rouges en conserve", 500, "g")
    plan = _proposed(db, client, user)
    activated = client.post(f"{P}/diet/plans/{plan['id']}/activate")
    assert activated.json()["status"] == "active"
    assert "Soupe de lentilles" in [r["title"] for r in client.get(f"{P}/recipes").json()["items"]]
    # Chili × 2 (8 portions pour 4) : haricots 1600 g − 500 g ; riz 800 g couvert ; oignons 4 ; lentilles 500 g.
    items = {i["name"]: (i["quantity"], i["unit"]) for i in client.get(f"{P}/shopping-list").json()["items"]}
    assert items == {"Haricots rouges": ("1.100", "kg"), "Oignon": ("4.000", "piece"),
                     "Lentilles corail": ("500.000", "g")}
    week_read = client.get(f"{P}/diet/week", params={"day": plan["week_start"]}).json()
    assert week_read["active"]["id"] == plan["id"] and week_read["pending"] is None and week_read["shopping_open"] == 3

    by_name = {i["name"]: i for i in client.get(f"{P}/shopping-list").json()["items"]}
    assert client.patch(f"{P}/shopping-list/{by_name['Oignon']['id']}", json={"checked": True}).json()["checked"]
    _stock(client, "Oignons jaunes", 3, "piece")  # pas assez : la ligne reste avec ce qui manque
    _stock(client, "Lentilles corail", 1, "kg")
    items = {i["name"]: (i["quantity"], i["checked"]) for i in client.get(f"{P}/shopping-list").json()["items"]}
    assert items == {"Haricots rouges": ("1.100", False), "Oignon": ("1.000", True)}
    assert client.delete(f"{P}/shopping-list/{by_name['Oignon']['id']}").status_code == 204
    assert [i["name"] for i in client.get(f"{P}/shopping-list").json()["items"]] == ["Haricots rouges"]
    assert db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.shopping.item_removed"))


def test_new_validated_plan_supersedes_the_previous_one(db, enabled):
    user = _user(db)
    client = _client(db, user)
    first = _proposed(db, client, user)
    client.post(f"{P}/diet/plans/{first['id']}/activate")
    second = _proposed(db, client, user)
    assert client.get(f"{P}/diet/week", params={"day": first["week_start"]}).json()["pending"]["id"] == second["id"]
    client.post(f"{P}/diet/plans/{second['id']}/activate")
    old = client.get(f"{P}/diet/plans/{first['id']}").json()
    assert old["status"] == "superseded" and {p["status"] for p in old["preparations"]} == {"cancelled"}
    assert {i["plan_id"] for i in client.get(f"{P}/shopping-list").json()["items"]} == {second["id"]}


def test_preparation_blocks_on_missing_stock_then_makes_portions_once(db, enabled):
    user = _user(db)
    client = _client(db, user)
    plan = _proposed(db, client, user)
    client.post(f"{P}/diet/plans/{plan['id']}/activate")
    chili = next(p for p in plan["preparations"] if p["recipe_title"] == "Chili sin carne")

    blocked = client.post(f"{P}/preparations/{chili['id']}/start")
    assert blocked.status_code == 409 and blocked.json()["code"] == "INGREDIENTS_MISSING"
    assert {m["name"] for m in blocked.json()["missing"]} == {"Haricots rouges", "Riz basmati", "Oignon"}
    attention = client.get(f"{P}/diet/attention").json()
    assert attention[0]["recipe_title"] == "Chili sin carne" and "il manque" in attention[0]["message_fr"]

    soon, later = date.today() + timedelta(days=3), date.today() + timedelta(days=30)
    old_rice = _stock(client, "Riz basmati", 500, "g", soon)
    new_rice = _stock(client, "Riz basmati", 1, "kg", later)
    beans = _stock(client, "Haricots rouges", 2, "kg")
    onions = _stock(client, "Oignon", 4, "piece")
    assert client.get(f"{P}/diet/attention").json() == []
    detail = client.get(f"{P}/preparations/{chili['id']}").json()
    assert all(line["enough"] for line in detail["needs"]) and detail["recipe"]["steps"]
    assert client.post(f"{P}/preparations/{chili['id']}/start").json()["status"] == "started"

    key = _key()
    body = {"portions": 9, "portion_weight_g": 430}
    done = client.post(f"{P}/preparations/{chili['id']}/complete", headers=key, json=body)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "done" and done.json()["portions_made"] == 9
    again = client.post(f"{P}/preparations/{chili['id']}/complete", headers=key, json=body)
    assert again.json() == done.json()
    assert client.post(f"{P}/preparations/{chili['id']}/complete", headers=_key(), json=body).status_code == 409

    stock = {i["id"]: i for i in client.get(f"{P}/food-stock", params={"include_inactive": True}).json()["items"]}
    assert stock[old_rice["id"]]["status"] == "consumed"  # FEFO : la date la plus proche part d'abord
    assert stock[new_rice["id"]]["quantity"] == "0.700"  # 800 g − 500 g
    assert stock[beans["id"]]["quantity"] == "0.400" and stock[onions["id"]]["status"] == "consumed"
    portions = stock[done.json()["stock_item_id"]]
    assert (portions["kind"], portions["quantity"], portions["unit"], portions["source"]) == ("prepared", "9.000", "piece",
                                                                                              "preparation")
    assert portions["portion_weight_g"] == "430.0" and portions["expiry_type"] == "DLC"
    # 8 portions prévues à 600 kcal, 9 faites : 533,3 kcal par portion (pas de multiplication par la perte de masse).
    assert portions["calories"] == "533.3" and portions["protein_g"] == "22.2"
    assert db.scalar(select(Event).where(Event.user_id == user.id, Event.event_type == "pulse.preparation.done"))


def test_eating_a_planned_meal_marks_it_eaten(db, enabled):
    user = _user(db)
    client = _client(db, user)
    plan = _proposed(db, client, user)
    client.post(f"{P}/diet/plans/{plan['id']}/activate")
    planned = plan["meals"][0]
    draft = client.post(f"{P}/meals/drafts", headers=_key(),
                        json={"description": "Chili sin carne", "plan_meal_id": planned["id"], "calories": 600})
    assert draft.status_code == 201 and draft.json()["plan_meal_id"] == planned["id"]
    assert client.post(f"{P}/meals/{draft.json()['id']}/confirm", headers=_key(), json={"stock_lines": []}).status_code == 200
    meal = next(m for m in client.get(f"{P}/diet/plans/{plan['id']}").json()["meals"] if m["id"] == planned["id"])
    assert meal["status"] == "eaten" and meal["meal_id"] == draft.json()["id"]
    unknown = client.post(f"{P}/meals/drafts", headers=_key(), json={"description": "x", "plan_meal_id": str(uuid4())})
    assert unknown.status_code == 404


def test_validated_plan_creates_imperium_missions_when_allowed(db, enabled):
    user = _user(db)
    client = _client(db, user)
    set_parameter(db, code="pulse.diet_missions_enabled", value=True, origin="user", rationale_fr="Test.")
    db.commit()
    try:
        plan = _proposed(db, client, user)
        client.post(f"{P}/diet/plans/{plan['id']}/activate")
        titles = sorted(db.scalars(select(ImperiumMission.title).where(ImperiumMission.user_id == user.id)))
        assert titles == ["Cuisiner : Chili sin carne, Soupe de lentilles", "Faire les courses"]
        mission = db.scalar(select(ImperiumMission).where(ImperiumMission.user_id == user.id,
                                                          ImperiumMission.title == "Faire les courses"))
        assert mission.domain == "health" and mission.deadline_at.astimezone(UTC) > datetime.now(UTC)
    finally:
        set_parameter(db, code="pulse.diet_missions_enabled", value=False, origin="user", rationale_fr="Test.")
        db.commit()
