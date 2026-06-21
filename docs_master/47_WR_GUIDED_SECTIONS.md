# 47 - WR Guided Sections (V2)

> ⚠️ **V2 feature — to be implemented after V1 is stable.**
> This document captures the design of the guided multi-section
> Weekly Report. It extends the WR defined in doc 32 (V1).

---

## 1. Purpose

The current Weekly Report (doc 32, V1) lets the AI roam relatively free in its analysis. While functional, it leaves room for the AI to skip important domains or to over-emphasize others depending on its mood.

This V2 evolution introduces **mandatory guided sections**: the AI MUST address every life domain in a fixed order, asking questions specific to each, before producing the final synthesis.

The goal: never let the AI silently skip a domain, ever.

---

## 2. Why This Is V2 And Not V1

```text
V1 — Free-form AI summary, occasional questions, single draft.
     Functional. Used for 4-6 weeks.

V2 — User has now seen what the V1 WR misses, what it skips,
     what it fluffs over. The structured guided flow lands at 
     the right time, with real-world feedback.

V3 — Possible future refinements based on V2 usage data.
```

Implementing this in V1 would lock the structure before the user knows what they actually need from each section.

---

## 3. The Five Mandatory Sections (in order)

```text
1. VECTOR (VTC)
   The most concrete, factual domain.
   Sets the conversation tone.

2. VAULT (Finances)
   Naturally follows VTC (revenue, fuel, profit).

3. PULSE (Health)
   Physical body after work.

4. PATH (Religion)
   Spiritual elevation after the material.

5. IMPERIUM MISSIONS (Global execution)
   The summary of what was actually done.
   Sets up the final "anything to add?" question.
```

This order moves from **work → money → body → soul → execution discipline**. It is fixed, not user-configurable.

---

## 4. The Conversational Flow

The WR popup becomes a guided conversation in 5 phases + 1 synthesis.

```text
PHASE 1 — VECTOR (VTC)
  AI: presents Vector summary of the week.
      key facts: total revenue, sessions, hourly rate, etc.
  
  AI: asks 1-3 Vector-specific questions.
      e.g. "Mardi soir tu as roulé moins. C'était volontaire 
       ou tu n'as pas trouvé de courses ?"
  
  USER: answers freely.
  
  AI: stores section, says: "Passons à la finance ?"
      [Continuer]

PHASE 2 — VAULT (Finances)
  AI: presents Vault summary.
      key facts: business profit, expenses, pressure, sadaqa basis.
  
  AI: asks 1-3 Vault-specific questions.
      e.g. "Tu as augmenté les dépenses 'Outils VTC' cette 
       semaine. Investissement ponctuel ou tendance ?"
  
  USER: answers.
  
  AI: stores section, says: "Passons à la santé ?"
      [Continuer]

PHASE 3 — PULSE (Health)
  AI: presents Pulse summary.
      key facts: workouts, meals, energy patterns, recovery.
  
  AI: asks 1-3 Pulse-specific questions.
      e.g. "Tu as raté 2 entraînements cette semaine. 
       Fatigue ? Manque de temps ? Autre ?"
  
  USER: answers.
  
  AI: stores section, says: "Passons à la spiritualité ?"
      [Continuer]

PHASE 4 — PATH (Religion)
  AI: presents Path summary.
      key facts: prayers completed, sadaqa progress, fasting,
                  adhkar discipline.
  
  AI: asks 1-3 Path-specific questions.
      e.g. "Tu as raté Asr 2 fois mardi et jeudi. C'est lié 
       aux longues sessions VTC ?"
  
  USER: answers.
  
  AI: stores section, says: "Passons à l'exécution ?"
      [Continuer]

PHASE 5 — IMPERIUM MISSIONS (Global execution)
  AI: presents the missions bilan.
      key facts: total missions, completed, failed, expired,
                  discipline score, replan history.
  
  AI: asks 1-3 execution-specific questions.
      e.g. "Tu as eu 3 replans cette semaine, surtout liés 
       à fatigue. C'est cohérent avec ton sentiment réel ?"
  
  USER: answers.
  
  AI: closes with the mandatory open question:
      "As-tu autre chose à rajouter concernant cette semaine,
       quelque chose qu'on n'a pas couvert ?"
  
  USER: answers (or "non").

PHASE 6 — FINAL SYNTHESIS
  AI: consolidates all 5 sections + final additions.
      Generates the full draft report.
      User validates or asks for revisions.
      (Standard V1 flow from doc 32 §6 step 9-10)
```

---

## 5. WR Context Architecture (Rich WR Log + Learning RAG)

Cross-domain correlations require a global view, but the WR dialogue must not fill
Qwen's context window with a large weekly summary. The WR therefore uses an
audit-first architecture: Opus produces a dense INPUT audit, the audit is indexed
in an ephemeral WR working vector store, Qwen retrieves only the relevant chunks
it needs while guiding the user, then Opus produces a final validated OUTPUT
audit.

Qwen3-32B native context is approximately 32,768 tokens. YaRN can extend the
window, but it degrades short-context behavior and is not reliable as the default
WR design. A talkative WR can grow quickly once the global summary, five guided
sections, user answers, and self-scoring are all in play. Holding everything in
context is the wrong design.

The architecture preserves the WR's purpose: cross-domain correlations such as
Pulse low sleep + Imperium missions marked as "flemme" should surface as possible
fatigue, not be missed because each section is isolated.

The complete WR is preserved as a rich, self-contained Markdown log in text form.
This rich log contains:
- the INPUT audit: analysis of the week's data only, plus pointers to source
  tables/rows; it must not copy raw weekly data into the log;
- the complete user <-> AI conversation across all guided sections;
- the OUTPUT audit: validated synthesis plus extracted learning elements.

The rich WR log is never vectorized. Only learning elements extracted from the
validated WR are embedded into `ai_memories`, and every memory row points back to
the rich log through `source_table` / `source_id`.

This creates two separate vectorization paths that must not be confused:
- ephemeral working vectorization for the INPUT audit during one WR session;
- permanent learning-memory vectorization for validated learning elements only.

### 5.1 Input audit by Opus 4.8 at max effort

```text
Once per week, Opus 4.8 is run at MAXIMUM reasoning effort. This is the rare,
high-stakes call that produces a structured weekly INPUT AUDIT:
  - key facts per domain (Vector, Vault, Pulse, Path, Imperium)
  - severity tiers: critical / high / medium / low points
  - maximum cross-domain correlations, pre-identified explicitly
    e.g. "low sleep (5h avg) ↔ 3 missions skipped 'flemme' → fatigue suspected?"
         "long VTC sessions Tue/Thu ↔ Asr missed those days"

Fable 5 was the originally intended top-tier model for this role but is currently
suspended (US export-control directive). Opus 4.8 at max effort is the relay until
that changes.
```

### 5.2 Preserve the audit inside the rich WR log

```text
The INPUT audit is stored as text inside the rich WR log. It contains analysis and
source pointers, not copied raw data.

The audit is structured along its natural sections:
  - per-domain facts
  - per-severity points
  - each cross-domain correlation as its own explicit point

During the current WR session, the INPUT audit is chunked and embedded into an
ephemeral WR working vector store. Qwen queries this temporary store through RAG
and receives only the relevant chunks for the current section or question.

This working vector store is distinct from `ai_memories`. It is not permanent
memory, it never becomes a source of historical retrieval, and it is discarded at
the end of the WR session.
```

### 5.3 Qwen drives the dialogue with scoped context

```text
Qwen 32B conducts the 5-phase guided conversation. It does NOT load the whole
audit into context. Per section / per need, it queries the ephemeral WR working
vector store for relevant INPUT audit chunks and may retrieve historical learning
elements from ai_memories.

Result: Qwen's context window stays largely free:
  - room for the user dialogue
  - room for self-scoring ("can I answer this, or escalate?")
  - room to call cloud specialists when a point exceeds its competence

Historical retrieval from ai_memories uses doc 38 retrieval mode A by default:
final_score = cosine_similarity × confidence. Mode B uses cosine_similarity only
when the workflow explicitly needs past low-confidence witnesses.

Because Opus pre-computed the current-week correlations and they are retrievable
from the ephemeral WR working vector store, Qwen surfaces them in the right
section without recomputing or holding everything in memory.
```

### 5.4 Correlations emerging during the dialogue

```text
If a new user answer reveals a correlation the audit could not foresee, Qwen has
the free context to notice it live and escalates to a specialist cloud model if it
exceeds local competence.
```

### 5.5 Final synthesis and output audit

```text
The final synthesis (Phase 6) consolidates the validated sections. Opus 4.8 then
reruns the audit at maximum effort using the user's corrections from the dialogue.

This OUTPUT AUDIT is the final, user-validated weekly learning artifact. It is
stored in the rich WR Markdown log together with the INPUT audit and complete
conversation. Only its extracted learning elements are vectorized into
`ai_memories`; the log itself remains text and becomes the source referenced by
Imperium planning, arbitration, advice, missions, and future WRs.
```

---

## 6. Cost Analysis (RAG architecture, two Opus audits)

The WR no longer runs many per-section Opus calls. Cost shape:

```text
├─ 1 Opus audit (max effort) — INPUT          — heavy call #1
├─ Qwen dialogue with scoped context (local)   — free in itself
│    └─ specialist escalations (variable):
│         finance/health → GPT-5.5 ; other → Opus ; religion → NO AI (DB lookup)
├─ INPUT audit working-store vectorization     — free (local embedding GPU)
├─ 1 Opus audit (max effort) — OUTPUT          — heavy call #2 (not optional)
└─ (final user validation of the report)
```

The OUTPUT audit is not just a source for daily AI advice. It is the central
learning artifact of the Imperium brain:
- it teaches the AI from user-validated reality, not hypotheses;
- week after week, it makes the system progressively more intelligent;
- it feeds planning, arbitration, advice, missions, WRs, and daily guidance.

This is why both Opus max-effort audits are justified: they invest in Imperium's
cognitive core, not comfort spending.

Estimated cost per WR (Opus 4.8 at $5/M input, $25/M output; output dominates):

```text
Opus INPUT audit (max effort):
  ~15,000 in × $5/M   = $0.075
  ~ 8,000 out × $25/M = $0.200   → ~$0.275

Qwen scoped dialogue (local)     → $0.000

Specialist escalations (~3 avg, small calls ~3,000 in / ~1,500 out each):
  ~3 × ~$0.05                    → ~$0.15
  (finance/health → GPT-5.5 ; other → Opus ; religion → no AI)

Opus OUTPUT audit (max effort, incorporates user corrections):
  ~25,000 in × $5/M   = $0.125
  ~10,000 out × $25/M = $0.250   → ~$0.375

INPUT audit working-store vectorization → $0.000
──────────────────────────────────────────────
TOTAL ≈ $0.80 per WR  →  ~$40-45 / year (×52 weeks)
```

Net: dominated by the two weekly Opus max-effort audits (input + output), plus a
small number of specialist escalations. The old per-section Opus model is gone.
The heavy spend is concentrated where it builds Imperium's core memory: the rich
WR log and its validated learning elements, which are the system's main assets.

These are estimates based on plausible token sizes. The real cost will be
calibrated in use via the AI cost-logging layer (doc 43 §17). Order of magnitude:
tens of dollars per year, not hundreds.

---

## 7. Database Architecture (Option C)

The V1 design has a single `weekly_reports` table holding the canonical row plus a JSON blob.

V2 adds a generic sections table.

### 7.1 Existing table preserved

```sql
-- weekly_reports stays as defined in doc 32 §11.2
-- It still holds: report_markdown, report_json, summary, etc.
-- report_markdown now contains the rich WR log:
--   1. INPUT audit analysis + source table/row pointers
--   2. complete user <-> AI conversation
--   3. OUTPUT audit with validated synthesis + learning elements
```

### 7.2 New table: weekly_report_sections

```sql
CREATE TABLE weekly_report_sections (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  weekly_report_id         UUID NOT NULL REFERENCES weekly_reports(id) 
                                                  ON DELETE CASCADE,
  section_name             VARCHAR(64) NOT NULL,
                           -- 'vector' | 'vault' | 'pulse' | 'path' 
                           -- | 'imperium_missions'
  section_order            INTEGER NOT NULL,
                           -- 1 to 5 (matches the fixed order)
  
  -- Section content
  narrative_markdown       TEXT NOT NULL,
                           -- AI's narrative summary of this section
  ai_questions_json        JSONB NOT NULL,
                           -- Questions the AI asked
                           -- [{question, why_it_matters, data_anchor}]
  user_answers_json        JSONB NULL,
                           -- User's answers to those questions
                           -- [{question_id, answer_text, answered_at}]
  ai_insights_json         JSONB NULL,
                           -- AI's insights derived from user answers
  extracted_for_memory_json JSONB NULL,
                           -- Section-specific learning elements for ai_memories
                           -- {insights:[], decisions:[], patterns:[], 
                           --  wins:[], blockers:[]}
  
  -- Metrics (cost tracking)
  tokens_input             INTEGER NULL,
  tokens_output            INTEGER NULL,
  cost_eur                 NUMERIC(6,4) NULL,
  
  -- Lifecycle
  status                   VARCHAR(32) NOT NULL DEFAULT 'pending',
                           -- 'pending' | 'awaiting_user' 
                           -- | 'completed'
  started_at               TIMESTAMPTZ NULL,
  completed_at             TIMESTAMPTZ NULL,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  CONSTRAINT weekly_report_sections_section_check
    CHECK (section_name IN ('vector', 'vault', 'pulse', 'path',
                             'imperium_missions')),
  CONSTRAINT weekly_report_sections_order_check
    CHECK (section_order BETWEEN 1 AND 5),
  CONSTRAINT weekly_report_sections_status_check
    CHECK (status IN ('pending', 'awaiting_user', 'completed'))
);

-- One section per (WR, section_name)
CREATE UNIQUE INDEX weekly_report_sections_unique_idx
ON weekly_report_sections (weekly_report_id, section_name);

-- Quick lookup of pending sections for a user
CREATE INDEX weekly_report_sections_user_status_idx
ON weekly_report_sections (user_id, status);
```

### 7.3 Why Option C wins

```text
✅ EVOLUTIVE
   Adding a new section in V3+ = adding 1 row, no schema change.

✅ GRANULAR LEARNING MEMORY
   Each section's extracted_for_memory feeds ai_memories independently.
   Future retrieval: "show me what the WR said about Vector"
   = retrieve learning elements with metadata section_name = 'vector',
     all pointing back to the rich WR log.

✅ COST TRACKABLE
   Per-section cost helps optimize prompts later.

✅ INDEPENDENT FAILURE
   If one section fails generation, others keep working.

✅ SIMPLE QUERIES
   weekly_report_sections WHERE weekly_report_id = X
   ORDER BY section_order
   = the full WR in order.

✅ ONE TABLE, NOT FIVE
   Avoids the explosion of 5 specialized tables.
```

---

## 8. AI Task Types

V2 uses the existing `ai_tasks` infrastructure (doc 31). New task types:

```text
weekly_report.section.summary       - generate one section's summary
weekly_report.section.questions     - generate questions for a section
weekly_report.section.integrate     - integrate user answers
weekly_report.final_synthesis       - aggregate all 5 sections
```

Each task references:
```text
- weekly_report_id (parent)
- section_name (which section)
- section_order (for ordering)
```

---

## 9. The WR Session Lifecycle Updated

V1 lifecycle (per doc 32 §5):
```text
passive → available → in_progress → waiting_for_ai 
       → waiting_for_user → draft_ready → validated
```

V2 enriches in_progress and waiting_for_user states with sub-states tracking the current section:

```text
weekly_review_states.status remains the same (high-level).

The new weekly_report_sections.status tracks per-section progress:
  pending      - section not started yet
  awaiting_user - AI generated narrative + questions, waiting for answer
  completed    - user answered, section locked

The UI consults section status to show the user where they are
in the conversation.
```

---

## 10. Section Generation Prompts

Each section uses a specialized Opus prompt (defined in doc 36).

### 10.1 Section prompt template (generic)

```text
You are generating section [SECTION_NAME] of the user's Weekly Report.

USER PROFILE: [anonymized summary]
WEEK: [week_start] to [week_end]

DATA FOR THIS SECTION:
[deterministic_data_for_section]

PAST CONTEXT (from ai_memories, Mode A unless explicitly overridden):
[relevant learning elements scored by cosine_similarity × confidence]

YOUR TASK:
1. Produce a narrative summary of the week for THIS DOMAIN ONLY.
2. Identify what's notable, what's missing, what's surprising.
3. Generate 1-3 specific clarification questions that:
   - relate directly to data points in this section
   - are NOT generic ("how was your week?")
   - invite reflection, not just confirmation

Tone: direct, no flattery (per doc 32 §8 anti-flattery rules).
Language: French for user-facing text.

OUTPUT FORMAT (strict JSON):
{
  "result_type": "weekly_report.section.[SECTION_NAME]",
  "summary": "<one-sentence section summary>",
  "structured_result": {
    "section_name": "[SECTION_NAME]",
    "narrative_markdown": "<the user-visible narrative>",
    "key_facts": [...],
    "clarification_questions": [
      {
        "id": "q1",
        "question": "<specific question in French>",
        "why_it_matters": "<one sentence>",
        "data_anchor": "<which field this references>"
      }
    ]
  }
}
```

Each section has its own specialized version of this prompt with domain-specific data and question patterns. Full prompt templates live in doc 36.

---

## 11. Section-Specific Data Sources

Each section pulls data from the appropriate domain:

```text
VECTOR SECTION:
  ├─ vector_sessions
  ├─ vector_rides
  ├─ vector_fuel_events
  ├─ vector_session_fuel_consumption (if V2 fuel feature deployed)
  ├─ vector_qwen_recommendations (if WRS-related)
  └─ events_calendar

VAULT SECTION:
  ├─ vault_transactions
  ├─ vault_pressure_snapshots
  ├─ weekly_finance_summaries
  └─ upcoming_expenses

PULSE SECTION:
  ├─ meals
  ├─ workouts
  ├─ pulse_medical_rules (active)
  ├─ body_snapshots
  ├─ hydration_logs
  ├─ pulse_pain_logs
  ├─ food_stock
  └─ pulse.diet_weekly_program (recipes + shopping list + cook mission)

PATH SECTION:
  ├─ prayer_logs
  ├─ fasting_logs
  ├─ sadaqa_records
  ├─ adhkar_completions
  └─ quran_progression

IMPERIUM SECTION (execution + projects):
  ├─ imperium_missions (filtered by week)
  ├─ imperium_replan_events
  ├─ imperium_discipline_scores
  ├─ imperium_morning_checkins
  ├─ projects
  ├─ routines
  └─ routine_daily_checks
```

The section service (per Section 13) handles the data assembly per section.

---

## 12. Learning Element Vectorization By Section

V1 vectorizes learning elements from the WR's `extracted_for_memory` as one batch
(per doc 38 §6.1).

V2 extracts learning elements from EACH SECTION's `extracted_for_memory_json`
separately, then writes only those elements to `ai_memories`:

```text
For each section in weekly_report_sections (status='completed'):
  for element in section.extracted_for_memory_json:
    INSERT INTO ai_memories:
      content: element.text
      embedding: vector
      source_table: 'weekly_reports'
      source_id: weekly_report.id
      learning_element_type: element.learning_element_type
      confidence: element.confidence
      privacy_level: element.privacy_level
      is_active: true
      metadata: 
        section_name: <section>
        section_id: <weekly_report_section_id>
        wr_id: <weekly_report_id>
        week_start: <week>
```

`learning_element_type` is an open descriptive label. V1 examples are:
`insight`, `decision`, `pattern`, `win`, `blocker`.

Anti-double-recording rule:
```text
The rich WR log itself is never embedded.
Only extracted learning elements are embedded.
Every embedded learning element points back to the rich WR log through
source_table='weekly_reports' and source_id=<weekly_report_id>.
```

This enables fine-grained retrieval:
```text
"What did past WRs say about my Vault patterns?"
→ search ai_memories WHERE 
    is_active = true
    metadata->>'section_name' = 'vault'
  ORDER BY cosine_similarity(embedding, query_embedding) × confidence DESC
```

---

## 13. Backend Service Changes

```text
backend/app/services/imperium/wr_session.py:
  Add:
    - start_next_section(session_id) -> initiates section N+1
    - submit_section_answer(session_id, section_name, answers)
    - generate_final_synthesis(session_id) -> when all 5 done

backend/app/services/imperium/wr_section_data.py (NEW):
  Per-section data assembly:
    - get_vector_data_for_week(user, week_start)
    - get_vault_data_for_week(user, week_start)
    - get_pulse_data_for_week(user, week_start)
    - get_path_data_for_week(user, week_start)
    - get_imperium_missions_data_for_week(user, week_start)
```

---

## 14. API Surface (V2)

V1 endpoints from doc 32 §14 are preserved.

New endpoints for guided mode:

```text
POST /api/v1/imperium/wr/sessions/{id}/sections/{name}/answer
  Submit user answers for the current section.
  Triggers AI integration + advance to next section.

GET /api/v1/imperium/wr/sessions/{id}/sections
  List all sections of a session with their status.
  Used by UI to show progress (e.g. "3 of 5 done").

```

The `/validate` endpoint (doc 32 §14.2) still applies at the very end.

---

## 15. UI Surface (V2)

```text
WR popup with progress indicator at top:
  ⚪⚪⚪⚪⚪  (all pending, before start)
  🟢🟡⚪⚪⚪  (1 done, currently in section 2)
  🟢🟢🟢🟢🟡  (4 done, currently in section 5)
  🟢🟢🟢🟢🟢  (all done, ready for synthesis)

Each section shows:
  Header: "1/5 — VECTOR (VTC)"
  
  AI narrative card
  
  AI questions (collapsible if more than 1)
  
  User answer text area
  
  [Continuer]  (advances to next section)
  
Final synthesis shows:
  Full report draft (V1 layout from doc 32 §13)
  
  [Valider et enregistrer le rapport]
  [Modifier ce point...]  (free conversation revision)
```

---

## 16. Failure Modes

### 16.1 AI fails on one section

```text
On an AI error on a section, the AI RETRIES the section.
If the error repeats more than 3 times:
  - an error message is shown
  - the user is taken out of the WR
  - the WR banner on the dashboard stays UNCHANGED
    → the user can relaunch the WR later; if it still fails, it can be repaired
      via the orchestrator.

NO "skip section" option: skipping a section means missing what the AI had to
surface on that domain — contrary to the WR's purpose (the AI always covers all
domains). The only outcomes are retry, or a clean exit that preserves the banner
for a later relaunch.
```

### 16.2 User abandons mid-WR

```text
PASSIVE abandon = the user did not decide to stop; they simply left (e.g. exited
Imperium for several hours mid-WR).
  - The WR state goes to PAUSE; the WR window disappears.
  - On reopening Imperium: the WR banner has NOT disappeared — it is replaced by
    "WR a été coupé. Veux-tu reprendre ?" with three buttons:
    [Reprendre] [Recommencer] [Abandonner].
  - Reprendre = resume where they left off; Recommencer = restart from scratch;
    Abandonner = drop (banner returns to initial state).

If next Tuesday 20:00 arrives before resumption: status = expired (per doc 32
§5.2).
```

### 16.3 Slow AI on a section

```text
Per doc 32 §12 timeouts apply per section.
If a section AI call exceeds 60s: retry once, then mark section
as failed (Section 16.1 path).
```

### 16.4 User explicitly closes the WR (the X)

```text
EXPLICIT close = the user clicks the X (top-right) to close the WR window — a
deliberate decision to stop.
  - A confirmation popup appears: "Es-tu sûr ? Tu vas perdre toute ton avancée du
    WR."
  - If the user confirms (Oui): the WR banner returns to its INITIAL state, as if
    the WR had never been started (progress discarded).
  - If the user cancels the popup: they stay in the WR where they were.

Distinction from §16.2: a passive abandon (the user just left) offers Reprendre;
an explicit close (the user decided to stop) confirms and resets — no resume.
```

---

## 17. Testing Considerations

```text
For each section, generate test fixtures with:
  - Realistic deterministic data
  - Expected narrative quality
  - Reasonable question quality
  - User answer integration

End-to-end test:
  - Start session → 5 sections → final synthesis → validate
  - Verify ai_memories entries created correctly per section
  - Verify cost tracking per section
```

---

## 18. Non-Goals For V2

```text
❌ User-configurable section order
   (Fixed order: VTC → Vault → Pulse → Path → Imperium)

❌ User-configurable number of questions per section
   (AI decides 1-3 based on data complexity)

❌ Skipping individual sections at user request
   (the AI always goes through all 5 sections)

❌ Cross-section AI questioning during a section
   (Each section is self-contained; cross-references appear
    only in the final synthesis)

❌ Real-time co-editing of the WR
   (One user, one session at a time)
```

---

## 19. V3 Future Considerations

```text
- Section-level pattern detection (cross-week)
- Automatic question selection based on past WR engagement
- Dynamic section order based on what changed most this week
- Section-specific quality gates with stricter rules
- A/B testing of question phrasings to improve responses
```

These are not in V2 scope.

---

## 20. Implementation Order (V2)

```text
Phase 1 — Schema migration
  ├─ weekly_report_sections table
  └─ Adjust ai_tasks to support new task types

Phase 2 — Backend services
  ├─ wr_session.py: lifecycle for guided mode
  ├─ wr_section_data.py: per-section data assembly
  └─ wr_synthesis.py: final aggregation

Phase 3 — Per-section prompt templates
  └─ Add to doc 36 (PROMPTS_CLOUD_AI)
     - opus_wr_section_vector.txt
     - opus_wr_section_vault.txt
     - opus_wr_section_pulse.txt
     - opus_wr_section_path.txt
     - opus_wr_section_imperium.txt
     - opus_wr_synthesis.txt

Phase 4 — API endpoints
  └─ POST/GET endpoints from Section 14

Phase 5 — n8n workflow updates
  └─ Branch existing WR workflow for guided mode

Phase 6 — Vectorization changes
  └─ wr_vectorize.py: per-section vectorization

Phase 7 — UI in Android app
  ├─ Progress indicator
  ├─ Section header + cards
  └─ Final synthesis view

Phase 8 — Migration of past WRs (optional)
  └─ V1 WRs stay as-is. V2 starts fresh from deployment date.
```

---

## 21. References

- `32_WR_INTERACTIVE_WORKFLOW.md` — V1 WR foundation (preserved)
- `36_PROMPTS_CLOUD_AI.md` — section-specific prompt templates
- `38_VECTORIZATION_PIPELINE.md` — ai_memories ingestion
- `39_WRS_VECTOR_LEARNING_LOOP.md` — Vector-specific learning loop
- `33_VECTOR_LOGIC_DETAIL.md` — Vector data
- `40_PULSE_LOGIC_DETAIL.md` — Pulse data
- `41_PATH_LOGIC_DETAIL.md` — Path data
- `42_VAULT_LOGIC_DETAIL.md` — Vault data
- `43_IMPERIUM_LOGIC_DETAIL.md` — Imperium missions data

---

**Document version:** 1.0
**Status:** V2 design specification (DO NOT IMPLEMENT before V1 stable)
**Last updated:** 2026-04-29
