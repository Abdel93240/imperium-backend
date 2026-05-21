# 14 - Offline Client Authority

## Purpose

This document defines exactly what Android apps may do locally and what must wait for backend validation.

Core principle:

> Apps are interfaces. Backend is the brain.

Offline mode exists for reliability, not to replace backend authority.

The Android apps may capture, queue, display, and remind. They must not silently become the decision engine.

## Authority Model

### Local Interface Authority

The app may:
- collect user input
- validate basic form shape
- store temporary pending events
- show cached state
- notify the user
- queue sync attempts

This is interface authority only.

### Backend Canonical Authority

The backend decides and validates:
- canonical state changes
- event acceptance
- idempotency
- mission status
- day closure
- financial truth
- wallet balances
- sadaqa obligations
- VTC session truth
- priority rules
- privacy gates
- AI routing
- memory writes

### User Explicit Authority

Some truth requires explicit user action.

Examples:
- prayer completion
- fasting intention
- ghusl-required activation
- sadaqa completion
- project completion
- weekly review completion
- manual correction of AI result

The app may collect this action offline, but the backend must confirm persistence.

## Allowed Local Actions

Apps may safely do the following offline.

### Capture User Input

Allowed:
- typed notes
- form drafts
- mission failure reason draft
- expense declaration draft
- VTC revenue input draft
- food stock update draft
- workout completion note draft
- worship log draft created by explicit user action

Local capture does not equal backend acceptance.

### Queue Events

Allowed:
- create local pending event records
- attach idempotency keys
- retry sync later
- show pending status

Queued events must preserve the canonical event envelope fields where possible.

### Display Last Known State

Allowed:
- last mission state
- last day session state
- last financial snapshot
- last Vector session status
- last prayer times
- last recommendation
- last weekly objective snapshot

The app must indicate when displayed state may be stale.

### Show Cached Recommendations

Allowed only when clearly marked as cached.

Example:

```text
Cached recommendation, not live:
Return toward Paris.
Last updated: 14:20.
```

Never present stale advice as live truth.

### Create Temporary Local Notes

Allowed:
- scratch notes
- unprocessed voice note metadata
- draft reminder
- draft expense note
- local VTC note

Temporary local notes must be syncable, editable, and deletable.

### Record Audio Before Upload

Allowed:
- record voice command
- store encrypted temporary file where possible
- queue upload
- retry later

The app must not perform fake strategic interpretation locally.

### Upload Later

Allowed:
- retry media upload
- retry event sync
- retry extraction request

The backend decides final action after upload.

### Create Temporary Reminders

Allowed:
- local notification reminder
- reminder draft
- timer notification

If the reminder requires canonical state, the app must mark it as local until synced.

### Basic UI Navigation

Allowed:
- open screens
- switch tabs
- show cached dashboards
- edit drafts
- prepare forms

### Show Cached Prayer Times

Allowed if:
- source is known
- calculation method is known
- timezone/location context is known or marked stale

Prayer completion must still never be inferred automatically.

### Show Cached Financial Snapshot

Allowed if clearly marked as cached.

The app must not calculate wallet authority from offline-only edits.

### Show Cached Mission State

Allowed if clearly marked as cached.

The app must not assume mission creation, completion, or failure is final until backend confirmation.

## Forbidden Local Authority

Apps must not locally decide final truth for the following.

### Mission Authority

Forbidden offline:
- final mission creation
- mission completion validation
- mission failure finalization
- active mission replacement
- mission status conflict resolution

The app may request these actions. The backend confirms them.

### Financial Authority

Forbidden offline:
- final financial truth updates
- wallet balance authority
- transaction deduplication authority
- weekly financial summary finalization
- financial pressure authority
- daily objective authority
- sadaqa obligation truth

Offline app calculations may be previews only.

### Vector Authority

Forbidden offline:
- VTC strategy authority
- live strategic recommendation presented as current truth
- session close finalization without backend confirmation
- final revenue truth
- final expense truth

Vector may show cached recommendations or collect manual notes.

### AI and Memory Authority

Forbidden offline:
- AI routing authority
- long-term memory truth
- pgvector writes
- priority rule silent rewrites
- strategic interpretation of voice commands
- storing durable AI conclusions as truth

### Religious Authority

Forbidden offline:
- religious completion inference
- prayer completion inference
- fasting intention inference
- sadaqa completion inference
- ghusl state inference
- Quran completion inference
- adhkar completion inference

The app may record explicit user actions as pending.

## Temporary Offline Actions

The app may accept offline actions only with a pending state.

Examples:
- expense declaration
- mission failure reason
- voice command
- manual VTC revenue input
- manual VTC expense input
- food stock update
- workout completion note
- explicit prayer log
- local reminder creation

Required statuses:
- `pending`
- `syncing`
- `synced`
- `failed`
- `conflict`
- `cancelled`

The app must show the status.

Never pretend success before confirmation.

## Pending Status Rules

Every pending item must show:
- action type
- created time
- sync status
- retry status if relevant
- failure reason if failed
- conflict reason if conflicted

The user must be able to:
- retry
- edit if still local
- cancel if not yet accepted by backend
- inspect failure reason
- delete local draft where safe

## Conflict Resolution

If local offline state conflicts with backend state:

```text
Backend wins.
```

But the conflict must be visible.

No silent overwrite.

Examples:
- duplicate expense
- already completed mission
- conflicting prayer log
- duplicated session close
- stale objective snapshot
- mission changed while app was offline

Conflict response should include:
- local action
- backend state
- reason for rejection or merge
- user options if available

User-facing example:

```text
Expense not synced.
Backend found a possible duplicate fuel expense from 16:42.
Review before saving.
```

## Voice Flow Offline

The user may record voice offline.

Flow:

```text
audio recorded locally
-> queued securely
-> uploaded later
-> transcription
-> AI routing
-> backend decision
-> final action returned
```

Rules:
- local app stores the audio temporarily
- audio is encrypted if possible
- app records metadata and idempotency key
- app uploads when network returns
- backend handles transcription request
- AI router decides model/workflow
- backend applies final validated action
- raw audio retention follows `10_RAW_MEDIA_RETENTION_POLICY.md`

Do not perform fake strategic interpretation locally.

Allowed local behavior:
- show `Voice note pending upload`
- play back/delete local recording
- retry upload

Forbidden local behavior:
- decide mission creation from the recording
- decide transaction creation from the recording
- decide routing to GPT/Gemini/Claude
- store transcript as truth before backend processing

## Cached Recommendation Policy

Cached recommendations are allowed only if clearly labeled.

Example:

```text
Last known Vector recommendation:
Return toward Paris.

Status: cached, not live.
Generated at: 14:20.
```

Cached recommendation rules:
- show timestamp
- show source app
- show stale/cached status
- show confidence if available
- avoid urgent language when stale
- require refresh for live decision

Never present stale advice as current truth.

## Local Deterministic Rules

Only simple deterministic safety helpers are allowed locally.

Allowed:
- duplicate tap prevention
- required-field validation
- number format validation
- idempotency key generation
- local reminder timeout
- local notification display
- cached prayer time display
- queue retry backoff
- media file size validation
- offline banner display

Not allowed:
- strategic decision making
- financial pressure final scoring
- mission priority reshuffle
- VTC repositioning authority
- automatic religious inference
- AI model routing
- long-term memory creation

## Emergency Manual Mode

If the backend is unavailable for an extended time, apps may offer manual mode.

Manual mode may include:
- manual expense logging only
- manual VTC notes only
- manual mission notes only
- manual food stock notes only
- manual workout notes only
- local audio capture only
- cached state view only

Manual mode must not simulate backend intelligence.

It must show:

```text
Manual offline mode.
Changes are pending until backend sync.
```

Manual mode must not:
- close the day officially
- finalize missions
- finalize transactions
- finalize sadaqa obligations
- generate live VTC strategy authority
- silently rewrite priorities

## Sync Model

Offline sync uses a local queue.

### `local_pending_events`

Required fields:
- `local_event_id`
- `event_type`
- `schema_version`
- `source_app`
- `device_id`
- `user_id`
- `idempotency_key`
- `correlation_id`
- `causation_id`
- `privacy_level`
- `payload_json`
- `created_at`
- `last_attempted_at`
- `attempt_count`
- `sync_status`
- `backend_event_id`
- `backend_response_json`
- `failed_sync_reason`
- `conflict_reason`

### `sync_status`

Canonical statuses:
- `draft`
- `pending`
- `syncing`
- `synced`
- `failed`
- `conflict`
- `cancelled`

### `last_known_state_cache`

Purpose:
- Stores cached state for display only.

Expected fields:
- `cache_key`
- `source_app`
- `data_json`
- `fetched_at`
- `expires_at`
- `is_stale`
- `backend_version`
- `privacy_level`

### `failed_sync_reasons`

Purpose:
- Stores visible reasons for failed sync.

Expected fields:
- `id`
- `local_event_id`
- `reason_code`
- `reason_message`
- `backend_response_code`
- `created_at`
- `resolved_at`

## Retry Policy

Retry rules:
- retry network failures with backoff
- do not retry validation failures automatically forever
- preserve idempotency key across retries
- do not create a new event for every retry
- stop retrying if backend returns permanent rejection
- show failed/conflict status to user

Recommended retry cadence:
- immediate retry when network returns
- then exponential backoff
- cap retries per event type
- allow manual retry

Duplicate prevention:
- local duplicate tap prevention
- stable idempotency key
- backend idempotency enforcement
- backend returns original result for duplicate accepted action

## Privacy Offline

Sensitive data stored temporarily on device must be:
- encrypted if possible
- minimized
- deletable
- scoped by retention
- excluded from unnecessary logs
- cleared after successful sync when no longer needed

Especially sensitive:
- finance
- audio
- religious data
- health notes
- media files
- access tokens
- refresh tokens
- device secrets

Rules:
- do not store secrets in plaintext
- do not keep raw audio forever
- do not keep raw screenshots forever
- do not keep private worship notes in stale caches without clear purpose
- allow manual deletion where safe
- follow raw media retention policy

## Relationship With Notifications

Local notifications may exist for:
- reminders
- prayer alerts
- mission reminders
- retry alerts
- sync failure alerts
- planned local timers

Notifications must not imply backend validation if none exists.

Examples:
- `Reminder: review expense draft` is allowed
- `Expense saved` is not allowed until backend confirms
- `Mission completed` is not allowed until backend confirms
- `Pending mission completion` is allowed

## Relationship With Imperium

Only backend may officially close:
- day
- mission
- weekly review

The app may request closure offline.

The closure remains pending until backend confirms.

Imperium app may display:
- pending finish day request
- pending mission completion
- pending failure reason
- last known current mission

Imperium app must not:
- create final current mission locally
- finalize the day locally
- finalize weekly review locally
- silently replace the active mission offline

## Relationship With The Vault

The Vault app may collect financial declarations offline.

But backend validates:
- duplicate transaction checks
- wallet assignment
- accounting consistency
- weekly summaries
- pressure score
- sadaqa basis

Offline financial display must distinguish:
- confirmed balance
- pending changes
- projected balance if useful

Projected values are not canonical truth.

## Relationship With Vector

Vector offline behavior:
- start local pending session request
- collect manual revenue draft
- collect manual expense draft
- collect last drop zone draft
- show cached recommendation
- queue screenshot upload

Vector offline must not:
- present stale recommendation as live
- finalize session result
- update Vault truth
- generate authoritative VTC strategy
- simulate backend recommendation engine

## Relationship With The Path

The Path may record explicit user worship actions offline as pending.

The Path must not infer:
- prayer completion
- fasting intention
- ghusl state
- Quran completion
- adhkar completion
- sadaqa completion

If offline, the app may show:

```text
Prayer log pending sync.
```

It must not silently merge conflicting logs.

## Non-Negotiable Rule

Never let offline mode create a second brain.

Apps are terminals.

Backend is command authority.

Offline support exists to preserve user input and continuity, not to create alternate truth.

## Examples

### Offline Expense Declaration

User enters fuel expense offline.

Local app:
- creates `local_pending_events`
- event type: `transaction.created`
- status: `pending`
- idempotency key: `fuel_2026-04-25_1642_device_pixel`
- shows `Pending sync`

When network returns:
- backend validates
- checks duplicate
- stores event
- creates transaction
- returns result

If duplicate:
- backend rejects or returns original result
- app shows conflict or synced duplicate result

### Offline Voice Note

User records:

```text
Add fuel expense 45 euros.
```

Local app:
- stores audio temporarily
- queues upload
- shows `Voice note pending upload`

Backend later:
- transcribes
- routes AI if needed
- validates transaction action
- asks confirmation if confidence is low
- stores canonical result

The app must not locally create the final transaction from the audio.

### Cached Vector Recommendation

At 14:20 backend returned:

```text
Return toward Paris.
```

At 15:10 user is offline.

Vector may show:

```text
Cached recommendation, not live.
Generated at 14:20:
Return toward Paris.
```

Vector must not show a live instruction unless backend has refreshed it.

### Duplicate Sync Retry

User taps `Objective reached` twice offline.

Local app:
- prevents duplicate tap where possible
- uses the same idempotency key for retry
- queues one action

If two requests still reach backend:
- backend returns original result for duplicate idempotency key
- app shows one synced completion

### Backend Conflict Resolution

User completes a mission offline.

Meanwhile backend already replaced the mission after a different confirmed event.

On sync:
- backend rejects completion for stale mission
- app marks item as `conflict`
- user sees the reason
- no silent overwrite occurs

User-facing message:

```text
Mission completion was not applied.
The active mission changed while this device was offline.
Review the current mission before retrying.
```

## Open Decisions

The following are TODO:
- exact Android encrypted storage library
- exact local database technology
- exact max offline retention for pending events
- exact retry cap per event type
- exact cache expiration policy per app
- exact local notification wording
- exact sync conflict UI
- exact local media cleanup schedule
