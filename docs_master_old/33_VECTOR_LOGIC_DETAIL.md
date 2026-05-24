# 33 — Vector Logic Detail

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
- user feedback on recommendation quality.

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

Possible outputs:

```text
strong_accept
accept
neutral
risky
reject
```

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

Qwen can be called often because Vector needs frequent micro-decisions.

Qwen tasks:

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

Vector learns from VTC outcome data:

- recommendation shown;
- user action;
- real result;
- actual waiting time;
- actual route time;
- actual revenue;
- user correction.

Bad recommendations are valuable if the user gives a clear reason.

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
