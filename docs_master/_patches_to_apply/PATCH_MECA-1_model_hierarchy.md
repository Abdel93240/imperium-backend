# Patch MÉCA-1 — Model hierarchy alignment (docs 16, 31, 34, 35, 03, 44)

Mechanical corrections from the model-hierarchy rewrite (doc 30 is the source of
truth). Removes legacy references: Qwen 2.5 7B → Qwen 32B, Opus 4.7 → Opus 4.8,
Haiku removed → Sonnet 4.6 fallback, stale threshold tables → doc 30 §5.6 grid.

Canonical replacements:
```
qwen2.5:7b-instruct / qwen-2.5-7b   → qwen3:32b          (Ollama tag, Q4_K_M)
Qwen 2.5 7B (descriptive text)      → Qwen 32B
Opus 4.7                            → Opus 4.8
Haiku (as fallback / light tier)    → Sonnet 4.6
stale /200 threshold tables         → doc 30 §5.6 grid + 30-B critical mechanic
```

Local model identifier confirmed by web check (June 2026): `qwen3:32b` runs in
~20-24 GB (Q4_K_M), fits the V100 32 GB with margin. FP8 vLLM
(`pytorch/Qwen3-32B-float8dq`, ~34 GB) noted as a later optimization, not adopted.

---

## DOC 16 — AI Backend Layer Overview

- L47 `├─ Qwen 2.5 7B (local Ollama)` → `├─ Qwen 32B (local, GPU-served on V100 / qwen3:32b)`
- L49 `├─ Claude Haiku/Sonnet/Opus (cloud API)` → `├─ Claude Sonnet/Opus (cloud API)` (drop Haiku)
- L91 `(Haiku, Sonnet, Opus, GPT-5.5, Gemini, or Qwen itself)` → `(Sonnet, Opus, GPT-5.5, Gemini, or Qwen itself)`
- L170 `Model: qwen2.5:7b-instruct-q5_K_M (~6 GB RAM)` → `Model: qwen3:32b (Q4_K_M, ~20-24 GB VRAM on V100)`
- L323 `"haiku-4.5",` → remove this list entry (Haiku no longer in hierarchy)
- L365 `WR analysis → Opus 4.7` → `WR re-planning → Fable 5` (RESOLVED: context shows this is a static routing table mirroring doc 30 §7; "WR analysis" here = the WR re-planning task, which doc 30 §7.6 forces on Fable 5)
- L408 `n8n falls back to Haiku 4.5 for routing decisions` → `n8n falls back to Sonnet 4.6 for routing decisions`
- L417 `falls back to Haiku 4.5 (or any cloud model used as substitute)` → `falls back to Sonnet 4.6 (or any cloud model used as substitute)`

## DOC 31 — AI Tasks and Results Contract

- L257 `Qwen 2.5 7B Instruct is the V1 local router/scorer/classifier/preparer.` → `Qwen 32B is the V1 local router/scorer/classifier/preparer.`
- L283 `QWEN_MODEL=qwen2.5:7b-instruct` → `QWEN_MODEL=qwen3:32b`
- L919 `No expensive AI cloud call (Haiku / Sonnet / Opus / GPT / Gemini)` → `No expensive AI cloud call (Sonnet / Opus / Fable / GPT / Gemini)`
- L995 `### 3.4 Qwen 2.5 7B Instruct (local)` → `### 3.4 Qwen 32B (local)`
- L1022 `- Claude Haiku 4.5` → remove this line
- L1024 `- Claude Opus 4.7` → `- Claude Opus 4.8`
- L1042 `external cloud model such as GPT, Claude, Opus, Sonnet, Haiku or Gemini` → `external cloud model such as GPT, Claude, Opus, Sonnet, Fable or Gemini`
- L1177 `routing_model VARCHAR(64) (e.g. qwen-2.5-7b)` → `routing_model VARCHAR(64) (e.g. qwen3:32b)`
- **L1625-1628 threshold table** — replace the whole table:
  ```
  | 0–59 | Qwen local | Execute locally |
  | 60–99 | Haiku 4.5 | Lightweight cloud |
  | 100–139 | Sonnet 4.6 | Balanced reasoning |
  | 140–169 | Opus 4.7 | Deep analysis |
  | 170–200 | Opus 4.7 + guard | Critical analysis, validation gate |
  ```
  with the canonical doc 30 §5.6 grid:
  ```
  | 0–99 | Qwen 32B local | Execute locally |
  | 100–139 | Sonnet 4.6 | Balanced reasoning |
  | 140–179 | Opus 4.8 | Deep analysis |
  | 180–200 | Critical mechanic (doc 30 §5.6 / Patch 30-B) | GPT-5.5 re-score → Opus orchestration |
  ```
  Keep the line "aligned with doc 30" and add: "doc 30 is the source of truth; see §5.6 for the critical-tier mechanic."
- L1843 `Qwen 2.5 7B : official local router/scorer` → `Qwen 32B : official local router/scorer`
- L1898 `Add Haiku / Sonnet / Opus / GPT-5.5 / Gemini progressively.` → `Add Sonnet / Opus / Fable / GPT-5.5 / Gemini progressively.`

## DOC 34 — Pulse Medical Feed AI

- L86 `Opus 4.7 is reserved for the WR analysis (deep reasoning across domains).` → `Fable 5 is reserved for the WR re-planning (deep reasoning across domains).` (RESOLVED: "deep reasoning across domains" = the trans-domain WR re-planning task, forced on Fable 5 by doc 30 §7.6. The following line — GPT-5.5 for medical-to-rules — stays unchanged.)

## DOC 35 — Qwen Setup and Prompts

- L56 `ollama pull qwen2.5:7b-instruct` → `ollama pull qwen3:32b`
- L73 `"model": "qwen2.5:7b-instruct",` → `"model": "qwen3:32b",`
- L93 `whether to escalate to Haiku, Sonnet, Opus, GPT, Gemini Vision, Whisper, ...` → `whether to escalate to Sonnet, Opus, Fable, GPT, Gemini Vision, Whisper, ...`
- **L120-130 threshold block** — replace:
  ```
  0–59    -> Qwen
  60–99   -> Claude Haiku
  100–139 -> Claude Sonnet
  140–169 -> Claude Opus
  170–200 -> strongest model + explicit guardrail
  ```
  with:
  ```
  0–99    -> Qwen 32B local
  100–139 -> Claude Sonnet 4.6
  140–179 -> Claude Opus 4.8
  180–200 -> critical mechanic (doc 30 §5.6 / Patch 30-B)
  ```
  (Doc 35 already says "Doc 30 is the source of truth" — this makes its table match.)

## DOC 03 — Model Strategy

- L13 `🟢 Qwen 2.5 7B Instruct (local) — primary router/scorer` → `🟢 Qwen 32B (local) — primary router/scorer`
- L14 `🟡 Claude Haiku 4.5 — lightweight cloud` → remove this line (Haiku removed; local Qwen 32B covers the low band)
- L16 `🟣 Claude Opus 4.7 — premium strategic (WR analysis)` → `🟣 Claude Opus 4.8 — premium strategic` (and add `⭐ Claude Fable 5 — top tier, WR re-planning / long+complex+durable` if the list is meant to be complete)

## DOC 44

- L163 `Official local router / classifier: Qwen 2.5 7B Instruct` → `Official local router / classifier: Qwen 32B`
- L703 `7. Qwen 2.5 7B Instruct is the official V1 local router.` → `7. Qwen 32B is the official V1 local router.`

---

## Notes / verification flags
- Lines 16 L365 and 34 L86 (WR analysis): RESOLVED → both refer to the
  trans-domain WR re-planning task, set to **Fable 5** (doc 30 §7.6). Not Opus.
- After applying, grep again for `haiku`, `opus 4.7`, `qwen.*7b`, `2.5` across
  these docs to confirm zero remaining legacy references.
- Other docs still holding legacy refs (not in this patch, to do when re-read):
  01, 36, 38, 43, 52, 55, 67 and the inventory files — track in doc 99 backlog.
