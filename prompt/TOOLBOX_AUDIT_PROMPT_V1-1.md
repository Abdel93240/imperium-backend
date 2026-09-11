# AUDIT — IMPERIUM TOOLBOX (LECTURE SEULE)

> **Prompt d'audit destiné à Claude Code (Fable 5)** sur Tower, avec accès à `/opt/imperium-backend`,
> `/opt/orchestrator`, le repo `vtc-companion-app`, et l'intégralité de `docs_master/` +
> `gap_analysis_v1/`. Mission : produire l'inventaire exhaustif et sourcé des OUTILS du système
> et de leurs CONSOMMATEURS, à travers les cinq applications de façade et le cerveau commun.
> **Cet audit ne modifie rien** : il lit, il compte, il source, il livre des documents.

---

## 0. CONTEXTE ET RÔLE

Imperium est un écosystème à cerveau commun (« le système ») exposé par cinq façades :
**Imperium** (centre de commande), **Pulse** (santé), **Vector** (assistant VTC),
**The Path** (gestion du religieux), **Vault** (finances). Quatre specs d'implémentation
one-pass ont été rédigées et ne sont PAS encore exécutées : Pulse Intelligence Layer,
WR Continuous Engine, Daily Orchestrator, VTC Assistant Vector (localiser les fichiers —
demander leur emplacement à l'utilisateur si introuvables).

Une couche « Imperium Toolbox » va être créée : capacités réutilisables, cataloguées,
contractualisées. Un pré-inventaire partiel (mené en conversation, vision limitée aux
domaines Pulse/WR/Daily/Vector) a identifié ~28 entrées et AU MOINS un doublon franc
(l'estimation de trajet, spécifiée deux fois). Ton audit remplace ce pré-inventaire par
la vérité du terrain — notamment tout ce qui concerne **The Path** et **Vault**, angles
morts connus du pré-inventaire.

**INTERDITS ABSOLUS** : aucune modification de code, aucune migration, aucune modification
des quatre specs ni d'aucun doc existant. Tes seules écritures : les livrables du §4, rangés
selon la convention d'audit existante (AUDIT_INDEX) — à défaut `gap_analysis_v1/toolbox/`.
Aucune affirmation sans référence (chemin de fichier exact, numéro de doc + section, table
SQL). Ce qui n'est pas vérifiable est marqué `HYPOTHÈSE`. Un besoin de consommateur non
documenté n'est pas inventé : il devient une `QUESTION UTILISATEUR`.

---

## 1. DÉFINITION D'UN « OUTIL » POUR CET AUDIT

Trois familles :
- **F1 — Librairies/services de code** : capacité appelable (estimation de trajet, moteur de
  signaux, client LLM contraint, OCR, embeddings/top-K, utilitaires H3, solveur, émetteur
  d'events E2, notifications, framework de caches poussés, harnais d'entraînement GBM…).
- **F2 — Tables/vues canoniques partagées** : structures consommées par plusieurs domaines
  (events post-E3, paramètres versionnés, ai_slot_transition, ai_audit_samples,
  wr_docket_items, ai_memories, imperium_user_priorities, définitions de signaux…).
- **F3 — Modèles servis** : ML/IA avec registre et consommateurs (CatBoost acceptation,
  modèles de zones, prédicteur surge, endpoints 32B/embedding/reranker, futurs LoRA et
  CatBoost routeur…).

N'est PAS un outil : la logique métier d'un domaine avec un seul consommateur plausible.
Ces cas sont listés à part comme **candidats dormants** (règle du second consommateur :
extraction seulement quand un deuxième domaine en a besoin).

---

## 2. CORPUS À LIRE (exhaustif, dans cet ordre)

1. `docs_master/` en INTÉGRALITÉ — attention particulière : doc 30 (routage), doc 40 (Pulse),
   doc 52 (decision framework), doc 77 (catalogue d'events), et TOUS les docs relatifs à
   The Path et Vault, quels que soient leurs numéros.
2. `gap_analysis_v1/` (DECISIONS_events, CONCEPTION_chainage_V2, CONCLUSIONS_test_papier,
   audits existants).
3. Les quatre specs one-pass (emplacement fourni par l'utilisateur).
4. Le code réel : `/opt/imperium-backend` (services, modules, jobs), `/opt/orchestrator`,
   `vtc-companion-app`. Greps ciblés minimum : durée/trajet/distance/haversine/H3, OCR,
   embedding/vector/top-k, notification/push/telegram, cache, param/setting/config,
   prayer/salat/path, finance/vault/forecast/pression.
5. Le schéma Postgres RÉEL (`information_schema`) — comparer aux docs : toute table
   partagée non documentée est un finding.
6. La liste des workflows n8n actifs.

---

## 3. MÉTHODE (quatre passes)

**Passe 1 — Inventaire brut.** Docs + greps → liste candidate d'outils, sans filtre.

**Passe 2 — Fiche par outil.** Pour chaque candidat :
```
nom_propose: toolbox.<x> | table canonique | modèle
description: 1 ligne
famille: F1|F2|F3
vit_aujourd_hui: chemins/tables EXACTS (ou "spécifié non codé: spec X §Y" ou "MANQUANT")
consommateurs_actuels: [(app|système, référence source)]
consommateurs_prevus_par_specs: [(spec, §)]
consommateurs_probables_non_documentés: [(app, raisonnement)] → QUESTION UTILISATEUR
doublons: chemins exacts des implémentations multiples, différences résumées
seconde_regle_consommateur: PASSE | ATTEND (dormant)
statut: existe_codé | spécifié | manquant | dupliqué
```

**Passe 3 — Matrice apps × outils.** Tableau croisé : les cinq façades + « système »
(usine WR, orchestrateur, routage) en colonnes, les outils en lignes, cellules =
consomme / devrait consommer (sourcé) / question. **Objectif explicite : révéler ce que
The Path et Vault consomment ou devraient consommer** — trajets (horaires de prière ?
déplacements mosquée ?), notifications, signaux/anomalies financières, paramètres,
events, mémoire. Chaque « devrait » non sourcé = question, pas affirmation.

**Passe 4 — Findings.** (a) Doublons avec chemins et recommandation d'unification ;
(b) trous : outils référencés par plusieurs specs que personne ne spécifie (le
pré-inventaire en a repéré un : les notifications — confirmer et chercher les autres) ;
(c) couplages cachés (un domaine qui importe le code d'un autre sans passer par une
interface) ; (d) tables partagées de fait mais non canonisées ; (e) divergences
docs ↔ code réel.

---

## 4. LIVRABLES (les seules écritures autorisées)

1. **`TOOLBOX_CATALOG_DRAFT.md`** — le catalogue : trois familles, une fiche par outil
   (format passe 2), la matrice apps × outils, la liste des dormants. C'est le brouillon
   du futur `TOOLBOX_CATALOG.md` canonique ; il sera validé par l'utilisateur avant
   promotion.
2. **`TOOLBOX_FINDINGS.md`** — doublons, trous, couplages, divergences, chacun avec
   références + effort estimé (S/M/L) + impact ; recommandations d'extraction classées
   (règle du second consommateur appliquée) ; **liste des QUESTIONS UTILISATEUR** en tête
   de document.
3. **`patches/`** — quatre fichiers d'amendement d'étape 0 (un par spec :
   PATCH_PULSE.md, PATCH_WR.md, PATCH_DAILY.md, PATCH_VECTOR.md) : uniquement les
   changements rendus nécessaires par le catalogue (tables partagées créées en amont,
   consommation de toolbox.travel/signals, lecture obligatoire du catalogue en étape 0).
   Base de départ fournie par le pré-inventaire : Pulse crée directement les tables
   partagées ; WR perd sa danse de migration pulse_→partagées et son fallback
   wr_signal_definitions ; Daily consomme toolbox.travel dans G4 ; Vector référence
   toolbox.travel au lieu de le construire (§3.5/§4.1). À CONFIRMER ou corriger par tes
   lectures.
4. **`EXECUTION_ORDER_PROPOSAL.md`** — l'ordre des passes recommandé (hypothèse de
   départ : Toolbox → Pulse → WR → Daily → Vector, contrainte WR-avant-Daily), avec ce
   que ton inventaire y change, notamment si The Path ou Vault révèlent des dépendances.
5. **`N8N_INVENTORY.md`** — contexte : décision prise de sortir n8n du chemin de production
   (runner Python unique dans le backend : APScheduler + LISTEN/NOTIFY + advisory locks,
   futur `toolbox.runner`). Pour chaque workflow n8n actif ou dormant : nom, déclencheur,
   fonction, systèmes touchés, date du dernier run, verdict `porter` (effort S/M/L, job
   backend cible) ou `tuer` (mort/redondant, preuve). C'est la liste de migration.
6. Une ligne ajoutée à l'AUDIT_INDEX selon la convention existante.

**Réponse chiffrée obligatoire en tête de TOOLBOX_CATALOG_DRAFT.md** : « Le système compte
N outils : N1 en F1 (dont X codés, Y spécifiés, Z manquants, W dupliqués), N2 en F2,
N3 en F3, plus D dormants » — chaque nombre traçable jusqu'aux fiches.

## 5. DEFINITION OF DONE

Les six livrables écrits et rangés ; zéro autre fichier touché (git status propre hors
livrables) ; chaque affirmation sourcée ou marquée HYPOTHÈSE ; les questions utilisateur
regroupées et numérotées ; les angles morts The Path et Vault explicitement couverts ou
explicitement déclarés non documentés.
