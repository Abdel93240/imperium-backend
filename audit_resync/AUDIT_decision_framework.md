# AUDIT decision_framework — Decision Framework / scoring déterministe

Date: 2026-06-28  
Périmètre: lecture du code uniquement, puis rédaction de ce rapport. Aucun code runtime modifié.

Fichiers lus:

- `docs_master/52_AI_DECISION_FRAMEWORK.md`
- `backend/alembic/versions/20260504_0019_decision_framework_foundation.py`
- `backend/app/services/imperium/decision_framework.py`
- `backend/app/models/imperium.py`
- surfaces publiques liées: `backend/app/schemas/imperium.py`, `backend/app/api/v1/routes/imperium.py`, `backend/app/services/imperium/missions.py`

## Conclusion

Verdict: **(b) léger décalage**.

Le coeur du "cerveau déterministe" est réellement codé pour ce périmètre: hiérarchie utilisateur canonique, coefficients internes, scoring intrinsèque A-E, score pondéré, bucket public, explication détaillée, sans appel IA/n8n/pgvector.

Nuance importante: ce n'est pas encore tout le cerveau doc 52. Le module ne fait pas la catégorisation IA silencieuse, ne fait pas de génération de plan mensuel/journalier, et ne branche pas le routage intelligent doc 30. Il implémente fidèlement la **fondation déterministe du scoring**, pas la couche d'intelligence complète.

## Partie 1 — Table `imperium_user_priorities`

Source code:

- migration `20260504_0019_decision_framework_foundation.py`
- ORM `ImperiumUserPriority`
- service `get_canonical_priority_order`

| Colonne / contrainte | Code réel | Doc 52 attendu | Écart |
|---|---|---|---|
| `id` | UUID PK, `gen_random_uuid()` en migration, mixin ORM | Non détaillé colonne par colonne | OK technique |
| `user_id` | UUID FK vers `users.id`, non nullable | "Every user defines their own life priorities" | OK |
| `domain` | `Text`, contrainte `religious/business/finance/health` | §3: Religieux, Business, Finances, Santé ; Patch 7G: table canonique | Fonctionnellement OK, mais vocabulaire anglais vs libellés FR à trancher transversalement |
| `position` | `Integer`, check `1 <= position <= 4` | §3 positions 1-4, drag-to-reorder | OK |
| `coefficient` | `Integer`, check couplé à position: 1→10, 2→8, 3→5, 4→4 | §3.2 coefficients invisibles ×10/×8/×5/×4 | OK |
| `is_active` | `Boolean`, default/server_default `true`, non nullable | Patch 7G: source canonique active | OK |
| `created_at` / `updated_at` | timestamps timezone, default `now()` | Non détaillé | OK technique |
| unicité active domaine | index unique partiel `(user_id, domain) WHERE is_active = true` | Un seul ordre actif cohérent par utilisateur | OK |
| unicité active position | index unique partiel `(user_id, position) WHERE is_active = true` | Une seule position 1-4 active par utilisateur | OK |
| index lecture | `(user_id, is_active, position)` | Lecture canonique ordonnée | OK |

Réponse publique priorités: `DecisionFrameworkPriorityRead` expose `id`, `domain`, `position`, `is_active`, timestamps. Elle **n'expose pas `coefficient`**, conforme à §3.2 ("invisible").

Écart mineur: le doc visible parle en français (`Religieux`, `Finances`, `Santé`) alors que le stockage/API canonique utilise l'anglais (`religious`, `finance`, `health`). Le service accepte des alias FR (`religieux`, `santé`, etc.), mais la valeur stockée et renvoyée reste anglaise.

## Partie 2 — Scoring déterministe

### Critères A-E

| Critère | Doc 52 §4 | Code `decision_framework.py` | Fidélité |
|---|---|---|---|
| A deadline | none=0, >30=5, 15-30=10, 7-14=15, 3-6=20, 1-2=25, today/past=30 + urgency flag | `_deadline_points`: `None`=0+missing, `<=0`=30 avec `deadline_past` si passé, `<=2`=25, `<=6`=20, `<=14`=15, `<=30`=10, sinon 5 | Conforme |
| B gravité | 0/5/10/15/20/25/30 | `_IMPACT_POINTS` mappe `cosmetic`, `quality_of_life`, `mid/paperwork`, `important`, `critical`, `vital_short_term`, `vital_immediate` | Conforme |
| C type CAT A-I | A=20, B=18, C=15, D=12, E=10, F=8, G=5, H=3, I=0 | `_MISSION_TYPE_POINTS` mappe `cat_a` à `cat_i` + synonymes | Conforme |
| D dépendance | none=0, 1-2=5, multiple=10 | `_DEPENDENCY_POINTS`, bool `true`=5, `blocked_mission_count <=2`=5, `>2`=10 | Conforme |
| E récurrence | daily=0, weekly=3, monthly=5, yearly=7, exceptional=10 | `_RECURRENCE_POINTS` exactement ces seuils + alias FR/EN | Conforme |

Compatibilité/dette: le service accepte aussi des entiers déjà scorés et des champs legacy (`impact_points`, `effort_points`, `alignment_points`, etc.) en les bornant. C'est déterministe et testé, mais plus permissif que le vocabulaire strict du doc 52.

### Score final et coefficients

- `COEFFICIENT_BY_POSITION = {1: 10, 2: 8, 3: 5, 4: 4}`: conforme §3.2.
- `compute_weighted_score(intrinsic_score, domain_coefficient)` retourne `clamp(intrinsic, 0, 100) * domain_coefficient`: conforme §5.
- `_priority_for_domain` récupère position/coefficient depuis les priorités actives si fournies, sinon fallback ordre V1 `religious/business/finance/health`.
- Le stockage mission (`build_mission_score_from_start_request`) conserve bien `intrinsic_score`, `domain_coefficient`, `weighted_score`, `explanation`, `source`.

Lien `imperium_mission_scores`: cohérent avec l'audit missions. Le scoring écrit les champs internes nécessaires, mais les surfaces mission publiques compactes ne les exposent pas.

### `explanation` et détail A-E

Oui: `explanation` contient le détail utile.

`DecisionFrameworkScoreExplanation` contient:

- `deadline_points`
- `impact_points`
- `mission_type_points`
- `dependency_points`
- `recurrence_points`
- `missing_fields`
- `final_intrinsic_score`
- `flags`

`_build_breakdown` ajoute une vue lisible en 5 items avec `label`, `key`, `points`, `max_points`, `reason`.

Réponse à la question de l'audit missions: le résumé mission public peut rester compact parce que le détail A-E existe bien dans `explanation` au moment du calcul/stockage. En revanche, les routes publiques mission `decision-preview` / `decision-score` ne renvoient volontairement que `label` + `reason_codes` / `priority_bucket` compact, conformément §5.3.

### Bucket public

`_priority_bucket(weighted_score)` implémente les seuils doc 52 §6.1:

- `>=700` → 10
- `600-699` → 9
- `500-599` → 8
- `400-499` → 7
- `300-399` → 6
- `200-299` → 5
- `100-199` → 4
- `50-99` → 3
- `20-49` → 2
- `0-19` → 1

Le bucket est donc dérivé du score pondéré, mais le score pondéré lui-même n'est pas exposé dans les surfaces mission publiques.

### Exposition publique §5.3

Conforme pour les routes mission:

- `/missions/backlog/decision-preview`
- `/missions/{mission_id}/decision-score`

Elles exposent une synthèse publique (`label`, `reason_codes`, `priority_bucket`, `safe_explanation`) et n'exposent pas `weighted_score` ni `domain_coefficient`. Des tests existent explicitement pour cette frontière.

Nuance: `/decision-framework/score-preview` expose `intrinsic_score`, `domain_position`, `explanation` et `breakdown`. Cette route ressemble à un endpoint de debug/fondation Decision Framework, pas à la surface mission publique décrite par §5.3. Si elle est destinée à être une UI utilisateur finale, il faudra décider si ce niveau de détail reste acceptable. Elle ne divulgue pas `weighted_score` ni `domain_coefficient`.

### Déterminisme

Confirmé.

Dans `decision_framework.py`, aucun import/appel à Qwen, OpenAI, Claude, Gemini, provider IA, n8n, pgvector, embeddings, OCR ou client HTTP. Le schema endpoint annonce explicitement:

- `real_ai_enabled=False`
- `embeddings_enabled=False`
- `monthly_planning_enabled=False`
- `daily_adaptation_enabled=False`

Les tests `test_decision_framework.py` et `test_repo_invariants.py` verrouillent aussi cette absence d'IA/n8n/embedding et l'absence d'exposition des coefficients.

## Partie 3 — Cohérence orchestration §3A / Patch 7G

`get_canonical_priority_order` lit bien `imperium_user_priorities` via `_get_active_user_priorities`, ordonne par `position`, et retourne un ordre V1 transient si aucune ligne active n'existe.

Points importants:

- Pas de `db.add`, `db.flush`, `db.commit` dans la lecture canonique.
- `get_user_priority_context` délègue à `get_canonical_priority_order`.
- Dashboard et daily plans utilisent `get_canonical_priority_order`.
- La route legacy `GET /api/imperium/priorities` est une projection depuis `imperium_user_priorities`.
- La route legacy `POST /api/imperium/priorities` est désactivée (`410 Gone`).

Donc §3A est cohérent: l'ordre multi-domaines peut s'appuyer sur `imperium_user_priorities` comme source canonique. Je n'ai pas trouvé de lecture canonique restante vers `imperium_priority_rules`.

Nuance: le modèle/table/service legacy `imperium_priority_rules` existent encore pour compatibilité historique. Ce n'est pas un problème si aucune route ou orchestration canonique ne les utilise, mais c'est un reste à supprimer plus tard si les tables sont vides et si l'objectif est de débrancher tout legacy.

## Partie 4 — Restes périmés / domaines

Restes legacy:

- `ImperiumPriorityRule` existe encore dans l'ORM.
- `backend/app/services/imperium/priorities.py` existe encore.
- migrations et docs anciennes mentionnent encore `imperium_priority_rules`.

État actuel: compatible avec Patch 7G, car les écritures legacy sont bloquées et les lectures publiques legacy sont projetées depuis la source canonique.

Décision transverse domaines:

- Code canonique: `religious/business/finance/health`.
- Doc visible: `Religieux/Business/Finances/Santé`.
- Service: accepte les alias FR, stocke anglais.

Recommandation: acter officiellement **anglais en base/API, français en libellés UI**. Cela évite de renommer les tables/contraintes tout en respectant l'expérience utilisateur.

## Actions recommandées

1. Classer ce module comme **fondation déterministe saine**. Pas de correction urgente du scoring.
2. Clarifier dans doc 52 ou doc 05 que les valeurs stockées/API de domaine sont anglaises, avec libellés FR côté UI.
3. Clarifier le statut de `/decision-framework/score-preview`: endpoint debug/fondation détaillé ou endpoint public utilisateur. Si public final, réduire la surface pour suivre strictement §5.3.
4. Garder `imperium_priority_rules` en compatibilité-only jusqu'à la passe de suppression legacy, puis le supprimer si les tables sont réellement vides.
5. Ne pas recoder le scoring: les barèmes A-E, coefficients, bucket et explication sont déjà présents et testés.

## Verdict final

**(b) léger décalage**: le scoring déterministe et la source canonique des priorités sont fidèles au doc 52. Les écarts restants sont surtout de vocabulaire, de documentation de surface API, et de dette legacy non canonique.
