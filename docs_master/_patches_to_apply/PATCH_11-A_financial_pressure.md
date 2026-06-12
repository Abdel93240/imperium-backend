# Patch 11-A — Recurring Expenses Truth, Wallets, and Classification Scoring

Patch 11-A clarifies how required expenses are determined and how real pressure
is computed. It resolves an ambiguity (the misleading `optional_required_expenses`
name) and restores the user-owned recurring-expenses list as the source of truth.

Decisions (June 2026 review):

## 1. Recurring-expenses list = user truth (not AI judgment)

There is a user-maintained **recurring-expenses list**, shown on the Vault
dashboard, 100% editable by the user. It is the **source of truth** for declared
obligations. The AI READS it and never judges whether a declared expense is
"required" — the user already decided that by putting it in the list.

Each entry has:
- `label` (dénomination)
- `recurrence` (weekly / monthly / quarterly / yearly …)
- `amount` (prix)
- `category` (dropdown: family, work, … with an "Other" option that opens a free
  text box for exceptional cases)
- `payment_day_of_month` (**new**) — the day the payment is actually due

Because the list is user-owned truth, no AI classification applies to its
entries. They are required, period.

## 2. Rename `optional_required_expenses` → `conditional_required_expenses`

The name `optional_required_expenses` is dangerously ambiguous ("optional" reads
as "sacrificable", which caused school fees to look skippable). Rename it to
`conditional_required_expenses` everywhere in the doc.

Definition: required expenses that do **not** occur every week but ARE required
when they fall due (e.g. monthly school fee, quarterly tax). They come FROM the
recurring-expenses list — not from any AI judgment. "Conditional" = conditional
on timing, never on importance.

Update Step 2 accordingly:
```text
required_money_this_week =
  fixed_weekly_charges
  + upcoming_required_expenses
  + overdue_expenses
  + fuel_required_next_days
  + conditional_required_expenses    # (was optional_required_expenses)
```

## 3. Two distinct uses of expenses: smoothed objective vs real pressure

These are different notions and must not be conflated.

- **Smoothed objective (how much to EARN).** Recurring expenses are *smoothed*
  across the period to tell the AI the earning rhythm the user must sustain
  (e.g. a 200€/month school fee informs a ~50€/week earning target). This is a
  TARGET, used to set daily/weekly earning goals.
- **Real pressure (what the user actually HAS).** Financial pressure is NOT
  computed on the smoothed theoretical figure. It is computed on the user's
  **real money** in the Vault wallets, confronted with what must actually go out
  (via `payment_day_of_month`). Pressure is anchored in reality, never in a
  provision that may not exist.

This avoids both a false sense of security and double-counting.

## 4. Available liquidity = stable wallets only (crypto excluded)

Step 1 `available_liquidity` is the sum of the **stable** Vault wallets:
```text
available_liquidity =
  current_bank_available_balance    # CB wallet
  + current_wallet_available_cash   # cash wallet
```
The **crypto wallet is EXCLUDED** from survival pressure. Rationale: crypto is
volatile and not instantly/cost-free liquidatable; counting it would inflate
perceived safety. Crypto is displayed separately in Vault as a **mobilizable
reserve** (a last-resort cushion), but it does not enter the pressure
calculation. Needing to sell crypto to cover an obligation is itself a tension
signal, not a "safe" state.

(If the user ever wants to explicitly mobilize crypto, that is a deliberate
user action, not an automatic inclusion.)

## 5. Classification scoring — ONLY for expenses NOT in the list

The recurring-expenses list covers the *known*. But unplanned/exceptional
expenses appear that the user did not pre-declare. For THOSE (and only those),
a scoring guides the AI to classify them as *required* vs *deferrable* — so the
AI is guided, never left to invent freely.

```text
If expense ∈ recurring-expenses list → REQUIRED (user truth, no scoring).
Else → classification scoring:
  + vital nature (housing, food, health, children's school) → strong "required"
  + legal/contractual consequence if unpaid (leasing, taxes, fines) → required
  + due inside the operational window → required
  + deferrable without consequence → deferrable
```

**Hard rule:** vital categories (housing, food, health, children's schooling,
legal obligations) can NEVER be classified deferrable by the AI alone. The
scoring guides ambiguous cases; it cannot downgrade a vital expense.

This couples cleanly with doc 30: financial reasoning is GPT-5.5's domain, and
GPT-5.5 must surface its reasoning / flag uncertainty rather than fabricate a
classification.

## 6. Core Inputs update

- Replace the "Optional inputs" heading by "Conditional required inputs"
  (these feed `conditional_required_expenses`), and note they are sourced from
  the recurring-expenses list, each carrying its `payment_day_of_month`.
- Add the recurring-expenses list as a first-class input source.
- Make explicit that `available_liquidity` = CB wallet + cash wallet (crypto
  excluded), all three wallets being Vault dashboard wallets.

## 7. Open Decisions (append)

- Exact smoothing window and how `payment_day_of_month` maps a monthly/quarterly
  expense onto real-pressure timing.
- Exact scoring weights for the out-of-list classification grid.
- Whether/how an explicit "mobilize crypto" user action feeds a secondary
  pressure view.
