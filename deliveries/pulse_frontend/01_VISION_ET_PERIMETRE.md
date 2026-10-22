# Vision et périmètre

## Le rôle de Pulse

Pulse aide son utilisateur à manger avec ce qu'il possède, boire, suivre ses
séances et observer son évolution physique. La perte de poids et l'objectif
d'abdominaux visibles sont des objectifs personnels, jamais une promesse de résultat.
Le suivi doit rester pratique pendant de longues journées de VTC.

Le frontend affiche, recueille, explique et transmet. Le cerveau commun décide :
API FastAPI, PostgreSQL, mémoire sémantique et orchestration backend. Il ne faut
pas reconstruire un moteur de santé, un planificateur ou un routeur IA dans l'app.
Imperium arbitre la journée et conserve l'unique mission active.

## Trois niveaux de livraison

| Niveau | Contenu | Traitement frontend |
|---|---|---|
| Socle utilisable | Repas, hydratation, stock, séances, matériel, saisies, mesures, douleurs, documents et règles manuelles | Brancher les contrats existants, tester contre l'environnement choisi |
| Codé sous conditions | OCR, signaux, sentinelle, propositions P1, programmes et métriques | Prévoir désactivation, absence de données, dry-run et erreurs ; activation serveur seulement |
| Cible produit | Recettes, plan nutritionnel, courses, batch cooking, programme IA, analyses médicales, montre | Décrire et maqueter séparément ; aucun appel inventé ni succès simulé en mode réel |

La présence d'une route n'atteste ni les migrations appliquées ni l'activation
des traitements. Aucun état de production n'a été modifié pour fabriquer ce kit.

## Règles de produit

- Une seule mission active, gérée par Imperium.
- Aucun score santé sans ses explications et sa confiance. Actuellement `health_score=null`.
- Une absence de donnée reste inconnue, jamais transformée en zéro.
- Les estimations alimentaires sont modifiables et deviennent canoniques après validation.
- L'énergie est déclarée ; le frontend ne la déduit pas du sommeil ou du sport.
- Les repas ne déclenchent pas de culpabilisation, badges punitifs ou classement social.
- Un document médical ne constitue pas un diagnostic de Pulse.
- Une proposition acceptée n'est appliquée qu'après réponse confirmée du backend.
- Les appels IA externes et les droits sensibles suivent les validations du backend.
- Aucune connexion Bolt ni automatisation VTC dans Pulse.

## Priorité de réalisation

1. Client API, connexion, stockage sécurisé des jetons, gestion des erreurs.
2. Accueil, repas manuels, eau et stock.
3. Séances, matériel, historique, sommeil et énergie.
4. Consentements, mesures, douleurs, documents et règles.
5. Signaux, propositions et programmes selon activation.
6. Voix, OCR et « Nourrir l'IA » lorsque leurs dépendances sont disponibles.
7. Fonctions futures dans un mode démonstration explicitement séparé.

Les réglages du compte, la revue hebdomadaire et l'arbitrage de la journée restent
partagés avec Imperium. Pulse peut y mener l'utilisateur, sans dupliquer ces moteurs.
