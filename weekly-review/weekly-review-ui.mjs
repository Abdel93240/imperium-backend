import {
  ACTION_LABELS,
  WeeklyReviewApiClient,
  actionNeedsUserText,
  buildIdempotencyKey,
  formatApiError,
  shouldPollConversation,
} from "./weekly-review-api.mjs";

const STORAGE_KEYS = {
  apiBaseUrl: "imperium_wr_api_base_url",
  accessToken: "imperium_access_token",
};

const POLL_INTERVAL_MS = 2500;
const MAX_POLL_ATTEMPTS = 24;

const state = {
  client: null,
  snapshot: null,
  error: "",
  loading: false,
  actionBusy: false,
  polling: false,
  pollTimer: null,
  pollAttempts: 0,
};

const el = {};

window.addEventListener("DOMContentLoaded", () => {
  bindElements();
  hydrateConfig();
  bindEvents();
  refreshCurrent();
});

function bindElements() {
  for (const id of [
    "apiBaseUrl",
    "accessToken",
    "saveConfig",
    "refresh",
    "statusBar",
    "errorBox",
    "sessionCard",
    "summaryCard",
    "messagesCard",
    "draftCard",
    "actionsCard",
    "actionText",
    "actionHint",
    "actionsList",
    "debugCard",
  ]) {
    el[id] = document.getElementById(id);
  }
}

function hydrateConfig() {
  el.apiBaseUrl.value = localStorage.getItem(STORAGE_KEYS.apiBaseUrl) || window.location.origin;
  el.accessToken.value = localStorage.getItem(STORAGE_KEYS.accessToken) || "";
  rebuildClient();
}

function bindEvents() {
  el.saveConfig.addEventListener("click", () => {
    localStorage.setItem(STORAGE_KEYS.apiBaseUrl, el.apiBaseUrl.value.trim());
    localStorage.setItem(STORAGE_KEYS.accessToken, el.accessToken.value.trim());
    rebuildClient();
    refreshCurrent();
  });
  el.refresh.addEventListener("click", () => refreshCurrent());
}

function rebuildClient() {
  state.client = new WeeklyReviewApiClient({
    baseUrl: el.apiBaseUrl.value,
    token: el.accessToken.value,
  });
}

async function refreshCurrent({ keepPolling = false } = {}) {
  if (!state.client) {
    rebuildClient();
  }
  state.loading = !keepPolling;
  state.error = "";
  render();
  try {
    const snapshot = await state.client.getCurrent();
    state.snapshot = snapshot;
    state.error = "";
    if (shouldPollConversation(snapshot?.conversation)) {
      startPolling();
    } else {
      stopPolling();
    }
  } catch (error) {
    state.error = formatApiError(error);
    stopPolling();
  } finally {
    state.loading = false;
    render();
  }
}

function startPolling() {
  if (state.polling) {
    return;
  }
  state.polling = true;
  state.pollAttempts = 0;
  state.pollTimer = window.setInterval(async () => {
    state.pollAttempts += 1;
    if (state.pollAttempts > MAX_POLL_ATTEMPTS) {
      stopPolling();
      render();
      return;
    }
    await refreshCurrent({ keepPolling: true });
  }, POLL_INTERVAL_MS);
}

function stopPolling() {
  if (state.pollTimer) {
    window.clearInterval(state.pollTimer);
  }
  state.pollTimer = null;
  state.polling = false;
  state.pollAttempts = 0;
}

function render() {
  renderStatus();
  renderError();
  const conversation = state.snapshot?.conversation || null;
  const session = state.snapshot?.session || conversation?.session || null;
  renderSession(session, conversation);
  renderSummary(conversation);
  renderMessages(conversation);
  renderDraft(conversation);
  renderActions(session, conversation);
  renderDebug(conversation);
}

function renderStatus() {
  const pieces = [];
  if (state.loading) {
    pieces.push("Loading");
  }
  if (state.actionBusy) {
    pieces.push("Sending action");
  }
  if (state.polling) {
    pieces.push(`Polling ${state.pollAttempts}/${MAX_POLL_ATTEMPTS}`);
  }
  if (pieces.length === 0) {
    pieces.push("Ready");
  }
  el.statusBar.textContent = pieces.join(" | ");
}

function renderError() {
  el.errorBox.textContent = state.error;
  el.errorBox.hidden = !state.error;
}

function renderSession(session, conversation) {
  clear(el.sessionCard);
  el.sessionCard.append(
    sectionHeader("Status"),
    kvGrid([
      ["Session", session?.id || "none"],
      ["Week", session ? `${session.week_start} -> ${session.week_end}` : "none"],
      ["Session status", session?.status || "none"],
      ["UI state", conversation?.ui_state || "none"],
      ["Allowed actions", (conversation?.allowed_actions || []).join(", ") || "none"],
    ]),
  );
  if (!session) {
    el.sessionCard.append(emptyBlock("No active Weekly Review found."));
  }
  if (conversation?.flags) {
    el.sessionCard.append(renderFlags(conversation.flags));
  }
}

function renderSummary(conversation) {
  clear(el.summaryCard);
  el.summaryCard.append(sectionHeader("Initial Summary"));
  const result = conversation?.initial_ai_result;
  if (!result) {
    el.summaryCard.append(stateBlock(conversation?.ui_state));
    return;
  }
  el.summaryCard.append(resultHeader(result));
  el.summaryCard.append(renderPayloadSummary(result.result_payload));
}

function renderMessages(conversation) {
  clear(el.messagesCard);
  el.messagesCard.append(sectionHeader("Messages"));
  const messages = conversation?.messages || [];
  if (messages.length === 0) {
    el.messagesCard.append(emptyBlock("No messages yet."));
    return;
  }
  for (const message of messages) {
    const row = document.createElement("article");
    row.className = "message";
    row.append(
      badge(`${message.role} / ${message.message_type}`),
      textBlock(message.content || summarizePayload(message.payload) || "No text content."),
      smallText(formatDate(message.created_at)),
    );
    el.messagesCard.append(row);
  }
}

function renderDraft(conversation) {
  clear(el.draftCard);
  el.draftCard.append(sectionHeader("Draft Candidates"));
  const reports = conversation?.final_report_candidates || [];
  if (reports.length === 0) {
    el.draftCard.append(emptyBlock("No draft candidate yet."));
    return;
  }
  for (const report of reports) {
    const article = document.createElement("article");
    article.className = `candidate candidate-${report.status}`;
    article.append(
      badge(report.status),
      textBlock(report.report_payload?.summary || report.report_payload?.title || "Draft candidate"),
      preBlock(report.report_markdown || ""),
      kvGrid([
        ["Created", formatDate(report.created_at)],
        ["Approved", formatDate(report.approved_at)],
        ["Stored", formatDate(report.stored_at)],
      ]),
    );
    el.draftCard.append(article);
  }
}

function renderActions(session, conversation) {
  clear(el.actionsList);
  const actions = conversation?.allowed_actions || [];
  el.actionText.disabled = state.actionBusy || actions.length === 0;
  el.actionHint.textContent = actionHint(conversation?.ui_state, actions);
  if (!session || actions.length === 0) {
    el.actionsList.append(emptyBlock("No action available from backend."));
    return;
  }
  for (const action of actions) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `button ${action === "reject_draft" ? "button-danger" : "button-primary"}`;
    button.textContent = ACTION_LABELS[action] || action;
    button.disabled = state.actionBusy;
    button.addEventListener("click", () => submitAction(action, session.id));
    el.actionsList.append(button);
  }
}

function renderDebug(conversation) {
  clear(el.debugCard);
  el.debugCard.append(sectionHeader("Read Model"));
  if (!conversation) {
    el.debugCard.append(emptyBlock("No conversation snapshot."));
    return;
  }
  el.debugCard.append(
    kvGrid([
      ["Current AI task", conversation.current_ai_task?.id || "none"],
      ["Initial result", conversation.initial_ai_result?.id || "none"],
      ["Final result", conversation.final_ai_result?.id || "none"],
      ["Final candidates", String(conversation.final_report_candidates?.length || 0)],
    ]),
  );
}

async function submitAction(action, sessionId) {
  const text = el.actionText.value.trim();
  if (actionNeedsUserText(action) && !text) {
    state.error = "This action needs text.";
    render();
    return;
  }
  state.actionBusy = true;
  state.error = "";
  render();
  try {
    await state.client.postAction(action, sessionId, {
      content: text,
      idempotencyKey: buildIdempotencyKey(action, sessionId),
    });
    el.actionText.value = "";
    await refreshCurrent();
  } catch (error) {
    state.error = formatApiError(error);
  } finally {
    state.actionBusy = false;
    render();
  }
}

function renderFlags(flags) {
  const wrapper = document.createElement("div");
  wrapper.className = "flag-grid";
  for (const [key, value] of Object.entries(flags)) {
    const item = document.createElement("span");
    item.className = `flag ${value ? "flag-on" : "flag-off"}`;
    item.textContent = `${key}: ${String(value)}`;
    wrapper.append(item);
  }
  return wrapper;
}

function renderPayloadSummary(payload) {
  const wrapper = document.createElement("div");
  wrapper.className = "payload-summary";
  if (!payload || typeof payload !== "object") {
    wrapper.append(textBlock("No summary payload."));
    return wrapper;
  }
  if (payload.summary) {
    wrapper.append(textBlock(payload.summary));
  }
  if (Array.isArray(payload.sections)) {
    for (const section of payload.sections) {
      const article = document.createElement("article");
      article.className = "summary-section";
      article.append(strongText(section.title || "Section"), textBlock(section.content || ""));
      wrapper.append(article);
    }
  }
  if (Array.isArray(payload.questions) && payload.questions.length > 0) {
    const list = document.createElement("ul");
    list.className = "question-list";
    for (const question of payload.questions) {
      const item = document.createElement("li");
      item.textContent = question;
      list.append(item);
    }
    wrapper.append(list);
  }
  return wrapper;
}

function resultHeader(result) {
  return kvGrid([
    ["Result type", result.result_type],
    ["Provider", result.provider || "unknown"],
    ["Model", result.model_used || "unknown"],
    ["Confidence", result.confidence == null ? "unknown" : String(result.confidence)],
    ["Status", result.status],
  ]);
}

function stateBlock(uiState) {
  const messageByState = {
    preparing_initial_summary: "AI summary is being prepared.",
    integrating_answers: "Answer integration is in progress.",
    initial_summary_ready: "Summary is ready.",
    waiting_for_user_answer: "Waiting for your answer.",
    draft_ready: "Draft candidate is ready.",
    approved: "Draft is approved and ready to store.",
    stored: "Final report is stored.",
    failed: "Weekly Review failed.",
    closed: "Weekly Review is closed.",
  };
  return emptyBlock(messageByState[uiState] || "Summary is not available yet.");
}

function actionHint(uiState, actions) {
  if (actions.includes("answer")) {
    return "Write your answer before sending.";
  }
  if (actions.includes("request_changes") || actions.includes("reject_draft")) {
    return "Write the change or rejection note before sending.";
  }
  if (actions.includes("store_final_report")) {
    return "Store marks the approved report as persisted. It does not write memory.";
  }
  if (uiState === "integrating_answers" || uiState === "preparing_initial_summary") {
    return "Backend is waiting for an AI result proposal.";
  }
  return "Actions come only from backend allowed_actions.";
}

function sectionHeader(title) {
  const header = document.createElement("div");
  header.className = "section-header";
  const h2 = document.createElement("h2");
  h2.textContent = title;
  header.append(h2);
  return header;
}

function kvGrid(rows) {
  const grid = document.createElement("dl");
  grid.className = "kv-grid";
  for (const [key, value] of rows) {
    const dt = document.createElement("dt");
    dt.textContent = key;
    const dd = document.createElement("dd");
    dd.textContent = value || "none";
    grid.append(dt, dd);
  }
  return grid;
}

function badge(value) {
  const span = document.createElement("span");
  span.className = "badge";
  span.textContent = value;
  return span;
}

function textBlock(value) {
  const p = document.createElement("p");
  p.textContent = value || "";
  return p;
}

function strongText(value) {
  const h3 = document.createElement("h3");
  h3.textContent = value || "";
  return h3;
}

function smallText(value) {
  const small = document.createElement("small");
  small.textContent = value || "";
  return small;
}

function preBlock(value) {
  const pre = document.createElement("pre");
  pre.textContent = value || "";
  return pre;
}

function emptyBlock(value) {
  const p = document.createElement("p");
  p.className = "empty";
  p.textContent = value;
  return p;
}

function clear(node) {
  node.replaceChildren();
}

function formatDate(value) {
  if (!value) {
    return "none";
  }
  try {
    return new Intl.DateTimeFormat("en-GB", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return String(value);
  }
}

function summarizePayload(payload) {
  if (!payload || typeof payload !== "object") {
    return "";
  }
  if (payload.summary) {
    return payload.summary;
  }
  if (payload.action) {
    return payload.action;
  }
  return JSON.stringify(payload);
}
