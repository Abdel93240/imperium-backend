# Vector — dossier complet de génération du frontend

Livraison du 22 octobre 2026, en français, pour téléphone Android et tablette.
Vector est l'assistant VTC personnel de l'écosystème Imperium. Ce dossier permet
à une IA de générer son interface avec des contrats vérifiables et une vision
complète des fonctionnalités actuelles et futures.

## Commencer ici

1. Lire `01_VISION_ET_PERIMETRE.md` puis `02_CATALOGUE_FONCTIONNEL.md`.
2. Construire les 11 écrans canoniques décrits dans `03_ECRANS_ET_PARCOURS.md`.
3. Appliquer `04_DESIGN_CONDUITE_TABLETTE.md` et `05_INTEGRATION_API.md`.
4. Prendre les types dans `contracts/openapi.json`, les champs dans
   `contracts/forms.md`, les routes dans `contracts/endpoints.md`.
5. Utiliser `examples/requests.json`, `examples/responses.json` et
   `examples/ui_scenarios.json` pour développer sans toucher à la production.
6. Passer la recette `09_RECETTE_FRONTEND.md`.
7. Copier `10_PROMPT_GENERATION.md` dans le générateur et joindre tout le dossier.

`06_OFFLINE_VOIX_PERMISSIONS.md` précise l'autorité du backend et la reprise réseau.
`07_SCORING_REGLES_APPRENTISSAGE.md` fixe les halos, les règles et l'apprentissage.
`08_EVOLUTIONS_COMPLETES.md` couvre Smart Fuel, import, capture,
flux externes et HUD V6+ sans les présenter comme déjà disponibles.
`11_ECARTS_ET_DECISIONS.md` résout les divergences documentaires.
`12_PLAN_GENERATION_ET_HANDOFF.md` indique l'ordre de construction et le relais backend.

## Lire les statuts correctement

- **CODÉ** : route et schéma présents dans cet instantané du dépôt. Cela ne prouve
  ni l'activation ni le bon fonctionnement d'une instance déployée.
- **INTERFACE** : comportement local d'affichage ou de collecte à développer.
- **À RACCORDER** : besoin produit identifié mais contrat dédié absent ou incomplet.
- **FUTUR** : évolution explicitement séparée du socle livré.

Les données des exemples sont fictives. Les annexes `sources/` donnent le contexte
produit ; les URLs historiques qu'elles contiennent ne remplacent pas OpenAPI.
Les écrans supplémentaires proposés pour couvrir les nouvelles routes portent
le préfixe `EXT-`, jamais un faux identifiant canonique VEC-12 ou suivant.

## Fabrication et intégrité

Depuis le dépôt, sans démarrer le backend ni accéder à la base :

```bash
backend/.venv/bin/python scripts/build_vector_frontend_kit.py --output /tmp/vector-delivery
backend/.venv/bin/python -m pytest backend/tests/test_vector_frontend_kit.py
python3 scripts/serve_vector_frontend_kit.py --archive /tmp/vector-delivery/Vector_Frontend_Kit.zip --host 0.0.0.0 --port 8768 --ttl-hours 24
```

`manifest.json` contient la date, le commit de référence (aucun commit créé),
les empreintes des sources inspectées et le SHA-256 de chaque fichier. L'export
refuse d'écraser une livraison existante. Les scripts sous `tooling/` sont fournis
pour audit et doivent être utilisés depuis le dépôt complet, avec ses dépendances.
Le serveur provisoire expose seulement sa page et ce ZIP, sous un lien aléatoire,
et s'arrête après 24 heures. Il ne sert ni les sources du dépôt ni une API Vector.
