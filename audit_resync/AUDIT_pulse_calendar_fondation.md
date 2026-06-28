# AUDIT groupe — Pulse, Calendar, Fondation

Date: 2026-06-28  
Scope: audit lecture seule du code applicatif. Ecritures limitees a ce rapport et a `audit_resync/00_INDEX.md`.

## 1. PULSE

Verdict: **(c) divergent de perimetre**, mais la fondation codee est saine.

Le code implemente uniquement la surface minimaliste `imperium_pulse_entries` declaree dans `04_MVP_BACKEND_CONTRACTS.md`: POST/GET entries, today read-only, stats summary. Migration, ORM et schemas sont alignes colonne par colonne. Le decalage vient des docs `40`/`34`, qui decrivent Pulse sante/medical V1 beaucoup plus large: repas, hydratation, stock, workouts, pain logs, documents medicaux, consentement RGPD, regles medicales et routage specialiste sante. Rien de cela n'est code ici.

| Point | Code lu | Doc attendue | Ecart |
|---|---|---|---|
| Table active | `imperium_pulse_entries`: `entry_date`, sommeil, energie, fatigue, poids, workout, notes | `04` dit que Pulse 11a-11d actif = seulement cette table | Conforme au contrat MVP minimal |
| Colonnes / ORM / Pydantic | Migration, `ImperiumPulseEntry`, `PulseEntryCreate/Read` alignes | Pas de dictionnaire schema detaille ailleurs | Pas d'ecart colonne detecte |
| Invariants DB | ranges sommeil 0-24, energie/fatigue 1-10, poids positif, un entry/user/date, workout_type interdit si workout_done=false | `04`: pas de scoring/coaching/auto creation | Conforme pour la surface minimaliste |
| Privacy medicale | Aucun appel cloud, aucun upload, aucun document medical, aucun stockage brut | `34`: consentement RGPD, chiffrement, retention, validation explicite avant regle active | Securise par absence, mais medical V1 non implemente |
| IA / n8n / pgvector | Aucun appel IA/n8n/embedding/pgvector write dans service/route | `04`: interdit pour cette surface | Conforme |
| Coherence doc 40/34 | Entries simples seulement | Docs decrivent food stock, hydration, workouts, pain, medical docs/rules | Ecart majeur de perimetre si ces docs sont considerees V1 obligatoire |

Notes perimees: pas de `pgvector_memory` trouve dans ce perimetre. Les docs Pulse utilisent surtout des roles generiques (`local model`, `health specialist`, `OCR service`), pas de nom de modele concret obsolete cote code audite.

## 2. CALENDAR

Verdict: **(a) conforme a la fondation Patch 7H**, pas au Calendar V3 complet.

`51_FUTURE_CALENDAR.md` est explicite: le Calendar complet est une feature **V3 future**, post-V1/V2. Le code actuel correspond au bloc "Patch 7H — Minimal Foundation": table `imperium_calendar_events`, types limites `event/deadline/vacation`, create/list/delete manuel, scope user, idempotence sur creation, validation `ends_at >= starts_at`, aucun AI/n8n/pgvector/sync externe.

| Point | Code lu | Doc attendue | Ecart |
|---|---|---|---|
| Statut produit | Service + routes actifs pour create/list/delete | Doc 51: V3 future, mais Patch 7H fondation backend autorisee | Conforme si limite a Patch 7H |
| Schema table | `imperium_calendar_events`: user, event_type, title, starts_at, ends_at, blocks_time, location, notes | Patch 7H: table imperium, types limites, validation dates | Conforme |
| Full V3 schema | Pas de recurrence, status, deadline_at, overrides, geo, urgency | Doc 51 §10/§16 les place dans V3 | Absence normale, pas un bug V1 |
| Mutations | POST idempotent; DELETE physique sans idempotency ni event delete | Patch 7H mentionne manual delete; V3 prevoit hooks delete | Conforme fondation, dette future sur audit/hook delete |
| IA / n8n / pgvector | Aucun appel IA/n8n/embedding/pgvector | Patch 7H non-goals l'interdisent | Conforme |

Notes perimees: `51_FUTURE_CALENDAR.md` cite encore `Sonnet/Opus` et `Sonnet 4.6` pour les futurs tasks Calendar. C'est une dette de nomenclature modele dans la doc future, pas dans le code audite. Pas de `pgvector_memory` trouve.

## 3. FONDATION

Verdict: **(b) base solide, couverture DB partielle des non-negociables**.

Les trois migrations initiales posent une base correcte: extensions `pgcrypto` + `vector`, utilisateur unique via index partiel, devices, refresh tokens, idempotency keys, event envelope, logs d'auth, durcissement token selector/secret hash, puis triggers append-only contre UPDATE/DELETE/TRUNCATE sur `events` et `auth_events`. C'est une fondation saine. Elle ne traduit pas toutes les regles produit du doc 08 en contraintes DB dans ces trois fichiers: plusieurs garanties arrivent dans des migrations metier ulterieures, ou restent API/doc/model-prompt.

| Regle / garde-fou | Code lu | Doc 08 | Ecart |
|---|---|---|---|
| Stack V1 | `pgcrypto`, `vector`, UUID, PostgreSQL/Alembic | MVP-000 | Conforme |
| One-user auth | `users_single_user_singleton_idx` sur `single_user_mode IS TRUE` | SEC-001 | Partiel: bloque un user canonique true, mais n'interdit pas des users `false` |
| Trusted devices | `devices`, status trusted/revoked, refresh token lie a device | SEC-003 | Fondation presente |
| Idempotence | `idempotency_keys` unique `(user_id, idempotency_key)` + `events` unique `(user_id, idempotency_key)` | EVENT-001/004 | Conforme fondation |
| Event envelope | `events` contient source, device, user, privacy, correlation, causation, payload | EVENT-005 | Present, mais pas de check DB sur format dotted `event_type` ni JSON object |
| Append-only events | Triggers UPDATE/DELETE + TRUNCATE sur `events` et `auth_events` | EVENT-003 | Conforme pour ces tables |
| Secrets/tokens | `token_selector`, `token_secret_hash`, `token_hash` nullable legacy | SEC-002/003 | Durcissement sain |
| Une mission active | Pas dans 0001-0003 | IMP-001 | Non couvert ici; couvert plus tard par migration missions |
| Vault ledger / Path / Pulse rules | Pas dans 0001-0003 | VAULT/PATH/PULSE | Normal: hors fondation initiale |
| Privacy gate AI/cloud | `privacy_level` existe sur events; pas de gate DB | PRIV-001/002 | A faire cote API/router, pas vraiment DB-only |

Notes perimees: pas de `pgvector_memory` trouve dans ces migrations. Pas de nom de modele concret dans la fondation auditee.
