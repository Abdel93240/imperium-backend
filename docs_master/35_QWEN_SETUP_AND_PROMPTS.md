# 35 — Qwen Setup and Prompts

Qwen is the official local AI router for Imperium V1.

It handles routing, triage, classification, adaptive questions, lightweight reasoning, and low-cost internal decisions.

The n8n AI Agent is not part of the official V1 architecture. n8n orchestrates; Qwen reasons.

## 1. Official Deployment Choice

Qwen runs through Ollama in Docker on the same Docker network as n8n and imperium-api.

Official V1 network rule:

```text
n8n -> ollama/qwen -> imperium-api
```

All services must be reachable by Docker service name inside the shared network.

Recommended internal Ollama URL:

```text
http://ollama:11434
```

## 2. Docker Compose Service Contract

Example service definition to integrate into the deployment compose stack or a dedicated compose file attached to the same network:

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    container_name: imperium-ollama
    restart: unless-stopped
    volumes:
      - ollama_data:/root/.ollama
    networks:
      - n8n-network
    ports:
      - "127.0.0.1:11434:11434"

volumes:
  ollama_data:

networks:
  n8n-network:
    external: true
    name: n8n-postgresql_n8n-network
```

After container start:

```bash
docker exec -it imperium-ollama ollama pull qwen3:32b
```

If another exact Qwen tag is selected later, document the tag and keep one official production tag in the deployment notes.

## 3. n8n Call Pattern

n8n calls Qwen by HTTP:

```text
POST http://ollama:11434/api/chat
```

Payload shape:

```json
{
  "model": "qwen3:32b",
  "stream": false,
  "messages": [
    {"role": "system", "content": "You are Imperium's local AI router. Return strict JSON only."},
    {"role": "user", "content": "...task envelope..."}
  ]
}
```

Qwen output must be strict JSON. n8n must validate it before calling the backend.

## 4. Qwen Responsibilities

Qwen may decide:

- task type;
- difficulty score;
- whether clarification is needed;
- which model should handle the task;
- whether the task is safe to process locally;
- whether to escalate to Sonnet, Opus, Fable, GPT, Gemini Vision, Whisper, or deterministic backend logic.

Qwen must not:

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
  "recommended_model": "claude_opus",
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
0–99    -> Qwen 32B local
100–139 -> Claude Sonnet 4.6
140–179 -> Claude Opus 4.8
180–200 -> critical mechanic (doc 30 §5.6 / Patch 30-B)
```

Qwen must not override hard-coded special routing rules such as medical files, image OCR, audio transcription, or compliance-sensitive workflows.

## 7. System Prompt

```text
You are Qwen, the local AI router for Imperium.

You do not own the database.
You do not make canonical decisions.
You classify tasks, score difficulty, ask for clarification when needed, and decide whether a task can stay local or must be escalated.

Return strict JSON only.
Do not include chain-of-thought.
Do not invent facts.
Respect the task contracts.
Use anonymized summaries for cloud models when possible.
```

## 8. Health Check

From the VPS:

```bash
docker exec imperium-ollama ollama list
```

From n8n network context:

```bash
curl -sS http://ollama:11434/api/tags
```

A successful response proves n8n can reach Ollama/Qwen internally.

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
