# PATCH_WR — Amendements d'étape 0 pour WR_CONTINUOUS_ENGINE_SPEC_V1

Source : audit toolbox 2026-07-10 (`gap_analysis_v1/toolbox/`). Amendements d'étape 0 uniquement.

## W-0. Lecture obligatoire à l'étape 0
Ajouter aux lectures §0 : `TOOLBOX_CATALOG_DRAFT.md` + `TOOLBOX_FINDINGS.md`. Vérification
anti-doublon au catalogue avant toute création, consignée dans WR_MAPPING.md.

## W-1. La danse de migration disparaît (confirme le pré-inventaire)
§0.3 cas particulier « Si la passe Pulse a déjà créé pulse_ai_transition… » : SUPPRIMÉ. La passe
Pulse (PATCH_PULSE P-1) crée directement `ai_slot_transition`/`ai_audit_samples` partagées.
L'étape 0 WR se contente de VÉRIFIER leur présence et d'y seeder les 10 slots `wr.*` (§13.1).

## W-2. Plus de fallback `wr_signal_definitions` (confirme le pré-inventaire)
§4 W4 : les définitions de signaux partagées (`signal_definitions`/`signal_values`, colonne
domain) existent depuis la passe Pulse (PATCH_PULSE P-1). Le fallback « sinon table équivalente
wr_signal_definitions » est SUPPRIMÉ. Si la passe Pulse n'a pas eu lieu (ordre modifié), créer la
table PARTAGÉE, jamais une table wr_.

## W-3. Paramètres : table partagée
§13.2 : les paramètres `wr.*` (chain_window_days, belief_alpha, docket_halflife…) vont dans la
table de paramètres partagée créée à la passe Pulse (PATCH_PULSE P-1 / FINDINGS DBL-4).

## W-4. ai_memories : ne pas ALTER le hub sans arbitrage (FINDINGS C-2 / DV-1 / Q5)
§3.4 : le schéma canonique `ai_memories` vient d'être posé (migration `20260705_0032`,
propriété de schéma = doc 05, PHASE_0 « Décisions mémoire »).
- Le décrément par « exposition non confirmée » et `status_multiplier` CONTREDISENT doc 75
  (« confidence ne descend jamais toute seule », verrouillé) → QUESTION UTILISATEUR Q5, à
  trancher AVANT cette étape.
- Tant que Q5 n'est pas tranchée : utiliser l'option « table compagnon 1-1 » (déjà prévue par la
  spec §3.4) pour les champs de cycle de vie (statement_canonical, occurrences, last_confirmed_at,
  last_exposed_at, context_predicate, status_multiplier, review_due_at, parent_pattern_id) —
  le hub reste intact ; `v_memories_active` joint les deux.
- Toute évolution du schéma passe par une mise à jour du doc 05 dans la même passe (D1).

## W-5. Table events canonique + curseurs généralisables
§0.2 : la table events canonique post-E3 est **`events`** (depth ajouté migration 0036 ;
`imperium_events` dépréciée, routes marquées deprecated). Le mécanisme
`wr_worker_runs`/`wr_worker_cursors` est le prototype du contrat de consommation d'events du
système entier (FINDINGS §4) : le construire dans `toolbox.runner` (tables génériques `job_runs`/
`job_cursors` avec worker namespacé) plutôt qu'en tables wr_ — Daily (§10.2 agrégation) et Vector
(§4.8) brancheront leurs jobs dessus.

## W-6. Docket = table canonique partagée dès la création
§3.1 `wr_docket_items` : consommée par Daily (§8.2, §10.2), Vector (§4.8, §6) et Pulse (P6).
La déclarer canonique au doc 05 dès sa création ; envisager le nom conforme convention PHASE_0
(`review_docket_items`) — décision de nommage à consigner dans WR_MAPPING.md.

## W-7. Notifications rouges
§7 / §13.7 : « canaux de notification existants réutilisés (identifier) » — il n'existe AUCUN
canal (stub vide, FINDINGS T1). Consommer `toolbox.notifications` ; si non livré, table
`notifications` en attente, pas de canal ad hoc.

## W-8. Client LLM et extraction : réutiliser, ne pas recréer
- §15.3 : le wrapper LLM contraint est `toolbox.llm` livré par la passe Pulse (PATCH_PULSE P-6).
- §6 (extraction + confrontation d'identité) : construire comme librairie PARTAGÉE
  (`toolbox.extraction`, FINDINGS C-3) — le chatbot (doc 72 §6) la consommera avec sa grille
  éditable ; ne pas coder deux extracteurs.

## W-9. Plan mensuel : remplace doc 52 §8 (sous réserve Q8)
§3.5/§8 : `plan_versions` devient LE plan 4 semaines. Le patch docs de fin de passe (§15.8)
inclut un renvoi dans doc 52 §8 (« la génération/régénération du plan est définie par ce doc »)
— sous réserve de la réponse à Q8 (FINDINGS DBL-5).

## W-10. Étape 0 — état des lieux corrigé
Les rollups W1 « alignés sur les agrégats pré-calculés de la plomberie WR existante » : attention,
`dashboard.py`/`weekly_report.py` lisent encore les tables LEGACY (vault_transactions,
imperium_path_items, imperium_priority_rules — FINDINGS C-1). Migrer ces lecteurs vers les
canoniques AVANT de construire W1 dessus (ou dans le même geste, consigné au mapping).
