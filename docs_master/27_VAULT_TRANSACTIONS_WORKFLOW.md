# 27 - Vault Transactions Workflow

## Status After Vault Phase E

This document now records the active transaction boundary after the Phase E
mini-pass.

`vault_transactions` was the old Vault ledger. It is archived and dropped by
migration `20260716_0040_vault_deterministic_phase_e.py` after the dump:

```text
backend/db_archives/20260716_vault_transactions_pre_drop.pg_dump.sql
```

The legacy `/api/vault/transactions`, `/api/vault/transactions/recent`, and
`/api/vault/summary/week` routes are removed. `/api/vault` is now reserved for
Phase E deterministic Vault surfaces: pressure, pressure explain/history,
upcoming expenses, and weekly summaries.

## Active Ledger

Canonical table: `imperium_vault_transactions`.

Active transaction routes live under `/api/imperium/vault`:

```text
GET  /api/imperium/vault/transactions
GET  /api/imperium/vault/transactions/{transaction_id}
POST /api/imperium/vault/transactions
POST /api/imperium/vault/transactions/{transaction_id}/reverse
```

Rules:

- Amounts are stored as positive cents in `amount_cents`.
- `transaction_type` is `income` or `expense` only.
- Corrections are append-only reversal rows; no UPDATE/DELETE correction path.
- `POST` and reversal require `Idempotency-Key`.
- Reads and writes are scoped to the authenticated user.
- Events use the current finance namespace; legacy `vault.transaction.created`
  is read-compatible through the event nomenclature layer during the compatibility
  window.

## Phase E Additions

Phase E adds deterministic Vault reporting around the canonical ledger:

```text
GET    /api/vault/pressure
GET    /api/vault/pressure/explain
GET    /api/vault/pressure/history
GET    /api/vault/upcoming-expenses
POST   /api/vault/upcoming-expenses
PATCH  /api/vault/upcoming-expenses/{expense_id}
DELETE /api/vault/upcoming-expenses/{expense_id}
GET    /api/vault/weekly-summaries?from=YYYY-MM-DD
```

Tables:

- `upcoming_expenses`
- `weekly_finance_summaries`
- `pressure_snapshots`

Jobs, all seeded disabled:

- `vault.weekly_profit`
- `vault.pressure_refresh`
- `vault.expenses_horizon`
