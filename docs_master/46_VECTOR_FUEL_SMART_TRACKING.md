# 46 - Vector Smart Fuel Tracking (V2)

> ⚠️ **V2 feature — to be implemented after V1 is stable.**
> This document captures the design decisions for future implementation.

---

## 1. Purpose

This feature precisely tracks **fuel consumption attributable to VTC business** versus **personal use**, so that:

- The business profit reflects the real cost of fuel for VTC.
- The sadaqa calculation (per doc 41 §7) is accurate, since it derives from business profit.
- The user gets visibility (via WR) on how much fuel they consume in personal use.

The user does NOT see "fuel pro" vs "fuel perso" split in the Vault UI. The split is internal to the AI brain. Only the corrected business profit is visible.

---

## 2. Core Insight

```text
PROBLEM:
  Without this feature, all fuel purchases are categorized as 
  "Carburant" (business) in Vault. But part of that fuel was 
  used for personal trips (restaurants, errands, etc.).
  
  Result: business profit is under-estimated. Sadaqa is 
  under-estimated. The numbers don't reflect reality.

SOLUTION:
  Track precisely what fuel was consumed during VTC sessions
  (in euros). Anything else purchased = personal by deduction.
  
  We track in EUROS, not liters. Liters are an intermediate 
  calculation. The number that matters for business profit 
  and sadaqa is in euros.
```

---

## 3. Why This Is V2 And Not V1

```text
V1 — Vector handles VTC sessions, rides, and basic finance.
     Generic fuel tracking via Vault is good enough.
     Business profit is approximate but functional.

V2 — Once VTC sessions are stable and the user has weeks of
     real data, the imprecision in fuel tracking becomes 
     visible. Smart fuel tracking lands at the right time.
```

---

## 4. The User Flow

### 4.1 Start session

```text
User taps "Démarrer session" in Vector.

Popup:
  ┌─────────────────────────────────┐
  │ Démarrer session VTC            │
  │                                 │
  │ Kilométrage actuel:             │
  │ [_______] km                    │
  │                                 │
  │ [Démarrer]                      │
  └─────────────────────────────────┘

Backend:
  - INSERT vector_sessions (status='active')
  - km_start = user input
```

### 4.2 During the session

Nothing special. User does VTC normally. Vector tracks rides as usual (per doc 33).

### 4.3 End session

```text
User taps "Fin session" in Vector.

Popup:
  ┌─────────────────────────────────┐
  │ Fin de session                  │
  │                                 │
  │ Kilométrage actuel:             │
  │ [_______] km                    │
  │                                 │
  │ Conso moyenne (tableau bord):   │
  │ [___] L/100km                   │
  │                                 │
  │ Prix au litre payé:             │
  │ [____] €/L                      │
  │                                 │
  │ [Terminer]                      │
  └─────────────────────────────────┘

Backend calculates:
  distance_km    = km_end - km_start
  liters_used   = (distance_km × consumption) / 100
  eur_consumed  = liters_used × price_per_liter
  
  INSERT vector_session_fuel_consumption:
    session_id, km_start, km_end, distance_km,
    avg_consumption_l_100km, price_per_liter,
    liters_consumed, eur_consumed
```

### 4.4 Filling up the tank

```text
User goes to a fuel station, pays.

User logs in Vault (or via Vector if smart fuel was used):
  Add expense:
    Amount: 80 €
    Category: Carburant
    Book: business (default)

Backend:
  - INSERT vault_transactions (book='business', category='Carburant')
  - INSERT vector_fuel_events (linked to the same expense)
  - The user does NOT manually distinguish pro vs perso.
```

### 4.5 Average price simplification

```text
The user enters the price per liter at end-of-session.
This is approximate (the user remembers the last fuel-up price).

Justification:
  Real-world fuel prices in Île-de-France typically vary by 
  1-10 cents per liter between stations and across weeks.
  
  The user can be slightly imprecise:
  - If unsure, they enter the most recent known price.
  - The result remains accurate to within a few percent.

A safety margin (10-15%) on sadaqa percentage compensates
for this imprecision (handled separately, see Section 11).
```

---

## 5. Weekly Reconciliation

The reconciliation runs **every Sunday at 23:00 Europe/Paris** as part of the weekly closing routine.

### 5.1 The simple formula (per user spec)

```python
# At Sunday close of week W:

total_carburant_acheté_W = SUM(vector_fuel_events.total_eur 
                               WHERE date IN week_W)

total_carburant_tracé_pro_W = SUM(vector_session_fuel_consumption.eur_consumed
                                   WHERE date IN week_W)

# Perso for this week (can be negative, see Section 5.2):
carburant_perso_W = total_carburant_acheté_W - total_carburant_tracé_pro_W
```

### 5.2 Negative weeks are acceptable

```text
A negative carburant_perso for a given week means:
  The fuel consumed during VTC sessions exceeded what was 
  purchased that week. This happens when fuel was bought 
  in a previous week and used this week.

DECISION: Accept the imprecision.

Why this is fine:
├─ It's rare (typically only 1-3 weeks per year)
├─ It self-balances over 52 weeks (yearly perspective)
├─ Sadaqa imprecision averages out over the year
└─ The 10-15% sadaqa safety margin absorbs the rest

We do NOT compute lifetime cumulatives.
We do NOT carry deficits forward.
We trust the year-level averaging.
```

This is the **explicit user-validated decision**.

### 5.3 Business profit correction

```text
The standard business profit calculation:
  business_profit = business_income - SUM(business_expenses)

With this feature, fuel is treated specially:
  business_profit = business_income 
                  - SUM(business_expenses HORS carburant)
                  - carburant_tracé_pro_W

Note: the difference (carburant_perso_W) is NOT subtracted 
from business profit. The AI knows it's personal use; the 
user's Vault display still shows the original purchase as 
"Carburant" but the AI's profit math is more accurate.
```

### 5.4 Sadaqa target update

Per doc 41 §7:

```text
weekly_sadaqa_target = business_profit_corrected × user.sadaqa_percentage
```

The corrected business profit (Section 5.3) is used. The sadaqa is on the right base.

---

## 6. What The User Sees

The user does NOT see the pro/perso split as separate categories. 

```text
USER VIEW IN VAULT:
  Catégorie "Carburant": 200 € cette semaine
  
  (No mention of pro vs perso. The user doesn't need to know
   or care during day-to-day usage.)

USER VIEW IN WR (optional, see Section 9):
  "Cette semaine, ton carburant total: 200 €.
   Carburant utilisé en VTC: 150 €.
   Carburant utilisé en perso: 50 €."
  
  (Surfaced once a week as informative context.)

USER VIEW IN PRESSURE / PROFIT:
  Bénéfice business cette semaine: 380 € (correctly computed)
  Sadaqa cible: 19 € (5% × 380, correctly computed)
```

---

## 7. The Database

### 7.1 New table: vector_session_fuel_consumption

```sql
CREATE TABLE vector_session_fuel_consumption (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  session_id               UUID NOT NULL REFERENCES vector_sessions(id) 
                                                  ON DELETE CASCADE,
  km_start                 INTEGER NOT NULL,
  km_end                   INTEGER NOT NULL,
  distance_km              INTEGER GENERATED ALWAYS AS (km_end - km_start) STORED,
  avg_consumption_l_100km  NUMERIC(4,2) NOT NULL,
  price_per_liter_eur      NUMERIC(5,3) NOT NULL,
  liters_consumed          NUMERIC(6,3) GENERATED ALWAYS AS 
                                       ((km_end - km_start) * 
                                        avg_consumption_l_100km / 100) STORED,
  eur_consumed             NUMERIC(8,2) GENERATED ALWAYS AS 
                                       ((km_end - km_start) * 
                                        avg_consumption_l_100km / 100 * 
                                        price_per_liter_eur) STORED,
  recorded_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  CHECK (km_end > km_start),
  CHECK (avg_consumption_l_100km > 0),
  CHECK (price_per_liter_eur > 0)
);

CREATE INDEX vector_session_fuel_consumption_user_recorded_idx
ON vector_session_fuel_consumption (user_id, recorded_at);

CREATE INDEX vector_session_fuel_consumption_session_idx
ON vector_session_fuel_consumption (session_id);
```

### 7.2 New table: vector_weekly_fuel_reconciliation

```sql
CREATE TABLE vector_weekly_fuel_reconciliation (
  id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  week_start                  DATE NOT NULL,
  week_end                    DATE NOT NULL,
  total_carburant_acheté_eur  NUMERIC(8,2) NOT NULL,
  total_carburant_tracé_pro_eur NUMERIC(8,2) NOT NULL,
  carburant_perso_eur         NUMERIC(8,2) GENERATED ALWAYS AS 
                                          (total_carburant_acheté_eur - 
                                           total_carburant_tracé_pro_eur) STORED,
  computed_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  UNIQUE (user_id, week_start)
);

CREATE INDEX vector_weekly_fuel_reconciliation_user_week_idx
ON vector_weekly_fuel_reconciliation (user_id, week_start DESC);
```

### 7.3 Existing table updated: vector_fuel_events

```sql
-- Already in doc 33 §16.1:
-- vector_fuel_events tracks each fuel-up

-- No changes needed for V2 feature.
-- Keep the existing structure.
```

---

## 8. The Reconciliation Cron

```text
Schedule: every Sunday at 23:00 Europe/Paris

n8n workflow: vector_weekly_fuel_reconciliation

Steps:
  1. Identify week boundaries (Monday 00:00 → Sunday 23:59)
  2. For each user (V1 = single user):
     a. Sum vector_fuel_events.total_eur for the week
     b. Sum vector_session_fuel_consumption.eur_consumed for the week
     c. INSERT vector_weekly_fuel_reconciliation
  3. Trigger downstream:
     - Vault recomputes weekly business profit
     - Path recomputes weekly sadaqa target
     - Imperium publishes the data for the next WR

Note: This runs BEFORE the WR availability flag (Tuesday 20:00).
The fuel data is ready when the user starts their WR.
```

---

## 9. Optional WR Surfacing

The Weekly Report (doc 32) can optionally include a fuel section.

### 9.1 In the WR final draft

```text
Section: "Carburant cette semaine"

  - Total carburant acheté: 200 €
  - Utilisé en VTC: 150 €
  - Utilisé en perso: 50 €
  
  Si carburant_perso > carburant_perso_average_4_weeks × 1.5:
    Flag: "Carburant perso plus élevé que d'habitude"
```

### 9.2 In the WR JSON (`extracted_for_memory`)

If a pattern emerges (e.g. consistent high personal fuel), it gets stored as a `pattern` in pgvector with decay. The next WR can surface the trend.

### 9.3 Privacy

The split is informative, not punitive. The WR uses neutral, non-judgmental tone:
- Not "You wasted 50€ on personal fuel"
- But "Carburant utilisé en perso: 50 €"

---

## 10. AI Tasks Touched

```text
No new ai_tasks types needed for V2.

The reconciliation is purely deterministic backend math.

The WR contribution (Section 9) is part of weekly_report.summary 
and weekly_report.final tasks (doc 32).
```

---

## 11. Sadaqa Safety Margin (Future)

Per the user's expressed wish:

```text
A safety margin of 10-15% applies on top of the calculated 
sadaqa target.

Reasoning:
- Fuel price imprecision (~1-3% error)
- Personal fuel deduction imprecision (~1-3% error)
- General desire to give slightly more, not less
- Mathematical safety buffer

This margin is configurable in Path settings:
  user.sadaqa_safety_margin_percent (default: 12.5%)

Final sadaqa target:
  effective_target = base_target × (1 + safety_margin)

This safety margin is NOT part of the V2 feature scope itself.
It's a Path setting (doc 41) that can be set independently.
```

---

## 12. Failure Modes

### 12.1 User doesn't enter km/conso/price at end of session

```text
The end-session popup is mandatory.

If the user dismisses or skips:
  - Session marked status='ended_no_fuel_data'
  - No vector_session_fuel_consumption row created
  - Weekly reconciliation skips this session
  - Net effect: that session counts as personal use
    (since the fuel cost is not attributed to VTC)

This penalizes laziness slightly without blocking the user.

Banner in next session: "Tu as oublié de finaliser ta dernière 
session. Tu peux compléter les données ici si tu te souviens."
```

### 12.2 User enters wrong km

```text
Validation:
  km_end MUST be greater than km_start
  difference MUST be > 0 and < 1000 (sanity check)
  
On invalid input:
  - Show error immediately
  - Keep popup open for correction
  - Do NOT save until valid
```

### 12.3 User has multiple cars (V3)

V2 assumes one car. V3 may add `vehicle_id` to sessions and fuel events for users with multiple vehicles. Not in scope here.

---

## 13. Integration Points

### 13.1 With Vector

This is a Vector feature. All UI lives in Vector:
- Start session popup (km input)
- End session popup (km, conso, price input)
- Optionally: a small dashboard tile showing this week's fuel cost

### 13.2 With Vault

```text
- Fuel purchases are still logged in Vault as usual.
- No new category needed in Vault.
- Vault's weekly business profit calculation reads:
    vector_weekly_fuel_reconciliation.total_carburant_tracé_pro_eur
  instead of:
    SUM(vault_transactions WHERE category='Carburant')
```

### 13.3 With Path

```text
- Path reads the corrected business profit for sadaqa target.
- No direct integration; it just consumes the right number.
```

### 13.4 With Imperium / WR

```text
- WR section optionally surfaces the breakdown (Section 9).
- No replan triggers needed for fuel events.
```

---

## 14. UI Surface (V2)

```text
Vector — Start session button:
  → opens popup with km input
  → validates non-negative integer
  → validates difference from last km if available 
    (sanity check: < 5000 km diff = OK)

Vector — End session button:
  → opens popup with 3 fields
  → all 3 mandatory
  → validation as Section 12.2
  → on submit: backend computes + stores

Vector dashboard (optional tile):
  "Cette semaine en VTC:
    - Distance: 850 km
    - Carburant utilisé: 64 L (~118 €)
    - Conso moyenne: 7.5 L/100km"
  
  No mention of personal fuel here. That's a WR-only insight.
```

---

## 15. Implementation Order (V2)

```text
Phase 1 — Schema migrations
  ├─ vector_session_fuel_consumption table
  └─ vector_weekly_fuel_reconciliation table

Phase 2 — Backend services
  ├─ services/vector/sessions.py: 
  │   - update start to require km_start
  │   - update end to require km_end + conso + price
  └─ services/vector/fuel_reconciliation.py:
      - weekly reconciliation function

Phase 3 — API endpoint changes
  ├─ POST /api/v1/vector/sessions: add km_start to body
  └─ POST /api/v1/vector/sessions/{id}/end: 
      add km_end, avg_consumption_l_100km, price_per_liter_eur

Phase 4 — n8n workflow
  └─ vector_weekly_fuel_reconciliation cron (Sunday 23:00)

Phase 5 — Vault profit calculation update
  └─ Use vector_weekly_fuel_reconciliation values 
    instead of raw vault_transactions sum

Phase 6 — Path sadaqa update
  └─ Already uses corrected business profit, no change needed

Phase 7 — Optional WR section
  └─ Add fuel breakdown to weekly_report.summary prompt template

Phase 8 — UI in Android app
  ├─ Update start session popup
  ├─ Update end session popup
  └─ Add validation logic
```

---

## 16. Non-Goals For V2

```text
❌ Tracking liters separately for personal use
❌ Tracking the exact stations for personal fuel
❌ Notifying the user about high personal fuel
   (only surfaced in WR, not pushed)
❌ Locking or warning about fuel purchases
❌ Multi-vehicle support (V3)
❌ Fuel price scraping APIs
❌ Auto-sync with car APIs (OnStar, etc.)
```

---

## 17. References

- `33_VECTOR_LOGIC_DETAIL.md` — Vector logic, smart fuel basics
- `41_PATH_LOGIC_DETAIL.md` — sadaqa calculation
- `42_VAULT_LOGIC_DETAIL.md` — business profit calculation
- `32_WR_INTERACTIVE_WORKFLOW.md` — WR fuel section integration
- `11_FINANCIAL_PRESSURE_FORMULA.md` — pressure based on profit

---

**Document version:** 1.0
**Status:** V2 design specification (DO NOT IMPLEMENT before V1)
**Last updated:** 2026-04-29
