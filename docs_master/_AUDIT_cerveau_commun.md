# Audit cerveau commun unifié — cohérence avec doc 44

**Mode :** audit lecture seule. Aucun fichier source modifié.
**Source de vérité :** `44_BRAIN_UNIFIED_LOGIC.md` (fait autorité).
**Date :** 2026-06-14
**Périmètre :** tous les fichiers de `docs_master/`.

---

## Résumé exécutif

L'écosystème est globalement décrit selon le bon modèle (cerveau commun + lecture
de la mémoire partagée), mais plusieurs documents de domaine (40 Pulse, 41 Path,
42 Vault, 43 Imperium) décrivent encore les apps comme des **acteurs qui
s'échangent des données directement** (« X EMITS→Y », « Y RECEIVES←X »,
« X subscribes to Y »). Cinq cas constituent des **écritures croisées / canaux
app↔app** qui contredisent §9, §10 et §19 du doc 44 et doivent être reformulés en
règles déterministes du backend écrivant la mémoire commune. Le reste relève de
formulations « lit depuis / fournit à » techniquement inoffensives mais à
réaligner sur le vocabulaire « lit la mémoire commune ».

---

## Issues CRITICAL

Aucune. (Pas de faille de sécurité ; il s'agit d'incohérences documentaires.)

---

## Issues HIGH — Violations MAJEURES (écriture croisée / canal app↔app)

### M1 — Pulse écrit dans le domaine Vault
- **Fichier / section :** `42_VAULT_LOGIC_DETAIL.md` — §15.2 « With Pulse » — **lignes 423-424**
- **Citation :** « Vault RECEIVES←Pulse: food purchases parsed from receipts (**automatic Vault-expense creation**) »
- **Pourquoi ça viole le doc 44 :** présente Pulse comme produisant/poussant des
  écritures dans `vault_transactions`, table **possédée par Vault**. Viole §10
  (« SEUL le service propriétaire écrit ses tables ») et §19 (« ❌ Apps writing to
  each other's tables »). Contredit aussi le doc 40 §15.3 qui décrit le même flux
  reçu (sens Vault→Pulse pour le stock) → incohérence interne.
- **Reformulation suggérée :** « Lors de la validation d'un ticket (VAU-05), le
  **backend** crée la dépense alimentaire dans la table Vault (Vault reste
  propriétaire) ET crée un handoff stock vers Pulse. Aucune app ne pousse
  d'écriture dans Vault ; c'est une règle déterministe du cerveau. »

### M2 — Vector écrit dans le domaine Vault
- **Fichier / section :** `42_VAULT_LOGIC_DETAIL.md` — §15.3 « With Vector » — **lignes 434-436**
- **Citation :** « Vault RECEIVES←Vector: VTC session revenue (**business income logged automatically**) … Fuel events »
- **Pourquoi ça viole le doc 44 :** décrit Vector écrivant des revenus dans Vault.
  Viole §10/§19. Le doc 44 §18 est explicite : « Vault may receive confirmed
  income **only through an allowed backend flow** ».
- **Reformulation suggérée :** « À la fin d'une session VTC, le **backend** (service
  Vault) écrit le revenu confirmé dans les tables Vault. Vector ne fait qu'écrire
  ses propres tables opérationnelles ; il ne crée pas de transaction Vault. »

### M3 — Path écrit une dépense dans le domaine Vault
- **Fichier / section :** `41_PATH_LOGIC_DETAIL.md` — §16.2 « With Vault » — **lignes 707-708**
- **Citation :** « **Path EMITS→Vault:** confirmed sadaqa donations (**logged as personal expense**, category Sadaqa) »
- **Pourquoi ça viole le doc 44 :** Path pousse une écriture (dépense) dans le
  registre financier de Vault. Viole §10/§19.
- **Reformulation suggérée :** « Quand l'utilisateur confirme un don de sadaqa, le
  **backend** enregistre l'action côté Path (propriétaire de l'état sadaqa) et le
  service Vault écrit la dépense correspondante (catégorie Sadaqa). Deux écritures
  par règle backend, pas un envoi Path→Vault. »

### M4 — Réciproque de M3, vue côté Vault
- **Fichier / section :** `42_VAULT_LOGIC_DETAIL.md` — §15.1 « With Path » — **lignes 416-417**
- **Citation :** « Vault RECEIVES←Path: sadaqa_donations (**logged as personal expense in Vault**) »
- **Pourquoi ça viole le doc 44 :** même écriture croisée que M3, décrite depuis
  Vault. À corriger conjointement avec M3.
- **Reformulation suggérée :** « Le backend écrit la dépense Sadaqa dans Vault
  lorsqu'un don est confirmé côté Path ; il n'y a pas de transfert direct
  Path→Vault. »

### M5 — Canal direct Path→Pulse (push d'état entre apps)
- **Fichier / section :** `41_PATH_LOGIC_DETAIL.md` — §16.3 « With Pulse » — **lignes 715-721**
- **Citation :** « **Path EMITS→Pulse:** fasting_active / fasting_type / fasting_window / hydration_limits … Pulse reads these to adapt… »
- **Pourquoi ça viole le doc 44 :** décrit un canal direct Path→Pulse (§9 « No
  Inter-App Communication Layer », §19 « ❌ app-to-app HTTP calls »). Contredit en
  plus le doc 40 §15.2 qui décrit **correctement** « Pulse READS from Path » la
  même donnée. Le sens « EMITS→ » est de trop.
- **Reformulation suggérée :** « Path écrit son état de jeûne dans ses propres
  tables (mémoire commune). Pulse **lit** cet état depuis la mémoire commune pour
  adapter repas/entraînement/hydratation. » (supprimer la formulation « Path EMITS
  to Pulse »).

---

## Issues MEDIUM — Violations MINEURES (formulation à reformuler, techniquement inoffensive)

> Ces cas ne créent ni écriture croisée ni canal réel : ils décrivent des
> lectures de mémoire commune (autorisées §10) ou des événements backend append-only
> (autorisés §9), mais avec un vocabulaire « X EMITS / RECEIVES / subscribes to Y »
> qui présente une app comme dialoguant avec une autre. À réaligner sur « lit la
> mémoire commune » / « le backend émet un événement, l'app le lit ».

| # | Fichier — section | Ligne | Citation courte | Reformulation suggérée |
|---|---|---|---|---|
| m1 | `43_IMPERIUM_LOGIC_DETAIL.md` §12.1 | 399-402 | « Imperium **IS the consumer of all events** … Imperium SUBSCRIBES to: path.* / pulse.* / vault.* / vector.* » | « Imperium **lit** les événements backend append-only (§9) et réagit (replan, log). Les noms pointés sont des événements du cerveau, pas des envois d'app à app. » |
| m2 | `40_PULSE_LOGIC_DETAIL.md` §15.1 | 449 | « **Pulse READS from Imperium:** imperium_morning_checkins… » | « Pulse **lit la mémoire commune** (imperium_morning_checkins) via le backend. » |
| m3 | `40_PULSE_LOGIC_DETAIL.md` §15.1 | 454 | « **Pulse EMITS events Imperium subscribes to** » | « Le backend émet des événements append-only ; Imperium les lit. » |
| m4 | `40_PULSE_LOGIC_DETAIL.md` §15.2 | 464 | « **Pulse READS from Path:** fasting_active… » | « Pulse lit l'état de jeûne dans la mémoire commune. » |
| m5 | `40_PULSE_LOGIC_DETAIL.md` §15.3 | 480 | « **Pulse READS from Vault:** food_related_expenses » | « Pulse lit les dépenses alimentaires (mémoire commune, lecture seule). » |
| m6 | `41_PATH_LOGIC_DETAIL.md` §16.1 | 693 | « **Path EMITS events Imperium subscribes to** » | « Le backend émet les événements ; Imperium les lit. » |
| m7 | `41_PATH_LOGIC_DETAIL.md` §16.2 | 704 | « **Path READS from Vault:** weekly_business_profit » | « Path lit le profit hebdo (lecture seule) pour calculer la cible sadaqa. » |
| m8 | `41_PATH_LOGIC_DETAIL.md` §10.2 | 472 | « **Imperium subscribes to event:** path.ghusl.required » | « Imperium lit l'événement backend path.ghusl.required et déclenche un replan. » |
| m9 | `41_PATH_LOGIC_DETAIL.md` §16.1-ADD | 1055 | « Add to the “**Path EMITS events Imperium subscribes to**” list » | Même reformulation que m6 (événements backend lus par Imperium). |
| m10 | `42_VAULT_LOGIC_DETAIL.md` §15.1 | 412 | « **Vault EMITS→Path:** weekly_business_profit, sadaqa basis available » | « Vault écrit le profit hebdo dans ses tables ; Path **lit** cette base sadaqa (lecture seule). » |
| m11 | `42_VAULT_LOGIC_DETAIL.md` §15.3 | 430 | « **Vault PROVIDES context to Vector indirectly** » | « Vector peut lire l'historique de dépenses carburant (mémoire commune) ; pas de canal direct. » |
| m12 | `42_VAULT_LOGIC_DETAIL.md` §15.4 | 442 | « **Vault PROVIDES→Imperium:** pressure_score, week_balance… » | « Imperium **lit** les résumés Vault (autorisé §10) pour dimensionner l'objectif et la pression. » |
| m13 | `F01_USER_OBJECTIVES.md` §14.1 | 541-544 | « **Imperium subscribes to:** user_objective.app_empty » | « Le backend émet l'événement user_objective.app_empty ; Imperium le lit et crée la mission. » |

---

## Issues LOW

- **Incohérence de sens du handoff ticket** entre `40_PULSE` §15.3 (décrit
  Vault→Pulse, stock) et `42_VAULT` §15.2 (décrit Pulse→Vault, dépense). Le ticket
  OCR produit en réalité **deux** écritures distinctes (dépense Vault **et** stock
  Pulse), chacune devant être une règle backend écrivant la table de son propre
  domaine. À harmoniser pour éviter l'impression d'un dialogue bidirectionnel
  entre les deux apps.
- Le titre récurrent « **Integration With Other Modules** » (docs 40, 41, 42, 43,
  F01) invite mécaniquement à décrire des échanges app↔app. Envisager un titre du
  type « Lectures et événements via la mémoire commune » pour cadrer le vocabulaire.

---

## Points positifs

- `44_BRAIN_UNIFIED_LOGIC.md` est clair, complet et non ambigu (§9, §10, §16, §18, §19).
- `40_PULSE_LOGIC_DETAIL.md` §15.3 décrit correctement le handoff ticket comme
  « **backend** creates a Pulse handoff » (règle backend, pas dialogue app↔app) —
  conforme à l'exception OCR autorisée.
- `40_PULSE_LOGIC_DETAIL.md` §15.4 et `41_PATH_LOGIC_DETAIL.md` §16.4 maintiennent
  explicitement Vector découplé (pureté profitabilité VTC), conformes au doc 44 §11.
- `06_N8N_WORKFLOWS.md` (l.96, « n8n subscribes to canonical dotted event names »)
  est conforme : n8n est orchestrateur lisant les événements backend, pas un canal
  app↔app — **non signalé**.
- `52_AI_DECISION_FRAMEWORK.md` §14 et `F01_USER_OBJECTIVES.md` §14.2 décrivent des
  références **doc-à-doc** et des requêtes **backend** (pas d'échange app↔app) —
  **non signalés**.

---

## Recommandations prioritaires

1. **Corriger les 3 écritures croisées financières (M1, M2, M3/M4)** dans `42_VAULT`
   §15.2/§15.3/§15.1 et `41_PATH` §16.2 : reformuler tout « RECEIVES← / EMITS→ »
   en « le **backend** écrit la table du domaine propriétaire » (sadaqa, revenu VTC,
   dépense ticket), conformément au doc 44 §10/§18/§19.
2. **Supprimer le canal direct Path→Pulse (M5)** dans `41_PATH` §16.3 : remplacer
   « Path EMITS→Pulse » par « Pulse **lit** l'état de jeûne en mémoire commune »
   (cohérent avec `40_PULSE` §15.2 qui est déjà correct).
3. **Réaligner le vocabulaire d'événements** (m1, m3, m6, m8, m9, m13) : remplacer
   « X subscribes to Y » / « X EMITS events » par « le backend émet un événement
   append-only ; l'app le lit » — et envisager de renommer les sections
   « Integration With Other Modules » pour décourager le réflexe app↔app.
