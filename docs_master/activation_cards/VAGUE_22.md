# VAGUE 22 — WR rituel cloud (hypothèses + audit de sortie)

**Composition** : ACT-WR-12, ACT-WR-15. Le rituel complet P1→P5 devient réel. Fenêtre :
2 WR consécutifs.

```
id: ACT-WR-12    nom_fr: P1 passe d'hypothèses (wr.hypothesis_pass, cloud_forced)
domaine: wr       classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE ai_slot_transition SET tier='cloud_forced' WHERE
  slot_code='wr.hypothesis_pass';  (réel via cloud_tiers_enabled, V12)
prerequis_activation: [ACT-WR-09, ACT-SYS-10, ACT-SYS-09]
protocole_terrain: 2 WR : digest ≤40k → hypothèses systémiques + agenda 5-8 questions +
  forage (max 6 requêtes, scopes autorisés seuls, drill_log complet) ; store éphémère P2
  peuplé digest+hypothèses+forage
critere_succes: hypothèses jugées pertinentes ; plafonds de forage tenus ; whitelist
  assembleur intacte (jamais de brut) ; coût dans l'ordre 2-5 $/WR (vs ~25-30 batch)
rollback: tier retour dry (le WR retombe sur conversation locale sans hypothèses)
source: spec WR §9 P1, §10 ; budget §10
prompt_codex: « Basculer hypothesis_pass en réel ; smoke digest fixture → hypothèses ;
  consigner coût réel. »
observations: trajectoire de sortie : 70B local sur digest (jamais sur brut) — bascule
  future distincte
```

```
id: ACT-WR-15    nom_fr: P5 écriture + audit de sortie (wr.exit_audit, Opus — gravé)
domaine: wr       classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE ai_slot_transition SET tier='cloud_forced' WHERE
  slot_code='wr.exit_audit';  + flag wr_phase5_write_enabled=true
prerequis_activation: [ACT-WR-12, ACT-WR-11]
protocole_terrain: 2 WR : validations appliquées par le CODE (chain_assemblies validées →
  écriture E2 causation/correlation/depth ; décisions → review_memory_decisions) ;
  exit_audit produit learning_facts → confrontation 6.2 (dry tant que V25 non faite —
  les facts attendent en file, à consigner)
critere_succes: SEUL ce chemin écrit le graphe causal découvert ; rapport en
  review_final_reports ; event review.completed ferme la session
rollback: flag=false (les validations restent en attente d'application — rejouables)
source: spec WR §9 P5, §10 (Opus gravé par décision utilisateur)
prompt_codex: « Basculer exit_audit + activer l'écriture Phase 5 ; smoke chaîne validée
  fixture → E2 ; consigner. »
observations: c'est la PREMIÈRE écriture du chaînage découvert dans le journal — la date
  de cette bascule est une frontière analytique majeure
```
