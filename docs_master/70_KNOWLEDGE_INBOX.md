# 70 - Knowledge Inbox ("Nourrir l'IA")

## 1. Purpose

The Knowledge Inbox is the canonical way for the user to **teach the global AI
things it could not learn otherwise** by uploading documents that become part of
the system's vectorized knowledge base.

It is exposed as a **"Nourrir l'intelligence artificielle"** action inside the
**Settings → Intelligence Artificielle** sub-section of **every app** (Imperium,
Vector, Vault, Pulse, Path). The entry point is per-app, but the knowledge is
**global**: there is one brain.

Canonical examples by entry point:

| Entry app | Example document fed |
|---|---|
| Vector | Vehicle maintenance log (carnet d'entretien) |
| Pulse | Blood test results, medical document |
| Path | New morning invocation text |
| Vault | Invoice PDF (as knowledge, not as a transaction) |
| Imperium | Completed project dossier |

---

## 2. Core Principle: One Brain, No App Tagging

```text
DECISION (user spec):
A document fed from ANY app enriches the GLOBAL AI knowledge, not a per-app silo.
No app tag is attached to the ingested knowledge.

WHY: tagging would artificially restrict which domain can use the data.
```

Worked example (why no tag):

```text
User feeds the vehicle maintenance log via Vector.
The vectorized knowledge is global, so:
  - Vector uses it → "your next service is approaching"
  - Vault ALSO uses it → "a ~200€ expense is coming in the next days"
Both apps draw from the same raw knowledge under different angles.
A "Vector" tag would have prevented Vault from ever seeing it.
```

The AI is allowed to make its own cross-domain connections from the raw content.
We do not pre-orient it.

---

## 3. What This Is NOT (boundary with metric/transaction capture)

The Knowledge Inbox is **separate** from the metric/transaction capture systems
that already exist. They coexist and must not be merged.

| | Knowledge Inbox ("Nourrir l'IA") | Metric/Transaction capture |
|---|---|---|
| Nature | Knowledge documents | Business/metric data |
| Examples | Maintenance log, invocation, project dossier | Receipt scan → a transaction; blood test feed → medical constants |
| Destination | Global vector memory (pgvector) | Structured tables (transactions, meal logs, etc.) |
| Goal | Teach / enrich the AI | Record a precise business fact |
| Existing docs | This doc (70) | Vault scan VAU-04/VAU-05 (doc 59/42), Pulse medical feed (doc 34) |

A receipt scanned in Vault creates a **transaction** (structured: amount, date).
A 40-page PDF about the car fed via the Inbox becomes **vectorized context** the
AI can consult. Two mechanisms, two goals.

> Note: doc 34 (Pulse Medical Feed) ingests medical documents for **Pulse medical
> rules** (structured rule extraction with a consent gate). The Knowledge Inbox is
> the general-purpose knowledge channel. Where they overlap conceptually, doc 34
> remains authoritative for medical rule extraction; the Inbox does not duplicate
> that pipeline.

---

## 4. Non-Negotiable Rules

```text
✅ The Knowledge Inbox can:
   - let the user browse the tablet's folders and select a file
   - validate file type and size before upload
   - upload the file to the backend
   - have the AI analyze the file immediately
   - show the user what the AI extracted
   - let the user edit/correct the extraction before validation
   - vectorize into the GLOBAL knowledge base only after explicit user validation

❌ The Knowledge Inbox must never:
   - vectorize anything without explicit user validation
   - attach an app tag that restricts cross-domain use
   - accept video or audio files (V1)
   - create canonical business records (that is the metric/transaction path)
   - silently overwrite or delete previously ingested knowledge
```

---

## 5. Authority Boundary

- The Android client (Settings → IA → "Nourrir l'IA") provides the file picker,
  the type/size pre-check, and the validation/edit UI.
- The backend is authoritative for: final type/size enforcement, AI analysis,
  extraction result, vectorization, and storage in pgvector.
- Nothing enters the vector memory without an explicit user validation action.
- The extraction shown to the user is a **draft** until validated (consistent
  with the project-wide "nothing canonical without user approval" rule).

---

## 6. Accepted File Types & Size (V1)

```text
V1 RULE: accept content files, including AUDIO and VIDEO. The Path needs this,
for example optional invocation audio. Reject by SAFETY, not by media type.

Likely ACCEPTED:
  - documents: PDF, plain text, Word, Excel
  - images: PNG, JPG
  - AUDIO: common formats (e.g. mp3, m4a, wav, ogg)
  - VIDEO: common formats (e.g. mp4, mov)
  (exact allow-list TBD)

REJECTED (safety):
  - executables and unsafe/odd types
  - examples: .exe, .info, scripts, and other potentially dangerous file types

Max file size: TBD. Audio/video imply a higher cap than documents, to define.
```

The client does a soft pre-check; the backend does the HARD enforcement and
returns a clear error if the type is unsafe or the size is exceeded.

Rationale: audio/video can be legitimate content. An invocation's audio is useful
and harmless when validated; an executable is a security risk. The correct reject
criterion is danger, not media format.

---

## 7. The Flow

```text
1. User opens Settings → Intelligence Artificielle → "Nourrir l'IA"
2. A small Inbox window opens
3. User browses tablet folders → selects a file
4. Client pre-check: type accepted? size acceptable?
      - if not → reject with clear message, stay on picker
5. Upload to backend
6. Backend re-validates type/size (hard enforcement)
7. AI analyzes the file immediately → produces an extraction summary
8. The window shows what the AI understood (EDITABLE)
9. User reviews, edits/corrects if needed
10. User validates ("Ajouter à la mémoire")
11. Backend vectorizes the (possibly edited) content into the GLOBAL vector base
12. Confirmation shown; window can close
```

If the user cancels at step 9/10, nothing is vectorized; the uploaded file is
discarded or kept as a non-vectorized pending item (see §8 states).

---

## 8. UI States

| State | Trigger | UI |
|---|---|---|
| Idle | Window opened | File picker, accepted-types hint, size hint. |
| Invalid file | Type/size pre-check fails | Inline error under the file, no upload. |
| Uploading | After selection passes pre-check | Progress line, cancel available. |
| Analyzing | Upload done, AI working | Analyzing shimmer, no fake result text. |
| Review (editable) | Extraction ready | Editable extraction summary + Validate / Cancel. |
| Vectorizing | After validate | Sync line. |
| Done | Vectorization confirmed | Confirmation; entry appears in ingest history. |
| Error | Upload/analyze/vectorize failure | Clear error + retry; nothing partially vectorized. |
| Offline | No network | Queue local pending upload banner; no analysis until online. |

---

## 9. Events

| Event | Trigger | Notes |
|---|---|---|
| `inbox.document.uploaded` | File accepted and uploaded. | Not yet knowledge. |
| `inbox.document.analyzed` | AI produced an extraction draft. | Draft only. |
| `inbox.document.validated` | User validated (possibly edited). | Triggers vectorization. |
| `inbox.document.vectorized` | Content embedded into global memory. | Now usable by all apps. |
| `inbox.document.rejected` | Type/size invalid or user cancelled. | No memory write. |

---

## 10. Data Model (V1, indicative)

```sql
CREATE TABLE knowledge_inbox_documents (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  entry_app          VARCHAR(16) NOT NULL,   -- provenance UI only (imperium|vector|vault|pulse|path)
                                             -- NOT used to restrict retrieval (see §2)
  original_filename  TEXT NOT NULL,
  mime_type          VARCHAR(128) NOT NULL,
  size_bytes         BIGINT NOT NULL,
  status             VARCHAR(24) NOT NULL DEFAULT 'uploaded',
                     -- uploaded | analyzed | validated | vectorized | rejected | failed
  extraction_draft   JSONB NULL,             -- what the AI understood (editable)
  extraction_final   JSONB NULL,             -- after user edit + validation
  uploaded_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  vectorized_at      TIMESTAMPTZ NULL
);

-- The vectorized chunks live in the existing global pgvector store.
-- entry_app is kept for provenance/audit only; retrieval does NOT filter on it.
```

Note on `entry_app`: it records *where the user uploaded from* for history/audit,
but per §2 it must NOT be used as a retrieval filter that restricts cross-domain
use. It is provenance, not a scope.

---

## 11. Endpoints (V1, indicative — TBD)

```text
TBD POST   /api/ai/knowledge-inbox/upload          (multipart, type/size enforced)
TBD GET    /api/ai/knowledge-inbox/{id}/extraction (the editable draft)
TBD PATCH  /api/ai/knowledge-inbox/{id}/extraction (user edits)
TBD POST   /api/ai/knowledge-inbox/{id}/validate   (vectorize the final content)
TBD GET    /api/ai/knowledge-inbox/history         (past ingests, status)
TBD DELETE /api/ai/knowledge-inbox/{id}            (remove a pending/rejected item)
Headers for mutations: Idempotency-Key
```

---

## 12. AI Analysis & Vectorization

- Analysis model: routed through the existing AI router. A document analysis is a
  vision/text extraction task; routing tier depends on document complexity.
- Vectorization: chunk + embed into the existing global pgvector store (same
  store used across the ecosystem).
- Privacy: documents may contain sensitive data (medical, financial, religious).
  Apply the same external-model privacy gates as the rest of the system; prefer
  local processing where the routing policy requires it for sensitive content.
- The user-edited `extraction_final` is what gets vectorized, not the raw draft,
  so corrections are honored.

---

## 13. Placement In Each App

Location: **Settings → Intelligence Artificielle → "Nourrir l'IA"** button.

This is a **settings sub-surface**, not a top-level navigation screen. It is the
same feature in all five apps; only the entry point's surrounding settings differ.

> This resolves the earlier "Inbox" ambiguity (audit trou #2): the Inbox is NOT a
> top-level Imperium screen. It is a cross-app settings action feeding one global
> brain. Any top-level `IMP.INBOX.MAIN` reference from an earlier draft should be
> reconciled against this document.

---

## 14. Open Points (to finalize later)

- Precise accepted file-type allow-list (§6).
- Max file size (§6).
- Audio/video storage and processing limits: larger uploads, transcription for
  audio, frame/OCR extraction for video, and vectorization cost/latency.
- Whether rejected/cancelled uploads are discarded immediately or kept as pending.
- Retention policy for the original uploaded file after vectorization (keep the
  source? keep only the embeddings?).
- Whether the ingest history is per-app filtered in the UI (display only) while
  retrieval stays global.

---

## 15. References

- `01_SIGNAL_VARIABLES_DICTIONARY.md`
- `05_DATABASE_SCHEMA.md` — existing pgvector store
- `30_AI_ROUTING_AND_SCORING_POLICY.md` — analysis routing
- `34_PULSE_MEDICAL_FEED_AI.md` — separate medical rule extraction pipeline
- `59_DESIGN_SYSTEM_V1_DRAFT.md` — settings surfaces, states
- `42_VAULT_LOGIC_DETAIL.md` — transaction capture (the other, separate path)

---

**Document version:** 1.0 (new feature spec — was an undocumented early-project intent)
**Status:** Knowledge Inbox V1 reference (file-type/size details pending)
**Last updated:** 2026-06-08
