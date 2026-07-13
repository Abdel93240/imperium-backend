# VAGUE 29 — Daily branchements (G5, overrides, agrégation, prières)

**Composition** : ACT-DLY-05, ACT-DLY-07, ACT-DLY-08, ACT-DLY-10. Durée : 3-7 j.

```
id: ACT-DLY-05   nom_fr: Porte G5 Pulse branchée (via vue contractuelle)
domaine: daily    classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: flag daily_g5_enabled=true (G5 lit v_pulse_active_blocks au lieu du stub)
prerequis_activation: [ACT-DLY-04, ACT-PLS-09]
protocole_terrain: red flag advise_doctor_and_pause_training actif → missions
  physical_load ≥ 4 rejetées AVEC la porte au log ; Pulse indisponible → porte passante
  loggée ; 3-7 j
critere_succes: blocage exact, jamais silencieux (visible au selection_log)
rollback: flag=false (stub passant)
source: spec Daily §5 G5 ; PATCH_DAILY D-7 / FINDINGS C-4 (vue dédiée, pas de lecture des
  tables médicales)
prompt_codex: « Activer G5 ; smoke red flag fixture → rejet loggé ; consigner. »
observations: première frontière santé→planning EN ACTES
```

```
id: ACT-DLY-07   nom_fr: Overrides capturés (raison obligatoire, features figées)
domaine: daily    classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: flag daily_override_enabled=true (POST /api/daily/override ; 400 sans raison)
prerequis_activation: [ACT-DLY-04]
protocole_terrain: chaque fois que l'utilisateur prend une autre mission que la proposée →
  override avec raison + contexte figé ; 7 j
critere_succes: zéro override sans raison ; contexte suffisant pour rejouer le choix
rollback: flag=false (la sélection reste, l'override n'est plus capturé — déconseillé :
  c'est la matière première du feedback)
source: spec Daily §3.4, §10.1
prompt_codex: « Activer override ; smoke POST sans raison → 400, avec → capturé ;
  consigner. »
observations: W3 (V25) voit chaque override comme clôture d'épisode — rien à activer ici
```

```
id: ACT-DLY-08   nom_fr: Agrégation hebdo des overrides → docket (diagnostic de barèmes)
domaine: daily    classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code='override_aggregation';
prerequis_activation: [ACT-DLY-07, ACT-WR-05]
protocole_terrain: motif ≥3 sur 28 j (domaine proposé/choisi/tranche horaire) → item
  ordering_override_pattern avec exemples verbatim + suggested_target ; 2 semaines
critere_succes: AUCUN ajustement automatique — le réglage reste un acte utilisateur
  (ACT-DLY-02)
rollback: job disabled
source: spec Daily §10.2 ; PATCH_DAILY D-4
prompt_codex: « Activer l'agrégation ; smoke 3 overrides même motif → item ; consigner. »
observations: —
```

```
id: ACT-DLY-10   nom_fr: Prières en engagements fixes G4 (fenêtres mobiles) — Q6
domaine: daily    classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: flag daily_prayer_commitments_enabled=true (G4 consomme les fenêtres
  ACT-PTH-02 EN LECTURE)
prerequis_activation: [ACT-DLY-04, ACT-PTH-02 ; Q6 TRANCHÉE]
protocole_terrain: le temps restant (G4) s'arrête à la prochaine fenêtre de prière comme
  à tout engagement fixe ; 3-7 j de journées réelles
critere_succes: aucune mission proposée qui chevauche une fenêtre ; awareness zones dans
  le planning, vérité des heures dans Path (frontière doc 41 §7-bis tenue)
rollback: flag=false
source: PATCH_DAILY D-8, Q6, doc 41 §7-bis, doc 52 §8.2 CAT 8
prompt_codex: « (Q6=oui) Activer ; smoke fenêtre fixture → G4 la respecte ; consigner. »
observations: ne rien construire de religieux DANS Daily (lecture seule)
```
