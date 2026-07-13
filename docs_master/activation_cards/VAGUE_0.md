# VAGUE 0 — État initial (features déjà ON, constat 2026-07-11)

Ces 8 features sont EN SERVICE (backend VPS, HYPOTHÈSE : migrations 0001-0037 appliquées,
digest 2026-07-11 limite 1). Elles n'ont pas été activées selon ce journal (antérieures) ;
leurs fiches existent pour que le rollback soit connu. Rollback générique = revert du
déploiement backend, jamais de perte de données (journaux append-only).

```
id: ACT-SYS-01    nom_fr: Émission d'events (19 types, 8 services)
domaine: system   classe: det_ecriture   echelon_audace: 2   statut: ON
bascule_exacte: en service (aucun flag — émission au fil des mutations)
prerequis_activation: []
protocole_terrain: table events (INSERT au fil des actions) ; zéro consommateur à ce jour
critere_succes: constat : chaque mutation notable écrit sa ligne (audit 2026-07-02)
rollback: revert déploiement (le journal reste, append-only tenu par triggers 0001-0003/0031)
source: app/services/* (grep event_type=), digest 2026-07-11 §3a
prompt_codex: s.o. (déjà en service)
observations: correlation aléatoire, causation vide (AD-7) ; noms d'apps à renommer (AD-6)
```

```
id: ACT-SYS-02    nom_fr: Idempotence des mutations (Idempotency-Key)
domaine: system   classe: det_ecriture   echelon_audace: 2   statut: ON
bascule_exacte: en service (systématique sur toutes les routes de mutation)
prerequis_activation: []
protocole_terrain: table idempotency_keys ; replay d'une mutation → même réponse
critere_succes: aucun doublon sur replay (testé)
rollback: s.o. (socle)
source: app/services/idempotency/, migration 0001, F1-22
prompt_codex: s.o.
observations: —
```

```
id: ACT-SYS-03    nom_fr: Scoring mission /100 (doc 52)
domaine: system   classe: det_lecture   echelon_audace: 1   statut: ON
bascule_exacte: en service (barèmes = constantes code, decision_framework.py:29-94)
prerequis_activation: []
protocole_terrain: scores + breakdown explanation sur missions/dashboard/score-preview
critere_succes: constat : fidèle doc 52, testé (meilleur module resync)
rollback: s.o.
source: backend/app/services/imperium/decision_framework.py (751 l.), F1-24
prompt_codex: s.o.
observations: externalisation des barèmes = ACT-DLY-01 (V27)
```

```
id: ACT-SYS-04    nom_fr: Lifecycle missions (une seule active par user)
domaine: system   classe: det_ecriture   echelon_audace: 2   statut: ON
bascule_exacte: en service (index partiel unique 0005 + garde 409)
prerequis_activation: []
protocole_terrain: création/démarrage/complétion de missions réelles — c'est le POINT
  D'ANCRAGE terrain de la vague V1 (« session/mission réelles » = usage, pas bascule)
critere_succes: invariant IMP-001 tenu (testé)
rollback: s.o.
source: app/services/imperium/missions.py, migration 0005, doc 08 IMP-001
prompt_codex: s.o.
observations: mission.failed double émetteur (AD-5) — corrigé par ACT-EVT-01
```

```
id: ACT-SYS-05    nom_fr: Calendrier (soft-delete) + daily plans CRUD
domaine: system   classe: det_ecriture   echelon_audace: 2   statut: ON
bascule_exacte: en service
prerequis_activation: []
protocole_terrain: imperium_calendar_events (0022/0035), imperium_daily_plans
critere_succes: constat (module calendar = seul (a) conforme de la campagne resync)
rollback: s.o.
source: migrations 0022/0035, F2-07, audit_resync
prompt_codex: s.o.
observations: le plan GÉNÉRÉ n'existe pas (v_plan_current = ACT-WR-18, V20)
```

```
id: ACT-VLT-01    nom_fr: Ledger Vault canonique (cents, reversals, wallet)
domaine: vault    classe: det_ecriture   echelon_audace: 2   statut: ON
bascule_exacte: en service (/api/imperium/vault)
prerequis_activation: []
protocole_terrain: imperium_vault_transactions ; guards append-only (0033)
critere_succes: constat (87 tests verts)
rollback: s.o.
source: migrations 0024-26/0033/0037, F2-08, GAP_vault §Code V1
prompt_codex: s.o.
observations: route legacy /api/vault encore servie → ACT-EVT-04 (V36, Q15)
```

```
id: ACT-PTH-01    nom_fr: Habits/check-ins Path (raison obligatoire sur manqué)
domaine: path     classe: det_ecriture   echelon_audace: 2   statut: ON
bascule_exacte: en service
prerequis_activation: []
protocole_terrain: habits + check-ins ; CHECK missed_requires_reason (0034)
critere_succes: constat (65 tests verts ; zéro IA/cloud religieux)
rollback: s.o.
source: migrations 0027/0034, imperium_path.py, audit_resync path
prompt_codex: s.o.
observations: tout le religieux spécifique (prières, jeûne, sadaqa) = GAP (V1/V5 + passe Path)
```

```
id: ACT-WR-01     nom_fr: WR conversationnel (plomberie sessions/messages, dry-run)
domaine: wr       classe: det_ecriture   echelon_audace: 2   statut: ON
bascule_exacte: en service en DRY-RUN (qwen_dry_run=True ; commit mémoire bloqué D5)
prerequis_activation: []
protocole_terrain: review_sessions/messages/rapports/décisions mémoire
critere_succes: constat (« machine V1 fonctionnelle », audit_resync WR-c)
rollback: s.o.
source: migrations 0010-0016, weekly_review_conversation.py
prompt_codex: s.o.
observations: la restructuration P1-P5 arrive avec la passe WR (V18+) ; D5 → ACT-SYS-15
```
