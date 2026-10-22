# 02 — Catalogue fonctionnel complet

Les numéros F servent à suivre la couverture. « CODÉ » signifie code trouvé,
non recette de production. Toutes les fonctions restent soumises à l'autorité
et aux limites du document 01.

| ID | Fonction et résultat attendu | Surface | État / référence |
|---|---|---|---|
| F01 | Connexion personnelle, session authentifiée, renouvellement et déconnexion | EXT-ACCESS | CODÉ `/api/auth/*` |
| F02 | Lire la session active ou afficher un vrai état vide | VEC-01/03 | CODÉ sessions/current |
| F03 | Démarrer avec cible CA facultative, direction et mission liée | VEC-02 | CODÉ sessions |
| F04 | Refuser une deuxième session et reprendre celle du serveur | VEC-02/03 | CODÉ conflit 409 |
| F05 | Modifier cible/direction avec version et clé de requête | VEC-03 | CODÉ PATCH session |
| F06 | CA, dépenses, net de session, durée et progression | VEC-01/03/11 | CODÉ kpis ; net ≠ bénéfice hebdomadaire |
| F07 | Gain VTC manuel, zone, date, note, wallet | VEC-04 | CODÉ manual-revenue, écrit au Vault |
| F08 | Dépense carburant/péage/parking/entretien/plateformes/autre | VEC-05 | CODÉ manual-expense, écrit au Vault |
| F09 | Choisir/prévisualiser une capture à l'arrêt | VEC-06 | INTERFACE ; upload Vector À RACCORDER |
| F10 | Demander « Où aller ? » avec zone courante facultative | VEC-07 | CODÉ historique local de l'utilisateur |
| F11 | Rester, changer de zone ou s'abstenir, avec raison courte | VEC-07/08 | CODÉ ; pas de flux externe aujourd'hui |
| F12 | Afficher zones comparées, confiance, créneau et contexte manquant | VEC-08 | CODÉ RecommendationRead |
| F13 | Dernier conseil, date, cache et obsolescence visibles | VEC-01/08 | CODÉ lecture + INTERFACE fraîcheur |
| F14 | Utile/non utile, action réelle et commentaire | VEC-09 | CODÉ ; un retour par recommandation |
| F15 | Confirmer une dépose, zone, GPS facultatif et durée réelle | VEC-10 | CODÉ ; jamais confirmation GPS automatique |
| F16 | Consulter les déposes d'une session | EXT-HISTORY | CODÉ drop-zones |
| F17 | Bilan, note finale, clôture confirmée du backend | VEC-11 | CODÉ complete |
| F18 | Demander un replan Imperium après clôture | VEC-11 | CODÉ replan ; distinct de la clôture |
| F19 | Historique des sessions avec dates de début/fin de filtre | EXT-HISTORY | CODÉ GET sessions |
| F20 | Saisir prix, approche, durée, zones, plateforme, majoration, type | EXT-OFFER | CODÉ offers ; manuel |
| F21 | Signal vert/rouge ou absence de verdict | VEC-03/EXT-OFFER | CODÉ règles seules `rules_only` |
| F22 | Consigner acceptée/refusée/manquée après décision réelle | EXT-OFFER | CODÉ decision ; aucune action sur Bolt |
| F23 | Résultat accepté : gain, approche, attente, course, retour | EXT-OUTCOME | CODÉ outcome ; temps à la minute |
| F24 | Écriture automatique du gain au Vault lors du résultat | EXT-OUTCOME | CODÉ record_revenue ; éviter double saisie |
| F25 | Consulter compteur de collecte et médiane horaire | EXT-LEARNING | CODÉ training-summary ; modèle non entraîné |
| F26 | Lire règles, état actif/ferme, conditions et versions | EXT-RULES | CODÉ rules et not_coded |
| F27 | Modifier les règles existantes avec motif et version | EXT-RULES | CODÉ PATCH ; pas de création/suppression |
| F28 | Mode conduite automatique ou manuel | VEC-03/07/08 | INTERFACE doc 59 §14.14 |
| F29 | Halos, sons différenciés, réglages locaux d'accessibilité | VEC-03 | INTERFACE ; blanc ≠ verdict, aucun jaune course |
| F30 | Brouillons hors ligne, états pending/syncing/failed/conflict | Transversal | INTERFACE doc 14 |
| F31 | Enregistrement vocal, relecture et confirmation | Transversal | INTERFACE ; pipeline Vector dédié À RACCORDER |
| F32 | Permissions GPS/micro/capture/superposition à la demande | EXT-SETTINGS | INTERFACE ; refus non bloquant pour saisie manuelle |
| F33 | Événements, trains, aéroports, trafic, fermetures et météo | VEC-01/03/07 | À RACCORDER ; valeur métier V1 selon décisions de juin |
| F34 | Alertes anti-retour à vide et rentabilité trompeuse | VEC-03/08 | Cible doc 33 ; contexte incomplet aujourd'hui |
| F35 | Courses programmées et coût d'opportunité | EXT-OFFER | Type `scheduled` CODÉ ; agenda et contexte À RACCORDER |
| F36 | Attente prolongée/repositionnement et budget mode destination | VEC-03 | À RACCORDER ; ne pas inventer quota consommé |
| F37 | Son d'offre → capture autorisée → OCR rapide → score VPS | Extension capture | À RACCORDER, décision de juin ; aucune automatisation Bolt |
| F38 | Captures volontaires de majoration, OCR différé et corrélations | Extension surge | À RACCORDER doc 57 ; pas de scraping continu |
| F39 | Import historique Bolt avec OCR, contrôle et dédoublonnage | EXT-IMPORT futur | FUTUR doc 57 §7 ; pas de route dédiée |
| F40 | CatBoost entraîné sur gain/temps mobilisé, transition contrôlée | Backend / indicateur UI | À RACCORDER ; ne pas entraîner sur refus |
| F41 | Rapport hebdo VTC, erreurs de conseil et révisions supervisées | WR Imperium / EXT-LEARNING | Cible docs 33/39/57 ; pas de rapport Vector dédié exporté |
| F42 | Compteurs kilométriques, consommation, coût carburant réel | Smart Fuel | FUTUR V2 doc 46 |
| F43 | Réconciliation carburant pro/perso, Vault puis sadaqa Path | Smart Fuel | FUTUR V2 ; calcul backend |
| F45 | HUD carte, standby/navigation et panneaux contextuels | HUD | FUTUR V6+ doc 55 |
| F46 | Couches zones chaudes, avions, événements, stations, mosquées | HUD | FUTUR V6+ et phases suivantes |
| F47 | Position, trace, raccourcis personnels et apprentissage des voies | HUD | FUTUR ; aucune suggestion de manœuvre illégale |
| F48 | Filtres par couche/élément, jour/nuit, consommation batterie | HUD settings | FUTUR doc 55 |
| F49 | Extensions possibles radar météo, historique géographique, montre/Auto | Recherche future | Idées doc 55, aucune promesse V1 |

## Règles de présentation

Une fonction future n'ajoute pas un bouton inactif dans la navigation principale.
Le catalogue ci-dessus permet de préparer les modules sans surcharger la V1.
VEC-06 reste documenté avec un état explicite d'indisponibilité tant que son
contrat n'existe pas. Les champs sans source (probabilité de retour, budget
mode destination, précision ML) ne sont pas simulés dans le mode API réel.
