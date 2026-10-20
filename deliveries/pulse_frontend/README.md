# Pulse — dossier de génération du frontend

Livraison du 20 octobre 2026. Application personnelle de sport, nutrition et suivi
santé pour un chauffeur VTC. Interface française, utilisable sur téléphone Android
et tablette. Le backend commun conserve toute autorité métier.

## Ordre de lecture

1. `01_VISION_ET_PERIMETRE.md` : intention, priorités et limites.
2. `02_CATALOGUE_FONCTIONNEL.md` : toutes les fonctions attendues et leur disponibilité.
3. `03_ECRANS_ET_PARCOURS.md` : écrans, champs, actions et critères de réussite.
4. `04_DESIGN_ET_ACCESSIBILITE.md` : navigation, composants, tablette.
5. `05_INTEGRATION_API.md` : authentification, contrats, uploads, erreurs.
6. `06_OFFLINE_CONFIDENTIALITE.md` : synchronisation, consentements, données sensibles.
7. `07_INTELLIGENCE_ET_EVOLUTIONS.md` : recommandations, programmes et fonctions à venir.
8. `08_RECETTE_FRONTEND.md` : scénarios de validation.
9. `09_PROMPT_GENERATION.md` : prompt à copier dans le générateur.
10. `10_ECARTS_ET_DECISIONS.md` : divergences entre anciens documents et code.

Dans le ZIP, `contracts/openapi.json` fournit les contrats extraits du routeur
FastAPI courant, sans démarrage du serveur, lecture de données utilisateur ou
appel IA. `contracts/endpoints.md` et `contracts/forms.md` en donnent des vues lisibles.
`examples/requests.json` contient uniquement des exemples fictifs validés par les
schémas Pydantic. `examples/ui_scenarios.json` décrit les états de présentation.
`sources/` conserve les références produit sélectionnées ; ce sont des annexes,
pas des instructions pour implémenter le backend.

**Codé ne signifie pas activé.** L'inventaire décrit le dépôt, pas une recette de
production. L'application doit afficher les refus et états désactivés renvoyés
par le serveur. Ne pas activer une fonction ni inventer une route pour achever
une maquette. Aucun secret ni donnée personnelle réelle n'est inclus.

## Autorité des sources

Les instructions utilisateur et règles produit priment. Pour les URLs, champs,
types et validations disponibles, utiliser le contrat extrait du code et les
notes d'intégration. Les annexes décrivent aussi la cible future et contiennent
des URLs historiques. La politique canonique des modèles reste le document 30
du dépôt ; le frontend ne choisit aucun modèle.

## Fabrication et téléchargement

Depuis la racine du dépôt :

```bash
backend/.venv/bin/python scripts/build_pulse_frontend_kit.py --output /tmp/pulse-delivery
backend/.venv/bin/python -m pytest backend/tests/test_pulse_frontend_kit.py
python3 scripts/serve_pulse_frontend_kit.py --archive /tmp/pulse-delivery/Pulse_Frontend_Kit.zip --port 8767 --ttl-hours 24
```

Le serveur provisoire fournit seulement une page de téléchargement et ce ZIP,
sous un chemin aléatoire. Il ne parcourt aucun répertoire du dépôt, ne reçoit
aucun upload et s'arrête après la durée indiquée. `Ctrl+C` l'arrête plus tôt.
L'adresse réseau dépend de la machine de livraison. Le serveur n'est pas l'API
Pulse ni un déploiement du frontend. Le fichier `manifest.json` du ZIP permet de
vérifier les empreintes SHA-256 des fichiers livrés.
