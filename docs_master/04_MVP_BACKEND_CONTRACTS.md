# 04 - MVP Backend Contracts

## Purpose

This document defines the first backend contracts for the MVP.

It is a developer-ready contract layer, not production code. Future backend work should implement these contracts or explicitly update this document first.

The contracts preserve the product rules:
- one user only
- apps are interfaces
- n8n orchestrates workflows
- PostgreSQL stores structured truth
- pgvector stores semantic memory
- only one active mission exists at a time
- user confirmation matters
- Vector never automates Bolt
- backend owns canonical database writes and invariants
- n8n writes canonical app data through backend APIs in V1

## API Conventions

## V1 Implementation Stack

Final implementation decisions:
- `backend_framework`: FastAPI
- `language`: Python
- `orm`: SQLAlchemy
- `migration_tool`: Alembic
- `database`: PostgreSQL
- `vector_extension`: pgvector
- `id_format`: UUID

Base URL:

```text
V1 local/dev default: http://localhost:8000
Production/deployment URL: TODO
```

Common request fields:

```json
{
  "request_id": "req_123",
  "user_id": "user_main",
  "source_app": "imperium",
  "client_timestamp": "2026-04-25T09:15:00+02:00",
  "timezone": "Europe/Paris"
}
```

Common response fields:

```json
{
  "request_id": "req_123",
  "status": "ok",
  "data": {},
  "warnings": [],
  "next_actions": []
}
```

## Canonical Event Envelope

All important actions in the ecosystem must be emitted as events.

The event system is the backbone between:
- Android apps
- backend
- PostgreSQL
- n8n
- AI router
- pgvector memory

### Canonical event naming

Use dotted event names only for canonical event types.

Examples:
- `mission.created`
- `mission.completed`
- `mission.failed`
- `day.started`
- `day.finished`
- `transaction.created`
- `sadaqa.recorded`
- `voice.transcribed`
- `ai.route.requested`
- `vector.session.started`

Do not use snake_case event names for canonical event types.

Snake_case is allowed for implementation artifacts such as n8n workflow names, function names, or internal job names, but not for `event_type`.

### Source app enum

Canonical `source_app` values:
- `imperium`
- `vector`
- `vault`
- `pulse`
- `path`
- `core`
- `external`
- `n8n`
- `ai_router`

Display names may be human-readable, but code must use these enum values.

### Envelope structure

Every event must use this structure:

```json
{
  "event_id": "evt_01HXYZ...",
  "event_type": "mission.completed",
  "schema_version": "1.0",
  "occurred_at": "2026-04-25T07:30:00Z",
  "received_at": "2026-04-25T07:30:02Z",
  "source_app": "imperium",
  "device_id": "device_pixel_7_pro",
  "user_id": "user_main",
  "idempotency_key": "mission_123_completed_2026-04-25T07:30:00Z",
  "correlation_id": "corr_01HXYZ...",
  "causation_id": "evt_previous_or_null",
  "privacy_level": "medium",
  "payload": {}
}
```

Required fields:
- `event_id`
- `event_type`
- `schema_version`
- `occurred_at`
- `received_at`
- `source_app`
- `device_id`
- `user_id`
- `idempotency_key`
- `correlation_id`
- `causation_id`
- `privacy_level`
- `payload`

The envelope is stable. The payload changes by event type.

Payload schemas must be defined per event in backend contracts.

### Idempotency rule

Every mutating action must include an `idempotency_key`.

Required for:
- creating mission
- completing mission
- failing mission
- finishing day
- creating transaction
- recording sadaqa
- uploading media
- triggering OCR
- transcribing audio
- starting VTC session
- ending VTC session
- updating priority rules

If the same idempotency key is received twice:
- do not duplicate the action
- return the original result
- log the duplicate attempt

Mobile apps may retry requests. The backend must guarantee:
- no duplicate missions
- no duplicate transactions
- no duplicate sadaqa records
- no duplicate day finish events
- no duplicate AI workflow triggers

### Correlation and causation

Use:
- `correlation_id` to group a full user flow
- `causation_id` to identify which previous event caused the current event

Example flow:

```text
user sends voice command
-> audio uploaded
-> audio transcribed
-> intent detected
-> transaction created
```

All events in that flow share the same `correlation_id`.

Each event points to the previous event with `causation_id`.

### Event storage

All accepted events must be stored in PostgreSQL in an `events` table.

Events are append-only.

Do not delete events during normal app usage.

The database must enforce uniqueness for:
- `event_id`
- `idempotency_key`

Exact table schema belongs in `05_DATABASE_SCHEMA.md`.

Authentication:

```text
One-user authentication model.
```

The product is one-user only, but API authentication is mandatory.

V1 must not implement SaaS-style multi-user complexity. There is one canonical user record.

Supported access methods:
- email + password
- master access key / secret phrase

Trusted devices must be registered before normal use.

Examples:
- Pixel 7 Pro
- Galaxy Tab
- laptop

Each trusted device receives:
- `device_id`
- short-lived JWT access token
- longer-lived refresh token

Refresh tokens are device-bound. Devices can be revoked.

Minimum auth API surface:

| method | endpoint | purpose | notes |
|---|---|---|---|
| POST | `/api/auth/login` | Login with email/password or master access key | Returns access token, refresh token, device registration state |
| POST | `/api/auth/refresh` | Exchange device-bound refresh token for new access token | Must validate device is still trusted |
| POST | `/api/auth/devices/register` | Register a trusted device | Requires valid login/master access |
| GET | `/api/auth/devices` | List trusted devices | One-user device management |
| POST | `/api/auth/devices/{device_id}/revoke` | Revoke a trusted device | Invalidates device refresh token |
| POST | `/api/auth/logout` | Revoke current refresh token | Device-specific logout |

Access tokens:
- JWT
- TTL: 15 minutes
- sent with API requests

## Mission API Contract Consolidation

The mission module is user-scoped through `CurrentUserDep` on every route.
Read-only mission routes do not require `Idempotency-Key`.
Write mission routes require `Idempotency-Key`.

Patch 8A through 8H mission routes must not call AI, n8n, pgvector, embeddings,
memory commit, or calendar replanning.
No AI. No n8n. No pgvector writes. No embeddings. No memory commit. No calendar replanning.

| method | endpoint | objective | Idempotency-Key | access scope | mode | public safe fields | main errors | allowed / forbidden side effects |
|---|---|---|---|---|---|---|---|---|
| POST | `/api/imperium/missions/start` | Create the single active mission directly from user input. | Required | `CurrentUserDep` | write | `mission`, `event_id`, `idempotency_key`, `status`, `score_created`, safe `decision_score` summary | `400`, `409`, `422` | Allowed: create active mission, event, idempotency record, stored decision-score summary. Forbidden: creating a second active mission, AI, n8n, pgvector, embeddings, memory commit, calendar replanning. |
| POST | `/api/imperium/missions/backlog` | Create a backlog mission from user input. | Required | `CurrentUserDep` | write | `mission`, `event_id`, `idempotency_key`, `status`, `score_created`, safe `decision_score` summary | `400`, `409`, `422` | Allowed: create mission, event, idempotency record, stored decision-score summary. Forbidden: AI, n8n, pgvector, embeddings, memory commit, calendar replanning. |
| GET | `/api/imperium/missions/backlog` | List the current user's backlog missions. | Not required | `CurrentUserDep` | read-only | `items`, `count`, `ordering` | `200`, `401`, `422` | Allowed: read stored backlog rows only. Forbidden: writes of any kind, AI, n8n, pgvector, embeddings, memory commit, calendar replanning. |
| GET | `/api/imperium/missions/backlog/decision-preview` | Return a deterministic backend preview of the recommended backlog mission. | Not required | `CurrentUserDep` | read-only | `recommended_mission_id`, `candidate_count`, `candidates`, `safe_explanation` | `200`, `401`, `422` | Allowed: read stored backlog rows and stored score rows only. Forbidden: AI calls, n8n, pgvector, embeddings, memory commit, calendar replanning. |
| POST | `/api/imperium/missions/backlog/{mission_id}/promote` | Promote one backlog mission to the single active mission. | Required | `CurrentUserDep` | write | `mission`, `promotion_summary`, `event_id`, `idempotency_key`, `status`, safe `decision_score` summary | `400`, `404`, `409`, `422` | Allowed: update mission state, create event, persist idempotency record. Forbidden: AI, n8n, pgvector, embeddings, memory commit, calendar replanning. |
| GET | `/api/imperium/missions/current` | Read the current active mission directly. | Not required | `CurrentUserDep` | read-only | mission safe public fields | `200`, `404` | Allowed: read only. Forbidden: writes, AI, n8n, pgvector, embeddings, memory commit, calendar replanning. |
| GET | `/api/imperium/missions/active` | Read the single active mission for the current user. | Not required | `CurrentUserDep` | read-only | `mission`, `safe_explanation` | `200`, `404`, `409` | Allowed: read only. Forbidden: writes, AI, n8n, pgvector, embeddings, memory commit, calendar replanning. |
| POST | `/api/imperium/missions/{mission_id}/complete` | Complete the active mission or mark it failed/abandoned. | Required | `CurrentUserDep` | write | `mission`, `completion_summary` | `400`, `404`, `409`, `422` | Allowed: update mission state, create `mission.completed`, `mission.failed`, or `mission.abandoned` event, persist idempotency record. Forbidden: AI, n8n, pgvector, embeddings, memory commit, calendar replanning. |
| POST | `/api/imperium/missions/{mission_id}/fail` | Mark the active mission failed with user-reported reason/signals. | Required | `CurrentUserDep` | write | `mission`, `event_id`, `idempotency_key`, `status` | `400`, `404`, `409`, `422` | Allowed: update mission state, create `mission.failed` event, persist idempotency record. Forbidden: AI judgement, n8n, pgvector, embeddings, memory commit, calendar replanning. |
| GET | `/api/imperium/missions/history` | Read historical missions for the current user. | Not required | `CurrentUserDep` | read-only | `items`, `count`, `limit`, `offset`, `safe_explanation` | `200`, `401`, `422` | Allowed: read only. Forbidden: writes, AI, n8n, pgvector, embeddings, memory commit, calendar replanning. |
| GET | `/api/imperium/missions/recent` | Read recent missions for the current user. | Not required | `CurrentUserDep` | read-only | list of mission safe public fields | `200`, `401`, `422` | Allowed: read only. Forbidden: writes, AI, n8n, pgvector, embeddings, memory commit, calendar replanning. |
| GET | `/api/imperium/missions/{mission_id}` | Read one mission detail record. | Not required | `CurrentUserDep` | read-only | `mission`, `safe_explanation` | `200`, `404` | Allowed: read only. Forbidden: writes, AI, n8n, pgvector, embeddings, memory commit, calendar replanning. |
| GET | `/api/imperium/missions/{mission_id}/decision-score` | Read the safe public decision-score view for one mission. | Not required | `CurrentUserDep` | read-only | `mission_id`, `status`, `priority_level`, `priority_bucket`, `score_summary`, `safe_explanation` | `200`, `404` | Allowed: read only, deterministic summary from stored data. Forbidden: AI, n8n, pgvector, embeddings, memory commit, calendar replanning. |

Public mission score summaries must stay safe:

- they do not expose `weighted_score`
- they do not expose `domain_coefficient`
- they do not expose the internal formula
- they do not expose client-supplied score fields
- they do not use AI as a hidden scorer
- they do not use n8n as a hidden scorer

Refresh tokens:
- TTL: 30 days
- device-bound
- revocable
- never accepted from revoked devices
- stored hashed in the database, never stored raw

Master access key / secret phrase:
- allowed for recovery/admin access
- must be hashed in the database
- must never be stored raw
- rotation and emergency recovery ceremony: TODO

Refresh token hashing algorithm and master key rotation ceremony: TODO.

## Main API Endpoints

This table is a high-level index only. The mission contract table above is
canonical for Imperium mission behavior.

### Core

| method | endpoint | purpose | emitted event |
|---|---|---|---|
| GET | `/api/health` | Health check | none |
| POST | `/api/events` | Generic app event ingestion | `event.ingested` |
| POST | `/api/ai/route` | Route a request to model/workflow | `ai.route.requested` |
| POST | `/api/files/upload` | Upload Feed IA docs, receipts, screenshots, audio | `file.uploaded` |
| GET | `/api/apps/{app}/state` | Read app state summary | optional |

### Imperium

| method | endpoint | purpose | emitted event |
|---|---|---|---|
| GET | `/api/imperium/dashboard` | Current mission, day session, advice, weekly review status | `imperium.dashboard.requested` |
| POST | `/api/imperium/day-session/start` | Start day session | `day.started` |
| POST | `/api/imperium/day-session/end` | End active day session | `day.finished` |
| POST | `/api/imperium/missions/start` | Start direct active mission | `mission.started` |
| GET | `/api/imperium/missions/current` | Read current active mission | none |
| GET | `/api/imperium/missions/recent` | Read recent missions | none |
| POST | `/api/imperium/missions/{mission_id}/complete` | Complete mission or mark failed/abandoned | `mission.completed`, `mission.failed`, or `mission.abandoned` |
| POST | `/api/imperium/missions/{mission_id}/fail` | Mark mission failed with reason/signals | `mission.failed` |
| GET | `/api/imperium/missions/{mission_id}/decision-score` | Read safe deterministic mission decision summary; no AI, no n8n, no writes | none |
| POST | `/api/imperium/replan` | Explicit replanning request | `replan.requested` |
| POST | `/api/imperium/projects` | Create/update project | `project.changed` |
| POST | `/api/imperium/projects/{project_id}/validate-completion` | Explicit project completion | `project.completion.validated` |
| POST | `/api/imperium/routines` | Create/update routine | `routine.changed` |
| POST | `/api/imperium/priorities` | Legacy priority write disabled; use `/api/imperium/decision-framework/priorities` | none; returns `410 Gone` |
| POST | `/api/imperium/weekly-review/start` | Start weekly review | `weekly.review.started` |
| POST | `/api/imperium/weekly-review/{review_id}/answer` | Store review answer | `weekly.review.answered` |
| POST | `/api/imperium/weekly-review/{review_id}/complete` | Complete after final validation | `weekly.review.completed` |

### The Vault

| method | endpoint | purpose | emitted event |
|---|---|---|---|
| GET | `/api/vault/dashboard` | Wallets, pressure, objectives, upcoming expenses | `vault.dashboard.requested` |
| POST | `/api/vault/transactions` | Create gain or expense | `transaction.created` |
| PATCH | `/api/vault/transactions/{transaction_id}` | Edit transaction | `transaction.updated` |
| POST | `/api/vault/upcoming-expenses` | Create upcoming expense | `upcoming.expense.created` |
| PATCH | `/api/vault/upcoming-expenses/{expense_id}` | Edit upcoming expense | `upcoming.expense.updated` |
| POST | `/api/vault/scan-ticket` | Receipt image OCR flow | `receipt.ocr.requested` |
| POST | `/api/vault/objectives/recalculate` | Recalculate daily targets | `vault.objectives.recalculate.requested` |

### Vector

| method | endpoint | purpose | emitted event |
|---|---|---|---|
| POST | `/api/vector/session/start` | Start VTC session | `vector.session.started` |
| POST | `/api/vector/session/end` | End VTC session and store result | `vector.session.completed` |
| POST | `/api/vector/ride-offer/analyze` | Analyze ride offer screenshot or structured offer | `vector.ride.offer.detected` |
| POST | `/api/vector/ride-offer/{offer_id}/user-action` | Store accepted/refused/missed action | `vector.ride.action.recorded` |
| POST | `/api/vector/recommendation-feedback` | Store bad/good recommendation feedback | `vector.recommendation.feedback.recorded` |
| POST | `/api/vector/fuel/low` | User pressed low fuel trigger | `vector.low.fuel.triggered` |
| POST | `/api/vector/scheduled-rides` | Create/update scheduled ride | `scheduled.ride.changed` |

Vector endpoint boundary:

```text
No endpoint may auto-click, auto-accept, auto-refuse, or automate Bolt.
```

### Pulse

| method | endpoint | purpose | emitted event |
|---|---|---|---|
| GET | `/api/pulse/dashboard` | Biological profile, health score, workout/nutrition summary | `pulse.dashboard.requested` |
| POST | `/api/pulse/biological-profile/correction` | User correction to biological truth | `biological.profile.corrected` |
| POST | `/api/pulse/workout/generate` | Generate today's workout | `workout.generate.requested` |
| POST | `/api/pulse/workout/adapt` | Adapt workout to reality | `workout.adaptation.requested` |
| POST | `/api/pulse/stock-items` | Create/update stock item | `stock.item.changed` |
| POST | `/api/pulse/grocery-list/generate` | Generate grocery list | `grocery.list.generated` |
| POST | `/api/pulse/batch-cooking/validate` | Validate cooked quantities | `batch.cooking.validated` |
| POST | `/api/pulse/wearable/sync` | Store wearable data if available | `wearable.data.synced` |

### The Path

| method | endpoint | purpose | emitted event |
|---|---|---|---|
| GET | `/api/path/prayers/today` | Prayer times and next prayer | `path.prayers.requested` |
| POST | `/api/path/ghusl/activate` | User manually activates ghusl required | `ghusl.required.activated` |
| POST | `/api/path/ghusl/done` | User confirms ghusl done | `ghusl.completed` |
| POST | `/api/path/fasting/set` | Create/update fasting state | `fasting.state.changed` |
| POST | `/api/path/quran/progress` | Store last validated Quran point | `quran.progress.updated` |
| POST | `/api/path/adhkar/progress` | Store adhkar completion | `adhkar.progress.updated` |
| POST | `/api/path/sadaqa/settings` | Set sadaqa percentage | `sadaqa.settings.changed` |
| POST | `/api/path/sadaqa/donation` | User confirms donation | `sadaqa.recorded` |

## Webhook Inputs

These webhook contracts are for app, n8n, or external-triggered ingestion.

| endpoint | source | purpose |
|---|---|---|
| `/webhooks/app-event` | mobile apps | Generic app event ingestion |
| `/webhooks/file-ready` | file/media service | File uploaded and ready for processing |
| `/webhooks/external/traffic` | external feed | Traffic or road closure update |
| `/webhooks/external/events` | external feed | Concert/event signal |
| `/webhooks/external/rail` | external feed | Rail/IDFM signal |
| `/webhooks/external/airports` | external feed | Flight/airport signal |
| `/webhooks/vector/ride-sound` | device/Vector | V3 only; not part of V1 because Vector V1 has no sound detection dependency |
| `/webhooks/scheduled/weekly-review` | scheduler | Weekly review due |
| `/webhooks/scheduled/daily-cycle` | scheduler | Daily refresh |

n8n webhooks must not be open/public without protection.

Every internal webhook must require:
- request signature
- idempotency key
- timestamp/replay protection

Webhook requests without valid protection must be rejected before workflow execution.

Minimum required headers:

```text
X-Signature: <signature>
Idempotency-Key: <key>
X-Timestamp: <unix_timestamp_seconds>
```

Webhook signature algorithm:
- HMAC-SHA256 over `{timestamp}.{raw_body}` using `INTERNAL_WEBHOOK_SECRET`

Timestamp tolerance:
- 60 seconds

All webhook calls require an idempotency key.

Secret rotation policy: TODO.

## Event Types

Canonical event types use dotted names only.

Core event types:

| event_type | source | purpose |
|---|---|---|
| `app.opened` | any app | Refresh state and context |
| `ai.route.requested` | backend/n8n | AI routing request |
| `ai.routing.decision` | AI router | Store selected workflow/model |
| `memory.updated` | memory pipeline | pgvector memory write |
| `feedback.submitted` | any app | Generic feedback |

Imperium:

| event_type | purpose |
|---|---|
| `day.started` | Manual day start |
| `day.finished` | Manual day end |
| `mission.created` | New planned/current mission |
| `mission.completed` | User tapped done |
| `mission.failed` | User tapped not done and provided reason |
| `replan.requested` | User or system requested controlled replanning |
| `project.completion.validated` | User explicitly completed project |
| `weekly.review.started` | Weekly review started |
| `weekly.review.completed` | Weekly review explicitly validated |

The Vault:

| event_type | purpose |
|---|---|
| `transaction.created` | Gain or expense stored |
| `transaction.updated` | Transaction edited |
| `receipt.ocr.requested` | Ticket/receipt scan sent to Gemini |
| `upcoming.expense.created` | Forecasting object created |
| `upcoming.expense.updated` | Forecasting object edited |
| `vault.pressure.updated` | Pressure recalculated |
| `vault.objectives.updated` | Daily targets recalculated |

Vector:

| event_type | purpose |
|---|---|
| `vector.session.started` | VTC session begins |
| `vector.session.completed` | VTC session result stored |
| `vector.ride.offer.detected` | Offer screenshot/structured offer received |
| `vector.ride.decision.generated` | Recommendation produced |
| `vector.ride.action.recorded` | User accepted/refused/missed |
| `vector.bad.recommendation.flagged` | User correction for learning |
| `vector.low.fuel.triggered` | User pressed low fuel |

Pulse:

| event_type | purpose |
|---|---|
| `biological.profile.corrected` | User corrected body data |
| `health.score.updated` | Score/explanation refreshed |
| `workout.generated` | Workout plan produced |
| `workout.adapted` | Workout changed due to reality |
| `stock.item.changed` | Stock changed |
| `grocery.list.generated` | Grocery list created |
| `batch.cooking.validated` | Cooking result validated |

The Path:

| event_type | purpose |
|---|---|
| `prayer.anchor.updated` | Prayer timing refreshed |
| `ghusl.required.activated` | User manually activated ghusl required |
| `ghusl.completed` | User confirmed ghusl done |
| `fasting.state.changed` | Fasting state changed |
| `quran.progress.updated` | Quran continuation point updated |
| `adhkar.progress.updated` | Adhkar count/completion updated |
| `sadaqa.recorded` | Donation validated |

## Payload Examples

The examples below show event requests. They must use the canonical event envelope. Event-specific fields belong inside `payload`.

### Mission Completed

```json
{
  "event_id": "evt_mission_completed_001",
  "event_type": "mission.completed",
  "schema_version": "1.0",
  "occurred_at": "2026-04-25T08:32:00Z",
  "received_at": "2026-04-25T08:32:02Z",
  "source_app": "imperium",
  "device_id": "device_pixel_7_pro",
  "user_id": "user_main",
  "idempotency_key": "mis_123_completed_2026-04-25T08:32:00Z",
  "correlation_id": "corr_001",
  "causation_id": "evt_previous_or_null",
  "privacy_level": "medium",
  "payload": {
    "mission_id": "mis_123",
    "day_session_id": "ds_20260425"
  }
}
```

Expected response:

```json
{
  "request_id": "req_001",
  "status": "ok",
  "data": {
    "mission_status": "done",
    "next_mission": {
      "id": "mis_124",
      "title": "TODO"
    },
    "ai_short_advice": "TODO"
  },
  "warnings": []
}
```

### Mission Failed

```json
{
  "event_id": "evt_mission_failed_001",
  "event_type": "mission.failed",
  "schema_version": "1.0",
  "occurred_at": "2026-04-25T09:00:00Z",
  "received_at": "2026-04-25T09:00:02Z",
  "source_app": "imperium",
  "device_id": "device_pixel_7_pro",
  "user_id": "user_main",
  "idempotency_key": "mis_123_failed_2026-04-25T09:00:00Z",
  "correlation_id": "corr_002",
  "causation_id": "evt_previous_or_null",
  "privacy_level": "high",
  "payload": {
    "mission_id": "mis_123",
    "reason_category": "fatigue",
    "reason_detail": "Too tired after VTC session"
  }
}
```

Expected behavior:
- store failure event
- treat failure as learning signal
- trigger replanning if current plan is no longer valid
- return one next current mission or no mission with reason

### Vault Transaction

```json
{
  "event_id": "evt_transaction_created_001",
  "event_type": "transaction.created",
  "schema_version": "1.0",
  "occurred_at": "2026-04-25T12:05:00Z",
  "received_at": "2026-04-25T12:05:02Z",
  "source_app": "vault",
  "device_id": "device_pixel_7_pro",
  "user_id": "user_main",
  "idempotency_key": "transaction_carburant_52_40_2026-04-25T12:05:00Z",
  "correlation_id": "corr_010",
  "causation_id": "evt_previous_or_null",
  "privacy_level": "high",
  "payload": {
    "transaction_type": "expense",
    "category": "carburant",
    "amount": 52.4,
    "wallet_type": "CB",
    "date": "2026-04-25",
    "time": "14:05",
    "location_text": "Station Total - Paris",
    "location_source": "gps",
    "latitude": 48.8566,
    "longitude": 2.3522,
    "source_type": "manual",
    "notes": "TODO"
  }
}
```

Expected response:

```json
{
  "request_id": "req_010",
  "status": "ok",
  "data": {
    "transaction_id": "txn_123",
    "wallets": {
      "CB": 447.6,
      "Cash": 1000,
      "Crypto": 0,
      "Total": 1447.6
    },
    "financial_pressure": {
      "score": 72,
      "label": "DANGER"
    },
    "daily_objectives": {
      "minimal": 150,
      "comfortable": 250,
      "optimal": 400
    }
  }
}
```

### Receipt OCR Request

```json
{
  "event_id": "evt_receipt_ocr_requested_001",
  "event_type": "receipt.ocr.requested",
  "schema_version": "1.0",
  "occurred_at": "2026-04-25T12:06:00Z",
  "received_at": "2026-04-25T12:06:02Z",
  "source_app": "vault",
  "device_id": "device_pixel_7_pro",
  "user_id": "user_main",
  "idempotency_key": "receipt_ocr_file_receipt_123",
  "correlation_id": "corr_011",
  "causation_id": "evt_previous_or_null",
  "privacy_level": "very_high",
  "input_type": "image",
  "payload": {
    "file_id": "file_receipt_123",
    "location_text": "Paris",
    "location_source": "gps"
  }
}
```

Expected behavior:
- route to Gemini
- extract candidate transaction fields
- return editable pre-filled expense popup
- store confidence and raw extracted text according to retention policy

### Vector Ride Offer Analysis

```json
{
  "event_id": "evt_vector_ride_offer_001",
  "event_type": "vector.ride.offer.detected",
  "schema_version": "1.0",
  "occurred_at": "2026-04-25T16:45:00Z",
  "received_at": "2026-04-25T16:45:02Z",
  "source_app": "vector",
  "device_id": "device_pixel_7_pro",
  "user_id": "user_main",
  "idempotency_key": "ride_offer_file_ride_123",
  "correlation_id": "corr_020",
  "causation_id": "evt_previous_or_null",
  "privacy_level": "very_high",
  "input_type": "screenshot",
  "payload": {
    "file_id": "file_ride_123",
    "vtc_session_id": "vs_123",
    "destination_mode_remaining": 4,
    "fuel_autonomy_km": 180
  }
}
```

Expected response:

```json
{
  "request_id": "req_020",
  "status": "ok",
  "data": {
    "offer_id": "ride_123",
    "halo_state": "green",
    "recommendation": "ACCEPT",
    "explanation": "High estimated hourly rate and acceptable return probability.",
    "extracted": {
      "price": 38,
      "pickup_distance": 2.4,
      "total_estimated_time": 42,
      "destination_zone": "TODO"
    },
    "compliance": {
      "auto_click": false,
      "user_final_decision_required": true
    }
  }
}
```

### Ghusl Activation

```json
{
  "event_id": "evt_ghusl_required_001",
  "event_type": "ghusl.required.activated",
  "schema_version": "1.0",
  "occurred_at": "2026-04-25T07:00:00Z",
  "received_at": "2026-04-25T07:00:02Z",
  "source_app": "path",
  "device_id": "device_pixel_7_pro",
  "user_id": "user_main",
  "idempotency_key": "ghusl_required_2026-04-25T07:00:00Z",
  "correlation_id": "corr_030",
  "causation_id": "evt_previous_or_null",
  "privacy_level": "very_high",
  "payload": {
    "ghusl_required": true,
    "location_text": "TODO"
  }
}
```

Expected behavior:
- store religious private state
- calculate next prayer timing and travel context
- create Imperium mission automatically
- rebuild daily planning
- require user action `GHUSL FAIT` to close

### AI Routing Request

```json
{
  "event_id": "evt_ai_route_requested_001",
  "event_type": "ai.route.requested",
  "schema_version": "1.0",
  "occurred_at": "2026-04-25T07:10:00Z",
  "received_at": "2026-04-25T07:10:02Z",
  "source_app": "imperium",
  "device_id": "device_pixel_7_pro",
  "user_id": "user_main",
  "idempotency_key": "ai_route_weekly_review_wr_2026w18",
  "correlation_id": "corr_040",
  "causation_id": "evt_previous_or_null",
  "privacy_level": "high",
  "input_type": "text",
  "payload": {
    "task": "weekly_review_synthesis",
    "urgency_level": "normal",
    "privacy_level": "high",
    "memory_required": true,
    "context_refs": {
      "weekly_review_id": "wr_2026w18"
    }
  }
}
```

Expected response:

```json
{
  "request_id": "req_040",
  "status": "ok",
  "data": {
    "selected_model": "Claude",
    "selected_workflow": "imperium_weekly_review_synthesis",
    "routing_reason": "complex strategic synthesis with long-term memory required",
    "memory_used": true
  }
}
```

## App-to-Backend Responsibilities

Apps must:
- send structured events
- include source app and timestamp
- include user-confirmed data where required
- display backend responses without inventing decisions
- keep specialist boundaries
- expose user editability for OCR/extracted data
- send feedback and corrections
- respect offline degraded behavior

Apps must not:
- make final strategic decisions locally
- create multiple current missions
- assume project completion
- hide failed AI confidence
- auto-click or automate Bolt
- treat upcoming expenses as real transactions
- treat prayer anchors as optional productivity slots

## Backend-to-App Responses

Backend responses should be structured for UI.

Response types:
- `state_snapshot`
- `mission_update`
- `recommendation`
- `extraction_result`
- `validation_error`
- `ai_advice`
- `warning`
- `pending_user_confirmation`

Example validation error:

```json
{
  "request_id": "req_err",
  "status": "error",
  "error": {
    "code": "ONE_ACTIVE_MISSION_VIOLATION",
    "message": "Only one current mission can exist."
  }
}
```

## n8n Workflow Triggers

Canonical event types remain dotted. n8n workflow names may use snake_case.

n8n orchestrates workflows but is not the database owner. For V1, n8n must write canonical app data through backend APIs, not directly to PostgreSQL. See `06_N8N_WORKFLOWS.md`.

| event_type | n8n workflow name | expected workflow |
|---|---|---|
| any accepted event | `event_ingested_workflow` | validate, store, route follow-up |
| `ai.route.requested` | `ai_route_requested_workflow` | classify, select model, execute, log |
| `file.uploaded` | `file_uploaded_workflow` | extract, process, store metadata |
| `mission.completed` | `mission_completed_workflow` | update mission, choose next state, learn |
| `mission.failed` | `mission_failed_workflow` | store reason, replan if needed, learn |
| `replan.requested` | `replan_requested_workflow` | collect context, AI/rules replan, return one mission |
| `weekly.review.completed` | `weekly_review_completed_workflow` | update assumptions, write memory, refresh app contexts |
| `transaction.created` | `transaction_created_analysis_workflow` | update wallets, pressure, objectives, notify dependent apps |
| `receipt.ocr.requested` | `receipt_ocr_requested_workflow` | Gemini OCR, return editable transaction |
| `vector.ride.offer.detected` | `vector_ride_offer_detected_workflow` | Gemini extraction, rules/AI recommendation, halo response |
| `vector.session.completed` | `vector_session_completed_workflow` | store result, update Vault/Imperium learning |
| `workout.adapted` | `workout_adapted_workflow` | apply constraints, generate adjusted session |
| `ghusl.required.activated` | `ghusl_required_activated_workflow` | create Imperium mission, rebuild plan |
| `sadaqa.recorded` | `sadaqa_recorded_workflow` | store donation, update remaining carry |
| `day.finished` | `day_finished_review_workflow` | close day, store summary, trigger review logic if needed |
| `daily.cycle` | `daily_cycle_workflow` | refresh prayer, objectives, pending review, reminders |
| `weekly.review.due` | `weekly_review_due_workflow` | create pending review if not completed |

## Storage Expectations

### PostgreSQL

PostgreSQL stores structured truth.

Expected MVP tables or equivalent:
- `users`
- `trusted_devices`
- `refresh_tokens`
- `auth_events`
- `events`
- `ai_requests`
- `ai_routing_decisions`
- `files`
- `day_sessions`
- `missions`
- `mission_events`
- `replanning_requests`
- `projects`
- `routines`
- `priorities`
- `weekly_reviews`
- `weekly_review_answers`
- `feed_ia_documents`
- `transactions`
- `wallet_balances`
- `upcoming_expenses`
- `vault_daily_objectives`
- `vector_sessions`
- `ride_offers`
- `ride_recommendations`
- `vector_business_rules`
- `map_eta_observations`
- `scheduled_rides`
- `pulse_biological_profiles`
- `pulse_health_scores`
- `pulse_workouts`
- `pulse_stock_items`
- `pulse_grocery_lists`
- `pulse_batch_cooking_sessions`
- `wearable_data_points`
- `path_prayer_days`
- `path_ghusl_events`
- `path_fasting_days`
- `path_quran_progress`
- `path_adhkar_progress`
- `path_sadaqa_settings`
- `path_sadaqa_donations`
- `feedback_events`

Table names are recommendations. Exact schema is TODO.

### pgvector

pgvector stores semantic memory, not raw truth replacement.

Expected memory objects:
- Feed IA document chunks
- weekly review summaries
- project strategy summaries
- user correction summaries
- repeated mission failure patterns
- Vector session learning summaries
- bad recommendation explanations
- financial behavior summaries
- Pulse biological pattern summaries
- The Path routine consistency summaries
- model output summaries approved for memory

Do not use pgvector as the only source for canonical state.

### File / Media Storage

File storage handles:
- Feed IA documents
- receipts
- VTC screenshots
- audio notes
- exported transcripts if retained
- processed extraction artifacts

Required metadata:
- `file_id`
- `user_id`
- `source_app`
- `file_name`
- `file_type`
- `mime_type`
- `size_bytes`
- `upload_status`
- `processing_status`
- `created_at`
- `processed_at`
- `retention_policy`

Retention policy: TODO.

Backups:
- must be encrypted
- must include PostgreSQL and required file/media metadata
- pgvector backup strategy must preserve memory linkage to PostgreSQL source records
- exact backup schedule, storage provider, restore process, and key management are TODO

## MVP Guardrails

Backend must enforce:
- only one current mission
- no silent project completion
- no weekly review completion without final validation
- one canonical user record in V1
- registered trusted device required for normal API access
- revoked devices cannot refresh tokens
- transaction amount > 0
- wallet type must be `CB`, `Cash`, or `Crypto`
- upcoming expense is not a real transaction
- Vector no auto-click/no automation
- ghusl activation is manual only
- prayer anchors cannot be treated as optional
- Pulse must work without wearable data
- AI routing decisions must be logged
- external AI calls must pass the privacy gate before sending data to Gemini, GPT, Claude, or any external provider
- backups must be encrypted

## Open Decisions

TODO:
- exact n8n deployment URL
- file storage provider
- push notification provider
- exact pgvector embedding model
- observability/logging stack
- production secrets management
- production/deployment base URL
- refresh token hashing algorithm
- master access key / secret phrase rotation and recovery ceremony
- webhook secret rotation policy
