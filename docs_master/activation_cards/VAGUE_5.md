# VAGUE 5 — Path notifiant

**Composition** : ACT-PTH-03 seul (lot de 1 — le religieux mérite sa fenêtre propre,
attribution sans ambiguïté avec les alertes Vault de V4). Durée : 3-7 j.

```
id: ACT-PTH-03    nom_fr: Rappels Path (path.reminder — bannières/notifications de pratique)
domaine: path     classe: notifiant   echelon_audace: 3   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code='path_reminders';
prerequis_activation: [ACT-SYS-07, ACT-PTH-02]
protocole_terrain: rappels reçus aux moments prévus (préparation jeûne, pratiques
  planifiées) ; 7 j — pertinence ET absence de harcèlement
critere_succes: rappels exacts, ack réguliers, zéro rappel pendant une fenêtre de prière
rollback: job disabled
source: doc 41 §5 (path.reminder.requested), §8 (bannières jeûne), FINDINGS Q3
prompt_codex: « Activer path_reminders ; smoke : fixture → notify() ; consigner. »
observations: privacy very_high — jamais de contenu religieux vers un canal cloud tiers
  sans arbitrage (doc 41 §17) ; le canal Q18 doit être jugé compatible
```
