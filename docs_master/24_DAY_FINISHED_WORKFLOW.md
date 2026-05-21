# 24 - Day Finished Workflow

## Purpose

Implement the first real Imperium backend workflow:

```text
day.finished
```

This is the backend contract for the Imperium "Finish Day" button.

## Principles

- Backend is source of truth.
- Android apps are interfaces only.
- PostgreSQL stores canonical truth.
- `events` is append-only.
- n8n is not triggered in V1.
- No AI decision logic is implemented yet.
- Reasons are stored as user-provided signals without judgment or reinterpretation.

## Endpoint

```http
POST /api/imperium/day/finish
```

Authentication:

```text
JWT required
```

Idempotency:

```http
Idempotency-Key: <unique_key>
```

The backend derives `user_id` from JWT.
Client-supplied `user_id` is not accepted.

## Payload

```json
{
  "local_date": "2026-04-26",
  "timezone": "Europe/Paris",
  "day_status": "partial",
  "energy_level": 6,
  "fatigue_level": 7,
  "sleep_quality": 5,
  "stress_level": 4,
  "mood": "calm",
  "main_win": "Finished the backend security work",
  "main_problem": "Low sleep",
  "missed_items": [
    {
      "label": "Workout",
      "category": "pulse",
      "reason": "Fatigue",
      "user_reported_signal": "slept late"
    }
  ],
  "completed_items": [
    {
      "label": "VTC session",
      "category": "vector"
    }
  ],
  "notes": "Plain user note.",
  "free_text": "Raw daily reflection."
}
```

Allowed `day_status`:

```text
completed
partial
failed
```

Score fields are optional integers from 1 to 10.

## Storage

Table:

```text
imperium_day_reviews
```

Columns:

- `id`
- `user_id`
- `local_date`
- `timezone`
- `day_status`
- `energy_level`
- `fatigue_level`
- `sleep_quality`
- `stress_level`
- `mood`
- `main_win`
- `main_problem`
- `completed_items` JSONB
- `missed_items` JSONB
- `notes`
- `free_text`
- `source_event_id`
- `created_at`
- `updated_at`

Constraint:

```text
unique(user_id, local_date)
```

## Event

The backend appends one canonical event:

```text
event_type = day.finished
source_app = imperium
privacy_level = medium
```

The event payload contains the sanitized request payload.

## Idempotency

First request with a new `Idempotency-Key`:

```text
201 Created
```

Retry with the same key and same payload:

```text
200 OK
```

The same stored response is returned.
No duplicate day review is created.
No duplicate event is created.

Same key with different payload:

```text
409 Conflict
```

## Second Finish For Same Date

V1 behavior:

```text
Reject with 409 Conflict
```

Reason:

The system should not silently rewrite day-review truth until an explicit correction workflow exists.

Future option:

Implement an explicit corrective endpoint that appends:

```text
day.finished.updated
```

and stores a correction reason.

## Read Latest Review

```http
GET /api/imperium/day/latest
```

Returns the latest day review for the authenticated user.

## Intentionally Not Implemented Yet

- AI analysis
- automatic replanning
- priority rewriting
- mission generation
- notifications
- n8n workflow trigger
- weekly review generation
- judgment of whether reasons are valid
- hardcoded life priority logic

## Future AI Analysis

Later AI workflows may analyze recurring patterns such as:

- repeated fatigue
- repeated missed workout
- sleep quality patterns
- stress patterns
- recurring blockers

But V1 only stores the user's reported signals.
It does not interpret or judge them.
