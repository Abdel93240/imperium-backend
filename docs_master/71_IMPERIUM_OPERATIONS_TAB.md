# 71 - Imperium Operations Tab (Projets + Routines) — V1 base

> ⚠️ **NOM PROVISOIRE : "Operations".** L'utilisateur souhaite rebaptiser cet
> onglet (pistes : Direction, QG, Commandement, Stratégie, Pilotage...). Le nom
> final reste à fixer. Tout le doc utilise "Operations" comme placeholder.
>
> Ce document décrit la **base V1** de l'onglet. Son enrichissement futur (dossier
> projet riche, espace de travail, médias) est spécifié séparément dans
> `F06_DOSSIER_PROJET.md` et NE fait PAS partie de la V1.

---

## 1. Purpose

L'onglet **Operations** est le **2ᵉ écran top-level** d'Imperium (après le
Dashboard). C'est là que l'utilisateur gère la matière première de son système :
ses **projets** et ses **routines**.

Rôle dans le core loop (doc 00) : `Projects + Routines + Priorities → arbitration
→ Current Mission`. Les projets et routines saisis ici sont ce à partir de quoi
**Imperium génère les missions**. 

> **Distinction cruciale :** cet écran gère des **PROJETS**, pas des missions.
> Les missions sont générées par Imperium à partir des projets, des routines, des
> priorités et du contexte. L'utilisateur ne crée pas de missions ici ; il crée
> des projets.

Route ID : `IMP.OPERATIONS.MAIN` (provisoire, à figer avec le nom final).
Type : Top-level route. Path : `imperium/operations` (provisoire).

---

## 2. Layout (tablette, paysage)

```text
┌──────────────────────────────────────────────┬─────────────────┐
│  PARTIE GAUCHE (~2/3) — PROJETS               │ PARTIE DROITE   │
│                                               │ (~1/3) ROUTINES │
│  ┌─────────────────────────────────────────┐ │                 │
│  │ Fenêtre 1 — PROJET ACTIF n°1 (principal) │ │  Liste des      │
│  │ (la plus grande, mise en avant)          │ │  routines       │
│  └─────────────────────────────────────────┘ │  quotidiennes   │
│  ┌─────────────────────────────────────────┐ │                 │
│  │ Fenêtre 2 — PROJET ACTIF n°2 (secondaire)│ │  - routine A ☐  │
│  └─────────────────────────────────────────┘ │  - routine B ☐  │
│  ┌─────────────────────────────────────────┐ │  - routine C ☐  │
│  │ Fenêtre 3 — LISTE des projets NON-ACTIFS │ │  ...            │
│  │ (ceux entrés par l'user, en attente)     │ │                 │
│  └─────────────────────────────────────────┘ │                 │
│                                               │                 │
│  [ Bouton MODIFIER ]                          │                 │
└──────────────────────────────────────────────┴─────────────────┘
        séparateur vertical (pas une vraie fenêtre flottante)
```

Le séparateur partage l'écran ~2/3 gauche (projets) / ~1/3 droite (routines).
Ce n'est pas un panneau flottant : c'est une division fixe de la surface.

---

## 3. Partie gauche — Projets

### 3.1 Les deux projets actifs (fenêtres 1 et 2)

```text
V1 RULE: exactement 2 projets actifs affichés.
  - Fenêtre 1 = projet actif n°1 (PRINCIPAL) — la plus grande, la plus visible.
  - Fenêtre 2 = projet actif n°2 (SECONDAIRE).

Le nombre 2 est FIXÉ en V1.
Versions suivantes : nombre de projets actifs configurable dans les réglages.
```

Chaque fenêtre de projet actif affiche le projet et son contexte de base
(titre, et les éléments de base déjà documentés du projet ; l'enrichissement
riche = F06, hors V1).

### 3.2 Fenêtre 3 — Liste des projets non-actifs

```text
Affiche UNIQUEMENT les projets NON-ACTIFS (en suspens).
Les 2 projets actifs ne sont PAS répétés ici (ils sont déjà en fenêtres 1 et 2).
Ce sont les projets entrés par l'utilisateur mais pas (encore) activés.
```

### 3.3 Bouton "Modifier"

Sous les fenêtres projets. Au clic, ouvre les actions de gestion des projets :

| Action | Effet |
|---|---|
| Ajouter un projet | Crée un nouveau projet. |
| Supprimer un projet | Retire un projet. |
| Activer un projet | Le passe dans les actifs (dans la limite V1 = 2 actifs). |
| Désactiver un projet | Le renvoie dans la liste des non-actifs (fenêtre 3). |
| Modifier l'ordre / priorité | Bascule prioritaire ↔ secondaire (n°1 ↔ n°2). |

Note V1 : avec 2 slots actifs, activer un 3ᵉ projet implique d'en désactiver un
(ou un choix utilisateur explicite). Comportement exact de dépassement à
préciser à l'implémentation.

---

## 4. Partie droite — Routines

```text
V1 = liste SIMPLE.
  - L'utilisateur saisit les choses à faire obligatoirement, tous les jours,
    de façon redondante.
  - Format V1 : texte + coche quotidienne (fait / pas fait).
  - Pas d'horaires, pas de fréquences complexes en V1 (réservé aux versions
    suivantes).
```

Les routines alimentent l'arbitrage d'Imperium (elles font partie du core loop),
mais leur affichage V1 reste une liste cochable simple.

> Référence : `01_SIGNAL_VARIABLES_DICTIONARY.md` mentionne "Routines managed in
> Operations" — c'est cet écran. (Le `routine_id` y est déjà défini.)

---

## 5. Création de projet (V1)

Deux voies, **également valides en V1** :

```text
1. Via le CHATBOT (Conversation-Driven Project Management — déjà acté) :
   on discute avec le chatbot, les décisions concrètes sont détectées et
   viennent créer/modifier le projet, AVEC validation utilisateur, stockage en
   vector memory pour que l'IA apprenne la façon de penser de l'utilisateur.
   Exemple validé : "châssis Iveco Daily allongé" décidé avec GPT → ajouté comme
   étape du projet camping-car, avec la raison + le lien vers la conversation.

2. Via SAISIE MANUELLE (bouton Modifier → Ajouter un projet).
```

Les deux mécanismes coexistent. La validation utilisateur reste requise avant
qu'une modification issue du chatbot devienne canonique (cohérent avec la règle
projet-wide "rien de canonique sans aval").

---

## 6. Authority Boundary

- Le backend reste la source de vérité pour les projets, leur état
  (actif/non-actif), leur ordre, et les routines.
- Le chatbot propose des changements ; l'utilisateur valide ; le backend écrit.
- Les missions ne sont JAMAIS créées sur cet écran : elles sont générées par
  Imperium en aval, à partir des projets/routines/priorités/contexte.

---

## 7. États (V1)

| État | UI |
|---|---|
| Loading | Skeleton des 3 fenêtres projets + liste routines. |
| Empty | Aucun projet : CTA "Ajouter un projet" ; routines vides : invite à saisir. |
| Ready | 2 projets actifs + liste non-actifs + routines cochables. |
| Editing | Bouton Modifier actif : actions add/delete/activate/reorder. |
| Error | Échec lecture/écriture projet ou routine, avec retry. |
| Offline | Lecture cache, modifications en attente de sync (bannière). |
| Conflict | Conflit serveur (ex. ordre modifié ailleurs) → diff/validation. |

---

## 8. Données (indicatif, V1 — à aligner avec le schéma existant)

```sql
-- Projets (le concept existe déjà dans la vision/priorités ; à formaliser)
projects:
  id, user_id, title, description,
  status (active | inactive),
  active_rank (1 = principal, 2 = secondaire, NULL si non-actif),
  created_at, source (chatbot | manual)

-- Routines quotidiennes (routine_id déjà au dictionnaire doc 01)
routines:
  id (routine_id), user_id, label, active, created_at

routine_daily_checks:
  id, routine_id, user_id, date, done (bool), checked_at
```

> À réconcilier avec `05_DATABASE_SCHEMA.md` (vérifier si des tables projects /
> routines existent déjà avant d'en créer).

---

## 9. Liens avec le reste du système

- **Core loop (doc 00)** : projets + routines + priorités → arbitrage → mission.
- **Chatbot (doc 43 §8)** : voie principale de création/modification de projet.
- **Priorités utilisateur (doc 01, `user_priority_order`)** : "Project" est une
  des priorités de l'utilisateur ; l'ordre influe sur l'arbitrage.
- **Dashboard** : la mission active (générée à partir d'ici) s'affiche sur le
  Dashboard, pas sur cet écran.
- **F06 (futur)** : enrichit le détail d'un projet en dossier riche (espace de
  travail, médias, contexte vivant). Hors V1.

---

## 10. Hors V1 (renvoi)

- Nombre de projets actifs configurable (>2).
- Routines avec horaires/fréquences avancées.
- Dossier projet riche (F06).
- Nom final de l'onglet (à fixer).

---

## 11. Points à trancher (utilisateur)

- **Nom final** de l'onglet (remplacer "Operations").
- Route ID / path définitifs.
- Comportement exact quand on active un 3ᵉ projet alors que 2 slots sont pleins.
- Confirmation du modèle de données projets/routines vs schéma existant (doc 05).

---

## 12. References

- `00_VISION_GLOBALE.md` — core loop (Projects + Routines + Priorities).
- `01_SIGNAL_VARIABLES_DICTIONARY.md` — `routine_id`, `user_priority_order`.
- `05_DATABASE_SCHEMA.md` — schéma à réconcilier.
- `43_IMPERIUM_LOGIC_DETAIL.md` — chatbot, génération de missions, arbitrage.
- `F06_DOSSIER_PROJET.md` — enrichissement futur du dossier projet.
- `99_AUDIT_COHERENCE_FRONTEND.md` — décision : Operations = 2ᵉ top-level.

---

**Document version:** 1.0 (spec de base V1 — nom d'onglet provisoire)
**Statut :** base V1 de l'onglet Operations ; enrichissement = F06 (futur)
**Last updated:** 2026-06-09
