"""
TrafficSense Dashboard Utilities
"""
import os
import json
from pathlib import Path
from ultralytics import YOLO
import streamlit as st


@st.cache_resource
def load_yolo_model():
    """Load trained YOLOv8n model (cached)."""
    model_path = r'C:\Pilli\trafficsense\models\yolo\best.pt'
    if os.path.exists(model_path):
        return YOLO(model_path)
    return None


@st.cache_data
def load_perception_states():
    """Load perception states JSON."""
    path = r'C:\Pilli\trafficsense\outputs\perception_demo\perception_states.json'
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return []


@st.cache_data
def load_simulation_metrics(controller='trafficsense'):
    """Load simulation metrics CSV."""
    import pandas as pd
    path = r'C:\Pilli\trafficsense\outputs\simulation_results\{}_metrics.csv'.format(controller)
    if os.path.exists(path):
        return pd.read_csv(path)
    return None


@st.cache_data
def load_decisions():
    """Load cooperative decisions JSON."""
    path = r'C:\Pilli\trafficsense\outputs\simulation_results\trafficsense_decisions.json'
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return []


def apply_theme():
    """Apply custom CSS for dark professional theme."""
    st.markdown("""
    <style>
    .main {
        background-color: #0e1117;
    }
    .stSidebar {
        background-color: #161b22;
    }
    .metric-card {
        background-color: #1c2128;
        border-radius: 10px;
        padding: 15px;
        border-left: 4px solid #3b82f6;
    }
    .intersection-card {
        background-color: #1c2128;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 15px;
    }
    h1, h2, h3 {
        color: #e6edf3;
    }
    .stButton>button {
        background-color: #238636;
        color: white;
        border-radius: 6px;
    }
    </style>
    """, unsafe_allow_html=True)


def render_metric_card(title, value, delta=None, icon="📊"):
    """Render a styled metric card."""
    delta_html = f'<span style="color: #3fb950;">▲ {delta}</span>' if delta else ''
    st.markdown(f"""
    <div class="metric-card">
        <div style="font-size: 14px; color: #8b949e;">{icon} {title}</div>
        <div style="font-size: 32px; font-weight: bold; color: #e6edf3;">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)
