# AUDIT EVENTS

Date: 2026-06-28
Perimetre lu:
- migrations `20260430_0011`, `20260526_0029`, `20260526_0030`, `20260526_0031`
- modeles `backend/app/models/event.py`, `backend/app/models/imperium.py`
- services `backend/app/services/imperium/events.py`, `event_readers.py`, `backend/app/services/events/ingestion.py`
- schema `backend/app/schemas/events.py`
- docs `08_NON_NEGOTIABLE_RULES.md`, `04_MVP_BACKEND_CONTRACTS.md`, `05_DATABASE_SCHEMA.md`

Audit lecture seule du code applicatif: aucun correctif code.

## Verdict

(c) divergent.

La solidite append-only DB est bonne, mais le module Events est coupe en deux:

1. `events` = ancien journal canonique avec enveloppe EVENT-005 quasi complete, types dotted, utilise par les vrais services metier.
2. `imperium_events` = fondation recente `/api/imperium/events`, append-only et bien durcie, mais enveloppe reduite et `event_type` snake_case mono-segment.

Resultat: les evenements reellement emis par le backend ne vont presque jamais dans `imperium_events`; l'API Events Foundation recente ne respecte pas l'enveloppe EVENT-005 complete ni la regle transverse EVENT-002 "dotted events".

## 1. Schema et enveloppe EVENT-005

### Table `events`

Source: migration `0001`, modele `backend/app/models/event.py`.

Colonnes presentes:
- `id`
- `event_id`
- `event_type`
- `schema_version`
- `occurred_at`
- `received_at`
- `source_app`
- `device_id`
- `user_id`
- `idempotency_key`
- `correlation_id`
- `causation_id`
- `privacy_level`
- `payload`
- `duplicate_of_event_id`
- `created_at`

Cette table colle le mieux a EVENT-005:
- source: `source_app`
- device: `device_id`
- user: `user_id`
- privacy: `privacy_level`
- correlation: `correlation_id`
- causation: `causation_id`
- type: `event_type`
- payload: `payload`
- idempotence: `idempotency_key`
- temps: `occurred_at`, `received_at`, `created_at`

Ecarts:
- pas de contrainte DB de format dotted sur `event_type`;
- `schema_version` utilise `"1.0"` dans les services, alors que `imperium_events` impose `"v1"`;
- le champ `source_module` n'existe pas, il est remplace par `source_app`;
- pas de contrainte DB `payload` JSON object seulement.

### Table `imperium_events`

Source: migrations `0029/0030/0031`, modele `ImperiumEvent`.

Colonnes presentes:
- `id`
- `user_id`
- `event_type`
- `source_module`
- `occurred_at`
- `payload_json`
- `schema_version`
- `idempotency_key`
- `created_at`
- `updated_at`

Ecarts EVENT-005:
- absent: `event_id`
- absent: `source`/`source_app` ou equivalent source systeme
- absent: `device_id`
- absent: `privacy_level`
- absent: `correlation_id`
- absent: `causation_id`
- absent: `received_at`
- payload nomme `payload_json`, nullable, pas `payload`
- `updated_at` existe pour compatibilite seulement, mais la table est append-only

Conclusion schema: `imperium_events` est conforme a la doc locale `04/05` "Event Foundation 23A", mais pas a l'enveloppe transverse EVENT-005 de `08`.

### Contradiction documentaire

`08_NON_NEGOTIABLE_RULES.md` et `06_N8N_WORKFLOWS.md` exigent des noms dotted, par exemple `mission.completed`.

`04_MVP_BACKEND_CONTRACTS.md` et `05_DATABASE_SCHEMA.md` documentent au contraire pour `/api/imperium/events`:
- `event_type snake_case strict`
- `schema_version = v1`
- `payload_json null or JSON object only`

Cette contradiction est maintenant codifiee par les tests et la migration `0031`.

## 2. Append-only, idempotence, event_type

### DB

Solide.

Pour `events`:
- migration `0002`: trigger `events_append_only_guard` bloque `UPDATE` et `DELETE`;
- migration `0003`: trigger `events_append_only_truncate_guard` bloque `TRUNCATE`;
- tests `test_events_append_only.py` couvrent `UPDATE`, `DELETE`, `TRUNCATE`.

Pour `imperium_events`:
- migration `0029`: trigger `imperium_events_append_only_guard` bloque `UPDATE` et `DELETE`;
- migration `0029`: trigger `imperium_events_append_only_truncate_guard` bloque `TRUNCATE`;
- tests `test_events_append_only.py` couvrent aussi `imperium_events`.

Pour `auth_events`:
- meme logique append-only dans `0002/0003`, hors journal transverse metier mais utile pour audit securite.

### Service

`backend/app/services/imperium/events.py` respecte l'append-only:
- `create_imperium_event()` fait uniquement `db.add(event)` puis `commit`;
- replay idempotent retourne l'ancien event;
- aucune fonction `update`, `delete`, `truncate`;
- `event_readers.py` est lecture seule et les tests ont des guards `add/flush/commit` qui echoueraient.

`backend/app/services/events/ingestion.py` respecte aussi l'append-only:
- insert `IdempotencyKey` + insert `Event`;
- replay idempotent retourne la reponse stockee;
- aucune mutation d'event.

Attention: les services metier modifient des tables canoniques (`missions`, `daily_plans`, etc.) apres avoir cree un `Event`. C'est normal pour ces objets metier, mais cela confirme que l'event journal n'est pas le seul stockage de verite.

### Idempotence

`events`:
- unique DB `(user_id, event_id)` depuis migration `0011`;
- unique DB `(user_id, idempotency_key)` depuis `0001`;
- `ingestion.py` utilise aussi `idempotency_keys` pour stocker request hash + response.

`imperium_events`:
- index unique partiel `(user_id, idempotency_key)` quand `idempotency_key IS NOT NULL`;
- API POST exige le header `Idempotency-Key`;
- service detecte replay identique et conflit si meme cle avec payload different.

Point faible: `imperium_events.idempotency_key` est nullable en DB. L'API le rend obligatoire, mais une insertion directe DB peut encore creer des events sans idempotency key.

### Format `event_type`

`events`:
- `EventEnvelope` Pydantic impose dotted: `^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*)+$`;
- mais la table DB `events` n'a pas de contrainte de format;
- les services metier qui creent `Event` directement contournent `EventEnvelope`.

`imperium_events`:
- Pydantic et DB imposent snake_case strict: `^[a-z][a-z0-9_]*$`;
- donc `mission.completed`, `vault.transaction.created`, `day.plan.created` sont refuses par `/api/imperium/events`.

Conclusion: le format dotted est respecte par la plupart des emissions reelles dans `events`, mais il n'est pas garanti par la DB; le nouveau journal `imperium_events` interdit le format canonique transverse.

## 3. Evenements reellement emis

### Dans `events`

Emis par le code metier:

| Event type | Source code | Table |
|---|---|---|
| `vault.transaction.created` | `services/vault/transactions.py` legacy `/api/vault` | `events` |
| `priority.rules.updated` | `services/imperium/priorities.py` | `events` |
| `day.plan.created` | `services/imperium/daily_plans.py` | `events` |
| `day.plan.activated` | `services/imperium/daily_plans.py` | `events` |
| `day.plan.completed` | `services/imperium/daily_plans.py` | `events` |
| `day.plan.cancelled` | `services/imperium/daily_plans.py` | `events` |
| `day.finished` | `services/imperium/day_finish.py` | `events` |
| `mission.started` | `services/imperium/missions.py` | `events` |
| `mission.backlog.created` | `services/imperium/missions.py` | `events` |
| `mission.completed` | `services/imperium/missions.py` via `mission.{outcome}` | `events` |
| `mission.failed` | `services/imperium/missions.py` | `events` |
| `mission.abandoned` | `services/imperium/missions.py` via `mission.{outcome}` | `events` |
| `path.item.created` | `services/imperium/path_items.py` legacy | `events` |
| `path.item.started` | `services/imperium/path_items.py` legacy | `events` |
| `path.item.completed` | `services/imperium/path_items.py` legacy | `events` |
| `path.item.skipped` | `services/imperium/path_items.py` legacy | `events` |
| `path.item.cancelled` | `services/imperium/path_items.py` legacy | `events` |
| `calendar.event.created` | `services/imperium/calendar.py` | `events` |

Il existe aussi l'ingestion generique `POST /api/events`, qui peut stocker n'importe quel `EventEnvelope` dotted valide dans `events`.

### Dans `imperium_events`

Le seul createur reel est `POST /api/imperium/events` via `create_imperium_event()`.

Ce n'est pas une emission metier automatique. C'est une API generique manuelle/current-user qui accepte des `event_type` snake_case et `source_module` dans la liste autorisee.

Les services metier audites ne l'utilisent pas.

### `auth_events`

Journal separe, append-only, pour securite/auth:
- `login`
- `auth.refresh.rotated`
- `auth.refresh.failed`
- `auth.logout`
- `auth.logout.failed`
- CLI: `user.bootstrap.created`, `auth.password.reset`, `auth.master_key.reset`, `auth.devices.revoked`

Ce n'est pas le journal transverse metier, mais il confirme un autre log append-only actif.

### Documentes mais pas emis

Confirme:
- `ai.result.stored` est documente (`16_AI_BACKEND_LAYER_OVERVIEW.md`, `31_AI_TASKS_AND_RESULTS_CONTRACT.md`) mais pas emis dans `receive_ai_result()`.

Autres exemples documentes non visibles dans le code actif:
- `ai.task.created`
- `ai.task.routed`
- `ai.task.started`
- `ai.task.completed`
- `ai.task.failed`
- `ai.result.validation.requested`
- `ai.result.validation.accepted`
- `ai.result.validation.rejected`
- `sadaqa.recorded` / `path.sadaqa.recorded`
- `transaction.created` tel que documente dans `06`; le code legacy emet `vault.transaction.created`
- `vector.session.started`
- `vector.session.completed`
- `vector.manual.revenue.recorded`
- `vector.manual.expense.recorded`
- `vector.screenshot.uploaded`
- `vector.zone.recommendation.requested`
- `vector.last_drop_zone.recorded`
- `vector.recommendation.feedback.recorded`

Important: certains sont probablement futurs ou frontend/doc-design, mais ils ne sont pas emis aujourd'hui par le backend.

## 4. Contraintes `0030` et `0031`

### `0030` source_module allowed

Valeurs autorisees:
- `mission`
- `vault`
- `path`
- `pulse`
- `vector`
- `dashboard`
- `daily_plan`
- `system`
- `manual`

Cohesion:
- coherent avec modules produit principaux;
- coherent avec docs `04/05`;
- incoherent avec quelques sources reelles ou futures du backend:
  - pas de `ai`;
  - pas de `calendar`;
  - pas de `weekly_review`;
  - pas de `imperium` comme module global, alors que `ai_tasks` et WR utilisent `source_module="imperium"` ailleurs;
  - pas de `auth`, car auth a son journal separe.

Comme les services metier n'ecrivent pas dans `imperium_events`, cette contrainte ne casse pas les emissions actuelles. Elle bloquera cependant une migration des vrais events vers `imperium_events` sans decision de vocabulaire.

### `0031` hardening

Contraintes ajoutees:
- `event_type ~ '^[a-z][a-z0-9_]*$'`
- `schema_version = 'v1'`
- `payload_json IS NULL OR jsonb_typeof(payload_json) = 'object'`

Effet:
- durcissement fort de la fondation `/api/imperium/events`;
- aligne DB et Pydantic de cette fondation;
- contredit les regles dotted EVENT-002 et n8n subscription rule;
- interdit les vrais events metier actuels (`mission.started`, `day.plan.created`, etc.).

## 5. Restes perimes et doublons

### Doublon `events` / `imperium_events`

Oui, doublon fonctionnel a signaler.

`events`:
- existe depuis `0001`;
- contient l'enveloppe complete;
- recoit les vrais events metier;
- route publique `/api/events`;
- append-only durci depuis `0002/0003`;
- utilise par les FK legacy/recentes: `missions.created_by_event_id`, `missions.ended_by_event_id`, `vault_transactions.event_id`, etc.

`imperium_events`:
- existe depuis `0029`;
- route publique `/api/imperium/events`;
- enveloppe reduite;
- pas utilise par les services metier;
- son reader interne lit seulement cette table.

Le nom "canonical Imperium Event Read Path" dans `04` pointe vers `imperium_events`, alors que la realite metier ecrit dans `events`. C'est le principal risque de resynchronisation.

### Ancien modele `Event` vs `ImperiumEvent`

Il y a deux modeles ORM:
- `Event` dans `backend/app/models/event.py`, table `events`;
- `ImperiumEvent` dans `backend/app/models/imperium.py`, table `imperium_events`.

Ce n'est pas seulement un vieux reste inoffensif: les deux sont actifs, routes, testes, append-only, et representent deux contrats differents.

### `pgvector_memory`

Pas de table ou service actif `pgvector_memory` dans `backend/app` ou les migrations auditees.

Reste documentaire:
- `docs_master/75_MEMOIRE_VECTORIELLE_UNIFIEE.md` dit explicitement que `pgvector_memory` est supprime comme table au profit de `ai_memories`;
- plusieurs docs anciennes parlent encore de pgvector comme concept, mais pas comme table active dans ce module.

### Noms de modeles

Reste code transversal confirme:
- `backend/app/core/config.py`: default `qwen2.5:7b-instruct`;
- `backend/app/services/ai/providers/qwen.py`: recommendation `qwen2.5:7b-instruct`;
- `backend/app/services/imperium/weekly_review_conversation.py`: `model_hint/model_used = qwen2.5:7b-instruct`.

Ce n'est pas specifique au module Events, mais lie a la dette transversale deja relevee.

## Conclusion et actions

Verdict: (c) divergent.

Ce qui est solide:
- append-only DB sur `events`, `auth_events`, `imperium_events`;
- idempotence forte sur les deux journals;
- services events sans update/delete;
- tests postgres couvrent les triggers critiques.

Ce qui diverge:
- deux journals actifs;
- vraie emission metier dans `events`, pas dans `imperium_events`;
- `imperium_events` ne porte pas l'enveloppe EVENT-005;
- `imperium_events` impose snake_case alors que les regles transverses exigent dotted;
- `ai.result.stored` documente mais absent;
- le Vault recent canonique `imperium_vault_transactions` ne cree pas d'event, alors que le vieux ledger `/api/vault` cree `vault.transaction.created`.

Actions recommandees:

1. Trancher le journal canonique unique:
   - option probable: garder `events` comme event store transverse, car il a l'enveloppe complete et les emissions reelles;
   - ou migrer `imperium_events` vers l'enveloppe complete EVENT-005 et rebrancher tous les services.

2. Aligner le format `event_type`:
   - remplacer la contrainte snake_case de `imperium_events` par dotted si `imperium_events` reste canonique;
   - sinon deprecier `/api/imperium/events` ou le renommer comme journal local reduit non-canonique.

3. Ajouter une contrainte DB de format dotted sur `events.event_type` si `events` devient officiellement canonique.

4. Rebrancher les emissions metier sur le journal choisi:
   - missions;
   - daily plans;
   - path legacy ou Path V1;
   - Vault canonique recent;
   - calendar;
   - AI callbacks.

5. Emettre `ai.result.stored` dans le flow `receive_ai_result()` si le contrat AI reste valide.

6. Corriger la doc:
   - `08/06` et `04/05` doivent cesser de se contredire sur dotted vs snake_case;
   - documenter clairement `events` vs `imperium_events`, ou supprimer le doublon.

7. Tests a prevoir lors de la correction:
   - test `event_type` dotted accepte/refuse selon journal canonique;
   - test `receive_ai_result()` emet `ai.result.stored`;
   - test Vault recent cree l'event canonique;
   - test aucun service metier n'ecrit dans l'ancien journal apres migration.
