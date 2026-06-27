# AUDIT daily_plans

Date: 2026-06-27
Scope: audit lecture seule du module DAILY_PLANS. Aucun code backend modifie.

## Verdict court

Verdict: **(c) divergent**

Le module contient deux realites actives:

- `backend/app/services/imperium/daily_plan.py` (singulier) = snapshot read-only expose par `GET /api/imperium/daily-plan`.
- `backend/app/services/imperium/daily_plans.py` (pluriel) = CRUD persistant sur `imperium_daily_plans`, expose par les routes legacy/Imperium generales `/api/imperium/day/plan...`.

Ils ne font pas la meme chose. Ce n'est pas un simple doublon de nom, c'est une bifurcation de produit: snapshot read-only vs plan persiste.

## Sources lues

Code:

- `backend/alembic/versions/20260426_0009_imperium_daily_plans.py`
- `backend/app/models/imperium.py`
- `backend/app/services/imperium/daily_plans.py`
- `backend/app/services/imperium/daily_plan.py`
- `backend/app/api/v1/routes/imperium_daily_plan.py`
- `backend/app/api/v1/routes/imperium.py`
- `backend/app/schemas/daily_plan.py`
- `backend/app/schemas/imperium.py`
- lecteurs dependants: `dashboard.py`, `weekly_report.py`, `missions.py`, `decision_framework.py`

Docs:

- `docs_master/28_DAILY_PLAN_WORKFLOW.md`
- `docs_master/52_AI_DECISION_FRAMEWORK.md` section 9 et schema section 12
- `docs_master/04_MVP_BACKEND_CONTRACTS.md`
- `docs_master/05_DATABASE_SCHEMA.md`

## Partie 1 - Schema daily_plans

### Proprietaire reel du schema

Le proprietaire reel du schema **execute** de la table `imperium_daily_plans` est:

1. migration `backend/alembic/versions/20260426_0009_imperium_daily_plans.py`;
2. ORM `ImperiumDailyPlan` dans `backend/app/models/imperium.py`.

La doc la plus alignee avec ce schema execute est `docs_master/28_DAILY_PLAN_WORKFLOW.md`.

Mais il existe une contradiction documentaire:

- doc 28 decrit une table canonique `imperium_daily_plans` tres proche du code;
- doc 52 section 12 decrit une autre table `imperium_daily_plans`, orientee instanciation IA depuis monthly plan;
- docs 04/05 decrivent surtout `/api/imperium/daily-plan` comme snapshot read-only, avec mention qu'il ne persiste pas de nouvelle ligne.

Donc le schema execute est clair dans le code, mais la propriete documentaire est dispersee.

### Table executee: `imperium_daily_plans`

| Colonne | Code migration/ORM | Doc 28 | Doc 52 section 12 | Docs 04/05 | Verdict |
|---|---|---|---|---|---|
| `id` | UUID PK | UUID primary key | UUID PK | non documente colonne | OK code-doc28-doc52 |
| `user_id` | UUID FK `users.id`, non nullable | canonical user FK | UUID FK | non documente colonne | OK partiel |
| `local_date` | `Date`, non nullable | user-local date | absent: doc 52 dit `date` | endpoint `date` query pour snapshot | **Ecart doc52: nom `date` vs `local_date`** |
| `timezone` | `Text`, non nullable, default `Europe/Paris` | default `Europe/Paris` | absent | default date convention Europe/Paris | OK doc28, absent doc52 |
| `plan_status` | `Text`, non nullable, default `draft`, check draft/active/completed/cancelled | `draft`, `active`, `completed`, `cancelled` | absent: doc 52 dit `status` draft/active/completed | non documente colonne | **Ecart doc52: nom + valeur `cancelled` absente** |
| `title` | nullable text | optional | absent | absent | OK doc28 seulement |
| `summary` | nullable text | optional | absent | summary section du snapshot, pas colonne | OK doc28, concept different dans docs04/05 |
| `focus_priority_key` | nullable text | optional | absent | absent | OK doc28 seulement |
| `current_mission_id` | nullable UUID FK `imperium_missions.id` | nullable FK | absent | active mission dans snapshot, pas colonne | OK doc28 seulement |
| `generated_from` | JSONB object, default `{}` | JSONB source IDs | absent | absent | OK doc28 seulement |
| `plan_blocks` | JSONB array, default `[]`, check JSON array | JSONB array | absent: doc 52 dit `plan_json` | absent | **Ecart doc52: `plan_blocks` vs `plan_json`** |
| `notes` | nullable text | optional | absent | absent | OK doc28 seulement |
| `created_at` | timestamptz default now | UTC timestamp | absent | absent | OK doc28 seulement |
| `updated_at` | timestamptz default now, ORM `onupdate` | UTC timestamp | absent | absent | OK doc28 seulement |
| `monthly_plan_id` | absent | absent | nullable FK | absent | **Doc52 futur/non implemente** |
| `generated_at` | absent | absent | timestamptz | snapshot has `snapshot_generated_at`, not table | **Doc52 futur/non implemente** |
| `generated_model` | absent | absent | varchar, `qwen-local` normally | absent | **Doc52 futur/non implemente** |
| `is_adapted` | absent | absent | boolean | absent | **Doc52 futur/non implemente** |
| `adaptation_reason` | absent | absent | text | absent | **Doc52 futur/non implemente** |
| `cost_eur` | absent | absent | numeric | absent | **Doc52 futur/non implemente** |

### Contraintes et index

| Element | Code | Doc 28 | Doc 52 / 04 / 05 | Verdict |
|---|---|---|---|---|
| unicite `(user_id, local_date)` | oui, `imperium_daily_plans_user_local_date_unique` | oui | non | OK doc28 |
| check status | oui, draft/active/completed/cancelled | oui | doc52 ne mentionne pas cancelled | OK doc28, ecart doc52 |
| check `plan_blocks` array | oui | oui | non | OK doc28 |
| FK `user_id` | oui | oui | implicite | OK |
| FK `current_mission_id` | oui | oui | absent | OK doc28 |
| index `(user_id, local_date)` | oui | non detaille | non | code seulement |
| index `(user_id, plan_status)` | oui | non detaille | non | code seulement |

## Partie 2 - Doublon `daily_plans.py` vs `daily_plan.py`

### `daily_plan.py` singulier

Role reel:

- service read-only;
- construit un snapshot a la volee;
- ne lit pas `ImperiumDailyPlan`;
- ne cree pas de ligne `imperium_daily_plans`;
- ne fait ni idempotency, ni event, ni transition de statut;
- expose par `backend/app/api/v1/routes/imperium_daily_plan.py`;
- route active: `GET /api/imperium/daily-plan`.

Sources lues:

- `get_imperium_dashboard_foundation`;
- `get_current_active_mission`;
- `get_path_today_view`;
- `get_pulse_today_entry`.

Tests directs:

- `backend/tests/test_imperium_daily_plan_foundation.py`;
- `backend/tests/test_imperium_daily_plan_contracts.py`;
- invariant repo `test_patch_13a_daily_plan_foundation_is_read_only_and_uses_existing_snapshots`.

### `daily_plans.py` pluriel

Role reel:

- service CRUD persistant;
- cree une ligne `ImperiumDailyPlan`;
- lit la table `imperium_daily_plans`;
- gere idempotency;
- cree des events applicatifs `day.plan.created`, `day.plan.activated`, `day.plan.completed`, `day.plan.cancelled`;
- gere transitions `draft -> active`, `draft/active -> completed/cancelled`;
- construit `generated_from` et `plan_blocks`.

Routes actives:

- importe par `backend/app/api/v1/routes/imperium.py`;
- `POST /api/imperium/day/plan`;
- `GET /api/imperium/day/plan/today`;
- `GET /api/imperium/day/plan`;
- `POST /api/imperium/day/plan/{plan_id}/activate`;
- `POST /api/imperium/day/plan/{plan_id}/complete`;
- `POST /api/imperium/day/plan/{plan_id}/cancel`.

Tests directs:

- `backend/tests/test_priority_reconciliation.py` importe `_collect_plan_sources` et `create_daily_plan`;
- `backend/tests/test_repo_invariants.py` verifie que `daily_plans.py` lit `get_canonical_priority_order` et non `ImperiumPriorityRule`.

### Sont-ils la meme chose?

Non.

| Point | `daily_plan.py` | `daily_plans.py` |
|---|---|---|
| Nature | snapshot read-only | plan persiste CRUD |
| Route principale | `/api/imperium/daily-plan` | `/api/imperium/day/plan...` |
| Schema Pydantic | `app.schemas.daily_plan.DailyPlanResponse` | `app.schemas.imperium.DailyPlanResponse` |
| Table `imperium_daily_plans` | non lue | lue/ecrite |
| Events | non | oui, ancien modele `Event` |
| Idempotency-Key | non requis | requis sur writes |
| Path source | habits/check-ins via `get_path_today_view` | legacy `ImperiumPathItem` |
| Vault source | via dashboard foundation, canonique `ImperiumVaultTransaction` | aucune lecture Vault |
| Mission guard | `get_current_active_mission` detecte plusieurs actives | simple `db.scalar` sur mission active, pas de detection explicite |
| AI/local model | aucun | aucun |

### Lequel est branche dans `imperium_daily_plan.py`?

`imperium_daily_plan.py` branche uniquement le service singulier:

```text
from app.services.imperium.daily_plan import get_daily_plan_snapshot
@router.get("/daily-plan")
```

### Lequel est mort/legacy?

Ni l'un ni l'autre n'est totalement mort:

- `daily_plan.py` est le contrat frontend/MVP read-only moderne.
- `daily_plans.py` est encore actif via `routes/imperium.py` et lu par dashboard/weekly report via la table `ImperiumDailyPlan`.

Mais `daily_plans.py` porte le chemin historique/persistant et une dependance Path legacy. Il doit etre classe **legacy actif / contrat a trancher**, pas supprime sans decision, car ses routes sont encore exposees et ses tests existent.

## Partie 3 - Dependances legacy

### Surface active `/api/imperium/daily-plan` via `daily_plan.py`

Lectures:

| Source | Chemin | Canonique ou legacy | Note |
|---|---|---|---|
| Mission active | `get_current_active_mission` -> `ImperiumMission` | canonique | Detecte plusieurs missions actives et la route retourne 409 |
| Dashboard foundation | `get_imperium_dashboard_foundation` | canonique pour le snapshot foundation | Lit mission/vault/path/pulse |
| Vault via dashboard foundation | `get_vault_summary` -> `ImperiumVaultTransaction` | canonique recent | Ne lit pas `VaultTransaction` dans ce chemin |
| Path via dashboard foundation et appel direct | `get_path_today_view` -> `ImperiumPathHabit` + `ImperiumPathCheckIn` | canonique Path V1 | Ne lit pas `ImperiumPathItem` dans ce chemin |
| Pulse | `get_pulse_today_entry` -> `ImperiumPulseEntry` | canonique | read-only |

Conclusion pour le snapshot moderne: **pas de dependance directe vers les sources legacy vault/path deja reperees**.

### Surface persistante `/api/imperium/day/plan...` via `daily_plans.py`

Lectures:

| Source | Chemin | Canonique ou legacy | Note |
|---|---|---|---|
| Mission active | `ImperiumMission` status `active` | canonique table missions | Mais `db.scalar`, pas de garde multi-active explicite |
| Path items | `ImperiumPathItem` | **legacy Path** | Dette deja signalee dans l'audit Path |
| Priorites | `get_canonical_priority_order` -> `ImperiumUserPriority` | canonique Decision Framework | Ne lit plus `ImperiumPriorityRule` |
| Day review | `ImperiumDayReview` latest | canonique historique Imperium | OK |
| Vault | aucune lecture directe | n/a | Pas de probleme Vault dans `daily_plans.py` |

### Lecteurs connexes encore legacy

- `get_dashboard_snapshot` (ancien dashboard, pas foundation) lit encore `VaultTransaction` et `ImperiumPathItem`.
- `weekly_report.py` lit encore `VaultTransaction`, `ImperiumPathItem` et `ImperiumPriorityRule`.
- `dashboard.py` foundation lit `ImperiumVaultTransaction` et Path habits/check-ins, mais `get_dashboard_snapshot` lit les anciennes sources.

Donc le daily plan moderne est propre, mais l'ecosysteme autour garde des lecteurs legacy actifs.

## Partie 4 - Coherence logique avec doc 52 section 9

### Ce que doc 52 section 9 demande

Doc 52 section 9 decrit une vraie instanciation quotidienne:

- generation chaque matin apres morning check-in;
- instanciation du rolling monthly plan;
- adaptation a l'etat reel;
- plan avec horaires, temps de trajet, buffers, respect calendrier;
- missions qui deviennent `active`;
- hooks de replanning;
- generation par le modele local en V1, avec fallback cloud si qualite insuffisante.

### Ce que le code fait

`daily_plan.py`:

- ne genere pas de plan;
- ne lit pas monthly plan;
- ne choisit pas de mission;
- ne score pas les missions;
- ne planifie pas d'horaires;
- ne change aucun statut;
- ne lance aucun modele local;
- renvoie un snapshot read-only de modules existants.

`daily_plans.py`:

- cree un plan persiste `draft`;
- copie mission active + items Path legacy + contexte de priorites + dernier day review;
- ne choisit pas de mission;
- ne lit pas monthly plan;
- ne calcule pas de scoring;
- ne cree pas de timed plan;
- ne lance aucun modele local;
- ne fait pas de replanning.

### Hierarchie `imperium_user_priorities`

Point positif:

- `daily_plans.py` utilise bien `get_canonical_priority_order`;
- `get_canonical_priority_order` lit `imperium_user_priorities` et retombe sur un ordre V1 transient si aucune ligne n'existe;
- il ne lit plus `imperium_priority_rules`.

Limite:

- cette hierarchie est seulement ajoutee comme bloc `priority_context`;
- elle n'est pas utilisee pour selectionner, scorer, ordonner ou instancier les missions du jour.

### Scoring documente

Le daily plan n'utilise pas le scoring doc 52 pour instancier le jour.

Le scoring existe cote missions/backlog (`ImperiumMissionScore`, `weighted_score`, `priority_bucket` public), mais:

- `daily_plan.py` ne le lit pas;
- `daily_plans.py` ne le lit pas;
- aucune requete `ImperiumMissionScore` dans ces deux services;
- aucun tri par score pour construire le plan du jour.

### V1 model choice

Doc 52 section 9.4 dit que la daily instantiation est generee par le modele local en V1.

Code actuel:

- aucun appel Qwen/local model;
- aucun prompt daily plan;
- aucun fallback;
- aucun champ `generated_model`;
- aucun `AIResult`.

Ce n'est pas forcement une erreur si le module actuel est volontairement "foundation/read-only", mais ce n'est pas conforme a l'instanciation IA de doc 52.

## Points de coherence produit

### Regle une seule mission active

- Le snapshot moderne `/api/imperium/daily-plan` respecte le garde-fou en appelant `get_current_active_mission`; si plusieurs missions actives existent, la route renvoie 409.
- Le flux persistant `/api/imperium/day/plan` recupere une mission active avec `db.scalar(select(ImperiumMission).where(...status == "active"))`. Il ne detecte pas explicitement plusieurs missions actives.

### Backend brain vs app interface

- Le snapshot moderne est coherent avec "apps display/collect only": il observe et consolide.
- Le flux persistant est coherent avec doc 28 "deterministic snapshot", mais pas avec doc 52 "brain instantiation".

## Conclusion

Classification: **(c) divergent**

Raison:

- schema table bien code et bien aligne avec doc 28;
- mais docs 04/05 disent snapshot read-only sans persistence;
- doc 52 decrit un autre schema et une autre logique d'instanciation;
- deux services actifs ont presque le meme nom mais des responsabilites differentes;
- le chemin persistant garde une dependance Path legacy.

### Actions recommandees

1. **Trancher le contrat daily plan V1**
   - Option A: daily plan V1 = snapshot read-only `/api/imperium/daily-plan`. Alors documenter `imperium_daily_plans` comme legacy/anticipation et deprecier `/day/plan...`.
   - Option B: daily plan V1 = plan persiste `imperium_daily_plans`. Alors rebrancher clairement le frontend/contrats vers `/day/plan...` et aligner docs 04/05.

2. **Renommer ou isoler les services**
   - Garder `daily_plan.py` pour snapshot read-only.
   - Renommer `daily_plans.py` en nom explicite type `daily_plan_records.py` ou `daily_plan_legacy_records.py`, selon decision.

3. **Delegacy**
   - Remplacer `ImperiumPathItem` dans `daily_plans.py` par Path V1 habits/check-ins si le flux persistant reste actif.
   - Verifier aussi `weekly_report.py` et `get_dashboard_snapshot`, qui gardent `VaultTransaction`, `ImperiumPathItem`, `ImperiumPriorityRule`.

4. **Aligner doc schema**
   - Si `imperium_daily_plans` reste canonique, doc 28 doit rester proprietaire fonctionnel et doc 52 section 12 doit etre marquee future/V2 ou corrigee.
   - Si doc 52 devient proprietaire, ajouter migration future: `monthly_plan_id`, `plan_json`, `generated_at`, `generated_model`, `is_adapted`, `adaptation_reason`, `cost_eur`, et trancher `local_date` vs `date`, `plan_status` vs `status`.

5. **Aligner logique doc 52 section 9**
   - Implementer seulement quand le MVP decide de passer de snapshot/foundation a vraie instanciation:
     - lecture monthly plan;
     - lecture backlog/scoring;
     - usage `imperium_user_priorities`;
     - generation locale Qwen;
     - stockage du modele et raison d'adaptation;
     - tests pytest avant code.

### Action immediate sans code fonctionnel

Mettre a jour l'index d'audit pour signaler:

- divergence;
- deux surfaces actives;
- `daily_plan.py` moderne read-only;
- `daily_plans.py` persistant legacy actif;
- schema execute proprietaire: migration + ORM, doc 28 alignee;
- doc 52 future/non implementee.
