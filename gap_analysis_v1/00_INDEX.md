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

Note positive de campagne gap : la catégorie "sensible" est précieuse et bien gérée. Pulse côté médical et Path côté religieux ont un cadre de respect documenté de bout en bout, y compris sur les surfaces non codées. C'est rassurant pour la phase de codage future.

### ⚠️ Calculs religieux = déterministe mais EXACT (pas juste fonctionnel)

Certaines features Path V1 calculent du religieux : temps de prière (MAWAQIT + moteur fallback type Adhan), calendrier Hijri, direction Qibla, score Path pondéré.

Techniquement, ces features sont déterministes. Mais une erreur touche la pratique religieuse de l'utilisateur : prière à la mauvaise heure, Qibla fausse, date Hijri erronée.

Conclusion pour le codage futur : sources reconnues, méthodes de calcul validées, validation humaine recommandée. Catégorie à traiter comme "déterministe qui doit être EXACT", distincte du déterministe ordinaire.

### DÉCISION — Périmètre réel du "V1" (le label V1 de la doc ≠ premier livrable)

La doc 40 étiquette "V1" un module santé complet mélangeant déterministe, médical sensible et IA. Ce n'est pas un premier jet réaliste.

Décision à trancher : le V1 Pulse livrable = probablement le NOYAU DÉTERMINISTE (suivi alimentaire, hydratation, stock, workouts), tandis que le médical et l'IA deviennent des phases ultérieures.

Ce constat vaut désormais pour plusieurs domaines. Le label "V1" des docs désigne souvent la VISION cible, pas le premier livrable. Path le confirme : le "Path V1" documenté est un module religieux complet, alors que le codé actuel n'est que le squelette habits/check-ins. Idem Pulse. Imperium le confirme à son tour : le "V1" documenté mélange fondation déterministe, orchestration cross-module, IA de replanning et surfaces frontend futures.

Conclusion de campagne : une passe de REDÉFINITION V1/V2/V3 des docs devient de plus en plus clairement utile, à faire après la campagne gap. À garder en tête pour tous les domaines suivants : distinguer "V1 documenté" (vision) de "V1 livrable" (ce qu'on code en premier).

- Vector / VTC : SUSPENDU — gap classique écarté. Vector nécessite un chantier dédié : la matrice des variables métier (récurrence × impact), à faire en conversation neuve. Voir `gap_analysis_v1/DECISIONS_vector_discussion.md`. La doc 57 est mûre mais son classement V1/V2 des features est à refaire sur le bon critère.

## Tableau de bord

| Domaine | Features V1 reclamees | Codees | GAP V1 | Statut |
|---|---:|---:|---:|---|
| Vault / Finance | Audité. ✅ CODÉ V1 : ledger de base (transactions, reversals, summary). 🔲 GAP V1 : 8 features déterministes réclamées en V1 mais PAS codées — (1) deux livres business/perso, (2) wallet snapshots cash/bank/crypto manuels, (3) dépenses récurrentes/upcoming + alertes, (4) score de pression financière 0-100 (doc 11, formule déterministe), (5) objectifs journaliers min/comfortable/optimal, (6) corrections manuelles de pression, (7) base sadaqa = profit business réel, (8) consommation Imperium complète (pressure+alerts). TOUTES DÉTERMINISTES = codables sans GPU. 11 items "V1 ? à confirmer" (décisions de version pour le user). Conflits doc : pression 0-10 (doc 42) vs 0-100 (doc 11) ; n8n exclu (doc 27) vs décrit (doc 42). | Ledger de base code | 8 GAP V1 confirmés + 11 V1 ? à confirmer | Rapport créé: `GAP_vault.md` |
| Pulse / Santé | Audité. ✅ CODÉ : table minimale `imperium_pulse_entries` (6 champs métier). 🔲 GAP V1 ÉNORME : 13 gaps. Le "Pulse V1" de la doc 40 = un système santé COMPLET : repas+macros, hydratation, stock+péremption, workouts détaillés, pain logs, body snapshots, documents médicaux, règles médicales, recommandations IA. La triple catégorie révèle 3 niveaux de maturité : DÉTERMINISTE codable MAINTENANT (hydratation+jeûne, stock CRUD+péremption, repas confirmation manuelle+macros, décrément stock, workouts manuels détaillés) ; MÉDICAL SENSIBLE, avec cadre RGPD/consentement requis AVANT (body snapshots, pain logs, documents médicaux, règles médicales) ; IA/GPU, qui attend un modèle local/cloud approprié (estimation repas, recommandations, extraction médicale). F08 dossier médical = hors V1, sujet séparé du doc 34, à implémenter plus tard. | Table minimale codee | 13 GAP V1 + décision globale de périmètre | Rapport créé: `GAP_pulse.md` |
| Path / Religieux | Audité. ✅ CODÉ : habits/check-ins GÉNÉRIQUES (le squelette sain d'hier). 🔲 GAP V1 GROS (surprise) : tout le RELIGIEUX SPÉCIFIQUE V1 non codé — 12 gaps : (1) events/idempotency Path, (2) temps de prière MAWAQIT+cache+fallback calcul, (3) marquage 5 prières (`prayer_logs`), (4) jeûne (`fasting_logs`)+contrainte Pulse, (5) sadaqa hebdo+dons+report+handoff Vault, (6) ghusl+adresses, (7) adhkar compteurs, (8) invocations/rappels, (9) progression Coran, (10) score Path pondéré, (11) Hijri/Qibla foundation, (12) intégrations common memory. QUASI TOUT DÉTERMINISTE = codable sans GPU (8/12 priorisés codables tout de suite). ⏳ HORS V1 confirmé EN BLOC : Dars (doc 50, V3), YouTube (doc 49, V3), F04 défi (futur). Règle d'or Path RESPECTÉE dans toute la doc : pas de cloud religieux, pas de vectorisation corpus, arabe non interprété, wording non jugeant. | Habits/check-ins Path code | 12 familles GAP V1 + V1 ? à confirmer | Rapport créé: `GAP_path.md` |
| Imperium / Orchestrateur | Audité via base imposée. ✅ CODÉ V1 : decision framework déterministe mature (priorités, scoring A-E, bucket public, explication) + snapshot daily-plan read-only + plan persistant legacy actif. 🔲 GAP V1 STRUCTURANT : Imperium n'est pas encore le chef opérationnel documenté. Gaps majeurs : (1) contrat daily plan vivant à trancher, (2) hooks/replan_events/debounce/batching, (3) morning checkin/start-day, (4) mission lifecycle complet + one-active guard partout, (5) objectifs projet→objectif→mission, (6) discipline score, (7) Operations projets/routines, (8) history/decisions/events, (9) settings hors priorités, (10) observability IA, (11) event consumer cross-module, (12) arbitrage runtime Path/Vault/Pulse/Vector. Catégories : gros déterministe codable sans GPU, gros IA/n8n pour replanning/chatbot/advice, et surtout handoffs cross-module orphelins côté implémentation. | Decision framework + daily-plan foundations | 12 familles GAP V1 + 13 V1 ? à confirmer | Rapport créé: `GAP_imperium.md` |

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

### Path / Religieux

1. MAWAQIT fallback exact : architecture fallback après investigation de l'API MAWAQIT réelle + moteur type Adhan validé.
2. Missioning dynamique prières : prayer mission awareness zones dans le daily planning, V1 livrable ou phase IA/cross-module ultérieure ?
3. Sélection mosquée dynamique pendant VTC/day continuity : V1 livrable ou après fondation geo/planning ?
4. Replan ghusl IA : activer en V1 ou garder seulement le state/event déterministe d'abord ?
5. Feed IA / Nourrir l'IA pour invocations : V1 ou après validation du mécanisme doc 70 ?
6. AI task catalog Path minimal : WR contribution, routine adjustment, sadaqa strategy.
7. Sadaqa strategy advice : V1 ou phase conseil spirituel/financier ultérieure ?
8. Routine adjustment advice : V1 ou après usage réel des adhkar routines ?
9. WR contribution from Path : traité dans Path V1 ou dans le domaine Weekly Review ?
10. Split backend vs Android pour PAT-01..PAT-12 : quels contrats backend exacts doivent être livrés avant UI ?

### Imperium / Orchestrateur

1. Objectifs : V1 livrable avec table/CRUD objectifs, ou phase après projets + missions ?
2. Mission attributes complets : source/source_ref/replan_version à auditer/coder dans le contrat mission officiel.
3. Operations data model exact : tables projets/routines à réconcilier avec doc 05.
4. Activation manuelle d'un 3e projet quand 2 slots actifs sont pleins.
5. Nom final de l'onglet Operations + route ID/path définitifs.
6. Chatbot actionnable : V1 livrable ou après fondation déterministe projets/routines ?
7. Daily AI Advice : V1 avec WR vectorisé, ou après pipeline memory/WR validé ?
8. Mission recommendation mid-day : V1 ou phase IA ultérieure ?
9. Rolling replan multi-week : V1 ou après daily replan ?
10. Monthly rolling plan : doc 43 le marque V2, mais c'est la seule décision vraiment autonome rappelée par le user.
11. AI observability complète : V1 avant usage réel, mais à normaliser avec la bibliothèque modèles.
12. Endpoints futurs doc 65 : lesquels deviennent API backend V1 contractuels ?
13. Doc 19 deployment : garder comme infra V1 séparée ou lier au catalogue Imperium ?

## Enrichissement catalogue

En attente. Ne pas encore appliquer l'enrichissement catalogue des docs 27/42/11, 40/34/F08, 41/50/49/F04, ni 43/71/19/65/66 ; tous les enrichissements catalogue seront appliqués en une passe à la fin de la campagne gap.
