# 12 - Daily Objective and Period Logic

## Purpose

This document defines the exact logic for:
- daily objective calculation
- weekly objective calculation
- useful workday calculation
- financial period boundaries

Core principle:

> The system must calculate real operational objectives, not fake dashboard targets.

Objectives must adapt to remaining obligations, real available work capacity, fatigue, schedule reality, VTC constraints, family constraints, and religious constraints.

Do not use fixed arbitrary targets.

## Primary Financial Period

Operational logic uses the weekly period first.

Reason:
- VTC work is managed weekly
- work intensity decisions happen inside the current week
- fuel, leasing, school payments, and urgent expenses affect the current work window

Monthly view exists for reporting only.

Monthly reporting must not drive daily operational pressure unless a monthly obligation is due inside the current week.

## Definition of Week

Default operational week:

```text
Monday 00:00 -> Sunday 23:59
```

Rules:
- calculate week boundaries in `users.timezone`
- store timestamps in UTC
- store `week_start_date`, `week_end_date`, and `timezone`
- V1 default is Monday start
- week start can become configurable later if VTC reality requires it

## Definition of Operational Day

VTC work may continue late at night.

The system must not use naive midnight reset.

Default rule:

```text
The operational day starts when user starts the day.
The operational day ends when user presses Finish Day.
```

An operational day can therefore last MORE than 24 hours (it is bounded by
start→finish, never by a midnight reset). This is not a problem: it simply means
following days may be shorter (e.g. a 6-hour day after a long one). The
ecosystem reasons in operational days, not calendar days.

Late-night VTC handling:
- a VTC session finishing at `03:30` may belong to the previous operational day if the day session is still open
- revenue, mission outcomes, fatigue, and daily snapshot attach to the open operational day
- if no operational day is open, fallback rules decide the safest assignment

Recommended operational day fields:
- `operational_day_id`
- `user_id`
- `day_session_id`
- `started_at`
- `finished_at`
- `operational_date`
- `timezone`
- `closure_method`

Closure methods:
- `manual_finish_day`
- `auto_fallback_inferred`
- `admin_correction`

## Finish Day Button

The official end of day is:

> user presses `Finish Day`

This closes:
- workday
- mission cycle
- daily review
- daily financial snapshot

When user presses `Finish Day`:
1. backend validates active day session
2. backend stores `day.finished`
3. backend closes day session
4. backend creates daily financial snapshot
5. backend stores mission/day summary
6. backend triggers n8n day finished workflow if needed
7. objective logic recalculates remaining week targets

The Finish Day button is the truth source when available.

## Automatic Fallback Closure

If user forgets `Finish Day`, the system must safely infer fallback closure without corrupting logic.

Fallback conditions:
- active day session remains open past a configured maximum duration
- no user activity for a long inactivity window
- next day is started while previous day is still active
- weekly boundary is approaching and previous day is stale

Recommended V1 fallback:

```text
If day session is active for more than 20 hours
AND no active VTC session is detected
AND no app activity for 6 hours,
mark day as fallback-closed.
```

If a new day starts while old day is active:
1. backend closes previous day with `closure_method = auto_fallback_inferred`
2. backend stores warning in day summary
3. backend starts new day
4. user can later correct if needed

If active VTC session exists:
- do not auto-close unless the session is stale beyond a stricter threshold
- keep warning visible

Fallback must:
- never delete events
- never silently reassign money without trace
- create an event
- lower confidence of the daily snapshot
- be visible in Imperium/The Vault if relevant

Fallback thresholds are TODO and must be configurable.

## Useful Workdays

Not all remaining days are equal.

Calculate:

```text
remaining_useful_workdays
```

Based on:
- actual availability
- appointments
- family constraints
- sleep debt
- maintenance needs
- expected rest requirement
- Friday/Jumu'ah constraints if relevant
- prayer constraints
- high fatigue
- known blocked periods

Do not assume every calendar day is usable.

### Useful Workday Weighting

A useful workday does not have to equal `1.0`.

Recommended V1 weights:

| day state | weight |
|---|---:|
| full available workday | 1.0 |
| partial workday | 0.5 |
| short/limited workday | 0.25 |
| unavailable day | 0 |
| forced recovery day | 0 |
| maintenance day | 0 or 0.25 |
| spiritual/family priority day | 0 or 0.25 |
| exceptional strong workday | 1.25 |

Formula:

```text
remaining_useful_workdays =
  sum(useful_workday_weight for remaining operational days in week)
```

The system should explain why a day has reduced weight.

## Realistic Daily Capacity

Daily objective logic uses realistic earning capacity, not fantasy income.

Realistic daily capacity should consider:
- recent VTC daily performance
- fatigue
- available hours
- active financial pressure
- known high-demand windows
- vehicle/fuel status
- sleep debt
- family/religious constraints

Recommended base:

```text
realistic_daily_capacity =
  recent_realistic_vtc_daily_average
  * capacity_adjustment_factor
```

Capacity adjustment examples:
- high fatigue: reduce
- partial day: reduce
- strong Saturday night: increase
- maintenance day: reduce to 0

Exact capacity model: TODO.

## Weekly Objective Calculation

Weekly objective is based on remaining required money for the operational week.

Inputs:
- current weekly obligations
- upcoming required expenses due in the week
- overdue expenses
- fuel required
- exceptional required expenses
- available liquidity
- current week income
- remaining useful workdays
- realistic capacity

Formula:

```text
weekly_remaining_required_money =
  max(0, required_money_this_week - available_liquidity)
```

Weekly target state:

```text
weekly_minimum_remaining = weekly_remaining_required_money
weekly_comfortable_remaining = weekly_remaining_required_money + stability_buffer
weekly_optimal_remaining = weekly_remaining_required_money + strategic_buffer
```

Buffers:
- `stability_buffer`: small margin to reduce next-day stress
- `strategic_buffer`: stronger margin for future costs

Exact buffer formula: TODO.

## Daily Objective Calculation

Define:
- `daily_minimum_target`
- `daily_comfortable_target`
- `daily_optimal_target`

These must be derived from:

```text
remaining_required_money / remaining_useful_workdays
```

Then adjusted by:
- realistic earning capacity
- fatigue
- current pressure
- known exceptional expenses

### Minimum

Purpose:
- survival + obligations
- avoid deterioration

Formula:

```text
daily_minimum_target =
  remaining_required_money
  / max(0.25, remaining_useful_workdays)
```

If `remaining_useful_workdays = 0`:
- daily minimum is not realistically achievable
- pressure should be critical if remaining required money > 0
- explanation must say capacity is unavailable

### Comfortable

Purpose:
- healthy sustainable week
- reduce pressure without pretending unlimited energy

Formula:

```text
daily_comfortable_target =
  min(
    realistic_daily_capacity,
    daily_minimum_target * 1.35
  )
```

If pressure is critical and user has capacity:

```text
daily_comfortable_target =
  min(
    realistic_daily_capacity * 1.15,
    daily_minimum_target * 1.35
  )
```

### Optimal

Purpose:
- strategic improvement
- buffer building
- secure future costs

Formula:

```text
daily_optimal_target =
  min(
    realistic_daily_capacity * 1.25,
    daily_minimum_target * 1.75
  )
```

Optimal must not be presented as mandatory.

If minimum is already secured:
- optimal becomes optional buffer building
- Imperium may recommend stopping if health/fatigue risk is high

## Stretch Logic

Do not confuse minimum and optimal.

Minimum:
- survival
- current obligations
- prevent deterioration

Comfortable:
- sustainable week
- less pressure tomorrow
- realistic workload

Optimal:
- strategic improvement
- buffer
- opportunity capture

The system must label these clearly.

## Override Rules

User must be able to mark:
- today unavailable
- exceptional workday
- family emergency
- maintenance day
- spiritual priority day
- forced recovery day

Each override must:
- create an event
- store `objective_override_reason`
- recalculate useful workdays
- recalculate daily/weekly objectives
- appear in the explanation

Override effects:

| override | typical useful day effect |
|---|---:|
| today unavailable | 0 |
| exceptional workday | 1.25 |
| family emergency | 0 or 0.25 |
| maintenance day | 0 or 0.25 |
| spiritual priority day | 0 or 0.25 |
| forced recovery day | 0 |

## Relationship With Imperium

Imperium must use real objective logic, not static target obsession.

If pressure is high:
- Imperium may recommend stronger work priority

But if minimum is already secured and health risk is high:
- Imperium may recommend stopping work
- Imperium may recommend recovery
- Imperium may recommend family/religious priority

Example:

```text
Minimum secured.
Fatigue high.
No urgent obligations left today.
Recommendation: stop VTC session and recover.
```

Pressure and objectives are signals, not tyrants.

## Relationship With Vector

Vector uses daily objective status to decide:
- continue session
- reposition aggressively
- return home
- accept lower-quality but necessary rides

Vector interpretation:
- below minimum: protect floor, consider necessary rides
- between minimum and comfortable: prioritize reliable earning
- comfortable reached: become more selective
- optimal reached: return home or stop may be valid

Vector must not:
- assume gross revenue = success
- push work beyond strategic value
- ignore fatigue
- violate platform rules

## Non-Negotiables

Never:
- assume every day is workable
- assume gross revenue = success
- punish recovery days as failure
- push work beyond strategic value
- use fixed arbitrary targets
- reset operational day blindly at midnight
- count expected future income as guaranteed money

## Storage

### `operational_day_id`

Purpose:
- identifies the real operational day, independent of naive calendar midnight

Recommended fields:
- `operational_day_id`
- `user_id`
- `day_session_id`
- `operational_date`
- `started_at`
- `finished_at`
- `closure_method`
- `timezone`

### `daily_objective_snapshot`

Purpose:
- stores objective calculation for an operational day

Recommended fields:
- `id`
- `user_id`
- `operational_day_id`
- `week_start_date`
- `remaining_required_money`
- `remaining_useful_workdays`
- `realistic_daily_capacity`
- `daily_minimum_target`
- `daily_comfortable_target`
- `daily_optimal_target`
- `current_pressure_score`
- `objective_status`
- `objective_factors` jsonb
- `confidence_level`
- `created_at`

### `weekly_objective_snapshot`

Purpose:
- stores weekly objective context

Recommended fields:
- `id`
- `user_id`
- `week_start_date`
- `week_end_date`
- `required_money_this_week`
- `available_liquidity`
- `weekly_remaining_required_money`
- `remaining_useful_workdays`
- `weekly_minimum_remaining`
- `weekly_comfortable_remaining`
- `weekly_optimal_remaining`
- `weekly_objective_factors` jsonb
- `created_at`

### `useful_workdays_remaining`

Purpose:
- computed sum of weighted remaining workdays

Type:
- numeric

Stored in:
- daily objective snapshot
- weekly objective snapshot

### `objective_override_reason`

Purpose:
- explains user/system override affecting objective logic

Examples:
- `today_unavailable`
- `exceptional_workday`
- `family_emergency`
- `maintenance_day`
- `spiritual_priority_day`
- `forced_recovery_day`

Must be event-backed.

## Example Cases

### Case A - Normal stable week

Context:
- Monday start
- 5 useful workdays left
- remaining required money = 500
- realistic daily capacity = 220
- fatigue normal

Calculation:

```text
remaining_useful_workdays = 5
daily_minimum = 500 / 5 = 100
daily_comfortable = min(220, 100 * 1.35) = 135
daily_optimal = min(275, 100 * 1.75) = 175
```

Meaning:
- minimum is manageable
- work target should be realistic, not aggressive

### Case B - Saturday night strong earning opportunity

Context:
- Saturday evening
- remaining required money = 260
- Saturday night is strong demand
- Sunday partially available
- useful weights: Saturday night `1.25`, Sunday `0.5`
- realistic capacity = 260

Calculation:

```text
remaining_useful_workdays = 1.75
daily_minimum = 260 / 1.75 = 149
daily_comfortable = min(260, 149 * 1.35) = 201
daily_optimal = min(325, 149 * 1.75) = 261
```

Meaning:
- Vector may recommend continuing because opportunity is strong
- if optimal reached, return home becomes valid

### Case C - Heavy fatigue + only 2 useful workdays left

Context:
- remaining required money = 600
- 2 calendar days left
- heavy fatigue reduces one day to 0.25
- one day is normal at 1.0
- realistic daily capacity reduced to 170

Calculation:

```text
remaining_useful_workdays = 1.25
daily_minimum = 600 / 1.25 = 480
daily_comfortable = min(170, 480 * 1.35) = 170
daily_optimal = min(212.5, 480 * 1.75) = 212.5
```

Meaning:
- objective is not realistically solvable through normal work
- pressure explanation must say capacity is insufficient
- Imperium must not punish fatigue as failure

### Case D - Low income but Sunday still available

Context:
- current income low
- remaining required money = 300
- Sunday available as partial workday
- useful workdays = 0.75
- realistic daily capacity = 240

Calculation:

```text
daily_minimum = 300 / 0.75 = 400
daily_comfortable = min(240, 400 * 1.35) = 240
daily_optimal = min(300, 400 * 1.75) = 300
```

Meaning:
- Sunday helps but does not fully solve the week
- Vector may protect guaranteed revenue
- the system should explain the gap instead of inventing comfort

### Case E - Good week already secured, early stop justified

Context:
- remaining required money = 0
- weekly minimum secured
- fatigue high
- no urgent obligation
- prayer/family/rest priority high

Calculation:

```text
daily_minimum = 0
daily_comfortable = 0
daily_optimal = optional buffer only
```

Meaning:
- Imperium may recommend stopping work
- Vector may recommend return home
- recovery is not failure

## Open Decisions

TODO:
- exact fallback closure thresholds
- exact realistic daily capacity formula
- exact workday weight formula
- exact confidence scoring
- exact weekly buffer formula
- exact storage table names for objective snapshots

