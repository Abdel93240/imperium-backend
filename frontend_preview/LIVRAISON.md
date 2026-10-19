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
Codé aussi : catégorie suggérée d'une transaction (doc 42 §7.0), réglages (doc 43 §15), état des services (GET /api/health/services), Nourrir l'IA (doc 70), OCR des PDF et images pour Nourrir l'IA (né désactivé, ops/gpu/OCR_SMOKE_CHECKLIST.md), justificatifs du Vault et d'Imperium (POST /api/imperium/vault/receipt-extractions, doc 37 §3.4) avec passage des articles alimentaires au stock Pulse (GET /api/imperium/pulse/food-stock), ajout et modification manuels du stock (POST et PATCH, version obligatoire), alertes de date limite (GET /api/imperium/pulse/food-stock/alerts + job pulse.food_stock_expiry à 9 h, semé désactivé), scan du placard (POST /api/imperium/pulse/food-stock/scans, photo jamais conservée, route /vision du service local), ajout au stock par le chatbot (POST /api/imperium/pulse/food-stock/declarations/preview puis POST …/declarations, une ligne par achat), repas avec décompte du stock (POST /api/imperium/pulse/meals/drafts au texte ou POST …/meals/photo-drafts en photo, puis POST …/{id}/confirm ; macros estimées depuis la photo, saisies au texte), hydratation (POST et GET /api/imperium/pulse/hydration-logs, l'eau bue est décomptée du stock), tableau de bord Pulse du jour (GET /api/imperium/pulse/dashboard, score santé masqué tant qu'il n'est pas calculé), séances de sport (POST/GET/PATCH /api/imperium/pulse/workouts, /start, /complete, /skip), matériel possédé (GET/POST/DELETE /api/imperium/pulse/equipment), consentement santé par domaine (GET/POST/DELETE /api/imperium/pulse/consents) et relevés corporels (GET/POST/DELETE /api/imperium/pulse/body-snapshots, sans photo, suppression réelle), journal des douleurs (GET/POST/DELETE /api/imperium/pulse/pain-logs, /{id}/resolve, sous consentement), médical (documents et règles sous double consentement : /api/imperium/pulse/medical-documents et /medical-rules, activation avec confirmation explicite, extraction automatique pas encore). Path : prières marquées (GET /api/imperium/path/prayers, POST …/prayers/{prière}/mark et /clear, jamais déduites) et jeûne (POST /api/imperium/path/fasts, /{id}/end, /{id}/break, GET …/fasting/state) ; pendant la fenêtre d'un jeûne, l'hydratation Pulse est bloquée, un repas reçoit un avertissement et le tableau de bord affiche une bannière. Sadaqa (GET/PATCH /api/imperium/path/sadaqa/settings, GET …/sadaqa/summary, GET/POST/DELETE …/sadaqa/donations, /{id}/vault-retry) : objectif de la semaine sur le bénéfice pro du Vault avec montant reporté, dépense « sadaqa » écrite au Vault (en attente si l'écriture échoue), job path.sadaqa_week_close semé désactivé. Ghusl (GET /api/imperium/path/ghusl, POST …/ghusl/activate et /complete, GET/POST/PATCH/DELETE …/ghusl-addresses) : activé et terminé par l'utilisateur seulement, mission Imperium « Faire le ghusl avant {prière} » et replanification immédiate. Adhkar (GET /api/imperium/path/adhkar/suggestions, routines, /increment, /reset) et Coran (GET /api/imperium/path/quran/continuation, POST …/progress, PATCH …/objective, POST …/khatm, …/plans). Tableau de bord Path (GET /api/imperium/path/dashboard : prières, prochaine prière, jeûne, sadaqa, ghusl, adhkar, Coran, qibla) et annulation d'un jeûne démarré par erreur (POST …/fasts/{id}/cancel). Calendrier hégirien (GET /api/imperium/path/calendar/hijri et /events, POST …/confirm-date, …/personal-events) : dates prédites affichées en double (J / J+1) jusqu'à la confirmation de l'observation. Vector : sessions VTC (GET /api/imperium/vector/sessions/current, POST /sessions, PATCH, /manual-revenue et /manual-expense écrits au Vault, /drop-zone, /complete). « Où aller ? » (POST /api/imperium/vector/recommendations, /latest, /{id}, /{id}/feedback) : zone conseillée sur l'historique du créneau, ou abstention. Courses proposées (POST /api/imperium/vector/sessions/{id}/offers, /offers/{id}/decision et /outcome, GET /training-summary) : base d'apprentissage du scoring. Règles métier R1, R2, R7, R8 (GET/PATCH /api/imperium/vector/rules) : signal « règles seules » vert ou rouge sur chaque course proposée, sinon « à toi de juger ». Soldes réels du Vault (GET /api/vault/wallet, POST …/wallet/snapshots ; la pression les lit) et échéances payées (POST /api/vault/upcoming-expenses/{id}/mark-paid). Correction d'une transaction (POST /api/imperium/vault/transactions/{id}/correct : écriture inverse + corrigée). Réglages Vault en lecture seule (GET /api/vault/settings). Mosquées enregistrées (GET/POST/PATCH/DELETE /api/imperium/path/mosques) : la mosquée par défaut sert de référence aux horaires et à la qibla de l'utilisateur. Vérification de fraîcheur après « Démarrer la journée » (GET /api/imperium/day/freshness, lecture seule, sans IA) : calendrier modifié depuis le plan, missions non faites de la veille, mission restée active, contraintes (ghusl, jeûne, replan ouvert, standby). Annulation d'une mission (POST /api/imperium/missions/{id}/cancel, raison obligatoire, définitive). Réglages Path (GET/PATCH /api/imperium/path/settings) : méthode de calcul, madhhab et ville du calcul local des horaires. Historique (GET /api/imperium/history/events et /{event_id}) : chronologie en lecture seule des missions, journées, plans, décisions, projets et Weekly Reviews, avec filtres et recherche. Détail d'une mosquée (GET /api/imperium/path/mosques/{id}) : horaires MAWAQIT en cache et leur qualité, horaires calculés, qibla. Historique : les missions supprimées ou annulées depuis le standby apparaissent comme annulées, plus comme ratées. Mission ratée : selon les réglages, replan demandé aussitôt (échéance dans les 24 h, par défaut) ou proposé à l'utilisateur (champ `replan` de la réponse). Douleur : POST /api/imperium/pulse/pain-logs/{id}/replan quand l'utilisateur accepte de replanifier. Invocations (GET/POST /api/imperium/path/invocations, favoris, matin et soir à cocher via /invocations/daily et /{id}/check). Historique : journées (GET /api/imperium/history/days) et Finances (GET /api/imperium/history/finances?period=). Corrections de la pression (POST /api/vault/pressure/corrections : échéance reportée ou déjà réglée, semaine exceptionnelle ; /{id}/revoke). Versions du plan vivant (GET /api/imperium/day/plan/{id}/versions) : chaque replan accepté ajoute une version, l'ancienne est conservée. Fin de session VTC : POST /api/imperium/vector/sessions/{id}/replan quand l'utilisateur demande de replanifier la journée. Mission ratée ou annulée : POST /api/imperium/missions/{id}/replan quand l'utilisateur accepte de replanifier (annuler une mission en cours le propose). Widgets du tableau de bord Imperium (GET /api/imperium/dashboard/widgets) : prochaine prière avec compte à rebours et score de pression, en lecture seule. Docket du WR (GET /api/wr/docket?status=&type=, GET /api/wr/docket/red, POST /api/wr/docket/{id}/decision) : points à trancher triés par priorité, report limité (au 3e report, trancher ou archiver), point rouge notifié tout de suite ; aucun écran ne l'affiche encore. Mode court du docket (GET /api/wr/docket?mode=light : rouges, décisions forcées, contradictions, deltas de plan). Digest du WR (POST /api/wr/digest, GET /api/wr/digest/current) : instantané figé du docket pour la revue en cours, plafonné par type et en taille. Métriques du WR (GET /api/wr/metrics/weekly?weeks=) : activité du docket par semaine et WR tenu ou sauté ; job wr.metrics_rollup semé désactivé. Journal des appels IA (GET /api/ai/call-logs, GET /api/ai/call-logs/daily) : chaque appel au modèle local, à l'OCR et aux embeddings est noté (durée, tokens, coût, erreur), jamais son contenu ; grille de prix vide à fournir. Alertes du journal (GET /api/ai/call-logs/alerts : dépense du jour ou de la semaine, taux d'erreur, erreurs du modèle local, appel trop cher, lenteur, replis) ; job ai.call_alerts semé désactivé.
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
