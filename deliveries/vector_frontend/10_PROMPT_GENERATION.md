# 10 — Prompt à transmettre à l'IA de génération du frontend

Copier le texte suivant et joindre tout le dossier décompressé.

---

Tu dois générer le frontend de **Vector**, assistant VTC personnel de l'écosystème
Imperium, en français, pour téléphone Android et tablette. Lis le README et les
documents 01 à 12 de ce dossier avant de coder. Respecte les contrats fournis.

Le backend existe et une autre IA travaille dessus. Tu ne dois ni le réécrire,
ni modifier ses tables, ni inventer des endpoints. Le frontend affiche, collecte,
et demande ; le backend commun/n8n/PostgreSQL/pgvector gardent l'autorité métier.
Une seule mission active Imperium et une seule session VTC active. Vector ne
pilote jamais Bolt : aucun clic, acceptation automatique ou contournement.

Génère d'abord les 11 écrans VEC-01 à VEC-11, avec les sous-vues EXT-HISTORY,
EXT-OFFER, EXT-OUTCOME, EXT-RULES, EXT-LEARNING et les réglages d'interface. Les EXT
sont des sous-vues proposées pour couvrir les routes codées, pas des numéros
canoniques supplémentaires. VEC-06 doit montrer honnêtement son absence de
raccordement API. Les fonctions futures Smart Fuel et HUD V6+
restent dans des modules non activés, hors navigation du socle.

Le dossier donne toute la vision, mais distingue CODÉ, INTERFACE, À RACCORDER et
FUTUR. « Codé » ne veut pas dire « déployé ». Fournis un mode démonstration séparé
avec les fixtures fictives fournies et un mode réel configurable. Ne remplace
jamais une erreur API par un succès fictif. En cas de manque, liste précisément
le contrat attendu et laisse la fonction non raccordée.

Stack : conserve la stack frontend existante si un projet est fourni ; sinon
Android Kotlin/Jetpack Compose est la cible du projet. Si l'environnement de
génération ne produit que du web, livre une interface responsive tablette/téléphone
et documente les capacités natives non disponibles sans simuler GPS en arrière-plan,
MediaProjection ou overlay système. Une PWA ne devient pas automatiquement un
service Android natif. Aucun choix de framework n'autorise à déplacer le cerveau
métier dans le client.

Design : teal sombre/cyan du document 04, composants lisibles, une action
principale en conduite, états pending/syncing/synced/failed/conflict/cache daté.
Téléphone en colonne, tablette à l'arrêt avec panneau de détail, conduite sans
sidebar. Tous les champs restent utilisables avec zoom texte et clavier français.

Scoring de course : vert/rouge uniquement quand le serveur les renvoie, blanc
pour présence et aucun verdict si signal nul. Aucun troisième verdict jaune.
Aucune explication narrative en direct de course. Les recommandations de zone
conservent leur raison courte. Source actuelle rules_only ; aucun CatBoost actif
inventé, même si le compteur de collecte affiche une phase autonomous.

Intégration : utiliser contracts/openapi.json, forms.md et endpoints.md. Base
/api/imperium/vector. Auth bearer, refresh protégé, montants en centimes entiers,
dates ISO timezone-aware. Idempotency-Key stable et versions selon document 05.
Respecter 400/401/403/404/409/422/429/5xx. Lire les erreurs métier non déclarées
exhaustivement dans OpenAPI. Aucun double revenu entre outcome et manual-revenue.

Hors ligne : drafts persistés, aucune clôture canonique locale, aucun score
stratégique local, aucune fausse réussite. Les réponses serveur gagnent lors d'un
conflit visible. Voix = collecte/transcription à vérifier ; pas une transaction
implicite. Permissions progressives, refus géré avec saisie manuelle à l'arrêt.

Commence par l'arborescence et les adaptateurs API/mock, puis les parcours réels.
Écris ou mets à jour les tests correspondant à chaque fonctionnalité/correction.
Applique la recette du document 09 et ne casse aucun test existant. Fournis le code
frontend, les instructions de lancement, la configuration sans secrets, les
résultats de tests et la liste courte des capacités restant à raccorder.

Ne fais aucun commit sauf instruction explicite ultérieure.

---
