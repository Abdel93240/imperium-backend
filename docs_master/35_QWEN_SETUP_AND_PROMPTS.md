# 35 — Local Model Setup and Prompts

The local model is the official local AI router for Imperium V1.

It handles routing, triage, classification, adaptive questions, lightweight reasoning, and low-cost internal decisions.

The n8n AI Agent is not part of the official V1 architecture. n8n orchestrates; the local model reasons.

## 1. Deployment ownership

`local_executor` is mapped to its concrete model/version exclusively in doc 30 §3.3.
The active physical deployment, runtime, endpoint, service configuration and H3
measurements are owned by [F10 §5-ter](F10_TOPOLOGIE_INFRA.md#5-ter-local-executor--phase-h).

## 2. Deployment contract

Use F10 as the operational reference. The service is deployed and validated at the
infrastructure level; product AI remains disabled (`qwen_enabled=False`,
`real_ai_enabled=False`). Technical availability does not authorize product calls.

## 3. n8n call pattern

n8n orchestrates the task; the backend resolves `local_executor`, validates the
structured output and controls canonical writes. The preserved dry-run bridge and
callback contracts are documented in doc 31 (Patch 2E/2F). They do not redefine
the active physical deployment. No model port is public.

## 4. Local Model Responsibilities

The local model may decide:

- task type;
- difficulty score;
- whether clarification is needed;
- which model should handle the task;
- whether the task is safe to process locally;
- whether to escalate to the first cloud tier, the high reasoning model, the sustained long-context model, a domain specialist, the OCR service, the transcription service, or deterministic backend logic.

The local model must not:

- write directly to DB;
- make canonical decisions;
- bypass backend validation;
- invent missing facts;
- call cloud models with raw personal identifiers;
- use the n8n AI Agent as a hidden second brain.

## 5. Router Output Schema

```json
{
  "task_type": "weekly_report.analysis",
  "difficulty_score": 148,
  "recommended_model": "<concrete ID resolved for high_reasoning>",
  "needs_user_clarification": false,
  "clarification_question": null,
  "context_summary": "Short summary of the task.",
  "reasoning_summary": "Why this routing decision was made.",
  "privacy_level": "anonymized_summary",
  "confidence": 0.82
}
```

## 6. Difficulty Thresholds

Doc 30 is the source of truth.

```text
0–99    -> the local model
100–139 -> the first cloud tier
140–179 -> the high reasoning model
180–200 -> critical mechanic (doc 30 §5.6 / Patch 30-B)
```

The local model must not override hard-coded special routing rules such as medical files, image OCR, audio transcription, or compliance-sensitive workflows.

## 7. System Prompt

```text
You are the local model, Imperium's local AI router.

You do not own the database.
You do not make canonical decisions.
You classify tasks, score difficulty, ask for clarification when needed, and decide whether a task can stay local or must be escalated.

Return strict JSON only.
Do not include chain-of-thought.
Do not invent facts.
Respect the task contracts.
Use anonymized summaries for cloud models when possible.
```

## 8. Health check

Use the checks and measured results in F10 §5-ter. Distinguish service health from
backend wrapper validation: the H3.7 `GpuServiceUnreachable/skip` scenario remains
untested while `toolbox.llm` is absent. A health response alone does not activate AI.

## 9. Carrier Classification Prompt (doc 53)

```text
You are assessing whether a mission can be a "carrier" mission — a mission during
which the user can also do short annex missions.

The decisive factor is ENGAGEMENT, not physical effort:
- A physically heavy task can still be a carrier if it leaves a hand and some
  attention free (e.g. carrying a bag while making a call).
- A physically light task is NOT a carrier if it takes both hands or full
  attention (e.g. holding something in place, precise work).
- A long, engaging task CAN be a carrier if it has pauses/idle stretches where
  annex missions fit.

MISSION TO ASSESS:
Title: "{title}"
Description: "{description}"
Estimated duration: {duration_minutes} minutes
Mission type: "{mission_type}"

OUTPUT (strict JSON):
{
  "is_carrier_mission": <true | false>,
  "engagement_level": <"low" | "medium" | "high">,
  "has_exploitable_pauses": <true | false>,
  "confidence": <0.0 to 1.0>,
  "reasoning": "<one sentence in French>"
}
```
