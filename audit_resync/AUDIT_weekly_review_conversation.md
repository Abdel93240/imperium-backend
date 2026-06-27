# AUDIT Weekly Review WR-c — logique conversationnelle

Date : 2026-06-27

Perimetre : lecture seule de `backend/app/services/imperium/weekly_review_conversation.py` (3728 lignes), avec croisement docs 32, 47, 75, 09 et 30. Aucun code applicatif modifie.

Audits precedents pris comme reference :

- WR-a : schema WR globalement sain, mais jonction memoire prisonniere du schema `ai_memories` divergent.
- WR-b : `weekly_review_state.py` est une couche readiness/banner, pas la vraie machine a etats.

## Verdict global

Verdict WR-c : **(c) divergent sur la memoire, (b) leger decalage sur la conversation/session**.

La machine conversationnelle V1 est fonctionnelle et prudente : backend-owned, idempotente, avec drafts non canoniques, validation utilisateur explicite, store separe, pas d'ecriture memoire pendant approve/store. En revanche le bloc memoire a depasse le contrat doc 32 ancien : il expose deja un endpoint de commit reel vers `ai_memories`, et ce commit confirme la dependance au schema WR-specifique divergent (`source_decision_id`, `source_report_id`, `kind/scope/status/visibility`) au lieu du schema vectoriel canonique docs 75/09 (`embedding`, `privacy_level`, `memory_type`, `source_table/source_id`, `is_active`, etc.).

Conclusion courte : **WR-c est utilisable comme workflow conversationnel V1, mais non conforme comme pipeline de memoire vectorielle unifiee.**

## Bloc 1 — Machine a etats / cycle de vie session

Verdict : **(b) leger decalage**.

Ce qui est conforme :

- Creation session : `get_or_create_weekly_review_session()` cree une session unique user/semaine en `ready`.
- Launch : `launch_weekly_review_session()` refuse `cancelled`, `failed`, `approved`, `stored`; pose `launched_at`; passe `ready -> preparing_initial_summary`; cree une `ai_task weekly_report.interactive.start`.
- n8n : l'appel sortant est garde par `N8N_DRY_RUN`, configuration signee, erreurs non bloquantes stockees sur `ai_task.error_code`.
- Attach AI result : types limites a `weekly_report.summary/questions/draft/final/revision`; ownership user verifie; attachement idempotent du meme summary.
- Terminal guards : `stored/cancelled/failed` bloquent la plupart des mutations; `approved` bloque les messages utilisateur ordinaires.

Ecarts / risques :

- Il n'existe pas de table centralisee des transitions autorisees. Les transitions sont dispersees dans les endpoints, donc certaines routes sautent ou ecrasent l'etat selon leur besoin.
- Le workflow doc utilisateur recent parle surtout `conversation_active -> draft_ready -> approved -> stored`. Le code conserve aussi l'ancien flux `initial_summary_ready/waiting_for_user_answer/integrating_answers`.
- `add_user_message()` met toujours `session.status = integrating_answers`, meme si `create_integration_task=False`. Cela peut creer un etat "waiting for AI" sans tache creee selon l'appelant legacy.
- `add_weekly_review_chat_message()` accepte seulement l'absence de draft/final, puis force `conversation_active`; il ne verifie pas explicitement que le summary initial existe.
- `confirm_weekly_review_no_more_input()` genere directement un draft dry-run backend/Qwen au lieu de preparer un vrai audit de sortie high reasoning model.
- `reject_latest_draft_report()` retourne a `initial_summary_ready` si `initial_ai_result_id` existe, sinon `waiting_for_user_answer`; pour le flow chatbot V1, le retour attendu parait plutot `conversation_active` apres rejet/demande de changement.
- `_conversation_ui_state()` mappe `draft_ready/final_ready` sans draft actif vers `preparing_initial_summary`, ce qui masque une incoherence possible au lieu de l'exposer.

Etat par rapport au workflow doc 32 :

- Chemin principal present : `ready -> preparing_initial_summary -> initial_summary_ready/waiting_for_user_answer/conversation_active -> draft_ready/final_ready -> approved -> stored`.
- `cancelled/failed` presents.
- `launched` existe dans le schema mais le service saute de fait vers `preparing_initial_summary`; c'est acceptable si `launched` reste un statut historique, mais a documenter.
- Les transitions interdites majeures sont globalement bloquees par guards terminaux, mais pas par une vraie machine a etats stricte.

## Bloc 2 — Rapport final / draft

Verdict : **(b) leger decalage, principe canonique respecte**.

Ce qui est conforme :

- `_attach_final_report_candidate_from_ai_result()` cree des candidats `draft` non canoniques, historises, lies a `source_ai_result_id`.
- Un autre candidat actif provoque un conflit, sauf reattachement du meme resultat.
- `approve_latest_draft_report()` et `approve_final_report()` exigent un draft/rapport existant, mettent `report.status = approved`, `approved_at`, `session.status = approved`.
- `store_approved_final_report()` est separe : exige `approved`, pose `stored_at`, `report.status = stored`, `session.status = stored`.
- Aucune de ces etapes n'ecrit `ai_memories`, ne genere d'embedding, ne valide une sortie IA sans utilisateur.
- `reject_latest_draft_report()` et `request_draft_changes()` gardent l'historique via `superseded` et details dans `report_payload`.

Ecarts / risques :

- `create_or_update_final_draft()` peut creer un final draft backend sans `ai_result_id`; c'est utile pour V1/backoffice, mais moins strict que le contrat "AI result attaches candidate".
- Le chat `confirm_no_more_input` cree un `AIResult` local dry-run avec `model_hint/model_used = qwen2.5:7b-instruct`; c'est obsolete face au doc 30 actuel (Qwen 32B role local) et couple le code a un modele concret.
- Aucun audit de sortie high reasoning model n'est visible dans ce bloc. Le draft dry-run est une proposition de confort, pas le OUTPUT AUDIT du doc 47.
- `final_ready` existe, mais l'UI/action code traite surtout `draft_ready`; le role de `weekly_report.final` reste moins clair dans le flow chatbot.

## Bloc 3 — Memoire / apprentissages / commit vers `ai_memories`

Verdict : **(c) divergent**. C'est le bloc critique.

### Ce qui est bien separe

- Preview candidates : lecture seulement, `storage_enabled=False`.
- Decisions : `approve/reject/edit` creent des lignes dans `imperium_memory_candidate_decisions`; une decision ne cree pas de memoire.
- Decisions autorisees seulement pour reports `approved` ou `stored`; drafts/superseded restent preview-only.
- Une seule decision par candidat; les replays idempotents sont geres.
- Dry-run commit : `storage_enabled=False`, bloque les rejected/non-approved/invalides, n'ecrit rien.
- Commit reel : accepte explicitement une liste de `decision_ids`, bloque `rejected`, `not_approved_or_edited`, `invalid_candidate`, et detecte les deja-committed par source.

Donc le principe **decision != memoire** est respecte cote declenchement : rien n'est stocke automatiquement lors du draft, approve, store ou decision simple.

### Ce que le commit ecrit vraiment

`commit_weekly_review_memory_candidates()` :

1. lit des `ImperiumMemoryCandidateDecision` appartenant au user;
2. transforme chaque decision via `build_memory_draft_from_weekly_review_decision()`;
3. cherche un doublon via `get_existing_memory_for_source(... source_decision_id=..., source_id=...)`;
4. appelle `create_ai_memory_from_draft()`;
5. retourne `storage_enabled=True` avec la note : `Committed approved memory candidates to ai_memories. No embeddings were generated.`

Le draft memoire cree par `services/ai/memories.py` utilise :

- `source_module = weekly_review`
- `source_type = memory_candidate_decision`
- `source_id = str(decision.id)`
- `source_report_id = decision.report_id`
- `source_session_id = decision.session_id`
- `source_candidate_id = decision.candidate_id`
- `source_decision_id = decision.id`
- `kind`, `scope`, `title`, `content`, `confidence`
- `status = active`
- `visibility = private`

Cela confirme exactement la dependance signalee en WR-a : le code commit depend du schema `ai_memories` actuel, WR-specifique, avec `source_decision_id` comme cle d'idempotence metier.

### Divergence docs 75/09

Non conforme a la memoire vectorielle unifiee :

- Pas d'`embedding` genere; le code le dit explicitement.
- Pas d'`embedding_model`.
- Pas de `privacy_level` sur les lignes `ai_memories`; seulement `visibility='private'`, qui ne remplace pas le privacy gate docs 75/09.
- Pas de `source_table/source_id` canonique pointant vers le contexte riche; le code pointe vers `source_decision_id`, `source_report_id`, `source_session_id`, `source_candidate_id`.
- Pas de `memory_type` ni `learning_element_type`; le code utilise `kind` et `scope`.
- Pas de `is_active`; le code utilise `status`.
- Pas de `supersedes_memory_id` dans le sens doc; le modele a `superseded_by_id`.
- Pas de `expires_at`, `correction_reason`.

Point positif : il n'y a pas de `pgvector_memory` et pas de decay/weight.

### Vectorisation du bon contenu

Le code normalise des candidats explicites depuis `report_payload.memory_candidates` ou `report.memory_candidates`. Si aucun candidat n'existe, il derive des fallback candidates depuis `summary`, `sections`, `questions_answered`.

Risque produit important : ces fallback candidates peuvent transformer un resume/section/reponse en candidat memoire, alors que doc 75 dit de vectoriser uniquement des elements d'apprentissage extraits du WR valide, pas le log WR complet ni des morceaux generiques. Le mecanisme reste soumis a decision utilisateur, donc ce n'est pas une ecriture automatique, mais la qualite de l'extraction est trop generique pour garantir "learning elements only".

## Bloc 4 — Helpers / timeline / etat UI

Verdict : **(b) leger decalage**.

Ce qui est sain :

- Read model conversation borne et user-scoped.
- Slim summaries pour AI result; raw payload non expose sauf debug keys.
- `chat_timeline`, `visible_ai_state`, `draft_review_state`, `primary_action/secondary_actions` evitent que le frontend infere seul les actions.
- `allowed_actions` est conservateur sur les etats fermes.
- `_strip_raw_payload()` retire `raw_payload`, `secret_prompt`, `internal_prompt`, `hidden_reasoning`.

Ecarts / restes perimes :

- Roles de message `qwen`/`opus` et helper `add_backend_or_qwen_message()` couplent le stockage a des modeles concrets.
- `_role_for_ai_result()` classe `claude/opus` en role `opus`; doc 30 demande de raisonner par roles et couche de routage, pas par nom fournisseur dans le domaine WR.
- `model_hint/model_used = qwen2.5:7b-instruct` est perime face au doc 30 actuel (Qwen 32B local).
- Pas de trace visible d'une decision de routage locale par tour (`router_decision`/score) dans ce service; les `AITask` WR sont crees avec `privacy_level=medium`, mais sans score ni choix modele dynamique.
- Pas de trace visible d'un audit d'entree high reasoning model ni d'un audit de sortie high reasoning model. Le code actuel est encore un flow dry-run/local/mock.

## Points transverses

### Routage doc 30

Verdict : **(c) non implemente dans ce fichier** pour le flow cible.

Le doc 30 actuel demande :

- Qwen 32B local comme conducteur/router/scorer;
- scoring par tour;
- specialistes en arriere-plan;
- escalation vers Opus 4.8 / GPT-5.5 selon domaine;
- WR Phase 3 replanning forcee Fable 5 avec fallback Opus 4.8;
- high reasoning model pour les moments de profondeur.

Dans le code :

- `AITask.router_decision` n'est pas renseigne ici.
- Pas de score `/200` visible.
- Pas de local model audit d'entree structure.
- Pas d'OUTPUT AUDIT high reasoning model avant memoire.
- Noms concrets anciens `qwen2.5:7b-instruct`, `qwen-dry-run`, roles `opus`.

Donc le service respecte la securite "AI proposals only", mais pas encore l'architecture de routage cible.

### n8n

Verdict : **(b) conforme V1 dry-run / pas encore cible complet**.

Le backend reste writer unique et les triggers n8n sont optionnels, signes et non bloquants. Pas de direct DB write visible. Les noms de chemins restent Qwen dry-run, ce qui est coherent avec les anciens patchs doc 32 mais obsolete face au doc 30 actuel si on veut abstraire les modeles.

### Privacy

Verdict : **(c) cote memoire cible**.

Les `AITask` ont `privacy_level=medium`; les payloads raw sont nettoyes dans les read models; mais les lignes `ai_memories` creees par commit n'ont aucun `privacy_level`. Doc 75 dit que `privacy_level` sur chaque ligne est non negociable.

## Classification par bloc

| Bloc | Verdict | Resume |
|---|---|---|
| 1. Machine a etats/session | (b) | Fonctionnelle, guards terminaux presents, mais transitions dispersees et pas strictement formalisees. |
| 2. Rapport final/draft | (b) | Approval/store explicites, non canoniques avant validation; manque audit sortie high reasoning, dry-run Qwen obsolete. |
| 3. Memoire/commit | (c) | Decision != memoire respecte, mais commit reel ecrit dans `ai_memories` divergent, sans embedding ni privacy_level. |
| 4. Helpers/UI/timeline | (b) | Read model prudent, mais roles/modeles concrets et routage cible absent. |

## Actions recommandees

1. **Corriger `ai_memories` en premier**, avant de modifier le commit WR : schema docs 75/09, `privacy_level`, embedding, `source_table/source_id`, `memory_type`, `learning_element_type`, lifecycle canonique.
2. Ensuite seulement, rebrancher `commit_weekly_review_memory_candidates()` sur le schema canonique :
   - source vers le WR riche (`source_table='imperium_weekly_review_final_reports'` ou table/log canonique choisie, `source_id=<report/log id>`);
   - conserver `source_decision_id` seulement si decide comme metadata ou colonne documentee;
   - generer embedding + `embedding_model`;
   - appliquer `privacy_level` depuis candidat/report/user settings;
   - mapper `kind` vers `learning_element_type` et domaine vers `memory_type`.
3. Supprimer ou durcir les fallback memory candidates generiques. Les fallback ne doivent pas promouvoir un simple resume/section en apprentissage durable sans extraction explicite.
4. Formaliser une table de transitions autorisees WR dans le service, ou au minimum centraliser les guards par action (`can_launch`, `can_chat`, `can_confirm`, `can_attach_draft`, `can_approve`, `can_store`, `can_commit_memory`).
5. Remplacer les roles et noms de modeles concrets (`qwen`, `opus`, `qwen2.5:7b-instruct`) par des roles stables (`local_conductor`, `high_reasoning`, `backend`) ou documenter une compatibilite legacy.
6. Implementer/brancher le routage doc 30 pour WR :
   - local router/scorer par tour;
   - `router_decision` renseigne sur les `AITask`;
   - audit d'entree par high reasoning model selon doc 47;
   - audit de sortie high reasoning model avant extraction memoire;
   - specialistes GPT-5.5 pour finance/health si necessaire.
7. Aligner doc 32 sur la realite actuelle : il existe maintenant un endpoint commit memoire reel, alors que les sections 4Q-4T disent encore "future explicit memory commit patch".
8. Ajouter les tests pytest lors de la phase correction :
   - interdiction de commit rejected/non-approved;
   - commit idempotent et no duplicate par `source_decision_id`;
   - aucun commit sans `privacy_level` apres alignement;
   - embedding requis apres alignement;
   - transitions interdites depuis `stored/cancelled/failed/approved`;
   - retour correct apres reject/request changes.

## Conclusion

WR-c confirme que `weekly_review_conversation.py` est bien la vraie machine conversationnelle. Elle est prudente sur la validation utilisateur et protege globalement le backend comme source de verite.

Mais le bloc memoire est en avance sur la doc ancienne et en retard sur la doc canonique nouvelle : il sait deja committer, mais il committe dans une table `ai_memories` non vectorielle et non conforme au modele unifie. La prochaine correction ne doit pas commencer par bricoler WR-c : elle doit d'abord resynchroniser `ai_memories`, puis rebrancher proprement WR -> memoire.
