# N8N_INVENTORY — Liste de migration n8n → toolbox.runner

Date : 2026-07-10. Contexte : décision prise de sortir n8n du chemin de production (runner
Python unique dans le backend : APScheduler + LISTEN/NOTIFY + advisory locks, futur
`toolbox.runner` — cf. FINDINGS T2, EXECUTION_ORDER 0a).

## Limite de vérification (à lire d'abord)

L'instance n8n de production tourne sur le VPS Hostinger (doc F10 §4, docker-compose
`IMPERIUM_DOCKER_NETWORK=n8n-postgresql_default`). Elle est INACCESSIBLE depuis Tower
(`N8N_BASE_URL` vide, VPS hors du réseau Tailscale visible, aucun credential sur disque).
→ Les « dates de dernier run » sont NON VÉRIFIABLES d'ici : HYPOTHÈSE ci-dessous = jamais
exécutés en réel (cohérent avec : système non en prod, tables vides, `N8N_DRY_RUN=true` par
défaut dans docker-compose). **À confirmer par un export de l'instance VPS avant suppression.**
L'inventaire se fonde sur : les 3 exports JSON de `ops/n8n/workflows/`, les références du code
(`app/services/integrations/n8n_client.py`, `app/core/config.py:46-47`), et les docs 06/18/32/45.

## A. Workflows n8n EXISTANTS (fichiers sur disque — les seuls prouvés)

| # | nom | déclencheur | fonction | systèmes touchés | dernier run | verdict |
|---|---|---|---|---|---|---|
| 1 | `IMPERIUM_WR_INTERACTIVE_START_QWEN_DRY_RUN` (`ops/n8n/workflows/wr_interactive_start_qwen_dry_run.json`, importé actif selon doc 32 Patch 2F/2G) | webhook signé `imperium/wr/interactive-start-qwen-dry-run` (POST backend, config.py:46) | pont WR : valide payload → `POST /api/internal/ai/qwen/smoke` (dry-run) → callback ai_result HMAC → attach WR | backend interne (ai_tasks/ai_results, WR sessions) | HYPOTHÈSE : smoke tests uniquement (doc 18) | **PORTER (S)** → devient un appel interne direct dans le flux WR du backend (le « workflow » n'est qu'une chaîne de 3 POST internes signés — en backend, c'est une fonction). Cible : job/étape `wr_interactive_start` du runner ou appel synchrone service-à-service. Noter : référence `qwen2.5:7b` à nettoyer (DV-6). |
| 2 | `IMPERIUM_WR_ANSWERS_INTEGRATE_QWEN_DRY_RUN` (`wr_answers_integrate_qwen_dry_run.json`, `active: false` dans l'export) | webhook signé `imperium/wr/answers-integrate-qwen-dry-run` (config.py:47) | pont WR : intégration des réponses utilisateur → callback résultat → attach | idem | HYPOTHÈSE : dry-run only | **PORTER (S)** → même traitement que #1. Après la passe WR Continuous Engine, ce flux est de toute façon restructuré (P2 store éphémère) : porter = absorber dans le service WR. |
| 3 | `IMPERIUM_WR_INTERACTIVE_START_MOCK` (`wr_interactive_start_mock.json`) | webhook mock (doc 32 Patch 2D) | mock de contrat pour tests | tests | HYPOTHÈSE : smoke only | **TUER** (redondant avec #1 ; sa valeur = fixture de test → convertir en test pytest du flux porté, preuve : doc 32 le décrit comme « importable mock … contract preparation »). |

Côté backend, l'unique client sortant est `app/services/integrations/n8n_client.py` (signature
HMAC, dry-run par défaut) : après portage de #1/#2, ce client n'a plus de consommateur → à
déprécier dans la même passe.

## B. Workflows PLANIFIÉS par les docs mais JAMAIS CONSTRUITS (rien à migrer — à créer directement comme jobs runner)

Preuve d'inexistence : seuls 3 JSON dans `ops/n8n/workflows/` ; aucune autre référence de
webhook dans le code. Ces lignes évitent qu'une passe « migre » un workflow fantôme.

| famille (source) | fonction prévue | devenir |
|---|---|---|
| Bannière WR mardi 20:00 (docs 45 §5.2, 32 §2) | flag readiness | déjà tranché backend-only (doc 45 : « Non, backend ») — job runner cron |
| Scan événements Paris lundi 03:00 (docs 45 §6, 30 §4.1) | GPT-5.5 + web → signaux Vector | job runner + toolbox.llm (rôle web/fresh-data) |
| Surveillance temps réel session VTC (doc 45 §7) | polling IdF Mobilités/trafic | builders de caches spec Vector §4.1 = jobs runner (5 min en session) |
| Routes/travaux (doc 45 §8) | hebdo | builder `roadworks` spec Vector §4.1 = job runner |
| Ticket de caisse OCR (docs 45 §9, 42 §6.3) | orchestration OCR + classification | pipeline backend + toolbox.ocr (F1-05) |
| Audio/transcription (doc 45 §10) | STT | toolbox.transcription (F1-06), pipeline backend |
| Mail reçu (docs 45 §13, 30 §4.5) | extraction administrative | SEUL cas où un déclencheur externe type n8n manque vraiment au runner : prévoir un intake IMAP dans toolbox.runner (ou différer — V2, doc 42 §10 le classe déjà V2) |
| Profit hebdo lundi 00:30 (doc 42 §11) | calcul + event | job runner (mini-passe Vault, Q9) |
| Refresh MAWAQIT 03:00 (doc 41 §6.3) | cache prières | job runner (passe Path) |
| Crons des 4 specs (~25 jobs, fiche F1-14) | pulse_*, wr_*, daily_*, vtc_* | jobs runner natifs — c'est le cœur de toolbox.runner |

## C. Rôle résiduel de n8n après portage

Après portage de #1/#2 et création du runner : n8n ne garde AUCUNE responsabilité produit.
Les six familles de triggers du doc 30 §4 se réparties : temporel → APScheduler ; signaux
backend/DB → LISTEN/NOTIFY ; boutons app → API backend (déjà le cas) ; API externes → jobs de
polling runner ; email → intake dédié (V2) ; webhooks entrants → endpoints
`/api/internal/*` existants (HMAC déjà en place). Docs à patcher au moment du décommissionnement :
06, 45, 18, 32 (patches 2D/2F/2O), 44 §13, docker-compose (réseau n8n), config
(`N8N_*`). Le conteneur n8n du VPS se coupe en dernier, après vérification de l'export réel de
l'instance (cf. limite ci-dessus).
