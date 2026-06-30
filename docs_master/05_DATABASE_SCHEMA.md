# 05 - Database Schema

Statut : dictionnaire de schema central unique (decision D1, 2026-06-30).

Ce document est la source centrale pour les tables PostgreSQL. Les docs metier
decrivent la logique et renvoient ici pour les colonnes, types, contraintes,
cles et index. Les applications sont des facades ; les noms de tables suivent le
domaine de donnees, jamais le nom d'application. Le socle technique reste nu
sans prefixe.

Regle de lecture pour cette section SOCLE :
- `Schema reel` = etat code aujourd'hui, lu dans les migrations Alembic et les
  modeles SQLAlchemy.
- `Nom cible` = nom documente selon la convention D1. Il ne renomme pas le code.
- Toute divergence migration/ORM visible est signalee. Aucune migration ni aucun
  modele n'est modifie par ce document.

## SOCLE / TECHNIQUE

Tables techniques sans prefixe :
`users`, `devices`, `refresh_tokens`, `auth_events`, `idempotency_keys`,
`events`, `ai_tasks`, `ai_results`, `ai_result_validations`, `ai_memories`.

Extensions installees par la migration initiale : `pgcrypto`, `vector`.
Enums PostgreSQL du socle existant : `source_app`, `privacy_level`,
`device_status`, `idempotency_status`.

### users

Nom actuel : `users`
Nom cible : `users` (conforme, socle technique nu)
Source code : migration `20260425_0001_initial_skeleton.py`, modele
`backend/app/models/auth.py::User`

Schema reel :

```text
id                   UUID PRIMARY KEY
email                TEXT NULL UNIQUE
password_hash        TEXT NULL
master_secret_hash   TEXT NULL
timezone             TEXT NOT NULL DEFAULT 'Europe/Paris'
locale               TEXT NULL
single_user_mode     BOOLEAN NOT NULL DEFAULT true
external_ai_enabled  BOOLEAN NOT NULL DEFAULT false
created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `users.id`
- Unique : `users_email_unique` sur `email`
- Index unique partiel : `users_single_user_singleton_idx` sur
  `single_user_mode` WHERE `single_user_mode IS TRUE`

Notes migration/ORM :
- La migration porte les defaults serveur pour `timezone`, `single_user_mode` et
  `external_ai_enabled`; le modele ORM porte des defaults Python equivalents.
- La migration ne met pas de default serveur sur `id`; le mixin ORM genere un
  UUID cote Python.

### devices

Nom actuel : `devices`
Nom cible : `devices` (conforme, socle technique nu)
Source code : migration `20260425_0001_initial_skeleton.py`, modele
`backend/app/models/auth.py::Device`

Schema reel :

```text
id                  UUID PRIMARY KEY
user_id             UUID NOT NULL FK users.id
device_label        TEXT NOT NULL
device_fingerprint  TEXT NULL
platform            TEXT NULL
status              device_status NOT NULL DEFAULT 'trusted'
trusted_at          TIMESTAMPTZ NOT NULL DEFAULT now()
revoked_at          TIMESTAMPTZ NULL
created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `devices.id`
- FK : `devices.user_id -> users.id`
- Enum `device_status` : `trusted`, `revoked`
- Index : `devices_user_status_idx` sur `(user_id, status)`

Notes migration/ORM :
- La migration ne met pas de default serveur sur `id`; le mixin ORM genere un
  UUID cote Python.
- Divergence : l'index `devices_user_status_idx` est present en migration mais
  absent du `__table_args__` du modele ORM.
- La migration porte un default serveur `trusted_at = now()`; le modele ORM ne
  declare pas de default pour `trusted_at`.
- `status` a un default serveur en migration et un default Python equivalent en
  ORM.

### refresh_tokens

Nom actuel : `refresh_tokens`
Nom cible : `refresh_tokens` (conforme, socle technique nu)
Source code : migrations `20260425_0001_initial_skeleton.py` et
`20260426_0002_security_hardening.py`, modele
`backend/app/models/auth.py::RefreshToken`

Schema reel :

```text
id                    UUID PRIMARY KEY
user_id               UUID NOT NULL FK users.id
device_id             UUID NOT NULL FK devices.id
token_selector        TEXT NOT NULL
token_secret_hash     TEXT NOT NULL
token_hash            TEXT NULL UNIQUE
issued_at             TIMESTAMPTZ NOT NULL DEFAULT now()
expires_at            TIMESTAMPTZ NOT NULL
revoked_at            TIMESTAMPTZ NULL
replaced_by_token_id  UUID NULL FK refresh_tokens.id
created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `refresh_tokens.id`
- FK : `refresh_tokens.user_id -> users.id`
- FK : `refresh_tokens.device_id -> devices.id`
- FK : `refresh_tokens.replaced_by_token_id -> refresh_tokens.id`
- Unique : `refresh_tokens_token_hash_unique` sur `token_hash`
- Index : `refresh_tokens_user_device_idx` sur `(user_id, device_id)`
- Index : `refresh_tokens_expires_at_idx` sur `expires_at`
- Index unique : `refresh_tokens_selector_idx` sur `token_selector`

Notes migration/ORM :
- La migration ne met pas de default serveur sur `id`; le mixin ORM genere un
  UUID cote Python.
- La table a ete durcie par `20260426_0002` : `token_selector` et
  `token_secret_hash` sont devenus obligatoires, `token_hash` est devenu nullable.
- La migration garde la contrainte unique historique
  `refresh_tokens_token_hash_unique`; le modele ORM exprime `token_hash` avec
  `unique=True` mais le nom de contrainte vient de la migration.
- La migration porte des defaults serveur pour `issued_at` et `created_at`; le
  modele ORM ne declare pas de default pour ces deux champs.

### auth_events

Nom actuel : `auth_events`
Nom cible : `auth_events` (conforme, socle technique nu)
Source code : migrations `20260425_0001_initial_skeleton.py`,
`20260426_0002_security_hardening.py`, `20260426_0003_append_only_truncate_guards.py`,
modele `backend/app/models/auth.py::AuthEvent`

Schema reel :

```text
id          UUID PRIMARY KEY
user_id     UUID NULL FK users.id
device_id   UUID NULL FK devices.id
event_type  TEXT NOT NULL
success     BOOLEAN NOT NULL
ip_address  TEXT NULL
user_agent  TEXT NULL
reason      TEXT NULL
created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes, index et triggers :
- PK : `auth_events.id`
- FK : `auth_events.user_id -> users.id`
- FK : `auth_events.device_id -> devices.id`
- Index : `auth_events_user_created_idx` sur `(user_id, created_at)`
- Index : `auth_events_device_created_idx` sur `(device_id, created_at)`
- Index : `auth_events_event_type_created_idx` sur `(event_type, created_at)`
- Trigger append-only : `auth_events_append_only_guard` interdit UPDATE/DELETE
- Trigger append-only : `auth_events_append_only_truncate_guard` interdit TRUNCATE

Notes migration/ORM :
- La migration ne met pas de default serveur sur `id`; le mixin ORM genere un
  UUID cote Python.
- La migration porte un default serveur `created_at = now()`; le modele ORM ne
  declare pas de default pour `created_at`.
- Table append-only saine et conforme au role journal technique.

### idempotency_keys

Nom actuel : `idempotency_keys`
Nom cible : `idempotency_keys` (conforme, socle technique nu)
Source code : migration `20260425_0001_initial_skeleton.py`, modele
`backend/app/models/idempotency.py::IdempotencyKey`

Schema reel :

```text
id                    UUID PRIMARY KEY
user_id               UUID NOT NULL FK users.id
idempotency_key       TEXT NOT NULL
request_method        TEXT NOT NULL
request_path          TEXT NOT NULL
request_hash          TEXT NULL
status                idempotency_status NOT NULL DEFAULT 'processing'
response_status_code  INTEGER NULL
response_body         JSONB NULL
locked_until          TIMESTAMPTZ NULL
created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `idempotency_keys.id`
- FK : `idempotency_keys.user_id -> users.id`
- Enum `idempotency_status` : `processing`, `completed`, `failed`
- Unique : `idempotency_keys_user_key_unique` sur `(user_id, idempotency_key)`
- Index : `idempotency_keys_user_created_idx` sur `(user_id, created_at)`

Notes migration/ORM :
- `status` a un default serveur en migration et un default Python equivalent en
  ORM.
- La migration ne met pas de default serveur sur `id`; le mixin ORM genere un
  UUID cote Python.

### events

Nom actuel : `events`
Nom cible : `events` (conforme, socle technique nu)
Source code : migrations `20260425_0001_initial_skeleton.py`,
`20260426_0002_security_hardening.py`, `20260426_0003_append_only_truncate_guards.py`,
`20260430_0011_events_user_scoped_event_id.py`, modele
`backend/app/models/event.py::Event`

Schema reel :

```text
id                     UUID PRIMARY KEY
event_id               TEXT NOT NULL
event_type             TEXT NOT NULL
schema_version         TEXT NOT NULL
occurred_at            TIMESTAMPTZ NOT NULL
received_at            TIMESTAMPTZ NOT NULL DEFAULT now()
source_app             source_app NOT NULL
device_id              UUID NULL FK devices.id
user_id                UUID NOT NULL FK users.id
idempotency_key        TEXT NOT NULL
correlation_id         TEXT NOT NULL
causation_id           TEXT NULL
privacy_level          privacy_level NOT NULL
payload                JSONB NOT NULL
duplicate_of_event_id  TEXT NULL
created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes, index et triggers :
- PK : `events.id`
- FK : `events.user_id -> users.id`
- FK : `events.device_id -> devices.id`
- Enum `source_app` : `imperium`, `vector`, `vault`, `pulse`, `path`, `core`,
  `external`, `n8n`, `ai_router`
- Enum `privacy_level` : `low`, `medium`, `high`, `very_high`
- Unique : `events_user_event_id_unique` sur `(user_id, event_id)`
- Unique : `events_user_idempotency_unique` sur `(user_id, idempotency_key)`
- Index : `events_user_event_type_occurred_idx` sur
  `(user_id, event_type, occurred_at)`
- Index : `events_user_correlation_idx` sur `(user_id, correlation_id)`
- Index : `events_causation_id_idx` sur `causation_id`
- Trigger append-only : `events_append_only_guard` interdit UPDATE/DELETE
- Trigger append-only : `events_append_only_truncate_guard` interdit TRUNCATE

Notes migration/ORM :
- La migration ne met pas de default serveur sur `id`; le mixin ORM genere un
  UUID cote Python.
- La migration initiale creait `events_event_id_unique` sur `event_id`; la
  migration `20260430_0011` l'a remplace par l'unique courant
  `(user_id, event_id)`.
- La colonne `source_app` reste l'enum code actuel. La convention D3 vise les
  domaines generiques pour les nouveaux catalogues d'events, mais aucun renommage
  de colonne ou d'enum n'est fait ici.
- Le modele ORM et les migrations sont alignes sur les colonnes, contraintes et
  index du schema courant.

### ai_tasks

Nom actuel : `ai_tasks`
Nom cible : `ai_tasks` (conforme, socle technique nu)
Source code : migrations `20260430_0012_ai_tasks_results_foundation.py` et
`20260503_0018_ai_user_id_not_null.py`, modele
`backend/app/models/ai.py::AITask`

Schema reel :

```text
id                UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_id           UUID NOT NULL FK users.id
task_type         TEXT NOT NULL
status            TEXT NOT NULL DEFAULT 'queued'
source_module     TEXT NOT NULL
input_payload     JSONB NOT NULL
prepared_payload  JSONB NULL
router_decision   JSONB NULL
model_hint        TEXT NULL
privacy_level     TEXT NULL
idempotency_key   TEXT NULL
created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
started_at        TIMESTAMPTZ NULL
completed_at      TIMESTAMPTZ NULL
failed_at         TIMESTAMPTZ NULL
error_code        TEXT NULL
error_message     TEXT NULL
```

Contraintes et index :
- PK : `ai_tasks.id`
- FK : `ai_tasks.user_id -> users.id`
- Check `ai_tasks_status_check` :
  `queued`, `running`, `result_received`, `validated`, `rejected`, `failed`,
  `cancelled`
- Check `ai_tasks_source_module_check` :
  `imperium`, `vector`, `vault`, `pulse`, `path`, `system`
- Index : `ai_tasks_user_status_idx` sur `(user_id, status)`
- Index : `ai_tasks_user_task_type_idx` sur `(user_id, task_type)`
- Index : `ai_tasks_user_source_module_idx` sur `(user_id, source_module)`
- Index : `ai_tasks_created_at_idx` sur `created_at`
- Index unique partiel : `ai_tasks_user_idempotency_unique_idx` sur
  `(user_id, idempotency_key)` WHERE `idempotency_key IS NOT NULL`

Notes migration/ORM :
- `user_id` a ete cree nullable en `20260430_0012` puis rendu NOT NULL par
  `20260503_0018`; le schema courant est NOT NULL.
- Divergence mineure : la migration donne a `id` un default serveur
  `gen_random_uuid()`, tandis que le mixin ORM genere aussi un UUID cote Python.

### ai_results

Nom actuel : `ai_results`
Nom cible : `ai_results` (conforme, socle technique nu)
Source code : migrations `20260430_0012_ai_tasks_results_foundation.py` et
`20260503_0018_ai_user_id_not_null.py`, modele
`backend/app/models/ai.py::AIResult`

Schema reel :

```text
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
task_id          UUID NOT NULL FK ai_tasks.id ON DELETE CASCADE
user_id          UUID NOT NULL FK users.id
result_type      TEXT NOT NULL
status           TEXT NOT NULL DEFAULT 'pending_validation'
result_payload   JSONB NOT NULL
raw_payload      JSONB NULL
model_used       TEXT NULL
provider         TEXT NULL
confidence       NUMERIC(5,4) NULL
idempotency_key  TEXT NULL
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `ai_results.id`
- FK : `ai_results.task_id -> ai_tasks.id ON DELETE CASCADE`
- FK : `ai_results.user_id -> users.id`
- Check `ai_results_status_check` :
  `received`, `pending_validation`, `accepted`, `rejected`, `superseded`
- Check `ai_results_confidence_range` :
  `confidence IS NULL OR (confidence >= 0 AND confidence <= 1)`
- Unique : `ai_results_task_idempotency_unique` sur `(task_id, idempotency_key)`
- Index : `ai_results_task_id_idx` sur `task_id`
- Index : `ai_results_status_idx` sur `status`
- Index : `ai_results_created_at_idx` sur `created_at`

Notes migration/ORM :
- `user_id` a ete cree nullable en `20260430_0012` puis rendu NOT NULL par
  `20260503_0018`; le schema courant est NOT NULL.
- L'unique `(task_id, idempotency_key)` suit la semantique PostgreSQL des NULL :
  plusieurs lignes avec `idempotency_key IS NULL` ne sont pas dedoublonnees.
- Divergence mineure : la migration donne a `id` un default serveur
  `gen_random_uuid()`, tandis que le mixin ORM genere aussi un UUID cote Python.

### ai_result_validations

Nom actuel : `ai_result_validations`
Nom cible : `ai_result_validations` (conforme, socle technique nu)
Source code : migrations `20260430_0012_ai_tasks_results_foundation.py` et
`20260503_0018_ai_user_id_not_null.py`, modele
`backend/app/models/ai.py::AIResultValidation`

Schema reel :

```text
id                 UUID PRIMARY KEY DEFAULT gen_random_uuid()
result_id          UUID NOT NULL FK ai_results.id ON DELETE CASCADE
task_id            UUID NOT NULL FK ai_tasks.id ON DELETE CASCADE
user_id            UUID NOT NULL FK users.id
validation_status  TEXT NOT NULL
validated_payload  JSONB NULL
user_note          TEXT NULL
created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `ai_result_validations.id`
- FK : `ai_result_validations.result_id -> ai_results.id ON DELETE CASCADE`
- FK : `ai_result_validations.task_id -> ai_tasks.id ON DELETE CASCADE`
- FK : `ai_result_validations.user_id -> users.id`
- Check `ai_result_validations_status_check` :
  `accepted`, `rejected`, `edited`
- Index : `ai_result_validations_result_id_idx` sur `result_id`
- Index : `ai_result_validations_task_id_idx` sur `task_id`
- Index : `ai_result_validations_created_at_idx` sur `created_at`

Notes migration/ORM :
- `user_id` a ete cree nullable en `20260430_0012` puis rendu NOT NULL par
  `20260503_0018`; le schema courant est NOT NULL.
- Divergence mineure : la migration donne a `id` un default serveur
  `gen_random_uuid()`, tandis que le mixin ORM genere aussi un UUID cote Python.

### ai_memories

Nom actuel : `ai_memories`
Nom cible : `ai_memories` (conforme, socle technique nu)

SCHÉMA CIBLE — la table codee actuelle est non conforme, a migrer (cf. decisions
memoire). Ne pas documenter l'existant comme canonique. Politique d'usage :
`09_PGVECTOR_MEMORY_POLICY.md`. Conception : `75_MEMOIRE_VECTORIELLE_UNIFIEE.md`.

Schema cible :

```text
memory_id             UUID PRIMARY KEY
user_id               UUID NOT NULL FK users.id
content               TEXT NOT NULL
embedding             vector(1024) NOT NULL
embedding_model       TEXT NOT NULL
memory_type           memory_type NOT NULL
learning_element_type TEXT NULL
source_domain         source_domain NOT NULL
source_table          TEXT NULL
source_id             TEXT NULL
confidence            NUMERIC NULL
privacy_level         privacy_level NOT NULL
is_active             BOOLEAN NOT NULL DEFAULT true
supersedes_memory_id  UUID NULL FK ai_memories.memory_id
correction_reason     TEXT NULL
expires_at            TIMESTAMPTZ NULL
created_at            TIMESTAMPTZ NOT NULL
updated_at            TIMESTAMPTZ NOT NULL
metadata              JSONB NULL
```

Contraintes et enums cibles :
- PK : `ai_memories.memory_id`
- FK : `ai_memories.user_id -> users.id`
- FK : `ai_memories.supersedes_memory_id -> ai_memories.memory_id`
- `memory_type` : enum de DOMAINE, semi-stable, cf. doc 09.
- `learning_element_type` : axe ouvert de NATURE
  (`insight`, `decision`, `pattern`, `win`, `blocker`, etc.), descriptif
  uniquement.
- `source_domain` : enum de domaines generiques, jamais noms d'apps :
  `finance`, `worship`, `health`, `rides`, `planning`, `decision`, `review`,
  `calendar`, `vehicle`, `system`, etc.
- `privacy_level` : obligatoire sur chaque ligne.
- `confidence` represente la preuve accumulee, pas un decay temporel.

Index cibles :
- HNSW cosine sur `embedding`.
- Index composite sur `(user_id, source_domain, memory_type, is_active)`.
- Index composite sur `(user_id, privacy_level, is_active)`.
- Index composite sur `(source_table, source_id)`.
- Index sur `expires_at`.

Notes cible :
- `content` contient uniquement un element d'apprentissage vectorise, pas la data
  brute.
- `source_table` et `source_id` sont des pointeurs vers la source canonique.
- `is_active`, `supersedes_memory_id` et `correction_reason` gerent la correction
  explicite. La confidence ne baisse pas seule.
- La migration et le modele actuels utilisent notamment `id`, `source_module`,
  `kind`, `scope`, `status`, `visibility` et plusieurs pointeurs Weekly Review :
  cet existant est non conforme a la cible ci-dessus et doit etre migre dans un
  chantier dedie.

## Notes historiques et marqueurs contractuels existants

Les lignes ci-dessous sont conservees temporairement comme marqueurs de contrats
existants. Elles ne remplacent pas le dictionnaire central ci-dessus.

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

## Canonical Domain Vocabulary

Storage and API contracts use English domain values:

```text
religious
business
finance
health
```

French domain names are UI labels only:

```text
Religieux
Business
Finances
Santé
```

Services may accept French aliases at input boundaries for convenience, but
database rows and API responses must normalize to the English canonical values.
This is a vocabulary decision only; it does not require table renames.
