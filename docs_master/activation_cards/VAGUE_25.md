# VAGUE 25 — Mémoire vivante (échelon 5 — apprenant)

**Composition** : ACT-SYS-15, ACT-WR-16, ACT-WR-17. La mémoire commence à s'écrire et à
bouger TOUTE SEULE (dans les limites arbitrées). **Q5 BLOQUANT** pour ACT-WR-17 (conflit
doctrinal doc 75 « confidence ne descend jamais seule » vs spec WR §6.3 — DV-1). Durée :
14 j minimum.

```
id: ACT-SYS-15   nom_fr: Commit mémoire WR débloqué (D5 levé)
domaine: system   classe: det_ecriture   echelon_audace: 2   statut: OFF
bascule_exacte: storage_enabled=true (lever WR_MEMORY_COMMIT_DISABLED_REASON,
  memories.py:31/244 — convertir la garde en setting au socle 0d)
prerequis_activation: [ACT-SYS-13, ACT-SYS-14]
protocole_terrain: premier commit mémoire validé (WR ou décision explicite) → ligne
  ai_memories avec vecteur 1024, privacy_level obligatoire ; 3-7 j
critere_succes: écritures validées uniquement (no-override tenu) ; validation stricte
  1024 dims ; supersession/is_active fonctionnels
rollback: storage_enabled=false (lignes écrites conservées)
source: PHASE_0 D5, memories.py, migration 0032, doc 75
prompt_codex: « Lever D5 ; smoke commit validé fixture ; consigner LA DATE (fin de la
  « dette assumée » D5 du digest). »
observations: —
```

```
id: ACT-WR-16    nom_fr: W3 réel — extraction + confrontation d'identité (écrit la mémoire)
domaine: wr       classe: apprenant   echelon_audace: 5   statut: NOT_CODED
bascule_exacte: UPDATE ai_slot_transition SET tier='local_default' WHERE slot_code IN
  ('wr.pattern_extract','wr.identity');
prerequis_activation: [ACT-SYS-15, ACT-WR-11, ACT-WR-15]
protocole_terrain: clôtures d'épisode → patterns canoniques (≤240c, autoportants) →
  top-K → verdicts duplicate/reinforces/refines/contradicts/unrelated → EFFETS APPLIQUÉS
  PAR LE CODE (duplicate n'insère pas, incrémente ; contradiction n'altère RIEN avant
  arbitrage Phase 4) ; 14 j — relire chaque pattern créé
critere_succes: canonicité rejetée quand il faut ; context_predicate validé contre la
  whitelist ; zéro écriture hors des 5 effets contractuels ; patterns lus = sensés
rollback: tiers retour dry (mémoire écrite conservée ; nettoyage éventuel = décision
  utilisateur explicite, jamais automatique)
source: spec WR §6.1/6.2 ; PATCH_WR W-4 (table compagnon tant que Q5 ouvert) ; C-3
  (librairie extraction PARTAGÉE, le chatbot la consommera)
prompt_codex: « Basculer pattern_extract+identity en réel ; smoke épisode fixture →
  confrontation → effet exact ; consigner. »
observations: PREMIER échelon 5 du système — c'est ici que « le système apprend » devient
  littéral ; surveiller la qualité plus que le volume
```

```
id: ACT-WR-17    nom_fr: Moteur d'exposition 6.3 (la confiance bouge sur observation)
domaine: wr       classe: apprenant   echelon_audace: 5   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code='wr_exposure_daily';
prerequis_activation: [ACT-WR-16 ; Q5 TRANCHÉE (DV-1 — sinon la fiche reste gelée)]
protocole_terrain: job quotidien : prédicats évalués sur les rollups du jour ; confirmé →
  confidence += α(100−c) ; présenté non confirmé → −βc ; NON PRÉSENTÉ → RIEN (un pattern
  rare reste fort) ; 14 j — suivre 3-5 patterns témoins
critere_succes: mouvements exactement conformes au moteur ; patterns sans prédicat
  immobiles ; v_memories_active cohérente avec le seuil
rollback: job disabled (confidences figées en l'état — donnée, R7)
source: spec WR §6.3 ; Q5/DV-1 (doc 75 §0.3/0.4 verrouillé — amendement doctrinal requis)
prompt_codex: « (Q5 réglée) Activer exposure_daily ; smoke prédicat fixture → mouvement
  exact ; consigner. »
observations: si Q5 = « doc 75 prime », cette fiche est ANNULÉE et remplacée par
  supersession/review_due uniquement — à consigner ici
```
