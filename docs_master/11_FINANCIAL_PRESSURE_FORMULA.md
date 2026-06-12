# 11 - Financial Pressure Formula

## Purpose

This document defines the V1 deterministic formula for Financial Pressure Score.

Core principle:

> Financial pressure must not be a vague feeling.

It must be transparent, explainable, deterministic, and understandable by the user.

Do not use black-box AI scoring for V1. AI may explain the score in natural language, but it must not invent the score.

## Product Goal

The score exists to:
- help Imperium decide work intensity
- help Vector decide VTC urgency
- help The Vault show real pressure
- prevent fake comfort
- prevent fake panic

The score must always answer:

> Why is the system saying pressure is safe, stable, attention, pressure, or critical?

## Weekly Philosophy

The system thinks weekly first.

Reason:
- VTC reality is weekly
- fuel, leasing, school payments, and urgent expenses affect the current work week
- daily operational decisions need current-week clarity

Monthly view may exist for strategic reporting. Daily operational decisions use weekly pressure.

## Recurring-Expenses List (User Truth)

There is a user-maintained **recurring-expenses list**, shown on the Vault dashboard, 100% editable by the user. It is the **source of truth** for declared obligations. The AI READS it and never judges whether a declared expense is "required" — the user already decided that by putting it in the list.

Each entry has:
- `label` (dénomination)
- `recurrence` (weekly / monthly / quarterly / yearly …)
- `amount` (prix)
- `category` (dropdown: family, work, … with an "Other" option that opens a free text box for exceptional cases)
- `payment_day_of_month` — the day the payment is actually due

Because the list is user-owned truth, no AI classification applies to its entries. They are required, period.

## Two Distinct Uses of Expenses: Smoothed Objective vs Real Pressure

These are different notions and must not be conflated.

- **Smoothed objective (how much to EARN).** Recurring expenses are *smoothed* across the period to tell the AI the earning rhythm the user must sustain (e.g. a 200€/month school fee informs a ~50€/week earning target). This is a TARGET, used to set daily/weekly earning goals.
- **Real pressure (what the user actually HAS).** Financial pressure is NOT computed on the smoothed theoretical figure. It is computed on the user's **real money** in the Vault wallets, confronted with what must actually go out (via `payment_day_of_month`). Pressure is anchored in reality, never in a provision that may not exist.

This avoids both a false sense of security and double-counting.

## Classification Scoring — ONLY for Expenses NOT in the List

The recurring-expenses list covers the *known*. But unplanned/exceptional expenses appear that the user did not pre-declare. For THOSE (and only those), a scoring guides the AI to classify them as *required* vs *deferrable* — so the AI is guided, never left to invent freely.

```text
If expense ∈ recurring-expenses list → REQUIRED (user truth, no scoring).
Else → classification scoring:
  + vital nature (housing, food, health, children's school) → strong "required"
  + legal/contractual consequence if unpaid (leasing, taxes, fines) → required
  + due inside the operational window → required
  + deferrable without consequence → deferrable
```

**Hard rule:** vital categories (housing, food, health, children's schooling, legal obligations) can NEVER be classified deferrable by the AI alone. The scoring guides ambiguous cases; it cannot downgrade a vital expense.

This couples cleanly with doc 30: financial reasoning is GPT-5.5's domain, and GPT-5.5 must surface its reasoning / flag uncertainty rather than fabricate a classification.

## Core Inputs

The user-maintained recurring-expenses list (see above) is a first-class input source.

Required V1 inputs:
- `current_week_income`
- `expected_week_income`
- `fixed_weekly_charges`
- `upcoming_required_expenses`
- `overdue_expenses`
- `current_wallet_available_cash`
- `current_bank_available_balance`
- `fuel_required_next_days`
- `minimum_survival_threshold`
- `number_of_remaining_work_days`
- `daily_minimum_target`
- `daily_comfortable_target`
- `daily_optimal_target`

Conditional required inputs (these feed `conditional_required_expenses`; sourced from the recurring-expenses list, each carrying its `payment_day_of_month`):
- `family_exceptional_expense`
- `school_payment_due`
- `rent_proximity`
- `leasing_payment_proximity`
- `urgent_maintenance_cost`

`available_liquidity` = CB wallet (`current_bank_available_balance`) + cash wallet (`current_wallet_available_cash`), crypto excluded — all three wallets being Vault dashboard wallets.

## Output

Output field:
- `financial_pressure_score`

Range:
- `0` to `100`

Interpretation:

| score range | label | meaning |
|---|---|---|
| 0-20 | safe | Obligations are covered with margin. |
| 21-40 | stable | Current week is under control. |
| 41-60 | attention | Some risk exists; watch spending/work plan. |
| 61-80 | pressure | Work intensity or financial caution likely needed. |
| 81-100 | critical | Obligations exceed realistic capacity or liquidity is dangerously low. |

Canonical labels:
- `safe`
- `stable`
- `attention`
- `pressure`
- `critical`

## V1 Formula Overview

V1 pressure is based on:

```text
remaining_required_money / remaining_realistic_earning_capacity
```

Then deterministic modifiers are added for:
- overdue expenses
- very low available cash
- urgent fixed charges
- exceptional required expenses

No AI weighting in V1.

## Step 1 - Available Liquidity

Available liquidity is the sum of the **stable** Vault wallets:

```text
available_liquidity =
  current_bank_available_balance    # CB wallet
  + current_wallet_available_cash   # cash wallet
```

Rules:
- include only money actually available
- do not count expected future income as available
- do not count uncertain payments as available

The **crypto wallet is EXCLUDED** from survival pressure. Rationale: crypto is volatile and not instantly/cost-free liquidatable; counting it would inflate perceived safety. Crypto is displayed separately in Vault as a **mobilizable reserve** (a last-resort cushion), but it does not enter the pressure calculation. Needing to sell crypto to cover an obligation is itself a tension signal, not a "safe" state.

(If the user ever wants to explicitly mobilize crypto, that is a deliberate user action, not an automatic inclusion.)

## Step 2 - Required Money This Week

```text
required_money_this_week =
  fixed_weekly_charges
  + upcoming_required_expenses
  + overdue_expenses
  + fuel_required_next_days
  + conditional_required_expenses    # (was optional_required_expenses)
```

Definition: `conditional_required_expenses` are required expenses that do **not** occur every week but ARE required when they fall due (e.g. monthly school fee, quarterly tax). They come FROM the recurring-expenses list — not from any AI judgment. "Conditional" = conditional on timing, never on importance.

Where:

```text
conditional_required_expenses =
  family_exceptional_expense
  + school_payment_due
  + urgent_maintenance_cost
  + urgent rent/leasing proximity amounts if due inside the operational window
```

Rules:
- include required expenses only
- do not include vague wishes
- do not include postponed expenses if user marked them postponed
- do not include handled expenses if user marked them handled

## Step 3 - Remaining Required Money

```text
remaining_required_money =
  max(0, required_money_this_week - available_liquidity)
```

This is how much money is still required after using real available liquidity.

## Step 4 - Remaining Realistic Earning Capacity

Do not assume infinite work capacity.

```text
remaining_realistic_earning_capacity =
  number_of_remaining_work_days
  * realistic_daily_capacity
```

`realistic_daily_capacity` should be based on:
- recent real VTC results
- fatigue-aware capacity
- known schedule constraints
- health/sleep constraints
- prayer/family constraints
- realistic time left in the week

Do not use fantasy income.

Example:

```text
realistic_daily_capacity = 220
number_of_remaining_work_days = 3
remaining_realistic_earning_capacity = 660
```

If capacity is unknown:
- use conservative estimate from recent real days
- mark confidence lower
- explain uncertainty

## Step 5 - Base Pressure Ratio

```text
base_pressure_ratio =
  remaining_required_money / max(1, remaining_realistic_earning_capacity)
```

Use `max(1, capacity)` to avoid division by zero.

If `remaining_realistic_earning_capacity = 0` and `remaining_required_money > 0`, pressure should become critical after modifiers.

## Step 6 - Base Score

```text
base_score = clamp(base_pressure_ratio * 100, 0, 100)
```

Examples:
- ratio `0.10` -> base score `10`
- ratio `0.45` -> base score `45`
- ratio `0.90` -> base score `90`
- ratio `1.20` -> base score `100`

## Step 7 - Deterministic Modifiers

### Overdue expenses modifier

```text
if overdue_expenses > 0:
  overdue_modifier = 10
else:
  overdue_modifier = 0
```

If overdue expenses are severe:

```text
if overdue_expenses > 0.5 * remaining_realistic_earning_capacity:
  overdue_modifier = 15
```

### Very low available cash modifier

```text
if available_liquidity < minimum_survival_threshold:
  low_cash_modifier = 10
else:
  low_cash_modifier = 0
```

If available liquidity is near zero:

```text
if available_liquidity <= 0:
  low_cash_modifier = 15
```

### Urgent fixed charge modifier

```text
if urgent_fixed_charges_due_within_3_days > available_liquidity:
  urgent_fixed_charge_modifier = 10
else:
  urgent_fixed_charge_modifier = 0
```

Examples:
- leasing payment in 3 days
- rent soon
- school payment due

### Exceptional required expense modifier

```text
if exceptional_required_expenses > 0:
  exceptional_modifier = 5
else:
  exceptional_modifier = 0
```

If exceptional expenses exceed realistic capacity:

```text
if exceptional_required_expenses > remaining_realistic_earning_capacity:
  exceptional_modifier = 10
```

## Step 8 - Final Score

```text
financial_pressure_score =
  clamp(
    base_score
    + overdue_modifier
    + low_cash_modifier
    + urgent_fixed_charge_modifier
    + exceptional_modifier,
    0,
    100
  )
```

## Step 9 - Label

```text
if score <= 20: label = "safe"
else if score <= 40: label = "stable"
else if score <= 60: label = "attention"
else if score <= 80: label = "pressure"
else: label = "critical"
```

## Daily Objectives

Daily objectives must come from:
- remaining obligations
- remaining useful workdays
- realistic fatigue-aware earning capacity

They must not be arbitrary fixed numbers.

### `daily_minimum_target`

The strict minimum to avoid deterioration.

```text
daily_minimum_target =
  remaining_required_money
  / max(1, number_of_remaining_work_days)
```

Clamp:
- cannot be negative
- should not exceed realistic daily capacity without warning

### `daily_comfortable_target`

The stabilizing target.

```text
daily_comfortable_target =
  min(
    realistic_daily_capacity,
    daily_minimum_target * 1.35
  )
```

If pressure is `critical`, this cap may be lifted with explanation:

```text
daily_comfortable_target =
  min(
    realistic_daily_capacity * 1.15,
    daily_minimum_target * 1.35
  )
```

### `daily_optimal_target`

The strong target to create margin.

```text
daily_optimal_target =
  min(
    realistic_daily_capacity * 1.25,
    daily_minimum_target * 1.75
  )
```

If `daily_minimum_target` is already above realistic capacity:
- show this clearly
- do not pretend the day can solve everything
- label pressure accordingly

## User Trust Rule

Never show only a mysterious number.

The score must explain why pressure is high.

Example:

```text
Pressure elevee car :
- leasing dans 3 jours
- carburant faible
- 2 jours de travail utiles restants
```

The explanation must include:
- main required obligations
- remaining liquidity
- realistic earning capacity
- modifiers applied
- daily objective reasoning

## Manual Correction

User must be able to mark:
- this expense is postponed
- this expense is already handled
- this week is exceptional

Effects:
- postponed expenses are removed from immediate required money but may remain tracked
- handled expenses are removed from pressure calculation
- exceptional week lowers confidence or changes realistic capacity context

Manual corrections must:
- create events
- update pressure snapshot
- be visible in explanation
- not silently erase the original obligation history

## Non-Negotiables

The system must never:
- push unnecessary work because of bad assumptions
- ignore real obligations
- create fake urgency
- assume future income as guaranteed money
- treat expected income as current liquidity
- let AI invent pressure score
- hide why pressure changed

## Storage

### `financial_pressure_score`

Purpose:
- final deterministic score 0-100

Recommended fields:
- `score`
- `label`
- `base_score`
- `base_pressure_ratio`
- `created_at`

### `financial_pressure_factors`

Purpose:
- explain score line by line

Recommended JSONB shape:

```json
{
  "remaining_required_money": 520,
  "remaining_realistic_earning_capacity": 660,
  "base_pressure_ratio": 0.79,
  "modifiers": {
    "overdue": 0,
    "low_cash": 10,
    "urgent_fixed_charge": 10,
    "exceptional": 0
  },
  "main_reasons": [
    "leasing due in 3 days",
    "fuel required",
    "2 useful work days remaining"
  ]
}
```

### `pressure_snapshot_date`

Type:
- `timestamptz`

### `weekly_financial_snapshot`

Recommended fields:
- `user_id`
- `week_start_date`
- `week_end_date`
- `current_week_income`
- `expected_week_income`
- `fixed_weekly_charges`
- `upcoming_required_expenses`
- `overdue_expenses`
- `available_liquidity`
- `remaining_required_money`
- `remaining_realistic_earning_capacity`
- `daily_minimum_target`
- `daily_comfortable_target`
- `daily_optimal_target`
- `financial_pressure_score`
- `financial_pressure_label`
- `financial_pressure_factors` jsonb
- `confidence_level`
- `created_at`
- `updated_at`

## Relationship With Sadaqa

Sadaqa must use real profit, not pressure score.

Pressure score may inform caution, but it does not replace sadaqa calculation.

Rules:
- sadaqa base = real weekly profit
- pressure score may affect reminder tone or caution
- pressure score must not redefine worship calculation

Example:

```text
Real profit = 1200
Sadaqa setting = 5%
Sadaqa target = 60
```

Pressure may explain:

```text
Consider timing carefully because cash pressure is high.
```

Pressure must not say:

```text
Sadaqa is cancelled because score is high.
```

## Relationship With Imperium

If pressure is high:
- stronger work priority may be recommended
- Vector may treat VTC urgency as higher
- The Vault should show clear pressure explanation

But:
- declared priorities still matter
- health still matters
- sleep still matters
- prayer anchors still matter
- family obligations still matter

Pressure does not automatically dominate life priorities.

Imperium should use pressure as one strong signal, not absolute authority.

## Relationship With Vector

Vector may use pressure to:
- protect minimum CA floor
- prioritize guaranteed revenue
- avoid low-value wandering
- increase urgency when realistic work days are low

Vector must not:
- assume future income is guaranteed
- push unsafe work intensity
- ignore fatigue or platform constraints

## Example Cases

### Case A - Low pressure week

Inputs:

```text
current_week_income = 650
expected_week_income = 800
fixed_weekly_charges = 300
upcoming_required_expenses = 100
overdue_expenses = 0
available_liquidity = 700
fuel_required_next_days = 60
minimum_survival_threshold = 150
remaining_work_days = 3
realistic_daily_capacity = 220
```

Calculation:

```text
required_money_this_week = 300 + 100 + 0 + 60 = 460
remaining_required_money = max(0, 460 - 700) = 0
remaining_capacity = 3 * 220 = 660
base_ratio = 0 / 660 = 0
base_score = 0
modifiers = 0
final_score = 0
label = safe
```

Explanation:

```text
Pressure safe because current liquidity covers required weekly obligations with margin.
```

### Case B - Fuel + leasing + school payment pressure

Inputs:

```text
current_week_income = 300
expected_week_income = 900
fixed_weekly_charges = 250
upcoming_required_expenses = 420
overdue_expenses = 0
available_liquidity = 180
fuel_required_next_days = 90
school_payment_due = 180
leasing due within 3 days = true
minimum_survival_threshold = 150
remaining_work_days = 3
realistic_daily_capacity = 220
```

Calculation:

```text
required_money_this_week = 250 + 420 + 0 + 90 + 180 = 940
remaining_required_money = max(0, 940 - 180) = 760
remaining_capacity = 3 * 220 = 660
base_ratio = 760 / 660 = 1.15
base_score = 100
urgent_fixed_charge_modifier = 10
final_score = 100
label = critical
```

Explanation:

```text
Pressure critical because remaining required money exceeds realistic earning capacity.
Main factors: leasing soon, school payment due, fuel required, only 3 useful work days left.
```

### Case C - Bad week + overdue expense + low cash

Inputs:

```text
current_week_income = 120
expected_week_income = 700
fixed_weekly_charges = 300
upcoming_required_expenses = 180
overdue_expenses = 160
available_liquidity = 40
fuel_required_next_days = 70
minimum_survival_threshold = 150
remaining_work_days = 2
realistic_daily_capacity = 200
```

Calculation:

```text
required_money_this_week = 300 + 180 + 160 + 70 = 710
remaining_required_money = max(0, 710 - 40) = 670
remaining_capacity = 2 * 200 = 400
base_ratio = 670 / 400 = 1.675
base_score = 100
overdue_modifier = 10
low_cash_modifier = 10
final_score = 100
label = critical
```

Explanation:

```text
Pressure critical because overdue expense exists, available liquidity is below survival threshold, and remaining required money is above realistic capacity.
```

### Case D - High gross income but poor real net profit

Inputs:

```text
current_week_income = 1100
expected_week_income = 1300
fixed_weekly_charges = 500
upcoming_required_expenses = 350
overdue_expenses = 0
available_liquidity = 120
fuel_required_next_days = 180
urgent_maintenance_cost = 300
minimum_survival_threshold = 150
remaining_work_days = 2
realistic_daily_capacity = 230
```

Calculation:

```text
required_money_this_week = 500 + 350 + 0 + 180 + 300 = 1330
remaining_required_money = max(0, 1330 - 120) = 1210
remaining_capacity = 2 * 230 = 460
base_ratio = 1210 / 460 = 2.63
base_score = 100
low_cash_modifier = 10
exceptional_modifier = 5
final_score = 100
label = critical
```

Explanation:

```text
Pressure critical despite high gross income because available liquidity is low and required net obligations exceed realistic remaining capacity.
```

Lesson:
- gross income does not equal financial safety
- pressure must use real available liquidity and required obligations

## Open Decisions

TODO:
- exact source for realistic daily capacity
- exact useful work day detection
- exact weekly boundary
- exact confidence formula
- exact handling of postponed expenses in future weeks
- exact table name for pressure snapshots
- exact smoothing window and how `payment_day_of_month` maps a monthly/quarterly expense onto real-pressure timing
- exact scoring weights for the out-of-list classification grid
- whether/how an explicit "mobilize crypto" user action feeds a secondary pressure view

