"""PostgreSQL : Nourrir l'IA (doc 70) — import, analyse, validation, vectorisation, suppression."""
from __future__ import annotations

import io
import zipfile
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("knowledge inbox DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.ai import AIMemory  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.imperium import ImperiumProject  # noqa: E402
from app.schemas.knowledge_inbox import ExtractionUpdate, InboxItemCreate, InboxValidateRequest  # noqa: E402
from app.services.ai import knowledge_inbox as inbox  # noqa: E402
from app.services.ai import knowledge_inbox_runner as runner  # noqa: E402
from app.services.ai.knowledge_files import KnowledgeFileError  # noqa: E402


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
    return tmp_path


def _user(db) -> User:
    user_id = uuid4()
    db.execute(
        text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) VALUES (:id, :email, FALSE, now(), now())"),
        {"id": str(user_id), "email": f"inbox-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _item(db, user, context="Voici trois propositions de courses Bolt. J'ai refusé la première."):
    return inbox.create_item(db, current_user=user, payload=InboxItemCreate(context_text=context, entry_app="imperium"),
                             idempotency_key=f"i-{uuid4().hex}")


def _upload(db, user, item, name, data: bytes):
    return inbox.add_source(db, current_user=user, item_id=item.id, filename=name, content_type="application/octet-stream",
                            stream=io.BytesIO(data))


def _run(db, *, model=None, embed=None):
    ctx = SimpleNamespace(db=db, items_in=None, items_out=None, detail={})
    runner.process_inbox(ctx, call_model=model, embed_texts=embed)
    db.commit()
    return ctx


def _fake_embed(texts):
    return [[0.01] * 1024 for _ in texts]


def test_full_path_import_analyze_validate_vectorize(db, storage) -> None:
    user = _user(db)
    item = _item(db, user)
    source = _upload(db, user, item, "exemples.txt", b"01 refusee\n02 acceptee\n03 sans reponse")
    assert (storage / source.storage_pointer).read_bytes().startswith(b"01 refusee")  # source toujours conservée

    inbox.request_analysis(db, current_user=user, item_id=item.id)
    _run(db)
    analyzed = inbox.get_item(db, current_user=user, item_id=item.id)
    assert analyzed.status == "to_validate" and analyzed.ui_state == "to_validate"
    assert "propositions de courses" in analyzed.extraction_draft["summary"]
    assert analyzed.extraction_draft["sources_read"] == ["exemples.txt"]

    inbox.update_extraction(db, current_user=user, item_id=item.id,
                            payload=ExtractionUpdate(summary="Trois courses : refusée, acceptée, sans réponse à temps."))
    inbox.validate_item(db, current_user=user, item_id=item.id, payload=InboxValidateRequest(destination="memory"))
    assert db.scalar(select(AIMemory).where(AIMemory.source_id == str(item.id))) is None  # rien avant la vectorisation

    _run(db, embed=_fake_embed)
    saved = inbox.get_item(db, current_user=user, item_id=item.id)
    memories = list(db.scalars(select(AIMemory).where(AIMemory.source_table == "knowledge_inbox_items", AIMemory.source_id == str(item.id))))
    assert saved.status == "vectorized" and saved.ui_state == "saved" and memories
    assert "sans réponse à temps" in memories[0].content  # la version corrigée, pas le brouillon
    assert memories[0].memory_type == "user_knowledge" and memories[0].source_domain == "system"
    types = set(db.scalars(select(Event.event_type).where(Event.user_id == user.id)))
    assert {"inbox.document.uploaded", "inbox.document.analyzed", "inbox.document.validated", "inbox.document.vectorized"} <= types


def test_nothing_is_vectorized_without_validation(db) -> None:
    user = _user(db)
    item = _item(db, user)
    _upload(db, user, item, "a.txt", b"contenu")
    inbox.request_analysis(db, current_user=user, item_id=item.id)
    _run(db, embed=_fake_embed)
    assert db.scalar(select(AIMemory).where(AIMemory.source_id == str(item.id))) is None


def test_gpu_down_keeps_item_validated_for_a_later_wake(db) -> None:
    user = _user(db)
    item = _item(db, user)
    inbox.request_analysis(db, current_user=user, item_id=item.id)
    _run(db)
    inbox.validate_item(db, current_user=user, item_id=item.id, payload=InboxValidateRequest(destination="memory"))
    _run(db, embed=None)  # embeddings désactivés / GPU injoignable
    assert inbox.get_item(db, current_user=user, item_id=item.id).status == "validated"


def test_unreadable_files_without_context_fail_then_retry(db) -> None:
    user = _user(db)
    item = _item(db, user, context=None)
    _upload(db, user, item, "releve.pdf", b"%PDF-1.7 binary")
    inbox.request_analysis(db, current_user=user, item_id=item.id)
    _run(db)
    failed = inbox.get_item(db, current_user=user, item_id=item.id)
    assert failed.status == "failed" and failed.ui_state == "error" and "Erreur de lecture" in failed.error_message

    inbox.retry_item(db, current_user=user, item_id=item.id)
    assert inbox.get_item(db, current_user=user, item_id=item.id).status == "to_analyze"


def test_unread_binary_sources_are_listed_in_the_draft(db) -> None:
    user = _user(db)
    item = _item(db, user)
    _upload(db, user, item, "capture.png", b"\x89PNG")
    inbox.request_analysis(db, current_user=user, item_id=item.id)
    _run(db)
    draft = inbox.get_item(db, current_user=user, item_id=item.id).extraction_draft
    assert draft["sources_unread"] == ["capture.png"]


def test_local_model_summary_is_used_when_valid(db) -> None:
    user = _user(db)
    item = _item(db, user)
    inbox.request_analysis(db, current_user=user, item_id=item.id)
    _run(db, model=lambda prompt: {"summary": "Synthèse du modèle.", "facts": ["fait 1"]})
    draft = inbox.get_item(db, current_user=user, item_id=item.id).extraction_draft
    assert draft["summary"] == "Synthèse du modèle." and draft["facts"] == ["fait 1"]


def test_cancel_before_validation_deletes_everything(db, storage) -> None:
    user = _user(db)
    item = _item(db, user)
    source = _upload(db, user, item, "a.txt", b"x")
    inbox.cancel_item(db, current_user=user, item_id=item.id)
    assert not (storage / source.storage_pointer).exists()
    with pytest.raises(inbox.InboxNotFoundError):
        inbox.get_item(db, current_user=user, item_id=item.id)


def test_delete_removes_sources_and_neutralizes_direct_memories(db, storage) -> None:
    user = _user(db)
    item = _item(db, user)
    source = _upload(db, user, item, "a.txt", b"x")
    inbox.request_analysis(db, current_user=user, item_id=item.id)
    _run(db)
    inbox.validate_item(db, current_user=user, item_id=item.id, payload=InboxValidateRequest(destination="memory"))
    _run(db, embed=_fake_embed)

    inbox.delete_item(db, current_user=user, item_id=item.id)

    assert not (storage / source.storage_pointer).exists()
    memories = list(db.scalars(select(AIMemory).where(AIMemory.source_id == str(item.id))))
    assert memories and all(m.is_active is False for m in memories)
    assert [i.id for i in inbox.list_items(db, current_user=user).items] == []


def test_validation_can_create_a_project_explicitly(db) -> None:
    user = _user(db)
    item = _item(db, user, context="Projet camping-car : châssis Iveco Daily allongé.")
    inbox.request_analysis(db, current_user=user, item_id=item.id)
    _run(db)
    validated = inbox.validate_item(db, current_user=user, item_id=item.id,
                                    payload=InboxValidateRequest(destination="project", project_title="Camping-car"))
    project = db.get(ImperiumProject, validated.created_entity_id)
    assert validated.created_entity_type == "project" and project.title == "Camping-car" and project.source == "chatbot"


def test_type_and_size_are_enforced_server_side(db, monkeypatch) -> None:
    user = _user(db)
    item = _item(db, user)
    with pytest.raises(KnowledgeFileError):
        _upload(db, user, item, "setup.exe", b"MZ")
    monkeypatch.setattr(inbox, "max_bytes", lambda kind: 5)
    with pytest.raises(KnowledgeFileError):
        _upload(db, user, item, "gros.txt", b"0123456789")
    assert inbox.get_item(db, current_user=user, item_id=item.id).sources == []


def test_zip_inner_files_become_their_own_items(db) -> None:
    user = _user(db)
    item = _item(db, user)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("a.txt", b"premier")
        archive.writestr("b.md", b"second")
        archive.writestr("virus.exe", b"MZ")
    result = inbox.add_source(db, current_user=user, item_id=item.id, filename="lot.zip", content_type="application/zip",
                              stream=io.BytesIO(buffer.getvalue()))
    assert sorted(i.title for i in result.created_items) == ["a.txt", "b.md"]
    assert result.rejected == [{"name": "virus.exe", "reason": "type non accepté"}]


def test_items_are_user_scoped(db) -> None:
    user, other = _user(db), _user(db)
    item = _item(db, user)
    with pytest.raises(inbox.InboxNotFoundError):
        inbox.get_item(db, current_user=other, item_id=item.id)


def test_http_upload_raw_body_and_preview(db, engine) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.deps import get_current_user, get_db
    from app.api.v1.routes import knowledge_inbox as routes

    user = _user(db)
    app = FastAPI()
    app.include_router(routes.router, prefix="/api/ai/knowledge-inbox")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    created = client.post("/api/ai/knowledge-inbox/items", headers={"Idempotency-Key": "http-1"},
                          json={"context_text": "Préférences d'organisation", "entry_app": "imperium"})
    item_id = created.json()["id"]
    uploaded = client.post(f"/api/ai/knowledge-inbox/items/{item_id}/sources",
                           headers={"X-Filename": "pr%C3%A9f%C3%A9rences.md", "Content-Type": "text/markdown"},
                           content=b"# Le matin pour l'administratif")
    refused = client.post(f"/api/ai/knowledge-inbox/items/{item_id}/sources",
                          headers={"X-Filename": "outil.exe", "Content-Type": "application/octet-stream"}, content=b"MZ")
    preview = client.get(f"/api/ai/knowledge-inbox/items/{item_id}/sources/{uploaded.json()['id']}")

    assert created.status_code == 201 and uploaded.status_code == 201
    assert uploaded.json()["original_filename"] == "preferences.md"
    assert refused.status_code == 422 and "Fichier refusé" in refused.json()["detail"]
    assert preview.status_code == 200 and preview.content == b"# Le matin pour l'administratif"
