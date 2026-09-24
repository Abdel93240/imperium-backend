# SPEC — DAILY MISSION ORCHESTRATOR V1

> **Livrable d'implémentation one-pass.** Prompt d'exécution destiné à un agent d'implémentation sur
> `/opt/imperium-backend`. Il implémente l'orchestration journalière des missions : moteur de
> faisabilité déterministe, ensemble obligatoire, sélection à la complétion, gradation à trois
> niveaux (code → `local_executor` → `high_reasoning`) avec détection déterministe du niveau, classes de préemption,
> et boucle de feedback sur les barèmes. Il CONSOMME le scoring /100 du doc 52 sans le modifier.
> Numérotation : nouveau doc au prochain numéro libre de `docs_master/` + patch de renvoi dans le
> doc 52. Cette spec fait système avec les deux précédentes (Pulse Intelligence Layer, WR
> Continuous Engine) : elle en référence les mécaniques au lieu de les dupliquer.

> **Contrat de démarrage de journée :**
> [`DECISION_demarrage_journee.md`](../gap_analysis_v1/DECISION_demarrage_journee.md) fait foi
> pour le déclencheur, le check-in, les deux axes d'énergie, l'état pré-démarrage et la journée
> opérationnelle. La présente spec ne le contredit pas.

> **Rôles IA :** les rôles ci-dessous se résolvent exclusivement via
> [`30_AI_ROUTING_AND_SCORING_POLICY.md`](../docs_master/30_AI_ROUTING_AND_SCORING_POLICY.md) §3 ;
> cette spec ne nomme aucun modèle concret.

---

## 0. MODE D'EMPLOI POUR L'EXÉCUTEUR (à lire en premier)

**Ton rôle** : implémenter l'intégralité de cette spec en une passe, ordre §15, tests §14 en
verrous. Commit/push via l'orchestrateur.

**Étape 0 obligatoire — AUDIT AVANT TOUTE ÉCRITURE.** Produire `migrations/DAILY_MAPPING.md`
répondant précisément à ces questions (lecture seule) :
1. `backend/app/services/imperium/decision_framework.py` : existe-t-il un filtre de faisabilité
   en amont du tri par score, ou le système trie-t-il purement par `weighted_score` ?
2. La dépendance entre missions est-elle quelque part une **porte topologique** (enfant
   insélectionnable avant complétion du parent) ou uniquement les points du critère D ?
   Identifier où vivent les liens de dépendance (colonne parent, table d'arêtes, ou seulement
   dans le calcul des points).
3. Où vivent les barèmes A-E et les coefficients ×10/8/5/4 : constantes code uniquement, ou déjà
   exposés dans les réglages Imperium ? Identifier le mécanisme de réglage existant s'il y en a
   un (l'utilisateur affirme qu'ils sont modifiables dans les réglages — vérifier, et si vrai,
   documenter le chemin exact ; le §4 s'y adapte).
4. Le chemin nominal de complétion de mission appelle-t-il aujourd'hui un LLM ? Tracer le flux
   réel `mission completed → next mission`.
5. Inventorier : la table missions (colonnes deadline, durée estimée, lieu, fenêtres, statut
   fixe), les sources d'engagements fixes (calendrier, sessions VTC planifiées), la table
   `imperium_mission_scores`, la vue `v_plan_current` si la passe WR est faite (sinon la source
   actuelle du plan), les tables Pulse si la passe Pulse est faite, `ai_slot_transition` si
   existante.
Consigner écarts et choix `créer / étendre / couvert par` dans DAILY_MAPPING.md. **Étendre
plutôt que dupliquer.** STOP et signaler si un point contredit frontalement cette spec.

**Contraintes globales non négociables** (identiques aux deux specs précédentes) : anglais en
base/API/code, français en libellés ; tout derrière feature flags, `real_ai_enabled=False` →
dry-run loggé ; aucune donnée personnelle en dur ; toute proposition passe par validation
utilisateur (no-override) ; migrations réversibles idempotentes ; **le service de scoring doc 52
est codé, testé et fidèle — il est ÉTENDU, jamais réécrit, et la parité de scores doit être
prouvée par tests dorés (§4)**.

**Definition of Done** : migrations + seeds + tests §14 verts + parité de scores prouvée +
dry-run end-to-end (complétion → sélection < 500 ms → override avec raison → item docket) +
DAILY_MAPPING.md + patchs docs.

---

## 1. CONTEXTE ET PRINCIPES

Le scoring déterministe /100 (doc 52 : critères A-E × coefficient de domaine ×10/8/5/4 depuis
`imperium_user_priorities`, breakdown transparent dans `explanation`) est la pièce la mieux
implémentée d'Imperium. Cette spec construit AUTOUR de lui la couche qui manque : l'ordre du
jour n'est pas un problème de score, c'est un problème de faisabilité puis de score.

Principes :
1. **Le score ne départage que des possibles.** Tout ce qui rend une mission impossible
   maintenant (dépendance, fenêtre, durée+trajet, contrainte Pulse) sort de la compétition
   avant que le score parle. Portes, puis score, puis départage — la même structure gravée
   pour le routage /200.
2. **L'urgence est orthogonale à l'importance.** Une deadline aujourd'hui est un mur, pas une
   préférence : l'ensemble obligatoire passe d'abord. À l'intérieur, la hiérarchie de vie de
   l'utilisateur garde son rôle d'arbitre. L'urgence décide qui doit passer aujourd'hui, la
   hiérarchie décide dans quel ordre parmi eux.
3. **Le cas nominal n'invoque aucun LLM.** Sélectionner la suivante = cinq opérations bêtes
   rejouées sur l'état frais à chaque complétion. L'intelligence a déjà été dépensée en amont
   (le plan mensuel par le frontier, les valeurs de l'utilisateur dans les barèmes).
4. **La détection du niveau d'intelligence est elle-même déterministe.** Niveau 1 code (~95 %
   des complétions) ; Niveau 2 `local_executor` sur CONDITIONS testables (ensemble faisable vide,
   conflit d'obligatoires, perturbation exprimée en langage) ; Niveau 3 `high_reasoning` sur classe
   choc (régénération immédiate, mécanique WR §8.1). Le code sait qu'il ne sait pas : c'est
   un test d'infaisabilité, pas un jugement.
5. **Deux régimes de stabilité.** Le plan mensuel est un objet stable amendé par deltas (spec
   WR). La file du jour est invisible (décision UX gravée : une seule mission affichée,
   recalcul à la complétion uniquement) donc librement recomposée. Le seul artefact stable du
   jour est la mission active : jamais préemptée hors classes définies.
6. **Le terrain règle les barèmes, le système fournit le diagnostic.** Chaque override porte sa
   raison obligatoire (mécanique existante) ; le système agrège et propose, l'utilisateur
   ajuste dans les réglages ; chaque changement de barème est versionné (date + raison).
7. **Zéro optimisation visible.** Pas de TSP, pas de justification affichée, pas de bruit de
   replanification. "Ta prochaine mission : X." Point.

---

## 2. ARCHITECTURE

```
mission.completed / clic explicite "Démarrer la journée" / événement déclencheur
        │
        ▼
┌─ NIVEAU 1 — SÉLECTION (code pur, < 500 ms) ────────────────────────────┐
│ 1. Temps restant avant prochain engagement fixe (soustraction)         │
│ 2. FILTRE DE FAISABILITÉ (portes, §5) → ensemble faisable              │
│ 3. ENSEMBLE OBLIGATOIRE (deadline auj./retard, §6) trié par score      │
│ 4. Reste trié par weighted_score (doc 52, inchangé)                    │
│ 5. Départage bande de tête → moindre coût trajet ×1,3 (§7)             │
│ → "Prochaine mission : X" + daily_selection_log                        │
└───────────────┬─────────────────────────────────────────────────────────┘
                │ conditions déterministes (§8.1) :
                │  faisable vide │ obligatoires en conflit │ perturbation texte
                ▼
┌─ NIVEAU 2 — ARBITRAGE (`local_executor`, slots contractualisés) ──────┐
│ daily.disruption_classify : déviation locale / delta plan / choc       │
│ daily.conflict_arbitrate : proposition d'ordre + sacrifice motivé      │
└───────────────┬─────────────────────────────────────────────────────────┘
                │ classe choc (taxonomie WR §13.6)
                ▼
┌─ NIVEAU 3 — RESTRUCTURATION (`high_reasoning`) ───────────────────────┐
│ Régénération complète exceptionnelle, validée par l'utilisateur :      │
│ mécanique WR spec §8.1, réutilisée (plan_versions origin=shock_regen) │
└─────────────────────────────────────────────────────────────────────────┘
Transverse : préemption (§9), feedback barèmes (§10), events E2 (§11).
```

---

## 3. SCHÉMA DE DONNÉES

Conventions identiques aux specs précédentes. DDL normatif ; adapter les noms via
DAILY_MAPPING.md si des tables existantes couvrent déjà.

```sql
-- 3.1 Dépendances explicites (si l'audit §0.2 révèle qu'elles n'existent que dans les points D)
CREATE TABLE mission_dependencies (
  id uuid PRIMARY KEY,
  parent_mission_id uuid NOT NULL,
  child_mission_id uuid NOT NULL,
  hard bool NOT NULL DEFAULT true,      -- true = porte topologique ; false = préférence d'ordre
  UNIQUE (parent_mission_id, child_mission_id)
);
-- Détection de cycles obligatoire à l'écriture (rejet motivé).
-- Le critère D du doc 52 (points "valeur de déblocage") reste INCHANGÉ : il lit ces arêtes
-- pour compter ce qu'une mission débloque. Points = importance ; hard=true = faisabilité.

-- 3.2 Attributs de mission requis par la faisabilité (étendre la table missions existante)
ALTER TABLE <missions> ADD COLUMN IF NOT EXISTS
  duration_estimate_min int,            -- null → paramètre P:default_mission_duration
  location_lat numeric, location_lng numeric, location_label text,
  window_start time, window_end time,   -- fenêtre d'exécution (null = toute la journée)
  window_days text[],                   -- jours valides (null = tous)
  is_fixed_commitment bool NOT NULL DEFAULT false,  -- rendez-vous à heure fixe
  fixed_at timestamptz,                 -- si is_fixed_commitment
  physical_load int, cognitive_load int;-- 1-5, null = 1 ; lus par la porte Pulse

-- 3.3 Journal de sélection (la trace d'audit du Niveau 1)
CREATE TABLE daily_selection_log (
  id uuid PRIMARY KEY,
  trigger text NOT NULL,                -- mission_completed|day_start|disruption_resolved|manual
  trigger_ref uuid,
  at_ts timestamptz NOT NULL,
  remaining_min int NOT NULL,
  next_fixed_ref uuid,
  feasible_set jsonb NOT NULL,          -- [{mission_id, gates_passed}] — refusés AVEC la porte qui a bloqué
  mandatory_set jsonb NOT NULL,
  chosen_mission_id uuid,               -- null si faisable vide → Niveau 2
  tiebreak_applied jsonb,               -- {band_members, travel_costs, winner_reason}
  level int NOT NULL,                   -- 1|2|3
  latency_ms int NOT NULL
);

-- 3.4 Overrides (la matière première du feedback)
CREATE TABLE daily_overrides (
  id uuid PRIMARY KEY,
  selection_log_id uuid NOT NULL REFERENCES daily_selection_log(id),
  proposed_mission_id uuid NOT NULL,
  chosen_mission_id uuid NOT NULL,
  reason text NOT NULL,                 -- OBLIGATOIRE — l'API rejette sans raison (mécanique gravée)
  context jsonb NOT NULL,               -- features figées : heure, jour, lieu, scores des deux,
                                        -- domaines, deltas de barème impliqués
  created_at timestamptz
);

-- 3.5 Conflits et perturbations (Niveau 2)
CREATE TABLE daily_arbitrations (
  id uuid PRIMARY KEY,
  kind text NOT NULL,                   -- empty_feasible|mandatory_conflict|disruption
  input_snapshot jsonb NOT NULL,
  llm_output jsonb,                     -- contrat §8
  model_used text NOT NULL, valid bool NOT NULL,
  proposal_ref uuid,                    -- proposition présentée à l'utilisateur si sacrifice/choix
  resolution text,                      -- accepted|refused|modified|escalated_shock
  created_at timestamptz
);
```

---

## 4. EXTERNALISATION DES BARÈMES — PARITÉ OBLIGATOIRE

Le service doc 52 est codé, testé, fidèle. On ne le réécrit pas : on déplace ses constantes.

1. Créer le jeu de paramètres versionnés `df.*` (table de paramètres partagée des specs
   précédentes, append-only, date + raison obligatoires à chaque version) : barèmes du critère A
   (points par tranche de deadline), B (points par gravité), C (points par CAT A-I), D, E, et la
   table de coefficients par position (×10/8/5/4 — `imperium_user_priorities` reste la source de
   l'ORDRE des domaines ; les VALEURS des coefficients deviennent des paramètres).
2. Initialiser ces paramètres **depuis les constantes actuelles du code**, à l'identique.
3. Le service lit désormais les paramètres (avec cache mémoire invalidé sur nouvelle version).
4. **Verrou de parité** : suite de tests dorés — un jeu de ≥ 40 missions fixtures couvrant toutes
   les tranches de chaque critère ; les scores (intrinsèque, pondéré, breakdown `explanation`)
   doivent être STRICTEMENT identiques avant/après externalisation. Aucune autre étape du §15 ne
   démarre tant que ce verrou n'est pas vert.
5. Si l'audit §0.3 a trouvé un mécanisme de réglages existant : le brancher sur ce store versionné
   (une modification dans les réglages = une nouvelle version de paramètre + event). Sinon,
   exposer les endpoints de réglage (§12) sur ce store.
6. Fraîcheur des scores : le critère A dépend du temps. La sélection (§7) calcule les scores À LA
   VOLÉE via le service (déterministe, < 50 missions, négligeable) ; `imperium_mission_scores`
   reste le registre persisté, rafraîchi par cron matinal et sur changement de barème. Vérifier à
   l'audit le mécanisme de refresh actuel et le conserver s'il fait déjà ça.

---

## 5. MOTEUR DE FAISABILITÉ — LES PORTES (code pur)

Chaque porte est une fonction pure, testée isolément. Le journal (§3.3) enregistre pour chaque
mission rejetée LA porte qui a bloqué — c'est la matière de l'auditabilité.

| porte | règle |
|---|---|
| G1 statut & périmètre | mission active du plan courant (jour ; semaine si pull-forward §7) ; ni faite, ni annulée, ni en attente d'arbitrage |
| G2 dépendance topologique | tous les parents `hard=true` complétés (mission_dependencies) ; détection de cycles à l'écriture des arêtes |
| G3 fenêtre | maintenant + trajet ∈ [window_start, window_end − durée] pour les jours valides ; null = pas de contrainte |
| G4 temps | trajet_estimé + durée ≤ temps_restant avant le prochain engagement fixe (is_fixed_commitment=true trié par fixed_at, + événements calendrier identifiés à l'audit) |
| G5 Pulse | lecture seule : red flag actif `advise_doctor_and_pause_training` → bloque physical_load ≥ P:pulse_block_load (4) ; Pulse absent → porte passante (stub loggé) |

**Trajet** : Google Maps API × `P:gmaps_multiplier` avec plancher codé en dur à 1,3 (la règle
gravée : jamais moins de +30 % sur Paris). Cache par (origine arrondie, destination arrondie,
tranche horaire) TTL 2h pour contenir le coût API. API indisponible → fallback
distance_km / P:fallback_speed_kmh (25) × 1,3, marqué `travel_source=fallback` dans le log.

---

## 6. ENSEMBLE OBLIGATOIRE

`mandatory = missions faisables avec deadline_date ≤ aujourd'hui (retard inclus)`.
Traité AVANT tout le reste. À l'intérieur : tri par `weighted_score` — l'urgence décide qui doit
passer aujourd'hui, la hiérarchie de vie décide dans quel ordre parmi eux.

Deux règles dures :
- Une mission obligatoire **bloquée par une porte** (fenêtre fermée, temps insuffisant) n'est
  JAMAIS silencieusement écartée → condition `mandatory_conflict` → Niveau 2 (§8).
- Somme (trajets + durées) des obligatoires > temps restant du jour → `mandatory_conflict`.

Limite V1 assumée (documentée dans le doc) : pas de look-ahead ("deadline demain mais seul
créneau faisable aujourd'hui"). V1.1 potentielle, hors périmètre §16.

---

## 7. SÉLECTION & DÉPARTAGE (le cœur du Niveau 1)

À chaque déclencheur (complétion, clic explicite de démarrage de journée, résolution de perturbation) :

```
1. remaining_min = prochain engagement fixe − maintenant
2. feasible = portes G1..G5 sur les missions du jour
3. si mandatory non vide → candidats = mandatory (tri weighted_score)
   sinon               → candidats = feasible (tri weighted_score)
4. bande de tête = candidats dont score ≥ (1 − P:top_band_pct/100) × score_max
5. élu = membre de la bande au moindre coût de trajet depuis la position courante
   (le clustering géographique ÉMERGE de cette règle — aucun TSP)
6. afficher "Prochaine mission : {élu}" + écrire daily_selection_log (level=1)
```

**Pull-forward** (`P:pullforward_enabled`, défaut true — décision à valider) : jour épuisé ET
remaining_min ≥ P:pullforward_min_threshold (45) → même pipeline sur les missions restantes de
la SEMAINE du plan courant, `pulled_forward=true` au log. Jour épuisé et rien d'avançable →
"Journée bouclée." (aucune mission inventée).

Latence cible du chemin nominal : **< 500 ms** (test §14). Aucun appel LLM, aucun appel réseau
hors cache trajet.

---

## 8. NIVEAUX 2 ET 3 — CONDITIONS DÉTERMINISTES, SLOTS CONTRACTUALISÉS

### 8.1 Conditions de déclenchement du Niveau 2 (tests, pas des jugements)
- C1 `empty_feasible` : ensemble faisable vide alors que des missions du jour restent.
- C2 `mandatory_conflict` : §6 (obligatoire bloquée, ou somme > temps restant).
- C3 `disruption` : texte utilisateur via `POST /api/daily/disruption`.

### 8.2 Slot `daily.disruption_classify` (local_default, temp 0, GBNF)
Entrée : texte + résumé d'état du jour (missions restantes, obligatoires, prochain fixe —
assembleur whitelisté, ≤ 1,5k tokens). Sortie :
```json
{"class": "local_deviation|plan_delta_needed|shock",
 "affected_mission_refs": ["..."],
 "immediate_action": "defer|cancel|none",
 "rationale_fr": "...", "confidence": "high|medium|low"}
```
Effets (code) :
- `local_deviation` → appliquer defer/cancel avec le texte comme raison (la mécanique raison
  obligatoire est ainsi préservée) → relancer la sélection.
- `plan_delta_needed` → item docket `plan_delta_proposal` (spec WR) + marquage des missions →
  relancer la sélection pour le reste du jour.
- `shock` → le CODE vérifie l'appartenance à la taxonomie shock seedée (spec WR §13.6). Match →
  proposition one-tap "Régénérer le plan maintenant ?" → acceptation → mécanique WR §8.1 telle
  quelle. Pas de match → rétrogradé `plan_delta_needed` + note. Un LLM ne déclenche JAMAIS seul
  une régénération frontier.
- `confidence=low` → routage doc 30 (contre-lecture) selon ai_slot_transition.

### 8.3 Slot `daily.conflict_arbitrate` (local_default)
Entrée : l'ensemble en conflit + contraintes + contexte. Sortie :
```json
{"ordering": ["mission_id..."],
 "sacrificed": [{"mission_ref": "...", "mitigation_fr": "reporter à demain 9h, prévenir M. X"}],
 "rationale_fr": "...", "confidence": "high|medium|low"}
```
Règle absolue : **sacrifier une deadline est TOUJOURS une proposition à l'utilisateur** (item
`daily.mission_sacrifice_proposed`, boutons accepter/refuser/choisir moi-même), jamais un acte
silencieux. Refus → l'utilisateur ordonne manuellement, son choix + raison = daily_overrides.

Les deux slots entrent dans `ai_slot_transition` (audit_sample_pct=100 au départ), leurs
désaccords et les overrides alimentent `v_ai_training_pairs`.

### 8.4 Niveau 3
Aucune logique nouvelle ici : le chemin choc RÉUTILISE la mécanique de la spec WR §8.1
(plan_versions origin=shock_regen, proposition, validation, supersede). Cette spec n'implémente
que le pont (§8.2).

---

## 9. PRÉEMPTION — LA MISSION ACTIVE EST SACRÉE

Les recompositions de file ne touchent JAMAIS la mission active (la file est invisible, elle
peut churner librement ; la mission active, non). Classes de préemption (table seedée,
éditable) autorisées à INTERROMPRE avec proposition :

| classe | comportement |
|---|---|
| red_flag (Pulse/docket severity=red) | notification immédiate + proposition d'interruption ; l'utilisateur décide |
| shock (taxonomie WR) | proposition de régénération (§8.2) |
| event_types listés | ex. évènements de type ghusl.required (vérifier les types réels au doc 77 à l'audit) → proposition de replan du créneau |

Tout le reste attend la complétion. Une préemption acceptée clôt proprement la mission active
en `interrupted` avec raison auto-remplie (classe + ref), et relance la sélection.

---

## 10. BOUCLE DE FEEDBACK — LE TERRAIN RÈGLE, LE SYSTÈME DIAGNOSTIQUE

1. **Capture** : chaque override (§3.4) fige ses features de contexte. La raison est obligatoire
   (l'API rejette sans elle) — mécanique gravée, réutilisée telle quelle.
2. **Agrégation** (job hebdo, branché sur l'usine WR — W5 crée l'item) : regrouper les overrides
   par motif déterministe (domaine_proposé, domaine_choisi, tranche horaire) ; motif ≥
   P:override_pattern_min (3) sur 28 j → item docket `ordering_override_pattern` :
   `{pattern, count, exemples (raisons verbatim), suggested_target}` où suggested_target est
   calculé quand c'est mécanique (ex. critère C d'une CAT systématiquement dépassée, coefficient
   d'un domaine) et `discussion` sinon. AUCUN ajustement automatique.
3. **Réglage** : l'utilisateur modifie dans les réglages → nouvelle version de paramètre `df.*`
   (date + raison) → event → refresh des scores → les tests dorés de parité ne s'appliquent
   qu'aux MIGRATIONS de code, pas aux réglages volontaires (documenté).
4. **W3** (spec WR) voit chaque override comme clôture d'épisode → extraction de patterns
   ("finance avant business le matin") → mémoire à cycle de vie. Rien à coder ici : vérifier
   seulement que les events §11 déclenchent bien W3.

---

## 11. EVENTS (table canonique post-E3, politique E2)

| type | émis par | payload minimal |
|---|---|---|
| daily.next_proposed | sélection | {selection_log_id, mission_id, level, pulled_forward} |
| daily.override_recorded | API override | {override_id, proposed, chosen} |
| daily.arbitration_required | conditions C1/C2 | {arbitration_id, kind} |
| daily.disruption_classified | slot 8.2 | {arbitration_id, class, confidence} |
| daily.mission_sacrifice_proposed / .decided | slot 8.3 / user | {arbitration_id, sacrificed_refs, decision} |
| daily.preemption_proposed / .decided | §9 | {class, ref, decision} |
| daily.pullforward_applied | §7 | {mission_id} |
| df.parameter_updated | réglages | {param_code, old_version, new_version} |

correlation_id = dossier du jour (ou de l'arbitrage) ; causation_id = event déclencheur
(mission.completed → daily.next_proposed) ; profondeur = parent + 1. Payloads = refs.

---

## 12. API & WORKFLOWS

**Endpoints (`/api/daily/`)** : `POST complete/{mission_id}` → {next_mission | arbitration_pending
| day_done} (LE chemin nominal) ; `POST override` {selection_log_id, chosen_mission_id, reason}
(400 sans raison) ; `POST disruption` {text} ; `GET current` ; `GET queue` (**admin/debug
uniquement** — la file reste invisible dans l'UI produit, décision UX gravée) ;
`GET selection-log?date=` ; `GET/PUT settings/scoring` (barèmes via store versionné, protégé) ;
`POST arbitrations/{id}/decision`.

**Workflows/crons** : `daily_scores_refresh` (06:30, critère A ; ce cron ne démarre jamais une
journée) ; `daily_day_start` (webhook du clic explicite "Démarrer la journée" : check-in de
ressenti seul, sélection initiale déterministe, puis repli local seulement en conflit) ;
`override_aggregation` (hebdo, → docket via W5) ; `gmaps_cache_gc` (quotidien). La journée est
bornée par démarrage→clôture et peut traverser minuit, jamais par date civile.

---

## 13. SEEDS V1

Paramètres (origin='initial', défauts à valider) : `df.*` initialisés depuis les constantes du
code (§4) ; gmaps_multiplier=1.3 (plancher dur 1.3) ; fallback_speed_kmh=25 ;
default_mission_duration=30 ; top_band_pct=15 ; pullforward_enabled=true ;
pullforward_min_threshold=45 ; pulse_block_load=4 ; override_pattern_min=3 ;
selection_latency_target_ms=500. Classes de préemption : red_flag, shock, event_types=[]
(à remplir à l'audit depuis doc 77). ai_slot_transition : daily.disruption_classify,
daily.conflict_arbitrate (local_default, audit 100 %).

---

## 14. TESTS REQUIS (verrous)

1. **Parité dorée §4** — verrou bloquant : scores identiques avant/après externalisation.
2. Portes G1-G5 : cas passant/bloquant chacune, porte bloquante correcte au log ; G2 : enfant
   insélectionnable avant parent, cycle rejeté à l'écriture.
3. Obligatoire : deadline aujourd'hui bat un score pondéré supérieur ; hiérarchie ordonne
   l'intérieur ; obligatoire bloquée → mandatory_conflict, jamais d'écartement silencieux.
4. Départage : bande de tête + moindre trajet ; cas de clustering émergent (3 missions proches
   moyennes vs 1 lointaine haute — dans la bande) ; hors bande → le score gagne.
5. Pull-forward : activé/désactivé, seuil, flag au log ; "journée bouclée" sans invention.
6. Démarrage : seul le clic explicite démarre la journée ; check-in de ressenti seul ; état
   pré-démarrage "Journée non démarrée" et programme masqué ; deux axes d'énergie, avec capacité
   retenue au plus bas et écart journalisé. Niveaux : C1/C2/C3 purement déterministes ; **spy : zéro appel LLM sur le chemin nominal** ;
   latence < 500 ms sur fixture 50 missions (trajets depuis cache).
7. Slot 8.2 : contrat + retry + effets par classe ; shock sans match taxonomie → rétrogradé ;
   régénération JAMAIS déclenchée sans acceptation utilisateur.
8. Slot 8.3 : sacrifice toujours en proposition ; refus → override manuel capturé.
9. Préemption : recomposition ne touche jamais la mission active ; classes red/shock proposent ;
   interruption acceptée → statut interrupted + raison auto.
10. Override sans raison → 400 ; features de contexte figées ; agrégation → item docket au seuil.
11. Trajet : multiplicateur plancher 1.3 appliqué même si paramètre < 1.3 ; cache ; fallback marqué.
12. Réglage barème : nouvelle version + raison obligatoire + event + refresh.
13. E2 : chaîne mission.completed → daily.next_proposed avec correlation/causation/profondeur.
14. Dry-run end-to-end complet avec real_ai_enabled=False.

---

## 15. ORDRE D'EXÉCUTION ONE-PASS

0. Audit §0 + DAILY_MAPPING.md. STOP si contradiction majeure.
1. Migrations (§3) + backfill des dépendances existantes si l'audit en trouve.
2. Externalisation des barèmes + **verrou de parité** (§4). Rien d'autre avant vert.
3. Moteur de faisabilité (portes, trajet+cache+fallback) + ensemble obligatoire + sélection +
   journal + pull-forward.
4. Conditions C1-C3 + slots Niveau 2 (contrats, effets, pont choc §8.4) + préemption.
5. Boucle de feedback : overrides, agrégation hebdo → docket, réglages versionnés.
6. API + crons + events.
7. Tests §14, dry-run, docs : patch doc 52 (renvoi "l'ordre journalier est défini par le doc N"),
   doc 77 (types §11), DAILY_MAPPING final.

## 16. HORS PÉRIMÈTRE EXPLICITE

- Optimisation globale de tournée (TSP) — la bande + moindre trajet suffit et reste explicable.
- Look-ahead de deadlines multi-jours (V1.1 potentielle, documentée §6).
- Toute UI (l'app consomme l'API ; la file reste invisible dans le produit).
- LoRA et bascules de tiers (les slots et vues dataset sont livrés).
- Écriture calendrier / intégrations externes nouvelles.
- Modification de la sémantique des critères A-E du doc 52 (consommés, jamais redéfinis).
- Le routeur /200 (routed≈cloud_forced en attendant, wrapper commun).
