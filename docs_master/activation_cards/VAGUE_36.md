# VAGUE 36 — Nettoyages et différés

**Composition** : ACT-SYS-16, ACT-EVT-04, ACT-SYS-18. Des DÉBRANCHEMENTS et un chantier
différé — journalisés comme des activations (un débranchement est une bascule, R1
symétrique). Durée : 3-7 j.

```
id: ACT-SYS-16   nom_fr: Sortie de n8n (portage des 2 ponts WR + décommissionnement)
domaine: system   classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: (1) déployer le portage des workflows #1/#2 en appels internes ;
  (2) déprécier n8n_client ; (3) EXPORT RÉEL de l'instance VPS vérifié ; (4) couper le
  conteneur n8n (dernier)
prerequis_activation: [ACT-WR-02 (le flux WR restructuré n'utilise plus les ponts)]
protocole_terrain: le flux WR fonctionne sans n8n pendant 7 j avant la coupure du
  conteneur ; docs 06/45/18/32/44 §13 + docker-compose + config N8N_* patchés
critere_succes: zéro responsabilité produit résiduelle pour n8n (N8N_INVENTORY §C) ;
  workflow #3 (mock) converti en test pytest
rollback: redémarrer le conteneur (les exports existent) — fenêtre de retour courte
source: N8N_INVENTORY complet ; PATCH P-3/W-5/D-6/V-8 (aucun NOUVEAU workflow n8n)
prompt_codex: « Porter #1/#2, déprécier le client, vérifier l'export VPS, couper ;
  consigner chaque étape datée. »
observations: n8n_dry_run=True reste en place jusqu'à la coupure — ne JAMAIS passer à
  false (la direction est la sortie, pas l'activation)
```

```
id: ACT-EVT-04   nom_fr: Débranchement des legacy (imperium_events, path_items, priority_rules, vault_transactions)
domaine: system   classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: migrations de drop + coupure des routes GET dépréciées (imperium.py:1275,
  routes/vault.py) — ordre et échéance = réponse Q15
prerequis_activation: [Q15 TRANCHÉE ; ACT-WR-03 (plus aucun lecteur legacy — AD-2 fini)]
protocole_terrain: 7 j de surveillance des 404/erreurs clients après coupure des routes ;
  puis drops
critere_succes: zéro lecteur cassé ; écart tables migrées/modélisées résorbé (AD-3)
rollback: routes réactivables (revert) AVANT les drops ; après drop : restauration par
  backup (d'où l'ordre routes→drops avec fenêtre)
source: AD-3/AD-9, Q15, doc 77 « À faire » n°5 (E3 option B)
prompt_codex: « Couper les routes, observer 7 j, dropper ; consigner chaque objet daté. »
observations: c'est la fin du pattern « refonte faite, ancien jamais débranché »
  (audit_resync §dette)
```

```
id: ACT-SYS-18   nom_fr: Routeur /200 branché (T3 — chantier différé)
domaine: system   classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: flag router_200_enabled=true (les slots tier='routed' cessent de se
  comporter comme cloud_forced et passent par le scoring /200)
prerequis_activation: [ACT-SYS-12 (32B servi), spec d'implémentation T3 écrite (L),
  colonnes routage doc 31 §7 codées]
protocole_terrain: comparaison des décisions de routage vs l'ancien comportement
  cloud_forced sur 7 j (log par slot routed)
critere_succes: escalades/downgrades conformes doc 30 ; mécanique critique 180+ intacte
rollback: router_200_enabled=false (routed redevient cloud_forced)
source: FINDINGS T3 (« pas bloquant, différable »), doc 30, doc 31 §7
prompt_codex: « Brancher le routeur ; smoke slot routed fixture ; consigner. »
observations: seule feature de la roadmap dont la PASSE elle-même n'est pas encore
  arbitrée — placée ici pour qu'elle ne se perde pas
```
