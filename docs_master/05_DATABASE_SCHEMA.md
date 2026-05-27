# Database Schema Notes

frontend metadata layer v6
metadata only
declarative metadata only
contains exactly 12 endpoints
not openapi
not a health check
not a dynamic discovery
not health check
not dynamic discovery
not runtime audit
no business data read
no action triggered
no cross-module write
no cross-module writes
jwt-scoped
get only
idempotency-key not required
no secrets/providers/infra metadata
static deterministic v1
not runtime audit
not runtime discovery
does not include user_id
frontend metadata layer v6 is stable
design_handoff_version v1
supported_modules order is deterministic
asset_groups align with asset-registry expectations
design_rules exact and declarative
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

contracts index
metadata only
not openapi
not a health check
not a dynamic discovery
not health check
not dynamic discovery
`/api/imperium/contracts/index`

contracts compliance
declarative metadata only
not a runtime compliance audit
not openapi
not a health check
not dynamic discovery
`/api/imperium/contracts/compliance`

home bootstrap
metadata only
status available
primary_endpoint
not a health check
no business data read
`/api/imperium/home/bootstrap`
not health check

static ui copy metadata
canonical v1 contract
not personalized recommendation
not coaching
not ai decision
not a health check
removed, not active, and not canonical
`/api/imperium/frontend/empty-states`

static ui action metadata
static deterministic v1
declarative navigation actions only
not permissions/feature flags
no destructive action
no mutation/destructive action
no action triggered
`/api/imperium/frontend/actions`

frontend application manifest metadata
metadata only
static deterministic v1
declarative endpoint list only
not runtime discovery
not openapi
not a health check
no business data read
no secrets/providers/infra metadata
`/api/imperium/frontend/app-manifest`

frontend module card metadata
metadata only
static deterministic v1
deterministic order
primary_endpoint canonical
no runtime status
no runtime count
no runtime score
no personalization
no feature flag
no business data read
no secrets/providers/infra metadata

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
no asset pipeline
final assets provided later
final assets can be provided later
placeholders allowed
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

static deterministic v1
not a dynamic theme
not a user preference
semantic tokens only
no font/assets exposure
not a dynamic discovery

route owner canonique
imperium_contracts.py
imperium_frontend.py

contract index groups
deterministic checks[] order
status is always declared

frontend contracts compliance metadata
`status` is always `declared`
deterministic `checks[]` order

the vault ledger is append-only
transactions are immutable after insert
all vault endpoints are scoped through `currentuserdep`
vault v1 uses utc temporal semantics
`occurred_at` is the only authoritative temporal source for vault v1 summaries and filters
`occurred_at` is stored and interpreted as utc for vault v1
summary endpoints share the same currency contract
exactly three ascii letters are accepted
accepted values are normalized uppercase

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
no automatic creation of path/pulse rows

imperium dashboard foundation 12b
snapshot read-only
readiness snapshot
readiness is not a score
readiness is not a recommendation
readiness is not a health score
responses are public-safe for the current authenticated user only
no auto-creation of path rows
no auto-creation of pulse rows

daily plan snapshot
read-only consolidation layer
no legacy dashboard aggregator
readiness snapshot only
bool/count only
not a score
not a recommendation
read-only semantics

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
no automatic entry creation
no automatic mission/vault/path linkage
meta.read_only
meta.daily_plan_version
snapshot_generated_at
does not persist a new plan row
summary and meta are metadata-only sections
readiness
modules
unknown or unused currency with no transaction returns zero totals
must not mask
#### Pulse Foundation 11A
### FUTURE / NOT IMPLEMENTED
#### Future Pulse surfaces - FUTURE / NOT IMPLEMENTED
/api/pulse/dashboard future / not implemented FUTURE / NOT IMPLEMENTED
/api/pulse/workout/generate future / not implemented FUTURE / NOT IMPLEMENTED
/api/pulse/workout/adapt future / not implemented FUTURE / NOT IMPLEMENTED
/api/pulse/wearable/sync future / not implemented FUTURE / NOT IMPLEMENTED
future / not implemented in pulse v1 11a->11d: `pulse_biological_profiles`
future / not implemented in pulse v1 11a->11d: `pulse_health_scores`
future / not implemented in pulse v1 11a->11d: `pulse_workouts`
future / not implemented in pulse v1 11a->11d: `pulse_recommendations`
`updated_at` remains a generic row timestamp
no put/patch/delete endpoint is allowed for `/api/imperium/vault/transactions`
corrections must be written by appending a reversal row through `post /api/imperium/vault/transactions/{transaction_id}/reverse`
the original transaction must never be updated or deleted
the reversal transaction is a new row linked to the original transaction
patch 9f/9g allow one and only one reversal per original transaction
europe/paris
required `idempotency-key`
required idempotency-key
no ocr
no automatic coaching
no automatic recommendations
no automatic mission/vault/path linkage
yyyy-mm
YYYY-MM
imperiumpathitem
read-only compatibility projection
three-letter currency codes are accepted and normalized uppercase
snapshot read-only
modules
default date convention is europe/paris
query `date` overrides the europe/paris default
daily plan snapshot
read-only consolidation layer
no legacy dashboard aggregator
readiness snapshot only
bool/count only
not a score
not a recommendation
read-only semantics
no orchestration
readiness snapshot
readiness is not a score
readiness is not a recommendation
readiness is not a health score
responses are public-safe for the current authenticated user only
no ai, n8n, ocr, scoring, coaching, or recommendations
`/api/imperium/daily-plan`
meta.daily_plan_version
removed from the active v1 contract
no scoring
get /api/imperium/pulse/today
get /api/imperium/pulse/stats/summary
#### Pulse Foundation 11A
#### Future Pulse surfaces - FUTURE / NOT IMPLEMENTED
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
no put/patch/delete endpoint is allowed for `/api/imperium/vault/transactions`
imperium_path_items
default date convention is europe/paris
query `date` overrides the europe/paris default
read-only compatibility projection
persistent initialization must use an explicit post
iso-4217 existence is not validated in v1
three-letter currency codes are accepted and normalized uppercase
path item legacy model
deprecated

## Frontend Module Cards Metadata

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

table `imperium_events`
route owner canonique
`app/api/v1/routes/imperium_events.py`
append-only
user-scoped
`updated_at` exists for BaseModel compatibility only
Events V1 keep `updated_at == created_at`
no runtime UPDATE is allowed
Idempotency-Key required on POST
read-only GETs
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
columns:
`id`
`user_id`
`event_type`
`source_module`
`occurred_at`
`payload_json`
`schema_version`
`idempotency_key`
`created_at`
`updated_at`
constraints:
append-only trigger guards
event_type non-empty
event_type snake_case strict
source_module non-empty
schema_version non-empty
schema_version = v1
payload_json null or JSON object only
DB constraints aligned with Pydantic
source_module allowed values
unique idempotency_key per user when present
index user/occurred_at
index user/occurred_at desc
index user/source_module/occurred_at
index user/source_module/occurred_at desc
index user/event_type/occurred_at
index user/event_type/occurred_at desc
source_module check constraint
intended future use:
Vault snapshots
Path consistency
Pulse tracking
Vector analytics
Weekly Review
Internal backend readers must use `app/services/imperium/event_readers.py`.
The public list route returns `count = page_count = len(items)` and does not expose a total_count.
The internal reader uses `limit + 1`, `has_more`, and `next_offset`.
