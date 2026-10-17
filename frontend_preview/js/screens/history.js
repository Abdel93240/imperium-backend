// HISTORY, HISTORY_DAY, HISTORY_PROJECT (13, 14, A5 ; régularité doc 43 §6.1 ; période doc 65 §7.5).
import { h, icon, btn, modal, modals, select, fmtEUR, fmtLong, fmtHM, fmtDM, fmtDur, pad } from "../core.js";
import { svc } from "../services/index.js";
import { app } from "../app.js";

const PERIODS = [{ value: "semaine", label: "Semaine" }, { value: "mois", label: "Mois" }, { value: "3mois", label: "3 mois" }, { value: "annee", label: "Année" }, { value: "tout", label: "Tout" }];
let period = (() => { try { return localStorage.getItem("imp.period") || "3mois"; } catch { return "3mois"; } })();
const MOIS_C = ["Janv.", "Févr.", "Mars", "Avr.", "Mai", "Juin", "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc."];

export const history = {
  title: "Historique", skeleton: "list",
  load: () => svc.getHistory(period),
  render(vm) {
    const body = h("div", { class: "page-body" });
    if (vm.empty) { body.append(h("div", { class: "col", style: "align-items:center;gap:12px;padding-top:120px;text-align:center" }, icon("nav_history", "muted", 44), h("div", { class: "h2" }, "Aucun historique pour l'instant"), h("div", { class: "muted" }, "Tes journées terminées apparaîtront ici."))); return body; }
    const per = select(PERIODS, period, (v) => { period = v; try { localStorage.setItem("imp.period", v); } catch {} app.refresh(); }, { "aria-label": "Période des graphiques", style: "width:150px" });
    const r = vm.regularity, f = vm.finance;
    body.append(
      h("div", { class: "row", style: "padding-bottom:12px;border-bottom:1px solid var(--sep)" }, h("h1", { class: "h1 grow" }, "Ton parcours"), h("span", { class: "small muted" }, "Période des graphiques"), per),
      h("div", { class: "hist-grid", style: "padding:14px 0;border-bottom:1px solid var(--sep)" },
        h("section", { "aria-label": "Régularité" }, h("div", { class: "row" }, icon("arrow_up", "gold", 26), h("h2", { class: "h2" }, "Régularité")),
          h("div", { class: "row", style: "align-items:baseline;margin-top:8px" }, h("span", { class: "bignum" }, r.score), h("span", { class: "serif gold", style: "font-size:30px" }, "/ 100")),
          h("div", { class: "muted", style: "margin:4px 0 8px" }, `${r.delta >= 0 ? "+" : "−"}${Math.abs(r.delta)} points par rapport à la période précédente`),
          chart(r.series, { min: 0, max: 100, fmt: (v) => String(v) })),
        h("div", { class: "vsep" }),
        h("section", { "aria-label": "Finances" }, h("div", { class: "row" }, icon("finance", "gold", 26), h("h2", { class: "h2" }, "Finances")),
          h("div", { class: "bignum", style: "margin-top:8px" }, fmtEUR(f.balance).replace(",00", "")),
          h("div", { class: "muted", style: "margin-top:4px" }, `${f.delta >= 0 ? "+" : "−"}${fmtEUR(Math.abs(f.delta)).replace(",00", "")} sur la période`), h("div", { class: "small dim", style: "margin-bottom:8px" }, "Solde total des portefeuilles"),
          chart(f.series, { min: 0, fmt: (v) => (v >= 1000 ? (v / 1000).toFixed(1).replace(".", ",") + " k€" : Math.round(v) + " €") }))),
      h("div", { class: "hist-grid", style: "padding:14px 0;border-bottom:1px solid var(--sep)" },
        h("section", null, h("div", { class: "row" }, icon("check", "gold", 26), h("div", null, h("h2", { class: "h2" }, "Projets accomplis"), h("div", { class: "small muted" }, `${vm.finished.length} projets terminés`))),
          vm.finished.map((p) => h("button", { class: "listrow", style: "min-height:60px", onclick: () => openProject(p) }, h("span", { class: "ring ok" }), h("span", { class: "col", style: "min-width:0" }, h("span", { class: "ellipsis" }, p.title), h("span", { class: "small muted" }, "Terminé le " + fmtLong(p.doneAt))), icon("chevron_right", "gold", 18)))),
        h("div", { class: "vsep" }),
        h("section", null, h("div", { class: "row" }, icon("weekly_review", "gold", 26), h("div", null, h("h2", { class: "h2" }, "Historique des journées"), h("div", { class: "small muted" }, `${vm.days.reduce((s, d) => s + d.done, 0)} missions réalisées · ${vm.days.length} journées`))),
          h("div", { class: "scroll", style: "max-height:300px" }, vm.days.map((d) => h("button", { class: "listrow", style: "min-height:60px", onclick: () => openDay(d.id) },
            h("span", { class: "col" }, h("span", { class: "serif", style: "font-size:19px" }, fmtLong(d.start)), h("span", { class: "small muted mono" }, `${durHM(d.end - d.start)} · ${d.done} missions sur ${d.total}`)), icon("chevron_right", "gold", 18)))))),
      h("section", { style: "padding-top:14px" }, h("div", { class: "row" }, icon("ai_common", "gold", 30), h("div", null, h("h2", { class: "h2" }, "Bilan de l'IA"), h("div", { class: "small muted" }, "Mis à jour après le Weekly Review du " + fmtLong(vm.review.date)))),
        h("div", { class: "h2", style: "margin:12px 0 8px" }, vm.review.title), vm.review.text.map((t) => h("p", { style: "line-height:1.55;margin:0 0 8px" }, t))));
    return body;
  },
};

const durHM = (ms) => { const m = Math.round(ms / 60000); return `${Math.floor(m / 60)} h ${pad(m % 60)}`; };

// Courbe quotidienne sans lissage (polyligne brute).
function chart(series, { min = 0, max, fmt }) {
  const W = 360, H = 170, L = 42, B = 22, T = 8, R = 6;
  const vals = series.map((p) => p.v); const hi = max ?? Math.ceil(Math.max(...vals) / 1000) * 1000; const lo = min;
  const x = (i) => L + (i / Math.max(1, series.length - 1)) * (W - L - R), y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const NS = "http://www.w3.org/2000/svg"; const s = (tag, attrs) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; };
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "chart", role: "img", "aria-label": "Courbe quotidienne" });
  [lo, (lo + hi) / 2, hi].forEach((v) => { svg.append(s("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: "#2c2e2c", "stroke-dasharray": "3 4" })); const t = s("text", { x: L - 6, y: y(v) + 4, "text-anchor": "end" }); t.textContent = fmt(v); svg.append(t); });
  const pts = series.map((p, i) => `${x(i).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ");
  svg.append(s("polygon", { points: `${L},${H - B} ${pts} ${x(series.length - 1)},${H - B}`, fill: "rgba(222,198,141,.08)" }));
  svg.append(s("polyline", { points: pts, fill: "none", stroke: "#EFE3C6", "stroke-width": 1.4, "stroke-linejoin": "round" }));
  let lastM = -1; const n = series.length;
  series.forEach((p, i) => { const d = new Date(p.t); const key = n > 60 ? d.getMonth() : d.getDate(); if (n <= 10 || (n > 60 ? key !== lastM && d.getDate() <= 7 : i % Math.ceil(n / 5) === 0)) { lastM = key; const t = s("text", { x: x(i), y: H - 6, "text-anchor": "middle" }); t.textContent = n > 60 ? MOIS_C[d.getMonth()] : fmtDM(p.t); svg.append(t); } });
  return svg;
}

export async function openDay(id) {
  const d = await svc.getHistoryDay(id);
  modals.open((close) => {
    const list = h("div", { class: "col" }, d.missions.map((m) => {
      const det = m.ok ? null : h("div", { style: "border-left:2px solid var(--gold);background:#1a1b1d;padding:8px 12px;margin:2px 0 6px" }, h("div", { class: "small red" }, "Non effectuée", m.reason ? " · " + m.reason : ""), m.note ? h("div", { class: "small" }, "Note : " + m.note.toLowerCase()) : null);
      const row = h("button", { class: "listrow", "aria-expanded": String(!m.ok) }, icon(m.ok ? "check" : "close", m.ok ? "success" : "danger", 22), h("span", { class: "ellipsis" }, m.title), icon(m.ok ? "chevron_right" : "chevron_down", "gold", 18));
      const note = h("div", { style: "border-left:2px solid var(--gold);background:#1a1b1d;padding:8px 12px;margin:2px 0 6px;display:none" }, h("div", { class: "small" }, m.note || "Aucune note pour cette mission."));
      row.addEventListener("click", () => { if (det) det.style.display = det.style.display === "none" ? "" : "none"; else note.style.display = note.style.display === "none" ? "" : "none"; });
      return [row, det, note];
    }));
    return modal({ title: "Journée du " + fmtLong(d.start), close,
      body: [h("div", { style: "display:grid;grid-template-columns:repeat(3,1fr);gap:10px" },
        stat("day_clock", "Début", `${fmtDM(d.start)} à ${fmtHM(d.start)}`), stat("day_clock", "Fin", `${fmtDM(d.end)} à ${fmtHM(d.end)}`), stat("day_clock", "Durée", durHM(d.end - d.start))),
        h("div", { class: "row" }, icon("programme", "gold", 22), `${d.done} missions réalisées sur ${d.total}`), h("hr", { class: "sep" }), h("h3", { class: "h2" }, "Missions de la journée"), list,
        h("div", { class: "row tiny dim" }, icon("info", "muted", 16), "Ouvre une mission pour retrouver ses notes. Lecture seule.")],
      foot: [btn("Fermer", { kind: "primary", onClick: close })] });
  });
}
const stat = (ic, label, v) => h("div", { class: "row", style: "align-items:flex-start" }, icon(ic, "gold", 20), h("div", null, h("div", { class: "small muted" }, label), h("div", { class: "mono" }, v)));

export function openProject(p) {
  modals.open((close) => modal({ title: "Projet accompli", close,
    body: [h("div", { class: "row", style: "gap:16px" }, h("span", { class: "ring ok", style: "width:44px;height:44px" }), h("div", null, h("div", { class: "h2" }, p.title), h("div", { class: "muted" }, "Terminé le " + fmtLong(p.doneAt)), h("div", { class: "muted" }, `${p.missions.length} missions réalisées`))),
      h("hr", { class: "sep" }), h("h3", { class: "h2" }, "Missions accomplies"),
      p.missions.map(([t, note]) => h("details", { style: "border-bottom:1px solid var(--sep-soft)" }, h("summary", { class: "row", style: "min-height:46px;cursor:pointer;list-style:none" }, icon("check", "success", 22), h("span", { class: "grow" }, t), icon("notes", "gold", 18)),
        h("div", { style: "border-left:2px solid var(--gold);background:#1a1b1d;padding:8px 12px;margin:0 0 8px" }, h("div", { class: "small gold" }, "Note de mission"), h("div", { class: "small" }, note || "Aucune note.")))),
      h("div", { class: "row" }, icon("notes", "gold", 22), h("h3", { class: "h3" }, "Notes du projet")), h("div", { class: "muted" }, p.notes || "Aucune note.")],
    foot: [btn("Fermer", { kind: "primary", onClick: close })] }));
}
void fmtDur;
