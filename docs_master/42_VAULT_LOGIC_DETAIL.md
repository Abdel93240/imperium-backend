# 42 - The Vault Logic Detail

## 1. Purpose

The Vault is the **financial radar**. It tracks income, expenses, business vs personal separation, weekly profit, and feeds the sadaqa calculation in Path.

Vault observes and reports. **It never decides on its own.** Investment decisions, big purchases, and financial strategy remain with the user.

---

## 2. Non-Negotiable Rules

```text
✅ Vault can:
   - track income (business + personal, separated)
   - track expenses (business + personal, separated)
   - calculate weekly business profit
   - calculate wallet totals (cash + bank + crypto)
   - compute pressure score (per doc 11)
   - feed sadaqa target to Path
   - emit upcoming expense alerts
   - propose categorization via the local model
   - parse receipts via the OCR service

❌ Vault must never:
   - automatically transfer money
   - automatically categorize without user validation on first sight
   - propose investments
   - lock spending
   - send guilt notifications about spending
   - hide reality (always report exact numbers)
```

---

## 3. The Two-Book Architecture

This is the most important Vault concept.

```text
LIVRE BUSINESS:
  Income:
    - VTC revenue (Bolt sessions)
    - Other professional income (if any)
  Expenses:
    - Carburant (fuel for VTC)
    - Plateformes (Bolt commission, Uber, etc.)
    - Entretien VTC (maintenance, tires, oil)
    - Assurance professionnelle
    - Outils VTC (chargers, accessories)
    - Charges sociales (URSSAF if applicable)
    - Tax provision
  
  → BUSINESS_PROFIT = business_income - business_expenses
  → This is what feeds sadaqa calculation in Path

LIVRE PERSONNEL:
  Income:
    - Side income (Leboncoin sales, RSA, other personal)
    - Salaire (if any)
    - Gifts received (if user logs)
  Expenses:
    - Loyer / housing
    - Courses (food, household)
    - Restaurant
    - Loisirs
    - Vêtements
    - Téléphone
    - Santé
    - Personal subscriptions
  
  → PERSONAL_BALANCE = personal_income - personal_expenses
```

### 3.1 Why this matters

```text
- Sadaqa is computed on business profit (per doc 41 §7.1)
- User can see clearly: "is the business sustainable?"
- Tax preparation simpler (business expenses traceable)
- Financial pressure (doc 11) uses business cashflow primarily
```

---

## 4. Wallet Definition

```text
WALLET = sum of all liquid assets:

  CASH:
    - physical cash on hand (manually updated)
  
  BANK:
    - linked bank account balances
    - V1: manually updated
    - V2: automatic via banking API (deferred)
  
  CRYPTO:
    - crypto wallet balances
    - V1: manually updated
    - V2: automatic via exchange API (deferred)
  
  TOTAL_WALLET = cash + bank + crypto
```

This represents what the user can actually access right now. Used by:
- Pressure score (doc 11)
- Imperium financial reasoning
- Daily objective context

---

## 5. The Three Decision Layers

```text
LAYER 1 — DETERMINISTIC (no AI)
  ├─ All arithmetic: totals, averages, projections
  ├─ Pressure score (per doc 11 formula)
  ├─ Categorization application (after first validation)
  └─ Cost: 0€

LAYER 2 — THE LOCAL MODEL
  ├─ Initial categorization suggestion
  ├─ Quick advice: "is this expense reasonable?"
  ├─ Pattern detection: "you spent 2x more on fuel this week"
  └─ Cost: 0€

LAYER 3 — DEFERRED CLOUD
  ├─ Receipt OCR → the OCR service
  ├─ Detailed advice (Level 2 popup) → the light cloud tier
  ├─ Monthly analysis → the first cloud tier
  └─ Weekly review → the high reasoning model (via WR)
```

---

## 6. Adding a Transaction

### 6.1 Add Income flow

```text
User taps "+ Gain" in Vault
  → bottom sheet opens:
     - amount (required)
     - book: business | personal (toggle)
     - category: dropdown (depending on book)
       - Business defaults: VTC, Autre pro
       - Personal defaults: Side income, RSA, Gift, Salaire, Autre
     - description (free text)
     - date (default: today)
     - source: cash | bank | crypto (which wallet receives)
  
  → User taps "Ajouter"
  → POST /api/vault/transactions
     headers: Idempotency-Key
  → backend validates + stores
  → wallet balance updated
```

### 6.2 Add Expense flow

```text
User taps "+ Dépense" in Vault
  → bottom sheet:
     - amount
     - book: business | personal (toggle)
     - category: dropdown
       - Business defaults: Carburant, Plateformes, Entretien, 
         Assurance pro, Outils VTC, Charges, Provision impôt, Autre
       - Personal defaults: Courses, Loyer, Restaurant, Loisirs,
         Vêtements, Téléphone, Santé, Abonnements, Autre
     - description (free text)
     - date
     - source (which wallet pays)
  
  → User can choose "Autre" + free text category name
  → backend stores including custom category
  → custom categories accumulate per user (suggestions later)
```

### 6.3 Receipt scan flow

```text
User taps "Scanner ticket"
  → camera opens
  → photo taken
  → the OCR service (per doc 37 §3)
  → backend creates ai_task vault.receipt_extract
  → the OCR service returns structured data
  → backend creates draft transactions:
     - one expense for the receipt total
     - line items proposed
     - category suggested by the local model
  → user reviews + validates
  → on validation: 
     - INSERT INTO vault_transactions
     - if food items: also INSERT INTO food_stock_items (Pulse)
```

---

## 7. Categorization

### 7.1 Initial categorization

```text
First time a description appears:
  the local model suggests a category based on:
    - the description text
    - the amount
    - the user's past categorization history
  
  User confirms or overrides.
  Choice stored in user_category_memory for future calls.
```

### 7.2 Repeated categorization

```text
After 3+ identical descriptions categorized the same way:
  → backend auto-suggests with high confidence
  → user can still override on each transaction
  → never silently auto-categorize without showing
```

---

## 8. Wallet Updates

### 8.1 Manual wallet refresh

```text
User taps "Mettre à jour wallet" in Vault settings:
  → opens form:
     - cash: __ €
     - bank: __ €
     - crypto: __ €
  → user enters current values
  → INSERT INTO vault_wallet_snapshots
  → latest snapshot used for pressure calc
```

### 8.2 Automatic adjustment after transactions

```text
For tracking purposes:
  - each transaction adjusts the predicted wallet
  - predicted_wallet = last_snapshot + sum(transactions_since)
  - shown alongside actual_wallet
  
When difference > 5%:
  → soft prompt: "Vérifier ton solde réel ?"
  → not blocking
```

---

## 9. Pressure Score

Defined fully in `11_FINANCIAL_PRESSURE_FORMULA.md`.

Brief summary:

```text
pressure_score (0-10):
  0 = comfortable, no urgency
  10 = critical, every euro counts

Inputs:
  - wallet_total
  - upcoming_expenses_next_30d (rent, bills, etc.)
  - weekly_business_profit_average
  - weekly_objective_progress
  - days_until_next_major_outflow

Output:
  - pressure_score: 0-10
  - pressure_explanation: short text
  - critical_signals: list (e.g. "rent due in 3 days")
```

Pressure is computed daily, deterministic, no AI.

Used by:
- Imperium daily planning (more VTC missions if pressure high)
- Vector zone recommendations (bias toward profitable zones if high)
- Bolt overlay (per doc 33 §5.2.3 — NOT consumed directly by Vector)

Wait — correction:
```text
Bolt overlay does NOT consume pressure_score directly (per doc 33).
It is consumed by Imperium when planning the daily VTC objective.
By the time Vector evaluates a ride, pressure has already shaped
the daily plan.
```

---

## 10. Upcoming Expenses

```text
upcoming_expenses table:
  - user_id
  - title (e.g. "Rent")
  - amount_eur
  - due_date
  - book: business | personal
  - status: pending | paid | overdue
  - recurrence (none | monthly | yearly)
  - reminder_days_before (e.g. 7)
```

Used for:
- pressure score calculation
- Imperium plan awareness
- Vault UI surfacing

User adds these manually. V2 may auto-detect from email parsing.

---

## 11. Weekly Profit Computation

```text
Triggered every Monday at 00:30 Europe/Paris (n8n temporal trigger):

1. n8n calls the dedicated backend endpoint or workflow trigger.
2. The backend reads vault_transactions for week N.
3. The backend computes:

  business_income_N = SUM(vault_transactions WHERE
    book = 'business' AND
    type = 'income' AND
    date IN week_N
  )

  business_expenses_N = SUM(vault_transactions WHERE
    book = 'business' AND
    type = 'expense' AND
    date IN week_N
  )

  business_profit_N = business_income_N - business_expenses_N

4. The backend writes weekly_finance_summaries when that table exists.
5. The backend emits vault.weekly_profit.computed.
6. Path/Imperium can use the event to update the sadaqa target.

n8n never writes directly to Postgres.
```

---

## 12. Vault AI Task Types

```text
vault.receipt_extract              - OCR via the OCR service (doc 37)
vault.categorization_suggestion    - the local model
vault.weekly_finance_analysis      - the first cloud tier, monthly
vault.detailed_advice              - the light cloud tier, "see why?" popup
vault.weekly_review_contribution   - the high reasoning model via WR
```

---

## 13. Routing Distribution For Vault

```text
Daily ops (92%):           the local model
Receipt OCR (2%):          the OCR service
Level 2 advice (4%):       the light cloud tier
Monthly analysis (1%):     the first cloud tier
Weekly review (1%):        the high reasoning model (via WR)
```

---

## 14. Two-Tier Advice System

```text
LEVEL 1 — Always visible
  Daily Vault dashboard shows:
    - week balance: +X €
    - month balance: +Y €
    - pressure score: N/10
    - upcoming alerts
  Computed deterministically, no AI.

LEVEL 2 — On-demand "Voir pourquoi"
  Below pressure score:
    [Voir pourquoi ?]
  
  When tapped:
    → POST /api/vault/advice/detail
    → ai_task: vault.detailed_advice
    → the light cloud tier generates contextual advice (3 sentences)
    → e.g. "Le carburant représente 60% des dépenses business
            cette semaine. C'est 25% au-dessus de la moyenne.
            Vérifier les trajets ou les prix."
  
  Cost: ~0.001 € per call
```

---

## 15. Reads & Events via Common Memory

### 15.1 With Path

```text
Vault writes weekly_business_profit into its own tables; Path READS this
sadaqa basis from common memory (read-only).

When a sadaqa donation is confirmed (Path side), the BACKEND writes the
corresponding expense into the Vault domain (category Sadaqa). There is no
direct Path→Vault transfer; it is a backend rule writing the owner's table.
```

### 15.2 With Pulse

```text
On receipt validation (VAU-05), the BACKEND writes the food expense into the
Vault tables (Vault remains the owner) AND writes a stock update into the Pulse
domain. No app pushes a write into Vault — it is a deterministic brain rule.
The receipt produces TWO separate backend writes (Vault expense + Pulse stock),
each into its own domain table. Not a Vault↔Pulse dialogue.
```

### 15.3 With Vector

```text
Vector may READ fuel-expense history from common memory; no direct channel.
  - VTC revenue tracking
  - Fuel expense history → smart fuel knowledge
  
At the end of a VTC session, the BACKEND (Vault service) writes the confirmed
income into the Vault tables. Vector only writes its own operational tables; it
never creates a Vault transaction. Fuel expenses likewise are written by the
backend into the Vault domain.
```

### 15.4 With Imperium

```text
Imperium READS Vault summaries from common memory (allowed §10) to size the
objective and pressure:
  - pressure_score (daily)
  - week_balance (daily)
  - upcoming_expenses_alert

Imperium uses these for:
  - daily VTC objective sizing
  - mission priority adjustment
  - financial mention in chatbot
```

---

## 16. Database Tables

Existing (per doc 05):
- `vault_transactions` ✅
- `weekly_finance_summaries` ✅

To add:

```sql
CREATE TABLE vault_wallet_snapshots (
  id              UUID PK,
  user_id         UUID FK,
  cash_eur        NUMERIC(12,2),
  bank_eur        NUMERIC(12,2),
  crypto_eur      NUMERIC(12,2),
  total_eur       NUMERIC(12,2) GENERATED ALWAYS AS (cash + bank + crypto),
  recorded_at     TIMESTAMPTZ,
  source          VARCHAR(32) -- manual | sync (V2)
);

CREATE TABLE upcoming_expenses (
  id                    UUID PK,
  user_id               UUID FK,
  title                 VARCHAR(200),
  amount_eur            NUMERIC(12,2),
  due_date              DATE,
  book                  VARCHAR(16) CHECK (book IN ('business','personal')),
  status                VARCHAR(16) CHECK (status IN ('pending','paid','overdue')),
  recurrence            VARCHAR(16) CHECK (recurrence IN ('none','monthly','yearly')),
  reminder_days_before  INTEGER,
  created_at            TIMESTAMPTZ,
  paid_at               TIMESTAMPTZ NULL
);

CREATE TABLE user_category_memory (
  id              UUID PK,
  user_id         UUID FK,
  description_normalized VARCHAR(255),
  category        VARCHAR(64),
  book            VARCHAR(16),
  occurrences     INTEGER,
  last_used_at    TIMESTAMPTZ,
  UNIQUE (user_id, description_normalized, book)
);

CREATE TABLE vault_pressure_snapshots (
  id              UUID PK,
  user_id         UUID FK,
  computed_at     TIMESTAMPTZ,
  pressure_score  NUMERIC(3,1),
  inputs_json     JSONB,
  explanation     TEXT
);
```

The existing `vault_transactions` table needs the `book` column added if not present:

```sql
ALTER TABLE vault_transactions
ADD COLUMN IF NOT EXISTS book VARCHAR(16) NOT NULL DEFAULT 'business'
CHECK (book IN ('business','personal'));
```

---

## 17. UI Surface (V1)

```text
Vault Dashboard:
  ├─ Wallet total: X €
     ├─ Cash: __ €
     ├─ Bank: __ €
     └─ Crypto: __ €
  ├─ Week balance: business +A €  / personal +B €
  ├─ Month balance: business +C € / personal +D €
  ├─ Pressure score: N/10
  │   └─ [Voir pourquoi ?] (light cloud tier level 2)
  ├─ Upcoming alerts (next 7 days)
  └─ Quick actions: + Gain | + Dépense | Scan ticket

Transactions tab:
  ├─ Filter: business | personal | all
  ├─ Filter: date range
  └─ List with edit/delete

Categories tab:
  ├─ Default categories (read-only)
  ├─ Custom categories (user-created)
  └─ Stats per category

Settings:
  ├─ Sadaqa percentage (also in Path)
  ├─ Default categories
  ├─ Wallet refresh
  └─ Upcoming expenses management
```

---

## 18. References

- `11_FINANCIAL_PRESSURE_FORMULA.md` — pressure score formula
- `27_VAULT_TRANSACTIONS_WORKFLOW.md` — transaction lifecycle
- `01_SIGNAL_VARIABLES_DICTIONARY.md` — vault signal list
- `41_PATH_LOGIC_DETAIL.md` — sadaqa integration
- `43_IMPERIUM_LOGIC_DETAIL.md` — pressure consumption
- `37_VISION_OCR_PROMPTS.md` — receipt OCR prompt

---

**Document version:** 1.0
**Status:** Vault V1 reference
**Last updated:** 2026-04-29
