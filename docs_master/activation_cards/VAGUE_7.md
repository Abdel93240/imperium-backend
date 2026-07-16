# VAGUE 7 — Pulse socle 1 (montre, signaux device, board)

**Composition** : ACT-PLS-01, ACT-PLS-02, ACT-PLS-08. Prérequis code : passe Pulse mergée
éteinte (seeds active=false, CF-1→CF-3). Durée : 2-3 j (lecture).

```
id: ACT-PLS-01    nom_fr: Pipeline montre (features device quotidiennes 06:45)
domaine: pulse    classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code='pulse_features_daily';
prerequis_activation: [ACT-SYS-06]
protocole_terrain: pulse_device_features : 1 ligne/jour (resting_hr, hrv, sommeil, steps,
  recovery_score) ; 2-3 j — plausibilité vs montre
critere_succes: 3 lignes consécutives complètes et plausibles ; baselines 28 j se remplissent
rollback: job disabled
source: spec Pulse §10, §14
prompt_codex: « Activer pulse_features_daily ; smoke run manuel ; consigner. »
observations: pulse_device_samples HORS whitelist prompts (testé §16.4) — invariant gravé
```

```
id: ACT-PLS-02    nom_fr: Signaux device — famille sleep (×3) + cardio (×4)
domaine: pulse    classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: UPDATE signal_definitions SET active=true WHERE domain='pulse' AND code IN
  ('sleep_duration_last','sleep_debt_7d','sleep_regularity_7d','resting_hr_delta',
  'hrv_delta_pct','steps_ratio_day','recovery_score');  -- table PARTAGÉE (socle 0038)
prerequis_activation: [ACT-PLS-01]
protocole_terrain: signal_values (table partagée) calculées à chaque refresh ; bandes vs
  ressenti ; 2-3 j
critere_succes: valeurs exactes (recalcul manuel sur 1 jour), staleness correcte
rollback: UPDATE ... SET active=false (valeurs écrites conservées)
source: spec Pulse §4 (dictionnaire des 32 signaux)
prompt_codex: « Activer les 7 signaux device ; smoke calculs fixtures ; consigner. »
observations: resting_hr_delta est is_medical au seuil ≥+8 soutenu — les bandes rouges ne
  ROUTENT vers les red flags qu'à partir de V9
```

```
id: ACT-PLS-08    nom_fr: Board Pulse (GET /api/pulse/board)
domaine: pulse    classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: flag pulse_board_enabled=true (route)
prerequis_activation: [ACT-PLS-02]
protocole_terrain: tableau courant lisible chaque matin ; signaux stale affichés comme
  tels ; 2-3 j
critere_succes: board = dernière valeur non-stale de chaque signal actif, âge correct
rollback: flag=false
source: spec Pulse §3.1 (v_pulse_board_current), §14
prompt_codex: « Activer la route board ; smoke GET ; consigner. »
observations: c'est l'écran de contrôle de TOUTES les vagues Pulse suivantes
```
