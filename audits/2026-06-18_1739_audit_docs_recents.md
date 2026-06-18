# Audit de code

> **Date :** 2026-06-18 17:39
> **Périmètre :** docs récents / non couverts de `docs_master/` (corpus passé de
> 61 → 90 fichiers depuis l'audit `_AUDIT_cerveau_commun.md` du 2026-06-14).
> **Mode :** lecture seule. **Aucun doc source modifié.** Livrable = ce rapport.
> **Sources de vérité :** 44 (cerveau commun), 08 (règles non négociables),
> 30 (routage), 09 (mémoire pgvector), 05 (schéma), 99_REGLES_NOMENCLATURE.
> **Verdict :** ✅ Aucune **nouvelle** violation d'écriture croisée app↔app dans
> les docs ajoutés. ⚠️ Une **contradiction** réelle sur le modèle d'embedding V1
> et plusieurs incohérences de nomenclature/métadonnées à réaligner.

## Resume executif

Les documents ajoutés depuis l'audit du 14/06 (notamment 46, 70, 71, et les
F-docs) sont **architecturalement conformes au doc 44** : ils décrivent le backend
comme seul écrivain et conservent la barrière de validation utilisateur, sans
réintroduire de canal app↔app. Le seul problème de **cohérence de fond** est une
**contradiction sur le modèle d'embedding V1** (Qwen3-Embedding dans le doc
autorité 38, mais bge-m3 dans l'index et la doc de nomenclature). Le reste relève
d'incohérences de nomenclature et de métadonnées (fichiers `.bak`, trou F11,
double numéro 00, dates « Last updated » périmées, index non mis à jour).

## Issues CRITICAL

Aucune. (Audit documentaire : pas de faille de sécurité ni de bug bloquant.)

## Issues HIGH

### H1 — Contradiction sur le modèle d'embedding V1 par défaut — **MAJEUR (contradiction)**
- **Docs concernés :**
  - `38_VECTORIZATION_PIPELINE.md` (autorité vectorisation, doc 44 §21 le référence) :
    - l.92 « **DÉCISION V1 (mise à jour) : embedding LOCAL Qwen3-Embedding par défaut.** »
    - l.101 « Model: Qwen3-Embedding (local, GPU-served) », l.431 « `EMBEDDING_MODEL=Qwen3-Embedding` »
  - `00_DOCS_MASTER_INDEX.md` l.49 : « Doc 38 : embedding V1 = **bge-m3 local** par défaut (privacy), cloud en secours. »
  - `99_REGLES_NOMENCLATURE_DOCS.md` l.90 : « corriger le doc 38 qui déclarait OpenAI cloud en V1 default. **bge-m3** devient le défaut V1. »
- **Nature :** **contradiction**, pas une simple formulation. Trois docs nomment
  deux modèles V1 par défaut différents (Qwen3-Embedding vs bge-m3). L'index et la
  doc de nomenclature ont figé une décision (bge-m3) que le doc 38 a depuis
  remplacée par Qwen3-Embedding, sans répercuter le changement.
- **Impact :** ambiguïté directe sur quel modèle héberger en V1 ; risque
  d'incohérence d'embeddings (doc 09 §… exige un modèle stable « for the lifetime
  of pgvector_memory »).
- **Atténuation :** la **dimension** reste cohérente partout (`vector(1024)`,
  doc 38 l.102/184), donc le schéma 05/09 n'est pas cassé — le conflit porte sur le
  **nom du modèle**, pas sur la dimension.
- **Action :** trancher (Qwen3-Embedding selon le doc le plus récent = autorité) et
  réaligner `00_DOCS_MASTER_INDEX` l.49 et `99_REGLES_NOMENCLATURE` l.90.

## Issues MEDIUM

### M1 — Méta-audit `99_AUDIT_COHERENCE_DOCS.md` périmé — **MINEUR (à réaligner)**
- **Doc concerné :** `99_AUDIT_COHERENCE_DOCS.md` (daté 2026-06-12).
- **Citations :** l.35/99 référencent « `45_USER_OBJECTIVES_FEATURE.md` » (renommé
  `F01` depuis, cf. index l.47 et nomenclature l.65) ; l.66 décrit l'embedding V1
  comme « **text-embedding-3-small (cloud)**, avec bge-m3 local en fallback V2 ».
- **Nature :** **non-contradiction au sens strict** (c'est un audit historique qui
  reflète l'état d'avant la décision), mais il contient des affirmations
  aujourd'hui **superséd ées** sur deux sujets (nom du doc F01, modèle embedding).
  À marquer comme historique ou à réaligner pour ne pas être pris pour l'état courant.

### M2 — Modèle de données `projects`/`routines` du doc 71 non réconcilié avec le schéma 05 — **MINEUR (à trancher)**
- **Docs concernés :** `71_IMPERIUM_OPERATIONS_TAB.md` §8 (l.186-203) vs
  `05_DATABASE_SCHEMA.md`.
- **Constat :** le doc 71 propose des tables `projects`, `routines`,
  `routine_daily_checks`, mais `05_DATABASE_SCHEMA.md` ne contient **aucune** table
  `projects`/`routines` (grep : seules des « projection » read-only). Le doc 71 le
  **signale lui-même** (« À réconcilier avec 05 », §8 et §11), donc ce n'est pas une
  contradiction silencieuse — c'est un point ouvert à clore avant implémentation.

### M3 — Fichiers `.bak` actifs à côté des docs vivants — **MINEUR (viole la règle de versionnement)**
- **Docs concernés :** `30_AI_ROUTING_AND_SCORING_POLICY.md.bak`,
  `32_WR_INTERACTIVE_WORKFLOW.md.bak`.
- **Nature :** contredit `99_REGLES_NOMENCLATURE_DOCS.md` §3 (« fini les `_v2` …
  on écrase le fichier, Git garde l'historique », « Interdit : garder deux fichiers
  actifs pour le même contenu »). Les `.bak` sont des doublons figés des docs 30/32.
  Risque : un lecteur édite/cite la mauvaise version.

## Issues LOW

- **Trou de numérotation F11** — **MINEUR.** Les F-docs sautent de `F10_TOPOLOGIE_INFRA`
  à `F12_PIPELINE_DESIGN`. `F11` est absent et `F12` n'est **pas** enregistré dans
  le tableau d'attribution de `99_REGLES_NOMENCLATURE_DOCS.md` §5 (qui ne liste que
  F01-F10). À documenter ou combler.
- **Double numéro `00`** — **MINEUR.** `00_DOCS_MASTER_INDEX.md` et
  `00_VISION_GLOBALE.md` partagent le préfixe `00`, ce qui heurte la règle « un
  numéro = un seul document vivant » (nomenclature §2/§7). Acceptable si `00` est
  traité comme espace « méta », mais à clarifier explicitement.
- **Index `00_DOCS_MASTER_INDEX.md` non à jour** — **MINEUR.** Daté 2026-05-24, sa
  section nomenclature n'énumère que `F01-F10` et « 00-58 », alors que le corpus va
  jusqu'à `71` et `F12` ; la section « Next implementation focus » est dépassée.
- **Dates « Last updated » périmées** — **MINEUR.** `70_KNOWLEDGE_INBOX.md`
  (« Last updated 2026-06-08 ») et `71_IMPERIUM_OPERATIONS_TAB.md` (« 2026-06-09 »)
  affichent des dates antérieures à leur contenu réel (références « PATCH 05/07 »,
  mtime fichier 2026-06-18). Métadonnée trompeuse, contenu lui-même cohérent.
- **Référence « doc 00 » ambiguë** — **MINEUR.** `71` cite « core loop (doc 00) »
  alors que deux docs portent le numéro 00 (le core loop est dans
  `00_VISION_GLOBALE`, pas dans l'index).
- **Auto-note non résolue** — **MINEUR.** `70_KNOWLEDGE_INBOX.md` §13 signale une
  référence `IMP.INBOX.MAIN` d'un draft antérieur « à réconcilier » — point ouvert
  assumé, à clore.

## Points positifs

- **Aucune nouvelle écriture croisée app↔app** dans les docs ajoutés. Le grep
  systématique (EMITS / RECEIVES / subscribes / PROVIDES→ / sends to) sur les 90
  fichiers ne fait ressortir, hors des 40/41/42/43 déjà traités le 14/06, que des
  occurrences **bénignes** : `06` (n8n orchestrateur), `30` (n8n→backend), `56`
  (screenshot→user), `57` (« OPUS RECEIVES » = entrée d'un modèle IA, pas un canal
  app↔app). Les 5 violations MAJEURES du 14/06 restent **confinées** à 40/41/42/43.
- **Doc 46 (fuel)** attribue correctement l'écriture au **backend** : §4.4 l.125-127
  « **Backend:** INSERT vault_transactions … INSERT vector_fuel_events » — conforme
  au doc 44 §10 (le service propriétaire/backend écrit), aucune écriture Vector→Vault.
  La réconciliation hebdo §8 passe par un cron n8n + recomputations backend, pas par
  un dialogue d'apps.
- **Doc 70 (Knowledge Inbox)** très aligné sur le doc 44 : « one brain, no app
  tagging » (§2), `entry_app` = provenance et **non** filtre de récupération
  (§10/§2), backend autoritaire, **rien de vectorisé/canonique sans validation
  utilisateur explicite** (§4/§5). Délimite proprement sa frontière avec doc 34
  (médical) et doc 42 (transactions).
- **Doc 71 (Operations)** cohérent : backend source de vérité, **aucune mission
  créée sur cet écran** (§6), validation utilisateur des changements chatbot, et son
  invariant de complétude (« Attention requise », projet inerte) **correspond
  exactement** au doc 44 §5-bis (gate de génération de missions).
- **Gemma** et **n8n AI Agent** sont signalés non-officiels de façon **cohérente**
  partout (30, 31, 32, 35, 44, 18, 51, 04) — pas de régression du routage.

## Recommandations prioritaires

1. **Trancher le modèle d'embedding V1 (H1).** Acter Qwen3-Embedding (doc 38 =
   autorité, le plus récent) et réaligner `00_DOCS_MASTER_INDEX.md` l.49 +
   `99_REGLES_NOMENCLATURE_DOCS.md` l.90 (qui disent encore bge-m3). Vérifier au
   passage que doc 09/05 restent sur `vector(1024)`.
2. **Hygiène de nomenclature (M3 + LOW).** Supprimer les `.bak` (30, 32) conformément
   à la règle de versionnement, enregistrer `F12` et clarifier le trou `F11` dans
   `99_REGLES_NOMENCLATURE_DOCS.md` §5, et statuer sur le double préfixe `00`.
3. **Réconcilier le modèle de données projets/routines (M2).** Confronter
   `71_IMPERIUM_OPERATIONS_TAB.md` §8 à `05_DATABASE_SCHEMA.md` (aucune table
   `projects`/`routines` n'y existe aujourd'hui) avant toute implémentation.

---

## Couverture de l'audit

**Total corpus :** 90 fichiers `.md` dans `docs_master/`.

**Lus / analysés en profondeur (sources de vérité + cibles non couvertes) :**
`_AUDIT_cerveau_commun.md`, `00_DOCS_MASTER_INDEX.md`, `99_REGLES_NOMENCLATURE_DOCS.md`,
`44_BRAIN_UNIFIED_LOGIC.md`, `70_KNOWLEDGE_INBOX.md`, `71_IMPERIUM_OPERATIONS_TAB.md`,
`46_VECTOR_FUEL_SMART_TRACKING.md`, `38_VECTORIZATION_PIPELINE.md`,
`09_PGVECTOR_MEMORY_POLICY.md`, `05_DATABASE_SCHEMA.md`, `30_AI_ROUTING_AND_SCORING_POLICY.md`.

**Couverts par grep systématique sur les 90 fichiers** (patterns d'écriture croisée
app↔app, concepts périmés Gemma/n8n-AI-Agent/36_OPUS/embedding, nomenclature,
références à docs renommés/supprimés). Aucun signal nécessitant une lecture intégrale
n'est ressorti pour : 48-58 (séries Vector/Path/UI), 59-69 (design system + specs
frontend), F02-F12.

**Délibérément exclus de la lecture intégrale (et pourquoi) :**
- `59_DESIGN_SYSTEM_V1_DRAFT` → `69_FRONTEND_API_MAPPING_V1` : docs de design
  system / specs frontend, sans logique cerveau ni interaction app↔app ; déjà
  couverts par `99_AUDIT_COHERENCE_FRONTEND.md`. Grep cross-app = vide.
- `48-51, 54, 55, 58` : docs de feature/UI de domaine ; grep cross-app = vide.
- `56_AUTONOMOUS_CODING_ORCHESTRATOR`, `57_VECTOR_RIDE_SCORING_ML` : orchestrateur
  de codage / ML de scoring ; seuls patterns trouvés = E/S de modèle IA (bénins).
- `F02-F12` : specs de features **futures** (non implémentées) ; grep cross-app et
  refs périmées = vide. Lecture intégrale non justifiée pour un audit de cohérence
  du noyau validé.
- `01-37` (hors 05/09/30/38) : noyau largement couvert par l'audit du 14/06 et par
  `99_AUDIT_COHERENCE_DOCS.md` ; seules les sources de vérité y ont été relues.

**En cas de doute, le doc a été inclus** (ex. 46, 70, 71 lus intégralement même si
partiellement adjacents au périmètre du 14/06).
