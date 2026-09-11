# ÉTAPE 1 — EXÉCUTION : de l'état actuel à la boucle vitale vivante (V1 ON)

> Document d'exécution. Objectif : partir de l'état du digest (rien de commité, rien de
> codé au-delà des fondations) et arriver à **V1 ON** — la première semaine où Imperium te
> rend réellement service. Durée estimée : 10-14 jours calendaires, dont l'essentiel est
> du temps machine et des fenêtres d'observation. **Zéro GPU requis** (les ventilateurs
> J+2 servent la phase parallèle §H, pas le chemin critique).
> Chaque phase a sa porte GO : on ne passe pas la porte tant qu'elle n'est pas verte.

---

## PHASE 0 — Rapatriement VPS → Tower (préalable, une soirée)

1. Postgres 16 + pgvector installés sur Tower (ou docker-compose repris du VPS).
2. `pg_dump` complet depuis le VPS → restore sur Tower.
3. `alembic current` en local = head `20260710_0037` (ou plus récent).
4. Backend lancé sur Tower, `DATABASE_URL` local, secrets migrés.
5. Smoke : suite pytest contre la vraie base + un appel API depuis la tablette via Tailscale.
6. VPS gelé en lecture — il devient cible de sauvegarde jusqu'à fin de contrat. Export n8n
   archivé (confirmation « jamais exécuté » avant coupure future).
+ Onduleur sur la Tour (recommandé, hors porte).

**GO Phase 0 : `alembic current` OK en local + un appel API réussi depuis la tablette.**

## PHASE A — Le commit (AD-10 meurt ici, 20 minutes)

Placer dans le repo (arborescence suggérée) :
- `docs_master/76_ACTIVATION_ROADMAP.md` + `docs_master/activation_cards/` (livrés par la passe roadmap)
- `specs/` : TOOLBOX_SOCLE_SPEC_V1.md, VAULT_DETERMINISTIC_SPEC_V1.md, PULSE_INTELLIGENCE_LAYER_SPEC_V1.md, WR_CONTINUOUS_ENGINE_SPEC_V1.md, DAILY_ORCHESTRATOR_SPEC_V1.md, VTC_ASSISTANT_SPEC_V1.md
- `prompts/` : TOOLBOX_AUDIT_PROMPT_V1.md, ARCHITECTURE_DIGEST_PROMPT_V1.md, ACTIVATION_ROADMAP_PROMPT_V1.md
- `gap_analysis_v1/toolbox/` (les 6 livrables d'audit, déjà en untracked) + `audits/` (les 2 digests)

```bash
cd /opt/imperium-backend
git add docs_master/ gap_analysis_v1/ audits/ specs/ prompts/
git commit -m "Audits toolbox + digests + 7 specs + roadmap activation (doc 76) — décisions Q1-Q23 encodées"
git push
```

**GO Phase A : `git status` propre ; les décisions existent enfin ailleurs que dans une conversation.**

## PHASE B — Lot Codex #1 : les 35 tests (Q14) — AVANT le merge du socle

Prompt à coller à Codex :

```
LOT BORNÉ — TRI DES 35 TESTS DOC-ANCRÉS (aucun code applicatif touché)
Contexte : suite à 907 passed / 35 failed. Les 35 échecs sont des tests ancrés sur la
LETTRE d'anciennes versions de docs (digest 2026-07-11 AD-1) : test_repo_invariants.py
(16), test_imperium_screen_architecture_docs.py (5), frontend_* (8), home_bootstrap (1),
daily_plan_contracts (1), docs_lot_* (2), asset_registry/app_manifest (2).
Politique gravée (Q14) : les tests verrouillent le CODE ; la conformité des DOCS
appartient aux audits.
Pour chacun des 35 : (a) s'il protège un contrat de CODE réel → le réécrire ancré sur le
code (route, schéma, constante), plus jamais sur une phrase de doc ; (b) s'il ne vérifie
que la lettre d'un doc → le SUPPRIMER, une ligne de justification par suppression dans
tests/TESTS_DOCS_POLICY.md (créer, avec la politique en en-tête).
Interdits : toucher un test vert ; toucher app/ ; modifier un doc.
DoD : suite 100 % verte (0 failed), TESTS_DOCS_POLICY.md créé, un commit par fichier de
tests traité.
```

**GO Phase B : `pytest` = 0 failed. Le verrou « tests verts » redevient un signal.**

## PHASE C — Lot Codex #2 : corrections doc 76 + amendements R1 (parallèle de B et D)

Prompt à coller à Codex :

```
LOT BORNÉ — DOCS UNIQUEMENT (doc 76 + 2 patches d'étape 0)
1. docs_master/76_ACTIVATION_ROADMAP.md :
   - Insérer ACT-SYS-19 « Backup nocturne restic (job system.backup_nightly) », classe dE,
     échelon 2, vague V1, obs « socle §12 ».
   - Composition V1 corrigée (Q17 tranchée) : runner+heartbeat, canal notifications,
     pression, ACT-VLT-04 upcoming CRUD (remonte de V3), puis V1-bis à J+3 : fenêtres de
     prière + backup. Retirer la mention « mini-lot Path » (Q19 SANS OBJET : c'est le
     socle §8) ; le crochet de V2 devient « [socle §6] », pas « passe events courte ».
   - CF-4/CF-6 : annoter « déjà conformes dans les specs Socle §2 / Vault §4
     (enabled=false par défaut) ».
   - Colonne obs : marquer RÉSOLUES avec leur réponse : Q1 (GitHub vérité/clone Tower),
     Q2 (privacy_tier travel), Q3+Q18 (Telegram produit d'abord), Q4 (0-100),
     Q5 (spec WR normative, doc 75 amendé au socle), Q6 (prières G4 via socle §8),
     Q8 (plan_versions), Q9 (mini-passe Vault), Q15 (drop à la passe du domaine + dump),
     Q16 (passes avancent, seule la chaîne mémoire attend le smoke P40), Q20 (chevauchement
     OUI : max 2 vagues, jamais 2× échelon ≥3, chrono de validation comme juge),
     Q21 (14 j ET ≥20 sorties auditées), Q22 (76 confirmé), Q23 (validé).
   - V36 : retirer « sortie n8n » (la coupure suit le merge du socle, ponts portés §2) ;
     garder drops legacy + routeur. Ajouter ligne « Feed AI / Knowledge Inbox : V37+,
     passe dédiée post-Vector (doc 70) ».
2. gap_analysis_v1/toolbox/patches/PATCH_PULSE.md : ajouter « R1 : TOUT seed (signaux,
   sentinelle, procédures, coups, rouges) naît active=false ; l'activation est un UPDATE
   journalisé par vague (doc 76) ». Corriger aussi vector(4096)→vector(1024) si absent (DV-2).
3. patches/PATCH_DAILY.md : ajouter « flag daily_selection_enabled=False : tant que OFF,
   POST /api/daily/complete conserve le comportement actuel (CF-5) ».
Interdits : tout fichier hors ces trois. DoD : diff lisible, un commit.
```

**GO Phase C : doc 76 reflète les décisions ; plus aucun « BLOQUANT » fantôme.**

## PHASE D — Passe SOCLE (Fable, la grosse dépense justifiée)

- Coller `specs/TOOLBOX_SOCLE_SPEC_V1.md` à Claude Code (Fable 5) sur Tower.
- Rappels : étape 0 = STOP si base non rapatriée (Phase 0) ; DoD = tests §13 verts +
  runner en dry-run + ponts n8n portés + unités systemd embeddings livrées (smoke différé
  J+2) + patches docs + catalogue promu doc 78 + SOCLE_MAPPING.md.
- Après merge : **contre-audit Codex gratuit** (méthode gravée) — « lis SOCLE_MAPPING.md
  + le diff de la passe, vérifie chaque test-verrou du §13, liste tout écart spec↔code ».
- Optionnel si la passe n'a pas démarré : extraire en lots Codex les §11 (patches docs),
  §9 (lecteurs legacy) — économie sans risque.

**GO Phase D : suite verte (grâce à B, un vrai signal) + contre-audit Codex sans finding MAJEUR.**

## PHASE E — Mini-passe VAULT (Codex, méthode A — l'économie sûre)

- Coller `specs/VAULT_DETERMINISTIC_SPEC_V1.md` à Codex.
- Point d'attention unique : si le doc 11 n'a pas d'exemples chiffrés, Codex construit
  les 5 exemples dorés et **s'arrête pour te les faire valider** avant merge (spec §7.1).
  C'est ton seul moment bloquant de la phase.
- DoD : tests §7 verts + drop `vault_transactions` (dump archivé) + jobs seedés éteints.

**GO Phase E : monotonies vertes + tes 5 exemples dorés signés.**

## PHASE F — ACTIVATION V1 (les fiches — le premier sang)

Préalable : phases A-E vertes. Démarre ton **chrono de validation** (note chaque jour le
temps passé à valider — c'est la métrique juge de Q20). Chaque bascule = une ligne au
journal du doc 76 + un commit.

**J1 — ACT-SYS-06 · Runner + heartbeat** (échelon 2)
- Bascule : `runner_enabled=True` puis `UPDATE job_definitions SET enabled=true WHERE code='system.events_heartbeat';`
- Terrain (2-3 j) : `job_runs` se remplit, statuts completed, zéro doublon (advisory lock),
  le heartbeat compte les events par type.
- Critère : 3 jours de runs sans failed. Rollback : les deux flags à false.

**J1 — ACT-SYS-07 · Notifications Telegram** (échelon 3)
- Bascule : `notifications_enabled=True` + canal `telegram_prod` enabled (bot produit,
  jamais celui du build — le test du socle §13.3 l'a déjà prouvé).
- Terrain (3-7 j) : un `notify()` manuel de chaque sévérité ; red → tous canaux ;
  dedup 24 h vérifié.
- Critère : réception < 1 min, zéro doublon sur 3 jours. Rollback : flag false (la table
  continue d'enregistrer — canal inapp).

**J2 — ACT-VLT-04 · Upcoming expenses (saisie réelle)** (échelon 2)
- Bascule : aucune — c'est de l'API. L'activation, c'est TOI : saisir tes vraies
  échéances (loyer, assurances, échéances véhicule…), 15 minutes.
- Critère : la liste est complète à tes yeux. Rollback : sans objet (données).

**J2 — ACT-VLT-05 · Pression financière** (échelon 1-2)
- Bascule : `UPDATE job_definitions SET enabled=true WHERE code='vault.pressure_refresh';`
- Terrain (3 j) : un snapshot quotidien ; `GET /pressure/explain` cohérent avec tes
  chiffres ; ajoute une dépense test → le score bouge dans le BON sens (monotonie en réel).
- Critère : 3 snapshots justes + une jauge à laquelle tu fais confiance. Rollback :
  job disabled (les snapshots restent, append-only).

**J+3 (V1-bis) — ACT-PTH-02 · Fenêtres de prière** (échelon 1)
- Bascule : `UPDATE job_definitions SET enabled=true WHERE code='path.mawaqit_refresh';`
- Terrain (3 j) : `prayer_windows(date)` vs les horaires réels de ta mosquée de référence.
- Critère : ±2 min sur 3 jours consécutifs. Rollback : job disabled.

**J+3 (V1-bis) — ACT-SYS-19 · Backup nocturne** (échelon 2)
- Préalable physique : le disque USB dédié est branché.
- Bascule : `UPDATE job_definitions SET enabled=true WHERE code='system.backup_nightly';`
- Terrain (3 j) : un snapshot restic par nuit sur les DEUX cibles, tailles cohérentes.
- Critère : 3 snapshots + **un restore d'essai réussi** (dump → base jetable → SELECT
  témoin, 10 min). Rollback : job disabled.

**Le premier sang est versé quand** : une notification Telegram réelle t'arrive, déclenchée
par une donnée réelle (échéance J-7 ou red test), pendant que la jauge de pression tourne
sur ton vrai ledger et que le journal d'events a son premier lecteur vivant. C'est la fin
de l'étape 1.

## PHASE H — Parallèle matériel (J+2, hors chemin critique)

Ventilateurs → V100 + P40 → checklist smoke embeddings du socle (dims 1024, latence,
paires témoins) → `embeddings_enabled=True` → D5 levé. Puis serving 32B + smoke GBNF.
Rien dans V1 n'attend ça ; tout V6+ en dépend.

## SORTIE DE L'ÉTAPE 1 → ÉTAPE 2

Livrables vivants : boucle vitale ON (6 features), journal doc 76 avec ses premières
lignes de bascule, chrono de validation initialisé, suite de tests = signal fiable.
L'étape 2 est déjà écrite : V2 (hygiène du journal d'events — déjà codée au socle §6, il
ne reste que les bascules) en chevauchement avec le lancement de la passe Pulse (Fable).
