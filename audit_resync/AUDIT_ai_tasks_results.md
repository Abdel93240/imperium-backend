# AUDIT ai_tasks_results - infrastructure taches/resultats IA

Date : 2026-06-27

Perimetre lu :
- Migration : `backend/alembic/versions/20260430_0012_ai_tasks_results_foundation.py`
- Migration ownership : `backend/alembic/versions/20260503_0018_ai_user_id_not_null.py`
- ORM : `backend/app/models/ai.py` (`AITask`, `AIResult`, `AIResultValidation`; `AIMemory` ignore sauf recherche de restes perimes)
- Service : `backend/app/services/ai/tasks.py`
- Provider local : `backend/app/services/ai/providers/qwen.py`
- Routes de contexte : `backend/app/api/v1/routes/ai.py`, `backend/app/api/v1/routes/internal.py`
- Docs : `docs_master/31_AI_TASKS_AND_RESULTS_CONTRACT.md`, `docs_master/16_AI_BACKEND_LAYER_OVERVIEW.md`, `docs_master/02_AI_ROUTING_POLICY.md`, `docs_master/30_AI_ROUTING_AND_SCORING_POLICY.md`

## Verdict global

Verdict : **(c) divergent de perimetre par rapport au contrat V1 complet, mais fondation saine et prudente**.

Le code implemente correctement la fondation Patch 2A/2E : stockage `ai_tasks`, callback `ai_results`, validations explicites, idempotency de base, dry-run Qwen, pas d'ecriture canonique automatique. En revanche il n'implemente pas encore le contrat V1 complet de `docs_master/31` section 7 ni le cycle de vie complet de `docs_master/16` section 4 : pas de vrai claim n8n, pas de routage/scoring persiste, pas d'event `ai.result.stored`, pas de statut `postponed`, pas de priorite `INTERACTIVE/BACKGROUND`, pas de file a priorites, pas de verrou de session.

Conclusion courte : **ce n'est pas un conflit destructeur ; c'est une pile a coder.** Le code actuel est une fondation storage/callback, pas encore le scheduler/concurrency layer du cerveau IA.

## Proprietaire du schema

Le vrai proprietaire fonctionnel du schema `ai_tasks` / `ai_results` est `docs_master/31_AI_TASKS_AND_RESULTS_CONTRACT.md`.

Raison :
- `docs_master/16_AI_BACKEND_LAYER_OVERVIEW.md` dit que les trois tables AI sont definies en detail dans le doc 31.
- `docs_master/02_AI_ROUTING_POLICY.md` est deprecie et renvoie vers les docs 30/31/32.
- `docs_master/05_DATABASE_SCHEMA.md` ne possede pas effectivement le schema colonne par colonne de ces tables.

Proprietaire executable : migrations Alembic + ORM. A noter : la migration 0012 cree `user_id` nullable, mais la migration 0018 corrige ensuite `user_id NOT NULL` sur `ai_tasks`, `ai_results`, `ai_result_validations`; l'ORM est aligne avec 0018.

## Partie 1 - Schema

### `ai_tasks` - ecart colonne par colonne code <-> doc 31 section 7.1

| Colonne / sujet | Code migration 0012 + ORM | Doc 31 §7.1 | Ecart |
|---|---|---|---|
| `id` | `UUID PK DEFAULT gen_random_uuid()` | `id UUID PK` | Conforme. |
| `user_id` | 0012 nullable, puis 0018 `NOT NULL`; ORM `nullable=False` | `UUID FK` | Conforme apres 0018. |
| `task_type` | `Text NOT NULL`; pas de check DB de registre | `VARCHAR(64)` | Present. Type plus large; registre non force en DB. |
| `source` | Absent | `source (app|cron|webhook|backend|external)` | Manquant. Le code a `source_module`, mais ce n'est pas le meme concept. |
| `source_module` | Present, check `imperium/vector/vault/pulse/path/system` | Absent dans §7.1 | Extra code utile pour l'ecosysteme, mais non decrit par le schema §7.1. |
| `source_ref_type` | Absent | Present nullable | Manquant. Souvent encode dans `prepared_payload` selon les flows WR. |
| `source_ref_id` | Absent | Present nullable | Manquant. |
| `trigger_type` | Absent | `button/schedule/db_event/external/email/media` | Manquant. |
| `status` | `queued/running/result_received/validated/rejected/failed/cancelled` | `queued/routing/waiting_for_user_clarification/waiting_for_user_validation/running/completed/failed/cancelled/expired` | Divergent. `postponed` demande par doc 16 n'est pas accepte non plus. |
| `difficulty_score` | Absent | `INTEGER NULL 0..200` | Manquant. Peut etre enfoui dans `router_decision`, mais pas requetable. |
| `score_breakdown` | Absent | `JSONB NULL` | Manquant comme colonne dediee. |
| `router_decision` | `JSONB NULL` | Pas dans §7.1 sous ce nom | Extra code. Utile, mais ne remplace pas les colonnes de routage requetables. |
| `routing_model` | Absent | `VARCHAR(64)` ex. `qwen3:32b` | Manquant. |
| `selected_model` | Absent | `VARCHAR(64)` | Manquant. |
| `fallback_model` | Absent | `VARCHAR(64) NULL` | Manquant. |
| `model_hint` | `Text NULL` | Absent | Extra code / ancien contrat. |
| `requires_user_validation` | Absent | `BOOLEAN NOT NULL DEFAULT FALSE` | Manquant. |
| `privacy_level` | `Text NULL` | Pas dans §7.1 | Present dans le code, mais non contraint. Coherent avec la vision privacy, a documenter/normaliser. |
| `idempotency_key` | `Text NULL`, unique partiel `(user_id, idempotency_key)` si non null; service public exige header | `VARCHAR(128) NOT NULL`, unique `(user_id, idempotency_key)` | Presque conforme fonctionnellement via API, mais DB autorise encore `NULL`. |
| `input_payload` | `JSONB NOT NULL` | `JSONB NULL` | Present, plus strict que doc. |
| `input_payload_hash` | Absent | `VARCHAR(64) NULL` | Manquant. Le service calcule un hash en memoire pour comparer les replays, mais ne le stocke pas. |
| `prepared_payload` | `JSONB NULL` | Absent dans §7.1 | Extra code. Necessaire aux payloads n8n WR documentes dans les patches 2C/2H/2J/2O. |
| `created_at` | `DateTime timezone NOT NULL DEFAULT now()` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Conforme. |
| `updated_at` | Present | Absent dans §7.1 | Extra code sain. |
| `started_at` | Present nullable | Present nullable | Conforme. |
| `completed_at` | Present nullable | Present nullable | Conforme. |
| `failed_at` | Present nullable | Present nullable | Conforme. |
| `error_code` | `Text NULL` | `VARCHAR(64) NULL` | Present, type plus large. |
| `error_message` | `Text NULL` | `TEXT NULL` | Conforme. |
| priorite `INTERACTIVE/BACKGROUND` | Absent | Doc 16 §4A exige une priorite sur chaque `ai_task` | Manquant. |
| verrou de session | Absent | Doc 16 §4A exige un verrou de session logique | Manquant. |

### `ai_results` - ecart colonne par colonne code <-> doc 31 section 7.2

| Colonne / sujet | Code migration 0012 + ORM | Doc 31 §7.2 | Ecart |
|---|---|---|---|
| `id` | `UUID PK DEFAULT gen_random_uuid()` | `id UUID PK` | Conforme. |
| `user_id` | 0012 nullable, puis 0018 `NOT NULL`; ORM `nullable=False` | `UUID FK` | Conforme apres 0018. |
| lien task | `task_id UUID NOT NULL FK ai_tasks(id) ON DELETE CASCADE` | `ai_task_id UUID FK -> ai_tasks(id)` | Conforme fonctionnellement, nom different. |
| `result_type` | `Text NOT NULL`; allowlist Pydantic dans callback | `VARCHAR(64)` | Present. Pas de check DB. |
| `status` | `received/pending_validation/accepted/rejected/superseded`, default `pending_validation` | Doc parle surtout `validation_status` avec `not_required/pending_user_validation/accepted/rejected/superseded/expired` | Divergent : le code fusionne statut resultat et validation. |
| `model_used` | Present nullable | Present | Conforme. |
| `provider` | Present nullable | `model_provider` | Present sous autre nom. |
| `model_version` | Absent | Present nullable | Manquant. |
| `input_hash` | Absent | Present nullable | Manquant. |
| `output_hash` | Absent | Present nullable | Manquant. |
| `confidence` | `NUMERIC(5,4) NULL`, check 0..1 | `confidence_score NUMERIC(4,3) NULL` | Present sous autre nom/precision. |
| `risk_score` | Absent | Present nullable | Manquant. |
| `requires_user_validation` | Absent | `BOOLEAN NOT NULL DEFAULT FALSE` | Manquant; implicite via `status=pending_validation`. |
| `validation_status` | Absent | Present | Manquant comme colonne dediee. |
| `validated_by_user_at` | Absent | Present nullable | Manquant; decision historisee dans `ai_result_validations.created_at`. |
| `result_payload` | `JSONB NOT NULL` | `result_json JSONB NOT NULL` | Conforme fonctionnellement, nom different. |
| `summary_text` | Absent | Present nullable | Manquant. |
| `metadata` | Absent | Present nullable | Manquant. Le code a `raw_payload`, mais ce n'est pas la meme exposition. |
| `raw_payload` | Present nullable, exclu des schemas publics | Absent dans §7.2 | Extra code sain pour audit/debug interne. |
| `input_tokens` | Absent | Present nullable | Manquant. |
| `output_tokens` | Absent | Present nullable | Manquant. |
| `estimated_cost_eur` | Absent | Present nullable | Manquant. |
| `latency_ms` | Absent | Present nullable | Manquant. |
| `idempotency_key` | Present nullable; unique `(task_id, idempotency_key)` | Pas dans §7.2, mais callback doc 31 exige idempotence `(task_id, Idempotency-Key)` | Conforme au callback, extra par rapport au tableau §7.2. |
| `created_at` | Present | Present | Conforme. |
| `updated_at` | Present | Absent | Extra code sain. |

### Liens task <-> result

Conforme sur le minimum :
- `ai_results.task_id` reference `ai_tasks.id` avec `ON DELETE CASCADE`.
- `AIResult.user_id` est repris depuis `AITask.user_id` dans `receive_ai_result()`.
- `ai_result_validations` lie `result_id` et `task_id`.

Limites :
- Pas de relation ORM explicite `AITask.results`, seulement des FKs.
- Pas d'unicite "un seul resultat final actif" au niveau generique; logique laissee aux flows metier.
- L'idempotence validation n'est pas stockee dans `ai_result_validations` malgre doc 31 §7.3 (`idempotency_key` manquant sur validations).

### Statuts

Statuts `ai_tasks` codes :

```text
queued, running, result_received, validated, rejected, failed, cancelled
```

Statuts doc 31 §7.1 :

```text
queued, routing, waiting_for_user_clarification, waiting_for_user_validation,
running, completed, failed, cancelled, expired
```

Statuts doc 16 §4A/§12.7 ajoutes :

```text
postponed
```

Ecart : `postponed` n'existe pas dans le check DB/ORM/service. `routing`, `waiting_*`, `completed`, `expired` n'existent pas non plus. Le code a ses propres statuts `result_received`, `validated`, `rejected`.

## Partie 2 - Cycle de vie et concurrence

### Cycle de vie doc 16 §4

| Etape doc 16 | Etat code |
|---|---|
| Trigger | Partiel. Routes publiques et Weekly Review creent des `AITask`. |
| Backend cree `ai_task(status=queued, idempotency_key)` | Oui. `create_ai_task()` cree `queued`; les flows WR creent aussi des taches directes. |
| Backend POST signed webhook to n8n | Partiel et surtout WR. Ce n'est pas generique dans `services/ai/tasks.py`. |
| n8n claims the task | Non code. Il n'existe pas de claim interne atomique ni de selection de prochaine tache. `mark-running` est une transition authentifiee par `task_id`, pas un claim de file. |
| Local model routes + scores `/200` | Provider Qwen sait produire un `QwenRoutingDecision`, mais ce n'est pas branche au lifecycle generique et ce n'est pas persiste en colonnes dediees. |
| Chosen model executes | Dry-run seulement dans les workflows WR/Qwen actuels; pas de vrai chainage modeles. |
| n8n callback backend | Oui. `POST /api/internal/ai/tasks/{task_id}/result` HMAC + idempotency appelle `receive_ai_result()`. |
| Backend stores `ai_result` | Oui. Status resultat `pending_validation`, task `result_received`. |
| Event emitted `ai.result.stored` | Non visible dans `receive_ai_result()`. |
| UI poll/push | Partiel via endpoints read/WR conversation, pas generique liste `GET /api/ai/tasks?status=...`. |
| User validates | Oui via `/api/ai/results/{id}/validate|reject`. |
| Canonical write after validation | Pas generique. Certaines couches WR ont leur logique specifique; l'AI result reste bien non canonique par defaut. |

### Concurrence doc 16 §4A

Etat : **non code, a coder**.

Constats :
- Aucun champ `priority`, `priority_level`, `task_priority`, `INTERACTIVE`, `BACKGROUND` sur `ai_tasks`.
- Aucun index de queue par priorite.
- Aucun statut `postponed` dans le check DB.
- Aucun endpoint de claim de queue.
- Aucun `SELECT ... FOR UPDATE SKIP LOCKED` / `with_for_update()` sur `AITask`.
- Aucun verrou de session AI. Le `locked_until` existant appartient a l'idempotency store, pas a un verrou GPU/session IA.
- Aucune notion de `session_lock_id`, `session_id`, `resource_lock`, `lock_owner`, `lock_expires_at` sur `ai_tasks`.

Interpretation : la section 4A est recente et etend le lifecycle. L'absence dans le code n'est pas un conflit avec une implementation existante ; c'est une backlog implementation claire.

Champ priorite : **n'existe pas encore** dans la migration 0012, l'ORM, les schemas, le service ou les workflows n8n audites.

## Partie 3 - Provider local `qwen.py`

Etat : **adaptateur fonctionnel en fondation, dry-run par defaut, mais nomenclature modele perimee**.

Ce qui fonctionne :
- `QwenClient` expose `classify_task()`, `score_task()`, `prepare_prompt_for_strong_model()`, `generate_weekly_summary()`.
- Dry-run par defaut si `QWEN_DRY_RUN=true` ou `QWEN_ENABLED=false`.
- Le dry-run retourne des contrats Pydantic structures : `QwenRoutingDecision`, `QwenScoreBreakdown`, `QwenWeeklySummary`.
- En mode reel, l'adaptateur appelle un endpoint Ollama-compatible : `POST {QWEN_BASE_URL}/api/generate`.
- Le payload Ollama utilise `model`, `prompt`, `stream=false`, `format=json`.
- Gestion d'erreur presente : base URL manquante, HTTP/timeout, JSON invalide, JSON non objet, shape non supportee.
- Aucun output Qwen n'ecrit directement en base ni ne devient canonique.

Limites :
- Pas de support vLLM natif. Le connecteur est Ollama-compatible uniquement.
- Pas de retry, backoff, circuit breaker, health check ou mesure `latency_ms`.
- Pas de persistance automatique du `router_decision` dans `ai_tasks`.
- Les erreurs provider remontent en `502` dans les routes smoke, mais ne marquent pas automatiquement une `AITask` failed sauf si un flow appelant le fait.

Ecart modele local :
- Doc 30 canonique : **Qwen 32B** est le modele local V1, remplace Qwen 2.5 7B.
- Doc 16 runtime : `qwen3:32b`.
- Doc 31 config Patch 2E : `QWEN_MODEL=qwen3:32b`.
- Code config : `qwen_model = "qwen2.5:7b-instruct"`.
- Prompt provider : "You are Qwen 2.5 7B Instruct inside Imperium."
- Dry-run routing : `recommended_model = "qwen2.5:7b-instruct"` sous score 60.

Conclusion provider : la plomberie est utilisable pour tester puis brancher un endpoint local, mais elle doit etre renommee/alignee avant exploitation GPU/V100 reelle.

## Partie 4 - Restes perimes

### Noms de modeles anciens

Restes trouves :
- `backend/app/core/config.py` : default `qwen2.5:7b-instruct`.
- `backend/app/services/ai/providers/qwen.py` : prompt Qwen 2.5 7B + recommendation `qwen2.5:7b-instruct`.
- `backend/app/services/imperium/weekly_review_conversation.py` : `model_hint/model_used = qwen2.5:7b-instruct`.
- `ops/n8n/workflows/wr_interactive_start_qwen_dry_run.json` et `wr_answers_integrate_qwen_dry_run.json` : callbacks dry-run avec `model_used: qwen2.5:7b-instruct`.
- `backend/tests/test_qwen_adapter.py` : test qui accepte explicitement `qwen2.5:7b-instruct`.

Statut : dette de nomenclature/code. Le doc 30 a deja tranche : Qwen 32B / `qwen3:32b`.

### `pgvector_memory`

Pas de table ou service actif `pgvector_memory` trouve dans le perimetre code audite. Le code actuel parle de `ai_memories`, et les docs recentes repettent que les AI results/WR drafts ne doivent pas ecrire automatiquement en pgvector.

Statut : pas de reste actif `pgvector_memory` dans ce module. La dette pgvector est plutot dans `ai_memories` (deja audite separement), pas dans `ai_tasks/results`.

### `doc 02`

`docs_master/02_AI_ROUTING_POLICY.md` est deprecie. Il ne doit plus etre utilise comme source de verite ; il renvoie explicitement vers docs 30/31/32.

## Conclusion

Verdict final : **(c) divergent de perimetre, a coder, pas a reparer comme bug isolé**.

Le module `ai_tasks/results` est une bonne fondation de stockage/callback :
- idempotence de creation task et callback result ;
- resultats non canoniques ;
- validations explicites ;
- HMAC pour callbacks internes ;
- provider Qwen dry-run structure.

Mais il ne correspond pas encore au cerveau IA cible :
- schema V1 complet doc 31 §7 non implemente ;
- lifecycle doc 16 §4 incomplet ;
- concurrence doc 16 §4A absente ;
- Qwen local encore nomme 2.5 7B dans le code ;
- routage `/200` pas branche a la queue.

Actions recommandees :

1. Ajouter une migration de resync `ai_tasks` : `priority` (`interactive/background`), `postponed` dans les statuts, champs routage requetables (`difficulty_score`, `score_breakdown`, `routing_model`, `selected_model`, `fallback_model`, `requires_user_validation`) ou documenter officiellement que `router_decision` JSONB est le stockage V1.
2. Concevoir le claim interne : endpoint HMAC `POST /api/internal/ai/tasks/claim`, selection `queued/postponed` par priorite puis FIFO, verrou SQL atomique.
3. Ajouter le verrou de session : champ/table de session lock avec `lock_key/session_id`, owner, expiration, release explicite, et tests de non-interleaving background pendant session interactive.
4. Aligner Qwen : remplacer defaults/prompts/tests/workflows de `qwen2.5:7b-instruct` vers le role local canonique (`qwen3:32b` / Qwen 32B) ou vers un alias role stable (`local_router`) si on veut eviter de recoder au prochain modele.
5. Brancher `QwenRoutingDecision` dans le lifecycle : persister score/decision au claim ou avant execution, puis stocker provider/model/version/cout/latence dans `ai_results`.
6. Ajouter event append-only `ai.result.stored` si la couche events est canonique pour l'audit.
7. Decider si le schema doc 31 §7 reste "recommended fields" futur ou devient obligatoire. Si obligatoire, migrer; sinon mettre a jour doc 31 pour refleter la fondation reelle + backlog explicite.
