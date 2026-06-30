
# PHASE 0 — Décisions de verrouillage architectural
Date : 2026-06-30. Statut : décisions ACTÉES, à appliquer en phase d'exécution.

## Principe fondateur (transverse à toutes les décisions)
Les applications (Vault, Pulse, Path, Vector, Imperium-app) sont des FAÇADES
d'affichage. Le CERVEAU = le backend possède TOUS les métiers et TOUTES les
tables/events. Les noms (tables, events, modèles) reflètent le DOMAINE DE DONNÉES,
jamais l'app. Ce principe tranche D1, D2/D3, et la convention de nommage.

## D1 — Propriétaire du schéma
Le doc 05 (DATABASE_SCHEMA) est réécrit en DICTIONNAIRE DE SCHÉMA CENTRAL UNIQUE :
il possède la définition de TOUTES les tables (colonne par colonne, types, règles).
Les docs métier (52, 04, 41...) décrivent la LOGIQUE et renvoient au 05 pour les
tables. Les docs front décrivent l'affichage, aucune table. Bénéfice : garde-fou
anti-doublon, force le bon modèle mental aux IA.

## D2 — Journal d'events unique
Canonique : `events` (enveloppe complète, dotted, reçoit déjà le vrai métier,
append-only solide). Déprécié : `imperium_events` (vide, snake_case, enveloppe
réduite). Action : corriger doc 04 (qui pointe à tort vers imperium_events),
débrancher imperium_events.

## D3 — Format des event_type
Format DOTTED : `domaine.sujet.action` (max 3 niveaux ; détails dans le payload).
Noms de domaines GÉNÉRIQUES en anglais, JAMAIS de noms d'apps (finance pas vault,
health pas pulse, worship pas path, rides/driving pas vector, + vehicle, planning...).
Principe d'enregistrement : GÉNÉREUX sur les faits métier significatifs (richesse
analytique future, même sans consumer immédiat), mais PAS le bruit pur.
Structure d'un event : event_type + occurred_at (date/h) + payload (détails)
+ correlation_id (même "histoire") + causation_id (lien de cause).
Domaines transverses (ex: vehicle, regardé par finance+rides+planning) : à identifier.
Tâche découlant : bâtir le catalogue d'events (doc 77).

## D4 — Daily plan = living plan versionné
Vision = un cerveau qui GÉNÈRE la journée (assistant de direction qui n'oublie pas).
Trajet : IA locale produit du JSON → backend range en TABLES (persistant) → Imperium
LIT les tables → events signalent. JSON = transport, Tables = stockage, Events =
signalisation. On VERSIONNE, on n'écrase PAS : table `planning_daily_plan_versions`,
chaque replan = nouvelle version + raison, l'ancienne archivée (nourrit l'apprentissage
et la future autonomie LoRA). Plomberie déterministe codable maintenant ; générateur
intelligent (étape 1) attend le modèle local/GPU.

## D5 — Stratégie mémoire transitoire
BLOQUER les commits mémoire du WR jusqu'à correction de `ai_memories` au schéma
canonique (doc 75/09). Justif : pas en prod, pas de front, WR jamais utilisé → rien
à perdre, zéro dette créée. Ordre verrouillé : (1) bloquer, (2) corriger ai_memories,
(3) rebrancher le commit WR, (4) durcir les fallback candidates.

## D6 — Alias de modèles
Le code/les contrats utilisent des ALIAS DE RÔLES stables (local_router/conductor,
high_reasoning, les spécialistes...), jamais les noms de produits en dur. La
bibliothèque de modèles = doc 30 §3 (déjà la source unique role→modèle→version ;
doc 03 = DEPRECATED). 7B ÉCARTÉ DÉFINITIVEMENT (insuffisant même pour scorer) : le
rôle local cible le 32B/V100, non opérationnel tant que pas de GPU (pas de modèle de
façade). Docs technique nettoyées (rôles), EXEMPLES gardés (noms concrets, sinon
incompréhensibles), CODE nettoyé en dernier (après le socle). Ajouter à la
bibliothèque le rôle "modification-système / orchestrateur".

## NOTES D'ARCHITECTURE (gravées)
1. Évolution de schéma : AJOUTER du contenu (lignes) par chatbot/voix = OK sans risque.
   CHANGER la structure (tables/colonnes/events) → l'IA PROPOSE (consulte doc 05,
   anti-doublon), l'utilisateur VALIDE, appliqué tracé via Git. Jamais l'IA ne crée
   une structure dans son coin.
2. Le spécialiste "modification-système/coding" = un PIPELINE, pas une IA qui code :
   demande → détection (routeur, règle dure) → orchestrateur reformule + validation
   conversationnelle → conception (doc 05) → code → BATTERIE DE TESTS = LE VERROU
   (rien d'appliqué sans tests verts) → si KO, retour utilisateur avec journal d'erreurs.
   Sécurité = les TESTS, pas la confiance en l'IA. À activer APRÈS le socle (dépend du doc 05).
3. Chantier futur (post-socle, post-V100) : calibration profondeur de corrélation vs coût.
   Mémoire = couches de résumé (récent=fin, ancien=grossier) + RAG ciblé. Stockage =
   aucun problème (PostgreSQL). Vraie limite = nombre d'appels IA (coût). Piste : repérage
   large en LOCAL gratuit (V100) → croisement final UNIQUE sur Opus. À chiffrer par
   simulation papier.

## TRI 1 — Doublons de tables tranchés
1. Ledger finance : CANONIQUE = `imperium_vault_transactions` (→ renommé finance_transactions ;
   cents, append-only, reversals). Déprécié = `vault_transactions`. Migrer les lecteurs
   restants (dashboard.py, weekly_report.py), supprimer le legacy, déprécier doc 27.
2. Events : CANONIQUE = `events`. Déprécié = `imperium_events` (cf. D2).
3. Path : CANONIQUE = `imperium_path_habits` + `imperium_path_check_ins` (→ worship_*).
   Déprécié = `imperium_path_items` (legacy) : débrancher les 3 lecteurs
   (dashboard/daily_plans/weekly_report), puis supprimer.
4. Daily plan : PAS un simple doublon. `daily_plan.py` (snapshot read-only) reste une
   VUE de lecture ; `imperium_daily_plans` (persistant) devient la base du living plan
   versionné (cf. D4, ajouter planning_daily_plan_versions). Chantier D4 dédié.
5. Priorités : CANONIQUE = `imperium_user_priorities` (→ decision_user_priorities ;
   déjà source active du Decision Framework). Déprécié = `imperium_priority_rules`
   (legacy lecture) : migrer le dernier lecteur (weekly_report), supprimer.
6. WR states vs sessions : `imperium_weekly_review_sessions` = la vraie machine WR.
   `imperium_weekly_review_states` (readiness/bannière) → À CLARIFIER au moment de
   coder le WR (vérifier ce que states porte d'utile que sessions n'a pas).

## CONVENTION DE NOMMAGE DES TABLES (entre dans le doc 05)
Règle : préfixe = DOMAINE DE DONNÉES en anglais, JAMAIS le nom d'app. TOUJOURS un
préfixe (sauf socle technique nu). Anglais en base/API, français en libellé UI seulement.
Principe : préfixer = se réserver l'espace pour faire grandir un domaine par AJOUT de
table, pas par renommage (éviter la dette future). Finesse maximale tant que ça reste
lisible (séparer planning et decision plutôt que tout fourrer ensemble).

Carte des domaines :
- SOCLE / TECHNIQUE (nu, pas de préfixe — universel, stable) :
  users, devices, refresh_tokens, auth_events, idempotency_keys, events,
  ai_tasks, ai_results, ai_result_validations, ai_memories
- FINANCE (ex-vault) : finance_transactions
- HEALTH (ex-pulse) : health_entries
- WORSHIP (ex-path) : worship_habits, worship_check_ins (+ futur worship_places, etc.)
- PLANNING (exécution) : planning_missions, planning_daily_plans, planning_day_reviews
  (+ futur planning_daily_plan_versions, planning_replan_events...)
- DECISION (arbitrage/scoring) : decision_user_priorities, decision_mission_scores
- REVIEW (weekly review) : review_sessions, review_messages, review_final_reports,
  review_states (à clarifier), review_memory_decisions
- CALENDAR : calendar_events
- RIDES (ex-vector, futur) : rides_*
- VEHICLE (futur) : vehicle_*

Application : la convention est ACTÉE maintenant, APPLIQUÉE au fil de l'eau (domaine
par domaine, dans le même geste que la correction du domaine + ses tests), PAS en un
grand renommage risqué d'un coup

## DÉCISIONS MÉMOIRE (ai_memories — hub central, priorité n°1)
Date : 2026-06-30. Suite à relecture des docs 75 (conception) et 09 (politique).

### Propriété (application de D1)
- SCHÉMA de ai_memories → DOC 05 (dictionnaire central).
- POLITIQUE d'usage (write/retrieval/privacy/correction/deletion/cascade/exemples)
  → reste DOC 09.
- CONCEPTION (3 étages, le pourquoi, confidence sans decay) → reste DOC 75.
- Les docs 09 et 75 renvoient au 05 pour le schéma.

### Deux axes conservés (version doc 09 ; le doc 75 avait fusionné à tort)
- memory_type = le DOMAINE (de quoi parle le souvenir) — enum semi-stable.
- learning_element_type = la NATURE (insight/decision/pattern/win/blocker) — axe OUVERT.
- Règle de sûreté : le type est purement DESCRIPTIF, aucune logique ne branche sur une
  valeur de type. Tous les éléments sont vectorisés/cherchés/privacy-gatés identiquement.
- ACTION : corriger le §3 du doc 75 (qui fusionnait element_type dans memory_type).

### Renommage source_app → source_domain (application D3 + convention nommage)
- Valeurs = domaines génériques (finance, worship, health, rides, planning...),
  JAMAIS de noms d'apps (vault/path/vector/imperium).
- À vérifier au moment d'écrire : aligner l'enum memory_type du doc 09
  (vtc_zone_pattern, financial_pattern...) sur la convention de nommage.

### Cible technique (rappel, va dans le doc 05)
- embedding vector(1024) + embedding_model ; confidence (preuve, PAS de decay) ;
  privacy_level obligatoire ; is_active + supersedes_memory_id + correction_reason ;
  expires_at ; source_table/source_id (pointeurs) ; index HNSW cosine + index composites.

### Principes de conception verrouillés (issus du 75, validés)
- 3 étages : data brute (tables) → on ne vectorise QUE les éléments d'apprentissage.
- Pas de decay temporel ; confidence monte avec la preuve, ne descend jamais seule.
- Patterns contradictoires COEXISTENT (le plus prouvé domine, l'ancien survit en trace).
- Confidence TRIE, n'EXCLUT jamais (seuls supersession + privacy gate excluent).
- privacy_level sur chaque ligne, non négociable.
