# Audit RESYNC — Missions schema

Date: 2026-06-27

Scope: audit lecture seule du schema missions code vs documentation.

Fichiers code lus:
- `backend/alembic/versions/20260426_0005_imperium_missions.py`
- `backend/alembic/versions/20260504_0019_decision_framework_foundation.py` (necessaire: creation de `imperium_mission_scores`)
- `backend/alembic/versions/20260511_0020_imperium_missions_decision_fields.py`
- `backend/alembic/versions/20260511_0021_imperium_mission_scores_unique_source.py`
- `backend/alembic/versions/20260525_0023_imperium_mission_abandoned_status.py`
- `backend/app/models/imperium.py`

Documentation lue:
- `docs_master/52_AI_DECISION_FRAMEWORK.md` sections 4, 5.3, 6, 12, 17A
- `docs_master/05_DATABASE_SCHEMA.md`
- `docs_master/43_IMPERIUM_LOGIC_DETAIL.md` section 5, car le doc 52 renvoie les statuts mission vers doc 43

## Reference documentaire

`docs_master/05_DATABASE_SCHEMA.md` ne definit pas exploitablement `imperium_missions`, `imperium_mission_scores`, `mission_outcomes` ou `mission_type_learned_durations`. Il ne contient que des notes heterogenes de contrats/front/pulse/path/vault.

Conclusion: pour cet audit schema missions, `docs_master/52_AI_DECISION_FRAMEWORK.md` est le seul proprietaire clair du schema Decision Framework. Le doc 43 reste une reference secondaire pour les statuts, mais il est lui-meme en decalage avec le code et avec les patch notes du doc 52.

## Table `imperium_missions`

### Colonnes code

Schema code consolide par migrations + ORM:

| Colonne code | Type code | Contraintes code | Source code | Statut vs doc 52 |
|---|---|---|---|---|
| `id` | UUID | PK | 0005, ORM | Conforme partiel: doc 52 attend `id`. |
| `user_id` | UUID | NOT NULL, FK `users.id` | 0005, ORM | Present code, non liste dans doc 52 §6 backlog, mais logique utilisateur. |
| `title` | TEXT | NOT NULL | 0005, ORM | Conforme. |
| `category` | TEXT | NULL | 0005, ORM | Code seulement. A rapprocher de `mission_type_category` ou a documenter. |
| `domain` | TEXT | NULL, check `religious/business/finance/health` | 0020, ORM | Present dans doc, mais vocabulaire different: doc §6 dit `religieux/business/finances/santé`; patch 17A dit `religious/business/finance/health`. |
| `priority_level` | INTEGER | NULL, 1..10 | 0005 + 0020, ORM | Conforme au concept 10 niveaux. |
| `mission_type_category` | TEXT | NULL, check `cat_a`..`cat_i` | 0020, ORM | Present code. Doc §4/§12 attend `criterion_c_category` `A`..`I` dans scores, pas cette colonne mission; patch 17A documente `mission_type_category`. |
| `status` | TEXT | NOT NULL, check `backlog/active/completed/failed/abandoned/cancelled` | 0005 + 0020 + 0023, ORM | Divergence avec doc 43 et partielle avec doc 52; details plus bas. |
| `planned_start_at` | TIMESTAMPTZ | NULL | 0005, ORM | Code seulement; doc 43 ancien parle `planned_for_at`. |
| `planned_end_at` | TIMESTAMPTZ | NULL | 0005, ORM | Code seulement; peut servir de deadline implicite mais doc §6 attend `deadline_at`. |
| `started_at` | TIMESTAMPTZ | NOT NULL | 0005, ORM | Code seulement; contrainte forte peu compatible avec backlog conceptuel si une mission backlog n'a pas encore commence. |
| `ended_at` | TIMESTAMPTZ | NULL | 0005, ORM | Code seulement; doc 43 ancien attend champs separes `completed_at/failed_at/cancelled_at/...`. |
| `completion_note` | TEXT | NULL | 0005, ORM | Code seulement; proche de `notes`. |
| `failure_reason` | TEXT | NULL | 0005, ORM | Code seulement; proche des outcomes documentes. |
| `user_reported_signals` | JSONB | NULL | 0005, ORM | Code seulement. |
| `ai_usable_reason` | BOOLEAN | NULL | 0005, ORM | Code seulement. |
| `created_by_event_id` | UUID | NULL, FK `events.id` | 0005, ORM | Code seulement. |
| `ended_by_event_id` | UUID | NULL, FK `events.id` | 0005, ORM | Code seulement. |
| `created_at` | TIMESTAMPTZ | NOT NULL, default `now()` | 0005, ORM | Code seulement mais standard. |
| `updated_at` | TIMESTAMPTZ | NOT NULL, default/onupdate `now()` | 0005, ORM | Code seulement mais standard. |

### Colonnes documentees mais absentes du code

Doc 52 §6 "Mission Backlog" attend sur chaque mission:

| Colonne doc | Type/semantique doc | Statut code | Ecart |
|---|---|---|---|
| `estimated_duration_minutes` | duree estimee | Absent | Manquant. |
| `required_location` | texte ou coordonnees | Absent | Manquant. |
| `required_skills` | competences/ressources rares | Absent | Manquant. |
| `financial_impact` | cout ou revenu estime | Absent | Manquant. |
| `prerequisite_mission_ids` | dependances | Absent | Manquant. |
| `source` | `ai_planner/path/vector/manual/calendar` | Absent | Manquant; code a seulement `created_by_event_id`. |
| `deadline_at` | deadline mission | Absent | Manquant; code a `planned_end_at`, mais ce n'est pas equivalent contractuellement. |
| `is_recurrent` | recurrence oui/non | Absent | Manquant. |
| `recurrence_rrule` | regle recurrence | Absent | Manquant. |
| `intrinsic_criteria_a`..`intrinsic_criteria_e` | criteres A-E | Absent de `imperium_missions` | Dans le code, pas non plus en colonnes dediees de `imperium_mission_scores`. |
| `intrinsic_score` | score 0..100 | Absent de `imperium_missions` | Stocke dans `imperium_mission_scores`, ce qui correspond au §4.6. |
| `domain_coefficient` | coefficient domaine | Absent de `imperium_missions` | Stocke dans `imperium_mission_scores`, cohérent avec stockage scoring separe. |
| `final_score` | score final | Absent | Le code stocke `weighted_score` dans `imperium_mission_scores`. |

Doc 43 §5.2 ancien attend aussi `description`, `mission_type`, `source_ref`, `completed_at`, `failed_at`, `cancelled_at`, `expired_at`, `stashed_at`, `notes`, `replan_version`, `stash_reason`, `is_carrier_mission`, `is_overlay_eligible`, `overlay_category`: aucun de ces champs n'existe dans `imperium_missions`. Comme le doc 52 est plus recent et porte le Decision Framework, ces ecarts doivent surtout etre traites comme dette documentaire doc 43, sauf si ces champs sont encore voulus.

### Index et contraintes code

| Element code | Statut vs doc | Commentaire |
|---|---|---|
| Unique index `imperium_missions_one_active_per_user_idx` WHERE `status = 'active'` | Conforme a la regle non-negociable | Garantit une seule mission active par utilisateur. |
| Index backlog `(user_id, priority_level, created_at)` WHERE `status = 'backlog'` | Conforme intention backlog | Le doc 52 demande une table unique et 10 niveaux; cet index supporte le tri. |
| Check `priority_level` 1..10 | Conforme | Aligne §6. |
| Check `mission_type_category` `cat_a`..`cat_i` | Partiel | Aligne patch 17A, pas le CREATE TABLE §12 qui attend `criterion_c_category` `A`..`I` dans scores. |

## Table `imperium_mission_scores`

### Colonnes code vs CREATE TABLE doc 52 §12

| Colonne | Code | Doc 52 §12 | Verdict |
|---|---|---|---|
| `id` | UUID PK, default DB `gen_random_uuid()` en migration, default Python ORM `uuid4` | UUID PK | Conforme. |
| `user_id` | UUID NOT NULL FK `users.id` | Non documente | Code seulement; utile pour scoping et index, a documenter si conserve. |
| `mission_id` | UUID NOT NULL FK `imperium_missions.id` ON DELETE CASCADE | UUID FK | Conforme + contrainte plus precise. |
| `criterion_a` | Absent | INTEGER 0-30 | Manquant. |
| `criterion_b` | Absent | INTEGER 0-30 | Manquant. |
| `criterion_c_category` | Absent | VARCHAR(2), `A` to `I` | Manquant. Le code met `mission_type_category` sur `imperium_missions` avec valeurs `cat_a`..`cat_i`. |
| `criterion_c` | Absent | INTEGER 0-20 | Manquant. |
| `criterion_d` | Absent | INTEGER 0-10 | Manquant. |
| `criterion_e` | Absent | INTEGER 0-10 | Manquant. |
| `intrinsic_score` | NUMERIC(5,2) NOT NULL, check 0..100 | INTEGER 0..100 | Difference type et nullability. Code accepte decimals, doc attend entier. |
| `domain` | TEXT NOT NULL, check `religious/business/finance/health` | VARCHAR(32) | Type different mais equivalent PostgreSQL pratique; vocabulaire anglais conforme patch 17A, pas le texte §6 français. |
| `domain_coefficient` | INTEGER NOT NULL, check 10/8/5/4 | INTEGER | Conforme + contrainte plus precise. |
| `final_score` | Absent | INTEGER | Manquant sous ce nom. Code stocke `weighted_score`. |
| `weighted_score` | NUMERIC(7,2) NOT NULL, check >=0 | Non dans CREATE TABLE §12; mentionne comme champ non expose en §5.3/17A | Nom divergent: probablement meme concept que `final_score`, mais contrat documentaire principal dit `final_score`. |
| `priority_level` | Absent | INTEGER 1-10 | Manquant dans score row. Le code garde `priority_level` sur `imperium_missions`; le score expose un bucket via `explanation`. |
| `computed_at` | Absent | TIMESTAMPTZ | Manquant. Code a `created_at`/`updated_at`. |
| `explanation` | JSONB NOT NULL default `{}` | Non dans CREATE TABLE §12 | Code seulement; compense partiellement les criteres absents, mais moins interrogeable/contraint. |
| `source` | TEXT NOT NULL default `decision_framework_v1`, check valeur unique | Non dans CREATE TABLE §12; documente par patch 17A | Conforme au patch 7F-2, absent du CREATE TABLE. |
| `created_at` | TIMESTAMPTZ NOT NULL default `now()` | Non documente | Code seulement; proche de `computed_at` mais pas equivalent nom/semantique. |
| `updated_at` | TIMESTAMPTZ NOT NULL default/onupdate `now()` | Non documente | Code seulement. |

### Contraintes et index

| Element code | Doc | Verdict |
|---|---|---|
| Unique index `(user_id, mission_id, source)` | Patch 17A dit que ce triplet est unique | Conforme au patch, absent du CREATE TABLE §12. |
| Index `(user_id, weighted_score)` | Non documente | Code seulement. |
| Index `(user_id, domain)` | Non documente | Code seulement. |
| Index `(mission_id)` | Non documente | Code seulement mais logique. |
| Check `source IN ('decision_framework_v1')` | Patch 17A source `decision_framework_v1` | Conforme V1, mais extension future limitee. |

### Scoring: §4/§5 vs code

| Point demande | Observation |
|---|---|
| Criteres A-E stockes individuellement | Non. Ils ne sont pas en colonnes. Ils peuvent etre enfouis dans `explanation` JSONB selon le service, mais le schema ne les impose pas. |
| Score intrinseque stocke | Oui, `intrinsic_score`, mais en `NUMERIC(5,2)` au lieu de `INTEGER`. |
| Coefficient domaine stocke | Oui, `domain_coefficient`, avec check 10/8/5/4. |
| Score final stocke | Oui conceptuellement via `weighted_score`, mais le nom documente est `final_score`. |
| Priority bucket/niveau stocke avec score | Non dans `imperium_mission_scores`. `priority_level` existe sur mission; le bucket public est derive. |
| Champs internes exposes au public | Le schema DB stocke `weighted_score` et `domain_coefficient`, mais les docs §5.3/17A interdisent seulement l'exposition publique. Rien dans les fichiers audites contredit cela. |

Verdict: `imperium_mission_scores` code correspond a une implementation V1 compacte de la decision framework, mais ne correspond pas au CREATE TABLE normatif du §12.

## Tables documentees mais absentes

| Table doc 52 §12 | Statut code | Ecart |
|---|---|---|
| `mission_outcomes` | Absente des migrations et de l'ORM `imperium.py` | Manquante si §12 est MVP/canonique. Le code stocke les resultats directement sur `imperium_missions` (`status`, `ended_at`, `completion_note`, `failure_reason`). |
| `mission_type_learned_durations` | Absente des migrations et de l'ORM `imperium.py` | Manquante. Aucun stockage de durees medianes apprises par signature de type mission. |

Le §12 utilise les noms sans prefixe `mission_outcomes` et `mission_type_learned_durations`, contrairement a beaucoup de tables codees prefixees `imperium_`. Il faut decider si ces tables doivent rester non prefixees ou etre renommees avant implementation.

## Statut `abandoned`

Code:
- migration 0023 ajoute `abandoned`;
- ORM `ImperiumMission` autorise `backlog/active/completed/failed/abandoned/cancelled`;
- schemas/services missions utilisent aussi `abandoned` comme outcome historique.

Documentation:
- doc 52 patch 17A mentionne `status now also allows backlog`, mais ne mentionne pas explicitement `abandoned`.
- doc 52 §6 dit `status (per doc 43 §5)`.
- doc 43 §5 liste des statuts francises/anciens: `active`, `faite`, `ratée`, `annulée`, `expirée`, `stashed`.
- doc 43 §5-bis dit que l'abandon vit au niveau mission via `annulée`, mais ne documente pas un statut code `abandoned`.

Verdict statut: `abandoned` est coherent avec l'intention produit "abandon au niveau mission" et avec le code applicatif actuel, mais il n'est pas correctement documente dans le schema canonique. La documentation statuts est divergente: anglais code vs francais doc 43, `backlog` present code/doc52 patch mais absent doc43, `expired/stashed` documentes doc43 mais absents code, `abandoned` present code mais non canonise doc52/doc43.

## Restes perimes / incoherences de nommage

| Recherche | Resultat |
|---|---|
| Ancien nom `pgvector_memory` | Non trouve dans `backend/app`, `backend/alembic/versions`, ni doc 52. |
| Tables mission outcomes/durations | Non trouvees dans code. |
| `weighted_score` | Present partout dans code/tests/services; doc §5.3/17A dit surtout "ne pas exposer". Mais §12 attend `final_score`. Nommage a trancher. |
| `ImperiumPriorityRule` | Toujours present comme legacy/compatibilite. Doc 52 Patch 7G confirme qu'il doit rester compatibility-only, donc pas un reste perime a supprimer dans ce module. |
| Domaines | Code utilise `religious/business/finance/health`; doc §6 utilise `religieux/business/finances/santé`; patch 17A utilise l'anglais code. La doc principale contient donc deux vocabulaires. |

## Conclusion

Verdict: **(c) divergent**.

Le module missions respecte quelques garde-fous essentiels:
- une seule mission active par utilisateur est garantie par index unique partiel;
- le backlog en table unique et `priority_level` 1..10 existent;
- `domain`, `mission_type_category`, `intrinsic_score`, `domain_coefficient`, score pondere interne et source unique V1 existent;
- les coefficients internes ne sont pas incompatibles avec la regle de non-exposition publique.

Mais le schema code diverge fortement du schema documente:
- `imperium_mission_scores` ne correspond pas au CREATE TABLE §12: criteres A-E absents, `final_score` absent, `priority_level` absent, `computed_at` absent, types differents;
- `imperium_missions` ne porte pas de nombreux champs backlog documentes (`deadline_at`, `source`, duree, dependances, recurrence, impact financier);
- `mission_outcomes` et `mission_type_learned_durations` sont entierement absentes;
- les statuts sont incoherents entre code, doc 52 et doc 43;
- `05_DATABASE_SCHEMA.md` ne joue pas son role de reference pour la table de base.

## Actions precises recommandees

1. Declarer explicitement le proprietaire schema missions:
   - soit `52_AI_DECISION_FRAMEWORK.md` devient canonique pour missions/scoring;
   - soit `05_DATABASE_SCHEMA.md` doit etre reecrit avec `imperium_missions`, `imperium_mission_scores`, `mission_outcomes`, `mission_type_learned_durations`.

2. Trancher le modele `imperium_mission_scores`:
   - option A: aligner le code sur §12 en ajoutant colonnes `criterion_a`..`criterion_e`, `criterion_c_category`, `final_score`, `priority_level`, `computed_at`;
   - option B: mettre a jour §12 pour documenter le schema V1 code (`weighted_score`, `explanation` JSONB, `source`, timestamps, unique `(user_id, mission_id, source)`).

3. Trancher `weighted_score` vs `final_score`:
   - garder `weighted_score` si le vocabulaire code V1 est choisi;
   - sinon migrer/aliaser vers `final_score` pour suivre le doc §5.

4. Reconciler les statuts dans une seule liste canonique:
   - code actuel: `backlog`, `active`, `completed`, `failed`, `abandoned`, `cancelled`;
   - supprimer/archiver ou traduire clairement les anciens statuts doc 43 (`faite`, `ratée`, `annulée`, `expirée`, `stashed`).

5. Decider si `mission_outcomes` et `mission_type_learned_durations` sont MVP:
   - si oui, creer migrations + ORM + tests;
   - si non, marquer explicitement ces tables comme futures/non implementees dans doc 52.

6. Reconciler `imperium_missions` backlog:
   - soit ajouter les champs documentes (`deadline_at`, `source`, `estimated_duration_minutes`, dependances, recurrence, etc.);
   - soit documenter que V1 stocke seulement les champs minimaux et que les signaux scoring ne sont pas tous persistants.

7. Apres choix d'alignement, ajouter/mettre a jour les tests pytest de schema et de contrats avant tout changement code, conformement a la regle CI du projet.
