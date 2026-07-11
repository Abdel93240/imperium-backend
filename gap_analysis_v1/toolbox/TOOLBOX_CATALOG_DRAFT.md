# TOOLBOX_CATALOG_DRAFT — Inventaire des outils du système et de leurs consommateurs

Date : 2026-07-10. Audit lecture seule (Claude Code / Fable 5, Tower).
Statut : BROUILLON du futur `TOOLBOX_CATALOG.md` canonique — à valider par l'utilisateur avant promotion.
Corpus lu : docs_master/ (dont 30, 40, 41, 42, 43, 44, 52, 75, 77, 11, 38, 09, 70, 72, 73, F10),
gap_analysis_v1/ (PHASE_0, DECISIONS_events, CONCEPTION_chainage_V2, CONCLUSIONS_test_papier,
INVENTAIRE_tables, GAP_*), audit_resync/, les 4 specs one-pass (`/tmp/incoming_docs/`), le code réel
(`/opt/imperium-backend/backend`, `/opt/orchestrator`), les migrations Alembic 0001→0037, les exports
n8n sur disque (`ops/n8n/workflows/`).

## RÉPONSE CHIFFRÉE

**Le système compte 55 outils : 25 en F1 (dont 5 codés, 15 spécifiés, 4 manquants, 1 dupliqué franc),
17 en F2 (dont 8 codées, 7 spécifiées, 2 manquantes), 13 en F3 (dont 1 servi en production, 12
spécifiés non déployés), plus 10 dormants** (candidats mono-consommateur, règle du second
consommateur : ATTEND). Chaque nombre est traçable aux fiches ci-dessous (F1-01…F1-25,
F2-01…F2-17, F3-01…F3-13, D-01…D-10).

## LIMITES DE L'AUDIT (à lire avant les fiches)

1. **Postgres réel inaccessible depuis Tower.** La base `imperium_core` de production vit sur le VPS
   Hostinger (doc F10 §4) ; le VPS n'est pas dans le réseau Tailscale visible (`tailscale status` :
   tower, iphone, tablette, thomson) et aucun credential n'est sur disque. Le Postgres local de Tower
   ne contient que `orchestrator_dev` (vérifié via `/opt/orchestrator/.env`). Le « schéma réel » est
   donc reconstruit depuis `backend/alembic/versions/` (0001→0037), qui est la source déployée.
   HYPOTHÈSE : toutes les migrations sont appliquées en prod (le déploiement passe par Alembic,
   doc 19). Toute table partagée non couverte par une migration est traitée comme inexistante.
2. **Instance n8n vivante inaccessible** (elle tourne sur le VPS, `N8N_BASE_URL` vide sur Tower).
   L'inventaire n8n (livrable N8N_INVENTORY.md) se fonde sur les 3 exports JSON de
   `ops/n8n/workflows/` + docs 06/18/32/45. Dates de dernier run : non vérifiables → HYPOTHÈSE.
3. **`vtc-companion-app` introuvable sur Tower** (find/locate négatifs sur /opt, /home, /srv ;
   `/opt/frontend-apps/imperium` ne contient qu'un README). La spec Vector le situe sur GitHub
   (Abd93240). → QUESTION UTILISATEUR Q1 (voir TOOLBOX_FINDINGS.md).
4. L'inventaire de tables `gap_analysis_v1/INVENTAIRE_tables.md` (2026-06-30) est **périmé** sur
   4 points, corrigés ici depuis les migrations : `ai_memories` recréée au schéma vectoriel canonique
   (migration `20260705_0032`, vector(1024), privacy_level, source_domain), `events.depth` ajouté
   (`20260707_0036`), calendar soft-delete (`20260707_0035`), colonne `wallet` sur
   `imperium_vault_transactions` (`20260710_0037`).

---

# FAMILLE F1 — LIBRAIRIES / SERVICES DE CODE

### F1-01 `toolbox.travel` — estimation de trajet ⚠ LE doublon franc
- description : durée/coût de déplacement A→B (temps réel + attendu par créneau).
- famille : F1
- vit_aujourd_hui : **MANQUANT** (greps `haversine|h3|google.?maps|travel_time|distance_km|osrm|valhalla|graphhopper` = zéro résultat dans `backend/app/`). Spécifié DEUX fois :
  - spec Daily Orchestrator §5 (porte G4 + « Trajet ») : Google Maps API × `P:gmaps_multiplier` plancher dur 1,3, cache (origine arrondie, destination arrondie, tranche horaire) TTL 2h, fallback `distance_km / 25 km/h × 1,3` ;
  - spec VTC Vector §3.5 (estimateur local embarqué : matrice H3 cellule×heure×type-de-jour × multiplicateurs live, ≤50 ms hors-ligne) + §4.2 (fantôme Google/TomTom asynchrone côté Tower, recyclé en multiplicateurs §4.1).
- consommateurs_actuels : aucun (rien de codé).
- consommateurs_prevus_par_specs : Daily (G4 temps, §7 départage moindre trajet), Vector (scoreur §3.6, « Où je vais » §3.10, matrice §3.5, fantôme §4.2).
- consommateurs_probables_non_documentés :
  - **The Path** — doc 41 §7-bis : sélection dynamique de mosquée « position dans la continuité de la journée » (scan geo + trajets) ; doc 41 §10.2 : replan ghusl « nearest registered ghusl address ». → QUESTION UTILISATEUR Q2 (fournisseur geo pour données religieuses very_high).
  - Vector HUD doc 55 §9.5/9.6 (overlay mosquées, raccourcis avec gain de temps estimé) — V6+, futur.
  - Doc 52 §9 génération du plan quotidien (enchaînement de missions avec lieux).
- doublons : les deux specs ci-dessus. Différences : Daily = service Tower, temps réel large, appel API cloud accepté, précision « verdict de planification » ; Vector = embarqué tablette, zéro réseau, <50 ms, précision « verdict binaire à seuil ». Ce sont deux PROFILS du même outil, pas deux outils : la matrice H3 calibrée par la Tower (Vector §3.5) et le fantôme Google (§4.2) peuvent servir le G4 de Daily (qui n'a pas la contrainte 900 ms) via une interface unique côté Tower ; la tablette embarque un miroir.
- seconde_regle_consommateur : PASSE (Daily + Vector spécifiés ; Path probable).
- statut : **dupliqué** (spécifié 2×, non codé).

### F1-02 `toolbox.signals` — moteur de signaux génériques
- description : définitions versionnées + valeurs horodatées + baselines glissantes (médiane 28j ± MAD) + bandes green/yellow/orange/red + drapeaux + staleness.
- famille : F1 (avec F2-13 pour les tables)
- vit_aujourd_hui : spécifié non codé — spec Pulse §3.1 (`pulse_signal_definitions`/`pulse_signal_values`/`v_pulse_board_current`, 32 signaux seedés §4) ; spec WR §4 W4 : « réutiliser le mécanisme `pulse_signal_definitions` si présent, sinon table équivalente `wr_signal_definitions` » — doublon latent explicite. Dictionnaire historique : doc 01.
- consommateurs_actuels : aucun.
- consommateurs_prevus_par_specs : Pulse (board, sentinelle, interprète), WR (W4 anomalies ecosystem, variance inexpliquée → digest), Vector (§4.8 dérive « au-delà de sa bande » → docket), Daily (indirect : signaux Pulse via porte G5).
- consommateurs_probables_non_documentés : Vault — la pression financière est « une jauge visuelle » (doc 77 « Ce qui n'est pas un event ») : c'est exactement un signal à bandes ; The Path — score quotidien §13 et assiduité (bandes) → QUESTION Q11.
- doublons : `pulse_signal_definitions` vs `wr_signal_definitions` (fallback WR) — à tuer par ordre d'exécution + patch (voir PATCH_WR).
- seconde_regle_consommateur : PASSE (Pulse + WR + Vector).
- statut : spécifié.

### F1-03 `toolbox.llm` — client LLM local contraint + wrapper de tiers
- description : appel Qwen local temp 0, sortie contrainte GBNF/guided decoding par JSON Schema, retry-avec-erreur, fallback déterministe, dry-run loggé (`real_ai_enabled=False`), tiers `local_default|cloud_forced|routed`.
- famille : F1
- vit_aujourd_hui : partiel — `backend/app/services/ai/providers/qwen.py` (adapter dry-run, doc 30 Patch 2E) ; MAIS modèle en dur `qwen2.5:7b-instruct` (`app/core/config.py:51`, 7B écarté définitivement par PHASE_0 D6), pas de GBNF, pas de wrapper de tiers. Spécifié complet : spec Pulse §6/§13 ; spec WR §15.3 « réutiliser le wrapper Pulse si présent » ; spec Daily §8.
- consommateurs_actuels : WR conversation (dry-run, `weekly_review_conversation.py`), smoke endpoint.
- consommateurs_prevus_par_specs : tous les slots LLM des specs Pulse (interpreter, p1..p10), WR (wr.probe_gen, wr.pair_verdict, wr.identity…), Daily (daily.disruption_classify, daily.conflict_arbitrate). Vector : AUCUN (zéro LLM, gravé spec §0).
- consommateurs_probables_non_documentés : chatbot doc 72, conseils quotidiens doc 43 §12.3.
- doublons : non, mais trois specs re-décrivent le même wrapper — à construire UNE fois (passe Pulse) puis référencer.
- seconde_regle_consommateur : PASSE.
- statut : spécifié (embryon codé).

### F1-04 `toolbox.router` — routage /200 (doc 30)
- description : scoring de difficulté /200 (7 critères §5.2), seuils dynamiques, règles statiques §7, mécanique critique 180+ (re-score GPT-5.5 → orchestration Opus → circuit breaker), escalade/downgrade auto.
- famille : F1
- vit_aujourd_hui : politique complète = doc 30 (canonique). Code : ABSENT — audit_resync WR-c : « routage doc 30 PAS implémenté (pas de scoring /200, pas de router_decision, pas d'audit entrée/sortie) » ; ai_tasks n'a pas les colonnes routage requêtables (doc 31 §7 non codé, audit_resync ai_tasks_results).
- consommateurs_actuels : aucun.
- consommateurs_prevus_par_specs : les 4 specs y renvoient (« routed ≈ cloud_forced en attendant, le wrapper l'attend » — Pulse §18, WR §16, Daily §16) ; chatbot doc 72 §3.1 ; hooks doc 43 §3.2 ; escalades doc 30 §5.8.
- consommateurs_probables_non_documentés : —
- doublons : non.
- seconde_regle_consommateur : PASSE (tout le système).
- statut : spécifié (politique docée, implémentation sans spec dédiée → voir FINDINGS trou T3).

### F1-05 `toolbox.ocr` — services OCR (trois profils distincts)
- description : (a) OCR système VLM précis (documents/médical/PDF) ; (b) OCR Bolt dédié léger (assistant course) ; (c) OCR embarqué tablette (ML Kit, spec Vector §3.3).
- famille : F1 (modèles associés en F3-04/05)
- vit_aujourd_hui : MANQUANT côté backend (seule mention : `app/schemas/ai.py`). Propriétaire des noms concrets : doc F10 §5-quater (PaddleOCR-VL-1.6/GLM-OCR sur P40 ; PP-OCRv4 pour Bolt ; accessibilité Android lue AVANT OCR pour Bolt). Spécifié : doc 37 (prompts), doc 42 §6.3 (reçus Vault), doc 34 (documents médicaux), doc 57 §7.2 (import historique Bolt), spec Vector §3.3 (ML Kit) + §4.7 (contre-lecture P40 nocturne), spec Pulse P5 (pdftotext d'abord, vision hors périmètre V1).
- consommateurs_actuels : aucun.
- consommateurs_prevus_par_specs : Vector (templates + contre-lecture), Pulse (P5 file vision), + docs : Vault reçus, Pulse médical, import Bolt.
- consommateurs_probables_non_documentés : Knowledge Inbox doc 70 (fichiers image/PDF), The Path (« donation receipts or charity scans… OCR uses a privacy gate », doc 41 §17).
- doublons : non (trois profils volontaires, F10 les distingue) — mais le catalogue doit les nommer pour éviter qu'une passe recrée « un OCR ».
- seconde_regle_consommateur : PASSE.
- statut : spécifié.

### F1-06 `toolbox.transcription` — service de transcription audio
- description : STT local (fr + ar), audio supprimé après transcription.
- famille : F1 (modèle F3-06)
- vit_aujourd_hui : MANQUANT. Propriétaire : F10 §5-quater (faster-whisper large-v3 sur P40). Docs : 30 §3.10, 45 §10, 72 §9 (audio supprimé après transcription), 41 §11 (comptage adhkar vocal avec confiance affichée).
- consommateurs_actuels : aucun.
- consommateurs_prevus_par_specs : aucune des 4 specs ne l'utilise directement.
- consommateurs_probables_non_documentés : chatbot (voix), Path (adhkar vocal), Vault (note vocale sur don/dépense, PAT-03 « optional voice transcript » doc 41 §9.4).
- seconde_regle_consommateur : PASSE (chatbot + Path).
- statut : spécifié.

### F1-07 `toolbox.embeddings` — service d'embedding + recherche top-K
- description : embed(texts)→vector(1024) local (privacy-first), wrapper provider (doc 38 §11), recherche sémantique top-K avec deux modes (current_truth = cos×confidence ; historical = cos seul), seuil 0.35.
- famille : F1 (modèle F3-02 ; table F2-02)
- vit_aujourd_hui : schéma PRÊT, service ABSENT — migration `20260705_0032` (vector(1024) + HNSW cosine) ; `app/services/ai/memories.py:29` : « Canonical writes wait for the embedding service » ; `embeddings_enabled=False`. Aucun module `embedding.py` codé.
- consommateurs_actuels : aucun (writes WR bloqués, D5).
- consommateurs_prevus_par_specs : WR (canal vectoriel classique + sondes §5.2, identity top-K §6.2, forage P1), Pulse (corpus sheets embedding §3.4 — ⚠ spec dit `vector(4096)`, canon = 1024, voir FINDINGS DV-2), chatbot pass 2 (doc 72 §6.1).
- consommateurs_probables_non_documentés : Knowledge Inbox (doc 70 §12), doc 52 §8.2 CATEGORY 6.
- seconde_regle_consommateur : PASSE.
- statut : spécifié (schéma codé, service manquant → FINDINGS trou T4).

### F1-08 `toolbox.memory` — API mémoire (ai_memories)
- description : écriture validée d'éléments d'apprentissage, supersession, expiry, contraintes de canonicité (1024 dims, privacy_level obligatoire).
- famille : F1 (table F2-02)
- vit_aujourd_hui : CODÉ — `backend/app/services/ai/memories.py` (458 lignes : validation, 1024 dims exactes, privacy) sur le schéma canonique 0032. Écritures bloquées jusqu'au service d'embedding (D5, `WR_MEMORY_COMMIT_DISABLED_REASON`).
- consommateurs_actuels : WR memory commit (bloqué volontairement).
- consommateurs_prevus_par_specs : WR (extension croyances §3.4 — ⚠ conflit doctrinal avec doc 75, voir FINDINGS DV-1), Pulse (labels refus), Daily (W3 via WR §10.4), chatbot (doc 72 §6).
- seconde_regle_consommateur : PASSE.
- statut : existe_codé (gated).

### F1-09 `toolbox.ephemeral_store` — store vectoriel de travail éphémère
- description : primitive générique : RAG jetable par session (au plus UN store, auto-nettoyé à la création du suivant), pour tâches locales > ~20k tokens.
- famille : F1
- vit_aujourd_hui : spécifié non codé — doc 38 §7-bis (conception complète) ; règle dure de débordement : CONCLUSIONS_test_papier (« >20k → store éphémère, passes RAG »).
- consommateurs_prevus_par_specs : WR P2 (store peuplé par digest+hypothèses+forage, spec WR §9).
- consommateurs_probables_non_documentés : chatbot dense (doc 72 §9), analyse de gros documents (doc 38 §7-bis « Consumers »), exécuteur local générique.
- seconde_regle_consommateur : PASSE.
- statut : spécifié.

### F1-10 `toolbox.events` — émetteur d'events E2
- description : émission dans le journal canonique `events` avec enveloppe complète + chaînage correlation_id/causation_id/depth.
- famille : F1 (table F2-01)
- vit_aujourd_hui : CODÉ PARTIEL — `app/services/events/ingestion.py` + `app/models/event.py` (depth ajouté migration 0036, CHECK ≥1) ; 19 event_types émis par 8 services (audit du 2026-07-02). MAIS le chaînage réel n'est pas rempli : correlation_id aléatoire, causation_id vide (même audit) ; renommage dotted génériques (doc 77 « À faire côté code ») pas fait.
- consommateurs_actuels : émetteurs = missions, daily plans, day finish, path items, priorities, calendar, vault legacy. **Consommateurs = AUCUN** (journal write-only, constat structurant de l'audit events).
- consommateurs_prevus_par_specs : les 4 specs émettent (Pulse §12, WR §11, Daily §11, Vector §7) ET consomment (usine WR s'abonne à la fin de session ; W2 lit les events notables ; Daily réagit à mission.completed).
- seconde_regle_consommateur : PASSE.
- statut : existe_codé (enveloppe) / spécifié (chaînage V1 temps réel + consumers).

### F1-11 `toolbox.notifications` — notifications utilisateur ⚠ LE trou confirmé
- description : canal de notification produit (rouge docket, red flags santé, préemption, sollicitations capture surge, rappels Path).
- famille : F1
- vit_aujourd_hui : **MANQUANT** — `backend/app/services/notifications/__init__.py` = 1 ligne : « Notifications service skeleton. Business logic intentionally not implemented yet. » Aucune spec ne le définit.
- consommateurs_actuels : aucun.
- consommateurs_prevus_par_specs : Pulse (red flag ack §11, fallback_move « appliqué automatiquement avec notification » §8, P5 file vision) ; WR (« item rouge → notification en semaine » §7 ; seed §13.7 : « canaux de notification existants réutilisés (identifier) » — ils N'EXISTENT PAS) ; Daily (préemption §9 « notification immédiate + proposition ») ; Vector (§3.9 « la Tower détecte une cause candidate → notification », §4.8 dérive).
- consommateurs_probables_non_documentés : Path (path.reminder.requested doc 41 §5 ; bannières de préparation jeûne §8), Vault (alertes upcoming expenses doc 42 §10).
- doublons : l'orchestrateur (`/opt/orchestrator/telegram_bot.py`) possède un canal Telegram — mais c'est l'outillage de DEV, pas le produit. Ne pas confondre.
- seconde_regle_consommateur : PASSE (4 specs + 2 apps).
- statut : **manquant** (trou T1 des FINDINGS ; à spécifier avant les passes).

### F1-12 `toolbox.params` — store de paramètres versionnés append-only
- description : paramètres à versions (jamais d'UPDATE de valeur, superseded_by, origin, rationale, date+raison), vue « current », cache invalidé sur nouvelle version.
- famille : F1 (table F2-10)
- vit_aujourd_hui : spécifié non codé — spec Pulse §3.4 (`pulse_parameters`) ; spec WR §13.2 (« table de paramètres versionnés existante ou équivalente ») ; spec Daily §4 (« jeu de paramètres versionnés `df.*` (table de paramètres partagée des specs précédentes) ») ; spec Vector §8 (« défauts à valider, versionnés »).
- consommateurs_prevus_par_specs : les 4 (P:*, df.*, chain_*, belief_*, docket_*, h3_res, thresholds…).
- doublons : latent — Pulse crée `pulse_parameters` (préfixe domaine), les trois autres attendent une table PARTAGÉE. À trancher AVANT la passe Pulse (patch).
- seconde_regle_consommateur : PASSE.
- statut : spécifié (dupliqué latent).

### F1-13 `toolbox.audit_loop` — audit décroissant des slots IA
- description : contre-lecture cloud échantillonnée des sorties locales, agreement par slot, décroissance = décision utilisateur, dataset LoRA depuis désaccords + refus expliqués.
- famille : F1 (tables F2-09)
- vit_aujourd_hui : spécifié non codé — spec Pulse §3.9 (`pulse_ai_transition`/`pulse_audit_samples`) ; spec WR §3.7 GÉNÉRALISE en `ai_slot_transition`/`ai_audit_samples` + `v_ai_training_pairs` (avec migration des lignes Pulse si déjà créées) ; spec Daily (2 slots seedés) ; spec Vector §4.7 (même principe appliqué au capteur OCR) ; racine conceptuelle : CONCEPTION_chainage_V2 Étape 4.
- doublons : latent pulse_* vs partagé — la spec WR prévoit la danse de migration ; le pré-inventaire recommande de créer PARTAGÉ dès Pulse (confirmé par cet audit, voir PATCH_PULSE/PATCH_WR).
- seconde_regle_consommateur : PASSE (4 specs).
- statut : spécifié (dupliqué latent).

### F1-14 `toolbox.runner` — runner de jobs backend (successeur de n8n)
- description : APScheduler + LISTEN/NOTIFY + advisory locks ; crons, abonnements events, verrous, un SEUL mécanisme pour toutes les passes.
- famille : F1
- vit_aujourd_hui : **MANQUANT** — décision prise (contexte fourni par l'utilisateur : sortir n8n du chemin de production) ; aucune spec. Chaque spec dit « workflows n8n ou crons backend, au choix de l'exécuteur, mais UN seul mécanisme » (Pulse §7, WR §12, Daily §12).
- consommateurs_prevus_par_specs : ~25 jobs — Pulse (features_daily 06:45, sentinel am/pm, pre_session, runners, weekly, monthly, scientific_review, audit_weekly, metrics_rollup) ; WR (factory_on_session_end, fallback 23:30, exposure_daily, review_due_weekly, digest_on_open, audit_weekly, metrics, monthly_regen) ; Daily (scores_refresh 06:30, day_start, override_aggregation, gmaps_cache_gc) ; Vector (builders 5 min/60 min/hebdo/nocturne, entraînement, fantôme).
- seconde_regle_consommateur : PASSE.
- statut : **manquant** (trou T2 ; à spécifier avant les passes — voir EXECUTION_ORDER_PROPOSAL).

### F1-15 `toolbox.gbm` — harnais d'entraînement GBM + registre de modèles
- description : entraînement nocturne CatBoost, verrou de backtest 14 j (jamais déployer un candidat inférieur), export ONNX + hash, registre `vtc_model_versions` (multi-`model_kind`), rollback une commande, poids d'exploration.
- famille : F1 (modèles F3-08/09/10)
- vit_aujourd_hui : spécifié non codé — spec Vector §4.4/§5 (`vtc_model_versions` : acceptance|zone_eph|zone_wait|surge) ; docs 57 (3 phases d'apprentissage), 58.
- consommateurs_prevus_par_specs : Vector (4 modèles).
- consommateurs_probables_non_documentés : futur « CatBoost routeur » (candidat au routage /200 évoqué au pré-inventaire) ; durées de mission apprises (doc 09 « Mission duration estimation ») → QUESTION Q12.
- seconde_regle_consommateur : ATTEND côté formel (un seul domaine spécifié) MAIS le registre versionné multi-kind est déjà généralisant → à cataloguer comme outil, implémentation dans la passe Vector.
- statut : spécifié.

### F1-16 `toolbox.prayer` — moteur religieux temporel (prières, Hijri, Qibla)
- description : temps de prière (MAWAQIT prioritaire + cache 30 j + fallback moteur type Adhan MuslimWorldLeague/Maliki), calendrier Hijri lunaire (observation + confirmation manuelle + duplicate-date V3), Qibla. Catégorie « déterministe qui doit être EXACT » (gap_analysis_v1/00_INDEX).
- famille : F1
- vit_aujourd_hui : MANQUANT (grep `prayer|salat|mawaqit|qibla|hijri` = zéro dans `backend/app/`). Spécifié : doc 41 §6, §14, Patch 41-A (14-V3) ; tables doc 41 §20 (`path_calculated_prayer_times`, `path_registered_mosques`, `path_mawaqit_cache`) non codées.
- consommateurs_actuels : aucun.
- consommateurs_prevus_par_specs : aucune des 4 specs (angle mort confirmé).
- consommateurs_probables_non_documentés (sourcés docs) : The Path (affichage PAT-01/02) ; **Imperium planning** (awareness zones de prière créées PAR le daily planning, doc 41 §7-bis → le futur Daily Orchestrator devrait traiter les prières comme engagements, cf. QUESTION Q6) ; **Vector HUD** doc 55 §9.5 (overlay mosquées, couleur = urgence prochaine prière) ; Pulse (fenêtres suhoor/iftar lues via l'état de jeûne Path, doc 40 §15.2/41 §8) ; doc 52 §8.2 CATEGORY 8 (« Daily prayers » en engagements récurrents).
- seconde_regle_consommateur : PASSE (Path + planning + HUD).
- statut : spécifié (non couvert par les 4 passes → FINDINGS).

### F1-17 `toolbox.pressure` — moteur de pression financière
- description : score déterministe 0-100 + label + facteurs explicables + objectifs journaliers min/comfortable/optimal (formule doc 11 complète).
- famille : F1 (tables F2-15/16 associées)
- vit_aujourd_hui : MANQUANT (grep `pressure` : seul un asset SVG `vault_pressure` dans `frontend.py:627`). Formule canonique : doc 11 ; doc 42 §9 (résumé, ⚠ échelle 0-10 divergente, voir FINDINGS DV-4).
- consommateurs_actuels : aucun.
- consommateurs_prevus_par_specs : WR W1 (« rollups finance (flux, pression) », spec WR §4).
- consommateurs_probables_non_documentés (sourcés docs) : Vault (affichage + « Voir pourquoi », doc 42 §14) ; Imperium (sizing objectif quotidien, doc 42 §15.4, doc 52 §8.2 CATEGORY 2) ; Vector (urgence via le plan, PAS en direct — doc 42 §9 correction) ; Daily Orchestrator (candidat via plan, non sourcé dans la spec → QUESTION Q7).
- seconde_regle_consommateur : PASSE (Vault + Imperium + WR).
- statut : spécifié (docs) non codé — déterministe codable maintenant (GAP_vault gap n°4).

### F1-18 `toolbox.dialogue` — moteur de dialogue partagé
- description : conducteur local unique, contexte de session détenu par le backend, spécialistes consultés en coulisse, escalade par tour, un seul interlocuteur.
- famille : F1
- vit_aujourd_hui : plomberie WR codée (`weekly_review_conversation.py`, sessions/messages/états — audit_resync : machine conversationnelle V1 fonctionnelle) ; le moteur GÉNÉRIQUE (partagé WR + chatbot) n'existe pas. Spécifié : doc 30 §6, doc 72, doc 44 §6-bis.
- consommateurs_prevus_par_specs : WR P2 (mécanisme inchangé, store éphémère repeuplé).
- consommateurs_probables_non_documentés : chatbot doc 72 (même moteur, gravé doc 30 §6).
- seconde_regle_consommateur : PASSE (WR + chatbot).
- statut : spécifié (plomberie WR codée).

### F1-19 `toolbox.extraction` — extraction d'apprentissages + confrontation d'identité
- description : détection par grille éditable (types ouverts doc 09), qualification domaine/nouveauté, extraction canonique (phrase autoportante ≤240c), confrontation top-K (duplicate/reinforces/refines/contradicts/unrelated) avec effets appliqués par le code.
- famille : F1
- vit_aujourd_hui : spécifié non codé — spec WR §6 (W3 + wr.pattern_extract + wr.identity) ; doc 72 §6 (3 passes chatbot, grille éditable) ; doc 38 §6 (extractor WR).
- consommateurs_prevus_par_specs : WR (clôtures d'épisodes, exit_audit P5), Daily (§10.4 : « W3 voit chaque override comme clôture d'épisode — rien à coder ici »), Pulse (refus/explications → labels).
- consommateurs_probables_non_documentés : chatbot (doc 72 §6 — même mécanique, spécifiée séparément : à UNIFIER, voir FINDINGS C-3).
- seconde_regle_consommateur : PASSE.
- statut : spécifié.

### F1-20 `toolbox.ingestion` — Knowledge Inbox (« Nourrir l'IA »)
- description : upload fichier → rétention source TOUJOURS (pointeur abstrait NAS-ready) → analyse IA → validation/édition utilisateur → vectorisation globale sans tag d'app ; suppression réversible via chatbot (write-authority 3).
- famille : F1
- vit_aujourd_hui : spécifié non codé — doc 70 (up_to_date 2026-06-09).
- consommateurs_prevus_par_specs : aucun directement.
- consommateurs_probables_non_documentés (sourcés docs) : toutes les apps (entrée Settings → IA, doc 70 §13) ; Path invocations (doc 41 §11-bis.1 « via doc 70 ») ; dossiers projet (doc 70 : création de PROJETS V1).
- seconde_regle_consommateur : PASSE.
- statut : spécifié.

### F1-21 `toolbox.privacy_gate` — garde-fou de confidentialité
- description : filtrage par `privacy_level` de tout contenu sortant vers un cloud, minimisation/anonymisation, dégradation plutôt que fuite (very_high ne sort JAMAIS), gate sur mémoire et embeddings cloud.
- famille : F1
- vit_aujourd_hui : **MANQUANT** comme mécanisme (politique complète : docs 09 §Privacy Gate, 75 §8, 38 §7-bis, 44 §8, 41 §17, 34 §16 ; `privacy_level` existe sur `events` et `ai_memories` post-0032). Aucune implémentation de gate, aucune spec d'implémentation.
- consommateurs_prevus_par_specs : Pulse (assemblers cloud « excluent tout identifiant direct » §13), WR (whitelists assembleurs §9), toutes les sorties cloud.
- seconde_regle_consommateur : PASSE.
- statut : **manquant** (trou T5).

### F1-22 `toolbox.idempotency` — socle d'idempotence
- description : Idempotency-Key sur toutes mutations, table dédiée, replay sûr.
- famille : F1 (table F2-04)
- vit_aujourd_hui : CODÉ — `app/services/idempotency/`, table `idempotency_keys` (migration 0001), « idempotence systématique sur chaque émission » (audit events 2026-07-02).
- consommateurs_actuels : toutes les routes de mutation.
- consommateurs_prevus_par_specs : les 4 (sync Vector idempotente par uuid, workers WR, etc.).
- seconde_regle_consommateur : PASSE.
- statut : existe_codé.

### F1-23 `toolbox.geo` — utilitaires géo/H3
- description : indexation H3 (résolution paramétrée), corridors de cellules, cellule tenue ≥10 min, distances ; support de travel/zones/mosquées.
- famille : F1
- vit_aujourd_hui : MANQUANT (aucun code H3). Spécifié implicitement par la spec Vector (§3.5 corridors, §4.5 cellules tenues, h3_res=8) ; besoins Path doc 41 §7-bis (scan geo).
- seconde_regle_consommateur : PASSE (travel + zones + Path probable).
- statut : spécifié (implicite, pas de propriétaire → à ancrer dans toolbox.travel ou séparé).

### F1-24 `toolbox.scoring_mission` — service de scoring déterministe /100 (doc 52)
- description : critères A-E, coefficients ×10/8/5/4 depuis `imperium_user_priorities`, breakdown `explanation`, bucket public.
- famille : F1
- vit_aujourd_hui : **CODÉ, TESTÉ, FIDÈLE** — `backend/app/services/imperium/decision_framework.py` (751 lignes ; `COEFFICIENT_BY_POSITION`, `_IMPACT_POINTS`, `_MISSION_TYPE_POINTS`… = CONSTANTES CODE, lignes 29-94 — réponse à l'audit §0.3 de la spec Daily : PAS d'exposition réglages aujourd'hui). Meilleur module de la campagne resync.
- consommateurs_actuels : missions, dashboard, score-preview.
- consommateurs_prevus_par_specs : Daily (consomme sans modifier ; externalise les barèmes en paramètres `df.*` avec verrou de parité §4). Constats d'audit spec Daily §0 : pas de filtre de faisabilité en amont (grep `feasib` = zéro) ; dépendances = uniquement points du critère D (pas de porte topologique) ; chemin de complétion sans LLM.
- seconde_regle_consommateur : PASSE.
- statut : existe_codé.

### F1-25 `toolbox.dev_orchestrator` — outillage d'orchestration de build (système)
- description : bot Telegram de pilotage, table de routage de modèles dev (`model_routing.py` : alias → runner codex/claude/openrouter), pattern_matcher + classifieur LLM local (Qwen 3B via Ollama, `llm_classifier.py`), pipeline design/assets (asset_registry/naming/splitter, image_runner, design_review).
- famille : F1 (colonne « système » de la matrice ; HORS produit)
- vit_aujourd_hui : CODÉ — `/opt/orchestrator/` (tourne sur la machine orchestrateur, doc F10 §2).
- consommateurs_actuels : le processus de build (Codex/Claude Code), le pipeline design F12.
- consommateurs_prevus_par_specs : les 4 specs « commit/push via l'orchestrateur ».
- doublons : `model_routing.py` (dev) vs doc 30 §3/doc 73 B (produit) — deux registres de rôles → assumé (mondes différents), à documenter pour éviter la confusion.
- seconde_regle_consommateur : PASSE (système).
- statut : existe_codé.

---

# FAMILLE F2 — TABLES / VUES CANONIQUES PARTAGÉES

### F2-01 `events` (+ depth) — journal canonique post-E3
- vit : migration 0001 + 0011 + **0036 (depth)** ; `app/models/event.py`. `imperium_events` DÉPRÉCIÉE (D2/E3 ; routes marquées deprecated, `imperium.py:1275`).
- consommateurs actuels : 8 services émetteurs ; **zéro lecteur** (write-only, audit 2026-07-02).
- prévus par specs : les 4 (émission + abonnements usine WR, W2, Daily, Vector).
- statut : existe_codé. C'est LA table events canonique que les specs doivent utiliser (les specs disent « identifier la table active » : c'est `events`).

### F2-02 `ai_memories` + `v_memories_active` (vue à venir)
- vit : migration **20260705_0032** (schéma vectoriel unifié : vector(1024), embedding_model, memory_type, learning_element_type, source_domain, source_table/id, confidence, privacy_level, is_active, supersedes…). Conforme doc 75/09/PHASE_0.
- consommateurs actuels : commit WR (bloqué D5).
- prévus : WR (croyances §3.4 + vue v_memories_active), Conseil IA quotidien, chatbot, Pulse (labels).
- statut : existe_codé (extension croyances spécifiée ; conflit doctrinal DV-1 à arbitrer).

### F2-03 `ai_tasks` / `ai_results` / `ai_result_validations`
- vit : migration 0012 ; `app/services/ai/tasks.py` (idempotence, HMAC callbacks). Contrat doc 31.
- consommateurs : WR (dry-run), n8n bridge. Prévus : tout travail IA.
- statut : existe_codé (colonnes routage doc 31 §7 NON codées ; queue à priorités absente — audit_resync).

### F2-04 `idempotency_keys` — statut : existe_codé (0001). Consommée partout.

### F2-05 `imperium_user_priorities` — hiérarchie de domaines
- vit : migration 0019 ; lecture via `get_canonical_priority_order` (decision_framework.py:165). Legacy `imperium_priority_rules` en compat (410 Gone sur write).
- consommateurs : scoring /100, doc 52 §3A (ordre de traitement multi-domaines), Daily (ordre intra-obligatoires).
- statut : existe_codé. (Renommage cible `decision_user_priorities`, PHASE_0.)

### F2-06 `imperium_mission_scores` — registre de scores persistés
- vit : migration 0019. Consommateurs : dashboard ; prévu : Daily (refresh cron matinal §4.6).
- statut : existe_codé.

### F2-07 `imperium_calendar_events` — fondation calendrier
- vit : migration 0022 + **0035 (soft delete + traçabilité)**. Doc 51 Patch 7H. Le SEUL module (a) conforme de la campagne resync.
- consommateurs : calendar service ; prévus : Daily G4 (engagements fixes « + événements calendrier identifiés à l'audit »), doc 52 §8.2 CATEGORY 3, WR digest.
- statut : existe_codé.

### F2-08 ledger finance canonique `imperium_vault_transactions`
- vit : migrations 0024/0025/0026 + **0033 (guards append-only)** + **0037 (wallet)**. PHASE_0 TRI 1 : canonique (cible `finance_transactions`) ; `vault_transactions` déprécié mais ENCORE LU par `dashboard.py` et `weekly_report.py` (risque chiffres incohérents, audit_resync).
- consommateurs : Vault ; prévus : Path (base sadaqa), WR W1 (rollups finance), pression (F1-17).
- statut : existe_codé (lecteurs legacy à migrer).

### F2-09 `ai_slot_transition` + `ai_audit_samples` + vue `v_ai_training_pairs`
- vit : spécifiées (spec WR §3.7, généralisation du pattern Pulse §3.9). MANQUANTES en code.
- consommateurs prévus : Pulse (tous slots), WR (10 slots §10), Daily (2 slots), Vector (audit OCR §4.7, même esprit).
- statut : spécifié — À CRÉER PARTAGÉES D'EMBLÉE (recommandation R1, FINDINGS).

### F2-10 store de paramètres versionnés partagé
- vit : spécifié 4× (cf. F1-12). MANQUANT.
- statut : spécifié (dupliqué latent) — à créer PARTAGÉ dès la première passe (R2).

### F2-11 `wr_docket_items` — le docket
- vit : spécifiée (spec WR §3.1). MANQUANTE.
- consommateurs prévus : WR (walker P4), Daily (§10.2 override_pattern → docket ; §8.2 plan_delta_needed), Vector (§4.8 dérives, §6 rapport fantôme, §4.6 rapport surge — « si l'usine n'est pas posée, table tampon »), Pulse (P6 s'intègre au WR).
- statut : spécifié. Table partagée de fait → canoniser en F2 dès création (R3).

### F2-12 `plan_versions` + `plan_deltas` + vue `v_plan_current`
- vit : spécifiées (spec WR §3.5). MANQUANTES. Chevauchement avec doc 52 §8 (plan mensuel cron lundi 05:00) et doc 43 (imperium_daily_plan_versions annoncée, jamais codée) — voir FINDINGS DV-5.
- consommateurs prévus : WR (deltas hebdo, régénérations), Daily (G1 périmètre « plan courant », §0.5), le 32B terrain (« le lit ENTIER »).
- statut : spécifié.

### F2-13 définitions de signaux partagées (`*_signal_definitions`/`*_signal_values`)
- vit : spécifiées (cf. F1-02). MANQUANTES. Doublon latent pulse_ vs wr_.
- statut : spécifié (dupliqué latent) — R2.

### F2-14 `ai_call_logs` + `ai_model_pricing` — observabilité IA
- vit : spécifiées (doc 43 §17, section « critique »). MANQUANTES en code. ⚠ seed pricing périmé (qwen-2.5-7b, claude-opus-4.7, haiku — doc 43 §17.2) vs doc 30 canonique.
- consommateurs prévus : TOUT appel IA (« ALL STEPS LOGGED », doc 43 §3.2) ; doc 58 patch 5 (vues Vector) ; console coûts.
- statut : spécifié.

### F2-15 `upcoming_expenses` / liste de dépenses récurrentes
- vit : MANQUANTE (docs 42 §10, 11 §Recurring-Expenses — « source of truth » utilisateur).
- consommateurs prévus : pression (F1-17), Imperium plan awareness, Vault UI, doc 52 §8.2 CATEGORY 2.
- statut : manquant (GAP_vault n°3).

### F2-16 `weekly_finance_summaries` / vue profit hebdo
- vit : MANQUANTE — doc 42 §16 la dit « Existing (per doc 05) », le code ne l'a pas (INVENTAIRE §3, revérifié : aucune migration).
- consommateurs prévus : Path (§16.2 lit `weekly_business_profit` « from common memory » pour la sadaqa), WR W1, doc 52 §8.2.
- statut : manquant (divergence docs↔code DV-3 ; QUESTION Q9).

### F2-17 config role→model éditable (doc 73 PART B)
- vit : spécifiée (doc 73 : store identifier-not-call, provider+model+effort par rôle, catalogue rafraîchissable, hybride OpenRouter/direct selon sensibilité). MANQUANTE.
- consommateurs prévus : toolbox.router, toolbox.llm, tous les appels cloud ; alias de rôles D6 (PHASE_0).
- statut : spécifié.

---

# FAMILLE F3 — MODÈLES SERVIS

| # | modèle | rôle | vit aujourd'hui | consommateurs (source) | statut |
|---|---|---|---|---|---|
| F3-01 | Qwen3-32B (V100, Q5) | routeur/scoreur/exécuteur/conducteur local | NON DÉPLOYÉ (GPU phase 2 à venir, F10 §5-bis) ; le code référence encore `qwen2.5:7b-instruct` (config.py:51 + 5 autres endroits, audit_resync) | doc 30 §3.3 ; tous slots local_default des 4 specs ; chatbot 72 ; dialogue 30 §6 | spécifié |
| F3-02 | qwen3-embedding:8b (P40, Q8→FP16) | embeddings 1024 | NON DÉPLOYÉ (`embeddings_enabled=False`) | doc 38 §5/§11, F10 §5-ter ; mémoire, chaînage WR, corpus Pulse | spécifié |
| F3-03 | Reranker Qwen3-4B (P40) | rerank candidats causaux | NON DÉPLOYÉ — brique V2 UNIQUEMENT (CONCEPTION_chainage : inutile tant que le juge est frontier) ; spec WR 5.2 : « si présent, sinon score composite » | WR W2 | spécifié (V2) |
| F3-04 | OCR VLM système (PaddleOCR-VL-1.6 ou GLM-OCR, P40) | OCR documents/médical/PDF | NON DÉPLOYÉ (F10 §5-quater propriétaire) | Vault reçus (42 §6.3), Pulse médical (34), Inbox (70) | spécifié |
| F3-05 | PP-OCRv4 (OCR Bolt dédié) | lecture écran offre (fallback de l'accessibilité Android) | NON DÉPLOYÉ (F10 §5-quater) ; la spec Vector §3.3 met ML Kit ON-DEVICE en primaire + P40 en contre-lecture §4.7 | Vector | spécifié |
| F3-06 | faster-whisper large-v3 (P40) | transcription fr/ar | NON DÉPLOYÉ (F10 §5-quater) | chatbot, Path adhkar, notes vocales | spécifié |
| F3-07 | fastText lid.176.ftz (CPU) | garde-fou langue sur artefacts | NON DÉPLOYÉ (F10 §5-quater) | artefacts générés (tous domaines) | spécifié |
| F3-08 | CatBoost acceptation (ONNX embarqué) | €/h cycle complet → verdict halo | NON ENTRAÎNÉ (spec Vector §3.6/§4.4 ; docs 57/58 ; doc 30 §2.2/§7.7) | Vector tablette | spécifié |
| F3-09 | CatBoost zones ×2 (zone_eph + zone_wait, même dataset) | temps mort/attente + « Où je vais » | NON ENTRAÎNÉ (spec Vector §4.5 — « un seul modèle de zones, deux consommateurs ») | scoreur embarqué + repositionnement | spécifié |
| F3-10 | Prédicteur cause→surge (GBM) | surge attendu +15/+30 min | NON ENTRAÎNÉ (spec Vector §4.6) | feature CatBoost, modèle de zones, notifications capture | spécifié |
| F3-11 | Rôles cloud : Sonnet 4.6 / Opus 4.8 / Fable 5 / GPT-5.5 (santé, finance, web ×3 rôles) | tiers cloud doc 30 §3 | CONFIGURÉS EN DOC uniquement ; aucun appel branché ; statut Fable §7.8 périmé (suspendu 17/06 ; revenu 01/07 — CONCLUSIONS_test_papier demande la mise à jour) | WR P1/P3/P5, plan, spécialistes, mécanique critique | spécifié |
| F3-12 | Qwen 3B classifier (Ollama, machine orchestrateur) | classification messages du bot de build | **SERVI ET CODÉ** (`/opt/orchestrator/llm_classifier.py`) — seul modèle local effectivement en service dans l'écosystème | orchestrateur (système) | existe_codé |
| F3-13 | Futurs LoRA (32B juge chaînage ; 70B plan_delta/plan_regen) | trajectoires de sortie du cloud | FUTURS (doc 74 ; CONCEPTION_chainage V2/V3 ; spec WR §10 « trajectoire ») ; datasets = v_ai_training_pairs + Phase 4 | WR, Daily | spécifié (futur) |

---

# MATRICE APPS × OUTILS

Légende : ✔ = consomme (codé) ; S = consommation SPÉCIFIÉE (spec/doc sourcé) ; ? = devrait
consommer, non documenté → QUESTION UTILISATEUR (numéro) ; · = sans objet.
Colonne « Système » = usine WR, orchestrateur de build, routage, runner.

| Outil | Imperium | Pulse | Vector | The Path | Vault | Système |
|---|---|---|---|---|---|---|
| F1-01 travel | S (Daily G4/§7) | · | S (§3.5/§4.2) | **? Q2** (mosquées §7-bis, ghusl §10.2) | · | S (builders) |
| F1-02 signals | S (Daily G5 lit) | S (§3.1) | S (§4.8 dérive) | ? Q11 (score §13) | ? Q11 (pression=jauge) | S (W4) |
| F1-03 llm contraint | S (Daily §8) | S (§6) | · (zéro LLM) | ? (advice reformulation, 30 §7.6) | ? (catégorisation, 42 §7) | S (WR slots) |
| F1-04 router /200 | S (hooks 43 §3.2) | S (routed) | · | S (41 §15-REV) | S (42 §13) | S (tout) |
| F1-05 ocr | · | S (P5) | S (§3.3/§4.7) | ? (reçus dons, 41 §17) | S (42 §6.3) | S (contre-lecture) |
| F1-06 transcription | ? (chatbot voix, 72 §9) | · | · | ? (adhkar vocal, 41 §11) | ? (note vocale don, 41 §9.4) | · |
| F1-07 embeddings/top-K | S (52 §8.2 C6) | S (corpus §3.4) | · | · (religieux non vectorisé, 38 §5.1) | · | S (W2/W3, identity) |
| F1-08 memory | S (conseil quotidien) | S (labels) | S (via WR, 39) | S (résumé only, 09 §Path) | S (patterns dépense, 09) | S (W3, P5) |
| F1-09 ephemeral_store | S (chatbot dense, 72 §9) | · | · | · | · | S (WR P2) |
| F1-10 events E2 | ✔ émet / S consomme | S (§12) | S (§7) | ✔ émet (path.item.*) | ✔ émet (vault.transaction.*) | S (usine s'abonne) |
| F1-11 notifications | S (Daily §9) | S (red flags §11) | S (§3.9, §4.8) | **? Q3** (rappels, 41 §5) | **? Q3** (alertes, 42 §10) | S (docket rouge §7) |
| F1-12 params | S (df.*) | S (P:*) | S (§8) | ? (sadaqa %, marges — réglages Path 41 §9) | ? (seuils pression, 11) | S (chain_*, belief_*) |
| F1-13 audit_loop | S (2 slots Daily) | S (§3.9) | S (OCR §4.7) | · | · | S (10 slots WR) |
| F1-14 runner | S (crons Daily) | S (crons) | S (builders) | ? (refresh MAWAQIT 03:00, 41 §6.3) | ? (profit lundi 00:30, 42 §11) | S (usine) |
| F1-15 gbm+registre | · | · | S (§4.4) | · | · | ? Q12 (CatBoost routeur) |
| F1-16 prayer | ? Q6 (awareness zones, 41 §7-bis) | S-doc (jeûne via état Path, 40 §15.2) | S-doc (HUD mosquées, 55 §9.5) | S-doc (41 §6/§14) | · | · |
| F1-17 pressure | S-doc (sizing, 42 §15.4 ; 52 §8.2) | · | S-doc (via plan, 42 §9) | · (sadaqa ≠ pression, 11) | S-doc (dashboard, 42 §14) | S (W1 rollups) |
| F1-18 dialogue | S (chatbot 72) | S (intents P2/P3) | · | · | · | S (WR P2) |
| F1-19 extraction | S (overrides Daily §10.4) | S (refus→labels) | S (WR loop, 39) | · | · | S (W3, chatbot close) |
| F1-20 ingestion | S (70 §13) | S (70 §13) | S (70 §2 exemple véhicule) | S (invocations 41 §11-bis) | S (70 §2) | · |
| F1-21 privacy_gate | S | S (médical) | · | S (very_high, 41 §17) | S (financier) | S (assemblers cloud) |
| F1-22 idempotency | ✔ | S | S (sync) | ✔ (check-ins) | ✔ | ✔ |
| F1-23 geo/H3 | ? (lieux missions Daily §3.2) | · | S (§3.5/§4.5) | ? Q2 | · | · |
| F1-24 scoring /100 | ✔ | · | · | · | · | S (Daily consomme) |
| F2-11 docket | S (Daily §8.2/§10.2) | S (P6) | S (§4.8/§6) | ? (belief religieux ? non documenté) | ? (anomalies finance → docket ? non documenté → Q10) | S (W5, P4) |
| F2-12 plan_versions | S (Daily G1) | · | · | ? (Ramadan → régénération ? 41 14-V3 : « may replan around it ») | · | S (§8) |
| F2-14 ai_call_logs | S (43 §17) | S | S (58 patch 5) | S | S | S |
| F2-15/16 expenses/profit hebdo | S-doc (52 §8.2) | · | S-doc (fuel→business, 46) | S-doc (sadaqa, 41 §9.2) | S-doc (11/42) | S (W1) |

**Lecture The Path / Vault (les angles morts, explicitement) :**
- The Path consomme ou devrait consommer : trajets/geo (Q2 — mosquées §7-bis, ghusl), prayer engine
  (S-doc), notifications (Q3 — rappels/bannières), events (émet déjà `path.item.*` ; renommage
  `worship.*` doc 77), params (réglages sadaqa/marge), runner (refresh MAWAQIT), profit hebdo
  (F2-16 — la sadaqa dépend d'une table qui N'EXISTE PAS), mémoire (résumés only, doc 09),
  ingestion (invocations), privacy gate (very_high). Il ne consomme PAS : embeddings (religieux non
  vectorisé), LLM local (98 % déterministe, 41 §15).
- Vault consomme ou devrait consommer : pression (F1-17, moteur à créer), signals (jauge),
  OCR (reçus), notifications (alertes échéances), events (`finance.*` cible), params (seuils doc 11),
  runner (profit hebdo lundi 00:30 — aujourd'hui prévu n8n doc 42 §11), LLM local (catégorisation
  42 §7), docket (Q10 : anomalies financières W4 → docket, non documenté), profit hebdo (F2-16).

---

# DORMANTS (règle du second consommateur : ATTEND)

| # | candidat | domaine | pourquoi dormant | source |
|---|---|---|---|---|
| D-01 | solveur repas (PuLP+CBC) | Pulse | un seul consommateur plausible ; Daily exclut explicitement le TSP (« aucun TSP », spec Daily §16) | spec Pulse §9 |
| D-02 | générateur de coups légaux (préconditions DSL) | Pulse | mécanique élégante (portes+menu) mais préconditions spécifiques entraînement ; les portes Daily G1-G5 sont plus simples et déjà spécifiées à part | spec Pulse §8 |
| D-03 | moteur de croyances (exposition/confirmation) | WR | cœur du domaine mémoire WR ; personne d'autre n'évalue de prédicats d'exposition | spec WR §6.3 |
| D-04 | walker de docket (budget d'attention, modes full/light) | WR | un seul rituel consommateur | spec WR §9 P4 |
| D-05 | assembleur de digest (caps par type, plafond 40k) | WR | idem | spec WR §9 P1 |
| D-06 | pipeline montre (features device) | Pulse | données brutes interdites de sortie ; consommé par les seuls signaux Pulse | spec Pulse §10 |
| D-07 | fuel smart tracking | Vector/Vault | V2 explicite ; réconciliation hebdo touche Vault et sadaqa → repasser en revue au moment V2 | doc 46 |
| D-08 | music shaker | Vector | feature isolée | doc 48 |
| D-09 | générateur de devis / scanner composition | features | F02/F03, aucun chantier actif | F02, F03 |
| D-10 | friction detection + health score système | Imperium | V3 (doc 54) ; réutilisera signals + docket le moment venu | doc 54 §6-7 |

---

# NOTES DE PROMOTION

Ce brouillon devient `TOOLBOX_CATALOG.md` canonique après : (1) réponses aux QUESTIONS
UTILISATEUR (TOOLBOX_FINDINGS.md, en tête) ; (2) arbitrage des doublons/divergences ;
(3) décision sur l'emplacement canonique (suggestion : `docs_master/78_TOOLBOX_CATALOG.md` —
le numéro 78 était déjà pressenti pour un catalogue transverse, cf. gap_analysis_v1/00_INDEX
ligne 93 qui réservait 78 au catalogue ai_task ; à arbitrer).
