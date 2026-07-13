# VAGUE 12 — Garde-fous cloud (domaine system)

**Composition** : ACT-SYS-09, ACT-SYS-10, ACT-SYS-17. À activer AVANT tout slot advisory
dont l'audit ou le tier passe par un cloud (V13+). Ordre interne impératif : gate PUIS
sortie. Durée : 3-7 j.

```
id: ACT-SYS-09    nom_fr: Privacy gate central (very_high ne sort JAMAIS)
domaine: system   classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: flag privacy_gate_enforced=true — le wrapper LLM/embeddings REFUSE tout
  payload sans verdict gate (fail-closed)
prerequis_activation: []
protocole_terrain: tentatives de sortie contrôlées (fixtures par tier de privacy) → seuls
  les payloads autorisés passent, very_high TOUJOURS bloqué, dégradation plutôt que fuite ;
  3-7 j
critere_succes: zéro fuite sur la batterie de fixtures ; chaque blocage loggé et explicable
rollback: INTERDIT tant qu'une sortie cloud est active (rollback = couper d'abord
  ACT-SYS-10) — consigner comme contrainte dure
source: FINDINGS T5, doc 75 §8 (non négociable §0.6), docs 09/44 §8, PRIV-002
prompt_codex: « Activer le gate fail-closed ; smoke fixtures 4 tiers ; consigner. »
observations: aujourd'hui « privacy par absence » (digest §6) — cette fiche transforme
  l'absence en mécanisme AVANT que les assemblers cloud existent en prod
```

```
id: ACT-SYS-10    nom_fr: Première sortie cloud réelle autorisée (wrapper de tiers)
domaine: system   classe: notifiant   echelon_audace: 3   statut: NOT_CODED
bascule_exacte: flag cloud_tiers_enabled=true (le wrapper honore cloud_forced/routed en
  réel ; routed≈cloud_forced tant que le routeur /200 n'est pas branché, ACT-SYS-18)
prerequis_activation: [ACT-SYS-09]
protocole_terrain: UN appel cloud de smoke (payload de test non personnel) tracé de bout
  en bout ; 3-7 j — aucun slot produit ne consomme encore
critere_succes: appel loggé (modèle, tokens, coût) ; gate consulté ; clés/quotas sains
rollback: cloud_tiers_enabled=false (une variable)
source: specs Pulse §13 / WR §10 / Daily §8 (« routed ≈ cloud_forced en attendant »),
  F3-11, doc 30 §3
prompt_codex: « Activer cloud_tiers ; smoke 1 appel tracé ; consigner. »
observations: publier vers un cloud = irréversible par nature — c'est la bascule la plus
  surveillée du socle ; statut Fable/pricing doc 30 §7.8 à rafraîchir avant (DV-7/DV-8)
```

```
id: ACT-SYS-17    nom_fr: Observabilité IA (ai_call_logs + pricing)
domaine: system   classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: flag ai_call_logging=true (chaque appel local/cloud écrit sa ligne)
prerequis_activation: []  (à activer idéalement AVANT ACT-SYS-10)
protocole_terrain: chaque appel (smoke V6, smoke V12) a sa ligne : modèle, tokens,
  latence, coût estimé ; 3-7 j
critere_succes: « ALL STEPS LOGGED » (doc 43 §3.2) vérifié ; coûts sommables par jour
rollback: flag=false (jamais recommandé — observabilité)
source: doc 43 §17, F2-14, DV-8 (seed pricing à régénérer depuis doc 30 avant)
prompt_codex: « Activer le logging ; smoke : 1 appel → 1 ligne ; consigner. »
observations: —
```
