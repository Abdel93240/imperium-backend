# VAGUE 10 — Sentinelle A (chaîne dry-run + passes programmées + signalement user)

**Composition** : ACT-PLS-15, ACT-PLS-10, ACT-PLS-13. Première rotation de la mécanique
IA — en dry-run intégral (aucun modèle appelé, R5 premier échelon). Durée : 3-7 j.

```
id: ACT-PLS-15    nom_fr: Chaîne IA Pulse en dry-run (sentinelle → dispatch → procédure factice)
domaine: pulse    classe: ia_dryrun   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code IN
  ('pulse_dispatch_runner','pulse_procedure_runner');  -- avec real_ai_enabled=False
prerequis_activation: [ACT-PLS-08]
protocole_terrain: dispatch_log se remplit (model_used='dry_run', sorties factices
  marquées dry_run=true) ; RIEN n'est proposé à l'utilisateur ; 3-7 j
critere_succes: chaîne complète loggée sans erreur ; zéro appel modèle (spy §16.11) ;
  zéro proposition visible
rollback: jobs disabled
source: spec Pulse §0 (contraintes flags), §16.11, DoD dry-run end-to-end
prompt_codex: « Activer les 2 runners en dry-run ; smoke chaîne complète ; consigner. »
observations: c'est le banc d'essai des vagues V13+ — les volumes/cooldowns s'observent ici
```

```
id: ACT-PLS-10    nom_fr: Sentinelle S4/S5 (passes 07:30/18:30) + garde S7 (plafond)
domaine: pulse    classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE pulse_sentinel_rules SET active=true WHERE code IN
  ('S4_scheduled_am','S5_scheduled_pm','S7_meta_guard');
prerequis_activation: [ACT-PLS-15]
protocole_terrain: 2 passes/jour ; board all-green → outcome='none_needed',
  model_used='skipped' SANS appel LLM ; snapshots créés ; 3-7 j
critere_succes: skip gratuit vérifié ; plafond 6 dispatch/jour jamais dépassé ; dédup 90 min
rollback: active=false
source: spec Pulse §5
prompt_codex: « Activer S4/S5/S7 ; smoke passe manuelle all-green → skip ; consigner. »
observations: S7 s'active AVEC la première règle et ne se désactive jamais seul (garde-fou)
```

```
id: ACT-PLS-13    nom_fr: Sentinelle S3 (signalement utilisateur → réveil immédiat)
domaine: pulse    classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE pulse_sentinel_rules SET active=true WHERE code='S3_user_report';
prerequis_activation: [ACT-PLS-05, ACT-PLS-15]
protocole_terrain: report ≥ yellow → dispatch immédiat (dry-run) ; 3-7 j
critere_succes: chaque report sévère déclenche exactement un dispatch (cooldown 0, dédup S7)
rollback: active=false
source: spec Pulse §5
prompt_codex: « Activer S3 ; smoke report fixture → dispatch ; consigner. »
observations: —
```
