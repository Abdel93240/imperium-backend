# 71 - Imperium Operations Tab (Projets + Routines) — V1 base

> **NOM FINAL : "Operations"** (libellé UI « Opérations ») — décision utilisateur 2026-10-15 : le renommage en "Pilotage" est abandonné.
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

Route ID : `IMP.OPERATIONS.MAIN` (définitif, décision utilisateur 2026-10-15).
Type : Top-level route. Path : `imperium/operations` (définitif).

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
RÈGLE DE REMONTÉE (à la complétion) :
  On vise TOUJOURS 2 projets actifs — pas seulement à l'affichage.
  Quand le projet actif n°1 est terminé :
    - le projet actif n°2 devient n°1 (principal) ;
    - le 1ᵉʳ projet non-actif (selon l'ordre utilisateur) est promu n°2 ;
    - il devient actif du seul fait d'entrer dans les 2 premiers slots.
  Exception — pile vide :
    s'il n'y a plus aucun projet non-actif à promouvoir, on reste à 1 actif
    (ou 0). C'est le SEUL cas où il y a moins de 2 actifs.
  Cette remontée est AUTOMATIQUE (déclenchée par la complétion d'un projet),
  distincte du dépassement manuel décrit en §3.3 (activer un 3ᵉ projet à la main).
```

Chaque fenêtre de projet actif affiche le projet et son contexte de base
(titre, et les éléments de base déjà documentés du projet ; l'enrichissement
riche = F06, hors V1).

« Progression indicative » (décision utilisateur 2026-10-16, maquette 08) :
`project_progress_percent` est ESTIMÉ PAR L'IA PENDANT LE WEEKLY REVIEW, dans
l'analyse de la section Imperium déjà prévue (doc 47 §11) — un champ de plus
dans cet appel, pas d'appel dédié, aucune escalade cloud propre à ce chiffre.
L'IA donne, pour chaque projet actif, un pourcentage 0-100 vers le résultat visé
et une phrase de justification (visible dans « Gérer les projets »). La barre ne
bouge donc qu'une fois par semaine ; avant la première WR d'un projet, elle est
masquée. Raison : chiffre indicatif, non utilisé par la planification ni le
score — il ne justifie pas d'appel IA à chaque mission terminée.

### 3.2 Fenêtre 3 — Liste des projets non-actifs

```text
Affiche UNIQUEMENT les projets NON-ACTIFS (en suspens).
Les 2 projets actifs ne sont PAS répétés ici (ils sont déjà en fenêtres 1 et 2).
Ce sont les projets entrés par l'utilisateur mais pas (encore) activés.
```

Chaque ligne porte un chevron › (décision utilisateur 2026-10-15) : la toucher ouvre
« Gérer les projets » (maquette 09) avec CE projet déplié (ses missions visibles, les
autres projets atténués).

### 3.3 Bouton "Modifier"

Sous les fenêtres projets. Au clic, ouvre les actions de gestion des projets :

| Action | Effet |
|---|---|
| Ajouter un projet | Crée un nouveau projet. |
| Supprimer un projet | Retire un projet. |
| Modifier l'ordre / priorité | Monte / descend un projet dans le classement. |

Note V1 — activation PAR LE CLASSEMENT (décision utilisateur 2026-10-15) : il n'y a
PAS de bouton Activer / Désactiver en V1. Les 2 premiers projets du classement sont
actifs (n°1 principal, n°2 secondaire), les suivants sont non actifs. Pour activer un
projet, l'utilisateur le remonte dans les 2 premières places ; celui qu'il dépasse
redescend en non actif. Libellé de la maquette : « Les deux premiers projets sont actifs ».
Versions suivantes : boutons Activer / Désactiver + fenêtre « choisir quel projet
actif désactiver » quand les slots sont pleins — seulement après avoir observé en V1
comment l'IA gère 2 projets actifs (et si le nombre d'actifs doit devenir réglable).

Note V1 (suppression) : toute suppression (projet, mission, routine) ouvre
une petite fenêtre de confirmation (`ImperiumAlertDialog`, doc 67 : aucune action
destructive sans confirmation) : « Supprimer <nom> ? » + Annuler / Supprimer.
Les priorités ne se suppriment pas (4 domaines fixes, doc 52 §3).

Effets d'une suppression — le passé est conservé (décision utilisateur 2026-10-16) :
- Projet : retiré d'Opérations. Ses missions non faites (backlog, prévues, standby)
  passent en `annulée` (raison « Projet supprimé ») et sortent du plan. Ses missions
  passées (faites, ratées) restent dans l'Historique avec le nom du projet figé.
  Texte : « Ses missions à venir seront annulées ; l'historique est conservé. »
- Routine : ne revient plus. Les coches passées restent dans l'Historique et dans le
  score des journées passées. Texte : « Elle ne sera plus planifiée ; l'historique
  est conservé. »
- Mission : seulement une mission non faite ; elle passe en `annulée`. Une mission
  terminée ne se supprime pas. Texte : « Elle sera retirée du plan. »
- Aucun recalcul des scores passés. La mémoire de l'IA dérivée d'un projet reste,
  sauf suppression explicite dans Nourrir l'IA (doc 72 §4).
Note V1 (complétion) : la promotion automatique à la complétion d'un projet actif
(cf. §3.1, règle de remontée) NE passe PAS par ce menu — elle est déclenchée par
le système, pas par l'utilisateur. Ce menu "Modifier" ne couvre que les actions
manuelles (ajouter / supprimer / réordonner).

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

Fréquence V1 (décision utilisateur 2026-10-15, maquette 12) : liste FERMÉE, sans
option « Autre » ni récurrence personnalisée — Chaque jour / Chaque semaine /
Toutes les 2 semaines / Chaque mois. L'aide « Exemples : deux fois par semaine… »
de la maquette est à retirer.

Les routines alimentent l'arbitrage d'Imperium (elles font partie du core loop),
mais leur affichage V1 reste une liste cochable simple.

### 4.1 Modèle et placement des routines (décision utilisateur 2026-10-16)

Remplace le « texte + coche quotidienne, pas de fréquences » ci-dessus : la
fréquence fermée et les champs de la maquette 12 sont V1.

```text
CHAMPS VISIBLES (formulaire maquette 12)
  name                 texte, obligatoire
  frequency            daily | weekly | biweekly | monthly
  estimated_minutes    entier, facultatif
  priority             low | medium | high  (aide l'IA à arbitrer un report)
  notes                texte, facultatif
  active               booléen

CHAMPS STOCKÉS, NON AFFICHÉS (posés seulement via le chatbot)
  pinned_weekday       1-7, NULL par défaut      (weekly / biweekly)
  pinned_month_day     1-31, NULL par défaut     (monthly ; 31 = dernier jour)
  pinned_time          heure locale, NULL par défaut (toutes fréquences)

PLACEMENT
  daily      : chaque journée opérationnelle (entre deux sommeils, doc 12).
  weekly / biweekly / monthly : à faire UNE fois dans la période ; l'IA
    choisit la journée (un jour léger) et l'heure dans le plan. La routine
    n'apparaît dans la liste du jour que la journée où elle est planifiée.
    Pas faite → l'IA la replace plus tard dans la même période.
    Période terminée sans la faire → comptée manquée, pas de report.
  Forçage : si l'utilisateur demande au chatbot un jour ou une heure précis
    (« l'entretien du véhicule toujours le samedi », « la lecture à 21h »),
    le chatbot écrit pinned_* après validation, et l'IA respecte ce créneau.
    Ces champs ne sont pas affichés dans l'UI ; on les retire aussi par le
    chatbot.
  Périodes par défaut : semaine = lundi → dimanche ; quinzaine = 14 jours
    depuis la création de la routine ; mois = mois civil.
  Total « aujourd'hui » = somme des estimated_minutes des seules routines
    planifiées dans la journée.
```

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
| Attention requise | Un projet promu (par remontée auto OU activation manuelle) mais INCOMPLET : bannière rouge "Attention requise" ; le projet est INERTE — il ne génère aucune mission tant qu'il n'est pas complété. Le critère de complétude est défini côté logique de génération (référencé, pas redéfini ici). |
| Editing | Bouton Modifier actif : actions add/delete/activate/reorder. |
| Error | Échec lecture/écriture projet ou routine, avec retry. |
| Offline | Lecture cache, modifications en attente de sync (bannière). |
| Conflict | Conflit serveur (ex. ordre modifié ailleurs) → diff/validation. |

---

## 8. Données (indicatif, V1 — à aligner avec le schéma existant)

> **CODÉ le 2026-10-17 (migration 20261017_0047)** sous les noms canoniques
> `imperium_projects`, `imperium_routines`, `imperium_routine_checks` (+ project_id,
> project_position, description, notes sur `imperium_missions`). Routes `/api/imperium` :
> `GET|POST /projects`, `POST /projects/reorder`, `PATCH|DELETE /projects/{id}`,
> `POST /projects/{id}/complete`, `GET /projects/completed`, `POST /projects/{id}/missions`,
> `POST /projects/{id}/missions/reorder`, `PATCH|DELETE /missions/{id}`,
> `GET|POST /routines`, `GET /routines/today`, `PATCH|DELETE /routines/{id}`,
> `POST /routines/{id}/place`, `POST /routines/{id}/check` ; WR :
> `POST /api/internal/projects/{id}/progress`. Le tableau ci-dessous reste la cible d'origine.

```sql
-- Projets (le concept existe déjà dans la vision/priorités ; à formaliser)
projects:
  id, user_id, title,
  description           -- libellé UI « Notes du projet » (maquette 11), facultatif
                        -- (décision 2026-10-16 : pas de champ notes séparé)
  status (active | inactive),
  active_rank (1 = principal, 2 = secondaire, NULL si non-actif),
  created_at, source (chatbot | manual)

-- Routines (routine_id déjà au dictionnaire doc 01) — champs : §4.1
routines:
  id (routine_id), user_id, name, frequency, estimated_minutes, priority,
  notes, active, pinned_weekday, pinned_month_day, pinned_time, created_at

routine_checks:
  id, routine_id, user_id, operational_day, done (bool), checked_at

-- Missions de projet (formulaire maquette 11) : title, description,
-- estimated_minutes (facultatif, doc 43 §5.2), notes.
```

> À réconcilier avec `05_DATABASE_SCHEMA.md` (vérifier si des tables projects /
> routines existent déjà avant d'en créer).

### 8bis. Missions hors projet (2026-10-21)

Décision utilisateur : une mission ponctuelle qui n'appartient à aucun projet (paperasse, démarche à la mairie,
rendez-vous…) doit être visible et gérable. Ce sont des missions du backlog sans projet, ni annexe, ni engagement
fixe (`imperium_missions`, aucune nouvelle table). Le moteur du jour les propose dès leur date de début
(`planned_start_at`) ou à leur échéance (`deadline_at`) ; sans aucune date, elles attendent.

- `GET /intrinsic-missions` : celles à faire (échéance la plus proche d'abord, puis date de début, puis
  ancienneté) et les 10 dernières faites ;
- `POST /intrinsic-missions` (Idempotency-Key) : titre, description, notes, domaine (religious, business,
  finance, health ou aucun), date de début, échéance, durée estimée ; événement `planning.mission.created`
  avec `project_id` nul ;
- `PATCH /missions/{id}` accepte aussi domaine, échéance et date de début (un champ envoyé à null s'efface) ;
- `POST /missions/{id}/done` : « Faite » hors du plan du jour (mission en attente ou en standby), événement de
  complétion ; `DELETE /missions/{id}` l'annule comme toute mission.

Écran : section « Missions hors projet » en haut de la colonne de droite, au-dessus des routines ; « + » ouvre
la fiche, une ligne ouvre sa fiche (Enregistrer, Faite, Supprimer). Échéance aujourd'hui ou demain par un choix
rapide, ou une date du calendrier. Le chatbot les crée aussi (doc 72, action `create_mission`).

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

- ~~Nom final de l'onglet~~ → RÉSOLU : "Operations", libellé UI « Opérations » (décision utilisateur 2026-10-15 ; "Pilotage" abandonné).
- ~~Route ID / path définitifs~~ → RÉSOLU : `IMP.OPERATIONS.MAIN`, `imperium/operations`.
- ~~Comportement du 3ᵉ projet~~ → RÉSOLU : V1 = le classement décide (2 premiers = actifs) ;
  fenêtre de choix Activer / Désactiver reportée aux versions suivantes (§3.3).
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

**Document version:** 1.0 (spec de base V1 — nom d'onglet définitif : Operations)
**Statut :** base V1 de l'onglet Operations ; enrichissement = F06 (futur)
**Last updated:** 2026-06-09
