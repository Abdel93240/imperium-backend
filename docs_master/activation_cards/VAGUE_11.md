# VAGUE 11 — Sentinelle B (règles d'état) + audit hebdo

**Composition** : ACT-PLS-11, ACT-PLS-12, ACT-PLS-14, ACT-PLS-27. Complète la sentinelle
(attribution possible : triggered_by loggé par règle). Durée : 3-7 j.

```
id: ACT-PLS-11    nom_fr: Sentinelle S1 multi-drapeaux (≥2 flags même jour)
domaine: pulse    classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE pulse_sentinel_rules SET active=true WHERE code='S1_multi_flags';
prerequis_activation: [ACT-PLS-10]
protocole_terrain: 2 drapeaux yellow+ le même jour → dispatch (dry-run) ; cooldown 90 min ;
  3-7 j
critere_succes: déclenchements exacts, pas de rafale (cooldown + dédup vérifiés au réel)
rollback: active=false
source: spec Pulse §5
prompt_codex: « Activer S1 ; smoke fixtures 2 flags ; consigner. »
observations: —
```

```
id: ACT-PLS-12    nom_fr: Sentinelle S2 sévérité (orange+, hors médical)
domaine: pulse    classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE pulse_sentinel_rules SET active=true WHERE code='S2_severe_signal';
prerequis_activation: [ACT-PLS-10]
protocole_terrain: signal orange non-médical → dispatch ; les is_medical vont d'abord aux
  red flags (V9) ; 3-7 j
critere_succes: routage correct médical/non-médical observé sur cas réels
rollback: active=false
source: spec Pulse §5
prompt_codex: « Activer S2 ; smoke ; consigner. »
observations: —
```

```
id: ACT-PLS-14    nom_fr: Sentinelle S6 pré-séance (T−3h)
domaine: pulse    classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE pulse_sentinel_rules SET active=true WHERE code='S6_pre_session';
prerequis_activation: [ACT-PLS-10, ACT-PLS-04]
protocole_terrain: session planifiée → passe à T−3h ; 3-7 j (avec sessions réelles)
critere_succes: une passe par session, à l'heure juste
rollback: active=false
source: spec Pulse §5
prompt_codex: « Activer S6 ; smoke session fixture ; consigner. »
observations: prépare P1 (V14) — le dispatch pré-séance est son déclencheur naturel
```

```
id: ACT-PLS-27    nom_fr: Audit hebdo agreement + rollup métriques Pulse
domaine: pulse    classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code IN
  ('pulse_audit_weekly','pulse_metrics_rollup');
prerequis_activation: [ACT-PLS-15]
protocole_terrain: pulse_metrics_daily rempli chaque nuit ; agreement par slot calculé
  chaque semaine (vide en dry-run — la tuyauterie tourne) ; 7 j
critere_succes: métriques cohérentes avec dispatch_log ; vue v_ai_training_pairs répond
rollback: jobs disabled
source: spec Pulse §3.9, §13, §14
prompt_codex: « Activer les 2 jobs ; smoke rollup manuel ; consigner. »
observations: l'agreement ne devient significatif qu'avec du RÉEL (V13+) — activer tôt
  pour éprouver la tuyauterie
```
