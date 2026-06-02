# 34 - Pulse Medical Feed AI

## 1. Purpose

This document defines the V1 policy for medical document handling in Pulse.

Pulse can store user-provided medical context and extract practical constraints
for planning, but it is not a medical authority. The system must not diagnose,
prescribe, or silently activate health rules.

Medical documents are sensitive health data under RGPD article 9. V1 requires
explicit consent before upload and explicit user validation before any derived
rule becomes active.

Canonical safety shorthand: no diagnosis, no prescription, user validation before activation, no automatic rule activation.

## 2. Model Routing

Medical extraction uses a GPT-5.5 static override.

```text
task: pulse.medical_document_extract
model_override: GPT-5.5 static override
reason: medical document reasoning and safety
gemini: not used except generic image/PDF OCR pre-extraction when required
qwen: may classify routing metadata only, never final medical content
```

Gemini may extract raw visible text from a scanned image if needed, but medical
interpretation and rule drafting are routed to GPT-5.5 static override.

## 3. Accepted V1 Documents

Allowed document types:

- prescription
- blood test result
- imaging report summary
- medical certificate
- physiotherapy or sports limitation note
- allergy or intolerance note
- discharge or consultation summary
- other user-confirmed medical document

Rejected or warning types:

- identity-only documents without medical content
- unreadable image/PDF
- third-party document not belonging to the user
- document containing another person's medical data

## 4. Consent Gate

Before upload, PUL-14 must show a consent gate with:

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

No consent means no upload.

## 5. Extraction Contract

Endpoint:

```text
TBD POST /api/pulse/medical-documents
Headers: Idempotency-Key
```

Backend creates a document record:

| Field | Rule |
|---|---|
| `medical_document_id` | Backend generated. |
| `document_type` | User selected or AI suggested, user editable. |
| `status` | `uploaded|extracting|needs_validation|validated|failed|deleted`. |
| `raw_storage_uri` | Encrypted storage reference, never shown in logs. |
| `retention_delete_after` | Defaults from §8. |
| `extraction_task_id` | AI task reference. |
| `confidence` | Model confidence for extraction quality. |
| `warnings` | Missing pages, low OCR quality, ambiguous medical terms. |

Extraction result:

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

No proposed rule can be active from extraction alone.

## 6. Rule Activation

Endpoint:

```text
TBD POST /api/pulse/medical-rules/{rule_id}/activate
Headers: Idempotency-Key
```

Activation requires:

- user reviewed the source document
- user confirmed the rule text
- user confirmed the rule is still relevant
- backend records source document id and consent version

After activation, backend emits:

```text
pulse.medical_rule.activated
```

Imperium consumes that event and may trigger replanning. Pulse only shows a
handoff state such as `Imperium replanning...`; it does not rewrite missions.

## 7. Deactivation And Revocation

Users can deactivate a rule without deleting the source document.

Users can delete the source document. When a source document is deleted:

- raw media is deleted or tombstoned according to storage capability
- extracted text is deleted unless required for an audit trail
- active rules from that document are revoked
- `pulse.medical_rule.deactivated` may be emitted for each active rule

## 8. Retention

Default raw medical document retention:

| Data | Retention V1 |
|---|---|
| Raw uploaded document | 90 days default, user can delete earlier. |
| Extracted raw text | 90 days default, deleted with document. |
| User-validated active rule | Until user deactivates or expiry date passes. |
| Audit metadata | Minimal metadata retained for integrity: ids, timestamps, consent version. |

Raw medical document retention must be visible in PUL-14 before upload.

## 9. Storage And Logging

Security rules:

- encrypt raw documents at rest
- never log document content, auth headers, cookies, or tokens
- redact AI prompt payloads in application logs
- store only summary in vector memory, never raw documents
- use parameterized SQL only
- all medical document endpoints require authentication
- no wildcard CORS with credentials

## 10. UI Rules

PUL-14 must show:

- documents list with status
- extraction progress
- failed extraction retry
- active rules list
- rule source document
- expiry where present
- consent and retention copy before upload
- disclaimer: Pulse ne pose pas de diagnostic

PUL-01 may show a compact active medical rule banner only when at least one
validated active rule affects today's workout, meal, fasting, or mission plan.

## 11. Safety Language

Required wording:

```text
Pulse ne pose pas de diagnostic. Les informations medicales servent uniquement
a adapter tes routines et tes plans apres ta validation.
```

The UI must not state that a medical condition is confirmed unless the user has
entered that fact or the source document explicitly states it and the user has
validated the extracted fact.

## 12. Failure Modes

| Failure | V1 behavior |
|---|---|
| Unsupported document | Error state, no extraction, user can retry. |
| Low OCR quality | Extraction may proceed but all rules require validation and Warning badge. |
| Model timeout | Status `failed`, retry available. |
| Ambiguous result | No active rule, display warning and require manual note. |
| User refuses consent | Return to PUL-14, no upload. |
| User rejects all rules | Document may remain stored, no `pulse.medical_rule.activated`. |

## 13. Out Of Scope V1

- automatic diagnosis
- automatic treatment recommendation
- medication dosage advice
- emergency triage
- sharing documents with third parties
- HDS-grade hosting claim unless infrastructure is formally certified
- automatic activation of AI-derived rules
