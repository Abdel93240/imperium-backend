import assert from "node:assert/strict";
import test from "node:test";

import {
  WeeklyReviewApiClient,
  buildIdempotencyKey,
  buildWeeklyReviewAction,
  shouldPollConversation,
  stripRawPayload,
} from "./weekly-review-api.mjs";

test("buildWeeklyReviewAction maps allowed actions to backend endpoints", () => {
  const sessionId = "session-1";

  assert.equal(buildWeeklyReviewAction("answer", sessionId, "Reality check").path, `/api/imperium/weekly-review/${sessionId}/answer`);
  assert.equal(
    buildWeeklyReviewAction("approve_draft", sessionId).path,
    `/api/imperium/weekly-review/${sessionId}/draft/approve`,
  );
  assert.equal(
    buildWeeklyReviewAction("store_final_report", sessionId).path,
    `/api/imperium/weekly-review/${sessionId}/draft/store`,
  );
});

test("buildWeeklyReviewAction adapts reject body to backend schema", () => {
  const action = buildWeeklyReviewAction("reject_draft", "session-1", "Too vague");

  assert.deepEqual(action.body, {
    reason: "Too vague",
    payload: {
      source: "imperium_frontend_wr_v1",
      action: "reject_draft",
    },
  });
});

test("stripRawPayload removes provider raw payload recursively", () => {
  const snapshot = {
    conversation: {
      initial_ai_result: {
        result_payload: { summary: "Visible" },
        raw_payload: { secret_prompt: "DO_NOT_EXPOSE" },
      },
      final_ai_result: {
        nested: [{ raw_payload: { provider_trace: true }, visible: true }],
      },
    },
  };

  const clean = stripRawPayload(snapshot);
  const serialized = JSON.stringify(clean);

  assert.equal("raw_payload" in clean.conversation.initial_ai_result, false);
  assert.equal(serialized.includes("DO_NOT_EXPOSE"), false);
  assert.equal(serialized.includes("raw_payload"), false);
});

test("shouldPollConversation follows backend waiting flags and states", () => {
  assert.equal(shouldPollConversation({ ui_state: "integrating_answers", flags: {} }), true);
  assert.equal(shouldPollConversation({ ui_state: "draft_ready", flags: { is_waiting_for_ai: false } }), false);
  assert.equal(shouldPollConversation({ ui_state: "approved", flags: { is_waiting_for_ai: true } }), true);
});

test("idempotency key is unique and action scoped", () => {
  const first = buildIdempotencyKey("approve_draft", "session-1");
  const second = buildIdempotencyKey("approve_draft", "session-1");

  assert.match(first, /^wr-v1:approve_draft:session-1:/);
  assert.notEqual(first, second);
});

test("client sends Authorization and Idempotency-Key on approve", async () => {
  const calls = [];
  const client = new WeeklyReviewApiClient({
    baseUrl: "http://imperium.local",
    token: "ACCESS",
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });

  await client.postAction("approve_draft", "session-1", {
    idempotencyKey: "idem-approve",
  });

  assert.equal(calls[0].url, "http://imperium.local/api/imperium/weekly-review/session-1/draft/approve");
  assert.equal(calls[0].init.headers.Authorization, "Bearer ACCESS");
  assert.equal(calls[0].init.headers["Idempotency-Key"], "idem-approve");
  assert.equal(calls[0].init.headers["Content-Type"], "application/json");
});

test("client sends store endpoint with Idempotency-Key", async () => {
  const calls = [];
  const client = new WeeklyReviewApiClient({
    baseUrl: "http://imperium.local/",
    token: "ACCESS",
    fetchImpl: async (url, init) => {
      calls.push({ url, init });
      return new Response(JSON.stringify({ status: "stored" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });

  await client.postAction("store_final_report", "session-1", {
    idempotencyKey: "idem-store",
  });

  assert.equal(calls[0].url, "http://imperium.local/api/imperium/weekly-review/session-1/draft/store");
  assert.equal(calls[0].init.headers["Idempotency-Key"], "idem-store");
});
