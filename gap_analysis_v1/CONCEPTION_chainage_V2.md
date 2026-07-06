# CONCEPTION CIBLE DU CHAÎNAGE PROFOND (post-V1) — entonnoir + distillation
Date : 2026-07-05. Travail Fable + arbitrage utilisateur. STATUT : conception CIBLE, à
implémenter APRÈS le WR V1 (le chaînage profond reste post-V1, cf. priorité V1 = scoring +
32B + 2e scoring Vector). NE PAS coder maintenant.

## Diagnostic des 2 failles de la méthode actuelle (Fable Phase 3 monolithique)
FAILLE 1 (majeure) — la similarité vectorielle trouve ce qui RESSEMBLE, pas ce qui CAUSE.
  L'effet ("trou dans le sol") est sémantiquement ÉLOIGNÉ de sa cause ("fuite d'eau il y a
  3 semaines", "engin lourd", "gel"). La recherche vectorielle classique remonte des effets
  similaires, pas les causes. Le rappel des candidats causaux est structurellement mauvais.
  Fable raisonne alors sur des candidats mal choisis (on paie un modèle frontier pour ça).
FAILLE 2 — la tâche est monolithique (un appel juge pertinence + mécanismes + assemblage +
  profondeur = formulation "GraphWalks" qui force Fable). Décomposée, presque chaque
  sous-étape est déterministe ou un jugement fermé qu'un 32B fait bien.
Point mineur : le graphe déjà posé (liens déterministes temps réel) n'est pas exploité comme
  canal de candidats (le traverser 1-2 sauts est gratuit et précis). La précédence temporelle
  devrait être un filtre SQL DUR (un event ne peut être causé que par un antérieur), pas un
  jugement LLM.

## L'entonnoir cible en 4 étapes
Étape 1 — CANDIDATS, hybride : filtres durs (antériorité SQL, fenêtre temporelle, pas déjà
  lié) puis 3 canaux : (a) le GRAPHE (mêmes entités/lieu/correlation_id, voisins du graphe
  causal existant), (b) vectoriel classique, (c) CANAL VECTORIEL CAUSAL : le modèle local
  génère 3-5 hypothèses de causes, on VECTORISE ces hypothèses pour chercher la DESCRIPTION
  de la cause (pas la ressemblance de l'effet) → corrige la Faille 1. Union ~30-60 candidats,
  reranker → ~8-10.
Étape 2 — JUGEMENT PAIRÉ, local : pour chaque paire (candidat→event), JSON fermé { type de
  lien: cause directe / condition favorisante / corrélation / aucun ; mécanisme en 1 phrase ;
  confiance /100 }. ~500 tokens/paire, tient dans les 16k du Qwen. 500-800 micro-jugements
  indépendants remplacent l'appel géant.
Étape 3 — ASSEMBLAGE, algorithmique : les paires retenues = arêtes ; causation_id, profondeur
  (= profondeur parent +1), détection cycles/doubles parents = du CODE. Le local n'arbitre que
  les conflits et rédige les propositions lisibles pour la Phase 4.
Étape 4 — AUDIT DÉCROISSANT + DISTILLATION : Fable audite un échantillon des jugements locaux
  + tous les cas basse confiance. Chaque désaccord Fable/local et chaque validation/rejet en
  Phase 4 alimente un DATASET (la Phase 4 = usine à labels gratuite pour LoRA ; les NÉGATIFS/
  rejets valent de l'or). Quand accord local/Fable ~90-95% sur plusieurs semaines → couper le
  cloud. MÉTRIQUES dès le départ : taux d'acceptation Phase 4, + liens ajoutés manuellement
  (= rappel manqué). Sans ça, "proche du cloud" n'est pas mesurable.
Note : le RE-PLANNING 4 semaines reste sur Fable (chantier LoRA à part, la moitié la plus dure).
On ne rapatrie ICI que le CHAÎNAGE.

## ARBITRAGE UTILISATEUR (ce qu'on fait vraiment, et quand)
- V1 (maintenant... plus tard, après le WR V1) : on garde Fable comme JUGE. On met l'effort
  seulement sur le FILTRAGE EN AMONT (Étape 1 : bien sélectionner les candidats, bonne
  vectorisation, canal causal) pour donner de BONNES data à Fable. Le jugement, l'assemblage
  local, la distillation = PAS en V1. Méthode actuelle (~$11-12/WR, ~$600/an) conservée pour
  le jugement — pas cher, ça marche, ça donne les 1ères données réelles.
- V2 : rapatrier le jugement pairé en local (Qwen 32B), audit Fable 100% décroissant, +
  Reranker 4B sur P40. Puis QLoRA du juge sur les labels Phase 4 (~1-2k paires, 8-12 semaines).
- V3 (optionnel) : 70B en split V100+P40 pour l'arbitrage (Étape 3) si les métriques le justifient.

## RÉSERVES CRITIQUES (à valider empiriquement, ne pas tenir pour acquis)
1. Le canal causal repose sur la QUALITÉ des hypothèses générées par le 32B (le maillon
   faible). S'il hallucine des causes plausibles-mais-fausses, on vectorise du vent. À prouver.
2. Le jugement PAIRÉ atomise des causes parfois GLOBALES (un faisceau : session VTC + nuit
   blanche + stress finance ensemble, pas isolément). Risque de rappel manqué. Piste : juger
   un event contre un petit GROUPE de candidats, pas 1 par 1.
3. Complexité ajoutée énorme pour un système pas encore construit → ne concevoir les seuils
   qu'avec des DONNÉES RÉELLES (issues du WR V1). Éviter la sur-ingénierie à l'aveugle.

## MATÉRIEL (confirmé par le passage V100 32Go)
- Qwen3-32B (4-bit) ≈ 19-20 Go sur V100 → tient, reste ~12 Go KV cache, batching ~10 séquences.
  500-800 jugements/semaine en 1-2h de nuit (débit 50-100 tok/s agrégé). → passe profonde
  nocturne, validation Phase 4 le lendemain. Plus besoin de scinder rapide/profond.
- QLoRA LOCAL faisable sans achat : QLoRA 14B confortable, QLoRA 32B jouable en serrant
  (batch 1-2, gradient checkpointing, séquences courtes 1-2k = cas favorable). Volta = pas de
  BF16 → FP16 + loss scaling ; Unsloth supporte la V100. Boucle complète (inférence + labels
  Phase 4 + distillation + redéploiement) 100% sur la Tower. La 3090 perd sa justification
  principale (ne redevient utile que pour 70B rapide ou entraînement plus gros).
- Reranker Qwen3-4B sur P40 : brique V2 UNIQUEMENT. Rôle = réduire ~60 candidats → ~8-10.
  Or réduire n'a d'intérêt que si le JUGE est CONTRAINT. En V1 Fable juge (1M de fenêtre,
  fort) → il avale les 60 candidats sans peine, le reranker serait inutile (travail en
  double). Le reranker ne sert QUE quand on rapatrie le jugement en LOCAL (Qwen 16k, faible) :
  là il faut donner au petit modèle les 8-10 meilleurs déjà triés. = outil d'optimisation
  sous contrainte, la contrainte n'existe qu'en local → V2.
- Option V3 : 70B 4-bit (~40Go) en split V100+P40 (56Go) via llama.cpp, 3-5 tok/s (P40),
  OK pour ~30-50 arbitrages/semaine en fond (~1h). Pas nécessaire au départ.
- Contraintes Volta/Pascal : pas de FlashAttention 2, pas de kernels AWQ/Marlin → llama.cpp/
  GGUF ou vLLM GPTQ uniquement.
