# SPEC — WR CONTINUOUS ENGINE & MEMORY LIFECYCLE V1

> **Livrable d'implémentation one-pass.** Ce document est un prompt d'exécution destiné à Claude Code
> (modèle Fable 5) sur le repo `/opt/imperium-backend`. Il implémente l'inversion du Weekly Review :
> l'usine continue (workers de fin de session), le docket, le pipeline de découverte causale quotidien,
> le cycle de vie des croyances (patterns), le plan mensuel à deltas, et les phases WR restructurées.
> Numérotation : intégrer dans `docs_master/` avec le prochain numéro libre (vérifier la convention).

---

## 0. MODE D'EMPLOI POUR L'EXÉCUTEUR (à lire en premier)

**Ton rôle** : implémenter l'intégralité de cette spec en une passe, dans l'ordre du §15, avec les tests
du §14 comme verrous. Commit/push via l'orchestrateur comme d'habitude.

**Étape 0 obligatoire — inventaire avant toute création** :
1. Lire : `docs_master/30_AI_ROUTING_AND_SCORING_POLICY.md`, `77_EVENTS_CATALOG.md`,
   `gap_analysis_v1/DECISIONS_events.md` (E1/E2/E3), `gap_analysis_v1/CONCEPTION_chainage_V2.md`,
   `gap_analysis_v1/CONCLUSIONS_test_papier.md`, les docs WR existants (plomberie : fenêtres, agrégats,
   sessions, messages, états), et le doc Pulse Intelligence Layer s'il est déjà intégré.
2. Inventorier les tables existantes : `review_sessions`, `review_memory_decisions`,
   `review_final_reports`, `ai_memories` (schéma vectoriel canonique, index HNSW cosine), la table
   d'events **canonique post-E3** (`imperium_events` est dépréciée — identifier la table active et
   l'utiliser partout où cette spec dit "events"), les tables de plan/missions existantes, les tables
   de sessions de travail (bouton début/fin).
3. Produire `migrations/WR_MAPPING.md` : pour chaque table de cette spec → `créer` / `étendre X` /
   `déjà couverte par X`. **Étendre plutôt que dupliquer.** Cas particuliers à traiter explicitement :
   - `CONCEPTION_chainage_V2.md` est la conception gravée du pipeline causal. Cette spec (§5) en est
     l'implémentation normative. En cas de divergence de détail, la conception gravée prime ; consigner
     tout écart dans WR_MAPPING.md.
   - Si la passe Pulse a déjà créé `pulse_ai_transition` / `pulse_audit_samples` : les GÉNÉRALISER en
     tables partagées `ai_slot_transition` / `ai_audit_samples` (§3.7) avec migration des lignes et mise
     à jour des références Pulse. Sinon, créer directement les tables partagées.

**Contraintes globales non négociables** (identiques au doc Pulse) :
- Anglais en base/API/code, français dans les libellés et messages utilisateur.
- Tout derrière feature flags ; `real_ai_enabled=False` → dry-run loggé partout (aucun appel modèle,
  sorties factices marquées `dry_run=true`).
- Aucune donnée personnelle en dur dans code, seeds, commentaires, tests.
- Toute écriture issue d'une proposition passe par validation utilisateur (no-override). Les seules
  écritures automatiques sont : valeurs de signaux/rollups, items de docket en `pending`, logs.
- Ne pas toucher aux modules déterministes existants audités. Ne pas modifier la mécanique des phases
  WR existantes côté plomberie (sessions, messages, états) : on change ce qui les ALIMENTE.
- Migrations réversibles, idempotentes.
- Données brutes device et contenus de conversation exclus de tout prompt (whitelist assembleurs, §9).

**Definition of Done** : migrations + seeds + tests §14 verts + dry-run end-to-end (fin de session →
usine → docket → digest → passe d'hypothèses factice → Phase 4 factice → écriture) avec
`real_ai_enabled=False` + WR_MAPPING.md + patchs docs (§15.8).

---

## 1. CONTEXTE ET PRINCIPES

Le WR actuel est un batch hebdomadaire : audit d'entrée frontier sur ~300-340k tokens bruts,
conversation locale sur store éphémère, chaînage profond Fable, validation, audit de sortie Opus,
écriture. L'inversion gravée dans cette session de conception : **l'usine tourne en continu, le WR
arbitre.** Les découvertes, apprentissages et bilans se calculent chaque soir en local ; le dimanche,
l'humain marche un docket priorisé et le frontier ne fait plus que quatre métiers de jugement (§10).

Principes :
1. **La semaine travaille pour le WR, pas l'inverse.** Tout ce qui peut être calculé à la clôture d'un
   épisode ou d'une session l'est, en local, la nuit même.
2. **Fraîcheur** : un event du lundi a ses candidats causaux jugés lundi soir. Un choc exogène
   replanifie le jour J, sans attendre le rituel.
3. **Tolérance au saut** : un WR sauté n'affame rien. L'usine continue, le docket porte.
4. **La ressource rare est l'attention de validation.** Le WR se conçoit à rebours depuis un budget
   temps (45 min plein / 15 min léger), docket priorisé, classes d'auto-acceptation prouvées.
5. **Divergence LLM, mécanique code, convergence LLM, assemblage code, arbitrage humain** — la
   frontière est la même dans tous les workers.
6. **Une croyance a un cycle de vie** : preuve, renforcement, décroissance par exposition (jamais par
   simple calendrier), contradiction arbitrée, archive interrogeable. Rien ne se supprime.
7. **Le déclaré est une ancre, pas une fin** : les raisons obligatoires de l'utilisateur donnent la
   profondeur 1 ; la découverte fore derrière.
8. **Zéro boîte noire** : chaque item de docket a sa provenance ; chaque forage du frontier est loggé ;
   chaque delta de plan est justifié.

---

## 2. ARCHITECTURE

```
        CHAQUE FIN DE SESSION (+ cron filet 23:30 les jours sans session)
┌────────────────────────────────────────────────────────────────────────┐
│ USINE (V100 locale, incrémentale — traite les events non traités)      │
│  W1 Rollups par domaine (code)      W4 Anomalies/bandes (code)         │
│  W2 Découverte causale (§5)         W3 Extraction + confrontation      │
│     sondes 32B → recherche hybride      d'apprentissages (§6)          │
│     → verdicts pairés 32B → assemblage                                 │
│  W5 Assembleur de DOCKET (code) — priorise, porte, décote              │
└──────────────────────────┬─────────────────────────────────────────────┘
                           ▼
                    ┌────────────┐   item rouge → notification en semaine,
                    │   DOCKET   │   n'attend pas le rituel
                    └─────┬──────┘
                          ▼  (dimanche, ou quand l'utilisateur ouvre le WR)
┌────────────────────────────────────────────────────────────────────────┐
│ WR RITUEL                                                              │
│  P1 Digest 20-40k → passe d'hypothèses frontier (+ droit de forage)    │
│  P2 Conversation Qwen local (store éphémère = docket+hypothèses+forage)│
│  P3 résiduelle : enquêtes dirigées, synthèse conjonctive, deltas plan  │
│  P4 Validation : docket priorisé, budget d'attention, auto-accept      │
│  P5 Écriture déterministe + audit de sortie Opus → faits atomiques     │
└──────────────────────────┬─────────────────────────────────────────────┘
                           ▼
   MÉMOIRE (croyances à cycle de vie, ensemble actif → Conseil IA)
   PLAN MENSUEL (objet complet ; deltas WR ; régénération choc/mensuelle)
```

---

## 3. SCHÉMA DE DONNÉES

Conventions identiques au doc Pulse (uuid pk, timestamps, user_id partout, DDL normatif =
colonnes/contraintes exigées, index secondaires à ta discrétion).

### 3.1 Docket

```sql
CREATE TABLE wr_docket_items (
  id uuid PRIMARY KEY,
  item_type text NOT NULL,      -- chain_proposal|pattern_new|pattern_contradiction|anomaly|
                                -- belief_review_due|user_question|plan_delta_proposal|
                                -- autoaccept_spotcheck|investigation_result|red_flag_ref
  domain text NOT NULL,
  title_fr text NOT NULL,
  payload jsonb NOT NULL,               -- contenu structuré selon item_type (contrats §5-§8)
  evidence_refs jsonb NOT NULL,         -- ids events / patterns / rollups / runs — provenance complète
  confidence int,                       -- 0-100 si porté par un verdict LLM
  impact_estimate int NOT NULL,         -- 1-5, formule déterministe par item_type (seed §13)
  severity text NOT NULL DEFAULT 'normal',   -- normal|elevated|red
  priority numeric NOT NULL,            -- calculée (§7), recalculée par W5 à chaque run
  status text NOT NULL DEFAULT 'pending',    -- pending|presented|validated|refused|deferred|archived
  consecutive_defers int NOT NULL DEFAULT 0,
  force_decision bool NOT NULL DEFAULT false,  -- posé à true quand consecutive_defers >= seuil (§7)
  source_worker text NOT NULL,          -- w1|w2|w3|w4|phase1|phase3|manual
  created_at timestamptz, decided_at timestamptz,
  decision_note text                    -- explication utilisateur au refus/modification (label)
);
```

### 3.2 Usine : runs et curseurs incrémentaux

```sql
CREATE TABLE wr_worker_runs (
  id uuid PRIMARY KEY,
  worker text NOT NULL,                 -- w1_rollups|w2_causal|w3_learning|w4_anomalies|w5_docket
  trigger text NOT NULL,                -- session_end|fallback_cron|manual
  session_ref uuid,                     -- session de travail ayant déclenché, si applicable
  window_from timestamptz NOT NULL, window_to timestamptz NOT NULL,
  items_in int, items_out int, llm_calls int, duration_ms int,
  status text NOT NULL,                 -- completed|failed|partial
  detail jsonb,
  created_at timestamptz
);

CREATE TABLE wr_worker_cursors (
  worker text PRIMARY KEY,
  last_processed_event_ts timestamptz NOT NULL,
  last_processed_event_id uuid,
  updated_at timestamptz
);
-- Règle : chaque worker traite ]cursor, now] puis avance son curseur en fin de run réussi.
-- Jamais de double traitement, jamais de trou (test §14.1). Une session multiple dans la journée
-- produit simplement des lots plus petits.
```

### 3.3 Pipeline de découverte causale (implémente CONCEPTION_chainage_V2)

```sql
CREATE TABLE chain_probes (
  id uuid PRIMARY KEY,
  target_event_id uuid NOT NULL,        -- l'event notable à expliquer (FK table events canonique)
  probe_text text NOT NULL,             -- description de la CAUSE hypothétique (sonde divergente)
  probe_kind text NOT NULL,             -- causal_hypothesis|entity_expansion
  generated_by text NOT NULL,           -- qwen3-32b|frontier(investigation)|dry_run
  run_id uuid REFERENCES wr_worker_runs(id),
  created_at timestamptz
);

CREATE TABLE chain_candidates (
  id uuid PRIMARY KEY,
  target_event_id uuid NOT NULL,
  candidate_event_id uuid NOT NULL,
  channels text[] NOT NULL,             -- vector_classic|vector_probe|graph|metadata
  probe_id uuid REFERENCES chain_probes(id),
  similarity numeric,
  passed_hard_filters bool NOT NULL,    -- antériorité, fenêtre, non-déjà-lié
  rerank_score numeric,
  retained bool NOT NULL DEFAULT false, -- top-N après rerank → part au verdict pairé
  UNIQUE (target_event_id, candidate_event_id)
);

CREATE TABLE chain_pair_verdicts (
  id uuid PRIMARY KEY,
  candidate_id uuid NOT NULL REFERENCES chain_candidates(id),
  verdict text NOT NULL,                -- direct_cause|favoring_condition|correlation|no_link
  mechanism_fr text NOT NULL,           -- ≤ 200 caractères
  confidence int NOT NULL,              -- 0-100
  model_used text NOT NULL, run_id uuid,
  valid bool NOT NULL,                  -- conformité schéma après retry éventuel
  created_at timestamptz
);

CREATE TABLE chain_assemblies (
  id uuid PRIMARY KEY,
  target_event_id uuid NOT NULL,
  proposed_links jsonb NOT NULL,        -- [{cause_event_id, verdict, mechanism_fr, confidence, depth}]
  conflicts jsonb NOT NULL DEFAULT '[]',-- doubles parents, cycles détectés → arbitrage humain
  docket_item_id uuid REFERENCES wr_docket_items(id),
  status text NOT NULL                  -- pending_validation|validated|refused (miroir du docket)
);
-- L'écriture dans le graphe causal réel (causation_id/correlation_id/depth de la table events, E2)
-- n'a lieu qu'en Phase 5, après validation. chain_assemblies est l'antichambre.
```

### 3.4 Cycle de vie des croyances (patterns)

`ai_memories` reste la table vectorielle canonique (une croyance = un fait atomique canonique = un
vecteur). Elle est ÉTENDUE (ou complétée par une table compagnon 1-1 si le mapping le recommande) avec :

```sql
ALTER TABLE ai_memories ADD COLUMN IF NOT EXISTS
  statement_canonical text NOT NULL,          -- phrase déclarative autoportante, format contrôlé
  pattern_domain text NOT NULL,
  confidence numeric NOT NULL DEFAULT 50,     -- 0-100, moteur §6.3
  occurrences int NOT NULL DEFAULT 1,
  last_confirmed_at timestamptz,
  last_exposed_at timestamptz,
  context_predicate jsonb,                    -- prédicat machine-évaluable d'exposition (§6.3) ; null = non dérivable
  status_multiplier numeric NOT NULL DEFAULT 1.0,  -- 1.0 actif ; 0.1 posé par arbitrage contradiction
  review_due_at timestamptz,                  -- filet : influence encore le Conseil mais ni confirmé ni testé depuis N mois
  parent_pattern_id uuid,                     -- lien 'refines' (affinage)
  supersedes_note text;

-- Ensemble actif consommé par le Conseil IA quotidien :
CREATE VIEW v_memories_active AS
  SELECT * FROM ai_memories
  WHERE (confidence * status_multiplier) >= (SELECT seuil depuis parameters 'belief_active_threshold');

CREATE TABLE memory_evidence_links (
  id uuid PRIMARY KEY,
  memory_id uuid NOT NULL,                    -- → ai_memories
  event_id uuid NOT NULL,                     -- → table events canonique (qui pointe elle-même vers la data)
  link_kind text NOT NULL,                    -- generated_by|confirmed_by|contradicted_by
  created_at timestamptz
);

CREATE TABLE memory_confrontations (
  id uuid PRIMARY KEY,
  new_statement text NOT NULL,
  neighbor_memory_id uuid NOT NULL,
  relation text NOT NULL,                     -- duplicate|reinforces|refines|contradicts|unrelated
  rationale_fr text NOT NULL,
  applied_effect text NOT NULL,               -- increment|new_pattern|refine_link|docket_contradiction|none
  model_used text NOT NULL, run_id uuid, created_at timestamptz
);
```

### 3.5 Plan mensuel et deltas

```sql
CREATE TABLE plan_versions (
  id uuid PRIMARY KEY,
  horizon_start date NOT NULL, horizon_end date NOT NULL,   -- ~4 semaines glissantes
  plan jsonb NOT NULL,                        -- objet plan complet (structure alignée sur les tables
                                              -- missions/objectifs existantes ; le 32B terrain le lit ENTIER)
  origin text NOT NULL,                       -- monthly_regen|shock_regen|initial
  origin_ref uuid,                            -- event déclencheur si shock_regen
  model_used text, rationale_fr text,
  status text NOT NULL,                       -- proposed|active|superseded
  created_at timestamptz
);

CREATE TABLE plan_deltas (
  id uuid PRIMARY KEY,
  plan_version_id uuid NOT NULL REFERENCES plan_versions(id),
  operations jsonb NOT NULL,                  -- [{op: move|add|remove|modify, target_ref, params, reason_fr}]
  origin text NOT NULL,                       -- wr_weekly|user_request|shock_minor
  proposal_id uuid,                           -- → docket item plan_delta_proposal
  status text NOT NULL,                       -- proposed|accepted|refused|applied
  applied_at timestamptz,
  model_used text, confidence int
);
-- Règles : le plan actif est TOUJOURS plan_versions(status='active') + deltas appliqués, matérialisé
-- dans une vue v_plan_current que le 32B terrain consomme. Un choc exogène (event replan avec raison
-- de classe 'shock', taxonomie seedée §13) déclenche une régénération complète IMMÉDIATE hors WR,
-- proposée puis validée. La révision mensuelle régénère complètement (remise à plat anti-dérive).
```

### 3.6 WR : digest, hypothèses, enquêtes

```sql
CREATE TABLE wr_digests (
  id uuid PRIMARY KEY,
  review_session_id uuid NOT NULL,            -- → review_sessions existante
  window_from date NOT NULL, window_to date NOT NULL,
  digest jsonb NOT NULL,                      -- snapshot figé : top docket par type (caps), rollups,
                                              -- anomalies, variances inexpliquées, contradictions,
                                              -- croyances à réviser, état du plan
  token_estimate int NOT NULL,                -- plafond dur 40k (test §14)
  created_at timestamptz
);

CREATE TABLE wr_hypotheses (
  id uuid PRIMARY KEY,
  digest_id uuid NOT NULL REFERENCES wr_digests(id),
  output jsonb NOT NULL,                      -- contrat hypothesis_pass (§9.P1)
  drill_log jsonb NOT NULL DEFAULT '[]',      -- [{query, scope, reason, chunks_returned}] — chaque forage loggé
  model_used text NOT NULL, prompt_tokens int, output_tokens int,
  created_at timestamptz
);

CREATE TABLE wr_investigations (
  id uuid PRIMARY KEY,
  review_session_id uuid NOT NULL,
  question_fr text NOT NULL,                  -- "pourquoi X ?" posé en Phase 2 (ou item docket escaladé)
  seed_refs jsonb NOT NULL,                   -- paires déjà jugées reprises comme point de départ
  output jsonb NOT NULL,                      -- contrat investigation (§9.P3)
  model_used text NOT NULL,
  docket_item_id uuid,                        -- résultat re-présenté en Phase 4
  created_at timestamptz
);
```

### 3.7 Transition IA partagée (généralise le pattern Pulse)

```sql
CREATE TABLE ai_slot_transition (
  slot_code text PRIMARY KEY,                 -- namespacé: 'wr.probe_gen','wr.pair_verdict','wr.identity',
                                              -- 'wr.hypothesis_pass','wr.investigation','wr.plan_delta',
                                              -- 'wr.exit_audit','pulse.*' (migrées si existantes)
  tier text NOT NULL,                         -- local_default|cloud_forced|routed
  local_share_pct int NOT NULL DEFAULT 100,
  audit_sample_pct int NOT NULL DEFAULT 100,
  audit_model text,
  agreement_target_pct int NOT NULL DEFAULT 92,
  updated_at timestamptz
);

CREATE TABLE ai_audit_samples (
  id uuid PRIMARY KEY,
  slot_code text NOT NULL,
  target_type text NOT NULL, target_id uuid NOT NULL,
  local_output jsonb NOT NULL,
  cloud_model text NOT NULL, cloud_output jsonb NOT NULL,
  agreement bool NOT NULL, disagreement_class text,
  created_at timestamptz
);
-- Vue v_ai_training_pairs : désaccords d'audit + refus/modifications utilisateur avec explication
-- (docket.decision_note, proposals des domaines) → dataset LoRA unifié.
-- La décroissance de audit_sample_pct est une DÉCISION UTILISATEUR proposée au WR quand
-- l'agreement tient >= cible sur 3 semaines. Jamais automatique.
```

### 3.8 Métriques

```sql
CREATE TABLE wr_metrics_weekly (
  week_start date PRIMARY KEY,
  factory_runs int, events_processed int, chain_proposals int,
  patterns_new int, patterns_reinforced int, contradictions int,
  docket_created int, docket_validated int, docket_refused int, docket_deferred int,
  docket_forced_decisions int,
  wr_duration_min int, wr_mode text,          -- full|light|skipped
  cloud_cost_estimate numeric,
  agreement_by_slot jsonb
);
```

---

## 4. L'USINE — DÉCLENCHEMENT ET WORKERS

**Déclencheur principal** : l'événement de fin de session de travail (bouton Fin — identifier le type
exact dans le catalogue doc 77 et s'y abonner). **Filet** : cron 23:30 les jours sans aucune fin de
session (repos, maladie) pour que les events de la journée soient traités quand même. **Incrémental**
via `wr_worker_cursors` : plusieurs sessions dans la journée = plusieurs petits lots, zéro double
traitement. Ordre d'exécution d'un run : W1 → W4 → W2 → W3 → W5 (les rollups et anomalies nourrissent
la sélection des events notables de W2 ; W5 assemble en dernier). Garde-fou : un run qui échoue
n'avance PAS son curseur ; le run suivant reprend le lot.

**W1 — Rollups (code pur).** Agrégats quotidiens par domaine, alignés sur les agrégats pré-calculés de
la plomberie WR existante (étendre, pas dupliquer) : finance (flux, pression), VTC (sessions, €/h,
zones), missions (avancement, dérive de deadline), Pulse (lit les tables Pulse si la passe est faite,
sinon stub neutre documenté).

**W4 — Anomalies (code pur).** Généralisation du tableau de signaux : pour chaque métrique de rollup,
baseline glissante (médiane 28j ± MAD) + bandes → drapeaux. Les définitions vivent dans une table de
signaux ecosystem (réutiliser le mécanisme `pulse_signal_definitions` si présent, sinon table
équivalente `wr_signal_definitions`, décision consignée au mapping). Variance inexpliquée = anomalie
sans lien causal validé ni raison déclarée à proximité temporelle → marqueur spécifique pour le digest.

**W2 — Découverte causale.** Détail au §5. Sélection des events notables : critères DÉTERMINISTES
seedés (§13.3) — sévérité de l'event, anomalie W4 liée, types d'events marqués `notable` au catalogue,
question explicite de l'utilisateur ("je ne comprends pas pourquoi..."), red flag. Jamais un LLM qui
choisit ce qui est intéressant.

**W3 — Extraction d'apprentissages.** Détail au §6. Déclenché par les événements de clôture d'épisode
du lot : mission.completed / mission.aborted, proposition tranchée avec explication,
mission.ai_disagreement (E1), fin de WR.

**W5 — Assembleur de docket.** Code pur : crée les items depuis les sorties W1-W4 (dédup par
evidence_refs), recalcule les priorités (§7), applique décote de fraîcheur et règle des reports,
pose les notifications rouges (§7).

**Charge locale attendue** : lot quotidien type = quelques events notables × (1 appel sondes + 8-15
verdicts pairés) + extractions/confrontations marginales → minutes à dizaines de minutes sur la V100,
compatible avec le budget nocturne déjà chiffré (~1-2h en pointe hebdomadaire). Les appels 32B d'un
run sont batchés (séquences indépendantes en parallèle).

---

## 5. PIPELINE DE DÉCOUVERTE CAUSALE (W2) — CONTRATS

Implémente CONCEPTION_chainage_V2. Frontière stricte : divergence LLM / mécanique code /
convergence LLM / assemblage code / arbitrage humain.

**5.1 Sondes divergentes** — slot `wr.probe_gen` (local_default, temp 0, GBNF).
Entrée : l'event notable (description, domaine, entités, raison déclarée si présente) + consigne.
Sortie (schema `probe_generation`) :
```json
{"probes": [{"hypothesis_fr": "sous-gonflage prolongé",
             "search_text": "pression pneu basse gonflage contrôle",
             "entity_hints": ["vehicle"]}],
 "notes_fr": ""}
```
3 à 6 sondes, max 6. Les sondes sont des REQUÊTES, jamais stockées comme savoir.

**5.2 Recherche hybride (code pur).** Quatre canaux, union dédupliquée dans `chain_candidates` :
(a) filtres durs d'abord — antériorité stricte, fenêtre paramétrée (P:chain_window_days, défaut 90,
extensible par type), non-déjà-lié ; (b) canal graphe — mêmes entités, même correlation_id, voisins
1-2 sauts du graphe causal existant ; (c) vectoriel classique sur la description de l'event ;
(d) vectoriel sondes — embedding de chaque search_text. Rerank (modèle reranker sur P40 si présent,
sinon score composite similarité × canal × proximité temporelle) → `retained=true` pour le top-N
(P:chain_topn, défaut 10).

**5.3 Verdicts pairés convergents** — slot `wr.pair_verdict` (local_default, temp 0, GBNF).
Un appel par paire retenue, batchés. Entrée : event cible (+ raison déclarée = ancre de vérité
profondeur 1) + candidat avec sa data liée (extraits plafonnés). Sortie (schema `pair_verdict`) :
```json
{"verdict": "favoring_condition",
 "mechanism_fr": "usure asymétrique non traitée après signalement vibration",
 "confidence": 75}
```
Invalide → 1 retry avec erreur → sinon verdict `no_link` avec `valid=false` (jamais de crash de lot).

**5.4 Assemblage (code pur).** Paires ≥ P:chain_min_confidence (défaut 60) → arêtes proposées ;
calcul de depth (depth parent + 1, ancré sur les liens déclarés existants) ; détection cycles et
doubles parents → `conflicts`. Écriture `chain_assemblies` + item docket `chain_proposal`
(payload = liens proposés + mécanismes + conflits à arbitrer).

**5.5 Rien n'entre dans le graphe réel avant Phase 5.** La passe déterministe temps-réel des liens
DÉCLARÉS (raisons obligatoires, E2 passe 1) reste inchangée et hors de ce pipeline — elle écrit
directement, comme aujourd'hui, car c'est du su, pas du découvert.

---

## 6. CYCLE DE VIE DES CROYANCES (W3)

**6.1 Extraction à la clôture d'épisode** — slot `wr.pattern_extract` (local_default).
Déclencheurs : mission.completed/aborted, proposition tranchée avec explication, ai_disagreement,
clôture WR. Entrée : l'épisode complet (event de clôture + chaîne déclarée + data liée plafonnée).
Sortie (schema `pattern_extraction`) :
```json
{"patterns": [{
  "statement_fr": "Les sessions VTC démarrées après 21h le samedi ont un €/h supérieur de 15-25%",
  "domain": "vtc",
  "context_predicate": {"all": [{"field":"session.day_of_week","op":"=","value":"saturday"},
                                 {"field":"session.start_hour","op":">=","value":21}]},
  "evidence_event_ids": ["..."],
  "suggested_confidence": 55}],
 "none": false}
```
Règles de canonicité (validées par code) : phrase déclarative autoportante ≤ 240 caractères, pas de
pronom sans référent, pas de date relative ("récemment" interdit), une seule affirmation par pattern.
`context_predicate` : le LLM le propose, le CODE le valide contre le vocabulaire des champs de
rollups/signaux (whitelist seedée) ; invalide ou non dérivable → null (le pattern reste légal, sa
décroissance passera par le filet review_due).

**6.2 Confrontation d'identité** — slot `wr.identity` (local_default). LA pièce qui fait fonctionner
le compteur. Pour chaque pattern extrait : (code) top-K vectoriel sur ai_memories (P:identity_topk,
défaut 5) + filtre domaine/entités → (LLM) un verdict par voisin (schema `identity_confrontation`) :
```json
{"relation": "duplicate", "rationale_fr": "même affirmation, formulation différente"}
```
Effets appliqués par le CODE, loggés dans memory_confrontations :
- `duplicate` → PAS d'insertion ; incrément du canonique : occurrences +1, confirmation (§6.3),
  evidence_link 'confirmed_by'.
- `reinforces` → idem duplicate + note (affirmations distinctes mais convergentes : lien evidence).
- `refines` → insertion avec parent_pattern_id (le parent n'est pas modifié).
- `contradicts` → insertion en confidence init basse + item docket `pattern_contradiction`
  (les DEUX patterns présentés à l'arbitrage) ; AUCUN effet sur le pattern existant avant arbitrage.
- `unrelated` (tous voisins) → insertion simple.

**6.3 Moteur de confiance — décroissance par exposition, jamais par calendrier.**
```
CONFIRMATION (occurrence observée du pattern) :
  confidence += alpha * (100 - confidence)          # saturant ; alpha = P:belief_alpha (0.15)
  last_confirmed_at = now ; occurrences += 1

EXPOSITION NON CONFIRMÉE (le contexte s'est présenté, le pattern ne s'est pas vérifié) :
  confidence -= beta * confidence                    # beta = P:belief_beta (0.10)
  last_exposed_at = now

DÉTECTION D'EXPOSITION (job quotidien, code pur) :
  pour chaque pattern actif avec context_predicate non null :
    évaluer le prédicat sur les rollups/signaux du jour
    présenté ET confirmé → CONFIRMATION ; présenté ET non confirmé → décrément
    non présenté → RIEN (non-observé ≠ faux ; un pattern rare reste fort)
  patterns sans prédicat → aucun mouvement automatique (filet 6.4 uniquement)

CONTRADICTION ARBITRÉE (Phase 4) :
  perdant : status_multiplier = 0.1  → sort de v_memories_active, reste interrogeable en archive
  gagnant : CONFIRMATION forte (alpha doublé, une fois)
```
Le Conseil IA quotidien ne consomme QUE v_memories_active. L'archive complète reste interrogeable
explicitement ("ce qui marchait avant") — rien ne se supprime jamais.

**6.4 Filet review_due.** Job hebdo (code) : pattern dans l'ensemble actif, sans confirmation ni
exposition depuis P:belief_review_months (défaut 6) → item docket `belief_review_due` (ligne de
5 secondes en Phase 4 : garder tel quel / affaiblir / archiver).

---

## 7. DOCKET — PRIORITÉ, PORTAGE, ROUGE

**Priorité (recalcul à chaque run W5)** :
`priority = severity_w × impact_estimate × freshness × confidence_factor`
avec severity_w ∈ {normal:1, elevated:2, red:4} ; freshness = exp(−age_jours / P:docket_halflife
(défaut 14)) ; confidence_factor = 0.5 + confidence/200 (les basses confiances montent MOINS —
elles attendent le mode plein, sauf sévérité). Formule en paramètres, pas en dur.

**Portage et décision forcée** : deferred → consecutive_defers +1. À P:docket_max_defers (défaut 3),
`force_decision=true` : l'item remonte en tête de son type au prochain WR avec deux boutons seulement
(trancher / archiver). Le docket ne peut ni exploser ni enterrer.

**Rouge en semaine** : item severity=red (red flag référencé, contradiction sur croyance à fort usage
Conseil, choc plan) → notification immédiate à l'utilisateur, sans attendre le rituel. Le rouge
n'applique RIEN tout seul : il notifie et attend décision.

**Politique de saut** : pas de WR ouvert dans la fenêtre → wr_metrics_weekly.wr_mode='skipped',
l'usine continue, le docket porte. Aucun traitement spécial, aucun rattrapage forcé : c'est le design.

---

## 8. PLAN — TROIS DÉCLENCHEURS

**8.1 Choc exogène (immédiat, hors WR).** Un replan utilisateur dont la raison appartient à la
taxonomie `shock` (seed §13.6 : accident, panne immobilisante, événement familial majeur, perte de
source de revenu, blessure invalidante) → slot `wr.plan_regen` (cloud_forced) le jour même :
régénération complète proposée (plan_versions status=proposed, origin=shock_regen) → validation
utilisateur → active, l'ancienne superseded. Les replans ordinaires (déviation terrain du 32B)
restent la mécanique existante, inchangée.

**8.2 Semaine ordinaire (WR).** Slot `wr.plan_delta` (cloud_forced → cible LoRA 70B) : entrée =
v_plan_current + digest + validations de la session. Sortie (schema `plan_delta`) :
```json
{"operations": [{"op": "move", "target_ref": "mission:...", "params": {"to_week": 3},
                 "reason_fr": "dette de sommeil + surcharge sem.2"}],
 "kept_invariants_fr": ["objectif X inchangé"],
 "confidence": 80}
```
Le reste du plan est réputé stable. Chaque delta = item docket `plan_delta_proposal`, validé en
Phase 4, appliqué en Phase 5 (code : vérification que les ops sont applicables — refs existantes,
pas de conflit de dates — sinon rejet motivé).

**8.3 Révision mensuelle.** Régénération complète (anti-dérive des deltas accumulés), même contrat
que 8.1 avec origin=monthly_regen, planifiée par le rythme mensuel existant.

---

## 9. LE WR RESTRUCTURÉ — CE QUI CHANGE PAR PHASE

La plomberie (review_sessions, messages, états, fenêtre 7 jours fermée) ne change pas. Change ce qui
alimente chaque phase.

**P1 — Passe d'hypothèses** — slot `wr.hypothesis_pass` (cloud_forced ; trajectoire 70B local).
(code) Assembler wr_digests : top docket par type avec caps (P:digest_caps par type), rollups semaine,
anomalies + variances inexpliquées, contradictions pendantes, croyances à réviser, état plan +
deltas pendants. Plafond dur 40k tokens estimés (troncature par priorité, jamais par hasard).
Whitelist assembleur : JAMAIS de brut device, JAMAIS de contenu conversationnel, JAMAIS de documents
médicaux (les refs suffisent). (LLM) Sortie (schema `hypothesis_pass`) :
```json
{"systemic_hypotheses": [{"statement_fr": "...", "domains": ["finance","pulse","vtc"],
                          "evidence_refs": ["..."], "confidence": 70}],
 "agenda": [{"question_fr": "...", "stake_fr": "...", "refs": ["..."]}],
 "drill_requests": [{"query": "...", "scope": "events|memories|rollups", "reason_fr": "..."}]}
```
Boucle de forage : max P:drill_max (défaut 6) requêtes, servies par le code (RAG sur stores vectoriels
+ vues rollups prédéfinies UNIQUEMENT), chaque forage loggé dans drill_log, puis sortie finale.
5-8 questions d'agenda max.

**P2 — Conversation (inchangée dans son mécanisme).** Qwen local + store éphémère ; le store est
peuplé par : digest + hypothèses + résultats de forage + refs docket. La conversation MARCHE L'AGENDA.
Une question utilisateur "pourquoi X ?" non couverte → crée wr_investigations (P3).

**P3 — Résiduelle : trois métiers.**
(a) Enquêtes dirigées — slot `wr.investigation` (cloud_forced, le raisonnement le plus dur du
système) : reprend les verdicts pairés existants sur X (seed_refs), peut demander de NOUVELLES sondes
(via 5.1, informées par la question), fore multi-sauts sur le dossier assemblé. Sortie : chaîne
explicative proposée + confiance + questions ouvertes → item docket re-présenté en Phase 4.
(b) Synthèse conjonctive — slot `wr.conjunctive` (cloud_forced) : sur le digest, cherche exclusivement
les patterns que le pairé A→B ne voit pas (conjonctions A+B+C→D, dérives lentes multi-semaines).
Sortie : hypothèses systémiques additionnelles → docket.
(c) Deltas de plan (§8.2).

**P4 — Validation, budget d'attention.** Le walker de docket sert les items par priorité sous
contrainte de mode : `full` (défaut 45 min, tous types) / `light` (15 min : rouges, force_decision,
contradictions, deltas plan uniquement — le reste porte sans pénalité). Classes d'auto-acceptation :
table seedée vide + mécanique — une classe (item_type + conditions : agreement ≥ cible 3 semaines,
confidence ≥ seuil) peut être activée PAR L'UTILISATEUR ; les items auto-acceptés génèrent
P:spotcheck_pct (défaut 10) d'items `autoaccept_spotcheck` re-présentés. Chaque refus/modification
exige une explication (decision_note) — c'est le label.

**P5 — Écriture + audit de sortie.** (code) Appliquer les validations : chain_assemblies validées →
écriture E2 dans la table events canonique (causation_id, correlation_id, depth) ; contradictions
arbitrées → multiplicateurs ; deltas acceptés → plan_deltas applied ; décisions →
review_memory_decisions. (LLM) Slot `wr.exit_audit` (cloud_forced, Opus — décision gravée) : entrée =
digest + hypothèses + résumé conversation + décisions de la session. Sortie (schema `exit_audit`) :
```json
{"learning_facts": [{"statement_fr": "...atomique canonique...", "evidence_refs": ["..."],
                     "initial_confidence": 60, "context_predicate": null}],
 "corrections_applied_fr": ["..."], "report_md": "..."}
```
Chaque learning_fact passe par la confrontation d'identité 6.2 (pas d'insertion aveugle), le rapport
va dans review_final_reports. Event review.completed ferme la session.

---

## 10. RÔLES FRONTIER & TRANSITION

| slot_code | rôle | tier initial | trajectoire de sortie |
|---|---|---|---|
| wr.probe_gen | sondes divergentes quotidiennes | local_default | déjà local |
| wr.pair_verdict | verdicts pairés quotidiens | local_default | LoRA sur désaccords + décisions Phase 4 |
| wr.pattern_extract | extraction d'apprentissages | local_default | déjà local |
| wr.identity | confrontation d'identité | local_default | déjà local |
| wr.hypothesis_pass | hypothèses cross-domaines + agenda | cloud_forced | 70B local sur digest (jamais sur brut) |
| wr.investigation | enquêtes dirigées multi-sauts | cloud_forced | dernier à partir (raisonnement le plus dur) |
| wr.conjunctive | synthèse conjonctive hebdo | cloud_forced | 70B local candidat |
| wr.plan_delta | deltas de plan hebdo | cloud_forced | LoRA 70B (dataset nativement en forme delta) |
| wr.plan_regen | régénérations (choc/mensuel) | cloud_forced | LoRA 70B, après plan_delta |
| wr.exit_audit | consolidation vérité validée | cloud_forced (Opus, gravé) | reste Opus par décision utilisateur |

L'audit décroissant s'applique aux slots local_default via ai_slot_transition (échantillon contre-lu,
agreement mesuré, décroissance proposée au WR, jamais automatique). Budget cloud cible par WR avec
cette architecture : ordre de 2-5 $ (digest ≤40k + enquêtes + deltas + exit condensé) contre ~25-30 $
pour l'architecture batch. Consigner l'estimation réelle dans wr_metrics_weekly.cloud_cost_estimate.

---

## 11. INTÉGRATION EVENTS (table canonique post-E3, politique E2)

Ajouter au catalogue (doc 77) et émettre :

| type | émis par | payload minimal |
|---|---|---|
| wr.factory.run_completed | usine | {worker, trigger, window, items_out, status} |
| chain.proposal_created | W2 | {target_event_id, links_count, conflicts_count, docket_item_id} |
| memory.pattern_created / .reinforced | W3 | {memory_id, relation, occurrences} |
| memory.contradiction_flagged / .arbitrated | W3 / P4 | {memory_ids, winner?} |
| memory.review_flagged | filet 6.4 | {memory_id, months_silent} |
| docket.item_created / .decided / .forced | W5 / P4 | {item_id, item_type, status, defers} |
| docket.red_notified | W5 | {item_id, severity} |
| plan.delta_proposed / .applied | P3/P5 | {delta_id, ops_count, origin} |
| plan.regenerated | 8.1/8.3 | {plan_version_id, origin, origin_ref} |
| wr.digest_assembled / wr.hypothesis_completed | P1 | {digest_id, token_estimate, drills} |
| wr.investigation_completed | P3 | {investigation_id, question_hash} |
| wr.exit_audit_completed / review.skipped | P5 / saut | {review_session_id, facts_count} |

Règles E2 : correlation_id = dossier du run/de la session WR ; causation_id = événement déclencheur
direct (ex. work_session.ended → wr.factory.run_completed) ; depth = depth parent + 1. Payloads =
références, jamais de contenus médicaux ou financiers bruts.

---

## 12. API & WORKFLOWS

**Endpoints (`/api/wr/`)** : `GET docket?status=&type=` ; `POST docket/{id}/decision`
{decision, decision_note?, modified_payload?} ; `GET docket/red` ; `GET digest/current` ;
`GET plan/current` (v_plan_current) ; `POST plan/shock` (déclenchement manuel d'une régénération
choc avec raison) ; `GET memories/active?domain=` ; `GET memories/archive?q=` (recherche archive
explicite) ; `GET metrics/weekly` ; `POST investigations` {question_fr} (depuis la Phase 2) ;
`POST admin/transition` (ai_slot_transition, protégé).

**Workflows/crons (même mécanisme runner que retenu pour Pulse)** :
`wr_factory_on_session_end` (abonnement event fin de session) ; `wr_factory_fallback` (23:30,
si aucun run du jour) ; `wr_exposure_daily` (moteur 6.3) ; `wr_review_due_weekly` (filet 6.4) ;
`wr_digest_on_open` (assemblage à l'ouverture du WR) ; `wr_audit_weekly` (agreement) ;
`wr_metrics_rollup` ; `monthly_regen` (8.3) ; `exploration_monthly` (SQUELETTE : export d'agrégats +
slot cloud proposant de nouveaux signaux/patterns candidats → docket ; corps optionnel V1).

---

## 13. SEEDS V1

1. **ai_slot_transition** : les 10 slots du §10 avec tiers initiaux, audit_sample_pct=100.
2. **Paramètres** (table de paramètres versionnés existante ou équivalente, origin='initial',
   défauts À VALIDER) : chain_window_days=90 ; chain_topn=10 ; chain_min_confidence=60 ;
   identity_topk=5 ; belief_alpha=0.15 ; belief_beta=0.10 ; belief_active_threshold=40 ;
   belief_review_months=6 ; docket_halflife_days=14 ; docket_max_defers=3 ; drill_max=6 ;
   digest_token_cap=40000 ; digest_caps par type {chain_proposal:12, pattern_new:10,
   contradiction:8, anomaly:10, belief_review_due:6, plan_delta_proposal:8} ; spotcheck_pct=10 ;
   wr_budget_min {full:45, light:15}.
3. **Critères de sélection des events notables (W2)** : sévérité ≥ seuil catalogue ; anomalie W4
   corrélée temporellement (même jour, même domaine) ; types marqués notable au doc 77 ; question
   utilisateur explicite ; red flag. Table de critères éditable, pas de code en dur.
4. **Vocabulaire des context_predicate** : whitelist des champs évaluables (day_of_week, start_hour,
   domain, session_type, zone, montants agrégés, bandes de signaux…) dérivée des rollups W1 —
   générer depuis le schéma réel, documenter.
5. **Formats canoniques** : règles de canonicité des statements (§6.1) en constantes testées.
6. **Taxonomie shock (8.1)** : accident véhicule, panne immobilisante, événement familial majeur,
   perte de source de revenu, blessure invalidante, sinistre logement. Éditable.
7. **wr_sentinel/notification rouge** : canaux de notification existants réutilisés (identifier).
8. **Classes d'auto-acceptation** : table vide + mécanique seulement (activation = décision user).

---

## 14. TESTS REQUIS (verrous)

1. Migrations up/down ; WR_MAPPING.md cohérent ; généralisation ai_slot_transition sans casser Pulse
   si présent.
2. Curseurs : pas de double traitement, pas de trou, run échoué n'avance pas, multi-sessions/jour.
3. W2 : sélection notable déterministe (fixtures), contrats probe/verdict (validation, retry,
   fallback no_link), filtres durs (antériorité, fenêtre, déjà-lié), assemblage (depth, cycles,
   doubles parents → conflicts), AUCUNE écriture E2 avant validation.
4. W3 : canonicité (rejets), validation context_predicate contre whitelist, chaque relation de
   confrontation → effet exact (duplicate n'insère PAS), contradiction n'altère RIEN avant arbitrage.
5. Moteur 6.3 : confirmation saturante, décrément uniquement sur exposition non confirmée,
   non-présenté = aucun mouvement, pattern sans prédicat = aucun mouvement automatique,
   multiplicateur post-arbitrage sort le pattern de v_memories_active, archive interrogeable.
6. Docket : formule de priorité paramétrée, décote de fraîcheur, defers → force_decision,
   rouge → notification sans application, politique de saut (usine continue, wr_mode=skipped).
7. Digest : caps par type, plafond tokens (troncature par priorité), whitelist assembleur
   (tentative d'inclure du brut device/conversation/document → exception).
8. Forage : plafond drill_max, scopes autorisés uniquement, log complet.
9. Plan : application de deltas (refs valides, conflits rejetés motivés), v_plan_current =
   version active + deltas, choc → régénération proposée jamais auto-appliquée, régénération
   mensuelle supersede proprement.
10. E2 : chaîne complète session_end → factory → docket → decided → écriture avec
    correlation/causation/depth corrects.
11. Flags : real_ai_enabled=False → zéro appel modèle (spy), dry-run marqué partout,
    end-to-end complet en dry-run.

---

## 15. ORDRE D'EXÉCUTION ONE-PASS

0. Inventaire + WR_MAPPING.md (§0). STOP et signaler si conflit majeur (table events canonique
   introuvable, plomberie WR divergente, schéma ai_memories incompatible).
1. Migrations + seeds (§3, §13).
2. Socle déterministe : curseurs/runs, W1 rollups (extension de l'existant), W4 anomalies,
   moteur d'exposition 6.3, filet 6.4, W5 docket (priorité, portage, rouge), assembleur de digest,
   v_plan_current + applicateur de deltas, applicateur d'effets de confrontation.
3. Contrats JSON (`wr/contracts/`), assembleurs whitelistés, client LLM (réutiliser le wrapper Pulse
   si présent), wrapper transition/dry-run.
4. W2 complet (sondes → recherche → verdicts → assemblage) ; W3 complet (extraction → confrontation).
5. Intégration WR : digest à l'ouverture, passe d'hypothèses + boucle de forage, peuplement du store
   éphémère P2, wr_investigations, walker Phase 4 (modes, budget, force_decision, spot-checks),
   Phase 5 (écritures + exit_audit → confrontation 6.2).
6. Plan : choc (abonnement taxonomie), deltas WR, régénération mensuelle.
7. API + workflows/crons + métriques.
8. Tests §14, dry-run end-to-end, patchs docs : doc WR (renvoi vers ce doc), doc 77 (nouveaux types),
   note dans CONCEPTION_chainage_V2 ("implémenté par doc N"), WR_MAPPING.md final.

## 16. HORS PÉRIMÈTRE EXPLICITE

- L'entraînement LoRA et la bascule 70B (les vues dataset et la table de transition sont livrées).
- Le corps de l'exploration mensuelle (squelette + contrat seulement).
- Toute UI (le docket/walker s'exposent par l'API ; l'app consomme).
- La modification de la conversation Phase 2 au-delà du contenu du store éphémère.
- Le panneau de calibration (chunking, top-K…) — existant, hors passe.
- La migration des patterns ai_memories HISTORIQUES vers le format canonique : script d'audit
  fourni (compte + échantillon), migration réelle = décision utilisateur ultérieure.
- Le routeur /200 (le wrapper l'attend ; routed≈cloud_forced en attendant).
