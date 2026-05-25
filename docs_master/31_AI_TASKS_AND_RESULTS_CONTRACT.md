# 31 - AI Tasks & Results Contract

## Patch 2A - Implemented Backend Foundation

Status: implemented as backend storage and callback contract only.

No Qwen, Claude, Opus, GPT, Gemini, n8n workflow, frontend, or business-domain automation is implemented in this patch.

### Tables Created

Patch 2A creates:

- `ai_tasks`
- `ai_results`
- `ai_result_validations`

`ai_tasks` stores the requested AI work item and routing/preparation context.

`ai_results` stores model or workflow output as a proposal/candidate result. It is not canonical truth.

`ai_result_validations` stores explicit backend/user validation decisions.

### Endpoint Contract

Authenticated app/backend endpoints:

```http
POST /api/ai/tasks
GET /api/ai/tasks/{task_id}
POST /api/ai/tasks/{task_id}/mark-running
POST /api/ai/results/{result_id}/validate
POST /api/ai/results/{result_id}/reject
```

Internal callback endpoint for future n8n orchestration:

```http
POST /api/internal/ai/tasks/{task_id}/result
```

The internal callback uses HMAC-only security:

```http
X-Timestamp: <unix timestamp seconds>
X-Signature: <hmac sha256 over "{timestamp}.{raw_body}">
Idempotency-Key: <stable callback key>
Content-Type: application/json
```

The shared `INTERNAL_WEBHOOK_SECRET` is only the HMAC key. It must not be sent as a plaintext header.

### Result Callback Payload

```json
{
  "result_type": "weekly_review_candidate",
  "result_payload": {
    "summary": "Draft result awaiting validation"
  },
  "model_used": "future-qwen-or-opus",
  "provider": "future-provider",
  "confidence": 0.82,
  "raw_payload": {}
}
```

Successful callback response:

```json
{
  "status": "ok",
  "task_id": "uuid",
  "result_id": "uuid",
  "result_status": "pending_validation",
  "idempotency_key": "same-key"
}
```

### Idempotency Behavior

`POST /api/internal/ai/tasks/{task_id}/result` is idempotent by `(task_id, Idempotency-Key)`.

Replay with the same payload returns the existing result.

Replay with the same key and a different payload returns conflict.

### Canonical Safety Rule

AI output never becomes a mission, transaction, weekly report, priority rule, memory, or other canonical action automatically.

The result remains `pending_validation` until explicitly accepted, rejected, or edited through backend-owned validation endpoints.

### Future Roles

Qwen role: future local router/preparer. Not implemented in Patch 2A.

Claude/Opus/GPT role: future heavy reasoning providers selected by routing policy. Not implemented in Patch 2A.

Gemini role: future image/OCR provider selected by routing policy. Not implemented in Patch 2A.

n8n role: future orchestration only. n8n must call backend APIs and must not write directly to PostgreSQL.

---

## Patch 2B - WR Conversation Integration

Patch 2B adds the backend-owned Weekly Review conversation layer.

AI task/result integration remains proposal-based:

- launching a WR session may create an `ai_task` such as `weekly_report.interactive.start`;
- n8n is not called by the backend in Patch 2B;
- future n8n workflows may return results through `POST /api/internal/ai/tasks/{task_id}/result`;
- WR-specific attachment may use `POST /api/internal/weekly-review/{session_id}/attach-ai-result`;
- attached AI results become WR messages or draft candidates only;
- no AI result becomes a canonical final report automatically;
- final WR approval remains an explicit user/backend action.

Supported future WR result types:

- `weekly_report.summary`
- `weekly_report.questions`
- `weekly_report.draft`
- `weekly_report.final`
- `weekly_report.revision`

Conversation ownership remains:

```text
User <-> App popup <-> Backend Imperium <-> Qwen later <-> Backend Imperium <-> App popup
```

n8n is reserved for heavy preparation or Opus orchestration later. It must not receive every WR user message.

---

## Patch 2C - Mock WR n8n Contract

Patch 2C prepares the future backend → n8n trigger contract without adding a real n8n workflow.

Backend launch behavior:

- `/api/imperium/weekly-review/launch` creates or opens the WR session;
- it creates an `ai_task` placeholder for `weekly_report.interactive.start` when needed;
- it stores the future n8n trigger payload in `ai_tasks.prepared_payload`;
- it does not call n8n, Qwen, Opus, GPT, Claude, Gemini, or any external AI.

Prepared WR trigger payload:

```json
{
  "task_id": "uuid",
  "session_id": "uuid",
  "task_type": "weekly_report.interactive.start",
  "week_start": "YYYY-MM-DD",
  "week_end": "YYYY-MM-DD",
  "callback_url": "/api/internal/ai/tasks/{task_id}/result",
  "wr_attach_url": "/api/internal/weekly-review/{session_id}/attach-ai-result"
}
```

Backend outbound n8n signing shell:

- can build HMAC-signed backend → n8n webhook requests;
- uses `N8N_BASE_URL`, `N8N_WEBHOOK_SECRET`, `N8N_REQUEST_TIMEOUT_SECONDS`, and `N8N_DRY_RUN`;
- defaults to dry-run behavior;
- refuses unsigned outbound requests when `N8N_DRY_RUN=false`;
- does not break app startup when n8n is not configured;
- never touches `n8n_db`.

Mock WR smoke endpoint:

```http
POST /api/internal/weekly-review/{session_id}/mock-ai-summary
```

This endpoint is for local/dev smoke testing only. It creates or reuses a mock `ai_result` with `result_type = weekly_report.summary`, attaches it to the WR session, and keeps it as a proposal/message. It does not approve a final report, write memory, or create canonical WR truth.

---

## Patch 2D - Mock Workflow Export

Patch 2D adds the first importable n8n workflow artifact:

```text
ops/n8n/workflows/wr_interactive_start_mock.json
```

Workflow:

```text
IMPERIUM_WR_INTERACTIVE_START_MOCK
```

This workflow consumes the backend-prepared `weekly_report.interactive.start` payload and performs the same contract flow future real n8n orchestration will use:

```text
prepared_payload
  -> n8n mock summary creation
  -> POST /api/internal/ai/tasks/{task_id}/result
  -> POST /api/internal/weekly-review/{session_id}/attach-ai-result
  -> backend stores pending proposal/message
```

It is still mock-only:

- no Qwen call;
- no Opus call;
- no GPT, Claude, Gemini, or external AI call;
- no direct PostgreSQL write;
- no `n8n_db` access except normal n8n internal execution storage;
- no final report approval;
- no pgvector memory write.

Required n8n environment variables:

```text
IMPERIUM_API_BASE_URL
INTERNAL_WEBHOOK_SECRET
```

Both backend callbacks use HMAC-only headers:

```http
X-Timestamp
X-Signature
Idempotency-Key
Content-Type: application/json
```

No plaintext shared secret header is sent.

---

## Patch 2E - Qwen Local Adapter Foundation

Patch 2E adds the backend-side local Qwen adapter contract.

Status: implemented as a safe adapter foundation only.

No Opus, GPT, Claude, Gemini, frontend, n8n AI Agent, or real n8n workflow wiring is added by this patch.

### Qwen role

Qwen 2.5 7B Instruct is the V1 local router/scorer/classifier/preparer.

Qwen may:

- classify task type;
- score task difficulty from 0 to 200;
- prepare structured prompts for stronger models;
- generate short structured weekly summaries;
- ask clarification questions;
- return routing metadata.

Qwen must not:

- write directly to PostgreSQL;
- create canonical missions, Vault transactions, memories, final WR reports, or priority rules;
- bypass backend validation;
- become the n8n AI Agent;
- replace the backend as source of truth.

### Backend config

Optional settings:

```text
QWEN_ENABLED=false
QWEN_BASE_URL=
QWEN_MODEL=qwen2.5:7b-instruct
QWEN_REQUEST_TIMEOUT_SECONDS=60
QWEN_DRY_RUN=true
```

Dry-run is the default. Missing Qwen configuration does not break backend startup.

### Structured output contracts

The adapter returns typed Pydantic contracts:

- `QwenScoreBreakdown`
- `QwenRoutingDecision`
- `QwenWeeklySummary`

All Qwen outputs are JSON-compatible proposals or routing metadata. They are not canonical business actions.

### Smoke endpoint

Authenticated smoke endpoint:

```http
POST /api/ai/qwen/smoke
```

Payload:

```json
{
  "task_type": "weekly_report.summary",
  "input_payload": {},
  "mode": "weekly_summary"
}
```

This endpoint performs no database write. It is only a local adapter contract smoke test.

### Real-call behavior

When `QWEN_ENABLED=true` and `QWEN_DRY_RUN=false`, the adapter can call an Ollama-compatible local endpoint:

```http
POST {QWEN_BASE_URL}/api/generate
```

The adapter asks for strict JSON. Invalid JSON, timeout, or HTTP failure raises a provider error. No provider error becomes canonical data.

---

## Patch 2F - n8n Qwen Dry-Run Workflow

Patch 2F adds a second importable n8n workflow artifact:

```text
ops/n8n/workflows/wr_interactive_start_qwen_dry_run.json
```

Workflow:

```text
IMPERIUM_WR_INTERACTIVE_START_QWEN_DRY_RUN
```

This workflow proves the contract chain:

```text
WR prepared_payload
  -> n8n webhook
  -> backend internal Qwen dry-run bridge
  -> n8n converts Qwen output into AIResultCallback
  -> POST /api/internal/ai/tasks/{task_id}/result
  -> POST /api/internal/weekly-review/{session_id}/attach-ai-result
  -> backend stores pending proposal/message
```

Internal bridge endpoint:

```http
POST /api/internal/ai/qwen/smoke
```

This endpoint:

- uses HMAC-only internal webhook verification;
- requires `Idempotency-Key`;
- allows only `task_type = weekly_report.summary` and `mode = weekly_summary`;
- performs no DB write;
- creates no canonical WR final report;
- writes no pgvector memory;
- returns a structured `QwenWeeklySummary`.

Required n8n environment variables:

```text
IMPERIUM_API_BASE_URL
INTERNAL_WEBHOOK_SECRET
```

Patch 2F still does not call a real local model from n8n. n8n must not call any local model endpoint directly in this workflow. It calls the backend bridge only.

Expected backend result:

- `ai_result.status = pending_validation`;
- WR receives a proposal/message;
- final report is not approved;
- no memory is written.

### Patch 2G stabilization

Patch 2G stabilizes the Qwen dry-run n8n workflow and WR attach behavior after VPS smoke testing.

Changes:

- `wr_interactive_start_qwen_dry_run.json` includes a stable top-level workflow `id` for n8n `2.14.2` import;
- n8n Code nodes use `$env.INTERNAL_WEBHOOK_SECRET` and `$env.IMPERIUM_API_BASE_URL`;
- `process.env` is forbidden in this workflow;
- Code nodes normalize HTTP Request output whether it is direct JSON, `{ body: ... }`, or `{ data: ... }`;
- Code nodes avoid stringifying raw HTTP responses in errors;
- WR attach is idempotent when the same `ai_result_id` is attached again;
- WR attach rejects replacing an existing initial summary with a different `ai_result_id`.

The result remains only a pending proposal. No canonical final report or memory is created.

---

## Patch 2H - Backend Outbound WR n8n Trigger

Patch 2H wires WR launch to optionally trigger the stable Qwen dry-run n8n workflow.

When `/api/imperium/weekly-review/launch` creates a fresh `ai_task` for:

```text
weekly_report.interactive.start
```

the backend stores `ai_tasks.prepared_payload` and may POST that payload to n8n.

Settings:

```text
N8N_BASE_URL=<optional, e.g. http://imperium-n8n:5678/webhook/>
N8N_WEBHOOK_SECRET=<required when N8N_DRY_RUN=false>
N8N_REQUEST_TIMEOUT_SECONDS=10
N8N_DRY_RUN=true
WR_N8N_QWEN_DRY_RUN_WEBHOOK_PATH=imperium/wr/interactive-start-qwen-dry-run
```

Behavior:

- if `N8N_DRY_RUN=true`, backend does not call n8n;
- if `N8N_DRY_RUN=false`, backend requires both `N8N_BASE_URL` and `N8N_WEBHOOK_SECRET`;
- if `N8N_DRY_RUN=false` and both settings are configured, backend signs and POSTs `prepared_payload`;
- if `N8N_DRY_RUN=false` but either setting is missing, backend refuses the outbound call and records `ai_task.error_code = n8n_not_configured`;
- outbound idempotency key is stable: `wr_n8n_trigger_{task_id}`;
- idempotent launch replay does not trigger n8n again;
- reopening an existing WR session with an existing task does not trigger n8n again;
- n8n failure does not fail the WR launch or mark the WR session failed;
- if the outbound trigger fails, the backend records `ai_task.error_code = n8n_trigger_failed`.

### Patch 2L - Signed Outbound n8n Boundary

Patch 2L closes the unsigned outbound webhook gap.

Production rule:

- backend → n8n webhook calls are always HMAC-signed;
- `N8N_WEBHOOK_SECRET` is mandatory whenever `N8N_DRY_RUN=false`;
- `N8N_BASE_URL` alone is not enough to enable outbound n8n;
- missing outbound signing configuration must not send an HTTP request;
- WR session and `ai_task` creation still succeed if n8n is not configured, and the task records `n8n_not_configured`.

Signed outbound headers:

```http
X-Timestamp: <unix timestamp seconds>
X-Signature: <hmac sha256 over "{timestamp}.{raw_body}">
Idempotency-Key: wr_n8n_trigger_{task_id}
Content-Type: application/json
```

n8n still writes no canonical data. It must return results through:

```text
POST /api/internal/ai/tasks/{task_id}/result
POST /api/internal/weekly-review/{session_id}/attach-ai-result
```

No final WR approval or pgvector memory write happens automatically.

---

## Patch 2I - WR Conversation Read Snapshot

Patch 2I adds a read-only authenticated endpoint for the future Imperium popup:

```http
GET /api/imperium/weekly-review/{session_id}/conversation
```

The endpoint returns the backend-owned WR conversation state in one response:

- session;
- messages ordered oldest to newest;
- linked `current_ai_task`;
- linked `initial_ai_result` and `final_ai_result`;
- latest draft/final reports;
- UI-safe flags for answering, revision, approval, waiting state, and whether summaries/drafts exist.

This is a read model only. It does not create AI tasks, call n8n, call Qwen, approve final reports, write memory, or make AI output canonical.

Patch 2M safety rule: this popup read model returns slim AI result summaries only. `AIResult.raw_payload` remains stored internally for audit/debug, but it is intentionally excluded from `initial_ai_result` and `final_ai_result` in the conversation response.

Patch 2N bounds the same endpoint for stable frontend reads:

```http
GET /api/imperium/weekly-review/{session_id}/conversation?messages_limit=200&messages_before=<datetime>&final_reports_limit=5
```

Limits:

- `messages_limit`: default `200`, minimum `1`, maximum `500`;
- `messages_before`: optional timestamp cursor; only messages created before this timestamp are returned;
- messages are returned oldest-to-newest after filtering and limiting;
- `final_reports_limit`: default `5`, minimum `1`, maximum `20`;
- final report candidates are selected newest-first.

This remains a read model only. It does not call n8n, Qwen, Opus, GPT, Claude, Gemini, modify WR state, expose `raw_payload`, write pgvector memory, or approve final reports.

---

## Patch 2J - WR Answer Integration Task

Patch 2J adds task preparation to the existing WR answer endpoint:

```http
POST /api/imperium/weekly-review/{session_id}/answer
```

On a fresh idempotent write, the backend stores the user answer and creates a queued AI task:

```text
task_type = weekly_report.answers.integrate
source_module = imperium
```

The task is created only by the backend after the authenticated user message is accepted. n8n does not receive every popup message directly.

The task `input_payload` and `prepared_payload` include:

- `task_id`;
- `session_id`;
- `task_type`;
- `source = app`;
- `trigger_type = user_message`;
- `source_ref_type = weekly_review_session`;
- `source_ref_id`;
- `week_start`;
- `week_end`;
- `latest_user_answer_message_id`;
- `latest_initial_ai_result_id`;
- `callback_url`;
- `wr_attach_url`.

This prepares a future workflow where n8n may integrate answers and return a proposal through:

```http
POST /api/internal/ai/tasks/{task_id}/result
POST /api/internal/weekly-review/{session_id}/attach-ai-result
```

Patch 2J does not auto-trigger n8n for this task, does not call Qwen/Opus/GPT/Claude/Gemini, does not create a final report, and does not write pgvector memory.

Patch 2M safety rule: creating a `weekly_report.answers.integrate` task must not overwrite an existing `session.current_ai_task_id`. If a launch task such as `weekly_report.interactive.start` is still in flight, the answer integration task is still created and prepared, but the existing pointer remains unchanged. If `current_ai_task_id` is empty, the new answer integration task may become the current pointer.

---

## Patch 2O - Answer Integration n8n Trigger

Patch 2O lets the backend optionally trigger n8n after a fresh `weekly_report.answers.integrate` task is created.

Configuration:

```text
WR_N8N_ANSWERS_INTEGRATE_WEBHOOK_PATH=imperium/wr/answers-integrate-qwen-dry-run
N8N_DRY_RUN=true
N8N_BASE_URL=<required only when N8N_DRY_RUN=false>
N8N_WEBHOOK_SECRET=<required only when N8N_DRY_RUN=false>
```

Trigger rules:

- `N8N_DRY_RUN=true`: the backend creates the user message and AI task, but does not call n8n;
- `N8N_DRY_RUN=false` with signed outbound n8n configured: backend POSTs the task `prepared_payload`;
- missing n8n config does not fail the user answer; the AI task records `n8n_not_configured`;
- n8n request failure does not roll back the user answer or task; the AI task records `n8n_trigger_failed`;
- idempotent replay of the answer does not create a duplicate message, duplicate task, or duplicate n8n trigger.

Outbound idempotency key:

```text
wr_n8n_answers_integrate_{task_id}
```

Prepared payload contains no secrets, JWTs, DB credentials, or `AIResult.raw_payload`. It includes:

- `task_id`;
- `session_id`;
- `task_type = weekly_report.answers.integrate`;
- `week_start`;
- `week_end`;
- `user_message_id`;
- `user_answer`;
- `callback_url`;
- `wr_attach_url`;
- `source = backend_wr_answer`.

n8n workflow artifact:

```text
ops/n8n/workflows/wr_answers_integrate_qwen_dry_run.json
```

Workflow name:

```text
IMPERIUM_WR_ANSWERS_INTEGRATE_QWEN_DRY_RUN
```

The workflow is dry-run only. It returns `weekly_report.draft` through the official backend AI result callback, then attaches that result to the WR session as a draft proposal. It does not approve the final report, write memory, call real models, use n8n AI Agent, or write directly to PostgreSQL.

---

## Patch 2P-2T - WR Frontend, Draft Actions, And Debug Contract

Frontend popup read endpoints:

```http
GET /api/imperium/weekly-review/current
GET /api/imperium/weekly-review/{session_id}/conversation
GET /api/imperium/weekly-review/{session_id}/debug-status
```

`/current` returns the latest authenticated-user WR session, or a requested `week_start` session when provided. If none exists, it returns:

```json
{
  "session": null,
  "conversation": null
}
```

The conversation snapshot is read-only and frontend-safe. It includes:

- `session`;
- messages ordered oldest-to-newest;
- slim `initial_ai_result` and `final_ai_result` summaries without `raw_payload`;
- bounded `final_report_candidates`, newest-first;
- slim `current_ai_task`;
- deterministic `ui_state`;
- conservative `allowed_actions`.

Read limits:

```text
messages_limit: default 200, max 500
messages_before: optional timestamp cursor
final_reports_limit: default 5, max 20
```

`ui_state` values are deterministic UI hints only:

```text
not_started
preparing_initial_summary
initial_summary_ready
waiting_for_user_answer
integrating_answers
draft_ready
approved
stored
failed
closed
```

`allowed_actions` is conservative:

- initial summary or user-answer state: `answer`;
- draft state: `approve_draft`, `reject_draft`, `request_changes`;
- approved state with an unstored approved report: `store_final_report`;
- integrating, stored, cancelled, closed, or failed states: no action.

Draft action endpoints:

```http
POST /api/imperium/weekly-review/{session_id}/draft/approve
POST /api/imperium/weekly-review/{session_id}/draft/reject
POST /api/imperium/weekly-review/{session_id}/draft/request-changes
POST /api/imperium/weekly-review/{session_id}/draft/store
```

All draft action POSTs require JWT ownership and `Idempotency-Key`.

Approval marks the latest draft candidate as `approved` and sets `approved_at`. It does not set `stored_at`, write pgvector memory, create canonical memory, or bypass the explicit user approval boundary.

Storage marks an already approved report as `stored` and sets `stored_at`. `approved != stored`: approval is the user decision, while stored is a backend V1 persistence marker. Stored does not write pgvector memory, create `ai_memories`, call n8n, call AI, create embeddings, or make any memory entry canonical. Memory/vector storage is reserved for a later explicit patch.

Reject uses the existing non-destructive `superseded` status and records rejection details in the report payload. No migration is required.

Request changes stores a user WR message and creates a queued `weekly_report.answers.integrate` AI task with a prepared n8n payload. If signed outbound n8n triggering is configured, it may trigger n8n through the existing backend-owned boundary. Replays do not duplicate messages, tasks, or n8n triggers.

Debug status is for VPS smoke tests and operational diagnosis. It may expose `raw_payload_keys`, but never the raw provider payload body or secrets.

---

## Patch 2U - Multi-Version WR Final Report Candidates

Patch 2U changes WR final report candidates from “one row forever” to historical multi-version candidates.

Database rule:

- superseded candidates remain as historical rows;
- active statuses are `draft`, `approved`, and `stored`;
- `superseded` is inactive and does not block a new revised candidate;
- a partial unique index allows only one active candidate per session;
- a partial unique index allows only one active candidate per user/week.

Indexes:

```text
uq_wr_final_reports_active_session
uq_wr_final_reports_active_user_week
```

Semantics:

- reattaching the same `source_ai_result_id` is idempotent and creates no duplicate message;
- attaching a different AI result while an active candidate exists returns conflict;
- rejecting or requesting changes supersedes the active draft first;
- after all existing candidates are `superseded`, a new `weekly_report.draft` or `weekly_report.final` result creates a new candidate row;
- old superseded rows are never deleted or overwritten.

Safety rules remain unchanged:

- no automatic approval;
- no `stored_at` on approval;
- no memory write;
- no pgvector write;
- no direct n8n DB write.

---

## Patch 2V-2Y - Approval, Store, UI, And Debug Hardening

Patch 2V hardens draft approval:

- only the latest active draft can be approved;
- superseded drafts cannot be approved;
- replay with the same `Idempotency-Key` returns the original response and does not update `approved_at`;
- approval sets session status to `approved` and `completed_at`;
- approval does not set `stored_at`, write pgvector, or write `ai_memories`.

Patch 2W adds explicit storage preparation:

```http
POST /api/imperium/weekly-review/{session_id}/draft/store
```

This endpoint is JWT-protected and idempotent. It is allowed only after approval. It sets the active report to `stored`, sets `stored_at`, and moves the session to `stored`. It is not a memory write and is not a vector write.

Patch 2X updates the frontend read model:

- `ui_state` includes `not_started`, `approved`, `stored`, and `closed`;
- `allowed_actions` exposes `store_final_report` only for an approved report with no `stored_at`;
- conversation reads still exclude `AIResult.raw_payload`;
- the `/current` endpoint returns the same safe conversation contract.

Patch 2Y expands debug status for smoke tests:

- active final report id/status;
- active and historical candidate counts;
- latest user/revision message ids;
- latest answer integration task id.

Debug may expose `raw_payload_keys`, never raw provider payload bodies. n8n remains orchestration only, and no endpoint performs automatic final approval or automatic final storage.

---

## Patch 4A-4D - Weekly Review Finalization Reads

Patch 4A-4D adds read/export surfaces for finalized WR data. These are backend-owned read endpoints only:

```http
GET /api/imperium/weekly-review/history
GET /api/imperium/weekly-review/{session_id}/final-report
GET /api/imperium/weekly-review/{session_id}/final-report/markdown
```

History is paginated with `limit`, `offset`, optional `status`, and `stored_only`. It returns a list object, never a raw array.

Final report selection uses this priority:

```text
stored > approved > draft > superseded
```

Markdown export returns the stored markdown when present, otherwise generates markdown from sanitized `report_payload` metadata.

Contract boundaries:

- JWT ownership is required for every read;
- foreign sessions return 404;
- no `AIResult.raw_payload` is exposed;
- markdown export is read-only;
- `stored` sessions reject further draft mutations except idempotent replay of the original store request;
- storing a WR final report still does not write memory, pgvector, embeddings, n8n, or AI outputs.

---

## Patch 2N - WR Cleanup and Bounded Reads

Patch 2N adds bounded WR conversation reads and cleans up dev/mock idempotency.

Mock summary endpoint:

```http
POST /api/internal/weekly-review/{session_id}/mock-ai-summary
```

The endpoint is still dev/mock only. It now derives stable sub-idempotency keys from the original request key:

```text
{original_key}:ai-result
{original_key}:wr-attach
```

This prevents the generic AI result write and the WR attach write from sharing the same idempotency namespace while keeping replay behavior safe. Replaying the same original key must not duplicate the `ai_result` or the WR message.

Internal HMAC callbacks continue to reject stale timestamps. Requests signed correctly but older than the configured tolerance return `401` with stale timestamp handling.

Canonical safety rules are unchanged: AI results remain proposals, n8n writes only through backend callbacks, no pgvector memory is written, and final WR approval remains explicit.

---

## Patch 2K - Weekly Report Draft/Final Proposal Rules

Patch 2K defines backend behavior for AI results with:

```text
weekly_report.draft
weekly_report.final
```

These result types are proposals only.

When attached through:

```http
POST /api/internal/weekly-review/{session_id}/attach-ai-result
```

the backend may create or link an `imperium_weekly_review_final_reports` row, but the row stays:

```text
status = draft
```

Rules:

- `weekly_report.draft` creates a draft candidate and moves the session to `draft_ready`;
- `weekly_report.final` creates a final candidate and moves the session to `final_ready`;
- `source_ai_result_id` links the candidate to the AI result;
- same-result reattach is safe and must not duplicate messages;
- different-result replacement is rejected until an explicit revision/superseding flow exists;
- `approved` and `stored` are never set by internal attach;
- pgvector memory is never written by internal attach.

Canonical approval remains separate:

```http
POST /api/imperium/weekly-review/{session_id}/approve
```

No n8n workflow may bypass this approval endpoint.

---

## 1. Document Purpose

This document defines the official contract between the Imperium app, the backend, n8n, Qwen, and external AI models.

Central rule:

> Every AI action must be typed, traceable, validated, idempotent, and stored only through the backend.

This document removes any confusion between:

- the canonical backend
- n8n
- Qwen (local router)
- GPT / Claude / Gemini / other models
- pgvector semantic memory
- user-facing actions

---

## 2. Non-Negotiable Rules

### 2.1 The backend is the only canonical writer

No AI model, no n8n workflow, no external service, and no frontend may write directly to the canonical database.

Allowed path:

```text
App / n8n / webhook
  → Imperium Backend API
  → validation
  → PostgreSQL imperium_core
  → append-only events when relevant
```

Forbidden paths:

```text
n8n → DB direct
AI → DB direct
frontend → DB direct
external workflow → DB direct
```

Rule:

> n8n orchestrates. Qwen routes. Models reason. The backend validates and writes.

### 2.2 User-triggered AI calls

No expensive AI cloud call (Haiku / Sonnet / Opus / GPT / Gemini) without explicit user action or a deterministic schedule the user has opted into.

Pattern:

```text
Suggest → Inform → User decides → Execute
```

Exceptions allowed without user action:

- Qwen local calls (free, fast, no impact)
- Vision OCR inside a flow the user explicitly initiated
- Pure deterministic backend calculations (no AI)

---

## 3. Component Responsibilities

### 3.1 Backend

The backend owns:

- authentication
- authorization
- input validation
- idempotency
- canonical writes
- append-only events
- AI task storage
- AI result storage
- final state transitions

The backend must not improvise complex AI decisions.

### 3.2 n8n

n8n is the orchestration engine.

n8n can:

- run scheduled workflows
- listen to webhooks
- watch external APIs
- receive emails
- call the backend
- call Qwen or external models per contract
- return results to the backend

n8n cannot:

- write directly to the Imperium canonical DB
- become the official decision brain
- replace Qwen
- decide a final business action alone
- silently modify canonical data

Rule:

> n8n is an orchestrator, not a decision intelligence.

### 3.3 n8n AI Agent (excluded in V1)

The n8n built-in AI Agent is **not part** of the official architecture for now.

Reasons:

- it would create a second decision layer
- it overlaps with Qwen
- it makes debugging harder
- it blurs responsibilities
- it risks producing decisions that diverge from the official AI policy

Official decision:

> The n8n AI Agent is excluded. Qwen handles routing, classification, adaptive questions, and triage.

### 3.4 Qwen 2.5 7B Instruct (local)

Qwen is the operational AI router.

Qwen can:

- classify tasks
- score difficulty (`/200`)
- decide whether a task can be processed locally
- decide whether a stronger model is needed
- prepare prompts
- ask adaptive clarification questions
- triage incoming signals
- produce structured decisions

Qwen cannot:

- write directly to the DB
- bypass the backend
- invent new business rules
- produce a final action without contract or validation

### 3.5 External models

Possible external models:

- GPT-5.5
- Claude Haiku 4.5
- Claude Sonnet 4.6
- Claude Opus 4.7
- Gemini (vision)
- Whisper / faster-whisper for audio
- future specialized models

They are used for:

- complex tasks
- long tasks
- sensitive tasks
- multimodal tasks
- high-impact-on-error tasks
- tasks beyond Qwen's threshold

They return structured results. The backend decides what is stored.

### 3.6 External model privacy rule

When a task is routed to an external cloud model such as GPT, Claude, Opus, Sonnet, Haiku or Gemini, the backend/Qwen context package must be minimized and anonymized before the cloud call.

External models receive a complete task summary, but not direct identity data. The package should remove or generalize:

- name, email, phone, exact address, account identifiers
- raw personal messages when a structured summary is enough
- unnecessary dates, locations, plates, invoices or document IDs
- any detail not required for the reasoning task

Medical or health-related tasks may still use GPT when required, but only through an anonymized medical summary plus the specific values needed for interpretation. GPT analyzes the data; it does not need to know who the user is.


---

## 4. AI Task Lifecycle

```text
1. Trigger
2. Task creation
3. Qwen classifies and scores
4. Router selects the model
5. Model produces a structured result
6. n8n returns the result to the backend
7. Backend validates the output contract
8. Backend stores the AI result
9. Optional: append-only event
10. Optional: user-facing display
11. Optional: user validation before any business action
```

---

## 5. Trigger Sources

### 5.1 App button

```text
User clicks "Start Weekly Report"
  → backend records the intent (creates ai_task)
  → backend notifies n8n (signed webhook)
  → n8n claims the task
  → Qwen prepares context
  → result returns to the backend
```

### 5.2 Time trigger

```text
Every Monday 03:00 Europe/Paris
  → n8n triggers events research within 30 km of Paris
  → Qwen filters useful events for Vector
  → strong model if needed (GPT-5.5 + web)
  → backend stores the result
```

### 5.3 DB update / backend event

```text
weekly_report.validated
  → backend POSTs to n8n internal webhook
  → n8n triggers downstream analysis if any
  → Qwen routes to Opus / GPT if necessary
  → backend stores the analysis
```

### 5.4 External API

```text
IDF Mobilités flags a problem on RER D
  → n8n captures the signal
  → Qwen evaluates VTC impact
  → backend stores a Vector signal
```

### 5.5 Email received

```text
Tax reminder email
  → n8n captures the email
  → Qwen triages urgency and domain
  → backend stores an item to handle
```

### 5.6 Media webhook

```text
Receipt photo / uploaded audio
  → backend or n8n receives the file
  → OCR / STT workflow
  → result returned to backend
```

---

## 6. Where AI Results Are Stored

AI results live in `imperium_core`, written by the backend.

A separate database for n8n is **not** acceptable.

Reasons:

- single source of truth
- simpler backups
- simpler audit
- easy joins with user, missions, Vault, Vector, Pulse, Path
- no split-brain architecture

n8n keeps its own internal database only for its own workflow executions.

Rule:

> n8n logs belong to n8n. Imperium intelligent results belong to Imperium.

---

## 7. AI Tables

### 7.1 ai_tasks

Stores every AI request.

Recommended fields:

```text
id                        UUID PK
user_id                   UUID FK
task_type                 VARCHAR(64) (e.g. weekly_report.interactive.start)
source                    VARCHAR(32) (app|cron|webhook|backend|external)
source_ref_type           VARCHAR(64) NULL
source_ref_id             UUID NULL
trigger_type              VARCHAR(32) (button|schedule|db_event|external|email|media)
status                    VARCHAR(32) (see statuses below)
difficulty_score          INTEGER NULL  (computed by Qwen, 0..200)
score_breakdown           JSONB NULL    (per-criterion scores)
routing_model             VARCHAR(64)   (e.g. qwen-2.5-7b)
selected_model            VARCHAR(64)   (e.g. opus-4.7)
fallback_model            VARCHAR(64) NULL
requires_user_validation  BOOLEAN NOT NULL DEFAULT FALSE
idempotency_key           VARCHAR(128) NOT NULL
input_payload             JSONB NULL
input_payload_hash        VARCHAR(64) NULL
created_at                TIMESTAMPTZ NOT NULL DEFAULT now()
started_at                TIMESTAMPTZ NULL
completed_at              TIMESTAMPTZ NULL
failed_at                 TIMESTAMPTZ NULL
error_code                VARCHAR(64) NULL
error_message             TEXT NULL
```

Recommended statuses:

```text
queued
routing
waiting_for_user_clarification
waiting_for_user_validation
running
completed
failed
cancelled
expired
```

Clarification means the model needs more information from the user before it can continue. Validation means the model produced a result and is waiting for explicit user approval.

Indexes:

```text
(user_id, status)
(user_id, task_type, created_at DESC)
UNIQUE (user_id, idempotency_key)
```

### 7.2 ai_results

Stores AI outputs.

Recommended fields:

```text
id                         UUID PK
user_id                    UUID FK
ai_task_id                 UUID FK → ai_tasks(id)
result_type                VARCHAR(64) (e.g. weekly_report.draft, weekly_report.message)
model_used                 VARCHAR(64)
model_provider             VARCHAR(32) (anthropic|openai|google|local)
model_version              VARCHAR(64) NULL
input_hash                 VARCHAR(64) NULL
output_hash                VARCHAR(64) NULL
confidence_score           NUMERIC(4,3) NULL  (0.000 to 1.000)
risk_score                 NUMERIC(4,3) NULL  (0.000 to 1.000)
requires_user_validation   BOOLEAN NOT NULL DEFAULT FALSE
validation_status          VARCHAR(32) NOT NULL DEFAULT 'not_required'
validated_by_user_at       TIMESTAMPTZ NULL
result_json                JSONB NOT NULL
summary_text               TEXT NULL
metadata                   JSONB NULL
input_tokens               INTEGER NULL
output_tokens              INTEGER NULL
estimated_cost_eur         NUMERIC(10,4) NULL
latency_ms                 INTEGER NULL
created_at                 TIMESTAMPTZ NOT NULL DEFAULT now()
```

Validation statuses:

```text
not_required
pending_user_validation
accepted
rejected
superseded
expired
```

Rule:

> An AI result is not automatically a business action.

Indexes:

```text
(user_id, ai_task_id, created_at)
(user_id, result_type, created_at DESC)
(user_id, validation_status) WHERE validation_status != 'not_required'
```

### 7.3 ai_result_validations

Stores explicit user decisions on AI results.

Recommended fields:

```text
id                  UUID PK
user_id             UUID FK
ai_result_id        UUID FK → ai_results(id)
validation_status   VARCHAR(32)  (accepted|rejected|deferred)
user_decision       VARCHAR(32) NULL
user_comment        TEXT NULL
idempotency_key     VARCHAR(128) NOT NULL
created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
```

Indexes:

```text
(user_id, ai_result_id, created_at)
UNIQUE (user_id, idempotency_key)
```

---

## 8. Official V1 AI Task Types

```text
weekly_report.interactive.start
weekly_report.summary
weekly_report.questions
weekly_report.answers.integrate
weekly_report.final
weekly_report.revision

vector.event_scan
vector.rail_disruption_triage
vector.zone_recommendation

vault.receipt_extract
vault.weekly_finance_analysis

pulse.meal_suggestion
pulse.training_adjustment
pulse.medical_report.analyze

imperium.email_triage
imperium.daily_plan_assist
imperium.mission_recommendation
imperium.priority_review
imperium.memory_candidate_extract

media.audio_transcription
media.image_ocr

system.health_review
```

This list is static on the backend side.

A new task type requires:

- input contract
- output contract
- storage target
- validation rule
- routing rule
- tests

---

## 9. Weekly Report Analysis (concrete reference case)

Short name: `WR analysis`

Task type chain (full interactive flow defined in doc 32):

```text
weekly_report.interactive.start
weekly_report.summary
weekly_report.questions
weekly_report.answers.integrate
weekly_report.final
weekly_report.revision
```

Trigger:

```text
User clicks "Start Weekly Report" in the app
  OR
weekly_report.finished event (deterministic source)
```

Flow:

```text
User starts the WR
  → backend creates ai_task(weekly_report.interactive.start)
  → backend POSTs signed webhook to n8n
  → n8n claims the task
  → Qwen routes
  → Opus generates summary / questions / draft
  → n8n callback to backend with structured result
  → backend stores ai_result(weekly_report.summary | questions | draft)
  → user converses inside the popup (each turn = one ai_task + ai_result)
  → on validation, backend creates canonical weekly_reports row
```

Storage:

- working data → `ai_results` (result_type prefixed by `weekly_report.*`)
- canonical → `weekly_reports` (defined in doc 32)
- semantic memory → `pgvector_memory` (extracted at validation)

---

## 10. Vector Event Scan (reference case)

Task type:

```text
vector.event_scan
```

Trigger:

```text
n8n cron Monday 03:00 Europe/Paris
```

The Vector weekly scan is scheduled Monday 03:00 Europe/Paris to prepare the operational week before morning driving decisions.

Examples extracted:

- sport events
- shows
- concerts
- RER disruptions
- road disruptions
- night closures
- VTC opportunities

Storage:

```text
ai_tasks
ai_results
future vector_intelligence_signals
```

User validation:

```text
not required for passive signal
required before official plan change unless an explicit rule says otherwise
```

---

## 11. Vault Receipt Extraction (reference case)

Task type:

```text
vault.receipt_extract
```

Flow:

```text
User takes receipt photo
  → App sends image to backend
  → Backend creates MediaItem / ai_task(vault.receipt_extract)
  → Backend triggers n8n or exposes the task for n8n
  → n8n calls Gemini OCR
  → Gemini extracts text and possible fields
  → n8n calls Qwen
  → Qwen classifies the data
  → n8n returns result to backend via HMAC callback
  → Backend stores ai_result as pending_validation
  → Backend pre-fills the "add expense" popup
  → User validates, edits, or cancels
  → Backend creates canonical vault_transactions row only after validation
```

User validation:

```text
required before any real transaction is created
```

---

## 12. Email Triage (reference case)

Task type:

```text
imperium.email_triage
```

Flow:

```text
Email received
  → n8n captures
  → Qwen classifies
  → strong model on sensitive subject
  → backend stores the analysis
```

User validation required for:

- replying
- sending
- paying
- archiving important data
- creating a commitment
- creating a mission

---

## 13. Daily Plan Assist (reference case)

Task type:

```text
imperium.daily_plan_assist
```

Storage:

```text
ai_tasks
ai_results
```

Possible canonical writes after user validation:

```text
imperium_daily_plans
imperium_path_items
imperium_missions
```

User validation:

```text
required before official plan creation
```

---

## 14. Mission Recommendation (reference case)

Task type:

```text
imperium.mission_recommendation
```

Possible canonical write after user validation:

```text
imperium_missions
```

User validation:

```text
required
```

---

## 15. Static And Dynamic Variables

The architecture is hybrid.

### 15.1 Static variables

Coded and documented:

- task_type
- source
- trigger_type
- allowed models
- forbidden models
- sensitivity level
- user-validation rule
- output_schema
- storage target
- routing overrides

### 15.2 Dynamic variables

Computed by Qwen at request time:

- real complexity
- ambiguity
- context size
- error risk
- urgency
- user fatigue
- operational pressure
- need for clarification
- model confidence
- need for a stronger model

Rule:

> The backend defines the playing field. Qwen plays within the playing field.

---

## 16. Difficulty Scoring

The official scoring formula is defined in doc 30 (`30_AI_ROUTING_AND_SCORING_POLICY.md`).

Total score over 200.

| Criterion | Note | Coefficient | Max |
|---|---:|---:|---:|
| Complexity | 0–10 | 5 | 50 |
| Context size | 0–10 | 3 | 30 |
| Clarity / ambiguity | 0–10 | 3 | 30 |
| Error consequences | 0–10 | 2 | 20 |
| Speed tolerance | 0–10 | 2 | 20 |
| Data sensitivity | 0–10 | 3 | 30 |
| Cost justification | 0–10 | 2 | 20 |

Total max:

```text
200
```

Special speed rule:

```text
0  = urgent / must be fast
10 = can be slow / no urgency
```

---

## 17. V1 Routing Thresholds

This is the **canonical V1 thresholds** (aligned with doc 30):

| Score `/200` | Recommended model | Role |
|---:|---|---|
| 0–59 | Qwen local | Execute locally |
| 60–99 | Haiku 4.5 | Lightweight cloud |
| 100–139 | Sonnet 4.6 | Balanced reasoning |
| 140–169 | Opus 4.7 | Deep analysis |
| 170–200 | Opus 4.7 + guard | Critical analysis, validation gate |

These thresholds are adjustable after observing costs and results, but only with explicit decision (not silently).

---

## 18. Routing Overrides

Some tasks bypass dynamic scoring entirely. Static rules win.

Examples:

```text
Medical report          → GPT-5.5 (preferred) or Opus
Legal analysis          → Opus or GPT-5.5
OCR receipt / photo     → Gemini
Audio transcription     → Whisper / faster-whisper
Sensitive financial/legal action → strong model + user validation
Web research            → GPT-5.5 + web
WR draft analysis       → Opus
Vector weekly events    → GPT-5.5 + web
```

Rule:

> A static override applies before dynamic scoring.

---

## 19. Standard AI Output Contract

Every model must return a structured JSON.

Minimum format:

```json
{
  "result_type": "string",
  "summary": "string",
  "confidence_score": 0.0,
  "risk_score": 0.0,
  "requires_user_validation": false,
  "recommended_next_action": "none",
  "structured_result": {},
  "warnings": [],
  "model_notes": []
}
```

Rules:

- `confidence_score` between 0 and 1
- `risk_score` between 0 and 1
- `requires_user_validation` is mandatory
- `structured_result` must respect the task's schema
- a free-text-only response is not canonical

Tasks define their own additional fields inside `structured_result`.

---

## 20. User Validation

Validation is required if the AI result wants to:

- create a mission
- modify a mission
- create a Vault transaction
- modify priorities
- send an email or message
- trigger a payment
- delete or archive important data
- change the daily plan
- store a sensitive memory
- create a real commitment

Validation is not required if the AI:

- summarizes
- classifies
- stores passive intelligence
- prepares a draft
- produces a non-binding analysis
- generates a read-only report

---

## 21. Idempotency

Every endpoint creating or storing an AI artifact requires `Idempotency-Key`.

This includes:

- AI task creation
- AI result storage
- n8n callback
- conversion of an AI result into a canonical action
- trigger from an app button

A repeated request must return the original response without creating a duplicate.

---

## 22. AI Append-Only Events

Recommended events:

```text
ai.task.created
ai.task.routed
ai.task.started
ai.task.completed
ai.task.failed
ai.result.stored
ai.result.validation.requested
ai.result.validation.accepted
ai.result.validation.rejected
```

Events provide an audit trail. They do not replace canonical tables.

---

## 23. n8n Callback To Backend

When n8n finishes an AI workflow, it calls the backend.

Recommended payload:

```json
{
  "ai_task_id": "uuid",
  "workflow_name": "string",
  "workflow_execution_id": "string",
  "model_used": "string",
  "model_provider": "string",
  "result_type": "string",
  "result_json": {},
  "summary_text": "string",
  "confidence_score": 0.0,
  "risk_score": 0.0,
  "requires_user_validation": false,
  "input_tokens": 0,
  "output_tokens": 0,
  "estimated_cost_eur": 0.0,
  "latency_ms": 0
}
```

Headers:

```text
X-Timestamp
X-Signature: sha256=<hmac-sha256(timestamp + "." + raw_body, internal_secret)>
Idempotency-Key
Content-Type: application/json
```

Backend validation steps:

- the task exists
- the task belongs to the right user
- the workflow is allowed
- the model is allowed
- the result respects the schema
- idempotency key is present
- no direct canonical mutation is requested

---

## 24. Storage Decision Table

| Task | AI result stored | Business state changed | Validation |
|---|---:|---:|---:|
| weekly_report.interactive.start | yes | no | no |
| weekly_report.final | yes | weekly_reports row on validation | yes |
| weekly_report.questions | yes | possible after WR validation | yes |
| vector.event_scan | yes | future passive signal | no |
| vector.zone_recommendation | yes | no | except plan change |
| vault.receipt_extract | yes | transaction after validation | yes |
| imperium.email_triage | yes | possible task / inbox | yes for action |
| imperium.daily_plan_assist | yes | plan / path after validation | yes |
| imperium.mission_recommendation | yes | mission after validation | yes |
| imperium.priority_review | yes | priorities after validation | yes |
| imperium.memory_candidate_extract | yes | memory after validation | yes |
| pulse.medical_report.analyze | yes | rules after validation | yes |
| media.audio_transcription | yes | follow-up task draft | depends |
| media.image_ocr | yes | follow-up task draft | depends |

---

## 25. Cost And Monitoring

Each AI result must allow tracking:

```text
provider
model
input_tokens
output_tokens
estimated_cost_eur
latency_ms
routing_reason
```

Goal:

> Qwen reduces costs by handling simple tasks locally and escalating only when justified.

---

## 26. Official V1 Decisions

```text
n8n AI Agent       : excluded
Qwen 2.5 7B        : official local router/scorer
n8n                : orchestrator only
backend            : sole canonical writer
imperium_core      : canonical storage
pgvector           : semantic memory / search, never source of truth
Routing thresholds : 0–59 / 60–99 / 100–139 / 140–169 / 170–200 (per doc 30)
```

---

## 27. Recommended Next Implementation Steps

### Step 1 — Backend AI tables

```text
ai_tasks
ai_results
ai_result_validations
```

### Step 2 — Minimum endpoints

```text
POST /api/ai/tasks                              (create task)
GET  /api/ai/tasks/{task_id}                    (read task)
POST /api/ai/tasks/{task_id}/result             (n8n callback storing ai_result)
GET  /api/ai/results/recent                     (UI listing recent results)
POST /api/ai/results/{result_id}/validate       (user validation accept/edit)
POST /api/ai/results/{result_id}/reject         (user validation reject)
```

All POST endpoints require `Idempotency-Key`. The n8n callback also requires HMAC + timestamp.

### Step 3 — First wired workflow

```text
weekly_report.interactive.start  (per doc 32)
```

Why this one first:

- high value
- low operational risk
- exercises the full chain n8n → Qwen → strong model → backend
- no dual-validation needed before storing the analysis itself
- enables clean cost / latency / quality measurement

### Step 4 — Wire Qwen local

Install Qwen via Ollama on the VPS (KVM 4: 16 GB RAM, suitable for Q5_K_M).

Replace mock Qwen calls in workflows with real local calls.

### Step 5 — Wire premium models

Add Haiku / Sonnet / Opus / GPT-5.5 / Gemini progressively.

Log every call with cost, latency, and routing reason.

### Step 6 — Wire Whisper local

Install faster-whisper alongside Qwen.

---

## 27A. Weekly Review Finalization Read Contract

Patch 4E-4H adds read/export surfaces for Weekly Review final reports without changing the AI proposal rules:

```http
GET /api/imperium/weekly-review/final-reports/{report_id}
GET /api/imperium/weekly-review/final-reports/stored?limit=20&offset=0
GET /api/imperium/weekly-review/{session_id}/final-report
GET /api/imperium/weekly-review/{session_id}/final-report/markdown
```

Contract rules:

- AI results remain proposals until explicit backend/user validation.
- Final report candidates may be `draft`, `approved`, `stored`, or `superseded`.
- `approved` is not the same as `stored`.
- `stored` is a backend V1 persistence marker only.
- Storing a report does not write pgvector, `ai_memories`, embeddings, or model memory.
- Stored report indexes use slim summaries and do not include full payloads, markdown bodies, memory candidates, or raw provider payloads.
- Full sanitized report reads are available by `session_id` or by `report_id`.
- Markdown export is read-only.
- Terminal WR sessions (`stored`, `cancelled`, `failed`) reject new mutations with 409, except idempotent replay of an already successful request.

n8n still only orchestrates callbacks. It never writes final reports directly and never approves or stores a Weekly Review.

---

## 27B. Weekly Review Memory Candidate Projection

Patch 4I-4L prepares memory projection candidates from stored Weekly Review final reports without storing them as canonical memory.

Read endpoints:

```http
GET /api/imperium/weekly-review/{session_id}/memory-candidates
GET /api/imperium/weekly-review/final-reports/{report_id}/memory-candidates
GET /api/imperium/weekly-review/memory-candidates/preview?limit=20&offset=0
```

Contract rules:

- endpoints require JWT and current-user ownership;
- memory candidates are proposals only;
- `storage_enabled` is always `false`;
- no memory is stored automatically;
- no `ai_memories` row is written;
- no pgvector or embedding write occurs;
- no n8n workflow is called;
- no real AI/model call is made;
- raw AI/provider payloads are never exposed.

Candidate source order:

1. `report_payload.memory_candidates`
2. `imperium_weekly_review_final_reports.memory_candidates`
3. deterministic fallback from summary, sections, and questions answered

Future patch requirement: explicit user approval must be added before any candidate can become canonical memory.

---

## 27C. Weekly Review Memory Candidate Decisions

Patch 4M-4P adds a decision table and backend endpoints for user decisions on WR memory projection candidates.

Table:

```text
imperium_memory_candidate_decisions
```

Stored fields include current user id, report id, session id, candidate id, decision, original candidate JSON, optional edited candidate JSON, reason, payload, idempotency key, and timestamps.

Decision values:

```text
approved
rejected
edited
```

Endpoints:

```http
POST /api/imperium/weekly-review/final-reports/{report_id}/memory-candidates/{candidate_id}/approve
POST /api/imperium/weekly-review/final-reports/{report_id}/memory-candidates/{candidate_id}/reject
POST /api/imperium/weekly-review/final-reports/{report_id}/memory-candidates/{candidate_id}/edit
GET /api/imperium/weekly-review/memory-candidates/decisions?limit=20&offset=0&decision=approved
```

Contract rules:

- all POSTs require JWT ownership and `Idempotency-Key`;
- the candidate must exist in the deterministic computed candidate set for the selected report;
- only `approved` and `stored` final reports can receive decisions;
- `draft` and `superseded` reports remain preview-only;
- one candidate can have only one decision row for a given user/report;
- idempotent replay returns the cached decision;
- same key with different body conflicts;
- different key for an already decided candidate conflicts.

Read models now merge decision metadata into candidate responses:

```text
decision_status
decision_id
decided_at
edited_candidate
effective_candidate
```

`include_rejected=false` is the preview default, so rejected candidates are hidden from the preview index unless explicitly requested.

Safety rules:

- approved and edited decisions are not long-term memory yet;
- no `ai_memories` row is written;
- no pgvector or embedding write occurs;
- no n8n workflow is called;
- no real AI/model call is made;
- raw AI/provider payloads are never exposed.

Future patch requirement: controlled memory materialization must explicitly turn approved or edited decisions into canonical memory.

---

## 27D. Weekly Review Memory Commit Readiness

Patch 4Q-4T adds a readiness and dry-run layer for future WR memory commits.

Read endpoints:

```http
GET /api/imperium/weekly-review/memory-candidates/commit-ready?limit=20&offset=0
GET /api/imperium/weekly-review/final-reports/{report_id}/memory-candidates/commit-ready
```

These are read models only. They return approved or edited candidate decisions for the authenticated user. Rejected decisions are not returned by commit-ready endpoints.

Readiness rules:

- `edited_candidate` becomes `effective_candidate` when present;
- otherwise `original_candidate` is the effective candidate;
- `readiness_status = ready` only when title, content, kind, confidence, and proposed memory scope are valid;
- blocked candidates include deterministic `readiness_reasons`.

Dry-run endpoint:

```http
POST /api/imperium/weekly-review/memory-candidates/commit-dry-run
```

The dry run requires JWT and `Idempotency-Key`. It accepts a list of decision ids and returns:

- requested count;
- eligible count;
- blocked count;
- would-commit count;
- ready candidates;
- blocked entries and reasons;
- `storage_enabled = false`;
- `Dry run only. Nothing has been written to memory.`

Safety rules:

- commit-ready is not memory storage;
- commit-dry-run is not memory storage;
- approved and edited candidate decisions are only proposals ready for a future memory commit;
- no `ai_memories` table write occurs;
- no pgvector or embedding write occurs;
- no n8n workflow is called;
- no real AI/model call is made.

Future patch requirement: a separate explicit user-approved materialization endpoint must perform any canonical memory write.

---

## 27E. Weekly Review Chatbot Flow Contract

Patch 5A-5D adds the backend contract for the chatbot-style Weekly Review popup.

Chat endpoints:

```http
POST /api/imperium/weekly-review/{session_id}/chat/messages
POST /api/imperium/weekly-review/{session_id}/chat/confirm-no-more-input
```

The frontend should use the actions returned by the conversation read model:

```text
send_message
confirm_no_more_input
approve_draft
request_changes
store_final_report
```

Contract:

- user chat turns are stored as WR messages in the backend;
- deterministic dry-run Qwen follow-ups are stored as proposal/chat messages only;
- final draft generation is gated by explicit `confirm_no_more_input`;
- draft approval and storage stay separate user actions;
- `request_changes` supersedes the active draft and resumes `conversation_active`;
- revised draft creation requires a later explicit confirmation.

No AI result from this flow is canonical by itself. Drafts remain proposals until approved. Stored reports do not write memory, pgvector, embeddings, or `ai_memories`.

Hidden chain-of-thought, raw model/provider payloads, internal prompts, and secrets must not be exposed through Weekly Review read schemas.

---

## 27F. Weekly Review UI Action and Anti-Corruption Contract

Patch 5E-5H enriches the Weekly Review conversation read model with stable UI metadata. The backend remains the authority for what the popup may do.

Read model additions:

```text
chat_timeline
visible_ai_state
latest_assistant_prompt
draft_review_state
primary_action
secondary_actions
```

`visible_ai_state` is a safe business summary of what the assistant is doing. It is not hidden reasoning, not an internal prompt, and not raw provider output.

Action descriptors expose endpoint hints for:

```http
POST /api/imperium/weekly-review/{session_id}/chat/messages
POST /api/imperium/weekly-review/{session_id}/chat/confirm-no-more-input
POST /api/imperium/weekly-review/{session_id}/draft/approve
POST /api/imperium/weekly-review/{session_id}/draft/request-changes
POST /api/imperium/weekly-review/{session_id}/draft/reject
POST /api/imperium/weekly-review/{session_id}/draft/store
```

Mutation guardrails:

- no final draft without user-provided input;
- no chat mutation on terminal sessions;
- no chat message while a draft is ready unless request-changes supersedes the draft first;
- no approval without an active draft;
- no storage without an approved report;
- request-changes can supersede an active draft or approved report and resumes the chat.

Patch 5I-5J clarifies the read-model action mapping:

- active mutable Weekly Review report candidates are only `draft` and `approved`;
- `stored` is terminal/display-only for the conversation read model;
- `superseded` is historical and never counts as an active draft;
- `draft_ready` plus an active `draft` exposes `approve_draft` as the primary action and `request_changes` as a secondary action;
- `approved` plus an active `approved` report exposes `store_final_report` as the primary action;
- `conversation_active` exposes only chat actions: `send_message` and `confirm_no_more_input`.

All mutation POSTs remain idempotent. AI outputs and dry-run drafts remain proposals until explicit user action.

---

## 27G. AI Memories Foundation and Commit V1

Patch 5K-5N defines the canonical text memory table:

```text
ai_memories
```

Patch 5O-5R adds the first explicit user-triggered commit path from approved or edited Weekly Review memory candidate decisions into `ai_memories`.

Rules:

- Weekly Review memory candidates remain proposals.
- The user must approve or edit candidates before commit.
- `POST /api/imperium/weekly-review/memory-candidates/commit` writes canonical text memories only for approved or edited decisions.
- Rejected, missing, foreign, or malformed decisions are blocked.
- Duplicate `source_decision_id` commits return the existing memory reference instead of creating duplicates.
- `ai_memories` has no pgvector column and no embedding column.
- No embeddings are generated in this patch.
- pgvector remains a future semantic index, not the canonical source.
- n8n must call backend APIs only and must never write memory rows directly.

Runtime surfaces:

```http
GET /api/imperium/memories/schema
GET /api/imperium/memories?limit=20&offset=0&status=active&kind=...&scope=...&q=...
GET /api/imperium/memories/{memory_id}
POST /api/imperium/memories/{memory_id}/archive
POST /api/imperium/memories/{memory_id}/supersede
POST /api/imperium/weekly-review/memory-candidates/commit
```

`GET /api/imperium/memories/schema` returns `storage_enabled=true`, `embeddings_enabled=false`, `pgvector_enabled=false`, and the available endpoint paths.

Patch 5S-5V adds explicit lifecycle controls for committed memories:

- memory index reads are JWT-scoped and active-only by default;
- filters support `status`, `kind`, `scope`, `source_module`, `source_type`, WR source ids, and a simple `ilike` text search over title/content;
- `status=all` is an explicit opt-in for non-active rows;
- archive is an idempotent status transition from `active` to `archived`;
- supersede is an idempotent user action that creates a new active memory row and marks the previous active row `superseded`;
- archived, superseded, or deleted memories cannot be archived or superseded again except through exact idempotent replay;
- memory rows are never physically deleted by these endpoints;
- lifecycle metadata is sanitized and must not contain raw provider payloads, hidden reasoning, internal prompts, or secrets;
- no vector search, embeddings, pgvector write, n8n AI Agent, n8n DB write, or automatic memory action is introduced.

---

## 28. Summary

```text
Every AI action is a typed task.
Every task produces a typed result.
Every result is either passive or requires user validation.
Every storage write goes through the backend.
Every external call goes through the routing layer.
Every routing decision is logged.
Every idempotency key is required.
Every model has its lane.
The user is always the final authority.
```

---

**Document version:** 2.0 (aligned with doc 30 thresholds and doc 32 WR flow)
**Status:** Official V1 reference
**Last updated:** 2026-04-28

## Audit Patch 1 Applied

The 2026-05-02 backend audit (Patch 1) tightened the AI ownership and result
schemas:

- **Ownership NOT NULL** — migration `20260503_0018_ai_user_id_not_null` makes
  `user_id` NOT NULL on `ai_tasks`, `ai_results`, and `ai_result_validations`.
  Existing orphaned rows (none in single-user mode, but possible from earlier
  bugs) are backfilled only when ownership can be resolved safely: either an
  explicit database setting `imperium.canonical_user_id` points to an existing
  user, or the database has exactly one user. If multiple users exist and no
  canonical user is configured, the migration fails instead of guessing. The
  ORM mappings (`Mapped[UUID]` on the three tables) match the DB constraint.
- **Public schema split** — `AIResultRead` no longer exposes `raw_payload`. A
  new sibling schema `AIResultInternalRead` retains `raw_payload` and is
  reserved for service-layer / debug-only use. No public route currently
  returns `AIResultInternalRead`. Treat `raw_payload` as internal-only.
- Single-user mode invariant: every AI task and result is owned by exactly
  one user; an unowned row cannot exist.

## Audit Closure Patch 6E-6H

Patch 6E-6H closes the remaining backend audit items before VPS deployment.

Security/read-model rules:

- public Weekly Review message creation is user-only;
- `WeeklyReviewMessageCreate.role` is locked to `user`;
- public message types are limited to user-originated message types:
  `user_answer`, `chat_message`, and `revision_request`;
- assistant/system/backend message roles (`qwen`, `opus`, `system`,
  `backend`) are backend-created only and use backend/internal schemas;
- debug/status surfaces must not expose raw provider payloads, provider/model
  identifiers, internal prompts, or raw payload keys in non-local
  environments;
- local/test environments may keep richer diagnostics for smoke testing;
- `events` and `auth_events` append-only triggers are covered by optional
  PostgreSQL tests for UPDATE, DELETE, and TRUNCATE rejection.

These changes do not add frontend behavior, AI calls, n8n workflows, memory
writes, pgvector writes, or embeddings.

## Patch 6I-6L - Decision Framework Foundation

Patch 6I-6L adds deterministic backend foundation for doc 52 without adding an
AI execution path.

New tables:

- `imperium_user_priorities`
- `imperium_mission_scores`

New endpoints:

```http
GET  /api/imperium/decision-framework/schema
GET  /api/imperium/decision-framework/priorities
POST /api/imperium/decision-framework/priorities
POST /api/imperium/decision-framework/score-preview
```

Boundary rules:

- the priority hierarchy is JWT-scoped and backend-owned;
- users provide only the domain order;
- internal coefficients are derived deterministically from position
  (`1 -> 10`, `2 -> 8`, `3 -> 5`, `4 -> 4`);
- `score-preview` is read-only and returns `storage_enabled=false`;
- no AI task, AI result, n8n workflow, model call, pgvector write, embedding,
  daily plan, monthly plan, or canonical mission update is created by this
  patch.

Patch 7A-7D hardens the `score-preview` contract:

- canonical public scoring fields are `domain`, `title`, `deadline_at`,
  `impact`, `mission_type`, `dependency`, `recurrence`, and `payload`;
- `effort` and `alignment` remain temporary input aliases only. When accepted,
  they are reported through sanitized warnings
  (`canonical_alias:effort_used_for_mission_type` and
  `canonical_alias:alignment_used_for_recurrence`);
- ambiguous fields such as `importance`, `urgency`, and `risk` are not
  canonical and are rejected as unknown extras;
- user priorities are read to resolve domain position and the internal
  coefficient, but public responses do not expose the coefficient;
- the response includes UI fields such as `score_status`, `display_summary`,
  `priority_bucket`, `breakdown`, `missing_fields`, and `warnings`;
- public score-preview responses expose canonical explanation keys
  `deadline_points`, `impact_points`, `mission_type_points`,
  `dependency_points`, and `recurrence_points`;
- public score-preview responses do not expose `domain_coefficient`,
  `weighted_score`, `final_weighted_score`, or `position_to_coefficient`;
- unsafe payload keys are sanitized and the payload body is not echoed;
- preview remains read-only with `storage_enabled=false`.

Patch 7E aligns the public Decision Framework contract with doc 52 before any
mission score persistence is enabled. Coefficients and weighted scores remain
internal implementation details. The user-facing API exposes the chosen domain
position and a `priority_bucket` from 1 to 10 instead of raw coefficient math.

Patch 7F-1 prepares `imperium_missions` for future score persistence without
writing scores yet.

Mission structural fields:

```text
domain                 nullable; religious/business/finance/health
priority_level         nullable; 1..10
mission_type_category  nullable; cat_a..cat_i
status                 backlog/active/completed/failed/cancelled
```

Contract boundaries:

- mission start/create may persist these fields when provided;
- the fields remain optional to preserve existing mission rows;
- `imperium_mission_scores` is not automatically inserted or updated;
- `score-preview` remains read-only and does not mutate missions;
- `backlog` is now a valid storage status, but no full backlog engine is
  implemented yet;
- clients cannot submit `domain_coefficient`, `weighted_score`, or hidden
  coefficient data.

Patch 7F-2 adds controlled mission score storage to mission start.

Changed mission start inputs:

```text
deadline_at
impact
mission_type
dependency
recurrence
```

Storage contract:

- `POST /api/imperium/missions/start` writes one
  `imperium_mission_scores` row only when the mission has a `domain` and at
  least one scoring signal;
- `mission_type_category` is structural but may be used as the scoring
  `mission_type` when `mission_type` is missing;
- if both `mission_type` and `mission_type_category` are `cat_*` values, they
  must match;
- client-submitted score values are rejected (`intrinsic_score`,
  `weighted_score`, `domain_coefficient`, `final_weighted_score`,
  `coefficient`, `score`, `priority_bucket`);
- score rows are computed server-side and may store internal coefficient and
  weighted score values;
- public mission responses expose only safe score summary fields:
  `intrinsic_score`, `priority_bucket`, `score_status`, `missing_fields`, and
  `source`;
- `GET /api/imperium/missions/{mission_id}/decision-score` returns the safe
  read model for the current user only;
- `(user_id, mission_id, source)` is unique for `imperium_mission_scores`.

Patch 7F-2 does not add real AI calls, n8n orchestration, frontend behavior,
monthly planning, daily adaptation, pgvector writes, embeddings, automatic
memory writes, or public coefficient exposure.

Patch 7G reconciles legacy Imperium priority rules with the Decision Framework.

Priority source of truth:

- `imperium_user_priorities` is canonical;
- `/api/imperium/decision-framework/priorities` is the only write surface for
  user priority order;
- `imperium_priority_rules` remains as historical/compatibility storage and is
  not dropped;
- `GET /api/imperium/priorities` returns a compatibility projection from
  Decision Framework priorities;
- `POST /api/imperium/priorities` returns `410 Gone` and instructs callers to
  use `/api/imperium/decision-framework/priorities`;
- dashboard and daily plan priority context use `imperium_user_priorities`.

Patch 7G introduces no double-write bridge, no migration, no destructive
legacy data deletion, no n8n workflow, no AI call, no pgvector write, no
embedding, and no public coefficient exposure.

Patch 8B adds:

```text
GET /api/imperium/missions/backlog/decision-preview
```

Query params:

```text
limit             integer, default 10, min 1, max 50
domain            optional religious/business/finance/health
priority_level    optional integer 1-10
include_reasons   boolean, default true
```

Response contract:

```json
{
  "recommended_mission_id": "uuid-or-null",
  "candidate_count": 3,
  "candidates": [
    {
      "id": "uuid",
      "title": "Mission title",
      "domain": "business",
      "priority_level": 1,
      "priority_bucket": 4,
      "score_summary": {
        "label": "high",
        "reason_codes": ["HIGH_PRIORITY_BUCKET", "LOW_PRIORITY_LEVEL", "FIFO_BACKLOG"]
      }
    }
  ],
  "safe_explanation": "Deterministic backend preview based on stored backlog fields only."
}
```

Rules:

- GET only, no `Idempotency-Key` required;
- user-scoped through the authenticated user;
- deterministic sorting uses backlog ordering:
  `priority_bucket` descending, `priority_level` ascending, `created_at`
  ascending, then `id`;
- `recommended_mission_id` is the first returned candidate, or `null`;
- `include_reasons=false` returns only the safe label in `score_summary`;
- no mission status, `started_at`, or `ended_at` is exposed;
- no coefficient, weighted score, raw score, n8n call, AI call, pgvector write,
  embedding, memory commit, calendar replanning, or mission status mutation is
  introduced.
