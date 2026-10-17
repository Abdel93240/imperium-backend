"""Règles de fichiers de Nourrir l'IA (doc 70 §6) — tests unitaires."""
import io
import zipfile

import pytest

from app.services.ai import knowledge_files as kf


@pytest.mark.parametrize(
    ("name", "kind"),
    [
        ("releve.PDF", "document"), ("notes.md", "document"), ("budget.xlsx", "document"), ("cv.odt", "document"),
        ("photo.HEIC", "image"), ("capture_01.png", "image"), ("note.m4a", "audio"), ("voix.opus", "audio"),
        ("clip.mov", "video"), ("lot.zip", "archive"),
    ],
)
def test_allow_list(name, kind) -> None:
    assert kf.classify(name) == kind


@pytest.mark.parametrize("name", ["setup.exe", "script.sh", "page.info", "archive.rar", "lot.7z", "sans_extension", "photo.png.exe"])
def test_everything_else_is_rejected(name) -> None:
    assert kf.classify(name) is None


def test_size_limits_per_kind() -> None:
    assert kf.max_bytes("document") == kf.max_bytes("image") == 25 * 1024 * 1024
    assert kf.max_bytes("audio") == kf.max_bytes("video") == 500 * 1024 * 1024


@pytest.mark.parametrize(
    ("raw", "safe"),
    [("../../etc/passwd.txt", "passwd.txt"), ("Relevé d'octobre.pdf", "Releve_d_octobre.pdf"), ("a/b\\c.png", "c.png")],
)
def test_filenames_are_sanitized(raw, safe) -> None:
    assert kf.safe_filename(raw) == safe


@pytest.mark.parametrize(
    ("status", "ui"),
    [("uploading", "to_analyze"), ("to_analyze", "to_analyze"), ("analyzing", "to_analyze"), ("to_validate", "to_validate"),
     ("validated", "saved"), ("vectorized", "saved"), ("failed", "error")],
)
def test_ui_states_match_the_mockup(status, ui) -> None:
    assert kf.ui_state(status) == ui


def _zip(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_zip_is_expanded_with_the_same_rules() -> None:
    data = _zip({"a.txt": b"hello", "img/b.png": b"\x89PNG", "evil.exe": b"MZ", "inner.zip": _zip({"x.txt": b"x"})})
    accepted, rejected = kf.expand_zip(data)
    assert sorted(name for name, _ in accepted) == ["a.txt", "b.png"]
    assert dict(rejected) == {"evil.exe": "type non accepté", "inner.zip": "archive imbriquée refusée"}


def test_zip_bomb_guards() -> None:
    too_many = _zip({f"f{i}.txt": b"x" for i in range(kf.ZIP_MAX_FILES + 1)})
    with pytest.raises(kf.KnowledgeFileError):
        kf.expand_zip(too_many)
    with pytest.raises(kf.KnowledgeFileError):
        kf.expand_zip(b"not a zip")


def test_zip_inner_size_limit(monkeypatch) -> None:
    monkeypatch.setattr(kf, "ZIP_MAX_TOTAL_BYTES", 10)
    with pytest.raises(kf.KnowledgeFileError):
        kf.expand_zip(_zip({"a.txt": b"x" * 20}))


def test_knowledge_inbox_routes_are_registered() -> None:
    from app.api.v1.router import api_router

    paths = {(route.path, method) for route in api_router.routes for method in getattr(route, "methods", set())}
    for expected in [
        ("/ai/knowledge-inbox/items", "POST"), ("/ai/knowledge-inbox/items", "GET"),
        ("/ai/knowledge-inbox/items/{item_id}/sources", "POST"), ("/ai/knowledge-inbox/items/{item_id}/analyze", "POST"),
        ("/ai/knowledge-inbox/items/{item_id}/extraction", "PATCH"), ("/ai/knowledge-inbox/items/{item_id}/validate", "POST"),
        ("/ai/knowledge-inbox/items/{item_id}/cancel", "POST"), ("/ai/knowledge-inbox/items/{item_id}", "DELETE"),
        ("/ai/knowledge-inbox/items/{item_id}/sources/{document_id}", "GET"),
    ]:
        assert expected in paths, expected


def test_seeded_job_handler_resolves() -> None:
    from app.services.ai.knowledge_inbox_runner import knowledge_inbox_job
    from app.services.runner.engine import resolve_handler

    assert resolve_handler("app.services.ai.knowledge_inbox_runner:knowledge_inbox_job") is knowledge_inbox_job
