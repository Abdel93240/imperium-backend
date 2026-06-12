# Audit de cohérence — docs_master (61 fichiers)

> Analyse complète du corpus documentaire pour repérer contradictions, doublons,
> architecture périmée et problèmes de numérotation. Objectif : repartir sur des
> bases saines avant de coder.

---

## Verdict global

**Bonne nouvelle : le corpus est globalement SAIN.** La logique de fond est
cohérente (one-user, backend source de vérité, apps = interfaces, n8n orchestre
sans écrire en base, pgvector ≠ vérité canonique). Les grandes décisions
d'architecture se tiennent entre elles.

Les problèmes sont surtout : **3 problèmes de numérotation/doublons**, **2
fichiers corrompus**, et **1 vraie contradiction technique** (embedding). Rien de
catastrophique, mais à nettoyer avant de continuer.

---

## A. Problèmes de numérotation et doublons

### A.1 Collision doc 43 — RÉSOLUTION CLAIRE
- `43_IMPERIUM_LOGIC_DETAIL.md` (580 lignes, ancien)
- `43_IMPERIUM_LOGIC_DETAIL_v2.md` (1276 lignes, daté 2026-05-16)
- **Analyse** : le v2 est un **sur-ensemble strict** de l'ancien — sections 1-16
  identiques, PLUS sections 17 (AI Observability Logging Layer) et 18 (How to Log
  in Code). Évolution purement additive.
- **Action** : garder le v2 comme `43` officiel, **supprimer l'ancien**. Le v2
  n'a pas le suffixe `_v2` dans son nom final (devient `43_IMPERIUM_LOGIC_DETAIL.md`).

### A.2 Collision doc 45 — DEUX DOCS DIFFÉRENTS
- `45_N8N_RESPONSIBILITY_MATRIX.md` (doc d'architecture, rôle de n8n)
- `45_USER_OBJECTIVES_FEATURE.md` (spec de **feature future V3**)
- **Analyse** : ce ne sont PAS des versions du même doc, mais deux documents
  distincts ayant reçu le même numéro. Cause racine : mélange entre docs
  d'architecture et specs de features futures dans la même séquence (cf. section D).
- **Action** : garder `45_N8N_RESPONSIBILITY_MATRIX` en tant que `45` (suite
  logique des docs 30-44 sur l'architecture IA/n8n). Déplacer
  `USER_OBJECTIVES_FEATURE` vers la séquence des features futures (cf. section D).

### A.3 Doublon 00 — NORMAL
- `00_DOCS_MASTER_INDEX.md` + `00_VISION_GLOBALE.md`
- **Analyse** : acceptable — un index + une vision en tête de dossier. Pas une
  vraie collision. **Aucune action** (ou renommer l'index en `00_INDEX` et la
  vision en `01`, au choix — cosmétique).

---

## B. Fichiers corrompus (sur la Tower)

Deux résidus d'un transfert/push interrompu, présents sur la Tower :
- `18_N8N_SMOKE_TEST.mdvlrGnhQr190317+` (nom de fichier corrompu)
- `52_AI_DECISIO` (fichier tronqué, le vrai est `52_AI_DECISION_FRAMEWORK.md`)
- **Action** : **supprimer ces deux fichiers** sur la Tower. Les versions saines
  (`18_N8N_SMOKE_TEST.md`, `52_AI_DECISION_FRAMEWORK.md`) existent dans le Windows.

---

## C. Contradiction technique réelle : modèle d'embedding

**LE point à trancher.**

- **Doc 38 (Vectorization Pipeline)** déclare : V1 default = **OpenAI
  `text-embedding-3-small` (cloud)**, avec bge-m3 local en fallback V2. Variable
  d'env `EMBEDDING_PROVIDER=openai`.
- **Mais** les docs 50 (Path Dars), 57 (Vector Ride Scoring), 38 lui-même par
  endroits, et d'autres, utilisent **bge-m3 (local)** dans leurs pipelines comme
  si c'était le défaut.

**Tension supplémentaire avec la privacy** : les règles PRIV-001/PRIV-002
(doc 08) imposent que les données sensibles ne quittent pas le serveur sans
permission. Or un embedding par défaut chez OpenAI = **tout ce qui est vectorisé
part dans le cloud**, ce qui frotte avec la philosophie « les données restent
dans l'écosystème ».

**À trancher** : embedding V1 = OpenAI cloud (simple, ~rien à héberger, mais
données sortantes) OU bge-m3 local (cohérent privacy, multilingue FR/AR/EN, mais
~2 Go RAM à héberger — possible sur la machine orchestrateur ou le NAS). Une fois
décidé, **aligner TOUS les docs** sur ce choix.

---

## D. Cause racine des collisions (le vrai sujet)

Les collisions 43 et 45 viennent du **mélange de deux natures de documents dans
une seule séquence numérique** :
- des docs d'**architecture actée** (00-44 : vision, schéma, contrats, logique
  des modules existants) ;
- des specs de **features futures** (ex. `45_USER_OBJECTIVES_FEATURE` marqué
  « V3 — do not implement before V1/V2 », et la plupart des docs 46-58).

Quand on crée les deux types en parallèle (et sur deux machines : Windows +
Tower), les numéros entrent en collision.

**Bonne pratique déjà présente** : les docs 02 et 03 sont proprement marqués
`DEPRECATED` avec renvoi vers 30/31/32. La discipline existe — elle n'a juste pas
été appliquée partout (d'où le `43_v2` non géré).

**Recommandation** : séparer physiquement les deux familles —
- garder la séquence numérique `00-58` pour l'architecture/l'existant ;
- créer un espace dédié aux **features futures** (préfixe `F01, F02…` ou
  sous-dossier `docs_master/features/`).
Cela élimine les collisions à la racine et clarifie « acté » vs « en réflexion ».

> Les 9 specs documentées aujourd'hui (devis, scanner composition, défi religieux,
> entraînement mental, dossier projet, vidéo VTC, dossier médical, kill switch,
> topologie infra) sont TOUTES des features futures → elles iraient dans cet
> espace dédié, aux côtés de `USER_OBJECTIVES_FEATURE`.

---

## E. Points cohérents vérifiés (RAS)

- **Gemma → Qwen** : le changement de routeur local est géré proprement. Les 2
  seules mentions de Gemma (docs 30, 44) disent clairement qu'il n'est plus le
  routeur V1. Pas de contradiction.
- **One active mission** : cohérent dans les 9 docs qui le mentionnent
  (00, 01, 04, 08, 25, 43…).
- **Backend = source de vérité / n8n n'écrit pas en base / pgvector ≠ canonique**
  : martelé de façon cohérente partout (vision, règles, doc 30).
- **Doc 56 (orchestrateur de codage)** : cohérent avec l'orchestrateur réellement
  construit. Note : il mentionne le pipeline ChatGPT↔Codex↔VPS mais pas encore la
  couche Claude Code/audit ni le flux reasoning ajoutés récemment → **évolution à
  documenter**, pas une contradiction.
- **Modèles cloud** (Haiku/Sonnet/Opus/GPT-5.5/Gemini/Whisper) : cohérents entre
  doc 03 et doc 30.

---

## F. Plan de nettoyage recommandé (à exécuter ce soir)

1. **Source de vérité = Windows** (61 fichiers, le plus complet). On écrase
   `docs_master/` de la Tower avec celui du Windows.
2. **Supprimer les 2 fichiers corrompus** (`18_...vlrGnhQr`, `52_AI_DECISIO`).
3. **Résoudre 43** : v2 devient le `43` officiel, supprimer l'ancien.
4. **Résoudre 45** : garder `N8N_RESPONSIBILITY_MATRIX` en 45 ; déplacer
   `USER_OBJECTIVES_FEATURE` dans l'espace features futures.
5. **Décider l'organisation features futures** (préfixe `F` ou sous-dossier) et y
   ranger `USER_OBJECTIVES` + les 9 nouvelles specs du jour.
6. **Trancher la contradiction embedding** (OpenAI cloud vs bge-m3 local) et
   aligner tous les docs.
7. **Mettre à jour le doc 56** pour refléter l'orchestrateur réel (Claude Code +
   reasoning).
8. Push vers GitHub → Tower fait un `git pull` → les trois alignés.

---

## G. Points à trancher par l'utilisateur

- **Embedding V1** : OpenAI cloud ou bge-m3 local ? (impact privacy + hébergement)
- **Organisation features futures** : préfixe `F` ou sous-dossier dédié ?
- **Doublon 00** : on laisse index+vision en 00, ou on renumérote ? (cosmétique)
## Audit Entry — Model Hierarchy Alignment Backlog (June 2026)

### Context

The AI routing/scoring policy (doc 30) was fully rewritten in June 2026. The new
canonical hierarchy is:

```text
Qwen 32B local → Sonnet 4.6 → Opus 4.8 → Fable 5
+ GPT-5.5 (health/Pulse + fresh data/web), Gemini (vision), Whisper (audio),
  CatBoost (Vector ride scoring).
Removed: Haiku 4.5 (no remaining territory).
Former: Qwen 2.5 7B → now Qwen 32B; Opus 4.7 → now Opus 4.8.
```

Docs written before the rewrite still reference the **old hierarchy** (Haiku,
Opus 4.7, Qwen 2.5 / Qwen 7B). They must be aligned on doc 30, which is the
single source of truth for routing.

### Status

- ✅ `30_AI_ROUTING_AND_SCORING_POLICY.md` — rewritten (source of truth).
- ✅ `32_WR_INTERACTIVE_WORKFLOW.md` — aligned via Patch 6M-6P.
- ✅ `41_PATH_LOGIC_DETAIL.md` — aligned via Patch 41-A (§15 routing + §16.1).

### Backlog — docs still referencing the old model hierarchy

To be realigned on doc 30 (verify each; some mentions may be incidental). Suggested
order: most central first (model strategy, unified brain, AI backend layer), then
per-app logic, then periphery.

```text
Central:
  03_MODEL_STRATEGY.md
  44_BRAIN_UNIFIED_LOGIC.md
  16_AI_BACKEND_LAYER_OVERVIEW.md
  31_AI_TASKS_AND_RESULTS_CONTRACT.md
  35_QWEN_SETUP_AND_PROMPTS.md
  36_PROMPTS_CLOUD_AI.md
  52_AI_DECISION_FRAMEWORK.md

Per-app logic:
  40_PULSE_LOGIC_DETAIL.md
  42_VAULT_LOGIC_DETAIL.md
  43_IMPERIUM_LOGIC_DETAIL.md
  34_PULSE_MEDICAL_FEED_AI.md
  57_VECTOR_RIDE_SCORING_ML.md
  58_DOC_57_INTEGRATION_PATCHES.md

Periphery:
  48_VECTOR_MUSIC_SHAKER.md
  50_PATH_DARS_KNOWLEDGE_BASE.md
  55_VECTOR_HUD_FINAL_INTERFACE.md
  56_AUTONOMOUS_CODING_ORCHESTRATOR.md
  59_DESIGN_SYSTEM_V1_DRAFT.md
  F01_USER_OBJECTIVES.md
  AGENTS.md
```

Note: `30_AI_ROUTING_AND_SCORING_POLICY.md.bak` is a local backup of the
pre-rewrite doc 30 and must not be committed; exclude it from the repo.

### Alignment checklist per doc

When aligning a doc, check and fix:
- `Haiku` references → remove / route via Qwen 32B or Sonnet 4.6 per doc 30.
- `Opus 4.7` → `Opus 4.8`.
- `Qwen 2.5` / `Qwen 7B` → `Qwen 32B`.
- Any local "score → model" table → defer to doc 30 §5.6 thresholds.
- Any WR-specific routing → defer to doc 32 + doc 30.
- Confirm the doc does not re-define routing in a way that contradicts doc 30
  (reference it instead).

---

## Backlog Entry — Path `base_advice` (pre-written religious advice)

Context: the morning "AI advice" card for The Path must NOT let the AI generate
or freely select religious content. Decision (doc 30, §7.6): Qwen 32B picks one
entry at random from a dedicated, closed list of pre-written, validated advice
and only reformulates/presents it.

To create (in the Path docs, e.g. doc 41 or a dedicated doc):
- A `base_advice` structure: a closed list of short, self-sufficient, validated
  religious advice entries (each entry is complete on its own, not an excerpt to
  be interpreted).
- Explicit statement that `base_advice` is DISTINCT from the Dars knowledge base
  (doc 50): the AI must never pull/interpret religious content from the Dars or
  any broad corpus.
- The Path advice flow: Qwen 32B random-picks one `base_advice` entry →
  reformulates/presents it. No generation, no selection-by-meaning, no cloud.
- Storage/endpoint for `base_advice` (backend), and how entries are added/curated
  by the user (human-validated only).

Status: to_create. Not urgent. Referenced by doc 30 §7.6.

---

## Backlog Entry — Critical-tier orchestration (doc 30 §5.6)

Context: doc 30 §5.6 critical tier (180–200) defines a two-step mechanic
(GPT-5.5 independent re-scoring → Opus free orchestration) with an anti-loop
circuit breaker. The design is documented; the backend implementation is pending.

To implement (backend):
- **Independent re-scoring call**: when Qwen emits score ≥180, route first to
  GPT-5.5 with the situation + scoring criteria (§5.2/5.3) to re-evaluate. Capture
  GPT-5.5's score; if <180, re-route to the warranted band; if ≥180, proceed.
- **Orchestration handle for Opus**: pass Opus 4.8 the capability profiles of
  Fable 5 and GPT-5.5 so it can delegate/combine.
- **Hand-off counter (circuit breaker)**:
  - Track the number of model-to-model relays within a single critical task.
  - Cap ≈3–4 hand-offs (exact value tunable).
  - Do NOT cap per-model reasoning depth.
  - On cap reached without resolution → force Opus to emit the final answer,
    no further delegation.
- **Logging**: record each hand-off (from_model, to_model, reason, relay_index)
  for later analysis of whether the breaker ever triggers and why.

Status: to_implement. Not urgent (band ≥180 is extremely rare). Referenced by
doc 30 §5.6 (Patch 30-B).
