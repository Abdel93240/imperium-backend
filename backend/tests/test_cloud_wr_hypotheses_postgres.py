"""PostgreSQL : rôles cloud par la CLI de l'abonnement (tests avant clé API) et passe d'hypothèses du WR
(spec WR §9 P1). CLI simulée : aucun appel réel."""
from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("psycopg")

from _postgres import require_test_database_url  # noqa: E402

_TEST_DB_URL = require_test_database_url("cloud WR hypotheses DB tests")

pytestmark = pytest.mark.postgres

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.models.auth import User  # noqa: E402
from app.models.imperium import ImperiumWeeklyReviewSession  # noqa: E402
from app.models.wr import WrHypothesis, WrRollupDaily  # noqa: E402
from app.services.ai import cloud  # noqa: E402
from app.services.params import set_parameter  # noqa: E402
from app.services.wr import digest as wr_digest  # noqa: E402
from app.services.wr import docket, hypotheses  # noqa: E402


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(_TEST_DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    outer.rollback()
    connection.close()


class FakeCli:
    """CLI simulée : rend les sorties préparées au format de `claude -p` ou de `codex exec`."""

    def __init__(self) -> None:
        self.outputs: list = []
        self.calls: list[tuple[list[str], str, str]] = []
        self.logs: list[dict] = []

    def run(self, args, stdin, timeout, cwd):
        self.calls.append((args, stdin, cwd))
        item = self.outputs.pop(0)
        if isinstance(item, Exception):
            raise item
        if args[1] == "exec":
            Path(args[args.index("-o") + 1]).write_text(json.dumps(item), encoding="utf-8")
            return json.dumps({"type": "turn.completed", "usage": {"input_tokens": 900, "output_tokens": 80}})
        return json.dumps({"type": "result", "subtype": "success", "is_error": False, "structured_output": item,
                           "total_cost_usd": 0.12, "usage": {"input_tokens": 3, "cache_creation_input_tokens": 1000,
                                                             "cache_read_input_tokens": 0, "output_tokens": 200},
                           "modelUsage": {"model-cloud-test": {}}})


@pytest.fixture()
def cli(monkeypatch) -> FakeCli:
    fake = FakeCli()
    monkeypatch.setattr(cloud, "_run", fake.run)
    monkeypatch.setattr(cloud, "_binary", lambda name: name)
    monkeypatch.setattr(cloud.call_log, "record", lambda **row: fake.logs.append(row))
    return fake


def _user(db) -> User:
    user_id = uuid4()
    db.execute(text("INSERT INTO users (id, email, single_user_mode, created_at, updated_at) "
                    "VALUES (:id, :email, FALSE, now(), now())"), {"id": str(user_id), "email": f"cw-{user_id}@example.test"})
    db.commit()
    return db.get(User, user_id)


def _enable(db, transport: str = "subscription", slots: dict | None = None) -> None:
    set_parameter(db, code="ai.cloud_transport", value=transport, origin="user", rationale_fr="Test.")
    set_parameter(db, code="ai.cloud_slot_modes", value={"wr.hypothesis_pass": "live"} if slots is None else slots,
                  origin="user", rationale_fr="Test.")
    db.commit()


def _digest(db, user):
    week_start = date.today() - timedelta(days=date.today().weekday())
    db.add(ImperiumWeeklyReviewSession(user_id=user.id, week_start=week_start, week_end=week_start + timedelta(days=6),
                                       status="conversation_active", launched_at=datetime.now(UTC)))
    for offset in range(3):
        db.add(WrRollupDaily(user_id=user.id, local_date=week_start + timedelta(days=offset), domain="finance",
                             metrics={"income_cents": 10000, "expense_cents": 4000, "net_cents": 6000}))
    db.commit()
    item = docket.create_item(db, current_user=user, item_type="anomaly", domain="vault", title_fr="Écart carburant",
                              payload={"signal": "vault.fuel"}, evidence_refs={"events": ["evt_x"]},
                              impact_estimate=3, source_worker="w4")
    db.commit()
    row, _created = wr_digest.assemble_digest(db, current_user=user)
    return row, str(item.id)


def _final(item_id: str, refs: list[str] | None = None) -> dict:
    return {"systemic_hypotheses": [{"statement_fr": "Le carburant pèse sur le net.", "domains": ["vault", "vector"],
                                     "evidence_refs": refs or [item_id], "confidence": 140}],
            "agenda": [{"question_fr": "Pourquoi ce plein ?", "stake_fr": "Le net de la semaine.",
                        "refs": [item_id, "inventé"]}],
            "drill_requests": []}


def test_everything_is_off_by_default(db, cli) -> None:
    user = _user(db)
    digest_row, _item = _digest(db, user)
    assert cloud.transport(db) == "off"
    assert cloud.slot_mode(db, hypotheses.SLOT) == "off"
    row, stats = hypotheses.run_pass(db, user=user, digest=digest_row)
    assert row is None and stats.calls == 0 and cli.calls == []
    with pytest.raises(cloud.CloudError):
        cloud.structured(db, slot_code=hypotheses.SLOT, app_name="imperium", system="s", user="u", schema={})


def test_slot_guards(db, cli, monkeypatch) -> None:
    _enable(db, slots={"wr.hypothesis_pass": "live", "pulse.p3.design": "live", "chat.converse": "live"})
    assert cloud.slot_mode(db, hypotheses.SLOT) == "live"
    assert cloud.slot_mode(db, "pulse.p3.design") == "off"  # pas de rôle cloud branché pour ce slot
    assert cloud.slot_mode(db, "chat.converse") == "off"
    monkeypatch.setitem(cloud.SLOT_ROLES, "chat.converse", "first_cloud_tier")
    assert cloud.slot_mode(db, "chat.converse") == "off"  # slot local_default
    monkeypatch.setitem(cloud.SLOT_ROLES, hypotheses.SLOT, "local_executor")
    assert cloud.slot_mode(db, hypotheses.SLOT) == "off"  # rôle local
    monkeypatch.setitem(cloud.SLOT_ROLES, hypotheses.SLOT, "high_reasoning")
    _enable(db, transport="off")
    assert cloud.slot_mode(db, hypotheses.SLOT) == "off"


def test_claude_cli_runs_without_tools_and_pass_drills(db, cli) -> None:
    user = _user(db)
    digest_row, item_id = _digest(db, user)
    _enable(db)
    cli.outputs = [
        {"systemic_hypotheses": [], "agenda": [],
         "drill_requests": [{"query": "finance net", "scope": "rollups", "reason_fr": "Voir le net."},
                            {"query": "planning", "scope": "events", "reason_fr": "Voir les events."},
                            {"query": "fatigue", "scope": "memories", "reason_fr": "Mémoire."}]},
        _final(item_id, refs=[item_id, "drill:1", "rollup:finance", "drill:9"]),
    ]
    row, stats = hypotheses.run_pass(db, user=user, digest=digest_row)
    assert row is not None and stats.calls == 2 and stats.drills == 3
    args, stdin, cwd = cli.calls[0]
    assert args[:2] == ["claude", "-p"] and args[args.index("--tools") + 1] == ""
    assert args[args.index("--setting-sources") + 1] == "" and "--strict-mcp-config" in args
    assert "--no-session-persistence" in args and json.loads(args[args.index("--json-schema") + 1])["required"]
    assert "Écart carburant" in stdin and "imperium-cloud-" in cwd
    second = cli.calls[1][1]
    assert "Résultats des forages" in second and "\"drill:1\"" in second and "income_cents" in second
    assert "mémoire de long terme éteinte" in second
    assert json.loads(cli.calls[1][0][cli.calls[1][0].index("--json-schema") + 1])["properties"]["drill_requests"][
        "maxItems"] == 0
    hypothesis = row.output["systemic_hypotheses"][0]
    assert hypothesis["evidence_refs"] == [item_id, "drill:1", "rollup:finance"] and hypothesis["confidence"] == 100
    assert row.output["agenda"][0]["refs"] == [item_id] and stats.refs_dropped == 2
    assert [entry["scope"] for entry in row.drill_log] == ["rollups", "events", "memories"]
    assert row.drill_log[0]["chunks_returned"] == 3 and row.drill_log[2]["chunks_returned"] == 0
    assert row.model_used == "model-cloud-test" and row.prompt_tokens == 2006 and row.output_tokens == 400
    assert [log["trigger_source"] for log in cli.logs] == ["subscription_cli"] * 2
    assert all(log.get("success", True) for log in cli.logs) and cli.logs[0]["model_tier"] == "cloud_premium"
    assert stats.cost_usd == pytest.approx(0.24)
    again, again_stats = hypotheses.run_pass(db, user=user, digest=digest_row)  # une passe par digest
    assert again.id == row.id and again_stats.calls == 0 and len(cli.calls) == 2


def test_codex_cli_for_openai_roles(db, cli, monkeypatch) -> None:
    user = _user(db)
    digest_row, item_id = _digest(db, user)
    _enable(db)
    monkeypatch.setattr(cloud, "resolve_role", lambda db, code: SimpleNamespace(provider="openai", model_id="gpt-test",
                                                                                effort="high"))
    cli.outputs = [_final(item_id)]
    row, stats = hypotheses.run_pass(db, user=user, digest=digest_row)
    args, stdin, _cwd = cli.calls[0]
    assert args[:4] == ["codex", "exec", "-m", "gpt-test"] and args[-1] == "-"
    disabled = {args[i + 1] for i, value in enumerate(args) if value == "--disable"}
    assert {"shell_tool", "unified_exec", "browser_use", "computer_use", "plugins", "apps"} <= disabled
    assert {"--ignore-user-config", "--ephemeral", "--ignore-rules"} <= set(args) and "web_search=disabled" in args
    assert "model_reasoning_effort=high" in args and stdin.startswith(hypotheses.SYSTEM[:40])
    assert row.model_used == "gpt-test" and (row.prompt_tokens, row.output_tokens) == (900, 80)
    set_parameter(db, code="ai.cloud_subscription_models", value={"gpt-test": "gpt-sub"}, origin="user",
                  rationale_fr="Test.")
    cli.outputs = [_final(item_id)]
    cloud.structured(db, slot_code=hypotheses.SLOT, app_name="imperium", system="s", user="u", schema={})
    assert cli.calls[-1][0][:4] == ["codex", "exec", "-m", "gpt-sub"] and cli.logs[-1]["model_used"] == "gpt-sub"
    assert stats.calls == 1 and row.drill_log == []


def test_cli_failure_is_logged_and_nothing_is_stored(db, cli) -> None:
    user = _user(db)
    digest_row, _item = _digest(db, user)
    _enable(db)
    cli.outputs = [cloud.CloudError("Cloud CLI exited with 1.")]
    with pytest.raises(cloud.CloudError):
        hypotheses.run_pass(db, user=user, digest=digest_row)
    assert cli.logs[0]["success"] is False and cli.logs[0]["error_code"] == "CloudError"
    assert db.scalar(select(WrHypothesis).where(WrHypothesis.digest_id == digest_row.id)) is None


def test_job_skips_when_the_slot_is_off(db, cli) -> None:
    user = _user(db)
    digest_row, _item = _digest(db, user)
    event_id = db.execute(text("SELECT id FROM events WHERE event_type = 'planning.wr_digest.assembled' "
                               "AND user_id = :u"), {"u": str(user.id)}).scalar_one()
    ctx = SimpleNamespace(db=db, trigger_ref=event_id, items_in=None, items_out=None, detail=None)
    hypotheses.hypothesis_on_digest_job(ctx, SimpleNamespace(to_ts=None))
    assert ctx.detail == {"skipped": "slot_off"} and cli.calls == []
    _enable(db)
    cli.outputs = [_final(str(digest_row.digest["docket"]["anomaly"][0]["id"]))]
    hypotheses.hypothesis_on_digest_job(ctx, SimpleNamespace(to_ts=None))
    assert ctx.items_out == 1 and ctx.detail["calls"] == 1
