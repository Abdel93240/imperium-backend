# SPEC — PULSE INTELLIGENCE LAYER V1

> **Livrable d'implémentation one-pass.** Ce document est un prompt d'exécution destiné à Claude Code
> (modèle Fable 5) sur le repo `/opt/imperium-backend`. Il spécifie la couche d'intelligence de Pulse :
> signaux, sentinelle, interprète local, procédures, objet programme, solveur repas, corpus, paramètres
> versionnés, règles rouges, intégration events et routage.
> Numérotation suggérée : intégrer comme doc `41_PULSE_INTELLIGENCE_LAYER.md` dans `docs_master/`
> (vérifier le prochain numéro libre selon la convention existante).

---

## 0. MODE D'EMPLOI POUR L'EXÉCUTEUR (à lire en premier)

**Ton rôle** : implémenter l'intégralité de cette spec en une passe, dans l'ordre du §17, avec les tests
du §16 comme verrous. Tu commites et pushes via l'orchestrateur comme d'habitude.

**Étape 0 obligatoire — inventaire avant toute création** :
1. Lister les tables existantes du schéma (santé/nutrition/hydratation/device notamment). Certaines tables
   spécifiées ici existent peut-être déjà sous un autre nom (recettes, hydratation, pain log, stock).
2. Produire un fichier `migrations/PULSE_MAPPING.md` : pour chaque table de cette spec →
   `créer` / `étendre table existante X` / `déjà couverte par X`. **Étendre plutôt que dupliquer.**
3. Lire `docs_master/30_AI_ROUTING_AND_SCORING_POLICY.md`, `40_PULSE_LOGIC_DETAIL.md`, le catalogue
   d'événements et la politique de chaînage E2 (`correlation_id`/`causation_id`/`profondeur`). Cette spec
   les respecte ; en cas de conflit, signaler dans PULSE_MAPPING.md au lieu de trancher silencieusement.

**Contraintes globales non négociables** :
- Anglais en base/API/code, français dans les libellés UI et messages utilisateur (convention actée).
- Tout passe derrière des feature flags. Respecter les flags existants (`real_ai_enabled`,
  `embeddings_enabled`) : s'ils sont à `False`, toute la couche tourne en **dry-run loggé** (les slots
  LLM renvoient des sorties factices marquées `dry_run=true`, rien n'est proposé à l'utilisateur).
- Aucune donnée personnelle en dur dans le code, les seeds, les commentaires ou les tests.
- Ne pas toucher aux modules déterministes existants déjà audités (decision_framework, etc.).
- Toute écriture issue d'une proposition passe par une validation utilisateur (no-override). Aucune
  exception.
- Migrations réversibles (up/down), idempotentes.

**Definition of Done** : migrations appliquées + seeds chargés + tous les tests du §16 verts + dry-run
end-to-end complet (sentinelle → dispatch → procédure P1 → proposition) avec `real_ai_enabled=False` +
patch doc 40 §18 + entrées ajoutées au catalogue d'événements + `PULSE_MAPPING.md` livré.

---

## 1. CONTEXTE ET PRINCIPES

Pulse est le domaine santé d'Imperium : nutrition, hydratation, sommeil, entraînement physique et mental,
récupération, documents médicaux, données de montre connectée. Objectif de cette couche : faire tourner le
**quotidien santé en 100 % local et déterministe-d'abord**, réserver le LLM local (Qwen3-32B) aux slots de
jugement définis, et le cloud aux slots explicitement routés pendant la transition (audit décroissant).

Principes gravés (rappel — ils gouvernent chaque choix d'implémentation) :
1. **Le système propose, l'utilisateur dispose.** Toute sortie est une proposition refusable avec
   explication ; le refus est un signal d'apprentissage capturé.
2. **Zéro boîte noire.** Chaque décision est traçable : quel signal, quelle règle, quel slot LLM, quelle
   sortie, quelle réaction utilisateur.
3. **Le déterministe est pur, l'IA vient par-dessus.** L'arithmétique, les seuils, les préconditions, les
   produits cartésiens = code. Le jugement contextuel = LLM, à des slots contractualisés.
4. **La science vit dans les paramètres et le corpus versionnés**, jamais dans le code ni dans les poids
   d'un modèle. Mise à jour par revue planifiée validée.
5. **Jamais seul sur le critique** (doc 30) : tout ce qui touche à l'interprétation médicale ou à un
   signal grave a un garde-fou déterministe + un second regard (cloud pendant la transition) + validation
   utilisateur.
6. **Les signaux rouges médicaux remontent "consulte un médecin"** et ne sont jamais absorbés
   silencieusement dans un ajustement de plan.
7. **Frontière de domaine** : Pulse émet des contraintes et signaux santé ; l'arbitrage des heures
   travail/repos appartient au cerveau planning (hiérarchie Niveau 1 > Niveau 2).
8. **Les données brutes de la montre ne quittent jamais la machine et n'entrent jamais dans un prompt**
   (local ou cloud). Seules les features dérivées circulent.

---

## 2. ARCHITECTURE EN COUCHES

```
┌─────────────────────────────────────────────────────────────────────┐
│  COUCHE 0 — SOCLE DÉTERMINISTE (CPU, zéro IA)                       │
│  compteurs, formules, solveur repas, features montre, stock,        │
│  préconditions des coups, règles rouges, produits cartésiens        │
├─────────────────────────────────────────────────────────────────────┤
│  COUCHE 1 — TABLEAU DE SIGNAUX                                      │
│  pipelines → pulse_signal_values → vue v_pulse_board_current        │
│  chaque signal = valeur + baseline + bande + drapeau                │
├─────────────────────────────────────────────────────────────────────┤
│  COUCHE 2 — SENTINELLE (code, volontairement bête)                  │
│  règles génériques (≥2 drapeaux / sévérité / signalement user)      │
│  + passes programmées matin/soir + passe pré-séance                 │
│  → réveille l'interprète, avec cooldown                             │
├─────────────────────────────────────────────────────────────────────┤
│  COUCHE 3 — INTERPRÈTE (Qwen3-32B local, temp 0, JSON contraint)    │
│  lit le tableau (≤3k tokens) + catalogue des procédures             │
│  → NOMME des procédures (ne les lance pas), confiance, escalade     │
├─────────────────────────────────────────────────────────────────────┤
│  COUCHE 4 — PROCÉDURES (workflows figés versionnés)                 │
│  séquences code + slots LLM contractualisés + user gates            │
│  P1..P10 (§7) — le code tient l'échiquier, le LLM joue un coup légal│
├─────────────────────────────────────────────────────────────────────┤
│  COUCHE 5 — PROPOSITIONS & FEEDBACK (no-override)                   │
│  accepter / refuser / modifier + explication → labels               │
│  → dispatch_log, audit décroissant, métriques précision/rappel      │
└─────────────────────────────────────────────────────────────────────┘
Transverse : corpus versionné (fiches), paramètres versionnés,
imperium_events (E2), routage doc 30, flags de transition IA.
```

Inversion de contrôle : **ce n'est jamais un LLM qui appelle du code ou un autre LLM de sa propre
initiative.** Les procédures appellent les slots LLM à des étapes fixes. L'interprète nomme, le code
vérifie l'existence et exécute.

---

## 3. SCHÉMA DE DONNÉES

Conventions : Postgres, snake_case anglais, `id uuid pk default gen_random_uuid()`, `created_at/updated_at
timestamptz`, soft-delete par `active bool` quand pertinent, versionnage append-only quand indiqué.
`user_id` sur toutes les tables (mono-utilisateur aujourd'hui, prêt pour multi). Les DDL ci-dessous sont
des squelettes normatifs : colonnes et contraintes sont exigées, les détails d'index secondaires sont à
ta discrétion.

### 3.1 Signaux

```sql
CREATE TABLE pulse_signal_definitions (
  id uuid PRIMARY KEY,
  code text UNIQUE NOT NULL,              -- ex: 'hydration_ratio_now'
  name_fr text NOT NULL,
  domain text NOT NULL,                   -- hydration|nutrition|sleep|cardio|training|subjective|medical|context|meta
  source_type text NOT NULL,              -- computed|user_event|device_feature|cross_domain_read
  compute_ref text,                       -- nom de la fonction pipeline qui le calcule
  formula_doc text NOT NULL,              -- formule lisible (documentation vivante)
  unit text,
  baseline_method text NOT NULL,          -- none|rolling_7d_median|rolling_28d_median|static_param
  baseline_param_code text,               -- si static_param → pulse_parameters.code
  bands jsonb NOT NULL,                   -- seuils green/yellow/orange/red (absolus ou relatifs baseline)
  freshness_minutes int NOT NULL,         -- au-delà → signal 'stale', non utilisable par l'interprète
  is_medical bool NOT NULL DEFAULT false, -- true → les bandes orange/red routent vers red_flag_rules
  version int NOT NULL DEFAULT 1,
  active bool NOT NULL DEFAULT true,
  created_at timestamptz, updated_at timestamptz
);

CREATE TABLE pulse_signal_values (
  id uuid PRIMARY KEY,
  signal_id uuid NOT NULL REFERENCES pulse_signal_definitions(id),
  ts timestamptz NOT NULL,
  value numeric,
  baseline numeric,
  band text NOT NULL,                     -- green|yellow|orange|red|stale
  flag bool NOT NULL,                     -- band >= yellow
  context jsonb,                          -- détails du calcul (auditables)
  UNIQUE (signal_id, ts)
);
-- Index (signal_id, ts DESC). Partitionnement mensuel si volumétrie le justifie.

CREATE VIEW v_pulse_board_current AS
  -- dernière valeur non-stale de chaque signal actif + méta (band, flag, baseline, âge)
  ;

CREATE TABLE pulse_board_snapshots (
  id uuid PRIMARY KEY,
  taken_at timestamptz NOT NULL,
  reason text NOT NULL,                   -- sentinel_rule_code | scheduled_am | scheduled_pm | pre_session | manual
  board jsonb NOT NULL,                   -- copie figée du tableau au moment du dispatch (reproductibilité)
  flags_count int NOT NULL,
  max_severity text NOT NULL
);
```

### 3.2 Sentinelle & dispatch

```sql
CREATE TABLE pulse_sentinel_rules (
  id uuid PRIMARY KEY,
  code text UNIQUE NOT NULL,
  rule_type text NOT NULL,                -- flag_count|severity|user_report|scheduled|pre_session
  config jsonb NOT NULL,                  -- ex: {"min_flags":2} ou {"cron":"30 7 * * *"}
  cooldown_minutes int NOT NULL DEFAULT 90,
  max_dispatch_per_day int,               -- garde-fou global posé sur la règle 'meta'
  version int NOT NULL DEFAULT 1,
  active bool NOT NULL DEFAULT true
);

CREATE TABLE pulse_dispatch_log (
  id uuid PRIMARY KEY,
  triggered_by text NOT NULL,             -- code règle sentinelle
  board_snapshot_id uuid NOT NULL REFERENCES pulse_board_snapshots(id),
  model_used text NOT NULL,               -- qwen3-32b|<cloud>|dry_run
  prompt_tokens int, output_tokens int, latency_ms int,
  output jsonb,                           -- sortie brute validée de l'interprète (§6)
  valid bool NOT NULL,                    -- sortie conforme au schéma après retry éventuel
  escalated bool NOT NULL DEFAULT false,
  procedures_named text[],
  outcome text,                           -- procedures_run|none_needed|invalid_fallback|escalated
  user_reaction text,                     -- rempli a posteriori: useful|useless|missed (annotation manuelle)
  created_at timestamptz
);
```

### 3.3 Procédures & propositions

```sql
CREATE TABLE pulse_procedures (
  id uuid PRIMARY KEY,
  code text UNIQUE NOT NULL,              -- ex: 'adapt_training_session'
  name_fr text NOT NULL,
  purpose_fr text NOT NULL,               -- 1 ligne, sert au catalogue vu par l'interprète
  trigger_types text[] NOT NULL,          -- dispatch|conversational|scheduled|signal|subprocedure
  steps jsonb NOT NULL,                   -- liste ordonnée: {order, type: code|llm_slot|user_gate|subprocedure,
                                          --  ref, contract_ref, on_fail}
  llm_slots jsonb NOT NULL,               -- {slot_code: {tier: local_default|cloud_forced|routed,
                                          --  input_assembler, output_schema_ref, max_input_tokens}}
  version int NOT NULL DEFAULT 1,
  active bool NOT NULL DEFAULT true
);

CREATE TABLE pulse_procedure_runs (
  id uuid PRIMARY KEY,
  procedure_id uuid NOT NULL REFERENCES pulse_procedures(id),
  procedure_version int NOT NULL,
  dispatch_id uuid REFERENCES pulse_dispatch_log(id),   -- null si conversational/scheduled
  correlation_id uuid NOT NULL,           -- E2: dossier commun à toute la chaîne
  status text NOT NULL,                   -- running|waiting_user|completed|aborted|failed
  steps_log jsonb NOT NULL DEFAULT '[]',  -- une entrée par étape: entrées/sorties/durée/modèle
  result jsonb,
  started_at timestamptz, finished_at timestamptz
);

CREATE TABLE pulse_proposals (
  id uuid PRIMARY KEY,
  procedure_run_id uuid NOT NULL REFERENCES pulse_procedure_runs(id),
  kind text NOT NULL,                     -- session_adaptation|diet_change|program|meal_plan|monitoring|
                                          -- corpus_sheet|parameter_update|signal_definition|doctor_advice
  payload jsonb NOT NULL,                 -- contenu structuré de la proposition
  summary_fr text NOT NULL,               -- texte présenté à l'utilisateur
  presented_at timestamptz,
  decision text,                          -- accepted|refused|modified|expired
  decided_at timestamptz,
  user_explanation text,                  -- verbatim du refus/modification → label
  modified_payload jsonb,                 -- si modified
  applied bool NOT NULL DEFAULT false,
  applied_at timestamptz
);
```

### 3.4 Corpus & paramètres

```sql
CREATE TABLE pulse_corpus_sheets (
  id uuid PRIMARY KEY,
  sheet_type text NOT NULL,               -- diet_family|objective_dimension|adjustment_doctrine|
                                          -- exercise_guideline|medical_reference
  code text NOT NULL,                     -- ex: 'diet.carnivore'
  title_fr text NOT NULL,
  content_md text NOT NULL,               -- fiche complète lisible
  structured jsonb NOT NULL,              -- champs exploitables par le code (contre-indications taguées,
                                          --  profil macro, monitoring recommandé, evidence_level...)
  sources jsonb NOT NULL,                 -- [{title, url, year, org}]
  evidence_level text,                    -- strong|moderate|weak|not_supported
  status text NOT NULL,                   -- draft|validated|deprecated
  generated_by text,                      -- modèle ayant produit le brouillon
  validated_at timestamptz,
  version int NOT NULL DEFAULT 1,
  embedding vector(1024),                 -- canon doc 75 §3 / migration 0032 (DV-2 corrigé)
  UNIQUE (sheet_type, code, version)
);
-- Index HNSW cosine sur embedding, aligné sur la convention ai_memories.

CREATE TABLE pulse_parameters (
  id uuid PRIMARY KEY,
  code text NOT NULL,                     -- ex: 'protein_g_per_kg_target'
  domain text NOT NULL,
  value jsonb NOT NULL,                   -- scalaire, fourchette ou table (ex: courbe horaire hydratation)
  unit text,
  rationale_fr text NOT NULL,
  sources jsonb,
  origin text NOT NULL,                   -- initial|scientific_review|user_feedback|procedure
  valid_from timestamptz NOT NULL,
  superseded_by uuid REFERENCES pulse_parameters(id),   -- append-only: jamais d'UPDATE de value
  version int NOT NULL
);
-- Vue v_pulse_parameters_current : dernière version non supersédée de chaque code.
```

### 3.5 Profil santé, blessures, documents médicaux, règles rouges

```sql
CREATE TABLE pulse_health_profile (
  id uuid PRIMARY KEY,
  conditions jsonb NOT NULL DEFAULT '[]',      -- [{code:'gerd', label_fr, declared_at, source}]
  medications jsonb NOT NULL DEFAULT '[]',
  intolerances jsonb NOT NULL DEFAULT '[]',    -- alimentaires, taguées pour le solveur
  anthropometrics_current jsonb,               -- {weight_kg, height_cm, measured_at} (historique en table dédiée si absente)
  version int NOT NULL, valid_from timestamptz NOT NULL,
  superseded_by uuid                            -- append-only, même pattern que pulse_parameters
);

CREATE TABLE pulse_injuries (
  id uuid PRIMARY KEY,
  zone text NOT NULL, injury_type text,
  severity text NOT NULL,                       -- mild|moderate|severe
  movement_restrictions text[] NOT NULL,        -- tags alignés sur pulse_exercise_catalog.contraindication_tags
  status text NOT NULL,                         -- active|recovering|resolved
  declared_at timestamptz NOT NULL, resolved_at timestamptz,
  source text NOT NULL,                         -- pain_log|user|medical_document
  notes text
);

CREATE TABLE pulse_medical_documents (
  id uuid PRIMARY KEY,
  doc_type text NOT NULL,                       -- blood_test|report|prescription|other
  file_ref text NOT NULL,
  received_at timestamptz NOT NULL,
  has_text_layer bool,
  extraction jsonb,                             -- sortie du slot LLM (avant normalisation)
  extraction_model text, extraction_confidence text,   -- high|medium|low
  second_read_verdict jsonb,                    -- cloud pendant transition (règle "jamais seul")
  validated_by_user bool NOT NULL DEFAULT false
);

CREATE TABLE pulse_lab_results (
  id uuid PRIMARY KEY,
  document_id uuid NOT NULL REFERENCES pulse_medical_documents(id),
  analyte_code text NOT NULL,                   -- nomenclature stable interne (mapper les libellés labo)
  analyte_label_raw text NOT NULL,
  value numeric NOT NULL, unit text NOT NULL,
  ref_low numeric, ref_high numeric,            -- plages IMPRIMÉES sur le compte rendu (source de vérité)
  out_of_range bool NOT NULL,
  measured_at date NOT NULL
);

CREATE TABLE pulse_red_flag_rules (
  id uuid PRIMARY KEY,
  code text UNIQUE NOT NULL,
  description_fr text NOT NULL,
  condition jsonb NOT NULL,                     -- DSL simple évaluée en code: {signal|lab, op, seuil, durée}
  severity text NOT NULL,                       -- advise|advise_strong|urgent
  action text NOT NULL,                         -- advise_doctor|advise_doctor_and_pause_training|urgent_message
  message_fr text NOT NULL,
  version int NOT NULL DEFAULT 1, active bool NOT NULL DEFAULT true
);

CREATE TABLE pulse_red_flag_events (
  id uuid PRIMARY KEY,
  rule_id uuid NOT NULL REFERENCES pulse_red_flag_rules(id),
  raised_at timestamptz NOT NULL,
  evidence jsonb NOT NULL,                      -- valeurs exactes ayant déclenché
  acknowledged_by_user_at timestamptz,
  resolution text                               -- doctor_consulted|resolved|dismissed_with_reason
);
```

**Règle d'implémentation** : les red flags sont évalués par le socle déterministe à chaque écriture de
`pulse_lab_results` et à chaque refresh des signaux `is_medical=true`. Un red flag actif est TOUJOURS
présenté tel quel (message_fr), n'est JAMAIS transformé en simple ajustement de plan, et bloque les
procédures listées dans son action le temps de l'acknowledgement.

### 3.6 Entraînement : programme, sessions, registre, dette, catalogue, coups

```sql
CREATE TABLE pulse_programs (
  id uuid PRIMARY KEY,
  objective_weights jsonb NOT NULL,             -- {dimension_code: poids} sur les dimensions du corpus
  mesocycle jsonb NOT NULL,                     -- {phase, week_current, weeks_total, progression_model}
  doctrine_sheet_code text NOT NULL,            -- fiche adjustment_doctrine appliquée
  status text NOT NULL,                         -- active|paused|completed|superseded
  created_by_run uuid REFERENCES pulse_procedure_runs(id),
  version int NOT NULL DEFAULT 1
);

CREATE TABLE pulse_program_targets (
  id uuid PRIMARY KEY,
  program_id uuid NOT NULL REFERENCES pulse_programs(id),
  week_start date NOT NULL,
  muscle_group text NOT NULL,
  target_sets int NOT NULL,
  tolerance_sets int NOT NULL DEFAULT 2,
  UNIQUE (program_id, week_start, muscle_group)
);

CREATE TABLE pulse_sessions (
  id uuid PRIMARY KEY,
  program_id uuid NOT NULL REFERENCES pulse_programs(id),
  planned_date date NOT NULL, slot_time time,
  session_type text NOT NULL,                   -- strength|hypertrophy|cardio|mobility|technique|mental
  systemic_load int NOT NULL,                   -- 1-10, sert aux préconditions des coups
  exercises jsonb NOT NULL,                     -- [{exercise_id, sets, reps, rpe_target, rest_s}]
  status text NOT NULL,                         -- planned|done|adapted|missed|cancelled
  actuals jsonb,                                -- réalisé: séries/reps/RPE effectifs
  adapted_by_proposal uuid REFERENCES pulse_proposals(id)
);

CREATE TABLE pulse_volume_debt (
  id uuid PRIMARY KEY,
  program_id uuid NOT NULL REFERENCES pulse_programs(id),
  muscle_group text NOT NULL,
  debt_sets int NOT NULL,
  origin_session uuid NOT NULL REFERENCES pulse_sessions(id),
  repayment_session uuid REFERENCES pulse_sessions(id),
  status text NOT NULL                          -- open|scheduled|repaid|written_off (write-off = décision WR)
);

CREATE TABLE pulse_exercise_catalog (
  id uuid PRIMARY KEY,
  name text NOT NULL, name_fr text,
  muscle_groups text[] NOT NULL,
  movement_patterns text[] NOT NULL,            -- squat|hinge|push_h|push_v|pull_h|pull_v|carry|core|...
  equipment text[] NOT NULL,
  contraindication_tags text[] NOT NULL,        -- ex: 'overhead','spinal_load','knee_flexion_deep','impact'
  systemic_load int NOT NULL,
  source text NOT NULL,                         -- free_exercise_db|custom
  validated bool NOT NULL DEFAULT false,        -- seul le sous-ensemble validé est proposable
  active bool NOT NULL DEFAULT true
);

CREATE TABLE pulse_legal_moves (
  id uuid PRIMARY KEY,
  code text UNIQUE NOT NULL,                    -- §8 pour le seed complet
  name_fr text NOT NULL,
  preconditions jsonb NOT NULL,                 -- DSL évaluée en code sur (programme, session, signaux, agenda)
  parameters_schema jsonb NOT NULL,             -- JSON Schema des paramètres que le LLM doit fournir
  effects jsonb NOT NULL,                       -- opérations déterministes sur l'objet programme
  doctrine_refs text[] NOT NULL,                -- principes de la fiche doctrine justifiant le coup
  version int NOT NULL DEFAULT 1, active bool NOT NULL DEFAULT true
);
```

### 3.7 Nutrition : régime, plans, contraintes solveur

```sql
CREATE TABLE pulse_diet_state (
  id uuid PRIMARY KEY,
  diet_family_code text NOT NULL,               -- → pulse_corpus_sheets(diet_family)
  params jsonb NOT NULL,                        -- ex: {eating_window:{start:'18:00',end:'19:00'},meals_per_day:1}
  started_at timestamptz NOT NULL,
  monitoring jsonb NOT NULL DEFAULT '[]',       -- [{check:'lipid_panel', due_date, status}] → signal medical_monitoring_due
  status text NOT NULL,                         -- active|transitioning|ended
  created_by_run uuid REFERENCES pulse_procedure_runs(id),
  version int NOT NULL
);

-- pulse_recipes : PROBABLEMENT EXISTANTE (catalogue recettes). Étendre si besoin pour garantir :
--   macros par portion {kcal, protein_g, carb_g, fat_g} sourcées Ciqual, prep_time_min,
--   diet_tags text[] (compatibilités familles), exclusion_tags text[], cost_estimate, active.

CREATE TABLE pulse_meal_plans (
  id uuid PRIMARY KEY,
  week_start date NOT NULL,
  plan jsonb NOT NULL,                          -- {date: [{slot, recipe_id, portions}]}
  solver_metrics jsonb NOT NULL,                -- cibles vs atteint par jour + relaxations appliquées
  constraints_snapshot jsonb NOT NULL,          -- copie figée des contraintes actives (reproductibilité)
  solver_version text NOT NULL,
  status text NOT NULL,                         -- proposed|accepted|modified|superseded
  proposal_id uuid REFERENCES pulse_proposals(id)
);

CREATE TABLE pulse_solver_constraints (
  id uuid PRIMARY KEY,
  constraint_type text NOT NULL,                -- macro_target|exclusion|variety|prep_time|eating_window|stock|budget
  config jsonb NOT NULL,
  origin text NOT NULL,                         -- diet_state|parameter|user_feedback|health_profile|procedure
  origin_ref uuid,
  active bool NOT NULL DEFAULT true, version int NOT NULL DEFAULT 1
);
```

### 3.8 Features montre

```sql
-- pulse_device_samples : brut (hr, hrv, steps, sleep). Si une table existe, la réutiliser.
-- INTERDICTION CODÉE : le module d'assemblage de prompts (§6) refuse toute référence à cette table
-- (whitelist de sources autorisées, test dédié au §16).

CREATE TABLE pulse_device_features (
  id uuid PRIMARY KEY,
  feature_date date NOT NULL UNIQUE,
  resting_hr numeric, resting_hr_baseline28 numeric,
  hrv_rmssd numeric, hrv_baseline28 numeric,
  sleep_duration_min int, sleep_bedtime time, sleep_regularity_stddev_min int,
  steps int,
  recovery_score numeric,                       -- composite documenté dans formula_doc du signal associé
  computed_at timestamptz NOT NULL
);
```

### 3.9 Transition IA, audit, métriques

```sql
CREATE TABLE pulse_ai_transition (
  id uuid PRIMARY KEY,
  slot_code text UNIQUE NOT NULL,               -- ex: 'interpreter', 'p1.choose_move', 'p5.extract'
  tier text NOT NULL,                           -- local_default|cloud_forced|routed
  local_share_pct int NOT NULL DEFAULT 100,     -- part exécutée en local
  audit_sample_pct int NOT NULL DEFAULT 100,    -- part des sorties locales contre-lues par le cloud
  audit_model text,                             -- modèle de contre-lecture pendant la transition
  agreement_target_pct int NOT NULL DEFAULT 92, -- seuil de décroissance
  updated_at timestamptz
);

CREATE TABLE pulse_audit_samples (
  id uuid PRIMARY KEY,
  slot_code text NOT NULL,
  target_type text NOT NULL,                    -- dispatch|pair_verdict|move_choice|extraction|synthesis
  target_id uuid NOT NULL,
  local_output jsonb NOT NULL,
  cloud_model text NOT NULL, cloud_output jsonb NOT NULL,
  agreement bool NOT NULL,
  disagreement_class text,                      -- si désaccord: label pour le futur dataset LoRA
  created_at timestamptz
);

CREATE TABLE pulse_metrics_daily (
  metric_date date PRIMARY KEY,
  dispatches int, dispatches_useful int, dispatches_useless int, missed_reports int,
  proposals int, accepted int, refused int, modified int,
  escalations int, red_flags int,
  solver_runs int, solver_infeasible int,
  agreement_by_slot jsonb                        -- {slot_code: pct}
);
```

---

## 4. DICTIONNAIRE DES SIGNAUX V1 (seed obligatoire)

Seeder `pulse_signal_definitions` avec les 32 signaux ci-dessous. `formula_doc` doit reprendre la colonne
Formule/Bandes verbatim. Bandes relatives = par rapport à la baseline ; bandes absolues = valeurs fixes ou
paramètre (`P:` = code dans pulse_parameters). Fraîcheur en minutes.

| code | domaine | source | formule (résumé normatif) | bandes | fraîcheur |
|---|---|---|---|---|---|
| hydration_ratio_now | hydration | computed | intake_ml cumulé / attendu à l'heure H selon courbe P:hydration_curve (cible jour P:hydration_target_ml ajustée poids/activité/T° P:hydration_adjusters) | ≥0.8 green / 0.6–0.8 yellow / 0.4–0.6 orange / <0.4 red | 60 |
| hydration_day_total | hydration | computed | intake_ml jour / cible jour | idem ratios | 60 |
| protein_ratio_day | nutrition | computed | protéines g consommées / cible (P:protein_g_per_kg × poids) au prorata de l'heure | ≥0.85 g / 0.65 y / 0.45 o / <0.45 r | 120 |
| kcal_ratio_day | nutrition | computed | kcal / cible jour (P:kcal_target, signé selon objectif) | dans ±10% g / ±20% y / ±30% o / au-delà r | 120 |
| eating_window_state | nutrition | computed | depuis diet_state.params : heures de jeûne écoulées, heures avant fenêtre | informational (pas de bande, flag=false) | 30 |
| last_meal_hours | nutrition | computed | heures depuis dernier repas loggé | contextuel : >18h hors jeûne planifié = orange | 30 |
| mealplan_adherence_7d | nutrition | computed | repas conformes au plan / repas planifiés (7j glissants) | ≥0.8 g / 0.6 y / 0.4 o / <0.4 r | 1440 |
| sleep_duration_last | sleep | device_feature | sleep_duration_min dernière nuit / cible P:sleep_target_min | ≥0.9 g / 0.8 y / 0.7 o / <0.7 r | 1440 |
| sleep_debt_7d | sleep | computed | Σ(cible − réel) sur 7j, en heures | <2h g / 2–4 y / 4–7 o / >7 r | 1440 |
| sleep_regularity_7d | sleep | device_feature | écart-type heure de coucher 7j (min) | <45 g / 45–90 y / >90 o | 1440 |
| resting_hr_delta | cardio | device_feature | FC repos − baseline 28j (bpm) | <+3 g / +3–5 y / +5–8 o / ≥+8 r (is_medical si ≥+8 soutenu 3j) | 1440 |
| hrv_delta_pct | cardio | device_feature | (HRV − baseline28)/baseline28 | >−10% g / −10–20 y / −20–30 o / <−30 r | 1440 |
| steps_ratio_day | cardio | device_feature | pas / cible P:steps_target au prorata heure | ≥0.7 g / 0.5 y / 0.3 o / <0.3 r | 240 |
| recovery_score | cardio | device_feature | composite documenté (sommeil 40% + HRV 30% + FC repos 20% + charge veille 10%) | ≥75 g / 60 y / 45 o / <45 r | 1440 |
| session_planned_today | training | computed | existe-t-il une session planned aujourd'hui ; expose {slot_time, systemic_load, session_type} | informational | 60 |
| hours_to_session | training | computed | heures avant slot_time | informational | 30 |
| volume_debt_total | training | computed | Σ debt_sets open par groupe | 0 g / 1–4 y / 5–9 o / ≥10 r | 1440 |
| training_adherence_7d | training | computed | sessions done / planned 7j | ≥0.8 g / 0.6 y / <0.6 o | 1440 |
| last_high_load_hours | training | computed | heures depuis dernière session systemic_load ≥7 | <24h → contexte pour préconditions | 60 |
| muscle_recovery_gate | training | computed | par groupe sollicité aujourd'hui : heures depuis dernière sollicitation vs P:muscle_recovery_min_h | ok/violation (violation=orange) | 60 |
| adaptation_freq_by_slot | training | computed | sur 28j : % de sessions adaptées/ratées par (jour_semaine, créneau) | >50% sur un slot = yellow (détecteur structurel) | 1440 |
| rpe_trend_7d | training | computed | moyenne RPE réels − RPE cibles (7j) | ±0.5 g / +0.5–1 y / >+1 o | 1440 |
| pain_active | subjective | user_event | douleur active du pain log (zone, sévérité) | mild y / moderate o / severe r (severe → mécanique critique doc 30 §5.6, inchangée) | 30 |
| fatigue_reported | subjective | user_event | signalement fatigue du jour (échelle 1-5) | 1-2 g / 3 y / 4 o / 5 r | 30 |
| mood_reported | subjective | user_event | humeur déclarée (1-5) | idem | 30 |
| stress_reported | subjective | user_event | stress déclaré (1-5) | idem | 30 |
| labs_out_of_range_active | medical | computed | count analytes out_of_range non résolus | 0 g / ≥1 → red_flag_rules (is_medical=true) | 1440 |
| medical_monitoring_due | medical | computed | checks de diet_state.monitoring arrivés à échéance | due = yellow, overdue 14j = orange | 1440 |
| weight_trend_28d | medical | computed | pente poids 28j (kg/mois, signée vs objectif) | conforme g / dérive modérée y / >1.5% masse/mois non planifié o (is_medical) | 1440 |
| workload_today_h | context | cross_domain_read | heures de travail planifiées aujourd'hui (LECTURE planning, Pulse ne l'écrit jamais) | informational | 120 |
| intense_session_yesterday | context | cross_domain_read | session VTC intensive la veille (bool depuis domaine VTC) | informational | 1440 |
| refusal_streak | meta | computed | propositions refusées consécutives (14j) | <3 g / 3-4 y / ≥5 o (signal que les plans collent mal au réel) | 1440 |

Règles transverses : un signal `stale` (fraîcheur dépassée) est affiché comme tel et **exclu** de l'entrée
interprète ; les signaux `is_medical=true` en orange/red passent d'abord par `pulse_red_flag_rules` ;
les signaux `context` sont en lecture seule inter-domaines (frontière : Pulse n'écrit jamais dans le
planning).

---

## 5. SENTINELLE — RÈGLES V1 (seed obligatoire)

La sentinelle est du code pur, volontairement grossière. Elle ne comprend rien : elle réveille.

| code | type | config | cooldown |
|---|---|---|---|
| S1_multi_flags | flag_count | {"min_flags": 2, "min_band": "yellow", "window": "same_day"} | 90 min |
| S2_severe_signal | severity | {"min_band": "orange"} (hors is_medical, qui va aux red flags d'abord) | 60 min |
| S3_user_report | user_report | déclenche sur tout événement pain/fatigue/mood/stress ≥ seuil yellow | 0 |
| S4_scheduled_am | scheduled | {"cron": "30 7 * * *"} — passe matinale systématique | — |
| S5_scheduled_pm | scheduled | {"cron": "30 18 * * *"} — passe du soir | — |
| S6_pre_session | pre_session | T−3h avant toute session planned du jour | — |
| S7_meta_guard | meta | {"max_dispatch_per_day": 6, "dedup_window_min": 90} — plafond global | — |

Comportements exigés : une passe programmée qui trouve un tableau entièrement green écrit
`dispatch_log(outcome='none_needed', model_used='skipped')` **sans appeler le LLM** (skip gratuit).
Le dédup S7 compare l'ensemble des drapeaux actifs : mêmes drapeaux dans la fenêtre → pas de nouveau
dispatch sauf montée de sévérité. Chaque réveil crée un `pulse_board_snapshots` AVANT l'appel interprète.

---

## 6. INTERPRÈTE — CONTRAT (slot `interpreter`)

**Modèle** : Qwen3-32B local, température 0, sortie contrainte par grammaire GBNF (llama.cpp) ou guided
decoding équivalent, dérivée du JSON Schema ci-dessous. Entrée plafonnée à 3 000 tokens (règle du
divide-by-two respectée avec marge).

**Assemblage d'entrée (code, module `pulse/prompting/assembler.py`)** — sources autorisées en whitelist
stricte : `v_pulse_board_current` (snapshot), `pulse_procedures` (catalogue résumé), `pulse_diet_state`,
`pulse_injuries` actives, `pulse_programs` actif (résumé), propositions en attente, monitoring dû.
Contenu : (a) signaux non-green + les `informational`/`context` du jour, format compact une ligne par
signal `code=valeur (baseline, bande, âge)` ; (b) catalogue : `code — purpose_fr — critères de
déclenchement` une ligne par procédure active ; (c) contraintes actives résumées. JAMAIS de données
brutes device, JAMAIS de contenu de documents médicaux, JAMais d'historique conversationnel.

**Sortie (JSON Schema `interpreter_output.schema.json`)** :

```json
{
  "type": "object",
  "required": ["procedures", "signals_used", "confidence", "escalate", "none_needed", "rationale_fr"],
  "properties": {
    "procedures": {"type": "array", "items": {
      "type": "object",
      "required": ["code", "urgency"],
      "properties": {
        "code": {"type": "string"},
        "urgency": {"enum": ["now", "today", "this_week"]},
        "inputs": {"type": "object"}
      }}},
    "signals_used": {"type": "array", "items": {"type": "string"}},
    "confidence": {"enum": ["high", "medium", "low"]},
    "escalate": {"type": "boolean"},
    "none_needed": {"type": "boolean"},
    "rationale_fr": {"type": "string", "maxLength": 400}
  }
}
```

**Règles post-sortie (code)** : (1) tout `procedures[].code` absent du catalogue actif → sortie invalide ;
(2) invalide → 1 retry avec rappel du schéma ; second échec → `outcome='invalid_fallback'` + mise en file
`scheduled review` (la passe suivante retentera) — jamais de crash silencieux ; (3) `confidence='low'` OU
`escalate=true` → routage doc 30 (contre-lecture cloud pendant la transition, selon
`pulse_ai_transition.interpreter`) ; (4) l'interprète NOMME : c'est le runner de procédures qui exécute,
après vérification des préconditions de chaque procédure.

---

## 7. CATALOGUE DES PROCÉDURES V1 (seed obligatoire — 10 cartes)

Format d'implémentation : chaque procédure = une entrée `pulse_procedures` + un workflow n8n (ou runner
backend équivalent si plus simple à tester — au choix de l'exécuteur, mais UN seul mécanisme pour les 10).
Chaque étape logge dans `steps_log`. Chaque slot LLM a un contrat JSON Schema versionné dans
`pulse/contracts/`. Tiers indiqués = état initial de `pulse_ai_transition`.

### P1 — adapt_training_session (trigger: dispatch, pre_session, signal)
1. [code] Charger : session du jour, programme actif (targets semaine, dette), signaux du snapshot,
   fiche doctrine (`adjustment_doctrine` du programme), agenda des prochains jours (sessions planifiées).
2. [code] Générer le **menu des coups légaux** : évaluer les préconditions de chaque `pulse_legal_moves`
   sur l'état courant (§8). Si aucun coup légal hors `maintain` → proposition automatique `maintain`.
3. [llm_slot p1.choose_move — local_default] Entrée : état résumé + menu (coups + préconditions
   satisfaites + effets). Sortie (schema `move_choice`) :
   `{move_code, parameters{...conformes au parameters_schema du coup}, fallback_move_code|null,
   condition_fr|null, rationale_fr ≤300c, confidence}`.
4. [code] Valider : coup ∈ menu, paramètres conformes au schema, effets simulables sans violation
   (recovery gates, dette max). Violation → retry 1 fois avec l'erreur, puis fallback déterministe :
   coup `reduce_volume` paramètres par défaut doctrine.
5. [user_gate] Proposition (summary_fr généré par template + rationale). Décision utilisateur.
6. [code] Si accepted/modified : appliquer les `effects` du coup (update session, dette, registre),
   émettre events (§12). Si refused : capturer `user_explanation`, aucun changement.

### P2 — diet_change_assessment (trigger: conversational)
1. [code] Résoudre l'intent → `diet_family_code`. Fiche absente du corpus → sous-procédure P10, puis reprise.
2. [code] Charger : fiche (structured), profil santé, labs récents, médication, diet_state actuel,
   objectifs (objective_weights du programme), paramètres macro actuels.
3. [code] Énumérer les **paires** {élément structuré de la fiche} × {contrainte du dossier} :
   contre-indications taguées × conditions/médications/intolérances, profil macro × labs concernés,
   exigences pratiques × contraintes de vie (workload, budget temps).
4. [llm_slot p2.pair_verdict — local_default, un appel par paire, batché] Sortie (schema `pair_verdict`) :
   `{verdict: compatible|monitor|risk, mechanism_fr ≤200c, uncertainty: low|med|high}`.
5. [code] Agrégation + passage `pulse_red_flag_rules` : toute paire touchant une règle rouge → verdict
   global bloqué sur `advise_doctor` (sans négociation LLM).
6. [llm_slot p2.synthesis — routed (cloud tant que agreement < cible)] Entrée : paires jugées + agrégat.
   Sortie (schema `diet_synthesis`) : `{verdict_global: adapted|adapted_with_monitoring|not_recommended|
   doctor_first, plan_transition[étapes], monitoring[{check, due_in_weeks}], rationale_fr}`.
7. [user_gate] Proposition complète.
8. [code] Si accepted : nouvelle version `pulse_diet_state`, mise à jour `pulse_solver_constraints`,
   planification monitoring, relance solveur (P6.4) pour la semaine en cours, events.

### P3 — new_training_program (trigger: conversational)
1. [code] Collecte conversationnelle structurée des objectifs → projection sur les dimensions du corpus
   (`objective_dimension`) avec poids.
2. [code] Filtrer `pulse_exercise_catalog` par restrictions actives (`pulse_injuries.movement_restrictions`
   × `contraindication_tags`) — le LLM ne voit QUE le catalogue filtré.
3. [llm_slot p3.design — cloud_forced (vague actuelle), bascule locale ultérieure] Entrée : dimensions
   pondérées, catalogue filtré, doctrine, historique de progression (features précalculées), budget
   temps hebdo. Sortie (schema `program_design`) : mesocycle + targets hebdo + sessions types.
4. [code] Validation structurelle (volumes dans les bornes doctrine, équilibre patterns, recovery gates).
5. [user_gate] → création `pulse_programs` versionnée + events.

### P4 — injury_or_pain (trigger: signal pain_active, conversational)
1. [code] Si severity=severe → mécanique critique existante doc 30 §5.6, INCHANGÉE (escalade forcée).
   Sinon :
2. [llm_slot p4.interpret — local_default] Douleur décrite → `{zone, movement_restrictions[] (tags du
   catalogue), suspected_pattern_fr, red_flag_suspected: bool, confidence}`. `red_flag_suspected` →
   règle rouge advise_doctor.
3. [code] Upsert `pulse_injuries` (status active) → re-filtrage automatique du catalogue pour les
   sessions à venir → sessions impactées identifiées.
4. [subprocedure] P1 sur chaque session impactée des 7 prochains jours (urgency=today).
5. [user_gate] Récap des restrictions + adaptations proposées.

### P5 — medical_document_ingest (trigger: signal nouveau document)
1. [code] Extraction texte (`pdftotext`). Pas de couche texte → `has_text_layer=false`, file d'attente
   vision (HORS PÉRIMÈTRE V1), notification utilisateur, fin.
2. [llm_slot p5.extract — local_default] Texte → schema `lab_extraction` : liste
   `{analyte_label_raw, analyte_code_proposé, value, unit, ref_low, ref_high, confidence_field}`.
   Consigne dure : ref_low/ref_high UNIQUEMENT depuis le document (plages imprimées), jamais de
   connaissance modèle.
3. [code] Normalisation analyte_code (table de mapping extensible), contrôles de plausibilité (unités,
   ordres de grandeur), calcul out_of_range vs plages imprimées.
4. [code] Règle "jamais seul sur le critique" : si ≥1 out_of_range OU confidence non-high sur un champ →
   contre-lecture cloud (slot p5.second_read, cloud_forced) sur les champs concernés, désaccords stockés.
5. [code] Écriture `pulse_lab_results` + passage red flags + [user_gate] validation du tableau extrait
   (l'utilisateur corrige champ par champ si besoin — corrections = labels).

### P6 — weekly_reconciliation (trigger: scheduled, hook WR — s'intègre à la phase Pulse du WR existant)
1. [code] Bilan semaine : adhérence, dette de volume (absorber/replacer/write-off proposé), signaux
   structurels (`adaptation_freq_by_slot` → proposition de déplacement permanent de créneau).
2. [code] Cibles semaine suivante depuis le mesocycle (progression_model, déterministe).
3. [llm_slot p6.review — local_default] Lecture du bilan → anomalies/ajustements qualitatifs proposés
   (schema `weekly_review_notes`, refusable comme le reste).
4. [code] **Solveur repas** (§9) pour la semaine → plan proposé.
5. [user_gate] Batch de propositions (plan repas, replacements, cibles).

### P7 — monthly_revision (trigger: scheduled)
Features précalculées (progression sur mouvements clés, tendances 28j, poids, adhérence) →
[llm_slot p7.revise — cloud_forced vague actuelle] transitions de phase / ajustements mesocycle →
[user_gate]. Même mécanique que P3 étape 4-5 pour la validation structurelle.

### P8 — scientific_review (trigger: scheduled, semestriel)
1. [code] Exporter l'état : `v_pulse_parameters_current` + fiches corpus `validated` (métadonnées +
   claims structurés, PAS de données personnelles).
2. [llm_slot p8.review — cloud_forced, avec web search] Confronter au consensus courant. Sortie : liste de
   diffs `{target: parameter|sheet, code, current, proposed, sources[], rationale_fr}`.
3. [user_gate] Validation diff par diff (flux type Phase 4).
4. [code] Application : nouvelles versions append-only (`pulse_parameters`, `pulse_corpus_sheets`), events.

### P9 — exploration_pass (trigger: scheduled, mensuel)
1. [code] Exporter features AGRÉGÉES (jamais de brut) : distributions de signaux, co-occurrences de
   drapeaux, issues des propositions.
2. [llm_slot p9.explore — cloud_forced aujourd'hui, 70B local demain] Sortie : propositions de NOUVEAUX
   signaux `{code, domain, formula_doc, bands_proposées, rationale_fr}`.
3. [user_gate] → insertion en `pulse_signal_definitions` avec `active=false` puis activation manuelle.

### P10 — missing_sheet (trigger: subprocedure, conversational)
1. [llm_slot p10.draft — routed] Générer la fiche (content_md + structured + sources) pour le code demandé.
2. [code] Insertion `status='draft'` — une fiche draft n'est JAMAIS utilisée par P2 pour un verdict.
3. [user_gate] Validation → `status='validated'`, embedding calculé, event.

---

## 8. MENU DES COUPS LÉGAUX V1 (seed obligatoire)

Le générateur de menu (code) évalue chaque coup contre l'état courant ; seuls les coups dont TOUTES les
préconditions passent sont présentés au slot LLM. Les préconditions référencent : session cible, programme
(targets/dette), signaux du snapshot, agenda (sessions et disponibilités des 7 jours), diet_state
(fenêtre alimentaire), recovery gates (P:muscle_recovery_min_h par groupe).

| code | effet (déterministe) | préconditions clés | paramètres LLM (schema) |
|---|---|---|---|
| maintain | aucun changement | toujours légal | {rationale obligatoire si des drapeaux orange existent} |
| reduce_volume | réduire les séries à X%, créer volume_debt pour le delta | X ∈ [40,90] ; dette résultante ≤ P:max_debt_sets_group | {percent, muscle_groups_scope} |
| shift_time | déplacer slot_time le même jour | nouveau créneau libre ; respecte eating_window si session_type ≠ mobility (pas de haute intensité en jeûne >12h : gate dur) ; respecte muscle_recovery_gate | {new_time, condition_fr optionnelle (ex: "repas 18h pris")} |
| reschedule | déplacer la session à J+n ≤ 6 | jour cible libre ; recovery gates ok au jour cible ; ne crée pas 2 sessions load≥7 consécutives | {target_date} |
| swap_modality | remplacer par technique/mobilité/cardio léger, séries manquantes → dette | session remplaçante systemic_load ≤ 4 | {new_session_type, exercises depuis catalogue filtré} |
| split_session | scinder en 2 demi-sessions sur 2 jours | 2 créneaux dispos ; les 2 respectent les gates | {part1_date/time, part2_date/time, split_ratio} |
| repay_debt | ajouter des séries de dette à une session existante | dette open sur les groupes de la session ; volume total session ≤ cible+tolérance | {debt_ids, added_sets} |
| deload_week | réduire toutes les sessions de la semaine à X% (doctrine) | critères doctrine réunis (rpe_trend, recovery_score, semaine mesocycle) | {percent} — proposé surtout par P6 |

Contrainte transverse codée dans le générateur : **aucun coup ne peut produire un état violant un recovery
gate ou une règle rouge active.** Le slot LLM choisit, paramètre, justifie, et fournit un `fallback_move`
utilisé si la `condition_fr` du coup principal n'est pas remplie à l'heure dite (ex: repas non pris à 18h
→ fallback appliqué automatiquement avec notification, sans nouveau dispatch).

---

## 9. SOLVEUR REPAS (module `pulse/solver/mealplan.py`)

**Techno** : PuLP + CBC (CPU, pip). Cible de résolution < 10 s pour 7 jours × slots.

**Variables** : x[recipe, date, slot] ∈ {0,1} ; portion[recipe, date, slot] ∈ [0.5, 2.0] pas de 0.25
(linéarisé par paliers).

**Contraintes dures** : nb de slots/jour = diet_state.params.meals_per_day ; exclusions (intolérances du
profil, exclusion_tags de la famille de régime, exclusions user_feedback) ; fenêtre alimentaire (slots
horodatés dans la fenêtre) ; macros/jour dans les bandes de tolérance (cibles depuis
v_pulse_parameters_current, modulées par diet_state) ; prep_time_min total/jour ≤ budget du jour (budget
réduit si workload_today_h élevé — table de correspondance paramétrée).

**Objectif (minimisation pondérée)** : |écart macros| (poids P:solver_weights) + pénalité de répétition
(même recette < N jours d'écart) + pénalité coût (optionnelle) + pénalité prep_time.

**Relaxations si infaisable, dans CET ordre, chacune loggée dans solver_metrics** :
1) élargir tolérances macros de ±5 pts ; 2) relâcher la variété (N−1) ; 3) élargir encore macros ±5 ;
4) statut `infeasible` → proposition à l'utilisateur avec les contraintes en conflit identifiées
(jamais de plan silencieusement dégradé au-delà de la relaxation 3).

**Sorties** : `pulse_meal_plans` (plan + metrics + snapshot contraintes) → proposition P6. Le stock
(si table existante) entre en pénalité douce, pas en contrainte dure V1.

---

## 10. PIPELINE MONTRE (module `pulse/device/features.py`)

Job quotidien (cron 06:45, avant la passe S4) + refresh intraday léger pour resting_hr si les données
arrivent en continu. Calculs : resting_hr (méthode documentée : percentile 5 des mesures éveillé au repos
ou valeur constructeur si fournie), baselines = médiane glissante 28j ± MAD, hrv_rmssd moyenne nocturne,
sommeil (durée, heure de coucher, régularité 7j), steps, recovery_score composite (pondérations en
paramètres, formule dans formula_doc). Écrit `pulse_device_features` ; les signaux cardio/sleep lisent
UNIQUEMENT cette table. Rappel dur : `pulse_device_samples` est hors whitelist du prompt assembler —
test dédié §16.

---

## 11. RÈGLES ROUGES MÉDICALES V1 (seed obligatoire)

| code | condition (DSL) | sévérité | action | message_fr (résumé) |
|---|---|---|---|---|
| RF_lab_out_of_range | lab out_of_range=true non résolu | advise (advise_strong si >20% hors plage) | advise_doctor | "Valeur hors plage sur ton bilan : à montrer à un médecin. Je n'ajuste rien sur cette base." |
| RF_rhr_sustained | resting_hr_delta ≥ +8 bpm sur 3 jours consécutifs | advise_strong | advise_doctor | "FC repos anormalement élevée depuis 3 jours : consulte." |
| RF_severe_pain | pain_active severity=severe | urgent | advise_doctor_and_pause_training | mécanique critique doc 30 §5.6 préservée |
| RF_weight_drop | weight_trend_28d < −1.5%/mois non planifié | advise | advise_doctor | perte de poids rapide non planifiée |
| RF_symptom_keywords | mots-clés graves dans pain/notes (liste seedée : douleur thoracique, malaise, essoufflement anormal, etc.) | urgent | advise_doctor_and_pause_training | consultation immédiate recommandée |

Implémentation : évaluation à chaque refresh de signal `is_medical` et à chaque écriture lab. Un red flag
actif est visible en tête de board, exige un acknowledgement, et son `action` bloque les procédures
d'entraînement concernées (P1/P3 refusent de proposer autre chose que mobilité légère tant que
`advise_doctor_and_pause_training` non résolu). Aucune règle rouge n'est désactivable par un slot LLM.

---

## 12. INTÉGRATION imperium_events (politique E2)

Tous les événements ci-dessous sont émis dans `imperium_events` selon la politique E2 : `correlation_id` =
celui du `pulse_procedure_runs` (ou nouveau dossier pour un déclencheur racine), `causation_id` =
l'événement déclencheur direct, `profondeur` = profondeur du parent + 1. Ajouter ces types au catalogue
d'événements (doc dédié) avec leurs payloads.

| type | émis par | payload minimal |
|---|---|---|
| pulse.signal.flagged | pipeline signaux | {signal_code, band, value, baseline} |
| pulse.redflag.raised / .acknowledged | moteur red flags | {rule_code, severity, evidence_ref} |
| pulse.sentinel.triggered | sentinelle | {rule_code, snapshot_id, flags_count} |
| pulse.dispatch.completed | interprète runner | {dispatch_id, outcome, procedures_named, confidence, escalated} |
| pulse.procedure.started / .completed / .failed | runner | {run_id, procedure_code, version, status} |
| pulse.proposal.presented / .decided | couche propositions | {proposal_id, kind, decision, has_explanation} |
| pulse.program.created / .adapted | P1/P3/P7 | {program_id, move_code?, session_id?} |
| pulse.mealplan.generated / .decided | P6 | {meal_plan_id, solver_status, relaxations} |
| pulse.document.ingested / .validated | P5 | {document_id, out_of_range_count, second_read} |
| pulse.corpus.sheet_drafted / .validated | P10/P8 | {sheet_type, code, version} |
| pulse.parameter.updated | P8 | {code, old_version, new_version, origin} |
| pulse.review.completed | P6/P7/P8/P9 | {procedure_code, period, proposals_count} |

Le payload ne contient jamais de valeurs médicales brutes : des références (ids) vers les tables Pulse.

---

## 13. ROUTAGE (doc 30) & TRANSITION IA

- Chaque slot LLM déclare son tier dans `pulse_procedures.llm_slots` ET a une ligne dans
  `pulse_ai_transition` (seed §15). Tiers initiaux : voir cartes §7.
- `routed` = passage par le routeur doc 30 existant quand il sera branché ; en attendant, `routed` se
  comporte comme `cloud_forced` si `real_ai_enabled=true`, sinon dry-run.
- **Audit décroissant** : pour tout slot `local_default`, `audit_sample_pct` des sorties est contre-lu par
  `audit_model` → `pulse_audit_samples`. Un job hebdo calcule l'agreement par slot (vue) ; la décroissance
  du `audit_sample_pct` est une DÉCISION UTILISATEUR (proposée par P6 quand agreement ≥ target sur 3
  semaines), jamais automatique.
- Les désaccords (`agreement=false`) + les refus/modifications utilisateur avec explication constituent le
  dataset LoRA : vue `v_pulse_training_pairs` (slot_code, input_ref, local_output, correction, source).
- Interdiction : aucun slot ne peut envoyer au cloud des champs hors de son assembler whitelisté (même
  discipline que l'interprète). Les assemblers cloud excluent en plus tout identifiant direct.

---

## 14. API & WORKFLOWS

**Endpoints backend (préfixe `/api/pulse/`)** — REST, JWT existant :
`GET board` (tableau courant + red flags actifs) ; `GET signals/{code}/history` ;
`GET proposals?status=pending` ; `POST proposals/{id}/decision` {decision, user_explanation?,
modified_payload?} ; `POST reports` {type: pain|fatigue|mood|stress, payload} ;
`POST intents` {text} → classification → dispatch conversationnel ;
`GET program/current` ; `GET mealplan/current` ; `GET metrics/summary` ;
`POST documents` (upload → P5) ; `GET corpus/sheets?status=` ; `POST admin/transition` (édition
pulse_ai_transition, protégée).

**Workflows n8n (ou crons backend, même mécanisme que choisi au §7)** :
`pulse_features_daily` (06:45) ; `pulse_sentinel_am/pm` (07:30/18:30) ; `pulse_pre_session` (calculé) ;
`pulse_dispatch_runner` ; `pulse_procedure_runner` ; `pulse_weekly` (hook WR) ; `pulse_monthly` ;
`pulse_scientific_review` (semestriel, désactivé par défaut jusqu'au premier corpus validé) ;
`pulse_audit_weekly` (agreement) ; `pulse_metrics_rollup` (quotidien).

---

## 15. SEEDS V1 (fichiers `seeds/pulse/*.sql` ou fixtures, chargés par migration)

1. `signal_definitions` : les 32 signaux du §4, verbatim.
2. `sentinel_rules` : S1–S7 du §5.
3. `procedures` : P1–P10 du §7 (steps + llm_slots sérialisés).
4. `legal_moves` : les 8 coups du §8 avec préconditions et parameters_schema complets.
5. `red_flag_rules` : les 5 règles du §11 + liste de mots-clés.
6. `parameters` (origin='initial', chaque valeur avec rationale_fr courte ; CE SONT DES DÉFAUTS À VALIDER,
   pas des vérités) : protein_g_per_kg_target=1.6 ; kcal_target (formule Mifflin-St Jeor + facteur
   activité, stockée comme table) ; hydration_target_ml (35 ml/kg) + hydration_adjusters (+500 ml si
   activité intense, +300 ml si T°>28°C) + hydration_curve (répartition horaire 7h→22h) ;
   sleep_target_min=450 ; steps_target=8000 ; muscle_recovery_min_h=48 ; max_debt_sets_group=10 ;
   solver_weights {protein:3, kcal:2, carb:1, fat:1} ; solver_tolerances {kcal:±10%, protein:−5/+15%,
   carb:±15%, fat:±15%} ; audit defaults (sample 100%, target 92%).
7. `ai_transition` : une ligne par slot (§7) avec tiers initiaux, audit_sample_pct=100.
8. `corpus_sheets` : le SCHÉMA + UNE seule fiche exemple complète `diet.carnivore` en `status='draft'`
   (générée par toi, sources incluses, marquée explicitement "exemple à valider"). LES AUTRES FICHES SONT
   HORS PÉRIMÈTRE (chantier contenu séparé, voir §18).
9. `exercise_catalog` : importer free-exercise-db (JSON public), `validated=false` partout, script
   d'import rejouable + mapping muscle_groups/patterns/contraindication_tags documenté.

---

## 16. TESTS REQUIS (verrous — la passe n'est pas terminée s'ils ne sont pas verts)

1. Migrations up/down idempotentes ; PULSE_MAPPING.md cohérent avec le schéma final.
2. Pipeline signaux : calculs unitaires par signal (fixtures), bandes, baselines, staleness.
3. Sentinelle : chaque règle S1–S7, cooldown, dédup, skip all-green sans appel LLM, plafond journalier.
4. Interprète : validation schema, rejet code de procédure inconnu, retry puis fallback, plafond tokens,
   **whitelist assembler** (tentative d'inclure pulse_device_samples ou un document médical → exception).
5. Coups légaux : préconditions de chaque coup (cas passants/bloquants), simulation d'effets, interdiction
   de violer un recovery gate ou un red flag, fallback_move automatique sur condition non remplie.
6. Solveur : cas faisable nominal, chaque relaxation dans l'ordre, cas infaisable → statut propre,
   respect fenêtre alimentaire OMAD, exclusions.
7. Red flags : chaque règle, blocage effectif de P1/P3, non-désactivable par sortie LLM (test d'injection :
   une sortie LLM qui tente de contourner → ignorée).
8. Procédures : P1 et P2 end-to-end en dry-run (mocks LLM déterministes), user_gate accepted/refused/
   modified, application des effets uniquement après acceptation.
9. Events : émission avec correlation/causation/profondeur corrects sur une chaîne P1 complète
   (signal → sentinel → dispatch → procedure → proposal → decided).
10. Transition : échantillonnage d'audit, calcul d'agreement, vue v_pulse_training_pairs.
11. Flags : `real_ai_enabled=False` → aucun appel modèle nulle part (spy), sorties dry_run marquées.

---

## 17. ORDRE D'EXÉCUTION ONE-PASS

0. Inventaire + PULSE_MAPPING.md (§0). STOP et signaler si conflit majeur avec l'existant.
1. Migrations (toutes les tables §3, vues, index) + seeds paramètres/signaux/règles/coups/procédures.
2. Socle déterministe : pipeline signaux + board + snapshots ; features montre ; moteur red flags ;
   générateur de coups légaux ; solveur.
3. Contrats : JSON Schemas dans `pulse/contracts/`, assemblers whitelistés, client LLM local
   (temp 0, GBNF), wrapper de tiers/transition (dry-run inclus).
4. Sentinelle + interprète + runner de procédures.
5. Procédures P1, P2, P4, P5, P6 complètes ; P3, P7, P8, P9, P10 en squelette exécutable (étapes code +
   gates fonctionnels, slots branchés sur le wrapper).
6. API + workflows/crons + rollup métriques.
7. Tests §16, corrections, dry-run end-to-end.
8. Docs : patch doc 40 §18 (renvoi vers ce doc), catalogue d'événements, ce fichier intégré en
   docs_master avec le prochain numéro libre.

## 18. HORS PÉRIMÈTRE EXPLICITE DE CETTE PASSE

- Le CONTENU du corpus (30 fiches régimes, 15 dimensions, doctrines) : chantier séparé de génération +
  validation utilisateur. Seuls le schéma, la mécanique P10 et l'exemple carnivore (draft) sont livrés.
- Toute UI (les écrans Pulse consomment l'API, chantier app séparé).
- La voie vision (photos de documents/repas) : file d'attente posée, traitement non implémenté.
- L'entraînement LoRA et l'automatisation complète de l'audit cloud (les hooks, tables et vues sont livrés).
- Le branchement du routeur /200 (le wrapper de tiers l'attend ; `routed`≈`cloud_forced` en attendant).
- Toute modification du cerveau planning (Pulse lit `workload_today_h`, n'écrit rien).
