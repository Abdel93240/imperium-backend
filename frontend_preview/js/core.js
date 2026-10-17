// Socle UI : création d'éléments, icônes, formats, fenêtres, toasts.

export function h(tag, props, ...children) {
  const el = document.createElement(tag);
  if (props) for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === "html") el.innerHTML = v;
    else if (k in el && typeof v !== "string") el[k] = v;
    else el.setAttribute(k, v === true ? "" : v);
  }
  append(el, children);
  return el;
}
function append(el, children) {
  for (const c of children.flat(Infinity)) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
}

// Composant à état local : rerender() remplace son contenu.
export function comp(render) {
  const holder = h("div", { style: "display:contents" });
  const api = { rerender() { holder.replaceChildren(...[render(api)].flat().filter(Boolean)); }, el: holder };
  holder.rerender = () => api.rerender();
  api.rerender();
  return holder;
}

const VARIANTS = {"ai_common":["gold","muted"],"alert":["danger","gold","muted","warning"],"arrow_down":["gold","muted"],"arrow_up":["gold","muted"],"attachment":["gold","muted"],"audio_file":["gold","muted"],"bank":["gold","muted"],"bell":["gold","muted"],"bubble_overlay":["gold","muted"],"camera":["gold","muted"],"cash":["gold","muted"],"check":["gold","muted","success"],"chevron_down":["gold","muted"],"chevron_left":["gold","muted"],"chevron_right":["gold","muted"],"chip":["gold","muted"],"close":["danger","gold","muted"],"cloud":["gold","muted"],"copy":["gold","muted"],"crypto":["gold","muted"],"database":["gold","muted"],"day_clock":["gold","muted"],"edit":["gold","muted"],"external":["gold","muted"],"eye":["gold","muted"],"eye_off":["gold","muted"],"file":["gold","muted"],"finance":["gold","muted"],"folder":["gold","muted"],"gallery":["gold","muted"],"import":["gold","muted"],"info":["gold","muted"],"key":["gold","muted"],"location":["gold","muted"],"logs":["gold","muted"],"memory":["gold","muted"],"microphone":["danger","gold","muted"],"minus":["gold","muted"],"nav_dashboard":["gold","muted"],"nav_history":["gold","muted"],"nav_operations":["gold","muted"],"nav_settings":["gold","muted"],"notes":["gold","muted"],"phone":["gold","muted"],"plus":["gold","muted"],"priorities":["gold","muted"],"programme":["gold","muted"],"projects":["gold","muted"],"refresh":["gold","muted","text"],"replan":["gold","muted"],"routines":["gold","muted"],"search":["gold","muted"],"send":["gold","muted","text"],"server":["danger","gold","muted","success"],"shield":["gold","muted"],"sliders":["gold","muted"],"stop":["gold","muted"],"sunrise":["gold","muted"],"trash":["danger","gold","muted"],"video_file":["gold","muted"],"warning":["danger","gold","muted","warning"],"weekly_review":["gold","muted"],"wifi_off":["gold","muted"]};
// Horloge : décalage réglable par le fournisseur de démonstration (horloge contrôlée).
export const clock = { offset: 0, now: () => Date.now() + clock.offset };
export function icon(name, variant = "gold", size = 24, label = "") {
  if (!VARIANTS[name]?.includes(variant)) variant = VARIANTS[name]?.includes("gold") ? "gold" : (VARIANTS[name] || ["gold"])[0];
  return h("img", { src: `assets/icons/${name}__${variant}.svg`, width: size, height: size, alt: label, "aria-hidden": label ? null : "true", style: `width:${size}px;height:${size}px` });
}

export function btn(label, opts = {}) {
  const { kind = "", onClick, icon: ic, iconVariant, disabled, big, block, title, iconRight } = opts;
  const b = h("button", { class: `btn ${kind} ${big ? "big" : ""} ${block ? "block" : ""}`, disabled, title, type: "button" },
    ic && !iconRight ? icon(ic, iconVariant || variantFor(kind), 18) : null, label, ic && iconRight ? icon(ic, iconVariant || variantFor(kind), 18) : null);
  if (onClick) b.addEventListener("click", (e) => onClick(e, b));
  return b;
}
function variantFor(kind) { return kind === "danger" ? "danger" : kind === "success" ? "success" : "gold"; }

export function iconBtn(name, label, onClick, opts = {}) {
  return h("button", { class: `icon-btn ${opts.boxed ? "boxed" : ""} ${opts.on ? "on" : ""}`, "aria-label": label, title: label, type: "button", disabled: opts.disabled, onclick: onClick },
    icon(name, opts.variant || "gold", opts.size || 22));
}

// Bouton d'enregistrement : se désactive pendant l'attente, empêche le double envoi.
export async function busy(button, fn) {
  if (button.dataset.busy) return;
  button.dataset.busy = "1"; const old = [...button.childNodes]; button.disabled = true;
  button.replaceChildren(h("span", { class: "spin" }), ...old.filter((n) => n.nodeType === 3));
  try { return await fn(); }
  catch (e) { toast(e?.message || "Échec de l'enregistrement. Réessaie."); }
  finally { if (button.isConnected) { button.replaceChildren(...old); button.disabled = false; } delete button.dataset.busy; }
}

export function toggle(on, onChange, label) {
  const t = h("button", { class: `toggle ${on ? "on" : ""}`, role: "switch", "aria-checked": String(!!on), "aria-label": label, type: "button" });
  t.addEventListener("click", () => { const v = !t.classList.contains("on"); t.classList.toggle("on", v); t.setAttribute("aria-checked", String(v)); onChange?.(v); });
  return t;
}
export function seg(options, value, onChange) {
  const wrap = h("div", { class: "seg", role: "radiogroup" });
  for (const o of options) {
    const b = h("button", { type: "button", class: o.value === value ? "on" : "", role: "radio", "aria-checked": String(o.value === value) }, o.icon ? icon(o.icon, o.iconVariant || "gold", 18) : null, o.label);
    b.addEventListener("click", () => { [...wrap.children].forEach((c) => { c.classList.remove("on"); c.setAttribute("aria-checked", "false"); }); b.classList.add("on"); b.setAttribute("aria-checked", "true"); onChange(o.value); });
    wrap.append(b);
  }
  return wrap;
}
export function select(options, value, onChange, attrs = {}) {
  const s = h("select", { class: "select", ...attrs }, options.map((o) => h("option", { value: o.value ?? o, selected: (o.value ?? o) === value }, o.label ?? o)));
  s.addEventListener("change", () => onChange(s.value));
  return s;
}
export function field(label, control, { optional, hint } = {}) {
  const id = control.id || (control.id = "f" + Math.random().toString(36).slice(2, 8));
  return h("div", { class: "field" }, h("label", { for: id }, label, optional ? h("span", { class: "opt" }, "Facultatif") : null), control, hint ? h("div", { class: "hint" }, hint) : null);
}
export function check(on, label, onChange) {
  const b = h("button", { class: "checkline", type: "button", role: "checkbox", "aria-checked": String(on) }, h("span", { class: `check ${on ? "on" : ""}` }), h("span", null, label));
  b.addEventListener("click", () => { on = !on; b.setAttribute("aria-checked", String(on)); b.firstChild.classList.toggle("on", on); onChange(on); });
  return b;
}
export const dot = (c) => h("span", { class: `dot ${c}` });

// ---------- Formats ----------
const eur = new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" });
export const fmtEUR = (n) => eur.format(n);
export const fmtSigned = (n) => (n > 0 ? "+" : n < 0 ? "−" : "") + eur.format(Math.abs(n));
export const pad = (n) => String(n).padStart(2, "0");
export const fmtHM = (d) => `${pad(new Date(d).getHours())}:${pad(new Date(d).getMinutes())}`;
export const fmtDM = (d) => `${pad(new Date(d).getDate())}/${pad(new Date(d).getMonth() + 1)}`;
export const fmtDMY = (d) => `${fmtDM(d)}/${new Date(d).getFullYear()}`;
const MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
export const fmtLong = (d) => `${new Date(d).getDate()} ${MOIS[new Date(d).getMonth()]}`;
// Durée sans rebouclage à 24 h.
export function fmtDur(ms) { const s = Math.max(0, Math.floor(Math.abs(ms) / 1000)); return `${pad(Math.floor(s / 3600))}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`; }
export function fmtMin(min) { const hh = Math.floor(min / 60), mm = min % 60; return hh ? `${hh} h${mm ? ` ${pad(mm)} min` : ""}` : `${mm} min`; }

// Chronomètres dérivés d'un instant (pas d'accumulation qui dérive).
const timers = new Set();
// fn(el) renvoie le texte et peut ajuster les classes de el.
export function liveTimer(fn, cls = "mono") { const el = h("span", { class: cls }); const t = { el, fn }; timers.add(t); el.textContent = fn(el); return el; }
setInterval(() => { for (const t of timers) { if (!t.el.isConnected) { timers.delete(t); continue; } t.el.textContent = t.fn(t.el); } }, 1000);

// ---------- Fenêtres ----------
const stack = [];
export const modals = {
  open(builder, opts = {}) {
    const layer = document.getElementById("modals");
    const back = h("div", { class: `backdrop ${opts.full ? "fullpad" : ""}` });
    const entry = { back, opts, returnFocus: document.activeElement };
    const close = () => modals.close(entry);
    back.append(builder(close, entry));
    layer.append(back); stack.push(entry);
    setTimeout(() => back.querySelector("[autofocus]")?.focus(), 30);
    return entry;
  },
  // Chaque étape remplace la précédente (parcours Nourrir l'IA, OCR).
  replace(builder, opts = {}) { const top = stack.at(-1); if (top) modals.close(top, true); return modals.open(builder, opts); },
  close(entry, silent) { const i = stack.indexOf(entry); if (i < 0) return; stack.splice(i, 1); entry.back.remove(); if (!silent) entry.opts.onClose?.();
    if (entry.returnFocus?.isConnected) entry.returnFocus.focus({ preventScroll: true }); },
  closeAll() { while (stack.length) modals.close(stack.at(-1), true); },
  get depth() { return stack.length; },
};
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && stack.length) { const top = stack.at(-1); top.back.querySelector("[data-close]")?.click(); } });

export function modal({ title, subtitle, eyebrow, body, foot, size = "", close, headExtra }) {
  return h("div", { class: `modal ${size}`, role: "dialog", "aria-modal": "true", "aria-label": typeof title === "string" ? title : "Fenêtre" },
    h("div", { class: "modal-head" },
      h("div", { class: "grow" }, eyebrow ? h("div", { class: "demo-tag" }, eyebrow) : null, h("h2", { class: "h1" }, title), subtitle ? h("div", { class: "muted", style: "margin-top:6px" }, subtitle) : null),
      headExtra || null,
      close ? h("button", { class: "icon-btn", "aria-label": "Fermer", "data-close": "1", onclick: close }, icon("close", "gold", 22)) : null),
    h("div", { class: "modal-body" }, body),
    foot ? h("div", { class: "modal-foot" }, foot) : null);
}

export function toast(text, { action, onAction, ms = 4000 } = {}) {
  const t = h("div", { class: "toast", role: "status" }, h("span", null, text), action ? h("button", { class: "link", onclick: () => { onAction?.(); t.remove(); } }, action) : null);
  document.getElementById("toast").append(t);
  setTimeout(() => t.remove(), ms);
}

// Écran de chargement partagé (reflet doré, aucun pourcentage fictif).
export function loader(title, sub, iconName = "day_clock") {
  return h("div", { class: "loader", role: "status", "aria-live": "polite" }, icon(iconName, "gold", 40), h("div", { class: "lt" }, title), h("div", { class: "ls" }, sub));
}
export async function withLoader(title, sub, fn, iconName) {
  const l = loader(title, sub, iconName); document.body.append(l);
  try { return await fn(l); } finally { l.remove(); }
}
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
