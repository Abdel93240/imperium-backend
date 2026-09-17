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

Mapping update (2026-09-17, documentation only): the §3 assignments dated June/July 2026 (Sonnet 4.6 as `first_cloud_tier`, Opus 4.8 as `high_reasoning`, Fable 5 as `sustained_long_context`, GPT-5.5 as the three specialists and as the §5.6 independent re-scorer) are superseded by the current §3 table, and a distinct role `high_reasoning_safeguard` (§3.8quater) now owns the independent re-scoring of §5.6. Historical audits, applied patches and authoring attributions keep the old names on purpose; they are not the current mapping.

**Document ownership (canonical):**
- §3 alone owns the logical ROLE → concrete model/version mapping, including fallback assignments and candidates.
- `F10_TOPOLOGIE_INFRA.md` owns physical/technical local deployment only: hardware, GGUF, quantization, hashes, runtime, endpoints, systemd and H3 measurements.
- All other sections and specs reference generic roles and resolve concrete assignments through §3.
- `local_executor` supplies local routing/scoring/execution and dialogue conduction; cloud tiers and specialists are selected under the rules below.
- CatBoost remains the dedicated business ML model for Vector ride scoring, outside LLM routing.

Patch 2E implementation note (preserved):
- backend adapter: `app/services/ai/providers/qwen.py`;
- default mode: dry-run, no network call;
- smoke endpoint: `POST /api/ai/qwen/smoke`;
- output: structured JSON contracts only;
- canonical writes: forbidden from local router-scorer output without backend/user validation.

Patch 2F implementation note (preserved):
- n8n dry-run workflow file: `ops/n8n/workflows/wr_interactive_start_qwen_dry_run.json`;
- n8n calls the backend internal local router-scorer dry-run bridge, not the local model endpoint directly;
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
2. local_executor if the task is within its reach
3. first_cloud_tier if the task exceeds the local model
4. high_reasoning if deep analysis / strategy is required
5. sustained_long_context only if the task is long AND complex AND high-stakes

### 1.6 User-triggered AI calls

No expensive AI cloud call is triggered without explicit user action or a deterministic schedule the user has already opted into.

Pattern:

```text
Suggest → Inform → User decides → Execute
```

Exceptions allowed without user action:
- local_executor calls (free, fast, no impact)
- Vision OCR inside a flow the user explicitly initiated
- Pure deterministic backend calculations (no AI)

---

## 2. The Two Distinct "Scorings"

A recurring source of confusion. Imperium has **two unrelated scoring systems**. They must never be conflated.

### 2.1 Task-difficulty scoring (`/200`)

A routing score that decides **which model** handles a task. Computed by the local router-scorer (`local_executor`). Detailed in §5. This is the "scoring" referenced everywhere else in this document unless stated otherwise.

### 2.2 Vector ride scoring (CatBoost)

A **business ML model** specific to Vector. It scores ride opportunities (accept/skip, value estimation) from historical ride data. It is a CatBoost classifier (gradient boosting), chosen over a fine-tuned LLM because the task is tabular with many categorical features (zone, time slot, ride type, etc.), which CatBoost handles natively and cheaply.

This has **nothing to do** with model routing. It does not call the cloud. It is trained offline on Vector history and served as a dedicated prediction endpoint. It is documented here only to prevent confusion with the routing score.

---

## 3. Component Roles

This section is the single owner of the logical role → concrete model → version mapping. Other docs name the ROLE. F10 documents physical/technical local deployment and may name deployed or candidate artifacts, without owning the logical mapping. This documentation update does not modify `ai_role_models` or activate any product call; `qwen_enabled=False` and `real_ai_enabled=False` remain unchanged.

> **Note (passe 0, 2026-07-15) : incarnation code = table `ai_role_models`**
> (migration 20260715_0039, doc 73 PART B "identifier-not-call"). Le code
> résout un rôle (`local_executor`, `first_cloud_tier`, `high_reasoning`,
> `sustained_long_context`, `health_specialist`, `finance_specialist`,
> `web_fresh_data`, `embedding_service`, `ocr_service`,
> `transcription_service`) via cette table ; ce doc reste le propriétaire de
> la LISTE des rôles et de leurs critères. Changer un modèle = nouvelle
> version de ligne, jamais un edit de code (DV-6 : plus aucune référence
> concrète en dur).

> **Note (2026-09-17) : rôle `high_reasoning_safeguard` (§3.8quater).** Rôle
> documentaire ajouté à la liste ci-dessus ; il n'a pas encore de ligne dans
> `ai_role_models`. L'ajouter sera une nouvelle ligne/migration hors de cette
> passe, jamais un edit de code. Aucun flag ni paramètre runtime n'est modifié
> par cette mise à jour.

Current logical mapping (summary; the subsections below are normative):

| Role | Current model | API identifier | Subsection |
|---|---|---|---|
| `local_executor` | `Qwen3.6-27B-Q6_K` (unchanged) | local, see F10 §5-ter | §3.3 |
| `first_cloud_tier` | Claude Sonnet 5 | `claude-sonnet-5` | §3.5 |
| `high_reasoning` | Claude Opus 5 | `claude-opus-5` | §3.6 |
| `sustained_long_context` | Claude Fable 5.1 | `claude-fable-5-1` | §3.7 |
| `health_specialist` | GPT-5.6 Sol | — | §3.8 |
| `finance_specialist` | GPT-5.6 Sol | — | §3.8bis |
| `web_fresh_data` | GPT-5.6 Sol | — | §3.8ter |
| `high_reasoning_safeguard` | GPT-6 Astra | `gpt-6-astra` | §3.8quater |
| `ocr_service` | not yet adopted | — | §3.9 |
| `transcription_service` | faster-whisper large-v3 (planned) | — | §3.10 |
| `embedding_service` | qwen3-embedding:8b (planned) | — | §3.12 |

### 3.1 Imperium Backend

- Current model: backend service
- Role: authentication, authorization, payload validation, idempotency, canonical storage, internal endpoints, permission enforcement, event journaling, exposing reliable snapshots to AI, and **maintaining shared dialogue context** (see §6).
- Selection criteria: source-of-truth authority, not model quality.
- Use for: canonical writes, reliable snapshots, backend validation, and final storage decisions.

The backend can call n8n or receive results from n8n, but it remains the final judge of what gets stored.

### 3.2 n8n

- Current model: workflow engine
- Role: run scheduled workflows, listen to webhooks, call external APIs, receive files/audio/images, chain multiple AI models, run long background workflows, return structured results to the backend.
- Selection criteria: orchestration and temporal execution, not authority over truth.
- Use for: scheduled workflows, multi-step chains, external integrations, file/audio/image intake, and background job execution.

V1 rule:

```text
Simple CRUD, simple read, simple deterministic compute → backend
Multi-step, temporal, AI, external, email, file, audio, image → n8n
```

### 3.3 Fast local model — `local_executor`

- Current model: `Qwen3.6-27B-Q6_K`
- Role: `local_executor` — local router / scorer / executor / dialogue conductor.
- Selection criteria: local, nothing leaves the machine.
- Use for: classify incoming tasks; compute the dynamic difficulty score `/200`; pick the recommended model; detect ambiguities; decide whether to escalate; emit strict JSON routing output; conduct dialogue sessions (Weekly Review, Imperium chatbot) as the default speaker, escalating per §6.
- Deployment: see [F10 §5-ter](F10_TOPOLOGIE_INFRA.md#5-ter-local-executor--phase-h) for the active local runtime, hardware and technical validation. Backend access is internal only; no public model port is exposed.

The local executor also executes local tasks directly: light reformulation, classification, short summary, categorization, simple extraction, non-critical micro-decisions, and the routine turns of a dialogue.

The local router-scorer is the router, not the sovereign. It must not be treated as absolute truth; canonical writes always pass through backend/user validation.

**Working hypothesis (assumed, validated empirically):** the local model is capable of routing and conducting dialogue reliably. If real-world use shows it is not, that is an ecosystem-wide problem (not a Weekly-Review-specific one), and the answer is a hardware decision (see F10 for hardware evolution), not a local patch.

### 3.4 Gemma

Optional, not deployed by default. Future possible uses: A/B challenger to the `local_executor` model on a sample of decisions, local fallback when the `local_executor` model is unavailable, specialized micro-model if benchmarks prove it useful. Do not run the `local_executor` model + Gemma in parallel by default in V1.

### 3.5 First cloud tier — `first_cloud_tier`

- Current model: Claude Sonnet 5 (API identifier `claude-sonnet-5`). Previous assignment: Sonnet 4.6 (superseded 2026-09-17).
- Role: balanced cloud model, the first step above the local model.
- Selection criteria: balanced cost/quality.
- Use for: structured reasoning, daily reorganization (multi-factor), logic correction, medium-complexity code, decisions with moderate context, document transformation, detailed financial advice (Vault Level 2), weekly nutrition / recovery plans, structuring projects (project module).

Note: candidates MiniMax M3 / Qwen3.7 Max may later challenge this tier on cost/quality — to be tested on real tasks before any swap.

### 3.6 High reasoning model — `high_reasoning`

- Current model: Claude Opus 5 (API identifier `claude-opus-5`). Previous assignment: Opus 4.8 (superseded 2026-09-17).
- Role: premium strategic model, the default when real depth is required.
- Selection criteria: depth of reasoning.
- Use for: deep analysis, complex priority arbitration, long-term strategy, multi-domain synthesis, serious architectural debugging, high-consequence decisions, strategic reflection in the project module; final orchestrator of the §5.6 critical tier (it may consult `sustained_long_context` and `high_reasoning_safeguard`, and it alone produces the final answer when the anti-loop breaker fires).

Opus must never be called by reflex.

### 3.7 Sustained long-context model — `sustained_long_context`

- Current model: Claude Fable 5.1 (API identifier `claude-fable-5-1`). Availability fallback: Gemini Pro 3.1. Provider-native content-safeguard redirection target: Claude Opus 5 (the `high_reasoning` model). Previous assignment: Fable 5 (superseded 2026-09-17).
- Role: the most capable long-context model (Mythos-class, above Opus). Reserved strictly for tasks that are **simultaneously long, complex, and high-stakes/durable**. On a moderately complex task, Opus and Fable perform comparably, so paying for Fable is only justified when task length and complexity let its endurance advantage materialize.
- Selection criteria: endurance on long tasks.
- Use for: the Weekly Review 4-week re-planning step (see §6) and other durable, long-horizon reasoning tasks where sustained coherence matters more than raw intelligence; consultable by `high_reasoning` in §5.6 Step 2.

#### Availability status

**RESOLVED (2026-07-01, doc patched 2026-07-15).** Fable 5 was suspended by a US
export-control directive on 2026-06-17 and access was restored on 2026-07-01
(CONCLUSIONS_test_papier, PHASE_0 note). The role was served by Fable 5 again
from that date; since 2026-09-17 it is served by Fable 5.1. Gemini Pro 3.1 stays
the availability fallback and Opus (the `high_reasoning` model) the target of the
provider-native content safeguard. The plan-generation cascade is Fable-based again.

Built-in safeguard (Anthropic-native mechanism): for high-risk topics (cybersecurity, biology, chemistry, distillation), Fable 5.1 blocks and redirects to Opus 5 on its own, model-side. This means the "sensitivity" routing criterion is partially handled model-side for Fable. This native redirection is **not** the Imperium role `high_reasoning_safeguard` (§3.8quater): the former is a provider content filter that swaps the answering model; the latter is an independent contradictory verifier that Imperium's routing calls on purpose (§5.6).

Two distinct fallbacks must not be conflated:
(a) Content safeguard — Fable redirects sensitive topics on its own, model-side, to Opus 5 (above). Anthropic mechanism, not an Imperium role.
(b) Total model unavailability — handled routing-side, see §7.8. When Fable 5.1 is
    unreachable, the routing layer must substitute Gemini Pro 3.1 wherever a static
    rule forced Fable.

Canonical V1 use: the Weekly Review 4-week re-planning step (see §6). It is the one recurring task that reliably meets the three conditions. Everything else escalates to Opus or below.

### 3.8 Health specialist — `health_specialist`

- Current model: GPT-5.6 Sol. Previous assignment: GPT-5.5 (superseded 2026-09-17).
- Role: specialist for health/Pulse.
- Selection criteria: GDPR/EU guarantees for health data.
- Use for: health/ Pulse (weight/nutrition/recovery calculations and medical-feed analysis). `health_specialist` is the de facto "owner" of Pulse reasoning.

### 3.8bis Finance specialist — `finance_specialist`

- Current model: GPT-5.6 Sol. Previous assignment: GPT-5.5 (superseded 2026-09-17).
- Role: specialist for financial reasoning over Vault data, fresh data / web research, verification of financial figures, and complex multimodal analysis.
- Selection criteria: hallucination resistance — must show reasoning and flag uncertainty, never invent a figure.
- Use for: financial reasoning over Vault data (budgets, cash-flow, financial pressure, project cost reasoning), invoked by the chatbot and the Weekly Review, not by the Vault app; fresh data / web research / multimodal analysis; generating actionable rules from sensitive or complex documents.

This reasoning lives in the Imperium brain and is invoked by the chatbot and the Weekly Review — NOT by the Vault app, which only displays/captures. In finance, `finance_specialist` must show its reasoning and flag uncertainty rather than invent a figure (hallucination resistance is the governing criterion); a confidently invented number is worse than useless.

### 3.8ter Web / fresh-data specialist — `web_fresh_data`

- Current model: GPT-5.6 Sol. Previous assignment: GPT-5.5 (superseded 2026-09-17).
- Role: real-time / fresh information specialist.
- Selection criteria: must have web access / real-time retrieval.
- Use for: fresh data (recent events around Paris for Vector — concerts, salons, sports), web retrieval, market/price comparison, regulatory research, real-time verification of facts against current sources.

Former overloads of this subsection, removed on 2026-09-17: (a) the independent critical re-scoring of §5.6 was attached here only because the same concrete model served it; it is now the dedicated role `high_reasoning_safeguard` (§3.8quater). (b) The generic last-resort plan generation of doc 52 §8.5 is a plan *generation* task, not a verification; it is now expressed under `sustained_long_context` (§3.7, durable long-horizon generator), see doc 52 §8.5. `web_fresh_data` keeps only its fresh-data function.

Note: the three specialist roles (health 3.8, finance 3.8bis, web/fresh-data 3.8ter) are all served by the same concrete model today (GPT-5.6 Sol), but they remain distinct roles, each with its own selection criterion and may be served by a different model in the future. `high_reasoning_safeguard` (§3.8quater) is deliberately served by a different model (GPT-6 Astra) so that the verifier is not the specialist being verified.

### 3.8quater High-reasoning safeguard — `high_reasoning_safeguard`

- Current model: GPT-6 Astra (API identifier `gpt-6-astra`). Role created 2026-09-17.
- Role: independent contradictory verification / anti-hallucination check of high-stakes reasoning. It is an Imperium routing role, invoked on purpose by the backend; it is **not** the Anthropic-native content safeguard of Fable described in §3.7, which is a provider-side redirection and never becomes this role.
- Selection criteria: provider independence from `high_reasoning` and `sustained_long_context` (Anthropic) and from the specialist model it may have to contradict; hallucination resistance; no stake in the execution it verifies (it never produces the final answer of the task it checks).
- Use for: §5.6 Step 1 independent re-scoring of a local score ≥180 (re-score → reroute below 180, authorise Step 2 at ≥180); consultation by `high_reasoning` during §5.6 Step 2 as a contradictory reviewer; any spec that explicitly requires a second, independent judgment on a high-stakes reasoning (contradictory review of a conclusion, not a domain calculation).
- Not for: domain second reads that belong to a specialist (health "never alone on the critical" rule → `health_specialist`; financial figure checks → `finance_specialist`), the WR input/output audits produced by `high_reasoning` (doc 47 §5), generation fallbacks, or fresh-data checks (`web_fresh_data`).
- Not yet in `ai_role_models` (see the note at the top of §3). No activation: `qwen_enabled=False` and `real_ai_enabled=False` are unchanged.

### 3.9 OCR service — vision / OCR — `ocr_service`

- Current model: not yet adopted; local candidates are PaddleOCR-VL-1.6 or GLM-OCR (not active).
- Existing cloud fallback assignment from doc 37: Gemini with structured output (2.5+); no exact version is adopted here. It is only eligible when the local engine is unavailable and the privacy gate permits it. A Flash variant was a future candidate, not an adopted real-time path.
- Role: `ocr_service` — vision / OCR.
- Selection criteria: reliable structured visual extraction; physical feasibility and deployment are documented in F10.
- Use for: receipts, screenshots, scanned documents, images, structured visual extraction.

### 3.10 Transcription service — audio — `transcription_service`

- Current model: faster-whisper large-v3, planned and not active.
- Role: `transcription_service` — audio transcription.
- Selection criteria: French/Arabic transcription quality, including dialectal Arabic; physical deployment is documented in F10.
- Use for: voice notes, long dictation, audio uploaded to Imperium, text preparation before AI routing. For short driving commands (<10s), Android Speech API is preferred to save resources.

### 3.11 CatBoost — Vector ride scoring

See §2.2. Dedicated business ML model, not part of routing.

### 3.12 Embedding service — `embedding_service`

- Current model: qwen3-embedding:8b, planned local V1 default; not active.
- Role: semantic embeddings, with the 1024-dimensional contract defined in doc 38.
- Selection criteria: privacy-first local processing and consistent embeddings across a corpus.
- Cloud fallback candidates already documented in doc 38: text-embedding-3-small (OpenAI) or voyage-3-lite, only if local hosting is impossible and the privacy gate permits it.
- Physical deployment and readiness belong to F10; a mapping is not an activation.

---

## 4. n8n Trigger Architecture

n8n responds to six trigger families.

### 4.1 Time trigger
Examples: every Monday prepare the week; Tuesday 20:00 backend-only WR availability flag; every morning events around Paris (Vector); weekly events research (web_fresh_data); nightly maintenance/backup/cleanup. Cron → backend snapshot/signal → often no AI yet → status flagged in DB → user banner on next refresh.

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

| Score `/200` | Recommended role | Function |
|---:|---|---|
| 0–99 | local_executor | Execute locally |
| 100–139 | first_cloud_tier | Balanced reasoning |
| 140–179 | high_reasoning | Deep analysis |
| 180–200 | **Critical mechanic (see below)** | Critical analysis |

#### Critical tier (180–200) — two-step mechanic

A score ≥180/200 is extremely rare (it requires a task that is simultaneously very complex, long, ambiguous, high-consequence and sensitive). When it happens, the gravity of the decision justifies the cost — we do not pinch pennies on Anthropic credits at this level. But a high score from the local router-scorer may itself be a hallucination, so it must be independently verified before the heavy machinery runs.

**Step 1 — Independent re-scoring (anti-hallucination) by `high_reasoning_safeguard`.**
The 180+ score was produced by the local router-scorer, which can hallucinate an inflated score. Before engaging the heavy machinery, **`high_reasoning_safeguard` (§3.8quater)** (a different provider, hallucination-resistant, and with no stake in the execution) receives the situation + the scoring table (§5.2/5.3) and **re-evaluates the score**.
- If `high_reasoning_safeguard` lowers it below 180 → re-route to the band actually warranted (140–179 high_reasoning, etc.). No heavy orchestration.
- If `high_reasoning_safeguard` confirms ≥180 → Step 2 is authorised.

(Until 2026-09-17 this re-scoring was attributed to the §3.8ter model; the function is unchanged, only its role owner is.)

**Step 2 — Free orchestration by high_reasoning (gravity confirmed).**
high_reasoning remains the final orchestrator. It is given the capability profiles of sustained_long_context and high_reasoning_safeguard and is left to **direct freely**: handle it itself, consult either of them (sustained_long_context for long durable reasoning, high_reasoning_safeguard for a contradictory review), delegate, or combine. No cap on each model's depth of reasoning. At this gravity, cost is not a constraint.

**Anti-loop breaker (circuit breaker).**
The real failure mode at this tier is not a single weak model — it is models relaying to each other indefinitely (hollow back-and-forth, everyone "thinking" without converging). To prevent it without throttling intelligence:
- A counter bounds the number of **hand-offs between models** (≈3–4 relays max for one critical task).
- Each model may reason as deeply as it wants on its own turn (depth NOT capped).
- If the relay cap is reached without resolution → **high_reasoning must produce the final answer itself, with no further delegation.** The breaker cuts the hollow loop; it does not limit thinking depth.

(The hand-off counter is a design rule; its backend implementation is tracked in the backlog.)

**sustained_long_context is not reached by raw score alone.** It is engaged only when the three-fold condition (long AND complex AND high-stakes/durable) is met — in practice through a static rule (§7), e.g. the Weekly Review re-planning step. A high score routes to high_reasoning; sustained_long_context is a deliberate, rule-driven choice, never a reflex of the score.

### 5.7 Emergency Mode (user-triggered)

Emergency Mode is a **behavior modifier**, not a shortcut to the heaviest model. Urgency and difficulty are different dimensions: an emergency can be simple-but-urgent (needs a FAST answer — local/first_cloud_tier) or complex-and-grave (warrants high_reasoning, or the §5.6 critical mechanic with sustained_long_context). Forcing the heaviest model on every emergency would be counter-productive: high_reasoning/sustained_long_context reason deeply and are slower, while urgency often needs speed. The §5.2 "speed tolerance (inverted)" criterion already pushes urgent tasks toward the fast tier. So Emergency Mode raises priority and lifts the cost barrier, but lets normal scoring still pick the RIGHT model by the task's real nature.

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
  - simple + urgent → fast answer (local_executor / first_cloud_tier); no time wasted;
  - complex + grave → escalate (high_reasoning, or the §5.6 critical mechanic with sustained_long_context if the re-scored gravity reaches ≥180).
- Emergency Mode **never forces** the heaviest model. It lifts the cost barrier and sets priority; speed stays king when the task is simple. This is consistent with the inverted speed-tolerance criterion (§5.2): urgency biases toward fast execution, not toward maximal depth.

**Exit**
- Emergency Mode applies to the current emergency handling and ends when resolved (or when the user cancels it). It is not a persistent global state.

**Cross-references**
- §5.2 — speed tolerance (inverted): urgency biases toward fast tiers; Emergency Mode honors this rather than overriding it.
- §5.6 — if the emergency is genuinely critical (re-scored ≥180), the critical mechanic (`high_reasoning_safeguard` re-score → high_reasoning orchestration → anti-loop breaker) applies as usual; Emergency Mode simply guarantees priority and no cost retention.
- §1.6 — Emergency Mode is an explicit, user-confirmed action, so it satisfies the "no expensive cloud call without explicit user action" rule by design.

### 5.8 Automatic escalation

Even with a low score, escalate if:
- local router-scorer confidence is low
- the request is very ambiguous
- consequences are high
- the output will become a durable rule
- the task touches money, health, law, critical administrative, or security
- the local router-scorer detects missing essential context

```text
If confidence < 0.65                     → escalate one tier
If consequences ≥ 8 and ambiguity ≥ 7    → minimum first_cloud_tier
If consequences ≥ 9 and sensitivity ≥ 8  → high_reasoning or the domain specialist (health_specialist / finance_specialist / web_fresh_data, depending on specialty)
```

### 5.9 Automatic downgrade

Downgrade to a cheaper model if: the score is low, the request is repetitive, a similar response already exists in memory, the task is pure formatting, the output has no consequences, or latency must be very short.

---

## 6. Dialogue Contexts (Weekly Review & Imperium Chatbot)

Imperium has two conversational contexts that share **one dialogue engine**: a single conductor model holds the thread, consults specialists behind the scenes, and escalates per turn. The engine is the same; only the framing differs.

### 6.1 Shared dialogue engine

- **Conductor = local_executor (default).** It speaks to the user, keeps tone and continuity, and handles routine turns locally (acknowledgements, simple follow-up questions).
- **Shared context held by the backend.** Each model call receives the full relevant session dossier (summary, dialogue, data); each response is appended back. Switching models mid-dialogue does not break the thread, because the thread lives in the backend, not in any model's memory.
- **Specialists consulted behind the scenes.** When a turn touches a domain (health → health_specialist, etc.), the conductor consults the specialist and **restitutes the answer itself**, so the user always talks to a single interlocutor. This is the "family doctor + specialists" pattern, not a "committee".
- **Per-turn escalation.** Each turn is scored: a simple turn stays on local_executor; a demanding turn escalates to high_reasoning (or sustained_long_context only under the §7 rule). Escalation is mixed: hard rules at key moments, dynamic scoring for the rest.

### 6.2 Domain routing vs dialogue

- **Isolated tasks** (OCR, web research, a one-shot analysis) → routed directly to the domain specialist (§7). No conductor.
- **Dialogue** (Weekly Review, chatbot) → single conductor, specialists consulted in the background.

### 6.3 Weekly Review (WR)

The WR is the "fuel in the AI's tank": a weekly **decision review**, not a chatbot. Its purpose is to examine what changed during the week and whether the right decisions were made — the AI gives its view, the user gives theirs, and they discuss the week's decisions.

Trigger: Tuesday 20:00 banner → user clicks → session starts.

**Phase 1 — Summary by exception.** A model reviews the week focusing on **changes/deviations**, not a full recital. Stable areas are skimmed ("religion: regular, nothing to flag"). Changes are reported with **precise figures** ("food budget +5%, minor" vs "+13%, worth attention"), crossing domains ("you skipped your mission 3 days for fatigue, yet your health constants were good — why?"). The backend pre-computes the figures, so this phase reasons over prepared data → high_reasoning if it escalates; lighter if data is well prepared.

**Phase 2 — Relevant questions + conversation.** The hard part: detecting the real issues, asking pertinent (non-generic) questions, sustaining a dialogue where the user can push back ("why did you insist on the prefecture when I had three months and the garage was more urgent?"). Conductor = local_executor (local conductor) by default; demanding turns escalate to high_reasoning. Domain turns consult specialists (health → health_specialist) in the background.

**Phase 3 — Rolling 4-week re-planning.** All of the above is summarized, vectorized, and integrated with prior plans, vectorized history, and the **calendar**, to refine the next 4 weeks. The WR is a rolling window: 4 weeks behind, 4 weeks ahead. If a prior plan still holds, it is left unchanged; otherwise the AI re-plans, and may adjust every week ahead of it. **This step is forced to sustained_long_context by a hard rule** (§7.8): it is long, complex, and high-stakes/durable — the one recurring task meeting all three conditions. It "lays the rails" the local executor then follows day to day, so the heavy model is not called by reflex during the week.

**Projects in the WR.** Projects are seen **only as decisions to evaluate** — e.g. the timing of activating a project versus the user's state ("you activated this heavy, slow-return project in a week you were exhausted; wouldn't a higher-energy month suit it better?"). The WR does not manage, plan, or break down projects. That belongs to the project module (§8).

**Calendar.** Fully integrated in V1 (decision: the planning value outweighs the connection overhead). n8n syncs an external calendar (§4.4), the backend stores an exploitable snapshot, the AI reads it in Phase 3.

### 6.4 Imperium chatbot

Same engine as the WR, different framing: **open, on-demand dialogue** with no imposed phases. The user drives the topic (often project advice). Escalation is purely score-driven per turn (no forced re-planning step). Conductor = local_executor, specialists in the background, context held by the backend.

---

## 7. Static Pre-Scoring Rules (Overrides)

Some tasks bypass dynamic scoring entirely. They have a forced model or a forced path.

Note — Emergency Mode (§5.7) is NOT a static rule: it raises priority and lifts the cost barrier, but never forces a model. Model choice stays nature-driven via normal scoring (see §5.7).

### 7.1 Vision / OCR
```text
Image, receipt, screenshot, scanned document → OCR service
```
After OCR service extraction, the local router-scorer may score the next step.

### 7.2 Audio
```text
Raw audio → transcription service
```
After transcription, the local router-scorer scores the follow-up.

### 7.3 Fresh data / web
```text
Need for current information → web_fresh_data + web search
```
Examples: events within 30 km of Paris, recent regulation, current prices, news, public disruptions not already in a connected API.

### 7.4 Health / Pulse
```text
Health calculation or medical analysis → health_specialist
```
health_specialist owns Pulse reasoning (weight/nutrition/recovery, medical-feed). The local model must not produce a critical health analysis alone.

### 7.5 Finance / Vault reasoning
```text
Financial analysis or advice (not mere display) → finance_specialist
```
Triggered when the brain reasons over financial data — typically inside the Imperium chatbot or the Weekly Review (budget/cash-flow analysis, financial pressure, project cost evaluation). NOT triggered by Vault simply displaying a balance or by deterministic backend computation (those stay app/backend). The distinction is **display vs reasoning**: showing a number is not analysing it. The local model must not produce a critical financial analysis alone. finance_specialist must surface its reasoning and signal uncertainty rather than fabricate values.

### 7.6 Morning "AI advice" cards
The advice module present on each app dashboard is routed by app, by required depth — not as a special case but via normal domain routing:
```text
Imperium → fine advice  → brain (high_reasoning / scoring by depth)
Pulse    → fine advice  → health_specialist (health, §7.4)
Vault    → fine advice  → finance_specialist (finance, §7.5)
Vector   → plain advice → local_executor (no finesse needed)
Path     → reformulation only → local_executor
```
**Path religious advice — hard rule.** For the religious advice, the AI does NOT generate and does NOT freely select content. local_executor picks one entry at random from a DEDICATED, closed list of pre-written, validated advice (`base_advice`, to be created in the Path docs) and only reformulates/presents it. This base is DISTINCT from the Dars knowledge base (doc 50): the AI must never extract or interpret religious content from the Dars (or any broad corpus) at will. On religion, the AI presents pre-validated content; it never invents or cherry-picks. (`base_advice` does not exist yet — see backlog.)

### 7.7 Vector ride scoring
```text
Ride opportunity scoring → CatBoost (business ML, not an LLM, not the cloud)
```

### 7.8 Weekly Review re-planning
```text
WR Phase 3 (rolling 4-week re-planning) → sustained_long_context (forced)
```
The one recurring task meeting long + complex + high-stakes/durable. sustained_long_context's own provider-native content safeguard (§3.7, an Anthropic mechanism) reroutes high-risk topics to the high_reasoning model; this is not the Imperium role `high_reasoning_safeguard` (§3.8quater), which the WR re-planning step does not invoke.

Unavailability fallback: use the availability fallback assigned in §3.7 when the sustained_long_context model is unreachable. This is distinct from its native content safeguard, which redirects high-risk topics to the high_reasoning model. Current availability and the dated suspension/restoration history are owned solely by §3.7.

### 7.9 Deterministic backend decision
```text
CRUD, DB read, health check, dashboard snapshot, deterministic summary → Backend only
```

---

## 8. Project Module

Distinct from temporal planning (the daily/weekly/monthly cadence the WR handles). A project is an objective with steps, dependencies, and progress, on its own timeline.

Two AI facets, both routed by the general scoring (no dedicated expert model):
- **Structure** (break into steps, track dependencies/progress, adjust the project plan) → local_executor or first_cloud_tier by complexity.
- **Reflect** (advise on strategy, arbitrate decisions) → high_reasoning, and sustained_long_context only if a given project decision is long + complex + high-stakes/durable.

Link to the WR is limited to §6.3: the WR evaluates the **timing** of project activation as one of the week's decisions. No mechanical step→mission automation in V1 (that is a V2 candidate). The project module also surfaces in the Imperium chatbot for open advice.

---

## 9. Summary Hierarchy

```text
local_executor         → local router/scorer, executor and dialogue conductor (~60% of tasks)
first_cloud_tier       → balanced reasoning
high_reasoning         → deep analysis and strategy
sustained_long_context → long + complex + high-stakes/durable; WR re-planning
health_specialist      → health/Pulse reasoning
finance_specialist     → financial reasoning over Vault data
web_fresh_data         → fresh information and web research
high_reasoning_safeguard → independent contradictory verification (§5.6 re-scoring; consulted by high_reasoning)
embedding_service     → semantic embeddings
ocr_service           → vision / OCR
transcription_service → audio
CatBoost               → Vector ride scoring (business ML, outside LLM routing)
```

Assignments, fallback models and future candidates are owned solely by §3.

Guiding principle throughout: deterministic on the critical path, dynamic for the rest; local by default; expensive cloud only when value justifies it. Local routing and dialogue capability are validated empirically, with hardware (see F10) as the answer if that hypothesis fails.
