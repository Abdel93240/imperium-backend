# Décisions structurantes des EVENTS (avant le catalogue doc 77)
Date : 2026-07-03. Basé sur l'inventaire Fable (INVENTAIRE_events.md).
Rappel décisions liées : D2 (journal `events` unique), D3 (format dotted, domaines génériques).

## E1 — mission.failed (double émetteur résolu)
Problème : deux émetteurs de mission.failed avec payloads incompatibles + mission.abandoned
construit par f-string. Décision :
- planning.mission.completed → mission réussie (fait distinct positif)
- planning.mission.aborted → mission pas réussie/interrompue. La RAISON va dans le payload
  { reason: abandoned | no_resources | poor_organization | no_energy | expired | ... }.
  "abandoned" est une RAISON, pas un type d'event (sous-catégorie de "aborted").
- planning.mission.ai_disagreement → event SÉPARÉ (pas une simple raison) quand la cause
  est un désaccord de planification IA↔humain. Émis EN PLUS de mission.aborted, car c'est
  la matière première du LoRA d'autonomie (proposition + correction + raison). Les deux
  events vivent dans le MÊME journal `events`, reliés par correlation_id + causation_id.
Principe général (à appliquer au catalogue) : un event séparé par FACETTE (domaine différent
OU consumer/but différent OU valeur analytique propre) ; sinon un seul event + nuance dans
le payload.

## E2 — Politique de chaînage (correlation / causation / profondeur)
Constat Fable : correlation_id aléatoire (ne relie rien), causation_id toujours vide.
Structure cible :
- correlation_id = le DOSSIER (une histoire = un fait déclencheur + ses events directs).
  Histoires courtes et lisibles.
- causation_id = pointeur vers l'event/dossier qui a DIRECTEMENT déclenché celui-ci.
  Permet de remonter la cascade.
- profondeur (NOUVEAU champ, à ajouter) = niveau dans la cascade (1 = racine, +1 par niveau
  de conséquence). Permet de savoir d'un coup d'œil combien de dossiers au-dessus, sans
  suivre toute la chaîne.
Règle "nouveau dossier" : un nouveau fait déclencheur = nouveau correlation_id. Causé par
un autre → profondeur +1 + causation vers le parent. Fait racine → profondeur 1, causation vide.

Remplissage en DEUX TEMPS :
1. TEMPS RÉEL (déterministe, V1) : chaînage évident/immédiat (un fait → ses events directs ;
   cause directe même session). Simple, sûr, codable maintenant.
2. HEBDOMADAIRE (Fable, en Phase 3 du WR, APRÈS la conversation) : chaînage PROFOND/LOINTAIN,
   UNIQUEMENT sur les events SIGNALÉS COMME IMPORTANTS par l'audit d'entrée (IA) ou par
   l'utilisateur pendant la conversation. Le filtre de pertinence = attention IA + humain.
   Mécanique : Fable cherche un pattern lié dans la mémoire vectorielle → remonte aux events
   sources → propose le lien → utilisateur valide. Si RIEN trouvé → devient une QUESTION à
   l'utilisateur, dont la réponse GÉNÈRE un nouveau pattern (vectorisé pour la fois d'après).
   Le système apprend par le dialogue.

PRINCIPE FONDATEUR (transverse, gravé) : modéliser la vie parfaitement est IMPOSSIBLE (effet
papillon infini). Le système ne cherche PAS à tout corréler. Il va le plus loin possible sur
ce qui est PERTINENT (jugé par l'IA ou l'humain) et accepte ses limites. Ce qui n'intéresse
personne, ou est trop sournois à capter, est laissé de côté sans acharnement. Accepter la
limite = garder le système honnête (pas de fausses corrélations de façade).

## E3 — Débrancher imperium_events (Option B)
imperium_events = déprécié (D2), vide, mais 3 points de code le référencent encore :
event_readers.py, GET /api/imperium/events, contrat frontend (contracts.py:47).
Décision (Option B) : DÉSACTIVER proprement ces lecteurs orphelins pour l'instant (ne PAS
se précipiter à les repointer). Marquer la table dépréciée (aucune donnée à migrer). Les
VRAIS consumers du journal `events` seront conçus plus tard, dans le chantier d'orchestration
Imperium ("brancher le système nerveux"). E3 débranche le mort, ne crée pas le vivant.

## Chorégraphie WR (esquisse, pour situer E2 — à détailler au chantier WR dédié)
5 phases : (0) déclenchement mardi 20h + pré-calcul agrégats déterministes ; (1) audit
d'entrée = 1ère passe IA (topo + questions + chaînage provisoire) ; (2) conversation
humain↔IA ; (3) chaînage profond = passe Fable en arrière-plan (WR réductible, pas
bloquant) ; (4) validation finale des propositions par l'utilisateur ; (5) enregistrement
déterministe (chaînages, patterns mémoire [bloqués par D5], review_memory_decisions,
rapport, révisions de règles). = 3 moments d'intervention IA.

PÉRIMÈTRE V1 du WR : PAS la machine complète. V1 = tester les MÉCANIQUES DE BASE, priorité
absolue : le SCORING (decision framework), le modèle local 32B, et le 2e scoring (Vector :
acceptation de course/importance/zone). Le chaînage profond et "rendre la machine plus
intelligente" = APRÈS V1. Futur : V3 du WR (à décrire), et objectif VISUEL (graphiques,
pas du texte plat) une fois toute la back-end V1 finie.
