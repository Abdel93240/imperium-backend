# 34 - Pulse Medical Feed AI

## 1. Purpose

This document defines how Pulse handles medical documents (blood tests, prescriptions, medical reports) using GPT-5.5 to generate actionable rules consumable by Qwen for daily nutrition and training adjustments.

This is one of the high-value, low-frequency AI use cases in the system.

---

## 2. The Use Case In One Diagram

```text
User uploads medical document (PDF or image)
        ↓
Backend creates ai_task (pulse.medical_report.analyze)
        ↓
n8n claims task
        ↓
GPT-5.5 (omnimodal native) reads document + cross-references with:
  - anonymized biological context required for interpretation only
  - past workout history
  - past nutrition data
  - past medical reports
        ↓
GPT-5.5 produces structured rules JSON
        ↓
Backend stores ai_result (requires_user_validation = TRUE)
        ↓
User reviews + validates each rule
        ↓
Backend stores validated rules in pulse_medical_rules
        ↓
Qwen reads these rules daily to adjust:
  - meal suggestions
  - training intensity
  - hydration targets
  - recovery recommendations
```

---

## 3. Why GPT-5.5 (and not Opus)

Per doc 30 §6.4, medical analysis uses GPT-5.5 by static override.

Reasons:

```text
✅ Native omnimodal (PDF + image in one model)
✅ Output 72% more concise than Opus (better for rules consumption)
✅ Excellent grounded reasoning
✅ Explicit instruction following (rule format strict)
✅ Better at producing structured rules from medical content
```

Opus 4.7 is reserved for the WR analysis (deep reasoning across domains). GPT-5.5 is the right tool for medical-to-rules transformation.

---

## 4. Document Types Supported

```text
- Blood tests (numerical values + reference ranges)
- Prescription orders (medications + dosages + duration)
- Medical reports (cardiology, sports medicine, etc.)
- Imaging reports (echocardiogram, ultrasound text)
- Vaccination records
- Allergy panels
- Body composition analyses
```

Not supported in V1:

```text
- Raw imaging files (DICOM, MRI scans)
- Genetic test data
- Mental health records (privacy concern)
```

---

## 5. Trigger Flow

### 5.1 User uploads document

```text
Pulse app → "Add medical document" → camera or file picker
  → POST /api/pulse/medical-reports
    headers: Idempotency-Key
    body: multipart/form-data with PDF or image

Backend:
  → stores raw file in object storage (encrypted at rest)
  → creates ai_task (pulse.medical_report.analyze)
  → status = queued
  → POSTs signed webhook to n8n
  → returns task_id to UI

UI shows:
  "Document reçu. Analyse en cours..."
  Status banner with task progress.
```

### 5.2 n8n analysis

```text
n8n claims the task
  → fetches task context via internal API:
      - reference to raw file
      - anonymized biological context required for interpretation only (anonymized)
      - last 6 medical reports rules (for cross-reference)
      - last 4 weeks workout summary
  → calls GPT-5.5 with:
      - the raw document (image or PDF)
      - the structured context
      - the prompt template (see Section 6)
  → receives structured JSON rules
  → POSTs callback to backend
```

### 5.3 Backend stores result

```text
Backend validates the callback
  → stores ai_result (result_type = pulse.medical_rules)
  → result includes:
      raw_extraction: {} (what GPT-5.5 read from document)
      proposed_rules: [] (rules to apply)
      detected_concerns: [] (anomalies to flag to user)
      contraindications: [] (things to avoid)
      requires_user_validation = TRUE
  → notifies user: "Analyse prête, vérifie les règles"
```

### 5.4 User validation

```text
User opens Pulse → Medical Reports tab
  → sees the proposed rules with explanations
  → validates each rule individually:
      [Accepter] [Modifier] [Rejeter]
  → for accepted rules:
      → backend writes to pulse_medical_rules table (canonical)
      → existing rules conflicting with new ones marked superseded
```

---

## 6. GPT-5.5 Prompt Template

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

Rules format:
{
  "rule_id": "auto",
  "rule_type": "nutrition | training | hydration | recovery | flag",
  "condition": "always | morning | post_workout | evening | etc.",
  "action": "concrete instruction",
  "rationale": "why this rule, citing the document",
  "priority": "high | medium | low",
  "duration_days": null | number
}

Output strict JSON:
{
  "raw_extraction": { ... key values from document ... },
  "proposed_rules": [ ...rule objects... ],
  "detected_concerns": [ "concerns the user should discuss with doctor" ],
  "contraindications": [ "things to avoid based on this document" ],
  "summary": "one paragraph summary in French",
  "confidence": 0.0..1.0
}

Important constraints:
- DO NOT diagnose. DO NOT prescribe medication.
- DO NOT recommend stopping medication.
- ALWAYS surface medical concerns rather than hide them.
- Rules must be CONCRETE and APPLICABLE BY A LOCAL AI (Qwen).
- Avoid generic advice ("eat healthy"). Be specific
  (e.g. "increase iron intake to 18mg/day via red meat or supplements").
- French language for summary and user-facing text.
```

The full prompt template lives alongside other AI prompts in `36_PROMPTS_CLOUD_AI.md` (and similar files for GPT/Gemini).

---

## 7. Rule Types And Examples

### 7.1 Nutrition rules

```json
{
  "rule_type": "nutrition",
  "condition": "always",
  "action": "Increase iron intake to 18mg/day. Sources: red meat 2x/week, lentils 3x/week, spinach daily.",
  "rationale": "Hemoglobin at 12.4 g/dL (low end of range). Trending down from 13.8 six months ago.",
  "priority": "high",
  "duration_days": 90
}
```

### 7.2 Training rules

```json
{
  "rule_type": "training",
  "condition": "post_workout",
  "action": "Limit cardio to zone 2 (HR < 145) for next 4 weeks. No HIIT.",
  "rationale": "Echocardiogram shows mild concentric remodeling. Recovery period recommended.",
  "priority": "high",
  "duration_days": 30
}
```

### 7.3 Hydration rules

```json
{
  "rule_type": "hydration",
  "condition": "always",
  "action": "Target 3.5L water per day. Track via Pulse hydration log.",
  "rationale": "Mild kidney function indicators (creatinine 105 µmol/L). Hydration support recommended.",
  "priority": "medium",
  "duration_days": null
}
```

### 7.4 Recovery rules

```json
{
  "rule_type": "recovery",
  "condition": "evening",
  "action": "Sleep target 7.5h minimum. Avoid VTC sessions ending after 1am for next 4 weeks.",
  "rationale": "Cortisol pattern abnormal in saliva test. Sleep restoration prioritized.",
  "priority": "high",
  "duration_days": 30
}
```

### 7.5 Flag rules (no action, surface concern)

```json
{
  "rule_type": "flag",
  "condition": "next_doctor_visit",
  "action": "Discuss elevated LDL cholesterol (165 mg/dL) with your physician.",
  "rationale": "LDL above optimal range. Statin discussion may be warranted.",
  "priority": "medium"
}
```

---

## 8. Daily Use Of Rules By Qwen

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

## 9. Storage

### 9.1 New tables

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
  priority        VARCHAR(16) NOT NULL,
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

### 9.2 Document storage (raw file)

Raw files (PDF, images) stored in:

```text
/var/lib/imperium/medical_documents/{user_id}/{document_uuid}.{ext}
encrypted at rest (LUKS or filesystem-level encryption)
```

Backups follow doc 22 backup execution layer.

---

## 10. Privacy

### 10.1 What stays local (never sent to cloud)

```text
- Raw document files (analyzed via GPT-5.5 streaming, not stored at GPT)
- Medical history details
- Exact medication names (sent to GPT-5.5 but not retained)
```

### 10.2 What goes to GPT-5.5

```text
- The document content (necessary for analysis)
- Anonymized profile (age, sex, weight, activity level)
- Past rules summary (text summary, not raw test values)
```

### 10.3 GDPR considerations

- User can delete a document → cascade deletes rules and ai_task/ai_result
- User can export all medical data via standard data export
- Retention: documents kept indefinitely unless user deletes

---

## 11. Edge Cases

### 11.1 GPT-5.5 detects critical concern

```text
If GPT-5.5 sets concern.priority = "critical":
  → backend pushes immediate notification to user
  → "Concern médical important détecté. Consulte ton médecin rapidement."
  → ai_result still stored normally
  → user must explicitly acknowledge before validating rules
```

### 11.2 Conflicting rules from different documents

```text
New rule conflicts with existing active rule:
  → backend marks existing rule as 'superseded_by' new rule
  → only new rule is active
  → audit trail preserved
```

### 11.3 Rule expiration

```text
Rule with duration_days set:
  → backend cron daily marks expired rules as 'expired'
  → Qwen no longer reads expired rules
  → user notified: "Règle expirée: {action}. Renouveler ?"
```

### 11.4 Failed analysis

```text
GPT-5.5 fails or times out:
  → ai_task → status = failed
  → user can re-trigger from UI
  → no rules created until successful analysis
```

---

## 12. UI Surface (V1)

```text
Pulse app → Medical tab:
  ├─ "Add document" button
  ├─ List of past documents (sorted by date)
  ├─ List of active rules (grouped by type)
  ├─ Pending validation banner if new analysis ready
  └─ "Concern history" section (flagged items)
```

V1 keeps it minimal. No graphs, no comparisons. Just:

- upload
- review proposed rules
- validate

---

## 13. References

- `30_AI_ROUTING_AND_SCORING_POLICY.md` §6.4 (medical override → GPT-5.5)
- `31_AI_TASKS_AND_RESULTS_CONTRACT.md` (ai_tasks, ai_results, validation)
- `09_PGVECTOR_MEMORY_POLICY.md` (medical insights also feed pgvector)
- `10_RAW_MEDIA_RETENTION_POLICY.md` (raw document retention)
- `36_PROMPTS_CLOUD_AI.md` (sister doc with all model prompts)

---

**Document version:** 1.0
**Status:** Pulse medical V1 reference
**Last updated:** 2026-04-28
