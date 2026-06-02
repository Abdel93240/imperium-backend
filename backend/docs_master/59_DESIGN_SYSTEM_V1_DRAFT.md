# 59 — Design System V1 (IMPERIUM Ecosystem)

**Version :** 1.0
**Cible technique :** Android natif Kotlin + Jetpack Compose (Material 3)
**Device principal :** Samsung Galaxy Tab S10 Ultra (14.6", 2960×1848, ~239 ppi, landscape primaire)
**Périmètre :** 5 apps (Imperium, Vault, Vector, Pulse, Path), 62 écrans V1
**Statut :** DRAFT V1 — toute déviation doit être justifiée par PR contre ce document.

> **Note DRAFT :** Ce document est un draft de fondation. Les palettes HEX et règles visuelles devront être revalidées lorsque les Style Masters et assets_registry seront versionnés dans le repo.

---

## 0. Principe fondateur

```text
clarity + speed + reliability
not beautiful complexity
```
(doc 07 §UI Principle)

Toute décision design qui contredit ce principe est invalide V1.

Corollaires :
- Density per surface : driving = minimal, planning = rich, dashboard = balanced.
- No fake success : tout état dérivé d'un backend doit refléter l'état réel (`pending|syncing|synced|failed|conflict|cached|stale`).
- One brain, five faces : les 5 apps partagent foundation tokens (spacing, typography, radius, elevation, states) mais divergent sur la palette pour ancrer l'identité.

---

## 1. COLOR SYSTEM

### 1.1 Système global (cross-app)

| Token sémantique | HEX | Usage | Règle |
|---|---|---|---|
| Success | `#34C759` | confirmation backend, sync OK, halo Vector vert | Réservé aux états positifs **confirmés**. Jamais pour un draft. |
| Warning | `#F5A524` | dérive légère, low confidence, sync lent | Pas pour un blocage. |
| Error | `#E5484D` | échec sync, mission failed, halo Vector rouge | Toujours accompagné d'un texte explicatif. |
| Info | `#0091FF` | recommandation, conseil AI non urgent | Jamais en remplacement de Success. |
| Halo Analyzing (Vector) | `#FFFFFF` opacité 80% | overlay en analyse | Halo blanc = "analyse en cours, ne pas décider" |

Contraste cible : **WCAG AA (4.5:1)** sur surface primaire de chaque app en dark mode (mode par défaut).

### 1.2 IMPERIUM — Command Center (deep navy + gold)

> Identité : autorité, décision, vue d'ensemble. L'or est *rare* (max 1 accent gold visible par écran).

| Token | HEX | Usage | Règle |
|---|---|---|---|
| Primary | `#1A2B4A` | barre supérieure, surfaces de commande, bouton primary | La couleur signature d'Imperium. |
| Secondary | `#2E4370` | surfaces secondaires, cartes de mission | Variante claire de Primary. |
| Accent | `#C9A24B` | bouton "Reprogrammer ma journée", emblèmes, badge "current mission" | Max 1 accent gold visible à la fois. Pas sur du texte courant. |
| Background | `#0E1626` | fond d'écran global | Dark mode par défaut. |
| Surface | `#16213A` | cards, panneaux | Au-dessus du background. |
| Surface Variant | `#1F2D4D` | cards imbriquées, listes alternées | 1 niveau de profondeur visuelle. |
| Border | `#2A3A5C` | bordures de cartes interactives | 1dp. |
| Divider | `#1F2D4D` | séparateurs liste, sections | Opacité 60%. |
| Success | `#34C759` | mission completed, plan synced | Cf. §1.1. |
| Warning | `#F5A524` | mission expiring soon | Cf. §1.1. |
| Error | `#E5484D` | replan failure, mission failed | Cf. §1.1. |
| Info | `#0091FF` | AI advice banner | Cf. §1.1. |
| Text Primary | `#F5F7FA` | titres, valeurs | Contraste 13.5:1 sur Background. |
| Text Secondary | `#B8C2D6` | sous-titres, labels secondaires | Contraste 8.4:1. |
| Text Muted | `#7886A0` | metadata, timestamps, captions | Contraste 4.6:1. Jamais en dessous de Caption. |

### 1.3 VAULT — Financial Reality (deep green + bronze)

> Identité : terre, stabilité, vérité financière. Pas de rouge agressif sauf pour overdue / failure réel.

| Token | HEX | Usage |
|---|---|---|
| Primary | `#163C2F` | top bar, header "balance" |
| Secondary | `#28604E` | cards transaction |
| Accent | `#B58A4C` | badge "obligation", chip "upcoming expense" |
| Background | `#0B1A14` | fond global |
| Surface | `#142A22` | cards |
| Surface Variant | `#1B392E` | cards imbriquées |
| Border | `#264636` | bordures |
| Divider | `#1B392E` | séparateurs |
| Success | `#34C759` | gain confirmé, transaction synced |
| Warning | `#F5A524` | pressure score élevé |
| Error | `#E5484D` | expense overdue, balance négative |
| Info | `#0091FF` | suggestion sadaqa |
| Text Primary | `#F2F7F4` | montants principaux |
| Text Secondary | `#B6C7BE` | labels |
| Text Muted | `#7A8D83` | metadata |

Règle Vault : **les montants sont toujours en JetBrains Mono** (cf. §2) pour aligner les chiffres en colonnes.

### 1.4 VECTOR — Strategic VTC Copilot (deep teal + electric cyan, halo trichromique)

> Identité : kinétique, instantanée, lisible en conduite. Le halo (white/green/red) est sacré.

| Token | HEX | Usage |
|---|---|---|
| Primary | `#0E2A33` | fond HUD standby (doc 55 §5.1) |
| Secondary | `#1C4753` | cards info, side panel |
| Accent | `#00D9E0` | actions kinétiques (start session, where should I go) |
| Background | `#06181E` | fond global (Tab et phone) |
| Surface | `#0F2730` | cards |
| Surface Variant | `#173744` | cards imbriquées, popup lane |
| Border | `#214756` | bordures HUD |
| Divider | `#173744` | séparateurs |
| **Halo Success (green)** | `#22D673` | recommandation positive (course OK) — **HEX figé, WCAG AA validé sur Background driving** |
| **Halo Warning (yellow)** | `#F5C842` | hésitation, low confidence |
| **Halo Error (red)** | `#FF4A4A` | refuser la course |
| **Halo Analyzing (white)** | `#FFFFFF` @ 80% | analyse en cours |
| Info | `#0091FF` | conseils non urgents |
| Text Primary | `#EEFAFD` | titres |
| Text Secondary | `#B6CCD2` | labels |
| Text Muted | `#778C92` | metadata |

Règle Vector : **en mode NAVIGATION (doc 55 §5.2), le halo prend précédence visuelle sur tout autre accent**. Les overlays se réduisent automatiquement.

### 1.5 PULSE — Biological Layer (deep crimson + warm coral)

> Identité : vital, organique, chaud. Évite la saturation excessive (cible : éviter la fatigue oculaire en soirée).

| Token | HEX | Usage |
|---|---|---|
| Primary | `#3D1418` | header |
| Secondary | `#682430` | cards workout, meal |
| Accent | `#FF8C7A` | badge "today's workout", call-to-action |
| Background | `#1A0A0D` | fond global |
| Surface | `#2A1015` | cards |
| Surface Variant | `#3A1A20` | cards imbriquées |
| Border | `#4A222B` | bordures |
| Divider | `#3A1A20` | séparateurs |
| Success | `#34C759` | meal logged, workout completed |
| Warning | `#F5A524` | low recovery |
| Error | `#E5484D` | pain logged (high severity) |
| Info | `#0091FF` | recommandation pulse |
| Text Primary | `#FAEFEF` | titres |
| Text Secondary | `#D6BABC` | labels |
| Text Muted | `#967A7E` | metadata |

### 1.6 PATH — Operational Islamic Discipline (deep emerald + warm gold)

> Identité : paix, ancrage spirituel, gold-as-light. L'or de Path est plus chaud que celui d'Imperium.

| Token | HEX | Usage |
|---|---|---|
| Primary | `#0E3A2C` | header, top bar |
| Secondary | `#1F5C46` | cards prière, fasting |
| Accent | `#D9B265` | sadaqa target, badge "ghusl required" |
| Background | `#071A14` | fond global |
| Surface | `#0F2A20` | cards |
| Surface Variant | `#173A2C` | cards imbriquées |
| Border | `#214936` | bordures |
| Divider | `#173A2C` | séparateurs |
| Success | `#34C759` | prière confirmée, fast complete |
| Warning | `#F5A524` | prière proche, ghusl required |
| Error | `#E5484D` | prière manquée (rare, jamais auto-déclenché) |
| Info | `#0091FF` | rappel adhkar |
| Text Primary | `#EEF7F2` | titres |
| Text Secondary | `#B6CFC2` | labels |
| Text Muted | `#7A938A` | metadata |

### 1.7 Règles transverses d'application des couleurs

- **Dark mode = défaut V1.** Light mode = V2.
- **Une seule couleur d'accent visible par écran.** Si un écran cross-app affiche du contenu de Vault + Vector simultanément, l'app *hôte* impose son accent ; les autres descendent en `Surface Variant`.
- **Halo states (Success/Warning/Error/Info)** ont la même HEX dans les 5 apps : sémantique > marque.
- **L'or (`#C9A24B` Imperium / `#B58A4C` Vault / `#D9B265` Path)** : max 1 élément doré visible par écran. Sinon dilution.
- **Accessibilité daltonisme** : les halo states ne sont JAMAIS utilisés seuls — toujours couplés à une icône (✓ ⚠ ✕ ⓘ) ou un libellé textuel. Cf. §6.

---

## 2. TYPOGRAPHY SYSTEM

### 2.1 Stratégie Android Compose

- **Police primaire :** **Inter** (variable font) — neutralité, lisibilité tablette, vaste support langues + arabe partiel pour Path.
- **Police secondaire (numérique) :** **JetBrains Mono** (variable) — montants Vault, IDs mission, heures de prière, KPI Vector (€ / km / h).
- **Police arabe (Path uniquement) :** **Noto Naskh Arabic** — calligraphie standardisée Quran/adhkar.
- **Stratégie Compose :**
  - Bundling `assets/fonts/` (Inter, JetBrains Mono, Noto Naskh Arabic).
  - `Typography` exposée par `ImperiumTheme.typography` (override `MaterialTheme.typography`).
  - Variable fonts → un seul fichier par famille, instances de poids dynamiques.
  - Unité : **sp** (scale-independent pixels) pour respecter accessibilité système. Jamais `dp` ni `px`.

### 2.2 Échelle (optimisée Tab S10 Ultra landscape)

| Style | Taille (sp) | Poids | Line height (sp) | Usage |
|---|---|---|---|---|
| **Display** | 56 | 700 (Bold) | 64 | Splash IMPERIUM, "Bonjour" du Morning Check-In, gros KPI dashboard (€ jour Vault) |
| **H1** | 40 | 700 | 48 | Titre d'écran principal (Dashboard, Weekly Review, HUD standby) |
| **H2** | 32 | 600 (SemiBold) | 40 | Titre de section (Missions, Aujourd'hui, Cette semaine) |
| **H3** | 24 | 600 | 32 | Card title (mission card, transaction card) |
| **H4** | 20 | 600 | 28 | Sub-section, dialog title, bottom sheet title |
| **Body Large** | 18 | 400 (Regular) | 28 | Contenu principal cards, AI advice, chat assistant |
| **Body Medium** | 16 | 400 | 24 | Listes, descriptions, formulaires standards |
| **Body Small** | 14 | 400 | 20 | Metadata, timestamps secondaires, descriptions courtes |
| **Caption** | 12 | 500 (Medium) | 16 | Status labels (`pending`, `synced`), tags, captions image |
| **Label** | 11 | 600 | 14 | Chips, badges, micro-labels, axis values |

### 2.3 Règles d'application

- **Tab S10 Ultra landscape :** échelle ci-dessus inchangée. La marge gagnée se déverse en spacing/whitespace, pas en agrandissement.
- **Phone portrait :** réduire Display→40, H1→32, H2→24, H3→20 (cf. §9 responsive). Le reste inchangé.
- **Numériques (€, km/h, h, score) :** **toujours JetBrains Mono Regular ou Medium**, taille = celle du contexte. Permet alignement colonnes dans Vault et Vector.
- **Arabe (Path) :** **Noto Naskh Arabic Regular**, +2 sp par rapport à Body équivalent pour compensation densité.
- **Letter-spacing :** par défaut Compose `0.sp`. Exception : `Label` et `Caption` en `0.2.sp` pour majuscules de chips.
- **Texte en majuscules :** réservé aux Labels (chips). Jamais sur Body ou titres.

---

## 3. SPACING SYSTEM

### 3.1 Base 8dp (avec sous-grille 4dp pour XXS/XS)

| Token | Valeur (dp) | Usage canonique |
|---|---|---|
| **XXS** | 2 | sous-pixel borders, indicateurs très fins |
| **XS** | 4 | espacement intra-chip, icône↔texte d'un même chip |
| **SM** | 8 | espacement compact (badge ↔ label, items de liste denses) |
| **MD** | 16 | unité de base (padding card interne, gap entre items de liste standard) |
| **LG** | 24 | espacement entre sections d'une même card |
| **XL** | 32 | padding global écran (Tab landscape), gap entre cards de section différente |
| **XXL** | 48 | gap entre zones sémantiquement distinctes (header ↔ body) |
| **XXXL** | 64 | top-padding hero, espace réservé aux ancrages de scroll |

### 3.2 Règles d'application par surface

| Surface | Padding | Spacing inter-items | Notes |
|---|---|---|---|
| **Card standard** | `MD` (16) | `SM` (8) | Coin radius `Card` (cf. §4). |
| **Card dense (mission list)** | `SM` (8) horizontal, `MD` (16) vertical | `XS` (4) | Pour listes haute densité. |
| **Screen (Tab landscape)** | `XL` (32) | `LG` (24) entre cards | Côté gauche + droit. Top safe area + `LG`. |
| **Screen (Phone portrait)** | `MD` (16) | `MD` (16) entre cards | |
| **Section dashboard** | `XL` (32) top, `LG` (24) entre cards | — | Section = ensemble cohérent (ex: "Aujourd'hui"). |
| **Widget (home screen)** | `MD` (16) interne | `SM` (8) | Pas plus de 3 niveaux d'info dans un widget. |
| **Bottom sheet** | `LG` (24) latéral, `LG` (24) top après drag handle | `MD` (16) entre groupes | Drag handle 32×4dp centré. |
| **Dialog** | `LG` (24) latéral, `LG` (24) top/bottom | `MD` (16) entre titre/body/actions | |
| **Top bar** | `MD` (16) latéral | `SM` (8) entre icônes | Hauteur 56dp standard, 64dp si tab. |
| **Bottom nav / bottom action bar** | `SM` (8) vertical, `MD` (16) latéral | flex egal | Hauteur 80dp tab, 64dp phone. |

### 3.3 Anti-règles

- Jamais de valeur intermédiaire (10dp, 14dp, 20dp interdits sauf radius cf. §4).
- Jamais de marges négatives.
- Le whitespace au-delà de `XXXL` est interdit V1 (vide perçu comme bug).

---

## 4. RADIUS SYSTEM

| Composant | Radius (dp) | Règle |
|---|---|---|
| **Chips** | 8 | Pill modéré ; chips de filtre, status. |
| **Buttons** | 12 | Tous les buttons (Primary/Secondary/Ghost/Destructive). Pas de variation par taille. |
| **Inputs** | 12 | Aligné sur Buttons pour cohérence verticale dans les formulaires. |
| **Cards** | 16 | Surface principale. |
| **Bottom Sheets** | 24 (top-left + top-right uniquement) | Sentiment "lift from below". Bas plat. |
| **Dialogs** | 20 | Plus arrondi que Card pour signaler la modalité. |
| **Modals fullscreen** | 0 | Pleine surface. |
| **Avatar / Emblème** | 50% (circulaire) | Photos profil, halos profil. |
| **Image cards (assets premium)** | 16 (image) imbriquée dans Card 16 | Imbrication directe (pas de bordure entre eux). |

Règle de cohérence : **la radius croît avec l'élévation perçue** — un Bottom Sheet (élévation 3, voir §5) a 24dp ; une Card simple (élévation 1) a 16dp ; un Chip (élévation 0) a 8dp.

---

## 5. ELEVATION SYSTEM

Compose `Surface(tonalElevation = …)`. Tonalité dark : l'élévation se traduit par **éclaircissement subtil** du surface (Material 3 dark elevation overlay), pas par une ombre forte.

| Level | Tonal elevation (dp) | Shadow | Usage |
|---|---|---|---|
| **L0** | 0 | none | Background plein écran, fond de section. |
| **L1** | 1 | none / 1dp à 8% noir | Card statique standard. |
| **L2** | 3 | 2dp à 12% noir | Card interactive en survol/press, raised card. |
| **L3** | 6 | 4dp à 16% noir | Modal, Dialog, Bottom Sheet, AlertDialog. |
| **L4** | 12 | 6dp à 24% noir | Top App Bar flottant, FAB, halo Vector overlay. |

Règles :
- **Max 2 niveaux d'élévation visibles simultanément** dans un même viewport.
- En mode driving (Vector navigation), l'élévation se réduit à L0/L1 pour limiter la pollution visuelle.
- Les ombres ne sont jamais colorées (toujours noir, opacité variable).

---

## 6. ICONOGRAPHY SYSTEM

### 6.1 Tailles

| Contexte | Taille (dp) | Usage |
|---|---|---|
| **Inline (dans texte Body)** | 16 | Icône inline d'une phrase. |
| **Input adornment** | 20 | Icône à gauche/droite d'un TextField. |
| **Action (toolbar, chip)** | 24 | Action standard, icône de chip. |
| **Navigation (bottom nav)** | 28 | Onglets de navigation. |
| **Top bar action** | 24 | Boutons en top bar. |
| **Avatar / status circle** | 40 | Avatar utilisateur, ronds d'état Vector. |
| **Emblème app (header)** | 48 | Identité d'écran (logo Vault, Pulse…). |
| **Widget hero** | 64 | Widget home screen — l'image hero. |
| **Asset premium / illustration** | 96 ou 128 | Illustrations Morning Check-In, Weekly Review hero, empty states "delight". |
| **Badge numérique** | 18 (cercle), texte 11sp Label | Badge sur icône nav (ex: "3 missions"). |

### 6.2 Stratégie 3-tier (assets premium / icônes système / illustrations)

| Type | Quand utiliser | Format |
|---|---|---|
| **Asset premium V1** (généré) | Emblèmes app, badges de succès rares, hero d'écrans clés (Morning Check-In, Weekly Review intro, end-of-day Bilan, milestones). Réservés aux moments à charge émotionnelle. | SVG vectoriel ou WebP @1x/2x/3x. Lottie autorisé uniquement pour milestones (≤2 par écran). |
| **Material Symbols** (système) | Toutes actions courantes, navigation, états (`check`, `error`, `close`, `more_vert`, `play_arrow`…). Le set "Outlined" est canonique V1. | Material Symbols Outlined, weight 400, grade 0, optical size auto. |
| **Illustrations** | Empty states sémantiquement riches (ex: "Pas encore de check-in du matin"), error states bloquants. | SVG ou WebP, dimension fixe 240×240dp. Pas plus de 1 illustration visible à la fois. |

### 6.3 Règles d'usage

- **Un emoji n'est jamais une icône.** Les emojis présents dans les docs (📊 🔥 🕌…) sont remplacés par leur équivalent Material Symbols ou un asset premium.
- **Asset premium = max 2 par écran.** Au-delà : c'est un mockup, pas un produit.
- **Toute icône d'état (Success/Warning/Error/Info)** est **toujours couplée à un libellé textuel** (cf. §1.7 daltonisme).
- **Halo Vector** : icône fixe (cercle plein) ; seule la couleur change. Jamais d'icône différente par état.

---

## 7. COMPOSE FOUNDATION COMPONENTS

> Description fonctionnelle uniquement (mode read-only). Le code Compose sera produit ultérieurement.

### 7.1 Buttons

| Variant | Surface | Texte | Usage | Anti-usage |
|---|---|---|---|---|
| **Primary** | Fond Accent app, radius 12, height 48dp (tab) / 44dp (phone), padding horizontal `LG` | Text Primary sur Accent, Label SemiBold 14sp | Action principale de l'écran. **Une seule par écran.** | Ne jamais utiliser pour des actions de navigation. |
| **Secondary** | Bordure 1dp `Border`, surface transparente, radius 12, mêmes dimensions | Text Primary, Label Medium 14sp | Actions secondaires (Annuler, Voir plus). | Pas pour Destructive. |
| **Ghost** | Pas de bordure, pas de fond, radius 12 | Text Secondary, Label Medium 14sp | Actions tertiaires, "skip", "later". | Pas pour Primary. |
| **Destructive** | Surface `Error` (#E5484D), texte `Text Primary` | Bold | Suppression, abandon mission, reset patterns. | Toujours derrière un confirm dialog. |

Tous les buttons exposent : `enabled`, `loading` (spinner remplace texte), `leadingIcon`, `trailingIcon`. Touch target minimal 48dp (WCAG).

### 7.2 Inputs

| Variant | Description | Notes |
|---|---|---|
| **Text** | TextField outlined, radius 12, height 56dp, label flottant | Erreur en `Error` sous le champ. |
| **Number** | Idem Text, clavier numérique, **font JetBrains Mono** pour le contenu | Montants Vault. |
| **Search** | TextField outlined avec icône `search` à gauche, "clear" à droite si content | Hauteur 48dp (légèrement plus compact). |
| **Voice** | Button circulaire 64dp, accent app, icône `mic` ; états : idle / recording (anneau pulsé) / uploading / processed | Le pipeline upload suit doc 07 §Voice Input Flow. |

Tous les inputs : `error` (string), `supportingText`, `enabled`, `readOnly`, `clearable`.

### 7.3 Selection

| Variant | Description |
|---|---|
| **Toggle (Switch)** | Standard Material 3, accent app sur l'état "on". |
| **Checkbox** | Radius 4dp, accent app, taille 24×24dp. |
| **Radio** | Standard Material 3, accent app. |
| **Segmented Control** | Container surface `Surface Variant`, radius 12, indicator surface `Accent`, items height 36dp ; 2-4 items max. |

### 7.4 Navigation

| Variant | Description |
|---|---|
| **Bottom Navigation** | Phone uniquement. Height 80dp, 3-5 items, icônes 28dp, label 11sp Caption. Active = couleur Accent app. |
| **Top Bar** | Hauteur 64dp tab / 56dp phone. Title H4. Action icons 24dp. Surface `Primary` (couleur app) sur fond `Background`. |
| **Sidebar (Rail)** | Tab landscape uniquement. Largeur 80dp (rail compact) ou 240dp (rail étendu). 5-7 items. Active = bar verticale Accent + icône colorée. |
| **Tab Bar** | Inline, height 48dp, indicator 2dp en bas sur tab actif, couleur Accent. |

**Tab S10 Ultra landscape : Sidebar (rail étendu 240dp) est la navigation primaire**, pas Bottom Nav.

### 7.5 Feedback

| Composant | Position | Durée | Usage |
|---|---|---|---|
| **Snackbar** | Bottom centre, slide-up | 4-7s | Confirmation backend (`Mission completed (synced)`), avec action optionnelle (`Undo`). |
| **Toast** | Top centre, slide-down | 2-3s | Acknowledgment local, **jamais pour confirmer un backend**. |
| **Banner** | En tête d'écran, sticky, surface `Warning`/`Error`/`Info` | persistant jusqu'à dismiss explicite | WR disponible, Ghusl required, critical alert. |
| **Alert (Dialog)** | Centré, élévation L3 | jusqu'à action | Décisions irréversibles (abandon mission, reset patterns). |

Règle no-fake-success : Snackbar "synced" n'apparaît que sur 200 backend confirmé. Sinon Toast "pending sync".

### 7.6 Containers

| Composant | Description | Élévation |
|---|---|---|
| **Card** | Surface `Surface`, radius 16, padding `MD`, élévation L1 ou L2 si interactive. | L1 (statique) / L2 (interactive) |
| **Bottom Sheet** | Slide-up depuis le bas, drag handle 32×4dp top center, radius 24 top, hauteur min 30% / max 90% du viewport. | L3 |
| **Dialog** | Modal centré, max width 480dp, radius 20, padding `LG`. | L3 |
| **Drawer** | Slide-in latéral (gauche), largeur 320dp phone / 360dp tab. Pour menus secondaires uniquement (cf. §7.4 sidebar pour nav primaire). | L3 |

### 7.7 States (Empty / Loading / Error / Sync)

Chaque écran expose obligatoirement les 7 états :

| État | Layout | Contenu |
|---|---|---|
| **Loading** | Skeleton (placeholders animés) ou spinner centré. Skeleton préféré pour cards prédictibles. | Spinner accent app, taille 32dp si centré. |
| **Empty** | Illustration 240×240, titre H3, body Body Medium, optional CTA Secondary. | "Pas encore de check-in du matin / Commencer". |
| **Error** | Illustration 240×240 (variante "error" en tons Warning), titre H3, body Body Medium, CTA Primary "Réessayer". | Toujours expliquer la raison technique. |
| **Offline** | Banner Warning persistant haut d'écran + état Empty/Cached selon. | "Hors ligne — données du HH:MM affichées". |
| **Syncing** | Indicateur ligne 2dp animée sous Top Bar, label "Synchronisation…". | Non bloquant. |
| **Synced** | Confirmation transitoire (Snackbar `Success`) puis disparition. | "Mission complétée — synced". |
| **Conflict** | Banner `Error`, Dialog au tap : "Conflit côté serveur" + diff visible + 2 actions (Garder local / Garder serveur). | Doc 07 §Sync Flow. |

---

## 8. IMPERIUM GOLDEN PATH — COMPONENT MAPPING

Mapping écran ↔ composants foundation ↔ assets. Cible : 7 écrans cœur du flow utilisateur Imperium V1.

### 8.1 Morning Check-In

- **Composants :** Dialog ou écran modal fullscreen ; Display "Bonjour" ; H3 "Comment ça va ce matin ?" ; Input slider (énergie 0-10, custom) ; Input slider (heures de sommeil) ; Segmented Control (mood 5 emojis) ; Text Input multilignes (free text) ; Button Primary "Continuer" ; Button Ghost "Plus tard".
- **Widgets :** none.
- **Assets :** illustration hero 240×240 (variante day/dawn), emblème Imperium 48dp en top.
- **États :** Loading (envoi backend), Synced (transition vers Dashboard).

### 8.2 Dashboard

- **Composants :** Top Bar (Imperium logo + emblème, profil), Sidebar étendue (tab landscape) ou Bottom Nav (phone), Cards "Current focus mission" (Card L2 Accent border), Card "Quick stats" (KPI Display + Caption), Banners (WR available, Ghusl required, Critical), Section "Today's plan" (liste de Card mission), Section "Plan history" tab, Button Primary "Reprogrammer ma journée" (Accent gold, **seul accent gold de l'écran**), Chatbot input ancré bas.
- **Widgets :** Next prayer countdown (mini-card), Pressure score (mini-card), Discipline streak (mini-card).
- **Assets :** emblème Imperium, icônes Material Symbols pour status missions.
- **États :** tous (cf. §7.7).

### 8.3 Mission

- **Composants :** Card hero (Card L2, H3 titre, Body Large description, Chips de priorité/category, Chip status `pending`/`active`), Section metadata (deadline, category, sub-tasks), Button Primary "Faite", Button Secondary "Ratée", Button Destructive (in confirm Dialog) "Annulée".
- **Widgets :** none.
- **Assets :** none (icônes système Material Symbols).
- **États :** Loading (sync action), Synced, Failed (banner Error).

### 8.4 Mission Outcome

- **Bottom Sheet** déclenché par "Ratée" ou "Annulée" : Title H4 "Pourquoi ?", Input voice (priorité) OU Text multilignes, Segmented Control "user_reported_signals" (énergie/distraction/temps/autre), Button Primary "Envoyer" (déclenche hook replan).
- **Composants :** Bottom Sheet L3, Input Voice, Text, Segmented.
- **Assets :** none.

### 8.5 Replan

- **Composants :** Dialog fullscreen modal (élévation L3), Top Bar minimal "Nouveau plan proposé", Section "Avant / Après" (deux colonnes Tab landscape, stacked phone), liste de Card mission (badges Δ "ajouté"/"déplacé"/"retiré"), Banner Info "Raison IA : …", Buttons : Primary "Accepter", Secondary "Modifier", Ghost "Annuler".
- **Widgets :** none.
- **Assets :** none.
- **États :** Loading hero (spinner + "Sonnet 4.6 replanifie…"), Error (Dialog Error si replan failed).

### 8.6 Chatbot

- **Composants :** Top Bar "Assistant" + chip de provider actif (Qwen/Sonnet/Opus), Liste messages (Body Large, surface alternée Surface / Surface Variant, timestamp Caption), Input Text + Button Voice + Button Send Primary, Banner Info pour Decisions Log.
- **Widgets :** none.
- **Assets :** emblème Imperium 24dp pour avatar AI ; avatar user 40dp.
- **États :** Loading (typing indicator 3 dots), Error (message bubble Error).

### 8.7 Weekly Review

- **Composants :** Top Bar "Weekly Review", Stepper horizontal (sections guidées doc 47), Section principale en Card (H3 question, Body Large contexte, Input adapté par section), Button Primary "Suivant", Button Ghost "Sauter", Banner Info pour initial summary, Bottom Sheet draft/final candidate.
- **Widgets :** sparkline trends (Compose Canvas custom, taille 64dp height).
- **Assets :** illustration hero 240×240 en intro, emblème Imperium.
- **États :** Loading (read-model fetch), `can_answer`/`is_waiting_for_ai` states (doc 32) → Banner status synchro.

---

## 9. RESPONSIVE STRATEGY

### 9.1 Breakpoints

| Mode | Largeur (dp) | Layout |
|---|---|---|
| **Portrait Phone** | 0 – 599 | 1 colonne, Bottom Navigation, padding `MD`, échelle typographique réduite (cf. §2.3). |
| **Landscape Phone** | 600 – 839 | 1-2 colonnes selon écran, Bottom Nav éventuellement, padding `MD`-`LG`. |
| **Tablet Portrait** | 840 – 1199 | 2 colonnes, Sidebar Rail compact 80dp ou Bottom Nav, padding `LG`. |
| **Tablet Landscape** | 1200+ (**cible Tab S10 Ultra : 2960dp à 239ppi → ~1860dp logiques en landscape selon density**) | **3 colonnes max**, Sidebar Rail étendu 240dp, padding `XL`, contenu central max-width 1280dp avec marges latérales. |

### 9.2 Priorité Tab S10 Ultra Landscape

C'est **le device par défaut V1.** Toutes les maquettes V1 sont d'abord conçues pour ce form factor.

Layout canonique Tab S10 Ultra landscape :

```
┌──────────────────────────────────────────────────────────────────┐
│ Top Bar 64dp                                                     │
├────────┬──────────────────────────────────────────┬──────────────┤
│        │                                          │              │
│        │                                          │              │
│ Side-  │     Contenu principal                    │  Panneau     │
│ bar    │     (max-width 1280dp, centré)           │  contextuel  │
│ Rail   │                                          │  optionnel   │
│ 240dp  │                                          │  320dp       │
│        │                                          │              │
│        │                                          │              │
└────────┴──────────────────────────────────────────┴──────────────┘
```

- **Colonne gauche (Sidebar 240dp) :** navigation primaire (Imperium tabs : Dashboard, Plan history, Decisions log, Settings).
- **Colonne centrale (flex, max 1280dp) :** contenu principal.
- **Colonne droite (320dp, optionnelle) :** panneau contextuel persistant (ex: chatbot dock sur Dashboard, side panel HUD Vector).

### 9.3 Règles de conversion

- **Portrait → Landscape :** la Bottom Nav devient Sidebar Rail. Les cards 1-col deviennent 2-col grid.
- **Rotation :** transition `Crossfade` 200ms ; pas de scroll loss.
- **Multi-window Samsung DeX :** support V2 (V1 : layout phone-style minimum).

### 9.4 Driving surface (Vector navigation)

Override du responsive : en mode driving (cf. doc 55 §5.2), le contenu se réduit à :
- 1 carte centrale info essentielle
- 0 sidebar
- Top bar minimaliste 40dp
- Halo en overlay plein écran semi-transparent

---

## 10. DESIGN RULES (synthèse non-négociables)

### 10.1 Quand utiliser les assets premium

- ✅ Emblèmes d'app (header).
- ✅ Hero d'écran à charge émotionnelle (Morning Check-In, Weekly Review intro, End-of-day Bilan, milestone).
- ✅ Empty states de cœur de flow (jamais d'illustration pour un empty state d'utilité technique).
- ❌ Buttons, top bar actions, listes, chips → Material Symbols.
- ❌ Jamais 2 assets premium côte à côte (sauf emblème + hero).

### 10.2 Quand utiliser une simple icône

- Toute action courante (tap, swipe, dismiss).
- Tout indicateur d'état (✓ ⚠ ✕ ⓘ).
- Toute navigation.
- Tout adornment d'input.
→ **Material Symbols Outlined, weight 400.**

### 10.3 Fréquence maximale des accents gold

- **Maximum 1 élément gold visible par écran.** Si une Card a un accent gold, le bouton primary de l'écran prend la couleur Accent app (non-or).
- Le gold marque ce qui mérite d'être regardé en priorité (current focus mission, sadaqa target, balance principale).
- L'or n'est jamais utilisé sur du texte courant.

### 10.4 Lisibilité

- Contraste WCAG AA minimum (4.5:1) pour tout texte sur surface.
- Body Small et Caption : interdit en dessous de Text Muted.
- Texte sur image / illustration : **toujours sur surface scrim (overlay noir 40-60%)**.
- Texte en mouvement (animations) : durée min 400ms pour rester lisible.
- Texte clignotant : **interdit V1** (sauf cursor input).

### 10.5 Densité d'information

| Surface | Cible items visibles (Tab landscape) | Logique |
|---|---|---|
| Dashboard Imperium | 5-7 cards majeures | Vue d'ensemble. |
| Mission detail | 1 mission hero + 3-5 metadata blocks | Focus. |
| Vault transactions list | 12-20 transactions / écran | Liste lourde. |
| Path next prayer | 1 info principale + 4 indicateurs secondaires | Glance. |
| HUD Vector standby | Map plein écran + 2-3 overlays | Spatial. |
| HUD Vector navigation | Map + 1 info dominante (lane/destination/halo) | Driving. |
| Weekly Review section | 1 question + contexte + 1 input | Guidée. |

### 10.6 Hiérarchie visuelle (cascade canonique)

1. **Display / H1** → 1 par écran maximum.
2. **Accent color (gold)** → 1 élément par écran maximum.
3. **Élévation L4** → 1 surface par écran maximum.
4. **Banner persistant** → 1 par écran maximum (sauf Critical Alert + WR available qui peuvent cohabiter dans cet ordre).
5. **Button Primary** → 1 par écran maximum.

Toute infraction à un de ces 5 points dilue la hiérarchie ; toute infraction simultanée à deux d'entre eux invalide l'écran.

### 10.7 Motion (durations & easings)

| Type | Durée | Easing |
|---|---|---|
| Micro-interactions (hover, press) | 100ms | `FastOutSlowIn` |
| Transitions standards (page, sheet) | 250-300ms | `FastOutSlowIn` |
| Replan transitions (avant/après) | 400ms | `FastOutLinearIn` |
| Skeleton shimmer | 1500ms loop | `LinearEasing` |
| Halo Vector pulsing (analyzing) | 1200ms loop | `EaseInOutSine` |
| **Mode driving** | **toutes durations × 0.5** | éviter distraction |

---

## 11. Implementation Guardrail (Compose)

Avant d'implémenter un composant V1, l'équipe Compose vérifie :

1. Le token utilisé existe-t-il dans ce DS ? (Si non : escalation, pas d'invention.)
2. La radius / spacing / typography correspond-elle à l'échelle officielle ?
3. Le composant gère-t-il les 7 states (§7.7) ?
4. La couleur d'état (Success/Warning/Error/Info) est-elle accompagnée d'une icône + libellé ?
5. Le device par défaut testé est-il Tab S10 Ultra landscape ?
6. Le composant respecte-t-il la règle "no fake success" ?

Si une réponse est non, le composant n'est pas mergeable.

---

## 12. Annexes (à produire post-V1)

- `60_DESIGN_SYSTEM_TOKENS.kt` (extraction Kotlin auto-générée).
- `61_DESIGN_SYSTEM_COMPONENTS_CATALOG.md` (catalogue détaillé Compose).
- `62_DESIGN_SYSTEM_FIGMA_REF.md` (références Figma synchronisées).
- `63_DESIGN_SYSTEM_A11Y.md` (audit accessibilité WCAG complet).

---

**Document version :** 1.0
**Statut :** DRAFT V1 — toute déviation requiert PR.
**Last updated :** 2026-06-02
