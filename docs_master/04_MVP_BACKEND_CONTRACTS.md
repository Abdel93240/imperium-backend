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

### Imperium Daily Plan V2

`GET /api/imperium/daily-plan`

Purpose:
- return a read-only daily plan snapshot for the current user
- consolidate existing read models without creating new rows
- expose the daily state for Imperium, Mission, Path, and Pulse in one response

Request semantics:
- optional query param: `date=YYYY-MM-DD`
- when `date` is omitted, the backend uses the Europe/Paris local date convention via `get_default_local_date()`
- this endpoint is snapshot-oriented and does not require `Idempotency-Key`

Read-only semantics:
- no AI
- no n8n
- no OCR
- no scoring
- no coaching
- no recommendation
- no orchestration
- no automatic creation
- no cross-module write
- no legacy dashboard aggregator

Response contract:
- `date`
- `dashboard`
- `mission`
- `path`
- `pulse`
- `summary`
- `meta`
- `readiness`
- `modules`
- `safe_explanation`

Response shape notes:
- `safe_explanation` is a public, read-only explanation string for the snapshot contract
- no user id is exposed in any daily-plan response section
- no legacy dashboard aggregator is used in this contract

Snapshot metadata:
- `summary` is metadata only and must contain booleans and counts only
- `summary.safe_explanation` must stay public, deterministic, and read-only
- `readiness` is a readiness snapshot only block and must contain booleans and counts only
- `readiness` is bool/count only
- `readiness` is not a score, not a health score, not a recommendation, and not a coaching surface
- `readiness.read_only` is always `true`
- `readiness.safe_explanation` must explain that it is computed from existing read-only data
- `modules` is metadata only
- `modules` is not a runtime availability check
- `modules` is not a health check
- `modules` is not a score
- `modules` deterministic order is: `dashboard`, `mission`, `path`, `pulse`
- each `modules[]` item has `name`, `status`, `read_only`
- each `modules[].status` is always `included` in Patch 13E
- each `modules[].read_only` is always `true`
- `modules` must not expose internal identifiers
- `meta.snapshot_generated_at` is timezone-aware UTC
- `meta.daily_plan_version` is `v1`
- `meta.read_only` is `true`
- `meta` is metadata only and must not carry business actions
- `meta` is UTC timestamp metadata only, not a business payload

Response shape rules:
- `dashboard` remains independently available as a separate snapshot contract
- the daily plan aggregates existing snapshot reads only
- no canonical row is created by the daily plan route
- no Mission, Vault, Path, or Pulse write is allowed from this contract

Europe/Paris convention:
- daily plan default date follows the Europe/Paris local date helper
- this convention applies only to the snapshot date selection, not to UTC metadata timestamps
- when `date` is omitted, selection follows Europe/Paris local date conventions



### Imperium Home Bootstrap

`GET /api/imperium/home/bootstrap`

Purpose:
- return minimal frontend bootstrap metadata for the current authenticated user
- expose contract-level module availability only (not runtime checks)
- avoid frontend coupling to multiple route contracts at startup

Request semantics:
- GET only
- JWT-scoped via `CurrentUserDep`
- no `Idempotency-Key` required

Read-only semantics:
- metadata only
- no business data
- no business data read
- no health check
- `status = available` means contract availability only, not runtime health
- no AI
- no n8n
- no OCR
- no scoring
- no coaching
- no recommendation
- no cross-module write
- no auto-creation

Response contract:
- `backend_version`
- `read_only`
- `modules[]` in deterministic order: `dashboard`, `daily_plan`, `mission`, `vault`, `path`, `pulse`
- `modules[].status` always `available` in Patch 14A
- `modules[].primary_endpoint` is metadata only and is the public primary read route for each module
- `safe_explanation`

Security/safety:
- do not expose `user_id`
- do not expose infra/host/provider/secrets metadata

Frontend bootstrap usage:
- call this endpoint once at home startup to discover core module entrypoints
- do not treat this response as a data snapshot or health probe

### Imperium Contracts Index V1

`GET /api/imperium/contracts/index`

Purpose:
- return metadata only for frontend contract navigation
- provide a static deterministic V1 index of selected public Imperium module endpoints
- help frontend map major routes without runtime discovery

Non-goals:
- not a full OpenAPI document
- not a health check
- not a dynamic runtime discovery mechanism
- no FastAPI route scanning

Rules:
- JWT-scoped via `CurrentUserDep`
- no `Idempotency-Key` required
- `contract_version` is `v1`
- `read_only` is always `true`
- deterministic groups order: `home`, `dashboard`, `daily_plan`, `mission`, `vault`, `path`, `pulse`
- metadata only: no business data read, no writes, no auto-creation
- no exposure of `user_id`, secrets, provider metadata, or infra metadata
- must not expose internal/admin/sensitive routes
- no AI, n8n, OCR, scoring, coaching, or recommendations
- route owner canonique: `app/api/v1/routes/imperium_contracts.py`
- `Home Bootstrap` ≠ `Contract Index`
- no duplicate/shadow route in `imperium_home.py`

### Imperium Contracts Compliance Metadata

`GET /api/imperium/contracts/compliance`

Purpose:
- return declarative compliance metadata for the contracts index surface
- help frontend and dev tooling confirm that the contract surface is metadata-only
- keep a stable, deterministic V1 summary without runtime auditing

Rules:
- JWT-scoped via `CurrentUserDep`
- no `Idempotency-Key` required
- read-only metadata only
- not a runtime compliance audit
- not OpenAPI
- not a health check
- not dynamic discovery
- no business data read
- no AI, n8n, OCR, scoring, coaching, or recommendations
- no cross-module writes
- no secrets, provider metadata, infra metadata, or user id
- `contract_version` is `v1`
- `read_only` is `true`
- deterministic `checks[]` order: `metadata_only`, `not_openapi`, `not_health_check`, `no_business_data_read`, `no_dynamic_discovery`
- each `checks[]` item has `key`, `status`, `safe_explanation`
- `status` is always `declared`
- `safe_explanation` is public, read-only, and declarative

Response contract:

```json
{
  "contract_version": "v1",
  "read_only": true,
  "checks": [
    {
      "key": "metadata_only",
      "status": "declared",
      "safe_explanation": "Contracts index is metadata-only."
    },
    {
      "key": "not_openapi",
      "status": "declared",
      "safe_explanation": "Contracts index is not a generated OpenAPI document."
    },
    {
      "key": "not_health_check",
      "status": "declared",
      "safe_explanation": "Contracts index is not a runtime health check."
    },
    {
      "key": "no_business_data_read",
      "status": "declared",
      "safe_explanation": "Contracts index does not read business data."
    },
    {
      "key": "no_dynamic_discovery",
      "status": "declared",
      "safe_explanation": "Contracts index is static and deterministic in V1."
    }
  ],
  "safe_explanation": "Frontend contracts compliance metadata."
}
```

This endpoint is declarative metadata only.
It is not a runtime audit and it does not scan routes dynamically.
It does not read business data.
It does not expose secrets, provider metadata, infra metadata, or user id.


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
| GET | `/api/imperium/dashboard` | Patch 12A read-only dashboard foundation: active mission, Vault summary, Path today, Pulse today | none |
| GET | `/api/imperium/daily-plan` | Patch 13A read-only daily plan snapshot: dashboard foundation plus active mission, Path today, and Pulse today | none |
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
| GET | `/api/imperium/priorities` | Legacy read-only compatibility projection from Decision Framework priorities | none |
| POST | `/api/imperium/priorities` | Legacy priority write disabled; use `/api/imperium/decision-framework/priorities` | none; returns `410 Gone` |
| POST | `/api/imperium/weekly-review/start` | Start weekly review | `weekly.review.started` |
| POST | `/api/imperium/weekly-review/{review_id}/answer` | Store review answer | `weekly.review.answered` |
| POST | `/api/imperium/weekly-review/{review_id}/complete` | Complete after final validation | `weekly.review.completed` |

#### Legacy Priorities Compatibility Projection

`GET /api/imperium/priorities` is a read-only compatibility projection over
Decision Framework priorities. If no active priority rows exist yet, it returns
the deterministic V1 defaults as transient response data and does not persist
them.

Persistent initialization must use an explicit POST flow. Hidden writes from GET
are forbidden: no `db.add`, no `flush`, and no `commit`.

#### Imperium Dashboard Foundation 12B - consolidated read-only module snapshot

Patch 12A introduced the dashboard surface. Patch 12B consolidates the final
contract and audit notes without changing behavior. The backend-owned read
model lives under:

- `GET /api/imperium/dashboard`

Purpose:
- aggregate the current-user state already owned by stable V1 modules
- expose a deterministic Imperium snapshot for Android/UI consumption
- keep the dashboard as a snapshot read-only view, not the AI brain, not a
  scoring/coaching/recommendation layer, and not an orchestration workflow

Query params:
- `date` optional `date`; default date convention is Europe/Paris through the backend helper; query `date` overrides the Europe/Paris default
- `currency` optional string; default `EUR`; must match `^[A-Za-z]{3}$`; three-letter currency codes are accepted and normalized uppercase

Currency V1 notes:
- ISO-4217 existence is not validated in V1.
- Unknown or unused currency with no transaction returns zero totals.
- This dashboard follows the Vault summary read contract; it observes ledger reality and does not create wallet or finance decisions.

Response sections:
- root `date`, normalized `currency`, and `safe_explanation`
- `mission`: active mission section from the current user's active mission read model, or `null`
- `vault`: current-user ledger summary for the requested currency only
- `path`: today view for the current user and requested date
- `pulse`: today entry for the current user and requested date

Contract:
- GET only
- JWT-scoped via `CurrentUserDep`
- no `Idempotency-Key` required
- strict current-user scope for Mission, Vault, Path, and Pulse
- snapshot read-only: no `db.add`, `db.flush`, `db.commit`, or rollback-driven mutation path
- no write cross-module and no cross-module writes
- deterministic: no hidden scoring, coaching, recommendation, or replanning layer
- no user id is exposed in any dashboard response section
- responses are public-safe for the current authenticated user only
- no auto-creation of Path rows
- no auto-creation of Pulse rows

Boundaries:
- no real AI call
- no n8n call or workflow trigger
- no n8n AI Agent
- no n8n DB write
- no pgvector write
- no embeddings
- no automatic memory commit
- no calendar or automatic replanning
- no OCR
- no automatic scoring
- no automatic coaching
- no automatic recommendations
- no automatic Path check-in creation
- no automatic Pulse entry creation
- no automatic creation of Path/Pulse rows
- no Mission/Vault/Path/Pulse mutation
- no cross-module write
- no AI routing, no model selection, no scoring, no coaching, no recommendation generation

| method | endpoint | objective | Idempotency-Key | access scope | mode | public safe fields | main errors | allowed / forbidden side effects |
|---|---|---|---|---|---|---|---|---|
| GET | `/api/imperium/dashboard` | Read the current user's Imperium dashboard snapshot from stable V1 modules. | Not required | `CurrentUserDep` | snapshot read-only | `date`, `currency`, `mission`, `vault`, `path`, `pulse`, `readiness`, `meta`, `safe_explanation` | `200`, `409`, `422` | Allowed: read active mission, Vault summary, Path today, Pulse today, readiness snapshot, snapshot metadata. Forbidden: writes, AI, n8n, n8n AI Agent, n8n DB write, pgvector writes, embeddings, automatic memory commit, calendar/replanning, OCR, automatic scoring, automatic coaching, automatic recommendations, automatic Path/Pulse creation, cross-module writes. |

#### Imperium Dashboard Foundation 12D - Readiness Snapshot

The dashboard response includes a read-only `readiness` block computed from the same read-only module data already used by Mission, Vault, Path, and Pulse.

Readiness is not a score.

Readiness is not a recommendation.

Readiness is not a health score.

*_available means the section was wired and calculated successfully in the snapshot.
It is not an external health check and not an availability score.

This block contains only booleans and counts:

- `mission_available`
- `vault_available`
- `path_available`
- `pulse_available`
- `active_mission_present`
- `vault_transaction_count`
- `path_today_count`
- `pulse_entry_present`

The `safe_explanation` for this block is:

#### Imperium Daily Plan Foundation 13A - read-only consolidated daily snapshot

Patch 13A adds a new daily planning snapshot for the current user.
It is a read-only consolidation layer on top of existing V1 snapshots.
It does not create plans, it does not score, and it does not recommend or coach.

The backend-owned read model lives under:

- `GET /api/imperium/daily-plan`

Purpose:
- consolidate the daily dashboard snapshot with the current active mission, Path today, and Pulse today
- give Android/UI a single read-only daily snapshot to render
- remain a pure snapshot view, not an AI, not a replanning workflow, and not a mutation path

Query params:
- `date` optional `date`; default date convention is Europe/Paris through the backend helper; query `date` overrides the Europe/Paris default

Response sections:
- root `date` and `safe_explanation`
- `dashboard`: the dashboard foundation snapshot for the same date
- `mission`: current active mission read model
- `path`: Path today snapshot
- `pulse`: Pulse today snapshot
- `summary`: derived booleans/counts only
- `meta`: snapshot metadata with UTC `snapshot_generated_at`, `daily_plan_version = v1`, and `read_only = true`

Contract:
- GET only
- JWT-scoped via `CurrentUserDep`
- no `Idempotency-Key` required
- strict current-user scope for Mission, Dashboard, Path, and Pulse
- snapshot read-only: no `db.add`, `db.flush`, `db.commit`, or rollback-driven mutation path
- no write cross-module and no cross-module writes
- deterministic: no hidden scoring, coaching, recommendation, replanning, AI, n8n, or OCR layer
- no user id is exposed in any daily-plan response section
- no auto-creation of Path rows
- no auto-creation of Pulse rows
- no automatic Path/Pulse/Mission/Vault linkage beyond reading the existing snapshots

Boundaries:
- no real AI call
- no n8n call or workflow trigger
- no n8n AI Agent
- no n8n DB write
- no pgvector write
- no embeddings
- no automatic memory commit
- no calendar or automatic replanning
- no OCR
- no automatic scoring
- no automatic coaching
- no automatic recommendations
- no automatic Path check-in creation
- no automatic Pulse entry creation
- no Mission/Vault/Path/Pulse mutation
- no cross-module write
- no legacy dashboard aggregator
- no auto-generated plan rows
- no model selection, scoring, or routing

| method | endpoint | objective | Idempotency-Key | access scope | mode | public safe fields | main errors | allowed / forbidden side effects |
|---|---|---|---|---|---|---|---|---|
| GET | `/api/imperium/daily-plan` | Read the current user's consolidated daily snapshot from stable V1 snapshots. | Not required | `CurrentUserDep` | snapshot read-only | `date`, `dashboard`, `mission`, `path`, `pulse`, `summary`, `meta`, `readiness`, `modules`, `safe_explanation` | `200`, `409`, `422` | Allowed: read dashboard foundation snapshot, active mission, Path today, Pulse today, daily-plan modules metadata list, derived summary, snapshot metadata. Forbidden: writes, AI, n8n, n8n AI Agent, n8n DB write, pgvector writes, embeddings, automatic memory commit, calendar/replanning, OCR, automatic scoring, automatic coaching, automatic recommendations, automatic Path/Pulse creation, cross-module writes. |

```text
Dashboard readiness snapshot computed from read-only module data.
```

Readiness has no side effects:

- no write
- no cross-module write

#### Imperium Dashboard Consistency Metadata 12E - read-only snapshot metadata

Patch 12E adds a small read-only `meta` block to the existing dashboard snapshot
without changing the dashboard mission/vault/path/pulse data model or adding
any business logic.

Purpose:
- expose snapshot metadata only
- support dashboard consistency checks for the current snapshot
- keep the dashboard read-only and deterministic

Metadata fields:
- `snapshot_generated_at`: UTC ISO8601 timestamp generated at snapshot time
- `dashboard_version`: static string `v1`
- `included_modules`: deterministic list `["mission", "vault", "path", "pulse"]`
- `read_only`: always `true`
- `safe_explanation`: `Dashboard metadata for current snapshot.`

Contract:
- metadata only, not telemetry
- no analytics
- no tracking
- no user id, request id, internal ids, hostnames, infra metadata, or AI provider info
- no score, coaching, recommendation, health score, or advice
- no AI, n8n, OCR, pgvector, embeddings, or memory commit
- no auto-creation of Path or Pulse data
- no cross-module writes

The dashboard remains a snapshot read-only view. The new `meta` block is
read-only metadata only and does not alter the behavior of 12A-12D.
- no Path creation
- no Pulse creation
- no AI
- no n8n
- no scoring
- no coaching
- no recommendation

### The Vault

| method | endpoint | purpose | emitted event |
|---|---|---|---|
| POST | `/api/imperium/vault/transactions` | Patch 9A append-only income/expense ledger create; JWT scoped; requires `Idempotency-Key`; no AI/n8n/pgvector/memory/calendar side effect | none in Patch 9A |
| GET | `/api/imperium/vault/transactions` | Patch 9A current-user ledger read with deterministic filters and sorting; no `Idempotency-Key` required | none |
| GET | `/api/imperium/vault/transactions/{transaction_id}` | Patch 9E current-user Vault transaction detail read; read-only; returns `404` when missing or non-owned; no `Idempotency-Key` required | none |
| POST | `/api/imperium/vault/transactions/{transaction_id}/reverse` | Patch 9F append-only transaction correction endpoint; JWT scoped; requires `Idempotency-Key`; creates one opposite reversal transaction and never updates/deletes the original transaction | none in Patch 9F |
| GET | `/api/imperium/vault/summary` | Patch 9B current-user ledger summary computed on the fly from current transactions; read-only; no `Idempotency-Key` required | none |
| GET | `/api/imperium/vault/summary/categories` | Patch 9C current-user category summary computed on the fly from current transactions; read-only; no `Idempotency-Key` required | none |
| GET | `/api/imperium/vault/summary/monthly` | Patch 9D/9J current-user monthly summary computed on the fly from current transactions; read-only; grouped by UTC `occurred_at` month `YYYY-MM`; currency accepts three ASCII letters and normalizes uppercase; no `Idempotency-Key` required | none |
| GET | `/api/vault/dashboard` | Wallets, pressure, objectives, upcoming expenses | `vault.dashboard.requested` |
| POST | `/api/vault/transactions` | Create gain or expense | `transaction.created` |
| PATCH | `/api/vault/transactions/{transaction_id}` | Legacy direct edit route; not part of Imperium Vault V1 and forbidden for the append-only ledger | forbidden in V1 |
| POST | `/api/vault/upcoming-expenses` | Create upcoming expense | `upcoming.expense.created` |
| PATCH | `/api/vault/upcoming-expenses/{expense_id}` | Edit upcoming expense | `upcoming.expense.updated` |
| POST | `/api/vault/scan-ticket` | Receipt image OCR flow | `receipt.ocr.requested` |
| POST | `/api/vault/objectives/recalculate` | Recalculate daily targets | `vault.objectives.recalculate.requested` |

#### Vault V1 / Ledger Foundation

Patch 9A introduces the Imperium-facing Vault ledger foundation at `/api/imperium/vault/transactions`.
This is an append-only foundation for manual income and expense facts only. It records reality so later
Vault, Path, and Imperium workflows can reason from canonical backend data, but Patch 9A does not
calculate strategy or trigger downstream automation.

`POST /api/imperium/vault/transactions`:
- Requires authenticated current-user scope.
- Requires `Idempotency-Key`.
- Rejects client-supplied `user_id`; the backend always uses the authenticated user.
- Rejects `amount_cents <= 0`.
- Accepts only `transaction_type` values `income` and `expense`.
- Requires timezone-aware `occurred_at`; optional `timezone` can be supplied by the client. Patch 9J makes `occurred_at` the only authoritative Vault V1 reporting time source.
- Creates one append-only row in `imperium_vault_transactions` and records the idempotency result.

`GET /api/imperium/vault/transactions`:
- Requires authenticated current-user scope.
- Does not require `Idempotency-Key`.
- Returns only transactions owned by the current user.
- Supports filters: `transaction_type`, `category`, `source`, `occurred_from`, and `occurred_to`.
- `occurred_from` and `occurred_to` must include timezone information and filter by the absolute `occurred_at` instant.
- Supports pagination with `limit` and `offset`.
- Sorts deterministically by `occurred_at desc`, `created_at desc`, then `id desc`.
- Is read-only: no `db.add`, `flush`, `commit`, event creation, or workflow trigger.

`GET /api/imperium/vault/transactions/{transaction_id}`:
- Requires authenticated current-user scope.
- Does not require `Idempotency-Key`.
- Returns only one transaction owned by the current user.
- Returns `404` when transaction is missing or non-owned => 404.
- Is read-only: no `db.add`, `flush`, `commit`, wallet persistence, balance persistence, AI, n8n, OCR, sadaqa, pgvector, memory, or calendar side effects.

`GET /api/imperium/vault/summary`:
- Requires authenticated current-user scope.
- Does not require `Idempotency-Key`.
- Returns only the current user's ledger transactions.
- Supports filters: `currency`, `occurred_from`, and `occurred_to`.
- `currency` accepts exactly three ASCII letters (`^[A-Za-z]{3}$`) and normalizes to uppercase.
- `occurred_from` and `occurred_to` must include timezone information. They are interpreted as UTC-normalized absolute bounds on `occurred_at`; no local timezone conversion is applied.
- Computes `total_income_cents`, `total_expense_cents`, `net_cents`, `transaction_count`, `income_count`, and `expense_count` at request time.
- Is read-only: no `db.add`, `flush`, `commit`, wallet persistence, balance persistence, AI, n8n, OCR, sadaqa, pgvector, memory, or calendar side effects.
- Returns zeros for all totals and counts when there are no matching transactions.

Patch 9A scope:
- Stores only `income` or `expense` rows in `imperium_vault_transactions`.
- Amount is stored as positive integer `amount_cents`; currency defaults to uppercase `EUR`.
- Public responses never accept or expose client-controlled `user_id`.
- `POST` is idempotent by current user and `Idempotency-Key`: same key plus same payload returns the original public response; same key plus different payload returns conflict.

Patch 9B scope:
- Adds a read-only summary endpoint for current-user vault ledger facts.
- The summary is computed from database transactions at request time and is not persisted.
- No AI/n8n/OCR/sadaqa/wallet/balance workflows are triggered by the summary read path.
- `GET` supports `limit`, `offset`, `transaction_type`, `category`, `source`, `occurred_from`, and `occurred_to`, sorted by `occurred_at desc`, `created_at desc`, and `id`.
- No balance, wallet automation, sadaqa, OCR ticket flow, AI analysis, n8n workflow, n8n AI Agent, n8n DB write, pgvector write, embedding, memory commit, automatic replanning, calendar replanning, financial scoring, or internal coefficient is part of this patch.

Patch 9C scope:
- Adds a read-only category summary endpoint for current-user vault ledger facts.
- The category summary is computed from database transactions at request time and is not persisted.
- Transactions are grouped by category; missing, null, or blank categories are returned as `uncategorized`.
- `GET` supports `currency`, `transaction_type`, `occurred_from`, and `occurred_to`.
- `currency` accepts exactly three ASCII letters (`^[A-Za-z]{3}$`) and normalizes to uppercase.
- `occurred_from` and `occurred_to` must include timezone information. They are interpreted as UTC-normalized absolute bounds on `occurred_at`; no local timezone conversion is applied.
- The response is deterministic and sorted by `transaction_count desc`, absolute net magnitude desc, then `category asc`.
- No AI/n8n/OCR/sadaqa/wallet/balance workflows are triggered by the category summary read path.
- No wallet balance is persisted and no ledger mutation occurs on this endpoint.

Patch 9D scope:
- Adds a read-only monthly summary endpoint for current-user vault ledger facts.
- The monthly summary is computed from database transactions at request time and is not persisted.
- The endpoint is grouped by month for public reporting.
- Patch 9J revises the month rule: transactions are grouped by UTC `occurred_at` month and the public `YYYY-MM` format.
- `currency` accepts exactly three ASCII letters (`^[A-Za-z]{3}$`) case-insensitively, normalizes to uppercase, and defaults to `EUR`.
- `GET` supports `currency`, `occurred_from`, and `occurred_to`.
- `occurred_from` and `occurred_to` must include timezone information. They are interpreted as UTC-normalized absolute bounds on `occurred_at`; no local timezone conversion is applied.
- The response is deterministic and sorted by `month desc`.
- No AI/n8n/OCR/sadaqa/wallet/balance workflows are triggered by the monthly summary read path.
- No wallet balance is persisted and no ledger mutation occurs on this endpoint.

Patch 9E scope:
- Adds a read-only Vault transaction detail endpoint for one transaction id.
- Enforces current-user scope in the query; non-owned records are not disclosed and return `404`.
- Deterministic output with safe public fields only.
- No AI/n8n/OCR/sadaqa/wallet/balance workflows are triggered by the detail read path.

`POST /api/imperium/vault/transactions/{transaction_id}/reverse`:
- Requires authenticated current-user scope.
- Requires `Idempotency-Key`.
- Accepts only `{ "reason": "..." }`; `reason` is trimmed, required, non-empty, and max 500 characters.
- Rejects unknown fields and never accepts client-supplied amount, type, currency, or user id.
- Returns `404` when the original transaction is missing or non-owned.
- Returns `409` when the original is already reversed, when the target is itself a reversal, or when the idempotency key is reused with a different payload.
- Same `Idempotency-Key` plus same payload returns the original reversal response.
- Creates exactly one new row in `imperium_vault_transactions` with the opposite transaction type, same positive amount, same currency, same category, source `reversal`, backend `occurred_at`, backend-derived compatibility date fields, null `external_ref`, `is_reversal = true`, `reversal_of_transaction_id = original.id`, and the trimmed `reversal_reason`.
- Reversals are dated at the backend moment of the counter-entry. They do not rewrite the original transaction's period. A January transaction reversed in March produces a March counter-entry in Vault V1 append-only accounting.
- This is an append-only correction endpoint: it reverses by appending an opposite ledger row.
- The original transaction is never updated or deleted, even for corrections.
- Patch 9F allows one and only one reversal per original transaction.

Patch 9F scope:
- Adds the append-only correction / reversal foundation for Vault transactions.
- Does not add persistent AI, n8n, OCR, sadaqa, wallet, balance, pgvector, embedding, memory, calendar, or financial decision side effects.
- Does not trigger AI, n8n, OCR, sadaqa, wallet, or balance workflows.
- Result is deterministic apart from backend timestamps and ids.

Patch 9G scope:
- Formalizes the Vault transaction immutability contract.
- The Vault ledger is append-only and transactions are immutable after insert.
- No PUT/PATCH/DELETE endpoints exist under `/api/imperium/vault/transactions`.
- Corrections must use `POST /api/imperium/vault/transactions/{transaction_id}/reverse`.
- The original transaction must never be updated or deleted.
- The reversal transaction is a new transaction linked to the original.
- Patch 9F/9G allow one and only one reversal per original transaction.
- This patch does not add any AI, n8n, OCR, sadaqa, wallet, balance, pgvector, memory, or calendar side effects.

#### Vault 9H Contract Consolidation

Patch 9H does not add new behavior. It consolidates the Vault contract so audit review can verify the final surface in one place.

| method | endpoint | scope | idempotency | mode | safe public response | principal errors | forbidden side effects |
|---|---|---|---|---|---|---|---|
| POST | `/api/imperium/vault/transactions` | `CurrentUserDep`, current-user scoped | Required | append-only write | `transaction`, `event_id`, `idempotency_key`, `status` | `400`, `409`, `422` | No AI, n8n, pgvector, embeddings, memory commit, OCR, sadaqa, or wallet persistence. |
| GET | `/api/imperium/vault/transactions` | `CurrentUserDep`, current-user scoped | Not required | read-only | `items`, `count`, `limit`, `offset`, `safe_explanation` | `200`, `422` | No `db.add`, `flush`, `commit`, AI, n8n, pgvector, embeddings, memory commit, OCR, sadaqa, or wallet persistence. |
| GET | `/api/imperium/vault/transactions/{transaction_id}` | `CurrentUserDep`, current-user scoped | Not required | read-only | `transaction`, `safe_explanation` | `200`, `404` | No `db.add`, `flush`, `commit`, AI, n8n, pgvector, embeddings, memory commit, OCR, sadaqa, or wallet persistence. |
| POST | `/api/imperium/vault/transactions/{transaction_id}/reverse` | `CurrentUserDep`, current-user scoped | Required | append-only correction write | `transaction`, `reversal_summary` | `201`, `400`, `404`, `409`, `422` | No update/delete of the original row; no AI, n8n, pgvector, embeddings, memory commit, OCR, sadaqa, or wallet persistence. |
| GET | `/api/imperium/vault/summary` | `CurrentUserDep`, current-user scoped | Not required | read-only | `currency`, totals, counts, `safe_explanation` | `200`, `422` | No `db.add`, `flush`, `commit`, AI, n8n, pgvector, embeddings, memory commit, OCR, sadaqa, or wallet persistence. |
| GET | `/api/imperium/vault/summary/categories` | `CurrentUserDep`, current-user scoped | Not required | read-only | `currency`, `items`, `count`, `safe_explanation` | `200`, `422` | No `db.add`, `flush`, `commit`, AI, n8n, pgvector, embeddings, memory commit, OCR, sadaqa, or wallet persistence. |
| GET | `/api/imperium/vault/summary/monthly` | `CurrentUserDep`, current-user scoped | Not required | read-only | `currency`, `items`, `count`, `safe_explanation` | `200`, `422` | No `db.add`, `flush`, `commit`, AI, n8n, pgvector, embeddings, memory commit, OCR, sadaqa, or wallet persistence. |

Audit-ready invariants:
- The Vault ledger is append-only.
- Vault transactions are immutable after insert.
- The only correction path is `POST /api/imperium/vault/transactions/{transaction_id}/reverse`.
- No PUT/PATCH/DELETE endpoint exists under `/api/imperium/vault/transactions`.
- All Vault endpoints are scoped through `CurrentUserDep`.
- None of the Vault 9H routes persist AI, n8n, OCR, sadaqa, wallet, balance, pgvector, embedding, or memory state.

#### Vault 9J UTC Temporal Semantics

Patch 9J fixes the audit 9I temporal ambiguity without adding endpoints, migrations, or local-time reporting.

- Vault V1 uses UTC temporal semantics.
- `occurred_at` is the only authoritative temporal source for Vault V1 summaries and filters.
- `GET /api/imperium/vault/summary/monthly` groups by the UTC month of `occurred_at` and returns `YYYY-MM`.
- `occurred_from` and `occurred_to` are timezone-aware UTC-normalized bounds on `occurred_at`.
- Transactions near a user's local monthly boundary can fall into the adjacent UTC month.
- Patch 9J does not introduce `local_date` or timezone-based reporting semantics. Existing compatibility columns must not drive Vault V1 summaries.
- Any future local-month or timezone-aware financial reporting must be a dedicated patch with its own migration and contract update.
- Summary endpoints share the same currency contract: exactly three ASCII letters are accepted, invalid values such as `US1` or `EURO` return `422`, and accepted values are normalized uppercase.

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

#### Pulse Foundation 11A - append-only daily entries

Patch 11A introduces the first backend-owned Pulse surface under `/api/imperium/pulse`.

Purpose:
- record simple daily facts for sleep, energy, fatigue, weight, workout, and notes
- keep Pulse practical while the user is busy
- preserve the backend as source of truth without creating health strategy, coaching, or hidden scoring

Implemented endpoints:

Pulse V1 11A->11D active backend surface is only the five `/api/imperium/pulse/...`
endpoints below. No `/api/pulse/...` route is implemented by Pulse V1 11A->11D.

| method | endpoint | purpose | idempotency |
|---|---|---|---|
| POST | `/api/imperium/pulse/entries` | Create one current-user Pulse daily entry | Required `Idempotency-Key` |
| GET | `/api/imperium/pulse/entries` | List current-user Pulse entries with optional `date_from`, `date_to`, `limit`, `offset` | Not required; read-only |
| GET | `/api/imperium/pulse/entries/{entry_id}` | Read one current-user Pulse entry by id | Not required; read-only |
| GET | `/api/imperium/pulse/today` | Read-only Pulse entry view for current user on backend current date or explicit `date` query param | Not required; read-only |
| GET | `/api/imperium/pulse/stats/summary` | Read-only deterministic Pulse summary stats for current user with optional `date_from`, `date_to` | Not required; read-only |

Contracts:
- all endpoints are JWT-scoped through `CurrentUserDep`
- client-provided `user_id` is forbidden
- `POST /api/imperium/pulse/entries` requires `entry_date`
- at least one business field is required: `sleep_hours`, `energy_level`, `fatigue_level`, `weight_kg`, `workout_done`, `workout_type`, or `notes`
- `sleep_hours` must be between `0` and `24`
- `energy_level` and `fatigue_level` must be between `1` and `10`
- `weight_kg` must be greater than `0`
- `workout_type` is forbidden when `workout_done=false`
- `notes` is trimmed and limited to 1000 characters
- one entry per `(user_id, entry_date)`
- repeating the same `Idempotency-Key` with the same payload returns the original result
- repeating the same `Idempotency-Key` with a different payload returns `409`
- idempotence is guaranteed for sequential replay of the same key and same normalized payload
- strictly concurrent replays of the same key/payload may return `409` in V1 if PostgreSQL uniqueness constraints win the race before the completed idempotency row is readable
- attempting the same `entry_date` with another idempotency key returns `409`
- there is no update, merge, destructive edit, or automatic recalculation in Patch 11A

#### Pulse Today Entry View 11B - read-only date lookup

Patch 11B adds:
- `GET /api/imperium/pulse/today`

Contract:
- read-only endpoint
- JWT-scoped via `CurrentUserDep`
- strict user scope: query uses `(user_id, entry_date)`
- query param `date` is optional; default is backend current date by repo convention
- response always includes:
  - `date`
  - `entry` object or `entry: null` when absent
  - `safe_explanation = "Pulse today entry for current user."`
- no `Idempotency-Key` required
- no automatic entry creation
- no entry mutation

Audit readiness boundaries:
- no AI
- no n8n
- no pgvector write
- no embeddings
- no memory commit
- no replanning
- no automatic scoring
- no automatic coaching
- no health score
- no automatic recommendations
- no automatic synchronization with Mission, Vault, Path, calendar, or any other module
- no AI/n8n/scoring/coaching/calendar/memory/cross-module linkage

#### Pulse Summary Stats 11C - deterministic read-only aggregates

Patch 11C adds:
- `GET /api/imperium/pulse/stats/summary`

Purpose:
- provide deterministic read-only Pulse aggregates for the current user over an optional date range
- report raw summary numbers only, with no interpretation layer

Contracts:
- endpoint is GET only
- endpoint is JWT-scoped via `CurrentUserDep`
- endpoint is strict user-scoped (`user_id == current_user.id`)
- `date_from` and `date_to` are optional query params
- no `Idempotency-Key` required
- endpoint is strict read-only: no `db.add`, `flush`, or `commit`
- `entry_count` = count of entries in period
- averages ignore null values:
  - `average_sleep_hours`
  - `average_energy_level`
  - `average_fatigue_level`
- `latest_weight_kg` uses deterministic ordering on period rows:
  - `entry_date DESC`
  - `created_at DESC`
  - `id ASC` (stable tie-break)
  - then first non-null `weight_kg`
- `workout_count` counts only entries where `workout_done = true`
- if no rows exist:
  - `entry_count = 0`
  - averages are `null`
  - `latest_weight_kg = null`
  - `workout_count = 0`
- `safe_explanation` must be `Pulse summary statistics for current user.`

11C boundaries:
- no health score
- no coaching
- no recommendations
- no cross-module linkage
- no real AI call
- no n8n AI Agent
- no n8n DB write
- no pgvector write
- no embeddings
- no automatic memory commit
- no automatic replanning
- no automatic scoring
- no automatic coaching
- no automatic recommendations
- no automatic Mission/Vault/Path linkage

#### Pulse Contract Consolidation 11D - audit readiness

Patch 11D does not add behavior. It consolidates the final Pulse contract so audit review can verify the stable surface in one place.

| method | endpoint | objective | Idempotency-Key | access scope | mode | public safe fields | main errors | allowed / forbidden side effects |
|---|---|---|---|---|---|---|---|---|
| POST | `/api/imperium/pulse/entries` | Create one current-user Pulse daily entry. | Required | `CurrentUserDep` | append-only write | `id`, `entry_date`, `sleep_hours`, `energy_level`, `fatigue_level`, `weight_kg`, `workout_done`, `workout_type`, `notes`, `created_at`, `updated_at` | `201`, `400`, `409`, `422` | Allowed: append one row, persist idempotency record, return original response on replay with same key/payload. Forbidden: updates, deletes, AI, n8n, pgvector, embeddings, memory commit, calendar replanning, scoring, coaching, recommendations, Mission/Vault/Path linkage. |
| GET | `/api/imperium/pulse/entries` | List current-user Pulse entries with optional `date_from`, `date_to`, `limit`, `offset`. | Not required | `CurrentUserDep` | read-only | `items`, `count`, `limit`, `offset`, `safe_explanation` | `200`, `422` | Allowed: read only. Forbidden: `db.add`, `flush`, `commit`, auto-creation, AI, n8n, pgvector, embeddings, memory commit, calendar replanning, scoring, coaching, recommendations, Mission/Vault/Path linkage. |
| GET | `/api/imperium/pulse/entries/{entry_id}` | Read one current-user Pulse entry by id. | Not required | `CurrentUserDep` | read-only | `id`, `entry_date`, safe entry fields, `created_at`, `updated_at` | `200`, `404` | Allowed: read only. Forbidden: `db.add`, `flush`, `commit`, AI, n8n, pgvector, embeddings, memory commit, calendar replanning, scoring, coaching, recommendations, Mission/Vault/Path linkage. |
| GET | `/api/imperium/pulse/today` | Read-only Pulse entry view for current user on backend current date or explicit `date` query param. | Not required | `CurrentUserDep` | read-only | `date`, `entry`, `safe_explanation` | `200` | Allowed: read only. Forbidden: automatic entry creation, AI, n8n, pgvector, embeddings, memory commit, calendar replanning, scoring, coaching, recommendations, Mission/Vault/Path linkage. |
| GET | `/api/imperium/pulse/stats/summary` | Read-only deterministic Pulse summary stats for current user with optional `date_from`, `date_to`. | Not required | `CurrentUserDep` | read-only | `entry_count`, averages, `latest_weight_kg`, `workout_count`, `safe_explanation` | `200`, `422` | Allowed: read only. Forbidden: automatic scoring, automatic coaching, automatic recommendations, AI, n8n, pgvector, embeddings, memory commit, calendar replanning, Mission/Vault/Path linkage. |

Pulse 11D audit invariants:

- no automatic entry creation
- no automatic scoring
- no automatic coaching
- no automatic recommendations
- no automatic scoring/coaching/recommendations
- no automatic Mission/Vault/Path linkage
- no AI
- no n8n
- no pgvector writes
- no embeddings
- no memory commit
- no calendar replanning
- `POST /api/imperium/pulse/entries` remains append-only and idempotent by `Idempotency-Key`
- `GET` routes remain user-scoped through `CurrentUserDep` and read-only

#### Future Pulse surfaces - FUTURE / NOT IMPLEMENTED in Pulse V1 11A->11D

The items below are retained as future product ideas only. They are not active
backend contracts, are outside Pulse V1 11A->11D scope, and must not be
interpreted as implemented endpoints.

| status | method | endpoint | future purpose | future event |
|---|---|---|---|---|
| FUTURE / NOT IMPLEMENTED | GET | `/api/pulse/dashboard` | Biological profile, health score, workout/nutrition summary | `pulse.dashboard.requested` |
| FUTURE / NOT IMPLEMENTED | POST | `/api/pulse/biological-profile/correction` | User correction to biological truth | `biological.profile.corrected` |
| FUTURE / NOT IMPLEMENTED | POST | `/api/pulse/workout/generate` | Generate today's workout | `workout.generate.requested` |
| FUTURE / NOT IMPLEMENTED | POST | `/api/pulse/workout/adapt` | Adapt workout to reality | `workout.adaptation.requested` |
| FUTURE / NOT IMPLEMENTED | POST | `/api/pulse/stock-items` | Create/update stock item | `stock.item.changed` |
| FUTURE / NOT IMPLEMENTED | POST | `/api/pulse/grocery-list/generate` | Generate grocery list | `grocery.list.generated` |
| FUTURE / NOT IMPLEMENTED | POST | `/api/pulse/batch-cooking/validate` | Validate cooked quantities | `batch.cooking.validated` |
| FUTURE / NOT IMPLEMENTED | POST | `/api/pulse/wearable/sync` | Store wearable data if available | `wearable.data.synced` |

### The Path

Patch 10I routing decision:
- The canonical Path V1 API module is `app/api/v1/routes/imperium_path.py`.
- Canonical Path V1 endpoints live under `/api/imperium/path/...` and use the habit/check-in contracts below.
- `imperium_path.py` is the canonical owner of `GET /api/imperium/path/today`.
- Legacy Path item endpoints that still exist in `app/api/v1/routes/imperium.py` are deprecated for Path V1 and must not mask canonical Path V1 routes.
- In particular, `GET /api/imperium/path/today` must resolve only to the `imperium_path.py` handler returning `PathTodayResponse`, not the legacy list-shaped `ImperiumPathItem` response.
- If legacy Path item endpoints remain mounted for older Imperium workflows, they are compatibility surfaces only and must not introduce new Path V1 behavior.

#### Path Foundation 10A - habits and check-ins

Path Foundation 10A adds the first backend-owned habit/check-in surface for The Path.

Purpose:
- record practical worship/discipline habits owned by the authenticated user
- record explicit daily/weekly check-ins for those habits
- keep the apps as interfaces: they collect and display, while the backend enforces ownership and idempotency

Implemented endpoints:

| method | endpoint | purpose | idempotency |
|---|---|---|---|
| GET | `/api/imperium/path/today` | Read-only Path day view for the current user, including active habits and same-day check-ins | Not required; read-only |
| GET | `/api/imperium/path/stats/summary` | Read-only Path stats summary for the current user | Not required; read-only |
| POST | `/api/imperium/path/habits` | Create a Path habit for the current user | Required `Idempotency-Key` |
| GET | `/api/imperium/path/habits` | List current-user habits, optionally filtered by `is_active` and `domain` | Not required; read-only |
| GET | `/api/imperium/path/habits/{habit_id}` | Read one current-user Path habit detail by id | Not required; read-only |
| POST | `/api/imperium/path/habits/{habit_id}/archive` | Archive one current-user habit without deleting history | Required `Idempotency-Key` |
| POST | `/api/imperium/path/habits/{habit_id}/reactivate` | Reactivate one current-user habit without deleting history | Required `Idempotency-Key` |
| POST | `/api/imperium/path/habits/{habit_id}/check-ins` | Create one check-in for a current-user active habit | Required `Idempotency-Key` |
| GET | `/api/imperium/path/check-ins` | List current-user check-ins, optionally filtered by `habit_id`, `status`, `date_from`, `date_to` | Not required; read-only |
| GET | `/api/imperium/path/check-ins/{check_in_id}` | Read one current-user Path check-in detail by id | Not required; read-only |

Canonical route keys:
- `GET /api/imperium/path/today`
- `GET /api/imperium/path/stats/summary`
- `POST /api/imperium/path/habits`
- `GET /api/imperium/path/habits`
- `GET /api/imperium/path/habits/{habit_id}`
- `POST /api/imperium/path/habits/{habit_id}/archive`
- `POST /api/imperium/path/habits/{habit_id}/reactivate`
- `POST /api/imperium/path/habits/{habit_id}/check-ins`
- `GET /api/imperium/path/check-ins`
- `GET /api/imperium/path/check-ins/{check_in_id}`

Contracts:
- all endpoints are JWT-scoped through `CurrentUserDep`
- all GET endpoints are read-only and do not require `Idempotency-Key`
- all POST endpoints require `Idempotency-Key`
- habit create payload accepts `title`, `description`, `domain`, and `frequency`; client-provided `user_id` is forbidden
- blank habit `title` is rejected
- supported habit `frequency`: `daily`, `weekly`
- supported check-in `status`: `done`, `missed`
- missed requires reason
- `done` check-ins must not send `reason`; use `note` for comments
- habit and check-in reads never expose another user's records
- `GET /api/imperium/path/today` is read-only, user-scoped, and returns active habits with same-day check-in status only
- `GET /api/imperium/path/today` returns `pending` when no check-in exists, `done` when a `done` check-in exists, and `missed` when a `missed` check-in exists
- `GET /api/imperium/path/today` never creates a check-in automatically
- `GET /api/imperium/path/stats/summary` counts only existing `done` and `missed` check-ins
- check-ins for non-owned habits return 404
- check-ins for inactive habits return 409
- duplicate `habit_id` plus `check_date` with another idempotency key returns 409
- repeating the same `Idempotency-Key` with the same payload returns the original result
- repeating the same `Idempotency-Key` with a different payload returns 409

Audit readiness boundaries:
- no AI/n8n/scoring/calendar in Path
- no pgvector write
- no embeddings
- no automatic memory commit
- no automatic replanning
- no automatic scoring
- no automatic mission/vault linkage
- no automatic sadaqa calculation or Vault decision is triggered by these endpoints
- no automatic check-in creation in `GET /api/imperium/path/today`
- no AI/n8n/scoring/calendar in `GET /api/imperium/path/today`

#### Path Habit Detail 10D - read-only habit detail by id

Path Habit Detail 10D adds deterministic read access for one Path habit owned by the current user.

Purpose:
- read one habit detail by `habit_id` for the authenticated user
- keep strict current-user ownership rules
- preserve read-only behavior with no side effects

Implemented endpoint:

| method | endpoint | purpose | idempotency |
|---|---|---|---|
| GET | `/api/imperium/path/habits/{habit_id}` | Read-only current-user Path habit detail by id | Not required; read-only |

Contracts:
- endpoint is JWT-scoped through `CurrentUserDep`
- missing habit returns `404`
- non-owned habit returns `404`
- no `Idempotency-Key` required
- endpoint is read-only: no `db.add`, `flush`, `commit`
- endpoint never creates a check-in
- endpoint never invokes AI, n8n, pgvector, embeddings, memory commit, calendar, or scoring
- response is deterministic and uses safe public fields only
- `safe_explanation` must be `Path habit detail for current user.`

#### Path Today View 10B - read-only daily snapshot

Path Today View 10B exposes a deterministic read-only snapshot of the current user's active Path habits for a given date.

Purpose:
- show active habits for the current user on a selected day
- attach the same-day check-in when one exists
- expose public status only: `pending/done/missed`
- keep the endpoint read-only so it never creates or mutates check-ins

Implemented endpoint:

| method | endpoint | purpose | idempotency |
|---|---|---|---|
| GET | `/api/imperium/path/today` | Read-only current-user Path day view with optional `date`, `domain`, and `frequency` filters | Not required; read-only |

Contracts:
- default `date` uses the backend Europe/Paris helper; query `date` overrides the Europe/Paris default
- `domain` and `frequency` are optional filters
- active habits only are returned
- check-in lookup is done for the selected date only
- `pending` is returned when no check-in exists
- `done` is returned when a `done` check-in exists
- `missed` is returned when a `missed` check-in exists
- the endpoint never creates a check-in automatically
- the endpoint never invokes AI, n8n, pgvector, embeddings, memory commit, calendar replanning, or scoring
- the endpoint is user-scoped and never exposes another user's habit/check-in data

#### Path Check-in Detail 10E - read-only check-in detail by id

Path Check-in Detail 10E adds deterministic read access for one Path check-in owned by the current user.

Purpose:
- read one check-in detail by `check_in_id` for the authenticated user
- keep strict current-user ownership rules
- preserve read-only behavior with no side effects

Implemented endpoint:

| method | endpoint | purpose | idempotency |
|---|---|---|---|
| GET | `/api/imperium/path/check-ins/{check_in_id}` | Read-only current-user Path check-in detail by id | Not required; read-only |

Contracts:
- endpoint is JWT-scoped through `CurrentUserDep`
- missing check-in returns `404`
- non-owned check-in returns `404`
- no `Idempotency-Key` required
- endpoint is read-only: no `db.add`, `flush`, `commit`
- endpoint never creates any check-in automatically
- endpoint never modifies any habit or check-in
- endpoint never invokes AI, n8n, pgvector, embeddings, memory commit, calendar, or scoring
- response is deterministic and uses safe public fields only
- `safe_explanation` must be `Path check-in detail for current user.`

#### Path Stats Summary 10F - deterministic aggregated summary

Path Stats Summary 10F adds a read-only deterministic summary for the current user's Path habits and existing check-ins.

Purpose:
- report simple Path stats for the current user
- support optional filtering by date range, domain, and frequency
- count only existing `done` and `missed` check-ins
- exclude implicit `pending` items from the completion rate

Implemented endpoint:

| method | endpoint | purpose | idempotency |
|---|---|---|---|
| GET | `/api/imperium/path/stats/summary` | Read-only current-user Path stats summary with optional `date_from`, `date_to`, `domain`, and `frequency` filters | Not required; read-only |

Contracts:
- endpoint is JWT-scoped through `CurrentUserDep`
- endpoint is user-scoped and never exposes another user's habits or check-ins
- `total_active_habits` counts only active habits and applies `domain` and `frequency` filters when present
- `done_count` and `missed_count` count only existing check-ins with status `done` or `missed`
- `check_in_count = done_count + missed_count`
- `completion_rate_percent = 0` when `check_in_count = 0`
- otherwise `completion_rate_percent = round(done_count / check_in_count * 100, 2)`
- `date_from` and `date_to` only filter check-ins, not active habit counting
- `domain` and `frequency` are applied to both the active-habit aggregate and the check-in aggregate
- check-ins linked to inactive habits remain countable when the `domain` and `frequency` filters match
- no `Idempotency-Key` is required
- the endpoint is read-only: no `db.add`, `flush`, or `commit`
- the endpoint never creates a check-in automatically
- the endpoint never invokes AI, n8n, pgvector, embeddings, memory commit, calendar replanning, or scoring
- the endpoint never links Mission or Vault automatically
- `safe_explanation` must be `Path summary stats computed from current user's habits and check-ins.`

10F boundaries:
- no AI/n8n/scoring/calendar in 10F
- no pgvector write
- no embeddings
- no automatic memory commit
- no automatic replanning
- no automatic scoring
- pending implicits are excluded in 10F

#### Path Habit Lifecycle 10C - archive and reactivate

Path Habit Lifecycle 10C adds safe lifecycle control for Path habits without destroying history.

Purpose:
- archive a habit by turning it inactive without deleting the habit row
- reactivate a habit by turning it active again without recreating history
- preserve all existing check-ins and historical data
- keep the endpoint deterministic and replay-safe with idempotency

Implemented endpoints:

| method | endpoint | purpose | idempotency |
|---|---|---|---|
| POST | `/api/imperium/path/habits/{habit_id}/archive` | Archive the current user's habit without deleting history | Required `Idempotency-Key` |
| POST | `/api/imperium/path/habits/{habit_id}/reactivate` | Reactivate the current user's habit without deleting history | Required `Idempotency-Key` |

Contracts:
- both endpoints are JWT-scoped through `CurrentUserDep`
- habit not found or not owned returns 404
- archive sets `is_active=false` when the habit is active
- archive is replay-safe when the habit is already inactive and returns `already_archived`
- reactivate sets `is_active=true` when the habit is inactive
- reactivate is replay-safe when the habit is already active and returns `already_active`
- same idempotency key with same payload returns the original result
- same idempotency key with a different payload returns 409
- check-ins are never deleted
- the habit row is never deleted
- the endpoints never call AI, n8n, pgvector, embeddings, memory commit, calendar, or scoring
- the response includes a public habit plus a lifecycle summary with guardrails
- `safe_explanation` must be `Path habit lifecycle updated without deleting history.`

Lifecycle response shape:

```json
{
  "habit": {
    "id": "uuid",
    "title": "Fajr on time",
    "description": "Pray before sunrise",
    "domain": "worship",
    "frequency": "daily",
    "is_active": false,
    "created_at": "2026-05-25T08:00:00Z",
    "updated_at": "2026-05-25T08:00:00Z"
  },
  "lifecycle_summary": {
    "status": "archived",
    "guardrails_checked": [
      "OWNERSHIP_CONFIRMED",
      "IDEMPOTENCY_KEY_ACCEPTED"
    ],
    "safe_explanation": "Path habit lifecycle updated without deleting history."
  }
}
```

Lifecycle status values:
- `archived`
- `reactivated`
- `already_archived`
- `already_active`

10C boundaries:
- no deletion of habits
- no deletion of check-ins
- no AI/n8n/scoring/calendar
- no pgvector write
- no embeddings
- no automatic memory commit
- no vault logic
- no mission replanning

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

These event types are FUTURE / NOT IMPLEMENTED for Pulse V1 11A->11D unless a
later patch explicitly promotes one into the active backend contract.

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
- `imperium_pulse_entries`
- FUTURE / NOT IMPLEMENTED in Pulse V1 11A->11D: `pulse_biological_profiles`
- FUTURE / NOT IMPLEMENTED in Pulse V1 11A->11D: `pulse_health_scores`
- FUTURE / NOT IMPLEMENTED in Pulse V1 11A->11D: `pulse_workouts`
- FUTURE / NOT IMPLEMENTED in Pulse V1 11A->11D: `pulse_stock_items`
- FUTURE / NOT IMPLEMENTED in Pulse V1 11A->11D: `pulse_grocery_lists`
- FUTURE / NOT IMPLEMENTED in Pulse V1 11A->11D: `pulse_batch_cooking_sessions`
- FUTURE / NOT IMPLEMENTED in Pulse V1 11A->11D: `wearable_data_points`
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
- FUTURE / NOT IMPLEMENTED in Pulse V1 11A->11D: Pulse biological pattern summaries
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

- status available is contract metadata only and is not a health check

### Imperium Frontend Navigation Config V1

`GET /api/imperium/frontend/navigation`

Purpose:
- return frontend navigation metadata only for Imperium main navigation
- provide static deterministic V1 navigation config for frontend routing
- avoid dynamic route discovery and runtime route scans

Rules:
- GET only
- JWT-scoped via `CurrentUserDep`
- no `Idempotency-Key` required
- metadata only
- no business data read
- no writes
- no auto-creation
- not a health check
- not a dynamic discovery mechanism
- no dynamic route scan
- no AI, n8n, OCR, scoring, coaching, or recommendations
- no cross-module write
- no user_id exposure
- no secrets/providers/infra metadata

Response contract:
- `navigation_version` is `v1`
- `read_only` is always `true`
- deterministic `items[]` ordered by `order`: `home`, `dashboard`, `daily_plan`, `missions`, `vault`, `path`, `pulse`
- each `items[]` element includes: `key`, `label`, `route`, `api_endpoint`, `order`, `enabled`
- `enabled` is always `true` in V1
- `safe_explanation`
