# 41 - The Path Logic Detail

## 1. Purpose

The Path is the **worship, prayer, fasting, sadaqa, and spiritual routines** module.

Path tracks religious obligations and surfaces them at the right time in the user's day. It connects with Vault (sadaqa calculation) and emits signals that Imperium uses to trigger AI replans.

---

## 2. Non-Negotiable Rules

```text
✅ Path can:
   - calculate prayer times (local + MAWAQIT)
   - track prayer completion
   - track fasting state
   - track adhkar routines
   - track Quran progression
   - emit ghusl_required signal
   - calculate sadaqa weekly target
   - track sadaqa donations
   - carry remaining sadaqa to next week

❌ Path must never:
   - infer fasting intention without explicit user action
   - infer ghusl state without explicit user action
   - infer Quran completion without explicit user action
   - infer adhkar completion without explicit user action
   - infer sadaqa completion without explicit user action
   - guilt-trip the user about missed obligations
   - send aggressive notifications
```

The principle: **religious actions are sacred and personal**. The system never auto-marks them as done.

Backend V1 routing note:
- `app/api/v1/routes/imperium_path.py` is canonical for Path V1.
- `GET /api/imperium/path/today` is owned by that module and returns `PathTodayResponse`.
- Legacy `ImperiumPathItem` compatibility code is deprecated for Path V1 and must not define or mask `/path/today`.

---

## 3. The Five Path Domains

```text
DOMAIN 1 — PRAYER
  ├─ Prayer time calculation
  ├─ Prayer completion tracking
  ├─ Mosque integration (MAWAQIT)
  └─ Prayer-related missions (e.g. ghusl)

DOMAIN 2 — FASTING
  ├─ Active fasting periods
  ├─ Suhoor / iftar windows
  ├─ Pulse constraint propagation
  └─ Fasting types (Mon/Thu, white days, Ramadan, custom)

DOMAIN 3 — SADAQA
  ├─ Weekly target from business profit
  ├─ Donation tracking
  ├─ Carry-forward of remaining
  └─ Configurable percentage

DOMAIN 4 — ADHKAR & QURAN
  ├─ Adhkar routines (categorized — see Section 9)
  ├─ Quran reading progression
  └─ Discipline contribution

DOMAIN 5 — GHUSL
  ├─ User-triggered requirement
  ├─ Auto-mission via Imperium AI replan
  └─ Mosque address registry
```

---

## 4. Prayer Times: Two Distinct Sources

This is the **most important architectural distinction** in Path.

### 4.1 Source A — Local calculation (default display)

```text
PURPOSE:
  Display prayer times in The Path dashboard.
  Always available, no external dependency.

INPUTS:
  - user.calculation_method (configured in settings)
    e.g. "Egyptian", "Karachi", "ISNA", "MWL", etc.
  - user.madhhab (configured in settings)
    e.g. "Shafi", "Hanafi"
  - user.large_city (configured in settings)
    e.g. "Paris" — used as reference, not exact GPS

OUTPUT:
  - Daily prayer times for the next 7 days
  - Stored in path_calculated_prayer_times

UPDATE:
  - Recomputed daily at 00:30 Europe/Paris
  - Stored canonical, no per-request recomputation
```

This is what the user sees on the Path home screen. Reliable, always there, no internet needed.

### 4.2 Source B — MAWAQIT (specific mosque, when needed)

```text
PURPOSE:
  Get the EXACT prayer time of a specific mosque
  the user plans to attend.

WHY THIS MATTERS:
  Different mosques use different calculation methods.
  Times can differ by 5-15 minutes between mosques.
  Missing a prayer because of a wrong assumption is unacceptable.

USE CASE:
  User finishes a Bolt ride near Mosque X.
  User wants to know if they can still catch Asr there.
  Local calculation says 18:12, but Mosque X actually does 18:18.
  → Path queries MAWAQIT for Mosque X
  → Returns 18:18, accurate

INPUTS:
  - mosque_id from MAWAQIT (user-registered mosques)

OUTPUT:
  - real prayer times for that specific mosque
  - cached for 24h to avoid API hammering
```

### 4.3 Which source is used when?

```text
DEFAULT (dashboard, planning, notifications):
  → Source A (local calculation)

SPECIFIC MOSQUE QUERY:
  → Source B (MAWAQIT)
  Triggered when:
    - User taps a registered mosque card
    - Vector recommends a zone with known mosque
    - Imperium plans a mission near a specific mosque
```

---

## 5. Prayer Completion Tracking

```text
prayer_logs table (per doc 05):
  - user_id
  - prayer_name (Fajr | Dhuhr | Asr | Maghrib | Isha)
  - prayer_date
  - completed (bool)
  - completed_at (timestamptz when marked)
  - location (optional: home | mosque | other)
  - source: user_action (always)

USER FLOW:
  Path home screen shows next prayer with countdown.
  When prayer time arrives:
    - subtle notification (no aggressive alarm)
    - card stays visible until user taps
    - user taps "✓ Faite" or "○ Manquée"
  
  Past prayers shown in today's list, can be marked retroactively.
```

The system **never** auto-completes a prayer. Only user action sets `completed = true`.

---

## 6. Fasting

### 6.1 Fasting state

```text
fasting_logs table (per doc 05):
  - user_id
  - fasting_date
  - fasting_type (monday_thursday | white_days | ramadan | custom | temporary)
  - action_type (start | end | break | abandon)
  - source: user_action

SIGNAL fasting_active:
  Computed boolean for current moment.
  TRUE if:
    - fasting_logs has start action for today
    - AND no end/break/abandon action since
    - AND current time within suhoor → iftar window
```

### 6.2 Suhoor and iftar windows

```text
For each fasting day:
  suhoor_time = (fajr_time - configurable_offset, default 30 min before)
  iftar_time  = maghrib_time

These windows propagate to Pulse:
  - meal suggestions disabled during fasting hours
  - hydration logging restricted
  - workout intensity reduced suggestion
```

### 6.3 Fasting types

```text
monday_thursday:
  - automatic recurring on Mon and Thu (if user opted in)
  - user must still confirm "start" action each day

white_days:
  - 13th, 14th, 15th of lunar month (white days)
  - calendar reminder, not auto-confirmed

ramadan:
  - all days of Ramadan month
  - calendar-aware, but each day still requires user start

custom:
  - user manually defines

temporary:
  - specific intent (e.g. "I'm fasting tomorrow because...")
```

---

## 7. Sadaqa

### 7.1 Calculation source: business profit only

```text
DECISION (per user spec):
Sadaqa is calculated on the BUSINESS profit only.
Not on personal income.
Not on total wallet.

Why: business profit is the income God blessed through work.
Personal money management is separate.
```

### 7.2 Weekly target computation

```text
At end of each ISO week (Sunday 23:59 Europe/Paris):
  weekly_business_profit = SUM(vault business_income) - SUM(vault business_expenses)
  
  weekly_sadaqa_target = weekly_business_profit × user.sadaqa_percentage
  
  e.g. profit = 1000€, percentage = 5%, target = 50€
```

The percentage is configurable in Path settings (default proposed: 2.5%, common practice).

### 7.3 Donation tracking

```text
sadaqa_records table (per doc 05):
  - user_id
  - amount_eur
  - destination (free text, optional)
  - donated_at
  - related_week_start
  - source: user_action

User confirms each donation via Path UI:
  → "J'ai donné" button + amount + optional destination
  → INSERT INTO sadaqa_records
```

### 7.4 Carry-forward logic

```text
End of week N:
  donated_total = SUM(sadaqa_records.amount where related_week = N)
  remaining = max(0, weekly_sadaqa_target_N - donated_total)
  
Beginning of week N+1:
  weekly_sadaqa_target_N+1 = (profit_N+1 × percentage) + remaining_from_N
  
EXAMPLE:
  Week N: target 50€, donated 30€ → remaining 20€
  Week N+1: profit gives 40€ target → effective target 40 + 20 = 60€

OVER-DONATION:
  Week N: target 50€, donated 80€
  → remaining = 0 (no credit carries)
  → Week N+1: target = profit × percentage normally
```

### 7.5 Surfacing in Path UI

```text
Path home shows:
  - Current week target: 60€
  - Donated this week: 25€
  - Remaining: 35€
  - Carry from last week: included
  - Last donation: 2 days ago
```

---

## 8. Ghusl Auto-Mission

This is the most architecturally interesting Path feature because it triggers cross-module AI behavior.

### 8.1 Activation

```text
USER ACTION (in Path UI):
  Toggle "Ghusl requis" → ON
  
BACKEND:
  - sets path.ghusl_required = TRUE
  - sets path.ghusl_required_since = NOW()
  - INSERTS event: path.ghusl.required
```

### 8.2 Imperium reception

```text
Imperium service subscribes to event: path.ghusl.required

On reception:
  1. Imperium creates a new mission:
     - title: "Faire le ghusl avant {next_prayer}"
     - source: "path"
     - priority: high (always, since prayer-related)
     - status: active
  
  2. Imperium triggers AI replan task:
     - ai_task type: imperium.day_replan
     - reason: "ghusl_required"
     - n8n claims, Sonnet 4.6 replans the day
  
  3. AI replan integrates the ghusl mission:
     - finds nearest registered_ghusl_address
     - inserts ghusl mission before next prayer
     - reorganizes other missions accordingly
  
  4. Result returned to backend
  5. New plan presented to user for validation
```

### 8.3 Completion

```text
User taps "Ghusl fait" in Path:
  → path.ghusl_required = FALSE
  → INSERTS event: path.ghusl.completed
  → Imperium marks the ghusl mission as "faite"
  → No additional replan needed
```

### 8.4 Registered ghusl addresses

```text
registered_ghusl_addresses table:
  - user_id
  - label (e.g. "home", "mosque_x", "gym_y")
  - address
  - latitude, longitude
  - is_default

Used by Imperium AI replan to choose the nearest valid option.
```

---

## 9. Adhkar Routines

> **NOTE — Pending document:**
> The complete adhkar categorization will be provided by the user in a separate document.
> This section will be expanded once that document is integrated.

### 9.1 V1 placeholder structure

```text
adhkar_routines table:
  - user_id
  - routine_id (e.g. "morning", "evening", "post_prayer")
  - adhkar_type (istighfar | salawat | tasbih | tahmid | takbir | personal)
  - target_count (e.g. 100)
  - frequency (daily | weekly | per_prayer)
  - active (bool)

adhkar_completions table:
  - user_id
  - routine_id
  - completed_count
  - completion_date
  - completed_at
```

### 9.2 V1 minimal implementation

```text
- Default routines: morning, evening, post-prayer (configurable)
- Each routine: counter that user increments by tap or voice
- Discipline score factors in completion rate
```

Full categorization and prompt-tied logic comes with the user-supplied adhkar document.

---

## 10. Quran Progression

```text
quran_progression table:
  - user_id
  - last_validated_page
  - last_validated_at
  - daily_objective (e.g. "2 pages")
  - current_streak_days

User flow:
  - Reads Quran (offline activity)
  - Returns to Path
  - Updates "I read up to page X"
  - Path stores validation, no friction
```

No restart logic if user misses a day. The progression is theirs to manage.

---

## 11. The Path Daily Score

A composite "discipline of Path" score is computed daily:

```text
score = weighted_average(
  prayer_completion_rate × 0.40,
  adhkar_completion_rate × 0.20,
  sadaqa_progress × 0.15,
  fasting_compliance_if_active × 0.15,
  quran_daily_objective_met × 0.10
)

Range: 0.0 to 1.0
Used by Imperium for the broader discipline_score.
```

Computed deterministically, no AI involved.

---

## 12. Path AI Task Types

```text
path.weekly_review_contribution    - feeds the WR (Opus via doc 32)
path.routine_adjustment            - rare, when user asks "should I 
                                     adapt my adhkar routine?"
path.sadaqa_strategy               - rare, deep advice (Opus)
```

Most Path operations are deterministic. AI is rarely needed because:
- prayer times are calculated, not reasoned
- sadaqa is arithmetic
- ghusl flow is event-based
- adhkar is counting

---

## 13. Routing Distribution For Path

```text
Daily ops (98%):           Qwen local OR backend deterministic
Light adaptations (1%):    Haiku 4.5
Strategic spiritual (1%):  Opus 4.7

Cost per month: < 0.50 €
```

---

## 14. Integration With Other Modules

### 14.1 With Imperium

```text
Path EMITS events Imperium subscribes to:
  - path.ghusl.required        → Imperium AI replan
  - path.ghusl.completed       → Imperium marks mission done
  - path.prayer.missed         → Imperium logs discipline impact
  - path.sadaqa.target_set     → Imperium daily plan awareness
```

### 14.2 With Vault

```text
Path READS from Vault:
  - weekly_business_profit (for sadaqa target)

Path EMITS to Vault context:
  - sadaqa_donations (logged as expense in Vault)
```

### 14.3 With Pulse

```text
Path EMITS to Pulse:
  - fasting_active
  - fasting_window (suhoor, iftar)
  - hydration_limits

Pulse reads these to adapt meal/workout/hydration logic.
```

### 14.4 With Vector

Path does not modify Vector’s profitability logic.

Vector only evaluates VTC profitability: zone, time, demand, distance, event opportunity, return strategy and ride economics.

If a Path constraint conflicts with a profitable Vector recommendation, Imperium applies the final user-facing overlay above Vector:

```text
Vector profitability signal: green
Path / Imperium constraint: prayer slot in 20 minutes
Final Imperium action: do not take a ride direction that would breach it
```

This keeps Vector pure and prevents worship, fatigue, family, health or lifestyle logic from leaking into the VTC profitability engine.

---

## 15. UI Surface (V1)

```text
Path Dashboard:
  ├─ Next prayer: name + countdown
  ├─ Today's prayers: list with ✓/○ checkboxes
  ├─ Sadaqa banner: target / donated / remaining
  ├─ Active fasting indicator (if applicable)
  ├─ Adhkar routines for current period
  ├─ Quran progress
  └─ Quick actions: J'ai prié | J'ai donné | Ghusl requis

Settings:
  ├─ Calculation method
  ├─ Madhhab
  ├─ Large city (Paris by default for our user)
  ├─ Sadaqa percentage
  ├─ Registered mosques (MAWAQIT)
  ├─ Registered ghusl addresses
  └─ Adhkar routines configuration

Mosque view (when tapped):
  ├─ MAWAQIT real prayer times
  └─ Distance from current location
```

---

## 16. Database Tables

Existing (per doc 05):
- `prayer_logs` ✅
- `fasting_logs` ✅
- `sadaqa_records` ✅

To add:

```sql
CREATE TABLE path_calculated_prayer_times (
  id              UUID PK,
  user_id         UUID FK,
  date            DATE,
  fajr            TIME, dhuhr TIME, asr TIME,
  maghrib         TIME, isha TIME,
  calculation_method VARCHAR(64),
  madhhab         VARCHAR(32),
  city_reference  VARCHAR(128),
  computed_at     TIMESTAMPTZ
);

CREATE TABLE path_registered_mosques (
  id          UUID PK,
  user_id     UUID FK,
  mawaqit_id  VARCHAR(128),
  name        VARCHAR(200),
  address     TEXT,
  latitude    NUMERIC,
  longitude   NUMERIC,
  added_at    TIMESTAMPTZ
);

CREATE TABLE path_mawaqit_cache (
  id            UUID PK,
  mosque_id     UUID FK -> path_registered_mosques,
  date          DATE,
  prayer_times  JSONB,
  fetched_at    TIMESTAMPTZ
);

CREATE TABLE registered_ghusl_addresses (
  id           UUID PK,
  user_id      UUID FK,
  label        VARCHAR(100),
  address      TEXT,
  latitude     NUMERIC,
  longitude    NUMERIC,
  is_default   BOOLEAN
);

CREATE TABLE adhkar_routines (
  id            UUID PK,
  user_id       UUID FK,
  routine_label VARCHAR(64),
  adhkar_type   VARCHAR(32),
  target_count  INTEGER,
  frequency     VARCHAR(32),
  active        BOOLEAN
);

CREATE TABLE adhkar_completions (
  id              UUID PK,
  user_id         UUID FK,
  routine_id      UUID FK -> adhkar_routines,
  completion_date DATE,
  completed_count INTEGER,
  completed_at    TIMESTAMPTZ
);

CREATE TABLE quran_progression (
  id                    UUID PK,
  user_id               UUID FK UNIQUE,
  last_validated_page   INTEGER,
  last_validated_at     TIMESTAMPTZ,
  daily_objective       VARCHAR(64),
  current_streak_days   INTEGER
);

CREATE TABLE path_weekly_sadaqa_state (
  id                       UUID PK,
  user_id                  UUID FK,
  week_start               DATE,
  business_profit_eur      NUMERIC,
  target_eur               NUMERIC,
  carried_from_previous    NUMERIC,
  donated_eur              NUMERIC,
  remaining_eur            NUMERIC,
  computed_at              TIMESTAMPTZ
);
```

---

## 17. References

- `01_SIGNAL_VARIABLES_DICTIONARY.md` — full Path signal list
- `05_DATABASE_SCHEMA.md` — existing tables
- `08_NON_NEGOTIABLE_RULES.md` — religious privacy rules
- `42_VAULT_LOGIC_DETAIL.md` — business profit source
- `43_IMPERIUM_LOGIC_DETAIL.md` — replan reception of Path events
- `40_PULSE_LOGIC_DETAIL.md` — fasting / hydration constraints

---

**Document version:** 1.0
**Status:** Path V1 reference (adhkar section pending user document)
**Last updated:** 2026-04-29
