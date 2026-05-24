# 51 - Future Calendar (V3)

> ⚠️ **V3 feature — full implementation, post-V1 and V2.**
> Personal calendar with structured events, deadlines, recurrences,
> and tight integration with the AI brain.

---

## Patch 7H — Minimal Foundation

Patch 7H adds only the backend storage foundation for calendar constraints.

Implemented scope:

- `imperium_calendar_events` table;
- event types limited to `event`, `deadline`, and `vacation`;
- manual create/list/delete backend APIs;
- ownership-scoped reads and deletes;
- `Idempotency-Key` required for event creation;
- date validation: `ends_at` must be null or greater than/equal to `starts_at`.

Strict non-goals for Patch 7H:

- no recurrence fields;
- no recurrence engine;
- no automatic replanning;
- no AI scheduling;
- no n8n AI Agent;
- no n8n database write;
- no pgvector write;
- no embeddings;
- no notifications;
- no Google/Apple/Samsung calendar sync;
- no mobile/frontend implementation.

This patch is **not** the full V3 calendar system described below. It only
creates a safe backend-owned table and API layer so future planning can consume
calendar constraints later without inventing storage under pressure.

---

## 1. Purpose

Provide the AI brain with knowledge of **future contexts** that should impact its decisions:

- The user is in Morocco from August 15-22 → no VTC missions
- Doctor appointment Tuesday 15h-16h → block that time slot
- Tax deadline May 15 noon → reserve preparation time before
- Weekly Dars course every Friday 19h-21h → recurring block

Without this feature, the AI plans every day as if nothing changed. With this feature, the AI's planning aligns with the user's real life.

---

## 2. Why V3 And Not Earlier

```text
V1 — Daily plan and missions exist but no future awareness.
V2 — Smart fuel, WR sections, refinements.
V3 — Calendar feature lands as a structured layer that
     informs the AI's decisions for upcoming events.

This requires:
- Mature mission lifecycle (V1)
- Stable replan mechanism (V1, doc 43 §3)
- WR feedback loop (V1, doc 32)
- Hook system in Imperium (V1, doc 43 §3.1)

Implementing this earlier would risk integration debt with 
core systems still in flux.
```

---

## 3. Design Principles

```text
PRINCIPLE 1 — A dedicated tab, no native calendar integration
  Native calendars (Google, Samsung, Apple) are not used.
  All events live in the system's own calendar.
  Full control, structured fields, no permission drama.

PRINCIPLE 2 — Manual entry = absolute commitment
  If the user took the time to add an event manually,
  it's important. The AI treats it as binding.

PRINCIPLE 3 — Optional but encouraged precisions
  Every event has a "précisions" text field always visible.
  Empty is fine for simple events. Encouraged for complex ones.

PRINCIPLE 4 — The 7-day threshold
  Events more than 7 days away: stored, no AI action.
  Events within 7 days: trigger AI replan immediately.

PRINCIPLE 5 — Deadlines are special
  Regular events block time slots.
  Deadlines reserve time BEFORE for preparation.

PRINCIPLE 6 — No retroactivity
  The calendar is for the future.
  Past adjustments happen via WR conversation, not via
  retroactive event creation.

PRINCIPLE 7 — The calendar is alive
  WR can interrogate and update events.
  The AI can ask "is your car still in repair?"
  User answers update the underlying event data.
```

---

## 4. Event Types

```text
TYPE 1 — EVENT (default)
  A scheduled commitment that BLOCKS a time slot.
  Examples: 
    - Médecin 15h-16h
    - Mariage cousin 14h-19h
    - Cours Dars vendredi 19h-21h
  
  AI behavior:
    - Time slot is unavailable
    - Add travel time before/after based on location
    - Cannot schedule other missions in this window

TYPE 2 — DEADLINE
  Something must be DONE BY a date/time.
  Does NOT block the deadline date itself.
  Reserves preparation time before the deadline.
  Examples:
    - Dossier impôts deadline 15 mai 12h
    - Rendre projet client deadline 30 avril 18h
  
  AI behavior:
    - Estimates: when is the best moment before the deadline?
    - Reserves a calculated time slot
    - If user fails to do it: standard mission-failed flow
      (replan handles it normally per doc 43 §5)
    - On D-Day: still creates urgent mission if not done

TYPE 3 — VACANCES / VOYAGE (multi-day blocked period)
  An entire period where the user is away or unavailable
  for normal activities.
  Examples:
    - Vacances Maroc 15-22 août
    - Voyage Bordeaux 5-7 mai
  
  AI behavior:
    - Pauses VTC missions during the period
    - Path: prayers calculated for the new location if specified
    - Pulse: workout adapt or pause based on context
    - Vault: anticipates revenue gap

TYPE 4 — PÉRIODE BLOQUÉE (multi-day non-vacation)
  Period where some activity is impossible.
  Examples:
    - Voiture au garage 5-12 mai (no VTC possible)
    - Période examen 18-25 juin (focus on study)
  
  AI behavior:
    - Specific app constraints (no VTC if no car)
    - Other apps continue normally

TYPE 5 — ÉVÉNEMENT RELIGIEUX (Ramadan, fêtes)
  Specific religious periods with system-wide impact.
  Examples:
    - Ramadan 2026 (auto-detected via Path)
    - Aïd Al-Fitr
    - Aïd Al-Adha
  
  AI behavior:
    - Path: special routines (suhoor, iftar timing)
    - Pulse: meal restrictions during fasting
    - Vector: possibly less VTC in late afternoons
    - Imperium: adjusted daily plans
```

---

## 5. The Add-Event Popup

```text
┌─────────────────────────────────────────┐
│ Nouvel événement                        │
│                                         │
│ Titre: [____________________]           │
│                                         │
│ Type: [Event ▾]                         │
│       ├─ Event                          │
│       ├─ Deadline                       │
│       ├─ Vacances/Voyage                │
│       ├─ Période bloquée                │
│       └─ Événement religieux            │
│                                         │
│ ┌─ CHAMPS DYNAMIQUES selon TYPE ─────┐ │
│ │                                    │ │
│ │ EVENT:                             │ │
│ │   Date/heure début: [_______]      │ │
│ │   Date/heure fin:   [_______]      │ │
│ │   Lieu (optionnel): [_______]      │ │
│ │   Urgence: [Normale ▾]             │ │
│ │                                    │ │
│ │ DEADLINE:                          │ │
│ │   Date limite:      [_______]      │ │
│ │   Heure limite:     [__:__]        │ │
│ │   Tâche à faire:    [____________] │ │
│ │   Temps estimé:     [_______]      │ │
│ │   Urgence: [Normale ▾]             │ │
│ │                                    │ │
│ │ VACANCES/VOYAGE:                   │ │
│ │   Du:  [_______]                   │ │
│ │   Au:  [_______]                   │ │
│ │   Destination:      [_______]      │ │
│ │   Coordonnées GPS:  [auto-fetch]   │ │
│ │   Pause VTC:        [☑ oui]        │ │
│ │                                    │ │
│ │ PÉRIODE BLOQUÉE:                   │ │
│ │   Du:  [_______]                   │ │
│ │   Au:  [_______]                   │ │
│ │   Apps impactées:                  │ │
│ │     [☑ VTC]                        │ │
│ │     [☐ Pulse]                      │ │
│ │     [☐ Path]                       │ │
│ │                                    │ │
│ └────────────────────────────────────┘ │
│                                         │
│ Récurrence: [Aucune ▾]                  │
│             ├─ Aucune                   │
│             ├─ Quotidienne              │
│             ├─ Hebdomadaire             │
│             ├─ Mensuelle                │
│             ├─ Annuelle                 │
│             └─ Personnalisée            │
│                                         │
│ Précisions:                             │
│ ┌─────────────────────────────────────┐ │
│ │                                     │ │
│ │                                     │ │
│ │                                     │ │
│ └─────────────────────────────────────┘ │
│ "Plus tu donnes de contexte, mieux       │
│  l'AI comprendra et planifiera."         │
│                                         │
│ [Annuler]  [Ajouter]                    │
└─────────────────────────────────────────┘
```

The "précisions" field is **always visible**, never collapsible. The hint text encourages filling it.

---

## 6. The 7-Day Threshold Logic

```text
On [Ajouter] click:

  1. Validate form
  2. Compute days_until_event = event_date - now()
  3. INSERT INTO calendar_events
  
  4. IF days_until_event > 7:
       Just stored. AI sees it later.
       
  5. IF days_until_event <= 7:
       a. Insert hook event: user.calendar.event_added
       b. Imperium replan service triggered (per doc 43 §3.2)
       c. AI evaluates: "Is the current plan still optimal?"
       d. If yes: nothing changes, plan kept
       e. If no: new plan version generated, user validates

For RECURRENCES:
  Same logic but evaluated per OCCURRENCE.
  Only occurrences within 7 days trigger the AI.
  Distant occurrences are stored as future markers.
```

---

## 7. Recurrence Support

V3 includes **complex recurrences** from day one (per user spec).

```text
RECURRENCE TYPES SUPPORTED:

A — None
  Single occurrence.

B — Daily
  Every day, optional days_of_week filter.

C — Weekly
  Every N weeks on specific weekday(s).
  Example: every Monday and Wednesday.

D — Monthly (by date)
  Every month on day X.
  Example: every 15th.

E — Monthly (by weekday position)
  Every month on the Nth weekday.
  Example: every 3rd Tuesday.

F — Yearly
  Every year on date X (with optional month flexibility).

G — Custom
  Free-form: every N days, every N weeks, every N months.

ALL recurrences support:
  - Start date
  - Optional end date
  - Optional max occurrences
  - Optional skip-dates (e.g. holidays)
  - Optional override per occurrence
```

### 7.1 The RFC 5545 RRULE format

```text
For internal storage, recurrences use the RFC 5545 RRULE format
(industry standard, supported by libraries):

Examples:
  Every Friday at 19:00:
    RRULE:FREQ=WEEKLY;BYDAY=FR
  
  Every 1st of the month:
    RRULE:FREQ=MONTHLY;BYMONTHDAY=1
  
  Every 3rd Tuesday:
    RRULE:FREQ=MONTHLY;BYDAY=3TU
  
  Every weekday:
    RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR
```

The user never sees RRULE strings. The UI translates choices to RRULE in the backend.

### 7.2 Per-occurrence overrides

```text
SCENARIO:
  Recurring "Cours Dars" every Friday 19h-21h.
  This Friday only, the cours is moved to Saturday 14h.

UI behavior:
  User opens the next occurrence
  Taps [Modifier cette occurrence uniquement]
  Edits date/time
  
Backend:
  - The recurrence stays (RRULE unchanged)
  - An override row created: skip the original date,
    add a one-off event at the new time
  - Future occurrences continue normally
```

---

## 8. Deadline Mechanics

### 8.1 Deadline registration

```text
User adds a Deadline:
  Title: "Dossier impôts"
  Date limite: 15 mai
  Heure limite: 12:00
  Tâche à faire: "Envoyer mon dossier aux impôts en ligne"
  Temps estimé: 2h
  Urgence: Normale
  Précisions: "Dernier recours, doit absolument être fait."

Backend:
  INSERT calendar_events with type=deadline
  IF days_until <= 7:
    - Trigger AI replan
    - AI computes optimal moment for 2h block
    - Considers: user's energy patterns, existing missions,
      day of week, etc.
    - Proposes: "Le 13 mai matin, 09h-11h"
    - User validates → mission created
```

### 8.2 What happens when the deadline approaches without action

```text
Day before deadline (14 mai):
  AI checks: was the deadline tasks completed?
  If NO:
    - Today's plan gets a high-urgency mission
    - "URGENT: Dossier impôts (deadline demain 12h)"
    - Standard mission, status='active', mission_type='urgente'
  If YES:
    - Nothing special. Deadline already met.

Day of deadline (15 mai):
  Morning replan includes the urgent mission if not done yet.
  Standard Imperium mission lifecycle applies.

If user marks the mission "ratée":
  - Standard mission_failed flow (per doc 43 §5)
  - Replan triggered if urgente
  - Communication with user via chatbot:
    "Tu as raté la deadline. Veux-tu la repousser ou laisser tomber?"
  - User answers via dialogue
  - AI updates the calendar_events.deadline_date or marks 
    abandonné based on the conversation
```

### 8.3 No special "deadline missed" logic

```text
KEY DESIGN DECISION (per user spec):

"Une deadline ratée, c'est une mission ratée Imperium."

We don't build a special "deadline failed" workflow.
We use the existing mission failure path.

The user's communication with the AI determines what 
happens next (extend deadline, abandon, reschedule).

This is consistent with the philosophy: no new mechanisms 
when existing ones cover the case.
```

---

## 9. WR Integration: The Calendar Stays Alive

```text
The calendar is queried during the WR (per doc 32, doc 47).

EXAMPLES OF WR ANGLES:

VECTOR section (doc 47 §4):
  AI sees: "Voiture au garage" event from 5-12 mai
  AI says: "Je n'ai pas vu de sessions VTC cette semaine.
            Normal, ta voiture était au garage. Est-elle
            ressortie ? Pour combien de temps encore ?"
  User answers → updates the event (extend/close)

PATH section (doc 47 §4):
  AI sees: scheduled "Cours Dars" weekly recurrence
  AI says: "Tu avais 4 cours Dars cette semaine. 
            Combien as-tu pu en suivre ?"

IMPERIUM section (doc 47 §4):
  AI sees: "Deadline impôts 15 mai" was active
  AI says: "Tu avais une deadline impôts cette semaine.
            Comment ça s'est passé?"
```

The WR is the place to discuss the past calendar. Not the calendar itself.

---

## 10. Database Schema

```sql
CREATE TABLE calendar_events (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  
  -- Common fields
  title                    TEXT NOT NULL,
  event_type               VARCHAR(32) NOT NULL,
                           -- 'event' | 'deadline' | 'vacances' 
                           -- | 'periode_bloquee' | 'evenement_religieux'
  precisions               TEXT NULL,
  
  -- Timing (varies by type)
  start_at                 TIMESTAMPTZ NULL,
                           -- for events, periods, vacances
  end_at                   TIMESTAMPTZ NULL,
                           -- for events, periods, vacances
  deadline_at              TIMESTAMPTZ NULL,
                           -- for deadlines only
  estimated_duration_min   INTEGER NULL,
                           -- for deadlines only
  urgency                  VARCHAR(16) NOT NULL DEFAULT 'normal',
                           -- 'low' | 'normal' | 'high' | 'critical'
  
  -- Location
  location_name            TEXT NULL,
  location_lat             NUMERIC NULL,
  location_lng             NUMERIC NULL,
  
  -- App impacts (for periode_bloquee, vacances)
  pause_vtc                BOOLEAN NOT NULL DEFAULT FALSE,
  pause_pulse              BOOLEAN NOT NULL DEFAULT FALSE,
  pause_path               BOOLEAN NOT NULL DEFAULT FALSE,
  
  -- Recurrence
  recurrence_rrule         TEXT NULL,
                           -- RFC 5545 RRULE string
  recurrence_end_date      DATE NULL,
  recurrence_max_count     INTEGER NULL,
  
  -- Lifecycle
  status                   VARCHAR(32) NOT NULL DEFAULT 'active',
                           -- 'active' | 'cancelled' | 'completed'
                           -- | 'deadline_missed' | 'superseded'
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  cancelled_at             TIMESTAMPTZ NULL,
  
  CONSTRAINT calendar_events_event_type_check
    CHECK (event_type IN ('event', 'deadline', 'vacances', 
                           'periode_bloquee', 'evenement_religieux')),
  CONSTRAINT calendar_events_status_check
    CHECK (status IN ('active', 'cancelled', 'completed', 
                       'deadline_missed', 'superseded'))
);

CREATE INDEX calendar_events_user_active_idx
ON calendar_events (user_id, status, start_at)
WHERE status = 'active';

CREATE INDEX calendar_events_user_deadlines_idx
ON calendar_events (user_id, deadline_at)
WHERE event_type = 'deadline' AND status = 'active';

CREATE INDEX calendar_events_user_recurrence_idx
ON calendar_events (user_id, recurrence_rrule)
WHERE recurrence_rrule IS NOT NULL AND status = 'active';

CREATE TABLE calendar_event_overrides (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  parent_event_id          UUID NOT NULL REFERENCES calendar_events(id)
                                                            ON DELETE CASCADE,
  
  override_type            VARCHAR(32) NOT NULL,
                           -- 'skip' | 'reschedule' | 'modify'
  original_occurrence_at   TIMESTAMPTZ NOT NULL,
                           -- when the recurrence WOULD have been
  
  new_start_at             TIMESTAMPTZ NULL,
                           -- if rescheduled
  new_end_at               TIMESTAMPTZ NULL,
  new_title                TEXT NULL,
  new_precisions           TEXT NULL,
  
  reason                   TEXT NULL,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX calendar_event_overrides_parent_idx
ON calendar_event_overrides (parent_event_id, original_occurrence_at);
```

---

## 11. Hook Integration With Imperium

The hooks system (doc 43 §3.1) is extended:

```text
NEW HOOKS:
  user.calendar.event_added       (if days_until <= 7)
  user.calendar.deadline_added    (if days_until <= 7)
  user.calendar.event_modified    (if days_until <= 7)
  user.calendar.event_deleted     (if days_until <= 7)
  user.calendar.recurrence_starts (when a recurrence begins
                                    its first occurrence within
                                    7 days)

For events more than 7 days away:
  - Stored
  - No hook
  - The event becomes "visible" to the AI when daily 
    plan generation includes it
  
The cron at 06:00 each morning:
  - Looks ahead 7 days
  - Surfaces newly-in-range events as hooks
  - Imperium replans accordingly
```

---

## 12. AI Task Types

```text
calendar.event.evaluate_impact   - Sonnet/Opus, when adding 
                                    an event ≤7 days away
calendar.event.deadline_plan     - Sonnet, propose best time
                                    slot for a deadline
calendar.event.recurrence_check  - daily, ensure recurrences
                                    in 7-day window are active
```

These integrate with existing Imperium routing (doc 30, doc 31).

---

## 13. Routing Distribution

```text
Most calendar work is DETERMINISTIC:
  - Storage
  - Recurrence calculations (RRULE library)
  - Conflict detection in UI
  - Cost: 0€

AI calls only happen on 7-day threshold crossings:
  - calendar.event.evaluate_impact: Sonnet 4.6
    (~0.02€ per event added in window)
  - calendar.event.deadline_plan: Sonnet 4.6
    (~0.02€ per deadline added in window)

Estimated annual cost: 1-3€ depending on usage.
```

---

## 14. UI Surface (V3)

### 14.1 Calendar tab in Imperium

```text
Imperium > Calendrier:

  ┌─────────────────────────────────────────────┐
  │ MON CALENDRIER                              │
  │                                             │
  │ [Vue mois ▾]  [Vue semaine]  [Vue agenda]   │
  │                                             │
  │ < April 2026 >                              │
  │                                             │
  │  L  M  M  J  V  S  D                        │
  │           1  2  3                           │
  │  4  5  6  7  8  9 10                        │
  │ 11 12 13 14 15 16 17    [● événements]      │
  │ 18 19 20 21 22 23 24    [● deadlines]       │
  │ 25 26 27 28 29 30                           │
  │                                             │
  │ Aujourd'hui (29 avril):                     │
  │  ⚪ Cours Dars 19h-21h (récurrent)          │
  │  ⏰ Deadline impôts dans 16 jours          │
  │                                             │
  │ Cette semaine:                              │
  │  • Médecin demain 15h                       │
  │  • Déjeuner Yacine vendredi 13h             │
  │                                             │
  │ [+ Ajouter un événement]                    │
  └─────────────────────────────────────────────┘
```

### 14.2 Event detail view

```text
Tap on event → detail view:

  ┌─────────────────────────────────────────────┐
  │ Médecin                                     │
  │                                             │
  │ Type: Event                                 │
  │ Quand: 30 avril 2026, 15h-16h               │
  │ Lieu: Cabinet Dr Smith                      │
  │ Urgence: Normale                            │
  │                                             │
  │ Précisions:                                 │
  │ "Contrôle annuel, prendre la prescription   │
  │  de tension."                               │
  │                                             │
  │ [Modifier]  [Supprimer]                     │
  └─────────────────────────────────────────────┘
```

### 14.3 Recurrent event detail

```text
Tap on recurrent event → options:

  ┌─────────────────────────────────────────────┐
  │ Cours Dars (récurrence)                     │
  │                                             │
  │ Type: Event                                 │
  │ Récurrence: Tous les vendredis 19h-21h     │
  │ Depuis: 1 mars 2026                         │
  │ Jusqu'à: indéfini                           │
  │                                             │
  │ [Modifier toute la série]                   │
  │ [Modifier cette occurrence uniquement]      │
  │ [Supprimer cette occurrence]                │
  │ [Supprimer toute la série]                  │
  └─────────────────────────────────────────────┘
```

---

## 15. Edge Cases

### 15.1 User adds an event in the past

```text
Per user spec: NO retroactivity.
UI rejects events with past dates.
"Tu ne peux pas créer un événement dans le passé.
 Si tu veux noter quelque chose qui est arrivé,
 attends ton prochain WR."
```

### 15.2 User tries to add 2 events at the same time slot

```text
Conflict in the calendar UI:
  - Detected on form submission
  - Modal: "Tu as déjà 'X' à ce créneau.
    Tu veux remplacer, modifier, ou annuler ?"
  - User decides
```

### 15.3 Recurrent event hits an existing one-off event

```text
When generating future occurrences of a recurrence:
  Each occurrence checked against existing events
  If conflict: notify user
  "L'occurrence du 14 juin entre en conflit avec
   ton événement existant 'X'. Que faire?"
  Options:
    - Skip this occurrence
    - Move the conflicting event
    - Keep both (overlap)
```

### 15.4 Vacances/voyage during a deadline

```text
SCENARIO:
  User adds vacances Maroc 10-17 May.
  Deadline already exists for May 15.

AI detects conflict:
  Notification: "Ta deadline du 15 mai tombe pendant 
   tes vacances. La déplacer avant ton départ ?"
  
User can:
  - Reschedule deadline before vacation
  - Mark deadline as "à faire au Maroc"
  - Cancel deadline
```

### 15.5 Religious event auto-detection

```text
Ramadan, Aïd, etc. detected from Path settings 
(prayer calculation method, date system).

System auto-suggests adding these as calendar events
on user setup or when Ramadan approaches.

User confirms or skips.

Once added: auto-applies adjustments per Section 4 Type 5.
```

---

## 16. Implementation Order (V3)

```text
Phase 1 — Schema migrations
  ├─ calendar_events
  └─ calendar_event_overrides

Phase 2 — RRULE library integration
  └─ python-dateutil (for RRULE parsing/generation)
  └─ Frontend: rrule.js for UI helpers

Phase 3 — Backend services
  ├─ services/imperium/calendar.py
  │  - CRUD events, validate, conflict detection
  ├─ services/imperium/calendar_recurrence.py
  │  - Compute occurrences, handle overrides
  ├─ services/imperium/calendar_threshold.py
  │  - 7-day threshold logic, hook firing
  └─ services/imperium/calendar_deadline_planner.py
     - AI call to propose deadline preparation slot

Phase 4 — Imperium hooks integration
  └─ Extend doc 43 §3.1 hook list
  └─ Wire up replan triggers

Phase 5 — API endpoints
  ├─ POST   /api/v1/imperium/calendar/events
  ├─ GET    /api/v1/imperium/calendar/events
  │   (with date range filtering)
  ├─ GET    /api/v1/imperium/calendar/events/{id}
  ├─ PATCH  /api/v1/imperium/calendar/events/{id}
  ├─ DELETE /api/v1/imperium/calendar/events/{id}
  ├─ POST   /api/v1/imperium/calendar/events/{id}/override
  └─ DELETE /api/v1/imperium/calendar/events/{id}/override/{occ}

Phase 6 — n8n workflow
  └─ calendar_morning_check (cron 06:00 daily)
     - Surfaces events newly within 7 days
     - Triggers Imperium replan if needed

Phase 7 — UI in Android app
  ├─ Calendar tab (month/week/agenda views)
  ├─ Event creation popup with dynamic fields
  ├─ Event detail view
  ├─ Recurrence editor
  └─ Override / "this occurrence" handler

Phase 8 — Religious events auto-suggestion
  └─ Ramadan/Aïd detection from Path settings
  └─ Setup wizard or annual prompt
```

---

## 17. Non-Goals For V3

```text
❌ Native calendar import (Google, Samsung, Apple)
   (User explicitly chose: dedicated tab only)

❌ Calendar export (.ics)
   (Possible V4; no need for V3)

❌ Sharing events with other users
   (System is mono-user)

❌ Email integration (auto-detect events from email)
   (V4+: complex, privacy-sensitive)

❌ Retroactive event creation
   (Past stays in WR, not in calendar)

❌ Smart scheduling suggestions when adding non-deadline events
   (User decides the time, AI doesn't second-guess)

❌ Pomodoro / time-blocking integrations
   (Out of scope for the calendar feature)

❌ External invitations / RSVPs
   (V4+ if ever needed)
```

---

## 18. V4+ Future Considerations

```text
- Email integration: parse confirmed appointments
- Travel planning: integrate Google Maps for travel time
- Smart suggestions: "Bons créneaux pour X" based on patterns
- Multi-event templates (e.g. "Ramadan adjustments package")
- Statistical analysis: "Most productive day of the week"
- Integration with WR planning: "What deadlines coming?"
- Voice input for event creation
```

---

## 19. References

- `12_DAILY_OBJECTIVE_PERIOD_LOGIC.md` — day boundary logic
- `28_DAILY_PLAN_WORKFLOW.md` — daily plan generation
- `32_WR_INTERACTIVE_WORKFLOW.md` — WR mechanism
- `43_IMPERIUM_LOGIC_DETAIL.md` — hooks system, mission lifecycle
- `47_WR_GUIDED_SECTIONS.md` — WR sections that interrogate calendar
- `41_PATH_LOGIC_DETAIL.md` — Ramadan / religious dates source
- `33_VECTOR_LOGIC_DETAIL.md` — Vector pause during vacances
- `42_VAULT_LOGIC_DETAIL.md` — financial impact of vacances
- `40_PULSE_LOGIC_DETAIL.md` — health adjustments during periods

---

## 20. Final Note

```text
The calendar is not a productivity tool.
The calendar is a CONTEXT FEEDER for the AI brain.

Every event captured here helps the AI understand:
- What the user CAN'T do at certain times
- What the user MUST do before certain times
- What the user IS DOING during certain periods
- What the AI SHOULD AVOID suggesting

Without this context, the AI plans in a vacuum.
With this context, the AI plans for the user's actual life.
```

---

**Document version:** 1.0
**Status:** V3 design specification (DO NOT IMPLEMENT before V1 + V2)
**Last updated:** 2026-04-29
