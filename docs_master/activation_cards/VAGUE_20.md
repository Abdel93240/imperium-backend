# VAGUE 20 — WR dry-run bout en bout + plan déterministe

**Composition** : ACT-WR-10, ACT-WR-18. Durée : 3-7 j.

```
id: ACT-WR-10    nom_fr: Chaîne WR dry-run bout en bout (W2/W3 factices → docket → P4 → P5)
domaine: wr       classe: ia_dryrun   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: workers_enabled+=w2,w3 AVEC real_ai_enabled=False (sorties factices
  marquées dry_run=true)
prerequis_activation: [ACT-WR-05]
protocole_terrain: sondes/verdicts/extractions factices traversent toute la chaîne
  (chain_probes → candidates → assemblies → docket ; extractions → confrontations
  simulées) ; AUCUNE écriture E2, AUCUNE écriture mémoire ; 3-7 j
critere_succes: chaîne loggée sans erreur ; zéro appel modèle (spy §14.11) ; volumes de
  lot conformes à la charge attendue (§4)
rollback: workers_enabled-=w2,w3
source: spec WR DoD (dry-run end-to-end), §14.11
prompt_codex: « Activer W2/W3 en dry-run ; smoke chaîne complète ; consigner. »
observations: banc d'essai de V21/V25
```

```
id: ACT-WR-18    nom_fr: Plan initial + v_plan_current (l'objet plan existe)
domaine: wr       classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: INSERT plan_versions (origin='initial', status='active') — construit et
  validé PAR L'UTILISATEUR — + flag wr_plan_enabled=true (GET plan/current)
prerequis_activation: []
protocole_terrain: v_plan_current = version active + deltas (aucun delta encore) ;
  lu quotidiennement ; 3-7 j
critere_succes: le plan affiché = le plan voulu ; la vue survit à un redéploiement
rollback: status='superseded' sur la version (jamais de DELETE)
source: spec WR §3.5, §8 ; Q8 (remplace doc 52 §8, sous réserve) ; PATCH_WR W-9
prompt_codex: « Créer le plan initial validé + activer la route ; smoke GET plan/current ;
  consigner. »
observations: prérequis de la sélection Daily (G1 lit le plan courant, V28) et des deltas
  (V23) ; le contenu du plan V1 est SAISI, pas généré (la génération = V23/V24)
```
