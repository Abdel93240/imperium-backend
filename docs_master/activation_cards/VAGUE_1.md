# VAGUE 1 — La boucle vitale (R9)

**Composition** : ACT-SYS-06 (runner + premier job), ACT-VLT-05 (pression financière),
ACT-SYS-07 (canal de notifications), ACT-PTH-02 (fenêtres de prière) — 4 features +
l'USAGE réel de l'existant (missions/sessions, ACT-SYS-04, déjà ON).

**Justification (challenge du point de départ suggéré)** : la plus petite chaîne
bout-en-bout utile dès la semaine 1 = l'utilisateur vit sa journée avec les missions
réelles (existant ON) ; la pression Vault lui dit OÙ il en est financièrement ; les
fenêtres de prière rythment la journée ; le runner consomme les events du jour et produit
un rollup observable (le « events consommés » suggéré — le consommateur PÉRENNE, l'usine
WR, arrive en V18) ; le canal porte la première notification réelle. Attribution R4 :
jauge écran Vault / notification canal / écran prières / table rollup — quatre effets non
confondables. Prérequis code : socle 0a+0b + mini-passe Vault (pression) + mini-lot Path
(Q19), mergés ÉTEINTS. Durée d'observation : 7 j (classe la plus haute = notifiant).

```
id: ACT-SYS-06    nom_fr: Runner de jobs — premier job actif (rollup quotidien minimal)
domaine: system   classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code='daily_events_rollup';
  (job quotidien 23:45 : lit les events du jour, écrit un rollup compteur par domaine)
prerequis_activation: []  (première feature de la roadmap ; le runner lui-même démarre
  avec TOUS ses jobs enabled=false — CF-4)
protocole_terrain: table job_runs (1 ligne/jour, status=completed) + table de rollup ;
  observer 7 j — zéro exécution manquée, zéro double exécution (advisory locks)
critere_succes: 7 runs consécutifs verts, rollup cohérent avec le comptage manuel des events
rollback: UPDATE job_definitions SET enabled=false WHERE code='daily_events_rollup';
source: EXECUTION_ORDER 0a, FINDINGS T2, spec WR §3.2 (prototype curseurs)
prompt_codex: « Brancher le job daily_events_rollup (enabled=true) ; smoke : run manuel →
  job_runs completed ; consigner date+obs au 76_ACTIVATION_ROADMAP §journal. »
observations: —
```

```
id: ACT-VLT-05    nom_fr: Pression financière 0-100 + explication (« Voir pourquoi »)
domaine: vault    classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: flag config vault_pressure_enabled=true (endpoint GET pressure répond 501
  tant que false) — flag à prévoir au merge de la mini-passe Vault
prerequis_activation: []  (V1 dégradée : inputs wallet manuel + upcoming minimale — Q17 ;
  version exacte après V3)
protocole_terrain: jauge 0-100 + label + facteurs explicables, lue chaque matin ; observer
  2-3 j (lecture) puis confronter au ressenti réel (R7)
critere_succes: le score et son explication correspondent à la réalité financière perçue
  sur 3 jours ; échelle 0-100 confirmée (Q4)
rollback: vault_pressure_enabled=false
source: doc 11 (formule canonique), GAP_vault gap n°4, F1-17
prompt_codex: « Activer vault_pressure_enabled ; smoke : GET pressure → score+label+
  facteurs sur fixtures ; consigner au journal. »
observations: PAS un event (doc 77) ; n'entre pas dans la sélection quotidienne (Q7)
```

```
id: ACT-SYS-07    nom_fr: Canal de notifications produit — première notification réelle
domaine: system   classe: notifiant   echelon_audace: 3   statut: NOT_CODED
bascule_exacte: flag notifications_enabled=true + config du canal retenu (Q3/Q18) ;
  tant que false : notify() écrit en table notifications sans envoi (pattern PATCH P-4)
prerequis_activation: [ACT-SYS-06]  (le premier émetteur = un job runner)
protocole_terrain: table notifications (statut lu/ack) + réception réelle sur le canal ;
  observer 7 j — délai de réception, zéro doublon, zéro notification fantôme
critere_succes: ≥1 notification utile reçue et ack ; zéro envoi non sollicité
rollback: notifications_enabled=false (les notifications restent en table, non envoyées)
source: FINDINGS T1, EXECUTION_ORDER 0b, Q3
prompt_codex: « Configurer le canal (Q18) + notifications_enabled=true ; smoke : notify()
  de test reçue+ack ; consigner au journal. »
observations: ne JAMAIS confondre avec le canal Telegram du bot de build (F1-11 doublons)
```

```
id: ACT-PTH-02    nom_fr: Fenêtres de prière (MAWAQIT + cache 30 j + fallback calculé)
domaine: path     classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: UPDATE job_definitions SET enabled=true WHERE code='mawaqit_refresh_0300';
  + flag prayer_windows_enabled=true (endpoint de lecture)
prerequis_activation: [ACT-SYS-06]  (le refresh 03:00 est un job runner)
protocole_terrain: les 5 fenêtres du jour affichées/servies ; observer 2-3 j — exactitude
  vs mosquée de référence (catégorie « déterministe qui doit être EXACT »)
critere_succes: heures exactes 3 jours de suite (MAWAQIT), fallback correct si API absente
rollback: prayer_windows_enabled=false + job disabled
source: doc 41 §6/§14/§20 (path_calculated_prayer_times, path_mawaqit_cache), F1-16,
  N8N_INVENTORY §B (refresh 03:00), Q19
prompt_codex: « Activer le job mawaqit_refresh + le flag ; smoke : GET fenêtres du jour =
  source MAWAQIT ; consigner au journal. »
observations: consommé plus tard par Daily G4 (ACT-DLY-10, Q6) et le HUD Vector (doc 55)
```
