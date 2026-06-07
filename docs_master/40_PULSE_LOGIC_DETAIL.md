# 40 - Pulse Logic Detail

## 1. Purpose

Pulse is the **health, nutrition, and physical activity** module — the food,
body, workout, stock, pain, and health-support interface. It tracks everything
related to the body so that downstream AI decisions stay grounded in real data.

Pulse must remain **simple to interact with** (the user is often busy and tired)
but **comprehensive in tracking** (nothing should be left to guesswork).

Pulse **does not diagnose, does not invent health truth, and does not decide the
day alone**. It collects confirmed signals, shows practical recommendations, and
triggers backend workflows that Imperium may use for replanning.

For medical document analysis (a separate flow), see doc 34.

Canonical sources used by this V1 detail:

- `01_SIGNAL_VARIABLES_DICTIONARY.md`
- `07_ANDROID_APP_RESPONSIBILITIES.md`
- `37_GEMINI_VISION_PROMPTS.md`
- `43_IMPERIUM_LOGIC_DETAIL.md`
- `59_DESIGN_SYSTEM_V1_DRAFT.md`

---

## 2. Non-Negotiable Rules

```text
✅ Pulse can:
   - track meals, workouts, body composition, hydration, sleep
   - manage food stock with expiry tracking
   - propose meals based on stock + goals + medical rules
   - propose training adjustments based on recovery + energy
   - apply validated medical rules silently in suggestions
   - learn from logged patterns

❌ Pulse must never:
   - prescribe medication
   - diagnose conditions
   - replace a medical professional
   - shame the user about food choices
   - send guilt notifications
   - gamify weight loss with social pressure
   - compute energy_score on its own (energy_score is INPUT)
```

---

## 3. Authority Boundary

Pulse writes canonical records **only after backend validation**. Android screens
may create local drafts with `pending|syncing|synced|failed|conflict` labels, but
the backend remains the authority for:

- meal macros estimation storage
- food stock mutations
- workout completion and adaptation acceptance
- body snapshot persistence
- pain log persistence
- medical rule activation events from doc 34
- Imperium replan handoffs

Pulse recommendations are practical support, **not medical rulings**.

---

## 4. The Three Pulse Domains

```text
DOMAIN 1 — NUTRITION (full tracking)
  ├─ Meals (logged + AI-suggested)
  ├─ Macros: calories, protein, carbs, fat
  ├─ Food stock (kitchen inventory + expiry)
  ├─ Hydration (target + actual)
  └─ Constraints: medical rules, fasting periods (from Path)

DOMAIN 2 — TRAINING (full tracking)
  ├─ Workouts (planned + logged + adapted)
  ├─ Body composition (weight, body fat %, measurements)
  ├─ Recovery state (computed from workout intensity + time)
  ├─ Pain or limitation log
  └─ Goals (e.g. visible abs target)

DOMAIN 3 — DAILY SIGNALS
  ├─ energy_score (INPUT from Imperium morning popup)
  ├─ fatigue_signal (derived from energy_score + workout history)
  ├─ sleep_hours (lightweight log)
  └─ Consumed by: Imperium (planning), Pulse itself (workout adapt)
```

---

## 5. Energy Score: Input, Not Computed

```text
ARCHITECTURE NOTE:
Energy score is NOT computed by Pulse.
It is entered by the user every morning via the Imperium popup.

FLOW:
1. Morning: Imperium opens popup
   → "How's your energy? (0-10)"
   → "How did you sleep? (hours)"
   → Optional: pain, mood, special context

2. User submits → Imperium stores in imperium_morning_checkins

3. Pulse READS this data via shared backend
   → uses energy_score for workout adaptation
   → uses sleep_hours for recovery calculation

4. Pulse does NOT consume Vector signals.
   Pulse does NOT consume Vault signals (except food expenses, see §15.3).
   Pulse stays focused on body data.
```

This separation keeps each module's responsibility clean.

---

## 6. The Three Decision Layers

```text
LAYER 1 — DETERMINISTIC (no AI)
  ├─ Macro totals from logged meals
  ├─ Stock level alerts (item < threshold)
  ├─ Hydration progress vs target
  ├─ Recovery time computation (workout end + 24-72h)
  └─ Cost: 0€

LAYER 2 — QWEN LOCAL
  ├─ Meal suggestions from stock + goals + rules
  ├─ Workout adaptation (light intensity if fatigue high)
  ├─ Food categorization on receipt scan
  └─ Cost: 0€

LAYER 3 — DEFERRED CLOUD
  ├─ Medical document analysis → GPT-5.5 (doc 34)
  ├─ Weekly review contribution → Opus via WR (doc 32)
  └─ Long-term plan adjustment → Sonnet 4.6
```

---

## 7. Events

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
| `pulse.medical_rule.activated` | Medical rule validated (doc 34) | Imperium may trigger replan. |

All mutation endpoints require `Idempotency-Key`.

---

## 8. Offline And Conflict Rules

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

---

## 9. Dashboard Read Model

Pulse dashboard combines today-only operational signals:

- meals logged today and macro totals
- hydration total and target state
- workout of the day or recovery state
- health_score with confidence and positive/negative factors
- stock expiring soon
- active fasting constraints from Path
- active medical rules summary from doc 34
- high-severity pain banner when unresolved

**Health score must never render without explanation.** If factors are missing,
the score card is hidden and an incomplete-data banner is shown.

---

## 10. Meal Tracking

### 10.1 Add Meal

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
| `confidence` | `low\|medium\|high` or decimal normalized by backend. |
| `source` | `text\|voice\|photo\|manual`. |
| `requires_user_validation` | Always true for AI-estimated macros. |
| `warnings` | Low confidence, missing quantity, image quality, or unusual estimate. |

### 10.2 Meal Confirmation

PUL-03 is independent from VAU-05. It is the post-Add-Meal confirmation screen,
not a second receipt validation screen.

The user can edit: meal label, quantity/portion, calories, protein_g, carbs_g,
fat_g, and stock decrement lines.

```text
TBD POST /api/pulse/meals/{meal_draft_id}/confirm
Headers: Idempotency-Key
```

### 10.3 Stock Decrement After Meal

Stock decrement is user-confirmed and idempotent. AI may suggest stock matches,
but no stock quantity changes until the user validates the lines.

```text
- proposed matches use stock item id, quantity, unit, and confidence
- low confidence lines default unchecked
- insufficient stock shows Warning, not hard block
- user can decrement to zero only with explicit confirmation
- each decrement write stores stock_decrement_applied = true for the meal confirmation id
- repeated confirmation with same Idempotency-Key returns the original result
- repeated confirmation with different payload creates Conflict
```

---

## 11. Food Stock

### 11.1 Stock sources

| Source | Flow |
|---|---|
| Manual add/edit | PUL-12 Stock Tab opens stock item edit/add surface. |
| Vault receipt handoff | VAU-05 validates receipt; backend creates Pulse draft/stock update without second receipt UI. |
| Pantry scan | PUL-13 uses Gemini task `pulse.kitchen_inventory_photo`; user validates diff. |
| Meal decrement | PUL-03 confirmed stock lines decrement quantities. |

### 11.2 Stock item fields (V1)

```text
stock_item_id, stock_item_name, stock_quantity, stock_unit,
stock_expiry_type (DLC|DDM|unknown), stock_expiry_date,
category, confidence, source
```

### 11.3 Expiry alerts

```text
Daily cron at 09:00 Europe/Paris (deterministic, no AI):
  - DLC in 0-2 days        → Warning banner
  - expired DLC            → Error banner
  - DDM in 0-7 days        → Info or Warning depending on backend policy
  → Surface in Pulse banner: "N items à consommer rapidement"
```

### 11.4 Anti-waste meal suggestions

When stock contains items expiring soon:

```text
Qwen called when user asks "what should I eat?"
  Inputs:
    - current stock with expiry dates
    - recent meals (last 3 days)
    - active medical rules
    - fasting state (from Path)
    - user goals (abs visible, etc.)
  Output:
    - 1-3 meal suggestions
    - prioritizes items expiring soon
    - respects medical rules
    - respects fasting if active
```

---

## 12. Hydration

PUL-04 supports quick buttons: `+250ml`, `+500ml`, `+1L`.

```text
TBD POST /api/pulse/hydration-logs
Headers: Idempotency-Key
```

Payload stores `amount_ml`, `logged_at`, `source`, and Path constraint context.

```text
target_liters_per_day:
  - default: 3.5L (per medical rule baseline)
  - overridden by active medical rules
```

If `fasting_active = true` and `hydration_limits.daytime = false`, the buttons
are disabled during the fasting window and the UI shows:

```text
Jeûne en cours - hydratation hors fenêtre désactivée.
```

The user may still add a historical hydration log outside the prohibited window
if the timestamp is valid. Offline rule: hydration sum merge adds distinct queued
logs after sync and dedupes identical `Idempotency-Key` writes.

---

## 13. Workouts

### 13.1 Plan Workout (PUL-05)

```text
- title
- scheduled date/time
- duration minutes
- intensity low|medium|high
- exercises list
- equipment chips
- optional source mission

TBD POST /api/pulse/workouts
Headers: Idempotency-Key
```

Workouts can be planned manually by the user, or proposed by Pulse based on:
energy_score (Imperium morning popup), recovery state, active medical rules
(training caps), fasting state, and weekly objectives.

### 13.2 Log Workout (PUL-06)

```text
- start
- pause/resume
- set/reps completion
- perceived intensity
- skip exercise with reason
- finish workout

TBD POST /api/pulse/workouts/{workout_id}/complete
Headers: Idempotency-Key
```

The `workouts` table tracks: title, status (`planned|in_progress|completed|
skipped`), planned_at/started_at/completed_at, duration_minutes, intensity_score
(1-10), exercises_json, body_state_at_start, notes_post_workout.

### 13.3 Workout Adaptation (PUL-07)

Adaptation is **suggested, not forced**. Triggers:

- fatigue_state high or energy below backend threshold
- known pain or injury affects planned exercise
- fasting_active and workout intensity is medium/high
- available_equipment no longer matches the plan
- unexpected event or Imperium replan context

V1 threshold rule:

```text
- energy scale 1-10: energy <= 3 requests adaptation
- fatigue enum: high requests adaptation
- any pain severity >= 7 requests adaptation
- fasting_active downgrades high intensity to low/medium suggestion
```

```text
TBD POST /api/pulse/workouts/{workout_id}/adaptation/accept
TBD POST /api/pulse/workouts/{workout_id}/adaptation/reject
Headers: Idempotency-Key
```

Decision is NEVER auto-applied. If the user refuses, the original workout remains
and the backend records the decision. Imperium replan is a backend handoff
surfaced by a toast/banner only.

### 13.4 Recovery computation

```text
deterministic rule:
  recovery_complete_at = workout.completed_at + recovery_hours
  recovery_hours depends on intensity:
    - intensity 1-3: 12h
    - intensity 4-6: 24h
    - intensity 7-8: 48h
    - intensity 9-10: 72h

Within recovery period:
  - Pulse warns if user plans intense workout
  - Pulse does NOT block (user decides)
```

---

## 14. Body Snapshot (PUL-08)

Captures: weight, optional waist/chest/arm measurements, optional notes, optional
local photo reference.

```text
TBD POST /api/pulse/body-snapshots
Headers: Idempotency-Key
```

**Body photo upload is disabled in V1.** The Android app may keep a local-only
photo reference for comparison, but the backend payload must not include the
binary, remote URI, or Gemini analysis request.

Body snapshot data is high privacy. It can be used for user-confirmed progress
visibility but **not for automatic medical conclusions**. Frequency is
user-driven; no notifications push measurement. Trends shown in Pulse history
view, no AI processing in V1.

---

## 15. Integration With Other Modules

### 15.1 With Imperium

```text
Pulse READS from Imperium:
  - imperium_morning_checkins.energy_score
  - imperium_morning_checkins.sleep_hours
  - imperium_daily_plans (to align workout timing)

Pulse EMITS events Imperium subscribes to:
  - pulse.workout.completed (Imperium logs success)
  - pulse.workout.skipped (Imperium notes failure reason)
  - pulse.medical_rule.activated (Imperium may trigger replan)
  - pulse.pain.logged severity 8-10 (Imperium replan prompt)
```

### 15.2 With Path

```text
Pulse READS from Path:
  - fasting_active
  - fasting_type
  - suhoor_time / iftar_time
  - hydration_limits

Pulse adapts:
  - meal suggestions (none during fasting hours; historical logging allowed with warning, never silently blocked)
  - workout intensity (lighter on fasting days)
  - hydration logging (only allowed window)
  - dashboard displays one fasting banner maximum
```

### 15.3 With Vault

```text
Pulse READS from Vault:
  - food_related_expenses (last 30 days)

Vault → Pulse handoff (receipt):
  - VAU-05 remains the ONLY receipt review screen in V1
  - when VAU-05 validates food lines, backend creates a Pulse handoff
    (stock additions/updates, source reference, confidence/warnings, sync state)
  - PUL-12 may display a badge for received handoffs;
    it does NOT ask the user to validate the same receipt again
```

### 15.4 With Vector

```text
Pulse and Vector are deliberately decoupled.
Vector does NOT consume energy_score (per doc 33 §5.2.3).
The only indirect link: Imperium uses both for daily planning.
```

---

## 16. Pain Log (PUL-09)

Captures: body zone, severity 0-10, pain type if known, limitation notes, voice
note transcript if used, current workout impact.

```text
TBD POST /api/pulse/pain-logs
Headers: Idempotency-Key
```

Severity rules:

```text
- 0-3:  normal log
- 4-7:  Warning and optional workout adaptation prompt
- 8-10: Error banner and user-confirmed Imperium replan prompt
```

Pulse does not diagnose. Pain logs are constraints for planning and workout
safety only.

---

## 17. Recommendations

Pulse recommendation requests are **explicit user actions**. They can originate
from PUL-10 (meal suggestions), PUL-11 (workout suggestions), PUL-12 (stock usage
suggestions), or PUL-01 (dashboard suggestion CTA).

```text
TBD POST /api/pulse/recommendations
Headers: Idempotency-Key
```

The response must include explanation and confidence. Recommendations cannot
override Imperium mission priority without backend validation.

---

## 18. Pulse AI Task Types & Routing

### 18.1 Task types

```text
pulse.meal_estimate              - estimate calories/macros from text
pulse.meal_photo_macros          - estimate macros from meal photo (Gemini)
pulse.meal_suggestion            - propose meal from stock + goals
pulse.training_adjustment        - adapt workout to current state
pulse.medical_document_extract   - delegated to GPT-5.5 (doc 34)
pulse.kitchen_inventory_photo    - parse fridge/pantry image (Gemini)
pulse.weekly_review_contribution - feeds the WR (Opus via doc 32)
```

### 18.2 Routing distribution

```text
Daily ops (88%):    Qwen local
Quick adapts (8%):  Haiku 4.5
Weekly plans (2%):  Sonnet 4.6
Receipt OCR (1%):   Gemini
Medical (0.5%):     GPT-5.5 (static override)
WR (0.5%):          Opus 4.7 (via WR workflow)
```

---

## 19. Database Tables

Most tables already exist (per doc 05). Confirmed structure: `meals` ✅,
`workouts` ✅, `food_stock_items` ✅, `pulse_recommendations` ✅.

New tables to add:

```sql
-- Body composition snapshots
CREATE TABLE body_snapshots (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  measured_at     TIMESTAMPTZ NOT NULL,
  weight_kg       NUMERIC(5,2),
  body_fat_percent NUMERIC(4,2) NULL,
  waist_cm        NUMERIC(5,1) NULL,
  chest_cm        NUMERIC(5,1) NULL,
  photo_uri       TEXT NULL,
  notes           TEXT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Hydration log
CREATE TABLE hydration_logs (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  logged_at   TIMESTAMPTZ NOT NULL,
  amount_ml   INTEGER NOT NULL,
  source      VARCHAR(32),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Pain / limitation log
CREATE TABLE pulse_pain_logs (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  body_area   VARCHAR(64),
  severity    INTEGER,  -- 0-10
  noted_at    TIMESTAMPTZ NOT NULL,
  resolved_at TIMESTAMPTZ NULL,
  notes       TEXT NULL
);

-- Medical rules: defined in doc 34 §12.2
```

---

## 20. Pulse UI Surface (V1)

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

---

## 21. Endpoint Matrix

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

---

## 22. Open V2 Items

```text
- wearable connection screen
- supplement note dedicated screen
- remote body photo upload
- automatic body composition analysis
- advanced nutrition database integration
- batch cooking planner UI
```

---

## 23. References

- `34_PULSE_MEDICAL_FEED_AI.md` — medical document analysis
- `30_AI_ROUTING_AND_SCORING_POLICY.md` — routing rules
- `31_AI_TASKS_AND_RESULTS_CONTRACT.md` — task contracts
- `37_GEMINI_VISION_PROMPTS.md` — meal photo / pantry scan prompts
- `41_PATH_LOGIC_DETAIL.md` — fasting and hydration constraints
- `42_VAULT_LOGIC_DETAIL.md` — receipt handoff source
- `43_IMPERIUM_LOGIC_DETAIL.md` — energy_score popup origin
- `01_SIGNAL_VARIABLES_DICTIONARY.md` — full signal list
- `59_DESIGN_SYSTEM_V1_DRAFT.md` — PUL screens design

---

**Document version:** 2.0 (merged — logic/architecture + V1 implementation contracts)
**Status:** Pulse V1 reference
**Last updated:** 2026-06-06
