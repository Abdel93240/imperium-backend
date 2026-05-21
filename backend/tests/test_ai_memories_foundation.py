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
from app.schemas.ai import AIMemoryArchiveRequest, AIMemorySupersedeRequest
from app.services.ai import memories
from app.services.ai.memories import (
    AIMemoryDuplicateSourceError,
    AIMemoryIdempotencyConflictError,
    AIMemoryOwnershipError,
    AIMemoryValidationError,
    archive_ai_memory,
    build_memory_draft_from_weekly_review_decision,
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


def _decision(user_id, *, decision: str = "approved", candidate: dict | None = None) -> ImperiumMemoryCandidateDecision:
    now = datetime.now(UTC)
    return ImperiumMemoryCandidateDecision(
        id=uuid4(),
        user_id=user_id,
        report_id=uuid4(),
        session_id=uuid4(),
        candidate_id="wrmem_candidate_1",
        decision=decision,
        source="weekly_review",
        original_candidate=candidate
        or {
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


def _memory(user_id, *, status: str = "active") -> AIMemory:
    now = datetime.now(UTC)
    return AIMemory(
        id=uuid4(),
        user_id=user_id,
        source_module="weekly_review",
        source_type="memory_candidate_decision",
        source_id=str(uuid4()),
        source_report_id=uuid4(),
        source_session_id=uuid4(),
        source_candidate_id="candidate",
        source_decision_id=uuid4(),
        kind="weekly_commitment",
        scope="weekly_review",
        title="Memory title",
        content="Memory content",
        confidence=Decimal("0.7"),
        status=status,
        visibility="private",
        metadata_json={"source": "test"},
        created_at=now,
        updated_at=now,
    )


def _idempotency_from_added(db: FakeDb, key: str) -> IdempotencyKey | None:
    for item in db.added:
        if isinstance(item, IdempotencyKey) and item.idempotency_key == key:
            return item
    return None


def test_ai_memory_model_has_no_vector_column() -> None:
    columns = set(AIMemory.__table__.columns.keys())

    assert "embedding" not in columns
    assert "vector" not in columns
    assert "metadata" in columns
    assert "metadata_json" not in columns


def test_ai_memory_schema_health_is_disabled() -> None:
    health = get_ai_memory_schema_health()

    assert health.storage_enabled is True
    assert health.table_defined is True
    assert health.embeddings_enabled is False
    assert health.pgvector_enabled is False
    assert "weekly_commitment" in health.supported_kinds
    assert "weekly_review" in health.supported_scopes
    assert "active" in health.supported_statuses
    assert health.supported_visibility == ["private"]


def test_memories_schema_endpoint_requires_auth() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    client = TestClient(app)

    response = client.get("/imperium/memories/schema")

    assert response.status_code == 401


def test_memories_schema_endpoint_returns_enabled_contract_without_embeddings() -> None:
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_current_user] = _user
    client = TestClient(app)

    response = client.get("/imperium/memories/schema")

    assert response.status_code == 200
    body = response.json()
    assert body["storage_enabled"] is True
    assert body["table_defined"] is True
    assert body["embeddings_enabled"] is False
    assert body["pgvector_enabled"] is False
    assert body["commit_endpoint"] == "/api/imperium/weekly-review/memory-candidates/commit"
    assert "weekly_review" in body["supported_scopes"]


def test_memories_index_returns_only_current_user_memories() -> None:
    current_user = _user()
    own_memory = _memory(current_user.id)
    foreign_memory = _memory(uuid4())
    archived_memory = _memory(current_user.id, status="archived")
    db = FakeDb(scalars_result=[own_memory, foreign_memory, archived_memory])
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
    assert "raw_payload" not in response.text


def test_memories_index_filters_kind_scope_source_and_search() -> None:
    current_user = _user()
    report_id = uuid4()
    session_id = uuid4()
    decision_id = uuid4()
    matching = _memory(current_user.id)
    matching.kind = "risk"
    matching.scope = "strategy"
    matching.source_module = "weekly_review"
    matching.source_type = "memory_candidate_decision"
    matching.source_report_id = report_id
    matching.source_session_id = session_id
    matching.source_candidate_id = "candidate-a"
    matching.source_decision_id = decision_id
    matching.title = "Driver risk"
    matching.content = "Fatigue risk should be watched."
    wrong_kind = _memory(current_user.id)
    wrong_kind.kind = "weekly_commitment"
    wrong_kind.title = "Driver risk"
    db = FakeDb(scalars_result=[matching, wrong_kind])
    app = FastAPI()
    app.include_router(imperium.router, prefix="/imperium")
    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)

    response = client.get(
        "/imperium/memories",
        params={
            "kind": "risk",
            "scope": "strategy",
            "source_module": "weekly_review",
            "source_type": "memory_candidate_decision",
            "source_report_id": str(report_id),
            "source_session_id": str(session_id),
            "source_candidate_id": "candidate-a",
            "source_decision_id": str(decision_id),
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


def test_archive_memory_is_idempotent_and_hides_from_default_index(monkeypatch) -> None:
    current_user = _user()
    memory = _memory(current_user.id)
    db = FakeDb(objects={(AIMemory, memory.id): memory})
    monkeypatch.setattr(memories, "_get_existing_idempotency", lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key))

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
    assert first.status == "archived"
    assert replay.status == "archived"
    assert memory.archived_at is not None
    assert len([item for item in db.added if isinstance(item, IdempotencyKey)]) == 1


def test_archive_memory_rejects_terminal_with_new_key() -> None:
    current_user = _user()
    memory = _memory(current_user.id, status="archived")
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


def test_supersede_memory_creates_new_memory_and_marks_old(monkeypatch) -> None:
    current_user = _user()
    memory = _memory(current_user.id)
    db = FakeDb(objects={(AIMemory, memory.id): memory})
    monkeypatch.setattr(memories, "_get_existing_idempotency", lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key))

    result, duplicate = supersede_ai_memory(
        db,
        current_user=current_user,
        memory_id=memory.id,
        payload=AIMemorySupersedeRequest(
            title="Updated memory",
            content="Updated safe memory content.",
            kind="strategy_note",
            scope="strategy",
            confidence=Decimal("0.9"),
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
    assert result.title == "Updated memory"
    assert result.kind == "strategy_note"
    assert result.scope == "strategy"
    assert memory.status == "superseded"
    assert memory.superseded_by_id == new_memory.id
    assert new_memory.source_type == "memory_supersession"
    assert new_memory.metadata_json["previous_memory_id"] == str(memory.id)
    assert "raw_payload" not in result.model_dump_json()


def test_supersede_memory_rejects_terminal_and_conflicting_replay(monkeypatch) -> None:
    current_user = _user()
    memory = _memory(current_user.id)
    db = FakeDb(objects={(AIMemory, memory.id): memory})
    monkeypatch.setattr(memories, "_get_existing_idempotency", lambda _db, *, user_id, idempotency_key: _idempotency_from_added(db, idempotency_key))

    supersede_ai_memory(
        db,
        current_user=current_user,
        memory_id=memory.id,
        payload=AIMemorySupersedeRequest(content="Updated once."),
        idempotency_key="supersede-conflict",
        request_method="POST",
        request_path=f"/api/imperium/memories/{memory.id}/supersede",
    )
    replay, duplicate = supersede_ai_memory(
        db,
        current_user=current_user,
        memory_id=memory.id,
        payload=AIMemorySupersedeRequest(content="Updated once."),
        idempotency_key="supersede-conflict",
        request_method="POST",
        request_path=f"/api/imperium/memories/{memory.id}/supersede",
    )

    assert duplicate is True
    assert replay.status == "active"
    with pytest.raises(AIMemoryIdempotencyConflictError):
        supersede_ai_memory(
            db,
            current_user=current_user,
            memory_id=memory.id,
            payload=AIMemorySupersedeRequest(content="Different."),
            idempotency_key="supersede-conflict",
            request_method="POST",
            request_path=f"/api/imperium/memories/{memory.id}/supersede",
        )
    with pytest.raises(AIMemoryValidationError):
        supersede_ai_memory(
            FakeDb(objects={(AIMemory, memory.id): _memory(current_user.id, status="archived")}),
            current_user=current_user,
            memory_id=memory.id,
            payload=AIMemorySupersedeRequest(content="Nope."),
            idempotency_key="supersede-archived",
            request_method="POST",
            request_path=f"/api/imperium/memories/{memory.id}/supersede",
        )


def test_memory_draft_accepts_approved_decision_without_insert() -> None:
    user = _user()
    decision = _decision(user.id)

    draft = build_memory_draft_from_weekly_review_decision(decision, current_user_id=user.id)

    assert draft.user_id == user.id
    assert draft.source_module == "weekly_review"
    assert draft.source_type == "memory_candidate_decision"
    assert draft.source_decision_id == decision.id
    assert draft.kind == "weekly_commitment"
    assert draft.scope == "weekly_review"
    assert draft.confidence == Decimal("0.8000")


def test_memory_draft_uses_edited_candidate() -> None:
    user = _user()
    decision = _decision(user.id, decision="edited")
    decision.edited_candidate = {
        "kind": "preference",
        "title": "Morning planning",
        "content": "Prefer reviewing operational priorities before 09:00.",
        "confidence": 1.4,
        "proposed_memory_scope": "user_preference",
    }

    draft = build_memory_draft_from_weekly_review_decision(decision, current_user_id=user.id)

    assert draft.kind == "preference"
    assert draft.scope == "user_preference"
    assert draft.title == "Morning planning"
    assert draft.confidence == Decimal("1")


def test_memory_draft_rejects_rejected_and_undecided_decisions() -> None:
    user = _user()

    with pytest.raises(AIMemoryValidationError):
        build_memory_draft_from_weekly_review_decision(_decision(user.id, decision="rejected"), current_user_id=user.id)
    with pytest.raises(AIMemoryValidationError):
        build_memory_draft_from_weekly_review_decision(_decision(user.id, decision="pending"), current_user_id=user.id)


def test_memory_draft_rejects_foreign_decision() -> None:
    user = _user()
    decision = _decision(uuid4())

    with pytest.raises(AIMemoryOwnershipError):
        build_memory_draft_from_weekly_review_decision(decision, current_user_id=user.id)


def test_memory_draft_rejects_empty_and_unknown_fields() -> None:
    user = _user()
    with pytest.raises(AIMemoryValidationError):
        build_memory_draft_from_weekly_review_decision(
            _decision(
                user.id,
                candidate={
                    "kind": "weekly_commitment",
                    "title": " ",
                    "content": "Missing title",
                    "confidence": 0.5,
                    "proposed_memory_scope": "weekly_review",
                },
            ),
            current_user_id=user.id,
        )
    with pytest.raises(AIMemoryValidationError):
        build_memory_draft_from_weekly_review_decision(
            _decision(
                user.id,
                candidate={
                    "kind": "unknown",
                    "title": "Title",
                    "content": "Content",
                    "confidence": 0.5,
                    "proposed_memory_scope": "weekly_review",
                },
            ),
            current_user_id=user.id,
        )


def test_duplicate_memory_source_is_prevented() -> None:
    user = _user()
    memory = AIMemory(
        id=uuid4(),
        user_id=user.id,
        source_module="weekly_review",
        source_type="memory_candidate_decision",
        source_id="source",
        source_decision_id=uuid4(),
        kind="weekly_commitment",
        scope="weekly_review",
        title="Title",
        content="Content",
        confidence=Decimal("0.5"),
        status="active",
        visibility="private",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )

    with pytest.raises(AIMemoryDuplicateSourceError):
        ensure_memory_source_not_committed(
            FakeDb(memory),
            user_id=user.id,
            source_module="weekly_review",
            source_type="memory_candidate_decision",
            source_decision_id=memory.source_decision_id,
            source_id=memory.source_id,
        )


def test_memory_read_schema_strips_unsafe_payloads() -> None:
    user = _user()
    decision = _decision(user.id)
    decision.original_candidate["raw_payload"] = {"secret": "DO_NOT_EXPOSE"}

    draft = build_memory_draft_from_weekly_review_decision(decision, current_user_id=user.id)
    serialized = draft.model_dump_json()

    assert "raw_payload" not in serialized
    assert "DO_NOT_EXPOSE" not in serialized
