# 09 - pgvector Memory Policy

## Purpose

This document defines the operational memory policy for pgvector.

Core principle:

> pgvector is semantic memory, not canonical truth.

PostgreSQL structured tables are the source of truth.

pgvector exists to help the system remember useful patterns, preferences, summaries, and planning context. It must not become a hidden database of raw sensitive life data.

## ai_memories Schema

Canonical table: `ai_memories`

Columns:
- `memory_id` uuid primary key
- `user_id` foreign key to `users.id` not null
- `source_app` source_app not null
- `source_table` text nullable
- `source_id` text nullable
- `memory_type` memory_type not null
- `content` text not null
- `embedding` vector not null
- `embedding_model` text not null
- `created_at` timestamptz not null
- `updated_at` timestamptz not null
- `expires_at` timestamptz nullable
- `privacy_level` privacy_level not null
- `confidence` numeric nullable
- `is_active` boolean not null default true
- `supersedes_memory_id` uuid nullable
- `correction_reason` text nullable
- `metadata` jsonb nullable

Required fields:
- `memory_id`
- `user_id`
- `source_app`
- `memory_type`
- `content`
- `embedding`
- `embedding_model`
- `created_at`
- `updated_at`
- `privacy_level`
- `is_active`

Foreign keys:
- `user_id -> users.id`
- `supersedes_memory_id -> ai_memories.memory_id`

Recommended indexes:
- vector similarity index on `embedding`
- index on `(user_id, source_app, memory_type, is_active)`
- index on `(user_id, privacy_level, is_active)`
- index on `(source_table, source_id)`
- index on `expires_at`

Required retrieval filter:

```sql
is_active = true
AND (expires_at IS NULL OR expires_at > now())
AND superseded memory is excluded
```

Implementation note:
- `05_DATABASE_SCHEMA.md` may use `id` instead of `memory_id` for consistency. The contract-level meaning is the same: canonical memory identifier.

## Canonical memory_type Enum

Use these memory types:
- `user_preference`
- `behavioral_pattern`
- `failure_pattern`
- `planning_insight`
- `vtc_zone_pattern`
- `financial_pattern`
- `sport_adaptation`
- `worship_preference`
- `correction`
- `system_note`

Do not create new memory types casually. Additions must be documented here first.

## What Can Be Stored

Allowed in vector memory:
- recurring user preferences
- repeated failure patterns
- useful behavioral summaries
- long-term planning insights
- stable VTC heuristics
- repeated financial behavior summaries
- sport adaptation patterns
- non-sensitive summaries of worship routines if user allows

Allowed examples:
- "User tends to complete sport missions better before long VTC shifts."
- "Airport strategy performs better when CDG demand window is confirmed and distance is under user threshold."
- "User prefers direct strict Imperium advice instead of motivational text."
- "Weekly overspending often happens after late VTC sessions."
- "User prefers sadaqa reminders as weekly amount summaries, without private detail."

## Forbidden by Default

Do not store these in vector memory by default:
- raw financial transactions
- raw religious private states
- raw audio transcripts
- raw Bolt screenshots
- raw health-sensitive notes
- passwords
- tokens
- secrets
- exact location history unless explicitly needed and summarized

Forbidden examples:
- full receipt OCR text from every purchase
- exact Bolt screenshot text and image data
- "ghusl required at exact time X because..."
- raw voice note transcript containing private details
- GPS trail of a full VTC day
- access token, refresh token, master phrase, or webhook secret

If a sensitive detail is useful, summarize it and reduce precision.

Example:
- Bad: "User bought X at exact address Y at 22:14."
- Better: "Late-night food spending tends to increase after long VTC shifts."

## Memory Write Policy

Do not write memory for every event.

Events that may create memories:
- `mission.failed` repeated pattern
- `day.finished` summary
- `week.review.completed` or `weekly.review.completed`
- `transaction.pattern.detected`
- `vtc.zone.pattern.detected`
- `workout.adaptation.learned`
- `user.preference.updated`

Memory writes should happen only when:
- the pattern is repeated
- the user explicitly confirms it
- the event is strategically important
- the insight will improve future decisions
- the memory can be stored without raw sensitive detail

Do not create memory for:
- every transaction
- every prayer log
- every mission completion
- every location update
- every media extraction
- every AI response
- every n8n workflow run

Recommended write flow:

```text
event occurs
-> backend stores canonical PostgreSQL event/table changes
-> workflow detects possible memory-worthy pattern
-> privacy gate checks data category and user setting
-> memory summary is created
-> embedding is generated
-> ai_memories row is stored through backend API
```

## Memory Correction Policy

If the user corrects the AI:
- do not delete old memory immediately
- mark old memory as inactive
- create corrected memory
- link corrected memory using `supersedes_memory_id`
- store `correction_reason`

Required behavior:
- inactive memory must not be retrieved
- superseded memory must not be retrieved
- corrected memory should be preferred in future retrieval
- correction events should be stored in PostgreSQL

Example:

```text
Old memory:
"User avoids Orly at night."

User correction:
"No, Orly is good at night only on weekends."

Action:
- mark old memory inactive
- create corrected memory:
  "User considers Orly useful at night on weekends, not as a general rule."
- set supersedes_memory_id to old memory
- correction_reason = "user corrected overly broad VTC heuristic"
```

## Memory Deletion Policy

User must be able to delete or deactivate memory.

Deletion modes:
- soft deactivate
- hard delete if requested
- expire automatically if temporary

### Soft deactivate

Use when:
- memory is wrong
- memory is outdated
- user wants it ignored but audit may remain

Behavior:
- set `is_active = false`
- keep row
- exclude from retrieval

### Hard delete

Use when:
- user explicitly requests deletion
- sensitive memory should not remain
- legal/privacy cleanup is required

Behavior:
- remove row and embedding
- ensure it cannot be retrieved
- keep only minimal deletion audit if needed and privacy-safe

### Automatic expiration

Use when:
- memory is temporary
- context is short-lived
- the pattern should not influence long-term planning

Behavior:
- set `expires_at`
- retrieval excludes expired memory

## Retrieval Policy

Memory retrieval must be scoped by:
- `source_app`
- `memory_type`
- `privacy_level`
- recency
- confidence
- current workflow

Use:
- top-k limits
- similarity threshold
- privacy filters
- active/non-expired filters

Default retrieval constraints:
- retrieve only `is_active = true`
- exclude expired memory
- exclude superseded memory
- retrieve only memory types relevant to the workflow
- retrieve only privacy levels allowed by the workflow and user setting
- prefer higher confidence and recent durable patterns

Recommended default values:
- top-k: TODO
- similarity threshold: TODO
- minimum confidence: TODO
- recency weighting: TODO

These values must be benchmarked and tuned later.

## Retrieval Examples by Workflow

### Imperium planning

Imperium planning should retrieve:
- priority preferences
- repeated mission failure patterns
- energy/sleep adaptation patterns
- project planning patterns
- user preference for strict advice style

It should not retrieve:
- raw transaction text
- unrelated VTC zone memories
- private worship details unless needed and allowed
- exact location history

### Vector strategy

Vector strategy should retrieve:
- stable VTC zone patterns
- repeated successful positioning heuristics
- bad recommendation corrections
- learned ETA/route reality summaries

It should not retrieve:
- private worship details
- raw health notes
- raw financial transaction text

### Vault explanations

Vault explanations should retrieve:
- repeated financial behavior summaries
- known recurring overspending patterns
- user preference for financial explanation style

It should not retrieve:
- raw religious states
- raw GPS history
- raw Bolt screenshots

### Pulse adaptation

Pulse adaptation should retrieve:
- sport adaptation patterns
- repeated fatigue-related failures
- known user preferences around workout timing

It should not retrieve:
- raw transaction details unless summarized as budget pressure
- unrelated VTC zone memories

### The Path reminders

The Path may retrieve:
- non-sensitive worship reminder preferences if user allows
- routine consistency summaries
- sadaqa reminder preference

It must not retrieve:
- raw religious private states
- inferred ghusl data
- private worship completion details unless explicitly stored by user action and needed

## Decision Safety Rule

For any decision affecting:
- finance
- health
- worship
- VTC work
- active missions

The system must combine:
- current PostgreSQL truth
- relevant pgvector memory

Never decide from pgvector alone.

Examples:
- A mission recommendation must check current `missions`, `day_sessions`, priorities, prayer anchors, and relevant memory.
- A Vault explanation must check current transactions/summaries, not only financial pattern memory.
- A Vector recommendation must check current ride/session context, not only past zone memory.
- A Pulse workout must check current body profile and today context, not only old adaptation patterns.
- The Path must use current prayer/fasting/worship records, not memory alone.

## Privacy Gate for Memory

Before writing sensitive information into vector memory:
- check `privacy_level`
- check user settings
- check data category
- summarize instead of storing raw details
- avoid external embedding provider for high/very_high privacy unless explicitly allowed

Privacy behavior:
- low/medium: memory allowed if useful
- high: summarize and minimize; local embedding preferred
- very_high: do not store by default unless explicitly allowed and strongly useful

Forbidden secrets:
- passwords
- refresh tokens
- access tokens
- master secret phrase
- webhook secrets
- provider API keys

## Anti-Pollution Rule

Do not store nonsense reasons as strong memory.

If user gives an illogical, impulsive, contradictory, or one-off reason:
- store it as low confidence if it must be stored
- do not use it strongly for future decisions
- do not treat it as a durable pattern unless repeated
- mark confidence accordingly

Example:
- User says once: "I failed sport because Mercury is bad today."
- Memory behavior: do not create durable sport pattern.
- If stored at all, store as low-confidence note linked to that event.

The system should learn truth, not noise.

## Memory Lifecycle

### Temporary memory

Purpose:
- short-lived context
- temporary situation awareness

Examples:
- "User is unusually tired today."
- "This week has exceptional admin pressure."

Behavior:
- set `expires_at`
- lower retrieval priority as it ages

### Durable memory

Purpose:
- stable user preference or long-term planning insight

Examples:
- "User prefers strict direct advice."
- "User wants sadaqa reminders in weekly financial terms."

Behavior:
- no `expires_at` unless user changes preference
- high confidence only after confirmation or repetition

### Recurring pattern memory

Purpose:
- repeated behavior pattern

Examples:
- "Sport missions fail more often after late VTC sessions."
- "Late-night food spending increases after long work shifts."

Behavior:
- confidence increases with repeated evidence
- can be superseded by later correction

### Mission duration estimation (recurring-pattern application)

RÈGLE — Durée estimée d'une mission (mission_estimated_duration)

Principe directeur. La PRIORITÉ d'une mission est un jugement de valeur de
l'utilisateur (l'IA ne la choisit pas). La DURÉE est une estimation empirique d'un
fait : l'IA a le droit de l'estimer et de l'auto-corriger. Estimer un fait
corrigible ne viole pas "l'IA ne décide pas librement de ce qui structure".

1. Jamais demandée mission par mission.
   Le nombre de missions par projet rend la saisie manuelle ingérable. L'utilisateur
   PEUT surcharger ponctuellement une durée, mais ce n'est jamais exigé.

2. Capture du réel.
   Chaque exécution de mission enregistre le temps réellement passé (infra de mesure
   déjà présente, cf. télémétrie doc 43). Ces durées réelles alimentent
   l'apprentissage.

3. Estimation par similarité vectorielle de LIBELLÉ.
   Durée estimée = médiane des durées réelles des missions au libellé
   vectoriellement proche. Ex. "écrire un mail" ≈ "rédiger mail client" → même base
   de temps. Ce n'est PAS une moyenne par catégorie de domaine : c'est de la
   similarité de libellé.

4. Démarrage à froid (historique vide).
   Tant qu'aucun voisin proche n'existe, l'IA pose une estimation "à sa sauce"
   marquée NON CONFIRMÉE. Elle se corrige semaine après semaine à mesure que la
   vectorisation se remplit, et devient de plus en plus précise.

5. Conséquence sur la planification.
   Une durée NON CONFIRMÉE ou absente n'est jamais calée au créneau serré : le
   planificateur la traite en bloc souple, sans inventer un chiffre dur.

### Expired memory

Purpose:
- memory that should no longer affect decisions

Behavior:
- `expires_at < now()`
- excluded from retrieval

### Superseded memory

Purpose:
- memory replaced by correction or better understanding

Behavior:
- `is_active = false`
- linked by `supersedes_memory_id`
- excluded from retrieval

## Required Examples

### Failed sport mission due to fatigue

Source:
- repeated `mission.failed` events
- category: fatigue
- mission type: sport
- context: late VTC sessions

Memory:

```json
{
  "memory_type": "sport_adaptation",
  "source_app": "imperium",
  "source_table": "mission_history",
  "content": "Sport missions are more likely to fail when scheduled after long late VTC sessions. Prefer shorter recovery sessions or earlier sport blocks in that context.",
  "privacy_level": "high",
  "confidence": 0.74,
  "is_active": true
}
```

Use:
- Imperium replanning
- Pulse workout adaptation

Do not use alone:
- must check current day session, current fatigue, and current mission state.

### Repeated VTC zone success

Source:
- `vtc.zone.pattern.detected`
- VTC session outcomes
- zone observation summaries

Memory:

```json
{
  "memory_type": "vtc_zone_pattern",
  "source_app": "vector",
  "source_table": "vtc_zone_observations",
  "content": "Weekend night sessions around Orly have repeatedly produced acceptable hourly rate when demand window is confirmed and pickup distance remains below the user's threshold.",
  "privacy_level": "medium",
  "confidence": 0.81,
  "is_active": true
}
```

Use:
- Vector non-real-time strategy
- Imperium work mission timing

Do not store:
- raw Bolt screenshots
- exact full route history

### User correction of bad recommendation

Source:
- user feedback event
- `vector.bad.recommendation.flagged`

Old memory:

```json
{
  "memory_type": "vtc_zone_pattern",
  "content": "Avoid Orly at night.",
  "confidence": 0.62,
  "is_active": false
}
```

Corrected memory:

```json
{
  "memory_type": "correction",
  "content": "User corrected the Orly night rule: Orly can be good on weekend nights when demand window is valid. Do not apply a blanket avoid rule.",
  "confidence": 0.9,
  "is_active": true,
  "supersedes_memory_id": "old_memory_id",
  "correction_reason": "user corrected overly broad Vector recommendation"
}
```

Use:
- Vector strategy
- business rule refinement

### Financial overspending pattern

Source:
- transaction summaries
- `transaction.pattern.detected`

Memory:

```json
{
  "memory_type": "financial_pattern",
  "source_app": "vault",
  "source_table": "weekly_financial_summaries",
  "content": "Food spending tends to rise after late VTC shifts. Financial advice should account for fatigue-related convenience purchases without storing raw transaction details.",
  "privacy_level": "high",
  "confidence": 0.68,
  "is_active": true
}
```

Use:
- Vault explanation
- Imperium mission planning
- Pulse grocery/batch cooking planning

Do not store:
- exact merchant list
- exact addresses
- raw receipts

### Sadaqa preference without private religious detail

Source:
- user preference update
- sadaqa settings

Memory:

```json
{
  "memory_type": "worship_preference",
  "source_app": "path",
  "source_table": "sadaqa_records",
  "content": "User prefers sadaqa reminders as simple weekly amount summaries based on real profit, without exposing private religious details.",
  "privacy_level": "medium",
  "confidence": 0.9,
  "is_active": true
}
```

Use:
- The Path reminders
- Imperium weekly planning

Do not store:
- private intention details
- unrelated worship states

## Required Implementation Gates

Before using pgvector in production:
- define embedding model
- define embedding dimension
- define local vs external embedding provider policy
- define top-k default
- define similarity threshold
- define minimum confidence behavior
- define memory deletion UI/API
- define correction workflow
- define retrieval filters per workflow
