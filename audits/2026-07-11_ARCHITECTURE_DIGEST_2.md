# ARCHITECTURE DIGEST 2 - Imperium

Date: 2026-07-11. Scope: `/opt/imperium-backend`.

Mode de lecture: digest d'arbitrage, pas rapport de correction. Chaque risque est formule
comme fait + reference + condition de materialisation. Aucune donnee personnelle de sante,
finance ou lieu n'est reproduite; seuls des agregats, chemins de code et references sont
utilises.

Limites verifiees:
- DB runtime non lue: `alembic current` echoue sur l'authentification Postgres locale
  `postgres@127.0.0.1:5432`; les SELECT 7 jours sont donc non verifies.
- Doc canonique `docs_master/78_*.md` absent; le catalogue toolbox existant est
  `gap_analysis_v1/toolbox/TOOLBOX_CATALOG_DRAFT.md`.
- Aucun `MAPPING.md` de passe trouve; seul `docs_master/69_FRONTEND_API_MAPPING_V1.md`
  existe comme mapping frontend.
- Ce livrable est documentaire; aucun test n'a ete ajoute car aucun code n'est modifie.

## 1. ETAT DES PASSES

| Passe | Etat constate | Tests | Jobs / mapping |
|---|---|---:|---|
| Socle backend | Auth, events, idempotence, AI tasks, HMAC n8n existent (`backend/app/models/*.py`, `backend/app/core/internal_webhooks.py`). Runner generique absent (`rg job_definitions|job_runs` = 0). | suite globale rouge | `job_definitions`, `job_runs`, `MAPPING.md` absents |
| Imperium missions | Une mission active forcee par API et index SQL (`models/imperium.py:143-148`, `missions.py:114-116`). | 187 passed / 1 skipped sur groupe missions/priorites/decision | mapping absent |
| Vault | Ledger `imperium_vault_transactions` avec cents, wallet, reversals (`models/vault.py:12-75`); legacy `vault_transactions` existe encore en migration. | 87 passed / 1 skipped | mapping absent |
| Pulse | V1 minimal `imperium_pulse_entries` seulement (`models/imperium.py:304-343`). | 38 passed / 1 skipped | mapping absent |
| Path | Habits/check-ins et contraintes schema presentes; raison de missed portee par migration `0034`. | 65 passed / 1 skipped | mapping absent |
| WR / AI | `ai_tasks`, `ai_results`, validations, sessions WR et decisions memoire existent (`models/ai.py:22-216`). | 202 passed / 1 skipped sur groupe AI/WR/Qwen | mapping absent |
| Daily / home / calendar | Read-model et fondations existent, mais docs de contrat driftent. | 53 passed / 2 failed / 1 skipped | mapping absent |
| Events | Event store canonique et `imperium_events` legacy coexistent (`models/event.py:14-55`, `models/imperium.py:64-120`). | 7 passed / 3 skipped | mapping absent |
| Frontend/docs | Metadata frontend codee, mais tests de docs cassent sur doc 05/doc 37/doc 53/doc 63/doc 34. | 256 passed / 33 failed | `69_FRONTEND_API_MAPPING_V1.md` seul mapping |
| Vector | Spec non negociee cote Bolt dans doc 08; backend dedie minimal seulement (`services/vector/scoring.py`), aucune route `/api/vector` constatee dans les audits precedents. | pas de sous-suite runtime dediee lancee | mapping absent |

Suite globale lancee: `907 passed / 35 failed / 9 skipped in 29.99s`.

## 2. CARTE DU SYSTEME

- Cerveau cible: backend + n8n + PostgreSQL + pgvector + routeur IA; les apps sont des
  interfaces (doc 08 `AUTHORITY-001..006`, lignes 86-135).
- Backend runtime: FastAPI/SQLAlchemy avec `DATABASE_URL`, HMAC inbound, client n8n signe
  (`internal_webhooks.py:17-53`, `n8n_client.py:37-119`).
- Canon PostgreSQL structurel: missions, events, vault, pulse, path, WR et AI sont dans
  les modeles/migrations; DB appliquee non confirmee faute d'acces.
- Memoire: table `ai_memories` vector(1024) (`models/ai.py:15-20`, `168-216`) mais service
  annonce `storage_enabled=False` et `embeddings_enabled=False` (`memories.py:54-64`).
- Events: table canonique `events` avec idempotence, correlation, causation, depth,
  privacy_level (`models/event.py:14-49`); table legacy `imperium_events` avec snake_case
  strict (`models/imperium.py:64-80`).
- Qwen backend: desactive et dry-run par defaut; modele par defaut `qwen2.5:7b-instruct`
  (`config.py:49-53`), ecart a traiter par rapport a la strategie V1 fournie dans AGENTS.
- n8n: client signe existe, dry-run par defaut (`config.py:42-47`, `n8n_client.py:63-101`).
- Toolbox: catalogue draft annonce 55 outils: 25 F1, 17 F2, 13 F3, 10 dormants
  (`TOOLBOX_CATALOG_DRAFT.md:13-17`).

## 3. FLUX MAJEURS REELS

1. Event -> orchestration -> WR/memoire:
   `POST /api/events` et emissions internes stockent dans `events`; aucun `LISTEN`,
   `NOTIFY` ou `pg_notify` trouve; `job_runs`/docket absents. WR et decisions memoire
   existent mais ne sont pas branches sur un bus runtime verifie.
2. Plan -> Daily -> completion -> events:
   Daily read-model existe, missions peuvent demarrer/terminer et emettent events
   (`missions.py:139-146`, `482-488`, `549-555`). `v_plan_current` absent au grep.
3. Pulse:
   tracking journalier minimal code; boucle signaux/sentinelle/interprete/procedure non
   trouvee (`imperium_pulse_entries`, pas de runner Pulse).
4. Vector:
   les regles anti-automation Bolt sont documentees (doc 08 lignes 281-327); chemin
   sonnerie/halo/log/training/bundle non prouve dans le backend inspecte.
5. Apprentissage transverse:
   validations AI et decisions de candidats memoire existent (`models/ai.py:131-166`,
   `weekly_review_conversation.py`); `v_ai_training_pairs` absent au grep.

## 4. INVARIANTS GRAVES ET ENFORCEMENT

| Invariant | Source | Enforcement constate | Verdict |
|---|---|---|---|
| Une seule mission active | doc 08 `IMP-001` lignes 37-43 | index partiel `imperium_missions_one_active_per_user_idx`; garde API `ActiveMissionExistsError` | tenu schema/code; DB live non verifiee |
| Apps interfaces, backend verite | doc 08 lignes 89-135 | backend porte les ecritures; aucune preuve Android locale contraire | tenu cote backend |
| n8n ne possede pas la DB | doc 08 lignes 105-119 | HMAC inbound, client n8n signe; pas de workflow DB direct audite | tenu cote backend, n8n runtime non verifie |
| Events append-only | doc 08 lignes 157-163 | triggers migrations events/auth/imperium_events; tests events verts | tenu dans migrations/tests |
| Idempotency sur mutations | doc 08 lignes 141-147 | `Idempotency-Key` exige par ingestion/events, missions, webhooks internes | tenu sur chemins inspectes |
| Event dotted canonique | doc 08 lignes 149-155 | `events` accepte dotted; `imperium_events` impose snake_case | partiel / legacy divergent |
| Chaînage event | modele `events` lignes 20-44 | colonnes existent; emissions internes generent surtout correlation locale, pas causation globale | ecrit mais non exploite |
| Privacy gate avant IA externe | doc 08 lignes 229-243 | champs `privacy_level`; pas de gate externe exhaustif trouve | partiel; risque au premier provider reel |
| Pas d'ecriture IA sans validation | doc 08 lignes 269-275 | validations AI et WR memory decisions existent | tenu sur WR/AI inspecte, pas prouve global |
| Memoire pgvector non verite canonique | doc 08 lignes 129-135 | `ai_memories` existe, ecritures canoniques bloquees avant embeddings | tenu par blocage |
| Vector sans auto-click/tap/fake GPS | doc 08 lignes 281-311 | aucun code Android auditable; aucune violation constatee | documente, non enforce dans app absente |
| Vault realite financiere | doc 08 lignes 330-355 | ledger append-only/reversal en schema; pas de decision autonome detectee | partiel tenu |
| Pulse simple | mission AGENTS + `imperium_pulse_entries` | surface codee minimale | tenu V1 minimal |

## 5. INCOHERENCES RESIDUELLES

- AD2-1 (MAJEUR, S): suite globale rouge `35 failed`; les echecs visibles concernent
  surtout docs/frontend (`05_DATABASE_SCHEMA.md`, doc 37 renomme, doc 53, doc 63, doc 34).
  Condition: toute CI stricte refusera le deploiement meme si les sous-suites metier sont
  vertes.
- AD2-2 (MAJEUR, M): `events` canonique et `imperium_events` legacy gardent des contrats
  incompatibles (`events` dotted + privacy/correlation; `imperium_events` snake_case +
  source_module legacy). Condition: premier consumer qui lit le mauvais journal.
- AD2-3 (MAJEUR, S): `mission.failed` a deux chemins d'emission avec payloads differents:
  completion dynamique `mission.{outcome}` (`missions.py:482-488`) et fail dedie
  (`missions.py:549-555`). Condition: consumer unique par `event_type`.
- AD2-4 (MAJEUR, M): `job_definitions`, `job_runs`, `LISTEN/NOTIFY`, docket et
  `v_plan_current` absents alors que les specs les supposent comme chaines de decision.
  Condition: codage d'une passe qui depend du runner ou du plan courant.
- AD2-5 (MAJEUR, M): memoire vectorielle definie mais commit canonique bloque:
  `storage_enabled=False`, `embeddings_enabled=False` (`memories.py:54-64`). Condition:
  WR ou chatbot attend une ecriture memoire reelle.
- AD2-6 (MAJEUR, M): Qwen V1 officiel attendu par AGENTS est local router/scorer, mais la
  config backend reste `qwen_enabled=False`, `qwen_dry_run=True`, modele 7B. Condition:
  activation IA reelle sans arbitrage modele/config.
- AD2-7 (MINEUR, S): doc 78 absent; le catalogue disponible reste un draft sous
  `gap_analysis_v1/toolbox/`. Condition: arbitrage qui cite "catalogue 78" comme source
  canonique.
- AD2-8 (MINEUR, S): aucun `MAPPING.md` de passe; impossible de mesurer des deviations
  par passe autrement que par audits narratifs. Condition: session de review qui demande
  la taille des mappings.
- AD2-9 (MINEUR, M): `vault_transactions` legacy et `imperium_vault_transactions` canonique
  coexistent dans l'inventaire (`INVENTAIRE_tables.md`), avec schemas monetaires differents.
  Condition: lecture finance depuis l'ancien ledger.
- AD2-10 (MAJEUR, M): privacy gate central non trouve alors que les sorties n8n/IA existent
  structurellement. Condition: `n8n_dry_run=false` ou provider externe actif sur donnees
  high/very_high sans gate.

## 6. SURFACES DE RISQUE

- R1 - SPOF runtime: Postgres local/runtime non accessible par l'audit; `alembic current`
  echoue avant lecture. Ref: sortie commande Alembic. Condition: une migration ou un
  SELECT de prod diverge des migrations locales sans detection.
- R2 - CI: la suite globale est rouge `35 failed`. Ref: `pytest -q`. Condition: pipeline
  de deploiement execute la suite complete.
- R3 - Bus write-only: events stockes mais aucun `LISTEN/NOTIFY`/runner/docket trouve.
  Ref: grep `LISTEN|NOTIFY|pg_notify|job_runs`; `models/event.py`. Condition: une feature
  suppose que l'event declenche automatiquement une action.
- R4 - Couplage inter-domaines non contractualise: services Imperium importent directement
  des modeles transverses (`Event`, `ImperiumMission`, `ImperiumVaultTransaction`,
  `AIMemory`) au lieu de vues/contrats dedies. Ref: `missions.py:9-13`, `vault.py`,
  `models/*.py`. Condition: migration d'un domaine casse un lecteur d'un autre domaine.
- R5 - Double event contract: `mission.failed` payload A et B. Ref: `missions.py:482-488`,
  `549-555`. Condition: premier consumer qui valide un schema strict par event_type.
- R6 - Sortie sensible n8n: `trigger_n8n_webhook` peut envoyer JSON signe si dry-run off.
  Ref: `n8n_client.py:63-119`, doc 08 `PRIV-001/002`. Condition: donnees high/very_high
  dans payload sans privacy gate central.
- R7 - Sortie sensible Qwen/backend: Qwen est dry-run/off par defaut; risque latent si
  active sans minimisation. Ref: `config.py:49-53`, doc 08 lignes 229-243. Condition:
  `QWEN_ENABLED=true` avec payload brut.
- R8 - Memoire: table pgvector existe mais embeddings/ecritures canoniques bloquees.
  Ref: `models/ai.py:168-216`, `memories.py:54-64`. Condition: une passe attend des
  souvenirs persistants.
- R9 - Vault legacy: deux ledgers coexistent. Ref: `INVENTAIRE_tables.md`, migrations
  `0007` et `0024`. Condition: reporting ou sadaqa lit l'ancien ledger.
- R10 - Vector compliance: absence d'app auditable ne prouve pas enforcement Android.
  Ref: doc 08 lignes 281-327. Condition: app Android future ajoute accessibility/tap/GPS
  sans tests de non-automation.
- R11 - Tests docs ancres: failures sur litteral documentaire. Ref: pytest failures
  `test_repo_invariants.py`, `test_imperium_screen_architecture_docs.py`. Condition:
  renommer/restructurer un doc masque une regression code ou bloque une passe.
- R12 - Dette assumee D5: commit memoire WR bloque jusqu'au service embedding. Ref:
  `WR_MEMORY_COMMIT_DISABLED_REASON` (`memories.py:29-31`). Condition: arbitrage decide
  d'activer WR memory avant embeddings.
- R13 - Dette assumee n8n dry-run: workflows signees mais dry-run par defaut. Ref:
  `config.py:42-47`, `n8n_client.py:72-101`. Condition: bascule prod sans inventaire
  runtime des workflows.
- R14 - Dette sourcee toolbox: `TOOLBOX_CATALOG_DRAFT.md` signale inventaire tables
  perime et outils manquants. Ref: lignes 13-17, 34-40, 288-366. Condition: une passe
  traite le draft comme code existe.

## 7. QUESTIONS UTILISATEUR

1. Contexte: `MAPPING.md` de passe absent. Question: creer retroactivement des `MAPPING.md`
   par passe maintenant: OUI ou NON ?
2. Contexte: doc 78 canonique absent, draft toolbox present. Question: promouvoir le draft
   toolbox en doc canonique 78: OUI ou NON ?
3. Contexte: CI globale rouge mais sous-suites metier vertes. Question: priorite immediate
   = reparer les tests docs/frontend avant toute nouvelle passe: OUI ou NON ?
4. Contexte: aucun runner/NOTIFY/job_runs trouve. Question: le runner backend remplace n8n
   dans V1: OUI ou NON ?
5. Contexte: `mission.failed` a deux payloads. Question: unifier en un seul schema avant
   premier consumer event: OUI ou NON ?
6. Contexte: `imperium_events` legacy contredit le contrat dotted. Question: supprimer ou
   migrer `imperium_events` avant nouveau consumer: OUI ou NON ?
7. Contexte: Qwen backend est off/dry-run et 7B. Question: garder Qwen dry-run tant que le
   service embeddings n'est pas pret: OUI ou NON ?
8. Contexte: `ai_memories` existe mais commit bloque. Question: maintenir le blocage D5
   jusqu'a embeddings reels: OUI ou NON ?
9. Contexte: deux ledgers finance coexistent. Question: interdire toute nouvelle lecture de
   `vault_transactions` legacy: OUI ou NON ?
10. Contexte: Vector n'a pas d'app auditable. Question: Vector V1 reste manuel-first
    screenshots/advice avant halo/sonnerie: OUI ou NON ?
11. Contexte: privacy gate central absent. Question: bloquer tout provider externe reel
    high/very_high tant que le gate n'existe pas: OUI ou NON ?
12. Contexte: `v_plan_current` absent. Question: creer une vue DB `v_plan_current` plutot
    qu'un read-model service: OUI ou NON ?

## 8. METRIQUES DE SANTE

- Date mesure: 2026-07-11.
- Suite globale: 907 passed.
- Suite globale: 35 failed.
- Suite globale: 9 skipped.
- Suite globale: duree 29.99s.
- Vault: 87 passed.
- Vault: 0 failed.
- Vault: 1 skipped.
- Missions/priorites/decision: 187 passed.
- Missions/priorites/decision: 0 failed.
- Missions/priorites/decision: 1 skipped.
- Path: 65 passed.
- Path: 0 failed.
- Path: 1 skipped.
- Pulse: 38 passed.
- Pulse: 0 failed.
- Pulse: 1 skipped.
- Events: 7 passed.
- Events: 0 failed.
- Events: 3 skipped.
- AI/WR/Qwen: 202 passed.
- AI/WR/Qwen: 0 failed.
- AI/WR/Qwen: 1 skipped.
- Daily/home/calendar/core: 53 passed.
- Daily/home/calendar/core: 2 failed.
- Daily/home/calendar/core: 1 skipped.
- Frontend/docs/gap/repo-invariants: 256 passed.
- Frontend/docs/gap/repo-invariants: 33 failed.
- Frontend/docs/gap/repo-invariants: 0 skipped.
- Alembic history head: `20260710_0037`.
- Alembic current: non verifie, auth Postgres refusee.
- Migrations create_table brutes: 31 occurrences; table finale documentee par
  `INVENTAIRE_tables.md`: 29 tables codees.
- Catalogue 78 tables: non verifiable; doc 78 absent.
- Toolbox draft: 55 outils, dont 25 F1, 17 F2, 13 F3, 10 dormants.
- Events 7j emis: non verifie, SELECT impossible.
- Events 7j consommes: non verifie, SELECT impossible.
- Events statiques audites: 19 event_types emis par 8 services, 0 consumer selon
  `audits/2026-07-02_2308_audit.md`.
- Notifications envoyees 7j: non verifie, pas de table/service reel au-dela du stub.
- job_runs 7j: sans objet, table absente.
- MAPPING: 0 fichier de passe.
- Deviation MAPPING par passe: non mesurable.

## 9. ANNEXE - INDEX DE FORAGE

- Routage/modeles: `docs_master/30_AI_ROUTING_AND_SCORING_POLICY.md`,
  `docs_master/31_AI_TASKS_AND_RESULTS_CONTRACT.md`, `backend/app/core/config.py`,
  `backend/app/services/ai/providers/qwen.py`, `gap_analysis_v1/toolbox/TOOLBOX_CATALOG_DRAFT.md`.
- Memoire/pgvector: `docs_master/09_PGVECTOR_MEMORY_POLICY.md`,
  `docs_master/75_MEMOIRE_VECTORIELLE_UNIFIEE.md`, migration `20260705_0032`,
  `backend/app/models/ai.py`, `backend/app/services/ai/memories.py`.
- Events/bus: `docs_master/77_EVENTS_CATALOG.md`,
  `gap_analysis_v1/INVENTAIRE_events.md`, `audits/2026-07-02_2308_audit.md`,
  `backend/app/models/event.py`, `backend/app/services/events/ingestion.py`,
  `backend/app/services/imperium/missions.py`.
- Runner/n8n: `docs_master/45_N8N_RESPONSIBILITY_MATRIX.md`,
  `gap_analysis_v1/toolbox/EXECUTION_ORDER_PROPOSAL.md`,
  `gap_analysis_v1/toolbox/TOOLBOX_FINDINGS.md`, `backend/app/services/integrations/n8n_client.py`,
  `ops/n8n/workflows/`.
- Imperium missions/Daily: `docs_master/43_IMPERIUM_LOGIC_DETAIL.md`,
  `docs_master/52_AI_DECISION_FRAMEWORK.md`, `backend/app/models/imperium.py`,
  `backend/app/services/imperium/missions.py`, `backend/app/services/imperium/daily_plan.py`.
- Vault/finance: `docs_master/11_FINANCIAL_PRESSURE_FORMULA.md`,
  `docs_master/42_VAULT_LOGIC_DETAIL.md`, `gap_analysis_v1/GAP_vault.md`,
  migrations `20260426_0007`, `20260525_0024..0026`, `20260706_0033`, `20260710_0037`,
  `backend/app/models/vault.py`.
- Pulse: `docs_master/40_PULSE_LOGIC_DETAIL.md`,
  `docs_master/34_PULSE_MEDICAL_FEED_AI.md`, `gap_analysis_v1/GAP_pulse.md`,
  `gap_analysis_v1/toolbox/patches/PATCH_PULSE.md`, `backend/app/models/imperium.py`.
- Path: `docs_master/41_PATH_LOGIC_DETAIL.md`, `gap_analysis_v1/GAP_path.md`,
  migrations `20260525_0027`, `20260707_0034`, `backend/app/services/path/habits.py`,
  `backend/app/services/imperium/path_items.py`.
- Vector: `docs_master/33_VECTOR_LOGIC_DETAIL.md`,
  `docs_master/57_VECTOR_RIDE_SCORING_ML.md`,
  `gap_analysis_v1/DECISIONS_vector_discussion.md`,
  `gap_analysis_v1/toolbox/patches/PATCH_VECTOR.md`, `backend/app/services/vector/scoring.py`,
  doc 08 lignes 281-327.
- Frontend/docs failures: `backend/tests/test_repo_invariants.py`,
  `backend/tests/test_imperium_screen_architecture_docs.py`,
  `docs_master/04_MVP_BACKEND_CONTRACTS.md`, `docs_master/05_DATABASE_SCHEMA.md`,
  `docs_master/53_SUBMISSIONS_OVERLAY_TASKS.md`, `docs_master/63_FRONTEND_ARCHITECTURE_V1.md`.
- Tables/catalogue: `gap_analysis_v1/INVENTAIRE_tables.md`,
  `gap_analysis_v1/toolbox/TOOLBOX_CATALOG_DRAFT.md`, `backend/alembic/versions/`,
  `backend/app/models/`.
