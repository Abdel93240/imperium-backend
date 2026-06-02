# 66 - Imperium User Flows V1

**Version :** 1.0
**Sources de verite :** `65_IMPERIUM_FRONTEND_SCREEN_SPEC_V1.md`, `64_FRONTEND_GENERATION_PLAN_V1.md`, `43_IMPERIUM_LOGIC_DETAIL.md`, `07_ANDROID_APP_RESPONSIBILITIES.md`
**Statut :** CANONICAL IMPERIUM USER FLOWS V1 - documentation only, aucun runtime, aucun backend, aucun Android.
**Last updated :** 2026-06-02

Ce document definit les parcours utilisateur officiels Imperium V1.
Il decrit les transitions entre ecrans, les actions utilisateur autorisees et les sorties autorisees.
Il reste strictement coherent avec `65_IMPERIUM_FRONTEND_SCREEN_SPEC_V1.md`.

## 1. Scope

- Documentation uniquement.
- Aucun runtime.
- Aucun backend.
- Aucun Android.
- Aucun endpoint.
- Aucun modele.
- Aucun schema.
- Aucun Kotlin.
- Aucun Compose.
- Aucune logique metier nouvelle.

## 2. Dashboard Flows

Le Dashboard est la porte d entree officielle de Imperium V1.
Il peut aussi servir de point de retour pour les autres flows.
Une seule mission active peut etre visible a la fois.

### 2.1 Open app

- Start Route: `APP_LAUNCH`
- Target Route: `IMP.DASH.MAIN`
- Allowed Actions: ouvrir l app, lire le statut global, voir la mission active, acceder aux destinations documentees.
- Exit Conditions: le Dashboard est rendu et le user peut choisir une destination documentee.

### 2.2 Consult active mission

- Start Route: `IMP.DASH.MAIN`
- Target Route: `IMP.MISSION.ACTIVE`
- Allowed Actions: ouvrir la mission active, lire le contexte complet, ajouter une note, modifier le statut.
- Exit Conditions: retour vers Dashboard ou poursuite explicite de la mission active.

### 2.3 Access inbox

- Start Route: `IMP.DASH.MAIN`
- Target Route: `IMP.INBOX.MAIN`
- Allowed Actions: ouvrir Inbox, lire les conversations, rechercher, filtrer, selectionner une conversation.
- Exit Conditions: retour vers Dashboard ou selection terminee dans Inbox.

### 2.4 Access history

- Start Route: `IMP.DASH.MAIN`
- Target Route: `IMP.HISTORY.MAIN`
- Allowed Actions: ouvrir History, rechercher, filtrer, consulter un detail d historique.
- Exit Conditions: retour vers Dashboard ou detail consulte.

### 2.5 Access settings

- Start Route: `IMP.DASH.MAIN`
- Target Route: `IMP.SETTINGS.CORE`
- Allowed Actions: ouvrir Settings, naviguer entre sections, modifier des preferences, consulter les sections documentees.
- Exit Conditions: retour vers Dashboard ou section de settings terminee.

### 2.6 Access weekly review

- Start Route: `IMP.DASH.MAIN`
- Target Route: `IMP.WR.SUMMARY`
- Allowed Actions: ouvrir Weekly Review, consulter le resume, voir les statistiques, lire les recommandations.
- Exit Conditions: retour vers Dashboard ou consultation terminee.

## 3. Mission Active Flows

La Mission Active reste la seule mission active autorisee.
Les actions suivantes sont documentees comme flows officiels.

### 3.1 See mission

- Start Route: `IMP.MISSION.ACTIVE`
- Target Route: `IMP.MISSION.ACTIVE`
- Allowed Actions: voir le titre, le statut, la priorite, la deadline et le contexte de la mission.
- Exit Conditions: retour vers Dashboard ou poursuite de la mission active.

### 3.2 Modify status

- Start Route: `IMP.MISSION.ACTIVE`
- Target Route: `IMP.MISSION.ACTIVE`
- Allowed Actions: marquer la mission complete, fail, replan ou annuler la modification.
- Exit Conditions: statut confirme par le flow documente ou modification abandonnee.

### 3.3 Add note

- Start Route: `IMP.MISSION.ACTIVE`
- Target Route: `IMP.MISSION.ACTIVE`
- Allowed Actions: ecrire une note, enregistrer un brouillon, enregistrer une note vocale documentee.
- Exit Conditions: note ajoutee, brouillon abandonne, ou retour vers Dashboard.

### 3.4 Return dashboard

- Start Route: `IMP.MISSION.ACTIVE`
- Target Route: `IMP.DASH.MAIN`
- Allowed Actions: utiliser back, appuyer sur retour Dashboard, quitter la surface mission.
- Exit Conditions: Dashboard visible.

## 4. Inbox Flows

Inbox collecte les entrees rapides et les conversations.
Elle ne cree jamais une mission active de facon autonome.

### 4.1 Open conversation

- Start Route: `IMP.INBOX.MAIN`
- Target Route: `IMP.INBOX.MAIN`
- Allowed Actions: ouvrir une conversation, lire le preview, changer de conversation.
- Exit Conditions: detail ferme, conversation changee, ou retour Dashboard.

### 4.2 Search

- Start Route: `IMP.INBOX.MAIN`
- Target Route: `IMP.INBOX.MAIN`
- Allowed Actions: saisir une requete, effacer la recherche, voir le resultat filtre.
- Exit Conditions: recherche videe ou retour vers Dashboard.

### 4.3 Filter

- Start Route: `IMP.INBOX.MAIN`
- Target Route: `IMP.INBOX.MAIN`
- Allowed Actions: choisir All, Voice, Notes, Missions ou Unprocessed.
- Exit Conditions: filtre reinitialise ou retour vers Dashboard.

### 4.4 Return dashboard

- Start Route: `IMP.INBOX.MAIN`
- Target Route: `IMP.DASH.MAIN`
- Allowed Actions: utiliser back ou la destination Dashboard documentee.
- Exit Conditions: Dashboard visible.

## 5. Weekly Review Flows

Weekly Review reste une consultation guidee.
La validation finale d une revue reste backend/WR workflow et ne se fait jamais localement.

### 5.1 Consult review

- Start Route: `IMP.WR.SUMMARY`
- Target Route: `IMP.WR.SUMMARY`
- Allowed Actions: lire le resume, voir la semaine active, ouvrir les blocs de synthese.
- Exit Conditions: consultation terminee ou retour Dashboard.

### 5.2 View statistics

- Start Route: `IMP.WR.SUMMARY`
- Target Route: `IMP.WR.SUMMARY`
- Allowed Actions: lire les statistiques, comparer les missions done et failed, lire le profit hebdomadaire documente.
- Exit Conditions: retour au resume ou retour Dashboard.

### 5.3 View recommendations

- Start Route: `IMP.WR.SUMMARY`
- Target Route: `IMP.WR.SUMMARY`
- Allowed Actions: lire les recommandations, ouvrir une suggestion, comprendre le rationnel.
- Exit Conditions: recommandation lue, retour au resume, ou retour Dashboard.

### 5.4 Return dashboard

- Start Route: `IMP.WR.SUMMARY`
- Target Route: `IMP.DASH.MAIN`
- Allowed Actions: utiliser back ou le retour documente vers Dashboard.
- Exit Conditions: Dashboard visible.

## 6. History Flows

History est read-only.
Elle expose la chronologie des missions, plans et evenements documentes.

### 6.1 Search

- Start Route: `IMP.HISTORY.MAIN`
- Target Route: `IMP.HISTORY.MAIN`
- Allowed Actions: saisir une requete, effacer la recherche, voir la liste filtree.
- Exit Conditions: recherche videe, resultat selectionne, ou retour Dashboard.

### 6.2 Filter

- Start Route: `IMP.HISTORY.MAIN`
- Target Route: `IMP.HISTORY.MAIN`
- Allowed Actions: choisir All, Missions, Decisions, Weekly ou Failed.
- Exit Conditions: filtre reinitialise ou retour Dashboard.

### 6.3 Consultation detail

- Start Route: `IMP.HISTORY.MAIN`
- Target Route: `IMP.HISTORY.MAIN`
- Allowed Actions: selectionner un event, lire le detail, consulter le lien documente.
- Exit Conditions: detail ferme ou retour vers la timeline.

### 6.4 Return dashboard

- Start Route: `IMP.HISTORY.MAIN`
- Target Route: `IMP.DASH.MAIN`
- Allowed Actions: utiliser back ou la destination Dashboard documentee.
- Exit Conditions: Dashboard visible.

## 7. Settings Flows

Settings expose les preferences documentees et les sections de configuration Imperium.
Settings ne doit jamais exposer de secrets ou d etat auth interne.

### 7.1 Navigation sections

- Start Route: `IMP.SETTINGS.CORE`
- Target Route: `IMP.SETTINGS.CORE`
- Allowed Actions: ouvrir User, Theme, Notifications, Integrations, Security, Advanced.
- Exit Conditions: section choisie ou retour Dashboard.

### 7.2 Modification preferences

- Start Route: `IMP.SETTINGS.CORE`
- Target Route: `IMP.SETTINGS.CORE`
- Allowed Actions: modifier le theme, basculer les notifications, lire les preferences de section.
- Exit Conditions: preference changee, preview appliquee, ou annulation.

### 7.3 Return dashboard

- Start Route: `IMP.SETTINGS.CORE`
- Target Route: `IMP.DASH.MAIN`
- Allowed Actions: utiliser back ou la destination Dashboard documentee.
- Exit Conditions: Dashboard visible.

## 8. Navigation Contract

Note: `Target Route` peut etre identique a `Start Route` quand le flow reste dans le meme ecran et change seulement l etat selectionne.

| Flow | Start Route | Target Route | Allowed Actions | Exit Conditions |
|---|---|---|---|---|
| Open app | `APP_LAUNCH` | `IMP.DASH.MAIN` | Ouvrir l app et afficher le Dashboard. | Dashboard visible et destinations documentees disponibles. |
| Consult active mission | `IMP.DASH.MAIN` | `IMP.MISSION.ACTIVE` | Voir la mission, modifier le statut, ajouter une note. | Retour Dashboard ou mission active continuee. |
| Access inbox | `IMP.DASH.MAIN` | `IMP.INBOX.MAIN` | Ouvrir Inbox, rechercher, filtrer, selectionner une conversation. | Retour Dashboard ou selection terminee. |
| Access history | `IMP.DASH.MAIN` | `IMP.HISTORY.MAIN` | Ouvrir History, rechercher, filtrer, consulter un detail. | Retour Dashboard ou detail consulte. |
| Access settings | `IMP.DASH.MAIN` | `IMP.SETTINGS.CORE` | Ouvrir Settings, naviguer entre sections, modifier des preferences. | Retour Dashboard ou section terminee. |
| Access weekly review | `IMP.DASH.MAIN` | `IMP.WR.SUMMARY` | Ouvrir Weekly Review, voir les statistiques, lire les recommandations. | Retour Dashboard ou consultation terminee. |

Related canonical routes inherited from 65 stay valid when explicitly documented there:

- `IMP.WR.READ_ONLY`
- `IMP.WR.INTERACTIVE`
- `IMP.PLAN.HISTORY`
- `IMP.SETTINGS.PRIORITIES`

## 9. Forbidden Flows

- Aucune navigation inconnue.
- Aucun ecran hors spec.
- Aucun deep link non documente.
- Aucune destination top-level non declaree dans 65.
- Aucune creation de mission active concurrente.
- Aucun detour vers un etat non documente.

## 10. Flow Validation Checklist

- ✓ depart defini
- ✓ arrivee definie
- ✓ action utilisateur definie
- ✓ retour defini
- ✓ coherent avec 65

## 11. Readiness

| Screen | Status |
|---|---|
| Dashboard | READY |
| Mission | READY |
| Inbox | READY |
| Weekly Review | READY |
| History | READY |
| Settings | READY |

**Document version :** 1.0
**Statut :** IMPERIUM USER FLOWS V1 - ready for future UI flow generation, not runtime wired.
