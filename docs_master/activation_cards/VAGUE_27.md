# VAGUE 27 — Daily fondations (barèmes, réglage, refresh)

**Composition** : ACT-DLY-01, ACT-DLY-02, ACT-DLY-03. Prérequis : passe Daily mergée,
verrou de parité VERT (§4 — bloquant, prouvé au merge). Durée : 2-3 j.

```
id: ACT-DLY-01   nom_fr: Barèmes df.* externalisés (le service lit les paramètres)
domaine: daily    classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: bascule au MERGE sous verrou de parité (CF-7 : accepté — effet prouvé
  nul par tests dorés ≥40 missions) ; cette fiche CONSIGNE la date
prerequis_activation: []
protocole_terrain: scores identiques avant/après (intrinsèque, pondéré, breakdown) ;
  2-3 j de comparaison sur missions réelles
critere_succes: zéro écart de score constaté au réel
rollback: revert du merge (constantes code reprennent)
source: spec Daily §4 ; PATCH_DAILY D-1/D-3 (constantes decision_framework.py:29-94,
  AUCUN mécanisme de réglage existant — branche « exposer les endpoints »)
prompt_codex: « Constater la parité au réel 2 j ; consigner la date de bascule de source
  de vérité. »
observations: seule bascule merge-time acceptée de la roadmap (verrou de parité)
```

```
id: ACT-DLY-02   nom_fr: Réglage des barèmes versionné (PUT settings/scoring)
domaine: daily    classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: flag daily_settings_enabled=true (endpoints GET/PUT settings/scoring)
prerequis_activation: [ACT-DLY-01]
protocole_terrain: 1 modification volontaire → nouvelle version df.* (date+raison
  OBLIGATOIRES) → event df.parameter_updated → refresh des scores ; 2-3 j
critere_succes: version tracée, ancien barème interrogeable, refresh effectif
rollback: flag=false (le réglage redevient impossible, les versions restent)
source: spec Daily §4.5, §10.3, §12
prompt_codex: « Activer les endpoints ; smoke PUT → version+event+refresh ; consigner. »
observations: les tests dorés ne s'appliquent qu'aux MIGRATIONS de code, pas aux réglages
  volontaires (documenté spec §10.3)
```

```
id: ACT-DLY-03   nom_fr: Refresh scores 06:30 + day_start
domaine: daily    classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code IN
  ('daily_scores_refresh','daily_day_start');
prerequis_activation: [ACT-SYS-06, ACT-DLY-01]
protocole_terrain: imperium_mission_scores rafraîchi chaque matin (critère A = temps) ;
  2-3 j
critere_succes: scores du registre = scores à la volée chaque matin
rollback: jobs disabled
source: spec Daily §4.6, §12
prompt_codex: « Activer les 2 jobs ; smoke run manuel ; consigner. »
observations: day_start ne SÉLECTIONNE que si V28 active — sinon no-op loggé
```
