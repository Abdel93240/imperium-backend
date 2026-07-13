# VAGUE 30 — Daily Niveau 2 (arbitrage IA) + préemption + décroissance

**Composition** : ACT-DLY-11, ACT-DLY-12, ACT-DLY-13, ACT-DLY-09, ACT-DLY-14 (lot de 5).
Durée : 7-14 j.

```
id: ACT-DLY-11   nom_fr: Slots Niveau 2 en dry-run (conditions C1-C3 loggées)
domaine: daily    classe: ia_dryrun   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: flag daily_n2_enabled=true AVEC real_ai_enabled dry pour ces slots
  (daily_arbitrations écrites, sorties factices, AUCUN effet)
prerequis_activation: [ACT-DLY-04]
protocole_terrain: faisable vide / conflit d'obligatoires / POST disruption → arbitration
  loggée dry ; 3-7 j — compter les déclenchements réels (attendu ~5 % des complétions)
critere_succes: conditions purement déterministes (tests, pas jugements) ; volumes sains
rollback: flag=false
source: spec Daily §8.1, §14.6
prompt_codex: « Activer N2 dry ; smoke C1/C2/C3 fixtures ; consigner. »
observations: —
```

```
id: ACT-DLY-12   nom_fr: daily.disruption_classify réel (32B local)
domaine: daily    classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE ai_slot_transition SET tier='local_default' WHERE
  slot_code='daily.disruption_classify';
prerequis_activation: [ACT-DLY-11, ACT-SYS-11, ACT-SYS-10 (audit 100 %)]
protocole_terrain: perturbation en langage → classe (local_deviation / plan_delta_needed /
  shock) + effets par le CODE ; shock vérifié contre la taxonomie SEEDÉE (pas de match →
  rétrogradé) ; 7-14 j
critere_succes: un LLM ne déclenche JAMAIS seul une régénération frontier ; classes jugées
  correctes à la relecture
rollback: tier retour dry
source: spec Daily §8.2
prompt_codex: « Basculer disruption_classify ; smoke texte fixture → classe+effet ;
  consigner. »
observations: —
```

```
id: ACT-DLY-13   nom_fr: daily.conflict_arbitrate réel (sacrifice = toujours une proposition)
domaine: daily    classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE ai_slot_transition SET tier='local_default' WHERE
  slot_code='daily.conflict_arbitrate';
prerequis_activation: [ACT-DLY-12]
protocole_terrain: conflit d'obligatoires réel → ordre proposé + sacrifice motivé avec
  mitigation → boutons accepter/refuser/choisir ; 7-14 j
critere_succes: sacrifier une deadline JAMAIS silencieux ; refus → ordre manuel capturé
  en override
rollback: tier retour dry
source: spec Daily §8.3
prompt_codex: « Basculer conflict_arbitrate ; smoke conflit fixture → proposition ;
  consigner. »
observations: —
```

```
id: ACT-DLY-09   nom_fr: Préemption (classes red_flag / shock / event_types)
domaine: daily    classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: flag daily_preemption_enabled=true + seed des event_types RÉELS (DV-11 :
  le type ghusl émis au moment de la bascule, vérifié au doc 77 à jour)
prerequis_activation: [ACT-DLY-04, ACT-PLS-09 (red), ACT-WR-20 (shock), ACT-SYS-07]
protocole_terrain: la mission active n'est JAMAIS touchée par les recompositions ;
  préemption = notification + proposition, décision utilisateur ; interruption acceptée →
  statut interrupted + raison auto ; 7-14 j
critere_succes: zéro interruption non consentie ; classes seedées correctes
rollback: flag=false (plus aucune interruption proposée)
source: spec Daily §9 ; PATCH_DAILY D-5
prompt_codex: « Activer la préemption ; smoke red flag fixture → proposition ; consigner. »
observations: —
```

```
id: ACT-DLY-14   nom_fr: Première décroissance d'audit Daily
domaine: daily    classe: apprenant   echelon_audace: 5   statut: NOT_CODED
bascule_exacte: UPDATE ai_slot_transition SET audit_sample_pct=<nouveau> WHERE
  slot_code IN ('daily.disruption_classify','daily.conflict_arbitrate');
prerequis_activation: [agreement ≥ cible 3 semaines sur le slot ; décision user]
protocole_terrain: agreement surveillé 1 mois post-baisse
critere_succes: stable ; rollback sinon
rollback: audit_sample_pct=100
source: spec Daily §8.3 (slots dans ai_slot_transition, audit 100 % au départ)
prompt_codex: « Appliquer la décroissance validée ; consigner slot+valeurs. »
observations: même mécanique que ACT-PLS-28/ACT-WR-24
```
