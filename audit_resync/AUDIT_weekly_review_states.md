# AUDIT weekly_review - WR-b ETATS

Date : 2026-06-27

Perimetre lu :

- `backend/app/services/imperium/weekly_review_state.py`
- `docs_master/32_WR_INTERACTIVE_WORKFLOW.md`
- points d'appel minimum : `backend/app/api/v1/routes/internal.py`, `backend/app/api/v1/routes/imperium.py`
- modele utile pour unicite : `backend/app/models/imperium.py`

## Resume

`weekly_review_state.py` ne code pas la machine a etats interactive de `imperium_weekly_review_sessions`.

Il code une couche readiness/banner separee, basee sur `imperium_weekly_review_states` :

- booleen `ready`;
- booleen `launched`;
- champ legacy `analysis_status`;
- idempotence pour `ready` et `launched`;
- affichage dashboard via `show_banner = ready and not launched`.

La machine officielle du doc 32 vit sur `imperium_weekly_review_sessions.status`. Le fichier audite n'en manipule aucun statut.

## Transitions codees dans `weekly_review_state.py`

| Transition codee | Condition | Effet | Reference code | Correspondance doc 32 |
|---|---|---|---|---|
| aucune ligne -> state row non ready | `get_or_create_weekly_review_state`, `week_start` lundi, aucune ligne existante | cree `ready=False`, `launched=False`, `analysis_status="pending"` | `weekly_review_state.py:38-58` | Non decrit comme etat de conversation. C'est un etat technique pre-ready hors machine doc 32. |
| `ready=False` -> `ready=True` | `mark_weekly_review_ready`, idempotency absente, ligne non ready | pose `ready=True`, `ready_at=now()` | `weekly_review_state.py:61-96` | Correspond partiellement au `ready` documentaire, mais dans une table differente et sans `imperium_weekly_review_sessions.status = ready`. |
| `ready=True` -> pas de changement | `mark_weekly_review_ready` sur state deja ready | retourne duplicate logique, sans enregistrer de nouvelle idempotency si pas de cle existante | `weekly_review_state.py:76-78` | Pas documente. Comportement idempotent acceptable, mais hors machine de session. |
| `ready=True`, `launched=False` -> `launched=True` + `analysis_status="running"` | `launch_weekly_review`, idempotency absente, state ready, state non launched | pose `launched=True`, `launched_at=now()`, `analysis_status="running"` | `weekly_review_state.py:99-143` | Ne correspond pas au workflow actuel : la route publique utilise `weekly_review_conversation.launch_weekly_review_session`, qui passe plutot `ready` -> `preparing_initial_summary`. |
| tentative launch depuis non ready -> rejet | `launch_weekly_review` avec `ready=False` | leve `WeeklyReviewNotReadyError` | `weekly_review_state.py:114-116` | Compatible avec l'idee "ne pas lancer avant ready", mais la doc ne decrit pas cette table/exception. |
| tentative launch deja lance -> rejet | `launch_weekly_review` avec `launched=True` | leve `WeeklyReviewAlreadyLaunchedError` | `weekly_review_state.py:117-118` | Doublon legacy de la protection session. La doc attend plutot une session unique par user/semaine et des statuts fermes. |
| lecture banner -> pas de transition | semaine courante Europe/Paris, state existant | `show_banner=True` si `ready and not launched` | `weekly_review_state.py:146-158` | Correspond au besoin UI "banner active", mais ne respecte pas a lui seul le timing mardi 20h. |

## Transitions documentees dans doc 32

Flux officiel attendu :

```text
ready -> launched -> preparing_initial_summary -> initial_summary_ready -> waiting_for_user_answer -> conversation_active -> integrating_answers -> draft_ready -> revision_requested -> final_ready -> approved -> stored
```

Avec branches terminales :

```text
cancelled
failed
```

Statuts documentes par doc 32 :

| Statut doc 32 | Code dans `weekly_review_state.py` ? | Observation |
|---|---:|---|
| `ready` | Partiel | `ready` est un booleen dans `imperium_weekly_review_states`, pas `session.status`. |
| `launched` | Partiel/legacy | `launched` est un booleen. La machine actuelle de session saute pratiquement vers `preparing_initial_summary`. |
| `preparing_initial_summary` | Non | Absent du fichier. |
| `initial_summary_ready` | Non | Absent du fichier. |
| `waiting_for_user_answer` | Non | Absent du fichier. |
| `conversation_active` | Non | Absent du fichier. |
| `integrating_answers` | Non | Absent du fichier. |
| `draft_ready` | Non | Absent du fichier. |
| `revision_requested` | Non | Absent du fichier. |
| `final_ready` | Non | Absent du fichier. |
| `approved` | Non | Absent du fichier. |
| `stored` | Non | Absent du fichier. |
| `cancelled` | Non | Absent du fichier. |
| `failed` | Non | Absent du fichier. |

## Ecarts code <-> doc

### 1. Mauvais objet d'etat

Doc 32 definit la machine sur les sessions WR interactives, c'est-a-dire `imperium_weekly_review_sessions.status`.

`weekly_review_state.py` manipule `ImperiumWeeklyReviewState`, donc `imperium_weekly_review_states`, avec trois champs seulement :

- `ready`;
- `launched`;
- `analysis_status`.

Conclusion : ce fichier ne peut pas etre considere comme la machine a etats WR documentee.

### 2. Transitions documentees non codees dans ce fichier

Presque toutes les transitions interactives sont absentes :

- `launched` -> `preparing_initial_summary`;
- `preparing_initial_summary` -> `initial_summary_ready`;
- `preparing_initial_summary` -> `waiting_for_user_answer`;
- `initial_summary_ready` / `waiting_for_user_answer` -> `conversation_active`;
- `conversation_active` -> `integrating_answers`;
- `integrating_answers` -> `draft_ready`;
- `draft_ready` -> `revision_requested`;
- `revision_requested` -> `conversation_active`;
- `draft_ready` / `final_ready` -> `approved`;
- `approved` -> `stored`;
- toute transition vers `cancelled` ou `failed`.

Ces transitions existent en grande partie dans `weekly_review_conversation.py`, qui sera le bon fichier a auditer en WR-c. Elles ne sont pas dans `weekly_review_state.py`.

### 3. Transitions codees mais non decrites par doc 32

Le couple de booleens `ready/launched` et le champ `analysis_status` produisent un mini-workflow non documente :

```text
pending row -> ready=True -> launched=True + analysis_status=running
```

Ce workflow est separe de la machine `imperium_weekly_review_sessions.status`. Il est donc un reste de couche banner/readiness ou une dette legacy, pas le workflow interactif officiel.

### 4. Route publique de launch ne passe plus par ce fichier

La route publique :

```text
POST /api/imperium/weekly-review/launch
```

appelle `launch_weekly_review_session` dans `weekly_review_conversation.py`, pas `weekly_review_state.launch_weekly_review`.

`weekly_review_state.launch_weekly_review` n'est reference que par le test d'idempotence legacy. Il semble donc deconnecte du launch WR canonique.

## Timing mardi 20h Europe/Paris

Doc 32 exige :

```text
Every Tuesday at 20:00 Europe/Paris, the WR banner in the UI changes from passive to active.
```

Constat code :

- `_current_week_start()` calcule seulement le lundi de la semaine courante en timezone Europe/Paris ;
- `get_weekly_review_banner()` lit la ligne de cette semaine et affiche le banner si `ready and not launched`;
- `mark_weekly_review_ready()` accepte n'importe quel `week_start` valide lundi et ne verifie ni mardi, ni 20h, ni timezone au moment de la mutation ;
- l'endpoint interne `/api/internal/weekly-review/ready` depend d'un appel externe HMAC, probablement scheduler, mais le garde-fou temporel n'est pas dans ce service.

Verdict timing : non garanti par le code audite. Le timing peut etre respecte uniquement si le scheduler externe appelle l'endpoint exactement mardi 20h Europe/Paris. Le backend ne l'impose pas.

## Garde-fou une session par user/semaine

Constat :

- `imperium_weekly_review_states` a bien une contrainte unique `(user_id, week_start)`;
- `weekly_review_state.py` fait un get-or-create sur `(user_id, week_start)`;
- `imperium_weekly_review_sessions` a aussi une contrainte unique `(user_id, week_start)` dans le modele ;
- la route publique de launch utilise la couche session, pas cette couche state.

Verdict unicite : oui au niveau schema pour state et sessions. Dans ce fichier, le garde-fou concerne seulement la readiness row, pas la session interactive elle-meme.

## Restes perimes / nomenclature

| Element | Constat | Risque |
|---|---|---|
| `analysis_status` | Present dans creation, launch, responses et banner. Valeurs codees : `pending`, `running`. | Vestige deja repere en WR-a. Ne correspond pas a la machine doc 32 et peut creer une deuxieme lecture de l'etat WR. |
| `analysis_completed_at` | Existe dans le modele, pas pilote par ce fichier. | Champ mort ou incomplet. |
| noms de modeles concrets | Aucun `qwen`, `opus`, `gpt`, `claude` dans `weekly_review_state.py`. | Pas d'ecart dans ce fichier. |
| vocabulaire `Weekly report` | Messages d'erreur disent "Weekly review", doc historique contient encore "weekly report" pour certains endpoints. | Mineur ici. La grande dette est surtout la coexistence state/readiness vs session/status. |

## Conclusion

Verdict WR-b sur `weekly_review_state.py` : **(c) divergent** si ce fichier est cense etre la machine a etats WR.

Raison : il ne code pas la machine documentee du WR interactif. Il code une ancienne couche readiness/banner avec `ready`, `launched` et `analysis_status`, tandis que les vrais statuts documentes appartiennent a `imperium_weekly_review_sessions.status` et sont geres ailleurs.

Nuance importante : le workflow WR complet n'est pas necessairement absent du backend ; il est surtout dans `weekly_review_conversation.py`. Mais le fichier audite est mal nomme ou mal perimetre par rapport a la doc 32.

## Actions recommandees

1. Decider si `imperium_weekly_review_states` reste utile comme table de banner/readiness.
2. Si oui, renommer/documenter clairement cette couche comme readiness scheduler, pas comme state machine WR.
3. Si non, migrer le banner vers `imperium_weekly_review_sessions.status` et supprimer progressivement `analysis_status`.
4. En correction future, ajouter un garde-fou backend pour mardi 20h Europe/Paris ou documenter explicitement que ce controle appartient au scheduler.
5. Auditer ensuite `weekly_review_conversation.py` en WR-c comme vraie machine de conversation : transitions, guards, actions autorisees, terminal states.
6. Lors des corrections, ajouter/mettre a jour les tests pytest correspondants, notamment pour timing, unicite user/semaine, idempotence, et refus des transitions interdites.
