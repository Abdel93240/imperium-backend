# 68 - Imperium Frontend Mock Data Catalog V1

**Version :** 1.0
**Sources de verite :** `65_IMPERIUM_FRONTEND_SCREEN_SPEC_V1.md`, `67_FRONTEND_STATE_MATRIX_V1.md`, `64_FRONTEND_GENERATION_PLAN_V1.md`, `07_ANDROID_APP_RESPONSIBILITIES.md`
**Cible :** catalogue canonique des donnees mockees Imperium V1
**Statut :** CANONICAL IMPERIUM FRONTEND MOCK DATA CATALOG V1 - documentation only, aucune API reelle, aucune donnee utilisateur reelle, aucun backend branche, aucun Kotlin, aucun Android runtime.
**Last updated :** 2026-06-02

Ce document definit le catalogue officiel des donnees mockees Imperium V1.
Il est strictement coherent avec `65_IMPERIUM_FRONTEND_SCREEN_SPEC_V1.md` pour les widgets et avec `67_FRONTEND_STATE_MATRIX_V1.md` pour les etats.

Imperium reste une interface du cerveau backend. Les mocks servent uniquement a visualiser, tester et documenter les ecrans V1.
Ils ne declenchent aucune decision canonique, ne modifient aucune mission active, ne lisent aucune donnee reelle et ne contiennent aucun secret.

## 1. Global Mock Rules

### 1.1 Scope

- Documentation only.
- Aucune API reelle.
- Aucune donnee utilisateur reelle.
- Aucune valeur de production.
- Aucun backend branche.
- Aucun endpoint ajoute.
- Aucun model ajoute.
- Aucun schema ajoute.
- Aucun runtime frontend ajoute.
- Aucun Kotlin ajoute.

### 1.2 Naming and identity rules

- Chaque mock a un `mock_object_name` stable.
- Chaque item identifiable utilise un ID stable qui commence par `mock-`.
- Les `screen` utilisent les IDs canoniques de `65` et `67`.
- Les dates sont ISO uniquement.
- Les textes restent courts et mobiles.
- Les nombres restent coherents entre eux.
- Les noms de fichiers, routes ou variantes ne contiennent aucun secret.

### 1.3 Data safety rules

- Aucun email reel.
- Aucun token.
- Aucun mot de passe.
- Aucun secret.
- Aucun hash.
- Aucun identifiant sensible.
- Aucune cle.
- Aucune adresse reseau privee.
- Aucune reference a une base reelle.
- Aucune reference a une session reelle.

### 1.4 Mock behavior rules

- `sync_state` vaut toujours `mock`.
- Les variants empty, error et offline utilisent le meme contrat de base.
- Les variants offline montrent un cache stale ou une connexion non disponible.
- Les variants error ne montrent jamais de donnee sensible.
- Les variants empty restent explicatifs et non cassants.
- Le dashboard ne montre jamais plus d une mission active.
- Settings ne montre jamais les internals d authentification.

## 2. Screen Mock Catalog

### 2.1 Dashboard

| Field | Value |
|---|---|
| Mock object name | `dashboard_mock_v1` |
| Screen | `Dashboard` |
| Linked states (67) | `Ready state`, `Empty state`, `Error state`, `Offline state`, `Partial sync state` |
| Linked widgets (65) | `Daily Focus Card`, `Active Mission Card`, `Priority Card`, `Quick Actions`, `Weekly Progress`, `Imperium Status` |

#### JSON example

```json
{
  "screen": "IMP.DASH.MAIN",
  "mock_object_name": "dashboard_mock_v1",
  "sync_state": "mock",
  "generated_at": "2026-06-02T07:30:00Z",
  "daily_focus": {
    "label": "Execution",
    "reason": "Finish the active mission first."
  },
  "active_mission": {
    "id": "mock-mission-001",
    "title": "Finish weekly financial review",
    "status": "active",
    "priority": "high",
    "deadline": "2026-06-02T18:00:00Z"
  },
  "priority": {
    "label": "Financial clarity",
    "reason": "Weekly profit feeds sadaqa calculation."
  },
  "weekly_progress": {
    "missions_done": 9,
    "missions_failed": 2,
    "completion_percent": 72
  },
  "imperium_status": {
    "mode": "mock",
    "backend_connected": false,
    "cache_age_minutes": 0
  }
}
```

#### Required fields

| Field | Notes |
|---|---|
| `screen` | Must be `IMP.DASH.MAIN`. |
| `mock_object_name` | Must be `dashboard_mock_v1`. |
| `sync_state` | Must be `mock`. |
| `generated_at` | ISO timestamp. |
| `daily_focus.label` | Short mobile text. |
| `daily_focus.reason` | Short explanation. |
| `active_mission.id` | Stable `mock-` ID. |
| `active_mission.title` | Short mission title. |
| `active_mission.status` | `active` in READY mock. |
| `active_mission.priority` | Coherent priority label. |
| `active_mission.deadline` | ISO timestamp. |
| `priority.label` | Short focus label. |
| `priority.reason` | Short rationale. |
| `weekly_progress.missions_done` | Integer. |
| `weekly_progress.missions_failed` | Integer. |
| `weekly_progress.completion_percent` | Integer between 0 and 100. |
| `imperium_status.mode` | Must be `mock`. |
| `imperium_status.backend_connected` | Boolean. |
| `imperium_status.cache_age_minutes` | Non-negative integer. |

#### Optional fields

- `active_mission.description`
- `active_mission.reason`
- `active_mission.expected_outcome`
- `weekly_progress.streak_days`
- `imperium_status.note`

#### Variant links

- Empty variant: `dashboard_empty_v1`
- Error variant: `dashboard_error_v1`
- Offline variant: `dashboard_offline_v1`

### 2.2 Mission Active

| Field | Value |
|---|---|
| Mock object name | `mission_active_mock_v1` |
| Screen | `Mission Active` |
| Linked states (67) | `Ready state`, `Empty state`, `Error state`, `Offline state`, `Partial sync state` |
| Linked widgets (65) | `Mission Header`, `Mission Description`, `Progress Block`, `Decision Buttons`, `Notes Area` |

#### JSON example

```json
{
  "screen": "IMP.MISSION.ACTIVE",
  "mock_object_name": "mission_active_mock_v1",
  "sync_state": "mock",
  "generated_at": "2026-06-02T08:15:00Z",
  "mission": {
    "id": "mock-mission-001",
    "title": "Finish weekly financial review",
    "status": "active",
    "priority": "high",
    "deadline": "2026-06-02T18:00:00Z",
    "reason": "The Vault must stay factual before sadaqa is calculated."
  },
  "progress": {
    "current_step": "Review expense categories",
    "percent": 45,
    "time_remaining_minutes": 90
  },
  "notes": [
    {
      "id": "mock-note-001",
      "text": "Check fuel expenses after shift.",
      "created_at": "2026-06-02T08:10:00Z"
    }
  ]
}
```

#### Required fields

| Field | Notes |
|---|---|
| `screen` | Must be `IMP.MISSION.ACTIVE`. |
| `mock_object_name` | Must be `mission_active_mock_v1`. |
| `sync_state` | Must be `mock`. |
| `generated_at` | ISO timestamp. |
| `mission.id` | Stable `mock-` ID. |
| `mission.title` | Short mission title. |
| `mission.status` | `active` in READY mock. |
| `mission.priority` | Coherent priority label. |
| `mission.deadline` | ISO timestamp. |
| `progress.current_step` | Short current step label. |
| `progress.percent` | Integer between 0 and 100. |
| `progress.time_remaining_minutes` | Integer. |
| `notes[].id` | Stable `mock-` ID. |
| `notes[].text` | Short note. |
| `notes[].created_at` | ISO timestamp. |

#### Optional fields

- `mission.description`
- `mission.expected_outcome`
- `mission.source`
- `progress.blocked_reason`
- `notes[].source`

#### Variant links

- Empty variant: `mission_active_empty_v1`
- Error variant: `mission_active_error_v1`
- Offline variant: `mission_active_offline_v1`

### 2.3 Inbox

| Field | Value |
|---|---|
| Mock object name | `inbox_mock_v1` |
| Screen | `Inbox` |
| Linked states (67) | `Ready state`, `Empty state`, `Error state`, `Offline state`, `Partial sync state` |
| Linked widgets (65) | `Conversation List`, `Message Preview`, `Filters`, `Search` |

#### JSON example

```json
{
  "screen": "IMP.INBOX.MAIN",
  "mock_object_name": "inbox_mock_v1",
  "sync_state": "mock",
  "generated_at": "2026-06-02T09:30:00Z",
  "filters": {
    "active": "all",
    "query": ""
  },
  "conversations": [
    {
      "id": "mock-conv-001",
      "title": "Voice note after VTC shift",
      "source": "voice",
      "status": "unprocessed",
      "latest_message": "Check fuel expenses before review.",
      "updated_at": "2026-06-02T09:20:00Z"
    }
  ],
  "selected_conversation_id": "mock-conv-001"
}
```

#### Required fields

| Field | Notes |
|---|---|
| `screen` | Must be `IMP.INBOX.MAIN`. |
| `mock_object_name` | Must be `inbox_mock_v1`. |
| `sync_state` | Must be `mock`. |
| `generated_at` | ISO timestamp. |
| `filters.active` | `all`, `voice`, `notes`, `missions`, or `unprocessed`. |
| `filters.query` | Short search string. |
| `conversations[].id` | Stable `mock-` ID. |
| `conversations[].title` | Short title. |
| `conversations[].source` | `voice` or `text`. |
| `conversations[].status` | Stable status label. |
| `conversations[].latest_message` | Short preview text. |
| `conversations[].updated_at` | ISO timestamp. |
| `selected_conversation_id` | Must match an item ID when present. |

#### Optional fields

- `conversations[].linked_mission_id`
- `conversations[].sender_label`
- `conversations[].message_count`
- `selection_reason`

#### Variant links

- Empty variant: `inbox_empty_v1`
- Error variant: `inbox_error_v1`
- Offline variant: `inbox_offline_v1`

### 2.4 Weekly Review

| Field | Value |
|---|---|
| Mock object name | `weekly_review_mock_v1` |
| Screen | `Weekly Review` |
| Linked states (67) | `Ready state`, `Empty state`, `Error state`, `Offline state`, `Partial sync state` |
| Linked widgets (65) | `Weekly Summary`, `Wins`, `Failures`, `Improvement Suggestions`, `Statistics` |

#### JSON example

```json
{
  "screen": "IMP.WR.SUMMARY",
  "mock_object_name": "weekly_review_mock_v1",
  "sync_state": "mock",
  "generated_at": "2026-06-02T10:00:00Z",
  "week": {
    "start": "2026-05-25",
    "end": "2026-05-31",
    "status": "ready"
  },
  "summary": "Execution improved. Failures need clearer reasons.",
  "wins": [
    {
      "id": "mock-win-001",
      "title": "Tracked income every workday",
      "source": "vault",
      "date": "2026-05-31"
    }
  ],
  "failures": [
    {
      "id": "mock-failure-001",
      "title": "Skipped evening review twice",
      "reason": "Fatigue after long VTC shift",
      "linked_mission_id": "mock-mission-004"
    }
  ],
  "improvement_suggestions": [
    {
      "id": "mock-suggestion-001",
      "text": "Use voice notes immediately after shifts.",
      "confidence": "medium"
    }
  ],
  "statistics": {
    "missions_done": 21,
    "missions_failed": 5,
    "completion_percent": 81,
    "weekly_profit_eur": 420.75
  }
}
```

#### Required fields

| Field | Notes |
|---|---|
| `screen` | Must be `IMP.WR.SUMMARY`. |
| `mock_object_name` | Must be `weekly_review_mock_v1`. |
| `sync_state` | Must be `mock`. |
| `generated_at` | ISO timestamp. |
| `week.start` | ISO date. |
| `week.end` | ISO date. |
| `week.status` | Stable readiness label. |
| `summary` | Short summary text. |
| `wins[].id` | Stable `mock-` ID. |
| `wins[].title` | Short win title. |
| `wins[].source` | Short source label. |
| `wins[].date` | ISO date. |
| `failures[].id` | Stable `mock-` ID. |
| `failures[].title` | Short failure title. |
| `failures[].reason` | Short reason. |
| `statistics.missions_done` | Integer. |
| `statistics.missions_failed` | Integer. |
| `statistics.completion_percent` | Integer between 0 and 100. |
| `statistics.weekly_profit_eur` | Numeric, coherent with other values. |

#### Optional fields

- `failures[].linked_mission_id`
- `improvement_suggestions[].confidence`
- `statistics.sadaqa_basis_eur`
- `week.generated_by`

#### Variant links

- Empty variant: `weekly_review_empty_v1`
- Error variant: `weekly_review_error_v1`
- Offline variant: `weekly_review_offline_v1`

### 2.5 History

| Field | Value |
|---|---|
| Mock object name | `history_mock_v1` |
| Screen | `History` |
| Linked states (67) | `Ready state`, `Empty state`, `Error state`, `Offline state`, `Partial sync state` |
| Linked widgets (65) | `Timeline`, `Search`, `Filters`, `History Detail Card` |

#### JSON example

```json
{
  "screen": "IMP.HISTORY.MAIN",
  "mock_object_name": "history_mock_v1",
  "sync_state": "mock",
  "generated_at": "2026-06-02T10:30:00Z",
  "filters": {
    "active": "all",
    "query": ""
  },
  "events": [
    {
      "id": "mock-history-001",
      "type": "mission_completed",
      "title": "Weekly income check completed",
      "status": "completed",
      "occurred_at": "2026-06-01T20:15:00Z",
      "linked_mission_id": "mock-mission-010"
    },
    {
      "id": "mock-history-002",
      "type": "mission_failed",
      "title": "Evening review skipped",
      "status": "failed",
      "reason": "Fatigue after VTC shift",
      "occurred_at": "2026-05-31T22:40:00Z"
    }
  ],
  "selected_event_id": "mock-history-001"
}
```

#### Required fields

| Field | Notes |
|---|---|
| `screen` | Must be `IMP.HISTORY.MAIN`. |
| `mock_object_name` | Must be `history_mock_v1`. |
| `sync_state` | Must be `mock`. |
| `generated_at` | ISO timestamp. |
| `filters.active` | Stable filter label. |
| `filters.query` | Short search string. |
| `events[].id` | Stable `mock-` ID. |
| `events[].type` | Stable event type. |
| `events[].title` | Short title. |
| `events[].status` | Stable status label. |
| `events[].occurred_at` | ISO timestamp. |
| `selected_event_id` | Must match an item ID when present. |

#### Optional fields

- `events[].reason`
- `events[].linked_mission_id`
- `events[].source`
- `detail_hint`

#### Variant links

- Empty variant: `history_empty_v1`
- Error variant: `history_error_v1`
- Offline variant: `history_offline_v1`

### 2.6 Settings

| Field | Value |
|---|---|
| Mock object name | `settings_mock_v1` |
| Screen | `Settings` |
| Linked states (67) | `Ready state`, `Empty state`, `Error state`, `Offline state`, `Partial sync state` |
| Linked widgets (65) | `User`, `Theme`, `Notifications`, `Integrations`, `Security`, `Advanced` |

#### JSON example

```json
{
  "screen": "IMP.SETTINGS.CORE",
  "mock_object_name": "settings_mock_v1",
  "sync_state": "mock",
  "generated_at": "2026-06-02T10:45:00Z",
  "user": {
    "display_name": "Imperium User",
    "timezone": "Europe/Paris",
    "language": "fr"
  },
  "theme": {
    "mode": "system",
    "accent": "imperium_gold"
  },
  "notifications": {
    "morning_check_in": true,
    "mission_reminders": true,
    "weekly_review": true
  },
  "integrations": {
    "n8n": "not_connected_in_mock",
    "postgresql": "not_connected_in_mock",
    "ai_router": "not_connected_in_mock"
  },
  "security": {
    "auth_state": "redacted_mock",
    "session_status": "mock_only"
  },
  "advanced": {
    "priority_rules_link": "IMP.SETTINGS.PRIORITIES",
    "cache_mode": "mock"
  }
}
```

#### Required fields

| Field | Notes |
|---|---|
| `screen` | Must be `IMP.SETTINGS.CORE`. |
| `mock_object_name` | Must be `settings_mock_v1`. |
| `sync_state` | Must be `mock`. |
| `generated_at` | ISO timestamp. |
| `user.display_name` | Short visible label. |
| `user.timezone` | IANA timezone string. |
| `user.language` | Short language code. |
| `theme.mode` | Stable theme mode. |
| `theme.accent` | Stable accent label. |
| `notifications.morning_check_in` | Boolean. |
| `notifications.mission_reminders` | Boolean. |
| `notifications.weekly_review` | Boolean. |
| `integrations.n8n` | Mock connection status. |
| `integrations.postgresql` | Mock connection status. |
| `integrations.ai_router` | Mock connection status. |
| `security.auth_state` | Redacted mock state only. |
| `security.session_status` | Mock session label. |
| `advanced.priority_rules_link` | Canonical route label. |
| `advanced.cache_mode` | Mock cache label. |

#### Optional fields

- `user.avatar_label`
- `theme.note`
- `notifications.quiet_hours`
- `integrations.vault`
- `security.last_local_refresh_at`
- `advanced.last_reset_at`

#### Variant links

- Empty variant: `settings_empty_v1`
- Error variant: `settings_error_v1`
- Offline variant: `settings_offline_v1`

## 3. Empty/Error/Offline Variants

Les variants ci-dessous gardent le meme contrat de base, le meme `screen`, le meme `mock_object_name` canonique par famille et les memes regles de securite.
Ils changent uniquement l etat visuel ou la disponibilite des donnees.
Empty variant, Error variant et Offline variant sont documentes pour chaque ecran.

### 3.1 Dashboard variants

| Variant | Mock object name | Shape |
|---|---|---|
| Empty | `dashboard_empty_v1` | `active_mission: null`, `weekly_progress` a zero, `daily_focus.label = "Waiting"`. |
| Error | `dashboard_error_v1` | `error_state.code = "dashboard_unavailable"`, retry available, no sensitive data. |
| Offline | `dashboard_offline_v1` | `imperium_status.backend_connected = false`, cached cards marked stale. |

### 3.2 Mission Active variants

| Variant | Mock object name | Shape |
|---|---|---|
| Empty | `mission_active_empty_v1` | `mission: null`, empty state title, back only. |
| Error | `mission_active_error_v1` | `error_state.code = "mission_unavailable"`, no mission details exposed. |
| Offline | `mission_active_offline_v1` | cached mission shown, pending writes queued only. |

### 3.3 Inbox variants

| Variant | Mock object name | Shape |
|---|---|---|
| Empty | `inbox_empty_v1` | `conversations: []`, no fake conversation. |
| Error | `inbox_error_v1` | `error_state.code = "inbox_unavailable"`, search disabled. |
| Offline | `inbox_offline_v1` | cached conversations shown, stale badges visible. |

### 3.4 Weekly Review variants

| Variant | Mock object name | Shape |
|---|---|---|
| Empty | `weekly_review_empty_v1` | `summary: null`, empty lists, week status not started. |
| Error | `weekly_review_error_v1` | `error_state.code = "weekly_review_unavailable"`, no recommendation leakage. |
| Offline | `weekly_review_offline_v1` | cached summary shown, stale stats visible. |

### 3.5 History variants

| Variant | Mock object name | Shape |
|---|---|---|
| Empty | `history_empty_v1` | `events: []`, filters preserved. |
| Error | `history_error_v1` | `error_state.code = "history_unavailable"`, no timeline leak. |
| Offline | `history_offline_v1` | cached timeline shown, stale markers visible. |

### 3.6 Settings variants

| Variant | Mock object name | Shape |
|---|---|---|
| Empty | `settings_empty_v1` | sections uninitialized, guided defaults only. |
| Error | `settings_error_v1` | `error_state.code = "settings_unavailable"`, no auth internals. |
| Offline | `settings_offline_v1` | cached settings shown, sync pending indicators only. |

## 4. Mock Validation Checklist

- [ ] The 6 screens are present.
- [ ] Every screen has a stable `mock_object_name`.
- [ ] Every screen has a JSON example.
- [ ] Every JSON example uses ISO dates only.
- [ ] Every JSON example uses stable `mock-` IDs where applicable.
- [ ] No example contains a real email.
- [ ] No example contains a token or secret.
- [ ] No example contains a real user value.
- [ ] Global rules forbid real API usage.
- [ ] Global rules forbid real backend branching.
- [ ] Global rules forbid real user data.
- [ ] Global rules require short mobile text.
- [ ] Global rules require coherent numbers.
- [ ] Every screen links to the `67` states.
- [ ] Every screen links to the `65` widgets.
- [ ] Empty, error and offline variants are documented.
- [ ] Readiness is `READY` for every screen.
- [ ] The document stays documentation only.

## 5. Readiness Matrix

| Screen | Readiness |
|---|---|
| Dashboard | READY |
| Mission Active | READY |
| Inbox | READY |
| Weekly Review | READY |
| History | READY |
| Settings | READY |
