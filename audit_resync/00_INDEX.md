# Campagne d'audit RESYNC — code backend ↔ doc (juin 2026)
> Resynchronisation ponctuelle du code backend avec la doc consolidée (post-stabilisation
> + grande passe nomenclature). Le code a été écrit en mai selon une pensée antérieure ;
> cette campagne mesure et planifie le réalignement, module par module.
> Système NON en production, tables VIDES → aligner ne casse aucune donnée.

## Tableau de bord

| Module | Migration(s) | Verdict | Action | Statut |
|---|---|---|---|---|
| ai_memories | 0017 | (c) divergent | réaligner sur doc 75 (table vide, schéma vectoriel manquant) | audité, à corriger |
| missions | 0005,0019,0020,0021,0023 | (c) divergent — MAIS module SAIN : cœur du scoring codé (`intrinsic_score`, `domain_coefficient` ×10/8/5/4, `mission_type_category` cat_a-i, index "1 seule active/user" conforme). Écarts = renommages + couches futures non codées + 1 choix design. | réconcilier docs 52/43 et schéma missions/scores; créer ou déclasser outcomes/durations | schéma audité (partie 2a). Reste : logique service `missions.py` (partie 2b) |
| vault | 0007,0024,0025,0026 | (c) divergent — DEUX LEDGERS coexistent et sont TOUS DEUX actifs : `vault_transactions` (legacy, `/api/vault`, decimal, doc 27) ET `imperium_vault_transactions` (récent, `/api/imperium/vault`, cents, reversals, doc 04). ⚠️ RISQUE : `dashboard.py` et `weekly_report.py` lisent encore l'ANCIEN ledger → chiffres financiers potentiellement incohérents selon l'écran. Le ledger récent est bien fait (reversals, append-only API, 1 reversal/original garanti). | choisir `imperium_vault_transactions` comme canonique, migrer les lecteurs restants, supprimer le legacy (tables vides) | audité, à corriger (décision ledger requise) |
| path | 0008,0027 | (b) léger décalage — surface V1 habits/check-ins cohérente et religieusement conforme, mais aucun doc ne possède le schéma colonne par colonne. `imperium_path_items` est bien legacy/déprécié dans la doc, mais reste branché via routes/lecteurs historiques. | écrire le schéma Path réel dans `05` ou doc dédié; décider du sort de `imperium_path_items`; éventuellement durcir DB `missed requires reason` et enum `domain` | audité, à clarifier |
| daily_plans | 0009 | — | — | à auditer |
| weekly_review | 0010,0013,0014,0015,0016 | — | — | à auditer |
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

### Doc 05 ne joue pas son rôle de dictionnaire de schéma (CONFIRMÉ 2× : missions + vault)

`05_DATABASE_SCHEMA.md` devrait être LE dictionnaire de schéma, mais il contient des notes hétérogènes, pas les vraies tables. Du coup chaque module a son schéma dispersé dans des docs métier (52 pour missions, 04/27 pour vault), sans propriétaire clair.

→ Décision majeure : soit réécrire 05 comme vrai dictionnaire de schéma (toutes les tables, colonne par colonne), soit acter que chaque doc métier possède son schéma et que le 05 est déprécié. À trancher AVANT les corrections (ça définit où vit la vérité).

### Ledgers Vault en double (lié au point ci-dessus)

Deux tables/routes/services pour la finance. Décision : `imperium_vault_transactions` (récent, moderne) = canonique probable ; `vault_transactions` (legacy) = à supprimer. Impact : migrer `weekly_report` + ancien dashboard, déprécier doc 27. Risque de chiffres incohérents tant que non résolu.

### Schéma imperium_mission_scores : compact (code) vs détaillé (doc §12)

Code = compact (`intrinsic_score` + `domain_coefficient` + `weighted_score` + `explanation` JSONB). Doc §12 = détaillé (`criterion_a`..`criterion_e` en colonnes dédiées, `computed_at`...).

→ Décision design : option A (aligner code sur doc, colonnes par critère) ou option B (garder le code compact V1 et documenter, si le JSONB `explanation` contient déjà le détail des critères). À vérifier : que contient `explanation` ?
