"""PostgreSQL : analyses de sang — reconnues dans Nourrir l'IA, corrigées, validées vers Pulse, lues dans Santé."""
from __future__ import annotations

import io
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("pulse labs DB tests")

pytestmark = pytest.mark.postgres

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.deps import get_current_user, get_db  # noqa: E402
from app.api.v1.routes import imperium_pulse_health, knowledge_inbox as inbox_routes  # noqa: E402
from app.models.ai import AIMemory  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.pulse import PulseLabResult  # noqa: E402
from app.schemas.knowledge_inbox import InboxItemCreate  # noqa: E402
from app.services.ai import knowledge_inbox as inbox  # noqa: E402
from app.services.ai import knowledge_inbox_runner as runner  # noqa: E402
from app.services.pulse import health_consent, labs  # noqa: E402

P = "/api/imperium/pulse"
INBOX = "/api/ai/knowledge-inbox"
REPORT = b"""LABORATOIRE DE BIOLOGIE MEDICALE - Preleve le 12/09/2026
Hemoglobine 13,1 g/dL (13,0 - 17,0)
Ferritine 18 ug/L (30 - 400)
TSH 2,1 mUI/L (0,4 - 4,0)
Valeurs de reference du laboratoire"""


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


@pytest.fixture(autouse=True)
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(inbox, "storage_root", lambda: tmp_path)


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"labs-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _client(db, user) -> TestClient:
    app = FastAPI()
    app.include_router(imperium_pulse_health.router, prefix=P)
    app.include_router(inbox_routes.router, prefix=INBOX)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def _fake_extract(results, measured="2026-09-12"):
    def extract(db, *, text, item_id=None):
        assert "Ferritine" in text  # le texte lu est bien transmis
        return results, measured, "local"
    return extract


def _deposit(db, user, extract, report: bytes = REPORT, context: str | None = None) -> str:
    item = inbox.create_item(db, current_user=user, payload=InboxItemCreate(context_text=context, entry_app="pulse"),
                             idempotency_key=f"i-{uuid4().hex}")
    inbox.add_source(db, current_user=user, item_id=item.id, filename="bilan.txt", content_type="text/plain",
                     stream=io.BytesIO(report))
    inbox.request_analysis(db, current_user=user, item_id=item.id)
    ctx = SimpleNamespace(db=db, items_in=None, items_out=None, detail={})
    runner.process_inbox(ctx, call_model=None, embed_texts=None, recognize_file=None, extract_labs=extract)
    db.commit()
    return str(item.id)


VALUES = [{"analyte": "Hémoglobine", "value": "13.1", "value_text": None, "unit": "g/dL", "ref_low": "13", "ref_high": "17",
           "ref_text": None},
          {"analyte": "Ferritine", "value": "18", "value_text": None, "unit": "µg/L", "ref_low": "30", "ref_high": "400",
           "ref_text": None}]


def test_detection_keys_and_parsing():
    assert labs.looks_like_lab(REPORT.decode())
    assert labs.looks_like_lab("", "voici ma prise de sang")
    assert not labs.looks_like_lab("Trois propositions de courses Bolt, j'ai refusé la première.")
    assert labs.analyte_key("Hémoglobine glyquée (HbA1c)") == "hemoglobine glyquee hba1c"
    results, measured = labs.parse({"measured_on": "2026-09-12", "results": [
        {"analyte": "Ferritine", "value": 18, "value_text": None, "unit": "ug/L", "ref_low": 30, "ref_high": 400, "ref_text": None},
        {"analyte": "Illisible", "value": None, "value_text": None, "unit": None, "ref_low": None, "ref_high": None, "ref_text": None},
        {"analyte": "HIV", "value": None, "value_text": "négatif", "unit": None, "ref_low": None, "ref_high": None, "ref_text": None}]})
    assert [r["analyte"] for r in results] == ["Ferritine", "HIV"] and measured == "2026-09-12"
    assert labs.parse({"measured_on": "12/09", "results": []}) == ([], None)


def test_blood_test_goes_from_the_inbox_to_pulse_after_consent(db):
    user = _user(db)
    client = _client(db, user)
    item_id = _deposit(db, user, _fake_extract(VALUES))
    item = client.get(f"{INBOX}/items/{item_id}").json()
    draft = item["extraction_draft"]
    assert item["status"] == "to_validate" and draft["proposed_destination"] == "lab_results"
    assert [r["analyte"] for r in draft["lab_results"]] == ["Hémoglobine", "Ferritine"] and draft["lab_engine"] == "local"

    # Correction avant validation : l'OCR a mal lu l'hémoglobine.
    corrected = [{**VALUES[0], "value": "12.4"}, VALUES[1], {"analyte": "TSH", "value": "2.1", "unit": "mUI/L",
                                                              "ref_low": "0.4", "ref_high": "4"}]
    patched = client.patch(f"{INBOX}/items/{item_id}/extraction", json={"lab_results": corrected, "measured_on": "2026-09-12"})
    assert patched.status_code == 200 and patched.json()["extraction_draft"]["lab_results"][0]["value"] == "12.4"

    refused = client.post(f"{INBOX}/items/{item_id}/validate", json={"destination": "lab_results"})
    assert refused.status_code == 403 and refused.json()["code"] == "CONSENT_REQUIRED"
    assert client.get(f"{P}/lab-results/latest").status_code == 403

    health_consent.grant(db, current_user=user, domain="medical", text_version=health_consent.TEXT_VERSION)
    assert client.get(f"{P}/lab-results/latest").json()["pending_inbox"] == 1
    validated = client.post(f"{INBOX}/items/{item_id}/validate", json={"destination": "lab_results"})
    assert validated.status_code == 200 and validated.json()["destination"] == "lab_results"
    latest = {i["analyte"]: i for i in client.get(f"{P}/lab-results/latest").json()["items"]}
    assert (latest["Hémoglobine"]["value"], latest["Hémoglobine"]["position"]) == ("12.4000", "below")
    assert latest["Ferritine"]["position"] == "below" and latest["TSH"]["position"] == "within"
    assert latest["TSH"]["measured_on"] == "2026-09-12" and latest["TSH"]["previous"] is None

    # Rien dans la mémoire vectorisée, même au passage de la vectorisation.
    runner.process_inbox(SimpleNamespace(db=db, items_in=None, items_out=None, detail={}), call_model=None,
                         embed_texts=lambda texts: [[0.0] * 1024 for _ in texts], recognize_file=None)
    assert db.scalar(select(AIMemory).where(AIMemory.source_id == item_id)) is None

    # Une seconde prise de sang : la dernière valeur et la précédente.
    second = _deposit(db, user, _fake_extract([{**VALUES[1], "value": "42"}], "2026-10-20"))
    client.post(f"{INBOX}/items/{second}/validate", json={"destination": "lab_results"})
    ferritin = next(i for i in client.get(f"{P}/lab-results/latest").json()["items"] if i["analyte"] == "Ferritine")
    assert (ferritin["value"], ferritin["position"], ferritin["count"]) == ("42.0000", "within", 2)
    assert ferritin["previous"] == {"value": "18.0000", "value_text": None, "measured_on": "2026-09-12"}
    assert len(client.get(f"{P}/lab-results", params={"analyte": "ferritine"}).json()["items"]) == 2

    # Supprimer l'élément de Nourrir l'IA supprime ses valeurs.
    assert client.delete(f"{INBOX}/items/{second}").status_code in (200, 204)
    ferritin = next(i for i in client.get(f"{P}/lab-results/latest").json()["items"] if i["analyte"] == "Ferritine")
    assert ferritin["value"] == "18.0000" and ferritin["count"] == 1


def test_without_a_brain_the_user_types_the_values(db):
    user = _user(db)
    client = _client(db, user)
    health_consent.grant(db, current_user=user, domain="medical", text_version=health_consent.TEXT_VERSION)
    item_id = _deposit(db, user, lambda db, *, text, item_id=None: ([], None, None))
    draft = client.get(f"{INBOX}/items/{item_id}").json()["extraction_draft"]
    assert draft["proposed_destination"] == "lab_results" and draft["lab_results"] == [] and draft["lab_engine"] is None
    empty = client.post(f"{INBOX}/items/{item_id}/validate", json={"destination": "lab_results"})
    assert empty.status_code == 409 and "Aucune valeur" in empty.json()["detail"]
    client.patch(f"{INBOX}/items/{item_id}/extraction", json={"lab_results": [VALUES[1]]})
    no_date = client.post(f"{INBOX}/items/{item_id}/validate", json={"destination": "lab_results"})
    assert no_date.status_code == 409 and "Date" in no_date.json()["detail"]
    client.patch(f"{INBOX}/items/{item_id}/extraction", json={"measured_on": "2026-09-12"})
    assert client.post(f"{INBOX}/items/{item_id}/validate", json={"destination": "lab_results"}).status_code == 200
    bad = client.patch(f"{INBOX}/items/{item_id}/extraction", json={"lab_results": [{"analyte": "Fer"}]})
    assert bad.status_code == 422  # ni valeur ni texte


def test_manual_entry_and_delete(db):
    user = _user(db)
    client = _client(db, user)
    body = {"analyte": "Vitamine D", "value": "21", "unit": "ng/mL", "ref_low": "30", "ref_high": "100", "measured_on": "2026-10-01"}
    assert client.post(f"{P}/lab-results", headers={"Idempotency-Key": "k"}, json=body).status_code == 403
    health_consent.grant(db, current_user=user, domain="medical", text_version=health_consent.TEXT_VERSION)
    created = client.post(f"{P}/lab-results", headers={"Idempotency-Key": "k"}, json=body)
    assert created.status_code == 201 and created.json()["source"] == "manual"
    assert client.post(f"{P}/lab-results", headers={"Idempotency-Key": "k"}, json=body).status_code == 200
    assert labs.out_of_range_lines(db, user) == ["- Vitamine D : 21.0000 ng/mL (sous la norme du labo 30.0000–100.0000, le 2026-10-01)"]
    assert client.delete(f"{P}/lab-results/{created.json()['id']}").status_code == 204
    assert db.scalar(select(PulseLabResult).where(PulseLabResult.user_id == user.id)) is None


def test_planner_prompt_mentions_out_of_range_values_only_with_consent(db):
    from app.models.pulse import PulseDietPlan
    from app.services.pulse import diet_planner

    user = _user(db)
    db.add(PulseLabResult(user_id=user.id, analyte="Ferritine", analyte_key="ferritine", value=18, unit="µg/L", ref_low=30,
                          ref_high=400, measured_on=date(2026, 9, 12), source="manual"))
    db.commit()
    plan = PulseDietPlan(user_id=user.id, week_start=date(2026, 10, 26), status="generating", idempotency_key="k",
                         request_hash="h")
    days = [date(2026, 10, 26)]
    assert "Analyses de sang" not in diet_planner.build_prompt(db, user, plan, days, {}, {})
    health_consent.grant(db, current_user=user, domain="medical", text_version=health_consent.TEXT_VERSION)
    prompt = diet_planner.build_prompt(db, user, plan, days, {}, {})
    assert "Ferritine" in prompt and "sous la norme du labo" in prompt and "sans diagnostic" in prompt
