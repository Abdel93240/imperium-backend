# AUDIT — ARCHITECTURE DIGEST (LECTURE SEULE)

> **Prompt destiné à Claude Code (Fable 5)** sur Tower, accès complet à `/opt/imperium-backend`,
> `/opt/orchestrator`, `/opt/apps/` et à toute la doc. Mission : produire LE document de
> compression de l'écosystème — `ARCHITECTURE_DIGEST.md` — qui servira d'entrée unique à une
> session d'arbitrage d'architecture avec un modèle frontier au contexte limité.
> **Conçu pour tourner APRÈS les passes** (socle, Vault, Pulse, WR, Daily, Vector). S'il est
> lancé plus tôt : l'exécuter quand même, en déclarant précisément la couverture (§1).
> Cet audit ne modifie rien : il lit, il exécute des commandes d'inspection non destructives
> (pytest, alembic current, greps, SELECT), et il livre UN document.

---

## 0. LE LECTEUR — règle de rédaction cardinale

Ton lecteur n'est pas un humain qui feuillette : c'est un modèle en session de conception,
au budget de contexte compté. Chaque ligne doit porter. Interdits : paraphrase longue des
docs, généralités, recommandations noyées dans la description, listes non sourcées.
Obligations : **chaque affirmation porte sa référence** (doc N §x, chemin de fichier, table,
migration, test) ou est marquée `HYPOTHÈSE` ; ce qui mérite d'être creusé pointe vers sa
source exacte au lieu d'être développé. **Budget dur : 600-1000 lignes, plafond absolu
1200.** Si tu dépasses, tronque par priorité (sévérité × portée), jamais par hasard —
et dis ce que tu as tronqué.

## 1. ÉTAT DES PASSES (en tête du digest, avant tout)

Tableau : pour chacune (Socle, Vault, Pulse, WR, Daily, Vector, + Path/Feed AI si entamées) —
mergée ? tests verts (chiffres réels : lancer la suite) ? flags activés (`real_ai_enabled`,
`embeddings_enabled`, `runner_enabled`, modes) ? jobs enregistrés vs activés
(`job_definitions`) ? Écarts consignés dans son MAPPING.md (les MAPPING sont TA source
première : c'est le journal des déviations spec↔réel — les exploiter systématiquement).
Puis : couverture de CE digest (docs lus / total, exclusions motivées).

## 2. CARTE DU SYSTÈME (~150 lignes max)

- Topologie physique : VPS (backend, Postgres, runner) ↔ Tower (services GPU) ↔ tablette,
  avec les protocoles (Tailscale, HTTP interne, sync). Sourcé sur l'état réel, pas les docs.
- Les 5 façades + le système : pour chacune, ce qui EXISTE (écrans, API consommées) vs
  spécifié vs absent.
- La toolbox : état par outil du doc 78 (codé/branché/consommateurs réels constatés dans le
  code — imports effectifs, pas intentions).
- Le cerveau : où vivent décision, mémoire, plan, docket — une ligne chacun + réf.

## 3. LES FLUX MAJEURS (diagrammes ASCII compacts, ~120 lignes)

Cinq chaînes, telles qu'elles tournent RÉELLEMENT (vérifier chaque maillon dans le code) :
(a) event → NOTIFY → usine → docket → WR → écriture E2 + mémoire ; (b) plan : régénération/
deltas/choc → v_plan_current → sélection Daily → complétion → events ; (c) Pulse : signaux →
sentinelle → interprète → procédure → proposition → feedback ; (d) Vector : sonnerie → halo
+ log → Tower entraînement → bundle ; (e) apprentissage transverse : refus/overrides/audits
→ v_ai_training_pairs → (futur LoRA). Pour chaque maillon : ✔ codé+testé / ◐ codé non
branché / ✗ absent, avec réf.

## 4. INVARIANTS GRAVÉS ET LEUR ENFORCEMENT (~100 lignes)

Tableau : invariant (no-override, append-only, privacy tiers very_high, zéro LLM chemin
critique Vector, un seul runner, E2 rempli, données brutes device jamais en prompt, raison
obligatoire, plancher ×1,3…) → où il est ÉCRIT (doc/spec) → où il est FORCÉ (code/contrainte
SQL/test précis) → verdict : tenu / écrit-non-forcé / violé (réf).

## 5. INCOHÉRENCES RÉSIDUELLES (style DV-x, numérotées AD-1…)

docs↔code↔specs, avec sévérité (MAJEUR/MINEUR), effort (S/M/L), et « depuis quand » si
datable. Inclure : les TODO/stubs laissés par les passes, les compat 30 j expirées, les
docs non patchés promis par les specs.

## 6. SURFACES DE RISQUE (~60 lignes)

Points de défaillance uniques, couplages non contractualisés (imports directs
inter-domaines), données sensibles et leurs chemins de sortie, dette assumée (avec la
décision qui l'a créée, sourcée). Pas de catastrophisme : chaque risque = fait + réf +
condition de matérialisation.

## 7. QUESTIONS UTILISATEUR (numérotées, en un bloc)

Tout ce qui exige un arbitrage humain. Une ligne de contexte + la question fermée. Jamais
de question dont la réponse est dans un doc (la chercher d'abord).

## 8. MÉTRIQUES DE SANTÉ (chiffres bruts, ~30 lignes)

pytest (passed/failed/skipped par domaine), migrations (head vs appliquées), nombre de
tables vs catalogue 78, events émis/consommés sur 7 j (SELECT), notifications envoyées,
job_runs par statut sur 7 j, taille des MAPPING (nombre de déviations par passe).

## 9. ANNEXE — INDEX DE FORAGE

Le plan de la session d'arbitrage : pour chaque sujet susceptible d'être creusé (routage,
mémoire, plan, chaque domaine, chaque flux), LA liste minimale des références à fournir
(3-6 items : doc précis, fichier, section de spec). C'est ce qui permet au lecteur de
demander exactement les bons documents au lieu de tout charger.

---

## LIVRABLE ET INTERDITS

- UN fichier : `audits/AAAA-MM-JJ_ARCHITECTURE_DIGEST.md` + mise à jour `audits/LATEST.txt`
  + une ligne à l'index selon la convention.
- Aucune valeur personnelle (santé, finances, lieux) dans le digest : des références et des
  agrégats, jamais des données.
- Aucune recommandation hors §5/§6 (le digest cartographie ; l'arbitrage décide).
- Aucune modification d'aucun fichier existant. `git status` propre hors livrable.
- Commandes autorisées : lecture, greps, `pytest`, `alembic current/history`, SELECT
  read-only. Rien d'autre.
