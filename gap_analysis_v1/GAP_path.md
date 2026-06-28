# GAP Analysis V1 - Path / Religieux

Date: 2026-06-28  
Scope: lecture docs -> gap V1. Aucun code backend audite a nouveau, aucun code applicatif modifie.

## Base de comparaison

Source "deja code" imposee par la tache, sans re-audit:

- `imperium_path_habits` + `imperium_path_check_ins`: Path V1 habits/check-ins propre, deterministe.
- Invariants deja codes: pas de check-in auto, pending exclu des stats, missed requires reason, unicite user/habit/date.
- Coherence religieuse respectee: aucun appel IA/cloud/pgvector/embedding.
- Legacy: `imperium_path_items` deprecie, a debrancher.

Important: ce rapport cherche les capacites Path decrites par les docs mais absentes du perimetre ci-dessus. Il ne rejuge pas la conformite fine du code existant.

Docs lues:

- `docs_master/41_PATH_LOGIC_DETAIL.md`
- `docs_master/50_PATH_DARS_KNOWLEDGE_BASE.md`
- `docs_master/49_PATH_YOUTUBE_CHANNELS.md`
- `docs_master/F04_DEFI_RELIGIEUX.md`
- contexte deja code: `audit_resync/AUDIT_path.md`

## Regle d'or Path

Le religieux ne part jamais au cloud non protege. Le corpus religieux n'est pas vectorise. Pour Path/Dars/invocations/defis religieux, toute feature qui enverrait du corpus religieux brut, de l'arabe religieux a interpreter, des questions religieuses personnelles, des donnees de mosquee/GPS, du ghusl, ou des destinations de sadaqa vers un cloud sans privacy gate doit etre bloquee ou classee comme violation.

Doc 41 pose la base: les actions religieuses sont explicites, personnelles, jamais inferees, et les donnees religieuses privees sont local-first sauf privacy gate. Doc 50 renforce pour Dars: pas de vectorisation du corpus, recherche deterministe full-text, Q&A locale, et refus plutot qu'envoi cloud.

## Lecture de version

| Feature / capacite Path | Version cible d'apres doc | Statut code selon base imposee | Categorie si GAP | Passage source |
|---|---:|---|---|---|
| Habits/check-ins Path generiques | MVP V1 deja code | Code | N/A | base imposee par la tache; audit Path: tables `imperium_path_habits` / `imperium_path_check_ins` |
| Invariants habits/check-ins: action explicite, pending exclu stats, missed reason, unicite | MVP V1 deja code | Code | N/A | base imposee par la tache |
| Absence IA/cloud/pgvector/embedding pour surface codee | MVP V1 deja code | Code | N/A | base imposee par la tache; doc 41 privacy lignes 60-65, 932-948 |
| Legacy `imperium_path_items` deprecie | Dette a debrancher | Code legacy actif | Deterministe | doc 41 lignes 72-78 |
| Events Path V1 append-only | V1 | GAP sauf surface habits/check-ins existante | Deterministe pur + religieux sensible selon event | doc 41 lignes 118-133 |
| All mutations require explicit user action + `Idempotency-Key` | V1 | GAP pour les futures surfaces doc 41; code pour habits/check-ins | Deterministe pur | doc 41 lignes 60-64 |
| Prayer times MAWAQIT priority + cache + stale rules | V1 | GAP | Deterministe pur + religieux sensible pour mosque/GPS privacy | doc 41 lignes 157-206 |
| Local fallback calculation engine, methods/madhhab settings, `path_calculated_prayer_times` | V1 | GAP | Deterministe pur | doc 41 lignes 208-243, 1026-1035 |
| Fallback architecture MAWAQIT API capability investigation | V1 ? a confirmer | GAP | Deterministe pur | doc 41 lignes 236-240 |
| Five obligatory prayer marking, explicit accomplished/not_marked/clear_status | V1 | GAP | Deterministe pur + religieux sensible | doc 41 lignes 247-285 |
| `prayer_logs` table / `/api/path/prayers/{prayer_slug}/mark` | V1 | GAP | Deterministe pur + religieux sensible | doc 41 lignes 267-278 |
| Dynamic prayer mission awareness zones in daily planning | V1 ? a confirmer | GAP | IA/GPU + religieux sensible + cross-module planning | doc 41 lignes 289-320 |
| Fasting start/end/break logs and `fasting_active` computed signal | V1 | GAP | Deterministe pur + religieux sensible | doc 41 lignes 324-382 |
| Pulse fasting constraints handoff | V1 | GAP | Deterministe pur | doc 41 lignes 362-367, 902-907 |
| Sadaqa target from weekly business profit only | V1 | GAP | Deterministe pur + religieux sensible | doc 41 lignes 386-422, 890-899 |
| Sadaqa carry-forward, no negative spiritual debt wording | V1 | GAP | Deterministe pur + religieux sensible | doc 41 lignes 424-452 |
| Sadaqa donation record + Vault expense handoff | V1 | GAP | Deterministe pur + religieux sensible | doc 41 lignes 454-482 |
| Sadaqa safety margin 10-15%, default 12.5% | V1 | GAP | Deterministe pur | doc 41 lignes 485-510 |
| Ghusl required activation/completion events | V1 | GAP | Deterministe pur + religieux sensible | doc 41 lignes 514-563 |
| Imperium ghusl replan / mission insertion | V1 ? a confirmer | GAP | IA/GPU + religieux sensible + cross-module planning | doc 41 lignes 539-552 |
| Registered ghusl addresses CRUD | V1 | GAP | Deterministe pur + religieux sensible | doc 41 lignes 565-593, 1057-1066 |
| Adhkar routines/counters, max 8, tactile +1 canonical | V1 | GAP | Deterministe pur + religieux sensible | doc 41 lignes 597-640, 1068-1085 |
| Optional voice counting for adhkar via transcription with confidence | Optional V1 | GAP | IA/GPU / STT + religieux sensible | doc 41 lignes 610-614 |
| Invocation library by situation + favorites | V1 (integrated in Path V1 reference) | GAP | Religieux sensible; CRUD deterministe apres validation | doc 41 lignes 645-694, 1124-1125 |
| Feed IA / Nourrir l'IA population for invocations | V1 ? a confirmer | GAP | IA/GPU + religieux sensible | doc 41 lignes 669-678 |
| Daily reminder banner from curated reliable base | V1 | GAP | Religieux sensible; deterministe if curated base exists | doc 41 lignes 697-715 |
| Invocations du matin/soir daily checklist | V1 | GAP | Deterministe pur + religieux sensible | doc 41 lignes 717-735 |
| Quran progression continuation point | V1 | GAP | Deterministe pur + religieux sensible | doc 41 lignes 746-768, 1087-1093 |
| Quran reading plans | V1 | GAP | Deterministe pur + religieux sensible | doc 41 lignes 769-793 |
| Path daily score 0.0-1.0 | V1 | GAP | Deterministe pur + religieux sensible | doc 41 lignes 802-829 |
| Hijri date, white days, qibla foundation | V1 | GAP | Deterministe pur + religieux sensible for calendar/location | doc 41 lignes 833-849 |
| Path AI task types: WR contribution, routine adjustment, sadaqa strategy | V1 ? a confirmer | GAP | IA/GPU + religieux sensible | doc 41 lignes 854-873, 1222-1248 |
| Common memory reads/events with Imperium/Vault/Pulse/Vector | V1 | GAP partiel | Mixte | doc 41 lignes 877-926 |
| Privacy/redaction/deletion rules for Path data | V1 | GAP for future surfaces; code by absence for habits/check-ins | Religieux sensible | doc 41 lignes 930-948 |
| Offline/conflict rules for prayer, sadaqa, ghusl, fasting, adhkar, Quran, mosques, settings | V1 | GAP | Deterministe pur + religieux sensible | doc 41 lignes 952-963 |
| PAT-01..PAT-12 backend support surfaces | V1, UI mostly hors backend | GAP backend contracts for most surfaces | Mixte | doc 41 lignes 967-1015 |
| `path_registered_mosques` / `path_mawaqit_cache` | V1 | GAP | Deterministe pur + religieux sensible | doc 41 lignes 1037-1055 |
| `path_weekly_sadaqa_state` | V1 | GAP | Deterministe pur + religieux sensible | doc 41 lignes 1095-1105 |
| Hijri Calendar V3: personal events, lunar observation confirmation, duplicate dates, Imperium bridge | V3 explicite | Hors V1 | Religieux sensible + IA/GPU/cross-module awareness | doc 41 lignes 1127-1218 |
| Path calendar events `path.calendar.*` | V3 extension | Hors V1 | Deterministe + cross-module | doc 41 lignes 1252-1267 |
| Sunnah/Rawatib/Tahajjud/Duha/Witr prayer status | V2 routine candidates | Hors V1 | Religieux sensible | doc 41 lignes 159-162 |
| Dars ingestion/transcription/indexing/Q&A/citations/conflicts/annotations | V3 explicite | Hors V1 en bloc | Religieux sensible + IA/GPU/local OCR/STT | doc 50 lignes 1-36, 64-86 |
| Dars no-vectorization, deterministic FTS, Arabic non-interpretation, local Q&A/refusal | V3 guardrails | Hors V1 en bloc, mais regle a respecter future | Religieux sensible | doc 50 lignes 72-86, 299-321, 802-824 |
| YouTube channels religious learning carousel | V3 explicite | Hors V1 | Deterministe pur; external Google API privacy | doc 49 lignes 1-28, 320-326 |
| Religious daily challenge `defis_religieux` | Future / later spec | Hors V1 | Religieux sensible; daily display deterministe, ingestion IA possible only from user-provided sources | F04 lignes 1-5, 18-33, 89-99 |

## CODE V1

Ces elements sont couverts par le perimetre "deja code" impose:

- Habitudes Path V1: creation/lecture/archive/reactivation de `imperium_path_habits`.
- Check-ins Path V1: creation/lecture/stats sur `imperium_path_check_ins`.
- Invariants operationnels: pas de check-in cree automatiquement, `pending` non persiste et exclu des stats, `missed` exige une raison, unicite `user/habit/date`.
- Surface deterministe sans IA, sans n8n, sans cloud, sans pgvector, sans embedding.
- Dette visible: `imperium_path_items` est legacy/deprecie et encore branche; a debrancher plus tard, hors de cette tache.

Interpretation importante: la surface codee est un noyau habits/check-ins sain. Elle ne couvre pas les contrats religieux specifiques de doc 41 comme `prayer_logs`, `fasting_logs`, `sadaqa_records`, `adhkar_routines`, `quran_progression`, MAWAQIT, ghusl, invocations, Hijri/Qibla.

## GAP V1

### 1. Events, idempotency et offline/conflicts Path V1

Ce qui manque:

- Envelope d'evenements Path doc 41: `path.prayer.logged`, `path.prayer.not_marked`, `path.fasting.started/ended/broken`, `path.sadaqa.recorded`, `path.ghusl.required/completed`, `path.adhkar.incremented`, `path.quran.progress.updated`, `worship.routine.updated`, `path.reminder.requested`.
- `Idempotency-Key` sur toutes les mutations Path doc 41, au-dela des check-ins deja codes.
- Regles offline/conflict par mutation: prayer, sadaqa, ghusl, fasting, adhkar, Quran, mosque, settings.

Tables / contrats affectes:

- Event log commun.
- Tous endpoints `/api/path/*` futurs.
- Read models Imperium/Vault/Pulse.

Categorie:

- Deterministe pur pour l'envelope, l'idempotency, les dedupes et les conflits.
- Religieux sensible pour le contenu des payloads. Logs rediges/redacts obligatoires.

Pourquoi V1:

- doc 41 liste les events Path V1 lignes 118-133.
- doc 41 impose explicit user action + `Idempotency-Key` lignes 60-64.
- doc 41 resume offline/conflict lignes 952-963.

### 2. Prayer times: MAWAQIT, cache, fallback calculation, reference mosque

Ce qui manque:

- Backend MAWAQIT HTTP adapter avec secret env, pas de credential en code.
- Table/cache `path_registered_mosques`, `path_mawaqit_cache`, `path_calculated_prayer_times`.
- Refresh quotidien reference mosque, refresh manuel, stale handling 48h.
- Fallback calculation equivalent Adhan avec method/madhhab/city/GPS/timezone.
- PAT-11 settings backend pour method, madhhab, city/location.

Tables / contrats affectes:

- `path_registered_mosques`.
- `path_mawaqit_cache`.
- `path_calculated_prayer_times`.
- Endpoints mosques / mawaqit search / settings / today dashboard.

Categorie:

- Deterministe pur pour calcul/cache/fetch.
- Religieux sensible pour mosque IDs, mosque names, GPS patterns. Privacy gate obligatoire pour toute sortie externe.

Pourquoi V1:

- doc 41 dit que Path affiche les cinq prieres obligatoires en V1 lignes 157-162.
- MAWAQIT V1 backend adapter lignes 172-184.
- fallback engine V1 settings lignes 208-234.
- tables a ajouter lignes 1026-1055.

### 3. Prayer marking for five obligatory prayers

Ce qui manque:

- `prayer_logs` canonique pour Fajr/Dhuhr/Asr/Maghrib/Isha.
- Endpoint `POST /api/path/prayers/{prayer_slug}/mark`.
- Actions `accomplished`, `not_marked_as_accomplished`, `clear_status`.
- Discipline impact calcule uniquement depuis events explicites, jamais depuis silence.

Tables / contrats affectes:

- `prayer_logs`.
- Event log `path.prayer.logged` / `path.prayer.not_marked`.
- Path dashboard and Imperium discipline context.

Categorie:

- Deterministe pur: CRUD/status rules/conflicts.
- Religieux sensible: wording non jugeant, aucune inference par localisation/temps/telephone.

Pourquoi V1:

- doc 41 lignes 247-285.

### 4. Fasting logs + Pulse constraints

Ce qui manque:

- `fasting_logs` pour start/end/break/abandon.
- Signal `fasting_active` calcule.
- Endpoints `start`, `end`, `break`.
- Handoff lisible par Pulse: hydration disabled during fasting hours, meal/workout constraints.

Tables / contrats affectes:

- `fasting_logs`.
- Path read model common memory.
- Pulse dashboard/hydration/workout/meal suggestion read context.

Categorie:

- Deterministe pur pour logs/signaux.
- Religieux sensible: intention jamais inferee, break fast user-confirmed.

Pourquoi V1:

- doc 41 lignes 324-382.
- Pulse handoff lignes 362-367 et common memory lignes 902-907.

### 5. Sadaqa weekly state, donations, carry, Vault handoff

Ce qui manque:

- `path_weekly_sadaqa_state`.
- Settings Path: sadaqa percentage 1%-20%, change limit, safety margin 10%-15%.
- Weekly target from Vault business profit only.
- Carry-forward remaining, no negative debt/credit display.
- Donation endpoint and history.
- Vault expense handoff category `Sadaqa` with pending/retry state if Vault write fails.

Tables / contrats affectes:

- `sadaqa_records`.
- `path_weekly_sadaqa_state`.
- Vault business profit read model.
- Vault transaction write/handoff contract.
- Endpoints `/api/path/sadaqa/*` and `/api/path/settings/sadaqa`.

Categorie:

- Deterministe pur: arithmetic, carry, allocations, handoff retry.
- Religieux sensible: donation amount/destination redacted, wording must not imply ruling.

Pourquoi V1:

- doc 41 lignes 386-510.
- common memory with Vault lignes 890-899.
- table lignes 1095-1105.

### 6. Ghusl required state + addresses + Imperium handoff

Ce qui manque:

- State `ghusl_required`, `ghusl_required_since`, optional `ghusl_mission_id`.
- Endpoints activate/complete with explicit user action.
- Events `path.ghusl.required` and `path.ghusl.completed`.
- `registered_ghusl_addresses` CRUD with privacy level very_high.
- Imperium handoff for mission creation/replan.

Tables / contrats affectes:

- `registered_ghusl_addresses`.
- Event log.
- Imperium replan request / mission read model.

Categorie:

- Deterministe pur for Path state, address CRUD, events.
- Religieux sensible: ghusl state/address is very_high privacy.
- IA/GPU for the Imperium day replan that inserts the ghusl mission.

Pourquoi V1:

- doc 41 says PAT-04 is V1 activation/completion surface lignes 514-517.
- activation/completion lines 521-563.
- address CRUD lines 565-593.

### 7. Adhkar routines/counters

Ce qui manque:

- `adhkar_routines`.
- `adhkar_completions`.
- CRUD routines, increment/reset endpoints.
- Max 8 active routines.
- Tactile `+1` canonical count, merge increments by idempotency key.
- Optional voice-counting with confidence validation.

Tables / contrats affectes:

- `adhkar_routines`.
- `adhkar_completions`.
- Endpoints `/api/path/adhkar/routines*`.
- Event `path.adhkar.incremented`.

Categorie:

- Deterministe pur for routine CRUD and tactile counter.
- Religieux sensible for Arabic/text/source fields and religious completion state.
- IA/GPU/STT only for optional voice counting.

Pourquoi V1:

- doc 41 lines 597-640.
- tables lines 1068-1085.

### 8. Invocations library, daily reminders, daily invocation checklists, favorites

Ce qui manque:

- Invocation library by situation: quotidien, voyage, protection, difficulte, maladie, peur_anxiete.
- Storage of Arabic text, French translation, optional audio, favorite flag, source/provenance.
- Favorites endpoint.
- Daily reminder curated base: hadith/verse/dua, Arabic + French + reference.
- Morning/evening checklist progress.

Tables / contrats affectes:

- `invocations`.
- `daily_reminders`.
- `daily_invocations`.
- Endpoints `/api/path/invocations*`.
- Worship read model PAT-12.

Categorie:

- Religieux sensible. CRUD/checklists are deterministic only after content is curated/validated.
- IA/GPU if Feed IA/Nourrir l'IA classifies user-provided source content. AI must never be source of truth.

Pourquoi V1:

- doc 41 integrated invocations into Path V1 reference lines 1124-1125.
- invocation sections lines 645-742.

### 9. Quran progression and reading plans

Ce qui manque:

- `quran_progression`.
- `quran_plans`.
- Continuation endpoint, progress mutation, objective patch, plan CRUD.
- Backend normalization page/juz/hizb/surah.
- Regression confirmation when lower than last validated point.

Tables / contrats affectes:

- `quran_progression`.
- `quran_plans`.
- Endpoints `/api/path/quran/*`.
- Event `path.quran.progress.updated`.

Categorie:

- Deterministe pur for progression/plans/validation.
- Religieux sensible: completion never inferred, Khatm informational and user-confirmed.

Pourquoi V1:

- doc 41 lines 746-798.
- table lines 1087-1093.

### 10. Path daily score and Imperium discipline contribution

Ce qui manque:

- Deterministic daily score weighted average:
  - prayer 40%
  - adhkar 20%
  - sadaqa 15%
  - fasting 15%
  - quran 10%
- Read model for Imperium discipline context.
- Explanations/wording that stay operational and non-judgmental.

Tables / contrats affectes:

- Path score service/read model.
- Imperium discipline score input.
- Events/read models from prayer/adhkar/sadaqa/fasting/quran.

Categorie:

- Deterministe pur.
- Religieux sensible because score touches worship discipline and must avoid guilt/judgment.

Pourquoi V1:

- doc 41 lines 802-829.

### 11. Hijri, white days, qibla foundation

Ce qui manque:

- Backend lunar calendar engine for `hijri_date`.
- `white_days_active` suggestion banner, never auto fast.
- Qibla direction endpoint.
- Location/sensor permission gating.

Tables / contrats affectes:

- Calendar/Qibla read endpoints.
- Path dashboard and fasting context.
- Optional external calendar API config.

Categorie:

- Deterministe pur for calendar/qibla calculation/read model.
- Religieux sensible for religious calendar and location.

Pourquoi V1:

- doc 41 lines 833-849.

### 12. Common memory integrations

Ce qui manque:

- Imperium reads Path events: ghusl, prayer not marked, sadaqa, fasting broken.
- Path reads Vault weekly business profit.
- Vault writes matching expense for confirmed sadaqa.
- Pulse reads Path fasting state.
- Imperium overlays Path constraints above Vector profitability.

Tables / contrats affectes:

- Event log / common memory read models.
- Vault profit and transaction contracts.
- Pulse fasting read model.
- Imperium daily planning context.

Categorie:

- Deterministe pur for read/write contracts.
- IA/GPU only where Imperium replanning is triggered.
- Religieux sensible for all payload minimization/redaction.

Pourquoi V1:

- doc 41 lines 877-926.

## V1 ? a confirmer

Ces capacites apparaissent dans le doc Path V1 ou dans un patch de doc 41, mais leur version exacte est ambigue, depend d'un autre module, d'une API externe a verifier, d'un modele local/cloud, ou d'un arbitrage MVP. Ne pas trancher sans validation utilisateur.

| Item | Pourquoi confirmer | Ce qu'il faudrait si valide V1 | Categorie |
|---|---|---|---|
| MAWAQIT fallback architecture exacte | Doc 41 dit d'investiguer ce que MAWAQIT offre avant de finaliser et de ne pas assumer une deuxieme API de calcul. | Spike provider, contrat adapter, fallback local finalise. | Deterministe pur |
| Dynamic prayer mission awareness zones | Doc 41 l'integre a daily planning; pas un simple CRUD Path. | Daily plan creates prayer awareness zones, geo mosque scan, privacy gate, Imperium replan. | IA/GPU + religieux sensible |
| Mosque dynamic selection during VTC/day continuity | Decrit comme dynamic, pas depuis une liste fixe; depend geo API et planning. | Service de recherche geo, scoring continuity, payload minimal. | IA/GPU/cross-module + religieux sensible |
| Ghusl Imperium AI replan | Path activation is V1, but replan uses Imperium AI/n8n and registered addresses. | Event -> replan request -> user validation; no ghusl inference. | IA/GPU + religieux sensible |
| Feed IA / Nourrir l'IA for invocations | Doc 41 l'indique, mais c'est une capacite transverse doc 70 non auditee ici. | Source user-provided, AI classifies only, user validates before storage. | IA/GPU + religieux sensible |
| Path AI task catalog minimal | Doc 41 lists WR contribution/routine adjustment/sadaqa strategy, patch delegates routing to doc 30/32. | ai_task contracts, privacy gate, refusal/local default. | IA/GPU + religieux sensible |
| Sadaqa strategy advice | Rare deep advice; religious+finance sensitive, beyond deterministic tracking. | Strict payload minimization, local/default privacy gate, no ruling language. | IA/GPU + religieux sensible |
| Routine adjustment advice | Could be local/light but touches worship routines. | Suggestion only, user validation, no guilt/authority tone. | IA/GPU + religieux sensible |
| WR contribution from Path | Belongs to WR docs 30/32 routing; Path only provides data. | Read-only contribution contract. | IA/GPU + religieux sensible |
| Backend vs Android split for PAT-01..PAT-12 | Doc 41 lists V1 UI surfaces; this repo is backend. | Backend contracts/read models only; Android UI separately. | Mixte |

## HORS V1

- Sunnah, Rawatib, Tahajjud, Duha, Witr as prayer status: V2 routine candidates, not counted in V1 prayer status.
- Hijri Calendar V3 advanced patch: personal religious events, manual lunar observation confirmation, duplicate-date mechanic, Gregorian bridge to Imperium, path calendar events. V3 explicite.
- Dars knowledge base doc 50: HORS V1 EN BLOC. V3 explicite, "DO NOT IMPLEMENT before V1 + V2". Includes ingestion, OCR/transcription, structuring, PDF rendering, deterministic full-text indexing, Q&A, conflict detection, magisterial annotations, document versioning, Dars UI, local Q&A runtime.
- Dars non-goals V3: auto-summary, quizzes, cross-document fact-checking, Arabic translation, voice questions, sharing, public AI model use, smart related-topic suggestions.
- YouTube channels doc 49: HORS V1 EN BLOC. V3 explicite, quality-of-life religious learning section, deterministic YouTube API/DB/UI, no AI.
- F04 Defi religieux: HORS V1. Spec / a implementer plus tard, dashboard Pulse not Path core. Religieux sensible; daily display is deterministic from prevalidated DB, but ingestion/structuring must never generate hadith from model memory and requires explicit user validation.

## Confirmation Dars / F04 / 49

### Dars doc 50

Confirme HORS V1 en bloc.

Raisons:

- Titre: "Path Dars Knowledge Base (V3)".
- Ligne 3: V3 feature, post-V1 and V2.
- Lignes 26-36: "V3 is the right time" because it requires stable AI layer, stable local OCR/structuring/FTS pipeline, accumulated content, and user trust.
- Lignes 839-900: implementation order explicitly V3.
- Lignes 1046-1048: status "V3 design specification (DO NOT IMPLEMENT before V1 + V2)".

Guardrails a conserver pour plus tard:

- No embedding / no vectorization of religious corpus.
- Deterministic PostgreSQL full-text search.
- Arabic text displayed as stored; AI must not interpret Arabic.
- Local Q&A/refusal; no cloud corpus send if local cannot answer.

### YouTube doc 49

Confirme HORS V1 en bloc.

Raisons:

- Titre: "Path YouTube Channels Follow (V3)".
- Lignes 3-4: V3 feature, quality of life, post-V1 and V2.
- Lignes 20-27: V1 is core prayers/fasting/sadaqa/ghusl/adhkar; V3 is external content tracking/knowledge base.
- Lignes 321-326: no AI, deterministic, but still V3 quality-of-life.
- Lignes 441-443: status V3 design specification, do not implement before V1 + V2.

### F04 Defi religieux

Confirme HORS V1.

Raisons:

- Lignes 3-5: "SPEC / A implementer plus tard", architecture only, no implementation launched.
- It targets Pulse dashboard, not Path V1 backend core lines 113-118.
- It is religious-sensitive content: the doc forbids daily generation and requires prevalidated sources lines 18-33, 89-99.

## GAP V1 priorise

Ordre conseille pour garder le backend-first et eviter les risques religieux/IA:

1. Deterministe pur: event/idempotency/offline envelope Path V1.
2. Deterministe pur + sensible: prayer marking `prayer_logs` for five obligatory prayers.
3. Deterministe pur + sensible: fasting logs and Pulse read constraint.
4. Deterministe pur + sensible: sadaqa state/donations/carry + Vault handoff.
5. Deterministe pur + sensible: ghusl required state + registered ghusl addresses, without AI replan first.
6. Deterministe pur + sensible: adhkar tactile counters.
7. Deterministe pur + sensible: Quran progression.
8. Deterministe pur + sensible: Hijri/Qibla foundation.
9. Religieux sensible: invocations/reminders only with curated/validated source base.
10. IA/GPU later: prayer dynamic missioning, ghusl day replan, routine adjustment, sadaqa strategy, WR contribution.
11. V3 only: Dars and YouTube learning section.

## Suggestion d'enrichissement `docs_master/_CATALOG.yaml`

Ne pas appliquer automatiquement dans cette campagne; proposition pour clarifier version + statut des docs Path.

```yaml
- file: "41_PATH_LOGIC_DETAIL.md"
  number: 41
  title: "The Path Logic Detail"
  family: architecture
  categories: [app:path]
  status: needs_alignment
  version: v1
  source_of_truth_for: ["path product logic", "path v1 capability map", "path religious privacy guardrails", "hijri calendar foundation"]
  depends_on: [1, 5, 30, 32, 40, 42, 43, 59, 70]
  notes: "Canonical Path V1 reference, but wider than current implemented habits/check-ins. Split deterministic V1 core from V1? cross-module AI planning. Patch 41-A contains explicit V3 Hijri calendar extension and should not be mistaken for V1 implementation scope."

- file: "50_PATH_DARS_KNOWLEDGE_BASE.md"
  number: 50
  title: "Path Dars Knowledge Base"
  family: architecture
  categories: [app:path, ai]
  status: up_to_date
  version: v3
  source_of_truth_for: ["future dars ingestion", "future religious corpus deterministic search", "future local-only religious Q&A guardrails"]
  depends_on: [9, 30, 36, 37, 38, 41, 49]
  notes: "Explicit V3 design specification: HORS V1 en bloc. Religious corpus must never be vectorized; use deterministic full-text, local Q&A, Arabic non-interpretation, and refusal instead of cloud fallback."

- file: "49_PATH_YOUTUBE_CHANNELS.md"
  number: 49
  title: "Path YouTube Channels"
  family: architecture
  categories: [app:path]
  status: up_to_date
  version: v3
  source_of_truth_for: ["future religious learning youtube channel follow"]
  depends_on: [41, 50]
  notes: "Explicit V3 quality-of-life feature, deterministic YouTube API/DB/UI, no AI. HORS V1."

- file: "F04_DEFI_RELIGIEUX.md"
  number: 4
  title: "Defi religieux quotidien"
  family: feature
  categories: [feature, app:pulse, app:path]
  status: to_review
  version: future
  source_of_truth_for: ["future prevalidated religious daily challenge"]
  notes: "SPEC / a implementer plus tard. HORS V1. Religieux sensible: daily feature must pick from validated sources, never generate hadith/content from model memory."
```
