# Plan de génération et transmission

1. Importer le dossier et lire les arbitrages ; conserver les IDs VAU et la cible Tab S8 portrait.
2. Créer structure Android et composants de présentation ; mode démo marqué avec états variés des fixtures.
3. Brancher authentification, couche API et erreurs transversales sur un environnement de test.
4. Livrer VAU-01/02/03/07/08 : manuel, registre, détail, correction et attente réseau.
5. Livrer VAU-09/10/11/12 : catégories en lecture, wallet, échéances, liens réglages.
6. Livrer VAU-06 et bénéfice hebdo : chiffres serveur, dates, explication et corrections.
7. Livrer VAU-04/05 : upload réel, OCR indisponible, vérification et stock_lines sélectionnées.
8. Valider confidentialité, cache, accessibilité et tous les scénarios doc 09. Laisser les dépendances sans contrat désactivées.
9. Refaire l'export des contrats après stabilisation du backend concurrent, vérifier versions/migrations/services et lancer les tests d'intégration isolés.
10. Remettre code frontend, instructions de build, configuration sans secret, tests et limites ; aucun commit backend sans demande.

## Livraison documentaire

Depuis le dépôt, avec les dépendances backend disponibles :

```bash
backend/.venv/bin/python -m pytest backend/tests/test_vault_frontend_kit.py -q
backend/.venv/bin/python scripts/build_vault_frontend_kit.py --output /tmp/vault-delivery-nouvelle
python3 scripts/serve_vault_frontend_kit.py --archive /tmp/vault-delivery-nouvelle/Vault_Frontend_Kit.zip --port 8769 --ttl-hours 24
```

Le constructeur refuse d'écraser une livraison existante. Le serveur sert uniquement une page et le ZIP en mémoire sous un chemin aléatoire, sans exploration du dépôt ; il s'arrête après la durée définie. Conserver la commande active ou lancer le processus détaché pour téléchargement tablette. Le chemin READY s'ouvre sur l'adresse LAN de la machine, ou sur son adresse Tailscale si la tablette est connectée au même réseau privé. Le serveur de téléchargement ne remplace pas l'API métier.

Les scripts et tests sont inclus comme preuve et outil reproductible depuis le dépôt complet ; ce ZIP ne contient volontairement ni environnement backend, ni base, ni fichiers privés.
