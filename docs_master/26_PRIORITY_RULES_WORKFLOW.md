# 26 - Priority Rules Workflow

## Scope

Imperium V1 stores the user's explicit priority hierarchy.

The backend does not hard-code life priorities and does not decide strategy from this table yet. Future planning/AI workflows may read these rules, but they must not silently rewrite them.

Not implemented in this workflow:

- AI planning
- automatic mission selection
- priority recommendations
- n8n workflow execution
- notifications
- Android UI

## Database Table

Canonical table: `imperium_priority_rules`

Purpose: store active and historical user-owned priority settings.

Columns:

- `id`: UUID primary key
- `user_id`: canonical user FK
- `priority_key`: stable key chosen by the user/app, for example `worship`, `health`, `family`, `money`, `project`, or a custom key
- `label`: display label
- `rank_order`: positive integer rank, where lower number means higher priority
- `importance_score`: optional integer from `1` to `100`
- `is_active`: active setting flag
- `updated_by_event_id`: nullable FK to the update event
- `created_at`, `updated_at`: UTC audit timestamps

Constraints:

- No duplicate active `rank_order` per user.
- No duplicate active `priority_key` per user.
- `rank_order` must be positive.
- `importance_score` must be null or between `1` and `100`.

Replacement behavior:

- A new hierarchy replacement deactivates old active rows.
- New active rows are inserted.
- Old rows are not deleted.
- The change is audited with `priority.rules.updated`.

## Endpoints

All endpoints require JWT authentication.

### Read Active Priority Rules

`GET /api/imperium/priorities`

Response:

```json
{
  "priorities": [
    {
      "id": "5e98f8a1-8e1a-46c8-b5fe-e30f98743724",
      "priority_key": "worship",
      "label": "Worship",
      "rank_order": 1,
      "importance_score": 100,
      "is_active": true,
      "updated_by_event_id": "4fa8b3b8-b9d5-4e91-9dfc-c75a85aabf5d",
      "created_at": "2026-04-26T10:00:00Z",
      "updated_at": "2026-04-26T10:00:00Z"
    }
  ],
  "event_id": null,
  "idempotency_key": null,
  "status": "ok"
}
```

### Replace Full Priority Hierarchy

`POST /api/imperium/priorities`

Headers:

```text
Authorization: Bearer <access_token>
Idempotency-Key: <unique_key>
```

Payload:

```json
{
  "priorities": [
    {
      "priority_key": "worship",
      "label": "Worship",
      "rank_order": 1,
      "importance_score": 100
    },
    {
      "priority_key": "health",
      "label": "Health",
      "rank_order": 2,
      "importance_score": 90
    },
    {
      "priority_key": "money",
      "label": "Money",
      "rank_order": 3,
      "importance_score": 80
    }
  ]
}
```

Validation:

- `priorities` cannot be empty.
- Maximum list length is `20`.
- `rank_order` must be a positive integer.
- Duplicate ranks are rejected.
- Duplicate priority keys are rejected.
- Custom labels and keys are allowed.

Behavior:

- Uses authenticated `user_id`; client-supplied `user_id` is not accepted.
- Appends `priority.rules.updated`.
- Deactivates old active rules and inserts the new hierarchy.
- Returns the active ordered priorities.
- Duplicate retry with same `Idempotency-Key` and same payload returns the original response.
- Same `Idempotency-Key` with different payload returns `409`.

## Event

Canonical event type:

```text
priority.rules.updated
```

Source app:

```text
imperium
```

Payload contains the submitted priority list.

Events remain append-only. Priority rows can be deactivated, but accepted events must not be updated or deleted.

## V1 Safety Rules

- The backend stores explicit user choices only.
- Priorities are not hard-coded in code.
- AI may read priorities later, but must not silently rewrite them.
- Replacements are auditable through events.
- This table is user-owned configuration, not AI memory.

## Deployment Commands

Run migrations against `imperium_core`, not `n8n_db`.

```bash
cd /root/imperium

set -a
. /etc/imperium/imperium-api.env
set +a

docker compose -f docker-compose.imperium.yml run --rm \
  -e DATABASE_URL='postgresql+psycopg://imperium_admin:ADMIN_PASSWORD@31.97.52.42:5432/imperium_core' \
  imperium-api alembic upgrade head

docker compose -f docker-compose.imperium.yml up -d --build imperium-api

curl -sS http://127.0.0.1:8000/api/health
curl -sS http://127.0.0.1:8000/api/health/db
```

## Manual Verification

Expected checks:

- Unauthenticated `GET /api/imperium/priorities` returns `401`.
- Unauthenticated `POST /api/imperium/priorities` returns `401`.
- Valid update returns `200`.
- Duplicate idempotency key returns the same response and creates no duplicate event.
- Duplicate rank returns `422`.
- Duplicate priority key returns `422`.
- `GET` returns active priorities ordered by `rank_order`.
- `events` contains `priority.rules.updated`.
- `n8n_db` is not touched.
