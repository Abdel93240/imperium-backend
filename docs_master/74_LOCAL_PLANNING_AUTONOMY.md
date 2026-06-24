# 74 - Local Planning Autonomy (LoRA target)

## 1. Purpose

Long-term objective: bring the **monthly planning** — the system's only fully
autonomous decision — back in-house, onto the **local model**, to cut the dependency
on the high reasoning model for the core of Imperium.

The means is a **LoRA** adapter carrying **the user's planning logic** (not the user's
data — data lives in RAG / `ai_memories`), targeting the **local 70B** model (not the
current local model), running on **3× V100** (phase 4, see F10).

This document owns: the autonomy objective, the two-type replanning distinction, the
training-example collection strategy, the cloud training + local inference split, and
the privacy protection for training. It does NOT redefine vectorization (see docs
09/38).

---

## 2. Why this matters

Today the autonomous monthly plan is produced by the high reasoning model. That is the single
point where Imperium depends on an external provider for a core cognitive function.
A local 70B carrying the user's own planning logic (via LoRA) would close that gap.

This is a **distant** objective (phase 4 hardware), but the **data that makes it
possible must be collected starting now** — otherwise phase 4 arrives empty-handed.

---

## 3. The means: a LoRA on the user's logic

- The LoRA encodes the user's **planning logic** (how they decide), learned from real
  corrections. It does NOT encode facts — facts are retrieved live via RAG.
- Target = the **local 70B** (phase 4), not the current local model. A 70B + the user's logic is a
  serious planning capability, much closer to the high reasoning model than the local model alone.
- **Fallback value (not all-or-nothing):** even if the LoRA never fully replaces the
  high reasoning model on monthly planning, it still improves the local model's daily work —
  the self-scoring (`can I answer? is this urgent?`) and the small daily decisions
  (`I'm tired → skip / shift / wait`). So the LoRA has standalone value even if the
  headline goal is not reached.

---

## 4. Two types of replanning (only ONE is training data)

Every replan ("I disagree, replan this") hides two sub-cases:

1. **Replan due to an UNFORESEEN event** (a client cancelled, the calendar changed).
   The high reasoning model could not have known; nobody could. This is the randomness of life, NOT a
   logic error → **discarded** from the training set.
2. **Replan due to DISAGREEMENT with the plan** (the model decided X, the user's logic
   says Y). This is gold: it captures exactly where the user's decision logic differs
   from the model's → **kept** as training data.

Within type 2, a further split:
- **2a — systematic disagreement** ("I always put sport in the morning") = stable
  logic → keep.
- **2b — one-off / mood disagreement** ("that day I didn't feel like it") = noise →
  not a logic pattern.

The training set must keep 2a (logic) and avoid 2b (mood), or the LoRA learns the
user's whims instead of their logic.

### Why the sort is already solved by design

The user **cannot replan without giving a clear reason** (mandatory field, originally
created for vectorization). That forced "why" is exactly what distinguishes the types:
a reason like "client cancelled" (type 1) reads differently from "I prefer sport in the
morning" (type 2a). The sort is **encoded in the obligation to justify** — no separate
mechanism needed.

---

## 5. Collect training examples starting NOW

All of this depends on one cheap, immediate action: **do not throw away what will
serve, and capture it in the right shape from the start.** The value of the future
LoRA is decided by the quality of today's logs.

Sources that feed the training corpus (same source data, reused — not a new capture
mechanism):
- **WR output audits** + the in-week corrections (the planning disagreements).
- **Rich logs already kept** (WR log, chatbot session log) — already retained as text
  (tier 1), they double as raw material for examples.
- **Validated/corrected scoring decisions** — each is an example of "the right call
  here, and why".

### Capture the 3 elements per decision

For each planning decision, the schema must store the **three** pieces:
1. the model's **proposed** plan,
2. the user's **correction**,
3. the **reason**.

⚠️ Deployment check: verify the schema stores the **initial proposal**, not only the
final reason. Without the proposal, the example is incomplete (no "rejected" side).

---

## 6. Example format: a dedicated, formatted training document

**The raw WR output audit is NOT a good training example.** It is rich but noisy
(input data + conversation + conclusions all mixed). LoRA is highly sensitive to noise:
clean small datasets beat large noisy ones. Feeding raw audits to the GPU trains on
garbage around the signal.

→ The WR guided-output step produces, IN ADDITION to the audit and the vectorized
learning elements, a **dedicated training-example document** ("week's examples"),
formatted for training:

- one **structured pair per decision**: condensed context + **proposed** plan (model,
  the "rejected" side) + **validated correction** (user, the "chosen" side) + **reason**.
- a **preference-pair shape** (chosen / rejected). This is the natural form of type-2
  replanning data and maps directly to modern preference-tuning (DPO-style), as well
  as instruction-response tuning.
- written in a precise, "expert" form for training — distinct from the raw audit.
- it is the **same source data, re-formatted** for this one purpose. No new data is
  invented.

This document is produced periodically (e.g. per week) and accumulates into the corpus.

---

## 7. Three distinct uses of the same source data (do NOT confuse)

The same source (type-2 replan, WR audit, chatbot log, validated scoring) serves THREE
different purposes through THREE different mechanisms, toward THREE destinations:

1. **MEMORY (vectorization):** learning elements → `ai_memories` (permanent) for
   semantic recall. Mechanism = embedding. Owned by docs 09/38. NOT redefined here.
2. **RAW LOG (audit/trace):** the full rich log kept as text (tier 1) for audit.
   Owned by the retention/WR docs.
3. **TRAINING DATASET (this doc):** the formatted example document (§6), a corpus of
   preference pairs for LoRA training. Mechanism = an examples file, NOT vectorization.

These never collapse into one another. In particular, the training corpus is **not**
the vectorized memory and is **not** the raw audit — it is a third, purpose-built form.

---

## 8. Training in the cloud, inference at home

- **Inference:** the 70B + LoRA **runs locally** on 3× V100 (phase 4). Day-to-day use
  is fully local.
- **Training:** the LoRA is **trained on a rented cloud GPU** (one-off, a few hours on
  a large card such as an A100). Local hardware (several V100) is enough to RUN a 70B,
  but NOT to train a LoRA on it correctly — only the training is offloaded.
- Cloud to **build** the adapter; local to **use** it. Consistent with the local-first
  philosophy: only the one-off training leaves the premises.

---

## 9. Privacy protection for training

Training data is the user's most intimate material (health, religion, finances pass
through WRs and the chatbot). One day it goes to a rented cloud GPU. This must be
protected, decided now (before the data is mixed and it is too late):

- **Complete training, all domains** (medical, religious included) — no amputation, or
  the 70B would be weak on central domains of the user's life.
- **High-guarantee provider:** European, GDPR, strong retention/erasure policy. No
  peer-to-peer / individual-rented machines.
- **Strong DE-IDENTIFICATION before sending:** sever the content from the identity.
  Keep the signal ("a user has such a health condition / such a practice"), remove
  every identifier (name, location, dates, cross-references that allow re-identifying
  the user). Goal: a reader of the data sees an ANONYMOUS user, never WHO.
- ⚠️ Vigilance: free-text de-identification is hard (indirect re-identifying details).
  To be done carefully when the time comes, with dedicated tooling.

This mirrors the cloud-fallback rule elsewhere (ephemeral store doc 38, OCR service fallback
doc 37): going to the cloud changes the access regime; the privacy gate / de-id
interposes. Service or capability is degraded before sensitive identity leaks.

---

## 10. Mixing general data at training time

At training time, do NOT train on the user's examples alone. Mix a small share
(~5–10%) of general instruction-following data into the set to preserve the 70B's broad
capabilities and avoid catastrophic forgetting (the model becoming good at the user's
logic but degrading on general tasks). This is a training-time concern, noted here for
the day of training; it does not affect collection.

---

## 11. Success conditions and exit door

- The LoRA is worth deploying only if the local 70B + LoRA plans **at least as well**
  as the high reasoning model on the monthly task.
- **Exit door:** if local + LoRA does not match the high reasoning model when the time comes,
  keep the high reasoning model for monthly planning. Autonomy is not worth a system that
  decides worse. The fallback daily value (§3) remains regardless.

---

## 12. References

- WR docs (32 / 47): output audits and corrections are part of the dataset; the
  formatted example document (§6) is produced by the WR guided-output step.
- Replan mechanics docs: the three-element capture (proposal + correction + reason)
  must be wired there.
- Doc 30: model hierarchy (high reasoning model for monthly planning today; local 70B + LoRA is
  the future target).
- F10: phase 4 hardware (local 70B on several recent Tesla cards).
- Docs 09 / 38: vectorization and memory — distinct from the training dataset (§7).
- AI calibration console doc: the local model's inference levers (separate from LoRA).
