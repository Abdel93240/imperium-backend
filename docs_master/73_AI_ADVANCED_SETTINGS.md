# 73 - AI Advanced Settings (technical, builder-only)

> Technical document for the BUILDER. Owns the single entry point **"AI Advanced
> Settings"** inside Imperium and everything behind it: the role → provider → model →
> effort mapping (editable), the scoring thresholds, the API keys, and the vectorization
> CALIBRATION CONSOLE (on the Tower). Unified entry, distributed execution: one menu, but
> each lever acts where it runs (Tower for vectorization, VPS for scoring/routing).
> These values are set during testing, then revised RARELY (a few times a year) as the
> vector memory grows.

---

## 0. Principle: one entry point, distributed execution

The builder IS the user. There is no separate "end user" from whom technical complexity
must be hidden, so there is no product/technical split to maintain. Everything technical
lives behind a single, comfortable menu instead of being scattered between terminal,
a hidden Tower console, and the app.

```text
Imperium → Settings → AI Advanced Settings
  ├─ Vectorization     → opens the calibration console (HTML on the Tower)   [Part D]
  ├─ Role mapping      → edit which provider/model/effort serves each role   [Part B]
  ├─ Scoring /200      → routing thresholds (edited in app, applied on VPS)   [Part C]
  └─ API keys          → provider credentials
```

Key point — **unified interface, distributed execution.** The menu is one place (where
the builder goes), but the levers act where the thing they pilot runs:

```text
LEVER                         RUNS ON                 EDITED FROM
──────────────────────────────────────────────────────────────────────
Vectorization                 Tower (embedding,       AI Advanced Settings
(chunk, top-K, threshold,     local retrieval)        → opens Tower HTML console
 quantization, temperature)
──────────────────────────────────────────────────────────────────────
Scoring /200 + routing        VPS (routing, cloud     AI Advanced Settings
thresholds                    calls originate here)   → applied on VPS
──────────────────────────────────────────────────────────────────────
Role mapping (provider/       VPS (the call layer     AI Advanced Settings
model/effort)                 reads config)           → applied on VPS
```

A reading not to make: "put everything on the Tower". Scoring and routing are owned by
the Imperium core on the VPS (cloud calls originate from the VPS), so their setting
cannot live on the Tower — it would be incoherent. The menu unifies *access*, not
*execution*.

The three operational levels remain:

```text
1. AI ADVANCED SETTINGS (this)  : all technical levers behind one menu. For the BUILDER.
                                  Editable fields + buttons, NOT raw terminal.
2. CALIBRATION CONSOLE (Part D) : the vectorization sub-tool, runs on the Tower, opened
                                  from the Vectorization entry above.
3. TERMINAL                     : only rare/deep ops (deployment, system maintenance).
                                  NOT for routine settings.
```
Rationale: a tool the builder dreads using won't be used. Editable panels with feedback
loops make settings fast, visible, and safe — so they actually get done, instead of
typing error-prone commands in a terminal.

---

## PART A — The unified entry point

"AI Advanced Settings" is a category the builder enters rarely, but is glad exists the
day a setting must change — rather than editing code or memorizing terminal commands.
It lists every technical lever and routes each to where it executes. The user cannot
change the model **roles** (the role list is owned by doc 30 §3); they change which
concrete model fills a role, the scoring thresholds, the API keys, and the vectorization
levers.

---

## PART B — Role mapping (editable)

This is the live incarnation of doc 30 §3. Doc 30 §3 **describes** the role → model →
version mapping; this panel makes it **editable** without touching code.

### B.1 The principle: store the identifier, not the call

A model call is two separate things: (1) HOW you call (the request recipe: URL, format,
auth) and (2) WHO you call (the model identifier, e.g. `opus-4.8`). For models of the
same provider, the "how" does not change — only the "who" does.

```text
The code does NOT hard-code "opus-4.8". It holds a variable, e.g. high_reasoning_model,
which reads its value from this panel's config.
  - Change a VERSION (same provider): change one string here → next call uses it.
  - Change a PROVIDER: change the provider menu → the code switches to that provider's
    recipe (which it already knows).
```

### B.2 The per-role edit box

Each role has a "Modify" button opening a small box with three lines:

```text
┌─ Modify model — [role name] ────────────────────────┐
│  Access  : [ provider ▾ ]   (OpenRouter / OpenAI /   │
│                              Anthropic / Google ...)  │
│  Model   : [ dropdown OR search box ]                 │
│            (dropdown for small catalogs; a search     │
│             box for huge catalogs like OpenRouter)    │
│  Effort  : [ levels pulled from the catalog ▾ ]       │
│            (adapts to the model; hidden if the model  │
│             does not support effort)                  │
│            [ Validate ]            [ ✕ Cancel ]        │
└───────────────────────────────────────────────────────┘
```

- **Access (provider):** a single dropdown of all providers at one level. Choosing a
  provider selects which call "recipe" the code uses.
- **Model:** a dropdown when the provider has few models (Anthropic, Google direct); a
  searchable box when the catalog is huge (OpenRouter has hundreds, often added to) — the
  UI adapts to catalog size.
- **Effort:** the reasoning-effort level (varies by provider/model: e.g. minimal / low /
  medium / high / xhigh on some OpenAI models). Pulled dynamically from the catalog, not
  hard-coded; hidden when unsupported.

### B.3 Update-catalog button

A "Update catalog" button refreshes the available models per provider. Where possible it
also pulls each model's supported **effort levels** alongside the names. Model names are
reliably exposed by provider catalogs; effort levels are NOT uniformly exposed — so:
try to pull effort with the catalog, and if a provider does not expose it cleanly, fall
back (hide the effort line, or offer a generic low/medium/high). Best-effort when present,
no breakage when absent.

### B.4 OpenRouter vs direct access (the hybrid)

OpenRouter is one façade for many providers: one recipe, one key, one catalog, models
added often — ideal for "swap a model in one click". But it adds an intermediary in the
data path and may route a given model to different backend hosts (less control over the
exact provider and retention terms).

Therefore the design is **hybrid, guided by the role's selection criterion (doc 30 §3):**

```text
- NON-sensitive roles (high reasoning, first cloud tier, web/fresh-data, fallbacks):
  → may go via OpenRouter. Maximum convenience, one-click model swap, fresh catalog.
- SENSITIVE roles (health specialist, finance specialist):
  → direct API key with a provider offering GDPR/EU guarantees, NOT via OpenRouter.
  → keeps exact control of provider and retention terms.
- Religious / very-high content: already LOCAL (doc 50), never leaves at all.
```
If a role's payloads are already minimized/anonymized upstream (per the privacy rule —
backend sends a minimized summary, no direct identifiers), the OpenRouter risk drops
sharply, and routing more roles through it becomes defensible. The selection criterion
on each role is the guide.

### B.5 "Dumb" interface (for now)

The panel lets the builder assign any model to any role without a blocking guard — the
builder is sole owner and knows what they are doing. A future improvement (non-blocking):
a soft warning on sensitive roles ("⚠ this role requires GDPR guarantees; this provider
offers none") that informs without preventing validation. Not a priority now.

---

## PART C — Scoring thresholds

The `/200` routing thresholds (which decide when a task escalates from the local model to
a cloud tier) are adjustable here. Example: if the local model proves insufficient at a
given band, the builder can lower the threshold; if cloud is called too readily, raise it
to stay local longer and save cost. This is a legitimate cost/quality arbitrage the
builder may want to pilot — unlike the purely-technical vectorization levers.

Edited in the app, **applied on the VPS** (the routing/scoring engine lives there). The
table is displayed and explained; the builder changes the thresholds, never the models
or roles. The scoring mechanism itself is owned by doc 30 §5; this panel only edits its
threshold values.

---

## PART D — The calibration console (vectorization, on the Tower)

This is the "Vectorization" entry of Part A. It opens a small local tool on the Tower.

### D.1 Key distinction: the model is NOT tuned — the surroundings are

The embedding model (Qwen3-Embedding 8B) and the conversational model (Qwen3-32B) are NOT
retrained or "tuned" internally (we deliberately do not fine-tune — we use MEMORY/RAG, not
training). The model weights never change. What IS adjustable are the parameters AROUND
the models: how text is chunked, how many pieces are retrieved, similarity thresholds,
quantization, and inference params.

### D.2 Retrieval levers (the biggest impact)

**Chunking (most impactful)** — how the audit text is split before vectorization.
```text
- Too LARGE: a vector averages too many notions → imprecise retrieval.
- Too SMALL: loses surrounding context → retrieves a fact without its cause.
- WELL-SIZED: each chunk = one coherent, complete idea (e.g. one full correlation).
Parameter: chunk size (tokens) + split strategy (by structure: per-domain fact,
per-severity point, each correlation as its own unit).
Starting point to TEST (not final): ~400 tokens, structure-aware. Revise by testing.
```

**Top-K (number of chunks retrieved)** — pgvector returns the K nearest chunks.
```text
- Too small (e.g. 2): may miss relevant info.
- Too large (e.g. 50): floods the 32B context, dilutes focus.
- Well-set (e.g. 5-10): complete but sharp.
NOTE: maps to the user-facing "fouille depth" idea — light fouille = small K, deep
fouille = large K. A "moment" top-K can be a PRODUCT setting in Imperium; the BASE
top-K default lives here.
```

**Similarity threshold** — minimum closeness for a chunk to be returned.
```text
- Low threshold: returns loosely-related chunks (noise risk).
- High threshold: only very relevant (may miss subtle links).
Parameter: min similarity (e.g. 0.75). Calibrate by observation.
```

### D.3 Embedding-model levers

**Model choice (replaceable):** if Qwen3-Embedding 8B gives weak retrievals, it can be
SWAPPED for another embedding model that runs on the hardware. Embedding models differ in
quality by language (French matters here) and domain. Test candidates with the same
inputs, keep the best.

**Quantization (Q8 / FP16 / Q4...):** trades precision vs speed/memory.
```text
- FP16: more precise, heavier, slower.
- Q8: good compromise (current choice).
- Q4: lighter/faster, slightly less precise.
Test whether Q8 suffices or FP16 is needed for better retrieval quality.
```

### D.4 Conversational-model (32B) levers (via call params, not prompt content)

```text
- Temperature: creativity vs determinism. Lower = more deterministic/consistent;
  higher = more varied. For analytical WR dialogue, lean lower.
- Other inference params (top-p, max tokens, etc.): tune for coherence.
These are TECHNICAL (builder) settings, calibrated once and frozen, like the rest.
```
(The prompt CONTENT itself — role layer, F01 meta-prompt, etc. — is specified elsewhere;
this section is only the inference parameters.)

### D.5 Levers are REVISABLE over time (important nuance)

Optimal values are NOT fixed forever. As the vector memory grows week after week, the
context changes and a value good at week 3 may need adjusting by week 80. Example: a
top-K of 8 may behave differently when the base holds 3 audits vs 80. HOWEVER, "revisable"
does NOT mean "in the product UI": these change RARELY (a few times a year, when the
volume crosses a threshold), via this console, as maintenance — not as a daily setting.
(Analogy: wheel alignment can need redoing over time, but you don't put an alignment knob
on the dashboard.)

### D.6 The calibration console (spec)

A small technical panel on the Tower. Editable fields show current values; the builder
types new numbers; a TEST button runs an immediate retrieval+answer loop.

```text
┌─ Calibration Console (Tower) ─────────────────┐
│ Chunk size (tokens):     [ 400 ]              │
│ Top-K (base):            [  8  ]              │
│ Similarity threshold:    [ 0.75 ]             │
│ Quantization:            [ Q8 ▾ ]             │
│ Temperature (32B):       [ 0.7 ]              │
│                                                │
│ Test subject: [ "mon sommeil semaine 3"   ]   │
│            [ RUN TEST ]                        │
│ ┌─ Result ──────────────────────────────────┐ │
│ │ Retrieved chunks: ... (so the builder sees │ │
│ │   whether retrieval is relevant)           │ │
│ │ Model answer: ... (small chatbot-like pane)│ │
│ └────────────────────────────────────────────┘ │
└────────────────────────────────────────────────┘
```

**TEST button behavior:**
```text
1. Builder picks a KNOWN subject (one they can judge).
2. The system runs a real vector retrieval on it (with the CURRENT field values).
3. It DISPLAYS the retrieved chunks → builder sees if retrieval is on-point.
4. It asks the local model a question using those chunks.
5. It shows the answer in a small chatbot-like pane.
→ Builder judges retrieval relevance + answer coherence, adjusts a field, re-tests.
```

**Dual role of the console:**
```text
- CALIBRATION: tune the levers with an immediate feedback loop (no blind tuning).
- DETECTION: when WR answers feel worse over time, run the TEST on known subjects to
  SEE if retrieval degraded → decide whether a re-calibration is needed → adjust →
  re-test → re-freeze for several months.
So: technical levers stay hard-set, and THIS console is both the tuner and the
"when to re-tune" instrument. This also answers the WR's missing measurement instrument
(alongside the validated-correlation rate + novelty count).
```

### D.7 Implementation note

The console is a small LOCAL tool (e.g. a simple local web page or a small script with a
minimal UI) on the Tower, opened from the Vectorization entry of AI Advanced Settings.
Build it when reaching the calibration phase (after the GPU arrives and real data exists).
It is worth the investment — it serves every calibration for the system's lifetime.

---

## Cross-references

- Doc 30 §3: owner of the role → model → version mapping. Part B makes it editable.
- Doc 30 §5: the scoring `/200` mechanism. Part C edits its thresholds.
- Doc 16: AI backend layer — the call layer reads the model identifier from config
  (Part B) instead of hard-coding it.
- F10: physical infrastructure (Tower vs VPS) — why vectorization runs on the Tower and
  scoring/routing on the VPS.
- Doc 50: religious/very-high content stays local (never routed to a cloud provider).
- Patch 38-A: embedding model + dedicated GPU.
- Patch 47-C/47-F: WR RAG + audit data window (what gets chunked/retrieved).
- WR measurement: validated-correlation rate + novelty, complemented by this console's
  detection role.
