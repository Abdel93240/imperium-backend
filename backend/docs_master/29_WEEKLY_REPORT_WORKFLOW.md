# 29 - Weekly Report Workflow

## Scope

Imperium Weekly Report V1 is a deterministic read-only report.

It does not:

- call AI
- trigger n8n
- write database rows
- emit events
- send notifications
- create plans or missions
- make new business decisions

The endpoint reads existing V1 tables for the authenticated user only.

## Endpoint

`GET /api/imperium/report/week?week_start=YYYY-MM-DD`

Authentication:

- JWT required

Rules:

- `week_start` must be a Monday.
- Range is `week_start` inclusive to `week_start + 7 days` exclusive.
- Timezone context is `Europe/Paris`.
- Empty weeks return `200` with zero/default values.

## Source Tables

The report reads:

- `imperium_day_reviews`
- `imperium_missions`
- `imperium_priority_rules`
- `vault_transactions`
- `imperium_path_items`
- `imperium_daily_plans`

No migration is required.

## Response Shape

```json
{
  "week_start": "2026-04-20",
  "week_end": "2026-04-26",
  "timezone": "Europe/Paris",
  "days": {
    "total_days": 7,
    "reviewed_days": 0,
    "completed_days": 0,
    "partial_days": 0,
    "failed_days": 0,
    "average_energy_level": null,
    "average_fatigue_level": null,
    "average_sleep_quality": null,
    "average_stress_level": null
  },
  "missions": {
    "total": 0,
    "active": 0,
    "completed": 0,
    "failed": 0,
    "cancelled": 0,
    "recent": []
  },
  "path": {
    "total_items": 0,
    "planned": 0,
    "in_progress": 0,
    "completed": 0,
    "skipped": 0,
    "cancelled": 0,
    "completion_rate": null
  },
  "daily_plans": {
    "total": 0,
    "draft": 0,
    "active": 0,
    "completed": 0,
    "cancelled": 0
  },
  "vault": {
    "income_total": "0.00",
    "expense_total": "0.00",
    "net_total": "0.00",
    "currency": "EUR",
    "by_category": []
  },
  "priorities": [],
  "signals": {
    "discipline_signal": "unknown",
    "fatigue_signal": "unknown",
    "financial_signal": "unknown",
    "execution_summary": "0/7 days reviewed, 0/0 path items completed, net 0.00 EUR."
  }
}
```

## Deterministic Signals

`fatigue_signal`:

- `unknown`: no fatigue data
- `high`: average fatigue >= 7
- `medium`: average fatigue >= 4
- `low`: otherwise

`financial_signal`:

- `unknown`: no vault transactions
- `positive`: net total > 0
- `negative`: net total < 0
- `neutral`: net total = 0

`discipline_signal`:

- `unknown`: no path items and no day reviews
- `strong`: path completion rate >= 80 or completed days >= 5
- `medium`: path completion rate >= 50 or reviewed days >= 3
- `weak`: otherwise

## Deployment

No migration is needed for this workflow if the database is already at `20260426_0009`.

```bash
cd /root/imperium

unzip -o imperium_backend_deploy.zip -d /root/imperium

set -a
. /etc/imperium/imperium-api.env
set +a

docker compose -f docker-compose.imperium.yml build imperium-api
docker compose -f docker-compose.imperium.yml up -d imperium-api

curl -sS http://127.0.0.1:8000/api/health
curl -sS http://127.0.0.1:8000/api/health/db
```

## Live Tests

```bash
API_BASE='http://127.0.0.1:8000/api'
TOKEN='<ACCESS_TOKEN>'

curl -i "$API_BASE/imperium/report/week?week_start=2026-04-20"

curl -i "$API_BASE/imperium/report/week?week_start=2026-04-20" \
  -H "Authorization: Bearer $TOKEN"

curl -i "$API_BASE/imperium/dashboard" \
  -H "Authorization: Bearer $TOKEN"
```

Expected:

- unauthenticated weekly report returns `401`
- authenticated weekly report returns `200`
- non-Monday `week_start` returns `422`
- dashboard still returns `200`
- `n8n_db` is not touched
