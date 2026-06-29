# Synthese strategique Codex - campagne gap V1

Date: 2026-06-29  
Portee: lecture de `gap_analysis_v1/` et des audits `audit_resync/`. Aucun code runtime modifie.

## Position generale

La campagne ne dit pas "il manque des features". Elle dit surtout que le backend a deja plusieurs fondations utiles, mais qu'elles ne parlent pas encore la meme langue.

Le risque V1 n'est pas de manquer un ecran, une recommandation IA ou une table secondaire. Le risque est de coder des modules metier qui emettent des signaux impossibles a consommer proprement par Imperium, ou de brancher l'IA sur une memoire et des events deja divergents.

La priorite strategique est donc:

1. unifier le socle transversal;
2. rendre Imperium capable de recevoir/arbitrer;
3. coder les briques deterministes metier qui alimentent ce socle;
4. brancher seulement ensuite les cerveaux IA.

## 1. Ordre de construction V1 recommande

### 0. Phase de verrouillage avant code lourd

Avant de coder des chantiers larges, il faut trancher quelques contrats, sinon chaque module va prolonger la divergence existante:

- journal d'events canonique: probablement `events`, car il porte l'enveloppe complete et recoit deja les vrais events metier;
- format canonique des events: dotted partout, par exemple `vault.pressure.spike`, pas snake_case pour une partie du systeme;
- proprietaire du schema: soit `docs_master/05_DATABASE_SCHEMA.md` devient un vrai dictionnaire colonne par colonne, soit chaque doc metier est explicitement proprietaire de ses tables;
- contrat daily plan: snapshot read-only, plan persistant, ou living plan versionne;
- strategie transitoire memoire: bloquer les commits non conformes ou autoriser un mode `text_only` documente, mais ne pas continuer silencieusement le schema actuel;
- alias de modeles: utiliser des roles stables (`local_router`, `high_reasoning`, etc.) plutot que figer `qwen2.5:7b-instruct` / `opus` dans les contrats metier.

Ce n'est pas du polish documentaire. Ce sont les decisions qui evitent de coder deux fois le meme backend.

### 1. Socle events canonique + catalogue d'events

Oui, le socle events doit venir avant les consumers Imperium.

Raison: Vault, Path, Pulse, Vector et WR sont censes "parler" au cerveau. Aujourd'hui le code contient deux journaux incompatibles:

- `events`: enveloppe riche, dotted, vraie emission metier;
- `imperium_events`: enveloppe reduite, snake_case, quasi pas utilisee par les services metier.

Tant que ce choix n'est pas tranche, chaque handoff sera fragile. Le premier chantier runtime doit donc fixer:

- un seul point d'entree recommande;
- un catalogue `event_type -> payload minimal -> privacy_level -> consumer -> effet autorise`;
- idempotency/replay uniformes;
- emission des events manquants importants, par exemple `ai.result.stored` et les events du ledger Vault canonique.

### 2. `ai_memories` canonique avant toute acceleration IA

Oui, `ai_memories` doit etre corrige avant de brancher les cerveaux IA.

Raison: ce n'est pas une feature absente, c'est une dette active. WR commit deja vers `ai_memories`, mais sans `embedding`, sans `privacy_level`, sans `source_table/source_id`, sans `memory_type`, avec un schema WR-specifique.

Si on branche WR intelligent, chatbot, daily advice ou retrieval dessus maintenant, on industrialise des souvenirs mal formes. L'ordre correct:

1. schema canonique `ai_memories` compatible docs 75/09;
2. privacy gate obligatoire;
3. strategie embedding ou mode transitoire explicite;
4. rebranchement du commit WR;
5. ensuite seulement memory candidates cross-module.

### 3. `ai_tasks` / resultats / apply contracts

Ce chantier vient juste apres events/memoire, avant les workflows IA reels.

Le code a une bonne fondation: `ai_tasks`, `ai_results`, callbacks HMAC, validations explicites, Qwen dry-run. Mais il manque ce qui empeche le systeme de devenir une collection de workflows n8n ad hoc:

- catalogue strict des `task_type`;
- mapping `task_type -> result_type -> validation -> apply`;
- queue/priorite interactive/background;
- statut `postponed` et claim interne atomique;
- routage `/200` persiste ou choix explicite de garder `router_decision` JSONB comme contrat V1;
- separation claire entre "resultat accepte" et "effet metier applique".

Sans contrats `apply`, l'IA reste une boite a propositions. Avec des `apply` mal cadres, elle peut modifier la realite sans garde-fou.

### 4. Imperium fondation deterministe: living plan, hooks, mission lifecycle

Imperium doit etre remis au centre avant de multiplier les signaux sortants des autres apps.

Chantier a coder:

- contrat unique du daily/living plan;
- `imperium_daily_plan_versions`;
- `imperium_replan_events`;
- morning check-in/start day;
- mission lifecycle complet;
- garde "une seule mission active" sur toutes les surfaces, pas seulement le snapshot moderne;
- decisions/history read models minimaux.

Raison: les autres modules ne sont pas le cerveau. S'ils emettent `path.ghusl.required`, `vault.pressure.spike`, `pulse.workout.skipped` ou `vector.smart_fuel.requested`, Imperium doit avoir un endroit stable pour recevoir, debouncer, expliquer, proposer et versionner.

### 5. Vault deterministe: ledger canonique, realite financiere, pression

Vault est a coder tot parce qu'il nourrit Imperium, Path et Vector.

Ordre interne conseille:

1. debrancher le double ledger ou consacrer `imperium_vault_transactions`;
2. ajouter le livre `business/personal`;
3. wallet snapshots manuels;
4. recurring/upcoming expenses;
5. pressure score 0-100 avec explications;
6. daily targets;
7. weekly business profit comme base sadaqa;
8. events/read models pour Imperium et Path.

Raison: la pression financiere est deterministe, codable maintenant, et centrale pour la decision "quoi faire maintenant". Mais elle depend d'abord d'un ledger unique et d'un vrai profit business.

### 6. Path deterministe exact: prieres, jeune, sadaqa, ghusl

Path doit etre decoupe entre noyau religieux exact et IA/recommandations.

Ordre interne conseille:

1. events/idempotency/offline Path;
2. prayer marking des 5 prieres;
3. fasting logs et signal `fasting_active`;
4. sadaqa state + donations + handoff Vault;
5. ghusl required + addresses, sans replan IA au debut;
6. adhkar tactile counters;
7. Quran progression;
8. Hijri/Qibla/prayer times avec sources validees.

Raison: techniquement beaucoup de Path est deterministe, mais le religieux deterministe doit etre exact, pas seulement fonctionnel. MAWAQIT/fallback, Hijri et Qibla ne doivent pas etre codes comme de simples helpers approximatifs.

### 7. Pulse deterministe simple, medical plus tard

Pulse doit rester pratique. Le premier livrable ne doit pas absorber tout le dossier medical.

Ordre interne conseille:

1. hydration logs avec contraintes fasting lues depuis Path;
2. food stock CRUD + expiry alerts;
3. meal manual confirmation/macros sans estimation IA obligatoire;
4. decrements stock/eau idempotents;
5. workouts manuels plan/log/status;
6. body snapshots numeric et pain logs seulement apres cadre privacy explicite;
7. medical documents/rules apres consentement, retention, chiffrement et routage sante.

Raison: la doc Pulse V1 est trop large pour un premier livrable. Le noyau utile maintenant est le tracking simple et exploitable par Imperium.

### 8. Weekly Review plomberie avant cerveau

WR est avance cote conversation, mais doit etre remis proprement dans le socle.

Chantiers codables maintenant:

- centraliser la vraie state machine autour des sessions, ou documenter clairement la couche readiness/banner;
- faire respecter mardi 20h Europe/Paris cote backend ou acter officiellement que c'est le scheduler;
- agregations/pre-calculs factuels avant IA;
- trail de versions des regles revisees;
- rebrancher le commit memoire apres correction `ai_memories`;
- durcir les fallback memory candidates.

Raison: WR peut produire des apprentissages tres puissants, mais seulement si la memoire et les contrats `apply` sont propres.

### 9. Imperium consumer cross-module minimal

Apres les events canoniques et les premiers signaux Vault/Path/Pulse, coder les consumers Imperium minimaux:

- `path.ghusl.required` -> replan event immediat;
- `vault.pressure.spike` -> replan si impact objectif journalier;
- `pulse.workout.skipped` -> replan si central au plan;
- `vector.smart_fuel.requested` -> replan partiel;
- `wr.validated` -> memory/rule update controle.

Raison: c'est le moment ou les modules cessent d'etre des tables isolees. C'est aussi le test reel de la vision "backend brain".

### 10. Vector CPU/VPS en chantier separe, apres matrice recurrence x impact

Vector ne doit pas suivre une priorisation "facile d'abord". La decision validee dit que le critere est recurrence x impact, pas complexite.

Codable maintenant sans GPU:

- contexte permanent sur VPS;
- Valhalla local;
- pipeline de features;
- CatBoost CPU;
- logs de sessions;
- handoff income/fuel vers Vault;
- events vers Imperium.

Mais avant un backlog classique, il faut finir la matrice des variables VTC. La doc `DECISIONS_vector_discussion.md` est tronquee au piege ML des variables confondantes; ne pas inventer la suite.

### 11. Cerveaux IA reels apres socle et GPU

A reporter apres socle stable et modele operationnel:

- Imperium morning plan intelligent;
- day replan IA;
- WR questions/reflexions/audits high reasoning;
- Pulse meal estimate/recommendations/medical extraction;
- Path routine adjustment/sadaqa strategy;
- retrieval semantique reel;
- chatbot actionnable complet.

Le dry-run et les contrats peuvent etre codes maintenant. Les decisions autonomes ou quasi-autonomes attendent le socle, pas seulement le GPU.

## 2. Chemin critique architectural

### 1. Event store unique + event catalog + consumers

Sans ca, tout le reste reste orphelin. Les modules peuvent ecrire des signaux, mais Imperium ne les ecoute pas.

Blocage concret: Path ghusl, Vault pressure, Pulse skipped workout, Vector smart fuel, WR validated.

### 2. `ai_memories` canonique avec privacy gate

Sans ca, chaque commit WR et futur chatbot ajoute de la dette difficile a migrer.

Blocage concret: daily advice, WR learning loop, memory retrieval, common memory cross-module.

### 3. `ai_tasks` catalogue + routing/apply lifecycle

Sans ca, n8n et les modeles vont produire des resultats non comparables, difficiles a valider, et impossibles a appliquer proprement.

Blocage concret: tous les cerveaux IA, y compris WR, Imperium, Pulse medical, OCR/OCR precise et chatbot actionnable.

### 4. Imperium living plan + mission lifecycle + one-active guard global

Sans ca, le systeme n'a pas de centre operationnel. Les apps redeviennent des dashboards.

Blocage concret: "que dois-je faire maintenant", replan, mission failure handling, priority arbitration Path/Vault/Vector.

### 5. Vault realite financiere canonique

Sans ledger unique, business profit, pressure score et daily targets, Imperium ne peut pas arbitrer les journees VTC/finance avec realite.

Blocage concret: financial pressure, sadaqa base, Vector revenue, weekly clarity.

## 3. Codable maintenant sans GPU vs attend les modeles

### Codable maintenant

- Resync schema/docs/contracts: event store, task catalog, schema ownership.
- Events: journal canonique, dotted validation, event catalog, idempotency, consumers skeleton.
- `ai_tasks`: queue, statuses, HMAC, task catalog, fake/dry-run routing, apply contracts.
- `ai_memories`: migration schema, privacy gate, HNSW/index DB, test embeddings/fake embeddings; activation semantique reelle peut rester desactivee.
- Imperium deterministe: daily plan contract, plan versions, replan events, morning check-in, mission lifecycle, Operations projets/routines, one-active guard.
- Vault deterministe: canonical ledger cleanup, business/personal, wallet snapshots, recurring/upcoming, pressure formula, daily targets, sadaqa base.
- Path deterministe: prayer logs, fasting, sadaqa arithmetic, ghusl state, adhkar counters, Quran progression, exact prayer-time provider integration/fallback apres validation.
- Pulse deterministe: hydration, stock, manual meals/macros, stock decrements, workout logs.
- WR plomberie: state machine/readiness, timing, aggregations, reports/versioning, rebranchement memoire apres schema.
- Vector CPU: Valhalla local, CatBoost, feature store, contexte permanent, session logs, revenu/fuel handoffs.
- n8n dry-run/smoke workflows et callbacks backend, sans decision IA canonique.

### Peut etre prepare maintenant, mais pas active comme cerveau

- Embedding pipeline: interface, tests, colonnes, privacy rules. Le vrai modele embedding peut attendre.
- Whisper/faster-whisper: API/queue/upload/retention peuvent etre codes; la production fiable en voiture attend le runtime materiel ou un choix CPU assume.
- Gemini/OCR cloud: contrats et validation utilisateur peuvent etre codes; activation depend des cles, privacy gate et cout.
- Qwen router: dry-run, prompts, contrats JSON et smoke tests peuvent etre codes; routage operationnel attend le modele local stable.

### Attend les modeles / GPU / runtime IA stable

- Imperium morning plan intelligent et day replan intelligent.
- WR reflective questions, output audit high reasoning, rolling 4-week replanning.
- Pulse meal estimation, pantry scan, recommendations, medical extraction/rules feed.
- Path routine adjustment, sadaqa strategy advice, religious-sensitive IA.
- Daily AI Advice base sur WR vectorise.
- Chatbot actionnable complet avec creation/modification de projets/missions apres validation.
- Retrieval semantique reel si aucun embedding local/cloud valide n'est encore disponible.

## 4. Risques et incoherences dangereuses code vs doc

### `ai_memories` accumule deja une dette active

Le WR commit reel ecrit dans une table appelee `ai_memories`, mais pas au schema canonique. C'est le risque le plus insidieux: l'interface porte le bon nom, donc on peut croire que la memoire est prete alors qu'elle ne l'est pas.

### Deux journaux d'events concurrents

`events` et `imperium_events` sont tous deux append-only et testes, mais incompatibles. Le plus dangereux est que la doc recente pointe vers `imperium_events` alors que le vrai metier ecrit dans `events`.

### Deux ledgers Vault actifs

`vault_transactions` et `imperium_vault_transactions` coexistent. Certains lecteurs lisent encore l'ancien ledger. Cela peut produire des chiffres financiers differents selon l'ecran, ce qui est inacceptable pour The Vault.

### Daily plan bifurque

`daily_plan.py` est un snapshot moderne; `daily_plans.py` est un CRUD persistant legacy/actif. Aucun des deux n'est le living plan IA documente. Il faut trancher, sinon Imperium aura trois definitions du plan du jour.

### Doc 05 ne joue pas le role de schema owner

Plusieurs audits le confirment: missions, Vault, Path, WR, ai_tasks n'ont pas de dictionnaire schema central fiable. C'est un accelerateur de divergence.

### Le label "V1" des docs est souvent trop large

Pulse, Path et Imperium melangent fondation deterministe, IA, medical/religieux sensible, V2/V3 et vision cible. Si on code tout ce qui est etiquete V1, le MVP explose.

### Nomenclature modele obsolete dans le code

Le projet dit Qwen 2.5 7B comme router V1 dans les instructions actuelles, tandis que certains docs/audits parlent aussi de Qwen 32B et que le code contient encore des slugs concrets. Le plus important n'est pas 7B vs 32B dans ce rapport: c'est d'arreter de graver des noms de modeles dans les schemas metier.

### WR a une vraie machine, mais pas centralisee strictement

La conversation WR est prudente, mais les transitions sont dispersees. La couche `weekly_review_state.py` est readiness/banner, pas la machine officielle. Le nom peut tromper les futures corrections.

### Path legacy encore branche

`imperium_path_items` est deprecie mais encore lu par des chemins legacy. Ce n'est pas aussi dangereux que Vault, mais ca entretient deux realites Path.

### Pulse medical est securise par absence, pas par cadre implemente

Aujourd'hui il n'y a pas de fuite medicale parce qu'il n'y a pas de medical. Cela ne suffit pas pour coder documents medicaux, pain logs interpretes ou health specialist. Il faut consentement, retention, redaction, chiffrement et validation utilisateur avant activation.

### Vector: attention aux variables confondantes

La decision Vector rappelle que le ML peut apprendre de mauvaises causes si une variable recurrente/impactante manque. Pour Vector, repousser l'evenementiel en V2 parce que c'est complexe peut degrader le modele V1.

## 5. Desaccords et reclassements recommandes

### Desaccord 1: ne pas traiter "V1 documente" comme "premier livrable"

Je ne suivrais pas les docs Pulse/Path/Imperium comme un backlog V1 lineaire. Elles decrivent souvent la vision cible. Le vrai V1 livrable doit etre:

- deterministe;
- testable;
- relié au socle;
- utile en conduite/quotidien;
- sans IA canonique tant que le routage/memoire ne sont pas stables.

### Desaccord 2: Medical documents Pulse ne devraient pas etre V1 operationnel

Meme si doc 34 parle V1, je le classerais apres le noyau Pulse deterministe. Le risque privacy/medical est trop haut pour le mettre avant hydration/stock/workouts simples.

### Desaccord 3: Daily AI Advice ne doit pas etre branche avant memoire WR propre

Un conseil quotidien base sur une memoire WR non conforme donnera une impression de cerveau alors que la source d'apprentissage est fragile.

### Desaccord 4: Vector ne doit pas repousser les variables a fort impact sous pretexte de complexite

Ici je suis d'accord avec la decision Vector, mais en desaccord avec tout classement V1/V2 fonde sur difficulte technique. Pour Vector, "complexe mais recurrent et rentable" peut etre V1.

### Desaccord 5: Monthly rolling plan est strategique, mais pas avant le living plan journalier

Le monthly rolling plan est probablement important pour la vision long terme. Mais s'il arrive avant mission lifecycle, replan events, WR memory propre et daily plan versionne, il restera theorique. Je le mettrais en V1.5 ou juste apres le socle Imperium, pas avant.

### Desaccord 6: ne pas coder plus de producers avant d'avoir des consumers

Ajouter des events sortants dans tous les modules sans consumer Imperium serait une fausse avance. Le bon ordre est: event store + catalogue, puis producers et consumers en binomes.

## Conclusion operationnelle

Le chemin le plus court vers un V1 fidele n'est pas de finir une app verticalement. C'est de rendre le cerveau capable d'entendre et d'arbitrer.

Ordre strict:

1. contrat events/memoire/ai_tasks;
2. Imperium living plan deterministe;
3. Vault finance reelle;
4. Path/Pulse noyaux deterministes;
5. WR plomberie propre;
6. consumers cross-module Imperium;
7. Vector CPU/VPS selon recurrence x impact;
8. IA reelle quand GPU/runtime et privacy gates sont prets.

Tout ce qui saute directement a l'IA avant ces etapes risque de produire une demo impressionnante mais pas un systeme personnel fiable.
