# 25 - Current Mission Workflow

## Scope

Imperium V1 supports one current mission at a time for the canonical user.

This workflow is backend-owned. Android apps may request mission actions and display the result, but the backend validates mission state, applies idempotency, writes PostgreSQL truth, and appends canonical events.

Not implemented in this workflow:

- AI mission selection
- scheduling intelligence
- priority hierarchy changes
- n8n workflow execution
- notifications
- Android UI
- automatic analysis of failure reasons

## Database Table

Canonical table: `imperium_missions`

Purpose: store the current and historical Imperium missions.

Important columns:

- `id`: UUID primary key
- `user_id`: canonical user FK
- `title`: mission title
- `category`: optional mission category
- `priority_level`: optional user/app-provided priority marker
- `status`: `active`, `completed`, `failed`, or `cancelled`
- `planned_start_at`: optional planned start timestamp
- `planned_end_at`: optional planned end timestamp
- `started_at`: actual backend-confirmed start timestamp
- `ended_at`: actual backend-confirmed end timestamp
- `completion_note`: optional completion note
- `failure_reason`: required when failing a mission
- `user_reported_signals`: JSONB signals reported by the user
- `ai_usable_reason`: boolean, default client value should be `true`
- `created_by_event_id`: FK to the start event row
- `ended_by_event_id`: FK to the completion/failure event row
- `created_at`, `updated_at`: UTC audit timestamps

Constraint:

- One active mission per user is enforced by a partial unique index on `user_id` where `status = 'active'`.

## Endpoints

All write endpoints require:

- JWT authentication
- `Idempotency-Key` header

### Start Mission

`POST /api/imperium/missions/start`

Payload:

```json
{
  "title": "Finish backend mission workflow",
  "category": "backend",
  "priority_level": 1,
  "planned_start_at": "2026-04-26T10:00:00Z",
  "planned_end_at": "2026-04-26T12:00:00Z"
}
```

Behavior:

- Creates an `active` mission.
- Appends `mission.started`.
- Returns `409` if another mission is already active.
- Replays the original response if the same idempotency key is retried with the same payload.

### Complete Mission

`POST /api/imperium/missions/{mission_id}/complete`

Payload:

```json
{
  "completion_note": "Finished cleanly."
}
```

Behavior:

- Requires the mission to exist and be `active`.
- Sets status to `completed`.
- Stores optional `completion_note`.
- Appends `mission.completed`.
- Returns `404` if mission is missing.
- Returns `409` if mission is not active.

### Fail Mission

`POST /api/imperium/missions/{mission_id}/fail`

Payload:

```json
{
  "failure_reason": "Fatigue was too high.",
  "user_reported_signals": {
    "fatigue_level": 9,
    "sleep_quality": 3
  },
  "ai_usable_reason": true
}
```

Behavior:

- Requires the mission to exist and be `active`.
- Requires explicit `failure_reason`.
- Stores raw `user_reported_signals`.
- Stores `ai_usable_reason` for future analysis.
- Appends `mission.failed`.
- Does not judge or reinterpret the reason in V1.

### Current Mission

`GET /api/imperium/missions/current`

Behavior:

- Returns the current active mission.
- Returns `404` if no active mission exists.

### Recent Missions

`GET /api/imperium/missions/recent?limit=10`

Behavior:

- Returns recent missions ordered by `started_at` descending.
- `limit` range: `1` to `50`.

## Event Rules

The backend appends canonical events only:

- `mission.started`
- `mission.completed`
- `mission.failed`

Events are append-only. Mission rows may change status from `active` to a terminal state, but event rows must not be updated.

Event payloads contain the sanitized mission action payload. `user_id` always comes from the authenticated JWT user, never from client-supplied data.

## Idempotency

Each write endpoint requires `Idempotency-Key`.

Duplicate behavior:

- Same key and same action payload: return the original stored response.
- Same key and different action payload: return `409`.
- Duplicate retries must not create another mission or append another event.

## V1 Boundaries

This workflow stores reality; it does not decide strategy.

Future workflows may analyze repeated failure reasons and mission patterns using PostgreSQL truth plus pgvector memory, but V1 only preserves the raw user-provided reason/signals for later.
