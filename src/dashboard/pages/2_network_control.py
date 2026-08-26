import streamlit as st
from utils import apply_theme

st.set_page_config(page_title="Network Control | TrafficSense", layout="wide")
apply_theme()

st.title("🌐 Network Control")
st.markdown("Multi-agent cooperative signal control and reasoning traces.")

st.warning("🚧 This page will display the 2×2 intersection grid, current signal phases, and LLM reasoning traces. Implementation in Step 4.3.")

# Placeholder grid
st.subheader("Intersection Grid (2×2)")
cols = st.columns(2)
for i in range(4):
    with cols[i % 2]:
        st.markdown(f"""
        <div style="background-color: #1c2128; border-radius: 10px; padding: 20px; margin-bottom: 10px; border: 1px solid #30363d;">
            <h4 style="color: #e6edf3;">Intersection I{i}</h4>
            <p style="color: #8b949e;">Status: <span style="color: #3fb950;">● Online</span></p>
            <p style="color: #8b949e;">Phase: <span style="color: #58a6ff;">N/S Through</span></p>
            <p style="color: #8b949e;">Queued: <span style="color: #e6edf3;">--</span></p>
        </div>
        """, unsafe_allow_html=True)
