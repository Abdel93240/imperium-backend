# 05 - Database Schema

## Purpose

This document defines the canonical PostgreSQL schema for the MVP.

It is a schema contract, not backend code.

The database must protect the architecture:
- one-user personal operating system
- backend as source of truth
- append-only event backbone
- idempotent mutating actions
- one current mission
- one active day session
- derived wallet balances
- pgvector memory as non-canonical semantic memory
- explicit user action for worship completion and religious privacy states

## Global Technical Rules

### Identity

Use UUID consistently.

MVP decision:
- `id_format`: UUID
- backend-generated primary keys use UUID
- client-generated local IDs may exist only as temporary offline identifiers
- canonical persisted IDs use UUID

### Time

All timestamps are stored in UTC.

User timezone is stored on the canonical user record.

Any app-local time must be converted to UTC before canonical storage, while keeping timezone context where it affects interpretation.

### One-User Architecture

The schema contains `user_id` for consistency, joins, security checks, and future-proofing.

V1 is not SaaS:
- one canonical user record
- no organizations
- no teams
- no roles
- no workspace model
- no billing model

### Enums

Use database enums or strict check constraints for stable values.

Recommended enums:

```sql
source_app = imperium | vector | vault | pulse | path | core | external | n8n | ai_router
privacy_level = low | medium | high | very_high
device_status = trusted | revoked
mission_status = planned | current | done | not_done | cancelled
day_session_status = active | completed
wallet_type = CB | Cash | Crypto
transaction_type = gain | expense
media_status = uploaded | processing | completed | error | deleted
workflow_status = queued | running | completed | failed | cancelled
memory_status = active | inactive | superseded
```

Canonical `event_type` values are dotted strings. Use a text field plus validation in backend for MVP unless the final event catalog is stable enough for an enum.

### Schema Versions

Use `schema_version` on:
- events
- ai_requests
- ai_responses
- media_extractions
- workflow_outputs
- ai_memories

### Idempotency

All mutating endpoints must store an idempotency key.

The canonical place is the `events` table. Domain tables may also keep the idempotency key when useful for direct lookup.

The database must prevent duplicate accepted events by:
- unique `event_id`
- unique idempotency key per user/action scope

Recommended MVP constraint:

```sql
unique(user_id, idempotency_key)
```

If a future workflow needs scoped idempotency, add `idempotency_scope`.

### Soft Delete

Canonical event rows are append-only and are not soft-deleted during normal usage.

Most domain tables should use soft delete only if user-facing deletion is needed:
- `deleted_at nullable`
- `deleted_reason nullable`

For MVP, prefer status transitions and audit/history over hard deletes.

### Audit and History

Events are the primary audit log.

For mutable domain records, use:
- `created_at`
- `updated_at`
- `created_by_event_id`
- `updated_by_event_id nullable`

For high-risk mutable records, add history tables or event-derived history:
- missions
- transactions
- user priority rules
- wallet adjustments
- religious logs

## Core and Auth

### `users`

Purpose:
- Stores the single canonical user record and global settings.

Columns:
- `id` uuid primary key
- `email` text unique nullable
- `password_hash` text nullable
- `master_secret_hash` text nullable
- `timezone` text not null default `Europe/Paris`
- `locale` text nullable
- `single_user_mode` boolean not null default true
- `external_ai_enabled` boolean not null default false
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Required fields:
- `id`
- `timezone`
- `single_user_mode`
- `created_at`
- `updated_at`

Foreign keys:
- none

Indexes:
- unique index on `email` where `email is not null`

Unique constraints:
- one canonical user record in V1

Implementation note:
- PostgreSQL cannot cleanly enforce "only one row ever" without a check strategy. Use a constant column or application migration seed.
- Recommended: `single_user_mode = true` and a unique partial index on `(single_user_mode)` where `single_user_mode = true`.

JSONB fields:
- none in MVP

Soft delete:
- no soft delete in MVP

Audit/history:
- auth events are tracked in `auth_events`

### `devices`

Purpose:
- Registered trusted devices.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `device_label` text not null
- `device_fingerprint` text nullable
- `platform` text nullable
- `status` device_status not null default `trusted`
- `trusted_at` timestamptz not null
- `revoked_at` timestamptz nullable
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `device_label`
- `status`
- `trusted_at`
- `created_at`
- `updated_at`

Foreign keys:
- `user_id -> users.id`

Indexes:
- index on `user_id`
- index on `(user_id, status)`

Unique constraints:
- optional unique `(user_id, device_fingerprint)` where fingerprint exists

JSONB fields:
- none in MVP

Soft delete:
- do not hard delete trusted devices; revoke with `status = revoked`

Audit/history:
- registration and revocation stored in `auth_events`

### `refresh_tokens`

Purpose:
- Stores device-bound refresh tokens.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `device_id` foreign key to `devices.id`
- `token_hash` text not null
- `issued_at` timestamptz not null
- `expires_at` timestamptz not null
- `revoked_at` timestamptz nullable
- `replaced_by_token_id` uuid nullable
- `created_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `device_id`
- `token_hash`
- `issued_at`
- `expires_at`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `device_id -> devices.id`
- `replaced_by_token_id -> refresh_tokens.id`

Indexes:
- unique index on `token_hash`
- index on `(user_id, device_id)`
- index on `expires_at`

Unique constraints:
- `token_hash` unique

JSONB fields:
- none

Soft delete:
- no hard delete in normal use; revoke with `revoked_at`

Audit/history:
- token issue/refresh/revoke events stored in `auth_events`

### `auth_events`

Purpose:
- Audit log for login, refresh, device registration, revocation, and auth failures.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id` nullable for failed unknown login
- `device_id` foreign key to `devices.id` nullable
- `event_id` foreign key to `events.id` nullable
- `auth_event_type` text not null
- `ip_address` inet nullable
- `user_agent` text nullable
- `metadata` jsonb nullable
- `created_at` timestamptz not null

Required fields:
- `id`
- `auth_event_type`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `device_id -> devices.id`
- `event_id -> events.id`

Indexes:
- index on `(user_id, created_at)`
- index on `(device_id, created_at)`
- index on `auth_event_type`

Unique constraints:
- none

JSONB fields:
- `metadata`

Soft delete:
- no

Audit/history:
- table is audit history

## Event Backbone

### `events`

Purpose:
- Canonical append-only event log for all important actions.

Columns:
- `id` uuid primary key
- `event_id` text not null
- `event_type` text not null
- `schema_version` text not null
- `occurred_at` timestamptz not null
- `received_at` timestamptz not null
- `source_app` source_app not null
- `device_id` foreign key to `devices.id` nullable
- `user_id` foreign key to `users.id` not null
- `idempotency_key` text not null
- `correlation_id` text not null
- `causation_id` text nullable
- `privacy_level` privacy_level not null
- `payload` jsonb not null
- `duplicate_of_event_id` text nullable
- `created_at` timestamptz not null

Required fields:
- `id`
- `event_id`
- `event_type`
- `schema_version`
- `occurred_at`
- `received_at`
- `source_app`
- `user_id`
- `idempotency_key`
- `correlation_id`
- `privacy_level`
- `payload`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `device_id -> devices.id`

Indexes:
- unique index on `event_id`
- unique index on `(user_id, idempotency_key)`
- index on `(user_id, event_type, occurred_at)`
- index on `(user_id, correlation_id)`
- index on `causation_id`
- GIN index on `payload` only if needed for querying

Unique constraints:
- `event_id`
- `(user_id, idempotency_key)`

JSONB fields:
- `payload`

Soft delete:
- forbidden in normal app usage

Audit/history:
- this table is append-only audit history

Notes:
- Canonical event names are dotted strings.
- n8n workflow names may use snake_case, but `event_type` must remain dotted.

## Imperium

### `day_sessions`

Purpose:
- Tracks bounded user day sessions.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `status` day_session_status not null
- `started_at` timestamptz not null
- `ended_at` timestamptz nullable
- `created_by_event_id` foreign key to `events.id`
- `updated_by_event_id` foreign key to `events.id` nullable
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `status`
- `started_at`
- `created_by_event_id`
- `created_at`
- `updated_at`

Foreign keys:
- `user_id -> users.id`
- `created_by_event_id -> events.id`
- `updated_by_event_id -> events.id`

Indexes:
- index on `(user_id, started_at)`
- partial unique index on `(user_id)` where `status = 'active'`

Unique constraints:
- one active day session per user

JSONB fields:
- none in MVP

Soft delete:
- no

Audit/history:
- changes are represented by events

### `missions`

Purpose:
- Canonical mission records. One mission may be current at a time.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `day_session_id` foreign key to `day_sessions.id` nullable
- `title` text not null
- `mission_type` text not null
- `status` mission_status not null
- `target_type` text nullable
- `target_value` text nullable
- `target_unit` text nullable
- `target_metadata` jsonb nullable
- `estimated_duration_minutes` integer nullable
- `scheduled_start_at` timestamptz nullable
- `scheduled_end_at` timestamptz nullable
- `source_type` text not null
- `created_by_event_id` foreign key to `events.id`
- `updated_by_event_id` foreign key to `events.id` nullable
- `completed_at` timestamptz nullable
- `failed_at` timestamptz nullable
- `cancelled_at` timestamptz nullable
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `title`
- `mission_type`
- `status`
- `source_type`
- `created_by_event_id`
- `created_at`
- `updated_at`

Foreign keys:
- `user_id -> users.id`
- `day_session_id -> day_sessions.id`
- `created_by_event_id -> events.id`
- `updated_by_event_id -> events.id`

Indexes:
- partial unique index on `(user_id)` where `status = 'current'`
- index on `(user_id, status)`
- index on `(user_id, day_session_id)`
- index on `(user_id, scheduled_start_at)`

Unique constraints:
- one current mission per user

JSONB fields:
- `target_metadata`

Soft delete:
- no hard delete in MVP; use `cancelled` if removed from plan

Audit/history:
- mission changes stored in `mission_history`

### `mission_history`

Purpose:
- Stores mission lifecycle changes and failure/completion details.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `mission_id` foreign key to `missions.id`
- `event_id` foreign key to `events.id`
- `from_status` mission_status nullable
- `to_status` mission_status not null
- `reason_category` text nullable
- `reason_detail` text nullable
- `metadata` jsonb nullable
- `created_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `mission_id`
- `event_id`
- `to_status`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `mission_id -> missions.id`
- `event_id -> events.id`

Indexes:
- index on `(mission_id, created_at)`
- index on `(user_id, created_at)`

Unique constraints:
- none

JSONB fields:
- `metadata`

Soft delete:
- no

Audit/history:
- table is mission history

### `user_priority_rules`

Purpose:
- Stores ordered personal priority rules.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `label` text not null
- `order_index` integer not null
- `is_active` boolean not null default true
- `created_by_event_id` foreign key to `events.id`
- `updated_by_event_id` foreign key to `events.id` nullable
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `label`
- `order_index`
- `is_active`
- `created_by_event_id`
- `created_at`
- `updated_at`

Foreign keys:
- `user_id -> users.id`
- `created_by_event_id -> events.id`
- `updated_by_event_id -> events.id`

Indexes:
- unique index on `(user_id, order_index)` where `is_active = true`
- index on `(user_id, is_active)`

Unique constraints:
- active order index unique per user

JSONB fields:
- none

Soft delete:
- deactivate with `is_active = false`

Audit/history:
- changes are event-backed

### `recommendations`

Purpose:
- Stores backend/AI recommendations for apps, especially Imperium, Vector, Vault, Pulse, and The Path.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `source_app` source_app not null
- `target_app` source_app nullable
- `event_id` foreign key to `events.id` nullable
- `ai_response_id` foreign key to `ai_responses.id` nullable
- `recommendation_type` text not null
- `title` text nullable
- `body` text not null
- `confidence` numeric nullable
- `status` text not null default `active`
- `metadata` jsonb nullable
- `created_at` timestamptz not null
- `acknowledged_at` timestamptz nullable
- `dismissed_at` timestamptz nullable

Required fields:
- `id`
- `user_id`
- `source_app`
- `recommendation_type`
- `body`
- `status`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `event_id -> events.id`
- `ai_response_id -> ai_responses.id`

Indexes:
- index on `(user_id, target_app, status)`
- index on `(user_id, created_at)`

Unique constraints:
- none in MVP

JSONB fields:
- `metadata`

Soft delete:
- dismiss with `dismissed_at`

Audit/history:
- event-backed

## The Vault

### `imperium_vault_transactions` - Patch 9A ledger foundation, Patch 9F reversals, Patch 9H audit readiness

Purpose:
- Stores a simple append-only Vault ledger for income and expense facts created through `/api/imperium/vault/transactions`.
- This table is the Patch 9A foundation only; it does not create wallets, balances, sadaqa records, OCR results, AI scores, memory, embeddings, or calendar replanning.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `transaction_type` text not null
- `amount_cents` integer not null
- `currency` text not null default `EUR`
- `occurred_at` timestamptz not null
- `local_date` date not null
- `timezone` text not null
- `category` text nullable
- `source` text nullable
- `note` text nullable
- `external_ref` text nullable
- `reversal_of_transaction_id` uuid nullable
- `reversal_reason` text nullable max 500
- `is_reversal` boolean not null default false
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Immutability contract:
- The Vault ledger is append-only.
- Transactions are immutable once inserted.
- No PUT/PATCH/DELETE endpoint is allowed for `/api/imperium/vault/transactions`.
- Corrections must be written by appending a reversal row through `POST /api/imperium/vault/transactions/{transaction_id}/reverse`.
- The original transaction must never be updated or deleted.
- The reversal transaction is a new row linked to the original transaction.
- Patch 9F/9G allow one and only one reversal per original transaction.
- `updated_at` remains a generic row timestamp, but V1 must not use it to represent direct transaction edits.

Reversal fields:
- `is_reversal` marks rows appended by the Patch 9F reverse endpoint.
- `reversal_of_transaction_id` links a reversal row to the original transaction and is required only when `is_reversal = true`.
- `reversal_reason` stores the trimmed user-provided correction reason; it is nullable on normal rows and max 500 characters on reversal writes.

Temporal semantics:
- Patch 9J makes `occurred_at` the only authoritative temporal source for Vault V1 summaries and filters.
- `occurred_at` is stored and interpreted as UTC for Vault V1.
- `GET /api/imperium/vault/summary/monthly` groups by the UTC month of `occurred_at` and returns `YYYY-MM`.
- `occurred_from` and `occurred_to` are timezone-aware UTC-normalized bounds on `occurred_at`.
- Transactions near a user's local monthly boundary can fall into the adjacent UTC month.
- `local_date` and `timezone` remain compatibility columns from earlier patches, but Patch 9J does not use them for Vault V1 summary semantics.
- Any future local-month or timezone-aware financial reporting requires a separate patch and migration.

Required fields:
- `id`
- `user_id`
- `transaction_type`
- `amount_cents`
- `currency`
- `occurred_at`
- `local_date`
- `timezone`
- `is_reversal`
- `created_at`
- `updated_at`

Foreign keys:
- `user_id -> users.id`
- `reversal_of_transaction_id -> imperium_vault_transactions.id`

Indexes:
- index on `(user_id, occurred_at desc)`
- index on `(user_id, local_date desc)`
- index on `(user_id, transaction_type)`
- index on `(user_id, reversal_of_transaction_id)`
- unique partial index on `(reversal_of_transaction_id)` where `is_reversal = true`

Check constraints:
- `transaction_type IN ('income', 'expense')`
- `amount_cents > 0`
- `length(currency) = 3`
- `is_reversal = true` requires `reversal_of_transaction_id IS NOT NULL`
- `is_reversal = false` requires `reversal_of_transaction_id IS NULL`

API and ownership rules:
- Routes are JWT scoped with `CurrentUserDep`; clients cannot provide `user_id`.
- `POST` requires `Idempotency-Key` and stores the public response in `idempotency_keys`.
- `POST /api/imperium/vault/transactions/{transaction_id}/reverse` requires `Idempotency-Key`.
- `GET` does not require `Idempotency-Key`.
- Reads are strictly current-user scoped and deterministic.
- Reversals are append-only corrections: the original row is never updated or deleted.
- A non-reversal original may have one and only one reversal in Patch 9F.
- Public Vault read responses stay safe for audit review: they expose only the fields needed by the contract and do not persist AI, n8n, OCR, sadaqa, wallet, balance, pgvector, embedding, or memory state.
- Monthly Vault summaries group by the UTC `occurred_at` month (`YYYY-MM`) in Patch 9J.

Patch 9A exclusions:
- no wallet/balance automation
- no sadaqa creation
- no receipt OCR
- no AI, n8n, pgvector, embedding, memory commit, calendar replanning, financial scoring, or exposed internal coefficient

Patch 9F reversal rules:
- income reverses to expense with the same amount and currency.
- expense reverses to income with the same amount and currency.
- Reversal rows use `source = 'reversal'`, `external_ref = null`, and store the trimmed user reason.
- Reversal rows use backend `occurred_at`; compatibility date fields are derived at reversal time. They correct the ledger at the backend moment of the counter-entry, not by rewriting the original transaction's period. A January transaction reversed in March produces a March counter-entry in Vault V1 append-only accounting.
- Reversal rows cannot themselves be reversed in V1.
- The reverse endpoint never updates or deletes the original transaction; correction is represented only by the appended reversal row.
- no wallet/balance automation
- no sadaqa creation
- no receipt OCR
- no persistent AI, n8n, OCR, sadaqa, wallet, balance, pgvector, embedding, memory commit, calendar replanning, financial scoring, or exposed internal coefficient
- no Mission-table coupling

Patch 9G immutability rules:
- The Vault ledger stays append-only after Patch 9F.
- No direct `PUT`, `PATCH`, or `DELETE` transaction mutation endpoints are part of the Imperium Vault contract.
- The only permitted correction path is `POST /api/imperium/vault/transactions/{transaction_id}/reverse`.
- The original transaction must never be updated or deleted.
- The reversal transaction is a new row linked to the original.
- One reversal per original transaction remains the V1 rule.
- no persistent AI, n8n, OCR, sadaqa, wallet, balance, pgvector, embedding, memory commit, calendar replanning, financial scoring, or exposed internal coefficient
- no Mission-table coupling

### `wallets`

Purpose:
- Stores wallet definitions and opening balances.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `wallet_type` wallet_type not null
- `opening_balance` numeric not null default 0
- `opening_balance_at` timestamptz not null
- `is_active` boolean not null default true
- `created_by_event_id` foreign key to `events.id`
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `wallet_type`
- `opening_balance`
- `opening_balance_at`
- `is_active`
- `created_by_event_id`
- `created_at`
- `updated_at`

Foreign keys:
- `user_id -> users.id`
- `created_by_event_id -> events.id`

Indexes:
- unique index on `(user_id, wallet_type)`
- index on `(user_id, is_active)`

Unique constraints:
- one wallet row per wallet type per user

JSONB fields:
- none

Soft delete:
- deactivate with `is_active = false`

Audit/history:
- wallet creation and adjustments are event-backed

Accounting rule:
- wallet balance = opening balance + gains - expenses + adjustments
- do not hardcode `wallet_cb_balance`, `wallet_cash_balance`, or `wallet_crypto_balance` columns

### `transactions`

Purpose:
- Stores financial gains and expenses.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `wallet_id` foreign key to `wallets.id`
- `event_id` foreign key to `events.id`
- `transaction_type` transaction_type not null
- `category` text not null
- `amount` numeric not null
- `transaction_at` timestamptz not null
- `location_text` text nullable
- `latitude` numeric nullable
- `longitude` numeric nullable
- `location_source` text nullable
- `source_type` text not null
- `notes` text nullable
- `ai_confidence` numeric nullable
- `raw_extracted_text` text nullable
- `created_at` timestamptz not null
- `updated_at` timestamptz not null
- `deleted_at` timestamptz nullable

Required fields:
- `id`
- `user_id`
- `wallet_id`
- `event_id`
- `transaction_type`
- `category`
- `amount`
- `transaction_at`
- `source_type`
- `created_at`
- `updated_at`

Foreign keys:
- `user_id -> users.id`
- `wallet_id -> wallets.id`
- `event_id -> events.id`

Indexes:
- index on `(user_id, transaction_at)`
- index on `(user_id, wallet_id, transaction_at)`
- index on `(user_id, transaction_type, transaction_at)`

Unique constraints:
- unique `event_id`

Check constraints:
- `amount > 0`

JSONB fields:
- none in MVP

Soft delete:
- use `deleted_at`; do not physically delete during normal app usage

Audit/history:
- edits should emit events; future `transaction_history` may be added

### `wallet_adjustments`

Purpose:
- Explicit corrections to wallet balances without pretending a transaction occurred.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `wallet_id` foreign key to `wallets.id`
- `event_id` foreign key to `events.id`
- `amount_delta` numeric not null
- `reason` text not null
- `notes` text nullable
- `adjusted_at` timestamptz not null
- `created_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `wallet_id`
- `event_id`
- `amount_delta`
- `reason`
- `adjusted_at`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `wallet_id -> wallets.id`
- `event_id -> events.id`

Indexes:
- index on `(user_id, wallet_id, adjusted_at)`

Unique constraints:
- unique `event_id`

JSONB fields:
- none

Soft delete:
- no; corrections require new adjustment

Audit/history:
- table is adjustment history

### `weekly_financial_summaries`

Purpose:
- Stores weekly financial summary used by The Vault and The Path sadaqa logic.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `week_start_date` date not null
- `week_end_date` date not null
- `total_gains` numeric not null default 0
- `total_expenses` numeric not null default 0
- `real_profit` numeric not null default 0
- `summary_status` text not null default `draft`
- `created_by_event_id` foreign key to `events.id` nullable
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `week_start_date`
- `week_end_date`
- `total_gains`
- `total_expenses`
- `real_profit`
- `summary_status`
- `created_at`
- `updated_at`

Foreign keys:
- `user_id -> users.id`
- `created_by_event_id -> events.id`

Indexes:
- unique index on `(user_id, week_start_date)`

Unique constraints:
- no duplicate weekly financial summary for same user/week

JSONB fields:
- none in MVP

Soft delete:
- no

Audit/history:
- recomputation should emit events

### `sadaqa_records`

Purpose:
- Stores sadaqa obligations and donation confirmations.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `event_id` foreign key to `events.id`
- `weekly_financial_summary_id` foreign key to `weekly_financial_summaries.id` nullable
- `record_type` text not null
- `amount` numeric not null
- `percentage` numeric nullable
- `destination` text nullable
- `notes` text nullable
- `recorded_at` timestamptz not null
- `created_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `event_id`
- `record_type`
- `amount`
- `recorded_at`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `event_id -> events.id`
- `weekly_financial_summary_id -> weekly_financial_summaries.id`

Indexes:
- index on `(user_id, recorded_at)`
- index on `(user_id, weekly_financial_summary_id)`

Unique constraints:
- unique `event_id`

Check constraints:
- `amount >= 0`

JSONB fields:
- none

Soft delete:
- no; corrections require new event

Audit/history:
- table is donation/obligation history

Note:
- This table serves The Path worship discipline while using real profit from The Vault.

## Vector

Vector MVP is manual-first.

No illegal Bolt automation.

No required overlay or sound detection in MVP.

### `vtc_sessions`

Purpose:
- Stores VTC work sessions.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `started_event_id` foreign key to `events.id`
- `ended_event_id` foreign key to `events.id` nullable
- `started_at` timestamptz not null
- `ended_at` timestamptz nullable
- `target_ca` numeric nullable
- `final_ca` numeric nullable
- `objective_reached` boolean nullable
- `notes` text nullable
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `started_event_id`
- `started_at`
- `created_at`
- `updated_at`

Foreign keys:
- `user_id -> users.id`
- `started_event_id -> events.id`
- `ended_event_id -> events.id`

Indexes:
- index on `(user_id, started_at)`

Unique constraints:
- unique `started_event_id`
- unique `ended_event_id` where not null

JSONB fields:
- none

Soft delete:
- no in MVP

Audit/history:
- session start/end events are canonical

### `vtc_ride_offers`

Purpose:
- Stores manually submitted or OCR-extracted ride offers.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `session_id` foreign key to `vtc_sessions.id` nullable
- `event_id` foreign key to `events.id`
- `price` numeric nullable
- `pickup_distance` numeric nullable
- `pickup_distance_unit` text nullable
- `estimated_total_minutes` integer nullable
- `destination_zone` text nullable
- `raw_extraction` jsonb nullable
- `extraction_confidence` numeric nullable
- `user_action` text nullable
- `created_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `event_id`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `session_id -> vtc_sessions.id`
- `event_id -> events.id`

Indexes:
- index on `(user_id, created_at)`
- index on `(session_id, created_at)`

Unique constraints:
- unique `event_id`

JSONB fields:
- `raw_extraction`

Soft delete:
- no in MVP

Audit/history:
- user action should emit a separate event

### `vtc_zone_observations`

Purpose:
- Stores learned observations about zones, routes, ETA differences, and field reality.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `event_id` foreign key to `events.id` nullable
- `zone_name` text not null
- `observation_type` text not null
- `observed_at` timestamptz not null
- `google_eta_minutes` integer nullable
- `real_duration_minutes` integer nullable
- `metadata` jsonb nullable
- `created_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `zone_name`
- `observation_type`
- `observed_at`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `event_id -> events.id`

Indexes:
- index on `(user_id, zone_name, observed_at)`
- index on `(user_id, observation_type, observed_at)`

Unique constraints:
- none in MVP

JSONB fields:
- `metadata`

Soft delete:
- no in MVP

Audit/history:
- observations are historical

### `vtc_recommendations`

Purpose:
- Stores VTC recommendations and user feedback.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `ride_offer_id` foreign key to `vtc_ride_offers.id` nullable
- `session_id` foreign key to `vtc_sessions.id` nullable
- `event_id` foreign key to `events.id` nullable
- `recommendation` text not null
- `halo_state` text nullable
- `explanation` text nullable
- `confidence` numeric nullable
- `user_feedback` text nullable
- `metadata` jsonb nullable
- `created_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `recommendation`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `ride_offer_id -> vtc_ride_offers.id`
- `session_id -> vtc_sessions.id`
- `event_id -> events.id`

Indexes:
- index on `(user_id, created_at)`
- index on `(ride_offer_id)`

Unique constraints:
- none in MVP

JSONB fields:
- `metadata`

Soft delete:
- no

Audit/history:
- feedback should be event-backed

## Pulse

Pulse MVP stays simple.

### `body_profile_snapshots`

Purpose:
- Stores user body profile snapshots over time.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `event_id` foreign key to `events.id`
- `height_cm` numeric nullable
- `estimated_weight_kg` numeric nullable
- `target_weight_kg` numeric nullable
- `known_pain` jsonb nullable
- `injuries` jsonb nullable
- `fatigue_state` text nullable
- `sleep_issues` jsonb nullable
- `mobility_limitations` jsonb nullable
- `snapshot_at` timestamptz not null
- `created_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `event_id`
- `snapshot_at`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `event_id -> events.id`

Indexes:
- index on `(user_id, snapshot_at)`

Unique constraints:
- unique `event_id`

JSONB fields:
- `known_pain`
- `injuries`
- `sleep_issues`
- `mobility_limitations`

Soft delete:
- no

Audit/history:
- table is snapshot history

### `meals`

Purpose:
- Simple meal tracking.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `event_id` foreign key to `events.id`
- `meal_at` timestamptz not null
- `meal_type` text nullable
- `description` text not null
- `estimated_calories` numeric nullable
- `estimated_protein_g` numeric nullable
- `metadata` jsonb nullable
- `created_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `event_id`
- `meal_at`
- `description`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `event_id -> events.id`

Indexes:
- index on `(user_id, meal_at)`

Unique constraints:
- unique `event_id`

JSONB fields:
- `metadata`

Soft delete:
- optional `deleted_at` later; not MVP

Audit/history:
- event-backed

### `workouts`

Purpose:
- Stores planned and completed workouts.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `event_id` foreign key to `events.id` nullable
- `title` text not null
- `status` text not null
- `planned_at` timestamptz nullable
- `completed_at` timestamptz nullable
- `duration_minutes` integer nullable
- `intensity` text nullable
- `exercises` jsonb nullable
- `adaptation_reason` text nullable
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `title`
- `status`
- `created_at`
- `updated_at`

Foreign keys:
- `user_id -> users.id`
- `event_id -> events.id`

Indexes:
- index on `(user_id, planned_at)`
- index on `(user_id, status)`

Unique constraints:
- unique `event_id` where not null

JSONB fields:
- `exercises`

Soft delete:
- use cancelled status; no hard delete in MVP

Audit/history:
- changes are event-backed

### `food_stock_items`

Purpose:
- Tracks simple food stock and expiration.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `event_id` foreign key to `events.id` nullable
- `name` text not null
- `quantity` numeric not null
- `unit` text not null
- `category` text nullable
- `expiry_type` text nullable
- `expiry_date` date nullable
- `storage_type` text nullable
- `source` text nullable
- `is_active` boolean not null default true
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `name`
- `quantity`
- `unit`
- `is_active`
- `created_at`
- `updated_at`

Foreign keys:
- `user_id -> users.id`
- `event_id -> events.id`

Indexes:
- index on `(user_id, is_active)`
- index on `(user_id, expiry_date)`

Unique constraints:
- none in MVP

JSONB fields:
- none

Soft delete:
- deactivate with `is_active = false`

Audit/history:
- stock changes should emit events

### `pulse_recommendations`

Purpose:
- Stores Pulse workout, nutrition, stock, and health recommendations.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `event_id` foreign key to `events.id` nullable
- `recommendation_type` text not null
- `body` text not null
- `confidence` numeric nullable
- `status` text not null default `active`
- `metadata` jsonb nullable
- `created_at` timestamptz not null
- `dismissed_at` timestamptz nullable

Required fields:
- `id`
- `user_id`
- `recommendation_type`
- `body`
- `status`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `event_id -> events.id`

Indexes:
- index on `(user_id, status, created_at)`

Unique constraints:
- none

JSONB fields:
- `metadata`

Soft delete:
- dismiss with `dismissed_at`

Audit/history:
- event-backed

## The Path

Important:
- Never infer prayer completion without explicit user action.
- Never infer fasting intention without explicit user action.
- Never infer ghusl state without explicit user action.
- Never infer Quran completion without explicit user action.
- Never infer adhkar completion without explicit user action.
- Never infer sadaqa completion without explicit user action.
- Path Foundation 10A is limited to habits and check-ins.
- 10A has no AI/n8n/scoring/calendar in 10A, no pgvector write, no embeddings, no automatic memory commit, no automatic replanning, no automatic scoring, and no automatic mission/vault linkage.

### Path Foundation 10A - `imperium_path_habits`

Purpose:
- Stores current-user Path habits for explicit worship, health, family, work, discipline, or custom routines.
- The table is a simple tracking foundation; it does not create missions, Vault rows, memories, calendar events, scoring rows, or workflow triggers.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `title` varchar(120) not null
- `description` varchar(500) nullable
- `domain` varchar(80) nullable
- `frequency` varchar(20) not null
- `is_active` boolean not null default true
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `title`
- `frequency`
- `is_active`
- `created_at`
- `updated_at`

Foreign keys:
- `user_id -> users.id`

Indexes:
- index on `(user_id, is_active, created_at)`
- index on `(user_id, domain)`

Check constraints:
- `frequency IN ('daily', 'weekly')`

API validation:
- client-provided `user_id` is forbidden
- blank `title` is rejected
- supported API domains are `worship`, `health`, `discipline`, `family`, `work`, `custom`

Soft delete:
- no hard delete in 10A; deactivate with `is_active = false`

Audit/history:
- idempotent creates are stored through the backend idempotency table
- no AI/n8n/scoring/calendar in 10A

### Path Foundation 10A - `imperium_path_check_ins`

Purpose:
- Stores one explicit check-in per current-user habit and date.
- Records only the user's stated status; missed requires reason.
- The table does not trigger automatic mission creation, Vault linkage, sadaqa calculation, memory commit, embeddings, pgvector writes, calendar replanning, or discipline scoring.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `habit_id` foreign key to `imperium_path_habits.id`
- `check_date` date not null
- `status` varchar(20) not null
- `reason` varchar(500) nullable
- `note` varchar(500) nullable
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `habit_id`
- `check_date`
- `status`
- `created_at`
- `updated_at`

Foreign keys:
- `user_id -> users.id`
- `habit_id -> imperium_path_habits.id`

Indexes:
- index on `(user_id, check_date desc)`
- index on `(user_id, habit_id, check_date)`

Unique constraints:
- unique `(user_id, habit_id, check_date)`

Check constraints:
- `status IN ('done', 'missed')`

API validation:
- client-provided `user_id` is forbidden
- check-ins are user-scoped through the owned habit
- non-owned habits return 404
- inactive habits return 409
- duplicate `habit_id` and `check_date` with another idempotency key returns 409
- missed requires reason
- `done` must not include `reason`; use `note`

Soft delete:
- no hard delete in 10A

Audit/history:
- idempotent creates are stored through the backend idempotency table
- no automatic memory commit
- no automatic mission/vault linkage
- no automatic replanning
- no automatic scoring
- Path remains deterministic and read-only on GET endpoints
- no automatic check-in creation

### `prayer_logs`

Purpose:
- Tracks prayer-related user actions and prayer timing context.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `event_id` foreign key to `events.id`
- `prayer_name` text not null
- `prayer_time_at` timestamptz nullable
- `action_type` text not null
- `source` text not null default `user_action`
- `location_text` text nullable
- `metadata` jsonb nullable
- `created_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `event_id`
- `prayer_name`
- `action_type`
- `source`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `event_id -> events.id`

Indexes:
- index on `(user_id, created_at)`
- index on `(user_id, prayer_name, created_at)`

Unique constraints:
- unique `event_id`

JSONB fields:
- `metadata`

Soft delete:
- no; corrections require new event

Audit/history:
- table is worship action history

### `fasting_logs`

Purpose:
- Tracks explicit fasting intention/status actions.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `event_id` foreign key to `events.id`
- `fasting_date` date not null
- `fasting_type` text nullable
- `action_type` text not null
- `source` text not null default `user_action`
- `metadata` jsonb nullable
- `created_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `event_id`
- `fasting_date`
- `action_type`
- `source`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `event_id -> events.id`

Indexes:
- index on `(user_id, fasting_date)`

Unique constraints:
- unique `event_id`

JSONB fields:
- `metadata`

Soft delete:
- no

Audit/history:
- explicit action history

### `worship_routines`

Purpose:
- Stores Quran, adhkar, prayer-related, and spiritual routines.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `routine_type` text not null
- `title` text not null
- `target_count` integer nullable
- `target_unit` text nullable
- `is_active` boolean not null default true
- `created_by_event_id` foreign key to `events.id`
- `updated_by_event_id` foreign key to `events.id` nullable
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `routine_type`
- `title`
- `is_active`
- `created_by_event_id`
- `created_at`
- `updated_at`

Foreign keys:
- `user_id -> users.id`
- `created_by_event_id -> events.id`
- `updated_by_event_id -> events.id`

Indexes:
- index on `(user_id, routine_type, is_active)`

Unique constraints:
- none in MVP

JSONB fields:
- none in MVP

Soft delete:
- deactivate with `is_active = false`

Audit/history:
- event-backed

### `worship_routine_logs`

Purpose:
- Tracks explicit completion/progress for worship routines.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `routine_id` foreign key to `worship_routines.id`
- `event_id` foreign key to `events.id`
- `completed_count` integer nullable
- `progress_value` text nullable
- `logged_at` timestamptz not null
- `created_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `routine_id`
- `event_id`
- `logged_at`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `routine_id -> worship_routines.id`
- `event_id -> events.id`

Indexes:
- index on `(user_id, routine_id, logged_at)`

Unique constraints:
- unique `event_id`

JSONB fields:
- none

Soft delete:
- no

Audit/history:
- explicit action history

## AI Routing

### `ai_requests`

Purpose:
- Stores AI routing requests.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `event_id` foreign key to `events.id` nullable
- `schema_version` text not null
- `source_app` source_app not null
- `input_type` text not null
- `privacy_level` privacy_level not null
- `complexity_level` text nullable
- `urgency_level` text nullable
- `memory_required` boolean not null default false
- `request_payload` jsonb not null
- `status` text not null
- `created_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `schema_version`
- `source_app`
- `input_type`
- `privacy_level`
- `memory_required`
- `request_payload`
- `status`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `event_id -> events.id`

Indexes:
- index on `(user_id, created_at)`
- index on `(user_id, status)`

Unique constraints:
- unique `event_id` where not null

JSONB fields:
- `request_payload`

Soft delete:
- no

Audit/history:
- request history retained

### `privacy_gate_decisions`

Purpose:
- Stores decisions about whether external AI may receive data.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `ai_request_id` foreign key to `ai_requests.id`
- `provider` text not null
- `data_category` text not null
- `privacy_level` privacy_level not null
- `user_setting_allowed` boolean not null
- `explicit_permission_required` boolean not null
- `explicit_permission_granted` boolean nullable
- `decision` text not null
- `reason` text nullable
- `created_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `ai_request_id`
- `provider`
- `data_category`
- `privacy_level`
- `user_setting_allowed`
- `explicit_permission_required`
- `decision`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `ai_request_id -> ai_requests.id`

Indexes:
- index on `(user_id, created_at)`
- index on `(ai_request_id)`

Unique constraints:
- none in MVP

JSONB fields:
- none

Soft delete:
- no

Audit/history:
- table is privacy gate audit

### `model_runs`

Purpose:
- Stores each model/provider execution.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `ai_request_id` foreign key to `ai_requests.id`
- `provider` text not null
- `model_name` text not null
- `local_or_external` text not null
- `started_at` timestamptz not null
- `completed_at` timestamptz nullable
- `status` text not null
- `latency_ms` integer nullable
- `cost_estimate` numeric nullable
- `error_message` text nullable
- `metadata` jsonb nullable
- `created_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `ai_request_id`
- `provider`
- `model_name`
- `local_or_external`
- `started_at`
- `status`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `ai_request_id -> ai_requests.id`

Indexes:
- index on `(user_id, started_at)`
- index on `(ai_request_id)`

Unique constraints:
- none

JSONB fields:
- `metadata`

Soft delete:
- no

Audit/history:
- model run history retained

### `ai_responses`

Purpose:
- Stores AI outputs returned to workflows or apps.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `ai_request_id` foreign key to `ai_requests.id`
- `model_run_id` foreign key to `model_runs.id` nullable
- `schema_version` text not null
- `response_type` text not null
- `response_payload` jsonb not null
- `confidence` numeric nullable
- `created_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `ai_request_id`
- `schema_version`
- `response_type`
- `response_payload`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `ai_request_id -> ai_requests.id`
- `model_run_id -> model_runs.id`

Indexes:
- index on `(user_id, created_at)`
- index on `(ai_request_id)`

Unique constraints:
- none

JSONB fields:
- `response_payload`

Soft delete:
- no

Audit/history:
- response history retained

## Media

### `media_files`

Purpose:
- Stores metadata for uploaded audio, screenshots, receipts, documents, and other media.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `event_id` foreign key to `events.id`
- `source_app` source_app not null
- `media_type` text not null
- `file_name` text nullable
- `mime_type` text not null
- `size_bytes` bigint nullable
- `storage_uri` text not null
- `status` media_status not null
- `privacy_level` privacy_level not null
- `retention_policy` text not null
- `retain_until` timestamptz nullable
- `raw_deleted_at` timestamptz nullable
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `event_id`
- `source_app`
- `media_type`
- `mime_type`
- `storage_uri`
- `status`
- `privacy_level`
- `retention_policy`
- `created_at`
- `updated_at`

Foreign keys:
- `user_id -> users.id`
- `event_id -> events.id`

Indexes:
- index on `(user_id, created_at)`
- index on `(user_id, media_type, created_at)`
- index on `retain_until`

Unique constraints:
- unique `event_id`

JSONB fields:
- none in MVP

Soft delete:
- raw file deletion tracked with `raw_deleted_at`

Audit/history:
- extraction and deletion events should be emitted

### `media_extractions`

Purpose:
- Stores OCR/transcription/extraction outputs from media.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `media_file_id` foreign key to `media_files.id`
- `ai_request_id` foreign key to `ai_requests.id` nullable
- `schema_version` text not null
- `extraction_type` text not null
- `extracted_payload` jsonb not null
- `raw_text` text nullable
- `confidence` numeric nullable
- `created_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `media_file_id`
- `schema_version`
- `extraction_type`
- `extracted_payload`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `media_file_id -> media_files.id`
- `ai_request_id -> ai_requests.id`

Indexes:
- index on `(user_id, created_at)`
- index on `(media_file_id)`

Unique constraints:
- none in MVP

JSONB fields:
- `extracted_payload`

Soft delete:
- no; if sensitive, redact with a future retention workflow

Audit/history:
- extraction output is retained according to retention policy

## pgvector Memory

### `ai_memories`

Purpose:
- Stores semantic memory embeddings. Memory is not canonical truth.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `source_app` source_app not null
- `source_table` text nullable
- `source_id` text nullable
- `source_event_id` foreign key to `events.id` nullable
- `schema_version` text not null
- `memory_type` text not null
- `content` text not null
- `embedding` vector not null
- `embedding_model` text not null
- `privacy_level` privacy_level not null
- `confidence` numeric nullable
- `status` memory_status not null default `active`
- `supersedes_memory_id` uuid nullable
- `created_at` timestamptz not null
- `expires_at` timestamptz nullable

Required fields:
- `id`
- `user_id`
- `source_app`
- `schema_version`
- `memory_type`
- `content`
- `embedding`
- `embedding_model`
- `privacy_level`
- `status`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `source_event_id -> events.id`
- `supersedes_memory_id -> ai_memories.id`

Indexes:
- vector similarity index on `embedding`
- index on `(user_id, memory_type, status)`
- index on `(source_table, source_id)`
- index on `expires_at`

Unique constraints:
- none in MVP

JSONB fields:
- none in MVP

Soft delete:
- do not delete for normal correction; set `status = inactive` or `superseded`

Audit/history:
- memory writes and supersessions should be event-backed

Retrieval rule:
- inactive or superseded memory must not be retrieved
- expired memory must not be retrieved
- canonical decisions must check PostgreSQL truth, not memory alone

## n8n / Workflow Tracking

### `workflow_runs`

Purpose:
- Tracks n8n/backend workflow execution.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id` nullable
- `trigger_event_id` foreign key to `events.id` nullable
- `workflow_name` text not null
- `workflow_version` text nullable
- `status` workflow_status not null
- `started_at` timestamptz not null
- `completed_at` timestamptz nullable
- `idempotency_key` text nullable
- `error_message` text nullable
- `metadata` jsonb nullable
- `created_at` timestamptz not null

Required fields:
- `id`
- `workflow_name`
- `status`
- `started_at`
- `created_at`

Foreign keys:
- `user_id -> users.id`
- `trigger_event_id -> events.id`

Indexes:
- index on `(user_id, started_at)`
- index on `(workflow_name, started_at)`
- index on `(status, started_at)`

Unique constraints:
- optional unique `(workflow_name, idempotency_key)` where `idempotency_key is not null`

JSONB fields:
- `metadata`

Soft delete:
- no

Audit/history:
- workflow run history retained

### `workflow_outputs`

Purpose:
- Stores structured workflow results returned by n8n/backend workflows.

Columns:
- `id` uuid primary key
- `workflow_run_id` foreign key to `workflow_runs.id`
- `user_id` foreign key to `users.id` nullable
- `schema_version` text not null
- `output_type` text not null
- `output_payload` jsonb not null
- `created_at` timestamptz not null

Required fields:
- `id`
- `workflow_run_id`
- `schema_version`
- `output_type`
- `output_payload`
- `created_at`

Foreign keys:
- `workflow_run_id -> workflow_runs.id`
- `user_id -> users.id`

Indexes:
- index on `(workflow_run_id)`
- index on `(user_id, created_at)`

Unique constraints:
- none in MVP

JSONB fields:
- `output_payload`

Soft delete:
- no

Audit/history:
- workflow output history retained

## Weekly Review

The requested MVP schema requires guarding against duplicate pending weekly reviews if represented.

### `weekly_reviews`

Purpose:
- Stores Imperium weekly strategic reviews.

Columns:
- `id` uuid primary key
- `user_id` foreign key to `users.id`
- `week_start_date` date not null
- `status` text not null
- `started_at` timestamptz nullable
- `completed_at` timestamptz nullable
- `summary_snapshot` jsonb nullable
- `detected_changes_count` integer nullable
- `created_by_event_id` foreign key to `events.id` nullable
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Required fields:
- `id`
- `user_id`
- `week_start_date`
- `status`
- `created_at`
- `updated_at`

Foreign keys:
- `user_id -> users.id`
- `created_by_event_id -> events.id`

Indexes:
- index on `(user_id, week_start_date)`
- partial unique index on `(user_id, week_start_date)` where `status = 'pending'`

Unique constraints:
- no duplicate pending weekly review for same user/week

JSONB fields:
- `summary_snapshot`

Soft delete:
- no

Audit/history:
- answers and completion events should be event-backed

## Critical Constraints Summary

Must be present in the final migration:

```sql
-- one canonical user record in V1
-- implementation strategy TODO: constant unique key or seeded singleton guard

-- one current mission per user
create unique index one_current_mission_per_user
on missions(user_id)
where status = 'current';

-- one active day session per user
create unique index one_active_day_session_per_user
on day_sessions(user_id)
where status = 'active';

-- unique event id
create unique index events_event_id_unique
on events(event_id);

-- idempotency per user
create unique index events_user_idempotency_unique
on events(user_id, idempotency_key);

-- no duplicate weekly financial summary for same week
create unique index weekly_financial_summary_user_week_unique
on weekly_financial_summaries(user_id, week_start_date);

-- no duplicate pending weekly review for same week
create unique index weekly_review_pending_user_week_unique
on weekly_reviews(user_id, week_start_date)
where status = 'pending';
```

## Explicit Non-Goals for MVP Schema

Do not add:
- organizations
- workspaces
- teams
- roles
- SaaS billing
- multi-tenant account hierarchy
- bank connection tables
- Bolt automation tables
- complex accounting ledger beyond transactions and adjustments
- mandatory wearable integration

## Open Database Decisions

TODO:
- final enum implementation strategy
- exact financial week boundary
- exact transaction edit history model
- exact raw media retention values
- exact pgvector embedding dimension/model
- exact workflow run linkage to n8n execution IDs
- exact backup and restore schema requirements
