"""
Unified Content Engine V6 — Streamlit Dashboard (Modular Edition)
Every section works independently — no sequential gating.
Sidebar tabs: Joke Generator | Caption Studio | Post to IG | Post to Twitter | Video Studio | Schedule Manager | Daily News Jokes

Run:  streamlit run app.py
"""

import streamlit as st
import os
import sys
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# ─── Bootstrap ────────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).parent / ".env")

PROJECT_ROOT = str(Path(__file__).parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Unified Content Engine V6",
    page_icon="🎭",
    layout="wide",
)

# ─── Bridge Streamlit Cloud Secrets → os.environ ─────────────────────────────
try:
    for key, value in st.secrets.items():
        if isinstance(value, str) and key not in os.environ:
            os.environ[key] = value
except Exception:
    pass

# ─── Bootstrap Twitter Credential Files ──────────────────────────────────────
import json as _json

_TWITTER_CREDS_DIR = Path(__file__).parent / "modules" / "twitter" / "credentials"
_TWITTER_CREDS_DIR.mkdir(parents=True, exist_ok=True)

_TW_API_KEY = os.environ.get("TWITTER_CONSUMER_KEY", "")
_TW_API_SECRET = os.environ.get("TWITTER_CONSUMER_SECRET", "")

_TW_ACCOUNTS = {
    "account_1": {
        "token_env": "TWITTER_ACCESS_TOKEN_ACCOUNT_1",
        "secret_env": "TWITTER_ACCESS_TOKEN_SECRET_ACCOUNT_1",
    },
    "account_2": {
        "token_env": "TWITTER_ACCESS_TOKEN_ACCOUNT_2",
        "secret_env": "TWITTER_ACCESS_TOKEN_SECRET_ACCOUNT_2",
    },
    "account_3": {
        "token_env": "TWITTER_ACCESS_TOKEN_ACCOUNT_3",
        "secret_env": "TWITTER_ACCESS_TOKEN_SECRET_ACCOUNT_3",
    },
}

for _acct_name, _acct_envs in _TW_ACCOUNTS.items():
    _cred_file = _TWITTER_CREDS_DIR / f"{_acct_name}.json"
    if not _cred_file.exists():
        _token = os.environ.get(_acct_envs["token_env"], "")
        _secret = os.environ.get(_acct_envs["secret_env"], "")
        if _token and _secret and _TW_API_KEY:
            _cred_data = {
                "auth_type": "oauth1",
                "api_key": _TW_API_KEY,
                "api_secret": _TW_API_SECRET,
                "access_token": _token,
                "access_token_secret": _secret,
            }
            with open(_cred_file, "w") as _f:
                _json.dump(_cred_data, _f, indent=2)

# ─── Start Background Auto-Publisher ─────────────────────────────────────────
# Runs a daemon thread that checks Supabase every 60s for due scheduled posts
# and publishes them automatically (Instagram, Twitter text, Twitter video).

@st.cache_resource
def _init_auto_publisher():
    """Start the auto-publisher thread (runs once per Streamlit server)."""
    try:
        from modules.scheduler.auto_publisher import start_publisher
        start_publisher()
        return True
    except Exception as e:
        print(f"⚠️ Auto-publisher failed to start: {e}")
        return False

_auto_publisher_active = _init_auto_publisher()


# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    * { font-family: 'Inter', sans-serif; }

    .hero-title {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.6rem;
        font-weight: 800;
        letter-spacing: -0.5px;
        margin-bottom: 0;
    }
    .hero-sub {
        color: #94a3b8;
        font-size: 1rem;
        font-weight: 400;
        margin-top: -8px;
        margin-bottom: 20px;
    }

    .section-header {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 12px 0 8px 0;
    }
    .section-header .icon { font-size: 1.5rem; }
    .section-header .label {
        font-size: 1.2rem;
        font-weight: 700;
        color: #e2e8f0;
    }
    .section-header .desc {
        font-size: 0.85rem;
        color: #64748b;
        font-weight: 400;
    }

    .joke-card {
        background: rgba(30, 30, 46, 0.7);
        border: 1px solid rgba(100, 116, 139, 0.2);
        border-radius: 12px;
        padding: 16px 20px;
        margin: 8px 0;
        transition: all 0.2s ease;
    }
    .joke-card:hover {
        border-color: rgba(102, 126, 234, 0.5);
        box-shadow: 0 4px 20px rgba(102, 126, 234, 0.1);
    }
    .joke-text {
        color: #e2e8f0;
        font-size: 0.95rem;
        line-height: 1.6;
    }
    .joke-meta {
        display: flex;
        gap: 16px;
        margin-top: 8px;
        font-size: 0.75rem;
        color: #64748b;
    }
    .joke-meta .badge {
        background: rgba(102, 126, 234, 0.15);
        color: #818cf8;
        padding: 2px 10px;
        border-radius: 20px;
        font-weight: 600;
    }

    .status-ok {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .status-warn {
        background: rgba(251, 191, 36, 0.15);
        color: #fbbf24;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid rgba(251, 191, 36, 0.3);
    }
    .status-error {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }

    .status-scheduled {
        background: rgba(139, 92, 246, 0.15);
        color: #a78bfa;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid rgba(139, 92, 246, 0.3);
    }
    .schedule-card {
        background: rgba(30, 30, 46, 0.7);
        border: 1px solid rgba(139, 92, 246, 0.2);
        border-radius: 12px;
        padding: 14px 18px;
        margin: 6px 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .twitter-badge {
        background: rgba(29, 155, 240, 0.15);
        color: #1d9bf0;
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid rgba(29, 155, 240, 0.3);
    }

    .char-count {
        font-size: 0.75rem;
        color: #64748b;
        text-align: right;
        margin-top: -8px;
    }
    .char-count.over { color: #f87171; font-weight: 600; }

    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;
        padding: 0.6rem 2rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4);
    }

    .divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(100, 116, 139, 0.3), transparent);
        margin: 24px 0;
    }

    /* News workflow cards */
    .headline-card {
        background: rgba(30, 30, 46, 0.7);
        border: 1px solid rgba(251, 191, 36, 0.3);
        border-radius: 12px;
        padding: 14px 18px;
        margin: 6px 0;
    }
    .headline-card .title {
        color: #fbbf24;
        font-weight: 700;
        font-size: 1rem;
    }
</style>
""", unsafe_allow_html=True)


# ─── Session State Defaults ──────────────────────────────────────────────────

defaults = {
    # Joke Generator tab
    "bridge_matches": [],
    "selected_bridge_indices": [],
    "bridge_selection_done": False,
    "jokes": [],
    "selected_indices": [],
    "edited_texts": {},
    "distribution_choices": {},
    "video_paths": {},
    "upload_results": {},
    "tweet_results": {},
    "schedule_results": {},
    "generation_done": False,
    "videos_done": False,
    "twitter_account": None,
    "twitter_user_info": None,
    "generated_captions": {},
    # Daily News Jokes tab
    "news_headlines": [],
    "news_jokes": {},           # {headline: [joke_dicts]}
    "news_pipeline_done": False,
    "news_pipeline_log": "",
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ─── Helpers ──────────────────────────────────────────────────────────────────

def scan_assets(subfolder, extensions):
    """Scan assets directory for files."""
    from modules.video_studio.studio import ASSETS_DIR
    target = os.path.join(ASSETS_DIR, subfolder)
    if not os.path.exists(target):
        return []
    return sorted([
        f for f in os.listdir(target)
        if f.lower().endswith(extensions) and not f.startswith(".")
    ])


def get_joke_text(idx):
    """Get the final (edited or original) joke text for an index."""
    return st.session_state.edited_texts.get(
        idx,
        st.session_state.jokes[idx].get("joke", "")
    )


# ─── Header ──────────────────────────────────────────────────────────────────

st.markdown('<p class="hero-title">Unified Content Engine</p>', unsafe_allow_html=True)
st.markdown('<p class="hero-sub">V6 — Every feature works independently. Jump to any section.</p>', unsafe_allow_html=True)
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)


# ─── Sidebar Navigation ─────────────────────────────────────────────────────

PAGES = [
    "🧠 Joke Generator",
    "✨ Caption Generator",
    "🎬 Video Studio",
    "📸 Post to Instagram",
    "🐦 Post to Twitter",
    "📅 Schedule Manager",
    "📰 Daily News Jokes",
    "🐦 Tweet Reply Studio",
]

with st.sidebar:
    st.markdown("### 🎭 Navigation")
    page = st.radio(
        "Go to",
        PAGES,
        label_visibility="collapsed",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAGE: JOKE GENERATOR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if page == "🧠 Joke Generator":
    st.markdown("""
    <div class="section-header">
        <span class="icon">🧠</span>
        <span class="label">Joke Generator</span>
        <span class="desc">Search bridge structures → Select the best ones → Generate jokes</span>
    </div>
    """, unsafe_allow_html=True)

    topic = st.text_input(
        "Topic / Headline",
        placeholder="e.g. Bangalore Traffic, IPL Auction, Inflation...",
        label_visibility="collapsed",
    )

    col_search, col_reset = st.columns([4, 1])

    with col_search:
        search_btn = st.button(
            "🔍 Search Bridges",
            type="primary",
            use_container_width=True,
            disabled=not topic.strip(),
        )
    with col_reset:
        reset_btn = st.button("🔄 New Search", use_container_width=True)

    if reset_btn:
        for key in ["bridge_matches", "selected_bridge_indices", "bridge_selection_done",
                     "jokes", "selected_indices", "edited_texts", "distribution_choices",
                     "video_paths", "upload_results", "tweet_results", "generation_done",
                     "videos_done"]:
            st.session_state[key] = defaults[key]
        st.rerun()

    # Phase 1: Bridge Search
    if search_btn and topic.strip():
        with st.spinner("🔍 Expanding themes and searching bridge embeddings..."):
            try:
                from modules.joke_generator.campaign_generator import search_bridges
                matches = search_bridges(topic.strip(), top_k=30)
                st.session_state.bridge_matches = matches
                st.session_state.selected_bridge_indices = []
                st.session_state.bridge_selection_done = False
                st.session_state.jokes = []
                st.session_state.selected_indices = []
                st.session_state.edited_texts = {}
                st.session_state.distribution_choices = {}
                st.session_state.video_paths = {}
                st.session_state.upload_results = {}
                st.session_state.tweet_results = {}
                st.session_state.generation_done = False
                st.session_state.videos_done = False
                st.rerun()
            except Exception as e:
                st.error(f"❌ Bridge search failed: {e}")

    # Phase 1 Results
    if st.session_state.bridge_matches and not st.session_state.generation_done:
        st.markdown(
            f"**{len(st.session_state.bridge_matches)} bridge structures found** — "
            f"select the ones you want to generate jokes from:"
        )

        col_sel_all, col_desel_all, _ = st.columns([1, 1, 4])
        with col_sel_all:
            if st.button("✅ Select All", use_container_width=True):
                st.session_state.selected_bridge_indices = list(
                    range(len(st.session_state.bridge_matches))
                )
                st.rerun()
        with col_desel_all:
            if st.button("❎ Deselect All", use_container_width=True):
                st.session_state.selected_bridge_indices = []
                st.rerun()

        for i, match in enumerate(st.session_state.bridge_matches):
            col_check, col_bridge = st.columns([0.05, 0.95])

            with col_check:
                selected = st.checkbox(
                    "sel",
                    key=f"bridge_sel_{i}",
                    value=i in st.session_state.selected_bridge_indices,
                    label_visibility="collapsed",
                )
                if selected and i not in st.session_state.selected_bridge_indices:
                    st.session_state.selected_bridge_indices.append(i)
                elif not selected and i in st.session_state.selected_bridge_indices:
                    st.session_state.selected_bridge_indices.remove(i)

            with col_bridge:
                joke_text = match.get("searchable_text", "N/A")
                bridge = match.get("bridge_content", "")
                similarity = match.get("similarity", 0)
                display_text = joke_text[:200] + "..." if len(joke_text) > 200 else joke_text

                st.markdown(f"""
                <div class="joke-card">
                    <div class="joke-text">{display_text}</div>
                    <div class="joke-meta">
                        <span class="badge">#{i + 1}</span>
                        <span>Similarity: {similarity:.3f}</span>
                        <span>🌉 {bridge[:80]}{'...' if len(bridge) > 80 else ''}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        num_selected = len(st.session_state.selected_bridge_indices)

        generate_btn = st.button(
            f"🔥 Generate {num_selected} Joke{'s' if num_selected != 1 else ''}"
            if num_selected > 0 else "🔥 Select bridges above first",
            type="primary",
            use_container_width=True,
            disabled=num_selected == 0,
        )

        if generate_btn and num_selected > 0:
            selected_matches = [
                st.session_state.bridge_matches[i]
                for i in sorted(st.session_state.selected_bridge_indices)
            ]
            with st.spinner(f"🔥 Generating {num_selected} jokes via Gemini..."):
                try:
                    from modules.joke_generator.campaign_generator import generate_from_selected
                    results = generate_from_selected(topic.strip(), selected_matches)
                    st.session_state.jokes = results
                    st.session_state.generation_done = True
                    st.session_state.bridge_selection_done = True
                    st.session_state.selected_indices = []
                    st.session_state.edited_texts = {}
                    st.session_state.distribution_choices = {}
                    st.session_state.video_paths = {}
                    st.session_state.upload_results = {}
                    st.session_state.tweet_results = {}
                    st.session_state.videos_done = False
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Generation failed: {e}")

    # Generated Jokes Display
    if st.session_state.jokes:
        st.markdown(f"**{len(st.session_state.jokes)} jokes generated:**")

        for i, joke_data in enumerate(st.session_state.jokes):
            engine = joke_data.get("engine", "?")
            similarity = joke_data.get("similarity", 0)

            st.markdown(f"""
            <div class="joke-card">
                <div class="joke-text">{joke_data.get('joke', 'N/A')}</div>
                <div class="joke-meta">
                    <span class="badge">{engine}</span>
                    <span>Similarity: {similarity:.2f}</span>
                    <span>Strategy: {joke_data.get('selected_strategy', 'N/A')[:60]}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Copy button
            if st.button(f"📋 Copy Joke #{i+1}", key=f"copy_joke_{i}"):
                st.code(joke_data.get("joke", ""), language=None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAGE: CAPTION GENERATOR (Standalone)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

elif page == "✨ Caption Generator":
    st.markdown("""
    <div class="section-header">
        <span class="icon">✨</span>
        <span class="label">Caption Generator</span>
        <span class="desc">Generate viral-ready captions for any text — no prerequisites needed</span>
    </div>
    """, unsafe_allow_html=True)

    caption_input = st.text_area(
        "Enter your joke, punchline, or any text",
        placeholder="Paste your joke text here, e.g. 'Bangalore traffic is so bad, my GPS gave up and said — walk.'",
        height=120,
        key="caption_input_text",
    )

    caption_topic = st.text_input(
        "Topic (optional, helps improve hashtags)",
        placeholder="e.g. Bangalore Traffic, IPL, Startup Life...",
        key="caption_topic_input",
    )

    col_gen, col_platform = st.columns([3, 1])

    with col_platform:
        platform = st.selectbox("Platform", ["Instagram", "Twitter"], key="caption_platform")

    with col_gen:
        gen_caption_btn = st.button(
            "✨ Generate Caption",
            type="primary",
            use_container_width=True,
            disabled=not caption_input.strip(),
        )

    if gen_caption_btn and caption_input.strip():
        with st.spinner("✨ Generating viral caption..."):
            try:
                from modules.caption_generator import generate_caption, format_caption
                plat = platform.lower()
                raw = generate_caption(caption_input.strip(), topic=caption_topic if caption_topic else "", platform=plat)
                formatted = format_caption(raw, platform=plat)

                st.markdown("### 📝 Generated Caption")
                st.text_area("Caption (edit as needed)", value=formatted, height=200, key="generated_caption_output")

                # Show structured data
                with st.expander("📊 Structured Data"):
                    st.json(raw)

            except Exception as e:
                st.error(f"❌ Caption generation failed: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAGE: VIDEO STUDIO (Standalone)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

elif page == "🎬 Video Studio":
    st.markdown("""
    <div class="section-header">
        <span class="icon">🎬</span>
        <span class="label">Video Studio</span>
        <span class="desc">Turn any text into an Instagram Reel with video templates + music</span>
    </div>
    """, unsafe_allow_html=True)

    video_joke_text = st.text_area(
        "Enter joke / text for the Reel",
        placeholder="Type or paste your joke text here...",
        height=100,
        key="video_studio_text",
    )

    templates = scan_assets("templates", (".mp4", ".mov"))
    templates = [t for t in templates if not t.endswith(".json")]
    music_files = scan_assets("music", (".mp3", ".wav", ".m4a"))

    col_template, col_music, col_duration = st.columns([2, 2, 1])

    with col_template:
        selected_template = st.selectbox(
            "🎥 Video Template",
            templates if templates else ["No templates found"],
            help="Background video for the Reel"
        )

    with col_music:
        selected_music = st.selectbox(
            "🎵 Music Track",
            music_files if music_files else ["No music found"],
            help="Background audio track"
        )

    with col_duration:
        duration = st.number_input("⏱ Duration (s)", min_value=5, max_value=60, value=15, step=5)

    can_produce = bool(video_joke_text.strip() and templates and music_files)

    produce_btn = st.button(
        "🎬 Generate Video",
        type="primary",
        use_container_width=True,
        disabled=not can_produce
    )

    if produce_btn and can_produce:
        from modules.video_studio.studio import generate_reel, ASSETS_DIR

        with st.spinner("🎬 Rendering video..."):
            try:
                video_path = os.path.join(ASSETS_DIR, "templates", selected_template)
                audio_path = os.path.join(ASSETS_DIR, "music", selected_music)

                result_path = generate_reel(
                    video_joke_text.strip(),
                    output_filename="reel_standalone.mp4",
                    duration=duration,
                    video_path=video_path,
                    audio_path=audio_path
                )
                st.session_state["standalone_video_path"] = result_path
                st.success("✅ Video generated!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Video generation failed: {e}")

    # Show generated video
    if st.session_state.get("standalone_video_path"):
        vpath = st.session_state["standalone_video_path"]
        if os.path.exists(vpath):
            st.markdown("### 🎞️ Generated Reel")
            st.video(vpath)
            st.caption(f"File: `{vpath}`")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAGE: POST TO INSTAGRAM (Standalone)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

elif page == "📸 Post to Instagram":
    st.markdown("""
    <div class="section-header">
        <span class="icon">📸</span>
        <span class="label">Post to Instagram</span>
        <span class="desc">Upload a video and post as an Instagram Reel — no prerequisites</span>
    </div>
    """, unsafe_allow_html=True)

    ig_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")

    IG_ACCOUNT_OPTIONS = {
        "khushal_page": {
            "label": "📸 Khushal Page",
            "id": os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID_1", os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID")),
        },
        "skin_nurture": {
            "label": "🌿 Skin Nurture",
            "id": os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID_2"),
        },
    }

    ig_account_keys = list(IG_ACCOUNT_OPTIONS.keys())
    ig_account_labels = [IG_ACCOUNT_OPTIONS[k]["label"] for k in ig_account_keys]

    selected_ig_idx = st.selectbox(
        "📸 Instagram Account",
        range(len(ig_account_keys)),
        format_func=lambda i: ig_account_labels[i],
    )
    selected_ig_account = ig_account_keys[selected_ig_idx]
    ig_account_id = IG_ACCOUNT_OPTIONS[selected_ig_account]["id"]
    ig_creds_ok = bool(ig_token and ig_account_id)

    if ig_creds_ok:
        st.markdown(f'<span class="status-ok">✅ {IG_ACCOUNT_OPTIONS[selected_ig_account]["label"]} Connected</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-error">❌ Missing Instagram credentials</span>', unsafe_allow_html=True)

    st.markdown("---")

    # Video source: either upload or use a generated video path
    video_source = st.radio(
        "Video source",
        ["📁 Use generated video path", "📤 Upload video file"],
        horizontal=True,
    )

    ig_video_path = None
    if video_source == "📁 Use generated video path":
        ig_video_path_input = st.text_input(
            "Video file path",
            value=st.session_state.get("standalone_video_path", ""),
            placeholder="/path/to/your/video.mp4",
        )
        if ig_video_path_input and os.path.exists(ig_video_path_input):
            ig_video_path = ig_video_path_input
            st.video(ig_video_path)
        elif ig_video_path_input:
            st.warning("⚠️ File not found at this path.")
    else:
        ig_uploaded = st.file_uploader("Upload .mp4 video", type=["mp4", "mov"], key="ig_upload")
        if ig_uploaded:
            temp_dir = Path(__file__).parent / "temp"
            temp_dir.mkdir(exist_ok=True)
            temp_path = temp_dir / ig_uploaded.name
            with open(temp_path, "wb") as f:
                f.write(ig_uploaded.getbuffer())
            ig_video_path = str(temp_path)
            st.video(ig_video_path)

    ig_caption = st.text_area(
        "Caption",
        placeholder="Your Instagram caption...",
        height=150,
        key="ig_standalone_caption",
    )

    # AI Caption generation
    col_ai_gen, _ = st.columns([1, 3])
    with col_ai_gen:
        if st.button("✨ Generate Caption", key="ig_ai_caption_btn"):
            if ig_caption.strip():
                with st.spinner("✨ Generating..."):
                    try:
                        from modules.caption_generator import generate_caption, format_caption
                        raw = generate_caption(ig_caption.strip(), platform="instagram")
                        formatted = format_caption(raw, platform="instagram")
                        st.session_state["ig_standalone_caption"] = formatted
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")
            else:
                st.warning("Enter some text in the caption box first.")

    col_post, col_sched = st.columns(2)

    with col_post:
        ig_post_btn = st.button(
            "📤 Post Now",
            type="primary",
            use_container_width=True,
            disabled=not (ig_creds_ok and ig_video_path and ig_caption.strip()),
        )

        if ig_post_btn:
            with st.spinner(f"📤 Uploading Reel to {IG_ACCOUNT_OPTIONS[selected_ig_account]['label']}..."):
                try:
                    from modules.video_studio.uploader import upload_reel
                    result = upload_reel(
                        access_token=ig_token,
                        ig_user_id=ig_account_id,
                        file_path=ig_video_path,
                        caption=ig_caption,
                    )
                    permalink = result.get("permalink", "")
                    if permalink:
                        st.success(f"✅ Posted! [View →]({permalink})")
                    else:
                        st.success("✅ Posted successfully!")
                except Exception as e:
                    st.error(f"❌ Upload failed: {e}")

    with col_sched:
        ig_sched_btn = st.button(
            "📅 Schedule",
            use_container_width=True,
            disabled=not (ig_creds_ok and ig_video_path and ig_caption.strip()),
        )

        if ig_sched_btn:
            with st.spinner("📅 Scheduling..."):
                try:
                    from modules.scheduler.scheduler_db import (
                        upload_to_storage, insert_schedule, get_last_scheduled_time
                    )
                    from modules.scheduler.slot_calculator import get_next_slot, format_slot_display

                    public_url = upload_to_storage(ig_video_path)
                    last_time = get_last_scheduled_time(platform="instagram", twitter_account=None)
                    next_slot = get_next_slot(last_time)
                    display_time = format_slot_display(next_slot)

                    insert_schedule(
                        platform="instagram",
                        video_url=public_url,
                        caption=ig_caption,
                        scheduled_time=next_slot,
                        instagram_account=selected_ig_account,
                    )
                    st.success(f"📅 Scheduled for {display_time}")
                except Exception as e:
                    st.error(f"❌ Scheduling failed: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAGE: POST TO TWITTER (Standalone)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

elif page == "🐦 Post to Twitter":
    st.markdown("""
    <div class="section-header">
        <span class="icon">🐦</span>
        <span class="label">Post to Twitter</span>
        <span class="desc">Tweet text or text + video — no prerequisites needed</span>
    </div>
    """, unsafe_allow_html=True)

    from modules.twitter.twitter_client import (
        TwitterClient, TwitterClientError, list_accounts, list_sample_videos,
        VIDEOS_DIR
    )

    accounts = list_accounts()

    if not accounts:
        st.markdown(
            '<span class="status-error">❌ No Twitter accounts found. '
            'Add credential files to modules/twitter/credentials/</span>',
            unsafe_allow_html=True,
        )
    else:
        col_account, col_status = st.columns([2, 3])

        with col_account:
            selected_account = st.selectbox(
                "🐦 Twitter Account",
                accounts,
                index=accounts.index(st.session_state.twitter_account) if st.session_state.twitter_account in accounts else 0,
            )

        with col_status:
            if selected_account != st.session_state.twitter_account:
                st.session_state.twitter_account = selected_account
                st.session_state.twitter_user_info = None

            if st.session_state.twitter_user_info is None and selected_account:
                try:
                    client = TwitterClient(selected_account)
                    user_info = client.get_me()
                    st.session_state.twitter_user_info = user_info
                except Exception as e:
                    st.session_state.twitter_user_info = {"error": str(e)}

            info = st.session_state.twitter_user_info
            if info and "error" not in info:
                username = info.get("username", "???")
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(
                    f'<span class="twitter-badge">@{username}</span> '
                    f'<span class="status-ok">Connected</span>',
                    unsafe_allow_html=True,
                )
            elif info and "error" in info:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(
                    f'<span class="status-error">❌ {info["error"][:80]}</span>',
                    unsafe_allow_html=True,
                )

        st.markdown("---")

        tweet_text = st.text_area(
            "Tweet text",
            placeholder="Type your tweet...",
            height=100,
            key="tw_standalone_text",
        )

        char_count = len(tweet_text)
        over_class = "over" if char_count > 280 else ""
        st.markdown(
            f'<div class="char-count {over_class}">{char_count}/280 chars</div>',
            unsafe_allow_html=True,
        )

        # AI Caption
        if st.button("✨ Generate Caption", key="tw_ai_caption_btn"):
            if tweet_text.strip():
                with st.spinner("✨ Generating..."):
                    try:
                        from modules.caption_generator import generate_caption, format_caption
                        raw = generate_caption(tweet_text.strip(), platform="twitter")
                        formatted = format_caption(raw, platform="twitter")
                        st.session_state["tw_standalone_text"] = formatted
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")

        # Video attachment
        attach_video = st.checkbox("🎬 Attach video", key="tw_attach_video")

        tw_video_path = None
        if attach_video:
            tw_video_source = st.radio(
                "Video source",
                ["📂 Sample videos", "📁 Custom path", "📤 Upload"],
                horizontal=True,
                key="tw_video_source",
            )

            if tw_video_source == "📂 Sample videos":
                sample_videos = list_sample_videos()
                if sample_videos:
                    selected_sample = st.selectbox("Select sample", sample_videos, key="tw_sample_sel")
                    tw_video_path = os.path.join(str(VIDEOS_DIR), selected_sample)
                    if os.path.exists(tw_video_path):
                        st.video(tw_video_path)
                else:
                    st.warning("No sample videos found.")
            elif tw_video_source == "📁 Custom path":
                tw_custom_path = st.text_input(
                    "Video file path",
                    value=st.session_state.get("standalone_video_path", ""),
                    key="tw_custom_video_path",
                )
                if tw_custom_path and os.path.exists(tw_custom_path):
                    tw_video_path = tw_custom_path
                    st.video(tw_video_path)
            else:
                tw_uploaded = st.file_uploader("Upload .mp4", type=["mp4"], key="tw_upload")
                if tw_uploaded:
                    temp_dir = Path(__file__).parent / "temp"
                    temp_dir.mkdir(exist_ok=True)
                    temp_path = temp_dir / tw_uploaded.name
                    with open(temp_path, "wb") as f:
                        f.write(tw_uploaded.getbuffer())
                    tw_video_path = str(temp_path)
                    st.video(tw_video_path)

        too_long = char_count > 280
        can_tweet = bool(accounts and not too_long and tweet_text.strip())
        if attach_video and not tw_video_path:
            can_tweet = False

        col_tw_post, col_tw_sched = st.columns(2)

        with col_tw_post:
            post_tweet_btn = st.button(
                "🐦 Tweet Now",
                type="primary",
                use_container_width=True,
                disabled=not can_tweet,
            )

            if post_tweet_btn:
                with st.spinner("🐦 Posting tweet..."):
                    try:
                        client = TwitterClient(selected_account)
                        if attach_video and tw_video_path:
                            result = client.post_tweet_with_video(tweet_text, tw_video_path)
                        else:
                            result = client.post_tweet(tweet_text)

                        tweet_id = result.get("id", "???")
                        tw_username = (st.session_state.twitter_user_info or {}).get("username", "???")
                        tweet_url = f"https://twitter.com/{tw_username}/status/{tweet_id}"
                        st.success(f"✅ Tweeted! [View →]({tweet_url})")
                    except TwitterClientError as e:
                        st.error(f"❌ Tweet failed: {e}")
                    except Exception as e:
                        st.error(f"❌ Unexpected error: {e}")

        with col_tw_sched:
            sched_tw_btn = st.button(
                "📅 Schedule",
                use_container_width=True,
                disabled=not can_tweet,
            )

            if sched_tw_btn:
                with st.spinner("📅 Scheduling tweet..."):
                    try:
                        from modules.scheduler.scheduler_db import (
                            upload_to_storage, insert_schedule, get_last_scheduled_time
                        )
                        from modules.scheduler.slot_calculator import get_next_slot, format_slot_display

                        platform = "twitter_video" if attach_video and tw_video_path else "twitter_text"
                        video_url = None

                        if platform == "twitter_video":
                            video_url = upload_to_storage(tw_video_path)

                        last_time = get_last_scheduled_time(
                            platform=platform, twitter_account=selected_account
                        )
                        next_slot = get_next_slot(last_time)
                        display_time = format_slot_display(next_slot)

                        insert_schedule(
                            platform=platform,
                            video_url=video_url,
                            caption=tweet_text,
                            scheduled_time=next_slot,
                            twitter_account=selected_account,
                        )
                        st.success(f"📅 Scheduled for {display_time}")
                    except Exception as e:
                        st.error(f"❌ Scheduling failed: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAGE: SCHEDULE MANAGER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

elif page == "📅 Schedule Manager":
    st.markdown("""
    <div class="section-header">
        <span class="icon">📋</span>
        <span class="label">Schedule Manager</span>
        <span class="desc">Platform → Account → Timeline view of all scheduled content</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Auto-publisher status ─────────────────────────────────────────────
    if _auto_publisher_active:
        st.markdown(
            '<span class="status-ok">🟢 Auto-Publisher Active</span> '
            '<span style="color:#94a3b8;font-size:0.85rem;">— checks every 60s for due posts</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="status-error">🔴 Auto-Publisher Inactive</span> '
            '<span style="color:#94a3b8;font-size:0.85rem;">— check logs for errors</span>',
            unsafe_allow_html=True,
        )

    try:
        from modules.scheduler.scheduler_db import (
            get_all_scheduled, delete_schedule, update_schedule_time,
            format_time_ist, retry_failed, retry_all_failed,
        )
        import pytz
        from dateutil.parser import parse as _parse_dt
        IST = pytz.timezone("Asia/Kolkata")

        PLATFORM_ICONS = {
            "instagram": "📸",
            "twitter_text": "🐦",
            "twitter_video": "🎬",
        }
        PLATFORM_LABELS = {
            "instagram": "Instagram Reel",
            "twitter_text": "Tweet (Text)",
            "twitter_video": "Tweet (Video)",
        }

        # ── Fetch all data once ──────────────────────────────────────────
        all_posts = get_all_scheduled()

        all_pending = [p for p in all_posts if p.get("status") == "pending"]
        all_posted = [p for p in all_posts if p.get("status") == "posted"]
        all_failed = [p for p in all_posts if p.get("status") == "failed"]

        # ── Extra CSS for new UI ─────────────────────────────────────────
        st.markdown("""
        <style>
            .next-up-card {
                background: linear-gradient(135deg, rgba(139,92,246,0.15), rgba(59,130,246,0.1));
                border: 2px solid rgba(139,92,246,0.4);
                border-radius: 16px;
                padding: 20px 24px;
                margin: 12px 0;
            }
            .next-up-card .next-label {
                color: #a78bfa;
                font-size: 0.75rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .next-up-card .next-caption {
                color: #e2e8f0;
                font-size: 1rem;
                line-height: 1.5;
                margin: 8px 0;
                white-space: pre-wrap;
                word-break: break-word;
            }
            .next-up-card .next-meta {
                color: #94a3b8;
                font-size: 0.85rem;
                margin-top: 8px;
            }
            .countdown {
                color: #a78bfa;
                font-size: 1.1rem;
                font-weight: 700;
            }
            .queue-card {
                background: rgba(30,30,46,0.5);
                border: 1px solid rgba(255,255,255,0.06);
                border-radius: 10px;
                padding: 12px 16px;
                margin: 4px 0;
            }
            .queue-card .q-platform { color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; }
            .queue-card .q-caption { color: #e2e8f0; font-size: 0.9rem; margin: 4px 0; }
            .queue-card .q-meta { color: #64748b; font-size: 0.78rem; }
            .history-card {
                background: rgba(255,255,255,0.02);
                border: 1px solid rgba(255,255,255,0.05);
                border-radius: 8px;
                padding: 10px 14px;
                margin: 3px 0;
            }
            .history-card.posted { border-left: 3px solid #10b981; }
            .history-card.failed { border-left: 3px solid #ef4444; }
            .acct-stats {
                display: flex; gap: 1rem; margin: 0.5rem 0 1rem 0;
            }
            .acct-stat {
                padding: 0.5rem 1rem; border-radius: 8px;
                background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06);
                text-align: center; font-size: 0.8rem; color: #94a3b8;
            }
            .acct-stat .num { font-size: 1.3rem; font-weight: 700; display: block; }
            .acct-stat .num.pending { color: #facc15; }
            .acct-stat .num.posted { color: #10b981; }
            .acct-stat .num.failed { color: #ef4444; }
            .reply-badge {
                display: inline-block; background: rgba(29,161,242,0.15);
                color: #1da1f2; padding: 2px 8px; border-radius: 10px;
                font-size: 0.7rem; font-weight: 600; margin-left: 6px;
            }
        </style>
        """, unsafe_allow_html=True)

        # ── Global Summary Bar ───────────────────────────────────────────
        st.markdown(f"""
        <div class="acct-stats">
            <div class="acct-stat"><span class="num pending">{len(all_pending)}</span>⏳ Pending</div>
            <div class="acct-stat"><span class="num posted">{len(all_posted)}</span>✅ Posted</div>
            <div class="acct-stat"><span class="num failed">{len(all_failed)}</span>❌ Failed</div>
            <div class="acct-stat"><span class="num" style="color:#818cf8;">{len(all_posts)}</span>📊 Total</div>
        </div>
        """, unsafe_allow_html=True)

        # ── Global Action Buttons ────────────────────────────────────────
        col_refresh, col_publish, col_retry_all = st.columns(3)
        with col_refresh:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()
        with col_publish:
            if st.button("⚡ Publish Due Now", use_container_width=True, type="primary"):
                with st.spinner("⚡ Publishing due posts..."):
                    try:
                        from modules.scheduler.auto_publisher import publish_due_posts
                        pub, fail = publish_due_posts()
                        if pub or fail:
                            st.success(f"✅ Published: {pub} | Failed: {fail}")
                        else:
                            st.info("📭 No posts are due right now.")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")
        with col_retry_all:
            retry_disabled = len(all_failed) == 0
            if st.button(f"🔄 Retry All Failed ({len(all_failed)})", use_container_width=True,
                         disabled=retry_disabled):
                with st.spinner("🔄 Retrying all failed posts..."):
                    try:
                        count = retry_all_failed()
                        st.success(f"✅ Reset {count} post(s) to pending — they'll publish shortly")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ {e}")

        st.markdown("---")

        # ── Helper: countdown string ─────────────────────────────────────
        def _countdown(iso_string):
            if not iso_string:
                return ""
            try:
                dt = _parse_dt(iso_string)
                if dt.tzinfo is None:
                    dt = pytz.utc.localize(dt)
                now = datetime.now(pytz.utc)
                diff = dt - now
                secs = int(diff.total_seconds())
                if secs <= 0:
                    return "⚡ Due now!"
                if secs < 60:
                    return f"in {secs}s"
                elif secs < 3600:
                    return f"in {secs // 60}m"
                elif secs < 86400:
                    h = secs // 3600
                    m = (secs % 3600) // 60
                    return f"in {h}h {m}m"
                else:
                    return f"in {secs // 86400}d {(secs % 86400) // 3600}h"
            except Exception:
                return ""

        # ── Helper: render account timeline ──────────────────────────────
        def _render_account_timeline(posts, account_name, platform_prefix):
            """Render the Next Up → Queue → History timeline for one account."""
            pending = sorted(
                [p for p in posts if p.get("status") == "pending"],
                key=lambda p: p.get("scheduled_time", ""),
            )
            posted = sorted(
                [p for p in posts if p.get("status") == "posted"],
                key=lambda p: p.get("posted_at", ""), reverse=True,
            )
            failed = sorted(
                [p for p in posts if p.get("status") == "failed"],
                key=lambda p: p.get("scheduled_time", ""), reverse=True,
            )

            # Per-account stats
            st.markdown(f"""
            <div class="acct-stats">
                <div class="acct-stat"><span class="num pending">{len(pending)}</span>Pending</div>
                <div class="acct-stat"><span class="num posted">{len(posted)}</span>Posted</div>
                <div class="acct-stat"><span class="num failed">{len(failed)}</span>Failed</div>
            </div>
            """, unsafe_allow_html=True)

            # ── 🚨 NEXT UP ──────────────────────────────────────────
            if pending:
                next_post = pending[0]
                plat = next_post.get("platform", "unknown")
                icon = PLATFORM_ICONS.get(plat, "📝")
                label = PLATFORM_LABELS.get(plat, plat)
                caption = next_post.get("caption") or "(no caption)"
                caption_display = caption[:300] + ("…" if len(caption) > 300 else "")
                sched_time = format_time_ist(next_post.get("scheduled_time"))
                cd = _countdown(next_post.get("scheduled_time"))
                reply_id = next_post.get("reply_to_tweet_id")
                reply_html = f'<span class="reply-badge">↩️ Reply to tweet</span>' if reply_id else ""

                st.markdown(f"""
                <div class="next-up-card">
                    <div class="next-label">🚨 NEXT UP {reply_html}</div>
                    <div style="color:#94a3b8;font-size:0.8rem;margin-top:4px;">{icon} {label}</div>
                    <div class="next-caption">{caption_display}</div>
                    <div class="next-meta">
                        📅 {sched_time} &nbsp;•&nbsp; <span class="countdown">⏳ {cd}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Reschedule / Cancel for NEXT UP
                try:
                    _current_dt = _parse_dt(next_post["scheduled_time"])
                    if _current_dt.tzinfo is None:
                        _current_dt = pytz.utc.localize(_current_dt)
                    _current_ist = _current_dt.astimezone(IST)
                    _default_date = _current_ist.date()
                    _default_time = _current_ist.time().replace(second=0, microsecond=0)
                except Exception:
                    _default_date = datetime.now(IST).date()
                    _default_time = datetime.now(IST).time().replace(second=0, microsecond=0)

                c1, c2, c3, c4 = st.columns([2, 2, 1, 1])
                with c1:
                    new_date = st.date_input("Date", value=_default_date,
                        key=f"next_date_{next_post['id']}", label_visibility="collapsed")
                with c2:
                    new_time = st.time_input("Time", value=_default_time,
                        key=f"next_time_{next_post['id']}", step=timedelta(minutes=30),
                        label_visibility="collapsed")
                with c3:
                    if st.button("⏰ Set", key=f"next_set_{next_post['id']}", type="primary"):
                        try:
                            new_dt = IST.localize(datetime.combine(new_date, new_time))
                            update_schedule_time(next_post["id"], new_dt)
                            st.success(f"✅ → {new_dt.strftime('%b %d, %I:%M %p IST')}")
                            time.sleep(0.5); st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")
                with c4:
                    if st.button("🗑️ Cancel", key=f"next_cancel_{next_post['id']}"):
                        try:
                            delete_schedule(next_post["id"])
                            st.success("Cancelled"); time.sleep(0.5); st.rerun()
                        except Exception as e:
                            st.error(f"Failed: {e}")

            else:
                st.info("📭 No upcoming posts for this account.")

            # ── 📅 UPCOMING QUEUE ────────────────────────────────────
            if len(pending) > 1:
                st.markdown("#### 📅 Upcoming Queue")
                for post in pending[1:]:
                    plat = post.get("platform", "unknown")
                    icon = PLATFORM_ICONS.get(plat, "📝")
                    label = PLATFORM_LABELS.get(plat, plat)
                    caption = (post.get("caption") or "")[:120]
                    sched = format_time_ist(post.get("scheduled_time"))
                    cd = _countdown(post.get("scheduled_time"))
                    reply_id = post.get("reply_to_tweet_id")
                    reply_html = f'<span class="reply-badge">↩️ Reply</span>' if reply_id else ""

                    st.markdown(f"""
                    <div class="queue-card">
                        <div class="q-platform">{icon} {label} {reply_html}</div>
                        <div class="q-caption">{caption}{"…" if len(post.get("caption", "")) > 120 else ""}</div>
                        <div class="q-meta">📅 {sched} &nbsp;•&nbsp; ⏳ {cd}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    try:
                        _dt = _parse_dt(post["scheduled_time"])
                        if _dt.tzinfo is None:
                            _dt = pytz.utc.localize(_dt)
                        _ist = _dt.astimezone(IST)
                        _dd = _ist.date()
                        _dt_time = _ist.time().replace(second=0, microsecond=0)
                    except Exception:
                        _dd = datetime.now(IST).date()
                        _dt_time = datetime.now(IST).time().replace(second=0, microsecond=0)

                    qc1, qc2, qc3, qc4 = st.columns([2, 2, 1, 1])
                    with qc1:
                        q_date = st.date_input("Date", value=_dd,
                            key=f"q_date_{post['id']}", label_visibility="collapsed")
                    with qc2:
                        q_time = st.time_input("Time", value=_dt_time,
                            key=f"q_time_{post['id']}", step=timedelta(minutes=30),
                            label_visibility="collapsed")
                    with qc3:
                        if st.button("⏰", key=f"q_set_{post['id']}"):
                            try:
                                new_dt = IST.localize(datetime.combine(q_date, q_time))
                                update_schedule_time(post["id"], new_dt)
                                st.success(f"✅ → {new_dt.strftime('%b %d, %I:%M %p')}"); time.sleep(0.5); st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")
                    with qc4:
                        if st.button("🗑️", key=f"q_cancel_{post['id']}"):
                            try:
                                delete_schedule(post["id"])
                                st.success("Cancelled"); time.sleep(0.5); st.rerun()
                            except Exception as e:
                                st.error(f"Failed: {e}")

            # ── ⏪ History (collapsible) ──────────────────────────────
            history_label = f"⏪ History ({len(posted)} posted, {len(failed)} failed)"
            with st.expander(history_label, expanded=False):
                if posted:
                    st.markdown("##### ✅ Posted")
                    for post in posted[:20]:
                        plat = post.get("platform", "unknown")
                        icon = PLATFORM_ICONS.get(plat, "📝")
                        caption = (post.get("caption") or "")[:100]
                        posted_at = format_time_ist(post.get("posted_at"))

                        st.markdown(f"""
                        <div class="history-card posted">
                            <span style="color:#10b981;font-weight:600;">✅ {icon}</span>
                            <span style="color:#e2e8f0;font-size:0.9rem;">{caption}{"…" if len(post.get("caption", "")) > 100 else ""}</span>
                            <br><span style="color:#64748b;font-size:0.75rem;">📅 {posted_at}</span>
                        </div>
                        """, unsafe_allow_html=True)

                        hc1, _ = st.columns([1, 5])
                        with hc1:
                            if st.button("🗑️", key=f"hdel_{post['id']}", help="Remove from history"):
                                delete_schedule(post["id"]); st.rerun()

                if failed:
                    st.markdown("##### ❌ Failed")
                    for post in failed[:10]:
                        plat = post.get("platform", "unknown")
                        icon = PLATFORM_ICONS.get(plat, "📝")
                        caption = (post.get("caption") or "")[:100]
                        error_msg = post.get("error_message", "Unknown error")

                        st.markdown(f"""
                        <div class="history-card failed">
                            <span style="color:#ef4444;font-weight:600;">❌ {icon}</span>
                            <span style="color:#e2e8f0;font-size:0.9rem;">{caption}{"…" if len(post.get("caption", "")) > 100 else ""}</span>
                            <br><span style="color:#fca5a5;font-size:0.75rem;font-family:monospace;">⚠️ {error_msg[:150]}</span>
                        </div>
                        """, unsafe_allow_html=True)

                        fc1, fc2, _ = st.columns([1, 1, 4])
                        with fc1:
                            if st.button("🔄 Retry", key=f"hretry_{post['id']}", type="primary"):
                                try:
                                    retry_failed(post["id"])
                                    st.success("✅ Reset to pending"); time.sleep(0.5); st.rerun()
                                except Exception as e:
                                    st.error(f"Failed: {e}")
                        with fc2:
                            if st.button("🗑️", key=f"hfail_del_{post['id']}"):
                                try:
                                    delete_schedule(post["id"])
                                    st.success("Deleted"); time.sleep(0.5); st.rerun()
                                except Exception as e:
                                    st.error(f"Failed: {e}")

                if not posted and not failed:
                    st.info("No history yet for this account.")

        # ── Build account lists dynamically ──────────────────────────────
        twitter_accounts = sorted({p["twitter_account"] for p in all_posts if p.get("twitter_account")})
        instagram_accounts = sorted({p["instagram_account"] for p in all_posts if p.get("instagram_account")})

        # ── Platform Tabs ────────────────────────────────────────────────
        tab_twitter, tab_instagram = st.tabs(["🐦 Twitter", "📸 Instagram"])

        with tab_twitter:
            if not twitter_accounts:
                st.info("No scheduled tweets for any account. Schedule a tweet from the Post to Twitter page!")
            else:
                account_tabs = st.tabs(twitter_accounts)
                for account_tab, account_name in zip(account_tabs, twitter_accounts):
                    with account_tab:
                        account_posts = [p for p in all_posts if p.get("twitter_account") == account_name]
                        _render_account_timeline(account_posts, account_name, "tw")

        with tab_instagram:
            if not instagram_accounts:
                st.info("No scheduled Instagram posts. Schedule a reel from the Post to Instagram page!")
            else:
                ig_tabs = st.tabs(instagram_accounts)
                for ig_tab, ig_name in zip(ig_tabs, instagram_accounts):
                    with ig_tab:
                        ig_posts = [p for p in all_posts if p.get("instagram_account") == ig_name]
                        _render_account_timeline(ig_posts, ig_name, "ig")

    except Exception as e:
        st.warning(f"⚠️ Schedule Manager unavailable: {e}")
        st.caption("Make sure the `content_schedule` table exists in your Supabase project.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAGE: DAILY NEWS JOKES (Manual trigger + log viewer)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

elif page == "📰 Daily News Jokes":
    st.markdown("""
    <div class="section-header">
        <span class="icon">📰</span>
        <span class="label">Daily News Jokes</span>
        <span class="desc">Fetch trending headlines → Generate 100 jokes → Send via Telegram & Email</span>
    </div>
    """, unsafe_allow_html=True)

    st.info(
        "🕐 **Automated**: This pipeline runs daily at **5:00 AM IST** via GitHub Actions "
        "and delivers 100 jokes to your Telegram & Email.\n\n"
        "You can also trigger it manually below."
    )

    col_run, col_reset_news = st.columns([3, 1])

    with col_run:
        run_news_btn = st.button(
            "🚀 Run News → Jokes Pipeline Now",
            type="primary",
            use_container_width=True,
        )

    with col_reset_news:
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.news_headlines = []
            st.session_state.news_jokes = {}
            st.session_state.news_pipeline_done = False
            st.session_state.news_pipeline_log = ""
            st.rerun()

    if run_news_btn:
        log_lines = []

        # Step 1: Fetch headlines
        with st.spinner("📰 Fetching trending headlines..."):
            try:
                from modules.news_workflow.news_fetcher import fetch_top_headlines
                headlines = fetch_top_headlines()
                st.session_state.news_headlines = headlines
                log_lines.append(f"✅ Fetched {len(headlines)} headlines")
                for i, h in enumerate(headlines, 1):
                    log_lines.append(f"   {i}. {h}")
            except Exception as e:
                st.error(f"❌ News fetch failed: {e}")
                st.stop()

        # Step 2: Generate jokes for each headline
        all_jokes = {}
        from modules.joke_generator.campaign_generator import search_bridges, generate_from_selected

        for idx, headline in enumerate(st.session_state.news_headlines):
            with st.spinner(f"🔍 [{idx+1}/{len(st.session_state.news_headlines)}] Searching bridges for: {headline[:50]}..."):
                try:
                    matches = search_bridges(headline, top_k=15)
                    log_lines.append(f"\n🔍 Headline {idx+1}: \"{headline}\" → {len(matches)} bridges found")
                except Exception as e:
                    log_lines.append(f"\n❌ Search failed for '{headline}': {e}")
                    all_jokes[headline] = []
                    continue

            with st.spinner(f"🔥 [{idx+1}/{len(st.session_state.news_headlines)}] Generating 10 jokes for: {headline[:50]}..."):
                try:
                    jokes = generate_from_selected(headline, matches[:10])
                    all_jokes[headline] = jokes
                    log_lines.append(f"   ✅ Generated {len(jokes)} jokes")
                except Exception as e:
                    log_lines.append(f"   ❌ Generation failed: {e}")
                    all_jokes[headline] = []

        st.session_state.news_jokes = all_jokes
        total_jokes = sum(len(j) for j in all_jokes.values())
        log_lines.append(f"\n{'='*50}")
        log_lines.append(f"🎯 TOTAL: {total_jokes} jokes from {len(st.session_state.news_headlines)} headlines")

        # Step 3: Send notifications
        with st.spinner("📨 Sending notifications via Telegram & Email..."):
            try:
                from modules.news_workflow.notifier import notify_jokes
                notify_jokes(st.session_state.news_headlines, all_jokes)
                log_lines.append("✅ Notifications sent (Telegram + Email)")
            except Exception as e:
                log_lines.append(f"⚠️ Notification failed: {e}")

        st.session_state.news_pipeline_log = "\n".join(log_lines)
        st.session_state.news_pipeline_done = True
        st.rerun()

    # Display results
    if st.session_state.news_pipeline_done:
        total = sum(len(j) for j in st.session_state.news_jokes.values())
        st.success(f"✅ Pipeline complete! Generated **{total}** jokes from **{len(st.session_state.news_headlines)}** headlines.")

        # Show log
        with st.expander("📋 Pipeline Log", expanded=False):
            st.text(st.session_state.news_pipeline_log)

        # Show jokes by headline
        for headline, jokes in st.session_state.news_jokes.items():
            with st.expander(f"📰 {headline} ({len(jokes)} jokes)", expanded=False):
                for i, joke_data in enumerate(jokes):
                    st.markdown(f"""
                    <div class="joke-card">
                        <div class="joke-text">{joke_data.get('joke', 'N/A')}</div>
                        <div class="joke-meta">
                            <span class="badge">#{i+1}</span>
                            <span>{joke_data.get('engine', '?')}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

    elif st.session_state.news_headlines:
        st.markdown("### 📰 Last Fetched Headlines")
        for i, headline in enumerate(st.session_state.news_headlines, 1):
            st.markdown(f"""
            <div class="headline-card">
                <span class="title">{i}. {headline}</span>
            </div>
            """, unsafe_allow_html=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PAGE: TWEET REPLY STUDIO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

elif page == "🐦 Tweet Reply Studio":
    st.markdown("""
    <div class="section-header">
        <span class="icon">🐦</span>
        <span class="label">Tweet Reply Studio</span>
        <span class="desc">Reply to trending tweets with AI-generated jokes or custom replies</span>
    </div>
    """, unsafe_allow_html=True)

    # Extra CSS for this page
    st.markdown("""
    <style>
        .tweet-card {
            background: rgba(29,161,242,0.06); border: 1px solid rgba(29,161,242,0.2);
            border-radius: 14px; padding: 16px 20px; margin: 8px 0;
        }
        .tweet-card .tweet-author { color: #1da1f2; font-weight: 700; font-size: 0.9rem; }
        .tweet-card .tweet-handle { color: #64748b; font-size: 0.8rem; }
        .tweet-card .tweet-text { color: #e2e8f0; font-size: 0.95rem; margin: 8px 0; line-height: 1.5; }
        .tweet-card .tweet-stats { color: #64748b; font-size: 0.78rem; }
        .joke-reply-card {
            background: rgba(139,92,246,0.08); border: 1px solid rgba(139,92,246,0.2);
            border-radius: 10px; padding: 12px 16px; margin: 4px 0;
        }
        .joke-reply-card .joke-text { color: #e2e8f0; font-size: 0.9rem; }
        .joke-reply-card .joke-meta { color: #64748b; font-size: 0.75rem; margin-top: 4px; }
        .trend-badge {
            display: inline-block; background: rgba(29,161,242,0.12);
            color: #1da1f2; padding: 3px 10px; border-radius: 12px;
            font-size: 0.72rem; font-weight: 600; margin-bottom: 8px;
        }
    </style>
    """, unsafe_allow_html=True)

    tab_trending, tab_manual = st.tabs(["🔥 Trending Jokes", "🔍 Manual Search"])

    # ── TAB 1: TRENDING JOKES (pre-generated) ────────────────────────────
    with tab_trending:
        st.markdown("Load the latest AI-generated jokes based on today's trending tweets.")

        # Account selector — AT THE TOP so user always sees it
        try:
            from modules.twitter.twitter_client import get_available_accounts
            available_accounts = get_available_accounts()
        except Exception:
            available_accounts = ["account_1"]

        st.selectbox(
            "🐦 Reply from account",
            options=available_accounts,
            key="reply_account",
        )
        st.markdown("---")

        try:
            from modules.news_workflow.twitter_trends_fetcher import load_latest_results

            results = load_latest_results()
            if results:
                gen_time = results.get("generated_at", "")[:19]
                topics = results.get("topics", [])
                total_jokes = sum(len(t.get("jokes", [])) for t in topics)

                st.success(f"✅ Loaded **{total_jokes}** jokes from **{len(topics)}** trending tweets (generated: {gen_time})")

                for t_idx, topic_data in enumerate(topics):
                    tweet = topic_data.get("tweet", {})
                    jokes = topic_data.get("jokes", [])
                    trend_name = topic_data.get("trend_name", "")

                    if not jokes:
                        continue

                    with st.expander(f"🐦 {trend_name} — {len(jokes)} jokes", expanded=False):
                        # Show the source tweet
                        st.markdown(f"""
                        <div class="tweet-card">
                            <span class="trend-badge">{trend_name}</span>
                            <div class="tweet-author">{tweet.get('author_name', '')}
                                <span class="tweet-handle">@{tweet.get('author', '')}</span>
                            </div>
                            <div class="tweet-text">{tweet.get('text', '')}</div>
                            <div class="tweet-stats">
                                ❤️ {tweet.get('likes', 0):,} &nbsp;·&nbsp;
                                🔁 {tweet.get('retweets', 0):,} &nbsp;·&nbsp;
                        👁️ {tweet.get('views', 0):,} &nbsp;·&nbsp;
                                🕐 {tweet.get('tweet_age', '')}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        st.markdown(f"[🔗 Open on X →]({tweet.get('url', '')})")

                        # Show jokes with reply buttons
                        for j_idx, joke_data in enumerate(jokes):
                            joke_text = joke_data.get("joke", "N/A")
                            engine = joke_data.get("engine", "?")

                            st.markdown(f'<div class="joke-meta">{engine} • generated joke:</div>',
                                        unsafe_allow_html=True)

                            # Editable text area pre-filled with the joke
                            edited_text = st.text_area(
                                f"✍️ Edit joke before replying",
                                value=joke_text,
                                max_chars=280,
                                key=f"jedit_{t_idx}_{j_idx}",
                                height=80,
                                label_visibility="collapsed",
                            )

                            char_count = len(edited_text) if edited_text else 0
                            char_color = "#10b981" if char_count <= 280 else "#ef4444"
                            st.markdown(f'<span style="color:{char_color};font-size:0.75rem;">{char_count}/280</span>',
                                       unsafe_allow_html=True)

                            col_reply, col_sched = st.columns(2)

                            with col_reply:
                                if st.button("🚀 Reply Now", key=f"treply_{t_idx}_{j_idx}", type="primary",
                                            disabled=not edited_text):
                                    try:
                                        from modules.twitter.twitter_client import TwitterClient
                                        account = st.session_state.get("reply_account", "account_1")
                                        client = TwitterClient(account_name=account)
                                        result = client.post_tweet(edited_text, reply_to_tweet_id=tweet.get("id"))
                                        st.success(f"✅ Reply posted! Tweet ID: {result.get('id', 'unknown')}")
                                    except Exception as e:
                                        st.error(f"❌ Failed: {e}")

                            with col_sched:
                                if st.button("📅 Schedule", key=f"tsched_{t_idx}_{j_idx}",
                                            disabled=not edited_text):
                                    st.session_state[f"show_sched_{t_idx}_{j_idx}"] = True

                            # Show schedule form if toggled
                            if st.session_state.get(f"show_sched_{t_idx}_{j_idx}", False):
                                try:
                                    import pytz
                                    IST = pytz.timezone("Asia/Kolkata")
                                    from modules.scheduler.scheduler_db import insert_schedule
                                    from modules.scheduler.slot_calculator import get_next_slot

                                    s_col1, s_col2, s_col3 = st.columns([2, 2, 1])
                                    with s_col1:
                                        s_date = st.date_input("Date", key=f"sd_{t_idx}_{j_idx}",
                                                               label_visibility="collapsed")
                                    with s_col2:
                                        s_time = st.time_input("Time", key=f"st_{t_idx}_{j_idx}",
                                                               step=timedelta(minutes=30),
                                                               label_visibility="collapsed")
                                    with s_col3:
                                        if st.button("✅ Confirm", key=f"sconf_{t_idx}_{j_idx}", type="primary"):
                                            sched_dt = IST.localize(datetime.combine(s_date, s_time))
                                            account = st.session_state.get("reply_account", "account_1")
                                            insert_schedule(
                                                platform="twitter_text",
                                                video_url=None,
                                                caption=edited_text,
                                                scheduled_time=sched_dt,
                                                twitter_account=account,
                                                reply_to_tweet_id=tweet.get("id"),
                                            )
                                            st.success(f"✅ Scheduled for {sched_dt.strftime('%b %d, %I:%M %p IST')}")
                                            del st.session_state[f"show_sched_{t_idx}_{j_idx}"]
                                            time.sleep(0.5); st.rerun()
                                except Exception as e:
                                    st.error(f"Schedule error: {e}")

                # Account selector for replies

            else:
                st.info("📭 No trending tweet jokes generated yet. Run the daily pipeline first from **📰 Daily News Jokes** or wait for the next automated run.")

        except Exception as e:
            st.error(f"❌ Failed to load trending results: {e}")

    # ── TAB 2: MANUAL SEARCH ─────────────────────────────────────────────
    with tab_manual:
        st.markdown("Search for any tweet and compose a reply directly.")

        # Account selector — AT THE TOP so user always sees it
        try:
            from modules.twitter.twitter_client import get_available_accounts
            available_accounts_m = get_available_accounts()
        except Exception:
            available_accounts_m = ["account_1"]

        st.selectbox(
            "🐦 Reply from account",
            options=available_accounts_m,
            key="reply_account_manual",
        )
        st.markdown("---")

        # Search bar
        search_query = st.text_input("🔍 Search tweets", placeholder="e.g., Modi, IPL, Tesla, UFC...",
                                     key="manual_tweet_search")

        if st.button("🔍 Search", type="primary", disabled=not search_query):
            with st.spinner(f"🔍 Searching tweets for: {search_query}..."):
                try:
                    from modules.news_workflow.twitter_trends_fetcher import search_tweets_manual
                    results = search_tweets_manual(search_query, count=10)
                    st.session_state.manual_search_results = results
                    st.session_state.manual_search_query = search_query
                except Exception as e:
                    st.error(f"❌ Search failed: {e}")
                    st.session_state.manual_search_results = []

        # Display results
        if st.session_state.get("manual_search_results"):
            results = st.session_state.manual_search_results
            st.success(f"Found **{len(results)}** tweets for \"{st.session_state.get('manual_search_query', '')}\"")

            for m_idx, tweet in enumerate(results):
                st.markdown(f"""
                <div class="tweet-card">
                    <div class="tweet-author">{tweet.get('author_name', '')}
                        <span class="tweet-handle">@{tweet.get('author', '')}</span>
                    </div>
                    <div class="tweet-text">{tweet.get('text', '')}</div>
                    <div class="tweet-stats">
                        ❤️ {tweet.get('likes', 0):,} &nbsp;·&nbsp;
                        🔁 {tweet.get('retweets', 0):,} &nbsp;·&nbsp;
                        👁️ {tweet.get('views', 0):,}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.markdown(f"[🔗 Open on X →]({tweet.get('url', '')})")

                # Reply compose section
                reply_text = st.text_area(
                    f"✍️ Reply to @{tweet.get('author', '')}",
                    max_chars=280,
                    key=f"manual_reply_{m_idx}",
                    placeholder="Type your reply here...",
                    height=80,
                )

                char_count = len(reply_text) if reply_text else 0
                char_color = "#10b981" if char_count <= 280 else "#ef4444"
                st.markdown(f'<span style="color:{char_color};font-size:0.75rem;">{char_count}/280</span>',
                           unsafe_allow_html=True)

                mc1, mc2 = st.columns(2)
                with mc1:
                    if st.button("🚀 Reply Now", key=f"m_reply_{m_idx}", type="primary",
                                disabled=not reply_text):
                        try:
                            from modules.twitter.twitter_client import TwitterClient
                            account = st.session_state.get("reply_account_manual", "account_1")
                            client = TwitterClient(account_name=account)
                            result = client.post_tweet(reply_text, reply_to_tweet_id=tweet.get("id"))
                            st.success(f"✅ Reply posted! Tweet ID: {result.get('id', 'unknown')}")
                        except Exception as e:
                            st.error(f"❌ Failed: {e}")

                with mc2:
                    if st.button("📅 Schedule Reply", key=f"m_sched_{m_idx}",
                                disabled=not reply_text):
                        st.session_state[f"m_show_sched_{m_idx}"] = True

                if st.session_state.get(f"m_show_sched_{m_idx}", False):
                    try:
                        import pytz
                        IST = pytz.timezone("Asia/Kolkata")
                        from modules.scheduler.scheduler_db import insert_schedule

                        ms1, ms2, ms3 = st.columns([2, 2, 1])
                        with ms1:
                            m_date = st.date_input("Date", key=f"md_{m_idx}", label_visibility="collapsed")
                        with ms2:
                            m_time = st.time_input("Time", key=f"mt_{m_idx}",
                                                    step=timedelta(minutes=30),
                                                    label_visibility="collapsed")
                        with ms3:
                            if st.button("✅ Confirm", key=f"mconf_{m_idx}", type="primary"):
                                sched_dt = IST.localize(datetime.combine(m_date, m_time))
                                account = st.session_state.get("reply_account_manual", "account_1")
                                insert_schedule(
                                    platform="twitter_text",
                                    video_url=None,
                                    caption=reply_text,
                                    scheduled_time=sched_dt,
                                    twitter_account=account,
                                    reply_to_tweet_id=tweet.get("id"),
                                )
                                st.success(f"✅ Scheduled for {sched_dt.strftime('%b %d, %I:%M %p IST')}")
                                del st.session_state[f"m_show_sched_{m_idx}"]
                                time.sleep(0.5); st.rerun()
                    except Exception as e:
                        st.error(f"Schedule error: {e}")

                st.markdown("---")




# ─── Footer ──────────────────────────────────────────────────────────────────
st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
st.markdown(
    '<p style="text-align: center; color: #475569; font-size: 0.8rem;">'
    'Unified Content Engine V6 — Modular × Independent × Automated'
    '</p>',
    unsafe_allow_html=True,
)
