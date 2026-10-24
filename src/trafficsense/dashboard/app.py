"""TrafficSense dashboard. Run from the repo root:

    streamlit run src/trafficsense/dashboard/app.py

It only reads files (outputs/, the replays and the detector weights); see docs/dashboard.md.
The page scripts live in screens/ (not pages/, so Streamlit does not build its automatic
page list before st.navigation runs).
"""
from pathlib import Path

import streamlit as st

from trafficsense.dashboard import data, theme, ui

HERE = Path(__file__).parent

st.set_page_config(page_title="TrafficSense", page_icon=":material/traffic:", layout="wide",
                   initial_sidebar_state="expanded")
st.html(theme.css())

pages = [
    st.Page(HERE / "screens/overview.py", title="Overview", icon=":material/space_dashboard:", default=True),
    st.Page(HERE / "screens/live_detection.py", title="Live Detection", icon=":material/videocam:"),
    st.Page(HERE / "screens/network_replay.py", title="Network Replay", icon=":material/route:"),
    st.Page(HERE / "screens/results.py", title="Results", icon=":material/monitoring:"),
]
nav = st.navigation(pages)


@st.cache_data(ttl=60, show_spinner=False)
def _version() -> dict[str, str]:
    return data.code_version()


v = _version()
dirty = v["commit"].endswith("-dirty")
with st.sidebar:
    ui.html(
        '<div class="ts-side-status">'
        f'<div class="row"><span class="ts-live-dot{" warn" if dirty else ""}"></span><span class="k">Reads files only</span></div>'
        f'<div class="row"><span class="k">Results</span><span class="v">{ui.esc(v["data_date"])}</span></div>'
        f'<div class="row"><span class="k">Code</span><span class="v">{ui.esc(v["commit"])}</span></div>'
        '</div>')
nav.run()
