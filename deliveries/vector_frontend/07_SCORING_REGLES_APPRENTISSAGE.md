# 07 — Scores, règles personnelles et apprentissage

## Sortie de course

La cible produit est binaire : vert = rentable, rouge = non rentable. Blanc =
assistant actif/en ligne, pas verdict. L'absence de contexte décisif peut entraîner
une abstention : « Haute incertitude, à toi de juger. » Ne pas créer un troisième
verdict jaune ni convertir un signal nul en vert par défaut.

En temps réel, halo + son, sans explication narrative générée. Les explications
de course après coup appartiennent à la revue et à l'historique. La recommandation
de zone conserve sa raison courte, c'est une fonction distincte (doc 33 §5).

## État codé à la livraison

Les offres manuelles calculent des features et appliquent les règles existantes.
`signal` vaut green, red ou null ; `signal_source` vaut actuellement `rules_only`.
`signal_reason` et `triggered_rules` servent au détail à l'arrêt. Aucun modèle
CatBoost entraîné n'est branché ici. L'UI affiche « Règles métier » si elle montre
la source, et non « IA autonome ». Le frontend ne reproduit pas les règles pour
combler un timeout.

`training-summary.phase` dépend du volume de résultats : `cold_start`,
`transition`, `autonomous`. Même `autonomous` ne prouve pas qu'un modèle est
entraîné ou déployé : le message courant précise que le modèle ne l'est pas.
Ne pas afficher une précision de 90 %, un statut d'entraînement ou une barre de
progression temporelle sans source serveur correspondante.

## Règles du projet

| Règle | Intention produit | Implémentation observée |
|---|---|---|
| R1 | Éviter le 8e | CODÉ : pickup ou destination 75008 → rouge |
| R2 | Éviter 18e/19e en journée | CODÉ : pickup 75018/75019, daytime → rouge |
| R3 | Limites de repositionnement de jour | Géographie manquante |
| R4 | Repositionnement après attente prolongée | Non codé ; ce n'est pas du scoring de course |
| R5 | Stratégie nightlife 01h–04h | Flux/géographie manquants |
| R6 | Fins de soirée et flux périphérie 04h–05h | Contexte externe manquant |
| R7 | Retour Paris la nuit | CODÉ via préfixe postal destination 75 et créneau |
| R8 | Course programmée la nuit | CODÉ via type scheduled et créneau |
| R9 | Budget mode destination | Non codé ; compteur à prévoir, pas une limite Bolt certifiée |
| R10 | Demande aéroport après débarquement réel | Non codé ; ne pas confondre atterrissage et demande |
| R11 | Écart durée annoncée/réelle appris | Non codé ; pas de multiplicateur fixe inventé |

Lire les valeurs effectives dans GET rules. Ne pas recopier les conditions de
ce tableau en moteur local. L'utilisateur peut modifier actif/ferme/conditions
avec motif et version. Si les données de la règle ont changé, afficher le conflit.
Aucune règle nouvelle n'est créée à partir d'une phrase libre dans cette V1.
Les périmètres et valeurs sont des règles personnelles du projet, pas des vérités
générales sur les zones ou des règles actuelles garanties d'une plateforme.

## Recommandation de zone actuellement codée

Historique de revenus par zone sur 90 jours, créneau heure ±1 et type de jour
semaine/week-end (Paris). Au moins 5 courses dans 2 sessions pour comparer une
zone. Transactions annulées exclues. Si aucune zone comparable : abstention ;
si meilleure zone actuelle ou amélioration <15 % : rester ; sinon changer de zone.
Confiance plafonnée à 0,6. Les événements, trains, aéroports et trafic ne sont pas
lus par cet algorithme actuel ; `missing_context` et la raison le signalent.

Pas de taux horaire par zone puisque le temps passé n'est pas mesuré. Les seuils
ci-dessus expliquent le résultat pour la transmission, ils ne doivent pas être
implémentés dans le frontend.

## Cible d'apprentissage

Revenu horaire objectif = gain réel / temps total mobilisé à la minute :
approche + attente + course + retour estimé. Saisir les durées réelles quand
connues ; ne pas remplacer une absence d'information par un zéro présenté réel.
Le contrat autorise certains zéros par défaut : le formulaire doit les rendre
visibles et confirmer ce que l'utilisateur a renseigné.

Les décisions acceptée/refusée/manquée restent des données comportementales.
Les refus ne sont pas la cible d'entraînement : ils peuvent refléter des raisons
personnelles hors de la rentabilité. L'état médical ou la fatigue ne devient pas
une feature du score. WR peut analyser les écarts dans son propre domaine, puis
proposer des corrections VTC supervisées et validées.

## Évolution ciblée

CatBoost côté backend pour les courses ; `local_executor` pour tri, résumé et
micro-tâches hors chemin critique. Rôles cloud et noms concrets restent gouvernés
par doc 30, aucun choix de modèle dans l'app. Son d'offre → capture autorisée →
OCR rapide → itinéraires/features → scorer côté VPS est la décision documentée
de juin. Ne pas appeler un service externe de cartographie à chaque offre depuis
le client ni annoncer un temps de réponse garanti avant mesure réelle.
