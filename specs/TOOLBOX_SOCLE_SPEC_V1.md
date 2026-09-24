# SPEC — SOCLE TOOLBOX V1 (PASSE 0)

> **Livrable d'implémentation one-pass.** Prompt d'exécution destiné à Claude Code (Fable 5),
> travail sur Tower, déploiement VPS par la voie habituelle (Alembic + commande). C'est la
> **passe 0**, exécutée avant Pulse/WR/Daily/Vector. Elle implémente les fondations partagées
> chiffrées par l'audit toolbox (gap_analysis_v1/toolbox/) : runner, notifications, tables
> partagées, serving d'embeddings, réparation E2 + contrat de consommation events, travel v0
> avec privacy_tier, prayer minimal, migration des lecteurs legacy, portage des ponts n8n,
> patches docs et promotion du catalogue en doc 78.
> Toutes les décisions utilisateur (Q1-Q13) sont tranchées et ENCODÉES ici — ne pas rouvrir.

---

## 0. MODE D'EMPLOI POUR L'EXÉCUTEUR

**Étape 0 obligatoire — vérifications avant toute écriture** (produire `SOCLE_MAPPING.md`) :
1. Lire : `gap_analysis_v1/toolbox/` en intégralité (CATALOG_DRAFT, FINDINGS, N8N_INVENTORY,
   EXECUTION_ORDER, patches/), docs 11, 30, 38, 41 §6/§20, 42, 52, 73, 75, 77, F10, doc 05.
2. Vérifier l'infrastructure (post-rapatriement) : Postgres vit-il sur Tower avec la base
   restaurée (`alembic current` = head 0037+, en local) ? Le backend tourne-t-il sur Tower
   (DATABASE_URL local) ? **Base non rapatriée = STOP** (cette passe code contre la vraie
   base, plus jamais contre une hypothèse). Le repo `vtc-companion-app` cloné sous
   `/opt/apps/` : consigner, non bloquant.
3. Confirmer l'état des migrations (0001→0037 + toute nouvelle) et l'écart éventuel avec
   l'audit du 2026-07-10.
4. Consigner créer/étendre/couvert pour chaque table du §4, §7, §8.

**Contraintes non négociables** (héritées des specs précédentes) : anglais base/API/code,
français libellés ; migrations réversibles idempotentes ; feature flags (`real_ai_enabled`,
`embeddings_enabled`, nouveaux : `runner_enabled`, `notifications_enabled`) ; aucune donnée
personnelle en dur ; **zéro nouveau workflow n8n** ; le mécanisme d'exécution unique de tout
l'écosystème est le runner de cette passe.

**Topologie gravée (décision utilisateur, révisée 2026-07-11)** : TOUT vit sur **Tower** —
Postgres, backend, runner, ET les services GPU (embeddings maintenant, 32B/OCR/whisper
ensuite), ces derniers en processus séparés exposés sur localhost. Le VPS Hostinger est
décommissionné : gelé en lecture après migration, il sert de cible de sauvegarde distante
jusqu'à la fin du contrat. Accès aux API : exclusivement via Tailscale (appareils de
l'utilisateur) — aucun port public. Un service GPU injoignable (processus down) ne fait
jamais échouer un job : skip loggé + notification si sévérité le justifie.

**Definition of Done** : migrations + seeds + tests §13 verts + runner opérationnel en
`runner_enabled=False` (dry-run loggé) + les deux ponts n8n portés et leurs équivalences
prouvées + unités systemd du serving embeddings livrées avec checklist de smoke (exécutable
à J+2, à l'arrivée des GPU — ne bloque pas le merge) + patches docs appliqués + catalogue
promu en `docs_master/78_TOOLBOX_CATALOG.md` + SOCLE_MAPPING.md.

---

## 1. CONTEXTE

L'audit a établi : 5 outils codés sur 25, un journal d'events write-only à l'enveloppe vide,
un stub notifications d'une ligne, un serving d'embeddings absent qui verrouille toute la
chaîne mémoire (D5), et trois specs qui re-créeraient chacune ses tables `pulse_/wr_/df_` sans
ce socle. Cette passe pose les fondations UNE fois. Principes : déterministe pur, testable,
zéro LLM dans cette passe (le wrapper LLM naît à la passe Pulse et consommera ces fondations).

---

## 2. TOOLBOX.RUNNER — le mécanisme d'exécution unique (successeur de n8n)

**Architecture** : APScheduler dans le processus backend (VPS) + un consommateur LISTEN/NOTIFY
Postgres + advisory locks. Pas de Celery, pas de Redis, pas de file externe — mono-utilisateur,
un processus, Postgres comme état.

```sql
CREATE TABLE job_definitions (
  id uuid PRIMARY KEY,
  code text UNIQUE NOT NULL,              -- ex: 'vault.weekly_profit', 'wr.factory'
  kind text NOT NULL,                     -- cron|event_subscription|manual
  schedule text,                          -- cron expr si kind=cron
  event_types text[],                     -- si kind=event_subscription
  handler_ref text NOT NULL,              -- chemin python de la fonction
  enabled bool NOT NULL DEFAULT false,    -- tout naît désactivé ; activation explicite
  singleton bool NOT NULL DEFAULT true,   -- advisory lock sur code
  timeout_s int NOT NULL DEFAULT 900,
  version int NOT NULL DEFAULT 1
);

CREATE TABLE job_runs (
  id uuid PRIMARY KEY,
  job_code text NOT NULL,
  trigger text NOT NULL,                  -- cron|event|manual|fallback
  trigger_ref uuid,                       -- event_id si event
  window_from timestamptz, window_to timestamptz,
  status text NOT NULL,                   -- running|completed|failed|skipped
  skip_reason text,                       -- ex: 'gpu_service_unreachable', 'flag_disabled'
  items_in int, items_out int, duration_ms int,
  detail jsonb, created_at timestamptz
);

CREATE TABLE job_cursors (
  job_code text PRIMARY KEY,
  last_processed_event_ts timestamptz NOT NULL,
  last_processed_event_id uuid,
  updated_at timestamptz
);
```

Règles (généralisation du pattern `wr_worker_*` des specs — qui CONSOMMERONT ces tables au
lieu de créer les leurs, cf. patches) : un run échoué n'avance pas son curseur ; singleton via
`pg_advisory_lock(hashtext(code))` ; chaque handler reçoit `(run_ctx, window)` et logge dans
`detail` ; `runner_enabled=False` → tous les jobs s'enregistrent, aucun ne s'exécute (dry-run
loggé en `skipped`). Le consommateur LISTEN écoute le canal `events_new` (trigger SQL
`NOTIFY` sur insert dans `events`, §6) et réveille les jobs `event_subscription` abonnés.

**Portage n8n (N8N_INVENTORY §A)** :
- #1 `wr_interactive_start` et #2 `wr_answers_integrate` : les chaînes de POST internes
  deviennent des appels de service directs dans le flux WR (fonctions backend), mêmes
  payloads, mêmes validations HMAC internes supprimées (plus de saut réseau). Équivalence
  prouvée par tests (fixtures = payloads des exports JSON).
- #3 mock : converti en fixture pytest du flux porté, workflow supprimé du repo.
- `app/services/integrations/n8n_client.py` : déprécié (docstring + warning), plus aucun
  appelant. Variables `N8N_*` de config marquées deprecated. Le conteneur VPS se coupe
  APRÈS confirmation par l'export de l'instance (action utilisateur, hors passe).

---

## 3. TOOLBOX.NOTIFICATIONS — notify() multi-canal, Telegram d'abord (Q3 gravée)

```sql
CREATE TABLE notifications (
  id uuid PRIMARY KEY,
  severity text NOT NULL,                 -- info|normal|red
  domain text NOT NULL,                   -- pulse|wr|daily|vector|path|vault|system
  ref_type text, ref_id uuid,             -- provenance (docket item, red flag, proposition…)
  message_fr text NOT NULL,
  channels_sent jsonb NOT NULL DEFAULT '[]',
  created_at timestamptz,
  read_at timestamptz, acked_at timestamptz
);

CREATE TABLE notification_channels (
  code text PRIMARY KEY,                  -- 'telegram_prod'|'android'|'inapp'
  kind text NOT NULL,
  config jsonb NOT NULL,                  -- token/chat_id chiffrés ou refs env
  enabled bool NOT NULL DEFAULT false,
  is_primary bool NOT NULL DEFAULT false
);
```

API interne : `notify(severity, domain, message_fr, ref=None)`. **Politique de routage
gravée** : `red` → TOUS les canaux actifs ; `normal|info` → canal primaire seulement.
Implémentation V1 : canal `telegram_prod` — **bot et chat DISTINCTS du bot d'orchestration
de build** (`/opt/orchestrator/telegram_bot.py` est l'outillage dev, interdiction de le
réutiliser — confusion signalée par l'audit F1-11). Canal `inapp` = la table elle-même (les
façades liront `notifications` non lues). Canal `android` : enregistré plus tard sans changer
l'interface. Idempotence : un même `(ref_type, ref_id, severity)` ne notifie qu'une fois par
24 h sauf montée de sévérité.

---

## 4. TABLES PARTAGÉES D'EMBLÉE (DBL-2/3/4 tués à la racine)

Créer directement les versions PARTAGÉES ; les passes suivantes consomment (patches déjà
écrits par l'audit) :

- **`parameters`** — pattern append-only de la spec Pulse §3.4 verbatim (code, domain, value
  jsonb, unit, rationale_fr, sources, origin, valid_from, superseded_by, version) + vue
  `v_parameters_current`. Codes namespacés : `pulse.*`, `wr.*`, `df.*`, `vtc.*`, `vault.*`,
  `path.*`, `toolbox.*`.
- **`signal_definitions` / `signal_values`** — schéma de la spec Pulse §3.1 verbatim + colonne
  `domain` en tête + vues par domaine (`v_board_pulse`, etc. créées par les passes). Les 32
  signaux Pulse seront seedés PAR la passe Pulse dans cette table.
- **`ai_slot_transition` / `ai_audit_samples` / vue `v_ai_training_pairs`** — schéma de la
  spec WR §3.7 verbatim. Vides au socle ; chaque passe seede ses slots.

Convention gravée : plus AUCUNE table `pulse_parameters`, `wr_signal_definitions`,
`pulse_ai_transition` ne sera créée — les patches d'étape 0 des passes le rappellent.

---

## 5. TOOLBOX.EMBEDDINGS — le serving qui déverrouille D5

**Serving (Tower, P40)** : `qwen3-embedding:8b` via llama.cpp server (ou vLLM si plus simple
sur Pascal — au choix, documenté), quantification Q8, endpoint HTTP `POST /embed` {texts[]} →
{vectors[][1024]}, exposé UNIQUEMENT sur l'IP Tailscale de Tower. Livrer : unité systemd,
script de démarrage, healthcheck `GET /health`, et la **checklist de smoke J+2** (dimensions
= 1024 exactement, latence batch 32 textes, cosinus de paires témoins > seuils attendus).

**Client (backend, VPS)** : module `app/services/ai/embedding.py` (le module que doc 38 §11
attend) : `embed(texts, privacy_check=True)` → vectors ; batching ; timeout court ; Tower
injoignable → exception typée `GpuServiceUnreachable` que les jobs traitent en skip loggé.
Recherche top-K : helper `search_memories(query_vec, mode=current_truth|historical, k)`
implémentant les deux modes doc 38 (cos×confidence vs cos seul, seuil 0.35 en paramètre).

**Levée de D5** : quand la checklist de smoke est verte, `embeddings_enabled=True` (action
utilisateur) → le commit mémoire WR (memories.py, déjà codé et gated) s'active. Cette passe
ne touche PAS memories.py : elle lui apporte enfin son service.

---

## 6. EVENTS — RÉPARATION E2 + CONTRAT DE CONSOMMATION (le bus cesse d'être muet)

Constats d'audit à corriger : correlation_id aléatoire, causation_id vide, zéro lecteur.

1. **Enveloppe remplie à l'émission** : `ingestion.py` accepte désormais
   `(correlation_id, causation_id)` explicites ; la **passe déterministe des liens déclarés**
   (raison obligatoire → replan → annulations) remplit réellement causation/depth au moment
   de l'action, comme les docs l'ont toujours dit. Les 8 services émetteurs sont mis à jour
   pour propager le contexte (le correlation_id du dossier en cours, le causation_id de
   l'event déclencheur). Ce qui n'a pas de parent naturel : racine (depth=1).
2. **NOTIFY** : trigger SQL sur insert dans `events` → `pg_notify('events_new', event_id)`.
3. **Contrat de consommation** : les jobs `event_subscription` du runner + `job_cursors` =
   LE mécanisme d'abonnement (celui que l'usine WR §4 utilisera). Un consommateur de smoke
   est livré : job `system.events_heartbeat` qui compte les events par type (métrique) —
   le journal a enfin un lecteur, le mécanisme est prouvé.
4. **Nomenclature (DV-11 gravée)** : le canonique est ce que le code émet — `path.ghusl.*`
   reste ; doc 77 patché (worship.* marqué non-retenu) ; les renommages dotted listés par
   doc 77 « À faire côté code » sont appliqués avec table de correspondance ancien→nouveau
   dans le patch et compat en lecture (30 jours), consignés au SOCLE_MAPPING.

---

## 7. TOOLBOX.TRAVEL V0 + TOOLBOX.GEO (interface définitive, moteur provisoire)

**Interface gravée (signature intangible — Vector la renforcera sans la changer)** :
```python
estimate(origin: LatLng, dest: LatLng, at: datetime,
         privacy_tier: Literal['normal','sensitive','very_high'] = 'normal',
         profile: Literal['planning','realtime'] = 'planning') -> TravelEstimate
# TravelEstimate: {duration_s, distance_m, provider, multiplier_applied, cached, computed_at}
```

**Moteur v0** : provider Google Directions (clé en config), **plancher dur ×1,3 codé**
(appliqué même si un paramètre tente moins), cache `(cellule H3 origine, cellule H3 dest,
tranche horaire)` TTL 2 h en table `travel_cache`, fallback hors-ligne
`distance_km / 25 km/h × 1,3` marqué `provider='local_fallback'`.

**privacy_tier (Q2 gravée)** : `very_high` (tout appel provenant de The Path) a
**interdiction codée d'atteindre un provider externe** — v0 le sert exclusivement en
`local_fallback` (grossier mais local ; la matrice H3 de la passe Vector affinera sans
changer la signature). Test-verrou : spy réseau, un appel very_high ne produit AUCUNE
requête sortante. Le pattern Path complet (annuaire mosquées ratissé large par API, sélection
locale, GPS local) s'implémente à la passe Path — l'interface est prête.

**toolbox.geo** : module `geo.py` — indexation H3 (résolution `toolbox.h3_res`, défaut 8),
arrondi de cache, distance haversine, corridor de cellules A→B (ligne brisée élargie, celui
que Vector §3.5 consommera). Propriétaire : le paquet travel.

---

## 8. TOOLBOX.PRAYER MINIMAL (Q6 gravée : les prières entrent dans Daily G4)

Périmètre STRICT de cette passe : **les fenêtres de prière du jour, exactes**. Le reste
(Hijri, Qibla, mosquées, adhkar) = passe Path.

- Client MAWAQIT (mosquée de référence en paramètre `path.reference_mosque_id`) + cache 30 j
  (`path_mawaqit_cache`, nom du doc 41 §20) rafraîchi par job runner `path.mawaqit_refresh`
  (cron 03:00).
- Fallback : calcul local (lib type adhan-python), méthode en paramètre
  `path.calc_method` (défaut : celle du doc 41 — vérifier §6, MuslimWorldLeague/Maliki),
  écart MAWAQIT↔calcul loggé quand les deux sont disponibles (calibration de confiance).
- API : `prayer_windows(date) -> [{prayer, adhan_ts, window_start, window_end}]` — fenêtres
  = paramètres `path.window_before_min`/`after_min`. C'est CE contrat que la passe Daily
  branchera en engagements fixes G4 à fenêtres mobiles (PATCH_DAILY complété en ce sens).
- Table `path_calculated_prayer_times` (doc 41 §20) créée, alimentée par le job.
- Catégorie « déterministe qui doit être EXACT » : tests contre valeurs de référence connues
  (fixtures : 3 dates × 2 saisons, tolérance ±2 min vs source officielle).

---

## 9. MIGRATION DES LECTEURS LEGACY (C-1) — pré-requis des rollups W1

`dashboard.py`, `weekly_report.py` **et `daily_plans.py`** (AD-2 du digest : l'import
`ImperiumPathItem` à daily_plans.py:279 est aussi legacy) migrent vers les sources canoniques :
`imperium_vault_transactions` (ledger), habits/check-ins (Path), `imperium_user_priorities`.
Verrou de parité : pour un jeu de fixtures identiques dans legacy et canonique, les chiffres
affichés sont identiques avant/après ; là où les données réelles DIVERGENT entre legacy et
canonique (raison d'être de la migration), produire un rapport d'écart une fois, en
notification `normal`. Les tables legacy ne sont PAS droppées (déjà tranché PHASE_0) — elles
perdent leurs derniers lecteurs.

## 10. CONFIG RÔLES→MODÈLES + NETTOYAGE DV-6

Table minimale `ai_role_models` (doc 73 PART B, identifier-not-call) : role_code, provider,
model_id, effort, sensitivity_route, version, active. Le seed est résolu exclusivement depuis
le doc 30 §3 actuel. **DV-6** : les six références en dur à l'ancien identifiant local
(config.py:51, providers/qwen.py, WR conversation, tests) sont remplacées par le rôle
`local_executor` résolu via cette table ; tant que l'endpoint n'existe pas, le comportement
reste en dry-run comme aujourd'hui.

## 11. PATCHES DOCS (appliqués dans cette passe, chacun = un commit dédié)

| doc | patch |
|---|---|
| 75 | décroissance par exposition non confirmée = normative (amendement §0.3/§4, renvoi spec WR §6.3) ; « ne plus y revenir » remplacé par la version amendée datée |
| 52 §8 | renvoi : le plan 4 semaines = `plan_versions` (spec WR) ; le cron lundi 05:00 devient la révision mensuelle §8.3 |
| 30 §7.8 | Fable 5 rétabli (01/07/2026), hiérarchie §3 réalignée ; note ai_role_models |
| F10 §5-quater | assistant course : capture+OCR embarqué = primaire (décision utilisateur) ; accessibilité Android = jamais ; PP-OCRv4 = contre-lecture uniquement |
| 42 | échelle pression 0-100 partout (Q4) ; §16 corrigé : weekly_finance_summaries « à créer, mini-passe Vault » |
| 04 | events canonique = `events` (D2 enfin appliqué au doc) |
| 10 | rétention média alignée sur la doctrine actée : « tout conserver » remplace « jeter le brut » (chantier ecosystem 3 absorbé) |
| 77 | nomenclature DV-11 (path.* canonique), renommages dotted appliqués, types des 4 specs ajoutés à leur passe |
| INVENTAIRE_tables | régénéré depuis migrations à jour (DV-9) |
| 78 | **promotion** : TOOLBOX_CATALOG_DRAFT → `docs_master/78_TOOLBOX_CATALOG.md`, questions résolues intégrées, note d'absorption du catalogue ai_task (T7 : ai_slot_transition = le registre), note Q12 (registre GBM naîtra `ml_model_versions` à la passe Vector) |

## 12. SEEDS & PARAMÈTRES

`toolbox.h3_res=8` ; `toolbox.travel_floor=1.3` (doublonné en constante code) ;
`toolbox.travel_cache_ttl_min=120` ; `toolbox.fallback_speed_kmh=25` ;
`toolbox.topk_threshold=0.35` ; `path.calc_method`, `path.window_before_min=0`,
`path.window_after_min` (valeurs doc 41) ; `notify.dedup_hours=24` ;
job_definitions : `system.events_heartbeat`, `path.mawaqit_refresh`, `system.backup_nightly`
(04:00 — restic : pg_dump + repo + docs + configs → disque USB dédié + cible distante via SSH,
dépôt chiffré, rétention 30 j ; le drill de restauration mensuel reste un acte utilisateur), + squelettes désactivés
des jobs des passes suivantes NON créés (chaque passe seede les siens).

## 13. TESTS REQUIS (verrous)

1. Runner : advisory lock (deux lancements concurrents → un run), curseur (échec n'avance
   pas, pas de trou, pas de double), `runner_enabled=False` → skipped loggé, timeout.
2. Ponts n8n : équivalence entrée/sortie sur les payloads des exports JSON ; mock devenu
   fixture ; n8n_client sans appelant (grep).
3. Notifications : routage red→tous / normal→primaire ; dedup 24 h sauf montée de sévérité ;
   bot ≠ bot d'orchestration (config distincte exigée par test).
4. Tables partagées : append-only parameters (UPDATE de value rejeté), vues current.
5. Embeddings : client → dims exactes 1024, GpuServiceUnreachable → skip loggé ; checklist
   smoke J+2 livrée (exécution différée documentée).
6. Events : enveloppe remplie sur un flux déclaré complet (replan avec raison → depth
   corrects) ; NOTIFY délivré ; heartbeat consomme ; renommages compat 30 j.
7. Travel : plancher 1,3 même si paramètre < 1,3 ; cache hit/expiry ; **very_high → zéro
   requête sortante (spy réseau)** ; fallback marqué.
8. Prayer : cache MAWAQIT, fallback ±2 min vs fixtures de référence, fenêtres correctes.
9. Legacy : parité sur fixtures ; rapport d'écart sur divergences réelles.
10. DV-6 : le grep de l'ancien identifiant local est à zéro hors changelog.

## 14. ORDRE D'EXÉCUTION

0. Étape 0 + SOCLE_MAPPING.md (STOP si VPS hors Tailscale).
1. Migrations (§2, §3, §4, §7, §8) + seeds.
2. Runner + portage n8n + heartbeat. 3. Notifications. 4. Réparation E2 + NOTIFY + contrat.
5. Embeddings (client + unités systemd + checklist). 6. Travel v0 + geo. 7. Prayer minimal.
8. Legacy C-1. 9. ai_role_models + DV-6. 10. Tests §13. 11. Patches docs + promotion doc 78.

## 15. HORS PÉRIMÈTRE EXPLICITE

privacy_gate complet (T5 — le privacy_tier travel en est la première brique ; primitive
générale spécifiée avant tout appel cloud réel, passe Pulse) ; routeur /200 (T3) ;
ephemeral_store (naît à la passe WR) ; Knowledge Inbox / Feed AI (passe dédiée après Vector,
remontée en priorité par décision utilisateur) ; prayer complet, Hijri, Qibla, mosquées
(passe Path) ; `ml_model_versions` (passe Vector, nom gravé) ; canal notification Android
(naît avec les façades) ; coupure du conteneur n8n (action utilisateur post-export).
