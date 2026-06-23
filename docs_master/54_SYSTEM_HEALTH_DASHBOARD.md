# 54 - System Health Dashboard (V3)

> ⚠️ **V3 feature — meta-level system observability.**
> Provides the user with a clear view of their OS's behavior 
> over time, surfaces frictions, and suggests tunings.

---

## 1. Purpose

Give the user a **meta view** of how their OS is behaving:

- Is the discipline trending up or down?
- Are plans being followed or adapted?
- How many replans per day?
- What patterns of friction emerge?
- What tunings could improve things?

Without this view, the system is a black box. The user has no way to know if it's working well, deteriorating, or needs adjustment.

This dashboard is **transparency for the user** about their own OS.

---

## 2. Why This Is V3

```text
V1 — System operational, generating data.
V2 — Refinements applied, more data accumulated.
V3 — Enough history exists to compute meaningful trends 
     and surface real patterns.

Earlier than V3, the data would be too sparse for the 
dashboard to be useful.
```

---

## 3. The Three Layers of System Health

```text
LAYER 1 — DISCIPLINE METRICS
  How well is the user executing their plans?
  Trends over time. Movement direction.

LAYER 2 — PLAN STABILITY
  How often are plans changed mid-stream?
  How many replans? How many adaptations?
  
LAYER 3 — FRICTION DETECTION
  Where do users systematically struggle?
  What missions get rejected? What patterns emerge?
  
LAYER 4 — ACTIONABLE SUGGESTIONS
  Based on layers 1-3, what could be tuned?
  Surface concrete improvements user can make.
```

---

## 4. Where It Lives

```text
Imperium > Settings > Mon OS personnel

Single screen with collapsible sections.
Generated on-demand (not always pre-computed).
Refresh button to recompute on user request.
```

---

## 5. The Dashboard Layout

### 5.1 Top section — Overall health

```text
┌─────────────────────────────────────────────────┐
│ MON OS PERSONNEL                                │
│ État du système (30 derniers jours)             │
│                                                 │
│ ┌───────────────────────────────────────────┐   │
│ │  SANTÉ GLOBALE: 76/100  ↗ +4 vs mois -1   │   │
│ │  ████████████████░░░░░                    │   │
│ └───────────────────────────────────────────┘   │
│                                                 │
│ Mis à jour: 2026-04-29 09:15                    │
│ [Actualiser]                                    │
└─────────────────────────────────────────────────┘
```

The "Health Score" is a composite (Section 6).

### 5.2 Discipline section

```text
┌─────────────────────────────────────────────────┐
│ 📊 DISCIPLINE                                   │
│                                                 │
│ Score moyen:           72%   ↗ +3% (mois -1)    │
│ Meilleur jour:         92%   (lundi 14 avril)   │
│ Pire jour:             45%   (samedi 5 avril)   │
│                                                 │
│ Par type de mission:                            │
│   Religieux:           94% ↗  (excellent)       │
│   Business:            68%    (stable)          │
│   Santé:               55% ↘  (en baisse)       │
│   Finances:            82% ↗  (en hausse)       │
│                                                 │
│ Tendance hebdomadaire (graphique sparkline)     │
│ ▁▃▆█▇▅▆█▆▇▆▆█▇                                  │
└─────────────────────────────────────────────────┘
```

### 5.3 Plan stability section

```text
┌─────────────────────────────────────────────────┐
│ 🔄 STABILITÉ DES PLANS                          │
│                                                 │
│ Plans suivis intacts:    62%                    │
│ Plans adaptés mid-jour:  38%                    │
│ Replans moyens/jour:     1.4   ↘ -0.3           │
│                                                 │
│ Causes de replans (30 jours):                   │
│   Mission ratée:         34%                    │
│   Ghusl required:        22%                    │
│   Smart fuel:            18%                    │
│   Calendar event:        12%                    │
│   User explicit:         8%                     │
│   Autre:                 6%                     │
└─────────────────────────────────────────────────┘
```

### 5.4 Frictions section (most insightful)

```text
┌─────────────────────────────────────────────────┐
│ ⚠️ FRICTIONS DÉTECTÉES                          │
│                                                 │
│ 1. Workouts ratés le mardi (4 fois sur 4)       │
│    Raison principale: "Trop fatigué"            │
│    💡 Déplacer ces workouts ?                   │
│                                                 │
│ 2. Submissions Email ignorées (8/10)             │
│    Catégorie systématiquement non utilisée      │
│    💡 Désactiver cette catégorie ?              │
│                                                 │
│ 3. Sessions VTC longues le lundi (>10h)         │
│    Discipline du lendemain en chute (-15%)      │
│    💡 Limiter à 8h le lundi ?                   │
│                                                 │
│ 4. Prière Asr souvent à la limite (6 fois)      │
│    Toujours pendant des courses VTC             │
│    💡 Vector overlay plus strict avant Asr ?    │
│                                                 │
│ [Voir toutes les frictions (12)]                │
└─────────────────────────────────────────────────┘
```

### 5.5 Submissions section

```text
┌─────────────────────────────────────────────────┐
│ 📋 SUBMISSIONS                                  │
│                                                 │
│ Proposées:               42                     │
│ Complétées:              16  (38%)              │
│ "Pas sa place ici":       4                     │
│                                                 │
│ Catégories les plus complétées:                 │
│   📞 Communication:      80% (4/5)              │
│   📋 Admin léger:        60% (6/10)             │
│   📱 Social léger:       57% (4/7)              │
│   🔎 Recherche:          50% (2/4)              │
│   🧠 Mental léger:       11% (1/9)              │
│                                                 │
│ 💡 Mental léger semble peu utilisé              │
└─────────────────────────────────────────────────┘
```

### 5.6 Pause / mode chill section

```text
┌─────────────────────────────────────────────────┐
│ ⏸️ PAUSE / RECONFIGURATION                       │
│                                                 │
│ Replans manuels (30 jours):    5                │
│ Raisons:                                        │
│   Trop fatigué:               3                 │
│   Plus d'énergie:             2                 │
│                                                 │
│ Pattern: tendance à demander un replan          │
│ le mercredi soir (3 fois)                       │
└─────────────────────────────────────────────────┘
```

### 5.7 Suggestions actionables (synthèse)

```text
┌─────────────────────────────────────────────────┐
│ 💡 SUGGESTIONS D'OPTIMISATION                   │
│                                                 │
│ Top 3 actions à considérer:                     │
│                                                 │
│ 🎯 Déplacer les workouts mardi → mercredi ?     │
│    Gain attendu: +8% discipline santé            │
│    [Plus tard]  [Modifier le planning]           │
│                                                 │
│ 🎯 Désactiver catégorie "Mental léger" ?        │
│    Gain attendu: moins de submissions ignorées  │
│    [Plus tard]  [Désactiver]                    │
│                                                 │
│ 🎯 Limiter sessions VTC du lundi à 8h ?         │
│    Gain attendu: meilleure discipline mardi     │
│    [Plus tard]  [Modifier les règles]            │
│                                                 │
│ Ces suggestions sont indicatives.                │
│ Tu restes maître de tes choix.                  │
└─────────────────────────────────────────────────┘
```

---

## 6. The Health Score Formula

```text
HEALTH_SCORE (0-100) = weighted average of:

  Discipline composite (40%):
    Average mission completion across all types,
    weighted by domain priority

  Plan stability (20%):
    % of plans followed without major adaptation
    + lower replans count = higher score

  Engagement consistency (15%):
    % of days with morning checkin done
    + % of days with at least 1 mission completed

  Friction reduction (15%):
    Lower number of detected frictions = higher score
    Trends matter (going down is good)

  Submissions usage (10%):
    Healthy ratio of completed submissions
    Not too low (ignored) nor too high (overwhelmed)

Each component is 0-100, weighted, then summed.
```

The score is meant to be a **quick pulse check**, not a grade. It's directional more than absolute.

---

## 7. Friction Detection Algorithm

This is the core intelligence of the dashboard.

### 7.1 Data sources

```text
- mission_outcomes (last 30 days)
- imperium_replan_events
- imperium_morning_checkins
- imperium_submission_completions / rejections
- mission failure reasons (analyzed by the local model)
- pgvector patterns (long-term)
```

### 7.2 Pattern detection

```text
PATTERN TYPE 1 — Recurring mission failures
  IF same mission_type fails ≥3 times with same reason in 30 days:
    Surface as friction
    Suggest: move, change time, or remove

PATTERN TYPE 2 — Day-of-week patterns
  IF discipline on a specific weekday is consistently lower:
    Surface as friction
    Suggest: lighten that day's load

PATTERN TYPE 3 — Domain neglect
  IF a domain has < 50% completion for 2+ weeks:
    Surface as friction
    Suggest: hierarchy review or content adjustment

PATTERN TYPE 4 — Submission category misuse
  IF a submission category has < 20% completion rate:
    Suggest: disable that category

PATTERN TYPE 5 — Replan triggers
  IF same trigger causes replan ≥5 times in 30 days:
    Surface as friction
    Suggest: address the root cause

PATTERN TYPE 6 — Late prayer warning
  IF prayer X is logged at the very end of its window
  more than 5 times in 30 days:
    Surface as friction
    Suggest: better Vector overlay rules

PATTERN TYPE 7 — Energy drain
  IF energy_score drops > 2 points after specific 
  mission types 3+ times:
    Surface as friction
    Suggest: rebalance or schedule recovery
```

### 7.3 Suggestion generation

```text
Frictions don't just describe problems — they suggest fixes.

For each detected friction:
  - Root cause analysis (the local model)
  - Proposed actions (parameterized)
  - Expected impact estimate
  - Action button ([Modifier], [Désactiver], [Plus tard])

The user can:
  - Apply the suggestion (system makes the change)
  - Defer ([Plus tard])
  - Dismiss permanently
```

---

## 8. Generation & Refresh

### 8.1 When the dashboard is generated

```text
ON-DEMAND ONLY by default.

User opens "Mon OS personnel":
  - If last generation < 24h: show cached
  - If last generation > 24h: regenerate automatically
  - User can tap [Actualiser] to force regenerate

NO BACKGROUND CRON for this.
The dashboard is a tool the user reaches for, not a 
constant computation.
```

### 8.2 Generation cost

```text
Once per generation:
  - SQL queries on outcomes/events (deterministic)
  - Friction detection algorithms (deterministic + the local model)
  - Health score computation (deterministic)
  - Suggestion phrasing (the local model for nuance)

Total: ~0.05€ per full generation
Annual: < 5€ if used weekly, even less otherwise
```

### 8.3 What's stored

```text
imperium_health_snapshots:
  Each generation stored with:
    - generated_at
    - period_days (30 default)
    - health_score
    - all metrics
    - frictions_detected (JSONB)
    - suggestions (JSONB)
    
Retained for 12 months for trend analysis.
After 12 months: only quarterly summaries kept.
```

---

## 9. The Daily End-of-Day Summary (Bonus Feature)

Validated: at end of day, Imperium shows a 4-line summary.

```text
At ~21h or before user's typical sleep time:
Imperium dashboard shows a transient card:

  ┌──────────────────────────────────────┐
  │ 🌙 Bilan d'aujourd'hui               │
  │                                      │
  │ • 8 missions complétées sur 11 (73%)│
  │ • VTC: 285 € généré                  │
  │ • Workout raté (fatigue)             │
  │ • Demain: réveil 6h30, journée VTC  │
  │                                      │
  │ Bonne nuit.                          │
  └──────────────────────────────────────┘

GENERATION:
- The first cloud tier generates the 3-4 lines
- Pulls from today's mission_outcomes
- Adds tomorrow's first 2-3 missions preview
- One-shot per day, ~0.02€/day

BEHAVIOR:
- Shown when user opens Imperium after 21h
- Auto-dismisses on tap or after 24h
- Stored in imperium_daily_summaries (audit trail)
```

This card is the bridge between the dashboard (long-term) and daily life (short-term). It humanizes the OS.

---

## 10. The Stash Zone (Bonus Feature)

A simple status for missions that the user doesn't want to delete but doesn't want to actively prioritize.

### 10.1 The mechanic

```text
Mission status in imperium_missions can include:
  - active (default)
  - faite, ratée, annulée, expirée (per doc 43)
  - stashed [NEW]

A stashed mission:
  - Is NOT in the active backlog
  - Is NOT scored or planned
  - Is NOT shown in daily plans
  - Is preserved (not deleted)
  - Can be re-activated anytime
```

### 10.2 How to stash

```text
On any mission, an option [Stasher]:
  - Mission moves to status='stashed'
  - User asked: "Pourquoi ?" (optional)
  - Mission disappears from active list

Where to find stashed missions:
  Imperium > Mes idées en attente:
    List all stashed missions
    User can:
      - Reactivate
      - Delete
      - Add a note
```

### 10.3 When stashing helps

```text
USE CASES:
- "I want to do this someday but not now"
- "This idea is interesting but too distracting"
- "I'm overwhelmed, archive this for later"
- "Maybe someone else will handle this"

PHILOSOPHY:
Stashed missions don't pressure the user.
They're a memory bank, not a TODO list.
```

### 10.4 Schema change

```sql
ALTER TABLE imperium_missions
ADD CONSTRAINT imperium_missions_status_check_v2
CHECK (status IN ('active', 'faite', 'ratée', 'annulée', 
                   'expirée', 'stashed'));

ALTER TABLE imperium_missions
ADD COLUMN IF NOT EXISTS stashed_at TIMESTAMPTZ NULL,
ADD COLUMN IF NOT EXISTS stash_reason TEXT NULL;
```

---

## 11. Database Schema

```sql
CREATE TABLE imperium_health_snapshots (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  generated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  period_days            INTEGER NOT NULL DEFAULT 30,
  
  -- Top-level
  health_score           INTEGER NOT NULL,        -- 0-100
  health_trend           NUMERIC(4,1) NULL,        -- delta vs previous month
  
  -- Discipline
  discipline_average     NUMERIC(4,3),
  discipline_per_domain  JSONB,
  best_day               DATE NULL,
  worst_day              DATE NULL,
  
  -- Stability
  plans_followed_pct     NUMERIC(4,3),
  plans_adapted_pct      NUMERIC(4,3),
  avg_replans_per_day    NUMERIC(4,2),
  replan_causes          JSONB,
  
  -- Submissions
  submissions_proposed   INTEGER,
  submissions_completed  INTEGER,
  submissions_rejected   INTEGER,
  submissions_per_category JSONB,
  
  -- Frictions
  frictions_detected     JSONB,
  frictions_count        INTEGER,
  
  -- Suggestions
  suggestions            JSONB,
  
  -- Generation cost
  ai_cost_eur            NUMERIC(6,4)
);

CREATE INDEX imperium_health_snapshots_user_idx
ON imperium_health_snapshots (user_id, generated_at DESC);

CREATE TABLE imperium_daily_summaries (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  summary_date           DATE NOT NULL,
  summary_text           TEXT NOT NULL,
  generated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  shown_to_user          BOOLEAN NOT NULL DEFAULT FALSE,
  shown_at               TIMESTAMPTZ NULL,
  
  UNIQUE (user_id, summary_date)
);
```

---

## 12. AI Tasks Touched

```text
imperium.health.compute_score      - deterministic
imperium.health.detect_frictions   - the local model (analyze patterns)
imperium.health.generate_suggestions - the first cloud tier (suggest tunings)
imperium.daily_summary.generate    - the first cloud tier (generate evening recap)
```

---

## 13. Routing Distribution

```text
Health dashboard generation: 
  - Health score: 0€ (deterministic)
  - Friction detection: 0€ (the local model)
  - Suggestions phrasing: ~0.05€ (the first cloud tier)

Daily summary:
  - The first cloud tier: ~0.02€/day = ~7€/year

Total annual: < 15€
```

---

## 14. UI Surface (V3)

```text
Imperium > Settings > "Mon OS personnel":
  
  ┌─ Top section ─────────────────────────────┐
  │ Health score (visual gauge + trend)        │
  │ [Actualiser]                               │
  └────────────────────────────────────────────┘
  
  ┌─ Sections collapsibles (open by default) ─┐
  │ 📊 Discipline                              │
  │ 🔄 Stabilité des plans                     │
  │ ⚠️ Frictions détectées                     │
  │ 📋 Submissions                             │
  │ ⏸️ Pause / Reconfiguration                  │
  │ 💡 Suggestions actionables                 │
  └────────────────────────────────────────────┘
  
  ┌─ Bottom ─────────────────────────────────┐
  │ Voir l'historique (12 derniers snapshots)│
  │ Exporter en PDF                          │
  └──────────────────────────────────────────┘

Imperium > Mes idées en attente (V3):
  List of stashed missions
  Search bar
  Sort options
  [Réactiver] [Supprimer] per mission

Imperium dashboard (after 21h):
  Bilan card (Section 9)
```

---

## 15. Privacy

```text
ALL ANALYSIS LOCAL OR TRUSTED CLOUD:
- Friction detection: the local model
- Suggestion generation: the first cloud tier (text input only)
- No external sharing of patterns

USER CONTROL:
- Disable dashboard anytime
- Clear health snapshot history
- Disable daily summary
- Disable stash feature
```

---

## 16. Implementation Order (V3)

```text
Phase 1 — Schema migrations
  ├─ imperium_health_snapshots
  ├─ imperium_daily_summaries
  └─ imperium_missions (status='stashed')

Phase 2 — Friction detection algorithms
  ├─ services/imperium/health/discipline_metrics.py
  ├─ services/imperium/health/plan_stability.py
  ├─ services/imperium/health/friction_detector.py
  ├─ services/imperium/health/suggestion_engine.py
  └─ Prompts for pattern analysis by the local model

Phase 3 — Health score computation
  └─ services/imperium/health/score_calculator.py

Phase 4 — API endpoints
  ├─ GET    /api/v1/imperium/health/snapshot
  ├─ POST   /api/v1/imperium/health/refresh
  ├─ POST   /api/v1/imperium/health/suggestions/{id}/apply
  ├─ POST   /api/v1/imperium/health/suggestions/{id}/dismiss
  ├─ GET    /api/v1/imperium/missions/stashed
  ├─ POST   /api/v1/imperium/missions/{id}/stash
  └─ POST   /api/v1/imperium/missions/{id}/unstash

Phase 5 — Daily summary
  ├─ services/imperium/daily_summary/generator.py
  ├─ Cron at 21h to pre-generate
  └─ Prompt template for the first cloud tier

Phase 6 — UI in Android
  ├─ Settings > Mon OS personnel screen
  ├─ Collapsible sections rendering
  ├─ Friction cards with action buttons
  ├─ Suggestion application flow
  ├─ Stash zone view
  └─ Evening summary card
```

---

## 17. Non-Goals For V3

```text
❌ Constant background computation
   (On-demand only, low cost)

❌ Comparing user to others (no social layer)

❌ Automatic friction "fixing" without user approval

❌ Push notifications about health score changes

❌ Public sharing of health stats

❌ Predictive AI ("you will fail tomorrow if...")

❌ Gamification (points, badges, etc.)
```

---

## 18. References

- `08_NON_NEGOTIABLE_RULES.md` — backend authority
- `30_AI_ROUTING_AND_SCORING_POLICY.md` — model selection
- `32_WR_INTERACTIVE_WORKFLOW.md` — WR feedback (different scope)
- `38_VECTORIZATION_PIPELINE.md` — long-term patterns
- `43_IMPERIUM_LOGIC_DETAIL.md` — mission lifecycle, replans
- `52_AI_DECISION_FRAMEWORK.md` — scoring framework
- `53_SUBMISSIONS_OVERLAY_TASKS.md` — submission stats

---

## 19. Final Note

```text
This dashboard is METADATA about the OS.
The OS has been working for the user.
This view shows IF and HOW WELL it has worked.

Without it: the OS is a black box.
With it: the OS is transparent and tunable.

The user is in control of their OS.
This dashboard is the steering wheel.
```

---

**Document version:** 1.0
**Status:** V3 design specification (DO NOT IMPLEMENT before V1 + V2)
**Last updated:** 2026-04-29
