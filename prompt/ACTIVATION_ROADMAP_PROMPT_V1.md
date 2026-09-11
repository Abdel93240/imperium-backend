# GÉNÉRATION — FEUILLE DE ROUTE D'ACTIVATION (V1/V2/V3)

> **Prompt destiné à Claude Code (Fable 5)** sur Tower. Mission : inventorier TOUTES les
> features activables de l'écosystème (specs + code) et produire la feuille de route
> d'activation par vagues, avec une fiche d'activation par feature. Ce prompt n'écrit AUCUN
> code : ses seuls livrables sont les documents du §5. Il est exécutable dès maintenant
> (les features non codées reçoivent le statut NOT_CODED) et le journal produit VIVRA —
> mis à jour à chaque merge de passe puis à chaque bascule.

---

## 1. LA DOCTRINE (gravée par l'utilisateur — chaque vague et chaque fiche la respecte)

R1 — Coder ≠ brancher. Les passes livrent éteint ; l'activation est un acte séparé,
journalisé, réversible. Un merge n'allume rien.
R2 — L'unité d'activation est la FEATURE OBSERVABLE (effet constatable en une phrase),
pas le module.
R3 — Chaque feature a sa fiche complète (§4).
R4 — Lots de 1 à 5 features, un domaine à la fois ; règle d'attribution : jamais deux
features aux effets confondables dans la même fenêtre d'observation.
R5 — Fenêtres par classe : déterministe-lecture 2-3 j ; déterministe-écriture/notifiant
3-7 j ; IA locale : dry-run → shadow → advisory, advisory sur accord mesuré uniquement.
R6 — Échelle d'audace : lecture < écriture < notifiant < proposant < apprenant.
Aucun saut d'échelon.
R7 — Le terrain juge : critère terrain distinct des tests de merge ; un rollback est une
donnée consignée, pas un échec.
R8 — Le journal (§5.1) est canonique : premier document lu par tout audit futur.
R9 — V1 = la boucle vitale : la plus petite chaîne bout-en-bout utile dès la semaine 1.

## 2. CORPUS À LIRE

`docs_master/78_TOOLBOX_CATALOG.md` (ou draft si non promu) ; les 7 specs (Socle, Vault,
Pulse, WR, Daily, Vector + emplacement fourni) ; `audits/*ARCHITECTURE_DIGEST*` ;
`gap_analysis_v1/toolbox/` ; le code réel : flags de config, seeds `job_definitions`,
tables de seeds des specs (procédures Pulse, règles sentinelle, coups légaux, red flags,
signaux, slots ai_slot_transition, workflows/crons listés).

## 3. CE QUI COMPTE COMME FEATURE ACTIVABLE (inventaire exhaustif)

Chaque : flag de config ; job/cron ; abonnement event ; signal (par signal ou par famille
cohérente) ; règle sentinelle ; procédure (P1-P10 Pulse, workers W1-W5, phases WR) ; slot
IA (chaque ligne ai_slot_transition, avec ses états dry-run/shadow/advisory comme
activations DISTINCTES) ; coup légal ; règle rouge ; canal de notification ; endpoint
notifiant/proposant ; modèle servi (32B, embeddings, CatBoost…) ; bascule de mode
(shadow→advisory Vector, décroissance d'audit). Regrouper ce qui n'est observable
qu'ensemble ; ne JAMAIS regrouper au-delà de l'observable (R2). Estimation attendue :
60-120 fiches. Chaque feature est sourcée (spec §, fichier) — zéro invention.

## 4. LA FICHE D'ACTIVATION (format normatif, une par feature)

```
id: ACT-<domaine>-<nn>        nom_fr: …
domaine: pulse|wr|daily|vector|vault|path|system
classe: det_lecture|det_ecriture|notifiant|proposant|ia_dryrun|ia_shadow|ia_advisory|apprenant
echelon_audace: 1-5 (R6)      statut: NOT_CODED|OFF|SHADOW|ON|ROLLED_BACK
bascule_exacte: flag/job/ligne SQL à changer (copiable)
prerequis_activation: [ACT-ids] (≠ dépendances de code ; ce qui doit être ON avant)
protocole_terrain: quoi observer, OÙ (table/notification/écran), pendant N jours (R5)
critere_succes: mesurable, une phrase
rollback: la commande exacte
prompt_codex: squelette rempli (brancher → smoke → consigner au journal)
observations: (vide — rempli à l'usage)
```

## 5. LIVRABLES

1. `docs_master/<prochain numéro libre>_ACTIVATION_ROADMAP.md` — le journal canonique :
   tableau une-ligne-par-feature (id, nom, domaine, classe, statut, vague, dates,
   observations) + la définition des vagues. Budget : ≤ 400 lignes.
2. `docs_master/activation_cards/VAGUE_<n>.md` — les fiches complètes, groupées par vague.
3. **Les vagues** : V1 = la boucle vitale (R9 — proposer et JUSTIFIER la composition ;
   point de départ suggéré à challenger : events consommés + pression Vault + notification
   Telegram + session/mission réelles + fenêtres de prière) ; puis V2, V3… en lots R4,
   chaque vague avec ses prérequis et sa durée d'observation cumulée estimée. Les états
   IA (dry-run/shadow/advisory) apparaissent comme features distinctes dans des vagues
   distinctes (R5/R6).
4. Une section « conflits détectés » : toute feature dont la spec suppose l'activation
   implicite au merge (violation R1) → à lister, avec le patch d'une ligne proposé.
5. QUESTIONS UTILISATEUR numérotées pour tout arbitrage de composition de vague non
   déductible des règles.

## 6. INTERDITS

Aucun code modifié ; aucune activation effectuée ; aucune feature inventée sans source ;
pas de vague > 5 features ; pas de regroupement qui casse l'attribution (R4) ; git status
propre hors livrables.
