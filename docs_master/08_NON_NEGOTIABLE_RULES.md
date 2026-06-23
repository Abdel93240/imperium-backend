# 08 - Non-Negotiable Rules

## Purpose

This document is the strict rule catalog for the personal AI ecosystem.

It is written to be machine-checkable later. Every rule has:
- `rule_id`
- `rule`
- `severity`
- `enforcement_layer`
- `affected_docs_or_modules`
- `example_violation`
- `expected_behavior`

Severity values:
- `critical`: must block implementation, merge, release, or workflow activation
- `high`: must be fixed before production use
- `medium`: must be tracked and fixed before feature completion

Enforcement layers:
- `documentation`
- `android`
- `backend_api`
- `postgresql`
- `pgvector`
- `n8n`
- `ai_router`
- `model_prompt`
- `media_storage`
- `backup`
- `manual_review`

## Imperium

```yaml
- rule_id: IMP-001
  rule: Only one active/current mission may exist per user.
  severity: critical
  enforcement_layer: [backend_api, postgresql, android]
  affected_docs_or_modules: [05_DATABASE_SCHEMA.md, 04_MVP_BACKEND_CONTRACTS.md, Imperium]
  example_violation: App creates a second current mission while one is already active.
  expected_behavior: Backend rejects or resolves the request through explicit replanning; PostgreSQL enforces a partial unique index.

- rule_id: IMP-002
  rule: Only one active day session may exist per user.
  severity: critical
  enforcement_layer: [backend_api, postgresql, android]
  affected_docs_or_modules: [05_DATABASE_SCHEMA.md, 12_DAILY_OBJECTIVE_PERIOD_LOGIC.md, Imperium]
  example_violation: User starts a new active day while yesterday's day session is still active.
  expected_behavior: Backend requires finishing, reconciling, or fallback-closing the existing active day session.

- rule_id: IMP-003
  rule: User priority hierarchy is user-defined, not hardcoded.
  severity: high
  enforcement_layer: [backend_api, postgresql, android, model_prompt]
  affected_docs_or_modules: [00_VISION_GLOBALE.md, 07_ANDROID_APP_RESPONSIBILITIES.md, Imperium]
  example_violation: Code always prioritizes VTC work above worship, family, health, or declared projects.
  expected_behavior: System reads priority rules from user-defined settings and explains any recommendation.

- rule_id: IMP-004
  rule: AI may adapt recommendations but must not silently rewrite priorities.
  severity: critical
  enforcement_layer: [backend_api, ai_router, model_prompt, android]
  affected_docs_or_modules: [02_AI_ROUTING_POLICY.md, 07_ANDROID_APP_RESPONSIBILITIES.md, Imperium]
  example_violation: AI changes the priority hierarchy after a bad day without user confirmation.
  expected_behavior: AI proposes a change; backend stores it only after explicit user confirmation.

- rule_id: IMP-005
  rule: Mission failure reasons must be stored and used for pattern detection.
  severity: high
  enforcement_layer: [backend_api, postgresql, pgvector, n8n]
  affected_docs_or_modules: [05_DATABASE_SCHEMA.md, 09_PGVECTOR_MEMORY_POLICY.md, Imperium]
  example_violation: Failed mission is stored only as status `failed` with no reason or learning signal.
  expected_behavior: Backend stores reason category/detail, emits event, and allows pattern detection workflows.

- rule_id: IMP-006
  rule: Nonsense or contradictory mission failure reasons are low confidence unless repeated.
  severity: medium
  enforcement_layer: [backend_api, pgvector, ai_router, model_prompt]
  affected_docs_or_modules: [09_PGVECTOR_MEMORY_POLICY.md, Imperium]
  example_violation: One illogical excuse becomes strong long-term memory and drives future planning.
  expected_behavior: Store as low confidence; do not strongly use it unless repeated or confirmed.
```

## Backend Authority

```yaml
- rule_id: AUTHORITY-001
  rule: Backend is the source of truth for canonical decisions.
  severity: critical
  enforcement_layer: [backend_api, postgresql, android, n8n]
  affected_docs_or_modules: [04_MVP_BACKEND_CONTRACTS.md, 05_DATABASE_SCHEMA.md, 07_ANDROID_APP_RESPONSIBILITIES.md, 14_OFFLINE_CLIENT_AUTHORITY.md]
  example_violation: Android app finalizes a mission or transaction without backend confirmation.
  expected_behavior: App sends request/event; backend validates, stores, and returns confirmed state.

- rule_id: AUTHORITY-002
  rule: Apps are interfaces.
  severity: critical
  enforcement_layer: [android, backend_api, documentation]
  affected_docs_or_modules: [07_ANDROID_APP_RESPONSIBILITIES.md, 14_OFFLINE_CLIENT_AUTHORITY.md]
  example_violation: App contains hidden strategic logic that changes priorities, finances, or missions locally.
  expected_behavior: Apps collect, display, trigger, explain, cache, and queue only.

- rule_id: AUTHORITY-003
  rule: n8n is the workflow engine, not the database owner.
  severity: critical
  enforcement_layer: [n8n, backend_api, postgresql]
  affected_docs_or_modules: [06_N8N_WORKFLOWS.md, 04_MVP_BACKEND_CONTRACTS.md]
  example_violation: n8n directly inserts missions or changes wallet balances in PostgreSQL.
  expected_behavior: n8n calls backend APIs for canonical writes.

- rule_id: AUTHORITY-004
  rule: n8n writes canonical data through backend APIs only in V1.
  severity: critical
  enforcement_layer: [n8n, backend_api, postgresql]
  affected_docs_or_modules: [06_N8N_WORKFLOWS.md, 04_MVP_BACKEND_CONTRACTS.md]
  example_violation: n8n directly updates `missions.status`.
  expected_behavior: n8n sends a signed request to a backend endpoint; backend validates and writes.

- rule_id: AUTHORITY-005
  rule: PostgreSQL is canonical truth for structured state.
  severity: critical
  enforcement_layer: [postgresql, backend_api]
  affected_docs_or_modules: [05_DATABASE_SCHEMA.md]
  example_violation: Current mission is derived only from vector memory or Android cache.
  expected_behavior: Current mission, sessions, transactions, reviews, and user-confirmed state come from PostgreSQL.

- rule_id: AUTHORITY-006
  rule: pgvector is semantic memory, never canonical truth.
  severity: critical
  enforcement_layer: [pgvector, ai_router, backend_api]
  affected_docs_or_modules: [09_PGVECTOR_MEMORY_POLICY.md, 05_DATABASE_SCHEMA.md]
  example_violation: System decides a transaction exists because similar memory was retrieved.
  expected_behavior: pgvector may inform context, but backend decisions combine memory with PostgreSQL truth.
```

## Events

```yaml
- rule_id: EVENT-001
  rule: All mutating actions require an idempotency_key.
  severity: critical
  enforcement_layer: [backend_api, postgresql, android, n8n]
  affected_docs_or_modules: [04_MVP_BACKEND_CONTRACTS.md, 05_DATABASE_SCHEMA.md, 14_OFFLINE_CLIENT_AUTHORITY.md]
  example_violation: Retried transaction request creates two expenses.
  expected_behavior: Backend requires idempotency_key and returns original result on duplicate.

- rule_id: EVENT-002
  rule: All important actions emit canonical dotted events.
  severity: critical
  enforcement_layer: [backend_api, postgresql, n8n]
  affected_docs_or_modules: [04_MVP_BACKEND_CONTRACTS.md, 06_N8N_WORKFLOWS.md]
  example_violation: Code emits `mission_completed` instead of `mission.completed`.
  expected_behavior: Canonical `event_type` uses dotted naming only.

- rule_id: EVENT-003
  rule: Events are append-only.
  severity: critical
  enforcement_layer: [postgresql, backend_api]
  affected_docs_or_modules: [04_MVP_BACKEND_CONTRACTS.md, 05_DATABASE_SCHEMA.md]
  example_violation: Normal app usage deletes old event rows to clean history.
  expected_behavior: Corrections are stored as new events; existing accepted events remain immutable.

- rule_id: EVENT-004
  rule: Duplicate idempotency keys must not duplicate effects.
  severity: critical
  enforcement_layer: [backend_api, postgresql]
  affected_docs_or_modules: [04_MVP_BACKEND_CONTRACTS.md, 05_DATABASE_SCHEMA.md]
  example_violation: Same `finish_day` retry closes two day sessions or triggers two reviews.
  expected_behavior: Backend returns original result, logs duplicate attempt, and creates no duplicate side effect.

- rule_id: EVENT-005
  rule: Every accepted event must use the canonical event envelope.
  severity: critical
  enforcement_layer: [backend_api, postgresql, n8n]
  affected_docs_or_modules: [04_MVP_BACKEND_CONTRACTS.md]
  example_violation: Event stored without `device_id`, `privacy_level`, or `correlation_id`.
  expected_behavior: Backend rejects malformed events or normalizes through a valid envelope before storage.
```

## Auth And Security

```yaml
- rule_id: SEC-001
  rule: V1 auth is one-user auth.
  severity: critical
  enforcement_layer: [backend_api, postgresql, android]
  affected_docs_or_modules: [05_DATABASE_SCHEMA.md, 04_MVP_BACKEND_CONTRACTS.md]
  example_violation: V1 adds organizations, workspaces, teams, roles, billing accounts, or tenant isolation.
  expected_behavior: Keep one canonical user record while retaining `user_id` for consistency.

- rule_id: SEC-002
  rule: Email/password and master key access are supported.
  severity: high
  enforcement_layer: [backend_api, postgresql, android]
  affected_docs_or_modules: [04_MVP_BACKEND_CONTRACTS.md, 05_DATABASE_SCHEMA.md]
  example_violation: App only supports a public SaaS OAuth flow.
  expected_behavior: Backend supports email/password and master access key/secret phrase for the single user.

- rule_id: SEC-003
  rule: Trusted devices are required.
  severity: critical
  enforcement_layer: [backend_api, postgresql, android]
  affected_docs_or_modules: [05_DATABASE_SCHEMA.md, 14_OFFLINE_CLIENT_AUTHORITY.md]
  example_violation: Unknown device uses a refresh token without being registered.
  expected_behavior: Backend requires registered device_id and supports revocation.

- rule_id: SEC-004
  rule: n8n webhooks require HMAC signature, idempotency key, timestamp, and replay protection.
  severity: critical
  enforcement_layer: [n8n, backend_api]
  affected_docs_or_modules: [04_MVP_BACKEND_CONTRACTS.md, 06_N8N_WORKFLOWS.md]
  example_violation: Public webhook accepts unsigned workflow writes or requests outside the 60-second replay window.
  expected_behavior: Webhook rejects unsigned, stale, replayed, or non-idempotent requests.

- rule_id: SEC-005
  rule: Backups must be encrypted.
  severity: critical
  enforcement_layer: [backup, postgresql, media_storage]
  affected_docs_or_modules: [05_DATABASE_SCHEMA.md, 10_RAW_MEDIA_RETENTION_POLICY.md]
  example_violation: PostgreSQL dump or media backup is stored unencrypted.
  expected_behavior: Backup process encrypts data and respects deletion/retention policies where possible.
```

## Privacy

```yaml
- rule_id: PRIV-001
  rule: External AI calls must pass the privacy gate.
  severity: critical
  enforcement_layer: [backend_api, ai_router, model_prompt]
  affected_docs_or_modules: [02_AI_ROUTING_POLICY.md, 03_MODEL_STRATEGY.md, 10_RAW_MEDIA_RETENTION_POLICY.md]
  example_violation: High privacy religious note is sent to a domain specialist without permission.
  expected_behavior: Backend checks privacy_level, data category, user settings, and explicit permission requirements.

- rule_id: PRIV-002
  rule: high and very_high data cannot leave the server unless allowed.
  severity: critical
  enforcement_layer: [backend_api, ai_router, media_storage]
  affected_docs_or_modules: [02_AI_ROUTING_POLICY.md, 09_PGVECTOR_MEMORY_POLICY.md, 10_RAW_MEDIA_RETENTION_POLICY.md]
  example_violation: Raw health photo is sent to external OCR by default.
  expected_behavior: Use local handling or require explicit permission before external provider use.

- rule_id: PRIV-003
  rule: Raw media must not be kept forever by accident.
  severity: critical
  enforcement_layer: [media_storage, backend_api, postgresql]
  affected_docs_or_modules: [10_RAW_MEDIA_RETENTION_POLICY.md, 05_DATABASE_SCHEMA.md]
  example_violation: Bolt screenshots remain indefinitely after OCR with no retention reason.
  expected_behavior: Store extracted structured data; expire/delete raw media unless explicitly retained.

- rule_id: PRIV-004
  rule: Summaries are preferred over raw storage.
  severity: high
  enforcement_layer: [backend_api, pgvector, media_storage]
  affected_docs_or_modules: [09_PGVECTOR_MEMORY_POLICY.md, 10_RAW_MEDIA_RETENTION_POLICY.md]
  example_violation: Raw audio transcripts are stored in vector memory by default.
  expected_behavior: Store minimal structured results or summaries; keep raw content only with explicit reason.

- rule_id: PRIV-005
  rule: User can delete or deactivate memory.
  severity: critical
  enforcement_layer: [backend_api, pgvector, postgresql]
  affected_docs_or_modules: [09_PGVECTOR_MEMORY_POLICY.md]
  example_violation: Incorrect memory continues to be retrieved after user correction.
  expected_behavior: Memory can be soft-deactivated, superseded, expired, or hard-deleted when requested. The chatbot is the user's channel to request this (add/modify/delete), always under explicit user validation before any write — see doc 72 §4.

- rule_id: PRIV-006
  rule: No AI write without explicit user validation.
  severity: critical
  enforcement_layer: [backend_api, pgvector, postgresql, media_storage]
  affected_docs_or_modules: [72_CHATBOT.md, 09_PGVECTOR_MEMORY_POLICY.md]
  example_violation: The chatbot deletes a document or writes a memory before the user validates.
  expected_behavior: AI proposes; the write executes only after explicit user validation.
```

## Vector

```yaml
- rule_id: VECTOR-001
  rule: No Bolt auto-click.
  severity: critical
  enforcement_layer: [android, backend_api, documentation]
  affected_docs_or_modules: [07_ANDROID_APP_RESPONSIBILITIES.md, 13_VECTOR_MVP_PHASE_DECISION.md]
  example_violation: Vector automatically clicks accept/refuse in Bolt.
  expected_behavior: Vector provides advice only; user performs any Bolt action manually.

- rule_id: VECTOR-002
  rule: No tap simulation.
  severity: critical
  enforcement_layer: [android, documentation]
  affected_docs_or_modules: [07_ANDROID_APP_RESPONSIBILITIES.md, 13_VECTOR_MVP_PHASE_DECISION.md]
  example_violation: App uses accessibility or input APIs to simulate a human tap.
  expected_behavior: Remove simulated interaction; keep decision support manual.

- rule_id: VECTOR-003
  rule: No fake GPS.
  severity: critical
  enforcement_layer: [android, documentation]
  affected_docs_or_modules: [13_VECTOR_MVP_PHASE_DECISION.md]
  example_violation: Vector changes device location to influence Bolt behavior.
  expected_behavior: Never implement fake location behavior.

- rule_id: VECTOR-004
  rule: No abusive accessibility automation.
  severity: critical
  enforcement_layer: [android, documentation]
  affected_docs_or_modules: [07_ANDROID_APP_RESPONSIBILITIES.md, 13_VECTOR_MVP_PHASE_DECISION.md]
  example_violation: Accessibility service controls Bolt, simulates actions, or acts as a hidden automation layer.
  expected_behavior: Accessibility may be used to READ on-screen content in order to ANALYZE an offer and DISPLAY advice (read-only, the user decides and acts). It must NEVER control Bolt, simulate actions, or act as a hidden automation layer. Read to advise, never act to decide.

- rule_id: VECTOR-005
  rule: Vector V1 is manual-first.
  severity: critical
  enforcement_layer: [android, backend_api, documentation]
  affected_docs_or_modules: [13_VECTOR_MVP_PHASE_DECISION.md, 07_ANDROID_APP_RESPONSIBILITIES.md]
  example_violation: V1 depends on live screen capture or notification interception to function.
  expected_behavior: V1 uses manual session start, objective reached button, manual inputs, manual screenshots, and on-demand recommendations.

- rule_id: VECTOR-006
  rule: Screenshots are manual upload in V1.
  severity: critical
  enforcement_layer: [android, media_storage, backend_api]
  affected_docs_or_modules: [13_VECTOR_MVP_PHASE_DECISION.md, 10_RAW_MEDIA_RETENTION_POLICY.md]
  example_violation: App continuously captures Bolt screens in the background.
  expected_behavior: User manually uploads screenshots; backend extracts and applies retention policy.
```

## The Vault

```yaml
- rule_id: VAULT-001
  rule: Wallet balances are derived from ledger, opening balance, and adjustments.
  severity: critical
  enforcement_layer: [postgresql, backend_api]
  affected_docs_or_modules: [05_DATABASE_SCHEMA.md]
  example_violation: Schema stores `wallet_cb_balance`, `wallet_cash_balance`, and `wallet_crypto_balance` as independent truth.
  expected_behavior: Use wallet records plus transactions and adjustments to derive balances.

- rule_id: VAULT-002
  rule: No fake financial truth.
  severity: critical
  enforcement_layer: [backend_api, postgresql, android]
  affected_docs_or_modules: [05_DATABASE_SCHEMA.md, 11_FINANCIAL_PRESSURE_FORMULA.md]
  example_violation: Expected future income is shown as confirmed available cash.
  expected_behavior: Distinguish confirmed, pending, projected, and hypothetical money.

- rule_id: VAULT-003
  rule: Sadaqa uses real profit, not pressure score.
  severity: critical
  enforcement_layer: [backend_api, postgresql]
  affected_docs_or_modules: [11_FINANCIAL_PRESSURE_FORMULA.md, 05_DATABASE_SCHEMA.md]
  example_violation: Sadaqa obligation is reduced because financial pressure score is high.
  expected_behavior: Calculate sadaqa from real confirmed profit according to explicit policy; pressure may inform caution but not replace basis.

- rule_id: VAULT-004
  rule: Financial pressure must be deterministic and explainable.
  severity: critical
  enforcement_layer: [backend_api, android, documentation]
  affected_docs_or_modules: [11_FINANCIAL_PRESSURE_FORMULA.md]
  example_violation: The finance specialist returns an unexplained financial pressure number.
  expected_behavior: Use deterministic formula and display factors/reasons.
```

## The Path

```yaml
- rule_id: PATH-001
  rule: No automatic inference of prayer completion.
  severity: critical
  enforcement_layer: [android, backend_api, model_prompt]
  affected_docs_or_modules: [05_DATABASE_SCHEMA.md, 07_ANDROID_APP_RESPONSIBILITIES.md]
  example_violation: App marks prayer complete because location or time suggests it.
  expected_behavior: Prayer completion requires explicit user action.

- rule_id: PATH-002
  rule: No automatic inference of fasting intention.
  severity: critical
  enforcement_layer: [android, backend_api, model_prompt]
  affected_docs_or_modules: [05_DATABASE_SCHEMA.md, 07_ANDROID_APP_RESPONSIBILITIES.md]
  example_violation: System assumes fasting because user woke before fajr.
  expected_behavior: Fasting intention/logging requires explicit user action.

- rule_id: PATH-003
  rule: No automatic inference of ghusl requirement.
  severity: critical
  enforcement_layer: [android, backend_api, model_prompt]
  affected_docs_or_modules: [05_DATABASE_SCHEMA.md, 07_ANDROID_APP_RESPONSIBILITIES.md]
  example_violation: AI infers ghusl state from private notes.
  expected_behavior: Ghusl-required activation is manual only.

- rule_id: PATH-004
  rule: No AI religious rulings in MVP.
  severity: critical
  enforcement_layer: [ai_router, model_prompt, android]
  affected_docs_or_modules: [07_ANDROID_APP_RESPONSIBILITIES.md, 02_AI_ROUTING_POLICY.md]
  example_violation: AI decides whether a fast is valid or gives fatwa-like rulings.
  expected_behavior: MVP supports operational tracking/reminders only; rulings require a future source policy.

- rule_id: PATH-005
  rule: The Path is operational tracking only unless source policy exists.
  severity: high
  enforcement_layer: [android, backend_api, ai_router]
  affected_docs_or_modules: [07_ANDROID_APP_RESPONSIBILITIES.md]
  example_violation: App creates spiritual obligations from AI interpretation.
  expected_behavior: App tracks explicit user actions and reminders; deeper religious guidance remains TODO until source policy exists.
```

## Pulse

```yaml
- rule_id: PULSE-001
  rule: Pulse has no medical authority.
  severity: critical
  enforcement_layer: [android, backend_api, model_prompt]
  affected_docs_or_modules: [07_ANDROID_APP_RESPONSIBILITIES.md]
  example_violation: Pulse diagnoses illness or presents medical certainty.
  expected_behavior: Pulse gives practical fitness/food support and recommends professional care when appropriate.

- rule_id: PULSE-002
  rule: Health and sport recommendations must be practical and confidence-aware.
  severity: high
  enforcement_layer: [ai_router, model_prompt, android]
  affected_docs_or_modules: [02_AI_ROUTING_POLICY.md, 07_ANDROID_APP_RESPONSIBILITIES.md]
  example_violation: AI recommends intense training despite weak data and no confidence warning.
  expected_behavior: Recommendation explains basis, confidence, and uncertainty.

- rule_id: PULSE-003
  rule: Fatigue and sleep patterns may adapt workout intensity.
  severity: high
  enforcement_layer: [backend_api, ai_router, model_prompt]
  affected_docs_or_modules: [05_DATABASE_SCHEMA.md, 09_PGVECTOR_MEMORY_POLICY.md]
  example_violation: Workout plan ignores repeated fatigue-related mission failures.
  expected_behavior: Backend/AI may lower intensity or recommend recovery when supported by current data and memory.
```

## Offline Mode

```yaml
- rule_id: OFFLINE-001
  rule: Apps may queue pending events offline.
  severity: high
  enforcement_layer: [android, backend_api]
  affected_docs_or_modules: [14_OFFLINE_CLIENT_AUTHORITY.md, 07_ANDROID_APP_RESPONSIBILITIES.md]
  example_violation: App drops offline expense input because network is unavailable.
  expected_behavior: App queues pending event with idempotency key and sync status.

- rule_id: OFFLINE-002
  rule: Backend confirms final truth.
  severity: critical
  enforcement_layer: [android, backend_api, postgresql]
  affected_docs_or_modules: [14_OFFLINE_CLIENT_AUTHORITY.md]
  example_violation: Offline app shows mission as completed before backend accepts it.
  expected_behavior: App shows pending until backend confirmation.

- rule_id: OFFLINE-003
  rule: Cached recommendations must be marked cached.
  severity: high
  enforcement_layer: [android]
  affected_docs_or_modules: [14_OFFLINE_CLIENT_AUTHORITY.md, 13_VECTOR_MVP_PHASE_DECISION.md]
  example_violation: Stale Vector recommendation is shown as live advice.
  expected_behavior: UI labels cached/stale status and timestamp.

- rule_id: OFFLINE-004
  rule: Backend wins conflicts.
  severity: critical
  enforcement_layer: [backend_api, android, postgresql]
  affected_docs_or_modules: [14_OFFLINE_CLIENT_AUTHORITY.md]
  example_violation: Offline local state overwrites a newer backend mission state silently.
  expected_behavior: Backend state wins; app shows conflict and user-visible reason.
```

## AI Routing

```yaml
- rule_id: AI-001
  rule: The local model handles simple, private, and fast tasks when suitable.
  severity: high
  enforcement_layer: [ai_router, backend_api]
  affected_docs_or_modules: [02_AI_ROUTING_POLICY.md, 03_MODEL_STRATEGY.md]
  example_violation: Simple private text classification is sent to a domain specialist by default.
  expected_behavior: Route simple/private/fast tasks to the local model when capability is sufficient.

- rule_id: AI-002
  rule: The transcription service handles transcription.
  severity: high
  enforcement_layer: [ai_router, backend_api]
  affected_docs_or_modules: [03_MODEL_STRATEGY.md, 04_MVP_BACKEND_CONTRACTS.md]
  example_violation: Voice audio is routed to a general reasoning model for transcription.
  expected_behavior: Use the transcription service for STT, then route transcript if needed.

- rule_id: AI-003
  rule: The OCR service handles OCR and image tasks when external use passes privacy gate.
  severity: high
  enforcement_layer: [ai_router, backend_api, media_storage]
  affected_docs_or_modules: [02_AI_ROUTING_POLICY.md, 03_MODEL_STRATEGY.md, 10_RAW_MEDIA_RETENTION_POLICY.md]
  example_violation: Screenshot OCR goes to the OCR service despite privacy gate denial.
  expected_behavior: Use the OCR service only when privacy policy allows; otherwise use local/manual fallback or ask permission.

- rule_id: AI-004
  rule: The first cloud tier or the high reasoning model handles complex reasoning and strategy.
  severity: medium
  enforcement_layer: [ai_router, model_prompt]
  affected_docs_or_modules: [02_AI_ROUTING_POLICY.md, 03_MODEL_STRATEGY.md]
  example_violation: The local model is asked to perform complex weekly strategic replanning beyond capability.
  expected_behavior: Route complex reasoning to the first cloud tier or the high reasoning model after privacy gate and cost/latency checks.

- rule_id: AI-005
  rule: Model outputs must carry confidence when inferred.
  severity: high
  enforcement_layer: [ai_router, model_prompt, backend_api, android]
  affected_docs_or_modules: [02_AI_ROUTING_POLICY.md, 09_PGVECTOR_MEMORY_POLICY.md]
  example_violation: OCR-derived transaction is presented as certain despite low confidence.
  expected_behavior: Store and display confidence; require confirmation when confidence is low or impact is high.
```

## MVP Boundaries

```yaml
- rule_id: MVP-000
  rule: Backend V1 stack is FastAPI, Python, SQLAlchemy, Alembic, PostgreSQL, pgvector, and UUID identifiers.
  severity: critical
  enforcement_layer: [documentation, backend_api, postgresql]
  affected_docs_or_modules: [04_MVP_BACKEND_CONTRACTS.md, 05_DATABASE_SCHEMA.md]
  example_violation: Backend skeleton starts with a different framework, ORM, migration tool, database, vector extension, or ID format without updating docs first.
  expected_behavior: Implement backend skeleton using the decided stack or explicitly revise this rule before coding.

- rule_id: MVP-001
  rule: Backend first.
  severity: critical
  enforcement_layer: [documentation, backend_api, postgresql]
  affected_docs_or_modules: [04_MVP_BACKEND_CONTRACTS.md, 05_DATABASE_SCHEMA.md]
  example_violation: Android UI implements flows before backend contracts/schema exist.
  expected_behavior: Define and preserve contracts, schema, events, idempotency, and authority before production UI behavior.

- rule_id: MVP-002
  rule: No UI polish before contracts and schema.
  severity: high
  enforcement_layer: [documentation, manual_review]
  affected_docs_or_modules: [04_MVP_BACKEND_CONTRACTS.md, 05_DATABASE_SCHEMA.md, 07_ANDROID_APP_RESPONSIBILITIES.md]
  example_violation: Building detailed animations while mission/event schema remains undefined.
  expected_behavior: Finalize developer-ready backend contracts and storage invariants first.

- rule_id: MVP-003
  rule: No real-time Android automation in Vector V1.
  severity: critical
  enforcement_layer: [android, documentation]
  affected_docs_or_modules: [13_VECTOR_MVP_PHASE_DECISION.md, 07_ANDROID_APP_RESPONSIBILITIES.md]
  example_violation: Vector V1 requires live screen capture, notification interception, or overlays.
  expected_behavior: Vector V1 remains manual-first and useful without real-time automation.

- rule_id: MVP-004
  rule: No bank sync in MVP.
  severity: high
  enforcement_layer: [backend_api, android, documentation]
  affected_docs_or_modules: [07_ANDROID_APP_RESPONSIBILITIES.md, 05_DATABASE_SCHEMA.md]
  example_violation: MVP connects unknown bank APIs and auto-imports unverified transactions.
  expected_behavior: Use manual declarations, receipts, and explicit correction flows.

- rule_id: MVP-005
  rule: No enterprise multi-user system in V1.
  severity: critical
  enforcement_layer: [backend_api, postgresql, android, documentation]
  affected_docs_or_modules: [00_VISION_GLOBALE.md, 05_DATABASE_SCHEMA.md]
  example_violation: V1 adds org roles, team invitations, tenant billing, or workspace permissions.
  expected_behavior: Keep one-user architecture with one canonical user record.
```

## Android App Boundary

```yaml
- rule_id: ANDROID-001
  rule: Android apps collect, display, trigger, and explain.
  severity: critical
  enforcement_layer: [android, backend_api]
  affected_docs_or_modules: [07_ANDROID_APP_RESPONSIBILITIES.md]
  example_violation: Android app finalizes strategy without backend validation.
  expected_behavior: App presents interface actions and backend-confirmed results.

- rule_id: ANDROID-002
  rule: Android apps request only permissions that are truly needed.
  severity: high
  enforcement_layer: [android, manual_review]
  affected_docs_or_modules: [07_ANDROID_APP_RESPONSIBILITIES.md]
  example_violation: App requests accessibility, background location, and storage permissions before any feature requires them.
  expected_behavior: Request minimum permissions at moment of need with clear purpose.

- rule_id: ANDROID-003
  rule: Notifications must not imply backend validation if none exists.
  severity: high
  enforcement_layer: [android, backend_api]
  affected_docs_or_modules: [07_ANDROID_APP_RESPONSIBILITIES.md, 14_OFFLINE_CLIENT_AUTHORITY.md]
  example_violation: Local notification says `Expense saved` while still offline.
  expected_behavior: Notification says `Expense pending sync` until backend confirms.
```

## Raw Media And Memory

```yaml
- rule_id: MEDIA-001
  rule: Raw audio is temporary by default.
  severity: high
  enforcement_layer: [media_storage, backend_api, android]
  affected_docs_or_modules: [10_RAW_MEDIA_RETENTION_POLICY.md]
  example_violation: Voice command audio is retained forever after successful transcription.
  expected_behavior: Keep transcript/structured result; delete raw audio unless explicitly archived.

- rule_id: MEDIA-002
  rule: Raw Bolt screenshots are not stored in vector memory by default.
  severity: critical
  enforcement_layer: [pgvector, media_storage, backend_api]
  affected_docs_or_modules: [09_PGVECTOR_MEMORY_POLICY.md, 10_RAW_MEDIA_RETENTION_POLICY.md]
  example_violation: Raw screenshot text is embedded as durable memory after every upload.
  expected_behavior: Store OCR extraction and summaries only when useful; memory writes require policy approval.

- rule_id: MEMORY-001
  rule: Inactive, expired, or superseded memory must not be retrieved.
  severity: critical
  enforcement_layer: [pgvector, backend_api, ai_router]
  affected_docs_or_modules: [09_PGVECTOR_MEMORY_POLICY.md]
  example_violation: Old corrected memory keeps influencing recommendations.
  expected_behavior: Retrieval filters `is_active`, expiry, status, privacy level, confidence, and workflow scope.
```
