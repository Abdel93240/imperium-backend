// Adaptateur backend réel — NON BRANCHÉ dans cette prévisualisation.
// Même interface que le fournisseur de démonstration. Chaque opération porte la route
// trouvée dans le dépôt (/opt/imperium-backend, main @ 4989f49, préfixe /api) ou
// « manquant » si aucun contrat n'existe. Aucune route n'est inventée.

export const OPERATIONS = {
  getStatus:          { route: "GET /api/health + GET /api/health/db", etat: "existe", note: "Mémoire vectorielle, IA locale, IA cloud : aucun endpoint → « Non vérifié » en réel." },
  getDay:             { route: "GET /api/imperium/day/current", etat: "existe" },
  startDay:           { route: "POST /api/imperium/day/start", etat: "existe" },
  finishDay:          { route: "POST /api/imperium/day/finish", etat: "existe", note: "Retour backlog / standby codés (2026-10-17)." },
  getDashboard:       { route: "GET /api/imperium/dashboard + GET /api/imperium/missions/active + GET /api/imperium/day/plan/today", etat: "existe", note: "Annexes (mission.annexes), estimated_minutes et deadline_at codés le 2026-10-17 ; bannière Intervention via /missions/standby." },
  completeMission:    { route: "POST /api/imperium/missions/{id}/complete", etat: "existe", note: "completed_annex_mission_ids codé (2026-10-17)." },
  attachAnnexes:      { route: "POST /api/imperium/missions/{id}/annexes", etat: "existe", note: "Annexes V1 (doc 53 §3.1), appelé par le planificateur." },
  failMission:        { route: "POST /api/imperium/missions/{id}/fail", etat: "existe", note: "failure_reason_code + failure_reason (détails) codés (2026-10-17)." },
  getNotes:           { route: null, etat: "manquant", note: "Notes de mission : FUTUR / NON CODÉ (doc 05)." },
  saveNotes:          { route: null, etat: "manquant" },
  getReplanState:     { route: "GET /api/imperium/day/replan/state", etat: "existe", note: "eligible_at fourni par le serveur (2026-10-17)." },
  requestReplan:      { route: "POST /api/imperium/day/replan", etat: "existe", note: "reason_category + reason_detail (+ other_reason) ; 202 ; 409 REPLAN_COOLDOWN + eligible_at." },
  reviseReplan:       { route: "POST /api/imperium/day/replan/{id}/revise", etat: "existe", note: "Correction chatbot, sans nouveau délai." },
  acceptReplan:       { route: "POST /api/imperium/day/replan/{id}/accept", etat: "existe" },
  cancelReplan:       { route: "POST /api/imperium/day/replan/{id}/cancel", etat: "existe" },
  getFinance:         { route: "GET /api/imperium/vault/summary + GET /api/imperium/vault/transactions + GET /api/vault/pressure", etat: "existe" },
  suggestCategory:    { route: null, etat: "manquant", note: "Table libellé → catégorie (doc 42 §7.0) à exposer." },
  runOcr:             { route: null, etat: "manquant", note: "ocr_service (doc 30)." },
  createTransaction:  { route: "POST /api/imperium/vault/transactions", etat: "existe", note: "Vérifier champ catégorie et livre dérivé." },
  getOperations:      { route: null, etat: "manquant", note: "Projets et routines : tables canoniques non codées (doc 05)." },
  saveProjects:       { route: null, etat: "manquant" },
  saveRoutine:        { route: null, etat: "manquant" },
  deleteRoutine:      { route: null, etat: "manquant" },
  getHistory:         { route: "GET /api/imperium/missions/history + GET /api/imperium/weekly-review/history", etat: "partiel", note: "Série de régularité (doc 43 §6.1) et bilan IA à exposer." },
  getHistoryDay:      { route: "GET /api/imperium/day/latest", etat: "partiel" },
  terminalSend:       { route: "POST /api/imperium/weekly-review/{session_id}/chat/messages", etat: "partiel", note: "Existe pour la WR seulement ; chatbot universel (doc 72) sans route." },
  startWR:            { route: "POST /api/imperium/weekly-review/launch", etat: "existe" },
  finishWR:           { route: "POST /api/imperium/weekly-review/{session_id}/approve", etat: "existe" },
  resolveIntervention:{ route: "GET /api/imperium/missions/standby + POST /api/imperium/missions/{id}/standby/resolve", etat: "existe", note: "Décision validée par l'utilisateur via le chatbot (doc 43 §5.4)." },
  getSettings:        { route: null, etat: "manquant", note: "Réglages doc 65 §8.5 sans endpoint." },
  saveSettings:       { route: null, etat: "manquant" },
  getPriorities:      { route: "GET /api/imperium/decision-framework/priorities", etat: "existe" },
  savePriorities:     { route: "POST /api/imperium/decision-framework/priorities", etat: "existe" },
  testServer:         { route: "GET /api/health", etat: "existe" },
  connect:            { route: "POST /api/auth/login", etat: "existe", note: "Stratégie de session : doc 63." },
  getPermissions:     { route: "Android (plateforme)", etat: "plateforme", note: "Non disponible dans un navigateur." },
  getModelRoles:      { route: null, etat: "manquant", note: "Doc 73." },
  saveModelRole:      { route: null, etat: "manquant" },
  getThresholds:      { route: null, etat: "manquant" },
  saveThresholds:     { route: null, etat: "manquant" },
  getApiKeys:         { route: null, etat: "manquant" },
  replaceApiKey:      { route: null, etat: "manquant" },
  deleteApiKey:       { route: null, etat: "manquant" },
  listLogs:           { route: null, etat: "manquant", note: "Navigateur de logs sandboxé (doc 72 §8)." },
  feedList:           { route: "GET /api/ai/memories", etat: "partiel", note: "Mémoires IA existent ; parcours Nourrir l'IA (doc 70 §11) TBD." },
  feedImport:         { route: null, etat: "manquant" },
  feedSave:           { route: null, etat: "manquant" },
  feedDelete:         { route: "POST /api/ai/memories/{id}/archive", etat: "à confirmer" },
};

export class NotConnected extends Error {
  constructor(op) { const o = OPERATIONS[op] || {}; super(`Non branché : ${op} (${o.route || "contrat manquant"})`); this.op = op; this.info = o; }
}

export function createBackendAdapter() {
  return new Proxy({}, { get: (_, op) => (op === "kind" ? "backend" : async () => { throw new NotConnected(String(op)); }) });
}
