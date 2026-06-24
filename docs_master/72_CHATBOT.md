# 72 - Chatbot (Universal Entry Point)

## 1. Purpose

The chatbot is the **universal entry point** to the whole ecosystem. Anything a button
does, the chatbot can do (replan, create, modify, validate, delete...). It is the
single conversational surface through which the user drives Imperium by natural
language (typed or voice-transcribed).

It is NOT a generic assistant like a public chatbot. Its reason for being is **access
to the ecosystem's data and actions** under the user's control. It is generalist, holds
all authorizations, and **never acts on its own** — every action is proposed and waits
for explicit user validation before being committed.

This document owns: the chatbot's nature, its engine and escalation model, the
per-message scoring, the closing-scoring (learning extraction), the non-blocking
post-close processing, the log browser (transparency), the write authority, and the
degraded mode. Other docs refer here for anything chatbot-related.

---

## 2. Core Principles

- **Generalist, all authorizations.** No hard topic barriers. Imperium runs the user's
  whole life, so a generalist recipe to add into Pulse is as legitimate as a ride
  question. The user defines the use, not a built-in restriction.
- **Never acts alone.** The chatbot proposes; the user validates; only then is anything
  written. Validation is non-negotiable (see doc 08 for the inviolable rule).
- **One interlocutor.** The user always talks to the local model. Other models,
  when used, work behind the scenes — the user never converses with them directly.
- **Minimal interface.** Conversation view + keyboard input + a mic button (voice → text
  transcription only) + send + a close (cross). Nothing else is required of the user.

---

## 3. Engine & Invisible Escalation

The engine is the **local model**. It is the only party the user speaks
to, always.

### 3.1 Per-message scoring

On every user message, the FIRST thing the local model does is **score its own ability** to handle
that message (the /200 scale of doc 30). Based on the score:
- low → the local model answers locally, alone (free).
- high → the local model calls another model to answer in its place, then relays the answer itself.

### 3.2 Escalation is invisible (as a change of interlocutor)

When the local model escalates, the user does not switch to another model. The local
model stays the face of the conversation. Concretely (health example):
- User: "the training you give me isn't producing results anymore, can we discuss it?"
- The local model scores this high (health domain, beyond its own reliable scope).
- The local model routes health questions to the health specialist. It **anonymizes
  generically** before sending: "a man of such weight, doing such exercises, with such a
  goal, who has already tried X/Y/Z and eats such things daily — what would you advise?"
- The health specialist answers the local model; the local model relays the answer to the
  user in its own voice.
- User side: it "loads a bit" while the models work, then the answer arrives in the
  thread. The user keeps talking to the local model.

The **generic anonymization at escalation IS the privacy gate in action**: the local
model never ships the raw identified dossier to the cloud; it reformulates into an anonymous,
generic case. See doc 52 §9A (access-regime principle) and doc 37 for the same logic
applied to the OCR service.

---

## 4. Write Authority (3 levels, always under user validation)

The chatbot can, ALWAYS on explicit user validation:

- **Level 1 — ADD** (documents, missions, entries).
- **Level 2 — MODIFY** an existing item.
- **Level 3 — DELETE**, with an honest technical limit:
  - deletes the raw document/data;
  - deletes or **supersedes** (doc 09) the DIRECT learning elements derived from it
    (found via `source_table`/`source_id`);
  - CANNOT undo the INDIRECT influences already propagated (a pattern whose confidence
    rose, a past WR conclusion). Supersession neutralizes future reliance; it does not
    rewrite the past.

The "validation required" rule is an inviolable non-negotiable → owned by doc 08. This
document describes the capability; doc 08 owns the guardrail.

---

## 5. Validation as the Tipping Point

While a proposal lives **inside the chatbot**, nothing is engraved. It is a malleable
draft: the user iterates freely ("replan my month" → 30 days proposed → "why day 26?
change it" → discuss until right).

- BEFORE validation: conversational draft, nothing written.
- AT validation: the **result** is engraved (written to the database, executed).

Validation is on the **result**, not action by action. The number of actions is
irrelevant — one validation for the 30 days if they suit; otherwise keep discussing,
then validate. Validation is the moment the conversational becomes real.

---

## 6. Closing: Learning Extraction

Closing the chatbot (cross) ends the session and triggers learning extraction. This is
a **distinct mechanism** from the /200 routing scale — the question here is not "which
model handles this" but "does this session contain something worth learning, and what".

### 6.1 Three passes

**Pass 1 — structured detection via an injected grid.** The local model reads the session ONCE
against a closed grid of learning-element types and reports, per type, whether it is
present and on what subject. The grid is NOT a vague "is this valuable?" judgment — it
is classification against defined categories, which a local model does reliably.
- If the grid returns nothing → purely operational session, no extraction; the text log
  is kept regardless.
- If it returns elements → continue.

**Pass 2 — qualification (local).** For each detected element, the local model evaluates:
- the **domain** (vtc, sport, finance, religious, project...) — for routing and
  sensitivity;
- **novelty vs redundancy**: is this already in `ai_memories`, or new? (a semantic
  search, not a judgment) — to avoid re-vectorizing the same thing repeatedly.

**Pass 3 — extraction / escalation.** With the grid filled, the decision is mechanical:
- simple + non-sensitive + new → the local model extracts locally (free);
- dense/nuanced (the local model judges it struggles to phrase cleanly) → escalate extraction for
  quality;
- redundant → do not re-extract; reinforce the existing element's confidence instead.

**The detection itself is scorable.** Before doing the analysis, the local model can score its own
ability to do it; if it judges the session too complex to analyze reliably alone, it
escalates the ANALYSIS (typically to the first cloud tier — it should not exceed that for detection).
This reuses the per-message scoring mechanism (§3.1).

### 6.2 The detection grid (editable data, not hard-coded)

The grid is a **separate editable data file**, not logic baked into code. The program
does "for the injected list of types, detect each one" — so changing the grid changes
behavior without touching code.

- Each entry is `{type, definition, example}` — NOT a bare word. A bare word is too
  ambiguous for reliable classification; a short definition + example gives the model a
  clean target.
- Initial grid = the learning-element types of doc 09: `insight`, `decision`,
  `pattern`, `win`, `blocker`.
- **Open list**: types can be added or removed. Adding "hesitation" makes it 6 passes-
  worth of targets; removing one makes it 4. But the whole grid is injected into a
  SINGLE pass (not N separate passes), so it scales without cost explosion.
- **How a type is added**: always by user-validated proposal, never by the chatbot on
  its own. Typically the high reasoning model proposes one in a WR ("it would help to track the user's
  hesitations"); the user adds it via the chatbot ("add hesitation to the detection
  grid"); the chatbot edits the data file. Guardrail (per doc 09 open-list rule): a new
  type is added only after being checked against another model to confirm it is not
  already covered by crossing existing types (no redundancy). The list stays small by
  construction (~5, rarely more) because the high reasoning model groups rather than multiplies.

---

## 7. Non-Blocking Post-Close Processing

Closing must NEVER make the user wait. The cross closes the chatbot and the user
**immediately** moves on to the rest of the interface. The extraction (detection,
qualification, possible multiple escalations) runs **fully in the background**, invisible
— it can be long (several escalations for a dense session), and the user never feels it.

This mirrors the WR entry-audit, which runs automatically (e.g. Tuesday 20:00, before
the banner appears) so that tapping the banner never waits on a long audit. Same
principle: heavy computation happens in the background; the user never absorbs the
latency.

Because processing happens AFTER the box is closed (the close is precisely what triggers
it), there is no in-chatbot review screen before closing — review is consulted on demand
afterward (see §8).

---

## 8. Transparency: the AI Log Browser (Settings)

Transparency is provided by a **log browser in Settings**, consulted on demand — not by
a pop-up that interrupts. Nothing surges at the user; the user goes to look when they
have a doubt.

Location: Imperium → Settings → Intelligence Artificielle → Logs.

Layout: a small **sandboxed file browser** on the left (navigate the AI-log folders
only), a display terminal on the right showing the selected log's contents. Sorted by
recency with explicit names, so the latest extractions are reachable in one tap without
digging.

Rules:
- **Sandboxed**: confined to the AI logs only, **read-only**, never the rest of the
  file system. (Security: a browser with access to everything would be a hole, and a
  risk for medical/religious data.)
- **Read-only; correction goes through the chatbot.** The browser SHOWS; the chatbot
  ACTS. If the user spots a bad extraction, they tell the chatbot ("in yesterday's
  session you misread X, remove it"), which applies write-authority level 3 (§4).
- **On-demand, not imposed.** The user is never required to review for the system to
  work — the cross alone suffices. The browser is a right of inspection, not a chore.

Why it matters — it makes the "bet on the local model" **observable and reversible**. The whole
extraction design bets that the local model is good enough. The browser lets the user
SEE, session after session, what was extracted/vectorized. If the local model extracts poorly,
the user sees it directly → a signal that it is time to move to a stronger local model —
and they see it before bad data accumulates. The bet is not blind; it is tested in real
conditions and reversible on evidence.

Note: this browser is described here because the chatbot is its primary consumer, but it
is a general transparency tool (WR logs, scoring decisions, etc. may use it too). Other
docs refer here rather than redescribing it.

---

## 9. Session Logging & Memory

- **Log kept as text** (tier 1), same status as the WR log. The full session text is
  retained.
- **Input audio is deleted after transcription**; the text is kept.
- **What gets vectorized**: only the learning elements extracted from the session (into
  `ai_memories`), pointing back to the log. The log itself is not vectorized. Consistent
  with docs 09 / 38 / 47.
- **Dense sessions** may use the ephemeral working vector store (doc 38 §7-bis) for RAG
  without saturating the local context window.

---

## 10. Degraded Mode (local engine down)

If the local engine is down, the fallback is the first cloud tier (doc 52 §9A), but the
first cloud tier has **no access to very_high data** (health, religious). So the chatbot runs in **explicit
partial mode**:

- Imperium, VTC, and part of finances (non-very_high) keep working.
- Pulse and Path (health / religious) are unavailable for now: the chatbot **says so
  explicitly** ("the local engine is unavailable, I can't access your health data for
  the moment, but I can help with the rest"). No silent or cryptic failure.

This is the access-regime principle (doc 52 §9A) applied to the chatbot: a degraded
service is preferred over leaking sensitive data, and the user is told why and that it
will return.

---

## 11. References

- Doc 30: the /200 routing scale (per-message scoring, §3.1).
- Doc 09: learning-element types (the initial detection grid, §6.2) and supersession
  (write authority level 3, §4).
- Doc 38: vectorization pipeline (§9) and the ephemeral working vector store (§6/§9).
- Doc 47 / 32: WR logs and the same rich-log philosophy; the WR may use the log browser
  (§8).
- Doc 52 §9A: local degradation & cloud fallback (the access-regime principle behind
  §3.2, §10).
- Doc 37: vision/OCR prompts — same anonymization/gate logic on escalation.
- Doc 08: the inviolable "validation required" rule (write authority, §4).
- Doc 74: training-example collection — distinct from vectorized memory (§9) and from
  the raw log; a third use of the same source data.
