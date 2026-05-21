export const FRONTEND_SOURCE = "imperium_frontend_wr_v1";

export const ACTION_LABELS = {
  answer: "Answer",
  approve_draft: "Approve draft",
  reject_draft: "Reject draft",
  request_changes: "Request changes",
  store_final_report: "Store final report",
};

export const WAITING_UI_STATES = new Set(["preparing_initial_summary", "integrating_answers"]);

export class WeeklyReviewApiError extends Error {
  constructor(message, { status = 0, detail = null } = {}) {
    super(message);
    this.name = "WeeklyReviewApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function normalizeApiBaseUrl(value) {
  const trimmed = String(value || "").trim();
  return trimmed.replace(/\/+$/, "") || globalThis.location?.origin || "http://127.0.0.1:8000";
}

export function buildIdempotencyKey(action, sessionId) {
  const random =
    globalThis.crypto && typeof globalThis.crypto.randomUUID === "function"
      ? globalThis.crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `wr-v1:${action}:${sessionId}:${random}`;
}

export function shouldPollConversation(conversation) {
  if (!conversation) {
    return false;
  }
  return Boolean(conversation.flags?.is_waiting_for_ai || WAITING_UI_STATES.has(conversation.ui_state));
}

export function actionNeedsUserText(action) {
  return action === "answer" || action === "request_changes" || action === "reject_draft";
}

export function buildWeeklyReviewAction(action, sessionId, userText = "") {
  const content = String(userText || "").trim();
  const noteByAction = {
    answer: content,
    approve_draft: "Approved from frontend Weekly Review V1.",
    reject_draft: content || "Rejected from frontend Weekly Review V1.",
    request_changes: content,
    store_final_report: "Stored from frontend Weekly Review V1.",
  };

  const sharedPayload = {
    source: FRONTEND_SOURCE,
    action,
  };

  switch (action) {
    case "answer":
      return {
        path: `/api/imperium/weekly-review/${sessionId}/answer`,
        body: {
          content: noteByAction.answer,
          payload: sharedPayload,
        },
      };
    case "approve_draft":
      return {
        path: `/api/imperium/weekly-review/${sessionId}/draft/approve`,
        body: {
          content: noteByAction.approve_draft,
          payload: sharedPayload,
        },
      };
    case "reject_draft":
      return {
        path: `/api/imperium/weekly-review/${sessionId}/draft/reject`,
        body: {
          reason: noteByAction.reject_draft,
          payload: sharedPayload,
        },
      };
    case "request_changes":
      return {
        path: `/api/imperium/weekly-review/${sessionId}/draft/request-changes`,
        body: {
          content: noteByAction.request_changes,
          payload: sharedPayload,
        },
      };
    case "store_final_report":
      return {
        path: `/api/imperium/weekly-review/${sessionId}/draft/store`,
        body: {
          content: noteByAction.store_final_report,
          payload: sharedPayload,
        },
      };
    default:
      throw new WeeklyReviewApiError(`Unsupported weekly review action: ${action}`);
  }
}

export function stripRawPayload(value) {
  if (Array.isArray(value)) {
    return value.map((item) => stripRawPayload(item));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value)
        .filter(([key]) => key !== "raw_payload")
        .map(([key, entry]) => [key, stripRawPayload(entry)]),
    );
  }
  return value;
}

export function formatApiError(error) {
  if (!(error instanceof WeeklyReviewApiError)) {
    return "Technical error. Please retry.";
  }
  const detail = typeof error.detail === "string" ? error.detail : error.detail?.detail || error.message;
  if (error.status === 401) {
    return "Session expired. Sign in again.";
  }
  if (error.status === 404) {
    return "No active Weekly Review found.";
  }
  if (error.status === 409) {
    return detail || "Action already processed or no longer allowed.";
  }
  if (error.status === 422) {
    return detail || "Validation error. Check the action input.";
  }
  if (error.status >= 500) {
    return "Backend technical error. Check Imperium API logs.";
  }
  return detail || error.message;
}

export class WeeklyReviewApiClient {
  constructor({ baseUrl, token, fetchImpl } = {}) {
    this.baseUrl = normalizeApiBaseUrl(baseUrl);
    this.token = token || "";
    this.fetchImpl = fetchImpl || globalThis.fetch.bind(globalThis);
  }

  async getCurrent() {
    return this.#request("/api/imperium/weekly-review/current");
  }

  async getConversation(sessionId) {
    return this.#request(`/api/imperium/weekly-review/${sessionId}/conversation`);
  }

  async getDebugStatus(sessionId) {
    return this.#request(`/api/imperium/weekly-review/${sessionId}/debug-status`);
  }

  async postAction(action, sessionId, { content = "", idempotencyKey } = {}) {
    const actionRequest = buildWeeklyReviewAction(action, sessionId, content);
    return this.#request(actionRequest.path, {
      method: "POST",
      idempotencyKey: idempotencyKey || buildIdempotencyKey(action, sessionId),
      body: actionRequest.body,
    });
  }

  async #request(path, { method = "GET", body, idempotencyKey } = {}) {
    if (!this.fetchImpl) {
      throw new WeeklyReviewApiError("Fetch API is not available.");
    }
    const headers = {
      Accept: "application/json",
    };
    if (this.token) {
      headers.Authorization = `Bearer ${this.token}`;
    }
    if (method !== "GET") {
      headers["Content-Type"] = "application/json";
      headers["Idempotency-Key"] = idempotencyKey;
    }

    const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      method,
      headers,
      body: method === "GET" ? undefined : JSON.stringify(body || {}),
    });
    const payload = await readJsonResponse(response);
    if (!response.ok) {
      throw new WeeklyReviewApiError(formatResponseError(response.status, payload), {
        status: response.status,
        detail: payload,
      });
    }
    return stripRawPayload(payload);
  }
}

async function readJsonResponse(response) {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

function formatResponseError(status, payload) {
  const detail = payload?.detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || JSON.stringify(item)).join("; ");
  }
  return `Weekly Review request failed with status ${status}.`;
}
