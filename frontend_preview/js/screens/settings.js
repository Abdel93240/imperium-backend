// SETTINGS et sous-vues (15 + A1, A7, B6–B9, B11, 17, 19).
import { h, clock, icon, btn, iconBtn, modal, modals, toast, field, select, seg, toggle, busy, dot, comp, fmtHM, fmtDur, sleep } from "../core.js";
import { svc, isDemo } from "../services/index.js";
import { app, statusLine } from "../app.js";
import { confirmDelete, openResult, openReplan } from "../flows.js";
import { openFeed } from "./feed.js";

const AI_MODES = { strict: "L'IA suit la hiérarchie des priorités et les règles à la lettre.", equilibre: "L'IA cherche le meilleur équilibre entre les priorités et le contexte.", souple: "L'IA peut s'écarter de la hiérarchie quand le contexte le justifie." };

export const settings = {
  title: "Réglages", skeleton: "list",
  topRight: () => { const s = statusLine(); s.addEventListener("click", openConnection); return s; },
  load: async () => ({ s: await svc.getSettings(), prio: await svc.getPriorities() }),
  render({ s, prio }) {
    const save = async (patch) => { try { await svc.saveSettings(patch); } catch { toast("Échec de l'enregistrement. Réessaie."); } };
    const navRow = (title, sub, onClick, ic) => h("button", { class: "listrow", style: "min-height:58px", onclick: onClick }, ic ? icon(ic, "gold", 22) : null, h("span", { class: "col" }, h("span", { class: "serif", style: "font-size:19px" }, title), sub ? h("span", { class: "small muted" }, sub) : null), icon("chevron_right", "gold", 18));
    const head = (ic, title, sub) => h("div", { class: "row", style: "margin-bottom:8px" }, icon(ic, "gold", 28), h("div", null, h("h2", { class: "h2" }, title), sub ? h("div", { class: "small muted" }, sub) : null));
    const modeDesc = h("div", { class: "small muted", style: "margin-top:8px" }, AI_MODES[s.aiMode]);
    return h("div", { class: "page-body" },
      isDemo ? h("div", { class: "demo-tag" }, "Exemple de configuration (démonstration)") : null,
      h("div", { class: "set-sec set-two" },
        h("section", null, head("bubble_overlay", "Bulle flottante"), h("div", { class: "set-row" }, h("span", { class: "grow" }, "Bulle flottante"), toggle(s.bubble, (v) => save({ bubble: v }), "Bulle flottante")),
          btn("Gérer la bulle", { kind: "primary", block: true, icon: "chevron_right", iconRight: true, onClick: openBubbleSettings })),
        h("div", { class: "vsep" }),
        h("section", null, head("bell", "Notifications"), h("div", { class: "set-row" }, h("span", { class: "grow" }, "Notifications"), toggle(s.notif, (v) => save({ notif: v }), "Notifications")),
          btn("Gérer les notifications", { kind: "primary", block: true, icon: "chevron_right", iconRight: true, onClick: openNotifications }))),
      h("div", { class: "set-sec set-two" },
        h("section", null, head("sunrise", "Routine du matin"), h("div", { class: "set-row" }, h("span", { class: "grow" }, "Popup du matin"), toggle(s.morningPopup, (v) => save({ morningPopup: v }), "Popup du matin")),
          h("div", { class: "small muted" }, "Il s'ouvre quand tu démarres ta journée.")),
        h("div", { class: "vsep" }),
        h("section", null, head("replan", "Replanification"),
          h("div", { class: "small muted" }, "Après une mission échouée"),
          h("div", { class: "set-row" }, h("span", { class: "grow" }, "Mission urgente"), select([{ value: "replanifier", label: "Replanifier" }, { value: "demander", label: "Demander" }], s.replanUrgent, (v) => save({ replanUrgent: v }), { style: "width:160px" })),
          h("div", { class: "set-row" }, h("span", { class: "grow" }, "Autres missions"), select([{ value: "replanifier", label: "Replanifier" }, { value: "demander", label: "Demander" }], s.replanOther, (v) => save({ replanOther: v }), { style: "width:160px" })),
          h("div", { class: "set-row" }, h("span", { class: "grow small" }, "Délai minimum entre deux replanifications (automatiques et manuelles)"), h("div", { class: "input-group", style: "width:120px" }, h("input", { class: "input mono", value: s.debounce, inputmode: "numeric", onchange: (e) => save({ debounce: parseInt(e.target.value, 10) || 5 }) }), h("span", { class: "addon" }, "min"))))),
      h("section", { class: "set-sec" }, head("ai_common", "Comportement de l'IA"),
        seg([{ value: "strict", label: "Strict" }, { value: "equilibre", label: "Équilibré" }, { value: "souple", label: "Souple" }], s.aiMode, (v) => { modeDesc.textContent = AI_MODES[v]; save({ aiMode: v }); }), modeDesc),
      h("section", { class: "set-sec" }, head("priorities", "Priorités personnelles", "Ton ordre décide du poids de chaque domaine dans le plan."),
        h("div", { class: "row", style: "flex-wrap:wrap;gap:18px" }, prio.map((p, i) => h("span", { class: "row", style: "gap:8px" }, h("span", { class: "gold mono" }, String(i + 1).padStart(2, "0")), p)), h("span", { class: "spacer" }),
          btn("Gérer les priorités", { kind: "primary", icon: "chevron_right", iconRight: true, onClick: () => openPriorities(prio) }))),
      h("section", { class: "set-sec", style: "border-left:2px solid var(--gold);padding-left:14px" }, head("ai_common", "Intelligence artificielle"),
        navRow("Nourrir l'IA", "Ce que tu as transmis à l'IA ; Importer se trouve dans la liste.", openFeed, "import"),
        navRow("Logs de l'IA", "Journal en lecture seule des traitements de l'IA.", openLogs, "logs"),
        h("div", { class: "set-row" }, icon("memory", "gold", 22), h("span", { class: "grow" }, "Conservation de l'historique du chat"), select([30, 60, 90, 180, 365].map((n) => ({ value: String(n), label: n + " jours" })), String(s.chatRetention), (v) => save({ chatRetention: +v }), { style: "width:150px" }))),
      h("section", { class: "set-sec" }, head("server", "Connexion et autorisations"),
        navRow("Connexion à Imperium", "Serveur et accès à l'API", openConnection), navRow("Autorisations de l'appareil", "Caméra, microphone, localisation, fichiers, bulle", openPermissions)),
      h("section", { class: "set-sec" }, navRow("Paramètres avancés", "Configuration technique de l'IA et des services.", openAdvanced, "sliders")));
  },
};

// ---------- B6 Gérer la bulle ----------
export async function openBubbleSettings() {
  const granted = (await svc.getPermissions()).find((p) => p.id === "overlay").state === "ok";
  const s = await svc.getSettings();
  modals.open((close) => { let tg; const explain = h("div", { class: "small orange", style: "display:none" }, "Pour afficher la bulle, Android doit autoriser Imperium à « s'afficher par-dessus les autres apps ». Appuie sur « Autoriser » : les réglages Android s'ouvrent, puis reviens ici. La bulle reste désactivée tant que l'autorisation manque.");
    tg = toggle(s.bubble && granted, async (v) => { if (v && !granted) { tg.classList.remove("on"); tg.setAttribute("aria-checked", "false"); explain.style.display = ""; return; } await svc.saveSettings({ bubble: v }); toast("Réglage enregistré."); }, "Bulle flottante");
    return modal({ title: "Gérer la bulle", close,
    body: [h("div", { class: "set-row" }, h("span", { class: "grow" }, "Bulle flottante (mission en cours)"), tg), explain,
      h("div", { class: "set-row" }, h("span", { class: "grow" }, h("div", null, "Afficher par-dessus les autres apps"), h("div", { class: "small muted" }, "Autorisation Android nécessaire pour la bulle.")), dot(granted ? "green" : "red"), h("span", { class: `small ${granted ? "green" : "red"}` }, granted ? "Autorisée" : "Non autorisée"),
        btn(granted ? "Gérer" : "Autoriser", { kind: granted ? "neutral" : "primary", onClick: () => toast("Sur la tablette : ouvre les réglages Android de l'autorisation (non disponible dans le navigateur).") })),
      h("hr", { class: "sep" }), h("div", { class: "small muted" }, "Aperçu — actions fixes : Terminer, Échouer, Demander une replanification complète de la journée."),
      btn("Voir la simulation de la bulle", { kind: "primary", onClick: () => { close(); openBubbleSim(); } }),
      h("div", { class: "tiny dim" }, "La bulle est un overlay Android : elle ne fonctionne pas dans une page web. Ceci est une simulation visuelle.")],
    foot: [btn("Fermer", { kind: "neutral", onClick: close })] }); });
}

export async function openBubbleSim() {
  const vm = await svc.getDashboard(); const m = vm.mission;
  modals.open((close) => {
    let openP = false;
    const view = comp((c) => {
      const left = m ? m.plannedStart + m.durationMin * 60000 - clock.now() : 0;
      return h("div", { class: "home-sim" },
        h("div", { class: "demo-tag", style: "position:absolute;top:16px;left:16px" }, "Simulation de l'overlay Android — écran d'accueil fictif"),
        h("button", { class: "icon-btn", style: "position:absolute;top:8px;right:8px", "aria-label": "Fermer la simulation", "data-close": "1", onclick: close }, icon("close", "gold", 24)),
        h("button", { class: "bubble", "aria-label": "Bulle Imperium", onclick: () => { openP = !openP; c.rerender(); } }, h("img", { src: "assets/brand/logo_imperium_original.png", alt: "" })),
        openP ? h("div", { class: "bubble-panel" },
          m ? [h("div", { class: "row" }, h("div", { class: "eyebrow grow" }, "Mission actuelle"), iconBtn("close", "Fermer le panneau", () => { openP = false; c.rerender(); })),
            h("div", { class: "h2" }, m.title), h("div", { class: "row small" }, h("span", { class: "muted" }, "Temps restant ·"), h("span", { class: `mono ${left < 0 ? "red" : ""}` }, (left < 0 ? "+" : "") + fmtDur(left))),
            h("hr", { class: "sep" }),
            h("div", { class: "row" }, btn("Terminer", { kind: "success", icon: "check", iconVariant: "success", onClick: () => { close(); openResult(m, "done"); } }), btn("Échouer", { kind: "danger", icon: "close", iconVariant: "danger", onClick: () => { close(); openResult(m, "fail"); } })),
            btn("Demander une replanification complète de la journée", { kind: "primary", icon: "replan", onClick: () => { close(); openReplan(); } })]
            : [h("div", { class: "muted" }, "Aucune mission en cours.")]) : null);
    });
    return h("div", { class: "modal full", style: "position:relative;overflow:hidden" }, view);
  }, { full: true });
}

// ---------- B7 Notifications ----------
export async function openNotifications() {
  const s = await svc.getSettings();
  modals.open((close) => {
    const warn = h("div", { class: "small orange", style: s.notifs.red ? "display:none" : "" }, "Attention : tu ne seras plus prévenu des urgences (ex. solde insuffisant pour une dépense à venir).");
    const row = (k, label, extra) => h("div", { class: "set-row" }, h("span", { class: "grow" }, label), toggle(s.notifs[k], async (v) => { s.notifs[k] = v; if (k === "red") warn.style.display = v ? "none" : ""; await svc.saveSettings({ notifs: s.notifs }); }, label), extra);
    return modal({ title: "Gérer les notifications", close, size: "small",
      body: [h("div", { class: "small muted" }, "Les notifications arrivent sur cette tablette (notifications Android)."),
        row("checkin", "Check-in du matin"), row("wr", "Weekly Review"), row("reminders", "Rappels de mission"), row("red", "Alertes rouges"), warn],
      foot: [btn("Fermer", { kind: "neutral", onClick: close })] });
  });
}

// ---------- A7 Priorités (4 domaines fixes, monter/descendre) ----------
export function openPriorities(initial) {
  const order = [...initial];
  modals.open((close) => {
    const list = comp((c) => h("div", { class: "col" }, order.map((p, i) => h("div", { class: "row", style: "min-height:56px;border-bottom:1px solid var(--sep-soft)" },
      h("span", { class: "rank" }, String(i + 1).padStart(2, "0")), h("span", { class: "serif grow", style: "font-size:21px" }, p),
      iconBtn("arrow_up", `Monter ${p}`, () => { [order[i - 1], order[i]] = [order[i], order[i - 1]]; c.rerender(); }, { disabled: i === 0, variant: i === 0 ? "muted" : "gold" }),
      iconBtn("arrow_down", `Descendre ${p}`, () => { [order[i + 1], order[i]] = [order[i], order[i + 1]]; c.rerender(); }, { disabled: i === order.length - 1, variant: i === order.length - 1 ? "muted" : "gold" })))));
    const save = btn("Enregistrer", { kind: "primary", onClick: () => busy(save, async () => { await svc.savePriorities(order); close(); toast("Priorités enregistrées."); app.refresh(); }) });
    return modal({ title: "Priorités personnelles", subtitle: "Ton ordre décide du poids de chaque domaine dans le plan.", close, size: "small", body: list, foot: [btn("Annuler", { kind: "neutral", onClick: close }), save] });
  });
}

// ---------- 19 Connexion / B9 Configurer ----------
const ST = { green: ["Disponible", "green"], orange: ["Dégradé", "orange"], red: ["Indisponible", "red"], grey: ["Non vérifié", "grey"] };
export async function openConnection() {
  modals.open((close) => {
    const view = comp((c) => {
      const box = h("div", { class: "col" }, h("div", { class: "skel", style: "height:200px" }));
      svc.getStatus().then((st) => box.replaceChildren(...[
        h("div", { class: "row" }, dot(app.offline ? "red" : "green"), h("div", null, h("div", { class: "serif", style: "font-size:21px" }, app.offline ? "Serveur déconnecté" : "Serveur connecté"), h("div", { class: "small muted" }, "Dernière vérification : " + fmtHM(st.checkedAt)))),
        h("hr", { class: "sep", style: "margin:12px 0" }), h("div", { class: "row" }, icon("database", "gold", 22), h("h3", { class: "h3" }, "État des services")),
        st.services.map((sv) => h("div", { class: "set-row" }, h("span", { class: "grow" }, sv.label), dot(ST[sv.state][1]), h("span", { class: `small ${ST[sv.state][1] === "grey" ? "muted" : ST[sv.state][1]}`, style: "width:100px" }, ST[sv.state][0]))),
        isDemo ? h("div", { class: "tiny dim" }, "Démonstration : mémoire vectorielle, IA locale et IA cloud n'ont pas encore d'endpoint de santé ; en réel elles s'affichent « Non vérifié ».") : null,
        btn("Actualiser les statuts", { kind: "primary", block: true, icon: "refresh", onClick: () => c.rerender() })].flat().filter(Boolean))).catch(() => box.replaceChildren(h("div", { class: "red" }, "Impossible de joindre Imperium.")));
      return box;
    });
    return modal({ title: "Connexion à Imperium", close,
      body: [view, h("hr", { class: "sep" }), h("button", { class: "listrow", onclick: () => { close(); openConnectForm(); } }, icon("sliders", "gold", 22), h("span", { class: "serif", style: "font-size:19px" }, "Configurer la connexion"), icon("chevron_right", "gold", 18)),
        h("div", { class: "row tiny", style: "gap:14px;flex-wrap:wrap" }, h("span", { class: "dim" }, "Statuts :"), Object.values(ST).map(([l, c]) => h("span", { class: "row", style: "gap:6px" }, dot(c), l)))],
      foot: [btn("Fermer", { kind: "neutral", onClick: close })] });
  });
}

export function openConnectForm(first = false) {
  modals.open((close) => {
    const url = h("input", { class: "input mono", value: "http://100.98.23.31:8000", inputmode: "url" });
    const res = h("span", { class: "small" });
    const key = h("input", { class: "input mono", type: "password", autocomplete: "off", placeholder: "Clé maître" });
    const eye = iconBtn("eye", "Afficher la clé", () => { const shown = key.type === "text"; key.type = shown ? "password" : "text"; eye.replaceChildren(icon(shown ? "eye" : "eye_off", "gold", 22)); }, { boxed: true });
    const device = h("input", { class: "input", value: "Galaxy Tab S8" });
    const err = h("div", { class: "err" });
    const test = btn("Tester", { kind: "neutral", onClick: () => busy(test, async () => { const r = await svc.testServer(url.value); res.replaceChildren(dot(r.ok ? "green" : "red"), " ", r.ok ? `Serveur joignable (${r.latency} ms)` : r.error); }) });
    const go = btn("Se connecter", { kind: "primary", onClick: () => busy(go, async () => {
      err.textContent = "";
      try { await svc.connect({ url: url.value, key: key.value, device: device.value }); key.value = ""; close(); toast("Connecté."); }
      catch (e) { key.value = ""; err.textContent = e.message; }
    }) });
    return modal({ title: "Configurer la connexion", subtitle: first ? "Premier lancement" : null, close,
      body: [field("Adresse du serveur", h("div", { class: "row" }, url, test)), res,
        field("Clé maître", h("div", { class: "row" }, key, eye), { hint: "Jamais mémorisée. Démonstration : la clé « demo » fonctionne." }),
        field("Nom de l'appareil", device), err],
      foot: [btn("Annuler", { kind: "neutral", onClick: close }), go] });
  });
}

// ---------- 19 Autorisations ----------
const PS = { ok: ["Autorisée", "green"], partial: ["À la sélection", "orange"], no: ["Non autorisée", "red"], unknown: ["Non vérifiée", "grey"] };
export async function openPermissions() {
  const perms = await svc.getPermissions();
  modals.open((close) => modal({ title: "Autorisations de l'appareil", subtitle: "Consulte et gère les accès utilisés par Imperium.", close,
    body: [perms.map((p) => h("div", { class: "set-row", style: "min-height:62px" }, icon(p.icon, "gold", 26), h("div", { class: "grow" }, h("div", { class: "serif", style: "font-size:19px" }, p.label), h("div", { class: "small muted" }, p.desc)),
      dot(PS[p.state][1]), h("span", { class: `small ${PS[p.state][1]}`, style: "width:110px" }, PS[p.state][0]), btn("Gérer", { kind: "neutral", onClick: () => toast("Sur la tablette : ouvre les réglages Android (non disponible dans le navigateur).") }))),
      h("div", { class: "row tiny", style: "gap:14px;flex-wrap:wrap" }, Object.values(PS).map(([l, c]) => h("span", { class: "row", style: "gap:6px" }, dot(c), l))),
      h("div", { class: "tiny dim" }, "Les accès se gèrent avec les réglages de l'appareil. Statuts de démonstration.")],
    foot: [btn("Fermer", { kind: "neutral", onClick: close })] }));
}

// ---------- B8 Paramètres avancés ----------
export function openAdvanced() {
  modals.open((close) => {
    const row = (ic, t, sub, fn) => h("button", { class: "listrow", style: "min-height:62px", onclick: fn }, icon(ic, "gold", 24), h("span", { class: "col" }, h("span", { class: "serif", style: "font-size:19px" }, t), h("span", { class: "small muted" }, sub)), icon(ic === "memory" ? "external" : "chevron_right", "gold", 18));
    return modal({ title: "Paramètres avancés", close,
      body: [row("memory", "Vectorisation", "Ouvre la console de calibration (Tower)", () => toast("Lien vers la console configurée sur la Tower : URL non fournie dans ce kit, aucun domaine inventé.")),
        row("chip", "Modèles par rôle", "Le modèle utilisé pour chaque rôle de l'IA", openModelRoles),
        row("sliders", "Seuils de score /200", "Quand l'IA locale passe la main au cloud", openThresholds),
        row("key", "Clés API", "État des clés des fournisseurs", openApiKeys)],
      foot: [btn("Fermer", { kind: "neutral", onClick: close })] });
  });
}

export async function openModelRoles() {
  let roles = await svc.getModelRoles();
  modals.open((close) => {
    const view = comp((c) => h("div", { class: "col" }, roles.map((r) => h("div", { class: "row", style: "min-height:52px;border-bottom:1px solid var(--sep-soft)" },
      h("span", { class: "mono small grow ellipsis" }, r.role), h("span", { class: `small ${r.model ? "" : "dim"}`, style: "width:190px" }, r.model ? `${r.model}` : "Non configuré", r.effort ? h("span", { class: "tiny dim" }, ` · ${r.effort}`) : null),
      btn("Modifier", { kind: "neutral", onClick: () => editModel(r, async (nr) => { await svc.saveModelRole(nr); roles = await svc.getModelRoles(); c.rerender(); }) })))));
    const upd = btn("Mettre à jour le catalogue", { icon: "refresh", onClick: () => busy(upd, async () => { await svc.getCatalog(); toast("Catalogue à jour."); }) });
    return modal({ title: "Modèles par rôle", close, size: "wide", headExtra: upd, body: [h("div", { class: "tiny dim" }, "Rôles fixes (doc 30 §3) : on ne peut ni en ajouter ni en renommer. Noms de modèles : valeurs de référence du projet."), view],
      foot: [btn("Fermer", { kind: "neutral", onClick: close })] });
  });
}
async function editModel(r, done) {
  const cat = await svc.getCatalog(); const d = { ...r, provider: r.provider || "OpenRouter" };
  modals.open((close) => {
    const effortWrap = h("div");
    const models = h("div");
    const paintModels = () => {
      const list = cat[d.provider] || []; if (!list.includes(d.model)) d.model = list[0];
      models.replaceChildren(d.provider === "OpenRouter"
        ? field("Modèle", h("div", { class: "col", style: "gap:8px" }, h("input", { class: "input", placeholder: "Rechercher un modèle OpenRouter…", oninput: (e) => { const m = list.find((x) => x.toLowerCase().includes(e.target.value.toLowerCase())); if (m) { d.model = m; sel.value = m; } } }), (sel = select(list, d.model, (v) => { d.model = v; paintEffort(); }))))
        : field("Modèle", select(list, d.model, (v) => { d.model = v; paintEffort(); })));
      paintEffort();
    };
    let sel;
    const paintEffort = () => effortWrap.replaceChildren(d.provider === "Anthropic" || d.provider === "OpenAI" ? field("Effort", select(["Faible", "Moyen", "Élevé"], d.effort || "Moyen", (v) => (d.effort = v))) : h("div", { class: "tiny dim" }, "Ce modèle ne gère pas de réglage d'effort."));
    paintModels();
    const ok = btn("Valider", { kind: "primary", onClick: () => busy(ok, async () => { if (!(d.provider === "Anthropic" || d.provider === "OpenAI")) d.effort = null; else d.effort = d.effort || "Moyen"; await done(d); close(); toast("Modèle mis à jour."); }) });
    return modal({ title: "Modifier le modèle", subtitle: r.role, close, size: "small",
      body: [field("Accès", select(Object.keys(cat), d.provider, (v) => { d.provider = v; paintModels(); })), models, effortWrap],
      foot: [btn("Annuler", { kind: "neutral", onClick: close }), ok] });
  });
}

export async function openThresholds() {
  const t = await svc.getThresholds();
  modals.open((close) => {
    const err = h("div", { class: "err" });
    const rows = t.map((r) => { const a = h("input", { class: "input mono", value: r.from, inputmode: "numeric", style: "width:90px" }), b = h("input", { class: "input mono", value: r.to, inputmode: "numeric", style: "width:90px" }); return { r, a, b }; });
    const check = () => {
      const v = rows.map(({ r, a, b }) => ({ label: r.label, from: +a.value, to: +b.value }));
      if (v.some((x) => !Number.isInteger(x.from) || !Number.isInteger(x.to) || x.from > x.to)) return "Chaque borne doit être un entier, début ≤ fin.";
      if (v[0].from !== 0 || v.at(-1).to !== 200) return "Les plages doivent couvrir 0 à 200.";
      for (let i = 1; i < v.length; i++) if (v[i].from !== v[i - 1].to + 1) return `Trou ou chevauchement entre « ${v[i - 1].label} » et « ${v[i].label} ».`;
      return v;
    };
    const save = btn("Enregistrer", { kind: "primary", onClick: () => busy(save, async () => { const v = check(); if (typeof v === "string") { err.textContent = v; return; } await svc.saveThresholds(v); close(); toast("Seuils enregistrés."); }) });
    return modal({ title: "Seuils de score /200", close, size: "small",
      body: [rows.map(({ r, a, b }) => h("div", { class: "row", style: "min-height:56px;border-bottom:1px solid var(--sep-soft)" }, a, h("span", { class: "dim" }, "–"), b, h("span", { class: "grow", style: "padding-left:8px" }, r.label))),
        h("div", { class: "small muted" }, "À chaque message, l'IA locale note sa capacité à répondre sur 200. Le score choisit le niveau qui répond."), err],
      foot: [btn("Annuler", { kind: "neutral", onClick: close }), save] });
  });
}

export async function openApiKeys() {
  let keys = await svc.getApiKeys();
  modals.open((close) => {
    const view = comp((c) => h("div", { class: "col" }, keys.map((k) => h("div", { class: "row", style: "min-height:56px;border-bottom:1px solid var(--sep-soft)" },
      icon("key", "gold", 22), h("span", { class: "grow" }, k.provider), k.present ? h("span", { class: "pill" }, "Clé enregistrée ✓") : h("span", { class: "pill red" }, "Manquante"),
      btn("Remplacer", { kind: "neutral", onClick: () => editKey(k.provider, async () => { await svc.replaceApiKey(k.provider); keys = await svc.getApiKeys(); c.rerender(); }) }),
      k.present ? btn("Supprimer", { kind: "ghost", icon: "trash", iconVariant: "danger", onClick: () => confirmDelete({ name: `la clé ${k.provider}`, text: `Les rôles qui utilisent ${k.provider} ne pourront plus l'appeler.`, onConfirm: async () => { await svc.deleteApiKey(k.provider); keys = await svc.getApiKeys(); c.rerender(); } }) }) : null))));
    return modal({ title: "Clés API", close, body: [h("div", { class: "tiny dim" }, "Seul l'état est affiché : une clé enregistrée n'est jamais réaffichée."), view], foot: [btn("Fermer", { kind: "neutral", onClick: close })] });
  });
}
function editKey(provider, done) {
  modals.open((close) => {
    const inp = h("input", { class: "input mono", type: "password", autocomplete: "off", placeholder: "Nouvelle clé", autofocus: true });
    const err = h("div", { class: "err" });
    const save = btn("Enregistrer", { kind: "primary", onClick: () => busy(save, async () => { if (inp.value.trim().length < 8) { err.textContent = "Clé trop courte."; return; } inp.value = ""; await done(); close(); toast("Clé remplacée."); }) });
    return modal({ title: "Remplacer une clé", subtitle: provider, close, size: "small", body: [field("Nouvelle clé", inp, { hint: "Écriture seule : la clé n'est pas conservée dans l'app." }), err], foot: [btn("Annuler", { kind: "neutral", onClick: () => { inp.value = ""; close(); } }), save] });
  });
}

// ---------- B11 Logs de l'IA ----------
export async function openLogs() {
  const logs = await svc.listLogs(); let sel = logs[0]?.id;
  modals.open((close) => {
    const view = comp((c) => { const l = logs.find((x) => x.id === sel);
      return h("div", { class: "col", style: "gap:12px;min-height:0;flex:1" },
        h("div", { class: "col", style: "border:1px solid var(--sep);border-radius:8px;max-height:220px;overflow:auto" }, logs.map((x) => h("button", { class: "listrow", style: `padding:0 12px;${x.id === sel ? "background:#1d1e21;color:var(--gold)" : ""}`, onclick: () => { sel = x.id; c.rerender(); } }, icon("folder", x.id === sel ? "gold" : "muted", 20), h("span", { class: "ellipsis small" }, x.name)))),
        h("div", { class: "term", style: "flex:1;min-height:240px" }, h("div", { class: "term-head" }, h("span", { class: "ttl", style: "font-size:15px" }, l ? l.name : "—")), h("pre", { class: "term-log", style: "margin:0;font-size:13px" }, l ? l.content : "Aucun log.")));
    });
    return modal({ title: "Logs de l'IA", subtitle: "Lecture seule. Pour corriger une extraction, parle au chatbot.", close, size: "wide", body: view, foot: [btn("Fermer", { kind: "neutral", onClick: close })] });
  });
}
void sleep;
