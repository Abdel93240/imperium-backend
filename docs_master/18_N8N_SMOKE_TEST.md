# 18 - n8n Smoke Test

## Patch 7H - Calendar Foundation API Smoke Examples

Patch 7H calendar endpoints are backend-only. They do not require an n8n
workflow, n8n AI Agent, or n8n database access.

Manual backend smoke examples:

```http
POST /api/imperium/calendar/events
Idempotency-Key: calendar-smoke-001
Content-Type: application/json
Authorization: Bearer <access_token>
```

```json
{
  "event_type": "event",
  "title": "Doctor appointment",
  "starts_at": "2026-06-01T09:00:00Z",
  "ends_at": "2026-06-01T10:00:00Z",
  "blocks_time": true,
  "location": "Paris",
  "notes": "Bring documents"
}
```

```http
GET /api/imperium/calendar/events?from=2026-06-01T00:00:00Z&to=2026-06-07T23:59:59Z&event_type=event
Authorization: Bearer <access_token>
```

```http
DELETE /api/imperium/calendar/events/{event_id}
Authorization: Bearer <access_token>
```

Expected boundary:

- backend is the only canonical writer;
- POST requires `Idempotency-Key`;
- no recurrence, auto-replan, AI scheduling, mobile sync, notifications,
  pgvector write, or embeddings are triggered.

## Patch 2F - WR Qwen Dry-Run Workflow Smoke Test

Workflow file:

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

Required n8n environment variables:

```text
IMPERIUM_API_BASE_URL=http://imperium-api:8000
INTERNAL_WEBHOOK_SECRET=<same HMAC secret as backend>
```

Expected input payload:

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

Workflow chain:

```text
Webhook
  -> validate prepared_payload
  -> POST /api/internal/ai/qwen/smoke
  -> convert QwenWeeklySummary to AIResultCallback
  -> POST /api/internal/ai/tasks/{task_id}/result
  -> POST /api/internal/weekly-review/{session_id}/attach-ai-result
```

Expected backend result:

- `ai_result` stored as `pending_validation`;
- WR session receives an attached proposal/message;
- no final report approval;
- no pgvector write;
- no canonical business action.

Troubleshooting:

- `401 Stale webhook timestamp`: n8n host clock is drifting or the request was delayed.
- `401 Invalid signature`: signed body and sent body differ, or the HMAC secret differs.
- `422 Internal Qwen smoke only supports...`: workflow sent a task type or mode other than `weekly_report.summary` / `weekly_summary`.
- `409 Idempotency key already used...`: replay used a different payload for the same key.
- `404 AI task not found`: payload `task_id` does not exist in backend.

Patch 2N note: stale timestamp rejection is covered by backend tests. A correctly signed request is still rejected when `X-Timestamp` is older than the configured HMAC tolerance.

### Patch 2O - WR Answers Integrate Dry-Run Workflow

Workflow file:

```text
ops/n8n/workflows/wr_answers_integrate_qwen_dry_run.json
```

Workflow name:

```text
IMPERIUM_WR_ANSWERS_INTEGRATE_QWEN_DRY_RUN
```

Webhook path:

```text
imperium/wr/answers-integrate-qwen-dry-run
```

Backend outbound setting:

```text
WR_N8N_ANSWERS_INTEGRATE_WEBHOOK_PATH=imperium/wr/answers-integrate-qwen-dry-run
```

Expected chain:

```text
User answers in WR popup
  -> backend stores user message
  -> backend creates ai_task(weekly_report.answers.integrate)
  -> backend signs and sends prepared_payload to n8n when enabled
  -> n8n returns weekly_report.draft through /api/internal/ai/tasks/{task_id}/result
  -> n8n attaches the result through /api/internal/weekly-review/{session_id}/attach-ai-result
  -> backend stores draft proposal only
```

No direct DB write, no n8n AI Agent, no real model call, no automatic final approval, and no pgvector write are part of this smoke workflow.

### Patch 2G stabilization notes

The Qwen dry-run workflow was stabilized for n8n `2.14.2`.

Runtime requirements:

```text
NODE_FUNCTION_ALLOW_BUILTIN=crypto
IMPERIUM_API_BASE_URL=http://imperium-api:8000
INTERNAL_WEBHOOK_SECRET=<same HMAC secret as backend>
```

Workflow rules:

- the workflow JSON includes a stable top-level `id` for n8n import;
- Code nodes use `$env`, never `process.env`;
- HTTP response consumers normalize direct JSON, `{ body: ... }`, and `{ data: ... }` response shapes;
- errors never stringify full raw HTTP response objects;
- duplicate replays with the same attached `ai_result_id` are safe;
- attempting to replace an already attached initial summary with a different `ai_result_id` returns `409`.

### Patch 2H backend-triggered smoke test

Patch 2H lets the backend trigger this workflow automatically after WR launch when n8n triggering is enabled.

Backend environment:

```text
N8N_DRY_RUN=true
N8N_BASE_URL=
N8N_WEBHOOK_SECRET=
```

Safe mode is the default. With `N8N_DRY_RUN=true`, the backend skips outbound n8n triggers and does not require `N8N_BASE_URL` or `N8N_WEBHOOK_SECRET`.

Real outbound n8n trigger mode:

```text
N8N_DRY_RUN=false
N8N_BASE_URL=http://imperium-n8n:5678/webhook/
N8N_WEBHOOK_SECRET=<required outbound HMAC signing secret>
WR_N8N_QWEN_DRY_RUN_WEBHOOK_PATH=imperium/wr/interactive-start-qwen-dry-run
N8N_REQUEST_TIMEOUT_SECONDS=10
```

When `N8N_DRY_RUN=false`, the backend refuses to send unsigned backend -> n8n webhook calls. Both `N8N_BASE_URL` and `N8N_WEBHOOK_SECRET` are required; missing configuration records `n8n_not_configured` on the `ai_task` and the WR launch still succeeds.

Expected behavior:

```text
POST /api/imperium/weekly-review/launch
  -> creates ai_task
  -> stores prepared_payload
  -> signs and POSTs prepared_payload to n8n webhook when real outbound mode is configured
  -> n8n calls backend Qwen dry-run bridge
  -> n8n stores ai_result through backend callback
  -> n8n attaches ai_result to WR session
```

Idempotency:

- backend outbound key: `wr_n8n_trigger_{task_id}`;
- replaying the same WR launch request does not trigger n8n again;
- if n8n is down, WR launch remains successful and the error may be recorded on `ai_task.error_code`.

---

## Goal

Verify that n8n can call the backend through the internal webhook security layer.

This smoke test does not trigger business logic.

## Deployment Impact

Internal webhooks are authenticated by HMAC signature only:

- `X-Timestamp`
- `X-Signature`
- `Idempotency-Key`

The shared secret is still `INTERNAL_WEBHOOK_SECRET`, but it is used only to compute the HMAC.
Do not send the secret value as a request header.

Timestamp tolerance is now:

```text
60 seconds
```

n8n and the backend host clocks must be synchronized.

## Backend Endpoint

```http
POST /api/internal/webhook-test
```

n8n Docker-network URL:

```text
http://imperium-api:8000/api/internal/webhook-test
```

## Required Headers

```http
X-Timestamp: <unix_timestamp_seconds>
X-Signature: <hmac_sha256_signature>
Idempotency-Key: <unique_idempotency_key>
Content-Type: application/json
```

Do not send the shared secret as a header.

## Signature Algorithm

Use:

```text
HMAC-SHA256
```

Sign exactly:

```text
{timestamp}.{raw_body}
```

Where:

- `timestamp` is the exact value sent in `X-Timestamp`
- `raw_body` is the exact request body bytes sent to the backend
- the dot between timestamp and body is required
- the HMAC key is `INTERNAL_WEBHOOK_SECRET`

The backend accepts either:

```text
<hex_signature>
```

or:

```text
sha256=<hex_signature>
```

## n8n HTTP Request Node Configuration

Method:

```text
POST
```

URL:

```text
http://imperium-api:8000/api/internal/webhook-test
```

Authentication:

```text
None
```

Headers:

```text
X-Timestamp: {{$json.timestamp}}
X-Signature: {{$json.signature}}
Idempotency-Key: {{$json.idempotencyKey}}
Content-Type: application/json
```

Body:

```json
{
  "ping": true
}
```

Recommended node order:

```text
Manual Trigger
-> Function node: Prepare signed request
-> HTTP Request node: Call backend smoke test
```

## n8n Function Node Example

```javascript
const crypto = require("crypto");

const internalSecret = $env.INTERNAL_WEBHOOK_SECRET;

if (!internalSecret) {
  throw new Error("Missing INTERNAL_WEBHOOK_SECRET environment variable.");
}

const timestamp = Math.floor(Date.now() / 1000).toString();
const rawBody = JSON.stringify({ ping: true });
const message = `${timestamp}.${rawBody}`;

const signature = crypto
  .createHmac("sha256", internalSecret)
  .update(message)
  .digest("hex");

return [
  {
    json: {
      timestamp,
      signature,
      idempotencyKey: `n8n_smoke_${timestamp}`,
      rawBody,
      body: JSON.parse(rawBody)
    }
  }
];
```

Important:

The exact body sent by the HTTP Request node must match `rawBody`.

## Expected Backend Response

```json
{
  "status": "ok",
  "accepted": true,
  "idempotency_key": "n8n_smoke_1760000000"
}
```

Expected status:

```text
200 OK
```

## Patch 2C WR Mock Smoke Test

Patch 2C adds a mock-only WR endpoint for local contract testing.

This is not a real n8n workflow and does not call Qwen, Opus, GPT, Claude, Gemini, or any external AI.

Endpoint:

```http
POST /api/internal/weekly-review/{session_id}/mock-ai-summary
```

Docker-network URL format:

```text
http://imperium-api:8000/api/internal/weekly-review/{session_id}/mock-ai-summary
```

Required headers are the same HMAC-only internal headers:

```http
X-Timestamp: <unix_timestamp_seconds>
X-Signature: <hmac_sha256_signature>
Idempotency-Key: <unique_idempotency_key>
Content-Type: application/json
```

Example body:

```json
{
  "result_type": "weekly_report.summary",
  "result_payload": {
    "summary": "Mock initial weekly review summary for smoke testing only."
  },
  "model_used": "mock-qwen",
  "provider": "mock",
  "confidence": 0.8,
  "raw_payload": {}
}
```

Expected behavior:

- backend creates or reuses a mock `ai_result`;
- backend attaches it to the WR session as a proposal/message;
- session may move to `initial_summary_ready`;
- final report is not approved;
- pgvector memory is not written;
- `n8n_db` is not touched.

## Patch 2D WR Workflow Import Smoke Test

Patch 2D adds the first importable n8n workflow artifact:

```text
ops/n8n/workflows/wr_interactive_start_mock.json
```

Workflow name:

```text
IMPERIUM_WR_INTERACTIVE_START_MOCK
```

Purpose:

```text
Mock contract test for weekly_report.interactive.start
```

This workflow is mock-only. It does not call Qwen, Opus, GPT, Claude, Gemini, or any external AI provider.

### Required n8n Environment Variables

```text
IMPERIUM_API_BASE_URL=http://imperium-api:8000
INTERNAL_WEBHOOK_SECRET=<same HMAC secret used by backend internal callbacks>
```

Do not expose secret values in workflow JSON or logs.

### Import Steps

1. Open n8n.
2. Import workflow from file.
3. Select `ops/n8n/workflows/wr_interactive_start_mock.json`.
4. Confirm the workflow name is `IMPERIUM_WR_INTERACTIVE_START_MOCK`.
5. Ensure the n8n container has `IMPERIUM_API_BASE_URL` and `INTERNAL_WEBHOOK_SECRET`.
6. Activate or manually execute the webhook workflow for smoke testing only.

### Webhook Input Payload

Send the prepared payload from `ai_tasks.prepared_payload`:

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

### Backend Calls Performed By Workflow

First callback:

```http
POST {{ IMPERIUM_API_BASE_URL }}/api/internal/ai/tasks/{task_id}/result
```

Payload result type:

```text
weekly_report.summary
```

Second callback:

```http
POST {{ IMPERIUM_API_BASE_URL }}/api/internal/weekly-review/{session_id}/attach-ai-result
```

The second callback uses the `result_id` returned by the first callback.

Both calls are signed with HMAC over:

```text
{timestamp}.{raw_body}
```

Headers:

```http
X-Timestamp
X-Signature
Idempotency-Key
Content-Type: application/json
```

No plaintext shared secret header is sent.

### Expected Backend Result

- `ai_result` exists with `status = pending_validation`.
- WR session receives a proposal/message.
- WR session may become `initial_summary_ready`.
- Final report is not approved.
- pgvector memory is not written.
- Canonical WR finalization does not happen.

### Patch 2P-2T Verification Endpoints

After the WR launch and answer-integration smoke tests, use the backend read endpoints to verify popup state:

```http
GET /api/imperium/weekly-review/current
GET /api/imperium/weekly-review/{session_id}/conversation
GET /api/imperium/weekly-review/{session_id}/debug-status
```

Expected checks:

- `conversation.ui_state` reflects the current WR state;
- `conversation.allowed_actions` is conservative;
- `conversation.final_report_candidates` contains draft candidates newest-first;
- `initial_ai_result` and `final_ai_result` do not include `raw_payload`;
- `debug-status` may show `raw_payload_keys`, but never raw provider payload bodies;
- no endpoint approves, stores, writes memory, or writes pgvector automatically.

Draft action smoke endpoints:

```http
POST /api/imperium/weekly-review/{session_id}/draft/approve
POST /api/imperium/weekly-review/{session_id}/draft/reject
POST /api/imperium/weekly-review/{session_id}/draft/request-changes
POST /api/imperium/weekly-review/{session_id}/draft/store
```

All draft action POSTs require JWT and `Idempotency-Key`. Use a fresh key for each new action. Replaying the same key with the same body should return the original result without duplicate messages, tasks, reports, or n8n triggers.

Approval and storage are separate checks:

- `approved != stored`;
- approval sets `approved_at` and keeps `stored_at` empty;
- store is only allowed after approval and sets `stored_at`;
- store is a backend V1 persistence marker, not a pgvector write, not an `ai_memories` write, not an embedding job, and not an n8n/AI call;
- n8n must never approve or store the WR automatically.

Finalization read/export smoke endpoints:

```http
GET /api/imperium/weekly-review/history
GET /api/imperium/weekly-review/{session_id}/final-report
GET /api/imperium/weekly-review/final-reports/{report_id}
GET /api/imperium/weekly-review/final-reports/stored
GET /api/imperium/weekly-review/{session_id}/final-report/markdown
```

Expected checks:

- all require JWT;
- foreign sessions return 404;
- history supports `limit`, `offset`, optional `status`, and `stored_only`;
- final report selection prefers `stored > approved > draft > superseded`;
- markdown export is read-only and returns `text/markdown`;
- no response exposes `raw_payload`;
- exporting markdown does not write memory, pgvector, n8n, AI results, or approval/storage state.

Example curl checks:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/history?limit=20&offset=0"

curl -sS -H "Authorization: Bearer $TOKEN" \
  "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/history?stored_only=true"

curl -sS -H "Authorization: Bearer $TOKEN" \
  "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/$SESSION_ID/final-report"

curl -sS -H "Authorization: Bearer $TOKEN" \
  "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/final-reports/$REPORT_ID"

curl -sS -H "Authorization: Bearer $TOKEN" \
  "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/final-reports/stored?limit=20&offset=0"

curl -sS -H "Authorization: Bearer $TOKEN" \
  -H "Accept: text/markdown" \
  "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/$SESSION_ID/final-report/markdown"
```

Closed-session negative test after storage:

```bash
curl -i -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: wr-closed-negative-$(date +%s)" \
  -d '{"content":"This should be rejected","payload":{"source":"vps_smoke"}}' \
  "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/$SESSION_ID/answer"
```

Expected result: HTTP 409 with `Cannot modify a closed weekly review session.` A replay of the original successful store request with the same original `Idempotency-Key` should still return the cached stored report.

Memory candidate projection smoke checks:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/$SESSION_ID/memory-candidates"

curl -sS -H "Authorization: Bearer $TOKEN" \
  "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/final-reports/$REPORT_ID/memory-candidates"

curl -sS -H "Authorization: Bearer $TOKEN" \
  "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/memory-candidates/preview?limit=20&offset=0"
```

Expected checks:

- `storage_enabled` is `false`;
- response note says nothing has been written to memory;
- candidates are derived from stored WR report data or deterministic fallback fields;
- no response contains `raw_payload`;
- these reads do not write `ai_memories`, pgvector, embeddings, n8n, AI tasks, or approval/storage state.

Memory candidate decision smoke checks:

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: wr-mem-approve-$(date +%s)" \
  -d '{"reason":"Looks useful","payload":{"source":"vps_smoke"}}' \
  "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/final-reports/$REPORT_ID/memory-candidates/$CANDIDATE_ID/approve"

curl -sS -H "Authorization: Bearer $TOKEN" \
  "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/memory-candidates/decisions?limit=20&offset=0"

curl -sS -H "Authorization: Bearer $TOKEN" \
  "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/memory-candidates/preview?include_rejected=true"
```

Expected checks:

- decisions are accepted only for `approved` or `stored` reports;
- replay with the same `Idempotency-Key` returns the same decision;
- a different key for an already decided candidate returns 409;
- candidate read responses include `decision_status`;
- rejected candidates are hidden from preview by default unless `include_rejected=true`;
- approved or edited decisions still do not write `ai_memories`, pgvector, embeddings, n8n, AI tasks, or canonical memory.

Memory commit readiness smoke checks:

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/memory-candidates/commit-ready?limit=20&offset=0"

curl -sS -H "Authorization: Bearer $TOKEN" \
  "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/final-reports/$REPORT_ID/memory-candidates/commit-ready"

curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: wr-memory-commit-dry-run-$(date +%s)" \
  -d '{"decision_ids":["'"$DECISION_ID"'"],"payload":{"source":"vps_smoke"}}' \
  "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/memory-candidates/commit-dry-run"
```

Expected checks:

- commit-ready returns only `approved` and `edited` decisions;
- `readiness_status` is `ready` or `blocked`;
- blocked candidates include `readiness_reasons`;
- dry-run returns `storage_enabled=false`;
- dry-run response note says nothing was written to memory;
- replaying the same dry-run `Idempotency-Key` with the same body returns the cached response;
- changing the body with the same key returns 409;
- no `ai_memories`, pgvector, embedding, n8n, AI task, or canonical memory write happens.

### Patch 2U Revised Draft Checks

WR final report candidates are multi-version rows.

Expected revised draft flow:

1. n8n attaches `weekly_report.draft`.
2. Backend creates a final report candidate with `status = draft`.
3. User rejects the draft or requests changes.
4. Backend marks the previous candidate `status = superseded`.
5. n8n later attaches a new `weekly_report.draft`.
6. Backend creates a new final report candidate row with `status = draft`.

Smoke assertions:

- superseded candidates remain visible in `final_report_candidates`;
- newest candidates are returned first;
- only one active candidate exists at a time;
- attaching a different draft while an active draft exists returns conflict;
- reattaching the same AI result is idempotent;
- no draft attach approves, stores, writes memory, or writes pgvector.

### Patch 5A-5D Chatbot Flow Checks

The Weekly Review popup is now modeled as a backend-owned chatbot flow. n8n is not involved in ordinary user chat messages.

Smoke commands:

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: wr-chat-message-$(date +%s)" \
  -d '{"content":"J’ajoute un point sur mon énergie.","payload":{"source":"vps_smoke"}}' \
  "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/$SESSION_ID/chat/messages"

curl -sS "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/$SESSION_ID/conversation" \
  -H "Authorization: Bearer $TOKEN"

curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: wr-chat-confirm-$(date +%s)" \
  -d '{"content":"Non, tu peux préparer le brouillon.","payload":{"source":"vps_smoke"}}' \
  "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/$SESSION_ID/chat/confirm-no-more-input"
```

Expected checks:

- after initial summary, `ui_state=conversation_active`;
- allowed actions include `send_message` and `confirm_no_more_input`;
- `primary_action.action=send_message`;
- `secondary_actions` includes `confirm_no_more_input`;
- `chat_timeline` contains display-safe items only;
- `visible_ai_state.current_step` matches the state (`collecting_user_context`, `reviewing_final_draft`, `ready_to_store`, `closed`, or `waiting_for_ai`);
- no `raw_payload`, internal prompts, hidden reasoning, secrets, or debug blobs appear in the conversation response;
- chat messages create a user `chat_message` and a deterministic Qwen dry-run `assistant_followup`;
- the assistant follow-up ends with `As-tu autre chose à ajouter avant que je prépare le rapport final ?`;
- no final report candidate is created by `/chat/messages`;
- `/chat/confirm-no-more-input` creates a draft candidate and moves to `draft_ready`;
- when the session is `draft_ready` with an active `draft`, `primary_action.action=approve_draft` and enabled chat/confirm actions are absent;
- when the session is `approved` with an active approved report, `primary_action.action=store_final_report`;
- stored or superseded-only report states may display report summaries but do not expose enabled mutation actions;
- confirmation without any prior user input returns 409;
- chat while `draft_ready` returns 409 until `/draft/request-changes` is used;
- no automatic approval, storage, memory write, pgvector write, embedding, n8n AI Agent, or real AI call occurs.

### Patch 5K-5R Memory Table and Explicit Commit Check

The backend now defines canonical text memory storage and an explicit user-triggered commit endpoint. This still does not generate embeddings and does not write pgvector values.

```bash
curl -sS "$IMPERIUM_API_BASE_URL/api/imperium/memories/schema" \
  -H "Authorization: Bearer $TOKEN"
```

Expected checks:

- response has `storage_enabled=true`;
- response has `embeddings_enabled=false`;
- response has `pgvector_enabled=false`;
- supported kinds/scopes are listed;
- no n8n workflow writes memory rows;
- no pgvector or embedding write exists.

Commit is manual and JWT-scoped:

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: wr-memory-commit-$(date +%s)" \
  -d '{"decision_ids":["<approved-or-edited-decision-id>"],"payload":{"source":"vps_smoke"}}' \
  "$IMPERIUM_API_BASE_URL/api/imperium/weekly-review/memory-candidates/commit"
```

Expected commit checks:

- approved/edited decisions create `ai_memories` rows;
- rejected, missing, foreign, undecided, or invalid candidates are blocked;
- duplicate `source_decision_id` returns `already_committed`;
- response note says no embeddings were generated.

Read memories:

```bash
curl -sS "$IMPERIUM_API_BASE_URL/api/imperium/memories?status=active" \
  -H "Authorization: Bearer $TOKEN"
```

Filtered index smoke checks:

```bash
curl -sS "$IMPERIUM_API_BASE_URL/api/imperium/memories?status=active&kind=weekly_commitment&limit=10&offset=0&q=semaine" \
  -H "Authorization: Bearer $TOKEN"
```

Archive a memory without deleting it:

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: memory-archive-$(date +%s)" \
  -d '{"reason":"VPS smoke archive","payload":{"source":"vps_smoke"}}' \
  "$IMPERIUM_API_BASE_URL/api/imperium/memories/<memory-id>/archive"
```

Supersede an active memory with a revised text row:

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: memory-supersede-$(date +%s)" \
  -d '{"content":"Revised memory text from VPS smoke.","reason":"Manual correction","payload":{"source":"vps_smoke"}}' \
  "$IMPERIUM_API_BASE_URL/api/imperium/memories/<memory-id>/supersede"
```

Expected lifecycle checks:

- archive and supersede require JWT plus `Idempotency-Key`;
- archive changes only `status`, `archived_at`, and `updated_at`;
- supersede creates one new active memory and marks the previous row `superseded`;
- archived or superseded memories reject new lifecycle mutations with 409 unless it is exact idempotent replay;
- default memory index remains active-only;
- `status=archived`, `status=superseded`, or `status=all` must be explicit;
- simple `q` search is database `ilike`, not vector search;
- no embeddings, pgvector writes, direct n8n DB writes, or n8n AI Agent are involved.

### Patch 2D Troubleshooting

Stale timestamp:

- n8n and backend clocks are not synchronized;
- generate timestamp immediately before each HTTP node.

Body mismatch:

- the raw body signed in Code node differs from the HTTP Request raw body;
- use the exact `aiCallbackRawBody` or `attachRawBody` field as the request body.

Missing env var:

- set `IMPERIUM_API_BASE_URL`;
- set `INTERNAL_WEBHOOK_SECRET`.
- if your n8n deployment blocks Node built-ins in Code nodes, allow `crypto` for this mock workflow according to your n8n runtime policy.

Wrong Docker URL:

- from n8n Docker to backend Docker, use `http://imperium-api:8000`;
- from host machine, use the public or localhost URL depending deployment.

Invalid Idempotency-Key replay:

- reusing the same key with a different body returns conflict;
- this is expected safety behavior.

Callback `422` invalid `result_type`:

- ensure result type is exactly `weekly_report.summary`.

## Common Errors

### Missing Header

Likely causes:

- `X-Signature` missing
- `X-Timestamp` missing
- `Idempotency-Key` missing

### Bad Signature

Likely causes:

- wrong `INTERNAL_WEBHOOK_SECRET`
- body used for signing differs from body sent
- timestamp in signature differs from `X-Timestamp`
- missing dot between timestamp and raw body

### Stale Timestamp

Cause:

`X-Timestamp` is outside the 60-second tolerance.

Fix:

Generate `X-Timestamp` immediately before the HTTP Request node runs.

### Body Mismatch

Likely causes:

- signed compact JSON but n8n sent pretty JSON
- n8n re-serialized the object
- signed body includes a newline but sent body does not

Fix:

Use the exact raw body string for both signing and sending.

## Non-Negotiable

n8n must call backend APIs.
n8n must not write canonical app data directly to PostgreSQL.

## Audit Patch 1 Applied

The 2026-05-02 backend audit (Patch 1) added two operational guards that
affect smoke testing:

- The smoke endpoint
  `/api/internal/weekly-review/{session_id}/mock-ai-summary` is now 404 when
  `settings.environment` is not `"local"` or `"test"`. Run the smoke against
  a backend started with `ENVIRONMENT=local` (or `ENVIRONMENT=test`) — the
  HMAC layer will still verify the request, but the env guard runs first in
  any other environment and short-circuits to `404 Not found.`
- `N8N_WEBHOOK_SECRET`, whenever configured, is now validated at startup with
  the same placeholder/length rules used for
  `JWT_SECRET_KEY` and `INTERNAL_WEBHOOK_SECRET`. If the secret is left as a
  placeholder (`local-dev-...`, `change-me`, ...) or shorter than 32
  characters, the API refuses to boot. Leaving `N8N_WEBHOOK_SECRET` unset is
  still allowed while n8n integration is optional. Local/test smoke runs should
  either omit this variable or use a real non-placeholder test secret.

## Audit Closure Patch 6E-6H Smoke Notes

Weekly Review public message creation is user-only:

- the app may send only user-originated messages;
- assistant/system/backend messages are created by backend services only;
- attempts to send `role=qwen`, `role=system`, `role=backend`, or assistant
  message types to public WR message endpoints should return validation errors.

Debug/status behavior:

- `/api/imperium/weekly-review/{session_id}/debug-status` may show richer
  diagnostic data in `local` or `test`;
- in staging/production-like environments it is sanitized and must not expose
  provider/model identifiers, raw payload keys, raw result payloads, internal
  prompts, or internal error strings;
- `/api/health` remains unchanged.

Append-only DB verification:

- optional PostgreSQL tests cover UPDATE, DELETE, and TRUNCATE rejection on
  `events` and `auth_events`;
- run them by setting `IMPERIUM_TEST_DATABASE_URL` to a migrated PostgreSQL
  test database before running pytest;
- without that env var, these tests skip cleanly.

## Patch 6I-6L Decision Framework Smoke Checks

The Decision Framework foundation is backend-only and does not involve n8n.

Schema/readiness:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "$IMPERIUM_API_BASE_URL/api/imperium/decision-framework/schema"
```

Expected:

- `scoring_enabled=true`
- `monthly_planning_enabled=false`
- `daily_adaptation_enabled=false`
- `real_ai_enabled=false`
- `embeddings_enabled=false`

Priority hierarchy:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "$IMPERIUM_API_BASE_URL/api/imperium/decision-framework/priorities"
```

Reorder priorities:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: df-priorities-$(date +%s)" \
  -d '{"domains":["religious","business","finance","health"]}' \
  "$IMPERIUM_API_BASE_URL/api/imperium/decision-framework/priorities"
```

Score preview:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"domain":"business","impact":"important","mission_type":"work_income","dependency":"some","recurrence":"weekly"}' \
  "$IMPERIUM_API_BASE_URL/api/imperium/decision-framework/score-preview"
```

Expected:

- `storage_enabled=false`;
- UI fields include `score_status`, `display_summary`, `breakdown`,
  `priority_bucket`, `missing_fields`, and `warnings`;
- public explanation keys are `deadline_points`, `impact_points`,
  `mission_type_points`, `dependency_points`, and `recurrence_points`;
- `effort` and `alignment` are accepted only as temporary input aliases and
  should produce sanitized alias warnings;
- public responses do not expose `domain_coefficient`, `weighted_score`,
  `final_weighted_score`, or `position_to_coefficient`;
- no `ai_task` is created;
- no n8n webhook is called;
- no mission is modified;
- no pgvector or embedding write happens.

Patch 7 hardening notes:

- `score-preview` is not an n8n smoke path and must not trigger n8n;
- user priorities influence `domain_position` and the internal coefficient, but
  the public API exposes only `priority_bucket`, not raw coefficient math;
- ambiguous fields such as `importance`, `urgency`, and `risk` should return
  validation errors rather than being interpreted as scoring signals;
- payload bodies are not echoed in the response, and unsafe payload keys are
  reported only through sanitized warnings.

Patch 7F-1 mission structure smoke check:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: mission-df-$(date +%s)" \
  -d '{"title":"Prepare tax file","domain":"finance","priority_level":6,"mission_type_category":"cat_b"}' \
  "$IMPERIUM_API_BASE_URL/api/imperium/missions/start"
```

Expected:

- the response echoes `domain`, `priority_level`, and
  `mission_type_category`;
- these fields are nullable and can be omitted by legacy callers;
- no `imperium_mission_scores` row is created by mission start in Patch 7F-1;
- `backlog` is accepted at the database level for future backlog work, but no
  full backlog engine is implemented yet;
- no n8n workflow, AI call, pgvector write, embedding, memory write, or
  coefficient exposure is involved.

Patch 7F-2 controlled mission score storage smoke check:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: mission-score-$(date +%s)" \
  -d '{
    "title":"Prepare tax file",
    "domain":"finance",
    "mission_type_category":"cat_b",
    "deadline_at":"2026-05-20T12:00:00Z",
    "impact":"important",
    "dependency":"some",
    "recurrence":"monthly"
  }' \
  "$IMPERIUM_API_BASE_URL/api/imperium/missions/start"
```

Expected:

- the response may include `score_created=true`;
- `decision_score` contains only `intrinsic_score`, `priority_bucket`,
  `score_status`, `missing_fields`, and `source`;
- the response must not contain `domain_coefficient`, `weighted_score`, or
  `final_weighted_score`;
- replaying the same `Idempotency-Key` must not create a second
  `imperium_mission_scores` row.

Read the safe score surface:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "$IMPERIUM_API_BASE_URL/api/imperium/missions/$MISSION_ID/decision-score"
```

Expected:

- returns the current user's score only;
- exposes canonical explanation keys but not internal coefficient math;
- still no n8n workflow, AI call, pgvector write, embedding, or memory write.

Patch 7G priority reconciliation smoke checks:

Read canonical Decision Framework priorities:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "$IMPERIUM_API_BASE_URL/api/imperium/decision-framework/priorities"
```

Update canonical order:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: df-priorities-$(date +%s)" \
  -d '{"domains":["health","finance","business","religious"]}' \
  "$IMPERIUM_API_BASE_URL/api/imperium/decision-framework/priorities"
```

Legacy compatibility read:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "$IMPERIUM_API_BASE_URL/api/imperium/priorities"
```

Expected:

- legacy read returns the same order as Decision Framework priorities;
- legacy read includes `deprecated=true`, `legacy=true`,
  `canonical_source=imperium_user_priorities`, and
  `superseded_by=/api/imperium/decision-framework/priorities`;
- `importance_score` is `null` because raw coefficients remain internal;
- no `imperium_priority_rules` row is created or updated.

Legacy write negative check:

```bash
curl -i -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: legacy-priority-write-$(date +%s)" \
  -d '{"priorities":[{"priority_key":"work","label":"Work","rank_order":1}]}' \
  "$IMPERIUM_API_BASE_URL/api/imperium/priorities"
```

Expected:

- HTTP `410 Gone`;
- response points to `/api/imperium/decision-framework/priorities`;
- dashboard and daily plan priority context reflect the Decision Framework
  order;
- no n8n workflow, AI call, pgvector write, embedding, memory write, or
  public coefficient exposure is involved.

## Patch 8A - Mission Backlog Foundation Smoke Checks

Patch 8A backlog endpoints are backend-only. They do not require an n8n
workflow, n8n AI Agent, n8n database access, AI provider call, pgvector write,
embedding generation, memory commit, calendar consumption, or automatic
replanning.

Create a backlog mission:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: backlog-create-$(date +%s)" \
  -d '{"title":"Prepare invoice","domain":"business","priority_level":4,"mission_type_category":"cat_e"}' \
  "$IMPERIUM_API_BASE_URL/api/imperium/missions/backlog"
```

List backlog missions:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "$IMPERIUM_API_BASE_URL/api/imperium/missions/backlog?limit=20&offset=0&domain=business&priority_level=4"
```

Promote a backlog mission:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: backlog-promote-$(date +%s)" \
  "$IMPERIUM_API_BASE_URL/api/imperium/missions/backlog/$MISSION_ID/promote"
```

Expected:

- POST routes require `Idempotency-Key`;
- all routes are JWT-scoped to the current user;
- creation and promotion remain deterministic backend writes only;
- no monthly or daily planning is generated;
- no automatic replanning is triggered;
- calendar constraints are not consumed yet;
- public score output may include `intrinsic_score`, `priority_bucket`,
  `score_status`, `missing_fields`, and `source`;
- public output must not include `domain_coefficient`, `weighted_score`,
  `final_weighted_score`, or `position_to_coefficient`.
