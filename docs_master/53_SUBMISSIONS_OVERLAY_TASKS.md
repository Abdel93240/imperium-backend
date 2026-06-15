# 53 - Submissions / Overlay Tasks (V3)

> ⚠️ **V3 feature — quality of life, post-V1 and V2.**
> Optional secondary tasks displayed inside active missions, 
> letting the user opportunistically handle small things 
> during long carrier missions.

---

## 1. Purpose

Allow the user to **handle small tasks (calls, emails, quick searches) DURING long, low-mental-load missions** like VTC sessions, instead of blocking dedicated time slots for them.

The goal: optimize the user's time without imposing pressure, and without the AI deciding when the user should do them.

---

## 2. The Insight That Drove This Feature

```text
Real-world observation by the user:
  "I was driving VTC between two clients.
   I realized I had been forgetting for 2-3 days to call 
   someone. I could have done it right then, but Imperium 
   never suggested it as something I could fit into my 
   active VTC time."

The system was creating standalone missions for these tasks,
forcing the user to dedicate separate time slots. But many 
small tasks can be handled DURING longer, low-effort missions.

Submissions solve this.
```

---

## 3. Why V3 And Not Earlier

```text
V1 — Mission lifecycle, scoring framework, daily plans.
V2 — WR sections, smart fuel, decision framework.
V3 — Submissions land here as a quality of life optimization.
```

This requires the decision framework (doc 52) to already classify mission types correctly. Without that foundation, submissions wouldn't have reliable "carrier missions" to attach to.

---

## 4. Core Architecture

```text
TWO CONCEPTS:

CARRIER MISSION
  An active mission that meets two criteria:
  1. LONG duration (typically > 1 hour)
  2. LOW physical demand (not workouts, not moving heavy stuff)
  
  Examples:
  - VTC session (long, sitting in car between clients)
  - Walking errands (light physical, time available)
  - Travel time (on public transit)
  
  Examples that are NOT carriers:
  - Workout (high physical, focus needed)
  - Prayer (focus required)
  - Dars cours (concentration)
  - Cooking (hands and mental engaged)
  - Sleep
  - Meals

SUBMISSION
  A small task that:
  1. Belongs to a "overlay-eligible type"
  2. Can be done in 3-15 minutes
  3. Doesn't require specific physical context
  4. Is currently active in the user's mission backlog

When a CARRIER MISSION is active, eligible SUBMISSIONS are 
displayed in a small panel inside the mission UI.
```

---

## 5. The Overlay-Eligible Types (Initial List)

The AI uses this **fixed list** to determine if a mission can be a submission. Categories evolve over time via WR feedback and manual tuning.

```text
📞 COMMUNICATION (5-15 min)
  ├─ Coup de téléphone bref
  ├─ Email/SMS rapide à envoyer
  ├─ Répondre à un message vocal
  └─ Confirmation RDV par téléphone

🔎 RECHERCHE (3-10 min)
  ├─ Recherche internet ponctuelle
  ├─ Vérifier infos site web
  ├─ Vérifier horaires d'un commerce
  └─ Comparer prix rapidement

📋 ADMINISTRATIF LIGHT (5-15 min)
  ├─ Réserver RDV en ligne
  ├─ Vérifier solde bancaire
  ├─ Confirmer une commande
  ├─ Renouveler abonnement
  └─ Lire et trier emails rapidement

🧠 MENTAL LIGHT (durée variable)
  ├─ Écouter podcast / cours audio
  ├─ Réfléchir à un sujet (pas critique)
  ├─ Adhkar (récitation)
  └─ Lecture courte d'article

📱 SOCIAL LIGHT (3-10 min)
  ├─ Souhaiter anniversaire
  ├─ Prendre nouvelles d'un proche
  ├─ Partager info avec quelqu'un
  └─ Photo + envoi
```

### 5.1 Explicitly excluded (never overlay-eligible)

```text
🚫 NEVER OVERLAY (exclusion by mission TYPE — perceivable by the AI):
  ├─ Toute mission Catégorie A (vital immédiat)
  ├─ Prières (besoin focus complet)
  ├─ Workouts (intense physique)
  ├─ Cours Dars (concentration totale)
  ├─ Ghusl
  ├─ Sleep
  └─ Tâches qui demandent ordinateur/papier physique
```

**Overlay-eligibility is defined by mission TYPE, never by a non-perceivable
internal moment.** The AI knows which mission TYPE is active (prayer, workout,
VTC session…) — it does NOT know transient internal states (driving a ride
right now vs parked, social meal vs quick bite). So exclusions apply to whole
types the AI can see; within a carrier, the user freely chooses when to act.

This avoids re-introducing the shortcut we removed (the AI guessing an internal
state it can't observe). Trust the user: he organized his life before Imperium
and can keep doing so.

### 5.2 Evolution of the list

```text
The list is NOT frozen. It evolves through:

1. WR FEEDBACK
   "I never do submissions during VTC because I focus on driving"
   → adjust the carrier mission rules

2. MANUAL TUNING
   Admin/developer adjusts the list based on observed usage

3. PATTERN DETECTION
   If user systematically rejects "podcast listening" as 
   submission, this category gets demoted

4. PERSONAL LEARNING (V4+)
   AI learns the user's specific tolerance per category
```

The VTC feedback example is now resolved at the root: VTC is a carrier; only
active driving would be off, and active driving is a non-perceivable internal
moment. The system does not encode non-perceivable moments.

Submission volume is small by nature: these are few, low-engagement, low-
commitment tasks — not an endless stream. If the user keeps up, the backlog
empties quickly and there is soon almost nothing left to overlay. So over-
solicitation is a non-issue, and no elaborate defensive exclusion rules are
needed. Submissions are optional and the reserve is modest and self-depleting.

---

## 6. The Carrier Mission Rules

A mission is a "carrier" when:

```text
RULE 1 — Long duration
  Estimated duration ≥ 60 minutes
  (configurable, can be adjusted to 90 min for stricter rules)

RULE 2 — Low physical demand
  Mission type is NOT in the "high-physical" set:
    workouts, moving, cleaning, cooking, dance, sport

RULE 3 — Low mental focus required (V4 future)
  Mission type is NOT in the "high-focus" set:
    studying, dars cours, complex calculations, exam prep

For V3, only RULES 1 and 2 are enforced.
RULE 3 added in V4 if pattern detection shows it's needed.
```

### 6.1 The carrier categorization

```text
At mission creation, AI categorizes the mission:
  - Determines is_carrier_mission TRUE/FALSE based on:
    * estimated_duration_minutes
    * physical_demand_category (mapped from mission type)

Stored in imperium_missions table:
  - is_carrier_mission BOOLEAN
  - is_overlay_eligible BOOLEAN
  - overlay_category VARCHAR(64) NULL  -- if eligible
```

### 6.2 Examples

```text
EXAMPLE 1 — VTC session 8h
  Duration: 480 min ≥ 60 → ✅ long
  Physical: sitting in car → ✅ low-physical
  → is_carrier_mission = TRUE

EXAMPLE 2 — Workout 45 min
  Duration: 45 min < 60 → ❌ short
  Physical: high → ❌ blocking anyway
  → is_carrier_mission = FALSE

EXAMPLE 3 — Errands walking 90 min
  Duration: 90 min ≥ 60 → ✅ long
  Physical: light walking → ✅ low-physical
  → is_carrier_mission = TRUE

EXAMPLE 4 — Cooking dinner 60 min
  Duration: 60 min ≥ 60 → ✅ long
  Physical: medium-high (hands engaged) → ❌ blocking
  → is_carrier_mission = FALSE
```

---

## 7. The User Interface

Front-end (French, what the user sees):
- **mission principale** (the active focus / carrier)
- **mission annexe** (the optional parallel task / submission / overlay)

Back-end/internal terms (carrier mission, submission, overlay task) are
unchanged — only the user-facing French labels are fixed to principale/annexe.

### 7.1 Standard view (no carrier active)

```text
Imperium dashboard, mission active:

  ┌─────────────────────────────────────┐
  │ MISSION ACTIVE                      │
  │ Workout — Push day                  │
  │ ▶ En cours depuis 18:00             │
  │ Durée: ~45 min                      │
  │                                     │
  │ [Fait]  [Pas fait]                  │
  └─────────────────────────────────────┘

No submissions shown — this isn't a carrier mission.
```

### 7.2 Carrier view (submissions displayed)

```text
Imperium dashboard, carrier mission active:

  ┌─────────────────────────────────────────────┐
  │ MISSION ACTIVE: Session VTC                 │
  │ ▶ En cours depuis 09:00                     │
  │ Objectif: 350€                              │
  │                                             │
  │ [Fait]  [Pas fait]                          │
  │                                             │
  │ ┌─ SUBMISSIONS DISPONIBLES ───────────────┐ │
  │ │ 📞 Appeler cousin Yacine        ✓  ✗   │ │
  │ │ ✉️  Email à Marie                ✓  ✗   │ │
  │ │ 🔎 Vérifier prix garage X       ✓  ✗   │ │
  │ │ 📋 Confirmer RDV dentiste       ✓  ✗   │ │
  │ └─────────────────────────────────────────┘ │
  └─────────────────────────────────────────────┘
```

### 7.3 The two buttons per submission

```text
✓  "FAIT"
   When tapped:
   - Submission's mission status → 'faite'
   - Logged: completed_via_submission = TRUE
   - Logged: carrier_mission_id = current carrier
   - User feels good about saving time
   - No impact on carrier mission status

✗  "PAS SA PLACE ICI"  
   When tapped:
   - Modal opens:
     "Cette tâche ne devrait pas être ici, pourquoi?"
     ⚪ Pas dans la liste superposable
     ⚪ Demande trop de focus
     ⚪ Autre raison [chat]
     [Confirmer]
   - Submission removed from this carrier
   - Pattern stored:
     * If "Pas dans la liste": this specific mission marked
       as is_overlay_eligible = FALSE
     * If "Trop de focus": signal to refine the carrier rules
     * If "Autre": user explains in chat, Qwen analyzes
   - Stored in pgvector for future learning
```

---

## 8. What Happens When User Doesn't Act

```text
User sees submissions, doesn't tap any of them.
That's totally fine.

OUTCOMES:
- User finishes the carrier mission normally
- Submissions remain in the backlog (still active)
- Their priority in the backlog is unchanged
- They MAY appear in the next carrier mission
- They MAY become standalone missions later if their 
  priority rises (deadline approaches, etc.)

NO PUNITIVE IMPACT:
- discipline_score unchanged
- WR doesn't reproach the user
- "You could have called Yacine during VTC" is NEVER said
- The user simply didn't have time/will: that's life
```

---

## 9. Selection of Submissions to Display

When a carrier mission becomes active, the system selects which submissions to show.

### 9.1 Selection criteria

```text
1. Status = 'active' (not yet completed/failed/cancelled)
2. is_overlay_eligible = TRUE
3. final_score (per doc 52) is NOT in priority 9 or 10
   (high-priority missions deserve their own time slot)
4. Estimated duration ≤ 15 min
5. Not currently in another active carrier (avoid duplicates)
6. Not previously rejected by user with "Pas sa place ici"
```

### 9.2 Ordering

```text
Display top N submissions, ordered by:
  1. Final score (highest first)
  2. Tie-breaker: deadline proximity
  3. Tie-breaker: oldest in backlog

N = 5 by default (configurable in user settings)

If more than N exist: only the top N are shown.
The others wait their turn in subsequent carriers.
```

### 9.3 No real-time refresh

```text
Submissions are computed when the carrier becomes active.
They don't refresh during the carrier (unless user 
explicitly refreshes via "Actualiser" gesture).

Why: avoiding distraction from the carrier mission itself.
The user shouldn't be notified that "a new submission appeared"
while driving.
```

---

## 10. AI Tasks Touched

```text
imperium.mission.classify_carrier   - Qwen, on mission creation
imperium.mission.classify_overlay   - Qwen, on mission creation
imperium.submission.analyze_refusal - Qwen, when user taps ✗
imperium.submission.list_for_carrier - deterministic SQL query
```

All AI calls are local (Qwen). Zero cloud cost for this feature.

---

## 11. Database Schema

### 11.1 Extensions to imperium_missions

```sql
ALTER TABLE imperium_missions
ADD COLUMN IF NOT EXISTS is_carrier_mission BOOLEAN NOT NULL DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS is_overlay_eligible BOOLEAN NOT NULL DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS overlay_category VARCHAR(64) NULL;

CREATE INDEX imperium_missions_overlay_eligible_idx
ON imperium_missions (user_id, is_overlay_eligible, status)
WHERE is_overlay_eligible = TRUE AND status = 'active';

CREATE INDEX imperium_missions_carrier_idx
ON imperium_missions (user_id, is_carrier_mission, status)
WHERE is_carrier_mission = TRUE;
```

### 11.2 Submission completion tracking

```sql
CREATE TABLE imperium_submission_completions (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id              UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  submission_mission_id UUID NOT NULL REFERENCES imperium_missions(id),
  carrier_mission_id   UUID NOT NULL REFERENCES imperium_missions(id),
  completed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  carrier_mission_progress INTEGER NULL  -- 0-100% of carrier when done
);

CREATE INDEX imperium_submission_completions_user_idx
ON imperium_submission_completions (user_id, completed_at DESC);
```

### 11.3 User rejection tracking (for learning)

```sql
CREATE TABLE imperium_submission_rejections (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id              UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  submission_mission_id UUID NOT NULL REFERENCES imperium_missions(id),
  carrier_mission_id   UUID NOT NULL REFERENCES imperium_missions(id),
  rejection_reason     VARCHAR(64),
                       -- 'not_in_overlay_list' | 'requires_focus' | 'other'
  user_explanation     TEXT NULL,
  rejected_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX imperium_submission_rejections_user_idx
ON imperium_submission_rejections (user_id, rejected_at DESC);
```

### 11.4 Overlay categories config

```sql
CREATE TABLE imperium_overlay_categories (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  category_code       VARCHAR(32) UNIQUE NOT NULL,
                      -- 'communication' | 'recherche' | etc.
  category_label      VARCHAR(128) NOT NULL,
  category_emoji      VARCHAR(8) NULL,
  active              BOOLEAN NOT NULL DEFAULT TRUE,
  min_duration_min    INTEGER NOT NULL DEFAULT 3,
  max_duration_min    INTEGER NOT NULL DEFAULT 15,
  description         TEXT NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Initial seed (Section 5):
INSERT INTO imperium_overlay_categories (category_code, category_label, category_emoji, ...) VALUES
  ('communication', 'Communication', '📞', ...),
  ('recherche', 'Recherche', '🔎', ...),
  ('admin_light', 'Administratif léger', '📋', ...),
  ('mental_light', 'Mental léger', '🧠', ...),
  ('social_light', 'Social léger', '📱', ...);
```

---

## 12. The Categorization Flow

When a new mission is created:

```text
Step 1 — Backend creates the mission as usual
  - Computes intrinsic score (per doc 52)
  - Stores in imperium_missions

Step 2 — Carrier classification (deterministic)
  is_carrier_mission = (
    estimated_duration_minutes >= 60
    AND physical_demand_category != 'high'
  )

Step 3 — Overlay classification (Qwen)
  Qwen receives:
    - Mission title
    - Mission description
    - Estimated duration
    - List of overlay categories from imperium_overlay_categories
  
  Qwen outputs:
    {
      "is_overlay_eligible": true|false,
      "category_code": "communication" | null,
      "confidence": 0.85,
      "reasoning": "Short call, no specific physical context required"
    }
  
  Backend stores: 
    is_overlay_eligible, overlay_category

Step 4 — Mission ready for use
  - If is_carrier_mission: will display submissions when active
  - If is_overlay_eligible: will appear in carrier missions
```

### 12.1 Qwen prompt template

```text
You are categorizing a mission for a personal task system.

Determine if this mission is "overlay-eligible" — meaning 
it can be done DURING a longer, low-physical-effort mission 
(like driving a VTC route between clients).

OVERLAY-ELIGIBLE CATEGORIES (a mission must fit one of these):
[list from imperium_overlay_categories]

NEVER OVERLAY-ELIGIBLE:
- Tasks requiring physical equipment (computer, paper, kitchen)
- Tasks requiring focus (studying, complex thought)
- Religious obligations (prayer, dars)
- Vital missions (medical urgency)
- Workouts or physical activity
- Sleep, ghusl
- Tasks longer than 15 minutes

MISSION TO CLASSIFY:
Title: "{title}"
Description: "{description}"
Estimated duration: {duration_minutes} minutes
Mission type: "{mission_type}"

OUTPUT (strict JSON):
{
  "is_overlay_eligible": <true | false>,
  "category_code": <"communication" | "recherche" | "admin_light" | "mental_light" | "social_light" | null>,
  "confidence": <0.0 to 1.0>,
  "reasoning": "<one sentence explanation in French>"
}
```

---

## 13. Settings & Customization

User can adjust submissions behavior in Imperium settings:

```text
Imperium > Settings > Submissions:

  ☑ Activer les submissions (default: TRUE)
  
  Nombre max affichées: [5 ▾]
  
  Catégories actives:
    ☑ 📞 Communication
    ☑ 🔎 Recherche
    ☑ 📋 Administratif léger
    ☐ 🧠 Mental léger  ← user can disable any category
    ☑ 📱 Social léger
  
  Durée minimum mission porteuse: [60 ▾] minutes
  
  [Voir l'historique des submissions]
```

### 13.1 Disable feature entirely

If user disables submissions:
- No submissions panel ever appears
- All missions still get categorized (data still useful)
- Re-enabling restores the feature instantly

---

## 14. WR Integration

The WR (doc 32, doc 47) covers submissions in the Imperium section:

```text
EXAMPLE WR COMMENTARY:

"Cette semaine, tu as complété 12 submissions pendant 
 tes sessions VTC, soit ~3 par jour de travail.

 Catégories les plus actives:
   📞 Communication: 7
   📋 Admin léger: 3
   🔎 Recherche: 2

 4 submissions ont été marquées 'pas sa place ici'.
 Patterns détectés:
   - 'Lire article long' n'est jamais accepté en VTC
     → suggestion: démouvoir mental_light en VTC ?

 Tu sembles préférer les submissions en début de session
 plutôt qu'en fin."
```

The WR helps:
- Surface patterns (which categories work, which don't)
- Tune the system over time
- Validate that the feature serves the user

---

## 15. Edge Cases

### 15.1 Many overlay-eligible missions in backlog

```text
If there are 50 overlay-eligible missions active:
- Only the top N (default 5) shown per carrier
- Rest wait their turn
- Sorted by score, deadline, age
```

### 15.2 Carrier mission ends abruptly

```text
User aborts VTC session.
- Submissions panel disappears
- Their missions remain in backlog unchanged
- Pending submissions can appear in next carrier
```

### 15.3 User does a submission in the middle of a non-carrier moment

```text
User taps "✓ Fait" on a submission while NOT in any carrier.
This shouldn't happen via UI (panel only shown in carriers),
but if user manually navigates to mission view:

- Submission marked done
- carrier_mission_id = NULL in completion record
- Logged as "completed standalone, marked as overlay-eligible"
```

### 15.4 User completes carrier without doing any submission

```text
Normal case. Frequent.
- Carrier mission marked completed
- All submissions remain unchanged
- Next time another carrier becomes active, they may be shown again
```

### 15.5 Overlay category seems off after deployment

```text
Real-world tuning will reveal:
- Some categories never get accepted (remove)
- Some categories should be added (e.g. "Listen to audiobook")

Adjustment process:
- Admin updates imperium_overlay_categories table
- Re-categorization batch job runs (Qwen re-evaluates active missions)
- Changes propagate within minutes
```

---

## 16. Implementation Order (V3)

```text
Phase 1 — Schema migrations
  ├─ Extensions to imperium_missions (3 columns)
  ├─ imperium_submission_completions
  ├─ imperium_submission_rejections
  └─ imperium_overlay_categories (with seed data)

Phase 2 — Backend services
  ├─ services/imperium/mission_categorizer.py
  │   - is_carrier_mission classification (deterministic)
  │   - is_overlay_eligible classification (Qwen call)
  └─ services/imperium/submission_selector.py
      - List submissions for an active carrier
      - Apply ordering and limits

Phase 3 — Qwen prompts
  └─ Add to doc 35:
     - qwen_classify_overlay.txt

Phase 4 — API endpoints
  ├─ GET    /api/v1/imperium/missions/{id}/submissions
  │   (list submissions for an active carrier)
  ├─ POST   /api/v1/imperium/submissions/{id}/complete
  ├─ POST   /api/v1/imperium/submissions/{id}/reject
  │   (with rejection_reason and explanation)
  └─ GET    /api/v1/imperium/submissions/history

Phase 5 — Mission categorization integration
  ├─ Hook into mission creation pipeline
  └─ Background batch for existing missions

Phase 6 — UI in Android
  ├─ Submissions panel in active mission view
  ├─ Tap "✓ Fait" → confirm + animate
  ├─ Tap "✗ Pas sa place ici" → modal + reason
  ├─ Settings: enable/disable, categories
  └─ History view in mission details

Phase 7 — WR integration
  └─ Add submission stats to Imperium WR section
```

---

## 17. Cost Analysis

```text
PER MISSION CREATION:
  Qwen classification: 0€ (local)
  Carrier check: 0€ (deterministic)

PER CARRIER ACTIVATION:
  SQL query for submissions: 0€

PER SUBMISSION COMPLETION:
  DB write: 0€

PER SUBMISSION REJECTION:
  Qwen analysis if "Other" reason: 0€ (local)

ANNUAL COST: 0€
```

---

## 18. Privacy

```text
DATA STORED:
- Mission categorizations (local DB)
- Submission completion records (local DB)
- User rejection reasons (local DB)

NOTHING SENT TO CLOUD AI:
- Qwen runs locally on VPS
- All learning happens internally

USER CONTROL:
- Disable feature anytime
- Disable specific categories
- Clear submission history (Settings)
```

---

## 19. Non-Goals For V3

```text
❌ Auto-detection of "opportune moments" within carrier
   (User decides when to act)

❌ Push notifications for new submissions
   (Display only, no interruption)

❌ Penalizing users for not doing submissions
   (Strictly bonus, never punitive)

❌ Dynamic carrier criteria based on user mood
   (V4: physical_demand_category considers energy)

❌ Suggesting submissions outside of carrier missions
   (V4: maybe small dashboard widget)

❌ Voice-activated submission completion
   (V4)

❌ Automatic submission execution (e.g., AI sends email)
   (Out of scope: user is the actor)
```

---

## 20. V4+ Future Considerations

```text
- Personal learning: per-user category preferences
- Mental focus rule (Rule 3 from Section 6)
- Submission grouping (e.g. "all phone calls together")
- Time-of-day preferences (some submissions in morning)
- Weather/traffic-based dynamic eligibility
- Voice control for hands-free completion
- Auto-detection of micro-pauses in carrier missions
- Integration with Vector overlay during VTC
```

---

## 21. References

- `08_NON_NEGOTIABLE_RULES.md` — backend authority
- `30_AI_ROUTING_AND_SCORING_POLICY.md` — Qwen routing
- `32_WR_INTERACTIVE_WORKFLOW.md` — WR feedback
- `33_VECTOR_LOGIC_DETAIL.md` — VTC carrier context
- `35_QWEN_SETUP_AND_PROMPTS.md` — overlay classification prompt
- `43_IMPERIUM_LOGIC_DETAIL.md` — mission lifecycle
- `44_BRAIN_UNIFIED_LOGIC.md` — unified brain
- `45_USER_OBJECTIVES_FEATURE.md` — V3 family
- `47_WR_GUIDED_SECTIONS.md` — WR submission stats
- `52_AI_DECISION_FRAMEWORK.md` — scoring foundation

---

## 22. Final Note

```text
This feature is OPTIONAL by design.
It serves users who want to optimize their time, but never 
nags those who don't.

The user is the master of their rhythm.
The system is the assistant, not the judge.
A submission ignored is just a submission for tomorrow.
A submission completed is a small win celebrated quietly.
```

---

**Document version:** 1.0
**Status:** V3 design specification (DO NOT IMPLEMENT before V1 + V2)
**Last updated:** 2026-04-29
