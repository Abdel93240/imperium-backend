# CONCLUSIONS DU TEST PAPIER (routage & fenêtres de contexte)
Date : 2026-07-04. Objectif : vérifier que les charges réelles (pire cas) tiennent dans
les fenêtres des modèles, et valider le scoring /200 du doc 30. Raisonnement PERFORMANCE
d'abord, budget ensuite.

## Fenêtres des modèles (vérifiées)
- Qwen 32B local : 32k natif → ~16k utiles (÷2 sécurité, pour rester "sharp" ; V100 32Go
  laisse de la marge VRAM, mais qualité prime). EXÉCUTEUR : marge jusqu'à ~20-22k avant
  bascule store éphémère.
- Sonnet / Opus 4.8 / Fable 5 : 1M tokens en entrée chacun (API directe).
- GPT-5.5 : ~1M (922k entrée). Note : 2× input au-delà de 272k (jamais atteint pour nos usages).

## Le goulot = le LOCAL. Le cloud (1M) n'est jamais le problème.

## TÂCHE — Scoring intrinsèque (le plus fréquent) : VALIDÉ
- Le scoreur fonctionne sur MÉTADONNÉES, jamais la data réelle. Le "context_size" du
  scoring /200 est alimenté par un COUNT SQL DÉTERMINISTE fait par le BACKEND
  (COUNT(*) × ~tokens/ligne) → le scoreur reçoit un CHIFFRE, pas les données.
- Pire cas mesuré : ~5k / 16k (prompt scoreur ~2,5k + demande ~1k + descripteur ~0,5k +
  sortie ~0,8k). Marge ~11k. Le scoreur ne déborde JAMAIS.
- Tri CIBLÉE vs GLOBALE = dans le score, via l'interprétation de "complexity" (PAS de
  nouveau critère) : tâche ciblée (chercher/filtrer) = complexity basse même sur gros
  volume ; tâche globale (synthèse/vue d'ensemble) = complexity haute → sort du local.
  Combiné à context_size ×3, le score route correctement (globale lourde → cloud 1M ;
  ciblée lourde → local + store éphémère).

## RÈGLE DURE — débordement de l'exécuteur local
- Si Qwen EXÉCUTE une tâche localement et que le volume dépasse ~20k tokens → ouvrir un
  STORE ÉPHÉMÈRE de vectorisation, travailler par PASSES RAG (même principe que WR Phase 2).
  Ne garde jamais tout en fenêtre. Filet mécanique, PAS décideur (le score a déjà trié
  ciblée/globale en amont).
- Limite honnête : les passes RAG conviennent aux tâches CIBLÉES (le RAG trouve la cible).
  Les tâches GLOBALES (vue d'ensemble simultanée) doivent escalader au cloud 1M (le score
  s'en charge via complexity).

## TÂCHE — Audit d'entrée WR (Phase 1, Opus) : VALIDÉ
- Tâche GLOBALE : charge la semaine écoulée + plans antérieurs + prévisions + RAG historique
  + missions (fenêtre ~120/sem). Pire cas ~300-340k tokens → tient dans 1M (~1/3, marge ~660k).
- C'est la charge la PLUS LOURDE du système (plus que la Phase 3).

## TÂCHE — WR Phase 3 (chaînage profond E2 + re-planning, Fable FORCÉ §7.8) : VALIDÉ
- Ce n'est PAS l'audit d'entrée. La Phase 3 prend les EVENTS de la semaine (signalés
  importants par IA+humain, cf. E2), va chercher dans les events PASSÉS des liens de
  causalité pour créer la PROFONDEUR, puis re-planifie 4 semaines.
- Fable ne s'arrête pas aux patterns : il remonte à la DATA CIBLE réelle vers laquelle les
  patterns pointent, pour VÉRIFIER (pas supposer). Et il procède par HYPOTHÈSES : pour un
  event, plusieurs passes possibles (suppose → vérifie → faux → re-suppose).
- DESIGN RETENU : traitement SÉQUENTIEL + PROMPT CACHING (Scénario C). Fable ouvre un
  "dossier" par event signalé, fait ses passes de vérification, ENREGISTRE le lien trouvé
  (compact), DÉCHARGE le travail intermédiaire, passe au suivant. Charge instantanée
  ~30-50k (jamais toutes les passes de tous les events en même temps). Le contexte de base
  est mis en cache → payé plein une fois, relu à ~10% ensuite.
- COÛT : ~$11-12 par WR (Scénario C). vs gros appel unique ~600k = ~$9 mais RISQUÉ (frôle
  les limites, moins robuste) ; vs séquentiel SANS cache = ~$34 (re-chargement, écarté).
  → ~$600/an pour le WR (poste le plus cher du système). Validé.
- Fable forcé pour la COMPLEXITÉ du raisonnement (chaînage causal, type GraphWalks où Fable
  excelle), PAS pour le volume (la Phase 3 charge peu). Volume ≠ complexité.

## TÂCHES non calculées (couvertes par déduction) :
- Génération plan mensuel (Opus) = l'audit d'entrée en MOINS gros → si l'audit passe (~340k),
  le plan mensuel passe. Validé par déduction.
- Réajustement plan quotidien → passe par le SCORING (déjà validé) qui route local/Sonnet/+.
- Conversation (WR Phase 2 ET chatbot Imperium) → dialogue lié au système, court, store
  éphémère (RAG) garde le local sharp. Léger, tient largement. Pas un cas lourd.
- GPT-5.5 events région parisienne → liste de quelques dizaines d'events/semaine, jamais
  près du 1M. Validé sans calcul.

## VERDICT GLOBAL
- Le scoring /200 (doc 30) est VALIDÉ : les charges tombent dans les bonnes bandes.
- Aucun débordement CLOUD (1M amplement suffisant ; pire cas ~340k).
- Le seul goulot = le local (16k), géré par le store éphémère + la règle dure >20k.
- Fable justifié par la complexité, pas le volume. Budget WR ~$600/an, reste du système
  bien moindre (local gratuit, Sonnet pour le moyen, Opus pour le lourd global).
- À METTRE À JOUR dans doc 30 : le statut Fable (§7.8 dit "suspendu 2026-06-17 → Opus" ;
  Fable est revenu le 01/07/2026, donc réactiver Fable pour la Phase 3).
