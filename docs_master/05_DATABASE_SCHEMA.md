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

