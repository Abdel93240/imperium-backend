# VAGUE 23 — WR résiduel (enquêtes, conjonctif, deltas de plan)

**Composition** : ACT-WR-13, ACT-WR-14, ACT-WR-19. Fenêtre : 2 WR.

```
id: ACT-WR-13    nom_fr: P3 enquêtes dirigées (wr.investigation, cloud — le raisonnement le plus dur)
domaine: wr       classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE ai_slot_transition SET tier='cloud_forced' WHERE
  slot_code='wr.investigation';  + POST /api/wr/investigations servi
prerequis_activation: [ACT-WR-11, ACT-WR-12]
protocole_terrain: « pourquoi X ? » posé en Phase 2 → enquête (reprend les verdicts
  existants, peut demander de nouvelles sondes, fore multi-sauts) → chaîne explicative
  re-présentée en Phase 4 ; 2 WR
critere_succes: chaque enquête loggée avec seed_refs ; résultat = proposition, jamais
  écrit direct
rollback: tier retour dry
source: spec WR §9 P3a, §10 (« dernier à partir »)
prompt_codex: « Basculer investigation ; smoke question fixture → dossier ; consigner. »
observations: —
```

```
id: ACT-WR-14    nom_fr: P3 synthèse conjonctive (wr.conjunctive, cloud)
domaine: wr       classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE ai_slot_transition SET tier='cloud_forced' WHERE
  slot_code='wr.conjunctive';
prerequis_activation: [ACT-WR-12]
protocole_terrain: sur le digest : patterns que le pairé A→B ne voit pas (A+B+C→D,
  dérives lentes) → hypothèses additionnelles au docket ; 2 WR
critere_succes: ≥1 conjonction plausible non triviale OU silence honnête
rollback: tier retour dry
source: spec WR §9 P3b
prompt_codex: « Basculer conjunctive ; smoke digest fixture ; consigner. »
observations: —
```

```
id: ACT-WR-19    nom_fr: Deltas de plan hebdo (wr.plan_delta, cloud → cible LoRA 70B)
domaine: wr       classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE ai_slot_transition SET tier='cloud_forced' WHERE
  slot_code='wr.plan_delta';
prerequis_activation: [ACT-WR-18, ACT-WR-12]
protocole_terrain: 2 WR : opérations move/add/remove/modify avec reason_fr → items
  plan_delta_proposal → validés Phase 4 → appliqués Phase 5 (code : refs valides,
  conflits rejetés motivés) ; v_plan_current reflète
critere_succes: aucun delta appliqué sans validation ; le reste du plan réputé stable
  (kept_invariants honnêtes)
rollback: tier retour dry (deltas proposés restent proposés)
source: spec WR §8.2, §10
prompt_codex: « Basculer plan_delta ; smoke ops fixtures → application ; consigner. »
observations: dataset nativement en forme delta → futur LoRA 70B (F3-13)
```
