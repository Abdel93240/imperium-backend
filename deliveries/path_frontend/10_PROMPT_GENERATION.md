# 10 — Prompt de génération frontend

Copier ce texte avec **tout le dossier** dans le générateur de frontend :

> Construis le frontend Android Jetpack Compose de **The Path**, une application personnelle en français intégrée à l'écosystème Imperium. Lis d'abord README, les documents 01–09, puis `contracts/openapi.json` et les sources jointes. Implémente les douze écrans PAT-01 à PAT-12 et leurs sous-vues, avec téléphone et tablette, design system partagé, états réseau/offline, accessibilité, arabe RTL et tests des parcours critiques. Garde les DTO API séparés des états UI.
>
> Le backend `/api/imperium/path` est l'unique autorité. N'invente aucun endpoint, règle religieuse, score, donnée utilisateur, horaire ou confirmation. Les cinq prières, les jeûnes, le ghusl, les dons, les adhkar, le Coran et les invocations sont mis à jour seulement après une action explicite et une réponse backend. Utilise les champs/version exacts d'OpenAPI, une clé Idempotency-Key stable par action, les dates Europe/Paris, et des montants en centimes/Decimal. Affiche la source et la fraîcheur des horaires, les conflits et les transferts Vault en attente. Respecte la confidentialité des données religieuses. Les fonctions sans contrat sont désactivées avec une explication claire.
>
> Commence par la structure Compose `feature_path` avec repositories, ViewModels, UiState/UiEvent, navigation et composants ; génère les écrans puis les tests. Fournis la liste des routes effectivement intégrées, les fonctions encore non raccordées et la manière de lancer le frontend. Ne modifie pas le backend et ne crée pas de commit.
