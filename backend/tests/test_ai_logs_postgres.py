"""PostgreSQL : navigateur des logs de l'IA (doc 72 §8) — lecture seule, confiné à l'utilisateur."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("ai logs DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.ai import AIResult, AITask, KnowledgeInboxItem  # noqa: E402
from app.models.auth import User  # noqa: E402
from app.services.ai import logs as ai_logs  # noqa: E402

T0 = datetime(2026, 10, 15, 18, 2, tzinfo=UTC)


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


def _user(db) -> User:
    user_id = uuid4()
    db.execute(
        text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) VALUES (:id, :email, FALSE, now(), now())"),
        {"id": str(user_id), "email": f"logs-{user_id}@example.test"},
    )
    db.commit()
    return db.get(User, user_id)


def _task(db, user, task_type, created_at, **kwargs):
    task = AITask(user_id=user.id, task_type=task_type, status=kwargs.pop("status", "result_received"), source_module="imperium",
                  input_payload=kwargs.pop("input_payload", {}), created_at=created_at, **kwargs)
    db.add(task)
    db.commit()
    return task


def test_logs_are_named_explicitly_and_sorted_recent_first(db) -> None:
    user = _user(db)
    _task(db, user, "imperium.rolling_replan", T0, input_payload={"reason_category": "fatigue", "reason_detail": "Longue nuit."},
          router_decision={"engine": "deterministic"})
    _task(db, user, "weekly_report.summary", T0 + timedelta(days=1))
    db.add(KnowledgeInboxItem(user_id=user.id, title="Exemples de courses Bolt", status="vectorized", entry_app="imperium",
                              extraction_final={"summary": "Trois courses."}, created_at=T0 - timedelta(days=1)))
    db.commit()

    listing = ai_logs.list_logs(db, current_user=user)

    assert [entry.name for entry in listing.logs] == [
        "2026-10-16 · Weekly Review",
        "2026-10-15 · Replanification",
        "2026-10-14 · Nourrir l'IA · Exemples de courses Bolt",
    ]


def test_log_content_is_a_readable_terminal_transcript(db) -> None:
    user = _user(db)
    task = _task(db, user, "imperium.rolling_replan", T0, input_payload={"reason_category": "fatigue", "reason_detail": "Longue nuit."},
                 router_decision={"engine": "deterministic"}, completed_at=T0 + timedelta(seconds=4))
    db.add(AIResult(task_id=task.id, user_id=user.id, result_type="replan.proposal", status="received",
                    result_payload={"rationale": "Pause ajoutée."}, model_used="local_executor"))
    db.commit()

    log = ai_logs.read_log(db, current_user=user, log_id=f"task:{task.id}")

    assert "imperium.rolling_replan" in log.content and "engine=deterministic" in log.content
    assert "reason_category: fatigue" in log.content and "Pause ajoutée." in log.content
    assert log.content.rstrip().endswith("Pour corriger une extraction, parle au chatbot.")


def test_inbox_log_shows_what_was_retained(db) -> None:
    user = _user(db)
    item = KnowledgeInboxItem(user_id=user.id, title="Préférences", status="vectorized", entry_app="imperium",
                              extraction_draft={"summary": "Brouillon", "sources_unread": ["note.m4a"]},
                              extraction_final={"summary": "Le matin pour l'administratif.", "facts": ["Matin"]})
    db.add(item)
    db.commit()
    content = ai_logs.read_log(db, current_user=user, log_id=f"inbox:{item.id}").content
    assert "Le matin pour l'administratif." in content and "note.m4a" in content and "vectorized" in content


def test_secrets_are_masked(db) -> None:
    user = _user(db)
    task = _task(db, user, "system.check", T0, input_payload={"api_key": "sk-123", "nested": {"Authorization": "Bearer x", "ok": 1}})
    content = ai_logs.read_log(db, current_user=user, log_id=f"task:{task.id}").content
    assert "sk-123" not in content and "Bearer x" not in content and "••••" in content and "ok: 1" in content


def test_logs_are_confined_to_the_user(db) -> None:
    user, other = _user(db), _user(db)
    task = _task(db, user, "imperium.rolling_replan", T0)
    assert ai_logs.list_logs(db, current_user=other).logs == []
    with pytest.raises(ai_logs.AILogNotFoundError):
        ai_logs.read_log(db, current_user=other, log_id=f"task:{task.id}")


@pytest.mark.parametrize("log_id", ["../../etc/passwd", "file:/etc/passwd", "task:not-a-uuid", "inbox:", ""])
def test_no_path_or_foreign_identifier_is_accepted(db, log_id) -> None:
    user = _user(db)
    with pytest.raises(ai_logs.AILogNotFoundError):
        ai_logs.read_log(db, current_user=user, log_id=log_id)


def test_logs_routes_are_registered() -> None:
    from app.api.v1.router import api_router

    paths = {(route.path, method) for route in api_router.routes for method in getattr(route, "methods", set())}
    assert ("/ai/logs", "GET") in paths and ("/ai/logs/{log_id}", "GET") in paths
    assert not any(path.startswith("/ai/logs") and method in {"POST", "PUT", "PATCH", "DELETE"} for path, method in paths)
