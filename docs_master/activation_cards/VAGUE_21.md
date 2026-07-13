# VAGUE 21 — W2 réel (découverte causale locale) — lot de 1

**Composition** : ACT-WR-11 seul. Premier PROPOSANT du domaine WR : gros échelon, vague
dédiée, fenêtre longue. Durée : 7-14 j.

```
id: ACT-WR-11    nom_fr: W2 découverte causale réelle (wr.probe_gen + wr.pair_verdict, 32B)
domaine: wr       classe: proposant   echelon_audace: 4   statut: NOT_CODED
bascule_exacte: UPDATE ai_slot_transition SET tier='local_default' WHERE slot_code IN
  ('wr.probe_gen','wr.pair_verdict');  -- W2 déjà rotatif (V20), bascule dry→réel
prerequis_activation: [ACT-WR-10, ACT-SYS-11, ACT-SYS-10 (audit 100 % contre-lu),
  ACT-PLS-16 (32B éprouvé 2 semaines sur l'interprète)]
protocole_terrain: chaque soir : 3-6 sondes par event notable, verdicts pairés
  (direct_cause/favoring_condition/correlation/no_link + mécanisme ≤200c + confiance),
  assemblage → items chain_proposal au docket ; RIEN n'entre dans le graphe E2 avant
  Phase 5 (V22) ; 14 j — lire les mécanismes proposés, annoter
critere_succes: sorties valides (retry → no_link, jamais de crash de lot) ; filtres durs
  respectés (antériorité, fenêtre 90 j, non-déjà-lié) ; cycles/doubles parents détectés →
  conflicts ; qualité des mécanismes jugée utile à l'œil sur 2 semaines ; agreement audit
  cloud mesuré
rollback: tier retour dry (une ligne) — les candidats/verdicts écrits restent (donnée)
source: spec WR §5 (implémente CONCEPTION_chainage_V2), §10, §13.3 (sélection notable
  DÉTERMINISTE seedée — jamais un LLM ne choisit ce qui est intéressant)
prompt_codex: « Basculer probe_gen+pair_verdict en réel ; smoke : event notable fixture →
  sondes → verdicts → item docket ; consigner. »
observations: les sondes sont des REQUÊTES, jamais stockées comme savoir ; le canal
  vectoriel (c/d de la recherche hybride) exige V6 — sinon canaux graphe+metadata seuls,
  à consigner comme mode dégradé
```
