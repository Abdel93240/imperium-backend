# VAGUE 16 — Pulse advisory : cloud lourds (P3, P7, P10)

**Composition** : ACT-PLS-19, ACT-PLS-23, ACT-PLS-26. Slots cloud_forced/routed —
propositions plus rares, plus structurantes. Durée : 7-14 j (au rythme réel des besoins).

```
id: ACT-PLS-19    nom_fr: P3 new_training_program en advisory (p3.design cloud_forced)
domaine: pulse    classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE pulse_procedures SET active=true WHERE code='new_training_program';
prerequis_activation: [ACT-PLS-17, ACT-SYS-10, ACT-PLS-09]
protocole_terrain: 1 création de programme réelle : objectifs → catalogue FILTRÉ par
  restrictions → design cloud → validation structurelle code → user_gate
critere_succes: le LLM ne voit QUE le catalogue filtré ; volumes dans les bornes doctrine ;
  programme versionné créé après acceptation seulement
rollback: active=false
source: spec Pulse §7 P3
prompt_codex: « Activer P3 ; smoke design fixture → validation structurelle ; consigner. »
observations: bascule locale ultérieure = nouvelle activation (changement de tier à
  consigner au journal)
```

```
id: ACT-PLS-23    nom_fr: P7 monthly_revision en advisory (cloud)
domaine: pulse    classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE pulse_procedures SET active=true WHERE code='monthly_revision';
  + UPDATE job_definitions SET enabled=true WHERE code='pulse_monthly';
prerequis_activation: [ACT-PLS-19, ACT-PLS-22]
protocole_terrain: 1 cycle mensuel : features précalculées → transitions de phase
  proposées → user_gate ; 1 mois
critere_succes: proposition mensuelle cohérente avec le mesocycle ; validation structurelle
  identique à P3
rollback: active=false + job disabled
source: spec Pulse §7 P7
prompt_codex: « Activer P7+job ; smoke run manuel ; consigner. »
observations: —
```

```
id: ACT-PLS-26    nom_fr: P10 missing_sheet en advisory (p10.draft routed)
domaine: pulse    classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE pulse_procedures SET active=true WHERE code='missing_sheet';
prerequis_activation: [ACT-SYS-10]
protocole_terrain: demande d'une fiche absente → draft généré (sources incluses) →
  validation utilisateur → status=validated + embedding (si V6 fait, sinon NULL+backfill)
critere_succes: une fiche draft n'est JAMAIS consommée par P2 avant validation (testé) ;
  sources réelles vérifiables
rollback: active=false
source: spec Pulse §7 P10, §15.8, PATCH_PULSE P-2 (vector 1024, backfill)
prompt_codex: « Activer P10 ; smoke draft fixture → validation ; consigner. »
observations: débloqueur du CONTENU corpus (chantier séparé, hors passes)
```
