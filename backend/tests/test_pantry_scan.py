"""Scan du placard (PUL-13, doc 37 §5) — lecture de la réponse, rapprochement, parcours complet."""
from __future__ import annotations

import io
import json
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.services.ai import ocr
from app.services.pulse import pantry_scan as ps


def _payload(items, quality="good", confidence=0.9, warnings=None):
    return {"result_type": ps.TASK, "summary": "Frigo", "confidence_score": confidence,
            "structured_result": {"items": items, "items_count": len(items), "image_quality": quality},
            "warnings": warnings or []}


def _item(name, quantity=None, unit="piece", category="dairy", expiry=None, confidence=0.9):
    return {"name_fr": name, "category": category, "estimated_quantity": quantity, "unit": unit,
            "expiry_visible": expiry, "confidence": confidence}


def test_parse_keeps_only_well_formed_items_and_cleans_fields() -> None:
    items, quality, confidence, summary, warnings = ps.parse_result(_payload([
        _item("Oeufs", 6), _item("  ", 1), {"name_fr": 3}, _item("Lait", -1, unit="bouteille", category="weird",
                                                                  expiry="2026-10-20", confidence=7),
    ], warnings=["une boîte cachée", 5]))
    assert [i["name"] for i in items] == ["Oeufs", "Lait"]
    assert items[1] == {"name": "Lait", "category": "other", "quantity": None, "unit": "piece",
                        "expiry_date": date(2026, 10, 20), "confidence": 1.0}
    assert (quality, confidence, summary, warnings) == ("good", 0.9, "Frigo", ["une boîte cachée"])


@pytest.mark.parametrize("payload", [None, [], {"structured_result": {}}, {"structured_result": {"items": "x"}}])
def test_parse_rejects_other_shapes(payload) -> None:
    assert ps.parse_result(payload) is None


@pytest.mark.parametrize(
    ("detected", "stock", "expected"),
    [("Oeufs", ["Œufs plein air", "Lait"], "Œufs plein air"), ("tomates", ["Tomate"], "Tomate"),
     ("Riz basmati", ["Riz"], "Riz"), ("Beurre", ["Lait"], None), ("de la", ["Lait"], None)],
)
def test_matching(detected, stock, expected) -> None:
    rows = [SimpleNamespace(name=name, created_at=index) for index, name in enumerate(stock)]
    match = ps.match_stock(detected, rows)
    assert (match.name if match else None) == expected


def test_vision_client_sends_task_prompt_and_image(monkeypatch) -> None:
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            seen["path"] = self.path
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(_payload([_item("Oeufs", 6)])).encode())

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    settings = SimpleNamespace(ocr_enabled=True, ocr_base_url=f"http://127.0.0.1:{server.server_address[1]}",
                               ocr_request_timeout_seconds=2)
    try:
        result = ocr.analyze_image(b"JPG", task=ps.TASK, prompt=ocr.load_prompt(ps.PROMPT), content_type="image/jpeg",
                                   settings=settings)
    finally:
        server.shutdown()
    assert seen["path"] == "/vision" and seen["body"]["task"] == ps.TASK and seen["body"]["image_base64"] == "SlBH"
    assert seen["body"]["prompt"].startswith("You are identifying food items") and "# Prompt" not in seen["body"]["prompt"]
    assert result["structured_result"]["items"][0]["name_fr"] == "Oeufs"


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
        {"id": str(user_id), "email": f"scan-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _client(db, user, analyze):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_user, get_db
    from app.api.v1.routes import imperium_pulse_stock as routes

    ps_default = ps._default_analyzer
    ps._default_analyzer = lambda: analyze
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/imperium/pulse")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app), lambda: setattr(ps, "_default_analyzer", ps_default)


BASE = "/api/imperium/pulse/food-stock"


def _scan(client, key=None):
    return client.post(f"{BASE}/scans", headers={"X-Filename": "frigo.jpg", "Content-Type": "image/jpeg",
                                                  "Idempotency-Key": key or uuid4().hex}, content=b"JPEGDATA")


@pytest.mark.postgres
def test_full_flow_proposes_a_diff_and_writes_only_kept_lines(db) -> None:
    from sqlalchemy import select

    from app.models.event import Event
    from app.models.imperium import PulsePantryScan

    user = _user(db)
    analyze = lambda data, content_type: _payload([  # noqa: E731
        _item("Oeufs", 6), _item("Yaourt nature", 4, expiry="2026-10-22"), _item("Moutarde", category="condiment", confidence=0.4)])
    client, restore = _client(db, user, analyze)
    try:
        existing = client.post(BASE, headers={"Idempotency-Key": uuid4().hex}, json={"name": "Œufs plein air", "quantity": 12}).json()
        scan = _scan(client)
        assert scan.status_code == 201
        lines = {line["name"]: line for line in scan.json()["lines"]}
        assert lines["Oeufs"]["action"] == "update" and lines["Oeufs"]["stock_item_id"] == existing["id"]
        assert lines["Oeufs"]["stock_quantity"] == 12 and lines["Oeufs"]["stock_version"] == 1
        assert lines["Yaourt nature"]["action"] == "add" and lines["Yaourt nature"]["expiry_type"] == "DLC"
        assert lines["Moutarde"]["quantity"] == 1 and lines["Moutarde"]["quantity_estimated"] is False
        assert lines["Moutarde"]["low_confidence"] is True
        assert db.scalar(select(PulsePantryScan.proposal).where(PulsePantryScan.id == scan.json()["id"])) is not None
        assert client.get(BASE).json()["items"][0]["quantity"] == "12.000"  # rien d'écrit avant validation

        validated = client.post(f"{BASE}/scans/{scan.json()['id']}/validate", headers={"Idempotency-Key": "v"}, json={"lines": [
            {"action": "update", "name": "Oeufs", "quantity": 6, "stock_item_id": existing["id"], "stock_version": 1},
            {"action": "add", "name": "Yaourt nature", "quantity": 4, "expiry_type": "DLC", "expiry_date": "2026-10-22",
             "category": "dairy"},
        ]})  # la moutarde est décochée
        assert validated.status_code == 200 and validated.json()["status"] == "validated"
        stock = {item["name"]: item for item in client.get(BASE).json()["items"]}
        assert set(stock) == {"Œufs plein air", "Yaourt nature"}
        assert stock["Œufs plein air"]["quantity"] == "6.000" and stock["Œufs plein air"]["version"] == 2
        assert stock["Yaourt nature"]["source"] == "pantry_scan" and stock["Yaourt nature"]["confidence"] == "0.900"
        replay = client.post(f"{BASE}/scans/{scan.json()['id']}/validate", headers={"Idempotency-Key": "v"}, json={"lines": []})
        assert replay.status_code == 200 and len(replay.json()["stock_items"]) == 2
        assert len(client.get(BASE).json()["items"]) == 2
        types = [e.event_type for e in db.scalars(select(Event).where(Event.user_id == user.id))]
        assert "pulse.pantry_scan.analyzed" in types and "pulse.pantry_scan.validated" in types
    finally:
        restore()


@pytest.mark.postgres
def test_stale_stock_version_rolls_back_the_whole_validation(db) -> None:
    user = _user(db)
    client, restore = _client(db, user, lambda data, content_type: _payload([_item("Lait", 2), _item("Beurre", 1)]))
    try:
        milk = client.post(BASE, headers={"Idempotency-Key": uuid4().hex}, json={"name": "Lait", "quantity": 1}).json()
        scan = _scan(client).json()
        client.patch(f"{BASE}/{milk['id']}", headers={"Idempotency-Key": uuid4().hex}, json={"version": 1, "quantity": 3})
        conflict = client.post(f"{BASE}/scans/{scan['id']}/validate", headers={"Idempotency-Key": "x"}, json={"lines": [
            {"action": "add", "name": "Beurre", "quantity": 1},
            {"action": "update", "name": "Lait", "quantity": 2, "stock_item_id": milk["id"], "stock_version": 1},
        ]})
        assert conflict.status_code == 409 and conflict.json()["current"]["quantity"] == "3.000"
        assert [item["name"] for item in client.get(BASE).json()["items"]] == ["Lait"]  # le beurre n'est pas entré
        assert client.get(f"{BASE}/scans/{scan['id']}").json()["status"] == "ready"
    finally:
        restore()


@pytest.mark.postgres
@pytest.mark.parametrize(
    ("analyze", "message"),
    [(None, "pas encore activée"), ("down", "ne répond pas"), ("bad", "illisible"),
     (lambda data, content_type: {"pas": "le format"}, "illisible")],
)
def test_failures_are_readable_and_nothing_is_kept(db, analyze, message) -> None:
    def down(data, content_type):
        raise ocr.OcrServiceUnreachable("x")

    def bad(data, content_type):
        raise ocr.OcrError("x")

    analyze = {"down": down, "bad": bad}.get(analyze, analyze) if isinstance(analyze, str) else analyze
    user = _user(db)
    scan, _ = ps.create_scan(db, current_user=user, filename="f.jpg", content_type="image/jpeg", stream=io.BytesIO(b"JPG"),
                             idempotency_key=uuid4().hex, analyze=analyze)
    assert scan.status == "failed" and message in scan.error_message and scan.lines == []


@pytest.mark.postgres
def test_empty_or_blurry_photo_warns(db) -> None:
    user = _user(db)
    scan, _ = ps.create_scan(db, current_user=user, filename="f.jpg", content_type="image/jpeg", stream=io.BytesIO(b"JPG"),
                             idempotency_key=uuid4().hex, analyze=lambda data, content_type: _payload([], quality="poor"))
    assert scan.status == "ready" and scan.lines == []
    assert scan.warnings[:2] == ["Aucun aliment détecté. Reprends la photo ou ajoute les produits à la main.",
                                 "Photo trop floue. Reprendre une photo ?"]


@pytest.mark.postgres
def test_upload_rules_replay_cancel_and_scope(db) -> None:
    user, other = _user(db), _user(db)
    analyze = lambda data, content_type: _payload([_item("Oeufs", 6)])  # noqa: E731
    with pytest.raises(ps.PantryScanFileError):
        ps.create_scan(db, current_user=user, filename="f.pdf", content_type="application/pdf", stream=io.BytesIO(b"x"),
                       idempotency_key="k0", analyze=analyze)
    first, _ = ps.create_scan(db, current_user=user, filename="f.jpg", content_type="image/jpeg", stream=io.BytesIO(b"x"),
                              idempotency_key="k1", analyze=analyze)
    again, duplicate = ps.create_scan(db, current_user=user, filename="f.jpg", content_type="image/jpeg",
                                      stream=io.BytesIO(b"x"), idempotency_key="k1", analyze=analyze)
    assert duplicate and again.id == first.id
    assert ps.cancel_scan(db, current_user=user, scan_id=first.id).status == "cancelled"
    with pytest.raises(ps.PantryScanStateError):
        ps.validate_scan(db, current_user=user, scan_id=first.id, payload=ps.PantryScanValidateRequest(lines=[]))
    with pytest.raises(ps.PantryScanNotFoundError):
        ps.get_scan(db, current_user=other, scan_id=first.id)
