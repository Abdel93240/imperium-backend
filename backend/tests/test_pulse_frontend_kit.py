"""Contrats du dossier Pulse et isolation du serveur de téléchargement."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import threading
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from fastapi import FastAPI

from app.api.v1.router import api_router

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def kit(tmp_path_factory):
    builder = _load("build_pulse_frontend_kit")
    output = tmp_path_factory.mktemp("pulse-kit")
    archive = builder.build(output)
    return builder, output, archive


def test_export_covers_every_current_pulse_operation_and_resolves_all_refs(kit):
    _, output, _ = kit
    schema = json.loads((output / "Pulse_Frontend_Kit/contracts/openapi.json").read_text())
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    current = app.openapi()
    for path, operations in current["paths"].items():
        if path.startswith("/api/imperium/pulse/"):
            assert schema["paths"][path] == operations

    def check(value):
        if isinstance(value, dict):
            if "$ref" in value:
                target = schema
                for part in value["$ref"].removeprefix("#/").split("/"):
                    target = target[part]
            for child in value.values():
                check(child)
        elif isinstance(value, list):
            for child in value:
                check(child)

    check(schema)
    assert not any(path.startswith("/api/internal") for path in schema["paths"])


def test_archive_manifest_matches_all_payloads_without_private_files(kit):
    _, _, archive = kit
    with zipfile.ZipFile(archive) as zipped:
        names = zipped.namelist()
        manifest = json.loads(zipped.read("Pulse_Frontend_Kit/manifest.json"))
        assert len(names) > 20
        for name in names:
            assert name.startswith("Pulse_Frontend_Kit/")
            assert ".." not in Path(name).parts
            assert not set(Path(name).parts) & {".env", ".git", "__pycache__", "db_archives"}
        assert set(names) == {
            f"Pulse_Frontend_Kit/{name}" for name in manifest["files"]
        } | {"Pulse_Frontend_Kit/manifest.json"}
        for name, digest in manifest["files"].items():
            assert hashlib.sha256(zipped.read(f"Pulse_Frontend_Kit/{name}")).hexdigest() == digest


def test_examples_validate_against_actual_request_models(kit):
    builder, output, _ = kit
    examples = json.loads((output / "Pulse_Frontend_Kit/examples/requests.json").read_text())
    assert len(examples) >= 12
    for example in examples:
        builder.REQUEST_MODELS[example["schema"]].model_validate(example["body"])


def test_medical_rule_example_uses_the_current_workout_constraint_contract():
    """Un exemple obsolète ne doit pas empêcher la génération de toute la livraison."""
    builder = _load("build_pulse_frontend_kit")

    examples = builder.request_examples()
    example = next(row for row in examples if row["schema"] == "MedicalRuleCreate")

    model = builder.REQUEST_MODELS["MedicalRuleCreate"].model_validate(example["body"])
    assert example["path"] == "/api/imperium/pulse/medical-rules"
    assert model.rule_type == "workout_limit"
    assert model.source_document_id is None
    assert example["synthetic"] is True


def test_kit_documents_all_canonical_screens_and_unavailable_features(kit):
    _, output, _ = kit
    screens = (output / "Pulse_Frontend_Kit/03_ECRANS_ET_PARCOURS.md").read_text()
    for number in range(1, 15):
        assert f"PUL-{number:02}" in screens
    integration = (output / "Pulse_Frontend_Kit/05_INTEGRATION_API.md").read_text()
    for marker in ("PULSE_BOARD_DISABLED", "PULSE_PROGRAMS_DISABLED", "corps brut", "Idempotency-Key"):
        assert marker in integration


def test_packaging_rejects_symlinks_and_unexpected_source_files(tmp_path):
    builder = _load("build_pulse_frontend_kit")
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").symlink_to(ROOT / "backend/.env")
    with pytest.raises(ValueError):
        builder.copy_documents(source, tmp_path / "dest")
    (source / "README.md").unlink()
    (source / ".env").write_text("private")
    with pytest.raises(ValueError):
        builder.copy_documents(source, tmp_path / "dest")


def test_build_refuses_to_overwrite_an_existing_delivery(kit):
    builder, output, archive = kit
    original = archive.read_bytes()
    with pytest.raises(FileExistsError):
        builder.build(output)
    assert archive.read_bytes() == original


def test_ui_scenarios_cover_each_screen_and_shared_failure_states(kit):
    _, output, _ = kit
    data = json.loads((output / "Pulse_Frontend_Kit/examples/ui_scenarios.json").read_text())
    assert data["synthetic"] is True
    assert {item["screen"] for item in data["screens"]} == {
        f"PUL-{number:02}" for number in range(1, 15)
    }
    assert {"loading", "empty", "error", "offline", "conflict", "disabled"} <= set(
        data["shared_states"]
    )


@pytest.fixture
def download_server(kit):
    _, _, archive = kit
    module = _load("serve_pulse_frontend_kit")
    server = module.make_server(archive, "127.0.0.1", 0, "test-download-route")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", archive
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def test_download_get_and_head_return_exact_zip_without_listing(download_server):
    base, archive = download_server
    url = f"{base}/test-download-route/Pulse_Frontend_Kit.zip"
    with urlopen(url, timeout=5) as response:
        assert response.read() == archive.read_bytes()
        assert response.headers["Content-Type"] == "application/zip"
        assert "attachment" in response.headers["Content-Disposition"]
    with urlopen(Request(url, method="HEAD"), timeout=5) as response:
        assert response.read() == b""
        assert int(response.headers["Content-Length"]) == archive.stat().st_size
    with urlopen(f"{base}/test-download-route/", timeout=5) as response:
        assert b"Pulse_Frontend_Kit.zip" in response.read()


@pytest.mark.parametrize("path", [
    "/", "/.env", "/test-download-route/../.env",
    "/test-download-route/%2e%2e/backend/.env",
    "/test-download-route/README.md", "/wrong/Pulse_Frontend_Kit.zip",
])
def test_download_server_does_not_expose_other_paths(download_server, path):
    base, _ = download_server
    with pytest.raises(HTTPError) as error:
        urlopen(base + path, timeout=5)
    assert error.value.code == 404


def test_download_server_rejects_uploads(download_server):
    base, _ = download_server
    with pytest.raises(HTTPError) as error:
        urlopen(Request(f"{base}/test-download-route/", data=b"payload"), timeout=5)
    assert error.value.code == 405


def test_expired_link_cannot_download_archive(kit):
    _, _, archive = kit
    module = _load("serve_pulse_frontend_kit")
    server = module.make_server(archive, "127.0.0.1", 0, "expired-route", ttl_seconds=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(HTTPError) as error:
            urlopen(
                f"http://127.0.0.1:{server.server_port}/expired-route/Pulse_Frontend_Kit.zip",
                timeout=5,
            )
        assert error.value.code == 410
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("token", ["", "../escape", "bad?query", "<script>"])
def test_server_rejects_invalid_download_paths(kit, token):
    _, _, archive = kit
    module = _load("serve_pulse_frontend_kit")
    with pytest.raises(ValueError):
        module.make_server(archive, "127.0.0.1", 0, token)
