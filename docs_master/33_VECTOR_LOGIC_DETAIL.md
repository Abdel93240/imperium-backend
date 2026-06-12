# 33 - Vector Logic Detail

Vector is the VTC profitability intelligence layer.

It is intentionally narrow: it optimizes the user's VTC work, not the user's global life.

## 1. Core Objective

Vector exists to answer one operational question:

```text
What VTC action is most profitable and least wasteful now?
```

That can mean:

- accept or reject a ride recommendation;
- reposition to a zone;
- avoid a dead-return trap;
- wait or move;
- use an event signal;
- exploit a rail disruption;
- avoid road closures;
- protect scheduled ride value.

## 2. Explicit Boundary

Vector does not use the following as decision inputs in V1:

- fatigue;
- sleep quality;
- mood;
- stress;
- family pressure;
- financial pressure;
- global daily objective;
- workout plan;
- worship plan;
- medical data.

Imperium can use those signals globally. Pulse can use health signals. Vault can use finance signals. Vector remains VTC profitability only.

## 3. VTC Inputs

Vector can use:

- current VTC zone;
- time and day;
- ride price;
- pickup ETA;
- pickup distance;
- estimated trip duration;
- destination zone;
- route and traffic risk;
- road closures;
- rail disruptions;
- event signals;
- airport demand windows;
- scheduled rides;
- fuel/autonomy only when it affects VTC execution;
- historical session outcomes;
- user feedback on recommendation quality;
- **weather** — source: **Open-Meteo** (free, no key, Météo-France AROME model, city-level via coordinates, ~15-min granularity), complemented by **Météo-France department weather alerts** for extreme events. Weather is a **demand signal** (rain/snow → higher demand, higher prices);
- **surge / majoration** — current and recent surge multiplier as a demand & profitability signal. Detailed mechanism (manual capture, OCR, correlation, derived features) lives in **doc 57 §16-17**; doc 33 only references it.

## 4. Ride Offer Score

A ride offer should be scored with VTC economics:

```text
profitability_score = hourly_rate_estimate
                    - dead_return_penalty
                    - pickup_waste_penalty
                    - traffic_risk_penalty
                    + strategic_zone_bonus
                    + event_or_airport_bonus
```

The result is advisory only.

The ride-offer evaluation (accept-a-ride feature) is **binary**. There are only two real actions when working: take it or don't.

```text
CatBoost ride verdict → 2 outcomes only:
  PROFITABLE     → GREEN halo + "take it" sound
  NOT PROFITABLE → RED halo  + "leave it" sound
(WHITE halo + sound = assistant active / online — not a ride verdict)
```

- Weather and surge feed the score (as inputs, see §3).
- Output is a **signal only**: halo + sound. **No natural-language explanation in real time.** Goal: speed and efficiency while driving, zero friction, zero text.
- The score still includes the existing economics (hourly_rate_estimate, dead_return_penalty, pickup_waste_penalty, traffic_risk_penalty, strategic_zone_bonus, event_or_airport_bonus) — but its **user-facing output** is the binary halo/sound, not a label list.

Note: this is the accept-a-ride feature ONLY. **Zone recommendation (§5) is a separate, already-documented feature and is unchanged** — it keeps its short textual reason (the driver is not mid-ride when repositioning, so a brief reason is useful there).

## 5. Zone Recommendation

Vector may recommend:

- stay here;
- move to a named zone;
- return toward Paris;
- move near a station;
- move near an event exit;
- avoid a zone;
- wait for scheduled ride.

Each recommendation must include a short reason.

Example:

```json
{
  "recommendation": "move_to_zone",
  "zone": "Bercy",
  "reason": "Event ending soon, high pickup density expected, low dead-return risk.",
  "confidence": 0.74
}
```

## 6. Qwen Role in Vector

The split is strict:

- **Ride classification/scoring = CatBoost only** (the ML metric model). Qwen does NOT classify rides and does NOT verbalize the verdict in real time.
- Natural-language commentary about rides exists **only after the fact**, in the **Vector report inside the Weekly Review** (built on recorded history), never during live work.
- Qwen keeps its non-scoring micro-roles where they make sense off the critical driving path — but not ride scoring and not live ride explanations.

Qwen can be called often because Vector needs frequent micro-decisions.

Qwen tasks (off the critical driving path):

- classify user feedback;
- summarize why a zone is attractive;
- compare two zones;
- triage ride screenshots after OCR;
- detect bad or incomplete data;
- decide whether escalation is needed.

Qwen should not invent data. If a required VTC input is missing, it must ask for clarification or return low confidence.

## 7. Escalation

Escalate to a stronger model only when:

- context is long;
- the decision has high operational impact;
- multiple feeds conflict;
- Qwen confidence is low;
- the user explicitly asks for deeper strategy.

Routine VTC micro-decisions should stay local and cheap.

## 8. Learning Loop

- **CatBoost learns on the OBJECTIVE hourly revenue** = ride earning ÷ **total mobilized time** (approach + wait + ride + estimated return), computed **to the minute** (not in ¼h/½h blocks, which distort short VTC rides).
- **CatBoost does NOT learn on accepted/refused outcome.** A refusal is polluted by fatigue, end-of-day, mood — learning on it would corrupt the profitability model.
- **Refusals ARE recorded** — they are valuable BEHAVIORAL data for the brain (not for CatBoost training). Example: in the Weekly Review the brain can flag "Vector judged these rides profitable, yet you refused many — why?", and cross it with other signals (missed missions, etc.) as a **mental-load / burnout indicator**.
- **WR refinement loop (supervised):** the binary verdict is intentionally imprecise at cold start; the user does not blindly follow it. The Weekly Review analyzes the **gap between CatBoost verdicts and the user's actual decisions** and produces refinement data CatBoost can use to sharpen its business logic. So: CatBoost learns directly on hourly revenue, AND the brain (via WR) prepares supervised corrections from the verdict-vs-decision gap. Raw refusals are never learned directly.

## 9. Compliance

Vector never auto-clicks Bolt.

Vector never automates ride acceptance.

Vector only advises. The user decides.

## 10. Future Vector Reports

A future weekly Vector report may summarize:

- best zones;
- worst zones;
- dead-return losses;
- airport timing accuracy;
- event signal accuracy;
- recommendation win/loss rate;
- average hourly rate.

It must not summarize fatigue, personal pressure, health, worship, or global life objectives.
