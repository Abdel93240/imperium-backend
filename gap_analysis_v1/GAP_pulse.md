# GAP Analysis V1 - Pulse / Sante

Date: 2026-06-28  
Scope: lecture docs -> gap V1. Aucun code backend audite a nouveau, aucun code applicatif modifie.

## Base de comparaison

Source "deja code" imposee par la tache, sans re-audit:

- `imperium_pulse_entries`: table minimale avec `entry_date`, sommeil, energie, fatigue, poids, `workout_done`, `workout_type`, notes.
- Invariants deja valides: ranges, un entry par user/date, `workout_type` interdit si `workout_done=false`.
- CRUD + `today` + stats.
- Privacy securisee par absence: aucun appel cloud, aucun upload, aucun document medical.

Important: ce rapport cherche les capacites Pulse V1 reclamees par les docs 40/34 mais absentes du perimetre ci-dessus. Il ne rejuge pas la conformite fine du code existant.

Docs lues:

- `docs_master/40_PULSE_LOGIC_DETAIL.md`
- `docs_master/34_PULSE_MEDICAL_FEED_AI.md`
- `docs_master/F08_DOSSIER_MEDICAL.md`
- contexte deja code: `audit_resync/AUDIT_pulse_calendar_fondation.md`

## Lecture de version

| Feature / capacite Pulse | Version cible d'apres doc | Statut code selon base imposee | Categorie si GAP | Passage source |
|---|---:|---|---|---|
| Entry quotidienne minimale: sommeil, energie, fatigue, poids, workout flag, notes | MVP minimal deja code | Code | N/A | base imposee par la tache; audit Pulse lignes 7-13 |
| Privacy par absence de medical/cloud/upload | MVP minimal deja code | Code | N/A | base imposee par la tache; audit Pulse lignes 13-15 |
| Pulse ne diagnostique pas, ne prescrit pas, ne decide pas seul | V1 | Code par absence / regle produit | Medical sensible | doc 40 lignes 12-14 et 39-46; doc 34 lignes 10-19 |
| Dashboard Pulse today: repas, macros, hydratation, workout/recovery, health_score explique, stock, fasting, regles medicales, pain banner | V1 | GAP | Mixte: deterministe + medical sensible + IA | doc 40 lignes 187-201; endpoint lignes 873-880 |
| Events Pulse + idempotency sur mutations | V1 | GAP | Deterministe pur, sauf events medical/pain IA | doc 40 lignes 148-165 |
| Offline/conflict rules par type de mutation | V1 | GAP | Deterministe pur, sauf medical rule | doc 40 lignes 169-183 |
| Meal estimate depuis texte/chatbot/voix/photo OCR | V1 | GAP | IA/GPU | doc 40 lignes 209-226; task types lignes 741-743 |
| Meal confirmation editable + macros stockees | V1 | GAP | Deterministe pur apres draft | doc 40 lignes 228-239 |
| Stock decrement apres repas, user-confirmed et idempotent | V1 | GAP | Deterministe pur | doc 40 lignes 241-254 |
| Recipe catalogue via chatbot/web/OCR/Nourrir l'IA | V1 ? a confirmer | GAP | IA/GPU | doc 40 lignes 256-271 |
| Raw stock / food stock CRUD manuel avec DLC/DDM/expiry | V1 | GAP | Deterministe pur | doc 40 lignes 274-280 et 353-371 |
| Stock sources Vault receipt, pantry scan OCR, chatbot, meal decrement | V1 | GAP | Mixte: deterministe + IA/GPU | doc 40 lignes 355-363 |
| Expiry alerts daily cron 09:00 | V1 | GAP | Deterministe pur | doc 40 lignes 373-381 |
| Anti-waste meal suggestions from stock/goals/medical rules/fasting | V1 | GAP | IA/GPU | doc 40 lignes 383-400 |
| Hydration logs quick buttons/chatbot | V1 | GAP | Deterministe pur pour log | doc 40 lignes 404-414; endpoint ligne 884 |
| Hydration personalized range by health specialist | V1 ? a confirmer | GAP | IA/GPU + medical sensible | doc 40 lignes 416-427 |
| Hydration quick-add decrements water stock | V1 | GAP | Deterministe pur | doc 40 lignes 430-437 |
| Fasting-aware hydration disable/historical log rules | V1 | GAP | Deterministe pur | doc 40 lignes 439-448; Path constraints lignes 652-661 |
| Workout manual planning | V1 | GAP partiel: only `workout_done/type` exists | Deterministe pur | doc 40 lignes 473-485 |
| Workout program creation by health specialist | V1 ? a confirmer | GAP | IA/GPU + medical sensible | doc 40 lignes 456-471 and 776-778 |
| Workout logging: start/pause/sets/intensity/skip/finish | V1 | GAP partiel: only `workout_done/type` exists | Deterministe pur | doc 40 lignes 488-504 |
| Workout adaptation accept/reject, never auto-applied | V1 | GAP | IA/GPU | doc 40 lignes 506-536 |
| Recovery display from personalized frame | V1 ? a confirmer | GAP | IA/GPU + medical sensible | doc 40 lignes 538-546 |
| Monthly workout revision / phase transitions | V1 ? a confirmer | GAP | IA/GPU + medical sensible | doc 40 lignes 548-560 |
| Owned equipment settings | V1 ? a confirmer | GAP | Deterministe pur | doc 40 lignes 562-570 |
| Park equipment / day-continuity workout placement | V1 ? a confirmer | GAP | IA/GPU / cross-module planning | doc 40 lignes 572-602 |
| Body snapshot numeric fields | V1 | GAP partiel: weight exists, measurements missing | Medical sensible | doc 40 lignes 606-623; table lignes 805-818 |
| Body photo local-only, no backend upload | V1 | Code par absence | Medical sensible | doc 40 lignes 616-623; base imposee: aucun upload |
| Common memory reads/writes for Imperium/Path/Vault/Vector context | V1 ? a confirmer | GAP | Mixte | doc 40 lignes 627-683 |
| Pain log capture body zone/severity/type/limitation/workout impact | V1 | GAP | Medical sensible | doc 40 lignes 687-716; table lignes 830-839 |
| Pain interpretation / escalation by local model -> health specialist/critical mechanism | V1 | GAP | IA/GPU + medical sensible | doc 40 lignes 699-712 and 755-757 |
| Explicit Pulse recommendations endpoint | V1 | GAP | IA/GPU | doc 40 lignes 720-732; endpoint ligne 902 |
| AI task catalog and routing distribution | V1 | GAP | IA/GPU | doc 40 lignes 736-788 |
| Medical document upload with consent gate | V1 | GAP | Medical sensible | doc 34 lignes 123-167 |
| Medical document health specialist extraction via n8n/ai_task | V1 | GAP | IA/GPU + medical sensible | doc 34 lignes 25-57, 61-75, 183-198 |
| Supported medical document types | V1 | GAP | Medical sensible | doc 34 lignes 92-119 |
| Extraction result contract, proposed rules inactive by default | V1 | GAP | IA/GPU + medical sensible | doc 34 lignes 202-240 |
| Medical rules activation/deactivation/revocation | V1 | GAP | Medical sensible | doc 34 lignes 352-381 |
| Daily use of validated medical rules by local model | V1 | GAP | IA/GPU + medical sensible | doc 34 lignes 383-410 |
| Medical retention policy 90 days + deletion/export | V1 | GAP | Medical sensible | doc 34 lignes 414-423 and 593-599 |
| Medical storage/logging: encryption, redaction, no raw doc in vector memory | V1 | GAP | Medical sensible | doc 34 lignes 427-490 |
| Medical tables `pulse_medical_documents`, `pulse_medical_rules` | V1 | GAP | Medical sensible | doc 34 lignes 441-481 |
| Medical UI PUL-14 minimal upload -> review -> validate | V1 | GAP backend contracts; UI hors backend | Medical sensible | doc 34 lignes 494-513 |
| Critical concern notification, conflicting rules, expiration cron, failure modes | V1 | GAP | Medical sensible + IA/GPU for detection | doc 34 lignes 532-571 |
| Raw DICOM/MRI, genetic data, mental health records | Hors V1 explicite | Hors V1 | Medical sensible | doc 34 lignes 116-118 |
| Automatic diagnosis / treatment / dosage / emergency triage / third-party sharing / auto activation | Hors V1 explicite | Hors V1 | Medical sensible | doc 34 lignes 603-613 |
| Wearable connection screen | V2 | Hors V1 | Medical sensible | doc 40 lignes 906-915 |
| Supplement note dedicated screen | V2 | Hors V1 | Medical sensible | doc 40 lignes 906-915 |
| Remote body photo upload | V2 | Hors V1 | Medical sensible | doc 40 lignes 906-915 |
| Automatic body composition analysis | V2 | Hors V1 | IA/GPU + medical sensible | doc 40 lignes 906-915 |
| Advanced nutrition database integration | V2 | Hors V1 | IA/GPU | doc 40 lignes 906-915 |
| Batch cooking planner UI | V2 | Hors V1 | Deterministe/UI | doc 40 lignes 906-915 |
| Dossier medical complet + fiche d'urgence | Plus tard / future spec | Hors V1 | Medical sensible | F08 lignes 3-4, 14-17, 89-95 |
| Native phone medical fiche / QR-NFC activation / emergency access | Plus tard / decisions ouvertes | Hors V1 | Medical sensible | F08 lignes 53-85 and 123-134 |

## CODE V1

Ces elements sont couverts par le perimetre "deja code" impose:

- Entry quotidienne minimale Pulse: date, sommeil, energie, fatigue, poids, workout done/type, notes.
- Contraintes minimales de donnees: ranges, unicite user/date, coherence `workout_done=false` sans `workout_type`.
- CRUD entries, lecture `today`, stats.
- Privacy medicale par absence: aucun document medical, aucun upload de photo/document, aucun appel cloud, aucun stockage brut medical.
- Interdits medicaux respectes par absence pour la surface existante: pas de diagnostic, pas de prescription, pas de regle medicale active automatiquement.

Dette a garder visible: cette surface codee correspond a un MVP minimal, pas a la reference Pulse V1 large des docs 40/34.

## GAP V1

### 1. Dashboard Pulse V1 read model

Ce qui manque:

- `GET /api/pulse/dashboard`.
- Agregation today: meals/macros, hydration target/progress, workout/recovery, stock expiring, fasting banner, active medical rules summary, unresolved pain banner.
- `health_score` avec explanation obligatoire ou banner incomplete-data.

Tables / contrats affectes:

- Read model dashboard.
- Meals, hydration, workouts, food stock, pain, medical rules.

Categorie:

- Mixte.
- Deterministe pur pour l'agregation de signaux deja stockes.
- Medical sensible pour les medical rules/pain.
- IA/GPU pour `health_score` si son calcul depend des facteurs IA/non definis.

Pourquoi V1:

- doc 40 est "Pulse V1 reference" lignes 933-935.
- doc 40 decrit le dashboard today lignes 187-201.
- endpoint matrix: `TBD GET /api/pulse/dashboard` lignes 873-880.

### 2. Event envelope Pulse + idempotency + offline conflict rules

Ce qui manque:

- Events `pulse.meal.logged`, `pulse.food_stock.updated`, `pulse.hydration.logged`, `pulse.workout.completed/skipped`, `pulse.workout.adaptation.accepted`, `pulse.body_snapshot.created`, `pulse.pain.logged`, `pulse.recommendation.requested`, `pulse.medical_rule.activated`.
- `Idempotency-Key` sur toutes les mutations Pulse.
- Conflict handling par type de mutation.

Tables / contrats affectes:

- Event log.
- Tous les endpoints de mutation Pulse.
- Mecanismes de sync offline.

Categorie:

- Deterministe pur pour les events, idempotency et conflits.
- Medical sensible pour `pulse.medical_rule.activated`.
- IA/GPU seulement pour les workflows qui produisent les propositions.

Pourquoi V1:

- doc 40 liste les events V1 lignes 148-165.
- doc 40 impose conflict handling V1 lignes 169-183.

### 3. Meal tracking: draft, confirmation, macros, history

Ce qui manque:

- `POST /api/pulse/meals/estimate`.
- Draft meal avec macros, confidence, source, warnings, `requires_user_validation=true`.
- `POST /api/pulse/meals/{meal_draft_id}/confirm`.
- `GET /api/pulse/meals`.
- Persistence des repas confirmes et totaux macros.

Tables / contrats affectes:

- `meals` ou table canonique equivalente.
- API meals estimate/confirm/list.
- Dashboard macro totals.

Categorie:

- IA/GPU pour l'estimation texte/voix/photo.
- Deterministe pur pour la confirmation, stockage, edition utilisateur, historique et totaux macros.

Pourquoi V1:

- inputs V1 textes/voix/photo lignes 209-226.
- confirmation editable lignes 228-239.
- endpoint matrix lignes 880-883.

### 4. Food stock CRUD + expiry alerts

Ce qui manque:

- `GET/POST/PATCH /api/pulse/food-stock`.
- Stock item fields V1: name, quantity, unit, DLC/DDM/unknown, expiry date, category, confidence, source.
- Stock sources: manual, Vault receipt handoff, pantry scan, chatbot, meal decrement.
- Daily expiry cron 09:00 Europe/Paris.
- Warning/error/info banners for expiring/expired items.

Tables / contrats affectes:

- `food_stock_items` ou table canonique equivalente.
- Food stock endpoints.
- Dashboard stock expiring.
- Vault receipt handoff contract.

Categorie:

- Deterministe pur for manual CRUD, expiry rules, meal decrement, receipt handoff after validation.
- IA/GPU for pantry scan OCR and chatbot natural-language stock parsing.

Pourquoi V1:

- stock fields V1 lignes 365-371.
- stock sources lignes 355-363.
- expiry alerts lignes 373-381.
- endpoints lignes 892-897.

### 5. Stock decrement after meal and hydration water-stock dual effect

Ce qui manque:

- User-confirmed stock decrement lines from meal confirmation.
- Idempotent `stock_decrement_applied`.
- Water stock decrement when hydration quick-add logs intake.
- Negative/insufficient stock warnings and explicit user override.

Tables / contrats affectes:

- Meals confirmations.
- Food stock items / stock mutations.
- Hydration logs.

Categorie:

- Deterministe pur, codable maintenant once meals/stock/hydration tables exist.

Pourquoi V1:

- meal stock decrement rules lignes 241-254.
- hydration button dual-effect lignes 430-437.

### 6. Hydration logging + fasting-aware rules

Ce qui manque:

- `POST /api/pulse/hydration-logs`.
- Amount, timestamp, source, Path constraint context.
- Quick buttons `+250ml`, `+500ml`, `+1L` and chatbot input path.
- Offline sum merge/dedupe.
- Disable quick buttons during fasting window when hydration limits forbid daytime hydration.

Tables / contrats affectes:

- `hydration_logs`.
- Path fasting read context.
- Dashboard hydration progress.

Categorie:

- Deterministe pur for logging, merge, fasting window enforcement, dashboard progress.
- IA/GPU / medical sensible only for personalized hydration target if included in same feature.

Pourquoi V1:

- hydration logging lines 404-414.
- fasting/historical log rules lignes 439-448.
- table definition lignes 820-828.

### 7. Workouts: manual plan and detailed log

Ce qui manque:

- `GET/POST /api/pulse/workouts`.
- Planned workout fields: title, schedule, duration, intensity, exercises, equipment, optional mission source.
- Completion/logging: start, pause/resume, sets/reps, perceived intensity, skip exercise reason, finish.
- Statuses `planned|in_progress|completed|skipped`.
- Rich workout history beyond the current `workout_done/type`.

Tables / contrats affectes:

- `workouts` table or canonical equivalent.
- Workout endpoints.
- Event `pulse.workout.completed` / `pulse.workout.skipped`.
- Imperium planning read model.

Categorie:

- Deterministe pur for manual planning/logging/status.

Pourquoi V1:

- manual planned workouts remain possible lignes 473-485.
- log workout lines 488-504.
- endpoint matrix lignes 885-887.

### 8. Body snapshots numeric

Ce qui manque:

- `POST /api/pulse/body-snapshots`.
- Measurements beyond current weight: waist/chest/arm, optional notes, optional local photo reference.
- History/trends for progress visibility.
- Guardrail: no backend body photo binary, no remote URI, no OCR service analysis request.

Tables / contrats affectes:

- `body_snapshots`.
- Body endpoint.
- Dashboard/history progress.

Categorie:

- Medical sensible because body composition/measurements are health data.
- Deterministic CRUD is codable only after privacy constraints are explicit.

Pourquoi V1:

- body snapshot contract lignes 606-623.
- table definition lignes 805-818.
- body photo upload disabled in V1 lignes 616-623.

### 9. Pain logs

Ce qui manque:

- `POST /api/pulse/pain-logs`.
- Capture zone/body area, severity 0-10, type if known, limitation notes, workout impact.
- Persistence and unresolved/resolved state.
- Dashboard unresolved pain banner when model interpretation marks it relevant.

Tables / contrats affectes:

- `pulse_pain_logs`.
- Pain endpoint.
- Dashboard banner.
- Workout adaptation input context.

Categorie:

- Medical sensible. It is health data and should not be treated as a trivial CRUD until privacy/consent/access rules are settled.
- IA/GPU for interpretation/escalation, separate from capture.

Pourquoi V1:

- pain capture lines 687-696.
- pain is input for local model lines 699-716.
- table definition lignes 830-839.

### 10. Medical documents + consent + validated medical rules

Ce qui manque:

- PUL-14 backend flow: consent gate, upload PDF/image, raw encrypted storage, ai_task creation, n8n webhook, status tracking.
- `pulse_medical_documents` and `pulse_medical_rules`.
- Strict extraction result contract.
- User reviews and validates each rule individually before activation.
- Rule deactivation/revocation when source document is deleted.
- Retention: raw document and extracted text 90 days default, user deletion/export.
- Logging/security: no raw document in logs/vector memory, redaction, auth required.

Tables / contrats affectes:

- `pulse_medical_documents`.
- `pulse_medical_rules`.
- `ai_tasks`, `ai_results`.
- `POST/GET /api/pulse/medical-documents`.
- `GET /api/pulse/medical-rules/active`.
- `POST /api/pulse/medical-rules/{rule_id}/activate`.

Categorie:

- Medical sensible. Requires privacy/RGPD/consent/encryption/retention framework before coding.
- IA/GPU for the health specialist extraction and rule drafting.

Pourquoi V1:

- doc 34 declares V1 safety policy lignes 5-19.
- flow diagram lines 25-57.
- consent gate lines 123-143.
- upload flow lines 147-167.
- tables lines 441-481.
- V1 minimal UI/upload/review/validate lines 494-513.

### 11. Medical feed AI / health specialist routing

Ce qui manque:

- `pulse.medical_document_extract` AI task.
- Health specialist static override.
- n8n task claim/callback path.
- Prompt and strict JSON result handling.
- Critical concern handling, conflict resolution, rule expiration cron, failure modes.

Tables / contrats affectes:

- `ai_tasks`, `ai_results`.
- Medical document status transitions.
- Medical rule lifecycle.
- Notifications/events.

Categorie:

- IA/GPU + medical sensible. Not codable safely until the model/runtime and medical privacy guardrails are available.

Pourquoi V1:

- model routing lines 61-75.
- n8n analysis lines 183-198.
- extraction contract lines 202-240.
- failure/edge cases lines 532-571.

### 12. Validated medical rules applied to daily suggestions

Ce qui manque:

- Active medical rules read model.
- Rule application in meal suggestions, workout adjustments, hydration reminders, recovery recommendations.
- Guarantee that active rules come only from user validation.

Tables / contrats affectes:

- `pulse_medical_rules`.
- Recommendations endpoint.
- Meal/workout/hydration suggestion flows.

Categorie:

- Medical sensible + IA/GPU.

Pourquoi V1:

- doc 34 lines 46-56: validated rules feed local model daily.
- daily use lines 383-410.
- doc 40 non-negotiable rules lines 31-37.

### 13. Recommendations endpoint and local-model suggestion flows

Ce qui manque:

- `POST /api/pulse/recommendations`.
- Meal suggestions, workout suggestions, stock usage suggestions, dashboard suggestion CTA.
- Response explanation and confidence.
- Backend validation before any Imperium priority impact.

Tables / contrats affectes:

- `pulse_recommendations` or canonical equivalent.
- AI task/result contracts.
- Dashboard CTA.

Categorie:

- IA/GPU.
- Medical sensible if active medical rules/pain data are included.

Pourquoi V1:

- recommendation request contract lines 720-732.
- AI task catalog/routing lines 736-788.

## V1 ? a confirmer

Ces capacites apparaissent dans une doc Pulse V1, mais leur version exacte est ambigue parce qu'elles dependent d'un modele local/specialiste, de WR, d'un autre module, d'un ecran Android, ou d'un cadre medical non encore implemente. Ne pas trancher sans validation utilisateur.

| Item | Pourquoi confirmer | Ce qu'il faudrait si valide V1 | Categorie |
|---|---|---|---|
| Recipe catalogue via chatbot/web/OCR/Nourrir l'IA | Dans doc 40 V1 reference, mais ce n'est pas dans l'endpoint matrix principal hors task `pulse.recipe_web_lookup`; implique web/local model. | Table recipe catalogue, validation user, source, history. | IA/GPU |
| Weekly diet programming | Decrit dans doc 40, aligne WR et health specialist; peut etre trop large pour V1 backend minimal. | ai_task `pulse.diet_weekly_program`, recipes of week, shopping list, Imperium cook mission. | IA/GPU + medical sensible |
| Shopping list generated from diet program | Depend de weekly diet program; doc 40 precise no prior validation et self-empty via stock. | Tables shopping list/items, stock reconciliation, WR learning. | Deterministe after AI generation |
| Batch cooking mission + smart storage | Decrit dans doc 40 but cross-module Imperium/Vector; likely beyond minimal Pulse backend. | Mission creation handoff to Imperium, batch cooking plan data. | IA/GPU / cross-module |
| Personalized hydration target | Decrit as health specialist range, not a fixed deterministic target. | Store health program frame/ranges and active medical overrides. | IA/GPU + medical sensible |
| Workout program creation Mode 1 | Decrit as health specialist conversational creation, user validated. | ai_task `pulse.workout_create`, program storage, equipment input. | IA/GPU + medical sensible |
| Recovery personalized forecast frame | Created/revised by health specialist; local model applies daily. | Recovery frame contract, warning rules, history. | IA/GPU + medical sensible |
| Monthly workout revision / phase transition | Doc says automatic every ~4 weeks; monthly may be too advanced before core CRUD. | ai_task `pulse.workout_revision_monthly`, user validation, phase state. | IA/GPU + medical sensible |
| Owned equipment settings | Needed for workout creation/revision, but no endpoint listed separately. | Equipment CRUD/settings endpoint and use in program generation. | Deterministe pur |
| Park equipment and day-continuity routing | Cross-module planning/geolocation; doc references Imperium/day continuity. | Geo/equipment catalogue, route continuity planner handoff. | IA/GPU / cross-module |
| Common memory reads/writes | Principle is V1 architecture, but exact contracts are outside Pulse docs and likely doc 44. | Shared read models/events for Imperium, Path, Vault, Vector. | Mixte |
| Health score | Dashboard requires it with explanation, but formula/model ownership is not specified in doc 40. | Define deterministic formula or AI task, confidence/explanation contract. | V1 ?; likely IA/GPU unless formula defined |
| Medical document flow in V1 | doc 34 calls it V1 reference, but it is sensitive RGPD + AI specialist. | Implement only after privacy/RGPD/consent/encryption/retention foundation is approved. | Medical sensible + IA/GPU |
| F08 dossier medical relation to doc 40 | doc 40 medical documents point to doc 34, not F08. F08 is complete medical dossier/emergency fiche, explicitly later. | Keep separate from PUL-14 medical document rules feed. | Medical sensible |

## HORS V1

- Wearable connection screen: V2 explicite.
- Supplement note dedicated screen: V2 explicite.
- Remote body photo upload: V2 explicite.
- Automatic body composition analysis: V2 explicite.
- Advanced nutrition database integration: V2 explicite.
- Batch cooking planner UI: V2 explicite.
- Raw imaging files / DICOM / MRI scans: not supported V1 explicite.
- Genetic test data: not supported V1 explicite.
- Mental health records: not supported V1 explicite.
- Automatic diagnosis, automatic treatment recommendation, medication dosage advice: out of scope V1 explicite.
- Emergency triage: out of scope V1 explicite.
- Sharing medical documents with third parties: out of scope V1 explicite.
- Automatic activation of AI-derived medical rules: out of scope V1 explicite.
- HDS-grade hosting claim unless infra is formally certified: out of scope V1 explicite.
- F08 dossier medical complet and fiche d'urgence: "SPEC / A implementer plus tard", future feature, not Pulse V1 core.
- Native phone medical fiche / QR-NFC / bracelet/carte emergency activation: decisions ouvertes, future implementation.

## GAP V1 priorise

Ordre conseille pour isoler ce qui est codable maintenant sans toucher au medical sensible ni a l'IA:

1. Deterministe pur: hydration logs + fasting window rules + idempotency.
2. Deterministe pur: food stock CRUD + expiry alerts.
3. Deterministe pur: meal confirmation/manual macros + macro totals, sans AI estimate au depart.
4. Deterministe pur: stock decrement after meal + water-stock decrement.
5. Deterministe pur: manual workouts plan/log/status, richer than `workout_done/type`.
6. Medical sensible, only after privacy frame: body snapshots numeric and pain log capture.
7. IA/GPU later: meal estimate, pantry/meal photo OCR, recommendations, workout adaptation.
8. Medical sensible + IA/GPU last: medical document upload/extraction/rules feed.

## Note specifique F08

Le "medical document analysis" de doc 40 renvoie explicitement a doc 34: "For medical document analysis (a separate flow), see doc 34" lignes 16-16. Doc 40 references doc 34 again for medical rule activation and active medical rules lines 62-63 and 197-198.

F08 ne semble pas etre la cible de ce renvoi. F08 couvre un autre sujet: le dossier medical complet et la fiche d'urgence. Son statut est explicite: "SPEC / A implementer plus tard" lignes 3-4. Il doit donc rester hors V1 tant que l'utilisateur ne le remonte pas dans la roadmap.

## Suggestion d'enrichissement `docs_master/_CATALOG.yaml`

Ne pas appliquer automatiquement dans cette campagne; proposition pour sortir les docs Pulse de l'ambiguite.

```yaml
- file: "40_PULSE_LOGIC_DETAIL.md"
  number: 40
  title: "Pulse Logic Detail"
  family: architecture
  categories: [app:pulse]
  status: needs_alignment
  version: v1
  source_of_truth_for: ["pulse product logic", "pulse v1 capability map", "pulse backend contracts"]
  depends_on: [1, 30, 31, 34, 37, 41, 42, 43, 44, 59]
  notes: "V1 reference but much wider than the current MVP table `imperium_pulse_entries`. Split deterministic V1 CRUD from medical-sensitive and IA/GPU items before implementation."

- file: "34_PULSE_MEDICAL_FEED_AI.md"
  number: 34
  title: "Pulse Medical Feed AI"
  family: architecture
  categories: [ai, app:pulse]
  status: needs_alignment
  version: v1
  source_of_truth_for: ["pulse medical document extraction", "medical rule validation lifecycle", "pulse medical privacy guardrails"]
  depends_on: [30, 31, 9, 10, 40, 59]
  notes: "Medical V1 reference, but implementation must wait for explicit RGPD/consent/encryption/retention guardrails and health-specialist routing. Keep separate from F08 emergency dossier."

- file: "F08_DOSSIER_MEDICAL.md"
  number: 8
  title: "Dossier Medical"
  family: feature
  categories: [feature, app:pulse, security]
  status: to_review
  version: future
  source_of_truth_for: ["future complete medical dossier", "future emergency medical fiche"]
  notes: "Explicitly 'SPEC / A implementer plus tard'. Not the doc 40 medical document flow; doc 40 points to doc 34 for V1 medical document analysis."
```
