# The Path — dossier de génération frontend

Livraison documentaire du 24 octobre 2026. Application personnelle Android en français pour le suivi du culte. Le backend commun décide et valide ; The Path collecte, affiche et déclenche des actions explicites. Ce dossier est conçu pour générer le frontend sans modifier le backend.

## Ordre de lecture

1. `01_VISION_ET_PERIMETRE.md` — principes, MVP et phases.
2. `02_CATALOGUE_FONCTIONNEL.md` — couverture exhaustive par domaine.
3. `03_ECRANS_ET_PARCOURS.md` — douze écrans PAT et sous-écrans.
4. `04_DESIGN_ET_ACCESSIBILITE.md` — design, tablette et conduite.
5. `05_INTEGRATION_API.md` — contrats réellement exposés et règles réseau.
6. `06_OFFLINE_VOIX_CONFIDENTIALITE.md` — cache, synchronisation et données sensibles.
7. `07_REGLES_METIER_ET_INTEGRATIONS.md` — règles religieuses et échanges inter-apps.
8. `08_EVOLUTIONS_ET_ECARTS.md` — fonctions non raccordées et divergences.
9. `09_RECETTE_FRONTEND.md` — scénarios de vérification.
10. `10_PROMPT_GENERATION.md` — consigne prête à donner au générateur.

`contracts/openapi.json` est un snapshot des routes FastAPI Path et auth extrait sans lancer le serveur ni lire la base. `contracts/endpoints.md` en donne l'inventaire. Les documents de référence sont dans `sources/`. L'implémentation d'une route dans le dépôt ne prouve pas son activation sur l'instance déployée : toute fonction doit afficher l'état réel renvoyé par l'API. Aucun identifiant, secret ni donnée de l'utilisateur n'est inclus dans l'archive.

**Autorité des sources :** code et schémas API pour les champs/chemins actuels ; `docs_master/41_PATH_LOGIC_DETAIL.md` pour les règles Path ; `docs_master/59_DESIGN_SYSTEM_V1_DRAFT.md` et `60`–`63` pour l'interface ; `docs_master/79_FRONTEND_MAP.md` pour la carte des écrans. Les écarts sont listés au document 08.
