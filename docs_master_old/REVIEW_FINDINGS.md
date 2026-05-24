# Review Findings - docs_master

## Historical Review Status

This file is a historical strict review snapshot.

It is kept for traceability, not as the current implementation gate.

Several findings in this file have since been resolved by later decisions and documents, including:
- canonical PostgreSQL schema
- n8n/backend responsibility boundary
- Android app responsibilities
- non-negotiable machine-checkable rules
- pgvector memory policy
- raw media retention policy
- financial pressure formula
- daily objective/period logic
- Vector MVP phase boundary
- offline client authority
- backend stack decision: FastAPI, Python, SQLAlchemy, Alembic, PostgreSQL, pgvector
- canonical ID format: UUID
- auth TTL and token storage decisions
- webhook HMAC-SHA256 signature decision

Use `08_NON_NEGOTIABLE_RULES.md`, `04_MVP_BACKEND_CONTRACTS.md`, and `05_DATABASE_SCHEMA.md` as the current source of truth before implementation.

## Review Position

This review is intentionally strict.

The current documentation is faithful to the product vision, but it is not yet strong enough to drive implementation safely. If coding starts from these files as-is, developers will fill gaps with assumptions, and those assumptions will diverge across API, database, n8n, AI routing, Android UI, and memory.

The biggest risk is not vision drift. The biggest risk is implementation ambiguity.

## Executive Summary

High-risk gaps:
- No canonical PostgreSQL schema exists yet.
- Canonical event envelope and idempotency are now defined; remaining work is per-event payload schemas and database constraints.
- n8n/backend responsibility boundary is now defined; individual workflow specs are still missing.
- pgvector is described conceptually but not operationally.
- AI routing has model principles but no executable routing matrix.
- MVP boundaries are broad enough that developers could overbuild.
- Variable naming is inconsistent between dictionary, API examples, event names, and proposed tables.
- Several variables are duplicated without clear canonical ownership.
- Important security, retention, and detailed privacy rules remain TODO.
- The one-user philosophy now has an auth direction, but its exact schema, token TTLs, key rotation, and recovery rules still need to be specified.

Recommendation:
- Do not write backend code yet.
- Create `05_DATABASE_SCHEMA.md`, `06_N8N_WORKFLOWS.md`, `07_ANDROID_APP_RESPONSIBILITIES.md`, and `08_NON_NEGOTIABLE_RULES.md` before backend implementation.
- Then revise `04_MVP_BACKEND_CONTRACTS.md` to match the schema and workflow docs.

## 1. Contradictions Between Documents

### F-001 - Qwen naming is inconsistent and implementation-hostile

Severity: High

Files:
- `00_VISION_GLOBALE.md`
- `02_AI_ROUTING_POLICY.md`
- `03_MODEL_STRATEGY.md`

Problem:
- The source vision says "Qwen local" and earlier docs mention "Qwen 4 Local / IA Master".
- The model strategy introduces "Qwen local E2B" and "Qwen local E4B".
- The routing policy uses "Qwen local E2B/E4B".
- No doc defines what E2B/E4B means technically.

Why this will break implementation:
- A backend developer cannot select, install, serve, benchmark, or route to these profiles without guessing.
- n8n workflow names and AI router model IDs will drift.

Required decision:
- Define canonical model IDs, for example `qwen_local_fast` and `qwen_local_reasoning`, then map them to actual checkpoints later.
- If E2B/E4B are placeholders, label them as placeholders and do not use them in contracts.

### F-002 - "IA Master" exists conceptually but not contractually

Severity: High

Files:
- `00_VISION_GLOBALE.md`
- `02_AI_ROUTING_POLICY.md`
- `03_MODEL_STRATEGY.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- The vision says central brain includes n8n, rules, PostgreSQL, pgvector, AI routing, and feedback.
- Routing docs imply Qwen does classification.
- Backend contracts expose `/api/ai/route`.
- No document defines whether "IA Master" is a service, an n8n workflow, a local model call, a router module, or a prompt policy.

Why this will break implementation:
- The codebase may accidentally create multiple "brains": backend router, n8n router, Qwen classifier, app-side route hints.

Required decision:
- Define exactly where routing authority lives.
- Recommended: backend owns routing policy and logs; n8n executes workflows; Qwen may classify but does not own final routing.

### F-003 - Event naming decision is resolved, but old examples must stay aligned

Severity: High

Files:
- `01_SIGNAL_VARIABLES_DICTIONARY.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Status:
- Resolved by decision: canonical event types use dotted names only.
- n8n workflow names may use snake_case.

Remaining risk:
- Future examples and workflow docs must keep this separation clean.

Why this will break implementation:
- One team may emit `mission.completed`, another may subscribe to `mission_completed`.
- n8n workflows may silently miss events.

Required follow-up:
- In `06_N8N_WORKFLOWS.md`, map each dotted `event_type` to one snake_case workflow name.

### F-004 - Source app names are not canonical

Severity: Medium

Files:
- `01_SIGNAL_VARIABLES_DICTIONARY.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- Source app values appear as `The Vault`, `The Path`, `Imperium`, `Vector`, `Pulse`.
- Endpoint paths use `/api/vault` and `/api/path`.
- Variables use categories like `The Vault`, `AI routing`, `feedback_learning`, `external_data`.

Why this will break implementation:
- Spaces in enum values create friction in code, logs, event topics, table constraints, and n8n filters.

Required decision:
- Define canonical enum values: `imperium`, `vault`, `vector`, `pulse`, `path`, `core`, `external`.
- Display names can remain human-readable.

### F-005 - The docs say no code yet, but backend contracts call themselves developer-ready

Severity: Medium

Files:
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- `04_MVP_BACKEND_CONTRACTS.md` says it is developer-ready.
- It also leaves base URL, auth, schemas, exact payloads, table schema, retention, n8n security, and endpoint behaviors as TODO.

Why this will break implementation:
- "Developer-ready" creates false confidence.

Required decision:
- Rename status to "draft contract" until schemas and workflow specs exist.

## 2. Missing Decisions

### F-006 - Authentication core model is decided, but implementation details remain missing

Severity: Critical

Files:
- `00_VISION_GLOBALE.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Status:
- Partially resolved by decision: one canonical user, email/password, master access key / secret phrase, registered trusted devices, JWT access tokens, device-bound refresh tokens, device revocation.

Remaining problem:
- The system handles finance, health, location, religious privacy, screenshots, audio, and personal documents, so the auth model still needs implementation-level detail.

Missing decisions:
- Access token TTL.
- Refresh token TTL.
- Refresh token hashing/storage format.
- Master access key / secret phrase storage, rotation, and recovery behavior.
- Local network vs public VPS exposure.
- Admin/manual recovery access.

Required before coding:
- Define the concrete auth schema and token lifecycle.

### F-007 - File/media retention is undefined

Severity: Critical

Files:
- `02_AI_ROUTING_POLICY.md`
- `03_MODEL_STRATEGY.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- Raw screenshots, receipts, audio, documents, OCR text, and transcripts may be stored.
- Retention policy is TODO everywhere.

Why this is dangerous:
- Raw Bolt screenshots and audio can become a privacy and compliance liability.
- Religious and financial data need stricter rules than generic app logs.

Required decisions:
- What raw media is stored.
- How long raw media is stored.
- Whether raw media can be deleted after extraction.
- Whether transcripts are stored fully, summarized, or discarded.
- Whether pgvector stores summaries only or chunks of sensitive documents.

### F-008 - Backend framework and runtime are undecided

Severity: High

Files:
- `00_VISION_GLOBALE.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- Exact backend framework is TODO.
- This blocks API implementation style, validation, migrations, auth middleware, and background job approach.

Required decision:
- Choose framework and migration stack before schema or endpoint code.

### F-009 - Local model serving architecture is undecided

Severity: High

Files:
- `03_MODEL_STRATEGY.md`

Problem:
- Model checkpoint, quantization, runtime, GPU/CPU, concurrency, queueing, and warmup are all TODO.

Why this matters:
- The docs assume local Qwen and local faster-whisper may be practical on 16 GB RAM, but no benchmark or fallback boundary exists.

Required decision:
- Create a benchmark task before promising local workloads in MVP.

### F-010 - External AI privacy gate is decided, but permission matrix is missing

Severity: Critical

Files:
- `01_SIGNAL_VARIABLES_DICTIONARY.md`
- `02_AI_ROUTING_POLICY.md`

Status:
- Partially resolved by decision: before sending data to Gemini, GPT, Claude, or any external provider, the backend must check privacy level, data category, user setting, and explicit permission requirement when needed.

Remaining problem:
- The dictionary labels privacy levels, but no exact permission matrix says which categories require explicit permission, which are blocked, and which are allowed by user setting.

Required decisions:
- Which data classes may leave the server.
- Whether user must explicitly enable external AI for high/very_high data.
- Whether Gemini OCR can receive raw Bolt screenshots by default.
- Whether GPT/Claude can receive financial/religious/health summaries.

### F-011 - Push notifications are mentioned but not specified

Severity: Medium

Files:
- `00_VISION_GLOBALE.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- Push notification routing is part of architecture.
- Provider is TODO.
- No notification payload contract exists.

Required decisions:
- Provider.
- Notification event types.
- Quiet hours.
- Critical notification rules.
- How prayer/ghusl/mission alerts interact.

## 3. Unclear MVP Boundaries

### F-012 - MVP includes too many app domains at once

Severity: High

Files:
- `00_VISION_GLOBALE.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- MVP includes Imperium, Vault, AI routing, memory, Vector, Path, Pulse, voice, OCR, n8n, PostgreSQL, pgvector.

Why this is risky:
- This is not a thin MVP. It is a multi-system platform.
- Without phase boundaries, backend implementation may become unfinished everywhere.

Required decision:
- Split MVP into strict phases:
  1. Core event log + auth + PostgreSQL.
  2. Imperium one-mission loop.
  3. Vault transactions and pressure.
  4. AI routing logs without full automation.
  5. n8n workflows.
  6. Vector/Path/Pulse minimal integrations.

### F-013 - Vector real-time assistant may be too advanced for MVP

Severity: High

Files:
- `00_VISION_GLOBALE.md`
- `02_AI_ROUTING_POLICY.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- MVP includes ride offer extraction pipeline, screenshot OCR, halo response, sound trigger, session learning, destination mode, fuel.

Why this is risky:
- Android screen capture, sound detection, overlay/halo UI, OCR latency, and legal guardrails are all complex.

Required decision:
- Define Vector MVP as manual screenshot upload first, unless screen capture/overlay is explicitly prioritized.
- Keep sound detection and halo overlay as later phase unless proven feasible.

### F-014 - Pulse MVP is underbounded

Severity: Medium

Files:
- `00_VISION_GLOBALE.md`
- `01_SIGNAL_VARIABLES_DICTIONARY.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- Pulse includes biological profile, health score, workout, nutrition, stock, grocery, batch cooking, wearable sync.

Why this is risky:
- This is several products, not one MVP slice.

Required decision:
- Choose one Pulse MVP slice: manual biological profile + simple workout adaptation, or stock/grocery, not all at once.

### F-015 - The Path MVP is broad but religious correctness policy is missing

Severity: High

Files:
- `00_VISION_GLOBALE.md`
- `02_AI_ROUTING_POLICY.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- The Path includes prayer, mosque times, qibla, ghusl, fasting, lunar calendar, Quran, adhkar, sadaqa.
- Routing policy explicitly leaves religious ruling model policy as TODO.

Why this is risky:
- The system may generate religious advice without source constraints.

Required decision:
- The Path MVP should focus on operational tracking and constraints.
- Explicitly prohibit AI religious rulings until a source policy exists.

## 4. Duplicated Variables

### F-016 - Duplicate variables are not marked as aliases or canonical references

Severity: High

File:
- `01_SIGNAL_VARIABLES_DICTIONARY.md`

Duplicates found:
- `planning_confidence_level`
- `energy_score`
- `discipline_score`
- `financial_pressure_score`
- `health_score`

Problem:
- Some duplicates are cross-references, but the table format treats them as independent variables.

Why this will break implementation:
- Schema designers may create duplicate columns or duplicate computed fields.
- API payloads may return both variants with inconsistent values.

Required decision:
- Add a `canonical_owner` or `canonical_variable` column.
- For derived scores, use either canonical row plus references, or explicit alias rows.

### F-017 - Daily financial target names are duplicated with different naming

Severity: Medium

Files:
- `01_SIGNAL_VARIABLES_DICTIONARY.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- Dictionary uses `daily_minimal_target`, `daily_comfortable_target`, `daily_optimal_target`.
- Derived scores use `daily_objective_minimal`, `daily_objective_comfortable`, `daily_objective_optimal`.
- API response uses `daily_objectives.minimal`, `comfortable`, `optimal`.

Required decision:
- Pick canonical names.
- Recommended: `daily_objective_minimal`, `daily_objective_comfortable`, `daily_objective_optimal`.

### F-018 - Location variables are too generic for event-scoped storage

Severity: Medium

File:
- `01_SIGNAL_VARIABLES_DICTIONARY.md`

Problem:
- `latitude`, `longitude`, `location_text`, and `location_source` are global names but used across transactions, ride offers, mosque choice, workouts, fuel, and device state.

Why this will break implementation:
- Developers may store current location when they should store event location.

Required decision:
- Define context-specific names in schema/payloads:
  - `transaction_location_*`
  - `current_device_location_*`
  - `ride_pickup_location_*`
  - `recommended_mosque_location_*`

## 5. Badly Named Variables

### F-019 - `source_app` and `request_source_app` conflict

Severity: Medium

File:
- `01_SIGNAL_VARIABLES_DICTIONARY.md`

Problem:
- Device context defines `source_app`.
- AI routing defines `request_source_app`.
- API examples use `source_app`.

Required decision:
- Use `source_app` everywhere unless there is a clear need for `request_source_app`.

### F-020 - `wallet_cb_balance`, `wallet_cash_balance`, `wallet_crypto_balance` hardcode schema as variables

Severity: Medium

File:
- `01_SIGNAL_VARIABLES_DICTIONARY.md`

Problem:
- These variables encode wallet types into field names.

Why this is weak:
- Even if V1 wallet types are fixed, database design should likely use rows with `wallet_type`, not one column per wallet.

Required decision:
- In dictionary, represent `wallet_balance` with `wallet_type`.
- Keep fixed enum values for V1.

### F-021 - `mission_target` is too vague

Severity: Medium

File:
- `01_SIGNAL_VARIABLES_DICTIONARY.md`

Problem:
- Example is `250 EUR CA`, but the data type is `string nullable`.

Why this is dangerous:
- VTC revenue target, Quran pages, workout duration, grocery list, prayer mission, and project action targets will all need different structures.

Required decision:
- Define `mission_target_type`, `mission_target_value`, `mission_target_unit`, and optional `mission_target_metadata`.

### F-022 - `health_score_positive_factors` and `health_score_negative_factors` are UI text, not canonical signals

Severity: Low

File:
- `01_SIGNAL_VARIABLES_DICTIONARY.md`

Problem:
- These may be generated explanations rather than durable structured variables.

Required decision:
- Store as explanation artifacts, not core signal variables, unless they are normalized factors.

### F-023 - `event_value` and `event_value_score` are ambiguous

Severity: Medium

File:
- `01_SIGNAL_VARIABLES_DICTIONARY.md`

Problem:
- `event_value` could mean external event signal strength, financial value, or VTC opportunity value.

Required decision:
- Rename to `vtc_event_opportunity_score` or define exact meaning.

## 6. Backend Contracts Too Vague

### F-024 - Endpoint contracts lack request/response schemas

Severity: Critical

File:
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- Endpoint tables list method, path, purpose, trigger.
- Most endpoints have no request schema, response schema, validation errors, auth requirements, idempotency rules, or side effects.

Why this will break implementation:
- Android, backend, and n8n cannot build against the same contract.

Required decision:
- Add per-endpoint contract sections for MVP endpoints only.

### F-025 - Generic `/api/events` now has an envelope, but payload schemas are still missing

Severity: High

File:
- `04_MVP_BACKEND_CONTRACTS.md`

Status:
- Partially resolved by decision: canonical event envelope is defined with required fields.

Remaining problem:
- Event-specific `payload` schemas are still not defined.
- `payload_version` was not included in the canonical envelope; `schema_version` may be enough, but this must be intentional.

Required follow-up:
- Define payload schemas per event in `04_MVP_BACKEND_CONTRACTS.md` or a dedicated event catalog.

### F-026 - Idempotency rule is defined, but storage constraints remain missing

Severity: Critical

File:
- `04_MVP_BACKEND_CONTRACTS.md`

Status:
- Partially resolved by decision: every mutating action must include `idempotency_key`; duplicates must return original result and log duplicate attempt.

Remaining problem:
- PostgreSQL constraint, original-result storage, and duplicate response behavior are not yet specified at schema level.

Required decision:
- Define database indexes and idempotency result storage in `05_DATABASE_SCHEMA.md`.

### F-027 - Error codes are almost absent

Severity: High

File:
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- Only one example error exists: `ONE_ACTIVE_MISSION_VIOLATION`.

Missing error families:
- auth errors
- validation errors
- duplicate event
- stale mission state
- inactive day session
- OCR low confidence
- model unavailable
- n8n workflow failed
- pgvector unavailable
- external provider unavailable
- privacy policy blocked external model

### F-028 - State snapshots are undefined

Severity: High

File:
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- `/api/apps/{app}/state`, `/api/imperium/dashboard`, `/api/vault/dashboard`, `/api/pulse/dashboard`, and `/api/path/prayers/today` are mentioned but not shaped.

Why this matters:
- Android UI work cannot begin safely without state contracts.

Required decision:
- Define dashboard response schemas for each app MVP.

### F-029 - `POST /api/ai/route` creates dangerous external API surface

Severity: High

File:
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- It exposes routing as a direct endpoint, but does not say who can call it or whether apps may bypass domain endpoints.

Why this is dangerous:
- Apps could start depending on generic AI calls instead of domain-safe workflows.

Required decision:
- Decide if `/api/ai/route` is internal-only.
- Recommended: domain endpoints call router internally; apps should not call generic AI route except specific approved voice/chat flows.

## 7. Missing PostgreSQL Decisions

### F-030 - No schema exists

Severity: Critical

File:
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- Table names are recommendations.
- Exact schema is TODO.

Required before coding:
- Create `05_DATABASE_SCHEMA.md`.

### F-031 - Mission uniqueness is not enforceable from docs

Severity: Critical

Files:
- `01_SIGNAL_VARIABLES_DICTIONARY.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- The docs say only one current mission.
- They do not define the database constraint.

Required decision:
- Define partial unique index:
  - one `missions` row with `status = 'current'` per `user_id`.
- Define transaction behavior when completing/replacing missions.

### F-032 - Day session uniqueness is not enforceable from docs

Severity: High

Problem:
- Only one active day session is allowed.
- No constraint is defined.

Required decision:
- Define partial unique index for active day session per user.

### F-033 - Wallet balance source of truth is unclear

Severity: High

Files:
- `00_VISION_GLOBALE.md`
- `01_SIGNAL_VARIABLES_DICTIONARY.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- Wallet balances are manual or derived from transactions and/or manually initialized balances.
- `wallet_balances` table is listed but no accounting rule exists.

Required decisions:
- Are balances calculated from transaction ledger plus opening balance?
- Can user manually adjust wallet balance?
- Are adjustments transactions?
- How are corrections represented?

### F-034 - Transaction edit audit trail is missing

Severity: Medium

Problem:
- Editing is anticipated, but no audit model exists.

Required decision:
- Define whether transaction edits overwrite rows or create revision/history records.

### F-035 - Timezone/date boundaries are not defined

Severity: High

Problem:
- Daily missions, daily objectives, prayer times, fasting, VTC sessions, weekly review, and finance periods all depend on date boundaries.

Required decisions:
- Canonical timezone storage.
- Whether timestamps are stored UTC plus timezone.
- Definition of "day" for VTC night sessions.
- Definition of financial week/month.

### F-036 - User ID model conflicts with one-user architecture

Severity: Medium

Problem:
- `user_id` exists everywhere, but no decision says whether it is a literal fixed value, UUID, seeded row, or future-proof field.

Required decision:
- Define one technical user record and migration seed policy.

### F-037 - External data storage is unspecified

Severity: Medium

Problem:
- Rail, events, traffic, airports, maps, MAWAQIT are variables, but no tables or cache policies are defined.

Required decisions:
- Which external feed responses are cached.
- TTL per feed.
- Normalized tables vs raw provider payloads.
- Failure behavior when stale.

## 8. Missing pgvector Decisions

### F-038 - No embedding schema exists

Severity: Critical

Files:
- `01_SIGNAL_VARIABLES_DICTIONARY.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- pgvector memory objects are listed, but no schema exists.

Required fields:
- `memory_id`
- `user_id`
- `source_app`
- `source_table`
- `source_id`
- `memory_type`
- `content`
- `embedding`
- `embedding_model`
- `created_at`
- `expires_at`
- `privacy_level`
- `confidence`
- `is_active`
- `supersedes_memory_id`

### F-039 - Memory write policy is too vague

Severity: High

Problem:
- "Write memory only after meaningful events" is not enough.

Required decision:
- Define which events write memory automatically.
- Define which events require user approval.
- Define which raw content is forbidden from vector memory.

### F-040 - Memory deletion and correction are absent

Severity: Critical

Problem:
- User corrections are central to the product.
- If pgvector stores old wrong assumptions, future AI may keep using them.

Required decisions:
- How to deactivate outdated memories.
- How corrections supersede old memories.
- Whether memory search filters inactive/superseded chunks.

### F-041 - Retrieval policy is absent

Severity: High

Problem:
- No top-k, similarity threshold, memory type filtering, privacy filtering, or recency logic exists.

Why this matters:
- AI may retrieve irrelevant or sensitive memories.

Required decision:
- Define retrieval scopes per workflow.

### F-042 - pgvector and PostgreSQL truth boundary needs stronger enforcement

Severity: High

Problem:
- Docs say pgvector is not canonical truth, but no workflow rule enforces it.

Required decision:
- Define that every memory used for a decision must be paired with current PostgreSQL truth when the decision affects missions, finance, health, worship, or VTC.

## 9. Unclear n8n Workflows

### F-043 - Workflow names exist but no workflow specs exist

Severity: Critical

File:
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- n8n triggers list "expected workflow" in prose only.

Missing:
- inputs
- outputs
- nodes
- model calls
- DB reads/writes
- retry policy
- timeout policy
- failure path
- idempotency
- side effects
- security

Required before coding:
- Create `06_N8N_WORKFLOWS.md`.

### F-044 - n8n/backend responsibility boundary is decided, workflow specs still needed

Severity: Critical

Files:
- `00_VISION_GLOBALE.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Status:
- Resolved by decision: backend is source of truth and gatekeeper; n8n orchestrates workflows.
- In V1, n8n must write canonical app data through backend APIs, not directly to PostgreSQL.

Remaining problem:
- Individual n8n workflow specs are still missing.

Required follow-up:
- Define each workflow's trigger, inputs, outputs, backend API calls, retries, timeouts, and failure behavior in `06_N8N_WORKFLOWS.md`.

### F-045 - Scheduled workflows are underspecified

Severity: High

Problem:
- Daily cycle and weekly review due exist but no schedule timezone, missed-run behavior, duplicate prevention, or recovery behavior exists.

Required decisions:
- Scheduler source.
- Timezone.
- If server is down, should missed jobs run on startup?
- How weekly review pending state is deduplicated.

### F-046 - Webhook protection model is decided, but cryptographic details are missing

Severity: Critical

File:
- `04_MVP_BACKEND_CONTRACTS.md`

Status:
- Partially resolved by decision: every internal webhook must use internal secret header, request signature, idempotency key, and timestamp/replay protection.

Remaining problem:
- Exact signature algorithm, timestamp tolerance, secret rotation, and failure handling are not defined.

Required decision:
- Define signature algorithm, replay window, secret rotation policy, and whether IP allowlists are also required.

## 10. Dangerous Assumptions

### F-047 - 16 GB RAM may not support the promised local AI stack

Severity: High

File:
- `03_MODEL_STRATEGY.md`

Problem:
- The docs assume local Qwen, faster-whisper, PostgreSQL, pgvector, n8n, backend, and possibly file processing on a 16 GB server.

Risk:
- Model latency or memory pressure may make "fast/private/local" impossible in practice.

Required action:
- Benchmark before committing MVP workflows to local models.

### F-048 - Real-time Vector workflow assumes Android capabilities not validated

Severity: High

Files:
- `00_VISION_GLOBALE.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- Sound detection, screen capture, overlay halo, and low-latency OCR are assumed.

Risk:
- Android permissions, background restrictions, overlay rules, and battery behavior could block this design.

Required action:
- Validate Android feasibility before making this MVP-critical.

### F-049 - Financial pressure score is described but not computable

Severity: High

Files:
- `01_SIGNAL_VARIABLES_DICTIONARY.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- Pressure score appears in API examples and variables.
- Formula is not defined.

Risk:
- Developers invent arbitrary scoring, weakening trust.

Required decision:
- Define V1 deterministic formula, even if simple.

### F-050 - Daily objectives depend on undefined period logic

Severity: High

Files:
- `01_SIGNAL_VARIABLES_DICTIONARY.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- `remaining_charges / remaining_days` requires knowing period, useful days, mandatory charges, optional expenses, and whether today counts.

Required decision:
- Define financial period model and useful workday calculation.

### F-051 - Religious automation boundary needs stronger wording

Severity: High

Files:
- `00_VISION_GLOBALE.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- Ghusl activation is manual, but after activation everything becomes automatic.
- This is fine, but the backend must distinguish religious state from mission automation.

Risk:
- A future workflow may infer ghusl or worship states from behavior, which violates privacy.

Required decision:
- Add explicit rule: never infer ghusl required, fasting intention, prayer completion, Quran completion, adhkar completion, or sadaqa completion without user action.

### F-052 - "Apps are interfaces" may be violated by offline mode

Severity: Medium

Files:
- `02_AI_ROUTING_POLICY.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- Offline mode says use deterministic rules/local Qwen and queue external workflows.
- But apps are not supposed to be the brain.

Risk:
- Android app may start making local strategic decisions offline.

Required decision:
- Define offline client authority:
  - what app may do locally
  - what must wait for backend
  - how queued events reconcile

### F-053 - Data confidence is not consistently part of contracts

Severity: Medium

Files:
- `01_SIGNAL_VARIABLES_DICTIONARY.md`
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- Confidence appears in OCR, health, model output, planning, but not in standard response contracts.

Required decision:
- Define a common confidence object for AI-generated or inferred outputs.

### F-054 - No migration/versioning strategy exists

Severity: High

File:
- `04_MVP_BACKEND_CONTRACTS.md`

Problem:
- API payloads, event schemas, database tables, model prompts, and n8n workflows will evolve.
- No versioning strategy exists.

Required decisions:
- API version.
- Event schema version.
- n8n workflow version.
- business rule version.
- memory schema version.

## Required Next Documentation Before Coding

### 1. `05_DATABASE_SCHEMA.md`

Must include:
- canonical table list
- columns
- data types
- enums
- indexes
- uniqueness constraints
- foreign keys
- soft delete policy
- audit history policy
- timezone strategy
- idempotency storage
- transaction boundaries

Minimum critical constraints:
- one current mission per user
- one active day session per user
- unique event id/idempotency key
- fixed wallet enum
- no duplicate weekly review pending for same period

### 2. `06_N8N_WORKFLOWS.md`

Must include for each workflow:
- trigger name
- input schema
- output schema
- nodes/steps
- backend endpoints called
- DB writes allowed or forbidden
- model calls
- retry policy
- timeout policy
- failure response
- idempotency behavior
- logging

### 3. `07_ANDROID_APP_RESPONSIBILITIES.md`

Must include:
- what each app may calculate locally
- what each app must ask backend for
- offline mode boundaries
- permission handling
- voice input flow
- screen capture flow
- file upload flow
- UI state contracts
- no-Bolt-automation rule in app terms

### 4. `08_NON_NEGOTIABLE_RULES.md`

Must include machine-checkable rules:
- one current mission
- no Bolt automation
- no auto religious inference
- no project completion without validation
- no upcoming expense converted to transaction automatically
- no bank sync in MVP
- pgvector never canonical truth
- AI outputs must carry confidence where inferred
- external model privacy gates

## Strict Implementation Gate

Do not start backend code until these are resolved:

1. Auth schema, token TTLs, and secret/key lifecycle.
2. PostgreSQL schema.
3. Event payload schemas and idempotency storage constraints.
4. n8n workflow specs and backend API call list.
5. pgvector schema and memory write/delete policy.
6. Raw media retention policy.
7. Financial pressure formula V1.
8. Daily objective period logic.
9. Vector MVP phase decision.
10. Offline client authority.

If these remain TODO, future coding will appear to work at first and then fail through inconsistent state, privacy leaks, duplicated logic, and n8n/backend drift.
