# GAP Analysis V1 - Infra / Mémoire / AI-tasks / Events

Date: 2026-06-29  
Scope: lecture docs + inspection ciblée code. Aucun code runtime modifié. Aucun test ajouté car la tâche produit un rapport documentaire, pas une fonctionnalité/correction.

## Base de comparaison

Docs lues:

- `docs_master/04_MVP_BACKEND_CONTRACTS.md`
- `docs_master/05_DATABASE_SCHEMA.md`
- `docs_master/06_N8N_WORKFLOWS.md`
- `docs_master/09_PGVECTOR_MEMORY_POLICY.md`
- `docs_master/30_AI_ROUTING_AND_SCORING_POLICY.md`
- `docs_master/31_AI_TASKS_AND_RESULTS_CONTRACT.md`
- `docs_master/38_VECTORIZATION_PIPELINE.md`
- `docs_master/45_N8N_RESPONSIBILITY_MATRIX.md`
- `docs_master/75_MEMOIRE_VECTORIELLE_UNIFIEE.md`

Code inspecté:

- `backend/app/models/ai.py`
- `backend/app/models/event.py`
- `backend/app/models/imperium.py`
- `backend/app/schemas/ai.py`
- `backend/app/schemas/events.py`
- `backend/app/services/ai/tasks.py`
- `backend/app/services/ai/memories.py`
- `backend/app/services/events/ingestion.py`
- `backend/app/services/imperium/events.py`
- routes `ai.py`, `internal.py`, `events.py`, `imperium_events.py`
- tests `test_ai_memories_foundation.py`, `test_ai_tasks_foundation.py`, `test_imperium_events_foundation.py`, `test_imperium_events_contracts.py`

Point de méthode: ce rapport ne rejuge pas toute la logique métier des modules. Il vérifie seulement le socle transversal: mémoire, tâches IA, journal d'événements.

## Les 3 listes

### 1. Déjà codé / socle réel

- `ai_tasks`, `ai_results`, `ai_result_validations` existent avec user scope, idempotency, statuts, callback interne HMAC et validation explicite.
- Qwen adapter foundation existe en dry-run avec sortie structurée, smoke endpoint public JWT et bridge interne HMAC pour n8n.
- Workflows n8n WR mock / Qwen dry-run existent et renvoient les résultats via backend, pas directement en DB.
- `ai_memories` existe comme stockage utilisateur explicite pour candidats mémoire WR validés, avec archive/supersede/read/list et idempotency.
- Le flow WR memory candidates existe: preview, approve/reject/edit, commit dry-run, commit réel.
- Un event store générique `events` existe avec event envelope dotted, `privacy_level`, `source_app`, correlation/causation et idempotency.
- Un journal `imperium_events` existe avec append-only, source modules bornés, read model paginé, filtres, user scope strict et non-exposition du `user_id`.

### 2. GAP V1 confirmé / à corriger avant branchement cerveau

- `ai_memories` codé n'est pas conforme au contrat canonique docs 09/38/75: pas d'`embedding`, pas de `embedding_model`, pas de `privacy_level`, pas de `memory_type`, pas de `learning_element_type`, pas de `is_active`, pas de `expires_at`, et modèle `kind/scope/status/visibility` spécifique WR.
- La mémoire est stockée en texte filtrable, mais pas en pgvector: pas d'embedding local, pas d'index HNSW, pas de recherche sémantique, pas de retrieval policy.
- La mémoire est encore trop WR-centrée: `source_module IN ('weekly_review')`, alors que la doc prévoit une mémoire commune cross-module.
- `ai_tasks.task_type` est libre: le catalogue des task types existe surtout côté documentation/schema résultat, mais pas comme contrat central strict pour toutes les créations de tâches.
- Le routing/scoring IA n'est pas branché au cycle `ai_tasks`: Qwen smoke existe, mais ne décide pas encore réellement du modèle pour les tâches entrantes.
- L'eventing transverse n'a pas encore de consumer/orchestrateur: les événements sont stockés, mais ne déclenchent pas encore les replan hooks, n8n subscriptions, projections ou handoffs Imperium.
- Il existe deux surfaces events concurrentes: `events` accepte les noms dotted canoniques; `imperium_events` accepte seulement snake_case. La doc n8n demande des event types dotted.

### 3. Hors V1 immédiat / ne pas bloquer le socle

- Appels cloud réels Sonnet/Opus/GPT/Gemini/Fable: hors socle V1 tant que le router local et les contrats backend ne sont pas stables.
- Mémoire conversationnelle brute du chatbot: hors V1 mémoire permanente; la doc 75 interdit de vectoriser la conversation brute.
- Vectorisation des signaux Vector, Vault weekly summaries, Pulse weekly summaries: V1.5 selon doc 38, sauf décision utilisateur contraire.
- Ephemeral vector store complet pour gros contextes temporaires: utile, mais à confirmer comme V1 ou V1.5.
- Observabilité coût/pricing multi-modèles complète: utile, mais secondaire après conformité `ai_tasks` + sécurité + validation.

## GAP V1 organisé en 3 sous-systèmes

### A. Mémoire

#### A1. `ai_memories` non conforme au canon pgvector

Ce qui manque:

- Colonnes canoniques `embedding vector(1024)`, `embedding_model`, `privacy_level`, `memory_type`, `learning_element_type`, `is_active`, `expires_at`, `supersedes_memory_id`, `correction_reason`.
- Alignement `source_app/source_table/source_id` avec docs 09/38 au lieu du modèle WR spécialisé `source_module/source_type/source_*`.
- Index vectoriel HNSW cosine et index `(user_id, source_app, memory_type, is_active)`.
- Migration ou stratégie de compatibilité pour les souvenirs WR déjà écrits au mauvais format.

Tables / contrats affectés:

- `ai_memories`
- `GET /api/imperium/memories`
- `GET /api/imperium/memories/{memory_id}`
- `POST /api/imperium/weekly-review/memory-candidates/commit`

MVP:

- Critique. C'est déjà du code actif qui écrit dans une table appelée `ai_memories`, donc la dette s'accumule à chaque commit mémoire WR.

#### A2. Pipeline d'embedding absent

Ce qui manque:

- Service d'embedding local V1.
- Génération embedding lors du commit mémoire validé.
- Refus explicite de commit si embedding impossible, ou mode transitoire documenté `text_only`.
- Métadonnées d'embedding stables et plan de ré-embedding si modèle changé.
- Tests DB pour dimension, présence embedding, privacy gate et retrieval filter.

Tables / contrats affectés:

- `ai_memories.embedding`
- `ai_memories.embedding_model`
- Service mémoire backend.

MVP:

- V1 mémoire oui. Sans embedding, la mémoire existe comme notes, pas comme mémoire vectorielle.

#### A3. Privacy gate mémoire incomplet

Ce qui manque:

- `privacy_level` obligatoire sur chaque souvenir.
- Règle de réduction/summarization avant stockage sensible.
- Blocage des données brutes interdites: transactions brutes, logs religieux privés, transcriptions audio, screenshots Bolt, notes santé sensibles.
- Séparation nette entre contenu permanent et données temporaires.

Tables / contrats affectés:

- `ai_memories`
- contrats WR memory candidate
- futurs contrats Pulse/Path/Vector/Vault memory candidates.

MVP:

- Critique pour respecter la règle personnelle: le système aide l'utilisateur sans transformer sa vie privée en base vectorielle brute.

#### A4. Mémoire commune cross-module absente

Ce qui manque:

- Autoriser les sources `imperium`, `vector`, `vault`, `pulse`, `path`, `weekly_review`.
- Contrat unique de création de memory candidates pour tous les modules.
- Source linkage vers tables canoniques, pas seulement WR.
- Retrieval par module avec privacy gate.

Tables / contrats affectés:

- `ai_memories`
- endpoint à définir: `POST /api/imperium/memory-candidates` ou équivalent interne.

MVP:

- Important, mais à faire après A1/A2. La mémoire commune ne doit pas propager le mauvais schéma.

### B. AI-tasks

#### B1. Catalogue `task_type/result_type` incompletement enforce

Ce qui manque:

- Catalogue canonique unique des `task_type` acceptés.
- Validation stricte de `AITaskCreate.task_type` contre ce catalogue.
- Mapping `task_type -> allowed result_type -> validation/apply contract`.
- Décision claire entre noms legacy (`weekly_review_analysis`) et noms docs (`weekly_report.interactive.start`, `imperium.daily_plan_assist`, etc.).

Tables / contrats affectés:

- `ai_tasks.task_type`
- `ai_results.result_type`
- `POST /api/ai/tasks`
- `POST /api/internal/ai/tasks/{task_id}/result`

MVP:

- Critique avant multiplication des workflows n8n. Sinon chaque workflow invente son propre vocabulaire.

#### B2. Routing/scoring Qwen non intégré au cycle des tâches

Ce qui manque:

- Appel router/scorer au moment opportun pour remplir `router_decision`.
- Score difficulté `/200` réellement stocké et exploité.
- Politique no-AI / Qwen / cloud appliquée par backend, pas seulement documentée.
- Clarification humaine quand Qwen retourne `requires_clarification`.
- Harmonisation modèle: les instructions projet indiquent Qwen 2.5 7B V1, la doc 30 parle Qwen 32B, le code default `qwen2.5:7b-instruct`.

Tables / contrats affectés:

- `ai_tasks.router_decision`
- `ai_tasks.model_hint`
- `POST /api/ai/qwen/smoke`
- futurs endpoints de lancement AI par module.

MVP:

- V1 oui pour le routeur local, mais le dry-run actuel est une fondation, pas le routeur opérationnel.

#### B3. Validation existe, mais `apply` métier manque

Ce qui manque:

- Après `ai_result_validations`, endpoints backend `apply` par domaine.
- Garanties que `accepted` ne signifie pas automatiquement "effet métier appliqué".
- Journalisation des décisions utilisateur liées à l'application réelle.
- Contrats pour transformer une proposition en mission, mémoire, règle, rapport, transaction draft, etc.

Tables / contrats affectés:

- `ai_result_validations`
- tables métier selon domaine.
- futurs endpoints `apply`.

MVP:

- Important. Sans `apply`, les AI-tasks restent une boîte à propositions; avec un `apply` mal cadré, l'IA risque de modifier la réalité sans garde.

#### B4. Orchestration n8n encore centrée WR

Ce qui manque:

- Endpoint ou outbox générique backend -> n8n pour les AI-tasks non-WR.
- Retry/failure policy partagée.
- Statut clair queued/running/failed quand n8n est indisponible.
- Liste officielle des workflows n8n par task/event.

Tables / contrats affectés:

- `ai_tasks`
- `ai_results`
- `ops/n8n/workflows/*`
- `app/services/integrations/n8n_client.py`

MVP:

- V1 socle oui, mais à limiter aux workflows vraiment nécessaires. Ne pas brancher n8n partout.

### C. Events

#### C1. Deux event stores concurrents à clarifier

Ce qui manque:

- Décision: `events` est-il le journal canonique global, ou `imperium_events` est-il le journal V1 officiel?
- Mapping ou fusion des deux modèles.
- Compatibilité avec la doc 06: event types dotted (`mission.failed`) au lieu de snake_case (`mission_failed`) pour la surface Imperium.
- Un seul point d'entrée recommandé pour les modules.

Tables / contrats affectés:

- `events`
- `imperium_events`
- `POST /api/events`
- `POST /api/imperium/events`

MVP:

- Critique. Les handoffs cross-module dépendent d'un vocabulaire event stable.

#### C2. Event ingestion sans consumer cross-module

Ce qui manque:

- Consumer Imperium pour événements Vault/Pulse/Path/Vector.
- Création de `imperium_replan_events` depuis événements pertinents.
- Déclenchement n8n seulement quand la matrice de responsabilité le justifie.
- Dead-letter / retry / statut de traitement.

Tables / contrats affectés:

- `events` ou `imperium_events`
- future table `imperium_replan_events`
- workflows n8n.

MVP:

- Central. Sans consumer, les modules parlent mais Imperium n'écoute pas.

#### C3. Catalogue d'événements absent

Ce qui manque:

- Liste canonique des event types par domaine.
- Schéma payload minimal par event type.
- Versioning payload au-delà de `schema_version = v1`.
- Règles d'idempotency par source.
- Mapping event -> consumer -> effet autorisé.

Tables / contrats affectés:

- `events.event_type`
- `imperium_events.event_type`
- docs 06/45 et contrats backend.

MVP:

- V1 oui. Le catalogue évite que chaque module invente ses signaux.

#### C4. Sécurité interne n8n/events incomplète

Ce qui manque:

- Clarifier comment n8n publie ou consomme les événements: JWT, HMAC interne, ou endpoint dédié.
- Endpoint event interne HMAC si n8n doit publier des événements.
- Replay window et `Idempotency-Key` uniformes sur les surfaces internes events.
- Secret rotation policy encore TODO dans doc 06.

Tables / contrats affectés:

- `POST /api/events`
- futur endpoint interne event si nécessaire.

MVP:

- Important avant exposition VPS réelle. n8n ne doit jamais devenir une porte d'écriture faible.

## V1 ? à confirmer

1. **Event store canonique**: garder `events`, garder `imperium_events`, ou migrer vers un seul journal global avec read models spécialisés?
2. **Format officiel event_type**: dotted partout (`mission.failed`) ou snake_case pour Imperium UI? La doc n8n demande dotted.
3. **Qwen V1 exact**: instructions projet = Qwen 2.5 7B; doc 30 = Qwen 32B; code = `qwen2.5:7b-instruct`. À normaliser avant catalogue modèle.
4. **Mémoire text-only transitoire**: autoriser temporairement `ai_memories` sans embedding, ou bloquer les commits mémoire jusqu'à migration canonique?
5. **Ephemeral vector store**: V1 nécessaire pour WR/chatbot, ou V1.5 après mémoire permanente?
6. **Source des memory candidates hors WR**: endpoint générique dès V1, ou seulement WR jusqu'à stabilisation?
7. **AI apply contracts**: V1 doit-il inclure seulement memory/report apply, ou aussi mission/replan/priority apply?
8. **n8n event subscription**: polling backend, outbox, webhook push, ou workflow déclenché explicitement par backend?
9. **Catalogue event payloads**: doc dédiée maintenant, ou section dans `06_N8N_WORKFLOWS.md`?
10. **Observabilité AI complète**: simple `ai_tasks` statuses en V1, ou tables `ai_call_logs`/coûts dès le socle?

## Suggestion catalogue

Ajouter en fin de campagne gap une entrée catalogue "INFRA-SOCLE" ou "BRAIN-INFRA" qui regroupe:

- `ai_memories` canonique pgvector.
- `memory_candidates` cross-module.
- `ai_tasks`, `ai_results`, `ai_result_validations`.
- `ai_task_catalog` et mapping task/result/apply.
- `events` canonique + event payload catalog.
- `imperium_replan_events` comme consumer métier Imperium.
- `n8n_workflow_catalog` avec trigger, input, output, backend callbacks, retry, privacy gate.

Suggestion de docs à créer ou consolider:

- `docs_master/76_INFRA_MEMORY_AI_EVENTS_CONTRACT.md`
- `docs_master/77_EVENT_TYPE_CATALOG_V1.md`
- `docs_master/78_AI_TASK_CATALOG_V1.md`

Raison: aujourd'hui les règles sont réparties entre docs 06/09/30/31/38/45/75 et le code a déjà divergé. Un catalogue unique éviterait de recoder un socle incohérent.
