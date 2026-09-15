# 03 - Model Strategy (DEPRECATED)

> **This document has been superseded.**

The official model strategy is now defined in:

- [`30_AI_ROUTING_AND_SCORING_POLICY.md`](./30_AI_ROUTING_AND_SCORING_POLICY.md) — model roles, cost distribution, evolution strategy
- [`31_AI_TASKS_AND_RESULTS_CONTRACT.md`](./31_AI_TASKS_AND_RESULTS_CONTRACT.md) — per-task model selection rules

Key model decisions for V1:

```text
🟢 local_executor             — local router/scorer/executor/conductor; mapping in doc 30 §3.3, deployment in F10
🟠 first_cloud_tier           — balanced reasoning
🟣 high_reasoning             — premium strategic
⭐ sustained_long_context              — top tier, WR re-planning / long+complex+durable
🟢 web_fresh_data / health_specialist                     — web research + medical
🔵 OCR service                  — vision/OCR
🎤 Transcription service       — transcription
```

For details, refer to doc 30 sections 2 and 9.

---

**Document status:** DEPRECATED
**Replaced by:** 30, 31
**Date:** 2026-04-28
