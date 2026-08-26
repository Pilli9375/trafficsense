import streamlit as st
from utils import apply_theme, load_yolo_model, render_metric_card

st.set_page_config(page_title="Live Monitor | TrafficSense", layout="wide")
apply_theme()

st.title("📹 Live Traffic Monitor")
st.markdown("Real-time vehicle detection and congestion analysis.")

st.warning("🚧 This page will display live YOLOv8 detection feed, vehicle counts, and congestion heatmaps. Implementation in Step 4.2.")

# Placeholder layout
col1, col2 = st.columns([2, 1])
with col1:
    st.subheader("Detection Feed")
    st.info("Upload a traffic video to see real-time detection.")
    
with col2:
    st.subheader("Metrics")
    render_metric_card("Vehicles Detected", "0", icon="🚗")
    render_metric_card("Congestion", "N/A", icon="🚦")
    render_metric_card("Avg Confidence", "0.00", icon="🎯")
