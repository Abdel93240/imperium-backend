# AUDIT Vault — code backend ↔ docs

Date: 2026-06-27  
Scope: lecture seule du module Vault finance. Aucun code backend modifié.

## Verdict court

Verdict: **(c) divergent**.

Raison: deux ledgers coexistent et sont tous les deux branchés:

- `vault_transactions` via `/api/vault/*`, documenté précisément par `docs_master/27_VAULT_TRANSACTIONS_WORKFLOW.md`.
- `imperium_vault_transactions` via `/api/imperium/vault/*`, documenté seulement par invariants/contrats dans `docs_master/04_MVP_BACKEND_CONTRACTS.md` et `docs_master/05_DATABASE_SCHEMA.md`.

Les docs de référence demandées ne donnent pas un propriétaire unique du schéma Vault:

- `04_MVP_BACKEND_CONTRACTS.md` est le propriétaire de fait du **contrat API actif `/api/imperium/vault`** et des invariants append-only/reversal.
- `05_DATABASE_SCHEMA.md` n'est pas un vrai dictionnaire de schéma; il contient des notes/invariants.
- `11_FINANCIAL_PRESSURE_FORMULA.md` possède la logique de pression financière, pas le schéma des transactions/ledger.
- Le seul doc colonne par colonne trouvé est `27_VAULT_TRANSACTIONS_WORKFLOW.md`, mais il décrit le ledger legacy `vault_transactions`, pas le ledger Imperium récent.

Conclusion propriétaire: **aucun doc ne possède correctement le schéma Vault complet actuel**. Il faut soit promouvoir/réécrire `05_DATABASE_SCHEMA.md` comme propriétaire, soit créer un doc Vault schema dédié et déclarer `27` legacy ou le mettre à jour.

## Partie 1 — Schéma

### Table `vault_transactions`

Code:

- Migration: `backend/alembic/versions/20260426_0007_vault_transactions.py`
- ORM: `backend/app/models/vault.py::VaultTransaction`
- API/service: `/api/vault/*`, `backend/app/services/vault/transactions.py`

Doc propriétaire trouvé: `docs_master/27_VAULT_TRANSACTIONS_WORKFLOW.md`. Les docs demandées `04/05/11` ne listent pas cette table colonne par colonne.

| Colonne / invariant | Code | Doc | Écart |
|---|---|---|---|
| `id` | UUID PK | UUID PK | Conforme |
| `user_id` | UUID FK `users.id`, non null | canonical user FK | Conforme |
| `event_id` | UUID FK `events.id`, nullable | nullable FK `events.id` | Conforme |
| `occurred_at` | `DateTime(timezone=True)`, non null | transaction timestamp | Conforme partiel; doc `04` dit que `occurred_at` est la seule source temporelle autoritaire |
| `local_date` | `Date`, non null | user-local date | Conforme au doc `27`, mais tension avec doc `04` si utilisé pour filtres/summaries |
| `timezone` | `Text`, non null | user timezone | Conforme |
| `transaction_type` | `Text`, check `income/expense/correction` | `income/expense/correction` | Conforme |
| `wallet` | `Text`, check `cash/bank` | `cash/bank` | Conforme |
| `category` | `Text`, non null | required category | Conforme |
| `label` | `Text`, nullable | optional display label | Conforme |
| `amount` | `Numeric(12,2)`, check `amount > 0` | numeric `12,2`, positive | Conforme |
| `currency` | `Text`, non null, default/server default `EUR` | defaults `EUR` | Conforme partiel; pas de check DB longueur/ASCII |
| `notes` | `Text`, nullable | optional notes | Conforme |
| `source_app` | `Text`, non null, default/server default `vault` | defaults `vault` | Conforme |
| `created_at` | timestamptz, default `now()` | UTC audit timestamp | Conforme partiel; DB ne force pas explicitement UTC |
| `updated_at` | timestamptz, default `now()`, ORM `onupdate=now()` | UTC audit timestamp | Conforme au doc `27`, mais tension avec append-only/immutability des docs `04/05` |
| Index `(user_id, local_date)` | migration + ORM | documenté | Conforme |
| Index `(user_id, occurred_at DESC)` | migration utilise DESC; ORM index simple `occurred_at` | documenté DESC | Écart ORM ↔ migration |
| Index `(user_id, transaction_type)` | migration + ORM | documenté | Conforme |
| Append-only | Pas de PUT/PATCH/DELETE dans `/api/vault`; pas de trigger DB anti-update/delete | docs `04/05` disent append-only/immutable pour Vault | Invariant seulement par absence de route, pas par DB |
| Reversal | Non présent | doc `27` parle de correction positive; docs `04/05` parlent de reversal sous `/api/imperium/vault` | `vault_transactions` n'a pas le modèle reversal récent |

Invariants financiers sur `vault_transactions`:

- Montants positifs et types bornés: OK.
- Devise: API normalise uppercase et Pydantic limite à 3 caractères, mais la DB accepte tout `Text` si écriture directe.
- Weekly summary legacy: `income - expense + correction`, conforme à doc `27`.
- Temporalité: `get_weekly_summary()` filtre par `local_date`, alors que le contrat `04` affirme que `occurred_at` est la source unique pour summaries/filtres Vault V1. Écart à trancher.
- Append-only: non garanti en base. `updated_at` avec `onupdate` indique même qu'une mutation ORM future mettrait la ligne à jour.

### Table `imperium_vault_transactions`

Code:

- Migrations: `20260525_0024`, `20260525_0025`, `20260525_0026`
- ORM: `backend/app/models/vault.py::ImperiumVaultTransaction`
- API/service: `/api/imperium/vault/*`, `backend/app/services/imperium/vault.py`, `backend/app/services/imperium/vault_transactions.py`

Doc propriétaire trouvé: `04_MVP_BACKEND_CONTRACTS.md` pour le contrat/invariants, mais pas pour la liste de colonnes. `05_DATABASE_SCHEMA.md` répète des invariants. Aucun doc ne possède cette table colonne par colonne.

| Colonne / invariant | Code | Doc | Écart |
|---|---|---|---|
| `id` | UUID PK | Non listé | Présent code / absent doc |
| `user_id` | UUID FK `users.id`, non null | endpoints scoped through `CurrentUserDep` | Colonne implicite seulement |
| `transaction_type` | `Text`, check `income/expense` | docs parlent revenus/dépenses | Conforme implicite; pas de `correction` dans ce ledger |
| `amount_cents` | `Integer`, check `> 0` | Montants non spécifiés colonne par colonne | Présent code / absent doc; choix cents non documenté |
| `currency` | `Text`, default `EUR`, check `length(currency)=3` | exactement 3 lettres ASCII, normalisées uppercase | Conforme API, DB partielle: longueur seulement, pas ASCII/uppercase |
| `occurred_at` | timestamptz non null | source temporelle autoritaire UTC | Conforme intention; DB ne force pas UTC |
| `local_date` | `Date`, non null, ajouté en 0026 | `05` mentionne Europe/Paris/default date convention | Présent code / doc partielle; tension avec `occurred_at` unique autoritaire si mal utilisé |
| `timezone` | `Text`, non null, ajouté en 0026 | `05` mentionne Europe/Paris/default date convention | Présent code / doc partielle |
| `category` | `Text`, nullable | utilisé par summary categories | Présent code / peu documenté |
| `source` | `Text`, nullable | non listé | Présent code / absent doc |
| `note` | `Text`, nullable | non listé | Présent code / absent doc |
| `external_ref` | `Text`, nullable | non listé | Présent code / absent doc |
| `is_reversal` | `Boolean`, default false | reversal append-only documenté | Conforme intention |
| `reversal_of_transaction_id` | self-FK nullable | reversal linked to original | Conforme intention |
| `reversal_reason` | `String(500)`, nullable | reversal endpoint reason implied by API | Présent code / peu documenté |
| `created_at` | timestamptz default `now()` | non listé | Présent code / absent doc |
| `updated_at` | timestamptz default `now()`, ORM `onupdate=now()` | transactions immutable after insert | Tension: colonne mutable sans trigger anti-update |
| Check reversal link | `is_reversal=true` requires FK; `false` requires null | reversal row linked to original | Conforme |
| Unique one reversal | unique partial index on `reversal_of_transaction_id` where `is_reversal=true` | one and only one reversal per original | Conforme DB |
| No PUT/PATCH/DELETE | route has POST/GET/reverse only | no put/patch/delete | Conforme route |

Invariants financiers sur `imperium_vault_transactions`:

- Ledger integrity: montants positifs, type borné, user-scoping dans services. OK pour V1.
- Reversals: le service crée une nouvelle ligne de type opposé, même montant/devise, `source="reversal"`, lien vers original. OK.
- One reversal per original: garanti par service + index unique partiel. OK.
- Reversal d'une reversal: bloqué par service, pas par DB. Une écriture directe DB pourrait pointer vers une reversal existante.
- Append-only/immutable: garanti par surface API, pas par DB. Pas de trigger anti-update/delete; `updated_at` mutable.
- Devise: API create exige `^[A-Z]{3}$`; query params acceptent `A-Za-z` puis normalisent. DB accepte n'importe quelle chaîne de longueur 3. Conforme au contrat API, pas au niveau DB.
- UTC: summary/monthly/category filtrent/groupent par `occurred_at`; monthly convertit en UTC pour `YYYY-MM`. C'est aligné avec `04`. `local_date/timezone` sont stockés mais ne pilotent pas ces summaries.

## Partie 2 — Doublons services/routes

### Services

| Fichier | Table | Responsabilité | Utilisation | Statut |
|---|---|---|---|---|
| `backend/app/services/imperium/vault.py` | `imperium_vault_transactions` | summaries global/monthly/categories + detail | importé par `routes/imperium_vault.py`; `get_vault_summary` aussi par dashboard foundation | Actif/canonique pour lectures Imperium |
| `backend/app/services/imperium/vault_transactions.py` | `imperium_vault_transactions` | create/list/reverse + idempotency | importé par `routes/imperium_vault.py`; très couvert par tests | Actif/canonique pour écritures/reversals Imperium |
| `backend/app/services/vault/transactions.py` | `vault_transactions` | create/recent/weekly summary + event `vault.transaction.created` | importé par `routes/vault.py` | Actif techniquement, mais legacy/duplicatif fonctionnel |

Ils ne font pas exactement la même chose, mais ils recouvrent le même domaine métier:

- Deux créations de transaction existent: `POST /api/vault/transactions` écrit `vault_transactions`; `POST /api/imperium/vault/transactions` écrit `imperium_vault_transactions`.
- Deux modèles de montant existent: decimal `amount` vs integer `amount_cents`.
- Deux modèles métier existent: `wallet/correction/event_id/source_app` vs `source/external_ref/reversal`.
- Deux chemins de summary existent: legacy weekly sur `vault_transactions`; Imperium summaries sur `imperium_vault_transactions`.

Point critique: certains services Imperium historiques lisent encore `VaultTransaction` directement:

- `backend/app/services/imperium/dashboard.py` lit `VaultTransaction` dans l'ancien `get_dashboard_snapshot()`.
- `backend/app/services/imperium/weekly_report.py` lit `VaultTransaction`.

Le nouveau dashboard foundation lit en revanche `ImperiumVaultTransaction` via `get_vault_summary()`. Cela crée un risque de chiffres incohérents selon l'écran/appel.

### Routes

| Route file | Prefix global | Table | Branchée dans l'app | Statut |
|---|---|---|---|---|
| `backend/app/api/v1/routes/imperium_vault.py` | `/api/imperium/vault` | `imperium_vault_transactions` | oui, `api_router.include_router(... prefix="/imperium/vault")` | Canonique actif selon `04_MVP_BACKEND_CONTRACTS.md` |
| `backend/app/api/v1/routes/vault.py` | `/api/vault` | `vault_transactions` | oui, `api_router.include_router(... prefix="/vault")` | Legacy actif, pas mort |

Il y a donc **deux routes pour le même domaine Vault**. Aucune n'est morte, car les deux sont incluses dans `backend/app/api/v1/router.py`. Mais la surface `/api/vault` est en dette: elle est encore active et documentée par `27`, pendant que les contrats MVP actifs promeuvent `/api/imperium/vault`.

## Conclusion

### (a) Conforme

Non.

### (b) Léger décalage

Non. Ce n'est pas seulement un renommage: deux ledgers et deux surfaces API coexistent.

### (c) Divergent

Oui.

Actions recommandées:

1. Trancher le ledger canonique avant toute correction: `imperium_vault_transactions` ou `vault_transactions`.
2. Déclarer un propriétaire de schéma unique. Option pragmatique: réécrire `05_DATABASE_SCHEMA.md` pour contenir le schéma Vault réel, et marquer `27_VAULT_TRANSACTIONS_WORKFLOW.md` comme legacy si `imperium_vault_transactions` gagne.
3. Si `imperium_vault_transactions` est canonique: migrer les lecteurs restants (`weekly_report`, ancien dashboard snapshot) vers `ImperiumVaultTransaction`, puis déprécier `/api/vault/*`, `VaultTransaction`, `services/vault/transactions.py`, et la migration/table legacy si tables vides.
4. Si `vault_transactions` est canonique: porter reversals, cents/idempotency moderne et summaries Imperium sur `vault_transactions`, puis supprimer `imperium_vault_transactions`.
5. Renforcer les invariants financiers en DB si append-only est non négociable: triggers anti-UPDATE/DELETE, ou politique explicite sur `updated_at`.
6. Harmoniser la devise: check DB `currency ~ '^[A-Z]{3}$'` si le contrat "exactement trois lettres ASCII uppercase" doit survivre aux écritures hors API.
7. Résoudre le conflit temporel: soit `occurred_at` est réellement unique source pour tous summaries/filtres, soit documenter que `local_date` sert aux vues locales hebdomadaires.

Tests non lancés: audit lecture seule, aucune modification de code.
