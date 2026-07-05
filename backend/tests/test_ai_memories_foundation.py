from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_db
from app.api.v1.routes import imperium
from app.models.ai import AIMemory
from app.models.idempotency import IdempotencyKey
from app.models.imperium import ImperiumMemoryCandidateDecision
from app.schemas.ai import AIMemoryArchiveRequest, AIMemoryDraftRead, AIMemorySupersedeRequest
from app.services.ai import memories
from app.services.ai.memories import (
    AIMemoryDuplicateSourceError,
    AIMemoryIdempotencyConflictError,
    AIMemoryOwnershipError,
    AIMemoryValidationError,
    WR_MEMORY_COMMIT_DISABLED_REASON,
    archive_ai_memory,
    build_memory_draft_from_weekly_review_decision,
    create_ai_memory_from_draft,
    ensure_memory_source_not_committed,
    get_ai_memory_schema_health,
    supersede_ai_memory,
)


class FakeDb:
    def __init__(self, scalar_result=None, scalars_result=None, objects=None) -> None:
        self.scalar_result = scalar_result
        self.scalars_result = scalars_result or []
        self.objects = objects or {}
        self.added = []
        self.committed = False

    def add(self, obj) -> None:
        self._prepare(obj)
        self.added.append(obj)
        self.objects[(type(obj), obj.id)] = obj

    def flush(self) -> None:
        for obj in self.added:
            self._prepare(obj)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass

    def scalar(self, _query):
        return self.scalar_result

    def scalars(self, _query):
        return self.scalars_result

    def get(self, model, object_id):
        return self.objects.get((model, object_id))

    def _prepare(self, obj) -> None:
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
            obj.created_at = datetime.now(UTC)
        if hasattr(obj, "updated_at") and getattr(obj, "updated_at", None) is None:
            obj.updated_at = datetime.now(UTC)


def _user() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4())


def _embedding() -> list[float]:
    return [0.0] * 1024


def _decision(user_id, *, decision: str = "approved") -> ImperiumMemoryCandidateDecision:
    now = datetime.now(UTC)
    return ImperiumMemoryCandidateDecision(
        id=uuid4(),
        user_id=user_id,
        report_id=uuid4(),
        session_id=uuid4(),
        candidate_id="wrmem_candidate_1",
        decision=decision,
        source="weekly_review",
        original_candidate={
            "kind": "weekly_commitment",
            "title": "Protect focus blocks",
            "content": "Keep two protected focus blocks next week.",
            "confidence": 0.8,
            "proposed_memory_scope": "weekly_review",
        },
        edited_candidate=None,
        created_at=now,
        updated_at=now,
    )


def _memory(user_id, *, is_active: bool = True) -> AIMemory:
    now = datetime.now(UTC)
    return AIMemory(
        id=uuid4(),
        user_id=user_id,
        content="Memory content about fatigue.",
        embedding=_embedding(),
        embedding_model="qwen3-embedding-1024",
        memory_type="planning_insight",
        learning_element_type="insight",
        source_domain="review",
        source_table="imperium_memory_candidate_decisions",
        source_id=str(uuid4()),
        confidence=Decimal("0.7000"),
        privacy_level="private",
        is_active=is_active,
        metadata_json={"source": "test"},
        created_at=now,
        updated_at=now,
    )


def _draft(user_id) -> AIMemoryDraftRead:
    return AIMemoryDraftRead(
        user_id=user_id,
        content="Keep sport before long VTC shifts.",
        embedding=_embedding(),
        embedding_model="qwen3-embedding-1024",
        memory_type="planning_insight",
        learning_element_type="pattern",
        source_domain="review",
        source_table="imperium_weekly_review_final_reports",
        source_id=str(uuid4()),
        confidence=Decimal("0.8000"),
        privacy_level="private",
        metadata={"raw_payload": "DROP_ME", "safe": True},
    )


def _idempotency_from_added(db: FakeDb, key: str) -> IdempotencyKey | None:
    for item in db.added:
        if isinstance(item, IdempotencyKey) and item.idempotency_key == key:
            return item
    return None


def test_ai_memory_model_matches_unified_vector_schema() -> None:
    columns = set(AIMemory.__table__.columns.keys())

    assert columns == {
        "id",
        "user_id",
        "content",
        "embedding",
        "embedding_model",
        "memory_type",
        "learning_element_type",
        "source_domain",
        "source_table",
        "source_id",
        "confidence",
        "privacy_level",
        "is_active",
        "supersedes_memory_id",
        "correction_reason",
        "expires_at",
        "created_at",
        "updated_at",
        "metadata",
        "idempotency_key",
    }
    assert AIMemory.__table__.columns["embedding"].type.get_col_spec() == "vector(1024)"


def test_ai_memory_schema_health_reports_vector_schema_but_disabled_writes() -> None:
    health = get_ai_memory_schema_health()

    assert health.storage_enabled is False
    assert health.table_defined is True
    assert health.embeddings_enabled is False
    assert health.pgvector_enabled is True
    assert "planning_insight" in health.supported_memory_types
    assert "review" in health.supported_source_domains
    assert health.supported_privacy_levels == ["private"]
    assert health.commit_endpoint is None


def test_memories_schema_endpoint_requires_auth() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    client = TestClient(app)

    response = client.get("/imperium/memories/schema")

    assert response.status_code == 401


def test_memories_schema_endpoint_returns_disabled_commit_contract() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_current_user] = _user
    client = TestClient(app)

    response = client.get("/imperium/memories/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["storage_enabled"] is False
    assert body["table_defined"] is True
    assert body["embeddings_enabled"] is False
    assert body["pgvector_enabled"] is True
    assert body["commit_endpoint"] is None
    assert "review" in body["supported_source_domains"]


def test_memories_index_returns_only_current_user_active_memories() -> None:
    current_user = _user()
    own_memory = _memory(current_user.id)
    foreign_memory = _memory(uuid4())
    inactive_memory = _memory(current_user.id, is_active=False)
    db = FakeDb(scalars_result=[own_memory, foreign_memory, inactive_memory])
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    response = client.get("/imperium/memories")
    body = response.json()

    assert response.status_code == 200
    assert body["count"] == 1
    assert body["items"][0]["id"] == str(own_memory.id)
    assert body["items"][0]["embedding_model"] == "qwen3-embedding-1024"
    assert "raw_payload" not in response.text


def test_memories_index_filters_type_source_privacy_and_search() -> None:
    current_user = _user()
    matching = _memory(current_user.id)
    matching.memory_type = "failure_pattern"
    matching.learning_element_type = "blocker"
    matching.source_domain = "review"
    matching.source_table = "imperium_memory_candidate_decisions"
    matching.source_id = "decision-a"
    matching.privacy_level = "private"
    matching.content = "Fatigue risk should be watched."
    wrong_type = _memory(current_user.id)
    wrong_type.memory_type = "planning_insight"
    db = FakeDb(scalars_result=[matching, wrong_type])
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    response = client.get(
        "/imperium/memories",
        params={
            "memory_type": "failure_pattern",
            "learning_element_type": "blocker",
            "source_domain": "review",
            "source_table": "imperium_memory_candidate_decisions",
            "source_id": "decision-a",
            "privacy_level": "private",
            "q": "fatigue",
        },
    )

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["items"][0]["id"] == str(matching.id)


def test_memory_detail_404s_for_foreign_memory() -> None:
    current_user = _user()
    foreign_memory = _memory(uuid4())
    db = FakeDb(objects={(AIMemory, foreign_memory.id): foreign_memory})
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    response = client.get(f"/imperium/memories/{foreign_memory.id}")

    assert response.status_code == 404


def test_create_memory_from_draft_requires_vector_embedding_and_sanitizes_metadata() -> None:
    user = _user()
    db = FakeDb()

    memory = create_ai_memory_from_draft(db, draft=_draft(user.id), idempotency_key="create-key")

    assert memory.embedding == _embedding()
    assert memory.embedding_model == "qwen3-embedding-1024"
    assert memory.memory_type == "planning_insight"
    assert memory.source_domain == "review"
    assert memory.metadata_json == {"safe": True}
    assert memory.idempotency_key == "create-key"


def test_create_memory_rejects_wrong_embedding_dimensions() -> None:
    draft = _draft(_user().id)
    draft.embedding = [0.0]

    with pytest.raises(AIMemoryValidationError):
        create_ai_memory_from_draft(FakeDb(), draft=draft)


def test_archive_memory_is_idempotent_and_deactivates_memory(monkeypatch) -> None:
    current_user = _user()
    memory = _memory(current_user.id)
    db = FakeDb(objects={(AIMemory, memory.id): memory})
    monkeypatch.setattr(
        memories,
        "_get_existing_idempotency",
        lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key),
    )

    first, duplicate = archive_ai_memory(
        db,
        current_user=current_user,
        memory_id=memory.id,
        payload=AIMemoryArchiveRequest(reason="old"),
        idempotency_key="archive-key",
        request_method="POST",
        request_path=f"/api/imperium/memories/{memory.id}/archive",
    )
    replay, replay_duplicate = archive_ai_memory(
        db,
        current_user=current_user,
        memory_id=memory.id,
        payload=AIMemoryArchiveRequest(reason="old"),
        idempotency_key="archive-key",
        request_method="POST",
        request_path=f"/api/imperium/memories/{memory.id}/archive",
    )

    assert duplicate is False
    assert replay_duplicate is True
    assert first.is_active is False
    assert replay.is_active is False
    assert memory.correction_reason == "old"
    assert len([item for item in db.added if isinstance(item, IdempotencyKey)]) == 1


def test_archive_memory_rejects_inactive_with_new_key() -> None:
    current_user = _user()
    memory = _memory(current_user.id, is_active=False)
    db = FakeDb(objects={(AIMemory, memory.id): memory})

    with pytest.raises(AIMemoryValidationError):
        archive_ai_memory(
            db,
            current_user=current_user,
            memory_id=memory.id,
            payload=AIMemoryArchiveRequest(),
            idempotency_key="archive-new",
            request_method="POST",
            request_path=f"/api/imperium/memories/{memory.id}/archive",
        )


def test_supersede_memory_creates_vector_memory_and_deactivates_old(monkeypatch) -> None:
    current_user = _user()
    memory = _memory(current_user.id)
    db = FakeDb(objects={(AIMemory, memory.id): memory})
    monkeypatch.setattr(
        memories,
        "_get_existing_idempotency",
        lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key),
    )

    result, duplicate = supersede_ai_memory(
        db,
        current_user=current_user,
        memory_id=memory.id,
        payload=AIMemorySupersedeRequest(
            content="Updated safe memory content.",
            embedding=_embedding(),
            embedding_model="qwen3-embedding-1024",
            memory_type="correction",
            learning_element_type="decision",
            source_domain="review",
            confidence=Decimal("0.9000"),
            reason="more precise",
            payload={"raw_payload": "DROP_ME", "safe": True},
        ),
        idempotency_key="supersede-key",
        request_method="POST",
        request_path=f"/api/imperium/memories/{memory.id}/supersede",
    )
    new_memory = next(item for item in db.added if isinstance(item, AIMemory))

    assert duplicate is False
    assert result.id == new_memory.id
    assert result.memory_type == "correction"
    assert result.learning_element_type == "decision"
    assert memory.is_active is False
    assert new_memory.supersedes_memory_id == memory.id
    assert new_memory.metadata_json["previous_memory_id"] == str(memory.id)
    assert "raw_payload" not in result.model_dump_json()


def test_supersede_memory_rejects_inactive_and_conflicting_replay(monkeypatch) -> None:
    current_user = _user()
    memory = _memory(current_user.id)
    db = FakeDb(objects={(AIMemory, memory.id): memory})
    monkeypatch.setattr(
        memories,
        "_get_existing_idempotency",
        lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key),
    )

    supersede_ai_memory(
        db,
        current_user=current_user,
        memory_id=memory.id,
        payload=AIMemorySupersedeRequest(
            content="Updated once.",
            embedding=_embedding(),
            embedding_model="qwen3-embedding-1024",
        ),
        idempotency_key="supersede-conflict",
        request_method="POST",
        request_path=f"/api/imperium/memories/{memory.id}/supersede",
    )
    replay, duplicate = supersede_ai_memory(
        db,
        current_user=current_user,
        memory_id=memory.id,
        payload=AIMemorySupersedeRequest(
            content="Updated once.",
            embedding=_embedding(),
            embedding_model="qwen3-embedding-1024",
        ),
        idempotency_key="supersede-conflict",
        request_method="POST",
        request_path=f"/api/imperium/memories/{memory.id}/supersede",
    )

    assert duplicate is True
    assert replay.is_active is True
    with pytest.raises(AIMemoryIdempotencyConflictError):
        supersede_ai_memory(
            db,
            current_user=current_user,
            memory_id=memory.id,
            payload=AIMemorySupersedeRequest(
                content="Different.",
                embedding=_embedding(),
                embedding_model="qwen3-embedding-1024",
            ),
            idempotency_key="supersede-conflict",
            request_method="POST",
            request_path=f"/api/imperium/memories/{memory.id}/supersede",
        )
    with pytest.raises(AIMemoryValidationError):
        supersede_ai_memory(
            FakeDb(objects={(AIMemory, memory.id): _memory(current_user.id, is_active=False)}),
            current_user=current_user,
            memory_id=memory.id,
            payload=AIMemorySupersedeRequest(
                content="Nope.",
                embedding=_embedding(),
                embedding_model="qwen3-embedding-1024",
            ),
            idempotency_key="supersede-inactive",
            request_method="POST",
            request_path=f"/api/imperium/memories/{memory.id}/supersede",
        )


def test_weekly_review_memory_draft_is_disabled_until_embedding_service() -> None:
    user = _user()

    with pytest.raises(AIMemoryValidationError, match=WR_MEMORY_COMMIT_DISABLED_REASON):
        build_memory_draft_from_weekly_review_decision(_decision(user.id), current_user_id=user.id)


def test_weekly_review_memory_draft_still_rejects_foreign_decision() -> None:
    user = _user()

    with pytest.raises(AIMemoryOwnershipError):
        build_memory_draft_from_weekly_review_decision(_decision(uuid4()), current_user_id=user.id)


def test_duplicate_memory_source_is_prevented() -> None:
    user = _user()
    memory = _memory(user.id)

    with pytest.raises(AIMemoryDuplicateSourceError):
        ensure_memory_source_not_committed(
            FakeDb(memory),
            user_id=user.id,
            source_domain=memory.source_domain,
            source_table=memory.source_table,
            source_id=memory.source_id,
        )
