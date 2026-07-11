# EXECUTION_ORDER_PROPOSAL — Ordre des passes recommandé

Date : 2026-07-10. Audit toolbox (lecture seule). Hypothèse de départ fournie :
Toolbox → Pulse → WR → Daily → Vector, contrainte WR-avant-Daily. **L'audit CONFIRME cet ordre**
et le précise : il ajoute un contenu concret à la passe « Toolbox » (socle), une mini-passe
Vault-déterministe optionnelle mais fortement recommandée avant Daily, et une passe Path
(prières) hors chemin critique.

## Ordre recommandé

```
0. SOCLE TOOLBOX (nouveau contenu, chiffré par cet audit)
   0a. toolbox.runner (T2)            — mini-spec + implémentation (APScheduler +
       LISTEN/NOTIFY + advisory locks, tables job_runs/job_cursors génériques)
   0b. toolbox.notifications (T1)     — mini-spec (canal = Q3) + table + notify()
   0c. tables partagées d'emblée      — parameters, signal_definitions/values,
       ai_slot_transition/ai_audit_samples (+ v_ai_training_pairs)   [DBL-2/3/4]
   0d. toolbox.embeddings serving (T4) — qwen3-embedding:8b sur P40 + embedding.py
       (débloque D5 → commit mémoire → usine WR)   [dépend des GPU, phase 2 F10]
   0e. interface toolbox.travel v0 + geo/H3 (DBL-1, T6) — signature seulement +
       impl Google/plancher/cache (peut glisser dans la passe Daily si préféré)
   0f. migration des lecteurs legacy (C-1) — dashboard.py / weekly_report.py vers
       ledger canonique + habits + user_priorities (pré-requis des rollups W1)
   0g. promotion du catalogue : TOOLBOX_CATALOG_DRAFT → doc canonique (Q13)

1. PULSE  (avec PATCH_PULSE : crée les tables partagées, pas de pulse_*)
2. WR     (avec PATCH_WR : plus de danse de migration, plus de fallback signaux,
           Q5 tranchée avant le §3.4 croyances)
3. DAILY  (avec PATCH_DAILY : consomme toolbox.travel, docket, v_plan_current)
4. VECTOR (avec PATCH_VECTOR : renforce toolbox.travel, Q1/V-2 résolus avant)
```

## Justification des contraintes

- **WR avant Daily — CONFIRMÉ, trois dépendances dures** : Daily §8.4 réutilise « telle quelle »
  la mécanique choc WR §8.1 (plan_versions origin=shock_regen) ; Daily §8.2/§10.2 écrivent des
  items docket (table WR §3.1) ; Daily §0.5 lit `v_plan_current` (vue WR §3.5). Sans WR, Daily
  devrait poser trois tampons.
- **Pulse avant WR — confirmé, deux dépendances souples** : W1 « lit les tables Pulse si la passe
  est faite, sinon stub neutre » (spec WR §4) ; le wrapper LLM contraint naît en Pulse (WR §15.3
  « réutiliser le wrapper Pulse si présent »). L'inverse marcherait (stubs prévus) mais
  gaspillerait la généralisation P-1.
- **Vector en dernier — confirmé** : dépend du docket/usine (§4.8), des paramètres partagés, et
  de deux préalables externes non résolus (Q1 repo introuvable ; V-2 historique de courses non
  localisé dans les migrations — candidat STOP §0.2). Le placer en dernier laisse le temps de
  résoudre Q1/V-2 sans bloquer le reste.
- **Socle d'abord** : sans 0a-0c, chaque passe re-tranche « n8n ou cron ? », recrée ses tables
  pulse_/wr_/df_ et bute sur le stub notifications. Coût du socle : essentiellement du S/M
  (FINDINGS §6 R0) contre trois migrations de généralisation évitées.

## Ce que Path et Vault changent à l'ordre (mission : angles morts)

L'audit révèle des dépendances mais AUCUNE qui inverse l'ordre des 4 passes :

- **Vault-déterministe (recommandé AVANT Daily, en parallèle de Pulse/WR)** : le moteur de
  pression (doc 11, F1-17), `upcoming_expenses` (F2-15) et le profit hebdo (F2-16, Q9) sont
  100 % déterministes, codables sans GPU (GAP_vault), et alimentent : les rollups W1 (« flux,
  pression », spec WR §4), le plan 4 semaines (doc 52 §8.2 CATEGORY 2), la sadaqa Path
  (doc 41 §9.2 — aujourd'hui sans source de données), et le doc 43 morning_plan. Sans cette
  mini-passe, W1 rollup finance = flux bruts sans pression, et la base sadaqa reste vide.
  Elle ne bloque PAS les 4 passes (stubs possibles) mais son absence dégrade WR et le plan.
- **Path (prières) — passe dédiée, hors chemin critique des 4** : toolbox.prayer (F1-16,
  « déterministe qui doit être EXACT ») n'est consommé par aucune des 4 specs. MAIS la réponse
  à Q6 (prières = engagements fixes du Daily) peut créer une dépendance Daily→prayer EN LECTURE :
  si Q6 = oui, livrer au minimum les fenêtres de prière (MAWAQIT + fallback) avant ou pendant la
  passe Daily ; sinon, passe Path après Vector. Q2 (geo religieux) doit être tranchée avant de
  figer l'interface toolbox.travel (0e) — pour ne pas concevoir une interface que Path ne pourra
  pas utiliser (contrainte privacy very_high).
- **n8n → runner** : les 3 workflows n8n existants (WR dry-run) ne bloquent rien ; leur sort est
  dans N8N_INVENTORY.md. La sortie de n8n se fait naturellement : aucun NOUVEAU workflow n8n
  dans les passes (patches P-3/W-5/D-6/V-8), et le pont WR dry-run est porté/retiré à la passe WR.

## Points de décision à résoudre avant de lancer (ordre de blocage)

| avant | questions |
|---|---|
| Socle 0b | Q3 (canal notifications) |
| Socle 0e | Q2 (geo religieux → interface travel) |
| Passe Pulse | Q13 (promotion catalogue) — souhaitable, pas bloquant |
| Passe WR §3.4 | Q5 (croyances vs doc 75) — bloquant pour l'étape croyances |
| Passe WR §8 | Q8 (plan mensuel 52 §8 vs plan_versions) |
| Passe Daily G4 | Q6 (prières en engagements fixes) |
| Passe Vector étape 0 | Q1 (repo companion), V-2 (historique courses) — bloquants |
| Mini-passe Vault | Q4 (échelle pression), Q9 (profit hebdo), Q10 (anomalies→docket) |
```
