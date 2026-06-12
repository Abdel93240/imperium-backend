## Patch 30-A — Financial Expert (GPT-5.5)

Patch 30-A designates the financial reasoning expert and clarifies where it
lives. It extends §3.8 and adds a static rule in §7. No other section changes.

Rationale (June 2026 review): when the model hierarchy was rewritten, finance was
left as "Vault → routing by requirement, no dedicated expert." A web review of
2026 financial-reasoning benchmarks showed the field is led by the GPT-5 and
Claude Opus families, with the decisive criterion for finance being
**hallucination resistance** (a model that confidently invents a figure is worse
than useless), not raw benchmark score. Since GPT-5.5 is already the ecosystem's
domain specialist (health, fresh data), it is the natural owner of financial
reasoning too — no new model is introduced.

Key architectural point: the financial expert lives in the **Imperium brain**,
not in the Vault app. Vault is a display/capture interface; it does not "own" the
expert. Financial reasoning is invoked by the brain's dialogue contexts — the
Imperium chatbot and the Weekly Review — when an analysis is required. Opening
Vault to read a balance does not call the expert; reasoning about finances does.
This mirrors the existing pattern (GPT-5.5 owns Pulse reasoning, but reasoning
runs from the brain, not from the app).

---

### §3.8 replacement — GPT-5.5 domain specialist (health + finance + fresh data)

Replace the §3.8 block with:

> ### 3.8 GPT-5.5 — domain specialist (health + finance + fresh data)
>
> Role: specialist for health/Pulse, **financial reasoning (Vault domain)**, and
> for fresh data / web research / verification / complex multimodal analysis.
>
> Use for:
> - health: weight/nutrition/recovery calculations and medical-feed analysis
>   (Pulse). GPT-5.5 is the de facto "owner" of Pulse reasoning.
> - **finance: analysis and advice over Vault data (budgets, cash-flow, financial
>   pressure, project cost reasoning). GPT-5.5 is the de facto "owner" of
>   financial reasoning. This reasoning lives in the Imperium brain and is invoked
>   by the chatbot and the Weekly Review — NOT by the Vault app, which only
>   displays/captures. In finance, GPT-5.5 must show its reasoning and flag
>   uncertainty rather than invent a figure (hallucination resistance is the
>   governing criterion); a confidently invented number is worse than useless.**
> - fresh data: recent events around Paris (Vector — concerts, salons, sports),
>   web retrieval, market comparison, regulatory research.
> - generating actionable rules from sensitive or complex documents.

---

### §7 new static rule — Finance

Insert a new rule after §7.4 (Health / Pulse), renumbering the subsequent rules
(old 7.5→7.6, 7.6→7.7, 7.7→7.8) so the list stays sequential:

> ### 7.5 Finance / Vault reasoning
> ```text
> Financial analysis or advice (not mere display) → GPT-5.5
> ```
> Triggered when the brain reasons over financial data — typically inside the
> Imperium chatbot or the Weekly Review (budget/cash-flow analysis, financial
> pressure, project cost evaluation). NOT triggered by Vault simply displaying a
> balance or by deterministic backend computation (those stay app/backend). The
> distinction is **display vs reasoning**: showing a number is not analysing it.
> Qwen must not produce a critical financial analysis alone. GPT-5.5 must surface
> its reasoning and signal uncertainty rather than fabricate values.

(Existing 7.5 Vector ride scoring → 7.6; 7.6 WR re-planning → 7.7; 7.7
deterministic backend → 7.8.)

---

### §7 new static rule — Morning "AI advice" cards (per app)

Every app's dashboard has an "AI advice" module that generates a personalized
morning tip. Routing is per app (by the depth the advice needs), and the
religious case is a hard exception. Insert as §7.6 (renumbering the rest):

> ### 7.6 Morning "AI advice" cards
> The advice module present on each app dashboard is routed by app, by required
> depth — not as a special case but via normal domain routing:
> ```text
> Imperium → fine advice  → brain (Opus 4.8 / scoring by depth)
> Pulse    → fine advice  → GPT-5.5 (health, §7.4)
> Vault    → fine advice  → GPT-5.5 (finance, §7.5)
> Vector   → plain advice → Qwen 32B local (no finesse needed)
> Path     → reformulation only → Qwen 32B local
> ```
> **Path religious advice — hard rule.** For the religious advice, the AI does
> NOT generate and does NOT freely select content. Qwen 32B picks one entry at
> random from a DEDICATED, closed list of pre-written, validated advice
> (`base_advice`, to be created in the Path docs) and only reformulates/presents
> it. This base is DISTINCT from the Dars knowledge base (doc 50): the AI must
> never extract or interpret religious content from the Dars (or any broad
> corpus) at will. On religion, the AI presents pre-validated content; it never
> invents or cherry-picks. (`base_advice` does not exist yet — see backlog.)

(This pushes the previously-renumbered rules down by one again: Vector ride
scoring → 7.7, WR re-planning → 7.8, deterministic backend → 7.9. Apply the
final numbering consistently when editing in place.)

---

### Note on project cost (resolves an open question)

Because the financial expert lives in the brain (not in Vault), the question
"does a project's money live in Vault or stay in Imperium?" no longer affects
*which model reasons about it*: the brain convenes GPT-5.5 either way. That
question remains a **storage/display** decision (where the data is kept and
shown), to be settled in the Vault doc (42) and/or the project docs (F06/52),
but it does not change routing. Wherever the project-cost data is stored, the
brain reads it (display filters never limit brain knowledge — see doc 41-A /
doc 32 6P) and GPT-5.5 reasons over it on demand.
