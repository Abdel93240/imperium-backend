# 52 - AI Decision Framework

## 1. Purpose

This document defines **how the AI brain decides what the user should do** across three time horizons:

- **Short term** — today's plan (the day-by-day operations)
- **Medium term** — the rolling 4-week plan (regenerated every Monday)
- **Long term** — patterns and trajectories (via WR + pgvector)

Without this framework, each app and each AI call operates on its own logic. With it, every decision flows from a single coherent system: priorities, scoring, planning, and learning.

This is the **operational brain** of the entire ecosystem.

---

## 2. The Three Horizons

```text
HORIZON 1 — DAILY (today)
  Generated each morning after the morning checkin.
  Reflects the rolling monthly plan AND the user's real-time state.
  Adapts via hooks throughout the day.

HORIZON 2 — ROLLING MONTHLY (4-week glide)
  Generated every Monday morning by the high reasoning model.
  Always 4 weeks forward from "now".
  Regenerated entirely each Monday based on what happened.
  Acts as the "spinal cord" that guides daily plans.

HORIZON 3 — LONG TERM (months / quarters / yearly)
  Not directly planned by the AI.
  Emerges from:
  - User objectives (V3, doc 45)
  - Pattern accumulation in pgvector
  - WR retrospectives
  - Ongoing trajectory observation
```

The daily plan is not generated in a vacuum. It instantiates the monthly plan for THIS specific day, adjusted to current reality.

---

## 3. The User-Defined Domain Hierarchy

Every user defines their own life priorities in Imperium settings.

### 3.1 The hierarchy (visible)

```text
SETTINGS — Priorités de vie (drag-to-reorder):

  Position 1 (haut):  [Religieux  ▼]
  Position 2:         [Business   ▼]
  Position 3:         [Finances   ▼]
  Position 4 (bas):   [Santé      ▼]

User can:
- Reorder positions anytime
- Choices stored in user_priorities table
- Changes propagate instantly to next plan generation
```

The 4 default domains are: Religieux, Business, Finances, Santé.

The hierarchy is **fully user-controllable**. If the user decides tomorrow that finances must come first, that's their right.

### Patch 7G — Priority Reconciliation

Patch 7G makes `imperium_user_priorities` the canonical read source for the
user's priority hierarchy.

- Dashboard priority context is read from `imperium_user_priorities`.
- Daily plan priority context is read from `imperium_user_priorities`.
- Mission scoring continues to use the Decision Framework hierarchy.
- Legacy `imperium_priority_rules` remains compatibility-only and must not be
  used as canonical ordering.
- Legacy priority writes are disabled; callers must use
  `/api/imperium/decision-framework/priorities`.

No AI call, n8n AI Agent, n8n DB write, pgvector write, embedding generation,
or automatic memory commit is introduced by this reconciliation patch.

### 3.2 The coefficients (invisible)

Behind each position sits a multiplier:

```text
Position 1 → coefficient ×10
Position 2 → coefficient ×8
Position 3 → coefficient ×5
Position 4 → coefficient ×4
```

These coefficients are **not shown to the user**. They are an internal tuning of the scoring system. The user sees only the order they chose.

The asymmetric distribution (10/8/5/4) ensures:
- A meaningful boost for the top priority
- Real differentiation between positions
- Without making lower priorities completely irrelevant

---

## 4. Mission Intrinsic Scoring (0-100)

Each mission candidate receives a **deterministic intrinsic score** between 0 and 100, computed from 5 measurable criteria.

The wide range (0-100) is intentional: it allows critical missions to mathematically dominate, even when their domain has a low coefficient.

### 4.1 Criterion A — DEADLINE PROXIMITY (0-30 points)

```text
├─ No deadline:                    0 pts
├─ Deadline > 30 days away:        5 pts
├─ Deadline 15-30 days away:      10 pts
├─ Deadline 7-14 days away:       15 pts
├─ Deadline 3-6 days away:        20 pts
├─ Deadline 1-2 days away:        25 pts
├─ Deadline today:                30 pts
└─ Deadline already passed:       30 pts (with urgency flag)
```

### 4.2 Criterion B — IMPACT GRAVITY (0-30 points)

```text
├─ Cosmetic (new shoes):           0 pts
├─ Quality of life (regular gym): 5 pts
├─ Mid-importance (paperwork):    10 pts
├─ Very important (car repair):   15 pts
├─ Critical (rent due in days):   20 pts
├─ Vital short-term (medical):    25 pts
└─ Vital immediate (ER visit):    30 pts
```

### 4.3 Criterion C — MISSION TYPE (0-20 points)

This replaces a subjective "is it recoverable?" judgement with a **categorical assignment** that is much more reliable for AI to evaluate.

The AI categorizes the mission into one of 9 categories:

```text
🚨 CAT A — VITAL IMMÉDIAT                    20 pts
   Acute respiratory difficulty, intense acute pain,
   accidents, severe bleeding, serious malaise.

⚖️ CAT B — JURIDIQUE/CONTRACTUEL             18 pts
   Tax declaration, rent/credit payment, official
   administrative dossiers, legal procedures.

🩺 CAT C — MÉDICAL PLANIFIÉ                  15 pts
   Doctor appointments, exams, follow-ups, fixed
   medication intake, ghusl required for prayer.

🕌 CAT D — RELIGIEUX OBLIGATOIRE             12 pts
   Mandatory prayers, sadaqa target, fasting respect,
   ramadan fasting.

💼 CAT E — TRAVAIL/REVENUS                   10 pts
   Planned VTC sessions, committed deliveries, client
   appointments, paid projects.

📚 CAT F — APPRENTISSAGE/COURS                8 pts
   Dars cours, study sessions, mandatory reading.

🏋️ CAT G — SANTÉ ROUTINE                     5 pts
   Planned workouts, balanced meals, hydration,
   daily walks.

🛒 CAT H — QUALITÉ DE VIE                    3 pts
   Cleaning, errands, organization, leisure.

✨ CAT I — OPTIONNEL                          0 pts
   Flexible mission with no impact if missed.
```

Categorization is performed silently by the local model. The user does NOT validate each categorization (impractical at ~50 missions/day). Errors are caught via the WR feedback loop (Section 9).

### 4.4 Criterion D — DEPENDENCY (0-10 points)

```text
"Do other missions depend on this one being done?"
├─ No dependency:                  0 pts
├─ 1-2 missions depend:            5 pts
└─ Multiple missions blocked:     10 pts
```

The system tracks dependencies in mission metadata. If "buy ingredients" must precede "cook for guest", the first gets dependency points.

### 4.5 Criterion E — RECURRENCE (0-10 points)

```text
├─ Daily routine (prayer, hydration):    0 pts
├─ Weekly routine (workout, dars):       3 pts
├─ Monthly routine (rent payment):       5 pts
├─ Yearly (tax declaration):             7 pts
└─ Exceptional/unique (vital event):    10 pts
```

The intuition: rare events tend to be more disruptive if missed than routine ones (which can be done tomorrow).

### 4.6 Total intrinsic score

```text
score_intrinsèque = A + B + C + D + E
                  = entre 0 et 100
```

Stored in `imperium_mission_scores` along with each criterion's value (for transparency and debugging).

---

## 5. Final Score Calculation

Once a mission has its intrinsic score and we know its domain, we compute the final score that determines its priority in the plan:

```text
score_final = score_intrinsèque × coef_domaine

Where coef_domaine depends on the user's hierarchy position
of that domain.
```

### 5.1 Examples

User's hierarchy: Religieux=10, Business=8, Finances=5, Santé=4

```text
EXAMPLE 1 — Difficulté respiratoire (Santé):
  intrinsèque = 100 (CAT A vital + deadline now + ...)
  final = 100 × 4 = 400 ✅ TOP — vital trumps everything

EXAMPLE 2 — Asr prayer (Religieux):
  intrinsèque = 35 (deadline today + religieux mandatory)
  final = 35 × 10 = 350

EXAMPLE 3 — Tax declaration deadline J-5 (Finances):
  intrinsèque = 67
  final = 67 × 5 = 335

EXAMPLE 4 — VTC session (Business):
  intrinsèque = 25
  final = 25 × 8 = 200

EXAMPLE 5 — Buy shoes (Finances):
  intrinsèque = 8
  final = 8 × 5 = 40
```

### 5.2 Why this works

```text
✅ DETERMINISTIC
   Same mission inputs → same score, always.

✅ EXPLAINABLE
   The user can ask "why is this priority?" and the system 
   shows the breakdown: A=20, B=15, C=15, D=0, E=5, total=55,
   coef Religieux ×10 = 550.

### 5.3 Mission decision-preview and decision-score

The mission `decision-preview` and `decision-score` routes are deterministic
backend-only reads.

- They use only fields already stored in PostgreSQL.
- They do not call AI.
- They do not call n8n.
- They do not write pgvector embeddings.
- They do not commit memory.
- They do not trigger calendar replanning.
- They do not expose `weighted_score`.
- They do not expose `domain_coefficient`.
- They do not expose the internal scoring formula.
- They expose a public `label` and optional `reason_codes` only.
- `reason_codes` are public-safe labels only.
- They are not a formula dump.
- Promotion remains a backend guardrail driven by the user flow, not an
  automatic AI decision.

✅ ADJUSTABLE
   Tuning is done by adjusting the criteria thresholds, not 
   by changing prompts.

✅ AI-FRIENDLY
   the local model categorizes (CAT A-I) and computes (deadline math).
   No subjective judgment required.

✅ EMERGENCIES DOMINATE
   A score of 100 in Santé (×4 = 400) beats a score of 35 
   in Religieux (×10 = 350). Vital missions win.
```

---

## 6. Mission Backlog (the 10 Conceptual Tables)

Missions live in a **single table** but are conceptually organized by 10 priority levels.

### 6.1 The structure

```text
At any time, the system has:
  Priority 10 — Critical / vital missions
  Priority 9
  Priority 8
  Priority 7
  Priority 6
  Priority 5
  Priority 4
  Priority 3
  Priority 2
  Priority 1 — Lowest priority backlog

A mission's priority slot is computed from its 
score_final via fixed brackets:
  score_final >= 700:  priority 10
  score_final 600-699: priority 9
  score_final 500-599: priority 8
  score_final 400-499: priority 7
  score_final 300-399: priority 6
  score_final 200-299: priority 5
  score_final 100-199: priority 4
  score_final  50-99:  priority 3
  score_final  20-49:  priority 2
  score_final   0-19:  priority 1
```

These brackets are tunable. They translate the continuous score into actionable priority levels.

### 6.2 What lives in the backlog

```text
Each mission carries:
  - id, title
  - domain (religieux | business | finances | santé)
  - estimated_duration_minutes
  - required_location (text or coordinates if specific)
  - required_skills (rare, e.g. need a car)
  - financial_impact (cost or income estimate)
  - prerequisite_mission_ids (dependencies)
  - source (ai_planner | path | vector | manual | calendar)
  - deadline_at (if any)
  - is_recurrent + recurrence_rrule
  - intrinsic_criteria_a, _b, _c, _d, _e
  - intrinsic_score
  - domain_coefficient
  - final_score
  - priority_level (1-10)
  - status (per doc 43 §5)
```

The backlog is alive: scores recompute when triggers happen (Section 7).

---

## 7. Score Recalculation Triggers

We do NOT recompute scores every day for every mission. We recompute on triggers:

```text
TRIGGER 1 — Mission added
  Initial score computed.

TRIGGER 2 — Mission edited
  Score recomputed.

TRIGGER 3 — Daily 06:00 cron (deadline progression)
  All open missions with deadlines have criterion A 
  recomputed (a deadline 5 days ago is now 4 days ago).
  Criteria B-E unchanged.

TRIGGER 4 — Calendar event added/modified within 7 days
  Affected missions are re-scored.

TRIGGER 5 — User priority hierarchy modified
  All missions re-scored (domain coefficients changed).

TRIGGER 6 — WR validated (each Tuesday)
  Scores reviewed and patterns surfaced for next 
  Monday's monthly plan.
```

This keeps compute lightweight and predictable.

---

## 8. The Rolling 4-Week Plan

The high reasoning model-generated monthly plan is the **spinal cord** of the operational brain.

### 8.1 When it runs

```text
Every Monday at 05:00 Europe/Paris.

Why Monday early:
- The user's Monday morning popup happens around 06:00-09:00
- The monthly plan must be ready before
- 05:00 leaves a comfortable buffer
- Sundays are part of the previous week (per ISO weeks)

If the cron fails: retry at 05:30, 06:00, 06:30.
If still failing: alert user, fall back to previous plan.
```

### 8.2 Inputs to the high reasoning model (10 categories)

The full input context (~25,000 tokens) given to the high reasoning model:

```text
CATEGORY 1 — User current state
  - Discipline score 4 weeks (composite)
  - Energy score average 2 weeks
  - Sleep hours average 2 weeks
  - Active pain logs
  - Mood patterns
  - Last WR emotional summary

CATEGORY 2 — Financial
  - Wallet total (cash + bank + crypto)
  - Pressure score
  - Business profit 4 weeks (trend)
  - Average weekly expenses
  - Sadaqa carry forward
  - Upcoming expenses (30 days)
  - User financial objectives (V3)

CATEGORY 3 — Calendar (V3, doc 51)
  - All events next 4 weeks
  - All deadlines
  - Vacances/voyages
  - Periodic blockers
  - Religious events (Ramadan, Aïd)
  - Active recurrences

CATEGORY 4 — Mission backlog
  - All missions priority 1-10 active
  - With full metadata
  - Sorted by priority within each level
  - Including auto-generated (ghusl, replans, etc.)

CATEGORY 5 — Hierarchy & objectives
  - User domain hierarchy
  - Domain coefficients
  - Active user objectives (V3)
  - Meta-prompts per app (V3)

CATEGORY 6 — Learned patterns (pgvector)
  - Top insights from last 4 WRs (decay-weighted)
  - Vector patterns (zones, days)
  - Pulse patterns (best workout hours)
  - Path patterns (prayer regularity)
  - Imperium patterns (completion rate by type)

CATEGORY 7 — Biological capacity
  - Minimum sleep hours (from Pulse health doc)
  - Maximum activity windows
  - Active medical restrictions

CATEGORY 8 — Recurring engagements
  - Weekly Dars cours (Path)
  - Habitual VTC sessions
  - Recurring workouts
  - Daily prayers
  - Adhkar routines

CATEGORY 9 — Seasonal & external context
  - Current season
  - Major Paris events (concerts, etc.)
  - School holidays (impact on VTC traffic)
  - Weather forecast (V4, not V3)

CATEGORY 10 — Last week retrospective
  - Previous monthly plan (what was scheduled)
  - What was completed
  - What was failed (with reasons)
  - Hooks triggered (replans)
  - Decisions made via chatbot
  - Calendar modifications
```

### 8.3 The high reasoning model prompt (sketch)

```text
You are generating the rolling 4-week monthly plan for the user.

[User profile]

[All 10 input categories above]

YOUR TASK:
1. Plan the next 4 weeks day by day with TIME-DETAILED missions.
2. The plan IS detailed (with hours), but IS NOT gospel: 
   it's the spinal cord. Daily AI will adjust.
3. Respect the user priority hierarchy (×10/×8/×5/×4 coefficients).
4. Top priority items: never skipped (prayers, deadlines).
5. Missions must respect the user's biological capacity 
   (sleep hours, max activity).
6. Recurring engagements must be present every week.
7. Calendar events are immutable: plan around them.
8. Missions from backlog distributed by priority and deadline.
9. Coherence: prepare for upcoming events, build progressively
   toward objectives.
10. Honesty: if the workload is unrealistic, flag it explicitly.

OUTPUT FORMAT (strict JSON):
{
  "plan_period_start": "2026-05-13",
  "plan_period_end":   "2026-06-09",
  "weeks": [
    {
      "week_index": 1,
      "days": [
        {
          "date": "2026-05-13",
          "missions": [
            {
              "title": "Fajr",
              "domain": "religieux",
              "scheduled_at": "06:30",
              "duration_minutes": 15,
              "from_backlog": false,
              "rationale": "Daily prayer, fixed time"
            },
            ...
          ]
        },
        ...
      ]
    },
    ...
  ],
  "warnings": [
    "Week 3 is dense due to dar deadline; consider lightening 
     the workout in week 2."
  ],
  "key_objectives_progress": {
    "abdos_visibles_ete": "On track per current trajectory",
    "vtc_revenue_weekly": "Plan delivers 1450€/week average"
  }
}
```

### 8.4 Validation by the local model

After the high reasoning model returns:

```text
the local model runs sanity checks LOCALLY:
  - Are sleep hours respected each day? (≥ minimum from Pulse)
  - Are mandatory prayers present every day?
  - Are calendar events not overlapping with planned missions?
  - Is the total work intensity realistic per discipline_score?
  - Are deadlines respected (every deadline has a planned slot 
    before it)?
  - Are vacances days truly empty of VTC?
  
If all OK: plan is saved as canonical.
If issues found: feedback loop (Section 8.5).
```

### 8.5 The fallback loop

```text
ATTEMPT 1 — the high reasoning model generates plan.
  the local model validates.
  If OK: SAVED.
  If KO: keep the issues list.

ATTEMPT 2 — the high reasoning model regenerates with the feedback.
  Same local model validation.
  If OK: SAVED.
  If KO: escalate.

ATTEMPT 3 — GPT-5.5 takes over.
  Same prompt + the fallback context.
  Same local model validation.
  If OK: SAVED (logged as "fallback used").
  If KO: ABORT.

ABORT — Last resort.
  - Send alert to user: "Plan generation issues this week.
    Continuing with last week's plan adapted."
  - Re-use previous monthly plan with date-shifts.
  - Schedule manual review for next session.
```

This caps the cost at approximately:
- 2 × the high reasoning model calls (~0.40€)
- 1 × GPT-5.5 call (~0.10€)
- Worst case total: ~0.50€ per monthly generation
- Annual: ~26€ if always worst case (highly unlikely)
- Realistic annual: ~10€

### 8.6 Storage

```sql
CREATE TABLE imperium_monthly_plans (
  id                       UUID PK,
  user_id                  UUID FK,
  generated_at             TIMESTAMPTZ,
  plan_period_start        DATE,
  plan_period_end          DATE,
  generation_attempt       INTEGER, -- 1, 2, or 3 (fallback)
  generation_model         VARCHAR(32), -- 'opus-4.8' or 'gpt-5.5'
  plan_json                JSONB,
  warnings                 TEXT[],
  key_objectives_progress  JSONB,
  validation_passed        BOOLEAN,
  superseded_at            TIMESTAMPTZ NULL,
  is_active                BOOLEAN DEFAULT TRUE
);
```

All plans are kept forever. They feed the WR retrospective and the high reasoning model's pattern recognition (next Monday's plan sees what was prescribed last week and what actually happened).

---

## 9. The Daily Plan (Instantiation)

The daily plan is generated each morning AFTER the morning checkin.

### 9.1 The flow

```text
06:00 (or user's wake time): Morning checkin popup.
User submits: energy, sleep, pain, mood, special context.

Backend:
  1. Read the active monthly plan
  2. Read morning checkin
  3. Read calendar events for today
  4. Read recent hooks (e.g. last night's mission failures)
  5. Check what was already scheduled by the high reasoning model for today

DECISION TREE:

  IF morning context matches what the high reasoning model expected:
    → Plan = monthly plan for today, unchanged
    → Quick generation by the local model (just timing refinements)
    → Cost: 0€ (local)

  ELSE (energy low, pain high, special event):
    → Plan = adapted from monthly plan
    → the local model considers monthly plan + current state
    → Adjusts mission selection and timing
    → Cost: 0€ (local)
    → Logged as "adapted from monthly plan"
```

### 9.2 Inputs to the local model (daily generation)

Smaller context (~5,000 tokens):

```text
- Today's row from the monthly plan (~500 tokens)
- Morning checkin (~200 tokens)
- Today's calendar events (~500 tokens)
- Last 3 days hook history (~500 tokens)
- Top 20 active missions from backlog (~2,000 tokens)
- User priority hierarchy (~200 tokens)
- Active medical/recurrence rules (~500 tokens)
- Yesterday's discipline score and outcomes (~300 tokens)

Total: ~5,000 tokens
Local V1 cost: 0€
Fallback reference if the first cloud tier is activated: ~0.02-0.05€/call,
~18€/year
```

### 9.3 Output

```text
Daily plan with timed missions:
- Specific clock times
- Travel time included between locations
- Buffer time between intense missions
- Respects calendar
- Aligns with monthly plan when possible
- Documents deviations

User sees the plan on Imperium dashboard.
Missions get status='active'.
Throughout the day, hooks may trigger replans (per doc 43 §3).
```

### 9.4 V1 model choice and fallback

```text
V1 MODEL CHOICE — DAILY PLAN:
The daily plan is generated by the local model in V1. Reasons: the task is light
instantiation (timing + adaptation), the local model is capable, it is free, and it keeps all
sensitive daily data local (privacy).

FALLBACK (documented, observation-based): if, in real use, the local model proves insufficient
on this task (weak plans, continuity/priority errors), switch the daily plan to
the first cloud tier. Cost would be ~18€/year — negligible — and justified only if a real
quality gap is observed. This is a deliberate test-first decision, not an a-priori
one.

MONTHLY PLAN: unchanged — the monthly strategic plan is generated by the high reasoning model.
Only the DAILY instantiation moves to the local model.
```

## 9A. Local Degradation & Cloud Fallback (access-regime principle)

This is a general principle, applied across the ecosystem wherever a local component
becomes unavailable and a cloud model takes over.

Principle: "the cloud model replaces the local one" describes WHICH model answers, NOT
identical data access. The replacement shifts from LOCAL to CLOUD, which changes the
ACCESS REGIME:
- LOCAL (the local model, local OCR, local embedding...): reads freely - nothing leaves the
  machine, so the privacy gate does not need to filter a purely local treatment.
- CLOUD fallback: subject to the privacy gate exactly like any external call. What may
  leave the machine is filtered/minimized before reaching the cloud model.

Locked decision: for very_high content (sensitive medical, religious), the service
DEGRADES (abstention or reduced capability) rather than sending to the cloud. Continuity
is never paid for in confidentiality. A degraded service is preferred over leaking
sensitive data.

This is distinct from the QUALITY fallback (§8.5, §9.4: the local model insufficient → the first cloud tier).
Here the trigger is AVAILABILITY (local is down), and the key consequence is the
access-regime change above.

Application cases (all refer back here):
- Ephemeral working vector store: the local model down → the first cloud tier reads the store under the gate
  (doc 38 §7-bis).
- OCR: local OCR down → the OCR service fallback under the gate (doc 37).
- LoRA training: data sent to a rented cloud GPU, de-identified, GDPR provider
  (doc 74 §9).
- Extensible: any future local→cloud handoff follows this principle.

---

## 10. Mission Refusal — How User Disagrees

A mission can be marked as failed (status='ratée') with one of 4 reasons:

```text
WHEN USER TAPS "NON" ON A MISSION:

Modal appears with 4 options:

  ⚪ Pas eu le temps           [no follow-up needed]
  ⚪ Trop fatigué              [no follow-up needed]
  ⚪ Pas pertinent             [opens chat for explanation]
  ⚪ Empêchement               [opens chat for explanation]
```

### 10.1 "Pas eu le temps" / "Trop fatigué"

```text
Stored as:
  - mission.status = 'ratée'
  - mission.failure_reason = 'no_time' or 'too_tired'
  - mission.failure_detail = NULL

These signals are pattern-rich without explanation:
- Frequent "no time" → workload is too dense, monthly plan
  must lighten
- Frequent "too tired" → energy management issue, sleep or
  workout balance problem

Both surface in WR analysis automatically.
```

### 10.2 "Pas pertinent"

```text
Critical signal: the AI made a decision the user disagrees with.
This MUST be understood for next plans.

Modal opens chatbot:
  "Tu as marqué cette mission comme non pertinente.
   Pourquoi ?"

User explains in free text.

Backend (the local model analyzes):
  - What is the nature of the disagreement?
    * Wrong priority?
    * Wrong timing?
    * Wrong domain?
    * Personal context AI didn't know?
  - Tag the failure_detail with the analyzed reason
  - Store in pgvector with high weight

Next monthly plan (next Monday):
  - the high reasoning model sees this disagreement in pattern history
  - Adjusts categorization or timing logic
  - Less likely to repeat
```

### 10.3 "Empêchement"

```text
Material/external/skill-based blocker.
Different from "not relevant": the user agreed with the plan,
something prevented execution.

Modal opens chatbot:
  "Tu as marqué un empêchement. Qu'est-ce qui a empêché ?"

User explains: car broke down, no money, lacks skills, etc.

Backend (the local model analyzes):
  - Categorize the empêchement type:
    * Material (car, tools, equipment)
    * Financial
    * Skills/competence
    * External (weather, others)
  - Tag the failure_detail
  - Store in pgvector for future reference

Next monthly plan:
  - the high reasoning model considers the empêchement type
  - If material/financial: backlog the mission until 
    blocker is removed
  - If recurring blocker: adjust mission expectations
```

### 10.4 Why no per-mission validation at addition time

```text
Reality of usage: ~50 missions per day.

If the user had to validate each AI categorization:
  - 50 popups per day is impractical
  - User fatigue would lead to careless validation
  - The system would become overhead, not assistant

Instead:
  - AI categorizes silently
  - Wrong categorizations surface via mission failures
  - WR captures patterns over time
  - the high reasoning model self-corrects in next monthly plan
  - User intervenes only when something is wrong (refusal)

This aligns with the brain unified philosophy (doc 44):
  Trust the system, learn from feedback, self-correct.
```

---

## 11. Learning From Mission Outcomes

```text
Every completed or failed mission generates an outcome record:

mission_outcomes table:
  - mission_id
  - status (completed | failed_no_time | failed_too_tired 
            | failed_not_relevant | failed_blocked)
  - actual_start_time
  - actual_end_time
  - actual_duration_minutes
  - failure_explanation (if Pas pertinent or Empêchement)
  - failure_category (analyzed by the local model)
  - completed_at | failed_at
```

### 11.1 Duration learning

```text
Over time, the system learns the REAL duration of mission types:

  "Morning routine" planned: 30 min
  Actual durations observed: 35, 42, 38, 40, 32 → avg 37 min

After 5 occurrences, AI uses 37 min as the new estimate.
After 20 occurrences, the estimate is well-calibrated.

This calibration runs nightly:
  For each mission_type with ≥5 outcomes in last 30 days:
    Compute median duration
    Update mission_type_learned_durations table
    
Next plan generation uses these learned durations.
```

### 11.2 Pattern detection

```text
Recurring patterns surface in WR analysis:

EXAMPLES:
  - "VTC sessions on Mondays consistently underperform"
    → AI may avoid scheduling intense Monday VTC

  - "Workouts on Fridays always skipped"
    → AI moves Friday workouts elsewhere or removes them

  - "Tax-related missions always 'pas pertinent' before 
    deadline-30 days"
    → AI adjusts deadline criterion to spike closer to deadline

These patterns feed the next monthly plan as Category 6 inputs.
```

---

## 12. Database Schema

```sql
CREATE TABLE user_priorities (
  id              UUID PK,
  user_id         UUID FK UNIQUE,
  position_1      VARCHAR(32) NOT NULL, -- e.g. 'religieux'
  position_2      VARCHAR(32) NOT NULL,
  position_3      VARCHAR(32) NOT NULL,
  position_4      VARCHAR(32) NOT NULL,
  updated_at      TIMESTAMPTZ
);

CREATE TABLE imperium_mission_scores (
  id                       UUID PK,
  mission_id               UUID FK,
  criterion_a              INTEGER, -- deadline proximity 0-30
  criterion_b              INTEGER, -- impact gravity 0-30
  criterion_c_category     VARCHAR(2), -- 'A' to 'I'
  criterion_c              INTEGER, -- 0-20 from category
  criterion_d              INTEGER, -- dependency 0-10
  criterion_e              INTEGER, -- recurrence 0-10
  intrinsic_score          INTEGER, -- 0-100
  domain                   VARCHAR(32),
  domain_coefficient       INTEGER,
  final_score              INTEGER, -- intrinsic × coef
  priority_level           INTEGER, -- 1-10
  computed_at              TIMESTAMPTZ
);

CREATE TABLE imperium_monthly_plans (
  -- per Section 8.6
);

CREATE TABLE imperium_daily_plans (
  id                  UUID PK,
  user_id             UUID FK,
  date                DATE,
  monthly_plan_id     UUID FK NULL, -- if derived from monthly
  status              VARCHAR(32), -- 'draft' | 'active' | 'completed'
  plan_json           JSONB,
  generated_at        TIMESTAMPTZ,
  generated_model     VARCHAR(32), -- 'qwen-local' typically; 'sonnet-4.6' fallback
  is_adapted          BOOLEAN,     -- TRUE if differs from monthly
  adaptation_reason   TEXT NULL,
  cost_eur            NUMERIC(6,4)
);

CREATE TABLE mission_outcomes (
  id                       UUID PK,
  mission_id               UUID FK,
  user_id                  UUID FK,
  status                   VARCHAR(32),
  actual_start_time        TIMESTAMPTZ NULL,
  actual_end_time          TIMESTAMPTZ NULL,
  actual_duration_minutes  INTEGER NULL,
  failure_explanation      TEXT NULL,
  failure_category         VARCHAR(64) NULL,
  completed_at             TIMESTAMPTZ NULL,
  failed_at                TIMESTAMPTZ NULL,
  recorded_at              TIMESTAMPTZ
);

CREATE TABLE mission_type_learned_durations (
  id                       UUID PK,
  user_id                  UUID FK,
  mission_type_signature   VARCHAR(128), -- normalized title pattern
  median_duration_minutes  INTEGER,
  sample_count             INTEGER,
  last_updated_at          TIMESTAMPTZ
);
```

---

## 13. Cost Summary (Annual)

```text
┌──────────────────────────────────────────────────────┐
│ TASK                          │ FREQUENCY  │ COST/YR │
├──────────────────────────────────────────────────────┤
│ Monthly plan (the high reasoning model) │ 52 × /year │ ~10€    │
│ Plan validation (the local model)       │ 52 × /year │ 0€      │
│ Fallback GPT-5.5 (rare)       │ ~5 × /year │ ~0.50€  │
│ Daily plan (the local model)       │ 365 × /year│ 0€      │
│ Daily first cloud tier fallback         │ if needed  │ ~18€    │
│ Mission scoring (the local model)        │ on trigger │ 0€      │
│ Mission categorization (the local model) │ on add     │ 0€      │
│ Failure analysis (the local model)       │ as needed  │ 0€      │
├──────────────────────────────────────────────────────┤
│ BASELINE ANNUAL                             │ ~10-12€│
└──────────────────────────────────────────────────────┘
```

For comparison: a single human life-coach session costs more.

---

## 14. Integration With Other Modules

### 14.1 With doc 43 (Imperium Logic)

```text
The hooks system from doc 43 §3 is the trigger mechanism.
This document defines what happens when a hook fires:
- Re-scoring of affected missions
- Possible plan adaptation (the local model, with documented first-cloud-tier fallback)
- Update of monthly plan retrospective
```

### 14.2 With doc 44 (Brain Unified)

```text
The decision framework lives inside the unified brain.
The brain consults user_priorities + scoring system 
when arbitrating between competing events.
```

### 14.3 With doc 32 (WR)

```text
The WR is the formal moment to surface scoring patterns.
Wrong categorizations, repeated failures, drift from objectives:
all surface in the weekly review for correction.
```

### 14.4 With doc 38 (Vectorization)

```text
Mission outcomes (especially failures with explanations)
are vectorized for long-term pattern memory.
The high reasoning model retrieves these on next monthly plan generation.
```

### 14.5 With doc 45 (User Objectives)

```text
User objectives provide direction.
The decision framework executes that direction tactically.
```

### 14.6 With doc 51 (Calendar)

```text
Calendar events are HARD constraints in the plan.
The framework plans AROUND them, never on top.
```

---

## 15. Implementation Order

```text
Phase 1 — Core scoring system
  ├─ user_priorities table & UI
  ├─ Mission scoring service (criteria A-E)
  ├─ Domain coefficient logic
  └─ Score storage and retrieval

Phase 2 — Backlog management
  ├─ Mission backlog views
  ├─ Priority level brackets
  └─ Score recalculation on triggers

Phase 3 — Monthly plan generation
  ├─ high reasoning model prompt template
  ├─ Input assembly service (10 categories)
  ├─ local model validation logic
  ├─ Fallback chain (the high reasoning model → the high reasoning model → GPT-5.5)
  └─ Storage of plan history

Phase 4 — Daily plan instantiation
  ├─ local model prompt for daily plan
  ├─ Adaptation logic (vs monthly)
  └─ Hook integration

Phase 5 — Refusal & feedback
  ├─ 4 refusal buttons in UI
  ├─ Chat opening for "Pas pertinent" / "Empêchement"
  ├─ local model analyzer for explanations
  └─ Storage in mission_outcomes + pgvector

Phase 6 — Learning systems
  ├─ Duration learning nightly cron
  ├─ Pattern detection in WR
  └─ Feedback to next monthly plan

Phase 7 — Tuning
  ├─ Field testing for 4-8 weeks
  ├─ Threshold adjustments based on observed scores
  ├─ Categorization corrections
  └─ Coefficient tuning if hierarchy feels off
```

---

## 16. Tuning Philosophy

```text
THIS DOCUMENT DEFINES STARTING VALUES.

In real usage:
  - Some criteria thresholds may need adjustment
  - Some category boundaries may be unclear
  - Some coefficients may not feel right

This is EXPECTED.

Tuning is done by:
  1. Observing patterns in mission failures
  2. User noting "this kept being too high/low"
  3. Adjusting thresholds in user_priorities or 
     scoring_config tables
  4. Re-scoring all active missions

Do NOT change the framework structure unless deeply needed.
DO change the numbers based on real-world data.

The system gets sharper with every WR.
```

---

## 17. Non-Goals

```text
❌ Asking user to validate each mission's categorization
❌ Manual scoring of every mission
❌ Per-day high reasoning model calls (too expensive)
❌ Real-time score updates (only on triggers)
❌ Hidden coefficients changing without user knowing 
   the hierarchy moved
❌ Auto-deletion of failed missions (user keeps history)
```

---

## 17A. Backend V1 Public Contract Status

Patch 7E aligns the implemented backend score-preview contract with this
document before mission score storage is enabled.

Public score-preview criteria are:

```text
deadline
impact
mission_type
dependency
recurrence
```

The public explanation uses these keys:

```text
deadline_points
impact_points
mission_type_points
dependency_points
recurrence_points
```

Temporary input aliases:

- `effort` may still be accepted as an alias for `mission_type`;
- `alignment` may still be accepted as an alias for `recurrence`;
- both aliases are reported through explicit warnings and are not canonical
  public vocabulary.

Coefficient privacy:

- the user-facing API exposes the user's domain order and `domain_position`;
- raw coefficients remain internal;
- public responses do not expose `domain_coefficient`,
  `position_to_coefficient`, `weighted_score`, or `final_weighted_score`;
- score-preview returns a `priority_bucket` from 1 to 10 instead of raw
  coefficient math.

Patch 7E adds no mission score persistence, no calendar tables, no frontend,
no real AI call, no n8n workflow, no pgvector write, and no embeddings.

Patch 7F-1 prepares `imperium_missions` for later Decision Framework scoring.

Structural mission fields now available:

```text
domain                 nullable, one of religious/business/finance/health
priority_level         nullable, 1..10
mission_type_category  nullable, cat_a..cat_i
status                 now also allows backlog
```

Important boundaries:

- these fields are nullable while legacy and active mission flows migrate;
- `priority_level` existed before Patch 7F-1 and now receives explicit
  database validation;
- no score is calculated from these fields by 7F-1 alone;
- the backlog status is storage-compatible, but the full backlog engine is not
  implemented yet;
- coefficients remain internal and are not accepted from clients.

Patch 7F-2 adds controlled backend-only mission score storage on
`POST /api/imperium/missions/start`.

Storage rules:

- if `domain` is absent, no score row is created;
- if no scoring signal is present, no score row is created;
- scoring signals are `deadline_at`, `impact`, `mission_type`,
  `dependency`, `recurrence`, or `mission_type_category`;
- when `mission_type` is absent, `mission_type_category` can be used as the
  mission type scoring signal;
- client-submitted score values are rejected (`intrinsic_score`,
  `weighted_score`, `domain_coefficient`, `final_weighted_score`,
  `coefficient`, `score`, `priority_bucket`);
- the backend computes and stores internal coefficient/weighted score fields
  in `imperium_mission_scores`;
- the public response only exposes `intrinsic_score`, `priority_bucket`,
  `score_status`, `missing_fields`, and `source`;
- `(user_id, mission_id, source)` is unique for mission scores so retries
  cannot create duplicate `decision_framework_v1` score rows.

Patch 7F-2 still adds no monthly planning, no daily adaptation, no frontend,
no real AI call, no n8n workflow, no pgvector write, no embeddings, and no
public coefficient exposure.

Patch 7G makes `imperium_user_priorities` the canonical priority source.

Priority source policy:

- canonical reads/writes use
  `GET/POST /api/imperium/decision-framework/priorities`;
- legacy `imperium_priority_rules` rows are kept for historical compatibility
  and are not deleted;
- legacy `GET /api/imperium/priorities` returns a compatibility projection
  generated from `imperium_user_priorities`;
- legacy priority writes are disabled and return a clear error directing the
  caller to `/api/imperium/decision-framework/priorities`;
- dashboard and daily plan priority context read the Decision Framework order;
- no double-write bridge is introduced between the old and new tables.

Patch 7G adds no migration, no destructive legacy data change, no frontend, no
real AI call, no n8n workflow, no pgvector write, and no embeddings.

Patch 7H adds the minimal Imperium Calendar foundation.

Decision Framework impact:

- calendar events are stored as backend-owned constraints only;
- current daily and monthly planning do not automatically consume them yet;
- future monthly planning may use calendar constraints as input context when
  the planning layer is explicitly implemented;
- no AI scheduling, auto-replan, recurrence handling, n8n AI Agent, pgvector
  write, or embeddings are introduced by Patch 7H.

Patch 8A adds the mission backlog foundation.

Decision Framework impact:

- backlog missions are created and listed through backend-owned Imperium APIs;
- backlog scoring is deterministic and backend-only;
- a score row is created only when the mission has a domain and at least one
  supported scoring signal;
- public backlog APIs expose the `priority_bucket` summary, not internal
  coefficients or weighted scores;
- promotion from backlog to active preserves the one-active-mission rule;
- GET backlog supports pagination and optional `domain` / `priority_level`
  filtering.

Patch 8A intentionally does not add monthly plan generation, daily plan
generation, AI calls, n8n workflows, automatic replanning, calendar constraint
consumption, pgvector writes, embeddings, or automatic memory commits.

Patch 8B adds a read-only backlog decision preview.

Decision Framework impact:

- `GET /api/imperium/missions/backlog/decision-preview` returns the current
  deterministic priority preview for backlog missions;
- preview is scoped to the current authenticated user;
- optional `domain`, `priority_level`, `limit`, and `include_reasons` query
  parameters narrow the candidate projection;
- candidates use the same documented backlog ordering:
  `priority_bucket` descending, `priority_level` ascending, `created_at`
  ascending, then `id` as stable tie-breaker;
- the response exposes only safe score summaries: `label` and optional
  `reason_codes`;
- raw coefficients, weighted scores, `started_at`, and `ended_at` are not
  exposed.

Patch 8B intentionally does not change mission status, promote missions,
generate plans, call AI providers, call n8n, write pgvector, generate
embeddings, commit memory, or consume calendar constraints.

---

## 18. References

- `08_NON_NEGOTIABLE_RULES.md` — backend authority
- `30_AI_ROUTING_AND_SCORING_POLICY.md` — model selection
- `32_WR_INTERACTIVE_WORKFLOW.md` — feedback loop
- `38_VECTORIZATION_PIPELINE.md` — pgvector storage
- `43_IMPERIUM_LOGIC_DETAIL.md` — mission lifecycle, hooks
- `44_BRAIN_UNIFIED_LOGIC.md` — unified brain philosophy
- `45_USER_OBJECTIVES_FEATURE.md` — long-term direction
- `47_WR_GUIDED_SECTIONS.md` — WR structure
- `51_FUTURE_CALENDAR.md` — calendar constraints

---

## 19. Final Note

```text
This framework is the OPERATING SYSTEM of decisions.
Without it, every AI call is a fresh guess.
With it, every call is a coherent step in a continuous trajectory.

The framework is FIXED in shape but TUNABLE in numbers.
The brain is unified, the logic is shared, the user is master.
```

---

**Document version:** 1.0
**Status:** Architectural specification — V2 implementation
**Last updated:** 2026-04-29
