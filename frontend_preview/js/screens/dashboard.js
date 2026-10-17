// DASH — Dashboard (01 révisée, A8, A9, densité doc 65 §3.3).
import { h, clock, icon, btn, busy, toast, withLoader, liveTimer, fmtDur, fmtHM, fmtEUR, fmtSigned, fmtDM, fmtMin } from "../core.js";
import { svc } from "../services/index.js";
import { app } from "../app.js";
import { openResult, openReplan, openNotes, openFinance, openTransaction, openTerminal, openIntervention, startWR, cooldownButton, PRESSURE } from "../flows.js";

const MIN = 60000;

export const dashboard = {
  title: "Dashboard", skeleton: "dash",
  load: () => svc.getDashboard(),
  render(vm) {
    const body = h("div", { class: "page-body fixed" });
    const d = h("div", { class: "dash" });
    body.append(d);

    // Journée
    const started = vm.day.state === "active";
    d.append(h("div", { class: "dash-day" },
      h("div", { class: "col", style: "gap:8px" },
        h("div", { class: "row", style: "gap:16px" }, h("h1", { class: "h1" }, "Ta journée"), icon("day_clock", "gold", 22), h("span", { class: "gold small" }, started ? "Journée en cours" : "Journée non démarrée")),
        started ? h("div", { class: "row", style: "gap:14px" }, h("span", { class: "muted" }, "Début"), h("span", { class: "mono" }, fmtHM(vm.day.startedAt)), h("span", { class: "vsep" }),
          h("span", { class: "muted" }, "Écoulé"), liveTimer(() => fmtDur(clock.now() - vm.day.startedAt), "mono muted")) : h("div", { class: "muted small" }, "Démarre ta journée pour voir ta mission et ton programme.")),
      h("div", { class: "col", style: "margin-left:auto;align-items:flex-end;gap:8px" },
        h("img", { class: "calli", src: "assets/brand/calligraphie_compacte_retenue.png", alt: "إن الساعة آتية لا ريب فيها" }),
        started && vm.pendingFinish ? h("span", { class: "pill orange" }, "Fin de journée en attente d'envoi")
        : started ? (() => { const b = btn("Terminer la journée", { kind: "primary", onClick: () => busy(b, async () => { const r = await svc.finishDay(); toast(r?.pending ? "Hors ligne : fin de journée en attente d'envoi. Le serveur clôturera la journée." : "Journée terminée. Les missions non faites retournent au backlog."); app.refresh(); }) }); return b; })()
          : (() => { const b = btn("Démarrer la journée", { kind: "primary", big: true, onClick: async () => { await withLoader("TA JOURNÉE", "Préparation de ta journée…", () => svc.startDay()); app.refresh(false); } }); return b; })())));

    // Bannières : 2 max ; ordre d'affichage WR puis Intervention (kit, règles finales).
    const banners = [];
    const wrBanner = vm.wr === "pending" ? h("div", { class: "banner" }, icon("weekly_review", "gold", 26), h("span", { class: "title" }, "Weekly Review en attente"), icon("warning", "warning", 22), h("span", { class: "spacer" }),
      btn("Commencer le Weekly Review", { kind: "primary", onClick: startWR })) : vm.wr === "done_recent" ? h("div", { class: "banner" }, icon("check", "success", 26), h("span", { class: "title green" }, "Weekly Review faite")) : null;
    if (wrBanner) banners.push(wrBanner);
    if (vm.intervention) banners.push(h("div", { class: "banner red" }, icon("alert", "danger", 26), h("span", { class: "title" }, "Intervention requise"), h("span", { class: "vsep" }), h("span", { class: "small" }, "Une décision t'attend."), h("span", { class: "spacer" }),
      btn("Examiner", { kind: "danger", icon: "chevron_right", iconVariant: "danger", iconRight: true, onClick: openIntervention })));
    d.append(...banners.slice(0, 2));

    if (vm.empty && started) {
      d.append(bottom(vm));
      d.append(h("div", { class: "grow col", style: "justify-content:center;align-items:center;gap:12px;text-align:center" }, icon("ai_common", "gold", 40), h("div", { class: "h2" }, "Aucune mission pour l'instant"),
        h("div", { class: "muted" }, "Parle au chatbot pour créer ton premier projet."), btn("Ouvrir le chatbot", { kind: "primary", icon: "chevron_right", iconRight: true, onClick: () => openTerminal({ ctx: { kind: "standard" }, initial: [["IMPERIUM", "Bienvenue. Dis-moi ce que tu veux construire et je crée ton premier projet."]] }) })));
      return body;
    }
    if (!started) {
      d.append(h("div", { class: "grow col", style: "justify-content:center;align-items:center;gap:16px;text-align:center" },
        icon("day_clock", "muted", 48), h("div", { class: "h2 muted" }, "Journée non démarrée"), h("div", { class: "dim small" }, "Ni mission ni programme avant le démarrage.")));
      d.append(bottom(vm), advice(vm));
      return body;
    }

    // Mission actuelle
    const m = vm.mission;
    if (m) {
      const end = m.plannedStart + m.durationMin * MIN;
      const remain = liveTimer((el) => { const left = end - clock.now(); el.classList.toggle("red", left < 0); return (left < 0 ? "+" : "") + fmtDur(left); }, "mono");
      d.append(h("section", { class: "dash-mission", "aria-label": "Mission actuelle" },
        h("div", { class: "row" }, h("div", { class: "eyebrow grow" }, "Mission actuelle"), h("span", { class: "muted small", "data-overlabel": "1" }, "Temps restant"), h("span", { class: "muted" }, "·"), remain),
        h("div", { class: "row", style: "margin-top:4px" }, h("div", { class: "mission-title ellipsis grow", title: m.title }, m.title)),
        h("button", { class: "row", style: "background:none;border:0;padding:0;text-align:left;width:100%;margin-top:4px", "aria-label": "Voir le détail de la mission", onclick: () => openNotes(m.id) },
          h("div", { class: "clamp3 grow", style: "line-height:1.45" }, m.description), icon("chevron_right", "gold", 20)),
        h("div", { class: "row small", style: "margin-top:6px;gap:14px" }, h("span", { class: "muted" }, "Début prévu"), h("span", { class: "mono" }, fmtHM(m.plannedStart)), h("span", { class: "vsep" }), h("span", { class: "muted" }, "Durée prévue"), h("span", { class: "mono" }, fmtMin(m.durationMin))),
        m.annexes?.length ? h("div", { style: "margin-top:8px" }, h("div", { class: "row" }, h("span", { class: "h3" }, "Missions annexes"), h("span", { class: "tiny dim" }, "Facultatives")),
          h("ul", { class: "annexes" }, m.annexes.slice(0, 6).map((a) => h("li", null, h("span", { class: "ellipsis" }, a.title))))) : null,
        m.pendingResult ? h("div", { class: "row", style: "justify-content:flex-end;margin-top:8px" }, h("span", { class: "pill orange" }, `${m.pendingResult} — en attente d'envoi`)) :
        h("div", { class: "row", style: "justify-content:flex-end;margin-top:8px;gap:12px" },
          btn("Fait", { kind: "success", icon: "check", iconVariant: "success", onClick: () => openResult(m, "done") }),
          btn("Pas fait", { kind: "danger", icon: "close", iconVariant: "danger", onClick: () => openResult(m, "fail") }))));
    }

    // Programme du jour (défilement interne, centré sur la mission en cours)
    const list = h("div", { class: "prog-list", role: "list" }, vm.plan.map((p) => h("button", { class: `prog-item ${p.status === "active" ? "now" : ""} ${p.status === "faite" || p.status === "ratée" ? "done" : ""}`, role: "listitem", onclick: () => openNotes(p.id), "aria-label": `${fmtHM(p.plannedStart)} ${p.title} — ouvrir les notes` },
      h("span", { class: "t" }, fmtHM(p.plannedStart)), h("span", { class: "bul" }), h("span", { class: "ellipsis" }, p.title), icon("chevron_right", "gold", 18))));
    d.append(h("section", { class: "prog", "aria-label": "Programme du jour" },
      h("div", { class: "row" }, icon("programme", "gold", 26), h("h2", { class: "h2 grow" }, "Programme du jour"), cooldownButton("Replanifier la journée", vm.replan.eligibleAt, openReplan, { kind: "primary" })), list));
    requestAnimationFrame(() => { const now = list.querySelector(".now"); if (now) list.scrollTop = now.offsetTop - list.clientHeight / 2 + now.clientHeight / 2; });

    d.append(bottom(vm), advice(vm));
    return body;
  },
};

function bottom(vm) {
  const p = PRESSURE(vm.finance.pressure);
  if (vm.empty) return h("div", { class: "dash-bottom" },
    h("section", { class: "col", style: "gap:8px" }, h("div", { class: "row" }, icon("finance", "gold", 24), h("h2", { class: "h3" }, "Résumé financier")), h("div", { class: "small dim" }, "Aucun portefeuille ni transaction pour l'instant."), btn("Transaction", { icon: "plus", onClick: () => openTransaction() })),
    h("div", { class: "vsep" }),
    h("section", { class: "col", style: "gap:8px" }, h("div", { class: "row" }, icon("projects", "gold", 24), h("h2", { class: "h3" }, "Projets en cours")), h("div", { class: "small dim" }, "Aucun projet — parle au chatbot pour en créer un.")));
  return h("div", { class: "dash-bottom" },
    h("section", { class: "col", style: "gap:6px", "aria-label": "Résumé financier" },
      h("div", { class: "row" }, icon("finance", "gold", 24), h("h2", { class: "h3" }, "Résumé financier")),
      p ? h("div", { class: "row small" }, h("span", { class: "grow" }, "Pression financière"), h("span", { class: p[1] }, p[0])) : null,
      p ? h("div", { class: "progress", role: "meter", "aria-valuenow": vm.finance.pressure, "aria-valuemin": 0, "aria-valuemax": 100, "aria-label": "Pression financière" }, h("i", { style: `width:${vm.finance.pressure}%` })) : null,
      h("div", { class: "row" }, h("span", { class: "grow" }, "Balance actuelle"), h("span", { class: "mono" }, fmtEUR(vm.finance.balance))),
      vm.finance.tx.length ? h("div", { class: "tx-mini" }, vm.finance.tx.slice(0, 3).flatMap((t) => [h("span", { class: "d" }, fmtDM(t.date)), h("span", { class: "ellipsis" }, t.label), h("span", { class: `mono amount ${t.amount > 0 ? "pos" : "neg"}` }, fmtSigned(t.amount))])) : h("div", { class: "small dim" }, "Aucune transaction"),
      h("div", { class: "row", style: "gap:10px;margin-top:4px" }, btn("Voir tout", { icon: "chevron_right", iconRight: true, onClick: openFinance }), btn("Transaction", { icon: "plus", onClick: () => openTransaction() }))),
    h("div", { class: "vsep" }),
    h("section", { class: "col", style: "gap:10px", "aria-label": "Projets en cours" },
      h("div", { class: "row" }, icon("projects", "gold", 24), h("h2", { class: "h3" }, "Projets en cours")),
      vm.projects.length ? vm.projects.map((p) => h("button", { class: "col", style: "background:none;border:0;text-align:left;padding:4px 0;gap:2px;min-height:48px", onclick: () => app.go("operations") },
        h("div", { class: "serif ellipsis", style: "font-size:18px" }, p.title), h("div", { class: "small muted ellipsis" }, "Prochaine mission : " + p.next))) : h("div", { class: "small dim" }, "Aucun projet — parle au chatbot pour en créer un.")));
}

function advice(vm) {
  if (!vm.advice) return h("div");
  return h("section", { class: "advice", "aria-label": "Conseils IA" }, icon("ai_common", "gold", 30),
    h("div", { class: "grow" }, h("div", { class: "h3" }, "Conseils IA"), h("div", { class: "small", style: "font-weight:600" }, vm.advice.title), h("div", { class: "small muted ellipsis" }, vm.advice.text)),
    btn("Ouvrir le chatbot", { kind: "primary", icon: "chevron_right", iconRight: true, onClick: () => openTerminal({ ctx: { kind: "standard" }, initial: [["IMPERIUM", vm.advice.text]] }) }));
}
