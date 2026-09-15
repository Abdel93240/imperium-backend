# VAGUE 6 — Infrastructure IA locale (état Phase H ; décision historique Q16)

**Composition** : ACT-SYS-12, ACT-SYS-13, ACT-SYS-14, ACT-SYS-11. Smoke infra, pas de
feature produit : rien de visible utilisateur ne change. Durée : 2-3 j de smoke.
État actuel : local_executor déployé et validé en infrastructure (F10 §5-ter).
Les services complémentaires restent futurs (F10 §5-quater) ; la validation humaine
Phase H n’est pas déclarée terminée. Mapping logique : doc 30 §3 uniquement.
`qwen_enabled=False` et `real_ai_enabled=False` restent inchangés ; aucune activation
produit. Les bascules ci-dessous décrivent des étapes futures, pas des actions autorisées
par cette mise à jour documentaire. Aucun shadow slot ni seed ai_role_models ajouté.

```
id: ACT-SYS-12    nom_fr: local_executor servi (mapping doc 30 §3.3)
domaine: system   classe: det_lecture   echelon_audace: 1   statut: INFRA_VALIDEE_PRODUIT_OFF
bascule_exacte: aucune — service déjà déployé ; état et procédure physique en F10 §5-ter
prerequis_activation: []  (état infrastructure Phase H ; validation humaine non clôturée)
protocole_terrain: consulter les mesures et contrats H3 en F10 §5-ter
critere_succes: résultats H3 consignés en F10 ; ne pas confondre santé du service et
  intégration backend ; H3.7 GpuServiceUnreachable/skip NON TESTÉ (wrapper absent)
rollback: procédure d'arrêt du service selon F10 ; aucun consommateur produit activé
source: F3-01, doc 30 §3.3, F10 §5-ter
prompt_codex: « Vérifier l'état infra documenté et consigner les validations restantes. »
observations: qwen_enabled=False ; real_ai_enabled=False ; aucune modification ai_role_models
```

```
id: ACT-SYS-13    nom_fr: embedding_service 1024 (mapping doc 30 §3.12 ; infra F10)
domaine: system   classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: démarrage du serving + module services/ai/embedding.py pointé dessus
prerequis_activation: []  (service complémentaire futur selon F10 ; socle 0d)
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
bascule_exacte: étape future d’intégration du local_executor via le wrapper backend ;
  résolution du rôle selon doc 30 §3.3 et endpoint selon F10 ; aucune bascule ici
prerequis_activation: [ACT-SYS-12]
protocole_terrain: smoke endpoint interne (pas de slot produit actif à ce stade — les
  slots s'activent par leurs vagues) ; 2-3 j
critere_succes: appel réel local_executor via le wrapper (GBNF, retry, dry-run OFF marqué) sans
  erreur ; AUCUN effet produit visible (tous les slots encore éteints)
rollback: QWEN_DRY_RUN=true (une variable d'env)
source: config.py:49-53, decision_framework.py:262, spec Pulse §6 (wrapper), AD2-6
prompt_codex: « Préparer la validation wrapper ; conserver les flags OFF ; consigner
  les prérequis avant toute activation distincte. »
observations: la bascule N'ALLUME AUCUN slot (ils ont chacun leur fiche) — c'est le
  carburant, pas le moteur
```
