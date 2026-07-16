# VAGUE 8 — Pulse socle 2 (intake, training, subjectifs, contexte/méta)

**Composition** : ACT-PLS-03, ACT-PLS-04, ACT-PLS-05, ACT-PLS-07. Attribution R4 : chaque
famille vit dans son domaine de board (colonnes distinctes). Durée : 2-3 j.

```
id: ACT-PLS-03    nom_fr: Signaux intake — hydration (×2) + nutrition (×5)
domaine: pulse    classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: UPDATE signal_definitions SET active=true WHERE domain='pulse' AND code IN
  ('hydration_ratio_now','hydration_day_total','protein_ratio_day','kcal_ratio_day',
  'eating_window_state','last_meal_hours','mealplan_adherence_7d');  -- table PARTAGÉE
prerequis_activation: [ACT-PLS-08]
protocole_terrain: saisies eau/repas réelles → ratios au prorata de l'heure ; 2-3 j
critere_succes: ratios exacts vs saisies ; courbe horaire P:hydration_curve respectée
rollback: active=false
source: spec Pulse §4
prompt_codex: « Activer les 7 signaux intake ; smoke fixtures ; consigner. »
observations: mealplan_adherence_7d reste neutre tant que P6/solveur inactifs (pas de plan)
```

```
id: ACT-PLS-04    nom_fr: Signaux training (×7)
domaine: pulse    classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: UPDATE signal_definitions SET active=true WHERE domain='pulse' AND code IN
  ('session_planned_today','hours_to_session','volume_debt_total','training_adherence_7d',
  'last_high_load_hours','muscle_recovery_gate','adaptation_freq_by_slot','rpe_trend_7d');
prerequis_activation: [ACT-PLS-08]
protocole_terrain: sessions planifiées/réalisées réelles → signaux ; 2-3 j
critere_succes: gates de récupération et dette calculés juste sur données réelles
rollback: active=false
source: spec Pulse §4
prompt_codex: « Activer les 8 signaux training ; smoke ; consigner. »
observations: nécessite un programme actif (pulse_programs) — sinon informational vides,
  acceptable en observation
```

```
id: ACT-PLS-05    nom_fr: Signaux subjectifs (×4) + POST /api/pulse/reports
domaine: pulse    classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: flag pulse_reports_enabled=true + UPDATE ... active=true WHERE code IN
  ('pain_active','fatigue_reported','mood_reported','stress_reported');
prerequis_activation: [ACT-PLS-08]
protocole_terrain: signalements réels (douleur/fatigue/humeur/stress) → signaux ; 3-7 j
critere_succes: chaque report visible au board dans la minute ; sévérités correctes
rollback: flag=false + active=false
source: spec Pulse §4, §14 (POST reports)
prompt_codex: « Activer reports + 4 signaux ; smoke POST → board ; consigner. »
observations: pain severe → mécanique critique doc 30 §5.6 : PRÉSERVÉE mais la règle rouge
  RF_severe_pain n'est active qu'en V9 — fenêtre assumée, courte
```

```
id: ACT-PLS-07    nom_fr: Signaux contexte (×2) + méta (×1)
domaine: pulse    classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: UPDATE ... active=true WHERE code IN ('workload_today_h',
  'intense_session_yesterday','refusal_streak');
prerequis_activation: [ACT-PLS-08]
protocole_terrain: lectures inter-domaines (planning, VTC) en LECTURE SEULE ; 2-3 j
critere_succes: frontière tenue : Pulse n'écrit jamais dans le planning (invariant §4)
rollback: active=false
source: spec Pulse §4 (source cross_domain_read)
prompt_codex: « Activer les 3 signaux ; smoke lecture ; consigner. »
observations: refusal_streak reste à 0 tant qu'aucune proposition n'existe (V14+)
```
