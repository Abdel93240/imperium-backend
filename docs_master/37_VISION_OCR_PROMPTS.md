# 37 - Vision / OCR Prompts

## 1. Purpose

Canonical home for **vision / OCR prompts** (OCR, screenshot analysis, image-based extraction).

The concrete execution engine is defined in F10.

---

## 2. General Rules For Vision / OCR Prompts

### 2.1 Mandatory output contract

Every OCR service call returns the standard JSON contract (per doc 31 §19), with image-specific fields in `structured_result`.

### 2.2 No invention

```text
- Extract only what is visible in the image.
- If a field is unreadable, set value to null and add a warning.
- Never guess prices, dates, or numbers.
- Confidence score must reflect image clarity, not certainty in interpretation.
```

### 2.3 Image safety

```text
- Reject and flag if the image contains personal IDs (passport, license)
  unless the task explicitly requires ID extraction.
- Reject if image quality makes accurate extraction impossible.
- Privacy: image data is processed through the OCR service and redacted from logs.
```

## Exécution par moteur (local + fallback)

The OCR service is the canonical execution layer for every prompt in this file.

- Main engine: local OCR, defined concretely in F10. All OCR uses the local engine by default.
- Mandatory fallback: Gemini cloud, only if the local OCR tower is unavailable or down.
- Gemini fallback must return JSON via `responseSchema` and `response_mime_type: application/json` (structured output, Gemini 2.5+).
- Privacy gate is mandatory before any fallback to Gemini, because the data moves from local to cloud.
- For `very_high` content (medical or religious), the privacy gate must prefer abstention over fallback to Gemini.
- The fallback exists for continuity, never at the expense of confidentiality.

---

## 3. Receipt Extraction (Vault + Pulse)

Used for: `vault.receipt_extract` task.

### 3.1 System prompt

```text
You are a receipt parsing assistant.

Extract structured data from a French retail receipt photo.

Rules:
- Read everything visible. Do not invent.
- If a field is unreadable, set it to null and add a warning.
- Currency: EUR.
- Date format: YYYY-MM-DD.
- Detect line items with quantity, unit price, total.
- Identify the merchant (store name).
- Detect VAT breakdown if present.
```

### 3.2 User prompt template

```text
Image: <attached receipt photo>

Extract the receipt data.

Output JSON:
{
  "result_type": "vault.receipt_extract",
  "summary": "<merchant name + total + date in one line>",
  "confidence_score": <0.0-1.0>,
  "risk_score": 0.0,
  "requires_user_validation": true,
  "recommended_next_action": "user_validate_transaction",
  "structured_result": {
    "merchant": {
      "name": "<store name or null>",
      "address": "<address or null>",
      "siret": "<SIRET if visible or null>"
    },
    "transaction": {
      "date": "YYYY-MM-DD",
      "time": "HH:MM",
      "total_eur": <decimal>,
      "payment_method": "card|cash|other|unknown",
      "vat_breakdown": [
        {
          "rate_percent": <decimal>,
          "amount_eur": <decimal>
        }
      ]
    },
    "line_items": [
      {
        "description": "<item name>",
        "quantity": <decimal>,
        "unit_price_eur": <decimal>,
        "total_eur": <decimal>,
        "category_hint": "food|drink|household|fuel|other|unknown"
      }
    ],
    "image_quality": "good|acceptable|poor"
  },
  "warnings": [
    "<list any field that was unclear>"
  ],
  "model_notes": []
}

Output strict JSON only.
```

### 3.3 Post-processing

After the OCR service returns, the backend:

1. Validates the JSON structure
2. Stores raw result in `ai_results`
3. Creates a draft `vault_transactions` row with `status = pending_user_validation`
4. If items are food-related (`category_hint = food`), creates draft updates to `pulse_food_stock`
5. UI shows the draft for user approval

The user always validates before any canonical write.

---

## 4. Bolt Screenshot Extraction (Vector V2)

Used for: `vector.bolt_screenshot_parse` task.

> Note: Bolt overlay is V2 (per doc 33 §15). Prompt documented now for completeness.

### 4.1 System prompt

```text
You are parsing a screenshot of a Bolt driver app ride offer.

Extract:
- pickup location (address or zone name)
- destination location (address or zone name)
- ride price in EUR (NET to driver, excluding tolls)
- toll fees in EUR (péages, paid by passenger, NO benefit to driver)
- distance in km
- estimated duration in minutes
- ride type (standard, comfort, etc.)

Rules:
- Bolt UI is in French.
- Distances may be in km or m.
- Prices may include or exclude commission.

CRITICAL — Toll detection:
- Bolt may show TWO price components on certain rides:
  1. Ride fare (revenue for the driver)
  2. Toll fees (péage, paid by passenger, ZERO benefit to driver)
- The TOLL portion must be reported separately in `toll_eur`.
- The TOLL must NOT be included in `price_eur`.
- If you mistakenly include the toll in price_eur, downstream Vector
  will treat the ride as more profitable than it actually is.
  This is a FALSE POSITIVE that hurts the driver.
- Common toll labels in Bolt French UI:
  "péage", "frais de péage", "tolls", "péages inclus"
- If you cannot tell whether a price segment is toll or ride fare,
  set toll_eur = null and add a warning. Do not guess.

Do not invent. If unclear, set null.
```

### 4.2 User prompt template

```text
Image: <Bolt screenshot>

Extract the ride offer.

Output JSON:
{
  "result_type": "vector.bolt_screenshot_parse",
  "summary": "<short description of the offer>",
  "confidence_score": <0.0-1.0>,
  "risk_score": 0.0,
  "requires_user_validation": false,
  "recommended_next_action": "score_overlay_decision",
  "structured_result": {
    "pickup": {
      "raw_text": "<as displayed>",
      "zone_hint": "<zone name if recognizable>"
    },
    "destination": {
      "raw_text": "<as displayed>",
      "zone_hint": "<zone name if recognizable>"
    },
    "price_eur": <decimal>,
    "toll_eur": <decimal or null>,
    "price_eur_is_net_of_toll": <bool>,
    "distance_km": <decimal>,
    "estimated_duration_min": <int>,
    "ride_type": "standard|comfort|xl|other|unknown",
    "image_quality": "good|acceptable|poor"
  },
  "warnings": [],
  "model_notes": []
}

Output strict JSON only.

Reminder: price_eur must be NET of tolls. The toll, if any, goes
in toll_eur as a separate value. If you set price_eur_is_net_of_toll
to false, Vector will reject the result and ask for re-extraction.
```

---

## 5. Food Inventory Photo (Pulse)

Used for: `pulse.kitchen_inventory_photo` task.

### 5.1 System prompt

```text
You are identifying food items visible in a photo of a fridge,
cupboard, or pantry.

Goal: produce a list of items with estimated quantities so the
backend can update kitchen stock.

Rules:
- List only items you can clearly identify.
- Do not guess if items are hidden or blurry.
- For each item, estimate quantity if possible (e.g. 6 eggs, 2 tomatoes).
- Suggest a category (vegetable, fruit, dairy, meat, dry, condiment, drink).
- French language for item names.
- Detect expiry dates if visible.
```

### 5.2 User prompt template

```text
Image: <photo of fridge/pantry>

Identify visible food items.

Output JSON:
{
  "result_type": "pulse.kitchen_inventory_photo",
  "summary": "<short overview of what's in the photo>",
  "confidence_score": <0.0-1.0>,
  "risk_score": 0.0,
  "requires_user_validation": true,
  "recommended_next_action": "user_validate_inventory_diff",
  "structured_result": {
    "items": [
      {
        "name_fr": "<item name in French>",
        "category": "vegetable|fruit|dairy|meat|fish|dry|condiment|drink|other",
        "estimated_quantity": <decimal or null>,
        "unit": "piece|g|kg|ml|l|null",
        "expiry_visible": "YYYY-MM-DD or null",
        "confidence": <0.0-1.0>
      }
    ],
    "items_count": <int>,
    "image_quality": "good|acceptable|poor"
  },
  "warnings": [
    "<items that were possibly there but unclear>"
  ],
  "model_notes": []
}

Output strict JSON only.
```

### 5.3 Meal Photo Macros (Pulse)

Used for: `pulse.meal_photo_macros` task.

This task estimates visible meal macros from a plate photo. It is always a draft
and always requires user validation in PUL-03 before any meal log or stock
decrement is canonical.

```text
You are estimating nutrition from a visible meal photo for a personal food log.

Rules:
- Identify only visible food items.
- Do not invent hidden ingredients.
- If portion size is unclear, lower confidence and add a warning.
- Return calories, protein_g, carbs_g, fat_g as estimates.
- Never present the result as medical advice.
- User validation is mandatory.
```

```text
Image: <meal photo>

Estimate the meal macros.

Output JSON:
{
  "result_type": "pulse.meal_photo_macros",
  "summary": "<short French description of visible meal>",
  "confidence_score": <0.0-1.0>,
  "risk_score": 0.0,
  "requires_user_validation": true,
  "recommended_next_action": "user_validate_meal_macros",
  "structured_result": {
    "detected_foods": [
      {
        "name_fr": "<food name>",
        "estimated_quantity": <decimal or null>,
        "unit": "g|ml|piece|portion|null",
        "confidence": <0.0-1.0>
      }
    ],
    "macros": {
      "calories": <decimal or null>,
      "protein_g": <decimal or null>,
      "carbs_g": <decimal or null>,
      "fat_g": <decimal or null>
    },
    "image_quality": "good|acceptable|poor"
  },
  "warnings": [
    "<portion ambiguity, hidden ingredient, poor lighting, or low confidence>"
  ],
  "model_notes": []
}

Output strict JSON only.
```

---

## 6. General Document OCR

Used for: `media.image_ocr` task when no specific extractor matches.

### 6.1 User prompt template

```text
Image: <document photo>

Extract all readable text from this image.
Preserve structure (headers, sections, lists) where possible.

Output JSON:
{
  "result_type": "media.image_ocr",
  "summary": "<short description of document type>",
  "confidence_score": <0.0-1.0>,
  "risk_score": 0.0,
  "requires_user_validation": false,
  "recommended_next_action": "none",
  "structured_result": {
    "document_type_hint": "receipt|invoice|letter|notice|form|other|unknown",
    "raw_text": "<full extracted text>",
    "structured_blocks": [
      {
        "block_type": "header|paragraph|list|table|signature|other",
        "text": "<block content>"
      }
    ],
    "language_detected": "fr|en|other",
    "image_quality": "good|acceptable|poor"
  },
  "warnings": [],
  "model_notes": []
}

Output strict JSON only.
```

---

## 7. ID Document Detection (safety check)

Triggered automatically before any other vision task to detect sensitive ID documents.

### 7.1 User prompt template

```text
Image: <photo>

Check if this image contains personal identification documents
that should be handled carefully:
- passport
- driver's license (carte grise, permis de conduire)
- ID card (carte d'identité)
- residence permit (titre de séjour)
- credit card (full number visible)
- social security card

Output JSON:
{
  "result_type": "media.id_document_check",
  "summary": "<one-sentence assessment>",
  "confidence_score": <0.0-1.0>,
  "risk_score": <0.0-1.0>,
  "requires_user_validation": false,
  "recommended_next_action": "block|warn|proceed",
  "structured_result": {
    "contains_id_document": <bool>,
    "document_types": ["<list of detected ID types>"],
    "should_block_processing": <bool>,
    "should_warn_user": <bool>
  },
  "warnings": [],
  "model_notes": []
}

Rules:
- If a clear ID document is detected:
    contains_id_document = true
    should_warn_user = true
    risk_score >= 0.7
- If credit card with full number visible:
    contains_id_document = true
    should_block_processing = true
    risk_score = 1.0

Output strict JSON only.
```

If `should_block_processing = true`, the backend rejects the upload entirely.
If `should_warn_user = true`, the user must explicitly confirm before processing continues.

---

## 8. Cost And Performance Notes (Gemini fallback only)

### 8.1 Cost estimation

```text
Gemini fallback per image (typical):
  Input:    ~$0.0003 per image
  Output:   ~$0.001 per image
  Total:    ~$0.0013 per image
```

Local OCR primary path:

```text
0 € for the local OCR engine
```

For ~50 receipt scans / month through Gemini fallback:

```text
Monthly cost: ~$0.07 (~0.06 €)
```

### 8.2 Latency

```text
Typical Gemini fallback response time: 2-5 seconds
For real-time Bolt overlay (V2): may need to use Gemini Flash variant
```

---

## 9. Image Storage And Retention

### 9.1 Where images live

```text
/var/lib/imperium/media/{user_id}/{uuid}.{ext}
```

Encrypted at rest. Backed up per doc 22.

### 9.2 What stays in ai_results

```text
ai_results.metadata.image_hash       (SHA-256 of image bytes)
ai_results.metadata.image_size_bytes
ai_results.metadata.image_storage_uri
```

The image binary is NOT stored in `ai_results` (too large). Only references.

### 9.3 Retention

```text
Receipts:               keep indefinitely (user can delete)
Bolt screenshots:       30 days max
Food inventory photos:  7 days max (then deleted)
ID document checks:     never store images, only result
Generic OCR:            user-configurable, default 90 days
```

Per doc 10 (raw media retention policy).

---

## 10. Error Handling

### 10.1 Image too low quality

```text
The OCR service returns image_quality: "poor"
Backend stores result but flags it
UI prompts user: "Photo trop floue. Reprendre une photo ?"
```

### 10.2 No content detected

```text
The OCR service returns empty fields
Confidence < 0.3
Backend stores result, UI shows: "Aucun contenu détecté."
User can retry with another photo.
```

### 10.3 Wrong document type

```text
e.g. user uploads a Bolt screenshot to receipt extractor
The OCR service detects mismatch (low merchant confidence, no line items)
Backend flags: "Ceci ne ressemble pas à un ticket. Bon document ?"
User confirms or cancels.
```

---

## 11. Versioning

Same approach as doc 36 §12:

```text
backend/app/services/ai/prompts/
├─ ocr_receipt.txt
├─ ocr_bolt_screenshot.txt
├─ ocr_kitchen_inventory.txt
├─ ocr_meal_photo_macros.txt
├─ ocr_generic.txt
└─ ocr_id_check.txt
```

Header on each:

```text
# Prompt: ocr_receipt
# Version: 1.0
# Last updated: 2026-06-22
# Doc reference: 37_VISION_OCR_PROMPTS.md §3
```

---

## 12. References

- `30_AI_ROUTING_AND_SCORING_POLICY.md` §6.1 — vision override
- `31_AI_TASKS_AND_RESULTS_CONTRACT.md` §19 — output contract
- `33_VECTOR_LOGIC_DETAIL.md` §5.2 — Bolt overlay V2
- `34_PULSE_MEDICAL_FEED_AI.md` — medical (uses GPT-5.5, not the OCR service, by static override)
- `10_RAW_MEDIA_RETENTION_POLICY.md` — media retention
- `36_PROMPTS_CLOUD_AI.md` — sister prompts file

---

**Document version:** 1.1
**Status:** Vision / OCR reference
**Last updated:** 2026-06-22
