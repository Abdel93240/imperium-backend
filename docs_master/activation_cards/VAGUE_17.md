# VAGUE 17 — Pulse revues + première décroissance

**Composition** : ACT-PLS-24, ACT-PLS-25, ACT-PLS-28. Rythme mensuel/semestriel — la
vague se juge sur un cycle complet.

```
id: ACT-PLS-24    nom_fr: P8 scientific_review en advisory (cloud + web, semestriel)
domaine: pulse    classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE pulse_procedures SET active=true WHERE code='scientific_review';
  + UPDATE job_definitions SET enabled=true WHERE code='pulse_scientific_review';
prerequis_activation: [ACT-SYS-10 ; PREMIER CORPUS VALIDÉ (gate gravé par la spec)]
protocole_terrain: 1 revue : export paramètres+fiches (métadonnées, PAS de données
  personnelles) → diffs proposés → validation diff par diff → versions append-only
critere_succes: chaque diff sourcé ; application uniquement après validation unitaire
rollback: active=false + job disabled
source: spec Pulse §7 P8, §14 (« désactivé par défaut jusqu'au premier corpus validé » —
  seul gate d'activation explicite de la spec, conforme R1)
prompt_codex: « Activer P8 (corpus validé constaté) ; smoke export sans PII ; consigner. »
observations: —
```

```
id: ACT-PLS-25    nom_fr: P9 exploration_pass en advisory (cloud, mensuel)
domaine: pulse    classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE pulse_procedures SET active=true WHERE code='exploration_pass';
prerequis_activation: [ACT-SYS-10, ACT-PLS-27]
protocole_terrain: 1 passe : features AGRÉGÉES (jamais de brut) → nouveaux signaux
  proposés → insertion active=false → activation MANUELLE (chaque nouveau signal = une
  ligne au journal des bascules)
critere_succes: propositions plausibles ; aucun signal auto-activé
rollback: active=false
source: spec Pulse §7 P9
prompt_codex: « Activer P9 ; smoke agrégats fixtures ; consigner. »
observations: les signaux qu'il propose entrent dans la roadmap comme features filles
```

```
id: ACT-PLS-28    nom_fr: Première décroissance d'audit Pulse (audit_sample_pct < 100)
domaine: pulse    classe: apprenant   echelon_audace: 5   statut: NOT_CODED
bascule_exacte: UPDATE ai_slot_transition SET audit_sample_pct=<nouveau> WHERE
  slot_code='<slot>';  -- UNIQUEMENT sur proposition P6 validée par l'utilisateur
prerequis_activation: [ACT-PLS-27 ; agreement ≥ 92 % (cible seedée) sur 3 semaines pour
  le slot concerné]
protocole_terrain: après la baisse : surveiller l'agreement sur l'échantillon restant
  pendant 1 mois — toute chute → remonter à 100 (rollback consigné, R7)
critere_succes: agreement stable après décroissance ; coût cloud d'audit en baisse mesurée
rollback: UPDATE ... SET audit_sample_pct=100 (une ligne)
source: spec Pulse §13 (décroissance = DÉCISION UTILISATEUR, jamais automatique)
prompt_codex: « Appliquer la décroissance validée (slot, ancien %, nouveau %) ; consigner
  slot+valeurs au journal. »
observations: une fiche PAR décroissance ultérieure n'est pas nécessaire : chaque baisse
  = une ligne au journal des bascules avec slot et valeurs
```
