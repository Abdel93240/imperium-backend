# 62 — Design System Foundation Component Catalog V1

**Version :** 1.0
**Sources de verite :** `docs_master/59_DESIGN_SYSTEM_V1_DRAFT.md`, `docs_master/60_DESIGN_SYSTEM_TOKENS_KT.md`, `docs_master/61_DESIGN_SYSTEM_COMPOSITE_COMPONENTS.md`
**Cible :** future implementation Android natif Kotlin + Jetpack Compose Material 3
**Statut :** SPECIFICATION ONLY — aucun composant Compose reel, fichier Kotlin, Android frontend ou backend runtime n'est cree par ce document.

Ce document catalogue les composants UI foundation reutilisables du Design System V1. Les noms commencent par `Imperium` pour stabiliser le namespace, mais ces composants sont cross-app : Imperium, Vault, Vector, Pulse et Path doivent les utiliser avec le theme actif.

Le document 59 reste canonique pour le Design System V1. Le document 60 reste canonique pour les tokens Kotlin Compose. Le document 61 reste canonique pour les composants dynamiques/composes metier et la regle : `premium asset must not contain dynamic data`.

---

## 1. Component Contract

Chaque composant foundation V1 doit respecter le meme contrat :

| Field | Rule |
|---|---|
| Purpose | Decrire la fonction UI generique, jamais une strategie metier autonome. |
| Compose responsibility | Rendre l'etat, collecter une saisie ou declencher une action explicite. La decision canonique vient du backend/n8n/AI router. |
| Tokens used | Utiliser uniquement les tokens de `60_DESIGN_SYSTEM_TOKENS_KT.md` et les mappings du document 59. |
| Variants | Rester V1, sans surface V2/V3. |
| States | Rendre les etats requis, sans fake success. |
| Accessibility rules | Label visible ou content description, ordre de focus stable, cible tactile adaptee, couleur jamais seule. |
| Responsive behavior Tab S10 Ultra | Landscape tablet est la surface de reference : sidebar 240dp, contenu max 1280dp, panel contextuel 320-480dp quand utile. |
| When to use | Cas clair et repetable dans plusieurs apps. |
| When not to use | Cas metier compose, navigation V2/V3, automatisation non validee, decoration pure. |

---

## 2. Theme Awareness

Un meme composant adopte les couleurs et tokens de l'app active via le theme Compose courant.

| App active | Palette source | Accent behavior |
|---|---|---|
| Imperium | `ImperiumColors` | Accent gold rare, max 1 accent visible par ecran. |
| Vault | `VaultColors` | Montants en `ImperiumFontFamilies.Numeric`; bronze reserve aux obligations et realite financiere. |
| Vector | `VectorColors` | Accent cyan pour actions; `VectorHaloColors` reserve uniquement au halo conduite. |
| Pulse | `PulseColors` | Accent coral pour actions pratiques de sante, sans complexite visuelle. |
| Path | `PathColors` | Accent gold/emerald pour sadaqa et rappels spirituels; arabe avec font Arabic quand applicable. |

Regles :

- Les composants utilisent `Primary`, `Secondary`, `Background`, `Surface`, `SurfaceVariant`, `Border`, `Divider`, `TextPrimary`, `TextSecondary`, `TextMuted`, `Accent` depuis l'app active.
- Les etats confirmes utilisent `SemanticStateColors.Success`, `Warning`, `Error`, `Info`; la couleur d'etat doit etre accompagnee d'une icone ou d'un libelle.
- Les composants ne lisent pas directement une couleur hardcodee sauf si le token est explicitement fixe par le document 60.
- Les composants ne changent pas leur contrat selon l'app : seul le theme, le copy et les donnees changent.
- Les composants Vector en mode conduite doivent rester lisibles rapidement et reduire les interactions longues.

---

## 3. Buttons

| Component | Purpose | Compose responsibility | Tokens used | Variants | States | Accessibility rules | Responsive behavior Tab S10 Ultra | When to use | When not to use |
|---|---|---|---|---|---|---|---|---|---|
| ImperiumPrimaryButton | Action principale explicite d'un ecran ou d'un formulaire. | Declencher une intention utilisateur validee par backend ou workflow. | App `Primary` or `Accent`, `TextPrimary`, `Radius.Button`, `Spacing.MD`, `IconSize.Action`, `Typography.BodyMedium`, `Elevation.L1/L2`. | Text only, icon leading, icon trailing, full width in sheets/forms. | Enabled, loading, disabled, pressed, focused. Loading bloque le double tap et affiche progress. | Libelle visible obligatoire; content description si icon-only future; minimum 48dp height; focus ring visible. | Max width 360dp sauf sticky action bar; un seul primary visible dans la zone active. | Sauvegarder, confirmer, demarrer une mission/session, valider une saisie. | Plusieurs actions concurrentes, action destructive, navigation passive. |
| ImperiumSecondaryButton | Action alternative importante mais non dominante. | Declencher une action secondaire sans voler la hierarchie au primary. | App `Secondary`, `Border`, `TextPrimary`, `Radius.Button`, `Spacing.MD`, `Elevation.L0/L1`. | Filled subdued, outline, icon leading. | Enabled, loading, disabled, pressed, focused. | Libelle distinct du primary; ordre de focus apres l'action principale. | Peut etre groupe avec primary dans une action row; largeur stable. | Voir detail, enregistrer correction, ouvrir explication. | Action principale unique, action dangereuse. |
| ImperiumGhostButton | Action discrete, annulation ou lien utilitaire. | Exposer une action faible sans creer de surface visuelle lourde. | Transparent surface, `TextSecondary`, `Accent` on focus/press, `Radius.Button`, `Spacing.SM/MD`. | Text, icon leading, compact. | Enabled, disabled, pressed, focused. Pas de loading long. | Contraste AA; label clair comme Annuler, Retour, Ignorer. | Compact dans top bars, dialogs et sheets; ne doit pas agrandir les panels. | Annuler, fermer, ignorer, action utilitaire faible. | Validation, paiement, suppression, action qui modifie fortement les donnees. |
| ImperiumDestructiveButton | Action irreversible ou negative confirmee. | Declencher une intention destructive apres garde-fou UI. | `SemanticStateColors.Error`, app `Surface`, `TextPrimary`, `Radius.Button`, `Spacing.MD`, `Elevation.L1/L2`. | Filled, outline destructive, confirm dialog action. | Enabled, loading, disabled, pressed, focused. | Libelle explicite; jamais icone seule; confirmation requise pour suppression/annulation forte. | Dans Dialog/BottomSheet L3; jamais comme action globale persistante. | Annuler par ecriture inverse, supprimer un brouillon, marquer echec avec raison. | Depense normale, erreur informative, action non irreversible. |
| ImperiumIconButton | Action compacte portee par une icone standard. | Declencher une intention courte et explicite sans porter de decision metier. | App `Accent`, `SurfaceVariant`, `TextPrimary`, `Radius.Button`, `Spacing.SM`, `IconSize.Action`. | Standard, tonal, ghost, top bar. | Enabled, loading, disabled, pressed, focused. | Content description obligatoire; cible tactile 48dp; tooltip ou label accessible si l'icone est ambigue. | Taille fixe pour eviter les shifts dans top bars, listes et panels. | Voice shortcut, filtre, refresh, close, open detail. | Action primaire d'ecran, action destructive seule, libelle metier ambigu. |
| ImperiumVoiceButton | Bouton micro compact pour lancer une saisie vocale courte. | Declencher `ImperiumVoiceInput` ou une permission audio explicite. | App `Accent`, `Surface`, `Border`, `Radius.Button`, `IconSize.Action`, `SemanticStateColors`. | Top bar, inline, floating compact. | Idle, recording, uploading, disabled, focused, error. | Etat annonce; content description obligatoire; ne doit jamais envoyer audio critique sans confirmation. | Stable en top bar ou quick action; minimum 48dp, 64dp en mode conduite. | Capture rapide Inbox, note de mission, commande courte. | Remplacer le pipeline STT, valider une action canonique sans backend. |

---

## 4. Inputs

| Component | Purpose | Compose responsibility | Tokens used | Variants | States | Accessibility rules | Responsive behavior Tab S10 Ultra | When to use | When not to use |
|---|---|---|---|---|---|---|---|---|---|
| ImperiumTextField | Collecter texte court ou moyen. | Gerer valeur locale, validation UI et emission d'un payload explicite. | App `SurfaceVariant`, `Border`, `TextPrimary`, `TextSecondary`, `TextMuted`, `Radius.Input`, `Spacing.MD`, `IconSize.InputAdornment`, `Typography.BodyMedium`. | Single-line, multi-line, leading icon, trailing clear/action. | Idle, focused, error, disabled, filled. | Label visible; supporting/error text annonce; ordre de focus logique; pas de placeholder comme seul label. | Largeur max 720dp dans forms; multi-line evite de pousser les actions sticky. | Notes, raison d'echec, description transaction, recherche libre courte. | Montants, choix enum, saisie longue en mode conduite Vector. |
| ImperiumNumberField | Collecter nombre, montant ou compteur. | Valider format, bornes, unite et precision avant envoi. | `ImperiumFontFamilies.Numeric`, `Radius.Input`, `Spacing.MD`, app text/surface tokens, `SemanticStateColors.Error`. | Integer, decimal, money, percent, duration. | Idle, focused, error, disabled, filled. | Unite visible et annoncee; clavier numerique; erreur textuelle, pas couleur seule. | Alignement numerique stable; largeur fixe pour montants KPI/forms. | Vault montants, objectifs CA Vector, pages Quran, quantites Pulse. | Texte libre, valeurs que le backend doit calculer seul. |
| ImperiumSearchField | Filtrer ou chercher dans une liste locale/serveur. | Maintenir query, clear, debounced submit si necessaire. | App `SurfaceVariant`, `Border`, `TextSecondary`, `IconSize.InputAdornment`, `Radius.Input`, `Spacing.MD`. | Compact, full width list header, with filter action. | Idle, focused, loading, error, disabled. | Label ou hint annonce; bouton clear accessible; resultat count annonce si disponible. | Dans list/detail, largeur max 880dp; ne remplace pas navigation primaire. | Transactions, missions, categories, mosques, stock food. | Creation de donnees, commande vocale, decision AI. |
| ImperiumVoiceInput | Capturer une commande ou note vocale rapide. | Gerer idle/recording/uploading/processed et transmettre audio au pipeline STT. | App `Accent`, `Surface`, `Border`, `Radius.Button`, `IconSize.Action/AppEmblem`, `SemanticStateColors.Warning/Error/Success`. | Circular 64dp, inline mic button, voice-first prompt. | Idle, recording, uploading, processed, error, disabled, focused. | Etat visible et annonce; bouton minimum 64dp; feedback haptique possible; transcription confirmable. | En mode conduite, peut remplacer les champs longs; position stable et facilement atteignable. | Driving, fatigue, note rapide, feedback court. | Donnees critiques sans confirmation, transcription par LLM principal sans Whisper/faster-whisper. |

---

## 5. Selection

| Component | Purpose | Compose responsibility | Tokens used | Variants | States | Accessibility rules | Responsive behavior Tab S10 Ultra | When to use | When not to use |
|---|---|---|---|---|---|---|---|---|---|
| ImperiumToggle | Activer/desactiver une preference locale ou option binaire. | Changer un boolean explicite et afficher sync si backend requis. | App `Accent`, `SurfaceVariant`, `Border`, `SemanticStateColors`, `Radius.Chip`, `Spacing.SM`. | Switch row, compact toggle. | On, off, disabled, focused, syncing, conflict. | Libelle visible; etat annonce; ne pas compter sur la position seule. | Ligne stable dans settings deux colonnes; pas en dense dashboard conduite. | Preferences, filtres persistants, options de formulaire. | Action immediate irreversible, choix multi-option. |
| ImperiumCheckbox | Selectionner zero, une ou plusieurs options. | Maintenir selection locale jusqu'a validation. | App `Accent`, `Border`, `TextPrimary`, `Spacing.SM`, `IconSize.Action`. | Standard, row checkbox, tri-state future only if backend supports. | Checked, unchecked, indeterminate, disabled, focused. | Label associe; group role si liste; cible 48dp. | Listes en colonnes possibles; labels ne doivent pas tronquer les obligations. | Checklist, consentement, filtres multiples. | Choix exclusif, action instantanee critique. |
| ImperiumRadio | Choisir une option exclusive. | Maintenir une valeur unique dans un groupe nomme. | App `Accent`, `Border`, `TextPrimary`, `Spacing.SM`, `IconSize.Action`. | Radio list, card row selection. | Selected, unselected, disabled, focused. | Group label obligatoire; annonce position et selection. | Peut devenir two-column si labels courts; ordre de lecture reste stable. | Source wallet unique, choix de categorie exclusive, statut. | Multi-selection, action primaire, navigation top-level. |
| ImperiumSegmentedControl | Basculer entre 2-5 vues ou modes proches. | Changer un mode d'affichage ou une option courte sans navigation lourde. | App `SurfaceVariant`, `Accent`, `TextPrimary`, `TextSecondary`, `Radius.Chip`, `Spacing.XS/SM`, `Typography.Label`. | 2, 3, 4, 5 segments max; icon+label. | Selected, unselected, disabled, focused. | Chaque segment a libelle; role tab/segmented selon usage. | Largeur stable; sur Tab peut rester dans toolbar ou form header. | Onglets internes, cash/bank/crypto, daily/weekly/monthly. | Navigation app principale, longues listes d'options, mode conduite avec labels longs. |
| ImperiumFilterChip | Filtrer une liste avec une option courte. | Maintenir ou emettre un filtre explicite sans modifier les donnees canoniques. | App `SurfaceVariant`, `Accent`, `Border`, `TextPrimary`, `TextSecondary`, `Radius.Chip`, `Spacing.XS/SM`. | Single-select, multi-select, with count. | Selected, unselected, disabled, focused, loading count. | Libelle visible; etat selectionne annonce; count textuel si present. | Wrap controle; hauteur stable dans les toolbars liste. | Inbox filters, history filters, categories read views. | Navigation top-level, action destructive, choix long ou ambigu. |

---

## 6. Navigation

| Component | Purpose | Compose responsibility | Tokens used | Variants | States | Accessibility rules | Responsive behavior Tab S10 Ultra | When to use | When not to use |
|---|---|---|---|---|---|---|---|---|---|
| ImperiumTopBar | Identifier l'ecran et exposer actions globales courtes. | Rendre title, subtitle, back/menu, sync/action icons. | App `Primary`, `TextPrimary`, `TextSecondary`, `IconSize.TopBarAction`, `Elevation.L4`, `Spacing.MD/XL`, `Typography.H3/H4`. | Standard, compact driving, floating. | Default, scrolled, loading/syncing, offline. | Title annonce; icons labellisees; back toujours predictible. | Height normale 64dp; Vector driving peut descendre a 40dp. | Routes, sheets larges, dashboards. | Remplacer sidebar, afficher trop d'actions, porter une decision metier. |
| ImperiumSidebar | Navigation primaire tablet. | Afficher destinations V1 autorisees et app active. | App `Primary/Surface`, `Accent`, `TextPrimary`, `IconSize.Navigation`, `Spacing.MD/XL`, `Elevation.L0/L1`. | Expanded 240dp, collapsed rail future. | Active, inactive, disabled, focused, stale badge. | Destination annoncee; active label visible; ordre stable. | Obligatoire comme navigation primaire Tab S10 Ultra landscape hors mode conduite. | Dashboards et top-level tabs. | Phone portrait, Vector driving mode, surface V2/V3. |
| ImperiumBottomNavigation | Navigation primaire phone. | Afficher 3-6 destinations top-level V1. | App `Background/Surface`, `Accent`, `TextSecondary`, `IconSize.Navigation`, `Typography.Label`, `Elevation.L4`. | 3, 4, 5, 6 items. | Active, inactive, disabled, focused. | Libelle visible; item actif pas seulement couleur. | Non primaire sur Tab S10 Ultra; absent ou remplace par sidebar. | Phone portrait seulement. | Tablet landscape, dialogs, nested panes. |
| ImperiumTabBar | Navigation secondaire dans un domaine. | Changer un sous-onglet sans quitter la route. | App `SurfaceVariant`, `Accent`, `Divider`, `TextPrimary`, `TextSecondary`, `Typography.Label`. | Underline tabs, contained tabs. | Active, inactive, disabled, focused, loading count. | Role tablist; selected annonce; count visible. | Peut s'etendre dans content max 1280dp; garde hauteur fixe. | Historique, categories, settings sections. | Destinations app principales, actions destructives. |
| ImperiumDrawer | Navigation ou context panel temporaire. | Afficher menu/panel uniquement quand sidebar permanente impossible. | App `Surface`, `Border`, `Elevation.L3`, `Radius.Dialog/BottomSheet`, `Spacing.LG/XL`. | Modal drawer, dismissible drawer. | Open, closed, focused, scrim active. | Focus trap; dismiss accessible; scrim annonce modal. | Rare sur Tab; preferer sidebar ou right panel persistant. | Phone/tablet medium, navigation secondaire temporaire. | Tab landscape top-level, formulaires critiques. |
| ImperiumDeepLinkTarget | Surface d'arrivee pour deep link autorise. | Rendre le contexte, l'etat de sync et une action de retour sans valider l'action canonique. | App `Surface`, `Accent`, `Border`, `TextPrimary`, `TextSecondary`, `Radius.Card`, `Spacing.MD/LG`. | Inline context, full screen landing, stale/cached target. | Loading, ready, stale, missing, error, focused. | Destination annoncee; fallback clair; aucune information cachee derriere la couleur seule. | Peut ouvrir un detail ou ramener vers la destination top-level associee. | Deep links resource-oriented autorises par le contrat navigation. | Creer une destination top-level, contourner backend validation. |

---

## 7. Feedback

| Component | Purpose | Compose responsibility | Tokens used | Variants | States | Accessibility rules | Responsive behavior Tab S10 Ultra | When to use | When not to use |
|---|---|---|---|---|---|---|---|---|---|
| ImperiumSnackbar | Feedback temporaire apres action. | Afficher resultat court avec action optionnelle. | App `SurfaceVariant`, `TextPrimary`, `SemanticStateColors`, `Radius.Card`, `Spacing.MD`, `Elevation.L3`. | Info, success confirmed, warning, error with action. | Visible, dismissed, action focused. | Live region; action label clair; temps suffisant. | Ancre bas centre ou bas panel; ne masque pas sticky action. | Sync confirme, action annulee, erreur recuperable. | Decision critique, conflit complexe, message persistant. |
| ImperiumToast | Message tres court non critique. | Afficher info ephemeral sans action. | App `SurfaceVariant`, `TextPrimary`, `Radius.Chip`, `Spacing.SM`, `Elevation.L2`. | Neutral, info. | Visible, dismissed. | Ne pas porter une information indispensable; contraste AA. | Position basse, courte; evite mode conduite sauf confirmation simple. | Copie, sauvegarde locale non critique. | Erreur, conflit, validation, data stale. |
| ImperiumBanner | Message persistant dans une surface. | Rendre alerte, info ou recommandation avec CTA. | `SemanticStateColors`, app `SurfaceVariant`, `Border`, `TextPrimary`, `IconSize.Action`, `Radius.Card`, `Spacing.MD`. | Info, warning, error, offline, stale. | Visible, dismissed, loading action. | Icone + libelle; CTA accessible; pas couleur seule. | Peut occuper top du main column ou right panel 320dp. | Offline, stale, recommandation AI, pression financiere. | Simple success ephemeral, decoration. |
| SyncBanner | Bannière globale de sync/offline/cache. | Rendre un etat global `ImperiumSyncState` qui affecte la confiance de l'ecran. | `SemanticStateColors`, app `SurfaceVariant`, `Border`, `TextPrimary`, `TextSecondary`, `Radius.Card`, `Spacing.MD`. | Offline, stale, syncing, failed, conflict, cached. | Visible, dismissed if safe, retrying, focused action. | Etat textuel obligatoire; timestamp si cache/stale; CTA retry labellise. | En haut du main content; ne masque pas l'action principale sticky. | Dashboard stale, offline global, write queue bloquee. | Statut discret d'une ligne ou d'une card, utiliser `SyncStateChip`. |
| ImperiumAlertDialog | Confirmation ou blocage court. | Focus trap, title, body, primary/secondary/destructive actions. | App `Surface`, `TextPrimary`, `TextSecondary`, `Radius.Dialog`, `Elevation.L3`, `Spacing.LG/XL`, `SemanticStateColors.Error`. | Confirm, destructive, warning, info. | Open, loading action, disabled action. | Role dialog; focus initial sur action sure; dismiss explicite. | Max width 720-760dp; jamais plein ecran sur Tab sauf contenu complexe. | Confirmer annulation, expliquer blocage, conflit simple. | Formulaire long, workflow multi-etapes. |
| SyncStateChip | Afficher etat de sync/cache/stale. | Rendre `ImperiumSyncState` avec texte, icon et timestamp optionnel. | `SemanticStateColors`, app `TextSecondary`, `SurfaceVariant`, `Radius.Chip`, `Spacing.XS/SM`, `Typography.Label`, `IconSize.Inline`. | Pending, syncing, synced, failed, conflict, cached, stale. | Normal, focused if clickable, loading spinner. | Etat textuel obligatoire; timestamp annonce si decision-grade. | Compact dans cards/list rows; ne doit pas deformer les lignes. | Toute donnee backend ou cachee. | Statut metier sans lien sync, decoration verte. |

---

## 8. Containers

| Component | Purpose | Compose responsibility | Tokens used | Variants | States | Accessibility rules | Responsive behavior Tab S10 Ultra | When to use | When not to use |
|---|---|---|---|---|---|---|---|---|---|
| ImperiumCard | Surface statique d'information. | Grouper contenu lisible sans action principale. | App `Surface`, `Border`, `Radius.Card`, `Spacing.MD/LG`, `Elevation.L1`, `TextPrimary`. | Flat, outlined, subtle elevated. | Default, loading child, stale child. | Heading structure claire; decorative assets hidden. | Grid 2-3 colonnes max; pas de card dans card. | KPI, resume, bloc info. | Clickable action card, modal, nested decoration. |
| ImperiumInteractiveCard | Surface tap/click avec action ou navigation. | Gerer press/focus et action explicite. | App `SurfaceVariant`, `Border`, `Accent`, `Radius.Card`, `Elevation.L1/L2`, `Spacing.MD/LG`. | Navigation card, selectable card, action card. | Default, pressed, focused, disabled, loading. | Role button/link; target min 48dp; action annoncee. | Taille stable en grid; focus ring visible. | Ouvrir detail, choisir une recommandation, selectionner une zone. | Contenu purement statique, action destructive sans dialog. |
| ImperiumBottomSheet | Surface temporaire ancree bas ou cote. | Rendre formulaire/action contextuelle avec scrim/focus. | App `Surface`, `Border`, `Radius.BottomSheet`, `Elevation.L3`, `Spacing.LG/XL`. | Bottom phone, right side-sheet Tab 360-480dp, expanded. | Open, closing, loading, error. | Focus trap; drag handle labelled si utile; actions sticky accessibles. | Sur Tab preferer side-sheet 480dp ancre au contexte. | Forms rapides, detail row, ajout transaction. | Rapport long, navigation primaire, dashboard. |
| ImperiumDialog | Modal generique centre. | Encapsuler contenu court ou decision bloquante. | App `Surface`, `Radius.Dialog`, `Elevation.L3`, `Spacing.LG/XL`, `TextPrimary`. | Info, form short, selection picker. | Open, loading, error, disabled action. | Role dialog; focus trap; close accessible. | Max 720-760dp; deux colonnes seulement si necessaire. | Morning check-in, finish day, picker court. | Long workflow, list/detail, navigation top-level. |
| ImperiumModalFrame | Cadre modal pour workflow plus riche. | Structurer header, content, actions, optional side panel. | App `Surface`, `SurfaceVariant`, `Border`, `Radius.Dialog`, `Elevation.L3`, `Spacing.XL`. | Two-column modal, wizard frame, review frame. | Open, loading, error, conflict. | Landmarks internes; progression annoncee; actions sticky. | Max 1040dp; peut avoir timeline gauche et panel droit. | Weekly review interactive, correction complexe. | Simple confirmation, toast/snackbar. |
| ImperiumSectionHeader | Titre de section avec action optionnelle. | Rendre hierarchy, subtitle, optional small action. | App `TextPrimary`, `TextSecondary`, `Accent`, `Spacing.SM/MD`, `Typography.H3/H4/Label`. | Plain, with action, with sync chip. | Default, loading count, stale. | Heading level coherent; action separee et labellisee. | Garde hauteur stable; aligne grids/listes. | Diviser dashboard, settings, list sections. | Remplacer top bar, contenir un gros CTA. |
| ImperiumContextPanel | Panneau contextuel persistant tablette. | Afficher detail, statistiques ou sync context sans devenir navigation primaire. | App `Surface`, `Border`, `Divider`, `TextPrimary`, `TextSecondary`, `Spacing.LG/XL`. | Right panel 320dp, wide panel 480dp, empty panel. | Ready, loading, empty, stale, offline, error. | Landmark ou heading; ordre de focus apres main content; close/resize seulement si autorise. | Largeur 320-480dp; absent ou inline sur telephone. | Mission progress, status dashboard, preview inbox, detail history. | Phone primary navigation, modal bloquant, card imbriquee. |

---

## 9. States

| Component | Purpose | Compose responsibility | Tokens used | Variants | States | Accessibility rules | Responsive behavior Tab S10 Ultra | When to use | When not to use |
|---|---|---|---|---|---|---|---|---|---|
| ImperiumLoadingState | Afficher chargement initial ou blocant. | Montrer progress/skeleton sans inventer de donnees. | App `Surface`, `TextSecondary`, `Accent`, `Spacing.LG/XL`, `IconSize.PremiumAsset`. | Full screen, card, inline. | Loading, slow loading. | Live region; libelle "Chargement" ou equivalent; animation reduite si besoin. | Centre dans content max; garde dimensions finales approximatives. | Chargement initial, workflow pending. | Sync discret d'une ligne, fake content. |
| ImperiumEmptyState | Expliquer une absence de donnees utile. | Rendre copy, illustration/icon et CTA legitime. | App `Surface`, `TextPrimary`, `TextSecondary`, `Accent`, `Spacing.XL`, `IconSize.PremiumAsset`. | Full list empty, panel empty, first-use. | Empty, filtered empty. | Message explicite; CTA accessible; illustration decorative si non informative. | Max 720dp centre ou dans pane; ne prend pas tout l'ecran si liste secondaire. | Aucun historique, aucun resultat filtre. | Erreur, offline, stale data. |
| ImperiumErrorState | Afficher une erreur recuperable. | Montrer cause lisible, retry/report action. | `SemanticStateColors.Error`, app `Surface`, `TextPrimary`, `TextSecondary`, `Spacing.LG`, `IconSize.PremiumAsset`. | Full screen, card, inline. | Error, retrying, failed retry. | Texte obligatoire; ne pas exposer secrets; retry labellise. | Peut vivre dans panel concerne; evite de bloquer toute app si partiel. | API failed, workflow failed, validation server. | Conflit de donnees, offline simple. |
| ImperiumOfflineState | Indiquer absence reseau et valeur cachee. | Afficher mode offline, timestamp cache, actions disponibles. | `SemanticStateColors.Warning/Info`, app `SurfaceVariant`, `TextPrimary`, `TextSecondary`, `Radius.Card`. | Full screen, banner, chip. | Offline, cached, stale. | Etat textuel + timestamp; pas couleur seule. | En dashboard, banner top; en conduite, message minimal. | Reseau perdu, cache acceptable. | Erreur serveur, conflit validation. |
| ImperiumConflictState | Signaler divergence local/serveur. | Bloquer fake success et guider resolution. | `SemanticStateColors.Error`, app `Surface`, `Border`, `Radius.Card/Dialog`, `Spacing.LG`. | Inline conflict, dialog conflict, review card. | Conflict, resolving, resolved, failed. | Raisons et options explicites; focus sur action sure. | Detail dans right panel ou modal 720dp; preserve contexte original. | Sync conflict, double update, backend disagreement. | Simple validation field, warning faible. |
| ImperiumSkeleton | Placeholder structurel pendant chargement. | Reserver dimensions sans contenu dynamique faux. | App `SurfaceVariant`, `TextMuted`, `Radius.Card/Input/Chip`, `Spacing.SM/MD`. | Text line, card, list row, metric. | Loading, shimmer disabled/reduced motion. | Mark non-informative for screen reader; announce parent loading. | Respecte dimensions finales pour eviter layout shift. | Listes, KPI, cards pendant fetch. | Erreur, empty final, donnees inventees. |

---

## 10. Data Display

| Component | Purpose | Compose responsibility | Tokens used | Variants | States | Accessibility rules | Responsive behavior Tab S10 Ultra | When to use | When not to use |
|---|---|---|---|---|---|---|---|---|---|
| ImperiumMetricCard | Afficher une mesure importante avec contexte. | Rendre label, valeur, unite, delta, sync chip. | App `Surface`, `TextPrimary`, `TextSecondary`, `Accent`, `Radius.Card`, `Elevation.L1`, `ImperiumFontFamilies.Numeric`. | Compact, standard, hero metric. | Normal, warning, error, stale, loading. | Valeur + unite annoncees; delta textuel. | Grid stable; un seul hero metric par surface. | Dashboard KPI, revenue, poids, prieres. | Decision complexe, formulaire. |
| ImperiumKpiBlock | Bloc KPI plus compact dans cards/panels. | Rendre valeur dense sans prendre la hierarchie du metric card. | `Typography.H3/BodyMedium/Label`, numeric font, app text tokens, `Spacing.SM`. | Inline, stacked, with status chip. | Normal, stale, warning, error. | Unit dans content description; couleur pas seule. | Peut se placer dans right panel 320dp. | Resumes secondaires, detail panels. | KPI principal d'ecran. |
| ImperiumProgressBar | Progression lineaire. | Rendre progress calcule par backend ou etat local valide. | App `Accent`, `SurfaceVariant`, `SemanticStateColors`, `Radius.Chip`, `Spacing.XS/SM`. | Determinate, indeterminate, segmented. | Empty, partial, complete, over, loading, stale. | Percent/valeur visible ou annoncee; pas progress sans label. | Largeur responsive; hauteur stable. | Macros, session pace, workflow steps. | Valeur inconnue determinate, decoration. |
| ImperiumProgressRing | Progression circulaire compacte. | Rendre arc et valeur associee. | App `Accent`, `SurfaceVariant`, `SemanticStateColors`, `IconSize.WidgetHero`, numeric font. | Small, standard, large. | Empty, partial, complete, warning, stale. | Texte central ou label externe; announce percent and target. | Taille fixe 120-180dp selon panel; pas de layout shift. | Recovery, savings, hydration, sadaqa. | Listes denses, mode conduite si distractif. |
| ImperiumTimeline | Evenements chronologiques. | Rendre ordre, statuts, timestamps et actions detail. | App `Divider`, `Accent`, `TextPrimary`, `TextSecondary`, `Radius.Chip`, `Spacing.MD/LG`. | Vertical, compact, grouped by day. | Loading, empty, partial, stale, conflict item. | Ordre lu chronologiquement; timestamps complets. | Max 1280dp; list/detail split possible. | Mission history, daily plan, workflow logs. | Donnees non chronologiques, menu navigation. |
| ImperiumListItem | Ligne generique de liste. | Rendre leading, content, trailing action/status. | App `Surface`, `Divider`, `TextPrimary`, `TextSecondary`, `IconSize.Action`, `Spacing.MD`. | One-line, two-line, three-line, with chip/action. | Default, pressed, focused, disabled, loading, stale. | Role selon action; trailing icon labelled; min height stable. | List max 880dp avec detail panel optionnel. | Transactions, missions, settings, stock. | Carte riche ou modal content complexe. |
| ImperiumTransactionRow | Ligne financiere standard Vault/Vector handoff. | Afficher montant, direction, categorie, date, source, sync. | Vault/app tokens, `ImperiumFontFamilies.Numeric`, `SemanticStateColors`, `SyncStateChip`, `Divider`. | Income, expense, correction, reversal, pending review. | Draft, synced, failed, reversed, conflict, stale. | Montant annonce avec direction et devise; status textuel. | Alignement montant a droite; detail pane 320-480dp. | Vault transactions, Vector revenue/expense handoff. | Donnee non financiere, suppression directe sans reversal. |
| ImperiumStatusChip | Statut metier court non seulement sync. | Rendre label, icon optionnelle, severity. | App `SurfaceVariant`, `TextSecondary`, `SemanticStateColors`, `Radius.Chip`, `Typography.Label`, `IconSize.Inline`. | Neutral, info, success, warning, error. | Default, focused if clickable, disabled. | Label obligatoire; icon decorative ou annoncee selon sens. | Reste compact; wrap controle dans grids. | Due soon, prayed, active, overdue, low confidence. | Remplacer une explication, afficher sync complexe sans SyncStateChip. |

---

## 11. Non-goals

- Ne pas creer Kotlin.
- Ne pas creer Android.
- Ne pas creer `android/`.
- Ne pas creer `frontend/`.
- Ne pas creer de vrai `.kt`.
- Ne pas creer de composant Compose runtime.
- Ne pas importer assets.
- Ne pas implementer les composants.
- Ne pas modifier le backend runtime.
- Ne pas modifier le Design System canonique sauf reference stricte depuis un patch dedie.
- Ne pas creer de nouvelle strategie metier dans les apps.
- Ne pas automatiser d'action Bolt illegale ou contraire aux plateformes.

**Document version :** 1.0
**Statut :** FOUNDATION COMPONENT CATALOG V1 — ready for future Compose implementation, not implemented yet.
**Last updated :** 2026-06-02
