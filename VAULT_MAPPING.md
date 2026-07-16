# VAULT_MAPPING.md

## Phase E Source

Specification used as the single implementation source:
`specs/VAULT_DETERMINISTIC_SPEC_V1.md`.

This versioned file is an exact copy of the source originally supplied at
`/tmp/incoming_docs/VAULT_DETERMINISTIC_SPEC_V1.md`.

The five golden pressure examples A-E in
`docs_master/11_FINANCIAL_PRESSURE_FORMULA.md` were human-validated on
2026-07-16 and are now normative fixtures.

## Documents Read

- `docs_master/11_FINANCIAL_PRESSURE_FORMULA.md`
- `docs_master/42_VAULT_LOGIC_DETAIL.md`
- `docs_master/41_PATH_LOGIC_DETAIL.md` sections 9 and 16.2
- `gap_analysis_v1/GAP_vault.md`
- `docs_master/78_TOOLBOX_CATALOG.md`
- `docs_master/05_DATABASE_SCHEMA.md` finance section
- `/tmp/incoming_docs/TOOLBOX_SOCLE_SPEC_V1.md`

## Scope Boundary

Implemented only Vault Phase E:

- deterministic pressure 0-100
- upcoming expenses
- weekly finance summaries
- runner job definitions seeded disabled
- shared signal/event publication
- legacy `/api/vault` transaction routes removed
- legacy `vault_transactions` archived then dropped by migration

Explicitly not implemented: OCR receipts, LLM categorization, forecasts,
fuel smart tracking, UI, WR/Plan consumption of pressure, and Phase F.

## Schema Mapping

| Spec item | Implementation |
|---|---|
| `upcoming_expenses` | `backend/app/models/vault.py::UpcomingExpense`, migration `20260716_0040` |
| `weekly_finance_summaries` | `backend/app/models/vault.py::WeeklyFinanceSummary`, migration `20260716_0040` |
| `pressure_snapshots` | `backend/app/models/vault.py::PressureSnapshot`, append-only trigger in migration `20260716_0040` |
| canonical ledger | existing `imperium_vault_transactions`, append-only guards left intact |
| legacy ledger | `vault_transactions` dump archive then `op.drop_table("vault_transactions")` |

Dump archive path:
`backend/db_archives/20260716_vault_transactions_pre_drop.pg_dump.sql`.

## Service Mapping

| Spec item | Implementation |
|---|---|
| pressure formula | `backend/app/services/vault/pressure.py::compute_pressure` |
| explain breakdown | `backend/app/services/vault/pressure.py::explain` and API explain route |
| pressure publication | snapshot insert + `signal_values` + `finance.pressure.updated` E2 event |
| upcoming CRUD/recurrence | `backend/app/services/vault/upcoming.py` |
| weekly profit/backfill | `backend/app/services/vault/weekly.py` |
| wildcard event wake-up | `backend/app/services/runner/scheduler.py::_event_type_matches` |

## API Mapping

`backend/app/api/v1/routes/vault.py` now exposes:

- `GET /api/vault/pressure`
- `GET /api/vault/pressure/explain`
- `GET /api/vault/pressure/history`
- `GET /api/vault/upcoming-expenses`
- `POST /api/vault/upcoming-expenses`
- `PATCH /api/vault/upcoming-expenses/{expense_id}`
- `DELETE /api/vault/upcoming-expenses/{expense_id}`
- `GET /api/vault/weekly-summaries?from=YYYY-MM-DD`

Removed legacy routes:

- `POST /api/vault/transactions`
- `GET /api/vault/transactions/recent`
- `GET /api/vault/summary/week`

Canonical transaction routes remain under `/api/imperium/vault`.

## Seeds

Migration `20260716_0040_vault_deterministic_phase_e.py` seeds:

- parameters: `vault.pressure_thresholds`, `vault.category_map`, `vault.horizon_days`
- signal definition: `vault.pressure`
- disabled jobs: `vault.weekly_profit`, `vault.pressure_refresh`, `vault.expenses_horizon`

`vault.pressure_refresh` is seeded as `event_subscription` with schedule
`0 6 * * *` and event filter `finance.transaction.*`; scheduler registration
uses any job with a non-null cron schedule, so the hybrid trigger is registered
while still disabled by default.

## Tests

- Golden pressure fixtures A-E exact.
- Pressure monotonicity.
- Weekly profit aggregation, empty week, idempotent upsert/event.
- Upcoming recurrence and no duplicate generation.
- Pressure snapshot/signal/E2 event publication.
- J-7/J-1 upcoming notifications with dedup-compatible refs.
- Append-only pressure snapshots and legacy table drop checks for migrated
  PostgreSQL environments.
- Negative Q7 grep: Daily modules do not import `vault.pressure`.

## Execution Note

Final Phase E database state verified on 2026-07-16:

- `alembic current` = `20260716_0041 (head)`
- `alembic check` = `No new upgrade operations detected`

Migration `20260716_0041` adds authenticated `user_id` scoping to the Phase E
runtime tables created by `20260716_0040`.
