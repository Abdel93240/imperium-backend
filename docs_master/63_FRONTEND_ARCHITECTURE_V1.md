# 63 — Frontend Architecture Android V1

**Version :** 1.0
**Sources de vérité :** `docs_master/59_DESIGN_SYSTEM_V1_DRAFT.md`, `docs_master/60_DESIGN_SYSTEM_TOKENS_KT.md`, `docs_master/61_DESIGN_SYSTEM_COMPOSITE_COMPONENTS.md`, `docs_master/62_DESIGN_SYSTEM_COMPONENT_CATALOG.md`, `docs_master/07_ANDROID_APP_RESPONSIBILITIES.md`
**Cible :** Android natif Kotlin + Jetpack Compose + Material 3
**Device principal :** Samsung Galaxy Tab S8, portrait (V1, décision 2026-10-16) — adaptation ultérieure : Samsung Galaxy Tab S10 Ultra, landscape

> **Cible V1 (décision utilisateur 2026-10-16) : Samsung Galaxy Tab S8 (11"), PORTRAIT**, dimensions fluides (aucune taille en pixels figée), comme les maquettes de la revue UI du 2026-10-15. Sidebar à gauche conservée. Les mentions « Tab S10 Ultra landscape » de ce document décrivent désormais l'ADAPTATION ULTÉRIEURE (S10/S11 Ultra, paysage), pas la cible V1.
**Device secondaire :** téléphone Android
**Statut :** CANONICAL FRONTEND ARCHITECTURE V1 — specification only, aucun Kotlin runtime ou scaffold Android n'est créé par ce document.

Ce document définit l'architecture frontend Android canonique V1 avant toute génération massive de Kotlin. Il ne remplace pas le backend : PostgreSQL, n8n, pgvector, API, AI router et règles backend restent la source de vérité.

---

## 1. Principes

### 1.1 Backend is source of truth

Le backend possède l'état canonique. Les apps Android affichent, collectent, déclenchent et expliquent. Elles ne décident pas seules.

Règles non négociables :

- Imperium reste le command center.
- Une seule mission active peut exister, et cette invariant est validé backend.
- Vault observe et rapporte la réalité financière ; il ne prend pas de décision financière autonome.
- Vector conseille l'activité VTC ; il n'automatise aucune action Bolt illégale ou contraire aux plateformes.
- Pulse reste simple et pratique ; il ne pose pas de diagnostic.
- Path collecte les confirmations spirituelles explicites ; il ne produit pas de jugement religieux autonome.

### 1.2 UI state only

Le frontend maintient uniquement de l'état UI :

- champ en cours de saisie ;
- filtre ou onglet sélectionné ;
- scroll position ;
- état local de dialog/bottom sheet ;
- brouillon non canonique clairement marqué `pending` ;
- snapshot cache avec timestamp.

Il ne maintient pas :

- priorité officielle ;
- mission active officielle ;
- solde financier canonique ;
- recommandation VTC live non confirmée ;
- mémoire long terme ;
- routing AI officiel ;
- règles de discipline ou santé indépendantes du backend.

### 1.3 Unidirectional data flow

Flux officiel :

```text
Screen
→ UiEvent
→ ViewModel
→ Repository
→ API
→ Backend validation
→ Repository cache/read model
→ UiState
→ Screen
```

Compose ne contient pas de logique métier. Compose rend `UiState`, émet des `UiEvent` explicites et observe les `UiEffect` à usage unique.

### 1.4 Compose first

L'UI V1 est Jetpack Compose first :

- Material 3 pour les primitives ;
- composants foundation `Imperium*` issus du document 62 ;
- composants composites métier issus du document 61 ;
- navigation Compose ;
- state hoisting vers ViewModel ;
- previews autorisées uniquement avec fixtures statiques clairement non canoniques.

### 1.5 Offline aware

Chaque donnée affichée doit dire si elle est live, cachee, stale, pending, syncing, synced, failed ou conflict. Le frontend ne présente jamais un cache comme vérité live.

### 1.6 Theme driven

Les couleurs, typographies, espacements, radius, elevations, icônes et états viennent des documents 59 et 60. Aucun écran V1 ne hardcode une palette locale hors tokens canoniques.

### 1.7 Feature modularity

Chaque app a son module feature. Les modules feature consomment `core/designsystem`, `core/navigation`, `core/network`, `core/database` et `core/sync`. Ils ne réimplémentent pas la stratégie métier.

---

## 2. Repository Structure

Arborescence Android cible :

```text
app/

core/
  designsystem/
  navigation/
  network/
  database/
  sync/
  widgets/

feature_imperium/
feature_vault/
feature_vector/
feature_pulse/
feature_path/
```

### 2.1 `app/`

Responsabilité :

- point d'entrée Android ;
- `MainActivity` ;
- DI root ;
- composition du thème actif ;
- root navigation host ;
- configuration device class tablet/phone ;
- wiring des modules feature.

`app/` ne contient pas de logique métier, pas d'appel API direct, pas de cache local direct.

### 2.2 `core/designsystem/`

Responsabilité :

- `ImperiumTheme` ;
- tokens Kotlin Compose extraits du document 60 ;
- composants foundation du document 62 ;
- interfaces des composants composites du document 61 ;
- états visuels `pending|syncing|synced|failed|conflict|cached|stale` ;
- règles responsive du document 59.

### 2.3 `core/navigation/`

Responsabilité :

- routes top-level ;
- graph Compose commun ;
- deep links internes ;
- transition tablet/phone ;
- contrat des tabs, dialogs, bottom sheets et side sheets.

Ce module expose des IDs stables ; il ne crée pas de nouvelle surface V2/V3.

### 2.4 `core/network/`

Responsabilité :

- Retrofit ;
- Kotlinx Serialization ;
- OkHttp interceptors ;
- authentification ;
- idempotency keys pour mutations ;
- timeouts ;
- retry policy ;
- mapping API errors vers états UI.

### 2.5 `core/database/`

Responsabilité :

- Room ;
- caches read-only ;
- pending write queue locale ;
- timestamps de fraîcheur ;
- tables locales de support UI.

Le cache local n'est jamais source de vérité.

### 2.6 `core/sync/`

Responsabilité :

- machine d'état sync ;
- WorkManager ;
- retry/backoff ;
- conflit local/serveur ;
- exposition `SyncBanner`, `SyncStateChip`, `ConflictState`.

### 2.7 `core/widgets/`

Responsabilité :

- bulles flottantes Android (overlay, §10) — pas de widgets d'écran d'accueil ;
- panneaux légers lisant l'état à l'ouverture ;
- aucune décision métier locale.

### 2.8 `feature_*`

Chaque feature module contient :

```text
navigation/
screens/
components/
viewmodel/
repository/
model/
```

Responsabilité :

- écrans V1 de l'app ;
- ViewModels de l'app ;
- repositories orientés API/cache ;
- models UI ;
- navigation locale ;
- composants métier propres à l'app.

---

## 3. Design System Integration

### 3.1 Source chain

Les documents alimentent Compose dans cet ordre :

| Document | Rôle frontend |
|---|---|
| `59_DESIGN_SYSTEM_V1_DRAFT.md` | Source canonique du design system, scope V1, palettes, responsive, 62 écrans. |
| `60_DESIGN_SYSTEM_TOKENS_KT.md` | Noms et valeurs de tokens Kotlin Compose à implémenter. |
| `61_DESIGN_SYSTEM_COMPOSITE_COMPONENTS.md` | Composants composites dynamiques, règle `premium asset must not contain dynamic data`. |
| `62_DESIGN_SYSTEM_COMPONENT_CATALOG.md` | Catalogue des composants foundation `Imperium*`. |

### 3.2 Theme

`ImperiumTheme` enveloppe toute l'application Android et reçoit l'app active :

```text
ImperiumTheme(app = Imperium|Vault|Vector|Pulse|Path)
```

Le thème expose :

- color scheme Material 3 mappé depuis les palettes app ;
- `ImperiumColors` custom pour `Accent`, `Border`, `Divider`, `TextMuted` ;
- `ImperiumTypography` ;
- `ImperiumSpacing` ;
- `ImperiumRadius` ;
- `ImperiumElevation` ;
- `ImperiumIcons` ;
- `ImperiumSyncState`.

### 3.3 Tokens

Les tokens sont immuables V1 :

- couleurs app : Imperium, Vault, Vector, Pulse, Path ;
- semantic states : `Success`, `Warning`, `Error`, `Info` ;
- Vector halo séparé : `HaloSuccess`, `HaloWarning`, `HaloError`, `HaloAnalyzing` ;
- typographies : Inter, JetBrains Mono, Noto Naskh Arabic ;
- spacing : `XXS` à `XXXL` ;
- radius : `Chip`, `Button`, `Input`, `Card`, `BottomSheet`, `Dialog` ;
- elevation : `L0` à `L4`.

### 3.4 Foundation Components

Les composants foundation vivent dans `core/designsystem/` :

- buttons ;
- inputs ;
- selection controls ;
- navigation ;
- feedback ;
- containers ;
- state surfaces ;
- data display.

Ils ne lisent que les tokens et `UiState`. Ils n'appellent pas l'API.

### 3.5 Composite Components

Les composants composites assemblent design system + données backend :

- `MissionFocusCard` ;
- `FinancialPressureCard` ;
- `VectorHalo` ;
- `HydrationDrop` ;
- `PrayerStatusCard` ;
- autres composants listés dans le document 61.

Règle obligatoire :

```text
premium asset must not contain dynamic data
```

Toute donnée dynamique est rendue par Compose depuis `UiState`.

---

## 4. Navigation Architecture

### 4.1 Root Compose Navigation

Le root graph contient cinq routes top-level :

| Top-level route | Dashboard route | Stable ID |
|---|---|---|
| `Imperium` | `imperium/dashboard` | `IMP.DASH.MAIN` |
| `Vault` | `vault/dashboard` | `VAU.DASH.MAIN` |
| `Vector` | `vector/dashboard` | `VEC.DASH.MAIN` |
| `Pulse` | `pulse/dashboard` | `PUL.DASH.MAIN` |
| `Path` | `path/dashboard` | `PAT.DASH.MAIN` |

Les stable IDs existants restent les clés d'identité UI, d'analytics local non sensible, de tests et de deep links internes.

### 4.2 Tabs and primary destinations

Tablet landscape utilise `ImperiumSidebar`. Téléphone utilise `ImperiumBottomNavigation`.

Destinations top-level V1 :

- Imperium : `IMP-01` Dashboard, `IMP-02` Mission Active, `IMP-03` Inbox, `IMP-04` Weekly Review, `IMP-05` History, `IMP-06` Settings.
- Vault : `VAU-01`, `VAU-07`, `VAU-09`, `VAU-12`.
- Vector : `VEC-01`, avec session active `VEC-03` accessible depuis dashboard ou deep link.
- Pulse : `PUL-01`, `PUL-10`, `PUL-11`, `PUL-12`, `PUL-14`.
- Path : `PAT-01`, `PAT-09`, `PAT-10`, `PAT-11`.

Les tabs secondaires restent internes à une feature et ne deviennent pas destinations root.

Navigation Imperium V1 permanente :

| Order | Label | Screen ID | Route ID |
|---|---|---|---|
| 1 | Dashboard | `IMP-01` | `IMP.DASH.MAIN` |
| 2 | Mission Active | `IMP-02` | `IMP.MISSION.ACTIVE` |
| 3 | Inbox | `IMP-03` | `IMP.INBOX.MAIN` |
| 4 | Weekly Review | `IMP-04` | `IMP.WR.SUMMARY` |
| 5 | History | `IMP-05` | `IMP.HISTORY.MAIN` |
| 6 | Settings | `IMP-06` | `IMP.SETTINGS.CORE` |

### 4.3 Dialogs

Dialogs pour :

- confirmation destructive ;
- conflit simple ;
- validation courte ;
- choix enum court ;
- garde-fou avant action importante.

Un dialog ne porte pas un workflow long. Sur tablette, max width cible 720-760dp.

### 4.4 Bottom sheets and side sheets

Téléphone :

- bottom sheets pour formulaires courts ;
- actions contextuelles ;
- quick capture.

Tablette :

- side sheets 360-480dp quand le contexte principal doit rester visible ;
- bottom sheet seulement si l'action est naturellement temporaire et compacte.

### 4.5 Deep links

Deep links V1 autorisés :

- Mission Active `IMP.MISSION.ACTIVE` pour la mission active unique, sans route detail V1 separee ;
- Vault transaction detail/edit `VAU-08` ;
- Vector recommendation detail `VEC-08` ;
- Pulse handoffs vers stock ou replan prompts ;
- Path sadaqa settings `PAT-11d` depuis Vault ;
- cross-app handoffs backend confirmés.

Un deep link ne valide pas une action canonique. Il ouvre une surface avec contexte et sync state.

---

## 5. State Management

### 5.1 Official pattern

Pattern officiel :

```text
Screen
→ ViewModel
→ Repository
→ API
```

Compose :

- collecte `UiState` ;
- émet `UiEvent` ;
- consomme `UiEffect` ;
- n'exécute pas de calcul métier canonique.

Compose ne contient pas de logique métier.

### 5.2 ViewModel

Le ViewModel :

- combine cache + API read model ;
- expose `StateFlow<UiState>` ;
- reçoit `UiEvent` ;
- appelle le repository ;
- traduit erreurs en états affichables ;
- déclenche `UiEffect` pour navigation/snackbar/toast.

Le ViewModel peut valider la forme d'un champ, mais pas valider une décision canonique.

### 5.3 UiState

`UiState` est une data class stable et explicite :

```text
data
isLoading
isOffline
syncState
lastUpdatedAt
error
permissions
draft
```

`UiState` doit pouvoir représenter loading, empty, error, offline, syncing, synced, conflict, cached et stale.

### 5.4 UiEvent

`UiEvent` représente une intention utilisateur :

- `RefreshRequested` ;
- `SubmitClicked` ;
- `RetrySyncClicked` ;
- `OpenDetailClicked(id)` ;
- `DraftChanged(value)` ;
- `VoiceInputRequested` ;
- `ConflictResolutionSelected`.

Chaque mutation transmet un payload explicite et une idempotency key si applicable.

### 5.5 UiEffect

`UiEffect` est à usage unique :

- navigation ;
- snackbar ;
- toast non autoritaire ;
- ouvrir/fermer sheet ;
- demander permission ;
- lancer picker média.

Un `UiEffect` ne remplace jamais un état backend confirmé.

---

## 6. Network Layer

### 6.1 Retrofit and serialization

`core/network/` utilise :

- Retrofit ;
- Kotlinx Serialization ;
- DTO request/update/response séparés ;
- mappers DTO vers models UI/domain frontend ;
- `response_model` backend comme contrat côté API.

### 6.2 Interceptors

OkHttp interceptors requis :

- auth bearer token ;
- request ID ;
- idempotency key pour writes ;
- redaction logs ;
- network status ;
- timeout metadata ;
- backend version header si disponible.

Les logs ne doivent jamais contenir token, cookie, credential, audio brut, image brute ou payload spirituel/santé sensible.

### 6.3 Auth

Auth frontend :

- stocker tokens dans mécanisme sécurisé Android ;
- refresh contrôlé ;
- logout efface cache sensible local ;
- erreurs auth mappées en état explicite ;
- pas de token exposé dans `UiState`.

### 6.4 Offline

Quand réseau absent :

- les reads servent le dernier cache disponible avec `cached` ou `stale` ;
- les writes entrent dans la write queue locale si autorisés ;
- les actions non sûres sont désactivées ;
- l'utilisateur voit timestamp et statut.

### 6.5 Timeout

Timeouts :

- read dashboard court ;
- upload image/audio plus long ;
- recommandation AI avec état progressif ;
- aucun spinner infini sans slow-loading state.

### 6.6 Retries

Retries :

- automatiques seulement pour erreurs réseau idempotentes ;
- writes avec idempotency key ;
- backoff via WorkManager ;
- bouton retry visible pour échecs utilisateurs.

### 6.7 Stale data

Une donnée stale reste affichable seulement si :

- timestamp visible ;
- `SyncStateChip` ou `SyncBanner` visible ;
- aucune décision live n'est prétendue ;
- CTA refresh ou retry existe si utile.

---

## 7. Local Cache

### 7.1 Room

`core/database/` utilise Room pour :

- read models cache ;
- pending writes ;
- sync attempts ;
- conflict records ;
- bubble panel state (léger, lu à l'ouverture).

### 7.2 Cache is not source of truth

Règle :

```text
cache local != source de vérité
```

Le backend reste canonique. Room accélère l'affichage, permet la lecture offline et garde une queue de writes non confirmés.

### 7.3 Cache categories

Catégories V1 :

- dashboard snapshots ;
- lists paginées ;
- detail snapshots ;
- pending mutation payloads ;
- état des panneaux de bulles ;
- permission/cache metadata.

### 7.4 Cache invalidation

Invalidation :

- après mutation backend confirmée ;
- après conflict resolution ;
- selon TTL par feature ;
- au logout ;
- au changement de compte si futur multi-compte.

---

## 8. Sync Layer

### 8.1 Sync states

États canoniques alignés DS :

| State | Signification frontend |
|---|---|
| `pending` | Action locale créée, pas encore envoyée ou pas encore acceptée backend. |
| `syncing` | Envoi ou refresh en cours. |
| `synced` | Backend a confirmé. |
| `failed` | Envoi ou refresh échoué, retry ou correction disponible. |
| `conflict` | Divergence local/serveur exigeant résolution. |
| `cached` | Donnée issue du cache, encore acceptable avec timestamp. |
| `stale` | Donnée trop ancienne pour être présentée comme live. |

### 8.2 SyncBanner

`SyncBanner` est utilisé pour état global ou critique :

- offline ;
- stale dashboard ;
- conflit bloquant ;
- write queue en attente ;
- backend unavailable.

Il est persistant jusqu'à résolution ou dismiss autorisé.

### 8.3 SyncStateChip

`SyncStateChip` est utilisé pour lignes, cards et détails :

- transaction ;
- mission ;
- recommandation ;
- prière/jeûne ;
- log Pulse ;
- upload image/audio.

La couleur n'est jamais seule : icon + label sont requis.

### 8.4 Conflict Handling

Process conflit :

```text
detect conflict
→ show conflict state
→ block fake success
→ fetch server version
→ present options
→ submit explicit resolution
→ backend confirms
→ update cache
```

Le frontend ne merge pas silencieusement une mission, transaction, prière, règle santé ou recommandation VTC.

---

## 9. Feature Modules

### 9.1 `feature_imperium/`

Screens V1 :

- `IMP-01` Dashboard ;
- `IMP-02` Mission Active ;
- `IMP-03` Inbox ;
- `IMP-04` Weekly Review ;
- `IMP-05` History ;
- `IMP-06` Settings.

Les anciens ecrans Imperium comme Morning Check-In, Mission Outcome, Day Finished, Replan Validation et Add Manual Mission ne sont pas des destinations top-level V1. Ils restent hors generation V1 tant qu'un contrat backend/frontend explicite ne les reactive pas.

ViewModels :

- `ImperiumDashboardViewModel` ;
- `ImperiumMissionActiveViewModel` ;
- `ImperiumInboxViewModel` ;
- `WeeklyReviewViewModel` ;
- `ImperiumHistoryViewModel` ;
- `ImperiumSettingsViewModel`.

Repositories :

- `ImperiumRepository` ;
- `MissionRepository` ;
- `ImperiumInboxRepository` ;
- `WeeklyReviewRepository` ;
- `ImperiumHistoryRepository`.

Navigation :

- top-level sidebar/bottom destination dashboard ;
- top-level sidebar/bottom destinations Mission Active, Inbox, Weekly Review, History et Settings ;
- settings/priorities nested graph futur seulement si documente ;
- aucune route detail mission separee en V1 ;
- replan surfaces futures ouvertes seulement depuis triggers backend ou actions utilisateur documentees.

### 9.2 `feature_vault/`

Screens V1 :

- `VAU-01` Dashboard ;
- `VAU-02` Add Income ;
- `VAU-03` Add Expense ;
- `VAU-04` Scan Ticket Capture ;
- `VAU-05` Receipt Review ;
- `VAU-06` Pressure Explain ;
- `VAU-07` Transactions ;
- `VAU-08` Transaction Edit ;
- `VAU-09` Categories ;
- `VAU-10` Wallet Update ;
- `VAU-11` Upcoming Expenses ;
- `VAU-12` Settings.

ViewModels :

- `VaultDashboardViewModel` ;
- `TransactionFormViewModel` ;
- `ReceiptReviewViewModel` ;
- `VaultTransactionsViewModel` ;
- `VaultSettingsViewModel`.

Repositories :

- `VaultRepository` ;
- `TransactionRepository` ;
- `ReceiptRepository` ;
- `FinancialPressureRepository`.

Navigation :

- dashboard, transactions, categories, settings top-level ;
- receipt capture to review ;
- sadaqa settings deep link to Path ;
- Pulse food stock handoff is backend event, not second validation screen.

### 9.3 `feature_vector/`

> **LIVRÉ (2026-10-22, appli 0.25.0-vector, lot V1 du kit Vector final du 2026-10-22).** Les décisions du kit
> remplacent la liste VEC-xx ci-dessous pour l'écran (pas d'écran Démarrer ni de saisie objectif/direction, pas de
> mode conduite, pas de dépenses/net, pas de connexion propre à Vector).
> - Même APK, troisième icône (`VectorActivity`, tâche séparée), session commune ; non connecté → « Connecte-toi
>   dans Imperium ». Thème du kit (vert forêt, ivoire, sauge, champagne ; Exo 2, Inter, JetBrains Mono ; logo
>   original non redessiné ; 54 pictogrammes convertis), barre latérale à trois entrées.
> - Branché : Ma session (Démarrer sans formulaire, Mettre en pause / Reprendre, Arrêter avec confirmation et clé
>   stable ; CA, courses effectuées = acceptées avec résultat réel, refusées ; objectif IA affiché s'il existe,
>   sinon « pas encore fixé »), Conseil de zone (trois zones au plus, GPS direct par l'appli de navigation avec le
>   nom de la zone), Historique (périodes en Europe/Paris, totaux, sessions, détail avec offres Toutes / Effectuées /
>   Refusées : « Offre » pour un refus, « CA » pour une course faite), terminal (chatbot commun, rôles VECTOR et
>   VOUS, actions proposées à valider), Réglages en quatre entrées (assistant : signaux, sons et aperçu, animations
>   réduites ; notifications ; Nourrir l'IA ouvert dans Imperium ; autorisations réelles).
> - Indisponible et dit comme tel : les sept flux d'information (avions, événements, métro-RER-Transilien, bus,
>   météo, SNCF, autoroutes : lot V2, sources autorisées par l'utilisateur), la dictée du terminal, l'envoi des
>   notifications.
> - **LIVRÉ (appli 0.26.0-assistant, lot V2-A)** : assistant de prise de course (doc 33, note « assistant de prise de
>   course ») — service d'accessibilité en lecture seule sur l'appli conducteur Bolt, halo par-dessus sans toucher,
>   sons, interrupteur actif dans Ma session (autorisation Android expliquée), carte « Dernière offre lue » pour
>   classer l'offre (acceptée / refusée / manquée), journal de lecture local dans Réglages › Assistant. Autorisations :
>   localisation, microphone, lecture des offres (la superposition et la capture d'écran ne sont pas nécessaires).

Screens V1 :

- `VEC-01` Dashboard ;
- `VEC-02` Start Session ;
- `VEC-03` Active Session ;
- `VEC-04` Manual Revenue ;
- `VEC-05` Manual Expense ;
- `VEC-06` Screenshot Upload ;
- `VEC-07` Where Should I Go ;
- `VEC-08` Recommendation Detail ;
- `VEC-09` Recommendation Feedback ;
- `VEC-10` Last Drop Zone ;
- `VEC-11` Session Review.

ViewModels :

- `VectorDashboardViewModel` ;
- `VectorSessionViewModel` ;
- `VectorRecommendationViewModel` ;
- `VectorScreenshotUploadViewModel` ;
- `VectorSessionReviewViewModel`.

Repositories :

- `VectorRepository` ;
- `VectorSessionRepository` ;
- `VectorRecommendationRepository` ;
- `VectorUploadRepository`.

Navigation :

- dashboard top-level ;
- active session driving-aware route ;
- recommendation request/detail/feedback ;
- Imperium VTC mission deep link ;
- no Bolt automation path.

### 9.4 `feature_pulse/`

> **LIVRÉ (2026-10-22, appli 0.18.0-pulse, kit Pulse du 2026-10-22).** Les fiches du kit (P01-P29)
> remplacent la liste PUL-xx ci-dessous pour l'écran ; les routes restent celles du backend.
> - Même APK qu'Imperium, deuxième icône (`PulseActivity`, tâche séparée) ; une seule session
>   (`AppSession` dans `core/network`) : se connecter dans l'une connecte l'autre.
> - Thème propre au kit (ivoire, saumon, Manrope / Inter / JetBrains Mono locales, figées en
>   graisses statiques), rail de six destinations : Aujourd'hui, Repas, Sport, Stock, Santé, Réglages.
> - Branché : tableau du jour, J'ai bu (eau ou autre), J'ai mangé (article du stock décompté après
>   validation serveur, ou « Autre » en un champ), repas du jour et brouillons, stock (correction
>   avec version, retrait), achats manuels, ticket photographié → lignes corrigibles → confirmation,
>   séances de la semaine, détail, déroulé local (brouillon gardé sur l'appareil, résultats envoyés
>   en un bloc à la fin), santé (valeurs sourcées, inconnu = tiret), douleurs, relevés, accords
>   demandés au moment du parcours, matériel, connexion, autorisations, bulle.
> - Diète (2026-10-22, appli 0.19.0-diet, serveur doc 40 §10 CODÉ) : Repas montre le prévu du jour,
>   la semaine proposée par le cerveau (Valider / Refuser, consigne facultative à la demande) et
>   les préparations ; Préparer (P05 : ingrédients comparés au stock, étapes, conditionnement et
>   conservation, Démarrer → manque = attention requise) ; Terminer (P06 : portions et poids
>   préremplis, une seule mutation) ; Courses (P08 : liste calculée par le serveur, cocher ne
>   crédite rien, les lignes cochées passent dans Enregistrer les achats) ; J'ai mangé propose
>   d'abord le repas prévu et prend sa portion préparée dans le stock. Imperium affiche la bannière
>   « Attention requise : préparation bloquée » (`GET /imperium/pulse/diet/attention`) qui ouvre
>   Nexus. Tant que `pulse.diet_enabled` est éteint, ces blocs disent « pas encore activée ».
> - Programme d'entraînement et signaux calculés indisponibles tant que `pulse.programs_enabled` /
>   `pulse.board_enabled` sont éteints (409 `…_DISABLED` lu comme « pas encore activé ») ; Nourrir
>   l'IA s'ouvre dans Imperium (même boîte, même serveur).
> - Pas encore : file d'actions hors ligne (aujourd'hui : clé d'idempotence stable par fenêtre,
>   saisie gardée en cas d'échec), dictée vocale.

Screens V1 :

- `PUL-01` Dashboard ;
- `PUL-02` Add Meal ;
- `PUL-03` Meal Confirm ;
- `PUL-04` Hydration ;
- `PUL-05` Plan Workout ;
- `PUL-06` Workout Log ;
- `PUL-07` Workout Adaptation ;
- `PUL-08` Body Snapshot ;
- `PUL-09` Pain Log ;
- `PUL-10` Meals ;
- `PUL-11` Workouts ;
- `PUL-12` Stock ;
- `PUL-13` Scan Pantry ;
- `PUL-14` Medical.

ViewModels :

- `PulseDashboardViewModel` ;
- `MealLogViewModel` ;
- `HydrationViewModel` ;
- `WorkoutViewModel` ;
- `StockViewModel` ;
- `PulseMedicalViewModel`.

Repositories :

- `PulseRepository` ;
- `MealRepository` ;
- `HydrationRepository` ;
- `WorkoutRepository` ;
- `StockRepository` ;
- `MedicalFeedRepository`.

Navigation :

- dashboard, meals, workouts, stock, medical top-level ;
- Path fasting constraints displayed as banners/disabled controls ;
- high pain or medical rule handoff asks Imperium only after backend acceptance.

### 9.5 `feature_path/`

Screens V1 :

- `PAT-01` Dashboard ;
- `PAT-02` Prayer Mark ;
- `PAT-03` Sadaqa Donation ;
- `PAT-04` Ghusl Required ;
- `PAT-05` Fasting Action ;
- `PAT-06` Adhkar Counter ;
- `PAT-07` Quran Progress ;
- `PAT-08` Mosque Detail ;
- `PAT-09` Mosques ;
- `PAT-10` Ghusl Addresses ;
- `PAT-11` Settings.

ViewModels :

- `PathDashboardViewModel` ;
- `PrayerViewModel` ;
- `SadaqaViewModel` ;
- `FastingViewModel` ;
- `AdhkarViewModel` ;
- `PathSettingsViewModel`.

Repositories :

- `PathRepository` ;
- `PrayerRepository` ;
- `SadaqaRepository` ;
- `FastingRepository` ;
- `MosqueRepository`.

Navigation :

- dashboard, mosques, ghusl addresses, settings top-level ;
- Vault settings deep link to `PAT-11d` for sadaqa percent ;
- sadaqa creates Vault handoff through backend ;
- fasting creates Pulse hydration constraint handoff only after backend confirmation.

---

## 10. Bulles flottantes (remplacent les widgets d'accueil)

> Décision utilisateur 2026-10-15 : PAS de widgets d'écran d'accueil. Les seuls
> « widgets » V1 sont des **bulles flottantes**, sur le modèle de la bulle de
> l'app Bolt chauffeur : une bulle déplaçable posée par-dessus les autres apps ;
> un tap ouvre un petit panneau avec l'information et les actions rapides.

### 10.1 Bulles V1

| Bulle | App | Contenu du panneau | Actions rapides |
|---|---|---|---|
| Mission en cours | Imperium | mission active unique (titre, échéance, progression) | Terminer ; Échouer (raison obligatoire, cf. 59 §12.4) ; Demander une replanification complète de la journée |
| Ajouter une transaction | Vault | formulaire court | Saisir une transaction : revenu OU dépense, montant, catégorie préremplie (table des libellés puis IA, doc 42 §7.0), livre business/perso déduit |
| Raccourci Path | Path | aucun panneau | Tap = ouvre directement l'app Path |
| Pulse | Pulse | panneau de cinq actions (kit Pulse 2026-10-22) | J'ai bu ; J'ai mangé ; Photographier le ticket ; Liste des courses ; Ouvrir Pulse — chaque action ouvre Pulse sur le même formulaire que dans l'appli ; ni séance ni douleur |
| Raccourci Vector | Vector | aucun panneau | Tap = ouvre directement l'app Vector |

Les cinq apps ont leur bulle (décision 2026-10-15, révisée le même jour). Imperium,
Vault et Pulse (kit du 2026-10-22, qui remplace le simple raccourci) ont un panneau
avec actions ; Path et Vector sont de simples raccourcis de lancement. La bulle Vector est un lanceur optionnel : Vector
V1 ne DÉPEND d'aucun overlay pour fonctionner, la règle du doc 08 reste respectée.

### 10.2 Technique et règles

Technique : fenêtre en superposition Android (permission « Afficher par-dessus les
autres apps », `SYSTEM_ALERT_WINDOW`), comme la bulle Bolt — pas l'API Bubbles
(liée aux notifications de conversation).

```text
Bulle (overlay)
→ tap → panneau
→ ViewModel → Repository → API → Backend
```

Règles :

- le panneau (Imperium, Vault) lit l'état à l'ouverture (pas de snapshot périodique ; plus de
  refresh WorkManager dédié) et affiche son état sync ;
- toute action affiche `pending` jusqu'à confirmation backend ; pas de succès local ;
- Terminer / Échouer passent par les endpoints mission existants
  (`POST …/missions/{id}/complete|fail`) ; jamais de seconde mission active ;
- « Replanification complète » envoie la demande (TBD `POST /api/imperium/replans/request`) ;
  la proposition s'ouvre ensuite dans `IMP.REPLAN.VALIDATE` pour validation — la bulle
  ne valide jamais un plan elle-même ;
- la transaction Vault passe par `POST /api/imperium/vault/transactions` avec
  `Idempotency-Key` ;
- la permission overlay est demandée au moment où l'utilisateur active une bulle,
  avec explication (doc 07 §Permissions) ;
- chaque bulle s'active / se désactive dans les Settings de son app.

### 10.3 Bulle ownership

| Bulle | Feature owner | Source backend |
|---|---|---|
| Mission en cours | Imperium | active mission Imperium |
| Ajouter une transaction | Vault | ledger Vault |
| Raccourcis Path / Pulse / Vector | app concernée | aucune (lancement d'app) |

---

## 11. Tablet Strategy

### 11.1 Galaxy Tab S10 Ultra as primary

Remplacé pour la V1 (décision 2026-10-16) : la surface de référence V1 est la **Galaxy Tab S8 portrait**, dimensions fluides ; ce qui suit décrit l'adaptation ultérieure S10/S11 Ultra paysage. La Galaxy Tab S10 Ultra landscape était la surface de référence. Les écrans sont conçus pour la décision rapide, la densité contrôlée et les panneaux persistants.

### 11.2 Three-column layout

Layout canonique :

```text
Sidebar | Content | Context Panel
```

| Zone | Largeur cible | Rôle |
|---|---:|---|
| Sidebar | 240dp | navigation primaire et app active. |
| Content | max 1280dp | écran principal, listes, dashboards, formulaires. |
| Context Panel | 320-480dp | assistant, détails, sync/conflict, preview, explication. |

### 11.3 Sidebar

La sidebar :

- remplace bottom nav sur tablette ;
- affiche uniquement destinations V1 ;
- garde app active visible ;
- peut porter un badge stale/sync sans masquer le label.

### 11.4 Content

Le contenu :

- évite les cartes imbriquées ;
- garde des dimensions stables ;
- utilise grids 2-3 colonnes selon densité ;
- ne masque pas les états sync.

### 11.5 Context Panel

Le panel contextuel :

- montre détails ou assistant sans quitter l'écran ;
- héberge conflit, explication, preview ou chat dock ;
- se ferme sans perdre l'état canonique ;
- n'est pas utilisé pour navigation primaire.

### 11.6 Phone support

Téléphone :

- bottom navigation ;
- routes plein écran ;
- bottom sheets ;
- moins de densité ;
- mêmes IDs et mêmes contrats que tablette.

---

## 12. Offline Strategy

### 12.1 Lecture offline

Lecture offline :

- afficher dernier snapshot Room disponible ;
- afficher timestamp ;
- état `cached` ou `stale` obligatoire ;
- désactiver décisions qui exigent une vérité live ;
- permettre consultation historique quand le cache suffit.

### 12.2 Write queue

Write queue :

- stocker payload validé côté forme ;
- stocker idempotency key ;
- stocker destination API ;
- stocker nombre de tentatives ;
- stocker état `pending`, `syncing`, `failed` ou `conflict` ;
- ne jamais marquer `synced` avant confirmation backend.

### 12.3 Sync retry

Retry :

- WorkManager avec backoff ;
- retry immédiat via bouton utilisateur ;
- pas de retry infini silencieux ;
- erreurs serveur non idempotentes exigent décision utilisateur ;
- upload audio/image reprend ou recommence selon capacité backend.

### 12.4 Conflict

Conflict :

- fetch de la version serveur ;
- affichage local vs serveur quand utile ;
- option sûre par défaut ;
- résolution explicite ;
- backend confirme la résolution ;
- cache mis à jour ensuite.

Exemples :

- transaction modifiée alors qu'une correction existe déjà ;
- mission terminée côté serveur pendant un brouillon local ;
- prière/fasting state divergeant après offline ;
- recommandation Vector stale utilisée après expiration.

### 12.5 Offline boundaries

Autorisé offline :

- lire dashboard cache ;
- préparer notes, dépenses, repas, hydratation, prière confirmée, feedback ;
- capturer audio/image en attente upload ;
- consulter historique cache.

Non autorisé comme vérité offline :

- créer mission active officielle ;
- recalculer priorité officielle ;
- confirmer solde officiel ;
- présenter recommandation VTC comme live ;
- produire sadaqa canonique sans handoff backend ;
- écrire mémoire long terme.

---

## 13. Security

### 13.1 JWT

JWT frontend V1 :

- le backend émet, valide et révoque les JWT ;
- le frontend transmet uniquement le bearer token aux endpoints autorisés ;
- le frontend ne décode jamais un JWT pour prendre une décision métier canonique ;
- access token court, refresh contrôlé, rotation côté backend ;
- logout efface token, cache sensible local et write queue sensible ;
- expiration, issuer, audience et algorithm restent des validations backend ;
- aucun token n'entre dans `UiState`, previews Compose, analytics, logs, screenshots ou widgets.

### 13.2 Secure storage

Stockage sécurisé Android cible :

- Android Keystore pour les clés locales ;
- stockage chiffré pour access/refresh tokens ;
- séparation stricte entre préférences UI non sensibles et secrets ;
- pas de secret dans Room non chiffré ;
- pas de secret dans fichier de config livré avec l'app ;
- aucun token en extra de navigation, deep link, route string ou saved state handle visible.

### 13.3 Encrypted preferences

Préférences chiffrées :

- autorisées pour secrets d'auth, identifiants de session et flags sensibles ;
- interdites comme source de vérité métier ;
- nettoyées au logout, à la révocation auth et en cas de corruption ;
- versionnées par schéma pour migration contrôlée ;
- jamais utilisées pour stocker audio brut, image brute, OCR brut, note santé sensible ou contenu spirituel sensible si Room/API offre un chemin plus sûr.

### 13.4 No secrets in UI

No secrets in UI :

- aucune API key pour [OCR service], OpenAI, Claude, n8n, backend admin ou service externe dans le frontend ;
- aucun secret affiché dans Compose, logs, previews, widgets, debug banners ou crash reports ;
- les screenshots UI ne doivent pas révéler token, cookie, Authorization header, refresh token ou payload sensible ;
- les erreurs affichées sont redaction-safe ;
- toute clé nécessaire aux modèles AI reste côté backend ou orchestration n8n.
- exception encadrée (décision 2026-10-15) : le panneau « Clés API » des AI Advanced
  Settings (doc 73) est un champ en ÉCRITURE SEULE — la clé collée part au backend
  et n'est jamais relue, stockée localement ni réaffichée ; seul un état
  « enregistrée / manquante » est visible.

### 13.5 Écran de connexion

Décision utilisateur 2026-10-15 : l'app propose la connexion par **clé maître
uniquement** (le backend accepte aussi email + mot de passe, doc 08, mais l'écran ne
l'expose pas). Contrat : `POST /api/auth/login` (`backend/app/schemas/auth.py`).

| Champ écran | Champ API | Règle |
|---|---|---|
| Adresse du serveur | — (base URL de l'app) | Bouton « Tester » : `GET /api/health` puis `/api/health/db`. |
| Clé maître | `master_key` | Champ masqué ; jamais stocké ; effacé après la tentative. |
| Nom de l'appareil | `device_label` | Obligatoire, pré-rempli avec le modèle (ex. « Galaxy Tab S8 »). |
| (invisible) | `device_fingerprint`, `platform` | Remplis automatiquement. |

Réponse stockée en stockage sécurisé (§13.2) : `access_token`, `refresh_token`,
`device_id`. Refresh et logout envoient `{refresh_token, device_id}`
(`/api/auth/refresh`, `/api/auth/logout`). V1 (décision utilisateur 2026-10-15) : UN
seul appareil connecté, qui est l'appareil de confiance — PAS de liste d'appareils ni de
révocation dans les Settings. Ajouter un autre appareil se fait à la main côté serveur
(les endpoints `GET /api/auth/devices` et `POST /api/auth/devices/{id}/revoke` restent
côté backend, sans écran).

Le secret de déverrouillage du kill switch (doc F09 §4) est DISTINCT de la clé
maître et ne doit jamais lui être identique : la clé maître est saisie sur la
tablette, le secret F09 ne doit jamais y vivre.

---

## 14. Performance

### 14.1 LazyColumn

Règles `LazyColumn` :

- listes longues rendues via `LazyColumn` ou `LazyVerticalGrid`, jamais via `Column` scrollée non bornée ;
- clés stables obligatoires pour missions, transactions, recommandations, repas, workouts, prières et logs ;
- item content léger, sans calcul métier, parsing lourd ou chargement image synchrone ;
- sections sticky autorisées uniquement si elles améliorent la lecture ;
- pas de `LazyColumn` imbriquée non contrainte ;
- placeholders, empty states et loading rows respectent les composants foundation du document 62.

### 14.2 Image loading

Image loading :

- loader Android dédié type Coil ou équivalent Compose-ready ;
- dimension cible connue avant chargement ;
- thumbnails pour listes, image complète seulement en détail ;
- placeholders et error states explicites ;
- cache mémoire/disque contrôlé par le loader ;
- aucune image brute plein format dans `UiState`, ViewModel ou saved state ;
- uploads image passent par repository et sync layer, pas par composant Compose direct.

### 14.3 Pagination

Pagination :

- pagination backend-driven pour historiques, transactions, recommandations, logs Pulse et listes de mosquées ;
- curseur ou page token conservé dans repository/cache, pas dans composant visuel ;
- chargement suivant déclenché par seuil de scroll ;
- retry visible en pied de liste ;
- refresh ne duplique pas les items ;
- Paging 3 autorisé si le backend expose un contrat compatible ;
- pas de liste infinie gardée intégralement en mémoire.

### 14.4 Memory rules

Memory rules :

- `UiState` contient des IDs, URLs, métadonnées et snapshots légers, pas de blobs lourds ;
- audio, image, OCR et exports passent par fichiers temporaires contrôlés et repositories ;
- ViewModels ne conservent pas de contexte Android long-lived ;
- caches Room bornés par feature et horodatés ;
- cleanup WorkManager pour uploads terminés ou abandonnés ;
- les panneaux de bulles lisent un état compact ;
- navigation arguments limités aux IDs stables et paramètres courts.

---

## 15. Non Goals

Les surfaces suivantes sont explicitement exclues du frontend V1 :

- iOS ;
- Web ;
- Desktop ;
- Compose Multiplatform ;
- Wear OS ;
- Android Auto ;
- OCR runtime V1 ;
- AI runtime local frontend.

Conséquences :

- aucun dossier `android/`, `frontend/` ou fichier Kotlin n'est créé par cette documentation ;
- aucune architecture multiplateforme n'est prévue en V1 ;
- OCR, vision via [OCR service], routage AI et modèles locaux restent backend/orchestration ;
- le frontend Android peut capturer ou uploader, mais il n'exécute pas l'OCR runtime V1 ;
- le [local model] router/scorer reste côté backend, pas dans le frontend.

---

## 16. Frontend Generation Readiness

### 16.1 Gate

```text
READY_FOR_COMPOSE_SCAFFOLD = YES
```

Ce statut signifie : les documents canoniques permettent de générer un scaffold Android Compose futur. Il ne signifie pas qu'un scaffold Android existe déjà dans ce repo.

### 16.2 Conditions

Conditions remplies pour `READY_FOR_COMPOSE_SCAFFOLD` :

| Condition | Source canonique | Statut |
|---|---|---|
| DS canonique | `docs_master/59_DESIGN_SYSTEM_V1_DRAFT.md` | OK |
| Tokens | `docs_master/60_DESIGN_SYSTEM_TOKENS_KT.md` | OK |
| Components | `docs_master/62_DESIGN_SYSTEM_COMPONENT_CATALOG.md` | OK |
| Composite Components | `docs_master/61_DESIGN_SYSTEM_COMPOSITE_COMPONENTS.md` | OK |
| Screen Architecture | `docs_master/63_FRONTEND_ARCHITECTURE_V1.md` | OK |

### 16.3 Guardrails

Un scaffold Compose futur doit respecter :

- `ImperiumTheme` et tokens des documents 59/60 ;
- composants foundation du document 62 ;
- composants composites du document 61 ;
- architecture repository/navigation/state/sync de ce document ;
- cinq modules feature V1 seulement ;
- stratégie tablette Galaxy Tab S10 Ultra + téléphone Android ;
- sync states `pending|syncing|synced|failed|conflict|cached|stale` ;
- non goals de la section 15.

Un générateur frontend ne peut pas promouvoir un non-goal en surface V1 ni créer de logique métier frontend autonome.

**Document version :** 1.0
**Statut :** FRONTEND ARCHITECTURE V1 — ready for future Android scaffolding, not implemented yet.
**Last updated :** 2026-06-02
