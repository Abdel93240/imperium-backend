# 41 - The Path Logic Detail

## 1. Purpose

The Path is the worship, prayer, fasting, sadaqa, Quran, adhkar, and ghusl
interface. It collects explicit user actions, displays operational worship
signals, and triggers backend workflows that Imperium may use for planning.

The Path is not a religious authority. It does not issue rulings, infer worship
completion, infer fasting intention, or infer ghusl requirement.

Canonical sources used by this V1 detail:

- `01_SIGNAL_VARIABLES_DICTIONARY.md`
- `07_ANDROID_APP_RESPONSIBILITIES.md`
- `42_VAULT_LOGIC_DETAIL.md`
- `43_IMPERIUM_LOGIC_DETAIL.md`
- `59_DESIGN_SYSTEM_V1_DRAFT.md`

## 2. Authority Boundary

Android screens may create local drafts with `pending|syncing|synced|failed|conflict`
labels, but the backend remains the authority for canonical records.

V1 rules:

- All Path writes require explicit user action and backend validation.
- All mutation endpoints require `Idempotency-Key`.
- Private religious data is local-first unless a privacy gate authorizes a
  specific external model call.
- Imperium can replan from Path events, but the event source remains Path and the
  final mission plan remains Imperium-owned.
- Vault receives confirmed sadaqa donations as personal expenses, but Path owns
  sadaqa percentage, weekly target, carry, and donation intent.
- Pulse receives fasting constraints from Path; Pulse does not decide fasting.

## 3. Events

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

## 4. Prayer Times, MAWAQIT, And Calculation Engine

### 4.1 Source Of Truth

Path displays the five obligatory prayers in V1:

```text
Fajr, Dhuhr, Asr, Maghrib, Isha
```

Sunnah, Rawatib, Tahajjud, Duha, and Witr are V2 routine candidates and are not
counted by V1 prayer status. This avoids inventing obligation scope.

Path uses this source order:

1. Registered default mosque MAWAQIT times when available and fresh.
2. Nearest registered mosque MAWAQIT times when user explicitly allows GPS use.
3. Offline cached MAWAQIT times.
4. Local calculation engine.

### 4.2 MAWAQIT Rules

V1 uses a backend MAWAQIT HTTP adapter. The exact provider URL/API credential is
environment-specific and must be configured through secrets, not code.

Cache rules:

- Cache daily prayer times per registered mosque for 30 days.
- Refresh default mosque daily at 03:00 UTC.
- Refresh on manual user request from PAT-08 or PAT-09.
- Stale cache can display for up to 48 hours with a Warning chip.
- After 48 hours stale, UI must show fallback calculation as primary and stale
  MAWAQIT as historical context only.

Conflict and selection rules:

- A user-selected default mosque wins over nearest mosque.
- If no default exists, the nearest registered mosque may be suggested but not
  silently registered.
- `nearby_mosque_id` is a GPS suggestion; PAT-09 registration is explicit user
  confirmation.
- Two registered mosques with conflicting times are displayed separately; PAT-01
  uses the default mosque or prompts the user to choose one.

Privacy rules:

- Mosque names, mosque IDs, and frequent GPS-derived mosque patterns are
  `very_high` privacy when linked to the user.
- GPS is sent to the backend only after permission and only for mosque search,
  qibla calculation, or registered-address distance display.
- External model calls receive no mosque names, addresses, or GPS unless a
  privacy gate explicitly allows a summarized use case.

### 4.3 Fallback Calculation Engine

If MAWAQIT is unavailable, Path uses a backend calculation engine equivalent to
Adhan with:

| Setting | V1 default | User setting |
|---|---|---|
| Calculation method | `MuslimWorldLeague` | PAT-11b |
| Madhhab / Asr rule | `Shafi` | PAT-11c |
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

If GPS is denied and no city is configured, PAT-01 shows an Empty/Warning state
that asks the user to configure city or mosque. It must not invent times.

## 5. Prayer Marking Logic

PAT-02 is the only V1 prayer marking surface.

Allowed actions:

- `accomplished`
- `not_marked_as_accomplished`
- `clear_status`

Rules:

- Only the five obligatory prayers are represented in V1.
- Prayer completion is never inferred from location, time, calendar, or phone
  activity.
- A future prayer cannot be marked as `not_marked_as_accomplished`.
- A prayer can be marked accomplished at any time by explicit user correction.
- The UI label can say `Non marquee comme accomplie`; it must not present itself
  as a religious judgment.
- Discipline impact is backend-calculated from explicit `not_marked_as_accomplished`
  events, never from silence alone.
- Post-prayer adhkar may be suggested after an accomplished mark, but it is not
  auto-completed.

Offline conflict:

- Same prayer/day/status with same `Idempotency-Key` dedupes.
- Different status for the same prayer/day opens a conflict sheet.
- Latest server state does not silently overwrite a local explicit correction.

Endpoint contract:

```text
TBD POST /api/path/prayers/{prayer_slug}/mark
Headers: Idempotency-Key
Payload: status, prayed_at, source, optional_note
```

## 6. Fasting Logic

Supported `fasting_type` values:

```text
monday_thursday, white_days, ramadan, custom, temporary
```

V1 fasting rules:

- A fast starts only when the user confirms PAT-05.
- Ramadan and white days can show preparation banners from lunar calendar data,
  but they do not auto-start a fast.
- `white_days_active=true` suggests a temporary fast; it does not create one.
- `suhoor_time` and `iftar_time` come from the selected prayer-time source.
- Ending a fast at iftar still requires user confirmation.
- Breaking a fast requires explicit confirmation; optional reason text is allowed
  but not required.
- `path.fasting.broken` opens a user-confirmed Imperium replan prompt.

Pulse handoff:

- While fasting is active and daytime drinking is disabled, Path sends
  `hydration_limits={"daytime":false}` to Pulse.
- PAT-05 shows a `Pulse adjusted` handoff toast only after backend acceptance.

Endpoint contracts:

```text
TBD POST /api/path/fasting/start
TBD POST /api/path/fasting/end
TBD POST /api/path/fasting/break
Headers: Idempotency-Key
```

Offline conflict:

- Start/end/break mutations are synced in local creation order.
- Server-active fast plus local start opens conflict.
- Local start followed by local break syncs as two ordered mutations.

## 7. Sadaqa Logic

### 7.1 Weekly Target

Sadaqa percentage is owned by Path. Vault exposes it read-only and deep-links to
PAT-11d.

V1 formula:

```text
sadaqa_weekly_target = max(vault_weekly_business_profit, 0) * sadaqa_percentage
effective_weekly_target = sadaqa_weekly_target + sadaqa_remaining_carry_from_previous_weeks
```

Default `sadaqa_percentage` is `0.05` and the V1 editable range is `0.01` to
`0.20`. User changes are allowed once per week without extra confirmation. A
second change in the same week opens a confirmation dialog explaining that the
new value affects future targets only.

Target recomputation:

- Weekly profit changes recompute the current week target.
- Sadaqa percentage changes are prospective by default.
- Past donation records are never recalculated.
- Carry is recomputed only from confirmed donations and weekly target snapshots.

### 7.2 Carry Behavior

Rules:

- Partial donation leaves remaining carry for the next week.
- Overpayment reduces existing carry first, then creates no negative spiritual
  debt display.
- Multi-week catch-up is logged as one donation with allocation lines generated
  by backend from oldest carry to newest target.
- PAT-01 shows a persistent carry banner only when carry is greater than 0.
- UI wording uses `montant reporte` or `reste a donner selon ton objectif`, not
  language that implies a religious ruling.

### 7.3 Sadaqa Donation Flow

PAT-03 fields:

- amount
- destination
- optional note
- date
- optional voice note transcript

Submission creates:

1. Path donation record.
2. Vault personal expense handoff with category `Sadaqa`.

The Vault handoff is automatic after confirmed Path donation because doc 42 says
Vault receives Path sadaqa donations as personal expenses. If Vault creation
fails, Path donation remains saved and PAT-03/PAT-01 shows `Vault transaction
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

## 8. Ghusl Logic

### 8.1 Ghusl Required Activation

PAT-04 is the only V1 activation/completion surface.

Rules:

- Ghusl requirement is never inferred.
- Activation and completion are both explicit user actions.
- Activation stores `ghusl_required_since` and may create `ghusl_mission_id`.
- Imperium receives `path.ghusl.required` and may create the mission
  `Faire le ghusl avant Asr` or the next relevant prayer anchor.
- PAT-04 shows `Imperium replanning...` only as a handoff state, not as final
  mission confirmation.
- PAT-01 shows a banner when a mission id is created.

Endpoint contracts:

```text
TBD POST /api/path/ghusl/activate
TBD POST /api/path/ghusl/complete
Headers: Idempotency-Key
```

### 8.4 Registered Ghusl Addresses

Registered ghusl address schema V1:

| Field | Rule |
|---|---|
| `ghusl_address_id` | Backend generated. |
| `label` | User label, required. |
| `type` | `home|mosque|gym|work|other`. |
| `address_text` | Optional manual address. |
| `latitude` / `longitude` | Optional, explicit GPS only. |
| `is_default` | At most one true. |
| `privacy_level` | `very_high`. |

Endpoint contracts:

```text
TBD GET /api/path/ghusl-addresses
TBD POST /api/path/ghusl-addresses
TBD PATCH /api/path/ghusl-addresses/{address_id}
TBD DELETE /api/path/ghusl-addresses/{address_id}
Headers for mutations: Idempotency-Key
```

Offline conflict:

- Activation followed by completion syncs in order.
- Server-completed plus local activation opens a conflict sheet.
- Address edits use version conflict detection; no silent overwrite.

## 9. Adhkar Routines

Supported `adhkar_type` values:

```text
morning, evening, istighfar, salawat, tasbih, tahmid, takbir, personal
```

V1 routines:

- Maximum 8 active routines.
- Default suggested routines can exist, but user activation is explicit.
- Counter supports tactile +1 as the canonical input.
- Voice counting through Whisper/faster-whisper is optional in V1 and must
  display confidence; low confidence requires user validation.
- Arabic text can render with Noto Naskh Arabic, plus transliteration and
  optional translation when configured.
- Post-prayer routine suggestion may appear after PAT-02 accomplished, but no
  adhkar completion is inferred.

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

Offline conflict:

- Distinct increment keys use merge sum.
- Same key dedupes.
- Routine edits use version conflict.
- Reset conflicts with queued increments open a review sheet.

## 10. Quran Progress

PAT-07 stores the user's validated continuation point.

V1 fields:

- `quran_page` from 1 to 604
- `quran_juz`
- `quran_hizb`
- `quran_surah`
- `quran_last_validated_point`
- `quran_daily_objective`

Rules:

- User can enter page, surah, or juz through PAT-07b selector.
- Backend normalizes page/juz/hizb/surah mapping.
- A lower page than the last validated point requires confirmation.
- Quran completion is never inferred from time spent or screen activity.
- Khatm milestone is informational and user-confirmed.

Endpoint contracts:

```text
TBD GET /api/path/quran/continuation
TBD POST /api/path/quran/progress
TBD PATCH /api/path/quran/objective
Headers for mutations: Idempotency-Key
```

Offline conflict:

- Same key dedupes.
- Higher server point plus lower local point opens regression confirmation.
- Higher local point can update after backend validation.

## 11. Discipline Contribution

Path can feed Imperium discipline context only from explicit user-confirmed
events.

Rules:

- `path.prayer.not_marked` may affect discipline score, but silence never does.
- `path.fasting.broken` may trigger replanning, not guilt messaging.
- `path.adhkar.incremented` and Quran progress contribute as discipline signals
  only after backend acceptance.
- UI wording must stay operational and non-judgmental.

## 12. Hijri, White Days, And Qibla

Hijri calendar V1 uses a backend lunar calendar engine. A configured external
calendar API may enrich it, but if unavailable the UI shows calculated data with
source and confidence.

Rules:

- `hijri_date` appears on PAT-01 top summary and PAT-05 fasting context.
- `white_days_active` shows a fasting suggestion banner, never an automatic fast.
- Qibla direction is V1 informational in PAT-01 and PAT-08 when location is
  available.
- Qibla compass sensor permission is requested only when the user opens the
  compass widget or screen.

Endpoint contracts:

```text
TBD GET /api/path/calendar/hijri
TBD GET /api/path/qibla
```

## 13. Religious Data Privacy Policy

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
- Vector memory stores summary-only fields where the dictionary permits it; no
  raw donation destination, ghusl address, or mosque pattern is embedded.
- Error messages must not expose sensitive religious details.

## 14. Offline And Conflict Summary

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

## 15. UI Surface

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

Internal V1 sub-surfaces are confirmed but not counted as new top-level screens:

- PAT-06b Adhkar Routine Configuration
- PAT-07b Quran Surah/Juz/Page Picker
- PAT-09b Add Mosque Sub-Flow
- PAT-10b Add Ghusl Address Sub-Flow
- PAT-11b Calc Method Selector
- PAT-11c Madhhab Selector
- PAT-11d Sadaqa Percentage Detail
- PAT-11e Adhkar Routines Manager
- PAT-11f City / Location Selector

These sub-surfaces are drawers, dialogs, side panes, or inline states. The V1
screen count remains 62.
