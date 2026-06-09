# ASSETS INVENTORY — Imperium

**App :** Imperium (Command Center).
**Version inventaire :** 2.0 — régénérée avec l'architecture corrigée (4 top-level).
**Date :** 2026-06-09.

**Sources consultées :**
- `43_IMPERIUM_LOGIC_DETAIL.md` (logique métier détaillée, UI Surface §14).
- `59_DESIGN_SYSTEM_V1_DRAFT.md` §1 (couleurs Imperium), §6 (iconography 3-tier),
  §7 (foundation), §12 (Imperium Screen Architecture Mapping V1 — Route IDs).
- `61_DESIGN_SYSTEM_COMPOSITE_COMPONENTS.md` (composants composites métier,
  `static_asset_parts`, règle premium asset).
- `62_DESIGN_SYSTEM_COMPONENT_CATALOG.md` (foundation components `Imperium*`).
- `65_IMPERIUM_FRONTEND_SCREEN_SPEC_V1.md` (spec écrans corrigée — 4 top-level).
- `66_IMPERIUM_USER_FLOWS_V1.md`, `67_FRONTEND_STATE_MATRIX_V1.md`.
- `70_KNOWLEDGE_INBOX.md` (action "Nourrir l'IA" dans Settings).
- `71_IMPERIUM_OPERATIONS_TAB.md` (onglet Operations — Projets + Routines).
- `99_AUDIT_COHERENCE_FRONTEND.md` §D (résolutions d'assets actées).

**Architecture verrouillée :** 4 écrans top-level Imperium V1
1. `IMP.DASH.MAIN` — Dashboard (module mission active, chatbot docké, widget
   mission, bannière Weekly Review).
2. `IMP.OPERATIONS.MAIN` — Operations (Projets + Routines, doc 71).
3. `IMP.HISTORY.MAIN` — History.
4. `IMP.SETTINGS.CORE` — Settings (contient l'action "Nourrir l'IA", doc 70).

**Ne sont PAS top-level :**
- `IMP.MISSION.ACTIVE` = module principal du Dashboard.
- Chatbot (`IMP.CHAT.CONVERSATION`) = fenêtre dockée du Dashboard. L'ancien
  écran "Inbox" du doc 65 §5 n'existe plus.
- Weekly Review = bannière + fenêtre événementielle du Dashboard (routes
  liées `IMP.WR.LIST`, `IMP.WR.READ_ONLY`, `IMP.WR.INTERACTIVE`).
- Popups/forms (Morning Check-In, Mission Outcome, Day Finished, Replan,
  Add Manual Mission, Knowledge Inbox) = surfaces secondaires
  (dialog / bottom_sheet) listées comme telles.

**Règle visuelle canonique (doc 61 §1) :** `premium asset must not contain
dynamic data`. Aucun asset n'inclut texte, chiffres, dates, états ou décisions ;
tout dynamique est rendu en Compose. Les assets sont des shells, frames,
textures, emblèmes, illustrations vides.

**Notion de scope :**
- `app` (= `_shared/`) : partagé sur toutes les surfaces Imperium (background,
  Banner Info frame, cadres, textures). Généré une seule fois.
- `card` : spécifique à une carte/écran (illustration hero, ornement dédié).

**Résolutions actées (audit 99 §D) appliquées dans cet inventaire :**
- Logo Imperium 48dp ET badge IA 24dp = DEUX assets distincts.
- Set mood (Morning Check-In / Day Finished) = CUSTOM à générer (pas d'emoji,
  pas de Material Symbols).
- Pictogramme "decision" = Material Symbol `gavel` (système, pas à générer).
- Banners (Decisions Log / Info / Replan reason) = UN SEUL `Banner Info frame`
  partagé.
- Metric card hero = pas d'ornement (juste la taille).
- Conflict state = pas d'illustration (textuel).
- Daily Focus = pas d'emblème (label seul).

**Marquage statut :** chaque asset porte un `statut` :
- `à générer (custom)` : asset graphique à produire.
- `système (Material Symbol, pas à générer)` : icône Material Symbols Outlined.
- `partagé existant` : asset déjà déclaré scope app, simple réutilisation.

---

# Dashboard (`IMP.DASH.MAIN`)

Écran d'entrée Imperium V1 : montre la mission active (module principal), le
focus du jour, les priorités, les actions rapides, l'état global, le chatbot
docké et la bannière Weekly Review événementielle (doc 65 §3, doc 43 §14).

## Top Bar

En-tête fixe avec titre `Imperium`, sous-titre `Aujourd'hui`, `SyncStateChip` à
droite (doc 65 §3.5).

### Background Top Bar
- scope : app
- type : background
- statut : à générer (custom)
- description : surface de barre supérieure Imperium en `Primary` (`#1A2B4A`),
  hauteur 64dp tablette / 56dp téléphone, élévation L4.
- réutilisé sur : tous les écrans Imperium top-level + surfaces secondaires
  (Operations, History, Settings, Mission Outcome, Replan, Add Manual Mission,
  WR Interactive, Priority Rules, Chatbot, Plan History, Decisions Log,
  WR List, WR Read-only).

### Logo Imperium 48dp
- scope : app
- type : icon
- statut : à générer (custom)
- description : emblème/logo de l'app Imperium en 48dp, identité de marque,
  utilisé en hero d'écrans pop-ups et en header WR (doc 59 §6.1, §12.2, §12.3 ;
  audit 99 §D résolution #9).
- réutilisé sur : Morning Check-In (hero), Day Finished (hero), WR Interactive
  (hero), WR Read-only (header).

### SyncStateChip pictogram set
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : pictogrammes Material Symbols Outlined pour les états `pending`,
  `syncing`, `synced`, `failed`, `conflict`, `cached`, `stale` (doc 62
  `SyncStateChip`, doc 59 §6.2).
- réutilisé sur : tous les écrans Imperium (chip systématique).

## Bannière Weekly Review (événementielle)

Bannière affichée en haut du Dashboard quand la WR est due ou vient d'être
faite (audit 99 §C.2 : cycle lancement → fait → cooldown → disparition). Utilise
le `Banner Info frame` partagé (résolution audit #12/15).

### Banner Info frame
- scope : app
- type : frame
- statut : à générer (custom)
- description : enveloppe `ImperiumBanner` variante info/warning/error
  (`SemanticStateColors`, surface `SurfaceVariant`, icon + libellé, doc 59 §7.5,
  doc 62 §7).
- réutilisé sur : Dashboard (WR/Ghusl/Critical/Decisions Log/Offline/Replan
  reason banners), WR List (readiness banner), WR Interactive, Chatbot
  (Decisions Log banner), Replan Validation (model reason).

### Banner state pictogram set
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `info`, `warning`, `error_outline`, `cloud_off`,
  `update` selon la variante du banner.
- réutilisé sur : tous les écrans Imperium.

## Daily Focus Card

Carte pleine largeur en haut du contenu : focus label + raison (doc 65 §3.5).
Aucun emblème — texte seul (résolution audit #3).

### Card surface shell standard
- scope : app
- type : frame
- statut : à générer (custom)
- description : enveloppe de card standard Imperium : `Surface` `#16213A`,
  radius 16dp, padding MD, élévation L1 (doc 59 §4/§5, doc 62 `ImperiumCard`).
- réutilisé sur : toutes les cards Imperium (Daily Focus, Priority, Quick
  Actions, Imperium Status, Weekly Progress, Description, History Detail,
  Decision cards, Stored WR cards, Project windows, etc.).

## Active Mission Card (module principal du Dashboard)

`MissionFocusCard` : mission active unique avec actions primary (doc 65 §3.5,
§4 ; doc 61 §4 ; doc 43 §5). Le module `IMP.MISSION.ACTIVE` est rendu ici
comme module principal et NON comme écran top-level.

### Mission shell premium (navy/gold)
- scope : card
- type : frame
- statut : à générer (custom)
- description : enveloppe premium navy/gold du `MissionFocusCard`
  (`Shell navy/gold, emblem mission, subtle command frame` — doc 61 §4). UN
  SEUL accent gold visible par écran (doc 59 §9 / §1.2 Accent rare).
- réutilisé sur : (spécifique au module mission, présent aussi quand le module
  est rappelé sur surface secondaire — Mission Outcome compact header).

### Mission emblem (current focus)
- scope : card
- type : icon
- statut : à générer (custom)
- description : emblème de mission dédié au focus du jour, distinct du logo
  Imperium et du badge IA (`emblem mission` dans `MissionFocusCard.static_asset_parts`,
  doc 61 §4).
- réutilisé sur : Mission Outcome (compact mission header), Replan (mission
  cards Before/After).

### Deadline pulse halo animation
- scope : card
- type : autre (animation overlay)
- statut : à générer (custom)
- description : halo statique animé par Compose autour de la deadline quand
  elle est proche (doc 61 §4 `MissionFocusCard.animation = Deadline pulse when
  close`).
- réutilisé sur : (spécifique `MissionFocusCard`).

### Mission state semantic icons
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols Outlined `check_circle`, `warning`,
  `error_outline`, `cancel`, `block` pour rendre `active / faite / ratée /
  annulée / expirée` (doc 43 §5, doc 59 §6.3 — couplé au libellé).
- réutilisé sur : History, Mission Outcome, Plan History.

### Priority status pictograms
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols pour `priority: high / medium / low`
  (doc 59 §6.2, doc 62 `ImperiumStatusChip`).
- réutilisé sur : Add Manual Mission, Mission Outcome, History detail.

## Priority Card

`ImperiumCard` + `ImperiumKpiBlock` : top priority, reason, urgency label
(doc 65 §3.5).

### KPI block frame
- scope : app
- type : frame
- statut : à générer (custom)
- description : mini-cadre optionnel autour d'un KPI compact (`KPIBlock.
  static_asset_parts = Optional mini-frame or icon` — doc 61 §4).
- réutilisé sur : Weekly Progress, Day Finished (Day completion / Discipline
  mini KPI), WR Statistics, Plan History (weekly trend), Decisions Log
  (decisions this week), Settings completion badge, Add Manual Mission
  (priority preview score).

### Urgency status chip pictogram
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols pour `today / overdue / due_soon / cleared`
  (doc 62 `ImperiumStatusChip`).
- réutilisé sur : Plan History, Mission Outcome.

## Quick Actions

`ImperiumCard` + buttons : focaliser module mission active, ouvrir chatbot
docké, replan mock, finish day (doc 65 §3.6). Les boutons primary/secondary/
ghost/destructive utilisent les shells partagés ci-dessous.

### Primary button background
- scope : app
- type : button
- statut : à générer (custom)
- description : fond `Accent` `#C9A24B` (or rare) du `ImperiumPrimaryButton`,
  radius 12dp, height 48dp (doc 59 §7.1, doc 62). UN SEUL primary visible par
  écran.
- réutilisé sur : tous les écrans Imperium avec action primary.

### Secondary button outline shell
- scope : app
- type : button
- statut : à générer (custom)
- description : bordure 1dp `Border` + fond transparent du
  `ImperiumSecondaryButton`.
- réutilisé sur : tous les écrans Imperium.

### Ghost button text-only shell
- scope : app
- type : button
- statut : à générer (custom)
- description : surface transparente pour `ImperiumGhostButton`.
- réutilisé sur : tous les écrans Imperium.

### Destructive button background
- scope : app
- type : button
- statut : à générer (custom)
- description : fond `SemanticStateColors.Error` `#E5484D` du
  `ImperiumDestructiveButton` (doc 59 §7.1, doc 62) — utilisé pour Fail /
  Delete / Clear cache.
- réutilisé sur : Mission Active (Fail), Priority Rules (Reset), Settings
  (Clear cache), Add Manual Mission (Cancel destructive si applicable).

### Quick action pictograms
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols pour les quick actions (Open Mission, Open
  Chatbot, Request Replan, Finish Day — `play_arrow`, `chat`, `refresh`,
  `night_shelter`/`bedtime`, doc 59 §6.2).
- réutilisé sur : Dashboard uniquement (set fonctionnellement spécifique).

## Weekly Progress

`ImperiumMetricCard` + `ImperiumProgressBar` : missions done, failures,
weekly completion percent (doc 65 §3.5). Variante `hero metric` SANS ornement
(résolution audit #4).

### Progress bar track texture
- scope : app
- type : texture
- statut : à générer (custom)
- description : fond statique de la barre de progression linéaire (doc 62
  `ImperiumProgressBar`, doc 59 §1.2 `SurfaceVariant`). Le remplissage est
  dynamique Compose.
- réutilisé sur : Mission Active progress block, WR Statistics, WR Interactive
  step indicator, Settings completion badge.

## Imperium Status (Context Panel tablette)

`ImperiumCard` + `SyncStateChip` : mode mock, cache age, next backend wiring
phase (doc 65 §3.5). En tablette dans `ImperiumContextPanel` 320dp.

### Context panel divider
- scope : app
- type : divider
- statut : à générer (custom)
- description : séparateur vertical / horizontal interne au panel contextuel
  (doc 62 `ImperiumContextPanel.tokens = Divider`).
- réutilisé sur : Operations (séparateur Projets ↔ Routines), History detail
  panel, WR Statistics panel.

## Chatbot docké (fenêtre du Dashboard — `IMP.CHAT.CONVERSATION`)

Fenêtre dockée à droite 320dp en tablette ou route plein écran depuis le
Dashboard (doc 65 §9.6 deep link, doc 59 §12.9). N'est PAS un écran top-level.

### Chat message bubble shell — assistant
- scope : card
- type : frame
- statut : à générer (custom)
- description : bulle de message assistant
  (`ChatMessageBubble.static_asset_parts = Optional avatar shell`, doc 61 §4).
- réutilisé sur : WR Interactive (timeline conversation).

### Chat message bubble shell — user
- scope : card
- type : frame
- statut : à générer (custom)
- description : bulle de message utilisateur (variante de couleur subtile
  côté Accent app).
- réutilisé sur : WR Interactive (timeline conversation).

### Badge IA Imperium 24dp
- scope : app
- type : icon
- statut : à générer (custom)
- description : badge IA distinct du logo Imperium 48dp, utilisé comme avatar
  assistant dans les bulles chatbot et comme marqueur des interventions de l'IA
  (audit 99 §D résolution #9 — DEUX assets distincts ; doc 59 §12.9).
- réutilisé sur : WR Interactive (avatar assistant), AI shell card,
  AIRecommendationCard.

### Avatar utilisateur 40dp
- scope : app
- type : icon
- statut : à générer (custom)
- description : avatar utilisateur 40dp, photo profil ou silhouette par défaut
  (doc 59 §6.1, §12.9).
- réutilisé sur : WR Interactive.

### Typing indicator dots
- scope : app
- type : icon
- statut : à générer (custom)
- description : 3 dots animés statiques utilisés pendant
  `is_waiting_for_ai` (doc 61 §4 `ChatMessageBubble.animation = Typing
  indicator`).
- réutilisé sur : WR Interactive.

### Voice button circular shell
- scope : app
- type : button
- statut : à générer (custom)
- description : bouton micro circulaire 64dp, fond Accent app, icône `mic`,
  ring pulsé en recording (doc 59 §7.2, doc 62 `ImperiumVoiceButton` /
  `ImperiumVoiceInput`).
- réutilisé sur : Mission Active (Notes Area), Mission Outcome, WR Interactive,
  Morning Check-In (notes vocales optionnelles), Day Finished.

### Voice recording ring animation
- scope : app
- type : texture
- statut : à générer (custom)
- description : anneau pulsé statique animé par Compose pendant `recording /
  uploading` (doc 62 `ImperiumVoiceInput` états `idle / recording / uploading /
  processed`).
- réutilisé sur : toutes les surfaces avec voice input.

### Voice mic pictogram set
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `mic`, `mic_none`, `mic_off`, `upload`
  (doc 59 §6.2).
- réutilisé sur : toutes les surfaces avec voice input.

### Text field outline shell
- scope : app
- type : frame
- statut : à générer (custom)
- description : cadre `ImperiumTextField` : `SurfaceVariant` + `Border`, radius
  12dp, height 56dp, label flottant (doc 59 §7.2, doc 62 `ImperiumTextField`).
- réutilisé sur : Mission Active (Notes), Mission Outcome (Reason), Add Manual
  Mission (title/description/category), Day Finished (Main win/problem), WR
  Interactive (answer), Priority Rules, History/Operations Search Field
  (variante compact), Knowledge Inbox (file picker label).

### Search field shell
- scope : app
- type : frame
- statut : à générer (custom)
- description : variante compacte du text field avec icône `search` à gauche,
  height 48dp (doc 62 `ImperiumSearchField`).
- réutilisé sur : History.

## Bouton "Ajouter une mission manuelle" (entry → IMP.MISSION.ADD_MANUAL)

(Réutilise Primary/Secondary/Ghost shells.)

## États Dashboard (Loading / Empty / Error / Offline)

États obligatoires (doc 65 §3.8, doc 67).

### Skeleton placeholder texture
- scope : app
- type : texture
- statut : à générer (custom)
- description : shimmer/skeleton bar utilisé par `ImperiumSkeleton`
  (doc 62, doc 59 §7.7) ; LinearEasing 1500ms anime la texture statique.
- réutilisé sur : tous les écrans Imperium (chaque écran déclare un état
  Loading).

### Empty state illustration — "No active mission"
- scope : card
- type : illustration
- statut : à générer (custom)
- description : illustration 240×240dp pour le slot Active Mission vide
  (doc 65 §3.8 — title `No active mission`, CTA `Open Chatbot`). Pas de texte
  intégré à l'image.
- réutilisé sur : (variante similaire utilisable côté module mission active
  vide).

### Error state illustration générique
- scope : app
- type : illustration
- statut : à générer (custom)
- description : illustration "Error" 240×240dp en tons Warning (doc 59 §7.7).
- réutilisé sur : toutes les surfaces Imperium qui rendent
  `ImperiumErrorState`.

### Offline banner pictogram
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : `cloud_off` dans le banner offline persistant (doc 59 §7.7,
  doc 67).
- réutilisé sur : tous les écrans Imperium.

> Pas d'illustration `Conflict state` (résolution audit #11 : conflit textuel
> uniquement). Pas d'ornement hero ni d'emblème Daily Focus
> (résolutions #3 et #4).

## Background global de l'app

### Background plein écran Imperium
- scope : app
- type : background
- statut : à générer (custom)
- description : fond plein écran navy `#0E1626` constant sur toutes les
  surfaces Imperium, dark mode V1 (doc 59 §1.2).
- réutilisé sur : toutes les surfaces Imperium.

### Card surface variant (nested rows / chips)
- scope : app
- type : background
- statut : à générer (custom)
- description : surface `SurfaceVariant` `#1F2D4D` pour rows / chips /
  segmented internes (doc 59 §1.2). Pas de card-dans-card (doc 65 §2.4).
- réutilisé sur : toutes les surfaces Imperium.

---

# Operations (`IMP.OPERATIONS.MAIN`)

2ᵉ écran top-level : Projets (~2/3 gauche) + Routines (~1/3 droite) (doc 71).
Layout : 2 projets actifs + liste des non-actifs + bouton Modifier ; liste de
routines cochables.

> Note : doc 71 demande explicitement « pas un panneau flottant, c'est une
> division fixe de la surface » → le séparateur central est un divider rigide,
> pas un cadre flottant.

## Top Bar

### Background Top Bar (partagé existant)
- scope : app
- statut : partagé existant
- réutilisé sur : voir Dashboard.

### SyncStateChip pictogram set (partagé existant)

## Partie gauche — Projets

### Card surface shell standard (partagé existant)
- réutilisé sur : fenêtre 1 (projet actif principal), fenêtre 2 (projet actif
  secondaire), fenêtre 3 (liste des non-actifs).

### Projet actif — hero distinction (par la taille)
- scope : card
- type : frame
- statut : à générer (custom)
- description : la fenêtre 1 (projet actif principal) est plus grande que la
  fenêtre 2 (doc 71 §3.1). Distinction purement par taille / hiérarchie
  visuelle, PAS d'ornement décoratif (cf. résolution audit #4 metric hero).
  Asset = mêmes `Card surface shell` ; cette entrée documente que la fenêtre
  principale n'a pas de cadre dédié supplémentaire.
- réutilisé sur : (déduit — confirmation product à faire si un cadre distinct
  est souhaité).

### Vertical divider Projets ↔ Routines
- scope : app
- type : divider
- statut : à générer (custom)
- description : séparateur vertical fixe (doc 71 §2 : « division fixe de la
  surface »). Réutilise le pattern `Context panel divider` du Dashboard.
- réutilisé sur : Operations uniquement (mais asset commun).

### Liste des projets non-actifs (fenêtre 3)
- scope : app
- type : background
- statut : à générer (custom)
- description : pattern `List item row background + divider` partagé pour la
  liste verticale des projets en attente (doc 62 `ImperiumListItem`).
- réutilisé sur : voir « List item row » ci-dessous (partagé).

### List item row background + divider
- scope : app
- type : background
- statut : à générer (custom)
- description : surface neutre `Surface` + divider opacité 60% entre lignes
  (doc 59 §1.2, doc 62 `ImperiumListItem`).
- réutilisé sur : Operations (projets non-actifs, routines), History (timeline),
  Plan History, Decisions Log, WR List, Settings sections.

### Bouton "Modifier"
- scope : app
- statut : partagé existant
- description : utilise le `Secondary button outline shell` (déclaré
  Dashboard).
- réutilisé sur : (déjà partagé).

### Edition mode pictograms (add / delete / activate / reorder)
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `add`, `delete`, `play_arrow` (activer),
  `pause` (désactiver), `swap_vert`/`drag_indicator` (reorder) pour les
  actions du mode édition (doc 71 §3.3).
- réutilisé sur : Settings (toggle on/off), Priority Rules (drag indicator).

## Partie droite — Routines

### Routine list item row (partagé existant)
- description : réutilise `List item row background + divider`.

### Routine checkbox shell
- scope : app
- type : button
- statut : à générer (custom)
- description : case à cocher quotidienne (doc 71 §4 : « texte + coche
  quotidienne »). Réutilise le pattern `ImperiumToggle` ou checkbox Material 3
  selon le composant retenu — la doc ne fige pas le composant exact, déduit
  comme `ImperiumToggle` ou variante checkbox (doc 62 famille Selection).
- réutilisé sur : (déduit — à confirmer côté DS si checkbox dédiée vs toggle).

### Routine completion icon
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `check_circle` (fait) / `radio_button_unchecked`
  (pas fait).
- réutilisé sur : History (mission_completed), WR Read-only.

## États Operations

(doc 71 §7 : Loading / Empty / Ready / Editing / Error / Offline / Conflict.)

### Skeleton placeholder texture (partagé existant)

### Empty state illustration — "No projects yet"
- scope : card
- type : illustration
- statut : à générer (custom)
- description : illustration 240×240dp empty Operations avec CTA `Ajouter un
  projet` (doc 71 §7 + doc 59 §6.2 standard illustrations 240×240).
- réutilisé sur : (spécifique Operations).

### Error state illustration générique (partagé existant)

### Offline banner pictogram (partagé existant)

---

# History (`IMP.HISTORY.MAIN`)

Historique des missions, plans, décisions et événements Imperium sous forme
chronologique read-only (doc 65 §7).

## Top Bar + Search + Filters

### Background Top Bar (partagé existant)

### Search field shell (partagé existant)

### Search pictograms (search / clear)
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `search`, `close`.
- réutilisé sur : Operations (si search ajouté V2).

### Filter chip shell
- scope : app
- type : frame
- statut : à générer (custom)
- description : enveloppe de chip filtre : `SurfaceVariant`, radius 8dp,
  hauteur compacte (doc 59 §4, doc 62 `ImperiumFilterChip`).
- réutilisé sur : Plan History, Decisions Log, WR List, Knowledge Inbox
  (file-type chips).

### Filter category pictograms — History
- scope : card
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols pour les filtres history : missions = `flag`,
  decisions = `gavel`, weekly = `calendar_view_week`, failed = `error`, all =
  `apps` (doc 65 §7.5).
- réutilisé sur : (spécifique History, mais via le set Material Symbols).

## Timeline

`ImperiumTimeline` : timestamp, event type, title, status (doc 65 §7.5, doc 61
§4 `DailyPlanCard`).

### Timeline decorative frame
- scope : app
- type : frame
- statut : à générer (custom)
- description : cadre/rail de timeline avec divider vertical et points
  (`DailyPlanCard.static_asset_parts = Decorative timeline frame`, doc 61 §4).
- réutilisé sur : Plan History (`IMP.PLAN.HISTORY`), WR Interactive
  (conversation timeline).

### Timeline event node pictograms
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols par type d'évent : `mission_completed` =
  `check_circle`, `mission_failed` = `error_outline`, `decision` = `gavel`
  (résolution audit #10), `weekly_review` = `calendar_view_week` (doc 59 §6.2).
- réutilisé sur : Plan History, Decisions Log.

## History Detail Card (Context Panel tablette)

### Card surface shell standard (partagé existant)

### Status chip semantic pictograms
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols pour statuts métier (`done`, `failed`,
  `cancelled`, `expired`) couplés au libellé (doc 62 `ImperiumStatusChip`,
  doc 59 §6.3).
- réutilisé sur : Plan History, Decisions Log, WR List.

## États History

### Empty state illustration — "No history yet"
- scope : app
- type : illustration
- statut : à générer (custom)
- description : illustration 240×240dp empty History (doc 65 §7.8).
- réutilisé sur : Plan History, Decisions Log, WR List (variantes textuelles
  via le même asset si générique, sinon ce slot est partagé "No history").

### Skeleton placeholder texture (partagé existant)

### Error state illustration générique (partagé existant)

### Offline banner pictogram (partagé existant)

---

# Settings (`IMP.SETTINGS.CORE`)

Préférences frontend et liens de configuration ; contient l'action "Nourrir
l'IA" (doc 70). Pas de modification canonique sans backend (doc 65 §8).

## Top Bar (partagé existant)

## Sections (User / Theme / Notifications / Integrations / Security / Advanced / IA)

### Card surface shell standard (partagé existant)

### List item row background + divider (partagé existant)

### Segmented control track shell
- scope : app
- type : frame
- statut : à générer (custom)
- description : container du `ImperiumSegmentedControl` (doc 59 §7.3, doc 62
  Selection family) : surface `SurfaceVariant`, radius 12dp, indicator `Accent`.
- réutilisé sur : Morning Check-In (mood), Day Finished (mood), Mission Outcome
  (Faite/Ratée/Annulée), WR Interactive (allowed actions), Theme settings.

### Toggle switch track
- scope : app
- type : frame
- statut : à générer (custom)
- description : track du `ImperiumToggle` (switch Material 3, accent app on)
  (doc 59 §7.3).
- réutilisé sur : Notifications section, Advanced section, toute préférence
  binaire.

### Theme pictograms (system / light / dark)
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `brightness_auto`, `light_mode`, `dark_mode`.

### Notification category pictograms
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `notifications`, `alarm`, `event_note`.

### Integration status pictograms
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `cloud`, `database`, `psychology`.

### Security pictograms
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `lock`, `verified_user`.

### User pictograms
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `person`, `language`, `schedule`.

### Alert dialog frame
- scope : app
- type : frame
- statut : à générer (custom)
- description : modal centré, surface `Surface`, radius 20dp, élévation L3
  (doc 59 §4/§5, doc 62 `ImperiumAlertDialog`). Utilisé pour les
  confirmations destructives (Clear cache, Reset Priority Rules).
- réutilisé sur : Priority Rules (confirmation reset), Knowledge Inbox
  (confirmation cancel), Replan (si dialog confirm), Morning Check-In (fallback
  dialog frame), Day Finished, Mission Outcome (variante).

### Destructive confirmation pictogram
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `warning` ou `delete_forever`.
- réutilisé sur : Priority Rules (Reset), Mission Outcome (Fail).

## Section "Intelligence Artificielle" → action "Nourrir l'IA" (doc 70)

L'action ouvre la sub-surface Knowledge Inbox (voir Surfaces secondaires).

### IA section pictogram
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `psychology` ou `memory` pour marquer la
  section IA dans la liste Settings (doc 70 §13).
- réutilisé sur : Integrations row "ai_router".

## États Settings

### Skeleton placeholder texture (partagé existant)

### Empty state illustration — "Settings defaults not initialized"
- scope : card
- type : illustration
- statut : à générer (custom)
- description : illustration 240×240dp avec CTA `Use mock defaults` (doc 65
  §8.8).
- réutilisé sur : (spécifique Settings).

### Error state illustration générique (partagé existant)

---

# Surfaces secondaires (popups / dialogs / sheets / sub-routes)

Les écrans suivants NE sont PAS top-level — ils sont ouverts depuis le
Dashboard ou Settings, sur action utilisateur ou hook. Ils utilisent
massivement les assets partagés déclarés ci-dessus ; cette section liste les
assets propres à chacun.

---

## Morning Check-In Popup (`IMP.CHECKIN.MORNING`)

Type : `dialog` (fullscreen téléphone, 720dp centered tablette). Déclenché par
le morning trigger avant Dashboard (doc 43 §4, doc 59 §12.3, doc 65 hors GO).

### Dialog frame shell (partagé existant)
- description : voir Settings (Alert dialog frame).
- réutilisé sur : Day Finished, Replan, Add Manual Mission, WR Interactive.

### Logo Imperium 48dp (partagé existant)
- description : utilisé en header pop-up.

### Morning hero illustration (dawn/day)
- scope : card
- type : illustration
- statut : à générer (custom)
- description : illustration premium 240×240dp dawn/day (doc 59 §12.3 :
  `dawn/day hero 240x240`, doc 59 §9.1 hero d'écran à charge émotionnelle).
- réutilisé sur : (spécifique Morning Check-In).

### Slider track shell
- scope : app
- type : frame
- statut : à générer (custom)
- description : track + thumb du slider (doc 62 famille inputs — variantes
  Slider/Stepper).
- réutilisé sur : Day Finished (sliders energy / fatigue / sleep / stress).

### Number field shell
- scope : app
- type : frame
- statut : à générer (custom)
- description : variante number du `ImperiumTextField` avec
  `ImperiumFontFamilies.Numeric`, clavier numérique (doc 59 §7.2, doc 62
  `ImperiumNumberField`).
- réutilisé sur : Add Manual Mission (priority_level stepper), Settings
  (composite weights, debounce minutes), Day Finished.

### Mood pictogram set CUSTOM
- scope : app
- type : icon
- statut : à générer (custom)
- description : SET D'HUMEUR CUSTOM à dessiner (audit 99 §D résolution #5 :
  pas d'emoji, pas de Material Symbols). Nombre de niveaux d'humeur à figer au
  moment de la génération (déduit : 3-5 niveaux). Couplage au libellé requis
  (doc 59 §1.7 daltonisme).
- réutilisé sur : Day Finished (mood segmented).

### Segmented control track shell (partagé existant)

### Voice button circular shell (partagé existant) — pour notes vocales optionnelles

---

## Mission Outcome Form (`IMP.MISSION.OUTCOME`)

Type : `bottom_sheet`. Ouvert depuis le module mission active (doc 59 §12.4).

### Bottom sheet shell
- scope : app
- type : frame
- statut : à générer (custom)
- description : surface `Surface`, radius 24dp top, élévation L3
  (doc 59 §4/§5/§7.6, doc 62 `ImperiumBottomSheet`).
- réutilisé sur : WR Interactive (draft/final bottom sheet).

### Drag handle pill
- scope : app
- type : icon
- statut : à générer (custom)
- description : pill 32×4dp centré top du bottom sheet (doc 59 §3.2).
- réutilisé sur : tous les bottom sheets Imperium.

### Mission emblem (current focus) (partagé existant)
- description : en compact mission header.

### Segmented control track shell (partagé existant) — Faite / Ratée / Annulée

### Outcome state pictograms
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `check_circle`, `cancel`, `block` (chacun
  couplé au libellé).
- réutilisé sur : History, Plan History.

### Text field outline shell (partagé existant) — reason

### Voice button circular shell (partagé existant)

---

## Day Finished Form (`IMP.DAY.FINISH`)

Type : `dialog` (fullscreen). Bilan du jour (doc 24, doc 59 §12.5).

### Dialog frame shell (partagé existant)

### End-of-day hero illustration
- scope : card
- type : illustration
- statut : à générer (custom)
- description : illustration 240×240dp end-of-day (doc 59 §12.5 : « only when
  first empty state is shown », doc 59 §9.1 hero émotionnel).
- réutilisé sur : (spécifique Day Finished).

### Slider track shell (partagé existant) — energy / fatigue / sleep / stress

### Segmented control track shell (partagé existant) + Mood pictogram set CUSTOM (partagé existant)

### Text field outline shell (partagé existant) — main win / problem

### KPI block frame (partagé existant) — Day completion / Discipline mini KPI

### Logo Imperium 48dp (partagé existant) — en header

---

## Replan Validation Screen (`IMP.REPLAN.VALIDATE`)

Type : `dialog` (fullscreen modal). Before/After plan (doc 59 §12.6).

### Background Top Bar (partagé existant) — minimaliste

### Modal two-column frame
- scope : app
- type : frame
- statut : à générer (custom)
- description : `ImperiumModalFrame.variants = Two-column modal, wizard frame,
  review frame` (doc 62 Containers). Modal large avec colonnes Before/After.
- réutilisé sur : WR Interactive (timeline left + draft/action panel right).

### Card surface shell standard (partagé existant) — mission cards Before/After

### Mission emblem (current focus) (partagé existant) — sur cards mission

### Banner Info frame (partagé existant) — model reason banner

### Primary / Secondary / Ghost buttons (partagés existants) — Accepter / Modifier / Annuler

> Pas de "mission card delta badge shell" séparé : le delta est rendu en
> Compose (texte/chiffre dynamique) sur la `Card surface shell` standard
> (résolution audit #6 : asset dédié non justifié).

---

## Add Manual Mission Form (`IMP.MISSION.ADD_MANUAL`)

Type : `dialog`. Ajout manuel au backlog (doc 59 §12.7).

### Dialog frame shell (partagé existant)

### Text field outline shell (partagé existant) — title, description, category

### Number field shell (partagé existant) — priority_level stepper

### Stepper +/− shell
- scope : app
- type : button
- statut : à générer (custom)
- description : boutons stepper increment/decrement intégrés au
  `ImperiumNumberField` (doc 62 variantes).
- réutilisé sur : Settings (composite weights, debounce minutes).

### Stepper pictograms
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `add`, `remove`.
- réutilisé sur : Operations (edition mode), Settings.

### Date picker pictogram
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `event` ou `calendar_today` pour deadline
  picker.
- réutilisé sur : (commun aux pickers de date Imperium V1).

### KPI block frame (partagé existant) — priority preview score

### Primary / Ghost buttons (partagés existants) — Ajouter / Annuler

---

## Knowledge Inbox — action "Nourrir l'IA" (doc 70)

Sub-surface ouverte depuis Settings → Intelligence Artificielle. Type :
`dialog` (petite fenêtre Inbox). Cycle : pick → pre-check → upload →
analyzing → review (editable) → vectorizing → done (doc 70 §7, §8).

### Dialog frame shell (partagé existant)

### File picker pictograms
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `folder_open`, `description` (file),
  `image`, `picture_as_pdf`, `text_snippet` selon le type accepté
  (doc 70 §6 : PDF, images, plain text, office — exact list TBD).
- réutilisé sur : (spécifique Knowledge Inbox).

### Filter chip shell (partagé existant) — accepted-types chips (si rendu en chips)

### Skeleton placeholder texture (partagé existant) — "Analyzing shimmer"

### Text field outline shell (partagé existant) — extraction draft éditable

### Primary / Ghost buttons (partagés existants) — Ajouter à la mémoire / Annuler

### Alert dialog frame (partagé existant) — cancel confirmation

### Inbox status pictograms
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols pour les états doc 70 §8 : `cloud_upload`
  (uploading), `psychology` (analyzing), `edit` (review), `memory`
  (vectorizing), `check_circle` (done), `error_outline` (error), `cloud_off`
  (offline).
- réutilisé sur : Settings (réutilisation des states sync).

> Pas d'illustration hero ni d'illustration empty dédiée (résolution audit #11
> + principe « ne générer que si valeur justifiée »). Empty/Idle = file picker
> visible directement.

---

## Plan History Tab (`IMP.PLAN.HISTORY`)

Sub-route (deep link) depuis History (doc 59 §12.8).

### Background Top Bar / Filter chip shell / Filter category pictograms (partagés existants)

### Timeline decorative frame (partagé existant)

### Card surface shell standard (partagé existant) — daily plan cards

### Sparkline base track
- scope : app
- type : texture
- statut : à générer (custom)
- description : track / arrière-plan pour mini sparkline 64dp (doc 59 §12.12 :
  WR Read-only `sparkline trends 64dp`). Le tracé est dynamique Compose ; le
  track est statique.
- réutilisé sur : WR Read-only.

### Empty state illustration — "No history yet" (partagé existant)

---

## Decisions Log Tab (`IMP.DECISIONS.LOG`)

Sub-route depuis le Chatbot et History (doc 59 §12.10, doc 43 §8).

### Background Top Bar / Filter chip shell / Card surface shell (partagés existants)

### Decision pictogram
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `gavel` (résolution audit #10).
- réutilisé sur : History (Decisions filter).

### KPI block frame (partagé existant) — decisions this week counter

### Empty state illustration — "No history yet" (partagé existant)

### Banner Info frame (partagé existant) — banner vers le chatbot source

---

## Weekly Review List (`IMP.WR.LIST`)

Sub-route depuis le Dashboard (banner) / History (doc 59 §12.11).

### Banner Info frame (partagé existant) — WR readiness banner

### Premium review frame
- scope : card
- type : frame
- statut : à générer (custom)
- description : `WeeklyReviewCard.static_asset_parts = Premium review frame,
  ledger ornament` (doc 61 §4). Cadre premium dédié aux cards de Weekly Review,
  hero d'écran à charge émotionnelle (doc 59 §9.1).
- réutilisé sur : WR Read-only, WR Interactive.

### Ledger ornament
- scope : card
- type : illustration
- statut : à générer (custom)
- description : ornement décoratif "ledger" propre à `WeeklyReviewCard`
  (doc 61 §4). Détail visuel à charge émotionnelle.
- réutilisé sur : WR Read-only, WR Interactive.

### Status chip semantic pictograms (partagé existant) — stored / approved / submitted

### KPI block frame (partagé existant) — weekly streak counter

### Empty state illustration — "WR list empty"
- scope : card
- type : illustration
- statut : à générer (custom)
- description : illustration 240×240dp empty WR (doc 59 §12.11).
- réutilisé sur : (spécifique WR List).

---

## Weekly Review Read-only View (`IMP.WR.READ_ONLY`)

Deep link `imperium/weekly-reviews/{session_id}` (doc 59 §12.12).

### Premium review frame (partagé existant) — title / summary card

### Logo Imperium 48dp (partagé existant) — header

### Card surface shell standard (partagé existant) — deterministic sections

### Sparkline base track (partagé existant) — metrics cards

### KPI block frame (partagé existant)

### Primary button background (partagé existant) — Markdown export

### Export pictogram
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `download` ou `file_download`.
- réutilisé sur : (spécifique WR Read-only).

### Win pictogram / Failure pictogram
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `check_circle` (win) / `error_outline`
  (failure), couplés au libellé (doc 59 §6.3).
- réutilisé sur : History.

---

## Weekly Review Interactive Popup (`IMP.WR.INTERACTIVE`)

Type : `dialog` (fullscreen sur téléphone, large modal sur tablette)
(doc 32, doc 59 §12.13).

### Dialog frame shell (partagé existant)

### Modal two-column frame (partagé existant) — timeline left + draft/action panel right

### WR intro hero illustration
- scope : card
- type : illustration
- statut : à générer (custom)
- description : illustration 240×240dp intro WR (doc 59 §12.13 : `WR intro
  hero 240x240`, doc 59 §9.1 hero émotionnel).
- réutilisé sur : (spécifique WR Interactive).

### Logo Imperium 48dp (partagé existant)

### Timeline decorative frame (partagé existant) — conversation timeline

### Chat message bubble shells (assistant / user) (partagés existants)

### Badge IA Imperium 24dp (partagé existant) — avatar assistant

### Avatar utilisateur 40dp (partagé existant)

### Typing indicator dots (partagé existant)

### AI shell (recommendation card)
- scope : app
- type : frame
- statut : à générer (custom)
- description : shell visuel `AIRecommendationCard.static_asset_parts = AI
  shell, info icon` (doc 61 §4) entourant une recommandation AI/backend.
- réutilisé sur : Dashboard (si recommandation présentée), Chatbot, WR
  Read-only.

### Confidence chip pictograms
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols + chip pour niveau de confiance
  (`AIRecommendationCard.confidence`).
- réutilisé sur : Chatbot.

### Text field outline shell + Voice button circular shell (partagés existants)

### Segmented control track shell (partagé existant) — allowed actions

### Primary / Secondary / Ghost / Destructive buttons (partagés existants)

### Progress bar track texture (partagé existant) — WR progress step indicator

### Bottom sheet shell + Drag handle pill (partagés existants) — draft/final sheet

### Premium review frame + Ledger ornament (partagés existants)

---

## Priority Rules Settings (`IMP.SETTINGS.PRIORITIES`)

Sub-route depuis Settings (doc 26, doc 43 §9, doc 59 §12.14).

### Background Top Bar (partagé existant)

### Card surface shell standard (partagé existant) — Decision Framework schema help

### Drag handle pictogram
- scope : app
- type : icon
- statut : système (Material Symbol, pas à générer)
- description : Material Symbols `drag_indicator` ou `drag_handle` pour la
  liste draggable.
- réutilisé sur : Operations (edition mode reorder).

### Rank label chip shell (partagé existant)
- description : utilise le pattern `ImperiumStatusChip` neutre, déjà déclaré
  via `Status chip semantic pictograms`. Aucun asset supplémentaire.

### Status chip semantic pictograms (partagé existant)

### Alert dialog frame (partagé existant) — confirmation reset

### Destructive confirmation pictogram (partagé existant) — Reset button

### Primary / Secondary buttons (partagés existants) — Enregistrer / Réinitialiser

---

# Résumé assets PARTAGÉS (scope app) — à générer une fois

Liste dédupliquée des assets `scope: app` à GÉNÉRER (statut `à générer
(custom)`) une seule fois en haute résolution, pour toute l'app Imperium.

**Backgrounds & surfaces**
1. Background plein écran Imperium (`#0E1626`).
2. Background Top Bar (`Primary #1A2B4A`, 64dp tab / 56dp phone, L4).
3. Card surface shell standard (`Surface #16213A`, radius 16dp, L1).
4. Card surface variant (`SurfaceVariant #1F2D4D`, nested rows/chips/segmented).
5. List item row background + divider (opacité 60%).
6. Context panel divider (vertical/horizontal — réutilisé en Operations
   séparateur Projets ↔ Routines).

**Frames & shells**
7. Banner Info frame (variantes info / warning / error / offline / stale —
   UN SEUL frame partagé, résolution audit #12/15).
8. Dialog frame shell (Surface, radius 20dp, L3).
9. Alert dialog frame (subset du dialog, confirmations).
10. Bottom sheet shell (radius 24dp top, L3).
11. Drag handle pill 32×4dp (bottom sheet handle).
12. Modal two-column frame (`ImperiumModalFrame`).
13. Search field shell (compact text field avec icône search).
14. Text field outline shell (radius 12dp, height 56dp).
15. Number field shell (variante numeric).
16. Filter chip shell (radius 8dp).
17. Segmented control track shell.
18. Toggle switch track.
19. Voice button circular shell (64dp).
20. Voice recording ring animation (texture pulsée).
21. AI shell (autour de recommandation AI).
22. Timeline decorative frame.
23. Progress bar track texture (fond statique).
24. Sparkline base track (64dp).
25. Skeleton placeholder texture (shimmer 1500ms).
26. KPI block frame (mini-cadre optionnel).

**Boutons**
27. Primary button background (Accent `#C9A24B` rare, radius 12dp, h. 48dp).
28. Secondary button outline shell (bordure 1dp `Border`).
29. Ghost button text-only shell.
30. Destructive button background (Error `#E5484D`).
31. Stepper +/− shell.
32. Routine checkbox shell *(déduit — à confirmer DS)*.

**Marques & avatars (DEUX assets distincts, audit 99 §D résolution #9)**
33. **Logo Imperium 48dp** — identité de marque, header pop-ups & hero
    d'écrans.
34. **Badge IA Imperium 24dp** — marqueur des interventions de l'IA, avatar
    assistant chatbot / WR Interactive.
35. Avatar utilisateur 40dp.

**Mood set CUSTOM (audit 99 §D résolution #5)**
36. **Mood pictogram set custom** — pas d'emoji, pas de Material Symbols.
    Couplage au libellé. Nombre de niveaux d'humeur à figer à la génération.

**Animations / textures de fond animé**
37. Deadline pulse halo (`MissionFocusCard` deadline proche).
38. Typing indicator dots (3 dots animés).
39. Skeleton shimmer texture *(cf. #25)*.
40. Voice recording ring animation *(cf. #20)*.

**Illustrations (scope app, génériques 240×240dp)**
41. Error state illustration générique (tons Warning).
42. Empty state illustration générique "No history yet" (réutilisée History,
    Plan History, Decisions Log).

---

# Résumé assets CUSTOM à générer (scope card)

Assets spécifiques à une carte/écran, non partagés.

| # | Asset | Écran/surface | Format |
|---|---|---|---|
| 1 | Mission shell premium (navy/gold) | Dashboard module mission active | frame |
| 2 | Mission emblem (current focus) | Module mission active (+ réutilisé Outcome compact / Replan cards) | icon dédié |
| 3 | Morning hero illustration (dawn/day) | Morning Check-In | 240×240 |
| 4 | End-of-day hero illustration | Day Finished | 240×240 |
| 5 | WR intro hero illustration | WR Interactive | 240×240 |
| 6 | Premium review frame | WR List / Read-only / Interactive | frame |
| 7 | Ledger ornament | WR List / Read-only / Interactive | illustration ornementale |
| 8 | Empty state — "No active mission" | Dashboard (module mission) | 240×240 |
| 9 | Empty state — "No projects yet" | Operations | 240×240 |
| 10 | Empty state — "WR list empty" | WR List | 240×240 |
| 11 | Empty state — "Settings defaults not initialized" | Settings | 240×240 |

---

# Assets système (Material Symbols Outlined weight 400) — pas à générer

Catalogue des pictogrammes consommés par Imperium. Tous sont des Material
Symbols (doc 59 §6.2 — set système), à utiliser tels quels, jamais à
redessiner.

**Sync & system**
- SyncStateChip set : `pending`, `syncing`, `synced`, `failed`, `conflict`,
  `cached`, `stale`.
- Banner state set : `info`, `warning`, `error_outline`, `cloud_off`, `update`.
- Offline banner : `cloud_off`.

**Mission & priorité**
- Mission state : `check_circle`, `warning`, `error_outline`, `cancel`,
  `block` (pour active / faite / ratée / annulée / expirée).
- Priority status : `keyboard_double_arrow_up` (high), `drag_handle` (medium),
  `keyboard_double_arrow_down` (low) — variantes Material Symbols selon le
  set retenu.
- Urgency : `today`, `schedule`, `error_outline`, `done`.
- Outcome : `check_circle`, `cancel`, `block`.
- Status chip métier : `done`, `failed`, `cancelled`, `expired`.

**Decision & timeline**
- Decision : `gavel` (résolution audit #10).
- Timeline events : `check_circle` (mission_completed), `error_outline`
  (mission_failed), `gavel` (decision), `calendar_view_week` (weekly_review).
- Win / Failure : `check_circle`, `error_outline`.
- Week status : `ready_for_review`, `not_started`, `submitted`, `incomplete`
  → mapping concret Material Symbols à figer (déduit : `assignment_turned_in`,
  `pending`, `task_alt`, `report_problem`).

**Inputs / boutons / navigation**
- Search : `search`, `close`.
- Voice mic : `mic`, `mic_none`, `mic_off`, `upload`.
- Button leading/trailing : `check`, `close`, `refresh`, `arrow_back`, `add`,
  `remove`.
- Drag handle : `drag_indicator` / `drag_handle`.
- Date picker : `event`, `calendar_today`.
- Export : `download`, `file_download`.
- Destructive confirm : `warning`, `delete_forever`.

**Quick actions (Dashboard)**
- `play_arrow` (Open Mission), `chat` (Open Chatbot), `refresh` (Request
  Replan), `bedtime` / `night_shelter` (Finish Day).

**Settings**
- User : `person`, `language`, `schedule`.
- Theme : `brightness_auto`, `light_mode`, `dark_mode`.
- Notifications : `notifications`, `alarm`, `event_note`.
- Integrations : `cloud`, `database`, `psychology`.
- Security : `lock`, `verified_user`.
- IA section : `psychology`, `memory`.

**Knowledge Inbox**
- `folder_open`, `description`, `image`, `picture_as_pdf`, `text_snippet`,
  `cloud_upload`, `psychology`, `edit`, `memory`, `check_circle`,
  `error_outline`, `cloud_off`.

**AI confidence**
- `verified`, `report`, `help` — mapping concret à figer pour high/medium/low.

**Operations / Routines**
- Edition mode : `add`, `delete`, `play_arrow` (activer), `pause` (désactiver),
  `swap_vert`.
- Routine completion : `check_circle`, `radio_button_unchecked`.

**Filters History (catégoriels)**
- Missions = `flag`, Decisions = `gavel`, Weekly = `calendar_view_week`,
  Failed = `error`, All = `apps`.

---

# Trous restants dans la spécification

Zones où les docs mentionnent un élément sans préciser assez pour figer
l'asset. À étoffer avant génération.

1. **Bannière Weekly Review — cycle "fait" + cooldown** (audit 99 §C.2,
   marqué "à documenter dans le doc Dashboard/WR"). Statut visuel
   "Weekly Review fait", durée du cooldown, message « tu peux retrouver ta
   Weekly Review dans History » : à figer pour décider si un asset distinct
   du `Banner Info frame` est requis. Hypothèse actuelle : réutilisation du
   Banner Info frame avec un libellé/pictogramme différent.

2. **Operations — Fenêtre 1 (projet actif principal) vs Fenêtre 2
   (secondaire)** (doc 71 §3.1). La doc dit « la plus grande, mise en avant »
   mais ne fixe ni ornement ni cadre distinct. Hypothèse : distinction par la
   taille uniquement (cohérent résolution audit #4). À confirmer côté product
   si un cadre visuel séparé est attendu.

3. **Operations — composant cochable des routines** (doc 71 §4 : « texte +
   coche quotidienne »). Pas de précision sur le composant exact entre
   `ImperiumToggle` et une variante checkbox dédiée. Choix de DS à figer.

4. **Operations — Empty state illustration scope**. Réutilisation possible du
   "No history yet" partagé ou illustration "No projects yet" dédiée ? La doc
   71 §7 propose une CTA dédiée "Ajouter un projet" donc plutôt asset dédié
   ; à confirmer.

5. **Knowledge Inbox — illustration empty/idle**. Doc 70 §8 décrit le state
   `Idle = File picker` sans illustration. Hypothèse retenue : pas
   d'illustration dédiée (file picker direct). À confirmer si la fenêtre doit
   afficher un visuel d'accueil.

6. **Set mood custom — nombre de niveaux** (audit 99 §D résolution #5).
   La doc 43 §4 parle d'un emoji "one tap" sans préciser un nombre fixe
   d'options. À figer à la génération (déduit 3-5 niveaux).

7. **Onglet Operations — nom final** (doc 71 préambule : "Operations" est
   provisoire). N'impacte pas les assets mais le label visible dans Sidebar/
   Bottom Nav et Top Bar changera : prévoir d'utiliser un slot libellé, pas
   un asset texturé.

8. **AI confidence chip — mapping pictogrammes concrets**. Doc 61 §4 nomme
   `confidence` sur `AIRecommendationCard` mais pas le mapping Material
   Symbols pour high/medium/low. À figer.

9. **Chatbot — provider chip pictogram** (Sonnet / Opus / Web / Qwen).
   Doc 59 §12.9 mentionne « read-only provider chip » sans figer
   d'iconographie. Probable mapping Material Symbols ou texte seul ; à
   trancher (le principe "ne générer que si valeur" pointe vers texte seul).

10. **Mission shell premium — distinction par rapport à Card surface shell
    standard**. Doc 61 §4 distingue les deux mais ne donne pas de
    spécification de la « subtle command frame ». Asset à concevoir avec
    soin pour respecter la règle « un seul accent gold visible par écran ».

11. **WR readiness banner vs "WR fait" banner** : un seul asset Banner Info
    frame, mais le pictogramme et le libellé devront varier. À documenter
    sur le cycle banner (cf. #1).

12. **Replan — "Before/After" delta visualisation**. La doc 59 §12.6 parle
    de "mission cards with delta badges". Résolution audit #6 = pas d'asset
    delta badge. Confirmer que le delta sera rendu en Compose pur (texte +
    couleur sémantique), sans frame additionnel.
