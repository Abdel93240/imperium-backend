# 40 - Pulse Logic Detail

## 1. Purpose

Pulse is the **health, nutrition, and physical activity** module. It tracks everything related to the body so that downstream AI decisions stay grounded in real data.

Pulse must remain **simple to interact with** (the user is often busy and tired) but **comprehensive in tracking** (nothing should be left to guesswork).

For medical document analysis (a separate flow), see doc 34.

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

## 3. The Three Pulse Domains

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

## 4. Energy Score: Input, Not Computed

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
   Pulse does NOT consume Vault signals.
   Pulse stays focused on body data.
```

This separation keeps each module's responsibility clean.

---

## 5. The Three Decision Layers

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

## 6. Meal Tracking

### 6.1 Quick log (most common path)

```text
User taps "+meal" in Pulse
  → bottom sheet:
     - meal_type: dropdown (breakfast/lunch/dinner/snack)
     - description: free text or voice
     - photo (optional)
  → backend:
     - if photo: Gemini OCR + Qwen categorization
     - if description: Qwen estimates calories + macros
  → user confirms or adjusts
  → INSERT INTO meals (canonical)
```

### 6.2 Detailed log (after meal scan)

If the user provides a receipt photo or photographs a complex meal, Gemini extracts ingredients. The backend computes detailed macros.

```text
result_type: pulse.meal_log
structured fields:
  - estimated_calories
  - estimated_protein_g
  - estimated_carbs_g
  - estimated_fat_g
  - estimated_fiber_g
  - confidence_score
```

### 6.3 Stock decrement

Every logged meal that consumed inventory items triggers stock decrements:

```text
After meal save:
  → backend identifies likely ingredients
  → proposes decrement of food_stock_items
  → user confirms or adjusts
  → updates applied
```

---

## 7. Food Stock

### 7.1 Inventory items

```text
food_stock_items:
  id, user_id, name, category,
  quantity, unit (piece|g|kg|ml|l),
  expiry_date (nullable), 
  bought_at, last_used_at,
  created_at
```

### 7.2 How items enter the system

```text
SOURCE A — Receipt scan (most common)
  Vault scans receipt → food items proposed → user validates
  → INSERT INTO food_stock_items

SOURCE B — Photo of fridge/pantry
  Pulse takes photo → Gemini identifies items
  → User reviews diff → applies updates

SOURCE C — Manual entry
  User types item + quantity directly
```

### 7.3 Expiry alerts

```text
Daily cron at 09:00 Europe/Paris:
  → Find items with expiry_date < (today + 3 days)
  → Surface in Pulse banner: "3 items à consommer rapidement"
  → No AI involved, deterministic rule
```

### 7.4 Anti-waste meal suggestions

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

## 8. Hydration Tracking

```text
target_liters_per_day:
  - default: 3.5L (per medical rule baseline)
  - overridden by active medical rules

logged_liters_today:
  - user logs each glass/bottle in Pulse
  - quick taps: +250ml, +500ml, +1L

constraint from Path:
  - if fasting_active = TRUE
  - hydration_limits.daytime = false
  - then: log only between iftar and suhoor
  - Pulse adapts UI accordingly
```

Simple, no AI.

---

## 9. Workouts

### 9.1 Planning

```text
Workouts can be:
  - planned manually by user
  - proposed by Pulse based on:
    * energy_score (Imperium morning popup)
    * recovery state (last workout + intensity)
    * active medical rules (training caps)
    * fasting state (no intense if fasting)
    * weekly objectives
```

### 9.2 Workout types tracked

```text
workouts table:
  - title (e.g. "Push day", "Run 5km")
  - status: planned | in_progress | completed | skipped
  - planned_at, started_at, completed_at
  - duration_minutes
  - intensity_score (1-10, user-rated post-workout)
  - exercises_json (sets/reps/weight or distance/pace)
  - body_state_at_start (energy, fatigue, pain notes)
  - notes_post_workout
```

### 9.3 Adaptation based on energy

```text
If energy_score < 4:
  Pulse proposes:
    - reduce intensity
    - shorten duration
    - or skip if recovery rule active

User can:
  - accept proposal
  - keep original plan
  - skip workout entirely

Decision is NEVER auto-applied. Always user-validated.
```

### 9.4 Recovery computation

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

## 10. Body Composition

```text
body_snapshots table:
  - user_id
  - measured_at
  - weight_kg
  - body_fat_percent (optional, from scale or estimation)
  - waist_cm, chest_cm, etc. (optional, manual)
  - photo_uri (optional, private)
  - notes
```

Frequency: user-driven, no notifications pushing measurement.

Trends shown in Pulse history view, no AI processing in V1.

---

## 11. Pulse AI Task Types

```text
pulse.meal_estimate              - estimate calories/macros from text
pulse.meal_suggestion            - propose meal from stock + goals
pulse.training_adjustment        - adapt workout to current state
pulse.medical_report.analyze     - delegated to GPT-5.5 (doc 34)
pulse.kitchen_inventory_photo    - parse fridge/pantry image (Gemini)
pulse.weekly_review_contribution - feeds the WR (Opus via doc 32)
```

---

## 12. Routing Distribution For Pulse

```text
Daily ops (88%):    Qwen local
Quick adapts (8%):  Haiku 4.5
Weekly plans (2%):  Sonnet 4.6
Receipt OCR (1%):   Gemini
Medical (0.5%):     GPT-5.5 (static override)
WR (0.5%):          Opus 4.7 (via WR workflow)
```

---

## 13. Integration With Other Modules

### 13.1 With Imperium

```text
Pulse READS from Imperium:
  - imperium_morning_checkins.energy_score
  - imperium_morning_checkins.sleep_hours
  - imperium_daily_plans (to align workout timing)

Pulse EMITS events Imperium subscribes to:
  - pulse.workout.completed (Imperium logs success)
  - pulse.workout.skipped (Imperium notes failure reason)
  - pulse.medical_rule.activated (Imperium may trigger replan)
```

### 13.2 With Path

```text
Pulse READS from Path:
  - fasting_active
  - fasting_window (suhoor / iftar)
  - hydration_limits

Pulse adapts:
  - meal suggestions (none during fasting hours)
  - workout intensity (lighter on fasting days)
  - hydration logging (only allowed window)
```

### 13.3 With Vault

```text
Pulse READS from Vault:
  - food_related_expenses (last 30 days)

Pulse EMITS to Vault (via receipt scan):
  - food_purchases parsed from receipts
  → Vault creates expense draft
```

### 13.4 With Vector

```text
Pulse and Vector are deliberately decoupled.
Vector does NOT consume energy_score (per doc 33 §5.2.3).
The only indirect link: Imperium uses both for daily planning.
```

---

## 14. Database Tables

Most tables already exist (per doc 05). Confirmed structure:

```text
meals                  ✅ exists
workouts               ✅ exists
food_stock_items       ✅ exists
pulse_recommendations  ✅ exists
```

New tables to add:

```sql
-- Body composition snapshots
CREATE TABLE body_snapshots (
  id              UUID PK,
  user_id         UUID FK,
  measured_at     TIMESTAMPTZ,
  weight_kg       NUMERIC(5,2),
  body_fat_percent NUMERIC(4,2) NULL,
  waist_cm        NUMERIC(5,1) NULL,
  chest_cm        NUMERIC(5,1) NULL,
  photo_uri       TEXT NULL,
  notes           TEXT NULL,
  created_at      TIMESTAMPTZ
);

-- Hydration log
CREATE TABLE hydration_logs (
  id          UUID PK,
  user_id     UUID FK,
  logged_at   TIMESTAMPTZ,
  amount_ml   INTEGER,
  source      VARCHAR(32),
  created_at  TIMESTAMPTZ
);

-- Medical rules (active subset, see doc 34 for full)
CREATE TABLE pulse_medical_rules (
  -- defined in doc 34 §9
);

-- Pain / limitation log
CREATE TABLE pulse_pain_logs (
  id          UUID PK,
  user_id     UUID FK,
  body_area   VARCHAR(64),
  severity    INTEGER,  -- 0-10
  noted_at    TIMESTAMPTZ,
  resolved_at TIMESTAMPTZ NULL,
  notes       TEXT NULL
);
```

---

## 15. UI Surface (V1)

```text
Pulse Dashboard:
  ├─ Today: meals logged, hydration, workout planned
  ├─ Stock alerts banner (expiring items)
  ├─ Body snapshot (latest weight + trend)
  ├─ Active medical rules summary
  └─ Quick actions: +meal, +water, +workout, scan stock

Meals tab:
  ├─ History
  ├─ Macros today + week
  └─ Suggestions (when user asks)

Workouts tab:
  ├─ Today's plan (if any)
  ├─ History
  └─ Recovery state visual

Stock tab:
  ├─ Inventory list grouped by category
  ├─ Expiring soon section
  └─ Add manually / scan

Medical tab (doc 34):
  ├─ Documents history
  └─ Active rules
```

---

## 16. References

- `34_PULSE_MEDICAL_FEED_AI.md` — medical document analysis
- `30_AI_ROUTING_AND_SCORING_POLICY.md` — routing rules
- `31_AI_TASKS_AND_RESULTS_CONTRACT.md` — task contracts
- `41_PATH_LOGIC_DETAIL.md` — fasting and hydration constraints
- `43_IMPERIUM_LOGIC_DETAIL.md` — energy_score popup origin
- `01_SIGNAL_VARIABLES_DICTIONARY.md` — full signal list

---

**Document version:** 1.0
**Status:** Pulse V1 reference
**Last updated:** 2026-04-29
