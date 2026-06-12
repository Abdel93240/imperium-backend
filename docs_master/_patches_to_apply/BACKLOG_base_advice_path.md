## Backlog Entry — Path `base_advice` (pre-written religious advice)

Context: the morning "AI advice" card for The Path must NOT let the AI generate
or freely select religious content. Decision (doc 30, §7.6): Qwen 32B picks one
entry at random from a dedicated, closed list of pre-written, validated advice
and only reformulates/presents it.

To create (in the Path docs, e.g. doc 41 or a dedicated doc):
- A `base_advice` structure: a closed list of short, self-sufficient, validated
  religious advice entries (each entry is complete on its own, not an excerpt to
  be interpreted).
- Explicit statement that `base_advice` is DISTINCT from the Dars knowledge base
  (doc 50): the AI must never pull/interpret religious content from the Dars or
  any broad corpus.
- The Path advice flow: Qwen 32B random-picks one `base_advice` entry →
  reformulates/presents it. No generation, no selection-by-meaning, no cloud.
- Storage/endpoint for `base_advice` (backend), and how entries are added/curated
  by the user (human-validated only).

Status: to_create. Not urgent. Referenced by doc 30 §7.6.
