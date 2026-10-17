# Imperium — prévisualisation web V1 · livraison du 2026-10-17

Emplacement : `frontend_preview/` (hors backend, aucun impact sur l'API ni les tests).

Kit source : `Imperium_Frontend_Kit_2026-10-16_v2` (6 ZIP, `VERIFIER_KIT.py` → OK, 619 fichiers).
Dépôt inspecté : `/opt/imperium-backend`, `main` @ 4989f49 (préfixe API `/api`).

## Ce que c'est
Une prévisualisation **web** navigable, construite en composants réels (HTML/CSS/JS sans
dépendance, polices et assets du kit, aucune ressource distante). **Ce n'est pas l'app
Android** : la stack cible (doc 59) est Kotlin + Jetpack Compose. Aucun build Android
n'a été produit ni ouvert sur la Tab S8.

## Lancer
```
python3 -m http.server 8770 --directory frontend_preview
# ouvrir http://<hôte>:8770/            (mode démo, défaut)
#        http://<hôte>:8770/?mode=backend (adaptateur réel, non raccordé)
```
Recette : servir sur 127.0.0.1:8770 puis `python3 frontend_preview/run_recette.py frontend_preview <dossier du kit>`
(Chrome headless ; le kit n'est pas versionné, `*.zip` est ignoré), ou
`?recette=R01` dans l'URL pour un contrôle isolé. `?open=<vue>` ouvre une fenêtre directement.

## Structure
- `js/services/demo.js` — fournisseur de démonstration (DEMO.json : horloge 07:24:18,
  journée 03:30, mission 07:00, délai de replan +3 min, pression 52, Imperium sans
  estimation WR, VTC 35 %). Aucune requête réseau. Hors ligne (doc 14) : fin de journée,
  résultat de mission, transaction et notes vont en file « en attente » (annulables,
  envoyées au retour du réseau) ; les actions IA sont refusées.
- `js/services/backend.js` — adaptateur réel, même interface ; carte opération → route
  du dépôt (existe / partiel / à confirmer / manquant). Aucune route inventée.
- `js/services/index.js` — seul point d'accès des écrans (`svc`).
- `js/screens/*`, `js/flows.js`, `js/terminal.js`, `js/core.js` — rendu et parcours.
- `js/recette.js` — les 50 contrôles de `07_recette/RECETTE.csv`.

## Recette — 48 PASS · 0 FAIL · 2 NON TESTE
Résultats détaillés : `recette/RECETTE_resultats.csv`, preuves `recette/R01.png` … `R50.png`
(Chrome headless, 800×1180 sauf R18/R19 800×553 et R43 1200×1900).

R18 et R19 (clavier) : PASS, validés par l'utilisateur sur la Galaxy Tab S8 le 2026-10-17.

NON TESTE (simulation web PASS, appareil requis) :
- R33 bulle sans autorisation overlay · R34 actions de la bulle — overlay Android non exécuté.

Bugs trouvés par la recette et corrigés : liste des services de « Connexion à Imperium »
rendue en `[object HTMLDivElement]` ; scénarios contenus longs / journée 36 h non
reconstruits ; terminal non positionné sur le dernier message ; mention « en attente
d'envoi » invisible aux lecteurs d'écran ; grille des annexes qui débordait avec des
titres longs.

## Carte du raccordement API (résumé)
Existe : journée (`/api/imperium/day/current|start|finish`), dashboard et missions
(`/api/imperium/dashboard`, `/missions/active`, `/missions/{id}/complete|fail`),
finances (`/api/imperium/vault/summary|transactions`, `/api/vault/pressure`),
priorités (`/api/imperium/decision-framework/priorities`), Weekly Review
(`/api/imperium/weekly-review/launch|…/approve`), santé (`/api/health`, `/api/health/db`),
connexion (`/api/auth/login`).
Codé le 2026-10-17 : missions annexes, `estimated_minutes`, `failure_reason_code`,
`deadline_at`, statut `standby` et clôture de journée (doc 43 §5.4), replanification
(demande, délai serveur, proposition IA, correction, acceptation/annulation).
Runner `imperium.rolling_replan` codé (proposition déterministe + corrections par le modèle
local), semé désactivé : à activer selon le doc 76.
Codé aussi : projets, missions de projet, routines et leurs coches, notes de mission.
Codé aussi : catégorie suggérée d'une transaction (doc 42 §7.0), réglages (doc 43 §15), état des services (GET /api/health/services), Nourrir l'IA (doc 70), OCR des PDF et images pour Nourrir l'IA (né désactivé, ops/gpu/OCR_SMOKE_CHECKLIST.md), justificatifs du Vault et d'Imperium (POST /api/imperium/vault/receipt-extractions, doc 37 §3.4) avec passage des articles alimentaires au stock Pulse (GET /api/imperium/pulse/food-stock), ajout et modification manuels du stock (POST et PATCH, version obligatoire), alertes de date limite (GET /api/imperium/pulse/food-stock/alerts + job pulse.food_stock_expiry à 9 h, semé désactivé), scan du placard (POST /api/imperium/pulse/food-stock/scans, photo jamais conservée, route /vision du service local).
Codé aussi : logs de l'IA, modèles par rôle, seuils /200, clés API (écriture seule).
Manquant :
OCR,
Carte complète : panneau Démo → « Carte des
opérations ».

## Limites connues
- Caméra, galerie, micro (onde et transcription de démonstration), notifications,
  autorisations et bulle : **simulés**, aucune capacité Android réelle.
- « Pas fait » : 4 raisons codées du doc 52 §10 (décision 2026-10-17). Replanification :
  5 catégories du doc 01 + détails obligatoires (doc 43 §3.4, décision 2026-10-17).
- Limites d'import (doc 70 §6) : pré-contrôle client par fichier, 25 Mo documents/images,
  500 Mo audio/vidéo ; le contrôle ferme reste côté backend.
- Console de calibration Tower : URL non fournie, lien non branché.
- Le format des dates et heures dépend de la langue du navigateur.
