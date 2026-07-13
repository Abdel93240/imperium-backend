# VAGUE 35 — Vector surge + audits de capteur

**Composition** : ACT-VEC-12, ACT-VEC-13, ACT-VEC-14, ACT-VEC-15, ACT-VEC-16 (lot de 5).
Durée : 1 mois.

```
id: ACT-VEC-12   nom_fr: Capture surge manuelle + pipeline d'observations
domaine: vector   classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: flag app vtc_surge_capture_enabled=true + job 'vtc_surge_ingest' enabled
prerequis_activation: [ACT-VEC-03]
protocole_terrain: capture carte plein-région (zoom imposé) → intensité par cellule,
  cellules VIDES écrites en 0 (les négatifs SONT des données) ; INERTE si GPS > 5 km/h ;
  1 mois
critere_succes: garde-fou vitesse jamais contourné ; calibration couleur→multiplicateur
  progresse
rollback: flag=false + job disabled
source: spec Vector §3.9, §4.6
prompt_codex: « Activer capture+ingestion ; smoke image fixture → observations ;
  consigner. »
observations: —
```

```
id: ACT-VEC-13   nom_fr: Sollicitations de capture (cause déclenchée + battement de cœur)
domaine: vector   classe: notifiant   echelon_audace: 3   statut: NOT_CODED
bascule_exacte: UPDATE parameters : vtc 'surge_heartbeat'=60 actif + job
  'vtc_capture_requests' enabled
prerequis_activation: [ACT-VEC-12, ACT-SYS-07]
protocole_terrain: cause candidate détectée → « si tu es à l'arrêt : une capture »
  (surtout carte vide — négatif = or) ; max 1/h de session ; inerte en roulant ; 1 mois
critere_succes: zéro sollicitation en mouvement ; taux de réponse utile
rollback: job disabled
source: spec Vector §3.9
prompt_codex: « Activer les sollicitations ; smoke cause fixture → notify inerte/actif ;
  consigner. »
observations: —
```

```
id: ACT-VEC-14   nom_fr: Prédicteur cause→surge (+15/+30 min)
domaine: vector   classe: apprenant   echelon_audace: 5   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code='vtc_surge_train';
prerequis_activation: [ACT-VEC-12 (dataset), ACT-VEC-09]
protocole_terrain: prédictions consommées par le CatBoost principal + zones + ciblage des
  sollicitations ; rapport mensuel automatique (importance de la feature en €/h réalisés)
  → item docket informatif ; 1 mois
critere_succes: rapport mensuel produit ; réponse chiffrée à « à quel point la majoration
  joue sur le €/h »
rollback: job disabled (feature neutre dans le scoreur)
source: spec Vector §4.6
prompt_codex: « Activer surge_train ; smoke prédiction fixture ; consigner. »
observations: seuil dynamique piloté par le surge = V2 explicite (hors roadmap)
```

```
id: ACT-VEC-15   nom_fr: Contre-lecture OCR P40 nocturne (audit du capteur)
domaine: vector   classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code='vtc_ocr_audit_nightly';
  (20 % des captures + 100 % des abstentions pour champ manquant)
prerequis_activation: [ACT-VEC-05, GPU P40 (V6)]
protocole_terrain: désaccords champ à champ → items template_fix groupés par
  plateforme/version ; taux d'accord par template dans les métriques ; 1 mois
critere_succes: chaque changement d'UI plateforme détecté par le taux d'accord
rollback: job disabled
source: spec Vector §4.7 (audit décroissant appliqué à un capteur)
prompt_codex: « Activer l'audit OCR ; smoke désaccord fixture → template_fix ;
  consigner. »
observations: la décroissance du % d'audit OCR suit la même règle que les slots (décision
  user, ligne au journal)
```

```
id: ACT-VEC-16   nom_fr: Dérive → docket (calibration, abstentions, accord OCR, exploration, couverture)
domaine: vector   classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code='vtc_drift_weekly';
prerequis_activation: [ACT-VEC-08, ACT-WR-05 (docket — sinon table tampon, §0.3)]
protocole_terrain: chaque métrique hors bande → item docket, JAMAIS d'auto-correction ;
  rupture de biais signé = suspicion de changement d'algo plateforme ; 1 mois
critere_succes: dérives visibles au WR avec provenance complète
rollback: job disabled
source: spec Vector §4.8
prompt_codex: « Activer drift_weekly ; smoke métrique hors bande → item ; consigner. »
observations: —
```
