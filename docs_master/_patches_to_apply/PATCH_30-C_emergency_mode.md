# Patch 30-C — Emergency Mode

Patch 30-C adds a user-triggered Emergency Mode to the routing policy. It is a
**behavior modifier**, not a shortcut to the heaviest model. Insert as a new
sub-section in §5 (e.g. §5.7) or as a static-rule note in §7; cross-reference
from both.

Rationale: urgency and difficulty are different dimensions. An emergency can be
simple-but-urgent (needs a FAST answer — local/Sonnet) or complex-and-grave
(warrants Opus, or the §5.6 critical mechanic with Fable). Forcing the heaviest
model on every emergency would be counter-productive: Opus/Fable reason deeply
and are slower, while urgency often needs speed. The §5.2 "speed tolerance
(inverted)" criterion already pushes urgent tasks toward the fast tier. So
Emergency Mode raises priority and lifts the cost barrier, but lets normal
scoring still pick the RIGHT model by the task's real nature.

---

## §5.7 — Emergency Mode (user-triggered)

**Trigger**
- The user signals an emergency through the chatbot (e.g. "I have an emergency").
- The AI asks for **explicit confirmation** ("activate Emergency Mode?") to
  prevent accidental activation.
- On confirmation → Emergency Mode ON for the current handling.

**What the mode changes (behavior)**
1. **Max priority** — the task jumps ahead of everything; it interrupts/preempts
   other in-flight processing.
2. **Cost barrier lifted** — as in the §5.6 critical tier, we do not pinch
   pennies; upgrading to a stronger model is allowed without cost retention.
3. **Fast context collection** — the AI immediately asks "explain what is
   happening" to scope the situation quickly, then acts.

**What the mode does NOT change (model choice stays nature-driven)**
- Normal §5 scoring still decides the model by the task's real nature:
  - simple + urgent → fast answer (Qwen 32B / Sonnet 4.6); no time wasted;
  - complex + grave → escalate (Opus 4.8, or the §5.6 critical mechanic with
    Fable 5 if the re-scored gravity reaches ≥180).
- Emergency Mode **never forces** the heaviest model. It lifts the cost barrier
  and sets priority; speed stays king when the task is simple. This is consistent
  with the inverted speed-tolerance criterion (§5.2): urgency biases toward fast
  execution, not toward maximal depth.

**Exit**
- Emergency Mode applies to the current emergency handling and ends when resolved
  (or when the user cancels it). It is not a persistent global state.

---

## Cross-reference
- §5.2 — speed tolerance (inverted): urgency biases toward fast tiers; Emergency
  Mode honors this rather than overriding it.
- §5.6 — if the emergency is genuinely critical (re-scored ≥180), the critical
  mechanic (GPT-5.5 re-score → Opus orchestration → anti-loop breaker) applies
  as usual; Emergency Mode simply guarantees priority and no cost retention.
- §1.6 — Emergency Mode is an explicit, user-confirmed action, so it satisfies
  the "no expensive cloud call without explicit user action" rule by design.
