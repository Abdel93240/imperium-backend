# 56 - Autonomous Coding Orchestrator

> ⚠️ **DEV INFRASTRUCTURE — used to BUILD the OS, not part of the OS itself.**
> This document describes the orchestrator that automates the
> ChatGPT ↔ Codex ↔ VPS pipeline, freeing the user from manual
> copy-paste during the implementation of V1-V5.

---

## 1. Purpose

Build a **personal autonomous coding pipeline** that:

- Reads instructions from ChatGPT (web interface, no API)
- Routes prompts to Codex using the appropriate model (mini/5.4/5.5)
- Uploads code to VPS via SSH
- Executes tests automatically
- Reports results back to ChatGPT
- Escalates to user via Telegram when judgment needed

The user supervises remotely. The orchestrator does the mechanical work.

---

## 2. Why This Exists

```text
THE REAL PROBLEM:

Coding V1-V5 of the personal OS = ~6-9 months of work.
The user's actual time spent is split:

- 10% writing prompts (intelligent work)
- 70% copy-paste between ChatGPT, Codex, VPS terminal
- 15% running tests and pasting results back
- 5% real debugging requiring judgment

= 85% of the time is mechanical pipeline work.

This time is currently ALREADY DELEGATED to ChatGPT
(ChatGPT writes the prompts, decides what to do next, etc.).
The user is just a human pipeline.

THE ORCHESTRATOR REMOVES THE HUMAN PIPELINE.
```

---

## 3. Cost-Benefit Analysis

```text
WITHOUT ORCHESTRATOR (manual workflow):
├─ User effectively works ~2-3h/day (Codex Plus limit)
├─ V1 timeline: ~8 months
├─ User exhaustion: high
├─ Mobility: zero (must be at PC)
└─ Cost: ChatGPT Plus 23€/month × 8 = ~185€

WITH ORCHESTRATOR (this document):
├─ Pipeline runs autonomously during Codex windows
├─ User reviews via Telegram on the go
├─ V1 timeline: ~3-4 months
├─ User exhaustion: low
├─ Mobility: full
└─ Cost: ChatGPT Plus + electricity = ~140€ total

GAIN: 4-5 months of user time
HARDWARE COST: 0€ (uses existing equipment)
SETUP COST: 3-4 weeks of dev work
```

---

## 4. Architecture Overview

### 4.1 The three-tier hardware setup

```text
TIER 1 — THE HORSE (home tower)
├─ Existing: i7-4790, 16 GB RAM, SSD, GTX 970
├─ OS: Ubuntu Server 24.04 LTS (no desktop)
├─ Role: runs the orchestrator 24/7
├─ Stays at home, always powered
├─ Accessed only via SSH
└─ ZERO purchase cost

TIER 2 — THE REMOTE (mobile laptop)
├─ Existing: Thomson NEOX13 (2 GB RAM, Celeron N3350)
├─ OS: Lubuntu 24.04 (lightweight Ubuntu variant)
├─ Role: monitoring + intervention from anywhere
├─ Used in cafés, métro, between VTC rides
└─ ZERO purchase cost

TIER 3 — THE ALERT (smartphone)
├─ Existing: user's Samsung Galaxy
├─ Telegram app for notifications
├─ Termux for emergency SSH access
└─ Already in user's pocket
```

### 4.2 The software stack

```text
ON THE TOWER (Tier 1):
├─ Ubuntu Server 24.04 LTS
├─ Python 3.12 with venv
├─ Playwright (Python) for web automation
├─ Chromium headless (managed by Playwright)
├─ Ollama serving Qwen 2.5 3B Q4_K_M
├─ PostgreSQL for task queue (lightweight)
├─ Custom Python scripts:
│   - orchestrator.py (main loop)
│   - pattern_matcher.py (regex layer)
│   - llm_classifier.py (Qwen fallback)
│   - playwright_actions.py (browser automation)
│   - vps_executor.py (SSH ops)
│   - telegram_bot.py (notifications)
│   - model_router.py (Codex model switching)
└─ SSH server for remote access

ON THE LAPTOP (Tier 2):
├─ Lubuntu 24.04 LTS
├─ OpenSSH client
├─ Firefox or Falkon (lightweight browser)
├─ Telegram Desktop
├─ Tmux for persistent SSH sessions
└─ Optional: VS Code Remote-SSH

ON THE PHONE (Tier 3):
├─ Telegram (notifications + commands)
└─ Termux (emergency SSH)

EXTERNAL DEPENDENCIES:
├─ ChatGPT Plus subscription (23€/month, already paid)
├─ Hostinger VPS (production, already in use)
└─ Telegram bot (free)
```

---

## 5. The Workflow in Detail

### 5.1 High-level loop

```text
EVERY 30 SECONDS, ON THE TOWER:

1. Check task queue (PostgreSQL)
2. If pending task: skip (already processing)
3. If empty: read latest ChatGPT message (Playwright)
4. Parse message intent (Pattern Layer → LLM Layer)
5. Execute action based on intent
6. Report result back to ChatGPT
7. Tap "Send" to continue conversation
8. Notify Telegram if escalation needed
9. Loop
```

### 5.2 Intent recognition (two-layer)

```text
LAYER 1 — REGEX PATTERN MATCHING (~95% of messages)

Patterns expected from ChatGPT (when using the strict template
defined in Section 6):

PATTERN A — New patch
  Match: r"=== PATCH \d+ ===\nCOMPLEXITY: (.+?)\nMODEL: (.+?)\n"
  Extract: complexity, model, fast_mode, prompt_block, tests
  Action: SUBMIT_TO_CODEX

PATTERN B — Validation
  Match: r"Tests OK, proceed to next patch"
  Action: CONTINUE_NEXT

PATTERN C — Upload file
  Match: r"Upload this file to (.+?):\n```\n(.+?)\n```"
  Extract: path, content
  Action: SCP_UPLOAD

PATTERN D — Execute command
  Match: r"Execute on VPS:\n```\n(.+?)\n```"
  Extract: command
  Action: SSH_EXEC

PATTERN E — Question to user
  Match: r"USER_DECISION_NEEDED:\n(.+)"
  Extract: question
  Action: NOTIFY_TELEGRAM

PATTERN F — Project complete
  Match: r"V1 COMPLETE" or r"PHASE \d+ COMPLETE"
  Action: NOTIFY_AND_PAUSE

If any pattern matches: act immediately, skip Layer 2.

LAYER 2 — LLM CLASSIFICATION (~5% of messages)

If no pattern matches: ChatGPT formulated differently.
Send the message to local Qwen 3B with this prompt:

  System: "You are an intent classifier. Read the ChatGPT
   message and classify it into one of these intents:
   SUBMIT_TO_CODEX, CONTINUE_NEXT, SCP_UPLOAD, SSH_EXEC,
   NOTIFY_TELEGRAM, NOTIFY_AND_PAUSE, UNCLEAR.
   Output JSON with confidence score 0-1."
  
  User: [the ChatGPT message]

Decision rules:
- If confidence > 0.8: execute the detected intent
- If 0.5 < confidence ≤ 0.8: execute + log warning
- If confidence ≤ 0.5: NOTIFY_TELEGRAM with the message
```

### 5.3 Action execution

```text
For each detected intent, the orchestrator runs:

SUBMIT_TO_CODEX:
  1. Open Codex tab in browser (or switch to it)
  2. Run /model <model_name> to switch model
  3. Run /fast on or /fast off based on fast_mode flag
  4. Paste the prompt block
  5. Press Send
  6. Wait for Codex completion (poll for "stop" indicator)
  7. Copy Codex response
  8. Switch to ChatGPT tab
  9. Paste Codex response
  10. Press Send
  11. Wait for ChatGPT next message
  12. Loop

CONTINUE_NEXT:
  1. Type "let's go" or "continue" in ChatGPT
  2. Press Send
  3. Wait for next message
  4. Loop

SCP_UPLOAD:
  1. Write content to temp file
  2. scp temp_file user@vps:path
  3. Read scp output
  4. Type in ChatGPT: "Upload successful: <stdout>"
  5. Press Send

SSH_EXEC:
  1. ssh user@vps "<command>"
  2. Capture stdout and stderr (max 10000 chars)
  3. Type in ChatGPT: "Command output:\n```\n<output>\n```"
  4. Press Send

NOTIFY_TELEGRAM:
  1. Send message to user via Telegram bot
  2. Wait for user response (max 30 min)
  3. If response: type it in ChatGPT, press Send
  4. If timeout: pause orchestrator, send reminder

NOTIFY_AND_PAUSE:
  1. Send celebration message to Telegram
  2. Pause orchestrator
  3. Wait for user to manually resume
```

---

## 6. The ChatGPT Communication Template

This is the **critical contract** between user, ChatGPT, and orchestrator.

### 6.1 Initial setup prompt to ChatGPT

```text
At project kickoff, the user gives ChatGPT this system prompt:

---
You are the project coordinator for my personal OS implementation.

I have an autonomous orchestrator that reads your messages and
executes actions on my development VPS. To work with it correctly,
you MUST follow this strict format for ALL operational messages.

FORMAT FOR NEW CODE PATCHES:
=== PATCH [N] ===
COMPLEXITY: [simple|medium|complex|critical]
MODEL: [gpt-5.4-mini|gpt-5.4|gpt-5.5]
FAST_MODE: [yes|no]
DESCRIPTION: [one-line description]

PROMPT FOR CODEX:
```
[the exact prompt for Codex]
```

EXPECTED FILES:
- path/to/file1.py
- path/to/file2.sql

TESTS TO RUN:
- pytest tests/test_x.py
- curl -X GET http://localhost:8000/health

VALIDATION CRITERIA:
- All tests pass
- No errors in logs
=== END PATCH ===

FORMAT FOR FILE UPLOADS:
Upload this file to /path/on/vps:
```
[file content]
```

FORMAT FOR VPS COMMANDS:
Execute on VPS:
```
[shell command]
```

FORMAT FOR USER QUESTIONS:
USER_DECISION_NEEDED:
[your question]

FORMAT FOR COMPLETION:
PATCH [N] COMPLETE
OR
V1 COMPLETE

MODEL ROUTING GUIDELINES:
- gpt-5.4-mini: Simple CRUD, isolated functions, basic SQL,
  pure config files. Anything where context fits in <500 lines.
- gpt-5.4: Default for everything moderate. API endpoints with
  business logic, multi-file changes within one module.
- gpt-5.5: Architecture decisions, complex refactoring,
  cross-module changes, subtle debugging, anything requiring
  deep system understanding.

FAST_MODE: Only "yes" when latency matters (rare).
---

This prompt is saved in ChatGPT's custom instructions or pinned
at the start of every session.
```

### 6.2 Why this strict format

```text
WITHOUT a strict format:
├─ ChatGPT phrases differently each time
├─ Regex patterns fail
├─ LLM classifier struggles
├─ Orchestrator escalates too often
└─ User intervention required constantly

WITH the strict format:
├─ 95%+ of messages parsed by regex
├─ Predictable, reliable
├─ User intervention rare
└─ True autonomy
```

### 6.3 When ChatGPT deviates

```text
DESPITE the strict format, ChatGPT will sometimes deviate
(5-10% of the time). This is normal AI behavior.

Examples of deviation:
- "Ok, before we move on, can you confirm X?"
- "I think there's an issue with the previous patch..."
- "Let me suggest a different approach..."

These don't match patterns → Layer 2 (Qwen) handles them.
Qwen classifies them as NOTIFY_TELEGRAM or UNCLEAR.
User responds via Telegram, orchestrator forwards to ChatGPT.

= Graceful degradation, no system crash.
```

---

## 7. Codex Model Routing — The Key Optimization

This is what makes the orchestrator **economically viable**.

### 7.1 Codex pricing reality (May 2026)

```text
CODEX TOKEN PRICING (token-based since April 2, 2026):

GPT-5.4-mini: ~5x cheaper than 5.5
  Use for: simple CRUD, isolated functions, config

GPT-5.4: ~2x cheaper than 5.5
  Use for: moderate complexity, business logic

GPT-5.5: full price
  Use for: architecture, debugging, multi-module

Fast mode: 2.5x more credits (GPT-5.5) or 2x (GPT-5.4)
  Use for: latency-critical work only (rare)

USER PLAN: ChatGPT Plus (~23€/month)
RATE LIMITS: 5-hour windows + weekly limit
WITH SMART ROUTING: ~2.5x more capacity per week vs all-5.5
```

### 7.2 Routing distribution for V1

```text
EXPECTED PATCH MIX FOR V1 IMPLEMENTATION:

50% of patches → GPT-5.4-mini
  - CRUD endpoints
  - Simple migrations
  - Config files
  - Isolated utility functions
  - Documentation files
  
35% of patches → GPT-5.4
  - API endpoints with business logic
  - Service classes
  - Multi-file changes within one module
  - n8n workflow definitions
  - SQL with moderate complexity

12% of patches → GPT-5.5
  - Architecture decisions
  - Cross-module changes
  - Complex AI routing logic
  - Subtle bug fixes
  - Performance optimization

3% of patches → GPT-5.5 with Fast mode
  - Critical hotfixes
  - Time-sensitive debugging
  - Production issues

EFFECTIVE RATE LIMIT GAIN: ~2-3x vs all-5.5 usage.
```

### 7.3 Switching models in Codex

```text
CODEX CLI (preferred for orchestrator):

To switch model:
  /model gpt-5.4-mini
  /model gpt-5.4
  /model gpt-5.5

To toggle fast mode:
  /fast on
  /fast off
  /fast status

CODEX WEB (fallback):
  Click model dropdown → select model
  Settings → Speed → Fast mode toggle

THE ORCHESTRATOR EXECUTES THESE COMMANDS AUTOMATICALLY
based on ChatGPT's MODEL: and FAST_MODE: fields.
```

---

## 8. The Database Schema — Complete Observability Layer

> **Why this is critical:** When 3 AIs talk to each other without a human in the loop, things can go wrong silently. ChatGPT misunderstands, Codex generates bad code, tests don't cover the right things, and the orchestrator keeps going. Without granular logs, you'll discover the disaster 3 days later with no way to know where it started.
>
> Every table below answers a specific question you WILL ask in production.

### 8.1 Core task queue (enhanced)

```sql
CREATE TABLE orchestrator_tasks (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  -- TASK IDENTITY
  patch_number          INTEGER NOT NULL,
  session_id            UUID NOT NULL,
                        -- groups patches in the same ChatGPT session
  complexity            VARCHAR(16) NOT NULL,
                        -- 'simple' | 'medium' | 'complex' | 'critical'
  model_requested       VARCHAR(32) NOT NULL,
                        -- 'gpt-5.4-mini' | 'gpt-5.4' | 'gpt-5.5'
  model_actually_used   VARCHAR(32) NULL,
                        -- may differ if model was switched by orchestrator
  fast_mode             BOOLEAN NOT NULL DEFAULT FALSE,
  description           TEXT NOT NULL,
  
  -- WHAT CHATGPT ASKED
  codex_prompt          TEXT NOT NULL,
  expected_files        TEXT[],
  test_commands         TEXT[],
  validation_criteria   TEXT,
  chatgpt_message_id    BIGINT NULL,
                        -- FK to orchestrator_chatgpt_messages.id
  
  -- LIFECYCLE STATUS
  status                VARCHAR(32) NOT NULL DEFAULT 'pending',
                        -- 'pending'         → waiting to start
                        -- 'codex_running'   → prompt sent to Codex
                        -- 'codex_done'      → Codex responded
                        -- 'uploading'       → uploading files to VPS
                        -- 'tests_running'   → running test commands
                        -- 'tests_passed'    → all tests green
                        -- 'tests_failed'    → tests failed, retrying
                        -- 'reporting'       → sending result to ChatGPT
                        -- 'completed'       → full cycle done
                        -- 'failed'          → abandoned after max retries
                        -- 'escalated'       → waiting for user intervention
                        -- 'aborted'         → user manually aborted
  
  -- TIMING (track each phase)
  queued_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  codex_started_at      TIMESTAMPTZ NULL,
  codex_done_at         TIMESTAMPTZ NULL,
  upload_started_at     TIMESTAMPTZ NULL,
  upload_done_at        TIMESTAMPTZ NULL,
  tests_started_at      TIMESTAMPTZ NULL,
  tests_done_at         TIMESTAMPTZ NULL,
  completed_at          TIMESTAMPTZ NULL,
  
  -- CODEX RESPONSE
  codex_raw_response    TEXT NULL,
                        -- full Codex output, unedited
  codex_tokens_estimate INTEGER NULL,
                        -- estimated from response length
  
  -- TEST RESULTS
  test_output           TEXT NULL,
                        -- full stdout/stderr of test commands
  tests_passed          BOOLEAN NULL,
                        -- NULL=not run, TRUE=all pass, FALSE=some fail
  tests_passed_count    INTEGER NULL,
  tests_failed_count    INTEGER NULL,
  
  -- RETRY TRACKING
  attempt_count         INTEGER NOT NULL DEFAULT 0,
  max_attempts          INTEGER NOT NULL DEFAULT 3,
  last_error_code       VARCHAR(64) NULL,
                        -- 'codex_timeout' | 'codex_empty_response' |
                        --  'upload_ssh_failed' | 'test_command_failed' |
                        --  'chatgpt_not_responding' | 'playwright_crash'
  last_error_message    TEXT NULL,
  
  -- QUALITY ASSESSMENT
  chatgpt_validated     BOOLEAN NULL,
                        -- did ChatGPT confirm the patch was good?
  chatgpt_feedback      TEXT NULL,
                        -- what ChatGPT said about the result
  user_override         BOOLEAN NOT NULL DEFAULT FALSE,
                        -- user manually validated despite test failure
  user_override_reason  TEXT NULL
);

CREATE INDEX orchestrator_tasks_status_idx
ON orchestrator_tasks (status, created_at DESC);

CREATE INDEX orchestrator_tasks_session_idx
ON orchestrator_tasks (session_id, patch_number);

CREATE INDEX orchestrator_tasks_failed_idx
ON orchestrator_tasks (created_at DESC)
WHERE status IN ('failed', 'escalated', 'aborted');
```

### 8.2 ChatGPT message log (every message, verbatim)

```sql
CREATE TABLE orchestrator_chatgpt_messages (
  id                    BIGSERIAL PRIMARY KEY,
  received_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  session_id            UUID NOT NULL,
  message_index         INTEGER NOT NULL,
                        -- position in conversation (1, 2, 3...)
  
  -- THE MESSAGE ITSELF
  message_content       TEXT NOT NULL,
                        -- verbatim content as read from screen
  message_length_chars  INTEGER GENERATED ALWAYS AS
                        (LENGTH(message_content)) STORED,
  
  -- INTENT DETECTION
  detected_intent       VARCHAR(64) NULL,
                        -- 'SUBMIT_TO_CODEX' | 'CONTINUE_NEXT' |
                        --  'SCP_UPLOAD' | 'SSH_EXEC' | 'ASK_USER' |
                        --  'NOTIFY_AND_PAUSE' | 'UNCLEAR'
  detection_layer       VARCHAR(16) NULL,
                        -- 'regex' | 'llm' | 'fallback_escalation'
  detection_confidence  NUMERIC(3,2) NULL,
                        -- 0.00 to 1.00
  regex_pattern_matched VARCHAR(64) NULL,
                        -- which pattern matched (e.g. 'PATTERN_A')
  llm_raw_output        TEXT NULL,
                        -- what Qwen returned (JSON string)
  
  -- ACTION TAKEN
  action_taken          VARCHAR(64) NULL,
  action_status         VARCHAR(32) NULL,
                        -- 'success' | 'failed' | 'escalated' | 'skipped'
  action_duration_ms    INTEGER NULL,
  action_error          TEXT NULL,
  
  -- LINKAGE
  task_id               UUID NULL REFERENCES orchestrator_tasks(id),
  was_escalated         BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX orchestrator_chatgpt_messages_time_idx
ON orchestrator_chatgpt_messages (received_at DESC);

CREATE INDEX orchestrator_chatgpt_messages_session_idx
ON orchestrator_chatgpt_messages (session_id, message_index);

CREATE INDEX orchestrator_chatgpt_messages_unclear_idx
ON orchestrator_chatgpt_messages (received_at DESC)
WHERE detected_intent = 'UNCLEAR' OR detection_layer = 'fallback_escalation';
```

### 8.3 Codex interaction log (every prompt + response)

```sql
CREATE TABLE orchestrator_codex_calls (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id               UUID NOT NULL REFERENCES orchestrator_tasks(id),
  attempt_number        INTEGER NOT NULL DEFAULT 1,
  called_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  -- WHAT WAS SENT
  model_used            VARCHAR(32) NOT NULL,
  fast_mode             BOOLEAN NOT NULL DEFAULT FALSE,
  prompt_sent           TEXT NOT NULL,
                        -- exact prompt pasted into Codex
  prompt_length_chars   INTEGER GENERATED ALWAYS AS
                        (LENGTH(prompt_sent)) STORED,
  
  -- WHAT CAME BACK
  response_received     TEXT NULL,
                        -- full Codex response, verbatim
  response_length_chars INTEGER GENERATED ALWAYS AS
                        (COALESCE(LENGTH(response_received), 0)) STORED,
  response_has_code     BOOLEAN NULL,
                        -- did the response contain code blocks?
  files_mentioned       TEXT[] NULL,
                        -- file paths detected in the response
  
  -- TIMING
  prompt_submitted_at   TIMESTAMPTZ NULL,
  response_received_at  TIMESTAMPTZ NULL,
  duration_ms           INTEGER NULL,
  
  -- OUTCOME
  success               BOOLEAN NOT NULL DEFAULT TRUE,
  failure_reason        VARCHAR(64) NULL,
                        -- 'timeout' | 'empty_response' |
                        --  'codex_error_message' | 'playwright_lost_focus' |
                        --  'browser_crashed' | 'rate_limited'
  was_response_used     BOOLEAN NULL,
                        -- FALSE if ChatGPT rejected it
  rejection_reason      TEXT NULL
);

CREATE INDEX orchestrator_codex_calls_task_idx
ON orchestrator_codex_calls (task_id, attempt_number);

CREATE INDEX orchestrator_codex_calls_failed_idx
ON orchestrator_codex_calls (called_at DESC)
WHERE success = FALSE;
```

### 8.4 File operations log (every upload)

```sql
CREATE TABLE orchestrator_file_operations (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id               UUID NOT NULL REFERENCES orchestrator_tasks(id),
  operated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  operation_type        VARCHAR(32) NOT NULL,
                        -- 'scp_upload' | 'ssh_create' | 'ssh_delete' |
                        --  'ssh_mkdir' | 'ssh_chmod'
  
  -- WHAT FILE
  file_path_local       TEXT NULL,
  file_path_remote      TEXT NOT NULL,
                        -- destination on VPS
  file_size_bytes       INTEGER NULL,
  
  -- CONTENT SNAPSHOT (for audit)
  content_before        TEXT NULL,
                        -- content that existed before (if overwriting)
  content_after         TEXT NULL,
                        -- new content written
  content_diff_lines    INTEGER NULL,
                        -- rough lines changed
  
  -- OUTCOME
  success               BOOLEAN NOT NULL DEFAULT TRUE,
  duration_ms           INTEGER NULL,
  error_message         TEXT NULL,
  
  -- REVERSIBILITY
  is_reversible         BOOLEAN NOT NULL DEFAULT TRUE,
  rollback_command      TEXT NULL
                        -- command to undo if needed
);

CREATE INDEX orchestrator_file_operations_task_idx
ON orchestrator_file_operations (task_id, operated_at);

CREATE INDEX orchestrator_file_operations_path_idx
ON orchestrator_file_operations (file_path_remote, operated_at DESC);

CREATE INDEX orchestrator_file_operations_failed_idx
ON orchestrator_file_operations (operated_at DESC)
WHERE success = FALSE;
```

### 8.5 Test execution log (every test command)

```sql
CREATE TABLE orchestrator_test_executions (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id               UUID NOT NULL REFERENCES orchestrator_tasks(id),
  attempt_number        INTEGER NOT NULL DEFAULT 1,
  executed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  -- WHAT WAS RUN
  command               TEXT NOT NULL,
                        -- exact command sent via SSH
  working_directory     TEXT NULL,
  
  -- WHAT CAME BACK
  stdout                TEXT NULL,
  stderr                TEXT NULL,
  exit_code             INTEGER NULL,
                        -- 0 = success, anything else = failure
  
  -- INTERPRETATION
  test_passed           BOOLEAN NOT NULL,
                        -- exit_code = 0 AND no error patterns
  failure_pattern       VARCHAR(128) NULL,
                        -- what keyword triggered failure detection
                        -- e.g. 'FAILED' | 'Error' | 'assert' | 'Exception'
  
  -- TIMING
  duration_ms           INTEGER NULL,
  timed_out             BOOLEAN NOT NULL DEFAULT FALSE,
  timeout_seconds       INTEGER NULL,
  
  -- CONTEXT
  was_final_attempt     BOOLEAN NOT NULL DEFAULT FALSE,
  triggered_escalation  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX orchestrator_test_executions_task_idx
ON orchestrator_test_executions (task_id, attempt_number, executed_at);

CREATE INDEX orchestrator_test_executions_failed_idx
ON orchestrator_test_executions (executed_at DESC)
WHERE test_passed = FALSE;
```

### 8.6 Playwright actions log (every browser action)

```sql
CREATE TABLE orchestrator_playwright_actions (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id               UUID NULL REFERENCES orchestrator_tasks(id),
  acted_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  action_type           VARCHAR(64) NOT NULL,
                        -- 'click' | 'type' | 'copy' | 'paste' |
                        --  'navigate' | 'screenshot' | 'wait' |
                        --  'switch_tab' | 'scroll' | 'read_element' |
                        --  'select_model' | 'submit_form'
  
  -- WHERE ON THE PAGE
  target_selector       TEXT NULL,
                        -- CSS selector or description
  target_description    TEXT NULL,
                        -- human-readable: "ChatGPT send button"
  
  -- WHAT WAS DONE
  value_sent            TEXT NULL,
                        -- text typed or pasted (truncated to 500 chars)
  value_read            TEXT NULL,
                        -- text read from page (truncated to 500 chars)
  
  -- OUTCOME
  success               BOOLEAN NOT NULL DEFAULT TRUE,
  duration_ms           INTEGER NULL,
  error_message         TEXT NULL,
  screenshot_path       TEXT NULL,
                        -- path to screenshot if action failed
  
  -- RETRY CONTEXT
  retry_of_action_id    UUID NULL REFERENCES orchestrator_playwright_actions(id)
);

CREATE INDEX orchestrator_playwright_actions_task_idx
ON orchestrator_playwright_actions (task_id, acted_at);

CREATE INDEX orchestrator_playwright_actions_failed_idx
ON orchestrator_playwright_actions (acted_at DESC)
WHERE success = FALSE;
```

### 8.7 LLM classifier log (Qwen decisions)

```sql
CREATE TABLE orchestrator_llm_classifications (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  classified_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  message_id            BIGINT NULL REFERENCES orchestrator_chatgpt_messages(id),
  
  -- INPUT
  input_text            TEXT NOT NULL,
                        -- the message sent to Qwen for classification
  input_length_chars    INTEGER GENERATED ALWAYS AS
                        (LENGTH(input_text)) STORED,
  
  -- QWEN OUTPUT
  raw_output            TEXT NULL,
                        -- exact JSON returned by Qwen
  classified_intent     VARCHAR(64) NULL,
  confidence_score      NUMERIC(3,2) NULL,
  
  -- PERFORMANCE
  duration_ms           INTEGER NULL,
  model_version         VARCHAR(32) NOT NULL DEFAULT 'qwen-2.5-3b-q4',
  
  -- QUALITY TRACKING
  was_correct           BOOLEAN NULL,
                        -- NULL = unknown, TRUE = correct, FALSE = wrong
  correct_intent        VARCHAR(64) NULL,
                        -- what the intent SHOULD have been (if wrong)
  correction_source     VARCHAR(32) NULL
                        -- 'user_telegram' | 'auto_detected' | 'escalation'
);

CREATE INDEX orchestrator_llm_classifications_time_idx
ON orchestrator_llm_classifications (classified_at DESC);

CREATE INDEX orchestrator_llm_classifications_wrong_idx
ON orchestrator_llm_classifications (classified_at DESC)
WHERE was_correct = FALSE;
```

### 8.8 Escalations log (enhanced)

```sql
CREATE TABLE orchestrator_escalations (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  triggered_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  task_id               UUID NULL REFERENCES orchestrator_tasks(id),
  
  -- WHY ESCALATED
  reason                VARCHAR(64) NOT NULL,
                        -- 'unclear_intent' | 'codex_failed_3x' |
                        --  'tests_failed_3x' | 'playwright_crash' |
                        --  'loop_detected' | 'manual_request' |
                        --  'budget_exceeded' | 'suspicious_pattern'
  reason_detail         TEXT NULL,
                        -- more context on why
  
  -- WHAT HAPPENED BEFORE
  context_chatgpt_message TEXT NULL,
  context_last_action   TEXT NULL,
  attempts_before       INTEGER NULL,
  
  -- TELEGRAM NOTIFICATION
  telegram_sent_at      TIMESTAMPTZ NULL,
  telegram_message_id   INTEGER NULL,
                        -- Telegram's own message ID
  
  -- USER RESPONSE
  user_response         TEXT NULL,
  user_responded_at     TIMESTAMPTZ NULL,
  response_delay_min    INTEGER GENERATED ALWAYS AS (
    EXTRACT(EPOCH FROM (user_responded_at - telegram_sent_at)) / 60
  )::INTEGER STORED,
  
  -- RESOLUTION
  resolution            VARCHAR(32) NULL,
                        -- 'user_resolved' | 'auto_resolved' |
                        --  'paused' | 'aborted' | 'skipped_by_user'
  resolved_at           TIMESTAMPTZ NULL,
  orchestrator_resumed  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX orchestrator_escalations_time_idx
ON orchestrator_escalations (triggered_at DESC);

CREATE INDEX orchestrator_escalations_open_idx
ON orchestrator_escalations (triggered_at DESC)
WHERE resolved_at IS NULL;
```

### 8.9 Session log (grouping everything)

```sql
CREATE TABLE orchestrator_sessions (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  started_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at              TIMESTAMPTZ NULL,
  end_reason            VARCHAR(32) NULL,
                        -- 'completed' | 'codex_rate_limit' |
                        --  'user_pause' | 'crash' | 'all_tasks_done'
  
  -- WHAT HAPPENED
  patches_attempted     INTEGER NOT NULL DEFAULT 0,
  patches_completed     INTEGER NOT NULL DEFAULT 0,
  patches_failed        INTEGER NOT NULL DEFAULT 0,
  patches_escalated     INTEGER NOT NULL DEFAULT 0,
  
  -- CODEX USAGE (per session)
  codex_calls_total     INTEGER NOT NULL DEFAULT 0,
  codex_model_mini      INTEGER NOT NULL DEFAULT 0,
  codex_model_5_4       INTEGER NOT NULL DEFAULT 0,
  codex_model_5_5       INTEGER NOT NULL DEFAULT 0,
  codex_fast_mode_uses  INTEGER NOT NULL DEFAULT 0,
  
  -- PLAYWRIGHT
  playwright_actions    INTEGER NOT NULL DEFAULT 0,
  playwright_errors     INTEGER NOT NULL DEFAULT 0,
  
  -- TESTS
  tests_run             INTEGER NOT NULL DEFAULT 0,
  tests_passed          INTEGER NOT NULL DEFAULT 0,
  tests_failed          INTEGER NOT NULL DEFAULT 0,
  
  -- LLM CLASSIFIER
  llm_calls_total       INTEGER NOT NULL DEFAULT 0,
  llm_correct           INTEGER NOT NULL DEFAULT 0,
  llm_wrong             INTEGER NOT NULL DEFAULT 0,
  llm_unclear           INTEGER NOT NULL DEFAULT 0,
  
  -- ESCALATIONS
  escalations_total     INTEGER NOT NULL DEFAULT 0,
  escalations_resolved  INTEGER NOT NULL DEFAULT 0,
  
  -- LOOP DETECTION
  max_consecutive_failures INTEGER NOT NULL DEFAULT 0,
  loop_detected         BOOLEAN NOT NULL DEFAULT FALSE,
  loop_detected_at      TIMESTAMPTZ NULL
);

CREATE INDEX orchestrator_sessions_time_idx
ON orchestrator_sessions (started_at DESC);
```

### 8.10 Daily statistics (enhanced)

```sql
CREATE TABLE orchestrator_daily_stats (
  date                  DATE PRIMARY KEY,
  
  -- VOLUME
  sessions_run          INTEGER NOT NULL DEFAULT 0,
  patches_attempted     INTEGER NOT NULL DEFAULT 0,
  patches_completed     INTEGER NOT NULL DEFAULT 0,
  patches_failed        INTEGER NOT NULL DEFAULT 0,
  patches_escalated     INTEGER NOT NULL DEFAULT 0,
  completion_rate_pct   NUMERIC(5,2) GENERATED ALWAYS AS (
    CASE WHEN patches_attempted > 0
    THEN ROUND(100.0 * patches_completed / patches_attempted, 2)
    ELSE 0 END
  ) STORED,
  
  -- CODEX
  codex_calls_total     INTEGER NOT NULL DEFAULT 0,
  codex_model_mini_pct  NUMERIC(5,2) NOT NULL DEFAULT 0,
  codex_model_5_4_pct   NUMERIC(5,2) NOT NULL DEFAULT 0,
  codex_model_5_5_pct   NUMERIC(5,2) NOT NULL DEFAULT 0,
  
  -- PLAYWRIGHT
  playwright_errors     INTEGER NOT NULL DEFAULT 0,
  playwright_crashes    INTEGER NOT NULL DEFAULT 0,
  
  -- TESTS
  test_pass_rate_pct    NUMERIC(5,2) NOT NULL DEFAULT 0,
  
  -- LLM ACCURACY
  llm_accuracy_pct      NUMERIC(5,2) NOT NULL DEFAULT 0,
  llm_unclear_count     INTEGER NOT NULL DEFAULT 0,
  
  -- ESCALATIONS
  escalations_count     INTEGER NOT NULL DEFAULT 0,
  avg_response_time_min NUMERIC(8,2) NULL,
                        -- avg time user took to respond
  
  -- UPTIME
  uptime_minutes        INTEGER NOT NULL DEFAULT 0,
  downtime_minutes      INTEGER NOT NULL DEFAULT 0,
  
  -- ANOMALIES
  loops_detected        INTEGER NOT NULL DEFAULT 0,
  budget_alerts         INTEGER NOT NULL DEFAULT 0
);
```

### 8.11 Analysis views for orchestrator

```sql
-- ─────────────────────────────────────────────────────
-- VIEW 1: PATCH AUDIT TRAIL
-- Question: "What exactly happened on patch 42?"
-- ─────────────────────────────────────────────────────
CREATE VIEW orchestrator_patch_audit AS
SELECT
  t.patch_number,
  t.description,
  t.complexity,
  t.model_requested,
  t.model_actually_used,
  t.status,
  t.attempt_count,
  -- timing
  t.codex_started_at - t.queued_at                    AS queue_wait,
  t.codex_done_at - t.codex_started_at                AS codex_duration,
  t.tests_done_at - t.tests_started_at                AS tests_duration,
  t.completed_at - t.queued_at                        AS total_duration,
  -- codex
  c.response_length_chars                             AS codex_response_chars,
  c.files_mentioned                                   AS files_generated,
  -- tests
  t.tests_passed,
  t.tests_passed_count,
  t.tests_failed_count,
  -- outcome
  t.chatgpt_validated,
  t.last_error_code
FROM orchestrator_tasks t
LEFT JOIN orchestrator_codex_calls c
  ON c.task_id = t.id AND c.attempt_number = 1
ORDER BY t.patch_number;

-- ─────────────────────────────────────────────────────
-- VIEW 2: FAILURE PATTERN ANALYSIS
-- Question: "What fails the most and why?"
-- ─────────────────────────────────────────────────────
CREATE VIEW orchestrator_failure_patterns AS
SELECT
  last_error_code,
  complexity,
  model_requested,
  COUNT(*)                            AS failure_count,
  AVG(attempt_count)                  AS avg_attempts_before_fail,
  ROUND(
    100.0 * COUNT(*)
    / SUM(COUNT(*)) OVER (),
    1
  )                                   AS pct_of_all_failures
FROM orchestrator_tasks
WHERE status IN ('failed', 'escalated', 'aborted')
GROUP BY 1, 2, 3
ORDER BY 4 DESC;

-- ─────────────────────────────────────────────────────
-- VIEW 3: LLM CLASSIFIER ACCURACY
-- Question: "Is Qwen understanding ChatGPT correctly?"
-- ─────────────────────────────────────────────────────
CREATE VIEW orchestrator_classifier_accuracy AS
SELECT
  DATE_TRUNC('day', classified_at)::DATE AS day,
  COUNT(*)                               AS total_classifications,
  COUNT(*) FILTER (WHERE was_correct = TRUE)  AS correct,
  COUNT(*) FILTER (WHERE was_correct = FALSE) AS wrong,
  COUNT(*) FILTER (WHERE was_correct IS NULL) AS unchecked,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE was_correct = TRUE)
    / NULLIF(COUNT(*) FILTER (WHERE was_correct IS NOT NULL), 0),
    1
  )                                      AS accuracy_pct,
  ROUND(AVG(confidence_score), 2)        AS avg_confidence,
  COUNT(*) FILTER (WHERE confidence_score < 0.5) AS low_confidence_count
FROM orchestrator_llm_classifications
GROUP BY 1
ORDER BY 1 DESC;

-- ─────────────────────────────────────────────────────
-- VIEW 4: LOOP / SPIRAL DETECTION
-- Question: "Is the orchestrator looping on something?"
-- ─────────────────────────────────────────────────────
CREATE VIEW orchestrator_loop_detector AS
SELECT
  session_id,
  COUNT(*) AS total_tasks,
  COUNT(*) FILTER (WHERE status = 'failed')     AS failed,
  COUNT(*) FILTER (WHERE status = 'escalated')  AS escalated,
  MAX(attempt_count)                            AS max_retries_on_one_task,
  BOOL_OR(loop_detected)                        AS loop_detected,
  MIN(queued_at)                                AS session_start,
  MAX(completed_at)                             AS session_last_activity,
  EXTRACT(EPOCH FROM (MAX(COALESCE(completed_at, NOW())) -
    MIN(queued_at))) / 3600                     AS session_hours
FROM orchestrator_tasks
LEFT JOIN orchestrator_sessions s ON s.id = session_id
GROUP BY session_id
HAVING MAX(attempt_count) >= 2
    OR COUNT(*) FILTER (WHERE status = 'failed') >= 2
ORDER BY MAX(attempt_count) DESC, failed DESC;

-- ─────────────────────────────────────────────────────
-- VIEW 5: TEST QUALITY ANALYSIS
-- Question: "Are the tests actually catching bugs?"
-- ─────────────────────────────────────────────────────
CREATE VIEW orchestrator_test_quality AS
SELECT
  t.description,
  t.complexity,
  te.command,
  COUNT(*)                                  AS times_run,
  COUNT(*) FILTER (WHERE te.test_passed)   AS times_passed,
  COUNT(*) FILTER (WHERE NOT te.test_passed) AS times_failed,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE te.test_passed)
    / COUNT(*),
    1
  )                                         AS pass_rate_pct,
  ROUND(AVG(te.duration_ms))                AS avg_duration_ms,
  MODE() WITHIN GROUP (ORDER BY te.failure_pattern) AS most_common_failure
FROM orchestrator_test_executions te
JOIN orchestrator_tasks t ON t.id = te.task_id
GROUP BY 1, 2, 3
ORDER BY times_failed DESC;

-- ─────────────────────────────────────────────────────
-- VIEW 6: PLAYWRIGHT RELIABILITY
-- Question: "Is the browser automation stable?"
-- ─────────────────────────────────────────────────────
CREATE VIEW orchestrator_playwright_reliability AS
SELECT
  action_type,
  target_description,
  COUNT(*)                              AS times_executed,
  COUNT(*) FILTER (WHERE success)      AS successes,
  COUNT(*) FILTER (WHERE NOT success)  AS failures,
  ROUND(
    100.0 * COUNT(*) FILTER (WHERE NOT success)
    / COUNT(*),
    1
  )                                    AS failure_rate_pct,
  ROUND(AVG(duration_ms))              AS avg_ms,
  ROUND(
    PERCENTILE_CONT(0.95)
    WITHIN GROUP (ORDER BY duration_ms)
  )                                    AS p95_ms
FROM orchestrator_playwright_actions
WHERE acted_at > NOW() - INTERVAL '7 days'
GROUP BY 1, 2
HAVING COUNT(*) >= 5
ORDER BY failure_rate_pct DESC, times_executed DESC;

-- ─────────────────────────────────────────────────────
-- VIEW 7: WEEKLY EXECUTIVE SUMMARY
-- Question: "How did the week go overall?"
-- ─────────────────────────────────────────────────────
CREATE VIEW orchestrator_weekly_summary AS
SELECT
  DATE_TRUNC('week', date)::DATE        AS week_start,
  SUM(patches_completed)                AS patches_done,
  SUM(patches_failed)                   AS patches_failed,
  ROUND(
    100.0 * SUM(patches_completed)
    / NULLIF(SUM(patches_attempted), 0),
    1
  )                                     AS completion_rate_pct,
  SUM(escalations_count)                AS total_escalations,
  ROUND(AVG(avg_response_time_min), 0)  AS avg_user_response_min,
  SUM(loops_detected)                   AS loops_caught,
  ROUND(AVG(llm_accuracy_pct), 1)       AS avg_llm_accuracy_pct,
  ROUND(AVG(test_pass_rate_pct), 1)     AS avg_test_pass_rate_pct,
  SUM(uptime_minutes) / 60              AS uptime_hours
FROM orchestrator_daily_stats
GROUP BY 1
ORDER BY 1 DESC;

-- ─────────────────────────────────────────────────────
-- VIEW 8: FILES TOUCHED (audit what changed in the codebase)
-- Question: "What files did the orchestrator modify this week?"
-- ─────────────────────────────────────────────────────
CREATE VIEW orchestrator_files_audit AS
SELECT
  file_path_remote,
  COUNT(*)                              AS times_modified,
  SUM(content_diff_lines)               AS total_lines_changed,
  MIN(operated_at)                      AS first_modified,
  MAX(operated_at)                      AS last_modified,
  COUNT(*) FILTER (WHERE NOT success)  AS failed_operations,
  COUNT(DISTINCT task_id)              AS from_n_patches
FROM orchestrator_file_operations
WHERE operated_at > NOW() - INTERVAL '7 days'
GROUP BY 1
ORDER BY times_modified DESC, total_lines_changed DESC;
```

### 8.12 Alert queries (run these daily)

```sql
-- ALERT 1: Loops — consecutive failures on same session
SELECT session_id, MAX(attempt_count) AS max_retries
FROM orchestrator_tasks
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY session_id
HAVING MAX(attempt_count) >= 3;
-- If any rows returned: something is looping, investigate NOW.

-- ALERT 2: LLM accuracy dropped below threshold
SELECT day, accuracy_pct
FROM orchestrator_classifier_accuracy
WHERE day = CURRENT_DATE AND accuracy_pct < 70;
-- If returned: Qwen is misunderstanding ChatGPT, review messages.

-- ALERT 3: Playwright is destabilizing
SELECT action_type, failure_rate_pct
FROM orchestrator_playwright_reliability
WHERE failure_rate_pct > 10;
-- If returned: ChatGPT or Codex UI probably changed.

-- ALERT 4: Tests not catching anything (all pass rate)
SELECT command, pass_rate_pct
FROM orchestrator_test_quality
WHERE pass_rate_pct = 100 AND times_run >= 10;
-- High pass rate across all tests could mean tests are too weak.

-- ALERT 5: Unresolved escalations older than 4 hours
SELECT id, reason, triggered_at, telegram_sent_at
FROM orchestrator_escalations
WHERE resolved_at IS NULL
  AND triggered_at < NOW() - INTERVAL '4 hours';
-- Means user hasn't responded. Check Telegram.

-- ALERT 6: Files modified too frequently (churn signal)
SELECT file_path_remote, times_modified
FROM orchestrator_files_audit
WHERE times_modified >= 5 AND last_modified > NOW() - INTERVAL '24 hours';
-- Same file rewritten 5+ times in a day = loop or bad prompts.
```

---

## 9. The Telegram Bot

### 9.1 Bot commands

```text
USER → BOT:

/status
  Returns: current task, queue size, last 3 patches, uptime

/queue
  Returns: list of pending patches with model + complexity

/pause
  Pauses the orchestrator (no new actions taken)

/resume
  Resumes the orchestrator

/last
  Returns: last 5 ChatGPT messages + actions taken

/logs [N]
  Returns: last N log lines (default 20)

/say [text]
  Types [text] in the ChatGPT conversation (manual intervention)

/screenshot
  Takes a screenshot of the orchestrator's browser, sends to user

/abort
  Stops current task, marks as failed, moves to next

/stats
  Returns: today's stats (patches, model distribution, etc.)

/help
  Lists all commands
```

### 9.2 Bot → User notifications

```text
NOTIFICATION TYPES:

✅ INFO (silent):
  - Patch N completed successfully
  - Daily stats summary at 21h

⚠️ WARNING (sound):
  - Patch failed, retrying (attempt 2/3)
  - Codex response unusually long
  - LLM classifier had low confidence

🚨 ALERT (loud notification):
  - Patch failed 3 times, requires intervention
  - ChatGPT asking a non-mechanical question
  - Browser session disconnected
  - VPS test failure
  - Tower temperature too high
  - Disk space low

🎉 CELEBRATION:
  - Phase complete (V1 backend done, etc.)
  - V1 complete
  - Milestone passed
```

---

## 10. Implementation Phases

### Phase 1 — Tower Setup (Days 1-3)

```text
DAY 1:
- Backup important files from current OS
- Download Ubuntu Server 24.04 LTS
- Create bootable USB
- Install Ubuntu Server (SSH enabled)
- Configure static IP on local network
- Set up SSH key authentication

DAY 2:
- Update packages
- Install Python 3.12, Node.js 20, build-essential
- Install Ollama: curl -fsSL https://ollama.com/install.sh | sh
- Pull Qwen 2.5 3B: ollama pull qwen2.5:3b
- Test: ollama run qwen2.5:3b "classify: hello world"
- Install Playwright + Chromium

DAY 3:
- Set up project structure in /opt/orchestrator
- Create Python venv
- Install dependencies: playwright, requests, psycopg2,
  python-telegram-bot
- playwright install chromium
- Test Chromium headless: playwright open https://example.com
- Configure UFW firewall (allow only SSH)
```

### Phase 2 — Laptop Setup (Days 4-5)

```text
DAY 4:
- Download Lubuntu 24.04 ISO
- Create bootable USB
- Install Lubuntu on Thomson
- Configure Wi-Fi
- Update packages

DAY 5:
- Install: openssh-client, firefox-esr, tmux, htop
- snap install telegram-desktop
- Generate SSH key for Thomson
- Copy SSH key to tower: ssh-copy-id user@tower-ip
- Test SSH from Thomson to tower
- Set up tmux config for persistent sessions
- Bookmark monitoring URLs in Firefox
```

### Phase 3 — Core Orchestrator (Week 2)

```text
DAY 6-7 — Project skeleton:
- main.py with main loop
- config.yaml for credentials and paths
- logger setup (file + stdout)
- PostgreSQL connection
- Health check endpoints

DAY 8-9 — Pattern Layer:
- pattern_matcher.py
- All 6 regex patterns from Section 5.2
- Unit tests for each pattern
- Edge cases (incomplete messages, special chars)

DAY 10-12 — Playwright actions:
- playwright_actions.py
- Login to ChatGPT (manual once, then persistent)
- Read latest message from chat
- Send message to chat
- Switch tabs (ChatGPT ↔ Codex)
- Execute Codex commands (/model, /fast)
- Wait for Codex completion
- Copy response
```

### Phase 4 — LLM Fallback + VPS Ops (Week 3)

```text
DAY 13-15 — LLM Classifier:
- llm_classifier.py
- Ollama API integration
- Classification prompt (Section 5.2)
- Confidence scoring
- Caching of classifications

DAY 16-18 — VPS Operations:
- vps_executor.py
- SSH wrapper (paramiko or subprocess)
- File upload (scp)
- Command execution
- Output capture and truncation
- Error handling

DAY 19 — Integration:
- Wire all components in main loop
- End-to-end test: simple patch from start to finish
```

### Phase 5 — Telegram + Polish (Week 4)

```text
DAY 20-22 — Telegram Bot:
- Create bot with @BotFather
- python-telegram-bot integration
- All commands from Section 9.1
- Notification types from Section 9.2
- User authentication (verify chat_id)

DAY 23-25 — Resilience:
- Auto-restart on crash (systemd service)
- Browser session refresh on stale
- Codex login re-auth if expired
- Database reconnect on lost connection
- Disk space monitoring
- Memory leak prevention

DAY 26-28 — Production hardening:
- Real-world testing on actual V1 patches
- Tune regex patterns based on observed messages
- Adjust LLM thresholds
- Stress test (50 patches in a row)
- Document edge cases discovered
```

---

## 11. Cost Analysis

```text
INITIAL INVESTMENT:
├─ Tower hardware: 0€ (already owned)
├─ Laptop hardware: 0€ (Thomson recovered)
├─ Smartphone: 0€ (already owned)
├─ Software: 0€ (all open source)
└─ Setup time: ~4 weeks of work (not money)

MONTHLY RECURRING:
├─ ChatGPT Plus: 23€ (already paid)
├─ Hostinger VPS: ~15€ (already paid)
├─ Tower electricity: ~10-15€
│   (i7-4790 + GTX 970 = 100-150W avg)
├─ Telegram: 0€
├─ Codex API: 0€ (uses ChatGPT Plus interface)
└─ TOTAL EXTRA: ~10-15€/month

OVER 4 MONTHS (V1 implementation):
├─ Already paid (Plus + VPS): 152€
├─ Extra (electricity): ~50€
└─ TOTAL: ~50€ above existing costs

COMPARED TO MANUAL CODING (8 months):
├─ Already paid (Plus + VPS): 304€
└─ Time spent: 8 months of user time

ORCHESTRATOR SAVINGS:
├─ Money: similar (electricity vs longer subscription)
├─ Time: 4 months of user freedom
└─ Mobility: priceless
```

---

## 12. Risks and Mitigations

### 12.1 Risk: OpenAI ban for automation

```text
PROBABILITY: Medium
IMPACT: High (loss of ChatGPT Plus account)

MITIGATION:
1. Use a SEPARATE ChatGPT Plus account for orchestrator
   - Cost: +23€/month
   - Protects main account if banned
2. Add random delays between actions (2-8 seconds)
3. Use realistic mouse movements (not direct clicks)
4. Avoid running 24/7 — pause overnight
5. Don't exceed normal human usage patterns
6. Plan B: switch to Anthropic Claude (more automation-friendly)
```

### 12.2 Risk: ChatGPT or Codex UI changes

```text
PROBABILITY: High (happens every few months)
IMPACT: Medium (orchestrator breaks until fixed)

MITIGATION:
1. Use robust selectors (data-testid > class names)
2. Monitor for UI changes via daily smoke tests
3. Maintain a "selectors.yaml" file for easy updates
4. Telegram alert when selectors fail
5. Graceful degradation: escalate to user when stuck
6. Budget 1-2h/month for maintenance
```

### 12.3 Risk: ChatGPT formulates differently

```text
PROBABILITY: Medium-High
IMPACT: Low (LLM layer catches most)

MITIGATION:
1. Strict template (Section 6) keeps 90%+ in regex
2. LLM fallback for the rest
3. Continuous improvement: add new regex patterns as 
   observed deviations
4. Telegram escalation for truly ambiguous cases
5. User can answer ambiguous questions on the go
```

### 12.4 Risk: Codex generates broken code

```text
PROBABILITY: Medium
IMPACT: Medium (wasted patches)

MITIGATION:
1. Tests run automatically after each patch
2. Failed tests trigger Codex to fix (max 3 attempts)
3. Persistent failure → escalate via Telegram
4. ChatGPT (intelligent coordinator) catches obvious issues
5. Weekly Claude Code audit catches subtle issues
6. Model routing: complex patches use GPT-5.5 (less buggy)
```

### 12.5 Risk: Tower hardware failure

```text
PROBABILITY: Low-Medium (10-year-old hardware)
IMPACT: High (project stops)

MITIGATION:
1. UPS battery backup (~50€) to handle brief outages
2. Critical state in PostgreSQL (survives reboots)
3. systemd auto-restart on crash
4. Telegram alerts on hardware issues
5. Monthly backup of orchestrator state to VPS
6. Plan B: rent a small cloud VM (~10€/month) if needed
```

### 12.6 Risk: Infinite loop or runaway costs

```text
PROBABILITY: Low (with safeguards)
IMPACT: High (Codex credit drain)

MITIGATION:
1. Max 50 patches/day (hard limit)
2. Max 3 attempts per patch
3. Idle timeout: pause if no progress in 30 min
4. Telegram alert if rate of message > 1/min sustained
5. Daily stats review (automated)
6. Manual /pause command from anywhere
```

---

## 13. Security Considerations

### 13.1 SSH security

```text
- SSH key authentication only (no passwords)
- Disable root SSH login
- UFW firewall: only allow SSH (port 22) from local network
- For remote access: use Hostinger VPS as jump host
- fail2ban to ban brute-force attempts
- Regular SSH key rotation (every 6 months)
```

### 13.2 Credential management

```text
- Never store ChatGPT password in code
- Use playwright persistent context (saved login state)
- Encrypt config.yaml with system-level encryption
- Telegram bot token: stored in environment variable
- VPS SSH key: stored with 600 permissions
- No credentials in git repository (use .gitignore)
```

### 13.3 Data privacy

```text
- All orchestrator logs stay on tower (not cloud)
- ChatGPT messages may contain sensitive code
- VPS connection encrypted (SSH)
- Telegram messages encrypted in transit
- Daily logs auto-delete after 30 days
- No telemetry sent anywhere
```

---

## 14. Maintenance Workflow

```text
DAILY:
- Glance at Telegram for any alerts (30 seconds)
- Check /status before bed if patches running

WEEKLY:
- Review /stats for the week
- Check if escalations are increasing (sign of new pattern needed)
- Add new regex patterns observed in escalations
- Restart tower if memory usage > 80% (cron Sunday 4am)

MONTHLY:
- Update Ubuntu packages: sudo apt update && apt upgrade
- Update Playwright: pip install --upgrade playwright
- Update Ollama and Qwen: ollama pull qwen2.5:3b
- Run Claude Code audit on V1 code so far
- Review monthly stats trends

QUARTERLY:
- Backup orchestrator state and configs
- Review selectors.yaml against current ChatGPT UI
- Rotate SSH keys
- Review and update model routing guidelines
```

---

## 15. Migration Path: From Manual to Orchestrator

```text
WEEK 1 — Code manually with strict format
- User starts using the Section 6 template TODAY
- ChatGPT learns to follow the format
- User validates that format works in practice
- No orchestrator yet, just discipline

WEEK 2-5 — Build orchestrator while coding manually
- Set up tower (week 2)
- Set up laptop (week 2)
- Build core orchestrator (weeks 3-4)
- Test on simple patches (week 5)
- Keep coding V1 manually in parallel

WEEK 6 — Soft launch
- Run orchestrator on simple patches only
- Continue manual on complex patches
- Validate quality and reliability
- Adjust thresholds

WEEK 7+ — Full autonomous
- All patches go through orchestrator
- User reviews via Telegram
- User intervenes only on escalations
- V1 progresses while user lives life

= No "big bang" switch. Smooth transition.
```

---

## 16. Success Metrics

```text
WHAT SUCCESS LOOKS LIKE:

WEEKLY METRICS (target after week 8):
├─ Patches completed/week: 30-50
├─ Escalation rate: < 10%
├─ Test pass rate (first try): > 70%
├─ Test pass rate (after retries): > 95%
├─ User intervention time: < 1h/day
├─ Uptime: > 95%
└─ Model distribution matches plan (~50/35/15)

V1 COMPLETION:
├─ Original estimate: 8 months manual
├─ Target with orchestrator: 4 months
├─ Stretch goal: 3 months
└─ Realistic: 4-5 months

QUALITATIVE:
├─ User can travel without project stopping
├─ User feels less mental load
├─ User maintains velocity even when fatigued
└─ User learns automation skills along the way
```

---

## 17. Non-Goals

```text
❌ Replacing ChatGPT or Claude's judgment
   The orchestrator is a PIPELINE, not a brain.

❌ Coding without supervision
   User reviews via Telegram, validates milestones.

❌ Running 24/7 to save time
   Codex rate limits prevent this; pretending otherwise wastes setup.

❌ Building general AI agents
   This is a SPECIFIC tool for THIS project.

❌ Open-sourcing the orchestrator
   Personal tool, not a product. Keep simple.

❌ Adding more features beyond V1 needs
   Resist scope creep. Build minimum viable orchestrator.

❌ Supporting multiple users
   Single-user system. Keep complexity low.
```

---

## 18. After V1: What Becomes of the Orchestrator?

```text
SCENARIO A — Continue using for V2-V5 (recommended)
├─ Same orchestrator powers V2, V3, V4, V5
├─ ROI keeps growing
├─ Minor tweaks for new patterns
└─ Total OS done in 12-18 months instead of 24-36

SCENARIO B — Decommission after V1
├─ User decides manual is fine for V2+
├─ Tower repurposed (e.g., home media server)
├─ Knowledge gained remains valuable
└─ No loss

SCENARIO C — Open-source contribution
├─ Generalize for community use
├─ Different project — not in scope here
└─ Side adventure if interested

Most likely: A. Once you have the orchestrator,
you'll wonder how you ever lived without it.
```

---

## 19. Open Questions to Resolve During Setup

```text
TO ANSWER WHEN IMPLEMENTING:

1. ChatGPT Plus: same account or separate for orchestrator?
   Recommendation: SEPARATE (protects main account)

2. Which Codex client: CLI or Web?
   CLI is simpler to automate, less UI to monitor.
   Recommendation: CLI (Codex CLI on the tower)

3. Browser visibility: headless or visible?
   Headless = less RAM, runs in server mode.
   Visible = easier to debug initially.
   Recommendation: Visible during dev, headless in prod.

4. Telegram bot in same process or separate?
   Separate process = more resilient (bot stays up if 
   orchestrator crashes).
   Recommendation: Separate (systemd service each).

5. Log retention period?
   Recommendation: 30 days local, 7 days for verbose debug.

6. Backup strategy?
   Recommendation: Weekly rsync to VPS, monthly to external HDD.
```

---

## 20. References

- `08_NON_NEGOTIABLE_RULES.md` — backend authority
- `30_AI_ROUTING_AND_SCORING_POLICY.md` — model selection patterns
- `35_QWEN_SETUP_AND_PROMPTS.md` — Qwen deployment reference
- ChatGPT custom instructions documentation
- Codex pricing: https://chatgpt.com/codex/pricing/
- Codex speed modes: https://developers.openai.com/codex/speed
- Playwright Python docs: https://playwright.dev/python/
- Ollama documentation: https://ollama.com/docs

---

## 21. Final Note

```text
THIS IS NOT A FEATURE OF THE OS.
THIS IS A FACTORY THAT BUILDS THE OS.

The orchestrator is the means, not the end.
Its purpose is to free the user's time and energy
so they can focus on the parts of the project that
require real thought:
- Architectural decisions
- Product vision
- Quality control via Claude Code audits
- Strategic prioritization

The mechanical work — copy, paste, upload, test —
is delegated to the machine.

This is the right tool at the right time:
- Codex is mature enough to follow instructions
- ChatGPT is smart enough to orchestrate
- Playwright is stable enough to automate
- The user has the hardware already

In 4 months, V1 is done.
In 6-12 months, the full ecosystem.
In 18 months, the HUD final vision (doc 55).

This orchestrator is the bridge.
```

---

**Document version:** 1.0
**Status:** Dev infrastructure specification — implement before V1 continues
**Last updated:** 2026-05-14
