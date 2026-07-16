# VAGUE 9 — Pulse médical + règles rouges

**Composition** : ACT-PLS-06, ACT-PLS-09. Le médical s'active APRÈS le socle (bandes
éprouvées) et AVANT toute IA Pulse (règle « jamais seul sur le critique » : les rouges
doivent monter la garde d'abord). Durée : 7 j (notifiant).

```
id: ACT-PLS-06    nom_fr: Signaux médicaux (×3 : labs, monitoring dû, tendance poids)
domaine: pulse    classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: UPDATE signal_definitions SET active=true WHERE domain='pulse' AND code IN
  ('labs_out_of_range_active','medical_monitoring_due','weight_trend_28d');  -- table PARTAGÉE
prerequis_activation: [ACT-PLS-08]
protocole_terrain: signaux visibles au board ; orange/red routés vers red_flag_rules
  (actives en même vague) ; 2-3 j
critere_succes: aucun signal médical orange/red absorbé silencieusement
rollback: active=false
source: spec Pulse §4 (is_medical=true)
prompt_codex: « Activer les 3 signaux médicaux ; smoke fixtures out_of_range ; consigner. »
observations: labs vides tant que P5 (V15) n'ingère pas — weight_trend fonctionne dès
  les pesées manuelles
```

```
id: ACT-PLS-09    nom_fr: Règles rouges RF1-RF5 + blocage des procédures d'entraînement
domaine: pulse    classe: notifiant   echelon_audace: 3   statut: NOT_CODED
bascule_exacte: UPDATE pulse_red_flag_rules SET active=true WHERE code IN
  ('RF_lab_out_of_range','RF_rhr_sustained','RF_severe_pain','RF_weight_drop',
  'RF_symptom_keywords');  -- LES 5 EN BLOC (sécurité, jamais partiellement)
prerequis_activation: [ACT-PLS-06, ACT-PLS-05, ACT-SYS-07]
protocole_terrain: red flag actif → visible en tête de board + notification + exige ack +
  bloque P1/P3 (advise_doctor_and_pause_training) ; 7 j
critere_succes: sur fixture réelle : message présenté TEL QUEL, jamais transformé en
  ajustement de plan ; blocage effectif ; non-désactivable par une sortie LLM (test §16.7)
rollback: active=false EN BLOC (à consigner avec la raison — un rollback de sécurité est
  une donnée majeure, R7)
source: spec Pulse §11, §3.5
prompt_codex: « Activer les 5 règles ; smoke : lab hors plage fixture → flag + notify +
  ack ; consigner. »
observations: préalable OBLIGATOIRE aux vagues advisory Pulse (V14+) et à la porte G5
  Daily (V29)
```
