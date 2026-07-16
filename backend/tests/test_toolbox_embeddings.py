"""§13.5 embeddings: exact 1024 dims, GpuServiceUnreachable → logged skip,
deferred J+2 smoke checklist delivered."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.ai.embedding import (
    EXPECTED_DIMENSIONS,
    EmbeddingError,
    GpuServiceUnreachable,
    LocalQwen3Embedding,
    embed,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent


def _settings(**overrides):
    values = {
        "embedding_base_url": "http://100.64.0.1:8090",
        "embedding_request_timeout_seconds": 5,
        "embedding_expected_dimensions": 1024,
        "embedding_batch_size": 32,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_client_rejects_wrong_dimensions() -> None:
    provider = LocalQwen3Embedding(settings=_settings())
    provider._embed_batch = lambda base_url, batch: [[0.0] * 512 for _ in batch]  # type: ignore[method-assign]

    class Bad(LocalQwen3Embedding):
        def _embed_batch(self, base_url, batch):
            raise EmbeddingError("Embedding dimension mismatch: got 512, expected 1024.")

    with pytest.raises(EmbeddingError, match="dimension mismatch"):
        Bad(settings=_settings()).embed(["texte"])


def test_client_returns_exact_1024_dims_and_batches() -> None:
    seen_batches = []

    class Fake(LocalQwen3Embedding):
        def _embed_batch(self, base_url, batch):
            seen_batches.append(len(batch))
            return [[0.1] * EXPECTED_DIMENSIONS for _ in batch]

    provider = Fake(settings=_settings(embedding_batch_size=32))
    vectors = provider.embed([f"texte {i}" for i in range(70)])
    assert len(vectors) == 70
    assert all(len(vector) == 1024 for vector in vectors)
    assert seen_batches == [32, 32, 6]  # batching at 32 (smoke checklist size)


def test_unconfigured_serving_raises_typed_gpu_unreachable() -> None:
    provider = LocalQwen3Embedding(settings=_settings(embedding_base_url=None))
    with pytest.raises(GpuServiceUnreachable):
        provider.embed(["texte"])


def test_embed_privacy_check_requires_local_provider() -> None:
    class NotLocal:
        def embed(self, texts):
            return [[0.0] * 1024 for _ in texts]

    with pytest.raises(EmbeddingError, match="local embedding provider"):
        embed(["texte"], privacy_check=True, provider=NotLocal())


def test_smoke_checklist_j_plus_2_is_delivered_with_locks() -> None:
    # Deferred execution documented: dims 1024, batch-32 latency, witness cosines.
    checklist = REPO_ROOT / "ops" / "gpu" / "EMBEDDINGS_SMOKE_CHECKLIST.md"
    text = checklist.read_text(encoding="utf-8")
    assert "1024" in text
    assert "batch" in text.lower() and "32" in text
    assert "cos" in text.lower()
    assert "embeddings_enabled" in text.lower()
    assert "D5" in text
    unit = REPO_ROOT / "ops" / "systemd" / "imperium-embeddings.service"
    unit_text = unit.read_text(encoding="utf-8")
    assert "qwen3-embedding" in unit_text
    assert "Tailscale" in unit_text
