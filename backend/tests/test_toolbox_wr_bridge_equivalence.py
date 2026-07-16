"""§13.2 n8n bridges: input/output equivalence on the JSON export payloads,
mock become fixture, n8n_client without caller."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from fixtures.n8n_wr_payloads import (
    EXPECTED_ANSWERS_ATTACH_TEMPLATE,
    EXPECTED_ANSWERS_CALLBACK_RESULT_TYPE,
    EXPECTED_ANSWERS_CALLBACK_SOURCE,
    EXPECTED_ANSWERS_CALLBACK_SUMMARY,
    EXPECTED_ANSWERS_CALLBACK_TITLE,
    EXPECTED_ANSWERS_RAW_WORKFLOW,
    EXPECTED_START_ATTACH_TEMPLATE,
    answers_integrate_payload,
    interactive_start_payload,
    mock_workflow_callback_body,
)

from app.models.ai import AITask
from app.services.imperium import wr_bridge

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent


def _task(payload: dict, task_type: str) -> AITask:
    return AITask(
        id=payload and uuid4(),
        user_id=uuid4(),
        task_type=task_type,
        status="queued",
        source_module="imperium",
        input_payload={},
        prepared_payload=payload,
    )


def _capture(monkeypatch):
    captured = {}

    def fake_receive(db, *, task_id, payload, idempotency_key):
        captured["callback"] = payload
        captured["callback_key"] = idempotency_key
        result = SimpleNamespace(id=uuid4())
        captured["result_id"] = result.id
        return result, False

    def fake_attach(db, *, session_id, payload, idempotency_key, request_method, request_path):
        captured["attach_key"] = idempotency_key
        captured["attach_result_id"] = payload.ai_result_id
        captured["attach_path"] = request_path
        return SimpleNamespace(), False

    monkeypatch.setattr(wr_bridge, "receive_ai_result", fake_receive)
    monkeypatch.setattr(wr_bridge, "attach_ai_result_to_session", fake_attach)
    monkeypatch.setattr(wr_bridge, "resolve_model_id", lambda role, db=None: "qwen3-32b")
    return captured


def test_answers_integrate_bridge_output_equals_export_output(monkeypatch) -> None:
    # Field-for-field the callback body of the export's Code node, HMAC removed
    # (no network hop) and model resolved by role (DV-6) — the only divergences.
    task_id, session_id = str(uuid4()), str(uuid4())
    message_id, answer = str(uuid4()), "Réponse de test"
    payload = answers_integrate_payload(
        task_id=task_id, session_id=session_id, user_message_id=message_id, user_answer=answer
    )
    task = _task(payload, "weekly_report.answers.integrate")
    task.id = task_id
    captured = _capture(monkeypatch)

    wr_bridge.run_wr_answers_integrate(None, ai_task=task)

    callback = captured["callback"]
    assert callback.result_type == EXPECTED_ANSWERS_CALLBACK_RESULT_TYPE
    assert callback.result_payload["title"] == EXPECTED_ANSWERS_CALLBACK_TITLE
    assert callback.result_payload["summary"] == EXPECTED_ANSWERS_CALLBACK_SUMMARY
    assert callback.result_payload["source"] == EXPECTED_ANSWERS_CALLBACK_SOURCE
    assert callback.result_payload["sections"][0]["content"] == (
        f"User answer captured for message {message_id}: {answer}"
    )
    assert callback.result_payload["questions_answered"] == [
        {"message_id": message_id, "answer": answer}
    ]
    assert callback.provider == "qwen-dry-run"
    assert float(callback.confidence) == 0.7
    assert callback.raw_payload == {"workflow": EXPECTED_ANSWERS_RAW_WORKFLOW, "dry_run": True}
    assert captured["callback_key"] == f"wr_qwen_dry_run_result_{task_id}"
    assert captured["attach_key"] == EXPECTED_ANSWERS_ATTACH_TEMPLATE.format(
        session_id=session_id, result_id=captured["result_id"]
    )
    assert captured["attach_result_id"] == captured["result_id"]


def test_interactive_start_attach_key_matches_export(monkeypatch) -> None:
    task_id, session_id = str(uuid4()), str(uuid4())
    payload = interactive_start_payload(task_id=task_id, session_id=session_id)
    task = _task(payload, "weekly_report.interactive.start")
    task.id = task_id
    captured = _capture(monkeypatch)

    wr_bridge.run_wr_interactive_start(None, ai_task=task)

    assert captured["attach_key"] == EXPECTED_START_ATTACH_TEMPLATE.format(
        session_id=session_id, result_id=captured["result_id"]
    )
    assert captured["attach_path"] == payload["wr_attach_url"]


def test_bridge_applies_same_field_validations_as_export(monkeypatch) -> None:
    _capture(monkeypatch)
    task_id, session_id = str(uuid4()), str(uuid4())
    valid = interactive_start_payload(task_id=task_id, session_id=session_id)

    missing = dict(valid)
    missing.pop("week_start")
    with pytest.raises(wr_bridge.WRBridgePayloadError, match="week_start"):
        wr_bridge.run_wr_interactive_start(None, ai_task=_task(missing, "x"))

    wrong_type = dict(valid, task_type="weekly_report.other")
    with pytest.raises(wr_bridge.WRBridgePayloadError, match="Unsupported task_type"):
        wr_bridge.run_wr_interactive_start(None, ai_task=_task(wrong_type, "x"))

    wrong_callback = dict(valid, callback_url="/api/internal/ai/tasks/other/result")
    with pytest.raises(wr_bridge.WRBridgePayloadError, match="callback_url"):
        wr_bridge.run_wr_interactive_start(None, ai_task=_task(wrong_callback, "x"))


def test_mock_workflow_removed_from_repo_and_fixture_carries_contract() -> None:
    assert not (REPO_ROOT / "ops" / "n8n" / "workflows" / "wr_interactive_start_mock.json").exists()
    remaining = sorted(
        item.name for item in (REPO_ROOT / "ops" / "n8n" / "workflows").iterdir()
    )
    assert remaining == [
        "wr_answers_integrate_qwen_dry_run.json",
        "wr_interactive_start_qwen_dry_run.json",
    ]
    body = mock_workflow_callback_body(week_start="2026-04-27", week_end="2026-05-03")
    assert json.dumps(body)  # serialisable contract fixture


def test_n8n_client_has_no_caller_and_config_is_deprecated() -> None:
    result = subprocess.run(
        ["grep", "-rln", "--include=*.py", "n8n_client", str(BACKEND_ROOT / "app")],
        capture_output=True,
        text=True,
        check=False,
    )
    files = [line for line in result.stdout.splitlines() if not line.endswith("n8n_client.py")]
    assert files == []

    config_text = (BACKEND_ROOT / "app" / "core" / "config.py").read_text(encoding="utf-8")
    n8n_block = config_text.split("n8n_base_url")[0]
    assert "DEPRECATED" in n8n_block
