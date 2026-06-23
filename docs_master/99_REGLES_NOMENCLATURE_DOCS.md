# Règles de nomenclature docs_master — Référence

> Document de référence pour l'organisation et le nommage des docs. Objectif :
> éliminer définitivement les collisions de numéros et la confusion archi vs
> features futures. Décidé après l'audit de cohérence du corpus.

---

## 1. Deux familles de documents

### Famille ARCHITECTURE (existant / acté)
- Décrit le système **actuel ou en cours d'implémentation** : vision, schéma,
  contrats, règles, logique des modules, déploiement, workflows.
- **Nomenclature : séquence numérique `NN_NOM.md`** (00 à 58 et au-delà).
- **On NE renomme PAS l'existant.** La séquence 00-58 reste telle quelle.
- Raison : ~700 références croisées entre docs. Renommer = risque élevé pour
  gain faible. La séquence numérique actuelle est stable et fonctionne.
- Un doc **sans préfixe** EST un doc d'architecture (pas besoin de préfixe `A`).

### Famille FEATURES FUTURES (réflexion / non implémenté)
- Décrit des features **pas encore implémentées**, documentées pour plus tard
  (souvent marquées V3/V4/V5/V7).
- **Nomenclature : préfixe `F` → `FNN_NOM.md`** (F01, F02, …).
- Espace séparé = **zéro collision possible** avec l'architecture.

---

## 2. Règle anti-collision (la cause racine éliminée)

**La cause des collisions passées (43, 45)** : mélange archi + features futures
dans la même séquence numérique, créés en parallèle sur deux machines.

**La règle simple désormais :**
- Une feature future ne prend JAMAIS un numéro de la séquence archi.
- Elle prend le prochain `FNN` disponible.
- Un numéro = un seul document vivant.

---

## 3. Règle de versionnement (fini les `_v2`)

- Quand un doc évolue, on **écrase le fichier** (même nom). Git garde
  l'historique — pas besoin de `_v2` qui traîne à côté.
- Si un doc est remplacé par d'autres, marquer l'ancien **`DEPRECATED`** en tête
  avec renvoi vers les remplaçants (bonne pratique déjà utilisée pour les docs
  02 et 03).
- Interdit : garder deux fichiers actifs pour le même contenu.

---

## 4. Migration progressive (optionnelle, plus tard)

- Si un jour un doc « archi » s'avère être en réalité une feature future, on peut
  le basculer en `F` **un par un**, proprement, en mettant à jour ses références.
- Pas d'opération de masse. Pas d'urgence. Le système marche sans ça.

---

## 5. Attribution des features futures (état au moment de l'audit)

Documents identifiés comme features futures → à mettre en `F` :

| Nouveau nom | Origine / sujet |
|---|---|
| `F01_USER_OBJECTIVES` | ex-`45_USER_OBJECTIVES_FEATURE` (collision 45 résolue) |
| `F02_GENERATEUR_DEVIS` | générateur de devis VTC intelligent |
| `F03_SCANNER_COMPOSITION` | scan composition produit (Pulse) |
| `F04_DEFI_RELIGIEUX` | défi religieux quotidien (Pulse/Path) |
| `F05_ENTRAINEMENT_MENTAL` | module entraînement mental (Pulse) |
| `F06_DOSSIER_PROJET` | dossier projet enrichi (Imperium) |
| `F07_VIDEO_VTC` | enregistrement vidéo sessions VTC (V7) |
| `F08_DOSSIER_MEDICAL` | dossier médical + fiche urgence (Pulse) |
| `F09_KILL_SWITCH` | kill switch / verrouillage d'urgence |
| `F10_TOPOLOGIE_INFRA` | topologie infrastructure physique (référence) |

> Note : `F10_TOPOLOGIE_INFRA` est une référence d'infra plutôt qu'une feature,
> mais elle décrit une cible non encore en place → rangée avec les futures pour
> l'instant. À reclasser en archi le jour où la topologie est en place.

> Les numéros `F02`-`F10` correspondent aux 9 specs documentées lors de la
> session du jour. L'ordre est indicatif, ajustable.

---

## 6. Décisions connexes prises en même temps

- **Embedding V1 = qwen3-embedding:8b local** (décision tranchée) : cohérent avec la
  philosophie privacy (données ne sortent pas vers OpenAI). ~2 Go RAM à héberger
  (machine orchestrateur ou NAS). → **Aligner tous les docs** : corriger le
  doc 38 qui déclarait OpenAI cloud en V1 default. qwen3-embedding:8b (local, dim 1024) devient le défaut V1.
- **Doc 43** : le `_v2` devient le `43` officiel (sur-ensemble de l'ancien),
  ancien supprimé.
- **Doc 45** : `N8N_RESPONSIBILITY_MATRIX` reste `45` ; `USER_OBJECTIVES` part
  en `F01`.
- **Fichiers corrompus** (`18_...vlrGnhQr`, `52_AI_DECISIO`) : supprimés.
- **Source de vérité** : le dossier Windows (61 fichiers) → écrase la Tower →
  push GitHub.

---

## 7. Récapitulatif de la règle, en une phrase

**Architecture = numéros (inchangés). Features futures = préfixe F. Un numéro =
un doc vivant. Une évolution écrase le fichier. Pas de doublon actif.**

## 8. Grande passe nomenclature par rôle (décidée, à exécuter quand la doc est stable)

PRINCIPE : à terme, les docs de logique nomment le RÔLE du modèle, jamais le fournisseur
ni la version. Exemples : "high reasoning cloud model", "health cloud model",
"vision/OCR service", "transcription service", "fast local model". Un doc propriétaire
unique mappe rôle → modèle concret → version, et porte les critères de sélection.

JUSTIFICATION : dans cet écosystème, le modèle est une dépendance enfichable (clé API +
prompt). Nommer le rôle (stable) plutôt que le fournisseur (volatil) reflète la réalité
et survit aux changements de modèle. Évite la panade déjà vécue (Opus 4.7 périmé dispersé
dans ~21 docs).

GARDE-FOUS (décidés) :
1. Liste de rôles PETITE, GÉNÉRALISTE (~6, alignés sur les modèles réellement
   utilisés : local, Sonnet, Opus, GPT, OCR local, embedding local). On ne crée pas de
   rôle pour un gain marginal (un généraliste à 97% vaut mieux qu'un spécialiste à 97,6%
   à gérer). Garde-fou d'ajout : exposer le besoin à une autre IA avant d'ajouter un
   rôle, pour vérifier qu'on ne peut pas le couvrir par croisement des rôles existants.
2. CRITÈRES DE SÉLECTION (ex. santé = garanties RGPD/UE) attachés au RÔLE chez le doc
   propriétaire, pas au nom du fournisseur. La garantie persiste ainsi au changement de
   modèle.
3. TIMING : à exécuter quand la doc est STABLE (= liste des incohérences de fond traitée).
   Sinon cible mouvante. Sûr car personne ne code le backend (attente des cartes GPU) et
   personne d'autre ne touche la doc.

MÉTHODE D'EXÉCUTION : grande passe via l'orchestrateur, 3 docs à la fois, même prompt
(~30 passes). En un seul passage par doc : retirer les versions périmées (Opus 4.7,
bge-m3, Qwen 2.5, gemini-2.5-pro, whisper-large-v3, Sonnet 4.6...), généraliser les
mentions OCR/transcription restantes, ET brancher les renvois vers le doc 72 (chatbot)
partout où il est mentionné. Le doc 43 (noms périmés dans la table de coûts) entre dans
cette passe.

NE PAS CONFONDRE avec : la généralisation OCR/transcription déjà faite (docs 40-65,
37 renommé), ni les corrections de logique déjà faites (doc 50 : vectorisation du corpus
religieux retirée). Ces chantiers-là sont distincts et terminés.
