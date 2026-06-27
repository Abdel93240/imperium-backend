# AUDIT Path — code backend ↔ docs

Date: 2026-06-27  
Scope: audit lecture seule du module Path: migrations `0008` et `0027`, ORM, routes, schemas, services. Aucun code backend modifié.

## Verdict court

Verdict: **(b) léger décalage**, avec une dette legacy active.

Raison:

- La surface Path V1 habits/check-ins est cohérente côté code: routes `/api/imperium/path/*`, service `services/path/habits.py`, schemas `schemas/path.py`, tables `imperium_path_habits` et `imperium_path_check_ins`.
- Le schéma colonne par colonne n'est pas vraiment documenté. `04_MVP_BACKEND_CONTRACTS.md` possède le contrat API Path V1, mais pas les colonnes. `05_DATABASE_SCHEMA.md` répète seulement les invariants. `41_PATH_LOGIC_DETAIL.md` possède la logique métier Path, mais ne définit pas les tables habits/check-ins actuelles.
- `imperium_path_items` est documenté comme legacy/déprécié, mais reste branché via routes legacy et lecteurs Imperium/weekly report. Ce n'est pas un doublon direct de habits/check-ins, mais c'est une dette de périmètre.

Propriétaire de schéma Path:

- **Doc 41** est le propriétaire canonique de la **logique Path** (`Doc 41 owns Path business logic`).
- **Doc 04** est le propriétaire de fait des **contrats API Path V1** (`/api/imperium/path/habits`, `/today`, `/stats/summary`, etc.).
- **Aucun doc ne possède correctement le schéma Path actuel colonne par colonne** pour `imperium_path_habits` et `imperium_path_check_ins`.
- `05_DATABASE_SCHEMA.md` devrait être le propriétaire naturel du schéma, mais il ne joue pas ce rôle aujourd'hui pour Path.

## Sources lues

- Migrations: `backend/alembic/versions/20260426_0008_imperium_path_items.py`, `backend/alembic/versions/20260525_0027_imperium_path_habits_check_ins.py`
- ORM: `backend/app/models/imperium.py::ImperiumPathItem`, `ImperiumPathHabit`, `ImperiumPathCheckIn`
- Routes: `backend/app/api/v1/routes/imperium_path.py`, `backend/app/api/v1/routes/imperium.py`
- Services: `backend/app/services/imperium/path_items.py`, `backend/app/services/path/habits.py`
- Schemas: `backend/app/schemas/path.py`, `backend/app/schemas/imperium.py`
- Docs: `docs_master/41_PATH_LOGIC_DETAIL.md`, `04_MVP_BACKEND_CONTRACTS.md`, `05_DATABASE_SCHEMA.md`, `50_PATH_DARS_KNOWLEDGE_BASE.md`

## Partie 1 — Schéma

### Table `imperium_path_items`

Code:

- Migration `20260426_0008`: table + index + constraints.
- ORM: `ImperiumPathItem`.
- Service: `services/imperium/path_items.py`.

Doc:

- `41_PATH_LOGIC_DETAIL.md` dit que `ImperiumPathItem` est du code de compatibilité legacy déprécié et ne doit pas définir/masquer `/path/today`.
- `05_DATABASE_SCHEMA.md` mentionne `imperium_path_items`, `read-only compatibility projection`, `path item legacy model`, `deprecated`.
- Aucun doc lu ne définit cette table colonne par colonne.

| Colonne / invariant | Code | Doc | Écart |
|---|---|---|---|
| `id` | UUID PK | Non listé | Présent code / absent doc |
| `user_id` | UUID FK `users.id`, non null | Non listé | Présent code / absent doc |
| `local_date` | `Date`, non null | `05` mentionne default date convention / query date, pas la colonne | Doc partielle |
| `timezone` | `Text`, non null, default `Europe/Paris` | `05` mentionne Europe/Paris | Conforme implicite, pas un schéma |
| `title` | `Text`, non null | Non listé | Présent code / absent doc |
| `description` | `Text`, nullable | Non listé | Présent code / absent doc |
| `category` | `Text`, nullable | Non listé | Présent code / absent doc |
| `priority_key` | `Text`, nullable | Non listé | Présent code / absent doc |
| `planned_start` | timestamptz nullable | Non listé | Présent code / absent doc |
| `planned_end` | timestamptz nullable | Non listé | Présent code / absent doc |
| `status` | `Text`, non null, check `planned/in_progress/completed/skipped/cancelled` | Non listé | Présent code / absent doc |
| `source` | `Text`, non null, default `manual`, check `manual/system/ai_planned` | Non listé | Présent code / absent doc |
| `sort_order` | `Integer`, non null, default `0` | Non listé | Présent code / absent doc |
| `skip_reason` | `Text`, nullable | Non listé | Présent code / absent doc |
| `completed_at` | timestamptz nullable | Non listé | Présent code / absent doc |
| `skipped_at` | timestamptz nullable | Non listé | Présent code / absent doc |
| `cancelled_at` | timestamptz nullable | Non listé | Présent code / absent doc |
| `metadata` | JSONB non null, default `{}` | Non listé | Présent code / absent doc |
| `created_at` | timestamptz non null, default `now()` | Non listé | Présent code / absent doc |
| `updated_at` | timestamptz non null, default `now()`, ORM `onupdate` | Non listé | Présent code / absent doc |
| Index `(user_id, local_date)` | Migration + ORM | Non listé | Présent code / absent doc |
| Index `(user_id, status)` | Migration + ORM | Non listé | Présent code / absent doc |
| Index `(user_id, planned_start)` | Migration + ORM | Non listé | Présent code / absent doc |
| Index `(user_id, local_date, sort_order)` | Migration + ORM | Non listé | Présent code / absent doc |
| Statut produit | Table active en routes legacy | `deprecated` / compatibility projection | Dette: encore branché malgré dépréciation |

### Table `imperium_path_habits`

Code:

- Migration `20260525_0027`.
- ORM: `ImperiumPathHabit`.
- Pydantic create/read: `PathHabitCreate`, `PathHabitRead`.
- Service: `services/path/habits.py`.

Doc:

- `04_MVP_BACKEND_CONTRACTS.md` documente `POST/GET /api/imperium/path/habits` et `GET /api/imperium/path/habits/{habit_id}`, mais pas les colonnes.
- `41_PATH_LOGIC_DETAIL.md` ne définit pas cette table; il définit des tables futures/indicatives comme `adhkar_routines`, `adhkar_completions`, etc.
- `05_DATABASE_SCHEMA.md` liste les invariants Path 10a/10d, mais pas les colonnes.

| Colonne / invariant | Code | Doc | Écart |
|---|---|---|---|
| `id` | UUID PK | `habit_id` apparaît dans les routes, pas comme colonne | Conforme implicite / absent schéma |
| `user_id` | UUID FK `users.id`, non null | Endpoints scoped current user implicite | Présent code / doc implicite |
| `title` | `String(120)`, non null; Pydantic min 1 max 120 + trim | Non listé | Présent code / absent doc |
| `description` | `String(500)`, nullable; Pydantic max 500 + trim blank→null | Non listé | Présent code / absent doc |
| `domain` | `String(80)`, nullable; Pydantic enum `worship/health/discipline/family/work/custom` | Non listé | Présent code / absent doc; enum API non garanti DB |
| `frequency` | `String(20)`, non null, DB check `daily/weekly` | Non listé | Présent code / absent doc |
| `is_active` | Boolean non null default true | Archive/reactivate routes non mentionnées dans `04` Path Contracts | Présent code / absent contrat demandé |
| `created_at` | timestamptz non null default `now()` | Non listé | Présent code / absent doc |
| `updated_at` | timestamptz non null default `now()`, ORM `onupdate` | Non listé | Présent code / absent doc |
| Index `(user_id, is_active, created_at)` | Migration + ORM | Non listé | Présent code / absent doc |
| Index `(user_id, domain)` | Migration + ORM | Non listé | Présent code / absent doc |
| No AI/n8n/scoring/calendar | Service deterministic CRUD/read | `04` et `05` l'interdisent pour 10a | Conforme |
| No automatic check-in creation | `create_path_habit` ne crée pas de check-in | `04` l'interdit | Conforme |

Point notable: `domain` est borné dans Pydantic, pas dans la DB. Une écriture hors API pourrait stocker une valeur non canonique.

### Table `imperium_path_check_ins`

Code:

- Migration `20260525_0027`.
- ORM: `ImperiumPathCheckIn`.
- Pydantic create/read: `PathCheckInCreate`, `PathCheckInRead`.
- Service: `services/path/habits.py`.

Doc:

- `04_MVP_BACKEND_CONTRACTS.md` documente `POST /api/imperium/path/habits/{habit_id}/check-ins`, `GET /api/imperium/path/check-ins`, `GET /api/imperium/path/check-ins/{check_in_id}`, `missed requires reason`, `pending implicits are excluded`, et `completion rate`.
- Aucun doc ne liste les colonnes.

| Colonne / invariant | Code | Doc | Écart |
|---|---|---|---|
| `id` | UUID PK | `check_in_id` apparaît dans route detail, pas comme colonne | Conforme implicite / absent schéma |
| `user_id` | UUID FK `users.id`, non null | Endpoints scoped current user implicite | Présent code / doc implicite |
| `habit_id` | UUID FK `imperium_path_habits.id`, non null | Présent dans route path | Conforme implicite |
| `check_date` | `Date`, non null | `today`/date filters implicites | Présent code / doc partielle |
| `status` | `String(20)`, non null, DB check `done/missed` | `done/missed`; `pending` seulement pour today view implicite | Conforme: pending n'est pas persisté |
| `reason` | `String(500)`, nullable; Pydantic requis si `missed`, interdit si `done` | `missed requires reason` | Conforme API, pas garanti DB |
| `note` | `String(500)`, nullable | Non listé | Présent code / absent doc |
| `created_at` | timestamptz non null default `now()` | Non listé | Présent code / absent doc |
| `updated_at` | timestamptz non null default `now()`, ORM `onupdate` | Non listé | Présent code / absent doc |
| Unique `(user_id, habit_id, check_date)` | Migration | Non listé | Présent code / absent doc; utile contre doublons |
| Index `(user_id, check_date DESC)` | Migration + ORM | Non listé | Présent code / absent doc |
| Index `(user_id, habit_id, check_date)` | Migration + ORM | Non listé | Présent code / absent doc |
| No automatic check-in creation | Service crée uniquement via POST explicite | `04`/`05` l'interdisent | Conforme |
| `pending` excluded from stats | Stats comptent seulement rows `done/missed` | `04` dit pending implicits excluded | Conforme |

Point notable: l'invariant religieux/discipline `missed requires reason` est seulement validé par Pydantic. La DB permet `status='missed'` avec `reason NULL`.

## Partie 2 — Doublons / cohérence services

### Services comparés

| Fichier | Tables | Responsabilité | Branché ? | Analyse |
|---|---|---|---|---|
| `backend/app/services/imperium/path_items.py` | `imperium_path_items` | Items legacy: day/recent/create/start/complete/skip/cancel + événements `path.item.*` | Oui, via `routes/imperium.py` (`/api/imperium/path/day`, `/path/recent`, `/path/items*`) et lecteurs legacy | Responsabilité distincte de habits/check-ins, mais legacy actif |
| `backend/app/services/path/habits.py` | `imperium_path_habits`, `imperium_path_check_ins` | Path V1 habits/check-ins/today/stats + archive/reactivate + idempotency | Oui, via `routes/imperium_path.py` préfixé `/api/imperium/path`; aussi dashboard foundation et daily plan snapshot | Service canonique pour Path V1 actuel |

Conclusion doublons:

- Les deux services ne se chevauchent pas au niveau table ni modèle métier immédiat: `path_items` gère des tâches/items planifiés legacy; `habits.py` gère habitudes/check-ins.
- Il y a tout de même un recouvrement de nommage/produit: les deux exposent des surfaces sous `/api/imperium/path*`, ce qui peut faire croire à deux Path actifs.
- `41_PATH_LOGIC_DETAIL.md` clarifie que `imperium_path.py` est canonique pour Path V1 et que `ImperiumPathItem` est déprécié pour Path V1.
- Pas de duplication de service sur la même table habits/check-ins trouvée.

### Ce qui est branché / utilisé

Surface canonique Path V1:

- `backend/app/api/v1/router.py` inclut `imperium_path.router` avec prefix `/imperium/path`.
- `routes/imperium_path.py` expose `/today`, `/stats/summary`, `/habits`, `/habits/{id}`, `/check-ins`, `/check-ins/{id}`.
- `routes/imperium_path.py` importe exclusivement `services/path/habits.py`.
- `get_path_today_view()` est aussi utilisé par dashboard foundation et daily plan snapshot.

Surface legacy encore active:

- `backend/app/api/v1/router.py` inclut aussi `imperium.router` avec prefix `/imperium`.
- `routes/imperium.py` expose encore `/path/day`, `/path/recent`, `/path/items`, `/path/items/{id}/start|complete|skip|cancel`.
- `services/imperium/dashboard.py`, `services/imperium/daily_plans.py` et `services/imperium/weekly_report.py` lisent encore `ImperiumPathItem` pour certains chemins historiques.

Risque:

- Tant que les routes/lecteurs legacy restent actifs, le mot "Path" peut désigner deux surfaces différentes.
- Pas de conflit direct avec `/api/imperium/path/today`: le legacy ne définit pas `/path/today`, donc il ne masque pas la route canonique.

## Partie 3 — Cohérence religieuse

Décisions docs à respecter:

- `41_PATH_LOGIC_DETAIL.md`: actions religieuses explicites seulement, backend authority, private religious data local-first sauf privacy gate, pas de complétion inférée.
- `41_PATH_LOGIC_DETAIL.md`: cloud models seulement après privacy gate et payload minimal; pas d'erreurs qui exposent des détails religieux.
- `50_PATH_DARS_KNOWLEDGE_BASE.md`: Dars est V3, pas V1; pas de vectorisation du corpus religieux; recherche déterministe full-text; Q&A locale par défaut; si le local ne suffit pas, réduire/refuser, pas envoyer le corpus au cloud.

Constats code:

- Le code audité pour habits/check-ins est déterministe CRUD/read. Il n'appelle pas AI, n8n, OCR, pgvector, embeddings, ni modèle cloud.
- Les check-ins sont créés uniquement par `POST /habits/{habit_id}/check-ins` avec `Idempotency-Key`; `today` ne crée pas automatiquement de check-in et retourne `pending` si aucune row n'existe.
- Le code ne contient pas de module Dars actif (`services/path/dars/*`, routes `/path/dars/*`, tables `dars_*`) dans le scope audité.
- La recherche globale dans `backend/app` ne montre pas de vectorisation religieuse ni de référence active à un corpus religieux. Les seules mentions `pgvector`/`embeddings` pertinentes sont des garde-fous ou des réponses indiquant que les embeddings sont désactivés.

Incohérences religieuses trouvées:

- Aucune contradiction directe avec doc 41/doc 50 dans le code Path habits/check-ins.
- Vigilance: `domain="worship"` et les notes/reasons peuvent contenir de la donnée religieuse personnelle. Le code ne route pas vers cloud, donc OK. Les messages d'erreur restent génériques (`Path check-in...`) et ne divulguent pas de détail religieux.

## Partie 4 — Restes périmés / références mortes

### Legacy actif

| Élément | Statut | Commentaire |
|---|---|---|
| `ImperiumPathItem` | Legacy mais encore actif | Déprécié par doc 41/05, mais routes et lecteurs existent encore |
| `services/imperium/path_items.py` | Legacy actif | Pas mort: routes `/api/imperium/path/day`, `/recent`, `/items*` |
| `routes/imperium.py` Path legacy | Actif | Branché par `api_router.include_router(imperium.router, prefix="/imperium")` |
| Lecteurs `ImperiumPathItem` dans dashboard/weekly/daily_plans legacy | Actifs | Peut entretenir deux vues Path différentes |

### Références pgvector / corpus religieux

- Aucune référence active `pgvector_memory` trouvée dans `backend/app` pour Path.
- Aucune table ou service Dars actif dans `backend/app`.
- Les docs `04/05/41/50` répètent correctement `no pgvector write`, `no embeddings`, et exclusion du corpus religieux.

### Documentation périmée ou incomplète

- `05_DATABASE_SCHEMA.md` mentionne `imperium_path_items` comme legacy, mais ne possède pas le schéma actuel Path.
- `41_PATH_LOGIC_DETAIL.md` §20 documente des tables Path plus religieuses/futures (`path_calculated_prayer_times`, `path_registered_mosques`, `path_mawaqit_cache`, `registered_ghusl_addresses`, `adhkar_routines`, `adhkar_completions`, `quran_progression`, `path_weekly_sadaqa_state`) qui ne correspondent pas aux tables `imperium_path_habits` / `imperium_path_check_ins`.
- `04_MVP_BACKEND_CONTRACTS.md` est correct pour les endpoints, mais insuffisant comme schéma.

## Conclusion

### (a) Conforme

Non pour le schéma documentaire: les tables actuelles ne sont pas documentées colonne par colonne.

### (b) Léger décalage

Oui pour le module Path habits/check-ins: code cohérent, contrats API globalement alignés, aucune contradiction religieuse, mais docs de schéma incomplètes.

### (c) Divergent

Non pour habits/check-ins. La seule divergence importante est la dette legacy `imperium_path_items`, encore active malgré sa dépréciation, mais elle ne duplique pas directement le service habits/check-ins.

Actions recommandées:

1. Déclarer officiellement le propriétaire du schéma Path. Option pragmatique: réécrire `05_DATABASE_SCHEMA.md` comme dictionnaire colonne par colonne pour `imperium_path_items`, `imperium_path_habits`, `imperium_path_check_ins`, avec statut legacy/canonique.
2. Dans `41_PATH_LOGIC_DETAIL.md`, ajouter une sous-section "V1 implemented schema" qui renvoie vers `05`, ou préciser que `imperium_path_habits/check_ins` sont le backend V1 minimal pour habits/check-ins.
3. Décider du sort de `imperium_path_items`: garder comme compatibilité legacy clairement hors Path V1 canonique, ou supprimer/débrancher routes et lecteurs si tables vides.
4. Si la règle `missed requires reason` doit être inviolable hors API, ajouter plus tard une contrainte DB sur `imperium_path_check_ins`.
5. Si `domain` doit rester borné hors API, ajouter plus tard une contrainte DB ou documenter que l'enum est API-only.
6. Mettre à jour `04_MVP_BACKEND_CONTRACTS.md` pour inclure les routes archive/reactivate ou les retirer du code si elles sont hors scope MVP.

Tests non lancés: audit lecture seule, aucune modification de code.
