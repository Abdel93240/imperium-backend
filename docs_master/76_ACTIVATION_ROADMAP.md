# 76 — ACTIVATION ROADMAP (journal canonique, document VIVANT)

Créé : 2026-07-11 (Claude Code / Fable 5, Tower). Statut : **canonique pour l'activation** —
premier document lu par tout audit futur (R8). Mis à jour à chaque merge de passe puis à
chaque bascule. Numéro 76 = prochain libre (78 reste réservé au catalogue toolbox, Q13/Q22).

Doctrine (gravée par l'utilisateur, résumé) : R1 coder ≠ brancher (les passes livrent
ÉTEINT, l'activation est un acte séparé, journalisé, réversible) ; R2 l'unité = la feature
OBSERVABLE ; R3 une fiche par feature (`activation_cards/VAGUE_<n>.md`) ; R4 lots de 1-5,
un domaine par vague, jamais deux effets confondables dans la même fenêtre ; R5 fenêtres
det-lecture 2-3 j / det-écriture-notifiant 3-7 j / IA dry-run→shadow→advisory sur accord
mesuré ; R6 échelle d'audace 1 lecture < 2 écriture < 3 notifiant < 4 proposant <
5 apprenant, aucun saut ; R7 le terrain juge, un rollback est une donnée ; R9 V1 = la
boucle vitale.

## Sources et limites

- Specs lues : Pulse / WR / Daily / Vector (`/tmp/incoming_docs/*.md`). Les « specs »
  Socle et Vault n'existent pas comme fichiers : leurs features sont sourcées depuis
  `gap_analysis_v1/toolbox/EXECUTION_ORDER_PROPOSAL.md` (socle 0a-0g), TOOLBOX_FINDINGS
  (T1-T6), `gap_analysis_v1/GAP_vault.md`, docs 11/42/41, doc 77, N8N_INVENTORY.
- Code réel vérifié ce jour : flags `qwen_enabled=False`, `qwen_dry_run=True`,
  `n8n_dry_run=True` (`backend/app/core/config.py:42-53`) ; `real_ai_enabled=False` /
  `embeddings_enabled=False` en dur (`decision_framework.py:262-263`, `memories.py:56-58`) ;
  commit mémoire bloqué D5 (`memories.py:31`) ; notifications = stub 1 ligne ;
  `job_definitions`/runner : inexistants. AUCUNE passe mergée (digest 2026-07-11 §1).
- Conséquence : la majorité des statuts = NOT_CODED ; leur `bascule_exacte` est la bascule
  CIBLE prévue par la spec, exécutable après le merge de la passe correspondante. Ce
  journal est exécutable dès maintenant (R statuts) et vivra avec les merges.
- Compte : **117 features** — 8 ON (existant en service, vague V0), 3 OFF (codées,
  éteintes), 106 NOT_CODED. Par domaine : system 18, events 4, vault 10, path 3,
  pulse 28, wr 24, daily 14, vector 16.

## Tableau canonique (une ligne par feature)

Colonnes : classe (dL=det_lecture, dE=det_ecriture, No=notifiant, Pr=proposant,
iaD/iaS/iaA=ia_dryrun/shadow/advisory, Ap=apprenant), éch(elon R6), statut, vague,
dates (activé le / rollback le), obs. Fiches complètes : `activation_cards/VAGUE_<n>.md`.

| id | nom | classe | éch | statut | vague | dates | obs |
|---|---|---|---|---|---|---|---|
| ACT-SYS-01 | Émission d'events (19 types, 8 services) | dE | 2 | ON | V0 | — | — |
| ACT-SYS-02 | Idempotence des mutations | dE | 2 | ON | V0 | — | — |
| ACT-SYS-03 | Scoring mission /100 (doc 52) | dL | 1 | ON | V0 | — | — |
| ACT-SYS-04 | Lifecycle missions (une seule active) | dE | 2 | ON | V0 | — | — |
| ACT-SYS-05 | Calendrier soft-delete + daily plans CRUD | dE | 2 | ON | V0 | — | — |
| ACT-VLT-01 | Ledger Vault canonique (cents, reversals, wallet) | dE | 2 | ON | V0 | — | — |
| ACT-PTH-01 | Habits/check-ins Path (raison obligatoire) | dE | 2 | ON | V0 | — | — |
| ACT-WR-01 | WR conversationnel (plomberie, dry-run) | dE | 2 | ON | V0 | — | commit mémoire bloqué D5 |
| ACT-SYS-06 | Runner de jobs : premier job actif | dE | 2 | NOT_CODED | V1 | — | socle 0a (T2) |
| ACT-VLT-05 | Pression financière 0-100 + explication | dL | 1 | NOT_CODED | V1 | — | Q4, Q17 |
| ACT-SYS-07 | Canal de notifications produit | No | 3 | NOT_CODED | V1 | — | Q3/Q18 |
| ACT-PTH-02 | Fenêtres de prière (MAWAQIT + fallback) | dL | 1 | NOT_CODED | V1 | — | Q19 |
| ACT-EVT-01 | Renommage domaines génériques + E1 aborted | dE | 2 | NOT_CODED | V2 | — | AD-6/AD-5 |
| ACT-EVT-02 | Chaînage temps réel V1 (corr/caus/depth) | dE | 2 | NOT_CODED | V2 | — | AD-7 |
| ACT-EVT-03 | Types V1 manquants du catalogue 77 | dE | 2 | NOT_CODED | V2 | — | — |
| ACT-VLT-02 | Deux livres business/personnel | dE | 2 | NOT_CODED | V3 | — | — |
| ACT-VLT-03 | Wallet snapshots manuels cash/bank/crypto | dE | 2 | NOT_CODED | V3 | — | — |
| ACT-VLT-04 | Dépenses récurrentes + upcoming (CRUD) | dE | 2 | NOT_CODED | V3 | — | — |
| ACT-VLT-07 | Corrections manuelles pression | dE | 2 | NOT_CODED | V3 | — | — |
| ACT-VLT-06 | Objectifs journaliers min/comfort/optimal | dL | 1 | NOT_CODED | V4 | — | — |
| ACT-VLT-09 | Profit hebdo business (job lundi 00:30) | dE | 2 | NOT_CODED | V4 | — | Q9 |
| ACT-VLT-10 | Base sadaqa exposée à Path | dL | 1 | NOT_CODED | V4 | — | — |
| ACT-VLT-08 | Alertes échéances (7 j / overdue) | No | 3 | NOT_CODED | V4 | — | — |
| ACT-PTH-03 | Rappels Path (path.reminder) | No | 3 | NOT_CODED | V5 | — | Q3 |
| ACT-SYS-11 | LLM local réel (qwen_enabled, dry_run=false) | dE | 2 | OFF | V6 | — | DV-6 : 7B→32B avant |
| ACT-SYS-12 | Modèle 32B servi (V100, phase 2) | dL | 1 | NOT_CODED | V6 | — | Q16 GPU |
| ACT-SYS-13 | Serving embeddings 1024 (P40) | dL | 1 | NOT_CODED | V6 | — | T4 |
| ACT-SYS-14 | embeddings_enabled=true (recherche vect.) | dL | 1 | OFF | V6 | — | — |
| ACT-PLS-01 | Pipeline montre (features 06:45) | dE | 2 | NOT_CODED | V7 | — | — |
| ACT-PLS-02 | Signaux device : sleep ×3 + cardio ×4 | dL | 1 | NOT_CODED | V7 | — | — |
| ACT-PLS-08 | Board Pulse (GET /api/pulse/board) | dL | 1 | NOT_CODED | V7 | — | — |
| ACT-PLS-03 | Signaux intake : hydration ×2 + nutrition ×5 | dL | 1 | NOT_CODED | V8 | — | — |
| ACT-PLS-04 | Signaux training ×7 | dL | 1 | NOT_CODED | V8 | — | — |
| ACT-PLS-05 | Signaux subjectifs ×4 + POST reports | dE | 2 | NOT_CODED | V8 | — | — |
| ACT-PLS-07 | Signaux contexte ×2 + méta ×1 | dL | 1 | NOT_CODED | V8 | — | — |
| ACT-PLS-06 | Signaux médicaux ×3 | dL | 1 | NOT_CODED | V9 | — | — |
| ACT-PLS-09 | Règles rouges RF1-RF5 + blocage P1/P3 | No | 3 | NOT_CODED | V9 | — | jamais désactivables par LLM |
| ACT-PLS-15 | Chaîne IA Pulse en dry-run (bout en bout) | iaD | 2 | NOT_CODED | V10 | — | — |
| ACT-PLS-10 | Sentinelle S4/S5 programmées + garde S7 | dE | 2 | NOT_CODED | V10 | — | — |
| ACT-PLS-13 | Sentinelle S3 signalement utilisateur | dE | 2 | NOT_CODED | V10 | — | — |
| ACT-PLS-11 | Sentinelle S1 multi-drapeaux | dE | 2 | NOT_CODED | V11 | — | — |
| ACT-PLS-12 | Sentinelle S2 sévérité | dE | 2 | NOT_CODED | V11 | — | — |
| ACT-PLS-14 | Sentinelle S6 pré-séance | dE | 2 | NOT_CODED | V11 | — | — |
| ACT-PLS-27 | Audit hebdo agreement + métriques Pulse | dE | 2 | NOT_CODED | V11 | — | — |
| ACT-SYS-09 | Privacy gate central | dE | 2 | NOT_CODED | V12 | — | T5 ; bloque very_high |
| ACT-SYS-10 | Sortie cloud réelle autorisée (wrapper tiers) | No | 3 | NOT_CODED | V12 | — | après SYS-09 uniquement |
| ACT-SYS-17 | Observabilité IA ai_call_logs | dE | 2 | NOT_CODED | V12 | — | DV-8 pricing |
| ACT-PLS-16 | Interprète réel local (shadow de fait) | iaS | 3 | NOT_CODED | V13 | — | Q21 durée |
| ACT-PLS-17 | P1 adapt_training_session advisory | Pr | 4 | NOT_CODED | V14 | — | — |
| ACT-PLS-20 | P4 injury_or_pain advisory | Pr | 4 | NOT_CODED | V14 | — | — |
| ACT-PLS-18 | P2 diet_change advisory (+synthesis routed) | Pr | 4 | NOT_CODED | V15 | — | — |
| ACT-PLS-21 | P5 medical_document_ingest advisory | Pr | 4 | NOT_CODED | V15 | — | second_read cloud |
| ACT-PLS-22 | P6 weekly_reconciliation + solveur repas | Pr | 4 | NOT_CODED | V15 | — | — |
| ACT-PLS-19 | P3 new_training_program (cloud) | Pr | 4 | NOT_CODED | V16 | — | — |
| ACT-PLS-23 | P7 monthly_revision (cloud) | Pr | 4 | NOT_CODED | V16 | — | — |
| ACT-PLS-26 | P10 missing_sheet (routed) | Pr | 4 | NOT_CODED | V16 | — | — |
| ACT-PLS-24 | P8 scientific_review (cloud, semestriel) | Pr | 4 | NOT_CODED | V17 | — | gated corpus validé |
| ACT-PLS-25 | P9 exploration_pass (cloud, mensuel) | Pr | 4 | NOT_CODED | V17 | — | — |
| ACT-PLS-28 | 1re décroissance d'audit Pulse (par slot) | Ap | 5 | NOT_CODED | V17 | — | décision user |
| ACT-WR-02 | Usine : session_end + filet 23:30 + curseurs | dE | 2 | NOT_CODED | V18 | — | 1er consumer events |
| ACT-WR-03 | W1 rollups par domaine | dE | 2 | NOT_CODED | V18 | — | AD-2 avant |
| ACT-WR-04 | W4 anomalies (signaux ecosystem) | dE | 2 | NOT_CODED | V18 | — | — |
| ACT-WR-05 | W5 assembleur de docket | dE | 2 | NOT_CODED | V18 | — | — |
| ACT-WR-06 | Walker P4 (modes full/light, budget) | dL | 1 | NOT_CODED | V18 | — | — |
| ACT-WR-07 | Notification rouge en semaine | No | 3 | NOT_CODED | V19 | — | — |
| ACT-WR-08 | Filet review_due hebdo | dE | 2 | NOT_CODED | V19 | — | — |
| ACT-WR-09 | Digest P1 (40k, caps, drill log) | dE | 2 | NOT_CODED | V19 | — | — |
| ACT-WR-23 | Audit hebdo agreement + métriques WR | dE | 2 | NOT_CODED | V19 | — | — |
| ACT-WR-10 | Chaîne WR dry-run bout en bout | iaD | 2 | NOT_CODED | V20 | — | — |
| ACT-WR-18 | Plan initial + v_plan_current | dE | 2 | NOT_CODED | V20 | — | Q8 |
| ACT-WR-11 | W2 découverte causale réelle (32B) | Pr | 4 | NOT_CODED | V21 | — | rien n'entre en E2 avant P4/P5 |
| ACT-WR-12 | P1 passe d'hypothèses (cloud) | Pr | 4 | NOT_CODED | V22 | — | — |
| ACT-WR-15 | P5 écriture + exit_audit (Opus, gravé) | Pr | 4 | NOT_CODED | V22 | — | — |
| ACT-WR-13 | P3 enquêtes dirigées (cloud) | Pr | 4 | NOT_CODED | V23 | — | — |
| ACT-WR-14 | P3 synthèse conjonctive (cloud) | Pr | 4 | NOT_CODED | V23 | — | — |
| ACT-WR-19 | Deltas de plan hebdo wr.plan_delta | Pr | 4 | NOT_CODED | V23 | — | — |
| ACT-WR-20 | Régénération choc (taxonomie shock) | Pr | 4 | NOT_CODED | V24 | — | — |
| ACT-WR-21 | Régénération mensuelle | Pr | 4 | NOT_CODED | V24 | — | Q8 |
| ACT-SYS-15 | Commit mémoire WR débloqué (D5) | dE | 2 | OFF | V25 | — | exige SYS-13/14 |
| ACT-WR-16 | W3 extraction + confrontation réelles | Ap | 5 | NOT_CODED | V25 | — | écrit la mémoire |
| ACT-WR-17 | Moteur d'exposition 6.3 (confiance) | Ap | 5 | NOT_CODED | V25 | — | Q5 BLOQUANT |
| ACT-WR-22 | Classes d'auto-acceptation (1re classe) | Ap | 5 | NOT_CODED | V26 | — | décision user |
| ACT-WR-24 | 1re décroissance d'audit WR | Ap | 5 | NOT_CODED | V26 | — | décision user |
| ACT-DLY-01 | Barèmes df.* externalisés (parité prouvée) | dL | 1 | NOT_CODED | V27 | — | verrou parité |
| ACT-DLY-02 | Réglage des barèmes versionné | dE | 2 | NOT_CODED | V27 | — | — |
| ACT-DLY-03 | Refresh scores 06:30 + day_start | dE | 2 | NOT_CODED | V27 | — | — |
| ACT-SYS-08 | toolbox.travel v0 (Google, plancher 1,3) | dL | 1 | NOT_CODED | V28 | — | DBL-1, Q2 |
| ACT-DLY-04 | Sélection Niveau 1 (portes G1-G5, <500 ms) | dL | 1 | NOT_CODED | V28 | — | — |
| ACT-DLY-06 | Pull-forward | dL | 1 | NOT_CODED | V28 | — | — |
| ACT-DLY-05 | Porte G5 Pulse branchée (vue dédiée) | dL | 1 | NOT_CODED | V29 | — | C-4 |
| ACT-DLY-07 | Overrides + raison obligatoire | dE | 2 | NOT_CODED | V29 | — | — |
| ACT-DLY-08 | Agrégation overrides → docket | dE | 2 | NOT_CODED | V29 | — | — |
| ACT-DLY-10 | Prières en engagements fixes G4 | dL | 1 | NOT_CODED | V29 | — | Q6 BLOQUANT |
| ACT-DLY-11 | Slots Niveau 2 en dry-run | iaD | 2 | NOT_CODED | V30 | — | — |
| ACT-DLY-12 | daily.disruption_classify réel | Pr | 4 | NOT_CODED | V30 | — | — |
| ACT-DLY-13 | daily.conflict_arbitrate réel | Pr | 4 | NOT_CODED | V30 | — | sacrifice = proposition |
| ACT-DLY-09 | Préemption (red_flag/shock/event_types) | Pr | 4 | NOT_CODED | V30 | — | DV-11 |
| ACT-DLY-14 | 1re décroissance d'audit Daily | Ap | 5 | NOT_CODED | V30 | — | — |
| ACT-VEC-01 | Matrice H3 + caches statiques | dE | 2 | NOT_CODED | V31 | — | Q1+V-2 BLOQUANTS |
| ACT-VEC-02 | Builders caches contextuels + seuils | dE | 2 | NOT_CODED | V31 | — | — |
| ACT-VEC-03 | Sync tablette↔Tower | dE | 2 | NOT_CODED | V31 | — | — |
| ACT-VEC-04 | Test NotificationListener (passif 2 sem.) | dL | 1 | NOT_CODED | V31 | — | — |
| ACT-VEC-05 | Mode shadow (pipeline complet, halo blanc) | iaS | 3 | NOT_CODED | V32 | — | ≥2 sem. gravées |
| ACT-VEC-06 | Fantôme Google/TomTom | dE | 2 | NOT_CODED | V32 | — | plafond quotidien |
| ACT-VEC-07 | Rapport du test fantôme | dE | 2 | NOT_CODED | V32 | — | seuils gravés §6 |
| ACT-VEC-08 | Mode advisory (halo coloré) | iaA | 4 | NOT_CODED | V33 | — | décision user |
| ACT-VEC-09 | Entraînement nocturne + verrou backtest | Ap | 5 | NOT_CODED | V34 | — | — |
| ACT-VEC-10 | Modèle de zones (zone_eph + zone_wait) | Ap | 5 | NOT_CODED | V34 | — | — |
| ACT-VEC-11 | Bouton « Où je vais » | Pr | 4 | NOT_CODED | V34 | — | — |
| ACT-VEC-12 | Capture surge manuelle + pipeline | dE | 2 | NOT_CODED | V35 | — | inerte >5 km/h |
| ACT-VEC-13 | Sollicitations de capture (cause/heartbeat) | No | 3 | NOT_CODED | V35 | — | — |
| ACT-VEC-14 | Prédicteur cause→surge | Ap | 5 | NOT_CODED | V35 | — | — |
| ACT-VEC-15 | Contre-lecture OCR P40 nocturne | dE | 2 | NOT_CODED | V35 | — | — |
| ACT-VEC-16 | Dérive → docket | dE | 2 | NOT_CODED | V35 | — | — |
| ACT-SYS-16 | Sortie n8n (portage ponts WR + décomm.) | dE | 2 | NOT_CODED | V36 | — | N8N_INVENTORY §C |
| ACT-EVT-04 | Débranchement legacy (4 objets) | dE | 2 | NOT_CODED | V36 | — | Q15 |
| ACT-SYS-18 | Routeur /200 branché | dE | 2 | NOT_CODED | V36 | — | T3, différable |

## Définition des vagues

Règles : lots ≤5, un domaine par vague (R4) ; durée = fenêtre R5 de la classe la plus
audacieuse du lot ; les vagues de DOMAINES DIFFÉRENTS peuvent se chevaucher si leurs effets
ne sont pas confondables (Q20 à confirmer) ; chaque vague exige le merge (éteint) de la
passe qui la code — indiqué entre crochets.

| vague | contenu | prérequis | durée obs. |
|---|---|---|---|
| V0 | état initial : 8 features déjà ON | — (constat, HYPOTHÈSE prod) | — |
| V1 | boucle vitale : runner+1er job, pression Vault, canal notif, fenêtres prière | [socle 0a/0b + mini-Vault pression + mini-lot Path] Q3, Q17-Q19 | 7 j |
| V2 | hygiène du journal : renommage+E1, chaînage V1, types manquants | [passe events courte] AVANT tout consumer pérenne (AD-6) | 3-7 j |
| V3 | Vault écritures : livres, wallet, upcoming, corrections | [mini-passe Vault] V1 | 3-7 j |
| V4 | Vault boucle : objectifs, profit hebdo, sadaqa→Path, alertes | V3, Q9 | 7 j |
| V5 | Path notifiant : rappels | V1 (canal) | 3-7 j |
| V6 | infra IA : 32B servi, serving embeddings, flags embeddings+qwen réels | GPU phase 2 (Q16) ; DV-6 corrigé ; [wrapper GBNF passe Pulse] | 2-3 j smoke |
| V7 | Pulse socle 1 : montre, signaux device, board | [passe Pulse] | 2-3 j |
| V8 | Pulse socle 2 : intake, training, subjectifs, contexte/méta | V7 | 2-3 j |
| V9 | Pulse médical : signaux médicaux + règles rouges | V7 ; canal notif (V1) | 7 j |
| V10 | sentinelle A : chaîne dry-run, S4/S5/S7, S3 | V8 | 3-7 j |
| V11 | sentinelle B : S1, S2, S6 + audit hebdo | V10 | 3-7 j |
| V12 | garde-fous cloud : privacy gate, 1re sortie cloud, ai_call_logs | [T5 codé] ; AVANT tout advisory à slot cloud | 3-7 j |
| V13 | interprète réel local (shadow de fait : nomme, rien ne s'exécute) | V6, V11, V12 (audit cloud) ; Q21 | 14 j (prop.) |
| V14 | Pulse advisory entraînement : P1, P4 | V13 accord ≥ cible | 7-14 j |
| V15 | Pulse advisory nutrition/médical : P2, P5, P6+solveur | V14 | 7-14 j |
| V16 | Pulse advisory cloud : P3, P7, P10 | V15 | 7-14 j |
| V17 | Pulse revues : P8 (post-corpus validé), P9, 1re décroissance | V16 ; accord ≥92 % 3 sem. | mensuel |
| V18 | usine WR : déclencheur+curseurs, W1, W4, W5, walker | [passe WR] ; V2 (noms) ; AD-2 fini | 3-7 j |
| V19 | WR filets : rouge, review_due, digest, audit hebdo | V18 ; canal (V1) | 3-7 j |
| V20 | WR dry-run bout en bout + plan initial/v_plan_current | V18 ; Q8 | 3-7 j |
| V21 | W2 réel (sondes+verdicts 32B) — seul, gros échelon | V13 (32B éprouvé), V20 | 7-14 j |
| V22 | WR rituel cloud : hypothesis_pass + exit_audit | V12, V21 | 2 WR |
| V23 | WR résiduel : investigation, conjunctive, plan_delta | V22 | 2 WR |
| V24 | plan régénérations : choc + mensuelle | V20 | 1 mois |
| V25 | mémoire vivante : commit D5, W3 réel, exposition 6.3 | V6 (embeddings), Q5 BLOQUANT | 14 j |
| V26 | WR autonomie graduée : auto-acceptation, décroissance | V25 ; accords mesurés | mensuel |
| V27 | Daily fondations : parité barèmes, réglage, refresh | [passe Daily] verrou parité vert | 2-3 j |
| V28 | sélection du jour : travel v0, sélection N1, pull-forward | V27 ; Q2 (interface travel) | 2-3 j |
| V29 | Daily branchements : G5, overrides, agrégation, prières G4 | V28 ; V9 (G5) ; V18 (docket) ; Q6 | 3-7 j |
| V30 | Daily N2 : dry-run, disruption, arbitrate, préemption, décroissance | V29, V13 | 7-14 j |
| V31 | Vector Tower : matrice, builders, sync, test notification | [passe Vector] Q1+V-2 résolus | 3-7 j |
| V32 | Vector shadow : mode shadow, fantôme, rapport test | V31 | ≥14 j gravés |
| V33 | Vector advisory : halo coloré | V32 + décision user sur rapport | 14 j |
| V34 | Vector apprentissage : entraînement verrouillé, zones, « Où je vais » | V33 | 1 mois |
| V35 | Vector surge + audits : captures, sollicitations, prédicteur, OCR, dérive | V34 ; V18 (docket) | 1 mois |
| V36 | nettoyages : sortie n8n, drops legacy (Q15), routeur /200 (différable) | V18+ (ponts WR portés) | 3-7 j |

Horizon cumulé indicatif (chevauchements inter-domaines autorisés, Q20) : V1-V5 ≈ 4-5
semaines (zéro GPU) ; V6-V17 ≈ 2-3 mois (Pulse) ; V18-V26 ≈ 2-3 mois (WR, partiellement
parallèle) ; V27-V30 ≈ 1 mois ; V31-V35 ≈ 2-3 mois (bloqué Q1/V-2). Sans chevauchement :
doubler.

## Conflits détectés (specs qui violent R1 : activation implicite au merge)

| # | conflit | source | patch une ligne proposé |
|---|---|---|---|
| CF-1 | 32 signaux seedés avec `active` DEFAULT true → pipelines calculent dès le merge | spec Pulse §3.1 + §15.1 | seed `active=false` partout ; activation = UPDATE journalisé par vague V7-V9 |
| CF-2 | règles sentinelle S1-S7 seedées actives → passes 07:30/18:30 tirent au premier démarrage | spec Pulse §3.2 (DEFAULT true) + §15.2 | seed `active=false` ; V10-V11 |
| CF-3 | procédures P1-P10, coups légaux et règles rouges seedés actifs | spec Pulse §3.3/§3.6/§3.5 + §15.3-5 | seed `active=false` (rouges activées en bloc V9, en premier) |
| CF-4 | ~25 jobs/crons des 4 specs sans flag d'extinction (features 06:45, factory session_end, scores 06:30, builders 5 min…) → tournent dès que le runner existe | Pulse §14, WR §12, Daily §12, Vector §4.1 | `job_definitions.enabled=false` par défaut au seed du runner ; activation par job |
| CF-5 | POST /api/daily/complete devient LE chemin nominal au merge (remplace le flux de complétion actuel) | spec Daily §12 | flag `daily_selection_enabled=False` → l'endpoint répond comme aujourd'hui tant que OFF |
| CF-6 | profit hebdo « lundi 00:30 » codé comme cron | doc 42 §11 / GAP_vault | job runner `enabled=false` (couvert par CF-4, rappelé pour la mini-passe Vault) |
| CF-7 | externalisation des barèmes = bascule de source de vérité au merge | spec Daily §4 | ACCEPTÉ sous verrou de parité (effet prouvé nul) — consigné, pas de patch |
| CF-8 | red flags évalués « à chaque écriture lab » dès le merge | spec Pulse §3.5 | couvert par CF-3 (seed inactif) ; à activer AVANT tout signal médical (V9) |

Contre-exemple conforme, à imiter : spec Vector §0 (`vtc_assistant_enabled` +
`vtc_assistant_mode ∈ {off, shadow, advisory}`, rollout gravé §10.7) — le seul système
livré avec ses états d'activation explicites.

## Questions utilisateur (numérotation continue après Q16 du digest)

- **Q17 — Composition V1 (pression).** La pression exacte exige livres+upcoming (V3).
  Accepter une pression V1 dégradée (wallet manuel + liste upcoming minimale saisie à la
  main) pour tenir la semaine 1, ou remplacer par le board Pulse dans V1 et décaler la
  pression en V4 ?
- **Q18 — Canal V1.** En attendant Q3 : bot Telegram PRODUIT dédié (distinct du bot de
  build de l'orchestrateur) acceptable comme canal V1 ? Sinon quel canal ?
- **Q19 — Mini-lot Path avant les 4 passes.** Les fenêtres de prière (F1-16, lecture
  seule, déterministe-EXACT) sont hors des 4 specs. Autoriser un mini-lot de code dédié
  (tables doc 41 §20 + MAWAQIT cache + fallback) pour que V1 les contienne ?
- **Q20 — Chevauchement de vagues.** Deux vagues de domaines différents aux effets non
  confondables peuvent-elles courir en parallèle (calendrier ÷2), ou séquentiel strict ?
- **Q21 — Durée du shadow interprète Pulse.** Vector grave 2 semaines de shadow ; rien
  n'est gravé pour l'interprète Pulse. Proposé : 14 j (V13). Confirmer ?
- **Q22 — Numéro de ce journal.** 76 choisi (prochain libre ; 78 réservé au catalogue,
  Q13). Confirmer ou déplacer.
- **Q23 — Patch R1 global.** Valider le principe « tout seed actif par défaut passe à
  `active=false` / tout job à `enabled=false` » (CF-1→CF-6) comme amendement d'étape 0
  des 4 passes (à ajouter aux PATCH_* existants) ?

## Journal des bascules (append-only — rempli à chaque activation/rollback)

| date | ACT-id | action (ON/OFF/ROLLBACK) | par | observation |
|---|---|---|---|---|
| — | — | — | — | — |
