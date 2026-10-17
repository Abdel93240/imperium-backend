// Terminal IA partagé (maquette 06) : JetBrains Mono, > IMPERIUM / > VOUS, sans bulles.
import { h, clock, icon, iconBtn, toast, pad } from "./core.js";
import { svc } from "./services/index.js";
import { app } from "./app.js";

const DEMO_TRANSCRIPTS = ["Quels documents dois-je préparer pour la préfecture ?", "Oui, je valide.", "Mets une nouvelle échéance vendredi.", "Garde la lecture ce soir."];

export function terminal({ ctx = { kind: "standard" }, title = "IMPERIUM / TERMINAL", initial = [], onClose, onReply, readOnly = false, footer = null, sub = null }) {
  const history = initial.map(([who, text]) => ({ who, text }));
  const log = h("div", { class: "term-log", "aria-live": "polite" });
  const draw = (m) => h("div", { class: `msg ${m.who === "VOUS" ? "me" : ""}` }, h("div", { class: "who" }, "> " + m.who, m.pendingSend ? h("span", { class: "orange small" }, "  · en attente d'envoi") : null), h("div", { class: m.typing ? "typing" : "" }, m.text));
  const toBottom = () => { log.scrollTop = log.scrollHeight; };
  const renderLog = () => { log.replaceChildren(...history.map(draw)); toBottom(); requestAnimationFrame(toBottom); };
  renderLog();

  const ta = h("textarea", { rows: 1, placeholder: "Écris ton message…", "aria-label": "Message", enterkeyhint: "send" });
  ta.addEventListener("input", () => { ta.style.height = "auto"; ta.style.height = Math.min(120, ta.scrollHeight) + "px"; });
  ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } });
  ta.addEventListener("focus", () => setTimeout(() => { toBottom(); ta.scrollIntoView({ block: "nearest" }); }, 300));
  const hint = h("div", { class: "term-hint" }, "Maintenir pour parler");
  const sendBtn = iconBtn("send", "Envoyer", () => send(), { boxed: true });
  const mic = iconBtn("microphone", "Maintenir pour parler", null, { boxed: true });
  const inputRow = h("div", { class: "term-input" }, h("span", { class: "prompt" }, ">"), ta, mic, sendBtn);

  // Push-to-talk : l'onde remplace le champ ; relâchement → transcription dans le champ, envoi manuel.
  let rec = null;
  mic.addEventListener("pointerdown", (e) => {
    e.preventDefault(); mic.setPointerCapture?.(e.pointerId);
    const t0 = clock.now(); const timer = h("span", { class: "mono gold small" }, "00:00");
    const wave = h("div", { class: "wave", "aria-hidden": "true" }, Array.from({ length: 44 }, (_, i) => h("i", { style: `animation-delay:${(i * 73) % 900}ms` })));
    rec = { t0, iv: setInterval(() => { const s = Math.floor((clock.now() - t0) / 1000); timer.textContent = `${pad(Math.floor(s / 60))}:${pad(s % 60)}`; }, 250) };
    ta.style.display = "none"; inputRow.querySelector(".prompt").style.display = "none";
    inputRow.insertBefore(wave, mic); inputRow.insertBefore(timer, mic);
    rec.nodes = [wave, timer]; mic.classList.add("on"); mic.replaceChildren(icon("microphone", "danger", 22));
    hint.textContent = "Écoute en cours · Relâcher pour terminer · onde de démonstration (pas de micro réel)";
  });
  const stop = () => {
    if (!rec) return; clearInterval(rec.iv); rec.nodes.forEach((n) => n.remove());
    ta.style.display = ""; inputRow.querySelector(".prompt").style.display = ""; mic.classList.remove("on"); mic.replaceChildren(icon("microphone", "gold", 22));
    hint.textContent = "Maintenir pour parler";
    const dur = clock.now() - rec.t0; rec = null;
    if (dur < 700) { toast("Je n'ai pas compris, réessaie"); return; }
    const t = DEMO_TRANSCRIPTS[Math.floor(Math.random() * DEMO_TRANSCRIPTS.length)];
    ta.value = ta.value ? ta.value.trimEnd() + " " + t : t; ta.dispatchEvent(new Event("input")); ta.focus();
    toast("Transcription de démonstration insérée : relis puis envoie.");
  };
  mic.addEventListener("pointerup", stop); mic.addEventListener("pointercancel", stop);

  let busy = false;
  async function send() {
    const text = ta.value.trim(); if (!text || busy) return;
    ta.value = ""; ta.dispatchEvent(new Event("input"));
    const mine = { who: "VOUS", text }; history.push(mine);
    if (app.offline) { mine.pendingSend = true; renderLog(); return; }
    const typing = { who: "IMPERIUM", text: "", typing: true }; history.push(typing); renderLog();
    busy = true; sendBtn.disabled = true;
    try {
      const r = onReply ? await onReply(text, history) : await svc.terminalSend(ctx, text, history);
      typing.typing = false; typing.text = r?.text ?? "";
      if (r?.pending) typing.pending = r.pending;
      if (!typing.text) history.splice(history.indexOf(typing), 1);
      renderLog(); api.onResult?.(r);
    } catch (e) { typing.typing = false; typing.text = "Je n'arrive pas à joindre Imperium. Ton message est conservé : réessaie."; ta.value = text; renderLog(); }
    finally { busy = false; sendBtn.disabled = false; }
  }

  const el = h("section", { class: "term", "aria-label": "Terminal IA" },
    h("div", { class: "term-head" }, h("div", { class: "grow" }, h("div", { class: "ttl" }, title), sub ? h("div", { class: "small muted", style: "margin-top:4px" }, sub) : null),
      onClose ? h("button", { class: "icon-btn", "aria-label": "Fermer", "data-close": "1", onclick: onClose }, icon("close", "gold", 22)) : null),
    ctx.label ? h("div", { class: "term-ctx" }, ctx.label) : null,
    ctx.attach || null,
    log,
    readOnly ? h("div", { class: "term-hint", style: "padding:12px" }, "Conversation archivée · lecture seule") : [inputRow, hint],
    footer);
  const api = { el, history, push(who, text) { history.push({ who, text }); renderLog(); }, flushPending() { history.forEach((m) => delete m.pendingSend); renderLog(); } };
  return api;
}
