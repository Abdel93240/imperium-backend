# 69 - Imperium Frontend API Mapping V1

**Version :** 1.0
**Sources de verite :** `63_FRONTEND_ARCHITECTURE_V1.md`, `64_FRONTEND_GENERATION_PLAN_V1.md`, `65_IMPERIUM_FRONTEND_SCREEN_SPEC_V1.md`, `66_IMPERIUM_USER_FLOWS_V1.md`, `67_FRONTEND_STATE_MATRIX_V1.md`, `68_FRONTEND_MOCK_DATA_CATALOG_V1.md`, `07_ANDROID_APP_RESPONSIBILITIES.md`
**Cible :** documentation canonique du mapping futur entre ecrans Imperium V1, widgets et API backend
**Statut :** CANONICAL IMPERIUM FRONTEND API MAPPING V1 - documentation only, aucun backend branche, aucun endpoint ajoute, aucun Kotlin, aucun Android runtime.
**Last updated :** 2026-06-02

Ce document definit le mapping futur entre les ecrans et widgets Imperium V1 et les endpoints backend pressentis.
Il reste strictement coherent avec `63`, `64`, `65`, `66`, `67` et `68`.

Imperium reste une interface du cerveau backend. Ce document ne branche rien, ne cree aucune logique metier et ne valide aucune action canonique.

## 1. Scope

- Documentation uniquement.
- Aucun endpoint n est branche maintenant.
- Aucun backend n est modifie maintenant.
- Aucun contract canonique n est cree ici.
- Aucun comportement metier nouveau n est invente.
- Les sources mock de `68` restent la reference de rendu tant que le wiring backend n est pas autorise.
- Les etats UI de `67` restent la reference d etat pour chaque mapping.

## 2. Global API Mapping Rules

### 2.1 Source chain obligatoire

Le mapping suit strictement cette chaine :

`63` architecture -> `64` generation -> `65` screen spec -> `66` user flows -> `67` state matrix -> `68` mock catalog -> `69` API mapping.

### 2.2 Rules de mapping

- Chaque ecran doit pointer vers un mock source documente dans `68`.
- Chaque widget doit avoir un contrat de donnees lisible depuis le mock, sans inference locale canonique.
- Chaque mapping doit mentionner un endpoint futur pressenti si un endpoint existe deja dans `65` ou `64`.
- Si aucun endpoint n existe encore dans les docs precedents, le mapping doit etre marque `FUTURE TBD`.
- La methode HTTP doit etre explicite.
- L etat UI lie doit venir de `67` et ne doit pas etre reinterprete.
- `Ready state` est l etat cible de reference pour le mapping nominal.
- `Loading state`, `Empty state`, `Error state`, `Offline state` et `Partial sync state` restent disponibles comme etats de support selon `67`.

### 2.3 No branching now

- Aucun branchement backend maintenant.
- Aucun branchement runtime maintenant.
- Aucun branchement compose ou Android maintenant.
- Aucun branchement depuis les widgets vers un endpoint reel maintenant.
- Aucun branchement local ne doit transformer ce document en decision metier.

## 3. Screen to API Mapping

### 3.1 Dashboard

| Field | Value |
|---|---|
| Screen ID | `IMP-01` |
| Route ID | `IMP.DASH.MAIN` |
| UI state (67) | `Ready state` |
| Mock source 68 | `dashboard_mock_v1` |

| Widget | Donnees affichees | Mock source 68 | Endpoint futur pressenti | Endpoint a creer plus tard si absent | Methode HTTP | Etat UI 67 | Branching now |
|---|---|---|---|---|---|---|---|
| Daily Focus Card | `daily_focus.label`, `daily_focus.reason`, date visible, contexte de priorite | `dashboard_mock_v1` | `GET /api/imperium/dashboard` | None | GET | `Ready state` | No branch now |
| Active Mission Card | `active_mission.id`, `active_mission.title`, `active_mission.status`, `active_mission.priority`, `active_mission.deadline` | `dashboard_mock_v1` | `GET /api/imperium/missions/active` | None | GET | `Ready state` | No branch now |
| Priority Card | `priority.label`, `priority.reason`, signal de priorite du moment | `dashboard_mock_v1` | `GET /api/imperium/dashboard` | None | GET | `Ready state` | No branch now |
| Quick Actions | `quick_actions[].id`, `quick_actions[].label`, `quick_actions[].target_route`, `quick_actions[].style`, aucune decision canonique locale | `dashboard_mock_v1` | `POST /api/imperium/day/finish` | `FUTURE TBD POST /api/imperium/replans/request` | POST | `Ready state` | No branch now |
| Weekly Progress | `weekly_progress.missions_done`, `weekly_progress.missions_failed`, `weekly_progress.completion_percent` | `dashboard_mock_v1` | `GET /api/imperium/weekly-review/state` | None | GET | `Ready state` | No branch now |
| Imperium Status | `imperium_status.mode`, `imperium_status.backend_connected`, `imperium_status.cache_age_minutes` | `dashboard_mock_v1` | `GET /api/imperium/dashboard` | None | GET | `Ready state` | No branch now |

### 3.2 Mission Active

| Field | Value |
|---|---|
| Screen ID | `IMP-02` |
| Route ID | `IMP.MISSION.ACTIVE` |
| UI state (67) | `Ready state` |
| Mock source 68 | `mission_active_mock_v1` |

| Widget | Donnees affichees | Mock source 68 | Endpoint futur pressenti | Endpoint a creer plus tard si absent | Methode HTTP | Etat UI 67 | Branching now |
|---|---|---|---|---|---|---|---|
| Mission Header | `mission.id`, `mission.title`, `mission.status`, `mission.priority`, `mission.deadline` | `mission_active_mock_v1` | `GET /api/imperium/missions/active` | None | GET | `Ready state` | No branch now |
| Mission Description | `mission.description`, `mission.reason`, `mission.expected_outcome` | `mission_active_mock_v1` | `GET /api/imperium/missions/{mission_id}` | None | GET | `Ready state` | No branch now |
| Progress Block | `progress.current_step`, `progress.percent`, `progress.time_remaining_minutes` | `mission_active_mock_v1` | `GET /api/imperium/missions/{mission_id}` | None | GET | `Ready state` | No branch now |
| Decision Buttons | `Complete`, `Fail`, `Replan`, `Back` labels only | `mission_active_mock_v1` | `POST /api/imperium/missions/{mission_id}/complete`, `POST /api/imperium/missions/{mission_id}/fail` | `FUTURE TBD POST /api/imperium/replans/request` | POST | `Ready state` | No branch now |
| Notes Area | `notes[].id`, `notes[].text`, `notes[].created_at`, `note_save_state.status`, `note_save_state.last_saved_at`, `note_save_state.pending_note_id` | `mission_active_mock_v1` | None | `FUTURE TBD POST /api/imperium/missions/{mission_id}/notes` | POST | `Ready state` | No branch now |

### 3.3 Inbox

| Field | Value |
|---|---|
| Screen ID | `IMP-03` |
| Route ID | `IMP.INBOX.MAIN` |
| UI state (67) | `Ready state` |
| Mock source 68 | `inbox_mock_v1` |

| Widget | Donnees affichees | Mock source 68 | Endpoint futur pressenti | Endpoint a creer plus tard si absent | Methode HTTP | Etat UI 67 | Branching now |
|---|---|---|---|---|---|---|---|
| Search | `filters.query`, result count, clear action | `inbox_mock_v1` | `FUTURE TBD GET /api/imperium/inbox/items` | `FUTURE TBD GET /api/imperium/inbox/items` | GET | `Ready state` | No branch now |
| Filters | `filters.active` with `all`, `voice`, `notes`, `missions`, `unprocessed` | `inbox_mock_v1` | `FUTURE TBD GET /api/imperium/inbox/items` | `FUTURE TBD GET /api/imperium/inbox/items` | GET | `Ready state` | No branch now |
| Conversation List | `conversations[].id`, `conversations[].title`, `conversations[].source`, `conversations[].status`, `conversations[].latest_message`, `conversations[].updated_at` | `inbox_mock_v1` | `FUTURE TBD GET /api/imperium/inbox/items` | `FUTURE TBD GET /api/imperium/inbox/items` | GET | `Ready state` | No branch now |
| Message Preview | selected conversation detail, linked intention, sender label if present | `inbox_mock_v1` | `FUTURE TBD GET /api/imperium/inbox/conversations/{conversation_id}` | `FUTURE TBD GET /api/imperium/inbox/conversations/{conversation_id}` | GET | `Ready state` | No branch now |
| Add voice note | draft input, transcription preview only | `inbox_mock_v1` | `FUTURE TBD POST /api/imperium/voice/transcriptions` | `FUTURE TBD POST /api/imperium/voice/transcriptions` | POST | `Ready state` | No branch now |
| Convert to mission | conversion proposal label only, no local mission creation | `inbox_mock_v1` | `FUTURE TBD POST /api/imperium/inbox/items/{item_id}/convert-to-mission-proposal` | `FUTURE TBD POST /api/imperium/inbox/items/{item_id}/convert-to-mission-proposal` | POST | `Ready state` | No branch now |

### 3.4 Weekly Review

| Field | Value |
|---|---|
| Screen ID | `IMP-04` |
| Route ID | `IMP.WR.SUMMARY` |
| UI state (67) | `Ready state` |
| Mock source 68 | `weekly_review_mock_v1` |

| Widget | Donnees affichees | Mock source 68 | Endpoint futur pressenti | Endpoint a creer plus tard si absent | Methode HTTP | Etat UI 67 | Branching now |
|---|---|---|---|---|---|---|---|
| Weekly Summary | `week.start`, `week.end`, `week.status`, `summary` | `weekly_review_mock_v1` | `GET /api/imperium/weekly-review/state` | None | GET | `Ready state` | No branch now |
| Wins | `wins[].id`, `wins[].title`, `wins[].source`, `wins[].date` | `weekly_review_mock_v1` | `GET /api/imperium/weekly-review/state` | None | GET | `Ready state` | No branch now |
| Failures | `failures[].id`, `failures[].title`, `failures[].reason`, `failures[].linked_mission_id` | `weekly_review_mock_v1` | `GET /api/imperium/weekly-review/state` | None | GET | `Ready state` | No branch now |
| Improvement Suggestions | `improvement_suggestions[].id`, `improvement_suggestions[].text`, `improvement_suggestions[].rationale`, `improvement_suggestions[].confidence` | `weekly_review_mock_v1` | `GET /api/imperium/weekly-review/state` | None | GET | `Ready state` | No branch now |
| Statistics | `statistics.missions_done`, `statistics.missions_failed`, `statistics.completion_percent`, `statistics.weekly_profit_eur` | `weekly_review_mock_v1` | `GET /api/imperium/weekly-review/state` | None | GET | `Ready state` | No branch now |

### 3.5 History

| Field | Value |
|---|---|
| Screen ID | `IMP-05` |
| Route ID | `IMP.HISTORY.MAIN` |
| UI state (67) | `Ready state` |
| Mock source 68 | `history_mock_v1` |

| Widget | Donnees affichees | Mock source 68 | Endpoint futur pressenti | Endpoint a creer plus tard si absent | Methode HTTP | Etat UI 67 | Branching now |
|---|---|---|---|---|---|---|---|
| Timeline | `events[].id`, `events[].type`, `events[].title`, `events[].status`, `events[].occurred_at` | `history_mock_v1` | `GET /api/imperium/missions/history` | None | GET | `Ready state` | No branch now |
| Search | `filters.query`, query count, result narrowing only | `history_mock_v1` | `GET /api/imperium/missions/history` | None | GET | `Ready state` | No branch now |
| Filters | `filters.active` and filter chips | `history_mock_v1` | `GET /api/imperium/missions/history` | None | GET | `Ready state` | No branch now |
| History Detail Card | selected event details, `events[].source`, `events[].linked_route`, linked mission if present | `history_mock_v1` | `FUTURE TBD GET /api/imperium/history/events` | `FUTURE TBD GET /api/imperium/history/events` | GET | `Ready state` | No branch now |

### 3.6 Settings

| Field | Value |
|---|---|
| Screen ID | `IMP-06` |
| Route ID | `IMP.SETTINGS.CORE` |
| UI state (67) | `Ready state` |
| Mock source 68 | `settings_mock_v1` |

| Widget | Donnees affichees | Mock source 68 | Endpoint futur pressenti | Endpoint a creer plus tard si absent | Methode HTTP | Etat UI 67 | Branching now |
|---|---|---|---|---|---|---|---|
| User | `user.display_name`, `user.timezone`, `user.language` | `settings_mock_v1` | `GET /api/imperium/frontend/app-manifest` | None | GET | `Ready state` | No branch now |
| Theme | `theme.mode`, `theme.accent` | `settings_mock_v1` | `GET /api/imperium/frontend/app-manifest` | None | GET | `Ready state` | No branch now |
| Notifications | `notifications.morning_check_in`, `notifications.mission_reminders`, `notifications.weekly_review` | `settings_mock_v1` | `GET /api/imperium/frontend/app-manifest` | None | GET | `Ready state` | No branch now |
| Integrations | `integrations.n8n`, `integrations.postgresql`, `integrations.ai_router` | `settings_mock_v1` | `GET /api/imperium/frontend/app-manifest` | None | GET | `Ready state` | No branch now |
| Security | `security.auth_state`, `security.session_status`, redacted only | `settings_mock_v1` | `GET /api/imperium/frontend/app-manifest` | None | GET | `Ready state` | No branch now |
| Advanced | `advanced.priority_rules_link`, `advanced.cache_mode` | `settings_mock_v1` | `GET /api/imperium/frontend/app-manifest` | `FUTURE TBD PATCH /api/imperium/settings` | PATCH | `Ready state` | No branch now |

## 4. Widget to Data Contract

### 4.1 Canonical contract rules

- Les widgets lisent des champs documentes dans `68`.
- Les widgets n inventent pas de proprietes backend.
- Les widgets ne reinterpretent pas les etats de `67`.
- Les widgets ne lancent aucun branchement maintenant.
- Le contrat est descriptif, pas executable.

### 4.2 Contract matrix

| Screen | Widget | Canonical fields | Mock reference |
|---|---|---|---|
| Dashboard | Daily Focus Card | `daily_focus.label`, `daily_focus.reason` | `dashboard_mock_v1` |
| Dashboard | Active Mission Card | `active_mission.id`, `active_mission.title`, `active_mission.status`, `active_mission.priority`, `active_mission.deadline` | `dashboard_mock_v1` |
| Dashboard | Priority Card | `priority.label`, `priority.reason` | `dashboard_mock_v1` |
| Dashboard | Quick Actions | `quick_actions[].id`, `quick_actions[].label`, `quick_actions[].target_route`, `quick_actions[].style` | `dashboard_mock_v1` |
| Dashboard | Weekly Progress | `weekly_progress.missions_done`, `weekly_progress.missions_failed`, `weekly_progress.completion_percent` | `dashboard_mock_v1` |
| Dashboard | Imperium Status | `imperium_status.mode`, `imperium_status.backend_connected`, `imperium_status.cache_age_minutes` | `dashboard_mock_v1` |
| Mission Active | Mission Header | `mission.id`, `mission.title`, `mission.status`, `mission.priority`, `mission.deadline` | `mission_active_mock_v1` |
| Mission Active | Mission Description | `mission.description`, `mission.reason`, `mission.expected_outcome` | `mission_active_mock_v1` |
| Mission Active | Progress Block | `progress.current_step`, `progress.percent`, `progress.time_remaining_minutes` | `mission_active_mock_v1` |
| Mission Active | Notes Area | `notes[].id`, `notes[].text`, `notes[].created_at`, `note_save_state.status` | `mission_active_mock_v1` |
| Inbox | Search | `filters.query` | `inbox_mock_v1` |
| Inbox | Filters | `filters.active` | `inbox_mock_v1` |
| Inbox | Conversation List | `conversations[].id`, `conversations[].title`, `conversations[].source`, `conversations[].status`, `conversations[].latest_message`, `conversations[].updated_at` | `inbox_mock_v1` |
| Inbox | Message Preview | selected conversation projection only | `inbox_mock_v1` |
| Weekly Review | Weekly Summary | `week.start`, `week.end`, `week.status`, `summary` | `weekly_review_mock_v1` |
| Weekly Review | Wins | `wins[].id`, `wins[].title`, `wins[].source`, `wins[].date` | `weekly_review_mock_v1` |
| Weekly Review | Failures | `failures[].id`, `failures[].title`, `failures[].reason`, `failures[].linked_mission_id` | `weekly_review_mock_v1` |
| Weekly Review | Improvement Suggestions | `improvement_suggestions[].id`, `improvement_suggestions[].text`, `improvement_suggestions[].rationale`, `improvement_suggestions[].confidence` | `weekly_review_mock_v1` |
| Weekly Review | Statistics | `statistics.missions_done`, `statistics.missions_failed`, `statistics.completion_percent`, `statistics.weekly_profit_eur` | `weekly_review_mock_v1` |
| History | Timeline | `events[].id`, `events[].type`, `events[].title`, `events[].status`, `events[].occurred_at` | `history_mock_v1` |
| History | History Detail Card | `events[].source`, `events[].linked_route`, selected event projection only | `history_mock_v1` |
| Settings | User | `user.display_name`, `user.timezone`, `user.language` | `settings_mock_v1` |
| Settings | Theme | `theme.mode`, `theme.accent` | `settings_mock_v1` |
| Settings | Notifications | `notifications.morning_check_in`, `notifications.mission_reminders`, `notifications.weekly_review` | `settings_mock_v1` |
| Settings | Integrations | `integrations.n8n`, `integrations.postgresql`, `integrations.ai_router` | `settings_mock_v1` |
| Settings | Security | `security.auth_state`, `security.session_status` | `settings_mock_v1` |
| Settings | Advanced | `advanced.priority_rules_link`, `advanced.cache_mode` | `settings_mock_v1` |

## 5. Missing Backend Contracts

Les contrats ci-dessous sont absents ou partiellement definis dans l etat courant des docs.
Ils restent marques `FUTURE` et ne doivent pas etre branches maintenant.

| Screen | Missing backend contract | Status | Method |
|---|---|---|---|
| Dashboard | `FUTURE TBD POST /api/imperium/replans/request` | Missing | POST |
| Mission Active | `FUTURE TBD POST /api/imperium/replans/request` | Missing | POST |
| Mission Active | `FUTURE TBD POST /api/imperium/missions/{mission_id}/notes` | Missing | POST |
| Inbox | `FUTURE TBD GET /api/imperium/inbox/items` | Missing | GET |
| Inbox | `FUTURE TBD POST /api/imperium/inbox/items` | Missing | POST |
| Inbox | `FUTURE TBD GET /api/imperium/inbox/conversations/{conversation_id}` | Missing | GET |
| Inbox | `FUTURE TBD POST /api/imperium/inbox/items/{item_id}/convert-to-mission-proposal` | Missing | POST |
| Inbox | `FUTURE TBD POST /api/imperium/voice/transcriptions` | Missing | POST |
| History | `FUTURE TBD GET /api/imperium/history/events` | Missing | GET |
| Settings | `FUTURE TBD PATCH /api/imperium/settings` | Missing | PATCH |

## 6. Wiring Preconditions

- `63`, `64`, `65`, `66`, `67` et `68` doivent rester coherents avant tout wiring.
- Les widgets doivent continuer a lire les fixtures de `68` tant que le backend n est pas valide.
- Les etats UI de `67` doivent rester les seuls etats visibles dans le contrat de wiring.
- Aucune mutation canonique ne doit etre branchee depuis ce document.
- Aucune action `FUTURE` ne doit etre active maintenant.
- Aucun endpoint ne doit etre cree ou modifie a cause de ce document.
- Toute branchement futur doit passer par validation backend avant integration UI.
- Le contrat `one active mission` reste non negociable.
- Les screens read-only doivent rester read-only tant que le backend n a pas autorise une ecriture.

## 7. Validation Checklist

- [ ] Les 6 ecrans sont documentes.
- [ ] Chaque ecran declare ses widgets.
- [ ] Chaque ecran declare ses donnees affichees.
- [ ] Chaque ecran declare son mock source depuis `68`.
- [ ] Chaque ecran declare un endpoint futur pressenti si disponible.
- [ ] Chaque endpoint absent est marque `FUTURE TBD`.
- [ ] Chaque methode HTTP est explicite.
- [ ] Chaque ecran est lie a un etat UI de `67`.
- [ ] Aucune branche backend n est presente.
- [ ] Aucune logique metier n est inventee.
- [ ] Le document reste documentation only.
- [ ] La readiness est `READY` pour chaque ecran.

## 8. Readiness Matrix

| Screen | Readiness |
|---|---|
| Dashboard | READY |
| Mission Active | READY |
| Inbox | READY |
| Weekly Review | READY |
| History | READY |
| Settings | READY |
