# VAGUE 2 — Hygiène du journal d'events (domaine system/events)

**Composition** : ACT-EVT-01, ACT-EVT-02, ACT-EVT-03. **Pourquoi maintenant** : chaque
semaine d'émission accroît le coût du renommage (journal append-only, AD-6) ; le premier
consommateur pérenne (usine WR, V18) doit lire les NOMS CIBLES. Le job V1 (rollup) est
jetable et tolère le renommage. Prérequis code : passe events courte. Durée : 3-7 j.

```
id: ACT-EVT-01    nom_fr: Renommage des domaines d'events + résolution E1 (mission.aborted)
domaine: system   classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: déploiement des émetteurs renommés (vault.*→finance.*, path.*→worship.*,
  mission.*/day.*→planning.*, priority.*→decision.*) ; pas de flag — bascule datée ici
prerequis_activation: []
protocole_terrain: SELECT DISTINCT event_type sur les events postérieurs à la bascule ;
  observer 3-7 j — plus aucun nom d'app émis ; mission.failed n'a plus qu'UN émetteur
  (planning.mission.aborted avec reason, completed pour la réussite)
critere_succes: 100 % des nouveaux events au vocabulaire doc 77 ; les anciens types restent
  en base (append-only) avec la date de bascule consignée ici comme frontière de lecture
rollback: revert du déploiement (les events déjà écrits gardent leur nom — donnée, R7)
source: doc 77 « À faire » n°1/3/4, AD-5/AD-6, DECISIONS_events E1
prompt_codex: « Déployer le renommage + E1 ; smoke : une mutation par domaine → event au
  nom cible ; consigner la DATE DE BASCULE au journal (frontière pour tout consumer). »
observations: DV-11 : ghusl = worship.ghusl.* (une seule vérité, alias doc 77)
```

```
id: ACT-EVT-02    nom_fr: Chaînage temps réel V1 (correlation/causation/depth remplis)
domaine: system   classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: déploiement des émetteurs passant le chaînage (même session, même action,
  conséquence directe — « simple, sûr, déterministe », doc 77 §chaînage)
prerequis_activation: [ACT-EVT-01]
protocole_terrain: sur 3-7 j : les events d'une même action partagent correlation_id ;
  causation_id non vide sur les conséquences directes ; depth = parent+1 (CHECK 0036)
critere_succes: échantillon de 10 chaînes vérifiées à la main, zéro correlation aléatoire
  sur les nouveaux events
rollback: revert (les events déjà chaînés restent)
source: doc 77 §chaînage, AD-7, ingestion.py:71-87 (accepte déjà)
prompt_codex: « Déployer le chaînage V1 ; smoke : mission.completed → daily rollup chaîné ;
  consigner au journal. »
observations: le chaînage PROFOND (découvert) reste la Phase 5 WR (ACT-WR-11/15)
```

```
id: ACT-EVT-03    nom_fr: Types V1 manquants du catalogue (compléments d'émission)
domaine: system   classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: déploiement des émetteurs ajoutés : finance.transaction.reversed,
  worship.habit.updated/.missed, planning.mission.deactivated/.deferred,
  calendar.event.updated, health.entry.logged
prerequis_activation: [ACT-EVT-01]
protocole_terrain: provoquer chaque fait (un reversal, un manqué, une mise à jour
  calendrier…) → l'event apparaît ; 3-7 j
critere_succes: chaque type V1 du doc 77 marqué « à créer » a ≥1 émission réelle correcte
rollback: revert émetteurs
source: doc 77 (colonnes « À créer », tri V1)
prompt_codex: « Déployer les émetteurs manquants ; smoke un par type ; consigner. »
observations: E2 « généreux sur les faits notables » (invariant partiel du digest §4)
```
