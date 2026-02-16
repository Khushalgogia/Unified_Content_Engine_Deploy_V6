# Unified Content Engine V5 — Complete Documentation

> **Purpose**: This document is a full, self-contained blueprint of the Unified Content Engine V5. A developer reading this can recreate the entire application from scratch — including every LLM prompt, every API integration, every database schema, and every UI component — without referencing the source code.

---

## Table of Contents

1. [What This App Does](#1-what-this-app-does)
2. [Architecture Overview](#2-architecture-overview)
3. [Technology Stack](#3-technology-stack)
4. [Directory Structure](#4-directory-structure)
5. [Environment Variables & Secrets](#5-environment-variables--secrets)
6. [Database Schema (Supabase)](#6-database-schema-supabase)
7. [Module 1: Joke Generator](#7-module-1-joke-generator)
8. [Module 2: Video Studio](#8-module-2-video-studio)
9. [Module 3: Caption Generator](#9-module-3-caption-generator)
10. [Module 4: Instagram Uploader](#10-module-4-instagram-uploader)
11. [Module 5: Twitter Client](#11-module-5-twitter-client)
12. [Module 6: Scheduler](#12-module-6-scheduler)
13. [Module 7: Publisher Script (GitHub Actions)](#13-module-7-publisher-script-github-actions)
14. [The Main Dashboard (app.py)](#14-the-main-dashboard-apppy)
15. [Utility Scripts](#15-utility-scripts)
16. [GitHub Actions Workflows](#16-github-actions-workflows)
17. [Deployment Guide (Streamlit Cloud)](#17-deployment-guide-streamlit-cloud)
18. [Asset Management](#18-asset-management)
19. [How to Clone This App from Scratch](#19-how-to-clone-this-app-from-scratch)

---

## 1. What This App Does

The Unified Content Engine is a **Streamlit-based content creation and distribution dashboard** that lets you:

1. **Generate jokes** — Enter a topic/headline → the app uses semantic bridge embeddings (stored in Supabase + OpenAI) to find structurally similar reference jokes → then uses Google Gemini to generate new jokes using the same comedic structure but applied to your topic.
2. **Create Instagram Reels** — Each generated joke is overlaid as text onto a background video template with background music, producing a 9:16 vertical video (1080×1920).
3. **Generate viral captions** — AI-powered caption generation using Gemini that creates hooks, body text, CTAs, and hashtags optimized for Instagram/Twitter.
4. **Post to Instagram** — Upload the generated Reel video directly to Instagram using the Graph API (resumable upload protocol).
5. **Post to Twitter/X** — Post text-only tweets or tweets with video attachments using the Twitter API v2 + v1.1 chunked media upload.
6. **Schedule posts** — Instead of posting immediately, queue content for future posting at optimal time slots (09:00, 14:00, 19:00 IST).
7. **Auto-publish scheduled posts** — A GitHub Actions cron job (`publisher_script.py`) runs hourly, checks Supabase for due posts, and publishes them automatically.
8. **Auto-refresh Instagram tokens** — Another GitHub Actions cron job refreshes the 60-day Instagram access token every 15 days.

### The 5-Step Pipeline

The dashboard is organized into 5 sequential sections:

```
🧠 Ideation → ✏️ Edit & Choose → 🎬 Production → 📤 Distribution → 📅 Schedule Manager
```

- **Ideation**: Enter a topic → search bridge embeddings → select bridges → generate jokes
- **Edit & Choose**: Edit joke text → choose distribution channels per joke (Instagram Reel, Tweet text-only, Tweet + sample video, Tweet + generated video)
- **Production**: Configure video template, music, duration → generate Reel videos
- **Distribution**: Post to Instagram and/or Twitter (immediate or scheduled)
- **Schedule Manager**: View/edit/cancel pending posts, see posted and failed items

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Streamlit Dashboard (app.py)                  │
│  Section 1: Ideation  │  Section 2: Edit  │  Section 3: Production  │
│  Section 4: Distribution  │  Section 5: Schedule Manager            │
└────────────────────┬────────────────────────────────────────────────┘
                     │
     ┌───────────────┼───────────────────────────────────┐
     │               │               │                   │
     ▼               ▼               ▼                   ▼
┌──────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────────┐
│  Joke    │  │  Video     │  │  Caption   │  │  Twitter Client  │
│Generator │  │  Studio    │  │  Generator │  │  (OAuth 1.0a/2.0)│
│  Module  │  │  Module    │  │  Module    │  └──────────────────┘
└─────┬────┘  └─────┬──────┘  └─────┬──────┘
      │             │               │
      ▼             ▼               ▼
┌──────────┐  ┌──────────┐  ┌──────────────┐
│ Supabase │  │ Instagram│  │  Scheduler   │
│ (Jokes   │  │ Graph API│  │  Module      │
│  + Embeds)  │ (Upload) │  │  (Supabase)  │
└──────────┘  └──────────┘  └──────┬───────┘
                                   │
                            ┌──────▼───────┐
                            │ GitHub Actions│
                            │ publisher_    │
                            │ script.py     │
                            └──────────────┘
```

**External Services Used:**
- **Supabase** — PostgreSQL database (joke storage, bridge embeddings, scheduled posts) + Storage (video files for scheduled posts)
- **Google Gemini API** — Joke classification/generation, caption generation (model: `gemini-3-flash-preview`)
- **OpenAI API** — Text embeddings (`text-embedding-3-small`), theme expansion (`gpt-4o-mini`)
- **Instagram Graph API v22.0** — Reel upload via resumable upload protocol
- **Twitter API v2 + v1.1** — Tweet posting, chunked video upload
- **GitHub Actions** — Automated publishing and token refresh

---

## 3. Technology Stack

### Python Dependencies (`requirements.txt`)

```
# Core
streamlit>=1.30.0
python-dotenv>=1.0.0

# Joke Generator (Version_12)
google-genai>=1.0.0
openai>=1.0.0
supabase>=2.0.0

# Video Studio (Studio_AutoPost)
moviepy>=2.2.1
Pillow>=11.3.0
numpy>=1.25
requests>=2.31.0

# Twitter/X API
requests-oauthlib>=1.3.1

# Scheduler
pytz>=2023.3
python-dateutil>=2.8.0
```

### System Dependencies (`packages.txt`)

```
ffmpeg
```

> `ffmpeg` is required by MoviePy for video encoding. On Streamlit Cloud, `packages.txt` installs system packages via `apt-get`.

---

## 4. Directory Structure

```
Unified_Content_Engine_Deploy_V5/
├── .env                              # Local environment variables (gitignored)
├── .gitignore
├── .streamlit/
│   ├── config.toml                   # Streamlit theme + server config
│   └── secrets.toml                  # Streamlit Cloud secrets (gitignored)
├── .github/
│   └── workflows/
│       ├── scheduler.yml             # Hourly cron: publish due posts
│       └── refresh_token.yml         # Bi-monthly: refresh Instagram token
├── app.py                            # Main Streamlit dashboard (1494 lines)
├── publisher_script.py               # Standalone publisher for GitHub Actions
├── refresh_instagram_token.py        # Instagram token refresh + GitHub Secret update
├── twitter_oauth1_auth.py            # OAuth 1.0a 3-legged flow for Twitter accounts
├── get_instagram_ids.py              # Utility: list Instagram Business Account IDs
├── requirements.txt                  # Python dependencies
├── packages.txt                      # System dependencies (ffmpeg)
├── temp/                             # Generated video output (gitignored)
├── DOCUMENTATION.md                  # This file
└── modules/
    ├── __init__.py
    ├── caption_generator.py          # AI caption generation (Gemini)
    ├── joke_generator/
    │   ├── __init__.py
    │   ├── campaign_generator.py     # Orchestrator: search + generate
    │   ├── bridge_manager.py         # Theme expansion + bridge creation (OpenAI)
    │   ├── db_manager.py             # Supabase: embeddings + vector search
    │   ├── engine.py                 # Core joke generation pipeline
    │   ├── gemini_client.py          # Gemini API: classify + brainstorm + draft
    │   └── openai_client.py          # OpenAI API wrapper
    ├── video_studio/
    │   ├── __init__.py
    │   ├── studio.py                 # Video generation (MoviePy)
    │   ├── uploader.py               # Instagram Graph API upload
    │   ├── assets/
    │   │   ├── fonts/                # TTF font files (Arial, Georgia, Mulish, etc.)
    │   │   ├── music/                # Background music files (.mp3)
    │   │   └── templates/            # Background video templates (.mp4) + config.json
    │   └── tools/
    │       └── template_editor.html  # Visual tool for configuring text placement
    ├── twitter/
    │   ├── __init__.py
    │   ├── twitter_client.py         # Twitter API client (OAuth 1.0a + 2.0)
    │   ├── credentials/              # Per-account JSON credential files (gitignored)
    │   └── videos/                   # Sample videos for Twitter video tweets
    └── scheduler/
        ├── __init__.py
        ├── scheduler_db.py           # Supabase CRUD for content_schedule table
        └── slot_calculator.py        # Next-available-slot algorithm
```

---

## 5. Environment Variables & Secrets

These must be set in `.env` (local) or `.streamlit/secrets.toml` / GitHub Secrets (production).

### Joke Generator
| Variable | Description | Example |
|---|---|---|
| `GEMINI_API_KEY` | Google Gemini API key | `AIzaSy...` |
| `OPENAI_API_KEY` | OpenAI API key (for embeddings + theme expansion) | `sk-proj-...` |
| `SUPABASE_URL` | Supabase project URL | `https://xxxx.supabase.co` |
| `SUPABASE_KEY` | Supabase anon/public key | `eyJhbG...` |

### Instagram
| Variable | Description |
|---|---|
| `INSTAGRAM_ACCESS_TOKEN` | Long-lived Instagram Graph API access token |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID` | Primary IG Business Account ID (fallback) |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID_1` | IG Business Account ID for account 1 (e.g., "Khushal Page") |
| `INSTAGRAM_BUSINESS_ACCOUNT_ID_2` | IG Business Account ID for account 2 (e.g., "Skin Nurture") |

### Twitter
| Variable | Description |
|---|---|
| `TWITTER_CLIENT_ID` | Twitter Developer App Client ID (OAuth 2.0) |
| `TWITTER_CLIENT_SECRET` | Twitter Developer App Client Secret |
| `TWITTER_CONSUMER_KEY` | Twitter API Key (OAuth 1.0a) — same as App API Key |
| `TWITTER_CONSUMER_SECRET` | Twitter API Secret (OAuth 1.0a) — same as App API Secret |
| `TWITTER_ACCESS_TOKEN_ACCOUNT_1` | OAuth 1.0a access token for account_1 |
| `TWITTER_ACCESS_TOKEN_SECRET_ACCOUNT_1` | OAuth 1.0a access token secret for account_1 |
| `TWITTER_ACCESS_TOKEN_ACCOUNT_2` | OAuth 1.0a access token for account_2 |
| `TWITTER_ACCESS_TOKEN_SECRET_ACCOUNT_2` | OAuth 1.0a access token secret for account_2 |
| `TWITTER_ACCESS_TOKEN_ACCOUNT_3` | OAuth 1.0a access token for account_3 |
| `TWITTER_ACCESS_TOKEN_SECRET_ACCOUNT_3` | OAuth 1.0a access token secret for account_3 |

### GitHub Actions Only
| Variable | Description |
|---|---|
| `GH_PAT` | GitHub Personal Access Token (repo scope) — for updating secrets |
| `GITHUB_REPO` | Repository in `owner/repo` format |

### `.env` File Format

```env
# ─── Joke Generator ─────────────────────────────────────────────
GEMINI_API_KEY=your_gemini_api_key
OPENAI_API_KEY=your_openai_api_key
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key

# ─── Video Studio / Instagram ───────────────────────────────────
INSTAGRAM_ACCESS_TOKEN=your_long_lived_instagram_token
INSTAGRAM_BUSINESS_ACCOUNT_ID=your_primary_ig_id
INSTAGRAM_BUSINESS_ACCOUNT_ID_1=your_ig_account_1_id
INSTAGRAM_BUSINESS_ACCOUNT_ID_2=your_ig_account_2_id

# ─── Twitter (X) API ────────────────────────────────────────────
TWITTER_CLIENT_ID=your_twitter_client_id
TWITTER_CLIENT_SECRET=your_twitter_client_secret
```

---

## 6. Database Schema (Supabase)

### Table: `comic_segments`

Stores jokes with their bridge embeddings for semantic search.

| Column | Type | Description |
|---|---|---|
| `id` | integer (PK) | Auto-increment ID |
| `searchable_text` | text | The original joke text (human-readable) |
| `bridge_content` | text | Abstract 1-sentence description of the joke's logic |
| `bridge_embedding` | vector(1536) | OpenAI embedding of `bridge_content` |

### SQL Function: `match_joke_bridges`

This Supabase RPC function performs vector similarity search:

```sql
CREATE OR REPLACE FUNCTION match_joke_bridges(
  query_embedding vector(1536),
  match_count int DEFAULT 10
)
RETURNS TABLE (
  id bigint,
  searchable_text text,
  bridge_content text,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    cs.id,
    cs.searchable_text,
    cs.bridge_content,
    1 - (cs.bridge_embedding <=> query_embedding) AS similarity
  FROM comic_segments cs
  WHERE cs.bridge_embedding IS NOT NULL
  ORDER BY cs.bridge_embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
```

### Table: `content_schedule`

Stores scheduled, posted, and failed content.

| Column | Type | Description |
|---|---|---|
| `id` | uuid (PK) | Auto-generated UUID |
| `platform` | text | `"instagram"`, `"twitter_text"`, or `"twitter_video"` |
| `video_url` | text (nullable) | Public URL from Supabase Storage (null for text tweets) |
| `caption` | text | The post caption/tweet text |
| `scheduled_time` | timestamptz | When to publish |
| `status` | text | `"pending"`, `"posted"`, or `"failed"` |
| `posted_at` | timestamptz (nullable) | When actually posted |
| `error_message` | text (nullable) | Error details if failed |
| `twitter_account` | text (nullable) | e.g., `"account_1"` |
| `instagram_account` | text (nullable) | e.g., `"khushal_page"` |
| `created_at` | timestamptz | Row creation time |

### Supabase Storage Bucket: `ready_to_publish`

- **Purpose**: Stores video files for scheduled posts. When a post is scheduled, the video is uploaded here. When published, the file is deleted.
- **Access**: Public URLs are used by the publisher script to download videos.

---

## 7. Module 1: Joke Generator

### Overview

The joke generator uses a **"Bridge Embedding"** approach from Version 12 of the comedy pipeline:

1. Each joke in the database has an abstract "bridge" — a 1-sentence description of its comedic mechanism (e.g., "A joke about extreme procrastination where a high-stakes timeline is ignored for comfort")
2. These bridges are embedded as vectors using OpenAI `text-embedding-3-small`
3. When you search for a topic, the topic is expanded into abstract themes, embedded, and matched against bridge vectors
4. The matched reference jokes are then used as templates — Gemini analyzes their structure and generates new jokes on your topic using the same comedic engine

### File: `openai_client.py` — OpenAI API Wrapper

A simple wrapper for OpenAI chat completions.

```python
# Model used: gpt-4o-mini
# Temperature: 0.7 (default)
# Max tokens: 500 (default)
```

**Function**: `generate_content(prompt, model, max_tokens, temperature) → str`

### File: `bridge_manager.py` — Theme Expansion & Bridge Creation

#### Function 1: `expand_headline_to_themes(headline) → str`

Expands a user's topic into abstract themes for better semantic search matching.

**LLM Used**: OpenAI `gpt-4o-mini` (temperature: 0.3, max_tokens: 100)

**Complete Prompt**:

```
Topic: "{headline}"

List 5 abstract themes or concepts associated with this topic.

Example: If topic is 'Traffic', themes are 'Waiting', 'Frustration', 'Wasting Time', 'Trapped'.

OUTPUT: Just the comma-separated themes, nothing else.
```

**Example**: Input `"Bangalore Traffic"` → Output `"Waiting, Frustration, Wasting Time, Trapped, Commuting"`

#### Function 2: `create_joke_bridge(joke_text) → str`

Creates an abstract bridge description for a joke (used when initially populating the database).

**LLM Used**: OpenAI `gpt-4o-mini` (temperature: 0.3, max_tokens: 200)

**Complete Prompt**:

```
Analyze this joke: "{joke_text}"

Write a 1-sentence "Search Description" for this joke.

RULES:
1. Do NOT mention specific nouns (e.g., don't say 'Coma', say 'Long Delay').
2. Focus on the EMOTION and the MECHANISM.
3. Use keywords that describe what kind of topics this joke fits.

Example Output: "A joke about extreme procrastination where a high-stakes timeline is ignored for comfort."

OUTPUT: Just the description, nothing else.
```

### File: `db_manager.py` — Supabase Database Operations

**Functions**:
- `get_supabase_client()` — Creates Supabase client from env vars
- `get_embedding(text) → list` — Generates embedding using OpenAI `text-embedding-3-small`
- `search_by_bridge(query_embedding, match_count) → list` — Calls `match_joke_bridges` RPC function
- `get_all_jokes(limit)` — Fetches jokes from `comic_segments` table
- `update_joke_bridge(joke_id, bridge_content, bridge_embedding)` — Updates bridge data
- `check_bridge_column_exists()` — Validates schema

### File: `gemini_client.py` — Gemini API Client (Core Intelligence)

**Model Configuration**:
```python
MODELS = {
    "classification": "gemini-3-flash-preview",
    "extraction": "gemini-3-flash-preview",
    "generation": "gemini-3-flash-preview",
}
```

#### Function: `classify_joke_type(reference_joke, new_topic) → dict`

This is the **core intelligence** of the app. It takes a reference joke and a new topic, then:
1. Classifies the joke into one of 3 engine types
2. Brainstorms 3 different angles
3. Selects the funniest
4. Drafts the final joke

**LLM Used**: Google Gemini `gemini-3-flash-preview` (temperature: 0.5, JSON output mode)

**Complete System Instruction** (verbatim):

```
You are a Comedy Architect. You reverse-engineer the logic of a reference joke and transplant it into a new topic.

YOUR PROCESS:
1. Analyze the 'Reference Joke' to find the Engine (A, B, or C).
2. BRAINSTORM 3 distinct mapping angles for the New Topic.
3. Select the funniest angle.
4. Draft the final joke.

---
THE ENGINES:

TYPE A: The "Word Trap" (Semantic/Pun)
- Logic: A trigger word bridges two unrelated contexts.
- Mapping: Find a word in the New Topic that has a double meaning. If none exists, FAIL and switch to Type C.

TYPE B: The "Behavior Trap" (Scenario/Character)
- Logic: Character applies a [Mundane Habit] to a [High-Stakes Situation], trivializing it.
- Mapping:
  1. Identify the Abstract Behavior (e.g. "Being Cheap", "Being Lazy", "Professional Deformation").
  2. You may SWAP the specific trait if a better one exists for the New Topic.
     (Example: If Ref is "Snoozing", you can swap to "Haggling" if the New Topic is "Medical Costs").
  3. Apply the Trait to the New Context. DO NOT PUN.

TYPE C: The "Hyperbole Engine" (Roast/Exaggeration)
- Logic: A physical trait is exaggerated until it breaks physics/social norms.
- Mapping:
  1. Identify the Scale (e.g. Size, Weight, Wealth).
  2. Constraint: Conservation of Failure. If Ref fails due to "Lack of Substance," New Joke must also fail due to "Lack of Substance."
  3. Format: Statement ("He is so X..."), NOT a scene.

---
OUTPUT FORMAT (JSON ONLY):
{
  "engine_selected": "Type A/B/C",
  "reasoning": "Explain why this engine fits.",
  "brainstorming": [
    "Option 1: [Trait/Angle] -> [Scenario]",
    "Option 2: [Trait/Angle] -> [Scenario]",
    "Option 3: [Trait/Angle] -> [Scenario]"
  ],
  "selected_strategy": "The best option from above",
  "draft_joke": "The final joke text. Max 40 words. NO FILLER (e.g. 'The health crisis is dire'). Start directly with the setup."
}
```

**Complete User Prompt**:

```
REFERENCE JOKE:
"{reference_joke}"

NEW TOPIC:
"{new_topic}"

Analyze the reference joke, brainstorm 3 mapping angles, select the funniest, and draft the final joke.
```

**JSON Parsing Fallback**: If Gemini returns malformed JSON, the client uses regex to extract `engine_selected`, `reasoning`, `draft_joke`, and `selected_strategy` individually.

#### Function: `call_gemini(prompt, system_instruction, model_stage, temperature, max_tokens, json_output) → dict|str`

Generic Gemini API wrapper. Uses `google.genai` client with `types.GenerateContentConfig`.

### File: `engine.py` — Core Pipeline Orchestrator

#### Function: `generate_v11_joke(reference_joke, new_topic) → dict`

Calls `classify_joke_type()` and validates the response has all required keys: `engine_selected`, `reasoning`, `brainstorming`, `selected_strategy`, `draft_joke`.

#### Function: `regenerate_joke(reference_joke, new_topic, engine_type, previous_draft) → dict`

Regenerates with the same engine type but different angles.

**Complete System Instruction**:

```
You are a Comedy Writer. You have already classified this joke as {engine_type}.

Now generate a DIFFERENT version. Brainstorm 3 NEW angles (different from before).

PREVIOUS DRAFT (DO NOT REPEAT):
"{previous_draft}"

Generate a fresh take using the same {engine_type} logic engine.
```

**Complete User Prompt**:

```
REFERENCE JOKE:
"{reference_joke}"

NEW TOPIC:
"{new_topic}"

FORCED ENGINE TYPE: {engine_type}

Create 3 NEW mapping options and select a different one from before.

OUTPUT JSON:
{
  "engine_selected": "{engine_type}",
  "brainstorming": [
    "New Option 1: [Trait/Angle] -> [Scenario]",
    "New Option 2: [Trait/Angle] -> [Scenario]",
    "New Option 3: [Trait/Angle] -> [Scenario]"
  ],
  "selected_strategy": "The new selected approach",
  "draft_joke": "The new joke (max 40 words, different from previous)"
}
```

### File: `campaign_generator.py` — Public API

**Exported Functions**:

1. `search_bridges(headline, top_k=30) → List[Dict]` — Phase 1: searches bridge embeddings, returns raw matches for user selection (no joke generation)
2. `generate_from_selected(headline, selected_matches) → List[Dict]` — Phase 2: generates jokes only for user-selected bridges
3. `generate_campaign(headline, top_k=10) → List[Dict]` — Full auto pipeline (search + generate all)
4. `generate_campaign_json(headline, top_k=10) → Dict` — JSON wrapper for `generate_campaign`

### Complete Joke Generation Flow

```
User enters topic: "IPL Auction"
        │
        ▼
expand_headline_to_themes("IPL Auction")
  → OpenAI gpt-4o-mini: "Competition, Valuation, Bidding Wars, Expectation, Strategy"
        │
        ▼
get_embedding("Competition, Valuation, Bidding Wars, Expectation, Strategy")
  → OpenAI text-embedding-3-small: [0.023, -0.041, 0.087, ...] (1536-dim vector)
        │
        ▼
search_by_bridge(embedding, match_count=30)
  → Supabase RPC: match_joke_bridges → returns 30 similar jokes with similarity scores
        │
        ▼
User selects 5 bridges from the UI
        │
        ▼
For each selected bridge:
  classify_joke_type(reference_joke, "IPL Auction")
    → Gemini gemini-3-flash-preview: analyzes structure, brainstorms 3 angles, drafts joke
        │
        ▼
Returns list of generated jokes with engine type, strategy, and draft
```

---

## 8. Module 2: Video Studio

### Overview

Generates Instagram Reels (9:16 vertical videos) by compositing:
- A background video template (looped/trimmed to desired duration)
- Text overlay (the joke, rendered via Pillow onto a transparent image)
- Background music (looped/trimmed)

### File: `studio.py`

**Key Constants**:
```python
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "temp")
VIDEO_DURATION = 15  # seconds default
```

#### Function: `generate_reel(joke_text, output_filename, duration, video_path, audio_path) → str`

**Process**:
1. Load background video → loop if shorter than duration, trim if longer
2. Resize to 1080×1920 (9:16 aspect ratio) — crops horizontally if needed
3. Create text overlay via `create_text_image()` — transparent PNG with text
4. Load audio → loop/trim to match duration
5. Composite video + text overlay + audio
6. Export as H.264 MP4 with AAC audio at 24fps

**Output**: Saved to `temp/reel_{n}.mp4`

#### Function: `create_text_image(text, width=1080, height=1920, config=None) → numpy.ndarray`

Creates a transparent RGBA image with the joke text rendered using Pillow.

**Behavior**:
- If `config` is provided (from `config.json`): positions text in the configured `text_area` box, uses configured font/size/color/alignment
- If no config: centers text vertically with a semi-transparent black background box
- **Auto-scaling**: if text overflows the configured area, font size is reduced in steps of 4px down to minimum 16px
- **Text wrapping**: pixel-accurate word wrapping using `draw.textbbox()`
- **Shadow**: optional text shadow (offset by 3px right, 3px down)

#### Font Resolution (`_resolve_font_name`, `_load_font`)

Supports font weight variants: `regular`, `bold`, `semibold`, `light`, `medium`, `extrabold`. Maps to filenames like `Mulish-Regular.ttf`, `TrebuchetMS-Bold.ttf`, etc.

**Fallback chain**: Configured font → Random font from `assets/fonts/` → System default

### Template Configuration (`assets/templates/config.json`)

Each video template has a JSON entry specifying text placement:

```json
{
  "cat.mp4": {
    "text_area": {
      "x": 44,
      "y": 1051,
      "width": 986,
      "height": 300
    },
    "font": "TrebuchetMS-Regular.ttf",
    "font_size": 62,
    "color": "#000000",
    "shadow": null,
    "alignment": "left",
    "font_weight": "medium",
    "padding": 20
  }
}
```

**Config Fields**:
| Field | Type | Description |
|---|---|---|
| `text_area.x` | int | Left edge of text box (px from left) |
| `text_area.y` | int | Top edge of text box (px from top) |
| `text_area.width` | int | Width of text box in pixels |
| `text_area.height` | int | Height of text box in pixels |
| `font` | string | Font filename in `assets/fonts/` |
| `font_size` | int | Initial font size in pixels |
| `color` | string | Text color (hex or name) |
| `shadow` | string/null | Shadow color (null = no shadow) |
| `alignment` | string | `"left"`, `"center"`, or `"right"` |
| `font_weight` | string | `"regular"`, `"bold"`, `"medium"`, etc. |
| `padding` | int | Internal padding within text_area in pixels |

### Visual Template Editor (`tools/template_editor.html`)

A standalone HTML tool for visually configuring text placement on video templates. Opens in a browser, lets you drag/resize the text area, adjust font settings, and exports the JSON config.

### Available Assets

**Fonts** (in `assets/fonts/`):
- Arial-Regular.ttf, Arial-Bold.ttf
- Georgia-Regular.ttf, Georgia-Bold.ttf
- Mulish-Regular.ttf
- TrebuchetMS-Regular.ttf, TrebuchetMS-Bold.ttf
- Verdana-Regular.ttf, Verdana-Bold.ttf

**Music** (in `assets/music/`):
- sample_music.mp3

**Video Templates** (in `assets/templates/`):
27 templates including themed categories:
- General: `New_sample.mp4`, `cat.mp4`, `cat1.mp4`, `jerry.mp4`
- Cricket: `cricket_India_reel.mp4`, `cricket_bumrah_reel.mp4`, `cricket_caught_reel.mp4`, `cricket_crowd_reel.mp4`, `cricket_rain_reel.mp4`, `cricket_random1_reel.mp4`, `cricket_runout_reel.mp4`, `cricket_aus_reel.mp4`
- Office/Lifestyle: `office_boredom_reel.mp4`, `office_boredom1_reel.mp4`, `stock_reel.mp4`, `traffic_reel.mp4`, `scenery_reel.mp4`
- Animals: `cat_typing_reel.mp4`
- Crowds: `cheering_reel.mp4`, `crowd_reel.mp4`, `aus_real.mp4`
- Fallback: `fallback1_reel.mp4` through `fallback6_reel.mp4`

---

## 9. Module 3: Caption Generator

**File**: `modules/caption_generator.py` | **Model**: `gemini-3-flash-preview` (temp: 0.8, JSON mode)

### System Prompt (verbatim)

```
You are an expert Instagram Growth Manager.
I will give you a piece of news and a punchline.
You must generate the JSON output with these exact fields:

1. "caption_hook": A shocking or funny first sentence (under 10 words).
2. "caption_body": Two short sentences explaining the context (include keywords like 'Bengaluru', 'Tech', 'Money', 'Dating').
3. "call_to_action": A question to make people comment (e.g., "Tag a friend who needs to see this").
4. "hashtags": A string of exactly 15 hashtags mixed as follows:
   - 5 Broad Tags (e.g., #india, #news, #funny, #memes, #relatable)
   - 5 Niche Tags (e.g., #bangalorestartups, #corporatehumor, #engineering, #sharktankindia, #financenews)
   - 5 Specific Tags related to the news topic

Return ONLY valid JSON, no markdown fences, no extra text.
```

### User Prompt

```
NEWS/TOPIC: {topic or "General humor"}
PUNCHLINE/JOKE: {joke_text}
Generate the viral caption JSON now.
```

`format_caption(data)` combines hook + body + CTA + hashtags into a single ready-to-post string. Falls back to generic caption if JSON parsing fails.

---

## 10. Module 4: Instagram Uploader

**File**: `modules/video_studio/uploader.py` | **API**: Instagram Graph API v22.0 (Resumable Upload)

### 5-Step Upload Pipeline (`upload_reel()`)

| Step | Method | Endpoint | Purpose |
|---|---|---|---|
| 1 | POST | `graph.facebook.com/v22.0/{ig_id}/media` | Create container (`media_type=REELS, upload_type=resumable`) |
| 2 | POST | `rupload.facebook.com/ig-api-upload/{container_id}` | Upload binary (headers: `Authorization: OAuth {token}`, `offset: 0`, `file_size`, `Content-Type: application/octet-stream`) |
| 3 | GET | `graph.facebook.com/v22.0/{container_id}?fields=status_code` | Poll until `FINISHED` (max 120×5s = 10 min) |
| 4 | POST | `graph.facebook.com/v22.0/{ig_id}/media_publish` | Publish (`creation_id={container_id}`) |
| 5 | GET | `graph.facebook.com/v22.0/{media_id}?fields=permalink` | Get permalink |

Returns `{"media_id": "...", "permalink": "https://www.instagram.com/reel/..."}`. Custom `UploadError` exception for failures.

---

## 11. Module 5: Twitter Client

**File**: `modules/twitter/twitter_client.py` | **Auth**: OAuth 1.0a (media) + OAuth 2.0 (text)

### Class: `TwitterClient(account_name, client_id, client_secret)`

Credentials stored in `modules/twitter/credentials/{account_name}.json`:

```json
{"auth_type": "oauth1", "api_key": "...", "api_secret": "...", "access_token": "...", "access_token_secret": "...", "username": "@handle"}
```

### Key Methods

| Method | Auth | Description |
|---|---|---|
| `post_text_tweet(text)` | OAuth 1.0a preferred, 2.0 fallback | `POST /2/tweets` with `{"text": text}` |
| `upload_media(video_path)` | OAuth 1.0a **required** | v1.1 chunked upload: INIT → APPEND (4MB chunks) → FINALIZE → poll STATUS |
| `post_tweet_with_video(text, video_path)` | OAuth 1.0a | upload_media() + post with `media.media_ids` |
| `get_sample_videos()` | — | Lists `.mp4` files from `modules/twitter/videos/` |

OAuth 2.0 auto-refreshes tokens via `POST /2/oauth2/token` with `grant_type=refresh_token`.

---

## 12. Module 6: Scheduler

### `scheduler_db.py` — Supabase CRUD for `content_schedule` table

| Function | Description |
|---|---|
| `upload_to_storage(file_path)` | Upload video to `ready_to_publish` bucket → returns public URL |
| `insert_schedule(platform, video_url, caption, scheduled_time, twitter_account, instagram_account)` | Create pending post |
| `get_pending_posts()` | Fetch posts where `status=pending AND scheduled_time <= now` |
| `get_all_scheduled(status)` | List all posts, optional status filter |
| `get_last_scheduled_time(platform, twitter_account)` | Last pending time (per-account isolation) |
| `mark_posted(post_id)` / `mark_failed(post_id, error)` | Update status |
| `delete_schedule(post_id)` | Delete post + cleanup Storage file |
| `update_schedule_time(post_id, new_time)` | Reschedule |
| `format_time_ist(iso_string)` | Convert to `"Sat, Feb 15 at 09:00 AM IST"` |

### `slot_calculator.py` — Next Available Slot

**Slots**: 09:00, 14:00, 19:00 IST daily.

**Algorithm** (`get_next_slot(last_scheduled_time)`):
- Empty queue → next future slot today, or first slot tomorrow
- Queue exists → next slot after last scheduled, or first slot next day
- Per-account: each Twitter account has independent slot chains

---

## 13. Publisher Script (GitHub Actions)

**File**: `publisher_script.py` — Standalone (no Streamlit). Runs hourly via GitHub Actions cron.

**Flow**: Query Supabase for due posts → download video from Storage → publish (Instagram/Twitter) → mark posted/failed → cleanup.

**Multi-Account**: Supports 2 Instagram accounts + 3 Twitter accounts via env vars (`TWITTER_ACCESS_TOKEN_ACCOUNT_1`, etc.).

| Platform | Action |
|---|---|
| `instagram` | Download video → Resumable upload pipeline |
| `twitter_text` | OAuth 1.0a `POST /2/tweets` |
| `twitter_video` | Download video → v1.1 chunked upload → tweet with media_id |

---

## 14. The Main Dashboard (`app.py` — 1494 lines)

### Theme & Config

```toml
# .streamlit/config.toml
[server]
maxUploadSize = 200
headless = true
port = 8501

[theme]
primaryColor = "#667eea"
backgroundColor = "#0e1117"
secondaryBackgroundColor = "#1e1e2e"
textColor = "#e2e8f0"
```

### Session State (key variables)

`bridge_matches`, `selected_bridge_indices`, `bridge_selection_done`, `jokes`, `selected_indices`, `edited_texts`, `distribution_choices`, `video_paths`, `upload_results`, `tweet_results`, `schedule_results`, `ig_captions`, `tw_captions`

### 5 Sections

**Section 1 — Ideation**: Topic input → `search_bridges(topic, 30)` → checkboxes for bridge selection → `generate_from_selected()` → joke cards with engine/strategy/draft.

**Section 2 — Edit & Choose**: Editable text areas per joke + character counter (280 for Twitter) + distribution channel checkboxes (IG Reel / Tweet text / Tweet sample video / Tweet generated video).

**Section 3 — Production**: Template dropdown + music dropdown + duration slider → `generate_reel()` per joke → video preview.

**Section 4 — Distribution**: IG account selector + Twitter account selector. Per joke: AI caption generation/edit, "Post Now" vs "Schedule" radio. Posts immediately or schedules via `insert_schedule()`.

**Section 5 — Schedule Manager**: 3 tabs (Pending/Posted/Failed). Pending posts have reschedule/cancel buttons.

### Pipeline Status Bar

CSS-animated 5-step indicator: `done` (green) → `active` (blue, pulsing) → `pending` (gray).

---

## 15. Utility Scripts

### `refresh_instagram_token.py`
Refreshes 60-day IG token via `GET https://graph.instagram.com/refresh_access_token`. With `--update-secret` flag, encrypts new token (libsodium sealed box) and updates GitHub Secret via API. Requires `PyNaCl`.

### `twitter_oauth1_auth.py`
3-legged OAuth 1.0a PIN-based flow: `python twitter_oauth1_auth.py account_2`. Gets request token → opens browser → user enters PIN → exchanges for access token → saves to `credentials/{account}.json`. Reads app key/secret from `account_1.json`.

### `get_instagram_ids.py`
Lists all Facebook Pages + linked IG Business Account IDs: `GET /v19.0/me/accounts?fields=name,instagram_business_account`.

---

## 16. GitHub Actions Workflows

### `scheduler.yml` — Hourly Publisher
- **Cron**: `0 * * * *` (every hour) + manual dispatch
- **Runs**: `python publisher_script.py`
- **Env**: All Supabase + Instagram + Twitter secrets

### `refresh_token.yml` — Bi-Monthly Token Refresh
- **Cron**: `0 6 1,15 * *` (1st & 15th of month at 06:00 UTC)
- **Runs**: `python refresh_instagram_token.py --update-secret`
- **Deps**: `requests`, `PyNaCl`

---

## 17. Deployment Guide (Streamlit Cloud)

1. Push to GitHub (ensure `.gitignore` excludes `.env`, `credentials/`, `temp/`)
2. Create app on [share.streamlit.io](https://share.streamlit.io), point to `app.py`
3. Add all env vars to Streamlit Secrets (TOML format)
4. Add same vars to GitHub Secrets for Actions
5. `app.py` injects Streamlit secrets into `os.environ` at startup:
   ```python
   for key, value in st.secrets.items():
       if isinstance(value, str): os.environ[key] = value
   ```

---

## 18. How to Clone from Scratch

1. Python 3.10+ and `ffmpeg` installed
2. `pip install -r requirements.txt`
3. Create `.env` with all keys (Section 5)
4. **Supabase**: Create `comic_segments` table (id, searchable_text, bridge_content, bridge_embedding vector(1536)), create `content_schedule` table (Section 6), create `match_joke_bridges` RPC function, create `ready_to_publish` storage bucket
5. Populate `comic_segments` with reference jokes + run `bridge_manager.create_joke_bridge()` + `db_manager.get_embedding()` for each
6. **Instagram**: Get long-lived token, run `get_instagram_ids.py` for Business Account IDs
7. **Twitter**: Create Dev App (OAuth 2.0 PKCE + 1.0a), authorize via sidebar or `twitter_oauth1_auth.py`
8. Add video templates + configure in `config.json` (use `template_editor.html`)
9. `streamlit run app.py`
10. Deploy to Streamlit Cloud (Section 17)

---

*Generated from full analysis of all source files in Unified Content Engine V5.*
