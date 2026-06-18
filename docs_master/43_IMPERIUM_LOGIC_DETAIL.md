# 43 - Imperium Logic Detail

**Version:** 2.0 — Added comprehensive AI observability logging layer
**Last updated:** 2026-05-16

---

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
  ├─ Chatbot: explicit user request (re-plan, or a decision raised in chat)
  ├─ Imperium: mission marked "ratée" (failed)
  ├─ Imperium: mission marked "annulée" (cancelled)
  ├─ Imperium: project activated / deactivated / reordered
  ├─ Path: "Ghusl requis" toggle ON
  ├─ Vector: "Smart fuel" requested
  ├─ Vector: VTC session paused/ended unexpectedly
  ├─ Pulse: workout cancelled or rescheduled
  ├─ Pulse: pain logged with high severity
  ├─ Vault: large unexpected expense logged
  ├─ Calendar: event added within 7-day window (V3, doc 51)
  ├─ Calendar: deadline added within 7-day window (V3, doc 51)
  └─ Calendar: event modified within 7-day window (V3, doc 51)

SYSTEM-INITIATED HOOKS:
  ├─ Mission expired (deadline passed without action)
  └─ External signal: critical disruption (Vector watcher)
```

### 3.2 What happens on a hook

```text
Hook fires:
  1. Backend captures the hook context (what changed, when, why)
  2. Backend creates the replan ai_task (task type by scope — see step 5)
     - input includes: current plan, current time, hook reason
  3. n8n claims the task
  4. Qwen 32B scores the change on the ecosystem-wide 0–200 scale (doc 30 §5)
  5. Routing by score (doc 30 §5 table — never bypass it):
       - 0–99   → Qwen 32B re-plans LOCALLY itself (small scope: ~1–2 missions,
                  same-day reshuffle). Task type: imperium.day_replan.
       - 100–179→ escalate: Sonnet 4.6 (most common) or Opus 4.8 (rare).
                  Task type: imperium.day_replan.
       - multi-week project-scope change (a project toggle that invalidates /
                  introduces missions across several weeks) → STATIC RULE,
                  same livrable as WR Phase 3 (doc 30 §7.8): Fable 5, with the
                  §7.8 unavailability fallback → Opus 4.8 (active today).
                  Task type: imperium.rolling_replan (NEW — see below).
  6. New plan returned with rationale
  7. UI shows new plan to user for validation
  8. User accepts / rejects / partially accepts
  9. Accepted plan replaces previous plan (with version trail)
  
  ALL STEPS LOGGED in ai_call_logs (§17)
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
Triggered when the user presses "commencer la journée" (start day). NOT a clock-
time/wake-time trigger and NOT merely first app open — Imperium days are bounded
start→finish (doc 12), not by a 24h schedule.

Imperium opens a popup BEFORE showing dashboard:

  "Bonjour. Comment ça va ce matin ?"
  
  ┌─ energy_score: slider 0-10
  ├─ sleep_hours: number input (or API from Pulse wearable)
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
→ ALL AI calls from this flow logged in ai_call_logs (§17)
```

The morning checkin is the day's first replan, triggered by the explicit
"commencer la journée" action (user-triggered, not clock-auto).

---

## 5. Mission Lifecycle

```text
STATUSES:

active     - the AI included this mission in the daily plan
faite      - user marked as completed
ratée      - user marked as failed
annulée    - user cancelled the mission
expirée    - deadline passed without user action
stashed    - user deferred indefinitely (V3, doc 54)
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
  - mission_type (urgente | importante | secondaire)   -- PRIORITY level
  - source (ai_planner | path | vector | pulse | vault | manual)
  - source_ref (link to triggering item, e.g. ghusl_required event)
  - planned_for_at (when AI scheduled it)
  - deadline_at (when it expires)
  - status (active | faite | ratée | annulée | expirée | stashed)
  - completed_at, failed_at, cancelled_at, expired_at, stashed_at
  - notes
  - replan_version (which plan version included this)
  - stash_reason (if stashed)
  - is_carrier_mission (for submissions, V3 doc 53)
  - is_overlay_eligible (for submissions, V3 doc 53)
  - overlay_category (for submissions, V3 doc 53)
```

### 5.3 Main mission + parallel annex missions (see doc 53)

A "mission principale" (carrier) is the active focus. While it runs, optional
"missions annexes" (submissions / overlay tasks) can be presented in parallel —
the full model (eligibility by mission TYPE, optional/bonus scoring, carrier
rules) is owned by doc 53. Do not redefine it here.

Key points (authoritative source = doc 53):
- Annex missions run in parallel with the principal mission; they are OPTIONAL
  (strictly bonus, never punitive — doing zero leaves discipline_score unchanged).
- Eligibility is by mission TYPE (the AI perceives the type), never by a non-
  perceivable internal moment. The VTC session is a valid carrier; the user
  chooses when to act on an annex.
- Front-end (FR): "mission principale" / "mission annexe".

This supersedes any earlier "single active focus / others queued" wording.

---

## 6. Discipline Score

```text
Computed daily:

discipline_score = SUM(completed_missions × type_coefficient)
                 / SUM(all_missions × type_coefficient)

type_coefficient:
  - urgente: 3.0
  - importante: 2.0
  - secondaire: 1.0

Range: 0.0 to 1.0

EXAMPLE:
  Day plan: 2 urgentes, 3 importantes, 2 secondaires
  Total weighted = 2×3 + 3×2 + 2×1 = 14
  
  User completed: 1 urgente, 2 importantes, 1 secondaire
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
  ├─ Mission categorization (doc 52)
  ├─ Overlay eligibility classification (doc 53)
  └─ Cost: 0€

LAYER 3 — DEFERRED CLOUD
  ├─ Day replan (most common): Sonnet 4.6
  ├─ Mentoring / strategic chat: Opus 4.7
  ├─ Web research chat: GPT-5.5 + web
  ├─ Standard chat: Sonnet 4.6
  ├─ Monthly plan (doc 52): Opus 4.7
  └─ Weekly review: Opus 4.7 (per doc 32)

ALL LAYER 2 AND LAYER 3 CALLS are logged in ai_call_logs (§17).
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
    
Routing decision logged in ai_call_logs with task_type='chatbot.routing'
Downstream call logged with task_type='chatbot.opus'/'chatbot.sonnet'/etc.
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
→ Cost of each chat call logged in ai_call_logs.
```

### 8.3 Decision-to-action flow

During a chatbot conversation, the AI may identify a "decision".

The AI's role here is a CONSTRUCTIVE CRITIC, not an executor. Before recording
or applying a decision, it CHALLENGES it: risks, blind spots, data that
contradicts it, better alternatives. Reason: calling a large model just to agree
adds no value; the model earns its cost by improving the decision.

The user remains the SOURCE OF TRUTH. After the challenge, the user decides —
and the AI respects that decision even if it differs from the AI's view. The
contradiction serves better decisions, it does not impose the AI's opinion.

Example (correct behavior):
  User: "Je pense que je devrais réduire VTC le mardi soir."
  AI:   "Avant de noter ça — le mardi soir est historiquement un de tes
         créneaux les plus rentables (~X€/h). Qu'est-ce qui motive la
         réduction : fatigue, autre priorité ? Si c'est la fatigue, on
         pourrait alléger ailleurs et garder ce créneau."
  User: "C'est la fatigue en ce moment."
  AI:   "Alors deux options : réduire vraiment le mardi (tu perds ~X€), ou
         garder le mardi et alléger lundi/mercredi. Qu'est-ce que tu choisis ?"
  User: [tranche en connaissance de cause]

  If user confirms a final decision:
    → backend creates a "user_decision" record (the INFORMED decision)
    → tied to the ai_result of this conversation
    → optionally creates a mission if action needed
    → feeds pgvector via the next WR validation

Notes:
- The challenge is proportionate: trivial decisions need little or none; high-
  impact ones (money, health, time, commitments) deserve a real challenge.
- The AI challenges with data it actually has (history, profitability, plan);
  it does not invent facts to win the point.
- If the user holds their position after the challenge, the AI records it without
  friction. No nagging, no repeated pushback.

---

## 9. The Priority Hierarchy (Settings)

The user configures priorities in Imperium settings. This is what the unified brain consults when deciding what to surface.

```text
DEFAULT PRIORITY ORDER (fully customizable):
  1. Path: prayer times (immovable)
  2. Imperium urgente missions
  3. Pulse critical alerts (pain, medical rule)
  4. Vault pressure alerts
  5. Vector critical ride opportunity
  6. Imperium importante missions
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
  → Vector overlay: RED (overrides green based on Path conflict)
  → Imperium suggests: "Prier d'abord, reprendre la session après"
```

The brain is unified: Vector and Path don't argue. The brain decides.

---

## 10. Imperium AI Task Types

```text
imperium.morning_plan              - first plan of the day (Sonnet)
imperium.day_replan                - hook-triggered replan (Sonnet, sometimes Opus)
imperium.monthly_plan              - rolling 4-week plan (Opus, V2 doc 52)
imperium.mission_scoring           - score mission intrinsèque (Qwen, doc 52)
imperium.mission_categorize        - catégoriser mission type A-I (Qwen, doc 52)
imperium.mission_overlay_classify  - classify overlay eligibility (Qwen, doc 53)
imperium.mission_recommendation    - propose new missions during the day
imperium.priority_review           - rare, when user changes settings
imperium.chat.routing              - Qwen routing decision
imperium.chat.opus_response        - mentoring chatbot
imperium.chat.web_response         - web-needed chatbot
imperium.chat.sonnet_response      - standard chatbot
imperium.email_triage              - email handling (rare)
imperium.weekly_review.*           - per doc 32
imperium.daily_plan_assist         - mid-day suggestion
imperium.daily_ai_advice           - dashboard advice generated inside daily plan (Qwen)
imperium.memory_candidate_extract  - identify memorable insights
imperium.health_snapshot           - system health analysis (Qwen+Sonnet, doc 54)
imperium.daily_summary             - end-of-day 4-line summary (Sonnet, doc 54)
imperium.submission_refusal_analyze - analyze rejection reason (Qwen, doc 53)
```

---

## 11. Routing Distribution For Imperium

```text
Daily ops / classification (90%):  Qwen local
Day reorganization (4%):           Sonnet 4.6
Chatbot mentoring (3%):            Opus 4.7
Chatbot web (2%):                  GPT-5.5 + web
Chatbot standard (1%):             Sonnet 4.6
Weekly review:                     Opus 4.7 (via WR)
Monthly plan (1x/week):            Opus 4.7

Imperium is the most AI-call-intensive app.
Estimated cost: 5-7 €/month.
All calls tracked precisely in ai_call_logs.
```

---

## 12. Reads & Events via Common Memory

### 12.1 Imperium IS the consumer of all events

```text
Imperium READS the backend append-only events (§9) and reacts (replan, log).
The dotted names are BRAIN events, not app-to-app sends. Imperium is the
display surface that reads and renders; it does not receive pushes from apps.

Event names:
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
  
  - calendar.event_added        → trigger replan if ≤7 days (V3 doc 51)
  - calendar.deadline_added     → trigger replan if ≤7 days (V3 doc 51)
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
  - Calendar event added ≤7 days (V3)
```

### 12.3 Daily AI advice (dashboard)

```text
The Daily AI Advice block is generated once per day inside the daily-plan call.
It does not add a separate paid model call in V1.

Model:
  - Qwen local, the daily-plan model.
  - If the daily-plan model is later switched, the advice follows the same
    fallback path.

Source:
  - the VECTORIZED latest WR OUTPUT audit
  - specifically the Opus audit after the WR dialogue corrections validated by
    the user, not the unvalidated input audit.

Selection rule:
  - WR output audit memories carry an importance tag
    (critical / important / light / ...).
  - Qwen selects one concrete pattern from critical or important items.
  - Peripheral observations must not become daily advice.

Output:
  - one short, concrete sentence about a real personal pattern.
  - example: "Attention à la fatigue vers 16h — dis-moi si tu veux te reposer."

Actions:
  - [Voir pourquoi] opens the underlying pattern/explanation.
  - [Ouvrir chatbot] opens the Imperium chatbot so the user can rebound on the
    advice and ask the brain to replan.

Relation:
  - Weekly Review is the deep weekly analysis.
  - Daily AI Advice is its lightweight daily sibling, fed by the vectorized,
    user-validated WR output.
```

---

## 13. Database Tables (operational)

Existing (per doc 05):
- `imperium_missions` ✅
- `imperium_priority_rules` ✅
- `imperium_path_items` ✅
- `imperium_daily_plans` ✅
- `imperium_day_reviews` ✅
- `imperium_weekly_review_states` ✅ (doc 32, migration 0010)

To add (operational):

```sql
CREATE TABLE imperium_morning_checkins (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date            DATE NOT NULL,
  energy_score    INTEGER CHECK (energy_score BETWEEN 0 AND 10),
  sleep_hours     NUMERIC(3,1),
  pain_notes      TEXT NULL,
  mood            VARCHAR(32) NULL,
  special_context TEXT NULL,
  submitted_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, date)
);

CREATE TABLE imperium_replan_events (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  triggered_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  trigger_source         VARCHAR(64) NOT NULL,
                         -- 'morning' | 'user_button' | 'path.ghusl.required' | etc.
  trigger_payload        JSONB,
  ai_task_id             UUID NULL,
  resulted_in_plan_version INTEGER NULL,
  status                 VARCHAR(16) NOT NULL DEFAULT 'pending'
                         -- 'pending' | 'completed' | 'rejected'
);

CREATE TABLE imperium_daily_plan_versions (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date                   DATE NOT NULL,
  version                INTEGER NOT NULL,
  plan_json              JSONB NOT NULL,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  source_replan_event_id UUID NULL,
  is_current             BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (user_id, date, version)
);

CREATE TABLE imperium_user_decisions (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  decided_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  decision_text          TEXT NOT NULL,
  source_chat_result_id  UUID NULL,
  applied                BOOLEAN NOT NULL DEFAULT FALSE,
  applied_at             TIMESTAMPTZ NULL,
  notes                  TEXT NULL
);

CREATE TABLE imperium_discipline_scores (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date            DATE NOT NULL,
  imperium_score  NUMERIC(4,3),
  path_score      NUMERIC(4,3) NULL,
  pulse_score     NUMERIC(4,3) NULL,
  composite       NUMERIC(4,3) NOT NULL,
  computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, date)
);
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
  ├─ Daily AI Advice
  │   - one concrete pattern from the latest validated WR output audit
  │   - [Voir pourquoi] [Ouvrir chatbot]
  ├─ Projets en cours
  │   - top active projects with progress %
  │   - [Voir tous les projets] link to Operations tab (doc 71)
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
  - History screen (read-only consultation)
    - finances evolution, e.g. 3-month net result curve
    - discipline evolution curve (real accomplishment ratio, not game score)
    - completed projects list with dates
    - AI note on the bilan (strong point / weak point / reading)
  - Decisions log (chatbot decisions)
  - Settings (priorities, morning popup time, etc.)
  - Weekly Reviews (validated WRs)
  - Mon OS personnel (doc 54, system health dashboard)
```

Gamification boundary for History:
```text
The old "Hall of Fame" framing is forbidden. Do not use badges, ranks, levels,
numeric game scores, streak rewards, or trophy framing. Discipline remains a real
metric: mission-accomplishment ratio and the composite-weighted metric described
in §6 and §15.
```

---

## 15. Settings

```text
Imperium settings includes:

CORE:
  - morning_popup_time (e.g. 06:30)
  - morning_popup_enabled (default true)
  - widget_enabled (show/manage Imperium widget on home screen)
  - notifications_enabled (missions, routines, alerts + manage)

PRIORITY HIERARCHY:
  - drag-to-reorder list of priority sources
  - default order shown in §9

MODE IA:
  - STRICT: the AI follows the priority hierarchy and rules to the letter.
  - ÉQUILIBRÉ: the AI seeks the best balance between priorities and context.
  - SOUPLE: the AI may deviate from the hierarchy when context justifies it.
  - Default: to confirm, likely ÉQUILIBRÉ.
  - This influences daily plan, mission arbitration, advice, and recommendations.
  - This is not "quick mode": it changes firmness of priority-following, not
    content depth or validation.

REPLAN BEHAVIOR:
  - replan_on_mission_failure (default: yes for urgente, ask for others)
  - debounce_minutes (default: 5)

CHATBOT:
  - default_routing (qwen → ... → opus chain visible in advanced)
  - chat history retention (default: 90 days)

FEED IA / NOURRIR L'IA:
  - button in Settings → Intelligence Artificielle.
  - references the central Knowledge Inbox spec (doc 70).
  - the user adds content; AI analyzes it; the user validates or modifies before
    anything enters common memory / pgvector.

API & SECURITY:
  - API connection status
  - location permission
  - microphone permission
  - camera permission
  - health data permission
  - storage permission
  - aligns with doc 44 privacy boundaries.

DISCIPLINE:
  - composite_weights (Imperium / Path / Pulse) - default 0.5 / 0.3 / 0.2

SUBMISSIONS (V3, doc 53):
  - submissions_enabled (default: true)
  - overlay_categories_enabled: per category

SYSTEM HEALTH (V3, doc 54):
  - lane_learning_enabled (default: false)
  - daily_summary_enabled (default: true)
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
- `51_FUTURE_CALENDAR.md` — calendar hooks (V3)
- `52_AI_DECISION_FRAMEWORK.md` — mission scoring
- `53_SUBMISSIONS_OVERLAY_TASKS.md` — carrier/overlay logic
- `54_SYSTEM_HEALTH_DASHBOARD.md` — health snapshots
- `70_KNOWLEDGE_INBOX.md` — central Feed IA / "Nourrir l'IA" spec
- `71_IMPERIUM_OPERATIONS_TAB.md` — projects/routines source for dashboard preview

---

## 17. AI Observability Logging Layer

> **Critical section.** This is the foundation for all future decisions about model quality, cost control, and architecture evolution. Every AI call in the ecosystem is logged here. Without this data, debugging and optimization are impossible after real usage.

### 17.1 The central AI call log table

```sql
CREATE TABLE ai_call_logs (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  called_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  -- ORIGIN: who triggered this call
  app_name              VARCHAR(32) NOT NULL,
                        -- 'imperium' | 'vector' | 'vault' | 'pulse' | 'path'
  task_type             VARCHAR(64) NOT NULL,
                        -- see §10 for full list + all app equivalents
  trigger_source        VARCHAR(64) NULL,
                        -- 'morning_checkin' | 'hook.mission_failed' |
                        --  'user.chatbot' | 'cron.weekly_plan' | etc.
  
  -- MODEL: what was used
  model_used            VARCHAR(48) NOT NULL,
                        -- 'qwen-2.5-7b-q5' | 'claude-haiku-4.5' |
                        --  'claude-sonnet-4.6' | 'claude-opus-4.7' |
                        --  'gpt-4o' | 'gpt-5.5' | 'gemini-2.5-pro' |
                        --  'whisper-large-v3'
  model_tier            VARCHAR(16) NOT NULL,
                        -- 'local' | 'cloud_cheap' | 'cloud_standard' | 'cloud_premium'
  
  -- TOKENS: usage breakdown
  input_tokens          INTEGER NULL,
  output_tokens         INTEGER NULL,
  total_tokens          INTEGER GENERATED ALWAYS AS
                        (COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)) STORED,
  
  -- COST: in euros, computed at insert time using pricing grid
  cost_eur              NUMERIC(10, 6) NULL,
                        -- 0.000000 for local models
  
  -- QUALITY: was the output good?
  was_validated         BOOLEAN NULL,
                        -- NULL = not checked
                        -- TRUE  = validated correct
                        -- FALSE = incorrect / hallucination
  validation_method     VARCHAR(32) NULL,
                        -- 'qwen_check' | 'user_feedback' |
                        --  'auto_test' | 'wr_review'
  quality_notes         TEXT NULL,
                        -- free text if something went wrong
  
  -- PERFORMANCE
  duration_ms           INTEGER NULL,
  queue_wait_ms         INTEGER NULL,
                        -- time waiting in n8n queue before execution
  
  -- OUTCOME
  success               BOOLEAN NOT NULL DEFAULT TRUE,
  error_code            VARCHAR(64) NULL,
                        -- 'timeout' | 'rate_limit' | 'context_too_long' |
                        --  'model_refused' | 'parsing_failed' | 'validation_failed'
  error_message         TEXT NULL,
  retry_attempt         INTEGER NOT NULL DEFAULT 0,
                        -- 0 = first try, 1 = first retry, etc.
  fallback_used         BOOLEAN NOT NULL DEFAULT FALSE,
                        -- TRUE if this is a fallback from a failed higher model
  original_model        VARCHAR(48) NULL,
                        -- if fallback_used: what model failed before this
  
  -- CONTEXT SIZE
  context_tokens_sent   INTEGER NULL,
                        -- how many tokens of context were in the prompt
  
  -- REFERENCE: link to what produced or consumed this call
  related_entity_type   VARCHAR(32) NULL,
                        -- 'mission' | 'daily_plan' | 'monthly_plan' |
                        --  'chat_session' | 'wr_session' | 'health_snapshot'
  related_entity_id     UUID NULL,
  
  -- CHAIN: if this call triggered another (e.g. Qwen routing → Sonnet response)
  parent_call_id        UUID NULL REFERENCES ai_call_logs(id)
);

-- INDEXES for all common query patterns
CREATE INDEX ai_call_logs_time_idx
ON ai_call_logs (called_at DESC);

CREATE INDEX ai_call_logs_app_task_idx
ON ai_call_logs (app_name, task_type, called_at DESC);

CREATE INDEX ai_call_logs_model_idx
ON ai_call_logs (model_used, called_at DESC);

CREATE INDEX ai_call_logs_cost_idx
ON ai_call_logs (cost_eur DESC, called_at DESC)
WHERE cost_eur IS NOT NULL;

CREATE INDEX ai_call_logs_errors_idx
ON ai_call_logs (called_at DESC)
WHERE success = FALSE;

CREATE INDEX ai_call_logs_hallucinations_idx
ON ai_call_logs (called_at DESC)
WHERE was_validated = FALSE;

CREATE INDEX ai_call_logs_related_idx
ON ai_call_logs (related_entity_type, related_entity_id)
WHERE related_entity_id IS NOT NULL;
```

### 17.2 Pricing configuration table

```sql
-- Allows updating pricing without code changes
CREATE TABLE ai_model_pricing (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  model_slug            VARCHAR(48) UNIQUE NOT NULL,
                        -- matches model_used in ai_call_logs
  input_cost_per_1m     NUMERIC(10, 4) NOT NULL DEFAULT 0,
                        -- euros per 1 million input tokens
  output_cost_per_1m    NUMERIC(10, 4) NOT NULL DEFAULT 0,
                        -- euros per 1 million output tokens
  is_local              BOOLEAN NOT NULL DEFAULT FALSE,
  valid_from            DATE NOT NULL DEFAULT CURRENT_DATE,
  valid_until           DATE NULL,
                        -- NULL = still current
  notes                 TEXT NULL
);

-- SEED with current pricing (May 2026)
INSERT INTO ai_model_pricing 
  (model_slug, input_cost_per_1m, output_cost_per_1m, is_local) VALUES
  ('qwen-2.5-7b-q5',     0,       0,      TRUE),
  ('qwen-2.5-3b-q4',     0,       0,      TRUE),
  ('whisper-large-v3',   0,       0,      TRUE),
  ('claude-haiku-4.5',   0.80,    4.00,   FALSE),
  ('claude-sonnet-4.6',  3.00,   15.00,   FALSE),
  ('claude-opus-4.7',   15.00,   75.00,   FALSE),
  ('gpt-4o',             2.50,   10.00,   FALSE),
  ('gpt-5.5',            5.00,   20.00,   FALSE),
  ('gemini-2.5-pro',     1.25,   10.00,   FALSE);
```

### 17.3 Automatic cost computation

```sql
-- FUNCTION: compute cost from tokens + current pricing
CREATE OR REPLACE FUNCTION compute_ai_call_cost(
  p_model_slug VARCHAR,
  p_input_tokens INTEGER,
  p_output_tokens INTEGER
) RETURNS NUMERIC(10,6) AS $$
  SELECT 
    ROUND(
      (p_input_tokens::NUMERIC  / 1000000 * input_cost_per_1m) +
      (p_output_tokens::NUMERIC / 1000000 * output_cost_per_1m),
      6
    )
  FROM ai_model_pricing
  WHERE model_slug = p_model_slug
    AND valid_from <= CURRENT_DATE
    AND (valid_until IS NULL OR valid_until >= CURRENT_DATE)
  LIMIT 1;
$$ LANGUAGE SQL STABLE;

-- TRIGGER: auto-compute cost on INSERT if not provided
CREATE OR REPLACE FUNCTION ai_call_logs_compute_cost()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.cost_eur IS NULL 
     AND NEW.input_tokens IS NOT NULL 
     AND NEW.output_tokens IS NOT NULL THEN
    NEW.cost_eur := compute_ai_call_cost(
      NEW.model_used, NEW.input_tokens, NEW.output_tokens
    );
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER ai_call_logs_auto_cost
BEFORE INSERT ON ai_call_logs
FOR EACH ROW EXECUTE FUNCTION ai_call_logs_compute_cost();
```

### 17.4 Analysis views

These views answer the real questions you'll ask after 2-3-6 months of usage.

```sql
-- ─────────────────────────────────────────────────────
-- VIEW 1: MONTHLY COST BREAKDOWN BY MODEL
-- Question: "What did I spend in March, and on what?"
-- ─────────────────────────────────────────────────────
CREATE VIEW ai_monthly_by_model AS
SELECT
  DATE_TRUNC('month', called_at)::DATE  AS month,
  model_used,
  model_tier,
  COUNT(*)                              AS call_count,
  SUM(input_tokens)                     AS total_input_tokens,
  SUM(output_tokens)                    AS total_output_tokens,
  SUM(total_tokens)                     AS total_tokens,
  ROUND(SUM(cost_eur), 4)               AS total_cost_eur,
  ROUND(AVG(cost_eur), 6)               AS avg_cost_per_call,
  ROUND(AVG(duration_ms))               AS avg_duration_ms,
  COUNT(*) FILTER (WHERE success=FALSE) AS error_count,
  COUNT(*) FILTER (WHERE fallback_used) AS fallback_count,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE was_validated = FALSE)
    / NULLIF(COUNT(*) FILTER (WHERE was_validated IS NOT NULL), 0),
    1
  )                                     AS hallucination_pct
FROM ai_call_logs
GROUP BY 1, 2, 3
ORDER BY 1 DESC, 4 DESC;

-- ─────────────────────────────────────────────────────
-- VIEW 2: MONTHLY COST BREAKDOWN BY APP
-- Question: "Which app costs me the most?"
-- ─────────────────────────────────────────────────────
CREATE VIEW ai_monthly_by_app AS
SELECT
  DATE_TRUNC('month', called_at)::DATE  AS month,
  app_name,
  COUNT(*)                              AS call_count,
  ROUND(SUM(cost_eur), 4)               AS total_cost_eur,
  ROUND(AVG(cost_eur) * 1000, 4)        AS avg_cost_meur,
  COUNT(*) FILTER (WHERE success=FALSE) AS error_count,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE was_validated = FALSE)
    / NULLIF(COUNT(*) FILTER (WHERE was_validated IS NOT NULL), 0),
    1
  )                                     AS hallucination_pct
FROM ai_call_logs
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC;

-- ─────────────────────────────────────────────────────
-- VIEW 3: TASK TYPE BREAKDOWN
-- Question: "Which task type calls AI the most / costs most?"
-- ─────────────────────────────────────────────────────
CREATE VIEW ai_monthly_by_task AS
SELECT
  DATE_TRUNC('month', called_at)::DATE  AS month,
  app_name,
  task_type,
  model_used,
  COUNT(*)                              AS call_count,
  ROUND(SUM(cost_eur), 4)               AS total_cost_eur,
  ROUND(AVG(duration_ms))               AS avg_duration_ms,
  COUNT(*) FILTER (WHERE success=FALSE) AS error_count
FROM ai_call_logs
GROUP BY 1, 2, 3, 4
ORDER BY 1 DESC, 5 DESC;

-- ─────────────────────────────────────────────────────
-- VIEW 4: DAILY SPEND (for budgeting)
-- Question: "What did I spend today / this week?"
-- ─────────────────────────────────────────────────────
CREATE VIEW ai_daily_spend AS
SELECT
  called_at::DATE           AS day,
  COUNT(*)                  AS total_calls,
  COUNT(*) FILTER (WHERE model_tier = 'local')          AS local_calls,
  COUNT(*) FILTER (WHERE model_tier = 'cloud_cheap')    AS cheap_calls,
  COUNT(*) FILTER (WHERE model_tier = 'cloud_standard') AS standard_calls,
  COUNT(*) FILTER (WHERE model_tier = 'cloud_premium')  AS premium_calls,
  ROUND(SUM(cost_eur), 4)   AS total_cost_eur,
  ROUND(SUM(cost_eur) FILTER (WHERE model_tier = 'cloud_premium'), 4) AS premium_cost_eur,
  COUNT(*) FILTER (WHERE success=FALSE) AS errors
FROM ai_call_logs
GROUP BY 1
ORDER BY 1 DESC;

-- ─────────────────────────────────────────────────────
-- VIEW 5: HALLUCINATION TRACKER
-- Question: "Which model / task hallucinates the most?"
-- ─────────────────────────────────────────────────────
CREATE VIEW ai_hallucination_tracker AS
SELECT
  DATE_TRUNC('month', called_at)::DATE AS month,
  app_name,
  task_type,
  model_used,
  COUNT(*) FILTER (WHERE was_validated IS NOT NULL) AS validated_calls,
  COUNT(*) FILTER (WHERE was_validated = TRUE)      AS correct_calls,
  COUNT(*) FILTER (WHERE was_validated = FALSE)     AS wrong_calls,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE was_validated = FALSE)
    / NULLIF(COUNT(*) FILTER (WHERE was_validated IS NOT NULL), 0),
    1
  )                                                 AS error_rate_pct
FROM ai_call_logs
WHERE was_validated IS NOT NULL
GROUP BY 1, 2, 3, 4
ORDER BY 1 DESC, 7 DESC;

-- ─────────────────────────────────────────────────────
-- VIEW 6: ERROR AND FALLBACK ANALYSIS
-- Question: "Which models / tasks fail the most often?"
-- ─────────────────────────────────────────────────────
CREATE VIEW ai_error_analysis AS
SELECT
  DATE_TRUNC('month', called_at)::DATE  AS month,
  model_used,
  task_type,
  error_code,
  COUNT(*)                              AS error_count,
  ROUND(AVG(retry_attempt), 2)          AS avg_retry_count,
  COUNT(*) FILTER (WHERE fallback_used) AS fallbacks_triggered
FROM ai_call_logs
WHERE success = FALSE
GROUP BY 1, 2, 3, 4
ORDER BY 1 DESC, 5 DESC;

-- ─────────────────────────────────────────────────────
-- VIEW 7: LATENCY HEATMAP
-- Question: "Are some tasks too slow?"
-- ─────────────────────────────────────────────────────
CREATE VIEW ai_latency_profile AS
SELECT
  task_type,
  model_used,
  COUNT(*)                          AS call_count,
  ROUND(MIN(duration_ms))           AS min_ms,
  ROUND(PERCENTILE_CONT(0.50)
    WITHIN GROUP (ORDER BY duration_ms)) AS p50_ms,
  ROUND(PERCENTILE_CONT(0.90)
    WITHIN GROUP (ORDER BY duration_ms)) AS p90_ms,
  ROUND(PERCENTILE_CONT(0.99)
    WITHIN GROUP (ORDER BY duration_ms)) AS p99_ms,
  ROUND(MAX(duration_ms))           AS max_ms
FROM ai_call_logs
WHERE duration_ms IS NOT NULL
  AND called_at > NOW() - INTERVAL '30 days'
GROUP BY 1, 2
ORDER BY 6 DESC;

-- ─────────────────────────────────────────────────────
-- VIEW 8: EVOLUTION OVER TIME (6-MONTH TREND)
-- Question: "Is my usage growing? Is it sustainable?"
-- ─────────────────────────────────────────────────────
CREATE VIEW ai_6month_trend AS
SELECT
  DATE_TRUNC('month', called_at)::DATE AS month,
  COUNT(*)                             AS total_calls,
  ROUND(SUM(cost_eur), 2)              AS total_cost_eur,
  COUNT(DISTINCT related_entity_id)    AS unique_entities_impacted,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE model_tier = 'local')
    / COUNT(*),
    1
  )                                    AS local_pct,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE success = FALSE)
    / COUNT(*),
    2
  )                                    AS error_rate_pct
FROM ai_call_logs
WHERE called_at > NOW() - INTERVAL '6 months'
GROUP BY 1
ORDER BY 1 DESC;

-- ─────────────────────────────────────────────────────
-- VIEW 9: FALLBACK CHAIN EFFECTIVENESS
-- Question: "Do my fallback models save the day or waste money?"
-- ─────────────────────────────────────────────────────
CREATE VIEW ai_fallback_effectiveness AS
SELECT
  original_model,
  model_used                            AS fallback_model,
  COUNT(*)                              AS fallback_count,
  COUNT(*) FILTER (WHERE success=TRUE)  AS fallback_success,
  COUNT(*) FILTER (WHERE success=FALSE) AS fallback_also_failed,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE success=TRUE)
    / COUNT(*),
    1
  )                                     AS success_rate_pct,
  ROUND(AVG(cost_eur), 5)               AS avg_cost_eur
FROM ai_call_logs
WHERE fallback_used = TRUE
GROUP BY 1, 2
ORDER BY 3 DESC;

-- ─────────────────────────────────────────────────────
-- VIEW 10: REAL MONTHLY TOTAL (vs estimates in docs)
-- Question: "What am I REALLY paying, vs my doc estimates?"
-- ─────────────────────────────────────────────────────
CREATE VIEW ai_vs_estimates AS
SELECT
  DATE_TRUNC('month', called_at)::DATE AS month,
  ROUND(SUM(cost_eur), 2)              AS actual_cost_eur,
  -- Compare to documented estimates per app:
  -- Imperium: 5-7€, Vector: 3€, Vault: 2€, Path: 1€, Pulse: 1€
  -- Total estimate: ~12-14€/month
  12.00                                AS doc_estimate_low_eur,
  14.00                                AS doc_estimate_high_eur,
  ROUND(SUM(cost_eur) - 12.00, 2)      AS vs_low_estimate,
  ROUND(SUM(cost_eur) - 14.00, 2)      AS vs_high_estimate
FROM ai_call_logs
GROUP BY 1
ORDER BY 1 DESC;
```

### 17.5 Helper queries for manual review

```sql
-- Last 50 errors with context
SELECT
  called_at,
  app_name,
  task_type,
  model_used,
  error_code,
  error_message,
  retry_attempt,
  fallback_used,
  original_model
FROM ai_call_logs
WHERE success = FALSE
ORDER BY called_at DESC
LIMIT 50;

-- Today's spending by hour
SELECT
  DATE_TRUNC('hour', called_at) AS hour,
  COUNT(*) AS calls,
  ROUND(SUM(cost_eur), 4) AS cost_eur
FROM ai_call_logs
WHERE called_at::DATE = CURRENT_DATE
GROUP BY 1
ORDER BY 1;

-- Top 10 most expensive individual calls ever
SELECT
  called_at,
  app_name,
  task_type,
  model_used,
  total_tokens,
  cost_eur,
  success
FROM ai_call_logs
ORDER BY cost_eur DESC
LIMIT 10;

-- Qwen 7B hallucination rate by task type
SELECT
  task_type,
  COUNT(*) FILTER (WHERE was_validated IS NOT NULL) AS checked,
  COUNT(*) FILTER (WHERE was_validated = FALSE) AS hallucinations,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE was_validated = FALSE)
    / NULLIF(COUNT(*) FILTER (WHERE was_validated IS NOT NULL), 0),
    1
  ) AS hallucination_pct
FROM ai_call_logs
WHERE model_used = 'qwen-2.5-7b-q5'
GROUP BY 1
HAVING COUNT(*) FILTER (WHERE was_validated IS NOT NULL) > 10
ORDER BY 4 DESC;

-- Monthly recap (the executive summary)
SELECT
  month,
  total_calls,
  ROUND(total_cost_eur, 2) AS cost_eur,
  ROUND(local_pct, 1) AS local_pct,
  ROUND(error_rate_pct, 2) AS error_rate_pct
FROM ai_6month_trend
ORDER BY month DESC;
```

### 17.6 Alert thresholds (to implement in monitoring)

```text
ALERT IF:

Daily spend > 1.50€
  → Something is looping or over-calling

Weekly spend > 7€
  → Review usage patterns

Error rate > 5% in last 24h
  → Model or network issue

Qwen hallucination rate > 15% on a task type
  → Prompt needs improvement or switch to Sonnet

Single call cost > 0.50€
  → Context window too large, review pruning

p90 latency > 30 seconds on any task type
  → Model selection or VPS performance issue

Fallback used > 3x in 1 hour
  → Primary model failing repeatedly, investigate
```

### 17.7 Review cadence

```text
APRÈS 2 MOIS:
├─ Lancer: SELECT * FROM ai_monthly_by_model;
├─ Lancer: SELECT * FROM ai_hallucination_tracker;
├─ Lancer: SELECT * FROM ai_vs_estimates;
└─ Questions à se poser:
   - Qwen 7B hallucine combien en %? Si >15% → switch Haiku
   - Coût réel vs estimé? Si >20% écart → ajuster routage
   - Tâche la plus chère? Optimiser le contexte envoyé
   - Erreurs récurrentes? Corriger avant que ça empire

APRÈS 3 MOIS:
├─ Lancer: SELECT * FROM ai_6month_trend;
├─ Lancer: SELECT * FROM ai_fallback_effectiveness;
└─ Questions:
   - Usage croît? Rythme soutenable?
   - Fallbacks efficaces? Si non, revoir la chain
   - Coût GPU cloud justifié? (RunPod pour plan mensuel)

APRÈS 6 MOIS:
├─ Toutes les vues précédentes
├─ Decision: rester KVM 4 ou passer KVM 8 ou serveur maison?
│   → Basé sur la vraie consommation RAM et coûts cloud
├─ Decision: Qwen 7B suffit ou upgrade nécessaire?
│   → Basé sur taux d'hallucinations réel
└─ Decision: V3 features pertinentes?
    → Basé sur quels patterns d'usage ont le plus de valeur
```

---

## 18. How to Log in Code

Every AI call in the codebase should follow this pattern:

```python
import time
from uuid import uuid4
from app.db import db
from app.services.ai_logging import log_ai_call

async def call_sonnet_for_daily_plan(user_id, context):
    start = time.time()
    call_id = uuid4()
    
    try:
        response = await anthropic_client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": context}]
        )
        
        duration_ms = int((time.time() - start) * 1000)
        
        await log_ai_call({
            "id": call_id,
            "app_name": "imperium",
            "task_type": "morning_plan",
            "trigger_source": "morning_checkin",
            "model_used": "claude-sonnet-4.6",
            "model_tier": "cloud_standard",
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "duration_ms": duration_ms,
            "success": True,
            "related_entity_type": "daily_plan",
            # related_entity_id filled after plan is saved
        })
        
        return response
        
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        
        await log_ai_call({
            "id": call_id,
            "app_name": "imperium",
            "task_type": "morning_plan",
            "model_used": "claude-sonnet-4.6",
            "model_tier": "cloud_standard",
            "duration_ms": duration_ms,
            "success": False,
            "error_code": classify_error(e),
            "error_message": str(e)[:500],
        })
        
        raise
```

```python
# ai_logging.py — the central service
async def log_ai_call(data: dict):
    """
    Central function to log any AI call.
    Cost is auto-computed via DB trigger if tokens provided.
    """
    await db.execute("""
        INSERT INTO ai_call_logs (
            id, called_at, app_name, task_type, trigger_source,
            model_used, model_tier, input_tokens, output_tokens,
            duration_ms, success, error_code, error_message,
            related_entity_type, related_entity_id, parent_call_id,
            retry_attempt, fallback_used, original_model
        ) VALUES (
            %(id)s, NOW(), %(app_name)s, %(task_type)s, 
            %(trigger_source)s, %(model_used)s, %(model_tier)s,
            %(input_tokens)s, %(output_tokens)s, %(duration_ms)s,
            %(success)s, %(error_code)s, %(error_message)s,
            %(related_entity_type)s, %(related_entity_id)s,
            %(parent_call_id)s, %(retry_attempt)s,
            %(fallback_used)s, %(original_model)s
        )
    """, {
        "id": data.get("id", uuid4()),
        "app_name": data["app_name"],
        "task_type": data["task_type"],
        "trigger_source": data.get("trigger_source"),
        "model_used": data["model_used"],
        "model_tier": data.get("model_tier", "local"),
        "input_tokens": data.get("input_tokens"),
        "output_tokens": data.get("output_tokens"),
        "duration_ms": data.get("duration_ms"),
        "success": data.get("success", True),
        "error_code": data.get("error_code"),
        "error_message": data.get("error_message"),
        "related_entity_type": data.get("related_entity_type"),
        "related_entity_id": data.get("related_entity_id"),
        "parent_call_id": data.get("parent_call_id"),
        "retry_attempt": data.get("retry_attempt", 0),
        "fallback_used": data.get("fallback_used", False),
        "original_model": data.get("original_model"),
    })
```

---

## 19. Retention Policy

```text
ai_call_logs:
  - Keep all data indefinitely (it's small: ~1 KB per row)
  - At 50 calls/day: ~18,000 rows/year = ~18 MB/year
  - Trivial storage cost on VPS

ai_model_pricing:
  - Never delete (historical pricing needed for retroactive analysis)

Views:
  - Materialized if query becomes slow (after 100k+ rows)
  - Not needed before 1 year of data

After 2 years:
  - Archive rows older than 18 months to cold storage (JSONB dump)
  - Keep aggregate tables permanently
```

---

**Document version:** 2.0
**Status:** Imperium V1 reference — logging layer added
**Last updated:** 2026-05-16
