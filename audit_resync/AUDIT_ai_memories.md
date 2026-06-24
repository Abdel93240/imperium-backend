AUDIT ai_memories - ecart schema code <-> documentation
Date: 2026-06-24

Perimetre lu:
- CODE: backend/alembic/versions/20260502_0017_ai_memories_foundation.py
- CODE ORM: backend/app/models/ai.py, classe AIMemory
- DOC cible: docs_master/75_MEMOIRE_VECTORIELLE_UNIFIEE.md section 3
- DOC cible: docs_master/09_PGVECTOR_MEMORY_POLICY.md section "ai_memories Schema"

Synthese courte:
Le schema code de ai_memories n'est pas le schema cible vectoriel documente.
Il ressemble a une fondation de memoires Weekly Review sans embedding, sans privacy_level,
avec status/visibility et des references WR specifiques. Les docs 75/09 decrivent une table
canonique vectorielle avec memory_id, source_app, memory_type, privacy_level, embedding
vectoriel, source_table/source_id, is_active et supersedes_memory_id.

Tableau d'ecart colonne par colonne:

| Colonne / sujet | Code migration 0017 / ORM | Doc 75 §3 + Doc 09 | Ecart |
|---|---|---|---|
| id / memory_id | `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` | `memory_id UUID PRIMARY KEY DEFAULT gen_random_uuid()` | Difference de nom. Le code utilise `id`; la doc cible utilise `memory_id`, y compris comme cible FK de supersession. |
| user_id | `UUID NOT NULL`, FK `users.id ON DELETE CASCADE` | `UUID NOT NULL`, FK `users.id ON DELETE CASCADE` | Conforme. |
| content | `TEXT NOT NULL` | `TEXT NOT NULL` | Conforme. |
| embedding | Absent | `embedding vector(1024) NOT NULL` dans doc 75; `embedding vector NOT NULL` dans doc 09 | Manquant critique. La dimension cible explicite est 1024 selon doc 75. |
| embedding_model | Absent | `TEXT NOT NULL` | Manquant critique. |
| memory_type | Absent | `memory_type memory_type NOT NULL` | Manquant. Le code a `kind` et `scope`, mais pas l'enum canonique `memory_type`. |
| learning_element_type | Absent | `TEXT NULL` dans doc 09 | Manquant par rapport au doc 09. Non present dans le CREATE TABLE de doc 75, mais le doc 09 le liste dans le schema proprietaire. |
| source_app | Absent | `source_app source_app NOT NULL` | Manquant. Le code a `source_module`, mais ce n'est pas le meme nom ni le meme type enum. |
| source_table | Absent | `TEXT NULL` | Manquant. Les docs demandent le chemin vers la source canonique. |
| source_id | `TEXT NOT NULL` | `TEXT NULL` | Present mais contrainte differente: code NOT NULL, doc nullable. |
| confidence | `NUMERIC(5,4) NOT NULL`, check `0 <= confidence <= 1` | `NUMERIC NULL`; doc 09/75 disent que confidence trie mais n'exclut pas par seuil par defaut | Present, mais contrainte differente: code rend obligatoire; doc cible le rend nullable. Le check 0..1 est coherent mais non explicitement donne dans le schema cible. |
| privacy_level | Absent | `privacy_level privacy_level NOT NULL`, non negociable sur chaque ligne | Manquant critique. Le code a `visibility TEXT NOT NULL DEFAULT 'private'`, mais ce n'est pas equivalent au privacy gate medical/financier/religieux attendu. |
| is_active | Absent | `BOOLEAN NOT NULL DEFAULT true` | Manquant. Le code utilise `status` a la place. |
| supersedes_memory_id | Absent | `UUID NULL REFERENCES ai_memories(memory_id)` | Manquant. Le code a `superseded_by_id`, qui pointe dans le sens inverse et reference `ai_memories.id`. |
| correction_reason | Absent | `TEXT NULL` | Manquant. |
| expires_at | Absent | `TIMESTAMPTZ NULL` | Manquant. Doc 75 precise que c'est une expiration explicite, pas un decay. |
| created_at | `DateTime(timezone=True) NOT NULL DEFAULT now()` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Conforme fonctionnellement. |
| updated_at | `DateTime(timezone=True) NOT NULL DEFAULT now()` avec ORM `onupdate=func.now()` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Globalement conforme. Attention: la migration ne cree pas de trigger DB pour mise a jour automatique; seul l'ORM applique `onupdate`. |
| metadata | `JSONB NULL` | `JSONB NULL` | Conforme. |
| source_module | `TEXT NOT NULL`, check limite a `'weekly_review'` | Absent; doc cible demande `source_app source_app NOT NULL` | Present dans le code mais pas dans la cible. A questionner/remplacer par `source_app`. |
| source_type | `TEXT NOT NULL` | Absent | Present dans le code mais pas dans la cible. A questionner. |
| source_report_id | `UUID NULL`, FK `imperium_weekly_review_final_reports.id` | Absent | Present dans le code mais pas dans la cible. A questionner; pourrait devenir detail de source via `source_table/source_id` ou metadata. |
| source_session_id | `UUID NULL`, FK `imperium_weekly_review_sessions.id` | Absent | Present dans le code mais pas dans la cible. A questionner; tres Weekly Review specifique. |
| source_candidate_id | `TEXT NULL` | Absent | Present dans le code mais pas dans la cible. A questionner. |
| source_decision_id | `UUID NULL`, FK `imperium_memory_candidate_decisions.id` | Absent | Present dans le code mais pas dans la cible. A questionner; peut rester en metadata ou contrat WR si besoin, mais non canonique doc 75/09. |
| kind | `TEXT NOT NULL`, check liste de kinds | Absent; doc cible demande `memory_type` | Present dans le code mais pas dans la cible. Semantique proche mais non conforme au nom/type cible. |
| scope | `TEXT NOT NULL`, check liste de scopes | Absent | Present dans le code mais pas dans la cible. A questionner; peut etre remplace par `memory_type`, `source_app`, metadata, ou un champ futur documente. |
| title | `TEXT NOT NULL` | Absent | Present dans le code mais pas dans la cible. A questionner; la doc cible ne stocke que `content` comme pattern naturel. |
| status | `TEXT NOT NULL DEFAULT 'active'`, check active/archived/superseded/deleted | Doc 75 dit que `status` est retire/remplace par `is_active` + `supersedes_memory_id` | Present dans le code mais explicitement contraire au schema cible doc 75. |
| visibility | `TEXT NOT NULL DEFAULT 'private'`, check seulement `'private'` | Absent; doc cible demande `privacy_level privacy_level NOT NULL` | Present dans le code mais pas dans la cible. Ne remplace pas `privacy_level`. |
| archived_at | `TIMESTAMPTZ NULL` | Absent | Present dans le code mais pas dans la cible. A questionner; le cycle de vie cible utilise `is_active`, `expires_at`, `supersedes_memory_id`, `correction_reason`. |
| superseded_by_id | `UUID NULL REFERENCES ai_memories(id)` | Absent; doc cible demande `supersedes_memory_id UUID REFERENCES ai_memories(memory_id)` | Present dans le code mais nom et sens differents. La cible stocke "cette memoire remplace telle ancienne memoire"; le code stocke "cette memoire est remplacee par telle nouvelle memoire". |
| idempotency_key | `TEXT NULL` | Absent | Present dans le code mais pas dans la cible. A questionner; peut etre utile au contrat API mais non documente dans le schema canonique. |

Colonnes presentes dans le code mais pas dans la doc cible:
- `id` sous ce nom, car la cible nomme la PK `memory_id`.
- `source_module`
- `source_type`
- `source_report_id`
- `source_session_id`
- `source_candidate_id`
- `source_decision_id`
- `kind`
- `scope`
- `title`
- `status`
- `visibility`
- `archived_at`
- `superseded_by_id`
- `idempotency_key`

Colonnes dans la doc cible mais pas dans le code:
- `memory_id`
- `embedding`
- `embedding_model`
- `memory_type`
- `learning_element_type` (doc 09)
- `source_app`
- `source_table`
- `privacy_level`
- `is_active`
- `supersedes_memory_id`
- `correction_reason`
- `expires_at`

Colonnes presentes des deux cotes avec difference:
- `source_id`: code `TEXT NOT NULL`; doc `TEXT NULL`.
- `confidence`: code `NUMERIC(5,4) NOT NULL` avec check 0..1; doc `NUMERIC NULL`.
- `updated_at`: types equivalents, mais le code migration ne cree pas de mecanisme DB de mise a jour automatique; l'ORM seul a `onupdate`.
- `id` / `memory_id`: meme role logique, nom different.
- `source_module` / `source_app`: role voisin, mais nom et type differents (`TEXT` limite a weekly_review vs enum `source_app`).
- `kind` / `memory_type`: role voisin, mais nom et type differents (`TEXT` + check vs enum `memory_type`).
- `status` / `is_active`: role cycle de vie voisin, mais doc 75 dit explicitement que `status` est remplace par `is_active` + `supersedes_memory_id`.
- `visibility` / `privacy_level`: role de protection voisin en apparence, mais non equivalent; la doc exige `privacy_level` enum non nullable.
- `superseded_by_id` / `supersedes_memory_id`: nom et direction inverses.

Points de coherence demandes explicitement:
- `weight` / decay temporel: `weight` est absent du code. C'est coherent avec doc 75 et doc 09: pas de decay temporel, pas de recency weighting, confidence ne baisse pas seule.
- `privacy_level`: absent du code `ai_memories`. Donc il n'est pas present et NOT NULL. Non conforme a doc 75, qui le declare non negociable.
- `confidence`: present dans le code, mais NOT NULL alors que la doc cible le declare nullable.
- `supersedes_memory_id`: absent du code. Le code contient `superseded_by_id`, mecanisme inverse.
- `embedding vector(1024)`: absent du code. Aucune colonne `embedding`; aucune dimension vectorielle; aucun index de similarite vectorielle.
- `source_table` / `source_id` ou `source_ref_*`: `source_id` est present mais NOT NULL; `source_table` est absent; `source_ref_type/source_ref_id` absents. Le code contient des references source specifiques Weekly Review (`source_report_id`, `source_session_id`, `source_candidate_id`, `source_decision_id`) au lieu du chemin canonique `source_table/source_id`.

Index et contraintes:
- Index code: user/created, user/status/created, user/kind, user/scope, source_module/source_type, source_report/session/candidate/decision, unique partiel sur source_decision.
- Index docs: vector similarity sur `embedding`, `(user_id, source_app, memory_type, is_active)`, `(user_id, privacy_level, is_active)`, `(source_table, source_id)`, `expires_at`.
- Ecart: les index code servent le schema WR actuel; les index cibles de recherche vectorielle/privacy gate sont absents.

Conclusion:
Classification: (c) tres divergent.

Raison:
Le code actuel n'est pas seulement legerement decale: il ne contient pas le coeur du schema canonique documente de memoire vectorielle (`embedding vector(1024)`, `embedding_model`, `privacy_level`, `source_app`, `memory_type`, `source_table`, `is_active`, `supersedes_memory_id`). Il conserve au contraire plusieurs champs que doc 75 retire ou remplace explicitement (`status`, mecanisme inverse `superseded_by_id`, absence du privacy gate, absence du chemin source canonique).

Actions precises pour aligner si une correction est decidee plus tard:
1. Renommer/adapter la cle primaire vers `memory_id`, ou documenter formellement que `id` remplace `memory_id` si le projet choisit la convention ORM existante.
2. Ajouter `embedding vector(1024) NOT NULL` et `embedding_model TEXT NOT NULL`, avec extension pgvector et index de similarite.
3. Ajouter `privacy_level privacy_level NOT NULL` et l'index `(user_id, privacy_level, is_active)`.
4. Remplacer/mapper `source_module` vers `source_app source_app NOT NULL`.
5. Ajouter `source_table TEXT NULL` et rendre `source_id` nullable selon la doc, ou corriger la doc si `source_id` doit rester obligatoire.
6. Remplacer/mapper `kind` vers `memory_type memory_type NOT NULL`; clarifier le statut de `learning_element_type`.
7. Remplacer le cycle de vie `status` par `is_active BOOLEAN NOT NULL DEFAULT true`, `expires_at`, `supersedes_memory_id`, `correction_reason`.
8. Corriger la supersession: utiliser `supersedes_memory_id` qui reference l'ancienne memoire, au lieu de `superseded_by_id` inverse, ou documenter explicitement le choix inverse.
9. Revoir `confidence`: nullable selon docs, ou mettre a jour docs/tests si le choix produit impose NOT NULL.
10. Decider du sort des champs WR specifiques (`source_report_id`, `source_session_id`, `source_candidate_id`, `source_decision_id`, `idempotency_key`, `title`, `scope`, `visibility`, `archived_at`): les retirer, les mettre en metadata, ou les documenter comme extension non canonique.
11. Ajouter/mettre a jour les tests pytest de schema/migration avant toute modification future, conformement a la regle CI.
