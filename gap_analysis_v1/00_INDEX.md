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

## Enrichissement catalogue

En attente. Ne pas encore appliquer l'enrichissement catalogue des docs 27/42/11 ; tous les enrichissements catalogue seront appliqués en une passe à la fin de la campagne gap.
