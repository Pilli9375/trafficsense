import streamlit as st
from utils import apply_theme

st.set_page_config(page_title="Analytics | TrafficSense", layout="wide")
apply_theme()

st.title("📈 Performance Analytics")
st.markdown("Compare TrafficSense cooperative control against FixedTime baseline.")

st.warning("🚧 This page will display comparison charts, metrics tables, and export options. Implementation in Step 4.4.")

# Placeholder
st.subheader("Controller Comparison")
st.info("Metrics will appear here after running simulations.")

col1, col2 = st.columns(2)
with col1:
    st.markdown("### FixedTime Baseline")
    st.metric("Avg Queue", "TBD")
    st.metric("Avg Wait Time", "TBD")
with col2:
    st.markdown("### TrafficSense")
    st.metric("Avg Queue", "TBD")
    st.metric("Avg Wait Time", "TBD")
