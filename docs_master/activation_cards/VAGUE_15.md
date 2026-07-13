# VAGUE 15 — Pulse advisory : nutrition & médical (P2, P5, P6)

**Composition** : ACT-PLS-18, ACT-PLS-21, ACT-PLS-22. Slots mixtes local+cloud → V12
obligatoire. Durée : 7-14 j.

```
id: ACT-PLS-18    nom_fr: P2 diet_change_assessment en advisory (pair_verdict local + synthesis routed)
domaine: pulse    classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE pulse_procedures SET active=true WHERE code='diet_change_assessment';
prerequis_activation: [ACT-PLS-16, ACT-PLS-09, ACT-SYS-10]
protocole_terrain: demande conversationnelle réelle → verdicts pairés (fiche × dossier) →
  synthèse → proposition complète ; 7-14 j
critere_succes: toute paire touchant une règle rouge → verdict bloqué advise_doctor SANS
  négociation LLM ; plan de transition + monitoring plausibles ; acceptation → diet_state
  versionné + solveur relancé
rollback: active=false
source: spec Pulse §7 P2, §13
prompt_codex: « Activer P2 ; smoke paire contre-indiquée → doctor_first ; consigner. »
observations: exige ≥1 fiche corpus VALIDÉE (P10/V16 ou seed carnivore validée à la main —
  une fiche draft n'est JAMAIS utilisée pour un verdict)
```

```
id: ACT-PLS-21    nom_fr: P5 medical_document_ingest en advisory (extract local + second_read cloud)
domaine: pulse    classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE pulse_procedures SET active=true WHERE code='medical_document_ingest';
prerequis_activation: [ACT-PLS-16, ACT-PLS-06, ACT-PLS-09, ACT-SYS-10, ACT-SYS-09]
protocole_terrain: 1 vrai compte rendu (pdftotext) → extraction champ à champ validée par
  l'utilisateur → pulse_lab_results → red flags ; 7-14 j
critere_succes: ref_low/ref_high UNIQUEMENT depuis le document (jamais la connaissance du
  modèle) ; ≥1 out_of_range → second_read cloud systématique ; corrections utilisateur
  capturées comme labels
rollback: active=false (documents et extractions conservés)
source: spec Pulse §7 P5, §11
prompt_codex: « Activer P5 ; smoke PDF fixture → tableau validé → labs ; consigner. »
observations: privacy MAXIMALE : le gate (V12) doit prouver que le contenu du document ne
  part au cloud que minimisé (champs concernés uniquement)
```

```
id: ACT-PLS-22    nom_fr: P6 weekly_reconciliation + solveur repas en advisory
domaine: pulse    classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE pulse_procedures SET active=true WHERE code='weekly_reconciliation';
  + UPDATE job_definitions SET enabled=true WHERE code='pulse_weekly';
prerequis_activation: [ACT-PLS-17, ACT-PLS-03]
protocole_terrain: 2 dimanches : bilan semaine + dette + plan repas solveur (PuLP/CBC,
  <10 s, relaxations loggées dans l'ordre) → batch de propositions ; 14 j
critere_succes: solveur faisable sur contraintes réelles OU infaisable PROPRE (contraintes
  en conflit identifiées, jamais de plan dégradé silencieux) ; write-off de dette = décision
rollback: active=false + job disabled
source: spec Pulse §7 P6, §9 (solveur)
prompt_codex: « Activer P6+job ; smoke solveur OMAD fixture + relaxations ; consigner. »
observations: propose aussi les décroissances d'audit (V17) quand l'agreement tient
```
