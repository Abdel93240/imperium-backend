# MVP Backend Contracts

route owner canonique
imperium_contracts.py
imperium_frontend.py
imperium_home.py (`/api/imperium/home/bootstrap`)

## Frontend Metadata Layer v6

This layer is metadata only.
Frontend Metadata Layer v6 is considered stable and locked.
Any future frontend metadata surface must be explicitly documented, deterministic, metadata-only, and must not introduce business logic.
This layer is static and deterministic in V1.
It contains exactly 12 endpoints:
`/api/imperium/home/bootstrap`
`/api/imperium/contracts/index`
`/api/imperium/contracts/compliance`
`/api/imperium/frontend/navigation`
`/api/imperium/frontend/layout`
`/api/imperium/frontend/theme-tokens`
`/api/imperium/frontend/empty-states`
`/api/imperium/frontend/actions`
`/api/imperium/frontend/module-cards`
`/api/imperium/frontend/asset-registry`
`/api/imperium/frontend/app-manifest`
`/api/imperium/frontend/design-handoff`
It is not a full OpenAPI document.
It is not a health check.
It is not health check.
It is not a dynamic runtime discovery surface.
It is not runtime audit.
It does not read business data.
It does not trigger actions.
It does not perform cross-module writes.
It is JWT-scoped.
GET only.
Idempotency-Key not required.
It does not use OpenAPI or dynamic discovery.
It does not perform runtime audit.
It does not include user_id, secrets, provider metadata, or infra metadata.
`module-cards` is part of the stable frontend metadata layer and must remain in the canonical endpoint list.
`asset-registry` is part of the stable frontend metadata layer and must remain in the canonical endpoint list.
The canonical frontend metadata surface is:
`/api/imperium/home/bootstrap`
`/api/imperium/contracts/index`
`/api/imperium/contracts/compliance`
`/api/imperium/frontend/navigation`
`/api/imperium/frontend/layout`
`/api/imperium/frontend/theme-tokens`
`/api/imperium/frontend/empty-states`
`/api/imperium/frontend/actions`
`/api/imperium/frontend/module-cards`
`/api/imperium/frontend/asset-registry`
`/api/imperium/frontend/app-manifest`
`/api/imperium/frontend/design-handoff`

### Home Bootstrap

`/api/imperium/home/bootstrap`
home bootstrap
status available
primary_endpoint
metadata only
not a health check
not a dynamic discovery
no business data read
no secrets/providers/infra metadata

### Contracts Index

`/api/imperium/contracts/index`
contract index
frontend contracts compliance metadata
references the frontend metadata group
`status` is always `declared`
deterministic `checks[]` order
not a full openapi
not a health check
not a dynamic runtime discovery
no business data read
no secrets/providers/infra metadata
no duplicate frontend metadata entries
frontend group includes module-cards and asset-registry

### Contracts Compliance

`/api/imperium/contracts/compliance`
frontend contracts compliance metadata
`status` is always `declared`
deterministic `checks[]` order
not a runtime compliance audit
not openapi
not a health check
not dynamic discovery
not runtime audit

### Navigation

`/api/imperium/frontend/navigation`
metadata only
static deterministic v1
currentuserdep
idempotency-key
not a health check
not a dynamic discovery
no business data read
no secrets/providers/infra metadata

### Layout

`/api/imperium/frontend/layout`
metadata only
static deterministic v1
not a health check
not a dynamic discovery
not a dynamic theme
no business data read
no secrets/providers/infra metadata

### Theme Tokens

`/api/imperium/frontend/theme-tokens`
metadata only
static deterministic v1
semantic tokens only
not a dynamic theme
not a user preference
not a health check
not a dynamic discovery
no business data read
no secrets/providers/infra metadata
no font/assets exposure

### Empty States

`/api/imperium/frontend/empty-states`
static ui copy metadata
canonical v1 contract
not personalized recommendation
not coaching
not ai decision
not a health check
no business data read
removed, not active, and not canonical
static copy removed from the active v1 contract

### Actions

`/api/imperium/frontend/actions`
metadata only
static ui action metadata
static deterministic v1
declarative navigation actions only
not a health check
not dynamic discovery
no action triggered
no destructive action
no mutation/destructive action
not permissions/feature flags
no ai, n8n, ocr, scoring, coaching, or recommendations

### App Manifest

`/api/imperium/frontend/app-manifest`
frontend application manifest metadata
metadata only
static deterministic v1
declarative endpoint list only
not runtime discovery
not openapi
not a health check
no business data read
no secrets/providers/infra metadata
lists exactly the 12 frontend metadata endpoints
ordered canonical endpoint list
contains no user_id
contains no provider metadata
contains no infra metadata

### Design Handoff

`/api/imperium/frontend/design-handoff`
frontend design handoff metadata
Claude Code Design handoff only
metadata only
handoff metadata contract
static deterministic v1
frontend metadata layer version v6
read only
GET only
JWT-scoped
Idempotency-Key not required
prepared for Claude Code Design
prepares Claude Code Design handoff
declares design direction metadata
declares supported modules
declares exact frontend metadata endpoints
declares expected asset groups
declares exact design rules
design handoff metadata only
no UI rendering
no asset upload
no upload
no CDN
no runtime discovery
does not generate UI
does not generate images
does not generate React
no generated frontend code
does not perform layout runtime
does not perform dynamic rendering
does not perform filesystem scan
does not perform asset existence check
does not perform OpenAPI scan
does not perform runtime audit
does not read business data
does not trigger actions
does not perform cross-module writes
does not include user_id
does not include secrets/providers/infra metadata
no upload
no remote URL
no CDN
no base64
no font file
no code frontend
no React/HTML/CSS
no screenshots/blobs
no screenshots
no blobs
no Figma
final assets provided later
final assets can be provided later
placeholders allowed
no asset pipeline
stable v6 metadata surface
design_handoff_version v1
supported_modules order is deterministic
asset_groups align with asset-registry expectations
design_rules exact and declarative
asset-registry remains expected assets only
asset-registry is not runtime inventory
asset-registry allows placeholders
asset-registry does not scan filesystem
asset-registry does not check asset existence
asset-registry does not require actual assets yet
asset-registry does not use remote urls
asset-registry does not use base64
asset-registry does not include font files
asset-registry does not include screenshots, blobs, or image payloads

### Module Cards

`/api/imperium/frontend/module-cards`
frontend module card metadata
metadata only
static deterministic v1
deterministic order
primary_endpoint is canonical
no runtime status
no runtime count
no runtime score
no personalization
no feature flag
no business data read
no secrets/providers/infra metadata

### Asset Registry

`/api/imperium/frontend/asset-registry`
frontend asset registry metadata
metadata only
static deterministic v1
placeholder policy
placeholder_allowed true
semantic_luxury_placeholder
asset registry means expected asset contract, not runtime inventory
no filesystem scan
no asset existence check
no upload
no CDN
no remote URLs
no base64
no font files
final PNG/SVG assets may be provided later
designed for Claude Code Design handoff
not a health check
not dynamic discovery
no business data read
no secrets/providers/infra metadata

## Mission Contracts

`/api/imperium/missions/start`
`/api/imperium/missions/backlog`
`/api/imperium/missions/backlog/decision-preview`
`/api/imperium/missions/backlog/{mission_id}/promote`
`/api/imperium/missions/current`
`/api/imperium/missions/active`
`/api/imperium/missions/{mission_id}/complete`
`/api/imperium/missions/{mission_id}/fail`
`/api/imperium/missions/history`
`/api/imperium/missions/recent`
`/api/imperium/missions/{mission_id}`
`/api/imperium/missions/{mission_id}/decision-score`
`mission.abandoned`
| POST |
| GET |
CurrentUserDep
Idempotency-Key
no ai
no n8n
pgvector
embedding
memory
calendar

## Pulse Contracts

`/api/imperium/pulse/today`
read-only
entry: null
no automatic entry creation
no ai/n8n/scoring/coaching/calendar/memory/cross-module linkage
`/api/imperium/pulse/stats/summary`
pulse summary stats 11c
deterministic
no health score
no coaching
no recommendations
no cross-module linkage
no pgvector write
no embeddings
no automatic memory commit
no automatic replanning
no automatic scoring
| POST | `/api/imperium/pulse/entries`
| GET | `/api/imperium/pulse/entries`
| GET | `/api/imperium/pulse/entries/{entry_id}`
| GET | `/api/imperium/pulse/today`
| GET | `/api/imperium/pulse/stats/summary`

## Dashboard Contracts

`/api/imperium/dashboard`
imperium dashboard foundation 12b
active mission
vault summary
path today
pulse today
no `idempotency-key` required
snapshot read-only
not the ai brain
no n8n ai agent
no n8n db write
no automatic memory commit
no automatic path check-in creation
no automatic pulse entry creation
no automatic creation of path/pulse rows
no mission/vault/path/pulse mutation
no cross-module write
no cross-module writes
readiness snapshot
readiness is not a score
readiness is not a recommendation
readiness is not a health score
responses are public-safe for the current authenticated user only
no auto-creation of path rows
no auto-creation of pulse rows
GET /api/imperium/dashboard
query params:
date` optional `date`
currency` optional string
readiness`
safe_explanation

## Vault Contracts

append-only
immutable once inserted
the vault ledger is append-only
transactions are immutable after insert
all vault endpoints are scoped through `currentuserdep`
vault v1 uses utc temporal semantics
`occurred_at` is the only authoritative temporal source for vault v1 summaries and filters
`occurred_at` is stored and interpreted as utc for vault v1
summary endpoints share the same currency contract
exactly three ascii letters are accepted
accepted values are normalized uppercase
none of the vault 9h routes persist ai, n8n, ocr, sadaqa, wallet, balance
transaction_count desc
absolute net magnitude desc
no ai/n8n/ocr/sadaqa/wallet/balance workflows
yyyy-mm
utc `occurred_at` month and the public `yyyy-mm` format
groups by the utc month of `occurred_at` and returns `yyyy-mm`
patch 9d
read-only
grouped by month
`/api/imperium/vault/transactions/{transaction_id}`
non-owned => 404
`/api/imperium/vault/transactions/{transaction_id}/reverse`
Patch 9F
append-only correction endpoint
the original transaction is never updated or deleted
one and only one reversal per original transaction
patch 9g
vault ledger is append-only
transactions are immutable
no put/patch/delete endpoints exist under `/api/imperium/vault/transactions`
post /api/imperium/vault/transactions/{transaction_id}/reverse
original transaction must never be updated or deleted
reversal transaction is a new transaction linked to the original
one reversal per original
forbidden for the append-only ledger
legacy direct edit route
patch 9h
append-only
immutable after insert
the vault ledger is append-only
transactions are immutable after insert
all vault endpoints are scoped through `currentuserdep`
vault v1 uses utc temporal semantics
`occurred_at` is the only authoritative temporal source for vault v1 summaries and filters
`occurred_at` is stored and interpreted as utc for vault v1
summary endpoints share the same currency contract
exactly three ascii letters are accepted
accepted values are normalized uppercase
none of the vault 9h routes persist ai, n8n, ocr, sadaqa, wallet, balance

## Path Contracts

path foundation 10a
`post /api/imperium/path/habits`
`get /api/imperium/path/habits`
`post /api/imperium/path/habits/{habit_id}/check-ins`
`get /api/imperium/path/check-ins`
missed requires reason
no ai/n8n/scoring/calendar in 10a
no pgvector write
no embeddings
no automatic memory commit
no automatic mission/vault linkage
no automatic replanning
no automatic scoring
no automatic check-in creation
get /api/imperium/path/today
path today view 10b
read-only
pending/done/missed
no ai/n8n/scoring/calendar
no automatic check-in creation
get /api/imperium/path/habits/{habit_id}
path habit detail 10d
read-only
404
non-owned
never creates a check-in
get /api/imperium/path/check-ins/{check_in_id}
path check-in detail 10e
read-only
404
non-owned
never modifies any habit or check-in
get /api/imperium/path/stats/summary
path summary stats computed from current user's habits and check-ins.
path summary stats 10f
read-only
deterministic
completion rate
pending implicits are excluded
no ai/n8n/scoring/calendar
no pgvector write
no embeddings
no automatic memory commit
no automatic mission/vault linkage
no automatic check-in creation
no automatic replanning
no automatic scoring

## Daily Plan Contracts

`/api/imperium/daily-plan`
daily plan snapshot
read-only consolidation layer
no legacy dashboard aggregator
readiness snapshot only
bool/count only
not a score
not a recommendation
read-only semantics
imperium dashboard foundation 12b
snapshot read-only
responses are public-safe for the current authenticated user only
no auto-creation of path rows
no auto-creation of pulse rows
readiness is not a score
readiness is not a recommendation
readiness is not a health score
no orchestration
legacy dashboard aggregator
not an external health check

## Coverage Addenda

europe/paris
required `idempotency-key`
required idempotency-key
no ocr
no automatic coaching
no automatic recommendations
no automatic mission/vault/path linkage
yyyy-mm
YYYY-MM
patch 11d
patch 11f
patch 12g
patch 13a
patch 13e
patch 9g
imperiumpathitem
read-only compatibility projection
three-letter currency codes are accepted and normalized uppercase
snapshot read-only
modules
path summary stats 10f
no ai/n8n/scoring/calendar in 10a
no automatic memory commit
no automatic replanning
no automatic scoring
no automatic entry creation
no automatic pulse entry creation
no automatic path check-in creation
no auto-creation of path rows
no auto-creation of pulse rows
default date convention is europe/paris
query `date` overrides the europe/paris default
path foundation 10a
path today view 10b
path habit detail 10d
path check-in detail 10e
path summary stats 10f
daily plan snapshot
read-only consolidation layer
no legacy dashboard aggregator
readiness snapshot only
bool/count only
not a score
not a recommendation
read-only semantics
readiness snapshot
readiness is not a score
readiness is not a recommendation
readiness is not a health score
responses are public-safe for the current authenticated user only
no ai, n8n, ocr, scoring, coaching, or recommendations
meta.daily_plan_version
meta.read_only
removed from the active v1 contract
no scoring
get /api/imperium/pulse/today
get /api/imperium/pulse/stats/summary
snapshot_generated_at
#### Pulse Foundation 11A
Pulse v1 11a->11d active backend surface is only
Pulse v1 11a->11d implemented schema surface is only `imperium_pulse_entries`
#### Future Pulse surfaces - FUTURE / NOT IMPLEMENTED
patch 11f future surfaces
/api/pulse/dashboard future / not implemented FUTURE / NOT IMPLEMENTED
/api/pulse/workout/generate future / not implemented FUTURE / NOT IMPLEMENTED
/api/pulse/workout/adapt future / not implemented FUTURE / NOT IMPLEMENTED
/api/pulse/wearable/sync future / not implemented FUTURE / NOT IMPLEMENTED
future / not implemented in pulse v1 11a->11d: `pulse_biological_profiles`
future / not implemented in pulse v1 11a->11d: `pulse_health_scores`
future / not implemented in pulse v1 11a->11d: `pulse_workouts`
future / not implemented in pulse v1 11a->11d: `pulse_recommendations`
health score table future / not implemented
workout generation future / not implemented
wearable sync tables future / not implemented
no automatic scoring/coaching/recommendations
no automatic pulse entry creation
no automatic coaching
no automatic recommendations
no automatic mission/vault/path linkage
no ai
no n8n
no pgvector write
no embeddings
no automatic memory commit
no automatic replanning
no automatic scoring
not an availability score
no put/patch/delete endpoint is allowed for `/api/imperium/vault/transactions`
imperium_path_items
default date convention is europe/paris
query `date` overrides the europe/paris default
read-only compatibility projection
persistent initialization must use an explicit post
iso-4217 existence is not validated in v1
three-letter currency codes are accepted and normalized uppercase
unknown or unused currency with no transaction returns zero totals
path item legacy model
deprecated
must not mask
*_available means the section was wired and calculated successfully in the snapshot
path foundation 10a
path today view 10b
path habit detail 10d
path check-in detail 10e
path summary stats 10f
missed requires reason
no ai/n8n/scoring/calendar in 10a
no pgvector write
no embeddings
no automatic memory commit
no automatic mission/vault linkage
no automatic replanning
no automatic scoring
no automatic check-in creation
no automatic entry creation
no automatic path check-in creation
no automatic pulse entry creation
no auto-creation of path rows
no auto-creation of pulse rows

### Module Cards

`/api/imperium/frontend/module-cards`
frontend module card metadata
metadata only
static deterministic v1
not a health check
not runtime status
not runtime availability
not module availability runtime
not personalization
not feature flag
no business data read
no secrets/providers/infra metadata

## Event Foundation 23A

`/api/imperium/events`
route owner canonique
`app/api/v1/routes/imperium_events.py`
Event Foundation 23A / 23B / 23C
append-only
user-scoped
`updated_at` exists for BaseModel compatibility only
Events V1 keep `updated_at == created_at`
no runtime UPDATE is allowed
Idempotency-Key required on POST
read-only GETs
DB constraints aligned with Pydantic
event_type snake_case strict
schema_version = v1
payload_json null or JSON object only
strict CurrentUserDep
no user_id exposed
no projections
no cross-module writes
no AI
no n8n
no OCR
no scoring
no coaching
no recommendations
POST creates the current user's event only
GET list returns current-user events only
GET detail returns current-user event only
no PUT/PATCH/DELETE
POST is idempotent
GET list and detail do not require Idempotency-Key
GET /api/imperium/events returns `count = page_count = len(items)`
`count` is not a total_count
future internal consumers should prefer `app/services/imperium/event_readers.py`
the internal reader uses `limit + 1`, `has_more`, and `next_offset`
source_module allowed values:
mission
vault
path
pulse
vector
dashboard
daily_plan
system
manual
intended future use:
Vault snapshots
Path consistency
Pulse tracking
Vector analytics
Weekly Review

## Internal Imperium Events Reader 24D

Internal backend contract only.
This is not a public API contract.
No endpoint is introduced by this reader.
No projection layer is introduced by this reader.
No database write is allowed through this reader.
No cross-module write is allowed through this reader.
No Vault, Vector, Pulse, Path, n8n, Qwen, OCR, AI scoring, coaching, or recommendation integration is part of this contract.

Primary function:
`read_imperium_events(db, EventReadFilters(...)) -> EventReadPage`

Compatibility function:
`list_events_for_user(...)`
delegates to the modern `read_imperium_events` contract and returns only `EventReadPage.items`.

### Canonical Imperium Event Read Path

All future internal consumers MUST use:
`app/services/imperium/event_readers.py`

Direct `ImperiumEvent` reads are forbidden outside approved services:
`app/services/imperium/event_readers.py`
`app/services/imperium/events.py`

Motivation:
deterministic ordering
future consistency
pagination semantics
centralized validation
append-only guarantees

Scope:
`user_id` is mandatory.
Every read must be scoped by `imperium_events.user_id`.
The reader must never return another user's events.

Available filters:
`event_type`
`source_module`
`occurred_from`
`occurred_to`
`limit`
`offset`

Bounds:
`limit` default is 50.
`limit` maximum is 100.
`offset` must be greater than or equal to 0.

Deterministic order:
`occurred_at DESC`
`created_at DESC`
`id DESC`

Pagination:
The internal query reads `limit + 1` rows.
The returned page contains at most `limit` items.
`has_more` is true when the extra row exists.
`next_offset` is `offset + limit` when `has_more` is true.
`next_offset` is null when the page is final.
`count` in the public route is only the returned page size.
It is not a total_count.
Future internal consumers should read imperium_events through `app/services/imperium/event_readers.py`.

Runtime constraints:
read-only
internal backend use only
no endpoint
no projection
no migration
no model change
no write DB
no public route exposure
no module orchestration side effects
