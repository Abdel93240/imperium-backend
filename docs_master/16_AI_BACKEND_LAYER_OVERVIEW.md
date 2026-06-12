# 16 - AI Backend Layer Overview

## 1. Purpose

This document gives the **architectural overview** of how the AI layer integrates into the Imperium backend.

It connects the dots between:

- the routing policy (doc 30)
- the AI tables and contracts (doc 31)
- the WR interactive workflow (doc 32)
- the existing backend services (`imperium`, `vault`, etc.)
- n8n orchestration
- Qwen local routing
- pgvector semantic memory

Read this before implementing any AI-related backend code.

---

## 2. Layer Architecture

```text
┌────────────────────────────────────────────────────────┐
│  ANDROID APPS (V2)                                     │
│  - display, collect, trigger                           │
└────────────────────┬───────────────────────────────────┘
                     │ HTTPS + JWT
┌────────────────────▼───────────────────────────────────┐
│  IMPERIUM BACKEND (FastAPI)                            │
│  ├─ /api/auth                                       │
│  ├─ /api/imperium                                   │
│  ├─ /api/vault                                      │
│  ├─ /api/ai          ◄── NEW LAYER                  │
│  ├─ /api/internal    (HMAC signed)                  │
│  └─ Services + business rules + idempotency            │
└──────┬─────────────────────────────────────┬───────────┘
       │                                     │
       │ Signed webhook                      │ SQL
       │                                     │
┌──────▼──────────┐                ┌─────────▼──────────┐
│  n8n            │                │ PostgreSQL         │
│  - orchestrator │                │ imperium_core      │
│  - workflows    │                │ + pgvector         │
└─────┬───────────┘                └────────────────────┘
      │
      ├─ Qwen 32B (local, GPU-served on V100 / qwen3:32b)
      ├─ Whisper local (faster-whisper)
      ├─ Claude Sonnet/Opus (cloud API)
      ├─ GPT-5.5 (cloud API)
      └─ Gemini (cloud API)
```

---

## 3. The AI Layer In Three Tables

The entire AI activity is captured by three canonical tables:

```text
ai_tasks               - the request: "do X"
ai_results             - the answer: "here is what the model produced"
ai_result_validations  - the user's decision on a result: "accepted / rejected"
```

These tables are defined in detail in doc 31.

Every AI interaction in the system flows through these tables, whatever the source (button click, cron, webhook, file upload).

---

## 4. Lifecycle Of An AI Action

```text
1. TRIGGER
   (app button, cron, db event, webhook, email, file)
        ↓
2. BACKEND CREATES ai_task
   (status = queued, idempotency_key set)
        ↓
3. BACKEND POSTS SIGNED WEBHOOK TO n8n
   (n8n is notified, not polling)
        ↓
4. n8n CLAIMS THE TASK
   (fetches context via internal API)
        ↓
5. QWEN ROUTES + SCORES (`/200`)
   (decides which model to call)
        ↓
6. CHOSEN MODEL EXECUTES
   (Sonnet, Opus, GPT-5.5, Gemini, or Qwen itself)
        ↓
7. n8n POSTS CALLBACK TO BACKEND
   (signed HMAC + timestamp + idempotency)
        ↓
8. BACKEND STORES ai_result
   (validates contract, status updated)
        ↓
9. EVENT EMITTED
   (ai.result.stored, append-only)
        ↓
10. UI POLLED OR PUSHED TO USER
        ↓
11. USER VALIDATES (if required)
    OR result is informational only
        ↓
12. CANONICAL WRITE (if validation accepted)
    (e.g. mission created, transaction stored, WR canonical)
```

---

## 5. Where Each Component Lives

### 5.1 Backend code structure

```text
backend/app/
├─ models/
│  ├─ ai.py                         (AiTask, AiResult, AiResultValidation)
│  └─ imperium.py                   (existing, plus WR state extension)
├─ schemas/
│  ├─ ai.py                         (Pydantic schemas)
│  └─ imperium.py                   (existing)
├─ services/
│  ├─ ai/
│  │  ├─ tasks.py                   (create, fetch, transition state)
│  │  ├─ results.py                 (store callback results)
│  │  ├─ validations.py             (user accept/reject)
│  │  └─ vectorize.py               (extract → pgvector with decay)
│  ├─ imperium/
│  │  ├─ wr_session.py              (WR interactive sessions)
│  │  └─ (existing files)
│  └─ (other domains)
├─ api/v1/routes/
│  ├─ ai.py                         (AI endpoints, see Section 7)
│  ├─ wr.py                         (WR interactive endpoints, doc 32)
│  ├─ internal.py                   (n8n callbacks, signed)
│  └─ (existing files)
└─ core/
   ├─ internal_webhooks.py          (HMAC verification, existing)
   └─ idempotency.py                (existing)
```

### 5.2 n8n workflows

```text
n8n/workflows/
├─ wr_interactive_analysis.json     (doc 32)
├─ vector_event_scan.json           (doc 30 §6.8, doc 31 §10)
├─ vault_receipt_extract.json       (doc 31 §11)
├─ pulse_medical_analyze.json       (doc 34)
├─ imperium_email_triage.json       (doc 31 §12)
└─ generic_ai_task_router.json      (handles any ai_task type)
```

Each workflow follows the same pattern:

```text
trigger → fetch context (backend API)
        → Qwen route + score
        → call selected model
        → POST callback to backend
```

### 5.3 Qwen runtime

```text
Ollama/Qwen in Docker on the VPS:
└─ Model: qwen3:32b (Q4_K_M, ~20-24 GB VRAM on V100)
   Endpoint: internal Docker network only, for example http://ollama:11434/api/generate
   Network: same internal Docker network as n8n, and reachable by backend through internal networking
   Public exposure: forbidden
   Used primarily by: n8n (orchestrated workflows)
   Used directly by backend: only for documented latency-critical exceptions
                             (see Section 5.4)
```

### 5.4 Direct Backend → Qwen exception (latency-critical)

By default, all AI calls go through n8n. This keeps responsibility boundaries clear.

**One documented exception**: real-time Vector profitability advisory while a VTC session is active.

```text
Why the exception:
├─ Latency target: <2s (Bolt ride offer expires fast)
├─ Going via n8n adds 500ms-1s of network overhead per hop
├─ User has explicitly started a VTC session (consent)
└─ The flow is short: Gemini OCR → Qwen profitability score → advisory color

Why this is safe:
├─ The two API calls are simple (no orchestration, no retry, no chain)
├─ Failure handling stays in the backend service
├─ User session is the gate (no calls without active session)
└─ This exception is the ONLY one in V1
```

This exception applies **only** to `vector.ride_overlay_decision` (per doc 33 §5.2).

All other Vector tasks (event scan, disruption triage, WR contribution, WRS learning loop) still go through n8n.

If a similar latency-critical case appears later, it must be documented here explicitly. No silent backend → AI direct calls allowed elsewhere.

---

## 6. The Three Storage Layers

```text
┌─────────────────────────────────────────────────────┐
│ LAYER 1: WORKING DATA                               │
│ - ai_tasks (lifecycle)                              │
│ - ai_results (every model output)                   │
│ - retention: 90 days post-completion                │
└─────────────────────────────────────────────────────┘
                       ↓ user validation
┌─────────────────────────────────────────────────────┐
│ LAYER 2: CANONICAL DATA                             │
│ - imperium_missions, vault_transactions,            │
│   weekly_reports, etc.                              │
│ - retention: forever                                │
│ - source of truth for the application               │
└─────────────────────────────────────────────────────┘
                       ↓ extraction at validation time
┌─────────────────────────────────────────────────────┐
│ LAYER 3: SEMANTIC MEMORY                            │
│ - pgvector_memory                                   │
│ - retention: forever (with temporal decay weighting)│
│ - never canonical, always informational             │
└─────────────────────────────────────────────────────┘
```

---

## 7. Backend API Endpoints (AI layer)

All endpoints require JWT auth and `Idempotency-Key` on POSTs.

### Public AI endpoints

```text
POST /api/ai/tasks
     Create an AI task (any task_type).
     Body: { task_type, source, input_payload, ... }
     Returns: ai_task with status="queued"

GET  /api/ai/tasks/{task_id}
     Read task state and current results.

GET  /api/ai/tasks?status=&task_type=&limit=
     List user tasks (paginated).

POST /api/ai/results/{result_id}/accept
     User validates an AI result.
     Triggers canonical write if applicable.

POST /api/ai/results/{result_id}/reject
     User rejects an AI result.
     No canonical write happens.

GET  /api/ai/results/recent
     UI listing of recent AI activity for the user.
```

### Internal endpoints (HMAC signed, called by n8n)

```text
GET  /api/internal/ai/tasks/{task_id}/context
     n8n fetches input + relevant data for Qwen.

POST /api/internal/ai/tasks/{task_id}/result
     n8n callback to store the model output.
     Headers: X-Timestamp, X-Signature, Idempotency-Key
```

---

## 8. Per-Feature AI Endpoints

Some features have their own endpoint surface that internally creates AI tasks:

```text
WR interactive (doc 32):
  POST /api/imperium/weekly-review/launch       (existing)
  POST /api/imperium/wr/sessions/{id}/messages
  POST /api/imperium/wr/sessions/{id}/validate
  GET  /api/imperium/wr/sessions/{id}
  GET  /api/imperium/wr/latest

Receipt scan (doc 31):
  POST /api/vault/receipts/scan

Medical analysis (doc 34):
  POST /api/pulse/medical-reports/analyze

Email triage (doc 31):
  Triggered internally by n8n email watcher
```

These domain-specific endpoints are wrappers that create the correct `ai_task` and may add domain-specific validation logic.

---

## 9. Qwen Routing Inputs

When n8n calls Qwen for routing, it provides:

```json
{
  "ai_task_id": "uuid",
  "task_type": "weekly_report.summary",
  "user_context_summary": "VTC driver, Île-de-France, ...",
  "input_payload": { ... },
  "static_overrides": {
    "requires_web": false,
    "requires_vision": false,
    "requires_audio": false,
    "is_medical": false,
    "force_model": null
  },
  "available_models": [
    "qwen-local",
    "sonnet-4.6",
    "opus-4.8",
    "gpt-5.5",
    "gemini"
  ]
}
```

Qwen returns:

```json
{
  "score_total": 142,
  "score_breakdown": {
    "complexity": 7,
    "context_size": 8,
    "ambiguity": 4,
    "consequences": 6,
    "speed_tolerance": 8,
    "sensitivity": 5,
    "cost_justification": 7
  },
  "selected_model": "opus-4.8",
  "reason": "Multi-domain weekly synthesis, deep reasoning needed",
  "confidence": 0.82,
  "needs_clarification": false,
  "fallback_model": "sonnet-4.6"
}
```

---

## 10. Static Overrides Bypass Qwen Scoring

Some tasks skip Qwen scoring entirely (per doc 30 §6):

```text
Vision (image present)         → Gemini
Audio                          → Whisper local
Web fresh data                 → GPT-5.5 + web
Medical reports                → GPT-5.5
WR re-planning                 → Fable 5
Backend deterministic          → no AI
```

These are encoded in the `task_type` registry on the backend.

---

## 11. User Validation Boundaries

The system distinguishes three reliability levels:

```text
LEVEL 1 - Raw facts:
  validated by direct user input (saisie manuelle)

LEVEL 2 - Enriched facts:
  validated through interactive AI dialogue (e.g. WR conversation)

LEVEL 3 - AI analysis:
  not directly validated, marked informational
```

The backend enforces user validation before any **canonical write** that creates or modifies a real-world action (mission, transaction, plan, etc.).

Pure analyses (WR, weekly insights) are stored without validation but flagged `requires_user_validation = false`.

---

## 12. Failure Modes And Recovery

### 12.1 n8n unreachable

```text
ai_task stays in status=queued
Backend retries webhook with exponential backoff (max 5 attempts)
After max retries, status=failed
User sees: "Service IA temporairement indisponible"
```

### 12.2 Qwen unavailable

```text
n8n falls back to Sonnet 4.6 for routing decisions
(more expensive but usable)
Logged as fallback event
User experience unchanged
Fallback is gated by token caps (see Section 12.6)
```

### 12.6 Token caps for fallback (mandatory)

When Qwen is unavailable and the system falls back to Sonnet 4.6 (or any cloud model used as substitute), three independent caps apply:

```text
Cap 1 — Per-task hard limit:
  max_tokens_per_call = 4000 (input + output combined)
  Prevents one runaway task from burning the budget

Cap 2 — Daily euro limit:
  daily_fallback_eur_limit = 5.00 EUR
  Tracked since 00:00 Europe/Paris
  Resets daily

Cap 3 — Daily token limit:
  daily_fallback_tokens_limit = 100000 tokens
  Tracked since 00:00 Europe/Paris
  Resets daily
```

### 12.7 Cap enforcement

```text
At 80% of any cap:
  → user notification: "Mode dégradé: 80% du budget IA utilisé"
  → log warning event

At 100% of any cap:
  → hard stop on cloud fallback
  → tasks queued or rejected with status=postponed
  → user notification: "Limite IA atteinte. Reprise demain à 00:00"
  → admin notification

At any time:
  → user can manually override the cap from Imperium settings
  → override is logged and audited
  → override resets at end of day
```

### 12.8 Cap recovery

```text
When Qwen comes back online:
  → routing returns to default (Qwen local)
  → caps stop being charged (only fallback usage counts)
  → daily counters keep their value (no reset)
```

### 12.3 Cloud model unavailable

```text
n8n uses fallback_model from Qwen routing decision
If fallback also fails, ai_task → status=failed
User notified via push
```

### 12.4 Stale callback

```text
Backend rejects callback if timestamp > 5 minutes old
n8n must retry with fresh timestamp
Prevents replay attacks
```

### 12.5 Idempotency conflict

```text
Same Idempotency-Key with different payload → 409 Conflict
Same Idempotency-Key with same payload → return cached response
```

---

## 13. Observability

Every AI call must produce:

```text
ai_task.created_at
ai_task.routing_model        (qwen-local)
ai_task.selected_model       (opus-4.8)
ai_result.input_tokens
ai_result.output_tokens
ai_result.estimated_cost_eur
ai_result.latency_ms
ai_result.confidence_score
ai_task.status_history       (via events)
```

Aggregated daily into dashboard:

```text
daily_total_cost_eur
daily_calls_per_model
daily_avg_latency
daily_failed_tasks
```

---

## 14. Privacy Boundaries

### 14.1 What stays local (never sent to cloud)

```text
Bank account numbers, card numbers
Government IDs
Detailed medical history (only summaries sent to GPT-5.5)
Personal voice recordings (Whisper local only)
Religious private practice details
```

### 14.2 What can go to cloud

```text
Aggregated weekly metrics
Anonymized event descriptions
Public information requests
General reasoning prompts
```

### 14.3 Redaction layer

Before any cloud call, the backend redacts:

- masks UUIDs that would leak
- replaces exact amounts with ranges when possible
- strips email addresses unless needed
- removes phone numbers

---

## 15. Implementation Order

```text
Step 1 — AI tables migrations
  ├─ ai_tasks (with all indexes)
  ├─ ai_results
  └─ ai_result_validations

Step 2 — Models + schemas + services
  ├─ services/ai/tasks.py
  ├─ services/ai/results.py
  └─ services/ai/validations.py

Step 3 — Public endpoints
  └─ /api/ai/* (5 endpoints)

Step 4 — Internal callbacks
  └─ /api/internal/ai/tasks/{id}/result

Step 5 — Mock n8n workflow
  └─ generic_ai_task_router with fake Qwen + fake model

Step 6 — Real Qwen via Ollama
  └─ Replace mock in n8n

Step 7 — First real cloud workflow
  └─ wr_interactive_analysis (depends on doc 32 implementation)

Step 8 — Other workflows progressively
  └─ vector, vault, pulse, imperium...
```

---

## 16. References

- `30_AI_ROUTING_AND_SCORING_POLICY.md` — routing rules and scoring formula
- `31_AI_TASKS_AND_RESULTS_CONTRACT.md` — tables, contracts, callbacks
- `32_WR_INTERACTIVE_WORKFLOW.md` — WR interactive flow
- `08_NON_NEGOTIABLE_RULES.md` — hard rules
- `15_SERVICE_ARCHITECTURE_MAP.md` — service evolution V1/V2/V3
- `09_PGVECTOR_MEMORY_POLICY.md` — vector memory rules

---

**Document version:** 1.0
**Status:** Architectural reference for AI layer
**Last updated:** 2026-04-28
