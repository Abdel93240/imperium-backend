# 45 - User Objectives Feature (V3)

> ⚠️ **V3 feature — do not implement before V1 and V2 are stable.**
> This document captures the design decisions for future implementation.

---

## 1. Purpose

The User Objectives feature allows the user to declare **personal objectives per application**, which the AI then uses to personalize all future suggestions and decisions in that domain.

Without this feature, the AI gives **generic answers**.
With this feature, the AI gives **personally aligned answers**.

The unified brain (per doc 44) needs to know what the user actually wants in each life domain to deliver real value.

---

## 2. Why V3 And Not Earlier

```text
V1 — Apps must run and collect data first.
     Without baseline data, personalized objectives are guesswork.

V2 — User must experience generic AI suggestions and feel
     their limits. This frustration is what makes objectives
     genuinely valuable.

V3 — User now knows what they want from each app, has data
     to ground the objectives, and has felt the gap.
     The feature lands at the right moment.
```

Implementing this in V1 would force the user to declare objectives **before** they know what they need.

---

## 3. Structure

### 3.1 Five objectives per app, max

```text
Each of the five apps can hold up to 5 user objectives:
  - Imperium
  - Vector
  - The Vault
  - Pulse
  - The Path

Total maximum across the system: 25 objectives.
```

### 3.2 Hierarchy: principal + secondary

```text
Position 1 (mandatory if any objective in this app):
  importance = "principal"
  → Drives the main orientation of all AI calls in this app

Positions 2 to 5 (optional):
  importance = "secondaire"
  → Constraints and bonuses
  → AI considers them when relevant
  → AI never lets them override the principal
```

### 3.3 Why hierarchy matters

```text
Real example (Pulse):
  Position 1 — principal:    "Plier le cardio"
  Position 2 — secondaire:   "Enchaîner 25 tractions"
  Position 3 — secondaire:   "Avoir un dos droit"
  Position 4 — secondaire:   "Plus de testostérone"
  Position 5 — empty

When user asks "Quel workout aujourd'hui ?":
  AI prioritizes cardio (principal) BUT also includes
  tractions when possible (secondary 1), keeps posture
  in mind (secondary 2), and considers food/lifestyle
  choices that support testosterone (secondary 3).

Without hierarchy:
  AI doesn't know what to do when objectives compete.
  Result: random selection or generic compromise.

With hierarchy:
  AI has a clear arbitration rule.
  Result: coherent, personalized advice.
```

### 3.4 Minimum: at least one objective per app

```text
The user is NOT required to fill all 5 slots in every app.

But the user IS required to have at least 1 validated
objective in each of the 5 apps.

If the user has not yet defined at least one objective for
any app, Imperium auto-creates a missions to do so.
See Section 5.
```

---

## 4. The Settings UI Flow

```text
USER PATH:
Imperium → Settings → Objectifs

DISPLAY:
  Five collapsible sections, one per app.
  Each section shows the 5 slots:

  ┌─────────────────────────────────────────┐
  │ PULSE — santé et activité physique      │
  │                                         │
  │ ① Principal     [_______________]  ⚪   │
  │ ② Secondaire    [_______________]  ⚪   │
  │ ③ Secondaire    [_______________]  ⚪   │
  │ ④ Secondaire    [_______________]  ⚪   │
  │ ⑤ Secondaire    [_______________]  ⚪   │
  │                                         │
  └─────────────────────────────────────────┘

  Same structure for Vault, Path, Vector, Imperium.

ACTION:
  Single button at the bottom: "Enregistrer les préférences"
  
  When tapped:
    → backend validates each filled slot in sequence
    → shows colored indicators per slot
    → on full success: persists and triggers prompt generation
```

### 4.1 Validation feedback under each slot

```text
After "Enregistrer les préférences":

Slot validated → green dot ✅
  No message shown.

Slot rejected — wrong app → red dot ❌
  Red text below the slot:
  "Cet objectif appartient plutôt à [suggested app].
   Veuillez le déplacer ou le reformuler."

Slot rejected — unclear → red dot ❌
  Red text below the slot:
  "Pas compris. Pourrais-tu reformuler ?"

Slot has cohrence warning → orange dot ⚠️ (non-blocking)
  Orange text below the slot:
  "Attention: cet objectif semble en tension avec ton 
   objectif principal '[principal text]'. Confirmer quand
   même ?" 
   [Yes, save anyway] [Edit]
```

The user keeps full control. Cohérence warnings never block.

---

## 5. Auto-Mission If An App Has No Objective

When the user opens the system the first day after the feature is enabled:

```text
For each app where user has 0 validated objectives:
  → Imperium creates a mission:
    
    Title: "Définir au moins un objectif pour [App name]"
    type: very_important
    source: ai_planner
    deadline: 7 days
    description: 
      "Le système est moitié configuré sans objectif pour [app].
       Une minute en Settings > Objectifs."
```

Why these missions matter:

```text
Without objectives in an app, the AI in that app gives
generic suggestions. Half-configured systems frustrate users.

These missions push the user to complete the configuration
without nagging or aggressive notifications.
```

If the user explicitly says "I don't want objectives in Vault",
they can opt out:

```text
In Settings > Objectifs > Vault:
  [☑ Skip this app — no objectives needed]
  
This removes the auto-mission and the AI uses generic mode for that app.
```

---

## 6. The Three-Level Validation By Qwen

```text
LEVEL 1 — APP MATCH (per slot, blocking)
  Qwen analyzes:
    Does this objective belong in this app?
    
  Examples:
    Slot in Pulse: "Économiser pour acheter une moto"
    → REJECT: belongs in Vault
    
    Slot in Path: "Faire 25 tractions"
    → REJECT: belongs in Pulse
    
    Slot in Vault: "Mettre 200€ de côté chaque semaine"
    → ACCEPT: correct app

LEVEL 2 — CLARITY (per slot, blocking)
  Qwen analyzes:
    Is the objective clear enough to derive a strategy?
    
  Examples:
    "Truc bidule"
    → REJECT: incomprehensible
    
    "Mieux"
    → REJECT: too vague
    
    "Augmenter ma masse musculaire de 5 kg en 6 mois"
    → ACCEPT: specific and actionable

LEVEL 3 — COHERENCE (per app, non-blocking)
  Qwen analyzes:
    Do the slots in this app contradict each other?
  
  Examples:
    Pulse:
      1. "Perdre 10 kg"
      2. "Prendre 5 kg de muscle"
    → WARNING: tension (recomposition is possible but rare)
    
    Vault:
      1. "Mettre 50% de mes revenus de côté"
      2. "Voyager 3 fois par an"
    → WARNING: tension depending on income
  
  User can save anyway.
```

---

## 7. Meta-Prompt Generation By Opus 4.7

Once all user objectives in an app are validated (Levels 1 + 2 passed; Level 3 acknowledged or absent), Opus 4.7 generates a meta-prompt that will be injected into all future AI calls in that app.

### 7.1 Why Opus and not Qwen

```text
THE PROMPT WILL BE READ 1000+ TIMES:
  - Each AI call in this app injects it
  - Workout planning: 200 calls/year
  - Meal suggestion: 1000 calls/year  
  - Total over 3 years: 5000+ uses

THE PROMPT IS GENERATED ONCE:
  - User defines objectives
  - Opus generates the meta-prompt
  - Stored in DB
  - Reused without regeneration

ECONOMICS:
  - Pay $0.10 once for top-quality meta-prompt
  - Versus risk: 5000 mediocre AI responses
  - Total cost lifetime: ~$2.50 max for 25 objectives
  - Negligible for the value
```

### 7.2 Opus prompt template

```text
You are generating a meta-prompt for a personal AI ecosystem.

TARGET APP: {app_name}
APP PURPOSE: {app_purpose_short}

USER OBJECTIVES (in priority order):
1. PRINCIPAL: {position_1_text}
2. SECONDARY: {position_2_text}
3. SECONDARY: {position_3_text}
4. SECONDARY: {position_4_text}
5. SECONDARY: {position_5_text}

USER PROFILE CONTEXT:
{anonymized_profile_summary}

YOUR TASK:
Produce a meta-prompt that will be INJECTED into every future AI call
in this app. The meta-prompt must:

1. Establish a clear strategic orientation aligned with the principal.
2. Treat secondary objectives as constraints/bonuses, not as competing goals.
3. Specify HOW the AI should arbitrate when objectives conflict.
4. Stay concise (200-400 words) to avoid token bloat in every call.
5. Use direct, no-flattery tone (the user explicitly rejects soft coaching).
6. End with a "REMINDER" section listing the 5 objectives verbatim.

OUTPUT FORMAT (strict):
{
  "meta_prompt_text": "<the full meta-prompt in French>",
  "summary": "<one sentence summarizing the orientation>",
  "arbitration_rule": "<how AI should choose when objectives conflict>",
  "warnings": ["<any concerns about the objectives>"]
}

Output strict JSON only.
```

### 7.3 Storage

```text
The generated prompt is stored in user_objective_prompts.
It carries a reference to the source objectives.
On any change, it is regenerated and the old version is marked superseded.
```

---

## 8. How The Meta-Prompt Is Used At Runtime

When any AI call happens in app X for user U:

```text
1. Backend retrieves the active meta-prompt for (user U, app X):
   SELECT generated_prompt FROM user_objective_prompts
   WHERE user_id = U AND app_target = X
   AND superseded_at IS NULL
   LIMIT 1

2. If found:
   final_prompt = base_prompt 
                + "\n\n--- USER OBJECTIVES CONTEXT ---\n"
                + meta_prompt_text
                + "\n\n--- TASK ---\n"
                + current_task_specific_prompt

3. If not found (app has no objectives):
   final_prompt = base_prompt + current_task_specific_prompt
   (generic mode)

4. Send to chosen model (Qwen / Sonnet / Opus per scoring).
```

The meta-prompt adds ~50-100 tokens per call. Negligible cost overhead.

---

## 9. Modifying An Existing Objective

When the user edits any slot in any app:

```text
1. Re-validation Qwen on the edited slot only (Levels 1 + 2)
2. Re-cohérence check on the entire app's slots (Level 3)
3. If validation passes:
   ├─ Mark old user_objectives rows for this app as superseded
   ├─ Insert new user_objectives rows (full set of slots)
   ├─ Mark old user_objective_prompts row as superseded
   ├─ Trigger Opus to regenerate the meta-prompt
   └─ New meta-prompt becomes active immediately

4. Cost per modification: ~$0.10 (Opus regeneration)
```

### 9.1 Why regenerate the entire prompt

```text
Changing one secondary objective shifts the arbitration logic.
Trying to update the meta-prompt partially:
  - Risk inconsistencies
  - Risk obsolete instructions
  - Complex code

Regenerating fully:
  - Always coherent
  - Simple code
  - Negligible cost ($0.10)
```

---

## 10. Cost Analysis

```text
INITIAL SETUP (lifetime, one-shot per objective):
  Maximum 25 objectives × Opus generation = ~$2.50
  Realistic (15 objectives) = ~$1.50

ONGOING USAGE:
  Meta-prompt injected in every call
  +50-100 tokens per call
  Marginal cost vs without objectives: <$2/year

MODIFICATIONS:
  Changing objectives = regenerating meta-prompt
  ~$0.10 per change × N changes/year = trivial

VALIDATION:
  Qwen local validation = $0

TOTAL COST OVER 3 YEARS:
  ~$10 — completely negligible.
  
VALUE:
  Every AI suggestion in every app aligned with user's
  actual goals.
  ROI: massive.
```

---

## 11. Database Schema

### 11.1 user_objectives — the raw user-entered objectives

```sql
CREATE TABLE user_objectives (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  app_target        VARCHAR(32) NOT NULL,
                    -- 'imperium' | 'vector' | 'vault' | 'pulse' | 'path'
  position          INTEGER NOT NULL,
                    -- 1 to 5
  importance        VARCHAR(16) NOT NULL,
                    -- 'principal' (position=1) | 'secondaire' (position 2-5)
  objective_text    TEXT NOT NULL,
  status            VARCHAR(32) NOT NULL DEFAULT 'pending',
                    -- 'pending' | 'validated' | 'rejected_wrong_app' 
                    -- | 'rejected_unclear' | 'coherence_warning'
  validation_reason TEXT NULL,
  suggested_app     VARCHAR(32) NULL,
                    -- when rejected_wrong_app, suggests which app fits
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  superseded_at     TIMESTAMPTZ NULL,
  
  CHECK (position BETWEEN 1 AND 5),
  CHECK (
    (position = 1 AND importance = 'principal') OR
    (position > 1 AND importance = 'secondaire')
  )
);

-- One active objective per (user, app, position)
CREATE UNIQUE INDEX user_objectives_active_unique_idx
ON user_objectives (user_id, app_target, position)
WHERE superseded_at IS NULL;

-- Quick lookup of active objectives per app
CREATE INDEX user_objectives_active_idx
ON user_objectives (user_id, app_target)
WHERE status = 'validated' AND superseded_at IS NULL;
```

### 11.2 user_objective_prompts — Opus-generated meta-prompts

```sql
CREATE TABLE user_objective_prompts (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  app_target               VARCHAR(32) NOT NULL,
  meta_prompt_text         TEXT NOT NULL,
  summary                  TEXT NULL,
  arbitration_rule         TEXT NULL,
  source_objective_ids     UUID[] NOT NULL,
                           -- references to user_objectives.id
  prompt_model             VARCHAR(32) NOT NULL DEFAULT 'opus-4.7',
  generated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  superseded_at            TIMESTAMPTZ NULL,
  estimated_cost_eur       NUMERIC(6,4) NULL
);

-- One active meta-prompt per (user, app)
CREATE UNIQUE INDEX user_objective_prompts_active_unique_idx
ON user_objective_prompts (user_id, app_target)
WHERE superseded_at IS NULL;
```

### 11.3 Optional events

```sql
-- For audit trail and pgvector ingestion
CREATE TABLE user_objective_events (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  event_type      VARCHAR(64) NOT NULL,
                  -- 'objective.created' | 'objective.validated' 
                  -- | 'objective.rejected' | 'objective.modified'
                  -- | 'meta_prompt.generated' | 'meta_prompt.superseded'
  app_target      VARCHAR(32) NOT NULL,
  payload         JSONB NOT NULL,
  occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 12. AI Task Types

```text
imperium.user_objective.validate     - Qwen, Levels 1 + 2 + 3
imperium.user_objective.generate_prompt - Opus, meta-prompt creation
imperium.user_objective.regenerate_prompt - Opus, after edit
```

---

## 13. Routing Decisions Per Task

```text
imperium.user_objective.validate          → Qwen local (low complexity)
imperium.user_objective.generate_prompt   → Opus 4.7 (static override)
imperium.user_objective.regenerate_prompt → Opus 4.7 (static override)
```

The "Opus static override" applies because:
- One-shot per objective (rare)
- Critical quality (5000+ future calls depend on it)
- Cost is trivial vs value

---

## 14. Reads & Events via Common Memory

### 14.1 Imperium

The backend emits the event user_objective.app_empty; Imperium READS it and
creates the mission.
```text
- user_objective.app_empty (when an app has no validated objectives)
  → Imperium auto-creates "Define at least one objective for [app]" mission
```

### 14.2 All apps (Vector, Vault, Pulse, Path)

Each AI call within an app:
```text
1. Backend service queries user_objective_prompts for active prompt
2. If exists: injects meta_prompt_text into the AI call
3. If absent: AI runs in generic mode
```

### 14.3 With WR (doc 32) and WRS (doc 39)

```text
When validated user objectives exist, the WR analysis includes:
  "Cette semaine, alignement avec ton objectif Pulse principal
   ('Plier le cardio'): X% des workouts étaient cardio."

When objectives change, the next WR comments:
  "Tu as redéfini ton objectif Pulse principal il y a 3 jours.
   Cette semaine reflète cet ajustement."

WRS (Vector learning loop) factors in objective alignment:
  "Vector recommended X% of rides aligned with your VTC objective."
```

### 14.4 With pgvector (doc 38)

```text
Active objectives may be embedded in pgvector with:
  source: 'user_objective'
  weight: 1.0 (no decay while active)
  status: marked 'expired' on supersession

Useful for: providing context when AI reasons across multiple domains.
```

---

## 15. UI Flows In Detail

### 15.1 First-time setup

```text
User opens Settings > Objectifs (first time)
→ Greeting screen:
  "Pour t'aider efficacement dans chaque domaine de ta vie,
   définissons ensemble ce que tu veux vraiment.
   Tu peux mettre 1 à 5 objectifs par application."
  [Commencer]

→ Sequential walkthrough:
  Pulse first → Vault → Path → Vector → Imperium
  
  Each step shows the 5 slots, user fills as many as desired.
  Single "Enregistrer les préférences" button at the very end.
```

### 15.2 Edit flow (later)

```text
User opens Settings > Objectifs (after initial setup)
→ Tabs at top: Pulse | Vault | Path | Vector | Imperium
→ Each tab shows current objectives + "Modifier" buttons
→ Modifying a slot triggers re-validation + regeneration
```

### 15.3 Mid-app suggestion flow

When user is using an app, the AI's suggestions naturally reflect their objectives. No special UI; the difference is in the quality and personalization of every AI response.

If the user wants to see why the AI made a specific suggestion:
```text
[Pourquoi cette suggestion ?]
  → modal: "Cette suggestion s'aligne avec tes objectifs:
              Principal — Plier le cardio
              Secondaire — Avoir un dos droit"
```

---

## 16. Failure Modes And Recovery

### 16.1 Opus unreachable during prompt generation

```text
Qwen validation succeeded but Opus fails:
  → User objectives saved with status = 'pending_prompt'
  → User notified: "Objectifs sauvegardés. Génération du
                    profil personnalisé en cours..."
  → Background retry every 30 minutes for 24 hours
  → On success: user notified "Profil prêt"
```

### 16.2 User wants to delete all objectives in an app

```text
Settings > Objectifs > [App name] > [Tout supprimer]
  → Confirmation modal
  → On confirm: 
    - all user_objectives for this (user, app) marked superseded
    - user_objective_prompts marked superseded
    - app reverts to generic mode
    - if user previously had skip flag, it's preserved
    - else: new auto-mission created to redefine
```

### 16.3 Inconsistent objectives causing AI confusion

```text
If WR analysis (doc 32) detects that AI suggestions in an app
seem confused or contradictory, it may flag:
  "Tu as 4 objectifs dans Pulse qui semblent en tension. 
   Voulez-vous les revoir ?"

Surfacing the issue, never auto-modifying.
```

---

## 17. Implementation Order (V3)

```text
PHASE 1 — Schema migrations
  ├─ user_objectives table
  ├─ user_objective_prompts table
  └─ user_objective_events table

PHASE 2 — Backend services
  ├─ services/imperium/user_objectives.py
  │  - create, validate, list, supersede
  ├─ services/imperium/objective_prompt_generator.py
  │  - Opus call, prompt assembly
  └─ services/imperium/objective_prompt_injector.py
     - middleware that injects meta-prompt into AI calls

PHASE 3 — API endpoints
  ├─ POST /api/v1/imperium/objectives        (save batch)
  ├─ GET  /api/v1/imperium/objectives        (list current)
  ├─ PATCH /api/v1/imperium/objectives/:id   (edit one)
  ├─ DELETE /api/v1/imperium/objectives/:id  (remove one)
  └─ POST /api/v1/imperium/objectives/regenerate  (force regen)

PHASE 4 — n8n workflow
  └─ user_objective_processing.json
     (Qwen validation → Opus generation → backend storage)

PHASE 5 — Imperium subscription logic
  └─ Auto-mission creator when app has 0 objectives

PHASE 6 — UI in Android app
  ├─ Settings > Objectifs screen
  ├─ Sequential walkthrough first-time
  ├─ Tabs for editing later
  └─ Validation feedback (green/red/orange dots)

PHASE 7 — Integration in all AI calls
  └─ Modify existing AI services to inject meta-prompt
     when active

PHASE 8 — WR + WRS integration
  └─ Surface objective alignment in weekly analysis
```

---

## 18. Non-Goals For V3

```text
❌ Auto-suggest objectives based on user behavior
   (V4: too risky early — user must own their objectives)

❌ Time-bound objectives (deadlines, expirations)
   (V4: complicates the model, not needed initially)

❌ Sub-objectives or nested goals
   (Out of scope: 5 flat objectives is enough)

❌ Sharing objectives between users
   (System is mono-user)

❌ AI generating objectives FOR the user
   (Defeats the purpose: user must want them)

❌ Linking objectives across apps
   (Each app has its own objectives; coherence
    is the user's responsibility)
```

---

## 19. Future V4+ Considerations

```text
- Time-bound objectives (3 months, 1 year, etc.)
- Progress tracking against objectives
- Auto-celebration when an objective is achieved
- AI-suggested refinements based on observed patterns
- Inter-app coherence checks (cross-domain conflicts)
```

These are for later. V3 focuses on the foundational mechanism.

---

## 20. References

- `30_AI_ROUTING_AND_SCORING_POLICY.md` — Opus static override
- `31_AI_TASKS_AND_RESULTS_CONTRACT.md` — task types, contracts
- `36_PROMPTS_CLOUD_AI.md` — Opus prompt template (will be added when implemented)
- `38_VECTORIZATION_PIPELINE.md` — pgvector integration potential
- `40_PULSE_LOGIC_DETAIL.md` — example of meta-prompt usage
- `41_PATH_LOGIC_DETAIL.md` — same
- `42_VAULT_LOGIC_DETAIL.md` — same
- `43_IMPERIUM_LOGIC_DETAIL.md` — auto-mission generator
- `44_BRAIN_UNIFIED_LOGIC.md` — unified brain context

---

**Document version:** 1.0
**Status:** V3 design specification (DO NOT IMPLEMENT in V1 or V2)
**Last updated:** 2026-04-29
