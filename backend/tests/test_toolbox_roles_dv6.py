"""§13.10 DV-6: zero hard-coded legacy 7B model id; roles resolved via ai_role_models."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from _postgres import require_test_database_url

BACKEND_ROOT = Path(__file__).resolve().parents[1]
LEGACY_7B = "qwen2.5" + ":7b"  # assembled so this test file never matches itself


def test_grep_legacy_7b_model_is_zero_outside_changelog() -> None:
    result = subprocess.run(
        [
            "grep",
            "-rln",
            "--include=*.py",
            LEGACY_7B,
            str(BACKEND_ROOT / "app"),
            str(BACKEND_ROOT / "tests"),
            str(BACKEND_ROOT / "alembic"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout.strip() == ""


def test_local_executor_role_is_seeded_with_qwen3_32b() -> None:
    pytest.importorskip("psycopg")
    from sqlalchemy.orm import Session

    from app.services.ai.roles import LOCAL_EXECUTOR_ROLE, resolve_role

    engine = create_engine(require_test_database_url("ai role models tests"), future=True)
    try:
        with Session(engine) as db:
            role = resolve_role(db, LOCAL_EXECUTOR_ROLE)
            assert role.model_id == "qwen3-32b"
            assert role.provider == "local"
            assert role.sensitivity_route == "local_only"
            # Doc 30 §3 seed with Fable 5 restored (patch §7.8 in this pass).
            sustained = resolve_role(db, "sustained_long_context")
            assert sustained.model_id == "claude-fable-5"
            assert sustained.active is True
    finally:
        engine.dispose()


def test_qwen_client_resolves_model_through_role(monkeypatch) -> None:
    from app.services.ai.providers import qwen as qwen_module

    monkeypatch.setattr(
        qwen_module, "resolve_model_id", lambda role, db=None: "qwen3-32b"
    )
    client = qwen_module.QwenClient()
    assert client.model_id == "qwen3-32b"
    decision = client.classify_task(task_type="imperium.test", input_payload={"x": 1})
    assert decision.recommended_model in {"qwen3-32b", "strong_model_required_by_policy"}
