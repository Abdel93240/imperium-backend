# TOOLBOX_FINDINGS — Doublons, trous, couplages, divergences

Date : 2026-07-10. Audit lecture seule. Compagnon de `TOOLBOX_CATALOG_DRAFT.md`
(les références F1-xx/F2-xx/F3-xx/D-xx pointent vers ses fiches).
Effort : S = < 1 jour de passe ; M = 1-3 jours ; L = chantier dédié.

---

## 0. QUESTIONS UTILISATEUR (regroupées, numérotées)

Un besoin de consommateur non documenté n'est pas inventé : il devient une question.

- **Q1 — vtc-companion-app.** Le repo est introuvable sur Tower (find/locate négatifs ;
  `/opt/frontend-apps/imperium` = README seul). La spec Vector (cible A) le situe sur GitHub
  Abd93240. Où le cloner, et la CI GitHub Actions APK est-elle toujours « en attente » (spec §0.1) ?
- **Q2 — The Path × trajets/geo.** Doc 41 §7-bis (sélection dynamique de mosquée « dans la
  continuité de la journée », scan geo) et §10.2 (adresse ghusl la plus proche) font de Path un
  consommateur de `toolbox.travel`/`toolbox.geo`. Quel fournisseur pour un usage religieux
  privacy `very_high` : Google (précis mais cloud, doc 41 §6.3 interdit mosquée+GPS vers modèles
  externes — un appel Directions est-il acceptable ?), matrice H3 locale (Vector §3.5), ou OSM
  local ? À trancher avant de figer l'interface de toolbox.travel.
- **Q3 — Notifications : quel canal produit ?** Le service backend est un stub vide
  (`app/services/notifications/__init__.py`). Quatre specs + Path (rappels, doc 41 §5) + Vault
  (alertes, doc 42 §10) en dépendent. Push Android ? Bannières in-app seulement (pattern WR
  existant) ? Telegram (canal dev de l'orchestrateur — à NE PAS confondre) ? La réponse
  dimensionne toolbox.notifications (T1).
- **Q4 — Échelle de pression financière.** Doc 11 (canonique, formule complète) = 0-100 à
  5 labels ; doc 42 §9 = 0-10. GAP_vault l'avait signalé sans trancher. Confirmer 0-100 ?
- **Q5 — Croyances WR vs doc 75.** La spec WR §6.3 décrémente la confiance sur « exposition non
  confirmée » (β×confidence) et introduit `status_multiplier`. Doc 75 §0/§4 grave : « confidence
  ne descend JAMAIS toute seule », pas de decay, supersession/is_active comme seuls mécanismes —
  et « décisions prises ici : ne plus y revenir ». L'exposition-non-confirmée est une OBSERVATION
  (pas du temps qui passe), donc défendable — mais c'est un amendement doctrinal du doc 75, pas un
  détail. Amender doc 75, ou contraindre la spec WR au modèle 75 ?
- **Q6 — Prières dans le Daily Orchestrator.** Doc 41 §7-bis dit que les « awareness zones » de
  prière vivent DANS le daily planning ; doc 52 §8.2 liste « Daily prayers » en engagements
  récurrents. La spec Daily ne mentionne pas les prières (G4 ne connaît que
  `is_fixed_commitment` + calendrier). Les 5 prières deviennent-elles des engagements fixes G4
  (fenêtres mobiles fournies par toolbox.prayer) dès la passe Daily, ou plus tard ?
- **Q7 — Pression → Daily.** La pression financière doit influencer l'intensité de travail
  (docs 11, 42 §15.4) mais la spec Daily ne la consomme nulle part (elle passe par le plan
  mensuel). Confirmer : la pression n'entre PAS dans la sélection quotidienne (elle reste en
  amont, dans le plan) ?
- **Q8 — Plan mensuel : doc 52 §8 vs spec WR §8.3.** Doc 52 §8 = cron lundi 05:00, high
  reasoning model, 10 catégories d'inputs. Spec WR §8.3 = régénération mensuelle via
  `plan_versions` (origin=monthly_regen), même contrat que le choc. Le second remplace-t-il le
  premier (recommandé : oui, plan_versions est plus riche et versionné) ? Patch doc 52 à prévoir.
- **Q9 — Profit hebdo (base sadaqa).** Path lit `weekly_business_profit` « from common memory »
  (doc 41 §16.2) ; la table `weekly_finance_summaries` n'existe pas (doc 42 §16 la dit existante
  à tort). Qui la crée et dans quelle passe ? (Aucune des 4 specs ne la couvre ; candidat :
  socle Toolbox ou mini-passe Vault déterministe.)
- **Q10 — Anomalies financières → docket.** W4 (spec WR) calcule des anomalies sur les rollups
  finance. Un drapeau finance (dépense anormale, dérive carburant) doit-il créer un item docket
  visible côté Vault, ou seulement côté WR ? Non documenté.
- **Q11 — Path/Vault × moteur de signaux.** La jauge de pression (Vault) et le score quotidien
  Path (doc 41 §13) rentrent naturellement dans le mécanisme bandes/baselines de F1-02. Les y
  brancher (cohérence W4/digest), ou les garder comme calculs de domaine ?
- **Q12 — Registre GBM au-delà de Vector.** `vtc_model_versions` (spec §5) est multi-`model_kind`.
  Le futur « CatBoost routeur » (pré-inventaire) et l'estimation de durée de mission apprise
  (doc 09 §Mission duration estimation) doivent-ils utiliser le MÊME registre (renommé
  `ml_model_versions`) ? Décision de nommage à prendre à la passe Vector.
- **Q13 — Emplacement canonique du catalogue.** `docs_master/78_TOOLBOX_CATALOG.md` proposé —
  mais gap_analysis_v1/00_INDEX ligne 93 réservait 78 à un catalogue ai_task. Arbitrer les numéros.

---

## 1. DOUBLONS (a)

### DBL-1 ⚠ Estimation de trajet — spécifiée DEUX fois (le doublon franc du pré-inventaire, confirmé)
- Chemins exacts : spec Daily §5 (« Trajet » : Google Maps × plancher 1,3, cache 2h, fallback
  25 km/h) vs spec Vector §3.5 (matrice H3 × multiplicateurs live, embarqué) + §4.2 (fantôme
  Google/TomTom Tower).
- Différences : profil serveur-planification (latence libre, cloud OK) vs profil embarqué-course
  (≤50 ms, zéro réseau). MAIS la Tower calibre déjà la matrice (Vector §3.5) et recycle les
  fantômes en multiplicateurs (§4.1) : tout ce qu'il faut à Daily existe côté Tower dans la spec
  Vector.
- Recommandation : **une interface unique `toolbox.travel` côté Tower** (source = matrice H3 +
  multiplicateurs live + fallback Google Directions avec plancher 1,3), consommée par Daily G4 ;
  la tablette embarque un miroir (inchangé, spec Vector). Le plancher 1,3 et le cache TTL restent
  des règles de l'interface, pas du consommateur. Effort : S (c'est un choix d'interface à écrire
  dans les patches, pas du code en plus). Impact : élevé (évite deux estimateurs divergents dont
  les verdicts se contrediraient — exactement ce que le test fantôme Vector §6 mesure).
- Attention ordre : Daily arrive AVANT Vector dans l'ordre proposé → Daily code la V0 de
  l'interface (Google+plancher+cache), Vector la RENFORCE (matrice H3, fantôme) sans en changer
  la signature. À écrire dans PATCH_DAILY et PATCH_VECTOR.

### DBL-2 Définitions de signaux — `pulse_signal_definitions` vs `wr_signal_definitions`
- Chemins : spec Pulse §3.1 ; spec WR §4 W4 (« sinon table équivalente wr_signal_definitions,
  décision consignée au mapping »).
- Recommandation : SUPPRIMER le fallback WR ; créer la table PARTAGÉE (préfixe neutre, ex.
  `signal_definitions`/`signal_values` + colonne domain) dès la passe Pulse. Effort : S.
  Impact : moyen (évite une migration pulse_→partagé + un W4 bancal).

### DBL-3 Transition/audit IA — `pulse_ai_transition`/`pulse_audit_samples` vs `ai_slot_transition`/`ai_audit_samples`
- Chemins : spec Pulse §3.9 ; spec WR §3.7 (+ §0 étape 0 : « les GÉNÉRALISER … avec migration des
  lignes et mise à jour des références Pulse. Sinon, créer directement les tables partagées »).
- Recommandation : créer DIRECTEMENT `ai_slot_transition`/`ai_audit_samples` (slots namespacés
  `pulse.*`) à la passe Pulse ; WR perd sa danse de migration. Confirme la base du pré-inventaire.
  Effort : S. Impact : moyen.

### DBL-4 Paramètres versionnés — `pulse_parameters` vs « table partagée »
- Chemins : spec Pulse §3.4 ; spec WR §13.2 ; spec Daily §4 (« table de paramètres partagée des
  specs précédentes ») ; spec Vector §8.
- Recommandation : une seule table partagée (ex. `parameters`, codes namespacés `pulse.*`,
  `df.*`, `wr.*`, `vtc.*`), créée à la passe Pulse avec le pattern append-only de la spec Pulse.
  Effort : S. Impact : élevé (4 specs en dépendent ; le réglage doc 73/C et la boucle feedback
  Daily §10 écrivent dedans).

### DBL-5 Plan mensuel — doc 52 §8 vs spec WR §3.5/§8
- Chemins : doc 52 §8 (cron lundi 05:00, prompt 10 catégories) ; spec WR §3.5 (`plan_versions`,
  origin=monthly_regen|shock_regen) + §8.3 ; doc 43 §13 annonçait `imperium_daily_plan_versions`
  (jamais codée) ; PHASE_0 D4 (`planning_daily_plan_versions` pour le plan QUOTIDIEN).
- Trois granularités se côtoient : plan 4 semaines (52 §8 / WR plan_versions), deltas hebdo
  (WR), versions du plan du JOUR (D4). Pas un doublon de code (rien n'est codé) mais un doublon
  de CONCEPTION.
- Recommandation : plan_versions (WR spec) = LE plan 4 semaines ; doc 52 §8 se fait patcher en
  renvoi ; D4 reste le versionnage du plan quotidien (autre objet). Effort : S (doc) ;
  décision → Q8. Impact : élevé (évite deux « spinal cords »).

### DBL-6 Doublons de code déjà tranchés (contexte, pas de nouvelle décision)
- `vault_transactions` vs `imperium_vault_transactions` ; `events` vs `imperium_events` ;
  `imperium_path_items` vs habits/check-ins ; `imperium_priority_rules` vs
  `imperium_user_priorities` ; `daily_plan.py` vs `daily_plans.py` — tous tranchés dans
  PHASE_0_DECISIONS TRI 1 et suivis par audit_resync. L'audit toolbox n'y ajoute rien, sauf :
  les LECTEURS legacy encore branchés (dashboard.py, weekly_report.py → vault legacy +
  path_items + priority_rules) sont des couplages cachés (C-1).

### DBL-7 Registres de rôles de modèles — dev vs produit
- Chemins : `/opt/orchestrator/model_routing.py` (alias → codex/claude/openrouter) vs doc 30 §3
  + doc 73 PART B (rôles produit).
- Verdict : PAS un doublon à unifier (mondes différents : build vs produit) mais à documenter
  dans le catalogue pour qu'aucune passe ne les confonde. Effort : S (une note). Impact : faible.

---

## 2. TROUS (b) — outils référencés par plusieurs specs que personne ne spécifie

### T1 ⚠ Notifications (confirmé — le trou pressenti par le pré-inventaire)
- Preuves : stub vide `backend/app/services/notifications/__init__.py` ; spec WR §13.7 « canaux
  de notification existants réutilisés (identifier) » → il n'y a RIEN à identifier ; consommateurs
  spec'd : Pulse §8/§11, WR §7 (rouge en semaine), Daily §9 (préemption), Vector §3.9/§4.8 ;
  consommateurs docs : Path 41 §5, Vault 42 §10.
- Recommandation : mini-spec `toolbox.notifications` AVANT les passes (canal → Q3, table
  `notifications` + statut lu/ack, API interne `notify(severity, ref, message_fr)`). Effort : M.
  Impact : élevé (le « rouge n'attend pas le rituel » est un pilier de la spec WR).

### T2 Runner de jobs (successeur n8n)
- Preuves : décision utilisateur (sortir n8n de prod) ; ~25 jobs listés par les 4 specs (fiche
  F1-14) ; chaque spec dit « UN seul mécanisme » sans le définir ; doc 44 §13.2 réservait
  LISTEN/NOTIFY à une « V2 ».
- Recommandation : mini-spec `toolbox.runner` (APScheduler + LISTEN/NOTIFY + advisory locks,
  table `job_runs` type `wr_worker_runs` généralisée, curseurs) AVANT la passe Pulse — c'est le
  mécanisme que Pulse §7 doit choisir. Effort : M. Impact : très élevé (toutes les passes).

### T3 Routeur /200 — politique complète, implémentation sans spec
- Preuves : doc 30 (politique) ; audit_resync (« pas branché au lifecycle ») ; les 4 specs
  l'attendent (`routed ≈ cloud_forced en attendant`).
- Recommandation : ce n'est PAS bloquant pour les 4 passes (le wrapper de tiers absorbe) ; écrire
  la spec d'implémentation quand le 32B est servi. Effort : L (chantier dédié, avec doc 31 §7
  queue/priorités). Impact : élevé mais différable.

### T4 Service d'embedding (serving)
- Preuves : `embeddings_enabled=False` ; `memories.py:29` « waits for the embedding service » ;
  doc 38 spécifie le pipeline mais pas le SERVING (qui lance qwen3-embedding:8b, sur quel port,
  quel wrapper HTTP) ; F10 §5-ter donne le hardware. WR (canal vectoriel, identity), Pulse
  (corpus), chatbot en dépendent.
- Recommandation : mini-spec de serving (P40, Q8, endpoint interne) + module
  `services/ai/embedding.py` (doc 38 §11) dans le socle Toolbox. Effort : M. Impact : très élevé
  (débloque D5 → commit mémoire WR → usine W2/W3).

### T5 Privacy gate — politique partout, mécanisme nulle part
- Preuves : docs 09/75 §8/38 §7-bis/44 §8/41 §17/34 §16 ; aucun module, aucune spec d'impl.
  Les assemblers whitelistés des specs Pulse/WR en sont des instances locales, pas le gate central.
- Recommandation : spécifier une primitive unique (`privacy_gate.check(payload_class, target_tier)`)
  consommée par toolbox.llm et toolbox.embeddings. Effort : M. Impact : élevé (non négociable
  doc 75 §0.6).

### T6 Utilitaires géo/H3 sans propriétaire
- Preuves : spec Vector les utilise partout (h3_res, corridors, cellules tenues) sans les isoler ;
  Path en aura besoin (Q2) ; Daily G4 a besoin d'arrondir origine/destination pour son cache.
- Recommandation : les ancrer dans `toolbox.travel` (même passe). Effort : S. Impact : moyen.

### T7 Catalogue ai_task absent
- Preuves : gap_analysis_v1/00_INDEX ligne 93 (« 78_AI_TASK_CATALOG_V1 … évite que chaque
  workflow invente ») ; GAP_infra : « catalogue task_type pas enforced ». Les 4 specs créent des
  dizaines de slots namespacés — sans registre central autre que `ai_slot_transition`.
- Recommandation : `ai_slot_transition` (F2-09) DEVIENT de fait ce registre pour les slots ;
  acter que tout slot doit y avoir une ligne (les specs le font déjà via leurs seeds). Effort : S.
  Impact : moyen.

---

## 3. COUPLAGES CACHÉS (c)

### C-1 Lecteurs legacy cross-domaine encore branchés
- `backend/app/services/imperium/dashboard.py` et `weekly_report.py` lisent `vault_transactions`
  (legacy) + `imperium_path_items` (legacy) + `imperium_priority_rules` (legacy) — sourcé
  audit_resync/00_INDEX (lignes vault/path/daily_plans). Risque réel : chiffres financiers
  incohérents selon l'écran. Effort : S-M (migrer 2 lecteurs vers ledger canonique + habits).
  Impact : élevé (W1 rollups de la spec WR liront ces mêmes sources — il faut qu'elles soient
  les canoniques AVANT la passe WR).

### C-2 La spec WR ALTER directement `ai_memories`
- Spec WR §3.4 : `ALTER TABLE ai_memories ADD COLUMN…` sur le hub mémoire fraîchement canonisé
  (migration 0032), propriété doc 05/09 (PHASE_0 « Décisions mémoire »). Étendre le hub sans
  passer par le propriétaire du schéma = couplage structurel + conflit doctrinal (Q5).
- Recommandation : la passe WR passe par une mise à jour du doc 05 + option « table compagnon
  1-1 » (déjà prévue par la spec : « ou complétée par une table compagnon si le mapping le
  recommande ») tant que Q5 n'est pas tranchée. Effort : S. Impact : élevé (intégrité du hub).

### C-3 Deux mécaniques d'extraction jumelles spécifiées séparément
- Spec WR §6 (W3 : extract + identity) et doc 72 §6 (chatbot : 3 passes + grille) décrivent la
  même capacité avec des vocabulaires différents. Si chacune est codée dans son coin, on aura
  deux extracteurs divergents écrivant dans le même hub mémoire.
- Recommandation : coder UNE librairie (F1-19) à la passe WR ; le chatbot la consommera. Effort :
  S (décision) ; Impact : élevé.

### C-4 Daily G5 lit l'état médical Pulse en direct
- Spec Daily §5 G5 lit « red flag actif advise_doctor_and_pause_training » — un état médical —
  depuis le moteur de sélection. Acceptable (lecture seule, stub loggé si absent) mais à
  contractualiser par une VUE dédiée (ex. `v_pulse_active_blocks`) plutôt qu'une lecture des
  tables rouges internes. Effort : S. Impact : moyen (frontière santé/planning, doc 40 §2).

### C-5 Le fallback « accessibilité Android » Bolt vit dans F10, pas dans la spec Vector
- F10 §5-quater : l'assistant lit « D'ABORD le texte affiché via l'accessibilité Android » ;
  la spec Vector §3.1 ne mentionne que l'empreinte audio + NotificationListener (test), et
  interdit tout accessibility service *qui agit* (§0). Lecture seule ≠ action, mais les deux
  documents doivent dire la même chose. Effort : S (aligner à la passe Vector). Impact : moyen.

---

## 4. TABLES PARTAGÉES DE FAIT NON CANONISÉES (d)

- **`events` sans lecteurs** : canonique, append-only durci, 19 types émis — et zéro consumer
  (audit 2026-07-02). Les specs en font le bus du système (usine WR s'abonne à la fin de
  session). Canoniser le CONTRAT de consommation (LISTEN/NOTIFY + curseurs `wr_worker_cursors`
  généralisés) dans toolbox.runner. Effort : inclus dans T2.
- **`wr_docket_items`** : 4 specs y écrivent/lisent (WR, Daily §10.2, Vector §4.8, Pulse P6) —
  à déclarer canonique dès sa création, nom SANS préfixe wr_ si la convention PHASE_0 doit tenir
  (`review_docket_items` ? à trancher à la passe WR). Effort : S.
- **`plan_versions`/`v_plan_current`** : consommée par WR + Daily + « le 32B terrain ». Idem.
- **profit hebdo (F2-16)** : Path (sadaqa) et W1 la lisent, personne ne la crée → Q9.
- **`imperium_calendar_events`** : Daily G4 et doc 52 §8.2 la lisent ; contrat de lecture
  (blocks_time, soft-deleted exclus — migration 0035) à écrire au moment de la passe Daily.

---

## 5. DIVERGENCES DOCS ↔ CODE / DOCS ↔ SPECS (e)

| # | divergence | références | effort | impact |
|---|---|---|---|---|
| DV-1 | Croyances : décroissance par exposition + status_multiplier (spec WR §6.3) vs « pas de decay, jamais de baisse seule » (doc 75 §0.3/§4, verrouillé) | Q5 | S (doc) | élevé |
| DV-2 | Embedding corpus Pulse `vector(4096)` (spec Pulse §3.4) vs canon 1024 (doc 75 §3, doc 38 §5.1, migration 0032) — la spec dit elle-même « vérifier ai_memories » | PATCH_PULSE | S | moyen |
| DV-3 | Tables annoncées « existantes » par les docs mais NON codées : `prayer_logs`, `fasting_logs`, `sadaqa_records` (doc 41 §20), `meals`/`workouts`/`food_stock_items` (doc 40), `weekly_finance_summaries` (doc 42 §16) | INVENTAIRE_tables §3 (revérifié migrations 0001-0037) | S (docs) | élevé (une passe qui y croit plantera son étape 0) |
| DV-4 | Pression 0-10 (doc 42 §9) vs 0-100 (doc 11, canonique) | Q4 | S | moyen |
| DV-5 | Plan 4 semaines : doc 52 §8 (cron 05:00) vs spec WR plan_versions | Q8, DBL-5 | S | élevé |
| DV-6 | Modèle local : code `qwen2.5:7b-instruct` à 6 endroits (config.py:51, providers/qwen.py, WR conversation, 2 workflows n8n, test) vs 32B canonique (doc 30) et 7B « écarté définitivement » (PHASE_0 D6) | audit_resync nomenclature | S | moyen |
| DV-7 | Statut Fable 5 : doc 30 §7.8 « suspendu 2026-06-17 → fallback Opus ACTIF » vs retour du 01/07/2026 (CONCLUSIONS_test_papier, PHASE_0 note) — doc 30 pas mis à jour | doc 30 §7.8 | S | faible |
| DV-8 | Pricing seed doc 43 §17.2 : modèles retirés de la hiérarchie (haiku, opus-4.7, qwen-7b, gemini-2.5-pro) — à régénérer depuis doc 30 §3 avant de coder ai_call_logs | doc 43 §17.2 | S | faible |
| DV-9 | `INVENTAIRE_tables.md` (2026-06-30) périmé : ai_memories vectorielle (0032), events.depth (0036), calendar soft-delete (0035), wallet (0037) — le document d'inventaire de référence contredit le schéma actuel | migrations 0032-0037 | S | moyen |
| DV-10 | Doc 04 désigne `imperium_events` comme canonique (constat D2 « corriger doc 04 ») — non revérifié ligne à ligne ici : HYPOTHÈSE que la correction doc n'est pas faite (les routes code, elles, sont dépréciées — imperium.py:1275) | PHASE_0 D2 | S | moyen |
| DV-11 | Événements de préemption : spec Daily §9 cite `ghusl.required` comme « event_types listés (vérifier les types réels au doc 77) » — doc 77 range ghusl en `worship.ghusl.*` FUTUR, le code émet `path.ghusl.*` (doc 41 §5). Trois noms pour le même fait | doc 77, doc 41 §5, spec Daily §9 | S | moyen |

---

## 6. RECOMMANDATIONS D'EXTRACTION CLASSÉES (règle du second consommateur appliquée)

**R0 (avant toute passe — le socle Toolbox) :**
1. `toolbox.runner` (T2) — M — condition d'exécution des 4 passes.
2. `toolbox.notifications` mini-spec (T1) — M — le rouge WR/Pulse/Daily en dépend.
3. Tables partagées d'emblée : `ai_slot_transition`/`ai_audit_samples` (DBL-3),
   `parameters` (DBL-4), `signal_definitions` (DBL-2) — S chacune.
4. `toolbox.embeddings` serving (T4) — M — débloque D5/commit mémoire/usine.
5. Interface `toolbox.travel` v0 + geo/H3 (DBL-1, T6) — S/M.
6. Migration des lecteurs legacy (C-1) — S-M — pour que W1 lise les canoniques.

**R1 (dans les passes, en consommant le catalogue) :**
7. `toolbox.llm` wrapper unique (passe Pulse, réutilisé WR/Daily) — inclus.
8. `toolbox.extraction` unique (passe WR, consommée par chatbot ensuite) — C-3.
9. `toolbox.gbm` + registre (passe Vector ; nommage Q12).

**R2 (différables, chantiers dédiés) :**
10. `toolbox.router` /200 implémentation (T3) — L — quand le 32B est servi.
11. `toolbox.privacy_gate` (T5) — M — avant tout appel cloud réel (peut suivre le socle).
12. `toolbox.ingestion` (doc 70) — L — chantier propre.
13. `toolbox.prayer` (F1-16) — M-L — passe Path dédiée (déterministe-EXACT, hors des 4 specs).
14. `toolbox.pressure` + `upcoming_expenses` + profit hebdo (F1-17, F2-15/16) — M — mini-passe
    Vault déterministe (GAP_vault : tout codable sans GPU) ; Q9 en dépend.

**ATTEND (dormants D-01…D-10)** : ne rien extraire tant qu'un second domaine ne le réclame pas.
