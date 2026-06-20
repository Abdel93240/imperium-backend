# 10 - Raw Media Retention Policy

## Purpose

This document defines the retention policy for all raw media handled by the ecosystem.

Core principle:

> Raw media is the source of truth. Processed output (OCR, transcription) is a lossy, error-prone derived view. The raw is kept by default so the truth can always be re-checked.

Default rule:

> Keep raw media by default when it is CONTENT (documents, content audio, images with intrinsic value). Deletion is an explicit user decision with a mandatory reason. EXCEPTION: raw audio used only as INPUT (voice command/chatbot dictation) is deleted after successful transcription — it is transport, not content.

Summaries and structured records are preferred over raw storage.

## Global Rules

1. Raw media must not be kept forever by accident.
2. Every media file must have a retention policy.
3. Every media file must have an expiration or explicit retention reason.
4. Raw media is kept by default. Deletion is an explicit user decision with a mandatory reason (except input-only audio, deleted after transcription).
5. Failed extraction may allow temporary debug retention with expiry.
6. Manual user delete must be a real feature.
7. Backups must respect deletion and retention policy where possible.
8. External provider usage must pass the privacy gate.

## Media Types

Canonical `media_type` values:
- `audio`
- `bolt_screenshot`
- `receipt_photo`
- `document`
- `health_media`
- `religious_private_media`
- `food_image`
- `other`

Canonical extraction statuses:
- `pending`
- `processing`
- `completed`
- `failed`
- `low_confidence`
- `not_required`

Canonical retention reasons:
- `temporary_processing`
- `retry_debug`
- `user_archive`
- `proof_required`
- `reference_document`
- `audit_flagged`
- `manual_keep`
- `delete_after_extraction`

## Media Tables

### `media_files`

Purpose:
- Stores raw media metadata and retention state.

Required fields:
- `media_id`
- `user_id`
- `source_app`
- `media_type`
- `storage_path`
- `uploaded_at`
- `expires_at`
- `delete_after_extraction`
- `retention_reason`
- `privacy_level`
- `extraction_status`
- `external_provider_used`

Columns:
- `media_id` uuid primary key
- `user_id` foreign key to `users.id` not null
- `source_app` source_app not null
- `media_type` text not null
- `storage_path` text not null
- `file_name` text nullable
- `mime_type` text nullable
- `size_bytes` bigint nullable
- `uploaded_at` timestamptz not null
- `expires_at` timestamptz nullable
- `delete_after_extraction` boolean not null default true
- `retention_reason` text not null
- `privacy_level` privacy_level not null
- `extraction_status` text not null
- `extraction_confidence` numeric nullable
- `extracted_summary` text nullable
- `external_provider_used` boolean not null default false
- `provider_name` text nullable
- `deleted_at` timestamptz nullable
- `delete_requested_at` timestamptz nullable
- `created_at` timestamptz not null
- `updated_at` timestamptz not null

Indexes:
- index on `(user_id, media_type, uploaded_at)`
- index on `(user_id, privacy_level, uploaded_at)`
- index on `expires_at`
- index on `deleted_at`

Rules:
- `expires_at` is required unless `retention_reason` is `user_archive`, `proof_required`, or `reference_document`.
- If `delete_after_extraction = true`, cleanup should delete raw media after successful extraction.
- `deleted_at` means raw media is deleted or inaccessible from normal storage.

### `media_extractions`

Purpose:
- Stores structured extraction result, transcript, OCR output, and summaries.

Required fields:
- `extraction_id`
- `media_id`
- `user_id`
- `extraction_type`
- `extraction_status`
- `extraction_confidence`
- `extracted_summary`
- `external_provider_used`
- `provider_name` if any
- `created_at`

Columns:
- `extraction_id` uuid primary key
- `media_id` foreign key to `media_files.media_id` not null
- `user_id` foreign key to `users.id` not null
- `extraction_type` text not null
- `extraction_status` text not null
- `extraction_confidence` numeric nullable
- `extracted_payload` jsonb nullable
- `extracted_summary` text nullable
- `raw_text` text nullable
- `external_provider_used` boolean not null default false
- `provider_name` text nullable
- `privacy_level` privacy_level not null
- `created_at` timestamptz not null

Indexes:
- index on `(user_id, created_at)`
- index on `(media_id)`
- index on `(extraction_status, created_at)`

Rules:
- Prefer `extracted_payload` and `extracted_summary` over keeping raw media.
- `raw_text` may still be sensitive and must follow privacy/retention policy.

## Audio Policy

Examples:
- voice commands while driving
- Imperium voice notes
- reminders
- quick spoken expense declarations

Policy:
- INPUT audio (voice command, chatbot dictation, quick spoken declaration): transport,
  not content. Delete raw audio after successful transcription. No user question.
- CONTENT audio (recorded lesson, voice note with intrinsic value): kept by default
  (raw = source of truth), via the normal upload flow (doc 70) with the "keep raw?"
  question defaulting to KEEP.
- Failed transcription (either role) may keep temporary audio for retry/debug with expiration.

Default:
- `delete_after_extraction = true`
- `retention_reason = temporary_processing`
- `expires_at` required

Store after successful transcription:
- transcript if useful and allowed
- structured event/action result
- confidence
- language if detected
- created transaction/mission/replanning event if applicable

Do not store by default:
- raw audio forever
- private raw voice note if a summary is enough

## Bolt Screenshot Policy

Examples:
- ride offers
- revenue screenshots
- zone analysis
- session review

Policy:
- keep OCR extraction and structured VTC event
- raw screenshot should be deleted after successful extraction unless flagged for audit
- never keep unnecessary screenshot history forever

Default:
- `delete_after_extraction = true`
- `retention_reason = delete_after_extraction`
- `privacy_level = very_high`

Allowed retention reasons:
- `audit_flagged`
- `retry_debug`
- `manual_keep`

Do not store by default:
- long-term raw Bolt screenshots
- full screenshot history
- screenshots unrelated to explicit Vector workflow

Compliance:
- raw screenshot retention must not enable illegal or platform-breaking automation.
- Vector remains decision support only.

## Receipts / Finance Photos Policy

Examples:
- fuel receipt
- expense proof
- maintenance proof

Policy:
- if user wants proof retention, keep securely
- otherwise keep extraction and summary only
- support `proof_required` flag per expense

Default:
- keep structured transaction fields
- keep merchant/category/amount/date/location clue when useful
- delete raw image after successful extraction unless proof required

When `proof_required = true`:
- `delete_after_extraction = false`
- `retention_reason = proof_required`
- `privacy_level = high` or `very_high`
- backup must be encrypted

Do not store by default:
- every raw receipt forever
- raw OCR text if summary and transaction fields are enough

## Documents Policy

Examples:
- contracts
- insurance docs
- invoices
- school payment docs

Policy:
- allow secure long-term retention if explicitly marked as reference documents
- otherwise summarize and apply clear archive/expiration policy

Reference document behavior:
- `delete_after_extraction = false`
- `retention_reason = reference_document`
- document may be chunked/summarized for memory if allowed
- pgvector memory should store summaries/chunks according to privacy policy

Temporary document behavior:
- summarize/extract
- set `expires_at`
- delete raw file after extraction or expiry

Do not store by default:
- sensitive document raw files without explicit reference/archive decision

## Health Media Policy

Examples:
- body progress photo
- food image
- supplement label

Policy:
- stricter privacy handling
- external provider usage must be controlled
- raw kept by default (source of truth); summary is ADDED, not a replacement

Default:
- privacy_level = high or very_high
- local/private handling preferred (local OCR, no cloud for sensitive)
- external provider requires privacy gate approval
- raw file KEPT by default; deletion is an explicit user decision with mandatory reason

Allowed extracted information:
- food estimate
- supplement label summary
- progress note if user explicitly stores it

Do not store by default:
- raw body progress photos
- raw health-sensitive notes
- sensitive images in vector memory

## Religious / Private Media Policy

Examples:
- personal worship notes
- spiritual reminders
- private reflections

Policy:
- default local/private handling only
- no automatic external provider sending
- no unnecessary retention

Default:
- `privacy_level = very_high`
- external provider blocked unless explicit permission is given
- summarize only if useful and allowed
- raw media expires or is deleted after processing

Do not store by default:
- raw private reflections
- raw religious private states
- raw worship notes

Never infer:
- prayer completion
- fasting intention
- ghusl state
- Quran completion
- adhkar completion
- sadaqa completion

## Deletion Policy

Supported deletion modes:
- automatic expiry
- manual delete by user
- forced delete after extraction
- audit-safe retention if explicitly required

### Automatic expiry

Use when:
- media is temporary
- extraction failed and retry/debug window is allowed
- no explicit archive/proof/reference reason exists

Required:
- `expires_at`
- cleanup job

### Manual delete by user

User must be able to delete raw media.

Manual delete should:
- require a MANDATORY reason via a dropdown of preset codes (deletion_reason_code:
  non_pertinent | doublon | trop_lourd | autre | ...). "autre" opens a free-text
  deletion_reason_text. The reason list is OPEN (extensible; a recurring "autre"
  is promoted to a code). deletion_reason_code is structured/exploitable by the WR.
- mark `delete_requested_at`
- delete raw file from normal storage
- set `deleted_at`
- preserve structured extracted result only if allowed
- avoid breaking canonical financial/mission/worship records

### Forced delete after extraction

Use when:
- `delete_after_extraction = true`
- extraction status is `completed`
- no proof/archive/audit flag exists

Behavior:
- delete raw file
- keep structured extraction
- keep event trace

### Audit-safe retention

Use only when explicitly required:
- proof required
- user archive
- reference document
- audit flagged

Audit-safe does not mean forever by accident. It must still have:
- explicit reason
- privacy level
- encrypted backup
- manual delete path unless legally/operationally blocked

## Privacy Gate

Before sending raw media to:
- Gemini
- GPT
- Claude
- OCR provider
- external AI provider

Check:
- `privacy_level`
- user settings
- media type
- explicit permission if required

Default behavior:
- low/medium privacy: external provider allowed if useful and user setting allows
- high privacy: minimize payload, prefer local processing, require stronger justification
- very_high privacy: block external provider unless explicitly allowed for that workflow

Provider usage must be stored:
- `external_provider_used`
- `provider_name`
- privacy gate decision

## Debug Retention

Temporary debug retention may exist for:
- failed OCR
- failed STT
- low confidence extraction

But it must include:
- expiration
- cleanup job
- no permanent silent retention

Rules:
- `retention_reason = retry_debug`
- `expires_at` required
- debug files must not enter long-term memory
- debug retention must be visible in admin/debug views later

## Backups

If raw media is backed up:
- backup must be encrypted
- retention must respect deletion policy
- deletion must propagate to backup policy where possible

Required backup decisions:
- backup provider: TODO
- backup encryption key management: TODO
- backup retention duration: TODO
- delete propagation behavior: TODO
- restore process: TODO

Rule:
- A deleted raw media file must not silently remain available forever through backups.

## Non-Negotiable Rules

- never keep raw media forever by accident
- summaries are preferred over raw storage
- explicit retention beats implicit retention
- privacy first
- deletion must be a real feature, not a promise
- raw media must have a retention reason
- temporary media must have `expires_at`
- external provider usage must be recorded
- high/very_high privacy media requires strict handling

## Required Examples

### Successful Bolt screenshot OCR

Flow:
1. Vector receives ride offer screenshot.
2. Media row created:
   - `media_type = bolt_screenshot`
   - `privacy_level = very_high`
   - `delete_after_extraction = true`
   - `retention_reason = delete_after_extraction`
3. Gemini or approved OCR provider extracts ride fields after privacy gate approval.
4. Backend stores structured VTC event and extraction confidence.
5. Raw screenshot is deleted after successful extraction.
6. Structured extraction remains.

Stored:
- price
- pickup distance
- estimated time
- destination zone
- extraction confidence
- recommendation result

Deleted:
- raw screenshot unless explicitly audit-flagged

### Failed voice transcription retry

Flow:
1. User records voice expense while driving.
2. STT fails or confidence is too low.
3. Raw audio is kept temporarily for retry/debug.
4. Media row has:
   - `media_type = audio`
   - `retention_reason = retry_debug`
   - `expires_at` set
   - `extraction_status = failed` or `low_confidence`
5. Cleanup job deletes raw audio after expiration.

Stored long-term only if successful later:
- transcript if allowed
- structured transaction or command result
- confidence

Not allowed:
- permanent silent raw audio retention

### Fuel receipt with proof retention

Flow:
1. User scans fuel receipt.
2. OCR extracts transaction fields.
3. User marks expense as proof required.
4. Media row has:
   - `media_type = receipt_photo`
   - `privacy_level = high`
   - `delete_after_extraction = false`
   - `retention_reason = proof_required`
5. Raw image is stored securely.
6. Backup is encrypted.
7. User can manually delete proof later if desired.

Stored:
- raw receipt photo
- structured transaction
- OCR extraction
- proof flag

### Private religious note handled locally

Flow:
1. User records a private religious note.
2. Backend marks media:
   - `media_type = religious_private_media`
   - `privacy_level = very_high`
3. External provider is blocked by default.
4. Local/private handling is used if processing is needed.
5. Raw media is deleted after summary or expires.
6. No unnecessary pgvector memory is created.

Stored:
- optional local summary if user allows
- structured reminder/action if explicitly requested

Not stored:
- raw private note forever
- external provider payload
- inferred worship state

