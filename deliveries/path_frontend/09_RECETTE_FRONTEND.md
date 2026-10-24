# 09 — Recette frontend

Exécuter avec des fixtures fictives et contre l'API d'intégration autorisée. Dans le projet Android généré, ajouter des tests unitaires de ViewModel/repository et des tests d'interface pour les parcours critiques. Les tests pytest existants du backend restent la porte CI pour toute évolution serveur.

| Scénario | Résultat attendu |
|---|---|
| Dashboard sans données personnelles | cinq horaires/source, états non définis neutres, cartes vides utiles ; aucun succès inventé |
| Marquer Fajr puis renvoyer la même requête après timeout | une seule action canonique ; même clé et même corps ; statut relu |
| Modifier une prière depuis une ancienne version | 409 affiché avec état actuel ; nouvelle confirmation nécessaire |
| Horaires MAWAQIT vieux de 49 h | calcul principal, cache historique averti ; ne pas montrer le vieux cache comme horaire fiable |
| Démarrer un jeûne, puis ouvrir Pulse | contrainte lue du backend, aucune intention inférée par Pulse |
| Rompre ou annuler un jeûne | confirmation distincte ; raison facultative pour rupture ; pas de changement avant réponse |
| Faire un don avec Vault indisponible | don Path confirmé ; `vault_status=pending`, bouton retry, aucun second don |
| Modifier le pourcentage sadaqa deux fois dans la semaine | changement différé ou 409 explicite ; confirmation de second changement si proposée |
| Activer ghusl sans jour Imperium ouvert | état Path confirmé, `replan_status=no_open_day` visible ; pas de mission inventée |
| Appuyer plusieurs fois sur +1 adhkar hors ligne | chaque appui a sa clé ; état pending ; reset sur compte périmé provoque résolution de conflit |
| Saisir page Coran inférieure à la page validée | confirmation de régression ; conservation du point courant si refus |
| Marquer Khatm avant page 604 | bouton absent/inactif ; aucune requête envoyée |
| Invocations matin/soir avec favoris | progression quotidienne et favori indépendants ; arabe RTL, traduction et source lisibles |
| Événement hégirien prédit puis confirmé | deux dates candidates avant ; une après relecture ; aucune date prédit-e affichée comme certaine |
| Refus GPS ou hors ligne | saisie manuelle mosquée/adresse possible ; qibla et cache avec provenance |
| Token expiré pendant une saisie | refresh sérialisé ou reconnexion ; brouillon préservé, token jamais affiché |
| Écran tablette et TalkBack | rail/panneau adaptés, navigation au clavier/lecteur, statuts annoncés sans couleur seule |
| Route future absente | fonction non raccordée expliquée, pas de requête vers `/api/path/*` inventée |

Critère de livraison : aucun test backend existant cassé par le frontend, aucun acte religieux confirmé localement sans réponse backend, aucun secret ou donnée sensible dans les artefacts et journaux.
