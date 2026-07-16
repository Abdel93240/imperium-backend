"""Embedding API wrapper (doc 38 §11) + top-K memory search (doc 38 §9).

Serving lives on Tower's P40 (qwen3-embedding:8b, Q8), exposed ONLY on Tower's
Tailscale IP: POST /embed {"texts": [...]} → {"vectors": [[...1024 floats]]},
GET /health. The client is deliberately thin: batching, short timeout, and a
typed GpuServiceUnreachable that runner jobs turn into a logged skip — a down
GPU service never fails a job.

This module does NOT touch memories.py (D5): it only brings the service that
memories.py has been waiting for. embeddings_enabled stays a user action after
the J+2 smoke checklist (ops/gpu/EMBEDDINGS_SMOKE_CHECKLIST.md) is green.
"""

import json
import logging
import urllib.error
import urllib.request
from typing import Literal, Protocol

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.services.params import get_parameter

logger = logging.getLogger(__name__)

EXPECTED_DIMENSIONS = 1024

# Full literal statements per mode — never assembled from fragments, so no
# dynamic SQL construction exists in this module (Bandit B608).
_SEARCH_MEMORIES_SQL = {
    "current_truth": """
        SELECT id AS memory_id, content, source_table, source_id, confidence,
               privacy_level::text AS privacy_level,
               (embedding <=> CAST(:query_vec AS vector)) AS distance,
               (1 - (embedding <=> CAST(:query_vec AS vector)))
                   * COALESCE(confidence, 1.0) AS final_score
        FROM ai_memories
        WHERE is_active = true
          AND (expires_at IS NULL OR expires_at > now())
        ORDER BY final_score DESC
        LIMIT :k
    """,
    "historical": """
        SELECT id AS memory_id, content, source_table, source_id, confidence,
               privacy_level::text AS privacy_level,
               (embedding <=> CAST(:query_vec AS vector)) AS distance,
               (1 - (embedding <=> CAST(:query_vec AS vector))) AS final_score
        FROM ai_memories
        WHERE is_active = true
          AND (expires_at IS NULL OR expires_at > now())
        ORDER BY final_score DESC
        LIMIT :k
    """,
}


class GpuServiceUnreachable(RuntimeError):
    """The Tower GPU service is down/unreachable — callers skip, never fail."""


class EmbeddingError(RuntimeError):
    pass


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class LocalQwen3Embedding:
    """V1 DEFAULT. Calls the local embedding service (privacy-first)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def embed(self, texts: list[str]) -> list[list[float]]:
        base_url = self.settings.embedding_base_url
        if not base_url:
            raise GpuServiceUnreachable("EMBEDDING_BASE_URL is not configured.")
        vectors: list[list[float]] = []
        batch_size = max(1, self.settings.embedding_batch_size)
        for start in range(0, len(texts), batch_size):
            vectors.extend(self._embed_batch(base_url, texts[start : start + batch_size]))
        return vectors

    def _embed_batch(self, base_url: str, batch: list[str]) -> list[list[float]]:
        body = json.dumps({"texts": batch}).encode("utf-8")
        request = urllib.request.Request(
            base_url.rstrip("/") + "/embed",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(  # nosec B310 - Tailscale-only internal URL
                request, timeout=self.settings.embedding_request_timeout_seconds
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise GpuServiceUnreachable(f"Embedding service unreachable: {exc}") from exc
        vectors = payload.get("vectors")
        if not isinstance(vectors, list) or len(vectors) != len(batch):
            raise EmbeddingError("Embedding service returned a malformed response.")
        for vector in vectors:
            if len(vector) != self.settings.embedding_expected_dimensions:
                raise EmbeddingError(
                    f"Embedding dimension mismatch: got {len(vector)}, "
                    f"expected {self.settings.embedding_expected_dimensions}."
                )
        return vectors


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Returns the configured provider. V1: local only (doc 38 §5.1)."""
    return LocalQwen3Embedding(settings=settings)


def embed(
    texts: list[str],
    *,
    privacy_check: bool = True,
    provider: EmbeddingProvider | None = None,
) -> list[list[float]]:
    """Embed texts through the local service.

    privacy_check is part of the graved signature: the full privacy_gate
    primitive arrives with the Pulse pass (T5). Until then the local-only
    provider IS the guarantee (nothing leaves the machine), and the flag is
    enforced trivially: cloud providers do not exist in this code path.
    """
    if not texts:
        return []
    provider = provider or get_embedding_provider()
    if privacy_check and not isinstance(provider, LocalQwen3Embedding):
        raise EmbeddingError("privacy_check requires the local embedding provider (doc 38 §5).")
    return provider.embed(texts)


def health_check(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    if not settings.embedding_base_url:
        return False
    request = urllib.request.Request(
        settings.embedding_base_url.rstrip("/") + "/health", method="GET"
    )
    try:
        with urllib.request.urlopen(  # nosec B310 - Tailscale-only internal URL
            request, timeout=settings.embedding_request_timeout_seconds
        ) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def search_memories(
    db: Session,
    query_vec: list[float],
    *,
    mode: Literal["current_truth", "historical"] = "current_truth",
    k: int = 5,
    threshold: float | None = None,
) -> list[dict]:
    """Top-K over ai_memories, both doc 38 modes.

    current_truth: final_score = cosine similarity × confidence (what is true NOW).
    historical:    final_score = cosine similarity alone (the weak witness is
                   wanted — doc 75 §7: confidence sorts, never excludes).
    Threshold comes from toolbox.topk_threshold (0.35, doc 38 §9.2).
    """
    if len(query_vec) != EXPECTED_DIMENSIONS:
        raise EmbeddingError(
            f"Query vector must have {EXPECTED_DIMENSIONS} dimensions, got {len(query_vec)}."
        )
    if threshold is None:
        threshold = float(get_parameter(db, "toolbox.topk_threshold", default=0.35))
    rows = db.execute(
        text(_SEARCH_MEMORIES_SQL[mode]),
        {"query_vec": "[" + ",".join(str(component) for component in query_vec) + "]", "k": k},
    ).mappings().all()
    return [dict(row) for row in rows if float(row["final_score"]) > threshold]
