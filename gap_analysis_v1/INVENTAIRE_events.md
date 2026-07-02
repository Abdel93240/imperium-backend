# INVENTAIRE EXHAUSTIF DES EVENTS — état des lieux brut

Date : 2026-07-02. Périmètre : `backend/` (hors `.venv`, `__pycache__`, migrations générées),
plus `ops/`, `scripts/`, `weekly-review/` pour les consumers externes.
Référence : gap_analysis_v1/PHASE_0_DECISIONS.md (D2 : `events` canonique, D3 : dotted
`domaine.sujet.action`, domaines génériques). Ce document RECENSE, il ne tranche rien.

Il existe TROIS journaux d'events distincts dans le code :

| Journal (table) | Statut (D2) | Format imposé | Émetteurs internes | Lecteurs |
|---|---|---|---|---|
| `events` | CANONIQUE | dotted (regex API) ; libre côté ORM interne | 8 services | AUCUN |
| `imperium_events` | DÉPRÉCIÉ | snake_case FORCÉ (regex + CHECK DB) | aucun (API générique seule) | 1 reader + 2 routes GET |
| `auth_events` | journal technique auth (hors D2) | libre (Text) | auth service + 2 CLI | AUCUN |

Les trois tables sont protégées append-only par triggers (migrations
`20260426_0002_security_hardening.py`, `20260426_0003_append_only_truncate_guards.py`,
`20260526_0031_imperium_events_constraints_hardening.py` ; vérifié par
`backend/tests/test_events_append_only.py`).

Il n'existe AUCUN mécanisme pub/sub, bus, handler ou subscriber dans le code : chaque
"émission" est un INSERT SQL dans la même transaction que l'écriture métier. Aucun
workflow n8n (`ops/n8n/workflows/*.json`) ne référence d'event.

---

## 1. EVENTS ÉMIS

### 1.A — Vers la table `events` (journal canonique)

Tous construits via un helper local `_build_event(...)` ou inline, avec systématiquement :
`schema_version="1.0"`, `occurred_at=now()` serveur, `device_id=None`, `causation_id=None`,
`correlation_id=f"corr_<type>_{uuid4().hex}"` (aléatoire par event), `event_id=f"evt_{uuid4().hex}"`.

| # | event_type (verbatim) | Fichier | Fonction | Format | source_app | privacy | Payload observé |
|---|---|---|---|---|---|---|---|
| 1 | `vault.transaction.created` | `backend/app/services/vault/transactions.py:209` | `create_transaction` (via `_build_event`) | dotted 3 niveaux | `vault` | high | `transaction_id` + champs de `CreateVaultTransactionRequest` (occurred_at, local_date, timezone, transaction_type, wallet, category, label, amount, currency, notes) |
| 2 | `path.item.created` | `backend/app/services/imperium/path_items.py:95` | `create_path_item` | dotted 3 niveaux | `imperium` | medium | `item_id` + champs de `CreatePathItemRequest` (local_date, timezone, title, description, category, priority_key, planned_start/end, status, source, sort_order, metadata) |
| 3 | `path.item.started` | `backend/app/services/imperium/path_items.py:138` | `start_path_item` (via `_transition_path_item`) | dotted 3 niveaux | `imperium` | medium | `{item_id}` |
| 4 | `path.item.completed` | `backend/app/services/imperium/path_items.py:160` | `complete_path_item` (via `_transition_path_item`) | dotted 3 niveaux | `imperium` | medium | `{item_id}` |
| 5 | `path.item.skipped` | `backend/app/services/imperium/path_items.py:183` | `skip_path_item` (via `_transition_path_item`) | dotted 3 niveaux | `imperium` | medium | `{item_id, skip_reason}` |
| 6 | `path.item.cancelled` | `backend/app/services/imperium/path_items.py:207` | `cancel_path_item` (via `_transition_path_item`) | dotted 3 niveaux | `imperium` | medium | `{item_id}` |
| 7 | `day.plan.created` | `backend/app/services/imperium/daily_plans.py:87` | `create_daily_plan` | dotted 3 niveaux | `imperium` | medium | `plan_id` + champs de `CreateDailyPlanRequest` + `generated_from` |
| 8 | `day.plan.activated` | `backend/app/services/imperium/daily_plans.py:158` | `activate_daily_plan` (via `_transition_daily_plan`) | dotted 3 niveaux | `imperium` | medium | `{plan_id, new_status}` |
| 9 | `day.plan.completed` | `backend/app/services/imperium/daily_plans.py:181` | `complete_daily_plan` (via `_transition_daily_plan`) | dotted 3 niveaux | `imperium` | medium | `{plan_id, new_status}` |
| 10 | `day.plan.cancelled` | `backend/app/services/imperium/daily_plans.py:204` | `cancel_daily_plan` (via `_transition_daily_plan`) | dotted 3 niveaux | `imperium` | medium | `{plan_id, new_status}` |
| 11 | `day.finished` | `backend/app/services/imperium/day_finish.py:85` | `finish_day` (Event inline) | dotted **2 niveaux** | `imperium` | medium | `FinishDayRequest` complet (local_date, timezone, day_status, energy_level, fatigue_level, sleep_quality, stress_level, mood, main_win, main_problem, completed_items, missed_items, notes, free_text) ; `correlation_id=f"corr_day_finish_{review.id}"` (seul cas non-aléatoire) |
| 12 | `calendar.event.created` | `backend/app/services/imperium/calendar.py:166` | `create_calendar_event` (via `_build_event`) | dotted 3 niveaux | `imperium` | medium | `calendar_event_id` + champs de `CalendarEventCreate` (event_type calendrier ∈ event/deadline/vacation, title, starts_at, ends_at, blocks_time, location, notes) |
| 13 | `priority.rules.updated` | `backend/app/services/imperium/priorities.py:139` | `replace_priority_rules` (via `_build_event`) | dotted 3 niveaux | `imperium` | medium | `ReplacePriorityRulesRequest` complet (liste priorities : priority_key, label, rank_order, importance_score) |
| 14 | `mission.started` | `backend/app/services/imperium/missions.py:142` | `start_mission` (via `_build_event`) | dotted **2 niveaux** | `imperium` | medium | `mission_id` + champs de `StartMissionRequest` (title, category, domain, priority_level, mission_type_category, planned_start_at, planned_end_at) |
| 15 | `mission.started` (2e émetteur) | `backend/app/services/imperium/missions.py:419` | `promote_backlog_mission` (via `_build_event`) | dotted 2 niveaux | `imperium` | medium | `{mission_id, source: "backlog_promotion"}` — même type que #14, payload différent |
| 16 | `mission.backlog.created` | `backend/app/services/imperium/missions.py:216` | `create_backlog_mission` (via `_build_event`) | dotted 3 niveaux | `imperium` | medium | `mission_id` + champs de `BacklogMissionCreateRequest` |
| 17 | `mission.{outcome}` (DYNAMIQUE, f-string) | `backend/app/services/imperium/missions.py:485` | `complete_mission` (via `_build_event`) | dotted 2 niveaux | `imperium` | medium | `{mission_id, outcome, reason}` (clés None retirées). `outcome` ∈ `MissionCompletionOutcome` = `completed` / `failed` / `abandoned` (`backend/app/schemas/imperium.py:263`) → produit `mission.completed`, `mission.failed`, `mission.abandoned` |
| 18 | `mission.failed` (2e émetteur) | `backend/app/services/imperium/missions.py:552` | `fail_mission` (via `_build_event`) | dotted 2 niveaux | `imperium` | medium | `{mission_id, failure_reason, user_reported_signals, ai_usable_reason}` — même type que #17-failed, payload différent |

**Émission générique par API** (event_type libre, fourni par le client) :
- `POST /api/v1/events` — `backend/app/api/v1/routes/events.py:12` (`ingest_event_route`)
  → `backend/app/services/events/ingestion.py:18` (`ingest_event`).
  Enveloppe = `EventEnvelope` (`backend/app/schemas/events.py:22`) : event_id, event_type,
  schema_version, occurred_at, received_at, source_app, device_id, user_id (ignoré au
  stockage, dérivé du JWT), idempotency_key, correlation_id, causation_id, privacy_level, payload.
  Regex imposée : `^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*)+$` → dotted obligatoire, ≥2 segments,
  **underscore INTERDIT dans les segments**, nombre de niveaux NON plafonné à 3.
  Aucun catalogue/whitelist de types : n'importe quel type dotted passe.

### 1.B — Vers la table `imperium_events` (DÉPRÉCIÉE, cf. D2)

- **Aucune émission interne du backend.** Le seul chemin d'écriture est l'API générique :
  `POST /api/imperium/events` — `backend/app/api/v1/routes/imperium_events.py:28`
  (`create_imperium_event_route`) → `backend/app/services/imperium/events.py:30`
  (`create_imperium_event`).
- Format imposé : `^[a-z][a-z0-9_]*$` (`ImperiumEventCreateRequest`,
  `backend/app/schemas/events.py:47`) + CHECK DB `imperium_events_event_type_format_check`
  (`backend/app/models/imperium.py:68`) → **snake_case FORCÉ, le point est INTERDIT**
  (exactement l'inverse de D3).
- Enveloppe réduite : event_type, source_module (∈ mission, vault, path, pulse, vector,
  dashboard, daily_plan, system, manual), occurred_at, payload_json (user_id interdit
  dedans), schema_version (forcé `v1`), idempotency_key (header).
- Types observés UNIQUEMENT dans les tests (jamais dans le code de prod) :
  `mission_started`, `mission_completed`, `vault_income_recorded`
  (`backend/tests/test_imperium_events_foundation.py:264,285,337`,
  `backend/tests/test_imperium_event_readers.py:244`).

### 1.C — Vers la table `auth_events` (journal technique auth, séparé)

Colonnes : user_id, device_id, event_type (Text libre), success, ip_address, user_agent, reason.

| event_type (verbatim) | Fichier | Fonction | Format | Données jointes |
|---|---|---|---|---|
| `login` (success=True et success=False) | `backend/app/services/auth/v1.py:85,105` | `login_user` (via `log_auth_event`) | **mot nu, 1 niveau** | user_id, device_id, ip, user_agent, reason (échec : invalid_credentials, device_revoked, user_missing, token_invalid, token_expired, internal_error) |
| `auth.refresh.rotated` | `backend/app/services/auth/v1.py:146` | `refresh_user_token` | dotted 3 niveaux | user_id, device_id, ip, user_agent |
| `auth.refresh.failed` | `backend/app/services/auth/v1.py:166` | `refresh_user_token` (except) | dotted 3 niveaux | idem + reason |
| `auth.logout` | `backend/app/services/auth/v1.py:194` | `logout_user` | dotted **2 niveaux** | user_id, device_id, ip, user_agent |
| `auth.logout.failed` | `backend/app/services/auth/v1.py:208` | `logout_user` (except) | dotted 3 niveaux | idem + reason |
| `auth.password.reset` | `backend/app/cli/reset_credentials.py:48` | `main` (via `_log_auth_event`) | dotted 3 niveaux | user_id, reason (texte fixe) |
| `auth.master_key.reset` | `backend/app/cli/reset_credentials.py:58` | `main` | dotted 3 niveaux (segment avec underscore) | idem |
| `auth.devices.revoked` | `backend/app/cli/reset_credentials.py:73` | `main` | dotted 3 niveaux | user_id, reason=`revoked_devices=<n>` |
| `user.bootstrap.created` | `backend/app/cli/create_user.py:56` | `main` | dotted 3 niveaux (domaine `user`) | user_id, device_id, reason (texte fixe) |

---

## 2. CONSUMERS (qui lit les events ?)

### 2.A — Table `events` (canonique) : **AUCUN consumer**

- Recherche exhaustive : aucun `select(Event)` hors ingestion, aucun endpoint GET sur
  `/api/v1/events`, aucune requête SQL brute `FROM events` dans `backend/app`, `scripts/`,
  `weekly-review/`, `ops/n8n/`.
- Seule lecture trouvée (technique, pas un consumer métier) :
  `ops/backup/imperium_core_restore_drill.sh:160` — `SELECT 'events=' || count(*) FROM events;`
  (drill de restauration : comptage de lignes uniquement).
- Les tests lisent la table pour vérifier l'append-only et les contraintes
  (`backend/tests/test_events_append_only.py`), pas pour consommer des types.

**Conséquence : les ~19 event_types du §1.A sont TOUS émis mais JAMAIS consommés**
(journal write-only à ce jour). C'est cohérent avec le principe D3 « enregistrement
généreux même sans consumer immédiat », mais c'est un fait à connaître pour le doc 77.

### 2.B — Table `imperium_events` (dépréciée) : des lecteurs SANS émetteur

- `backend/app/services/imperium/event_readers.py:41` — `read_imperium_events` et
  `:57` — `list_events_for_user` : lecteurs génériques (filtres event_type,
  source_module, occurred_from/to ; pas de type câblé en dur). Docstring : « internal
  backend callers only » — mais **aucun autre service backend ne les appelle** ;
  seul appelant réel = `list_imperium_events` (`services/imperium/events.py:78`).
- `GET /api/imperium/events` et `GET /api/imperium/events/{event_id}` —
  `backend/app/api/v1/routes/imperium_events.py:58,81`.
- Déclaré aussi dans le contrat frontend : `backend/app/services/imperium/contracts.py:47-66`
  (capability "events" → read/append/detail sur `/api/imperium/events`).

**Handoff orphelin inverse : ces consumers lisent une table dans laquelle le backend
n'écrit JAMAIS de lui-même** (seul un client externe pourrait la remplir via POST).
Table vide en pratique — confirme le constat D2 (« imperium_events vide »).

### 2.C — Table `auth_events` : aucun lecteur

Aucun code ne lit `auth_events` (ni service, ni route, ni script). Journal de sécurité
write-only (les index `auth_events_event_type_created_idx` etc. existent pour des
lectures futures, `backend/app/models/auth.py:84-86`).

### 2.D — n8n / front / scripts

- `ops/n8n/workflows/` (3 workflows WR : `wr_answers_integrate_qwen_dry_run.json`,
  `wr_interactive_start_mock.json`, `wr_interactive_start_qwen_dry_run.json`) :
  **aucune référence à un event** — ils appellent les endpoints internes weekly-review
  (`/api/internal/weekly-review/...`), qui n'émettent aucun event.
- `weekly-review/*.mjs` : uniquement des events DOM (addEventListener), hors sujet.
- `scripts/imperium_login.py`, `scripts/deploy.sh` : aucun event.

### 2.E — Synthèse orphelins

- **Émis mais jamais consommés** : la totalité du §1.A (`vault.transaction.created`,
  `path.item.*` ×5, `day.plan.*` ×4, `day.finished`, `calendar.event.created`,
  `priority.rules.updated`, `mission.started`, `mission.backlog.created`,
  `mission.completed`, `mission.failed`, `mission.abandoned`) + tout `auth_events` (§1.C).
- **Consumers sans event émis** : tout le chemin `imperium_events`
  (`event_readers.py`, routes GET, capability contrat frontend) — lit une table que
  le backend ne remplit jamais.
- **Aucun consumer par event_type précis n'existe nulle part** : les seuls lecteurs
  (imperium_events) sont génériques à filtres.

---

## 3. REGROUPEMENT PAR DOMAINE PROBABLE (indicatif, rien de tranché)

| Domaine probable (convention D3) | Events actuels | Nom actuel conforme ? |
|---|---|---|
| **finance** (ex-vault) | `vault.transaction.created` | NON — domaine = nom d'app `vault` |
| **worship** (ex-path) | `path.item.created/started/completed/skipped/cancelled` | NON — domaine = nom d'app `path` ; de plus émis sur la table legacy `imperium_path_items` (dépréciée, TRI 1.3) |
| **planning** (exécution) | `day.plan.created/activated/completed/cancelled`, `day.finished`, `mission.started`, `mission.backlog.created`, `mission.completed`, `mission.failed`, `mission.abandoned` | Domaines `day` et `mission` : génériques mais non alignés sur la carte des domaines (planning) ; à trancher au doc 77 |
| **decision** (arbitrage) | `priority.rules.updated` | Domaine `priority` : générique mais absent de la carte (decision) ; à trancher |
| **calendar** | `calendar.event.created` | OUI (domaine générique) ; noter : `delete_calendar_event` (`calendar.py:106`) fait un hard delete SANS émettre d'event |
| **health** (ex-pulse) | AUCUN — `services/pulse/entries.py` écrit `health_entries` sans émettre d'event | — |
| **rides** (ex-vector) | AUCUN event dans le code | — |
| **vehicle** | AUCUN | — |
| **review** (weekly review) | AUCUN — `weekly_review_conversation.py`, `weekly_review_state.py`, routes `internal.py` n'émettent rien | — |
| **socle / technique (auth, user, ai)** | `login`, `auth.refresh.rotated`, `auth.refresh.failed`, `auth.logout`, `auth.logout.failed`, `auth.password.reset`, `auth.master_key.reset`, `auth.devices.revoked`, `user.bootstrap.created` (tous dans `auth_events`, pas dans `events`) ; AI tasks/results (`services/ai/`) n'émettent aucun event | Formats mixtes (voir §4) |

Modules métier qui écrivent des faits SANS émettre d'event (constat brut, pas une
proposition) : pulse/health entries, weekly review (sessions, ready, réponses, rapport
final), AI tasks/résultats/validations, devices (trust/revoke hors CLI), suppression
d'événement calendrier, vault reversals/corrections (seule la création émet).

---

## 4. INCOHÉRENCES DE FORMAT

### 4.1 Noms d'app au lieu de domaines (contraire à D3)
- `vault.transaction.created` → domaine attendu : finance.
- `path.item.*` (5 types) → domaine attendu : worship.
- Enum `SourceApp` (`backend/app/models/enums.py:4`) = noms d'apps (imperium, vector,
  vault, pulse, path, core, external, n8n, ai_router) — portée par la colonne
  `source_app` de CHAQUE ligne de `events`.
- `ImperiumEventSourceModule` (`backend/app/schemas/events.py:9`) = mission, vault, path,
  pulse, vector, dashboard, daily_plan, system, manual — mélange apps/modules.

### 4.2 snake_case vs dotted
- Table `imperium_events` : snake_case OBLIGATOIRE par regex API + CHECK DB — le point
  y est interdit. Structurellement incompatible avec D3 (confirme la dépréciation D2).
- `auth_events.login` : 1 seul mot, ni dotted ni préfixé (les 8 autres types
  d'auth_events sont dotted → incohérence interne au même journal).
- Doublon de convention latent : `mission.started` (events, dotted) vs `mission_started`
  (imperium_events, tests) — même fait, deux écritures.

### 4.3 Profondeur / structure irrégulières
- 2 niveaux au lieu de `domaine.sujet.action` : `day.finished`, `mission.started`,
  `mission.backlog.created` est à 3 mais `mission.completed`/`mission.failed`/
  `mission.abandoned` sont à 2 ; `auth.logout` à 2 vs `auth.logout.failed` à 3.
- `mission.{outcome}` construit dynamiquement par f-string (`missions.py:485`) :
  invisible à un grep sur littéraux ; `mission.abandoned` n'apparaît nulle part en toutes
  lettres dans le code.
- Regex de l'ingestion générique (`^[a-z][a-z0-9]*(\.[a-z][a-z0-9]*)+$`) : interdit
  l'underscore dans un segment et n'impose PAS le plafond de 3 niveaux de D3 (elle
  accepte 2 comme 5 niveaux). NB : `auth.master_key.reset` (underscore dans segment)
  ne passerait pas cette regex — mais il vit dans `auth_events` qui n'a aucune contrainte.

### 4.4 Doublons / ambiguïtés sémantiques (même fait, plusieurs noms ou l'inverse)
- `mission.failed` émis par DEUX chemins avec payloads différents :
  `complete_mission(outcome=failed)` → `{mission_id, outcome, reason}` et
  `fail_mission` → `{mission_id, failure_reason, user_reported_signals, ai_usable_reason}`.
  Même type, deux schémas de payload.
- `mission.started` émis par `start_mission` (payload riche) ET `promote_backlog_mission`
  (payload `{mission_id, source}`) ; la promotion backlog n'a pas de type propre (le hash
  d'idempotence interne utilise pourtant la clé `"mission.backlog.promoted"`,
  `missions.py:395`, qui n'est PAS un event émis).
- `day.finished` (event) vs `day.plan.completed` (event) : deux notions de « fin de
  journée » proches, frontière non documentée dans le code.
- Collision de vocabulaire : `calendar.event.created` où « event » désigne un rendez-vous
  calendrier (table `imperium_calendar_events`, avec sa PROPRE colonne `event_type` ∈
  event/deadline/vacation, `backend/app/schemas/imperium.py:617`) — à ne pas confondre
  avec le journal `events`. Trois colonnes `event_type` coexistent (events,
  imperium_events, imperium_calendar_events) avec trois sémantiques différentes.

### 4.5 Enveloppe D3 sous-utilisée (constat, valable pour tous les émetteurs internes)
- `causation_id` : TOUJOURS None (aucun émetteur ne chaîne les causes).
- `correlation_id` : toujours un UUID aléatoire propre à l'event
  (`corr_<type>_<uuid>`) → ne relie jamais deux events d'une même « histoire ».
  Seule exception partielle : `day.finished` (`corr_day_finish_{review.id}`).
- `occurred_at` : systématiquement `now()` serveur chez les émetteurs internes (le vrai
  moment métier fourni par le client n'est pas utilisé), sauf ingestion générique qui
  respecte l'enveloppe.
- `device_id` : toujours None chez les émetteurs internes.
- `schema_version` : `"1.0"` partout côté `events`, `"v1"` forcé côté `imperium_events`
  (deux conventions de versionnage).
- Colonne `events.duplicate_of_event_id` : définie (`backend/app/models/event.py:48`)
  mais jamais écrite nulle part.

---

## 5. LIMITES DU RECENSEMENT

- Les types en f-string (`mission.{outcome}`) ont été résolus via l'enum source ; s'il
  apparaissait d'autres constructions dynamiques à l'avenir, un grep littéral ne les
  verrait pas.
- Les événements « calendrier » (rendez-vous) et les enums de statut (plan_status,
  mission.status…) ne sont PAS des events de journal et ont été exclus, sauf mention
  pour lever l'ambiguïté.
- Les workflows n8n live (instance n8n) n'ont pas pu être inspectés — seuls les 3 JSON
  versionnés dans `ops/n8n/workflows/` l'ont été (aucun ne touche aux events).
