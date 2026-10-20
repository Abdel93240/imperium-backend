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
depth                  INTEGER NULL
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
- Check : `ck_events_depth_positive_check` (`depth IS NULL OR depth >= 1`)
- Index : `events_user_event_type_occurred_idx` sur
  `(user_id, event_type, occurred_at)`
- Index : `events_user_correlation_idx` sur `(user_id, correlation_id)`
- Index : `events_causation_id_idx` sur `causation_id`
- Trigger append-only : `events_append_only_guard` interdit UPDATE/DELETE
- Trigger append-only : `events_append_only_truncate_guard` interdit TRUNCATE
- Contract read V1 : no projections, no cross-module writes, strict CurrentUserDep,
  no user_id exposed ; les endpoints exposent la forme publique
  documentee, sans `user_id` dans les responses.

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

### ai_call_logs et ai_model_pricing

CODE (migration 20261019_0086, 2026-10-19, doc 43 §17.1-§17.4 ; doc 78 F2-14). Colonnes du
doc 43 §17.1 (sans `user_id` : journal systeme), index §17.1, fonction
`compute_ai_call_cost` + trigger `ai_call_logs_auto_cost` (§17.3), vues `ai_monthly_by_model`,
`ai_monthly_by_app`, `ai_monthly_by_task`, `ai_daily_spend` (§17.4 ; jour Europe/Paris).
Une ligne par appel reel de modele, ecrite par `app/services/ai/call_log.py` dans sa propre
session (survit au rollback de l'appelant, ne casse jamais l'appel) : executant local, OCR et
vision, embeddings. Jamais de prompt, de reponse ni de texte reconnu. Le dry-run n'ecrit rien.
`model_used` = identifiant reel resolu par role (`ai_role_models`), le code du role a defaut.
Cout : 0 en local ; sinon calcule par le trigger depuis `ai_model_pricing`, NULL sans prix.
`ai_model_pricing` nait VIDE : le seed historique du doc 43 §17.2 est perime (DV-8), la grille
reste a fournir. Lecture : `GET /api/ai/call-logs?limit=`, `GET /api/ai/call-logs/daily?days=`.
Vues 5 a 10 du §17.4 (`ai_hallucination_tracker`, `ai_error_analysis`, `ai_latency_profile`,
`ai_6month_trend`, `ai_fallback_effectiveness`, `ai_vs_estimates`) : CODE (migration
20261019_0087). Seuils §17.6 en parametres `ai.alert_*` (defauts du doc ; ajout
`ai.alert_error_min_calls` = 20 et `ai.alert_hallucination_min_checked` = 10, a valider) ;
`GET /api/ai/call-logs/alerts` (lecture seule) ; job horaire `ai.call_alerts` seme desactive :
une notification `normal`/`system` par seuil et par jour de Paris, rien n'est coupe ni reroute.
Requetes manuelles §17.5 : non codees (requetes ad hoc).

### ai_slot_transition et ai_audit_samples

Tables partagees du socle (migration 20260715_0038, spec WR §3.7 ; doc 78 F1-13, F2-09).
`ai_slot_transition` : une ligne par slot IA (registre + tier `local_default|cloud_forced|routed`,
`audit_sample_pct`, `agreement_target_pct`, `version`). Migration 20261019_0088 : 10 slots WR
(spec WR §10) et 2 slots Daily (spec Daily §13) semes, audit 100 %, cible 92 %.
`ai_audit_samples` : une contre-lecture cloud d'une sortie locale ; 0088 ajoute `cloud_model`,
`disagreement_class` (label du futur dataset) et l'unicite partielle (`slot_code`, `run_ref`).
Vue `v_ai_slot_agreement_weekly` : echantillons et agreement par slot et semaine de Paris ;
`v_ai_training_pairs` (0038) : desaccords. Le code (`app/services/ai/audit_loop.py`) tire
l'echantillon de facon deterministe, enregistre les resultats et PROPOSE une decroissance ;
seul l'utilisateur la decide (`POST /api/wr/admin/transition`, event `decision.ai_audit.updated`).
Le tier ne change jamais par cette route. Aucune contre-lecture cloud n'est branchee.

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
`finance_transactions`), `upcoming_expenses`, `weekly_finance_summaries` et
`pressure_snapshots`. `vault_transactions` est un legacy archivé puis droppé par
la migration Phase E `20260716_0040`; il ne doit plus être lu ni écrit.

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
`20260525_0026_imperium_vault_local_date_timezone.py`,
`20260710_0037_imperium_vault_wallet.py`, modele
`backend/app/models/vault.py::ImperiumVaultTransaction`

Role : ledger finance canonique. Montants en cents, append-only, corrections par
reversal. Le wallet est conserve dans le canonique comme texte ouvert.

Schema reel :

```text
id                          UUID PRIMARY KEY
user_id                     UUID NOT NULL FK users.id
transaction_type            TEXT NOT NULL
amount_cents                INTEGER NOT NULL
currency                    TEXT NOT NULL DEFAULT 'EUR'
wallet                      TEXT NOT NULL DEFAULT 'cash'
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
- Aucune CheckConstraint fermee sur `wallet`. Valeurs applicatives de base :
  `cash`, `bank`; la colonne reste extensible pour crypto/comptes futurs sans
  migration de contrainte.
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
- Vault ledger is append-only ; transactions are immutable.
- Aucune correction par UPDATE ou DELETE. Les corrections s'ecrivent par ajout
  d'une ligne de reversal via
  `POST /api/imperium/vault/transactions/{transaction_id}/reverse`.
- No PUT/PATCH/DELETE endpoint is allowed for `/api/imperium/vault/transactions`.
- Corrections must be written by appending a reversal row through `POST /api/imperium/vault/transactions/{transaction_id}/reverse`.
- The original transaction must never be updated or deleted.
- The reversal transaction is a new row linked to the original transaction.
- Une reversal est une nouvelle transaction liee a l'originale par
  `reversal_of_transaction_id`.
- Une transaction originale ne peut avoir qu'une seule reversal. Cette regle est
  portee par le service et par l'index unique partiel ajoute en patch 9f/9g.
- Patch 9f/9g allow one and only one reversal per original transaction.
- Une ligne de reversal ne peut pas etre reversee a son tour.
- `occurred_at` est la seule source temporelle autoritative pour les summaries,
  filtres et regroupements finance V1. La semantique temporelle de V1 est UTC.
- `local_date` et `timezone` servent de convention de date utilisateur. La
  convention par defaut produit attendue est `Europe/Paris`; une date fournie en
  query/payload peut surcharger cette convention selon le contrat d'endpoint.
- `currency` accepte exactement 3 lettres ASCII et est normalisee en majuscule
  par les schemas API. V1 ne valide pas l'existence ISO-4217 de la devise.
- `wallet` est un texte ouvert, normalise/controle cote applicatif. Les valeurs
  de base sont `cash` et `bank`, mais la base n'enferme pas la liste.
- Les montants declares en euros par les anciennes surfaces Vault sont convertis
  en centimes avant insertion canonique. Les affichages legacy reconvertissent
  `amount_cents` en euros.
- Le type `correction` n'existe pas dans le canonique. Les annulations sont des
  transactions inverses liees a l'originale par `is_reversal`,
  `reversal_of_transaction_id` et `reversal_reason`.
- Les summaries comptent les reversals dans income/expense selon leur sens et
  exposent separement leur total et leur compteur pour eviter toute boite noire.
- Les endpoints de creation et de reversal exigent `Idempotency-Key`.
- Les endpoints finance sont scopes par l'utilisateur courant.
- Les endpoints de summary partagent le meme contrat de devise. Une devise
  inconnue ou inutilisee sans transaction retourne des totaux a zero, sans
  masquer une erreur de validation.

Notes migration/ORM :
- La migration ne met pas de default serveur sur `id`; le mixin ORM genere un
  UUID cote Python.
- `currency`, `wallet` et `is_reversal` ont des defaults serveur en migration et des
  defaults Python equivalents en ORM.
- `created_at` et `updated_at` ont des defaults serveur en migration ; le modele
  declare aussi `server_default=func.now()`. `updated_at` porte en plus
  `onupdate=func.now()` cote ORM, mais la regle metier interdit de modifier les
  transactions apres insert. `updated_at` remains a generic row timestamp.
- Trigger append-only : `imperium_vault_transactions_append_only_guard`
  interdit UPDATE/DELETE.
- Trigger append-only : `imperium_vault_transactions_append_only_truncate_guard`
  interdit TRUNCATE.
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
- Les anciens lecteurs directs `backend/app/services/imperium/dashboard.py` et
  `backend/app/services/imperium/weekly_report.py` lisent aussi le canonique.
- `backend/app/api/v1/routes/vault.py` ne porte plus les transactions legacy ;
  il expose uniquement les surfaces Phase E : pression, dépenses à venir et
  résumés hebdomadaires.

### upcoming_expenses

Source code : migrations `20260716_0040_vault_deterministic_phase_e.py`,
`20260716_0041_vault_phase_e_user_scope.py`, modèle
`backend/app/models/vault.py::UpcomingExpense`.

Role : source de vérité utilisateur pour les dépenses à venir et récurrentes
utilisées par la pression financière et les notifications J-7/J-1.

```text
id          UUID PRIMARY KEY
user_id     UUID NOT NULL FK users.id
label_fr    TEXT NOT NULL
amount      NUMERIC(12,2) NOT NULL CHECK amount > 0
due_date    DATE NOT NULL
recurrence  TEXT NULL CHECK null|monthly|quarterly|yearly
category    TEXT NOT NULL
wallet      TEXT NULL
mandatory   BOOLEAN NOT NULL DEFAULT true
active      BOOLEAN NOT NULL DEFAULT true
created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
```

Index : `upcoming_expenses_due_active_idx`,
`upcoming_expenses_user_active_due_idx`, `upcoming_expenses_category_idx`.

### weekly_finance_summaries

Source code : migrations `20260716_0040_vault_deterministic_phase_e.py`,
`20260716_0041_vault_phase_e_user_scope.py`, modèle
`backend/app/models/vault.py::WeeklyFinanceSummary`.

Role : résumé hebdomadaire déterministe Vault. `weekly_business_profit` est le
champ lu par The Path pour la cible sadaqa.

```text
user_id                 UUID NOT NULL FK users.id
week_start              DATE NOT NULL
business_revenue        NUMERIC(12,2) NOT NULL
business_expenses       NUMERIC(12,2) NOT NULL
weekly_business_profit  NUMERIC(12,2) NOT NULL
personal_expenses       NUMERIC(12,2) NOT NULL
computed_at             TIMESTAMPTZ NOT NULL
detail                  JSONB NOT NULL
```

Primary key : `(user_id, week_start)`.

### pressure_snapshots

Source code : migrations `20260716_0040_vault_deterministic_phase_e.py`,
`20260716_0041_vault_phase_e_user_scope.py`, modèle
`backend/app/models/vault.py::PressureSnapshot`.

Role : historique append-only de la pression financière 0-100. Chaque calcul
publie aussi le signal partagé `vault.pressure` et l'événement
`finance.pressure.updated`.

```text
id               UUID PRIMARY KEY
user_id          UUID NOT NULL FK users.id
computed_at      TIMESTAMPTZ NOT NULL
score            INTEGER NOT NULL CHECK score BETWEEN 0 AND 100
label            TEXT NOT NULL CHECK safe|stable|attention|pressure|critical
factors          JSONB NOT NULL
daily_targets    JSONB NOT NULL
inputs_snapshot  JSONB NOT NULL
```

Guards : `pressure_snapshots_append_only_guard` interdit UPDATE/DELETE et
`pressure_snapshots_append_only_truncate_guard` interdit TRUNCATE.

### vault_transactions

Statut Phase E : table legacy archivée puis supprimée.

- Archive préalable :
  `backend/db_archives/20260716_vault_transactions_pre_drop.pg_dump.sql`.
- Drop : migration `20260716_0040_vault_deterministic_phase_e.py`.
- Modèle ORM actif : aucun.
- Routes legacy `/api/vault/transactions`, `/api/vault/transactions/recent` et
  `/api/vault/summary/week` : supprimées.
- Ledger actif inchangé : `imperium_vault_transactions` via
  `/api/imperium/vault/transactions` et reversals append-only.

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
- Cadre retenu (decision utilisateur 2026-10-17, CODE migration 20261017_0061, doc 08
  PULSE-004) : consentement explicite par domaine body|pain|medical, texte versionne,
  date, retirable (`pulse_health_consents`) ; sans consentement actif, ecriture refusee
  (403 CONSENT_REQUIRED) ; aucune photo cote serveur ; evenements sans mesure (identifiants
  seulement, privacy high) ; lecture et suppression reelle toujours ouvertes a
  l'utilisateur ; retention = jusqu'a suppression par l'utilisateur ; acces limite au
  proprietaire. Chiffrement : celui du disque et des sauvegardes (ops), pas de chiffrement
  par colonne en V1.
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
- Repas : CODE, table `pulse_meals` (voir plus bas, migration 20261017_0056).
- Hydratation : CODE, table `pulse_hydration_logs` (voir plus bas, migration 20261017_0058).
- Food stock / stock alimentaire : FUTUR / NON CODE. Schema a definir au moment
  du chantier stock.
- Workouts : CODE, table `pulse_workouts` (voir plus bas, migration 20261017_0059).
- Pain logs : CODE, table `pulse_pain_logs` (voir plus bas, migration 20261017_0062),
  sous consentement « pain ».
- Body snapshots : CODE, table `pulse_body_snapshots` (voir plus bas, migration
  20261017_0061), sous consentement « body ». Profils biologiques : FUTUR / NON CODE.
- Health scores : FUTUR / NON CODE. Aucun score sante n'est calcule ou stocke
  par la V1 codee.
- Medical documents et medical rules : CODE, tables `pulse_medical_documents` et
  `pulse_medical_rules` (voir plus bas, migration 20261017_0063), sous consentement
  « medical ».
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
failure_reason_code     TEXT NULL   -- CODE (migration 20261017_0043) : no_time | too_tired | not_relevant | impediment (doc 52 §10)
estimated_minutes       INTEGER NULL -- CODE (20261017_0043) : > 0 (doc 43 §5.2)
deadline_at             TIMESTAMPTZ NULL -- CODE (20261017_0044) : échéance ; dépassée à la clôture → standby (doc 43 §5.4)
annex_of_mission_id     UUID NULL FK imperium_missions.id ON DELETE SET NULL -- CODE (20261017_0043) : annexe V1 (doc 53 §3.1), <> id
user_reported_signals   JSONB NULL
ai_usable_reason        BOOLEAN NULL
created_by_event_id     UUID NULL FK events.id
ended_by_event_id       UUID NULL FK events.id
replan_event_id         UUID NULL FK planning_replan_events.id ON DELETE SET NULL -- CODE (20261018_0082) : replan demandé depuis la mission ratée ou annulée (doc 43 §3.1)
location_lat            NUMERIC(9,6) NULL -- CODE (20261019_0104) : lieu (spec Daily §3.2), lat/lng ensemble ou aucun
location_lng            NUMERIC(9,6) NULL
location_label          TEXT NULL
window_start            TIME NULL -- CODE (20261019_0104) : fenêtre d'exécution (Paris), window_start < window_end ; null = libre
window_end              TIME NULL
window_days             TEXT[] NULL -- CODE (20261019_0104) : ⊂ {mon..sun} ; null = tous les jours
is_fixed_commitment     BOOLEAN NOT NULL DEFAULT false -- CODE (20261019_0104) : rendez-vous à heure fixe, borne le temps restant (porte G4)
fixed_at                TIMESTAMPTZ NULL -- requis si is_fixed_commitment
physical_load           INTEGER NULL -- CODE (20261019_0104) : 1-5, lu par la porte Pulse G5 (stub en V28)
cognitive_load          INTEGER NULL -- 1-5
created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
```

Contraintes et index :
- PK : `imperium_missions.id`
- FK : `imperium_missions.user_id -> users.id`
- FK : `imperium_missions.created_by_event_id -> events.id`
- FK : `imperium_missions.ended_by_event_id -> events.id`
- FK : `imperium_missions.replan_event_id -> planning_replan_events.id` (SET NULL)
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

### planning_days

Nom actuel : `planning_days`
Nom cible : `planning_days` (conforme au domaine planning, sans prefixe
d'application)
Source code : migration `20260923_0042_planning_days.py`, modele
`backend/app/models/imperium.py::PlanningDay`

Role : porter la journee operationnelle explicite d'Imperium. Une journee est
ouverte par l'action utilisateur « Demarrer la journee », reste rattachee a sa
date civile de depart meme apres minuit, puis est fermee par « Finish Day ».
`finished_at IS NULL` signifie que la journee est ouverte.

Schema reel :

```text
id                UUID PRIMARY KEY
user_id           UUID NOT NULL FK users.id
started_at        TIMESTAMPTZ NOT NULL
finished_at       TIMESTAMPTZ NULL
start_local_date  DATE NOT NULL
timezone          TEXT NOT NULL
felt_energy       SMALLINT NOT NULL
day_review_id     UUID NULL FK imperium_day_reviews.id
created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
idempotency_key   TEXT NOT NULL
```

Contraintes et index :
- PK : `planning_days.id`
- FK : `planning_days.user_id -> users.id`
- FK : `planning_days.day_review_id -> imperium_day_reviews.id`
- Check `ck_planning_days_felt_energy_range` :
  `felt_energy >= 1 AND felt_energy <= 5`
- Check `ck_planning_days_finished_after_started` :
  `finished_at IS NULL OR finished_at >= started_at`
- Unique : `planning_days_user_idempotency_key_unique` sur
  `(user_id, idempotency_key)`
- Index unique partiel : `planning_days_one_open_per_user_idx` sur `user_id`
  WHERE `finished_at IS NULL`
- Index : `planning_days_user_started_at_idx` sur `(user_id, started_at)`

Regles metier planning :
- Une seule journee operationnelle peut etre ouverte par utilisateur. Le
  service retourne `409` et l'index partiel protege aussi les courses
  concurrentes.
- `start_local_date` est calculee au demarrage dans le fuseau canonique
  `Europe/Paris`. Elle devient la reference de « aujourd'hui »
  jusqu'a la cloture, y compris si la journee depasse minuit.
- `felt_energy` est le ressenti subjectif court du check-in de demarrage ; il
  ne remplace pas les futurs signaux objectifs d'energie.
- La cloture remplit `finished_at` et `day_review_id` dans la meme transaction
  que la creation de `imperium_day_reviews` et de l'event canonique.
- `idempotency_key` rattache le demarrage a la mutation idempotente. Les
  reessais sont aussi gardes par la table technique `idempotency_keys`.

Notes migration/ORM :
- La migration ne met pas de default serveur sur `id`; le mixin ORM genere un
  UUID cote Python.
- `created_at` et `updated_at` ont des defaults serveur ; `updated_at` porte
  aussi `onupdate=func.now()` cote ORM.
- La migration est reversible et son downgrade supprime d'abord les index,
  puis la table.

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
- La table `planning_daily_plan_versions` est CODEE (2026-10-18, migration 0080) avec le
  schema du doc 43 §20 : chaque replan accepte cree une nouvelle version avec sa raison et
  archive l'ancienne ; elle pourra nourrir l'apprentissage futur.
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
  `expired`, `stashed` et l'overlay V3 (doc 53 hors §3.1) restent hors schema
  code actuel. CODE (migration 20261017_0043, 2026-10-17) : colonnes
  `annex_of_mission_id` (annexes V1 allegees, doc 53 §3.1), `estimated_minutes` (doc 43 §5.2)
  et `failure_reason_code` (doc 52 §10) sur `imperium_missions` ; le reste de l'overlay reste V3.
  CODE (migration 20261017_0044) : statut `standby` (echeance depassee
  constatee a la cloture de journee, attend une decision, doc 43 §5.4) et
  colonne `deadline_at`.
- Les projets actifs et routines d'Operations sont la source de missions ; leurs
  tables canoniques sont codees (`imperium_projects`, `imperium_routines`,
  `imperium_routine_checks`, migration 20261017_0047). La regle
  documentee par la doc 71 est V1 cible : viser deux projets actifs quand la
  pile le permet, garder une liste non-active distincte, auto-promouvoir apres
  completion et rendre un projet incomplet inerte en "Attention requise".
- Les routines sont codees (doc 71 §4.1). Leur branchement sur l'arbitrage et le
  daily plan (placement automatique des routines non quotidiennes) reste a faire
  par le planificateur ; V1 expose `POST /routines/{id}/place` pour ce placement.
- Le bilan de journee (`planning_day_reviews`) sert a expliquer ce qui s'est
  passe : victoires, problemes, items manques, fatigue, humeur et signaux. Il
  ne remplace pas l'historique de missions ni les events.

Nourrir l'IA (CODE, migration 20261017_0050, doc 70 §10.1) :
- `knowledge_inbox_items` (element : contexte, statut, brouillon / version validee,
  destination) et `knowledge_inbox_documents` (sources conservees, sha256, pointeur
  relatif a KNOWLEDGE_INBOX_STORAGE_DIR). Memoires : ai_memories.memory_type
  `user_knowledge`, source_table `knowledge_inbox_items`.

Justificatifs du Vault (CODE, migration 20261017_0051, doc 37 §3.4) :
- `vault_receipt_extractions` : statut ready|failed|validated|cancelled, texte OCR
  brut, confiance, brouillon (jsonb), pointeur d'image relatif a
  VAULT_RECEIPTS_STORAGE_DIR, transaction_id (obligatoire une fois validated),
  Idempotency-Key unique par utilisateur.

Stock alimentaire Pulse (CODE, migration 20261017_0052, doc 40 §11) :
- `food_stock_items` : nom, quantite (> 0), unite piece|kg|g|l|cl|ml, expiry_type
  DLC|DDM|unknown, expiry_date, category, confidence, source
  manual|vault_receipt|pantry_scan|chatbot, source_ref (unique par utilisateur,
  receipt:{id}:{n} pour un ticket, scan:{id}:{n} pour un scan, chat:{id}:{n} pour un
  ajout par le chatbot), status active|consumed|removed, version (>= 1,
  migration 20261017_0053, verrou optimiste des modifications).

Scan du placard Pulse (CODE, migration 20261017_0055, doc 37 §5.4) :
- `pulse_pantry_scans` : statut ready|failed|validated|cancelled, empreinte et taille de
  la photo (jamais la photo), qualite, confiance, resume, proposition (jsonb : lignes
  add|update avec version du stock), avertissements, resultat, Idempotency-Key unique.

Repas Pulse (CODE, migration 20261017_0056, doc 40 §10) :
- `pulse_meals` : statut draft|confirmed|cancelled, libelle, description, source
  text|voice|photo|manual|chatbot, eaten_at, macros facultatives (>= 0), proposition de
  decompte (jsonb), avertissements, stock_decrement_applied, resultat (lignes de stock
  touchees), Idempotency-Key unique du brouillon + empreinte, cle et empreinte de la
  validation. Migration 20261017_0057 : confidence, macros_estimated, photo_sha256 (la
  photo du repas n'est jamais conservee).

Hydratation Pulse (CODE, migration 20261017_0058, doc 40 §12) :
- `pulse_hydration_logs` : amount_ml (1..5000), logged_at, source quick|manual|chatbot,
  stock_decrement_applied, resultat (reponse rejouee), Idempotency-Key unique + empreinte.

Seances de sport Pulse (CODE, migration 20261017_0059, doc 40 §13) :
- `pulse_workouts` : titre, statut planned|in_progress|completed|skipped, planned_at,
  duree prevue et reelle (1..600), intensite low|medium|high, intensity_score 1..10,
  exercices et materiel (jsonb), mission liee (FK imperium_missions, SET NULL),
  started_at, completed_at, etat au depart, notes, raison du saut, version (>= 1),
  Idempotency-Key unique + empreinte, cle et empreinte de la cloture.

Materiel possede Pulse (CODE, migration 20261017_0060, doc 40 §13-EQUIP) :
- `pulse_owned_equipment` : nom, cle de nom (sans accents ni casse, unique par
  utilisateur parmi les lignes actives), notes, statut active|removed, removed_at.

Consentement sante et releves corporels Pulse (CODE, migration 20261017_0061, doc 40 §14) :
- `pulse_health_consents` : domaine body|pain|medical, version du texte accepte,
  granted_at, revoked_at ; un seul consentement actif par domaine (index unique partiel).
- `pulse_body_snapshots` : measured_at, poids (> 0), masse grasse (1..70 %), tours de
  taille, poitrine, bras, notes ; au moins une mesure ; aucune colonne photo ;
  Idempotency-Key unique + empreinte. Suppression reelle (DELETE).

Journal des douleurs Pulse (CODE, migration 20261017_0062, doc 40 §16) :
- `pulse_pain_logs` : zone (liste fermee), cote left|right|both, intensite 0..10, type,
  gene, impact sur la seance, seance liee (FK pulse_workouts, SET NULL), noted_at,
  resolved_at, Idempotency-Key unique + empreinte. Suppression reelle (DELETE).
  Migration 20261018_0077 : `replan_event_id` (sans FK) = replan demande depuis la douleur.

Prieres et jeune Path (CODE, migration 20261018_0064, doc 41 §7-§8) :
- `path_prayer_logs` : prayer_date, prayer_name fajr|dhuhr|asr|maghrib|isha, statut
  accomplished|not_marked_as_accomplished, prayed_at (accomplie seulement), note, version ;
  unique (user_id, prayer_date, prayer_name). Effacer le statut supprime la ligne.
  Idempotence par la table idempotency_keys.
- `path_fasts` : fasting_date (unique par utilisateur), type
  monday_thursday|white_days|ramadan|custom|temporary, statut active|ended|broken (un seul
  active par utilisateur, index partiel), started_at, suhoor_at < iftar_at (figes au
  demarrage), times_source mawaqit|calculated, hydration_daytime_allowed, ended_at,
  broken_at, break_reason, version, Idempotency-Key unique + empreinte.
- Remplacent les `prayer_logs` et `fasting_logs` annonces par le doc 41 §20 (jamais crees).

Invocations Path (CODE, migration 20261018_0078, doc 41 §11-bis) :
- `path_invocations` : situation (quotidien|voyage|protection|difficulte|maladie|peur_anxiete),
  arabic_text, translation_fr, source (obligatoires), audio_url https, is_favorite,
  daily_period morning|evening + daily_order (ensemble), version, Idempotency-Key + empreinte.
- `path_invocation_checks` : coche par invocation et jour de Paris (unique), cascade.

Reglages Path (CODE, migration 20261018_0076, PAT-11) :
- `path_settings` : une ligne par utilisateur (creee au premier changement) ; calculation_method
  MuslimWorldLeague|Karachi|Egypt|ISNA, madhhab Hanafi|Maliki|Shafii|Hanbali|Jafari, ville
  (city_name + latitude + longitude, tous ou aucun), version. Sans ligne : parametres globaux
  path.calc_method / path.madhhab et Paris.

Mosquees Path (CODE, migration 20261018_0075, PAT-09) :
- `path_registered_mosques` recoit `version`, `idempotency_key`, `request_hash`, une mosquee
  par defaut au plus par utilisateur (index partiel) et la paire latitude/longitude.

Corrections de pression (CODE, migration 20261018_0079, doc 11 « Manual Correction ») :
- `vault_pressure_corrections` (ajout seul, revoked_at) : kind postponed (postponed_until) |
  handled | exceptional_week (week_start, lundi), echeance cible (FK upcoming_expenses, SET NULL),
  raison obligatoire, Idempotency-Key + empreinte ; une correction active au plus par echeance
  et par semaine (index partiels). L'echeance d'origine n'est jamais modifiee.

Correction Vault (CODE, migration 20261018_0074, VAU-08) :
- `imperium_vault_transactions.corrects_transaction_id` (FK vers la meme table, unique quand
  renseigne) : la transaction corrigee pointe vers l'originale, annulee par ecriture inverse.

Soldes reels Vault (CODE, migration 20261018_0073, doc 42 §8) :
- `vault_wallet_snapshots` : cash (>= 0), banque (decouvert possible), crypto (>= 0) en
  centimes EUR, recorded_at, source manual|sync, note, Idempotency-Key unique + empreinte.
- `upcoming_expenses` recoit `paid_at` et `paid_transaction_id` (sans FK) : echeance payee
  via `POST /api/vault/upcoming-expenses/{id}/mark-paid`.

Sessions VTC Vector (CODE, migration 20261018_0069, domaine rides, doc 59 §14) :
- `rides_sessions` : statut active|completed (une seule active, index partiel), started_at,
  ended_at, CA cible (centimes), direction strategique, mission_id (FK imperium_missions,
  SET NULL), CA et depenses figes a la cloture, note de revue, version, Idempotency-Key.
  `replan_event_id` (migration 20261018_0081, sans FK) : replan Imperium demande apres la cloture.
- `rides_drop_zones` : depose confirmee (zone, latitude/longitude par paire, confiance GPS,
  duree reelle), FK rides_sessions (CASCADE), Idempotency-Key unique + empreinte.
- Revenus et depenses : `imperium_vault_transactions` (source vector_manual, external_ref
  `rides:{session}:{cle}`), jamais une table Vector.
- `rides_revenue_entries` (migration 20261018_0070) : contexte VTC d'un revenu de session
  (zone, cle de zone sans accents ni casse, montant, heure), transaction_id unique sans FK.
- `rides_offers` (migration 20261018_0071) : course proposee pendant une session (prix,
  distances, durees, zones, majoration, paiement, type, plateforme, source manual|ocr),
  variables calculees (JSONB), decision accepted|refused|missed + note, resultat reel
  (gain, minutes mobilisees, EUR/h en centimes, detail), revenue_transaction_id (sans FK),
  version, Idempotency-Key unique + empreinte.
- `rides_business_rules` et `rides_rule_revisions` (migration 20261018_0072) : regles metier
  par utilisateur (code unique, conditions JSONB, action red|green, active, ferme, compteur,
  version) et leurs revisions (type, raison, avant/apres, proposee par, validee) ;
  `rides_offers` recoit les codes postaux, `signal` green|red, source, raison, regles declenchees.
- `rides_recommendations` (migration 20261018_0070) : « Ou aller ? » ; stay_here|move_to_zone|
  abstain, zone, raison, confiance 0..1, entrees (creneau, zones comparees, contexte
  manquant), retour utilisateur (utile, action accepted|refused|missed|ignored, raison).

Calendrier hegirien Path (CODE, migration 20261018_0068, doc 41 14-V3) :
- `path_hijri_month_starts` : debut de mois confirme par l'utilisateur (annee 1300..1700,
  mois 1..12, first_day), unique (user_id, annee, mois).
- `path_calendar_events` : evenement religieux personnel (libelle, note, annee facultative =
  chaque annee, mois, jour 1..30), Idempotency-Key unique + empreinte.

Adhkar et Coran Path (CODE, migration 20261018_0067, doc 41 §11-§12) :
- `path_adhkar_routines` : libelle, type (liste du doc 41 §11), cible 1..10000, frequence
  daily|weekly|per_prayer, active (8 au plus, cote service), version, Idempotency-Key.
- `path_adhkar_counts` : compteur par routine et periode (`YYYY-MM-DD`, `week:<lundi>`,
  `YYYY-MM-DD:<priere>`), unique (routine_id, period_key), target_reached_at, reset_at.
- `path_adhkar_increments` : appuis (1..1000, tap|voice), cle unique par utilisateur,
  reponse gardee pour le rejeu.
- `path_quran_progress` : une ligne par utilisateur, derniere page validee 1..604, objectif
  quotidien, nombre de khatm, version.
- `path_quran_plans` : daily_pages|finish_in_days|juz_based, pages par jour, date de fin,
  page de depart, un seul actif (index partiel).
- Remplacent `adhkar_routines`, `adhkar_completions` et `quran_progression` du doc 41 §20.

Ghusl Path (CODE, migration 20261018_0066, doc 41 §10) :
- `path_ghusl_states` : une ligne par activation ; statut required|completed (un seul
  required par utilisateur, index partiel), required_since, completed_at, next_prayer,
  mission_id (FK imperium_missions, SET NULL), replan_event_id, replan_status
  pending|requested|no_open_day|replan_in_progress|failed, Idempotency-Key unique + empreinte.
- `path_ghusl_addresses` : libelle, type home|mosque|gym|work|other, adresse, latitude et
  longitude (par paire), is_default (une seule, index partiel), version,
  Idempotency-Key unique + empreinte. Remplace `registered_ghusl_addresses` du doc 41 §20.

Sadaqa Path (CODE, migration 20261018_0065, doc 41 §9) :
- `path_sadaqa_settings` : une ligne par changement ; percentage 0.01..0.20, safety_margin
  0.10..0.15, effective_from (lundi). Defauts 5 % et 12,5 % tant qu'aucune ligne.
- `path_sadaqa_donations` : amount_cents (1..10 000 000), destination, note, donated_at,
  related_week_start (lundi), allocation JSONB (carry|week_target|beyond_target),
  record_in_vault, wallet, vault_status not_requested|pending|recorded,
  vault_transaction_id (sans FK : le registre Vault garde son garde-fou en ajout seul),
  Idempotency-Key unique + empreinte. Suppression reelle.
- `path_sadaqa_weeks` : semaine close (PK user_id + week_start) : benefice, source,
  pourcentage, marge, base, report entrant, cible, dons, reste >= 0 (figes).
- Job `path.sadaqa_week_close` seme desactive (lundi 01:00 UTC).
- Remplacent `sadaqa_records` et `path_weekly_sadaqa_state` du doc 41 §20.

Medical Pulse (CODE, migration 20261017_0063, doc 34 §16-bis) :
- `pulse_medical_documents` : type (liste fermee), date, nom d'origine, type MIME, taille,
  sha256, nom de stockage interne (fichier 0600 sous MEDICAL_DOCUMENTS_STORAGE_DIR),
  statut uploaded|extracting|needs_validation|validated|failed, version et portee du
  consentement de l'envoi, consented_at, retention_delete_after (90 jours),
  Idempotency-Key unique + empreinte.
- `pulse_medical_rules` : document source (FK SET NULL), type (liste du doc 34 §7), texte,
  citation, severite info|warning|critical, statut proposed|active|inactive|expired|
  superseded, echeance, validated_at, accuse de lecture critique, deactivated_at,
  superseded_by (FK), Idempotency-Key unique + empreinte, cle et empreinte de l'activation.
- Job `pulse.medical_retention` seme desactive.

Reglages Imperium (CODE, migration 20261017_0049, doc 43 §15) :
- `imperium_user_settings` : une ligne par utilisateur (user_id unique), creee a la
  premiere lecture ; colonnes typees et contraintes (ai_mode, replan_on_failure_*,
  replan_debounce_minutes 1-120, chat_retention_days dans 30/60/90/180/365).

Vault — memoire de categories (CODE, migration 20261017_0048, doc 42 §7.0) :
- `user_category_memory` : user_id, label_key (libelle normalise, unique par
  utilisateur), sample_label, category, confirmations (>= 1), last_confirmed_at.
  Consultee avant la table en dur ; alimentee par la validation de l'utilisateur.

Tables planning futures / non codees :
- `planning_daily_plan_versions` : CODE (migration 20261018_0080, 2026-10-18). Versionnement du
  living plan D4 (schema du doc 43 §20) : daily_plan_id (FK, cascade), version (0 = plan
  d'origine, archive au premier replan accepte ; N = N-ieme replan accepte), plan_blocks JSONB,
  reason (categorie ou hook), trigger, source_replan_event_id (FK, SET NULL). La version
  courante est la plus haute (`generated_from.replan_version`). Lecture :
  `GET /api/imperium/day/plan/{plan_id}/versions`.
- `planning_replan_events` : CODE (migration 20261017_0045, 2026-10-17). Demande
  (trigger manual|hook, hook_type, reason_category + other_reason + reason_detail
  obligatoires en manuel), statut requested|proposed|revising|accepted|cancelled|failed,
  ai_task_id (imperium.rolling_replan), proposal JSONB + rationale + proposal_version,
  une seule demande ouverte par utilisateur, debounce 5 min calcule sur requested_at.
- Morning check-ins : pas de table dediee. Le check-in du matin est le ressenti
  `planning_days.felt_energy` (1-5) saisi par `POST /api/imperium/day/start`
  (DECISION_demarrage_journee) ; la verification de fraicheur
  (`GET /api/imperium/day/freshness`) lit les tables existantes sans rien ecrire.
- Projets Operations : CODE (migration 20261017_0047, 2026-10-17). Nom canonique
  `imperium_projects` (rank_order, status open|completed|deleted, source manual|chatbot,
  progress_percent 0-100 + progress_why + progress_at deposes par la WR, completed_at,
  completion_method, deleted_at). Les 2 premiers `open` du classement sont actifs (doc 71).
  `imperium_missions` gagne project_id, project_position, description, notes.
- Routines recurrentes et checks quotidiens : CODE (migration 20261017_0047). Noms
  canoniques `imperium_routines` (champs doc 71 §4.1, pinned_* poses par le chatbot,
  anchor_date, deleted_at) et `imperium_routine_checks` (une ligne par routine et par
  journee operationnelle, status planned|done|missed ; conservees apres suppression).
- Expiration de mission, notes de mission, `source/source_ref`,
  `replan_version` et liens objectifs -> missions : FUTUR / NON CODE dans les
  tables planning actuelles.

## DECISION

Tables d'arbitrage et scoring :
`imperium_user_priorities`, `imperium_mission_scores`.

Baremes externalises (migration 20261019_0101, 2026-10-19, spec Daily §4, carte ACT-DLY-01) :
parametres versionnes `df.deadline_points`, `df.impact_points`, `df.mission_type_points`,
`df.dependency_points`, `df.recurrence_points`, `df.criterion_max`, `df.coefficient_by_position`,
`df.priority_buckets` (domaine `df`), semes a l'identique depuis les constantes du code. Le
service (`decision_framework.load_scales`) les lit avec un cache par version ; parametre absent
ou invalide → constantes du code, journalise. Parite prouvee par 83 cas dores captures avant
l'externalisation (`tests/fixtures/df_golden_scores.json`). L'ORDRE des domaines reste dans
`imperium_user_priorities` ; seuls les VALEURS des coefficients sont des parametres. Pas de
refresh du registre (ACT-DLY-03). Audit : `DAILY_MAPPING.md`.
Reglage versionne (migration 20261019_0102, 2026-10-19, spec Daily §4.5 et §10.3, carte ACT-DLY-02) :
`GET /api/daily/settings/scoring` (baremes courants, `source` parameters|code),
`GET /api/daily/settings/scoring/{code}/versions` (historique, l'ancienne version reste lisible),
`PUT /api/daily/settings/scoring` {changes: {code: valeur complete}, reason_fr} (Idempotency-Key).
Coupes (409 `DAILY_SETTINGS_DISABLED`) tant que `daily.settings_enabled` = false (seme). Chaque
parametre change = nouvelle version (origin `user`, raison, `valid_from`) + event
`decision.scoring.updated` ; jeu complet valide avant ecriture (422 `SCORING_INVALID`,
`SCORING_PARAMETER_UNKNOWN` ; 409 `SCORING_NO_CHANGE`, `SCORING_NOT_SEEDED`). Les tests dores ne
s'appliquent pas aux reglages volontaires ; apres un reglage, le registre est rafraichi.
Refresh du registre `imperium_mission_scores` (migration 20261019_0103, 2026-10-19, spec Daily §4.6,
carte ACT-DLY-03) : missions ouvertes (backlog, active, standby), ligne reecrite seulement si elle
change. Les scores ecrits depuis ce lot gardent leurs entrees B-E (`explanation.inputs`) et sont
rejoues en entier avec les baremes courants ; les lignes plus anciennes ne recalculent que le
critere A (les points B-E stockes restent). Coefficient et bucket suivent toujours baremes et
hierarchie courants. Jobs semes desactives : `daily.scores_refresh` (cron `30 4,5 * * *` UTC, ne
tourne qu'a 6 h de Paris) et `daily.day_start` (abonne a `planning.day.started` : refresh ; la
selection initiale du Niveau 1 si `daily.selection_enabled`). Aucun des deux ne demarre une journee.
Selection Niveau 1 (migration 20261019_0104, 2026-10-19, spec Daily §3.1-3.3 et §5-7, cartes
ACT-DLY-04, ACT-DLY-06, ACT-SYS-08) :

```sql
mission_dependencies (id, user_id FK users, parent_mission_id FK imperium_missions ON DELETE CASCADE,
  child_mission_id FK imperium_missions ON DELETE CASCADE, hard BOOLEAN NOT NULL DEFAULT true, created_at,
  UNIQUE (parent_mission_id, child_mission_id), CHECK parent <> child)
daily_selection_log (id, user_id FK users, trigger mission_completed|day_start|disruption_resolved|manual,
  trigger_ref, at_ts, remaining_min, next_fixed_ref, next_fixed_kind mission|calendar_event (0107), scope day|week, feasible_set JSONB array
  [{mission_id, gates_passed, blocked_by, score, duration_min, travel_min, travel_source, mandatory, g5}],
  mandatory_set JSONB array, chosen_mission_id FK imperium_missions ON DELETE SET NULL, tiebreak_applied JSONB
  {band_pct, band_floor, band_members, travel_costs, winner_reason, pool}, outcome next_mission|arbitration_pending|day_done,
  condition empty_feasible|mandatory_conflict, pulled_forward, level 1|2|3, latency_ms, created_at ;
  CHECK chosen_mission_id present ssi outcome = next_mission)
```

Aucun backfill des dependances (aucune arete n'existait). Cycles refuses a l'ecriture
(`POST /api/daily/dependencies`, 422 `DEPENDENCY_CYCLE`). Parametres semes eteints :
`daily.selection_enabled`, `daily.pullforward_enabled` (la carte corrige le defaut true de la spec),
`daily.queue_debug_enabled`, `toolbox.travel_enabled` (le fournisseur de trajet n'est appele que si ce
parametre est vrai ET une cle est configuree ; sinon repli local distance/25 km/h ×1,3 marque
`fallback`) ; reglages `daily.top_band_pct` 15, `daily.pullforward_min_threshold` 45,
`daily.default_mission_duration` 30, `daily.selection_latency_target_ms` 500 (A VALIDER).
Overrides (migration 20261019_0105, 2026-10-19, spec Daily §3.4 et §10.1-10.2, cartes ACT-DLY-07 et
ACT-DLY-08) :

```sql
daily_overrides (id, user_id FK users, selection_log_id FK daily_selection_log UNIQUE,
  proposed_mission_id FK imperium_missions, chosen_mission_id FK imperium_missions, reason TEXT NOT NULL
  CHECK non vide, context JSONB objet {at_local, hour, weekday, time_slot, selection_at, scope, pulled_forward,
  remaining_min, proposed{...}, chosen{...}, scale_versions{df.*: version}}, created_at ;
  CHECK proposed <> chosen)
```

`POST /api/daily/override` {selection_log_id, chosen_mission_id, reason} : 400
`OVERRIDE_REASON_REQUIRED` sans raison, coupe (409 `DAILY_OVERRIDE_DISABLED`) tant que
`daily.override_enabled` = false (seme) ; l'override ne demarre rien. Job `daily.override_aggregation`
(cron `0 17 * * 0` UTC, seme desactive) : motif (domaine propose, domaine choisi, tranche horaire
morning 5-12 h | afternoon 12-18 h | evening 18-23 h | night, Paris) ≥ `daily.override_pattern_min` (3)
sur `daily.override_window_days` (28) → item docket `ordering_override_pattern` (worker w5, domaine daily)
{pattern, count, examples verbatim (5 max), suggested_target domain_coefficient|criterion_c|discussion}.
Un motif encore ouvert au docket n'est pas redepose ; apres decision, seuls les overrides posterieurs
comptent. Aucun ajustement automatique des baremes. Le type n'entre pas dans l'auto-acceptation.
Regles rouges Pulse et porte G5 (migration 20261019_0106, 2026-10-19, spec Pulse §3.5 et §11, spec
Daily §5 G5, cartes ACT-PLS-09 et ACT-DLY-05) :

```sql
pulse_red_flag_rules (id, code UNIQUE, description_fr, condition JSONB objet (DSL evaluee en code),
  severity advise|advise_strong|urgent, action advise_doctor|advise_doctor_and_pause_training|urgent_message,
  message_fr, version, active BOOLEAN DEFAULT false)  -- globale, 5 regles semees INACTIVES
pulse_red_flag_events (id, user_id FK users ON DELETE CASCADE, rule_id FK pulse_red_flag_rules,
  subject_ref TEXT (pain:<id> | weight:<id>), severity, raised_at, evidence JSONB objet (identifiants
  et valeurs, jamais le texte libre), acknowledged_by_user_at, resolution doctor_consulted|resolved|
  dismissed_with_reason, resolution_reason (obligatoire pour dismissed_with_reason), resolved_at ;
  CHECK resolution et resolved_at presents ensemble ; UNIQUE (user_id, rule_id, subject_ref) WHERE
  resolved_at IS NULL)
v_pulse_active_blocks (user_id, block_kind 'pause_training', min_physical_load = daily.pulse_block_load,
  since, source_ref = id du red flag)  -- red flags advise_doctor_and_pause_training non resolus
```

Bascule ACT-PLS-09 : `UPDATE pulse_red_flag_rules SET active=true` sur les 5 codes EN BLOC ; aucune
route ne modifie les regles. Evaluation a chaque ecriture de douleur ou de releve corporel :
RF_severe_pain (douleur ouverte ≥ 8/10), RF_symptom_keywords (type ou notes d'une douleur ouverte,
sans accents ni casse, liste semee), RF_weight_drop (tendance < -1,5 %/mois sur 28 j, ecart ≥ 14 j) ;
RF_lab_out_of_range et RF_rhr_sustained ne se levent jamais tant que bilans structures et FC de repos
n'existent pas. Un sujet n'est leve qu'une fois ; l'acquittement ne leve pas le blocage, seule la
resolution le fait. Daily G5 lit seulement la vue, derriere `daily.g5_enabled` (seme false ; sinon
porte passante `g5: stub`) ; `daily.pulse_block_load` 4 (A VALIDER).
Engagements fixes calendrier (migration 20261019_0107, 2026-10-19, spec Daily §5 G4, PATCH_DAILY D-8) :
`daily_selection_log.next_fixed_kind` (mission | calendar_event, CHECK present ssi `next_fixed_ref`
present ; lignes anterieures : mission). Quand `daily.calendar_commitments_enabled` (seme false) est
vrai, le temps restant s'arrete au plus proche entre la mission `is_fixed_commitment` a venir et
l'evenement `imperium_calendar_events` a venir, `blocks_time`, non soft-supprime. Un evenement deja
commence n'est pas une borne. Les prieres (Q6) arrivent par la migration 0113 ci-dessous.
Prieres en engagements fixes de G4 (migration 20261020_0113, 2026-10-20, Q6, carte ACT-DLY-10) :
`path_registered_mosques` + `adhan_offsets` jsonb {priere: minutes, -120..120} (adhan de la mosquee moins
le calcul local a ses coordonnees) et `iqama_offsets` jsonb {priere: minutes, 0..90} (attente adhan →
iqama) ; `daily_selection_log.next_fixed_kind` accepte `prayer` (ref = uuid5 utilisateur + jour +
priere, sans cle etrangere). Parametres : `daily.prayer_commitments_enabled` false,
`path.mosque_search_travel_min` 20, `path.mosque_travel_margin_pct` 20, `path.prayer_after_iqama_min`
15, `path.prayer_solo_block_min` 20. Aucun nouvel appel reseau : le cache MAWAQIT passe devant le calcul
s'il existe pour la mosquee.
Signaux Pulse hors montre et board (migration 20261020_0108, 2026-10-20, spec Pulse §3.1, §4, §14,
cartes ACT-PLS-08 et ACT-PLS-05 ; familles V8 partielles) :

```sql
pulse_subjective_reports (id, user_id FK users ON DELETE CASCADE, kind fatigue|mood|stress,
  level SMALLINT 1 (bien) .. 5 (mal), reported_at, idempotency_key UNIQUE par utilisateur,
  request_hash, created_at)
```

Signaux `pulse.*` semes INACTIFS dans la table partagee `signal_definitions` (domain `pulse`, jamais de
`pulse_signal_definitions`) : pain_active (severite max des douleurs ouvertes ; 1 yellow, 4 orange,
8 red), fatigue_reported / mood_reported / stress_reported (dernier signalement du jour ; 3 yellow,
4 orange, 5 red), last_meal_hours (> 18 h orange, neutre pendant un jeune), training_adherence_7d
(seances faites / prevues ; ≥ 0,8 green, ≥ 0,6 yellow, sinon orange), workload_today_h (lecture du
planning, informatif). `bands` porte `kind` (high|low|info) et `freshness_minutes`. Valeurs dans
`signal_values` avec `detail.user_id` ; un refresh sans changement ne fait que rafraichir
`measured_at`. Suppression reelle d'un signalement ou d'une douleur : ses valeurs de signal partent
aussi. Job `pulse.signals_refresh` (cron `*/15`, seme desactive) ; refresh immediat apres un
signalement et apres une douleur creee, resolue ou supprimee. `pulse.board_enabled` et
`pulse.reports_enabled` semes false. Non codes : signaux montre, hydratation et nutrition a cible
personnalisee, dette de volume et recuperation, medical structure.
Sentinelle Pulse et dispatch en essai a blanc (migration 20261020_0109, 2026-10-20, spec Pulse §3.1,
§3.2, §5, §6, cartes ACT-PLS-10, 11, 12, 13, 14, ACT-PLS-15 partielle) :

```sql
pulse_sentinel_rules (id, code UNIQUE, rule_type flag_count|severity|user_report|scheduled|pre_session|meta,
  config jsonb, cooldown_minutes NULL|>=0, max_dispatch_per_day, description_fr, version, active DEFAULT false)
pulse_board_snapshots (id, user_id FK users ON DELETE CASCADE, taken_at, reason (code de regle),
  board jsonb (valeur, bande, age, etat par signal ; red flags par reference ; jamais de detail),
  flags_count, max_severity green|yellow|orange|red)
pulse_dispatch_log (id, user_id FK users ON DELETE CASCADE, triggered_by, subject_ref,
  board_snapshot_id FK ON DELETE CASCADE, flag_set jsonb {code: bande}, trigger_event_id,
  status queued|done, model_used, prompt_tokens, output_tokens, latency_ms, output, valid, escalated,
  procedures_named text[], outcome none_needed|dry_run|procedures_run|invalid_fallback|escalated,
  user_reaction useful|useless|missed, reacted_at, created_at, completed_at ;
  CHECK done ssi outcome, model_used et valid presents ; UNIQUE (user_id, triggered_by, subject_ref)
  quand subject_ref present)
```

Regles S1-S7 du §5 semees INACTIVES. S4/S5 : une passe par jour a l'heure de Paris du cron de la
regle (rattrapable `grace_minutes`) ; board sans drapeau = ligne `done`, `none_needed`, `skipped`, sans
file ni event. S6 : une fois par seance `planned` dans les `lead_minutes`. S3 : juste apres un
signalement ou une douleur dont le signal est frais et >= `min_band`. Garde S7 toujours appliquee
(config de S7 meme inactive) : plafond par jour de Paris, dedup des memes drapeaux sans montee de bande
dans la fenetre. Jobs `pulse.sentinel_tick` (cron `*/15`) et `pulse.dispatch_runner` (cron `*/5`),
semes desactives ; le runner ecrit une sortie factice `dry_run` validee par le contrat de
l'interprete et echoue sans rien consommer si `real_ai_enabled` est vrai. Catalogue des procedures
P1-P10 et runner de procedures non codes. Effacement reel de l'historique par l'utilisateur.
Metriques quotidiennes Pulse (migration 20261020_0110, 2026-10-20, spec Pulse §3.9, §13, carte
ACT-PLS-27) :

```sql
pulse_metrics_daily (id, user_id FK users ON DELETE CASCADE, metric_date (jour de Paris),
  dispatches, skipped_passes, dispatches_useful, dispatches_useless, missed_reports, escalations,
  invalid_fallbacks, red_flags (NOT NULL), proposals, accepted, refused, modified, solver_runs,
  solver_infeasible (NULL = pas encore mesurable), agreement_by_slot jsonb (slots pulse.* contre-lus ce
  jour, NULL sinon), computed_at ; UNIQUE (user_id, metric_date))
```

La spec avait `metric_date` en cle seule ; `user_id` ajoute comme partout. Comptes tires de
`pulse_dispatch_log` (un reveil retenu compte, une passe verte gratuite va dans `skipped_passes`) et de
`pulse_red_flag_events`. Slot `pulse.interpreter` seme dans `ai_slot_transition` (local_default, audit
100 %, cible 92 %) ; pas de job d'audit Pulse dedie, le job partage `wr.audit_weekly` couvre tous les
slots. Job `pulse.metrics_rollup` (cron `45 0 * * *` UTC, seme desactive) : recalcule les deux derniers
jours clos.
Procedures Pulse et propositions (migration 20261020_0111, 2026-10-20, spec Pulse §3.3, §7, §8, §13) :

```sql
pulse_procedures (id, code UNIQUE, name_fr, purpose_fr, trigger_types text[], steps jsonb,
  llm_slots jsonb, version, active DEFAULT false)
pulse_procedure_runs (id, user_id FK users ON DELETE CASCADE, procedure_id FK, procedure_version,
  dispatch_id FK pulse_dispatch_log ON DELETE SET NULL, trigger_event_id, correlation_id, inputs jsonb,
  dry_run, status queued|running|waiting_user|completed|aborted|failed, steps_log jsonb, result jsonb,
  created_at, started_at, finished_at)
pulse_proposals (id, user_id FK users ON DELETE CASCADE, procedure_run_id FK ON DELETE CASCADE,
  kind session_adaptation|diet_change|program|meal_plan|monitoring|corpus_sheet|parameter_update|
  signal_definition|doctor_advice, payload jsonb, summary_fr, dry_run, created_at, presented_at,
  expires_at, decision accepted|refused|modified|expired, decided_at, user_explanation,
  modified_payload, applied, applied_at ; CHECK refus explique, modification avec payload, essai a
  blanc jamais presente, application seulement apres accepted|modified)
```

Les 10 cartes P1-P10 du §7 semees INACTIVES ; leurs 12 slots IA semes dans `ai_slot_transition` avec
les tiers du §7 (domaine pulse). Un seul mecanisme : job `pulse.procedure_runner` (cron `*/5`, seme
desactive). Seule P1 (`adapt_training_session`) a ses etapes code : seance, menu des coups legaux,
choix factice tant que `real_ai_enabled` est faux, validation avec repli `maintain`, proposition
`dry_run` jamais presentee. Sans programme d'entrainement, seuls `maintain`, `shift_time` et
`reschedule` peuvent etre legaux (creneaux libres de seances, missions a heure fixe et evenements
bloquants ; pas de seance high apres 12 h de jeune ni deux jours high d'affilee). Un blocage sante
actif arrete P1. Les autres procedures s'arretent en `aborted` (`not_coded`). Parametre
`pulse.proposals_enabled` seme false.
Chatbot V1 local (migration 20261020_0115, 2026-10-20, doc 72) :

```sql
chat_sessions (id, user_id FK users ON DELETE CASCADE, context_kind general|project|mission|intervention,
  context_ref, status open|closed, started_at, closed_at ; CHECK closed ssi closed_at)
chat_messages (id, session_id FK ON DELETE CASCADE, user_id, role user|assistant, content <= 8000,
  model_used, latency_ms, degraded, created_at)
chat_proposals (id, session_id FK ON DELETE CASCADE, message_id FK ON DELETE CASCADE, user_id,
  action create_project|add_project_mission|create_routine, params jsonb, summary_fr,
  status proposed|validated|rejected|superseded|failed, result jsonb, created_at, decided_at ;
  UNIQUE une seule proposition ouverte par session)
```

Slot `chat.converse` (local_default) ; parametre `chat.enabled` seme false. Une proposition n'est executee
que par la validation explicite de l'utilisateur (cle d'idempotence tiree de la proposition).
Migration 20261020_0116 : parametre `chat.action_requirements` (fiche par action : champs requis et
libelles, `min_description_chars` 15, `min_missions` 1, `max_missions` 10 pour `create_project`) ; aucune table.
`create_project` porte desormais `params.missions` (liste titre + duree), creees a la validation.
Migration 20261020_0117 : `chat_sessions.agent` (general|project|mission, defaut general, choisi par le code a
l'ouverture) ; parametre `chat.agents` (role, libelle, actions, enabled ; project et mission semes false).
Migration 20261020_0118 : `chat_proposals.action` accepte `switch_agent` (params agent + context_ref) ; sa
validation change `chat_sessions.agent`, `context_kind` et `context_ref`.
Programme d'entrainement et dette de volume (migration 20261020_0112, 2026-10-20, spec Pulse §3.6, §8) :

```sql
pulse_programs (id, user_id FK users ON DELETE CASCADE, name, objective_weights jsonb, mesocycle jsonb,
  doctrine_sheet_code NULL (corpus absent), status active|paused|completed|superseded,
  created_by_run FK pulse_procedure_runs ON DELETE SET NULL, version, idempotency_key UNIQUE par
  utilisateur, request_hash, created_at, updated_at ; UNIQUE un seul active par utilisateur)
pulse_program_targets (id, program_id FK ON DELETE CASCADE, week_start (lundi, CHECK), muscle_group,
  target_sets, tolerance_sets DEFAULT 2 ; UNIQUE (program_id, week_start, muscle_group))
pulse_workouts + program_id FK pulse_programs ON DELETE SET NULL, session_type
  strength|hypertrophy|cardio|mobility|technique|mental, systemic_load 1..10
pulse_volume_debt (id, user_id, program_id FK ON DELETE CASCADE, muscle_group, debt_sets > 0,
  origin_workout_id FK ON DELETE CASCADE, repayment_workout_id FK ON DELETE SET NULL,
  created_by_proposal FK ON DELETE SET NULL, status open|scheduled|repaid|written_off, created_at,
  resolved_at)
pulse_legal_moves (id, code UNIQUE, name_fr, preconditions, parameters_schema, effects, doctrine_refs,
  version, active DEFAULT true)
```

`pulse_workouts` est etendue au lieu d'une table `pulse_sessions` en double ; le groupe musculaire est
porte par chaque exercice (`exercises[].muscle_group`), le volume se compte en series planifiees par
semaine de Paris. Les 8 coups du §8 sont semes actifs (evalues en code ; un coup desactive n'est jamais
legal). Dette : nee d'un coup accepte, placee par `repay_debt`, remboursee quand la seance est
terminee, rouverte si elle est sautee ; la perte reste une decision du WR, non codee. Parametres
`pulse.programs_enabled` false et `pulse.max_debt_sets_group` 10.
IA locale par slot (migration 20261020_0114, 2026-10-20, decision utilisateur : local seulement) :
parametre `ai.local_slot_modes` ({slot_code: off|shadow|live}, seme vide). Seul un slot `local_default`
d'`ai_slot_transition` peut etre servi, et seulement vers une adresse de bouclage. En `shadow`, la sortie
du modele est rangee a cote du resultat deterministe (`pulse_dispatch_log.output.local`,
`pulse_procedure_runs.steps_log[].local`) sans servir ; en `live`, elle decide (procedures nommees,
coup de P1), et une proposition reste soumise a decision. Timeout des jobs `pulse.dispatch_runner` et
`pulse.procedure_runner` porte a 600 s (3 elements par passe quand un slot local est allume).

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
- Check : `coefficient > 0` (migration 0103, 2026-10-19). Avant : position 1→10, 2→8, 3→5, 4→4
  impose en base ; les valeurs viennent desormais de `df.coefficient_by_position` (reglable).
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
- Check : `domain_coefficient > 0` (migration 0103, 2026-10-19 ; avant `IN (10, 8, 5, 4)`, incompatible avec un coefficient regle)
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

Docket du WR — `wr_docket_items` : CODE (migration 20261019_0083, 2026-10-19, spec WR §3.1 ;
doc 78 F2-11). Table partagee d'emblee (R3) : WR, Daily, Vector et Pulse y deposent les points
a trancher par l'utilisateur. Colonnes du DDL de la spec + `user_id` (FK users) : item_type
(10 valeurs de la spec, + `ordering_override_pattern` depuis 20261019_0105, Daily §10.2), domain, title_fr, payload et evidence_refs JSONB, confidence 0-100
(NULL = depot deterministe), impact_estimate 1-5, severity normal|elevated|red, priority,
status pending|presented|validated|refused|deferred|archived, consecutive_defers,
force_decision, source_worker w1|w2|w3|w4|w5|phase1|phase3|manual (w5 depuis 0105), created_at, decided_at,
decision_note. Parametres semes (`parameters`, a valider) : `wr.docket_halflife_days` = 14,
`wr.docket_max_defers` = 3. Priorite = poids severite (1/2/4) x impact x exp(-age/demi-vie)
x (0,5 + confidence/200, ou 1 sans confidence). Une decision ne fait qu'enregistrer le choix ;
rien n'est applique par le docket. Routes : `GET /api/wr/docket?status=&type=`,
`GET /api/wr/docket/red`, `POST /api/wr/docket/{id}/decision` (Idempotency-Key).
`GET /api/wr/docket?mode=light` = WR court (spec WR §9 P4) : rouges, decisions forcees,
contradictions et deltas de plan seulement ; le reste porte sans penalite. Depuis le
2026-10-19, un refus ou une validation modifiee exige `decision_note` (422 sinon ; spec WR §9 P4 :
l'explication est le label).
Notification rouge (migration 20261019_0098, 2026-10-19, spec WR §7, carte ACT-WR-07) : parametre
seme `wr.red_notify_enabled` = false. Eteint, un item rouge est depose et reste en tete de
`GET docket/red`, sans notification ni event `planning.docket.red_notified` ; allume, il notifie
une fois (`notify()`, toutes les voies). `POST /api/wr/docket/{id}/red-ack` : accuse de reception
idempotent (`notifications.acked_at` et `read_at`, event `planning.docket.red_acked`), 409
`DOCKET_NOT_RED` ou `RED_NOT_NOTIFIED` ; l'accuse ne decide pas l'item. Pas de DDL.

Marche du docket — `wr_walks` : CODE (migration 20261019_0093, 2026-10-19, spec WR §9 P4 ;
carte V18 ACT-WR-06). Une marche par session WR (unique, FK cascade) : user_id, mode
full|light, budget_min fige au depart depuis `wr.budget_min` ({full: 45, light: 15}, a
valider), started_at, closed_at. `GET /api/wr/walk/next` sert l'item ouvert le plus
prioritaire du mode (decisions forcees d'abord ; un item reporte pendant la marche n'est pas
resservi) ; budget epuise -> seuls rouges et decisions forcees. Lecture seule ; les decisions
passent par `POST /api/wr/docket/{id}/decision`. `POST /api/wr/walk` (201, 200 si deja
demarree, 409 `WR_NOT_OPEN`), `POST /api/wr/walk/close` (idempotente, les items non tranches
portent). Events `planning.wr_walk.started` / `.closed`.

Plan strategique — `plan_versions`, `plan_deltas`, vue `v_plan_current` : CODE (migration
20261019_0095, 2026-10-19, spec WR §3.5 et §8 ; Q8 ; carte V20 ACT-WR-18). DDL de la spec +
user_id, activated_at, superseded_at, superseded_reason_fr (plan_versions) et user_id,
rejection_fr, created_at (plan_deltas). `plan_versions` : horizon 7 a 42 jours, `plan` objet
`{items: [{ref, title_fr, week, params}], invariants_fr}` (ref `type:id` unique, semaine dans
l'horizon), origin initial|monthly_regen|shock_regen, status proposed|active|superseded, une
seule version active par utilisateur (index partiel) ; DELETE interdit (trigger) : le retour
arriere passe la version en superseded. `plan_deltas` : operations move|add|remove|modify,
origin wr_weekly|user_request|shock_minor, status proposed|accepted|refused|applied
(applied_at ssi applied), proposal_id (FK docket). `v_plan_current` : version active + deltas
appliques dans l'ordre ; le code les rejoue (un delta s'applique en entier ou est rejete avec
ses raisons : ref absente ou deja presente, semaine hors horizon, champ non modifiable).
Plan initial SAISI par l'utilisateur : `POST /api/wr/plan/initial` (Idempotency-Key, cree
`proposed`, 409 `PLAN_ALREADY_ACTIVE`), `POST /api/wr/plan/versions/{id}/activate` (validation ;
l'ancienne active passe superseded ; 409 `PLAN_SUPERSEDED`), `POST …/{id}/supersede` (raison
obligatoire), `GET /api/wr/plan/versions`, `GET /api/wr/plan/current` (409 `PLAN_DISABLED` tant
que `wr.plan_enabled` = false, seme ; 404 sans version active). Events `planning.plan.proposed`,
`.activated`, `.superseded`. Generation des deltas hebdo : V23.
Regeneration choc (migration 20261019_0099, 2026-10-19, spec WR §8.1 et §13.6, carte ACT-WR-20) :
parametres semes `wr.shock_taxonomy` (6 raisons : vehicle_accident, immobilizing_breakdown,
major_family_event, income_source_loss, disabling_injury, housing_disaster ; editable, a valider)
et `wr.plan_shock_enabled` = false. `POST /api/wr/plan/shock` {reason_code} (Idempotency-Key ; 409
`PLAN_SHOCK_DISABLED` tant que `wr.plan_enabled` ou `wr.plan_shock_enabled` est faux) :
declenchement MANUEL seulement, aucun abonnement aux replans ordinaires. Cree une version
`proposed`, origin `shock_regen`, origin_ref = event `planning.plan.shock_requested`, jamais
activee seule (activate reste la validation). Essai a blanc tant que `real_ai_enabled` est faux :
copie du plan courant (deltas appliques) recalee sur aujourd'hui, `model_used=dry_run` ; avec
`real_ai_enabled` vrai, 409 `PLAN_REGEN_NOT_CODED`. Refus : 422 `SHOCK_REASON_UNKNOWN`, 409
`PLAN_NOT_ACTIVE`, `PLAN_REGEN_PENDING` (une regeneration deja proposee). `PlanVersionRead` expose
`origin_ref` et `model_used`. Pas de DDL.
Regeneration mensuelle (migration 20261019_0100, 2026-10-19, spec WR §8.3, carte ACT-WR-21) :
job `wr.monthly_regen` (cron `0 5 1 * *` UTC, le 1er du mois ; a valider face au doc 52 §8 /
DV-5), seme desactive. Meme contrat que le choc avec origin `monthly_regen`, sans origin_ref :
version `proposed` jamais activee seule, essai a blanc (copie du plan courant) tant que
`real_ai_enabled` est faux, echec du run sinon. Saut motive (`detail.skip`) : plan eteint, pas de
version active, regeneration deja en attente, deja une regeneration mensuelle ce mois (Paris).

Classes d'auto-acceptation — `wr_autoaccept_classes` : CODE (migration 20261019_0089,
2026-10-19, spec WR §9 P4 et §13.8 : « table vide + mecanique, activation = decision user » ;
pas de DDL dans la spec). Colonnes : user_id, item_type (7 types ; jamais autoaccept_spotcheck,
red_flag_ref ni user_question), domain (NULL = tous), slot_code (FK ai_slot_transition),
min_confidence 0-100, rationale_fr (raison de l'utilisateur), enabled, created_at, disabled_at ;
une seule classe active par utilisateur, type et domaine. `wr_docket_items.autoaccept_class_id`
(FK) marque l'item valide d'office et ses controles. Au depot, un item non rouge avec
confidence >= min_confidence, dont le slot tient sa cible d'agreement sur les
`ai.audit_decay_weeks` dernieres semaines closes, passe `validated` ; `wr.spotcheck_pct` (10)
% d'entre eux, tires sur l'id, sont re-presentes en `autoaccept_spotcheck` (payload = item
d'origine). Un refus de controle est un label, il ne desactive rien. Routes :
`GET /api/wr/autoaccept-classes`, `POST /api/wr/autoaccept-classes` (Idempotency-Key, 409
`AUTOACCEPT_CLASS_EXISTS`), `POST /api/wr/autoaccept-classes/{id}/disable`.

Digest du WR — `wr_digests` : CODE (migration 20261019_0084, 2026-10-19, spec WR §3.6).
Un digest par session WR (`review_session_id` unique, FK cascade), fige a l'assemblage :
user_id, window_from/window_to (= week_start/week_end), digest JSONB (sections whitelistees
window, docket par type, counts open/included, truncated, unavailable), token_estimate
(caracteres JSON / 4). Parametres semes (a valider) : `wr.digest_token_cap` = 40000 et
`wr.digest_caps` (chain_proposal 12, pattern_new 10, pattern_contradiction 8, anomaly 10,
belief_review_due 6, plan_delta_proposal 8 ; un type sans plafond n'est borne que par les
tokens). Troncature par priorite, rouges et decisions forcees en dernier recours. Payload
d'item contenant du brut (conversation, transcript, texte de document, image...) -> refus.
Depuis la migration 0094 : section `rollups` (totaux de la semaine par domaine depuis
`wr_rollups_daily` : jours couverts, sommes, derniere et pire pression, net VTC par heure,
missions ouvertes en retard le dernier jour) et section `anomalies` (journees hors green des
signaux W4 de la semaine, |z| decroissant, au plus `wr.digest_anomaly_signals_cap` = 20, a
valider). Depuis la migration 0095 : section `plan_state` (plan courant de `v_plan_current`,
deltas appliques) quand `wr.plan_enabled` est vrai et qu'une version est active, sinon
`unavailable: ["plan_state"]`. Routes : `POST /api/wr/digest` (session WR lancee
et non fermee, sinon 409 `WR_NOT_OPEN` ; 201 cree, 200 deja fige), `GET /api/wr/digest/current`.
Job `wr.digest_on_open` (seme desactive) : abonne a `planning.weekly_review.launched`, emis au
premier lancement de la session WR.

Usine du WR — `wr_worker_runs` et `wr_worker_cursors` : CODE (migration 20261019_0090,
2026-10-19, spec WR §3.2 et §4). DDL de la spec + `wr_worker_runs.job_run_id` (run du runner).
Ordre d'un passage : W1 rollups -> W4 anomalies -> W2 causal -> W3 apprentissages -> W5 docket ;
chaque worker traite ]curseur, maintenant] puis avance son curseur. Un echec n'avance pas le
curseur et arrete la chaine ; le passage suivant reprend le meme lot. Worker non code : saute,
sans curseur (premier lot = depuis minuit, heure de Paris). Un worker code ne tourne que s'il
est liste dans le parametre `wr.factory_workers_enabled` (seme vide ; carte V18). Codes : W1
(rollups, ci-dessous), W4 (anomalies, ci-dessous), W2 et W3 en dry-run (ci-dessous) et W5 (items
`anomaly` depuis W4 puis recalcul des priorites du docket) ; aucun appel de modele. Jobs semes desactives :
`wr.factory_on_session_end` (abonne a `rides.session.ended`) et `wr.factory_fallback` (cron
UTC 21:30 et 22:30 ; ne tourne qu'a 23 h de Paris et si l'usine n'a pas tourne ce jour-la).
Event `planning.factory.run_completed` par worker passe.

Decouverte causale W2 — `chain_probes`, `chain_candidates`, `chain_pair_verdicts`,
`chain_assemblies` : CODE (migration 20261019_0096, 2026-10-19, spec WR §3.3 et §5 ; carte V20
ACT-WR-10). DDL de la spec + user_id et created_at partout, FK vers `events.id`,
`chain_assemblies.dry_run`. Antichambre : rien n'entre dans le graphe causal reel (causation_id,
depth des events, E2) avant la Phase 5. Events notables choisis par le code selon le parametre
editable `wr.notable_criteria` (types notables `planning.mission.aborted`,
`planning.replan.requested`, `finance.pressure.corrected` ; red flag `planning.docket.red_notified` ;
questions utilisateur : aucune encore ; anomalie W4 >= orange le meme jour de Paris dans le domaine
de l'event ; 10 cibles au plus par passage, red flags d'abord ; un event deja sonde n'est pas
repris ; a valider). Candidats (code) : anteriorite stricte, `wr.chain_window_days` (90), cause
declaree exclue, events internes du WR exclus ; canaux graph (meme correlation_id) et metadata
(meme famille ou meme jour) ; canaux vectoriels eteints ; rerank composite canal x proximite,
`wr.chain_topn` (10) retenus. Sondes et verdicts FACTICES tant que `real_ai_enabled` est faux
(`generated_by` / `model_used` = `dry_run`, tirage deterministe) ; W2 reel non code (V21) : avec
`real_ai_enabled` vrai, le worker echoue sans avancer son curseur. Assemblage (code) : verdicts
direct_cause|favoring_condition >= `wr.chain_min_confidence` (60) -> liens (depth = depth de la
cause + 1), plusieurs causes directes ou cycle -> `conflicts` ; avec au moins un lien, item
docket `chain_proposal` (titre « [essai] », payload.dry_run, sans confiance donc jamais
auto-accepte). Le statut de l'assemblage suit la decision du docket (valide, refuse ; archive =
refuse ; report = inchange).

Apprentissages W3 — `wr_pattern_extractions` et `memory_confrontations` : CODE (migration
20261019_0097, 2026-10-19, spec WR §6.1-6.2, §13.4-13.5 ; carte V20 ACT-WR-10).
`wr_pattern_extractions` est un ajout (la spec insere directement dans ai_memories) : journal des
patterns extraits a la cloture d'un episode (statement_fr, pattern_domain, context_predicate valide
ou null, predicate_rejected, evidence_event_ids, suggested_confidence, canonical_errors,
model_used, dry_run). `memory_confrontations` : DDL de la spec + user_id, extraction_id, dry_run ;
`neighbor_memory_id` nullable (aucun voisin = `unrelated`). Episodes choisis par le code selon
`wr.episode_criteria` (types `planning.mission.completed`, `planning.mission.aborted`,
`planning.wr_walk.closed` ; decision du docket validee ou refusee avec explication, hors
auto-acceptation ; 20 au plus par passage ; a valider). Code reel : regles de canonicite (240
caracteres, affirmative, pas de pronom en tete, pas de date relative, une seule affirmation) et
vocabulaire des context_predicate (`all`|`any` de conditions field/op/value sur `day.day_of_week`,
`day.is_weekend` et les metriques des rollups W1 `finance.*`, `rides.*`, `missions.*`) ;
statement non canonique -> journalise, pas confronte ; predicat invalide -> null. Extraction et
verdict d'identite FACTICES tant que `real_ai_enabled` est faux (`dry_run`), aucun voisin
(recherche vectorielle eteinte) : effet prevu journalise, jamais applique. AUCUNE ecriture dans
ai_memories (extension croyances : DV-1 ; commit memoire : V25). Parametre `wr.identity_topk` (5)
seme pour la V25. W3 reel non code : avec `real_ai_enabled` vrai, le worker echoue sans avancer
son curseur.

Rollups W1 — `wr_rollups_daily` : CODE (migration 20261019_0091, 2026-10-19, spec WR §4 W1 ;
pas de DDL dans la spec ; lu par le digest depuis 0094). Une ligne par utilisateur, jour de Paris et domaine, `metrics` JSONB
reecrit en entier a chaque passage (upsert, unique user/jour/domaine). Sources canoniques
seulement (AD-2) : finance = ledger `imperium_vault_transactions` du jour (income, expense,
net, nombre, reversals ; regles du rapport hebdo) + score du dernier `pressure_snapshots` du
jour ; rides = sessions terminees (revenu, depense, minutes, net par heure) + deposes (nombre,
5 zones les plus frequentes) ; missions = demarrees, terminees/ratees/annulees, terminees en
retard et retard moyen sur la deadline, ouvertes en retard en fin de jour (statut a l'instant
du calcul). Pulse : stub neutre (aucune ligne ; lecture des donnees de sante par l'usine a
trancher). Jours recalcules : ceux de la fenetre + ceux des lignes creees ou modifiees dans la
fenetre (saisie tardive).

Anomalies W4 — tables partagees `signal_definitions` / `signal_values` (migration
20261019_0092, spec WR §4 W4 ; jamais de table wr_). 8 signaux `wr.*` (domain `wr`, semes
INACTIFS : activation = `active=true` par signal) : revenus, depenses, pression, net VTC par
heure, minutes de conduite, missions ratees, finies en retard, ouvertes en retard. Pour chaque
jour recalcule par W1 : baseline = mediane des 28 jours precedents, echelle = MAD x 1,4826
(plancher `min_scale`), z dans le sens qui inquiete ; bandes yellow 2, orange 3, red 4 ; il faut
14 jours d'historique ; les jours a zero sont ignores pour les signaux VTC. Une valeur par
signal et par jour (`measured_at` = 23:59:59 a Paris, reecrite au recalcul, `detail.user_id`).
Marqueur `unexplained` sur toute bande hors green (pas encore de lien causal W2 ni de catalogue
de raisons). W5 depose un item `anomaly` par signal et par jour a partir de
`wr.anomaly_docket_min_band` (orange) : rouge -> severite `elevated` et impact 4, orange ->
`normal` et 3 ; jamais `red` (reserve aux red flags).

Metriques du WR — `wr_metrics_weekly` : CODE (migration 20261019_0085, 2026-10-19, spec WR §3.8).
Colonnes de la spec + `user_id` ; une ligne par utilisateur et par lundi (unique), NULL = pas
encore mesurable (events_processed, patterns_reinforced, cloud_cost_estimate,
agreement_by_slot rempli depuis l'audit des slots (0088) quand il y a des contre-lectures :
usine W1-W3 non codee ; factory_runs = passages de l'usine dans `wr_worker_runs`).
Semaine Europe/Paris. Comptes du docket : items crees (et par type :
chain_proposals, patterns_new, contradictions), decisions et decisions forcees d'apres les
events `planning.docket.*`. Politique de saut : session de la semaine lancee -> wr_mode = mode
de sa marche du docket (`full` sans marche) et duree lancement -> fin ; rien de
lance au lundi de S+2 -> `skipped` ; avant, NULL. Job `wr.metrics_rollup` (cron 04:30, seme
desactive) : recalcule et ecrit les deux dernieres semaines closes. Route
`GET /api/wr/metrics/weekly?weeks=1..12` : calcul a l'instant, lecture seule.

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
`20260512_0022_imperium_calendar_events_foundation.py` +
`20260707_0035_calendar_events_soft_delete_traceability.py`, modele
`backend/app/models/imperium.py::ImperiumCalendarEvent`

Role : fondation Calendar V1 minimale et deterministe. La table stocke des
evenements/deadlines/vacances manuels appartenant a l'utilisateur courant, pour
que le backend puisse disposer plus tard de contraintes calendaires sans
inventer un stockage sous pression.

Schema reel :

```text
id               UUID PRIMARY KEY DEFAULT gen_random_uuid()
user_id          UUID NOT NULL FK users.id
event_type       TEXT NOT NULL
title            TEXT NOT NULL
starts_at        TIMESTAMPTZ NOT NULL
ends_at          TIMESTAMPTZ NULL
blocks_time      BOOLEAN NOT NULL DEFAULT true
location         TEXT NULL
notes            TEXT NULL
deleted_at       TIMESTAMPTZ NULL
deleted_by       TEXT NULL
deletion_reason  TEXT NULL
created_by       TEXT NULL
updated_by       TEXT NULL
created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
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
  `event_type`. Elle exclut par defaut les lignes soft-deleted
  (`deleted_at IS NULL`).
- Le filtre `to` ne peut pas etre inferieur a `from`.
- La suppression `DELETE /api/imperium/calendar/events/{event_id}` est
  user-scoped. Elle soft-delete la ligne calendar (`deleted_at`, `deleted_by`,
  `deletion_reason`) et cree un event canonique `calendar.event.deleted` dans
  `events` avec payload `{ calendar_event_id, deleted_by, reason }`. Elle ne
  requiert pas d'idempotency key cote API.
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
