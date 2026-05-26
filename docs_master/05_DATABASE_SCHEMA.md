# Database Schema Notes

frontend metadata layer v3
metadata only
declarative metadata only
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
`/api/imperium/home/bootstrap`
`/api/imperium/contracts/index`
`/api/imperium/contracts/compliance`
`/api/imperium/frontend/navigation`
`/api/imperium/frontend/layout`
`/api/imperium/frontend/theme-tokens`
`/api/imperium/frontend/empty-states`
`/api/imperium/frontend/actions`

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
