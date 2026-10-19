"""PostgreSQL : W2 découverte causale en dry-run (spec WR §5, §14 verrous 10-11 ; carte V20 ACT-WR-10)."""
from __future__ import annotations

import socket
import urllib.request
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("wr causal DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, delete, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.models import ai  # noqa: E402,F401 - FK de la session WR vers ai_tasks
from app.models.auth import User  # noqa: E402
from app.models.event import Event  # noqa: E402
from app.models.toolbox import SignalValue  # noqa: E402
from app.models.wr import (  # noqa: E402
    ChainAssembly,
    ChainCandidate,
    ChainPairVerdict,
    ChainProbe,
    WrDocketItem,
    WrWorkerCursor,
    WrWorkerRun,
)
from app.schemas.wr import DocketDecisionRequest  # noqa: E402
from app.services.events.emitter import build_event  # noqa: E402
from app.services.wr import causal, docket, factory  # noqa: E402

NOW = datetime(2026, 10, 14, 16, 0, tzinfo=UTC)
CRITERIA = {"event_types": ["planning.mission.aborted"], "red_flag_event_types": ["planning.docket.red_notified"],
            "user_question_event_types": [], "anomaly_min_band": "orange",
            "anomaly_domains": {"finance": ["finance."]}, "max_targets_per_run": 10}


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
def no_model_calls(monkeypatch):
    """Espion §14.11 : toute sortie réseau ou appel modèle fait échouer le test."""
    def forbidden(*_args, **_kwargs):
        raise AssertionError("model or network call during a W2 dry-run")

    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


@pytest.fixture(autouse=True)
def criteria(monkeypatch):
    real = causal.get_parameter

    def fake(db, code, default=None):
        return CRITERIA if code == "wr.notable_criteria" else real(db, code, default=default)

    monkeypatch.setattr(causal, "get_parameter", fake)


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"w2-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _event(db, user, event_type, occurred_at, *, correlation_id=None, causation_id=None, payload=None) -> Event:
    event = build_event(db, user_id=user.id, event_type=event_type, payload=payload or {},
                        idempotency_key=uuid4().hex, occurred_at=occurred_at, correlation_id=correlation_id,
                        causation_id=causation_id)
    db.add(event)
    db.flush()
    return event


def _window(db):
    db.commit()
    return datetime.now(UTC) - timedelta(minutes=5), datetime.now(UTC) + timedelta(minutes=5)


def _story(db, user):
    """Une mission avortée, des causes possibles avant elle, un event hors fenêtre et un event interne."""
    target_at = NOW
    causes = [_event(db, user, "planning.mission.started", target_at - timedelta(hours=hours), correlation_id="c-1")
              for hours in (1, 5, 30)]
    _event(db, user, "planning.mission.created", target_at - timedelta(days=120))  # hors fenêtre de 90 jours
    _event(db, user, "planning.factory.run_completed", target_at - timedelta(hours=2))  # interne au WR
    _event(db, user, "path.prayer.cleared", target_at - timedelta(days=3))  # ni même famille, ni même jour
    target = _event(db, user, "planning.mission.aborted", target_at, correlation_id="c-1")
    _event(db, user, "planning.mission.started", target_at + timedelta(hours=1))  # postérieur
    return target, causes


def _force_verdict(monkeypatch, verdict: str) -> None:
    monkeypatch.setattr(causal, "VERDICTS", (verdict,))
    real = causal.get_parameter
    monkeypatch.setattr(causal, "get_parameter", lambda db, code, default=None: (
        CRITERIA if code == "wr.notable_criteria" else 0 if code == "wr.chain_min_confidence"
        else real(db, code, default=default)))


def test_dry_run_chain_reaches_the_docket_without_any_model_call(db, monkeypatch) -> None:
    _force_verdict(monkeypatch, "favoring_condition")
    user = _user(db)
    target, causes = _story(db, user)
    window_from, window_to = _window(db)
    stats = causal.run_window(db, user=user, window_from=window_from, window_to=window_to)
    assert (stats.targets, stats.probes, stats.reasons) == (1, 3, {"notable_type": 1})
    probes = db.scalars(select(ChainProbe).where(ChainProbe.target_event_id == target.id)).all()
    assert {probe.generated_by for probe in probes} == {"dry_run"}
    candidates = db.scalars(select(ChainCandidate).where(ChainCandidate.target_event_id == target.id)
                            .order_by(ChainCandidate.rerank_score.desc())).all()
    assert [c.candidate_event_id for c in candidates] == [cause.id for cause in causes]  # le plus proche d'abord
    assert all(c.retained and c.passed_hard_filters and "graph" in c.channels for c in candidates)
    verdicts = db.scalars(select(ChainPairVerdict).where(
        ChainPairVerdict.candidate_id.in_([c.id for c in candidates]))).all()
    assert len(verdicts) == 3 and {v.model_used for v in verdicts} == {"dry_run"}
    assembly = db.scalar(select(ChainAssembly).where(ChainAssembly.target_event_id == target.id))
    assert (assembly.dry_run, assembly.status, len(assembly.proposed_links), assembly.conflicts) == (
        True, "pending_validation", 3, [])
    item = db.get(WrDocketItem, assembly.docket_item_id)
    assert (item.item_type, item.source_worker, item.payload["dry_run"], item.confidence) == ("chain_proposal", "w2", True, None)
    assert item.title_fr.startswith("[essai]")
    assert all(link["depth"] == 2 for link in assembly.proposed_links)  # depth de la cause (1) + 1
    # rien n'entre dans le graphe réel : la cible garde sa causation
    db.refresh(target)
    assert target.causation_id is None


def test_several_direct_causes_are_a_conflict_and_no_link_means_no_item(db, monkeypatch) -> None:
    _force_verdict(monkeypatch, "direct_cause")
    user = _user(db)
    target, causes = _story(db, user)
    window_from, window_to = _window(db)
    causal.run_window(db, user=user, window_from=window_from, window_to=window_to)
    assembly = db.scalar(select(ChainAssembly).where(ChainAssembly.target_event_id == target.id))
    assert assembly.conflicts == [{"kind": "double_parent", "cause_event_ids": [str(cause.id) for cause in causes]}]
    _force_verdict(monkeypatch, "no_link")
    other = _user(db)
    lonely, _ = _story(db, other)
    window_from, window_to = _window(db)
    stats = causal.run_window(db, user=other, window_from=window_from, window_to=window_to)
    assert (stats.verdicts, stats.assemblies) == (3, 0)
    assert db.scalar(select(ChainAssembly).where(ChainAssembly.target_event_id == lonely.id)) is None


def test_targets_are_probed_once_and_selected_by_criteria(db) -> None:
    user = _user(db)
    red = _event(db, user, "planning.docket.red_notified", NOW - timedelta(hours=3))
    finance = _event(db, user, "finance.transaction.created", NOW - timedelta(hours=2))
    _event(db, user, "finance.transaction.created", NOW.replace(day=12))  # jour sans anomalie
    db.add(SignalValue(signal_code="wr.finance.expense", measured_at=NOW, value=9000, band="orange",
                       flags={"flag": True}, stale=False,
                       detail={"user_id": str(user.id), "local_date": NOW.date().isoformat(), "z": 3.2}))
    window_from, window_to = _window(db)
    targets = causal.notable_events(db, user=user, window_from=window_from, window_to=window_to, criteria=CRITERIA)
    assert [(event.id, reasons) for event, reasons in targets] == [
        (red.id, ["red_flag"]), (finance.id, ["anomaly_same_day"])]  # red flag d'abord
    causal.run_window(db, user=user, window_from=window_from, window_to=window_to)
    assert causal.run_window(db, user=user, window_from=window_from, window_to=window_to).targets == 0
    capped = {**CRITERIA, "max_targets_per_run": 1}
    assert causal.notable_events(db, user=user, window_from=window_from, window_to=window_to, criteria=capped) == []


def test_docket_decision_is_mirrored_on_the_assembly(db) -> None:
    user = _user(db)
    target, _causes = _story(db, user)
    db.flush()
    assembly = ChainAssembly(user_id=user.id, target_event_id=target.id, proposed_links=[{"x": 1}], conflicts=[],
                             status="pending_validation", dry_run=True)
    db.add(assembly)
    db.flush()
    item = docket.create_item(db, current_user=user, item_type="chain_proposal", domain="imperium", title_fr="essai",
                              payload={}, evidence_refs={"assembly_id": str(assembly.id)}, impact_estimate=3,
                              source_worker="w2")
    assembly.docket_item_id = item.id
    db.commit()
    docket.decide(db, current_user=user, item_id=item.id, request=DocketDecisionRequest(decision="deferred"),
                  idempotency_key=uuid4().hex, request_path="/x")
    assert db.get(ChainAssembly, assembly.id).status == "pending_validation"
    docket.decide(db, current_user=user, item_id=item.id,
                  request=DocketDecisionRequest(decision="refused", decision_note="Coïncidence."),
                  idempotency_key=uuid4().hex, request_path="/x")
    assert db.get(ChainAssembly, assembly.id).status == "refused"


def test_real_ai_enabled_fails_w2_without_moving_its_cursor(db, monkeypatch) -> None:
    user = _user(db)
    db.execute(delete(WrWorkerRun))
    db.execute(delete(WrWorkerCursor))
    db.commit()
    monkeypatch.setattr(factory, "get_parameter",
                        lambda _db, code, default=None: ["w2_causal"] if code == "wr.factory_workers_enabled" else default)
    monkeypatch.setattr(get_settings(), "real_ai_enabled", True)
    summary = factory.run_factory(db, user=user, trigger="manual", now=datetime.now(UTC))
    assert summary["failed"] == "w2_causal" and db.get(WrWorkerCursor, "w2_causal") is None
    monkeypatch.setattr(get_settings(), "real_ai_enabled", False)
    summary = factory.run_factory(db, user=user, trigger="manual", now=datetime.now(UTC))
    assert summary["completed"] == ["w2_causal"]
    run = db.scalar(select(WrWorkerRun).where(WrWorkerRun.worker == "w2_causal", WrWorkerRun.status == "completed"))
    assert run.detail["dry_run"] is True and run.detail["vector_channels"] == "off"
    db.rollback()
    db.execute(delete(WrWorkerRun))
    db.execute(delete(WrWorkerCursor))
    db.commit()
