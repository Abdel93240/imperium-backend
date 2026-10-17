// FEED, FEED_IMPORT, FEED_CHAT, FEED_ITEM, FEED_SOURCES, FEED_RETAINED, FEED_CONVERSATION, FEED_DELETE (16, B10, doc 70 §7).
// Parcours : liste → Importer → sélecteur → (remplacé par) conversation → Enregistrer → retour liste.
import { h, icon, btn, iconBtn, modal, modals, toast, field, busy, comp, fmtLong, withLoader } from "../core.js";
import { svc } from "../services/index.js";
import { terminal } from "../terminal.js";

const STATE = { saved: ["Enregistré", "green"], to_validate: ["À valider", "gold"], to_analyze: ["À analyser", "grey"], error: ["Erreur de lecture", "red"] };
const ACCEPT = ".pdf,.txt,.md,.docx,.xlsx,.csv,.odt,.jpg,.jpeg,.png,.webp,.heic,.mp3,.m4a,.wav,.ogg,.opus,.mp4,.mov,.webm,.zip";

export async function openFeed(selectId) {
  const items = await svc.feedList();
  let q = "", filter = "all", sel = selectId || items[0]?.id;
  const builder = (close) => {
    const view = comp((c) => {
      const shown = items.filter((i) => (filter === "all" || (filter === "todo" && (i.state === "to_validate" || i.state === "to_analyze")) || (filter === "saved" && i.state === "saved") || (filter === "err" && i.state === "error")) && i.name.toLowerCase().includes(q.toLowerCase()));
      const it = items.find((i) => i.id === sel);
      return h("div", { class: "col", style: "gap:12px" },
        h("div", { class: "row", style: "border:1px solid #3b3d3b;border-radius:6px;padding:0 12px" }, icon("search", "gold", 20), h("input", { class: "input", style: "border:0;background:transparent", placeholder: "Rechercher un élément…", value: q, oninput: (e) => { q = e.target.value; const pos = e.target.selectionStart; c.rerender(); const n = c.el.querySelector("input"); n.focus(); n.setSelectionRange(pos, pos); } })),
        h("div", { class: "seg" }, [["all", "Tous"], ["todo", "À traiter"], ["saved", "Enregistrés"], ["err", "Erreurs"]].map(([k, l]) => h("button", { class: filter === k ? "on" : "", onclick: () => { filter = k; c.rerender(); } }, l))),
        shown.length ? h("div", { class: "col" }, shown.map((i) => h("button", { class: "listrow", style: `min-height:62px;padding:0 10px;${i.id === sel ? "border-left:2px solid var(--gold);background:#16171a" : ""}`, onclick: () => { sel = i.id; c.rerender(); } },
          h("span", { class: "col grow", style: "min-width:0" }, h("span", { class: "serif ellipsis", style: "font-size:19px" }, i.name), h("span", { class: "small muted" }, `${fmtLong(i.date)} · ${i.kind}`)),
          h("span", { class: "row small", style: "gap:6px" }, h("span", { class: `dot ${STATE[i.state][1]}` }), h("span", { class: STATE[i.state][1] === "grey" ? "muted" : STATE[i.state][1] }, STATE[i.state][0])), icon("chevron_right", "gold", 18))))
          : h("div", { class: "muted", style: "padding:20px 0;text-align:center" }, items.length ? "Aucun élément ne correspond." : "Rien n'a encore été transmis à l'IA. Appuie sur Importer."),
        it ? itemCard(it, close) : null);
    });
    return modal({ title: "Éléments transmis", subtitle: "Nourrir l'IA", close, size: "wide",
      headExtra: btn("Importer", { kind: "primary", icon: "plus", onClick: () => modals.replace(importStep) }), body: view, foot: [btn("Fermer", { kind: "neutral", onClick: close })] });
  };
  modals.open(builder);
}

function itemCard(it, close) {
  const row = (ic, label, fn, extra) => h("button", { class: "listrow", onclick: fn }, icon(ic, "gold", 22), h("span", { class: "grow" }, label, extra ? h("span", { class: "small muted" }, " · " + extra) : null), icon("chevron_right", "gold", 18));
  return h("section", { style: "border-top:1px solid var(--sep);padding-top:10px" },
    h("div", { class: "h2", style: "margin-bottom:6px" }, it.name),
    it.state === "to_analyze" ? h("div", { class: "row muted" }, h("span", { class: "spin", style: "width:14px;height:14px;border:2px solid currentColor;border-right-color:transparent;border-radius:50%;animation:spin .8s linear infinite" }), "En attente d'analyse par l'IA. Aucune action pour l'instant.") : null,
    it.state === "error" ? h("div", { class: "col", style: "gap:10px" }, h("div", { class: "red small" }, it.error), h("div", { class: "row" },
      (() => { const b = btn("Réessayer", { kind: "primary", icon: "refresh", onClick: () => busy(b, async () => { const f = await svc.feedRetry(it.id); toast("Lecture réussie : à valider."); modals.replace(chatStep({ name: f.name, conv: f.conv, resume: true })); }) }); return b; })(),
      btn("Ouvrir le chatbot", { kind: "neutral", onClick: () => modals.replace(chatStep({ name: it.name, conv: [["IMPERIUM", it.error + "\nTu peux m'envoyer une version non protégée ou me décrire le contenu."]], resume: true })) }))) : null,
    it.state === "to_validate" ? btn("Reprendre la validation", { kind: "primary", icon: "ai_common", onClick: () => modals.replace(chatStep({ name: it.name, conv: it.conv, resume: true })) }) : null,
    row("folder", "Sources", () => modals.open((c) => sourcesView(it, c)), `${it.sources.length} ${it.sources.length > 1 ? "fichiers" : "fichier"}`),
    it.state === "saved" ? row("notes", "Informations retenues", () => modals.open((c) => retainedView(it, c))) : null,
    it.conv?.length ? row("ai_common", "Conversation", () => modals.open((c) => convView(it, c))) : null,
    h("button", { class: "listrow", style: "color:var(--red)", onclick: () => feedDelete(it, close) }, icon("trash", "danger", 22), "Supprimer…"),
    h("div", { class: "tiny dim" }, "Sources et informations retenues sont liées."));
}

// ---------- Import ----------
export function importStep(close) {
  const files = [];
  const list = h("div", { class: "col" });
  const paint = () => list.replaceChildren(...(files.length ? files.map((f, i) => h("div", { class: "row", style: "min-height:48px;border-bottom:1px solid var(--sep-soft)" }, h("span", { class: "gold mono small" }, String(i + 1).padStart(2, "0")),
    icon(/image/.test(f.type) ? "gallery" : /audio/.test(f.type) ? "audio_file" : /video/.test(f.type) ? "video_file" : "file", "gold", 20), h("span", { class: "grow ellipsis" }, f.name), h("span", { class: "tiny dim mono" }, Math.max(1, Math.round(f.size / 1024)) + " Ko"),
    iconBtn("close", "Retirer " + f.name, () => { files.splice(i, 1); paint(); }))) : [h("div", { class: "small dim", style: "padding:10px 0" }, "Aucun fichier sélectionné.")]));
  paint();
  // Sélecteur générique : aucun présélecteur de type (doc 70). Formats et limites : doc 70 §6.
  // Pré-contrôle client (doc 70 §6) : 25 Mo par document/image, 500 Mo par audio/vidéo ; le backend fait le contrôle ferme.
  const limitOf = (f) => (/^(audio|video)\//.test(f.type) || /\.(mp3|m4a|wav|ogg|opus|mp4|mov|webm)$/i.test(f.name) ? 500 : 25) * 1024 * 1024;
  const input = h("input", { type: "file", multiple: true, accept: ACCEPT, style: "display:none", onchange: (e) => {
    const ok = [], refused = []; for (const f of e.target.files) (f.size > limitOf(f) || !ACCEPT.split(",").some((x) => f.name.toLowerCase().endsWith(x)) ? refused : ok).push(f);
    files.push(...ok); err.textContent = refused.length ? `Refusé : ${refused.map((f) => f.name).join(", ")} (type non accepté ou taille > 25 Mo documents/images, 500 Mo audio/vidéo).` : ""; e.target.value = ""; paint(); } });
  const ctx = h("textarea", { class: "textarea", style: "min-height:120px", placeholder: "Explique ce que contiennent ces éléments et ce que l'IA doit en retenir…" });
  const err = h("div", { class: "err" });
  const back = () => { close(); openFeed(); };
  const analyse = btn("Analyser", { kind: "primary", onClick: async () => {
    if (!files.length && !ctx.value.trim()) { err.textContent = "Ajoute un fichier ou écris un texte."; return; }
    close();
    const sess = await withLoader("NOURRIR L'IA", "Analyse des éléments…", () => svc.feedImport({ files: files.map((f) => ({ name: f.name, type: f.type, size: f.size })), context: ctx.value }), "ai_common");
    modals.open(chatStep({ name: sess.name, files: sess.files, context: sess.context }));
  } });
  return modal({ title: "Nourrir l'IA", subtitle: "Importer des éléments", close: back,
    body: [h("div", { class: "h3" }, "Éléments sélectionnés"), list, input, btn("Ajouter des éléments", { kind: "primary", block: true, icon: "plus", onClick: () => input.click() }),
      h("div", { class: "tiny dim" }, "Formats acceptés : pdf, txt, md, docx, xlsx, csv, odt, images, audio, vidéo, zip. Max 25 Mo par document ou image, 500 Mo par audio ou vidéo."),
      field("Contexte ou information à transmettre", ctx, { hint: "Tu peux aussi transmettre un texte sans fichier." }), err],
    foot: [btn("Annuler", { kind: "neutral", onClick: back }), analyse] });
}

function chatStep({ name, files = [], context = "", conv, resume }) { return (close) => {
  const attach = files.length ? h("div", { class: "row small", style: "margin:10px 18px 0;border:1px solid #3b3d3b;border-radius:6px;padding:8px 12px" }, icon("attachment", "gold", 18), `${files.length} fichier${files.length > 1 ? "s" : ""} joint${files.length > 1 ? "s" : ""}`) : null;
  const initial = conv || [["IMPERIUM", `COMPRÉHENSION\n${context ? "Selon tes précisions : " + context.slice(0, 220) : "J'ai lu les fichiers transmis."}\n\nPROPOSITION\nConserver ces éléments dans la mémoire comme contexte. Tu confirmes, ou tu corriges ?`]];
  const save = btn("Enregistrer", { kind: "primary", block: true, disabled: true, onClick: () => busy(save, async () => { await svc.feedSave(name); close(); toast("Enregistré dans la mémoire."); openFeed(); }) });
  const t = terminal({ ctx: { kind: "feed", label: "NOURRIR L'IA", attach }, initial, onClose: async () => { await svc.feedCancel(); close(); toast(resume ? "Validation interrompue : l'élément reste à valider." : "Import annulé : rien n'a été enregistré, le fichier est supprimé."); openFeed(); }, footer: h("div", { style: "padding:10px 14px 14px" }, save) });
  t.onResult = (r) => { if (r?.ready) save.disabled = false; };
  return h("div", { class: "modal wide", style: "height:min(860px,calc(100dvh - 48px));background:transparent;border:0" }, t.el);
}; }

function sourcesView(it, close) {
  return modal({ title: "Sources", subtitle: it.name, close, size: "small",
    body: it.sources.map(([n, type, size]) => h("button", { class: "listrow", onclick: () => toast("Aperçu du fichier : ouvert par la capacité Android adaptée (non disponible ici).") },
      icon(type === "Image" ? "gallery" : type === "Audio" ? "audio_file" : "file", "gold", 22), h("span", { class: "col grow" }, h("span", null, n), h("span", { class: "small muted" }, `${type} · ${size} · ${fmtLong(it.date)}`)), icon("eye", "gold", 18))),
    foot: [btn("Retour", { kind: "neutral", onClick: close })] });
}
function retainedView(it, close) {
  return modal({ title: "Informations retenues", subtitle: it.name, close, size: "small",
    body: [h("div", { class: "row small" }, icon("memory", "gold", 20), "Destination : ", h("span", { class: "gold" }, it.destination || "Mémoire"), h("span", { class: "dim" }, " · " + fmtLong(it.date))),
      h("div", { class: "term", style: "padding:14px;line-height:1.55" }, it.retained), h("div", { class: "tiny dim" }, "Lecture seule. Pour corriger, parle au chatbot.")],
    foot: [btn("Retour", { kind: "neutral", onClick: close })] });
}
function convView(it, close) {
  const t = terminal({ initial: it.conv, readOnly: true, onClose: close, sub: it.name });
  return h("div", { class: "modal wide", style: "height:min(700px,calc(100dvh - 48px));background:transparent;border:0" }, t.el);
}

// Supprimer : confirmation, puis le terminal exécute et confirme ; la ligne ne disparaît qu'après succès.
function feedDelete(it, closeList) {
  modals.open((close) => modal({ title: `Supprimer « ${it.name} » ?`, close, size: "small", body: h("div", { class: "muted" }, "Les sources et les informations retenues seront supprimées ensemble."),
    foot: [btn("Annuler", { kind: "neutral", onClick: close }), btn("Supprimer", { kind: "danger", onClick: () => { close(); closeList(); runDeleteTerminal(it); } })] }));
}
function runDeleteTerminal(it) {
  modals.open((close) => {
    const t = terminal({ ctx: { kind: "feedDelete", label: "SUPPRESSION" }, initial: [["IMPERIUM", `Je supprime « ${it.name} », ses sources et les informations retenues…`]], onClose: () => { close(); openFeed(); } });
    svc.feedDelete(it.id).then(() => { t.push("IMPERIUM", "C'est fait. Les influences indirectes déjà propagées ne sont pas annulées automatiquement."); setTimeout(() => { close(); openFeed(); toast("Élément supprimé."); }, 1800); })
      .catch(() => t.push("IMPERIUM", "La suppression a échoué. L'élément est conservé."));
    return h("div", { class: "modal wide", style: "height:min(520px,calc(100dvh - 48px));background:transparent;border:0" }, t.el);
  });
}
