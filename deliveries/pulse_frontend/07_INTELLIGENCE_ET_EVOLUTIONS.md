# Intelligence et évolutions

## Ce que le frontend affiche

Les calculs et décisions appartiennent au cerveau commun : totaux, contraintes,
signaux, règles, propositions. Le frontend peut formater et filtrer les données ;
il ne doit pas définir de seuils médicaux ou décider qu'une séance est sûre.
`local_executor`, `transcription_service`, `ocr_service` et les rôles cloud sont
choisis par le backend. Aucun nom de modèle concret dans la logique frontend.

La sentinelle relève des situations et déclenche un traitement selon les règles
serveur. Le board explique valeur, fraîcheur et bande. Une valeur périmée ne
devient pas un signal normal par absence de mise à jour. Les propositions ne sont
affichées que lorsqu'elles sont présentées à l'utilisateur ; les essais dry-run
restent techniques.

## Les dix procédures prévues

| Procédure | Surface utilisateur | Situation au moment de l'export |
|---|---|---|
| P1 Adaptation séance | Proposition, accepter/refuser/modifier, effets sur séance/programme | Étapes codées, sous activation |
| P2 Changement alimentaire | Objectif, compatibilités, incertitudes, transition à valider | Cible, pas de flux complet branchable |
| P3 Nouveau programme | Collecte objectifs/contraintes, programme proposé puis validé | Création manuelle disponible ; génération IA cible |
| P4 Blessure/douleur | Contraintes de mouvement et adaptations proposées | Journal de douleur disponible ; procédure cible |
| P5 Document médical | Extraction de champs, corrections, source et contre-lecture | Stockage/règles manuelles disponibles ; extraction cible |
| P6 Réconciliation hebdomadaire | Bilan du réel, alimentation suivante, courses et préparation | Cible, intégration à la revue commune |
| P7 Révision mensuelle | Progression, phases, programme révisé à accepter | Cible |
| P8 Revue scientifique | Changements de références/paramètres à valider | Cible secondaire, pas un écran quotidien |
| P9 Exploration | Proposition d'expérience limitée et suivie | Cible |
| P10 Référence manquante | Acquisition d'une fiche, source puis validation | Cible |

Dans le runner actuel, les procédures autres que P1 s'arrêtent comme non codées.
Ne pas créer des écrans qui prétendent avoir achevé ces traitements.

## P1 : adaptations actuellement pertinentes

Le backend génère les coups autorisés à partir de la situation actuelle :
maintenir, décaler dans la journée, reporter, et selon le programme réduire le
volume, changer de modalité ou rembourser une dette. Le fractionnement et la
semaine allégée ont encore des limites d'implémentation.
Ne jamais afficher toutes ces options comme nécessairement disponibles.
Les versions, contraintes horaires, jeûne et blocages sont revérifiés à la décision.

## Nutrition complète à préparer

Recettes : catalogue personnel, capture légère, adaptations validées. Une recette
ajoutée ne constitue pas à elle seule une recommandation de régime.
Menus : semaine construite à partir des objectifs, du stock réel, des recettes
et des contraintes validées. Afficher provenance, hypothèses et portions.
Courses : manquants issus des menus ; les achats réellement enregistrés diminuent
la liste, les articles non achetés restent. L'utilisateur garde ses choix.
Batch cooking : mission de préparation gérée par Imperium, décompte des ingrédients
et création de portions après confirmation. Expliquer stockage et dates à partir
des informations backend, sans règle alimentaire inventée.

Ces vues peuvent être préparées en maquette isolée. Une API et des tests backend
doivent exister avant leur branchement réel.

## Sommeil, récupération et montre

Le journal manuel fonctionne sans capteur. Les connexions montre et les features
dérivées sont une extension. Ne pas afficher un faux rythme cardiaque, une
récupération estimée ou une dette de sommeil calculée dans le frontend.
Les scores futurs doivent avoir source, fraîcheur, confiance et explication.

## Liens avec l'écosystème

Imperium reçoit les contraintes utiles et arbitre la journée. The Path fournit
les périodes de jeûne via le backend. The Vault alimente le stock depuis les
tickets validés et la réalité financière utile aux futures recommandations.
Vector ne reçoit pas de score d'énergie via Pulse. Le frontend ne construit
aucun dialogue direct app-à-app pour produire une décision.
