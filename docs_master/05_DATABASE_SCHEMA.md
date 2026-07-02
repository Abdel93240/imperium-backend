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

## FINANCE

Tables finance :
`imperium_vault_transactions` (canonique actuel, nom cible
`finance_transactions`) et `vault_transactions` (legacy deprecie).

Regle de lecture pour cette section :
- Le ledger canonique fonctionnel est `imperium_vault_transactions`.
- Le nom cible documentaire est `finance_transactions`, conforme a la convention
  D1 : prefixe de domaine, pas nom d'application.
- Ce document ne renomme aucune table dans le code.

### finance_transactions

Nom actuel : `imperium_vault_transactions`
Nom cible : `finance_transactions`
Source code : migrations `20260525_0024_imperium_vault_ledger_foundation.py`,
`20260525_0025_imperium_vault_transaction_reversals.py`,
`20260525_0026_imperium_vault_local_date_timezone.py`, modele
`backend/app/models/vault.py::ImperiumVaultTransaction`

Role : ledger finance canonique. Montants en cents, append-only, corrections par
reversal.

Schema reel :

```text
id                          UUID PRIMARY KEY
user_id                     UUID NOT NULL FK users.id
transaction_type            TEXT NOT NULL
amount_cents                INTEGER NOT NULL
currency                    TEXT NOT NULL DEFAULT 'EUR'
occurred_at                 TIMESTAMPTZ NOT NULL
local_date                  DATE NOT NULL
timezone                    TEXT NOT NULL
category                    TEXT NULL
source                      TEXT NULL
note                        TEXT NULL
external_ref                TEXT NULL
is_reversal                 BOOLEAN NOT NULL DEFAULT false
reversal_of_transaction_id  UUID NULL FK imperium_vault_transactions.id
reversal_reason             VARCHAR(500) NULL
created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `imperium_vault_transactions.id`
- FK : `imperium_vault_transactions.user_id -> users.id`
- FK :
  `imperium_vault_transactions.reversal_of_transaction_id -> imperium_vault_transactions.id`
- Check `imperium_vault_transactions_transaction_type_check` :
  `transaction_type IN ('income', 'expense')`
- Check `imperium_vault_transactions_amount_positive` :
  `amount_cents > 0`
- Check `imperium_vault_transactions_currency_length_check` :
  `length(currency) = 3`
- Check `imperium_vault_transactions_reversal_link_check` :
  `is_reversal = true` impose `reversal_of_transaction_id IS NOT NULL` ;
  `is_reversal = false` impose `reversal_of_transaction_id IS NULL`
- Index :
  `imperium_vault_transactions_user_occurred_at_idx` sur
  `(user_id, occurred_at DESC)`
- Index :
  `imperium_vault_transactions_user_local_date_idx` sur
  `(user_id, local_date DESC)`
- Index :
  `imperium_vault_transactions_user_transaction_type_idx` sur
  `(user_id, transaction_type)`
- Index :
  `imperium_vault_transactions_user_reversal_of_idx` sur
  `(user_id, reversal_of_transaction_id)`
- Index unique partiel :
  `imperium_vault_transactions_one_reversal_per_original_idx` sur
  `reversal_of_transaction_id` WHERE `is_reversal = true`

Regles metier du ledger canonique :
- Ledger append-only : une transaction est immutable apres insertion.
- Aucune correction par UPDATE ou DELETE. Les corrections s'ecrivent par ajout
  d'une ligne de reversal via
  `POST /api/imperium/vault/transactions/{transaction_id}/reverse`.
- Une reversal est une nouvelle transaction liee a l'originale par
  `reversal_of_transaction_id`.
- Une transaction originale ne peut avoir qu'une seule reversal. Cette regle est
  portee par le service et par l'index unique partiel ajoute en patch 9f/9g.
- Une ligne de reversal ne peut pas etre reversee a son tour.
- `occurred_at` est la seule source temporelle autoritative pour les summaries,
  filtres et regroupements finance V1. La semantique temporelle de V1 est UTC.
- `local_date` et `timezone` servent de convention de date utilisateur. La
  convention par defaut produit attendue est `Europe/Paris`; une date fournie en
  query/payload peut surcharger cette convention selon le contrat d'endpoint.
- `currency` accepte exactement 3 lettres ASCII et est normalisee en majuscule
  par les schemas API. V1 ne valide pas l'existence ISO-4217 de la devise.
- Les endpoints de creation et de reversal exigent `Idempotency-Key`.
- Les endpoints finance sont scopes par l'utilisateur courant.
- Les endpoints de summary partagent le meme contrat de devise. Une devise
  inconnue ou inutilisee sans transaction retourne des totaux a zero, sans
  masquer une erreur de validation.

Notes migration/ORM :
- La migration ne met pas de default serveur sur `id`; le mixin ORM genere un
  UUID cote Python.
- `currency` et `is_reversal` ont des defaults serveur en migration et des
  defaults Python equivalents en ORM.
- `created_at` et `updated_at` ont des defaults serveur en migration ; le modele
  declare aussi `server_default=func.now()`. `updated_at` porte en plus
  `onupdate=func.now()` cote ORM, mais la regle metier interdit de modifier les
  transactions apres insert.
- Divergence de durcissement : les regles append-only sont appliquees par le
  service/API et la doc, mais il n'existe pas encore de trigger DB
  UPDATE/DELETE/TRUNCATE sur `imperium_vault_transactions` dans les migrations
  0024/0025/0026.
- Divergence de nommage : la table codee reste
  `imperium_vault_transactions`; le nom cible documente est
  `finance_transactions`.

Lecteurs et contrats actifs :
- API canonique actuelle :
  `backend/app/api/v1/routes/imperium_vault.py`
- Service d'ecriture/reversal :
  `backend/app/services/imperium/vault_transactions.py`
- Services de lecture/summaries :
  `backend/app/services/imperium/vault.py`

### vault_transactions

Nom actuel : `vault_transactions`
Nom cible : aucun. Table DEPRECIEE, legacy, a supprimer apres migration des
lecteurs restants.
Source code : migration `20260426_0007_vault_transactions.py`, modele
`backend/app/models/vault.py::VaultTransaction`

Role legacy : ancien ledger Vault, remplace par le ledger canonique ci-dessus.
Ne pas creer de nouveau developpement dessus.

Schema reel bref :

```text
id                UUID PRIMARY KEY
user_id           UUID NOT NULL FK users.id
event_id          UUID NULL FK events.id
occurred_at       TIMESTAMPTZ NOT NULL
local_date        DATE NOT NULL
timezone          TEXT NOT NULL
transaction_type  TEXT NOT NULL
wallet            TEXT NOT NULL
category          TEXT NOT NULL
label             TEXT NULL
amount            NUMERIC(12, 2) NOT NULL
currency          TEXT NOT NULL DEFAULT 'EUR'
notes             TEXT NULL
source_app        TEXT NOT NULL DEFAULT 'vault'
created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `vault_transactions.id`
- FK : `vault_transactions.user_id -> users.id`
- FK : `vault_transactions.event_id -> events.id`
- Check `vault_transactions_transaction_type_check` :
  `transaction_type IN ('income', 'expense', 'correction')`
- Check `vault_transactions_wallet_check` :
  `wallet IN ('cash', 'bank')`
- Check `vault_transactions_amount_positive` : `amount > 0`
- Index : `vault_transactions_user_local_date_idx` sur `(user_id, local_date)`
- Index : `vault_transactions_user_occurred_at_idx` sur
  `(user_id, occurred_at DESC)`
- Index : `vault_transactions_user_transaction_type_idx` sur
  `(user_id, transaction_type)`

Notes legacy :
- Cette table utilise `NUMERIC(12, 2)` au lieu de `amount_cents`.
- Elle porte `wallet`, `label`, `notes`, `source_app` et `event_id`, absents du
  ledger canonique actuel.
- Elle autorise `transaction_type = 'correction'`, alors que le canonique
  represente les corrections par reversal append-only.
- Lecteurs a migrer avant suppression :
  `backend/app/services/imperium/dashboard.py` et
  `backend/app/services/imperium/weekly_report.py`.
- Ancien chemin API encore present :
  `backend/app/api/v1/routes/vault.py` avec service
  `backend/app/services/vault/transactions.py`.

## HEALTH

Tables health :
`imperium_pulse_entries` (canonique actuel, nom cible `health_entries`).

Regle de lecture pour cette section :
- La seule table Pulse/Health reellement codee en V1 est
  `imperium_pulse_entries`.
- Le nom cible documentaire est `health_entries`, conforme a la convention D1 :
  prefixe de domaine, pas nom d'application.
- Ce document ne renomme aucune table dans le code.
- Les autres sous-domaines Pulse annonces par les docs 40/34 sont futurs et non
  codes ; ils ne sont pas definis ici tant qu'ils ne sont pas implementes.

### health_entries

Nom actuel : `imperium_pulse_entries`
Nom cible : `health_entries`
Source code : migration `20260525_0028_imperium_pulse_entries.py`, modele
`backend/app/models/imperium.py::ImperiumPulseEntry`

Role : journal quotidien Health/Pulse V1 minimal. Il stocke les signaux
confirmes par l'utilisateur pour une date donnee : sommeil, energie, fatigue,
poids, workout realise et note libre.

Schema reel :

```text
id             UUID PRIMARY KEY
user_id        UUID NOT NULL FK users.id
entry_date     DATE NOT NULL
sleep_hours    NUMERIC(4, 2) NULL
energy_level   SMALLINT NULL
fatigue_level  SMALLINT NULL
weight_kg      NUMERIC(5, 2) NULL
workout_done   BOOLEAN NULL
workout_type   VARCHAR(80) NULL
notes          VARCHAR(1000) NULL
created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `imperium_pulse_entries.id`
- FK : `imperium_pulse_entries.user_id -> users.id`
- Unique : `imperium_pulse_entries_user_entry_date_unique` sur
  `(user_id, entry_date)`
- Check `imperium_pulse_entries_sleep_hours_range` :
  `sleep_hours IS NULL OR (sleep_hours >= 0 AND sleep_hours <= 24)`
- Check `imperium_pulse_entries_energy_level_range` :
  `energy_level IS NULL OR (energy_level >= 1 AND energy_level <= 10)`
- Check `imperium_pulse_entries_fatigue_level_range` :
  `fatigue_level IS NULL OR (fatigue_level >= 1 AND fatigue_level <= 10)`
- Check `imperium_pulse_entries_weight_kg_positive` :
  `weight_kg IS NULL OR weight_kg > 0`
- Check `imperium_pulse_entries_workout_type_requires_workout_done` :
  `workout_done IS DISTINCT FROM false OR workout_type IS NULL`
- Index : `imperium_pulse_entries_user_entry_date_desc_idx` sur
  `(user_id, entry_date DESC)`

Regles metier Health/Pulse V1 :
- Une seule entree Health/Pulse existe par `(user_id, entry_date)`. Cette regle
  est portee par la contrainte unique DB.
- L'entree est creee explicitement par l'utilisateur ou par un endpoint valide
  cote backend. Il n'y a pas de creation automatique d'entree Pulse.
- `sleep_hours`, `energy_level`, `fatigue_level`, `weight_kg`, `workout_done`,
  `workout_type` et `notes` sont des signaux simples. Ils ne constituent pas un
  diagnostic, un health check, un health score ou une recommandation.
- `workout_type` est interdit lorsque `workout_done = false`. Il peut rester
  nul lorsque `workout_done = true` si le type n'est pas connu.
- Les endpoints de lecture `GET /api/imperium/pulse/today` et
  `GET /api/imperium/pulse/stats/summary` sont des surfaces de lecture simples
  et scopees par l'utilisateur courant.
- Pulse summary stats 11c est deterministe et read-only : il calcule des
  compteurs/moyennes a partir des lignes existantes, sans scoring, coaching,
  recommandation, orchestration n8n, appel IA, OCR, pgvector write, embeddings,
  commit memoire automatique, replanning automatique ou creation de mission.
- La table ne cree aucune liaison automatique mission/vault/path. Les liens
  inter-domaines restent des decisions explicites du backend cerveau, pas de
  l'application Pulse.

Garde-fous sante sensible :
- Le medical n'est pas active en V1 dans le schema code ci-dessus. La privacy est
  securisee par absence : aucun document medical, pain log interprete, body photo
  ou snapshot medical sensible n'est code dans cette table.
- Les futurs documents medicaux, pain logs interpretes, body snapshots et profils
  biologiques relevent de donnees de sante sensibles. Avant activation, il faut
  definir le cadre RGPD, le consentement explicite, la retention, le chiffrement,
  l'export/suppression et les controles d'acces.
- Aucune donnee sante sensible brute ne doit etre vectorisee. Le privacy gate du
  doc 09 doit s'appliquer : seules des syntheses minimales, utiles et validees
  peuvent eventuellement devenir des elements de memoire, jamais les documents ou
  donnees brutes.
- Pulse ne diagnostique pas, ne prescrit pas et ne remplace pas un professionnel
  de sante. Les futures recommandations Health devront rester explicites,
  validables et tracees.

Notes migration/ORM :
- La migration ne met pas de default serveur sur `id`; le mixin ORM genere un
  UUID cote Python.
- `created_at` et `updated_at` ont des defaults serveur en migration et en ORM.
  `updated_at` porte en plus `onupdate=func.now()` cote ORM.
- Les colonnes, types, nullabilites, contraintes et index sont alignes entre la
  migration 0028 et le modele ORM.
- Divergence de nommage : la table codee reste `imperium_pulse_entries`; le nom
  cible documente est `health_entries`.

Sous-domaines Health/Pulse futurs non codes :
- `meals` / repas : FUTUR / NON CODE. Schema a definir au moment du chantier
  repas, sans reprendre les exemples non autoritatifs des docs 40/34 comme
  definition DB.
- Hydratation : FUTUR / NON CODE. Schema a definir au moment du chantier
  hydratation.
- Food stock / stock alimentaire : FUTUR / NON CODE. Schema a definir au moment
  du chantier stock.
- Workouts : FUTUR / NON CODE. Schema a definir au moment du chantier workouts.
- Pain logs : FUTUR / NON CODE. Schema a definir au moment du chantier pain,
  avec garde-fous sante sensible.
- Body snapshots et profils biologiques : FUTUR / NON CODE. Schema a definir au
  moment du chantier body/biological profiles, avec cadre RGPD/consentement
  avant activation.
- Health scores : FUTUR / NON CODE. Aucun score sante n'est calcule ou stocke
  par la V1 codee.
- Medical documents et medical rules : FUTUR / NON CODE. Les docs 34/40
  annoncent le besoin, mais le schema doit etre redessine ici au moment du
  chantier avec consentement, retention, chiffrement et privacy gate.
- Recommandations : FUTUR / NON CODE. Schema a definir au moment du chantier
  recommandations ; aucune recommandation automatique n'est stockee en V1.

## WORSHIP

Tables worship :
`imperium_path_habits` (canonique actuel, nom cible `worship_habits`),
`imperium_path_check_ins` (canonique actuel, nom cible
`worship_check_ins`) et `imperium_path_items` (legacy deprecie).

Regle de lecture pour cette section :
- Le noyau Path/Worship V1 canonique est le couple
  `imperium_path_habits` + `imperium_path_check_ins`.
- Les noms cibles documentaires sont `worship_habits` et
  `worship_check_ins`, conformes a la convention D1 : prefixe de domaine, pas
  nom d'application.
- `imperium_path_items` est legacy. Il reste lu par compatibilite et ne doit pas
  recevoir de nouveau developpement.
- Ce document ne renomme aucune table dans le code.

### worship_habits

Nom actuel : `imperium_path_habits`
Nom cible : `worship_habits`
Source code : migration `20260525_0027_imperium_path_habits_check_ins.py`,
modele `backend/app/models/imperium.py::ImperiumPathHabit`

Role : definition des habitudes/routines Path V1 suivies par check-in explicite.
La table est generique mais devient le socle canonique Worship tant que les
tables religieuses specialisees ne sont pas codees.

Schema reel :

```text
id           UUID PRIMARY KEY
user_id      UUID NOT NULL FK users.id
title        VARCHAR(120) NOT NULL
description  VARCHAR(500) NULL
domain       VARCHAR(80) NULL
frequency    VARCHAR(20) NOT NULL
is_active    BOOLEAN NOT NULL DEFAULT true
created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `imperium_path_habits.id`
- FK : `imperium_path_habits.user_id -> users.id`
- Check `imperium_path_habits_frequency_check` :
  `frequency IN ('daily', 'weekly')`
- Index : `imperium_path_habits_user_active_created_idx` sur
  `(user_id, is_active, created_at)`
- Index : `imperium_path_habits_user_domain_idx` sur `(user_id, domain)`

Notes migration/ORM :
- La migration ne met pas de default serveur sur `id`; le mixin ORM genere un
  UUID cote Python.
- `is_active`, `created_at` et `updated_at` ont des defaults serveur en
  migration et en ORM. `updated_at` porte en plus `onupdate=func.now()` cote ORM.
- Les colonnes, types, nullabilites, contraintes et index sont alignes entre la
  migration 0027 et le modele ORM.
- Divergence de nommage : la table codee reste `imperium_path_habits`; le nom
  cible documente est `worship_habits`.

### worship_check_ins

Nom actuel : `imperium_path_check_ins`
Nom cible : `worship_check_ins`
Source code : migration `20260525_0027_imperium_path_habits_check_ins.py`,
modele `backend/app/models/imperium.py::ImperiumPathCheckIn`

Role : enregistrement explicite d'un check-in utilisateur pour une habitude Path
sur une date donnee. Aucune ligne n'est creee automatiquement pour un etat
`pending`.

Schema reel :

```text
id          UUID PRIMARY KEY
user_id     UUID NOT NULL FK users.id
habit_id    UUID NOT NULL FK imperium_path_habits.id
check_date  DATE NOT NULL
status      VARCHAR(20) NOT NULL
reason      VARCHAR(500) NULL
note        VARCHAR(500) NULL
created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `imperium_path_check_ins.id`
- FK : `imperium_path_check_ins.user_id -> users.id`
- FK :
  `imperium_path_check_ins.habit_id -> imperium_path_habits.id`
- Check `imperium_path_check_ins_status_check` :
  `status IN ('done', 'missed')`
- Unique : `imperium_path_check_ins_user_habit_date_unique` sur
  `(user_id, habit_id, check_date)`
- Index : `imperium_path_check_ins_user_check_date_desc_idx` sur
  `(user_id, check_date DESC)`
- Index : `imperium_path_check_ins_user_habit_check_date_idx` sur
  `(user_id, habit_id, check_date)`

Notes migration/ORM :
- La migration ne met pas de default serveur sur `id`; le mixin ORM genere un
  UUID cote Python.
- `created_at` et `updated_at` ont des defaults serveur en migration et en ORM.
  `updated_at` porte en plus `onupdate=func.now()` cote ORM.
- Les colonnes, types, nullabilites, contraintes et index sont alignes entre la
  migration 0027 et le modele ORM.
- `pending` n'est pas une valeur stockee : c'est un etat de lecture calcule par
  `PathTodayResponse` quand aucune ligne de check-in n'existe pour
  `(user_id, habit_id, check_date)`.
- `missed` exige une `reason` dans le schema API
  `backend/app/schemas/path.py::PathCheckInCreate`, mais cette regle n'est pas
  encore portee par une contrainte SQL. La colonne reste nullable en base.
- Divergence de nommage : la table codee reste `imperium_path_check_ins`; le nom
  cible documente est `worship_check_ins`.

### imperium_path_items

Nom actuel : `imperium_path_items`
Nom cible : aucun. Table DEPRECIEE, legacy, a supprimer apres migration des
lecteurs restants.
Source code : migration `20260426_0008_imperium_path_items.py`, modele
`backend/app/models/imperium.py::ImperiumPathItem`

Role legacy : ancien modele d'items Path planifies. Il est remplace pour Path V1
par le couple canonique `imperium_path_habits` + `imperium_path_check_ins`.
Ne pas creer de nouveau developpement dessus.

Schema reel bref :

```text
id             UUID PRIMARY KEY
user_id        UUID NOT NULL FK users.id
local_date     DATE NOT NULL
timezone       TEXT NOT NULL DEFAULT 'Europe/Paris'
title          TEXT NOT NULL
description    TEXT NULL
category       TEXT NULL
priority_key   TEXT NULL
planned_start  TIMESTAMPTZ NULL
planned_end    TIMESTAMPTZ NULL
status         TEXT NOT NULL
source         TEXT NOT NULL DEFAULT 'manual'
sort_order     INTEGER NOT NULL DEFAULT 0
skip_reason    TEXT NULL
completed_at   TIMESTAMPTZ NULL
skipped_at     TIMESTAMPTZ NULL
cancelled_at   TIMESTAMPTZ NULL
metadata       JSONB NOT NULL DEFAULT '{}'::jsonb
created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `imperium_path_items.id`
- FK : `imperium_path_items.user_id -> users.id`
- Check `imperium_path_items_status_check` :
  `status IN ('planned', 'in_progress', 'completed', 'skipped', 'cancelled')`
- Check `imperium_path_items_source_check` :
  `source IN ('manual', 'system', 'ai_planned')`
- Index : `imperium_path_items_user_local_date_idx` sur
  `(user_id, local_date)`
- Index : `imperium_path_items_user_status_idx` sur `(user_id, status)`
- Index : `imperium_path_items_user_planned_start_idx` sur
  `(user_id, planned_start)`
- Index : `imperium_path_items_user_local_date_sort_idx` sur
  `(user_id, local_date, sort_order)`

Notes legacy :
- Cette table melange planification, statut, source systeme/IA et metadonnees.
  Elle ne represente pas le noyau Worship V1 canonique.
- Lecteurs a migrer avant suppression :
  `backend/app/services/imperium/dashboard.py`,
  `backend/app/services/imperium/daily_plans.py` et
  `backend/app/services/imperium/weekly_report.py`.
- Anciennes surfaces encore presentes :
  `backend/app/api/v1/routes/imperium.py` et
  `backend/app/services/imperium/path_items.py`.

Regles metier du noyau Worship canonique :
- Fondation Path 10a : habits + check-ins seulement. Les vues "today", detail
  habit, detail check-in et stats summary lisent cette fondation.
- Tous les ecritures Path/Worship canoniques requierent une action utilisateur
  explicite, une validation backend et une `Idempotency-Key`.
- Aucun check-in n'est cree automatiquement. Une absence de ligne reste un
  `pending` de lecture et ne doit pas entrer dans les statistiques.
- Les stats ne comptent que les lignes stockees `done` et `missed`; `pending`
  est exclu du denominateur.
- Une seule ligne de check-in peut exister par `(user_id, habit_id, check_date)`.
- `missed` doit porter une raison cote API/service. `done` ne porte pas de
  `reason`; les commentaires vont dans `note`.
- Les habitudes archivees (`is_active = false`) ne peuvent plus recevoir de
  nouveaux check-ins via le service canonique, mais leur historique reste lisible.
- Le domaine `worship` est une valeur API supportee pour les habitudes Path.
  Les valeurs francaises restent des labels UI, pas des valeurs stockees.

Regles religieuses et limites d'automatisation :
- Path/Worship n'est pas une autorite religieuse. Il ne donne pas de fatwa, ne
  deduit pas une obligation et ne transforme pas le silence de l'utilisateur en
  jugement religieux.
- Le wording doit rester non jugeant : l'interface peut dire "non marquee comme
  accomplie", mais ne doit pas culpabiliser l'utilisateur.
- Les actions religieuses ne sont jamais marquees comme accomplies par inference
  depuis la localisation, l'heure, le calendrier, l'activite telephone, une IA ou
  un workflow.
- Pour cette fondation 10a : pas d'appel IA/cloud, pas de n8n, pas de scoring,
  pas de calendrier, pas d'ecriture pgvector, pas d'embeddings, pas de commit
  memoire automatique, pas de replanning automatique et pas de liaison
  automatique mission/Vault/Pulse.
- Les textes arabes, invocations ou contenus religieux futurs ne doivent pas etre
  interpretes par l'IA sans cadre religieux explicite, source et validation
  utilisateur. Le socle habits/check-ins ne stocke pas d'interpretation arabe.
- Les futurs liens sadaqa, calendrier religieux, ghusl, prieres, fasting,
  invocations et memoire doivent rester des contrats explicites separes. Ils ne
  doivent pas etre caches dans `imperium_path_habits`,
  `imperium_path_check_ins` ou `imperium_path_items`.

## PLANNING

Tables planning codees :
`imperium_missions` (nom cible `planning_missions`),
`imperium_daily_plans` (nom cible `planning_daily_plans`) et
`imperium_day_reviews` (nom cible `planning_day_reviews`).

Regle de lecture pour cette section :
- Le domaine cible est `planning`, conformement a D1 : prefixe de domaine, pas
  nom d'application.
- Ce document ne renomme aucune table dans le code. Les noms cibles documentent
  la direction canonique future.
- Le schema reel ci-dessous vient des migrations Alembic et des modeles
  SQLAlchemy. Les surfaces API/snapshot sont mentionnees seulement quand elles
  clarifient le role de la table.
- La regle produit non negociable reste : une seule mission active a la fois.

### planning_missions

Nom actuel : `imperium_missions`
Nom cible : `planning_missions`
Source code : migrations `20260426_0005_imperium_missions.py`,
`20260511_0020_imperium_missions_decision_fields.py`,
`20260525_0023_imperium_mission_abandoned_status.py`, modele
`backend/app/models/imperium.py::ImperiumMission`

Role : stocker les missions planning courantes, en backlog et historiques. Cette
table est le garde-fou backend de la mission active unique.

Schema reel :

```text
id                      UUID PRIMARY KEY
user_id                 UUID NOT NULL FK users.id
title                   TEXT NOT NULL
category                TEXT NULL
domain                  TEXT NULL
priority_level          INTEGER NULL
mission_type_category   TEXT NULL
status                  TEXT NOT NULL
planned_start_at        TIMESTAMPTZ NULL
planned_end_at          TIMESTAMPTZ NULL
started_at              TIMESTAMPTZ NOT NULL
ended_at                TIMESTAMPTZ NULL
completion_note         TEXT NULL
failure_reason          TEXT NULL
user_reported_signals   JSONB NULL
ai_usable_reason        BOOLEAN NULL
created_by_event_id     UUID NULL FK events.id
ended_by_event_id       UUID NULL FK events.id
created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `imperium_missions.id`
- FK : `imperium_missions.user_id -> users.id`
- FK : `imperium_missions.created_by_event_id -> events.id`
- FK : `imperium_missions.ended_by_event_id -> events.id`
- Check `imperium_missions_status_check` :
  `status IN ('backlog', 'active', 'completed', 'failed', 'abandoned', 'cancelled')`
- Check `imperium_missions_domain_check` :
  `domain IS NULL OR domain IN ('religious', 'business', 'finance', 'health')`
- Check `imperium_missions_priority_level_range` :
  `priority_level IS NULL OR (priority_level >= 1 AND priority_level <= 10)`
- Check `imperium_missions_mission_type_category_check` :
  `mission_type_category IS NULL OR mission_type_category IN ('cat_a', 'cat_b',
  'cat_c', 'cat_d', 'cat_e', 'cat_f', 'cat_g', 'cat_h', 'cat_i')`
- Index unique partiel : `imperium_missions_one_active_per_user_idx` sur
  `user_id` WHERE `status = 'active'`
- Index : `imperium_missions_user_status_idx` sur `(user_id, status)`
- Index : `imperium_missions_started_at_idx` sur `started_at`
- Index : `imperium_missions_user_domain_idx` sur `(user_id, domain)`
- Index partiel : `imperium_missions_user_backlog_priority_created_idx` sur
  `(user_id, priority_level, created_at)` WHERE `status = 'backlog'`
- Index : `imperium_missions_user_mission_type_category_idx` sur
  `(user_id, mission_type_category)`

Regles metier planning :
- Une seule mission peut etre `active` par utilisateur. La regle est portee par
  l'index unique partiel et doit aussi etre gardee par tous les services,
  snapshots et futurs replans.
- Le lifecycle code accepte `backlog`, `active`, `completed`, `failed`,
  `abandoned` et `cancelled`. Les documents metier historiques parlent aussi
  d'expiration et de stash ; ces etats ne sont pas codes dans la contrainte
  actuelle. `stashed` est hors V1.
- Une mission demarree devient `active`. Une mission de backlog peut etre
  promue seulement si aucune autre mission active n'existe.
- Les transitions codees exigent une mission `active` pour terminer, echouer ou
  abandonner. `failed` et `abandoned` portent une raison cote schema API.
- `failure_reason`, `user_reported_signals` et `ai_usable_reason` conservent la
  realite rapportee par l'utilisateur pour apprentissage futur ; V1 ne juge pas
  et ne reinterprete pas automatiquement ces raisons.
- Les colonnes `created_by_event_id` et `ended_by_event_id` pointent vers le
  journal canonique `events`, pas vers `imperium_events`.
- La table ne porte pas encore les attributs futurs annonces par la doc 43 comme
  `source`, `source_ref`, `replan_version`, `deadline_at`, `expired_at` ou
  `stashed_at`.

Notes migration/ORM :
- La migration initiale creeait les statuts `active`, `completed`, `failed`,
  `cancelled`; `20260511_0020` a ajoute `backlog`, `domain` et
  `mission_type_category`; `20260525_0023` a ajoute `abandoned`.
- La migration ne met pas de default serveur sur `id`; le mixin ORM genere un
  UUID cote Python.
- `created_at` et `updated_at` ont des defaults serveur en migration et en ORM.
  `updated_at` porte en plus `onupdate=func.now()` cote ORM.
- Les colonnes, types, nullabilites, contraintes et index courants sont alignes
  entre migrations et modele ORM.
- Divergence de nommage : la table codee reste `imperium_missions`; le nom
  cible documente est `planning_missions`.

### planning_daily_plans

Nom actuel : `imperium_daily_plans`
Nom cible : `planning_daily_plans`
Source code : migration `20260426_0009_imperium_daily_plans.py`, modele
`backend/app/models/imperium.py::ImperiumDailyPlan`

Role reel code : plan quotidien persistant, cree manuellement/deterministement a
partir de verites backend existantes. Role cible D4 : base persistante du living
plan versionne.

Schema reel :

```text
id                  UUID PRIMARY KEY
user_id             UUID NOT NULL FK users.id
local_date          DATE NOT NULL
timezone            TEXT NOT NULL DEFAULT 'Europe/Paris'
plan_status         TEXT NOT NULL DEFAULT 'draft'
title               TEXT NULL
summary             TEXT NULL
focus_priority_key  TEXT NULL
current_mission_id  UUID NULL FK imperium_missions.id
generated_from      JSONB NOT NULL DEFAULT '{}'::jsonb
plan_blocks         JSONB NOT NULL DEFAULT '[]'::jsonb
notes               TEXT NULL
created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `imperium_daily_plans.id`
- FK : `imperium_daily_plans.user_id -> users.id`
- FK :
  `imperium_daily_plans.current_mission_id -> imperium_missions.id`
- Unique : `imperium_daily_plans_user_local_date_unique` sur
  `(user_id, local_date)`
- Check `imperium_daily_plans_status_check` :
  `plan_status IN ('draft', 'active', 'completed', 'cancelled')`
- Check `imperium_daily_plans_plan_blocks_array_check` :
  `jsonb_typeof(plan_blocks) = 'array'`
- Index : `imperium_daily_plans_user_local_date_idx` sur
  `(user_id, local_date)`
- Index : `imperium_daily_plans_user_status_idx` sur
  `(user_id, plan_status)`

Contrat D4 daily plan vivant :
- `imperium_daily_plans` est la base persistante qui doit devenir le support du
  living plan. La journee n'est pas un JSON oublie ni un plan ecrase : elle doit
  etre stockee en tables, lisible par Imperium, et signalee par events.
- Le module `backend/app/services/imperium/daily_plan.py` et l'endpoint moderne
  `GET /api/imperium/daily-plan` sont un snapshot / une vue de LECTURE. Ils
  consolident dashboard, mission active, Path et Pulse ; ils ne persistent pas
  de ligne `imperium_daily_plans` et ne definissent pas une table concurrente.
- La surface persistante actuelle `/api/imperium/day/plan...` cree, lit,
  active, complete et annule des lignes `imperium_daily_plans`. Elle est
  utile comme fondation, mais ne code pas encore la generation IA, le replan
  vivant, la validation de proposition ou l'historique de versions.
- La future table `planning_daily_plan_versions` est FUTURE / NON CODEE. Sa
  raison d'etre est le versionnement D4 : chaque replan cree une nouvelle
  version avec sa raison, archive l'ancienne version et nourrit l'apprentissage
  futur / LoRA. Ne pas inventer son schema detaille avant le chantier D4.
- On VERSIONNE, on n'ecrase pas. Un replan futur ne doit pas masquer la raison
  de changement ni detruire l'historique de la journee.
- Le plan vivant doit respecter la garde globale "une seule mission active a la
  fois". Il ne peut pas creer une mission active concurrente.

Notes migration/ORM :
- La migration ne met pas de default serveur sur `id`; le mixin ORM genere un
  UUID cote Python.
- `timezone`, `plan_status`, `generated_from`, `plan_blocks`, `created_at` et
  `updated_at` ont des defaults serveur en migration et en ORM.
- `updated_at` porte en plus `onupdate=func.now()` cote ORM.
- Les colonnes, types, nullabilites, contraintes et index sont alignes entre la
  migration 0009 et le modele ORM.
- Divergence de nommage : la table codee reste `imperium_daily_plans`; le nom
  cible documente est `planning_daily_plans`.

### planning_day_reviews

Nom actuel : `imperium_day_reviews`
Nom cible : `planning_day_reviews`
Source code : migration `20260426_0004_imperium_day_reviews.py`, modele
`backend/app/models/imperium.py::ImperiumDayReview`

Role : bilan de journee. Cette table capture le statut global du jour, les
signaux ressentis, les items termines/manques et les notes utilisateur pour
alimenter les lectures, les reviews et l'apprentissage futur.

Schema reel :

```text
id                 UUID PRIMARY KEY
user_id            UUID NOT NULL FK users.id
local_date         DATE NOT NULL
timezone           TEXT NOT NULL
day_status         TEXT NOT NULL
energy_level       INTEGER NULL
fatigue_level      INTEGER NULL
sleep_quality      INTEGER NULL
stress_level       INTEGER NULL
mood               TEXT NULL
main_win           TEXT NULL
main_problem       TEXT NULL
completed_items    JSONB NOT NULL DEFAULT '[]'
missed_items       JSONB NOT NULL DEFAULT '[]'
notes              TEXT NULL
free_text          TEXT NULL
source_event_id    TEXT NULL
created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `imperium_day_reviews.id`
- FK : `imperium_day_reviews.user_id -> users.id`
- Unique : `imperium_day_reviews_user_local_date_unique` sur
  `(user_id, local_date)`
- Index : `imperium_day_reviews_user_created_idx` sur
  `(user_id, created_at)`

Regles metier planning :
- Une seule day review peut exister par utilisateur et date locale. Un second
  finish-day non idempotent est rejete par le service.
- `day_status` est valide par le schema API `FinishDayRequest` avec les valeurs
  `completed`, `partial`, `failed`, mais la base ne porte pas encore de check SQL
  equivalent.
- `energy_level`, `fatigue_level`, `sleep_quality` et `stress_level` sont
  bornes de 1 a 10 cote schema API, mais la base ne porte pas encore de check SQL
  equivalent.
- `completed_items` et `missed_items` stockent des listes JSON issues du bilan
  utilisateur. `missed_items` peut porter une raison et un signal rapporte par
  l'utilisateur.
- `source_event_id` stocke l'identifiant metier de l'event `day.finished`, mais
  n'est pas une FK vers `events.id`.

Notes migration/ORM :
- La migration ne met pas de default serveur sur `id`; le mixin ORM genere un
  UUID cote Python.
- `completed_items` et `missed_items` ont des defaults serveur en migration et
  des defaults Python `list` en ORM.
- `created_at` et `updated_at` ont des defaults serveur en migration et en ORM.
  `updated_at` porte en plus `onupdate=func.now()` cote ORM.
- Divergence de durcissement : la validation des valeurs `day_status` et des
  niveaux 1-10 est portee par les schemas API, pas par des contraintes SQL.
- Divergence de durcissement : aucune contrainte SQL ne verifie que
  `completed_items` et `missed_items` sont des tableaux JSON.
- Divergence de nommage : la table codee reste `imperium_day_reviews`; le nom
  cible documente est `planning_day_reviews`.

Invariants planning reintegres :
- Imperium reste le command center : les apps affichent, collectent et
  declenchent ; le backend cerveau decide et valide.
- La mission active unique est un garde-fou partout : DB, services, snapshots,
  read models, futurs hooks et replans. Une anomalie de plusieurs missions
  actives doit etre detectee et exposee comme erreur, pas masquee.
- Le mission lifecycle V1 code est volontairement simple : backlog -> active ->
  terminal (`completed`, `failed`, `abandoned`, `cancelled`). Les notions
  `expired`, `stashed`, missions annexes et overlay restent hors schema code
  actuel.
- Les projets actifs et routines d'Operations sont la source future de missions,
  mais leurs tables planning canoniques ne sont pas encore codees. La regle
  documentee par la doc 71 est V1 cible : viser deux projets actifs quand la
  pile le permet, garder une liste non-active distincte, auto-promouvoir apres
  completion et rendre un projet incomplet inerte en "Attention requise".
- Les routines quotidiennes simples sont FUTURES / NON CODEES dans le domaine
  planning. Elles devront alimenter l'arbitrage et le daily plan, sans devenir
  une logique UI autonome.
- Le bilan de journee (`planning_day_reviews`) sert a expliquer ce qui s'est
  passe : victoires, problemes, items manques, fatigue, humeur et signaux. Il
  ne remplace pas l'historique de missions ni les events.

Tables planning futures / non codees :
- `planning_daily_plan_versions` : FUTUR / NON CODE. Versionnement du living
  plan D4 ; chaque replan cree une nouvelle version et conserve la raison.
- `planning_replan_events` : FUTUR / NON CODE. Capture des triggers de replan,
  debounce/batching, statut et lien futur vers tache IA / version de plan.
- Morning check-ins : FUTUR / NON CODE. La doc 43 annonce le check-in du matin
  comme premier replan de la journee ; aucune table canonique `planning_*` n'est
  encore definie ici.
- Projets Operations : FUTUR / NON CODE. Le nom canonique reste a definir dans
  ce dictionnaire avant migration ; ne pas reprendre `projects` comme schema
  officiel sans chantier dedie.
- Routines recurrentes et checks quotidiens : FUTUR / NON CODE. Les noms cibles
  restent a definir dans ce dictionnaire avant implementation.
- Expiration de mission, notes de mission, `source/source_ref`,
  `replan_version` et liens objectifs -> missions : FUTUR / NON CODE dans les
  tables planning actuelles.

## DECISION

Tables d'arbitrage et scoring :
`imperium_user_priorities`, `imperium_mission_scores`.

Convention D1 : le domaine cible est `decision`. Les noms cibles sont
documentes ici pour le dictionnaire central, mais le code garde les noms actuels
jusqu'a une migration explicite future. Ne pas renommer les tables dans les
modeles, migrations ou services sans chantier dedie.

### decision_user_priorities

Nom actuel : `imperium_user_priorities`
Nom cible : `decision_user_priorities`
Source code : migration `20260504_0019_decision_framework_foundation.py`,
modele `backend/app/models/imperium.py::ImperiumUserPriority`

Role : source canonique active de l'ordre de priorite utilisateur pour le
Decision Framework. Cette table remplace `imperium_priority_rules` pour
l'arbitrage moderne.

Schema reel :

```text
id           UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_id      UUID NOT NULL FK users.id
domain       TEXT NOT NULL
position     INTEGER NOT NULL
coefficient  INTEGER NOT NULL
is_active    BOOLEAN NOT NULL DEFAULT true
created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `imperium_user_priorities.id`
- FK : `imperium_user_priorities.user_id -> users.id`
- Check : `domain IN ('religious', 'business', 'finance', 'health')`
- Check : `position >= 1 AND position <= 4`
- Check position/coefficient :
  - `position = 1` impose `coefficient = 10`
  - `position = 2` impose `coefficient = 8`
  - `position = 3` impose `coefficient = 5`
  - `position = 4` impose `coefficient = 4`
- Index unique partiel :
  `imperium_user_priorities_active_domain_unique_idx` sur `(user_id, domain)`
  WHERE `is_active = true`
- Index unique partiel :
  `imperium_user_priorities_active_position_unique_idx` sur
  `(user_id, position)` WHERE `is_active = true`
- Index : `imperium_user_priorities_user_active_position_idx` sur
  `(user_id, is_active, position)`

Notes migration/ORM :
- Divergence de nommage : la table codee reste `imperium_user_priorities`; le
  nom cible documente est `decision_user_priorities`.
- La migration 0019 met `id` en default serveur `gen_random_uuid()`; le mixin
  ORM genere aussi un UUID cote Python avec `uuid4`.
- Les colonnes, types, nullabilites, FK, checks et index sont alignes entre la
  migration 0019 et le modele ORM.
- Les noms de checks apparaissent en ORM sous leur nom logique court, puis sont
  rendus avec la convention SQLAlchemy (`ck_<table>_<name>`) comme dans la
  migration.

### decision_mission_scores

Nom actuel : `imperium_mission_scores`
Nom cible : `decision_mission_scores`
Source code : migration `20260504_0019_decision_framework_foundation.py`,
modele `backend/app/models/imperium.py::ImperiumMissionScore`

Role : stockage backend des scores Decision Framework des missions. La version
retenue est COMPACTE : les colonnes detaillees `criterion_a`..`criterion_e`
n'existent pas en V1 ; le detail A-E vit dans `explanation` JSONB.

Schema reel :

```text
id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_id             UUID NOT NULL FK users.id
mission_id          UUID NOT NULL FK imperium_missions.id ON DELETE CASCADE
domain              TEXT NOT NULL
intrinsic_score     NUMERIC(5,2) NOT NULL
domain_coefficient  INTEGER NOT NULL
weighted_score      NUMERIC(7,2) NOT NULL
explanation         JSONB NOT NULL DEFAULT '{}'::jsonb
source              TEXT NOT NULL DEFAULT 'decision_framework_v1'
created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `imperium_mission_scores.id`
- FK : `imperium_mission_scores.user_id -> users.id`
- FK :
  `imperium_mission_scores.mission_id -> imperium_missions.id`
  avec `ON DELETE CASCADE`
- Check : `domain IN ('religious', 'business', 'finance', 'health')`
- Check : `intrinsic_score >= 0 AND intrinsic_score <= 100`
- Check : `domain_coefficient IN (10, 8, 5, 4)`
- Check : `weighted_score >= 0`
- Check : `source IN ('decision_framework_v1')`
- Index : `imperium_mission_scores_user_weighted_idx` sur
  `(user_id, weighted_score)`
- Index : `imperium_mission_scores_user_domain_idx` sur `(user_id, domain)`
- Index : `imperium_mission_scores_mission_idx` sur `(mission_id)`
- Index unique ORM uniquement :
  `imperium_mission_scores_user_mission_source_unique_idx` sur
  `(user_id, mission_id, source)`

Notes migration/ORM :
- Divergence de nommage : la table codee reste `imperium_mission_scores`; le nom
  cible documente est `decision_mission_scores`.
- La migration 0019 met `id` en default serveur `gen_random_uuid()`; le mixin
  ORM genere aussi un UUID cote Python avec `uuid4`.
- Divergence migration/ORM : le modele ORM declare l'index unique
  `imperium_mission_scores_user_mission_source_unique_idx` sur
  `(user_id, mission_id, source)`, mais la migration 0019 ne le cree pas.
- Les autres colonnes, types, nullabilites, FK, checks et index sont alignes
  entre la migration 0019 et le modele ORM.
- Les noms de checks apparaissent en ORM sous leur nom logique court, puis sont
  rendus avec la convention SQLAlchemy (`ck_<table>_<name>`) comme dans la
  migration.

### imperium_priority_rules

Nom actuel : `imperium_priority_rules`
Nom cible : aucun. Table DEPRECIEE, legacy, a supprimer apres migration du
dernier lecteur.
Source code : migration `20260426_0006_imperium_priority_rules.py`, modele
`backend/app/models/imperium.py::ImperiumPriorityRule`

Role legacy : ancienne hierarchie de priorites Imperium. La decision actee est :
`imperium_user_priorities` est CANONIQUE pour le Decision Framework ;
`imperium_priority_rules` est deprecie, ses writes sont bloques en `410 Gone`,
et le dernier lecteur connu a migrer est
`backend/app/services/imperium/weekly_report.py`.

Schema reel bref :

```text
id                   UUID PRIMARY KEY
user_id              UUID NOT NULL FK users.id
priority_key         TEXT NOT NULL
label                TEXT NOT NULL
rank_order           INTEGER NOT NULL
importance_score     INTEGER NULL
is_active            BOOLEAN NOT NULL
updated_by_event_id  UUID NULL FK events.id
created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `imperium_priority_rules.id`
- FK : `imperium_priority_rules.user_id -> users.id`
- FK : `imperium_priority_rules.updated_by_event_id -> events.id`
- Check : `rank_order > 0`
- Check :
  `importance_score IS NULL OR (importance_score >= 1 AND importance_score <= 100)`
- Index unique partiel :
  `imperium_priority_rules_active_rank_unique_idx` sur `(user_id, rank_order)`
  WHERE `is_active = true`
- Index unique partiel :
  `imperium_priority_rules_active_key_unique_idx` sur `(user_id, priority_key)`
  WHERE `is_active = true`
- Index : `imperium_priority_rules_user_active_rank_idx` sur
  `(user_id, is_active, rank_order)`

Notes legacy :
- Ne pas ajouter de nouveau developpement sur cette table.
- La route legacy de lecture `/api/imperium/priorities` reste une projection de
  compatibilite et annonce `canonical_source = imperium_user_priorities`.
- La route legacy d'ecriture `/api/imperium/priorities` est bloquee en
  `410 Gone`; les ecritures doivent passer par
  `/api/imperium/decision-framework/priorities`.
- Lecteur a migrer avant suppression : `weekly_report`.

Regles metier du Decision Framework :
- L'ordre de domaines vient de `imperium_user_priorities`, source canonique
  active. `imperium_priority_rules` ne doit plus etre considere comme source de
  verite.
- Les domaines stockes/API sont en anglais :
  `religious`, `business`, `finance`, `health`. Les labels francais restent UI.
- Les coefficients sont internes et derives de la position utilisateur :
  position 1 = x10, position 2 = x8, position 3 = x5, position 4 = x4.
- Le scoring mission est deterministe et backend-only : memes entrees, meme
  score. Il ne declenche aucun appel IA, n8n, pgvector, embedding, memoire,
  calendrier ou replanning automatique.
- Le score intrinseque A-E est calcule de 0 a 100 :
  A deadline proximity, B impact gravity, C mission type, D dependency,
  E recurrence. En V1, ces details sont stockes dans `explanation` JSONB et non
  dans des colonnes `criterion_a`..`criterion_e`.
- Le score pondere est interne :
  `weighted_score = intrinsic_score * domain_coefficient`.
- Les surfaces publiques ne doivent pas exposer `domain_coefficient`,
  `weighted_score`, `final_weighted_score`, `position_to_coefficient` ou la
  formule interne. Elles exposent un resume public, notamment `priority_bucket`
  et les labels/reason codes autorises.
- Le `priority_bucket` public est derive par brackets fixes du score pondere :
  `>=700 => 10`, `600-699 => 9`, `500-599 => 8`, `400-499 => 7`,
  `300-399 => 6`, `200-299 => 5`, `100-199 => 4`, `50-99 => 3`,
  `20-49 => 2`, `0-19 => 1`.

## REVIEW

Tables Weekly Review :
`imperium_weekly_review_sessions`, `imperium_weekly_review_messages`,
`imperium_weekly_review_final_reports`, `imperium_weekly_review_states`,
`imperium_memory_candidate_decisions`.

Convention D1 : le domaine cible est `review`. Les noms cibles sont
documentes ici pour le dictionnaire central, mais le code garde les noms actuels
jusqu'a une migration explicite future. Ne pas renommer les tables dans les
modeles, migrations ou services sans chantier dedie.

Nommage cible acte :
- `imperium_weekly_review_sessions` -> `review_sessions`
- `imperium_weekly_review_messages` -> `review_messages`
- `imperium_weekly_review_final_reports` -> `review_final_reports`
- `imperium_weekly_review_states` -> `review_states` (À CLARIFIER)
- `imperium_memory_candidate_decisions` -> `review_memory_decisions`

WR signifie Weekly Review, pas Weekly Report. Le Weekly Report du doc 29 est un
rapport deterministe read-only ; le Weekly Review du doc 32 est la conversation
interactive IA, backend-owned, qui transforme la semaine en rapport final
valide par l'utilisateur.

### review_sessions

Nom actuel : `imperium_weekly_review_sessions`
Nom cible : `review_sessions`
Source code : migrations `20260430_0013_weekly_review_conversation.py` et
`20260501_0016_wr_chatbot_flow_constraints.py`, modele
`backend/app/models/imperium.py::ImperiumWeeklyReviewSession`

Role : machine conversationnelle WR canonique. Cette table porte la session
interactive, le statut courant, la fenetre de semaine et les pointeurs vers les
taches/resultats IA associes.

Schema reel :

```text
id                    UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_id               UUID NOT NULL FK users.id
week_start            DATE NOT NULL
week_end              DATE NOT NULL
status                TEXT NOT NULL DEFAULT 'ready'
launched_at           TIMESTAMPTZ NULL
completed_at          TIMESTAMPTZ NULL
failed_at             TIMESTAMPTZ NULL
error_code            TEXT NULL
error_message         TEXT NULL
current_ai_task_id    UUID NULL FK ai_tasks.id
initial_ai_result_id  UUID NULL FK ai_results.id
final_ai_result_id    UUID NULL FK ai_results.id
created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `imperium_weekly_review_sessions.id`
- FK : `imperium_weekly_review_sessions.user_id -> users.id`
- FK :
  `imperium_weekly_review_sessions.current_ai_task_id -> ai_tasks.id`
- FK :
  `imperium_weekly_review_sessions.initial_ai_result_id -> ai_results.id`
- FK :
  `imperium_weekly_review_sessions.final_ai_result_id -> ai_results.id`
- Unique : `imperium_weekly_review_sessions_user_week_unique` sur
  `(user_id, week_start)`
- Check `imperium_weekly_review_sessions_status_check` :
  `ready`, `launched`, `preparing_initial_summary`,
  `initial_summary_ready`, `waiting_for_user_answer`,
  `conversation_active`, `integrating_answers`, `draft_ready`,
  `revision_requested`, `final_ready`, `approved`, `stored`, `cancelled`,
  `failed`
- Index : `imperium_weekly_review_sessions_user_status_idx` sur
  `(user_id, status)`
- Index : `imperium_weekly_review_sessions_user_week_start_idx` sur
  `(user_id, week_start)`

Notes migration/ORM :
- Divergence de nommage : la table codee reste
  `imperium_weekly_review_sessions`; le nom cible documente est
  `review_sessions`.
- La migration met `id` en default serveur `gen_random_uuid()` ; le mixin ORM
  genere aussi un UUID cote Python.
- La migration 0013 creait la machine sans `conversation_active`; la migration
  0016 ajoute ce statut au check. Le modele ORM est aligne sur l'etat courant.
- `week_start` est valide cote schemas/services comme un lundi. Il n'existe pas
  de check SQL qui impose le lundi.
- `week_end` est stocke comme date de fin affichee de semaine
  (`week_start + 6 jours`), pas comme borne SQL exclusive. Il n'existe pas de
  check SQL qui impose `week_end = week_start + 6`.

### review_messages

Nom actuel : `imperium_weekly_review_messages`
Nom cible : `review_messages`
Source code : migrations `20260430_0013_weekly_review_conversation.py` et
`20260501_0016_wr_chatbot_flow_constraints.py`, modele
`backend/app/models/imperium.py::ImperiumWeeklyReviewMessage`

Role : journal des messages de la conversation WR. Les messages sont rattaches
a une session et peuvent pointer vers une tache IA ou un resultat IA.

Schema reel :

```text
id            UUID PRIMARY KEY DEFAULT gen_random_uuid()
session_id    UUID NOT NULL FK imperium_weekly_review_sessions.id ON DELETE CASCADE
user_id       UUID NOT NULL FK users.id
role          TEXT NOT NULL
message_type  TEXT NOT NULL
content       TEXT NULL
payload       JSONB NULL
ai_task_id    UUID NULL FK ai_tasks.id
ai_result_id  UUID NULL FK ai_results.id
created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `imperium_weekly_review_messages.id`
- FK :
  `imperium_weekly_review_messages.session_id -> imperium_weekly_review_sessions.id`
  avec `ON DELETE CASCADE`
- FK : `imperium_weekly_review_messages.user_id -> users.id`
- FK : `imperium_weekly_review_messages.ai_task_id -> ai_tasks.id`
- FK : `imperium_weekly_review_messages.ai_result_id -> ai_results.id`
- Check `imperium_weekly_review_messages_role_check` :
  `user`, `qwen`, `system`, `opus`, `backend`
- Check `imperium_weekly_review_messages_type_check` :
  `user_answer`, `clarification_question`, `initial_summary`, `draft`,
  `revision_request`, `final_report`, `system_note`, `chat_message`,
  `assistant_followup`, `final_report_draft`
- Index : `imperium_weekly_review_messages_session_created_idx` sur
  `(session_id, created_at)`
- Index : `imperium_weekly_review_messages_user_created_idx` sur
  `(user_id, created_at)`

Notes migration/ORM :
- Divergence de nommage : la table codee reste
  `imperium_weekly_review_messages`; le nom cible documente est
  `review_messages`.
- La migration met `id` en default serveur `gen_random_uuid()` ; le mixin ORM
  genere aussi un UUID cote Python.
- La migration 0013 creait les types initiaux ; la migration 0016 ajoute
  `chat_message`, `assistant_followup` et `final_report_draft`. Le modele ORM
  est aligne sur l'etat courant.
- Il n'existe pas de contrainte SQL qui impose que `user_id` du message soit le
  meme que `user_id` de la session. Cette coherence est portee par les services.

### review_final_reports

Nom actuel : `imperium_weekly_review_final_reports`
Nom cible : `review_final_reports`
Source code : migrations `20260430_0013_weekly_review_conversation.py` et
`20260430_0014_wr_final_report_candidate_history.py`, modele
`backend/app/models/imperium.py::ImperiumWeeklyReviewFinalReport`

Role : candidats de rapport final WR. Les lignes historisent les drafts,
approbations, stockages et candidats superseded. Un candidat n'est pas
canonique tant qu'il n'a pas ete explicitement approuve puis stocke par le
backend.

Schema reel :

```text
id                   UUID PRIMARY KEY DEFAULT gen_random_uuid()
session_id           UUID NOT NULL FK imperium_weekly_review_sessions.id ON DELETE CASCADE
user_id              UUID NOT NULL FK users.id
week_start           DATE NOT NULL
week_end             DATE NOT NULL
status               TEXT NOT NULL DEFAULT 'draft'
report_payload       JSONB NOT NULL
report_markdown      TEXT NOT NULL
memory_candidates    JSONB NULL
approved_at          TIMESTAMPTZ NULL
stored_at            TIMESTAMPTZ NULL
source_ai_result_id  UUID NULL FK ai_results.id
created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `imperium_weekly_review_final_reports.id`
- FK :
  `imperium_weekly_review_final_reports.session_id -> imperium_weekly_review_sessions.id`
  avec `ON DELETE CASCADE`
- FK : `imperium_weekly_review_final_reports.user_id -> users.id`
- FK :
  `imperium_weekly_review_final_reports.source_ai_result_id -> ai_results.id`
- Check `imperium_weekly_review_final_reports_status_check` :
  `draft`, `approved`, `stored`, `superseded`
- Index : `imperium_weekly_review_final_reports_user_status_idx` sur
  `(user_id, status)`
- Index : `imperium_weekly_review_final_reports_user_week_idx` sur
  `(user_id, week_start)`
- Index unique partiel : `uq_wr_final_reports_active_session` sur
  `session_id` WHERE `status IN ('draft', 'approved', 'stored')`
- Index unique partiel : `uq_wr_final_reports_active_user_week` sur
  `(user_id, week_start)` WHERE `status IN ('draft', 'approved', 'stored')`

Notes migration/ORM :
- Divergence de nommage : la table codee reste
  `imperium_weekly_review_final_reports`; le nom cible documente est
  `review_final_reports`.
- La migration 0013 creait deux contraintes uniques strictes :
  `session_id` unique et `(user_id, week_start)` unique. La migration 0014 les
  remplace par des index uniques partiels pour autoriser l'historique des
  candidats `superseded`.
- Le modele ORM est aligne sur les index partiels courants.
- La migration met `id` en default serveur `gen_random_uuid()` ; le mixin ORM
  genere aussi un UUID cote Python.
- Il n'existe pas de contrainte SQL qui impose que `week_start/week_end` soient
  identiques a ceux de la session. Cette coherence est portee par les services.

### review_states

Nom actuel : `imperium_weekly_review_states`
Nom cible : `review_states` (À CLARIFIER)
Source code : migration `20260427_0010_imperium_weekly_review_states.py`,
modele `backend/app/models/imperium.py::ImperiumWeeklyReviewState`

Role actuel : couche readiness/banniere WR au nom trompeur. Cette table a ete
codee avant la vraie machine conversationnelle WR. Elle porte `ready`,
`launched` et `analysis_status` pour l'affichage/dashboard, mais
`imperium_weekly_review_sessions` est la machine conversationnelle canonique.

À CLARIFIER au moment de coder/reprendre le WR : verifier ce que
`imperium_weekly_review_states` porte d'utile que `imperium_weekly_review_sessions`
n'a pas. Ne pas trancher maintenant. Ne pas renommer ni supprimer cette table
dans le code dans ce chantier documentaire.

Schema reel :

```text
id                     UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_id                UUID NOT NULL FK users.id ON DELETE CASCADE
week_start             DATE NOT NULL
ready                  BOOLEAN NOT NULL DEFAULT false
ready_at               TIMESTAMPTZ NULL
launched               BOOLEAN NOT NULL DEFAULT false
launched_at            TIMESTAMPTZ NULL
analysis_status        VARCHAR(32) NOT NULL DEFAULT 'pending'
analysis_completed_at  TIMESTAMPTZ NULL
created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `imperium_weekly_review_states.id`
- FK : `imperium_weekly_review_states.user_id -> users.id`
  avec `ON DELETE CASCADE`
- Unique : `imperium_weekly_review_states_user_week_start_unique` sur
  `(user_id, week_start)`
- Index : `imperium_weekly_review_states_user_week_start_idx` sur
  `(user_id, week_start)`
- Index partiel : `imperium_weekly_review_states_user_ready_true_idx` sur
  `(user_id, ready)` WHERE `ready = TRUE`

Notes migration/ORM :
- Divergence de nommage : la table codee reste
  `imperium_weekly_review_states`; le nom cible documente est `review_states`,
  mais son role est À CLARIFIER.
- La migration met `id` en default serveur `gen_random_uuid()` ; le mixin ORM
  genere aussi un UUID cote Python.
- `week_start` est valide cote service comme un lundi. Il n'existe pas de check
  SQL qui impose le lundi.
- `analysis_status` n'a pas de check SQL. Le code ecrit notamment `pending` et
  `running`.
- Cette table ne contient pas `week_end`, pas de pointeurs `ai_tasks` /
  `ai_results`, pas les statuts riches de conversation, et pas de liens vers les
  rapports finaux. Ces attributs vivent dans `review_sessions` /
  `review_final_reports`.

### review_memory_decisions

Nom actuel : `imperium_memory_candidate_decisions`
Nom cible : `review_memory_decisions`
Source code : migration `20260501_0015_memory_candidate_decisions.py`, modele
`backend/app/models/imperium.py::ImperiumMemoryCandidateDecision`

Role : decisions utilisateur/backend issues de la reflexion WR sur des
candidats memoire. Cette table garde une valeur haute : elle ne doit pas devenir
un log memoire banal. Elle enregistre si un candidat issu d'un rapport WR est
approuve, rejete ou edite, avec la version originale et la version eventuellement
editee.

Schema reel :

```text
id                  UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_id             UUID NOT NULL FK users.id
report_id           UUID NOT NULL FK imperium_weekly_review_final_reports.id ON DELETE CASCADE
session_id          UUID NOT NULL FK imperium_weekly_review_sessions.id ON DELETE CASCADE
candidate_id        TEXT NOT NULL
decision            TEXT NOT NULL
source              TEXT NOT NULL DEFAULT 'weekly_review'
original_candidate  JSONB NOT NULL
edited_candidate    JSONB NULL
reason              TEXT NULL
payload             JSONB NULL
idempotency_key     TEXT NULL
created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `imperium_memory_candidate_decisions.id`
- FK :
  `imperium_memory_candidate_decisions.report_id -> imperium_weekly_review_final_reports.id`
  avec `ON DELETE CASCADE`
- FK :
  `imperium_memory_candidate_decisions.session_id -> imperium_weekly_review_sessions.id`
  avec `ON DELETE CASCADE`
- FK : `imperium_memory_candidate_decisions.user_id -> users.id`
- Unique : `uq_mem_candidate_decision_user_report_candidate` sur
  `(user_id, report_id, candidate_id)`
- Check `imperium_memory_candidate_decisions_decision_check` :
  `approved`, `rejected`, `edited`
- Check `imperium_memory_candidate_decisions_source_check` :
  `source IN ('weekly_review')`
- Index : `imperium_memory_candidate_decisions_user_created_idx` sur
  `(user_id, created_at DESC)` dans la migration
- Index : `imperium_memory_candidate_decisions_user_decision_idx` sur
  `(user_id, decision)`
- Index : `imperium_memory_candidate_decisions_report_idx` sur `report_id`
- Index : `imperium_memory_candidate_decisions_session_idx` sur `session_id`
- Index : `imperium_memory_candidate_decisions_candidate_idx` sur
  `candidate_id`

Notes migration/ORM :
- Divergence de nommage : la table codee reste
  `imperium_memory_candidate_decisions`; le nom cible documente est
  `review_memory_decisions`.
- La migration met `id` en default serveur `gen_random_uuid()` ; le mixin ORM
  genere aussi un UUID cote Python.
- Divergence migration/ORM : la migration cree
  `imperium_memory_candidate_decisions_user_created_idx` avec `created_at DESC`,
  tandis que le modele ORM declare l'index sur `(user_id, created_at)` sans
  ordre explicite.
- Il n'existe pas de contrainte SQL qui impose que `report_id`, `session_id` et
  `user_id` appartiennent au meme utilisateur/session. Cette coherence est
  portee par les services.

Point critique D5 :
- Les commits memoire WR sont BLOQUÉS jusqu'a correction de `ai_memories` au
  schema canonique du present doc 05 et des docs 09/75. Le code contient encore
  un chemin de commit WR vers `ai_memories`; ce chemin est NON CONFORME tant que
  `ai_memories` garde le schema actuel (`source_module`, `kind`, `scope`,
  pointeurs WR, etc.).
- A rebrancher seulement apres correction de `ai_memories`. Ordre verrouille :
  bloquer les commits memoire WR, corriger `ai_memories`, rebrancher le commit
  WR, puis durcir les fallback candidates.
- `review_memory_decisions` conserve sa valeur propre : decisions issues de la
  reflexion WR. Ce n'est ni un simple log d'ecriture memoire ni un substitut a
  `ai_memories`.

Invariants metier WR reintegres :
- Le WR est backend-owned. L'app affiche et collecte ; n8n orchestre seulement
  des taches preparees/signees ; les modeles IA retournent des propositions via
  le backend. Aucun modele, n8n workflow ou frontend ne doit ecrire directement
  PostgreSQL.
- Fenetre temporelle : `week_start` doit etre un lundi. La fenetre metier est
  stricte de 7 jours en timezone Europe/Paris, du lundi au dimanche inclus pour
  l'utilisateur. Pour les requetes temporelles, la borne technique recommandee
  est demi-ouverte `[week_start, week_start + 7 jours)` afin d'eviter les erreurs
  de precision ; la colonne `week_end` stocke la date affichee du dimanche
  (`week_start + 6 jours`).
- Activation : chaque mardi a 20h Europe/Paris, la banniere WR passe de
  passive a active. Cette regle doit etre backend-enforced. n8n n'est pas
  proprietaire de cette activation.
- Machine d'etat : `review_sessions` est la source canonique de l'etat
  conversationnel. Les statuts fermes/terminaux empechent les mutations
  ordinaires ; `stored`, `cancelled` et `failed` ferment la session. `approved`
  represente une approbation utilisateur, mais `approved != stored`.
- Cycle validation -> stockage : un resultat IA, un draft ou un final candidate
  n'est jamais canonique automatiquement. Le cycle attendu est :
  proposition IA -> conversation utilisateur -> candidat draft/final ->
  approbation explicite -> stockage explicite. Le stockage WR V1 marque le
  rapport comme `stored`; il ne cree pas de memoire vectorielle tant que D5 n'est
  pas resolu.
- Historique des candidats : les drafts/revisions doivent conserver un trail de
  versions. Les anciens candidats passent en `superseded`; un seul candidat
  actif (`draft`, `approved` ou `stored`) est autorise par session et par
  utilisateur/semaine.
- Trail de regles : les regles utilisees pour produire, reviser, approuver et
  stocker un WR doivent rester tracables via les payloads, rapports, statuts,
  decisions et idempotency keys. Quand les prompts/regles evoluent, la version
  applicable doit etre visible dans les payloads ou dans un champ dedie futur,
  pas implicite dans le code.

## CALENDAR

Tables calendar :
`imperium_calendar_events` (canonique actuel, nom cible `calendar_events`).

Regle de lecture pour cette section :
- Le module Calendar code aujourd'hui est la fondation minimale Patch 7H :
  stockage backend-owned de contraintes calendrier, creation/liste/suppression
  manuelles et validation deterministe.
- Le nom cible documentaire est `calendar_events`, conforme a la convention D1 :
  prefixe de domaine, pas nom d'application.
- Ce document ne renomme aucune table dans le code.
- Le Calendar complet du doc 51 est V3 FUTUR / NON CODE. Ses champs/tables ne
  deviennent pas schema canonique tant qu'un chantier dedie ne les implemente
  pas.

### calendar_events

Nom actuel : `imperium_calendar_events`
Nom cible : `calendar_events`
Source code : migration
`20260512_0022_imperium_calendar_events_foundation.py`, modele
`backend/app/models/imperium.py::ImperiumCalendarEvent`

Role : fondation Calendar V1 minimale et deterministe. La table stocke des
evenements/deadlines/vacances manuels appartenant a l'utilisateur courant, pour
que le backend puisse disposer plus tard de contraintes calendaires sans
inventer un stockage sous pression.

Schema reel :

```text
id           UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_id      UUID NOT NULL FK users.id
event_type   TEXT NOT NULL
title        TEXT NOT NULL
starts_at    TIMESTAMPTZ NOT NULL
ends_at      TIMESTAMPTZ NULL
blocks_time  BOOLEAN NOT NULL DEFAULT true
location     TEXT NULL
notes        TEXT NULL
created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `pk_imperium_calendar_events` sur `id`
- FK : `fk_imperium_calendar_events_user_id_users`,
  `imperium_calendar_events.user_id -> users.id`
- Check SQL rendu
  `ck_imperium_calendar_events_imperium_calendar_events_event_type_check`
  (nom logique ORM `imperium_calendar_events_event_type_check`) :
  `event_type IN ('event', 'deadline', 'vacation')`
- Check SQL rendu
  `ck_imperium_calendar_events_imperium_calendar_events_date_range_check`
  (nom logique ORM `imperium_calendar_events_date_range_check`) :
  `ends_at IS NULL OR ends_at >= starts_at`
- Index : `imperium_calendar_events_user_starts_at_idx` sur
  `(user_id, starts_at)`
- Index : `imperium_calendar_events_user_event_type_idx` sur
  `(user_id, event_type)`

Regles metier Calendar Patch 7H :
- Le module est deterministe. Il ne planifie pas, ne score pas, ne replanifie
  pas et ne demande pas a l'IA de choisir une strategie.
- Les seuls `event_type` codes sont `event`, `deadline` et `vacation`.
- La creation est manuelle via `POST /api/imperium/calendar/events` et requiert
  `Idempotency-Key`.
- La creation est user-scoped et cree aussi un event canonique
  `calendar.event.created` dans `events` avec `privacy_level = medium`.
- La liste `GET /api/imperium/calendar/events` est user-scoped, triee par
  `starts_at ASC, created_at ASC`, et accepte les filtres `from`, `to` et
  `event_type`.
- Le filtre `to` ne peut pas etre inferieur a `from`.
- La suppression `DELETE /api/imperium/calendar/events/{event_id}` est
  user-scoped. Elle supprime physiquement la ligne calendar en V1. Elle ne cree
  pas d'event `calendar.event.deleted` et ne requiert pas d'idempotency key.
- `ends_at` peut etre nul ; s'il est fourni, il doit etre superieur ou egal a
  `starts_at`.
- `blocks_time` vaut `true` par defaut. La table ne deduit pas encore les
  conflits ou indisponibilites dans le daily plan.
- Aucun champ de recurrence, statut, deadline specialisee, geo precise,
  urgence, impact applicatif, override d'occurrence ou synchronisation externe
  n'existe dans le schema code actuel.

Non-objectifs explicites de la fondation 7H :
- Pas de recurrence fields, pas de moteur de recurrence et pas de RRULE en V1.
- Pas d'automatic replanning, pas d'AI scheduling, pas d'appel IA, pas de n8n AI
  Agent, pas d'ecriture DB par n8n.
- Pas d'ecriture pgvector, pas d'embeddings et pas de commit memoire
  automatique.
- Pas de notifications.
- Pas de sync Google/Apple/Samsung calendar.
- Pas d'implementation mobile/frontend dediee.

Notes migration/ORM :
- Divergence de nommage : la table codee reste `imperium_calendar_events`; le
  nom cible documente est `calendar_events`.
- Divergence mineure : la migration met `id` en default serveur
  `gen_random_uuid()`, tandis que le mixin ORM genere aussi un UUID cote Python.
- `blocks_time`, `created_at` et `updated_at` ont des defaults serveur en
  migration et en ORM. `updated_at` porte en plus `onupdate=func.now()` cote
  ORM.
- Les colonnes, types, nullabilites, FK, checks et index sont alignes entre la
  migration 0022 et le modele ORM.
- Les noms de checks apparaissent en ORM sous leur nom logique court, puis sont
  rendus avec la convention SQLAlchemy (`ck_<table>_<name>`) dans la migration.

Capacites Calendar futures / non codees :
- Calendar V3 complet : FUTUR / NON CODE. Le doc 51 annonce un calendrier
  personnel structure qui informe les decisions du cerveau, mais il n'est pas
  implemente par la fondation 7H.
- Types futurs annonces : `periode_bloquee` et `evenement_religieux` sont V3 /
  NON CODES dans cette table. Le calendrier religieux Path reste un domaine
  specifique separe et ne doit pas etre cache dans le schema minimal actuel.
- Schema V3 riche : FUTUR / NON CODE. Le doc 51 annonce notamment
  `precisions`, `deadline_at`, `estimated_duration_min`, `urgency`,
  `location_name`, `location_lat`, `location_lng`, impacts applicatifs
  (`pause_vtc`, `pause_pulse`, `pause_path`), `status`, `cancelled_at` et
  champs de recurrence. Ces colonnes n'existent pas aujourd'hui.
- Recurrence avancee : FUTUR / NON CODE. Le doc 51 annonce des recurrences
  daily/weekly/monthly/yearly/custom, stockage interne au format RFC 5545
  RRULE, dates sautees, limite de recurrence et overrides par occurrence.
- `calendar_event_overrides` : FUTUR / NON CODE. Le doc 51 donne une table
  cible pour skip/reschedule/modify d'occurrences, mais aucune migration ni
  modele ne l'implemente aujourd'hui.
- Seuil 7 jours, hooks et replanning : FUTUR / NON CODE. Le doc 51 annonce des
  hooks `user.calendar.*`, une reevaluation quand un evenement entre dans la
  fenetre de 7 jours, et une consommation par le daily plan. La V1 codee stocke
  seulement les contraintes.
- WR integration : FUTUR / NON CODE. Le doc 51 annonce que le Weekly Review
  pourra interroger et mettre a jour le calendrier ; aucun flux WR calendar
  n'est code dans le schema actuel.
- Notifications/rappels : FUTUR / NON CODE. La fondation 7H les exclut
  explicitement.
- Sync externe/native calendar : NON CODE et non canonique pour V3 selon le doc
  51. La fondation 7H exclut Google/Apple/Samsung calendar sync, et le principe
  V3 annonce un calendrier propre au systeme plutot qu'une integration native.
