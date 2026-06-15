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
  ├─ Recovery state (personalized forecast frame + Qwen day-to-day adjustment)
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
  ├─ Workout / recovery display from the current personalized frame
  └─ Cost: 0€

LAYER 2 — QWEN LOCAL
  ├─ Meal suggestions from stock + goals + rules
  ├─ Workout adaptation (Qwen self-scores capability, escalates if needed)
  ├─ Food categorization on receipt scan
  └─ Cost: 0€

LAYER 3 — DEFERRED CLOUD
  ├─ Medical document analysis → GPT-5.5 (doc 34)
  ├─ Weekly review contribution → Opus via WR (doc 32)
  └─ Health program creation/revision → GPT-5.5
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
| `pulse.pain.logged` | Pain log confirmed | Pain data is interpreted by Qwen; escalation follows model scoring, not a hard severity threshold. |
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
| Pain log | Queue with zone, severity, impact, and notes | Sync stores data; Qwen interpretation/escalation is not a hard offline threshold. |
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
- unresolved pain banner when Qwen interpretation marks it relevant

**Health score must never render without explanation.** If factors are missing,
the score card is hidden and an incomplete-data banner is shown.

---

## 10. Meal Tracking

### 10.1 Add Meal

Supported V1 inputs:

- chatbot text description (primary natural-language path)
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
| `source` | `chatbot\|text\|voice\|photo\|manual`. |
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

### 10.4 Recipe catalogue

```text
A catalogue of recipes provided by the user via: chatbot | internet search |
OCR | the "Nourrir l'IA" button (present in every app).

Adding a recipe is a LIGHT conversational capture:
- The AI that fetches the recipe (web search) discusses ONLY the recipe with the
  user. It does NOT cross-check the current diet at this stage (that would force a
  GPT-5.5 diet call — not wanted here).
- WHO: Qwen local (with a web search tool) finds the recipe; escalates to GPT-5.5
  only if genuinely needed. No diet reasoning at add-time.
- The user validates / modifies (e.g. "yes, but oregano instead of coriander").
- On validation → stored in the recipe catalogue.

The catalogue is then AVAILABLE to GPT-5.5 when it programs the diet (below).
```

### 10.5 Raw stock (matières premières)

```text
Stock holds RAW ingredients (matières premières). Sources:
- OCR receipt (Vault handoff) | manual entry | chatbot | pantry scan (Gemini)
Stock is the raw material the weekly program draws from.
```

### 10.6 Weekly diet programming

```text
WHEN  : start of week, aligned to the Weekly Review (GPT-5.5 grouped call, same
        model as the workout — rare, planned).
WHO   : GPT-5.5 (health + diet reasoning).
INPUTS: nutrition goals + current raw stock + recipe catalogue.
OUTPUT (three things):
  1. RECIPES OF THE WEEK
  2. If raw stock is INSUFFICIENT for the recipes → a SHOPPING LIST (see §10.7)
  3. A "CUISINER" (batch cooking) mission for Imperium (see §10.8)
```

### 10.7 Shopping list

```text
Generated when raw stock is insufficient for the week's recipes.

NO prior validation. The user does the shopping and decides on the ground what he
buys (a product may be missing, or replaced by another — his freedom).

When he finishes shopping and UPDATES his stock:
- everything bought → enters stock AND disappears from the list
- everything not bought → stays on the list
The user decides when/if he buys the rest; he can also remove an item by force
via the chatbot.

→ The list self-empties as stock is updated; it follows reality, no friction.

LEARNING: items the user systematically does NOT buy are data for the WR. The AI
may ask "you never buy what I suggest — is there a reason?" and learn (dislike,
too expensive, unavailable nearby...). Same pattern as Vector (proposed vs done
gap → WR learning). The raw datum stays; the brain analyzes it in the WR; the
user stays free.
```

### 10.8 Batch cooking mission + smart storage

```text
A start-of-week Imperium mission "CUISINER" (batch cooking): cook ALL the week's
meals at once.

Storage: sterilized glass jars, ~1 week shelf life, kept in the CAR'S UNDER-TRUNK
— the A/C ducts run through it, so it stays at ambient temperature even in heat,
shielded from sunlight. → a meal reserve accessible all day, wherever the user is.

Result: balanced, cheap, ready meals all week, eaten during the VTC day (Vector).
Economy + nutrition + health in one loop.
```

### 10.9 Nutrition / batch cooking loop

```text
Start of week (on WR) → GPT-5.5 crosses goals + stock + catalogue
  ├─ recipes of the week
  ├─ if stock insufficient → shopping list → Imperium "faire les courses"
  │     (no validation; stock update empties the list; non-buys feed WR learning)
  └─ Imperium "cuisiner" (batch cooking) → glass jars → car under-trunk
        → the week's food, accessible everywhere during VTC
```

Cross-module links:
- Vault → stock (OCR receipts).
- Imperium → carries the "faire les courses" and "cuisiner" missions, placed in
  the week by the brain (day-continuity, like other missions).
- Vector → meals eaten during the VTC session (under-trunk reserve).
- Recipe add = Qwen local + web (light); diet programming = GPT-5.5 (grouped, on
  the WR). Clean separation: collection (light) vs exploitation (GPT-5.5).

---

## 11. Food Stock

### 11.1 Stock sources

| Source | Flow |
|---|---|
| Manual add/edit | PUL-12 Stock Tab opens stock item edit/add surface. |
| Vault receipt handoff | VAU-05 validates receipt; backend creates Pulse draft/stock update without second receipt UI. |
| Pantry scan | PUL-13 uses Gemini task `pulse.kitchen_inventory_photo`; user validates diff. |
| Chatbot | User declares stock in natural language ("j'ai acheté 2kg de riz"); backend updates stock. |
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

The workout program has three explicit modes:

```text
MODE 1 — CREATION (one-off, at start)
  WHO    : GPT-5.5 (health), CONVERSATIONAL with the user, user validates.
  INPUTS : goals, level, owned equipment (§13-EQUIP), available time, fatigue.
  OUTPUT : base program + a PERSONALIZED forecast frame (per-person intensities
           and recovery — NOT generic rules).
  NOTE   : GPT-5.5 uses owned equipment CREATIVELY — the user declares raw
           equipment, GPT-5.5 derives many exercises from it (a push-up board →
           push-ups AND core work; a 20kg handled dumbbell → halo AND more).

MODE 2 — DAILY ADAPTATION (reactive) — see §13.3

MODE 3 — GLOBAL REVISION (proactive, MONTHLY ~4 weeks) — see §13-REVISION
```

Manual user-planned workouts remain possible.

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

```text
An adaptation hook is triggered (triggers list below).
  → QWEN evaluates whether it can adapt (it scores its OWN capability, as
    everywhere in the ecosystem):
      • capable (within reach) → it adapts locally (free)
      • out of reach (complex/health-heavy) → it escalates to GPT-5.5
  Adaptation is SUGGESTED, never forced. The user validates (accept/reject
  endpoints kept). Never auto-applied.

No CatBoost here: the ecosystem already relies on Qwen scoring its own ability;
adding CatBoost would duplicate that. CatBoost stays Vector-only (ride scoring).

Adaptation triggers (hooks):
  - fatigue / low readiness
  - pain or injury affecting SPECIFIC planned exercises (not a global block)
  - fasting active vs planned intensity
  - owned/available equipment no longer matches the plan
  - unexpected event or Imperium replan context
```

```text
TBD POST /api/pulse/workouts/{workout_id}/adaptation/accept
TBD POST /api/pulse/workouts/{workout_id}/adaptation/reject
Headers: Idempotency-Key
```

Decision is NEVER auto-applied. If the user refuses, the original workout remains
and the backend records the decision. Imperium replan is a backend handoff
surfaced by a toast/banner only.

### 13.4 Recovery

```text
Recovery is part of the PERSONALIZED forecast frame produced by GPT-5.5
(Mode 1 creation / Mode 3 revision), based on the user's real level. Qwen applies
and adjusts it day to day. No generic intensity→hours rule.
Within a recovery window, Pulse may WARN before an intense workout; it never
blocks (user decides).
```

### 13-REVISION. Global monthly revision (Mode 3)

```text
Independently of daily adaptation, GPT-5.5 returns AUTOMATICALLY every ~4 weeks
(monthly) for a deep review:
  - progression (muscle, level), are sessions actually being followed?
  - global re-adaptation if needed
  - PHASE TRANSITION decided by GPT-5.5, user-validatable
    (e.g. objective "visible abs" = phase 1 fat loss → phase 2 muscle gain)
Rhythm is monthly (not weekly): physical progression is slow; weekly revision
would over-adjust on noise. A light "is it being followed?" check may occur in
the weekly WR, without a heavy revision.
```

### 13-EQUIP. Owned equipment

```text
A Settings window: "mettre à jour mon matériel" (update my equipment).
The user adds/removes owned equipment (dumbbells, push-up board with handles,
attachable elastics, etc.). Owned equipment is considered ALWAYS available with
the user (at home). It is a direct INPUT to program creation/revision.
GPT-5.5 exploits it creatively (one item → many exercises).
```

### 13-PARK. Park equipment & day-continuity routing

```text
Some generated workouts need equipment NOT owned at home but available outdoors
(e.g. pull-up bars). Principle: the OPTIMAL workout prevails — the LOCATION
adapts, not the workout.

When a day's workout requires external equipment:
  → the UNIFIED BRAIN integrates this need into the day's PLANNING and finds a
    street-workout park (geo) that has the required equipment ON THE CONTINUITY
    of the user's trips/missions — same mechanism as prayer mosque selection
    (doc 41 §7-bis): a need + a geo constraint resolved within the day's flow.

Example:
  - mission: finish VTC work
  - mission: pick up a document at the tax office of [ville A]
  - on the route: a park at [ville B] with the needed equipment, hours fit
  → Imperium inserts BETWEEN the two missions: "stop at [ville B] park for your
    workout".

This is a cross-module link (Pulse workout need → Imperium mission placement),
resolved by the brain like any other day-continuity optimization.
```

Cross-references:
- Owned equipment (§13-EQUIP) and park need (§13-PARK) are INPUTS to program
  creation (§13.1 Mode 1) and revision (§13-REVISION Mode 3).
- §13-PARK reuses the day-continuity mechanism of doc 41 §7-bis (prayer) and the
  daily plan (doc 28). The brain places the workout in the trip/mission flow.
- Routing alignment (§18): workout creation/revision = GPT-5.5 (health, grouped,
  rare); daily adaptation = Qwen local with GPT-5.5 escalation. No CatBoost.

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

## 15. Integration With The Common Brain

⚠️ Terminology: modules do NOT exchange data with each other. Everything lives
in the common brain's shared memory (PostgreSQL + pgvector on Hostinger). The
brain (GPT-5.5 / Qwen / hard rules) reads and writes that memory; apps only
display. "X reads from Y" elsewhere is shorthand. Authoritative principle: see
the common-brain doc (to confirm — likely doc 44).

### 15.1 Imperium planning domain

```text
Shared data the BRAIN reads for planning (written by the morning check-in / daily
plan, stored in common memory):
  - energy_score, sleep_hours (morning check-in)
  - daily plan (to align workout timing)

Workout outcomes the BRAIN records in common memory (surfaced by Imperium as
display only):
  - workout completed / skipped (with reason)
  - medical rule activated (may inform a brain re-plan)
  - pain logged  ← NOTE: no hard "severity 8-10 -> replan" trigger. Pain is data
    the brain interprets (Qwen, escalating per scoring) — see §13.3 / §16 /
    Patch 40-C.
```

### 15.2 Path fasting/prayer domain

```text
Fasting/prayer data in common memory that conditions Pulse display & suggestions:
  - fasting_active, fasting_type, suhoor/iftar times, hydration_limits
Deterministic adaptations (hard rules of the brain, not a Pulse↔Path dialogue):
  - no meal suggestion during fasting hours (historical logging allowed w/ warning)
  - lighter workout intensity on fasting days
  - hydration logging only in allowed window
  - one fasting banner max on the dashboard
```

### 15.3 Vault receipt and expense domain

```text
Deterministic plumbing (a hard rule of the brain writing to common memory — NOT a
Vault↔Pulse exchange):
  - receipt OCR validated at VAU-05 -> brain writes stock additions/updates to
    common memory (source ref, confidence/warnings, sync state)
  - the stock tab may show a "received" badge; it never re-asks the user to
    validate the same receipt
Food-related expenses (last 30 days) live in common memory; the brain reads them
when relevant.
```

### 15.4 Vector planning domain

```text
Pulse and Vector are deliberately decoupled: Vector does not consume energy_score
(doc 33 §5.2.3). The only link is the common brain using both domains' data for
daily planning — not a direct Pulse↔Vector channel.
```

---

## 16. Pain Log (PUL-09)

Pain is CAPTURED via the chatbot (conversational): body zone, severity 0-10,
type if known, limitation notes, current workout impact. (No "voice note
transcript" mechanism.)

```text
TBD POST /api/pulse/pain-logs
Headers: Idempotency-Key
```

```text
The pain log is DATA, an INPUT for Qwen in workout adaptation (§13.3). Qwen
interprets the real situation (zone + severity + type + impact on SPECIFIC
exercises) and, per its own scoring:
  - adapts locally if within reach, OR
  - escalates to GPT-5.5 (health) if it looks medically serious, OR
  - if the scored gravity is critical (>=180/200), the critical mechanism
    (doc 30 §5.6 / Patch 30-B: GPT-5.5 re-score -> Opus orchestration) engages.

A high severity NATURALLY raises Qwen's score (error consequences + health
sensitivity) -> a deserved escalation, NOT a mechanical threshold.

NO hard safety net: the probability that Qwen misses an EXPLICIT "9/10" signal is
near nil (gravity is stated in clear, not inferred). The ultimate fallback is the
user triggering Emergency Mode manually via the chatbot (Patch 30-C).
```

Pulse does not diagnose (doc 36 §2.4, nuanced). Pain logs are constraints for
planning and workout safety.

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
