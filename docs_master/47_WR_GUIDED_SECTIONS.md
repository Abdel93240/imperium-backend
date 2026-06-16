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

## 6. Cost Analysis

```text
V1 WR (free-form):
├─ 1 Opus call: initial summary (with embedded questions)
├─ 1 Opus call: integrate user answers into final draft
├─ Optional: 1 Opus call for revision
└─ Total: ~$0.20/week

V2 WR (guided sections):
├─ 5 Opus calls: one per section (summary + questions)
├─ 5 Opus calls: one per section (integrate user answers)
├─ 1 Opus call: final synthesis from all sections
├─ Optional: 1 Opus call for revision
└─ Total: ~$1.20/week

DIFFERENCE: +$1/week = ~$52/year

Justification: the quality jump is significant. Users
explicitly identified V1 free-form as a weakness. Paying
$1/week for guaranteed multi-domain coverage is trivial.
```

The cost remains negligible at the project's scale.

---

## 7. Database Architecture (Option C)

The V1 design has a single `weekly_reports` table holding the canonical row plus a JSON blob.

V2 adds a generic sections table.

### 7.1 Existing table preserved

```sql
-- weekly_reports stays as defined in doc 32 §11.2
-- It still holds: report_markdown, report_json, summary, etc.
-- These now contain the FINAL synthesis after all sections.
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
                           -- Section-specific elements for pgvector
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

✅ GRANULAR PGVECTOR
   Each section's extracted_for_memory feeds pgvector independently.
   Future retrieval: "show me what the WR said about Vector"
   = filter by section_name = 'vector'.

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

PAST CONTEXT (from past 4 weeks):
[past_wr_section_data, decay-weighted]

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
  └─ pulse_pain_logs

PATH SECTION:
  ├─ prayer_logs
  ├─ fasting_logs
  ├─ sadaqa_records
  ├─ adhkar_completions
  └─ quran_progression

IMPERIUM MISSIONS SECTION:
  ├─ imperium_missions (filtered by week)
  ├─ imperium_replan_events
  ├─ imperium_discipline_scores
  └─ imperium_morning_checkins
```

The section service (per Section 13) handles the data assembly per section.

---

## 12. Vectorization By Section

V1 vectorizes the entire WR's `extracted_for_memory` as one batch (per doc 38 §6.1).

V2 vectorizes EACH SECTION's `extracted_for_memory_json` separately:

```text
For each section in weekly_report_sections (status='completed'):
  for element in section.extracted_for_memory_json:
    INSERT INTO pgvector_memory:
      content: element.text
      embedding: vector
      source: 'weekly_report'
      source_ref_type: 'weekly_report_section'
      source_ref_id: section.id
      element_type: 'insight' | 'decision' | etc.
      metadata: 
        section_name: <section>
        wr_id: <weekly_report_id>
        week_start: <week>
      weight: 1.0 (decays per doc 38 §8)
```

This enables fine-grained retrieval:
```text
"What did past WRs say about my Vault patterns?"
→ search pgvector_memory WHERE 
    metadata->>'section_name' = 'vault'
    AND status = 'active'
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
section.status = 'failed'
The flow allows user to:
  - Retry that section
  - Skip it (proceeds to next; final synthesis notes the gap)
  - Cancel WR session entirely (status = cancelled)
```

### 16.2 User abandons mid-WR

```text
Session stays in_progress.
On next user open: "Tu avais commencé ton WR. Reprendre où 
tu en étais ?" [Reprendre] [Recommencer] [Abandonner]

If next Tuesday 20:00 arrives: status = expired (per doc 32 §5.2).
```

### 16.3 Slow AI on a section

```text
Per doc 32 §12 timeouts apply per section.
If a section AI call exceeds 60s: retry once, then mark section
as failed (Section 16.1 path).
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
  - Verify pgvector entries created correctly per section
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
- `38_VECTORIZATION_PIPELINE.md` — pgvector ingestion
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
