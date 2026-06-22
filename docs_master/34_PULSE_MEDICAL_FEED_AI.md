# 34 - Pulse Medical Feed AI

## 1. Purpose

This document defines how Pulse handles medical documents (blood tests,
prescriptions, medical reports) using GPT-5.5 to generate actionable rules
consumable by Qwen for daily nutrition and training adjustments — and the
**V1 safety policy** that governs that handling.

Pulse can store user-provided medical context and extract practical constraints
for planning, but **it is not a medical authority**. The system must not
diagnose, prescribe, or silently activate health rules.

Medical documents are sensitive health data under **RGPD article 9**. V1 requires
explicit consent before upload and explicit user validation before any derived
rule becomes active.

> **Canonical safety shorthand:** no diagnosis, no prescription, user validation
> before activation, no automatic rule activation.

This is one of the high-value, low-frequency AI use cases in the system.

---

## 2. The Use Case In One Diagram

```text
User uploads medical document (PDF or image)
        ↓
Consent gate (RGPD art. 9) — see §5
        ↓
Backend creates ai_task (pulse.medical_document_extract)
        ↓
n8n claims task
        ↓
GPT-5.5 (omnimodal native) reads document + cross-references with:
  - anonymized biological context required for interpretation only
  - past workout history
  - past nutrition data
  - past medical reports
        ↓
GPT-5.5 produces structured rules JSON (requires_user_validation = TRUE)
        ↓
Backend stores ai_result
        ↓
User reviews + validates EACH rule individually
        ↓
Backend stores validated rules in pulse_medical_rules
        ↓
pulse.medical_rule.activated → Imperium may replan
        ↓
Qwen reads active rules daily to adjust:
  - meal suggestions
  - training intensity
  - hydration targets
  - recovery recommendations
```

---

## 3. Model Routing

Per doc 30 §6.4, medical analysis uses a **GPT-5.5 static override**.

```text
task: pulse.medical_document_extract
model_override: GPT-5.5 static override
reason: medical document reasoning and safety
ocr_service: not used except generic image/PDF OCR pre-extraction when required
qwen: may classify routing metadata only, never final medical content
```

The OCR service may extract raw visible text from a scanned image if needed,
but medical interpretation and rule drafting are routed to GPT-5.5 static
override.

### 3.1 Why GPT-5.5 (and not Opus)

```text
✅ Native omnimodal (PDF + image in one model)
✅ Output more concise than Opus (better for rules consumption)
✅ Excellent grounded reasoning
✅ Explicit instruction following (rule format strict)
✅ Better at producing structured rules from medical content
```

Fable 5 is reserved for the WR re-planning (deep reasoning across domains).
GPT-5.5 is the right tool for medical-to-rules transformation.

---

## 4. Document Types Supported

Allowed document types:

```text
- Blood tests (numerical values + reference ranges)
- Prescription orders (medications + dosages + duration)
- Medical reports (cardiology, sports medicine, etc.)
- Imaging report summaries (echocardiogram, ultrasound text)
- Medical certificates
- Physiotherapy / sports limitation notes
- Allergy or intolerance notes
- Discharge or consultation summaries
- Vaccination records
- Other user-confirmed medical document
```

Rejected or warning types:

```text
- Identity-only documents without medical content
- Unreadable image/PDF
- Third-party document not belonging to the user
- Document containing another person's medical data
- Raw imaging files (DICOM, MRI scans) — not supported V1
- Genetic test data — not supported V1
- Mental health records — privacy concern, not supported V1
```

---

## 5. Consent Gate (RGPD)

Before upload, screen **PUL-14** must show a consent gate with:

- document may contain sensitive health data
- extraction is AI-assisted and can be wrong
- Pulse does not diagnose
- derived rules are inactive until user validates each one
- raw medical document retention policy is visible
- user can delete the document and revoke derived rules

Consent fields:

| Field | Rule |
|---|---|
| `medical_upload_consent` | Required true per upload. |
| `consent_version` | Stored with document. |
| `consented_at` | Server timestamp. |
| `consent_scope` | `extract_constraints_for_pulse_and_imperium`. |

**No consent means no upload.**

---

## 6. Trigger Flow

### 6.1 User uploads document

```text
Pulse app → "Add medical document" → camera or file picker
  → consent gate (§5) must pass first
  → POST /api/pulse/medical-documents
    headers: Idempotency-Key
    body: multipart/form-data with PDF or image

Backend:
  → stores raw file in object storage (encrypted at rest)
  → creates ai_task (pulse.medical_document_extract)
  → status = uploaded → extracting
  → POSTs signed webhook to n8n
  → returns medical_document_id to UI

UI shows:
  "Document reçu. Analyse en cours..."
  Status banner with task progress.
```

### 6.2 Document record fields

| Field | Rule |
|---|---|
| `medical_document_id` | Backend generated. |
| `document_type` | User selected or AI suggested, user editable. |
| `status` | `uploaded\|extracting\|needs_validation\|validated\|failed\|deleted`. |
| `raw_storage_uri` | Encrypted storage reference, never shown in logs. |
| `retention_delete_after` | Defaults from §11. |
| `extraction_task_id` | AI task reference. |
| `confidence` | Model confidence for extraction quality. |
| `warnings` | Missing pages, low OCR quality, ambiguous medical terms. |

### 6.3 n8n analysis

```text
n8n claims the task
  → fetches task context via internal API:
      - reference to raw file
      - anonymized biological context (for interpretation only)
      - last 6 medical reports rules (for cross-reference)
      - last 4 weeks workout summary
  → calls GPT-5.5 with:
      - the raw document (image or PDF)
      - the structured context
      - the prompt template (see §8)
  → receives structured JSON rules
  → POSTs callback to backend
```

---

## 7. Extraction Contract

The extraction result follows this strict contract. **No proposed rule can be
active from extraction alone.**

```json
{
  "result_type": "pulse.medical_document_extract",
  "summary": "short non-diagnostic summary",
  "confidence_score": 0.0,
  "risk_score": 0.0,
  "requires_user_validation": true,
  "recommended_next_action": "user_validate_medical_rules",
  "structured_result": {
    "document_type": "prescription|blood_test|imaging_report|certificate|physio_note|allergy_note|consultation_summary|other|unknown",
    "document_date": "YYYY-MM-DD or null",
    "issuer": "doctor/lab/clinic name or null",
    "extracted_facts": [
      {
        "label": "short factual item",
        "value": "verbatim or normalized value",
        "confidence": 0.0
      }
    ],
    "proposed_rules": [
      {
        "rule_type": "workout_limit|nutrition_constraint|fasting_caution|pain_watch|medication_note|general_context",
        "rule_text": "plain practical constraint",
        "source_quote": "short source excerpt or null",
        "severity": "info|warning|critical",
        "expires_at": "YYYY-MM-DD or null",
        "requires_user_validation": true
      }
    ]
  },
  "warnings": [],
  "model_notes": []
}
```

---

## 8. GPT-5.5 Prompt Template

```text
You are analyzing a medical document for a personal AI wellness system.

User profile (anonymized):
{age, sex, weight, height, activity_level (VTC driver, ~10h/day),
 known_conditions, current_medications, allergies}

Past 6 medical results context:
{summarized previous findings, current rules in effect}

Document type: {blood_test | prescription | medical_report | etc.}

Your task:
1. Extract all measurable values and their reference ranges.
2. Identify any values out of range or trending poorly.
3. Cross-reference with the user profile and past data.
4. Generate ACTIONABLE RULES that a downstream local model
   (Qwen) can apply daily for nutrition and training adjustments.
5. Flag anything that requires medical follow-up
   (you do not replace a doctor; surface the concern).

Output strict JSON per the extraction contract (§7).

Important constraints:
- DO NOT diagnose. DO NOT prescribe medication.
- DO NOT recommend stopping medication.
- ALWAYS surface medical concerns rather than hide them.
- Rules must be CONCRETE and APPLICABLE BY A LOCAL AI (Qwen).
- Avoid generic advice ("eat healthy"). Be specific
  (e.g. "increase iron intake to 18mg/day via red meat or supplements").
- French language for summary and user-facing text.
```

The full prompt template lives alongside other AI prompts in
`36_PROMPTS_CLOUD_AI.md`.

---

## 9. Rule Types And Examples

### 9.1 Nutrition rules

```json
{
  "rule_type": "nutrition_constraint",
  "condition": "always",
  "action": "Increase iron intake to 18mg/day. Sources: red meat 2x/week, lentils 3x/week, spinach daily.",
  "rationale": "Hemoglobin at 12.4 g/dL (low end of range). Trending down from 13.8 six months ago.",
  "severity": "warning",
  "expires_at": null
}
```

### 9.2 Training rules

```json
{
  "rule_type": "workout_limit",
  "condition": "post_workout",
  "action": "Limit cardio to zone 2 (HR < 145) for next 4 weeks. No HIIT.",
  "rationale": "Echocardiogram shows mild concentric remodeling. Recovery period recommended.",
  "severity": "critical",
  "expires_at": "2026-07-15"
}
```

### 9.3 Hydration rules

```json
{
  "rule_type": "nutrition_constraint",
  "condition": "always",
  "action": "Target 3.5L water per day. Track via Pulse hydration log.",
  "rationale": "Mild kidney function indicators (creatinine 105 µmol/L). Hydration support recommended.",
  "severity": "info",
  "expires_at": null
}
```

### 9.4 Recovery rules

```json
{
  "rule_type": "workout_limit",
  "condition": "evening",
  "action": "Sleep target 7.5h minimum. Avoid VTC sessions ending after 1am for next 4 weeks.",
  "rationale": "Cortisol pattern abnormal in saliva test. Sleep restoration prioritized.",
  "severity": "warning",
  "expires_at": "2026-07-15"
}
```

### 9.5 Flag rules (no action, surface concern)

```json
{
  "rule_type": "pain_watch",
  "condition": "next_doctor_visit",
  "action": "Discuss elevated LDL cholesterol (165 mg/dL) with your physician.",
  "rationale": "LDL above optimal range. Statin discussion may be warranted.",
  "severity": "warning"
}
```

---

## 10. Rule Activation, Deactivation, Revocation

### 10.1 Activation

```text
POST /api/pulse/medical-rules/{rule_id}/activate
Headers: Idempotency-Key
```

Activation requires:

- user reviewed the source document
- user confirmed the rule text
- user confirmed the rule is still relevant
- backend records source document id and consent version

After activation, backend emits `pulse.medical_rule.activated`. Imperium consumes
that event and may trigger replanning. Pulse only shows a handoff state such as
`Imperium replanning...`; **it does not rewrite missions**.

### 10.2 Deactivation and revocation

Users can deactivate a rule without deleting the source document.

When a source document is deleted:

- raw media is deleted or tombstoned according to storage capability
- extracted text is deleted unless required for an audit trail
- active rules from that document are revoked
- `pulse.medical_rule.deactivated` may be emitted for each active rule

### 10.3 Daily use of rules by Qwen

Once validated and stored in `pulse_medical_rules`, Qwen reads them when generating:

```text
- Daily meal suggestions (pulse.meal_suggestion task)
- Workout adjustments (pulse.training_adjustment task)
- Hydration reminders (deterministic backend rule)
- Energy score calculation (factors in active rules)
```

Example:

```text
User asks Pulse: "What should I eat for lunch?"

Qwen reads:
  active rules: [iron rule, hydration rule]
  user_meal_history: last 7 days
  current_stock: from kitchen inventory

Qwen produces:
  "Lentilles + épinards + œuf au plat. 600 cal, 22g protein.
   Apporte 4mg de fer pour ton objectif quotidien.
   N'oublie pas tes 3.5L d'eau aujourd'hui (déjà 1.2L)."
```

The rules are passively applied — the user doesn't have to remember them.

---

## 11. Retention

| Data | Retention V1 |
|---|---|
| Raw uploaded document | 90 days default, user can delete earlier. |
| Extracted raw text | 90 days default, deleted with document. |
| User-validated active rule | Until user deactivates or expiry date passes. |
| Audit metadata | Minimal metadata retained for integrity: ids, timestamps, consent version. |

Raw medical document retention must be visible in PUL-14 before upload.

---

## 12. Storage And Logging

### 12.1 Security rules

```text
- encrypt raw documents at rest
- never log document content, auth headers, cookies, or tokens
- redact AI prompt payloads in application logs
- store only summary in vector memory, never raw documents
- use parameterized SQL only
- all medical document endpoints require authentication
- no wildcard CORS with credentials
```

### 12.2 Tables

```sql
CREATE TABLE pulse_medical_documents (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  doc_type        VARCHAR(64) NOT NULL,
  doc_date        DATE NULL,
  storage_uri     TEXT NOT NULL,
  storage_hash    VARCHAR(64) NOT NULL,
  ai_task_id      UUID NULL REFERENCES ai_tasks(id),
  status          VARCHAR(32) NOT NULL DEFAULT 'pending_analysis',
  consent_version VARCHAR(32) NOT NULL,
  consented_at    TIMESTAMPTZ NOT NULL,
  retention_delete_after TIMESTAMPTZ NULL,
  uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  analyzed_at     TIMESTAMPTZ NULL
);

CREATE TABLE pulse_medical_rules (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  source_doc_id   UUID NULL REFERENCES pulse_medical_documents(id),
  source_result_id UUID NOT NULL REFERENCES ai_results(id),
  rule_type       VARCHAR(32) NOT NULL,
  condition       VARCHAR(64) NOT NULL,
  action          TEXT NOT NULL,
  rationale       TEXT NOT NULL,
  severity        VARCHAR(16) NOT NULL,
  duration_days   INTEGER NULL,
  status          VARCHAR(32) NOT NULL DEFAULT 'active',
  validated_at    TIMESTAMPTZ NOT NULL,
  expires_at      TIMESTAMPTZ NULL,
  superseded_by   UUID NULL REFERENCES pulse_medical_rules(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX pulse_medical_rules_active_idx
ON pulse_medical_rules (user_id, rule_type, status)
WHERE status = 'active';
```

### 12.3 Document storage (raw file)

```text
/var/lib/imperium/medical_documents/{user_id}/{document_uuid}.{ext}
encrypted at rest (LUKS or filesystem-level encryption)
```

Backups follow doc 22 backup execution layer.

---

## 13. UI Rules (V1)

PUL-14 (Medical tab) must show:

```text
- documents list with status
- extraction progress
- failed extraction retry
- active rules list
- rule source document
- expiry where present
- consent and retention copy before upload
- disclaimer: Pulse ne pose pas de diagnostic
```

PUL-01 may show a compact active medical rule banner only when at least one
validated active rule affects today's workout, meal, fasting, or mission plan.

V1 keeps it minimal. No graphs, no comparisons. Just: upload → review proposed
rules → validate.

---

## 14. Safety Language

Required wording:

```text
Pulse ne pose pas de diagnostic. Les informations médicales servent uniquement
à adapter tes routines et tes plans après ta validation.
```

The UI must not state that a medical condition is confirmed unless the user has
entered that fact, or the source document explicitly states it AND the user has
validated the extracted fact.

---

## 15. Edge Cases & Failure Modes

### 15.1 Critical concern detected

```text
If GPT-5.5 sets a proposed_rule severity = "critical":
  → backend pushes immediate notification to user
  → "Concern médical important détecté. Consulte ton médecin rapidement."
  → ai_result still stored normally
  → user must explicitly acknowledge before validating rules
```

### 15.2 Conflicting rules from different documents

```text
New rule conflicts with existing active rule:
  → backend marks existing rule as 'superseded_by' new rule
  → only new rule is active
  → audit trail preserved
```

### 15.3 Rule expiration

```text
Rule with expires_at set:
  → backend cron daily marks expired rules as 'expired'
  → Qwen no longer reads expired rules
  → user notified: "Règle expirée: {action}. Renouveler ?"
```

### 15.4 Failure modes table

| Failure | V1 behavior |
|---|---|
| Unsupported document | Error state, no extraction, user can retry. |
| Low OCR quality | Extraction may proceed but all rules require validation + Warning badge. |
| Model timeout | Status `failed`, retry available. |
| Ambiguous result | No active rule, display warning and require manual note. |
| User refuses consent | Return to PUL-14, no upload. |
| User rejects all rules | Document may remain stored, no `pulse.medical_rule.activated`. |

---

## 16. Privacy

### 16.1 What stays local (never sent to cloud)

```text
- Raw document files (analyzed via GPT-5.5 streaming, not stored at GPT)
- Medical history details
- Exact medication names (sent to GPT-5.5 but not retained)
```

### 16.2 What goes to GPT-5.5

```text
- The document content (necessary for analysis)
- Anonymized profile (age, sex, weight, activity level)
- Past rules summary (text summary, not raw test values)
```

### 16.3 GDPR considerations

- Medical documents are sensitive health data under RGPD article 9.
- Explicit consent required before each upload (§5).
- User can delete a document → cascade deletes rules and ai_task/ai_result.
- User can export all medical data via standard data export.
- Retention per §11 (90-day default on raw documents).

---

## 17. Out Of Scope V1

```text
❌ Automatic diagnosis
❌ Automatic treatment recommendation
❌ Medication dosage advice
❌ Emergency triage
❌ Sharing documents with third parties
❌ HDS-grade hosting claim unless infrastructure is formally certified
❌ Automatic activation of AI-derived rules
```

---

## 18. References

- `30_AI_ROUTING_AND_SCORING_POLICY.md` §6.4 (medical override → GPT-5.5)
- `31_AI_TASKS_AND_RESULTS_CONTRACT.md` (ai_tasks, ai_results, validation)
- `09_PGVECTOR_MEMORY_POLICY.md` (medical insights summary feeds pgvector)
- `10_RAW_MEDIA_RETENTION_POLICY.md` (raw document retention)
- `36_PROMPTS_CLOUD_AI.md` (sister doc with all model prompts)
- `40_PULSE_LOGIC_DETAIL.md` (Pulse general logic; medical is a separate flow)
- `59_DESIGN_SYSTEM_V1_DRAFT.md` (PUL-14 / PUL-01 screen design)

---

**Document version:** 2.0 (merged — operational detail + V1/RGPD guardrails)
**Status:** Pulse medical V1 reference
**Last updated:** 2026-06-06
