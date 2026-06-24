# Campagne d'audit RESYNC — code backend ↔ doc (juin 2026)
> Resynchronisation ponctuelle du code backend avec la doc consolidée (post-stabilisation
> + grande passe nomenclature). Le code a été écrit en mai selon une pensée antérieure ;
> cette campagne mesure et planifie le réalignement, module par module.
> Système NON en production, tables VIDES → aligner ne casse aucune donnée.

## Tableau de bord

| Module | Migration(s) | Verdict | Action | Statut |
|---|---|---|---|---|
| ai_memories | 0017 | (c) divergent | réaligner sur doc 75 (table vide, schéma vectoriel manquant) | audité, à corriger |
| missions | 0005,0006,0020,0021 | — | — | à auditer |
| vault | 0007,0024,0025 | — | — | à auditer |
| path | 0008,0027 | — | — | à auditer |
| daily_plans | 0009 | — | — | à auditer |
| weekly_review | 0010,0013,0014,0015,0016 | — | — | à auditer |
| ai_tasks_results | 0012 | — | — | à auditer |
| decision_framework | 0019 | — | — | à auditer |
| pulse | 0028 | — | — | à auditer |
| events | 0011,0029,0030,0031 | — | — | à auditer |
| calendar | 0022 | — | — | à auditer |
| fondation (skeleton/security/guards) | 0001,0002,0003 | — | — | à auditer |

Verdicts : (a) conforme / (b) léger décalage / (c) divergent.
