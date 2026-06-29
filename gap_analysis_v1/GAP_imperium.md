# GAP Analysis V1 - Imperium / Orchestrateur

Date: 2026-06-29  
Scope: lecture docs -> gap V1. Aucun code backend audite a nouveau, aucun code runtime modifie.

## Base de comparaison

Source "deja code" imposee par la tache, sans re-audit:

- `audit_resync/AUDIT_decision_framework.md`: fondation deterministe saine. Priorites utilisateur canoniques, coefficients internes, scoring intrinseque A-E, score pondere, bucket public, explication detaillee. Pas d'IA, n8n ou pgvector dans ce module.
- `audit_resync/AUDIT_daily_plans.md`: deux surfaces actives. `daily_plan.py` = snapshot read-only moderne expose par `GET /api/imperium/daily-plan`. `daily_plans.py` = plan persistant/legacy actif expose par `/api/imperium/day/plan...`, avec divergence documentaire et dependance Path legacy. Le vrai living plan IA/hook n'est pas code.

Important: le present rapport considere uniquement ces audits comme base codee. Il ne rejuge pas les autres modules Imperium existants.

Docs lues:

- `docs_master/43_IMPERIUM_LOGIC_DETAIL.md`
- `docs_master/71_IMPERIUM_OPERATIONS_TAB.md`
- contexte seulement: `docs_master/19_IMPERIUM_API_DOCKER_DEPLOYMENT.md`, `docs_master/65_IMPERIUM_FRONTEND_SCREEN_SPEC_V1.md`, `docs_master/66_IMPERIUM_USER_FLOWS_V1.md`

Terminologie a conserver: Imperium -> projets intrinseques/explicites -> objectifs -> missions/routines.

## Lecture de version

| Capacite Imperium | Version cible d'apres doc | Statut selon base imposee | Passage source |
|---|---:|---|---|
| Imperium comme command center et orchestrateur "what now" | V1 | GAP large | doc 43: decide quoi faire maintenant et orchestre les modules lignes 8-12 |
| Daily plan vivant, reshape par hooks | V1 | GAP | doc 43: plan vivant lignes 16-32 |
| Hooks V1: reprogrammer, chatbot, mission ratee/annulee, projet active/desactive/reordonne, Path/Pulse/Vault/Vector | V1 | GAP | doc 43: liste hooks V1 lignes 40-61 |
| Capture hook -> ai_task -> n8n -> score 0-200 -> plan propose -> validation user -> version trail | V1 | GAP IA/orchestration | doc 43: flow hook lignes 64-88 |
| Debounce 5 min + batching, exceptions ghusl/fasting_break | V1 | GAP | doc 43: limites lignes 91-98 |
| Morning checkin "commencer la journee" + table `imperium_morning_checkins` | V1 | GAP | doc 43: popup, inputs, insert lignes 102-138; table lignes 603-617 |
| First daily plan apres morning checkin | V1 | GAP IA/orchestration | doc 43: `imperium.morning_plan` lignes 121-134 |
| Mission lifecycle simple active/faîte/ratée/annulée/expirée | V1 | GAP partiel | doc 43: statuts lignes 142-155; audit daily_plan detecte seulement mission active dans snapshot |
| Mission `stashed` | V3 | HORS V1 | doc 43: `stashed` V3 ligne 152 |
| Mission attributes source/source_ref/planned/deadline/replan_version | V1 | GAP a confirmer par audit missions futur | doc 43: attributs lignes 166-185 |
| Mission principale + missions annexes overlay | V3 / doc 53 | HORS V1 | doc 43: renvoie a doc 53 lignes 187-202 |
| Objective lifecycle active/termine/dormant, modifier/supprimer avec raison | V1 ? a confirmer | GAP | doc 43: cycle objectif lignes 204-266, pas de tag V explicite |
| Discipline score quotidien pondere + stockage | V1 | GAP | doc 43: formule et stockage lignes 270-297; table lignes 663-674 |
| Decision Framework/priorites/scoring deterministe | V1 | CODE V1 | audit decision_framework: scoring A-E, priorites, bucket public conformes |
| Mission categorization A-I par le local model | V1 ? a confirmer | GAP IA | doc 43: layers et task types lignes 310-315, 463-465 |
| Chatbot routing + stockage ai_results + decision-to-action | V1 ? a confirmer | GAP IA/orchestration | doc 43: chatbot lignes 330-407 |
| Priority hierarchy settings + `brain.consult_priority` | V1 | CODE partiel / GAP usage | audit decision_framework: ordre canonique code; doc 43: arbitration runtime lignes 411-453 non prouvee |
| AI task catalog Imperium | V1 ? a confirmer | GAP | doc 43: task types lignes 457-480 |
| Monthly rolling plan | V2 d'apres doc 43 / a confirmer | HORS V1 ? | doc 43: `imperium.monthly_plan` V2 ligne 462, mais routing mensuel ligne 493 |
| Common memory event consumption | V1 | GAP orchestration | doc 43: Imperium consumer des events lignes 502-552 |
| Daily AI Advice depuis WR valide | V1 | GAP IA/memory | doc 43: advice dans daily-plan call lignes 554-589 |
| Tables `imperium_replan_events`, `imperium_daily_plan_versions`, `imperium_user_decisions` | V1 | GAP | doc 43: tables a ajouter lignes 619-661 |
| AI observability `ai_call_logs`, pricing, vues, alert thresholds | V1 reference | GAP a confirmer par audit IA | doc 43: section logging lignes 805-1467 |
| Dashboard V1 backend read model | V1 | CODE partiel / GAP | audit daily_plan: snapshot moderne; doc 65 endpoints futurs lignes 250-258 |
| Operations: 2 projets actifs + liste non-active | V1 | GAP | doc 71: V1 rule 2 projets lignes 63-87 |
| Operations: CRUD projet manuel + activation/desactivation/reorder + auto-promotion | V1 | GAP | doc 71: actions et promotion lignes 97-115 |
| Operations: routines quotidiennes simples cochees | V1 | GAP | doc 71: routines lignes 119-134 |
| Projet via chatbot avec validation utilisateur | V1 | GAP IA/orchestration | doc 71: creation projet chatbot lignes 138-155 |
| Backend source of truth projets/routines | V1 | GAP | doc 71: authority boundary lignes 159-165 |
| Operations data model projects/routines/routine_daily_checks | V1 indicatif | V1 ? a confirmer | doc 71: donnees indicatives lignes 184-203 |
| Operations: projet incomplet inerte + attention requise | V1 | GAP | doc 71: state attention requise lignes 169-180 |
| Nombre projets actifs configurable >2 | versions suivantes | HORS V1 | doc 71: lignes 70-71, 220-224 |
| Routines horaires/frequences complexes | versions suivantes | HORS V1 | doc 71: lignes 126-127, 220-224 |
| Dossier projet riche F06 | futur/hors V1 | HORS V1 | doc 71: lignes 7-9, 215-224 |
| Calendar hooks | V3 | HORS V1 | doc 43: lignes 55-57, 532-533 |
| Frontend Android ecrans/flows | chantier separe | HORS backend | docs 65/66: documentation only, aucun backend lignes 6-9 et 12-23 |
| Deployment Docker/n8n internal call | V1 infra implicite | contexte, pas gap Imperium logique | doc 19: backend beside n8n lignes 3-8, HMAC/idempotency lignes 262-280 |

## CODÉ V1

Ces elements sont reclames par la doc et couverts par les deux audits imposes:

- **Decision Framework deterministe**: priorites utilisateur canoniques, coefficients invisibles, scoring intrinseque A-E, score pondere interne, bucket public, explanation/breakdown, absence d'appel IA/n8n/pgvector.
- **Priorite hierarchy foundation**: `imperium_user_priorities` est la source canonique; les lectures legacy sont projetees ou bloquees selon l'audit.
- **Mission scoring foundation**: le scoring existe cote missions/backlog et peut produire le contexte de priorite, mais il n'est pas encore branche pour instancier le plan du jour.
- **Daily plan snapshot read-only**: `GET /api/imperium/daily-plan` consolide des snapshots existants et garde la regle "une seule mission active" en retournant une erreur si plusieurs actives sont detectees.
- **Daily plan persistant legacy actif**: `/api/imperium/day/plan...` cree/lit/active/complete/cancel des plans persistants avec idempotency et events historiques, mais il est divergent et ne doit pas etre confondu avec le living plan V1 cible.

Dette importante: le module daily plan est le plus gros point de divergence Imperium. La surface moderne est read-only; la surface persistante est legacy/active; aucune des deux ne fait generation, replanning, score 0-200, validation de proposition ou version trail du living plan.

## GAP V1

### DETERMINISTE pur

#### 1. Contrat canonique du daily plan vivant

Ce qui manque:

- Contrat unique entre snapshot read-only et plan persistant.
- `imperium_daily_plan_versions` avec version courante, historique et source replan.
- Remplacement atomique du plan accepte par l'utilisateur.
- Read model Dashboard qui expose focus, plan courant, autres missions, stats et contexte.
- Deprecation ou clarification de `/api/imperium/day/plan...` si le V1 officiel reste `/api/imperium/daily-plan`.

Tables / contrats affectes:

- `imperium_daily_plans`, `imperium_daily_plan_versions`.
- `GET /api/imperium/daily-plan`, `GET /api/imperium/dashboard`, `/api/imperium/day/plan...`.

MVP:

- Central. Imperium n'est pas le chef tant que le plan vivant n'a pas de contrat stable.

#### 2. Hook capture, debounce, batching, status

Ce qui manque:

- Table/service `imperium_replan_events`.
- Capture du trigger source/payload, status pending/completed/rejected.
- Debounce 5 minutes et batching.
- Exceptions immediates pour ghusl et fasting break.
- Lien vers `ai_task_id` et `resulted_in_plan_version`.

Tables / contrats affectes:

- `imperium_replan_events`.
- Event consumer common memory.
- `POST /api/imperium/replans/request` ou contrat equivalent.

MVP:

- Central pour tous les handoffs cross-module.

#### 3. Morning checkin / start day

Ce qui manque:

- API explicite `commencer la journee`.
- Creation idempotente d'un `imperium_morning_checkins` par date utilisateur.
- Champs energy, sleep, pain/limitation, mood, special context.
- Blocage/controle du dashboard tant que le checkin requis n'est pas fait.
- Creation du premier hook/replan de la journee.

Tables / contrats affectes:

- `imperium_morning_checkins`.
- `imperium_replan_events`.
- Dashboard/daily-plan contract.

MVP:

- V1 oui: c'est l'entree officielle de la journee Imperium.

#### 4. Mission lifecycle operationnel complet

Ce qui manque:

- Endpoints canonique complete/fail/cancel/expire/note.
- Reason obligatoire pour `ratée`/`annulée` lorsque la doc l'exige.
- Expiry detection deterministe.
- Creation des hooks apres mission `ratée` ou `annulée`.
- Trace `replan_version` et source/source_ref dans les read models.
- Garantie globale "une seule mission active" sur toutes les surfaces, pas seulement le snapshot moderne.

Tables / contrats affectes:

- `imperium_missions`.
- `POST /api/imperium/missions/{mission_id}/complete`.
- `POST /api/imperium/missions/{mission_id}/fail`.
- `POST /api/imperium/missions/{mission_id}/cancel` a confirmer.
- `TBD POST /api/imperium/missions/{mission_id}/notes`.

MVP:

- Central. C'est la surface utilisateur principale.

#### 5. Objectifs sous projets

Ce qui manque:

- Modele objectif entre projet et mission.
- Status `active`, `terminé`, `dormant`.
- Transition deduite vers `terminé` quand toutes les missions du bloc sont terminees.
- Passage dormant/active par activation du parent project.
- Modifier/supprimer avec raison obligatoire et signaux captures.
- Bilan objectif derive des missions, pas clic user "success/fail".

Tables / contrats affectes:

- Nouvelles tables objectifs ou extension project/task model.
- Events/signaux objectifs pour WR/memory.

MVP:

- V1 ? a confirmer: doc 43 le decrit comme logique Imperium, mais ne le tag pas explicitement V1.

#### 6. Discipline score Imperium

Ce qui manque:

- Calcul quotidien pondere: urgente 3.0, importante 2.0, secondaire 1.0.
- Stockage `imperium_discipline_scores`.
- Exposition dans Dashboard, History et WR.
- Integration separee avec Path/Pulse composite sans melanger les scores.

Tables / contrats affectes:

- `imperium_discipline_scores`.
- Dashboard, History, Weekly Review.

MVP:

- V1 oui: mesure centrale d'execution.

#### 7. Operations: projets actifs/non-actifs

Ce qui manque:

- Table/contrat projets Imperium source of truth.
- Exactement deux projets actifs V1 quand la pile le permet.
- `active_rank` 1/2, liste non-active distincte.
- Ajouter/supprimer/activer/desactiver/reordonner.
- Auto-promotion a la completion d'un projet actif.
- Gestion explicite du cas "activer un 3e projet".
- Projet incomplet promu = `Attention requise`, inerte, ne genere aucune mission.

Tables / contrats affectes:

- `projects` ou table canonique a definir/reconcilier avec doc 05.
- Endpoint read model `IMP.OPERATIONS.MAIN`.
- Endpoints CRUD projets.

MVP:

- V1 oui. Sans projets, Imperium ne peut pas generer les missions fideles a la vision.

#### 8. Operations: routines simples

Ce qui manque:

- Table routines quotidiennes.
- Check quotidien `done` / `not done`.
- Read model Operations.
- Signal routine vers arbitrage/daily plan.

Tables / contrats affectes:

- `routines`, `routine_daily_checks` ou equivalent canonique.
- Endpoints CRUD routines + check daily.

MVP:

- V1 oui, mais simple: pas horaires/frequences complexes.

#### 9. History / decisions / events read models

Ce qui manque:

- Timeline missions, plans, decisions et events.
- Detail event.
- Search/filter read-only.
- Decision log lie au chatbot.

Tables / contrats affectes:

- `imperium_user_decisions`.
- `ai_results`.
- `imperium_replan_events`.
- `GET /api/imperium/missions/history`.
- `TBD GET /api/imperium/history/events`.

MVP:

- V1 utile pour confiance/debug, mais a prioriser apres plan/missions.

#### 10. Settings Imperium hors scoring deja code

Ce qui manque:

- Morning popup enabled/time.
- Notifications missions/routines/alerts.
- AI mode `STRICT` / `EQUILIBRÉ` / `SOUPLE`.
- Replan behavior `replan_on_mission_failure`, `debounce_minutes`.
- Chat retention.
- Composite weights Imperium/Path/Pulse.
- Permissions/status API/micro/camera/location/health/storage en read model.

Tables / contrats affectes:

- `TBD GET /api/imperium/settings`.
- `TBD PATCH /api/imperium/settings`.
- Settings storage.

MVP:

- V1 partiel: priorites sont codees; le reste peut etre livre progressivement.

#### 11. AI observability foundation

Ce qui manque:

- Table centrale `ai_call_logs`.
- Table pricing ou integration avec bibliotheque modele centralisee.
- Vues cout/latence/erreurs/fallback/validation.
- Alert thresholds monitoring.
- Service unique de logging pour toutes les couches IA.

Tables / contrats affectes:

- `ai_call_logs`, pricing/config modele, vues analytics.
- Tous services IA.

MVP:

- V1 important avant usage reel, surtout parce qu'Imperium est le module le plus intensif en appels IA.
- Attention: la doc 43 contient des slugs modeles litteraux dans les exemples SQL/code. A normaliser via la bibliotheque des modeles, sans reintroduire de noms en dur.

### IA/GPU ou IA/cloud

#### 12. Morning plan generation

Ce qui manque:

- Creation d'un `ai_task` `imperium.morning_plan`.
- Inputs normalises: checkin, yesterday outcomes, calendar items, active medical rules, business pressure, WR insights.
- Execution par le modele route selon politique.
- Output first daily plan.
- Validation utilisateur globale V1.
- Logging `ai_call_logs`.

Dependance:

- IA/cloud ou local selon routage; n8n/ai_tasks requis.

MVP:

- Central, mais peut etre livre apres la fondation deterministe start-day + plan versions.

#### 13. Day replan et rolling replan

Ce qui manque:

- Score 0-200 de changement.
- Routing strict par politique.
- `imperium.day_replan` pour reshuffle same-day.
- `imperium.rolling_replan` pour changement projet multi-semaines.
- Proposition avec rationale.
- Accept/reject/partial accept.

Dependance:

- IA + n8n + ai_tasks.

MVP:

- Day replan V1 oui. Rolling/multi-week a confirmer selon perimetre V1 reel.

#### 14. Chatbot Imperium actionnable

Ce qui manque:

- Routing chatbot par le local model vers specialiste adapte.
- Stockage conversation/resultat dans `ai_results`.
- Flow "constructive critic" pour decisions importantes.
- `imperium_user_decisions` lie a `ai_result`.
- Creation/modification proposee de projet/objectif/mission uniquement apres validation utilisateur.
- Alimentation pgvector via validation WR, pas ecriture canonique directe.

Dependance:

- IA + memory + backend validation.

MVP:

- V1 ? a confirmer: doc 43 et doc 71 le placent au coeur, mais le V1 livrable peut commencer par saisie manuelle projets/routines.

#### 15. Mission categorization, recommendation, daily advice

Ce qui manque:

- `imperium.mission_categorize` A-I.
- `imperium.mission_recommendation`.
- `imperium.daily_ai_advice` genere dans le daily-plan call.
- Lecture WR vectorise valide, selection d'un pattern important/critical, bouton "Voir pourquoi".

Dependance:

- IA local/cloud + pgvector/common memory.

MVP:

- V1 ? a confirmer pour advice/recommendation. Categorization est utile a la qualite du scoring.

### ORCHESTRATION cross-module

#### 16. Event consumer common memory

Ce qui manque:

- Consommation canonique des events append-only listes par doc 43.
- Mapping event -> action Imperium.
- Idempotency par event.
- Read/update context.
- Trigger replan si criteres.
- Tests de non-regression pour handoffs critiques.

Tables / contrats affectes:

- Event store commun.
- `imperium_replan_events`.
- Dashboard/daily-plan read model.

MVP:

- Central. Imperium est le chef; les autres modules ne doivent pas porter la strategie seuls.

#### 17. Arbitrage inter-modules runtime

Ce qui manque:

- Service `brain.consult_priority(event_a, event_b)`.
- Application runtime de l'ordre prioritaire au-dela du scoring statique.
- Exemple Path > Vector: priere imminente doit override opportunite VTC.
- Surface Imperium qui explique le gagnant et affiche les autres en badge/contexte.

Tables / contrats affectes:

- Priority context.
- Vector overlay/read model.
- Imperium dashboard alerts.

MVP:

- V1 oui pour les conflits critiques. Sans ca, Vector/Path/Vault/Pulse risquent de redevenir des apps separees.

#### 18. Financial pressure -> plan

Ce qui manque:

- Imperium lit pressure score, weekly balance, alerts Vault.
- `vault.pressure.spike` declenche replan si l'objectif journalier change.
- Vault weekly profit met a jour le contexte financier.
- Dashboard expose pressure score sans faire la decision financiere a la place de Vault.

Tables / contrats affectes:

- Contrats Vault pressure/weekly profit.
- `imperium_replan_events`.
- Daily plan context.

MVP:

- V1 oui, mais depend des gaps Vault (pressure score, weekly profit).

#### 19. Path constraints -> plan et Vector

Ce qui manque:

- `path.ghusl.required` -> replan immediat.
- `path.ghusl.completed` -> mission done si liee.
- `path.prayer.missed` -> discipline impact.
- `path.fasting.started` -> adjust meal-time missions.
- `path.fasting.broken` -> log + replan si necessaire.
- Path priority > VTC profitability dans arbitrage.

Tables / contrats affectes:

- Path events.
- Imperium missions/source_ref.
- Vector decision overlay.

MVP:

- V1 oui pour ghusl/priere/fasting core; depend des gaps Path.

#### 20. Pulse constraints -> plan

Ce qui manque:

- `pulse.workout.completed` -> log + adjust energy expectations.
- `pulse.workout.skipped` -> log reason + replan si central au plan.
- `pulse.medical_rule.activated` ou pain high severity -> replan / contrainte.
- Morning checkin consomme sleep/energy/pain et active medical rules.

Tables / contrats affectes:

- Pulse events/medical rules.
- Morning checkins.
- Daily plan context.

MVP:

- V1 partiel: workout skipped/rescheduled et pain severe sont dans hooks V1, mais les medical rules sensibles dependent du cadre Pulse.

#### 21. Vector constraints -> plan

Ce qui manque:

- `vector.session.started` -> suivi VTC du jour.
- `vector.session.ended` -> revenue logged + final plan adjustment.
- `vector.event_scan.complete` -> events_calendar updated.
- `vector.smart_fuel.requested` -> replan partial immediat.
- External critical disruption -> system hook.

Tables / contrats affectes:

- Vector session/events contracts.
- Vault income handoff pour revenue.
- Imperium replan events.

MVP:

- V1 oui pour smart fuel/session; depend du chantier Vector separe.

## Handoffs cross-module

| Source | Handoff attendu vers Imperium | Imperium a le contrat doc ? | Repondant implemente selon base imposee ? | Statut |
|---|---|---|---|---|
| Path | `path.ghusl.required` -> replan immediat | Oui doc 43 lignes 512, 545 | Non prouve par audits | Orphelin implementation |
| Path | `path.ghusl.completed` -> mark mission done | Oui doc 43 ligne 513 | Non prouve | Orphelin implementation |
| Path | `path.prayer.missed` -> discipline impact | Oui doc 43 ligne 514 | Non prouve; discipline score gap | Orphelin implementation |
| Path | `path.fasting.started/broken` -> meal missions/log/replan | Oui doc 43 lignes 515-516 | Non prouve | Orphelin implementation |
| Path + Vector | Priere imminente > ride profitable | Oui doc 43 lignes 438-453 | Non prouve; pas de `brain.consult_priority` runtime dans audits | Orphelin critique |
| Vault | `vault.weekly_profit.computed` -> financial context | Oui doc 43 ligne 522 | Non prouve; Vault weekly profit gap | Orphelin dependant Vault |
| Vault | `vault.pressure.spike` -> replan si critical | Oui doc 43 lignes 523, 548 | Non prouve; pressure gap | Orphelin dependant Vault |
| Pulse | workout skipped/cancelled/rescheduled -> replan si central | Oui doc 43 lignes 52, 519, 547 | Non prouve; Pulse detail gap | Orphelin dependant Pulse |
| Pulse | pain high severity / medical rule -> replan | Oui doc 43 lignes 53, 520 | Non prouve; sensible Pulse | Orphelin sensible |
| Vector | smart fuel requested -> partial replan | Oui doc 43 lignes 50, 528, 546 | Non prouve | Orphelin dependant Vector |
| Vector | session ended -> revenue logged + final plan adjustment | Oui doc 43 ligne 526 | Non prouve; implique Vault income | Orphelin cross Vault |
| Vector | critical disruption watcher -> system hook | Oui doc 43 lignes 59-61 | Non prouve | Orphelin dependant Vector |
| WR | `wr.validated` -> WRS + memory update | Oui doc 43 ligne 530 | Non prouve ici; WR audits separes | Orphelin hors base |
| Calendar | event/deadline <=7j -> replan | Oui mais V3 | Non requis V1 | Hors V1 |
| Path -> Vault | donation/sadaqa expense | Pas un contrat Imperium direct dans doc 43 | N/A | A superviser via dashboard/WR, contrat Path/Vault |
| Vault -> Path | weekly profit -> sadaqa base | Imperium lit context financier, mais calcul Path/Vault | N/A | A exposer comme contexte, pas decision Imperium seule |

Conclusion handoffs: Imperium a presque tous les contrats **documentes**, mais la base codee imposee ne prouve pas le consommateur event/replan correspondant. Les modules peuvent donc produire des signaux sans chef effectif cote Imperium. C'est le gap le plus important du domaine.

## HORS V1

- Calendar hooks/event/deadline modification: V3.
- Mission `stashed`: V3.
- Missions annexes/submissions overlay, carrier mission details, refusal analyze: V3/doc 53.
- System Health dashboard / `Mon OS personnel`, lane learning, health snapshots: V3/doc 54.
- Dossier projet riche F06: hors V1.
- Nombre de projets actifs configurable au-dela de 2: versions suivantes.
- Routines avec horaires/frequences complexes: versions suivantes.
- Frontend Android Kotlin/Compose des docs 65/66: chantier separe, documentation only.
- Calendar/future schedule doc 51: hors V1.
- Monthly rolling plan autonome: doc 43 le marque V2, meme s'il est strategiquement important; a confirmer si le user veut le remonter dans le livrable V1 reel.

## V1 ? à confirmer

1. **Objectifs**: doc 43 decrit un lifecycle complet objectif, mais sans tag V1 explicite. Confirmer si le V1 livrable doit inclure table/CRUD objectifs ou seulement projets + missions d'abord.
2. **Mission attributes complets**: source/source_ref/replan_version semblent V1, mais leur conformite code n'est pas etablie par les deux audits imposes.
3. **Operations data model exact**: doc 71 dit donnees "indicatif, V1" et "a reconcilier avec doc 05" lignes 184-203. Confirmer tables canoniques avant codage.
4. **Activation manuelle d'un 3e projet**: doc 71 demande de preciser le comportement exact lignes 109-111.
5. **Nom final de l'onglet Operations**: placeholder; route ID/path definitifs a figer.
6. **Chatbot actionnable en V1 livrable**: doc 43/71 en font une voie principale, mais une V1 deterministe peut commencer par projet/routine manuel.
7. **Daily AI Advice**: doc 43 dit V1 dans daily-plan call, mais depend de WR vectorise valide et du pipeline memory.
8. **Mission recommendation mid-day**: task type documente, version non explicite.
9. **Rolling replan multi-week**: hook project-scope documente, mais proche monthly/WR long-context; confirmer V1 vs phase apres fondation.
10. **Monthly rolling plan**: marque V2 dans doc 43 ligne 462, mais cite dans routing mensuel ligne 493 et rappel utilisateur comme seule decision vraiment autonome. Decision produit necessaire.
11. **AI observability full SQL/views**: doc 43 status V1 reference, mais doit etre normalise avec la bibliotheque modele pour eviter noms en dur.
12. **Frontend endpoints 65**: endpoints futurs listent des contrats backend, mais les docs 65/66 interdisent le branchement runtime. Confirmer lesquels deviennent API V1 backend.
13. **Deployment doc 19**: contrat infra deja tres concret (HMAC/idempotency/internal webhook). A noter dans catalogue, mais pas a melanger avec le gap logique Imperium.

## Contrats backend implicites dans docs 19/65/66

Doc 19 contient des contrats infra V1 utiles:

- Service `imperium-api` sur port interne 8000.
- n8n doit appeler le backend via le service Docker, pas PostgreSQL directement.
- `DATABASE_URL` doit viser `imperium_core`, jamais `n8n_db`.
- Health `GET /api/health` et DB health.
- Internal webhook test avec HMAC signature, timestamp et `Idempotency-Key`.

Doc 65 contient des endpoints backend futurs a aligner:

- `GET /api/imperium/dashboard`
- `GET /api/imperium/missions/active`
- `GET /api/imperium/weekly-review/state`
- `POST /api/imperium/day/finish`
- `FUTURE TBD POST /api/imperium/replans/request`
- `GET /api/imperium/missions/{mission_id}`
- `POST /api/imperium/missions/{mission_id}/complete`
- `POST /api/imperium/missions/{mission_id}/fail`
- `TBD POST /api/imperium/missions/{mission_id}/notes`
- `GET /api/imperium/missions/history`
- `TBD GET /api/imperium/history/events`
- `TBD GET /api/imperium/history/events/{event_id}`
- `TBD GET /api/imperium/settings`
- `TBD PATCH /api/imperium/settings`

Doc 66 ne cree aucun endpoint/schema; il confirme surtout les flows utilisateur et l'interdiction de creer une mission active concurrente.

## Suggestion catalogue

Proposition sans application:

| Doc | Version proposee catalogue | Statut propose | Note |
|---|---|---|---|
| `43_IMPERIUM_LOGIC_DETAIL.md` | V1 reference Imperium core, avec sous-sections V2/V3 explicites | `gap_analyzed` | Ajouter un marqueur: V1 documente trop large; distinguer fondation deterministe, IA V1, V2 monthly, V3 submissions/system health/calendar. Normaliser les exemples modeles via bibliotheque centrale. |
| `71_IMPERIUM_OPERATIONS_TAB.md` | V1 base Operations | `gap_analyzed` | Pret pour backlog deterministe projets/routines, mais data model et nom/path restent a trancher. |
| `19_IMPERIUM_API_DOCKER_DEPLOYMENT.md` | V1 infra/deployment | `context_not_gapped` | Contient contrats backend/n8n implicites; ne pas melanger avec logique Imperium. |
| `65_IMPERIUM_FRONTEND_SCREEN_SPEC_V1.md` | V1 frontend spec | `context_not_gapped` | Contient endpoints backend futurs a reconcilier; frontend chantier separe. |
| `66_IMPERIUM_USER_FLOWS_V1.md` | V1 frontend flows | `context_not_gapped` | Aucun backend/schema; confirme flows et regle une mission active. |

## Priorisation pragmatique

Ordre conseille pour rendre Imperium chef sans attendre tout l'IA:

1. Trancher le contrat daily plan: snapshot vs plan persistant.
2. Ajouter fondation hooks/replan_events + plan_versions + start-day/morning_checkins.
3. Stabiliser mission lifecycle + one-active guard partout.
4. Coder Operations deterministe projets/routines.
5. Coder event consumer cross-module minimal pour ghusl, pressure spike, workout skipped, smart fuel.
6. Brancher IA replan/morning_plan seulement apres contrats deterministes et logging.

