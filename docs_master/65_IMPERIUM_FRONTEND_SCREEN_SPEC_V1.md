# 65 — Imperium Frontend Screen Spec V1

**Version :** 1.0
**Sources de verite :** `59_DESIGN_SYSTEM_V1_DRAFT.md`, `60_DESIGN_SYSTEM_TOKENS_KT.md`, `61_DESIGN_SYSTEM_COMPOSITE_COMPONENTS.md`, `62_DESIGN_SYSTEM_COMPONENT_CATALOG.md`, `63_FRONTEND_ARCHITECTURE_V1.md`, `64_FRONTEND_GENERATION_PLAN_V1.md`, `07_ANDROID_APP_RESPONSIBILITIES.md`, `43_IMPERIUM_LOGIC_DETAIL.md`
**Cible :** generation future Android natif Kotlin + Jetpack Compose + Material 3
**Statut :** CANONICAL IMPERIUM FRONTEND SCREEN SPEC V1 — documentation only, aucun Kotlin, aucun dossier `android/`, aucun runtime frontend, aucun backend branche, aucune API reelle.
**Last updated :** 2026-06-02

Ce document decrit les six ecrans Imperium V1 a generer en priorite selon `64_FRONTEND_GENERATION_PLAN_V1.md`.

Il est la source de verite ecran par ecran pour Claude Design, Codex ou tout generateur frontend. Aucun choix UI critique ne doit etre laisse a interpretation.

---

## 1. Mission du document

Le document verrouille :

1. les routes stables et les titres visibles ;
2. l'objectif metier de chaque ecran ;
3. le layout tablette et telephone ;
4. les widgets et composants autorises ;
5. l'ordre visuel exact ;
6. les actions utilisateur autorisees ;
7. les mock data documentaires ;
8. les etats loading, empty et error ;
9. les futurs endpoints backend, sans branchement reel ;
10. la Definition of Done par ecran.

Imperium reste une interface du cerveau backend. Les ecrans affichent, collectent et declenchent des intentions explicites. Ils ne decident pas seuls de la strategie, ne creent pas de mission active concurrente et ne valident jamais une action canonique sans backend.

## 2. Regles globales

### 2.1 Documents obligatoires

Respecter strictement les documents suivants est obligatoire pour tout generateur :

| Document | Role |
|---|---|
| `59_DESIGN_SYSTEM_V1_DRAFT.md` | Design System V1 canonique. |
| `60_DESIGN_SYSTEM_TOKENS_KT.md` | Tokens Kotlin Compose canoniques. |
| `61_DESIGN_SYSTEM_COMPOSITE_COMPONENTS.md` | Composants composites metier et regle premium asset. |
| `62_DESIGN_SYSTEM_COMPONENT_CATALOG.md` | Component Catalog foundation `Imperium*`. |
| `63_FRONTEND_ARCHITECTURE_V1.md` | Architecture Android, navigation, state, cache, sync. |
| `64_FRONTEND_GENERATION_PLAN_V1.md` | Ordre de generation, phases et interdiction de backend avant validation visuelle. |

### 2.2 Interdictions

- Aucun ecran invente.
- Aucun widget invente.
- Aucune navigation inventee.
- Aucun backend branche.
- Aucune API reelle appelee.
- Aucune logique metier inventee.
- Aucune decision locale canonique.
- Aucune deuxieme mission active.
- Aucun placeholder visuel casse.
- Aucun composant hors `62_DESIGN_SYSTEM_COMPONENT_CATALOG.md`.
- Aucun changement de scope V2/V3.

### 2.3 Composants autorises

Les ecrans GO 65 utilisent uniquement :

| Famille | Composants autorises |
|---|---|
| Navigation | `ImperiumTopBar`, `ImperiumSidebar`, `ImperiumBottomNavigation`, `ImperiumTabBar`, `ImperiumDeepLinkTarget`. |
| Buttons | `ImperiumPrimaryButton`, `ImperiumSecondaryButton`, `ImperiumGhostButton`, `ImperiumDestructiveButton`, `ImperiumIconButton`, `ImperiumVoiceButton`. |
| Inputs | `ImperiumTextField`, `ImperiumSearchField`, `ImperiumVoiceInput`. |
| Selection | `ImperiumSegmentedControl`, `ImperiumFilterChip`, `ImperiumToggle`. |
| Feedback | `ImperiumSnackbar`, `ImperiumBanner`, `ImperiumAlertDialog`, `SyncStateChip`. |
| Containers | `ImperiumCard`, `ImperiumInteractiveCard`, `ImperiumSectionHeader`, `ImperiumContextPanel`. |
| States | `ImperiumLoadingState`, `ImperiumEmptyState`, `ImperiumErrorState`, `ImperiumOfflineState`, `ImperiumSkeleton`. |
| Data | `ImperiumMetricCard`, `ImperiumKpiBlock`, `ImperiumProgressBar`, `ImperiumProgressRing`, `ImperiumTimeline`, `ImperiumListItem`, `ImperiumStatusChip`. |
| Composite | `MissionFocusCard`, `ImperiumKpiBlock`, `ChatMessageBubble`. |

### 2.4 Layout global

Tablet landscape, cible Samsung Galaxy Tab S10 Ultra :

```text
ImperiumSidebar 240dp | Main content max 1280dp | Optional context panel 320-480dp
```

Telephone portrait :

```text
ImperiumTopBar
Scrollable single column content
ImperiumBottomNavigation
```

Regles communes :

- top-level tablette : sidebar obligatoire ;
- top-level telephone : bottom navigation obligatoire ;
- contenu principal contraint, jamais etire sans limite ;
- pas de card dans une card ;
- un seul bouton primary visible dans la zone active ;
- un seul accent gold fort visible par ecran ;
- tous les textes importants doivent rester visibles en telephone ;
- etats loading, empty et error obligatoires pour chaque ecran.

## 3. Dashboard Screen

### 3.1 Identity

| Champ | Valeur |
|---|---|
| Route ID | `IMP.DASH.MAIN` |
| Screen ID source | `IMP-01` |
| Route path | `imperium/dashboard` |
| Titre visible | `Imperium` |
| Type | Top-level route |

### 3.2 Objectif metier

Montrer ce que l'utilisateur doit faire maintenant, avec une seule mission active visible, les priorites du jour, les actions rapides et l'etat global Imperium.

Le Dashboard ne choisit pas une nouvelle mission localement. Il affiche le read model mock en Phase 1/2, puis le backend en Phase 3 seulement.

### 3.3 Layout tablette

| Zone | Specification |
|---|---|
| Sidebar | 240dp, destinations top-level Imperium dans l'ordre du contrat navigation. |
| Main column | Max 960dp, scroll vertical. |
| Context panel | 320dp, affiche `Imperium Status` et details sync/cache. |
| Grille main | 2 colonnes apres la Daily Focus Card. |

Ordre tablette :

1. `ImperiumTopBar` avec titre `Imperium`, sous-titre `Aujourd'hui`, `SyncStateChip`.
2. `Daily Focus Card` pleine largeur.
3. `Active Mission Card` pleine largeur.
4. Ligne deux colonnes : `Priority Card`, `Weekly Progress`.
5. `Quick Actions` pleine largeur.
6. `Imperium Status` dans context panel.

### 3.4 Layout telephone

Ordre telephone, une seule colonne :

1. `ImperiumTopBar`.
2. `Daily Focus Card`.
3. `Active Mission Card`.
4. `Priority Card`.
5. `Quick Actions`.
6. `Weekly Progress`.
7. `Imperium Status`.
8. `ImperiumBottomNavigation`.

### 3.5 Widgets presents

| Widget | Composant autorise | Contenu obligatoire |
|---|---|---|
| Daily Focus Card | `ImperiumCard` + `ImperiumSectionHeader` | focus label, raison, date locale mock, source `mock`. |
| Active Mission Card | `MissionFocusCard` | mission id, titre, priorite, deadline, status, une action primary. |
| Priority Card | `ImperiumCard` + `ImperiumKpiBlock` | top priority, reason, urgency label. |
| Quick Actions | `ImperiumCard` + buttons | ouvrir mission active, ajouter note inbox, lancer replan mock, finish day mock. |
| Weekly Progress | `ImperiumMetricCard` + `ImperiumProgressBar` | missions done, failures, weekly completion percent. |
| Imperium Status | `ImperiumCard` + `SyncStateChip` | mock sync, cache age, next backend wiring phase. |

### 3.6 Actions utilisateur

| Action | UI | Effet Phase 1/2 | Backend Phase 3 future |
|---|---|---|---|
| Ouvrir mission active | Primary sur `Active Mission Card` | navigue vers `IMP.MISSION.ACTIVE` avec mock id. | lecture active mission confirmee par backend. |
| Ajouter note inbox | Secondary dans `Quick Actions` | navigue vers `IMP.INBOX.MAIN` avec champ vide. | creation inbox item backend-validee. |
| Demander replan | Secondary dans `Quick Actions` | affiche snackbar `Mock only`. | ouvre `IMP.REPLAN.VALIDATE` si proposition backend existe. |
| Finish day | Ghost dans `Quick Actions` | affiche snackbar `Mock only`. | ouvre `IMP.DAY.FINISH`. |

### 3.7 Mock data

Fixture locale canonique : `dashboard_mock_v1`.

```json
{
  "screen_id": "IMP-01",
  "route_id": "IMP.DASH.MAIN",
  "screen": "IMP.DASH.MAIN",
  "fixture_name": "dashboard_mock_v1",
  "sync_state": "mock",
  "generated_at": "2026-06-02T07:30:00Z",
  "daily_focus": {
    "label": "Execution",
    "reason": "Finish the one active mission before opening new work."
  },
  "active_mission": {
    "id": "mock-mission-001",
    "title": "Finish weekly financial review",
    "description": "Check income, expenses and weekly profit before planning sadaqa.",
    "status": "active",
    "priority": "high",
    "deadline": "2026-06-02T18:00:00Z"
  },
  "priority": {
    "label": "Financial clarity",
    "reason": "Weekly profit feeds The Path sadaqa calculation.",
    "urgency": "today"
  },
  "weekly_progress": {
    "missions_done": 9,
    "missions_failed": 2,
    "completion_percent": 72
  },
  "quick_actions": [
    {
      "id": "mock-action-open-mission",
      "label": "Open Mission Active",
      "target_route": "IMP.MISSION.ACTIVE",
      "style": "primary"
    },
    {
      "id": "mock-action-add-inbox-note",
      "label": "Add Inbox Note",
      "target_route": "IMP.INBOX.MAIN",
      "style": "secondary"
    },
    {
      "id": "mock-action-request-replan",
      "label": "Request Replan",
      "target_route": null,
      "style": "secondary",
      "mock_effect": "snackbar_only"
    },
    {
      "id": "mock-action-finish-day",
      "label": "Finish Day",
      "target_route": null,
      "style": "ghost",
      "mock_effect": "snackbar_only"
    }
  ],
  "imperium_status": {
    "mode": "mock",
    "backend_connected": false,
    "cache_age_minutes": 0
  }
}
```

### 3.8 States

| State | Specification |
|---|---|
| Loading state | `ImperiumSkeleton` for Daily Focus, Active Mission, two metric cards and status panel. No fake mission title. |
| Empty state | `ImperiumEmptyState` inside Active Mission slot: title `No active mission`, body `Waiting for backend-confirmed next mission.`, CTA `Open Inbox`. |
| Error state | `ImperiumErrorState` full main column if dashboard fixture/read fails; retry button visual only in Phase 1/2. |

### 3.9 Future backend endpoints

- `GET /api/imperium/dashboard`
- `GET /api/imperium/missions/active`
- `GET /api/imperium/weekly-review/state`
- `POST /api/imperium/day/finish`
- `FUTURE TBD POST /api/imperium/replans/request`

Ces endpoints ne sont pas branches dans GO 65.

### 3.10 Definition of Done

- Route `IMP.DASH.MAIN` rendue en mock.
- Tous les widgets minimum sont visibles.
- Une seule mission active visible.
- Responsive tablette conforme.
- Responsive telephone conforme.
- Loading, empty, error visibles.
- Aucune API reelle appelee.
- Navigation locale limitee au contrat GO 65.

## 4. Mission Active Screen

### 4.1 Identity

| Champ | Valeur |
|---|---|
| Route ID | `IMP.MISSION.ACTIVE` |
| Screen ID source | `IMP-02` |
| Route path | `imperium/missions/active` |
| Titre visible | `Mission active` |
| Type | Top-level route |

`IMP.MISSION.ACTIVE` est la destination top-level V1 de la mission active unique. La route detail mission separee est supprimee de la V1 et ne doit pas etre generee.

### 4.2 Objectif metier

Permettre a l'utilisateur de comprendre la mission active, agir dessus et enregistrer des notes sans creer une autre mission active.

### 4.3 Layout tablette

| Zone | Specification |
|---|---|
| Sidebar | Presente avec destination Mission Active active. |
| Main column | Max 880dp, mission detail pleine largeur. |
| Context panel | 320dp, progress block et sync state. |

Ordre tablette :

1. `ImperiumTopBar` avec back vers Dashboard.
2. `Mission Header`.
3. `Mission Description`.
4. `Decision Buttons`.
5. `Notes Area`.
6. `Progress Block` dans context panel.

### 4.4 Layout telephone

Ordre telephone :

1. `ImperiumTopBar` avec back.
2. `Mission Header`.
3. `Progress Block`.
4. `Mission Description`.
5. `Decision Buttons`.
6. `Notes Area`.

### 4.5 Composants

| Bloc | Composant autorise | Contenu obligatoire |
|---|---|---|
| Mission Header | `MissionFocusCard` | titre, status `active`, priority, deadline, sync chip. |
| Mission Description | `ImperiumCard` | description, reason, expected outcome. |
| Progress Block | `ImperiumProgressBar` + `ImperiumKpiBlock` | current step, percent, time remaining. |
| Decision Buttons | buttons | `Complete`, `Fail`, `Replan`, `Back`. |
| Notes Area | `ImperiumTextField` + `ImperiumVoiceInput` | text note, voice note entry, mock save state. |

### 4.6 Actions

| Action | UI | Effet Phase 1/2 | Backend Phase 3 future |
|---|---|---|---|
| Complete | `ImperiumPrimaryButton` | snackbar mock success, no state mutation canonical. | `POST /api/imperium/missions/{mission_id}/complete`. |
| Fail | `ImperiumDestructiveButton` | opens visual reason requirement only. | `POST /api/imperium/missions/{mission_id}/fail`. |
| Replan | `ImperiumSecondaryButton` | snackbar `Mock replan request`. | open `IMP.REPLAN.VALIDATE` after backend proposal. |
| Save note | `ImperiumGhostButton` | stores local preview note only. | `TBD POST /api/imperium/missions/{mission_id}/notes`. |
| Voice note | `ImperiumVoiceInput` | visual recording/transcribed mock. | Whisper/faster-whisper transcription then backend validation. |

### 4.7 Mock data

Fixture locale canonique : `mission_active_mock_v1`.

```json
{
  "screen_id": "IMP-02",
  "route_id": "IMP.MISSION.ACTIVE",
  "screen": "IMP.MISSION.ACTIVE",
  "fixture_name": "mission_active_mock_v1",
  "sync_state": "mock",
  "mission": {
    "id": "mock-mission-001",
    "title": "Finish weekly financial review",
    "description": "Check income, expenses and weekly profit before planning sadaqa.",
    "reason": "The Vault must show financial reality before The Path calculates sadaqa.",
    "expected_outcome": "Weekly profit reviewed and ready for weekly review.",
    "status": "active",
    "priority": "high",
    "deadline": "2026-06-02T18:00:00Z"
  },
  "progress": {
    "current_step": "Review expense categories",
    "percent": 45,
    "time_remaining_minutes": 90
  },
  "notes": [
    {
      "id": "mock-note-001",
      "text": "Need to verify Bolt fuel expenses.",
      "created_at": "2026-06-02T08:10:00Z",
      "source": "text"
    }
  ],
  "note_save_state": {
    "status": "idle",
    "last_saved_at": null,
    "pending_note_id": null
  }
}
```

### 4.8 States

| State | Specification |
|---|---|
| Loading | Mission header skeleton, progress skeleton, disabled decision buttons. |
| Empty | `ImperiumEmptyState`: title `No active mission`, CTA `Back to Dashboard`; no create mission button here. |
| Error | `ImperiumErrorState`: title `Active mission unavailable`, retry visual only, back button always available. |

### 4.9 Future endpoints

- `GET /api/imperium/missions/active`
- `GET /api/imperium/missions/{mission_id}`
- `POST /api/imperium/missions/{mission_id}/complete`
- `POST /api/imperium/missions/{mission_id}/fail`
- `TBD POST /api/imperium/missions/{mission_id}/notes`
- `FUTURE TBD POST /api/imperium/replans/request`

### 4.10 DoD

- Route top-level visible dans la navigation Imperium V1.
- Navigation vers Dashboard disponible via sidebar/bottom nav.
- Mission header, description, progress, buttons et notes visibles.
- Fail demande une raison visuelle avant mock submit.
- Empty state ne cree pas de mission active localement.
- Loading et error rendus.
- Aucune API reelle.

## 5. Inbox Screen

### 5.1 Identity

| Champ | Valeur |
|---|---|
| Route ID | `IMP.INBOX.MAIN` |
| Screen ID source | `IMP-03` |
| Route path | `imperium/inbox` |
| Titre visible | `Inbox` |
| Type | Top-level route |

### 5.2 Objectif metier

Capturer et consulter les entrees utilisateur rapides : notes, messages, idees, commandes vocales transcrites et previews de conversation. L'Inbox collecte. Elle ne transforme pas seule une entree en mission active.

### 5.3 Layout tablette

| Zone | Specification |
|---|---|
| Sidebar | Dashboard, Mission Active, Inbox, Weekly Review, History, Settings. |
| Main column | Max 880dp, conversation list. |
| Context panel | 360dp, selected message preview/detail. |

Ordre tablette :

1. `ImperiumTopBar` titre `Inbox`.
2. Search row.
3. Filters row.
4. Conversation List.
5. Message Preview in context panel.

### 5.4 Layout telephone

Ordre telephone :

1. `ImperiumTopBar`.
2. `ImperiumSearchField`.
3. horizontal filter chips.
4. Conversation List.
5. Message Preview opens inline below selected list item.
6. `ImperiumBottomNavigation`.

### 5.5 Composants

| Bloc | Composant autorise | Contenu obligatoire |
|---|---|---|
| Conversation List | `ImperiumListItem` | title, source, timestamp, status chip. |
| Message Preview | `ImperiumCard` or `ChatMessageBubble` | latest message, sender, linked intention. |
| Filters | `ImperiumFilterChip` | All, Voice, Notes, Missions, Unprocessed. |
| Search | `ImperiumSearchField` | query, clear action, result count. |

### 5.6 Actions

| Action | UI | Effet Phase 1/2 | Backend Phase 3 future |
|---|---|---|---|
| Search | Search input | filters fixture locally. | server/local repository search. |
| Filter | Filter chips | filters fixture locally. | query parameter or local cache filter. |
| Select conversation | list item | shows preview panel. | fetch conversation detail. |
| Add voice note | voice button | appends mock draft visually. | STT pipeline then backend validation. |
| Convert to mission | secondary button in preview | disabled or mock snackbar until backend. | backend creates backlog/proposal, never active directly. |

### 5.7 Mock data

Fixture locale canonique : `inbox_mock_v1`.

```json
{
  "screen_id": "IMP-03",
  "route_id": "IMP.INBOX.MAIN",
  "screen": "IMP.INBOX.MAIN",
  "fixture_name": "inbox_mock_v1",
  "sync_state": "mock",
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
      "latest_message": "I need to check fuel expenses before weekly review.",
      "updated_at": "2026-06-02T09:20:00Z"
    },
    {
      "id": "mock-conv-002",
      "title": "Mission idea",
      "source": "text",
      "status": "linked_to_backlog",
      "latest_message": "Prepare morning routine checklist.",
      "updated_at": "2026-06-01T21:45:00Z"
    }
  ],
  "selected_conversation_id": "mock-conv-001"
}
```

### 5.8 States

| State | Specification |
|---|---|
| Loading | Search visible disabled, list skeleton rows, preview skeleton. |
| Empty | `ImperiumEmptyState`: title `Inbox empty`, body `No captured notes yet.`, CTA `Add voice note` mock only. |
| Error | `ImperiumErrorState`: title `Inbox unavailable`, retry visual only, search disabled. |

### 5.9 Future endpoints

- `TBD GET /api/imperium/inbox/items`
- `TBD POST /api/imperium/inbox/items`
- `TBD GET /api/imperium/inbox/conversations/{conversation_id}`
- `TBD POST /api/imperium/inbox/items/{item_id}/convert-to-mission-proposal`
- `TBD POST /api/imperium/voice/transcriptions`

### 5.10 DoD

- Conversation List, Message Preview, Filters et Search visibles.
- Search et filters fonctionnent sur mock data.
- Convert to mission ne cree jamais de mission active.
- Voice note reste mock.
- Loading, empty, error rendus.
- Responsive tablette et telephone.

## 6. Weekly Review Screen

### 6.1 Identity

| Champ | Valeur |
|---|---|
| Route ID | `IMP.WR.SUMMARY` |
| Related canonical routes | `IMP.WR.LIST`, `IMP.WR.READ_ONLY`, `IMP.WR.INTERACTIVE` |
| Screen ID source | `IMP-04` |
| Route path | `imperium/weekly-review` |
| Titre visible | `Weekly Review` |
| Type | Top-level route |

### 6.2 Objectif metier

Afficher une synthese hebdomadaire lisible : resultats, victoires, echecs, suggestions d'amelioration et statistiques. La validation finale d'une weekly review reste backend/WR workflow, jamais locale.

### 6.3 Layout tablette

| Zone | Specification |
|---|---|
| Sidebar | Destination Weekly Review active. |
| Main column | Max 960dp, summary and lists. |
| Context panel | 320dp, Statistics sticky panel. |

Ordre tablette :

1. `ImperiumTopBar`.
2. `Weekly Summary`.
3. Deux colonnes : `Wins`, `Failures`.
4. `Improvement Suggestions`.
5. `Statistics` dans context panel.

### 6.4 Layout telephone

Ordre telephone :

1. `ImperiumTopBar`.
2. `Weekly Summary`.
3. `Statistics`.
4. `Wins`.
5. `Failures`.
6. `Improvement Suggestions`.
7. `ImperiumBottomNavigation`.

### 6.5 Composants

| Bloc | Composant autorise | Contenu obligatoire |
|---|---|---|
| Weekly Summary | `ImperiumCard` | week range, status, summary paragraph. |
| Wins | `ImperiumListItem` | win title, source, date. |
| Failures | `ImperiumListItem` + status chip | failure, reason, linked mission if any. |
| Improvement Suggestions | `ImperiumCard` list | suggestion, rationale, confidence label mock. |
| Statistics | `ImperiumMetricCard`, `ImperiumProgressBar` | missions done, failed, completion, profit placeholder if provided by Vault mock. |

### 6.6 Actions

| Action | UI | Effet Phase 1/2 | Backend Phase 3 future |
|---|---|---|---|
| Start interactive review | Primary | snackbar mock or open disabled preview; never locale finalization. | `POST /api/imperium/weekly-review/launch`. |
| Open stored report | list/detail link | navigates within mock preview. | `GET /api/imperium/weekly-review/{session_id}/final-report`. |
| Export markdown | Ghost | snackbar mock. | `GET /api/imperium/weekly-review/{session_id}/final-report/markdown`. |

### 6.7 Mock data

Fixture locale canonique : `weekly_review_mock_v1`.

```json
{
  "screen_id": "IMP-04",
  "route_id": "IMP.WR.SUMMARY",
  "screen": "IMP.WR.SUMMARY",
  "fixture_name": "weekly_review_mock_v1",
  "sync_state": "mock",
  "week": {
    "start": "2026-05-25",
    "end": "2026-05-31",
    "status": "ready_for_review"
  },
  "summary": "Execution improved, but failed missions still need clearer reasons.",
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
      "text": "Use voice notes immediately after VTC shifts.",
      "rationale": "The user often finishes VTC shifts tired, so voice capture lowers friction while preserving data quality.",
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

### 6.8 States

| State | Specification |
|---|---|
| Loading | Summary skeleton, metric skeletons, list skeletons. |
| Empty | `ImperiumEmptyState`: title `No weekly review yet`, CTA `Back to Dashboard`. |
| Error | `ImperiumErrorState`: title `Weekly review unavailable`, retry visual only. |

### 6.9 Future endpoints

- `GET /api/imperium/weekly-review/state`
- `GET /api/imperium/weekly-review/history`
- `GET /api/imperium/weekly-review/current`
- `POST /api/imperium/weekly-review/launch`
- `GET /api/imperium/weekly-review/{session_id}/final-report`
- `GET /api/imperium/weekly-review/{session_id}/final-report/markdown`

### 6.10 DoD

- Weekly Summary, Wins, Failures, Improvement Suggestions et Statistics visibles.
- Start interactive review ne finalise rien localement.
- Stats clairement mock.
- Loading, empty, error rendus.
- Responsive tablette et telephone.

## 7. History Screen

### 7.1 Identity

| Champ | Valeur |
|---|---|
| Route ID | `IMP.HISTORY.MAIN` |
| Related canonical route | `IMP.PLAN.HISTORY` |
| Screen ID source | `IMP-05` |
| Route path | `imperium/history` |
| Titre visible | `History` |
| Type | Top-level route |

### 7.2 Objectif metier

Afficher l'historique des missions, plans, decisions et evenements Imperium sous forme chronologique. L'historique observe et explique ; il ne modifie pas la strategie. This screen is read-only.

### 7.3 Layout tablette

| Zone | Specification |
|---|---|
| Sidebar | Destination History active. |
| Main column | Max 880dp, timeline. |
| Context panel | 360dp, History Detail Card. |

Ordre tablette :

1. `ImperiumTopBar`.
2. Search.
3. Filters.
4. Timeline.
5. History Detail Card in context panel.

### 7.4 Layout telephone

Ordre telephone :

1. `ImperiumTopBar`.
2. Search.
3. Filters horizontal.
4. Timeline.
5. History Detail Card inline after selected event.
6. `ImperiumBottomNavigation`.

### 7.5 Composants

| Bloc | Composant autorise | Contenu obligatoire |
|---|---|---|
| Timeline | `ImperiumTimeline` | timestamp, event type, title, status. |
| Search | `ImperiumSearchField` | query, clear, result count. |
| Filters | `ImperiumFilterChip` | All, Missions, Decisions, Weekly, Failed. |
| History Detail Card | `ImperiumCard` | selected event details, source, linked route. |

### 7.6 Actions

| Action | UI | Effet Phase 1/2 | Backend Phase 3 future |
|---|---|---|---|
| Search history | search field | filters fixture. | server/local cache query. |
| Filter history | chips | filters fixture. | query params/cache filter. |
| Select event | timeline item | shows detail card. | fetch event/detail read model if needed. |
| Open linked mission | ghost/detail link | navigates mock to Mission Active only if the linked mission is the active mock id. | `IMP.MISSION.ACTIVE` if backend confirms active mission context. |

### 7.7 Mock data

Fixture locale canonique : `history_mock_v1`.

```json
{
  "screen_id": "IMP-05",
  "route_id": "IMP.HISTORY.MAIN",
  "screen": "IMP.HISTORY.MAIN",
  "fixture_name": "history_mock_v1",
  "sync_state": "mock",
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
      "source": "mission",
      "linked_mission_id": "mock-mission-010",
      "linked_route": "IMP.HISTORY.MAIN"
    },
    {
      "id": "mock-history-002",
      "type": "mission_failed",
      "title": "Evening review skipped",
      "status": "failed",
      "reason": "Fatigue after VTC shift",
      "occurred_at": "2026-05-31T22:40:00Z",
      "source": "mission",
      "linked_route": "IMP.HISTORY.MAIN"
    }
  ],
  "selected_event_id": "mock-history-001"
}
```

### 7.8 States

| State | Specification |
|---|---|
| Loading | Search disabled, timeline skeleton, detail card skeleton. |
| Empty | `ImperiumEmptyState`: title `No history yet`, CTA `Back to Dashboard`. |
| Error | `ImperiumErrorState`: title `History unavailable`, retry visual only. |

### 7.9 Future endpoints

- `GET /api/imperium/missions/history`
- `GET /api/imperium/daily-plan`
- `GET /api/imperium/day/plan`
- `TBD GET /api/imperium/history/events`
- `TBD GET /api/imperium/history/events/{event_id}`

### 7.10 DoD

- Timeline, Search, Filters et History Detail Card visibles.
- Timeline ordre chronologique clair.
- Detail card suit la selection.
- Loading, empty, error rendus.
- Aucune mutation possible.

## 8. Settings Screen

### 8.1 Identity

| Champ | Valeur |
|---|---|
| Route ID | `IMP.SETTINGS.CORE` |
| Screen ID source | `IMP-06` |
| Route path | `imperium/settings` |
| Titre visible | `Settings` |
| Type | Top-level route |

### 8.2 Objectif metier

Afficher les preferences frontend et les liens de configuration Imperium sans permettre a l'UI de modifier une regle canonique sans validation backend.

### 8.3 Layout tablette

| Zone | Specification |
|---|---|
| Sidebar | Destination Settings active. |
| Main column | Max 960dp, sections grid 2 colonnes. |
| Context panel | Aucun panel par defaut. |

Ordre tablette :

1. `ImperiumTopBar`.
2. `User` and `Theme` row.
3. `Notifications` and `Integrations` row.
4. `Security` and `Advanced` row.

### 8.4 Layout telephone

Ordre telephone :

1. `ImperiumTopBar`.
2. User.
3. Theme.
4. Notifications.
5. Integrations.
6. Security.
7. Advanced.
8. `ImperiumBottomNavigation`.

### 8.5 Sections minimum

| Section | Composant autorise | Contenu obligatoire |
|---|---|---|
| User | `ImperiumCard`, `ImperiumListItem` | display name mock, timezone, language. |
| Theme | `ImperiumSegmentedControl`, `ImperiumToggle` | mode system/light/dark mock, accent note. |
| Notifications | `ImperiumToggle` rows | morning check-in, weekly review, mission reminders. |
| Integrations | `ImperiumListItem` | n8n, PostgreSQL, AI router as status mock. |
| Security | `ImperiumListItem` | auth state redacted, session status mock. |
| Advanced | `ImperiumListItem`, `ImperiumAlertDialog` | priority rules link, cache mock, reset mock protected by dialog. |

### 8.6 Actions

| Action | UI | Effet Phase 1/2 | Backend Phase 3 future |
|---|---|---|---|
| Change theme | segmented control | local preview only. | persisted user preference. |
| Toggle notification | toggle | local visual only with mock chip. | settings patch. |
| Open priority rules | list item | navigates to documented route if available, otherwise snackbar mock. | `IMP.SETTINGS.PRIORITIES`. |
| Clear local mock cache | destructive in Advanced | confirmation dialog, visual only. | local cache operation, not backend strategy. |

### 8.7 Mock data

Fixture locale canonique : `settings_mock_v1`.

```json
{
  "screen_id": "IMP-06",
  "route_id": "IMP.SETTINGS.CORE",
  "screen": "IMP.SETTINGS.CORE",
  "fixture_name": "settings_mock_v1",
  "sync_state": "mock",
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

### 8.8 States

| State | Specification |
|---|---|
| Loading | Section skeleton cards, toggles disabled. |
| Empty | `ImperiumEmptyState`: title `Settings defaults not initialized`, CTA `Use mock defaults`. |
| Error | `ImperiumErrorState`: title `Settings unavailable`, no sensitive data exposed. |

### 8.9 Future endpoints

- `GET /api/imperium/frontend/app-manifest`
- `TBD GET /api/imperium/settings`
- `TBD PATCH /api/imperium/settings`
- `GET /api/imperium/decision-framework/priorities`
- `POST /api/imperium/decision-framework/priorities`

### 8.10 DoD

- User, Theme, Notifications, Integrations, Security et Advanced visibles.
- Toggles ne pretendent pas etre synchronises sans backend.
- Security ne montre aucun token, password, hash ou auth internals.
- Loading, empty, error rendus.
- Responsive tablette et telephone.

## 9. Navigation Contract

### 9.1 Stable Route IDs

| Screen | Screen ID | Stable Route ID | Path | Navigation exposure |
|---|---|---|---|---|
| Dashboard | `IMP-01` | `IMP.DASH.MAIN` | `imperium/dashboard` | Top-level. |
| Mission Active | `IMP-02` | `IMP.MISSION.ACTIVE` | `imperium/missions/active` | Top-level. |
| Inbox | `IMP-03` | `IMP.INBOX.MAIN` | `imperium/inbox` | Top-level. |
| Weekly Review | `IMP-04` | `IMP.WR.SUMMARY` | `imperium/weekly-review` | Top-level. |
| History | `IMP-05` | `IMP.HISTORY.MAIN` | `imperium/history` | Top-level. |
| Settings | `IMP-06` | `IMP.SETTINGS.CORE` | `imperium/settings` | Top-level. |

Existing canonical related routes remain valid:

- `IMP.PLAN.HISTORY`
- `IMP.WR.LIST`
- `IMP.WR.READ_ONLY`
- `IMP.WR.INTERACTIVE`
- `IMP.SETTINGS.PRIORITIES`
- `IMP.MISSION.OUTCOME`
- `IMP.REPLAN.VALIDATE`
- `IMP.DAY.FINISH`

### 9.2 Bottom Navigation

Telephone GO 65 bottom navigation contains exactly six visible items in this order:

| Order | Label | Route ID | Icon intent |
|---|---|---|---|
| 1 | Dashboard | `IMP.DASH.MAIN` | dashboard/home. |
| 2 | Mission Active | `IMP.MISSION.ACTIVE` | active mission. |
| 3 | Inbox | `IMP.INBOX.MAIN` | inbox/message. |
| 4 | Weekly Review | `IMP.WR.SUMMARY` | weekly review. |
| 5 | History | `IMP.HISTORY.MAIN` | timeline/history. |
| 6 | Settings | `IMP.SETTINGS.CORE` | settings. |

### 9.3 Sidebar Navigation

Tablet GO 65 sidebar contains exactly six visible items in this order:

| Order | Label | Route ID |
|---|---|---|
| 1 | Dashboard | `IMP.DASH.MAIN` |
| 2 | Mission Active | `IMP.MISSION.ACTIVE` |
| 3 | Inbox | `IMP.INBOX.MAIN` |
| 4 | Weekly Review | `IMP.WR.SUMMARY` |
| 5 | History | `IMP.HISTORY.MAIN` |
| 6 | Settings | `IMP.SETTINGS.CORE` |

The Mission item is enabled only when mock data has an active mission. If no active mission exists, it is disabled and Dashboard shows the empty state.

### 9.4 Top Bar

Every GO 65 screen uses `ImperiumTopBar`.

| Screen | Title | Leading action | Trailing action |
|---|---|---|---|
| Dashboard | `Imperium` | none | `SyncStateChip`. |
| Mission Active | `Mission active` | Back to Dashboard | `SyncStateChip`. |
| Inbox | `Inbox` | none on top-level, back only if opened as child | Voice icon button. |
| Weekly Review | `Weekly Review` | none | `SyncStateChip`. |
| History | `History` | none | filter icon if filters collapse. |
| Settings | `Settings` | none | none. |

### 9.5 Back Navigation

| From | Back target |
|---|---|
| `IMP.MISSION.ACTIVE` | Previous route if present, otherwise `IMP.DASH.MAIN`. |
| Mock preview detail inside Inbox | `IMP.INBOX.MAIN`. |
| Mock preview detail inside Weekly Review | `IMP.WR.SUMMARY`. |
| Mock preview detail inside History | `IMP.HISTORY.MAIN`. |
| Top-level routes | no back action in top bar. |

### 9.6 Deep Links

Deep links are allowed only for existing resource-oriented routes:

| Deep link | Target |
|---|---|
| `imperium://mission/active` | `IMP.MISSION.ACTIVE`. |
| `imperium://weekly-review/{session_id}` | `IMP.WR.READ_ONLY`. |
| `imperium://settings/priorities` | `IMP.SETTINGS.PRIORITIES`. |

No other deep link is allowed in GO 65.

## 10. Mock Data Contract

Mock data is documentary and local-only:

- no real API ;
- no backend ;
- no n8n ;
- no PostgreSQL ;
- no pgvector ;
- no canonical AI decision ;
- every fixture includes `sync_state: "mock"` ;
- every fixture includes `screen_id`, `route_id`, `screen` and `fixture_name` ;
- fixture IDs start with `mock-`.

### 10.1 Dashboard

```json
{
  "screen_id": "IMP-01",
  "route_id": "IMP.DASH.MAIN",
  "screen": "IMP.DASH.MAIN",
  "fixture_name": "dashboard_empty_v1",
  "sync_state": "mock",
  "active_mission": null,
  "daily_focus": {
    "label": "Waiting",
    "reason": "No backend-confirmed mission in this mock state."
  },
  "weekly_progress": {
    "missions_done": 0,
    "missions_failed": 0,
    "completion_percent": 0
  }
}
```

### 10.2 Mission

```json
{
  "screen_id": "IMP-02",
  "route_id": "IMP.MISSION.ACTIVE",
  "screen": "IMP.MISSION.ACTIVE",
  "fixture_name": "mission_active_empty_v1",
  "sync_state": "mock",
  "mission": null,
  "empty_state": {
    "title": "No active mission",
    "body": "Waiting for backend-confirmed next mission."
  }
}
```

### 10.3 Inbox

```json
{
  "screen_id": "IMP-03",
  "route_id": "IMP.INBOX.MAIN",
  "screen": "IMP.INBOX.MAIN",
  "fixture_name": "inbox_empty_v1",
  "sync_state": "mock",
  "filters": {
    "active": "all",
    "query": ""
  },
  "conversations": []
}
```

### 10.4 Weekly Review

```json
{
  "screen_id": "IMP-04",
  "route_id": "IMP.WR.SUMMARY",
  "screen": "IMP.WR.SUMMARY",
  "fixture_name": "weekly_review_empty_v1",
  "sync_state": "mock",
  "week": {
    "start": "2026-05-25",
    "end": "2026-05-31",
    "status": "not_started"
  },
  "summary": null,
  "wins": [],
  "failures": [],
  "improvement_suggestions": [],
  "statistics": {
    "missions_done": 0,
    "missions_failed": 0,
    "completion_percent": 0
  }
}
```

### 10.5 History

```json
{
  "screen_id": "IMP-05",
  "route_id": "IMP.HISTORY.MAIN",
  "screen": "IMP.HISTORY.MAIN",
  "fixture_name": "history_empty_v1",
  "sync_state": "mock",
  "filters": {
    "active": "all",
    "query": ""
  },
  "events": []
}
```

### 10.6 Settings

```json
{
  "screen_id": "IMP-06",
  "route_id": "IMP.SETTINGS.CORE",
  "screen": "IMP.SETTINGS.CORE",
  "fixture_name": "settings_empty_v1",
  "sync_state": "mock",
  "sections": [
    "user",
    "theme",
    "notifications",
    "integrations",
    "security",
    "advanced"
  ]
}
```

## 11. Screen Validation Checklist

Every screen must pass every item before Phase 3 backend wiring.

### 11.1 Detailed Screen Checklist

| Screen | Responsive tablette | Responsive telephone | Design System conforme | Component Catalog conforme | Navigation conforme | Loading state | Empty state | Error state | Mock data fonctionnelle |
|---|---|---|---|---|---|---|---|---|---|
| Dashboard | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Mission Active | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Inbox | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Weekly Review | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| History | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Settings | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

Additional validation rules:

- Dashboard must show no more than one active mission.
- Mission Active must be present in top-level bottom navigation and sidebar as `IMP-02`, without creating any second active mission.
- Inbox convert-to-mission action must remain backend-validated.
- Weekly Review must never finalize locally.
- History must remain read-only.
- Settings must never expose secrets or internal auth state.

### 11.2 Canonical Definition of Done Checklist

Each screen is done only when every canonical GO 64 criterion is validated:

| Criterion | Required |
|---|---|
| UI validée | YES |
| Navigation validée | YES |
| Responsive validé | YES |
| Loading validé | YES |
| Empty validé | YES |
| Error validé | YES |
| Mock data validée | YES |

This checklist is documentary only. It does not authorize Kotlin generation, Android runtime setup, Compose implementation, backend wiring, endpoint creation, model changes, schema changes or API contract changes.

**Document version :** 1.0
**Statut :** IMPERIUM FRONTEND SCREEN SPEC V1 — ready for future UI pure and mock-data generation, not backend wired.
