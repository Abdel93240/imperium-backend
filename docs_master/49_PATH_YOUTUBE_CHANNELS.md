# 49 - Path YouTube Channels Follow (V3)

> ⚠️ **V3 feature — quality of life, post-V1 and V2.**
> Religious learning section in Path.

---

## 1. Purpose

Allow the user to follow up to **2 YouTube channels** dedicated to religious sciences. New videos appear in a dedicated "Apprentissage religieux" section in the Path dashboard, with a `NEW` badge until visible.

The goal: never miss new content from key religious teachers, without notification spam, without forced missions, without complexity.

This feature pairs with doc 50 (Dars knowledge base) under the same Path UI section.

---

## 2. Why V3 And Not Earlier

```text
V1 — Path core: prayers, fasting, sadaqa, ghusl, adhkar.
V2 — Path refinements based on V1 usage.
V3 — Quality of life: external content tracking, knowledge base.

This feature is purely additive. It doesn't impact daily 
operations. It enhances the religious learning experience 
without forcing it.
```

---

## 3. Hard Limit: Maximum 2 Channels

```text
The user can follow ONLY 2 YouTube channels.

Why this strict limit:
- Prevents the section from becoming a content firehose
- Forces curation: the user must choose 2 channels they value
- Keeps the dashboard focused
- Avoids notification fatigue and decision paralysis

The user can change channels anytime in Path settings,
but only 2 active at any time.
```

---

## 4. The User Flow

### 4.1 First-time setup

```text
Path settings → Apprentissage religieux:
  
  Chaînes YouTube suivies (max 2):
    [Aucune chaîne configurée]
    
    [+ Ajouter une chaîne]

User taps [+ Ajouter une chaîne]:
  
  ┌──────────────────────────────────────┐
  │ Ajouter une chaîne YouTube           │
  │                                      │
  │ Recherche par nom:                   │
  │ [____________________________]  🔍   │
  │                                      │
  │ Ou colle une URL de chaîne:          │
  │ [____________________________]       │
  │                                      │
  │ [Annuler]  [Ajouter]                 │
  └──────────────────────────────────────┘

Backend:
  - Calls YouTube Data API to verify channel exists
  - Stores channel_id in path_youtube_channels
  - Fetches the latest 10 videos as initial state
```

### 4.2 Daily check (cron)

```text
Cron daily at 09:00 Europe/Paris:
  For each channel followed (max 2):
    GET YouTube API: channels uploads playlist
    Compare with stored video list
    If new videos detected:
      INSERT into path_youtube_videos with is_new=TRUE
    
  No notification fired.
  The user discovers new content when they open Path.
```

### 4.3 Path dashboard "Apprentissage religieux" section

```text
The section appears between other Path elements (above the 
fold so it's discoverable without searching).

  ┌─────────────────────────────────────────────────┐
  │ 📚 APPRENTISSAGE RELIGIEUX                      │
  │                                                 │
  │ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐       │
  │ │ NEW │ │     │ │     │ │     │ │     │  →    │
  │ │ ▶   │ │ ▶   │ │ ▶   │ │ ▶   │ │ ▶   │       │
  │ │     │ │     │ │     │ │     │ │     │       │
  │ │titre│ │titre│ │titre│ │titre│ │titre│       │
  │ │  3j │ │  7j │ │ 14j │ │ 21j │ │ 28j │       │
  │ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘       │
  │                                                 │
  │ [Voir mes Dars]  ← link to doc 50 feature       │
  │                                                 │
  └─────────────────────────────────────────────────┘

Carousel scrolls horizontally. Newest video first. Older 
videos to the right.

NEW badge:
  - Appears on videos detected within last 24h
  - Disappears when the user has tapped the thumbnail at 
    least once (the system considers it "discovered")
  - Falls off automatically after 7 days regardless

Tap on thumbnail:
  - Opens the YouTube app (or browser) on that video
  - The user watches in YouTube
  - When user returns to Path, the NEW badge is gone
```

### 4.4 Video tap behavior

```text
On thumbnail tap:
  Backend records: 
    - video_discovered_at (first tap)
    - is_new = FALSE after first tap
  
  Opens external link: youtube.com/watch?v=VIDEO_ID
  
  No "watched" tracking. The user simply opened it.
  Whether they watched 5 seconds or 20 minutes is not 
  the system's concern.
```

This minimalism is intentional. Per user spec: "if YouTube doesn't expose watch state, we don't fake it."

---

## 5. YouTube API Integration

### 5.1 API used

```text
YouTube Data API v3 (free tier):
  - Quota: 10,000 units/day
  - Channel lookup: 1 unit
  - Playlist items list: 1 unit per page
  - Videos details: 1 unit per video

Daily usage estimate:
  - 2 channels × 1 unit (playlist check) = 2 units
  - Plus video details if new: ~5-10 units total
  - DAILY: ~10-15 units used out of 10,000
  - Massive headroom

Authentication: API key (not OAuth, since it's read-only public data)
```

### 5.2 Setup requirements

```text
1. Create Google Cloud project
2. Enable YouTube Data API v3
3. Create API key (restrict to YouTube Data API)
4. Store key in env: YOUTUBE_API_KEY
5. No OAuth needed, no scope dance
```

---

## 6. Database Schema

```sql
CREATE TABLE path_youtube_channels (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  channel_id      VARCHAR(64) NOT NULL,        -- YouTube channel ID
  channel_name    VARCHAR(200) NOT NULL,
  channel_url     TEXT NOT NULL,
  thumbnail_url   TEXT NULL,
  added_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_checked_at TIMESTAMPTZ NULL,
  active          BOOLEAN NOT NULL DEFAULT TRUE,
  
  CONSTRAINT path_youtube_channels_user_channel_unique
    UNIQUE (user_id, channel_id)
);

-- Enforce max 2 active channels per user (V3 hard rule)
CREATE UNIQUE INDEX path_youtube_channels_max_two_idx
ON path_youtube_channels (user_id)
WHERE active = TRUE
;
-- Note: PostgreSQL doesn't enforce "max 2" via index directly.
-- Application layer must verify count before INSERT.

CREATE TABLE path_youtube_videos (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  channel_id        UUID NOT NULL REFERENCES path_youtube_channels(id) 
                                                          ON DELETE CASCADE,
  video_id          VARCHAR(64) NOT NULL,      -- YouTube video ID
  title             TEXT NOT NULL,
  thumbnail_url     TEXT NOT NULL,
  duration_seconds  INTEGER NULL,
  published_at      TIMESTAMPTZ NOT NULL,
  is_new            BOOLEAN NOT NULL DEFAULT TRUE,
  discovered_at     TIMESTAMPTZ NULL,           -- when user first tapped
  detected_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  CONSTRAINT path_youtube_videos_user_video_unique
    UNIQUE (user_id, video_id)
);

CREATE INDEX path_youtube_videos_user_channel_published_idx
ON path_youtube_videos (user_id, channel_id, published_at DESC);

CREATE INDEX path_youtube_videos_user_new_idx
ON path_youtube_videos (user_id)
WHERE is_new = TRUE;
```

---

## 7. The Daily Check Workflow

```text
n8n workflow: path_youtube_daily_check
Schedule: every day at 09:00 Europe/Paris

Steps:
  1. SELECT all path_youtube_channels WHERE active = TRUE
  
  2. For each channel:
     a. Call YouTube API: channels.uploads playlist
     b. Get list of last 20 videos
     c. SELECT existing videos for this channel from DB
     d. Diff: identify new videos
     e. INSERT new videos with is_new = TRUE
     f. UPDATE path_youtube_channels.last_checked_at
  
  3. NO notification sent.
  4. NO mission created (per user spec: "trop dur").
  5. The user discovers new content next time they open Path.
```

---

## 8. Auto-Cleanup

```text
Daily cron at 09:30 Europe/Paris:

For each user:
  - SET is_new = FALSE on videos older than 7 days even if 
    the user never tapped them
  - DELETE videos older than 90 days that haven't been tapped
  - Keep tapped videos forever (the user may want history)
```

---

## 9. Edge Cases

### 9.1 Channel becomes private or deleted

```text
If YouTube returns 404 or 403 for a channel:
  - SET path_youtube_channels.active = FALSE
  - Notify user via Path banner: 
    "La chaîne 'X' n'est plus accessible. La retirer ou attendre ?"
  - User can remove or wait (some channels go private temporarily)
```

### 9.2 Video published_at in the future

```text
Some channels schedule videos.
If published_at > now():
  - Don't show as "new yet"
  - Show in the carousel only after published_at passes
  - Cron picks them up automatically when the time comes
```

### 9.3 Live streams or premieres

```text
For V3, treat live streams as regular videos when published_at 
is set. Skip live streams that have no fixed publication time.
```

### 9.4 User wants to add a 3rd channel

```text
Backend rejects with 400:
  "Tu as déjà 2 chaînes suivies. Retire-en une avant 
   d'en ajouter une nouvelle."

UI shows clear message and the [Add] button is disabled when 
2 channels are already active.
```

---

## 10. AI Tasks Touched

```text
NONE.

This feature is fully deterministic:
- YouTube API call
- DB operations
- UI rendering

No AI is needed. No cost beyond YouTube API quota (free).
```

---

## 11. UI Surface (V3)

```text
Path Dashboard:
  ├─ (existing prayer/sadaqa/fasting elements)
  ├─ APPRENTISSAGE RELIGIEUX section:
  │   ├─ Header
  │   ├─ Horizontal carousel of videos
  │   │   - newest first
  │   │   - NEW badge if applicable
  │   │   - thumbnail + title + days ago
  │   └─ Link to Dars (doc 50)
  └─ (other elements)

Path Settings:
  ├─ Apprentissage religieux subsection:
  │   ├─ Chaînes YouTube suivies:
  │   │   - List of active channels (max 2)
  │   │   - [Modifier] / [Supprimer] buttons
  │   │   - [+ Ajouter une chaîne] button (disabled if 2 active)
  │   └─ Effacer l'historique des vidéos:
  │       - "Garde les chaînes mais oublie les vidéos vues"
  │       - For privacy / decluttering
```

---

## 12. Privacy

```text
DATA SENT TO GOOGLE (YouTube API):
- Channel IDs (public information)
- API key (yours)
- Standard rate-limit metadata

DATA STORED LOCALLY:
- Channels followed
- Videos detected
- Discovery timestamps

USER CONTROL:
- Add/remove channels anytime
- Clear video history anytime
- Disable feature entirely anytime (no impact on rest of Path)
```

---

## 13. Implementation Order (V3)

```text
Phase 1 — Schema migrations
  ├─ path_youtube_channels
  └─ path_youtube_videos

Phase 2 — YouTube API client
  └─ services/integrations/youtube_client.py
     - get_channel_info(channel_id)
     - get_recent_videos(channel_id, limit=20)

Phase 3 — Backend services
  └─ services/path/youtube_channels.py
     - add_channel, remove_channel, list_channels
     - check_for_new_videos (used by cron)
     - mark_video_discovered

Phase 4 — API endpoints
  ├─ POST   /api/v1/path/youtube/channels
  ├─ GET    /api/v1/path/youtube/channels
  ├─ DELETE /api/v1/path/youtube/channels/{id}
  ├─ GET    /api/v1/path/youtube/videos (carousel data)
  └─ POST   /api/v1/path/youtube/videos/{id}/discovered

Phase 5 — n8n workflow
  └─ path_youtube_daily_check.json
     - Daily 09:00 cron
     - Call backend internal endpoint to refresh

Phase 6 — UI in Android app
  ├─ Path dashboard "Apprentissage religieux" section
  ├─ Horizontal carousel component
  ├─ NEW badge logic
  └─ Path settings: channels management
```

---

## 14. Non-Goals For V3

```text
❌ Video watch tracking (user spec: "trop galère")
❌ Auto-creating missions for new videos (user spec: "trop dur")
❌ Notifications when new video drops
❌ More than 2 channels
❌ Channels other than YouTube (no Twitter/podcast/etc.)
❌ AI summarizing video content
❌ Transcription of videos
❌ Recommendations of new channels to follow
```

---

## 15. References

- `41_PATH_LOGIC_DETAIL.md` — Path module
- `50_PATH_DARS_KNOWLEDGE_BASE.md` — companion feature in same Path section
- `08_NON_NEGOTIABLE_RULES.md` — religious privacy

---

**Document version:** 1.0
**Status:** V3 design specification (DO NOT IMPLEMENT before V1 + V2)
**Last updated:** 2026-04-29
