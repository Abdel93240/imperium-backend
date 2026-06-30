# Inventaire brut des tables codees

Date de recensement: 2026-06-30

Scope: lecture des migrations `backend/alembic/versions/*.py`, des modeles
`backend/app/models/*.py`, des references de services/routes, et des docs
`docs_master/*.md` + rapports `gap_analysis_v1/*.md` deja presents.

Ce document ne tranche pas le schema cible. Il recense l'etat des lieux.

## 1. Liste exhaustive des tables definies dans le code

Notes de lecture:

- Le nombre de colonnes est approximatif mais base sur l'etat final Alembic
  quand une migration ajoute des colonnes apres creation.
- Les modeles heritent de `Base.id`; certains modeles ne declarent pas toutes
  les colonnes techniques creees par migration. Ces ecarts sont notes quand ils
  sont visibles.

| Table | Domaine | Fichier(s) de definition code | Colonnes approx. | Definition documentaire actuelle |
|---|---|---:|---:|---|
| `users` | SOCLE/AUTH | migration `backend/alembic/versions/20260425_0001_initial_skeleton.py`; modele `backend/app/models/auth.py` | 10 en migration / ~8 ORM | ORPHELINE pour definition de colonnes. Mentionnee dans docs 17/21 surtout infra/permissions. |
| `devices` | SOCLE/AUTH | migration `20260425_0001_initial_skeleton.py`; modele `backend/app/models/auth.py` | 10 en migration / ~8 ORM | ORPHELINE pour definition de colonnes. Mentionnee dans docs 21/23. |
| `refresh_tokens` | SOCLE/AUTH | migration `20260425_0001_initial_skeleton.py` + ajout `20260426_0002_security_hardening.py`; modele `backend/app/models/auth.py` | 11 | Doc partielle: `23_REFRESH_TOKEN_LIFECYCLE.md`; permissions dans doc 21. |
| `auth_events` | SOCLE/AUTH/AUDIT | migration `20260425_0001_initial_skeleton.py`; modele `backend/app/models/auth.py` | 9 | ORPHELINE pour definition de colonnes. Doc 21 decrit surtout append-only/permissions. |
| `events` | SOCLE/TRANSVERSE | migration `20260425_0001_initial_skeleton.py` + contrainte `20260430_0011_events_user_scoped_event_id.py`; modele `backend/app/models/event.py` | 16 | Doc partielle: docs 21/31/04. Pas proprietaire central clair dans doc 05. |
| `idempotency_keys` | SOCLE/TRANSVERSE | migration `20260425_0001_initial_skeleton.py`; modele `backend/app/models/idempotency.py` | 12 en migration / ~10 ORM | ORPHELINE pour definition de colonnes. Mentions dispersees dans docs 21/contrats metier. |
| `ai_tasks` | SOCLE/AI | migration `20260430_0012_ai_tasks_results_foundation.py`; modele `backend/app/models/ai.py` | 18 | `31_AI_TASKS_AND_RESULTS_CONTRACT.md` §7.1; aussi doc 16. |
| `ai_results` | SOCLE/AI | migration `20260430_0012_ai_tasks_results_foundation.py`; modele `backend/app/models/ai.py` | 13 | `31_AI_TASKS_AND_RESULTS_CONTRACT.md` §7.2; aussi doc 16. |
| `ai_result_validations` | SOCLE/AI | migration `20260430_0012_ai_tasks_results_foundation.py`; modele `backend/app/models/ai.py` | 8 | `31_AI_TASKS_AND_RESULTS_CONTRACT.md` §7.3; aussi doc 16. |
| `ai_memories` | SOCLE/MEMOIRE | migration `20260502_0017_ai_memories_foundation.py`; modele `backend/app/models/ai.py` | 22 | Docs 31/32 decrivent la version text-only active. Docs 09/38/75 decrivent un canon pgvector divergent. |
| `imperium_events` | SOCLE/TRANSVERSE ou IMPERIUM | migration `20260526_0029_imperium_events_foundation.py` + contraintes `0030/0031`; modele `backend/app/models/imperium.py` | 10 | `05_DATABASE_SCHEMA.md` section Event Foundation 23A; aussi `04_MVP_BACKEND_CONTRACTS.md`. |
| `imperium_day_reviews` | IMPERIUM/PLANNING | migration `20260426_0004_imperium_day_reviews.py`; modele `backend/app/models/imperium.py` | 19 | `24_DAY_FINISHED_WORKFLOW.md` Storage; liste aussi doc 43; lu par doc 29. |
| `imperium_missions` | IMPERIUM/PLANNING | migration `20260426_0005_imperium_missions.py` + ajouts `20260511_0020_imperium_missions_decision_fields.py`; modele `backend/app/models/imperium.py` | 20 | `25_CURRENT_MISSION_WORKFLOW.md`; doc 43 §5; doc 52 ajoute champs/scoring. |
| `imperium_priority_rules` | IMPERIUM/PLANNING | migration `20260426_0006_imperium_priority_rules.py`; modele `backend/app/models/imperium.py` | 10 | `26_PRIORITY_RULES_WORKFLOW.md`, mais marque legacy/superseded; doc 43 liste; doc 52 le remplace conceptuellement. |
| `imperium_user_priorities` | IMPERIUM/DECISION | migration `20260504_0019_decision_framework_foundation.py`; modele `backend/app/models/imperium.py` | 8 | `52_AI_DECISION_FRAMEWORK.md` §12; doc 26 indique que c'est la source canonique active. |
| `imperium_mission_scores` | IMPERIUM/DECISION | migration `20260504_0019_decision_framework_foundation.py`; modele `backend/app/models/imperium.py` | 11 | `52_AI_DECISION_FRAMEWORK.md` §12; patch aussi dans doc 31. |
| `imperium_daily_plans` | IMPERIUM/PLANNING | migration `20260426_0009_imperium_daily_plans.py`; modele `backend/app/models/imperium.py` | 14 | `28_DAILY_PLAN_WORKFLOW.md`; doc 52 §12 contient aussi un schema; doc 43 liste. |
| `imperium_calendar_events` | IMPERIUM/PLANNING/CALENDAR | migration `20260512_0022_imperium_calendar_events_foundation.py`; modele `backend/app/models/imperium.py` | 11 | `51_FUTURE_CALENDAR.md` minimal foundation + schema. |
| `imperium_path_items` | RELIGIEUX/LEGACY + PLANNING | migration `20260426_0008_imperium_path_items.py`; modele `backend/app/models/imperium.py` | 20 | Doc 05/04 signalent projection legacy/deprecated; doc 29 le lit; doc 43 le liste indirectement via tables operationnelles. |
| `imperium_path_habits` | RELIGIEUX | migration `20260525_0027_imperium_path_habits_check_ins.py`; modele `backend/app/models/imperium.py` | 9 | ORPHELINE dans `docs_master` pour definition de table. Recensee dans `gap_analysis_v1/GAP_path.md` comme code V1. |
| `imperium_path_check_ins` | RELIGIEUX | migration `20260525_0027_imperium_path_habits_check_ins.py`; modele `backend/app/models/imperium.py` | 9 | ORPHELINE dans `docs_master` pour definition de table. Recensee dans `gap_analysis_v1/GAP_path.md` comme code V1. |
| `imperium_pulse_entries` | SANTE/PULSE | migration `20260525_0028_imperium_pulse_entries.py`; modele `backend/app/models/imperium.py` | 12 | Doc 04/05 mentionnent Pulse Foundation 11A, mais sans definition complete de colonnes. Recensee dans `gap_analysis_v1/GAP_pulse.md`. |
| `vault_transactions` | FINANCE/LEGACY | migration `20260426_0007_vault_transactions.py`; modele `backend/app/models/vault.py` | 16 | `27_VAULT_TRANSACTIONS_WORKFLOW.md` l'appelle canonique; doc 42 l'utilise encore. Conflit avec ledger `imperium_vault_transactions`. |
| `imperium_vault_transactions` | FINANCE | migration `20260525_0024_imperium_vault_ledger_foundation.py` + ajouts `0025/0026`; modele `backend/app/models/vault.py` | 17 | Doc 05 contient des regles append-only/reversal, mais pas dictionnaire de colonnes. Recensee dans `gap_analysis_v1/GAP_vault.md`. |
| `imperium_weekly_review_states` | WR/IMPERIUM | migration `20260427_0010_imperium_weekly_review_states.py`; modele `backend/app/models/imperium.py` | 11 | Doc 43 liste la table; definition detaillee absente. |
| `imperium_weekly_review_sessions` | WR | migration `20260430_0013_weekly_review_conversation.py`; modele `backend/app/models/imperium.py` | 15 | `32_WR_INTERACTIVE_WORKFLOW.md` tables ajoutees + state machine; docs 31/32 patches. |
| `imperium_weekly_review_messages` | WR | migration `20260430_0013_weekly_review_conversation.py`; modele `backend/app/models/imperium.py` | 10 | `32_WR_INTERACTIVE_WORKFLOW.md`; docs 31/32 patches. |
| `imperium_weekly_review_final_reports` | WR | migration `20260430_0013_weekly_review_conversation.py` + contraintes `20260430_0014_wr_final_report_candidate_history.py`; modele `backend/app/models/imperium.py` | 14 | `32_WR_INTERACTIVE_WORKFLOW.md`; doc 31 sections 27A/27B. |
| `imperium_memory_candidate_decisions` | WR/MEMOIRE | migration `20260501_0015_memory_candidate_decisions.py`; modele `backend/app/models/imperium.py` | 14 | `32_WR_INTERACTIVE_WORKFLOW.md` patch 4M-4P; doc 31 section 27C. |

## 2. Tables codees mais definition documentaire absente ou partielle

Marquage strict sur la definition de table/colonnes, pas sur les simples mentions.

### ORPHELINE pour definition de colonnes

- `users`
- `devices`
- `auth_events`
- `idempotency_keys`
- `imperium_path_habits`
- `imperium_path_check_ins`
- `imperium_weekly_review_states`

### Documentation partielle ou conflictuelle

- `events`: enveloppe et append-only documentes, mais pas proprietaire central
  unique dans doc 05.
- `imperium_pulse_entries`: surface Pulse 11A mentionnee dans docs 04/05, mais
  colonnes surtout visibles dans code et gap Pulse.
- `imperium_vault_transactions`: regles append-only/reversal presentes dans doc
  05, mais colonnes surtout visibles dans code et gap Vault.
- `ai_memories`: la table est documentee, mais la version active text-only
  docs 31/32 diverge du canon pgvector docs 09/38/75.
- `vault_transactions`: doc 27 l'appelle canonique alors que le gap Vault et
  les endpoints Imperium utilisent aussi `imperium_vault_transactions`.

## 3. Doublons / conflits connus

### `vault_transactions` vs `imperium_vault_transactions`

Tables:

- `vault_transactions`: 16 colonnes, montants `Numeric(12, 2)`, `wallet`,
  `source_app`, FK optionnelle vers `events`.
- `imperium_vault_transactions`: 17 colonnes, montants en cents,
  append-only/reversal, `local_date`, `timezone`.

Actif/lu dans le code:

- `vault_transactions` est actif via `backend/app/api/v1/routes/vault.py` et
  `backend/app/services/vault/transactions.py`.
- Il est aussi lu par `backend/app/services/imperium/dashboard.py` et
  `backend/app/services/imperium/weekly_report.py`.
- `imperium_vault_transactions` est actif via
  `backend/app/api/v1/routes/imperium_vault.py`,
  `backend/app/services/imperium/vault_transactions.py` et
  `backend/app/services/imperium/vault.py`.

Constat brut:

- Les deux ledgers sont actifs.
- Doc 27 documente `vault_transactions` comme canonique.
- Gap Vault recense `imperium_vault_transactions` comme ledger canonique actif
  cote `/api/imperium/vault`.
- Les deux schemas ne portent pas les memes champs ni la meme representation
  monetaire.

### `events` vs `imperium_events`

Tables:

- `events`: event store generique, dotted event types, enum `source_app`,
  `privacy_level`, correlation/causation, payload JSONB.
- `imperium_events`: journal Imperium reduit, `event_type` snake_case strict,
  `source_module`, `payload_json`, idempotency optionnelle.

Actif/lu dans le code:

- `events` est expose via `/api/events` et `backend/app/services/events/ingestion.py`.
- Plusieurs services ecrivent des `Event`: Vault legacy, missions, daily plans,
  day finish, path items, priorities, calendar.
- `imperium_events` est expose via `/api/imperium/events`,
  `backend/app/services/imperium/events.py` et lu par
  `backend/app/services/imperium/event_readers.py`.

Constat brut:

- Deux event stores actifs coexistent.
- Les formats ne sont pas compatibles: dotted vs snake_case, enveloppe riche vs
  enveloppe reduite.
- Les rapports gap existants constatent l'absence de consumer cross-module
  prouve.

### `imperium_path_items` legacy vs `imperium_path_habits` / `imperium_path_check_ins`

Tables:

- `imperium_path_items`: item religieux/planning date, statut, planning,
  `metadata`.
- `imperium_path_habits`: habitudes Path generiques.
- `imperium_path_check_ins`: check-ins par habitude/date.

Actif/lu dans le code:

- `imperium_path_items` reste actif via `backend/app/services/imperium/path_items.py`.
- Il est lu par `backend/app/services/imperium/dashboard.py`,
  `backend/app/services/imperium/daily_plans.py` et
  `backend/app/services/imperium/weekly_report.py`.
- `imperium_path_habits` et `imperium_path_check_ins` sont actifs via
  `backend/app/services/path/habits.py` et
  `backend/app/api/v1/routes/imperium_path.py`.

Constat brut:

- Les deux surfaces Path sont actives.
- Le legacy `imperium_path_items` alimente encore dashboard/daily plan/weekly
  report.
- Les habits/check-ins sont le noyau Path V1 code, mais leur definition de table
  n'est pas encore dans `docs_master`.

### `daily_plan` vs `daily_plans`

Surfaces:

- `backend/app/services/imperium/daily_plan.py`: snapshot read-only expose par
  `/api/imperium/daily-plan`; ne cree pas de row.
- `backend/app/services/imperium/daily_plans.py`: plan persistant base sur la
  table `imperium_daily_plans`, expose via `/api/imperium/day/plan...`.

Actif/lu dans le code:

- La surface snapshot est referencee par le module frontend/home/contracts et
  route `backend/app/api/v1/routes/imperium_daily_plan.py`.
- La surface persistante cree/lit/active/complete/cancel des rows
  `imperium_daily_plans`.
- `imperium_daily_plans` est lu par dashboard et weekly report.

Constat brut:

- Les deux surfaces sont actives.
- Le nom singulier/pluriel correspond a deux comportements differents:
  read-only consolidation vs table persistante.
- Gap Imperium signale deja cette divergence.

### `imperium_priority_rules` vs `imperium_user_priorities`

Tables:

- `imperium_priority_rules`: ancienne hierarchie prioritaire.
- `imperium_user_priorities`: source de priorites du Decision Framework.

Actif/lu dans le code:

- `imperium_user_priorities` est lu/ecrit par
  `backend/app/services/imperium/decision_framework.py`; dashboard l'utilise.
- `imperium_priority_rules` reste lu par weekly report et le service legacy
  `backend/app/services/imperium/priorities.py`.
- Les routes legacy declarent que les writes priority_rules sont bloques et
  que `imperium_user_priorities` est canonical_source.

Constat brut:

- Les deux tables existent.
- `imperium_user_priorities` est la source active du scoring/priorites moderne.
- `imperium_priority_rules` reste en compatibilite/lecture historique.

### `imperium_weekly_review_states` vs `imperium_weekly_review_sessions`

Tables:

- `imperium_weekly_review_states`: readiness/launch flags par semaine.
- `imperium_weekly_review_sessions`: session conversationnelle WR complete.

Actif/lu dans le code:

- `imperium_weekly_review_states` est utilise par
  `backend/app/services/imperium/weekly_review_state.py` et la route
  `/api/imperium/weekly-review/state`.
- `imperium_weekly_review_sessions` porte le flux WR interactif dans
  `backend/app/services/imperium/weekly_review_conversation.py`.

Constat brut:

- Les deux tables portent de l'etat WR.
- `states` semble readiness/ancien endpoint; `sessions` porte la conversation,
  les messages et les final reports.

### Autres doublons nommes dans les docs mais non codes

- Pulse doc 40 annonce `meals`, `workouts`, `food_stock_items`,
  `pulse_recommendations` comme existantes, mais elles ne sont pas definies dans
  les migrations/modeles recenses.
- Path doc 41 annonce `prayer_logs`, `fasting_logs`, `sadaqa_records` comme
  existantes, mais elles ne sont pas definies dans les migrations/modeles
  recenses.
- Vault doc 42 annonce `weekly_finance_summaries`, mais aucune table codee
  correspondante n'a ete trouvee.
- Imperium doc 43 annonce/future `imperium_daily_plan_versions`,
  `imperium_replan_events`, `imperium_user_decisions`; aucune table codee
  correspondante n'a ete trouvee.

## 4. Classement par domaine

### SOCLE / TRANSVERSE

- `users`
- `devices`
- `refresh_tokens`
- `auth_events`
- `events`
- `imperium_events`
- `idempotency_keys`
- `ai_tasks`
- `ai_results`
- `ai_result_validations`
- `ai_memories`

Notes:

- `imperium_events` semble transverse dans son intention future, mais son nom,
  ses routes et ses contraintes le rattachent aussi a Imperium.
- `ai_memories` est transverse par vision, mais son usage code actuel est surtout
  WR/memory candidate commit.

### FINANCE

- `vault_transactions`
- `imperium_vault_transactions`

Notes:

- Les deux sont actifs.
- `vault_transactions` est encore lu par dashboard et weekly report.
- `imperium_vault_transactions` porte l'API Imperium Vault append-only actuelle.

### SANTE / PULSE

- `imperium_pulse_entries`

Notes:

- C'est la seule table Pulse reelle trouvee dans code.
- Les tables Pulse riches citees en docs ne sont pas codees.

### RELIGIEUX / PATH

- `imperium_path_items`
- `imperium_path_habits`
- `imperium_path_check_ins`

Notes:

- `imperium_path_items` est legacy mais encore lu.
- `imperium_path_habits` et `imperium_path_check_ins` sont la surface Path V1
  generique codee.

### IMPERIUM / PLANNING / DECISION

- `imperium_day_reviews`
- `imperium_missions`
- `imperium_priority_rules`
- `imperium_user_priorities`
- `imperium_mission_scores`
- `imperium_daily_plans`
- `imperium_calendar_events`

Notes:

- `imperium_priority_rules` est legacy/compatibilite.
- `imperium_user_priorities` + `imperium_mission_scores` correspondent au
  Decision Framework.
- `imperium_calendar_events` est calendar/future planning, code comme fondation
  minimale.

### WR / WEEKLY REVIEW

- `imperium_weekly_review_states`
- `imperium_weekly_review_sessions`
- `imperium_weekly_review_messages`
- `imperium_weekly_review_final_reports`
- `imperium_memory_candidate_decisions`

Notes:

- `imperium_memory_candidate_decisions` est WR mais touche le domaine memoire.
- `imperium_weekly_review_states` et `imperium_weekly_review_sessions` portent
  deux niveaux d'etat WR.

### VTC / RIDES

- Aucune table VTC/ride definie dans les migrations ou modeles recenses.

Notes:

- Les docs Vector decrivent scoring, zones, sessions, fuel, events, mais aucune
  table Vector/Rides n'est actuellement definie dans `backend/app/models/*.py`
  ou `backend/alembic/versions/*.py`.

### VEHICULE

- Aucune table vehicule definie dans les migrations ou modeles recenses.

Notes:

- Les docs Vector/fuel existent, mais pas de table vehicule/fuel codee dans le
  recensement actuel.

## 5. Recapitulatif brut

- Total tables codees trouvees: 29.
- Toutes les tables creees par migrations ont un modele SQLAlchemy correspondant
  dans `backend/app/models/*.py`.
- Les definitions documentaires sont dispersees entre docs 04, 05, 16, 23, 24,
  25, 26, 27, 28, 31, 32, 41, 42, 43, 51, 52, 75 et rapports gap.
- Le doc 05 ne possede actuellement qu'une definition detaillee claire pour
  `imperium_events` et des fragments/notes pour Vault, Pulse et Path.
- Les doublons actifs majeurs constates sont:
  `vault_transactions` / `imperium_vault_transactions`,
  `events` / `imperium_events`,
  `imperium_path_items` / `imperium_path_habits` + `imperium_path_check_ins`,
  surface `daily_plan` / table `imperium_daily_plans`,
  `imperium_priority_rules` / `imperium_user_priorities`,
  `imperium_weekly_review_states` / `imperium_weekly_review_sessions`.
