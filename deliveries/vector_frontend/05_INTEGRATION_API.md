# 05 — Intégration API réelle

## Contrats de référence

`contracts/openapi.json` est extrait des routeurs FastAPI sans lancer leur
lifespan ni ouvrir de session de base. Il contient Vector et l'authentification.
`endpoints.md` et `forms.md` sont générés à partir du même snapshot. L'inventaire
ne prétend pas que les migrations ou fournisseurs d'une instance sont activés.

Base API configurable, jamais une IP de production ou une clé codée en dur.
Préfixe réel Vector : `/api/imperium/vector`. Les anciens `/api/vector/*` des
annexes ne sont pas les routes de ce backend. Utiliser les DTO réseau tels quels,
avec adaptateurs vers les modèles de vue, sans transformer le contrat public.

## Authentification

`POST /api/auth/login` : `device_label` obligatoire ; soit email+password, soit
master_key, exclusivement. Le frontend personnel privilégie les identifiants
configurés, ne préremplit jamais de master key. Réponse : access/refresh token,
device_id, type bearer et expires_in_seconds. Ces valeurs ne sont jamais rendues
comme du contenu métier, ni loguées. Android Keystore/stockage protégé pour les
secrets. Ne pas ajouter un proxy public stockant le mot de passe.

Appels protégés : `Authorization: Bearer <access_token>`.
Refresh : `POST /api/auth/refresh` avec refresh_token et device_id ; stocker le
nouveau couple retourné et sérialiser les refresh concurrents. Logout : même
couple sur `/api/auth/logout`. 401 après refresh : reconnexion ; préserver les
brouillons sans réutiliser des tokens invalides. Les routes de gestion d'appareil
sont exportées comme support, pas une obligation de créer un écran d'administration.

## Matrice des opérations Vector

Tous les chemins ci-dessous sont relatifs à `/api/imperium/vector`.

| Opération | Méthode / chemin | Particularité |
|---|---|---|
| Session courante | GET /sessions/current | `{session: null}` si aucune |
| Historique | GET /sessions | from_day/to_day, dates Paris, défaut 30 jours |
| Démarrage | POST /sessions | SessionStart + Idempotency-Key obligatoire |
| Détail | GET /sessions/{session_id} | Inclut les KPIs, utilisé pour le bilan |
| Mise à jour | PATCH /sessions/{session_id} | SessionUpdate, version + Idempotency-Key |
| Gain | POST /sessions/{session_id}/manual-revenue | ManualRevenueCreate + Idempotency-Key |
| Dépense | POST /sessions/{session_id}/manual-expense | ManualExpenseCreate + Idempotency-Key |
| Déposes | GET /sessions/{session_id}/drop-zones | Liste de DropZoneRead |
| Dépose | POST /sessions/{session_id}/drop-zone | DropZoneCreate + Idempotency-Key |
| Clôture | POST /sessions/{session_id}/complete | SessionComplete + Idempotency-Key |
| Replan Imperium | POST /sessions/{session_id}/replan | Après clôture ; pas de body métier |
| Où aller | POST /recommendations | RecommendationRequest + Idempotency-Key |
| Dernier conseil | GET /recommendations/latest | Peut renvoyer null |
| Détail conseil | GET /recommendations/{recommendation_id} | RecommendationRead |
| Retour | POST /recommendations/{recommendation_id}/feedback | RecommendationFeedback, un retour |
| Offres | GET /sessions/{session_id}/offers | RideOfferListResponse |
| Saisie offre | POST /sessions/{session_id}/offers | RideOfferCreate + Idempotency-Key |
| Détail offre | GET /offers/{offer_id} | RideOfferRead |
| Décision passée | POST /offers/{offer_id}/decision | RideDecisionRequest avec version |
| Résultat réel | POST /offers/{offer_id}/outcome | RideOutcomeRequest avec version |
| Collecte | GET /training-summary | Compteurs et message, pas preuve d'entraînement |
| Règles | GET /rules | items + not_coded |
| Édition règle | PATCH /rules/{rule_code} | BusinessRuleUpdate, version et reason |

## Données, unités et validation

Montants `*_cents` : entiers, euros affichés avec virgule française. Ne pas
utiliser la multiplication naïve d'un float utilisateur pour une écriture.
Distances en km, durées en minutes, consommation future en L/100 km. Les décimaux
Pydantic peuvent être sérialisés en chaînes : générer des adaptateurs robustes.
Datetimes ISO 8601 avec fuseau ; affichage Europe/Paris, y compris changement
d'heure et sessions traversant minuit. UUID opaques, jamais des indices d'écran.

`net_cents` décrit CA moins dépenses enregistrées de la session, pas le bénéfice
hebdomadaire officiel ni une estimation fiscale. Les sommes du backend sont
canoniques. `target_progress` peut dépasser 1 : afficher le vrai pourcentage et
borner seulement la barre graphique. `objective_reached=null` signifie sans cible.

Formulaires exacts et plafonds dans `forms.md`. Ne pas envoyer de champs bonus :
les schémas d'écriture Vector interdisent les extras. Le sélecteur de décision
d'offre accepte trois valeurs ; `ignored` est réservé au retour de recommandation.

## Idempotence, concurrence et double comptage

Une action utilisateur crée une clé stable unique, conservée avec son body et
sa cible. Timeout ou retry : même clé, mêmes valeurs. Si l'utilisateur modifie le
brouillon avant tout envoi, une nouvelle action peut être préparée. Après une
réponse ambiguë, vérifier l'état serveur avant de considérer la requête annulée.

OpenAPI décrit certains headers comme facultatifs, mais `_require_key` renvoie
400 s'ils sont absents sur les routes concernées. Les doublons peuvent renvoyer
200 au lieu de 201. Les mutations à `version` utilisent la version lue ; le
frontend ne devine pas la prochaine version après un conflit.

`outcome.record_revenue=true` enregistre aussi le revenu au Vault. Ne pas créer
ensuite un gain manuel pour cette même course. Si un gain a déjà été enregistré,
le choix `record_revenue=false` doit être explicite ; le contrat n'associe pas
magiquement cette ancienne transaction. Toute correction comptable passe par
Vault, sans suppression de l'historique.

## Erreurs et comportement visible

| Réponse/code | Réaction frontend |
|---|---|
| 400 clé manquante | Erreur d'intégration ; conserver brouillon et corriger l'adaptateur |
| 401 | Refresh une fois puis reconnexion si nécessaire |
| 403 | Accès refusé ; ne pas tenter de contournement |
| 404 | Ressource absente, retour à la liste et refresh |
| 422 | Erreurs de champs lisibles, brouillon conservé |
| 409 RIDES_SESSION_STATE | Session déjà active/close ; afficher `current` quand présent |
| 409 RIDES_SESSION_VERSION_CONFLICT | Recharger session et comparer les changements |
| 409 RIDES_OFFER_VERSION_CONFLICT | Recharger offre ; ne pas rejouer une décision devenue invalide |
| 409 RIDES_RULE_VERSION_CONFLICT | Conditions locales et serveur visibles, nouvelle validation |
| 409 RIDES_FEEDBACK_CONFLICT | Retour déjà enregistré ; afficher le retour serveur |
| 409 sans code spécialisé | Afficher conflit générique, garder saisie, pas de retry infini |
| DAY_NOT_STARTED / REPLAN_COOLDOWN / REPLAN_ALREADY_OPEN | Replan refusé/différé ; session déjà close reste close |
| 429 | Respecter le délai fourni, limiter les retries |
| 5xx / timeout | Message bref, reprise contrôlée, aucune fausse réussite |

Certaines erreurs métier sont construites en JSONResponse et ne figurent pas
dans toutes les réponses OpenAPI. Ne pas afficher de stack trace ou de détails
internes sensibles. Les textes anglais peuvent être traduits par code stable.

## Contrats absents

Pas de route dédiée Vector pour upload capture, OCR temps réel, STT métier,
flux opérationnels, quota destination, GPS continu, import historique, Smart Fuel,
ou HUD. Ne pas détourner Knowledge Inbox en pipeline Vector implicite.
Un formulaire réservé reste explicitement non raccordé. Aucun appel direct n8n,
SQL, fournisseur IA, Bolt ou service interne depuis le frontend.
