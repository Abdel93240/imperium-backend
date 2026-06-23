# 58 - Doc 57 Integration Patches

> **Purpose:** This document lists EXACTLY what to update in
> existing docs (33, 30, 16, 39, 43) to integrate the CatBoost
> ride scoring (doc 57) without creating contradictions.
>
> **When implementing V1**: read each patch, find the section
> in the target doc, apply the change. No rewrite of full docs needed.

**Created:** 2026-05-17
**Status:** Patches to apply when V1 backend coding starts

---

## Patch 1 — Doc 33 (Vector Logic Detail)

### Section 5.2 — Bolt overlay decision

```text
CURRENT (doc 33 §5.2):
  - User receives Bolt notification
  - Screenshot + OCR via Gemini
  - Backend calls Qwen DIRECTLY (exception per doc 16 §5.4)
  - Qwen returns decision: good | bad
  - Halo updated
  
REPLACE WITH:
  - User receives Bolt notification
  - Screenshot + OCR via Gemini
  - Backend calls VectorRideScorer (CatBoost + rules hybrid)
  - Scorer returns: signal (GREEN/RED/WHITE) + 
                    predicted_hourly_rate + 
                    triggered_rules + 
                    source (model | rules_only | hard_rule)
  - Halo updated
  - Score logged to vector_ride_score_log (per doc 57 §11)
  
LATENCY:
  Old: 2-4 seconds (Qwen)
  New: < 30 ms total (feature engineering + CatBoost + format)
  
QWEN ROLE NOW:
  - Only used ON-DEMAND for explanation when user asks "Pourquoi ?"
  - See doc 57 §2 for full reasoning
```

### Section 5.2.4 — Decision logic threshold

```text
CURRENT:
  - hourly_rate above user's median threshold → GREEN
  - hourly_rate below user's bad threshold → RED
  - Static thresholds, no personalization
  
REPLACE WITH:
  - Phase 1 (cold_start, <100 rides): apply business rules R1-R11
    (per doc 57 §4)
  - Phase 2 (transition, 100-500): rules + model hybrid
  - Phase 3 (autonomous, 500+): model primary, rules safety net
  
  Signal computation (Phase 2+):
    score_vs_median = predicted_hourly_rate / user_median_hourly_rate
    GREEN if ≥ 1.10
    RED if ≤ 0.85
    WHITE otherwise
  
  Thresholds user-adjustable in Vector settings.
```

### Section 8 — Vector AI Task Types

```text
CURRENT line: 
  vector.ride_overlay_decision      - Bolt halo overlay (the local model)
  
REPLACE WITH:
  vector.ride_score.catboost        - Real-time CatBoost scoring (0€, <1ms)
  vector.ride_score.rules           - Cold-start rules engine (0€)
  vector.ride_score.fallback        - Fallback if model unavailable
  vector.ride_score.explanation     - On-demand "Pourquoi ?" (Qwen local, 0€)
  vector.ride_model.train           - Weekly retraining (0€, ~60s)
  vector.ride_model.evaluate        - Post-training accuracy check
  vector.bolt_import.ocr            - Bolt history import OCR (Gemini, ~0.001€/screenshot)
  vector.bolt_import.enrich         - Historical enrichment (FREE APIs)
```

### Section 8 — Cost line

```text
CURRENT:
  COST per call: ~0.005 EUR (Gemini OCR) + 0 EUR (Qwen local) = ~0.005 EUR
  
REPLACE WITH:
  COST per call: ~0.005 EUR (Gemini OCR) + 0 EUR (CatBoost local) = ~0.005 EUR
  (Note: cost unchanged, but latency divided by 100+)
```

---

## Patch 2 — Doc 30 (AI Routing and Scoring Policy)

### Routing distribution for Vector

```text
CURRENT line:
  Bolt overlay (3%):            the local model
  
REPLACE WITH:
  Bolt ride scoring (3%):       CatBoost local (0€, <1ms)
  Bolt ride explanation:        Qwen 7B local (on demand only)
  
ADD NOTE:
  "Ride scoring is the only Vector task that bypasses the AI routing
   system entirely. CatBoost runs deterministically on every Bolt offer.
   The AI routing remains for: event scans, disruption triage, zone
   recommendations, WR contributions, and ride explanations."
```

### Section on Vector tasks (if present)

```text
ADD this clarification in the Vector section:
  
  "Real-time ride scoring uses a CatBoost regression model (doc 57)
   instead of the AI routing system. This decision is documented in
   doc 57 §1-2. Rationale:
   - Latency: <1ms vs 2-4s
   - Personal learning: trained on user's actual rides
   - Cost: 0€ inference
   - Personal thresholds vs generic rules"
```

---

## Patch 3 — Doc 16 (AI Backend Layer Overview)

### Section 5.4 — Real-time Bolt overlay exception

```text
CURRENT (doc 16 §5.4):
  "Real-time Bolt overlay decisions (Vector).
   - Latency target: <2s (Bolt ride offer expires fast)
   - Backend calls Qwen DIRECTLY
   - Exception applies only to vector.ride_overlay_decision"
  
REPLACE WITH:
  "Real-time Bolt ride scoring (Vector) — CatBoost model.
   - Latency: <30ms total
   - Backend calls VectorRideScorer (CatBoost + rules hybrid)
   - No AI routing involved
   - This is NOT an exception to the AI layer, it's a separate ML system
   - See doc 57 for full architecture
   
   The 'Qwen exception' from earlier versions is REMOVED.
   Vector no longer requires real-time LLM calls for ride scoring."
```

### Section 10 — Static Overrides

```text
NO CHANGE NEEDED.
Static overrides still apply to other Vector tasks (event scan, etc.)
Ride scoring simply doesn't use the AI routing layer at all now.
```

---

## Patch 4 — Doc 39 (WRS Vector Learning Loop)

### Section: What WRS analyzes

```text
CURRENT:
  "WRS compares Qwen recommendations vs actual user outcomes"
  
REPLACE WITH:
  "WRS compares:
   - CatBoost predictions vs actual ride outcomes
   - Business rules triggers vs profitability
   - Qwen recommendations (for zone/event/disruption tasks) vs outcomes"
```

### Section: Ride overlay decision comparison

```text
CURRENT (lines ~95-105):
  For ride overlay decisions (GREEN | RED):
    ├─ Read Qwen's decision: good | bad
    ├─ Computed actual hourly_rate = revenue / duration_hours
    └─ Classify outcome:
        qwen_correct        → Qwen called good, ride was good
        qwen_wrong_false_positive → Qwen called good, ride was bad
        qwen_wrong_false_negative → Qwen called bad, user accepted, ride was good
        qwen_correct_skip   → Qwen called bad, user skipped, no data
  
REPLACE WITH:
  For ride scoring decisions (GREEN | RED | WHITE):
    ├─ Read CatBoost's prediction: predicted_hourly_rate
    ├─ Read triggered_rules (R1-R11)
    ├─ Computed actual hourly_rate = revenue / duration_hours
    └─ Classify outcome:
        model_correct         → predicted within ±15% of actual
        model_overestimate    → predicted > 15% above actual
        model_underestimate   → predicted > 15% below actual
        rule_blocked_profitable → rule said RED, ride would have been profitable
        rule_blocked_unprofitable → rule said RED, correctly avoided bad ride
  
  Output:
  - Weekly model accuracy report
  - Per-rule performance (feeds doc 57 §10 rule revision)
  - Patterns where model systematically wrong
  - Feature importance evolution
```

### Section: Learning signals

```text
ADD this new signal category:
  
  RULE_REVISION_PROPOSALS:
    Based on per-rule performance analysis (doc 57 §10),
    WRS now produces revision proposals for Opus to present
    in the weekly review.
    
    Stored in vector_rule_revisions with proposed_by='opus_wr'.
    User validates in WR interface.
```

---

## Patch 5 — Doc 43 v2 (Imperium Logic — AI Observability)

### Section 17.4 — Analysis views

```text
The ai_call_logs table from doc 43 v2 already supports tracking
all model types. No schema change needed.

JUST ADD this clarification in §17.1 or as a note:
  
  "Note: vector.ride_score.catboost calls are logged with:
     model_used = 'catboost-vector-ride-v{timestamp}'
     model_tier = 'local_ml'
     cost_eur = 0
     duration_ms typically < 30ms
   
   These calls do NOT consume LLM tokens but ARE logged
   for performance tracking and accuracy analysis.
   
   See doc 57 §11 for the dedicated vector_ride_score_log
   table that complements ai_call_logs with ride-specific data."
```

### New entry in pricing seed (Section 17.2)

```text
ADD to ai_model_pricing seed:
  ('catboost-vector-ride',  0, 0, TRUE),   -- local ML, no cost
  ('xgboost-fallback',      0, 0, TRUE),   -- if needed later
```

---

## Summary: What Changes, What Doesn't

```text
WHAT CHANGES:
├─ Doc 33 §5.2: Qwen → CatBoost for ride scoring
├─ Doc 33 §8: new task types added
├─ Doc 30: routing distribution clarified
├─ Doc 16 §5.4: exception removed
├─ Doc 39: comparison source updated
└─ Doc 43 v2 §17: catboost logging clarification

WHAT DOESN'T CHANGE:
├─ All other Vector tasks still go through AI routing
├─ ai_call_logs structure (doc 43 v2 §17)
├─ pgvector memory system (still relevant for context)
├─ WR validation workflow (doc 32)
├─ Backend authority (doc 08)
├─ Imperium decision framework (doc 52)
└─ All other modules (Pulse, Path, Vault, Imperium) unchanged
```

---

## Implementation Checklist for Coding Time

When you start coding Vector V1, follow this order:

```text
☐ 1. Apply Patch 1 (doc 33) — manual edit to doc
☐ 2. Apply Patch 2 (doc 30) — manual edit to doc
☐ 3. Apply Patch 3 (doc 16) — manual edit to doc
☐ 4. Apply Patch 4 (doc 39) — manual edit to doc
☐ 5. Apply Patch 5 (doc 43 v2) — manual edit to doc
☐ 6. Create vector_business_rules table + seed R1-R11
☐ 7. Implement rules-only scorer (cold start phase)
☐ 8. Implement vector_ride_score_log + vector_bolt_import_staging
☐ 9. Build Bolt screenshot import workflow (Gemini OCR)
☐ 10. Train first CatBoost model from imported data
☐ 11. Deploy in 'transition' mode
☐ 12. Set up weekly retraining cron
☐ 13. Integrate rule revision into WR workflow
```

---

## Reference Map

```text
WHO POINTS TO WHAT:
  
  Doc 57 (master) is the source of truth for ride scoring.
  
  All other docs should reference:
    "See doc 57 §X for ride scoring details"
  
  Instead of duplicating logic that may drift.
```

---

**Document version:** 1.0
**Status:** Patch notes — apply when implementing Vector V1
**Last updated:** 2026-05-17
