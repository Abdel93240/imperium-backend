// Parcours en fenêtres (fiches RESULT, REPLAN, REPLAN_VALIDATE, FINANCE, TRANSACTION, OCR_*, NOTES, WR, INTERVENTION, DELETE).
import { h, clock, icon, btn, iconBtn, modal, modals, toast, select, field, check, seg, busy, withLoader, loader, sleep,
  fmtEUR, fmtSigned, fmtHM, fmtDMY, fmtDM, fmtDur, fmtMin, liveTimer, pad } from "./core.js";
import { svc } from "./services/index.js";
import { app } from "./app.js";
import { terminal } from "./terminal.js";

const MIN = 60000;
export const PRESSURE = (s) => s == null ? null : s <= 20 ? ["Très faible", "green"] : s <= 40 ? ["Faible", "green"] : s <= 60 ? ["Modérée", "gold"] : s <= 80 ? ["Forte", "orange"] : ["Critique", "red"];

// ---------- Bouton soumis au délai de replanification ----------
export function cooldownButton(label, eligibleAt, onClick, { kind = "", withHint = true, icon: ic = "chevron_right" } = {}) {
  const b = btn(label, { kind, icon: ic, iconRight: true, onClick });
  const hint = h("div", { class: "tiny dim mono", style: "text-align:right;margin-top:4px;min-height:15px" });
  const tick = () => {
    const left = eligibleAt - clock.now();
    b.disabled = left > 0;
    hint.textContent = left > 0 ? `Disponible dans ${Math.ceil(left / MIN)} min` : "";
    return left > 0;
  };
  tick(); const iv = setInterval(() => { if (!b.isConnected && iv) { /* attendre montage */ } if (!tick()) clearInterval(iv); }, 1000);
  return withHint ? h("div", { class: "col", style: "align-items:flex-end" }, b, hint) : b;
}

// ---------- Résultat de mission (03 + A8) ----------
export function openResult(mission, mode) {
  const overtime = clock.now() > mission.plannedStart + mission.durationMin * MIN;
  const overMs = clock.now() - (mission.plannedStart + mission.durationMin * MIN);
  const draft = { annexes: new Set(), remark: "", reasonKey: "Séance prolongée", reasonText: "" };
  const REASONS = ["Séance prolongée", "Interruption", "Imprévu", "Fatigue", "Autre"];
  modals.open((close) => {
    let save;
    const reasonText = h("textarea", { class: "textarea", placeholder: "Explique ce qui s'est passé…" });
    const reasonSel = select(REASONS, mode === "done" ? "Séance prolongée" : "Imprévu", (v) => { draft.reasonKey = v; prefill(); });
    draft.reasonKey = reasonSel.value;
    // Le menu préremplit le texte libre (doc 59 §12.4) ; les détails restent modifiables.
    const prefill = () => { const cur = reasonText.value.replace(/^[^—]*—\s?/, ""); reasonText.value = `${draft.reasonKey} — ${cur}`; };
    prefill();
    const body = mode === "done" ? [
      overtime ? h("div", { class: "red mono small" }, `Temps dépassé · +${fmtDur(overMs)}`) : null,
      overtime ? field("Raison du dépassement", reasonSel) : null,
      overtime ? field("Détails", reasonText) : null,
      mission.annexes?.length ? h("div", { class: "col", style: "gap:4px" },
        h("div", { class: "row" }, h("div", { class: "h3 grow" }, "Missions annexes réalisées"), h("span", { class: "tiny dim" }, "Facultatives")),
        mission.annexes.map((a) => check(false, a.title, (v) => v ? draft.annexes.add(a.id) : draft.annexes.delete(a.id)))) : null,
      field("Remarque", h("textarea", { class: "textarea", placeholder: "Ajouter une précision…", oninput: (e) => (draft.remark = e.target.value) }), { optional: true }),
    ] : [
      field("Raison", reasonSel),
      field("Détails de la raison", reasonText, { hint: "Précise pourquoi la mission n'a pas été faite. Le texte complet est envoyé." }),
    ];
    save = btn(mode === "done" ? "Valider" : "Confirmer", { kind: mode === "done" ? "success" : "danger", onClick: () => busy(save, async () => {
      try {
        if (mode === "done") await svc.completeMission(mission.id, { remark: draft.remark, overtimeReason: overtime ? reasonText.value : null, completedAnnexIds: [...draft.annexes] });
        else { if (!reasonText.value.replace(/^[^—]*—\s?/, "").trim() && draft.reasonKey === "Autre") { toast("Précise la raison."); return; } await svc.failMission(mission.id, { reason: reasonText.value }); }
        close(); toast(mode === "done" ? "Mission validée." : "Mission enregistrée comme non faite."); app.refresh();
      } catch (e) { toast(e.message || "Échec de l'enregistrement. Réessaie."); }
    }) });
    return modal({ title: mode === "done" ? "Valider la mission" : "Mission non effectuée", subtitle: mission.title, close, size: "small",
      body, foot: [btn("Annuler", { kind: "neutral", onClick: close }), save] });
  });
}

// ---------- Replanification (02 + A9) ----------
export async function openReplan() {
  const st = await svc.getReplanState();
  modals.open((close) => {
    const REASONS = ["Fatigue", "Imprévu", "Retard sur le programme", "Rendez-vous déplacé", "Autre"]; // valeurs de démonstration : liste réelle à confirmer dans le contrat
    const other = h("input", { class: "input", placeholder: "Indique le motif…" });
    const otherField = field("Autre raison", other); otherField.style.display = "none";
    const sel = select(REASONS, REASONS[0], (v) => { otherField.style.display = v === "Autre" ? "" : "none"; });
    const details = h("textarea", { class: "textarea", placeholder: "Décris la situation…", style: "min-height:130px" });
    const go = async () => {
      const reason = `${sel.value === "Autre" ? other.value.trim() || "Autre" : sel.value} — ${details.value.trim()}`;
      close();
      try { const proposal = await withLoader("REPLANIFICATION", "Calcul de ta nouvelle journée…", () => svc.requestReplan({ reason }), "replan"); openReplanValidate(proposal); }
      catch (e) { toast(e.code === "COOLDOWN" ? "Délai de replanification en cours." : "La replanification a échoué. Ton plan actuel est conservé."); app.refresh(); }
    };
    return modal({ title: "Replanifier la journée", close, size: "small",
      body: [h("div", null, "Pourquoi souhaites-tu adapter ta journée ?"), field("Raison de la replanification", sel), otherField, field("Détails de la raison", details)],
      foot: [btn("Annuler", { kind: "neutral", onClick: close }), cooldownButton("Replanifier", st.eligibleAt, go, { kind: "primary", withHint: false })] });
  });
}

export function openReplanValidate(proposal) {
  modals.open((close) => {
    let pr = proposal;
    const planCol = h("div", { class: "col", style: "min-height:0" });
    const drawPlan = () => planCol.replaceChildren(
      h("div", { class: "row", style: "margin-bottom:8px" }, icon("replan", "gold", 24), h("div", { class: "h2 grow" }, "Nouvelle planification"), h("span", { class: "tiny dim mono" }, "v" + pr.version)),
      h("div", { class: "small muted", style: "margin-bottom:8px" }, "Raison : ", h("span", { class: "gold" }, pr.reason)),
      h("div", { class: "scroll grow" }, pr.items.map((x) => h("div", { class: "prog-item", style: x.badge === "Retirée" ? "opacity:.55;text-decoration:line-through" : "" },
        h("span", { class: "t" }, fmtHM(x.plannedStart)), h("span", { class: "bul" }),
        h("span", { class: "row" }, h("span", { class: "ellipsis grow" }, x.title), h("span", { class: "tiny dim mono" }, fmtMin(x.durationMin)),
          x.badge ? h("span", { class: `pill ${x.badge === "Nouvelle" ? "" : x.badge === "Retirée" ? "red" : "gold"}` }, x.badge) : null), h("span")))));
    drawPlan();
    const term = terminal({ ctx: { kind: "replan", label: "REPLANIFICATION" }, initial: [["IMPERIUM", "Voici la proposition pour la suite de ta journée. J'ai décalé l'après-midi de 30 min, ajouté une pause récupération et retiré la lecture. Souhaites-tu l’ajuster ?"]],
      onReply: async (text) => { const r = await svc.reviseReplan(pr.id, text); pr = r.proposal; drawPlan(); return { text: r.reply }; } });
    const accept = btn("Accepter", { kind: "primary", onClick: () => busy(accept, async () => { await svc.acceptReplan(pr.id); close(); toast("Nouveau plan appliqué."); app.refresh(); }) });
    const m = h("div", { class: "modal full" },
      h("div", { class: "modal-head" }, h("div", { class: "grow h1" }, "Résultat de la replanification"), h("button", { class: "icon-btn", "aria-label": "Annuler", "data-close": "1", onclick: async () => { await svc.cancelReplan(); close(); toast("Plan précédent conservé."); } }, icon("close", "gold", 22))),
      h("div", { class: "modal-body", style: "overflow:hidden" }, h("div", { class: "split" }, h("div", { class: "col", style: "max-height:42dvh;min-height:0" }, planCol), term.el)),
      h("div", { class: "modal-foot" }, btn("Annuler", { kind: "neutral", onClick: async () => { await svc.cancelReplan(); close(); toast("Plan précédent conservé."); } }), accept));
    return m;
  }, { full: true });
}

// ---------- Notes de mission (10) ----------
export async function openNotes(missionId, { editable = true } = {}) {
  const n = await svc.getNotes(missionId);
  modals.open((close) => {
    const ta = h("textarea", { class: "textarea", style: "min-height:140px", readOnly: !editable }, n.notes);
    const save = btn("Enregistrer", { kind: "primary", onClick: () => busy(save, async () => { await svc.saveNotes(missionId, ta.value); close(); toast("Notes enregistrées."); }) });
    return modal({ title: "Notes de la mission", close, size: "small",
      body: [h("div", null, h("div", { class: "small muted" }, n.context), h("div", { class: "h2", style: "margin-top:4px" }, n.title)),
        n.description ? h("div", { class: "muted" }, n.description) : null, h("hr", { class: "sep" }),
        field("Notes", ta, { hint: editable ? "Informations utiles pour toi et pour l'IA." : "Lecture seule." })],
      foot: editable ? [btn("Annuler", { kind: "neutral", onClick: close }), save] : [btn("Fermer", { kind: "neutral", onClick: close })] });
  });
}

// ---------- Finances (04) ----------
export async function openFinance() {
  const f = await svc.getFinance();
  modals.open((close) => modal({ title: h("span", { class: "row" }, icon("finance", "gold", 28), "Vue financière"), close,
    body: [
      h("div", null, h("div", { class: "h3" }, "Balance totale"), h("div", { class: "bignum", style: "font-size:52px" }, fmtEUR(f.balance)),
        (() => { const p = PRESSURE(f.pressure); return h("div", { class: "row small", style: "margin-top:8px" }, "Pression financière :", h("span", { class: p[1] }, p[0])); })()),
      h("hr", { class: "sep" }),
      h("div", { style: "display:grid;grid-template-columns:repeat(3,1fr);gap:12px" }, f.wallets.map((w) => h("div", { class: "row" }, icon(w.icon, "gold", 28), h("div", null, h("div", { class: "small muted" }, w.label), h("div", { class: "mono" }, fmtEUR(w.value)))))),
      h("hr", { class: "sep" }),
      h("div", { class: "row" }, icon("logs", "gold", 26), h("div", { class: "h2" }, "Dernières transactions")),
      h("div", { style: "display:grid;grid-template-columns:110px 1fr auto;gap:0 12px;font-size:14px" },
        h("div", { class: "small muted", style: "padding:6px 0" }, "Date"), h("div", { class: "small muted", style: "padding:6px 0" }, "Libellé"), h("div", { class: "small muted", style: "padding:6px 0;text-align:right" }, "Montant"),
        f.tx.flatMap((t) => [h("div", { class: "mono", style: "padding:9px 0;border-top:1px solid var(--sep-soft)" }, fmtDMY(t.date)), h("div", { class: "ellipsis", style: "padding:9px 0;border-top:1px solid var(--sep-soft)" }, t.label),
          h("div", { class: `mono amount ${t.amount > 0 ? "pos" : "neg"}`, style: "padding:9px 0;border-top:1px solid var(--sep-soft);text-align:right" }, fmtSigned(t.amount))])),
    ],
    foot: [btn("Fermer", { kind: "neutral", onClick: close }), btn("Ajouter une transaction", { kind: "primary", icon: "plus", onClick: () => { close(); openTransaction(); } })] }));
}

// ---------- Transaction + OCR (05, B3, B4, B5) ----------
export async function openTransaction(draft) {
  const [cats, fin] = await Promise.all([svc.getCategories(), svc.getFinance()]);
  draft = draft || { type: "out", amount: "", date: new Date().toISOString().slice(0, 10), label: "", wallet: "w_bank", category: "", source: null };
  modals.open((close) => {
    const bookOf = (c) => cats.find((x) => x.name === c)?.book;
    const badge = h("span", { class: "pill gold" });
    const srcTag = h("span", { class: "tiny" });
    const catSel = select([{ value: "", label: "Choisir une catégorie" }, ...cats.map((c) => ({ value: c.name, label: c.name }))], draft.category, (v) => { draft.category = v; draft.source = "user"; paint(); });
    const paint = () => {
      catSel.value = draft.category || "";
      const b = bookOf(draft.category); badge.textContent = b ? `Livre : ${b}` : "Livre : —"; badge.className = `pill ${b === "Business" ? "gold" : b ? "grey" : "grey"}`;
      srcTag.replaceChildren(draft.source === "known" ? h("span", { class: "green" }, "Reconnu") : draft.source === "ai" ? h("span", { class: "row gold", style: "gap:4px" }, icon("ai_common", "gold", 14), "Proposé par l'IA") : draft.source === "user" ? h("span", { class: "dim" }, "Choisi par toi") : "");
    };
    let t; const label = h("input", { class: "input", value: draft.label, placeholder: "Ex. Carburant",
      oninput: (e) => { draft.label = e.target.value; clearTimeout(t); t = setTimeout(async () => { if (!draft.label.trim() || draft.source === "user") return; srcTag.textContent = "Analyse du libellé…"; const s = await svc.suggestCategory(draft.label); draft.category = s.category; draft.source = s.source; paint(); }, 450); } });
    const amount = h("input", { class: "input mono", inputmode: "decimal", value: draft.amount, placeholder: "0,00", oninput: (e) => (draft.amount = e.target.value) });
    const date = h("input", { class: "input mono", type: "date", value: draft.date, oninput: (e) => (draft.date = e.target.value) });
    const wallet = select(fin.wallets.map((w) => ({ value: w.id, label: w.label === "Comptes" ? "Compte bancaire" : w.label })), draft.wallet, (v) => (draft.wallet = v));
    const err = h("div", { class: "err" });
    paint();
    const save = btn("Enregistrer la transaction", { kind: "primary", onClick: () => busy(save, async () => {
      const n = parseFloat(String(draft.amount).replace(",", "."));
      if (!(n > 0)) { err.textContent = "Indique un montant."; return; }
      if (!draft.label.trim()) { err.textContent = "Indique un libellé."; return; }
      if (!draft.category) { err.textContent = "Choisis une catégorie."; return; }
      try { await svc.createTransaction({ amount: draft.type === "in" ? n : -n, date: new Date(draft.date).getTime(), label: draft.label.trim(), wallet: draft.wallet, category: draft.category }); close(); toast("Transaction enregistrée."); app.refresh(); }
      catch (e) { err.textContent = e.message; }
    }) });
    return modal({ title: "Ajouter une transaction", close,
      body: [
        field("Type", seg([{ value: "in", label: "Entrée", icon: "plus", iconVariant: "gold" }, { value: "out", label: "Sortie", icon: "minus" }], draft.type, (v) => (draft.type = v))),
        h("button", { class: "listrow", style: "border:1px solid #3b3d3b;border-radius:6px;padding:12px 14px;min-height:72px", onclick: () => { close(); openCamera(draft); } },
          icon("camera", "gold", 30), h("div", null, h("div", { class: "serif", style: "font-size:20px" }, "Importer un justificatif"), h("div", { class: "small dim" }, "Lecture automatique par OCR"))),
        h("div", { class: "tiny dim" }, "Les informations préremplies restent modifiables."),
        h("div", { style: "display:grid;grid-template-columns:1fr 1fr;gap:14px" }, field("Montant", h("div", { class: "input-group" }, amount, h("span", { class: "addon" }, "€"))), field("Date", date)),
        field("Libellé", label),
        field("Catégorie", catSel, { hint: "Suggérée à partir du libellé ; tu peux la changer." }),
        h("div", { class: "row" }, badge, srcTag, h("span", { class: "tiny dim" }, "· déduit de la catégorie")),
        field("Portefeuille", wallet), err],
      foot: [btn("Annuler", { kind: "neutral", onClick: close }), save] });
  });
}

export function openCamera(draft) {
  modals.open((close) => {
    const back = () => { close(); openTransaction(draft); };
    return h("div", { class: "modal full", style: "background:#000" },
      h("div", { style: "position:relative;flex:1;display:grid;place-items:center;background:radial-gradient(80% 60% at 50% 45%,#2a2a28,#050505)" },
        h("div", { class: "demo-tag", style: "position:absolute;top:16px;left:16px" }, "Aperçu caméra de démonstration — la caméra réelle passe par Android"),
        h("div", { style: "height:58%;aspect-ratio:3/5;border:2px dashed rgba(239,227,198,.7);border-radius:10px;display:grid;place-items:center;color:var(--text-2)" }, "Place le ticket dans le cadre"),
        h("div", { class: "small muted", style: "position:absolute;bottom:24px" }, "L'image est envoyée au service OCR.")),
      h("div", { class: "row", style: "justify-content:space-around;padding:20px 24px 28px;background:#0a0a0a" },
        btn("Galerie", { kind: "neutral", icon: "gallery", onClick: () => { close(); openGallery(draft); } }),
        h("button", { "aria-label": "Prendre la photo", style: "width:76px;height:76px;border-radius:50%;border:4px solid var(--gold-light);background:#ddd;box-shadow:inset 0 0 0 4px #000", onclick: () => { close(); analyse(draft, { blurry: false }); } }),
        btn("Annuler", { kind: "neutral", onClick: back })));
  }, { full: true });
}

export function openGallery(draft) {
  modals.open((close) => {
    let sel = null; const use = btn("Utiliser cette photo", { kind: "primary", disabled: true, onClick: () => { close(); analyse(draft, sel); } });
    const photos = [["Ticket carburant", false, "#3b3326"], ["Ticket flou", true, "#2b2b2b"], ["Facture garage", false, "#2e3530"], ["Courses", false, "#33302c"], ["Parking", false, "#2a2f36"], ["Restaurant", false, "#362c2c"]];
    const grid = h("div", { style: "display:grid;grid-template-columns:repeat(3,1fr);gap:10px" }, photos.map(([name, blurry, c]) => {
      const tile = h("button", { style: `aspect-ratio:1;border-radius:6px;border:2px solid transparent;background:linear-gradient(160deg,${c},#111);display:flex;align-items:flex-end;padding:8px;font-size:12px;color:var(--text-2);${blurry ? "filter:blur(.6px)" : ""}`, "aria-label": name },
        name);
      tile.addEventListener("click", () => { grid.querySelectorAll("button").forEach((b) => (b.style.borderColor = "transparent")); tile.style.borderColor = "var(--gold)"; sel = { blurry, name }; use.disabled = false; });
      return tile;
    }));
    return modal({ title: "Choisir une photo", subtitle: "Galerie de démonstration — « Ticket flou » montre l'échec OCR.", close: () => { close(); openTransaction(draft); }, body: grid,
      foot: [btn("Annuler", { kind: "neutral", onClick: () => { close(); openTransaction(draft); } }), use] });
  });
}

async function analyse(draft, photo) {
  const l = loader("JUSTIFICATIF", "Lecture du justificatif…", "camera"); document.body.append(l);
  try {
    const r = await svc.runOcr(photo); l.remove();
    Object.assign(draft, { type: r.type, amount: String(r.amount).replace(".", ","), date: new Date(r.date).toISOString().slice(0, 10), label: r.label, category: "", source: null });
    const s = await svc.suggestCategory(r.label); draft.category = s.category; draft.source = s.source;
    openTransaction(draft);
  } catch (e) {
    // Même écran, message en rouge discret, 10 s puis retour au brouillon.
    l.classList.add("error"); l.querySelector(".ls").textContent = e.message;
    const c = h("div", { class: "tiny dim mono", style: "position:relative" }); l.append(c);
    for (let i = 10; i > 0; i--) { c.textContent = `Retour au formulaire dans ${i} s`; await sleep(1000); }
    l.remove(); openTransaction(draft);
  }
}

// ---------- Terminal générique, intervention, WR ----------
export function openTerminal({ ctx, initial, sub, onResult }) {
  modals.open((close) => {
    const t = terminal({ ctx, initial, onClose: close, sub });
    t.onResult = (r) => onResult?.(r, close, t);
    return h("div", { class: "modal wide", style: "height:min(820px,calc(100dvh - 48px));background:transparent;border:0" }, t.el);
  });
}

export function openIntervention() {
  openTerminal({ ctx: { kind: "intervention", label: "INTERVENTION REQUISE" },
    initial: [["IMPERIUM", "La mission « Renouveler la carte VTC » (projet Activité VTC) a dépassé son échéance d'il y a 2 jours. Elle est en attente et n'entre dans aucun plan.\nQue veux-tu faire : nouvelle échéance, faite ou annulée ?"]],
    onResult: async (r, close) => { if (r?.action === "resolveIntervention") { await svc.resolveIntervention(); await sleep(900); close(); toast("Intervention résolue."); app.refresh(); } } });
}

export async function startWR() {
  await withLoader("WEEKLY REVIEW", "Préparation de ton bilan…", () => svc.startWR(), "weekly_review");
  openTerminal({ ctx: { kind: "wr", label: "WEEKLY REVIEW" }, initial: [["IMPERIUM", "Commençons le bilan de ta semaine.\nQu'est-ce qui a bien fonctionné ?"]],
    onResult: async (r, close) => {
      if (r?.action !== "finishWR") return;
      await sleep(800); close();
      await withLoader("WEEKLY REVIEW", "Finalisation du bilan…", () => svc.finishWR(), "weekly_review");
      app.refresh(); setTimeout(() => app.refresh(), 10200);
      setTimeout(() => toast("Tu peux retrouver ta Weekly Review dans l'Historique.", { action: "Historique", onAction: () => app.go("historique"), ms: 6000 }), 10000);
    } });
}

// ---------- Confirmation de suppression (B2) ----------
export function confirmDelete({ name, text, onConfirm, label = "Supprimer" }) {
  modals.open((close) => {
    const del = btn(label, { kind: "danger", onClick: () => busy(del, async () => { try { await onConfirm(); close(); } catch (e) { toast(e.message || "La suppression a échoué."); } }) });
    return modal({ title: `Supprimer « ${name} » ?`, close, size: "small", body: h("div", { class: "muted" }, text),
      foot: [btn("Annuler", { kind: "neutral", onClick: close }), del] });
  });
}
export { fmtDM, pad, liveTimer, iconBtn };
