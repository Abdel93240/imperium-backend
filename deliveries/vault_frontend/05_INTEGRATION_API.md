# Intégration avec le backend existant

La source machine est `contracts/openapi.json`. `endpoints.md` énumère chaque méthode/paramètre et `forms.md` chaque schéma. Export fait à partir des routeurs Python sans démarrage applicatif ni appel à la base. Les erreurs métier ne sont pas toutes déclarées dans OpenAPI : traiter aussi 400, 401, 403, 404, 409, 413, 422, 429 et 5xx.

## Familles

| Usage | Préfixe réel |
|---|---|
| Registre, résumé, catégories, tickets | `/api/imperium/vault` |
| Pression, échéances, relevés, réglages, résumés hebdo | `/api/vault` |
| Connexion, renouvellement, déconnexion, appareils | `/api/auth` |

Paramétrer l'URL HTTPS du backend par environnement ; le serveur ZIP provisoire n'est pas l'API. Authentification Bearer selon securitySchemes et auth DTO exportés. Utiliser le compte/appareil déjà configurés ; pas d'inscription SaaS. Session expirée : renouvellement centralisé une seule fois, sinon reconnexion ; garder brouillons mais ne pas rejouer automatiquement une écriture dont l'issue est incertaine. Stockage sécurisé des tokens, aucune clé dans l'application ou les exemples.

## Montants, dates et modèles

Transactions et relevés utilisent des centimes entiers. Les échéances `amount`, les résumés hebdomadaires et daily_targets utilisent Decimal en EUR, généralement sérialisé en chaîne JSON. Respecter le type de chaque champ. `45,20` saisi → 4520 centimes, ou `"45.20"` pour un champ Decimal. Interdire zéro/négatif pour un gain ou une dépense ; exception du solde banque réel qui peut être négatif.

occurred_at doit inclure un décalage horaire ; envoyer timezone IANA connue, afficher local_date retourné par le backend. Ne pas convertir une simple date due_date ou week_start avec un fuseau implicite. Les bornes occurred_from et occurred_to sont inclusives dans les services : éviter de compter deux fois minuit entre périodes contiguës. La granularité et le fuseau mensuel doivent être vérifiés au branchement ; ne pas promettre qu'ils sont identiques à la semaine local_date.

DTO transaction : transaction_type, amount_cents, currency EUR, wallet, occurred_at, timezone?, category?, source?, note?, external_ref?. Pas de book. Réserver external_ref aux liens métier validés ; ne pas fabriquer une référence de session Vector. Le schéma interdit les champs supplémentaires.

## Idempotence et limites de reprise

Clé UUID stable par intention utilisateur pour les écritures qui la supportent : création transaction, reverse, correct, upload/validation ticket, relevé, mark-paid et création correction de pression. Timeout : conserver clé et corps exacts. Nouvelle intention ou saisie modifiée : nouvelle clé après résolution de l'état précédent. 201 ou 200 peuvent être un succès ; une réponse HTTP 200/201 d'OCR doit encore être lue pour son status métier.

Écart actuel important : création échéance, confirmation catégorie, annulation extraction et révocation correction n'exposent pas tous une Idempotency-Key avec garantie de déduplication. Envoyer un header supplémentaire n'ajoute aucune protection. Pas de rejeu automatique illimité de ces mutations. Désactiver le double appui, relire si possible après une réponse perdue ; sinon garder « résultat à vérifier » et demander une action explicite. PATCH d'échéance n'expose pas de version optimiste.

## Tickets : complément non déduit d'OpenAPI

`POST /api/imperium/vault/receipt-extractions?entry_app=vault` : corps = octets du fichier, headers Authorization, Idempotency-Key, Content-Type du média, X-Filename encodé URL. Maximum 25 × 1024 × 1024 octets, pas de fichier vide. Formats acceptés à vérifier dans le validateur média courant (photo ou PDF selon support) ; ne pas promettre HEIC si non pris en charge. L'appel OCR est synchrone et peut durer environ 60 secondes : chargement réel, timeout réseau adapté, récupération GET par identifiant dès qu'il est connu. Pas de polling de job inventé.

GET extraction retourne brouillon et status. GET image nécessite l'auth ; charger en mémoire privée et libérer au départ. POST validate envoie le total vérifié, date aware, catégorie, wallet, note et stock_lines. Le frontend n'appelle PAS Pulse pour recréer les mêmes aliments. POST cancel conserve une trace et supprime le média selon règles backend ; l'image validée reste un justificatif.

## Lecture et invalidation

Pagination du registre : limit 1–200, offset ≥ 0, count = nombre de lignes retournées sur cette page. Filtres serveur disponibles : type, catégorie, source, dates. Pas de paramètre book, wallet ou recherche textuelle globale dans cette liste. Charger les agrégats par endpoints dédiés, jamais en additionnant la page visible. GET settings est lecture seule, pas de PATCH settings réel.

Après transaction confirmée : invalider liste/détail, summary, categories summary, monthly, wallet et pression affichée. Ne pas supposer que weekly-summaries est recalculé immédiatement : afficher computed_at. Après mark-paid : relire échéances et mêmes cartes ; après snapshot : relire wallet/pression ; après correction : relire état serveur. Ne pas marteler GET pressure : le handler effectue un calcul, il n'est pas une horloge live.

Les événements internes finance.* ne prouvent pas l'existence d'un WebSocket/SSE public. Prévoir rafraîchissement à l'ouverture, à la demande et après mutations. Notifications backend dépendent du runner, pas d'un moteur de calcul recréé dans l'app.
