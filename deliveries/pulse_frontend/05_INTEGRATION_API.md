# Intégration API

## Source exacte

`contracts/openapi.json` exporte toutes les routes Pulse et les routes partagées
d'authentification et de connaissance sélectionnées. Les références de schéma
sont complètes. `endpoints.md` énumère méthode, URL, paramètres et réponses ;
`forms.md` expose les propriétés, types, contraintes et champs requis.

La base d'URL de l'environnement reste configurable. Le chemin Pulse est
`/api/imperium/pulse`, jamais `/api/pulse`. Aucun hostname, identifiant ou jeton
de production n'est nécessaire pour générer le frontend.

## Authentification

Utiliser les contrats `/api/auth/login`, `/refresh`, `/logout` et appareils de
confiance inclus. Respecter leurs champs exacts, notamment l'identité appareil.
Envoyer `Authorization: Bearer <access_token>` aux routes protégées.
Stocker les secrets dans le stockage sécurisé de la plateforme ; pas dans les
logs, URLs ou fichiers de maquette. Les routes de login/refresh délivrent
normalement les jetons : ne pas les afficher dans les écrans métier.

Sur 401 : tenter le renouvellement selon contrat, une seule requête de refresh
à la fois ; sinon demander une reconnexion en conservant les brouillons.
Ne pas réessayer automatiquement une mutation avec un nouveau corps/une nouvelle clé.
L'app est personnelle ; aucun écran d'inscription publique, équipe ou abonnement.

## Écritures et conflits

Envoyer un UUID stable en `Idempotency-Key` pour chaque intention de mutation.
La clé et le corps sont conservés dans la file locale pour les retries.
Les contrats historiques n'imposent pas tous ce header et ne garantissent donc
pas tous une déduplication : voir le paramètre « Idempotency-Key déclaré » dans
l'inventaire. Pour une action sans déduplication explicite, relire l'état serveur
avant de permettre une relance ambiguë. Le header seul ne crée pas cette garantie.

Les PATCH stock/séance demandent leur version. Un 409 ouvre une explication ou
un conflit, jamais un « dernier arrivé gagne ». Après succès, invalider les
lectures concernées (dashboard, repas, eau, stock, séances/programme).
Les réponses de création peuvent être 201 puis 200 lors d'un rejeu.
Une suppression 204 n'a pas de JSON à décoder.

## Dates et nombres

Les journées fonctionnelles sont celles d'Europe/Paris, y compris les changements
d'heure. Envoyer les timestamps ISO 8601 avec fuseau ; dates de filtre `YYYY-MM-DD`.
Ne pas fabriquer minuit UTC pour représenter arbitrairement un jour parisien.
Les Decimal peuvent être sérialisés en chaînes ; préserver précision et unités.
Respecter les échelles propres à chaque modèle, sans normaliser l'énergie en
pourcentage ou inverser les ressentis.

## Uploads : écart important d'OpenAPI

Les handlers utilisant `Request.stream()` ne déclarent pas leur corps binaire dans
l'OpenAPI automatique. Le contrat supplémentaire obligatoire est :

| Route POST | Corps | Paramètres particuliers |
|---|---|---|
| `/api/imperium/pulse/meals/photo-drafts` | Image en corps brut | `eaten_at` optionnel |
| `/api/imperium/pulse/food-stock/scans` | Image en corps brut | Aucun corps JSON |
| `/api/imperium/pulse/medical-documents` | PDF/image en corps brut | `doc_type`, `doc_date?`, `consent=true`, `consent_version` |

Pour les trois : `Authorization`, `Idempotency-Key`, `X-Filename` encodé URL,
`Content-Type` réel ; limite actuelle 25 × 1024 × 1024 octets. Laisser la bibliothèque
HTTP calculer `Content-Length`. Ne pas envoyer de multipart/FormData.
Les images de repas/placard acceptent les extensions définies par le backend ;
un fichier illisible peut être refusé malgré son extension. Les photos corporelles
n'utilisent aucune de ces routes.

L'OCR peut prendre environ une minute : afficher attente/progression d'upload,
gérer timeout et lecture de l'état existant. Annuler l'attente côté client ne
garantit pas l'annulation du traitement serveur.
Le téléchargement médical utilise GET authentifié et doit éviter le cache partagé.

## Erreurs et états désactivés

| Cas | Traitement attendu |
|---|---|
| 400 clé manquante | Corriger le client ; conserver la saisie |
| 401 | Session/refresh/reconnexion |
| 403 `CONSENT_REQUIRED` | Ouvrir le texte du domaine concerné |
| 403 `UPLOAD_CONSENT_REQUIRED` | Redemander l'accord spécifique à l'envoi |
| 404 | Objet supprimé ou indisponible ; rafraîchir la liste |
| 409 version/idempotence | Montrer le conflit, relire avant nouvelle action |
| 409 `PULSE_BOARD_DISABLED` | Masquer l'accès actif au board, état non activé |
| 409 `PULSE_REPORTS_DISABLED` | Ressenti avancé indisponible |
| 409 `PULSE_PROGRAMS_DISABLED` | Programme indisponible ; séances simples utilisables |
| 409 `PULSE_PROPOSALS_DISABLED` | Aucune action d'adaptation disponible |
| 409 `PROPOSAL_STALE` | Proposition périmée ; recharger, ne pas appliquer |
| 409 stock/jeûne/replan | Afficher la raison renvoyée, aucune décision locale |
| 413 | Taille de fichier excessive |
| 422 | Erreur de champ, format, unité ou état ; afficher au bon endroit |
| 429 | Attendre le délai fourni, éviter le polling agressif |
| 503 / réseau | État temporairement indisponible ; conserver brouillon |

Le format des erreurs existantes varie : `detail` peut être texte, objet ou liste ;
`code` peut être à la racine ou dans `detail`. Normaliser la présentation dans
le client sans supposer une enveloppe unique. Ne pas afficher stacktrace,
identifiant de fournisseur ou détails internes à l'utilisateur.

## Interfaces partagées

« Nourrir l'IA » utilise `/api/ai/knowledge-inbox`, avec import/analyse/correction/
validation distincts. Ce flux général ne remplace pas le consentement médical.
Le flux Vault est l'origine des stocks validés depuis un ticket.
Les lectures dashboard partagent déjà les contraintes The Path ; ne pas déduire
un jeûne localement. Aucune clé de n8n, accès PostgreSQL ou fournisseur IA dans l'app.
