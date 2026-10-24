"""TrafficSense dashboard. Run from the repo root:

    streamlit run src/trafficsense/dashboard/app.py

It only reads files (outputs/, the replays and the detector weights); see docs/dashboard.md.
"""
from pathlib import Path

import streamlit as st

from trafficsense.dashboard import theme

HERE = Path(__file__).parent

st.set_page_config(page_title="TrafficSense", page_icon=":material/traffic:", layout="wide",
                   initial_sidebar_state="expanded")
st.markdown(theme.CSS, unsafe_allow_html=True)

pages = [
    st.Page(HERE / "pages/overview.py", title="Overview", icon=":material/space_dashboard:", default=True),
    st.Page(HERE / "pages/live_detection.py", title="Live Detection", icon=":material/videocam:"),
    st.Page(HERE / "pages/network_replay.py", title="Network Replay", icon=":material/route:"),
    st.Page(HERE / "pages/results.py", title="Results", icon=":material/monitoring:"),
]
nav = st.navigation(pages)
with st.sidebar:
    st.markdown('<div class="ts-eyebrow">TrafficSense</div>', unsafe_allow_html=True)
    st.caption("LLM signal control for Indian roads. Every number is read from files in outputs/; "
               "each chart names its source file and commit.")
nav.run()
