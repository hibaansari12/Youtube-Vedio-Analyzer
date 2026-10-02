import sys
from html import escape
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).parent))
from core.transcript_service import get_transcript, get_video_title
from core.summarizer import create_video_report

st.set_page_config(
    page_title="Video Analyzer",
    page_icon="▸",
    layout="wide",
    initial_sidebar_state="expanded",
)

BG = "#090A19"
PANEL = "#111329"
PANEL_RAISED = "#171A36"
BORDER = "#282B50"
TEXT = "#F6F4FF"
MUTED = "#B0B1D2"
FAINT = "#777A9F"
ACCENT = "#8B68FF"
ACCENT_HOVER = "#A18AFF"
ACCENT_SOFT = "#211B4B"
ACCENT_LINE = "#5D48B4"
CYAN = "#65DDD0"

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');
    #MainMenu, footer, header {{ visibility: hidden; }}
    .stApp {{ background: linear-gradient(135deg, #090A19 0%, #0E1025 56%, #0A0B1B 100%); color: {TEXT}; }}
    html, body, [class*="css"], p, span, div, label, li {{ font-family: "DM Sans", sans-serif; color: {TEXT}; letter-spacing: 0; }}
    .block-container {{ max-width: 1420px; padding: 2rem 3rem 4rem; }}
    [data-testid="stSidebar"] {{ background: #0B0C1E; border-right: 1px solid {BORDER}; }}
    [data-testid="stSidebar"] > div {{ padding: 1.2rem 0.9rem; }}
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{ color: {MUTED} !important; }}
    .side-brand {{ display:flex; align-items:center; gap:.65rem; padding:.55rem .4rem 1.6rem; font:600 1.05rem "Space Grotesk",sans-serif; }}
    .side-mark {{ display:grid; place-items:center; width:30px; height:30px; border-radius:9px; background:linear-gradient(145deg,#A58AFF,#6540EE); color:#fff; font-size:1rem; box-shadow:0 5px 18px #784EFF55; }}
    .side-nav {{ display:flex; align-items:center; gap:.7rem; padding:.7rem .8rem; border:1px solid #5D48B466; border-radius:8px; background:#30216E88; color:#F8F6FF; font-size:.92rem; }}
    .side-nav-icon {{ color:#C2B3FF; font-size:1rem; }}
    .side-foot {{ margin-top:55vh; padding:.9rem .5rem; border-top:1px solid {BORDER}; color:{FAINT}; font-size:.78rem; line-height:1.6; }}
    .topline {{ display:flex; justify-content:space-between; align-items:center; color:{FAINT}; font-size:.76rem; text-transform:uppercase; }}
    .online {{ color:{CYAN}; }}
    .hero-row {{ display:grid; grid-template-columns:1.15fr .85fr; gap:2rem; align-items:center; margin:2.1rem 0 1.7rem; }}
    .eyebrow {{ color:#B8A8FF !important; font-size:.76rem; font-weight:700; text-transform:uppercase; }}
    h1.page-title {{ font:600 3.15rem/1.08 "Space Grotesk",sans-serif !important; color:{TEXT} !important; margin:.7rem 0 .8rem; }}
    h1.page-title span {{ color:#9D82FF !important; }}
    .page-lede {{ max-width:590px; color:{MUTED} !important; font-size:1rem; line-height:1.7; margin:0; }}
    .visual-window {{ position:relative; min-height:205px; border:1px solid #4C3B9D; border-radius:12px; overflow:hidden; background:linear-gradient(145deg,#19153F,#10152F 60%,#101123); box-shadow:0 18px 60px #02020C88; }}
    .visual-window:before {{ content:""; position:absolute; inset:0; background:linear-gradient(115deg,transparent 38%,#7352FF20 39%,transparent 63%); }}
    .visual-head {{ position:relative; display:flex; justify-content:space-between; padding:.75rem 1rem; border-bottom:1px solid #FFFFFF12; color:#A9A0D8; font-size:.68rem; text-transform:uppercase; }}
    .visual-center {{ position:relative; display:flex; align-items:center; justify-content:center; height:128px; }}
    .play-symbol {{ display:grid; place-items:center; width:54px; height:54px; border-radius:50%; background:linear-gradient(145deg,#A28AFF,#6945EE); color:white; box-shadow:0 0 34px #885DFF77; font-size:1.2rem; }}
    .wave {{ position:absolute; bottom:20px; left:9%; right:9%; height:22px; display:flex; justify-content:center; align-items:center; gap:4px; }}
    .wave i {{ width:3px; height:var(--h); border-radius:4px; background:#7E69FF; opacity:.8; }}
    .float-label {{ position:absolute; right:13px; bottom:23px; padding:.5rem .7rem; border:1px solid #6550BA; border-radius:7px; background:#161837; color:#DCD5FF; font-size:.72rem; }}
    div[data-testid="stTabs"] {{ margin-top:.6rem; background:linear-gradient(135deg,#111329,#101226); border:1px solid {BORDER}; border-radius:10px; padding:.45rem 1rem 1rem; }}
    div[data-baseweb="tab-list"] {{ gap:1.3rem; border-bottom:1px solid {BORDER}; }}
    button[data-baseweb="tab"] p {{ color:{MUTED} !important; font-size:.9rem; }}
    button[data-baseweb="tab"][aria-selected="true"] p {{ color:#EAE5FF !important; }}
    div[data-baseweb="tab-highlight"] {{ background:#9A7AFF !important; height:2px; }}
    div[data-baseweb="input"], div[data-baseweb="base-input"], div[data-baseweb="textarea"] {{ background:#0B0D20 !important; border:1px solid #30345D !important; border-radius:8px !important; box-shadow:none !important; }}
    div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within {{ border-color:#9276FF !important; box-shadow:0 0 0 2px #7B5BFF33 !important; }}
    .stTextInput input, .stTextArea textarea {{ background:transparent !important; color:{TEXT} !important; font-size:.92rem; }}
    .stTextInput input::placeholder, .stTextArea textarea::placeholder {{ color:#777A9F !important; }}
    .stButton button {{ min-height:44px; background:linear-gradient(100deg,#875EFF,#5433DC) !important; border:1px solid #A38BFF !important; border-radius:8px; box-shadow:0 5px 18px #5433DC44; transition:filter .15s ease,transform .15s ease; }}
    .stButton button:hover {{ filter:brightness(1.12); transform:translateY(-1px); }}
    .stButton button p {{ color:#fff !important; font-weight:600; }}
    .signal-row {{ display:flex; gap:2rem; align-items:center; margin:1.2rem .5rem 1.8rem; color:{MUTED}; font-size:.8rem; }}
    .signal-item {{ display:flex; align-items:center; gap:.55rem; }}
    .signal-icon {{ display:grid; place-items:center; width:34px; height:34px; border:1px solid #454078; border-radius:50%; background:#171638; color:#B8A7FF; }}
    .report-card {{ margin-top:1.6rem; padding:1.7rem 1.9rem; border:1px solid {BORDER}; border-radius:10px; background:linear-gradient(145deg,#111329,#101225); box-shadow:0 12px 40px #02020A55; }}
    .report-head {{ display:grid; grid-template-columns:1fr 255px; gap:1.5rem; align-items:center; padding-bottom:1.2rem; border-bottom:1px solid {BORDER}; }}
    .report-title {{ font:600 1.55rem/1.25 "Space Grotesk",sans-serif; color:{TEXT} !important; margin:0 0 .55rem; }}
    .report-meta {{ color:{FAINT} !important; font-size:.82rem; }}
    .report-meta a {{ color:#C3B5FF !important; text-decoration:none; }}
    .report-meta a:hover {{ color:#fff !important; text-decoration:underline; }}
    .report-thumb {{ display:block; width:100%; aspect-ratio:16/9; object-fit:cover; border:1px solid #494071; border-radius:8px; }}
    .report-label {{ margin:1.2rem 0 .45rem; color:#AAA3D1 !important; font-size:.75rem; font-weight:700; text-transform:uppercase; }}
    .report-tldr {{ color:#E6E2F8 !important; font:500 1.02rem/1.65 "DM Sans",sans-serif; }}
    .report-points {{ margin:0; padding-left:1.2rem; color:#E3E0F4 !important; line-height:1.7; }}
    .report-points li {{ margin:.3rem 0; padding-left:.15rem; }}
    .report-overview {{ margin:0 0 .85rem; color:#D0CEE4 !important; font:400 .98rem/1.75 "DM Sans",sans-serif; }}
    .report-footer {{ margin-top:1.1rem; padding-top:.85rem; border-top:1px solid {BORDER}; color:{FAINT} !important; font-size:.76rem; }}
    @media (max-width:900px) {{ .block-container {{ padding:1.4rem 1.2rem 3rem; }} .hero-row {{ grid-template-columns:1fr; }} .visual-window {{ min-height:180px; }} h1.page-title {{ font-size:2.5rem; }} }}
    @media (max-width:640px) {{ [data-testid="stSidebar"] {{ min-width:64px; }} .side-brand span:last-child, .side-nav span:last-child, .side-foot {{ display:none; }} .block-container {{ padding:.9rem .8rem 2rem; }} h1.page-title {{ font-size:2rem; }} .report-card {{ padding:1.15rem; }} .report-head {{ grid-template-columns:1fr; }} .report-head > a {{ max-width:320px; }} .signal-row {{ flex-wrap:wrap; gap:.75rem 1rem; }} }}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown(
        '<div class="side-brand"><span class="side-mark">▶</span><span>Video Analyzer</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="side-nav"><span class="side-nav-icon">⌂</span><span>Analyze</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="side-foot"><span class="online">●</span> LOCAL WORKSPACE<br>Transcripts stay on this device</div>',
        unsafe_allow_html=True,
    )

top_left, top_right = st.columns([5, 1])
with top_left:
    st.markdown('<div class="topline">Video intelligence <span> / </span> Analysis workspace</div>', unsafe_allow_html=True)
with top_right:
    st.markdown('<div class="topline" style="justify-content:flex-end"><span class="online">● READY</span></div>', unsafe_allow_html=True)

hero_copy, hero_visual = st.columns([1.1, .9], gap="large")
with hero_copy:
    st.markdown(
        '<div class="eyebrow">✦ TRANSCRIPT INTELLIGENCE</div>'
        '<h1 class="page-title">Understand a video<br><span>in under a minute.</span></h1>'
        '<p class="page-lede">Paste a YouTube link or transcript. Get a clear takeaway, '
        'the essential points, and an overview that follows the video from start to finish.</p>',
        unsafe_allow_html=True,
    )
with hero_visual:
    st.markdown(
        '<div class="visual-window"><div class="visual-head"><span>VIDEO SIGNAL</span><span>TRANSCRIPT READY</span></div>'
        '<div class="visual-center"><span class="play-symbol">▶</span>'
        '<div class="wave">'
        '<i style="--h:8px"></i><i style="--h:13px"></i><i style="--h:19px"></i><i style="--h:10px"></i>'
        '<i style="--h:16px"></i><i style="--h:22px"></i><i style="--h:12px"></i><i style="--h:18px"></i>'
        '<i style="--h:9px"></i><i style="--h:20px"></i><i style="--h:14px"></i><i style="--h:7px"></i>'
        '<i style="--h:16px"></i><i style="--h:23px"></i><i style="--h:11px"></i><i style="--h:18px"></i>'
        '<i style="--h:8px"></i><i style="--h:14px"></i><i style="--h:20px"></i><i style="--h:10px"></i></div>'
        '<span class="float-label">✦ Clear video brief</span></div></div>',
        unsafe_allow_html=True,
    )

tab_url, tab_transcript = st.tabs(["YouTube link", "Paste transcript"])

with tab_url:
    url_input, url_action = st.columns([5, 1.25], gap="small")
    with url_input:
        url_value = st.text_input(
            "YouTube URL", placeholder="https://www.youtube.com/watch?v=...",
            label_visibility="collapsed",
        )
    with url_action:
        run_url = st.button("Analyze video", use_container_width=True, key="analyze_url")

with tab_transcript:
    transcript_value = st.text_area(
        "Transcript", placeholder="Paste the transcript text here...",
        height=150, label_visibility="collapsed",
    )
    run_transcript = st.button("Analyze transcript", use_container_width=True, key="analyze_transcript")

st.markdown(
    '<div class="signal-row"><div class="signal-item"><span class="signal-icon">ϟ</span><span>Fast analysis<br><b>Optimized speech recognition</b></span></div>'
    '<div class="signal-item"><span class="signal-icon">◈</span><span>VAD + timestamps<br><b>Only speech, precisely indexed</b></span></div>'
    '<div class="signal-item"><span class="signal-icon">✧</span><span>Private workflow<br><b>Local model inference</b></span></div></div>',
    unsafe_allow_html=True,
)

run = run_url or run_transcript
if run:
    mode = "url" if run_url else "transcript"
    content = url_value.strip() if mode == "url" else transcript_value.strip()

    if not content:
        st.error("Add a YouTube link or paste a transcript first.")
    else:
        spinner_msg = "Fetching captions or transcribing with large-v3..." if mode == "url" else "Building your video brief..."
        with st.spinner(spinner_msg):
            try:
                if mode == "url":
                    title = get_video_title(content) or "YouTube video summary"
                    result = get_transcript(content)
                    transcript_text = result.text
                    video_id = result.video_id
                    source = result.source
                    timestamped_segments = result.segments
                else:
                    transcript_text = content
                    video_id = None
                    source = "pasted"
                    title = "Transcript summary"
                    timestamped_segments = []

                if len(transcript_text.split()) < 5:
                    st.error("That transcript is too short to analyze. Add at least a few sentences.")
                else:
                    report_data = create_video_report(transcript_text)
                    st.session_state["result"] = {
                        "title": title,
                        "video_id": video_id,
                        "transcript_source": source,
                        "timestamps": timestamped_segments,
                        "word_count": len(transcript_text.split()),
                        "tldr": report_data["tldr"],
                        "key_points": report_data["key_points"],
                        "overview": report_data["overview"],
                    }
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Couldn't analyze this: {e}")

if "result" in st.session_state:
    data = st.session_state["result"]
    title = escape(str(data["title"]))
    video_id = data.get("video_id")
    source_link = "AI summary"
    thumbnail = ""
    if video_id:
        safe_video_id = escape(str(video_id))
        source_link = (
            f'<a href="https://www.youtube.com/watch?v={safe_video_id}" '
            'target="_blank" rel="noopener noreferrer">Watch on YouTube ↗</a>'
        )
        thumbnail = (
            f'<a href="https://www.youtube.com/watch?v={safe_video_id}" '
            'target="_blank" rel="noopener noreferrer">'
            f'<img class="report-thumb" src="https://img.youtube.com/vi/{safe_video_id}/hqdefault.jpg" '
            f'alt="Thumbnail for {title}"></a>'
        )
    points_html = "".join(
        f"<li>{escape(str(point))}</li>" for point in data["key_points"]
    )
    overview_html = "".join(
        f'<p class="report-overview">{escape(str(paragraph))}</p>'
        for paragraph in data["overview"]
    )
    st.markdown(
        f'<article class="report-card"><header class="report-head"><div>'
        f'<h2 class="report-title">{title}</h2>'
        f'<div class="report-meta">AI brief · {escape(str(data["transcript_source"]).replace("faster-whisper", "Faster-Whisper"))} · {source_link}</div>'
        f'</div>{thumbnail}</header>'
        f'<div class="report-label">TL;DR</div><div class="report-tldr">{escape(str(data["tldr"]))}</div>'
        f'<div class="report-label">Key points</div><ul class="report-points">{points_html}</ul>'
        f'<div class="report-label">Overview</div>{overview_html}'
        f'<div class="report-footer">{data["word_count"]:,} transcript words'
        f'{" · Timestamped segments available" if data["timestamps"] else ""}</div></article>',
        unsafe_allow_html=True,
    )
