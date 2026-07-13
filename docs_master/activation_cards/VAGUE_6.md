# VAGUE 6 — Infrastructure IA locale (GPU phase 2 — Q16)

**Composition** : ACT-SYS-12, ACT-SYS-13, ACT-SYS-14, ACT-SYS-11. Smoke infra, pas de
feature produit : rien de visible utilisateur ne change. Durée : 2-3 j de smoke.
Prérequis matériel : V100+P40 sur Tower (F10 §5-bis phase 2, non datée — Q16).

```
id: ACT-SYS-12    nom_fr: Modèle 32B servi (Qwen3-32B, V100, Q5)
domaine: system   classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: démarrage du serving (llama.cpp/Ollama selon déploiement) + healthcheck
prerequis_activation: []  (matériel phase 2)
protocole_terrain: endpoint interne répond ; latence/température 0/JSON contraint vérifiés
critere_succes: smoke GBNF : sortie conforme à un schéma sur 20 essais, temp 0 stable
rollback: arrêt du serving (aucun consommateur tant que SYS-11 OFF)
source: F3-01, doc 30 §3.3, F10 §5-ter/quater
prompt_codex: « Démarrer le serving 32B ; smoke schéma contraint ; consigner. »
observations: AVANT la bascule : nettoyer les 6 références 7B en dur (DV-6/AD-8)
```

```
id: ACT-SYS-13    nom_fr: Serving embeddings 1024 (qwen3-embedding:8b, P40)
domaine: system   classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: démarrage du serving + module services/ai/embedding.py pointé dessus
prerequis_activation: []  (matériel phase 2 ; socle 0d)
protocole_terrain: embed(texts) → vector(1024) exactement ; latence acceptable
critere_succes: 1024 dims strictes (validation memories.py), similarité cohérente sur
  paires de test
rollback: arrêt du serving
source: FINDINGS T4, doc 38 §5/§11, migration 0032, F3-02
prompt_codex: « Démarrer le serving embeddings ; smoke 1024 dims ; consigner. »
observations: débloque la chaîne D5 (V25) — mais PAS automatiquement (R1)
```

```
id: ACT-SYS-14    nom_fr: embeddings_enabled=true (recherche vectorielle en lecture)
domaine: system   classe: det_lecture   echelon_audace: 1   statut: OFF
bascule_exacte: passer embeddings_enabled de False à True (aujourd'hui EN DUR
  memories.py:58 / decision_framework.py:263 — à convertir en setting au socle 0d)
prerequis_activation: [ACT-SYS-13]
protocole_terrain: recherche top-K sur ai_memories (vide au début — lecture seulement,
  le COMMIT reste bloqué D5) ; 2-3 j
critere_succes: top-K répond sans erreur, seuil 0.35 appliqué, modes current_truth/
  historical corrects
rollback: embeddings_enabled=false
source: memories.py:56-58, doc 38 §11, F1-07
prompt_codex: « Basculer le flag ; smoke top-K ; consigner. »
observations: distinct de ACT-SYS-15 (commit) — R6 : lecture avant écriture
```

```
id: ACT-SYS-11    nom_fr: LLM local réel (qwen_enabled=true, qwen_dry_run=false)
domaine: system   classe: det_ecriture   echelon_audace: 2   statut: OFF
bascule_exacte: env QWEN_ENABLED=true QWEN_DRY_RUN=false QWEN_MODEL=<32B servi>
  (config.py:49-53) + real_ai_enabled converti de constante en setting et passé à true
prerequis_activation: [ACT-SYS-12]
protocole_terrain: smoke endpoint interne (pas de slot produit actif à ce stade — les
  slots s'activent par leurs vagues) ; 2-3 j
critere_succes: appel réel 32B via le wrapper (GBNF, retry, dry-run OFF marqué) sans
  erreur ; AUCUN effet produit visible (tous les slots encore éteints)
rollback: QWEN_DRY_RUN=true (une variable d'env)
source: config.py:49-53, decision_framework.py:262, spec Pulse §6 (wrapper), AD2-6
prompt_codex: « Basculer les flags qwen ; smoke wrapper ; vérifier zéro slot actif ;
  consigner. »
observations: la bascule N'ALLUME AUCUN slot (ils ont chacun leur fiche) — c'est le
  carburant, pas le moteur
```
