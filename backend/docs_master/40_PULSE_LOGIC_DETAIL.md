# 40 - Pulse Logic Detail

## 1. Purpose

Pulse is the food, body, workout, stock, pain, and health-support interface.

Pulse does not diagnose, does not invent health truth, and does not decide the
day alone. It collects confirmed signals, shows practical recommendations, and
triggers backend workflows that Imperium may use for replanning.

Canonical sources used by this V1 detail:

- `01_SIGNAL_VARIABLES_DICTIONARY.md`
- `07_ANDROID_APP_RESPONSIBILITIES.md`
- `37_GEMINI_VISION_PROMPTS.md`
- `43_IMPERIUM_LOGIC_DETAIL.md`
- `59_DESIGN_SYSTEM_V1_DRAFT.md`

## 2. Authority Boundary

Pulse writes canonical records only after backend validation. Android screens may
create local drafts with `pending|syncing|synced|failed|conflict` labels, but the
backend remains the authority for:

- meal macros estimation storage
- food stock mutations
- workout completion and adaptation acceptance
- body snapshot persistence
- pain log persistence
- medical rule activation events from doc 34
- Imperium replan handoffs

Pulse recommendations are practical support, not medical rulings.

## 3. Events

Pulse V1 may emit:

| Event | Trigger | Notes |
|---|---|---|
| `pulse.meal.logged` | Meal confirmed by user | Backend stores macros, confidence, and optional stock decrement. |
| `pulse.food_stock.updated` | Stock item create/update/decrement validated | Source can be manual, Vault receipt handoff, or pantry scan. |
| `pulse.hydration.logged` | Hydration quick action confirmed or queued | Offline entries use hydration sum merge on sync. |
| `pulse.workout.completed` | Workout completion confirmed | Imperium adjusts energy expectations. |
| `pulse.workout.skipped` | Workout skipped with reason | Imperium may replan if workout was central. |
| `pulse.workout.adaptation.accepted` | User accepts adaptation proposal | Backend may emit Imperium replan request. |
| `pulse.body_snapshot.created` | User confirms body snapshot | Photo binary is local-only in V1. |
| `pulse.pain.logged` | Pain log confirmed | Severity 8-10 opens a user-confirmed Imperium replan prompt. |
| `pulse.recommendation.requested` | User asks for Pulse suggestion | Backend routes model; UI displays explanation. |

All mutation endpoints require `Idempotency-Key`.

## 4. Offline And Conflict Rules

Pulse has many same-day mutations, so V1 uses type-specific conflict handling:

| Mutation | Offline behavior | Conflict rule |
|---|---|---|
| Meal draft | Queue local draft; no stock decrement until confirmation syncs | Same `Idempotency-Key` returns stored result; different payload opens diff. |
| Meal confirmation | Queue confirmation payload with macro edits and stock lines | `stock_decrement_applied` prevents double decrement. |
| Hydration log | Queue individual quick logs | Same key dedupes; separate valid keys use hydration sum merge. |
| Workout completion | Continue local workout log | Server completed/cancelled conflict opens user diff; no silent overwrite. |
| Workout adaptation | Queue accept/reject only if proposal id matches | Stale proposal is rejected with conflict. |
| Body snapshot | Queue numeric fields; photo remains local-only V1 | Same date conflict opens diff, latest is not auto-won. |
| Pain log | Queue with severity and notes | Severity 8-10 triggers replan prompt after successful sync, debounced once per pain log. |
| Stock update | Queue line-level update | Quantity is patched with version; negative stock requires explicit user override. |
| Medical rule | Offline upload disabled in V1 | Rules activate only after doc 34 validation flow. |

## 5. Dashboard Read Model

Pulse dashboard combines today-only operational signals:

- meals logged today and macro totals
- hydration total and target state
- workout of the day or recovery state
- health_score with confidence and positive/negative factors
- stock expiring soon
- active fasting constraints from Path
- active medical rules summary from doc 34
- high-severity pain banner when unresolved

Health score must never render without explanation. If factors are missing, the
score card is hidden and an incomplete-data banner is shown.

## 6. Meals And Macros

### 6.1 Add Meal

Supported V1 inputs:

- text description
- voice note transcribed by Whisper/faster-whisper
- meal photo processed by Gemini prompt `pulse.meal_photo_macros`

The backend creates a meal draft through `TBD POST /api/pulse/meals/estimate`.
The draft contains:

| Field | Rule |
|---|---|
| `meal_draft_id` | Backend generated. |
| `description` | User text/transcript or image summary. |
| `macros` | calories, protein_g, carbs_g, fat_g. |
| `confidence` | `low|medium|high` or decimal normalized by backend. |
| `source` | `text|voice|photo|manual`. |
| `requires_user_validation` | Always true for AI-estimated macros. |
| `warnings` | Low confidence, missing quantity, image quality, or unusual estimate. |

### 6.2 Meal Confirmation

PUL-03 is independent from VAU-05. It is the post Add Meal confirmation screen,
not a second receipt validation screen.

The user can edit:

- meal label
- quantity/portion
- calories
- protein_g
- carbs_g
- fat_g
- stock decrement lines

Confirmation endpoint:

```text
TBD POST /api/pulse/meals/{meal_draft_id}/confirm
Headers: Idempotency-Key
```

### 6.3 Stock Decrement After Meal

Stock decrement is user-confirmed and idempotent. AI may suggest stock matches,
but no stock quantity changes until the user validates the lines.

Rules:

- proposed matches use stock item id, quantity, unit, and confidence
- low confidence lines default unchecked
- insufficient stock shows Warning, not hard block
- user can decrement to zero only with explicit confirmation
- each decrement write stores `stock_decrement_applied = true` for the meal confirmation id
- repeated confirmation with same `Idempotency-Key` returns the original result
- repeated confirmation with different payload creates Conflict

## 7. Food Stock

Stock sources:

| Source | Flow |
|---|---|
| Manual add/edit | PUL-12 Stock Tab opens stock item edit/add surface. |
| Vault receipt handoff | VAU-05 validates receipt; backend creates Pulse draft/stock update without second receipt UI. |
| Pantry scan | PUL-13 uses Gemini task `pulse.kitchen_inventory_photo`; user validates diff. |
| Meal decrement | PUL-03 confirmed stock lines decrement quantities. |

Stock item fields V1:

- `stock_item_id`
- `stock_item_name`
- `stock_quantity`
- `stock_unit`
- `stock_expiry_type` with `DLC|DDM|unknown`
- `stock_expiry_date`
- `category`
- `confidence`
- `source`

Expiring soon:

- DLC in 0-2 days uses Warning banner
- expired DLC uses Error banner
- DDM in 0-7 days uses Info or Warning depending on backend policy

## 8. Hydration

PUL-04 supports quick buttons:

- `+250ml`
- `+500ml`
- `+1L`

Endpoint:

```text
TBD POST /api/pulse/hydration-logs
Headers: Idempotency-Key
```

Payload stores amount_ml, logged_at, source, and Path constraint context.

If `fasting_active = true` and `hydration_limits.daytime = false`, the buttons
are disabled during the fasting window and the UI shows:

```text
Jeune en cours - hydratation hors fenetre desactivee.
```

The user may still add a historical hydration log outside the prohibited window
if the timestamp is valid.

Offline rule: hydration sum merge adds distinct queued logs after sync and
dedupes identical `Idempotency-Key` writes.

## 9. Workouts

### 9.1 Plan Workout

PUL-05 supports a simple V1 workout plan:

- title
- scheduled date/time
- duration minutes
- intensity `low|medium|high`
- exercises list
- equipment chips
- optional source mission

Endpoint:

```text
TBD POST /api/pulse/workouts
Headers: Idempotency-Key
```

### 9.2 Log Workout

PUL-06 supports:

- start
- pause/resume
- set/reps completion
- perceived intensity
- skip exercise with reason
- finish workout

Completion endpoint:

```text
TBD POST /api/pulse/workouts/{workout_id}/complete
Headers: Idempotency-Key
```

### 9.3 Workout Adaptation

Adaptation is suggested, not forced. Triggers:

- fatigue_state high or energy below backend threshold
- known pain or injury affects planned exercise
- fasting_active and workout intensity is medium/high
- available_equipment no longer matches the plan
- unexpected event or Imperium replan context

V1 threshold rule:

- if energy scale is 1-10, `energy <= 3` requests adaptation
- if fatigue enum is used, `high` requests adaptation
- any pain severity `>= 7` requests adaptation
- fasting_active downgrades high intensity to low/medium suggestion

Acceptance endpoint:

```text
TBD POST /api/pulse/workouts/{workout_id}/adaptation/accept
Headers: Idempotency-Key
```

Reject endpoint:

```text
TBD POST /api/pulse/workouts/{workout_id}/adaptation/reject
Headers: Idempotency-Key
```

If the user refuses, the original workout remains and the backend records the
decision. Imperium replan is a backend handoff surfaced by a toast/banner only.

## 10. Body Snapshot

PUL-08 captures:

- weight
- optional waist/chest/arm measurements
- optional notes
- optional local photo reference

Body photo upload is disabled in V1. The Android app may keep a local-only photo
reference for comparison, but the backend payload must not include the binary,
remote URI, or Gemini analysis request.

Endpoint:

```text
TBD POST /api/pulse/body-snapshots
Headers: Idempotency-Key
```

Body snapshot data is high privacy. It can be used for user-confirmed progress
visibility but not for automatic medical conclusions.

## 11. Recommendations

Pulse recommendation requests are explicit user actions. They can originate from:

- PUL-10 meal suggestions
- PUL-11 workout suggestions
- PUL-12 stock usage suggestions
- PUL-01 dashboard suggestion CTA

Endpoint:

```text
TBD POST /api/pulse/recommendations
Headers: Idempotency-Key
```

The response must include explanation and confidence. Recommendations cannot
override Imperium mission priority without backend validation.

## 12. Path Constraints

Pulse consumes Path signals:

- `fasting_active`
- `fasting_type`
- `suhoor_time`
- `iftar_time`
- `hydration_limits`

Effects:

- hydration quick buttons disable during restricted fasting windows
- meal logging outside iftar-to-suhoor is allowed only as historical logging or
  with a warning, never silently blocked
- workout adaptation includes fasting context
- dashboard displays one fasting banner maximum

## 13. Vault Handoff

Vault receipt validation remains the only receipt review screen in V1. When
VAU-05 validates food lines, the backend creates a Pulse handoff:

- stock item additions or updates
- source reference to receipt extraction
- confidence/warnings
- sync state

PUL-12 may display a badge for received handoffs, but it does not ask the user to
validate the same receipt again.

## 14. Pain Log

PUL-09 captures:

- body zone
- severity 0-10
- pain type if known
- limitation notes
- voice note transcript if used
- current workout impact

Endpoint:

```text
TBD POST /api/pulse/pain-logs
Headers: Idempotency-Key
```

Severity rules:

- 0-3: normal log
- 4-7: Warning and optional workout adaptation prompt
- 8-10: Error banner and user-confirmed Imperium replan prompt

Pulse does not diagnose. Pain logs are constraints for planning and workout
safety only.

## 15. Pulse UI Surface

Canonical Pulse V1 screens:

| Screen | Purpose |
|---|---|
| PUL-01 | Dashboard: today overview, health score explanation, banners. |
| PUL-02 | Add meal from text, voice, or photo. |
| PUL-03 | Confirm meal macros and optional stock decrement. |
| PUL-04 | Hydration quick log. |
| PUL-05 | Add or plan workout. |
| PUL-06 | Workout logging. |
| PUL-07 | Workout adaptation proposal. |
| PUL-08 | Body snapshot entry. |
| PUL-09 | Pain log entry. |
| PUL-10 | Meals tab and history. |
| PUL-11 | Workouts tab and history. |
| PUL-12 | Stock tab. |
| PUL-13 | Scan pantry/fridge. |
| PUL-14 | Medical tab, driven by doc 34. |

Sub-surfaces PUL-10b/11b/12b/14b-14e are V1 detail states inside the parent
tabs, not additional top-level counted screens. If product promotes them later,
the screen inventory must be renumbered.

## 16. Endpoint Matrix

This document names backend contracts for UI generation. Endpoints marked `TBD`
must be implemented in backend patches before UI relies on them.

| Domain | Endpoint |
|---|---|
| Dashboard | `TBD GET /api/pulse/dashboard` |
| Meals | `TBD POST /api/pulse/meals/estimate` |
| Meals | `TBD POST /api/pulse/meals/{meal_draft_id}/confirm` |
| Meals | `TBD GET /api/pulse/meals` |
| Hydration | `TBD POST /api/pulse/hydration-logs` |
| Workouts | `TBD GET /api/pulse/workouts` |
| Workouts | `TBD POST /api/pulse/workouts` |
| Workouts | `TBD POST /api/pulse/workouts/{workout_id}/complete` |
| Workouts | `TBD POST /api/pulse/workouts/{workout_id}/adaptation/accept` |
| Workouts | `TBD POST /api/pulse/workouts/{workout_id}/adaptation/reject` |
| Body | `TBD POST /api/pulse/body-snapshots` |
| Pain | `TBD POST /api/pulse/pain-logs` |
| Stock | `TBD GET /api/pulse/food-stock` |
| Stock | `TBD POST /api/pulse/food-stock` |
| Stock | `TBD PATCH /api/pulse/food-stock/{stock_item_id}` |
| Stock | `TBD POST /api/pulse/food-stock/scan` |
| Stock | `TBD POST /api/pulse/food-stock/scans/{scan_id}/validate` |
| Vault handoff | `TBD POST /api/pulse/food-stock/drafts/confirm` |
| Medical | `TBD GET /api/pulse/medical-documents` |
| Medical | `TBD POST /api/pulse/medical-documents` |
| Medical | `TBD GET /api/pulse/medical-rules/active` |
| Medical | `TBD POST /api/pulse/medical-rules/{rule_id}/activate` |
| Recommendations | `TBD POST /api/pulse/recommendations` |

## 17. Open V2 Items

- wearable connection screen
- supplement note dedicated screen
- remote body photo upload
- automatic body composition analysis
- advanced nutrition database integration
- batch cooking planner UI

