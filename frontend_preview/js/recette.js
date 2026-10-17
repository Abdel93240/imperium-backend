// Recette automatisée (07_recette/RECETTE.csv) — exécutée dans la page : ?recette=R01
// Chaque contrôle agit sur l'interface réelle et renvoie { status, proof }.
import { clock, modals } from "./core.js";
import { svc } from "./services/index.js";
import { app } from "./app.js";

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
async function waitFor(fn, ms = 8000) { const t = Date.now(); while (Date.now() - t < ms) { if (fn()) return true; await wait(100); } return false; }
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const byText = (sel, txt, root = document) => $$(sel, root).find((e) => e.textContent.trim().includes(txt));
const btnT = (txt, root) => byText("button", txt, root);
const top = () => $$("#modals .backdrop").at(-1);
const text = (el = document.body) => el.innerText;
const inView = (el) => { const r = el.getBoundingClientRect(); return r.top >= -1 && r.bottom <= innerHeight + 1 && r.left >= -1 && r.right <= innerWidth + 1 && r.height > 0; };
const pageFixedOk = () => { const pb = $(".page-body.fixed"); return pb && pb.scrollHeight <= pb.clientHeight + 1 && document.scrollingElement.scrollHeight <= innerHeight + 1; };
function type(el, v) { el.value = v; el.dispatchEvent(new Event("input", { bubbles: true })); el.dispatchEvent(new Event("change", { bubbles: true })); }
async function go(page, scen) { if (scen) svc.setScenario(scen); location.hash = "#/" + page; await wait(50); await app.refresh(false); await wait(500); }
async function send(term, msg) { type($("textarea", term), msg); $("button[aria-label='Envoyer']", term).click(); await wait(3500); }
const P = (proof) => ({ status: "PASS", proof }), F = (proof) => ({ status: "FAIL", proof }), N = (proof) => ({ status: "NON TESTE", proof });
const check = (conds) => { const bad = Object.entries(conds).filter(([, v]) => !v).map(([k]) => k); return bad.length ? F("Échec : " + bad.join(" ; ")) : P(Object.keys(conds).join(" ; ")); };

const T = {
  async R01() { await go("dashboard");
    return check({ "2 bannières": $$(".banner").length === 2, "5 annexes": $$(".annexes li").length === 5, "mission, programme, finances, projets, conseils visibles": [".dash-mission", ".prog", ".dash-bottom", ".advice"].every((s) => $(s) && inView($(s))),
      "aucun défilement de page": pageFixedOk(), "programme défilant": $(".prog-list").scrollHeight > $(".prog-list").clientHeight }); },
  async R02() { await go("dashboard", { mission: "sport" });
    return check({ "aucun bloc annexes": !$(".annexes") && !text($(".dash-mission")).includes("Missions annexes"), "page fixe": pageFixedOk() }); },
  async R03() { await go("dashboard", { long: true }); const t = $(".mission-title"), d = $(".dash-mission .clamp3");
    const r = { "titre en ellipse (100 car.)": t.textContent.length >= 100 && t.scrollWidth > t.clientWidth, "description 800 car. limitée à 3 lignes": d.textContent.length >= 790 && d.scrollHeight > d.clientHeight + 2,
      "6 annexes en ellipse": $$(".annexes li").length === 6 && $$(".annexes li .ellipsis").some((e) => e.scrollWidth > e.clientWidth), "programme ≥ 25 missions": $$(".prog-item").length >= 25, "aucun défilement de page": pageFixedOk() };
    d.closest("button").click(); await wait(600); r["détail complet accessible (notes)"] = !!top() && text(top()).includes("Rassemble le justificatif"); return check(r); },
  async R04() { await go("dashboard", { day: "not_started" });
    return check({ "Journée non démarrée": text().includes("Journée non démarrée"), "bouton Démarrer": !!btnT("Démarrer la journée"), "ni mission": !$(".dash-mission"), "ni programme": !$(".prog") }); },
  async R05() { await go("dashboard", { empty: true }); const b = $(".dash-bottom");
    return check({ "message vide sobre": text().includes("Aucune mission pour l'instant"), "accès terminal": !!btnT("Ouvrir le chatbot"), "aucun chiffre fictif": !/\d/.test(b.innerText) }); },
  async R06() { svc.setScenario({ loading: true }); location.hash = "#/dashboard"; app.refresh(false); await wait(400); const r = { "skeletons": $$(".skel").length >= 4, "aria-busy": !!$("[aria-busy='true']"), "aucune donnée fictive": !text($("#main")).match(/Travail VTC|€/) }; svc.setScenario({ loading: false }); return check(r); },
  async R07() { await go("dashboard", { mission: "overtime" }); await wait(1100); const tm = $$(".dash-mission .mono").find((e) => e.textContent.startsWith("+"));
    const r = { "timer +00:12:0x": !!tm && /^\+00:12:0\d$/.test(tm.textContent), "rouge": !!tm && tm.classList.contains("red") }; btnT("Fait").click(); await wait(500); r["raison du dépassement demandée"] = text(top()).includes("Raison du dépassement"); r["texte « Temps dépassé · +00:12 »"] = text(top()).includes("+00:12"); return check(r); },
  async R08() { await go("dashboard", { longDay: true }); await wait(1100); const el = $$(".dash-day .mono").at(-1);
    return check({ "36:12 affiché": el.textContent.startsWith("36:12"), "pas de modulo 24": !el.textContent.startsWith("12:12") }); },
  async R09() { await go("dashboard"); btnT("Replanifier la journée").closest("div").querySelector("button"); const F2 = await import("./flows.js"); await F2.openReplan(); await wait(300);
    const m = top(); const sel = $("select", m); type(sel, "other"); await wait(100);
    return check({ "champ Autre raison affiché": $$(".field", m).some((f) => f.textContent.includes("Autre raison") && f.style.display !== "none"), "Détails toujours là": text(m).includes("Détails de la raison"), "aucune durée d'imprévu": !text(m).match(/durée/i) }); },
  async R10() { await go("dashboard", { cooldown: true }); const dash = btnT("Replanifier la journée"); const F2 = await import("./flows.js"); await F2.openReplan(); await wait(300); const dlg = btnT("Replanifier", top());
    const r = { "bouton dashboard désactivé": dash.disabled, "« Disponible dans 3 min »": text().includes("Disponible dans 3 min"), "bouton fenêtre désactivé": dlg.disabled };
    type($("textarea", top()), "Le client a annulé, je libère l'après-midi."); clock.offset += 3 * 60000 + 1000; await wait(1300); r["réactivation automatique (2 boutons)"] = !dash.disabled && !dlg.disabled; return check(r); },
  async R10b() { await go("dashboard", { cooldown: false }); const F2 = await import("./flows.js"); await F2.openReplan(); await wait(300); const m = top(), b = btnT("Replanifier", m);
    const r = { "bloqué sans détails": b.disabled }; type($("textarea", m), "Le client a annulé."); await wait(100); r["actif avec détails"] = !b.disabled;
    type($("select", m), "other"); await wait(100); r["Autre exige « Autre raison »"] = b.disabled; type($$("input", m)[0], "Panne de voiture"); await wait(100); r["actif avec Autre raison"] = !b.disabled; return check(r); },
  async R11() { await go("dashboard", { cooldown: false }); const before = (await svc.getDashboard()).plan.map((p) => p.title).join("|");
    const F2 = await import("./flows.js"); F2.openReplanValidate(await svc.requestReplan({ reason: "Fatigue — test" })); await wait(400); let m = top();
    const r = { "badges Déplacée/Nouvelle/Retirée": ["Déplacée", "Nouvelle", "Retirée"].every((b) => text(m).includes(b)) };
    await send($(".term", m), "Garde la lecture ce soir"); r["correction via terminal (Retirée → Déplacée, v2)"] = !text(m).includes("Retirée") && text(m).includes("v2");
    btnT("Annuler", m.querySelector(".modal-foot")).click(); await wait(500); r["Annuler préserve le plan"] = (await svc.getDashboard()).plan.map((p) => p.title).join("|") === before;
    F2.openReplanValidate(await svc.requestReplan({ reason: "Fatigue — test" })); await wait(400); m = top(); btnT("Accepter", m).click(); await wait(1500);
    r["Accepter applique"] = (await svc.getDashboard()).plan.some((p) => p.title === "Pause récupération"); return check(r); },
  async R12() { await go("dashboard"); const F2 = await import("./flows.js"); await F2.openTransaction(); await wait(400); const m = top(); const lab = $$("input", m).find((i) => i.placeholder === "Ex. Carburant");
    type(lab, "Carburant"); await wait(900); const cat = $$("select", m)[0]; const r = { "catégorie préremplie": cat.value === "Carburant", "badge Reconnu": text(m).includes("Reconnu"), "livre Business déduit": text(m).includes("Livre : Business") };
    type(cat, "Courses"); await wait(100); r["édition possible"] = text(m).includes("Choisi par toi") && text(m).includes("Livre : Perso"); return check(r); },
  async R13() { await go("dashboard"); const F2 = await import("./flows.js"); await F2.openTransaction(); await wait(400); const m = top(); const lab = $$("input", m).find((i) => i.placeholder === "Ex. Carburant");
    type(lab, "LECLERC DRIVE 4471"); await wait(1800);
    return check({ "Proposé par l'IA": text(m).includes("Proposé par l'IA"), "icône ai_common": $$("img", m).some((i) => i.src.includes("ai_common")), "Business/Perso dérivé": text(m).includes("Livre : Perso") }); },
  async R14() { await go("dashboard"); const F2 = await import("./flows.js"); await F2.openTransaction(); await wait(400); btnT("Importer un justificatif", top()).click(); await wait(300);
    $("button[aria-label='Prendre la photo']", top()).click(); await wait(400); const loading = text().includes("Lecture du justificatif"); await wait(4000); const m = top();
    const lab = $$("input", m).find((i) => i.placeholder === "Ex. Carburant"), amt = $$("input", m).find((i) => i.placeholder === "0,00");
    return check({ "chargement « Lecture du justificatif… »": loading, "retour prérempli": lab?.value === "TOTAL ENERGIES" && amt?.value === "54,2", "champs modifiables": !lab.readOnly && !amt.readOnly && !lab.disabled }); },
  async R15() { await go("dashboard"); const F2 = await import("./flows.js"); await F2.openTransaction(); await wait(400); let m = top(); type($$("input", m).find((i) => i.placeholder === "Ex. Carburant"), "Brouillon test"); type($$("input", m).find((i) => i.placeholder === "0,00"), "12,50");
    btnT("Importer un justificatif", m).click(); await wait(300); btnT("Galerie", top()).click(); await wait(300); $("button[aria-label='Ticket flou']", top()).click(); btnT("Utiliser cette photo", top()).click();
    await wait(3200); const err = $(".loader.error"); const r = { "message d'erreur rouge": !!err && err.innerText.includes("Échec de la lecture : image trop floue") };
    await wait(5000); r["encore affiché à 5 s"] = !!$(".loader.error"); await wait(5600); m = top();
    r["retour au brouillon intact après 10 s"] = !$(".loader") && $$("input", m).find((i) => i.placeholder === "Ex. Carburant")?.value === "Brouillon test" && $$("input", m).find((i) => i.placeholder === "0,00")?.value === "12,50"; return check(r); },
  async R16() { await go("dashboard"); const F2 = await import("./flows.js"); F2.openTerminal({ ctx: { kind: "standard" }, initial: [["IMPERIUM", "Bonjour."]] }); await wait(300); const m = top(); const mic = $("button[aria-label='Maintenir pour parler']", m), ta = $("textarea", m);
    mic.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, pointerId: 1 })); await wait(1200); const r = { "onde pendant l'appui": !!$(".wave", m) && ta.style.display === "none" };
    const n = $$(".msg", m).length; mic.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, pointerId: 1 })); await wait(300);
    r["transcription dans le champ"] = ta.value.length > 3 && !$(".wave", m); r["envoi manuel (aucun message envoyé)"] = $$(".msg", m).length === n; return check(r); },
  async R17() { await go("dashboard"); const F2 = await import("./flows.js"); F2.openTerminal({ ctx: { kind: "standard" }, initial: [] }); await wait(300); const m = top(); const mic = $("button[aria-label='Maintenir pour parler']", m), ta = $("textarea", m);
    type(ta, "mon brouillon"); mic.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, pointerId: 1 })); await wait(200); mic.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, pointerId: 1 })); await wait(300);
    return check({ "message d'erreur": text($("#toast")).includes("Je n'ai pas compris, réessaie"), "brouillon inchangé": ta.value === "mon brouillon" }); },
  async R18() { await go("dashboard"); const F2 = await import("./flows.js"); F2.openTerminal({ ctx: { kind: "standard" }, initial: Array.from({ length: 14 }, (_, i) => [i % 2 ? "VOUS" : "IMPERIUM", "Message " + (i + 1)]) }); await wait(300); const m = top(); $("textarea", m).focus(); await wait(500);
    const ok = [$$(".msg", m).at(-1), $("textarea", m), $("button[aria-label='Maintenir pour parler']", m), $("button[aria-label='Envoyer']", m)].every(inView);
    return ok ? N(`Simulation clavier (fenêtre ${innerWidth}×${innerHeight}) : dernier message, champ, micro et envoyer visibles. À confirmer sur la Tab S8 avec le clavier réel.`) : F(`Élément hors écran en ${innerWidth}×${innerHeight}.`); },
  async R19() { await go("operations"); const O = await import("./screens/operations.js"); O.editMission({ title: "Apprendre le russe", missions: [] }, null, () => {}); await wait(300); const m = top(); const notes = $$("textarea", m).at(-1); notes.focus(); notes.scrollIntoView({ block: "nearest" }); await wait(300);
    const body = $(".modal-body", m); const ok = inView(notes) && inView(btnT("Enregistrer", m)) && inView(btnT("Annuler", m)) && body.scrollHeight >= body.clientHeight;
    return ok ? N(`Simulation clavier (${innerWidth}×${innerHeight}) : champ bas et actions atteignables, défilement interne. À confirmer sur appareil.`) : F(`Champ ou action inaccessible en ${innerWidth}×${innerHeight}.`); },
  async R20() { app.offline = true; await go("dashboard", { offline: true }); const r = { "bannière hors ligne": !!$(".offline-bar"), "contenu du cache affiché": !!$(".dash-mission") };
    const F2 = await import("./flows.js"); F2.openTerminal({ ctx: { kind: "standard" }, initial: [] }); await wait(300); let m = top(); type($("textarea", m), "Test hors ligne"); $("button[aria-label='Envoyer']", m).click(); await wait(400);
    r["message marqué en attente"] = text(m).includes("en attente d'envoi"); modals.closeAll();
    const mis = (await svc.getDashboard()).mission; F2.openResult(mis, "done"); await wait(300); btnT("Valider", top()).click(); await wait(1200);
    r["pas de faux succès (refus explicite)"] = text($("#toast")).includes("Hors ligne") && (await svc.getDashboard()).mission.id === mis.id; app.offline = false; svc.setScenario({ offline: false }); return check(r); },
  async R21() { await go("dashboard", { error: true }); const r = { "Impossible de joindre Imperium": text().includes("Impossible de joindre Imperium"), "Réessayer": !!btnT("Réessayer"), "statut rouge": !!$("#main .dot.red") }; svc.setScenario({ error: false }); return check(r); },
  async R22() { await go("dashboard"); btnT("Commencer le Weekly Review").click(); await wait(3200); let m = top(); const r = { "terminal Weekly Review": !!m && text(m).includes("WEEKLY REVIEW"), "aucun bouton Suivant": !btnT("Suivant", m) && !btnT("Précédent", m) };
    await send($(".term", m), "J'ai tenu mon programme."); await send($(".term", m), "La fatigue du mercredi."); type($("textarea", m), "Oui, je valide."); $("button[aria-label='Envoyer']", m).click();
    r["finalisation"] = await waitFor(() => text().includes("Finalisation du bilan")); r["« Weekly Review faite » affichée"] = await waitFor(() => text($("#main")).includes("Weekly Review faite"));
    await wait(10600); r["bannière retirée après 10 s"] = !text($("#main")).includes("Weekly Review faite"); r["accès Historique proposé"] = text($("#toast")).includes("Historique"); return check(r); },
  async R23() { await go("reglages"); const S = await import("./screens/settings.js"); S.openPriorities(await svc.getPriorities()); await wait(300); const m = top(); const ups = $$("button[aria-label^='Monter']", m), downs = $$("button[aria-label^='Descendre']", m);
    const r = { "4 domaines fixes": ["Religieux", "Business", "Finances", "Santé"].every((d) => text(m).includes(d)) && ups.length === 4, "aucun CRUD": !/Ajouter|Renommer|Supprimer/.test(text(m)), "limites haut/bas": ups[0].disabled && downs[3].disabled };
    downs[0].click(); await wait(100); btnT("Enregistrer", top()).click(); await wait(900); r["enregistrement cohérent"] = (await svc.getPriorities()).join() === "Business,Religieux,Finances,Santé"; return check(r); },
  async R24() { await go("operations"); const O = await import("./screens/operations.js"); await O.openProjects(); await wait(400); let m = top(); const rows = () => $$(".listrow", m);
    const r = { "deux premiers actifs": rows().slice(0, 2).every((x) => x.textContent.includes("Actif")) && !rows()[2].textContent.includes("Actif") };
    rows()[2].click(); await wait(100); $("button[aria-label='Monter le projet']", m).click(); await wait(100); r["changement de rang → actif"] = rows()[1].textContent.includes("Apprendre le russe") && rows()[1].textContent.includes("Actif");
    modals.closeAll(); const res = await svc.completeTopProject(); const ops = await svc.getOperations(); r["au terme du n°1, le suivant est promu"] = ops.projects[0].title === "Activité VTC" && ops.projects[1].title === res.promoted; return check(r); },
  async R25() { await go("operations"); const blk = $$(".block").find((b) => b.textContent.includes("Imperium"));
    return check({ "pas de barre": !$(".progress", blk), "pas de faux 0 %": !blk.textContent.includes("0 %"), "mention de l'estimation à venir": blk.textContent.includes("prochain Weekly Review") }); },
  async R26() { await go("operations"); const O = await import("./screens/operations.js"); let saved; O.editRoutine(null, async (d) => { saved = d; }); await wait(300); let m = top(); const opts = $$("select option", m).map((o) => o.textContent);
    const r = { "quatre fréquences": opts.join("|") === "Chaque jour|Chaque semaine|Toutes les 2 semaines|Chaque mois", "aucun jour/heure/Autre": !$("input[type=time],input[type=date]", m) && !/Autre|Jour de|Heure/.test(text(m)) };
    type($$("input", m)[0], "Étirements"); btnT("Enregistrer", m).click(); await wait(300); r["création"] = saved?.name === "Étirements";
    O.editRoutine(saved, async (d) => { saved = d; }); await wait(300); m = top(); type($$("input", m)[0], "Étirements du soir"); btnT("Enregistrer", m).click(); await wait(300); r["édition"] = saved?.name === "Étirements du soir"; return check(r); },
  async R27() { await go("operations"); const O = await import("./screens/operations.js"); await O.openProjects("pr_apprendre_le_russe"); await wait(400); byText("button", "Supprimer", top()).click(); await wait(300); const m = top();
    return check({ "texte exact": text(m).includes("Supprimer « Apprendre le russe » ?") && text(m).includes("Ses missions à venir seront annulées ; l'historique est conservé."), "Annuler neutre": btnT("Annuler", m).classList.contains("neutral"), "Supprimer rouge": btnT("Supprimer", $(".modal-foot", m)).classList.contains("danger") }); },
  async R28() { await go("operations"); const O = await import("./screens/operations.js"); await O.openProjects("pr_apprendre_le_russe"); await wait(400); const m = top(); btnT("Choisir une méthode", m).click(); await wait(200);
    const bar = $$("span", m).find((s) => s.textContent.trim() === "Mission :").parentElement; return check({ "indisponibilité explicite": text(m).includes("Mission terminée : non supprimable"), "pas de bouton Supprimer pour la mission": !$$("button", bar).some((b) => b.textContent.includes("Supprimer")) }); },
  async R29() { await go("historique"); const rev = text($$("section").at(-1)), lists = $$(".listrow").length, pts = () => $$("polyline")[0].getAttribute("points").split(" ").length;
    const n3 = pts(); const sel = $("select[aria-label='Période des graphiques']"); type(sel, "semaine"); await wait(900);
    return check({ "graphes affectés (91 → 7 points)": n3 === 91 && pts() === 7, "bilan IA indépendant": text($$("section").at(-1)) === rev, "listes inchangées": $$(".listrow").length === lists, "pas de lissage (polyligne brute)": !!$("polyline") && !$("path[d*='C']") }); },
  async R30() { await go("reglages"); const Fd = await import("./screens/feed.js"); await Fd.openFeed(); await wait(400); btnT("Importer", top()).click(); await wait(300); let m = top(); const inp = $("input[type=file]", m);
    const r = { "sélecteur générique multiple": inp.multiple && inp.accept.includes(".pdf") && inp.accept.includes(".png"), "aucun présélecteur de type": !/Fichiers ?\/|Caméra|Audio ?\//.test(text(m)) };
    const dt = new DataTransfer(); dt.items.add(new File(["x"], "releve.pdf", { type: "application/pdf" })); dt.items.add(new File(["y"], "ticket.png", { type: "image/png" })); inp.files = dt.files; inp.dispatchEvent(new Event("change"));
    await wait(100); r["document et image ajoutés"] = text(m).includes("releve.pdf") && text(m).includes("ticket.png"); type($("textarea", m), "Relevé et ticket du mois.");
    btnT("Analyser", m).click(); await wait(3600); m = top(); r["analyse → terminal"] = text(m).includes("NOURRIR L'IA"); const save = btnT("Enregistrer", m); r["Enregistrer après validation seulement"] = save.disabled;
    await send($(".term", m), "Oui, conserve-les."); r["validé"] = !save.disabled; save.click(); await wait(1800); r["retour à la liste avec l'élément"] = text(top()).includes("Éléments transmis") && text(top()).includes("Relevé et ticket du mois"); return check(r); },
  async R31() { await go("reglages"); const Fd = await import("./screens/feed.js"); await Fd.openFeed(); await wait(400); const m = top(); const sel = async (n) => { btnT(n, m).click(); await wait(150); return $$("section", m).at(-1); };
    const a = await sel("Notes personnelles"), r = { "À analyser : attente sans action": text(a).includes("En attente d'analyse") && !btnT("Réessayer", a) && !btnT("Reprendre", a) };
    const v = await sel("Préférences d'organisation"); r["À valider : reprise du terminal"] = !!btnT("Reprendre la validation", v);
    const e = await sel("Document importé"); r["Erreur : Réessayer + Ouvrir le chatbot"] = !!btnT("Réessayer", e) && !!btnT("Ouvrir le chatbot", e);
    const s = await sel("Exemples de courses Bolt"); btnT("Informations retenues", s).click(); await wait(200); const ro = top(); r["sous-vues en lecture seule"] = !$("textarea,input", ro) && text(ro).includes("Lecture seule"); return check(r); },
  async R32() { await go("reglages"); const Fd = await import("./screens/feed.js"); await Fd.openFeed(); await wait(400); byText("button", "Supprimer…", top()).click(); await wait(200); let m = top();
    const r = { "confirmation": text(m).includes("Les sources et les informations retenues seront supprimées ensemble.") }; btnT("Supprimer", $(".modal-foot", m)).click(); await wait(300);
    r["terminal d'exécution"] = text(top()).includes("SUPPRESSION"); r["élément encore présent avant succès"] = (await svc.feedList()).some((f) => f.name === "Exemples de courses Bolt");
    await wait(4000); r["retiré après succès"] = !(await svc.feedList()).some((f) => f.name === "Exemples de courses Bolt"); return check(r); },
  async R33() { await go("reglages", { overlayDenied: true }); const S = await import("./screens/settings.js"); await S.openBubbleSettings(); await wait(300); const m = top(); const tg = $(".toggle", m); if (tg.classList.contains("on")) tg.click(); tg.click(); await wait(200);
    const r = { "aucune fausse activation": !tg.classList.contains("on"), "explication affichée": text(m).includes("s'afficher par-dessus les autres apps"), "renvoi aux réglages Android (Autoriser)": !!btnT("Autoriser", m) };
    svc.setScenario({ overlayDenied: false }); const c = check(r); return c.status === "PASS" ? N("Simulation web PASS (" + c.proof + "). Overlay Android réel non exécuté.") : c; },
  async R34() { await go("dashboard"); const S = await import("./screens/settings.js"); await S.openBubbleSim(); await wait(300); $("button[aria-label='Bulle Imperium']").click(); await wait(200); const m = top();
    const r = { "trois actions fixes": !!btnT("Terminer", m) && !!btnT("Échouer", m) && !!btnT("Demander une replanification complète de la journée", m), "pas d'accès terminal": !text(m).includes("chatbot") };
    btnT("Terminer", m).click(); await wait(400); r["réutilise le flux Fait"] = text(top()).includes("Valider la mission"); const c = check(r); return c.status === "PASS" ? N("Simulation web PASS (" + c.proof + "). Overlay Android réel non exécuté.") : c; },
  async R35() { await go("reglages"); const S = await import("./screens/settings.js"); await S.openNotifications(); await wait(300); const m = top(); const row = byText(".set-row", "Alertes rouges", m); $(".toggle", row).click(); await wait(200);
    return check({ "avertissement sous l'interrupteur": text(m).includes("tu ne seras plus prévenu des urgences"), "pas de canal alternatif": !$("select", m) && text(m).includes("notifications Android") }); },
  async R36() { await go("reglages"); const S = await import("./screens/settings.js"); S.openConnectForm(); await wait(300); const m = top(); const key = $("input[type=password]", m);
    btnT("Tester", m).click(); await wait(1300); const r = { "test lisible": text(m).includes("Serveur joignable") };
    type(key, "mauvaise"); btnT("Se connecter", m).click(); await wait(1600); r["Clé maître invalide"] = text(m).includes("Clé maître invalide"); r["clé effacée après échec"] = key.value === "";
    type(key, "demo"); btnT("Se connecter", m).click(); await wait(1600); r["succès simulé"] = text($("#toast")).includes("Connecté"); r["clé effacée"] = key.value === "";
    let st = ""; try { st = JSON.stringify(localStorage) + JSON.stringify(sessionStorage); } catch {} r["aucun secret persistant"] = !st.includes("demo") && !st.includes("mauvaise"); return check(r); },
  async R37() { await go("reglages"); const S = await import("./screens/settings.js"); await S.openThresholds(); await wait(300); const m = top(); const ins = $$("input", m); const save = () => { btnT("Enregistrer", m).click(); return wait(200); };
    type(ins[2], "98"); await save(); const r = { "chevauchement refusé et localisé": text(m).includes("chevauchement entre « IA locale » et « Premier niveau cloud »") };
    type(ins[2], "105"); await save(); r["trou refusé et localisé"] = text(m).includes("Trou ou chevauchement entre « IA locale » et « Premier niveau cloud »");
    type(ins[2], "100"); await save(); await wait(800); r["valeurs valides enregistrées"] = !top()?.innerText.includes("Seuils de score"); return check(r); },
  async R38() { await go("reglages"); const S = await import("./screens/settings.js"); await S.openApiKeys(); await wait(300); const m = top();
    const r = { "aucune valeur de clé affichée": !/sk-|key_|•{4}/.test(text(m)) && text(m).includes("Clé enregistrée") };
    btnT("Remplacer", m).click(); await wait(200); const k = top(); const inp = $("input[type=password]", k); r["remplacement en écriture seule (champ vide, masqué)"] = inp.value === "" && !$("button[aria-label='Afficher la clé']", k); btnT("Annuler", k).click(); await wait(200);
    btnT("Supprimer", m).click(); await wait(200); r["confirmation destructive"] = !!btnT("Supprimer", $(".modal-foot", top())) && btnT("Supprimer", $(".modal-foot", top())).classList.contains("danger"); return check(r); },
  async R39() { await go("reglages"); const S = await import("./screens/settings.js"); await S.openModelRoles(); await wait(400); const m = top(); const r = { "pas d'ajout de rôle": !/Ajouter/.test(text(m)) };
    $$("button", m).find((b) => b.textContent === "Modifier").click(); await wait(1300); const e = top(); r["modèle sans effort : champ masqué"] = !byText("label", "Effort", e) && text(e).includes("ne gère pas"); return check(r); },
  async R40() { await go("reglages"); let calls = 0; const orig = svc.savePriorities; svc.savePriorities = async (...a) => { calls++; return orig(...a); }; const S = await import("./screens/settings.js"); S.openPriorities(await svc.getPriorities()); await wait(300);
    const b = btnT("Enregistrer", top()); b.click(); const dis = b.disabled; b.click(); b.click(); await wait(900); svc.savePriorities = orig; return check({ "désactivé pendant l'attente": dis, "un seul traitement": calls === 1 }); },
  async R41() { await go("reglages"); const S = await import("./screens/settings.js"); await S.openConnection(); await wait(600); const m = top();
    const row = (l) => byText(".set-row", l, m); return check({ "mémoire, IA locale, IA cloud en Non vérifié gris": ["Mémoire vectorielle", "IA locale", "IA cloud"].every((l) => row(l)?.textContent.includes("Non vérifié") && $(".dot.grey", row(l))), "pas de vert simulé": ["Mémoire vectorielle", "IA locale", "IA cloud"].every((l) => !$(".dot.green", row(l))), "en-tête IA non vérifiée": text($("#topRight")).includes("IA : non vérifiée") }); },
  async R42() { await go("reglages"); const S = await import("./screens/settings.js"); await S.openLogs(); await wait(400); const m = top(); const names = $$(".listrow", m).map((b) => b.textContent);
    btnT("Nourrir l'IA", m).click(); await wait(100); return check({ "tri récent d'abord": names[0].startsWith("2026-10-16") && names.at(-1).startsWith("2026-10-14"), "terminal de contenu": text($(".term", top())).includes("feed.import"), "lecture seule": !$("textarea,input", top()) }); },
  async R43() { await go("dashboard"); const r = { [`dashboard sans défilement (${innerWidth}×${innerHeight})`]: pageFixedOk(), "aucun débordement horizontal": document.scrollingElement.scrollWidth <= innerWidth + 1, "contrôles visibles": $$(".dash button").every((b) => b.getBoundingClientRect().right <= innerWidth + 1) };
    const F2 = await import("./flows.js"); svc.setScenario({ cooldown: false }); F2.openReplanValidate(await svc.requestReplan({ reason: "x" })); await wait(400); const sp = $(".split", top()); r[innerWidth >= 1100 ? "replan en 2 colonnes" : "replan empilé"] = (getComputedStyle(sp).gridTemplateColumns.split(" ").length === 2) === innerWidth >= 1100; return check(r); },
  async R44() { await go("dashboard"); const imgs = $$("img"); const ai = imgs.filter((i) => /brain|robot|ia_|sparkle/.test(i.src)); const logo = $(".brand img"), cal = $(".calli");
    return check({ "aucun autre symbole IA": ai.length === 0, "ai_common sur Conseils IA": $$(".advice img").some((i) => i.src.includes("ai_common")), "logo source sans déformation": logo.src.endsWith("logo_imperium_original.png") && getComputedStyle(logo).objectFit === "contain", "calligraphie source sans déformation": cal.src.endsWith("calligraphie_compacte_retenue.png") && getComputedStyle(cal).objectFit === "contain" && cal.alt.includes("الساعة") }); },
  async R45() { const r = {}; for (const [p, t] of [["dashboard", "Dashboard"], ["operations", "Gestion des opérations"], ["historique", "Historique"], ["reglages", "Réglages"]]) { await go(p); r[`navigation ${t}`] = $("#pageTitle").textContent === t; }
    await go("reglages"); const rows = $$("#main .listrow"); let opened = 0; for (const b of rows) { b.click(); await wait(700); if (modals.depth) opened++; modals.closeAll(); } r[`${rows.length} entrées de Réglages ouvrent une vue`] = opened === rows.length;
    await go("dashboard"); const F2 = await import("./flows.js"); await F2.openTransaction(); await wait(300); type($$("input", top()).find((i) => i.placeholder === "Ex. Carburant"), "Garde-moi"); btnT("Importer un justificatif", top()).click(); await wait(300); btnT("Annuler", top()).click(); await wait(500);
    r["retour de la caméra : brouillon conservé"] = $$("input", top()).find((i) => i.placeholder === "Ex. Carburant")?.value === "Garde-moi"; return check(r); },
  async R46() { let fetches = 0; const of = window.fetch; window.fetch = (...a) => { fetches++; return of(...a); }; await go("dashboard"); const F2 = await import("./flows.js"); const mis = (await svc.getDashboard()).mission; F2.openResult(mis, "done"); await wait(200); btnT("Valider", top()).click(); await wait(1500);
    window.fetch = of; const B = await import("./services/backend.js"); let err = ""; try { await B.createBackendAdapter().createTransaction({}); } catch (e) { err = e.message; }
    return check({ "aucune requête réseau en démo": fetches === 0, "fournisseur démo identifié": svc.kind === "demo", "adaptateur réel séparé, même interface": err.includes("POST /api/imperium/vault/transactions") }); },
  async R47() { await go("dashboard", { cooldown: true }); await wait(1100); const el = $$(".dash-day .mono").at(-1), t0 = el.textContent; clock.offset += 10 * 60000; await wait(1300); const t1 = el.textContent; const toS = (s) => s.split(":").reduce((a, b) => a * 60 + +b, 0);
    return check({ "timer recalculé (+10 min)": Math.abs(toS(t1) - toS(t0) - 600) <= 3, "cooldown conservé puis libéré à l'échéance": !btnT("Replanifier la journée").disabled }); },
  async R48() { await go("dashboard"); const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches; const l = document.createElement("div"); l.className = "loader"; document.body.append(l); const anim = getComputedStyle(l, "::before").animationName; l.remove();
    const b = btnT("Voir tout"); b.focus(); b.click(); await wait(500); document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" })); await wait(100);
    return check({ "mode réduction d'animation actif": reduced, "chargement sans animation": anim === "none", "focus restauré après fermeture": document.activeElement === b }); },
  async R49() { await go("dashboard"); btnT("Terminer la journée").click(); await wait(200); const noPopup = modals.depth === 0; await wait(1500); await app.refresh(false); await wait(600);
    return check({ "clôture sans popup": noPopup, "journée close": text().includes("Journée non démarrée"), "conséquence serveur : standby → Intervention requise": text().includes("Intervention requise") }); },
  async R50() { let all = ""; for (const p of ["dashboard", "operations", "historique", "reglages"]) { await go(p); all += text($("#main")); }
    const S = await import("./screens/settings.js"); for (const f of [S.openNotifications, S.openConnection, S.openAdvanced, S.openBubbleSettings]) { await f(); await wait(500); all += text(top()); modals.closeAll(); }
    const vous = all.replace(/> VOUS/g, "").match(/\b(vous|votre|vos)\b/gi);
    return check({ "tutoiement (aucun vous/votre)": !vous, "Historique partout, pas de Hall of Fame": !/Hall of Fame/i.test(all) && all.includes("Historique"), "pas de Widget accueil": !/widget/i.test(all), "pas de priorités libres": !/Ajouter une priorité|Renommer/.test(all) }); },
};

export async function run(id) {
  const out = document.createElement("pre"); out.id = "recette-result"; out.style.display = "none";
  let res; try { res = await (T[id] ? T[id]() : { status: "NON TESTE", proof: "Contrôle inconnu" }); } catch (e) { res = { status: "FAIL", proof: "Exception : " + (e?.message || e) }; }
  out.textContent = JSON.stringify({ id, viewport: `${innerWidth}×${innerHeight}`, ...res }); document.body.append(out);
  document.title = `${id} ${res.status}`;
}
