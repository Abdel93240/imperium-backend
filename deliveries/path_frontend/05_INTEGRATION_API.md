# 05 — Intégration API

Base URL configurable. Préfixe réel : `/api/imperium/path`. `contracts/openapi.json` contient les schémas exacts du checkout du 24 octobre 2026 ; générer les DTO réseau à partir de ce fichier et conserver les modèles UI séparés. Le backend peut évoluer pendant la génération : comparer le snapshot à l'instance cible avant branchement final.

## Auth et appels

`POST /api/auth/login`, `/refresh`, `/logout` figurent dans le contrat. Bearer token sur les routes protégées. Conserver les tokens dans le stockage protégé Android, jamais dans les logs. Une seule opération de refresh à la fois ; en cas de 401 persistant, reconnexion et conservation des brouillons.

Une action mutante envoie `Idempotency-Key` stable pour ses retries, y compris POST, PATCH et DELETE selon la règle produit. La même clé ne doit jamais accompagner un corps différent. Plusieurs routeurs refusent explicitement son absence avec 400 même si OpenAPI la présente comme facultative. Les versions lues (`version`, `base_version`, `state_id`, `expected_count`) servent aux modifications concurrentes.

## Matrice métier

Tous les chemins sont relatifs à `/api/imperium/path`.

| Domaine | Lecture | Écriture |
|---|---|---|
| Dashboard | `GET /dashboard?day=` | aucune |
| Prières | `GET /prayers?day=` | `POST /prayers/{prayer_name}/mark`, `/clear` |
| Jeûne | `GET /fasting/state`, `GET /fasts` | `POST /fasts`, `/fasts/{id}/end`, `/break`, `/cancel` |
| Sadaqa | `GET /sadaqa/settings`, `/summary?week_start=`, `/donations` | `PATCH /sadaqa/settings`, `POST /sadaqa/donations`, `/donations/{id}/vault-retry`, `DELETE /donations/{id}` |
| Ghusl | `GET /ghusl`, `/ghusl-addresses` | `POST /ghusl/activate`, `/ghusl/complete`, `POST/PATCH/DELETE /ghusl-addresses` |
| Adhkar | `GET /adhkar/suggestions`, `/adhkar/routines` | `POST/PATCH/DELETE /adhkar/routines`, `POST /adhkar/routines/{id}/increment`, `/reset` |
| Coran | `GET /quran/continuation` | `POST /quran/progress`, `/quran/khatm`, `/quran/plans`, `/quran/plans/{id}/stop`; `PATCH /quran/objective` |
| Invocations | `GET /invocations`, `/invocations/daily?day=` | `POST /invocations`, `PATCH /invocations/{id}`, `/{id}/favorite`, `POST /{id}/check`, `DELETE /{id}` |
| Mosquées | `GET /mosques`, `/mosques/{id}?day=` | `POST /mosques`, `PATCH/DELETE /mosques/{id}` |
| Réglages | `GET /settings` | `PATCH /settings` |
| Calendrier | `GET /calendar/hijri?day=`, `/calendar/events`, `/calendar/personal-events` | `POST /calendar/confirm-date`, `/calendar/personal-events`, `DELETE /calendar/personal-events/{id}` |
| Habitudes legacy | `GET /today`, `/stats/summary`, `/habits`, `/habits/{id}`, `/check-ins`, `/check-ins/{id}` | `POST /habits`, `/habits/{id}/archive`, `/reactivate`, `/habits/{id}/check-ins` |

`contracts/endpoints.md` énumère chaque route précise ; `openapi.json` fixe les champs et réponses.

## Formats et conflits

- Les montants de don sont des entiers `amount_cents` ; les agrégats de sadaqa sont des `Decimal` JSON à parser sans float pour les calculs d'affichage.
- Dates de suivi : jour de Paris (`YYYY-MM-DD`). Horodatages : ISO 8601 avec fuseau. UUID opaques.
- `PrayerMarkRequest` : `prayer_date`, statut `accomplished` ou `not_marked_as_accomplished`, `prayed_at`/`note` facultatifs, `base_version` pour changer une ligne existante.
- `FastBreakRequest` et `FastCancelRequest` demandent `confirm: true`. `GhuslCompleteRequest` demande `state_id`.
- Le réglage sadaqa a `base_version` et une application au lundi suivant par défaut. Un second changement hebdomadaire requiert une confirmation après `SADAQA_SECOND_CHANGE`.
- `QuranProgressRequest` accepte exactement un de `page`, `surah`, `juz`. Une régression exige `confirm_regression` après 409.
- `AdhkarIncrementRequest` avec `source=voice` exige `confidence` ; les faibles confiances doivent être validées par l'utilisateur.
- Un 409 renvoie parfois `current` : le montrer, recharger, et demander une nouvelle confirmation. Ne pas rejouer aveuglément une modification.
- 422 : erreurs de champs ; 429 : attendre ; 5xx/timeout : action incertaine, vérifier par lecture avant de créer une nouvelle clé.

L'API Path n'expose aucune route d'upload vocal, de recherche/sync réseau MAWAQIT, de configuration de rappels ou de score Path. Ne pas appeler les endpoints hypothétiques `/api/path/*` des anciens documents.
