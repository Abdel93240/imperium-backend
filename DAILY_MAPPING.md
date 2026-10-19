# DAILY_MAPPING.md

## Source

Spécification : `specs/DAILY_ORCHESTRATOR_SPEC_V1.md`. Audit de l'étape 0 (§0), en lecture seule,
fait le 2026-10-19 avant la première écriture Daily (carte ACT-DLY-01, vague 27). Livré : étape 2
du §15 (externalisation des barèmes + verrou de parité), le réglage versionné (§4.5), le refresh du
registre (§4.6) et l'étape 3 (portes, trajet, ensemble obligatoire, sélection, journal, pull-forward ;
vague 28), les overrides et leur agrégation au docket (§10.1-10.2, vague 29), la porte G5 sur la vue
contractuelle Pulse (vague 29), les événements calendrier bloquants comme engagements fixes de G4
(D-8, hors prières). Pas encore codés : prières en engagements fixes, Niveaux 2-3 (§8), préemption (§9),
`POST disruption`, `POST arbitrations/{id}/decision`.

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
| Réglage (§4.5) | **créé** : `GET/PUT /api/daily/settings/scoring` derrière `daily.settings_enabled` ; event `decision.scoring.updated` (nom canonique de `df.parameter_updated`) | migration 0102, ACT-DLY-02 |
| Dépendances (§3.1) | **créé** `mission_dependencies` (+ user_id), sans backfill ; cycles refusés à l'écriture | migration 0104, `constraints.py` |
| Attributs de faisabilité (§3.2) | **étendu** `imperium_missions` ; durée = `estimated_minutes` existant (pas de `duration_estimate_min`) | migration 0104, `PUT missions/{id}/constraints` |
| Journal (§3.3) | **créé** `daily_selection_log` + user_id, scope, outcome, condition, pulled_forward | migration 0104 |
| Sélection (§5-7) | **créé** `app/services/daily/selection.py` derrière `daily.selection_enabled` ; events `planning.daily.*` | ACT-DLY-04, ACT-DLY-06 |
| Trajet (§5) | **réutilisé** `toolbox.travel` (plancher 1,3 dur, cache 2 h) + bascule `toolbox.travel_enabled` (semée false) | ACT-SYS-08 |
| Overrides (§3.4, §10.1) | **créé** `daily_overrides` (+ user_id, une par sélection) ; event `planning.daily.override_recorded` | migration 0105, ACT-DLY-07 |
| Agrégation (§10.2) | **créé** job `daily.override_aggregation` → item `ordering_override_pattern` (worker `w5` ajouté) | ACT-DLY-08 |
| G5 Pulse (§5) | **créé** : lecture de `v_pulse_active_blocks` seulement (pas des tables médicales) derrière `daily.g5_enabled` ; `daily.pulse_block_load` 4 | migration 0106, ACT-DLY-05 |
| Engagements calendrier (§5 G4, D-8) | **étendu** : `imperium_calendar_events` à venir, `blocks_time`, non supprimés, derrière `daily.calendar_commitments_enabled` ; `daily_selection_log.next_fixed_kind` | migration 0107 |
| Refresh (§4.6) | **créé** : `refresh_scores` (cron 6 h Paris, `planning.day.started`, après réglage) ; entrées B-E gardées dans `explanation.inputs` ; CHECK de coefficients figés remplacés par `> 0` | migration 0103, ACT-DLY-03 |

## Écarts signalés (pas de contradiction bloquante)

- Les libellés d'entrée (alias `quality-of-life`, `vital_immediate` côté type, etc.) sont gardés
  tels quels dans les paramètres pour une parité stricte ; une normalisation des alias serait un
  changement de code, pas de barème.
- Fallback : si un `df.*` manque ou est invalide, le service reprend `CODE_SCALES` et journalise
  (jamais d'erreur côté utilisateur). Les lignes anciennes de `imperium_mission_scores` sans
  `priority_bucket` dans leur explication gardent le calcul de bucket du code.
- Les CHECK de la migration 0019 figeaient les coefficients ×10/8/5/4 en base, ce qui contredit un
  coefficient réglable (§4.1) : remplacés par `coefficient > 0` (migration 0103).
- Les missions ne stockaient pas leurs entrées B-E (seulement les points) : elles sont gardées
  depuis 0103 dans `explanation.inputs` ; les scores plus anciens ne suivent un changement de
  barème B-E qu'à leur prochain recalcul complet (jamais pour l'instant).
- Périmètre du jour (G1) : le plan WR n'a que des semaines. « Missions du jour » = `backlog` prévues
  (`planned_start_at`) ou échues (`deadline_at`) au plus tard aujourd'hui (Paris), plus les éléments
  `mission:<id>` du plan courant dont `params.day` est aujourd'hui (si `wr.plan_enabled`). Semaine
  (pull-forward) : dates jusqu'à dimanche + éléments de la semaine courante du plan. Les missions sans
  date ni place dans le plan ne sont jamais proposées. Annexes et engagements fixes sortent par G1.
- Temps restant : jusqu'au prochain engagement fixe (`is_fixed_commitment`, et événement calendrier
  bloquant si `daily.calendar_commitments_enabled`), sinon jusqu'à minuit (Paris) ; la spec borne la
  journée par démarrage → clôture, sans heure de fin connue. Un événement calendrier déjà commencé
  n'est pas une borne (l'appel montre que l'utilisateur est disponible).
- Niveau 2 non codé : C1 (`empty_feasible`) et C2 (`mandatory_conflict`) sont journalisés
  `arbitration_pending` (level 2) avec l'event `planning.daily.arbitration_required`, sans table
  `daily_arbitrations` ni slot. G5 (Pulse) : `g5` vaut `stub` (flag
  éteint), `clear` ou `blocked` dans chaque entrée du journal ; une mission bloquée porte `g5_blocks`
  (identifiants des red flags). Charge physique inconnue : la porte passe. Une mission obligatoire
  bloquée par G5 donne `mandatory_conflict` (arbitrage, Niveau 2 non codé).
- Position courante : lieu de la mission qui vient d'être close (`POST complete/{id}`) ou position
  fournie (`POST next`) ; sans position ou sans lieu de mission, trajet 0 (`travel_source=none`).
- Le critère D ne lit pas encore les arêtes de `mission_dependencies` (points inchangés).
- Override : la mission choisie doit être en attente (`backlog`) ; l'override ne la démarre pas.
  Tranches horaires du motif : matin 5-12 h, après-midi 12-18 h, soir 18-23 h, nuit (Paris).
  `suggested_target` : coefficient de domaine si les domaines diffèrent ; critère C si le domaine est le
  même et que la catégorie choisie est toujours la même (et jamais celle proposée) ; sinon discussion.
- W3 ne voit pas encore les overrides : `planning.daily.override_recorded` n'est pas dans
  `wr.episode_criteria` (réglage à faire par l'utilisateur, aucune écriture de paramètre ici).
