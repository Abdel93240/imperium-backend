# VAGUE 26 — WR autonomie graduée

**Composition** : ACT-WR-22, ACT-WR-24. Rythme mensuel.

```
id: ACT-WR-22    nom_fr: Classes d'auto-acceptation (première classe activée)
domaine: wr       classe: apprenant   echelon_audace: 5   statut: NOT_CODED
bascule_exacte: INSERT dans la table des classes d'auto-acceptation (item_type +
  conditions : agreement ≥ cible 3 semaines, confidence ≥ seuil) — PAR L'UTILISATEUR
prerequis_activation: [ACT-WR-06 (walker rodé), ACT-WR-23 (agreements mesurés) ; accord
  tenu 3 semaines sur le type visé]
protocole_terrain: items du type auto-acceptés + 10 % re-présentés en spot-check ; 1 mois
critere_succes: spot-checks sans surprise (zéro auto-acceptation qu'on aurait refusée)
rollback: DELETE de la classe (une ligne) — les items repassent en validation manuelle
source: spec WR §9 P4 (table seedée VIDE + mécanique — conforme R1)
prompt_codex: « Insérer la classe validée ; smoke spot-check ; consigner type+conditions. »
observations: chaque classe supplémentaire = une ligne au journal des bascules
```

```
id: ACT-WR-24    nom_fr: Première décroissance d'audit WR (audit_sample_pct < 100)
domaine: wr       classe: apprenant   echelon_audace: 5   statut: NOT_CODED
bascule_exacte: UPDATE ai_slot_transition SET audit_sample_pct=<nouveau> WHERE
  slot_code='wr.<slot>';  -- proposée AU WR quand agreement ≥ cible 3 semaines, décision user
prerequis_activation: [ACT-WR-23 ; agreement tenu 3 semaines sur le slot]
protocole_terrain: agreement sur l'échantillon restant surveillé 1 mois post-baisse
critere_succes: agreement stable ; coût d'audit en baisse
rollback: audit_sample_pct=100
source: spec WR §3.7 (jamais automatique)
prompt_codex: « Appliquer la décroissance validée ; consigner slot+valeurs. »
observations: même règle que ACT-PLS-28 — chaque baisse ultérieure = ligne au journal
```
