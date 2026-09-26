import sys
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
# Styling — dark, high-contrast professional theme. Every color below is
# set explicitly (not inherited from Streamlit's base theme) so text never
# ends up low-contrast regardless of the user's system/browser theme.
# ---------------------------------------------------------------------------
BG = "#F6F5F2"
PANEL = "#FFFFFF"
BORDER = "#E2DFD8"
TEXT = "#1B1D21"
MUTED = "#666B72"
ACCENT = "#2F4B7C"
ACCENT_DIM = "rgba(47, 75, 124, 0.08)"

st.markdown(
    f"""
    <style>
    #MainMenu, footer, header {{ visibility: hidden; }}

    .stApp {{ background-color: {BG} !important; }}
    .block-container {{ max-width: 720px; padding-top: 3rem; padding-bottom: 4rem; }}

    html, body, [class*="css"], p, span, div, label, h1, h2, h3, h4 {{
        font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
        color: {TEXT} !important;
    }}

    .eyebrow {{
        font-size: 0.82rem;
        color: {ACCENT} !important;
        background: {ACCENT_DIM};
        border: 1px solid rgba(47, 75, 124, 0.25);
        display: inline-block;
        padding: 0.3rem 0.8rem;
        border-radius: 6px;
        margin-bottom: 1.2rem;
    }}
    h1.page-title {{
        font-size: 2.25rem;
        font-weight: 700;
        color: {TEXT} !important;
        letter-spacing: -0.3px;
        margin: 0 0 0.7rem 0;
    }}
    p.page-lede {{
        color: {MUTED} !important;
        font-size: 1rem;
        max-width: 560px;
        margin-bottom: 2rem;
    }}

    div[data-baseweb="tab-list"] {{ gap: 1.5rem; border-bottom: 1px solid {BORDER}; }}
    button[data-baseweb="tab"] p {{ font-size: 0.95rem; color: {MUTED} !important; font-weight: 500; }}
    button[data-baseweb="tab"][aria-selected="true"] p {{ color: {TEXT} !important; font-weight: 700; }}
    div[data-baseweb="tab-highlight"] {{ background-color: {ACCENT} !important; }}

    .stTextInput input, .stTextArea textarea {{
        background: {PANEL} !important;
        border-radius: 8px;
        border: 1px solid {BORDER} !important;
        color: {TEXT} !important;
        font-size: 0.95rem;
    }}
    .stTextInput input::placeholder, .stTextArea textarea::placeholder {{ color: #9A9EA4 !important; }}
    .stTextInput input:focus, .stTextArea textarea:focus {{
        border-color: {ACCENT} !important;
        box-shadow: 0 0 0 1px {ACCENT};
    }}

    .stButton button {{
        background: {ACCENT} !important;
        border-radius: 8px;
        border: none;
        padding: 0.65rem 1.4rem;
        font-weight: 700;
        width: 100%;
    }}
    .stButton button p {{ color: #FFFFFF !important; }}
    .stButton button:hover {{ background: #24395F !important; }}

    .result-card {{
        background: {PANEL};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 1.3rem 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    }}
    .result-card h4 {{
        font-size: 0.8rem;
        letter-spacing: 0.02em;
        color: {ACCENT} !important;
        margin: 0 0 0.7rem 0;
        font-weight: 700;
    }}
    .meta-row {{ font-size: 0.8rem; color: {MUTED} !important; margin-bottom: 0.9rem; }}
    .summary-text {{ font-size: 0.98rem; color: {TEXT} !important; line-height: 1.65; }}

    .kw-chip {{
        display: inline-block;
        background: {ACCENT_DIM};
        border: 1px solid rgba(47, 75, 124, 0.25);
        color: {TEXT} !important;
        font-size: 0.83rem;
        padding: 0.3rem 0.75rem;
        border-radius: 6px;
        margin: 0 0.4rem 0.4rem 0;
    }}
    .kw-chip b {{ color: {ACCENT} !important; }}

    .future-card {{
        border: 1px solid {BORDER};
        border-left: 3px solid {ACCENT};
        border-radius: 8px;
        padding: 1rem 1.2rem;
        color: {MUTED} !important;
        font-size: 0.9rem;
        background: {PANEL};
    }}
    .future-card b {{ color: {TEXT} !important; }}

    [data-testid="stExpander"] {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 8px; }}
    [data-testid="stExpander"] summary {{ color: {TEXT} !important; }}

    hr {{ border-color: {BORDER}; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown('<div class="eyebrow">NLP · Summarization · Keyword Extraction</div>', unsafe_allow_html=True)
st.markdown('<h1 class="page-title">Video Analyzer</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="page-lede">Paste a YouTube link or a transcript. The pipeline pulls the '
    "transcript (captions, with a Whisper fallback), chunks long videos, and generates "
    "a summary and keywords.</p>",
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
                    st.error("That transcript looks too short to analyze.")
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
# Results
# ---------------------------------------------------------------------------
if "result" in st.session_state:
    data = st.session_state["result"]

    st.markdown(
        f"""
        <div class="result-card">
            <h4>Summary</h4>
            <div class="meta-row">
                {data['word_count']:,} words · {data['chunk_count']} chunk(s) · source: {data['transcript_source']}
            </div>
            <div class="summary-text">{data['summary']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    kw_html = "".join(
        f'<span class="kw-chip">{k["keyword"]} <b>· {k["relevance"]}</b></span>'
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
        with st.expander("View per-chunk summaries"):
            for i, chunk in enumerate(data["chunk_summaries"], 1):
                st.markdown(f"**Chunk {i}**")
                st.write(chunk)

st.divider()

st.markdown('<div class="eyebrow">FUTURE SCOPE</div>', unsafe_allow_html=True)
st.markdown(
    """
    <div class="future-card">
        <b>Live data mode.</b> Stream audio from a live lecture or webinar, transcribe it
        in real time with Whisper, and maintain a rolling summary and keyword feed as the
        session unfolds — turning any live talk into searchable notes on the fly.
    </div>
    """,
    unsafe_allow_html=True,
)