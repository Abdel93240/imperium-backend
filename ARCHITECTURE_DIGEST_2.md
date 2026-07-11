# ARCHITECTURE_DIGEST_2

## 0. Mode de lecture
1. Objet: digest de compression architecture pour arbitrage frontier a contexte limite [demande audit; fichier cree le 2026-07-11].
2. Regle appliquee: chaque ligne porte une source locale, une commande d'audit, ou la marque HYPOTHESE [demande audit §0].
3. Perimetre lu: `/opt/imperium-backend`, `/opt/orchestrator`, `/opt/apps` [cmd `pwd`; cmd `find /opt/orchestrator`; cmd `find /opt/apps`].
4. Perimetre non modifie: aucun code/test/migration modifie; seul ce document est livre [git status avant: modifications preexistantes hors digest].
5. Tests backend lances: `./.venv/bin/pytest` depuis `backend` [cmd pytest backend].
6. Resultat backend: 943 collectes, 907 passed, 35 failed, 9 skipped, duree 30.47s [cmd pytest backend].
7. Tests orchestrateur lances: `./venv/bin/python -m pytest` depuis `/opt/orchestrator` [cmd pytest orchestrator].
8. Resultat orchestrateur: 227 passed, duree 2.30s [cmd pytest orchestrator].
9. Alembic current lance: `./.venv/bin/alembic current` depuis `backend` [cmd alembic current].
10. Resultat Alembic: echec auth Postgres `postgres@127.0.0.1:5432`, donc etat DB runtime non verifie [cmd alembic current].
11. SELECT runtime: non execute car acces DB refuse avant connexion [cmd alembic current].
12. `job_definitions`: absent du code et des migrations inspectes [cmd rg `job_definitions`].
13. `v_plan_current`: absent du code et des migrations inspectes [cmd rg `v_plan_current`].
14. `v_ai_training_pairs`: absent du code et des migrations inspectes [cmd rg `v_ai_training_pairs`].
15. `LISTEN/NOTIFY/pg_notify`: absent du code et des migrations inspectes [cmd rg `LISTEN|NOTIFY|pg_notify`].
16. MAPPING de passes: aucun `MAPPING.md` par Socle/Vault/Pulse/WR/Daily/Vector trouve; seul `docs_master/69_FRONTEND_API_MAPPING_V1.md` existe [cmd find `*MAPPING*.md`].
17. Consequence: les MAPPING demandes ne peuvent pas etre source primaire; ce digest utilise docs canoniques, code, migrations, tests, commandes [cmd find MAPPING].
18. `/opt/apps`: aucun fichier visible sous `find /opt/apps -maxdepth 5 -type f` [cmd find /opt/apps].
19. Consequence `/opt/apps`: les facades Android sont auditees comme non presentes dans le filesystem inspecte [cmd find /opt/apps].
20. Documents `docs_master`: 87 fichiers markdown/yaml/sql listes sous `docs_master` et sous-dossiers [cmd find docs_master].
21. Docs canoniques attendues par AGENTS lues/sondees: 00,01,02,03,04,05,06,07,08,30,31,32,45 [AGENTS.md; cmd rg headings].
22. Docs de domaines lues/sondees: 33 Vector, 34 Pulse Medical, 39 WRS, 40 Pulse, 41 Path, 42 Vault, 43 Imperium, 44 Brain, 57 Vector ML, 75 Memoire [cmd rg headings].
23. Doc 78 toolbox demande: aucun `docs_master/78_*.md` trouve [cmd rg --files docs_master].
24. Troncature: les 87 docs ne sont pas paraphrasees; seules les assertions utiles avec refs sont gardees [demande audit §0].

## 1. Etat des passes
25. Table: `Passe | Merge constatee | tests | flags | jobs | mapping | verdict` [demande audit §1].
26. Socle | merge partiel: auth/events/AI tables/migrations existent | backend suite rouge 907/943 | Qwen off/dry-run; n8n dry-run | `job_definitions` absent | MAPPING absent | partiel [migrations 0001-0012; config.py:1270-1300; cmd pytest].
27. Vault | merge partiel: legacy `/api/vault` + Imperium vault ledger existent | tests Vault visibles passent dans log, mais suite globale rouge | wallet field existe | jobs absent | MAPPING absent | partiel [routes list; models/vault.py:1172-1246; pytest log].
28. Pulse | merge partiel: entries/today/stats existent | tests Pulse visibles passent dans log, mais suite globale rouge | no AI flag propre Pulse | jobs absent | MAPPING absent | partiel [routes list; models/imperium.py:304-354; pytest log].
29. WR | merge avance: sessions/messages/final reports/memory candidates/routes existent | tests WR visibles passent, suite globale rouge | n8n dry-run true; Qwen dry-run true | jobs absent | MAPPING absent | le plus complet [routes list; docs 31 lines 1704-2198; config.py:1288-1300].
30. Daily | merge partiel: read-model `/api/imperium/daily-plan` + old day plan CRUD existent | test daily docs fail sur `meta.daily_plan_version` dans doc 05 | no runner flag | jobs absent | MAPPING absent | partiel avec doc drift [routes list; pytest failure daily].
31. Vector | backend dedie minimal: `services/vector/scoring.py` existe mais aucun `/api/vector` route monte | aucun test Vector runtime dans log visible | no real-time runner flag | jobs absent | MAPPING absent | spec majoritairement non codee [routes list; services/vector/scoring.py; docs 33; docs 57].
32. Path | entamee: habits/check-ins/today/stats/routes existent | tests Path visibles passent, suite globale rouge | no AI flag propre Path | jobs absent | MAPPING absent | partiel [routes list; docs 41; pytest log].
33. Feed AI/Pulse Medical | spec doc existe, pas tables/routes medicales visibles | tests docs Pulse medical en echec dans repo invariants | no flag | jobs absent | MAPPING absent | spec non implementee [docs 34 headings; pytest failure `test_pulse_medical...`].
34. Frontend metadata | code routes statiques existe | nombreux tests frontend/docs en echec sur doc 05/doc 53/docs 63 | no runtime flag | jobs absent | MAPPING: 69 existe | code partiel, docs rouges [routes list; pytest failures].
35. Qwen local adapter | code existe et tests `test_qwen_adapter.py` passent dans suite visible | backend suite globale rouge | `qwen_enabled=false`, `qwen_dry_run=true` par defaut | jobs absent | MAPPING absent | fondation safe [config.py:1295-1299; qwen.py:39-45,135-170].
36. Orchestrateur Tower | merge effectif dans `/opt/orchestrator` | 227/227 passed | `DESIGN_CLAUDE_EXECUTION_ENABLED=false` par defaut | DB interne orchestrateur hors job_definitions | N/A | vert local [orchestrator config.py; pytest orchestrator].
37. Couverture digest: backend code, migrations, tests, docs_master, orchestrator code/tests lus par commandes [cmd find/rg/nl].
38. Exclusions motivees: DB runtime non verifiee a cause auth Postgres refusee [cmd alembic current].
39. Exclusions motivees: `/opt/apps` vide dans inspection; aucun ecran Android reel auditable [cmd find /opt/apps].
40. Exclusions motivees: MAPPING de passes absents; impossible d'exploiter journal spec-reel demande [cmd find MAPPING].
41. Exclusions motivees: doc 78 absent; toolbox reconstituee depuis `/opt/orchestrator/model_routing.py` et imports [cmd rg --files docs_master; model_routing.py:1-107].

## 2. Carte du systeme
42. Topologie physique specifiee: Hostinger VPS porte backend/Postgres/n8n; Tower porte services GPU locaux; tablette Galaxy interface utilisateur [docs_master/F10_TOPOLOGIE_INFRA.md headings; F10 sections 3-5].
43. Topologie runtime constatee backend: Docker compose expose service backend avec `DATABASE_URL`, `INTERNAL_WEBHOOK_SECRET`, Qwen/n8n env vars, reseau `n8n-postgresql_default` [docker-compose.imperium.yml:12-31,53-57].
44. Topologie runtime constatee Tower: `/opt/orchestrator` contient bot Telegram, runners Codex/Claude/OpenRouter/image/design, tests verts [find /opt/orchestrator; pytest orchestrator].
45. Protocole backend-n8n: HMAC `X-Timestamp`, `X-Signature`, `Idempotency-Key` pour inbound internal webhooks [internal_webhooks.py:1344-1380].
46. Protocole backend->n8n: `build_signed_n8n_request` signe JSON trie et envoie HTTP POST si dry-run false [n8n_client.py:1444-1527].
47. Protocole DB: SQLAlchemy/FastAPI vers PostgreSQL via `DATABASE_URL`; DB runtime non connectee durant audit [config.py:1276; cmd alembic current].
48. Protocole Tower orchestration: Telegram bot polling appelle runners et maintient etat in-memory [orchestrator/main.py:397-438; telegram_bot.py:445-458].
49. Imperium existe backend: dashboard, daily-plan, missions, day, priorities, decision-framework, weekly-review, memories, calendar routes [routes introspection].
50. Imperium specifie: command center, plan vivant, hooks, decision framework, one active mission [docs 43 headings; docs 08 lines 34-84].
51. Imperium absent: ecran Android reel non auditable sous `/opt/apps` [cmd find /opt/apps].
52. Vector existe backend: schema AI task types `vector.event_scan`, `vector.rail_disruption_triage`, `vector.zone_recommendation`; service scoring local [schemas/ai.py lines earlier; services/vector/scoring.py].
53. Vector specifie: no auto-click, no tap simulation, no fake GPS, manual-first V1 [docs 08 lines 278-328].
54. Vector absent: aucune route `/api/vector` dans FastAPI [routes introspection].
55. Vault existe backend: `/api/vault/*` legacy et `/api/imperium/vault/*` ledger/summary/reversal [routes introspection].
56. Vault specifie: observe/report, wallet derive, no fake financial truth, sadaqa based on real profit [docs 08 lines 330-360].
57. Vault code: `ImperiumVaultTransaction` ledger avec amount_cents, wallet, reversal fields, one reversal per original index [models/vault.py:1172-1246].
58. Pulse existe backend: `/api/imperium/pulse/entries`, `/today`, `/stats/summary` [routes introspection].
59. Pulse specifie: simple/practical; domains meals/stock/workouts/body; broad future surfaces [docs 40 headings].
60. Pulse code: one entry per user/date, sleep/energy/fatigue/weight/workout constraints [models/imperium.py:304-354].
61. Path existe backend: habits, check-ins, items, today, day, recent, stats [routes introspection].
62. Path specifie: worship/prayer/fasting/sadaqa and Vault linkage [docs 41 headings; AGENTS Path section].
63. Path code: habits/check-ins routes exist; sadaqa linkage not verified in code routes list [routes introspection; HYPOTHESE for linkage absent].
64. System/Brain existe backend: AI tasks/results/validations, memory schema, event ingestion, n8n callbacks [routes introspection; models/ai.py].
65. System/Brain specifie: backend+n8n+Postgres+pgvector+AI router are brain, apps are interfaces [AGENTS; docs 44 headings].
66. Toolbox doc 78 absent; effective toolbox derived from orchestrator [cmd rg --files docs_master].
67. Toolbox Codex: alias `openai_fast` -> `gpt-5.4-mini`, `openai_strong` -> `gpt-5.5`, runner_kind `codex` [model_routing.py:31-45].
68. Toolbox Claude Audit: alias `claude_audit` -> model `opus`, runner_kind `claude` [model_routing.py:46-52].
69. Toolbox DeepSeek/Gemini/Qwen: OpenRouter aliases `deepseek`, `gemini`, `qwen` [model_routing.py:53-73].
70. Toolbox Image: `image_runner` imported and image flow managed in Telegram bot [telegram_bot.py:487,2160-2198].
71. Toolbox Claude Design: design sessions/corrections via `claude_design_runner` and state fields [state.py:249-263; telegram_bot.py:2010-2158].
72. Toolbox single-run guard: orchestrator rejects prompts while `orchestrator_state.is_running()` [state.py:278-287; telegram_bot.py:1925-1927].
73. Decision lives in backend services: missions decision preview/scores deterministic [missions.py:316-383; decision_framework service referenced missions.py:43-48].
74. Memory lives in `ai_memories` pgvector-style table and memory services [models/ai.py; services/ai/memories.py].
75. Plan lives in daily plan tables/routes, not in `v_plan_current` view [routes introspection; rg v_plan_current absent].
76. Docket term: no code object named docket found [cmd rg docket].
77. Event log lives in `events` and `imperium_events`; canonical `events` has envelope with source_app/privacy/idempotency [models/event.py:1119-1155].
78. AI task queue lives in `ai_tasks` and `ai_results`; no runner job table found [models/ai.py; rg job_definitions absent].

## 3. Flux majeurs reels
79. Legende: `[OK]` code+test visible; `[PARTIAL]` code sans chain complete; `[ABSENT]` non trouve; `[SPEC]` doc seulement [commande pytest; rg].
80. Flux A attendu: event -> NOTIFY -> usine -> docket -> WR -> ecriture E2 + memoire [demande audit §3].
81. A1 event ingestion `[OK]`: `POST /api/events` monte, service ingestion existe [routes introspection; services/events/ingestion.py].
82. A2 append event `[OK]`: table `events` avec unique user/event/idempotency et privacy_level [models/event.py:1119-1155].
83. A3 NOTIFY `[ABSENT]`: aucun `LISTEN/NOTIFY/pg_notify` dans code/migrations [cmd rg].
84. A4 usine `[ABSENT]`: aucun worker usine ou job_definitions trouve [cmd rg job_definitions].
85. A5 docket `[ABSENT]`: aucun objet code `docket` trouve [cmd rg docket].
86. A6 WR consume event `[PARTIAL]`: WR lit sessions/messages/AI results mais pas branche sur NOTIFY [weekly_review_conversation.py; rg NOTIFY absent].
87. A7 ecriture E2 `[ABSENT]`: aucun symbole/table E2 trouve dans inspection [cmd rg `E2` non conserve; HYPOTHESE absence a re-verifier].
88. A8 memoire `[PARTIAL]`: memory candidates/commit routes existent, commit explicite requis [routes introspection; services/weekly_review_conversation.py:2762-3043].
89. Flux A ASCII: `POST /api/events -> events table -> [no NOTIFY] -> [no docket] -> WR manual/AI routes -> memory candidates -> explicit commit` [sources A1-A8].
90. Verdict A: chaine demandee non tournee reellement; seuls event log, WR, memoire explicite existent [A1-A8].
91. Flux B attendu: plan regeneration/deltas/choc -> v_plan_current -> selection Daily -> completion -> events [demande audit §3].
92. B1 daily read `[OK]`: `GET /api/imperium/daily-plan` existe [routes introspection].
93. B2 old daily CRUD `[OK]`: create/get/today/activate/cancel/complete day plan routes existent [routes introspection].
94. B3 `v_plan_current` `[ABSENT]`: aucun view/migration/code trouve [cmd rg v_plan_current].
95. B4 regeneration/deltas/choc `[SPEC/PARTIAL]`: docs 43 decrivent plan vivant/hooks; code route de replan dedie non identifie [docs 43 headings; routes introspection].
96. B5 selection Daily `[PARTIAL]`: service daily_plan compose snapshots dashboard/path/pulse/vault; pas via view [daily_plan.py; routes introspection].
97. B6 completion -> events `[OK/PARTIAL]`: mission completion/failure cree Event `mission.<outcome>` [missions.py:454-518].
98. Flux B ASCII: `snapshots services -> GET daily-plan / day-plan CRUD -> mission complete/fail -> events table` [B1-B6].
99. Verdict B: backend daily existe; architecture view-driven `v_plan_current` absente [B1-B6].
100. Flux C attendu Pulse: signaux -> sentinelle -> interprete -> procedure -> proposition -> feedback [demande audit §3].
101. C1 signaux `[OK]`: pulse entries acceptent sleep/energy/fatigue/weight/workout [models/imperium.py:304-354].
102. C2 today/stats `[OK]`: `/today` et `/stats/summary` montes [routes introspection].
103. C3 sentinelle `[SPEC]`: doc Pulse detaille decision layers/recommendations; pas de runner trouve [docs 40 headings; rg runner absent Pulse].
104. C4 interprete/procedure/proposition `[PARTIAL]`: AI task types Pulse existent dans schemas, pas de workflow Pulse branche [schemas/ai.py; rg workflow Pulse absent].
105. C5 feedback `[ABSENT/PARTIAL]`: aucun endpoint feedback Pulse dedie dans routes [routes introspection].
106. Flux C ASCII: `POST pulse entry -> pulse table -> today/stats read models -> [no sentinel runner] -> [AI task types only]` [C1-C5].
107. Verdict C: V1 pratique de tracking existe; boucle medical/feed AI non implementee [C1-C5; docs 34; pytest failure].
108. Flux D attendu Vector: sonnerie -> halo + log -> Tower entrainement -> bundle [demande audit §3].
109. D1 sonnerie `[ABSENT]`: aucun Android/app/service notification Vector auditable [cmd find /opt/apps; routes introspection].
110. D2 halo `[SPEC]`: docs/design mention Vector Halo; aucun code app visible [docs 59 refs via rg; /opt/apps vide].
111. D3 log `[PARTIAL]`: AI task types Vector et generic event log peuvent stocker, mais pas endpoint Vector dedie [schemas/ai.py; routes introspection].
112. D4 Tower entrainement `[SPEC]`: doc 57 contient CatBoost training pipeline; aucun trainer code trouve dans backend [docs 57 headings; find backend services/vector].
113. D5 bundle `[ABSENT]`: aucun bundle/vector model artifact trouve dans code inspecte [find backend; find orchestrator].
114. Flux D ASCII: `[no app sonnerie] -> [no halo code] -> generic ai_tasks/events -> [no trainer] -> [no bundle]` [D1-D5].
115. Verdict D: Vector reste surtout specification, avec scoring service minimal non expose [D1-D5].
116. Flux E attendu apprentissage transverse: refus/overrides/audits -> v_ai_training_pairs -> futur LoRA [demande audit §3].
117. E1 refus/validations `[OK]`: `ai_result_validations` table/routes accept/reject/edit existent [routes introspection; models/ai.py].
118. E2 memory candidate decisions `[OK]`: approve/edit/reject memory candidates routes existent [routes introspection].
119. E3 audits `[PARTIAL]`: backend/audits et patch_reports existent; pas de table audit training [find backend audits; rg v_ai_training_pairs absent].
120. E4 `v_ai_training_pairs` `[ABSENT]`: no view/code/migration [cmd rg v_ai_training_pairs].
121. E5 LoRA `[SPEC]`: futur mentionne par demande; aucun code LoRA trouve [cmd rg LoRA non central; HYPOTHESE].
122. Flux E ASCII: `AI validation + memory decisions + audit files -> [no v_ai_training_pairs] -> [no LoRA pipeline]` [E1-E5].
123. Verdict E: donnees sources existent, projection training absente [E1-E5].

## 4. Invariants graves et enforcement
124. `Only one active mission` ecrit: IMP-001 [docs 08 lines 37-43].
125. `Only one active mission` force SQL: partial unique index `imperium_missions_one_active_per_user_idx` [models/imperium.py:143-148; migration 0005 lines 57-64].
126. `Only one active mission` force API: start/promote rejettent active existante [missions.py:114-117,406-408].
127. Verdict: tenu au niveau code/schema; DB runtime non verifiee [cmd alembic current].
128. `Apps are interfaces` ecrit: AUTHORITY-002 [docs 08 lines 97-103].
129. `Apps are interfaces` force: backend routes source of truth; `/opt/apps` absent donc enforcement Android non verifiable [routes introspection; find /opt/apps].
130. Verdict: ecrit/backend compatible, Android non verifie.
131. `n8n not DB owner` ecrit: AUTHORITY-003/004 [docs 08 lines 105-119].
132. `n8n not DB owner` force: internal webhook HMAC; backend->n8n signed client; no direct DB workflow code trouve [internal_webhooks.py:1344-1380; n8n_client.py:1444-1527].
133. Verdict: tenu cote backend; n8n runtime/workflows non verifies.
134. `Postgres canonical` ecrit: AUTHORITY-005 [docs 08 lines 121-127].
135. `Postgres canonical` force: tables SQLAlchemy pour missions, events, vault, pulse, path, WR [models/imperium.py; models/vault.py; models/ai.py].
136. Verdict: tenu conceptuellement; DB runtime inaccessible.
137. `pgvector semantic, not truth` ecrit: AUTHORITY-006 [docs 08 lines 129-135].
138. `pgvector semantic, not truth` force: memory write requires explicit services/idempotency; schema health says commit disabled until embedding service [schemas/ai.py; tests test_ai_memories_foundation].
139. Verdict: partiel; memory table exists but embeddings service not active.
140. `Events append-only` ecrit: EVENT-003 [docs 08 lines 157-163].
141. `Events append-only` force migrations: trigger prevent update/delete/truncate on `events`, `auth_events`, `imperium_events` [migrations 0002,0003,0029].
142. Verdict: tenu dans migrations; runtime DB non verifie.
143. `Mutations need idempotency` ecrit: EVENT-001 [docs 08 lines 141-147].
144. `Mutations need idempotency` force API: mission start/complete store idempotency; internal webhook requires header [missions.py:100-177,454-518; internal_webhooks.py:1344-1360].
145. Verdict: tenu sur routes inspectees, pas prouve exhaustif pour toutes routes.
146. `HMAC internal webhooks` ecrit: SEC-004 [docs 08 lines 209-215].
147. `HMAC internal webhooks` force code: timestamp freshness + signature compare_digest [internal_webhooks.py:1362-1375].
148. Verdict: tenu cote backend.
149. `high/very_high privacy gate` ecrit: PRIV-001/002 [docs 08 lines 229-243].
150. `high/very_high privacy gate` force code: event privacy enum stored; AI task privacy_level field exists [models/event.py:1150-1154; models/ai.py].
151. `high/very_high privacy gate` fail: no exhaustive external provider gate proven in routes [rg providers; HYPOTHESE].
152. Verdict: ecrit-partiellement-force.
153. `No AI write without explicit validation` ecrit: PRIV-006 [docs 08 lines 269-275].
154. Enforcement: AI results validations and WR approval/store routes explicit [routes introspection; weekly_review_conversation.py:2168-2244].
155. Verdict: tenu pour WR/memory candidates; not global proven.
156. `Vector no auto-click/tap/fake GPS` ecrit: VECTOR-001..004 [docs 08 lines 281-311].
157. Enforcement code: aucun app Vector present, donc pas de violation constatee; pas d'enforcement Android verifiable [find /opt/apps].
158. Verdict: ecrit-non-force dans code auditable.
159. `Vector zero LLM critical path` ecrit: doc 57 says not LLM for real-time scoring [docs 57 headings §2].
160. Enforcement: aucun real-time Vector path code; no LLM path can be verified [routes introspection].
161. Verdict: non applicable/absent.
162. `Vault observes/reports` ecrit: Vault rules in AGENTS and docs 08 VAULT [AGENTS; docs 08 lines 330-360].
163. Enforcement: Vault summary reads; ledger append-only guard migration 0033; reversal instead update [models/vault.py:1172-1246; migration 0033].
164. Verdict: partiel tenu.
165. `Vault append-only` ecrit/force: migration 0033 adds update/delete/truncate guards [migration 0033].
166. Verdict: tenu in migration; runtime DB non verifie.
167. `Sadaqa from real profit` ecrit: VAULT-003 [docs 08 lines 349-355].
168. Enforcement: no direct sadaqa linkage found in inspected routes [routes introspection; rg sadaqa not in captured code].
169. Verdict: ecrit-non-force.
170. `Pulse simple/practical` ecrit: AGENTS and docs 40 [AGENTS; docs 40].
171. Enforcement: implemented Pulse is minimal daily entry/stats [models/imperium.py:304-354; routes introspection].
172. Verdict: tenu V1 minimal.
173. `Reason obligatoire for failed/abandoned missions` ecrit: IMP-005 requires failure reasons [docs 08 lines 69-75].
174. Enforcement: tests require failed/abandoned reason; service stores failure_reason [pytest log; missions.py:492-500].
175. Verdict: tenu pour mission completion.
176. `Path missed requires reason` force: migration 0034 exists [migration list].
177. Verdict: likely tenu schema; runtime DB non verifie.
178. `One runner` ecrit in task: "un seul runner" invariant demande [demande audit §4].
179. Enforcement orchestrator: state `is_running()` and `try_start_run()` block concurrent runs [state.py:278-287].
180. Verdict: tenu pour orchestrateur Telegram.
181. `Secrets not placeholders` force: startup validates JWT/internal/n8n secrets [config.py:1305-1322].
182. Verdict: tenu; route introspection needed fake non-default env [cmd route introspection].
183. `Raw device data never in prompt` ecrit in task; code enforcement not proven [demande audit §4; qwen.py build_prompt uses bounded JSON of input_payload].
184. Verdict: risque; no global sanitizer except memory unsafe metadata keys [services/ai/memories.py: unsafe_keys from rg].
185. `Plancher x1.3` demande invariant: aucune source trouvee dans code/docs inspectes [cmd rg `1,3|1.3|plancher` non conserve; HYPOTHESE].
186. Verdict: absent.

## 5. Incoherences residuelles
187. AD-1 MAJEUR S depuis audit: MAPPING de passes absents alors que la mission les declare source primaire [find MAPPING].
188. AD-2 MAJEUR S depuis audit: doc 78 toolbox absent alors que la mission demande son etat outil par outil [rg docs_master].
189. AD-3 MAJEUR M depuis 2026-07-11: suite backend rouge 35 fails, CI rejettera [pytest backend].
190. AD-4 MAJEUR S: `05_DATABASE_SCHEMA.md` manque metadata frontend/daily attendue par tests [pytest failures frontend/daily].
191. AD-5 MINEUR S: `53_SUBMISSIONS_OVERLAY_TASKS.md` manque sections Qwen prompt attendues [pytest failures doc 53].
192. AD-6 MAJEUR M: `docs_master/63_FRONTEND_ARCHITECTURE_V1.md` et docs screen manquent clauses attendues par tests [pytest failures screen architecture].
193. AD-7 MAJEUR M: `/opt/apps` vide; aucune facade Android reelle malgre specs UI massives [find /opt/apps].
194. AD-8 MAJEUR M: Vector a docs ML/halo mais pas route backend dediee ni app auditable [routes introspection; docs 57].
195. AD-9 MAJEUR L: flux event->NOTIFY->docket absent; events sont stockes mais pas orchestrés par Postgres notification [rg NOTIFY/docket].
196. AD-10 MAJEUR M: `v_plan_current` absent alors que le flux Daily cible une vue courante [rg v_plan_current].
197. AD-11 MAJEUR M: `v_ai_training_pairs` absent; apprentissage transverse non projetable [rg v_ai_training_pairs].
198. AD-12 MAJEUR M: `job_definitions` absent; impossible de comparer jobs enregistres vs actives [rg job_definitions].
199. AD-13 MAJEUR S: Alembic runtime non verifiable avec credentials locaux [cmd alembic current].
200. AD-14 MINEUR S: backend `.env.example` garde `postgres:postgres` exemple; startup force secrets mais DB placeholder reste doc/dev [backend/.env.example:6].
201. AD-15 MAJEUR M: docs 31/32 disent workflows n8n artifacts dans `ops/n8n/workflows`, mais audit n'a pas trouve cette arborescence dans sorties initiales [docs 31 lines 1780-1829; find output].
202. AD-16 MINEUR S: docs 02/03 marquees DEPRECATED mais AGENTS les liste encore comme attendues [docs headings; AGENTS].
203. AD-17 MAJEUR L: Pulse Medical Feed AI richement specifie mais tables/routes medical documents non visibles [docs 34 headings; routes introspection].
204. AD-18 MAJEUR M: Path sadaqa/Vault linkage specifie mais non prouve dans routes inspectees [AGENTS Path; routes introspection].
205. AD-19 MINEUR M: `imperium_events` event_type regex interdit point (`^[a-z][a-z0-9_]*$`) alors docs demandent dotted events; canonical `events` accepte text [models/imperium.py:64-80; docs 08 lines 149-155].
206. AD-20 MAJEUR M: `imperium_events` source modules differ from AI source modules (`mission` vs `imperium`) [models/imperium.py:76-79; models/ai.py source_module check].
207. AD-21 MAJEUR S: backend app import bloque sans secrets non-placeholder, ce qui est bon prod mais complique introspection/tests manuels [config.py:1305-1322; route introspection retry].
208. AD-22 MINEUR S: orchestrator Qwen alias utilise OpenRouter `qwen/qwen-2.5-72b-instruct`, different du backend local Qwen V1 `qwen2.5:7b-instruct` [model_routing.py:67-72; config.py:1295-1299].
209. AD-23 MAJEUR M: Real local Qwen disabled by default; Patch 2E foundation exists but production model path off unless env changes [config.py:1295-1299; qwen.py:135-136].
210. AD-24 MAJEUR M: Embeddings table exists but schema health says writes wait for embedding service; no embedding runner flag visible [schemas/ai.py; tests memory].
211. AD-25 MINEUR M: Existing untracked `audits/2026-07-11_ARCHITECTURE_DIGEST.md` may overlap with this digest [git status].
212. AD-26 MINEUR S: Working tree already dirty (`audits/LATEST.txt`, `gap_analysis_v1/00_INDEX.md`, untracked toolbox) before this doc [git status].
213. AD-27 MAJEUR L: No frontend consuming APIs can be verified because `/opt/apps` empty [find /opt/apps].
214. AD-28 MINEUR S: `/api/imperium/events` intentionally decommissioned while generic `/api/events` remains [pytest `test_imperium_events_decommission`; routes introspection].

## 6. Surfaces de risque
215. R1 CI risk: backend tests fail now; deploy will reject even if runtime routes work [pytest backend].
216. R2 Audit source risk: missing MAPPING means deviation history is fragmented [find MAPPING].
217. R3 Runtime DB risk: migrations may not match live DB; Alembic current impossible [cmd alembic current].
218. R4 Orchestration risk: no `job_definitions`, no NOTIFY, no docket; automation brain may be manual-route only [rg job_definitions/NOTIFY/docket].
219. R5 Vector compliance risk: no app code to enforce "read-only advise"; absence avoids violation but not product proof [find /opt/apps; docs 08 lines 281-311].
220. R6 Vector MVP risk: specs exceed implementation by large margin [docs 57; routes introspection].
221. R7 Memory risk: vector schema exists but embeddings disabled; arbitration must decide commit path [models/ai.py; schemas/ai.py].
222. R8 Privacy risk: external provider gate not globally proven; only field/schema-level privacy visible [models/event.py; qwen.py].
223. R9 Frontend metadata risk: code appears static, docs drift causes many failures [pytest frontend failures].
224. R10 Schema-doc risk: doc 05 is treated by tests as contract text, not just DB schema [pytest failures].
225. R11 n8n risk: backend has signed client but real workflows/artifacts not verified in repo [docs 31 lines 1780-2198; find output].
226. R12 Qwen risk: backend official V1 local model is dry-run/off by default; real_ai not active [config.py:1295-1299].
227. R13 Orchestrator model risk: Tower Qwen alias is OpenRouter 72B, not local Qwen 7B [model_routing.py:67-72].
228. R14 App absence risk: Android UX, offline queue, voice input, driving constraints untested [find /opt/apps; AGENTS constraints].
229. R15 Financial truth risk: Vault ledger exists; wallet balances derivation/personal-business separation not fully audited [models/vault.py; routes introspection].
230. R16 Sadaqa risk: Path-Vault calculation not traced in code during audit [AGENTS; routes introspection].
231. R17 Event taxonomy risk: generic `events` and `imperium_events` have divergent format/source rules [models/event.py; models/imperium.py:64-80].
232. R18 Audit overload risk: docs_master contains many future/V2/V3 specs; MVP boundary can blur [find docs_master; docs 53 V3 failure].
233. R19 Security operations risk: `.env.example` uses simple DB example; deployment README has real host placeholders; avoid leaking/rotating secrets if exposed [README refs from rg].
234. R20 Test suite split risk: orchestrator green can mask backend red; both must be reported separately [pytest backend; pytest orchestrator].
235. R21 Direct DB select unavailable risk: job activation/runtime flags in DB cannot be asserted [cmd alembic current].
236. R22 Calendar risk: calendar routes exist despite docs noting conflicts around Samsung/calendar future [models/imperium.py:357-396; doc 05 tail in pytest output].
237. R23 Decommission risk: `imperium_events` table still exists while route removed; clarify canonical event path [models/imperium.py:64-120; pytest decommission].
238. R24 Daily risk: old `/day/plan` CRUD and new `/daily-plan` read model coexist; arbitration needed on canonical plan surface [routes introspection].
239. R25 AI canonicality risk: AI task/result foundation strong, but no central runner loop consumes `ai_tasks` found [models/ai.py; rg runner].

## 7. Arbitrage frontier: questions a trancher
240. Q1: Faut-il creer les MAPPING par passe retroactivement ou remplacer cette convention par un `ARCHITECTURE_DIGEST` periodique? [AD-1].
241. Q2: Faut-il restaurer/creer doc 78 toolbox, ou declarer `/opt/orchestrator/model_routing.py` source canonique? [AD-2; model_routing.py].
242. Q3: Le prochain fix doit-il etre docs-only pour repasser les 35 tests, avant toute architecture? [pytest backend].
243. Q4: Le brain V1 doit-il utiliser Postgres NOTIFY/job_definitions ou rester API+n8n webhooks explicites? [rg NOTIFY/job_definitions absent].
244. Q5: Daily canonical doit-il etre `/api/imperium/daily-plan` read-only ou `/api/imperium/day/plan/*` CRUD? [routes introspection].
245. Q6: Faut-il implementer `v_plan_current` comme vue DB, read model service, ou abandonner le nom? [rg v_plan_current absent].
246. Q7: Vector V1 doit-il rester manuel screenshots/advice ou inclure sonnerie/halo Android maintenant? [docs 08 Vector; /opt/apps vide].
247. Q8: Le scoring Vector doit-il etre route backend avant Android, ou Android-first avec backend log minimal? [services/vector/scoring.py; no route].
248. Q9: Faut-il activer Qwen local reel sur Tower ou garder dry-run jusqu'a WR stable? [config.py:1295-1299; qwen.py].
249. Q10: Les embeddings doivent-ils etre actives avant WR memory commit, ou memory commit reste bloque? [schemas/ai.py; memory tests].
250. Q11: Le Path sadaqa linkage doit-il etre table/endpoint dedie ou derive dans summary Vault/Path? [AGENTS; routes].
251. Q12: `imperium_events` doit-il etre supprime, aligne sur dotted events, ou garde comme log interne separe? [models/imperium.py:64-80; docs 08 lines 149-155].
252. Q13: n8n workflow artifacts doivent-ils etre versionnes dans ce repo sous `ops/n8n/workflows`? [docs 31 lines 1780-2198].
253. Q14: Faut-il une table `ai_training_pairs`/vue `v_ai_training_pairs` maintenant ou attendre LoRA? [rg v_ai_training_pairs absent].
254. Q15: Android apps doivent-ils etre scaffoldes dans `/opt/apps` maintenant pour verifier les contrats consommes? [find /opt/apps].

## 8. Index sources rapides
255. Backend routes source: introspection FastAPI avec secrets factices non-default [cmd route introspection].
256. Backend config source: `backend/app/core/config.py:1270-1322` [nl config].
257. HMAC inbound source: `backend/app/core/internal_webhooks.py:1344-1380` [nl internal_webhooks].
258. HMAC outbound source: `backend/app/services/integrations/n8n_client.py:1444-1527` [nl n8n_client].
259. Mission source: `backend/app/services/imperium/missions.py:100-177`, `454-518` [nl missions].
260. Mission schema source: `backend/app/models/imperium.py:123-198` [nl models].
261. Event schema source: `backend/app/models/event.py:1119-1155` [nl models].
262. Imperium event schema source: `backend/app/models/imperium.py:64-120` [nl models].
263. Pulse schema source: `backend/app/models/imperium.py:304-354` [nl models].
264. Calendar schema source: `backend/app/models/imperium.py:357-396` [nl models].
265. Vault schema source: `backend/app/models/vault.py:1172-1246` [nl models].
266. WR docs source: `docs_master/31_AI_TASKS_AND_RESULTS_CONTRACT.md:1704-2198` [nl docs].
267. Qwen backend source: `backend/app/services/ai/providers/qwen.py:39-45`, `135-170` [nl qwen].
268. Orchestrator routing source: `/opt/orchestrator/model_routing.py:31-107` [nl orchestrator].
269. Orchestrator state source: `/opt/orchestrator/state.py:119-318` [nl orchestrator].
270. Orchestrator main source: `/opt/orchestrator/main.py:397-438` [nl orchestrator].
271. Orchestrator Telegram flow source: `/opt/orchestrator/telegram_bot.py:445-458`, `1916-2198` [nl orchestrator].
272. Non-negotiables source: `docs_master/08_NON_NEGOTIABLE_RULES.md:34-328` [nl docs].
273. Infra source: `docs_master/F10_TOPOLOGIE_INFRA.md` headings and sections [rg headings].
274. Pulse spec source: `docs_master/40_PULSE_LOGIC_DETAIL.md` headings [rg headings].
275. Vector spec source: `docs_master/33_VECTOR_LOGIC_DETAIL.md`, `57_VECTOR_RIDE_SCORING_ML.md` headings [rg headings].
276. N8N responsibility source: `docs_master/45_N8N_RESPONSIBILITY_MATRIX.md` headings [rg headings].
277. Frontend mapping source: `docs_master/69_FRONTEND_API_MAPPING_V1.md` exists as only MAPPING-like file [find MAPPING].
278. Backend test source: `./.venv/bin/pytest` output 907/943/35 failed/9 skipped [cmd pytest backend].
279. Orchestrator test source: `./venv/bin/python -m pytest` output 227 passed [cmd pytest orchestrator].
280. DB runtime source: `alembic current` failed password auth [cmd alembic current].

## 9. Troncature volontaire
281. Troncature A: docs UI/design 59-69 non detaillees sauf failures et endpoints, car `/opt/apps` absent [find /opt/apps; pytest failures].
282. Troncature B: contenus longs des docs 31/32 WR non recopies; sources exactes pointees [docs 31/32].
283. Troncature C: tous les tests unitaires non enumeres; seuls resultats globaux et familles de failures retenus [pytest backend].
284. Troncature D: anciens audits/patch_reports non synthetises; ils sont nombreux et hors demande principale [find backend/audits].
285. Troncature E: code orchestrateur design/image non detaille hors toolbox, car ce digest cible ecosysteme Imperium backend/apps [orchestrator tests].
286. Ligne finale: le systeme reel est un backend FastAPI riche + orchestrateur Tower vert + docs ambitieuses; les apps Android, les jobs, les vues plan/training, Vector runtime et DB live restent les grands trous d'architecture [sources ci-dessus].

## 10. Inventaire endpoints montes
287. AI endpoint: `POST /api/ai/qwen/smoke` existe [route introspection].
288. AI endpoint: `POST /api/ai/results/{result_id}/reject` existe [route introspection].
289. AI endpoint: `POST /api/ai/results/{result_id}/validate` existe [route introspection].
290. AI endpoint: `POST /api/ai/tasks` existe [route introspection].
291. AI endpoint: `GET /api/ai/tasks/{task_id}` existe [route introspection].
292. AI endpoint: `POST /api/ai/tasks/{task_id}/mark-running` existe [route introspection].
293. Auth endpoint: `GET /api/auth/devices` existe [route introspection].
294. Auth endpoint: `POST /api/auth/devices/register` existe [route introspection].
295. Auth endpoint: `POST /api/auth/devices/{device_id}/revoke` existe [route introspection].
296. Auth endpoint: `POST /api/auth/login` existe [route introspection].
297. Auth endpoint: `POST /api/auth/logout` existe [route introspection].
298. Auth endpoint: `POST /api/auth/refresh` existe [route introspection].
299. Events endpoint: `POST /api/events` existe [route introspection].
300. Health endpoint: `GET /api/health` existe [route introspection].
301. Health endpoint: `GET /api/health/db` existe [route introspection].
302. Calendar endpoint: `POST /api/imperium/calendar/events` existe [route introspection].
303. Calendar endpoint: `GET /api/imperium/calendar/events` existe [route introspection].
304. Calendar endpoint: `DELETE /api/imperium/calendar/events/{event_id}` existe [route introspection].
305. Contract endpoint: `GET /api/imperium/contracts/compliance` existe [route introspection].
306. Contract endpoint: `GET /api/imperium/contracts/index` existe [route introspection].
307. Daily endpoint: `GET /api/imperium/daily-plan` existe [route introspection].
308. Dashboard endpoint: `GET /api/imperium/dashboard` existe [route introspection].
309. Day endpoint: `POST /api/imperium/day/finish` existe [route introspection].
310. Day endpoint: `GET /api/imperium/day/latest` existe [route introspection].
311. Day plan endpoint: `POST /api/imperium/day/plan` existe [route introspection].
312. Day plan endpoint: `GET /api/imperium/day/plan` existe [route introspection].
313. Day plan endpoint: `GET /api/imperium/day/plan/today` existe [route introspection].
314. Day plan endpoint: `POST /api/imperium/day/plan/{plan_id}/activate` existe [route introspection].
315. Day plan endpoint: `POST /api/imperium/day/plan/{plan_id}/cancel` existe [route introspection].
316. Day plan endpoint: `POST /api/imperium/day/plan/{plan_id}/complete` existe [route introspection].
317. Decision endpoint: `GET /api/imperium/decision-framework/priorities` existe [route introspection].
318. Decision endpoint: `POST /api/imperium/decision-framework/priorities` existe [route introspection].
319. Decision endpoint: `GET /api/imperium/decision-framework/schema` existe [route introspection].
320. Decision endpoint: `POST /api/imperium/decision-framework/score-preview` existe [route introspection].
321. Frontend metadata endpoint: `GET /api/imperium/frontend/actions` existe [route introspection].
322. Frontend metadata endpoint: `GET /api/imperium/frontend/app-manifest` existe [route introspection].
323. Frontend metadata endpoint: `GET /api/imperium/frontend/asset-registry` existe [route introspection].
324. Frontend metadata endpoint: `GET /api/imperium/frontend/design-handoff` existe [route introspection].
325. Frontend metadata endpoint: `GET /api/imperium/frontend/empty-states` existe [route introspection].
326. Frontend metadata endpoint: `GET /api/imperium/frontend/layout` existe [route introspection].
327. Frontend metadata endpoint: `GET /api/imperium/frontend/module-cards` existe [route introspection].
328. Frontend metadata endpoint: `GET /api/imperium/frontend/navigation` existe [route introspection].
329. Frontend metadata endpoint: `GET /api/imperium/frontend/theme-tokens` existe [route introspection].
330. Home endpoint: `GET /api/imperium/home/bootstrap` existe [route introspection].
331. Memory endpoint: `GET /api/imperium/memories` existe [route introspection].
332. Memory endpoint: `GET /api/imperium/memories/schema` existe [route introspection].
333. Memory endpoint: `GET /api/imperium/memories/{memory_id}` existe [route introspection].
334. Memory endpoint: `POST /api/imperium/memories/{memory_id}/archive` existe [route introspection].
335. Memory endpoint: `POST /api/imperium/memories/{memory_id}/supersede` existe [route introspection].
336. Mission endpoint: `GET /api/imperium/missions/active` existe [route introspection].
337. Mission endpoint: `POST /api/imperium/missions/backlog` existe [route introspection].
338. Mission endpoint: `GET /api/imperium/missions/backlog` existe [route introspection].
339. Mission endpoint: `GET /api/imperium/missions/backlog/decision-preview` existe [route introspection].
340. Mission endpoint: `POST /api/imperium/missions/backlog/{mission_id}/promote` existe [route introspection].
341. Mission endpoint: `GET /api/imperium/missions/current` existe [route introspection].
342. Mission endpoint: `GET /api/imperium/missions/history` existe [route introspection].
343. Mission endpoint: `GET /api/imperium/missions/recent` existe [route introspection].
344. Mission endpoint: `POST /api/imperium/missions/start` existe [route introspection].
345. Mission endpoint: `GET /api/imperium/missions/{mission_id}` existe [route introspection].
346. Mission endpoint: `POST /api/imperium/missions/{mission_id}/complete` existe [route introspection].
347. Mission endpoint: `GET /api/imperium/missions/{mission_id}/decision-score` existe [route introspection].
348. Mission endpoint: `POST /api/imperium/missions/{mission_id}/fail` existe [route introspection].
349. Path endpoint: `GET /api/imperium/path/check-ins` existe [route introspection].
350. Path endpoint: `GET /api/imperium/path/check-ins/{check_in_id}` existe [route introspection].
351. Path endpoint: `GET /api/imperium/path/day` existe [route introspection].
352. Path endpoint: `POST /api/imperium/path/habits` existe [route introspection].
353. Path endpoint: `GET /api/imperium/path/habits` existe [route introspection].
354. Path endpoint: `GET /api/imperium/path/habits/{habit_id}` existe [route introspection].
355. Path endpoint: `POST /api/imperium/path/habits/{habit_id}/archive` existe [route introspection].
356. Path endpoint: `POST /api/imperium/path/habits/{habit_id}/check-ins` existe [route introspection].
357. Path endpoint: `POST /api/imperium/path/habits/{habit_id}/reactivate` existe [route introspection].
358. Path endpoint: `POST /api/imperium/path/items` existe [route introspection].
359. Path endpoint: `POST /api/imperium/path/items/{item_id}/cancel` existe [route introspection].
360. Path endpoint: `POST /api/imperium/path/items/{item_id}/complete` existe [route introspection].
361. Path endpoint: `POST /api/imperium/path/items/{item_id}/skip` existe [route introspection].
362. Path endpoint: `POST /api/imperium/path/items/{item_id}/start` existe [route introspection].
363. Path endpoint: `GET /api/imperium/path/recent` existe [route introspection].
364. Path endpoint: `GET /api/imperium/path/stats/summary` existe [route introspection].
365. Path endpoint: `GET /api/imperium/path/today` existe [route introspection].
366. Priority endpoint: `GET /api/imperium/priorities` existe [route introspection].
367. Priority endpoint: `POST /api/imperium/priorities` existe [route introspection].
368. Pulse endpoint: `POST /api/imperium/pulse/entries` existe [route introspection].
369. Pulse endpoint: `GET /api/imperium/pulse/entries` existe [route introspection].
370. Pulse endpoint: `GET /api/imperium/pulse/entries/{entry_id}` existe [route introspection].
371. Pulse endpoint: `GET /api/imperium/pulse/stats/summary` existe [route introspection].
372. Pulse endpoint: `GET /api/imperium/pulse/today` existe [route introspection].
373. Report endpoint: `GET /api/imperium/report/week` existe [route introspection].
374. Vault endpoint: `GET /api/imperium/vault/summary` existe [route introspection].
375. Vault endpoint: `GET /api/imperium/vault/summary/categories` existe [route introspection].
376. Vault endpoint: `GET /api/imperium/vault/summary/monthly` existe [route introspection].
377. Vault endpoint: `GET /api/imperium/vault/transactions` existe [route introspection].
378. Vault endpoint: `POST /api/imperium/vault/transactions` existe [route introspection].
379. Vault endpoint: `GET /api/imperium/vault/transactions/{transaction_id}` existe [route introspection].
380. Vault endpoint: `POST /api/imperium/vault/transactions/{transaction_id}/reverse` existe [route introspection].
381. WR endpoint: `GET /api/imperium/weekly-review/current` existe [route introspection].
382. WR endpoint: `GET /api/imperium/weekly-review/final-reports/stored` existe [route introspection].
383. WR endpoint: `GET /api/imperium/weekly-review/final-reports/{report_id}` existe [route introspection].
384. WR endpoint: `GET /api/imperium/weekly-review/final-reports/{report_id}/memory-candidates` existe [route introspection].
385. WR endpoint: `GET /api/imperium/weekly-review/final-reports/{report_id}/memory-candidates/commit-ready` existe [route introspection].
386. WR endpoint: `POST /api/imperium/weekly-review/final-reports/{report_id}/memory-candidates/{candidate_id}/approve` existe [route introspection].
387. WR endpoint: `POST /api/imperium/weekly-review/final-reports/{report_id}/memory-candidates/{candidate_id}/edit` existe [route introspection].
388. WR endpoint: `POST /api/imperium/weekly-review/final-reports/{report_id}/memory-candidates/{candidate_id}/reject` existe [route introspection].
389. WR endpoint: `GET /api/imperium/weekly-review/history` existe [route introspection].
390. WR endpoint: `POST /api/imperium/weekly-review/launch` existe [route introspection].
391. WR endpoint: `POST /api/imperium/weekly-review/memory-candidates/commit` existe [route introspection].
392. WR endpoint: `POST /api/imperium/weekly-review/memory-candidates/commit-dry-run` existe [route introspection].
393. WR endpoint: `GET /api/imperium/weekly-review/memory-candidates/commit-ready` existe [route introspection].
394. WR endpoint: `GET /api/imperium/weekly-review/memory-candidates/decisions` existe [route introspection].
395. WR endpoint: `GET /api/imperium/weekly-review/memory-candidates/preview` existe [route introspection].
396. WR endpoint: `GET /api/imperium/weekly-review/session` existe [route introspection].
397. WR endpoint: `GET /api/imperium/weekly-review/state` existe [route introspection].
398. WR endpoint: `POST /api/imperium/weekly-review/{session_id}/answer` existe [route introspection].
399. WR endpoint: `POST /api/imperium/weekly-review/{session_id}/approve` existe [route introspection].
400. WR endpoint: `POST /api/imperium/weekly-review/{session_id}/cancel` existe [route introspection].
401. WR endpoint: `POST /api/imperium/weekly-review/{session_id}/chat/confirm-no-more-input` existe [route introspection].
402. WR endpoint: `POST /api/imperium/weekly-review/{session_id}/chat/messages` existe [route introspection].
403. WR endpoint: `GET /api/imperium/weekly-review/{session_id}/conversation` existe [route introspection].
404. WR endpoint: `GET /api/imperium/weekly-review/{session_id}/debug-status` existe [route introspection].
405. WR endpoint: `POST /api/imperium/weekly-review/{session_id}/draft/approve` existe [route introspection].
406. WR endpoint: `POST /api/imperium/weekly-review/{session_id}/draft/reject` existe [route introspection].
407. WR endpoint: `POST /api/imperium/weekly-review/{session_id}/draft/request-changes` existe [route introspection].
408. WR endpoint: `POST /api/imperium/weekly-review/{session_id}/draft/store` existe [route introspection].
409. WR endpoint: `POST /api/imperium/weekly-review/{session_id}/final-draft` existe [route introspection].
410. WR endpoint: `GET /api/imperium/weekly-review/{session_id}/final-report` existe [route introspection].
411. WR endpoint: `GET /api/imperium/weekly-review/{session_id}/final-report/markdown` existe [route introspection].
412. WR endpoint: `GET /api/imperium/weekly-review/{session_id}/memory-candidates` existe [route introspection].
413. WR endpoint: `GET /api/imperium/weekly-review/{session_id}/messages` existe [route introspection].
414. WR endpoint: `POST /api/imperium/weekly-review/{session_id}/messages` existe [route introspection].
415. WR endpoint: `POST /api/imperium/weekly-review/{session_id}/request-revision` existe [route introspection].
416. Internal endpoint: `POST /api/internal/ai/qwen/smoke` existe [route introspection].
417. Internal endpoint: `POST /api/internal/ai/tasks/{task_id}/result` existe [route introspection].
418. Internal endpoint: `POST /api/internal/webhook-test` existe [route introspection].
419. Internal endpoint: `POST /api/internal/weekly-review/ready` existe [route introspection].
420. Internal endpoint: `POST /api/internal/weekly-review/{session_id}/attach-ai-result` existe [route introspection].
421. Internal endpoint: `POST /api/internal/weekly-review/{session_id}/mock-ai-summary` existe [route introspection].
422. Legacy Vault endpoint: `GET /api/vault/summary/week` existe [route introspection].
423. Legacy Vault endpoint: `POST /api/vault/transactions` existe [route introspection].
424. Legacy Vault endpoint: `GET /api/vault/transactions/recent` existe [route introspection].
425. Route absence: aucun endpoint commencant par `/api/vector` [route introspection].
426. Route absence: aucun endpoint commencant par `/api/pulse` hors `/api/imperium/pulse` [route introspection].
427. Route absence: aucun endpoint commencant par `/api/path` hors `/api/imperium/path` [route introspection].

## 11. Inventaire tables modelees
428. Table modelee: `users` [SQLAlchemy metadata dump].
429. Table modelee: `devices` [SQLAlchemy metadata dump].
430. Table modelee: `refresh_tokens` [SQLAlchemy metadata dump].
431. Table modelee: `auth_events` [SQLAlchemy metadata dump].
432. Table modelee: `events` [SQLAlchemy metadata dump].
433. Table modelee: `imperium_events` [SQLAlchemy metadata dump].
434. Table modelee: `idempotency_keys` n'apparait pas dans dump court mais modele `IdempotencyKey` importe dans services [missions.py:12; HYPOTHESE metadata omission due imports].
435. Table modelee: `ai_tasks` [SQLAlchemy metadata dump].
436. Table modelee: `ai_results` [SQLAlchemy metadata dump].
437. Table modelee: `ai_result_validations` [SQLAlchemy metadata dump].
438. Table modelee: `ai_memories` [SQLAlchemy metadata dump].
439. Table modelee: `imperium_day_reviews` [SQLAlchemy metadata dump].
440. Table modelee: `imperium_missions` [SQLAlchemy metadata dump].
441. Table modelee: `imperium_priority_rules` [SQLAlchemy metadata dump].
442. Table modelee: `imperium_daily_plans` [SQLAlchemy metadata dump].
443. Table modelee: `imperium_weekly_review_states` [SQLAlchemy metadata dump].
444. Table modelee: `imperium_weekly_review_sessions` [SQLAlchemy metadata dump].
445. Table modelee: `imperium_weekly_review_messages` [SQLAlchemy metadata dump].
446. Table modelee: `imperium_weekly_review_final_reports` [SQLAlchemy metadata dump].
447. Table modelee: `imperium_memory_candidate_decisions` [SQLAlchemy metadata dump].
448. Table modelee: `imperium_user_priorities` [SQLAlchemy metadata dump].
449. Table modelee: `imperium_mission_scores` [SQLAlchemy metadata dump].
450. Table modelee: `imperium_calendar_events` [SQLAlchemy metadata dump].
451. Table modelee: `imperium_vault_transactions` [SQLAlchemy metadata dump].
452. Table modelee: `imperium_path_items` [SQLAlchemy metadata dump].
453. Table modelee: `imperium_path_habits` [SQLAlchemy metadata dump].
454. Table modelee: `imperium_path_check_ins` [SQLAlchemy metadata dump].
455. Table modelee: `imperium_pulse_entries` [SQLAlchemy metadata dump].
456. Table absente: `job_definitions` [SQLAlchemy metadata dump; rg job_definitions].
457. Table absente: `vector_rides` ou equivalent dedie Vector [SQLAlchemy metadata dump; routes introspection].
458. Table absente: `pulse_medical_documents` ou equivalent medical feed [SQLAlchemy metadata dump; docs 34 spec].
459. View absente: `v_plan_current` [rg v_plan_current].
460. View absente: `v_ai_training_pairs` [rg v_ai_training_pairs].

## 12. Inventaire migrations
461. Migration `20260425_0001_initial_skeleton.py`: socle users/devices/tokens/auth/events/idempotency [migration list; rg create_table].
462. Migration `20260426_0002_security_hardening.py`: hardening refresh tokens et append-only logs [migration list; rg append].
463. Migration `20260426_0003_append_only_truncate_guards.py`: guards TRUNCATE append-only [migration list; rg truncate].
464. Migration `20260426_0004_imperium_day_reviews.py`: day reviews [migration list].
465. Migration `20260426_0005_imperium_missions.py`: missions + unique active [migration list; rg one_active].
466. Migration `20260426_0006_imperium_priority_rules.py`: priority rules [migration list].
467. Migration `20260426_0007_vault_transactions.py`: legacy vault transactions [migration list].
468. Migration `20260426_0008_imperium_path_items.py`: Path items [migration list].
469. Migration `20260426_0009_imperium_daily_plans.py`: daily plans [migration list].
470. Migration `20260427_0010_imperium_weekly_review_states.py`: WR readiness states [migration list].
471. Migration `20260430_0011_events_user_scoped_event_id.py`: event id user scope [migration list].
472. Migration `20260430_0012_ai_tasks_results_foundation.py`: ai_tasks/results/validations [migration list].
473. Migration `20260430_0013_weekly_review_conversation.py`: WR sessions/messages/final reports [migration list].
474. Migration `20260430_0014_wr_final_report_candidate_history.py`: WR active report uniqueness changes [migration list].
475. Migration `20260501_0015_memory_candidate_decisions.py`: WR memory candidate decisions [migration list].
476. Migration `20260501_0016_wr_chatbot_flow_constraints.py`: WR chatbot statuses [migration list].
477. Migration `20260502_0017_ai_memories_foundation.py`: old memory foundation [migration list].
478. Migration `20260503_0018_ai_user_id_not_null.py`: AI ownership hardening [migration list].
479. Migration `20260504_0019_decision_framework_foundation.py`: user priorities and mission scores [migration list].
480. Migration `20260511_0020_imperium_missions_decision_fields.py`: mission decision fields/backlog [migration list].
481. Migration `20260511_0021_imperium_mission_scores_unique_source.py`: mission score uniqueness [migration list].
482. Migration `20260512_0022_imperium_calendar_events_foundation.py`: calendar events [migration list].
483. Migration `20260525_0023_imperium_mission_abandoned_status.py`: abandoned status [migration list].
484. Migration `20260525_0024_imperium_vault_ledger_foundation.py`: Imperium Vault ledger [migration list].
485. Migration `20260525_0025_imperium_vault_transaction_reversals.py`: reversals [migration list].
486. Migration `20260525_0026_imperium_vault_local_date_timezone.py`: vault local date/timezone [migration list].
487. Migration `20260525_0027_imperium_path_habits_check_ins.py`: Path habits/check-ins [migration list].
488. Migration `20260525_0028_imperium_pulse_entries.py`: Pulse entries [migration list].
489. Migration `20260526_0029_imperium_events_foundation.py`: Imperium events + append-only guard [migration list; rg trigger].
490. Migration `20260526_0030_imperium_events_source_module_check.py`: source module check [migration list].
491. Migration `20260526_0031_imperium_events_constraints_hardening.py`: event constraints hardening [migration list].
492. Migration `20260705_0032_ai_memories_unified_vector_schema.py`: unified vector memory schema [migration list].
493. Migration `20260706_0033_imperium_vault_append_only_guards.py`: vault append-only guards [migration list].
494. Migration `20260707_0034_path_check_ins_missed_requires_reason.py`: missed reason Path [migration list].
495. Migration `20260707_0035_calendar_events_soft_delete_traceability.py`: calendar soft-delete traceability [migration list].
496. Migration `20260707_0036_events_depth.py`: event depth [migration list].
497. Migration `20260710_0037_imperium_vault_wallet.py`: vault wallet field [migration list].
498. Migration gap: aucune migration `job_definitions` [migration list; rg job_definitions].
499. Migration gap: aucune migration `v_plan_current` [migration list; rg v_plan_current].
500. Migration gap: aucune migration `v_ai_training_pairs` [migration list; rg v_ai_training_pairs].

## 13. Carte des tests rouges backend
501. Backend global: 35 failed, 907 passed, 9 skipped [pytest backend].
502. Failure family docs 53: `test_carrier_engagement_and_expert_orchestration_are_documented` manque `### 12.2 Qwen carrier prompt template` [pytest backend].
503. Failure family docs 53: `test_doc_53_overlay_exclusions_use_observable_mission_types` ne trouve pas `### 12.1 Qwen prompt template` [pytest backend].
504. Failure family Daily/docs: `test_daily_plan_docs_explicitly_document_contract_rules` manque `meta.daily_plan_version` dans doc 05 [pytest backend].
505. Failure family frontend actions/docs: endpoint code existe mais doc 05 manque `/api/imperium/frontend/actions` [pytest backend; route introspection].
506. Failure family frontend manifest/docs: doc 05 manque `/api/imperium/frontend/app-manifest` [pytest backend].
507. Failure family frontend asset/docs: doc 05 manque `/api/imperium/frontend/asset-registry` [pytest backend].
508. Failure family frontend handoff/docs: doc 05 manque `/api/imperium/frontend/design-handoff` [pytest backend].
509. Failure family frontend empty/docs: doc 05 manque `/api/imperium/frontend/empty-states` [pytest backend].
510. Failure family frontend layout/docs: doc 05 manque `/api/imperium/frontend/layout` [pytest backend].
511. Failure family frontend metadata/docs: doc 05 manque `frontend metadata layer v6` [pytest backend].
512. Failure family frontend module/docs: doc 05 manque `/api/imperium/frontend/module-cards` [pytest backend].
513. Failure family frontend navigation/docs: doc 05 manque `/api/imperium/frontend/navigation` [pytest backend].
514. Failure family frontend theme/docs: doc 05 manque `/api/imperium/frontend/theme-tokens` [pytest backend].
515. Failure family home/docs: home bootstrap docs metadata-only manquants dans doc 05 [pytest backend].
516. Failure family architecture docs: doc 63 manque security/performance/non-goals attendus [pytest backend].
517. Failure family source docs: Vault screen source docs non disponibles selon tests [pytest backend].
518. Failure family source docs: Vector screen source docs non disponibles selon tests [pytest backend].
519. Failure family source docs: Pulse screen source docs non disponibles selon tests [pytest backend].
520. Failure family Pulse medical/docs: required V1 contracts manquants selon tests [pytest backend].
521. Failure family repo invariants: contract index static metadata only docs mismatch [pytest backend].
522. Failure family repo invariants: contracts compliance declarative metadata only docs mismatch [pytest backend].
523. Failure family repo invariants: frontend navigation metadata-only docs mismatch [pytest backend].
524. Failure family repo invariants: frontend metadata layer services docs mismatch [pytest backend].
525. Failure family repo invariants: design handoff non-rendering docs mismatch [pytest backend].
526. Failure family repo invariants: Pulse future surfaces outside V1 contract docs mismatch [pytest backend].
527. Failure family repo invariants: Imperium events DB constraints hardening stability docs mismatch [pytest backend].
528. Failure family repo invariants: daily plan foundation read-only docs mismatch [pytest backend].
529. Failure family repo invariants: daily plan consolidation v2 docs mismatch [pytest backend].
530. Failure family repo invariants: frontend layout/theme/empty/actions metadata docs mismatch [pytest backend].
531. Failure family repo invariants: frontend metadata manifest exact/static docs mismatch [pytest backend].
532. Interpretation tests rouges: majorite document-contract drift, pas preuve d'echec runtime route dans extraits [pytest backend; route introspection].
533. Tests passes visibles: AI memories foundation passed [pytest backend log].
534. Tests passes visibles: AI tasks foundation passed [pytest backend log].
535. Tests passes visibles: calendar events unit passed; postgres variants skipped/filtered selon log [pytest backend log].
536. Tests passes visibles: decision framework passed [pytest backend log].
537. Tests passes visibles: dashboard foundation/contracts passed [pytest backend log].
538. Tests passes visibles: mission backlog/decision/completion guardrails passed [pytest backend log].
539. Tests passes visibles: Path foundation/router/today/stats/detail passed [pytest backend log].
540. Tests passes visibles: Pulse foundation/today/stats passed [pytest backend log].
541. Tests passes visibles: Vault summaries/transactions/reversals passed [pytest backend log].
542. Tests passes visibles: Qwen adapter passed [pytest backend log].
543. Tests passes visibles: weekly review conversation/idempotency passed [pytest backend log].
544. Skips backend: 9 skipped, details non tous affiches dans output tronque [pytest backend].
545. Orchestrator tests: 227 passed, no failure [pytest orchestrator].

## 14. Etat flags et modes
546. Backend `QWEN_ENABLED` default false [config.py:1295].
547. Backend `QWEN_DRY_RUN` default true [config.py:1299].
548. Backend `QWEN_MODEL` default `qwen2.5:7b-instruct` [config.py:1297].
549. Backend `QWEN_BASE_URL` default null [config.py:1296].
550. Backend `N8N_DRY_RUN` default true [config.py:1291].
551. Backend `N8N_BASE_URL` default null [config.py:1288].
552. Backend `N8N_WEBHOOK_SECRET` default null [config.py:1289].
553. Backend `WR_N8N_QWEN_DRY_RUN_WEBHOOK_PATH` default `imperium/wr/interactive-start-qwen-dry-run` [config.py:1292].
554. Backend `WR_N8N_ANSWERS_INTEGRATE_WEBHOOK_PATH` default `imperium/wr/answers-integrate-qwen-dry-run` [config.py:1293].
555. Docker compose passes `QWEN_ENABLED`, `QWEN_BASE_URL`, `QWEN_MODEL`, `QWEN_DRY_RUN` [docker-compose.imperium.yml:22-26].
556. Docker compose passes `N8N_DRY_RUN`, `N8N_BASE_URL`, `N8N_WEBHOOK_SECRET` [docker-compose.imperium.yml:27-29].
557. Docker compose requires `DATABASE_URL` from deployment env [docker-compose.imperium.yml:12].
558. Docker compose requires `INTERNAL_WEBHOOK_SECRET` from deployment env [docker-compose.imperium.yml:18].
559. Startup validates JWT secret not placeholder and length >=32 [config.py:1305-1322].
560. Startup validates internal webhook secret not placeholder and length >=32 [config.py:1305-1322].
561. Startup validates n8n webhook secret if provided [config.py:1313-1314].
562. Orchestrator default model alias `openai_fast` [state.py:160-162].
563. Orchestrator default auth mode `subscription` [state.py:173-176].
564. Orchestrator auth modes allowed: `subscription`, `api`; old `plus` normalizes to subscription [state.py:136-146].
565. Orchestrator default repo target `backend` [state.py:178-180].
566. Orchestrator design mode pending fields exist for `imperium/vault/vector/pulse/path` [state.py:249-255].
567. Orchestrator single active process field exists [state.py:268-270].
568. Orchestrator OpenAI Fast maps to `gpt-5.4-mini` [model_routing.py:31-38].
569. Orchestrator OpenAI Strong maps to `gpt-5.5` [model_routing.py:39-45].
570. Orchestrator Claude Audit maps to `opus` [model_routing.py:46-52].
571. Orchestrator Gemini maps to `google/gemini-flash-1.5` [model_routing.py:60-65].
572. Orchestrator Qwen maps to OpenRouter `qwen/qwen-2.5-72b-instruct` [model_routing.py:67-72].
573. Flag `real_ai_enabled`: not found by exact name in backend/orchestrator scan [rg real_ai_enabled].
574. Flag `embeddings_enabled`: schema health exposes false by default [schemas/ai.py from earlier rg].
575. Flag `runner_enabled`: not found by exact name in backend/orchestrator scan [rg runner_enabled].

## 15. Couverture docs par priorite
576. Doc 00 Vision: present [rg --files docs_master].
577. Doc 01 Signal Variables: present, headings include global/time/location/device/app variables [rg headings].
578. Doc 02 AI Routing Policy: present but marked DEPRECATED [rg headings].
579. Doc 03 Model Strategy: present but marked DEPRECATED [rg headings].
580. Doc 04 MVP Backend Contracts: present and tested heavily [rg headings; pytest failures].
581. Doc 05 Database Schema: present, but tests expect more contract prose than file contains now [pytest failures].
582. Doc 06 N8N Workflows: present; contains TODO secret rotation/exact endpoints in rg output [rg TODO].
583. Doc 07 Android App Responsibilities: present [rg --files docs_master].
584. Doc 08 Non-Negotiable Rules: present and central for invariants [docs 08 lines 34-328].
585. Doc 09 PGVector Memory Policy: present [rg --files docs_master].
586. Doc 10 Raw Media Retention Policy: present [rg --files docs_master].
587. Doc 11 Financial Pressure Formula: present [rg --files docs_master].
588. Doc 12 Daily Objective Period Logic: present [rg --files docs_master].
589. Doc 13 Vector MVP Phase Decision: present [rg --files docs_master].
590. Doc 14 Offline Client Authority: present [rg --files docs_master].
591. Doc 15 Service Architecture Map: present [rg --files docs_master].
592. Doc 16 AI Backend Layer Overview: present [rg --files docs_master].
593. Doc 17 Hostinger Postgres Deployment: present [rg --files docs_master].
594. Doc 18 N8N Smoke Test: present [rg --files docs_master].
595. Doc 19 Imperium API Docker Deployment: present [rg --files docs_master].
596. Doc 20 Backup Recovery Plan: present [rg --files docs_master].
597. Doc 21 DB Runtime Role Hardening: present [rg --files docs_master].
598. Doc 22 Backup Execution Layer: present [rg --files docs_master].
599. Doc 23 Refresh Token Lifecycle: present [rg --files docs_master].
600. Doc 24 Day Finished Workflow: present [rg --files docs_master].
601. Doc 25 Current Mission Workflow: present [rg --files docs_master].
602. Doc 26 Priority Rules Workflow: present [rg --files docs_master].
603. Doc 27 Vault Transactions Workflow: present [rg --files docs_master].
604. Doc 28 Daily Plan Workflow: present [rg --files docs_master].
605. Doc 29 Weekly Report Workflow: present [rg --files docs_master].
606. Doc 30 AI Routing And Scoring Policy: present [rg --files docs_master].
607. Doc 31 AI Tasks And Results Contract: present and aligned with implemented tables/routes [docs 31 headings; routes introspection].
608. Doc 32 WR Interactive Workflow: present and detailed through patches [docs 32 headings].
609. Doc 33 Vector Logic Detail: present, but implementation lag high [docs 33 headings; routes introspection].
610. Doc 34 Pulse Medical Feed AI: present, but implementation lag high [docs 34 headings; pytest failures].
611. Doc 35 Qwen Setup And Prompts: present [rg --files docs_master].
612. Doc 36 Cloud AI Prompts: present [rg --files docs_master].
613. Doc 37 Vision OCR Prompts: present [rg --files docs_master].
614. Doc 38 Vectorization Pipeline: present [rg --files docs_master].
615. Doc 39 WRS Vector Learning Loop: present [rg --files docs_master].
616. Doc 40 Pulse Logic Detail: present [rg headings].
617. Doc 41 Path Logic Detail: present [rg headings].
618. Doc 42 Vault Logic Detail: present [rg headings].
619. Doc 43 Imperium Logic Detail: present [rg headings].
620. Doc 44 Brain Unified Logic: present and central [rg headings].
621. Doc 45 N8N Responsibility Matrix: present [rg headings].
622. Doc 46 Vector Fuel Smart Tracking: present [rg --files docs_master].
623. Doc 47 WR Guided Sections: present [rg --files docs_master].
624. Doc 48 Vector Music Shaker: present [rg --files docs_master].
625. Doc 49 Path Youtube Channels: present [rg --files docs_master].
626. Doc 50 Path Dars Knowledge Base: present [rg --files docs_master].
627. Doc 51 Future Calendar: present [rg --files docs_master].
628. Doc 52 AI Decision Framework: present [rg --files docs_master].
629. Doc 53 Submissions Overlay Tasks: present but failing doc tests [pytest failures].
630. Doc 54 System Health Dashboard: present [rg --files docs_master].
631. Doc 55 Vector HUD Final Interface: present [rg --files docs_master].
632. Doc 56 Autonomous Coding Orchestrator: present [rg --files docs_master].
633. Doc 57 Vector Ride Scoring ML: present and detailed, code lag [rg headings; routes introspection].
634. Doc 58 Doc 57 Integration Patches: present [rg --files docs_master].
635. Docs 59-69 frontend/design: present; tests show doc drift mainly 04/05/63/screen sources [rg --files docs_master; pytest failures].
636. Docs 70-75 AI/memory/ops: present except 76; 75 unified memory present [rg --files docs_master].
637. Doc 77 Events Catalog: present [rg --files docs_master].
638. Doc 78: absent [rg --files docs_master].

## 16. Compression conclusion
639. Keep for frontier context: backend has many working deterministic slices; do not restart from zero [routes introspection; pytest passed families].
640. Keep for frontier context: CI is currently red from doc-contract drift; fix docs before architecture branching [pytest backend].
641. Keep for frontier context: WR is the deepest implemented AI workflow surface; use it as reference pattern [routes introspection; docs 31/32].
642. Keep for frontier context: Vector is the largest spec-code gap; treat as architecture decision, not bugfix [docs 33/57; no `/api/vector`].
643. Keep for frontier context: no Android code visible; backend-first remains reality, not just preference [find /opt/apps].
644. Keep for frontier context: no jobs/NOTIFY/views; "brain" orchestration is currently API/service/database plus optional n8n webhooks [rg job_definitions/NOTIFY/views].
645. Keep for frontier context: Qwen local adapter is safe/dry-run/off by default; do not assume real local AI is active [config.py; qwen.py].
646. Keep for frontier context: pgvector memory schema exists but embedding/commit path is intentionally constrained [models/ai.py; schemas/ai.py].
647. Keep for frontier context: orchestrator Tower is healthy independently of backend CI [pytest orchestrator].
648. Keep for frontier context: DB live state unknown until credentials/runtime role fixed [alembic current].
649. Final truncation note: route/table/migration inventories retained over long doc paraphrase because they compress real state better for arbitration [demande audit §0].
