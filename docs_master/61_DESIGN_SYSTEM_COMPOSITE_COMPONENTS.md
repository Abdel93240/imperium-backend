# 61 — Design System Composite Components V1

**Version :** 1.0
**Sources de vérité :** `docs_master/59_DESIGN_SYSTEM_V1_DRAFT.md`, `docs_master/60_DESIGN_SYSTEM_TOKENS_KT.md`
**Cible :** future implémentation Android natif Kotlin + Jetpack Compose Material 3
**Statut :** SPECIFICATION ONLY — aucun composant Compose réel, fichier Kotlin, Android frontend ou asset n'est créé par ce document.

Ce document précise comment reconstruire les visuels premium du Design System V1 comme composants dynamiques/composés. Il ne remplace pas le Design System V1 canonique. En cas de contradiction, `59_DESIGN_SYSTEM_V1_DRAFT.md` reste prioritaire, puis `60_DESIGN_SYSTEM_TOKENS_KT.md` pour les tokens.

---

## 1. Principe central

Un asset premium ne doit jamais contenir une donnée dynamique figée.

Canonical English rule for tests and future implementation:

```text
premium asset must not contain dynamic data
```

Un visuel peut contenir une ambiance, une texture, une bordure, une icône, une frame ou un motif décoratif. Il ne doit pas contenir de montant réel, date, horaire, compteur, statut, texte utilisateur, recommandation, score, progress, bouton, slider, waveform fonctionnelle ou état métier. Ces éléments sont rendus par Compose à partir des données backend.

Raison produit : les apps sont des interfaces. Le backend, n8n, PostgreSQL, pgvector et l'AI router restent le cerveau. Un asset figé ne doit jamais inventer ou fossiliser une décision, un état financier, une prière, une mission ou une recommandation.

---

## 2. Taxonomie

| Type | Définition | Autorisé dans l'asset | Interdit dans l'asset |
|---|---|---|---|
| Static Asset | Image non interactive et non data-driven. | Motif, icône, illustration, texture, arrière-plan non informatif. | Texte dynamique, chiffres, dates, progress, états. |
| Decorative Shell | Cadre premium autour d'un contenu Compose. | Frame, border, glow, ornament, placeholder visuel. | Valeur métier, label d'état, bouton cliquable. |
| Dynamic Compose Component | Composant dont le contenu est rendu par Compose depuis un contrat de données. | Aucun asset obligatoire. | Donnée figée dans un bitmap. |
| Composite Component | Assemblage d'un Decorative Shell ou Static Asset avec des parties Compose dynamiques. | Shell décoratif, icône premium, frame. | Données réelles intégrées à l'image. |
| Interactive Component | Composant avec actions utilisateur. | Décor non cliquable. | Boutons, sliders, toggles ou zones de tap rendus dans l'image. |
| Animated Component | Composant avec animation pilotée par état ou progress. | Texture, glow, masque, frame. | Animation qui affiche une valeur non pilotée par Compose/backend. |

---

## 3. Règles de rendu

- Les textes sont rendus par Compose avec les styles de `60_DESIGN_SYSTEM_TOKENS_KT.md`.
- Les montants sont rendus par Compose, avec `ImperiumFontFamilies.Numeric` pour Vault.
- Les dates, horaires et durées sont rendus par Compose.
- Les progress, rings, bars, gauges, remplissages et waveforms fonctionnelles sont rendus par Compose.
- Les boutons interactifs, sliders, toggles, menus, chips et actions sont rendus par Compose.
- Les états métier et sync (`Loading`, `Empty`, `Error`, `Offline`, `Syncing`, `Synced`, `Conflict`) sont rendus par Compose.
- Les couleurs d'état ne sont jamais le seul signal : elles sont accompagnées d'une icône ou d'un libellé visible.
- Accessibility is mandatory: chaque composant dynamique doit définir un label lisible par lecteur d'écran, un ordre de focus cohérent, un état annoncé et une cible tactile adaptée.
- Les assets décoratifs doivent être marqués décoratifs quand ils n'ajoutent aucune information.
- Les composants conduites Vector doivent rester lisibles rapidement et ne pas distraire.
- Les composants Path avec texte arabe utilisent la famille Arabic prévue par les tokens.

---

## 4. Catalogue Imperium

| Component | Purpose | Static asset parts | Dynamic Compose parts | Interactive parts | States | Animation | Accessibility notes | Data dependencies |
|---|---|---|---|---|---|---|---|---|
| MissionFocusCard | Afficher l'unique mission active et guider l'action immédiate. | Shell navy/gold, emblem mission, subtle command frame. | Mission title, reason, deadline, priority, sync label. | Start, complete, fail, replan. | No active mission, active, overdue, syncing, conflict, failed. | Deadline pulse when close; no animation during driving. | Announce "current mission"; expose one primary action first. | Active mission contract, day plan, priority rules, sync state. |
| DailyPlanCard | Résumer le plan du jour et ses blocs utiles. | Decorative timeline frame. | Blocks, times, mission count, failure reasons, backend status. | Open plan, activate mission, replan day. | Empty, planned, partially done, stale, conflict. | Progress line based on completed blocks. | Times read in chronological order; stale data announced. | Daily plan, mission backlog, day finished workflow. |
| WeeklyReviewCard | Montrer la revue hebdomadaire et les décisions validées. | Premium review frame, ledger ornament. | Week dates, score, wins, failures, recommendations. | Open review, acknowledge, create follow-up mission. | Loading, ready, submitted, incomplete, error. | Score count-up only after data load. | Scores include text equivalents, not color only. | Weekly report workflow, missions history, Vault summary. |
| AIRecommendationCard | Afficher une recommandation backend/AI avec confiance. | AI shell, info icon. | Recommendation text, confidence, model/source, timestamp. | Accept, reject, ask why, defer. | Draft, pending validation, accepted, rejected, expired. | Subtle analyzing shimmer while routing. | Announce confidence and source; actions labelled explicitly. | AI router result, workflow logs, user validation status. |
| KPIBlock | Afficher un KPI opérationnel compact. | Optional mini-frame or icon. | Label, value, delta, unit, state chip. | Open detail where relevant. | Normal, warning, error, stale, cached. | Delta transition when value changes. | Numeric value has unit in content description. | Dashboard metrics, sync state, app-specific KPI source. |
| ChatMessageBubble | Afficher échange utilisateur/assistant dans Imperium. | Optional avatar shell. | Message text, sender, timestamp, tool/model label. | Copy, retry, rate, open linked action. | Sending, sent, failed, tool-running, stale context. | Typing indicator; no fake final text. | Sender and delivery state announced. | Conversation log, AI task result, tool execution status. |

---

## 5. Catalogue Vault

| Component | Purpose | Static asset parts | Dynamic Compose parts | Interactive parts | States | Animation | Accessibility notes | Data dependencies |
|---|---|---|---|---|---|---|---|---|
| FinancialPressureCard | Montrer la pression financière réelle. | Bronze/green pressure shell. | Score, explanation, obligations, weekly reality. | Open explanation, log transaction. | Low, medium, high, stale, error. | Gauge sweep from previous score. | Score has text severity and reason. | Financial pressure formula, income, expenses, obligations. |
| TransactionRow | Afficher une transaction traçable. | Category icon only. | Amount, category, date, note, source, sync state. | Edit, reverse, attach receipt. | Draft, synced, failed, reversed, pending review. | Row insert/update transition. | Amount announces income/expense direction. | Transaction table, category table, receipt extraction. |
| ReceiptReviewCard | Vérifier une extraction du service OCR. | Receipt frame, scan texture. | Merchant, amount, date, confidence, extracted lines. | Confirm, correct, reject. | Extracting, needs review, confirmed, rejected, failed. | Confidence highlight after extraction. | Low confidence fields announced individually. | OCR service extraction result, transaction draft, image metadata. |
| WalletBalanceCard | Afficher la réalité de caisse. | Wallet shell. | Balance, cash/card split, last update, warning. | Update wallet, open history. | Current, stale, negative, syncing, conflict. | Balance change transition. | Negative balance includes explicit warning text. | Wallet balances, transaction rollup, sync state. |
| SavingsProgressRing | Montrer progression vers objectif. | Ring frame only. | Progress arc, saved amount, target, percent. | Open goal, adjust target. | No goal, in progress, reached, behind, stale. | Arc animates to backend percent. | Percent and amounts announced together. | Savings goal, Vault summary, weekly profit. |
| MonthlyReviewCard | Résumer le mois financier. | Monthly ledger shell. | Income, expenses, profit, categories, status. | Open month, export, create action. | Ready, incomplete, loss, surplus, error. | KPI reveal after load. | Profit/loss text does not rely on red/green alone. | Monthly rollup, categories, obligations, sadaqa handoff. |

---

## 6. Catalogue Vector

| Component | Purpose | Static asset parts | Dynamic Compose parts | Interactive parts | States | Animation | Accessibility notes | Data dependencies |
|---|---|---|---|---|---|---|---|---|
| VectorHalo | Donner un état de décision conduite clair. | Halo shell/glow texture only. | Halo color, status label, confidence, reason. | Ask why, refresh advice, start/end session. | Standby, analyzing, go, wait, avoid, offline, stale. | Breathing halo; color from `VectorHaloColors`. | State label visible and announced; color never alone. | VTC session, zone score, traffic/events, AI routing result. |
| DemandRing | Visualiser demande estimée par zone. | Ring frame/map ornament. | Demand score, confidence, trend, zone name. | Open zone detail, compare zones. | Low, medium, high, uncertain, stale. | Ring fills to score. | Score has numeric and verbal label. | Zone history, events, traffic, time window. |
| RecommendationCard | Conseiller où aller sans automatiser Bolt. | Tactical card shell. | Recommendation, reasoning, ETA, expected value. | Accept as plan, dismiss, ask alternative. | Fresh, stale, low confidence, offline, conflict. | Analyzing shimmer only while pending. | Legal/platform-safe advisory wording. | AI recommendation, zone priority, disruption feed. |
| ZonePriorityCard | Classer les zones VTC. | Zone badge/shell. | Zone name, rank, score, reason, last update. | Select zone, navigate externally if user chooses. | Ranked, skipped, stale, low data. | Rank change transition. | Rank and reason read together. | Zone priority scoring, history, events, revenue objective. |
| TrafficAlertPanel | Montrer perturbation utile en conduite. | Alert shell, route icon. | Alert title, severity, location, ETA impact. | Dismiss, open map, mark irrelevant. | Info, warning, severe, expired, offline. | Severity pulse for severe only. | Severity text required; dismiss button labelled. | Traffic feed, transport disruptions, current zone. |
| SessionStatusCard | Suivre session VTC et objectif revenu. | Session shell, vehicle icon. | Duration, revenue, target, pace, break status. | Start, pause, end, log income. | Not started, active, paused, ended, syncing, failed. | Pace/progress bar updates from session data. | Time and revenue include units. | VTC session log, Vault income handoff, objective. |

---

## 7. Catalogue Pulse

| Component | Purpose | Static asset parts | Dynamic Compose parts | Interactive parts | States | Animation | Accessibility notes | Data dependencies |
|---|---|---|---|---|---|---|---|---|
| HydrationDrop | Montrer l'eau consommée simplement. | Drop/frame/mask texture. | Fill level, wave, current ml, target, percent. | Add glass, edit intake. | Empty, behind, on track, target reached, stale. | Animated fill and wave from Compose progress. | Percent and ml target announced; tap target large. | Hydration logs, daily target, time of day. |
| MacroProgressCard | Résumer macros du jour. | Food/macro shell icons. | Protein, carbs, fat, calories, progress bars. | Add meal, open meal log. | Empty, partial, complete, over target, stale. | Bars animate to logged totals. | Each macro announces consumed and target. | Meal logs, nutrition targets, food stock. |
| WorkoutActivityCard | Suivre activité ou séance. | Workout icon/frame. | Exercise, sets, duration, completion, notes. | Start, complete, skip, edit. | Planned, active, completed, skipped, failed sync. | Active timer/progress. | Timer and action labels explicit. | Workout plan, activity logs, recovery status. |
| RecoveryRing | Donner un signal récupération simple. | Ring shell. | Recovery score, sleep/training hints, warning. | Open recovery detail. | Good, moderate, low, missing data, stale. | Ring fills to score. | Low recovery includes text reason. | Sleep, workout load, body status. |
| SleepScoreCard | Afficher sommeil utile à la journée. | Night shell/icon. | Sleep duration, quality score, bedtime, wake time. | Log/edit sleep. | Missing, logged, low, good, stale. | Score reveal. | Duration announced in hours/minutes. | Sleep logs, recovery calculation. |
| BodyStatusWidget | Montrer état corporel sans complexité. | Body silhouette/frame. | Weight, waist, progress, note, trend. | Log measure, open history. | No data, updated, improving, plateau, warning. | Trend transition. | Measurements include units and date. | Body measurements, goal, progress history. |

---

## 8. Catalogue Path

| Component | Purpose | Static asset parts | Dynamic Compose parts | Interactive parts | States | Animation | Accessibility notes | Data dependencies |
|---|---|---|---|---|---|---|---|---|
| HijriDateCard | Afficher la date hijri et contexte spirituel. | Decorative Islamic frame, subtle ornament. | Hijri date, Gregorian date, event label, timezone note. | Open calendar, adjust verified date if backend allows. | Current, estimated, verified, stale, error. | Gentle date reveal on refresh. | Dates announced in full; decorative frame hidden from screen reader. | Path calendar, locale, timezone, date verification source. |
| QuranAudioPlayer | Lire audio Quran avec contrôles réels. | Player frame, optional reciter artwork shell. | Surah/ayah title, waveform, slider, duration, playback state. | Play, pause, seek, next, previous, speed where allowed. | Loading, ready, playing, paused, buffering, failed, offline. | Waveform and slider progress from playback state. | Media buttons have content labels; slider exposes position/duration. | Quran audio metadata, playback position, network/cache status. |
| TasbihCounter | Compter dhikr sans figer la valeur. | Bead/chapelet asset, counter shell. | Count, target, progress, dhikr label. | Increment, reset, choose dhikr. | Zero, counting, target reached, saved, failed sync. | Bead tick or progress animation per increment. | Increment button label includes current count and target. | Dhikr session, target, Path history, sync state. |
| PrayerStatusCard | Afficher état prière, horaire et action. | Prayer visual shell, masjid/line ornament. | Prayer name, time, remaining time, status, reason. | Mark prayed, mark missed with reason, open details. | Upcoming, due soon, prayed, late, missed, qada, syncing. | Due-soon pulse; no auto miss animation. | Status and time announced; missed state requires explicit text. | Prayer times, user confirmation, timezone, Path rules. |
| FastingProgressCard | Suivre jeûne du jour ou planifié. | Fasting shell, moon/sun ornament. | Suhoor/iftar times, progress, intention status, notes. | Start/confirm fast, break fast, log reason. | Planned, active, completed, broken, missed, stale. | Daylight progress bar from current time. | Progress includes time remaining; actions confirm intent. | Fasting log, prayer calendar, local time. |
| SadaqaProgressCard | Relier sadaqa au profit Vault. | Gold/emerald giving shell. | Weekly profit, sadaqa target, paid amount, remaining amount. | Mark paid, open Vault source, adjust note. | No profit data, calculated, partially paid, paid, overdue, stale. | Progress bar/ring to target. | Amounts announced with currency and source week. | Vault weekly profit, sadaqa rule, payment log. |

---

## 9. Non-goals

- Ne pas créer Kotlin.
- Ne pas créer Android.
- Ne pas importer assets.
- Ne pas créer de frontend.
- Ne pas créer de composant Compose runtime.
- Ne pas modifier le backend runtime.
- Ne pas ajouter `android/`.
- Ne pas ajouter `frontend/`.
- Ne pas créer de vrai `.kt`.
- Ne pas modifier le Design System canonique sauf référence stricte depuis un futur patch dédié.

**Document version :** 1.0
**Statut :** COMPOSITE COMPONENT SPEC V1 — ready for future Compose implementation, not implemented yet.
**Last updated :** 2026-06-02
