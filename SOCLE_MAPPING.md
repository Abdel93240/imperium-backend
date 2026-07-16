# SOCLE_MAPPING — Passe 0 (Socle Toolbox V1)

Date : 2026-07-15. Exécuteur : Claude Code (Fable 5), Tower.
Spec source : `/tmp/incoming_docs/TOOLBOX_SOCLE_SPEC_V1.md`.
Lectures faites : `gap_analysis_v1/toolbox/` intégral (CATALOG_DRAFT, FINDINGS,
N8N_INVENTORY, EXECUTION_ORDER, patches/ ×4), docs 04, 05, 10, 11, 30 (§3, §7.8, §9),
38 (§5, §9, §11), 41 (§6, §20), 42 (§9, §16), 52 (§8), 73, 75, 77, F10.

---

## 1. Vérifications d'infrastructure (étape 0.2/0.3)

| point | constat | verdict |
|---|---|---|
| Postgres sur Tower | cluster 16/main actif, `127.0.0.1:5432`, base `imperium_core` restaurée | ✅ |
| `alembic current` (local) | `20260710_0037 (head)` — 0001→0037 toutes appliquées | ✅ (= head 0037+, pas d'écart avec l'audit du 2026-07-10) |
| Backend sur Tower | `backend/.env` : `DATABASE_URL=postgresql+psycopg://…@127.0.0.1:5432/imperium_core` (local). Processus non lancé en service au moment de l'audit — non bloquant, le code cible la vraie base locale | ✅ |
| **Condition STOP (base non rapatriée)** | **NON DÉCLENCHÉE** — la base vit sur Tower | ✅ GO |
| `vtc-companion-app` sous `/opt/apps/` | ABSENT (`/opt/apps/` vide) | consigné, non bloquant (Q1 reste ouverte pour la passe Vector) |
| Écart avec l'audit 2026-07-10 | l'audit disait « Postgres réel inaccessible depuis Tower » — c'était le VPS ; depuis, rapatriement fait (commits `6c25960`, `84894db`, `8ccf6ba`). Le schéma reconstruit par l'audit depuis les migrations correspond à la base réelle (vérifié : 30 tables publiques, aucune table du socle présente) | ✅ |

Correction d'état vs audit C-1 : `dashboard.py` et `weekly_report.py` lisent déjà
`imperium_vault_transactions` (canonique) pour la finance — la partie « vault legacy »
de C-1 est **déjà couverte**. Restent legacy : `ImperiumPathItem` (dashboard,
weekly_report, daily_plans:279) et `ImperiumPriorityRule` (weekly_report:103).

## 2. Tables du périmètre — créer / étendre / couvert

Base réelle vérifiée (30 tables publiques). AUCUNE table du socle n'existe → tout « créer ».

| table / vue | § spec | verdict | notes |
|---|---|---|---|
| `job_definitions`, `job_runs`, `job_cursors` | §2 | **créer** | généralisation `wr_worker_*` (jamais codées) |
| `notifications`, `notification_channels` | §3 | **créer** | stub `services/notifications/__init__.py` = 1 ligne, rien à étendre |
| `parameters` + vue `v_parameters_current` | §4 | **créer** | pattern append-only spec Pulse §3.4 verbatim |
| `signal_definitions`, `signal_values` | §4 | **créer** | schéma spec Pulse §3.1 + colonne `domain` en tête ; 32 signaux Pulse seedés PAR la passe Pulse (pas ici) |
| `ai_slot_transition`, `ai_audit_samples`, vue `v_ai_training_pairs` | §4 | **créer** | schéma spec WR §3.7 verbatim ; vides au socle |
| `travel_cache` | §7 | **créer** | clé (h3 origine, h3 dest, tranche horaire), TTL 2 h |
| `path_registered_mosques` | §8 | **créer** | dépendance FK de `path_mawaqit_cache` (schéma doc 41 §20) ; la mosquée de référence est pointée par le paramètre `path.reference_mosque_id` |
| `path_mawaqit_cache` | §8 | **créer** | nom doc 41 §20, cache 30 j |
| `path_calculated_prayer_times` | §8 | **créer** | doc 41 §20, alimentée par le job |
| `ai_role_models` | §10 | **créer** | doc 73 PART B, identifier-not-call |
| `events` (trigger NOTIFY) | §6 | **étendre** | table existante (0001/0011/0036) ; ajout trigger `pg_notify('events_new', event_id)` |
| `imperium_vault_transactions`, habits/check-ins, `imperium_user_priorities` | §9 | **couvert** | existent (0019/0024-26/0033/0037) — deviennent les seules sources des lecteurs |

## 3. Décisions encodées (rappel — ne pas rouvrir)

- Q2 → `privacy_tier='very_high'` : interdiction codée d'appel provider externe, `local_fallback` exclusif, test-verrou spy réseau.
- Q3 → Telegram d'abord (`telegram_prod`, bot ≠ `/opt/orchestrator/telegram_bot.py`), routage red→tous, normal/info→primaire, dedup 24 h.
- Q6 → prières = engagements fixes G4 (contrat `prayer_windows(date)`, PATCH_DAILY complété).
- Q4 → pression 0-100 partout (patch doc 42).
- Q8 → plan 4 semaines = `plan_versions` (patch doc 52 §8).
- Q13 → catalogue promu `docs_master/78_TOOLBOX_CATALOG.md` (78 ai_task absorbé, note T7).
- DV-11 → canonique = ce que le code émet : `path.*` reste (`worship.*` marqué non-retenu au doc 77) ; les AUTRES renommages dotted du doc 77 « À faire côté code » sont appliqués (§5 ci-dessous).
- CF-4/CF-6 (doc 76) → `job_definitions.enabled=false` par défaut : déjà conforme dans la spec §2, encodé dans la migration.
- Topologie (révisée 2026-07-11) → TOUT sur Tower ; F10 décrit encore la topologie VPS : la spec prime (F10 §5-quater seul est patché dans cette passe, périmètre assistant course).

## 4. Portage n8n (état vérifié)

- 3 exports JSON sur disque (`ops/n8n/workflows/`), conformes à N8N_INVENTORY §A :
  - #1 `wr_interactive_start_qwen_dry_run` : webhook → POST interne `/api/internal/ai/qwen/smoke` → callback `/api/internal/ai/tasks/{id}/result` → attach `/api/internal/weekly-review/{id}/attach-ai-result`. Chaîne de 3 POST internes signés → devient une fonction backend.
  - #2 `wr_answers_integrate_qwen_dry_run` : callback → attach (2 POST) → idem.
  - #3 `wr_interactive_start_mock` : converti en fixture pytest, JSON supprimé du repo.
- Unique appelant sortant : `weekly_review_conversation.py:302` (`_trigger_weekly_review_n8n_if_enabled`) → remplacé par le flux direct.
- `n8n_client.py` : déprécié (docstring + DeprecationWarning), `N8N_*` marqués deprecated dans config.
- Coupure du conteneur VPS : action utilisateur, hors passe (après export de l'instance).

## 5. Renommages dotted appliqués (compat lecture 30 j)

| ancien (émis aujourd'hui) | nouveau (canonique doc 77) |
|---|---|
| `vault.transaction.created` | `finance.transaction.created` |
| `mission.backlog.created` | `planning.mission.created` |
| `mission.started` | `planning.mission.started` |
| `mission.completed` | `planning.mission.completed` |
| `mission.failed`, `mission.abandoned` (E1) | `planning.mission.aborted` (+ `reason`) |
| `day.plan.created` | `planning.daily_plan.generated` |
| `day.plan.activated` / `completed` / `cancelled` | `planning.daily_plan.replanned` (+ `reason`, `trigger`) |
| `day.finished` | `planning.day.finished` |
| `priority.rules.updated` | `decision.priorities.updated` |
| `path.item.*` | **INCHANGÉ** (DV-11 : `worship.*` non-retenu, le code fait foi) |

Compat en lecture 30 j (jusqu'au 2026-08-14) : les lecteurs (`/api/imperium/events`,
heartbeat, filtres `event_types`) traduisent ancien→nouveau via la table de
correspondance `app/services/events/nomenclature.py` (les deux formes matchent).

## 6. Divers consignés

- Flags : `real_ai_enabled`/`embeddings_enabled` n'existaient PAS dans `Settings` (valeurs en dur `False` dans le code) → ajoutés à `Settings` avec défaut `False`, plus `runner_enabled` et `notifications_enabled`.
- DV-6 : 5 fichiers porteurs de `qwen2.5:7b-instruct` vérifiés (config.py:51, providers/qwen.py:165, weekly_review_conversation.py:2105/2122, tests/test_qwen_adapter.py:58) — remplacés par la résolution du rôle `local_executor` via `ai_role_models` (seed `qwen3-32b`).
- Émetteurs d'events à mettre à jour (enveloppe E2) : missions, daily_plans, day_finish, path_items, priorities, calendar, vault/transactions (7 services + la route d'ingestion externe qui accepte l'enveloppe du client).
- Dépendances ajoutées : `apscheduler==3.11.3`, `h3==4.5.0`, `adhan==0.1.1` (fallback prières ; si l'API de la lib est insuffisante, calcul solaire local — voir code).
- Serving embeddings : unités systemd livrées sous `ops/systemd/`, smoke J+2 sous `ops/gpu/EMBEDDINGS_SMOKE_CHECKLIST.md` — exécution différée à l'arrivée des GPU, ne bloque pas le merge.
- Backup nightly (`system.backup_nightly`, 04:00, restic) : job seedé désactivé + script `ops/backup/restic_nightly.sh` ; l'existant pg_dump (`imperium_core_backup.sh`) reste en place, le drill mensuel reste un acte utilisateur.
