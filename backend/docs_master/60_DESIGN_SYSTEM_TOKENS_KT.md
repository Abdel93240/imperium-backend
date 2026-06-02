# 60 — Design System Tokens Kotlin Compose V1

**Version :** 1.0
**Source de vérité :** `docs_master/59_DESIGN_SYSTEM_V1_DRAFT.md`
**Commit de référence :** `033277a` — Canonize design system V1 documentation
**Cible :** future implémentation Android natif Kotlin + Jetpack Compose Material 3
**Statut :** SPECIFICATION ONLY — aucun fichier Kotlin runtime n'est créé par ce document.

Ce document extrait les tokens Kotlin Compose prêts à implémenter depuis le Design System V1 canonique. Il ne remplace pas `59_DESIGN_SYSTEM_V1_DRAFT.md` : en cas de contradiction, le document 59 reste prioritaire.

---

## 1. Color Tokens

Les objets de couleurs sont des contrats de nommage pour la future couche Compose. Les couleurs d'état (`Success`, `Warning`, `Error`, `Info`) sont partagées par les 5 apps via `SemanticStateColors`. Les couleurs `VectorHaloColors` sont séparées et réservées au halo de conduite Vector.

### 1.1 ImperiumColors

| Token Kotlin | HEX | Mapping Compose attendu | Usage canonique |
|---|---|---|---|
| Primary | `#1A2B4A` | `primary` / top bars | Barre supérieure, surfaces de commande, bouton primary. |
| Secondary | `#2E4370` | `secondary` | Surfaces secondaires, cartes de mission. |
| Accent | `#C9A24B` | accent app custom | Reprogrammer la journée, emblèmes, badge current mission. Max 1 accent gold visible. |
| Background | `#0E1626` | `background` | Fond global dark mode. |
| Surface | `#16213A` | `surface` | Cards, panneaux. |
| SurfaceVariant | `#1F2D4D` | `surfaceVariant` | Cards imbriquées, listes alternées. |
| Border | `#2A3A5C` | `outline` | Bordures interactives 1dp. |
| Divider | `#1F2D4D` @ 60% | divider custom | Séparateurs. |
| TextPrimary | `#F5F7FA` | `onBackground` / `onSurface` | Titres, valeurs. |
| TextSecondary | `#B8C2D6` | `onSurfaceVariant` | Sous-titres, labels secondaires. |
| TextMuted | `#7886A0` | muted custom | Metadata, timestamps, captions. |
| Success | alias `SemanticStateColors.Success` | state custom | Mission completed, plan synced. |
| Warning | alias `SemanticStateColors.Warning` | state custom | Mission expiring soon. |
| Error | alias `SemanticStateColors.Error` | `error` | Replan failure, mission failed. |
| Info | alias `SemanticStateColors.Info` | state custom | AI advice banner. |

### 1.2 VaultColors

| Token Kotlin | HEX | Mapping Compose attendu | Usage canonique |
|---|---|---|---|
| Primary | `#163C2F` | `primary` | Top bar, header balance. |
| Secondary | `#28604E` | `secondary` | Cards transaction. |
| Accent | `#B58A4C` | accent app custom | Badge obligation, chip upcoming expense. |
| Background | `#0B1A14` | `background` | Fond global. |
| Surface | `#142A22` | `surface` | Cards. |
| SurfaceVariant | `#1B392E` | `surfaceVariant` | Cards imbriquées. |
| Border | `#264636` | `outline` | Bordures. |
| Divider | `#1B392E` | divider custom | Séparateurs. |
| TextPrimary | `#F2F7F4` | `onBackground` / `onSurface` | Montants principaux. |
| TextSecondary | `#B6C7BE` | `onSurfaceVariant` | Labels. |
| TextMuted | `#7A8D83` | muted custom | Metadata. |
| Success | alias `SemanticStateColors.Success` | state custom | Gain confirmé, transaction synced. |
| Warning | alias `SemanticStateColors.Warning` | state custom | Pressure score élevé. |
| Error | alias `SemanticStateColors.Error` | `error` | Expense overdue, balance négative. |
| Info | alias `SemanticStateColors.Info` | state custom | Suggestion sadaqa. |

Vault rule: all financial amounts use JetBrains Mono.

### 1.3 VectorColors

| Token Kotlin | HEX | Mapping Compose attendu | Usage canonique |
|---|---|---|---|
| Primary | `#0E2A33` | `primary` | Fond HUD standby V1. |
| Secondary | `#1C4753` | `secondary` | Cards info, side panel. |
| Accent | `#00D9E0` | accent app custom | Actions kinétiques. |
| Background | `#06181E` | `background` | Fond global. |
| Surface | `#0F2730` | `surface` | Cards. |
| SurfaceVariant | `#173744` | `surfaceVariant` | Cards imbriquées, popup lane. |
| Border | `#214756` | `outline` | Bordures HUD. |
| Divider | `#173744` | divider custom | Séparateurs. |
| TextPrimary | `#EEFAFD` | `onBackground` / `onSurface` | Titres. |
| TextSecondary | `#B6CCD2` | `onSurfaceVariant` | Labels. |
| TextMuted | `#778C92` | muted custom | Metadata. |
| Success | alias `SemanticStateColors.Success` | state custom | Etat UI positif confirmé. |
| Warning | alias `SemanticStateColors.Warning` | state custom | Etat UI warning. |
| Error | alias `SemanticStateColors.Error` | `error` | Etat UI erreur. |
| Info | alias `SemanticStateColors.Info` | state custom | Conseils non urgents. |

Vector rule: the driving halo uses `VectorHaloColors`, never `SemanticStateColors`.

### 1.4 PulseColors

| Token Kotlin | HEX | Mapping Compose attendu | Usage canonique |
|---|---|---|---|
| Primary | `#3D1418` | `primary` | Header. |
| Secondary | `#682430` | `secondary` | Cards workout, meal. |
| Accent | `#FF8C7A` | accent app custom | Badge today's workout, call-to-action. |
| Background | `#1A0A0D` | `background` | Fond global. |
| Surface | `#2A1015` | `surface` | Cards. |
| SurfaceVariant | `#3A1A20` | `surfaceVariant` | Cards imbriquées. |
| Border | `#4A222B` | `outline` | Bordures. |
| Divider | `#3A1A20` | divider custom | Séparateurs. |
| TextPrimary | `#FAEFEF` | `onBackground` / `onSurface` | Titres. |
| TextSecondary | `#D6BABC` | `onSurfaceVariant` | Labels. |
| TextMuted | `#967A7E` | muted custom | Metadata. |
| Success | alias `SemanticStateColors.Success` | state custom | Meal logged, workout completed. |
| Warning | alias `SemanticStateColors.Warning` | state custom | Low recovery. |
| Error | alias `SemanticStateColors.Error` | `error` | Pain logged high severity. |
| Info | alias `SemanticStateColors.Info` | state custom | Recommandation Pulse. |

### 1.5 PathColors

| Token Kotlin | HEX | Mapping Compose attendu | Usage canonique |
|---|---|---|---|
| Primary | `#0E3A2C` | `primary` | Header, top bar. |
| Secondary | `#1F5C46` | `secondary` | Cards prière, fasting. |
| Accent | `#D9B265` | accent app custom | Sadaqa target, badge ghusl required. |
| Background | `#071A14` | `background` | Fond global. |
| Surface | `#0F2A20` | `surface` | Cards. |
| SurfaceVariant | `#173A2C` | `surfaceVariant` | Cards imbriquées. |
| Border | `#214936` | `outline` | Bordures. |
| Divider | `#173A2C` | divider custom | Séparateurs. |
| TextPrimary | `#EEF7F2` | `onBackground` / `onSurface` | Titres. |
| TextSecondary | `#B6CFC2` | `onSurfaceVariant` | Labels. |
| TextMuted | `#7A938A` | muted custom | Metadata. |
| Success | alias `SemanticStateColors.Success` | state custom | Prière confirmée, fast complete. |
| Warning | alias `SemanticStateColors.Warning` | state custom | Prière proche, ghusl required. |
| Error | alias `SemanticStateColors.Error` | `error` | Prière manquée, jamais auto-déclenché. |
| Info | alias `SemanticStateColors.Info` | state custom | Rappel adhkar. |

### 1.6 SemanticStateColors

| Token Kotlin | HEX | Usage canonique |
|---|---|---|
| Success | `#34C759` | Confirmation backend, sync OK, action accomplie. Réservé aux états positifs confirmés. |
| Warning | `#F5A524` | Dérive légère, low confidence, sync lent. |
| Error | `#E5484D` | Echec sync, mission failed, blocage validé. Toujours accompagné d'un texte explicatif. |
| Info | `#0091FF` | Recommandation, conseil AI non urgent. Jamais en remplacement de Success. |

Accessibility rule: state color is never used alone. It must be paired with a Material Symbol and a visible label.

### 1.7 VectorHaloColors

| Token Kotlin | HEX | Usage canonique |
|---|---|---|
| HaloSuccess | `#22D673` | Recommandation conduite positive. |
| HaloWarning | `#F5C842` | Hésitation, low confidence conduite. |
| HaloError | `#FF4A4A` | Refuser la course. |
| HaloAnalyzing | `#FFFFFF` @ 80% | Analyse en cours. Future Compose value: `Color(0xCCFFFFFF)`. |

These tokens are not aliases of `SemanticStateColors`. In Vector navigation mode, the halo takes visual precedence over app accent, but cached/stale/sync labels remain explicit.

---

## 2. Typography Tokens

### 2.1 Font families

| Kotlin token | Font family | Scope |
|---|---|---|
| Primary | Inter variable | Default typography for all apps. |
| Numeric | JetBrains Mono variable | Vault amounts, mission IDs, prayer times, Vector KPIs. |
| Arabic | Noto Naskh Arabic | Path Arabic Quran/adhkar content only. |

Compose unit rule: all font sizes and line heights use `sp`. Letter spacing defaults to `0.sp` except Caption and Label.

### 2.2 Text styles

| Style token | Size sp | Weight | Line height sp | Letter spacing sp | Default family | Usage |
|---|---:|---:|---:|---:|---|---|
| Display | 56 | 700 | 64 | 0 | Primary | Splash, greeting, major dashboard KPI. |
| H1 | 40 | 700 | 48 | 0 | Primary | Main screen title. |
| H2 | 32 | 600 | 40 | 0 | Primary | Section title. |
| H3 | 24 | 600 | 32 | 0 | Primary | Card title. |
| H4 | 20 | 600 | 28 | 0 | Primary | Sub-section, dialog title, bottom sheet title. |
| BodyLarge | 18 | 400 | 28 | 0 | Primary | Main card body, AI advice, chat assistant. |
| BodyMedium | 16 | 400 | 24 | 0 | Primary | Lists, descriptions, forms. |
| BodySmall | 14 | 400 | 20 | 0 | Primary | Metadata and short descriptions. |
| Caption | 12 | 500 | 16 | 0.2 | Primary | Status labels, tags, image captions. |
| Label | 11 | 600 | 14 | 0.2 | Primary | Chips, badges, micro-labels, axis values. |

Responsive note: phone portrait reduces Display to 40, H1 to 32, H2 to 24, and H3 to 20. Other styles remain unchanged. Arabic Path text uses Noto Naskh Arabic Regular with +2sp over the equivalent body style.

---

## 3. Spacing Tokens

| Token Kotlin | Value dp | Usage canonique |
|---|---:|---|
| XXS | 2 | Sous-pixel borders, indicateurs très fins. |
| XS | 4 | Intra-chip spacing, icon-to-text gap inside one chip. |
| SM | 8 | Compact spacing, dense list items, badge-to-label. |
| MD | 16 | Base unit, internal card padding, standard list gap. |
| LG | 24 | Spacing between sections inside one card. |
| XL | 32 | Global screen padding on tablet landscape, gap between distinct cards. |
| XXL | 48 | Gap between semantically distinct zones. |
| XXXL | 64 | Hero top padding, scroll anchor reserved space. |

Anti-rule: no intermediate values such as 10dp, 14dp, or 20dp for spacing.

---

## 4. Radius Tokens

| Token Kotlin | Value dp | Usage canonique |
|---|---:|---|
| Chip | 8 | Filter chips and status chips. |
| Button | 12 | Primary, Secondary, Ghost, Destructive buttons. |
| Input | 12 | Text, number, search inputs. |
| Card | 16 | Main surface cards. |
| BottomSheet | 24 | Top-left and top-right only. Bottom remains flat. |
| Dialog | 20 | Centered modal dialogs. |

Additional source tokens from doc 59 for future extraction: `Fullscreen = 0`, `Avatar = 50%`, `ImageCard = 16`.

---

## 5. Elevation Tokens

| Token Kotlin | Tonal elevation dp | Shadow guidance | Usage canonique |
|---|---:|---|---|
| L0 | 0 | none | Full-screen background, section background. |
| L1 | 1 | none / 1dp at 8% black | Static card. |
| L2 | 3 | 2dp at 12% black | Interactive card hover/press, raised card. |
| L3 | 6 | 4dp at 16% black | Modal, Dialog, Bottom Sheet, AlertDialog. |
| L4 | 12 | 6dp at 24% black | Floating Top App Bar, FAB, Vector halo overlay. |

Compose rule: use Material 3 `Surface(tonalElevation = ...)`. In dark mode, elevation is a subtle surface lightening, not a strong shadow.

---

## 6. Icon Size Tokens

| Token Kotlin | Value dp | Usage canonique |
|---|---:|---|
| Inline | 16 | Icon inside Body text. |
| InputAdornment | 20 | Leading/trailing TextField icon. |
| Action | 24 | Toolbar action, chip icon. |
| Navigation | 28 | Bottom navigation tabs. |
| TopBarAction | 24 | Top bar icon buttons. |
| Avatar | 40 | User avatar, Vector status circles. |
| AppEmblem | 48 | App identity in headers. |
| WidgetHero | 64 | Home widget hero image. |
| PremiumAsset | 96 or 128 | Morning Check-In, Weekly Review, milestones, empty states. |

Icon source rule: Material Symbols Outlined, weight 400, grade 0, optical size auto. Emojis are not icons.

---

## 7. State Tokens

### 7.1 ImperiumSyncState

| Enum value | Canonical meaning | Color mapping |
|---|---|---|
| Pending | Local action exists but backend confirmation has not started or completed. | Warning or neutral pending chip. |
| Syncing | Backend sync is currently in progress. | Warning plus progress indicator. |
| Synced | Backend confirmation succeeded. | `SemanticStateColors.Success`. |
| Failed | Backend or workflow sync failed. | `SemanticStateColors.Error`. |
| Conflict | Local and server state disagree and user/backend review is required. | `SemanticStateColors.Error`. |
| Cached | Data is from cache but still acceptable for display with timestamp. | Info or neutral cached chip. |
| Stale | Cached data is too old or invalid for decision-grade display. | Warning with explicit stale label. |

### 7.2 Screen state note

The foundation screen states from doc 59 remain required for every screen: `Loading`, `Empty`, `Error`, `Offline`, `Syncing`, `Synced`, `Conflict`. They may reuse `ImperiumSyncState` values where appropriate, but they are layout states, not only sync states.

---

## 8. Kotlin naming conventions

### 8.1 Package suggestion

Suggested package for the future Android implementation:

```kotlin
package com.imperium.designsystem.tokens
```

This package is a suggestion only. No Kotlin file is created in this patch.

### 8.2 Object names

Required objects:

| Token family | Object name |
|---|---|
| Imperium app colors | `ImperiumColors` |
| Vault app colors | `VaultColors` |
| Vector app colors | `VectorColors` |
| Pulse app colors | `PulseColors` |
| Path app colors | `PathColors` |
| Cross-app semantic states | `SemanticStateColors` |
| Vector driving halo | `VectorHaloColors` |
| Typography | `ImperiumTypography` |
| Font families | `ImperiumFontFamilies` |
| Spacing | `ImperiumSpacing` |
| Radius | `ImperiumRadius` |
| Elevation | `ImperiumElevation` |
| Icon sizes | `ImperiumIconSize` |

Token properties use PascalCase: `Primary`, `SurfaceVariant`, `TextPrimary`, `BodyLarge`, `BottomSheet`, `TopBarAction`.

### 8.3 Enum names

Required enums:

| Enum | Values |
|---|---|
| `ImperiumAppId` | `Imperium`, `Vault`, `Vector`, `Pulse`, `Path` |
| `ImperiumSyncState` | `Pending`, `Syncing`, `Synced`, `Failed`, `Conflict`, `Cached`, `Stale` |
| `ImperiumScreenState` | `Loading`, `Empty`, `Error`, `Offline`, `Syncing`, `Synced`, `Conflict` |

Enums are never localized. User-facing strings are resolved by the UI layer.

### 8.4 Compose Material 3 mapping

Future Compose implementation should map each app palette into a Material 3 dark `ColorScheme`:

| Material 3 field | Token source |
|---|---|
| `primary` | App `Primary` |
| `secondary` | App `Secondary` |
| `background` | App `Background` |
| `surface` | App `Surface` |
| `surfaceVariant` | App `SurfaceVariant` |
| `outline` | App `Border` |
| `error` | `SemanticStateColors.Error` |
| `onBackground` | App `TextPrimary` |
| `onSurface` | App `TextPrimary` |
| `onSurfaceVariant` | App `TextSecondary` |

Custom CompositionLocals should carry values Material 3 does not model directly: `Accent`, `Divider`, `TextMuted`, `SemanticStateColors`, `VectorHaloColors`, spacing, radius, icon sizes, and app-specific token object.

Typography maps to Material 3 text roles conservatively:

| Imperium token | Suggested Material 3 role |
|---|---|
| Display | `displayLarge` |
| H1 | `headlineLarge` |
| H2 | `headlineMedium` |
| H3 | `titleLarge` |
| H4 | `titleMedium` |
| BodyLarge | `bodyLarge` |
| BodyMedium | `bodyMedium` |
| BodySmall | `bodySmall` |
| Caption | `labelMedium` |
| Label | `labelSmall` |

---

## 9. Non-goals

- No Android frontend creation.
- No Kotlin runtime implementation yet.
- No real `.kt` file.
- No `android/` directory.
- No `frontend/` directory.
- No asset import.
- No screen implementation.
- No change to backend runtime.
- No change to the canonical Design System V1 except through a future PR against `docs_master/59_DESIGN_SYSTEM_V1_DRAFT.md`.

---

## 10. Implementation guardrails for the future

- Do not invent a token missing from doc 59 or this extraction spec.
- Do not use Vector halo colors as generic success/warning/error colors.
- Do not use `SemanticStateColors.Success` for drafts, local-only actions, or pending sync.
- Do not localize Kotlin object names or enum values.
- Do not let app frontends create strategy. Tokens support display, input, actions and recommendations only.
- Keep dark mode as V1 default. Light mode is V2.

**Document version :** 1.0
**Statut :** TOKEN SPEC V1 — ready for future Kotlin Compose implementation, not implemented yet.
**Last updated :** 2026-06-02
