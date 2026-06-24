# 57 - Vector Ride Scoring — ML Classifier (CatBoost)

> **Architectural decision:** Real-time ride scoring in Vector uses a
> **CatBoost regression model** trained on the user's own historical rides.
> The model is bootstrapped with explicit business rules but is designed
> to **override them over time** as it learns the user's real profitability
> patterns.

**Version:** 2.0 — CatBoost + rules cold-start + Bolt import + WR revision
**Last updated:** 2026-05-17

---

## 1. Why CatBoost (not LightGBM)

After review of 2026 ML landscape, **CatBoost is the right choice** for this use case.

```text
LIGHTGBM:
  + Très rapide sur gros volumes (millions de lignes)
  - Encoding manuel des catégorielles (perte d'info)
  - Tuning fin nécessaire
  - Plus sensible à l'overfitting sur petit dataset
  
XGBOOST:
  + Le plus mature
  - Pas de support natif des catégorielles
  - Plus lent que CatBoost/LightGBM
  
CATBOOST (CHOSEN):
  ✅ Gère NATIVEMENT les features catégorielles
     (zones, payment_type, platform, zone_type, etc.)
  ✅ Excellent sur datasets moyens (500-10000 rows)
  ✅ Symmetric trees → moins d'overfitting naturel
  ✅ Robuste aux valeurs manquantes
  ✅ Bon out-of-the-box (peu de tuning)
  ✅ Inference < 1ms sur CPU
  ✅ Modèle compact (< 5 Mo)

POUR TOI (500-10k courses avec beaucoup de catégorielles):
  CatBoost est strictement supérieur.
```

---

## 2. Why Not LLM for Real-Time Scoring

```text
PROBLÈMES AVEC QWEN (plan original doc 33):

1. LATENCE: 2-4s par décision (fenêtre Bolt = 8s)
2. PAS D'APPRENTISSAGE PERSONNEL (règles génériques)
3. PGVECTOR AJOUTE +200-500ms
4. COÛT CPU INUTILE

SOLUTION CATBOOST:
  Inference < 1ms
  Personnel (entraîné sur TES données)
  0€ coût opérationnel
  Précision 70% → 90%+ en 6 mois

LLM REDÉPLOYÉ:
  - Expliquer un score sur demande (the local model, 0€)
  - Analyser patterns dans WR (the high reasoning model, ~0.20€/sem)
  - Proposer révision règles cold-start (the high reasoning model, WR)
```

---

## 3. The Three-Phase Learning Strategy

**Insight architectural critique**: le modèle doit passer des règles aux données dans le temps.

### 3.1 Phase 1 — Cold Start (Days 1-14, < 100 rides)

```text
SITUATION:
  Pas assez de données pour entraîner un modèle fiable.

STRATÉGIE:
  Le scorer applique les RÈGLES MÉTIER explicites (§4).
  Toutes les décisions sont LOGUÉES avec contexte complet.
  Aucun apprentissage actif, juste collecte de données.

OUTPUT:
  Signal GREEN/RED basé sur règles déterministes.
  Source: "rules_only".
  Top factors: la règle qui a tranché.

OBJECTIF:
  Accumuler ~100 courses propres pour entraîner Phase 2.
```

### 3.2 Phase 2 — Transition (Days 15-60, 100-500 rides)

```text
SITUATION:
  Premier modèle CatBoost entraîné, peu de données.
  Précision attendue: 65-75%.

STRATÉGIE HYBRIDE:
  Pour chaque ride, on calcule:
    - score_rules     = décision règles métier
    - score_catboost  = prédiction du modèle
  
  Si d'accord: utiliser le résultat
  Si désaccord: utiliser les règles (plus prudent)
  
  Logger toujours les deux pour analyse.

PHASE-OUT GRADUEL:
  Semaine 3-4: 80% règles / 20% modèle
  Semaine 5-6: 60% règles / 40% modèle
  Semaine 7-8: 40% règles / 60% modèle
  À partir 500 rides: 20% règles / 80% modèle

OBJECTIF:
  Le modèle prouve sa supériorité progressivement.
```

### 3.3 Phase 3 — Autonomous (60+ days, 500+ rides)

```text
SITUATION:
  Modèle mature, précision 80%+.

STRATÉGIE:
  Le modèle CatBoost est PRIMAIRE.
  Les règles s'appliquent UNIQUEMENT si:
    - Hard rule activée par utilisateur (ex: "jamais 8e")
    - Modèle a une confiance très basse (<30%)

RÉVISION DES RÈGLES:
  Chaque semaine, dans le WR (the high reasoning model):
    - Quelle règle a coûté combien en €/semaine?
    - Combien de courses rentables refusées à cause de X?
    - Proposition de désactiver/modifier la règle
  
  Utilisateur valide ou refuse via interface WR.
  Règles deviennent ÉCRASABLES sur validation utilisateur.

OBJECTIF:
  Le modèle devient l'autorité.
  Les règles initiales = safety net + raffinées dans le temps.
```

---

## 4. Initial Business Rules (Cold-Start Pack)

Règles métier explicites de l'utilisateur. **Servent de point de départ** mais sont **conçues pour être écrasées par les données** dans le temps.

### 4.1 Rule R1 — Avoid 8th arrondissement

```text
APPLY: 24/7
ACTION: signal = RED si pickup OR destination = "75008"
REASON: mauvais flux, faible rentabilité réelle, perte de temps
REVISABLE: oui (si modèle prouve €/h > médiane×1.10 sur 75008)
```

### 4.2 Rule R2 — Avoid 18e/19e in daytime

```text
APPLY: time_block = 'daytime' (10h-16h)
ACTION: signal = RED si pickup in ['75018', '75019']
        AND time_block = 'daytime'
REASON: zones non-optimales en journée, repositionnement préférable
REVISABLE: oui
```

### 4.3 Rule R3 — Paris repositioning limits (daytime)

```text
APPLY: time_block = 'daytime' (10h-16h)
ACTION: signal = RED si destination HORS de:
  - West:  beyond Poissy
  - North: beyond L'Isle-Adam
  - East:  beyond Noisy-le-Grand
  - South: beyond Corbeil-Essonnes
REASON: trop loin en journée, repositionnement Paris préférable
REVISABLE: oui (cas spéciaux comme CDG avec retour planifié)
```

### 4.4 Rule R4 — Maximum waiting time (NOT scoring)

```text
APPLY: continuous (during session)
TYPE: repositioning trigger (not ride scoring)
ACTION: After 20 min idle:
  - Trigger Vector suggestion: "Consider repositioning"
  - Show heatmap of better zones
REASON: idle time tue le €/h
NOTE: dans session manager, pas dans le scorer
```

### 4.5 Rule R5 — Night strategy 01h-04h

```text
APPLY: hour in [1, 2, 3]
ACTION: 
  - GREEN bonus si destination 2-3km de zone nightlife majeure
  - RED si destination DANS zone saturée (Bastille, Pigalle, etc.)
REASON: catch outgoing flows, stay mobile
FEATURES NEEDED:
  - distance_to_nearest_nightlife_zone
  - is_in_saturated_zone
```

### 4.6 Rule R6 — Early morning 04h-05h

```text
APPLY: hour in [4, 5]
ACTION:
  - GREEN bonus pour fins d'événements et flux banlieue
  - Prioriser late party / périphérie returns
REASON: late-night flows + early departures
FEATURES NEEDED:
  - event_ending_nearby_last_60min
  - is_banlieue_flow_route
```

### 4.7 Rule R7 — Night Paris return

```text
APPLY: time_block in ['night', 'late_evening']
ACTION: GREEN bonus si destination vers Paris
        même après courses extérieures
REASON: retour progressif vers zone haute densité
FEATURES NEEDED:
  - is_returning_to_paris (calculé via headings)
```

### 4.8 Rule R8 — Scheduled rides at night

```text
APPLY: ride_type = 'scheduled' AND time_block in ['night', 'late_evening']
ACTION: GREEN strong (sécurise CA, réduit incertitude)
REASON: scheduled rides la nuit = revenue safety
FEATURES NEEDED:
  - is_scheduled_ride (from Bolt offer type)
```

### 4.9 Rule R9 — Destination mode budget (NOT scoring)

```text
APPLY: continuous (during session)
TYPE: resource tracker (not ride scoring)
ACTION: Track destination_mode_uses_today (max 6/day)
        Warn quand budget dépensé sur low-value moves
FEATURES IN SCORER:
  - destination_mode_uses_remaining
  - Model learns when destination_mode is "worth using"
```

### 4.10 Rule R10 — Airport arrival lag

```text
APPLY: pickup zone is airport (CDG/ORY/BVA)
ACTION: Ajuster expected demand sur LAG RÉEL, pas heure atterrissage
LAG ESTIMATE: landing + 30 min (immigration + bags + terminal + app)
FEATURES NEEDED:
  - aircraft_landing_30min_ago (PAS next_30min)
  - aircraft_landing_60min_ago (catches late ones)
```

### 4.11 Rule R11 — Google Maps duration underestimation

```text
APPLY: continuous
TYPE: data processing rule (not scoring)
ACTION: Track actual_duration / estimated_duration par zone/heure
LEARNING:
  - Feature: zone_time_duration_multiplier (learned, NOT hardcoded)
  - Updated weekly from completed rides
REASON: Google annonce 10 min → réalité souvent 13-14 min
PRINCIPE: pas de multiplicateur en dur, le modèle apprend.
```

### 4.12 Rule storage schema

```sql
CREATE TABLE vector_business_rules (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_code             VARCHAR(16) UNIQUE NOT NULL,
                        -- 'R1', 'R2', ... 'R11'
  rule_name             TEXT NOT NULL,
  rule_description      TEXT NOT NULL,
  rule_type             VARCHAR(32) NOT NULL,
                        -- 'scoring' | 'repositioning' | 'budget' | 'data_processing'
  
  conditions_json       JSONB NOT NULL,
  action_json           JSONB NOT NULL,
  
  is_active             BOOLEAN NOT NULL DEFAULT TRUE,
  is_hard_rule          BOOLEAN NOT NULL DEFAULT FALSE,
                        -- TRUE = never auto-overridable
  
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_revised_at       TIMESTAMPTZ NULL,
  revision_count        INTEGER NOT NULL DEFAULT 0,
  
  -- Performance tracking
  times_applied         INTEGER NOT NULL DEFAULT 0,
  estimated_revenue_impact_eur NUMERIC(8,2) NULL,
  last_impact_review_at TIMESTAMPTZ NULL
);

CREATE TABLE vector_rule_revisions (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rule_id               UUID NOT NULL REFERENCES vector_business_rules(id),
  revised_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  revision_type         VARCHAR(32) NOT NULL,
                        -- 'disabled' | 'modified' | 'tightened' | 'loosened'
  reason                TEXT NOT NULL,
  
  previous_conditions   JSONB,
  new_conditions        JSONB,
  
  proposed_by           VARCHAR(32) NOT NULL,
                        -- 'opus_wr' | 'user_manual' | 'auto_threshold'
  user_validated        BOOLEAN NOT NULL DEFAULT FALSE,
  validated_at          TIMESTAMPTZ NULL
);
```

---

## 5. Complete Feature List

### 5.1 Ride features (from Bolt OCR)

```text
NUMERICAL:
├─ price_eur                       — offer price (excl. tolls)
├─ distance_km                     — ride distance
├─ estimated_duration_min          — estimated duration
├─ approach_distance_km            — from current GPS to pickup
├─ approach_duration_min           — time to reach pickup
├─ surge_multiplier                — surge ratio (1.0 = no surge)
├─ hourly_rate_offered             — computed: price / (duration/60)
├─ price_per_km                    — computed: price / distance
└─ total_ride_time_min             — approach + ride duration

CATEGORICAL (CatBoost natif):
├─ pickup_zone_code                — postal code "75008"
├─ destination_zone_code           — postal code
├─ pickup_zone_type                — 'airport'|'station'|'business'|'residential'|'leisure'|'nightlife'
├─ destination_zone_type           — same options
├─ payment_type                    — 'card'|'cash'|'pro'
├─ platform                        — 'bolt' (V1) | 'heetch' (V2+)
├─ ride_type                       — 'immediate'|'scheduled'
└─ ride_class                      — 'standard'|'comfort'|'xl'|'pet'
```

### 5.2 Temporal features

```text
NUMERICAL:
├─ hour_of_day                     — 0-23
├─ day_of_week                     — 0=Monday, 6=Sunday
├─ day_of_month                    — 1-31
├─ month                           — 1-12
├─ week_of_year                    — 1-52
├─ minutes_to_next_prayer          — from Path MAWAQIT
├─ minutes_since_last_prayer       — same
└─ minutes_to_end_of_session       — if user set target

BOOLEAN:
├─ is_weekend                      — Saturday or Sunday
├─ is_friday_night                 — Friday after 22h
├─ is_school_holiday               — French school holidays
├─ is_public_holiday               — French public holidays
├─ is_eve_of_holiday               — day before public holiday
├─ is_ramadan                      — from Path religious calendar
└─ is_jumuah_approaching           — Friday prayer time approaching

CATEGORICAL:
└─ time_block                      — 'night'(00-06) | 'morning'(06-10)
                                     | 'daytime'(10-16) | 'evening'(16-20)
                                     | 'late_evening'(20-24)
```

### 5.3 Zone & geographic features

```text
PICKUP ZONE:
├─ pickup_zone_demand_score        — WRS score this time block (0-10)
├─ pickup_zone_avg_hourly_rate     — historical €/h from this zone
├─ pickup_in_paris                 — BOOL
├─ pickup_in_petite_couronne       — BOOL (92, 93, 94)
├─ pickup_in_grande_couronne       — BOOL (77, 78, 91, 95)
├─ pickup_lat / pickup_lng         — raw coordinates

DESTINATION ZONE:
├─ dest_zone_demand_score          — WRS score
├─ dest_zone_return_probability    — P(ride within 15min)
├─ dest_zone_avg_wait_min          — avg wait after dropoff
├─ dest_in_paris                   — BOOL
├─ dest_in_petite_couronne         — BOOL
├─ dest_in_grande_couronne         — BOOL
├─ dest_lat / dest_lng             — raw coordinates

DISTANCE-BASED:
├─ direction_toward_paris          — BOOL (Rule R7)
├─ direction_away_from_paris       — BOOL
├─ distance_paris_center_km        — destination distance to Paris center
├─ distance_to_nearest_airport_km  — CDG/ORY/BVA
├─ distance_to_nearest_station_km  — Gare du Nord/Lyon/etc.
├─ distance_to_nearest_nightlife   — Rule R5
├─ within_repositioning_limits     — Rule R3 zones (BOOL)
└─ is_in_saturated_zone            — Rule R5 (BOOL)

LEARNED ZONE FEATURES:
├─ pickup_zone_time_duration_mult  — Rule R11 learned ratio
├─ dest_zone_time_duration_mult    — same for destination
└─ dest_is_dead_zone               — historical return < 20%
```

### 5.4 Session context features

```text
├─ session_rides_done              — rides completed this session
├─ session_elapsed_hours           — hours since session started
├─ session_revenue_so_far          — €€ earned this session
├─ session_daily_target_pct        — % of daily target achieved
├─ session_avg_hourly_rate_so_far  — current session €/h
├─ time_since_last_ride_min        — idle time before this offer
├─ last_ride_destination_zone      — where last dropoff was
├─ last_ride_hourly_rate           — last ride's €/h
├─ destination_mode_uses_remaining — Rule R9 budget (0-6)
└─ minutes_in_current_zone         — for Rule R4 alignment
```

### 5.5 External signals (V1 — easy)

```text
WEATHER (Open-Meteo, FREE):
├─ weather_is_rain                 — BOOL
├─ weather_is_snow                 — BOOL
├─ weather_temp_celsius            — current temperature
├─ weather_wind_kmh                — wind speed
└─ weather_visibility_km           — fog detection
```

### 5.6 External signals (V2 — to add)

```text
TRANSPORT DISRUPTIONS:
├─ ratp_disruption_metro_active    — BOOL
├─ ratp_disruption_rer_active      — BOOL
├─ sncf_disruption_active          — BOOL
└─ ratp_lines_affected             — count

AIRPORTS (Rule R10 lag):
├─ cdg_landings_30_60_min_ago      — count
├─ ory_landings_30_60_min_ago      — count
└─ bva_landings_30_60_min_ago      — count

EVENTS:
├─ event_nearby_attendees          — total within 2km
├─ event_ending_within_60min       — BOOL (Rule R6)
└─ event_type                      — 'concert'|'sport'|'theater'|'club'

SURGE HISTORY (from manual captures — see §16):
├─ zone_surge_recent_avg        — avg surge multiplier in zone, last N min
├─ zone_surge_trend             — rising | flat | falling (last 10 min)
└─ zone_surge_at_similar_time   — historical surge for this zone + time_block

TRAFFIC:
├─ idf_traffic_level               — 1-5 from TomTom
└─ pickup_zone_traffic_jam         — BOOL local jam
```

### 5.7 Rule-derived features (CRITICAL)

Ces features encodent explicitement les règles. **Le modèle apprend ainsi s'il doit les suivre ou les contourner.**

```text
├─ rule_R1_violation               — pickup or dest in 75008
├─ rule_R2_violation               — pickup in 75018/75019 daytime
├─ rule_R3_violation               — destination outside reposition limits
├─ rule_R5_bonus                   — night zone bonus (01h-04h)
├─ rule_R6_bonus                   — early morning bonus (04h-05h)
├─ rule_R7_bonus                   — returning to Paris at night
└─ rule_R8_bonus                   — scheduled ride at night
```

**Pourquoi inclure les violations comme features**: le modèle apprend à override les règles. Si "Rule R1 violation" donne en fait du bon €/h, le modèle prédit GREEN malgré la règle. Avec le temps, ça signale au WR de réviser la règle.

---

## 6. The Target Variable

```text
PRIMARY TARGET: predicted_hourly_rate (REGRESSION)

  = €/h que la course va RÉELLEMENT rapporter, en comptant:
    - Durée réelle (pas estimation Bolt)
    - Probabilité de retour
    - Temps d'attente après dépose
    - Idle time absorbé avant prochaine course

DERIVED SIGNAL:
  score_vs_median = predicted_hourly_rate / user_median_hourly_rate
  
  GREEN  if score_vs_median ≥ 1.10  (10% above median)
  RED    if score_vs_median ≤ 0.85  (15% below median)
  WHITE  if entre 0.85 et 1.10      (around median)
  
USER ADJUSTABLE in settings.
```

**CHOIX DE DESIGN CRITIQUE**: On NE PAS entraîne sur "user accepted/declined". Parce que l'utilisateur refuse parfois des courses rentables par fatigue. Entraîner sur l'acceptation subjective apprendrait au modèle les FAIBLESSES de l'utilisateur, pas sa rentabilité. Le modèle apprend du €/h RÉEL atteint, point.

---

## 7. Bootstrap: Importing Historical Bolt Rides

### 7.1 The workflow

```text
STEP 1 — USER COLLECTS SCREENSHOTS
  - User opens Bolt app history
  - Takes screenshots of all rides from last 1-3 months
  - Compresses into ZIP
  - Uploads to import endpoint

STEP 2 — THE OCR SERVICE EXTRACTION
  - Each screenshot → the OCR service
  - Extracts: date, time, pickup, destination, distance,
    duration, price, payment method
  - JSON output per screenshot

STEP 3 — CSV CONSOLIDATION
  - All extractions merged into single review interface
  - User reviews via UI
  - Manual correction for OCR errors
  - Confirms when ready

STEP 4 — DATA ENRICHMENT
  - Each ride enriched with:
    * Postal code from address (Nominatim geocoding, FREE)
    * Zone type classification
    * Time block, day-of-week, etc.
    * Weather at that hour (Open-Meteo Historical, FREE)
    * Public/school holidays
    * Coordinates (lat/lng)
  - Deterministic enrichments only for V1

STEP 5 — DB IMPORT
  - Import to vector_ride_history with status='historical_import'
  - Compute actual_hourly_rate where possible
  - Mark usable rides for training

STEP 6 — VALIDATION REPORT
  - Show: N imported, M usable
  - Flag anomalies (duration=0, price=0, etc.)
  - User reviews before triggering training
```

### 7.2 The OCR service prompt template

```text
SYSTEM PROMPT:
"You are extracting Bolt VTC ride data from a screenshot.
Return ONLY valid JSON, no commentary.

Schema:
{
  \"date\": \"YYYY-MM-DD\",
  \"time\": \"HH:MM\",
  \"pickup_address\": \"...\",
  \"destination_address\": \"...\",
  \"distance_km\": float,
  \"duration_min\": int,
  \"price_eur\": float,
  \"payment_method\": \"card\"|\"cash\"|\"pro\"|null,
  \"ride_class\": \"standard\"|\"comfort\"|\"xl\"|\"pet\"|null,
  \"is_scheduled\": boolean,
  \"surge_applied\": boolean,
  \"confidence\": 0.0-1.0
}

If any field unclear, return null. Confidence reflects overall certainty."
```

### 7.3 Import tables

```sql
CREATE TABLE vector_bolt_import_staging (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  imported_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  import_batch_id       UUID NOT NULL,
  
  -- Source
  screenshot_filename   TEXT,
  gemini_raw_response   JSONB NOT NULL,
  gemini_confidence     NUMERIC(3,2),
  
  -- Extracted data
  ride_date             DATE,
  ride_time             TIME,
  pickup_address_raw    TEXT,
  destination_address_raw TEXT,
  distance_km           NUMERIC(8,2),
  duration_min          INTEGER,
  price_eur             NUMERIC(8,2),
  payment_method        VARCHAR(16),
  ride_class            VARCHAR(16),
  is_scheduled          BOOLEAN,
  surge_applied         BOOLEAN,
  
  -- Validation
  needs_user_review     BOOLEAN NOT NULL DEFAULT FALSE,
  review_reason         TEXT,
  user_corrected        BOOLEAN NOT NULL DEFAULT FALSE,
  
  -- Enrichment status
  geocoded              BOOLEAN NOT NULL DEFAULT FALSE,
  weather_enriched      BOOLEAN NOT NULL DEFAULT FALSE,
  ready_for_import      BOOLEAN NOT NULL DEFAULT FALSE,
  
  imported_to_history_id UUID NULL REFERENCES vector_ride_history(id)
);

CREATE INDEX vector_bolt_import_staging_batch_idx
ON vector_bolt_import_staging (import_batch_id);

CREATE INDEX vector_bolt_import_staging_review_idx
ON vector_bolt_import_staging (needs_user_review)
WHERE needs_user_review = TRUE;
```

### 7.4 Import processor (Python)

```python
# bolt_import_processor.py
import json
import zipfile
import google.generativeai as genai
from pathlib import Path
from uuid import uuid4

class BoltImportProcessor:
    
    def __init__(self, db, gemini_api_key):
        self.db = db
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
    
    async def process_zip(self, zip_path: Path) -> dict:
        batch_id = uuid4()
        results = {
            'batch_id': str(batch_id),
            'total': 0,
            'successful': 0,
            'failed': 0,
            'needs_review': 0
        }
        
        with zipfile.ZipFile(zip_path) as z:
            screenshots = [n for n in z.namelist()
                          if n.lower().endswith(('.png', '.jpg', '.jpeg'))]
            results['total'] = len(screenshots)
            
            for filename in screenshots:
                try:
                    img_data = z.read(filename)
                    extracted = await self._ocr(img_data)
                    needs_review = self._needs_review(extracted)
                    
                    await self.db.execute("""
                        INSERT INTO vector_bolt_import_staging (
                            import_batch_id, screenshot_filename,
                            gemini_raw_response, gemini_confidence,
                            ride_date, ride_time,
                            pickup_address_raw, destination_address_raw,
                            distance_km, duration_min, price_eur,
                            payment_method, ride_class,
                            is_scheduled, surge_applied,
                            needs_user_review, review_reason
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s, %s, %s
                        )
                    """, (
                        batch_id, filename,
                        json.dumps(extracted),
                        extracted.get('confidence', 0.0),
                        extracted.get('date'), extracted.get('time'),
                        extracted.get('pickup_address'),
                        extracted.get('destination_address'),
                        extracted.get('distance_km'),
                        extracted.get('duration_min'),
                        extracted.get('price_eur'),
                        extracted.get('payment_method'),
                        extracted.get('ride_class'),
                        extracted.get('is_scheduled', False),
                        extracted.get('surge_applied', False),
                        needs_review,
                        self._review_reason(extracted) if needs_review else None
                    ))
                    
                    results['successful'] += 1
                    if needs_review:
                        results['needs_review'] += 1
                        
                except Exception as e:
                    results['failed'] += 1
                    print(f"Failed {filename}: {e}")
        
        return results
    
    async def _ocr(self, img_bytes: bytes) -> dict:
        prompt = """Extract Bolt VTC ride data from this screenshot.
Return ONLY valid JSON. If any field unclear, return null."""
        
        response = await self.model.generate_content_async([
            prompt,
            {"mime_type": "image/png", "data": img_bytes}
        ])
        
        text = response.text.strip()
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
        return json.loads(text.strip())
    
    def _needs_review(self, e: dict) -> bool:
        if e.get('confidence', 0) < 0.85: return True
        if not e.get('date') or not e.get('time'): return True
        if e.get('price_eur', 0) <= 0: return True
        if e.get('duration_min', 0) <= 0: return True
        if not e.get('pickup_address'): return True
        if not e.get('destination_address'): return True
        return False
    
    def _review_reason(self, e: dict) -> str:
        reasons = []
        if e.get('confidence', 0) < 0.85: reasons.append('low_confidence')
        if not e.get('date'): reasons.append('missing_date')
        if e.get('price_eur', 0) <= 0: reasons.append('invalid_price')
        if e.get('duration_min', 0) <= 0: reasons.append('invalid_duration')
        return ','.join(reasons)
```

### 7.5 Enrichment processor

```python
# bolt_import_enricher.py
import requests
import time

class BoltImportEnricher:
    """Enriches staging with weather, geocoding."""
    
    OPEN_METEO_HIST = "https://archive-api.open-meteo.com/v1/archive"
    NOMINATIM = "https://nominatim.openstreetmap.org/search"
    
    async def enrich_batch(self, batch_id):
        rows = await self.db.fetch("""
            SELECT * FROM vector_bolt_import_staging
            WHERE import_batch_id = %s
              AND needs_user_review = FALSE
              AND ready_for_import = FALSE
        """, batch_id)
        
        for row in rows:
            pickup_geo = await self._geocode(row['pickup_address_raw'])
            dest_geo = await self._geocode(row['destination_address_raw'])
            time.sleep(1)  # Nominatim rate limit
            
            weather = await self._fetch_weather(
                pickup_geo['lat'], pickup_geo['lng'],
                row['ride_date'], row['ride_time']
            )
            
            await self.db.execute("""
                UPDATE vector_bolt_import_staging
                SET geocoded = TRUE,
                    weather_enriched = TRUE,
                    ready_for_import = TRUE
                WHERE id = %s
            """, row['id'])
    
    async def _geocode(self, address: str) -> dict:
        params = {
            'q': address + ', France',
            'format': 'json',
            'limit': 1,
            'addressdetails': 1
        }
        # Returns: {lat, lng, postcode, district, city}
        # Rate-limited to 1 req/sec
        pass
    
    async def _fetch_weather(self, lat, lng, date, time) -> dict:
        params = {
            'latitude': lat, 'longitude': lng,
            'start_date': date, 'end_date': date,
            'hourly': 'temperature_2m,precipitation,rain,snowfall,visibility,wind_speed_10m'
        }
        # Returns weather for specific hour of ride
        pass
```

### 7.6 User review interface

```text
Vector > Settings > Import historique:

  ┌─────────────────────────────────────────────────────┐
  │ Import en cours: Batch 2026-05-17                   │
  │                                                     │
  │ Screenshots traités: 247 / 247                      │
  │ Extractions réussies: 231 (93.5%)                   │
  │ Échouées: 16 (6.5%)                                 │
  │ Nécessitent ta validation: 28                       │
  │                                                     │
  │ [Voir les courses à valider]                        │
  │ [Lancer l'enrichissement (météo, géoloc)]           │
  │ [Importer en historique principal]                  │
  │ [Annuler ce batch]                                  │
  └─────────────────────────────────────────────────────┘

  COURSE À VALIDER #15:
  ┌─────────────────────────────────────────────────────┐
  │ Date: 2026-04-12 18:34                              │
  │ Pickup: [12 rue de Rivoli, 75001]    [✏️ Modifier]  │
  │ Destination: [Aéroport CDG T2E]      [✏️ Modifier]  │
  │ Distance: 38.4 km                                   │
  │ Durée: ???  ← À vérifier              [✏️ Saisir]  │
  │ Prix: 89.50€                                        │
  │ Paiement: Carte                                     │
  │                                                     │
  │ Confiance the OCR service: 82%                      │
  │ Raison: durée manquante                             │
  │                                                     │
  │ [✓ Valider] [✗ Supprimer] [⏭ Plus tard]              │
  └─────────────────────────────────────────────────────┘
```

---

## 8. The Inference Pipeline

```python
# vector_ride_scorer.py
import json
from pathlib import Path
from datetime import datetime
from catboost import CatBoostRegressor

class VectorRideScorer:
    """Hybrid rules + ML scorer with phase logic."""
    
    MODEL_PATH = Path("/opt/vector/models/vector_ride_model.cbm")
    META_PATH = Path("/opt/vector/models/vector_ride_model_meta.json")
    
    def __init__(self, db):
        self.db = db
        self.model = None
        self.metadata = None
        self.feature_names = []
        self.cat_features = []
        self.median_hourly_rate = 22.0
        self.rules = []
        self.phase = 'cold_start'
        self.reload()
        self._load_rules()
    
    def reload(self):
        """Hot-reload after retraining."""
        if self.MODEL_PATH.exists():
            self.model = CatBoostRegressor()
            self.model.load_model(str(self.MODEL_PATH))
            with open(self.META_PATH) as f:
                self.metadata = json.load(f)
            self.feature_names = self.metadata['feature_names']
            self.cat_features = self.metadata['cat_features']
            self.median_hourly_rate = self.metadata['median_hourly_rate']
            
            n = self.metadata['n_rides']
            self.phase = ('cold_start' if n < 100
                         else 'transition' if n < 500
                         else 'autonomous')
    
    async def _load_rules(self):
        self.rules = await self.db.fetch(
            "SELECT * FROM vector_business_rules WHERE is_active = TRUE"
        )
    
    async def score(self, ride: dict, context: dict) -> dict:
        # Always evaluate rules
        rules_result = self._apply_rules(ride, context)
        
        # If no model: rules only
        if self.model is None or self.phase == 'cold_start':
            return self._format(
                rules_result['signal'], None,
                rules_result['triggered_rules'],
                'rules_only', rules_result['reasoning']
            )
        
        # Run model
        features = self._build_features(ride, context)
        vec = [features.get(f, 0) for f in self.feature_names]
        pred_eur_h = float(self.model.predict([vec])[0])
        pred_eur_h = max(0, pred_eur_h)
        score_vs_median = pred_eur_h / max(self.median_hourly_rate, 1)
        
        green = context.get('green_threshold', 1.10)
        red = context.get('red_threshold', 0.85)
        
        if score_vs_median >= green: model_signal = 'GREEN'
        elif score_vs_median <= red: model_signal = 'RED'
        else: model_signal = 'WHITE'
        
        # Hybrid decision
        if self.phase == 'transition':
            if rules_result['signal'] != 'NEUTRAL' and rules_result['signal'] != model_signal:
                final = rules_result['signal']
                source = 'rules_override'
            else:
                final = model_signal
                source = 'model'
        else:  # autonomous
            if rules_result['hard_rule_violated']:
                final = rules_result['signal']
                source = 'hard_rule'
            else:
                final = model_signal
                source = 'model'
        
        return self._format(
            final, pred_eur_h,
            rules_result['triggered_rules'], source, None
        )
    
    def _apply_rules(self, ride, ctx) -> dict:
        triggered = []
        signal = 'NEUTRAL'
        hard_violated = False
        
        for rule in self.rules:
            if self._rule_applies(rule, ride, ctx):
                triggered.append(rule['rule_code'])
                action = rule['action_json']
                if action.get('signal') == 'RED':
                    signal = 'RED'
                    if rule['is_hard_rule']: hard_violated = True
                elif action.get('signal') == 'GREEN' and signal != 'RED':
                    signal = 'GREEN'
        
        return {
            'signal': signal,
            'triggered_rules': triggered,
            'hard_rule_violated': hard_violated,
            'reasoning': f"Rules: {','.join(triggered)}"
        }
    
    def _rule_applies(self, rule, ride, ctx) -> bool:
        # Conditions parsing logic per rule
        # See §4 for examples
        pass
    
    def _build_features(self, ride, ctx) -> dict:
        now = datetime.now()
        return {
            'price_eur': ride.get('price_eur', 0),
            'distance_km': ride.get('distance_km', 0),
            'estimated_duration_min': ride.get('estimated_duration_min', 0),
            'hourly_rate_offered': ride.get('price_eur', 0) / max(
                ride.get('estimated_duration_min', 1) / 60, 0.01),
            'pickup_zone_code': ride.get('pickup_zone_code', 'unknown'),
            'destination_zone_code': ride.get('destination_zone_code', 'unknown'),
            'payment_type': ride.get('payment_type', 'card'),
            'time_block': self._time_block(now.hour),
            # Rule features (model learns to override)
            'rule_R1_violation': int(
                ride.get('pickup_zone_code') == '75008' or
                ride.get('destination_zone_code') == '75008'
            ),
            'rule_R2_violation': int(
                ride.get('pickup_zone_code') in ['75018', '75019'] and
                10 <= now.hour < 16
            ),
            # ... all other features from §5
        }
    
    def _time_block(self, h: int) -> str:
        if 0 <= h < 6:  return 'night'
        if 6 <= h < 10: return 'morning'
        if 10 <= h < 16: return 'daytime'
        if 16 <= h < 20: return 'evening'
        return 'late_evening'
    
    def _format(self, signal, pred, triggered, source, reasoning):
        return {
            'signal': signal,
            'predicted_hourly_rate': pred,
            'score_vs_median': pred / self.median_hourly_rate if pred else None,
            'phase': self.phase,
            'source': source,
            'triggered_rules': triggered,
            'reasoning': reasoning,
            'model_version': self.metadata.get('trained_at') if self.metadata else 'rules_only'
        }
```

---

## 9. Training Pipeline

```python
# vector_model_trainer.py
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
from catboost import CatBoostRegressor
from sklearn.model_selection import KFold

class VectorRideModelTrainer:
    
    MODEL_PATH = Path("/opt/vector/models/vector_ride_model.cbm")
    META_PATH = Path("/opt/vector/models/vector_ride_model_meta.json")
    
    CAT_FEATURES = [
        'pickup_zone_code', 'destination_zone_code',
        'pickup_zone_type', 'destination_zone_type',
        'payment_type', 'platform', 'ride_type', 'ride_class',
        'time_block'
    ]
    
    async def train(self, db) -> dict:
        df = await self._load_rides(db)
        if len(df) < 50:
            return {'status': 'insufficient_data', 'n_rides': len(df)}
        
        X, y, cat_idx = self._prepare(df)
        
        # CV for accuracy estimate
        kf = KFold(n_splits=5, shuffle=True, random_state=42)
        cv_maes = []
        for tr_idx, val_idx in kf.split(X):
            cv_model = CatBoostRegressor(
                iterations=500, learning_rate=0.05, depth=6,
                cat_features=cat_idx, loss_function='RMSE',
                verbose=0, random_seed=42, min_data_in_leaf=5,
                l2_leaf_reg=3
            )
            cv_model.fit(
                X.iloc[tr_idx], y.iloc[tr_idx],
                eval_set=(X.iloc[val_idx], y.iloc[val_idx]),
                early_stopping_rounds=50, verbose=0
            )
            preds = cv_model.predict(X.iloc[val_idx])
            cv_maes.append(abs(preds - y.iloc[val_idx]).mean())
        
        mae = sum(cv_maes) / len(cv_maes)
        
        # Final model
        model = CatBoostRegressor(
            iterations=500, learning_rate=0.05, depth=6,
            cat_features=cat_idx, loss_function='RMSE',
            verbose=0, random_seed=42, min_data_in_leaf=5,
            l2_leaf_reg=3
        )
        model.fit(X, y, verbose=0)
        model.save_model(str(self.MODEL_PATH))
        
        metadata = {
            'trained_at': datetime.now().isoformat(),
            'n_rides': len(df),
            'feature_names': list(X.columns),
            'cat_features': self.CAT_FEATURES,
            'mae_cv_eur_per_hour': round(float(mae), 2),
            'median_hourly_rate': round(float(y.median()), 2),
            'feature_importance': dict(zip(
                X.columns,
                model.get_feature_importance().tolist()
            )),
            'phase': ('cold_start' if len(df) < 100
                     else 'transition' if len(df) < 500
                     else 'autonomous')
        }
        
        with open(self.META_PATH, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Register version in DB
        await db.execute("""
            INSERT INTO vector_model_versions (
                trained_at, n_training_rides, mae_cv_eur_per_hour,
                median_hourly_rate, feature_count, feature_importance,
                model_path, is_active, deployed_at
            ) VALUES (now(), %s, %s, %s, %s, %s, %s, TRUE, now())
        """, (
            len(df), mae, float(y.median()), X.shape[1],
            json.dumps(metadata['feature_importance']),
            str(self.MODEL_PATH)
        ))
        
        await db.execute("""
            UPDATE vector_model_versions
            SET is_active = FALSE
            WHERE trained_at < %s
        """, metadata['trained_at'])
        
        return metadata
```

---

## 10. WR Rule Revision Mechanism

### 10.1 Weekly high reasoning model analysis

```text
EVERY MONDAY 04:00 (after WR validation):

THE HIGH REASONING MODEL RECEIVES:
  - All rides of week
  - Each ride's: rules_triggered, model_prediction, actual_outcome
  - Aggregated per rule:
    * times_triggered_this_week
    * estimated_revenue_lost (model GREEN, rule RED)
    * estimated_revenue_saved (rule RED correctly)

THE HIGH REASONING MODEL ANALYZES PER RULE:

  EXAMPLE FOR R1 (avoid 75008):
    - Triggered 14 times this week
    - Model predicted positive €/h on 11 (78%)
    - Revenue "lost" if rule disabled: 285€
    - Revenue "saved" by rule: 12€
    - Recommendation: PROPOSE DISABLE
  
  EXAMPLE FOR R5 (night zone bonus):
    - Triggered 22 times
    - Model agreed 18 times (82%)
    - Recommendation: KEEP
```

### 10.2 User validation interface

```text
WR > Cette semaine > Révision des règles:

  ┌─────────────────────────────────────────────────────┐
  │ 💡 Proposition de révision                          │
  │                                                     │
  │ Règle R1 — Éviter 75008                             │
  │ Statut: Actif 24/7                                  │
  │                                                     │
  │ Impact cette semaine:                               │
  │ • Déclenchée 14 fois                                │
  │ • Sur 11 courses, le modèle prédisait €/h positif  │
  │   (moyenne 26€/h vs ta médiane 22€/h)              │
  │ • Coût estimé du refus systématique: 285€/sem      │
  │                                                     │
  │ Recommandation du high reasoning model:             │
  │ "Tes courses 75008 cette semaine étaient en fait    │
  │  rentables. Soit Paris a évolué, soit les hôtels    │
  │  Champs-Élysées attirent des courses longue distance.│
  │  Je propose de désactiver R1."                      │
  │                                                     │
  │ [✗ Garder la règle] [⚙️ Modifier] [✓ Désactiver]    │
  └─────────────────────────────────────────────────────┘
```

### 10.3 Override mechanics

```text
WHEN USER VALIDATES:

1. Update vector_business_rules:
   - is_active = FALSE (if disabled)
   - OR conditions_json modified (if tightened/loosened)
2. Log to vector_rule_revisions:
   - reason, proposed_by='opus_wr', user_validated=TRUE
3. Scorer reloads rules on next request
4. Future rides scored without this rule

HARD RULES (is_hard_rule=TRUE):
  Cannot be auto-revised by the high reasoning model.
  User must manually disable in Settings.
  Examples: rules user marked "always apply".
```

---

## 11. Score Logging Schema

```sql
CREATE TABLE vector_ride_score_log (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scored_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  -- Offer
  price_eur             NUMERIC(8,2) NOT NULL,
  distance_km           NUMERIC(8,2) NOT NULL,
  estimated_duration_min NUMERIC(8,2) NOT NULL,
  pickup_zone_code      VARCHAR(32),
  destination_zone_code VARCHAR(32),
  payment_type          VARCHAR(16),
  
  -- Decision
  phase                 VARCHAR(16) NOT NULL,
                        -- 'cold_start' | 'transition' | 'autonomous'
  source                VARCHAR(32) NOT NULL,
                        -- 'rules_only' | 'model' | 'rules_override' | 'hard_rule'
  signal                VARCHAR(8) NOT NULL,
  
  -- Features (full snapshot for retraining)
  feature_vector        JSONB NOT NULL,
  
  -- Predictions
  predicted_hourly_rate NUMERIC(8,2),
  score_vs_median       NUMERIC(5,3),
  triggered_rules       VARCHAR(16)[],
  model_version         VARCHAR(64),
  
  -- Outcome
  ride_accepted         BOOLEAN NULL,
  actual_ride_id        UUID NULL REFERENCES vector_ride_history(id),
  actual_hourly_rate    NUMERIC(8,2) NULL,
  prediction_error_pct  NUMERIC(8,2) NULL
);

CREATE INDEX vector_ride_score_log_time_idx
ON vector_ride_score_log (scored_at DESC);

CREATE INDEX vector_ride_score_log_rules_idx
ON vector_ride_score_log USING GIN (triggered_rules);

-- Rule performance view
CREATE VIEW vector_rule_performance AS
SELECT
  unnest(triggered_rules) AS rule_code,
  DATE_TRUNC('week', scored_at)::DATE AS week,
  COUNT(*) AS times_triggered,
  COUNT(*) FILTER (WHERE signal = 'RED') AS times_blocked,
  COUNT(*) FILTER (WHERE actual_hourly_rate IS NOT NULL) AS with_outcome,
  ROUND(AVG(actual_hourly_rate) FILTER (WHERE actual_hourly_rate IS NOT NULL), 2) AS avg_actual_hr,
  COUNT(*) FILTER (
    WHERE predicted_hourly_rate > (
      SELECT median_hourly_rate FROM vector_model_versions 
      WHERE is_active = TRUE LIMIT 1
    ) AND signal = 'RED'
  ) AS times_blocked_profitable_ride
FROM vector_ride_score_log
WHERE triggered_rules IS NOT NULL 
  AND array_length(triggered_rules, 1) > 0
GROUP BY 1, 2
ORDER BY 2 DESC, 1;
```

---

## 12. Implementation Order

```text
PHASE 1 — RULES + DATA COLLECTION (V1, week 1-2)
  ✅ vector_business_rules table
  ✅ Seed with R1-R11 from §4
  ✅ Rules-only scorer
  ✅ Log every decision to vector_ride_score_log
  ✅ Start Bolt screenshot import workflow
  ✅ Build staging review UI
  → Vector functions on RULES ONLY
  → All decisions logged
  → User imports 1-3 months Bolt history

PHASE 2 — FIRST MODEL (V1, week 3-4)
  ✅ bolt_import_processor.py operational
  ✅ bolt_import_enricher.py operational
  ✅ Train first CatBoost model on imported data
  ✅ Validate accuracy
  ✅ Deploy in 'transition' mode
  → Model assists rules
  → Weekly performance comparison

PHASE 3 — TRANSITION (V2, month 2)
  ✅ Weekly training cron
  ✅ Track vector_rule_performance view
  ✅ First WR rule revision (the high reasoning model analyzes)
  ✅ User validates/disables rules
  → Model gains autonomy

PHASE 4 — AUTONOMOUS (V2, month 3+)
  ✅ Model is primary scorer
  ✅ Rules = safety net only
  ✅ Hard rules user-flagged
  ✅ Monthly accuracy review in System Health
  → System mature
```

---

## 13. Expected Accuracy Progression

```text
RIDES   PHASE         ACCURACY    NOTES
─────────────────────────────────────────────────
< 100   cold_start    N/A         Rules only
100     transition    65-70%      First model
300     transition    72-76%      Patterns emerge
500     autonomous    78-82%      Personal thresholds
1,000   autonomous    83-86%      Time-of-day rich
3,000   autonomous    87-90%      Zone patterns mature
6,000+  autonomous    89-92%      Fully calibrated
─────────────────────────────────────────────────

WITH BOLT IMPORT BOOTSTRAP:
  Start at ~500-1000 historical rides on Day 1
  → Phase 2 in week 1-2
  → 75-80% accuracy on Day 14
  → vs 12 weeks without bootstrap

= Bootstrap saves ~3 months of low accuracy.
```

---

## 14. Cost Analysis

```text
INFRASTRUCTURE: 0€ (CPU on existing tower/VPS)
INFERENCE: 0€ (CatBoost local, <1ms)
TRAINING: 0€ (weekly cron, ~60s)

BOLT IMPORT (one-time):
├─ the OCR service: ~500-1000 screenshots × 0.001€ = 0.50-1€
├─ Open-Meteo Historical: FREE
├─ Nominatim geocoding: FREE
└─ Total bootstrap: < 2€

WR RULE REVISION (weekly high reasoning model):
└─ ~0.10€/week = 0.40€/month

EXPLANATIONS (on-demand):
├─ the local model: 0€
└─ Sonnet deep analysis: ~1€/month

TOTAL ONGOING: < 2€/month
TOTAL BOOTSTRAP: < 2€ one-time

VS QWEN (previous plan):
└─ Saves ~3€/month + 2-4s latency per ride
```

---

## 15. Non-Goals

```text
❌ Predicting demand in zones (that's WRS, doc 39)
❌ Learning from accept/decline (would learn fatigue)
❌ Cross-user federated learning (data stays personal)
❌ Deep learning / transformers (overkill)
❌ Heetch integration in V1 (waiting for stability)
❌ Real-time event scraping in V1 (V2+)
❌ Hard-coded duration multipliers (Rule R11 learned)
```

---

## 16. References

- `33_VECTOR_LOGIC_DETAIL.md` — §5.2 updated by this doc
- `30_AI_ROUTING_AND_SCORING_POLICY.md` — routing updated
- `39_WRS_VECTOR_LEARNING_LOOP.md` — zone scores feed features
- `43_IMPERIUM_LOGIC_DETAIL.md` — ai_call_logs (CatBoost calls logged)
- `52_AI_DECISION_FRAMEWORK.md` — mission scoring (separate, unchanged)

---

**Document version:** 2.0
**Status:** Vector V1 cold-start with rules + V2 ML transition
**Last updated:** 2026-05-17

---

## 17. Surge Capture & Correlation

### 16.1 Why surge data matters (the latency insight)

Bolt surge multipliers are displayed on the in-app map, but the displayed value
carries a **latency**. The multiplier shown at time T is the one captured by a
driver who was already positioned 2-3 minutes earlier — not by the driver who
arrives now. The trigger event (RER outage, rush hour onset, match ending,
sudden rain) reaches the zone before the surge color updates on the map.

```text
EVENT (e.g. RER B breakdown at 18:12)
        ↓ (latency 2-3 min)
SURGE appears on map at ~18:15 (×2.5 northern suburbs)
        ↓
Drivers already there at 18:12 catch the best fares.
Drivers seeing ×2.5 at 18:15 are already late.
```

**The strategic value is prediction:** if Vector can anticipate a surge from its
trigger event *before* it appears on the map, the driver positions ahead of the
crowd. Capturing surge history correlated to events is what makes that prediction
possible over time.

### 16.2 Why manual capture, not continuous capture

Automatic periodic screenshots were rejected for two concrete reasons:

```text
1. SCREEN CONTEXT
   Most of the time the driver is on the GPS app (Waze/Maps), NOT on Bolt.
   Automatic capture would mostly grab GPS screens, home screen, noise.

2. ZOOM LEVEL
   When Bolt is open, it is zoomed on the driver's exact position.
   The valuable view is the WIDE view (surrounding surge zones + multipliers),
   which only the driver knows when to show.
```

Manual capture, triggered by the driver, guarantees that every capture is taken
(a) while Bolt is open, (b) in wide view, (c) when surge is actually worth
recording. Zero useless data, only high-quality signal. This mirrors the proven
pattern already used for GPS/lane selection.

### 16.3 Capture mechanism: floating overlay

```text
SETTINGS:
  "Mode apprentissage majoration" toggle (off by default).

WHEN ENABLED:
  A floating bubble (Android SYSTEM_ALERT_WINDOW overlay, same tech as the
  Messenger chat-head bubble) stays on top of all apps.

ON TAP:
  → instant screenshot of the current screen
  → stored with capture timestamp (no GPS — see §16.5)
  → driver returns to driving immediately (zero friction)

WHEN DISABLED:
  Bubble disappears, no capture possible.
```

The driver taps the bubble only when the Bolt wide-view map shows a surge worth
recording. One tap, no form, no interruption to driving.

### 16.4 Deferred OCR extraction (the OCR service)

Capture stores only the raw image + timestamp on the spot. Interpretation is
**deferred** and done at rest, following the same model as the Bolt history
import (§7): capture → the OCR service → user review → clean data.

```text
AT REST (evening, or batch validation session):
  Each surge screenshot → the OCR service
  → reads the ENTIRE map: every surge zone + its multiplier
  → produces structured JSON per zone

  User reviews the extraction (corrects OCR errors)
  → confirmed data written to surge tables
```

The OCR service extraction target (whole-map reading):

```text
For each visible surge zone on the captured map:
  - zone label / approximate area (postal code or named area if legible)
  - surge multiplier (e.g. 1.5, 2.0, 2.5)
  - surge color (maps to intensity if number not legible)
  - relative position / extent if determinable
```

### 16.5 What is captured (and what is not)

```text
✅ Captured:
   - raw screenshot (Bolt wide-view surge map)
   - capture timestamp (the correlation key)

❌ NOT captured:
   - GPS position
     Reason: for a WIDE-view surge map, the driver's exact position adds nothing.
     The map itself shows the zones; GPS could even mislead (driver is "here"
     but the relevant surge is 3km away). Timestamp alone is the correlation key.
```

### 16.6 Storage

```sql
-- Raw surge captures (manual, via overlay)
CREATE TABLE vector_surge_captures (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  captured_at        TIMESTAMPTZ NOT NULL,        -- correlation key
  screenshot_uri     TEXT NOT NULL,               -- encrypted at rest
  platform           VARCHAR(16) NOT NULL DEFAULT 'bolt',
  ocr_status         VARCHAR(24) NOT NULL DEFAULT 'pending',
                     -- pending | extracted | needs_review | validated | failed
  gemini_raw         JSONB NULL,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Per-zone surge readings extracted from a capture (after OCR + validation)
CREATE TABLE vector_surge_zone_readings (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  capture_id         UUID NOT NULL REFERENCES vector_surge_captures(id) ON DELETE CASCADE,
  user_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  captured_at        TIMESTAMPTZ NOT NULL,        -- denormalized for fast querying
  zone_label         VARCHAR(64) NULL,            -- postal code or named area
  surge_multiplier   NUMERIC(4,2) NULL,           -- e.g. 2.50
  surge_color        VARCHAR(24) NULL,            -- fallback if number illegible
  confidence         NUMERIC(3,2) NULL,
  user_validated     BOOLEAN NOT NULL DEFAULT FALSE,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX vector_surge_zone_readings_time_idx
ON vector_surge_zone_readings (captured_at DESC);

CREATE INDEX vector_surge_zone_readings_zone_idx
ON vector_surge_zone_readings (zone_label, captured_at DESC);
```

### 16.7 How surge data feeds the scoring

The surge history serves **two distinct purposes**, both downstream of the
CatBoost architecture (not a replacement for it):

```text
PURPOSE A — Enrich existing ride-scoring features (§5)
  The §5.1 feature surge_multiplier already exists at ride-offer time.
  Surge history adds richer derived features:
    - zone_surge_recent_avg        (avg multiplier in this zone, last N min)
    - zone_surge_trend             (rising / flat / falling over last 10 min)
    - zone_surge_at_similar_time   (historical surge for this zone/time-block)

PURPOSE B — Feed a future surge-PREDICTION model (separate from ride scoring)
  Correlating captured surge (timestamped) with trigger events lets Vector
  learn to anticipate surge BEFORE it appears on the map (the §16.1 insight).
  This is a separate modeling track; surge captures are its training data.
```

### 16.8 Event correlation

The capture timestamp is the join key to external trigger events:

```text
Surge reading (captured_at = 18:14, northern suburbs, ×2.5)
        ⨝ on time window
External events around 18:12-18:14:
  - RER B disruption active        (doc 5.6 ratp_disruption_rer_active)
  - rush hour (evening peak)
  - weather (rain onset)
  - nearby event ending

→ Over many captures, Vector learns which events precede which surges,
  in which zones, with what delay → predictive positioning.
```

The external-signal features needed here already align with §5.6
(transport disruptions, events, weather). The surge captures provide the
**labels** (what actually surged, where, when) that those event features
predict.

### 16.9 V1 vs later

```text
V1 (now):
  - overlay capture + timestamp
  - deferred OCR service extraction (whole map) + user validation
  - store surge zone readings
  - expose enrichment features (Purpose A) to CatBoost as data accumulates

LATER:
  - dedicated surge-prediction model (Purpose B)
  - real-time event ingestion for live anticipation
  - automatic zone-label normalization
```

---

### 17.1 Feature reference (applied in §5.6)

> RÉSOLU (Patch 33-A) : dans la sous-section **§5.6 External signals (V2 — to
> add)**, sous le bloc `TRANSPORT DISRUPTIONS` / `EVENTS`, la note suivante a
> été ajoutée :

```text
SURGE HISTORY (from manual captures — see §16):
├─ zone_surge_recent_avg        — avg surge multiplier in zone, last N min
├─ zone_surge_trend             — rising | flat | falling (last 10 min)
└─ zone_surge_at_similar_time   — historical surge for this zone + time_block
```
