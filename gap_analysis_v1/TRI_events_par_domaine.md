# TRI DES EVENTS PAR DOMAINE (matière du futur doc 77)
Date : 2026-07-04. Basé sur INVENTAIRE_events.md (Fable) + décisions E1/E2/E3
(DECISIONS_events.md). Rappels : D2 (journal `events` unique), D3 (dotted, domaines
génériques), convention de nommage (préfixe = domaine, pas nom d'app).

PRINCIPES TRANSVERSES dégagés pendant le tri (valent partout) :
- Un EVENT = un fait DATÉ NOTABLE auquel on peut réagir / qu'on voudra analyser.
  Un CALCUL PERMANENT ou un AGRÉGAT (score de mission, profit hebdo, pression
  financière) n'est PAS un event : c'est un attribut/agrégat recalculé à la demande.
- Un signal déterministe (fatigue, pression financière) ne DÉCLENCHE JAMAIS d'action
  automatique (trop de faux positifs, cf. exemple du prêt à un ami / confounding
  CatBoost). Il est VISUEL/informatif pour l'humain (qui a le contexte). L'action vient
  d'une DÉCISION HUMAINE explicite ; le signal fournit la CAUSE (reliée par causation E2).
- Traçabilité : chaque event porte QUI (user|ai) + POURQUOI (reason) quand c'est une
  action. Sans ça = bruit inexploitable ; avec = matière d'apprentissage.
- On retrace un maximum (stockage gratuit), on n'écrase jamais (soft delete, versionnement).

## FINANCE
- finance.transaction.created  (ex vault.*, renommé) — V1
- finance.transaction.reversed (ex vault.*, renommé) — V1
- PRESSION FINANCIÈRE : PAS un event. VISUELLE uniquement (jauge informative). Déterministe
  = trop de faux positifs (ex : prêt à un ami qui fausse le calcul). Handoff pression→replan
  ANNULÉ. Une pression "intelligente/contextuelle" = futur possible, pas maintenant.
- PROFIT HEBDO : PAS un event (agrégat calculé à la demande). Mais faits liés = events
  (voir PLANNING : profit_target.set/reached/missed).

## WORSHIP
Chaque pratique a ses events DÉDIÉS dès le début (ensemble fini, finesse gérable) :
- worship.habit.* (ex path.item.*, renommés : created/updated/completed/missed/skipped) — V1
- worship.sadaqa.given — V1. Acte religieux 100% (donnable en argent/riz/service). PAS de
  lien finance auto. Baromètre déterministe suggère un montant (depuis le profit) mais
  l'accomplissement est DÉCLARÉ par l'utilisateur, sans traçage du moyen.
- worship.prayer.*   (prières accomplies/manquées)
- worship.ghusl.*    (MODE GHUSL, voir ci-dessous)
- worship.fasting.*  (jeûne : started/broken)
- worship.quran.*    (apprentissage/révision du Coran, plans journaliers)
- worship.dhikr.*    (adhkar quotidiens, ajout de nouveaux dhikr)
MODE GHUSL — feature qui EXPLIQUE au système un comportement qui semblerait ERRATIQUE
autrement (refuser des courses + long détour depuis Versailles vers un point de ghusl, avant
la prochaine prière). Activé par l'utilisateur (jamais inféré ; le ghusl matinal tranquille
n'est pas signalé). Mécanique : scoring de mission → saute les missions les moins importantes
du créneau (retour dans la pile à re-scorer) → insère le ghusl prioritaire avant la prière.
100% MODÈLE LOCAL. privacy_level ÉLEVÉ, mais vectorisation anonymisée (pas de fuite).
PRINCIPE : le religieux ne signale QUE ce qui a un impact opérationnel.

## PLANNING
Missions (cycle de vie) :
- planning.mission.created { created_by: user|ai, objective_id, project_id, reason } — V1
  (une mission sert un objectif qui sert un projet ; savoir qui/quand/pourquoi = précieux)
- planning.mission.activated   { activated_by: user|ai, reason } — V1
- planning.mission.deactivated { deactivated_by: user|ai, reason } — V1
- planning.mission.started — V1
- planning.mission.completed — V1 (réussie)
- planning.mission.aborted { reason: abandoned|no_resources|poor_organization|no_energy|
  expired|... } — V1 (E1 ; "abandoned" = une raison, pas un type)
- planning.mission.ai_disagreement — V2 (E1 ; event séparé, matière LoRA)
- planning.mission.deferred { reason, deferred_by } — quand SAUTÉE DÉLIBÉRÉMENT (mode ghusl,
  replan qui écarte explicitement), PAS quand le score baisse tout seul.
- mission "rescored" : PAS un event (le score change en permanence avec l'urgence ; c'est un
  attribut dans decision_mission_scores, pas un fait daté).
Plans :
- planning.daily_plan.generated — V1 (le plan du jour est né)
- planning.daily_plan.replanned { version, reason, trigger } — V1 (D4 versionné ;
  causation_id vers le déclencheur, E2)
- planning.day.finished — V1
- FUTUR : planning.weekly_plan.* / planning.monthly_plan.* (+ résumés) quand les tables existeront.
Profit (émis par le WR) :
- planning.profit_target.set — V2 (le WR fixe l'objectif de la semaine)
- planning.profit_target.reached / missed — V2 (constat fin de semaine)

## HEALTH
- health.entry.logged — V1. Trace la saisie du jour (sommeil/énergie/fatigue/poids...).
  Purement INFORMATIF : agrégats WR + matière à corrélation. AUCUN déclenchement automatique.
- Déclenchement via fatigue = MANUEL/EXPLICITE : si l'utilisateur décide de replanifier à
  cause de la fatigue → DEUX events reliés (causation E2) : health.fatigue.high (constat)
  + planning.daily_plan.replanned { reason: fatigue }. C'est le REPLAN (décision humaine)
  qui régénère, pas l'event santé.
- FUTUR (tables non codées) : health.pain.logged, workouts, etc.
- SCORING : NON TOUCHÉ en V1. On teste l'existant à fond d'abord. Aucune pondération nouvelle
  (fatigue, etc.) tant que les tests réels ne l'ont pas justifiée (anti-optimisation prématurée).

## DECISION
- decision.priorities.updated — V1 (l'utilisateur change son ordre religious/business/finance/
  health ; rare mais recalcule tout le scoring).
- PAS d'override (decision.override.applied) — CHOIX DE DESIGN, pas un oubli. Imperium =
  l'IA planifie À LA PLACE de l'utilisateur (décharger son cerveau). Un override ferait de
  l'utilisateur le planificateur (contraire au but) et appauvrirait l'apprentissage. Les
  corrections passent par aborted+reason / replanned+reason / ai_disagreement : on donne à
  l'IA l'ERREUR + la RAISON, pas la solution toute faite. Système "moins pratique" au début
  pour être "plus intelligent" à la fin.
- mission scorée : PAS un event (calcul permanent).
- Autres faits de décision : à compléter au passage "catalogue complet" plus tard.

## CALENDAR
- calendar.event.created { created_by: user|ai, reason, ... } — V1 (existe, à enrichir)
- calendar.event.updated { updated_by: user|ai, reason, ... } — V1
- calendar.event.deleted { deleted_by: user|ai, reason } — V1 (corrige le hard delete
  silencieux repéré par Fable)
- SOFT DELETE : plus de hard delete. Suppression = marquer supprimé + garder la ligne/trace.
- 📌 TÂCHE code : passer calendar de hard delete → soft delete + émettre calendar.event.deleted.

## RIDES (ex-vector) — FUTUR / NON CODÉ (grandes lignes)
- rides.session.started/ended, rides.ride.accepted/refused, rides.zone.repositioned
- Le "2e SCORING" (acceptation course / importance / zone) que l'utilisateur veut tester en
  V1 vit ICI. Domaine "futur" mais touche la priorité V1 → à coder assez tôt.

## VEHICLE — FUTUR / NON CODÉ (grandes lignes)
- vehicle.maintenance.completed (vidange...), vehicle.incident.logged (pneu crevé...),
  vehicle.odometer.updated
- Domaine transverse (finance=coût, rides=dispo, planning=le pneu déclenche un replan).
  Illustre le mieux le chaînage E2 (un fait → plusieurs events reliés par correlation_id).

## SOCLE / AUTH (rappel, hors D2)
- auth_events reste séparé (login, auth.refresh.*, auth.logout.*, user.bootstrap.created...).
  Journal technique sain. Normaliser "login" (mot nu) → dotted si on y touche. Pas prioritaire.
