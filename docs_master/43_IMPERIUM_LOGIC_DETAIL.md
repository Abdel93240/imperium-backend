# 43 - Imperium Logic Detail

## 1. Purpose

Imperium is the **personal command center**. It is the user-facing surface of the unified brain. It decides what the user should do **right now**, manages the live daily plan, and orchestrates priorities across all other modules.

Imperium is the only app the user interacts with for "what's next?" questions. The other apps (Vector, Vault, Pulse, Path) are angles of the same brain.

---

## 2. The Core Principle: A Living Plan

```text
The daily plan is NOT generated once and frozen.
The daily plan is a LIVING entity reshaped throughout the day by HOOKS.

Morning:
  AI generates the first plan based on context.

Day in progress:
  Each hook can re-trigger AI to reshape the plan.

End of day:
  The plan reflects everything the user actually did + what AI helped re-arrange.
```

This is the most important architectural distinction in Imperium.

---

## 3. The Hooks System

A "hook" is any event that triggers the AI to re-evaluate the day's plan.

### 3.1 List of hooks (V1)

```text
USER-INITIATED HOOKS:
  ├─ Imperium: "Reprogrammer ma journée" button
  ├─ Imperium: mission marked "ratée" (failed)
  ├─ Imperium: mission marked "annulée" (cancelled)
  ├─ Path: "Ghusl requis" toggle ON
  ├─ Vector: "Smart fuel" requested
  ├─ Vector: VTC session paused/ended unexpectedly
  ├─ Pulse: workout cancelled or rescheduled
  ├─ Pulse: pain logged with high severity
  └─ Vault: large unexpected expense logged

SYSTEM-INITIATED HOOKS:
  ├─ Mission expired (deadline passed without action)
  └─ External signal: critical disruption (Vector watcher)
```

### 3.2 What happens on a hook

```text
Hook fires:
  1. Backend captures the hook context (what changed, when, why)
  2. Backend creates ai_task: imperium.day_replan
     - input includes: current plan, current time, hook reason
  3. n8n claims the task
  4. Qwen scores complexity (typically 60-130)
  5. Sonnet 4.6 (most common) or Opus 4.7 (rare) replans
  6. New plan returned with rationale
  7. UI shows new plan to user for validation
  8. User accepts / rejects / partially accepts
  9. Accepted plan replaces previous plan (with version trail)
```

### 3.3 Hook frequency limits

```text
To avoid plan thrashing:
  - max 1 replan per 5 minutes (debounce)
  - if multiple hooks fire within 5 min, batch them
  - exceptions: ghusl_required, fasting_break (always immediate)
```

---

## 4. The Morning Popup

```text
First app open of the day OR scheduled trigger at user's configured wake time:

Imperium opens a popup BEFORE showing dashboard:

  "Bonjour. Comment ça va ce matin ?"
  
  ┌─ energy_score: slider 0-10
  ├─ sleep_hours: number input
  ├─ pain or limitation: optional text
  ├─ mood: optional emoji (one tap)
  └─ special context: optional text
  
  [Continuer]

→ INSERT INTO imperium_morning_checkins
→ Triggers FIRST replan of the day:
   ai_task: imperium.morning_plan
   inputs:
     - morning checkin
     - yesterday's outcomes
     - today's calendar items
     - active medical rules
     - business pressure
     - WR insights from past 4 weeks (decay-weighted)
   output: first daily plan

→ Plan presented to user. User accepts globally (V1) or per-mission (V2).
```

The morning checkin is the **only** auto-triggered AI replan. All other replans require an explicit hook.

---

## 5. Mission Lifecycle

```text
STATUSES:

active     - the AI included this mission in the daily plan
faite      - user marked as completed
ratée      - user marked as failed
annulée    - user cancelled the mission
expirée    - deadline passed without user action
```

No "proposed", "paused", "scheduled" intermediate states. Simple and binary.

### 5.1 Why this simplicity

```text
Philosophy: AI proposes, user accepts the day, then operates.
  - One active plan at a time
  - User does each mission or doesn't
  - Replans happen via hooks, not by editing existing missions
```

### 5.2 Mission attributes

```text
imperium_missions table (per doc 05):
  - id, user_id
  - title, description
  - mission_type (urgente | très_importante | secondaire)
  - source (ai_planner | path | vector | pulse | vault | manual)
  - source_ref (link to triggering item, e.g. ghusl_required event)
  - planned_for_at (when AI scheduled it)
  - deadline_at (when it expires)
  - status (active | faite | ratée | annulée | expirée)
  - completed_at, failed_at, cancelled_at, expired_at
  - notes
  - replan_version (which plan version included this)
```

### 5.3 Only one active mission rule (per doc 08)

```text
Constraint: only ONE mission with status='active' can be the
"current focus" at any time.

The plan can have many active missions for the day, but the user's
"current focus" is always one. Imperium UI surfaces this.

Other active missions are queued. As the current is finished/failed,
the next active becomes the focus.
```

---

## 6. Discipline Score

```text
Computed daily:

discipline_score = SUM(completed_missions × type_coefficient)
                 / SUM(all_missions × type_coefficient)

type_coefficient:
  - urgente: 3.0
  - très_importante: 2.0
  - secondaire: 1.0

Range: 0.0 to 1.0

EXAMPLE:
  Day plan: 2 urgentes, 3 très_importantes, 2 secondaires
  Total weighted = 2×3 + 3×2 + 2×1 = 14
  
  User completed: 1 urgente, 2 très_importantes, 1 secondaire
  Completed weighted = 1×3 + 2×2 + 1×1 = 8
  
  discipline_score = 8/14 = 0.57

Stored daily, used for trend analysis and WR.
```

The Path discipline (per doc 41 §11) feeds into a broader composite for the WR but is computed separately.

---

## 7. The Three Decision Layers

```text
LAYER 1 — DETERMINISTIC
  ├─ Mission lifecycle transitions
  ├─ Discipline score computation
  ├─ Mission expiry detection
  └─ Cost: 0€

LAYER 2 — QWEN LOCAL
  ├─ Quick interpretation of user input
  ├─ Routing chatbot to right specialist
  └─ Cost: 0€

LAYER 3 — DEFERRED CLOUD
  ├─ Day replan (most common): Sonnet 4.6
  ├─ Mentoring / strategic chat: Opus 4.7
  ├─ Web research chat: GPT-5.5 + web
  ├─ Standard chat: Sonnet 4.6
  └─ Weekly review: Opus 4.7 (per doc 32)
```

---

## 8. The Chatbot

The Imperium dashboard includes a chatbot accessible at any time.

### 8.1 Routing the chatbot

```text
User message → Qwen analyzes:
  - Does it need web data? (keywords: "actuel", "récent", "2026"...)
    → GPT-5.5 + web
  - Is it mentoring / deep thinking?
    → Opus 4.7
  - Is it standard conversation?
    → Sonnet 4.6
```

### 8.2 Where conversations are stored

```text
ai_results table:
  result_type = imperium.chat.opus_response
              | imperium.chat.web_response
              | imperium.chat.sonnet_response

The conversation is treated as ai_results because the outcomes
of these discussions can lead to:
  - new missions
  - project changes
  - objective changes
  - health adaptations
  - financial decisions

→ Chat results are first-class AI outputs, not throwaway logs.
→ They are visible in the user's history and can be referenced
  when the AI needs context later.
```

### 8.3 Decision-to-action flow

```text
During a chatbot conversation, Opus may identify a "decision".

Example:
  User: "Je pense que je devrais réduire VTC le mardi soir."
  Opus: "OK. Veux-tu que je note cette décision et l'applique ?"
  
  If user accepts:
    → backend creates a "user_decision" record
    → tied to the ai_result of this conversation
    → optionally creates a mission if action needed
    → feeds pgvector via the next WR validation
```

---

## 9. The Priority Hierarchy (Settings)

The user configures priorities in Imperium settings. This is what the unified brain consults when deciding what to surface.

```text
DEFAULT PRIORITY ORDER (fully customizable):
  1. Path obligations (prayer, fasting break)
  2. Health critical (medical rule violation, pain spike)
  3. Imperium urgent missions
  4. Vault critical alerts (overdue payment, etc.)
  5. Vector active session decisions
  6. Imperium très_importante missions
  7. Pulse routine (workouts, meals)
  8. Imperium secondaire missions
  9. Other notifications
```

### 9.1 How the brain uses this

```text
When two or more events compete for the user's attention:
  brain.consult_priority(event_a, event_b) → returns winner
  
Imperium UI shows the winner first.
Other relevant items shown below or as badges.
```

### 9.2 Example: prayer vs ride offer

```text
17:55 - Bolt offers a profitable ride (Vector evaluates: GREEN)
17:55 - Asr prayer at 18:12 (17 min away)

Brain evaluates:
  - ride duration: 25 min
  - ride end: 18:20 (8 min after prayer)
  
  Path priority > VTC priority
  → Vector profitability signal remains GREEN internally
  → Imperium overlay becomes RED based on Path conflict
  → Imperium suggests: "Prier d'abord, reprendre la session après"
```

The brain is unified: Vector and Path don't argue. The brain decides.

---

## 10. Imperium AI Task Types

```text
imperium.morning_plan              - first plan of the day (Sonnet)
imperium.day_replan                - hook-triggered replan (Sonnet, sometimes Opus)
imperium.mission_recommendation    - propose new missions during the day
imperium.priority_review           - rare, when user changes settings
imperium.chat.opus_response        - mentoring chatbot
imperium.chat.web_response         - web-needed chatbot
imperium.chat.sonnet_response      - standard chatbot
imperium.email_triage              - email handling (rare)
imperium.weekly_review.*           - per doc 32
imperium.daily_plan_assist         - mid-day suggestion
imperium.memory_candidate_extract  - identify memorable insights
```

---

## 11. Routing Distribution For Imperium

```text
Daily ops (90%):           Qwen local
Day reorganization (4%):   Sonnet 4.6
Chatbot mentoring (3%):    Opus 4.7
Chatbot web (2%):          GPT-5.5 + web
Chatbot standard (1%):     Sonnet 4.6
Weekly review:             Opus 4.7 (via WR)

Imperium is the most AI-call-intensive app.
Estimated cost: 5-7 €/month.
```

---

## 12. Integration With Other Modules

### 12.1 Imperium IS the consumer of all events

```text
Imperium SUBSCRIBES to:
  - path.ghusl.required        → trigger replan
  - path.ghusl.completed       → mark mission done
  - path.prayer.missed         → discipline score impact
  - path.fasting.started       → adjust meal-time missions
  - path.fasting.broken        → log + replan if needed
  
  - pulse.workout.completed    → log + adjust energy expectations
  - pulse.workout.skipped      → log skip reason + replan if needed
  - pulse.medical_rule.activated → trigger replan to apply rule
  
  - vault.weekly_profit.computed → financial context update
  - vault.pressure.spike        → trigger replan if critical
  
  - vector.session.started      → daily VTC tracking begins
  - vector.session.ended        → revenue logged + final plan adjustment
  - vector.event_scan.complete  → events_calendar updated
  - vector.smart_fuel.requested → trigger replan partial
  
  - wr.validated                → start WRS (doc 39) + memory update
```

### 12.2 What Imperium does with these events

```text
For most events:
  - log them
  - update relevant context
  - trigger replan if criteria met

Replan is triggered by:
  - path.ghusl.required (always)
  - vector.smart_fuel.requested (always)
  - pulse.workout.skipped (if was central to plan)
  - vault.pressure.spike (if shifts daily objective)
  - User explicit action ("Reprogrammer")
  - Mission ratée (lost time to recover)
```

---

## 13. Database Tables

Existing (per doc 05):
- `imperium_missions` ✅
- `imperium_priority_rules` ✅
- `imperium_path_items` ✅
- `imperium_daily_plans` ✅
- `imperium_day_reviews` ✅
- `imperium_weekly_review_states` ✅ (doc 32, migration 0010)

To add:

```sql
CREATE TABLE imperium_morning_checkins (
  id              UUID PK,
  user_id         UUID FK,
  date            DATE,
  energy_score    INTEGER CHECK (energy_score BETWEEN 0 AND 10),
  sleep_hours     NUMERIC(3,1),
  pain_notes      TEXT NULL,
  mood            VARCHAR(32) NULL,
  special_context TEXT NULL,
  submitted_at    TIMESTAMPTZ,
  UNIQUE (user_id, date)
);

CREATE TABLE imperium_replan_events (
  id              UUID PK,
  user_id         UUID FK,
  triggered_at    TIMESTAMPTZ,
  trigger_source  VARCHAR(64),  -- 'morning' | 'user_button' | 'path.ghusl.required' | etc.
  trigger_payload JSONB,
  ai_task_id      UUID FK -> ai_tasks(id),
  resulted_in_plan_version INTEGER NULL,
  status          VARCHAR(16)   -- 'pending' | 'completed' | 'rejected'
);

CREATE TABLE imperium_daily_plan_versions (
  id              UUID PK,
  user_id         UUID FK,
  date            DATE,
  version         INTEGER,
  plan_json       JSONB,
  created_at      TIMESTAMPTZ,
  source_replan_event_id UUID FK -> imperium_replan_events(id),
  is_current      BOOLEAN DEFAULT FALSE,
  UNIQUE (user_id, date, version)
);

CREATE TABLE imperium_user_decisions (
  id                UUID PK,
  user_id           UUID FK,
  decided_at        TIMESTAMPTZ,
  decision_text     TEXT,
  source_chat_result_id UUID FK -> ai_results(id),
  applied           BOOLEAN DEFAULT FALSE,
  applied_at        TIMESTAMPTZ NULL,
  notes             TEXT NULL
);

CREATE TABLE imperium_discipline_scores (
  id              UUID PK,
  user_id         UUID FK,
  date            DATE UNIQUE PER USER,
  imperium_score  NUMERIC(4,3),
  path_score      NUMERIC(4,3) NULL,
  pulse_score     NUMERIC(4,3) NULL,
  composite       NUMERIC(4,3),
  computed_at     TIMESTAMPTZ
);
```

The existing `imperium_missions` table needs alignment:

```sql
-- Ensure status enum matches (V1):
ALTER TABLE imperium_missions
ADD CONSTRAINT imperium_missions_status_check
CHECK (status IN ('active', 'faite', 'ratée', 'annulée', 'expirée'));

ALTER TABLE imperium_missions
ADD COLUMN IF NOT EXISTS mission_type VARCHAR(32) NOT NULL DEFAULT 'secondaire'
CHECK (mission_type IN ('urgente', 'très_importante', 'secondaire'));

ALTER TABLE imperium_missions
ADD COLUMN IF NOT EXISTS source VARCHAR(32) NOT NULL DEFAULT 'ai_planner';

ALTER TABLE imperium_missions
ADD COLUMN IF NOT EXISTS source_ref UUID NULL;
```

---

## 14. UI Surface (V1)

```text
Imperium Dashboard (the main user-facing screen):

  ┌─ Top: Greeting + morning checkin status
  ├─ Banner section:
  │   - Weekly Review available? (per doc 32)
  │   - Ghusl required?
  │   - Critical alert?
  ├─ Current focus mission (the ONE thing now)
  │   - Title + countdown to deadline
  │   - [Faite] [Ratée] [Annulée] buttons
  ├─ Today's plan (other active missions)
  │   - Tap to expand
  ├─ Quick stats:
  │   - Discipline today: N/N missions
  │   - Pressure score
  │   - Next prayer countdown
  ├─ Chatbot input (always visible)
  └─ Quick actions:
      [Reprogrammer] [+ Mission manuelle] [Voir historique]

Other tabs:
  - Plan history (past days)
  - Decisions log (chatbot decisions)
  - Settings (priorities, morning popup time, etc.)
  - Weekly Reviews (validated WRs)
```

---

## 15. Settings

```text
Imperium settings includes:

CORE:
  - morning_popup_time (e.g. 06:30)
  - morning_popup_enabled (default true)

PRIORITY HIERARCHY:
  - drag-to-reorder list of priority sources
  - default order shown in §9

REPLAN BEHAVIOR:
  - replan_on_mission_failure (default: yes for urgente, ask for others)
  - debounce_minutes (default: 5)

CHATBOT:
  - default_routing (qwen → ... → opus chain visible in advanced)
  - chat history retention (default: 90 days)

DISCIPLINE:
  - composite_weights (Imperium / Path / Pulse) - default 0.5 / 0.3 / 0.2
```

---

## 16. References

- `08_NON_NEGOTIABLE_RULES.md` — one active mission rule
- `12_DAILY_OBJECTIVE_PERIOD_LOGIC.md` — day boundary logic
- `25_CURRENT_MISSION_WORKFLOW.md` — current mission detail
- `26_PRIORITY_RULES_WORKFLOW.md` — priority rules
- `28_DAILY_PLAN_WORKFLOW.md` — plan generation flow
- `30_AI_ROUTING_AND_SCORING_POLICY.md` — Imperium routing
- `32_WR_INTERACTIVE_WORKFLOW.md` — Weekly Review
- `40_PULSE_LOGIC_DETAIL.md` — energy_score consumption
- `41_PATH_LOGIC_DETAIL.md` — ghusl event source
- `42_VAULT_LOGIC_DETAIL.md` — pressure consumption
- `33_VECTOR_LOGIC_DETAIL.md` — VTC session lifecycle
- `44_BRAIN_UNIFIED_LOGIC.md` — unified brain principles

---

**Document version:** 1.0
**Status:** Imperium V1 reference
**Last updated:** 2026-04-29
