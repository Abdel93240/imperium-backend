"""PostgreSQL : W3 apprentissages en dry-run, aucune écriture mémoire (spec WR §6 ; carte V20 ACT-WR-10)."""
from __future__ import annotations

import socket
import urllib.request
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("wr learning DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, delete, func, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.models import ai  # noqa: E402 - FK de la session WR vers ai_tasks ; ai_memories
from app.models.auth import User  # noqa: E402
from app.models.wr import MemoryConfrontation, WrPatternExtraction, WrWorkerCursor, WrWorkerRun  # noqa: E402
from app.schemas.wr import DocketDecisionRequest  # noqa: E402
from app.services.events.emitter import build_event  # noqa: E402
from app.services.wr import docket, factory, learning  # noqa: E402

NOW = datetime(2026, 10, 17, 16, 0, tzinfo=UTC)  # samedi
CRITERIA = {"event_types": ["planning.mission.completed"], "decided_with_note": True, "max_episodes_per_run": 20}


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
def guards(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("model or network call during a W3 dry-run")

    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    real = learning.get_parameter
    monkeypatch.setattr(learning, "get_parameter", lambda db, code, default=None: (
        CRITERIA if code == "wr.episode_criteria" else real(db, code, default=default)))


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"w3-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _event(db, user, event_type, occurred_at=NOW):
    event = build_event(db, user_id=user.id, event_type=event_type, payload={}, idempotency_key=uuid4().hex,
                        occurred_at=occurred_at)
    db.add(event)
    db.flush()
    return event


def _window(db):
    db.commit()
    return datetime.now(UTC) - timedelta(minutes=5), datetime.now(UTC) + timedelta(minutes=5)


def test_episode_closes_are_extracted_and_confronted_without_memory_writes(db) -> None:
    user = _user(db)
    memories_before = db.scalar(select(func.count()).select_from(ai.AIMemory))
    completed = _event(db, user, "planning.mission.completed")
    _event(db, user, "planning.mission.started")  # pas une clôture
    explained = docket.create_item(db, current_user=user, item_type="anomaly", domain="vault", title_fr="a",
                                   payload={}, evidence_refs={"k": uuid4().hex}, impact_estimate=3, source_worker="w4")
    silent = docket.create_item(db, current_user=user, item_type="anomaly", domain="vault", title_fr="b",
                                payload={}, evidence_refs={"k": uuid4().hex}, impact_estimate=3, source_worker="w4")
    db.commit()
    docket.decide(db, current_user=user, item_id=explained.id,
                  request=DocketDecisionRequest(decision="refused", decision_note="Jour férié."),
                  idempotency_key=uuid4().hex, request_path="/x")
    docket.decide(db, current_user=user, item_id=silent.id, request=DocketDecisionRequest(decision="validated"),
                  idempotency_key=uuid4().hex, request_path="/x")
    window_from, window_to = _window(db)
    stats = learning.run_window(db, user=user, window_from=window_from, window_to=window_to)
    assert (stats.episodes, stats.extractions, stats.rejected, stats.confrontations) == (2, 2, 0, 2)
    extraction = db.scalar(select(WrPatternExtraction).where(WrPatternExtraction.episode_event_id == completed.id))
    assert (extraction.dry_run, extraction.model_used, extraction.canonical_errors, extraction.pattern_domain) == (
        True, "dry_run", [], "imperium")
    assert extraction.context_predicate == {"all": [{"field": "day.day_of_week", "op": "=", "value": "saturday"}]}
    confrontation = db.scalar(select(MemoryConfrontation).where(MemoryConfrontation.extraction_id == extraction.id))
    assert (confrontation.relation, confrontation.neighbor_memory_id, confrontation.applied_effect,
            confrontation.dry_run) == ("unrelated", None, "new_pattern", True)
    assert db.scalar(select(func.count()).select_from(ai.AIMemory)) == memories_before  # aucune écriture mémoire
    assert learning.run_window(db, user=user, window_from=window_from, window_to=window_to).episodes == 0


def test_non_canonical_or_bad_predicate_is_logged_but_not_confronted(db, monkeypatch) -> None:
    user = _user(db)
    _event(db, user, "planning.mission.completed")
    monkeypatch.setattr(learning, "_dry_run_extraction", lambda episode: [
        {"statement_fr": "Il rapporte plus depuis récemment.", "domain": "vector", "context_predicate": None,
         "evidence_event_ids": [episode.id], "suggested_confidence": 40},
        {"statement_fr": "Le samedi soir rapporte plus.", "domain": "vector",
         "context_predicate": {"all": [{"field": "session.start_hour", "op": ">=", "value": 21}]},
         "evidence_event_ids": [episode.id], "suggested_confidence": 55},
    ])
    window_from, window_to = _window(db)
    stats = learning.run_window(db, user=user, window_from=window_from, window_to=window_to)
    assert (stats.extractions, stats.rejected, stats.predicates_rejected, stats.confrontations) == (2, 1, 1, 1)
    rows = {row.statement_fr: row for row in db.scalars(select(WrPatternExtraction).where(
        WrPatternExtraction.user_id == user.id))}
    assert rows["Il rapporte plus depuis récemment."].canonical_errors == ["dangling_pronoun", "relative_date:récemment"]
    kept = rows["Le samedi soir rapporte plus."]
    assert (kept.context_predicate, kept.predicate_rejected) == (None, True)  # le pattern reste légal


def test_factory_runs_w3_in_dry_run_and_fails_it_with_real_ai(db, monkeypatch) -> None:
    user = _user(db)
    db.execute(delete(WrWorkerRun))
    db.execute(delete(WrWorkerCursor))
    db.commit()
    monkeypatch.setattr(factory, "get_parameter",
                        lambda _db, code, default=None: ["w3_learning"] if code == "wr.factory_workers_enabled" else default)
    monkeypatch.setattr(get_settings(), "real_ai_enabled", True)
    assert factory.run_factory(db, user=user, trigger="manual", now=datetime.now(UTC))["failed"] == "w3_learning"
    assert db.get(WrWorkerCursor, "w3_learning") is None
    monkeypatch.setattr(get_settings(), "real_ai_enabled", False)
    assert factory.run_factory(db, user=user, trigger="manual", now=datetime.now(UTC))["completed"] == ["w3_learning"]
    run = db.scalar(select(WrWorkerRun).where(WrWorkerRun.worker == "w3_learning", WrWorkerRun.status == "completed"))
    assert (run.detail["dry_run"], run.detail["memory_writes"]) == (True, 0)
    db.rollback()
    db.execute(delete(WrWorkerRun))
    db.execute(delete(WrWorkerCursor))
    db.commit()
