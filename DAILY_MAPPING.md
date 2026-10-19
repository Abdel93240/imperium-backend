# DAILY_MAPPING.md

## Source

Spécification : `specs/DAILY_ORCHESTRATOR_SPEC_V1.md`. Audit de l'étape 0 (§0), en lecture seule,
fait le 2026-10-19 avant la première écriture Daily (carte ACT-DLY-01, vague 27). Seule l'étape 2
du §15 (externalisation des barèmes + verrou de parité) est livrée ; le reste du Daily (portes,
sélection, journal, overrides, Niveaux 2-3, préemption, API `/api/daily/`) n'est PAS codé.

## Réponses aux cinq questions du §0

1. **Filtre de faisabilité avant le tri ?** Non. Aucun filtre de faisabilité : le backlog
   (`app/services/imperium/missions.py`, `_backlog_sort_key`) trie par bucket de priorité
   décroissant, puis `priority_level`, puis date de création. Le moteur de portes G1-G5 est à
   **créer** (§5).
2. **Dépendances = porte topologique ?** Non. Aucune arête persistée : le critère D lit seulement
   l'entrée du score (`dependency` libellé ou booléen, `dependency_points`, `blocked_mission_count`).
   `annex_of_mission_id` lie une annexe à sa mission (complétion groupée), `project_id` +
   `project_position` ordonnent un projet ; ni l'un ni l'autre n'est une porte. Table
   `mission_dependencies` (§3.1) à **créer**, sans backfill possible (aucune arête existante).
3. **Où vivent les barèmes ?** Constantes du code seulement (`decision_framework.py`,
   `_IMPACT_POINTS`, `_MISSION_TYPE_POINTS`, `_DEPENDENCY_POINTS`, `_RECURRENCE_POINTS`,
   `COEFFICIENT_BY_POSITION`, tranches de deadline et seuils de bucket écrits en dur). **Aucun
   mécanisme de réglage existant** : les réglages exposent seulement l'ORDRE des domaines
   (`PUT /api/imperium/decision-framework/priorities`, table `imperium_user_priorities`). Branche
   « exposer les endpoints » du §4.5 → carte ACT-DLY-02 (non codée).
4. **La complétion appelle-t-elle un LLM ?** Non. `complete_mission` (missions.py) enregistre la
   complétion, ses annexes et ses events ; aucun appel de modèle, aucune sélection de la mission
   suivante. Le chemin `mission completed → next mission` n'existe pas encore (§7, §12
   `POST /api/daily/complete/{id}`).
5. **Inventaire.**
   - `imperium_missions` : deadline_at, estimated_minutes (≈ duration_estimate_min),
     planned_start_at / planned_end_at, status, domain, category, mission_type_category,
     priority_level, project_id / project_position, annex_of_mission_id. **Manquent** (§3.2) :
     lieu (lat/lng/label), fenêtres (window_start/end/days), is_fixed_commitment / fixed_at,
     physical_load / cognitive_load → à **étendre**.
   - `imperium_mission_scores` : registre persisté (intrinsic, coefficient, weighted, explanation,
     source `decision_framework_v1`), écrit UNE fois au démarrage d'une mission
     (`_maybe_create_decision_score`). **Aucun refresh** (cron ou changement de barème) : le
     critère A vieillit dans le registre → `daily_scores_refresh` à **créer** (ACT-DLY-03).
   - Plan : `v_plan_current` existe (passe WR, migration 0095) ; plan quotidien versionné dans
     `planning_daily_plan_versions` (0080).
   - Engagements fixes : pas de source dédiée ; sessions VTC (`imperium_vector_sessions`) et
     calendrier à cartographier au moment des portes.
   - `ai_slot_transition` : existe (passe Pulse/WR) ; slots `daily.*` non semés.

## Choix

| Élément spec | Choix | Où |
|---|---|---|
| Barèmes `df.*` (§4.1-4.3) | **créer** sur la table `parameters` partagée | migration 0101, `load_scales` |
| Coefficients ×10/8/5/4 | **étendre** : valeurs → `df.coefficient_by_position`, ORDRE reste `imperium_user_priorities` | `get_domain_coefficient` |
| Seuils de bucket 1-10 | **créer** `df.priority_buckets` (hors liste A-E de la spec, mais constantes du même service) | |
| Maxima par critère | **créer** `df.criterion_max` (bornes des entiers bruts et du breakdown) | |
| Verrou de parité (§4.4) | **créer** : 83 cas dorés capturés AVANT l'externalisation | `tests/fixtures/df_golden_scores.json` |
| Réglage (§4.5) | à **créer** (aucun mécanisme existant) | ACT-DLY-02 |
| Refresh (§4.6) | à **créer** (aucun mécanisme existant) | ACT-DLY-03 |

## Écarts signalés (pas de contradiction bloquante)

- Les libellés d'entrée (alias `quality-of-life`, `vital_immediate` côté type, etc.) sont gardés
  tels quels dans les paramètres pour une parité stricte ; une normalisation des alias serait un
  changement de code, pas de barème.
- Fallback : si un `df.*` manque ou est invalide, le service reprend `CODE_SCALES` et journalise
  (jamais d'erreur côté utilisateur). Les lignes anciennes de `imperium_mission_scores` sans
  `priority_bucket` dans leur explication gardent le calcul de bucket du code.
