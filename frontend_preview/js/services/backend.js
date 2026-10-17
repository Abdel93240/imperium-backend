// Adaptateur backend réel — NON BRANCHÉ dans cette prévisualisation.
// Même interface que le fournisseur de démonstration. Chaque opération porte la route
// trouvée dans le dépôt (/opt/imperium-backend, main @ 4989f49, préfixe /api) ou
// « manquant » si aucun contrat n'existe. Aucune route n'est inventée.

export const OPERATIONS = {
  getStatus:          { route: "GET /api/health/services", etat: "existe", note: "Codé le 2026-10-17 : API, base, mémoire vectorielle, IA locale, lecture des images et PDF (OCR), IA cloud (grey tant qu'aucun fournisseur cloud n'est branché)." },
  getDay:             { route: "GET /api/imperium/day/current", etat: "existe" },
  startDay:           { route: "POST /api/imperium/day/start", etat: "existe" },
  finishDay:          { route: "POST /api/imperium/day/finish", etat: "existe", note: "Retour backlog / standby codés (2026-10-17)." },
  getDashboard:       { route: "GET /api/imperium/dashboard + GET /api/imperium/missions/active + GET /api/imperium/day/plan/today", etat: "existe", note: "Annexes (mission.annexes), estimated_minutes et deadline_at codés le 2026-10-17 ; bannière Intervention via /missions/standby." },
  completeMission:    { route: "POST /api/imperium/missions/{id}/complete", etat: "existe", note: "completed_annex_mission_ids codé (2026-10-17)." },
  attachAnnexes:      { route: "POST /api/imperium/missions/{id}/annexes", etat: "existe", note: "Annexes V1 (doc 53 §3.1), appelé par le planificateur." },
  failMission:        { route: "POST /api/imperium/missions/{id}/fail", etat: "existe", note: "failure_reason_code + failure_reason (détails) codés (2026-10-17)." },
  getNotes:           { route: "GET /api/imperium/missions/{id}", etat: "existe", note: "description, notes, project_id (2026-10-17)." },
  saveNotes:          { route: "PATCH /api/imperium/missions/{id}", etat: "existe", note: "Mission terminée : lecture seule (409)." },
  getReplanState:     { route: "GET /api/imperium/day/replan/state", etat: "existe", note: "eligible_at fourni par le serveur (2026-10-17)." },
  requestReplan:      { route: "POST /api/imperium/day/replan", etat: "existe", note: "reason_category + reason_detail (+ other_reason) ; 202 ; 409 REPLAN_COOLDOWN + eligible_at." },
  reviseReplan:       { route: "POST /api/imperium/day/replan/{id}/revise", etat: "existe", note: "Correction chatbot, sans nouveau délai." },
  acceptReplan:       { route: "POST /api/imperium/day/replan/{id}/accept", etat: "existe" },
  cancelReplan:       { route: "POST /api/imperium/day/replan/{id}/cancel", etat: "existe" },
  getFinance:         { route: "GET /api/imperium/vault/summary + GET /api/imperium/vault/transactions + GET /api/vault/pressure", etat: "existe" },
  suggestCategory:    { route: "POST /api/imperium/vault/categories/suggest (+ GET /categories, POST /categories/confirm)", etat: "existe", note: "Mémoire utilisateur, table en dur, puis modèle local (2026-10-17)." },
  runOcr:             { route: "POST /api/imperium/vault/receipt-extractions?entry_app=imperium|vault (corps brut, X-Filename, Idempotency-Key) + GET /{id}, GET /{id}/image, POST /{id}/validate, POST /{id}/cancel", etat: "existe", note: "Codé le 2026-10-17 (doc 37 §3). Synchrone : status ready (brouillon) ou failed (error_message à afficher 10 s). Enregistrer par POST /{id}/validate, pas par createTransaction, pour lier le justificatif ; stock_lines = lignes cochées vers le stock Pulse (absent : lignes food du brouillon). OCR né désactivé." },
  createTransaction:  { route: "POST /api/imperium/vault/transactions", etat: "existe", note: "Vérifier champ catégorie et livre dérivé." },
  getOperations:      { route: "GET /api/imperium/projects + GET /api/imperium/routines + GET /api/imperium/routines/today", etat: "existe", note: "Codé le 2026-10-17 (doc 71)." },
  saveProjects:       { route: "POST|PATCH|DELETE /api/imperium/projects…, POST /projects/reorder, /projects/{id}/missions…", etat: "existe", note: "Le brouillon de « Gérer les projets » est envoyé opération par opération." },
  saveRoutine:        { route: "POST /api/imperium/routines, PATCH /api/imperium/routines/{id}", etat: "existe" },
  deleteRoutine:      { route: "DELETE /api/imperium/routines/{id}", etat: "existe" },
  getHistory:         { route: "GET /api/imperium/missions/history + GET /api/imperium/weekly-review/history", etat: "partiel", note: "Série de régularité (doc 43 §6.1) et bilan IA à exposer." },
  getHistoryDay:      { route: "GET /api/imperium/day/latest", etat: "partiel" },
  terminalSend:       { route: "POST /api/imperium/weekly-review/{session_id}/chat/messages", etat: "partiel", note: "Existe pour la WR seulement ; chatbot universel (doc 72) sans route." },
  startWR:            { route: "POST /api/imperium/weekly-review/launch", etat: "existe" },
  finishWR:           { route: "POST /api/imperium/weekly-review/{session_id}/approve", etat: "existe" },
  resolveIntervention:{ route: "GET /api/imperium/missions/standby + POST /api/imperium/missions/{id}/standby/resolve", etat: "existe", note: "Décision validée par l'utilisateur via le chatbot (doc 43 §5.4)." },
  getSettings:        { route: "GET /api/imperium/settings", etat: "existe", note: "Codé le 2026-10-17 (doc 43 §15)." },
  saveSettings:       { route: "PATCH /api/imperium/settings", etat: "existe", note: "Mise à jour partielle." },
  getPriorities:      { route: "GET /api/imperium/decision-framework/priorities", etat: "existe" },
  savePriorities:     { route: "POST /api/imperium/decision-framework/priorities", etat: "existe" },
  testServer:         { route: "GET /api/health", etat: "existe" },
  connect:            { route: "POST /api/auth/login", etat: "existe", note: "Stratégie de session : doc 63." },
  getPermissions:     { route: "Android (plateforme)", etat: "plateforme", note: "Non disponible dans un navigateur." },
  getModelRoles:      { route: "GET /api/ai/advanced/roles (+ GET /catalog)", etat: "existe", note: "Codé le 2026-10-17 (doc 73) ; catalogue distant non branché." },
  saveModelRole:      { route: "PUT /api/ai/advanced/roles/{role}", etat: "existe" },
  getThresholds:      { route: "GET /api/ai/advanced/thresholds", etat: "existe" },
  saveThresholds:     { route: "PUT /api/ai/advanced/thresholds", etat: "existe" },
  getApiKeys:         { route: "GET /api/ai/advanced/api-keys", etat: "existe", note: "Statut seulement." },
  replaceApiKey:      { route: "PUT /api/ai/advanced/api-keys/{provider}", etat: "existe", note: "Écriture seule." },
  deleteApiKey:       { route: "DELETE /api/ai/advanced/api-keys/{provider}", etat: "existe" },
  listLogs:           { route: "GET /api/ai/logs + GET /api/ai/logs/{id}", etat: "existe", note: "Codé le 2026-10-17 (doc 72 §8)." },
  feedList:           { route: "GET /api/ai/knowledge-inbox/items", etat: "existe", note: "Codé le 2026-10-17 (doc 70)." },
  feedImport:         { route: "POST /api/ai/knowledge-inbox/items + POST /items/{id}/sources (corps brut) + POST /items/{id}/analyze", etat: "existe" },
  feedSave:           { route: "PATCH /items/{id}/extraction + POST /api/ai/knowledge-inbox/items/{id}/validate", etat: "existe", note: "Vectorisation par le job ai.knowledge_inbox après validation." },
  feedDelete:         { route: "DELETE /api/ai/knowledge-inbox/items/{id} (et POST /items/{id}/cancel avant validation)", etat: "existe" },
};

export class NotConnected extends Error {
  constructor(op) { const o = OPERATIONS[op] || {}; super(`Non branché : ${op} (${o.route || "contrat manquant"})`); this.op = op; this.info = o; }
}

export function createBackendAdapter() {
  return new Proxy({}, { get: (_, op) => (op === "kind" ? "backend" : async () => { throw new NotConnected(String(op)); }) });
}
