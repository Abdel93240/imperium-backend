# 28 - Daily Plan Workflow

## Scope

Imperium Daily Plan V1 stores and retrieves a deterministic daily plan snapshot.

It does not:

- call AI or LLMs
- trigger n8n workflows
- send notifications
- select missions automatically
- invent tasks
- schedule times automatically
- make cross-domain decisions

The plan is built from existing backend truth only:

- current active mission, if present
- existing path items for the selected `local_date`
- top active priority rules as context
- latest day review reference, if present

## Canonical Day Start

The canonical start-of-day contract is
[`DECISION_demarrage_journee.md`](../gap_analysis_v1/DECISION_demarrage_journee.md).
This document describes the daily-plan snapshot layer; it does not itself make an
AI call. The operational flow is nevertheless fixed:

- A day starts only when the user explicitly clicks **"Démarrer la journée"**;
  no clock, wake-time, or first-open event starts it.
- Before that click, the current-mission state is **"Journée non démarrée"** and
  the programme du jour is hidden. A mission left active yesterday is not shown
  as today's active mission.
- At the click, the only check-in input is the user's subjective feeling. The
  deterministic selector reads the current plan in under 500 ms, then performs
  freshness checks (calendar changes, unfinished prior-day missions, and recent
  constraints). It invokes `local_executor` through scoring only for a
  conflict or infeasibility. A `high_reasoning` regeneration is exceptional
  and requires user validation; role assignments are defined in doc 30 §3.
- The operational day runs from this start to its closure and may pass midnight
  (up to roughly 36 hours). `local_date` remains a snapshot/display attribute;
  it must not be used to infer that an operational day has ended.

Energy is deliberately two-dimensional: objective energy is estimated
deterministically from wearable sleep, Pulse declarations (nutrition, caffeine,
hydration), and prior-day load; subjective energy is the check-in feeling. The
selected capacity is the lower value, and their difference is retained as an
algorithm-calibration signal.

Prayer awareness zones note (future brain planning): when daily planning becomes
brain-generated/replanned, prayer awareness zones are part of the generated plan
and are recomputed on every re-plan. They are not a separate prayer scheduler;
they inherit the daily plan lifecycle (see doc 41 §7-bis).

## Database Table

Canonical table: `imperium_daily_plans`

Columns:

- `id`: UUID primary key
- `user_id`: canonical user FK
- `local_date`: user-local date
- `timezone`: defaults to `Europe/Paris`
- `plan_status`: `draft`, `active`, `completed`, or `cancelled`
- `title`: optional
- `summary`: optional
- `focus_priority_key`: optional
- `current_mission_id`: nullable FK to `imperium_missions.id`
- `generated_from`: JSONB object with source IDs
- `plan_blocks`: JSONB array
- `notes`: optional
- `created_at`, `updated_at`: UTC timestamps

Constraints:

- one snapshot per `user_id` and `local_date` (legacy display/snapshot constraint;
  it must never determine the operational-day boundary)
- `plan_status` allowed values only
- `plan_blocks` must be a JSON array

## Endpoints

All endpoints require JWT authentication.

### Create Daily Plan

`POST /api/imperium/day/plan`

Headers:

```text
Authorization: Bearer <access_token>
Idempotency-Key: <unique_key>
```

Payload:

```json
{
  "local_date": "2026-04-26",
  "timezone": "Europe/Paris",
  "title": "Sunday plan",
  "summary": "Manual daily plan snapshot",
  "focus_priority_key": "admin",
  "notes": "No AI planning in V1."
}
```

Behavior:

- Creates a `draft` plan.
- Appends `day.plan.created`.
- Uses authenticated `user_id`.
- If the same idempotency key is retried with the same payload, returns the original response.
- If a plan already exists for the same `local_date` with a different idempotency key, returns `409`.

### Get Today Plan

`GET /api/imperium/day/plan/today`

Behavior:

- Resolves the currently started operational day; it must not infer "today" from
  the civil date alone. `Europe/Paris` remains the V1 display timezone.
- Returns `404` if no plan exists.

### Get Plan By Date

`GET /api/imperium/day/plan?local_date=YYYY-MM-DD`

Behavior:

- Returns the plan for that date.
- Returns `404` if no plan exists.

The `404` behavior matches existing Imperium read endpoints such as current mission and latest day review.

### Activate Plan

`POST /api/imperium/day/plan/{plan_id}/activate`

Behavior:

- Requires `Idempotency-Key`.
- Moves `draft` to `active`.
- Appends `day.plan.activated`.
- Returns `409` for invalid state transition.

### Complete Plan

`POST /api/imperium/day/plan/{plan_id}/complete`

Behavior:

- Requires `Idempotency-Key`.
- Moves `draft` or `active` to `completed`.
- Appends `day.plan.completed`.

### Cancel Plan

`POST /api/imperium/day/plan/{plan_id}/cancel`

Behavior:

- Requires `Idempotency-Key`.
- Moves `draft` or `active` to `cancelled`.
- Appends `day.plan.cancelled`.

## Generated Fields

Example `generated_from`:

```json
{
  "current_mission_id": "uuid-or-null",
  "path_item_ids": ["uuid"],
  "priority_rule_ids": ["uuid"],
  "latest_day_review_id": "uuid-or-null"
}
```

Example `plan_blocks`:

```json
[
  {
    "block_type": "current_mission",
    "source_id": "uuid",
    "title": "Finish backend workflow",
    "category": "backend",
    "status": "active",
    "planned_start": null,
    "planned_end": null
  },
  {
    "block_type": "path_item",
    "source_id": "uuid",
    "title": "Manual admin task",
    "category": "admin",
    "priority_key": "admin",
    "status": "planned",
    "sort_order": 1,
    "planned_start": "2026-04-26T10:00:00Z",
    "planned_end": null
  },
  {
    "block_type": "priority_context",
    "priorities": []
  }
]
```

No task is invented. Times are copied only from existing path items or missions.

## Dashboard

`GET /api/imperium/dashboard` now includes:

```json
{
  "daily_plan_today": null
}
```

If a plan exists for today, it returns the daily plan response object.

## Deployment Commands

Run migrations against `imperium_core`, never `n8n_db`.

```bash
cd /root/imperium

set -a
. /etc/imperium/imperium-api.env
set +a

docker compose -f docker-compose.imperium.yml build imperium-api

docker compose -f docker-compose.imperium.yml run --rm \
  -e DATABASE_URL='postgresql+psycopg://imperium_admin:ADMIN_PASSWORD@31.97.52.42:5432/imperium_core' \
  imperium-api alembic upgrade head

docker compose -f docker-compose.imperium.yml up -d imperium-api

curl -sS http://127.0.0.1:8000/api/health
curl -sS http://127.0.0.1:8000/api/health/db
```

## Live Test Commands

```bash
API_BASE='http://127.0.0.1:8000/api'
TOKEN='<ACCESS_TOKEN>'
IDEM_PLAN="daily_plan_$(date -u +%Y%m%dT%H%M%SZ)"

curl -i -X POST "$API_BASE/imperium/day/plan" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: $IDEM_PLAN" \
  -H "Content-Type: application/json" \
  -d '{
    "local_date": "2026-04-26",
    "timezone": "Europe/Paris",
    "title": "Manual daily plan",
    "summary": "Deterministic V1 snapshot",
    "notes": "No AI."
  }'

curl -i -X POST "$API_BASE/imperium/day/plan" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: $IDEM_PLAN" \
  -H "Content-Type: application/json" \
  -d '{
    "local_date": "2026-04-26",
    "timezone": "Europe/Paris",
    "title": "Manual daily plan",
    "summary": "Deterministic V1 snapshot",
    "notes": "No AI."
  }'

curl -i "$API_BASE/imperium/day/plan?local_date=2026-04-26" \
  -H "Authorization: Bearer $TOKEN"

curl -i "$API_BASE/imperium/day/plan/today" \
  -H "Authorization: Bearer $TOKEN"

curl -i "$API_BASE/imperium/dashboard" \
  -H "Authorization: Bearer $TOKEN"
```

Expected checks:

- unauthenticated create/read returns `401`
- valid create returns `201`
- duplicate idempotency key returns same stored response and no duplicate event
- second plan for same date with new idempotency key returns `409`
- activation/completion/cancellation append events
- dashboard includes `daily_plan_today`
- `n8n_db` is not touched
