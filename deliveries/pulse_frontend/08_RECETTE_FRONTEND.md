# Recette du frontend à générer

Le kit contient des tests pytest d'export et du serveur temporaire. Les scénarios
ci-dessous sont la recette à implémenter avec les tests du futur frontend.
Les contrats backend existants restent couverts par leurs tests dédiés.

| Scénario | Résultat attendu |
|---|---|
| Première ouverture sans données | États vides utiles, aucune macro/mesure/score inventé |
| Connexion valide puis jeton expiré | Renouvellement unique ou reconnexion, brouillon préservé |
| Ajout repas sans macros | Brouillon, avertissement, validation possible, compteur de données manquantes |
| Ajout photo OCR indisponible | Erreur explicite, reprise texte/manuelle |
| Repas avec correspondance peu fiable | Ligne de stock décochée |
| Confirmation repas rejouée après timeout | Même clé/corps, pas de double décompte |
| Stock insuffisant sans `finish` | Conflit affiché, pas de confirmation locale |
| Deux appuis eau distincts | Deux intentions distinctes, total relu |
| Retry d'un seul appui eau | Une seule consommation confirmée |
| Hydratation sans cible | Total affiché, aucun pourcentage ou objectif arbitraire |
| Eau durant jeûne | Refus backend respecté, message visible |
| Repas déclaré pendant jeûne | Avertissement conservé, aucun jugement religieux |
| Scan placard non validé | Aucun changement canonique de stock |
| Ticket déjà validé dans Vault | Stock visible sans revalidation du ticket |
| Modification stock avec ancienne version | Conflit, relecture, brouillon préservé |
| Séance commencée puis app fermée | Progression locale restaurée, statut serveur relu |
| Exercice passé sans motif | Formulaire bloque avant envoi |
| Séance finie | Résultats envoyés, statut confirmé relu, accueil actualisé |
| Proposition acceptée | Attendre `applied`, actualiser séances/programme |
| Proposition refusée sans motif | Demander l'explication |
| Proposition périmée | Message et relecture, aucune mutation frontend |
| Fonction programmes désactivée | État désactivé, séances simples toujours accessibles |
| Aucun programme actif | État vide, pas de dette ou cibles fictives |
| Consentement absent | Texte du domaine, accord explicite, reprise de la saisie |
| Texte de consentement changé | Nouvel affichage et nouvel accord |
| Consentement retiré | Lecture/suppression disponibles, nouvelle écriture refusée |
| Mesure sans aucun nombre | Validation de formulaire |
| Photo corporelle | Aucun octet, URL ou référence photo dans une requête backend |
| Douleur et replan en cooldown | Saisie conservée, délai/raison affiché, aucune nouvelle mission |
| Upload médical sans accord d'envoi | Blocage et accord spécifique |
| Document seulement stocké | Statut importé, jamais prétendument analysé |
| Activation règle critique | Trois confirmations et acquittement critique requis |
| Acquittement alerte | Marque lue, pas résolue, blocage encore respecté |
| Suppression document | Conséquences sur règles expliquées puis résultat confirmé |
| Signal stale/no_data | Périmé/inconnu ; jamais vert par défaut |
| Valeurs Decimal, null et zéro | Aucun arrondi destructeur ; trois cas distingués |
| Minuit/changement d'heure Paris | Journées et horodatages cohérents |
| Rotation tablette / grand texte / TalkBack | Navigation, champs et actions utilisables |
| Mode démo puis mode réel | Aucune donnée fictive mélangée aux données du compte |
| Déconnexion / compte changé | Aucun cache médical exposé à une autre session |

À chaque fonctionnalité ou correction backend ajoutée pour le frontend :
écrire ou mettre à jour d'abord le test pytest correspondant dans `backend/tests/`,
puis vérifier la suite concernée et les tests existants. Aucun contournement CI.

## Conditions d'acceptation

Tous les parcours branchés ont une route existante, des champs conformes et un
retour d'erreur utilisable. Aucun bouton ne promet une fonction désactivée.
Les données de démonstration sont explicitement fictives. Les fonctions futures
ont un état indisponible ou restent hors du mode connecté.
La recette réelle doit être effectuée sur l'environnement de test désigné,
sans transformer les données personnelles de production en fixtures.
