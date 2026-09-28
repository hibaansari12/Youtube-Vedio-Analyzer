import sys
from html import escape
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).parent))
from core.transcript_service import get_transcript
from core.summarizer import summarize_long_text
from core.keywords import extract_keywords

st.set_page_config(
    page_title="Video Analyzer",
    page_icon="▸",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------
BG = "#F3F1F9"
PANEL = "#FFFFFF"
BORDER = "#E0DCEE"
TEXT = "#191627"
MUTED = "#605B77"
FAINT = "#8E89A6"
ACCENT = "#4B3F9E"
ACCENT_HOVER = "#3B3180"
ACCENT_SOFT = "#ECE9F8"
ACCENT_LINE = "#CFC9EC"

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,500;8..60,600;8..60,700&display=swap');

    /* ---------- Base ---------- */
    #MainMenu, footer, header {{ visibility: hidden; }}
    .stApp {{ background-color: {BG} !important; }}
    .block-container {{
        max-width: 760px;
        padding-top: 3.5rem;
        padding-bottom: 5rem;
    }}
    html, body, [class*="css"], p, span, div, label, li {{
        font-family: "Source Sans 3", -apple-system, "Segoe UI", Roboto, sans-serif;
        color: {TEXT} !important;
    }}

    /* ---------- Header ---------- */
    .brand {{
        display: flex; align-items: center; gap: 0.6rem;
        margin-bottom: 2.2rem;
    }}
    .brand-mark {{
        width: 30px; height: 30px; border-radius: 8px;
        background: {ACCENT};
        display: flex; align-items: center; justify-content: center;
        color: #FFFFFF !important; font-size: 0.85rem; line-height: 1;
    }}
    .brand-name {{ font-weight: 600; font-size: 0.98rem; color: {TEXT} !important; }}
    .brand-tag {{
        font-size: 0.85rem; color: {FAINT} !important;
        padding-left: 0.6rem; margin-left: 0.2rem;
        border-left: 1px solid {BORDER};
    }}
    h1.page-title {{
        font-family: "Source Serif 4", Georgia, serif !important;
        font-size: 2.6rem;
        font-weight: 600;
        line-height: 1.15;
        letter-spacing: -0.5px;
        color: {TEXT} !important;
        margin: 0 0 0.9rem 0;
        padding: 0;
    }}
    p.page-lede {{
        color: {MUTED} !important;
        font-size: 1.08rem;
        line-height: 1.6;
        max-width: 580px;
        margin: 0 0 2.2rem 0;
    }}

    /* ---------- Input panel ---------- */
    div[data-testid="stTabs"] {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 12px;
        padding: 0.4rem 1.4rem 1.4rem 1.4rem;
        box-shadow: 0 1px 2px rgba(20, 24, 31, 0.04);
    }}
    div[data-baseweb="tab-list"] {{
        gap: 1.6rem;
        border-bottom: 1px solid {BORDER};
        margin-bottom: 1rem;
    }}
    button[data-baseweb="tab"] {{ padding-left: 0; padding-right: 0; }}
    button[data-baseweb="tab"] p {{
        font-size: 0.95rem; color: {MUTED} !important; font-weight: 500;
    }}
    button[data-baseweb="tab"][aria-selected="true"] p {{
        color: {TEXT} !important; font-weight: 600;
    }}
    div[data-baseweb="tab-highlight"] {{ background-color: {ACCENT} !important; height: 2px; }}
    div[data-baseweb="tab-border"] {{ display: none; }}

    /* Streamlit wraps inputs in extra baseweb divs; style those, not just the <input> */
    div[data-baseweb="input"], div[data-baseweb="base-input"], div[data-baseweb="textarea"] {{
        background: {PANEL} !important;
        border-radius: 8px !important;
        border: 1px solid {BORDER} !important;
        box-shadow: none !important;
    }}
    div[data-baseweb="input"]:focus-within,
    div[data-baseweb="textarea"]:focus-within {{
        border-color: {ACCENT} !important;
        box-shadow: 0 0 0 3px {ACCENT_SOFT} !important;
    }}
    .stTextInput input, .stTextArea textarea {{
        background: transparent !important;
        color: {TEXT} !important;
        font-size: 1rem;
        padding: 0.7rem 0.85rem;
    }}
    .stTextInput input::placeholder, .stTextArea textarea::placeholder {{
        color: {FAINT} !important;
    }}

    /* ---------- Button ---------- */
    .stButton {{ margin-top: 1rem; }}
    .stButton button {{
        background: {ACCENT} !important;
        border: none !important;
        border-radius: 8px;
        padding: 0.7rem 1.4rem;
        width: 100%;
        transition: background 0.15s ease;
    }}
    .stButton button p {{ color: #FFFFFF !important; font-weight: 600; font-size: 1rem; }}
    .stButton button:hover {{ background: {ACCENT_HOVER} !important; }}
    .stButton button:focus-visible {{
        outline: 3px solid {ACCENT_LINE} !important; outline-offset: 2px;
    }}

    /* ---------- Process steps (shown before first result) ---------- */
    .steps {{
        display: grid; grid-template-columns: repeat(3, 1fr);
        gap: 1rem; margin-top: 2.2rem;
    }}
    .step {{ border-top: 2px solid {ACCENT_LINE}; padding-top: 0.8rem; }}
    .step b {{ display: block; font-size: 0.95rem; margin-bottom: 0.25rem; }}
    .step span {{ font-size: 0.88rem; color: {MUTED} !important; line-height: 1.5; }}
    @media (max-width: 640px) {{
        .steps {{ grid-template-columns: 1fr; }}
        h1.page-title {{ font-size: 2.1rem; }}
    }}

    /* ---------- Results ---------- */
    .stats {{
        display: grid; grid-template-columns: repeat(3, 1fr);
        gap: 1rem; margin: 2.2rem 0 1rem 0;
    }}
    .stat {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 0.9rem 1.1rem;
    }}
    .stat .label {{ font-size: 0.8rem; color: {MUTED} !important; margin-bottom: 0.15rem; }}
    .stat .value {{
        font-family: "Source Serif 4", Georgia, serif;
        font-size: 1.5rem; font-weight: 600; color: {TEXT} !important;
    }}

    .result-card {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 12px;
        padding: 1.6rem 1.8rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 2px rgba(20, 24, 31, 0.04);
    }}
    .result-card h4 {{
        font-size: 1rem;
        font-weight: 600;
        color: {TEXT} !important;
        margin: 0 0 0.9rem 0;
        padding: 0 0 0.7rem 0;
        border-bottom: 1px solid {BORDER};
    }}
    .summary-text {{
        font-family: "Source Serif 4", Georgia, serif;
        font-size: 1.08rem;
        line-height: 1.75;
        color: {TEXT} !important;
    }}

    .kw-chip {{
        display: inline-block;
        background: {ACCENT_SOFT};
        border: 1px solid {ACCENT_LINE};
        color: {TEXT} !important;
        font-size: 0.9rem;
        padding: 0.3rem 0.8rem;
        border-radius: 999px;
        margin: 0 0.45rem 0.5rem 0;
    }}
    .kw-chip i {{ font-style: normal; color: {ACCENT} !important; font-weight: 600; margin-left: 0.35rem; }}

    [data-testid="stExpander"] {{
        background: {PANEL};
        border: 1px solid {BORDER} !important;
        border-radius: 10px;
    }}
    [data-testid="stExpander"] summary {{ font-weight: 600; }}

    /* ---------- Footer note ---------- */
    .future-note {{
        margin-top: 1rem;
        padding: 1rem 1.2rem;
        border-left: 3px solid {ACCENT};
        background: {PANEL};
        border-radius: 0 8px 8px 0;
        font-size: 0.92rem; line-height: 1.6;
        color: {MUTED} !important;
    }}
    .future-note b {{ color: {TEXT} !important; }}
    .section-title {{ font-weight: 600; font-size: 0.95rem; margin: 0; }}
    hr {{ border-color: {BORDER}; margin: 2.5rem 0 1.5rem 0; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="brand">
        <div class="brand-mark">▸</div>
        <span class="brand-name">Video Analyzer</span>
        <span class="brand-tag">Summaries and keywords from any talk</span>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown('<h1 class="page-title">Understand a video in under a minute.</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="page-lede">Paste a YouTube link or a transcript. We pull the captions '
    "(with a Whisper fallback), break long videos into sections, and return a clear "
    "summary with the key topics.</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
tab_url, tab_transcript = st.tabs(["YouTube link", "Paste transcript"])

with tab_url:
    url_value = st.text_input(
        "YouTube URL", placeholder="https://www.youtube.com/watch?v=...",
        label_visibility="collapsed",
    )

with tab_transcript:
    transcript_value = st.text_area(
        "Transcript", placeholder="Paste the transcript text here...",
        height=160, label_visibility="collapsed",
    )

run = st.button("Analyze video", use_container_width=True)


# ---------------------------------------------------------------------------
# Cache the heavy model load across reruns/analyses (not across restarts).
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _warm_summarizer():
    from core import summarizer
    summarizer._get_summarizer()  # triggers the one-time model load
    return True


# ---------------------------------------------------------------------------
# Run analysis directly — no separate backend process/server involved.
# ---------------------------------------------------------------------------
if run:
    mode = "url" if url_value.strip() else "transcript"
    content = url_value.strip() if mode == "url" else transcript_value.strip()

    if not content:
        st.error("Paste a YouTube link or a transcript first.")
    else:
        spinner_msg = "Fetching transcript and analyzing..." if mode == "url" else "Analyzing transcript..."
        with st.spinner(spinner_msg):
            try:
                _warm_summarizer()

                if mode == "url":
                    result = get_transcript(content)
                    transcript_text = result.text
                    video_id = result.video_id
                    source = result.source
                else:
                    transcript_text = content
                    video_id = None
                    source = "pasted"

                if len(transcript_text.split()) < 5:
                    st.error("That transcript is too short to analyze. Add at least a few sentences.")
                else:
                    summary_data = summarize_long_text(transcript_text)
                    kw = extract_keywords(transcript_text)
                    st.session_state["result"] = {
                        "video_id": video_id,
                        "transcript_source": source,
                        "word_count": len(transcript_text.split()),
                        "chunk_count": summary_data["chunk_count"],
                        "summary": summary_data["summary"],
                        "chunk_summaries": summary_data["chunk_summaries"],
                        "keywords": kw,
                    }
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Couldn't analyze this: {e}")

# ---------------------------------------------------------------------------
# Results (or, before the first run, a short explanation of the pipeline)
# ---------------------------------------------------------------------------
if "result" in st.session_state:
    data = st.session_state["result"]

    st.markdown(
        f"""
        <div class="stats">
            <div class="stat"><div class="label">Length</div>
                <div class="value">{data['word_count']:,} words</div></div>
            <div class="stat"><div class="label">Sections analyzed</div>
                <div class="value">{data['chunk_count']}</div></div>
            <div class="stat"><div class="label">Transcript source</div>
                <div class="value">{escape(str(data['transcript_source']).capitalize())}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="result-card">
            <h4>Summary</h4>
            <div class="summary-text">{escape(str(data['summary']))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    kw_html = "".join(
        f'<span class="kw-chip">{escape(str(k["keyword"]))}<i>{escape(str(k["relevance"]))}</i></span>'
        for k in data["keywords"]
    ) or f'<span style="color:{MUTED};">No keywords extracted.</span>'

    st.markdown(
        f"""
        <div class="result-card">
            <h4>Keywords</h4>
            {kw_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if data.get("chunk_summaries") and len(data["chunk_summaries"]) > 1:
        with st.expander("View summary of each section"):
            for i, chunk in enumerate(data["chunk_summaries"], 1):
                st.markdown(f"**Section {i}**")
                st.write(chunk)
else:
    st.markdown(
        """
        <div class="steps">
            <div class="step"><b>1. Get the transcript</b>
                <span>Reads YouTube captions, or transcribes the audio with Whisper if none exist.</span></div>
            <div class="step"><b>2. Split long videos</b>
                <span>Breaks the text into sections so nothing is lost in a long talk.</span></div>
            <div class="step"><b>3. Summarize</b>
                <span>Combines section summaries into one overview and pulls out key terms.</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()

st.markdown('<p class="section-title">Coming next</p>', unsafe_allow_html=True)
st.markdown(
    """
    <div class="future-note">
        <b>Live mode.</b> Stream audio from a lecture or webinar, transcribe it in real
        time with Whisper, and keep a rolling summary and keyword feed as the session
        unfolds.
    </div>
    """,
    unsafe_allow_html=True,
)
