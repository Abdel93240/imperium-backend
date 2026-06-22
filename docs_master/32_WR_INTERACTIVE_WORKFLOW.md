# 32 - WR Interactive Workflow

WR means **Weekly Review** (NOT Weekly Report). The deterministic read-only
"Weekly Report" is a separate object, defined in doc 29. Throughout the
ecosystem, "WR" always means Weekly Review.

This document defines the official interactive WR flow and the Patch 2B backend contract.

Core ownership:

```text
User <-> App popup <-> Backend Imperium <-> Qwen later <-> Backend Imperium <-> App popup
```

n8n may later orchestrate heavy preparation or Opus calls through `ai_tasks` and `ai_results`, but n8n does not own the WR conversation and must not receive every user message.

## Patch 2E - Qwen Adapter Boundary

Patch 2E adds a backend-side Qwen adapter helper for WR summary generation:

```text
generate_wr_summary_with_qwen(session, input_payload)
```

This helper returns a structured `QwenWeeklySummary` only.

It does not:

- approve a weekly review;
- create a final report;
- write pgvector memory;
- call Opus, GPT, Claude, or Gemini;
- call n8n;
- make Qwen canonical truth.

In dry-run mode, the helper returns a clearly marked mock summary with `warnings` that include `dry_run_no_network`.

The WR conversation remains backend-owned:

```text
User <-> App popup <-> Backend Imperium <-> Qwen adapter later <-> Backend Imperium <-> App popup
```

## Patch 2F - n8n Qwen Dry-Run Contract

Patch 2F adds an importable n8n workflow:

```text
ops/n8n/workflows/wr_interactive_start_qwen_dry_run.json
```

Workflow name:

```text
IMPERIUM_WR_INTERACTIVE_START_QWEN_DRY_RUN
```

Webhook path:

```text
imperium/wr/interactive-start-qwen-dry-run
```

The workflow receives the backend `prepared_payload`, calls the backend internal Qwen dry-run bridge, converts the structured Qwen response into an `AIResultCallback`, stores it through the official internal callback, then attaches the result to the WR session.

Important boundaries:

- n8n does not call the local model directly;
- n8n does not use the n8n AI Agent;
- no Opus, GPT, Claude, or Gemini call is made;
- no direct database write exists;
- the WR final report is not approved automatically;
- the result remains a proposal/message until backend/user validation.

## Patch 2G - WR Smoke Workflow Stabilization

Patch 2G keeps the same dry-run architecture but stabilizes production smoke-test behavior:

- n8n import uses a workflow JSON with a stable top-level `id`;
- Code nodes use `$env` instead of `process.env`;
- HMAC signing still uses Node `crypto`, so n8n must allow it with `NODE_FUNCTION_ALLOW_BUILTIN=crypto`;
- HTTP responses are normalized before reading fields such as `result_type` or `result_id`;
- workflow errors report safe response shapes/keys instead of stringifying raw response objects;
- attaching the same initial summary result again is safe;
- attaching a different initial summary after one is already set returns `409 Conflict`.

This prevents duplicate `initial_summary` messages after partial n8n retries.

## Patch 2H - Automatic Backend Trigger

Patch 2H connects the WR launch backend flow to n8n in a guarded way.

On first WR launch for a week:

```text
User starts WR
  -> backend creates/opens WR session
  -> backend creates ai_task(weekly_report.interactive.start)
  -> backend stores prepared_payload
  -> if N8N_DRY_RUN=false and signed outbound n8n is configured, backend POSTs prepared_payload to n8n
  -> n8n returns ai_result through backend callbacks
  -> backend attaches proposal/message
```

Important safety rules:

- `N8N_DRY_RUN=true` by default;
- when `N8N_DRY_RUN=false`, both `N8N_BASE_URL` and `N8N_WEBHOOK_SECRET` are required;
- backend refuses to send unsigned backend -> n8n webhook calls;
- idempotent replay does not trigger n8n twice;
- an existing WR task is not retriggered automatically;
- n8n unavailability does not fail the WR session;
- backend may record the outbound failure on the `ai_task` error fields;
- no final report approval happens automatically;
- no pgvector memory write happens automatically.

## Patch 2I - Frontend Conversation Read Model

Patch 2I adds one read-only endpoint for the future tablet/popup UI:

```http
GET /api/imperium/weekly-review/{session_id}/conversation
```

This endpoint requires JWT authentication and reads only the authenticated user's WR session.

It returns one consolidated frontend-friendly snapshot:

- the WR session;
- messages ordered by `created_at ASC`;
- the current AI task if one is linked;
- the initial and final AI result references if linked;
- the latest draft/final reports if present;
- safe UI flags:
  - `can_answer`;
  - `can_request_revision`;
  - `can_approve`;
  - `is_waiting_for_ai`;
  - `has_initial_summary`;
  - `has_final_draft`.

This endpoint does not:

- call Qwen, Opus, GPT, Claude, Gemini, or n8n;
- approve a final WR report;
- create canonical memory;
- write pgvector memory;
- modify session state.

The popup uses this endpoint to render the current WR conversation state without becoming the decision engine. All canonical mutations still go through existing backend POST endpoints with idempotency.

Patch 2M hardening: `initial_ai_result` and `final_ai_result` are slim summaries in this response. They include safe fields such as id, task id, result type, result payload, provider, model, confidence, status, and creation time. They do not include `raw_payload` or provider debug blobs. Raw payloads remain internal backend audit/debug data.

Patch 2N adds bounded read controls:

```http
GET /api/imperium/weekly-review/{session_id}/conversation
  ?messages_limit=200
  &messages_before=<datetime>
  &final_reports_limit=5
```

Rules:

- `messages_limit` defaults to `200` and is capped at `500`;
- `messages_before` is an optional timestamp cursor for older messages;
- response messages stay ordered oldest-to-newest;
- `final_reports_limit` defaults to `5` and is capped at `20`;
- final report candidates are read newest-first;
- the endpoint remains read-only and never exposes AI `raw_payload`.

## Patch 2J - Answer Integration Task Preparation

Patch 2J improves the existing user answer endpoint:

```http
POST /api/imperium/weekly-review/{session_id}/answer
```

The endpoint remains backward-compatible: it still returns the stored `WeeklyReviewMessageRead` user message.

On a fresh accepted request, the backend now:

1. stores the user answer as a WR message;
2. sets the WR session status to `integrating_answers`;
3. creates one queued AI task:

```text
task_type = weekly_report.answers.integrate
source_module = imperium
```

The task payload records the app/user trigger context:

```json
{
  "task_id": "uuid",
  "session_id": "uuid",
  "task_type": "weekly_report.answers.integrate",
  "source": "app",
  "trigger_type": "user_message",
  "source_ref_type": "weekly_review_session",
  "source_ref_id": "uuid",
  "week_start": "YYYY-MM-DD",
  "week_end": "YYYY-MM-DD",
  "latest_user_answer_message_id": "uuid",
  "latest_initial_ai_result_id": "uuid-or-null",
  "callback_url": "/api/internal/ai/tasks/{task_id}/result",
  "wr_attach_url": "/api/internal/weekly-review/{session_id}/attach-ai-result"
}
```

This payload is stored in both `ai_tasks.input_payload` and `ai_tasks.prepared_payload` so a future n8n workflow can consume it safely.

Idempotency rules:

- same `Idempotency-Key` plus same body returns the original message;
- same `Idempotency-Key` plus different body returns conflict;
- replay does not create another message;
- replay does not create another AI task.

Patch 2J does not auto-trigger n8n for answer integration. It only prepares the task. No final WR report is approved, no pgvector memory is written, and no AI result becomes canonical automatically.

Patch 2M hardening: answer integration task creation no longer overwrites an existing `session.current_ai_task_id`. This protects an in-flight launch task from being silently dropped when the user answers before the initial preparation chain has fully settled. The new `weekly_report.answers.integrate` task is still created and receives its own `prepared_payload`; the session pointer is assigned only when it was previously empty.

Patch 2N also cleans up the dev/mock summary endpoint idempotency. `mock_weekly_review_summary` now derives separate subkeys:

```text
{original_key}:ai-result
{original_key}:wr-attach
```

This endpoint remains mock/dev only. The split avoids accidental key sharing between AI result storage and WR attach while preserving safe replay behavior.

## Patch 2O - Answer Integration n8n Dry-Run Trigger

Patch 2O optionally connects answer integration tasks to n8n.

When the authenticated user posts:

```http
POST /api/imperium/weekly-review/{session_id}/answer
```

the backend stores the user answer and creates:

```text
task_type = weekly_report.answers.integrate
```

If the task is fresh and n8n outbound triggering is enabled, the backend signs and POSTs the task `prepared_payload` to:

```text
imperium/wr/answers-integrate-qwen-dry-run
```

Workflow artifact:

```text
ops/n8n/workflows/wr_answers_integrate_qwen_dry_run.json
```

Workflow name:

```text
IMPERIUM_WR_ANSWERS_INTEGRATE_QWEN_DRY_RUN
```

Safety behavior:

- `N8N_DRY_RUN=true` skips the outbound call;
- `N8N_DRY_RUN=false` requires signed outbound n8n config;
- missing config records `n8n_not_configured` on the AI task and does not fail the user answer;
- n8n failure records `n8n_trigger_failed` on the AI task and does not roll back the user answer;
- idempotent replay does not retrigger n8n;
- n8n returns a dry-run `weekly_report.draft`;
- the draft attaches as a proposal only;
- final approval remains explicit through the backend approve endpoint;
- no pgvector memory write happens.

## Patch 2K - Draft/Final Candidate Attachment

Patch 2K strengthens how WR draft and final AI results are handled.

When the internal endpoint receives an attached AI result:

```http
POST /api/internal/weekly-review/{session_id}/attach-ai-result
```

and the result has:

```text
result_type = weekly_report.draft
```

or:

```text
result_type = weekly_report.final
```

the backend creates a final-report candidate in `imperium_weekly_review_final_reports` with:

```text
status = draft
source_ai_result_id = <ai_result_id>
```

The candidate remains non-canonical.

Behavior:

- `weekly_report.draft` sets the WR session to `draft_ready`;
- `weekly_report.final` sets the WR session to `final_ready`;
- a WR message is added with type `draft` or `final_report`;
- attaching the same AI result again is safe and does not create duplicate draft/final messages;
- attaching a different final candidate over an existing candidate returns conflict unless a future explicit revision/superseding flow is implemented.

The backend does not:

- approve the report;
- mark it `stored`;
- write pgvector memory;
- create canonical weekly truth;
- let n8n write directly to PostgreSQL.

Approval still requires:

```http
POST /api/imperium/weekly-review/{session_id}/approve
```

## 1. Goal

The WR is not a passive report. It is an interactive weekly conversation that turns the user's week into a validated, structured, long-term memory candidate.

The system must never store the final AI analysis as truth until the user explicitly approves it.

## 2. Weekly Timing

Every Tuesday at 20:00 Europe/Paris, the WR banner in the UI changes from passive to active.

This banner activation is a backend-only scheduled rule. n8n is not involved.

Passive state:

```text
Weekly report not ready yet.
```

Active state:

```text
Weekly report ready.
Button: Start weekly report
```

The user does not have to start immediately. The banner stays active until the user starts or dismisses the WR according to the future UI rule.

## 3. Patch 2B Implemented Backend Layer

Patch 2B implements backend-owned storage and contracts only.

It does not implement Qwen calls, Opus calls, GPT calls, Gemini calls, n8n workflows, frontend UI, pgvector memory writes, or automatic finalization.

### Tables Added

- `imperium_weekly_review_sessions`
- `imperium_weekly_review_messages`
- `imperium_weekly_review_final_reports`

### Implemented Endpoints

| Endpoint | Method | Auth | Idempotency | Purpose |
|---|---:|---|---|---|
| `/api/imperium/weekly-review/state` | GET | JWT | no | Read the existing WR readiness/banner state. |
| `/api/imperium/weekly-review/session?week_start=YYYY-MM-DD` | GET | JWT | no | Get or create/read the backend-owned WR conversation session for a week. |
| `/api/imperium/weekly-review/launch` | POST | JWT | yes | Open the WR conversation session and create an AI task placeholder for future preparation. |
| `/api/imperium/weekly-review/{session_id}/messages` | GET | JWT | no | Read WR messages stored by the backend. |
| `/api/imperium/weekly-review/{session_id}/messages` | POST | JWT | yes | Store a user message in the backend-owned WR conversation. |
| `/api/imperium/weekly-review/{session_id}/answer` | POST | JWT | yes | Store a user answer to a WR clarification. |
| `/api/imperium/weekly-review/{session_id}/request-revision` | POST | JWT | yes | Store a user revision request. |
| `/api/imperium/weekly-review/{session_id}/final-draft` | POST | JWT | yes | Store or update a draft final report. This is not canonical yet. |
| `/api/imperium/weekly-review/{session_id}/approve` | POST | JWT | yes | Explicitly approve a draft/final report. |
| `/api/imperium/weekly-review/{session_id}/cancel` | POST | JWT | yes | Cancel a WR session. |
| `/api/internal/weekly-review/{session_id}/attach-ai-result` | POST | HMAC | yes | Attach a pending AI result to a WR session. |
| `/api/internal/ai/tasks/{task_id}/result` | POST | HMAC | yes | Generic n8n/AI result callback. |

Internal endpoints use HMAC-only headers:

```http
X-Timestamp: <unix timestamp seconds>
X-Signature: <hmac sha256 over "{timestamp}.{raw_body}">
Idempotency-Key: <stable callback key>
```

The old plaintext internal secret header is not used.

## 4. Patch 2C - Mock n8n Contract Preparation

Patch 2C prepares the backend-side contract for a future n8n WR workflow.

It is mock/contract-only:

- no real n8n workflow is added;
- no Qwen, Opus, GPT, Claude, Gemini, or external AI call is made;
- no frontend is touched;
- no `n8n_db` access is allowed;
- no AI output becomes canonical automatically.

When `/api/imperium/weekly-review/launch` creates the `ai_task` placeholder, the backend stores a future n8n trigger payload in `ai_tasks.prepared_payload`:

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

A reusable backend integration shell can build signed outbound backend → n8n requests using:

```http
X-Timestamp: <unix timestamp seconds>
X-Signature: <hmac sha256 over "{timestamp}.{raw_body}">
Idempotency-Key: <stable trigger key>
Content-Type: application/json
```

Optional settings:

- `N8N_BASE_URL`
- `N8N_WEBHOOK_SECRET`
- `N8N_REQUEST_TIMEOUT_SECONDS`
- `N8N_DRY_RUN`

These settings must not break backend startup if absent. They are optional only while `N8N_DRY_RUN=true`.

When `N8N_DRY_RUN=false`, outbound n8n is considered configured only if both `N8N_BASE_URL` and `N8N_WEBHOOK_SECRET` are present. The backend must not send unsigned n8n calls in production mode.

## Patch 2L - Outbound n8n Signature Hardening

Patch 2L makes backend -> n8n signing mandatory outside dry-run mode.

Rules:

- `N8N_DRY_RUN=true`: backend skips outbound n8n and no n8n settings are required;
- `N8N_DRY_RUN=false`: backend requires `N8N_BASE_URL` and `N8N_WEBHOOK_SECRET`;
- missing `N8N_WEBHOOK_SECRET` records `n8n_not_configured` on the `ai_task` and sends no HTTP request;
- outbound requests include `X-Timestamp`, `X-Signature`, `Idempotency-Key`, and `Content-Type`;
- n8n failure or misconfiguration does not roll back WR session or task creation;
- idempotent WR launch replay does not retrigger n8n.

Mock smoke endpoint:

```http
POST /api/internal/weekly-review/{session_id}/mock-ai-summary
```

Purpose:

- local contract smoke testing only;
- HMAC-only internal verification;
- creates or reuses an `ai_result` with `result_type = weekly_report.summary`;
- attaches the result to the WR session as a proposal/message;
- keeps the result `pending_validation`;
- does not approve a final report;
- does not create pgvector memory;
- does not call external AI.

---

## 5. Patch 2D - Importable Mock n8n Workflow

Patch 2D adds the first real n8n workflow artifact, but it is still mock-only.

Workflow file:

```text
ops/n8n/workflows/wr_interactive_start_mock.json
```

Workflow name:

```text
IMPERIUM_WR_INTERACTIVE_START_MOCK
```

Expected input is the `ai_tasks.prepared_payload` created when the backend launches a WR session:

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

Workflow behavior:

1. Webhook receives the prepared payload.
2. Code node validates required fields.
3. Code node builds a mock `weekly_report.summary` result.
4. Code node signs the exact raw JSON body with HMAC.
5. HTTP node calls `/api/internal/ai/tasks/{task_id}/result`.
6. Code node signs the WR attach payload with the returned `result_id`.
7. HTTP node calls `/api/internal/weekly-review/{session_id}/attach-ai-result`.

Required n8n environment variables:

```text
IMPERIUM_API_BASE_URL=http://imperium-api:8000
INTERNAL_WEBHOOK_SECRET=<backend internal HMAC secret>
```

Expected backend result:

- `ai_result.status = pending_validation`;
- WR session receives the mock summary as proposal/message;
- final report is not approved;
- no pgvector memory is written;
- no canonical WR finalization happens.

Patch 2D still does not implement Qwen, Opus, GPT, Claude, Gemini, real n8n production workflows, frontend UI, or final WR automation.

---

## 6. State Machine

Implemented WR conversation statuses:

```text
ready
launched
preparing_initial_summary
initial_summary_ready
waiting_for_user_answer
integrating_answers
draft_ready
revision_requested
final_ready
approved
stored
cancelled
failed
```

Meaning:

- `ready`: backend has a session or readiness state available.
- `launched`: user opened the WR flow.
- `preparing_initial_summary`: backend created a future AI task placeholder; no model call happens in Patch 2B.
- `initial_summary_ready`: an attached AI result produced an initial summary message.
- `waiting_for_user_answer`: an attached AI result produced questions.
- `integrating_answers`: user answers are being stored and prepared for later processing.
- `draft_ready`: a draft exists but is not approved.
- `revision_requested`: user requested changes.
- `final_ready`: a final candidate exists but still requires explicit approval.
- `approved`: user approved the final report.
- `stored`: future state for stored/canonical WR completion.
- `cancelled`: user cancelled the WR session.
- `failed`: backend marked the session failed.

## 7. User Flow

1. User clicks **Start weekly report**.
2. The app calls the backend.
3. The backend creates or opens the WR session.
4. The backend may create an `ai_task` placeholder for future preparation.
5. In a future patch, n8n may process that task and return an `ai_result`.
6. The backend attaches the AI result as a proposal/message.
7. User answers, revises, or approves inside the WR popup.
8. The backend stores all messages and draft/final reports.
9. Only after explicit user approval may the report become canonical.

## 8. Architecture Rule

The backend is the only DB writer.

n8n never writes directly to PostgreSQL.

Qwen, Opus, GPT, Claude, and Gemini never write directly to PostgreSQL.

All AI results return to the backend through authenticated endpoints and remain proposals until validated.

## 9. Data Sources for First WR Draft

The first WR draft reads deterministic backend data only:

- day reviews;
- missions;
- path items;
- daily plans;
- Vault transactions;
- active priority rules;
- previous approved WR summaries if useful;
- module-specific summaries approved by the backend.

The AI must clearly separate:

- facts from the DB;
- user-provided clarifications;
- AI interpretations;
- recommendations.

## 10. AI Routing

Qwen is the future local router and conversation controller.

Opus is the future default model for deep weekly analysis when WR has long context, multi-domain interpretation, and high consequence for long-term memory.

Patch 2B does not call Qwen, Opus, GPT, Claude, Gemini, or any external provider.

## 11. User Approval Rule

The user must approve the final WR before it becomes canonical.

```text
AI draft != canonical memory
Canonical WR = user-approved final report stored by backend
```

## 11A. Patch 2P-2T Frontend Contract

The popup can read one consolidated backend-owned snapshot:

```http
GET /api/imperium/weekly-review/{session_id}/conversation
GET /api/imperium/weekly-review/current
```

The conversation endpoint is read-only. It keeps JWT ownership, bounded reads, and stable ordering:

```text
messages_limit: default 200, max 500
messages_before: optional timestamp cursor
final_reports_limit: default 5, max 20
```

The response includes:

- session;
- messages oldest-to-newest;
- slim AI result summaries without `raw_payload`;
- bounded `final_report_candidates`, newest-first;
- current AI task summary;
- `ui_state`;
- `allowed_actions`.

`ui_state` is a deterministic UI hint, not a business decision:

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

- `initial_summary_ready` or `waiting_for_user_answer`: `answer`;
- `integrating_answers`: no action;
- `draft_ready`: `approve_draft`, `reject_draft`, `request_changes`;
- `approved` with an unstored approved report: `store_final_report`;
- stored, cancelled, closed, or failed sessions: no action.

Draft action endpoints:

```http
POST /api/imperium/weekly-review/{session_id}/draft/approve
POST /api/imperium/weekly-review/{session_id}/draft/reject
POST /api/imperium/weekly-review/{session_id}/draft/request-changes
POST /api/imperium/weekly-review/{session_id}/draft/store
```

Approval marks the latest draft candidate as approved and sets `approved_at`. It does not set `stored_at`, write pgvector memory, create canonical memory, or auto-store the WR as final system memory.

Store is a separate explicit V1 marker. `approved != stored`: approval records the user decision, while storage marks the approved report as persisted for WR completion. Store sets `stored_at` and `session.status = stored`, but it does not write pgvector memory, write `ai_memories`, create embeddings, call n8n, call AI, or silently create long-term memory. Memory/vector storage requires a later explicit patch.

Reject is non-destructive: it uses the existing `superseded` report status and stores rejection details in the report payload.

Request changes stores the user's feedback as a WR message, creates a `weekly_report.answers.integrate` task, and may trigger n8n only through the signed backend → n8n boundary when configured.

Diagnostic endpoint:

```http
GET /api/imperium/weekly-review/{session_id}/debug-status
```

This endpoint is JWT-protected and bounded. It returns task/result/message/report summaries for smoke tests. It may expose `raw_payload_keys`, but never raw provider payload bodies or secrets.

## 11B. Patch 2U Multi-Version Candidate History

WR final report candidates are now historical rows.

The backend may store multiple candidates for the same WR session over time:

- old rejected drafts remain as `superseded`;
- the active candidate may be `draft`, `approved`, or `stored`;
- only one active candidate is allowed per session;
- only one active candidate is allowed per user/week;
- revised drafts after a reject or request-changes create a new candidate row.

The replacement rule is explicit:

```text
active draft exists + different AI result -> conflict
active candidate rejected/superseded -> new AI result may create a new draft row
same AI result reattached -> idempotent OK, no duplicate message
```

`request-changes` supersedes the current active draft before creating the `weekly_report.answers.integrate` task. This lets the later n8n dry-run draft attach become visible as a new candidate without overwriting history.

No candidate becomes canonical automatically. Approval is still a separate user action, and approval still does not write pgvector memory or `stored_at`.

## 11C. Patch 2V-2Y Approval, Store, UI, And Debug Contract

Patch 2V hardens approval so only the latest active draft can be approved. Superseded drafts cannot be approved, closed sessions cannot be approved, and idempotent replay does not update `approved_at`.

Patch 2W adds:

```http
POST /api/imperium/weekly-review/{session_id}/draft/store
```

This endpoint is allowed only after approval. It sets `status = stored`, sets `stored_at`, and keeps `stored_at` stable on idempotent replay. It is not a pgvector or memory write.

Patch 2X keeps the popup read model frontend-ready:

- `approved` exposes `store_final_report` only while `stored_at` is empty;
- `stored` exposes no actions;
- raw AI provider payloads remain hidden;
- `/api/imperium/weekly-review/current` returns the same safe conversation contract.

Patch 2Y expands debug status with active final report id/status, active and historical candidate counts, latest user/revision message ids, and latest answer integration task id. Debug may show `raw_payload_keys`, never raw payload bodies.

No automatic final approval, automatic final storage, pgvector write, `ai_memories` write, n8n AI Agent, direct n8n DB write, or real AI call is part of this contract.

## 11D. Patch 3A-3D Frontend Weekly Review V1

Patch 3A-3D adds the first functional frontend WR screen:

```text
Imperium/frontend/weekly-review/index.html
```

The screen is a static frontend that consumes backend-owned WR endpoints. It does not contain backend business logic and does not invent actions.

Frontend read flow:

```http
GET /api/imperium/weekly-review/current
GET /api/imperium/weekly-review/{session_id}/conversation
```

Frontend write actions:

```http
POST /api/imperium/weekly-review/{session_id}/answer
POST /api/imperium/weekly-review/{session_id}/draft/approve
POST /api/imperium/weekly-review/{session_id}/draft/reject
POST /api/imperium/weekly-review/{session_id}/draft/request-changes
POST /api/imperium/weekly-review/{session_id}/draft/store
```

Rules:

- buttons are rendered strictly from `conversation.allowed_actions`;
- each POST sends `Authorization`, `Content-Type: application/json`, and `Idempotency-Key`;
- after every POST, the frontend reloads `/current`;
- waiting states poll `/current` every few seconds;
- `AIResult.raw_payload` is never expected or rendered;
- approval and storage remain explicit user actions;
- frontend does not call n8n, AI models, pgvector, memory, or the database.

## 11E. Patch 4A-4D Finalization Read And Export Surfaces

Patch 4A-4D adds read-only backend surfaces for finalized Weekly Reviews.

History endpoint:

```http
GET /api/imperium/weekly-review/history?limit=20&offset=0&status=stored&stored_only=true
```

It is JWT-protected, user-owned, paginated, and returns a list object with `items`, `limit`, `offset`, `count`, and `has_more`. Each item includes session dates/status, latest final report summary, final report counts, superseded counts, and booleans for initial summary, active/stored reports, stored report, and superseded history.

Final report endpoint:

```http
GET /api/imperium/weekly-review/{session_id}/final-report
```

It returns the latest relevant final report owned by the current user. Selection priority is:

```text
stored > approved > draft > superseded
```

Markdown export endpoint:

```http
GET /api/imperium/weekly-review/{session_id}/final-report/markdown
```

It returns `text/markdown`. If `report_markdown` is blank, the backend generates markdown from sanitized `report_payload` with title, summary, sections, questions answered, and metadata.

Finalization safety rules:

- all endpoints require JWT and enforce session ownership;
- foreign sessions return 404;
- read/export endpoints never expose `AIResult.raw_payload`;
- markdown export is read-only;
- once a session is `stored`, mutation actions remain closed;
- storing a final report does not write memory, write pgvector, create embeddings, call AI, call n8n, or auto-approve anything.

### Patch 4E-4H Finalization Hardening

Final report by id:

```http
GET /api/imperium/weekly-review/final-reports/{report_id}
```

This is JWT-protected and scoped to the current user. Missing or foreign reports return 404. It supports every candidate status: `draft`, `approved`, `stored`, and `superseded`. It returns the full sanitized final report read model and never exposes `AIResult.raw_payload`.

Stored reports index:

```http
GET /api/imperium/weekly-review/final-reports/stored?limit=20&offset=0
```

This returns only stored final reports for the current user, newest first by `stored_at` then `created_at`. The response is a list object with `items`, `limit`, `offset`, `count`, and `has_more`. Each item is a slim summary only: id, session id, week range, status, title, summary, timestamps, and source AI result id. It intentionally omits full `report_payload`, `report_markdown`, `memory_candidates`, and all raw provider payloads.

Terminal mutation rule:

- terminal session statuses are `stored`, `cancelled`, and `failed`;
- a new mutation request against a terminal session returns 409 with `Cannot modify a closed weekly review session.`;
- replay of an earlier successful idempotent request still returns the cached response;
- a same-key/different-body replay still returns idempotency conflict;
- `stored` sessions cannot accept answers, approve, reject, request changes, or store again with a new key.

History and debug consistency:

- history now separates `active_reports_count`, `stored_reports_count`, and `superseded_reports_count`;
- active reports mean `draft` or `approved`;
- stored reports are terminal and exportable, but not active for mutation;
- `has_active_or_stored_report` is true when active count or stored count is non-zero;
- debug status exposes latest report ids and counts, but only raw payload keys when needed, never raw payload bodies.

### Patch 4I-4L Memory Projection Prep

Memory candidate preview endpoints:

```http
GET /api/imperium/weekly-review/{session_id}/memory-candidates
GET /api/imperium/weekly-review/final-reports/{report_id}/memory-candidates
GET /api/imperium/weekly-review/memory-candidates/preview?limit=20&offset=0
```

These endpoints are JWT-scoped read endpoints. They expose deterministic memory projection candidates derived from an existing WR final report, preferably the stored report. If a session endpoint is used, final report selection follows the normal priority:

```text
stored > approved > draft > superseded
```

Candidate response rules:

- `storage_enabled` is always `false`;
- the response note says candidates are proposals only;
- candidates may come from `report_payload.memory_candidates`, the final report `memory_candidates` column, or a deterministic fallback built from summary, sections, and questions answered;
- no raw provider payload is exposed;
- reading candidates does not mutate the session or final report;
- no memory is stored;
- no pgvector write, `ai_memories` write, embedding job, n8n call, or AI call occurs.

Candidate kinds are strings for V1: `behavior_pattern`, `blocker`, `weekly_commitment`, `preference`, `operational_signal`, `risk`, and `achievement`. Future memory storage requires a separate explicit user approval patch.

### Patch 4M-4P Memory Candidate Decisions

Patch 4M-4P adds a user decision layer for WR memory projection candidates without storing anything into long-term memory.

Decision endpoints:

```http
POST /api/imperium/weekly-review/final-reports/{report_id}/memory-candidates/{candidate_id}/approve
POST /api/imperium/weekly-review/final-reports/{report_id}/memory-candidates/{candidate_id}/reject
POST /api/imperium/weekly-review/final-reports/{report_id}/memory-candidates/{candidate_id}/edit
GET /api/imperium/weekly-review/memory-candidates/decisions?limit=20&offset=0
```

Rules:

- POST endpoints require JWT ownership and `Idempotency-Key`;
- decisions are allowed only for `approved` or `stored` final reports;
- `draft` and `superseded` report candidates remain preview-only and cannot receive decisions;
- a candidate can receive one decision: `approved`, `rejected`, or `edited`;
- idempotent replay returns the original decision without creating duplicates;
- a different key for an already decided candidate returns conflict;
- edited decisions preserve the original candidate and store `edited_candidate` separately.

The table `imperium_memory_candidate_decisions` stores decisions as audit records. These records are still proposals for future memory materialization. An approved or edited decision does not write `ai_memories`, does not write pgvector, does not create embeddings, does not call n8n, and does not call any model.

Memory candidate read responses now merge decisions:

- `decision_status`: `undecided`, `approved`, `rejected`, or `edited`;
- `decision_id`;
- `decided_at`;
- `edited_candidate`;
- `effective_candidate` for frontend convenience.

The preview index hides rejected candidates by default. Use `include_rejected=true` to include them for audit/review.

### Patch 4Q-4T Memory Commit Readiness

Patch 4Q-4T adds the final readiness layer before any future memory materialization.

Commit-ready read endpoints:

```http
GET /api/imperium/weekly-review/memory-candidates/commit-ready?limit=20&offset=0
GET /api/imperium/weekly-review/final-reports/{report_id}/memory-candidates/commit-ready
```

These endpoints are JWT-scoped read models. They return only memory candidate decisions with `decision = approved` or `decision = edited`. Rejected decisions are excluded.

Each returned item includes:

- original candidate;
- edited candidate when present;
- effective candidate;
- readiness status: `ready` or `blocked`;
- readiness reasons when blocked.

A candidate is `ready` only when it has a non-empty title, non-empty content, valid kind, valid confidence between 0 and 1, and valid proposed memory scope.

Dry-run endpoint:

```http
POST /api/imperium/weekly-review/memory-candidates/commit-dry-run
```

The dry run requires JWT and `Idempotency-Key`. It accepts decision ids and returns how many candidates would be committed later, plus blocked decisions and reasons. It always returns `storage_enabled = false` and the note: `Dry run only. Nothing has been written to memory.`

This is not memory storage. Approved or edited decisions are only proposals ready for a future explicit memory commit patch. Patch 4Q-4T does not write `ai_memories`, does not write pgvector, does not create embeddings, does not call n8n, and does not call any model.

### Patch 5A-5D Chatbot Weekly Review Flow

The chatbot as a general component (universal entry point, per-message scoring,
write authority, closing extraction) is owned by doc 72. This section describes
its WR-specific flow only; doc 72 owns the general chatbot behavior.

Patch 5A-5D changes the product contract from a form-like flow to a chatbot popup flow.

Primary chat endpoints:

```http
POST /api/imperium/weekly-review/{session_id}/chat/messages
POST /api/imperium/weekly-review/{session_id}/chat/confirm-no-more-input
```

The conversation read model now exposes product-level actions:

```text
send_message
confirm_no_more_input
approve_draft
request_changes
store_final_report
```

Rules:

- the initial AI summary is shown as visible state-of-week analysis in the chat;
- user chat messages are stored as backend-owned WR messages;
- dry-run Qwen follow-up messages are deterministic and user-facing;
- hidden chain-of-thought, raw provider payloads, and internal prompts must never be exposed;
- final draft generation happens only after explicit `confirm_no_more_input`;
- `request_changes` supersedes the active draft and returns the session to `conversation_active`;
- a revised final draft can be generated only after the user confirms again;
- approval and storage remain explicit separate user actions.

Main UI states:

```text
preparing_initial_summary
conversation_active
draft_ready
approved
stored
failed
closed
```

Compatibility:

- existing stored sessions remain readable;
- legacy `/answer` remains available for backward compatibility, but new frontends should use `/chat/messages`;
- final report history, exports, memory candidates, memory decisions, and commit dry-run endpoints are unchanged.

Safety:

- no frontend code is part of this backend patch;
- no real AI/model call is made;
- no n8n workflow or n8n AI Agent is added;
- no direct n8n DB write is allowed;
- no automatic approval or storage occurs;
- no memory, pgvector, embedding, or `ai_memories` write occurs.

### Patch 5E-5H Chatbot Read Model and Action Contract

Patch 5E-5H adds frontend-ready fields to the conversation snapshot so the popup does not infer product state from raw rows.

`GET /api/imperium/weekly-review/{session_id}/conversation` now includes:

- `chat_timeline`: ordered display items with normalized roles and item types;
- `visible_ai_state`: safe user-visible analysis state, never hidden reasoning;
- `latest_assistant_prompt`: latest assistant question, usually the final confirmation prompt;
- `draft_review_state`: active draft/report review state;
- `primary_action` and `secondary_actions`: backend-derived UI actions;
- legacy `allowed_actions` remains for compatibility.

Action descriptors include:

```text
action
label
endpoint_hint
method
requires_text
style
enabled
disabled_reason
confirmation_required
```

Backend action contract:

- `conversation_active`: primary `send_message`, secondary `confirm_no_more_input`;
- `draft_ready`: primary `approve_draft`, secondary `request_changes` and `reject_draft` when supported;
- `approved`: primary `store_final_report`, with `request_changes` available when an approved active report can still be superseded;
- `stored`, `failed`, `closed`, and waiting states: no mutation action.

Patch 5I-5J active report rule:

- an active mutable report is the latest candidate with status `draft` or `approved`;
- `stored` reports remain display/export records and are not mutable draft candidates;
- `superseded` reports are historical only and never unlock approval, storage, chat, or confirmation actions;
- when `session.status=draft_ready` and an active `draft` exists, `draft_review_state.has_draft=true`, `primary_action=approve_draft`, and chat/confirm actions are disabled;
- when `session.status=approved` and an active `approved` report exists, `primary_action=store_final_report` and chat/confirm actions are disabled;
- terminal sessions (`stored`, `cancelled`, `failed`) can still display the latest report summary/preview, but expose no enabled mutation action.

Anti-corruption rules:

- terminal sessions (`stored`, `cancelled`, `failed`) reject mutations;
- final draft generation requires user-provided input;
- chat messages are rejected while a draft is ready unless the user requests changes first;
- confirming no more input while a draft is ready returns conflict unless it is the same idempotency replay;
- approval requires an active draft;
- storage requires an approved active report;
- request changes requires a draft or approved report, supersedes it, and returns to `conversation_active`.

Visible AI state is product-facing only. It must not expose raw provider payloads, internal prompts, hidden reasoning, secrets, or debug data.

### Patch 5K-5R Memory Target Table and Explicit Commit

Patch 5K-5N adds the durable memory target table `ai_memories`.
Patch 5O-5R adds explicit user-triggered commit from approved or edited WR memory candidate decisions.

Rules:

- WR memory candidates are still proposals;
- no WR candidate is committed automatically;
- `POST /api/imperium/weekly-review/memory-candidates/commit` is the only V1 commit path;
- commit writes one sanitized `ai_memories` row per eligible approved/edited decision;
- rejected, foreign, missing, malformed, or undecided decisions are blocked;
- duplicate source decisions return existing memory references instead of duplicate rows;
- no frontend memory action is added;
- no AI/model call is added;
- no n8n workflow writes memory;
- no pgvector or embedding column is added.

Read endpoints:

```http
GET /api/imperium/memories?limit=20&offset=0&status=active&kind=...&scope=...&q=...
GET /api/imperium/memories/{memory_id}
GET /api/imperium/memories/schema
POST /api/imperium/memories/{memory_id}/archive
POST /api/imperium/memories/{memory_id}/supersede
```

`GET /api/imperium/memories/schema` reports `storage_enabled=true`, `embeddings_enabled=false`, and `pgvector_enabled=false`.

Patch 5S-5V hardens memory lifecycle and read models:

- memory index results are always scoped to the current JWT user;
- the default memory index returns only `active` memories unless another `status` or `status=all` is requested;
- filters include `kind`, `scope`, source module/type, Weekly Review source ids, and simple title/content `ilike` search;
- archive changes an active memory to `archived` without deleting the row;
- supersede creates a new active memory revision and marks the previous active row `superseded`;
- terminal memories (`archived`, `superseded`, `deleted`) reject new archive/supersede mutations except exact idempotent replay;
- lifecycle actions do not change WR final reports and do not trigger n8n;
- metadata stored during lifecycle actions is sanitized and must not include raw payloads, prompts, hidden reasoning, or secrets;
- no embeddings, pgvector write, vector search, automatic memory commit, or n8n DB write is added.

## 12. Storage Model

The final WR is stored in Imperium's canonical DB, not in n8n.

Storage split:

1. WR session table: state, week range, status, timestamps.
2. WR messages table: user/backend/Qwen/Opus/system chat turns.
3. WR final report table: draft/approved final report and structured extracts.
4. AI task/result tables: raw AI task metadata, model used, confidence, and result envelope.

The n8n execution history is not the source of truth. It is only operational trace.

## 13. Privacy Rule

When a cloud model is called in a future patch, the backend should send a complete but minimized working summary.

The model should not receive direct personal identifiers unless a future explicit exception is created and approved by privacy policy.

On very_high content (health, religious), the access-regime principle applies:
the service degrades (abstention) rather than sending to the cloud - see doc 52
§9A. The minimized-summary rule above is the standard case; very_high is the
degraded case.

## 14. Failure Handling

If n8n fails in a future heavy workflow:

- backend keeps WR status visible;
- user sees a retry option;
- no partial AI output becomes canonical;
- idempotency prevents duplicate WR sessions;
- failed AI tasks are stored as operational failures.

If user closes the popup:

- WR session remains resumable;
- status remains recoverable;
- no final storage occurs until approval.

## 15. V1 Non-Goals

Patch 2B does not include:

- automatic life decisions;
- automatic objective changes;
- direct n8n DB writes;
- hidden finalization without user approval;
- n8n AI Agent as decision maker;
- unapproved medical interpretation inside WR;
- pgvector memory writes;
- frontend UI;
- real AI model calls.

## Audit Patch 1 Applied

The 2026-05-02 backend audit (Patch 1) tightened three WR surfaces:

- **`/api/internal/weekly-review/{session_id}/mock-ai-summary`** now returns
  `404 Not found.` when `settings.environment` is anything other than
  `"local"` or `"test"`. The endpoint remains available for local n8n contract
  smoke tests but is unreachable in staging/production even with a valid
  HMAC. n8n workflows targeting non-local environments must use
  `/api/internal/ai/tasks/{task_id}/result` + `attach-ai-result` instead.
- **`commit_weekly_review_memory_candidates`** filters
  `ImperiumMemoryCandidateDecision.user_id == current_user.id` at the SQL
  level. The previous `"foreign"` post-fetch reason code is gone — any
  decision_id not owned by the caller now collapses into the same `"not_found"`
  bucket, eliminating the existence-leak in a future multi-user mode. The
  same SQL-level filter is used in `dry_run_weekly_review_memory_commit`.
- **`WeeklyReviewMessageCreate.role`** is now `Literal["user"]`. The defense-
  in-depth `if payload.role != "user"` check in the route is preserved. A
  separate `WeeklyReviewMessageCreateInternal` schema retains the original
  permissive role regex for backend-only call sites; it must never be wired
  to a user-facing route.

## Audit Closure Patch 6E-6H

Patch 6E-6H tightens the WR conversation boundary before VPS deployment:

- public WR message creation is strictly user-originated;
- public message creation accepts only `role=user`;
- public message creation accepts only user-facing message types:
  `user_answer`, `chat_message`, and `revision_request`;
- assistant messages (`qwen`/`opus`), system notes, backend messages, initial
  summaries, assistant follow-ups, and final draft messages are created by
  backend services only;
- `/api/imperium/weekly-review/{session_id}/debug-status` keeps local/test
  diagnostics but sanitizes non-local responses by removing provider/model
  identifiers, raw payload keys, raw result payloads, model hints, privacy
  labels, and internal error messages;
- ordinary WR conversation/final-report/export reads remain sanitized and do
  not expose `AIResult.raw_payload`.

No product behavior changes: WR remains backend-owned, user-approved, and
idempotent. No frontend, real AI call, n8n AI Agent, direct n8n DB write,
automatic memory write, pgvector write, or embedding generation is introduced.

## Patch 6I-6L Decision Framework Alignment

Patch 6I-6L implements the deterministic Decision Framework foundation from
doc 52 as a backend service and API surface.

WR remains the feedback loop, not the automatic decision writer:

- WR may later surface that mission priorities felt wrong;
- future patches may use WR feedback to tune scoring inputs;
- this patch does not change WR state machines;
- this patch does not create monthly plans or daily plans;
- this patch does not call Qwen, Opus, GPT, Claude, Gemini, or n8n;
- this patch does not write memory, pgvector, embeddings, or canonical mission
  changes.

The new read/write surfaces are:

```http
GET  /api/imperium/decision-framework/schema
GET  /api/imperium/decision-framework/priorities
POST /api/imperium/decision-framework/priorities
POST /api/imperium/decision-framework/score-preview
```

`score-preview` is deterministic and read-only. It can explain deadline,
impact, effort/type, dependency, and alignment/recurrence points, but it stores
nothing and returns `storage_enabled=false`.
## Patch 6M-6P Multi-Model Routing & Rolling Planning Alignment

Patch 6M-6P aligns the WR specification with the consolidated AI architecture
decisions (June 2026). It is a **documentation alignment patch**: it updates the
WR's functional vision (routing, rolling planning, calendar, projects) and does
not, by itself, change the implemented backend state machine, contracts, or
storage. Implementation of the real model calls remains gated behind the
existing dry-run boundaries until separately patched.

Ownership boundary (canonical):

- **Doc 32 (this document) owns the WR business logic**: phases, data sources,
  conversation behaviour, state machine, approval, storage.
- **Doc 30 owns AI routing**: model hierarchy, the `/200` scoring, escalation,
  static overrides, and the shared dialogue engine.
- Where routing detail is needed here, this document **references doc 30** rather
  than restating it, to prevent the two documents from drifting apart.

### 6M — Rolling 4-week planning model

The WR is not a single-week summary. It is a **rolling planning window**:

```text
[ -4 weeks  ……  current  ……  +4 weeks ]
        past (analysed)        future (planned)
```

- Four weeks behind: the user's recorded data, analysed.
- Four weeks ahead: the plan the WR maintains.
- Each weekly run advances the window by one week (a "wagon on rails").

Re-planning is **conservative**: if a previously produced plan still holds, the
WR leaves it unchanged. Only where reality diverged from the plan does the WR
revise — and it may revise every week ahead of the current one. This is what
"lays the rails" that the local model then follows for day-to-day decisions
during the week, so the heavy model is not called by reflex.

### 6N — Three phases of the WR run

The WR run is structured in three phases. The phase→model mapping is governed by
doc 30 (§6.3 and §7.6); summarized here for the business flow only.

1. **Summary by exception.** Reviews the week focusing on *changes/deviations*,
   not a full recital. Stable domains are skimmed; changes are reported with
   precise figures (e.g. "food budget +13%"), crossing domains (e.g. fatigue
   declared while health constants were good). The backend pre-computes the
   figures from deterministic data (see §9). Maps to the existing
   `preparing_initial_summary` → `initial_summary_ready` states.

2. **Relevant questions + conversation.** The system asks pertinent,
   non-generic questions about the detected deviations and sustains a dialogue
   in which the user can push back. Maps to `conversation_active` /
   `waiting_for_user_answer`. Domain turns consult specialists behind the scenes
   (see §10).

3. **Rolling 4-week re-planning.** The dialogue is summarized and integrated
   with prior plans, historical memory, and the calendar (§9) to refine the next
   four weeks. Maps to `integrating_answers` → `draft_ready`. Per doc 30 §7.6,
   the re-planning step is the one WR moment forced to the top model tier.

Phases remain bounded by the existing approval rule (§11): nothing becomes
canonical without explicit user approval.

### 6O — Projects as decisions to evaluate

The WR does **not** manage, plan, or break down projects (that belongs to the
project module, doc-side §8 of doc 30). Within the WR, a project appears **only
as a decision to evaluate** — typically the timing of activating a project
versus the user's state. Example: "you activated this heavy, slow-return project
in a week you were exhausted; wouldn't a higher-energy month suit it better?"

This keeps the WR faithful to its purpose: reviewing the week's decisions. A
project activation is just one such decision, evaluated like any other (a skipped
mission, a budget change). No project field becomes a WR-managed object.

### 6P — Calendar integration (V1) and vectorization status

- **Calendar: integrated in V1.** The rolling re-planning (Phase 3) reads the
  user's calendar. Calendar sync is an external-API trigger handled by n8n
  (doc 30 §4.4); the backend stores an exploitable snapshot; the WR reads it in
  Phase 3. Decision rationale: the planning value outweighs the connection
  overhead.
- **Vectorization: future milestone, not yet active.** The WR already produces
  user-validated memory candidates committed to `ai_memories` (Patches 5K-5V),
  but `embeddings_enabled=false` and `pgvector_enabled=false` remain in force.
  The "summarized, vectorized" integration the WR is designed around is a
  **planned milestone** on the existing pgvector infrastructure, to be enabled by
  a later patch. Until then, memory candidates are stored without embeddings and
  read non-vectorially. The target mechanism (rich WR log, learning elements
  vectorized into ai_memories, and the entry-audit vectorized in the ephemeral
  working vector store then destroyed) is owned by doc 47 (WR guided sections)
  and doc 38 §7-bis (ephemeral store). This doc describes the V1 phasing; doc
  47/38 describe the target design.

### Section 10 rewrite (replaces the former "10. AI Routing")

## 10. AI Routing

WR routing is governed by **doc 30 (AI Routing & Scoring Policy)**. This section
states only how the WR uses that policy; it does not redefine models, scores, or
thresholds.

- **Shared dialogue engine.** The WR uses the dialogue engine of doc 30 §6: a
  single **conductor model (Qwen 32B local)** holds the thread and speaks to the
  user; the **backend holds the shared context** across turns; **specialists are
  consulted behind the scenes** (e.g. health → GPT-5.5) and the conductor
  restitutes their input itself, so the user always faces a single interlocutor.
  Raw provider payloads, internal prompts, and hidden reasoning are never exposed
  (consistent with Patches 5A-5H).

- **Per-turn escalation (mixed).** Each turn is scored (doc 30 §5). Routine turns
  (acknowledgements, simple follow-ups) stay on Qwen 32B; demanding turns
  escalate to Opus 4.8. Escalation is mixed: hard rules at key moments, dynamic
  scoring for the rest (doc 30 §5.6–§5.8).

- **Phase mapping.**
  - Phase 1 (summary by exception): reasons over backend-prepared data; escalates
    to Opus 4.8 if needed, lighter when data is well prepared.
  - Phase 2 (questions + conversation): Qwen 32B conductor, escalating to Opus
    4.8 on demanding turns; domain turns consult specialists.
  - Phase 3 (rolling re-planning): **forced to Fable 5** by doc 30 §7.6 (the one
    recurring task that is simultaneously long, complex, and high-stakes/durable).
    Fable's own safeguard reroutes high-risk topics to Opus 4.8.

- **No reflex premium calls.** Opus and Fable are never called by reflex. The
  heavy tiers serve the WR only at the moments their value is established (the
  re-planning step, or a turn the scoring escalates).

- **Same engine, the Imperium chatbot.** The Imperium chatbot reuses this exact
  engine (doc 30 §6.4): same conductor, same specialists-in-the-background, same
  shared context — but as an open, on-demand dialogue with no imposed phases and
  no forced re-planning step.

Historical note: the former §10 described "Qwen later" and "Opus later" as
future models with no real calls (dry-run era). That description is superseded by
this rewrite and by doc 30. The dry-run implementation boundaries still hold
until the model calls are separately enabled.

### §9 addendum — calendar as a data source

The "Data Sources for First WR Draft" list (§9) is extended with:

- **calendar snapshot** (user's calendar for the rolling window), synced via n8n
  (doc 30 §4.4) and stored by the backend.

The fact/clarification/interpretation/recommendation separation in §9 still
applies; the calendar is a *fact* source.

### §15 addendum — non-goals revision

The former §15 listed "real AI model calls" as a Patch 2B non-goal. That was true
of the dry-run era. As the routing is enabled (per doc 30), real model calls
cease to be a non-goal. The following remain firm V1 non-goals:

- automatic life decisions or objective changes without user approval;
- hidden finalization without user approval;
- direct n8n DB writes; n8n AI Agent as decision maker;
- unapproved medical interpretation inside WR;
- automatic (non-user-triggered) memory commit;
- pgvector/embedding writes and vector search (deferred milestone, see 6P).
