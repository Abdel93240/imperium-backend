# PATCH_DAILY — Amendements d'étape 0 pour DAILY_ORCHESTRATOR_SPEC_V1

Source : audit toolbox 2026-07-10 (`gap_analysis_v1/toolbox/`). Amendements d'étape 0 uniquement.

## D-0. Lecture obligatoire à l'étape 0
Ajouter aux lectures §0 : `TOOLBOX_CATALOG_DRAFT.md` + `TOOLBOX_FINDINGS.md`.

## D-1. Réponses d'audit §0 déjà établies (à vérifier rapidement, pas à re-découvrir)
L'audit toolbox a répondu aux questions §0.1-0.4 (sources : `decision_framework.py`,
audit_resync) :
1. §0.1 : AUCUN filtre de faisabilité en amont — tri pur par weighted_score.
2. §0.2 : la dépendance n'existe QUE comme points du critère D (`_DEPENDENCY_POINTS`,
   decision_framework.py:82) ; aucune porte topologique, aucune table d'arêtes →
   `mission_dependencies` est à CRÉER.
3. §0.3 : les barèmes A-E et coefficients sont des CONSTANTES CODE
   (decision_framework.py:29-94 : `COEFFICIENT_BY_POSITION`, `_IMPACT_POINTS`,
   `_MISSION_TYPE_POINTS`, `_DEPENDENCY_POINTS`, `_RECURRENCE_POINTS`). Il n'existe PAS de
   mécanisme de réglage exposé (l'affirmation utilisateur « modifiables dans les réglages » ne
   correspond pas au code actuel) → le §4.5 s'applique dans sa branche « sinon, exposer les
   endpoints de réglage ».
4. §0.4 : le chemin de complétion n'appelle aucun LLM aujourd'hui.
DAILY_MAPPING.md confirme ces points en une passe rapide au lieu d'une redécouverte.

## D-2. `toolbox.travel` : consommer l'interface, ne pas coder un estimateur jetable (G4/§7)
FINDINGS DBL-1 (le doublon franc). §5 « Trajet » : implémenter la logique Google Maps ×
plancher 1,3 + cache (origine arrondie, destination arrondie, tranche horaire) + fallback
25 km/h DERRIÈRE une interface `toolbox.travel.estimate(origin, dest, at) → {duration_min,
source, confidence}` posée dans un module partagé (ex. `services/travel/`), PAS dans le moteur
de sélection. La passe Vector remplacera la source (matrice H3 + multiplicateurs + fantôme) SANS
changer la signature. Les arrondis de cellule (cache) utilisent les utilitaires geo/H3 partagés
(FINDINGS T6). Le plancher 1,3 reste codé en dur dans l'interface (règle gravée).

## D-3. Paramètres `df.*` : table partagée
§4 : la table de paramètres partagée existe depuis la passe Pulse (PATCH_PULSE P-1). Les `df.*`
y vont. Le verrou de parité §4.4 est inchangé (bloquant).

## D-4. Docket et plan : tables de la passe WR
§8.2 (`plan_delta_proposal`), §10.2 (`ordering_override_pattern`) → items dans le docket créé
par la passe WR (PATCH_WR W-6). §0.5 : `v_plan_current` = vue de la passe WR. La contrainte
d'ordre WR-avant-Daily est CONFIRMÉE par l'audit (voir EXECUTION_ORDER_PROPOSAL).

## D-5. Préemption : types d'events réels (§9)
FINDINGS DV-11 : le code émet `path.ghusl.required` (doc 41 §5), le doc 77 vise
`worship.ghusl.*` (futur). Seeder la classe de préemption `event_types` avec le TYPE RÉEL émis
au moment de la passe (vérifier dans `events` / doc 77 à jour), et prévoir le renommage doc 77
comme alias, pas comme deuxième entrée.

## D-6. Notifications et runner
- §9 préemption « notification immédiate » → `toolbox.notifications` (FINDINGS T1) ; si non
  livré : table `notifications` en attente.
- §12 crons (`daily_scores_refresh` 06:30, `day_start`, `override_aggregation`,
  `gmaps_cache_gc`) → jobs `toolbox.runner`, pas de workflows n8n.

## D-7. Porte G5 (Pulse) via une vue contractuelle
FINDINGS C-4 : G5 lit l'état red-flag Pulse à travers une vue dédiée (ex.
`v_pulse_active_blocks` exposant {block_kind, min_physical_load}) créée par la passe Pulse —
pas de lecture directe des tables médicales depuis le moteur de sélection. Pulse absent →
porte passante (stub loggé), inchangé.

## D-8. Engagements fixes : calendrier + prières (Q6)
§5 G4 : les engagements fixes incluent les événements `imperium_calendar_events` NON
soft-supprimés avec `blocks_time` (migration 0035 : colonnes soft-delete à exclure).
QUESTION Q6 (prières comme engagements mobiles fournis par toolbox.prayer) : si la réponse est
oui, G4 consomme une source « fenêtres de prière » EN LECTURE — ne rien construire de religieux
dans Daily (frontière doc 41 §7-bis : les awareness zones appartiennent au planning, la vérité
des heures appartient à Path).
