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
