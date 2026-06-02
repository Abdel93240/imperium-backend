# 26 - Priority Rules Workflow

## SUPERSEDED BY DECISION FRAMEWORK

Patch 7G supersedes `imperium_priority_rules` as a priority hierarchy source.

The canonical hierarchy is now `imperium_user_priorities`, owned by the
Decision Framework endpoints:

```text
GET  /api/imperium/decision-framework/priorities
POST /api/imperium/decision-framework/priorities
```

`imperium_priority_rules` remains legacy compatibility only. It must not be
used by dashboard, daily plan generation, mission scoring, or new planning
logic as the canonical priority order. Legacy read surfaces may project the
Decision Framework hierarchy for old clients, but legacy writes are disabled.

No legacy table is deleted in Patch 7G.

## Scope

Historically, Imperium V1 stored the user's explicit priority hierarchy in
`imperium_priority_rules`.

This workflow is retained only to document the legacy compatibility table. New
strategy, planning, scoring, dashboard, and daily-plan reads must use
`imperium_user_priorities` through the Decision Framework.

Not implemented in this workflow:

- AI planning
- automatic mission selection
- priority recommendations
- n8n workflow execution
- notifications
- Android UI

## Database Table

Legacy table: `imperium_priority_rules`

Purpose: historical compatibility storage for old priority settings.

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

Deprecated compatibility route. It projects the canonical Decision Framework
priority order and includes deprecation metadata.

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
  "status": "legacy_superseded",
  "deprecated": true,
  "legacy": true,
  "superseded_by": "/api/imperium/decision-framework/priorities",
  "canonical_source": "imperium_user_priorities",
  "message": "Legacy priority rules are superseded; Decision Framework priorities are canonical."
}
```

### Replace Full Priority Hierarchy

`POST /api/imperium/priorities`

Deprecated. Patch 7G disables legacy writes and returns `410 Gone`. Use
`POST /api/imperium/decision-framework/priorities`.

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

- Returns `410 Gone`.
- Does not create or update `imperium_priority_rules`.
- Points callers to `/api/imperium/decision-framework/priorities`.

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
- Authenticated `GET /api/imperium/priorities` returns a legacy projection of
  Decision Framework priorities ordered by `rank_order`.
- Authenticated `GET /api/imperium/priorities` includes `deprecated=true`,
  `legacy=true`, `canonical_source=imperium_user_priorities`, and
  `superseded_by=/api/imperium/decision-framework/priorities`.
- Authenticated `POST /api/imperium/priorities` returns `410 Gone`.
- Legacy `POST` creates no `priority.rules.updated` event.
- Legacy `POST` creates or updates no `imperium_priority_rules` rows.
- `n8n_db` is not touched.
