# 27 - Vault Transactions Workflow

## Scope

Vault V1 supports manual financial transaction capture and a live weekly summary.

Not implemented in this workflow:

- AI analysis
- n8n workflows
- bank sync
- notifications
- UI
- materialized weekly summaries
- wallet balance tables

The backend remains source of truth. The Vault stores declared financial reality; it must not invent money or treat future income as confirmed.

## Database Table

Canonical table: `vault_transactions`

Columns:

- `id`: UUID primary key
- `user_id`: canonical user FK
- `event_id`: nullable FK to `events.id`
- `occurred_at`: transaction timestamp
- `local_date`: user-local date
- `timezone`: user timezone
- `transaction_type`: `income`, `expense`, or `correction`
- `wallet`: `cash` or `bank`
- `category`: required category
- `label`: optional display label
- `amount`: numeric `12,2`, positive
- `currency`: defaults to `EUR`
- `notes`: optional notes
- `source_app`: defaults to `vault`
- `created_at`, `updated_at`: UTC audit timestamps

Constraints:

- `amount > 0`
- `transaction_type IN ('income', 'expense', 'correction')`
- `wallet IN ('cash', 'bank')`

Indexes:

- `(user_id, local_date)`
- `(user_id, occurred_at DESC)`
- `(user_id, transaction_type)`

## Endpoints

All endpoints require JWT authentication.

### Create Transaction

`POST /api/vault/transactions`

Headers:

```text
Authorization: Bearer <access_token>
Idempotency-Key: <unique_key>
```

Payload:

```json
{
  "occurred_at": "2026-04-26T12:00:00+02:00",
  "local_date": "2026-04-26",
  "timezone": "Europe/Paris",
  "transaction_type": "income",
  "wallet": "cash",
  "category": "vtc",
  "label": "Course Bolt",
  "amount": "42.50",
  "currency": "EUR",
  "notes": "Optional"
}
```

Behavior:

- Uses authenticated `user_id`; request body cannot set `user_id`.
- Stores one canonical `vault_transactions` row.
- Appends `vault.transaction.created`.
- Stores the idempotent response.
- Same `Idempotency-Key` and same payload returns original response.
- Same `Idempotency-Key` and different payload returns `409`.

Response:

```json
{
  "transaction": {
    "id": "f1ec4b45-f639-40da-a02f-f40232ce26d8",
    "occurred_at": "2026-04-26T12:00:00+02:00",
    "local_date": "2026-04-26",
    "timezone": "Europe/Paris",
    "transaction_type": "income",
    "wallet": "cash",
    "category": "vtc",
    "label": "Course Bolt",
    "amount": "42.50",
    "currency": "EUR",
    "notes": "Optional",
    "created_at": "2026-04-26T10:00:01Z",
    "event_id": "evt_...",
    "idempotency_key": "..."
  },
  "event_id": "evt_...",
  "idempotency_key": "...",
  "status": "created"
}
```

### Recent Transactions

`GET /api/vault/transactions/recent?limit=20`

Behavior:

- Returns recent transactions ordered by `occurred_at` descending.
- `limit` range: `1` to `100`.

### Weekly Summary

`GET /api/vault/summary/week?week_start=YYYY-MM-DD`

Rules:

- `week_start` must be a Monday.
- Summary is computed live from `vault_transactions`.
- No materialized weekly table exists in V1.

Response:

```json
{
  "week_start": "2026-04-20",
  "week_end": "2026-04-26",
  "income_total": "42.50",
  "expense_total": "12.00",
  "correction_total": "0.00",
  "net_total": "30.50",
  "by_wallet": {
    "cash": {
      "income_total": "42.50",
      "expense_total": "12.00",
      "correction_total": "0.00",
      "net_total": "30.50"
    }
  },
  "by_category": {
    "vtc": {
      "income_total": "42.50",
      "expense_total": "0.00",
      "correction_total": "0.00",
      "net_total": "42.50"
    }
  }
}
```

V1 correction rule:

- `correction` uses a positive `amount`.
- Weekly `net_total = income_total - expense_total + correction_total`.
- If negative corrections are needed later, add a dedicated signed `amount_delta` migration instead of overloading this V1 column.

## Event

Canonical event type:

```text
vault.transaction.created
```

Source app:

```text
vault
```

Privacy level:

```text
high
```

Events are append-only. Transaction rows are canonical financial declarations.

## Deployment Commands

Run migrations against `imperium_core`, never `n8n_db`.

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

## Live Test Commands

Login first and store the masked token locally in shell variables. Do not print secrets in logs.

```bash
API_BASE='http://127.0.0.1:8000/api'
TOKEN='<ACCESS_TOKEN>'
IDEM_KEY="vault_txn_$(date -u +%Y%m%dT%H%M%SZ)"

curl -i -X POST "$API_BASE/vault/transactions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: $IDEM_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "occurred_at": "2026-04-26T12:00:00+02:00",
    "local_date": "2026-04-26",
    "timezone": "Europe/Paris",
    "transaction_type": "income",
    "wallet": "cash",
    "category": "vtc",
    "label": "Course Bolt",
    "amount": "42.50",
    "currency": "EUR",
    "notes": "Manual V1 test"
  }'

curl -i -X POST "$API_BASE/vault/transactions" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: $IDEM_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "occurred_at": "2026-04-26T12:00:00+02:00",
    "local_date": "2026-04-26",
    "timezone": "Europe/Paris",
    "transaction_type": "income",
    "wallet": "cash",
    "category": "vtc",
    "label": "Course Bolt",
    "amount": "42.50",
    "currency": "EUR",
    "notes": "Manual V1 test"
  }'

curl -i "$API_BASE/vault/transactions/recent?limit=20" \
  -H "Authorization: Bearer $TOKEN"

curl -i "$API_BASE/vault/summary/week?week_start=2026-04-20" \
  -H "Authorization: Bearer $TOKEN"
```

Expected verification:

- Unauthenticated `POST /api/vault/transactions` returns `401`.
- Valid transaction returns `201`.
- Duplicate idempotency retry returns same response and does not create a second event or transaction.
- Recent endpoint returns transactions ordered by newest first.
- Weekly summary rejects non-Monday `week_start`.
- Weekly summary totals match live transactions.
- `events` contains `vault.transaction.created`.
- `n8n_db` is not touched.
