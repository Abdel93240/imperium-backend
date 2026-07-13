# VAGUE 28 — La sélection du jour (Niveau 1)

**Composition** : ACT-SYS-08 (travel v0), ACT-DLY-04, ACT-DLY-06. « Ta prochaine
mission : X. » Durée : 2-3 j (lecture) — mais fenêtre réelle 7 j conseillée (premier
changement d'EXPÉRIENCE quotidienne).

```
id: ACT-SYS-08   nom_fr: toolbox.travel v0 (Google Directions × plancher 1,3, cache 2 h, fallback)
domaine: system   classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: flag travel_enabled=true + clé API configurée (sinon fallback
  distance/25 km/h ×1,3 marqué travel_source=fallback)
prerequis_activation: []
protocole_terrain: estimations comparées à la réalité sur trajets connus ; cache hit rate ;
  2-3 j
critere_succes: plancher 1,3 JAMAIS contourné (même si paramètre < 1,3 — codé dur) ;
  fallback marqué ; coût API contenu par le cache
rollback: travel_enabled=false (fallback ou porte G4 passante, loggée)
source: FINDINGS DBL-1, PATCH_DAILY D-2 (interface partagée services/travel/), spec Daily
  §5 « Trajet » ; Q2 (Path n'y touche pas tant que le fournisseur religieux n'est pas
  arbitré)
prompt_codex: « Activer travel ; smoke estimate() 3 trajets connus ; consigner. »
observations: la passe Vector RENFORCERA la source (matrice H3+fantôme) sans changer la
  signature (V-3) — bascule de source future à consigner
```

```
id: ACT-DLY-04   nom_fr: Sélection Niveau 1 (portes G1-G5 → obligatoire → score → départage trajet)
domaine: daily    classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: daily_selection_enabled=true (CF-5 : POST complete/{id} répond
  next_mission au lieu du comportement actuel)
prerequis_activation: [ACT-DLY-03, ACT-SYS-08, ACT-WR-18 (G1 lit le plan courant)]
protocole_terrain: chaque complétion → proposition <500 ms + daily_selection_log (porte
  bloquante par mission rejetée) ; G5 PASSANTE (stub loggé) tant que V29 non faite ;
  7 j de journées réelles
critere_succes: latence <500 ms ; zéro LLM sur le chemin nominal (spy) ; obligatoires
  d'abord (deadline bat le score) ; départage moindre trajet dans la bande de 15 % ;
  le log permet de rejouer chaque choix
rollback: daily_selection_enabled=false (une variable — retour au comportement actuel)
source: spec Daily §5/§6/§7, §14.6
critere_complementaire: la file reste INVISIBLE (GET queue = admin/debug seulement, UX gravée)
prompt_codex: « Activer la sélection ; smoke complétion fixture → next <500 ms + log ;
  consigner. »
observations: LA feature qui change la journée — observer les envies d'override (matière
  de V29)
```

```
id: ACT-DLY-06   nom_fr: Pull-forward (avancer la semaine quand le jour est bouclé)
domaine: daily    classe: det_lecture   echelon_audace: 1   statut: NOT_CODED
bascule_exacte: UPDATE parameters : df 'pullforward_enabled'=true (défaut seedé true —
  CF à corriger : seeder false, activer ici)
prerequis_activation: [ACT-DLY-04]
protocole_terrain: jour épuisé + ≥45 min → missions de la semaine proposées,
  pulled_forward=true au log ; sinon « Journée bouclée » (aucune mission inventée) ; 2-3 j
critere_succes: seuil respecté ; flag au log ; jamais d'invention
rollback: pullforward_enabled=false
source: spec Daily §7 (« défaut true — décision à valider » → validée par CETTE bascule)
prompt_codex: « Activer pull-forward ; smoke jour épuisé fixture ; consigner. »
observations: —
```
