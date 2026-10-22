# Hors ligne, consentements et confidentialité

## États locaux

`pending → syncing → synced`, avec branches `failed` et `conflict`.
Un brouillon a un identifiant local séparé de l'UUID serveur.
Ne jamais montrer une écriture comme canonique avant la réponse backend.
Afficher la date de dernière mise à jour des lectures en cache.

| Action | Hors ligne | Après reconnexion |
|---|---|---|
| Repas manuel | Brouillon et confirmation en attente, ordre conservé | Créer puis confirmer ; aucun stock modifié localement |
| Eau | Un élément de file par appui volontaire | Même clé pour retry, différentes clés pour différents appuis |
| Séance en cours | Progression locale et minuterie | Vérifier le statut serveur avant terminer/passer |
| Stock | Brouillon de modification avec version initiale | PATCH ou conflit, pas d'écrasement silencieux |
| Mesures | Mesures numériques en file, consentement connu | Le serveur revérifie le consentement |
| Douleur | Brouillon conservé | Enregistrer ; éventuelle replanification séparée et explicite |
| Adaptation | Lire une proposition en cache avec date | Décision en ligne après relecture ; elle peut être périmée |
| Upload médical | Pas d'envoi en file automatique V1 | Reprendre avec consentement actuel et accord d'envoi |
| OCR photo | Photo locale temporaire seulement si nécessaire | Envoi volontaire, puis purge du temporaire |
| Suppression sensible | Confirmation requise | Effectuer en ligne et confirmer le résultat |

La file ne suppose pas que tous les endpoints sont idempotents. Pour les routes
sans garantie contractuelle, bloquer le retry automatique après un résultat
réseau ambigu jusqu'à relecture. Purger les caches sensibles lors d'une
déconnexion conformément au choix produit et isoler les brouillons du compte.

## Consentements

Trois domaines indépendants : `body`, `pain`, `medical`.
Afficher `text_fr` et mémoriser le `text_version` lu. L'utilisateur accepte
explicitement. Un changement de texte renvoie un conflit : montrer la version
actuelle, ne pas accepter silencieusement à sa place.

Le retrait interdit de nouvelles écritures concernées ; les lectures et
suppressions restent possibles. Fournir des actions distinctes « Retirer mon
accord » et « Supprimer mes données ». Un consentement général ne vaut pas
permission d'expédier n'importe quelles données à un fournisseur externe.

## Médias et stockage

Photos corporelles : strictement locales, aucun champ photo dans les requêtes.
Photos de repas/placard : extraction puis non-conservation côté backend ;
supprimer les copies temporaires frontend devenues inutiles.
Documents médicaux : rétention affichée depuis la réponse serveur. La politique
actuelle prévoit 90 jours, mais son exécution dépend du job de rétention activé :
ne pas annoncer une suppression effectuée sur la seule base d'un compte à rebours.

Ne pas journaliser mesures, douleurs, texte médical, fichiers, transcriptions,
jetons ou payloads de consentement dans l'analytics/crash reporting.
Éviter les aperçus médicaux dans les notifications et les captures automatiques.
Les données brutes d'une future montre restent hors prompts IA.

## Suppression et effets

Avant une suppression collective, afficher le domaine et le périmètre exact.
La suppression manuelle d'un document médical supprime aussi ses règles dérivées
selon l'implémentation actuelle ; prévenir l'utilisateur. Le nettoyage automatique
de rétention a une sémantique différente décrite dans l'annexe médicale.
Les événements d'audit ne doivent pas être reconstruits ou modifiés par l'app.
