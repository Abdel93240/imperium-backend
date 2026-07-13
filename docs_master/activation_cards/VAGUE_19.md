# VAGUE 19 — WR filets (rouge, review_due, digest, audit)

**Composition** : ACT-WR-07, ACT-WR-08, ACT-WR-09, ACT-WR-23. Durée : 3-7 j.

```
id: ACT-WR-07    nom_fr: Notification rouge en semaine (le rouge n'attend pas le rituel)
domaine: wr       classe: notifiant   echelon_audace: 3   statut: NOT_CODED
bascule_exacte: flag wr_red_notify_enabled=true (W5 pose la notification sur severity=red)
prerequis_activation: [ACT-WR-05, ACT-SYS-07]
protocole_terrain: item rouge (red flag référencé, contradiction à fort usage, choc plan)
  → notification immédiate ; le rouge N'APPLIQUE RIEN seul ; 7 j
critere_succes: chaque rouge notifié une fois ; zéro action automatique ; ack tracé
rollback: flag=false (les rouges restent en tête de docket)
source: spec WR §7 ; PATCH_WR W-7
prompt_codex: « Activer red_notify ; smoke item rouge fixture → notify ; consigner. »
observations: —
```

```
id: ACT-WR-08    nom_fr: Filet review_due hebdo (croyances silencieuses N mois)
domaine: wr       classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code='wr_review_due_weekly';
prerequis_activation: [ACT-WR-05]
protocole_terrain: patterns actifs sans confirmation/exposition depuis 6 mois → item
  belief_review_due (ligne de 5 s en Phase 4) ; vide tant que la mémoire est vide (V25)
critere_succes: tuyauterie verte (job tourne, zéro item = normal avant V25)
rollback: job disabled
source: spec WR §6.4
prompt_codex: « Activer review_due ; smoke fixture pattern ancien ; consigner. »
observations: —
```

```
id: ACT-WR-09    nom_fr: Digest P1 (assemblage 20-40k, caps par type, forage loggé)
domaine: wr       classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code='wr_digest_on_open';
prerequis_activation: [ACT-WR-05]
protocole_terrain: à l'ouverture du WR : wr_digests écrit (top docket cappé, rollups,
  anomalies, contradictions, état plan), token_estimate ≤ 40k dur ; 2 dimanches
critere_succes: plafond tenu (troncature par priorité, jamais par hasard) ; whitelist
  assembleur : zéro brut device/conversation/document (test §14.7)
rollback: job disabled
source: spec WR §9 P1, §3.6
prompt_codex: « Activer digest_on_open ; smoke assemblage fixture ; consigner. »
observations: consommé par la passe d'hypothèses (V22) — l'activer avant permet de LIRE
  des digests réels avant d'y brancher le frontier
```

```
id: ACT-WR-23    nom_fr: Audit hebdo agreement + métriques WR
domaine: wr       classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code IN
  ('wr_audit_weekly','wr_metrics_rollup');
prerequis_activation: [ACT-WR-02]
protocole_terrain: wr_metrics_weekly rempli (runs, items, durées, wr_mode, coût cloud
  estimé) ; 2 semaines
critere_succes: métriques = recomptage manuel sur 1 semaine
rollback: jobs disabled
source: spec WR §3.8, §12
prompt_codex: « Activer les 2 jobs ; smoke rollup ; consigner. »
observations: —
```
