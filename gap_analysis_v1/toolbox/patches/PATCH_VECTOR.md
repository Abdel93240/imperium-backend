# PATCH_VECTOR — Amendements d'étape 0 pour VTC_ASSISTANT_SPEC_V1

Source : audit toolbox 2026-07-10 (`gap_analysis_v1/toolbox/`). Amendements d'étape 0 uniquement.

## V-0. Lecture obligatoire à l'étape 0
Ajouter aux lectures §0 : `TOOLBOX_CATALOG_DRAFT.md` + `TOOLBOX_FINDINGS.md`.

## V-1. Cible A introuvable sur Tower (Q1 — bloquant étape 0)
`vtc-companion-app` n'existe pas sur le disque de Tower (vérifié : /opt, /home, /srv ;
`/opt/frontend-apps/imperium` = README seul). La spec le situe sur GitHub (Abd93240). Résoudre
Q1 (clonage + état CI) AVANT la passe ; le VTC_MAPPING.md « déposé dans les deux repos » en
dépend.

## V-2. Historique de courses : le STOP §0.2 est probablement réel
Aucune table VTC/rides n'existe dans les migrations 0001-0037 ni dans `backend/app/models/`
(INVENTAIRE_tables §4 « VTC/RIDES : aucune », revérifié). Les ~800 courses/mois d'historique
évoquées ne sont PAS dans `imperium_core` sous forme de tables rides. Pistes à vérifier à
l'étape 0 avant de déclencher le STOP : captures/exports Bolt hors base (NAS ? tablette ?),
`vault_transactions` (revenus VTC agrégés — insuffisant pour la matrice). Sans source localisée :
STOP et signaler (la matrice §3.5 et les labels de zones §4.5 n'ont pas de socle).

## V-3. `toolbox.travel` : renforcer l'interface Daily, ne pas construire un deuxième estimateur (confirme le pré-inventaire, précisé)
FINDINGS DBL-1. La passe Daily a posé `toolbox.travel.estimate(...)` (Google + plancher 1,3 +
cache, PATCH_DAILY D-2). Cette passe :
- §3.5/§4.1 : construit la matrice H3 + multiplicateurs live CÔTÉ TOWER comme NOUVELLE SOURCE de
  la même interface (le fallback Google devient le professeur §4.2) — signature inchangée, les
  consommateurs Daily ne bougent pas ;
- la tablette embarque son miroir local (inchangé, contrainte ≤50 ms hors-ligne) ;
- les utilitaires H3 (résolution, corridors, cellules tenues) vont dans le module geo partagé
  (FINDINGS T6), pas dans un utilitaire privé Vector — The Path en aura besoin (Q2).
Le §3.5/§4.1 de la spec reste normatif pour le CONTENU ; seul le POINT D'ANCRAGE change
(interface partagée au lieu de module privé).

## V-4. Usine WR et docket : présents si l'ordre est respecté
§0.3 : dans l'ordre Toolbox → Pulse → WR → Daily → Vector, `wr_docket_items` (ou son nom
canonique décidé en passe WR) et l'usine W4/W5 existent → brancher §4.8 directement, la « table
tampon + TODO » ne sert que si l'ordre change. Table events canonique = `events` (depth, 0036).
Paramètres versionnés = table partagée (PATCH_PULSE P-1).

## V-5. Registre de modèles : nommage généralisant (Q12)
§5 `vtc_model_versions` est déjà multi-`model_kind`. Si Q12 = oui (futur CatBoost routeur,
durées de mission apprises), nommer le registre `ml_model_versions` avec `domain` + `model_kind`
dès la création — coût zéro maintenant, renommage évité plus tard. Consigner dans VTC_MAPPING.md.

## V-6. OCR : trois profils, pas un
FINDINGS F1-05 / C-5. (a) ML Kit on-device = chemin critique (spec §3.3) ; (b) contre-lecture
nocturne P40 (§4.7) = pipeline Paddle du service OCR système (F10 §5-quater) ; (c) F10 prévoit
AUSSI la lecture par accessibilité Android AVANT OCR pour Bolt (lecture seule, jamais d'action).
Aligner la spec et F10 au moment du patch docs de fin de passe : soit intégrer la voie
accessibilité comme déclencheur/source de champs (avant OCR), soit la déprécier dans F10 —
pas deux vérités.

## V-7. Notifications
§3.9 (sollicitation capture surge), §4.8 (dérive) : consommer `toolbox.notifications`
(FINDINGS T1). Le garde-fou vitesse GPS > 5 km/h (inertie) reste côté app, inchangé.

## V-8. Builders = jobs runner
§4.1 : les builders de caches (5 min/60 min/hebdo/nocturne) et l'entraînement §4.4 sont des jobs
`toolbox.runner` (advisory locks pour éviter deux entraînements concurrents), pas des workflows
n8n ni des crons systèmes isolés.

## V-9. Events
§7 : émettre dans `events` (canonique). Les types `vtc.*` proposés au §7 devront suivre doc 77
(domaine générique `rides.*` déjà réservé au catalogue — `vtc` est un nom d'app, interdit par
D3). À traiter dans le patch doc 77 de fin de passe.
