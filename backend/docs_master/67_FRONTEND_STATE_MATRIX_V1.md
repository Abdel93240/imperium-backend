# 67 - Imperium Frontend State Matrix V1

**Version :** 1.0
**Sources de verite :** `63_FRONTEND_ARCHITECTURE_V1.md`, `64_FRONTEND_GENERATION_PLAN_V1.md`, `65_IMPERIUM_FRONTEND_SCREEN_SPEC_V1.md`, `66_IMPERIUM_USER_FLOWS_V1.md`, `07_ANDROID_APP_RESPONSIBILITIES.md`
**Cible :** documentation canonique de la matrice des etats UI Imperium V1
**Statut :** CANONICAL IMPERIUM FRONTEND STATE MATRIX V1 - documentation only, aucun backend branche, aucun endpoint ajoute, aucun Kotlin, aucun Android runtime.
**Last updated :** 2026-06-02

Ce document definit la matrice officielle des etats UI pour Imperium V1.
Il est strictement coherent avec `63_FRONTEND_ARCHITECTURE_V1.md`, `64_FRONTEND_GENERATION_PLAN_V1.md`, `65_IMPERIUM_FRONTEND_SCREEN_SPEC_V1.md` et `66_IMPERIUM_USER_FLOWS_V1.md`.

Imperium reste une interface du cerveau backend. Les ecrans affichent, expliquent, collectent et declenchent des intentions explicites, mais ils ne decident jamais seuls d une mission active, d une strategie ou d une action canonique.

## 1. Scope

- Documentation uniquement.
- Aucun backend branche.
- Aucun endpoint ajoute.
- Aucun Kotlin.
- Aucun Android runtime.
- Aucun changement de contrat backend.
- Aucun changement des regles de mission unique.
- Aucune nouvelle logique metier locale.

## 2. Screen Routing Canonical IDs

| Screen | Route ID | Route path | Top-level |
|---|---|---|---|
| Dashboard | `IMP.DASH.MAIN` | `imperium/dashboard` | Yes |
| Mission Active | `IMP.MISSION.ACTIVE` | `imperium/missions/active` | Yes |
| Inbox | `IMP.INBOX.MAIN` | `imperium/inbox` | Yes |
| Weekly Review | `IMP.WR.SUMMARY` | `imperium/weekly-review` | Yes |
| History | `IMP.HISTORY.MAIN` | `imperium/history` | Yes |
| Settings | `IMP.SETTINGS.CORE` | `imperium/settings` | Yes |

## 3. Dashboard

### 3.1 Identity

| Field | Value |
|---|---|
| Screen ID | `IMP-01` |
| Route ID | `IMP.DASH.MAIN` |
| Title | `Imperium` |

### 3.2 State Matrix

| State | User actions allowed | Visible components | Expected user message | Transition vers autres etats |
|---|---|---|---|---|
| Ready state | Open mission, open inbox, open weekly review, open history, open settings, read quick actions. | Top bar, Daily Focus card, Active Mission card, Priority card, Quick Actions, Weekly Progress, SyncStateChip. | `Tu dois savoir quoi faire maintenant.` | Can move to any top-level destination or refresh to Loading if data is requested again. |
| Loading state | No destructive action; only back navigation and cancel refresh if the platform supports it. | Top bar, skeleton for Daily Focus, skeleton for Active Mission, skeleton metric cards, skeleton status panel. | `Chargement du command center.` | Returns to Ready when data arrives, Error on fetch failure, Offline when network is unavailable. |
| Empty state | Open Inbox, read the instruction, return to Dashboard after acknowledgement. | Top bar, ImperiumEmptyState in active mission zone, helper text, one CTA, sync indicator. | `Aucune mission active pour le moment.` | Moves to Ready when backend provides a confirmed mission, or to Loading on manual retry. |
| Error state | Retry, back, open Inbox, open Settings for local review only. | Top bar, ImperiumErrorState, retry action, back action, sync indicator. | `Le Dashboard est temporairement indisponible.` | Can go to Loading after retry, Offline if the device is disconnected, Ready after successful recovery. |
| Offline state | Read cached content, open destinations already cached, queue non-destructive local intent where allowed. | Offline banner, cached mission card, stale labels, sync chip, top bar. | `Mode hors ligne: affichage cache.` | Can go to Partial sync when some blocks refresh later, or back to Ready once connectivity returns. |
| Partial sync state | Read blocks already synced, wait for syncing widgets, retry refresh, no destructive action. | Mix of synced cards, syncing chip, stale badge on specific blocks, offline or sync banner if needed. | `Certaines donnees se mettent encore a jour.` | Can converge to Ready after all blocks finish syncing, or to Error if one critical block fails. |

### 3.3 Transitions summary

- Ready can transition to Loading, Offline, or Error depending on refresh and connectivity.
- Empty can transition to Ready when the backend-confirmed mission arrives.
- Error must always offer retry or back navigation.
- Offline must stay visible while the device remains disconnected.

## 4. Mission Active

### 4.1 Identity

| Field | Value |
|---|---|
| Screen ID | `IMP-02` |
| Route ID | `IMP.MISSION.ACTIVE` |
| Title | `Mission Active` |

### 4.2 State Matrix

| State | User actions allowed | Visible components | Expected user message | Transition vers autres etats |
|---|---|---|---|---|
| Ready state | Mark complete, mark fail, request replan, add note, add voice note, back to Dashboard, open detail if documented. | Mission header, description, progress block, decision buttons, notes area, sync chip. | `Une seule mission active doit rester visible.` | Can move to Loading on refresh, Error on data failure, Offline on connectivity loss, or remain Ready after note updates. |
| Loading state | Back only, or cancel pending interaction if supported locally. | Header skeleton, progress skeleton, disabled decision buttons, notes skeleton. | `Chargement de la mission active.` | Returns to Ready when the mission is fetched, Error on fetch failure, Offline on disconnect. |
| Empty state | Back to Dashboard, open Inbox. | Empty state card, helper text, back action, no create mission CTA. | `No active mission.` | Moves to Ready when the backend confirms a mission, or to Loading on retry. |
| Error state | Retry, back, open Dashboard. | Error state card, retry action, back action, sync chip. | `Mission active indisponible.` | Can transition to Loading after retry or to Offline if the device is disconnected. |
| Offline state | Read cached mission, inspect note draft, back. | Offline banner, cached mission card, stale badge, sync chip. | `Mode hors ligne: mission en cache.` | Can move to Partial sync when note save queues, or Ready when network returns and sync completes. |
| Partial sync state | Continue reading mission, wait for note or status sync, do not submit destructive changes twice. | Mission card, syncing chip, pending note chip, partial stale indicators. | `La mission se synchronise encore.` | Returns to Ready when all pending writes are acknowledged, or Error if sync fails critically. |

### 4.3 Transitions summary

- Ready is the only state that exposes mission actions in full.
- Error and Offline must still allow safe back navigation.
- Empty must never create a mission locally.

## 5. Inbox

### 5.1 Identity

| Field | Value |
|---|---|
| Screen ID | `IMP-03` |
| Route ID | `IMP.INBOX.MAIN` |
| Title | `Inbox` |

### 5.2 State Matrix

| State | User actions allowed | Visible components | Expected user message | Transition vers autres etats |
|---|---|---|---|---|
| Ready state | Search, filter, open conversation, add voice note, add text note, propose mission conversion. | Search field, filter chips, list items, preview panel, sync chip. | `Capture rapide, tri rapide, lecture rapide.` | Can move to Loading on refresh, Partial sync when only some items refresh, Offline when cache-only mode starts. |
| Loading state | Search and filter inputs remain visible but disabled, back navigation allowed. | Search skeleton, filter skeleton, list skeleton, preview skeleton. | `Chargement des entrees.` | Returns to Ready on success, Error on failure, Offline if network disappears. |
| Empty state | Add voice note, add text note, back to Dashboard. | Empty state card, CTA to capture a note, helper text, no fake conversations. | `Inbox vide: aucune entree capturee.` | Can move to Ready after a new captured item arrives, or to Loading when data refreshes. |
| Error state | Retry, back, open Dashboard. | Error state card, retry action, sync chip, disabled search. | `Inbox temporairement indisponible.` | Can transition to Loading after retry, or Offline when the device is disconnected. |
| Offline state | Read cached conversations, inspect existing previews, queue a local draft, back. | Offline banner, cached list, stale badges, sync chip, preview panel. | `Mode hors ligne: conversations en cache.` | Can move to Partial sync while queued drafts upload, then to Ready when sync completes. |
| Partial sync state | Read synced items, wait for pending uploads, avoid duplicate sends. | Mixed synced and pending list items, syncing chip, partial stale badges. | `Certaines entrees sont encore en synchronisation.` | Returns to Ready when all items are acknowledged or Error if a sync block fails. |

### 5.3 Transitions summary

- Ready exposes capture and consultation.
- Empty must explain that the Inbox is empty, not broken.
- Offline must remain visible and readable.

## 6. Weekly Review

### 6.1 Identity

| Field | Value |
|---|---|
| Screen ID | `IMP-04` |
| Route ID | `IMP.WR.SUMMARY` |
| Title | `Weekly Review` |

### 6.2 State Matrix

| State | User actions allowed | Visible components | Expected user message | Transition vers autres etats |
|---|---|---|---|---|
| Ready state | Read summary, inspect wins, inspect failures, open suggestions, return to Dashboard. | Summary card, wins block, failures block, recommendation card, statistics panel, sync chip. | `La semaine est lisible et exploitable.` | Can move to Loading on refresh, Partial sync if statistics arrive progressively, Offline on disconnect. |
| Loading state | Back navigation only. | Summary skeleton, statistics skeleton, recommendation skeleton, sync chip. | `Chargement de la weekly review.` | Returns to Ready when the weekly data arrives, Error on failure, Offline if the device is disconnected. |
| Empty state | Return to Dashboard, open guidance if available. | Empty state card, helper text, back action. | `Aucune weekly review disponible pour le moment.` | Can move to Ready when the weekly review is generated, or Loading on retry. |
| Error state | Retry, back, open Dashboard. | Error state card, retry action, sync chip. | `Weekly Review indisponible.` | Can transition to Loading after retry, or Offline if connectivity is lost. |
| Offline state | Read cached summary, open already cached blocks, back. | Offline banner, cached summary, stale labels, sync chip. | `Mode hors ligne: weekly review en cache.` | Can move to Partial sync if some metrics refresh later, then to Ready when sync finishes. |
| Partial sync state | Read what is already synced, wait for remaining statistics, no destructive action. | Mixed summary blocks, syncing chip, stale badges. | `Les statistiques se synchronisent encore.` | Returns to Ready when all review blocks are synced, or Error if a block fails critically. |

### 6.3 Transitions summary

- Ready is the default readable state.
- Empty must always explain why the week is empty.
- Error is always actionable.

## 7. History

### 7.1 Identity

| Field | Value |
|---|---|
| Screen ID | `IMP-05` |
| Route ID | `IMP.HISTORY.MAIN` |
| Title | `History` |

### 7.2 State Matrix

| State | User actions allowed | Visible components | Expected user message | Transition vers autres etats |
|---|---|---|---|---|
| Ready state | Search, filter, open item detail, return to Dashboard. | Timeline, filters, search field, detail panel, sync chip. | `L historique est pret.` | Can move to Loading on refresh, Offline when cache-only mode starts, Partial sync when some events arrive later. |
| Loading state | Search and filter remain visible but disabled, back navigation allowed. | Timeline skeleton, filter skeleton, detail skeleton, sync chip. | `Chargement de l historique.` | Returns to Ready when data arrives, Error on failure, Offline when the device disconnects. |
| Empty state | Back to Dashboard, adjust filters. | Empty state card, helper text, filter reset action. | `Aucun resultat dans l historique.` | Can move to Ready when history data becomes available, or Loading on retry. |
| Error state | Retry, back, open Dashboard. | Error state card, retry action, sync chip. | `Historique temporairement indisponible.` | Can transition to Loading after retry or Offline on connectivity loss. |
| Offline state | Read cached items, inspect cached detail, back. | Offline banner, cached timeline, stale badges, sync chip. | `Mode hors ligne: historique en cache.` | Can move to Partial sync when new items sync in later, then to Ready when stable. |
| Partial sync state | Read synced events, wait for pending events to arrive, no destructive action. | Mixed timeline items, syncing chip, stale badges. | `Certains evenements sont encore en synchronisation.` | Returns to Ready when synchronization completes, or Error if one block fails. |

### 7.3 Transitions summary

- History is read-heavy and must stay legible in cached mode.
- Empty should always explain the filter context if the list is empty.

## 8. Settings

### 8.1 Identity

| Field | Value |
|---|---|
| Screen ID | `IMP-06` |
| Route ID | `IMP.SETTINGS.CORE` |
| Title | `Settings` |

### 8.2 State Matrix

| State | User actions allowed | Visible components | Expected user message | Transition vers autres etats |
|---|---|---|---|---|
| Ready state | Open sections, edit allowed preferences, view sync status, return to Dashboard. | Section list, preference cards, sync chip, caution banners if needed. | `Les preferences sont disponibles.` | Can move to Loading on refresh, Offline when settings are cached only, Partial sync when some preferences are still syncing. |
| Loading state | Back navigation only. | Section skeleton, preference skeleton, sync chip. | `Chargement des parametres.` | Returns to Ready when data is loaded, Error on failure, Offline on disconnect. |
| Empty state | Return to Dashboard, open help copy if provided. | Empty state card, helper text, no fake settings sections. | `Aucun parametre configurable pour le moment.` | Can move to Ready when preferences are available, or Loading on retry. |
| Error state | Retry, back, open Dashboard. | Error state card, retry action, sync chip. | `Parametres indisponibles.` | Can transition to Loading after retry or Offline if the device is disconnected. |
| Offline state | Read cached settings, adjust local non-destructive UI state, back. | Offline banner, cached sections, stale labels, sync chip. | `Mode hors ligne: parametres en cache.` | Can move to Partial sync when pending preference writes later flush, then to Ready when complete. |
| Partial sync state | Read already-synced preferences, wait for pending saves, do not duplicate changes. | Mixed preference cards, syncing chip, pending save badges. | `Certaines preferences se synchronisent encore.` | Returns to Ready when sync completes, or Error if one preference write fails critically. |

### 8.3 Transitions summary

- Settings must never expose secrets or auth internals.
- Destructive actions are never allowed without confirmation.

## 9. Global State Rules

- Loading jamais vide.
- Error toujours actionnable.
- Empty state toujours explicatif.
- Offline state toujours visible.
- Aucune action destructive sans confirmation.
- Aucune ecran ne doit inventer une mission active locale.
- Aucune mission active concurrente ne peut apparaitre.
- Un cache ne doit jamais etre presente comme une verite live.
- Un etat partiellement sync doit montrer ce qui est deja valide et ce qui ne l est pas encore.
- Le bouton primary visible doit rester unique dans la zone active.

## 10. State Validation Checklist

- [ ] Les 6 ecrans sont decrits.
- [ ] Chaque ecran declare Ready state.
- [ ] Chaque ecran declare Loading state.
- [ ] Chaque ecran declare Empty state.
- [ ] Chaque ecran declare Error state.
- [ ] Chaque ecran declare Offline state.
- [ ] Partial sync state est documente quand utile.
- [ ] Les actions utilisateur autorisees sont explicites par etat.
- [ ] Les composants visibles sont explicites par etat.
- [ ] Le message utilisateur attendu est explicite par etat.
- [ ] La transition vers d autres etats est explicite par etat.
- [ ] Les regles globales sont toutes presentees.
- [ ] La checklist elle-meme reste purement documentaire.
- [ ] Aucun backend branche.
- [ ] Aucun endpoint ajoute.
- [ ] Aucun Kotlin.
- [ ] Aucun Android runtime.
- [ ] Cohérence preservee avec 63, 64, 65 et 66.

## 11. Readiness Matrix

| Screen | Readiness |
|---|---|
| Dashboard | READY |
| Mission Active | READY |
| Inbox | READY |
| Weekly Review | READY |
| History | READY |
| Settings | READY |

