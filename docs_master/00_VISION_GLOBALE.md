# 00 - Vision Globale

## Purpose

This ecosystem is a personal operating system for one user.

It is not:
- a SaaS
- a generic productivity app
- a social app
- a multi-user platform
- a collection of disconnected trackers

It is a set of focused interfaces connected to one central intelligent system. The user should feel one thing above all:

> I know what reality is, what matters now, and what I should do next.

The apps must stay simple. The intelligence lives in the backend, the orchestration layer, the rules, the memory, and the AI routing system.

## One-User Philosophy

The system is built for one person, not for account teams, organizations, customers, admins, or tenants.

This has direct product consequences:
- no SaaS billing concepts
- no organization or workspace model in the MVP
- no role-based multi-user permissions in the MVP
- no social sharing by default
- no generic onboarding for a mass-market audience
- no feature that dilutes the user's personal execution flow

The backend can still use `user_id` for technical consistency, but product decisions must assume a single owner.

Authentication follows this one-user philosophy:
- one canonical user record
- email + password access
- master access key / secret phrase access
- registered trusted devices only
- device-bound refresh tokens
- revocable devices

This is not a SaaS auth system.

## Core Architecture

The ecosystem has three main layers.

### 1. Client Layer

The client layer contains the user-facing apps:
- Imperium
- The Vault
- Vector
- Pulse
- The Path

Each app is an interface. It collects data, displays state, triggers actions, and receives recommendations.

Apps do not own final intelligence.

### 2. Orchestration Layer

The orchestration layer is the central brain.

It contains:
- REST API and webhooks
- n8n workflow orchestration
- business rules
- signal engine
- AI routing
- push notification routing
- feedback and learning loops

n8n is the workflow conductor. It coordinates app events, model calls, deterministic rules, external feeds, storage, and responses back to the apps.

### 3. Data and Memory Layer

The data layer contains:
- PostgreSQL for structured truth
- pgvector for semantic memory
- file/media storage for uploaded documents, audio, screenshots, receipts, and scans

PostgreSQL is the source of truth for structured objects such as missions, transactions, sessions, upcoming expenses, workouts, prayer events, and feedback.

pgvector stores semantic memory such as document chunks, recurring user patterns, learning summaries, strategy notes, and contextual memories.

## Central Brain Principle

The central brain is not a single app.

It is the combination of:
- n8n orchestration
- deterministic business rules
- signal engine
- PostgreSQL state
- pgvector memory
- AI model routing
- feedback learning

The central brain:
- analyzes context
- routes requests
- applies rules
- selects models
- explains decisions
- stores learning signals
- updates planning confidence

The apps:
- submit events
- display current state
- ask for decisions
- expose fast user actions
- collect explicit confirmation

## Non-Negotiable Product Principles

1. Imperium is the command center.
2. Apps are interfaces, not the brain.
3. n8n orchestrates workflows.
4. PostgreSQL stores structured data.
5. pgvector stores semantic memory.
6. The local model handles simple, private, fast tasks.
7. The transcription service handles audio transcription.
8. The OCR service handles OCR, images, receipts, screenshots, and visual extraction.
9. The first cloud tier, the high reasoning model, or a domain specialist handles complex reasoning, strategy, synthesis, and mentoring.
10. Only one active mission can exist at a time.
11. The Vault reports financial reality.
12. Vector advises VTC decisions but must not automate Bolt or violate platform rules.
13. Pulse stays simple, practical, and biologically useful.
14. The Path connects worship, prayer, fasting, Quran, adhkar, ghusl, and sadaqa to the rest of the system.
15. User confirmation matters. The system must not silently pretend something is done.
16. Failure is information. It must feed learning, not punishment.

## Role of Each App

### Imperium - Command Center

Imperium is the visible command center of the personal operating system.

It answers:

> What should I do right now?

Imperium is responsible for:
- current mission display
- day session structure
- mission completion and failure flow
- replanning
- project and routine structure
- priority order
- weekly strategic review
- AI advice display
- widget-level instant action

Imperium is not a todo list. It is not a generic productivity app. It must not become a finance app, fitness tracker, note app, CRM, or journal.

Imperium orchestrates the meaning of signals from the rest of the ecosystem. It does not replace the specialist apps.

### The Vault - Financial Reality

The Vault is the financial radar.

It answers:

> What is the real financial situation right now?

The Vault is responsible for:
- gains
- expenses
- wallets
- upcoming expenses
- pressure score
- daily financial targets
- recurring obligations
- financial explanations

The Vault must stay clear and practical.

MVP boundaries:
- no bank sync
- no automatic external account connection
- no wallet transfers in V1
- fixed wallet types in V1: `CB`, `Cash`, `Crypto`
- every transaction is an event, not a daily summary
- daily financial targets are advisory, not coercive

The Vault provides financial pressure and cash reality to Imperium, Vector, Pulse, and The Path.

### Vector - Strategic VTC Copilot

Vector is the VTC field decision support layer.

It answers:

> Which VTC decision is strategically best right now?

Vector is responsible for:
- ride offer analysis
- destination mode strategy
- airport demand window estimation
- scheduled ride reasoning
- learned Google Maps time adjustment
- fuel strategy
- VTC session learning
- business rule evolution

Vector is not a GPS app.

Vector must never auto-click, auto-accept, auto-refuse, or automate Bolt. It may analyze a ride offer and display a recommendation, but the user remains responsible for the final action.

The real-time assistant flow is:

```text
Ride notification sound
-> screen capture
-> ride extraction
-> AI decision
-> halo display
-> user decides manually
```

Halo states:
- white: analysis in progress
- green: recommended ride
- red: bad ride

Destination mode is limited strategic ammunition, with a maximum of 6 per day. The decision question is not "is destination mode available?", but "is it worth spending now?"

### Pulse - Biological Layer

Pulse is the health, nutrition, workout, stock, and recovery layer.

It answers:

> What is realistic for my body today?

Pulse is responsible for:
- biological profile
- health score
- nutrition planning
- workout generation
- workout adaptation
- grocery list logic
- stock and expiration tracking
- batch cooking
- wearable data integration where available

Pulse must stay simple and practical. Missing wearable data must reduce confidence, not break the system.

Pulse sends biological constraints and practical missions to Imperium. It uses budget context from The Vault, location and field context from Vector, and religious timing constraints from The Path.

### The Path - Operational Islamic Discipline

The Path is the religious discipline layer.

It answers:

> What worship constraints and actions must shape the day?

The Path is responsible for:
- precise prayer timing
- mosque-aware prayer logic
- qibla direction
- ghusl state and missions
- fasting constraints
- Hijri/lunar calendar logic
- Quran continuation
- adhkar routines
- sadaqa discipline

The Path is not a religious content app. It is operational Islamic discipline.

Prayer anchors are non-negotiable. Imperium builds around them, never the opposite.

The Path sends constraints. Imperium decides execution order.

## Decision and Feedback Loop

The core loop is:

Terminology cascade:

```text
Projet (what the user wants to build: intrinsic per-app + explicit per-domain)
  → Objectif (the results needed for the project)
    → Mission (the precise tasks)

Routine = a recurring mission serving an objective/project.

Full definitions live in doc 44.
```

```text
Projects + Routines + Priorities + Weekly Reality Check
                    |
          System + AI arbitration
                    |
             Current Mission
                    |
              User Action
        Done / Not Done / Replan
                    |
          Feedback + Weekly Review
                    |
            System adapts
                    |
              Next Mission
```

The loop must remain clean. If this loop breaks, Imperium loses its value.

## Learning Philosophy

The system learns from:
- mission completion
- mission failure
- replanning
- weekly review answers
- priority changes
- project validation
- transaction patterns
- VTC ride decisions and outcomes
- bad recommendation feedback
- workout adaptation
- prayer, fasting, Quran, adhkar, and sadaqa completion
- user corrections

Learning must improve precision, trust, and local adaptation.

Learning must not become random rule drift or blind AI behavior. Business rules must be versioned, explainable, adjustable, and reversible.

## MVP Priorities

The MVP must create the backbone first.

### Priority 1 - Central contracts and event flow

Create a consistent backend contract for:
- app events
- AI routing requests
- workflow triggers
- storage writes
- app state reads
- feedback events

The apps must speak the same event language.

### Priority 2 - Imperium execution loop

Implement the minimum Imperium loop:
- one active mission
- day session start/end
- mission done
- mission not done with reason
- explicit replanning
- AI advice
- weekly review pending/completed state

This is the highest-value MVP surface.

### Priority 3 - The Vault reality engine

Implement:
- transactions
- fixed wallets
- upcoming expenses
- pressure score
- daily financial targets
- receipt OCR flow if image handling is ready

The Vault must provide financial truth to the rest of the system.

### Priority 4 - AI routing and memory

Implement:
- request classification
- local model routing for simple/private tasks
- OCR service routing for OCR/images/screenshots
- first cloud tier / high reasoning model / domain specialist routing for complex reasoning
- Transcription service routing for audio transcription
- routing decision logs
- feedback storage
- pgvector memory writes for approved summaries and documents

### Priority 5 - Vector guardrailed decision support

Implement:
- ride offer extraction pipeline
- recommendation display
- no auto-click boundary
- VTC session result logging
- destination mode remaining count
- fuel low trigger
- session learning events

### Priority 6 - The Path anchors

Implement:
- prayer anchors
- next prayer display
- ghusl required flow
- fasting constraints
- Quran continuation
- sadaqa target from real weekly profit

### Priority 7 - Pulse practical basics

Implement:
- biological profile
- health score with explanation and confidence
- workout generation/adaptation
- stock and grocery list basics
- nutrition plan basics

## Explicitly Out of Scope for MVP

- SaaS/multi-tenant architecture beyond technical `user_id`
- banking API sync
- automatic Bolt interaction
- automatic religious validation without user action
- complex social or sharing features
- generic chatbot-first product direction
- manual drag/drop day micromanagement
- full accounting system
- full GPS navigation app
- heavy wearable dependency
- religious content library unless required by operational workflow

## Open Decisions

The source documentation does not yet define the following:
- exact mobile framework
- exact model checkpoints and quantization
- exact n8n hosting topology
- exact file/media storage provider
- exact push notification provider
- exact pgvector embedding model
- exact retention policy for screenshots, audio, and receipts
- exact SLA targets by request type

Resolved implementation decisions:
- backend framework: FastAPI
- backend language: Python
- ORM: SQLAlchemy
- migration tool: Alembic
- database: PostgreSQL
- vector extension: pgvector
- canonical ID format: UUID

Until decided, these must remain `TODO` in implementation tasks.
