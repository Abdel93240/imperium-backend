// État applicatif partagé et routeur.
import { h, icon, btn, dot } from "./core.js";
import { svc, isDemo } from "./services/index.js";

export const app = {
  offline: false,
  pages: {},
  current: null,
  vm: null,
  go(name) { location.hash = "#/" + name; },
  async refresh(silent = true) { await renderPage(app.current, silent); },
};

const NAV = [["dashboard", "Dashboard", "nav_dashboard"], ["operations", "Opérations", "nav_operations"], ["historique", "Historique", "nav_history"], ["reglages", "Réglages", "nav_settings"]];

export function shell() {
  const root = document.getElementById("app");
  root.replaceChildren(
    h("header", { class: "topbar" },
      h("div", { class: "brand" }, h("img", { src: "assets/brand/logo_imperium_original.png", alt: "" }), h("span", { class: "brand-word" }, "IMPERIUM")),
      h("div", { class: "page", id: "pageTitle" }, ""),
      h("div", { id: "topRight", style: "margin-left:auto;display:flex;align-items:center" })),
    h("nav", { class: "sidebar", "aria-label": "Navigation principale" },
      NAV.map(([k, label, ic]) => h("a", { class: "nav", href: "#/" + k, "data-k": k }, h("img", { src: `assets/icons/${ic}__gold.svg`, alt: "", "aria-hidden": "true", "data-ic": ic }), label))),
    h("main", { id: "main" }));
  window.addEventListener("hashchange", route);
  route();
}

function route() {
  const name = (location.hash.replace("#/", "") || "dashboard").split("?")[0];
  app.current = app.pages[name] ? name : "dashboard";
  document.querySelectorAll(".nav").forEach((a) => {
    const on = a.dataset.k === app.current; a.classList.toggle("on", on);
    if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    const img = a.querySelector("img"); img.src = `assets/icons/${img.dataset.ic}__${on ? "gold" : "muted"}.svg`;
  });
  renderPage(app.current, false);
}

let token = 0;
async function renderPage(name, silent) {
  const page = app.pages[name]; const main = document.getElementById("main"); const my = ++token;
  document.getElementById("pageTitle").textContent = page.title;
  const top = document.getElementById("topRight"); top.replaceChildren(page.topRight ? page.topRight() : "");
  if (!silent) main.replaceChildren(offlineBar(), skeleton(page.skeleton));
  try {
    const vm = await page.load();
    if (my !== token) return;
    app.vm = vm;
    main.replaceChildren(offlineBar(), page.render(vm));
  } catch (e) {
    if (my !== token) return;
    main.replaceChildren(offlineBar(), errorState(e));
  }
}

export function offlineBar() {
  return app.offline ? h("div", { class: "offline-bar", role: "status" }, icon("wifi_off", "gold", 18), "Hors ligne — tes actions seront envoyées au retour du réseau. Affichage depuis le cache.") : "";
}

function skeleton(kind = "dash") {
  const b = (hgt, w = "100%") => h("div", { class: "skel", style: `height:${hgt}px;width:${w};margin-bottom:14px` });
  return h("div", { class: "page-body", "aria-busy": "true", "aria-label": "Chargement" },
    kind === "dash" ? [b(70), b(48), b(220), b(260), h("div", { style: "display:grid;grid-template-columns:1fr 1fr;gap:18px" }, b(170), b(170)), b(60)]
      : [b(60, "60%"), b(200), b(200), b(140)]);
}

function errorState(e) {
  return h("div", { class: "page-body", style: "display:grid;place-items:center" },
    h("div", { class: "col", style: "align-items:center;gap:14px;text-align:center;max-width:420px" },
      icon("server", "danger", 44), h("div", { class: "h2" }, "Impossible de joindre Imperium"), h("div", { class: "row small red" }, dot("red"), "Serveur : déconnecté"),
      h("div", { class: "muted" }, e?.info ? `Opération : ${e.op} — ${e.info.route || "contrat manquant"}` : "Le serveur ne répond pas. Tes données ne sont pas perdues."),
      btn("Réessayer", { kind: "primary", icon: "refresh", onClick: () => app.refresh(false) })));
}

export function statusLine() {
  const s = h("button", { class: "status", "aria-label": "État de la connexion" }, "…");
  const AI = { green: "IA : disponible", orange: "IA : dégradée", red: "IA : indisponible", grey: "IA : non vérifiée" };
  svc.getStatus().then((st) => s.replaceChildren(dot(app.offline ? "red" : st.server), app.offline ? "Serveur : déconnecté" : "Serveur : connecté", h("span", { style: "width:12px" }), dot(app.offline ? "grey" : st.ai), AI[app.offline ? "grey" : st.ai], icon("chevron_right", "gold", 16))).catch(() => s.replaceChildren(dot("red"), "Serveur : déconnecté", h("span", { style: "width:12px" }), dot("grey"), AI.grey));
  return s;
}
export { isDemo };
