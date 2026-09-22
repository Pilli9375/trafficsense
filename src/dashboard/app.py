"""
TrafficSense Dashboard
Main entry point for the Streamlit application.
"""
import streamlit as st
from utils import apply_theme, render_metric_card

# Page config
st.set_page_config(
    page_title="TrafficSense | Smart City AI",
    page_icon="🚥",
    layout="wide",
    initial_sidebar_state="expanded"
)

apply_theme()

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/color/96/traffic-light.png", width=60)
    st.html("<h2 style='margin-bottom: 0;'>TrafficSense</h2>")
    st.html("<p style='color: #94a3b8; font-size: 14px;'>Multi-Agent Smart City Traffic</p>")
    st.markdown("---")
    
    st.markdown("### Navigation")
    st.page_link("pages/1_live_monitor.py", label="🎥 Live Monitor", icon="🎥")
    st.page_link("pages/2_network_control.py", label="🌐 Network Control", icon="🌐")
    st.page_link("pages/3_analytics.py", label="📈 Analytics", icon="📈")
    
    st.markdown("---")
    st.markdown("### Architecture Specs")
    st.html("""
    <div style='background: rgba(30,41,59,0.5); padding: 15px; border-radius: 10px; font-size: 13px;'>
    <b style='color: #60a5fa;'>Base Paper:</b> CoLLMLight<br>
    <b style='color: #60a5fa;'>Perception:</b> YOLOv8s (24-class)<br>
    <b style='color: #60a5fa;'>Reasoning:</b> Gemma 3 4B<br>
    <b style='color: #60a5fa;'>Engine:</b> CityFlow C++
    </div>
    """)
    
    st.html("<br><br>")
    st.html("""
    <div style='display: flex; align-items: center; gap: 10px; padding: 10px; background: rgba(16, 185, 129, 0.1); border-radius: 8px; border: 1px solid rgba(16, 185, 129, 0.2);'>
        <span class='glowing-dot'></span>
        <span style='color: #10b981; font-weight: 600; font-size: 14px;'>System Online</span>
    </div>
    """)

# Hero Section
st.html("""
<div style="padding: 3rem 2rem; background: linear-gradient(135deg, rgba(30,58,138,0.2) 0%, rgba(2,6,23,0) 100%); border-radius: 24px; margin-bottom: 2rem; border: 1px solid rgba(255,255,255,0.05);">
    <h1 style="font-size: 3.5rem; font-weight: 800; margin-bottom: 0.5rem; background: -webkit-linear-gradient(45deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        TrafficSense
    </h1>
    <p style="font-size: 1.2rem; color: #94a3b8; max-width: 800px; margin-bottom: 2rem; line-height: 1.6;">
        Next-generation smart city traffic management powered by cooperative LLM orchestration and real-time YOLOv8 perception, optimized for complex Indian road networks.
    </p>
</div>
""")

# Metrics Grid
col1, col2, col3, col4 = st.columns(4)
with col1:
    render_metric_card("Network Nodes", "4", icon="🚦", color_theme="blue")
with col2:
    render_metric_card("Tracked Classes", "24", icon="🚗", color_theme="amber")
with col3:
    render_metric_card("Detection mAP", "56.3%", "+2.7%", icon="🎯", color_theme="green")
with col4:
    render_metric_card("LLM Backend", "Gemma 3", icon="🧠", color_theme="purple")

st.markdown("---")

st.html("""
<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; margin-top: 2rem;">
    <div class="glass-card">
        <h3 style="color: #60a5fa; display: flex; align-items: center; gap: 10px;">🎥 1. Live Monitor</h3>
        <p style="color: #94a3b8; font-size: 14px; line-height: 1.6;">Upload raw dashcam or CCTV footage and watch the custom Indian YOLOv8s model detect and classify highly dense, mixed traffic in real-time.</p>
    </div>
    <div class="glass-card">
        <h3 style="color: #a78bfa; display: flex; align-items: center; gap: 10px;">🌐 2. Network Control</h3>
        <p style="color: #94a3b8; font-size: 14px; line-height: 1.6;">View the live multi-agent simulation where 4 distinct agents negotiate and optimize traffic light phases using cooperative spatiotemporal reasoning via Gemma 3.</p>
    </div>
</div>
""")
