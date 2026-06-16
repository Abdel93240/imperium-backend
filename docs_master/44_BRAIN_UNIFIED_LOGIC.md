# 44 - Brain Unified Logic

## 1. Purpose

This document defines the **official unified brain model** of the Imperium ecosystem.

The core principle is simple:

> There is one canonical brain. The apps are not independent systems. They are different surfaces over the same backend, the same database, the same memory, the same routing policy, and the same user context.

This document must be read together with:

- `30_AI_ROUTING_AND_SCORING_POLICY.md`
- `31_AI_TASKS_AND_RESULTS_CONTRACT.md`
- `32_WR_INTERACTIVE_WORKFLOW.md`
- `40_PULSE_LOGIC_DETAIL.md`
- `41_PATH_LOGIC_DETAIL.md`
- `42_VAULT_LOGIC_DETAIL.md`
- `43_IMPERIUM_LOGIC_DETAIL.md`

This document does **not** replace the AI routing contract. It clarifies how all domains use the same brain without creating inter-app chaos.

---

## 2. The Wrong Mental Model

```text
WRONG:

  ┌──────────┐    ┌──────────┐
  │ Imperium │ ←→ │  Vector  │
  └──────────┘    └──────────┘
        ↑               ↑
        │               │
        ↓               ↓
  ┌──────────┐    ┌──────────┐
  │  Vault   │ ←→ │  Pulse   │
  └──────────┘    └──────────┘
                       ↑
                       │
                  ┌──────────┐
                  │ The Path │
                  └──────────┘

Apps as separate nodes that communicate directly.
```

This model creates unnecessary complexity:

```text
- app-to-app APIs
- message passing between domains
- duplicated state
- conflict resolution between apps
- fragile orchestration
- unclear ownership
```

This is not the Imperium architecture.

---

## 3. The Right Mental Model

```text
RIGHT:

                 ┌──────────────────────────┐
                 │                          │
                 │     UNIFIED BRAIN        │
                 │                          │
                 │  Backend services        │
                 │  PostgreSQL canonical DB │
                 │  pgvector memory         │
                 │  ai_tasks / ai_results   │
                 │  Qwen router             │
                 │  cloud model escalation  │
                 │  deterministic rules     │
                 │  user priority hierarchy │
                 │                          │
                 └──────────────────────────┘
                    ↑     ↑     ↑     ↑
                    │     │     │     │
          ┌─────────┘     │     │     └─────────┐
          │               │     │               │
    ┌─────┴─────┐   ┌─────┴─────┐        ┌──────┴──────┐
    │ Imperium  │   │  Vector   │        │   The Path  │
    └───────────┘   └───────────┘        └─────────────┘
                          │
                    ┌─────┴─────┐
                    │ Vault     │
                    │ Pulse     │
                    └───────────┘
```

The apps do not talk to each other directly.

They all consult the same backend brain.

The backend brain decides what each app shows, based on canonical data, deterministic rules, and AI outputs when needed.

---

## 4. The Teacher Analogy

```text
Imagine a professor in front of one blackboard.
The blackboard contains the full truth.
Different students sit in different places.

The professor does not create five blackboards.
He turns the same blackboard toward the student who needs it.

- Imperium sees: missions, focus, dashboard, WR, priorities
- Vector sees: VTC profitability, zones, sessions, operational opportunities
- Vault sees: money, transactions, weekly profit, financial radar
- Pulse sees: health, food, training, stock, body tracking
- The Path sees: worship, sadaqa, fasting, prayer-related actions

Same blackboard.
Same truth.
Different angle.
```

When the user logs data in one surface, the backend updates the canonical blackboard. Other surfaces see the new state when they query the backend.

---

## 5. Unified Brain Does Not Mean AI Controls Everything

The word “brain” does **not** mean every decision goes through an LLM.

The official order is:

```text
1. Hard rules / non-negotiable rules
2. Deterministic backend logic
3. User priority hierarchy
4. Qwen routing / classification when needed
5. Cloud model escalation only when justified by doc 30 scoring
6. Backend validation before any canonical write
```

AI is not the source of truth.

The source of truth is:

```text
PostgreSQL canonical DB + backend rules + append-only events.
```

AI proposes, classifies, summarizes, extracts, reasons, or drafts. The backend validates and writes.

---

## 6. The AI Layer Within The Brain

The AI layer follows docs 30 and 31.

### 6.1 Official V1 router

```text
Official local router / classifier: Qwen 32B
Runtime target: Ollama/Qwen in Docker
Network target: same Docker network as n8n and imperium-api
```

Qwen is responsible for:

```text
- task classification
- difficulty scoring
- deciding whether a stronger model is required
- selecting the model according to doc 30 thresholds
- creating structured task plans for the backend/n8n workflow
- detecting when user clarification is needed
```

### 6.2 Gemma status

```text
Gemma is not the official V1 router.
Gemma is optional lab infrastructure only.
It must not be referenced as the production decision-maker.
```

This avoids ambiguity between Qwen and Gemma.

### 6.3 n8n AI Agent status

```text
The n8n AI Agent is not part of the official V1 intelligence layer.
```

n8n may execute workflows, call Qwen/Ollama, call external models, wait for results, and send results back to the backend.

But n8n does not become the AI decision authority.

---

## 6-bis. Expert-Call Orchestration During Qwen Dialogue

### 6-bis.1 Principle: the orchestrator drives

Models never call each other directly.

```text
Qwen talks with the user
→ Qwen returns a structured result + self-score to the backend/orchestrator
→ the orchestrator decides whether escalation is needed
→ the orchestrator fills the specialist prompt template
→ the specialist model returns a structured expert result
→ Qwen reintegrates the result for the user
```

This prevents runaway chains, uncontrolled cost, and untraceable model-to-model
calls. Every hop is created, logged, validated, and bounded by the backend/Tower.

### 6-bis.2 Qwen stays master of live dialogue

The user always talks to Qwen. If a specialist is needed, the specialist round
trip is invisible to the user.

Rules:

- Qwen keeps conversational continuity.
- The expert does not become the chat surface.
- Qwen reintegrates the expert answer in its own words.
- Canonical writes still require backend validation and, when needed, user
  confirmation.

Continuity lives in Qwen, not in the expert.

### 6-bis.3 Expert data freshness: solved by RAG

The system must not rely on Qwen to gather and forward all domain facts. Qwen may
forget a key detail, compress too much, or preserve the wrong thing.

When the orchestrator invokes an expert, it provides:

```text
- expert role / intrinsic project of the domain (Layer 1)
- user's explicit domain projects from F01 meta-prompt (Layer 2)
- user's question
- RAG access to vectorized domain data
```

Example for Pulse:

```text
The health expert receives the Pulse role, the user's explicit health projects,
the user's question, and RAG access to workouts, meals, weight history, pain logs,
and training evolution. The expert retrieves what it needs itself.
```

This matches the WR RAG principle: the expert pulls real vectorized data instead
of depending on a possibly lossy Qwen summary.

### 6-bis.4 Cost control for expert calls

API models are stateless. Keeping an expert "warm" means re-sending prior
exchanges; it preserves continuity but does not reduce the number of calls and
can increase per-call cost as history grows.

Cost is controlled by:

```text
1. RAG: the expert pulls data directly.
2. Filtering: Qwen escalates only genuinely complex questions.
3. Light question grouping: Qwen can let the user finish a small flow of domain
   questions, then make one expert call.
```

Qwen must not escalate ordinary low-risk questions that it can answer locally.

### 6-bis.5 V1 decision

```text
V1:
  - keep expert continuity by re-sending the relevant recent conversation
  - limit this to a small number of exchanges, around 2-3 max on a topic
  - combine it with RAG access, strict escalation filtering, and light grouping
```

This accepts a small context cost for continuity while keeping live expert
dialogues bounded.

### 6-bis.6 Future option: vectorize expert answers during dialogue

Not V1.

The possible future design is to vectorize expert answers so the next expert call
retrieves only the important essence instead of re-sending verbatim history.

Merit:

- applies RAG to the expert's own conversational memory
- can keep context light if expert dialogues become long

V1 blocker:

- latency during live chat: embed, store, embed query, search, build prompt
- likely overkill for short expert sub-dialogues of 2-5 questions

Viability condition:

```text
Adopt only if real expert dialogues become genuinely long AND measured embedding
latency on the V100 is low enough to avoid a slow/choppy chat experience.
```

---

## 7. Where AI And n8n Results Are Stored

AI and n8n results are **not** stored in a separate n8n database.

The official storage target is the canonical Imperium database:

```text
Database: imperium_core
Tables: ai_tasks, ai_results, domain-specific result tables
```

The n8n database remains only n8n’s operational database:

```text
n8n_db:
  - workflow definitions
  - execution history
  - n8n credentials
  - n8n internal state

n8n_db must not become an Imperium source of truth.
```

### 7.1 Write path for AI results

```text
Backend creates ai_task
→ n8n receives/observes task
→ n8n calls Qwen or cloud model
→ model returns structured result
→ n8n POSTs result to backend internal endpoint
→ backend validates result against schema
→ backend writes ai_result
→ backend writes domain table only if allowed
```

AI and n8n never write canonical tables directly.

---

## 8. Privacy Boundary For External Models

When a cloud model is used, especially GPT or Claude, the backend must send only the minimum required context.

Official rule:

```text
External models receive anonymized or pseudonymized task context.
They analyze the data.
They do not need to know who the user is.
```

Example:

```text
Allowed:
  "User had 4 VTC sessions, 2 missed workouts, net weekly profit 740 EUR."

Not allowed:
  "Abderrahman, living at X, using email Y, did..."
```

For sensitive domains such as medical data, the dedicated override rules in doc 30 still apply. If a Weekly Report references medical information, the medical analysis and the weekly analysis must be treated as separate `ai_tasks` when needed:

```text
Pulse medical extraction/analysis → medical-safe model route
Weekly Report synthesis → WR route
Shared memory reference → backend-controlled, minimal, contextual
```

This prevents one workflow from accidentally bypassing a stricter privacy rule.

---

## 9. No Inter-App Communication Layer

There is no direct message bus between apps.

```text
Vector does not call Pulse.
Pulse does not call Vault.
Vault does not call Path.
Path does not call Imperium.
```

Instead:

```text
1. The frontend calls the backend.
2. The backend service reads canonical data.
3. The owning service writes its own domain tables.
4. The backend emits append-only events.
5. Other services read the updated state when queried or triggered.
```

The event table is an audit and coordination surface, not a replacement for backend rules.

---

## 10. Table Ownership Rule

Each service can read data required to compute its response, but writes are owned.

```text
READ:
  A service may read any table it needs, through backend code, with auth and policy checks.

WRITE:
  Only the owning domain service writes its own canonical tables.
```

Examples:

```text
Vault owns vault_transactions.
Imperium may read Vault summaries for dashboard and WR.
Imperium does not manually mutate vault_transactions.

Path owns worship/sadaqa/fasting related tables.
Imperium may read Path obligations for dashboard priority.
Imperium does not directly mutate Path logs.

Vector owns VTC operational tables.
Imperium may read Vector session state.
Imperium does not write Vector rides directly.
```

---

## 11. Vector Scope Boundary

Vector V1 is strictly focused on **VTC profitability and operational execution**.

Vector should reason about:

```text
- zones
- sessions
- revenue opportunities
- waiting / repositioning
- airport / station / event opportunities
- traffic and disruption signals relevant to profitability
- ride profitability heuristics
- VTC operational timing
```

Vector should not own:

```text
- fatigue management
- sleep pressure
- health decisions
- global objective pressure
- family priorities
- spiritual priorities
- general life arbitration
```

Those belong to Imperium, Pulse, Path, or the unified priority system.

When Vector needs to display a recommendation, the backend can still filter or suppress it through the global priority hierarchy, but Vector’s internal job remains VTC profitability.

---

## 12. User Priority Hierarchy

When the brain must arbitrate between competing surfaces, it uses deterministic priority rules.

Stored in:

```text
imperium_priority_rules
```

Edited through:

```text
Imperium settings UI
```

The priority hierarchy is not an AI feeling. It is a user-defined rule set.

AI can help explain or suggest changes, but the active hierarchy is deterministic.

---

## 13. n8n Role In The Unified Brain

n8n is useful, but it has a precise role.

n8n is:

```text
- orchestrator
- scheduler
- trigger receiver
- external API watcher
- email/webhook connector
- long-running workflow executor
- bridge between backend and model calls
```

n8n is not:

```text
- source of truth
- direct DB writer
- AI decision authority
- replacement for backend services
- owner of Imperium business logic
```

### 13.1 Official n8n trigger categories

n8n may be triggered by:

```text
1. Temporal triggers
   Example: every Monday, fetch events in a 30 km radius for Vector.

2. Backend/application signals
   Example: user clicks "start Weekly Review" in the app.

3. Database state changes mediated by backend
   Example: Weekly Review state changed, backend exposes or sends a signal.

4. External APIs
   Example: Île-de-France Mobilités disruption signal for RER D.

5. Incoming emails
   Example: tax reminder email received, n8n routes it to backend intake.

6. Generic webhooks
   Example: receipt photo upload, audio capture sent for transcription.
```

### 13.2 DB updates must not call n8n directly in V1

In V1, PostgreSQL should not directly trigger n8n.

Allowed V1 mechanisms:

```text
A. Backend emits an internal HTTP call to an n8n webhook after an important write.
B. n8n polls a backend endpoint such as /api/internal/events/since when implemented.
C. User/app button calls backend, backend creates state/task, then n8n continues workflow.
```

Deferred V2 mechanism:

```text
PostgreSQL LISTEN/NOTIFY or event-stream worker.
```

This keeps responsibility clean:

```text
DB stores truth.
Backend owns rules.
n8n executes workflows.
```

---

## 14. App Buttons Are Backend Signals, Not Direct n8n Authority

When the user presses a button in the app, the frontend should normally call the backend first.

Example: Weekly Review.

```text
User clicks "Start Weekly Review"
→ frontend calls POST /api/imperium/weekly-review/launch
→ backend authenticates user
→ backend validates idempotency
→ backend updates WR state
→ backend creates/updates ai_task if needed
→ n8n continues the workflow
→ n8n sends AI result back to backend
```

The app should not bypass the backend and call n8n directly for canonical workflows.

---

## 15. The Brain Has No Public `/brain` API

There is no public endpoint like:

```text
/api/brain/decide
```

The brain is not one endpoint. It is the combined behavior of:

```text
- backend services
- canonical tables
- events
- ai_tasks / ai_results
- Qwen routing
- model escalation
- deterministic rules
- user priorities
```

Apps call domain endpoints:

```text
/api/imperium/dashboard
/api/imperium/report/week
/api/imperium/weekly-review/launch
/api/vault/transactions
/api/vector/...
/api/pulse/...
/api/path/...
```

Internal automation may call internal endpoints:

```text
/api/internal/...
```

But there is no public brain endpoint.

---

## 16. What Each App Surface Does

### Imperium

```text
Reads:
  missions, priorities, dashboard, daily plan, day review, WR, Path/Pulse/Vault/Vector summaries

Writes:
  missions, priority rules, daily plan state, day finish, WR state, user-validated command actions

Owns:
  command center, arbitration display, global dashboard, WR UX, planning surfaces
```

### Vector

```text
Reads:
  VTC sessions, external event signals, traffic/disruption signals, zone history, profitability context

Writes:
  VTC session state, ride logs, zone observations, VTC operational notes

Owns:
  VTC profitability logic only
```

### Vault

```text
Reads:
  transactions, weekly summaries, pressure indicators, upcoming obligations

Writes:
  manual transactions, wallet snapshots, categories, weekly financial facts

Owns:
  financial truth and money radar
```

### Pulse

```text
Reads:
  meals, workouts, stock, body, hydration, health rules

Writes:
  meal logs, workout logs, stock updates, body snapshots, hydration logs

Owns:
  health, food, training, body tracking
```

### The Path

```text
Reads:
  prayer times, fasting state, sadaqa state, Quran progression, adhkar, ghusl status

Writes:
  prayer completions, fasting actions, sadaqa donations, adhkar increments, Quran progression, ghusl status

Owns:
  worship and spiritual path tracking
```

---

## 17. Weekly Review Example

The Weekly Review is a good example of the unified brain.

```text
Tuesday 20:00
→ WR banner becomes active in Imperium UI
→ user clicks "Start Weekly Review"
→ backend launches WR state
→ n8n receives the workflow signal
→ Qwen routes the task
→ Opus generates the first weekly synthesis when required
→ user reads it in WR popup
→ AI asks clarification questions if needed
→ user answers in the popup
→ AI generates final report
→ user approves or requests revision
→ approved report is stored by backend in canonical DB
```

Important constraints:

```text
- n8n orchestrates the workflow
- Qwen routes/classifies
- Opus may synthesize
- user validates the final report
- backend writes the final canonical result
- n8n never writes canonical DB tables directly
```

---

## 18. A Real Day In The Life

```text
06:30 - Imperium opens daily plan
        User reviews the deterministic plan or AI-assisted plan
        Backend reads priorities, missions, recent data
        Backend returns one coherent dashboard

09:00 - User starts VTC session in Vector
        Vector records session start
        Vector focuses on VTC profitability and positioning

11:45 - External signal arrives
        n8n sees an event, traffic, or rail disruption
        n8n sends the signal to backend intake
        Backend stores canonical event/signal
        Vector endpoint can use it when asked for recommendations

14:00 - Vault transaction logged
        User records income or expense
        Backend writes vault_transactions
        Weekly summaries and dashboard become aware of it

18:00 - Path action completed
        User marks prayer/fasting/sadaqa action
        Backend writes Path-owned data
        Imperium dashboard can surface the result

22:00 - User ends VTC session
        Vector stores session end
        Vault may receive confirmed income only through an allowed backend flow

23:00 - User finishes day
        Imperium day review is stored
        Events are append-only
        Future WR has more data to summarize
```

No app called another app directly.

The backend and DB unified the day.

---

## 19. What This Architecture Forbids

```text
❌ Apps writing to each other's tables
❌ n8n writing directly into canonical DB tables
❌ AI models writing directly into canonical DB tables
❌ n8n_db storing Imperium truth
❌ frontend making cross-domain decisions
❌ app-to-app HTTP calls
❌ cloud models receiving unnecessary identity data
❌ Gemma being treated as the official V1 router
❌ n8n AI Agent replacing Qwen routing
❌ Vector owning fatigue, health pressure, or global objective pressure
```

---

## 20. Implementation Anchor Points

For Codex / Claude Code:

```text
1. All domain services live under backend/app/services/.
2. Service folders are domains, not isolated apps.
3. Services may read any required canonical table through backend rules.
4. Services write only their owned domain tables.
5. Events are append-only audit/coordination records.
6. ai_tasks and ai_results are the official AI work ledger.
7. Qwen 32B is the official V1 local router.
8. Ollama/Qwen runs in Docker on the same network as n8n and imperium-api.
9. n8n orchestrates triggers and workflows, but owns no truth.
10. n8n sends all results back to backend internal endpoints.
11. Backend validates and writes canonical results.
12. Cloud model calls must use minimized/anonymized context.
13. The frontend displays backend decisions; it does not become the brain.
```

---

## 21. References

- `00_VISION_GLOBALE.md` — original vision
- `08_NON_NEGOTIABLE_RULES.md` — backend authority rules
- `15_SERVICE_ARCHITECTURE_MAP.md` — service evolution
- `16_AI_BACKEND_LAYER_OVERVIEW.md` — AI layer overview
- `30_AI_ROUTING_AND_SCORING_POLICY.md` — official scoring and model routing
- `35_QWEN_SETUP_AND_PROMPTS.md` — Qwen prompts and specialist prompt placement
- `38_VECTORIZATION_PIPELINE.md` — vectorization mechanics
- `47_WR_GUIDED_SECTIONS.md` — WR RAG precedent
- `F01_USER_OBJECTIVES.md` — explicit projects as domain prompt layer
- `31_AI_TASKS_AND_RESULTS_CONTRACT.md` — AI task/result storage contract
- `32_WR_INTERACTIVE_WORKFLOW.md` — Weekly Review interactive workflow
- `33_VECTOR_LOGIC_DETAIL.md` — Vector scope and VTC logic
- `40_PULSE_LOGIC_DETAIL.md` — Pulse logic
- `41_PATH_LOGIC_DETAIL.md` — Path logic
- `42_VAULT_LOGIC_DETAIL.md` — Vault logic
- `43_IMPERIUM_LOGIC_DETAIL.md` — Imperium logic

---

**Document version:** 1.1  
**Status:** Architectural reference — cleaned and aligned with AI routing docs 30/31/32  
**Last updated:** 2026-04-29
