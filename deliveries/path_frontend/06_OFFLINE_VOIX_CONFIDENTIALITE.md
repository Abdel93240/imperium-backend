# 06 — Offline, voix et confidentialité

## Offline

Le cache local ne contient que les réponses nécessaires à la lecture rapide et des brouillons d'actions explicites. Chaque snapshot affiche `mis à jour à…`, la source et le statut. Pour les horaires MAWAQIT, le backend expose la qualité `fresh/stale/expired/missing` : au-delà de 48 h, le calcul devient principal. Le client ne prolonge pas la fraîcheur lui-même.

File de synchronisation : `pending → syncing → synced` ou `failed/conflict`. Une action garde sa clé d'idempotence, sa cible, son corps et sa version lors des retries. Ne pas transformer un brouillon offline en « accompli » canonique. Les corrections de statut, reset adhkar, don et action de jeûne conflictuels attendent une nouvelle décision utilisateur. Après reconnexion, lire l'état serveur avant toute relance ambiguë.

Le calendrier hégirien prédit reste explicitement prédit en cache. Pour les dates religieuses sensibles, ne pas afficher une date prédite comme confirmée. La qibla issue d'un ancien lieu est signalée comme telle.

## Voix

Prévoir le point d'entrée vocal pour les gestes courts lorsque le pipeline commun `transcription_service` sera raccordé. En V1, aucune route Path STT spécifique n'existe : afficher « indisponible » ou garder une saisie manuelle. Jamais d'enregistrement silencieux, de validation par transcription seule ni de texte inventé par l'IA. Pour un compteur adhkar, `source=voice` ne part qu'après relecture du nombre ; transmettre la confiance et `validated` si l'utilisateur a confirmé.

## Vie privée

Prière, jeûne, ghusl, adresses et mosquées sont sensibles. Minimiser leur stockage local, chiffrer les données persistées, les effacer à la déconnexion de l'appareil, ne jamais les inclure dans analytics, crash logs, notifications écran verrouillé ou URLs de partage. GPS à permission ponctuelle pour recherche de mosquée, qibla ou distance demandée ; aucun suivi continu. La saisie manuelle doit toujours fonctionner sans GPS. Les appels à un modèle externe passent par la privacy gate backend prévue ; le frontend ne décide pas seul d'envoyer ces données.
