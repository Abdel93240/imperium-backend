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

En Phase 3 du Weekly Review, Fable peut proposer un chaînage profond sur les
events signalés comme importants par l'audit d'entrée ou par l'utilisateur
pendant la conversation. Fable cherche un pattern lié dans la mémoire
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
| `finance.transaction.created` | Actuel : `vault.transaction.created`. Existe, à renommer. | `transaction_id` + champs de `CreateVaultTransactionRequest` : `occurred_at`, `local_date`, `timezone`, `transaction_type`, `wallet`, `category`, `label`, `amount`, `currency`, `notes`. | V1 | Domaine `vault` interdit en cible car c'est un nom d'app. Privacy actuelle : `high`. |
| `finance.transaction.reversed` | Aucun event canonique observé aujourd'hui. À créer. | Non détaillé dans les sources. | V1 | Le ledger financier reste factuel. La décision financière ne vient pas de Vault seul. |

La pression financière n'est pas un event. Elle reste une jauge visuelle
informative. Le profit hebdomadaire n'est pas un event non plus ; les faits
liés aux objectifs de profit vivent côté `planning`.

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
| `worship.sadaqa.given` | Aucun event canonique observé aujourd'hui. À créer. | Sadaqa déclarée par l'utilisateur. | V1 | Acte religieux. Pas de lien finance automatique ; le baromètre peut suggérer un montant depuis le profit, mais l'accomplissement est déclaré sans traçage du moyen. |
| `worship.prayer.*` | Futur/non codé. | Non détaillé dans les sources. | Futur | Prières accomplies ou manquées. |
| `worship.ghusl.*` | Futur/non codé. | Non détaillé dans les sources. | Futur | Mode activé par l'utilisateur, jamais inféré. Privacy élevée ; vectorisation anonymisée. Sert à expliquer un comportement opérationnel sinon erratique. |
| `worship.fasting.*` | Futur/non codé. | Non détaillé dans les sources. | Futur | Jeûne : started/broken. |
| `worship.quran.*` | Futur/non codé. | Non détaillé dans les sources. | Futur | Apprentissage, révision, plans journaliers. |
| `worship.dhikr.*` | Futur/non codé. | Non détaillé dans les sources. | Futur | Adhkar quotidiens et ajout de nouveaux dhikr. |

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
| `planning.day.finished` | Actuel : `day.finished`. Existe, à renommer. | `FinishDayRequest` complet : `local_date`, `timezone`, `day_status`, `energy_level`, `fatigue_level`, `sleep_quality`, `stress_level`, `mood`, `main_win`, `main_problem`, `completed_items`, `missed_items`, `notes`, `free_text`. | V1 | Seul cas actuel avec `correlation_id` non totalement aléatoire : `corr_day_finish_{review.id}`. |
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
| `rides.session.started` | Futur/non codé. | Non détaillé dans les sources. | Futur | Vector conseille, analyse et optimise ; il n'automatise pas d'action Bolt illégale ou contraire aux plateformes. |
| `rides.session.ended` | Futur/non codé. | Non détaillé dans les sources. | Futur | Session VTC terminée. |
| `rides.ride.accepted` | Futur/non codé. | Non détaillé dans les sources. | Futur | Fait d'acceptation, pas automatisation. |
| `rides.ride.refused` | Futur/non codé. | Non détaillé dans les sources. | Futur | Fait de refus, utile au scoring et à l'analyse. |
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

La pression financière n'est pas un event. C'est un signal déterministe
potentiellement trompeur, par exemple quand un prêt à un ami fausse le calcul.
Elle doit rester visuelle et informative ; elle ne déclenche pas de replan
automatique.

Le profit hebdomadaire n'est pas un event. C'est un agrégat calculé à la demande.
Les faits notables autour du profit sont les objectifs fixés, atteints ou ratés :
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
