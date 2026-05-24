# 06 - n8n Workflows

## Purpose

This document defines the responsibility boundary between the backend and n8n.

n8n is the workflow engine.

The backend is the source of truth and the gatekeeper.

## Core Responsibility Boundary

The backend owns:
- database invariants
- validation
- auth checks
- idempotency
- business constraints
- event storage
- mission uniqueness
- day session uniqueness
- wallet/accounting consistency
- privacy gates

n8n owns:
- workflow orchestration
- scheduled jobs
- external API calls
- AI workflow coordination
- notifications
- long-running automations

## Database Write Rule

For V1, n8n must write through backend APIs, not directly to PostgreSQL.

Allowed:
- n8n calls backend endpoints
- backend validates and writes to PostgreSQL
- backend emits/stores events
- backend returns structured results to n8n

Forbidden in V1:
- n8n directly inserting missions
- n8n directly modifying wallet balances
- n8n directly changing mission status
- n8n directly writing user priority rules
- n8n directly marking religious actions complete
- n8n directly updating pgvector memory without backend approval

Exception:
- n8n may write to its own internal execution logs
- n8n may store temporary workflow state in n8n itself

Canonical app data must go through backend APIs.

## Why This Rule Exists

This prevents:
- duplicated logic
- broken database constraints
- inconsistent mission state
- duplicate transactions
- privacy leaks
- n8n/backend drift

## Standard Workflow Pattern

```text
Android app
-> backend
-> auth check
-> validation
-> idempotency check
-> PostgreSQL event storage
-> canonical table update if needed
-> n8n workflow trigger or event exposure
-> n8n orchestration
-> backend API call for any canonical write
-> backend stores final event/result
```

Step-by-step:

1. Android app sends request to backend.
2. Backend authenticates, validates, and applies idempotency.
3. Backend stores the event in PostgreSQL.
4. Backend updates canonical tables if needed.
5. Backend triggers n8n workflow or exposes event for n8n.
6. n8n performs orchestration.
7. n8n calls backend API for any canonical write.
8. Backend stores final event/result.

## Event Subscription Rule

n8n subscribes to canonical dotted event names.

Examples:
- `mission.completed`
- `mission.failed`
- `day.finished`
- `transaction.created`
- `sadaqa.recorded`
- `ai.route.requested`
- `vector.session.started`

n8n workflow names may use snake_case.

Example mapping:

| canonical event_type | n8n workflow name |
|---|---|
| `mission.completed` | `mission_completed_workflow` |
| `mission.failed` | `mission_failed_analysis_workflow` |
| `day.finished` | `day_finished_review_workflow` |
| `transaction.created` | `transaction_created_analysis_workflow` |
| `sadaqa.recorded` | `sadaqa_recorded_workflow` |
| `ai.route.requested` | `ai_route_requested_workflow` |
| `vector.session.started` | `vector_session_started_workflow` |

The event type remains dotted. The n8n workflow name may use snake_case.

## Example - Mission Failed

Flow:

1. Imperium sends `mission.failed`.
2. Backend validates mission state.
3. Backend applies idempotency.
4. Backend stores the event.
5. Backend updates mission status.
6. Backend triggers n8n `mission_failed_analysis_workflow`.
7. n8n analyzes patterns and asks AI if needed.
8. n8n calls backend endpoint to store recommendation.
9. Backend stores recommendation and optional memory.

Forbidden:
- n8n must not directly update the mission row.
- n8n must not directly create the next mission.
- n8n must not directly write pgvector memory without backend approval.

## Example - Transaction Created

Flow:

1. The Vault sends `transaction.created`.
2. Backend validates wallet type, amount, date, source app, and idempotency.
3. Backend stores the event.
4. Backend creates the transaction.
5. Backend recalculates or schedules recalculation for wallet totals, pressure, and objectives.
6. Backend triggers n8n `transaction_created_analysis_workflow`.
7. n8n may request AI explanation or downstream notification.
8. n8n calls backend API for any final canonical write.

Forbidden:
- n8n must not directly insert a transaction.
- n8n must not directly modify wallet balances.

## Example - Ghusl Required

Flow:

1. The Path sends `ghusl.required.activated`.
2. Backend verifies the event is user-initiated.
3. Backend stores the event.
4. Backend stores the religious constraint.
5. Backend triggers n8n `ghusl_required_activated_workflow`.
6. n8n coordinates prayer timing, travel context, and mission generation request.
7. n8n calls backend API to request canonical Imperium mission creation.
8. Backend enforces one-current-mission rules and stores the result.

Forbidden:
- n8n must not infer ghusl required.
- n8n must not mark ghusl complete.
- n8n must not directly insert an Imperium mission.

## Webhook Security

n8n webhooks must not be open/public without protection.

Every internal webhook must use:
- request signature header: `X-Signature`
- timestamp header: `X-Timestamp`
- idempotency key: `Idempotency-Key` or canonical payload `idempotency_key`
- timestamp/replay protection with 60 second tolerance

Invalid webhook protection must reject the request before workflow execution.

Signature algorithm:
- HMAC-SHA256 over `{timestamp}.{raw_body}` using `INTERNAL_WEBHOOK_SECRET`

Replay window:
- 60 seconds

All webhook calls require an idempotency key.

Secret rotation policy: TODO.

## Backend APIs Called by n8n

n8n may call backend APIs for:
- storing AI routing results
- storing AI recommendations
- requesting mission generation
- requesting replanning result storage
- requesting memory write approval
- storing notification delivery result
- recording workflow completion/failure

Exact endpoint list: TODO.

## Workflow Spec Template

Every workflow must eventually define:
- canonical trigger event
- workflow name
- input schema
- output schema
- backend APIs called
- external APIs called
- AI models called
- PostgreSQL canonical writes requested through backend
- pgvector writes requested through backend
- idempotency behavior
- retry policy
- timeout policy
- failure behavior
- privacy gate requirements
- logs emitted

## Non-Negotiable Rule

n8n is not the database owner.

n8n is the workflow engine.

The backend is the gatekeeper.
