# 48 - Vector Music Shaker (V3)

> ⚠️ **V3 feature — quality of life, post-V1 and V2.**
> This document captures the design for future implementation.

---

## 1. Purpose

The **Music Shaker** is an in-Vector feature that generates a personalized 1h30 Spotify playlist on demand, based on a few seed tracks the user provides. It learns from the user's modifications over time, but only within similar musical contexts.

Goal: end the morning frustration of listening to the same songs on repeat. Provide a fresh, coherent playlist tailored to today's mood, in seconds.

---

## 2. Why V3 And Not Earlier

```text
V1 — VTC core, sessions, fuel basics, Vector dashboard.
     The user has no time to think about extras.

V2 — Smart fuel tracking, WR guided sections.
     Quality and clarity improvements to existing flows.

V3 — Quality of life features that make the system pleasant
     to use, not just functional. Music Shaker lands here
     as a feature that doesn't impact operational quality
     but greatly improves the daily experience.
```

This feature requires Spotify OAuth setup, which is a clear separate workstream best done after V1 and V2 are stable.

---

## 3. Core Architecture

```text
USER FLOW:

1. User opens Vector dashboard
2. Taps "🎵 Music Shaker" button (dedicated button, NOT auto-launch)
3. Popup opens:
   - "Quel mood aujourd'hui ?"
   - Spotify search bar (autocomplete)
   - User adds 1-5 seed tracks
   - User taps [Mixer]

4. Backend processing (~6 seconds):
   - Step 0: Learn from yesterday's modifications (if any)
   - Step 1: Qwen extracts intent from seed tracks
   - Step 2: Spotify /recommendations endpoint
   - Step 3: Qwen filters and orders results
   - Step 4: Spotify creates playlist "Vector daily YYYY-MM-DD"

5. UI shows:
   - "Playlist créée!"
   - [Ouvrir dans Spotify]
   - Track preview list
```

---

## 4. The Three Key Decisions

### 4.1 The user always controls the seeds

```text
DECISION (validated by user):
The seed tracks the user types are sent VERBATIM to Spotify.
Backend does NOT augment them with learned tracks.

WHY:
- User stays 100% master of the starting pool
- Predictable behavior: what you type is what you get
- The AI brings value in filtering and ordering, not in
  silently adding tracks the user didn't ask for

ALTERNATIVE REJECTED (Option B in design discussion):
- Backend silently adds 2 historical seeds based on context
- Risk: surprising results, user loses understanding
- Risk: "Why is Stromae here? I posted Booba and Sch."
```

### 4.2 Contextual learning, not absolute

```text
DECISION (validated by user):
Learning from past modifications applies ONLY when the new
session has a SIMILAR musical context to the past one.

WHY:
- Tastes are contextual, not absolute
- Liking Ninho in rap FR context ≠ liking Ninho everywhere
- Ignoring this leads to wrong recommendations

EXAMPLE OF WRONG BEHAVIOR (avoided):
- Monday: user likes Ninho added in rap FR playlist
- Tuesday: user requests deep house playlist
- Naive system: "User loves Ninho, add it to deep house"
- Reality: user would be confused and annoyed

EXAMPLE OF RIGHT BEHAVIOR (implemented):
- Monday: user adds Ninho in rap FR context
- Stored: {action: added, track: Ninho, context: rap FR}
- Tuesday: deep house context → no Ninho
- Wednesday: rap FR context again → Ninho boosted
```

### 4.3 Two-layer learning (contextual + global)

```text
LAYER 1 — Contextual (local to a style):
Modifications matter only in similar contexts.
Quick to learn, applies to most cases.

LAYER 2 — Global anti-patterns and affinities:
After 3+ occurrences across DIFFERENT contexts:
- 3+ removals of an artist → globally disliked, excluded
- 3+ additions of an artist → globally liked, boosted

WHY THE GLOBAL LAYER:
Some artists transcend styles. If the user removes Booba
in rap FR, in trap, AND in old-school rap, then Booba is
truly disliked, not contextually disliked.

THE 3+ THRESHOLD:
- Avoids overreacting to one-off mood-driven removals
- Requires consistent pattern across distinct contexts
- Conservative by design
```

---

## 5. Detailed Backend Flow

### 5.1 Step 0 — Learn from yesterday (if applicable)

```text
INPUT: user_id, today's date

ALGORITHM:
1. SELECT * FROM vector_music_sessions
   WHERE user_id = ? 
   AND created_at > now() - interval '7 days'
   AND modifications_checked_at IS NULL
   ORDER BY created_at DESC

2. For each unchecked past session:
   a. GET spotify playlist tracks (current state)
   b. Compare with initial_track_list (stored)
   c. Compute diff:
      - added[]: tracks in current but not initial
      - removed[]: tracks in initial but not current
   d. UPDATE vector_music_sessions:
      modifications_json = {added, removed}
      modifications_checked_at = now()
   
3. Update profile patterns (Section 6)

LATENCY: ~1-2 seconds
COST: 0€ (Spotify API free)
```

### 5.2 Step 1 — Qwen extracts intent

```text
INPUT: 5 seed tracks (with Spotify track features)

QWEN ANALYZES:
- Tempo distribution
- Energy distribution
- Valence (positivity) distribution
- Genres represented
- Languages
- Era/decade

QWEN PRODUCES:
{
  "target_energy": 0.7,
  "target_tempo": 110,
  "target_valence": 0.6,
  "target_acousticness": 0.2,
  "primary_genres": ["hip-hop", "rap-fr"],
  "language_preferences": ["fr", "en"],
  "context_signature": "rap_fr_high_energy",
  "confidence": 0.82
}

LATENCY: ~2 seconds
COST: 0€ (Qwen local)
```

### 5.3 Step 2 — Spotify recommendations

```text
INPUT: 
- seed_tracks (the 1-5 user-provided IDs)
- target_energy, target_tempo, target_valence (from Qwen)
- limit: 80 (we'll filter later)

CALL: GET https://api.spotify.com/v1/recommendations

OUTPUT: 80 candidate tracks with full audio features

LATENCY: ~500ms
COST: 0€
```

### 5.4 Step 3 — Qwen filters and orders

```text
INPUT:
- 80 candidate tracks from Spotify
- User's vector_music_profile (Section 7)
- Past contextual modifications matching current context

QWEN APPLIES:

A. Anti-patterns (HARD FILTER):
   - Exclude tracks by globally disliked artists
   - Exclude tracks user has explicitly removed in 
     similar contexts in the past

B. Affinity boost (SOFT BOOST):
   - Tracks by globally liked artists move up
   - Tracks user has explicitly added in similar 
     contexts move up

C. Diversity rules:
   - Max 2 tracks per artist
   - Spread out energy if too uniform
   - Mix languages naturally if user has multilingual taste

D. Length matching:
   - Target: 1h30 = 90 minutes total
   - Compute cumulative duration
   - Stop adding tracks at ~90 min (±5 min tolerance)

E. Ordering for progression:
   - Start with energy slightly below target
   - Build up to target around track 5-6
   - Maintain energy through middle
   - Slight wind-down for last 2-3 tracks

OUTPUT: 25-30 tracks in optimal order

LATENCY: ~2 seconds
COST: 0€
```

### 5.5 Step 4 — Spotify creates playlist

```text
ACTIONS:
1. POST /v1/users/{user_id}/playlists
   - name: "Vector daily 2026-04-29"
   - description: "Generated by Vector"
   - public: false
2. POST /v1/playlists/{playlist_id}/tracks
   - uris: [array of track URIs in order]

OUTPUT:
- spotify_playlist_id
- spotify_playlist_url

3. INSERT vector_music_sessions
   - user_id, seed_tracks, qwen_intent_json
   - spotify_playlist_id, spotify_playlist_url
   - initial_track_list, initial_duration_sec

LATENCY: ~1 second
COST: 0€
```

---

## 6. The Profile Update Algorithm

After learning from past modifications (Step 0), we update `vector_music_profile`.

```text
INPUT: list of recent modifications across past sessions

A. CONTEXTUAL modifications storage:
   For each modification (added or removed track):
   - Store: track_id, action, context_signature, occurred_at
   - Do NOT update global profile yet

B. GLOBAL pattern detection:
   For each artist in modifications:
   - Count distinct context_signatures with REMOVAL action
   - Count distinct context_signatures with ADDITION action
   
   If removals across 3+ distinct contexts:
     - Add to vector_music_profile.avoided_artists
   
   If additions across 3+ distinct contexts:
     - Add to vector_music_profile.liked_artists

C. AGGREGATE statistics (background):
   - avg_energy: rolling average from recent sessions
   - avg_tempo: same
   - language_mix: ratio of FR/EN/other in recent listens
   - preferred_track_length_sec: median of kept tracks
```

The profile updates SLOWLY and CONSERVATIVELY. One bad day doesn't reshape the profile.

---

## 7. Database Schema

### 7.1 Spotify OAuth tokens

```sql
CREATE TABLE spotify_oauth_tokens (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  access_token    TEXT NOT NULL,    -- encrypted at rest
  refresh_token   TEXT NOT NULL,    -- encrypted at rest
  expires_at      TIMESTAMPTZ NOT NULL,
  scope           TEXT NOT NULL,
  spotify_user_id VARCHAR(128),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 7.2 Music sessions

```sql
CREATE TABLE vector_music_sessions (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                  UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  vector_session_id        UUID NULL REFERENCES vector_sessions(id),
  
  -- User input
  seed_tracks              JSONB NOT NULL,
                           -- [{spotify_id, name, artist}]
  duration_target_min      INTEGER NOT NULL DEFAULT 90,
  
  -- AI processing
  qwen_intent_json         JSONB NOT NULL,
                           -- {target_energy, target_tempo, target_valence,
                           --  primary_genres, language_preferences,
                           --  context_signature, confidence}
  
  -- Spotify output (initial state)
  spotify_playlist_id      TEXT NOT NULL,
  spotify_playlist_url     TEXT NOT NULL,
  initial_track_list       JSONB NOT NULL,
                           -- [{spotify_id, name, artist, position, 
                           --   duration_ms, energy, tempo, valence}]
  initial_duration_sec     INTEGER NOT NULL,
  initial_track_count      INTEGER NOT NULL,
  
  -- Modifications (filled later by Step 0 of next session)
  modifications_checked_at TIMESTAMPTZ NULL,
  modifications_json       JSONB NULL,
                           -- {added: [...], removed: [...]}
  
  -- Lifecycle
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX vector_music_sessions_user_created_idx
ON vector_music_sessions (user_id, created_at DESC);

CREATE INDEX vector_music_sessions_unchecked_idx
ON vector_music_sessions (user_id)
WHERE modifications_checked_at IS NULL;
```

### 7.3 Music profile

```sql
CREATE TABLE vector_music_profile (
  id                        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id                   UUID UNIQUE NOT NULL REFERENCES users(id) 
                                                          ON DELETE CASCADE,
  
  -- Global profile (computed slowly)
  preferred_genres          TEXT[],
  avoided_artists           TEXT[],   -- 3+ context-distinct removals
  liked_artists             TEXT[],   -- 3+ context-distinct additions
  avg_energy                NUMERIC(3,2),
  avg_tempo                 INTEGER,
  language_mix              JSONB,    -- {fr: 0.6, en: 0.4}
  preferred_track_length_sec INTEGER,
  
  -- Lifecycle
  last_computed_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  total_sessions_analyzed   INTEGER NOT NULL DEFAULT 0
);
```

### 7.4 Contextual modifications (the key learning store)

```sql
CREATE TABLE vector_music_modifications (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  music_session_id    UUID NOT NULL REFERENCES vector_music_sessions(id) 
                                                            ON DELETE CASCADE,
  
  -- The modification
  action              VARCHAR(16) NOT NULL,
                      -- 'added' | 'removed'
  spotify_track_id    TEXT NOT NULL,
  track_name          TEXT NOT NULL,
  track_artist        TEXT NOT NULL,
  
  -- Track features (from Spotify, for context matching)
  track_energy        NUMERIC(3,2),
  track_tempo         INTEGER,
  track_valence       NUMERIC(3,2),
  
  -- Context signature (from the music session it was modified in)
  context_signature   VARCHAR(64) NOT NULL,
                      -- e.g. "rap_fr_high_energy"
  context_genres      TEXT[],
  context_target_energy NUMERIC(3,2),
  context_target_tempo INTEGER,
  
  -- Lifecycle
  occurred_at         TIMESTAMPTZ NOT NULL,
  detected_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX vector_music_modifications_user_artist_idx
ON vector_music_modifications (user_id, track_artist, action);

CREATE INDEX vector_music_modifications_user_context_idx
ON vector_music_modifications (user_id, context_signature, action);
```

---

## 8. Context Similarity Function

When generating a new playlist, the backend looks at past modifications to apply contextual learning.

```text
TWO CONTEXTS ARE "SIMILAR" if at least 2 of these 3 match:

1. ENERGY proximity:
   |context_a.target_energy - context_b.target_energy| <= 0.2

2. TEMPO proximity:
   |context_a.target_tempo - context_b.target_tempo| <= 30 BPM

3. GENRE overlap:
   At least 1 common genre between context_a.genres and context_b.genres

If SIMILAR (>= 2 of 3):
   → Past modifications in this context APPLY to current session

If NOT SIMILAR (<= 1 of 3):
   → Past modifications in this context DO NOT APPLY
   → Only global anti-patterns/affinities apply
```

This is computed on-the-fly during Step 3 (Qwen filtering).

---

## 9. AI Task Types

```text
vector.music.intent_extract  - Qwen, extract vibe from seed tracks
vector.music.filter_order    - Qwen, filter + order Spotify results
vector.music.profile_update  - Qwen, update profile from modifications

NO Sonnet, no Opus. Qwen handles everything.
```

---

## 10. Routing Distribution

```text
All AI calls in this feature: Qwen 2.5 7B local (100%)

Cost per playlist generation: 0€
Cost per profile update: 0€
TOTAL COST: 0€/year for AI

Spotify API costs: 0€ (free tier sufficient)
Spotify Premium required: YES (user already has it)

= ZERO ongoing cost for this feature.
```

---

## 11. Spotify Authentication Flow

```text
ONE-TIME SETUP:

1. User taps "Connect Spotify" in Vector settings
2. App opens browser → Spotify OAuth consent
3. User approves scopes:
   - playlist-modify-private
   - playlist-modify-public
   - playlist-read-private
   - user-read-private
4. Spotify redirects to backend callback
5. Backend exchanges code for access_token + refresh_token
6. Tokens encrypted and stored in spotify_oauth_tokens
7. User can now use Music Shaker

REFRESH:
- access_token expires every 1 hour
- Backend refreshes silently using refresh_token
- User is unaware

REVOCATION:
- User can disconnect anytime in Settings
- DELETE spotify_oauth_tokens row
- Music Shaker disabled until reconnected
```

---

## 12. Edge Cases

### 12.1 Spotify down or rate limited

```text
If Spotify API fails:
  - Show user-friendly error: "Spotify temporairement 
    indisponible. Réessaie dans 1 minute."
  - Do NOT save partial state
  - User can retry
```

### 12.2 OAuth token expired and refresh fails

```text
- Display: "Reconnecte ton compte Spotify"
- Open settings → re-auth flow
- Music Shaker disabled until reconnected
```

### 12.3 User has fewer than 5 sessions in history

```text
Cold start scenario:
- No contextual modifications yet
- No global patterns yet
- Profile is empty

Behavior:
- Music Shaker still works
- Learning starts from session 1
- Quality improves with usage
- After 5+ sessions, contextual learning is meaningful
- After ~10 sessions in same context, refinement is noticeable
```

### 12.4 User adds the same track they posted as seed

```text
Edge case: track in initial_track_list AND user added it again somehow.
- Detect duplicate
- Treat as "neutral" (no learning signal)
- Don't double-count
```

### 12.5 Spotify renames a track or removes it

```text
If a track in stored playlist no longer exists:
- Mark as "missing" in modifications
- Don't penalize user (it's not their fault)
- Skip in pattern analysis
```

### 12.6 User wants to delete history

```text
Settings → Music Shaker → "Effacer l'historique musical"
- Confirmation modal
- DELETE all vector_music_sessions for user
- DELETE vector_music_modifications for user
- RESET vector_music_profile
- Spotify playlists themselves stay (user owns them in Spotify)
```

---

## 13. UI Surface

```text
Vector Dashboard:
  [🎵 Music Shaker]  ← dedicated button, not auto-launched

Tap → Popup:
  ┌────────────────────────────────────────┐
  │ Quel mood aujourd'hui ?                │
  │                                        │
  │ Cherche un morceau...                  │
  │ 🔍 [____________]                       │
  │                                        │
  │ Morceaux choisis (1-5):                │
  │  • Ninho - Maman ne le sait pas    ✕  │
  │  • Pop Smoke - Mood Swings          ✕  │
  │  [+ Ajouter]                            │
  │                                        │
  │  Durée: 1h30 (par défaut)              │
  │                                        │
  │  [Mixer] [Annuler]                     │
  └────────────────────────────────────────┘

After tap [Mixer], loading screen ~6s:
  "Mixage en cours..."
  - Étape 1: Apprentissage des dernières modifs ✓
  - Étape 2: Compréhension de ton mood ✓
  - Étape 3: Sélection des morceaux ✓
  - Étape 4: Création de la playlist ...

Result screen:
  ┌────────────────────────────────────────┐
  │ ✅ Playlist créée!                     │
  │                                        │
  │ "Vector daily 2026-04-29"              │
  │ 28 morceaux • 1h32                     │
  │                                        │
  │ Aperçu:                                │
  │  1. Ninho - Maman ne le sait pas       │
  │  2. SCH - Cabane                       │
  │  3. Damso - 911                        │
  │  4. ...                                │
  │  [Voir tout]                           │
  │                                        │
  │ [▶ Ouvrir dans Spotify]                │
  │ [Garder ce mix]                        │
  └────────────────────────────────────────┘

Settings → Music:
  - "Connecter Spotify" / "Déconnecter Spotify"
  - "Voir mon historique de mixes"
  - "Effacer mon historique musical"
```

---

## 14. Music Shaker History View

```text
Settings → Music → Mon historique:

  Aujourd'hui:
   "Vector daily 2026-04-29"
    Seeds: Ninho, Pop Smoke
    28 tracks • Status: Active

  Hier:
   "Vector daily 2026-04-28"
    Seeds: Stromae, Orelsan
    25 tracks • Modifs: +2 ajoutés, -3 enlevés
    [Voir détails]

  Détails (tap):
    Tracks ajoutés par toi:
     - Damso - 911
     - SCH - JVLIVS
    
    Tracks enlevés par toi:
     - PNL - DA
     - Niska - Réseaux
     - Booba - Ratpi World
```

This view helps the user understand what the AI learned and gives a sense of progress.

---

## 15. Privacy

```text
DATA SENT TO SPOTIFY:
- User's seed tracks (already public on Spotify)
- Playlist creation requests
- Track features queries

DATA SENT TO QWEN:
- All Qwen calls are LOCAL on the VPS
- No external transmission
- Zero privacy concern

DATA STORED:
- Spotify tokens (encrypted at rest)
- Music history (private to user, never shared)
- Profile (private to user, never shared)

USER CONTROL:
- Can disconnect Spotify anytime
- Can delete history anytime
- Can stop using the feature anytime
```

---

## 16. Implementation Order (V3)

```text
Phase 1 — Schema migrations
  ├─ spotify_oauth_tokens
  ├─ vector_music_sessions
  ├─ vector_music_modifications
  └─ vector_music_profile

Phase 2 — Spotify integration layer
  ├─ services/integrations/spotify_client.py
  ├─ OAuth flow handlers
  ├─ Token refresh logic
  └─ Encryption for stored tokens

Phase 3 — Backend services
  ├─ services/vector/music/intent.py (Qwen call)
  ├─ services/vector/music/recommendation.py (Spotify call)
  ├─ services/vector/music/filter_order.py (Qwen call)
  ├─ services/vector/music/profile_updater.py
  └─ services/vector/music/modification_detector.py

Phase 4 — API endpoints
  ├─ POST /api/v1/vector/music/connect (OAuth start)
  ├─ GET  /api/v1/vector/music/callback (OAuth callback)
  ├─ POST /api/v1/vector/music/mix (generate playlist)
  ├─ GET  /api/v1/vector/music/sessions (history)
  ├─ DELETE /api/v1/vector/music/sessions/all (clear history)
  └─ DELETE /api/v1/vector/music/disconnect

Phase 5 — Qwen prompts
  ├─ Add to doc 35 (Qwen prompts):
  │  - qwen_music_intent.txt
  │  - qwen_music_filter_order.txt
  └─ Test with realistic seed examples

Phase 6 — Android UI
  ├─ Music Shaker button on Vector dashboard
  ├─ Popup with seed input + autocomplete
  ├─ Loading screen with steps
  ├─ Result screen with preview
  ├─ History view
  └─ Settings integration

Phase 7 — Testing
  ├─ Cold start (no history)
  ├─ With history (contextual learning)
  ├─ Cross-context test (rap FR vs deep house)
  ├─ Anti-pattern detection (3+ removals)
  └─ Affinity detection (3+ additions)
```

---

## 17. Non-Goals For V3

```text
❌ Auto-launching at session start
   (User explicitly chose: dedicated button)

❌ Multiple playlists per day
   (One per day, kept simple)

❌ Real-time skip detection during playback
   (Spotify Web Playback SDK is heavy; 
    modification tracking is enough)

❌ Cross-user recommendations
   (System is mono-user; no social layer)

❌ Album-level recommendations
   (Track-level only)

❌ Reordering as a learning signal
   (Too subtle; only adds and removes are tracked)

❌ Automatic generation based on mood detection
   (User stays in control of when and what)
```

---

## 18. V4+ Future Considerations

```text
- Time-of-day patterns (different vibes morning vs evening)
- Day-of-week patterns (different vibes weekday vs weekend)
- Weather-aware suggestions (sunny vs rainy)
- Activity context (driving alone vs with passengers)
- Voice input for seed tracks
- Multi-mood mixes (start chill, end energetic)
- Integration with Pulse (workout playlists)
```

These are not in V3 scope. They're noted for future ideation.

---

## 19. References

- `33_VECTOR_LOGIC_DETAIL.md` — Vector core logic
- `35_QWEN_SETUP_AND_PROMPTS.md` — Qwen prompts (will add music prompts)
- `09_PGVECTOR_MEMORY_POLICY.md` — modifications could feed pgvector in V4
- `08_NON_NEGOTIABLE_RULES.md` — privacy and user authority

---

## 20. Music Shaker Design Philosophy

```text
The Music Shaker is a SIDE FEATURE.
It must:
  - Make the day better, not complicate it
  - Stay invisible when not needed
  - Never override the user's musical agency
  - Learn quietly without being creepy

The AI here serves the user's mood.
The AI does not impose its own.
```

---

**Document version:** 1.0
**Status:** V3 design specification (DO NOT IMPLEMENT before V1 + V2)
**Last updated:** 2026-04-29
