# VAGUE 14 — Pulse advisory : entraînement (P1, P4)

**Composition** : ACT-PLS-17, ACT-PLS-20. Premières PROPOSITIONS visibles (échelon 4).
Condition R5 : advisory sur accord mesuré → l'agreement de l'interprète (V13) doit tenir
la cible avant d'ouvrir. Durée : 7-14 j.

```
id: ACT-PLS-17    nom_fr: P1 adapt_training_session en advisory (slot p1.choose_move)
domaine: pulse    classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE pulse_procedures SET active=true WHERE code='adapt_training_session';
prerequis_activation: [ACT-PLS-16 (accord ≥ cible), ACT-PLS-09, ACT-PLS-14]
protocole_terrain: pulse_proposals kind=session_adaptation : menu de coups légaux généré
  par le code, coup choisi/paramétré par le 32B, proposition refusable ; 7-14 j — chaque
  refus expliqué = label
critere_succes: ≥1 adaptation utile ACCEPTÉE ; ZÉRO effet appliqué avant validation
  (no-override testé) ; aucun coup violant un recovery gate ou un red flag ; fallback_move
  automatique observé au moins une fois correctement
rollback: UPDATE pulse_procedures SET active=false WHERE code='adapt_training_session';
source: spec Pulse §7 P1, §8 (coups légaux), §13
prompt_codex: « Activer P1 ; smoke : dispatch fixture → menu → proposition → refus avec
  explication ; consigner. »
observations: les 8 coups légaux s'activent AVEC P1 (observables uniquement à travers lui,
  R2) ; chaque coup a son active bool si un coup se comporte mal (rollback fin possible,
  à consigner par coup)
```

```
id: ACT-PLS-20    nom_fr: P4 injury_or_pain en advisory (slot p4.interpret)
domaine: pulse    classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE pulse_procedures SET active=true WHERE code='injury_or_pain';
prerequis_activation: [ACT-PLS-17]  (P4 déclenche P1 en sous-procédure)
protocole_terrain: douleur déclarée → restrictions proposées + catalogue re-filtré +
  adaptations P1 sur 7 j ; severity=severe → mécanique critique doc 30 §5.6 INCHANGÉE ;
  7-14 j
critere_succes: restrictions correctes (tags du catalogue) ; red_flag_suspected route vers
  advise_doctor ; récap validé par l'utilisateur
rollback: active=false
source: spec Pulse §7 P4
prompt_codex: « Activer P4 ; smoke douleur fixture → restrictions + sous-P1 ; consigner. »
observations: —
```
