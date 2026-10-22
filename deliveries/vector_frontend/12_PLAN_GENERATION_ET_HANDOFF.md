# 12 — Ordre de génération et transmission au backend

## Construction frontend

1. Charger types OpenAPI, config de base URL, auth et adaptateurs DTO/vue.
2. Ajouter navigation, thème Vector, états communs et fixtures séparées.
3. Démarrer/reprendre une session, KPIs, gain/dépense, idempotence et conflits.
4. Ajouter où aller/détail/feedback, datation du cache et abstention.
5. Ajouter dépose/bilan/clôture/replan avec file locale ordonnée.
6. Ajouter offres/décisions/résultats, historique, règles et compteurs.
7. Tester mode conduite, téléphone/tablette, accessibilité et reprise réseau.
8. Garder les interfaces futures isolées et produire le relevé des raccords manquants.

Pas de branchement sur une base réelle pour une maquette. Les exemples JSON
sont validés par les schémas actuels, sans prétendre être des réponses de production.

## Attendus de l'IA frontend

Code clair par feature, composants partagés, repository API et repository mock
séparés, gestionnaire de file locale testable, tests de parcours critiques,
instructions de lancement et configuration sans secret. Un état réseau ne doit
pas effacer le brouillon de l'utilisateur. Le build doit échouer visiblement si
le contrat utilisé n'est pas couvert, plutôt que contourner le type par `any`.

## Transmission à l'IA backend

Ce kit est un instantané : relire les contrats avant tout branchement final,
car le backend peut évoluer en parallèle. Livrer à l'autre IA une liste de
besoins fonctionnels, sans inventer des URLs définitives :

- pipeline capture/offre et gestion des permissions/échecs OCR ;
- réception/transcription d'une note vocale Vector et validation du résultat ;
- signaux opérationnels horodatés et sources par zone ;
- statut réel du modèle, fraîcheur/abstention et signal courant ;
- import historique et prévention de doublons comptables ;
- quota destination et attente, si ces besoins sont confirmés ;
- contrats Smart Fuel, puis HUD selon les phases approuvées.

Demander pour chacun : request/response typées, erreurs, idempotence/version,
durée de vie, activation, permissions et effet canonique. Ce sont des informations
pour un futur raccord, pas une demande de réécrire le backend maintenant.

## Validation de ce kit

Tests pytest dédiés : couverture de toutes les routes Vector exportées,
résolution des références OpenAPI, conformité des exemples request/response,
présence des écrans, intégrité SHA-256 du ZIP, refus de symlinks/fichiers inattendus,
refus d'écrasement et isolation du serveur (GET/HEAD, refus d'écriture, expiration,
traversal et chemins non autorisés). Ils ne démarrent pas la base de production.

Le serveur provisoire est un processus de téléchargement distinct, avec une
page adaptée tablette et un ZIP fixe chargé en mémoire. Pas de directory listing,
pas d'upload et pas d'accès réseau aux sources de travail. Un port distinct
préserve les serveurs existants. Aucun commit, push ou déploiement backend.
