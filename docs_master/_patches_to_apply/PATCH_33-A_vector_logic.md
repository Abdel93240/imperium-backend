# Patch 33-A — Vector Logic Corrections (météo, surge, halos, CatBoost learning)

Patch 33-A makes doc 33 the source of truth for Vector logic and aligns it with
decisions from the June 2026 re-read. It also resolves a pending TODO in doc 57
(§5.6 surge features) and adds a redirect note to doc 13.

Ownership: **doc 33 owns Vector business logic**; **doc 57 owns the CatBoost ML
detail** (features, training, surge capture); **doc 13 owns MVP scope/phasing**
and defers logic to doc 33.

---

## A. Doc 33 corrections

### A1 — §3 VTC Inputs: add weather + surge

Add to the §3 input list:
- **weather** — source: **Open-Meteo** (free, no key, Météo-France AROME model,
  city-level via coordinates, ~15-min granularity), complemented by
  **Météo-France department weather alerts** for extreme events. Weather is a
  **demand signal** (rain/snow → higher demand, higher prices).
- **surge / majoration** — current and recent surge multiplier as a demand &
  profitability signal. Detailed mechanism (manual capture, OCR, correlation,
  derived features) lives in **doc 57 §16-17**; doc 33 only references it. Do not
  duplicate the surge detail here.

### A2 — §4 Ride Offer Score: binary verdict + halo + sound (NO real-time text)

The ride-offer evaluation (accept-a-ride feature) is **binary**. There are only
two real actions when working: take it or don't.

Replace the five-level output (`strong_accept/accept/neutral/risky/reject`) with:
```text
CatBoost ride verdict → 2 outcomes only:
  PROFITABLE     → GREEN halo + "take it" sound
  NOT PROFITABLE → RED halo  + "leave it" sound
(WHITE halo + sound = assistant active / online — not a ride verdict)
```
- Weather and surge feed the score (as inputs, A1).
- Output is a **signal only**: halo + sound. **No natural-language explanation in
  real time.** Goal: speed and efficiency while driving, zero friction, zero text.
- The score still includes the existing economics (hourly_rate_estimate,
  dead_return_penalty, pickup_waste_penalty, traffic_risk_penalty,
  strategic_zone_bonus, event_or_airport_bonus) — but its **user-facing output**
  is the binary halo/sound, not a label list.

Note: this is the accept-a-ride feature ONLY. **Zone recommendation (§5) is a
separate, already-documented feature and is unchanged** — it keeps its short
textual reason (the driver is not mid-ride when repositioning, so a brief reason
is useful there).

### A3 — §6 Qwen Role: CatBoost scores, Qwen does NOT explain ride verdicts in real time

Clarify the split:
- **Ride classification/scoring = CatBoost only** (the ML metric model). Qwen does
  NOT classify rides and does NOT verbalize the verdict in real time.
- Natural-language commentary about rides exists **only after the fact**, in the
  **Vector report inside the Weekly Review** (built on recorded history), never
  during live work.
- Qwen keeps its non-scoring micro-roles where they make sense off the critical
  driving path (e.g. classify user feedback, triage OCR data, detect bad/missing
  data, decide escalation) — but not ride scoring and not live ride explanations.

### A4 — §8 Learning Loop: hourly revenue target, refusals recorded-not-learned, WR refinement loop

Replace the learning signals with:
- **CatBoost learns on the OBJECTIVE hourly revenue** = ride earning ÷ **total
  mobilized time** (approach + wait + ride + estimated return), computed **to the
  minute** (not in ¼h/½h blocks, which distort short VTC rides).
- **CatBoost does NOT learn on accepted/refused outcome.** A refusal is polluted
  by fatigue, end-of-day, mood — learning on it would corrupt the profitability
  model.
- **Refusals ARE recorded** — they are valuable BEHAVIORAL data for the brain (not
  for CatBoost training). Example: in the Weekly Review the brain can flag "Vector
  judged these rides profitable, yet you refused many — why?", and cross it with
  other signals (missed missions, etc.) as a **mental-load / burnout indicator**.
- **WR refinement loop (supervised):** the binary verdict is intentionally
  imprecise at cold start; the user does not blindly follow it. The Weekly Review
  analyzes the **gap between CatBoost verdicts and the user's actual decisions**
  and produces refinement data CatBoost can use to sharpen its business logic.
  So: CatBoost learns directly on hourly revenue, AND the brain (via WR) prepares
  supervised corrections from the verdict-vs-decision gap. Raw refusals are never
  learned directly.

---

## B. Doc 57 — resolve the pending §5.6 TODO

§17.1 of doc 57 says the surge features are "to add in §5". Apply it: in
**§5.6 External signals (V2 — to add)**, under TRANSPORT DISRUPTIONS / EVENTS,
insert:
```text
SURGE HISTORY (from manual captures — see §16):
├─ zone_surge_recent_avg        — avg surge multiplier in zone, last N min
├─ zone_surge_trend             — rising | flat | falling (last 10 min)
└─ zone_surge_at_similar_time   — historical surge for this zone + time_block
```
Also add `weather` (Open-Meteo) explicitly to §5.6 external signals if not
already present, as a demand feature.

(The surge capture/correlation logic in §16-17 is already complete and correct;
only the §5.6 feature-list reference was pending.)

---

## C. Doc 13 — redirect note

Doc 13 (`MVP_PHASE_DECISION`) overlaps doc 33 on ride scoring, learning, and Qwen
role, which risks divergence. Add a note at the top of doc 13's logic sections:

> Vector logic (ride scoring, learning loop, halos, CatBoost/Qwen split, weather,
> surge) is owned by **doc 33** (and the ML detail by **doc 57**). This document
> only fixes MVP scope/phasing. For any logic detail, see doc 33 — do not
> duplicate it here.

Then trim doc 13's §3.3 / §4 detail to a pointer to doc 33 (keep only what is
genuinely about MVP phase scope).
