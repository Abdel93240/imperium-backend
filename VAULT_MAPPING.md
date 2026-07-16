# VAULT_MAPPING.md

## Phase E Status

Source spec read from `/tmp/incoming_docs/VAULT_DETERMINISTIC_SPEC_V1.md`.

Phase E is stopped at the golden-fixture validation gate required by spec
section 7.1 and by the user instruction:

- `docs_master/11_FINANCIAL_PRESSURE_FORMULA.md` had four narrative example
  cases, not five golden examples.
- The existing examples did not define exact daily target expectations for test
  fixtures.
- Five proposed golden examples have been added to doc 11 and require human
  validation before any implementation, migration, seed, route, job, or table
  drop.

## Documents Read

- `docs_master/11_FINANCIAL_PRESSURE_FORMULA.md`
- `docs_master/42_VAULT_LOGIC_DETAIL.md`
- `docs_master/41_PATH_LOGIC_DETAIL.md` sections 9 and 16.2
- `gap_analysis_v1/GAP_vault.md`
- `docs_master/78_TOOLBOX_CATALOG.md`
- `docs_master/05_DATABASE_SCHEMA.md` finance section
- `/tmp/incoming_docs/TOOLBOX_SOCLE_SPEC_V1.md` for inherited runner, signals,
  notifications, and events constraints referenced by the Vault spec

## Scope Boundary

No Phase E technical implementation has been started.

Unchanged in this stop-point commit:

- Alembic migrations
- SQL tables
- API routes
- Vault services
- runner job definitions
- seed data
- legacy `/api/vault` route
- legacy `vault_transactions` physical table

## Prerequisite Check From Repository State

The toolbox socle appears present in code:

- `job_definitions`, `job_runs`, `job_cursors`
- `parameters` and `v_parameters_current`
- `signal_definitions`, `signal_values`
- `notifications`, `notification_channels`
- events `NOTIFY` trigger on channel `events_new`

Relevant migrations:

- `backend/alembic/versions/20260715_0038_toolbox_socle_foundations.py`
- `backend/alembic/versions/20260715_0039_toolbox_socle_seeds.py`
- `backend/alembic/versions/20260706_0033_imperium_vault_append_only_guards.py`
- `backend/alembic/versions/20260710_0037_imperium_vault_wallet.py`

## Human Validation Needed

Validate or correct the five proposed golden examples in doc 11:

- Golden A: safe
- Golden B: stable
- Golden C: attention
- Golden D: pressure
- Golden E: critical

Once validated, Phase E can continue with tests-first implementation against
those fixtures.
