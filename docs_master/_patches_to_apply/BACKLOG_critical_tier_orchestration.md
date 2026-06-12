## Backlog Entry — Critical-tier orchestration (doc 30 §5.6)

Context: doc 30 §5.6 critical tier (180–200) defines a two-step mechanic
(GPT-5.5 independent re-scoring → Opus free orchestration) with an anti-loop
circuit breaker. The design is documented; the backend implementation is pending.

To implement (backend):
- **Independent re-scoring call**: when Qwen emits score ≥180, route first to
  GPT-5.5 with the situation + scoring criteria (§5.2/5.3) to re-evaluate. Capture
  GPT-5.5's score; if <180, re-route to the warranted band; if ≥180, proceed.
- **Orchestration handle for Opus**: pass Opus 4.8 the capability profiles of
  Fable 5 and GPT-5.5 so it can delegate/combine.
- **Hand-off counter (circuit breaker)**:
  - Track the number of model-to-model relays within a single critical task.
  - Cap ≈3–4 hand-offs (exact value tunable).
  - Do NOT cap per-model reasoning depth.
  - On cap reached without resolution → force Opus to emit the final answer,
    no further delegation.
- **Logging**: record each hand-off (from_model, to_model, reason, relay_index)
  for later analysis of whether the breaker ever triggers and why.

Status: to_implement. Not urgent (band ≥180 is extremely rare). Referenced by
doc 30 §5.6 (Patch 30-B).
