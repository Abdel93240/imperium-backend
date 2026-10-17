// Point unique d'accès aux services. Les écrans ne connaissent que `svc`.
// Mode démo par défaut ; ?mode=backend branche l'adaptateur réel (non raccordé ici :
// chaque appel échoue proprement avec la route attendue).
import { createDemoProvider } from "./demo.js";
import { createBackendAdapter } from "./backend.js";

const mode = new URLSearchParams(location.search).get("mode") === "backend" ? "backend" : "demo";
export const svc = mode === "backend" ? createBackendAdapter() : createDemoProvider();
export const isDemo = mode === "demo";
