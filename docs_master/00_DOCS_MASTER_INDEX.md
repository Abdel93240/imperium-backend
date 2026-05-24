# 00 — Docs Master Index

This archive is the cleaned working baseline for Imperium docs.

## Official decisions locked in this cleanup

1. Qwen is the official local AI router in V1.
2. Qwen runs through Ollama in Docker on the same Docker network as n8n.
3. n8n orchestrates workflows but does not write directly to PostgreSQL.
4. The n8n AI Agent is not part of the official V1 architecture.
5. WR interactive flow uses backend state, n8n orchestration, Qwen routing, Opus analysis, user clarification, user approval, then backend storage.
6. Vector is scoped to VTC profitability only. Fatigue, financial pressure, personal objectives, and health are handled by Imperium/Pulse/Vault, not Vector.
7. Cloud AI calls must use anonymized summaries whenever possible.
8. Doc 30 owns AI routing thresholds. Doc 31 uses the same thresholds.

## Cleaned conflicts

- Removed the duplicate `36_OPUS_PROMPTS.md` document. `36_PROMPTS_CLOUD_AI.md` is the canonical prompt contract.
- Replaced obsolete old dual-local-model role language with Qwen-only V1 routing language.
- Rewrote Vector docs to remove cross-domain health/pressure/objective logic.
- Rewrote WR doc with current implemented endpoints and planned conversational endpoints.
- Updated n8n docs with the official trigger families and DB-write boundary.

## Next implementation focus

The next backend/n8n work should follow this order:

1. AI task/result storage layer.
2. Internal AI task result callback.
3. WR conversational session tables and endpoints.
4. n8n workflow for WR launch → Qwen → Opus → callback.
5. Qwen/Ollama Docker deployment on shared n8n network.

---

## Nomenclature (mise à jour)

- **Docs `NN_` (00-58)** : architecture actée / en cours. Numéros inchangés.
- **Docs `FNN_` (F01-F10)** : features futures (non implémentées, documentées
  pour plus tard). Espace séparé pour éviter les collisions de numéros.
- **Docs `99_`** : méta-documentation (règles de nomenclature, audit de cohérence).

Voir `99_REGLES_NOMENCLATURE_DOCS.md` pour les règles complètes.

### Changements de ce nettoyage
- `43` = ex-`43_v2` (l'ancien a été supprimé, le v2 est devenu officiel).
- `45` = `N8N_RESPONSIBILITY_MATRIX` ; l'ancien `45_USER_OBJECTIVES` est devenu `F01`.
- Fichiers corrompus supprimés.
- Doc 38 : embedding V1 = **bge-m3 local** par défaut (privacy), cloud en secours.
