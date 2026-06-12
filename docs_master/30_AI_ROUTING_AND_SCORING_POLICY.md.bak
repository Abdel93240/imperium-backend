# 30 - AI Routing & Scoring Policy

## 0. Document Status

This document is the **official reference** for the AI layer of Imperium V1.

It defines:
- which AI model to call for each task
- when to call no AI at all
- how to score task difficulty
- where n8n fits in
- where AI results are stored

This document supersedes any previous version where Gemma was considered the default router.

**V1 decision: Qwen 2.5 7B Instruct is the official local routing/scoring model.**

Gemma is not removed from the project but is no longer the V1 router. It remains an optional future challenger / fallback / specialized local model if internal benchmarks justify it.

Patch 2E implementation note:

- backend adapter: `app/services/ai/providers/qwen.py`;
- default mode: dry-run, no network call;
- smoke endpoint: `POST /api/ai/qwen/smoke`;
- output: structured JSON contracts only;
- canonical writes: forbidden from Qwen output without backend/user validation.

Patch 2F implementation note:

- n8n dry-run workflow file: `ops/n8n/workflows/wr_interactive_start_qwen_dry_run.json`;
- n8n calls the backend internal Qwen dry-run bridge, not the local model endpoint directly;
- bridge endpoint: `POST /api/internal/ai/qwen/smoke`;
- allowed bridge contract for now: `weekly_report.summary` + `weekly_summary`;
- result storage still goes through `POST /api/internal/ai/tasks/{task_id}/result`.

---

## 1. Non-Negotiable Principles

### 1.1 Backend is the source of truth

The Imperium backend is the canonical source of truth.

Apps, n8n, and AI models must not write directly to PostgreSQL.

Allowed flow:

```text
App / n8n / external service
        ↓
Imperium Backend API
        ↓
Validation + business rules + idempotency
        ↓
PostgreSQL imperium_core
```

Forbidden flow:

```text
n8n → PostgreSQL direct
AI → PostgreSQL direct
Android app → PostgreSQL direct
```

### 1.2 AI does not autonomously alter reality

AI may:

- analyze
- propose
- classify
- summarize
- score
- recommend
- produce structured output

AI must not:

- write directly to the database
- modify a mission without a backend endpoint
- change a priority rule without a backend endpoint
- make a critical financial or operational decision without a guard
- become the source of truth in place of the database

### 1.3 n8n orchestrates but does not own truth

n8n handles workflows that are:

- temporal
- multi-step
- asynchronous
- multi-API
- AI-chained
- email-triggered
- webhook-triggered
- file / audio / image based
- external feed driven

n8n must not contain canonical business logic. That logic belongs to the backend.

### 1.4 Scoring reduces cost

The scoring system exists to avoid calling a powerful (expensive) model when a local (free) or cheap model is enough.

Priority order for execution:

1. No AI if the backend can answer alone
2. Qwen local if the task is simple
3. Cheap cloud model if the task exceeds Qwen
4. Premium cloud model only if the score or a static rule justifies it

### 1.5 User-triggered AI calls

No expensive AI cloud call is triggered without explicit user action or a deterministic schedule that the user has already opted into.

The system pattern is:

```text
Suggest → Inform → User decides → Execute
```

Exceptions allowed without user action:

- Local Qwen calls (free, fast, no impact)
- Vision OCR inside a flow the user explicitly initiated
- Pure deterministic backend calculations (no AI)

---

## 2. Component Roles

### 2.1 Imperium Backend

Responsibilities:

- authentication
- authorization
- payload validation
- idempotency
- canonical storage
- internal endpoints
- permission enforcement
- event journaling
- exposing reliable snapshots to AI

The backend can call n8n or receive results from n8n, but it remains the final judge of what gets stored.

### 2.2 n8n

Responsibilities:

- run scheduled workflows
- listen to webhooks
- call external APIs
- receive files / audio / images
- chain multiple AI models
- run long background workflows
- return structured results to the backend

n8n is useful when the workflow exceeds a simple backend action.

V1 rule:

```text
Simple CRUD, simple read, simple deterministic compute → backend
Multi-step, temporal, AI, external, email, file, audio, image → n8n
```

### 2.3 Qwen 2.5 7B Instruct — primary local router/scorer

V1 role:

- classify incoming tasks
- compute the dynamic score `/200`
- pick the recommended model
- detect ambiguities
- decide whether to escalate
- produce a structured routing plan
- emit strict JSON routing output

Qwen can also execute small local tasks:

- light reformulation
- simple classification
- short summary
- categorization
- simple extraction
- non-critical micro-decisions

Qwen must not be used as absolute truth. Qwen is the router, not the sovereign.

### 2.3.1 Local deployment rule

In V1, Qwen runs through Ollama in Docker. The Ollama/Qwen container must be attached to the same internal Docker network as n8n and be reachable by the backend through internal networking only. No public Qwen/Ollama port should be exposed.

### 2.4 Gemma

V1 status: optional, not deployed by default.

Gemma is not installed simply out of habit. It can be added later if benchmarks show it beats Qwen on specific cases.

Future possible uses:

- A/B challenger to Qwen on a sample of decisions
- local fallback when Qwen is unavailable
- specialized micro-model for Vector if benchmarks prove it useful
- weekly routing-quality comparison

V1 rule:

```text
Do not run Qwen + Gemma in parallel by default.
Start with Qwen only for routing.
Gemma stays as a future benchmark candidate.
```

### 2.5 Claude Haiku 4.5

Role: lightweight cloud model.

Use for:

- clean reformulation
- medium synthesis
- classification with more nuance than Qwen
- non-critical tasks too long or too ambiguous for Qwen

### 2.6 Claude Sonnet 4.6

Role: balanced cloud model.

Use for:

- structured reasoning
- daily reorganization (multi-factor)
- logic correction
- medium-complexity code
- decisions with moderate context
- document transformation
- detailed financial advice (Vault Level 2)
- weekly nutrition / recovery plans

### 2.7 Claude Opus 4.7

Role: premium strategic model.

Use only when value justifies cost:

- Weekly Report deep analysis
- complex priority arbitration
- long-term strategy
- multi-domain synthesis
- serious architectural debugging
- high-consequence decisions

Opus must never be called by reflex.

### 2.8 GPT-5.5

Role: specialist for fresh data, web research, verification, and complex multimodal analysis.

Use for:

- recent events research (Vector — concerts, sports, salons in Paris area)
- web information retrieval
- market comparison
- regulatory research
- medical or administrative analysis requiring caution (Pulse Feed IA)
- generating actionable rules from sensitive or complex documents

### 2.9 Gemini

Role: vision / OCR.

Use for:

- cash receipts
- screenshots
- scanned documents
- images
- structured visual extraction

### 2.10 Whisper local

Role: audio transcription.

Use for:

- voice notes
- long dictation
- audio uploaded to Imperium
- text preparation before AI routing

For short driving commands (<10s), Android Speech API is preferred to save VPS resources.

---

## 3. n8n Trigger Architecture

n8n responds to six trigger families.

### 3.1 Time trigger

Examples:

- every Monday: prepare the week
- Tuesday 20:00 backend-only: WR availability flag, not n8n
- every morning: events around Paris (Vector)
- every Monday 03:00 Europe/Paris: weekly events research (GPT-5.5 + web)
- every night: maintenance, backup, cleanup, pre-analysis

Type flow:

```text
n8n cron
  → Backend snapshot or signal
  → no AI call yet (in many cases)
  → status flagged in DB
  → user banner shows on next refresh
```

### 3.2 Database update trigger

Examples:

- weekly report validated
- day.finished created
- new Vault transaction
- mission completed
- daily plan validated

The DB does not call n8n directly in V1. The backend POSTs to n8n internal webhooks when needed, signed and idempotent.

### 3.3 App button trigger

Examples:

- "Start Weekly Report"
- "Analyze my week"
- "Where should I go now?"
- "Scan receipt"
- "Analyze audio"
- "Generate daily plan"

The app calls the backend. The backend decides whether to involve n8n.

### 3.4 External API trigger

Examples:

- Île-de-France Mobilités disruption alert
- weather alerts
- events feeds
- traffic
- public APIs useful to Vector

n8n watches or polls these APIs and forwards a structured result to the backend.

### 3.5 Email trigger

Examples:

- tax reminder
- invoice
- fine
- bank notification
- administrative correspondence
- insurance

n8n receives or watches the email, extracts useful data, then sends to the backend.

### 3.6 Webhook / file / audio / image trigger

Examples:

- receipt photo
- Bolt screenshot
- user audio
- PDF document
- medical image
- voice note

n8n orchestrates OCR / STT / analysis; final storage goes through the backend.

---

## 4. Difficulty Scoring `/200`

### 4.1 Why `/200`

A `/200` score gives more granularity than a `/10` score.

Each criterion is scored 0 to 10, then multiplied by a coefficient.

Sum of coefficients:

```text
5 + 3 + 3 + 2 + 2 + 3 + 2 = 20
```

Maximum total:

```text
20 × 10 = 200
```

### 4.2 Official criteria

| Criterion | Coefficient | Score meaning |
|---|---:|---|
| Complexity | 5 | 0 = trivial, 10 = very complex |
| Context size | 3 | 0 = tiny context, 10 = massive context |
| Clarity / ambiguity | 3 | 0 = clear request, 10 = vague request |
| Error consequences | 2 | 0 = harmless, 10 = severe |
| Speed tolerance (inverted) | 2 | 0 = urgent / real-time, 10 = can wait |
| Data sensitivity | 3 | 0 = non-sensitive, 10 = highly sensitive |
| Cost justification | 2 | 0 = no premium cost justified, 10 = premium fully justified |

### 4.3 Official formula

```text
score_total =
    complexity        × 5
  + context_size      × 3
  + ambiguity         × 3
  + consequences      × 2
  + speed_tolerance   × 2
  + sensitivity       × 3
  + cost_justification × 2
```

Result range: `0` to `200`.

### 4.4 Speed criterion is inverted

```text
0 = task must be done now
10 = task can wait
```

In our model selection, fast models are also the cheaper and less capable. Powerful models are slower and more expensive.

The more a task can wait, the more Imperium can afford to escalate.

This criterion measures **escalation room**, not pure difficulty.

### 4.5 Cost criterion is value-based

The cost criterion does not mean "the more expensive, the more difficult."

It means:

```text
Does the expected value justify paying for a more powerful model?
```

Score:

- `0` = premium cost forbidden or useless
- `5` = medium cost acceptable
- `10` = premium cost fully justified

---

## 5. Dynamic Routing Thresholds

Dynamic routing applies only if no static rule already forces a model.

| Score `/200` | Recommended model | Role |
|---:|---|---|
| 0–59 | Qwen local | Execute locally |
| 60–99 | Haiku 4.5 | Lightweight cloud |
| 100–139 | Sonnet 4.6 | Balanced reasoning |
| 140–169 | Opus 4.7 | Deep analysis |
| 170–200 | Opus 4.7 + guard | Critical analysis, possible second opinion or user validation gate |

These thresholds are the **canonical V1 thresholds**. They override any older draft thresholds.

### 5.1 Automatic escalation

Even with a low score, escalate if:

- Qwen confidence is low
- the request is very ambiguous
- consequences are high
- the output will become a durable rule
- the task touches money, health, law, critical administrative, or security
- Qwen detects missing essential context

Rules:

```text
If confidence < 0.65               → escalate one tier
If consequences ≥ 8 and ambiguity ≥ 7  → minimum Sonnet 4.6
If consequences ≥ 9 and sensitivity ≥ 8 → Opus 4.7 or GPT-5.5 (depending on specialty)
```

### 5.2 Automatic downgrade

Downgrade to a cheaper model if:

- the score is low
- the request is repetitive
- a similar response already exists in memory
- the task is pure formatting
- the output has no consequences
- expected latency must be very short

---

## 6. Static Pre-Scoring Rules (Overrides)

Some tasks bypass dynamic scoring entirely. They have a forced model or a forced path.

### 6.1 Vision / OCR

```text
Image, receipt, screenshot, scanned document → Gemini
```

After Gemini extraction, Qwen may score the next step.

### 6.2 Audio

```text
Raw audio → Whisper local
```

After transcription, Qwen scores the follow-up.

### 6.3 Fresh data / web

```text
Need for current information → GPT-5.5 + web search
```

Examples:

- events within 30 km of Paris
- recent regulation
- current prices
- news
- public disruptions not already in a connected API

### 6.4 Medical / health-sensitive

```text
Medical document or critical health analysis → GPT-5.5 (preferred) or Opus 4.7
```

Qwen must not produce a critical medical analysis alone.

GPT-5.5 is preferred for medical reports because of its omnimodal native handling and concise rule-output format suitable for downstream Qwen consumption.

### 6.5 Deterministic backend decision

```text
CRUD, DB read, health check, dashboard snapshot, deterministic summary → Backend only
```

No AI involved.

### 6.6 Vector real-time

```text
Real-time decision, low consequences → Qwen local or backend deterministic rules
Strategic deferred VTC decision → Qwen scores, then escalates as needed
```

The detailed Vector logic is documented separately because rules are more complex.

### 6.7 Weekly Report analysis

```text
Weekly Report user-validated draft generation → Opus 4.7
```

This is a static override: WR analysis always uses Opus regardless of dynamic score.

Reason: WR is high-value, low-frequency, multi-domain, requires deep reasoning.

### 6.8 Vector weekly events research

```text
Weekly events research (Monday 03:00 Europe/Paris) → GPT-5.5 + web search
```

Static override based on the web-browsing requirement.

---

## 7. Routing Variables

The router operates on a hybrid set of variables.

### 7.1 Static variables

These are coded and stable. They must be present in the routing contract when available:

```text
request_id
user_id
source
trigger_type
task_type
module
priority_class
sensitivity_class
sla_class
allowed_models
forbidden_models
output_schema
storage_target
requires_user_validation
```

### 7.2 Dynamic variables

Evaluated by Qwen at each request:

```text
complexity
context_size
ambiguity
consequences
speed_tolerance
sensitivity
cost_justification
qwen_confidence
needs_clarification
detected_keywords
estimated_token_volume
```

Rule:

```text
The backend defines the playing field.
Qwen plays within the playing field.
```

---

## 8. App-Specific Routing Distribution

### 8.1 Imperium

```text
Daily ops (90%):              Qwen local
Day reorganization (4%):      Sonnet 4.6
Chatbot mentoring (3%):       Opus 4.7
Chatbot current events (2%):  GPT-5.5 + web
Chatbot standard (1%):        Sonnet 4.6
Weekly Report:                Opus 4.7 (static override)
```

### 8.2 Vector

```text
Daily decisions (95%):        Qwen local
Bolt overlay (3%):            Haiku 4.5
Events research weekly (1%):  GPT-5.5 + web (static override)
Strategic adjustments (0.5%): Sonnet 4.6
Weekly review (0.5%):         Opus 4.7
```

### 8.3 The Vault

```text
Daily ops (92%):              Qwen local
Receipt OCR (2%):             Gemini (static override)
Level 2 advice (4%):          Haiku 4.5
Monthly analysis (1%):        Sonnet 4.6
Weekly review (1%):           Opus 4.7
```

### 8.4 Pulse

```text
Daily ops (88%):              Qwen local
Quick adaptations (8%):       Haiku 4.5
Weekly plans (2%):            Sonnet 4.6
Receipt / inventory (1%):     Gemini
Medical reports (0.5%):       GPT-5.5 (static override)
Weekly review (0.5%):         Opus 4.7
```

### 8.5 The Path

```text
Daily ops (98%):              Qwen local
Light adaptations (1%):       Haiku 4.5
Strategic spiritual (1%):     Opus 4.7
```

---

## 9. Cost Distribution Target

```text
🟢 Qwen local / Gemma benchmark:    ~90% of all calls
🟡 Haiku 4.5:             ~5% of all calls
🟠 Sonnet 4.6:            ~3% of all calls
🟣 Opus 4.7:              ~1.5% of all calls
🔵 Gemini:                ~0.3% of all calls (vision only)
🟢 GPT-5.5:               ~0.2% of all calls (web / medical)
🎤 Whisper local:         used as needed (free)

Target monthly cost: ~13 € for AI + ~15 € VPS = ~28 € total
```

---

## 10. Storage Of AI Results

### 10.1 Future tables

Defined in `31_AI_TASKS_AND_RESULTS_CONTRACT.md`:

```text
ai_tasks
ai_results
ai_result_validations
```

Optional future:

```text
ai_routing_decisions
ai_runs
ai_cost_ledger
ai_feedback
```

### 10.2 Official storage flow

```text
n8n receives trigger
  → calls backend for context
  → calls Qwen router
  → calls chosen model
  → receives result
  → POST backend /api/ai/results (signed, idempotent)
  → backend validates contract
  → backend writes in imperium_core
```

n8n must not write directly to PostgreSQL.

---

## 11. Routing Examples

### 11.1 "Analyze my Weekly Report" button

```text
Trigger:        app button
Module:         Imperium
Task:           weekly_report.interactive.start
Static override: yes (WR → Opus)
Likely score:   145–175 (informational)
Model:          Opus 4.7
Mode:           async (n8n)
Storage:        ai_results, then weekly_reports on validation
```

### 11.2 Events around Paris (weekly research)

```text
Trigger:        scheduled Monday 03:00 Europe/Paris
Module:         Vector
Task:           vector.event_scan
Static override: requires_web (→ GPT-5.5)
Model:          GPT-5.5 + web
Mode:           async
Storage:        ai_results / future vector_intelligence_signals
```

### 11.3 Cash receipt photo

```text
Trigger:        image upload
Module:         Vault / Pulse
Task:           vault.receipt_extract
Static override: vision (→ Gemini)
Step 1:         Gemini extracts items + amounts
Step 2:         Qwen categorizes
Storage:        backend-validated transaction draft (user must validate)
```

### 11.4 Long voice note

```text
Trigger:        audio upload
Module:         Imperium
Task:           media.audio_transcription + extract
Static override: audio (→ Whisper local)
Step 1:         Whisper local transcription
Step 2:         Qwen scoring of resulting text
Storage:        ai_results or task draft
```

### 11.5 Backend health check

```text
Trigger:        app / API
Task:           system.health_review
AI:             none
Backend responds directly
```

### 11.6 Vector real-time decision

```text
Trigger:        app button / external signal
Module:         Vector
Task:           vector.zone_recommendation
AI:             Qwen local OR backend deterministic rules
Mode:           sync
High-latency model forbidden unless user explicitly asks deep strategy
```

---

## 12. Observability And Learning

Each AI call must record:

```text
model_selected
model_fallback
score_total
score_breakdown
latency_ms
estimated_cost
actual_cost_if_available
input_tokens
output_tokens
success
error_type
user_feedback
was_escalated
was_downgraded
```

### 12.1 Continuous improvement

The system can learn to route better, but not by silently changing official rules.

Allowed:

- adjust prompts
- add examples
- propose threshold changes
- produce a weekly routing-quality report

Forbidden without explicit user approval:

- change coefficients
- change thresholds
- enable a premium model everywhere
- create new official criteria
- bypass the backend

---

## 13. Privacy Policy

### 13.1 Local first

By default, sensitive data stays local if the local model is sufficient.

### 13.2 Redaction before cloud

If a cloud model is needed, the backend or n8n reduces data sent to the minimum useful.

Examples:

- mask identifiers
- remove full emails when not needed
- replace exact amounts with ranges when possible
- extract only the relevant fields

### 13.3 Cloud allowed when

- expected value exceeds risk
- the task cannot be done locally
- the user has explicitly triggered an analysis
- the output contract is clear
- the audit trail is preserved

---

## 14. Official Decision: Qwen vs Gemma

### 14.1 V1 decision

```text
Qwen 2.5 7B Instruct replaces Gemma as the primary local router.
```

Reasons:

- best candidate for instruction following
- fits structured scoring well
- better at producing stable JSON
- more consistent for classification and routing
- avoids running two local routers concurrently in V1

### 14.2 Gemma status

Gemma is in backlog.

It can be added later if:

- Qwen costs too much in RAM or latency
- Qwen fails on certain micro-decisions
- Gemma scores higher on Vector tasks
- a second local opinion is desired
- the VPS can support both without degrading n8n / PostgreSQL / API

### 14.3 No double-cost in V1

V1 does not run Qwen + Gemma on each task.

The system collects metrics with Qwen alone first.

After 2 to 4 weeks of logs, Gemma can be tested offline on a sample.

---

## 15. Implementation Order

### Phase 1 — Documents

```text
docs_master/30_AI_ROUTING_AND_SCORING_POLICY.md  (this document)
docs_master/31_AI_TASKS_AND_RESULTS_CONTRACT.md  (next)
docs_master/32_WR_INTERACTIVE_WORKFLOW.md         (depends on 31)
```

### Phase 2 — Backend AI contracts

Create migrations and endpoints for `ai_tasks`, `ai_results`, `ai_result_validations`.

No AI model connected yet.

### Phase 3 — Storage validation

Test end-to-end task creation, result storage, validation flow with mock data.

### Phase 4 — Wire n8n with mock

Build a simple n8n workflow:

```text
Manual trigger
  → backend get task context
  → mock Qwen scoring
  → mock model result
  → backend store ai_result
```

### Phase 5 — Wire Qwen local

Install Qwen via Ollama on the VPS (KVM 4 confirmed: 16 GB RAM, suitable for Q5_K_M quantization).

Replace mock Qwen with real local calls.

### Phase 6 — Wire premium models

Add Haiku / Sonnet / Opus / GPT-5.5 / Gemini progressively, with cost and latency logging.

### Phase 7 — Wire Whisper local

Install faster-whisper alongside Qwen for transcription.

---

## 16. Executive Summary

Imperium uses a hybrid AI architecture:

```text
Backend = truth
n8n = orchestration
Qwen = local router/scorer
Cloud models = specialists called only when justified
PostgreSQL imperium_core = canonical storage
pgvector = semantic memory (never canonical truth)
```

The scoring is hybrid:

```text
Static criteria + dynamic notes + static overrides
```

The official formula:

```text
/200 = 7 criteria scored /10 with weighted coefficients
```

The thresholds:

```text
0–59     → Qwen local
60–99    → Haiku 4.5
100–139  → Sonnet 4.6
140–169  → Opus 4.7
170–200  → Opus 4.7 + guard (validation or second opinion)
```

The goal is not to call the most powerful model everywhere.

The goal is to call the model that is:

```text
smart enough to succeed,
fast enough for the context,
cheap enough to last,
and controlled enough to never corrupt Imperium.
```

---

**Document version:** 2.0 (aligned with doc 31 and doc 32)
**Status:** Official V1 reference
**Last updated:** 2026-04-28
