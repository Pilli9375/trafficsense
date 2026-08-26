"""
TrafficSense Dashboard
Main entry point for the Streamlit application.
"""
import streamlit as st
from utils import apply_theme

# Page config
st.set_page_config(
    page_title="TrafficSense",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded"
)

apply_theme()

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/color/96/traffic-light.png", width=80)
    st.title("TrafficSense")
    st.markdown("*Multi-Agent Smart City Traffic Management*")
    st.markdown("---")
    
    st.markdown("### Project Info")
    st.markdown("""
    - **Base Paper**: CoLLMLight (ICLR 2026)
    - **Perception**: YOLOv8n
    - **Orchestration**: Gemma 3 4B
    - **Simulator**: CityFlow
    """)
    
    st.markdown("---")
    st.markdown("### Navigation")
    st.page_link("pages/1_live_monitor.py", label="📹 Live Monitor", icon="📹")
    st.page_link("pages/2_network_control.py", label="🌐 Network Control", icon="🌐")
    st.page_link("pages/3_analytics.py", label="📈 Analytics", icon="📈")
    
    st.markdown("---")
    st.markdown("### Status")
    st.success("System Online")
    st.info("Second Review: Sep 29 - Oct 3, 2026")

# Main content
st.title("🚦 TrafficSense Dashboard")
st.markdown("""
Welcome to the **TrafficSense** smart city traffic management dashboard.

This system integrates **YOLOv8-based perception** with **cooperative LLM orchestration**
to optimize traffic signal control for Indian urban road conditions.

### Quick Stats
""")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Intersections", "4", "Active")
with col2:
    st.metric("Vehicle Classes", "11", "Detected")
with col3:
    st.metric("Avg mAP50", "0.50", "YOLOv8n")
with col4:
    st.metric("LLM Model", "Gemma 3 4B", "Local")

st.markdown("---")
st.info("👈 Use the sidebar to navigate between Live Monitor, Network Control, and Analytics pages.")
