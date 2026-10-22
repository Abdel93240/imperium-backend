# Hors réseau, voix, permissions et confidentialité

L'app conserve une intention utilisateur sans créer une vérité concurrente. État local : draft → pending → syncing → synced ; sorties failed, conflict ou cancelled. Conserver identifiant local, type action, corps exact, clé idempotente, date appareil, tentatives, dernière erreur et identifiant serveur si reçu.

Cache : valeur, fetched_at, date métier retournée, utilisateur et statut périmé. Jamais « à jour » sur la seule base d'un timestamp local. Les opérations en attente sont une section distincte des chiffres confirmés. Après redémarrage, aucune perte de montant ni génération d'une deuxième clé pour le même envoi.

Reprise réseau : backoff borné pour erreurs transitoires et routes réellement idempotentes ; arrêter sur validation 422, lire puis résoudre 409, reconnexion sur 401. Rejouer exactement le corps et la clé. Voir doc 05 pour routes sans garantie de déduplication. Ne pas vider les brouillons en déconnectant sans prévenir ; les isoler et chiffrer selon le compte/appareil.

## Voix

Objectif : « Ajoute 45 euros de carburant en espèces ». Chaîne attendue : capture audio → transcription_service → extraction structurée backend → formulaire prérempli → validation utilisateur → transaction. Aucun appel direct du frontend à un modèle cloud, aucune transaction depuis une transcription ambiguë non confirmée.

Aucun endpoint Vault vocal dédié n'est attesté dans l'export. Prévoir un adaptateur de saisie vocale désactivé tant que le contrat de capture/transcription central n'est pas confirmé. Une dictée système dans le champ texte peut être offerte comme aide de saisie explicite, sans la présenter comme ce pipeline connecté. Toujours proposer le formulaire manuel.

## Permissions et données

Caméra au déclenchement du scan ; sélecteur système pour les fichiers ; microphone au lancement volontaire de capture si raccordé. Refus → accès manuel utilisable. Aucune permission localisation, banque, contacts, accessibilité système ou notifications Bolt requise par Vault.

Pas de secrets dans les exemples ou logs. Pas de montants, images, notes, tokens ou destinations sadaqa envoyés à un outil d'analytics. Chiffrer stockage sensible et cache local si persistant ; effacer copies temporaires après traitement selon politique, garder un brouillon non envoyé tant que l'utilisateur en a besoin. Les justificatifs confirmés restent sous la politique backend. Ne pas offrir un bouton « tout supprimer du serveur » sans API de rétention correspondante.

Notifications sobres : intitulé minimal sur écran verrouillé, contenu financier masqué si possible ; jamais « enregistré » avant acquittement backend. Pas de rappels culpabilisants. Les règles de rétention restent celles de la documentation centrale, sans durée inventée ici.
