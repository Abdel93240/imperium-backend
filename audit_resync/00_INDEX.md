# Campagne d'audit RESYNC — code backend ↔ doc (juin 2026)
> Resynchronisation ponctuelle du code backend avec la doc consolidée (post-stabilisation
> + grande passe nomenclature). Le code a été écrit en mai selon une pensée antérieure ;
> cette campagne mesure et planifie le réalignement, module par module.
> Système NON en production, tables VIDES → aligner ne casse aucune donnée.
>
> Observation : les modules les plus divergents (`ai_memories`, `vault`) sont ceux le
> plus retouchés récemment dans la doc. Les modules plus stables (`path`) sont sains.
> Le backend n'est pas à refaire — il est à resynchroniser et à débrancher du legacy.

## Tableau de bord

| Module | Migration(s) | Verdict | Action | Statut |
|---|---|---|---|---|
| ai_memories | 0017 | (c) divergent | réaligner sur doc 75 (table vide, schéma vectoriel manquant) | audité, à corriger |
| missions | 0005,0019,0020,0021,0023 | (c) divergent — MAIS module SAIN : cœur du scoring codé (`intrinsic_score`, `domain_coefficient` ×10/8/5/4, `mission_type_category` cat_a-i, index "1 seule active/user" conforme). Écarts = renommages + couches futures non codées + 1 choix design. | réconcilier docs 52/43 et schéma missions/scores; créer ou déclasser outcomes/durations | schéma audité (partie 2a). Reste : logique service `missions.py` (partie 2b) |
| vault | 0007,0024,0025,0026 | (c) divergent — DEUX LEDGERS coexistent et sont TOUS DEUX actifs : `vault_transactions` (legacy, `/api/vault`, decimal, doc 27) ET `imperium_vault_transactions` (récent, `/api/imperium/vault`, cents, reversals, doc 04). ⚠️ RISQUE : `dashboard.py` et `weekly_report.py` lisent encore l'ANCIEN ledger → chiffres financiers potentiellement incohérents selon l'écran. Le ledger récent est bien fait (reversals, append-only API, 1 reversal/original garanti). | choisir `imperium_vault_transactions` comme canonique, migrer les lecteurs restants, supprimer le legacy (tables vides) | audité, à corriger (décision ledger requise) |
| path | 0008,0027 | (b) léger décalage — module SAIN. Path V1 habits/check-ins propre : code cohérent, invariants codés (pas de check-in auto, pending exclu des stats, missed requires reason, unicité user/habit/date), COHÉRENCE RELIGIEUSE RESPECTÉE (déterministe, aucun appel IA/cloud/pgvector/embedding, conforme docs 41/50). Pas de doublon (`path_items` vs habits = responsabilités distinctes). SEUL BÉMOL : dette legacy `imperium_path_items` déprécié mais encore branché (routes + lecteurs dashboard/weekly/daily_plans) — à débrancher, sans risque (pas un doublon dangereux). Schéma non documenté colonne/colonne. | écrire le schéma Path réel dans `05` ou doc dédié; débrancher `imperium_path_items` legacy après confirmation du canonique | audité |
| daily_plans | 0009 | (c) divergent — DEUX services à rôles DIFFÉRENTS, pas un doublon : `daily_plan.py` (singulier) = SNAPSHOT read-only, propre, sources canoniques, `GET /api/imperium/daily-plan` ; `daily_plans.py` (pluriel) = CRUD persistant, statuts `draft`→`active`→`completed`, lit encore le legacy `ImperiumPathItem`, `/api/imperium/day/plan...`. ÉCART MAJEUR : le daily plan "cerveau" du doc 52 §9 (génération intelligente : lit plan mensuel, score les missions, génère via modèle local) N'EST PAS CODÉ — seul l'échafaudage snapshot + CRUD existe. Normal : la génération intelligente attendait le GPU. Positifs : snapshot propre, garde-fou 1 mission active (409), priorités canoniques (`get_canonical_priority_order`, plus de `imperium_priority_rules`). Doc 28 ≠ doc 52 §12 sur les noms de colonnes. | trancher produit V1 : simple snapshot/CRUD foundation maintenant, ou vrai générateur intelligent doc 52 §9 à coder quand le GPU/local model est en place ; si le CRUD reste actif, rebrancher Path V1 habits/check-ins | audité |
| weekly_review | 0010,0013,0014,0015,0016 | (b) léger décalage — schéma WR globalement sain et conforme au doc 32 (sessions/messages/final_reports/decisions), mais propriétaire colonne-par-colonne absent dans doc 05; lien WR→mémoire cohérent avec le code actuel mais dépend de `ai_memories` déjà audité (c) divergent face aux docs 75/09. | ne pas toucher au schéma WR avant WR-b/WR-c; documenter le schéma WR dans 05 ou doc 32; réaligner `ai_memories` avant le commit mémoire WR | schéma audité (WR-a), reste logique |
| ai_tasks_results | 0012 | — | — | à auditer |
| decision_framework | 0019 | — | — | à auditer |
| pulse | 0028 | — | — | à auditer |
| events | 0011,0029,0030,0031 | — | — | à auditer |
| calendar | 0022 | — | — | à auditer |
| fondation (skeleton/security/guards) | 0001,0002,0003 | — | — | à auditer |

Verdicts : (a) conforme / (b) léger décalage / (c) divergent.

## Décisions transverses à trancher

Ces décisions se tranchent une fois le diagnostic complet, car plusieurs sont transverses (statuts, domaines, propriété de schéma) et valent mieux d'être réglées d'un coup que module par module.

### Vocabulaire des domaines

Code = `religious`/`business`/`finance`/`health` (anglais). Doc 52 §6 = `religieux`/`business`/`finances`/`santé` (français), mais Patch 17A = anglais.

→ Trancher UNE langue canonique pour les valeurs de domaine, partout.

### Liste canonique des statuts de mission

Code = `backlog`/`active`/`completed`/`failed`/`abandoned`/`cancelled` (anglais). Doc 43 §5 = `active`/`faite`/`ratée`/`annulée`/`expirée`/`stashed` (français, ancien). Doc 52 patch 17A = mentionne `backlog`, pas `abandoned`.

→ Établir UNE liste canonique de statuts, dans une langue, et aligner doc 43 + doc 52 + code dessus. Le code semble le plus à jour ; doc 43 est en dette.

### final_score vs weighted_score

Doc 52 §12 = `final_score`. Code = `weighted_score` (même concept).

→ Choisir un nom.

### Propriétaire du schéma missions

`05_DATABASE_SCHEMA.md` ne définit PAS réellement les tables missions. Doc 52 est de fait le propriétaire.

→ Acter officiellement que doc 52 possède le schéma missions/scoring, OU réécrire le 05. Question plus large : qui possède quoi entre 05 et les docs métier ?

### DÉCISION TRANSVERSE PRIORITAIRE — Doc 05 dictionnaire de schéma (CONFIRMÉ 3× : missions + vault + path)

`05_DATABASE_SCHEMA.md` devrait être LE dictionnaire de schéma, mais il contient des notes hétérogènes, pas les vraies tables. Du coup chaque module a son schéma dispersé dans des docs métier (52 pour missions, 04/27 pour vault), sans propriétaire clair.

→ Décision majeure et prioritaire : soit réécrire 05 comme vrai dictionnaire de schéma (toutes les tables, colonne par colonne), soit acter que chaque doc métier possède son schéma et que le 05 est déprécié. À trancher AVANT les corrections : cette décision conditionne toutes les corrections, car elle définit où vit la vérité du schéma. Les tables sans propriétaire documenté s'accumulent à chaque module.

### Ledgers Vault en double (lié au point ci-dessus)

Deux tables/routes/services pour la finance. Décision : `imperium_vault_transactions` (récent, moderne) = canonique probable ; `vault_transactions` (legacy) = à supprimer. Impact : migrer `weekly_report` + ancien dashboard, déprécier doc 27. Risque de chiffres incohérents tant que non résolu.

### DÉCISION PRODUIT — Qu'est-ce que le daily plan en V1 ?

Le doc 52 §9 décrit le daily plan comme un CERVEAU qui GÉNÈRE le plan du jour : il lit le plan mensuel, score les missions via doc 52, planifie horaires/trajets, et génère via le modèle local.

Le code actuel ne fait PAS ça : il a un snapshot read-only + un CRUD persistant, sans génération intelligente, sans scoring, sans modèle local, sans lecture du plan mensuel.

→ Trancher : daily plan V1 = simple snapshot/CRUD (ce qui est codé) OU vrai générateur intelligent (doc 52 §9, à coder une fois le GPU en place) ? C'est une décision de produit, pas seulement d'alignement.

Décision probable : foundation maintenant, cerveau quand le modèle local tourne.

### Dette legacy à débrancher (s'accumule)

Du code déprécié reste branché et lu : vault (`vault_transactions` + lecteurs), path (`imperium_path_items` + lecteurs dashboard/weekly/daily_plans). `daily_plans.py` (CRUD persistant) lit encore `ImperiumPathItem` → à rebrancher sur Path V1 habits/check-ins si ce service reste actif. Pattern : refonte faite, ancien jamais débranché.

→ Lister tout le legacy actif et le débrancher proprement (tables vides, donc sans risque) une fois les canoniques confirmés.

### Contradiction doc 28 vs doc 52 §12 (schéma imperium_daily_plans)

Noms de colonnes divergents : `local_date` (28/code) vs `date` (52), `plan_status` (28/code) vs `status` (52), `plan_blocks` (28/code) vs `plan_json` (52). Le code suit le doc 28.

→ Doc 52 §12 est soit futur, soit à corriger pour suivre le doc 28.

### Schéma imperium_mission_scores : compact (code) vs détaillé (doc §12)

Code = compact (`intrinsic_score` + `domain_coefficient` + `weighted_score` + `explanation` JSONB). Doc §12 = détaillé (`criterion_a`..`criterion_e` en colonnes dédiées, `computed_at`...).

→ Décision design : option A (aligner code sur doc, colonnes par critère) ou option B (garder le code compact V1 et documenter, si le JSONB `explanation` contient déjà le détail des critères). À vérifier : que contient `explanation` ?
