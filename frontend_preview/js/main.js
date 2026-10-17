// Point d'entrée de la prévisualisation web.
import { h, btn, modal, modals, toast } from "./core.js";
import { svc, isDemo } from "./services/index.js";
import { app, shell } from "./app.js";
import { dashboard } from "./screens/dashboard.js";
import { operations } from "./screens/operations.js";
import { history } from "./screens/history.js";
import { settings, openBubbleSim, openConnectForm } from "./screens/settings.js";
import { OPERATIONS } from "./services/backend.js";

app.pages = { dashboard, operations, historique: history, reglages: settings };
shell();

// Panneau de démonstration : scénarios et états transversaux (B12). Absent en mode backend.
if (isDemo) {
  const fab = h("button", { class: "demo-fab", "aria-label": "Panneau de démonstration" }, "Démo ▾");
  document.body.append(fab);
  fab.addEventListener("click", () => modals.open((close) => {
    const sc = svc.scenario;
    const opt = (label, on, fn) => h("button", { class: on ? "on" : "", onclick: () => { fn(); close(); app.refresh(false); } }, label);
    return modal({ title: "Démonstration", subtitle: "Données fictives. Choisis un scénario ou un état à afficher.", close,
      body: [
        h("div", { class: "h3" }, "Mission en cours"),
        h("div", { class: "scen" },
          opt("Travail VTC avec missions annexes", sc.mission === "vtc", () => svc.setScenario({ mission: "vtc", day: "active" })),
          opt("Séance de sport (aucune annexe)", sc.mission === "sport", () => svc.setScenario({ mission: "sport", day: "active" })),
          opt("Temps dépassé (+ en rouge)", sc.mission === "overtime", () => svc.setScenario({ mission: "overtime", day: "active" })),
          opt(sc.cooldown ? "Délai de replanification : actif" : "Délai de replanification : aucun", sc.cooldown, () => svc.setScenario({ cooldown: !sc.cooldown })),
          opt("Contenus longs (titre 100, description 800, 6 annexes, 25 missions)", sc.long, () => svc.setScenario({ long: !sc.long, day: "active" })),
          opt("Journée de 36 h 12", sc.longDay, () => svc.setScenario({ longDay: !sc.longDay, day: "active" }))),
        h("div", { class: "h3" }, "États (B12)"),
        h("div", { class: "scen" },
          opt("Journée non démarrée", sc.day === "not_started", () => svc.setScenario({ day: "not_started" })),
          opt("Chargement (skeleton)", sc.loading, () => { svc.setScenario({ loading: true }); setTimeout(() => { svc.setScenario({ loading: false }); }, 4000); }),
          opt("Vide — premier jour", sc.empty, () => svc.setScenario({ empty: !sc.empty })),
          opt("Erreur serveur", sc.error, () => svc.setScenario({ error: !sc.error })),
          opt("Hors ligne", app.offline, async () => { app.offline = !app.offline; svc.setScenario({ offline: app.offline });
            if (!app.offline) { const r = await svc.flushPending(); if (r.sent || r.failed) toast(`Réseau rétabli : ${r.sent} action(s) envoyée(s)${r.failed ? `, ${r.failed} en échec` : ""}.`); app.refresh(); } }),
          opt("Bulle : autorisation Android refusée", sc.overlayDenied, () => svc.setScenario({ overlayDenied: !sc.overlayDenied })),
          h("button", { onclick: async () => { close(); const r = await svc.completeTopProject(); toast(`« ${r.done} » terminé : « ${r.promoted} » devient actif.`); app.refresh(); } }, "Terminer le projet actif n° 1"),
          opt("Tout réinitialiser", false, () => { app.offline = false; svc.setScenario({ mission: "vtc", day: "active", loading: false, empty: false, error: false, offline: false, cooldown: true, long: false, longDay: false, overlayDenied: false }); })),
        h("div", { class: "h3" }, "Vues Android simulées"),
        h("div", { class: "scen" },
          h("button", { onclick: () => { close(); openBubbleSim(); } }, "Bulle flottante (overlay)"),
          h("button", { onclick: () => { close(); openConnectForm(true); } }, "Écran de connexion (1er lancement)")),
        h("div", { class: "h3" }, "Raccordement backend"),
        h("button", { class: "btn neutral block", onclick: () => { close(); openApiMap(); } }, "Voir la carte des opérations → routes"),
        h("div", { class: "tiny dim" }, "Le clavier se teste en touchant un champ sur la tablette. Ajoute ?mode=backend à l'URL pour brancher l'adaptateur réel (non raccordé : chaque appel affiche la route attendue)."),
      ],
      foot: [btn("Fermer", { kind: "neutral", onClick: close })] });
  }));
}

function openApiMap() {
  const C = { existe: "green", partiel: "orange", "à confirmer": "orange", manquant: "red", plateforme: "grey" };
  modals.open((close) => modal({ title: "Carte du raccordement API", subtitle: "Routes trouvées dans le dépôt (préfixe /api). Rien n'est inventé.", close, size: "wide",
    body: Object.entries(OPERATIONS).map(([op, o]) => h("div", { class: "row", style: "align-items:flex-start;min-height:44px;border-bottom:1px solid var(--sep-soft);padding:6px 0" },
      h("span", { class: "mono small", style: "width:170px;flex:none" }, op), h("span", { class: `pill ${C[o.etat] === "green" ? "" : C[o.etat]}`, style: "flex:none" }, o.etat),
      h("span", { class: "col small", style: "min-width:0" }, h("span", { class: "mono" }, o.route || "—"), o.note ? h("span", { class: "dim" }, o.note) : null))),
    foot: [btn("Fermer", { kind: "neutral", onClick: close })] }));
}

window.addEventListener("online", () => toast("Réseau rétabli."));

// Crochet de recette : ?open=<vue> ouvre directement une fenêtre (captures de contrôle).
const OPEN = new URLSearchParams(location.search).get("open");
if (OPEN) setTimeout(async () => {
  const F = await import("./flows.js"), O = await import("./screens/operations.js"), Hs = await import("./screens/history.js"), S = await import("./screens/settings.js"), Fd = await import("./screens/feed.js");
  const vm = await svc.getDashboard(); const m = vm.mission;
  const map = {
    result_done: () => F.openResult(m, "done"), result_fail: () => F.openResult(m, "fail"), replan: () => F.openReplan(),
    replan_validate: async () => { svc.setScenario({ cooldown: false }); F.openReplanValidate(await svc.requestReplan({ reason: "Je suis trop fatigué — longue nuit" })); },
    finance: F.openFinance, transaction: () => F.openTransaction(), camera: () => F.openCamera({ type: "out", amount: "", date: "2026-10-17", label: "", wallet: "w_bank", category: "" }),
    gallery: () => F.openGallery({ type: "out", amount: "", date: "2026-10-17", label: "", wallet: "w_bank", category: "" }), notes: () => F.openNotes(m.id),
    terminal: () => F.openTerminal({ ctx: { kind: "standard" }, initial: [["IMPERIUM", "Rassemble tes documents avant de partir pour éviter un aller-retour."], ["VOUS", "Quels documents dois-je préparer ?"], ["IMPERIUM", "Dis-moi quelle démarche tu prévois.\nJe t'aiderai à préparer la liste."]] }),
    intervention: F.openIntervention, delete: () => F.confirmDelete({ name: "Apprendre le russe", text: "Ses missions à venir seront annulées ; l'historique est conservé.", onConfirm: async () => {} }),
    projects: () => O.openProjects("pr_apprendre_le_russe"), routines: async () => O.openRoutines((await svc.getOperations()).routines), routine_edit: async () => O.editRoutine((await svc.getOperations()).routines[0], async () => {}),
    history_day: () => Hs.openDay("d1"), history_project: async () => Hs.openProject((await svc.getHistory("3mois")).finished[0]),
    bubble_settings: S.openBubbleSettings, bubble: S.openBubbleSim, notifications: S.openNotifications, priorities: async () => S.openPriorities(await svc.getPriorities()),
    connection: S.openConnection, connect: () => S.openConnectForm(true), permissions: S.openPermissions, advanced: S.openAdvanced, models: S.openModelRoles, thresholds: S.openThresholds, keys: S.openApiKeys, logs: S.openLogs,
    feed: () => Fd.openFeed(), feed_import: () => modals.open(Fd.importStep), demo: () => document.querySelector(".demo-fab")?.click(),
  };
  map[OPEN]?.();
}, 600);

// Recette automatisée : ?recette=R01 (voir js/recette.js).
const REC = new URLSearchParams(location.search).get("recette");
if (REC) setTimeout(() => import("./recette.js").then((m) => m.run(REC)), 900);
