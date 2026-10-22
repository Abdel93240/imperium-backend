# 03 — Écrans, champs, actions et parcours

Les 11 identifiants VEC proviennent des docs 59 et 79. Les URLs de navigation
ci-dessous sont des routes **frontend**. Les chemins API sont dans le document 05.
Tous les écrans ont loading, erreur/retry, cache daté, hors ligne et conflit.
Les données nulles donnent « Non disponible » ou un état vide, jamais un zéro inventé.

## VEC-01 — Dashboard · /vector/dashboard

Afficher en premier la session active (ou « Aucune session en cours »), son CA,
sa durée et sa progression si une cible existe. Ensuite le dernier conseil de
zone avec raison, date et contexte manquant. Action principale : « Démarrer une
session » ou « Reprendre la session ». Raccourcis gain, dépense et dépose seulement
si la session correspondante est disponible. « Où aller ? » peut fonctionner
sans session active selon le contrat actuel. Historique et réglages accessibles
à l'arrêt. Les signaux événements/trains/traffic sont réservés à un raccord futur.

Chargement : squelettes distincts pour session et conseil. Une panne de lecture
du conseil ne doit pas effacer une session correctement chargée. Premier usage :
pas de faux gains, pas de zone supposée rentable. Une permission GPS refusée
permet toujours une saisie manuelle. Succès : reprendre exactement l'id serveur.

## VEC-02 — Démarrage · /vector/sessions/start

Bottom sheet téléphone, panneau latéral tablette. Champs actuels :
`target_ca_cents` facultatif (1 à 10 000 000), `strategic_direction` facultatif
(120 caractères), `mission_id` facultatif si transmis par Imperium.
Ne pas envoyer durée, kilomètres ou intention libre sous un champ inventé.
Montant saisi en euros, conversion décimale sûre vers centimes entiers.

Boutons « Démarrer » et « Annuler ». Désactiver le double appui pendant l'envoi,
conserver la même Idempotency-Key lors d'un retry. Après confirmation serveur,
ouvrir VEC-03. Hors ligne : « Démarrage en attente », aucun faux id canonique.
409 : proposer « Reprendre la session existante » ; pas de remplacement silencieux.

## VEC-03 — Session active · /vector/sessions/active

CA, dépenses, net de session, durée, objectif/progression, direction stratégique,
statut réseau et nombre d'actions en attente. Lire les KPIs du serveur. Le timer
local peut animer le temps affiché depuis `started_at`, pas réécrire les résultats.
Un objectif absent n'affiche ni 0 % ni « objectif raté ».

En conduite : carte centrale, halo et une action principale « Où aller ? ».
Actions secondaires compactes : gain, dépense, « Dépose effectuée », fin de session.
Édition cible/direction à l'arrêt : envoi de la version lue et d'une clé stable.
Pas de quota de destination fictif. Un signal de course expire visuellement quand
son contexte n'est plus courant ; aucun ancien vert ne se transforme en conseil live.

Si session terminée ailleurs : ouvrir VEC-11 avec l'état serveur. Une action
locale non acceptée reste récupérable comme brouillon. La clôture attend le
traitement ou l'annulation explicite des écritures locales de cette session.

## VEC-04 — Gain manuel · /vector/revenue/manual

Montant positif en centimes (plafond 10 000 000), zone facultative (120), date/heure
facultative, note (300), wallet (1–80 caractères ; défaut contrat `cash`).
Ne pas inventer une liste de wallets autorisés : utiliser la configuration du
projet ou conserver le défaut clairement visible. Identifiant de session requis
par l'URL. Bouton « Enregistrer le gain ».

Le backend crée la transaction Vault et renvoie son id avec la session actualisée.
Ne pas envoyer une deuxième transaction à The Vault. En conduite : saisie longue
reportée ; dictée uniquement si disponible et toujours confirmée. Après timeout,
rejouer avec la même clé. Succès seulement sur réponse confirmée.

## VEC-05 — Dépense manuelle · /vector/expense/manual

Montant positif, catégorie obligatoire : `carburant`, `peage`, `parking`,
`entretien`, `plateformes`, `autre`. Date, note et wallet comme VEC-04.
Présenter les libellés français avec accents sans modifier les valeurs API.
Bouton « Enregistrer la dépense ». Péage/parking/autre rejoignent la catégorie
comptable `charges` côté serveur ; aucun changement de vocabulaire côté API.

Même cycle pending/syncing/synced et même prévention de double transaction.
Une correction d'écriture confirmée appartient au parcours Vault existant ;
ne pas inventer de DELETE de revenu ou de dépense Vector.

## VEC-06 — Capture · /vector/screenshots/upload

Sélecteur de fichier Android, aperçu, retirer/remplacer le brouillon. À l'arrêt
uniquement. Dans ce snapshot, **aucune route d'upload Vector dédiée n'existe** :
présenter « Envoi des captures pas encore disponible » et la saisie manuelle
comme solution utilisable. Ne pas envoyer les fichiers à un endpoint supposé.

La cible V1 historique est upload-only, l'OCR et la chaîne son/capture sont
traités dans les évolutions et les écarts. Ne jamais afficher « Envoyé » si le
fichier est uniquement stocké localement. Pas de contournement de FLAG_SECURE.

## VEC-07 — Où aller ? · /vector/recommendations/request

Zone courante facultative, action « Calculer ». Résultat serveur : `stay_here`
(« Rester dans la zone »), `move_to_zone` (« Rejoindre … »), `abstain`
(« Haute incertitude, à toi de juger. »). Raison courte et date visibles.
Le calcul actuel compare des historiques de revenus, pas la demande en direct.

Pas de reconstruction de stratégie en local. Une erreur peut montrer l'ancien
conseil avec son libellé cache et une action « Réessayer ». Une recommandation
ancienne ne doit pas sonner comme une nouvelle décision. Accès VEC-08 et VEC-09.

## VEC-08 — Détail du conseil · /vector/recommendations/:id

Zone, recommandation, raison, confiance, créneau et `requested_at`. Tableau des
zones comparées : nombre de courses, nombre de sessions, gain moyen par course.
Liste `missing_context` avec libellés lisibles. Le taux horaire par zone est
actuellement nul : ne pas appeler le gain moyen d'une course « €/h ».

Le détail ne calcule pas de probabilité aéroport ou retour vide absente du DTO.
Conduite : une carte compacte et brève. À l'arrêt : détail et « Donner mon avis ».
404 : « Conseil introuvable », retour dashboard. Aucun texte explicatif de
**verdict de course** en direct ; ceci est une recommandation de zone distincte.

## VEC-09 — Retour sur conseil · /vector/recommendations/:id/feedback

`useful` obligatoire (oui/non) ; `ride_user_action` facultatif : `accepted`,
`refused`, `missed`, `ignored` ; `reason` facultative (500 caractères).
« Suivi », « Refusé », « Manqué », « Ignoré » décrivent ce que l'utilisateur a fait
avec le conseil. Ce formulaire ne pilote aucune application VTC.

Un seul retour canonique. 409 `RIDES_FEEDBACK_CONFLICT` : afficher celui du serveur,
conserver le texte local si nécessaire, sans inventer un PATCH de modification.
Pas de promesse d'idempotence par header pour cette route qui n'en déclare pas.

## VEC-10 — Dépose · /vector/drop-zone/confirm

Zone obligatoire, 1–120 caractères non blancs. Latitude/longitude facultatives
mais ensemble, jusqu'à 6 décimales ; `gps_confidence` facultative 0–1 à 2 décimales ;
`real_duration_minutes` facultatif 1–600. Localisation proposée modifiable.
Ne pas convertir automatiquement la précision en mètres en confiance arbitraire.
Boutons « Confirmer la dépose » et « Annuler ». Pas d'enregistrement automatique
à l'arrivée GPS. Après succès, retour session ; doublon rejoué avec même clé.

## VEC-11 — Bilan · /vector/sessions/:id/review

Session, heures début/fin, CA, dépenses, net, nombre d'écritures, durée, cible
atteinte ou non si connue. `review_note` facultative, 2 000 caractères.
Pas de tableau de « mauvaises recommandations » sans données réelles associées.
Avant clôture, montrer les brouillons en attente et permettre leur traitement.
« Terminer la session » appelle complete. Le bilan confirmé reste consultable.

Après clôture seulement, action distincte « Replanifier dans Imperium ».
Afficher « Demande transmise » lorsque le backend a accepté la demande ; ne pas
afficher une nouvelle mission ni « journée replanifiée » à cette étape.
409 cooldown/journée non démarrée/demande déjà ouverte : expliquer sans annuler
la clôture réussie. Une double demande peut renvoyer 200 au lieu de 201.

## Sous-vues proposées pour les routes supplémentaires

| ID local | Contenu et parcours | Critère essentiel |
|---|---|---|
| EXT-ACCESS | Connexion, session expirée, déconnexion | Tokens hors UI/logs, pas d'inscription multi-utilisateur |
| EXT-HISTORY | Depuis dashboard : liste sessions filtrée par dates, détail puis offres/déposes | Dates selon Paris ; pas de pagination inventée |
| EXT-OFFER | Depuis session à l'arrêt : liste + formulaire offre + décision passée | Champs RideOfferCreate ; `signal` vient du backend |
| EXT-OUTCOME | Depuis offre acceptée : gain réel, approche/attente/course/retour, wallet | `record_revenue=true` par défaut ; aucune double saisie |
| EXT-RULES | Depuis réglages : liste règles existantes, édition conditions/active/ferme/motif | Version obligatoire ; `not_coded` reste indisponible |
| EXT-LEARNING | Depuis historique/réglages : collecte, résultats réels, médiane, message serveur | Phase ne prouve pas un modèle entraîné |
| EXT-SETTINGS | Mode conduite, sons, permissions, données locales et API configurée | Réglages locaux clairement distincts des règles backend |

## Parcours de référence

1. Connexion → dashboard vide → démarrer → session active.
2. Session → gain/dépense → confirmation → KPIs rechargés.
3. Session → où aller → détail → retour utile/non utile.
4. Session → offre manuelle → signal serveur → décision réelle → résultat accepté.
5. Session → dépose confirmée → bilan → clôture → demande de replan facultative.
6. Hors ligne → brouillon → reprise → version en conflit → état serveur visible.
7. Historique → session terminée → offres/résultats en lecture.

Le bouton retour ferme d'abord la sheet ; un formulaire modifié propose de
conserver ou abandonner son brouillon. Le retour ne relance aucune mutation.
