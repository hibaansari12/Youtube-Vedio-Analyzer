import streamlit as st

from core.branding import logo_data_uri

st.set_page_config(
    page_title="About | Video Analyzer",
    page_icon="ⓘ",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(135deg, #090A19 0%, #0E1025 56%, #0A0B1B 100%); }
    [data-testid="stSidebar"] { background: #0B0C1E; border-right: 1px solid #282B50; }
    [data-testid="stSidebarNav"] { display:none; }
    .block-container { max-width: 1000px; padding: 3rem 3rem 4rem; }
    .about-kicker { color: #B8A8FF; font-size: .78rem; font-weight: 700; letter-spacing: .08em; }
    .about-title { color: #F6F4FF; font-size: 2.8rem; line-height: 1.15; margin: .6rem 0 1rem; }
    .about-lede { color: #B0B1D2; font-size: 1.08rem; line-height: 1.75; max-width: 760px; }
    .about-card { margin: 1.2rem 0; padding: 1.25rem 1.45rem; border: 1px solid #282B50; border-radius: 10px; background: #111329; }
    .about-card h3 { color: #F6F4FF; margin: 0 0 .55rem; font-size: 1.05rem; }
    .about-card p, .about-card li { color: #B0B1D2; line-height: 1.7; }
    .about-step { display: grid; grid-template-columns: 2.1rem 1fr; gap: .8rem; margin: .8rem 0; color: #B0B1D2; line-height: 1.7; }
    .about-step b { display: grid; place-items: center; width: 2rem; height: 2rem; border: 1px solid #5D48B4; border-radius: 50%; color: #C3B5FF; }
    .about-brand { display:flex; align-items:center; gap:.8rem; margin-bottom:1.4rem; color:#F6F4FF; font-weight:700; font-size:1.1rem; }
    .about-brand img { width:42px; height:42px; }
    @media (max-width: 640px) { .block-container { padding: 1.5rem 1rem 3rem; } .about-title { font-size: 2.1rem; } }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown(
        f'<div class="about-brand"><img src="{logo_data_uri()}" alt="Video Analyzer logo">Video Analyzer</div>',
        unsafe_allow_html=True,
    )
    st.page_link("app.py", label="Analyze")
    st.page_link("pages/about.py", label="About")

st.markdown(
    f'<div class="about-brand"><img src="{logo_data_uri()}" alt="Video Analyzer logo">VIDEO ANALYZER</div>',
    unsafe_allow_html=True,
)
st.markdown('<div class="about-kicker">ABOUT THE PROJECT</div>', unsafe_allow_html=True)
st.markdown('<h1 class="about-title">A clearer view of every video.</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="about-lede">Video Analyzer turns a YouTube video into a concise, '
    'readable brief: a short takeaway, key points, and an overview.</p>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <section class="about-card">
      <h3>Summarize a video in three steps</h3>
      <div class="about-step"><b>1</b><span>On the Analyze page, paste a YouTube video link and choose English or Hindi.</span></div>
      <div class="about-step"><b>2</b><span>Select <strong>Analyze video</strong>. The app gets captions when available; if not, it can try local speech recognition. BART creates the report on this device.</span></div>
      <div class="about-step"><b>3</b><span>Read the takeaway, key points, and overview on the same page, or download the cleaned transcript as readable, timestamped paragraphs. Progress messages show what the analyzer is processing.</span></div>
    </section>
    <section class="about-card">
      <h3>What kinds of videos work best?</h3>
      <ul>
        <li>Recorded meetings, conferences, lectures, tutorials, interviews, presentations, and podcasts with clear speech.</li>
        <li>Meeting and conference recordings work when accessible through a YouTube link. The app does not join live events or identify speakers by name.</li>
        <li>The video must be accessible to the app. Private videos and live streams may not work.</li>
      </ul>
    </section>
    <section class="about-card">
      <h3>English and Hindi</h3>
      <p>Video Analyzer currently supports English and Hindi summaries. Choose the
      language you prefer when analyzing a video. More languages are planned for
      future updates.</p>
    </section>
    <section class="about-card">
      <h3>Privacy and limitations</h3>
      <ul>
        <li>Transcript summarization, speech recognition, and translation run on this device; no report API key is needed.</li>
        <li>BART and Hindi translation models download the first time they are used. YouTube caption and audio downloads require an internet connection.</li>
        <li>BART is optimized for general summaries and can miss or distort details. Check important details against the downloaded transcript.</li>
      </ul>
    </section>
    """,
    unsafe_allow_html=True,
)
