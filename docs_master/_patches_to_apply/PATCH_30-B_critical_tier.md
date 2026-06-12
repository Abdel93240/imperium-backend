# Patch 30-B — Critical-tier mechanics (§5.6)

Patch 30-B enriches the top band of the dynamic routing table (§5.6). The current
"180–200 → Opus 4.8 + guard" is replaced by an explicit two-step mechanic with an
independent anti-hallucination check and bounded multi-model orchestration.

Rationale: a score ≥180/200 is extremely rare (it requires a task that is
simultaneously very complex, long, ambiguous, high-consequence and sensitive).
When it happens, the gravity of the decision justifies the cost — we do not
pinch pennies on Anthropic credits at this level. But a high score from Qwen may
itself be a hallucination, so it must be independently verified before the heavy
machinery runs.

---

## §5.6 — replace the critical row's handling

Keep the band table as-is for 0–179:

| Score `/200` | Recommended model | Role |
|---:|---|---|
| 0–99 | Qwen 32B local | Execute locally |
| 100–139 | Sonnet 4.6 | Balanced reasoning |
| 140–179 | Opus 4.8 | Deep analysis |
| 180–200 | **Critical mechanic (see below)** | Critical analysis |

Replace the 180–200 cell handling with the following mechanic.

### Critical tier (180–200) — two-step mechanic

**Step 1 — Independent re-scoring (anti-hallucination).**
The 180+ score was produced by Qwen (local scorer), which can hallucinate an
inflated score. Before engaging the heavy machinery, **GPT-5.5** (a different
provider, hallucination-resistant, and with no stake in the execution) receives
the situation + the scoring table (§5.2/5.3) and **re-evaluates the score**.
- If GPT-5.5 lowers it below 180 → re-route to the band actually warranted
  (140–179 Opus 4.8, etc.). No heavy orchestration.
- If GPT-5.5 confirms ≥180 → Step 2.

**Step 2 — Free orchestration by Opus (gravity confirmed).**
Opus 4.8 is given the capability profiles of Fable 5 and GPT-5.5 and is left to
**direct freely**: handle it itself, delegate, or combine. No cap on each model's
depth of reasoning. At this gravity, cost is not a constraint.

**Anti-loop breaker (circuit breaker).**
The real failure mode at this tier is not a single weak model — it is models
relaying to each other indefinitely (hollow back-and-forth, everyone "thinking"
without converging). To prevent it without throttling intelligence:
- A counter bounds the number of **hand-offs between models** (≈3–4 relays max
  for one critical task).
- Each model may reason as deeply as it wants on its own turn (depth NOT capped).
- If the relay cap is reached without resolution → **Opus must produce the final
  answer itself, with no further delegation.** The breaker cuts the hollow loop;
  it does not limit thinking depth.

(The hand-off counter is a design rule; its backend implementation is tracked in
the backlog.)

---

## Cross-reference

This critical mechanic is consistent with:
- §3.8 / §7.5 — GPT-5.5 owns finance/health reasoning and is hallucination-aware.
- §7.6 — Fable 5 is reserved for long + complex + durable-stakes tasks; here Opus
  may route to it during Step 2 if the confirmed-critical task also fits that
  profile.
- The "afficher ≠ raisonner" and "no invented values" principles: GPT-5.5's
  re-scoring must justify itself, not fabricate a verdict.
