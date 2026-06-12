# Rapport d'application des patches de relecture doc

Date : 2026-06-12. Appliqué par Fable Code dans l'ordre prescrit (1→9).
Aucun fichier hors `docs_master/` modifié. Aucun code/test/migration touché
(consigne explicite du prompt : doc Markdown uniquement). Le dossier
`_patches_to_apply/` est conservé.

---

## 1. PATCH_30-A_financial_expert.md — DÉJÀ APPLIQUÉ (rien à faire)

Constat : le doc 30 contenait déjà, mot pour mot, l'état cible du patch
(vraisemblablement via le commit `68f3ef0` "docs: rewrite doc 30") :
- §3.8 = "GPT-5.5 — domain specialist (health + finance + fresh data)" avec le
  bloc finance complet (brain ≠ Vault, hallucination resistance).
- §7.5 "Finance / Vault reasoning" présent.
- §7.6 "Morning AI advice cards" présent (avec la hard rule Path `base_advice`).
- Renumérotation finale conforme : 7.7 Vector ride scoring, 7.8 WR re-planning,
  7.9 Deterministic backend. Aucun doublon, aucun trou.

Aucune modification effectuée pour ce patch.

## 2. PATCH_30-B_critical_tier.md — DÉJÀ APPLIQUÉ (rien à faire)

Constat : le doc 30 §5.6 contenait déjà la table 0–179 inchangée + la ligne
180–200 → "Critical mechanic (see below)" + la sous-section "Critical tier
(180–200) — two-step mechanic" complète (Step 1 GPT-5.5 re-score, Step 2 Opus
orchestration, anti-loop breaker, note backlog), conforme au patch mot pour mot.

Aucune modification effectuée pour ce patch.

## 3. PATCH_30-C_emergency_mode.md — APPLIQUÉ

- Inséré `### 5.7 Emergency Mode (user-triggered)` dans le doc 30 (rationale,
  Trigger, ce que le mode change, ce qu'il ne change pas, Exit, cross-refs
  §5.2 / §5.6 / §1.6 — texte du patch).
- Renuméroté : ancien 5.7 "Automatic escalation" → 5.8 ; ancien 5.8 "Automatic
  downgrade" → 5.9.
- Cross-ref ajoutée dans le préambule du §7 (le patch demande "cross-reference
  from both") : note indiquant qu'Emergency Mode n'est PAS une règle statique.
- **Correction induite (hors patch, conséquence de la renumérotation)** :
  doc 32 L1345 référençait "doc 30 §5.6–§5.7" (thresholds + escalation) ;
  l'escalation étant devenue §5.8, la référence a été mise à jour en
  "§5.6–§5.8". Signalé ici par transparence.

## 4. PATCH_MECA-1_model_hierarchy.md — APPLIQUÉ

Toutes les lignes indiquées appliquées :
- **Doc 16** : L47 (Qwen 32B/V100), L49 (drop Haiku), L91 (drop Haiku), L170
  (qwen3:32b Q4_K_M), L323 (entrée "haiku-4.5" supprimée de available_models),
  L365 (WR analysis → "WR re-planning → Fable 5", résolu), L408 et L417
  (fallback Haiku 4.5 → Sonnet 4.6).
- **Doc 31** : L257, L283 (QWEN_MODEL=qwen3:32b), L919, L995, L1022 (ligne Haiku
  supprimée), L1024 (Opus 4.8), L1042, L1177 (qwen3:32b), table L1625-1628
  remplacée par la grille canonique doc 30 §5.6 + mention "doc 30 is the source
  of truth; see §5.6 for the critical-tier mechanic", L1843, L1898.
- **Doc 34** : L86 → "Fable 5 is reserved for the WR re-planning…" (résolu) ;
  la ligne GPT-5.5 suivante inchangée.
- **Doc 35** : L56, L73 (qwen3:32b), L93 (Sonnet/Opus/Fable…), bloc seuils
  L120-130 remplacé par la grille 0–99/100–139/140–179/180–200.
- **Doc 03** : Qwen 32B, ligne Haiku supprimée, Opus 4.8 "premium strategic",
  ligne ⭐ Fable 5 ajoutée (option "if the list is meant to be complete" — la
  liste se présente comme les décisions modèles V1 complètes, donc ajoutée).
- **Doc 44** : L163 et L703 → Qwen 32B.

**Lignes supplémentaires corrigées (non listées dans le patch mais couvertes par
les remplacements canoniques + la consigne de grep final "zéro référence
legacy")** :
- Doc 16 L345 `"selected_model": "opus-4.7"` → `opus-4.8`.
- Doc 16 L494 `ai_task.selected_model (opus-4.7)` → `opus-4.8`.
- Doc 31 L1178 `selected_model VARCHAR(64) (e.g. opus-4.7)` → `opus-4.8`.

Grep de vérification final sur les 6 docs (`haiku`, `opus 4.7`, `qwen.*7b`,
`qwen 2.5`, insensible à la casse) : **0 occurrence restante**.

## 5. PATCH_11-A_financial_pressure.md — APPLIQUÉ

- §1 : nouvelle section "Recurring-Expenses List (User Truth)" (entrées : label,
  recurrence, amount, category avec "Other", `payment_day_of_month`), insérée
  après "Weekly Philosophy".
- §2 : `optional_required_expenses` → `conditional_required_expenses` partout
  (Step 2 formule avec le commentaire `# (was optional_required_expenses)`, et
  le bloc "Where:") + définition ("conditional on timing, never on importance").
- §3 : nouvelle section "Two Distinct Uses of Expenses: Smoothed Objective vs
  Real Pressure".
- §4 : Step 1 réécrit — `available_liquidity` = CB wallet + cash wallet,
  paragraphe d'exclusion crypto (réserve mobilisable, signal de tension) +
  parenthèse "mobilize crypto = action délibérée".
- §5 : nouvelle section "Classification Scoring — ONLY for Expenses NOT in the
  List" avec la grille et la hard rule (catégories vitales jamais déférables par
  l'IA seule) + couplage doc 30.
- §6 : Core Inputs — "Optional inputs" → "Conditional required inputs" avec note
  de sourcing (liste récurrente + `payment_day_of_month`) ; liste récurrente
  ajoutée comme source d'entrée de premier rang ; liquidité = CB + cash, crypto
  exclue, "all three wallets being Vault dashboard wallets".
- §7 : 3 puces ajoutées aux Open Decisions (smoothing window /
  payment_day_of_month, poids du scoring hors-liste, "mobilize crypto").

## 6. PATCH_33-A_vector_logic.md — APPLIQUÉ

- **Doc 33 A1** (§3) : ajout des entrées **weather** (Open-Meteo + alertes
  Météo-France, signal de demande) et **surge / majoration** (renvoi doc 57
  §16-17, pas de duplication).
- **Doc 33 A2** (§4) : sortie à 5 niveaux (`strong_accept…reject`) remplacée par
  le verdict binaire CatBoost (halo VERT/ROUGE + son, halo BLANC = assistant
  actif), signal-only sans texte temps réel, économie existante conservée, note
  "zone recommendation (§5) inchangée".
- **Doc 33 A3** (§6) : split clarifié en tête de section (CatBoost seul score
  les courses ; pas d'explication verbale temps réel ; commentaire NL uniquement
  a posteriori dans le rapport Vector de la WR ; micro-rôles Qwen conservés hors
  chemin critique). Liste de tâches Qwen existante conservée, intitulée "off the
  critical driving path".
- **Doc 33 A4** (§8) : signaux d'apprentissage remplacés — revenu horaire
  objectif à la minute, pas d'apprentissage sur accepté/refusé, refus
  enregistrés comme données comportementales (indicateur charge mentale/burnout
  en WR), boucle de raffinement WR supervisée.
- **Doc 57 B** : bloc SURGE HISTORY inséré dans §5.6 sous EVENTS (avant
  TRAFFIC). §17.1 marqué "RÉSOLU (Patch 33-A)" (titre passé de "(to add in §5)"
  à "(applied in §5.6)").
  - Météo : **déjà présente** en §5.5 "External signals (V1 — easy)" (bloc
    WEATHER Open-Meteo complet) — le patch dit "if not already present", donc
    rien ajouté en §5.6.
- **Doc 13 C** : note de renvoi (blockquote du patch) insérée avant §3 ; §3.3
  élagué vers un pointeur doc 33 §8 (la liste incluant "accepted/refused ride
  outcome" contredisait désormais doc 33 ; conservé : la phrase fatigue/état
  émotionnel → Imperium/Pulse) ; §4 élagué vers un pointeur doc 33 §6 (les
  exemples "classify a ride…/explain a dead-return risk" contredisaient le
  split CatBoost/Qwen ; conservée : la phrase d'escalade advisory).

## 7. PATCH_FACT-1_docs_07_12_29_32.md — APPLIQUÉ

- **07-1** : `- start day button` ajouté avant `- finish day button` (doc 07,
  section "Imperium Must Handle"). Motif unique, trouvé.
- **12-1** : paragraphe ">24h / journées suivantes plus courtes / operational
  days not calendar days" ajouté après le bloc start/finish (doc 12).
- **29-1** : encart "⚠️ NAMING — do not confuse" ajouté en tête du doc 29,
  entre le titre et "## Scope".
- **32-1** : doc 32 L3 "WR means **Weekly Review / Weekly Report**." remplacé
  par le texte tranché (WR = Weekly Review, renvoi doc 29).

## 8. BACKLOG_base_advice_path.md — APPLIQUÉ

Contenu apposé verbatim à la fin de `99_AUDIT_COHERENCE_DOCS.md` (après la
checklist d'alignement, séparé par `---`).

## 9. BACKLOG_critical_tier_orchestration.md — APPLIQUÉ

Contenu apposé verbatim à la fin de `99_AUDIT_COHERENCE_DOCS.md`, après l'entrée
précédente.

---

## Points laissés inchangés / remarques

- **Patches 30-A et 30-B : déjà appliqués** avant cette passe (état cible
  présent mot pour mot dans le doc 30). Aucune modification, aucune divergence
  détectée entre le patch et l'état du doc.
- **Incohérence interne aux patches (non corrigée, hors périmètre)** : les
  patches 30-B et MÉCA-1 citent "doc 30 §7.6" pour la règle Fable 5 / WR
  re-planning, alors que la numérotation finale du doc 30 (après insertion de
  7.5 finance et 7.6 conseils matinaux) place cette règle en **§7.8**. Aucun des
  remplacements appliqués n'a introduit de référence "§7.6" dans les docs cibles
  (les lignes remplacées ne citent pas de numéro de section), donc aucun doc
  n'est incohérent — mais les fichiers patch eux-mêmes contiennent cette
  référence périmée.
- **Cross-ref doc 32 §5.6–§5.7 → §5.6–§5.8** : modification induite par la
  renumérotation du patch 30-C, non listée explicitement dans un patch (voir
  point 3).
- **3 occurrences `opus-4.7` hors liste MÉCA-1** corrigées au titre des
  remplacements canoniques + grep final demandé (voir point 4).
- **Tests pytest** : aucun ajouté — la consigne du prompt interdit explicitement
  de toucher au code et aux tests (changements 100 % documentation Markdown).
- **Commit/push** : laissé au mécanisme Fable Code, comme indiqué dans le
  prompt.
