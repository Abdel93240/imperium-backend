# 13 — Vector MVP Phase Decision

## 1. Official Scope

Vector is the VTC profitability and execution assistant.

Its job is to help the user earn more per hour, avoid bad rides, reduce dead time, and position correctly around zones, events, airports, stations, disruptions, road closures, and learned VTC patterns.

Vector does not manage the user's global life balance. Imperium handles global priorities, fatigue, pressure, daily objectives, health, and life planning.

## 2. Non-Negotiable Boundary

Vector must never auto-click, auto-accept, bypass Bolt protections, or manipulate the Bolt application.

Vector can:

- read user-provided or permissioned signals;
- analyze screenshots or manual ride data;
- estimate profitability;
- recommend a zone or action;
- explain why a ride or zone looks good or bad;
- learn from user feedback.

Vector cannot:

- accept a ride automatically;
- click in Bolt;
- scrape private data outside approved capture flows;
- make health or personal life decisions;
- adjust recommendations based on fatigue, mood, family pressure, or global daily objective.

> Vector logic (ride scoring, learning loop, halos, CatBoost/Qwen split, weather,
> surge) is owned by **doc 33** (and the ML detail by **doc 57**). This document
> only fixes MVP scope/phasing. For any logic detail, see doc 33 — do not
> duplicate it here.

## 3. V1 Functional Scope

### 3.1 Ride Offer Evaluation

Vector evaluates a ride using VTC variables only:

- offered price;
- pickup distance;
- pickup ETA;
- drop-off zone;
- estimated full duration;
- dead-return risk;
- expected hourly rate;
- event or airport value;
- traffic and closure risk;
- known zone history;
- scheduled ride opportunity cost.

### 3.2 Zone Recommendation

Vector can answer:

```text
Where should I go now?
```

The answer is based on VTC profitability signals only:

- current location;
- time window;
- day type;
- nearby demand signals;
- events;
- rail disruptions;
- airport demand windows;
- traffic and closures;
- learned zone performance;
- dead-mile risk.

### 3.3 Session Learning

Session learning is in V1 scope. The learning-loop logic (what CatBoost learns, what is recorded but not learned) is owned by **doc 33 §8** — see doc 33.

It does not learn personal fatigue or emotional state. Those belong to Imperium/Pulse.

## 4. Role of Qwen

The CatBoost/Qwen split (CatBoost scores rides; Qwen keeps non-scoring micro-roles off the critical driving path; no real-time ride explanations) is owned by **doc 33 §6** — see doc 33.

For high-impact or ambiguous strategic cases, the AI routing policy can escalate to a stronger model, but the result remains advisory.

## 5. Inputs Vector May Use

Allowed V1 inputs:

- user location while Vector is active;
- ride screenshot OCR output;
- manual ride/session data;
- map ETA;
- event feeds;
- rail disruption feeds;
- airport/flight-derived demand windows;
- road closure data;
- historical Vector outcomes.

Not allowed in Vector V1 decision logic:

- fatigue;
- mood;
- sleep quality;
- financial pressure;
- family pressure;
- global daily objective;
- worship schedule;
- workout plan;
- medical status.

These can exist elsewhere in Imperium, but they must not drive Vector profitability recommendations in V1.

## 6. V1 Success Criteria

Vector V1 is successful if it can:

- recommend profitable zones;
- warn against fake profitability;
- identify dead-return traps;
- use events/disruptions before Bolt surge becomes obvious;
- keep a clean learning history;
- remain compliant by never automating ride acceptance.

## 7. Future Extensions

Possible later features:

- stronger learned zone model;
- event score calibration;
- airport passenger-delay model;
- user feedback scoring;
- route profitability simulation;
- Vector-specific weekly profitability report.

Cross-domain health or life optimization remains outside Vector. Imperium orchestrates those decisions.
