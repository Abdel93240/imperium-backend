# 64 — Frontend Generation Plan V1

**Version :** 1.0
**Sources de vérité :** `docs_master/59_DESIGN_SYSTEM_V1_DRAFT.md`, `docs_master/60_DESIGN_SYSTEM_TOKENS_KT.md`, `docs_master/61_DESIGN_SYSTEM_COMPOSITE_COMPONENTS.md`, `docs_master/62_DESIGN_SYSTEM_COMPONENT_CATALOG.md`, `docs_master/63_FRONTEND_ARCHITECTURE_V1.md`, `docs_master/07_ANDROID_APP_RESPONSIBILITIES.md`
**Cible :** génération future Android natif Kotlin + Jetpack Compose + Material 3
**Device principal :** Samsung Galaxy Tab S10 Ultra, landscape primaire
**Statut :** CANONICAL FRONTEND GENERATION PLAN V1 — documentation only, aucun Kotlin, aucun dossier `android/`, aucun runtime frontend, aucun scaffold Android et aucun backend modifié.

Ce document définit l'ordre officiel de génération du frontend V1. Il verrouille la séquence de travail avant toute génération massive afin de préserver la vision produit : les apps sont des interfaces, le backend reste le cerveau.

---

## 1. Mission du document

Ce document a quatre missions :

1. Définir l'ordre officiel de génération des applications et des écrans V1.
2. Définir les critères de validation nécessaires avant de passer d'une phase à la suivante.
3. Définir les dépendances documentaires, visuelles, fonctionnelles et backend.
4. Définir la stratégie de branchement backend : aucune connexion backend réelle avant validation visuelle complète de l'écran.

Le document ne crée pas de runtime frontend. Il sert de plan de génération, de checklist de validation et de garde-fou pour les worktrees de design.

## 2. Règle fondamentale

La génération frontend V1 suit obligatoirement ces phases :

| Phase | Nom | Autorisé | Interdit |
|---|---|---|---|
| Phase 1 | UI pure | Écran statique, composants visuels, navigation locale de preview, responsive tablette. | API réelle, repository réseau, ViewModel connecté, données backend. |
| Phase 2 | Mock data | Fixtures contrôlées, états visuels, navigation mock, scénarios tablette. | Connexion backend, n8n, PostgreSQL, pgvector, endpoint live. |
| Phase 3 | Backend wiring | Branchement endpoint documenté/testé, loading, empty, error, sync states. | Branchement d'un endpoint non documenté ou non testé. |
| Phase 4 | Polish | Ajustements visuels, accessibilité, micro-interactions sobres, validation finale tablette. | Changement de logique métier, ajout de scope V2/V3. |

Interdiction explicite :

> Aucun branchement backend avant validation visuelle complète de l'écran.

Conséquences pratiques :

- Le backend ne sert pas à compenser une UI non validée.
- Les mocks ne doivent pas créer de vérité canonique.
- Les écrans doivent d'abord prouver leur lisibilité, leur navigation et leur conformité au Design System.
- Le passage en Phase 3 est impossible sans validation humaine de la preview.

## 3. Ordre officiel des applications

| Ordre | Application | Justification V1 |
|---|---|---|
| 1 | Imperium | Command center prioritaire ; il porte la mission active unique, la journée, l'inbox et la weekly review. |
| 2 | Vault | Réalité financière nécessaire pour la clarté hebdomadaire et le lien sadaqa vers Path. |
| 3 | Path | Discipline spirituelle et sadaqa dépendent partiellement de Vault ; priorité personnelle forte mais moins bloquante qu'Imperium/Vault. |
| 4 | Pulse | Santé et nutrition doivent rester simples ; important pour le quotidien mais moins central pour l'orchestration V1. |
| 5 | Vector | VTC advice arrive après le socle command/finance/spiritualité ; il doit rester advisory et platform-safe. |

Cet ordre respecte le MVP : missions Imperium, suivi financier Vault, workflows n8n, PostgreSQL, AI routing, voice input, Vector advice basique, Pulse simple, Path simple.

## 4. Ordre officiel des écrans Imperium

Les écrans Imperium sont générés dans cet ordre minimum. Chaque écran démarre en Phase 1, passe en Phase 2 après validation structurelle, puis passe en Phase 3 uniquement quand les critères fonctionnels sont remplis.

| Ordre | Écran | Status | Dependencies | Validation Criteria |
|---|---|---|---|---|
| 01 | Dashboard | READY FOR UI PURE | Design System, Component Catalog, Screen Architecture, Navigation V1, fixtures dashboard. | Vue command center lisible, mission active visible sans ambiguïté, KPI non inventés, responsive tablette, aucun placeholder cassé. |
| 02 | Mission Active | READY FOR UI PURE | Dashboard shell, MissionFocusCard, règle une seule mission active, fixtures mission active/empty/overdue. | Une seule mission active affichée, actions finish/fail/replan claires, états empty/error prévus, aucune décision locale canonique. |
| 03 | Inbox | READY FOR UI PURE | Navigation V1, ImperiumListItem, filters, fixtures inbox. | Capture rapide des entrées, tri visuel clair, empty state, action de transformation en mission explicitement backend-validée. |
| 04 | Weekly Review | READY FOR UI PURE | WeeklyReviewCard, workflow weekly review, fixtures review ready/incomplete/error. | Lecture hebdomadaire structurée, décisions non finalisées localement, étapes visibles, validation tablette. |
| 05 | History | READY FOR UI PURE | ImperiumTimeline, mission history contracts, filters, fixtures history. | Chronologie lisible, statuts complets, filtres cohérents, cache/stale visible. |
| 06 | Settings | READY FOR UI PURE | Settings sections, priority rules docs, sync state components, fixtures preferences. | Préférences séparées des règles backend, aucun toggle ne prétend modifier une règle canonique sans validation backend. |

Statuts autorisés pour ce plan :

- `READY FOR UI PURE`
- `UI VALIDATED`
- `MOCK DATA VALIDATED`
- `READY FOR BACKEND WIRING`
- `BACKEND WIRED`
- `DONE`

## 5. Mock Data Strategy

La Phase 2 utilise exclusivement des données fictives contrôlées :

- aucune API réelle ;
- aucune connexion backend ;
- aucun appel n8n ;
- aucune lecture PostgreSQL ;
- aucune écriture PostgreSQL ;
- aucune mémoire vectorielle ;
- aucune décision AI canonique ;
- données clairement nommées comme fixtures de démonstration.

Les mocks servent à valider l'écran, pas à définir la stratégie métier.

Exemple Imperium Dashboard :

```json
{
  "screen": "IMP-01",
  "fixture_name": "dashboard_with_active_mission",
  "sync_state": "mock",
  "active_mission": {
    "id": "mock-mission-001",
    "title": "Finish weekly financial review",
    "status": "active",
    "priority": "high",
    "deadline": "2026-06-02T18:00:00Z"
  },
  "daily_focus": {
    "label": "Execution",
    "reason": "Demo fixture only"
  },
  "metrics": {
    "missions_done_today": 2,
    "vault_weekly_profit_eur": 340.5,
    "path_prayers_confirmed": 3
  }
}
```

Exemple état vide Mission Active :

```json
{
  "screen": "IMP-02",
  "fixture_name": "mission_active_empty",
  "sync_state": "mock",
  "active_mission": null,
  "empty_state": {
    "title": "No active mission",
    "body": "Waiting for backend-confirmed next mission in real wiring."
  }
}
```

Exemple erreur contrôlée :

```json
{
  "screen": "IMP-04",
  "fixture_name": "weekly_review_error",
  "sync_state": "mock",
  "error_state": {
    "code": "MOCK_WEEKLY_REVIEW_UNAVAILABLE",
    "message": "Demo error state for visual validation only."
  }
}
```

## 6. Design Validation Checklist

Un écran est validé visuellement uniquement si tous les critères suivants sont cochés :

| Critère | Required |
|---|---|
| ✓ Responsive tablette | YES |
| ✓ Respecte Design System | YES |
| ✓ Respecte Component Catalog | YES |
| ✓ Respecte Navigation | YES |
| ✓ Respecte Spacing | YES |
| ✓ Respecte Architecture V1 | YES |
| ✓ Aucun placeholder cassé | YES |

Cette validation est humaine et bloque le branchement backend.

## 7. Functional Validation Checklist

Un écran peut être branché backend uniquement si tous les critères suivants sont cochés :

| Critère | Required |
|---|---|
| ✓ UI validée | YES |
| ✓ Endpoint existant | YES |
| ✓ Endpoint documenté | YES |
| ✓ Endpoint testé | YES |
| ✓ Loading state | YES |
| ✓ Empty state | YES |
| ✓ Error state | YES |

Le backend wiring doit respecter `63_FRONTEND_ARCHITECTURE_V1.md` : `Screen → UiEvent → ViewModel → Repository → API → Backend validation → Repository cache/read model → UiState → Screen`.

## 8. Claude Design Pipeline

Pipeline officiel :

```text
Prompt
↓
Worktree
↓
Preview URL
↓
Validation humaine
↓
Correction éventuelle
↓
Merge
```

Règles du pipeline :

- Un worktree par écran ou petit groupe cohérent d'écrans.
- La Preview URL sert à valider la Phase 1 et la Phase 2.
- La validation humaine est obligatoire avant tout branchement backend.
- Les corrections visuelles restent dans le worktree de l'écran.
- Le merge ne doit pas inclure de backend wiring non validé.

## 9. Screen Completion Gate

Un écran Imperium V1 ne peut pas être déclaré terminé par un générateur frontend tant que la Definition of Done canonique de la section 12 n'est pas entièrement cochée.

Cette règle sépare volontairement :

- la validation visuelle et mock-data, qui rend un écran prêt pour revue ;
- le branchement backend futur, qui reste interdit tant que les phases précédentes ne sont pas validées ;
- la complétion d'écran GO 64/65, qui reste documentaire et ne crée aucun runtime Android.

## 10. Global Frontend Foundation Readiness V1

| Area | Status |
|---|---|
| Design System | READY |
| Component Catalog | READY |
| Screen Architecture | READY |
| Frontend Architecture | READY |
| Generation Plan | READY |
| Android Runtime | NOT STARTED |

## 11. Constraints

Ce GO 64 est documentation uniquement.

Contraintes non négociables :

- Aucun code Kotlin.
- Aucun dossier `android/`.
- Aucun runtime frontend.
- Aucun scaffold Android.
- Aucun backend modifié.
- Documentation uniquement.
- Tests documentaires pytest verrouillant les sections clés.

## 12. Definition of Done

Un écran est terminé uniquement si tous les critères suivants sont cochés :

| Critère | Required |
|---|---|
| ✓ UI validée | YES |
| ✓ Navigation validée | YES |
| ✓ Responsive validé | YES |
| ✓ Loading validé | YES |
| ✓ Empty validé | YES |
| ✓ Error validé | YES |
| ✓ Mock data validée | YES |

La Definition of Done ne s'applique pas à la Phase 1 seule. Un écran peut être visuellement validé sans être terminé.

## 13. Frontend Generation Readiness

Tableau obligatoire pour la génération future des écrans Imperium GO 65 :

| Screen | Status |
|---|---|
| Dashboard | READY |
| Mission Active | READY |
| Inbox | READY |
| Weekly Review | READY |
| History | READY |
| Settings | READY |

**Document version :** 1.0
**Statut :** FRONTEND GENERATION PLAN V1 — ready for future screen generation, not implemented yet.
**Last updated :** 2026-06-02
