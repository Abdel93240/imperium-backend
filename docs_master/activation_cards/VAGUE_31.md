# VAGUE 31 — Vector Tower (fondations données)

**Composition** : ACT-VEC-01, ACT-VEC-02, ACT-VEC-03, ACT-VEC-04. **BLOQUANTS AMONT** :
Q1 (repo vtc-companion-app introuvable) et V-2 (historique ~800 courses/mois non localisé
— STOP §0.2 probablement réel, PATCH_VECTOR V-2). Durée : 3-7 j.

```
id: ACT-VEC-01   nom_fr: Matrice de base H3 + caches statiques (événements, travaux)
domaine: vector   classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code IN
  ('vtc_base_matrix_build','vtc_static_cache_weekly');
prerequis_activation: [Q1 + V-2 RÉSOLUS (historique localisé)]
protocole_terrain: vtc_base_matrix peuplée (cellule × tranche × type de jour, source
  history|osm_fallback marquée) ; static_cache.json généré ; 3-7 j
critere_succes: vitesses plausibles sur trajets connus ; cellules jamais visitées en
  fallback OSM marqué
rollback: jobs disabled
source: spec Vector §3.5, §4.1 ; PATCH_VECTOR V-2/V-3 (source de l'interface travel)
prompt_codex: « Activer les builders de base ; smoke matrice sur historique fixture ;
  consigner. »
observations: renforce toolbox.travel (ACT-SYS-08) sans changer la signature — la bascule
  de SOURCE Daily→matrice est une activation ultérieure à consigner
```

```
id: ACT-VEC-02   nom_fr: Builders de caches contextuels (trafic 5 min, transports, aéroports, seuils, zones)
domaine: vector   classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code IN
  ('vtc_traffic_5min','vtc_transports_5min','vtc_airports_60min',
  'vtc_period_thresholds_nightly','vtc_zone_scores_15min');
prerequis_activation: [ACT-VEC-01]
protocole_terrain: context_cache.json régénéré aux fréquences (5 min EN SESSION seulement,
  dormant sinon) ; TTL par section ; 3-7 j
critere_succes: multiplicateurs = écart à l'attendu DU CRÉNEAU (jamais à la vitesse libre
  — double comptage interdit, testé) ; seuils = quantile des OFFRES par sceau
rollback: jobs disabled
source: spec Vector §4.1, §4.3 ; V-8 (jobs runner, advisory locks)
prompt_codex: « Activer les builders ; smoke cache généré+TTL ; consigner. »
observations: transports = feature de DEMANDE, pas de temps de trajet (deux tuyaux nommés)
```

```
id: ACT-VEC-03   nom_fr: Sync tablette↔Tower (montée logs, descente caches/bundles)
domaine: vector   classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: flag vtc_sync_enabled=true (endpoints de sync + WorkManager app)
prerequis_activation: [ACT-VEC-02 ; app installée (Q1)]
protocole_terrain: batchs idempotents par uuid ; reprise sur coupure ; descente caches
  5 min en session ; 3-7 j
critere_succes: rejeu de batch sans doublon ; hash de bundle vérifié
rollback: flag=false
source: spec Vector §2.3, §3.11
prompt_codex: « Activer la sync ; smoke batch rejoué ; consigner. »
observations: —
```

```
id: ACT-VEC-04   nom_fr: Test NotificationListener (écoute passive instrumentée, 2 semaines)
domaine: vector   classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: flag app vtc_notif_listener_test=true (écoute PASSIVE : horodatage,
  plateforme, texte dispo o/n — rien d'autre)
prerequis_activation: [ACT-VEC-03]
protocole_terrain: 2 semaines gravées ; issue consignée EN PARAMÈTRE : double déclencheur
  si texte exploitable, avance d'horodatage seule, ou suppression du service
critere_succes: décision documentée par les données (pas d'intuition)
rollback: flag=false (service supprimé si issue négative)
source: spec Vector §3.1 (secondaire)
prompt_codex: « Activer le test passif ; consigner l'issue à J+14. »
observations: —
```
