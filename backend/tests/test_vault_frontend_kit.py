"""Livraison Vault : contrats réels, exemples et téléchargement isolé."""

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


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def kit(tmp_path_factory):
    builder = load("build_vault_frontend_kit")
    output = tmp_path_factory.mktemp("vault-kit")
    archive = builder.build(output)
    return builder, output / builder.NAME, archive


def test_export_covers_actual_vault_routes_and_resolves_every_reference(kit):
    _, folder, _ = kit
    exported = json.loads((folder / "contracts/openapi.json").read_text())
    app = FastAPI()
    app.include_router(api_router, prefix="/api")
    actual = app.openapi()
    vault = {p: v for p, v in actual["paths"].items() if p.startswith(("/api/imperium/vault/", "/api/vault/"))}
    assert len(vault) >= 20
    assert {p: v for p, v in exported["paths"].items() if p in vault} == vault
    assert all(p.startswith(("/api/imperium/vault/", "/api/vault/", "/api/auth/")) for p in exported["paths"])

    def visit(value):
        if isinstance(value, dict):
            if "$ref" in value:
                target = exported
                for part in value["$ref"].removeprefix("#/").split("/"):
                    target = target[part]
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(exported)


def test_request_and_response_examples_validate_and_use_real_operations(kit):
    builder, folder, _ = kit
    schema = json.loads((folder / "contracts/openapi.json").read_text())
    requests = json.loads((folder / "examples/requests.json").read_text())
    responses = json.loads((folder / "examples/responses.json").read_text())
    assert len(requests) >= 12
    assert len(responses) >= 8
    for item in requests + responses:
        assert item["synthetic"] is True
        builder.MODELS[item["schema"]].model_validate(item["body"])
        assert item["method"].lower() in schema["paths"][item["path"]]


def test_archive_contains_only_manifested_files_and_expected_sources(kit):
    _, _, archive = kit
    with zipfile.ZipFile(archive) as zipped:
        manifest = json.loads(zipped.read("Vault_Frontend_Kit/manifest.json"))
        assert manifest["synthetic_examples_only"] is True
        assert len(manifest["files"]) >= 25
        assert set(zipped.namelist()) == {
            f"Vault_Frontend_Kit/{name}" for name in manifest["files"]
        } | {"Vault_Frontend_Kit/manifest.json"}
        for name, digest in manifest["files"].items():
            assert not set(Path(name).parts) & {"..", ".env", ".git", "__pycache__"}
            assert hashlib.sha256(zipped.read(f"Vault_Frontend_Kit/{name}")).hexdigest() == digest


def test_catalogue_maps_all_canonical_screens_and_future_features(kit):
    _, folder, _ = kit
    catalogue = json.loads((folder / "examples/ui_scenarios.json").read_text())
    assert {row["screen"] for row in catalogue["screens"]} == {
        f"VAU-{number:02}" for number in range(1, 13)
    }
    assert {"loading", "empty", "error", "offline", "conflict", "disabled", "stale"} <= set(catalogue["shared_states"])
    docs = "\n".join(p.read_text() for p in folder.glob("*.md"))
    for marker in ("stock_lines", "weekly_business_profit", "crypto", "append-only", "Idempotency-Key"):
        assert marker in docs
    screens = (folder / "03_ECRANS_ET_PARCOURS.md").read_text()
    for number in range(1, 13):
        assert f"VAU-{number:02}" in screens


def test_kit_preserves_canonical_floating_bubble_requirement(kit):
    _, folder, _ = kit
    assert (folder / "sources/docs_master/63_FRONTEND_ARCHITECTURE_V1.md").is_file()
    specification = (folder / "13_BULLE_FLOTTANTE.md").read_text()
    for requirement in ("SYSTEM_ALERT_WINDOW", "Idempotency-Key", "pending", "VAU-12"):
        assert requirement in specification
    for document in ("README.md", "02_CATALOGUE_FONCTIONNEL.md", "09_RECETTE_FRONTEND.md", "10_PROMPT_GENERATION.md"):
        assert "bulle" in (folder / document).read_text().lower()


def test_packaging_rejects_symlinks_and_non_document_files(tmp_path):
    builder = load("build_vault_frontend_kit")
    source = tmp_path / "source"
    source.mkdir()
    (source / "README.md").symlink_to(tmp_path / "private")
    with pytest.raises(ValueError):
        builder.copy_documents(source, tmp_path / "dest")
    (source / "README.md").unlink()
    (source / ".env").write_text("private")
    with pytest.raises(ValueError):
        builder.copy_documents(source, tmp_path / "dest")


def test_existing_delivery_is_never_overwritten(kit):
    builder, folder, archive = kit
    before = archive.read_bytes()
    with pytest.raises(FileExistsError):
        builder.build(folder.parent)
    assert archive.read_bytes() == before


@pytest.fixture
def server(kit):
    _, _, archive = kit
    module = load("serve_vault_frontend_kit")
    instance = module.make_server(archive, "127.0.0.1", 0, "vault-test-route")
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{instance.server_port}", archive
    instance.shutdown()
    instance.server_close()
    thread.join(timeout=5)


def test_download_get_head_and_tablet_page(server):
    base, archive = server
    with urlopen(base + "/vault-test-route/", timeout=5) as response:
        html = response.read()
        assert b"Vault_Frontend_Kit.zip" in html
        assert b"viewport" in html
    url = base + "/vault-test-route/Vault_Frontend_Kit.zip"
    with urlopen(url, timeout=5) as response:
        assert response.read() == archive.read_bytes()
        assert response.headers["Content-Type"] == "application/zip"
        assert "attachment" in response.headers["Content-Disposition"]
    with urlopen(Request(url, method="HEAD"), timeout=5) as response:
        assert response.read() == b""
        assert int(response.headers["Content-Length"]) == archive.stat().st_size


@pytest.mark.parametrize("path", ["/", "/.env", "/vault-test-route/../.env", "/vault-test-route/%2e%2e/backend/.env", "/vault-test-route/README.md", "/wrong/Vault_Frontend_Kit.zip"])
def test_unlisted_paths_cannot_expose_repository_files(server, path):
    base, _ = server
    with pytest.raises(HTTPError) as error:
        urlopen(base + path, timeout=5)
    assert error.value.code == 404


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_download_server_rejects_writes(server, method):
    base, _ = server
    with pytest.raises(HTTPError) as error:
        urlopen(Request(base + "/vault-test-route/", data=b"payload", method=method), timeout=5)
    assert error.value.code == 405


def test_expired_link_is_rejected(kit):
    _, _, archive = kit
    module = load("serve_vault_frontend_kit")
    instance = module.make_server(archive, "127.0.0.1", 0, "expired-vault", ttl_seconds=0)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(HTTPError) as error:
            urlopen(f"http://127.0.0.1:{instance.server_port}/expired-vault/Vault_Frontend_Kit.zip", timeout=5)
        assert error.value.code == 410
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("token", ["", "../escape", "bad?query", "<script>"])
def test_invalid_paths_are_rejected_before_binding(kit, token):
    _, _, archive = kit
    module = load("serve_vault_frontend_kit")
    with pytest.raises(ValueError):
        module.make_server(archive, "127.0.0.1", 0, token)
