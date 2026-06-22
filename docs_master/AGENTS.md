# AGENTS.md

> **Read this file before writing any code in this project.**

## Mission

You are working on a personal AI-powered ecosystem for one user.

This is **not** a SaaS, **not** a generic productivity app.

It is a personal command system to manage life, work, finances, health, worship, and VTC activity.

The system must be faithful to the user's vision, not generic best practices.

---

## Core Architecture

```text
Backend (FastAPI + PostgreSQL) = canonical truth
n8n                            = orchestration only
Qwen 2.5 7B local              = router/scorer
Cloud models                   = specialists, called only when justified
pgvector                       = semantic memory, never canonical truth
Apps (Android, V2)             = display + collect, never decide
```

---

## Application Ecosystem

| App | Role | Non-negotiable |
|---|---|---|
| **Imperium** | Command center, missions, replan, mentoring chat | One active mission at a time |
| **Vector** | VTC assistant, zone scoring, events anticipation | Never automate platform-breaking actions |
| **The Vault** | Finance radar, income, expenses, weekly profit | Observes and reports, never decides alone |
| **Pulse** | Sport, nutrition, health tracking | Stay simple and practical |
| **The Path** | Worship, prayer, fasting, sadaqa | Connects with Vault for sadaqa calculation |

---

## AI Model Strategy

```text
~90% calls → Qwen local (free)
~5%        → Haiku 4.5 (light cloud)
~3%        → Sonnet 4.6 (balanced)
~1.5%      → Opus 4.7 (deep, WR)
~0.5%      → GPT-5.5 (web + medical)
~0.3%      → the OCR service (vision)
the transcription service for audio
```

**Routing rule:** Qwen scores tasks `/200`. Static overrides for vision/audio/web/medical/WR.

**See:** `30_AI_ROUTING_AND_SCORING_POLICY.md` for full rules.

---

## Non-Negotiable Rules

1. **PostgreSQL is the only canonical writer** — apps, n8n, AI never write directly
2. **Backend defines the playing field** — Qwen plays within it
3. **No AI cloud call without user trigger** — except local Qwen and OCR in user-initiated flows
4. **Idempotency-Key on every POST** that mutates state
5. **HMAC + timestamp on every internal callback** — never send the shared secret as a header
6. **AI results need user validation** before becoming canonical actions
7. **One active mission only** at any time
8. **Validated WR is canonical, AI drafts are not**
9. **WR insights feed pgvector with temporal decay, never as hard rules**
10. **Append-only events** for audit trail

**See:** `08_NON_NEGOTIABLE_RULES.md` for the full list.

---

## When To Use What

```text
Simple CRUD, deterministic compute → backend, no AI, no n8n
Multi-step / async / external      → n8n
Routing / classification / score   → Qwen local
Receipt / screenshot / image       → the OCR service (static override)
Audio                              → the transcription service
Web fresh data                     → GPT-5.5 + web
Medical reports                    → GPT-5.5
WR analysis                        → Opus 4.7
Quick advice with context          → Haiku 4.5
Day reorganization (multi-factor)  → Sonnet 4.6
Mentoring chat                     → Opus 4.7
```

---

## Development Priority

1. Documentation
2. Database schema and migrations
3. AI tables (`ai_tasks`, `ai_results`, `ai_result_validations`)
4. Backend services
5. n8n workflows
6. Qwen integration
7. App frontends
8. Visual polish (last)

---

## Documentation Map

```text
00_VISION_GLOBALE.md                  - project vision
01_SIGNAL_VARIABLES_DICTIONARY.md     - signal vocabulary
04_MVP_BACKEND_CONTRACTS.md           - API contracts V1
05_DATABASE_SCHEMA.md                 - DB schema
06_N8N_WORKFLOWS.md                   - n8n workflows overview
07_ANDROID_APP_RESPONSIBILITIES.md    - app responsibilities
08_NON_NEGOTIABLE_RULES.md            - hard rules
09_PGVECTOR_MEMORY_POLICY.md          - vector memory rules
10_RAW_MEDIA_RETENTION_POLICY.md      - GDPR compliance
11_FINANCIAL_PRESSURE_FORMULA.md      - Vault pressure score
12_DAILY_OBJECTIVE_PERIOD_LOGIC.md    - Imperium daily objective
13_VECTOR_MVP_PHASE_DECISION.md       - Vector phase scope
14_OFFLINE_CLIENT_AUTHORITY.md        - offline UI authority
15_SERVICE_ARCHITECTURE_MAP.md        - service map V1/V2/V3
16_AI_BACKEND_LAYER_OVERVIEW.md       - AI layer architecture
17–23                                 - ops, deployment, security
24–29                                 - per-feature workflows
30_AI_ROUTING_AND_SCORING_POLICY.md   - AI routing rules
31_AI_TASKS_AND_RESULTS_CONTRACT.md   - AI tables + contracts
32_WR_INTERACTIVE_WORKFLOW.md         - WR interactive flow
33_VECTOR_LOGIC_DETAIL.md             - Vector logic details
34_PULSE_MEDICAL_FEED_AI.md           - Pulse medical analysis
38_VECTORIZATION_PIPELINE.md          - WR → pgvector pipeline
```

---

## Coding Standards

- Type hints on every Python function
- `Decimal` for money (never `float`)
- UTC timezone-aware datetimes
- UUID primary keys, generated by PostgreSQL
- One file per domain in `services/`
- Routes thin, services thick
- Custom exceptions per service module
- Docstrings for non-obvious behavior

---

## Before Writing Any Code

1. Read `08_NON_NEGOTIABLE_RULES.md`
2. Read the doc(s) covering the feature you're implementing
3. Check `15_SERVICE_ARCHITECTURE_MAP.md` for V1 scope
4. Check existing similar code in `backend/app/services/` for patterns
5. Check `04_MVP_BACKEND_CONTRACTS.md` for API conventions
6. Use `Idempotency-Key` on every state-mutating POST
7. Never write to PostgreSQL from anywhere except backend services

---

## Final Instruction

This is a personal operating system, not a normal app.

Faithfulness to the user's vision is more important than technical elegance.

When in doubt: ask, don't assume.

---

**Last updated:** 2026-04-28
