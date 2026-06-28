# GAP Analysis V1 - Index

### Deux backlogs distincts révélés

La gap analysis distingue ce que l'audit de conformité ne voyait pas :

- BACKLOG IA (routage, génération, mémoire vectorielle) -> attend le GPU/V100.
- BACKLOG DÉTERMINISTE (formules, tables, CRUD comme la pression financière) -> codable MAINTENANT, sans GPU. Le Vault montre que ce backlog est gros et immédiatement actionnable.

Pour chaque gap, l'auditeur précise déterministe vs IA -> permet de coder le déterministe pendant que la V100 n'est pas prête.

### Note transverse - triple catégorie de maturité

L'audit Pulse révèle une catégorie plus fine que le simple couple déterministe / IA :

- DÉTERMINISTE codable MAINTENANT : règles, CRUD, agrégations, validations, idempotency, alertes simples.
- SENSIBLE : données ou décisions nécessitant cadre explicite, consentement, sécurité, réversibilité et validation utilisateur avant activation.
- IA/GPU : estimation, extraction, recommandation, adaptation ou raisonnement non déterministe qui attend un modèle local/cloud approprié.

Cette triple catégorie est à généraliser. Pour les domaines à données sensibles, par exemple Path religieux ou santé Pulse, garder une catégorie "sensible" distincte du simple déterministe.

### DÉCISION — Périmètre réel du "V1" (le label V1 de la doc ≠ premier livrable)

La doc 40 étiquette "V1" un module santé complet mélangeant déterministe, médical sensible et IA. Ce n'est pas un premier jet réaliste.

Décision à trancher : le V1 Pulse livrable = probablement le NOYAU DÉTERMINISTE (suivi alimentaire, hydratation, stock, workouts), tandis que le médical et l'IA deviennent des phases ultérieures.

Ce constat vaut probablement pour d'autres domaines : le label "V1" des docs désigne souvent la VISION cible, pas le MVP. À garder en tête pour tous les domaines suivants : distinguer "V1 documenté" (vision) de "V1 livrable" (ce qu'on code en premier).

## Tableau de bord

| Domaine | Features V1 reclamees | Codees | GAP V1 | Statut |
|---|---:|---:|---:|---|
| Vault / Finance | Audité. ✅ CODÉ V1 : ledger de base (transactions, reversals, summary). 🔲 GAP V1 : 8 features déterministes réclamées en V1 mais PAS codées — (1) deux livres business/perso, (2) wallet snapshots cash/bank/crypto manuels, (3) dépenses récurrentes/upcoming + alertes, (4) score de pression financière 0-100 (doc 11, formule déterministe), (5) objectifs journaliers min/comfortable/optimal, (6) corrections manuelles de pression, (7) base sadaqa = profit business réel, (8) consommation Imperium complète (pressure+alerts). TOUTES DÉTERMINISTES = codables sans GPU. 11 items "V1 ? à confirmer" (décisions de version pour le user). Conflits doc : pression 0-10 (doc 42) vs 0-100 (doc 11) ; n8n exclu (doc 27) vs décrit (doc 42). | Ledger de base code | 8 GAP V1 confirmés + 11 V1 ? à confirmer | Rapport créé: `GAP_vault.md` |
| Pulse / Santé | Audité. ✅ CODÉ : table minimale `imperium_pulse_entries` (6 champs métier). 🔲 GAP V1 ÉNORME : 13 gaps. Le "Pulse V1" de la doc 40 = un système santé COMPLET : repas+macros, hydratation, stock+péremption, workouts détaillés, pain logs, body snapshots, documents médicaux, règles médicales, recommandations IA. La triple catégorie révèle 3 niveaux de maturité : DÉTERMINISTE codable MAINTENANT (hydratation+jeûne, stock CRUD+péremption, repas confirmation manuelle+macros, décrément stock, workouts manuels détaillés) ; MÉDICAL SENSIBLE, avec cadre RGPD/consentement requis AVANT (body snapshots, pain logs, documents médicaux, règles médicales) ; IA/GPU, qui attend un modèle local/cloud approprié (estimation repas, recommandations, extraction médicale). F08 dossier médical = hors V1, sujet séparé du doc 34, à implémenter plus tard. | Table minimale codee | 13 GAP V1 + décision globale de périmètre | Rapport créé: `GAP_pulse.md` |

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

Pour Pulse, la vraie question n'est pas item par item mais globale : où coupe-t-on le V1 livrable par rapport au "V1 documenté" de la doc 40 ?

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
13. Medical document flow timing : en V1 livrable ou phase ultérieure après cadre RGPD/consentement/sécurité ?
14. Relation F08 vs doc 40: doc 40 renvoie à doc 34; F08 semble future/hors V1.

## Enrichissement catalogue

En attente. Ne pas encore appliquer l'enrichissement catalogue des docs 27/42/11 ni 40/34/F08 ; tous les enrichissements catalogue seront appliqués en une passe à la fin de la campagne gap.
