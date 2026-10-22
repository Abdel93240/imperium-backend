# The Vault — dossier complet de génération frontend

Livraison du 22 octobre 2026. Application personnelle de réalité financière pour un chauffeur VTC. Ce dossier permet de générer le frontend ; il ne contient pas une application déjà compilée. Cible canonique : Android Kotlin / Jetpack Compose, Samsung Galaxy Tab S8 en portrait, adaptation téléphone et grande tablette.

## Ordre de lecture

1. `01_VISION_ET_PERIMETRE.md` : objectif et règles inviolables.
2. `02_CATALOGUE_FONCTIONNEL.md` : toutes les capacités, priorité et disponibilité.
3. `03_ECRANS_ET_PARCOURS.md` : les 12 écrans, champs et transitions.
4. `04_DESIGN_ET_ACCESSIBILITE.md` : présentation et utilisation tablette.
5. `05_INTEGRATION_API.md` : connexion aux routes réellement présentes.
6. `06_OFFLINE_VOIX_CONFIDENTIALITE.md` : brouillons, synchronisation et permissions.
7. `07_REGLES_FINANCIERES_ET_INTEGRATIONS.md` : sens des chiffres et liens entre apps.
8. `08_EVOLUTIONS_ET_LIMITES.md` : fonctions attendues mais non raccordées et V2.
9. `09_RECETTE_FRONTEND.md` : scénarios de validation.
10. `10_PROMPT_GENERATION.md` : prompt à copier dans le générateur.
11. `11_ECARTS_DOCUMENTAIRES.md` : arbitrages entre anciens documents et code.
12. `12_PLAN_DE_REALISATION.md` : ordre d'implémentation et passage en mode réel.
13. `13_BULLE_FLOTTANTE.md` : saisie rapide par-dessus les autres apps et activation locale.

## Fichiers techniques dans le ZIP

- `contracts/openapi.json` : export des routes Vault et authentification du checkout, sans lancer le serveur backend ni accéder à la base.
- `contracts/endpoints.md` et `forms.md` : inventaire lisible des paramètres, corps, réponses et champs.
- `examples/requests.json`, `responses.json`, `ui_scenarios.json` : exemples fictifs, validés par les modèles Python et états à représenter.
- `sources/docs_master/` : références produit sélectionnées et extraits du design system. Leur historique peut contenir des routes périmées : appliquer le document 11.
- `manifest.json` : date, commit de référence, empreintes des sources et des fichiers. Ce commit identifie la base lue ; aucun commit n'est créé par cette livraison.
- `tooling/` : scripts de livraison et tests pytest, à utiliser depuis le dépôt d'origine. Ils ne sont pas un SDK frontend autonome.

Commencer par fournir **tout le dossier**, puis le prompt du document 10 au générateur. Les exemples sont des instantanés indépendants : ne pas les additionner comme un historique comptable cohérent. Les contrats décrivent le code présent, pas la disponibilité des services ou migrations du serveur déployé. Une autre IA travaille sur le backend : revérifier l'export avant branchement final.
