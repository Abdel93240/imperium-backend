# AUDIT Weekly Review WR-a — schema code ↔ docs

Date: 2026-06-27

Scope: audit lecture seule du schema Weekly Review uniquement. Aucune logique de service analysee. Aucun code backend modifie.

## Verdict court

Verdict: **(b) leger decalage**, avec une dependance memoire **(c) divergente** deja connue.

Raison:

- Les tables WR principales (`imperium_weekly_review_sessions`, `imperium_weekly_review_messages`, `imperium_weekly_review_final_reports`) suivent globalement le contrat evolutif du doc 32.
- Le schema WR n'est pas documente colonne par colonne dans `05_DATABASE_SCHEMA.md`; le proprietaire reel est donc **doc 32** pour WR, mais il agit surtout comme contrat workflow/API, pas comme dictionnaire de schema strict.
- Le lien WR -> memoire existe dans le code via `imperium_memory_candidate_decisions` puis `ai_memories.source_decision_id`, mais la table cible `ai_memories` est deja auditee **(c) divergente** face aux docs 75/09. Le lien est coherent avec le code actuel, pas avec le modele canonique vectoriel documente.

## Sources lues

- Docs: `docs_master/32_WR_INTERACTIVE_WORKFLOW.md`, `docs_master/09_PGVECTOR_MEMORY_POLICY.md`, `docs_master/75_MEMOIRE_VECTORIELLE_UNIFIEE.md`, `docs_master/05_DATABASE_SCHEMA.md`
- Migrations WR: `20260427_0010`, `20260430_0013`, `20260430_0014`, `20260501_0015`, `20260501_0016`
- ORM WR: `backend/app/models/imperium.py`
- Schemas Pydantic WR: `backend/app/schemas/weekly_review.py`
- Lecture minimale de la cible memoire: `backend/alembic/versions/20260502_0017_ai_memories_foundation.py`, `backend/app/models/ai.py::AIMemory`

## Proprietaire du schema WR

| Sujet | Proprietaire attendu | Etat reel |
|---|---|---|
| Workflow WR, etats, conversation, rapports, candidats memoire | `docs_master/32_WR_INTERACTIVE_WORKFLOW.md` | Proprietaire reel et le plus complet. |
| Schema DB colonne par colonne | `docs_master/05_DATABASE_SCHEMA.md` devrait naturellement le porter | Non present: doc 05 contient des notes heterogenes, pas les tables WR. |
| Table cible memoire `ai_memories` | Doc 75 verrouille la decision; doc 09 possede le schema canonique | Proprietaire clair cote doc, mais code divergent selon audit `AUDIT_ai_memories.md`. |

Conclusion proprietaire: **doc 32 est le proprietaire de fait du schema WR**, mais il faut soit enrichir doc 05 en dictionnaire de schema, soit acter que doc 32 possede aussi les colonnes WR.

## Table `imperium_weekly_review_states`

Role code: readiness/banner state hebdomadaire.

Doc: doc 32 decrit le timing du mardi 20:00, l'etat passif/actif du banner et l'endpoint `/state`, mais ne donne pas le schema colonne par colonne.

| Colonne / contrainte | Code migration/ORM | Doc 32 / 05 | Ecart |
|---|---|---|---|
| `id` | UUID PK default `gen_random_uuid()` | Non liste | Present code / absent doc. |
| `user_id` | UUID FK `users.id ON DELETE CASCADE`, non null | JWT/user-owned implicite | Conforme implicite, pas documente colonne. |
| `week_start` | `Date`, non null | WR hebdomadaire, `week_start` dans endpoints | Conforme implicite. |
| `ready` | Boolean non null default false | Banner passif/actif | Conforme conceptuellement. |
| `ready_at` | timestamptz nullable | Non liste | Present code / absent doc. |
| `launched` | Boolean non null default false | User starts/launches WR | Conforme conceptuellement. |
| `launched_at` | timestamptz nullable | Mentionne lancement via session | Present code; aussi present dans sessions. Dette de duplication conceptuelle a clarifier, pas forcement bug schema. |
| `analysis_status` | `String(32)` non null default `pending` | Non liste dans doc 32 actuel | Present code / absent doc. Possible ancien vestige pre-conversation. |
| `analysis_completed_at` | timestamptz nullable | Non liste | Present code / absent doc. |
| `created_at`, `updated_at` | timestamptz non null default now | Non liste | Present code / absent doc. |
| Unique `(user_id, week_start)` | Oui | Implicite: une readiness state par user/semaine | Conforme implicite. |
| Index `(user_id, week_start)`, partial ready true | Oui | Non liste | Present code / absent doc. |

Analyse: schema plausible pour `/state`, mais **sous-documente**. `analysis_status` et `analysis_completed_at` ressemblent a un reste d'ancien modele "analysis" plutot qu'au workflow chatbot actuel.

## Table `imperium_weekly_review_sessions`

Role code: session WR backend-owned, etat conversationnel, liens AI task/result.

| Colonne / contrainte | Code migration/ORM | Doc 32 / 05 | Ecart |
|---|---|---|---|
| `id` | UUID PK default `gen_random_uuid()` | `session_id` partout | Conforme. |
| `user_id` | UUID FK `users.id`, non null | JWT ownership | Conforme implicite. |
| `week_start` | `Date`, non null | Present dans endpoints/payloads | Conforme. |
| `week_end` | `Date`, non null | Present dans payloads/read models | Conforme. |
| `status` | Text non null default `ready`; check avec `ready`, `launched`, `preparing_initial_summary`, `initial_summary_ready`, `waiting_for_user_answer`, `conversation_active`, `integrating_answers`, `draft_ready`, `revision_requested`, `final_ready`, `approved`, `stored`, `cancelled`, `failed` | Doc 32 liste ces etats apres patch chatbot; UI states plus reduits se projettent depuis eux | Conforme au dernier etat documente. |
| `launched_at` | timestamptz nullable | Lancement WR explicite | Conforme. |
| `completed_at` | timestamptz nullable | "completed"/canonical WR conceptuel, mais doc insiste surtout `stored_at` sur report | Present code / doc peu precise. |
| `failed_at` | timestamptz nullable | Failure handling | Conforme. |
| `error_code`, `error_message` | Text nullable | Failure/status recoverable | Conforme conceptuel; attention aux messages sensibles, logique non auditee ici. |
| `current_ai_task_id` | UUID FK `ai_tasks.id` nullable | Current AI task summary/read model | Conforme. |
| `initial_ai_result_id` | UUID FK `ai_results.id` nullable | Initial result slim summary | Conforme. |
| `final_ai_result_id` | UUID FK `ai_results.id` nullable | Final result slim summary | Conforme. |
| `created_at`, `updated_at` | timestamptz non null default now | Non liste | Present code / absent doc schema. |
| Unique `(user_id, week_start)` | Oui | Une session par user/semaine | Conforme. |
| Index `(user_id,status)`, `(user_id,week_start)` | Oui | Non liste | Present code / absent doc. |

Etat WR conforme au doc 32: **oui pour la liste stockee**, incluant `conversation_active` ajoute par 0016. Le doc contient plusieurs couches UI (`closed`, `not_started`) qui sont des projections/read models, pas des valeurs DB attendues.

## Table `imperium_weekly_review_messages`

Role code: tours de conversation WR backend-owned.

| Colonne / contrainte | Code migration/ORM/Pydantic | Doc 32 / 05 | Ecart |
|---|---|---|---|
| `id` | UUID PK default `gen_random_uuid()` | Message id implicite | Conforme implicite. |
| `session_id` | UUID FK `imperium_weekly_review_sessions.id ON DELETE CASCADE` | Messages appartiennent a une session | Conforme. |
| `user_id` | UUID FK `users.id`, non null | JWT ownership | Conforme. |
| `role` | Text check `user/qwen/system/opus/backend` | Doc 32 storage model dit user/backend/local-model/high-reasoning-model/system; audit patch mentionne encore messages assistant `qwen`/`opus` | Fonctionnellement documente par patch 6E, mais noms de roles couples a des modeles concrets. Preferer a terme des roles generiques (`local_model`, `high_reasoning_model`). |
| `message_type` | Text check `user_answer`, `clarification_question`, `initial_summary`, `draft`, `revision_request`, `final_report`, `system_note`, `chat_message`, `assistant_followup`, `final_report_draft` | Doc 32 liste messages initiaux/draft/final, puis chatbot ajoute `chat_message`, `assistant_followup`, `final_report_draft` | Conforme au doc 32 recent. |
| `content` | Text nullable; Pydantic max 12000 | User/assistant text | Conforme. |
| `payload` | JSONB nullable | Payload/display data | Conforme implicite. |
| `ai_task_id` | UUID FK `ai_tasks.id` nullable | AI task links | Conforme. |
| `ai_result_id` | UUID FK `ai_results.id` nullable | AI result links | Conforme. |
| `created_at` | timestamptz non null default now | Ordered by `created_at ASC` | Conforme. |
| Index `(session_id, created_at)`, `(user_id, created_at)` | Oui | Ordered/bounded reads | Conforme utile, non liste colonne par colonne. |
| Pydantic public create | `role=Literal["user"]`; `message_type` limite a `user_answer/chat_message/revision_request` | Audit patch 6E impose public user-originated only | Conforme. |

Restes perimes: pas de `pgvector_memory` ici. Les roles `qwen` et surtout `opus` sont des noms de modele/provider dans le schema; ils sont encore cites dans doc 32 audit patch, mais restent une dette de nomenclature si la strategie modele doit rester interchangeable.

## Table `imperium_weekly_review_final_reports`

Role code: candidats de rapport final WR, historiques, non canoniques tant que non approuves/stores.

| Colonne / contrainte | Code migration/ORM/Pydantic | Doc 32 / 05 | Ecart |
|---|---|---|---|
| `id` | UUID PK default `gen_random_uuid()` | `report_id` / final report id | Conforme. |
| `session_id` | UUID FK `imperium_weekly_review_sessions.id ON DELETE CASCADE` | Rapport lie a session | Conforme. |
| `user_id` | UUID FK `users.id`, non null | User-owned | Conforme. |
| `week_start`, `week_end` | Date non null | Present dans endpoints/history/export | Conforme. |
| `status` | Text default `draft`; check `draft/approved/stored/superseded` | Doc 32 statuses final candidates identiques | Conforme. |
| `report_payload` | JSONB non null | Structured extracts/report payload | Conforme. |
| `report_markdown` | Text non null | Markdown export; fallback si blank cote endpoint | Conforme schema, mais non null force une valeur. |
| `memory_candidates` | JSONB nullable | Candidates may come from payload or column | Conforme. |
| `approved_at` | timestamptz nullable | Approval sets `approved_at` | Conforme. |
| `stored_at` | timestamptz nullable | Store sets `stored_at` | Conforme. |
| `source_ai_result_id` | UUID FK `ai_results.id` nullable | Candidate source AI result | Conforme. |
| `created_at`, `updated_at` | timestamptz non null default now | History/sorting | Conforme. |
| Status check | `draft/approved/stored/superseded` | Doc 32 same | Conforme. |
| Unique active session | Partial unique on `session_id` where `status IN ('draft','approved','stored')` | Patch 2U dit active candidate may be `draft`, `approved`, or `stored`; later patch 5I dit active mutable report is only `draft` or `approved`, stored terminal | Code suit l'ancien vocabulaire "active includes stored". Doc 32 est auto-tendu sur le mot active. Schema reste compatible avec "un stored par session/semaine", mais le vocabulaire doit etre clarifie. |
| Unique active user/week | Partial unique on `(user_id, week_start)` where `status IN ('draft','approved','stored')` | One active candidate per user/week | Conforme selon 2U; meme nuance sur `stored`. |
| Index `(user_id,status)`, `(user_id,week_start)` | Oui | History/filtering | Conforme utile, pas documente en 05. |

Final report / candidate history conforme au doc 32: **globalement oui**. L'historisation est presente via suppression des uniques strictes et partial indexes. Point a clarifier: `stored` est inclus dans les uniques "active", alors que les derniers paragraphes distinguent `active_reports_count` (`draft/approved`) et `stored_reports_count`.

## Table `imperium_memory_candidate_decisions`

Role code: decisions utilisateur sur les candidats memoire issus d'un WR final report.

| Colonne / contrainte | Code migration/ORM/Pydantic | Doc 32 / docs memoire | Ecart |
|---|---|---|---|
| `id` | UUID PK default `gen_random_uuid()` | `decision_id` dans read/commit-ready | Conforme. |
| `user_id` | UUID FK `users.id`, non null | JWT ownership; audit patch impose filtre SQL user | Conforme. |
| `report_id` | UUID FK `imperium_weekly_review_final_reports.id ON DELETE CASCADE` | Decisions par final report | Conforme. |
| `session_id` | UUID FK `imperium_weekly_review_sessions.id ON DELETE CASCADE` | Decisions rattachables a session WR | Conforme. |
| `candidate_id` | Text non null | Candidate id dans endpoints | Conforme. |
| `decision` | Text check `approved/rejected/edited` | Doc 32: one decision: approved/rejected/edited | Conforme. |
| `source` | Text default/check `weekly_review` | Source weekly_review | Conforme. |
| `original_candidate` | JSONB non null | Original candidate preserve | Conforme. |
| `edited_candidate` | JSONB nullable | Edited decision stores edited candidate separately | Conforme. |
| `reason` | Text nullable | Reason payloads | Conforme. |
| `payload` | JSONB nullable | Extra audit payload | Present code / doc partielle. |
| `idempotency_key` | Text nullable | POST requires Idempotency-Key | Conforme utile. |
| `created_at`, `updated_at` | timestamptz non null default now | `decided_at`/history | Conforme. |
| Unique `(user_id, report_id, candidate_id)` | Oui | One decision per candidate | Conforme. |
| Index user/created | Migration uses `created_at DESC`; ORM declares plain `created_at` | Difference migration vs ORM declaration. Pas critique fonctionnel, mais l'ORM metadata ne reflete pas exactement l'index expressionnel. |
| Index user/decision, report, session, candidate | Oui | Read/index endpoints | Conforme utile. |
| Lien direct vers `ai_memories` | Aucun champ `memory_id` dans cette table | Doc 32 commit ecrit ensuite `ai_memories`; decisions restent propositions avant commit | Conforme au principe "decision != memory". Le lien inverse est porte par `ai_memories.source_decision_id`. |

Analyse: table conforme au doc 32 pour la couche decision/proposition. Elle ne stocke pas l'etat "committed" directement; la materialisation se detecte via `ai_memories.source_decision_id`.

## Coherence du lien WR -> memoire (`ai_memories`)

Flux code constate:

```text

imperium_weekly_review_final_reports.memory_candidates
  -> imperium_memory_candidate_decisions.original_candidate / edited_candidate
  -> ai_memories.source_decision_id FK imperium_memory_candidate_decisions.id
     + ai_memories.source_report_id FK final_reports.id
     + ai_memories.source_session_id FK sessions.id
     + ai_memories.source_candidate_id text
```

Points conformes au doc 32:

- La decision WR ne cree pas automatiquement de memoire.
- La materialisation memoire est separee et explicite.
- Le code cible `ai_memories`, pas `pgvector_memory`.
- Un unique partiel sur `ai_memories(user_id, source_module, source_type, source_decision_id)` evite les doublons par decision source.

Points divergents face aux docs 75/09:

- Doc 75 dit que le `source_ref` d'un element d'apprentissage pointe vers le **log WR complet riche**. Le code pointe surtout vers des objets relationnels WR (`source_report_id`, `source_session_id`, `source_candidate_id`, `source_decision_id`) et n'a pas `source_table`.
- Doc 09/75 attend `ai_memories` avec `memory_id`, `source_app`, `source_table/source_id`, `memory_type`, `learning_element_type`, `embedding`, `embedding_model`, `privacy_level`, `is_active`, `supersedes_memory_id`. Le code actuel `ai_memories` utilise `id`, `source_module/source_type`, `kind/scope/title`, `status/visibility`, sans embedding ni privacy_level.
- Donc le lien WR -> memoire est **coherent avec l'implementation actuelle**, mais **pas coherent avec la cible canonique vectorielle doc 75/09**.

Impact pour WR-a: ne pas corriger WR seul avant de trancher/aligner `ai_memories`, sinon le lien WR -> memoire risque d'etre recode deux fois.

## Restes perimes / nomenclature

| Sujet | Constat |
|---|---|
| `pgvector_memory` | Aucun usage dans les fichiers WR audites. Le code WR parle de `ai_memories` seulement via la couche commit/memoire actuelle. |
| `pgvector` writes automatiques | Les docs et schemas WR restent coherents: candidates/decisions ne sont pas des writes automatiques de memoire. |
| Anciens noms de modeles | `role` DB/Pydantic contient `qwen` et `opus`. `qwen` est coherent avec la strategie V1 locale, mais `opus` couple le schema a un modele/provider precis. Doc 32 contient encore ce vocabulaire dans l'audit patch, tout en parlant ailleurs de roles generiques. |
| `analysis_status` | Present dans `imperium_weekly_review_states`, peu raccord avec le workflow chatbot actuel. A classer comme possible vestige, pas comme bug bloquant. |

## Synthese des ecarts majeurs

| Sujet | Niveau | Action recommandee |
|---|---|---|
| Absence de schema WR colonne par colonne dans doc 05 | Moyen | Ajouter WR au dictionnaire schema ou acter doc 32 comme proprietaire colonne par colonne. |
| `ai_memories` cible divergente | Eleve mais hors correction WR-a seule | Aligner `ai_memories` d'abord ou en meme temps que le commit WR memoire. |
| `stored` inclus dans les partial unique "active" | Faible/moyen | Clarifier le vocabulaire doc: active mutable (`draft/approved`) vs active-or-stored uniqueness (`draft/approved/stored`). |
| Roles `qwen`/`opus` dans le schema messages | Faible/moyen | Renommer a terme vers roles generiques si migration acceptable; sinon documenter que ce sont des roles historiques stables, pas des modeles configurables. |
| `imperium_weekly_review_states.analysis_status` | Faible | Documenter ou deprecier lors d'une future passe schema. |

## Conclusion

Classification WR-a: **(b) leger decalage**.

Le schema WR lui-meme est globalement sain et fidele au doc 32: backend-owned session, messages ordonnes, candidats de final report historises, decisions memoire separees, aucun write automatique en memoire.

La reserve principale ne vient pas du WR pur, mais de la jonction avec la memoire: `imperium_memory_candidate_decisions` est propre comme couche d'audit/proposition, mais sa cible `ai_memories` ne correspond pas encore aux docs 75/09. Tant que `ai_memories` reste divergent, le flux WR -> memoire ne peut pas etre considere conforme a la vision vectorielle unifiee.

Actions proposees:

1. Ne pas modifier les tables WR principales avant l'audit logique WR-b/WR-c, sauf documentation.
2. Ajouter une section schema WR colonne par colonne dans doc 05 ou enrichir doc 32 en schema owner officiel.
3. Clarifier dans doc 32 la difference entre "active mutable report" (`draft/approved`) et contrainte d'unicite "active-or-stored" (`draft/approved/stored`).
4. Traiter `ai_memories` avant tout changement du commit WR memoire: le lien `source_decision_id` devra etre reconcilie avec `source_table/source_id`, `privacy_level`, `learning_element_type` et le futur embedding.
5. Plus tard, envisager une migration de nomenclature des roles messages (`qwen`/`opus` -> roles generiques), seulement si cela ne casse pas la compatibilite historique.

