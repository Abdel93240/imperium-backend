# VAGUE 34 — Vector apprentissage (entraînement, zones, « Où je vais »)

**Composition** : ACT-VEC-09, ACT-VEC-10, ACT-VEC-11. Durée : 1 mois (cycles nocturnes réels).

```
id: ACT-VEC-09   nom_fr: Entraînement nocturne + verrou de backtest + déploiement de bundles
domaine: vector   classe: apprenant   echelon_audace: 5   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code='vtc_train_nightly';
prerequis_activation: [ACT-VEC-08 (données advisory réelles), ACT-VEC-06]
protocole_terrain: chaque nuit : candidat entraîné (fenêtre 120 j, poids exploration ×3) ;
  backtest 14 j EXCLUS de l'entraînement ; candidat ≤ prod sur la justesse → PAS de
  déploiement (log + compteur) ; déployé → vtc_model_versions + push bundle + hot-swap
  entre deux offres ; 1 mois
critere_succes: JAMAIS un modèle inférieur déployé (verrou observé au réel) ; rollback
  une commande vérifié une fois volontairement
rollback: re-push de la version précédente (une commande) + job disabled si dérive
source: spec Vector §4.4
prompt_codex: « Activer l'entraînement ; smoke verrou sur fixture inférieure ; consigner
  chaque déploiement au journal. »
observations: chaque déploiement de modèle = une ligne au journal des bascules
  (model_kind, version, métriques)
```

```
id: ACT-VEC-10   nom_fr: Modèle de zones unifié (zone_eph + zone_wait — nourrit le scoreur)
domaine: vector   classe: apprenant   echelon_audace: 5   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code='vtc_zones_train';
  (les deux régresseurs entrent dans zone_scores du cache)
prerequis_activation: [ACT-VEC-09]
protocole_terrain: temps_mort(zone,h) et attente_client(h) alimentent le €/h du cycle
  complet ; couverture censurée aux zones fréquentées marquée low_coverage + priors
  métier ; 1 mois
critere_succes: verdicts de halo sensibles à la zone de dépose (vérifiable sur offres
  jumelles) ; honnêteté de couverture
rollback: job disabled + zone_scores figés (le scoreur retombe sur les dernières valeurs)
source: spec Vector §4.5
prompt_codex: « Activer zones ; smoke deux consommateurs sur fixtures ; consigner. »
observations: « un seul modèle de zones, deux consommateurs » — le second est ACT-VEC-11
```

```
id: ACT-VEC-11   nom_fr: Bouton « Où je vais » (top 3 zones €/h net)
domaine: vector   classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: flag app vtc_reposition_enabled=true
prerequis_activation: [ACT-VEC-10]
protocole_terrain: à l'arrêt, sans course : top 3 zones + trajet + une ligne de pourquoi
  (template déterministe) ; log passif zone prise/€ h suivant, zéro friction ; pondération
  fin de session (90 min) ; 1 mois
critere_succes: outcome mesuré à +1 h ; followed correct ; hors-ligne → fallback marqué
  « estimation »
rollback: flag=false
source: spec Vector §3.10, §4.5
prompt_codex: « Activer le bouton ; smoke top3 fixture ; consigner. »
observations: choix hors-recommandation = exploration (donnée, pas déviance)
```
