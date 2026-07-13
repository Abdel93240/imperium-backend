# VAGUE 13 — Interprète Pulse réel (shadow de fait)

**Composition** : ACT-PLS-16 seul. C'est LA première IA locale réelle du produit — vague
de 1, fenêtre longue (Q21 : 14 j proposés). État « shadow de fait » : l'interprète nomme
des procédures, le code vérifie, MAIS toutes les procédures sont encore inactives → rien
ne s'exécute, rien n'est proposé. On observe la qualité de jugement à blanc.

```
id: ACT-PLS-16    nom_fr: Interprète réel local (Qwen3-32B, temp 0, GBNF) — shadow
domaine: pulse    classe: ia_shadow   echelon_audace: 3   statut: NOT_CODED
bascule_exacte: UPDATE ai_slot_transition SET tier='local_default' WHERE
  slot_code='pulse.interpreter';  -- avec real_ai_enabled=true (V6) ; procédures actives=0
prerequis_activation: [ACT-SYS-11, ACT-PLS-11, ACT-PLS-12, ACT-PLS-14, ACT-SYS-10]
  (l'audit décroissant contre-lit au cloud → V12 obligatoire)
protocole_terrain: dispatch_log : sorties RÉELLES du 32B (procedures_named, confidence,
  rationale_fr ≤400c) ; audit_sample_pct=100 → chaque sortie contre-lue (ai_audit_samples) ;
  14 j (Q21) — lire chaque rationale, annoter user_reaction (useful/useless/missed)
critere_succes: sorties valides ≥95 % (retry compris, jamais de crash silencieux) ;
  agreement cloud mesurable ; procédures nommées pertinentes à l'œil humain sur 2 semaines
rollback: UPDATE ai_slot_transition SET tier='...' + real dispatch coupé en remettant les
  jobs runner en dry-run (une ligne) — les logs restent (donnée, R7)
source: spec Pulse §6, §13 ; contrat interpreter_output.schema.json
prompt_codex: « Basculer pulse.interpreter en réel (procédures toutes inactives) ; smoke :
  dispatch → sortie 32B validée + échantillon d'audit ; consigner. »
observations: escalate=true / confidence=low → routage doc 30 (contre-lecture) : vérifier
  ces chemins pendant la fenêtre ; le plafond 3k tokens d'entrée est testé (whitelist)
```
