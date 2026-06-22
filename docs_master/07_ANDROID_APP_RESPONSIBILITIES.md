# 07 - Android App Responsibilities

## Purpose

This document defines the responsibility boundary for each Android app.

Core principle:

> Apps are interfaces. They collect, display, trigger, and explain.

They do not become independent strategy engines.

The backend is the brain:
- API
- PostgreSQL
- n8n
- pgvector
- AI router
- backend rules

Android apps must be fast, reliable, and honest about what is confirmed, pending, cached, or failed.

## Shared Responsibilities For All Apps

All Android apps may:
- display current state
- collect structured input
- collect audio input
- collect screenshots and documents
- trigger backend workflows
- display recommendations
- show explanations
- show pending/synced/failed states
- cache last known state
- work safely in offline pending mode
- show backend-confirmed alerts
- show local reminders clearly marked as local when not backend-confirmed

All Android apps must not:
- silently rewrite priorities
- invent strategic truth
- replace backend validation
- become hidden autonomous systems
- finalize canonical records without backend confirmation
- hide sync failures
- present cached data as live truth
- perform AI routing authority locally
- write long-term memory locally
- bypass privacy gates

The interface can be smart in presentation, but the decision authority remains backend-side.

## Shared State Language

Apps must use clear sync and authority labels.

Required labels:
- `pending`
- `syncing`
- `synced`
- `failed`
- `conflict`
- `cached`
- `stale`

Examples:
- `Expense pending sync`
- `Mission completion synced`
- `Cached recommendation, not live`
- `Upload failed, retry available`

No fake success.

## Imperium Responsibilities

Imperium is the command center interface.

### Imperium Must Handle

Imperium must provide:
- current mission view
- finish mission action
- failure reason input
- start day button
- finish day button
- replan with AI request
- daily planning visibility
- daily objective visibility
- weekly objective visibility
- priority rules settings
- weekly review visibility
- current pressure/context summary
- explanation for backend recommendations
- pending/synced/failed state for user actions

### Imperium May Trigger

Imperium may trigger backend workflows for:
- `mission.created`
- `mission.completed`
- `mission.failed`
- `day.finished`
- `imperium.replan.requested`
- `week.review.requested`
- `priority.rules.updated`

The backend validates and stores canonical results.

### Imperium Does Not Decide Alone

Imperium does not decide alone:
- what the next mission officially is
- final weekly review conclusions
- final priority hierarchy changes
- official day closure
- official mission completion
- official mission failure state
- one-current-mission invariant

Only backend confirms.

Imperium may display suggestions and ask for user confirmation.

## Vector Responsibilities

Vector is the VTC decision assistant interface.

Vector must be manual-first in V1.

### Vector Must Handle

Vector must provide:
- start session
- objective reached
- manual revenue input
- manual expense input
- manual screenshot upload
- `Where should I go?` button
- driving tips display
- recommendation explanation
- session review visibility
- last drop zone input or confirmation
- cached recommendation display with timestamp
- pending/synced/failed state for session and uploads

### Vector May Trigger

Vector may trigger backend workflows for:
- `vector.session.started`
- `vector.session.completed`
- `vector.manual.revenue.recorded`
- `vector.manual.expense.recorded`
- `vector.screenshot.uploaded`
- `vector.zone.recommendation.requested`
- `vector.last_drop_zone.recorded`
- `vector.recommendation.feedback.recorded`

### Vector Does Not

Vector does not:
- auto-click Bolt
- auto-accept rides
- auto-refuse rides
- intercept illegally
- simulate user taps
- create fake GPS behavior
- abuse accessibility permissions
- bypass backend financial truth
- maintain duplicate wallet balances
- present stale recommendations as live
- turn screenshots into permanent memory by default

Vector is a decision assistant, not a rule-breaking bot.

## The Vault Responsibilities

The Vault is the financial reality interface.

### The Vault Must Handle

The Vault must provide:
- income declaration
- expense declaration
- wallet visibility
- financial pressure display
- weekly profit visibility
- obligations visibility
- upcoming required expenses visibility
- overdue expenses visibility
- manual correction input
- receipt/photo upload
- proof-required display where relevant
- pressure explanation
- pending/synced/failed financial action state

### The Vault May Trigger

The Vault may trigger backend workflows for:
- `transaction.created`
- `transaction.corrected`
- `expense.postponed`
- `expense.handled`
- `financial.snapshot.requested`
- `financial.pressure.recalculated`
- `sadaqa.recorded`

### The Vault Does Not

The Vault does not:
- invent money
- silently change accounting truth
- auto-sync unknown bank systems in MVP
- treat projected money as confirmed money
- store derived wallet balances as independent truth
- calculate sadaqa from financial pressure score
- hide uncertainty in extracted receipt data

Wallet balances are derived from opening balance plus transactions and adjustments.

## Pulse Responsibilities

Pulse is the health, body, food, and sport interface.

### Pulse Must Handle

Pulse must provide:
- body tracking input
- workout logging
- food stock logging
- meal logging
- supplement note input if needed
- progress visibility
- recommendation display
- recommendation explanation
- manual correction input
- pending/synced/failed state for logs

### Pulse May Trigger

Pulse may trigger backend workflows for:
- `workout.completed`
- `meal.logged`
- `food.stock.updated`
- `body.profile.snapshot.created`
- `pulse.recommendation.requested`
- `workout.adaptation.requested`

### Pulse Does Not

Pulse does not:
- act as medical authority
- infer health truth without confirmation
- diagnose conditions
- treat wearable data as absolute truth
- force workouts when recovery is strategically better
- override Imperium priorities without backend validation

Pulse recommendations are practical support, not medical rulings.

## The Path Responsibilities

The Path is the worship and spiritual discipline interface.

### The Path Must Handle

The Path must provide:
- prayer tracking
- fasting tracking
- sadaqa tracking
- worship reminders
- spiritual reminders
- prayer time display
- operational worship support
- manual correction input
- pending/synced/failed state for explicit logs

### The Path May Trigger

The Path may trigger backend workflows for:
- `prayer.logged`
- `fasting.logged`
- `sadaqa.recorded`
- `worship.routine.updated`
- `ghusl.required.activated`
- `path.reminder.requested`

### The Path Does Not

The Path does not:
- generate religious rulings
- infer worship completion automatically
- infer ghusl requirement
- infer fasting intention
- infer prayer completion
- infer Quran completion
- infer adhkar completion
- decide spiritual obligations without explicit user input
- send private religious data externally without privacy gate approval

The Path supports worship discipline. It does not replace explicit user intention or religious judgment.

## Voice Input Flow

Canonical flow:

```text
user speaks
-> app records audio
-> secure upload
-> backend transcription
-> AI routing
-> backend action
-> app receives result
```

App responsibilities:
- request microphone permission only when needed
- record audio
- store temporarily if offline
- upload securely
- show upload/transcription/action status
- allow retry or deletion when safe

Backend responsibilities:
- receive upload
- enforce auth and device trust
- apply privacy gate
- transcribe using the transcription service
- route AI if needed
- validate final action
- store event/result

Apps do not perform strategic interpretation alone.

## File Upload Flow

Examples:
- Bolt screenshots
- receipts
- documents
- contracts
- invoices
- health media
- private notes

Canonical flow:

```text
upload
-> extraction
-> confidence result
-> backend validation
-> structured data result
```

App responsibilities:
- collect file or image
- show upload state
- show processing state
- show confidence result
- show confirmation UI when needed
- show rejection reason
- support retry

Required display states:
- `uploaded`
- `processing`
- `confirmed`
- `rejected`
- `low_confidence`
- `failed`

Raw media retention follows `10_RAW_MEDIA_RETENTION_POLICY.md`.

## Notification Flow

Apps may receive or show:
- reminders
- mission alerts
- prayer alerts
- financial alerts
- review alerts
- sync failure alerts

Rules:
- notifications must reflect backend truth when they claim canonical status
- local reminders must be marked or designed as local reminders
- notifications must not imply backend validation if none exists
- notification taps should open the relevant app state
- actions from notifications must still sync through backend APIs

Examples:
- `Prayer reminder` is allowed from cached prayer time logic.
- `Mission completed` requires backend confirmation.
- `Expense saved` requires backend confirmation.
- `Expense pending sync` is allowed locally.

## Permissions

Apps should request only permissions that are truly needed.

Allowed when justified:
- microphone
- notifications
- storage/files
- camera
- location

Permission rules:
- request at the moment of need when possible
- explain why the permission matters
- avoid broad background access in MVP
- minimize sensitive data collection
- respect Android platform rules

Avoid:
- abusive accessibility usage
- unnecessary background permissions
- unstable Android hacks for MVP
- permissions used to bypass platform policies
- hidden monitoring behavior

## Sync Flow

Apps must show:
- `pending`
- `syncing`
- `synced`
- `failed`
- `conflict`

No fake success.

User must trust sync state.

Every mutating offline action must include:
- local event id
- idempotency key
- created_at
- source app
- device id
- sync status
- payload

Backend confirms canonical result.

If backend rejects or conflicts, the app must show the reason.

## Offline Mode

Apps may:
- queue
- cache
- display last known state
- create local drafts
- capture audio
- capture files
- show local reminders

Apps may not:
- decide strategic truth
- finalize missions
- finalize day closure
- finalize transactions
- finalize wallet balances
- finalize worship logs silently
- route AI requests independently
- create long-term memory

Backend remains authority.

Offline mode is continuity, not a second brain.

## No-Bolt-Automation Rule

Non-negotiable:

No:
- auto accept
- auto tap
- click simulation
- hidden accessibility abuse
- fake human interaction
- fake GPS behavior
- policy-breaking automation
- forced live screen capture in MVP
- notification interception dependency in MVP

Vector is a decision assistant, not a rule-breaking bot.

## UI Principle

The goal is:

```text
clarity + speed + reliability
```

Not:

```text
beautiful complexity
```

Especially while driving.

UI rules:
- show the current actionable state quickly
- make pending/synced/failed obvious
- keep driving surfaces minimal
- make recommendations explainable
- avoid hidden autonomy
- avoid excessive screens
- prioritize one-handed clarity where relevant

## Success Metric

Success means:
- better decisions
- less friction
- less wasted time
- more discipline
- better financial clarity
- better sync trust
- fewer ambiguous states

Success does not mean:
- more screens
- more animations
- more hidden automation
- more local intelligence
- more permissions

## Implementation Guardrail

Before implementing any Android feature, answer:
- Does this collect, display, trigger, or explain?
- Does it require backend confirmation?
- Is pending/synced/failed visible?
- Does it preserve privacy?
- Does it avoid local strategic authority?
- Does it follow the no-Bolt-automation rule?

If the feature makes the app an independent decision engine, it is outside the Android app responsibility boundary.
