# 50 - Path Dars Knowledge Base (V3)

> ⚠️ **V3 feature — sérieuse, post-V1 and V2.**
> Personal religious sciences knowledge base with strict 
> source verification.

---

## 1. Purpose

Build a **personal deterministic source search and Q&A system** for the user's religious sciences notes (cours, support du professeur, notes de camarades).

The system:
- Ingests all formats of source material (manuscript photos, PDFs, audio, Word, etc.)
- Produces clean, beautifully formatted PDFs for the user
- Classifies every dars in a category tree and searches the markdown deterministically
- Answers the user's questions using ONLY the corpus
- Cites every claim with a clickable source reference
- Refuses to answer if the question is outside the corpus
- Tracks conflicts and lets the user resolve them with their professor's help

This is the most rigorous AI feature in the whole ecosystem. Religious sciences require zero tolerance for hallucination.

---

## 2. Why V3 And Not Earlier

```text
This feature requires:
- Stable AI layer (V1)
- Stable local OCR / structuring / full-text search pipeline
- User has accumulated content to classify and search
- User trusts the system enough for sensitive content

V3 is the right time. By then, everything else is stable.
```

---

## 3. Design Philosophy

```text
RIGOR FIRST. SPEED SECOND. FANCINESS LAST.

This system serves religious learning. The cost of a wrong 
answer is high (a wrong fatwa quoted, a misunderstood ruling, 
a fabricated dalil).

We accept:
- Slower indexing
- Stricter refusal to answer
- Less polished UI
- More user friction in validation

In exchange for:
- Zero hallucination tolerance
- Verifiable citations on every claim
- Complete user control over the corpus
- The professor remains the ultimate authority
```

---

## 4. The Three Major Capabilities

```text
CAPABILITY 1 — INGESTION & TRANSCRIPTION
  Take raw materials (photos, PDFs, audio, Word)
  Produce clean dual-format output (PDF for user, 
  markdown for AI)

CAPABILITY 2 — INDEXING
  Classify every dars in a category tree
  Facets: domain / theme / sub-theme
  Store metadata in PostgreSQL
  Keep markdown available for deterministic full-text search
  DO NOT vectorize the religious corpus

CAPABILITY 3 — Q&A WITH SOURCE VERIFICATION
  User asks a question
  System narrows by facets, then searches markdown full-text
  Local Q&A engine (Opus 4.7 prompt label) answers ONLY based
  on candidate passages
  Cites sources with clickable references
  Refuses if no relevant passages found
```

---

## 5. Supported Source Formats

```text
✅ MANUSCRIPT PHOTOS (your handwritten notes)
   → Local OCR service (doc 37)
   → Multilingual: French + Arabic transcription support

✅ BLACKBOARD PHOTOS (during cours)
   → Local OCR service (doc 37)
   → Optimized for whiteboard/blackboard scenes

✅ PDF DOCUMENTS (support from professor)
   → Native text extraction (PyPDF2 / pdfplumber)
   → Fallback to local OCR if scanned PDF

✅ AUDIO RECORDINGS (cours recordings)
   → faster-whisper large-v3 local
   → Multilingual: French + Arabic + English
   → Code-switching aware

✅ WORD DOCUMENTS (notes from classmates)
   → python-docx parsing
   → Preserves headings and structure

✅ GOOGLE DOCS (export as docx first)

✅ TEXT FILES (.txt, .md)
```

---

## 6. The Ingestion Pipeline

### 6.1 Step-by-step flow

```text
1. USER UPLOADS material via Path > Dars > [+ Ajouter source]
   - Selects file(s) from device
   - Selects metadata: cours number, source type
     (notes_user, support_prof, notes_friend, other)
   - MANDATORY categorization prompt before processing:
     "Dans quelle branche classer ce dars ?"
     * domain (e.g. Fiqh, Aqida, Hadith, Arabic, other)
     * theme (e.g. Tahara, Salah, Tawhid, Mustalah, other)
     * sub-theme (e.g. Wudu, Ghusl, Nullifiers, other)
   - Category lists are open for now: the user can reuse an
     existing facet or add a new one.

2. BACKEND DETECTS file type and routes:
   - Image → local OCR service (doc 37)
   - PDF → text extraction (try native first, OCR fallback)
   - Audio → faster-whisper local
   - Word → python-docx
   - Text → direct read

3. EXTRACTED RAW TEXT goes to next step

4. STRUCTURE STEP — local structuring runtime:
   - Sonnet 4.6 prompt label retained until nomenclature pass
   - Identifies titles, subtitles
   - Identifies citations (Coran, hadith, scholars)
   - Identifies definitions
   - Identifies lists, tables
   - Outputs structured markdown
   - DOES NOT REWRITE: pure transcription with structure

5. PDF GENERATION — weasyprint code:
   - Takes the markdown + Dars CSS template
   - Renders beautiful PDF
   - French serif for body (Crimson, Lora, etc.)
   - Arabic font for arabic passages (Amiri, Scheherazade)
   - Citations in elegant boxed format
   - Page numbering, header with course info
   - Saves PDF to /var/lib/imperium/dars/{user_id}/{doc_id}.pdf

6. USER VALIDATES:
   - Backend returns: PDF preview + raw markdown
   - User reads the entire PDF
   - User taps [Valider] or [Modifier] or [Rejeter]
   - On Valider: doc becomes canonical
   - On Modifier: user edits the markdown manually, regenerates PDF
   - On Rejeter: doc deleted, no trace

7. INDEXING — deterministic category tree + full-text:
   - Once user validates, the markdown dars is stored as canonical
     searchable text.
   - The dars is placed in the category tree chosen at upload:
     * domain
     * theme
     * sub_theme
     * course_number
     * source_type
     * category_path
   - Metadata is stored in PostgreSQL:
     * doc_id, doc_name, page_count
     * domain, theme, sub_theme, category_path
     * course_number, source_type
     * markdown_storage_path / markdown_text
     * created_at, validated_at
   - A deterministic full-text index is maintained over the
     markdown / paragraph text.
   - No embedding is generated. The religious corpus is never
     vectorized.
```

### 6.2 Latency expectations

```text
For a 10-page handwritten document:
  - Local OCR: 30-60 seconds (10 photos × 3-6s each)
  - Local markdown structuring: 10-20 seconds
  - PDF generation: 2-5 seconds
  - User validation: variable (the user's own time)
  - Category metadata + full-text indexing: 1-5 seconds

For a 1-hour audio recording:
  - faster-whisper transcription: 5-10 minutes on CPU
  - Local markdown structuring: 20-30 seconds
  - Rest: similar to above

Total per document: 5-15 minutes typically.
This is acceptable. Documents are added rarely (1-2 per week).
```

---

## 7. The Q&A System

### 7.1 The user flow

```text
Path > Dars > [Poser une question]:

  ┌──────────────────────────────────────────┐
  │ Recherche dans tes Dars                  │
  │                                          │
  │ Ta question:                             │
  │ [____________________________________]   │
  │                                          │
  │ [Rechercher]                             │
  └──────────────────────────────────────────┘

User types: 
  "Quelles sont les conditions de validité du wudu ?"

Tap [Rechercher]:

  1. FACETS:
     - The system maps the question to domain/theme/sub-theme.
     - It narrows candidates to dars in the matching category
       branch using PostgreSQL metadata.
     - If the branch is uncertain, the AI asks a short
       clarification question instead of broad guessing.

  2. FULL-TEXT SEARCH:
     - The system extracts French keywords from the question.
     - It searches only the candidate markdown documents.
     - It returns matching paragraphs with page/source anchors.

  3. CONTEXT-WINDOW SELF-TEST:
     - The AI estimates whether all candidate paragraphs fit in
       its context window with enough room to reason safely.
     - If yes: it reads the paragraphs and answers in French.
     - If no: it tightens the deterministic search:
       * add more keywords
       * require an extra facet
       * restrict to a narrower course/sub-theme
     - It must not use vector search as a fallback.

  4. ANSWER OR REFUSAL:
     - If relevant passages remain: the local Q&A engine
       (Opus 4.7 prompt label) produces an answer in French with
       citations.
     - If no relevant passage remains: the system refuses with
       the standard out-of-corpus message.

UI shows:

  ┌──────────────────────────────────────────┐
  │ RÉPONSE                                  │
  │                                          │
  │ Les conditions de validité du wudu       │
  │ sont:                                    │
  │                                          │
  │ 1. Niya (l'intention)                    │
  │    [src: cours_05_user.pdf, p.3]         │
  │                                          │
  │ 2. Lavage du visage                      │
  │    [src: cours_05_user.pdf, p.4]         │
  │    Dalil: 5:6 (Al-Maïda)                 │
  │    [src: cours_05_user.pdf, p.5]         │
  │                                          │
  │ 3. Lavage des bras jusqu'aux coudes      │
  │    [src: cours_05_user.pdf, p.4]         │
  │                                          │
  │ ... (etc.)                               │
  │                                          │
  │ Sources consultées:                      │
  │ • cours_05_user.pdf (5 passages)         │
  │ • support_prof_cours_05.pdf (2 passages) │
  └──────────────────────────────────────────┘

Each [src: X] is clickable:
  - Opens the PDF source
  - Jumps to the exact page
  - Highlights the passage used
  - User can verify visually
```

### 7.2 Arabic Source Rule

```text
The AI does NOT interpret Arabic text and does NOT correlate Arabic
phrases by meaning.

Allowed:
- Locate a passage that matches deterministic metadata / full-text
  search.
- Answer in French based on the validated French/transliterated
  course content.
- Display the Arabic source passage exactly as stored so the USER
  can read it himself.
- Cite the Arabic source with clickable page + highlight.

Forbidden:
- Infer a religious ruling directly from Arabic wording.
- Translate Arabic as the basis for an answer.
- Correlate separate Arabic passages semantically.
- Decide between Arabic formulations.

Interpretation of Arabic belongs to the scholars and to the
professor. The professor remains the ultimate authority.
```

### 7.3 Conflict detection in answers

```text
When the candidate passages contain CONTRADICTING information,
the local Q&A engine (Opus 4.7 prompt label) must surface this
in the answer:

  ┌──────────────────────────────────────────┐
  │ ⚠️ Conflit détecté dans tes sources      │
  │                                          │
  │ Tes documents contiennent deux versions  │
  │ différentes:                             │
  │                                          │
  │ • Version A (cours_05_user.pdf, p.3):    │
  │   "Le wudu nécessite X"                  │
  │                                          │
  │ • Version B (cours_05_omar.pdf, p.5):    │
  │   "Le wudu nécessite Y"                  │
  │                                          │
  │ Quelle est la bonne réponse selon ton    │
  │ professeur ?                             │
  │                                          │
  │ [Demander à mon professeur et noter]     │
  │ [Ignorer pour l'instant]                 │
  └──────────────────────────────────────────┘

User can come back later with the professor's resolution.
That resolution becomes a "magisterial annotation" (Section 8).
```

### 7.4 Refusal when out of corpus

```text
If deterministic full-text search finds no relevant passage OR if
the local Q&A engine determines the question cannot be answered
with the candidate passages:

  ┌──────────────────────────────────────────┐
  │ Pas de réponse dans tes cours             │
  │                                          │
  │ Je n'ai pas trouvé d'information         │
  │ pertinente sur ce sujet dans ton corpus.│
  │                                          │
  │ Suggestions:                             │
  │ • Demander à ton professeur              │
  │ • Ajouter un nouveau document si tu      │
  │   as la source                           │
  │                                          │
  │ Quand tu auras la réponse, tu peux       │
  │ l'enregistrer ici pour que je puisse     │
  │ y référer à l'avenir.                    │
  │                                          │
  │ [Ajouter une réponse de mon professeur]  │
  └──────────────────────────────────────────┘
```

---

## 8. Magisterial Annotations (Critical Mechanism)

This is the most important feature for keeping the corpus reliable over time.

### 8.1 What they are

```text
A "magisterial annotation" is a piece of authoritative content 
that the user adds AFTER consulting their professor:

- To resolve a conflict between sources
- To answer a question the corpus didn't cover
- To correct an error the user discovered
- To add a nuance the professor clarified

These annotations have ABSOLUTE PRIORITY over any other source.
```

### 8.2 How they're created

```text
Two paths:

PATH A — From a conflict:
  In the conflict warning screen (Section 7.3)
  User taps [Demander à mon professeur et noter]
  
  Form opens:
    Question concernée:
    [Auto-filled from the original query]
    
    Réponse de mon professeur:
    [_______________________________]
    
    Dalil (verset, hadith, citation):
    [_______________________________]
    
    Date de la réponse:
    [Auto = today]
    
    [Enregistrer]

PATH B — From an out-of-corpus question:
  In the "no answer" screen (Section 7.4)
  Same form, same flow.

PATH C — Standalone:
  Path > Dars > [+ Annotation magistrale]
  Same form, no original question reference.
```

### 8.3 How they're used in search

```text
When a question is asked, the search includes:
  1. Deterministic facet narrowing across normal dars documents
  2. Full-text search across markdown / paragraph text
  3. ALSO full-text search across active magisterial_annotations
  
If a magisterial annotation matches the same question terms or
facet branch:
  It is presented FIRST in the answer
  Tagged: "Réponse de ton professeur (date)"
  Gets ABSOLUTE PRIORITY over conflicting sources

If a normal source contradicts a magisterial annotation:
  The annotation wins
  The conflict is silently resolved (no warning shown)
  Optional: notify "Note: ce sujet a été tranché par ton 
   professeur le X"
```

### 8.4 Schema

```sql
CREATE TABLE dars_magisterial_annotations (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  
  question_text      TEXT NOT NULL,
                     -- the question that triggered this
  professor_answer   TEXT NOT NULL,
                     -- the actual answer from the professor
  dalil              TEXT NULL,
                     -- supporting evidence (verse, hadith)
  date_answered      DATE NOT NULL,
  notes              TEXT NULL,
                     -- any additional context
  
  related_source_ids UUID[] NULL,
                     -- if resolving a specific conflict

  domain             VARCHAR(64) NULL,
  theme              VARCHAR(128) NULL,
  sub_theme          VARCHAR(128) NULL,
  category_path      TEXT NULL,
                     -- same open facet system as dars documents
  
  status             VARCHAR(32) NOT NULL DEFAULT 'active',
                     -- 'active' | 'superseded'
  superseded_by      UUID NULL REFERENCES dars_magisterial_annotations(id),
  superseded_at      TIMESTAMPTZ NULL,
  
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX dars_magisterial_annotations_active_idx
ON dars_magisterial_annotations (user_id, status)
WHERE status = 'active';

CREATE INDEX dars_magisterial_annotations_facet_idx
ON dars_magisterial_annotations (user_id, domain, theme, sub_theme)
WHERE status = 'active';

CREATE INDEX dars_magisterial_annotations_fts_idx
ON dars_magisterial_annotations
USING gin (
  to_tsvector(
    'simple',
    coalesce(question_text, '') || ' ' ||
    coalesce(professor_answer, '') || ' ' ||
    coalesce(dalil, '')
  )
)
WHERE status = 'active';
```

---

## 9. Document Versioning

### 9.1 The mechanism

```text
When the user adds a NEW version of a document on the same 
topic:

User flow:
  Path > Dars > Documents > [Cours 05 — Wudu]
  Tap [+ Nouvelle version]
  Upload new material (e.g. better notes from a friend)
  System processes it (same pipeline as Section 6)
  
  After validation:
    Old version: status = 'archived', tag = 'v1'
    New version: status = 'active', tag = 'v2'
  
  Both versions remain stored.
  Only 'active' versions are searched by metadata + full-text.
```

### 9.2 Conflict between v1 and v2

```text
In rare cases, v1 and v2 contain contradicting points.

Detection:
  At validation/indexing time, when v2 is added:
  - System restricts comparison to the same category branch and
    same course/topic metadata.
  - Full-text search finds paragraphs sharing headings, keywords,
    source labels, or explicit lesson references.
  - If candidate passages differ significantly: mark as potential
    conflict
  - Surface in user's Dars dashboard:
    "Conflit potentiel détecté entre v1 et v2 du cours X"
  
User resolves via professor (Section 8 mechanism).
The magisterial annotation overrides both versions.

If user doesn't resolve:
  - System uses v2 by default (newest = most accurate assumption)
  - Old version marked as superseded but kept
  - User can view both anytime
```

---

## 10. Categorization Structure

```sql
CREATE TABLE dars_documents (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  
  -- Categorization
  course_year         VARCHAR(16) NULL,         -- "Année 1"
  course_module       VARCHAR(64) NULL,         -- "Aqida" | "Fiqh" | etc.
  domain              VARCHAR(64) NOT NULL,     -- open facet: "Fiqh"
  theme               VARCHAR(128) NOT NULL,    -- open facet: "Tahara"
  sub_theme           VARCHAR(128) NULL,        -- open facet: "Wudu"
  category_path       TEXT NOT NULL,            -- "Fiqh/Tahara/Wudu"
  course_number       INTEGER NOT NULL,         -- 5 (cours 5)
  course_title        TEXT NOT NULL,            -- "Tawhid Al-Asma wa-s-Sifat"
  
  -- Themes (auto-detected, user can edit)
  primary_theme       VARCHAR(128) NULL,
  secondary_themes    TEXT[] NULL,
  tags                TEXT[] NULL,
  
  -- Source
  source_type         VARCHAR(32) NOT NULL,
                      -- 'notes_user' | 'support_prof' | 'notes_friend' | 'other'
  source_origin       TEXT NULL,                -- "from Omar"
  
  -- Versioning
  version             VARCHAR(8) NOT NULL DEFAULT 'v1',
  status              VARCHAR(32) NOT NULL DEFAULT 'active',
                      -- 'active' | 'archived' | 'superseded'
  superseded_by       UUID NULL REFERENCES dars_documents(id),
  
  -- Files
  raw_storage_uri     TEXT NOT NULL,
                      -- where the original file is stored
  pdf_storage_uri     TEXT NOT NULL,
                      -- the beautifully formatted PDF
  markdown_text       TEXT NOT NULL,
                      -- the structured markdown for AI
  
  -- Metadata
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  validated_at        TIMESTAMPTZ NULL,
  page_count          INTEGER NULL,
  word_count          INTEGER NULL
);

CREATE INDEX dars_documents_user_status_idx
ON dars_documents (user_id, status);

CREATE INDEX dars_documents_user_module_course_idx
ON dars_documents (user_id, course_module, course_number);

CREATE INDEX dars_documents_category_path_idx
ON dars_documents (user_id, status, category_path);

CREATE INDEX dars_documents_markdown_fts_idx
ON dars_documents
USING gin (to_tsvector('simple', markdown_text));

CREATE TABLE dars_document_passages (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  document_id         UUID NOT NULL REFERENCES dars_documents(id) 
                                                          ON DELETE CASCADE,
  
  passage_index       INTEGER NOT NULL,
  passage_text        TEXT NOT NULL,
  page_number         INTEGER NULL,
  source_anchor       TEXT NULL,
                      -- stable PDF/text anchor used for page jump + highlight
  
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX dars_document_passages_user_doc_idx
ON dars_document_passages (user_id, document_id);

CREATE INDEX dars_document_passages_fts_idx
ON dars_document_passages
USING gin (to_tsvector('simple', passage_text));
```

---

## 11. AI Stack Summary

```text
┌──────────────────────────────────────────────────────────┐
│ TASK                       │ MODEL              │ COST/YR │
├──────────────────────────────────────────────────────────┤
│ OCR (manuscripts, photos)  │ Local OCR          │ 0€      │
│ OCR fallback if allowed    │ Gemini             │ ~5€     │
│ Audio (FR+AR cours)        │ faster-whisper     │ 0€      │
│                            │ large-v3 local     │         │
│ Markdown structuring       │ Sonnet 4.6 label   │ 0€      │
│                            │ retained; local    │         │
│                            │ execution required │         │
│ PDF rendering              │ weasyprint code    │ 0€      │
│ Category indexing          │ PostgreSQL         │ 0€      │
│ Full-text retrieval        │ PostgreSQL FTS     │ 0€      │
│ Q&A reasoning              │ Opus 4.7 prompt    │ 0€      │
│                            │ label retained;    │         │
│                            │ local execution    │         │
│                            │ required           │         │
├──────────────────────────────────────────────────────────┤
│ TOTAL ANNUAL DEFAULT LOCAL                      │ 0€      │
│ POSSIBLE OCR FALLBACK ONLY                      │ ~5€     │
└──────────────────────────────────────────────────────────┘
```

**Note:** Religious Q&A is local by default. If the local Q&A engine
cannot handle the request or the candidate set is too large, the system
narrows the deterministic search or refuses; it does not send the corpus
to a cloud model.

---

## 12. AI Task Types

```text
dars.document.ocr               - Local OCR; Gemini fallback only if allowed
dars.document.transcribe        - Whisper local (audio static override)
dars.document.structure         - Local structuring; Sonnet label retained
dars.document.categorize        - mandatory facet prompt
dars.document.index_metadata    - category tree + PostgreSQL full-text
dars.question.facets            - choose / clarify domain-theme-subtheme
dars.question.full_text_search  - deterministic markdown search
dars.question.answer            - Opus 4.7 prompt label, local execution
dars.annotation.index_metadata  - category tree + PostgreSQL full-text
```

---

## 13. The Opus Q&A Prompt

The prompt name is retained for now for nomenclature continuity, but the
religious Q&A execution must remain local. The prompt is critical. Here
is the strict template.

```text
You are an assistant for religious sciences study.

CRITICAL RULES (non-negotiable):
1. You MUST answer based ONLY on the provided passages.
2. You MUST cite every claim with [src: filename, p.X].
3. You MUST refuse to answer if the passages don't contain 
   the information.
4. You MUST NOT invent any dalil, verse, hadith, or scholar's 
   ruling.
5. You MUST NOT use general religious knowledge from your 
   training. Only the user's corpus matters.
6. You MUST surface conflicts between passages explicitly.
7. You MUST NOT take a personal position on differences between 
   scholars. Present the positions and refer to the professor.
8. Magisterial annotations have ABSOLUTE priority. If present, 
   use them as the canonical answer.
9. Sensitive topics (politics, sects, takfir): refuse to answer 
   and refer to the professor.
10. You MUST NOT interpret Arabic text. Display Arabic source
   passages exactly for the user to read; do not derive rulings
   from Arabic wording.
11. Tone: factual, direct, never opinionated. Servant, not master.

USER'S QUESTION:
{user_question}

DETERMINISTIC CANDIDATE PASSAGES (with source metadata):
{candidate_passages}

MAGISTERIAL ANNOTATIONS (if any):
{magisterial_annotations}

YOUR ANSWER:
- Structure with clear points
- Each point cited with [src: ...]
- If conflict detected, surface explicitly
- If no clear answer, refuse with the standard message:
  "Je n'ai pas trouvé d'information pertinente sur ce sujet 
   dans ton corpus. Demande à ton professeur."

Output in French. Use Arabic transliteration for technical 
terms (e.g. "wudu", "salah", "niya").
```

---

## 14. UI Surface (V3)

```text
Path Dashboard:
  [Apprentissage religieux] section (linked from doc 49)
  → [Voir mes Dars]

Path > Dars main view:
  ┌─────────────────────────────────────────────┐
  │ MES DARS                                    │
  │                                             │
  │ [+ Ajouter une source]                      │
  │ [+ Annotation magistrale]                   │
  │ [🔍 Poser une question]                     │
  │                                             │
  │ DOCUMENTS PAR MODULE:                       │
  │   Aqida (12 docs)                           │
  │   ├─ Cours 1 — Tawhid                       │
  │   ├─ Cours 2 — Imane                        │
  │   └─ ...                                    │
  │                                             │
  │   Fiqh (8 docs)                             │
  │   ├─ Cours 1 — Tahara                       │
  │   ├─ Cours 5 — Wudu                         │
  │   │   ├─ v1 (notes_user)                    │
  │   │   └─ v2 (notes_friend) [ACTIVE]         │
  │   └─ ...                                    │
  │                                             │
  │   ANNOTATIONS MAGISTRALES (3)               │
  │   ├─ Wudu — conditions (réponse 2026-04-15) │
  │   ├─ ...                                    │
  └─────────────────────────────────────────────┘

Document detail view:
  - PDF preview
  - Metadata
  - [Voir versions historiques]
  - [Modifier métadonnées]
  - [+ Nouvelle version]
  - [Supprimer]

Question view:
  - Search bar
  - Recent questions (history)
  - Tap to re-run a previous question

Settings:
  - Manage stored documents
  - Manage magisterial annotations
  - Clear all dars data (irreversible)
  - Export all to ZIP (PDFs + markdown)
```

---

## 15. Privacy & Security

```text
DATA SENT TO GEMINI:
- None by default for religious dars.
- Residual cloud case only: OCR fallback if the local OCR tower is
  unavailable/down, under doc 37 privacy gate.
- For `very_high` religious content, the system follows doc 52 §9A:
  degrade / abstain instead of sending the content to cloud.

DATA SENT TO ANTHROPIC (Sonnet, Opus):
- None by default for religious dars.
- Structuring and Q&A must run locally for this corpus.
- If local Q&A cannot safely answer, the system narrows deterministic
  search or refuses; it does not send the religious corpus to cloud.

DATA THAT NEVER LEAVES THE VPS:
- Religious extracted text and markdown
- Audio recordings (Whisper local)
- Magisterial annotations
- Final stored PDFs
- Category metadata and full-text search indexes
- User religious questions and candidate passages

ENCRYPTION:
- Files at rest: filesystem-level encryption (LUKS)
- DB: standard PostgreSQL encryption
- Backups: GPG-encrypted

ACCESS CONTROL:
- Only the authenticated user can access their corpus
- No multi-tenant sharing
- Disconnection logs out all sessions
```

---

## 16. Implementation Order (V3)

```text
PHASE 1 — Schema migrations
  ├─ dars_documents
  ├─ dars_document_passages
  └─ dars_magisterial_annotations

PHASE 2 — Local infrastructure
  ├─ local OCR service per doc 37
  ├─ local religious structuring / Q&A runtime
  ├─ faster-whisper large-v3 deployment (~3 GB RAM)
  ├─ PostgreSQL full-text search indexes
  └─ weasyprint setup with Dars CSS template

PHASE 3 — Ingestion services
  ├─ services/path/dars/ingestion.py (multi-format dispatcher)
  ├─ services/path/dars/ocr.py (local OCR + gated Gemini fallback)
  ├─ services/path/dars/transcribe.py (Whisper)
  ├─ services/path/dars/parse_pdf.py (PyPDF2)
  ├─ services/path/dars/parse_word.py (python-docx)
  ├─ services/path/dars/structure.py (local; Sonnet label retained)
  ├─ services/path/dars/categorize.py (mandatory facets)
  ├─ services/path/dars/render_pdf.py (weasyprint)
  └─ services/path/dars/index_text.py (category tree + full-text)

PHASE 4 — Q&A services
  ├─ services/path/dars/search.py (facets + full-text)
  ├─ services/path/dars/answer.py (local; Opus 4.7 label retained)
  └─ services/path/dars/conflict_detect.py

PHASE 5 — Annotations
  ├─ services/path/dars/annotations.py
  └─ Resolution flow (from conflict detection)

PHASE 6 — API endpoints
  ├─ POST   /api/v1/path/dars/documents (upload)
  ├─ GET    /api/v1/path/dars/documents
  ├─ GET    /api/v1/path/dars/documents/{id}
  ├─ POST   /api/v1/path/dars/documents/{id}/validate
  ├─ POST   /api/v1/path/dars/documents/{id}/version
  ├─ DELETE /api/v1/path/dars/documents/{id}
  ├─ POST   /api/v1/path/dars/questions (search + answer)
  ├─ POST   /api/v1/path/dars/annotations (create)
  ├─ GET    /api/v1/path/dars/annotations
  ├─ DELETE /api/v1/path/dars/annotations/{id}
  └─ GET    /api/v1/path/dars/conflicts (open conflicts)

PHASE 7 — Prompts
  ├─ Add to the prompt catalog:
  │   - sonnet_dars_structure.txt (label retained; local execution)
  │   - opus_dars_qa.txt (label retained; local execution)
  └─ Tested with realistic religious sciences fixtures

PHASE 8 — UI in Android
  ├─ Dars main view
  ├─ Upload flow with format detection
  ├─ Validation flow (PDF preview + accept/reject)
  ├─ Question view with chat-like history
  ├─ Conflict resolution flow
  ├─ Annotation creation form
  └─ Settings: export, delete, manage versions
```

---

## 17. Edge Cases

### 17.1 Mixed-language document

```text
Some documents have French + Arabic + transliterated Arabic.

Pipeline handles automatically:
- Whisper large-v3: detects language per segment
- Local OCR: handles mixed scripts
- Local structuring runtime: preserves original language in markdown
- Full-text search: searches stored markdown deterministically
- Local Q&A runtime: answers in French, displays Arabic source
  passages without interpreting them
```

### 17.2 Very long audio (3-hour cours)

```text
Whisper local with 3 GB RAM may struggle on 3+ hours.

Mitigation:
- Auto-split audio into 30-min chunks
- Transcribe each chunk separately
- Concatenate results in markdown
- Total transcription time: ~30-60 min on CPU
```

### 17.3 Poor handwriting

```text
If local OCR confidence is low for a page:
- Flag the page in the validation view
- Show side-by-side: photo + extracted text
- User can correct manually before validation
- Better to ask user upfront than have errors slip through
```

### 17.4 User wants to ask a complex question

```text
For complex multi-part questions:
- The first deterministic search may return too many paragraphs
- The system runs the context-window self-test from Section 7.1
- If the candidate set is too large, it tightens keywords/facets
- If the answer still cannot be grounded in a manageable set of
  passages, it refuses rather than broadening to semantic search
```

### 17.5 Document deletion

```text
User deletes a document:
- DELETE dars_documents (cascades to passages)
- DELETE related full-text passage entries
- DELETE original file from filesystem
- Magisterial annotations referencing this doc:
  - Marked: "source_now_missing = TRUE"
  - Still searchable by full-text, but warning shown to user
```

---

## 18. Non-Goals For V3

```text
❌ Auto-summarization of documents
   (Risk of altering meaning. User can request later if needed.)

❌ AI-generated questions for self-study (V4)

❌ Cross-document fact-checking (V4)

❌ Translation of Arabic passages
   (Out of scope; the user knows enough to read original)

❌ Voice queries
   (V4: speak the question instead of typing)

❌ Sharing dars with others
   (System is mono-user)

❌ Public AI model use for sensitive questions
   (Refusal is the answer)

❌ "Smart suggestions" of related topics
   (Adds complexity; user can navigate by module)
```

---

## 19. V4+ Future Considerations

```text
- Auto-summarization on demand (with strong disclaimer)
- AI-generated study quizzes from corpus
- Voice questions with Whisper
- Audio playback of Q&A answers
- Cross-document conflict scanning (proactive)
- Statistical analysis: "topics I've studied most"
- Time-based progression tracking
- Integration with WR (weekly Dars summary)
```

---

## 20. References

- `41_PATH_LOGIC_DETAIL.md` — Path module
- `49_PATH_YOUTUBE_CHANNELS.md` — sister feature in same UI section
- `09_PGVECTOR_MEMORY_POLICY.md` — vector storage policy; dars religious
  content is excluded from vectorization
- `30_AI_ROUTING_AND_SCORING_POLICY.md` — model selection
- `36_PROMPTS_CLOUD_AI.md` — Sonnet + Opus prompts
- `37_VISION_OCR_PROMPTS.md` — Gemini OCR prompts
- `38_VECTORIZATION_PIPELINE.md` — embedding architecture for learning
  patterns only, not the religious corpus

---

## 21. Final Note

```text
This feature must NEVER:
- Replace the professor
- Be the sole source of religious authority
- Encourage skipping authentic learning
- Become a fatwa-issuing system
- Speak with religious authority

This feature ONLY:
- Helps the user retrieve what THEY have already learned
- Helps cross-reference between THEIR own notes
- Helps prepare for THEIR exams
- Helps remember THEIR professor's teachings

The professor remains the authority. Always.
```

---

**Document version:** 1.0
**Status:** V3 design specification (DO NOT IMPLEMENT before V1 + V2)
**Last updated:** 2026-04-29
