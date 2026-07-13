# VAGUE 24 — Régénérations de plan (choc + mensuelle)

**Composition** : ACT-WR-20, ACT-WR-21. Fenêtre : 1 mois (un cycle mensuel réel).

```
id: ACT-WR-20    nom_fr: Régénération choc (taxonomie shock, immédiate hors WR)
domaine: wr       classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE ai_slot_transition SET tier='cloud_forced' WHERE
  slot_code='wr.plan_regen';  + POST /api/wr/plan/shock servi + abonnement taxonomie
prerequis_activation: [ACT-WR-18, ACT-SYS-10]
protocole_terrain: déclenchement MANUEL de test (raison de la taxonomie seedée : accident,
  panne immobilisante, événement familial majeur, perte de revenu, blessure, sinistre) →
  régénération complète PROPOSÉE le jour même → validation → active, l'ancienne superseded
critere_succes: JAMAIS auto-appliquée ; replans ordinaires inchangés ; ancienne version
  interrogeable
rollback: tier retour dry + route coupée (le plan actif reste)
source: spec WR §8.1, §13.6
prompt_codex: « Basculer plan_regen + activer la route choc ; smoke raison fixture →
  proposition ; consigner. »
observations: le pont Daily (classe shock du Niveau 2, V30) RÉUTILISE cette mécanique
  telle quelle
```

```
id: ACT-WR-21    nom_fr: Régénération mensuelle (anti-dérive des deltas)
domaine: wr       classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code='monthly_regen';
prerequis_activation: [ACT-WR-20, ACT-WR-19]
protocole_terrain: 1 cycle : régénération complète proposée (origin=monthly_regen), même
  contrat que le choc → validation → supersede propre
critere_succes: remise à plat cohérente avec les deltas accumulés ; historique intact
rollback: job disabled
source: spec WR §8.3 ; Q8 (remplace doc 52 §8 — patch doc à la passe, W-9)
prompt_codex: « Activer monthly_regen ; smoke run manuel ; consigner. »
observations: —
```
