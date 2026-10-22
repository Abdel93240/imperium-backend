# 09 — Recette et critères d'acceptation

Chaque fonctionnalité/correction implémentée doit avoir ses tests correspondants.
Le dépôt backend utilise pytest dans `backend/tests/`. Le générateur frontend
ajoute les tests adaptés à sa stack sans modifier les tests backend existants.
Le présent kit possède ses propres tests pytest de contrats/export/téléchargement.

| Cas | Action | Résultat attendu |
|---|---|---|
| T01 | Connexion valide puis token expiré | Refresh sérialisé, tokens remplacés, aucun secret visible |
| T02 | Mauvais identifiants | Erreur lisible, aucun accès fictif |
| T03 | Premier dashboard | Session absente, conseil absent, CTA démarrer |
| T04 | Démarrer sans cible | Session active, progression masquée |
| T05 | Démarrer deux fois avec même clé | Une seule session ; traiter 200 comme réussite |
| T06 | Deuxième session depuis un autre écran | 409, reprise de la session serveur |
| T07 | Gain 12,50 € | 1250 cents transmis, une transaction, KPIs serveur |
| T08 | Montant nul/négatif/trop grand | Validation locale puis serveur, pas d'envoi invalide silencieux |
| T09 | Dépense péage | category=peage, aucune deuxième transaction Vault |
| T10 | Timeout après écriture | Retry même clé et body, aucun double gain |
| T11 | Modification avec ancienne version | Conflit visible, état courant conservé |
| T12 | Recommandation sur historique insuffisant | Abstention, aucun conseil inventé |
| T13 | Conseil move_to_zone | Zone, raison, confiance et contexte manquant |
| T14 | Gain moyen 18 € par course, taux horaire null | Aucune étiquette 18 €/h |
| T15 | Conseil âgé de 20 puis 35 min | À actualiser puis obsolète ; timestamp inchangé |
| T16 | Déplacement >2 km | Conseil obsolète selon règle UI, pas de halo live |
| T17 | Retour utile envoyé deux fois | Un retour ; 409 explicite si conflit |
| T18 | GPS proposé pour dépose | Rien enregistré avant confirmation |
| T19 | Une seule coordonnée saisie | Validation empêchant latitude sans longitude |
| T20 | Clôture avec gains pending | Résoudre la file avant clôture, pas de perte silencieuse |
| T21 | Clôture confirmée | Bilan final serveur, plus de session active |
| T22 | Replan refusé par cooldown | Clôture conservée, motif/éligibilité affichés |
| T23 | Offre manuelle hors règles | Signal null, aucune fausse recommandation positive |
| T24 | Offre avec signal rules_only | Halo serveur, pas de label CatBoost actif |
| T25 | Appuyer « J'ai accepté » | Enregistre uniquement decision ; aucun contrôle Bolt |
| T26 | Résultat d'une course acceptée | Gain et temps complet ; revenu unique si record_revenue=true |
| T27 | Résultat d'une course refusée | Refus métier respecté, aucune cible ML artificielle |
| T28 | Phase autonomous mais message modèle non entraîné | Aucun badge modèle déployé |
| T29 | Modifier règle avec motif/version | Conditions serveur, conflit si édition concurrente |
| T30 | Règle dans not_coded | Indisponible, pas de règle exécutée localement |
| T31 | Hors ligne puis redémarrage de l'app | Brouillons persistés, cache daté, reprise ordonnée |
| T32 | Autorisation GPS/micro refusée | Saisie manuelle possible, pas de permission en boucle |
| T33 | Capture depuis mode API | Fonction non raccordée annoncée, aucun POST inventé |
| T34 | Mode conduite >5 km/h 5s | UI compacte ; retour sous 3 km/h 60s |
| T35 | Tablette paysage/font scale 200 % | Actions utilisables, pas de montant critique tronqué |
| T36 | Sons coupés/daltonisme/lecteur d'écran | Signal discernable autrement que par couleur |
| T37 | Erreur 500 en mode API | Erreur réelle, pas de bascule automatique sur fixtures |
| T38 | Minuit et changement d'heure Paris | Historique et durée cohérents, dates ISO conservées |
| T39 | Reconnexion après session terminée ailleurs | Aucun gain rejoué aveuglément sur la session close |
| T40 | Déconnexion et effacement brouillons | Pas de token conservé en clair ; aucune prétendue suppression ledger |

## Livraison frontend acceptable

Les 11 surfaces canoniques existent avec leurs limites. La saisie offre/résultat,
l'historique, règles et collecte sont accessibles à l'arrêt dans des sous-vues.
Tous les chemins API utilisés figurent dans le snapshot ou dans une évolution de
contrat explicitement fournie ensuite par l'IA backend. Aucune intégration future
n'est simulée en production. Fixtures identifiées « Démonstration ».

Vérifier les tests à la fois sur schémas et interactions : doublon financier,
conflit de version, abstention, restauration hors ligne et aucun contrôle Bolt.
Le frontend n'embarque ni base SQL, ni CatBoost, ni accès direct n8n, ni clé de
fournisseur. La recette réelle devra être faite sur une instance de test autorisée.
