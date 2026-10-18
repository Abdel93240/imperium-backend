# 77 - Catalogue des Events

Statut : catalogue central des `event_type` cibles, base de normalisation du
journal `events`.

Ce document est le pendant du doc 05 pour les events. Le doc 05 reste la source
pour la table PostgreSQL `events` elle-même : colonnes, types, contraintes,
index et état réel du schéma. Le présent document ne redéfinit pas la table ; il
décrit le vocabulaire métier autorisé et la logique d'usage des `event_type`.

Rappels structurants :

- D2 : le journal canonique est `events`. `imperium_events` est déprécié.
- D3 : le format cible des `event_type` est dotted,
  `domaine.sujet.action`.
- Le premier segment est un domaine générique, jamais un nom d'application :
  `finance`, `planning`, `health`, `decision`, `calendar`, `rides`,
  `vehicle` — **et `path` (DV-11, gravée 2026-07-15) : exception assumée,
  voir section WORSHIP.**
- **PATCH 2026-07-15 (passe 0) — renommages APPLIQUÉS côté code** avec compat
  en lecture 30 jours (jusqu'au 2026-08-14, module
  `app/services/events/nomenclature.py`). Table de correspondance :

| ancien (historique) | nouveau (canonique, émis) |
|---|---|
| `vault.transaction.created` | `finance.transaction.created` |
| `mission.backlog.created` | `planning.mission.created` |
| `mission.started` | `planning.mission.started` |
| `mission.completed` | `planning.mission.completed` |
| `mission.failed`, `mission.abandoned` (E1) | `planning.mission.aborted` (+ `reason`) |
| `day.plan.created` | `planning.daily_plan.generated` |
| `day.plan.activated/completed/cancelled` | `planning.daily_plan.replanned` (+ `trigger`) |
| `day.finished` | `planning.day.finished` |
| `priority.rules.updated` | `decision.priorities.updated` |
| `path.item.*` | **INCHANGÉ** (DV-11 : le code fait foi) |
- Les applications restent des interfaces. Elles affichent, collectent,
  déclenchent et montrent des recommandations ; elles ne deviennent pas le
  cerveau stratégique.

Aucun code, modèle ou migration n'est modifié par ce document.

## Principes transverses

Un event est un fait daté notable auquel le système peut réagir ou qu'il voudra
analyser plus tard. Un calcul permanent ou un agrégat n'est pas un event : c'est
un attribut ou une valeur recalculée à la demande.

Un signal déterministe ne déclenche jamais d'action automatique. Fatigue,
pression financière ou autre signal brut peuvent informer visuellement
l'utilisateur, mais l'action vient d'une décision humaine explicite. Le signal
peut alors devenir la cause de cette décision, reliée par `causation_id`.

Tout event d'action doit porter la traçabilité utile : qui a agi
(`user` ou `ai`) et pourquoi (`reason`) quand l'action s'y prête. Sans ce contexte,
le journal devient du bruit ; avec ce contexte, il devient une matière
d'apprentissage.

Le système retrace au maximum et n'écrase pas. Les suppressions métier doivent
devenir des soft deletes ou des versions, avec event explicite quand le fait est
notable.

## Politique de chaînage

Le chaînage cible repose sur trois champs :

```text
correlation_id = le dossier, c'est-à-dire une histoire courte et lisible
causation_id   = la cause directe qui a déclenché l'event
profondeur     = niveau dans la cascade, champ à ajouter à events
```

Un fait racine ouvre un nouveau `correlation_id`, porte une `profondeur` de `1`
et n'a pas de `causation_id`. Un fait causé par un autre pointe vers sa cause
directe avec `causation_id` et augmente la `profondeur` de `1`.

Le remplissage se fait en deux temps.

En temps réel V1, le backend remplit le chaînage évident et immédiat : même
session, même action, même conséquence directe. Ce chaînage doit être simple,
sûr et déterministe.

En Phase 3 du Weekly Review, sustained_long_context peut proposer un chaînage profond sur les
events signalés comme importants par l'audit d'entrée ou par l'utilisateur
pendant la conversation. sustained_long_context cherche un pattern lié dans la mémoire
vectorielle, remonte aux events sources, propose le lien, puis l'utilisateur le
valide. Si rien n'est trouvé, la question revient à l'utilisateur et sa réponse
peut créer un nouveau pattern pour les revues suivantes.

Le système ne modélise pas l'effet papillon. Il va le plus loin possible sur ce
qui est pertinent pour l'IA ou l'humain, et laisse de côté ce qui n'intéresse
personne ou ce qui serait trop fragile à corréler.

## Catalogue par domaine

Le tri reprend les niveaux décidés dans les sources : V1, V2 et futur/non codé.
Aucun event V3 explicite n'est arrêté dans les sources de ce catalogue.

### FINANCE

Le domaine `finance` remplace les noms d'application de type `vault.*`.

| Event cible | Code actuel / statut | Payload attendu | Tri | Notes |
|---|---|---|---|---|
| `finance.transaction.created` | Existe ; émis par le service canonique `/api/imperium/vault/transactions`. | `transaction_id`, `transaction_type`, `amount_cents`, `currency`, `wallet`, `occurred_at`, `local_date`, `timezone`, `category`, `source`, `external_ref`, `is_reversal`, `reversal_of_transaction_id`. | V1 | Domaine `finance` canonique. Privacy `high`. |
| `finance.transaction.reversed` | Existe ; émis par le service canonique de reversal. | Payload transaction canonique + `original_transaction_id`, `reversal_reason`. | V1 | Le ledger financier reste factuel. La décision financière ne vient pas de Vault seul. |
| `finance.pressure.updated` | Existe ; émis après écriture d'un snapshot déterministe. | `snapshot_id`, `score`, `label`. | V1 | Le score reste calculé/signal déterministe `vault.pressure`; l'event journalise qu'un nouveau snapshot existe. |
| `finance.weekly_summary.created` | Existe ; émis par le job/calcul weekly profit. | `week_start`, `weekly_business_profit`. | V1 | The Path lit `weekly_finance_summaries` comme source de valeur ; l'event sert au réveil/chaînage. |

### WORSHIP — NON-RETENU (DV-11, 2026-07-15)

> **DÉCISION DV-11 (gravée, passe 0) : le canonique est ce que le code émet.**
> Le domaine `worship.*` proposé par ce catalogue N'EST PAS RETENU : les
> events religieux restent sous **`path.*`** (`path.item.*` émis aujourd'hui,
> `path.ghusl.*` reste le nom cible du mode ghusl, `path.prayer.*`,
> `path.fasting.*`, etc. pour les futurs). Le tableau ci-dessous est conservé
> comme inventaire SÉMANTIQUE (quels faits méritent un event, quels payloads)
> — lire chaque `worship.X.Y` comme `path.X.Y`.

Les pratiques religieuses ont des events dédiés quand elles ont une valeur
opérationnelle ou analytique.

| Event cible | Code actuel / statut | Payload attendu | Tri | Notes |
|---|---|---|---|---|
| `worship.habit.created` | Actuel : `path.item.created`. Existe, à renommer. | `item_id` + champs de `CreatePathItemRequest` : `local_date`, `timezone`, `title`, `description`, `category`, `priority_key`, `planned_start`, `planned_end`, `status`, `source`, `sort_order`, `metadata`. | V1 | `path` est un nom d'app, pas un domaine cible. |
| `worship.habit.updated` | Aucun event canonique observé aujourd'hui. À créer. | Non détaillé dans les sources. | V1 | Les sources demandent un ensemble fini `created/updated/completed/missed/skipped`. |
| `worship.habit.completed` | Actuel : `path.item.completed`. Existe, à renommer. | `{ item_id }`. | V1 | Fait daté notable. |
| `worship.habit.missed` | Aucun event canonique observé aujourd'hui. À créer. | Non détaillé dans les sources. | V1 | Le manqué est distinct du skipped. |
| `worship.habit.skipped` | Actuel : `path.item.skipped`. Existe, à renommer. | `{ item_id, skip_reason }`. | V1 | Action tracée avec raison. |
| `worship.sadaqa.given` | CODE (2026-10-18) sous `path.sadaqa.recorded` / `.deleted` et `path.sadaqa.settings_updated` : `/api/imperium/path/sadaqa/*`. | Don : `{ donation_id, related_week_start, record_in_vault }` ; supprimé : `+ vault_transaction_id` (privacy very_high ; jamais le montant ni la destination). Réglages : `{ percentage, safety_margin, applies_from }` (privacy high). | V1 | Acte religieux déclaré par l'utilisateur. **Divergence** avec la note d'origine (« pas de lien finance automatique ») : le code suit les docs 41 §9.4 et 42 §15.1, qui écrivent la dépense `sadaqa` au Vault ; l'utilisateur peut l'éviter don par don (`record_in_vault: false`). La dépense Vault garde la note « Sadaqa », sans destination. |
| `worship.prayer.*` | CODE (2026-10-18) sous `path.prayer.logged` / `.not_marked` / `.cleared` : `POST /api/imperium/path/prayers/{prayer}/mark` et `/clear`. | `{ prayer_log_id, prayer_name, prayer_date, status, previous_status, source: user_action }` (privacy high ; jamais la note). | V1 | Doc 41 §7. Une émission par statut posé ou changé ; `.cleared` quand l'utilisateur efface le statut. |
| `worship.ghusl.*` | CODE (2026-10-18) sous `path.ghusl.required` / `.completed` et `path.ghusl_address.updated` : `/api/imperium/path/ghusl*`. | Requis : `{ ghusl_state_id, required_since }` ; fait : `{ ghusl_state_id, mission_id, mission_completed }` ; adresse : `{ address_id, action added|updated|removed, address_type }` (privacy very_high). | V1 | Mode activé par l'utilisateur, jamais inféré. Privacy élevée ; vectorisation anonymisée. Sert à expliquer un comportement opérationnel sinon erratique. |
| `worship.fasting.*` | CODE (2026-10-18) sous `path.fasting.started` / `.ended` / `.broken` / `.cancelled` : `/api/imperium/path/fasts`. | `{ fast_id, fasting_date, fasting_type, source: user_action }` + démarré : `suhoor_at, iftar_at, hydration_limits` ; terminé : `ended_at` ; rompu : `broken_at, replan_prompt: true` (privacy high ; jamais la raison de la rupture). | V1 | Doc 41 §8. Imperium pourra proposer un nouveau planning sur `.broken`, confirmé par l'utilisateur. |
| `path.calendar.date_confirmed` / `.event_added` | CODE (2026-10-18) : `/api/imperium/path/calendar/*`. | Confirmé : `{ hijri_year, hijri_month, first_day }` (privacy medium) ; ajouté : `{ event_id, hijri_year, hijri_month, hijri_day }` sans libellé (privacy high). | V1 | Doc 41 16.1-ADD. `date_predicted` pas émis (aucun job) ; Imperium lit `/calendar/events`. |
| `worship.quran.*` | CODE (2026-10-18) sous `path.quran.progress.updated`, `path.quran.khatm_confirmed`, `path.quran.plan_updated` : `/api/imperium/path/quran/*`. | Progression : `{ page, previous_page, regression }` ; khatm : `{ khatm_count }` ; plan : `{ plan_id, plan_type, pages_per_day, active }` (privacy high). | V1 | Apprentissage, révision, plans journaliers. |
| `worship.dhikr.*` | CODE (2026-10-18) sous `path.adhkar.incremented`, `path.adhkar.reset`, `path.routine.updated` : `/api/imperium/path/adhkar/*`. | Appui : `{ routine_id, adhkar_type, period_key, amount, count, target_reached, source }` ; remise à zéro : `{ routine_id, period_key, previous_count }` ; routine : `{ routine_id, action, adhkar_type, active, target_count, frequency }` (privacy high). | V1 | Adhkar quotidiens et ajout de nouveaux dhikr. |

Deux events actuels existent aussi dans le code sous `path.item.started` et
`path.item.cancelled`. Le tri cible ne les retient pas comme types dédiés :
le chantier de renommage devra les résorber proprement dans le modèle
`worship.habit.*` décidé, sans inventer de nouveaux noms d'app.

### PLANNING

Le domaine `planning` couvre missions, plans du jour, fin de journée et objectifs
opérationnels. Il remplace les préfixes actuels `mission.*` et `day.*`.

#### Missions

| Event cible | Code actuel / statut | Payload attendu | Tri | Notes |
|---|---|---|---|---|
| `planning.mission.created` | Actuel partiel : `mission.backlog.created`. Existe, à renommer/aligner. | `{ created_by: user|ai, objective_id, project_id, reason }`. | V1 | Une mission sert un objectif qui sert un projet. Savoir qui, quand et pourquoi est précieux. |
| `planning.mission.activated` | Actuel ambigu : `mission.started` peut aussi venir d'une promotion backlog. À clarifier/renommer. | `{ activated_by: user|ai, reason }`. | V1 | À distinguer du démarrage effectif. |
| `planning.mission.deactivated` | Aucun event canonique observé aujourd'hui. À créer. | `{ deactivated_by: user|ai, reason }`. | V1 | Action explicite, pas simple baisse de score. |
| `planning.mission.started` | Actuel : `mission.started`. Existe, à renommer. | `mission_id` + champs de `StartMissionRequest` : `title`, `category`, `domain`, `priority_level`, `mission_type_category`, `planned_start_at`, `planned_end_at`. | V1 | Le code a deux émetteurs actuels avec payloads différents ; à normaliser. |
| `planning.mission.completed` | Actuel : `mission.completed` via `mission.{outcome}` dynamique. Existe, à renommer. | `{ mission_id, outcome, reason }` aujourd'hui ; cible : mission réussie. | V1 | Fait positif distinct. |
| `planning.mission.annexes_attached` | CODE (2026-10-17) : `POST /api/imperium/missions/{id}/annexes`. | `{ mission_id, annex_mission_ids }`. | V1 | Missions annexes V1 allégées (doc 53 §3.1). La complétion de la porteuse porte `completed_annex_mission_ids` dans `planning.mission.completed`. |
| `pulse.food_stock.updated` | CODE (2026-10-17) : validation d'un justificatif avec lignes au stock ; ajout et modification manuels. | Ticket : `{ source: vault_receipt, source_ref, items_added, stock_item_ids }` ; manuel : `{ source: manual, action created|updated|consumed|removed, stock_item_id, version, fields }` ; scan : `{ source: pantry_scan, scan_id, items_added, items_updated, stock_item_ids }` ; chatbot : `{ source: chatbot, declaration_id, items_added, stock_item_ids }` ; repas : `{ source: meal, meal_id, items_decremented, items_finished, stock_item_ids }` ; eau bue : `{ source: hydration, hydration_log_id, items_finished, stock_item_ids }` (privacy medium). | V1 | Doc 40 §11. Une émission par ticket, scan, ajout par le chatbot, repas ou appui d'hydratation, une par version manuelle. |
| `pulse.hydration.logged` | CODE (2026-10-17) : `POST /api/imperium/pulse/hydration-logs`. | `{ hydration_log_id, amount_ml, logged_at, source, stock_decrement_applied }` (privacy medium). | V1 | Doc 40 §12. Une émission par appui (pas au rejeu). |
| `pulse.workout.completed` | CODE (2026-10-17) : `POST /api/imperium/pulse/workouts/{id}/complete`. | `{ workout_id, planned_at, intensity_score, duration_minutes, exercises_done, exercises_skipped }` (privacy medium). | V1 | Doc 40 §13.2. Une émission par séance. |
| `pulse.workout.skipped` | CODE (2026-10-17) : `POST /api/imperium/pulse/workouts/{id}/skip`. | `{ workout_id, planned_at, reason }` (privacy medium). | V1 | Doc 40 §13.2. Une émission par séance. |
| `pulse.equipment.updated` | CODE (2026-10-17) : `POST` et `DELETE /api/imperium/pulse/equipment`. | `{ equipment_id, action added|removed, name }` (privacy low). | V1 | Doc 40 §13-EQUIP. Une émission par ajout ou retrait réel. |
| `pulse.health_consent.granted` / `.revoked` | CODE (2026-10-17) : `POST` et `DELETE /api/imperium/pulse/consents/{domain}`. | `{ domain, text_version }` (privacy medium). | V1 | Doc 08 PULSE-004. |
| `pulse.body_snapshot.created` / `.deleted` | CODE (2026-10-17) : `/api/imperium/pulse/body-snapshots`. | Créé : `{ snapshot_id }` ; supprimé : `{ deleted, scope one|all }` — aucune mesure (privacy high). | V1 | Doc 40 §14. Le journal étant en ajout seul, il ne garde jamais de valeur corporelle. |
| `pulse.pain.logged` / `.resolved` / `.deleted` | CODE (2026-10-17) : `/api/imperium/pulse/pain-logs`. | `{ pain_log_id }` ; supprimé : `{ deleted, scope one|all }` — aucun détail de douleur (privacy high). | V1 | Doc 40 §16, doc 08 PULSE-004. |
| `pulse.medical_document.uploaded` / `.deleted` | CODE (2026-10-17) : `/api/imperium/pulse/medical-documents` et job `pulse.medical_retention`. | `{ document_id }` ; supprimé : `{ document_id, rules_deleted | reason: retention }` (privacy very_high). | V1 | Doc 34 §16-bis. Aucun contenu de document. |
| `pulse.medical_rule.activated` / `.deactivated` / `.expired` | CODE (2026-10-17) : `/api/imperium/pulse/medical-rules/*` et job `pulse.medical_retention`. | `{ rule_id, rule_type, severity }` (privacy very_high). | V1 | Doc 34 §10. Imperium pourra replanifier sur `activated` ; jamais le texte de la règle. |
| `pulse.meal.logged` | CODE (2026-10-17) : `POST /api/imperium/pulse/meals/{id}/confirm`. | `{ meal_id, eaten_at, has_macros, stock_decrement_applied }` (privacy high). | V1 | Doc 40 §10.2. Une émission par repas validé. |
| `pulse.pantry_scan.analyzed` / `.failed` / `.validated` / `.cancelled` | CODE (2026-10-17) : `/api/imperium/pulse/food-stock/scans`. | `{ scan_id, lines | reason | items_added, items_updated }` (privacy medium). | V1 | Doc 37 §5.4. Les écritures au stock restent `pulse.food_stock.updated` (source pantry_scan). |
| `finance.wallet.updated` | CODE (2026-10-18) : `POST /api/vault/wallet/snapshots`. | `{ snapshot_id, recorded_at, source }` sans montants (privacy high). | V1 | Doc 42 §8.1. La pression relit le dernier relevé. |
| `finance.receipt.extracted` / `.failed` / `.validated` / `.cancelled` | CODE (2026-10-17) : `/api/imperium/vault/receipt-extractions`. | `{ extraction_id, entry_app, … }` (privacy high ; jamais le texte du ticket). | V1 | Doc 37 §3.4. `.validated` porte `transaction_id` ; la dépense elle-même reste `finance.transaction.created`. |
| `inbox.document.uploaded` / `.analyzed` / `.validated` / `.vectorized` / `.rejected` / `.deleted` | CODE (2026-10-17) : `/api/ai/knowledge-inbox` + job `ai.knowledge_inbox`. | `{ item_id, entry_app, … }` (privacy high). | V1 | Doc 70 §9. `.deleted` = suppression délibérée (sources + mémoires directes neutralisées). |
| `planning.project.created` / `planning.project.reordered` / `planning.project.deleted` / `planning.project.completed` | CODE (2026-10-17) : routes `/api/imperium/projects`. | created `{ project_id, source, rank }` ; reordered `{ project_ids }` ; deleted `{ project_id, cancelled_missions }` ; completed `{ project_id, promoted_project_ids }`. | V1 | Doc 71 §3. La création d'une mission de projet émet `planning.mission.created { mission_id, project_id, created_by }` ; sa suppression `planning.mission.aborted { reason: deleted_by_user }`. |
| `planning.replan.requested` | CODE (2026-10-17) : `POST /api/imperium/day/replan` ou hook. | `{ replan_event_id, trigger, hook_type, reason_category, ai_task_id }`. | V1 | Doc 43 §3.4 ; le détail texte reste dans `planning_replan_events`. L'acceptation émet `planning.daily_plan.replanned { plan_id, version, reason, trigger, replan_event_id }`. |
| `planning.replan.revision_requested` | CODE (2026-10-17) : `POST /api/imperium/day/replan/{id}/revise`. | `{ replan_event_id, ai_task_id, proposal_version }`. | V1 | Réveille le job runner `imperium.rolling_replan` (doc 43 §3.2). |
| `planning.mission.rescheduled` | CODE (2026-10-17) : sortie du standby par nouvelle échéance (`POST /api/imperium/missions/{id}/standby/resolve`). | `{ mission_id, decision, deadline_at, note }`. | V1 | Doc 43 §5.4. « Faite » et « annulée » réutilisent `planning.mission.completed` et `planning.mission.aborted` (`reason: standby_cancelled`). `planning.day.finished` porte `missions_returned_to_backlog` et `standby_mission_ids`. |
| `planning.mission.aborted` | Actuels à remplacer : `mission.failed` et `mission.abandoned`. À renommer/refondre. | `{ reason: abandoned|no_resources|poor_organization|no_energy|expired|... }`. | V1 | Décision E1 : `abandoned` est une raison, pas un type. Résout le double émetteur `mission.failed`. |
| `planning.mission.ai_disagreement` | Aucun event canonique observé aujourd'hui. À créer. | Désaccord de planification IA-humain, avec proposition, correction et raison. | V2 | Event séparé car matière première du LoRA d'autonomie. Émis en plus de `planning.mission.aborted`, relié par `correlation_id` et `causation_id`. |
| `planning.mission.deferred` | Aucun event canonique observé aujourd'hui. À créer. | `{ reason, deferred_by }`. | V1 | À émettre quand une mission est sautée délibérément : mode ghusl, replan qui écarte explicitement. Pas quand le score baisse tout seul. |

Le rescoring d'une mission n'est pas un event. Le score change en permanence
avec l'urgence ; il appartient à `decision_mission_scores` ou à l'équivalent
calculé, pas au journal des faits.

#### Plans et journée

| Event cible | Code actuel / statut | Payload attendu | Tri | Notes |
|---|---|---|---|---|
| `planning.daily_plan.generated` | Actuel : `day.plan.created`. Existe, à renommer. | `plan_id` + champs de `CreateDailyPlanRequest` + `generated_from`. | V1 | Le plan du jour est né. |
| `planning.daily_plan.replanned` | Actuels proches : `day.plan.activated`, `day.plan.completed`, `day.plan.cancelled`. À créer/aligner. | `{ version, reason, trigger }`. | V1 | D4 versionné. `causation_id` pointe vers le déclencheur selon E2. |
| `planning.day.started` | Existe ; émis par `POST /api/imperium/day/start`. | `{ planning_day_id, felt_energy }`. | V1 | Racine de la journée opérationnelle. Le ressenti subjectif est borné de 1 à 5 ; la date locale et le fuseau restent dans `planning_days`. |
| `planning.day.finished` | Actuel : `day.finished`, normalisé à l'émission. Existe. | `FinishDayRequest` complet + `planning_day_id`; `local_date` et `timezone` sont normalisés depuis la journée ouverte. | V1 | Ferme `planning_days`, lie `day_review_id` et conserve `corr_day_finish_{review.id}`. Sans journée ouverte, la mutation est rejetée. |
| `planning.weekly_plan.*` | Futur/non codé. | Non détaillé dans les sources. | Futur | À créer quand les tables existeront. |
| `planning.monthly_plan.*` | Futur/non codé. | Non détaillé dans les sources. | Futur | À créer quand les tables existeront. |

#### Profit opérationnel

| Event cible | Code actuel / statut | Payload attendu | Tri | Notes |
|---|---|---|---|---|
| `planning.profit_target.set` | Aucun event canonique observé aujourd'hui. À créer. | Objectif de profit fixé par le WR. | V2 | Le profit hebdo lui-même reste un agrégat, pas un event. |
| `planning.profit_target.reached` | Aucun event canonique observé aujourd'hui. À créer. | Constat de fin de semaine. | V2 | Fait lié à l'objectif. |
| `planning.profit_target.missed` | Aucun event canonique observé aujourd'hui. À créer. | Constat de fin de semaine. | V2 | Fait lié à l'objectif. |

### HEALTH

Le domaine `health` reste informatif en V1. Il nourrit les agrégats WR et les
corrélations, sans déclencher automatiquement le planning.

| Event cible | Code actuel / statut | Payload attendu | Tri | Notes |
|---|---|---|---|---|
| `health.entry.logged` | Aucun event canonique observé aujourd'hui ; les entrées Pulse écrivent `health_entries` sans event. À créer. | Saisie du jour : sommeil, énergie, fatigue, poids, etc. | V1 | Informatif uniquement. Aucun déclenchement automatique. |
| `health.fatigue.high` | Aucun event canonique observé aujourd'hui. À créer seulement dans le cas manuel/explicite décrit. | Constat de fatigue élevée. | V1 | Si l'utilisateur décide de replanifier à cause de la fatigue, alors deux events sont reliés : `health.fatigue.high` puis `planning.daily_plan.replanned { reason: fatigue }`. |
| `health.pain.logged` | Futur/non codé. | Non détaillé dans les sources. | Futur | Tables non codées. |
| `health.workout.*` | Futur/non codé. | Non détaillé dans les sources. | Futur | Tables non codées. |

Le scoring santé n'est pas modifié en V1. Aucune pondération nouvelle ne doit
être ajoutée tant que les tests réels ne l'ont pas justifiée.

### DECISION

Le domaine `decision` porte les faits rares qui changent l'arbitrage du système.

| Event cible | Code actuel / statut | Payload attendu | Tri | Notes |
|---|---|---|---|---|
| `decision.priorities.updated` | Actuel : `priority.rules.updated`. Existe, à renommer. | `ReplacePriorityRulesRequest` complet : liste de `priority_key`, `label`, `rank_order`, `importance_score`. | V1 | L'utilisateur change l'ordre religious/business/finance/health ; cela recalcule tout le scoring. |

Il n'y a pas de `decision.override.applied`. C'est un choix de design : Imperium
doit planifier à la place de l'utilisateur pour décharger son cerveau. Les
corrections passent par `planning.mission.aborted` + raison,
`planning.daily_plan.replanned` + raison, ou
`planning.mission.ai_disagreement`.

Une mission scorée n'est pas un event. C'est un calcul permanent.

### CALENDAR

Le domaine `calendar` est déjà générique, mais il doit cesser les suppressions
silencieuses.

| Event cible | Code actuel / statut | Payload attendu | Tri | Notes |
|---|---|---|---|---|
| `calendar.event.created` | Existe. À enrichir. | `calendar_event_id` + champs de `CalendarEventCreate` : `event_type` calendrier (`event`, `deadline`, `vacation`), `title`, `starts_at`, `ends_at`, `blocks_time`, `location`, `notes`; cible enrichie avec `{ created_by: user|ai, reason, ... }`. | V1 | Attention : `event` désigne ici un rendez-vous calendrier, pas le journal `events`. |
| `calendar.event.updated` | Aucun event canonique observé aujourd'hui. À créer. | `{ updated_by: user|ai, reason, ... }`. | V1 | Mise à jour traçable. |
| `calendar.event.deleted` | Aucun event canonique observé aujourd'hui. À créer. | `{ deleted_by: user|ai, reason }`. | V1 | Corrige le hard delete silencieux repéré. Suppression = soft delete + trace. |

### RIDES

Le domaine `rides` remplace le nom d'application Vector pour les faits VTC.
Il est futur/non codé, mais il touche une priorité V1 car le deuxième scoring
acceptation de course / importance / zone doit être testé assez tôt.

| Event cible | Code actuel / statut | Payload attendu | Tri | Notes |
|---|---|---|---|---|
| `rides.session.started` | CODE (2026-10-18) : `POST /api/imperium/vector/sessions`. | `{ session_id, target_ca_cents, mission_id }` (privacy high). | V1 | Vector conseille, analyse et optimise ; il n'automatise pas d'action Bolt illégale ou contraire aux plateformes. |
| `rides.session.ended` | CODE (2026-10-18) : `POST …/vector/sessions/{id}/complete`. | `{ session_id, revenue_cents, expense_cents, objective_reached, elapsed_minutes }` (privacy high). | V1 | Session VTC terminée. |
| `rides.ride.accepted` / `.missed` / `.completed` | CODE (2026-10-18) : `POST /api/imperium/vector/offers/{id}/decision` et `/outcome`. | Décision : `{ offer_id, session_id, price_cents, hourly_rate_offered_cents }` ; terminée : `{ offer_id, session_id, earning_cents, mobilized_minutes, hourly_rate_cents }` (privacy medium). | V1 | Fait d'acceptation, pas automatisation. |
| `rides.ride.refused` | CODE (2026-10-18) : `POST /api/imperium/vector/offers/{id}/decision`. | `{ offer_id, session_id, price_cents, hourly_rate_offered_cents }`, sans la note (privacy medium). | V1 | Fait de refus, utile au scoring et à l'analyse. |
| `rides.drop_zone.recorded` | CODE (2026-10-18) : `POST …/vector/sessions/{id}/drop-zone`. | `{ session_id, drop_zone_id, zone, real_duration_minutes }` (privacy high). | V1 | Dépose confirmée par l'utilisateur (VEC-10) ; les revenus et dépenses restent `finance.transaction.created` (external_ref `rides:…`). |
| `rides.zone.recommended` / `rides.recommendation.feedback_recorded` | CODE (2026-10-18) : `/api/imperium/vector/recommendations*`. | `{ recommendation_id, recommendation, zone, confidence, session_id }` ; retour : `{ recommendation_id, useful, ride_user_action }` (privacy medium). | V1 | Doc 33 §5. Conseil seulement, jamais d'action sur l'appli VTC. |
| `rides.rule.revised` | CODE (2026-10-18) : `PATCH /api/imperium/vector/rules/{code}`. | `{ rule_code, revision_type, version }` (privacy low). | V1 | Doc 57 §4.12 ; l'avant / après reste dans `rides_rule_revisions`. |
| `rides.zone.repositioned` | Futur/non codé. | Non détaillé dans les sources. | Futur | Déplacement de zone. |

### VEHICLE

Le domaine `vehicle` est transverse : un fait véhicule peut avoir un coût
finance, impacter la disponibilité rides et déclencher un replan planning.
Il illustre le chaînage E2.

| Event cible | Code actuel / statut | Payload attendu | Tri | Notes |
|---|---|---|---|---|
| `vehicle.maintenance.completed` | Futur/non codé. | Non détaillé dans les sources. | Futur | Exemple : vidange. |
| `vehicle.incident.logged` | Futur/non codé. | Non détaillé dans les sources. | Futur | Exemple : pneu crevé. Peut chaîner vers finance, rides et planning. |
| `vehicle.odometer.updated` | Futur/non codé. | Non détaillé dans les sources. | Futur | Relevé kilométrique. |

### SOCLE / AUTH

Les `auth_events` restent séparés du journal métier D2. C'est un journal
technique sain, append-only, mais hors catalogue `events`.

| Event technique actuel | Journal / statut | Payload observé | Tri | Notes |
|---|---|---|---|---|
| `login` | `auth_events`. Existe. | `user_id`, `device_id`, IP, user-agent, `success`, `reason` en cas d'échec. | Hors D2 | Mot nu, à normaliser en dotted si ce chemin est retouché. Pas prioritaire. |
| `auth.refresh.rotated` | `auth_events`. Existe. | `user_id`, `device_id`, IP, user-agent. | Hors D2 | Journal technique auth. |
| `auth.refresh.failed` | `auth_events`. Existe. | Idem + `reason`. | Hors D2 | Journal technique auth. |
| `auth.logout` | `auth_events`. Existe. | `user_id`, `device_id`, IP, user-agent. | Hors D2 | Dotted 2 niveaux. |
| `auth.logout.failed` | `auth_events`. Existe. | Idem + `reason`. | Hors D2 | Journal technique auth. |
| `auth.password.reset` | `auth_events`. Existe via CLI. | `user_id`, `reason`. | Hors D2 | Journal technique auth. |
| `auth.master_key.reset` | `auth_events`. Existe via CLI. | `user_id`, `reason`. | Hors D2 | Segment avec underscore ; ne passerait pas la regex dotted stricte de l'ingestion générique. |
| `auth.devices.revoked` | `auth_events`. Existe via CLI. | `user_id`, `reason=revoked_devices=<n>`. | Hors D2 | Journal technique auth. |
| `user.bootstrap.created` | `auth_events`. Existe via CLI. | `user_id`, `device_id`, `reason`. | Hors D2 | Journal technique de bootstrap utilisateur. |

## Ce qui n'est pas un event

La valeur de pression financière n'est pas inventée par un event : c'est un
signal déterministe (`vault.pressure`) issu de `pressure_snapshots`. L'event
`finance.pressure.updated` existe seulement pour journaliser la création d'un
nouveau snapshot et réveiller les consommateurs autorisés ; il ne doit pas
déclencher de replan automatique à lui seul.

Le profit hebdomadaire reste un agrégat stocké dans `weekly_finance_summaries`.
L'event `finance.weekly_summary.created` existe pour signaler qu'un résumé a été
recalculé ; les faits d'objectif restent côté planning :
`planning.profit_target.set`, `planning.profit_target.reached`,
`planning.profit_target.missed`.

Le score de mission n'est pas un event. C'est un attribut ou calcul permanent
qui varie avec l'urgence et le contexte. Une mission rescored n'est donc pas un
fait journalisé ; seules les décisions explicites liées à cette mission le sont.

## À faire côté code — ÉTAT AU 2026-07-15 (passe 0)

1. ✅ FAIT (partiel par décision) : `vault.*`→`finance.*`, `mission.*`/`day.*`
   →`planning.*`, `priority.*`→`decision.*` appliqués (compat lecture 30 j).
   `path.*`→`worship.*` NON APPLIQUÉ : DV-11 grave `path.*` comme canonique.
2. ✅ FAIT : `events.depth` rempli à l'émission (émetteur partagé
   `app/services/events/emitter.py` — cause déclarée → depth parent+1).
3. ✅ FAIT pour les types émis par le backend (dotted génériques).
4. ✅ FAIT : E1 résolu — `mission.failed`/`mission.abandoned` →
   `planning.mission.aborted` (+ raison). `planning.mission.ai_disagreement`
   reste V2 (à créer à la passe Daily/WR).
5. Débrancher `imperium_events` selon E3 option B : EN COURS (routes
   dépréciées, doc 04 patché ; coupure des lecteurs orphelins à suivre).
6. ✅ FAIT (migration 0035) : soft delete calendrier + `calendar.event.deleted`
   émis (lié à la création par causation, passe 0).
7. ✅ FAIT : `correlation_id`/`causation_id` remplis par la passe déterministe
   des liens déclarés (même action, conséquence directe) ; le chaînage profond
   reste WR Phase 3.

## Types des passes à venir

Chaque passe ajoute ses types à CE catalogue au moment de son patch docs de
fin de passe, sous domaines génériques : Pulse → `health.*` ; WR → `planning.*`
(revue/plan) ; Daily → `planning.*` ; Vector → `rides.*`/`vehicle.*` (jamais
`vtc.*`, nom d'app interdit par D3). Le runner (passe 0) consomme ces types
via `job_definitions.event_types` + `job_cursors`.
