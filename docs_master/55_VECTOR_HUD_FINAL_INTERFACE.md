# 55 - Vector HUD Final Interface (V6+)

> ⚠️ **V6+ feature — the ultimate Vector evolution.**
> The map becomes the primary interface. Everything else 
> becomes a contextual overlay or slide-up panel.
> DO NOT START before V1 through V5 are stable.

---

## 1. Purpose

This document captures the **endgame vision** for Vector: transforming the app from a traditional list/dashboard UI into a **map-centric HUD** (Heads-Up Display) optimized for VTC drivers.

The map is no longer a feature inside Vector.
The map IS Vector.

Everything else (missions, stats, settings, history) becomes a contextual overlay or a slide-up panel from the bottom of the screen.

---

## 2. Why V6+ And Not Earlier

```text
V1-V2 — Vector foundations, sessions, fuel, basic dashboard
V3-V5 — All other ecosystem features stabilized

V6+ — When everything else works reliably, Vector can evolve 
      into its final form: the HUD.

This requires:
- Stable Vector core (sessions, recommendations, halo logic)
- Mature WRS learning loop (heatmap quality)
- All ecosystem features working (Path mosques, Vault fuel, etc.)
- User has clear sense of what they need geographically

DO NOT START THIS BEFORE V5 IS PROVEN.
```

---

## 3. Core Insight

```text
A VTC DRIVER LIVES IN SPACE, NOT IN LISTS.

Their decisions are geographical:
- "Where are the customers right now?"
- "Where is my next prayer happening?"
- "Where should I refuel?"
- "Where is the event ending in 1 hour?"

Traditional UIs (lists, menus, tabs) force the driver to 
TRANSLATE their geographical thinking into navigation through 
abstract menus.

The HUD eliminates that translation.
Everything that matters is shown WHERE it matters.

This is the natural evolution of Vector for its core user.
```

---

## 4. The HUD Always-On Principle

```text
THE HUD IS ACTIVE 100% OF THE TIME.

Not only during VTC sessions.
Also during planning, during evenings, during off-duty hours.

WHY:
- The user wants to PLAN before starting a session
- "What does today look like, geographically?"
- "Where are the events tomorrow?"
- "When is the next big aviation arrival?"

The HUD lets the user understand their environment 
BEFORE they hit the road, not just during driving.

This makes Vector a strategic tool, not just a tactical one.
```

---

## 5. The Two Display Modes

The HUD adapts its display based on user activity.

### 5.1 STANDBY mode (not currently navigating)

```text
TRIGGER: No active route in progress, user is exploring/planning.

DISPLAY:
- Centered on user position
- 50 km diameter view
- All overlays visible per user preferences
- User can pan/zoom freely
- Tap on overlays for details
- Used for planning the day

WHY 50 KM:
- Captures user's typical operational radius
- VTC trips rarely exceed 50 km in IDF
- Shows enough context for planning without zooming in/out
- Single glance gives the geographic picture of the day
```

### 5.2 NAVIGATION mode (active route)

```text
TRIGGER: User is actively driving a route (VTC or personal).

DISPLAY:
- Zoom level dynamic based on speed
- High speed (>70 km/h): zoom out, see ahead
- Medium speed (40-70 km/h): standard zoom
- Low speed (<40 km/h): zoom in, see immediate surroundings
- Camera follows direction of travel
- Camera ahead of user (perspective view possible)
- Less overlay clutter (focus on safety)
- Critical overlays only (next instruction, hazards)

WHY DYNAMIC ZOOM:
- High speed = need to see further ahead
- Low speed (city traffic) = need detail
- Reduces cognitive load
- Standard practice in modern GPS apps
```

### 5.3 Mode switching

```text
Automatic detection:
- Speed > 5 km/h continuously for 30s → NAVIGATION mode
- Speed < 5 km/h for 60s → STANDBY mode
- User taps explicit "Stop navigation" → STANDBY mode

Manual override:
- User can pin mode (lock STANDBY even while driving)
- Used for: passenger viewing, planning mid-trip
```

---

## 6. The Overlay System

The HUD's power comes from its overlays. Each overlay represents a layer of contextual information on the map.

### 6.1 The 8 planned overlays

```text
1. 🔥 ZONES CHAUDES (Heatmap)
   Color-coded zones showing predicted profitability.
   Data: Bolt patterns + WRS learning (doc 39)
   Update: every 5 minutes
   
2. ✈️ AVIATION (Aircraft tracking)
   Approaching aircraft to Roissy / Orly
   Shows ETA and aircraft origin
   Helps anticipate airport runs
   Data: AeroAPI / FlightRadar24
   Update: every 1 minute

3. 🎵 ÉVÉNEMENTS LIVE
   Concerts, sports, manifestations
   Shows venue + event end time
   Visual: ripples/waves from venue (impactful)
   Data: events_calendar (doc 33)
   Update: at scan + every hour

4. ⛽ STATIONS ESSENCE
   With real-time prices
   Smart fuel recommendations
   Data: CarbuRoi API or similar
   Update: every 30 minutes

5. 🕌 MOSQUÉES
   With next prayer countdown
   Color-coded urgency
   Data: MAWAQIT (doc 41)
   Update: per prayer schedule

6. 🚀 RACCOURCIS PERSO
   User-saved shortcuts (parking traversées, voies bus)
   Subtle visual (semi-transparent)
   Activatable when user passes near

7. 📍 POSITION USER
   Current location with bearing
   Recent trajectory trail (last 5 min)
   Halo color (per Vector overlay logic, doc 33)

8. 🛣️ LANE OPTIMIZATION (Apprentissage des voies)
   Predictive lane recommendations on highways and rapid roads.
   System learns which lane is fastest per highway segment
   over time, based on user-tagged lane positions.
   Data: OSM highway metadata + user observations
   Toggle: enabled/disabled in Settings
   See Section 9.8 for full details.
```

### 6.2 User control over overlays — the side panel

A persistent dropdown panel sits on the RIGHT side of the map, acting as a legend + control center for all overlays.

```text
LOCATION: right edge of HUD (collapsible)
STYLE: accordion (only one category expanded at a time)
ACCESS: tap [≡] icon to open/close

WHEN OPEN, displays each overlay category as a collapsible section:
```

```text
┌─────────────────────────────────────┐
│ AFFICHAGE DES OVERLAYS              │
│                                     │
│ ▼ 🔥 Zones chaudes                  │
│   ┌─────────────────────────────┐   │
│   │ Quand afficher:             │   │
│   │ ⚫ Tout le temps             │   │
│   │ ⚪ En conduite seulement     │   │
│   │ ⚪ En mode standby seulement │   │
│   │ ⚪ Ne pas afficher           │   │
│   │                             │   │
│   │ [Tout sélectionner]          │   │
│   │ [Tout désélectionner]        │   │
│   │                             │   │
│   │ Items individuels:          │   │
│   │ ☑ Châtelet                  │   │
│   │ ☑ La Défense                │   │
│   │ ☐ Saint-Denis               │   │
│   │ ☑ Roissy                    │   │
│   └─────────────────────────────┘   │
│                                     │
│ ▶ ✈️ Aviation                       │
│ ▶ 🎵 Événements                     │
│ ▶ ⛽ Stations essence               │
│ ▶ 🕌 Mosquées                       │
│ ▶ 🚀 Raccourcis perso               │
│ ▶ 🛣️ Apprentissage voies           │
│ ▶ 🚉 Transports en commun           │
│ ▶ 🚧 Accidents/pannes               │
└─────────────────────────────────────┘
```

#### 6.2.1 The 4-option display filter (per category)

```text
EACH OVERLAY CATEGORY has 4 mutually exclusive display modes:

1. TOUT LE TEMPS
   Category visible in both standby AND navigation modes.
   Use for: critical info user always wants (e.g., prayers)

2. EN CONDUITE SEULEMENT
   Category visible only during active navigation.
   Hidden during standby planning.
   Use for: tactical info (e.g., real-time lane recommendations)

3. EN MODE STANDBY SEULEMENT
   Category visible only when planning, not while driving.
   Hidden during navigation.
   Use for: strategic info that would distract while driving
            (e.g., aviation tracking when planning sessions)

4. NE PAS AFFICHER
   Category completely hidden.
   Use for: categories the user doesn't care about
```

#### 6.2.2 Per-item selection within categories

```text
Each category has INDIVIDUAL ITEMS that can be toggled:

EXAMPLE — Public Transport Issues category:
  Display filter: Tout le temps
  Items:
    ☑ Panne RER A
    ☐ Panne RER B  ← user doesn't care
    ☑ Grève SNCF
    ☑ Travaux Métro 14
    [Tout sélectionner] [Tout désélectionner]

WHY THIS GRANULARITY:
- User cares about RER A (drives passengers there often)
- Doesn't care about RER B (rarely relevant)
- Wants to see SNCF strikes (impacts all clients)
- "Tout sélectionner" reset button for safety
```

#### 6.2.3 Preferences storage

```text
PREFERENCES STORED in vector_hud_preferences:
- Per-category display filter (1 of 4 modes)
- Per-category individual item toggles
- Per-category-item visibility

REMEMBERED between sessions.
EXPORTABLE/IMPORTABLE for backup.

DEFAULT STATE (first use):
- Position + Raccourcis: "Tout le temps"
- Zones chaudes + Mosquées: "Tout le temps"
- Events + Aviation: "En mode standby seulement"
- Lane Optimization: "En conduite seulement"
- Others: "Ne pas afficher" (user enables progressively)
```

### 6.3 Overlay interaction patterns

```text
TAP on overlay marker:
  Opens small info card at top of screen
  - For heatmap: zone stats + reasons
  - For aircraft: flight details + ETA
  - For event: venue + audience + end time
  - For station: prices + distance + route
  - For mosque: next prayer + Mawaqit times
  - For shortcut: usage tips + activation hint

LONG PRESS on overlay:
  Quick action menu
  - "Hide for 1h"
  - "Set as destination"
  - "Add to favorites"
  - "Get directions"

DOUBLE TAP on map (empty area):
  Quick "What's here?" lookup
  Shows nearby POIs across all enabled overlays
```

---

## 7. The Persistent UI Elements

While the map dominates, some elements are always visible.

### 7.1 Top bar (minimal, contextual)

```text
LEFT:
  - Current time
  - Next prayer countdown (small)

CENTER:
  - Active session status (if any)
  - "Session: 285€ • 3h32"

RIGHT:
  - Energy/fatigue indicator (small icon)
  - Network status (if relevant)
```

### 7.2 Bottom bar (action shortcuts)

```text
4 main buttons, always visible:

[🎯 Mission]  [📊 Stats]  [⚙️ Settings]  [📡 Tools]

Tap → slides up the corresponding panel
The map stays visible behind, dimmed slightly
Swipe down to dismiss the panel
```

### 7.3 Slide-up panels

```text
The traditional Vector UI lives in these slide-up panels:

MISSION PANEL:
- Current focus mission
- Mission backlog
- Submissions
- Mission detail views

STATS PANEL:
- Today's revenue
- Week summary
- Pressure score
- Performance trends

SETTINGS PANEL:
- All Vector settings
- HUD overlay preferences
- Notification settings

TOOLS PANEL:
- Music shaker (doc 48)
- Smart fuel (doc 46)
- WR access
- Other Vector tools
```

This way, the map is ALWAYS the primary view. Other UI is accessible but never intrusive.

---

## 8. Technical Architecture

### 8.1 The stack

```text
BACKEND (VPS):
├─ Valhalla (open source routing engine)
│   ├─ OSM data Île-de-France (~500 MB)
│   └─ Custom costing for user shortcuts
│
├─ Tile server
│   ├─ Option A: MapTiler (paid SaaS)
│   ├─ Option B: TileServer GL (self-hosted)
│   └─ Renders map tiles to app
│
├─ External APIs:
│   ├─ TomTom Traffic API (flow + incidents)
│   ├─ FlightRadar24 / AeroAPI (aviation)
│   ├─ Events API (manual or 3rd party)
│   ├─ CarbuRoi or similar (fuel prices)
│   └─ MAWAQIT (already in Path)
│
└─ Backend services:
    ├─ /api/v1/vector/hud/heatmap (compute zones)
    ├─ /api/v1/vector/hud/aviation
    ├─ /api/v1/vector/hud/events
    ├─ /api/v1/vector/hud/stations
    ├─ /api/v1/vector/hud/mosques
    └─ /api/v1/vector/hud/route (Valhalla + TomTom)

FRONTEND (Android):
├─ MapLibre Native SDK (open source, free)
│   ├─ Renders map tiles
│   ├─ Renders custom overlays
│   ├─ Camera control
│   └─ Touch interactions
│
├─ Overlay manager
│   ├─ Per-overlay rendering logic
│   ├─ Visibility toggling
│   └─ Performance optimization
│
└─ State management
    ├─ Mode (standby / navigation)
    ├─ Active overlays
    └─ Camera state
```

### 8.2 Why this stack

```text
VALHALLA:
- Open source, free
- Self-hosted (privacy)
- Custom costing supported
- Active development
- Handles personal shortcuts natively

MAPLIBRE:
- Fork of Mapbox (open source)
- Native performance
- Battle-tested
- Great for overlays
- No vendor lock-in

TOMTOM:
- Best free tier for traffic
- Reliable incidents data
- Good Paris coverage
- ~7€/month worst case

OSM DATA:
- Free, open
- Comprehensive IDF
- Updated weekly by community
- Modifiable for personal shortcuts
```

---

## 9. Data Sources Per Overlay

### 9.1 Heatmap (zones chaudes)

```text
SOURCES:
├─ Vector ride history (last 30 days)
│   Aggregated by zone (1km² grid)
├─ WRS learning patterns (doc 39)
│   Time-weighted profitability
├─ Real-time event proximity
│   Boost zones near active events
└─ Day-of-week + hour patterns

COMPUTATION:
- Background job every 5 minutes
- Caches result for the next 5 minutes
- Returns: grid of (lat, lon, score, color)

COST: 0€ (deterministic SQL queries)
```

### 9.2 Aviation tracking

```text
SOURCES:
├─ AeroAPI (FlightAware) — best precision
└─ OR FlightRadar24 API — alternative

QUERY:
- Bbox: Île-de-France area + buffer
- Filter: aircraft descending below 10,000 ft
- Heading: toward Roissy or Orly

DISPLAY:
- Aircraft icon at current GPS position
- Trail showing recent trajectory
- Tap → ETA, origin, aircraft type

UPDATE: every 60 seconds
COST: ~10-20€/month for AeroAPI
       FlightRadar24 has cheaper tiers
```

### 9.3 Events live

```text
SOURCES:
├─ events_calendar (Vector existing, doc 33)
│   Already populated by event scan
└─ Manual additions by user

DISPLAY:
- Venue icon at GPS position
- Animated "wave" effect (audio-visual metaphor)
- Wave size = audience size
- Wave intensity = time until event ends
- Tap → details

UPDATE: at every event_scan + every hour
COST: 0€ (already in Vector)
```

### 9.4 Stations essence

```text
SOURCES:
├─ CarbuRoi (free API, France)
└─ OR Gouvernement France API (prix-carburants.gouv.fr)

DISPLAY:
- Station icons
- Color by price (green = cheap, red = expensive)
- Smart fuel recommendation badge if applicable
- Tap → prices for all fuel types

UPDATE: every 30 min
COST: 0€ (free APIs available)
```

### 9.5 Mosquées

```text
SOURCES:
├─ MAWAQIT (already in Path, doc 41)
│   For mosques user has registered
└─ Wikidata / OSM
    For other mosques in zone

DISPLAY:
- Mosque icon
- Color-coded next prayer urgency:
  Green: >2h until prayer
  Yellow: 30 min - 2h
  Orange: 5-30 min
  Red: <5 min
- Tap → MAWAQIT detail (if registered)

UPDATE: per prayer schedule
COST: 0€
```

### 9.6 Raccourcis perso

```text
SOURCES:
└─ User-added shortcuts (stored in DB)
    - Entry point GPS
    - Exit point GPS
    - Estimated time gain
    - Usage context (hours, days)

DISPLAY:
- Semi-transparent line connecting entry → exit
- Subtle icon at entry point
- Activates: when user passes within 100m of entry
  → notification "Raccourci dispo: gain ~3 min"

UPDATE: on user action (add/edit/delete)
COST: 0€
```

### 9.7 Position user

```text
SOURCES:
└─ Android Location API (GPS sensor)

DISPLAY:
- Arrow icon showing heading
- Halo color = Vector overlay state (per doc 33)
- Trail: last 5 minutes of movement
- Optional: time stamps on trail

UPDATE: continuous (every 1-2 seconds)
COST: 0€
```

### 9.8 Lane Optimization (Apprentissage des voies)

This overlay is the most distinctive feature of the HUD. It enables progressive learning of which highway lane is fastest per segment AND per destination, based on user observations during real traffic jams.

#### 9.8.1 The core insight

```text
On highways during congestion, lane choice can save significant 
time. Patterns are remarkably stable per highway segment AND 
per destination:

- Entry/exit positions create predictable speed differentials
- The best lane depends on WHERE YOU'RE GOING
  (A6 splitting into A6A vs A6B = different optimal lanes)
- Truck lanes vs passing lanes have consistent behaviors
- Time-of-day patterns repeat (rush hour, etc.)

The user often knows some of these intuitively but cannot 
remember all of them perfectly. The system captures and 
returns this knowledge progressively.

CRITICAL NUANCE — DESTINATION AWARENESS:
Since the HUD is the user's GPS, it always knows the active 
destination (from the Bolt course or user input). Lane patterns 
are learned and recommended PER (segment + destination branch) 
combination, not just per segment.

ESTIMATED VALUE:
- 5-15 minutes saved per 1-hour highway trip in heavy traffic
- Significant over weeks of VTC operations
```

#### 9.8.2 OSM data extraction

```text
OSM PROVIDES THE LANE COUNT for highways and rapid roads:

Relevant tags:
- "highway" = "motorway" | "trunk" | "primary" (filterable)
- "lanes" = total lane count (e.g., "3")
- "lanes:forward" = lanes in direction of travel
- "lanes:backward" = opposite direction lanes
- "lanes:psv" = restricted lanes (bus/taxi)
- "ref" = road identifier (A6, A86, etc.)

EXTRACTION QUALITY in Île-de-France:
- Motorways: 95%+ tagged correctly
- Trunk roads: 90%+ tagged
- Primary roads: 80%+ tagged
- Secondary: variable, less reliable

THIS DATA IS USED:
- To know how many lanes to display in the popup
- To filter: only enable feature on roads with lanes >= 2
- To map user observations to lane numbers
```

#### 9.8.3 Activation flow (two-tier)

```text
TIER 1 — GLOBAL TOGGLE (Settings):

Vector > Settings > Apprentissage des voies:
  [OFF] / [ON]  "Apprentissage actif"

When OFF:
  - No popup ever appears
  - No observations recorded
  - Existing patterns still usable for recommendations
  
When ON:
  - Popup appears whenever on highway with lanes >= 2
  - Popup persistently displays current possible lanes
  - User can still choose NOT to record (see Tier 2)

TIER 2 — PER-SESSION RECORDING (Popup button):

The popup itself has a "Démarrer l'enregistrement" button.
This decoupling exists because:
- The system can't reliably detect "real congestion"
  (a small slowdown doesn't justify lane analysis)
- The user knows when traffic is genuinely jammed
- The user wants to control WHEN data is collected

User flow:
1. User goes to Settings, toggles "Apprentissage" ON
2. User starts driving
3. User enters highway → popup appears top-right
4. Lane buttons visible but inactive (waiting for record start)
5. User encounters real traffic jam
6. User taps "Démarrer l'enregistrement"
7. Lane buttons become active
8. User taps their current lane → recording begins
9. Each lane change → new tap, new record
10. User taps "Arrêter l'enregistrement" when jam clears
11. Or system auto-stops when speed returns to normal
```

#### 9.8.4 The popup UI

```text
THE POPUP STATES:

STATE 1 — Highway detected, recording NOT started:
┌─────────────────────────────┐
│ 🛣️ A6 vers Paris            │ ← context info
│                             │
│  [1]  [2]  [3]              │ ← buttons (greyed out)
│                             │
│ [▶ Démarrer l'enregistrement]│
└─────────────────────────────┘

STATE 2 — Recording active, no lane selected yet:
┌─────────────────────────────┐
│ 🔴 Enregistrement actif      │
│                             │
│  [1]  [2]  [3]              │ ← buttons (active, none selected)
│                             │
│ Tape ta voie actuelle       │
│ [■ Arrêter]                 │
└─────────────────────────────┘

STATE 3 — Recording active, lane 2 selected:
┌─────────────────────────────┐
│ 🔴 Enregistrement actif      │
│                             │
│  [1]  [✓2]  [3]             │ ← lane 2 highlighted
│                             │
│ Vitesse moyenne: 12 km/h    │
│ [■ Arrêter]                 │
└─────────────────────────────┘

LANE NUMBERING CONVENTION (user preference):
- Lane 1 = leftmost (fast lane in France)
- Lane 2 = middle on 3-lane / right on 2-lane
- Lane 3 = rightmost on 3-lane
- Lane 4 = rightmost on 4-lane (rare)

POSITION: top-right of HUD
SIZE: ~15% of screen width
SAFETY:
- Buttons are large enough for safe tapping
- High contrast for visibility while driving
- Tap latency minimal (no animations)
```

#### 9.8.5 Auto-detection rules

```text
WHEN THE POPUP APPEARS:

Rule 1: User has enabled "Apprentissage" in Settings
Rule 2: User is on highway (highway = motorway | trunk | primary)
Rule 3: Lane count from OSM >= 2

If all three: popup visible
If any false: popup hidden

WHEN RECORDING AUTO-STOPS (optional, configurable):

Option A — User-controlled (default)
  Recording continues until user taps "Arrêter"

Option B — Auto-stop when speed returns to normal
  If avg speed last 60s > 70% of free-flow speed:
    Recording pauses automatically
    User can manually resume
    
Option C — Auto-stop when leaving segment
  If user exits the highway:
    Recording stops
    
Default: A (user-controlled), with B/C as Settings options.
```

#### 9.8.6 Destination-aware learning

```text
THE CRITICAL INNOVATION:

Each observation is logged with:
- segment_id (where on the highway)
- lane_number (which lane)
- destination_segment_id (where the user is going)
- observed_speed_kmh
- timestamp + context

WHEN COMPUTING PATTERNS:
Group observations by (segment_id, destination_branch, time_window, weekend)

EXAMPLE:
On A6 north before split:
- 10 observations going to A6A: lane 1 averages 25 km/h
- 10 observations going to A6A: lane 2 averages 35 km/h  
- 10 observations going to A6A: lane 3 averages 30 km/h
  → For A6A destination: lane 2 recommended (+17% vs lane 3)
  
- 8 observations going to A6B: lane 1 averages 40 km/h
- 8 observations going to A6B: lane 2 averages 30 km/h
- 8 observations going to A6B: lane 3 averages 20 km/h
  → For A6B destination: lane 1 recommended (+33% vs lane 2)

HOW DESTINATION IS KNOWN:
- Active Bolt course: pickup/dropoff address → route → known
- Manual GPS destination entered: → route → known
- No destination set: recommendation skipped for this trip
  (still records observations against most-recent-route or null)
```

#### 9.8.7 The recommendation display

```text
WHEN PATTERNS ARE RELIABLE AND DESTINATION KNOWN:

As user approaches a known segment, banner appears:

┌────────────────────────────────────────┐
│ 💡 Voie 2 recommandée (vers A6A)       │
│ +18% rapide (basé sur 24 passages)     │
└────────────────────────────────────────┘

CONDITIONS FOR DISPLAY:
- Reliable pattern (>= 10 observations on this segment+destination)
- Significant improvement (>= 10% speed gain)
- Time-of-day match (same hour window as patterns)
- Destination is known (Bolt course or manual)
- User not currently changing lanes

POSITIONING:
- Top-center of HUD (not the lane popup which is top-right)
- Disappears after 30 seconds
- Disappears immediately if user follows recommendation
- Disappears if traffic conditions change
```

#### 9.8.8 The learning algorithm

```text
DATA FLOW:

1. RECORDING (when user is tagging lanes)
   Every 5 seconds while in active recording:
   - Capture: lat/lng, speed, current_lane (last tap), timestamp
   - Identify highway_segment (spatial query)
   - Identify destination_branch (from active route)
   - Insert into highway_lane_observations

2. AGGREGATION (nightly cron at 03:00)
   For each (segment, destination_branch) with new observations:
   - Group by lane, time_window, weekday/weekend
   - Compute avg + median speeds
   - Compute confidence (samples / 30, max 1.0)
   - Upsert into highway_lane_patterns

3. RECOMMENDATION (real-time lookup)
   When user approaches a segment:
   - Match (segment, destination, time_window, weekend)
   - Get all lane patterns for this context
   - Find fastest lane
   - Compute improvement % vs next-best lane
   - If criteria met: surface recommendation

ADAPTIVE FORGETTING:
- Observations older than 6 months get half weight
- Patterns recomputed nightly
- Construction zones naturally adapt over time
- User can manually reset all patterns (Settings)
```

#### 9.8.9 Settings configuration

```text
Vector > Settings > Apprentissage des voies:

┌────────────────────────────────────────────┐
│ 🛣️ APPRENTISSAGE DES VOIES                 │
│                                            │
│ [ON]  Apprentissage actif                  │
│   (le popup apparaît sur autoroute)        │
│                                            │
│ État actuel:                               │
│ • 1,247 observations collectées            │
│ • 28 segments × destinations avec patterns │
│ • Confiance moyenne: 67%                   │
│                                            │
│ ☑ Afficher recommandations                  │
│   (montre les voies recommandées)          │
│                                            │
│ Arrêt automatique de l'enregistrement:      │
│ ⚫ Manuel uniquement (défaut)              │
│ ⚪ Auto-stop quand trafic redevient fluide │
│ ⚪ Auto-stop en sortant de l'autoroute     │
│                                            │
│ [Voir les patterns appris]                  │
│ [Réinitialiser les données apprises]        │
└────────────────────────────────────────────┘
```

#### 9.8.10 Privacy and data ownership

```text
ALL DATA STORED LOCALLY ON USER VPS:
- Never shared with third parties
- Never aggregated across users
- User can export observations as JSON
- User can reset all data anytime

OSM DATA: open source, no privacy implications
USER OBSERVATIONS: 100% local, 100% private
```

#### 9.8.11 Cost analysis

```text
DATA STORAGE:
- ~12 observations per highway km (every 5s at 80km/h)
- Recording only during active jams: ~10-30% of highway time
- Yearly: ~20,000-50,000 observations
- ~5-15 MB in PostgreSQL annually
- Negligible storage cost

COMPUTATION:
- Real-time: simple INSERT, < 10ms
- Aggregation: nightly cron, ~30 seconds
- Recommendation: indexed lookup, < 50ms
- No AI calls needed (deterministic algorithm)

ANNUAL COST: 0€
```

#### 9.8.12 Limitations and honest caveats

```text
WHAT THIS SYSTEM CAN'T DO:

1. AUTOMATIC JAM DETECTION
   System can't reliably know if a small slowdown 
   justifies analysis. User decides via tap.

2. WEATHER ADAPTATION (V8.5+)
   Rain changes patterns significantly.
   Initial version doesn't track weather context.

3. INCIDENT-DRIVEN PATTERNS
   Accidents are unpredictable.
   System sees them as noise (eventually fade).

4. CONSTRUCTION ZONES
   New lane configurations confuse patterns.
   User must manually reset affected segments.

5. PERFECT LANE DETECTION
   GPS precision ±3-5m vs lane width 3.5m.
   System relies on user input, not auto-detect.

6. UNFAMILIAR ROADS / DESTINATIONS
   First use: no data, no recommendations.
   Learning phase: 10-20 tagged trips needed for reliable patterns.

THESE LIMITATIONS ARE ACCEPTABLE because:
- The system provides value EVEN WITH them
- Improvements come naturally over time
- Settings toggle gives user full control
- Manual recording trigger ensures data quality
```

---

## 10. Roadmap By Phases

This vision implementation is split into phases for tractability.

### Phase V6.0 — GPS foundation (~6 weeks)

```text
GOAL: Basic working GPS with shortcuts

DELIVERABLES:
├─ Valhalla self-hosted on VPS
├─ OSM IDF imported
├─ MapLibre SDK in Android app
├─ Map displayed (no overlays yet)
├─ Routes calculated for Bolt pickups
├─ User shortcuts addable + integrated in routing
├─ TomTom traffic integrated
└─ Basic navigation (no voice)

USABLE: minimally, alongside existing apps
```

### Phase V6.5 — First overlay: Heatmap (~3 weeks)

```text
GOAL: Show profitability heatmap

DELIVERABLES:
├─ Backend heatmap computation
├─ Frontend heatmap rendering
├─ Refresh every 5 min
├─ Tap → zone details
└─ User can toggle on/off

USABLE: real value for planning sessions
```

### Phase V7.0 — Mosques + Stations (~3 weeks)

```text
GOAL: Religious + fuel awareness on map

DELIVERABLES:
├─ Mosques overlay with countdown
├─ Stations overlay with prices
├─ User preferences per overlay
└─ Performance optimization (multiple overlays)

USABLE: ecosystem becomes spatial
```

### Phase V7.5 — Events overlay (~2 weeks)

```text
GOAL: Live events on map

DELIVERABLES:
├─ Visual wave effect for events
├─ Tap → event details
└─ Integration with events_calendar

USABLE: anticipation of demand spikes
```

### Phase V8.0 — Aviation + Lane Optimization (~5 weeks)

```text
GOAL: Aircraft visualization + lane learning system

DELIVERABLES — Aviation:
├─ AeroAPI / FR24 integration
├─ Aircraft icons + trails
├─ ETA computations
├─ Filter by airport (Roissy / Orly)
└─ Cost optimization (caching)

DELIVERABLES — Lane Optimization:
├─ OSM lane data extraction (already in V6.0)
├─ Highway segment detection
├─ Popup UI with adaptive lane count
├─ Observation recording service
├─ Nightly aggregation cron
├─ Recommendation display logic
├─ Settings toggle (3 modes)
└─ Reset functionality

USABLE: airport runs + lane recommendations operational
```

### Phase V8.5 — Polish (~4 weeks)

```text
GOAL: Production-grade experience

DELIVERABLES:
├─ Day / Night map themes
├─ Animation refinements
├─ Performance profiling
├─ Battery optimization
├─ Filter UI for each overlay
└─ Beta testing on real sessions

USABLE: the HUD is your new primary interface
```

```text
TOTAL ESTIMATED: ~22 weeks (~5-6 months) of dev work
```

---

## 11. Cost Analysis

```text
ONE-TIME COSTS:
├─ VPS upgrade (KVM 4 → KVM 8 for RAM): +15€/month ongoing
├─ Initial setup time: ~22 weeks dev (your time)
└─ No upfront fees (all FOSS / free tiers)

ONGOING COSTS (monthly):
├─ TomTom Traffic API: 0-7€ (free tier likely sufficient)
├─ AeroAPI (aviation): 10-30€ depending on tier
├─ Tile server (if self-hosted): 0€
├─ CarbuRoi: 0€ (free)
├─ MAWAQIT: 0€ (already integrated)
└─ TOTAL: ~15-40€/month

ANNUAL COST: ~250-500€/year
PER MONTH: ~25-40€/month with VPS upgrade

= Trivial compared to value for daily VTC use.
```

---

## 12. Resource Requirements (VPS)

```text
CURRENT VPS (KVM 4 — 16 GB RAM):
├─ PostgreSQL: ~2 GB
├─ n8n + Imperium API: ~2 GB
├─ Qwen 2.5 7B: ~6 GB
└─ Available: ~6 GB

NEW STACK ADDITIONS (V6+):
├─ Valhalla: ~4 GB RAM (IDF data loaded)
├─ Tile server (if self-hosted): ~1-2 GB
├─ Additional services: ~1 GB
└─ NEW TOTAL: ~6-7 GB extra needed

UPGRADE PATH:
KVM 4 (16 GB) → KVM 8 (32 GB)
├─ Cost: +15€/month (~30€ → ~45€/month)
├─ Provides ample headroom
├─ Future-proof for V7+ additions
└─ Recommended once V6 starts

INCREMENTAL APPROACH:
- Stay on KVM 4 during Phase V6.0 (test with limited data)
- Upgrade to KVM 8 when adding multiple overlays
- Plan budget accordingly
```

---

## 13. Why This Vision Is Right

```text
The HUD vision aligns perfectly with:

1. THE BRAIN UNIFIED (doc 44)
   The map is the visual manifestation of the brain.
   Everything spatial is shown in space.
   No translation between data and intuition.

2. THE USER OBJECTIVES (doc 45)
   Geographic decisions follow life objectives.
   The HUD shows the geographic reality of those objectives.

3. THE AI DECISION FRAMEWORK (doc 52)
   Decisions become spatial.
   "Where should I go?" is the natural question.
   The HUD makes the answer visible.

4. THE WR (doc 47)
   The retrospective gains spatial dimension.
   "This week I worked these zones, missed these prayers,
    refueled at these stations."

5. SUBMISSIONS (doc 53)
   Submissions get spatial context.
   "While driving through this zone, you could..."

6. ALL EXISTING VECTOR LOGIC
   Bolt overlay logic, fuel tracking, sessions
   All become more powerful when spatially visible.

= THE HUD IS NOT A FEATURE.
  IT IS THE NATURAL EVOLUTION OF VECTOR.
```

---

## 14. Database Schema

```sql
CREATE TABLE vector_hud_preferences (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                  UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  
  -- Per-overlay display mode (4-option filter)
  -- Values: 'always' | 'driving_only' | 'standby_only' | 'never'
  overlay_heatmap_mode     VARCHAR(16) NOT NULL DEFAULT 'always',
  overlay_aviation_mode    VARCHAR(16) NOT NULL DEFAULT 'standby_only',
  overlay_events_mode      VARCHAR(16) NOT NULL DEFAULT 'standby_only',
  overlay_stations_mode    VARCHAR(16) NOT NULL DEFAULT 'always',
  overlay_mosques_mode     VARCHAR(16) NOT NULL DEFAULT 'always',
  overlay_shortcuts_mode   VARCHAR(16) NOT NULL DEFAULT 'always',
  overlay_lanes_mode       VARCHAR(16) NOT NULL DEFAULT 'driving_only',
  overlay_transport_mode   VARCHAR(16) NOT NULL DEFAULT 'never',
  overlay_incidents_mode   VARCHAR(16) NOT NULL DEFAULT 'never',
  
  CONSTRAINT chk_mode_values CHECK (
    overlay_heatmap_mode IN ('always', 'driving_only', 'standby_only', 'never') AND
    overlay_aviation_mode IN ('always', 'driving_only', 'standby_only', 'never') AND
    overlay_events_mode IN ('always', 'driving_only', 'standby_only', 'never') AND
    overlay_stations_mode IN ('always', 'driving_only', 'standby_only', 'never') AND
    overlay_mosques_mode IN ('always', 'driving_only', 'standby_only', 'never') AND
    overlay_shortcuts_mode IN ('always', 'driving_only', 'standby_only', 'never') AND
    overlay_lanes_mode IN ('always', 'driving_only', 'standby_only', 'never') AND
    overlay_transport_mode IN ('always', 'driving_only', 'standby_only', 'never') AND
    overlay_incidents_mode IN ('always', 'driving_only', 'standby_only', 'never')
  ),
  
  -- Display preferences
  standby_zoom_diameter_km INTEGER NOT NULL DEFAULT 50,
  day_night_mode           VARCHAR(16) NOT NULL DEFAULT 'auto',
                           -- 'auto' | 'day' | 'night'
  show_user_trail          BOOLEAN NOT NULL DEFAULT TRUE,
  trail_duration_min       INTEGER NOT NULL DEFAULT 5,
  
  -- Side panel state
  side_panel_open          BOOLEAN NOT NULL DEFAULT FALSE,
  side_panel_expanded_category VARCHAR(64) NULL,
  
  -- Updates
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Per-item visibility within each overlay category
CREATE TABLE vector_hud_item_preferences (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  overlay_category         VARCHAR(64) NOT NULL,
                           -- 'heatmap' | 'aviation' | 'events' | etc.
  item_identifier          VARCHAR(200) NOT NULL,
                           -- e.g., 'zone:chatelet', 'transport:rer_a'
  is_visible               BOOLEAN NOT NULL DEFAULT TRUE,
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  UNIQUE (user_id, overlay_category, item_identifier)
);

CREATE INDEX vector_hud_item_preferences_user_cat_idx
ON vector_hud_item_preferences (user_id, overlay_category);

CREATE TABLE vector_personal_shortcuts (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  
  -- Shortcut definition
  title                    VARCHAR(200) NOT NULL,
  description              TEXT NULL,
  entry_lat                NUMERIC NOT NULL,
  entry_lng                NUMERIC NOT NULL,
  exit_lat                 NUMERIC NOT NULL,
  exit_lng                 NUMERIC NOT NULL,
  
  -- Metadata
  estimated_time_gain_min  INTEGER NOT NULL,
  shortcut_type            VARCHAR(64),
                           -- 'parking_through' | 'bus_lane' | 'small_street' | 'other'
  
  -- Usage context
  applicable_hours         INT4RANGE NULL,
                           -- e.g., [8, 22) for daytime only
  applicable_weekdays      INTEGER[] NULL,
                           -- e.g., [1,2,3,4,5] for weekdays only
  
  -- Lifecycle
  status                   VARCHAR(32) NOT NULL DEFAULT 'active',
                           -- 'active' | 'archived' | 'failed'
  times_used               INTEGER NOT NULL DEFAULT 0,
  total_time_saved_min     INTEGER NOT NULL DEFAULT 0,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at             TIMESTAMPTZ NULL
);

CREATE INDEX vector_personal_shortcuts_user_active_idx
ON vector_personal_shortcuts (user_id, status)
WHERE status = 'active';

CREATE TABLE vector_heatmap_snapshots (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  computed_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  zone_data                JSONB NOT NULL,
                           -- Array of {lat, lon, score, color}
  area_bbox                JSONB NOT NULL,
  CONSTRAINT vector_heatmap_snapshots_freshness 
    CHECK (computed_at > now() - interval '1 hour')
);

CREATE INDEX vector_heatmap_snapshots_computed_idx
ON vector_heatmap_snapshots (computed_at DESC);

-- Lane Optimization (Section 9.8)

CREATE TABLE highway_segments (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  road_ref                 VARCHAR(32) NOT NULL,
                           -- 'A6', 'A86', 'N118', etc.
  road_name                VARCHAR(200),
  highway_type             VARCHAR(32) NOT NULL,
                           -- 'motorway' | 'trunk' | 'primary'
  
  start_lat                NUMERIC NOT NULL,
  start_lng                NUMERIC NOT NULL,
  end_lat                  NUMERIC NOT NULL,
  end_lng                  NUMERIC NOT NULL,
  segment_length_m         INTEGER NOT NULL,
  
  lane_count               INTEGER NOT NULL CHECK (lane_count >= 2),
  
  osm_way_ids              BIGINT[],
                           -- Reference back to OSM source
  
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX highway_segments_spatial_idx
ON highway_segments USING gist (
  ST_MakeEnvelope(start_lng, start_lat, end_lng, end_lat, 4326)
);

CREATE INDEX highway_segments_road_ref_idx
ON highway_segments (road_ref);

CREATE TABLE highway_lane_observations (
  id                       BIGSERIAL PRIMARY KEY,
  user_id                  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  segment_id               UUID NOT NULL REFERENCES highway_segments(id) ON DELETE CASCADE,
  session_id               UUID NULL,  -- link to vector_sessions if applicable
  recording_session_id     UUID NOT NULL,  -- groups observations during one jam
  
  lane_number              INTEGER NOT NULL CHECK (lane_number >= 1),
  observed_speed_kmh       NUMERIC(5,2) NOT NULL,
  observed_lat             NUMERIC NOT NULL,
  observed_lng             NUMERIC NOT NULL,
  
  -- Destination awareness (critical for accurate patterns)
  destination_segment_id   UUID NULL REFERENCES highway_segments(id),
                           -- which branch the user is heading toward
                           -- (e.g., A6A vs A6B)
  destination_branch_label VARCHAR(64) NULL,
                           -- human label like 'A6A_paris' for clarity
  
  observed_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  day_of_week              SMALLINT NOT NULL,  -- 0=Sunday ... 6=Saturday
  hour_of_day              SMALLINT NOT NULL,
  time_window              VARCHAR(32) NOT NULL,
                           -- 'rush_morning' | 'midday' | 'rush_evening' | 'night'
  
  context_json             JSONB NULL
                           -- weather, events, other context
);

CREATE INDEX highway_lane_observations_segment_user_idx
ON highway_lane_observations (segment_id, user_id, observed_at DESC);

CREATE INDEX highway_lane_observations_aggregation_idx
ON highway_lane_observations (segment_id, destination_segment_id, lane_number, time_window, day_of_week);

CREATE INDEX highway_lane_observations_recording_idx
ON highway_lane_observations (recording_session_id);

CREATE TABLE highway_lane_recording_sessions (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  vector_session_id        UUID NULL,  -- if recorded during a VTC session
  
  started_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at                 TIMESTAMPTZ NULL,
  ended_reason             VARCHAR(32) NULL,
                           -- 'manual' | 'traffic_cleared' | 'left_highway'
  
  total_observations       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX highway_lane_recording_sessions_user_idx
ON highway_lane_recording_sessions (user_id, started_at DESC);

CREATE TABLE highway_lane_patterns (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  segment_id               UUID NOT NULL REFERENCES highway_segments(id) ON DELETE CASCADE,
  destination_segment_id   UUID NULL REFERENCES highway_segments(id),
                           -- NULL = no destination split applicable
  
  lane_number              INTEGER NOT NULL,
  time_window              VARCHAR(32) NOT NULL,
  is_weekend               BOOLEAN NOT NULL,
  
  avg_speed_kmh            NUMERIC(5,2) NOT NULL,
  median_speed_kmh         NUMERIC(5,2) NOT NULL,
  sample_count             INTEGER NOT NULL,
  confidence_score         NUMERIC(3,2) NOT NULL CHECK (confidence_score BETWEEN 0 AND 1),
  
  last_updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  UNIQUE (user_id, segment_id, destination_segment_id, lane_number, time_window, is_weekend)
);

CREATE INDEX highway_lane_patterns_lookup_idx
ON highway_lane_patterns (user_id, segment_id, destination_segment_id, time_window, is_weekend);
```

---

## 15. AI Tasks Touched

```text
vector.hud.heatmap_compute     - deterministic SQL + Qwen analysis
vector.hud.shortcut_detect     - GPS proximity check (no AI)
vector.hud.aviation_filter     - deterministic
vector.hud.event_priority      - Qwen analysis of impact
vector.hud.station_recommend   - integrates with smart fuel (doc 46)
```

Most operations are deterministic. AI only used for nuanced decisions.

---

## 16. Risks And Mitigations

```text
RISK 1 — Battery drain
  HUD with multiple overlays = GPU + GPS intensive
  Mitigation: 
    - Background mode when app in background
    - Reduce update frequencies in background
    - User can manually pause overlays

RISK 2 — Data overload
  Too many overlays = visual chaos
  Mitigation:
    - Default to minimal overlays
    - User progressively enables
    - Smart filtering per overlay

RISK 3 — API costs spiral
  AeroAPI / TomTom usage grows
  Mitigation:
    - Aggressive caching
    - Smart polling (only when relevant)
    - User can disable expensive overlays

RISK 4 — Map accuracy issues
  OSM may have gaps
  Mitigation:
    - User can report missing data
    - Manual corrections via JOSM
    - Validate via real trips

RISK 5 — Network dependency
  All overlays require connectivity
  Mitigation:
    - Cache last 1-2 hours of data
    - Graceful degradation
    - User can pre-download IDF tiles

RISK 6 — Visual safety while driving
  Distractions = danger
  Mitigation:
    - Navigation mode = minimal overlays
    - Critical alerts only
    - No animations during high-speed driving
```

---

## 17. Implementation Order

```text
PHASE V6.0 — Foundation
  ├─ Provision VPS upgrade (KVM 8) - optional initially
  ├─ Install Valhalla
  ├─ Import OSM Île-de-France
  ├─ Set up tile server
  ├─ MapLibre SDK in Android app
  ├─ Basic map display
  ├─ Routing API endpoint
  ├─ TomTom Traffic integration
  ├─ Personal shortcuts (DB + UI to add)
  ├─ Custom costing in Valhalla (shortcuts in routing)
  └─ Basic navigation (no voice, no recalc)

PHASE V6.5 — Heatmap
  ├─ Backend heatmap computation
  ├─ Frontend overlay rendering
  ├─ Refresh logic
  ├─ Tap interactions
  └─ User preferences (enable/disable)

PHASE V7.0 — Mosques + Stations
  ├─ Mosques overlay rendering
  ├─ MAWAQIT integration (already done in Path)
  ├─ Stations overlay rendering
  ├─ CarbuRoi API integration
  ├─ Price-based color coding
  └─ Smart fuel badge integration

PHASE V7.5 — Events
  ├─ Events overlay rendering
  ├─ Wave animation
  ├─ Integration with events_calendar
  └─ Filter UI

PHASE V8.0 — Aviation
  ├─ AeroAPI / FR24 client
  ├─ Aircraft tracking logic
  ├─ Trail rendering
  ├─ ETA computation
  └─ Performance optimization

PHASE V8.5 — Polish
  ├─ Day/Night themes
  ├─ Animation refinement
  ├─ Battery profiling
  ├─ Per-overlay filter UIs
  ├─ Mode switching animations
  ├─ Beta testing
  └─ Production deployment
```

---

## 18. Non-Goals For V6+

```text
❌ Voice navigation (user explicitly rejects)
❌ Replace Waze/Google Maps for general navigation
❌ Marketplace of overlays from third parties
❌ Multi-user features
❌ Carpool / ride-sharing integration
❌ Predictive AI saying "you should be in zone X now"
   (User decides, system shows context)
❌ Penalize user for ignoring HUD suggestions
   (HUD is informative, never directive)
❌ Replace existing Vector functionality
   (HUD is the new shell, but old logic remains)
```

---

## 19. V7+ Future Possibilities

```text
ADDITIONAL OVERLAYS TO CONSIDER:
- Weather radar (rain on map, real-time)
- Traffic incidents with severity colors
- Customer demand prediction (ML-based)
- Time-based zone profitability (4D)
- Route history visualization
- "Where I've been" heatmap (personal)
- Real-time competitor positions (Bolt drivers density)
- Construction zones / planned roadworks
- Safety alerts (high-risk zones)

CAPABILITIES TO ENHANCE:
- 3D map view (depth perception)
- AR overlays (when stopped)
- Voice queries ("Where's the nearest mosque?")
- Apple CarPlay / Android Auto integration
- Smartwatch glance display
```

---

## 20. References

- `33_VECTOR_LOGIC_DETAIL.md` — Vector core
- `39_WRS_VECTOR_LEARNING_LOOP.md` — heatmap learning
- `41_PATH_LOGIC_DETAIL.md` — mosques source
- `42_VAULT_LOGIC_DETAIL.md` — financial context
- `44_BRAIN_UNIFIED_LOGIC.md` — unified brain
- `46_VECTOR_FUEL_SMART_TRACKING.md` — fuel context
- `52_AI_DECISION_FRAMEWORK.md` — decision integration
- `53_SUBMISSIONS_OVERLAY_TASKS.md` — submission context

---

## 21. Final Note

```text
This is the endgame for Vector.

When V6+ is complete:
- The user opens Vector
- The map fills the screen
- Their world is laid out in front of them
- Every overlay shows what matters
- Every interaction is spatial
- The brain becomes visual

This is not a feature.
This is Vector growing up into its final form.

UNTIL THAT DAY:
- Don't start it before V5 is stable
- Don't spec it further until you've used V1-V5
- Trust that your future self will know what to refine
- This document is the seed, not the recipe

The vision is captured.
The execution waits for its time.
```

---

**Document version:** 1.0
**Status:** V6+ design vision (DO NOT IMPLEMENT before V5 stable)
**Last updated:** 2026-05-12
