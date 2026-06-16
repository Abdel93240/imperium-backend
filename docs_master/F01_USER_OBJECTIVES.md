# F01 - User Projects Feature (V3)

> ⚠️ **V3 feature — do not implement before V1 and V2 are stable.**
> This document captures the design decisions for future implementation.

---

## 1. Purpose

The User Projects feature allows the user to declare **personal projects per
domain/category**, which the AI then uses to personalize all future suggestions
and decisions in that domain.

Without this feature, the AI gives **generic answers**.
With this feature, the AI gives **personally aligned answers**.

The unified brain (per doc 44) needs to know what the user actually wants in each life domain to deliver real value.

---

## 2. Why V3 And Not Earlier

```text
V1 — Apps must run and collect data first.
     Without baseline data, personalized projects are guesswork.

V2 — User must experience generic AI suggestions and feel
     their limits. This frustration is what makes projects
     genuinely valuable.

V3 — User now knows what they want from each domain, has data
     to ground the projects, and has felt the gap.
     The feature lands at the right moment.
```

Implementing this in V1 would force the user to declare projects **before** they know what they need.

---

## 3. Structure

### 3.1 Five projects per domain/category, max

```text
Each of the five domains/categories can hold up to 5 user projects:
  - Imperium
  - Vector
  - The Vault
  - Pulse
  - The Path

Total maximum across the system: 25 projects.
```

### 3.2 Hierarchy: principal + secondary

```text
Position 1 (mandatory if any project in this domain/category):
  importance = "principal"
  → Drives the main orientation of all AI calls in this domain

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
  AI doesn't know what to do when projects compete.
  Result: random selection or generic compromise.

With hierarchy:
  AI has a clear arbitration rule.
  Result: coherent, personalized advice.
```

### 3.4 Minimum: at least one project per domain/category

```text
The user is NOT required to fill all 5 slots in every domain/category.

But the user IS required to have at least 1 validated
project in each of the 5 domains/categories.

If the user has not yet defined at least one project for
any domain/category, Imperium auto-creates a mission to do so.
See Section 5.
```

---

## 4. The Settings UI Flow

```text
USER PATH:
Imperium → Settings → Projets

DISPLAY:
  Five collapsible sections, one per domain/category.
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

Slot rejected — wrong domain/category → red dot ❌
  Red text below the slot:
  "Ce projet appartient plutôt à [suggested domain].
   Veuillez le déplacer ou le reformuler."

Slot rejected — unclear → red dot ❌
  Red text below the slot:
  "Pas compris. Pourrais-tu reformuler ?"

Slot has coherence warning → orange dot ⚠️ (non-blocking)
  Orange text below the slot:
  "Attention: ce projet semble en tension avec ton
   projet principal '[principal text]'. Confirmer quand
   même ?" 
   [Yes, save anyway] [Edit]
```

The user keeps full control. Cohérence warnings never block.

---

## 5. Auto-Mission If A Domain Has No Project

When the user opens the system the first day after the feature is enabled:

```text
For each domain/category where user has 0 validated projects:
  → Imperium creates a mission:
    
    Title: "Définir au moins un projet pour [Domain name]"
    type: very_important
    source: ai_planner
    deadline: 7 days
    description: 
      "Le système est moitié configuré sans projet pour [domain].
       Une minute en Settings > Projets."
```

Why these missions matter:

```text
Without projects in a domain/category, the AI in that domain gives
generic suggestions. Half-configured systems frustrate users.

These missions push the user to complete the configuration
without nagging or aggressive notifications.
```

If the user explicitly says "I don't want projects in Vault",
they can opt out:

```text
In Settings > Projets > Vault:
  [☑ Skip this domain — no projects needed]
  
This removes the auto-mission and the AI uses generic mode for that domain.
```

---

## 6. The Three-Level Validation By Qwen

```text
LEVEL 1 — DOMAIN MATCH (per slot, blocking)
  Qwen analyzes:
    Does this project belong in this domain/category?
    
  Examples:
    Slot in Pulse: "Économiser pour acheter une moto"
    → REJECT: belongs in Vault
    
    Slot in Path: "Faire 25 tractions"
    → REJECT: belongs in Pulse
    
    Slot in Vault: "Mettre 200€ de côté chaque semaine"
    → ACCEPT: correct domain

LEVEL 2 — CLARITY (per slot, blocking)
  Qwen analyzes:
    Is the project clear enough to derive a strategy?
    
  Examples:
    "Truc bidule"
    → REJECT: incomprehensible
    
    "Mieux"
    → REJECT: too vague
    
    "Augmenter ma masse musculaire de 5 kg en 6 mois"
    → ACCEPT: specific and actionable

LEVEL 3 — COHERENCE (per domain/category, non-blocking)
  Qwen analyzes:
    Do the slots in this domain/category contradict each other?
  
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

Once all user projects in a domain/category are validated (Levels 1 + 2 passed;
Level 3 acknowledged or absent), Opus 4.7 generates a meta-prompt that will be
injected into all future AI calls in that domain.

### 7.1 Why Opus and not Qwen

```text
THE PROMPT WILL BE READ 1000+ TIMES:
  - Each AI call in this domain injects it
  - Workout planning: 200 calls/year
  - Meal suggestion: 1000 calls/year  
  - Total over 3 years: 5000+ uses

THE PROMPT IS GENERATED ONCE:
  - User defines projects
  - Opus generates the meta-prompt
  - Stored in DB
  - Reused without regeneration

ECONOMICS:
  - Pay $0.10 once for top-quality meta-prompt
  - Versus risk: 5000 mediocre AI responses
  - Total cost lifetime: ~$2.50 max for 25 projects
  - Negligible for the value
```

### 7.2 Opus prompt template

```text
You are generating a meta-prompt for a personal AI ecosystem.

TARGET DOMAIN: {domain_name}
DOMAIN PURPOSE: {domain_purpose_short}

USER PROJECTS (in priority order):
1. PRINCIPAL: {position_1_text}
2. SECONDARY: {position_2_text}
3. SECONDARY: {position_3_text}
4. SECONDARY: {position_4_text}
5. SECONDARY: {position_5_text}

USER PROFILE CONTEXT:
{anonymized_profile_summary}

YOUR TASK:
Produce a meta-prompt that will be INJECTED into every future AI call
in this domain. The meta-prompt must:

1. Establish a clear strategic orientation aligned with the principal.
2. Treat secondary projects as constraints/bonuses, not as competing goals.
3. Specify HOW the AI should arbitrate when projects conflict.
4. Stay concise (200-400 words) to avoid token bloat in every call.
5. Use direct, no-flattery tone (the user explicitly rejects soft coaching).
6. End with a "REMINDER" section listing the 5 projects verbatim.

OUTPUT FORMAT (strict):
{
  "meta_prompt_text": "<the full meta-prompt in French>",
  "summary": "<one sentence summarizing the orientation>",
  "arbitration_rule": "<how AI should choose when projects conflict>",
  "warnings": ["<any concerns about the projects>"]
}

Output strict JSON only.
```

### 7.3 Storage

```text
The generated prompt is stored in user_project_prompts.
It carries a reference to the source projects.
On any change, it is regenerated and the old version is marked superseded.
```

---

## 8. How The Meta-Prompt Is Used At Runtime

When any AI call happens in domain X for user U:

```text
1. Backend retrieves the active meta-prompt for (user U, domain X):
   SELECT generated_prompt FROM user_project_prompts
   WHERE user_id = U AND domain_target = X
   AND superseded_at IS NULL
   LIMIT 1

2. If found:
   final_prompt = base_prompt 
                + "\n\n--- USER PROJECTS CONTEXT ---\n"
                + meta_prompt_text
                + "\n\n--- TASK ---\n"
                + current_task_specific_prompt

3. If not found (domain has no projects):
   final_prompt = base_prompt + current_task_specific_prompt
   (generic mode)

4. Send to chosen model (Qwen / Sonnet / Opus per scoring).
```

The meta-prompt adds ~50-100 tokens per call. Negligible cost overhead.

---

## 9. Modifying An Existing Project

When the user edits any slot in any domain/category:

```text
1. Re-validation Qwen on the edited slot only (Levels 1 + 2)
2. Re-cohérence check on the entire domain/category's slots (Level 3)
3. If validation passes:
   ├─ Mark old user_projects rows for this domain/category as superseded
   ├─ Insert new user_projects rows (full set of slots)
   ├─ Mark old user_project_prompts row as superseded
   ├─ Trigger Opus to regenerate the meta-prompt
   └─ New meta-prompt becomes active immediately

4. Cost per modification: ~$0.10 (Opus regeneration)
```

### 9.1 Why regenerate the entire prompt

```text
Changing one secondary project shifts the arbitration logic.
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
INITIAL SETUP (lifetime, one-shot per project):
  Maximum 25 projects × Opus generation = ~$2.50
  Realistic (15 projects) = ~$1.50

ONGOING USAGE:
  Meta-prompt injected in every call
  +50-100 tokens per call
  Marginal cost vs without projects: <$2/year

MODIFICATIONS:
  Changing projects = regenerating meta-prompt
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

### 11.1 user_projects — the raw user-entered projects

```sql
CREATE TABLE user_projects (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  domain_target     VARCHAR(32) NOT NULL,
                    -- 'imperium' | 'vector' | 'vault' | 'pulse' | 'path'
  position          INTEGER NOT NULL,
                    -- 1 to 5
  importance        VARCHAR(16) NOT NULL,
                    -- 'principal' (position=1) | 'secondaire' (position 2-5)
  project_text      TEXT NOT NULL,
  status            VARCHAR(32) NOT NULL DEFAULT 'pending',
                    -- 'pending' | 'validated' | 'rejected_wrong_domain'
                    -- | 'rejected_unclear' | 'coherence_warning'
  validation_reason TEXT NULL,
  suggested_domain  VARCHAR(32) NULL,
                    -- when rejected_wrong_domain, suggests which domain fits
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  superseded_at     TIMESTAMPTZ NULL,
  
  CHECK (position BETWEEN 1 AND 5),
  CHECK (
    (position = 1 AND importance = 'principal') OR
    (position > 1 AND importance = 'secondaire')
  )
);

-- One active project per (user, domain, position)
CREATE UNIQUE INDEX user_projects_active_unique_idx
ON user_projects (user_id, domain_target, position)
WHERE superseded_at IS NULL;

-- Quick lookup of active projects per domain
CREATE INDEX user_projects_active_idx
ON user_projects (user_id, domain_target)
WHERE status = 'validated' AND superseded_at IS NULL;
```

### 11.2 user_project_prompts — Opus-generated meta-prompts

```sql
CREATE TABLE user_project_prompts (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  domain_target            VARCHAR(32) NOT NULL,
  meta_prompt_text         TEXT NOT NULL,
  summary                  TEXT NULL,
  arbitration_rule         TEXT NULL,
  source_project_ids       UUID[] NOT NULL,
                           -- references to user_projects.id
  prompt_model             VARCHAR(32) NOT NULL DEFAULT 'opus-4.7',
  generated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  superseded_at            TIMESTAMPTZ NULL,
  estimated_cost_eur       NUMERIC(6,4) NULL
);

-- One active meta-prompt per (user, domain)
CREATE UNIQUE INDEX user_project_prompts_active_unique_idx
ON user_project_prompts (user_id, domain_target)
WHERE superseded_at IS NULL;
```

### 11.3 Optional events

```sql
-- For audit trail and pgvector ingestion
CREATE TABLE user_project_events (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  event_type      VARCHAR(64) NOT NULL,
                  -- 'project.created' | 'project.validated' 
                  -- | 'project.rejected' | 'project.modified'
                  -- | 'meta_prompt.generated' | 'meta_prompt.superseded'
  domain_target   VARCHAR(32) NOT NULL,
  payload         JSONB NOT NULL,
  occurred_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 12. AI Task Types

```text
imperium.user_project.validate     - Qwen, Levels 1 + 2 + 3
imperium.user_project.generate_prompt - Opus, meta-prompt creation
imperium.user_project.regenerate_prompt - Opus, after edit
```

---

## 13. Routing Decisions Per Task

```text
imperium.user_project.validate          → Qwen local (low complexity)
imperium.user_project.generate_prompt   → Opus 4.7 (static override)
imperium.user_project.regenerate_prompt → Opus 4.7 (static override)
```

The "Opus static override" applies because:
- One-shot per project (rare)
- Critical quality (5000+ future calls depend on it)
- Cost is trivial vs value

---

## 14. Reads & Events via Common Memory

### 14.1 Imperium

The backend emits the event user_project.domain_empty; Imperium READS it and
creates the mission.
```text
- user_project.domain_empty (when a domain/category has no validated projects)
  → Imperium auto-creates "Define at least one project for [domain]" mission
```

### 14.2 All domains (Vector, Vault, Pulse, Path)

Each AI call within a domain:
```text
1. Backend service queries user_project_prompts for active prompt
2. If exists: injects meta_prompt_text into the AI call
3. If absent: AI runs in generic mode
```

### 14.3 With WR (doc 32) and WRS (doc 39)

```text
When validated user projects exist, the WR analysis includes:
  "Cette semaine, alignement avec ton projet Pulse principal
   ('Plier le cardio'): X% des workouts étaient cardio."

When projects change, the next WR comments:
  "Tu as redéfini ton projet Pulse principal il y a 3 jours.
   Cette semaine reflète cet ajustement."

WRS (Vector learning loop) factors in project alignment:
  "Vector recommended X% of rides aligned with your VTC project."
```

### 14.4 With pgvector (doc 38)

```text
Active projects may be embedded in pgvector with:
  source: 'user_project'
  weight: 1.0 (no decay while active)
  status: marked 'expired' on supersession

Useful for: providing context when AI reasons across multiple domains.
```

---

## 15. UI Flows In Detail

### 15.1 First-time setup

```text
User opens Settings > Projets (first time)
→ Greeting screen:
  "Pour t'aider efficacement dans chaque domaine de ta vie,
   définissons ensemble ce que tu veux vraiment.
   Tu peux mettre 1 à 5 projets par domaine."
  [Commencer]

→ Sequential walkthrough:
  Pulse first → Vault → Path → Vector → Imperium
  
  Each step shows the 5 slots, user fills as many as desired.
  Single "Enregistrer les préférences" button at the very end.
```

### 15.2 Edit flow (later)

```text
User opens Settings > Projets (after initial setup)
→ Tabs at top: Pulse | Vault | Path | Vector | Imperium
→ Each tab shows current projects + "Modifier" buttons
→ Modifying a slot triggers re-validation + regeneration
```

### 15.3 Mid-app suggestion flow

When user is using a domain surface, the AI's suggestions naturally reflect their
projects. No special UI; the difference is in the quality and personalization of
every AI response.

If the user wants to see why the AI made a specific suggestion:
```text
[Pourquoi cette suggestion ?]
  → modal: "Cette suggestion s'aligne avec tes projets:
              Principal — Plier le cardio
              Secondaire — Avoir un dos droit"
```

---

## 16. Failure Modes And Recovery

### 16.1 Opus unreachable during prompt generation

```text
Qwen validation succeeded but Opus fails:
  → User projects saved with status = 'pending_prompt'
  → User notified: "Projets sauvegardés. Génération du
                    profil personnalisé en cours..."
  → Background retry every 30 minutes for 24 hours
  → On success: user notified "Profil prêt"
```

### 16.2 User wants to delete all projects in a domain/category

```text
Settings > Projets > [Domain name] > [Tout supprimer]
  → Confirmation modal
  → On confirm: 
    - all user_projects for this (user, domain) marked superseded
    - user_project_prompts marked superseded
    - domain reverts to generic mode
    - if user previously had skip flag, it's preserved
    - else: new auto-mission created to redefine
```

### 16.3 Inconsistent projects causing AI confusion

```text
If WR analysis (doc 32) detects that AI suggestions in a domain
seem confused or contradictory, it may flag:
  "Tu as 4 projets dans Pulse qui semblent en tension. 
   Voulez-vous les revoir ?"

Surfacing the issue, never auto-modifying.
```

---

## 17. Implementation Order (V3)

```text
PHASE 1 — Schema migrations
  ├─ user_projects table
  ├─ user_project_prompts table
  └─ user_project_events table

PHASE 2 — Backend services
  ├─ services/imperium/user_projects.py
  │  - create, validate, list, supersede
  ├─ services/imperium/project_prompt_generator.py
  │  - Opus call, prompt assembly
  └─ services/imperium/project_prompt_injector.py
     - middleware that injects meta-prompt into AI calls

PHASE 3 — API endpoints
  ├─ POST /api/v1/imperium/projects        (save batch)
  ├─ GET  /api/v1/imperium/projects        (list current)
  ├─ PATCH /api/v1/imperium/projects/:id   (edit one)
  ├─ DELETE /api/v1/imperium/projects/:id  (remove one)
  └─ POST /api/v1/imperium/projects/regenerate  (force regen)

PHASE 4 — n8n workflow
  └─ user_project_processing.json
     (Qwen validation → Opus generation → backend storage)

PHASE 5 — Imperium subscription logic
  └─ Auto-mission creator when domain has 0 projects

PHASE 6 — UI in Android app
  ├─ Settings > Projets screen
  ├─ Sequential walkthrough first-time
  ├─ Tabs for editing later
  └─ Validation feedback (green/red/orange dots)

PHASE 7 — Integration in all AI calls
  └─ Modify existing AI services to inject meta-prompt
     when active

PHASE 8 — WR + WRS integration
  └─ Surface project alignment in weekly analysis
```

---

## 18. Non-Goals For V3

```text
❌ Auto-suggest projects based on user behavior
   (V4: too risky early — user must own their projects)

❌ Time-bound projects (deadlines, expirations)
   (V4: complicates the model, not needed initially)

❌ Sub-projects or nested goals
   (Out of scope: 5 flat projects is enough)

❌ Sharing projects between users
   (System is mono-user)

❌ AI generating projects FOR the user
   (Defeats the purpose: user must want them)

❌ Linking projects across domains
   (Each domain has its own projects; coherence
    is the user's responsibility)
```

---

## 19. Future V4+ Considerations

```text
- Time-bound projects (3 months, 1 year, etc.)
- Progress tracking against projects
- Auto-celebration when a project is achieved
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
