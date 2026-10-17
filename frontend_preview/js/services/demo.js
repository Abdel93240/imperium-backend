// FOURNISSEUR DE DÉMONSTRATION — données fictives, aucune requête réseau.
// Les composants n'importent jamais ce fichier : ils passent par services/index.js.
import { sleep, clock } from "../core.js";

const MIN = 60000, HOUR = 60 * MIN, DAY = 24 * HOUR;
let seq = 1000; const id = (p) => `${p}_${++seq}`;
const clone = (x) => structuredClone(x);

// Générateur pseudo-aléatoire déterministe pour l'historique.
function rng(seed) { return () => ((seed = (seed * 16807) % 2147483647) / 2147483647); }

export function createDemoProvider() {
  // Horloge contrôlée (DEMO.json) : la démo démarre toujours à 07:24:18, heure locale.
  { const t = new Date(); t.setHours(7, 24, 18, 0); clock.offset = +t - Date.now(); }
  const now = () => clock.now();
  const scen = { mission: "vtc", day: "active", loading: false, empty: false, error: false, offline: false, cooldown: true, long: false, longDay: false, overlayDenied: false };
  const db = {};

  function buildDay() {
    const t0 = now();
    const start = scen.longDay ? t0 - (36 * HOUR + 12 * MIN) : t0 - (3 * HOUR + 54 * MIN + 18 * 1000);
    db.day = { id: "day_demo", startedAt: start, state: scen.day };
    const vtc = { id: "m_vtc", title: "Travail VTC", kind: "urgente", plannedStart: t0 - (24 * MIN + 18 * 1000), // 07:00 (DEMO.json) durationMin: 300,
      description: "Effectue ta session VTC du matin. Ouvre Vector pour consulter les opportunités. Profite des pauses à l’arrêt pour tes missions annexes.",
      notes: "Objectif de la session : 350 €. Zone aéroport conseillée entre 9 h et 11 h.",
      annexes: [
        { id: "a1", title: "Appeler Yacine" }, { id: "a2", title: "Confirmer RDV dentiste" }, { id: "a3", title: "Vérifier prix garage" },
        { id: "a4", title: "Répondre à Marie" }, { id: "a5", title: "Réserver contrôle technique" }] };
    const sport = { id: "m_sport", title: "Séance de sport", kind: "importante", plannedStart: t0 - 27 * MIN, durationMin: 45,
      description: "Aujourd’hui, travaille le dos et la posture. Ouvre Pulse pour démarrer ta séance et enregistrer tes séries.",
      notes: "Garde 2 min de récupération entre les séries lourdes.", annexes: [] };
    const cur = scen.mission === "vtc" ? vtc : sport;
    if (scen.mission === "overtime") cur.plannedStart = t0 - (45 + 12) * MIN;
    if (scen.long) Object.assign(cur, {
      title: "Préparer le dossier complet de renouvellement de la carte professionnelle VTC avec toutes les pièces",
      description: ("Rassemble le justificatif de domicile, les deux photos d'identité, l'attestation d'assurance et le certificat médical. ").repeat(8).slice(0, 800),
      annexes: ["Appeler Yacine pour confirmer le rendez-vous de samedi au garage de la rue principale", "Confirmer le rendez-vous chez le dentiste et demander le devis complet", "Vérifier les prix de trois garages pour la révision des 120 000 km", "Répondre à Marie au sujet de l'organisation du repas familial de dimanche", "Réserver le contrôle technique avant la fin du mois pour éviter l'amende", "Envoyer la facture de septembre au comptable avec les justificatifs"].map((t, i) => ({ id: "al" + i, title: t })) });
    const at = (offMin) => start + offMin * MIN;
    const items = [
      { id: "p1", title: "Routine du matin", plannedStart: at(0), durationMin: 30, status: "faite", notes: "Ablutions, Fajr, adhkar du matin." },
      { id: "p2", title: "Préparation de la journée", plannedStart: at(30), durationMin: 60, status: "faite", notes: "" },
    ];
    if (scen.mission === "vtc") {
      items.push({ id: "p3", title: "Séance de sport", plannedStart: at(150), durationMin: 45, status: "faite", notes: sport.notes });
      items.push({ ...vtc, status: "active" });
    } else {
      items.push({ ...cur, status: "active" });
      items.push({ ...vtc, id: "m_vtc_next", plannedStart: cur.plannedStart + 60 * MIN, status: "prévue", annexes: vtc.annexes });
    }
    const after = items.at(-1).plannedStart + items.at(-1).durationMin * MIN;
    [["Déjeuner", 45], ["Démarches administratives", 60], ["Reprise VTC", 180], ["Temps en famille", 120], ["Lecture", 20], ["Bilan et repos", 30]]
      .concat(scen.long ? Array.from({ length: 16 }, (_, i) => [`Mission supplémentaire n° ${i + 1} au titre volontairement très long pour tester l'ellipse`, 15]) : [])
      .reduce((t, [title, d]) => { items.push({ id: id("p"), title, plannedStart: t, durationMin: d, status: "prévue", notes: title === "Démarches administratives" ? "Préfecture : apporter justificatif de domicile et 2 photos." : "", deadline: title === "Démarches administratives" ? now() - 30 * MIN : null }); return t + d * MIN + 15 * MIN; }, after + 15 * MIN);
    db.plan = items;
    db.currentId = cur.id;
    db.mission = cur;
    db.replan = { eligibleAt: scen.cooldown ? t0 + 3 * MIN : 0, proposal: null }; // availableAt = now + 3 min (DEMO.json)
  }

  db.wr = { state: "pending" }; // pending | done_recent | none
  db.standby = [{ id: "m_admin_old", title: "Renouveler la carte VTC", deadline: now() - 2 * DAY, project: "Activité VTC" }];

  db.finance = {
    wallets: [{ id: "w_cash", label: "Cash", icon: "cash", value: 1000 }, { id: "w_bank", label: "Comptes", icon: "bank", value: 3000 }, { id: "w_crypto", label: "Crypto", icon: "crypto", value: 500 }],
    pressure: { score: 52 },
    tx: [],
  };
  const txSeed = [["VTC", 500], ["Carburant", -17], ["Courses", -42], ["VTC", 280], ["Stationnement", -8], ["VTC", 190], ["Téléphone", -15], ["Carburant", -54], ["VTC", 320], ["Courses", -63], ["Restaurant", -24], ["VTC", 410], ["Loyer", -650], ["VTC", 365]];
  txSeed.forEach(([label, amount], i) => db.finance.tx.push({ id: id("tx"), label, amount, date: now() - Math.floor(i / 2) * DAY - i * HOUR, wallet: amount > 0 ? "w_bank" : i % 3 ? "w_bank" : "w_cash", category: KNOWN[norm(label)] || "Courses" }));

  db.categories = [
    { name: "Revenus VTC", book: "Business" }, { name: "Carburant", book: "Business" }, { name: "Entretien véhicule", book: "Business" },
    { name: "Téléphone", book: "Business" }, { name: "Stationnement", book: "Business" }, { name: "Péage", book: "Business" },
    { name: "Courses", book: "Perso" }, { name: "Restaurant", book: "Perso" }, { name: "Loyer", book: "Perso" }, { name: "Santé", book: "Perso" }, { name: "Loisirs", book: "Perso" }];

  db.projects = [
    P("Imperium", null, null, [["Définir les modules", 1], ["Choisir les polices", 1], ["Valider le style", 1], ["Finaliser le dashboard", 0, 240], ["Concevoir les opérations", 0, 180], ["Préparer l'intégration", 0, 120]]),
    P("Activité VTC", 35, "Les premières étapes sont terminées.", [["Définir les services", 1], ["Préparer les offres", 0, 90], ["Créer la présentation", 0, 120], ["Organiser les contacts", 0, 60], ["Lancer les premiers échanges", 0, 45]]),
    P("Apprendre le russe", null, null, [["Choisir une méthode", 1], ["Faire des cours avec Ivanov", 0, 60, "Suivre un cours pour travailler la conversation et la prononciation.", "Ivanov est disponible uniquement le vendredi de 14 h à 16 h."], ["Réviser le vocabulaire", 0, 15]]),
    P("Installation à Tanger", null, null, [["Lister les démarches", 0, 30], ["Chercher un logement", 0, 120]]),
    P("Apprendre l'espagnol", null, null, [["Choisir une application", 0, 15]]),
    P("Développer les navettes", null, null, [["Étudier la demande aéroport", 0, 60]]),
    P("Aménager le bureau", null, null, [["Mesurer la pièce", 0, 15]]),
  ];
  db.projects[1].progressAt = now() - 6 * DAY; // updatedAt 2026-10-11
  db.projects[2].description = "Pouvoir tenir une conversation simple et comprendre les échanges du quotidien.";

  db.routines = [
    R("Lecture", "daily", 20, "medium", "Prévoir un moment calme pour lire."), R("Mobilité", "daily", 10, "high"), R("Planifier la journée", "daily", 10, "medium"),
    R("Suivi des comptes", "daily", 10, "high"), R("Rangement", "daily", 15, "low"), R("Révision de vocabulaire", "daily", 15, "medium"),
    { ...R("Entretien du véhicule", "weekly", 30, "high"), plannedToday: true }, { ...R("Classement des papiers", "biweekly", 20, "low"), active: false }];

  // Historique : 420 journées.
  const rand = rng(7); db.days = [];
  for (let i = 420; i >= 1; i--) {
    const total = 8 + Math.floor(rand() * 6), trend = 0.55 + 0.3 * (1 - i / 420);
    const done = Math.min(total, Math.max(2, Math.round(total * (trend + (rand() - 0.5) * 0.35))));
    const wTotal = total * 2 + Math.floor(rand() * 6), wDone = Math.round(wTotal * done / total);
    const start = now() - i * DAY - (rand() * 2 + 2.5) * HOUR - 10 * HOUR;
    db.days.push({ id: "d" + i, date: start, start, end: start + (13 + rand() * 4 + (i % 37 === 0 ? 14 : 0)) * HOUR, done, total, wDone, wTotal, balance: 1500 + (420 - i) * 7.2 + Math.sin(i / 9) * 160 + rand() * 90 });
  }
  db.finished = [
    { id: "hp1", title: "Installer le poste de travail", doneAt: now() - 19 * DAY, notes: "Le poste de travail est prêt à être utilisé.", missions: [["Définir les besoins", ""], ["Choisir le matériel", "Écran 27 pouces retenu."], ["Installer les équipements", ""], ["Vérifier le fonctionnement", "Installation terminée. Les équipements ont été vérifiés."]] },
    { id: "hp2", title: "Organiser les documents", doneAt: now() - 35 * DAY, notes: "Classeur administratif à jour.", missions: [["Trier les papiers", ""], ["Scanner les originaux", ""]] },
    { id: "hp3", title: "Préparer les offres VTC", doneAt: now() - 48 * DAY, notes: "", missions: [["Lister les tarifs", ""], ["Rédiger la grille", ""]] },
    { id: "hp4", title: "Créer le budget familial", doneAt: now() - 91 * DAY, notes: "", missions: [["Relever les dépenses fixes", ""], ["Fixer les enveloppes", ""]] },
  ];
  db.aiReview = { date: now() - 3 * DAY, title: "Des progrès qui s'accumulent", text: ["Sur les trois derniers mois, ta régularité progresse et ton solde total augmente. Quatre projets ont été menés à terme. Ces avancées sont concrètes, même si elles restent peu visibles au quotidien.", "Certaines journées restent très chargées. L'enjeu est de consolider ce rythme en gardant une charge soutenable."] };

  db.settings = { bubble: true, notif: true, morningPopup: true, replanUrgent: "replanifier", replanOther: "demander", debounce: 5, aiMode: "equilibre", chatRetention: 90,
    notifs: { checkin: true, wr: true, reminders: true, red: true } };
  db.priorities = ["Religieux", "Business", "Finances", "Santé"];
  db.permissions = [
    { id: "camera", label: "Caméra", desc: "Photographier un justificatif", icon: "camera", state: "ok" },
    { id: "mic", label: "Microphone", desc: "Dicter et parler au terminal", icon: "microphone", state: "ok" },
    { id: "loc", label: "Localisation", desc: "Utiliser ta position", icon: "location", state: "no" },
    { id: "files", label: "Fichiers", desc: "Accéder aux éléments sélectionnés", icon: "folder", state: "partial" },
    { id: "overlay", label: "Bulle flottante", desc: "Afficher le panneau au-dessus des autres apps", icon: "bubble_overlay", state: "ok" }];
  db.roles = [
    ["local_executor", "OpenRouter", "Qwen3.6-27B"], ["first_cloud_tier", "Anthropic", "Claude Sonnet 5"], ["high_reasoning", "Anthropic", "Claude Opus 5.5"],
    ["sustained_long_context", "Anthropic", "Claude Fable 5.1"], ["health_specialist", null, null], ["finance_specialist", null, null],
    ["web_fresh_data", "OpenAI", "GPT-5.6 Sol"], ["high_reasoning_safeguard", "OpenAI", "GPT-6 Astra"], ["ocr_service", null, null], ["transcription_service", null, null], ["embedding_service", null, null]]
    .map(([role, provider, model]) => ({ role, provider, model, effort: model && provider === "Anthropic" ? "Moyen" : null }));
  db.catalog = { OpenRouter: ["Qwen3.6-27B", "Qwen3.6-72B", "Mistral Large 3"], Anthropic: ["Claude Sonnet 5", "Claude Opus 5.5", "Claude Fable 5.1", "Claude Haiku 5.5"], OpenAI: ["GPT-5.6 Sol", "GPT-6 Astra"], Google: ["Gemini 3 Pro"] };
  db.thresholds = [{ label: "IA locale", from: 0, to: 99 }, { label: "Premier niveau cloud", from: 100, to: 139 }, { label: "Raisonnement poussé", from: 140, to: 179 }, { label: "Mécanique critique", from: 180, to: 200 }];
  db.apiKeys = [{ provider: "OpenRouter", present: true }, { provider: "Anthropic", present: true }, { provider: "OpenAI", present: true }, { provider: "Google", present: false }];
  db.logs = [
    { id: "l1", name: "2026-10-16 · Weekly Review", date: now() - 1 * DAY, content: "[22:10:04] wr.session.start week=2026-W42\n[22:10:05] role=local_executor score=72/200 → local\n[22:14:31] section=imperium missions=58 faites=46\n[22:15:02] project_progress Imperium=60 « style et polices validés »\n[22:15:02] project_progress Activité VTC=30\n[22:21:47] wr.final_draft stored\n[22:22:10] wr.approve ok" },
    { id: "l2", name: "2026-10-15 · Nourrir l'IA · Exemples de courses Bolt", date: now() - 2 * DAY, content: "[18:02:11] feed.import files=3 type=image/png\n[18:02:13] ocr_service ok ×3\n[18:02:20] extraction: 01 refusée, 02 acceptée, 03 sans réponse\n[18:03:40] user.validate destination=memory\n[18:03:41] embedding_service chunks=4 ok" },
    { id: "l3", name: "2026-10-15 · Replanification", date: now() - 2 * DAY, content: "[14:20:03] replan.request reason=« Imprévu — rendez-vous annulé »\n[14:20:04] debounce ok (dernier replan 11:02)\n[14:20:09] proposal v3 : 2 déplacées, 1 retirée\n[14:21:15] user.accept v3" },
    { id: "l4", name: "2026-10-14 · Catégorisation · libellé inconnu", date: now() - 3 * DAY, content: "[09:41:00] vault.category label=« LECLERC DRIVE 4471 » table=miss\n[09:41:01] local_executor → Courses (confiance 0.91)\n[09:41:30] user.confirm → user_category_memory += « LECLERC DRIVE »" }];
  db.feed = [
    { id: "f1", name: "Exemples de courses Bolt", date: now() - 2 * DAY, kind: "3 images", state: "saved", sources: [["capture_01.png", "Image", "412 Ko"], ["capture_02.png", "Image", "398 Ko"], ["capture_03.png", "Image", "405 Ko"]], retained: "Trois propositions de courses Bolt : la première refusée, la deuxième acceptée, la troisième sans réponse à temps (distincte d'un refus). Raisons des refus à préciser.", destination: "Mémoire", conv: [["IMPERIUM", "Selon tes précisions :\n01 — course refusée\n02 — course acceptée\n03 — aucune réponse à temps"], ["VOUS", "Oui, conserve-les comme exemples."], ["IMPERIUM", "C'est enregistré dans la mémoire."]] },
    { id: "f2", name: "Préférences d'organisation", date: now() - 3 * DAY, kind: "Texte", state: "to_validate", sources: [["texte", "Texte", "1 Ko"]], retained: null, conv: [["IMPERIUM", "Tu préfères les tâches administratives le matin. Je l'enregistre dans la mémoire ?"]] },
    { id: "f3", name: "Notes personnelles", date: now() - 3 * DAY, kind: "Audio", state: "to_analyze", sources: [["note_vocale.m4a", "Audio", "2,1 Mo"]] },
    { id: "f4", name: "Document importé", date: now() - 4 * DAY, kind: "PDF", state: "error", error: "Erreur de lecture : le PDF est protégé par un mot de passe.", sources: [["releve.pdf", "PDF", "880 Ko"]] }];

  buildDay();

  // ---------- helpers ----------
  async function io(ms = 350) {
    await sleep(ms); while (scen.loading) await sleep(200);
    if (scen.error) throw Object.assign(new Error("Impossible de joindre Imperium"), { code: "SERVER" });
  }
  function nextMission(p) { return p.missions.find((m) => m.status !== "faite"); }
  const activeProjects = () => db.projects.slice(0, 2);

  const api = {
    kind: "demo",
    scenario: scen,
    setScenario(patch) { Object.assign(scen, patch); if (["mission", "cooldown", "day", "long", "longDay"].some((k) => k in patch)) buildDay(); },

    async getStatus() { await io(120); return { server: scen.offline ? "red" : "green", ai: "grey", checkedAt: now(),
      services: [["API Imperium", "green"], ["Base de données", "green"], ["Mémoire vectorielle", "grey"], ["IA locale", "grey"], ["IA cloud", "grey"]].map(([label, s]) => ({ label, state: scen.offline ? "grey" : s })) }; },

    async getDashboard() {
      await io();
      if (scen.empty) return { empty: true, day: { state: scen.day, startedAt: db.day.startedAt }, plan: [], finance: { balance: 0, tx: [], pressure: null }, projects: [], wr: "none", intervention: false, advice: null };
      const bal = db.finance.wallets.reduce((s, w) => s + w.value, 0);
      return {
        day: { state: db.day.state, startedAt: db.day.startedAt },
        wr: db.wr.state, intervention: db.standby.length > 0,
        mission: db.day.state === "active" ? (() => { const m = clone(db.plan.find((p) => p.status === "active")); const q = m && api.pendingFor(m.id); if (q) m.pendingResult = q.label; return m; })() : null,
        pendingFinish: db.pending.some((p) => p.status === "pending" && p.type === "finishDay"),
        plan: db.day.state === "active" ? clone(db.plan) : [],
        replan: { eligibleAt: db.replan.eligibleAt },
        finance: { balance: bal, pressure: db.finance.pressure.score, tx: clone(db.finance.tx.slice(0, 3)) },
        projects: activeProjects().map((p) => ({ id: p.id, title: p.title, next: nextMission(p)?.title || "—" })),
        advice: { title: "Prépare tes démarches", text: "Rassemble tes documents avant de partir pour éviter un aller-retour." },
      };
    },
    async startDay() { await sleep(2600); scen.day = "active"; buildDay(); return { ok: true }; },
    async finishDay() {
      await io(500);
      // Effet backend (doc 43 §5.4) : non faites → backlog ; échéance dépassée → standby.
      const overdue = db.plan.filter((p) => p.status !== "faite" && p.deadline && p.deadline < now());
      db.standby.push(...overdue.map((o) => ({ id: o.id, title: o.title, deadline: o.deadline })));
      scen.day = "not_started"; db.day.state = "not_started";
      return { ok: true, backlog: db.plan.filter((p) => p.status !== "faite").length, standby: overdue.length };
    },
    async getMission(mid) { await io(150); return clone(db.plan.find((p) => p.id === mid) || db.mission); },
    async completeMission(mid, body) {
      await io(700);
      const m = db.plan.find((p) => p.id === mid); if (m) { m.status = "faite"; m.result = body; }
      const nxt = db.plan.find((p) => p.status === "prévue"); if (nxt) { nxt.status = "active"; nxt.plannedStart = Math.min(nxt.plannedStart, now()); }
      return { ok: true, annexesDone: body.completedAnnexIds.length };
    },
    async failMission(mid, body) {
      await io(700);
      const m = db.plan.find((p) => p.id === mid); if (m) { m.status = "ratée"; m.reasonCode = body.reasonCode; m.reason = body.reason; }
      const nxt = db.plan.find((p) => p.status === "prévue"); if (nxt) nxt.status = "active";
      return { ok: true };
    },
    async getNotes(mid) { await io(150); const m = db.plan.find((p) => p.id === mid) || findProjectMission(mid); return { title: m?.title, context: m?.project || "Programme du jour", notes: m?.notes || "", description: m?.description || "" }; },
    async saveNotes(mid, notes) { await io(400); const m = db.plan.find((p) => p.id === mid) || findProjectMission(mid); if (m) m.notes = notes; return { ok: true }; },

    async getReplanState() { await io(80); return { eligibleAt: db.replan.eligibleAt }; },
    async requestReplan({ reason }) {
      await sleep(2400); if (scen.error) throw new Error("Impossible de joindre Imperium");
      if (db.replan.eligibleAt > now()) throw Object.assign(new Error("Délai de replanification en cours"), { code: "COOLDOWN" });
      const rest = db.plan.filter((p) => p.status === "prévue" || p.status === "active");
      const items = rest.map((p, i) => ({ id: p.id, title: p.title, plannedStart: p.plannedStart + (i > 1 ? 30 * MIN : 0), durationMin: p.durationMin, badge: i > 1 ? "Déplacée" : null }));
      const removed = items.find((x) => x.title === "Lecture"); if (removed) { removed.badge = "Retirée"; }
      items.splice(3, 0, { id: id("p"), title: "Pause récupération", plannedStart: (items[2]?.plannedStart || now()) - 20 * MIN, durationMin: 20, badge: "Nouvelle" });
      items.sort((a, b) => a.plannedStart - b.plannedStart);
      db.replan.proposal = { id: id("rp"), reason, items, version: 1 };
      return clone(db.replan.proposal);
    },
    async reviseReplan(pid, message) {
      await sleep(1600);
      const pr = db.replan.proposal; pr.version++;
      const r = pr.items.find((x) => x.badge === "Retirée");
      if (r && /lecture|garde|remet/i.test(message)) { r.badge = "Déplacée"; r.plannedStart += 60 * MIN; return { proposal: clone(pr), reply: "D'accord, je garde la lecture et je la place plus tard dans la soirée. La colonne du plan est à jour." }; }
      return { proposal: clone(pr), reply: "Je garde la proposition telle quelle : elle laisse 20 min de récupération avant la reprise. Dis-moi ce que tu veux déplacer." };
    },
    async acceptReplan(pid) {
      await io(800);
      const pr = db.replan.proposal;
      db.plan = db.plan.filter((p) => p.status === "faite").concat(pr.items.filter((x) => x.badge !== "Retirée").map((x) => ({ ...(db.plan.find((p) => p.id === x.id) || { notes: "" }), ...x, badge: undefined, status: db.plan.find((p) => p.id === x.id)?.status || "prévue" })));
      db.plan.sort((a, b) => a.plannedStart - b.plannedStart);
      db.replan = { eligibleAt: now() + db.settings.debounce * MIN, proposal: null };
      return { ok: true };
    },
    async cancelReplan() { await sleep(200); db.replan.proposal = null; return { ok: true }; },

    async getFinance() {
      await io();
      return { wallets: clone(db.finance.wallets), balance: db.finance.wallets.reduce((s, w) => s + w.value, 0), pressure: db.finance.pressure.score, tx: clone(db.finance.tx) };
    },
    async getCategories() { await io(80); return clone(db.categories); },
    async suggestCategory(label) {
      const k = KNOWN[norm(label)];
      if (k) return { category: k, source: "known" };
      await sleep(700);
      return { category: /drive|leclerc|carrefour|lidl|auchan/i.test(label) ? "Courses" : /total|esso|shell|bp/i.test(label) ? "Carburant" : "Loisirs", source: "ai" };
    },
    async runOcr(photo) {
      await sleep(2600);
      if (photo?.blurry) throw Object.assign(new Error("Échec de la lecture : image trop floue"), { code: "OCR" });
      return { amount: 54.2, date: now(), label: "TOTAL ENERGIES", type: "out" };
    },
    async createTransaction(tx) {
      await io(700);
      const t = { id: id("tx"), ...tx }; db.finance.tx.unshift(t);
      const w = db.finance.wallets.find((x) => x.id === tx.wallet); if (w) w.value += tx.amount;
      return clone(t);
    },

    async getOperations() {
      await io();
      if (scen.empty) return { projects: [], routines: [], today: [], totalMin: 0 };
      const today = db.routines.filter((r) => r.active && (r.freq === "daily" || r.plannedToday));
      return { projects: clone(db.projects), routines: clone(db.routines), today: clone(today), totalMin: today.reduce((s, r) => s + (r.minutes || 0), 0) };
    },
    async saveProjects(projects) { await io(700); db.projects = clone(projects); return { ok: true }; },
    async saveRoutine(r) { await io(500); const i = db.routines.findIndex((x) => x.id === r.id); if (i >= 0) db.routines[i] = clone(r); else db.routines.push({ ...clone(r), id: id("r") }); return { ok: true }; },
    async deleteRoutine(rid) { await io(500); db.routines = db.routines.filter((r) => r.id !== rid); return { ok: true }; },

    async getHistory(period) {
      await io();
      if (scen.empty) return { empty: true };
      const len = { semaine: 7, mois: 30, "3mois": 91, annee: 365, tout: db.days.length }[period];
      const cur = db.days.slice(-len), prev = period === "tout" ? null : db.days.slice(-2 * len, -len);
      const agg = (ds) => Math.round(100 * ds.reduce((s, d) => s + d.wDone, 0) / ds.reduce((s, d) => s + d.wTotal, 0));
      const score = agg(cur);
      const delta = prev && prev.length ? score - agg(prev) : score - Math.round(100 * cur[0].wDone / cur[0].wTotal);
      const balNow = db.finance.wallets.reduce((s, w) => s + w.value, 0);
      return {
        regularity: { score, delta, series: cur.map((d) => ({ t: d.date, v: Math.round(100 * d.wDone / d.wTotal) })) },
        finance: { balance: balNow, delta: Math.round(cur.at(-1).balance - cur[0].balance), series: cur.map((d) => ({ t: d.date, v: d.balance })) },
        finished: clone(db.finished),
        days: db.days.slice(-30).reverse().map((d) => ({ id: d.id, start: d.start, end: d.end, done: d.done, total: d.total })),
        review: clone(db.aiReview),
      };
    },
    async getHistoryDay(did) {
      await io(250);
      const d = db.days.find((x) => x.id === did);
      const names = ["Routine du matin", "Préparer la journée", "Séance de sport", "Travail VTC — matin", "Pause déjeuner", "Démarches administratives", "Travail VTC — après-midi", "Révision de vocabulaire", "Temps en famille", "Lecture", "Rangement", "Bilan de la journée", "Appel banque"];
      const fails = new Set([5, d.total - 3, 2, d.total - 1, 8, 1].filter((i) => i >= 0 && i < d.total).slice(0, d.total - d.done));
      const missions = names.slice(0, d.total).map((title, i) => ({ id: did + "_" + i, title, ok: !fails.has(i), note: "" }));
      const k = missions.findIndex((m) => !m.ok); if (k >= 0) { missions[k].reason = "Imprévu"; missions[k].note = "Le rendez-vous a été annulé."; }
      return { ...d, missions };
    },

    async terminalSend(ctx, text, history) { await sleep(900 + Math.min(1200, text.length * 12)); return reply(ctx, text, history); },
    async startWR() { await sleep(2400); return { ok: true }; },
    async finishWR() { await sleep(2200); db.wr.state = "done_recent"; setTimeout(() => { db.wr.state = "none"; }, 10000); return { ok: true }; },
    async resolveIntervention(decision) { await io(500); db.standby = []; return { ok: true, decision }; },

    async getSettings() { await io(); return clone(db.settings); },
    async saveSettings(patch) { await io(300); Object.assign(db.settings, clone(patch)); return clone(db.settings); },
    async getPriorities() { await io(150); return [...db.priorities]; },
    async savePriorities(order) { await io(500); db.priorities = [...order]; return { ok: true }; },
    async testServer(url) { await sleep(900); return /^https?:\/\/\S+/.test(url) ? { ok: true, latency: 42 } : { ok: false, error: "Adresse invalide" }; },
    async connect({ key }) { await sleep(1200); if (key !== "demo") throw Object.assign(new Error("Clé maître invalide"), { code: "AUTH" }); return { ok: true }; },
    async getPermissions() { await io(120); const p = clone(db.permissions); if (scen.overlayDenied) p.find((x) => x.id === "overlay").state = "no"; return p; },
    async completeTopProject() { await io(500); const p = db.projects.shift(); db.finished.unshift({ id: id("hp"), title: p.title, doneAt: now(), notes: p.description, missions: p.missions.map((m) => [m.title, m.notes]) }); return { done: p.title, promoted: db.projects[1]?.title }; },
    async getModelRoles() { await io(); return clone(db.roles); },
    async getCatalog() { await sleep(900); return clone(db.catalog); },
    async saveModelRole(r) { await io(500); const i = db.roles.findIndex((x) => x.role === r.role); db.roles[i] = clone(r); return { ok: true }; },
    async getThresholds() { await io(); return clone(db.thresholds); },
    async saveThresholds(t) { await io(500); db.thresholds = clone(t); return { ok: true }; },
    async getApiKeys() { await io(); return clone(db.apiKeys); },
    async replaceApiKey(provider) { await io(600); db.apiKeys.find((k) => k.provider === provider).present = true; return { ok: true }; },
    async deleteApiKey(provider) { await io(500); db.apiKeys.find((k) => k.provider === provider).present = false; return { ok: true }; },
    async listLogs() { await io(); return clone(db.logs).sort((a, b) => b.date - a.date); },

    async feedList() { await io(); return scen.empty ? [] : clone(db.feed); },
    async feedImport({ files, context }) {
      await sleep(2800);
      const name = files.length ? (files.length > 1 ? `${files.length} fichiers` : files[0].name) : "Texte transmis";
      const sess = { id: id("fs"), name: context.split(/[.\n]/)[0].slice(0, 40) || name, files: files.map((f) => [f.name, f.type || "Fichier", Math.max(1, Math.round(f.size / 1024)) + " Ko"]), context };
      db.pendingFeed = sess; return clone(sess);
    },
    async feedSave(name) {
      await io(900); const s = db.pendingFeed;
      if (!s) { const f = db.feed.find((x) => x.name === name); if (f) { f.state = "saved"; f.retained = f.retained || "Préférence validée dans la conversation."; f.destination = "Mémoire"; } return { ok: true }; }
      db.feed.unshift({ id: id("f"), name: s.name, date: now(), kind: s.files.length ? `${s.files.length} fichier${s.files.length > 1 ? "s" : ""}` : "Texte", state: "saved", sources: s.files.length ? s.files : [["texte", "Texte", "1 Ko"]], retained: s.context || "(contenu des fichiers)", destination: "Mémoire", conv: s.conv || [] });
      db.pendingFeed = null; return { ok: true };
    },
    async feedCancel() { await sleep(200); db.pendingFeed = null; return { ok: true }; },
    async feedDelete(fid) { await sleep(1500); db.feed = db.feed.filter((f) => f.id !== fid); return { ok: true }; },
    async feedRetry(fid) { await sleep(1800); const f = db.feed.find((x) => x.id === fid); f.state = "to_validate"; f.error = null; f.conv = [["IMPERIUM", "J'ai pu lire le document cette fois. C'est un relevé bancaire d'octobre. Je l'enregistre comme contexte financier ?"]]; return clone(f); },
  };

  // Hors ligne (doc 14) : les actions autorisées sont mises en file avec un statut « en attente »
  // (jamais de faux succès) ; le backend confirme au retour du réseau. Les autres sont refusées.
  const QUEUE = { finishDay: "Fin de journée", completeMission: "Mission faite", failMission: "Mission non faite", createTransaction: "Transaction", saveNotes: "Notes de mission" };
  db.pending = []; const orig = {};
  for (const k of ["finishDay", "startDay", "completeMission", "failMission", "saveNotes", "requestReplan", "acceptReplan", "saveProjects", "saveRoutine", "deleteRoutine", "saveSettings", "savePriorities", "saveModelRole", "saveThresholds", "replaceApiKey", "deleteApiKey", "feedImport", "feedSave", "feedDelete", "feedRetry", "resolveIntervention", "startWR", "completeTopProject", "createTransaction"]) {
    const f = (orig[k] = api[k]);
    api[k] = async (...a) => {
      if (!scen.offline) return f(...a);
      if (!QUEUE[k]) throw Object.assign(new Error("Hors ligne : cette action demande le serveur. Réessaie au retour du réseau."), { code: "OFFLINE" });
      const item = { id: id("q"), type: k, label: QUEUE[k], detail: k === "createTransaction" ? `${a[0].label} ${a[0].amount} €` : "", args: clone(a), createdAt: now(), status: "pending", idempotencyKey: id("idem") };
      db.pending.push(item); return { pending: true, item: clone(item) };
    };
  }
  api.listPending = async () => clone(db.pending.filter((p) => p.status !== "cancelled" && p.status !== "synced"));
  api.cancelPending = async (qid) => { const p = db.pending.find((x) => x.id === qid); if (p && p.status === "pending") p.status = "cancelled"; return { ok: true }; };
  api.flushPending = async () => {
    let sent = 0;
    for (const p of db.pending.filter((x) => x.status === "pending" || x.status === "failed")) {
      p.status = "syncing";
      try { await orig[p.type](...p.args); p.status = "synced"; sent++; } catch (e) { p.status = "failed"; p.error = e.message; }
    }
    return { sent, failed: db.pending.filter((x) => x.status === "failed").length };
  };
  api.pendingFor = (mid) => db.pending.find((p) => p.status === "pending" && (p.type === "completeMission" || p.type === "failMission") && p.args[0] === mid);

  function findProjectMission(mid) { for (const p of db.projects) { const m = p.missions.find((x) => x.id === mid); if (m) return { ...m, project: p.title }; } }

  function reply(ctx, text, history) {
    const t = text.toLowerCase();
    if (ctx.kind === "wr") {
      const n = history.filter((m) => m.who === "VOUS").length;
      if (/valide|oui|ok|termin/.test(t) && n >= 2) return { text: "Parfait. Je finalise ton bilan de la semaine.", action: "finishWR" };
      return { text: ["Qu'est-ce qui t'a le plus freiné cette semaine ?", "Noté. Je retiens aussi 46 missions faites sur 58, dont toutes les urgentes. Le projet Imperium passe à 60 %. Tu valides ce bilan ?", "Tu valides ce bilan ?"][Math.min(n - 1, 2)] || "Continue." };
    }
    if (ctx.kind === "intervention") {
      if (/annul/.test(t)) return { text: "Je passe « Renouveler la carte VTC » en annulée. Tu valides ?", pending: "annuler" };
      if (/fait|déjà/.test(t)) return { text: "Je la marque comme faite. Tu valides ?", pending: "faite" };
      if (/oui|valide/.test(t) && history.some((m) => m.pending)) return { text: "C'est fait. L'intervention est résolue.", action: "resolveIntervention" };
      if (/vendredi|semaine|demain|échéance|reporte/.test(t)) return { text: "Je fixe une nouvelle échéance à vendredi et la mission retourne au backlog. Tu valides ?", pending: "nouvelle échéance" };
      return { text: "Dis-moi : nouvelle échéance, faite ou annulée ?" };
    }
    if (ctx.kind === "replan") return { text: null, revise: true };
    if (ctx.kind === "feed") {
      if (/oui|conserve|enregistre|valide/.test(t)) return { text: "Synthèse prête à enregistrer. Appuie sur Enregistrer pour l'ajouter à la mémoire.", ready: true };
      return { text: "D'accord, j'ai corrigé la synthèse. Je la conserve dans la mémoire ?" };
    }
    if (ctx.kind === "project") return { text: "Je propose de placer les cours avec Ivanov avant la révision du vocabulaire, le vendredi à 14 h. Tu valides cet ordre ?" };
    if (ctx.kind === "projectDelete") return { text: "C'est fait : l'élément et ses sources sont supprimés.", action: "done" };
    if (/document|papier|démarche/.test(t)) return { text: "Dis-moi quelle démarche tu prévois.\nJe t'aiderai à préparer la liste." };
    if (/préfecture|carte|titre/.test(t)) return { text: "Pour la préfecture, prépare :\n- justificatif de domicile de moins de 3 mois\n- 2 photos d'identité\n- ta carte actuelle\nJe l'ajoute aux notes de « Démarches administratives » ?" };
    return { text: "Je regarde ton plan du jour et je te réponds avec une action concrète. (réponse de démonstration)" };
  }

  return api;
}

const KNOWN = { vtc: "Revenus VTC", carburant: "Carburant", courses: "Courses", stationnement: "Stationnement", telephone: "Téléphone", restaurant: "Restaurant", loyer: "Loyer", peage: "Péage", "total energies": "Carburant" };
function norm(s) { return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/\s+\d+$/, "").trim(); }
function P(title, progress, why, missions) {
  return { id: "pr_" + norm(title).replace(/\W+/g, "_"), title, description: "", progress, progressWhy: why,
    missions: missions.map(([t, done, min, desc, notes]) => ({ id: "pm_" + Math.random().toString(36).slice(2, 8), title: t, status: done ? "faite" : "à faire", estimatedMin: min || null, description: desc || "", notes: notes || "" })) };
}
function R(name, freq, minutes, priority, notes = "") { return { id: "r_" + norm(name).replace(/\W+/g, "_"), name, freq, minutes, priority, notes, active: true }; }
