# GAP Analysis V1 - Index

### Deux backlogs distincts révélés

La gap analysis distingue ce que l'audit de conformité ne voyait pas :

- BACKLOG IA (routage, génération, mémoire vectorielle) -> attend le GPU/V100.
- BACKLOG DÉTERMINISTE (formules, tables, CRUD comme la pression financière) -> codable MAINTENANT, sans GPU. Le Vault montre que ce backlog est gros et immédiatement actionnable.

Pour chaque gap, l'auditeur précise déterministe vs IA -> permet de coder le déterministe pendant que la V100 n'est pas prête.

## Tableau de bord

| Domaine | Features V1 reclamees | Codees | GAP V1 | Statut |
|---|---:|---:|---:|---|
| Vault / Finance | Audité. ✅ CODÉ V1 : ledger de base (transactions, reversals, summary). 🔲 GAP V1 : 8 features déterministes réclamées en V1 mais PAS codées — (1) deux livres business/perso, (2) wallet snapshots cash/bank/crypto manuels, (3) dépenses récurrentes/upcoming + alertes, (4) score de pression financière 0-100 (doc 11, formule déterministe), (5) objectifs journaliers min/comfortable/optimal, (6) corrections manuelles de pression, (7) base sadaqa = profit business réel, (8) consommation Imperium complète (pressure+alerts). TOUTES DÉTERMINISTES = codables sans GPU. 11 items "V1 ? à confirmer" (décisions de version pour le user). Conflits doc : pression 0-10 (doc 42) vs 0-100 (doc 11) ; n8n exclu (doc 27) vs décrit (doc 42). | Ledger de base code | 8 GAP V1 confirmés + 11 V1 ? à confirmer | Rapport créé: `GAP_vault.md` |
| Pulse / Santé | Audité. ✅ CODÉ V1 : entrée quotidienne minimale (`imperium_pulse_entries`: sommeil, énergie, fatigue, poids, workout flag/type, notes) + privacy sécurisée par absence (aucun cloud/upload/document médical). 🔲 GAP V1 : la doc 40/34 réclame une V1 beaucoup plus large. 13 blocs GAP détaillés : dashboard Pulse, events/idempotency/offline, meals, food stock, stock decrement, hydration, workouts, body snapshots, pain logs, documents médicaux, feed médical IA, règles médicales actives, recommandations. Distinction cruciale : déterministe pur codable maintenant (hydration, stock, meal confirmation, workouts manuels) vs médical sensible (body/pain/medical docs/rules) vs IA/GPU (estimation repas, OCR, recommandations, adaptation, health specialist). | Fondation minimale codee | 13 blocs GAP V1 + 14 V1 ? à confirmer | Rapport créé: `GAP_pulse.md` |

## Décisions de version à trancher (V1 ?)

Pile à croiser avec le travail au crayon du user.

### Vault / Finance

1. Predicted wallet + prompt écart > 5%.
2. Stockage pressure snapshots / weekly financial snapshot.
3. Weekly profit computation n8n lundi 00:30 + event.
4. Classification required/deferrable des dépenses hors liste.
5. Categorization suggestion + `user_category_memory`.
6. Receipt scan OCR + draft transactions.
7. Receipt food items -> Pulse stock.
8. Path donation -> Vault expense `Sadaqa`.
9. Vector fuel history + session income write.
10. Level 2 "Voir pourquoi" advice.
11. Vault AI task catalog/routing.

### Pulse / Santé

1. Recipe catalogue via chatbot/web/OCR/Nourrir l'IA.
2. Weekly diet programming par health specialist.
3. Shopping list générée depuis diet program.
4. Batch cooking mission + smart storage.
5. Personalized hydration target.
6. Workout program creation Mode 1 par health specialist.
7. Recovery personalized forecast frame.
8. Monthly workout revision / phase transition.
9. Owned equipment settings.
10. Park equipment and day-continuity routing.
11. Common memory reads/writes exact contracts.
12. Health score formula/model ownership.
13. Medical document flow en V1 malgré RGPD/IA specialist.
14. Relation F08 vs doc 40: doc 40 renvoie à doc 34; F08 semble future/hors V1.

## Enrichissement catalogue

En attente. Ne pas encore appliquer l'enrichissement catalogue des docs 27/42/11 ni 40/34/F08 ; tous les enrichissements catalogue seront appliqués en une passe à la fin de la campagne gap.
