# 99 - Audit de cohérence FRONTEND (volet 2)

> Suite de `99_AUDIT_COHERENCE_DOCS.md` (qui couvrait le corpus à 61 fichiers,
> avant la couche frontend). Ce volet couvre la **couche frontend** (docs 59-70),
> révélée par l'audit automatisé Claude Code du 2026-06-08 et par la revue
> utilisateur du même jour. Objectif : consigner les décisions AVANT de corriger,
> pour que les corrections Codex appliquent des choix tracés, pas improvisés.

---

## Verdict

La couche frontend (docs 59-69) est riche mais présente **un problème
structurant** (nomenclature d'écrans en collision) et **plusieurs trous** :
features réelles dont la spec de base manque, et désalignements entre docs. La
logique de fond reste saine ; il s'agit de cohérence et de complétude, pas de
contradiction profonde.

---

## A. DÉCISION STRUCTURANTE — Nomenclature des écrans

### A.1 Le problème
- Le doc 65 (`FRONTEND_SCREEN_SPEC`) et le doc 59 §12 (`SCREEN ARCHITECTURE
  MAPPING`) utilisent **tous deux des IDs `IMP-XX`**, mais pour des écrans
  DIFFÉRENTS. Exemple : `IMP-03` = Inbox (doc 65) **vs** Mission Outcome Form
  (doc 59). Collision sur quasiment tous les numéros sauf IMP-01.

### A.2 La décision (tranchée)
- **Les numéros `IMP-XX` sont ABANDONNÉS comme identifiants.** Ils sont ambigus
  par nature (un numéro ne porte pas de sens).
- **Les Route ID parlants font autorité** partout : `IMP.DASH.MAIN`,
  `IMP.CHAT.CONVERSATION`, `IMP.SETTINGS.CORE`, etc. Un Route ID ne peut désigner
  qu'un seul écran → zéro ambiguïté possible.
- Constat clé qui valide la décision : même quand les numéros divergent entre les
  deux docs, **les Route ID, eux, convergent** (les deux docs sont d'accord que
  Settings = `IMP.SETTINGS.CORE`, Dashboard = `IMP.DASH.MAIN`). La couche stable
  existe déjà ; on supprime juste la couche cassée (les numéros).

### A.3 Table de correspondance officielle (issue du doc 59 §12)

| Ancien n° (à abandonner) | Route ID (autorité) | Écran |
|---|---|---|
| IMP-01 | `IMP.DASH.MAIN` | Dashboard |
| IMP-02 | `IMP.MISSION.ACTIVE` | Mission active (→ module Dashboard, voir B) |
| IMP-02(59) | `IMP.CHECKIN.MORNING` | Morning Check-In Popup |
| IMP-03(59) | `IMP.MISSION.OUTCOME` | Mission Outcome Form |
| IMP-04(59) | `IMP.DAY.FINISH` | Day Finished Form |
| IMP-05(59) | `IMP.REPLAN.VALIDATE` | Replan Validation |
| IMP-06(59) | `IMP.MISSION.ADD_MANUAL` | Add Manual Mission |
| IMP-07 | `IMP.PLAN.HISTORY` | Plan History |
| IMP-08 | `IMP.CHAT.CONVERSATION` | Chatbot (→ fenêtre Dashboard, voir B) |
| IMP-09 | `IMP.DECISIONS.LOG` | Decisions Log |
| IMP-10 | `IMP.WR.LIST` | Weekly Review List |
| IMP-11 | `IMP.WR.READ_ONLY` | Weekly Review Read-only |
| IMP-12 | `IMP.WR.INTERACTIVE` | Weekly Review Interactive |
| IMP-13 | `IMP.SETTINGS.PRIORITIES` | Priority Rules Settings |
| IMP-14 / IMP-06(65) | `IMP.SETTINGS.CORE` | Settings (core) |

> Les `(59)` / `(65)` indiquent quel doc utilisait ce numéro. À terme, plus aucun
> numéro : seuls les Route ID subsistent.

---

## B. La VRAIE liste des écrans top-level Imperium V1

Décidée par l'utilisateur (la liste du doc 65 §9.1 était erronée).

**4 écrans top-level :**

| Écran | Route ID | Note |
|---|---|---|
| Dashboard | `IMP.DASH.MAIN` | Contient le module mission active, le chatbot docké, le widget mission, la bannière Weekly Review. |
| Projet | `IMP.PROJECT.*` (à fixer) | Onglet Projet. **Spec de base manquante** (voir C.1). Enrichi plus tard par F06. |
| History | `IMP.HISTORY.MAIN` | |
| Settings | `IMP.SETTINGS.CORE` | Contient l'action "Nourrir l'IA" (doc 70). |

**Ce qui N'EST PAS un écran top-level (et pourquoi) :**

- **Mission Active** (`IMP.MISSION.ACTIVE`) → c'est un **module du Dashboard**
  (le module principal, plus grand que les autres) + un **widget** d'accès rapide
  (pratique en conduite VTC). Le doc 65 §4 a tort d'en faire un top-level.
- **"Inbox"** (doc 65 §5, `IMP.INBOX.MAIN`) → **faux écran**. Le doc 65 a nommé
  "Inbox" ce qui est en réalité le **chatbot IA** (mal nommé ET mal placé en
  top-level). Le chatbot est une **fenêtre dockée du Dashboard**
  (`IMP.CHAT.CONVERSATION`, déjà bien décrit doc 59 §12.9 et doc 43 §8).
  → La section §5 "Inbox" du doc 65 doit être **supprimée**.
- **Weekly Review** → **n'est pas un top-level**. C'est une **bannière + fenêtre
  événementielle du Dashboard** (voir C.2), déclenchée une fois par semaine. Le
  doc 65 a tort de la lister en top-level.
- **"Nourrir l'IA"** → action dans **Paramètres → IA** de chaque app (doc 70),
  pas un écran top-level.

---

## C. Trous : features réelles à spec de base manquante

### C.1 Onglet Projet — spec de base absente
- **Statut** : écran top-level V1 CONFIRMÉ (présent dans la vision doc 00, dans
  les priorités utilisateur doc 01, confirmé par l'utilisateur).
- **Problème** : sa **logique de base n'a aucun doc dédié**. Le concept est
  éparpillé (vision 00, mentions doc 43) et F06 décrit surtout son
  **enrichissement futur**, pas la base. F06 prétend que la base est "documentée
  jusqu'à ~doc 50-51", mais c'est **inexact** (50 = Path Dars V3, 51 = Future
  Calendar V3, sans rapport).
- **Acquis réel** (d'après F06, à formaliser) : hiérarchie de projets décidée par
  l'utilisateur ; création surtout via chatbot ; Conversation-Driven Project
  Management (les décisions détectées en conversation modifient le projet, avec
  validation, stockage vector). Exemple validé : "châssis Iveco Daily allongé"
  ajouté comme étape du projet camping-car.
- **Action** : créer un **doc de base dédié pour l'onglet Projet** (même démarche
  que le doc 70 pour Nourrir l'IA). F06 reste l'enrichissement futur.

### C.2 Weekly Review — bannière "fait" et cooldown non documentés
- **Acquis documenté** : le process Weekly Review lui-même est bien spécifié
  (docs 32, 47, etc.). Déclencheur par défaut : **mardi 20h, configurable** dans
  les paramètres.
- **Manque** :
  1. La **bannière de lancement** s'affiche en haut, au-dessus de la mission
     active : "Revue de la semaine à effectuer". Clic → lance le process.
  2. Une fois la WR effectuée, cette bannière se **transforme en "Weekly Review
     fait"** — ce remplacement n'est pas documenté.
  3. Un **cooldown** (quelques secondes à une minute) après quoi la bannière
     disparaît, avec un message "tu peux retrouver ta Weekly Review dans History".
     Comportement pressenti par l'utilisateur, **non encore décidé/documenté**.
- **Action** : documenter ce cycle de bannière (lancement → fait → cooldown →
  disparition + renvoi History) dans le doc concerné (Dashboard / Weekly Review).

### C.3 Knowledge Inbox "Nourrir l'IA" — RÉSOLU
- Était le trou #2 de l'audit Claude Code (Inbox sous-spécifié). **Résolu** par
  le nouveau **doc 70** (`70_KNOWLEDGE_INBOX.md`). Action dans Paramètres → IA de
  chaque app, ingestion de documents → vectorisation globale, un seul cerveau,
  pas de tag d'app, validation utilisateur éditable. Distinct du scan ticket
  Vault et du feed médical Pulse.

---

## D. Autres trous de l'audit Claude Code (statut)

Les 15 trous remontés par l'audit automatisé, triés par catégorie et statut :

**Vrais conflits (tranchés) :**
- #1 Nomenclature IMP-XX → RÉSOLU par A (Route ID parlants).
- #7 Dashboard Quick Stats (doc 43 dit Prayer/Pressure/Discipline, doc 65 dit
  Weekly Progress) → à aligner ; Discipline streak retiré (gamification), donc
  Quick Stats = Prayer countdown + Pressure (+ Weekly Progress). À harmoniser.
- #13 Tab "Mon OS personnel" (doc 43 le mentionne, doc 59 l'exclut V1) → exclu
  V1 confirmé, simple signalement.

**Ambiguïtés "un ou deux assets" (à décider, impact génération) :**
- #9 Imperium emblem 48dp vs AI emblem 24dp → à trancher (1 marque ou 2 ?).
- #12 / #15 banners Decisions Log / Info réutilisés → probablement le même
  `Banner Info frame`, à confirmer.
- #5 set mood (Morning Check-In) → à créer/choisir (doc 43 dit emoji, doc 59
  interdit emoji comme icône).
- #10 pictogramme "decision" → à fixer.

**Sous-spécifications (à étoffer) :**
- #3 focus emblem, #4 hero ornament, #6 delta badge, #8 chatbot provider chips,
  #11 conflict illustration, #14 Day Finished hero → à préciser au fil de la
  spécification des écrans.

---

## E. Plan de correction (à exécuter via Codex, APRÈS validation de cet audit)

1. **Doc 65** :
   - Supprimer la section §5 "Inbox Screen" (faux écran = chatbot mal nommé).
   - Retirer "Mission Active" des écrans top-level (→ module Dashboard).
   - Retirer "Weekly Review" des écrans top-level (→ bannière/fenêtre Dashboard).
   - Ajouter "Projet" aux écrans top-level.
   - Mettre à jour le contrat de navigation §9.1 : top-level = Dashboard, Projet,
     History, Settings.
   - Remplacer les numéros IMP-XX par les Route ID parlants.
2. **Doc 59** : remplacer les numéros IMP-XX par les Route ID parlants (titres,
   références croisées de navigation, décisions produit §12.0).
3. **Nouveau doc** : spec de base de l'onglet Projet (C.1).
4. **Doc Dashboard/WR** : documenter le cycle de bannière Weekly Review (C.2).
5. **Doc 70** : installer dans docs_master (déjà rédigé).
6. Aligner Quick Stats (#7) et trancher les ambiguïtés d'assets (#9, #12, #15...)
   au fil de la spécification.

> Chaque étape = un diff relu avant commit. Ne pas tout faire d'un coup.

---

## F. Points à trancher par l'utilisateur (restants)

- Route ID exact de l'onglet Projet (`IMP.PROJECT.MAIN` ?).
- Comportement final de la bannière Weekly Review (cooldown : durée ? message ?).
- Imperium emblem vs AI emblem : une marque ou deux assets (#9) ?
- Set mood : Material Symbols ou assets custom (#5) ?

---

**Document version:** 1.0 (volet 2 — couche frontend)
**Statut :** audit consigné, corrections en attente de validation
**Last updated:** 2026-06-08
