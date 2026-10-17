// OPS, PROJECTS, PROJECT_EDIT, MISSION_EDIT, ROUTINES, ROUTINE_EDIT (08, 09, 11, 12, A2, A3).
import { h, icon, btn, iconBtn, modal, modals, toast, field, select, seg, toggle, busy, fmtMin, fmtLong, comp } from "../core.js";
import { svc } from "../services/index.js";
import { app } from "../app.js";
import { confirmDelete, openNotes, openTerminal } from "../flows.js";

const FREQ = { daily: "Chaque jour", weekly: "Chaque semaine", biweekly: "Toutes les 2 semaines", monthly: "Chaque mois" };
const PRIO = { low: ["Priorité basse", "grey"], medium: ["Priorité moyenne", "gold"], high: ["Priorité élevée", "red"] };

export const operations = {
  title: "Gestion des opérations", skeleton: "list",
  load: () => svc.getOperations(),
  render(vm) {
    const active = vm.projects.slice(0, 2), waiting = vm.projects.slice(2);
    const body = h("div", { class: "page-body fixed" });
    const left = h("div", { class: "col" },
      h("div", { class: "row", style: "margin-bottom:6px" }, icon("projects", "gold", 28), h("h2", { class: "h2 grow" }, "Projets actifs"), h("span", { class: "gold mono" }, `${active.length} / 2`)),
      vm.projects.length === 0 ? h("div", { class: "col", style: "gap:10px;padding:20px 0" }, h("div", { class: "muted" }, "Aucun projet."), btn("Créer avec le chatbot", { kind: "primary", onClick: () => openTerminal({ ctx: { kind: "project", label: "PROJET" }, initial: [["IMPERIUM", "Quel projet veux-tu lancer ?"]] }) })) : null,
      h("div", { class: "scroll", style: "flex:1.5" }, active.map((p, i) => h("div", { class: "block" },
        h("div", { class: "row" }, h("span", { class: "rank" }, `0${i + 1}`), h("span", { class: "h2 ellipsis" }, p.title)),
        p.progress != null ? h("div", { style: "margin:8px 0" }, h("div", { class: "row small muted" }, h("span", { class: "grow" }, "Progression indicative"), h("span", { class: "gold mono" }, p.progress + " %")),
          h("div", { class: "progress", style: "margin-top:4px" }, h("i", { style: `width:${p.progress}%` })), h("div", { class: "tiny dim", style: "margin-top:4px" }, `Estimée au Weekly Review${p.progressAt ? " du " + fmtLong(p.progressAt) : ""} : ${p.progressWhy}`))
          : h("div", { class: "tiny dim", style: "margin:8px 0" }, "Progression : estimée au prochain Weekly Review."),
        p.missions.map((m) => h("button", { class: "mcheck", style: "background:none;border:0;width:100%;text-align:left;padding:0;color:inherit", onclick: () => openNotes(m.id) }, h("span", { class: `ring ${m.status === "faite" ? "ok" : ""}` }), h("span", { class: "ellipsis" }, m.title)))))),
      h("div", { class: "row", style: "margin-top:10px" }, icon("projects", "gold", 26), h("h2", { class: "h2" }, "Projets en attente")),
      h("div", { class: "scroll", style: "flex:1;margin-top:4px" }, waiting.map((p, i) => h("button", { class: "listrow", onclick: () => openProjects(p.id) }, h("span", { class: "rank", style: "font-size:18px" }, String(i + 3).padStart(2, "0")), h("span", { class: "ellipsis" }, p.title), icon("chevron_right", "gold", 18)))),
      h("div", { style: "padding-top:10px" }, btn("Gérer les projets", { kind: "primary", block: true, icon: "chevron_right", iconRight: true, onClick: () => openProjects() })));
    const right = h("div", { class: "col" },
      h("div", { class: "row" }, icon("routines", "gold", 28), h("div", null, h("h2", { class: "h2" }, "Routines"), h("div", { class: "small muted" }, "Prévues aujourd'hui"))),
      h("div", { class: "scroll grow", style: "margin-top:8px" }, vm.today.length ? vm.today.map((r) => h("div", { class: "block" }, h("div", { class: "serif ellipsis", style: "font-size:20px" }, r.name), h("div", { class: "small muted" }, FREQ[r.freq], r.minutes ? ` · ${r.minutes} min` : "")))
        : h("div", { class: "muted small", style: "padding:16px 0" }, "Aucune routine prévue aujourd'hui.")),
      h("div", { class: "block", style: "border-top:1px solid var(--sep)" }, h("div", { class: "serif", style: "font-size:19px" }, "Total estimé aujourd'hui"), h("div", { class: "mono", style: "font-size:26px;margin-top:4px" }, fmtMin(vm.totalMin))),
      btn("Gérer les routines", { kind: "primary", block: true, icon: "chevron_right", iconRight: true, onClick: () => openRoutines(vm.routines) }));
    body.append(h("div", { class: "ops" }, left, h("div", { class: "vsep" }), right));
    return body;
  },
};

// ---------- Gérer les projets (brouillon distinct, Enregistrer applique) ----------
export async function openProjects(expandId) {
  const { projects } = await svc.getOperations();
  const draft = structuredClone(projects);
  let open = expandId || null, selMission = null, dirty = false;
  modals.open((close) => {
    const cancel = () => { if (!dirty) return close();
      modals.open((c2) => modal({ title: "Abandonner les modifications ?", size: "small", close: c2, body: h("div", { class: "muted" }, "Rien n'a été enregistré. Le brouillon sera perdu."),
        foot: [btn("Continuer l'édition", { kind: "neutral", onClick: c2 }), btn("Abandonner", { kind: "danger", onClick: () => { c2(); close(); } })] })); };
    const view = comp((c) => {
      const move = (arr, i, d) => { const j = i + d; if (j < 0 || j >= arr.length) return; [arr[i], arr[j]] = [arr[j], arr[i]]; dirty = true; c.rerender(); };
      return h("div", { class: "col", style: "gap:0" }, draft.map((p, i) => {
        const isOpen = open === p.id;
        const row = h("button", { class: "listrow", style: `min-height:52px;${open && !isOpen ? "opacity:.55" : ""}`, onclick: () => { open = isOpen ? null : p.id; selMission = null; c.rerender(); }, "aria-expanded": String(isOpen) },
          h("span", { class: "rank", style: "font-size:19px" }, String(i + 1).padStart(2, "0")), h("span", { class: "serif ellipsis grow", style: "font-size:20px" }, p.title),
          i < 2 ? h("span", { class: "pill" }, h("span", { class: "dot green" }), "Actif") : null, icon(isOpen ? "chevron_down" : "chevron_right", "gold", 18));
        if (!isOpen) return row;
        const ms = p.missions;
        return h("div", { style: "border-left:2px solid var(--gold);background:#16171a;padding:0 12px 12px;margin:2px 0" }, row,
          h("div", { class: "row small", style: "gap:8px;flex-wrap:wrap" }, h("span", { class: "muted" }, "Projet :"),
            btn("Modifier", { kind: "ghost", icon: "edit", onClick: () => editProject(p, () => { dirty = true; c.rerender(); }) }),
            btn("Supprimer", { kind: "ghost", icon: "trash", iconVariant: "danger", onClick: () => confirmDelete({ name: p.title, text: "Ses missions à venir seront annulées ; l'historique est conservé.", onConfirm: async () => { draft.splice(i, 1); open = null; dirty = true; c.rerender(); toast("Suppression ajoutée au brouillon : Enregistrer pour l'appliquer."); } }) }),
            iconBtn("arrow_up", "Monter le projet", () => move(draft, i, -1), { disabled: i === 0 }), iconBtn("arrow_down", "Descendre le projet", () => move(draft, i, 1), { disabled: i === draft.length - 1 })),
          h("div", { class: "row", style: "margin-top:8px" }, h("div", { class: "h3 grow" }, "Missions"), btn("Ajouter une mission", { icon: "plus", onClick: () => editMission(p, null, () => { dirty = true; c.rerender(); }) })),
          ms.length ? ms.map((m, k) => h("div", { class: "row", style: `min-height:44px;border-bottom:1px solid var(--sep-soft);${selMission === m.id ? "background:#1d1e21" : ""}` },
            h("span", { class: "gold mono small", style: "width:24px" }, String(k + 1).padStart(2, "0")), h("span", { class: `ring ${m.status === "faite" ? "ok" : ""}` }),
            h("button", { class: "grow ellipsis", style: "background:none;border:0;text-align:left;min-height:44px;color:inherit", onclick: () => { selMission = m.id; c.rerender(); } }, m.title),
            iconBtn("notes", "Notes de la mission", () => openNotes(m.id)))) : h("div", { class: "small dim", style: "padding:8px 0" }, "Aucune mission."),
          (() => {
            const k = ms.findIndex((m) => m.id === selMission); if (k < 0) return h("div", { class: "tiny dim", style: "margin-top:6px" }, "Touche une mission pour la modifier ou la déplacer.");
            const m = ms[k]; const doneM = m.status === "faite";
            return h("div", { class: "row small", style: "gap:8px;margin-top:6px;flex-wrap:wrap" }, h("span", { class: "muted" }, "Mission :"),
              btn("Modifier", { kind: "ghost", icon: "edit", onClick: () => editMission(p, m, () => { dirty = true; c.rerender(); }) }),
              doneM ? h("span", { class: "tiny dim" }, "Mission terminée : non supprimable") : btn("Supprimer", { kind: "ghost", icon: "trash", iconVariant: "danger", onClick: () => confirmDelete({ name: m.title, text: "Elle sera retirée du plan.", onConfirm: async () => { ms.splice(k, 1); selMission = null; dirty = true; c.rerender(); } }) }),
              iconBtn("arrow_up", "Monter la mission", () => move(ms, k, -1), { disabled: k === 0 }), iconBtn("arrow_down", "Descendre la mission", () => move(ms, k, 1), { disabled: k === ms.length - 1 }));
          })());
      }));
    });
    const save = btn("Enregistrer", { kind: "primary", onClick: () => busy(save, async () => { await svc.saveProjects(draft); close(); toast("Projets enregistrés."); app.refresh(); }) });
    return modal({ title: "Gérer les projets", subtitle: "Les deux premiers projets sont actifs.", close: cancel, size: "wide",
      headExtra: h("div", { class: "row", style: "gap:8px" }, btn("Ajouter un projet", { icon: "plus", onClick: () => editProject(null, (np) => { draft.push(np); open = np.id; dirty = true; view.rerender?.(); }) }),
        btn("Terminal", { kind: "neutral", onClick: () => openTerminal({ ctx: { kind: "project", label: "PROJET" }, sub: open ? "Projet : " + draft.find((p) => p.id === open)?.title : null, initial: [] }) })),
      body: view, foot: [btn("Annuler", { kind: "neutral", onClick: cancel }), save] });
  });
}

function editProject(p, done) {
  const isNew = !p; p = p || { id: "pr_new_" + Date.now(), title: "", description: "", progress: null, missions: [] };
  modals.open((close) => {
    const name = h("input", { class: "input", value: p.title, autofocus: true });
    const desc = h("textarea", { class: "textarea", style: "min-height:120px" }, p.description);
    const err = h("div", { class: "err" });
    return modal({ title: isNew ? "Ajouter un projet" : "Modifier un projet", close, size: "small",
      body: [field("Nom du projet", name), field("Description du projet", desc, { optional: true, hint: "Informations utiles pour toi et pour l'IA." }), err],
      foot: [btn("Annuler", { kind: "neutral", onClick: close }), btn("Enregistrer", { kind: "primary", onClick: () => { if (!name.value.trim()) { err.textContent = "Indique un nom."; return; } p.title = name.value.trim(); p.description = desc.value; close(); done(p); } })] });
  });
}

export function editMission(project, m, done) {
  const isNew = !m; m = m || { id: "pm_new_" + Date.now(), title: "", description: "", estimatedMin: null, notes: "", status: "à faire" };
  modals.open((close) => {
    const name = h("input", { class: "input", value: m.title, autofocus: true });
    const desc = h("textarea", { class: "textarea" }, m.description);
    const dur = h("input", { class: "input mono", inputmode: "numeric", value: m.estimatedMin ?? "", placeholder: "—" });
    const notes = h("textarea", { class: "textarea" }, m.notes);
    const err = h("div", { class: "err" });
    return modal({ title: isNew ? "Ajouter une mission" : "Modifier une mission", subtitle: "Projet : " + project.title, close, size: "small",
      body: [field("Nom de la mission", name), field("Description", desc), field("Durée estimée", h("div", { class: "input-group", style: "max-width:200px" }, dur, h("span", { class: "addon" }, "min")), { optional: true }),
        field("Notes", notes, { optional: true, hint: "Précisions utiles à la planification." }), err],
      foot: [btn("Annuler", { kind: "neutral", onClick: close }), btn("Enregistrer", { kind: "primary", onClick: () => {
        if (!name.value.trim()) { err.textContent = "Indique un nom."; return; }
        const n = dur.value.trim() ? parseInt(dur.value, 10) : null; if (dur.value.trim() && !(n > 0)) { err.textContent = "Durée en minutes."; return; }
        Object.assign(m, { title: name.value.trim(), description: desc.value, estimatedMin: n, notes: notes.value }); if (isNew) project.missions.push(m); close(); done();
      } })] });
  });
}

// ---------- Routines ----------
export function openRoutines(routines) {
  let list = structuredClone(routines), sel = list[0]?.id;
  modals.open((close) => {
    const view = comp((c) => h("div", { class: "col" },
      list.map((r) => h("div", { class: "row", style: `min-height:60px;border-bottom:1px solid var(--sep-soft);${sel === r.id ? "border-left:2px solid var(--gold);padding-left:10px;background:#16171a" : "padding-left:12px"}` },
        h("button", { class: "grow col", style: "background:none;border:0;text-align:left;color:inherit;min-height:56px;justify-content:center", onclick: () => { sel = r.id; c.rerender(); } },
          h("span", { class: "serif ellipsis", style: "font-size:19px" }, r.name), h("span", { class: "small muted" }, FREQ[r.freq], r.minutes ? ` · ${r.minutes} min` : "")),
        h("span", { class: "row small", style: "gap:6px;width:150px" }, h("span", { class: `dot ${PRIO[r.priority][1]}` }), h("span", { class: PRIO[r.priority][1] === "grey" ? "muted" : PRIO[r.priority][1] }, PRIO[r.priority][0])),
        toggle(r.active, async (v) => { r.active = v; await svc.saveRoutine(r); toast(v ? "Routine activée." : "Routine désactivée."); app.refresh(); }, "Routine active"),
        h("span", { class: `small ${r.active ? "green" : "muted"}`, style: "width:56px" }, r.active ? "Active" : "Inactive"))),
      (() => { const r = list.find((x) => x.id === sel); if (!r) return null;
        return h("div", { class: "row", style: "margin-top:12px;gap:10px" }, h("span", { class: "serif grow", style: "font-size:20px" }, r.name),
          btn("Modifier", { kind: "ghost", icon: "edit", onClick: () => editRoutine(r, async (nr) => { await svc.saveRoutine(nr); Object.assign(r, nr); c.rerender(); app.refresh(); }) }),
          btn("Supprimer", { kind: "ghost", icon: "trash", iconVariant: "danger", onClick: () => confirmDelete({ name: r.name, text: "Elle ne sera plus planifiée ; l'historique est conservé.", onConfirm: async () => { await svc.deleteRoutine(r.id); list = list.filter((x) => x.id !== r.id); sel = list[0]?.id; c.rerender(); app.refresh(); toast("Routine supprimée."); } }) })); })()));
    return modal({ title: "Gérer les routines", close, size: "wide",
      headExtra: btn("Ajouter une routine", { icon: "plus", onClick: () => editRoutine(null, async (nr) => { await svc.saveRoutine(nr); const { routines: rs } = await svc.getOperations(); list = rs; sel = list.at(-1).id; view.rerender?.(); app.refresh(); }) }),
      body: [h("div", { class: "tiny dim" }, "L'ordre d'exécution est décidé par l'IA. Un jour ou une heure précis se demandent au chatbot."), view],
      foot: [btn("Fermer", { kind: "neutral", onClick: close })] });
  });
}

export function editRoutine(r, done) {
  const isNew = !r; const d = structuredClone(r || { id: null, name: "", freq: "daily", minutes: null, priority: "medium", notes: "", active: true });
  modals.open((close) => {
    const name = h("input", { class: "input", value: d.name, autofocus: true });
    const freq = select(Object.entries(FREQ).map(([value, label]) => ({ value, label })), d.freq, (v) => (d.freq = v));
    const dur = h("input", { class: "input mono", inputmode: "numeric", value: d.minutes ?? "" });
    const notes = h("textarea", { class: "textarea" }, d.notes);
    const err = h("div", { class: "err" });
    const save = btn("Enregistrer", { kind: "primary", onClick: () => busy(save, async () => {
      if (!name.value.trim()) { err.textContent = "Indique un nom."; return; }
      const n = dur.value.trim() ? parseInt(dur.value, 10) : null; if (dur.value.trim() && !(n > 0)) { err.textContent = "Durée en minutes."; return; }
      Object.assign(d, { name: name.value.trim(), minutes: n, notes: notes.value }); await done(d); close(); toast(isNew ? "Routine ajoutée." : "Routine enregistrée.");
    }) });
    return modal({ title: isNew ? "Ajouter une routine" : "Modifier une routine", close, size: "small",
      body: [field("Nom de la routine", name), field("Fréquence", freq),
        field("Durée estimée", h("div", { class: "input-group", style: "max-width:200px" }, dur, h("span", { class: "addon" }, "min")), { optional: true }),
        field("Priorité", seg([{ value: "low", label: "Basse" }, { value: "medium", label: "Moyenne" }, { value: "high", label: "Élevée" }], d.priority, (v) => (d.priority = v)), { hint: "Aide l'IA à arbitrer si une routine doit être reportée." }),
        field("Notes", notes, { optional: true }),
        h("div", { class: "set-row" }, h("span", { class: "grow" }, "Routine active"), toggle(d.active, (v) => (d.active = v), "Routine active")), err],
      foot: [btn("Annuler", { kind: "neutral", onClick: close }), save] });
  });
}
