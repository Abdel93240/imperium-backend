# AGENTS.md

## Mission

You are working on a personal AI-powered application ecosystem for one user.

This is **not** a SaaS.

This is **not** a generic productivity app.

This is a **personal command system** designed to help the user manage life, work, finances, health, worship, and VTC activity.

The system must be **faithful to the user's vision**.

---

## Core Principle

The apps are **not** the brain.

The central backend, n8n workflows, PostgreSQL database, vector memory, and AI router form the brain.

Apps are interfaces:

- they display
- they collect data
- they trigger actions
- they show recommendations

They do not independently invent strategy.

---

## Application Ecosystem

The ecosystem contains these apps:

### Imperium

Personal command center.

**Main purpose:**

- decide what the user should do now
- manage daily missions
- replan the day
- track failures and reasons
- orchestrate the user's priorities

**Non-negotiable rule:**

> There must be only one active mission at a time.

---

### Vector

VTC assistant.

**Main purpose:**

- help the user decide where to go
- analyze VTC sessions
- track revenue objectives
- use transport disruptions, events, traffic, and zone history
- give driving tips

**Important:**

> Vector must not automate illegal or platform-breaking Bolt actions.
>
> It should advise, analyze, and optimize decisions.

---

### The Vault

Finance radar.

**Main purpose:**

- track income
- track expenses
- calculate weekly profit
- show financial reality
- feed sadaqa calculation into The Path

**Non-negotiable rule:**

> The Vault observes and reports.
>
> It does not make financial decisions alone.

---

### Pulse

Sport, nutrition, and health tracking.

**Main purpose:**

- track meals
- track food stock
- track workouts
- track body progress
- support weight loss and visible abs goal

> Pulse must stay simple and practical.

---

### The Path

Worship, prayer, fasting, sadaqa, and spiritual routines.

**Main purpose:**

- prayer tracking
- fasting tracking
- sadaqa tracking
- spiritual reminders
- link sadaqa to weekly profit from The Vault

---

## Backend Target Architecture

Preferred architecture:

- Android apps as frontends
- Hostinger VPS
- n8n as orchestration engine
- PostgreSQL for structured data
- pgvector for vector memory
- API/webhook layer between apps and backend
- AI router to decide which model handles each task

---

## AI Model Strategy

Use different models for different jobs.

### Local Router / Scorer

**Qwen 2.5 7B Instruct** is the official V1 local router and scorer.

Qwen V1 should be used for:

- routing
- classification
- scoring task difficulty
- short summaries
- adaptive clarification questions
- low-cost daily interactions
- privacy-sensitive lightweight tasks

Patch 2E provides the backend adapter foundation for Qwen. It defaults to dry-run mode, returns structured JSON contracts, and must not create canonical actions without backend/user validation.

**Gemma local** is only a future optional challenger or fallback, not the default V1 router.

---

### Speech-to-Text

Use **Whisper** or **faster-whisper** for:

- voice notes
- commands while driving
- audio transcription

> Do not rely only on the main LLM for transcription.

---

### Gemini

Use **Gemini** for:

- image understanding
- OCR
- screenshots
- Bolt screenshots
- document/image extraction

---

### GPT or Claude

Use **GPT** or **Claude** for:

- complex reasoning
- architecture
- weekly analysis
- strategic decisions
- difficult debugging
- deep planning

---

## Development Priority

> Do not start with UI polish.

**Priority order:**

1. Documentation
2. Signal variables dictionary
3. Model strategy
4. Database schema
5. API contracts
6. n8n workflow map
7. Backend skeleton
8. Android UI
9. Animations and visual polish

---

## Documentation Rule

Before writing code, always read the relevant documentation files.

**Expected documentation folder:**

```text
/docs_master
  00_VISION_GLOBALE.md
  01_SIGNAL_VARIABLES_DICTIONARY.md
  02_AI_ROUTING_POLICY.md
  03_MODEL_STRATEGY.md
  04_MVP_BACKEND_CONTRACTS.md
  05_DATABASE_SCHEMA.md
  06_N8N_WORKFLOWS.md
  07_ANDROID_APP_RESPONSIBILITIES.md
  08_NON_NEGOTIABLE_RULES.md
  30_AI_ROUTING_AND_SCORING_POLICY.md
  31_AI_TASKS_AND_RESULTS_CONTRACT.md
  32_WR_INTERACTIVE_WORKFLOW.md
  45_N8N_RESPONSIBILITY_MATRIX.md
```

If documentation is missing, **create or propose it before coding**.

---

## Non-Negotiable Product Rules

- Imperium is the command center.
- Only one active mission can exist at a time.
- The apps collect and display; the backend brain decides.
- n8n orchestrates workflows.
- PostgreSQL stores structured data.
- pgvector stores semantic memory.
- The Vault tracks reality, not dreams.
- Vector advises VTC positioning but must not violate platform rules.
- Pulse must remain simple and usable while the user is busy.
- The Path must connect with The Vault for sadaqa.
- Every user action should become useful data.
- Avoid overengineering the V1.
- Backend first, UI second.
- Do not create generic app logic when personal rules exist.
- Always preserve the user's real-life constraints.

---

## User Constraints

The user is a **VTC driver** and may work very long days.

**Important constraints:**

- often driving
- needs voice input
- needs fast decisions
- limited attention while working
- wants strict guidance
- wants minimal friction
- wants weekly financial clarity
- wants discipline and execution
- prefers practical systems over theoretical dashboards

---

## MVP Focus

The first usable version should prioritize:

- Imperium missions
- The Vault income/expense tracking
- n8n workflow execution
- PostgreSQL schema
- AI routing
- voice input pipeline
- basic Vector advice
- simple Pulse tracking
- simple The Path tracking

> Do not build unnecessary advanced features before the core system works.

---

## Coding Standards

When coding:

- keep files clear and modular
- prefer simple architecture over clever architecture
- document important decisions
- create typed data contracts where possible
- avoid hidden magic
- make debugging easy
- create logs for workflows and AI decisions
- separate business rules from UI
- separate model routing from app logic

---

## Before Making Major Changes

Always explain:

1. **What** you are changing
2. **Why** it matters
3. **Which app/module** is affected
4. **Which data tables or API contracts** are affected
5. **Whether it impacts the MVP scope**

---

## Final Instruction

Do not treat this project like a normal app.

Treat it like a **personal operating system**.

> Faithfulness to the user's vision is more important than technical elegance.
