# VAGUE 18 — Usine WR (le premier consommateur pérenne du journal)

**Composition** : ACT-WR-02, ACT-WR-03, ACT-WR-04, ACT-WR-05, ACT-WR-06 (lot de 5, tout
code pur). Prérequis : passe WR mergée éteinte ; V2 faite (l'usine lit les NOMS CIBLES) ;
lecteurs legacy migrés (AD-2, socle 0f). Durée : 3-7 j.

```
id: ACT-WR-02    nom_fr: Usine — déclencheur fin de session + filet 23:30 + curseurs
domaine: wr       classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code IN
  ('wr_factory_on_session_end','wr_factory_fallback');
prerequis_activation: [ACT-SYS-06, ACT-EVT-01]
protocole_terrain: chaque fin de session réelle → wr_worker_runs ; jours sans session →
  run 23:30 ; curseurs avancent sans trou ni double traitement ; 3-7 j
critere_succes: 7 j de runs sans trou (test curseurs au réel) ; run échoué n'avance pas
  son curseur (observé ou simulé)
rollback: jobs disabled (curseurs figés — la reprise retraite le retard, par design)
source: spec WR §4, §3.2 ; PATCH_WR W-5 (curseurs = prototype du contrat de consommation)
prompt_codex: « Activer les 2 déclencheurs ; smoke : fin de session fixture → run complet ;
  consigner. »
observations: c'est l'abonnement LISTEN/NOTIFY inaugural du système (le « events
  consommés » définitif — remplace le job jetable de V1, à désactiver alors)
```

```
id: ACT-WR-03    nom_fr: W1 rollups par domaine (code pur)
domaine: wr       classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: activer le worker w1 dans la config de l'usine (workers_enabled+=w1)
prerequis_activation: [ACT-WR-02]
protocole_terrain: agrégats quotidiens finance (flux, pression), missions (avancement,
  dérive deadline), Pulse (si V7+ : réel, sinon stub neutre loggé) ; 3-7 j
critere_succes: rollups = recalcul manuel sur 2 jours ; sources = tables CANONIQUES
  uniquement (AD-2 vérifié)
rollback: workers_enabled-=w1
source: spec WR §4 W1 ; PATCH_WR W-10
prompt_codex: « Activer W1 ; smoke rollup 1 jour fixture ; consigner. »
observations: —
```

```
id: ACT-WR-04    nom_fr: W4 anomalies (baselines 28 j ± MAD, bandes, variance inexpliquée)
domaine: wr       classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: workers_enabled+=w4 (+ signal_definitions ecosystem actives — partagées,
  PATCH_PULSE P-1, jamais de table wr_)
prerequis_activation: [ACT-WR-03]
protocole_terrain: drapeaux sur métriques de rollup ; marqueur « variance inexpliquée »
  quand ni lien causal ni raison déclarée proche ; 3-7 j
critere_succes: drapeaux plausibles sur 1 semaine réelle, zéro faux positif criant
rollback: workers_enabled-=w4
source: spec WR §4 W4 ; PATCH_WR W-2
prompt_codex: « Activer W4 ; smoke bandes fixtures ; consigner. »
observations: nourrit la sélection des events notables de W2 (V21)
```

```
id: ACT-WR-05    nom_fr: W5 assembleur de docket (priorités, portage, force_decision)
domaine: wr       classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: workers_enabled+=w5
prerequis_activation: [ACT-WR-03, ACT-WR-04]
protocole_terrain: items docket pending créés depuis W1/W4 (anomalies) ; priorité =
  severity × impact × fraîcheur × confidence (paramètres, pas en dur) ; defers →
  force_decision à 3 ; 3-7 j
critere_succes: dédup par evidence_refs ; priorités recalculées à chaque run ; le docket
  ne peut ni exploser ni enterrer (formule vérifiée au réel)
rollback: workers_enabled-=w5 (items pending conservés)
source: spec WR §4 W5, §7 ; PATCH_WR W-6 (docket = table canonique partagée)
prompt_codex: « Activer W5 ; smoke anomalie fixture → item pending priorisé ; consigner. »
observations: écritures automatiques AUTORISÉES par la doctrine spec (items pending, logs)
```

```
id: ACT-WR-06    nom_fr: Walker P4 (modes full 45 min / light 15 min, budget d'attention)
domaine: wr       classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: flag wr_walker_enabled=true (GET docket + POST decision servis)
prerequis_activation: [ACT-WR-05]
protocole_terrain: 1er WR : marcher le docket par priorité sous budget ; chaque refus
  exige decision_note (= label) ; mode light ne sert que rouges/forced/contradictions/
  deltas ; 1-2 dimanches
critere_succes: budget respecté ; politique de saut vérifiée (WR sauté → wr_mode=skipped,
  l'usine continue, rien ne se perd)
rollback: flag=false (items portent, par design)
source: spec WR §9 P4, §7
prompt_codex: « Activer le walker ; smoke : 3 items fixtures → décisions ; consigner. »
observations: auto-acceptation = table VIDE au seed ; première classe = ACT-WR-22 (V26)
```
