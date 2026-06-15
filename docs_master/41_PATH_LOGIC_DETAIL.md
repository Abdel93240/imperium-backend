# 41 - The Path Logic Detail

## 1. Purpose

The Path is the **worship, prayer, fasting, sadaqa, Quran, adhkar, and ghusl**
module. It tracks religious obligations, collects explicit user actions, displays
operational worship signals, and triggers backend workflows that Imperium may use
for planning. It connects with Vault (sadaqa calculation) and emits signals that
Imperium uses to trigger AI replans.

**The Path is not a religious authority.** It does not issue rulings, infer
worship completion, infer fasting intention, or infer ghusl requirement.

Canonical sources used by this V1 detail:

- `01_SIGNAL_VARIABLES_DICTIONARY.md`
- `07_ANDROID_APP_RESPONSIBILITIES.md`
- `42_VAULT_LOGIC_DETAIL.md`
- `43_IMPERIUM_LOGIC_DETAIL.md`
- `59_DESIGN_SYSTEM_V1_DRAFT.md`

---

## 2. Non-Negotiable Rules

```text
✅ Path can:
   - calculate / fetch prayer times (MAWAQIT + local fallback)
   - track prayer completion (explicit user action)
   - track fasting state
   - track adhkar routines
   - track Quran progression
   - emit ghusl_required signal
   - calculate sadaqa weekly target
   - track sadaqa donations
   - carry remaining sadaqa to next week

❌ Path must never:
   - infer fasting intention without explicit user action
   - infer ghusl state without explicit user action
   - infer Quran completion without explicit user action
   - infer adhkar completion without explicit user action
   - infer sadaqa completion without explicit user action
   - infer prayer completion from location, time, or phone activity
   - guilt-trip the user about missed obligations
   - send aggressive notifications
```

The principle: **religious actions are sacred and personal**. The system never
auto-marks them as done.

---

## 3. Authority Boundary

Android screens may create local drafts with
`pending|syncing|synced|failed|conflict` labels, but the backend remains the
authority for canonical records.

V1 rules:

- All Path writes require explicit user action and backend validation.
- All mutation endpoints require `Idempotency-Key`.
- Private religious data is local-first unless a privacy gate authorizes a
  specific external model call.
- Imperium can replan from Path events, but the event source remains Path and the
  final mission plan remains Imperium-owned.
- Vault receives confirmed sadaqa donations as personal expenses, but **Path owns
  sadaqa percentage, weekly target, carry, and donation intent**.
- Pulse receives fasting constraints from Path; Pulse does not decide fasting.

Backend V1 routing note:

- `app/api/v1/routes/imperium_path.py` is canonical for Path V1.
- `GET /api/imperium/path/today` is owned by that module and returns
  `PathTodayResponse`.
- Legacy `ImperiumPathItem` compatibility code is deprecated for Path V1 and must
  not define or mask `/path/today`.

---

## 4. The Five Path Domains

```text
DOMAIN 1 — PRAYER
  ├─ Prayer time source (MAWAQIT priority, local fallback)
  ├─ Prayer completion tracking (explicit user action)
  ├─ Mosque integration (MAWAQIT)
  └─ Prayer-related missions (e.g. ghusl)

DOMAIN 2 — FASTING
  ├─ Active fasting periods
  ├─ Suhoor / iftar windows
  ├─ Pulse constraint propagation
  └─ Fasting types (Mon/Thu, white days, Ramadan, custom, temporary)

DOMAIN 3 — SADAQA
  ├─ Weekly target from business profit
  ├─ Donation tracking
  ├─ Carry-forward of remaining
  └─ Configurable percentage (Path-owned)

DOMAIN 4 — ADHKAR & QURAN
  ├─ Adhkar routines (categorized — see §10)
  ├─ Quran reading progression
  └─ Discipline contribution

DOMAIN 5 — GHUSL
  ├─ User-triggered requirement
  ├─ Auto-mission via Imperium AI replan
  └─ Ghusl address registry
```

---

## 5. Events

Path V1 may emit:

| Event | Trigger | Notes |
|---|---|---|
| `path.prayer.logged` | User marks one of the five obligatory prayers as accomplished. | No automatic completion. |
| `path.prayer.not_marked` | User explicitly marks the prayer as not accomplished. | UI wording avoids religious judgment language. |
| `path.fasting.started` | User starts a fast and confirms type. | No inferred intention. |
| `path.fasting.ended` | User confirms end at iftar or a historical correction. | Pulse constraints update after backend validation. |
| `path.fasting.broken` | User confirms a broken fast. | Imperium replan prompt is user-confirmed. |
| `path.sadaqa.recorded` | User validates donation amount and destination. | Vault transaction handoff is automatic but visibly pending if it fails. |
| `path.ghusl.required` | User activates ghusl required. | Imperium receives replan request. |
| `path.ghusl.completed` | User confirms ghusl completed. | Imperium may mark ghusl mission done. |
| `path.adhkar.incremented` | User taps or validates voice-counted adhkar increment. | Distinct increments merge by idempotency key. |
| `path.quran.progress.updated` | User validates Quran continuation point. | Regression requires confirmation. |
| `worship.routine.updated` | User edits adhkar or reminder routine settings. | Origin screen PAT-11e. |
| `path.reminder.requested` | User creates a prayer, fasting, Quran, or adhkar reminder. | Origin screen PAT-11 reminder settings. |

---

## 6. Prayer Times, MAWAQIT, And Calculation Engine

This is the **most important architectural distinction** in Path: there are two
sources of prayer times, and MAWAQIT (the real mosque time) takes priority.

### 6.1 Why two sources

```text
WHY THIS MATTERS:
  Different mosques use different calculation methods.
  Times can differ by 5-15 minutes between mosques.
  Missing a prayer because of a wrong assumption is unacceptable.

USE CASE (VTC driver):
  User finishes a Bolt ride near Mosque X.
  User wants to know if they can still catch Asr there.
  Local calculation says 18:12, but Mosque X actually does 18:18.
  → Path uses MAWAQIT for Mosque X → returns 18:18, accurate.
```

### 6.2 Source order (priority)

Path displays the five obligatory prayers in V1: `Fajr, Dhuhr, Asr, Maghrib, Isha`.

Sunnah, Rawatib, Tahajjud, Duha, and Witr are V2 routine candidates and are not
counted by V1 prayer status. This avoids inventing obligation scope.

Source order:

```text
1. Reference mosque MAWAQIT times (when available and fresh).
2. Offline cached MAWAQIT times for the reference mosque.
3. Local calculation engine (fallback).
```

### 6.3 MAWAQIT rules

V1 uses a backend MAWAQIT HTTP adapter. The exact provider URL/API credential is
environment-specific and configured through secrets, not code.

Cache rules:

- Cache daily prayer times per registered mosque for 30 days.
- Refresh default mosque daily at 03:00 UTC.
- Refresh on manual user request from PAT-08 or PAT-09.
- Stale cache can display for up to 48 hours with a Warning chip.
- After 48 hours stale, UI must show fallback calculation as primary and stale
  MAWAQIT as historical context only.

Reference mosque (times):

- The user has ONE reference mosque (the mosque near home, e.g. [ville]). Its
  MAWAQIT times are the displayed prayer times, at all times.
- This is the single source for displayed times. No multi-mosque list, no
  "pick among registered mosques" for the schedule.
- Changing the reference mosque (move/travel) is an explicit user action.
- GPS/`nearby_mosque` suggestion may help the user PICK the reference mosque,
  but is never silently registered.

IMPORTANT — this section now covers TIMES ONLY. Choosing where to physically pray
during the day is NOT here; see §7-bis.

Privacy rules:

- Mosque names, mosque IDs, and frequent GPS-derived mosque patterns are
  `very_high` privacy when linked to the user.
- GPS is sent to the backend only after permission and only for mosque search,
  qibla calculation, or registered-address distance display.
- External model calls receive no mosque names, addresses, or GPS unless a
  privacy gate explicitly allows a summarized use case.

### 6.4 Fallback calculation engine

If MAWAQIT is unavailable, Path uses a backend calculation engine equivalent to
Adhan with:

| Setting | V1 default | User setting |
|---|---|---|
| Calculation method | `MuslimWorldLeague` | PAT-11b |
| Madhhab / Asr rule | `Maliki` | PAT-11c |
| Location source | registered city or explicit GPS | PAT-11f |
| Timezone | device/backend timezone for selected location | derived |
| Precision | minute-level display | fixed V1 |

Supported methods in V1 settings:

```text
MuslimWorldLeague, Karachi, Egypt, ISNA, Jafari, Custom
```

Supported madhhab values:

```text
Hanafi, Maliki, Shafii, Hanbali, Jafari
```

The fallback engine recomputes daily at 00:30 Europe/Paris and stores results in
`path_calculated_prayer_times` (no per-request recomputation).

⚠️ TO INVESTIGATE before finalizing fallback architecture: explore what the
MAWAQIT API itself offers when the reference mosque has no data (does it expose
a calculation, neighboring mosques, etc.?). Do NOT assume a second calculation
API is needed until MAWAQIT's real capabilities are checked. The Maliki
calculation engine (§6.4) is the assumed fallback only pending this check.

If GPS is denied and no city is configured, PAT-01 shows an Empty/Warning state
asking the user to configure city or mosque. **It must not invent times.**

---

## 7. Prayer Marking Logic

PAT-02 is the only V1 prayer marking surface.

Allowed actions: `accomplished`, `not_marked_as_accomplished`, `clear_status`.

Rules:

- Only the five obligatory prayers are represented in V1.
- Prayer completion is **never inferred** from location, time, calendar, or phone
  activity. Only explicit user action sets completion.
- A future prayer cannot be marked as `not_marked_as_accomplished`.
- A prayer can be marked accomplished at any time by explicit user correction.
- The UI label can say `Non marquée comme accomplie`; it must not present itself
  as a religious judgment.
- Discipline impact is backend-calculated from explicit
  `not_marked_as_accomplished` events, never from silence alone.
- Post-prayer adhkar may be suggested after an accomplished mark, but it is not
  auto-completed.

```text
prayer_logs table (per doc 05):
  user_id, prayer_name (Fajr|Dhuhr|Asr|Maghrib|Isha), prayer_date,
  completed (bool), completed_at, location (optional), source: user_action
```

Endpoint contract:

```text
TBD POST /api/path/prayers/{prayer_slug}/mark
Headers: Idempotency-Key
Payload: status, prayed_at, source, optional_note
```

Offline conflict:

- Same prayer/day/status with same `Idempotency-Key` dedupes.
- Different status for the same prayer/day opens a conflict sheet.
- Latest server state does not silently overwrite a local explicit correction.

---

### 7-bis. Prayer Mission Logic (go pray) — dynamic

Distinct from prayer TIMES (§6) and prayer MARKING (§7). This is the mission of
physically going to pray, integrated into the day.

**Awareness zones are created during daily planning, not in real time.**
When the brain plans the day (daily plan — see doc 28 `DAILY_PLAN_WORKFLOW`,
function around `daily_plan`), it creates the prayer "awareness zones" as part
of the plan: knowing where the user will be and what mission is active around
each prayer time, it provisions the prayer in that context.

Because awareness zones live INSIDE daily planning, they are recomputed
automatically on every re-plan (the re-planning reason is added to context).
No separate prayer-rescheduling mechanism is needed — the prayer inherits the
planning lifecycle. If the real day deviates, the next re-plan adjusts the zone
and the mosque choice.

**Mosque selection is DYNAMIC, not from a pre-registered list.**
There are tens of thousands of mosques in Île-de-France; a fixed registered
list is not feasible. At planning time, the brain scans mosques in the zone
where the user is / will be (geo API), and selects one based on a single
criterion: **position in the continuity of the day** — i.e. close to the user
now, OR moving the user toward the next mission. Example: while doing VTC, the
brain scans mosques along the arrival zone and routes the user to one that fits
the day's flow.

**Anticipation window is not fixed.** The lead time before a prayer (could be
10, 15, 20, 30+ min) depends on context (current mission, travel), determined
at planning time — never a blind fixed rule.

Privacy: mosque scan/selection follows §6.3 privacy rules (GPS gated, no mosque
data to external models without a privacy gate).

---

## 8. Fasting Logic

Supported `fasting_type` values: `monday_thursday, white_days, ramadan, custom,
temporary`.

```text
fasting_logs table (per doc 05):
  user_id, fasting_date, fasting_type, action_type (start|end|break|abandon),
  source: user_action

SIGNAL fasting_active (computed boolean for current moment):
  TRUE if fasting_logs has a start action for today
       AND no end/break/abandon action since
       AND current time within suhoor → iftar window.
```

V1 fasting rules:

- A fast starts only when the user confirms PAT-05.
- Ramadan and white days can show preparation banners from lunar calendar data,
  but they do not auto-start a fast.
- `white_days_active=true` suggests a temporary fast; it does not create one.
- `suhoor_time` and `iftar_time` come from the selected prayer-time source
  (suhoor default = fajr − 30 min configurable offset; iftar = maghrib).
- Ending a fast at iftar still requires user confirmation.
- Breaking a fast requires explicit confirmation; optional reason text allowed.
- `path.fasting.broken` opens a user-confirmed Imperium replan prompt.

Fasting types detail:

```text
monday_thursday: recurring Mon/Thu if opted in, user still confirms start daily
white_days:      13/14/15 lunar month, calendar reminder, not auto-confirmed
ramadan:         all Ramadan days, calendar-aware, each day still requires start
custom:          user manually defines
temporary:       specific intent (e.g. "fasting tomorrow because...")
```

Pulse handoff:

- While fasting is active and daytime drinking is disabled, Path sends
  `hydration_limits={"daytime":false}` to Pulse.
- Meal suggestions disabled during fasting hours; workout intensity reduced.
- PAT-05 shows a `Pulse adjusted` handoff toast only after backend acceptance.

Endpoint contracts:

```text
TBD POST /api/path/fasting/start
TBD POST /api/path/fasting/end
TBD POST /api/path/fasting/break
Headers: Idempotency-Key
```

Offline conflict:

- Start/end/break mutations synced in local creation order.
- Server-active fast plus local start opens conflict.
- Local start followed by local break syncs as two ordered mutations.

---

## 9. Sadaqa Logic

### 9.1 Calculation source: business profit only

```text
DECISION (per user spec):
Sadaqa is calculated on the BUSINESS profit only.
Not on personal income. Not on total wallet.

Why: business profit is the income God blessed through work.
Personal money management is separate.
```

Sadaqa percentage is **owned by Path**. Vault exposes it read-only and deep-links
to PAT-11d.

### 9.2 Weekly target computation

```text
At end of each ISO week (Sunday 23:59 Europe/Paris):
  weekly_business_profit = SUM(vault business_income) - SUM(vault business_expenses)

  sadaqa_weekly_target = max(weekly_business_profit, 0) * sadaqa_percentage
  effective_weekly_target = sadaqa_weekly_target + carry_from_previous_weeks
```

Default `sadaqa_percentage` is `0.05` (5%); V1 editable range is `0.01` to `0.20`.
User changes are allowed once per week without extra confirmation. A second change
in the same week opens a confirmation dialog explaining that the new value affects
**future targets only**.

Target recomputation:

- Weekly profit changes recompute the current week target.
- Sadaqa percentage changes are prospective by default.
- Past donation records are never recalculated.
- Carry is recomputed only from confirmed donations and weekly target snapshots.

### 9.3 Carry behavior

```text
End of week N:
  donated_total = SUM(sadaqa_records.amount where related_week = N)
  remaining = max(0, effective_weekly_target_N - donated_total)

Beginning of week N+1:
  effective_weekly_target_N+1 = (profit_N+1 × percentage) + remaining_from_N

EXAMPLE:
  Week N: target 50€, donated 30€ → remaining 20€
  Week N+1: profit gives 40€ target → effective target 40 + 20 = 60€

OVER-DONATION:
  Week N: target 50€, donated 80€ → remaining = 0 (no negative debt/credit)
  Week N+1: target = profit × percentage normally
```

Rules:

- Partial donation leaves remaining carry for the next week.
- Overpayment reduces existing carry first, then creates no negative spiritual
  debt display.
- Multi-week catch-up is logged as one donation with allocation lines generated
  by backend from oldest carry to newest target.
- PAT-01 shows a persistent carry banner only when carry is greater than 0.
- UI wording uses `montant reporté` or `reste à donner selon ton objectif`, not
  language that implies a religious ruling.

### 9.4 Donation flow

PAT-03 fields: amount, destination, optional note, date, optional voice transcript.

```text
sadaqa_records table (per doc 05):
  user_id, amount_eur, destination (optional), donated_at,
  related_week_start, source: user_action
```

Submission creates:

1. Path donation record.
2. Vault personal expense handoff with category `Sadaqa`.

The Vault handoff is automatic after a confirmed Path donation (doc 42 says Vault
receives Path sadaqa donations as personal expenses). If Vault creation fails,
the Path donation remains saved and PAT-03/PAT-01 shows `Vault transaction
pending` until retry succeeds.

Endpoint contracts:

```text
TBD GET /api/path/sadaqa/summary
TBD POST /api/path/sadaqa/donations
TBD GET /api/path/sadaqa/donations
TBD GET /api/path/settings/sadaqa
TBD PATCH /api/path/settings/sadaqa
Headers for mutations: Idempotency-Key
```

---

## 10. Ghusl Auto-Mission

The most architecturally interesting Path feature because it triggers
cross-module AI behavior. PAT-04 is the only V1 activation/completion surface.

### 10.1 Activation

```text
USER ACTION (PAT-04): Toggle "Ghusl requis" → ON

BACKEND:
  - sets path.ghusl_required = TRUE
  - sets path.ghusl_required_since = NOW()
  - may create ghusl_mission_id
  - INSERTS event: path.ghusl.required
```

Rules:

- Ghusl requirement is **never inferred**. Activation and completion are both
  explicit user actions.
- PAT-04 shows `Imperium replanning...` only as a handoff state, not as final
  mission confirmation.
- PAT-01 shows a banner when a mission id is created.

### 10.2 Imperium reception

```text
Imperium READS the backend event path.ghusl.required and triggers a replan.

On reception:
  1. Creates a mission: "Faire le ghusl avant {next_prayer}"
     source: "path", priority: high, status: active
  2. Triggers AI replan (ai_task imperium.day_replan, reason ghusl_required;
     n8n claims, Sonnet 4.6 replans the day)
  3. Replan finds nearest registered ghusl address, inserts the ghusl mission
     before next prayer, reorganizes other missions
  4. New plan returned to backend
  5. Presented to user for validation
```

### 10.3 Completion

```text
User taps "Ghusl fait" (PAT-04):
  → path.ghusl_required = FALSE
  → INSERTS event: path.ghusl.completed
  → Imperium marks the ghusl mission as "faite"
  → No additional replan needed
```

### 10.4 Registered ghusl addresses

| Field | Rule |
|---|---|
| `ghusl_address_id` | Backend generated. |
| `label` | User label, required. |
| `type` | `home\|mosque\|gym\|work\|other`. |
| `address_text` | Optional manual address. |
| `latitude` / `longitude` | Optional, explicit GPS only. |
| `is_default` | At most one true. |
| `privacy_level` | `very_high`. |

Used by Imperium AI replan to choose the nearest valid option.

```text
TBD GET /api/path/ghusl-addresses
TBD POST /api/path/ghusl-addresses
TBD PATCH /api/path/ghusl-addresses/{address_id}
TBD DELETE /api/path/ghusl-addresses/{address_id}
TBD POST /api/path/ghusl/activate
TBD POST /api/path/ghusl/complete
Headers for mutations: Idempotency-Key
```

Offline conflict:

- Activation followed by completion syncs in order.
- Server-completed plus local activation opens a conflict sheet.
- Address edits use version conflict detection; no silent overwrite.

---

## 11. Adhkar Routines

> **NOTE — Pending document:** the complete adhkar categorization will be provided
> by the user in a separate document. This section will be expanded once that
> document is integrated.

Supported `adhkar_type` values:

```text
morning, evening, istighfar, salawat, tasbih, tahmid, takbir, personal
```

V1 routines:

- Maximum 8 active routines.
- Default suggested routines can exist, but user activation is explicit.
- Counter supports tactile +1 as the canonical input.
- Voice counting through Whisper/faster-whisper is optional in V1 and must display
  confidence; low confidence requires user validation.
- Arabic text can render with Noto Naskh Arabic, plus transliteration and optional
  translation when configured.
- Post-prayer routine suggestion may appear after PAT-02 accomplished, but no
  adhkar completion is inferred.

```text
adhkar_routines:    user_id, routine_label, adhkar_type, target_count,
                    frequency (daily|weekly|per_prayer), active
adhkar_completions: user_id, routine_id, completion_date, completed_count,
                    completed_at
```

Endpoint contracts:

```text
TBD GET /api/path/adhkar/routines
TBD POST /api/path/adhkar/routines
TBD PATCH /api/path/adhkar/routines/{routine_id}
TBD DELETE /api/path/adhkar/routines/{routine_id}
TBD POST /api/path/adhkar/routines/{routine_id}/increment
TBD POST /api/path/adhkar/routines/{routine_id}/reset
Headers for mutations: Idempotency-Key
```

Offline conflict: distinct increment keys use merge sum; same key dedupes; routine
edits use version conflict; reset conflicts with queued increments open a review
sheet.

---

## 12. Quran Progress

PAT-07 stores the user's validated continuation point.

V1 fields: `quran_page` (1-604), `quran_juz`, `quran_hizb`, `quran_surah`,
`quran_last_validated_point`, `quran_daily_objective`.

Rules:

- User can enter page, surah, or juz through PAT-07b selector.
- Backend normalizes page/juz/hizb/surah mapping.
- A lower page than the last validated point requires confirmation.
- Quran completion is **never inferred** from time spent or screen activity.
- Khatm milestone is informational and user-confirmed.
- No restart logic if user misses a day. The progression is theirs to manage.

```text
quran_progression table:
  user_id (unique), last_validated_page, last_validated_at,
  daily_objective
```

Endpoint contracts:

```text
TBD GET /api/path/quran/continuation
TBD POST /api/path/quran/progress
TBD PATCH /api/path/quran/objective
Headers for mutations: Idempotency-Key
```

Offline conflict: same key dedupes; higher server point plus lower local point
opens regression confirmation; higher local point can update after backend
validation.

---

## 13. The Path Daily Score

A composite "discipline of Path" score is computed daily:

```text
score = weighted_average(
  prayer_completion_rate × 0.40,
  adhkar_completion_rate × 0.20,
  sadaqa_progress × 0.15,
  fasting_compliance_if_active × 0.15,
  quran_daily_objective_met × 0.10
)

Range: 0.0 to 1.0
Used by Imperium for the broader discipline_score.
```

Computed deterministically, no AI involved.

### 13.1 Discipline contribution rules

Path feeds Imperium discipline context **only from explicit user-confirmed events**:

- `path.prayer.not_marked` may affect discipline score, but silence never does.
- `path.fasting.broken` may trigger replanning, not guilt messaging.
- `path.adhkar.incremented` and Quran progress contribute as discipline signals
  only after backend acceptance.
- UI wording must stay operational and non-judgmental.

---

## 14. Hijri, White Days, And Qibla

Hijri calendar V1 uses a backend lunar calendar engine. A configured external
calendar API may enrich it, but if unavailable the UI shows calculated data with
source and confidence.

Rules:

- `hijri_date` appears on PAT-01 top summary and PAT-05 fasting context.
- `white_days_active` shows a fasting suggestion banner, never an automatic fast.
- Qibla direction is V1 informational in PAT-01 and PAT-08 when location available.
- Qibla compass sensor permission is requested only when the user opens the
  compass widget or screen.

```text
TBD GET /api/path/calendar/hijri
TBD GET /api/path/qibla
```

---

## 15. Path AI Task Types & Routing

```text
path.weekly_review_contribution  - feeds the WR (Opus via doc 32)
path.routine_adjustment          - rare, "should I adapt my adhkar routine?"
path.sadaqa_strategy             - rare, deep advice (Opus)
```

Most Path operations are deterministic. AI is rarely needed because prayer times
are calculated/fetched, sadaqa is arithmetic, ghusl flow is event-based, and
adhkar is counting.

Routing distribution:

```text
Daily ops (98%):           Qwen local OR backend deterministic
Light adaptations (1%):    Haiku 4.5
Strategic spiritual (1%):  Opus 4.7
Cost per month: < 0.50 €
```

---

## 16. Reads & Events via Common Memory

### 16.1 With Imperium

```text
The backend emits append-only events; Imperium READS them:
  - path.ghusl.required     → Imperium AI replan
  - path.ghusl.completed    → Imperium marks mission done
  - path.prayer.not_marked  → Imperium logs discipline impact
  - path.sadaqa.recorded    → Imperium daily plan awareness
  - path.fasting.broken     → Imperium replan prompt (user-confirmed)
```

### 16.2 With Vault

```text
Path READS weekly_business_profit from common memory (read-only) to compute
the sadaqa target.

When the user confirms a sadaqa donation, the BACKEND records the action on the
Path side (owner of sadaqa state) AND the Vault service writes the matching
expense (category Sadaqa). Two backend writes by rule, not a Path→Vault send.
Path owns percentage/target/carry; Vault exposes percentage read-only.
```

### 16.3 With Pulse

```text
Path writes its fasting state into its own tables (common memory). Pulse READS
that state from common memory to adapt meals / workout / hydration. There is no
direct Path-to-Pulse channel, consistent with doc 40 §15.2.
```

### 16.4 With Vector

Path does not modify Vector's profitability logic. Vector only evaluates VTC
profitability: zone, time, demand, distance, event opportunity, return strategy,
ride economics.

If a Path constraint conflicts with a profitable Vector recommendation, Imperium
applies the final user-facing overlay above Vector:

```text
Vector profitability signal: green
Path / Imperium constraint: prayer slot in 20 minutes
Final Imperium action: do not take a ride direction that would breach it
```

This keeps Vector pure and prevents worship, fatigue, family, health, or lifestyle
logic from leaking into the VTC profitability engine.

---

## 17. Religious Data Privacy Policy

Path handles high and very-high privacy data. V1 rules:

- `sadaqa_destination`, `sadaqa_donation_amount`, `ghusl_required`,
  `ghusl_addresses`, mosque attendance patterns, and precise GPS are redacted
  from logs.
- External model routing for Path data defaults to local Qwen only for routing,
  classification, short summaries, and clarification.
- GPT/Claude/Gemini receive Path religious data only after privacy gate approval
  and only the minimum required payload.
- Donation receipts or charity scans are local-only in V1 unless the user
  explicitly uploads for OCR; OCR uses a privacy gate.
- Deletion of a Path donation removes or anonymizes the linked Path record and
  marks the Vault transaction linkage as deleted/reversed according to Vault
  immutability rules.
- Vector memory stores summary-only fields where the dictionary permits it; no raw
  donation destination, ghusl address, or mosque pattern is embedded.
- Error messages must not expose sensitive religious details.

---

## 18. Offline And Conflict Summary

| Mutation | Offline behavior | Conflict rule |
|---|---|---|
| Prayer mark | Queue one prayer/day/status payload. | Different status opens conflict; no silent overwrite. |
| Sadaqa donation | Queue donation and Vault handoff. | Same key dedupes; Vault failure becomes pending handoff. |
| Ghusl activation/completion | Queue ordered mutations. | Completed vs activated conflict opens review. |
| Fasting start/end/break | Queue ordered mutations. | Server active-state mismatch opens review. |
| Adhkar increment | Queue increment events. | Distinct keys merge sum; same key dedupes. |
| Quran progress | Queue validated continuation point. | Regression requires confirmation. |
| Mosque registration | Queue user-confirmed registration/edit. | Version conflict opens diff. |
| Settings | Queue line-level patch. | Server changed value opens confirmation. |

---

## 19. UI Surface (V1)

Path V1 screens:

| Screen | Purpose | Stable ID |
|---|---|---|
| PAT-01 | Dashboard | `PAT.DASH.MAIN` |
| PAT-02 | Prayer Mark Action | `PAT.PRAYER.MARK` |
| PAT-03 | Sadaqa Donation Form | `PAT.SADAQA.DONATE` |
| PAT-04 | Ghusl Required Toggle | `PAT.GHUSL.REQUIRED` |
| PAT-05 | Fasting Start / End Action | `PAT.FASTING.ACTION` |
| PAT-06 | Adhkar Counter | `PAT.ADHKAR.COUNTER` |
| PAT-07 | Quran Progress Update | `PAT.QURAN.PROGRESS` |
| PAT-08 | Mosque Detail / MAWAQIT View | `PAT.MOSQUE.DETAIL` |
| PAT-09 | Registered Mosques Management | `PAT.MOSQUES.MANAGE` |
| PAT-10 | Registered Ghusl Addresses | `PAT.GHUSL.ADDRESSES` |
| PAT-11 | Path Settings | `PAT.SETTINGS.CORE` |

Internal V1 sub-surfaces (confirmed, not counted as new top-level screens):

```text
PAT-06b Adhkar Routine Configuration
PAT-07b Quran Surah/Juz/Page Picker
PAT-09b Add Mosque Sub-Flow
PAT-10b Add Ghusl Address Sub-Flow
PAT-11b Calc Method Selector
PAT-11c Madhhab Selector
PAT-11d Sadaqa Percentage Detail
PAT-11e Adhkar Routines Manager
PAT-11f City / Location Selector
```

These sub-surfaces are drawers, dialogs, side panes, or inline states.

Settings (PAT-11) covers: calculation method, madhhab, large city (Paris default),
sadaqa percentage, registered mosques (MAWAQIT), registered ghusl addresses, and
adhkar routines configuration.

---

## 20. Database Tables

Existing (per doc 05): `prayer_logs` ✅, `fasting_logs` ✅, `sadaqa_records` ✅.

To add:

```sql
CREATE TABLE path_calculated_prayer_times (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  date            DATE NOT NULL,
  fajr TIME, dhuhr TIME, asr TIME, maghrib TIME, isha TIME,
  calculation_method VARCHAR(64),
  madhhab         VARCHAR(32),
  city_reference  VARCHAR(128),
  computed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE path_registered_mosques (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  mawaqit_id  VARCHAR(128),
  name        VARCHAR(200),
  address     TEXT,
  latitude    NUMERIC,
  longitude   NUMERIC,
  is_default  BOOLEAN NOT NULL DEFAULT FALSE,
  added_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE path_mawaqit_cache (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  mosque_id     UUID NOT NULL REFERENCES path_registered_mosques(id) ON DELETE CASCADE,
  date          DATE NOT NULL,
  prayer_times  JSONB NOT NULL,
  fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE registered_ghusl_addresses (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  label        VARCHAR(100) NOT NULL,
  type         VARCHAR(32),
  address      TEXT,
  latitude     NUMERIC,
  longitude    NUMERIC,
  is_default   BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE adhkar_routines (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  routine_label VARCHAR(64),
  adhkar_type   VARCHAR(32),
  target_count  INTEGER,
  frequency     VARCHAR(32),
  active        BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE adhkar_completions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  routine_id      UUID NOT NULL REFERENCES adhkar_routines(id) ON DELETE CASCADE,
  completion_date DATE NOT NULL,
  completed_count INTEGER NOT NULL DEFAULT 0,
  completed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE quran_progression (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  last_validated_page   INTEGER,
  last_validated_at     TIMESTAMPTZ,
  daily_objective       VARCHAR(64)
);

CREATE TABLE path_weekly_sadaqa_state (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  week_start            DATE NOT NULL,
  business_profit_eur   NUMERIC,
  target_eur            NUMERIC,
  carried_from_previous NUMERIC,
  donated_eur           NUMERIC,
  remaining_eur         NUMERIC,
  computed_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

---

## 21. References

- `01_SIGNAL_VARIABLES_DICTIONARY.md` — full Path signal list
- `05_DATABASE_SCHEMA.md` — existing tables
- `07_ANDROID_APP_RESPONSIBILITIES.md` — client/backend authority split
- `08_NON_NEGOTIABLE_RULES.md` — religious privacy rules
- `42_VAULT_LOGIC_DETAIL.md` — business profit source, sadaqa expense handoff
- `43_IMPERIUM_LOGIC_DETAIL.md` — replan reception of Path events
- `40_PULSE_LOGIC_DETAIL.md` — fasting / hydration constraints
- `59_DESIGN_SYSTEM_V1_DRAFT.md` — PAT screens design

---

**Document version:** 2.0 (merged — worship logic detail + V1 implementation contracts)
**Status:** Path V1 reference (adhkar categorization section pending user document)
**Last updated:** 2026-06-06
## Patch 41-A Hijri Calendar V3 & Model Routing Alignment

Patch 41-A does two things:
1. extends the Hijri calendar (§14) with the V3 feature set (personal events,
   lunar observation + manual confirmation, duplicate-date mechanic, bridge to
   Imperium, 2-week display window);
2. realigns Path AI routing (§15) and the Imperium integration (§16.1) with the
   consolidated AI architecture (doc 30, June 2026 rewrite): Haiku removed,
   Qwen 32B as local model, Opus 4.8, and WR routing delegated to doc 30/32.

This is a documentation alignment patch. It does not, by itself, change
implemented backend behaviour; the V3 calendar feature is targeted for V3.

Ownership boundary (canonical):
- **Doc 41 owns Path business logic**, including the Hijri calendar.
- **Doc 30 owns AI routing**; this patch references it rather than restating it.
- **Doc 32 owns the WR**; Path contributions to the WR reference it.

---

### 14-V3 — Hijri Calendar V3 (extends §14)

The §14 Hijri foundation (backend lunar engine, `hijri_date`, white days, Qibla)
remains valid. V3 extends it into a full living calendar.

**Why Hijri stays in The Path (and is the exception).**
Most app calendars (Pulse medical appointments, Vector private-client rides,
etc.) are Gregorian and are therefore centralized in Imperium with no per-app
redundancy. The Path's religious calendar is the **one legitimate exception**: it
runs on the **Hijri (lunar) system**, a different temporality from the Gregorian
grid. Mixing the two in one view would confuse; the Hijri calendar therefore
lives in The Path and feeds Imperium through conversion (below).

**Dual content.**
- **Pre-computed religious dates**: Ramadan, the two Eids, sacred months,
  Ashura, Mawlid, white days, etc.
- **User personal religious events**: lessons (dars), reminders, personal
  observances the user adds.

**Lunar observation, not pure astronomical calculation.**
Religious-date determination follows **real lunar observation** (more
religiously accurate), not a purely astronomical calculation. Consequence: the
start of a lunar month (hence Ramadan, the Eids…) is not fixed with certainty in
advance — it is confirmed at/around the eve.

- **Manual confirmation.** The user confirms the date themselves when the
  observation is made. (No external authority feed is assumed in V3; a future
  enrichment could add one, consistent with the existing §14 note about an
  optional external calendar API.)

**Duplicate-date mechanic (handling the ±1 day uncertainty).**
Until a date is confirmed, it appears **as a duplicate** — both candidate days
(J and J+1) are shown. When the user confirms the observation, the **incorrect
duplicate disappears**, leaving only the true date. This makes the uncertainty
explicit instead of asserting a false certainty, and resolves cleanly on
confirmation. It also keeps Imperium from being filled with stale candidates.

**Bridge to Imperium (conversion).**
All religious dates — major dates AND personal additions — **flow up to Imperium,
converted to Gregorian**, so Imperium (which plans on the Gregorian grid) can
plan around religious life (e.g. adapt the rhythm during Ramadan, anticipate an
Eid). The Path owns the Hijri calendar; Imperium receives a converted,
Gregorian view as one more data source — analogous to how a specialist owns a
domain but feeds the WR.

**Display window vs AI knowledge (general principle).**
This is a principle that applies across the whole ecosystem, stated here
because the calendar makes it concrete:

```text
DISPLAY  : Imperium surfaces Hijri-derived dates to the USER over a rolling
           2-week window only (ergonomics, anti-overload), with duplicates
           until confirmation.
KNOWLEDGE: the unified brain (the AI) has access to ALL ecosystem data at ALL
           horizons, always. The 2-week limit is a display filter only — it
           never limits what the AI knows.
```

So the WR (which plans 4 weeks ahead, doc 32) plans with full knowledge of every
religious date at any horizon, even those not shown on screen. One never asks
"does the AI see this date?" — it sees everything stored in the backend. One only
asks "what do we show the user?" — and there, 2 weeks.

**Endpoints (extends the §14 TBD set).**
```text
TBD GET  /api/path/calendar/hijri          (existing)
TBD GET  /api/path/calendar/events         (religious dates + personal, with status)
TBD POST /api/path/calendar/events         (add a personal religious event)
TBD POST /api/path/calendar/confirm-date   (manual lunar-observation confirmation)
```
Date records carry a status: `predicted` (duplicated J / J+1) → `confirmed`
(single true date) after manual confirmation.

---

### 15-REV — Path AI Task Types & Routing (replaces §15 model lines)

Path remains overwhelmingly deterministic; AI is rarely needed (prayer times are
calculated/fetched, sadaqa is arithmetic, ghusl is event-based, adhkar is
counting). Routing is governed by **doc 30**; this section states only the Path
specifics.

```text
path.weekly_review_contribution  - feeds the WR (see doc 32; WR routing per doc 30)
path.routine_adjustment          - rare, "should I adapt my adhkar routine?"
path.sadaqa_strategy             - rare, deep advice
```

Routing distribution (aligned with doc 30):

```text
Daily ops (~98%):           Qwen 32B local OR backend deterministic
Rare adaptations:           escalate via the /200 score (doc 30 §5) — typically Sonnet 4.6
Strategic spiritual advice: Opus 4.8 (doc 30); Fable 5 only if long + complex + durable
Cost per month:             still < 0.50 € (AI rarely invoked)
```

Changes vs the former §15:
- **Haiku 4.5 removed** (no longer in the hierarchy; the local Qwen 32B covers the
  low band — doc 30 §0).
- **Opus 4.7 → Opus 4.8**.
- WR contribution routing is **delegated to doc 30/32**, not fixed to a model here.

---

### 16.1-ADD — Path → Imperium: religious calendar events

Add to the backend append-only events that Imperium READS (§16.1):

```text
  - path.calendar.date_predicted   → Imperium shows duplicated candidate (J / J+1)
                                      within the 2-week display window
  - path.calendar.date_confirmed   → Imperium drops the incorrect duplicate,
                                      keeps the true Gregorian-converted date,
                                      and may replan around it
  - path.calendar.event_added      → personal religious event flows up
                                      (Gregorian-converted) for planning awareness
```

The unified brain consumes all of these at any horizon regardless of the 2-week
display window (see the display-vs-knowledge principle in 14-V3).
