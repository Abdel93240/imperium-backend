from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
from pathlib import Path

import pytest


ORCHESTRATOR_ROOT = Path("/opt/orchestrator")
if not ORCHESTRATOR_ROOT.is_dir():
    pytest.skip("orchestrator workspace is not available", allow_module_level=True)

os.environ.setdefault("DB_PASSWORD", "test-password")
sys.path.insert(0, str(ORCHESTRATOR_ROOT))

import asset_registry  # noqa: E402
import image_runner  # noqa: E402


class FakeOpenRouterResponse:
    status_code = 200
    text = "{}"

    def json(self) -> dict:
        image_b64 = base64.b64encode(b"generated-image").decode("ascii")
        return {
            "choices": [
                {
                    "message": {
                        "images": [
                            {
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_b64}",
                                },
                            },
                        ],
                    },
                },
            ],
        }


class FakeOpenRouterClient:
    captured_payload: dict | None = None

    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> "FakeOpenRouterClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, headers: dict, json: dict) -> FakeOpenRouterResponse:
        FakeOpenRouterClient.captured_payload = json
        return FakeOpenRouterResponse()


def _source_pack(root: Path, app: str = "imperium") -> Path:
    pack_dir = root / app / "20260101T000000Z"
    pack_dir.mkdir(parents=True)
    for index in range(1, 9):
        (pack_dir / f"asset_{index:02d}.png").write_bytes(b"png")
    return pack_dir


def test_openai_image_normal_mode_without_source_keeps_one_reference_max(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    refs = []
    for index in range(3):
        ref = tmp_path / f"ref_{index}.png"
        ref.write_bytes(f"ref-{index}".encode("ascii"))
        refs.append(ref)

    monkeypatch.setattr(image_runner.settings, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(image_runner, "IMAGES_DIR", tmp_path / "generated")
    monkeypatch.setattr(image_runner, "_collect_reference_paths", lambda app_key, max_files: refs)
    monkeypatch.setattr(image_runner.httpx, "AsyncClient", FakeOpenRouterClient)

    result = asyncio.run(
        image_runner.run_image(
            prompt="Assets:\n1. Respond Button",
            model_alias="openai_image",
            app_key="imperium",
        )
    )

    assert result.ok is True
    assert result.refs_used == 1
    payload = FakeOpenRouterClient.captured_payload
    assert payload is not None
    content = payload["messages"][0]["content"]
    image_parts = [part for part in content if part["type"] == "image_url"]
    assert len(image_parts) == 1


def test_semantic_path_validation_accepts_expected_path_and_refuses_escape_abs_and_depth() -> None:
    assert (
        asset_registry.validate_semantic_path("weekly_review/chatbot/respond_button")
        == "weekly_review/chatbot/respond_button"
    )

    assert asset_registry.validate_semantic_path("../escape") is None
    assert asset_registry.validate_semantic_path("/abs") is None
    assert asset_registry.validate_semantic_path("a/b/c/d/e/f") is None


def test_validate_pack_lands_assets_under_app_semantic_path_and_orch11_names_them(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    exported = tmp_path / "exported_assets"
    registry = tmp_path / "assets_registry"
    source_pack = _source_pack(exported)
    monkeypatch.setattr(asset_registry, "EXPORTED_ASSETS_DIR", exported)
    monkeypatch.setattr(asset_registry, "ASSETS_REGISTRY_DIR", registry)

    prompt = "\n".join(
        [
            "path: weekly_review/chatbot/respond_button",
            "Assets:",
            "1. Primary Respond Button",
            "2. Secondary Respond Button",
            "3. Voice Reply Button",
            "4. Confirm Answer Button",
            "5. Edit Answer Button",
            "6. Cancel Answer Button",
            "7. Disabled Respond Button",
            "8. Loading Respond Button",
        ]
    )

    result = asset_registry.validate_pack(
        source_pack_dir=str(source_pack),
        app_key="imperium",
        generator="openai_image",
        source_prompt=prompt,
        semantic_path="weekly_review/chatbot/respond_button",
    )
    assert result.ok is True

    pack_dir = Path(result.pack_dir)
    assert pack_dir.parent == (
        registry / "imperium" / "weekly_review" / "chatbot" / "respond_button"
    )
    assert result.timestamp == f"weekly_review/chatbot/respond_button/{pack_dir.name}"
    assert all((pack_dir / f"asset_{index:02d}.png").is_file() for index in range(1, 9))

    metadata = json.loads((pack_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["semantic_path"] == "weekly_review/chatbot/respond_button"
    assert metadata["naming_status"] == "auto"
    assert metadata["naming_model"] == "rule_based"
    assert metadata["asset_names"]["asset_01.png"] == "primary_respond_button"
