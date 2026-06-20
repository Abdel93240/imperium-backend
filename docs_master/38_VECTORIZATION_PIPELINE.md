# 38 - Vectorization Pipeline

## 1. Purpose

This document defines the **vectorization pipeline** that turns validated AI outputs (especially WR insights, decisions, patterns) into searchable semantic memory in pgvector.

It is the bridge between **canonical truth** (PostgreSQL tables) and **semantic memory** (pgvector).

It is referenced by:

- `09_PGVECTOR_MEMORY_POLICY.md` — overall memory policy
- `32_WR_INTERACTIVE_WORKFLOW.md` §9 — WR-specific extraction
- `34_PULSE_MEDICAL_FEED_AI.md` — medical rules also vectorized
- `30_AI_ROUTING_AND_SCORING_POLICY.md` — context retrieval at decision time

---

## 2. Core Principle

```text
pgvector is NEVER source of truth.
pgvector IS semantic memory for retrieval.

Canonical row in PostgreSQL → extracted elements → embedded → pgvector.

If pgvector is corrupted or lost: rebuild from canonical tables.
```

---

## 3. What Gets Vectorized

```text
HIGH PRIORITY (V1):
  ├─ Validated WR insights, decisions, patterns, wins, blockers
  └─ Validated medical rules (active ones only)

MEDIUM PRIORITY (V1.5):
  ├─ Vector signals (events, disruptions) — short retention
  ├─ Vault weekly summaries
  └─ Pulse weekly summaries

LOW PRIORITY (V2+):
  ├─ Imperium memory candidates
  ├─ Email triage decisions
  └─ Conversation history with Imperium chatbot
```

V1 implements only HIGH PRIORITY. The pipeline is designed to extend.

---

## 4. Pipeline Architecture

```text
┌──────────────────────────────────────────────┐
│ TRIGGER                                      │
│ User validates AI result that produces       │
│ structured insights/decisions/rules          │
└───────────────────┬──────────────────────────┘
                    │
┌───────────────────▼──────────────────────────┐
│ EXTRACTOR                                    │
│ Parses structured_result.extracted_for_memory│
│ Splits into individual elements              │
└───────────────────┬──────────────────────────┘
                    │
┌───────────────────▼──────────────────────────┐
│ EMBEDDER                                     │
│ Generates embedding for each element         │
│ Uses local embedding model OR cloud API      │
└───────────────────┬──────────────────────────┘
                    │
┌───────────────────▼──────────────────────────┐
│ STORER                                       │
│ Writes to pgvector_memory with metadata      │
│ Sets initial weight = 1.0                    │
│ Sets created_at, source, source_ref          │
└───────────────────┬──────────────────────────┘
                    │
┌───────────────────▼──────────────────────────┐
│ DECAY SCHEDULER (daily cron)                 │
│ Recomputes weight based on age               │
│ Marks elements past 5 weeks as inactive      │
└──────────────────────────────────────────────┘
```

---

## 5. Embedding Model Choice

> **DÉCISION V1 (mise à jour) : embedding LOCAL Qwen3-Embedding par défaut.**
> Choix tranché pour la cohérence avec la philosophie privacy de l'écosystème :
> les données ne doivent pas sortir vers un fournisseur cloud par défaut (cf.
> règles PRIV-001 / PRIV-002, doc 08). Le cloud (OpenAI/Voyage) devient une
> option de secours, pas le défaut.

### 5.1 V1 default: local embedding (Qwen3-Embedding)

```text
Model:     Qwen3-Embedding (local, GPU-served), privacy-first
Dimension: 1024   (Matryoshka — the model supports up to 1024; we use 1024)
```

Rationale: best cross-domain semantic quality with excellent French; same model
family as the Qwen3 routing model (ecosystem coherence). Multilingual breadth is
NOT a selection driver here (usage is ~99.9% French; Arabic/religious content is
mostly hard-coded rules, not vectorized). The driver is reasoning quality on
French, where Qwen3-Embedding is strong.

Quality > dimension: 1024 dims of a strong model beat 1536 of a weaker one.
Quantization note: Q8 keeps ~99% quality and is safe for embeddings; **Q4 and
below are NOT acceptable for embeddings** (they distort the numeric distances
that retrieval depends on). FP16 = full quality when the hardware allows it.

### 5.2 Option de secours: cloud embedding (OpenAI / Voyage)

```text
Model:    text-embedding-3-small (OpenAI) or voyage-3-lite
Dimension: 1536 (small) or 1024 (voyage-3-lite)
Cost:     ~$0.02 per million tokens
Latency:  ~200ms per element
```

À n'utiliser que si Qwen3-Embedding local devient impossible à héberger, et uniquement
pour des données non sensibles ayant passé le privacy gate. **Ce n'est pas le
défaut.**

### 5.3 Embedding consistency

```text
Once chosen, the embedding model MUST stay consistent for the lifetime of pgvector_memory.

If switching models later:
  → re-embed all entries
  → atomic swap (build new column, switch index, drop old)
  → planned migration, not on-the-fly
```

---

## 6. Extraction Per Source Type

### 6.1 WR validated → extraction

When a WR is validated, the backend extracts from `report_json.extracted_for_memory`:

```python
{
  "insights":  [...],   # observations
  "decisions": [...],   # commitments
  "patterns":  [...],   # recurring behaviors
  "wins":      [...],   # what worked
  "blockers":  [...]    # what blocked
}
```

Each list item becomes one row in `pgvector_memory`.

### 6.2 Medical rules validated → extraction

When a user validates medical rules, each accepted rule becomes one entry:

```python
content = f"{rule.action} (rationale: {rule.rationale})"
metadata = {
  "source": "medical_rule",
  "rule_id": rule.id,
  "rule_type": rule.rule_type,
  "priority": rule.priority,
  ...
}
```

---

## 7. The Memory Table (canonical: ai_memories)

This pipeline does NOT define its own table. The canonical memory table is
`ai_memories`, owned by doc 09 (AI Memory Policy). See doc 09 for the full schema.

Key points relevant to this pipeline:
- column `embedding vector(1024)` (Qwen3-Embedding, dim 1024)
- column `confidence` (rises with repeated evidence, never decays — NO `weight`)
- column `privacy_level` (mandatory on every row)
- columns `source_table` / `source_id` (path back to the rich source log)
- column `learning_element_type` (open label; no logic branches on its value)
- supersession via `supersedes_memory_id`; `is_active` for soft-deactivate

There is NO `weight` column and NO temporal decay anywhere (see §8).

CREATE INDEX pgvector_memory_embedding_idx
ON pgvector_memory
USING hnsw (embedding vector_cosine_ops);

CREATE INDEX pgvector_memory_user_active_idx
ON pgvector_memory (user_id, source, status)
WHERE status = 'active';

CREATE INDEX pgvector_memory_source_ref_idx
ON pgvector_memory (source_ref_type, source_ref_id);

### 7.1 Field meanings

```text
content         - the natural-language text (used for re-embedding if needed)
embedding       - vector representation
source          - "weekly_report" | "medical_rule" | ...
source_ref_type - which canonical table the source lives in
source_ref_id   - id in that canonical table
element_type    - "insight" | "decision" | "pattern" | "win" | "blocker" |
                  "nutrition_rule" | "training_rule" | etc.
metadata        - free-form JSONB (week_start, priority, etc.)
weight          - current weight (decayed over time)
status          - "active" | "expired" | "superseded"
expires_at      - hard cutoff when status auto-flips to "expired"
```

---

## 8. Temporal Decay Function

WR vectors carry decreasing weight over time (per doc 32 §9.3):

```text
Age (weeks)    Weight
─────────────────────
0              1.00
1              0.70
2              0.40
3              0.20
4              0.05
5+             excluded (status = 'expired')
```

Other source types may have different decay curves:

```text
Medical rules:
  - active until rule.duration_days expires (or never if NULL)
  - weight stays 1.0 while rule is active
  - drops to 0 when rule expires or is superseded

Vector signals (V1.5):
  - 6 hours active, then expired
  - weight stays 1.0 while active

Vault/Pulse weekly summaries:
  - same decay as WR (5-week horizon)
```

### 8.1 Decay applied at retrieval time

```python
# At retrieval:
final_score = cosine_similarity * weight
```

The decay multiplier is applied **at query time**, not stored as the cosine itself. This way:

- weights can be recomputed without re-embedding
- decay strategy can change without data migration

### 8.2 Weight refresh cron

```text
Daily cron at 04:00 UTC:
  → recompute weights for all active entries
  → mark entries with weight < 0.05 as 'expired'
  → cleanup: delete expired entries older than 90 days
```

---

## 9. Retrieval At Decision Time

When Vector / Imperium / Pulse needs context:

```python
def retrieve_context(user_id, query_text, source_filter=None, top_k=3):
    query_embedding = embed(query_text)
    
    sql = """
        SELECT id, content, source, element_type, weight,
               (embedding <=> %s) AS distance,
               (1 - (embedding <=> %s)) * weight AS final_score
        FROM pgvector_memory
        WHERE user_id = %s
          AND status = 'active'
          AND (%s IS NULL OR source = %s)
        ORDER BY final_score DESC
        LIMIT %s
    """
    return db.execute(sql, [
        query_embedding, query_embedding,
        user_id,
        source_filter, source_filter,
        top_k
    ])
```

### 9.1 Injection into prompts

Retrieved context is injected as **soft information**, never as commands:

```text
Recent validated insights (informational only, not enforced):

[2026-04-27, decision, weight=0.70]
"Reduce VTC on Tuesday evenings due to fatigue"

[2026-04-20, pattern, weight=0.40]
"CA drops by 22% after intense workout days"

The user can ignore these. Surface them only if directly relevant.
```

### 9.2 Filtering by relevance threshold

```text
Only inject if final_score > 0.35
Avoids polluting prompts with weak matches
```

---

## 10. The Vectorization Service Module

```text
backend/app/services/ai/vectorize.py
```

Public functions:

```python
def vectorize_wr_validation(
    db: Session,
    *,
    current_user: User,
    weekly_report: WeeklyReport,
) -> int:
    """
    Called when a WR is validated.
    Extracts elements from report_json, embeds, stores.
    Returns count of vectors created.
    """

def vectorize_medical_rule(
    db: Session,
    *,
    current_user: User,
    rule: PulseMedicalRule,
) -> uuid.UUID:
    """
    Called when a medical rule is validated.
    Returns the new pgvector_memory.id.
    """

def search_memory(
    db: Session,
    *,
    current_user: User,
    query_text: str,
    source_filter: str | None = None,
    top_k: int = 3,
    min_score: float = 0.35,
) -> list[MemoryRetrievalResult]:
    """
    Retrieves top-k semantically relevant entries.
    Applies decay weighting and threshold filtering.
    """

def supersede_entries(
    db: Session,
    *,
    user_id: uuid.UUID,
    source_ref_type: str,
    source_ref_id: uuid.UUID,
) -> int:
    """
    Marks all entries from a source as 'superseded'.
    Used when an old rule is replaced by a new one.
    Returns count of superseded entries.
    """

def decay_refresh(db: Session) -> dict:
    """
    Daily cron job. Updates weights and expires old entries.
    Returns {refreshed: N, expired: M}.
    """
```

---

## 11. Embedding API Wrapper

```text
backend/app/services/ai/embedding.py
```

Abstracts the embedding provider so we can swap later:

```python
class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...

class OpenAIEmbedding(EmbeddingProvider):
    """Fallback option. Calls OpenAI text-embedding-3-small (non-default, privacy gate required)."""

class LocalQwen3Embedding(EmbeddingProvider):
    """V1 DEFAULT. Calls local Qwen3-Embedding (privacy-first)."""

def get_embedding_provider() -> EmbeddingProvider:
    """Returns the configured provider based on env."""
```

Configuration via env:

```text
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=Qwen3-Embedding
OPENAI_API_KEY=sk-...
```

Embedding hardware plan (transitional → final):
- **Bridge (now):** a dedicated GPU for embedding — Tesla **P40 24GB** running
  Qwen3-Embedding in **Q8** (~99% quality, fast ~0.2 s/query). Chosen over M40:
  Pascal (CC 6.1) is still supported by current CUDA/PyTorch, whereas Maxwell
  (M40, CC 5.2) is being dropped. P40 needs an added blower+shroud (passive
  card). The routing Qwen3-32B stays on the V100; no VRAM conflict.
- **Then:** migrate everything onto the server (full re-host).
- **Final:** a 2nd V100 → Qwen3-Embedding in **FP16** (100% quality, fast).

Note: P40/M40 have weak FP16, which is why the bridge runs Q8 (not FP16). Full
FP16 quality is deferred to the V100 stage. Q8 vs FP16 ≈ 1% quality, acceptable
for the transition.

Open item (backlog): confirm the exact Qwen3-Embedding size to serve
(0.6B / 4B / 8B) given the bridge P40 (24GB is ample) vs final V100. Larger is
fine on 24GB; the choice is quality vs load time. Track separately.

---

## 12. Idempotency

### 12.1 Same source, same elements

If a WR validation is replayed (idempotency replay), the vectorization must not duplicate entries.

Detection logic:

```python
existing = db.scalar(select(PgvectorMemory).where(
    PgvectorMemory.source_ref_type == "weekly_report",
    PgvectorMemory.source_ref_id == wr.id,
).limit(1))

if existing:
    # Already vectorized, skip
    return 0
```

### 12.2 New version supersedes old

If a WR is corrected (creates a new `weekly_reports` row with `superseded_by`):

```python
# 1. Mark old entries as superseded
supersede_entries(
    user_id=user.id,
    source_ref_type="weekly_report",
    source_ref_id=old_wr_id,
)

# 2. Vectorize new WR
vectorize_wr_validation(db, current_user=user, weekly_report=new_wr)
```

---

## 13. Observability

Each vectorization call logs:

```text
operation:    "vectorize_wr" | "vectorize_medical_rule" | ...
source_id:    UUID of source entity
elements_in:  count extracted
elements_out: count successfully stored
errors:       list of failures
duration_ms:  time taken
embedding_provider: "openai" | "local"
estimated_cost_eur: tracked for reporting
```

Aggregated daily:

```text
daily_vectorization_count
daily_vectorization_cost
daily_avg_duration
daily_failure_rate
```

---

## 14. Failure Modes

### 14.1 Embedding API down

```text
Backend retries up to 3 times with backoff
If still failing: stores entries with embedding = NULL
Background job re-attempts later
WR validation NOT blocked by embedding failure
```

The WR is still canonical — vectorization is best-effort enrichment.

### 14.2 pgvector index corrupted

```text
Detection: query returns empty or wrong results despite known data
Recovery:
  REINDEX TABLE pgvector_memory;
Or full rebuild from canonical sources:
  python -m app.scripts.rebuild_vector_memory
```

### 14.3 Embedding provider switch

Planned migration documented in Section 5.3.

---

## 15. Testing

### 15.1 Unit tests

```text
- vectorize_wr_validation extracts correctly
- decay weights compute correctly at various ages
- supersede marks entries correctly
- search filters by user, source, status
```

### 15.2 Integration tests

```text
- Validate a fake WR → check pgvector entries
- Run decay cron → check weight updates
- Search for known query → check top result
```

### 15.3 Quality tests (manual)

```text
After 1 month of real WR data:
  - Run sample queries
  - Assess if retrieved context is genuinely relevant
  - Tune threshold (currently 0.35) if needed
```

---

## 16. References

- `09_PGVECTOR_MEMORY_POLICY.md` — overall memory policy
- `32_WR_INTERACTIVE_WORKFLOW.md` §9 — WR vectorization specifics
- `34_PULSE_MEDICAL_FEED_AI.md` — medical rules vectorization
- `30_AI_ROUTING_AND_SCORING_POLICY.md` — when context retrieval happens

---

**Document version:** 1.0
**Status:** Vectorization V1 reference
**Last updated:** 2026-04-28
