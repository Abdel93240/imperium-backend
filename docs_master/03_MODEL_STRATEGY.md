# 03 - Model Strategy (DEPRECATED)

> **This document has been superseded.**

The official model strategy is now defined in:

- [`30_AI_ROUTING_AND_SCORING_POLICY.md`](./30_AI_ROUTING_AND_SCORING_POLICY.md) — model roles, cost distribution, evolution strategy
- [`31_AI_TASKS_AND_RESULTS_CONTRACT.md`](./31_AI_TASKS_AND_RESULTS_CONTRACT.md) — per-task model selection rules

Key model decisions for V1:

```text
🟢 Qwen 32B (local)            — primary router/scorer
🟠 Claude Sonnet 4.6           — balanced reasoning
🟣 Claude Opus 4.8             — premium strategic
⭐ Claude Fable 5              — top tier, WR re-planning / long+complex+durable
🟢 GPT-5.5                     — web research + medical
🔵 Gemini                      — vision/OCR
🎤 Whisper local               — transcription
```

For details, refer to doc 30 sections 2 and 9.

---

**Document status:** DEPRECATED
**Replaced by:** 30, 31
**Date:** 2026-04-28
