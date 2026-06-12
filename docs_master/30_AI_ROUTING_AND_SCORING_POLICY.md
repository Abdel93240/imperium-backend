# 30 - AI Routing & Scoring Policy

## 0. Document Status

This document is the **official reference** for the AI layer of Imperium V1.

It defines:
- which AI model to call for each task
- when to call no AI at all
- how to score task difficulty
- where n8n fits in
- how the dialogue contexts (Weekly Review, Imperium chatbot) route models
- where AI results are stored

This version is a **full rewrite** (June 2026). It supersedes all previous versions, including any version where:
- Gemma was the default router
- Qwen 2.5 7B was the local router
- Opus 4.7 was the premium tier
- Haiku 4.5 was a routing tier

**V1 model decisions (canonical):**
- **Qwen 32B** is the official local routing/scoring/execution model (GPU-served on the V100). It replaces the former Qwen 2.5 7B.
- **Sonnet 4.6** is the first cloud tier.
- **Opus 4.8** is the default heavy cloud model.
- **Fable 5** is the top tier, reserved for tasks that are simultaneously long, complex, and high-stakes.
- **GPT-5.5** is the domain specialist for health (Pulse) and fresh/web data (Vector).
- **Gemini** handles vision/OCR. **Whisper local** handles audio.
- **CatBoost** is a dedicated metric ML model for Vector ride scoring — not an LLM.
- **Haiku is removed** from the routing hierarchy (the local Qwen 32B covers the low band; Sonnet bounds the top of it — no room left for a paid light tier).
- **Gemma** remains a future challenger only, not deployed by default.

**Candidates to evaluate later (not adopted yet):** MiniMax M3 and Qwen3.7 Max as potential challengers to Sonnet 4.6 on the mid cloud tier. To be tested on real Imperium tasks (reasoning, advice, French), not adopted on the basis of coding benchmarks.

Patch 2E implementation note (preserved):
- backend adapter: `app/services/ai/providers/qwen.py`;
- default mode: dry-run, no network call;
- smoke endpoint: `POST /api/ai/qwen/smoke`;
- output: structured JSON contracts only;
- canonical writes: forbidden from Qwen output without backend/user validation.

Patch 2F implementation note (preserved):
- n8n dry-run workflow file: `ops/n8n/workflows/wr_interactive_start_qwen_dry_run.json`;
- n8n calls the backend internal Qwen dry-run bridge, not the local model endpoint directly;
- bridge endpoint: `POST /api/internal/ai/qwen/smoke`;
- allowed bridge contract for now: `weekly_report.summary` + `weekly_summary`;
- result storage still goes through `POST /api/internal/ai/tasks/{task_id}/result`.

---

## 1. Non-Negotiable Principles

### 1.1 Backend is the source of truth

The Imperium backend is the canonical source of truth. Apps, n8n, and AI models must not write directly to PostgreSQL.

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

AI may: analyze, propose, classify, summarize, score, recommend, produce structured output.

AI must not:
- write directly to the database
- modify a mission without a backend endpoint
- change a priority rule without a backend endpoint
- make a critical financial or operational decision without a guard
- become the source of truth in place of the database

### 1.3 n8n orchestrates but does not own truth

n8n handles workflows that are temporal, multi-step, asynchronous, multi-API, AI-chained, email-triggered, webhook-triggered, file/audio/image based, or external-feed driven.

n8n must not contain canonical business logic. That logic belongs to the backend.

### 1.4 Determinism on the critical path

Wherever a deterministic choice (a fixed rule, a button, a backend computation) is sufficient, it must be preferred over an AI decision. AI is used where judgment is genuinely required, never where a rule already settles the matter.

This principle governs the whole document: hard rules force models at critical moments; dynamic scoring only fills the space rules leave open.

### 1.5 Scoring reduces cost

The scoring system exists to avoid calling a powerful (expensive) model when the local (free) model or a cheaper tier is enough.

Priority order for execution:

1. No AI if the backend can answer alone
2. Qwen 32B local if the task is within its reach
3. Sonnet 4.6 if the task exceeds the local model
4. Opus 4.8 if deep analysis / strategy is required
5. Fable 5 only if the task is long AND complex AND high-stakes

### 1.6 User-triggered AI calls

No expensive AI cloud call is triggered without explicit user action or a deterministic schedule the user has already opted into.

Pattern:

```text
Suggest → Inform → User decides → Execute
```

Exceptions allowed without user action:
- Local Qwen 32B calls (free, fast, no impact)
- Vision OCR inside a flow the user explicitly initiated
- Pure deterministic backend calculations (no AI)

---

## 2. The Two Distinct "Scorings"

A recurring source of confusion. Imperium has **two unrelated scoring systems**. They must never be conflated.

### 2.1 Task-difficulty scoring (`/200`)

A routing score that decides **which model** handles a task. Computed by the local Qwen 32B. Detailed in §5. This is the "scoring" referenced everywhere else in this document unless stated otherwise.

### 2.2 Vector ride scoring (CatBoost)

A **business ML model** specific to Vector. It scores ride opportunities (accept/skip, value estimation) from historical ride data. It is a CatBoost classifier (gradient boosting), chosen over a fine-tuned LLM because the task is tabular with many categorical features (zone, time slot, ride type, etc.), which CatBoost handles natively and cheaply.

This has **nothing to do** with model routing. It does not call the cloud. It is trained offline on Vector history and served as a dedicated prediction endpoint. It is documented here only to prevent confusion with the routing score.

---

## 3. Component Roles

### 3.1 Imperium Backend

Responsibilities: authentication, authorization, payload validation, idempotency, canonical storage, internal endpoints, permission enforcement, event journaling, exposing reliable snapshots to AI, and **maintaining shared dialogue context** (see §6).

The backend can call n8n or receive results from n8n, but it remains the final judge of what gets stored.

### 3.2 n8n

Responsibilities: run scheduled workflows, listen to webhooks, call external APIs, receive files/audio/images, chain multiple AI models, run long background workflows, return structured results to the backend.

V1 rule:

```text
Simple CRUD, simple read, simple deterministic compute → backend
Multi-step, temporal, AI, external, email, file, audio, image → n8n
```

### 3.3 Qwen 32B — local router / scorer / executor / dialogue conductor

GPU-served locally (V100). V1 roles:

- classify incoming tasks
- compute the dynamic difficulty score `/200`
- pick the recommended model
- detect ambiguities
- decide whether to escalate
- emit strict JSON routing output
- **conduct dialogue sessions** (Weekly Review, Imperium chatbot) as the default speaker, escalating per §6

Qwen 32B also executes local tasks directly: light reformulation, classification, short summary, categorization, simple extraction, non-critical micro-decisions, and the routine turns of a dialogue.

Qwen 32B is the router, not the sovereign. It must not be treated as absolute truth; canonical writes always pass through backend/user validation.

**Working hypothesis (assumed, validated empirically):** the 32B is capable of routing and conducting dialogue reliably. If real-world use shows it is not, that is an ecosystem-wide problem (not a Weekly-Review-specific one), and the answer is a hardware decision (e.g. a 70B model + an additional GPU), not a local patch.

### 3.3.1 Local deployment

Qwen 32B is GPU-served on the V100. The serving stack (Ollama or vLLM, to be finalized for a 32B on the V100) must be reachable by the backend through internal networking only. No public model port is exposed.

### 3.4 Gemma

Optional, not deployed by default. Future possible uses: A/B challenger to Qwen on a sample of decisions, local fallback when Qwen is unavailable, specialized micro-model if benchmarks prove it useful. Do not run Qwen + Gemma in parallel by default in V1.

### 3.5 Sonnet 4.6 — first cloud tier

Role: balanced cloud model, the first step above the local model.

Use for: structured reasoning, daily reorganization (multi-factor), logic correction, medium-complexity code, decisions with moderate context, document transformation, detailed financial advice (Vault Level 2), weekly nutrition / recovery plans, structuring projects (project module).

Note: candidates MiniMax M3 / Qwen3.7 Max may later challenge this tier on cost/quality — to be tested on real tasks before any swap.

### 3.6 Opus 4.8 — default heavy model

Role: premium strategic model, the default when real depth is required.

Use when value justifies cost: deep analysis, complex priority arbitration, long-term strategy, multi-domain synthesis, serious architectural debugging, high-consequence decisions, strategic reflection in the project module.

Opus must never be called by reflex.

### 3.7 Fable 5 — top tier (reserved)

Role: the most capable model (Mythos-class, above Opus). Reserved strictly for tasks that are **simultaneously long, complex, and high-stakes/durable**. On a moderately complex task, Opus and Fable perform comparably — so paying for Fable is only justified when task length and complexity let its lead materialize.

Built-in safeguard: for high-risk topics (cybersecurity, biology, chemistry, distillation), Fable blocks and falls back to Opus 4.8 on its own. This means the "sensitivity" routing criterion is partially handled model-side for Fable.

Canonical V1 use: the Weekly Review 4-week re-planning step (see §6). It is the one recurring task that reliably meets the three conditions. Everything else escalates to Opus or below.

### 3.8 GPT-5.5 — domain specialist (health + finance + fresh data)

Role: specialist for health/Pulse, **financial reasoning (Vault domain)**, and for fresh data / web research / verification / complex multimodal analysis.

Use for:
- health: weight/nutrition/recovery calculations and medical-feed analysis (Pulse). GPT-5.5 is the de facto "owner" of Pulse reasoning.
- **finance: analysis and advice over Vault data (budgets, cash-flow, financial pressure, project cost reasoning). GPT-5.5 is the de facto "owner" of financial reasoning. This reasoning lives in the Imperium brain and is invoked by the chatbot and the Weekly Review — NOT by the Vault app, which only displays/captures. In finance, GPT-5.5 must show its reasoning and flag uncertainty rather than invent a figure (hallucination resistance is the governing criterion); a confidently invented number is worse than useless.**
- fresh data: recent events around Paris (Vector — concerts, salons, sports), web retrieval, market comparison, regulatory research.
- generating actionable rules from sensitive or complex documents.

### 3.9 Gemini — vision / OCR

Role: vision / OCR. Use for receipts, screenshots, scanned documents, images, structured visual extraction.

### 3.10 Whisper local — audio

Role: audio transcription. Voice notes, long dictation, audio uploaded to Imperium, text preparation before AI routing. For short driving commands (<10s), Android Speech API is preferred to save resources.

### 3.11 CatBoost — Vector ride scoring

See §2.2. Dedicated business ML model, not part of routing.

---

## 4. n8n Trigger Architecture

n8n responds to six trigger families.

### 4.1 Time trigger
Examples: every Monday prepare the week; Tuesday 20:00 backend-only WR availability flag; every morning events around Paris (Vector); weekly events research (GPT-5.5 + web); nightly maintenance/backup/cleanup. Cron → backend snapshot/signal → often no AI yet → status flagged in DB → user banner on next refresh.

### 4.2 Database update trigger
Examples: weekly report validated, day.finished created, new Vault transaction, mission completed, daily plan validated. The DB does not call n8n directly in V1; the backend POSTs to signed, idempotent n8n internal webhooks when needed.

### 4.3 App button trigger
Examples: "Start Weekly Report", "Analyze my week", "Where should I go now?", "Scan receipt", "Analyze audio", "Generate daily plan". The app calls the backend; the backend decides whether to involve n8n.

### 4.4 External API trigger
Examples: Île-de-France Mobilités disruptions, weather alerts, events feeds, traffic, **calendar sync (V1)**. n8n watches/polls and forwards structured results to the backend. The calendar integration (see §6) lives here.

### 4.5 Email trigger
Examples: tax reminder, invoice, fine, bank notification, administrative correspondence, insurance. n8n extracts useful data, then sends to the backend.

### 4.6 Webhook / file / audio / image trigger
Examples: receipt photo, Bolt screenshot, user audio, PDF, medical image, voice note. n8n orchestrates OCR/STT/analysis; final storage goes through the backend.

---

## 5. Difficulty Scoring `/200`

### 5.1 Why `/200`

A `/200` score gives more granularity than a `/10` score. Each criterion is scored 0–10, then multiplied by a coefficient. Sum of coefficients: `5 + 3 + 3 + 2 + 2 + 3 + 2 = 20`. Maximum: `20 × 10 = 200`.

### 5.2 Official criteria

| Criterion | Coefficient | Score meaning |
|---|---:|---|
| Complexity | 5 | 0 = trivial, 10 = very complex |
| Context size | 3 | 0 = tiny context, 10 = massive context |
| Clarity / ambiguity | 3 | 0 = clear request, 10 = vague request |
| Error consequences | 2 | 0 = harmless, 10 = severe |
| Speed tolerance (inverted) | 2 | 0 = urgent / real-time, 10 = can wait |
| Data sensitivity | 3 | 0 = non-sensitive, 10 = highly sensitive |
| Cost justification | 2 | 0 = no premium cost justified, 10 = premium fully justified |

### 5.3 Official formula

```text
score_total =
    complexity         × 5
  + context_size       × 3
  + ambiguity          × 3
  + consequences       × 2
  + speed_tolerance    × 2
  + sensitivity        × 3
  + cost_justification × 2
```

Range: `0` to `200`.

### 5.4 Speed criterion is inverted

```text
0 = task must be done now
10 = task can wait
```

Fast models are cheaper and less capable; powerful models are slower and more expensive. The more a task can wait, the more Imperium can afford to escalate. This criterion measures escalation room, not pure difficulty.

### 5.5 Cost criterion is value-based

The cost criterion does not mean "more expensive = more difficult." It means: does the expected value justify paying for a more powerful model?

```text
0  = premium cost forbidden or useless
5  = medium cost acceptable
10 = premium cost fully justified
```

### 5.6 Dynamic routing thresholds

Dynamic routing applies only if no static rule (§7) already forces a model. Haiku has been removed; the local model now covers the former light-cloud band.

| Score `/200` | Recommended model | Role |
|---:|---|---|
| 0–99 | Qwen 32B local | Execute locally |
| 100–139 | Sonnet 4.6 | Balanced reasoning |
| 140–179 | Opus 4.8 | Deep analysis |
| 180–200 | **Critical mechanic (see below)** | Critical analysis |

#### Critical tier (180–200) — two-step mechanic

A score ≥180/200 is extremely rare (it requires a task that is simultaneously very complex, long, ambiguous, high-consequence and sensitive). When it happens, the gravity of the decision justifies the cost — we do not pinch pennies on Anthropic credits at this level. But a high score from Qwen may itself be a hallucination, so it must be independently verified before the heavy machinery runs.

**Step 1 — Independent re-scoring (anti-hallucination).**
The 180+ score was produced by Qwen (local scorer), which can hallucinate an inflated score. Before engaging the heavy machinery, **GPT-5.5** (a different provider, hallucination-resistant, and with no stake in the execution) receives the situation + the scoring table (§5.2/5.3) and **re-evaluates the score**.
- If GPT-5.5 lowers it below 180 → re-route to the band actually warranted (140–179 Opus 4.8, etc.). No heavy orchestration.
- If GPT-5.5 confirms ≥180 → Step 2.

**Step 2 — Free orchestration by Opus (gravity confirmed).**
Opus 4.8 is given the capability profiles of Fable 5 and GPT-5.5 and is left to **direct freely**: handle it itself, delegate, or combine. No cap on each model's depth of reasoning. At this gravity, cost is not a constraint.

**Anti-loop breaker (circuit breaker).**
The real failure mode at this tier is not a single weak model — it is models relaying to each other indefinitely (hollow back-and-forth, everyone "thinking" without converging). To prevent it without throttling intelligence:
- A counter bounds the number of **hand-offs between models** (≈3–4 relays max for one critical task).
- Each model may reason as deeply as it wants on its own turn (depth NOT capped).
- If the relay cap is reached without resolution → **Opus must produce the final answer itself, with no further delegation.** The breaker cuts the hollow loop; it does not limit thinking depth.

(The hand-off counter is a design rule; its backend implementation is tracked in the backlog.)

**Fable 5 is not reached by raw score alone.** It is engaged only when the three-fold condition (long AND complex AND high-stakes/durable) is met — in practice through a static rule (§7), e.g. the Weekly Review re-planning step. A high score routes to Opus 4.8; Fable is a deliberate, rule-driven choice, never a reflex of the score.

### 5.7 Emergency Mode (user-triggered)

Emergency Mode is a **behavior modifier**, not a shortcut to the heaviest model. Urgency and difficulty are different dimensions: an emergency can be simple-but-urgent (needs a FAST answer — local/Sonnet) or complex-and-grave (warrants Opus, or the §5.6 critical mechanic with Fable). Forcing the heaviest model on every emergency would be counter-productive: Opus/Fable reason deeply and are slower, while urgency often needs speed. The §5.2 "speed tolerance (inverted)" criterion already pushes urgent tasks toward the fast tier. So Emergency Mode raises priority and lifts the cost barrier, but lets normal scoring still pick the RIGHT model by the task's real nature.

**Trigger**
- The user signals an emergency through the chatbot (e.g. "I have an emergency").
- The AI asks for **explicit confirmation** ("activate Emergency Mode?") to prevent accidental activation.
- On confirmation → Emergency Mode ON for the current handling.

**What the mode changes (behavior)**
1. **Max priority** — the task jumps ahead of everything; it interrupts/preempts other in-flight processing.
2. **Cost barrier lifted** — as in the §5.6 critical tier, we do not pinch pennies; upgrading to a stronger model is allowed without cost retention.
3. **Fast context collection** — the AI immediately asks "explain what is happening" to scope the situation quickly, then acts.

**What the mode does NOT change (model choice stays nature-driven)**
- Normal §5 scoring still decides the model by the task's real nature:
  - simple + urgent → fast answer (Qwen 32B / Sonnet 4.6); no time wasted;
  - complex + grave → escalate (Opus 4.8, or the §5.6 critical mechanic with Fable 5 if the re-scored gravity reaches ≥180).
- Emergency Mode **never forces** the heaviest model. It lifts the cost barrier and sets priority; speed stays king when the task is simple. This is consistent with the inverted speed-tolerance criterion (§5.2): urgency biases toward fast execution, not toward maximal depth.

**Exit**
- Emergency Mode applies to the current emergency handling and ends when resolved (or when the user cancels it). It is not a persistent global state.

**Cross-references**
- §5.2 — speed tolerance (inverted): urgency biases toward fast tiers; Emergency Mode honors this rather than overriding it.
- §5.6 — if the emergency is genuinely critical (re-scored ≥180), the critical mechanic (GPT-5.5 re-score → Opus orchestration → anti-loop breaker) applies as usual; Emergency Mode simply guarantees priority and no cost retention.
- §1.6 — Emergency Mode is an explicit, user-confirmed action, so it satisfies the "no expensive cloud call without explicit user action" rule by design.

### 5.8 Automatic escalation

Even with a low score, escalate if:
- Qwen confidence is low
- the request is very ambiguous
- consequences are high
- the output will become a durable rule
- the task touches money, health, law, critical administrative, or security
- Qwen detects missing essential context

```text
If confidence < 0.65                     → escalate one tier
If consequences ≥ 8 and ambiguity ≥ 7    → minimum Sonnet 4.6
If consequences ≥ 9 and sensitivity ≥ 8  → Opus 4.8 or GPT-5.5 (depending on specialty)
```

### 5.9 Automatic downgrade

Downgrade to a cheaper model if: the score is low, the request is repetitive, a similar response already exists in memory, the task is pure formatting, the output has no consequences, or latency must be very short.

---

## 6. Dialogue Contexts (Weekly Review & Imperium Chatbot)

Imperium has two conversational contexts that share **one dialogue engine**: a single conductor model holds the thread, consults specialists behind the scenes, and escalates per turn. The engine is the same; only the framing differs.

### 6.1 Shared dialogue engine

- **Conductor = Qwen 32B (default).** It speaks to the user, keeps tone and continuity, and handles routine turns locally (acknowledgements, simple follow-up questions).
- **Shared context held by the backend.** Each model call receives the full relevant session dossier (summary, dialogue, data); each response is appended back. Switching models mid-dialogue does not break the thread, because the thread lives in the backend, not in any model's memory.
- **Specialists consulted behind the scenes.** When a turn touches a domain (health → GPT-5.5, etc.), the conductor consults the specialist and **restitutes the answer itself**, so the user always talks to a single interlocutor. This is the "family doctor + specialists" pattern, not a "committee".
- **Per-turn escalation.** Each turn is scored: a simple turn stays on Qwen 32B; a demanding turn escalates to Opus 4.8 (or Fable 5 only under the §7 rule). Escalation is mixed: hard rules at key moments, dynamic scoring for the rest.

### 6.2 Domain routing vs dialogue

- **Isolated tasks** (OCR, web research, a one-shot analysis) → routed directly to the domain specialist (§7). No conductor.
- **Dialogue** (Weekly Review, chatbot) → single conductor, specialists consulted in the background.

### 6.3 Weekly Review (WR)

The WR is the "fuel in the AI's tank": a weekly **decision review**, not a chatbot. Its purpose is to examine what changed during the week and whether the right decisions were made — the AI gives its view, the user gives theirs, and they discuss the week's decisions.

Trigger: Tuesday 20:00 banner → user clicks → session starts.

**Phase 1 — Summary by exception.** A model reviews the week focusing on **changes/deviations**, not a full recital. Stable areas are skimmed ("religion: regular, nothing to flag"). Changes are reported with **precise figures** ("food budget +5%, minor" vs "+13%, worth attention"), crossing domains ("you skipped your mission 3 days for fatigue, yet your health constants were good — why?"). The backend pre-computes the figures, so this phase reasons over prepared data → Opus 4.8 if it escalates; lighter if data is well prepared.

**Phase 2 — Relevant questions + conversation.** The hard part: detecting the real issues, asking pertinent (non-generic) questions, sustaining a dialogue where the user can push back ("why did you insist on the prefecture when I had three months and the garage was more urgent?"). Conductor = Qwen 32B by default; demanding turns escalate to Opus 4.8. Domain turns consult specialists (health → GPT-5.5) in the background.

**Phase 3 — Rolling 4-week re-planning.** All of the above is summarized, vectorized, and integrated with prior plans, vectorized history, and the **calendar**, to refine the next 4 weeks. The WR is a rolling window: 4 weeks behind, 4 weeks ahead. If a prior plan still holds, it is left unchanged; otherwise the AI re-plans, and may adjust every week ahead of it. **This step is forced to Fable 5 by a hard rule** (§7.8): it is long, complex, and high-stakes/durable — the one recurring task meeting all three conditions. It "lays the rails" the Qwen 32B then follows day to day, so the heavy model is not called by reflex during the week.

**Projects in the WR.** Projects are seen **only as decisions to evaluate** — e.g. the timing of activating a project versus the user's state ("you activated this heavy, slow-return project in a week you were exhausted; wouldn't a higher-energy month suit it better?"). The WR does not manage, plan, or break down projects. That belongs to the project module (§8).

**Calendar.** Fully integrated in V1 (decision: the planning value outweighs the connection overhead). n8n syncs an external calendar (§4.4), the backend stores an exploitable snapshot, the AI reads it in Phase 3.

### 6.4 Imperium chatbot

Same engine as the WR, different framing: **open, on-demand dialogue** with no imposed phases. The user drives the topic (often project advice). Escalation is purely score-driven per turn (no forced re-planning step). Conductor = Qwen 32B, specialists in the background, context held by the backend.

---

## 7. Static Pre-Scoring Rules (Overrides)

Some tasks bypass dynamic scoring entirely. They have a forced model or a forced path.

Note — Emergency Mode (§5.7) is NOT a static rule: it raises priority and lifts the cost barrier, but never forces a model. Model choice stays nature-driven via normal scoring (see §5.7).

### 7.1 Vision / OCR
```text
Image, receipt, screenshot, scanned document → Gemini
```
After Gemini extraction, Qwen may score the next step.

### 7.2 Audio
```text
Raw audio → Whisper local
```
After transcription, Qwen scores the follow-up.

### 7.3 Fresh data / web
```text
Need for current information → GPT-5.5 + web search
```
Examples: events within 30 km of Paris, recent regulation, current prices, news, public disruptions not already in a connected API.

### 7.4 Health / Pulse
```text
Health calculation or medical analysis → GPT-5.5
```
GPT-5.5 owns Pulse reasoning (weight/nutrition/recovery, medical-feed). Qwen must not produce a critical health analysis alone.

### 7.5 Finance / Vault reasoning
```text
Financial analysis or advice (not mere display) → GPT-5.5
```
Triggered when the brain reasons over financial data — typically inside the Imperium chatbot or the Weekly Review (budget/cash-flow analysis, financial pressure, project cost evaluation). NOT triggered by Vault simply displaying a balance or by deterministic backend computation (those stay app/backend). The distinction is **display vs reasoning**: showing a number is not analysing it. Qwen must not produce a critical financial analysis alone. GPT-5.5 must surface its reasoning and signal uncertainty rather than fabricate values.

### 7.6 Morning "AI advice" cards
The advice module present on each app dashboard is routed by app, by required depth — not as a special case but via normal domain routing:
```text
Imperium → fine advice  → brain (Opus 4.8 / scoring by depth)
Pulse    → fine advice  → GPT-5.5 (health, §7.4)
Vault    → fine advice  → GPT-5.5 (finance, §7.5)
Vector   → plain advice → Qwen 32B local (no finesse needed)
Path     → reformulation only → Qwen 32B local
```
**Path religious advice — hard rule.** For the religious advice, the AI does NOT generate and does NOT freely select content. Qwen 32B picks one entry at random from a DEDICATED, closed list of pre-written, validated advice (`base_advice`, to be created in the Path docs) and only reformulates/presents it. This base is DISTINCT from the Dars knowledge base (doc 50): the AI must never extract or interpret religious content from the Dars (or any broad corpus) at will. On religion, the AI presents pre-validated content; it never invents or cherry-picks. (`base_advice` does not exist yet — see backlog.)

### 7.7 Vector ride scoring
```text
Ride opportunity scoring → CatBoost (business ML, not an LLM, not the cloud)
```

### 7.8 Weekly Review re-planning
```text
WR Phase 3 (rolling 4-week re-planning) → Fable 5 (forced)
```
The one recurring task meeting long + complex + high-stakes/durable. Fable's own safeguard reroutes high-risk topics to Opus 4.8.

### 7.9 Deterministic backend decision
```text
CRUD, DB read, health check, dashboard snapshot, deterministic summary → Backend only
```

---

## 8. Project Module

Distinct from temporal planning (the daily/weekly/monthly cadence the WR handles). A project is an objective with steps, dependencies, and progress, on its own timeline.

Two AI facets, both routed by the general scoring (no dedicated expert model):
- **Structure** (break into steps, track dependencies/progress, adjust the project plan) → Qwen 32B or Sonnet 4.6 by complexity.
- **Reflect** (advise on strategy, arbitrate decisions) → Opus 4.8, and Fable 5 only if a given project decision is long + complex + high-stakes/durable.

Link to the WR is limited to §6.3: the WR evaluates the **timing** of project activation as one of the week's decisions. No mechanical step→mission automation in V1 (that is a V2 candidate). The project module also surfaces in the Imperium chatbot for open advice.

---

## 9. Summary Hierarchy

```text
Qwen 32B local   → router/scorer + local execution + dialogue conductor (~60% of tasks)
Sonnet 4.6       → first cloud tier (balanced reasoning)
Opus 4.8         → default heavy model (deep analysis, strategy)
Fable 5          → top tier, reserved (long + complex + high-stakes/durable; WR re-planning)
GPT-5.5          → specialist: health/Pulse + fresh data/web (Vector)
Gemini           → vision / OCR
Whisper local    → audio
CatBoost         → Vector ride scoring (business ML, not routing)
```

Removed: Haiku (no remaining territory). Future challengers: Gemma (local), MiniMax M3 / Qwen3.7 Max (mid cloud tier, to be tested).

Guiding principle throughout: deterministic on the critical path, dynamic for the rest; local by default; expensive cloud only when value justifies it; the 32B-capability hypothesis is assumed and validated empirically, with hardware (not patches) as the answer if it fails.
