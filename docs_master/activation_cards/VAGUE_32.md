# VAGUE 32 — Vector shadow (pipeline complet, halo blanc)

**Composition** : ACT-VEC-05, ACT-VEC-06, ACT-VEC-07. Le SEUL domaine dont la spec grave
déjà ses états d'activation (off/shadow/advisory + rollout §10.7) — la roadmap les suit
à la lettre. Durée : **≥14 j gravés** (prolongés à 4 semaines si verdict ambigu ou
période atypique).

```
id: ACT-VEC-05   nom_fr: Mode shadow (sonnerie → capture → OCR → score → log, halo BLANC)
domaine: vector   classe: ia_shadow   echelon_audace: 3   statut: NOT_CODED
bascule_exacte: vtc_assistant_enabled=true + vtc_assistant_mode='shadow'
prerequis_activation: [ACT-VEC-03 ; templates construits sur captures réelles fournies
  (§0.4 — jamais inventer une disposition d'écran) ; empreinte sonnerie calibrée]
protocole_terrain: sessions réelles : une ligne vtc_offers PAR sonnerie (y compris
  abstentions), latences par étage, verdict calculé, halo BLANC affiché ; ≥14 j
critere_succes: p95 sonnerie→verdict ≤900 ms sur l'appareil réel ; ≥98 % champs requis
  OCR par plateforme ; micro jamais persisté/transmis (gravé, testé §9.2) ; zéro appel
  réseau dans le chemin critique (spy)
rollback: vtc_assistant_mode='off' (une variable)
source: spec Vector §0 (flags), §3, §10.7 (rollout gravé)
prompt_codex: « Passer en shadow ; smoke sonnerie simulée → log complet halo blanc ;
  consigner date de début de fenêtre. »
observations: ZÉRO LLM dans ce domaine (gravé §0) ; consultatif strict — jamais d'action
  sur l'app VTC, pas même en option
```

```
id: ACT-VEC-06   nom_fr: Fantôme Google/TomTom (professeur asynchrone, hors chemin critique)
domaine: vector   classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code='vtc_ghost_scoring';
  (plafond P:ghost_daily_cap=400, échantillonnage près du seuil si dépassé)
prerequis_activation: [ACT-VEC-05]
protocole_terrain: chaque offre loggée → appel Directions horodaté → vtc_ghost_scores ;
  recyclage en multiplicateurs ; affinage upgrade-only (ne rétrograde JAMAIS un halo) ;
  14 j (avec la fenêtre shadow)
critere_succes: would_have_arrived_in_window correct ; budget API tenu ; recyclage visible
  dans les multiplicateurs
rollback: job disabled
source: spec Vector §4.2, §3.7
prompt_codex: « Activer le fantôme ; smoke offre fixture → ghost score ; consigner. »
observations: coût API — surveiller le plafond quotidien dès le jour 1
```

```
id: ACT-VEC-07   nom_fr: Rapport du test fantôme (seuils gravés AVANT le test)
domaine: vector   classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code='vtc_ghost_report';
prerequis_activation: [ACT-VEC-06 ; défauts des règles de décision VALIDÉS avant
  lancement, puis intangibles pendant le test]
protocole_terrain: fin de fenêtre : taux de bascule de décision (hors bande 10 %), MAE/biais
  des deux estimateurs vs RÉALISÉ, disponibilité fenêtre 2,5 s → item docket avec
  recommandation chiffrée
critere_succes: rapport produit ; la bascule d'architecture (local seul / hybride / Google
  en course) = DÉCISION UTILISATEUR consignée ici
rollback: s.o. (rapport)
source: spec Vector §6 (annexe A — protocole gravé)
prompt_codex: « Activer le rapport ; smoke sur fenêtre fixture ; consigner le verdict. »
observations: « le juge est le réel, pas l'un des deux estimateurs »
```
