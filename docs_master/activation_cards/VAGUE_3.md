# VAGUE 3 — Vault écritures (mini-passe Vault déterministe)

**Composition** : ACT-VLT-02, ACT-VLT-03, ACT-VLT-04, ACT-VLT-07. Toutes déterministes,
zéro GPU (GAP_vault). Elles rendent la pression V1 EXACTE. Durée : 3-7 j.

```
id: ACT-VLT-02    nom_fr: Deux livres business/personnel sur le ledger
domaine: vault    classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: déploiement du champ book obligatoire sur POST /api/imperium/vault/
  transactions (+ backfill des lignes existantes, décision de classement à consigner)
prerequis_activation: []
protocole_terrain: chaque transaction saisie porte son livre ; totaux séparés
  business/personnel sur la semaine ; 3-7 j de saisies réelles
critere_succes: totaux par livre cohérents avec la réalité ; aucune transaction sans livre
rollback: le champ reste, l'API cesse de l'exiger (revert du required) — pas de perte
source: GAP_vault gap n°1, doc 42 §36-82 (Two-Book Architecture)
prompt_codex: « Rendre book obligatoire ; smoke : 1 transaction par livre + totaux ;
  consigner. »
observations: prérequis du profit hebdo (ACT-VLT-09) et de la sadaqa (ACT-VLT-10)
```

```
id: ACT-VLT-03    nom_fr: Wallet snapshots manuels cash/bank/crypto
domaine: vault    classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: déploiement endpoint POST wallet-snapshots (+ lecture dernier snapshot)
prerequis_activation: []
protocole_terrain: 1 snapshot manuel saisi ; le total wallet apparaît au dashboard et
  entre dans la pression ; 3-7 j
critere_succes: total wallet = réalité déclarée ; la pression consomme le dernier snapshot
rollback: endpoint désactivé (données conservées)
source: GAP_vault gap n°2, doc 42 §86-104/§231-241
prompt_codex: « Activer wallet-snapshots ; smoke : POST + lecture + pression recalculée ;
  consigner. »
observations: sync bancaire/crypto auto = V2 explicite (hors roadmap)
```

```
id: ACT-VLT-04    nom_fr: Dépenses récurrentes + upcoming expenses (CRUD + échéances)
domaine: vault    classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: déploiement CRUD obligations récurrentes + upcoming (pending/paid/overdue)
prerequis_activation: []
protocole_terrain: liste réelle saisie (loyer, assurance…) ; statuts vivent sur 7 j ;
  la pression lit les obligations dues dans la fenêtre
critere_succes: la liste = source de vérité (doc 11) ; overdue détecté correctement
rollback: CRUD gelé en lecture seule (données conservées)
source: GAP_vault gap n°3, doc 11 §Recurring-Expenses, doc 42 §300-319
prompt_codex: « Activer le CRUD ; smoke : 1 obligation → upcoming généré → paid ;
  consigner. »
observations: auto-détection email = V2 ; les ALERTES = ACT-VLT-08 (V4, notifiant)
```

```
id: ACT-VLT-07    nom_fr: Corrections manuelles de la pression (postponed/handled/exceptional)
domaine: vault    classe: det_ecriture   echelon_audace: 2   statut: NOT_CODED
bascule_exacte: déploiement endpoints de correction (events append-only + recalcul)
prerequis_activation: [ACT-VLT-04, ACT-VLT-05]
protocole_terrain: 1 correction réelle (ex. dépense reportée) → la pression se recalcule
  et l'explication AFFICHE la correction sans effacer l'historique ; 3-7 j
critere_succes: recalcul immédiat + trace append-only + explication honnête
rollback: endpoints désactivés (corrections passées conservées)
source: doc 11 §433-449, GAP_vault gap n°6
prompt_codex: « Activer les corrections ; smoke : postponed → score recalculé + trace ;
  consigner. »
observations: —
```
