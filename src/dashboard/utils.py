import os
import sys
import json
from pathlib import Path
from ultralytics import YOLO
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src import config

@st.cache_resource
def load_yolo_model():
    """Load trained YOLO model (cached)."""
    model_path = str(config.MODELS_DIR / 'yolo' / 'best.pt')
    if os.path.exists(model_path):
        return YOLO(model_path)
    return None

@st.cache_data
def load_perception_states():
    """Load perception states JSON."""
    path = str(config.OUTPUTS_DIR / 'perception_demo' / 'perception_states.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

@st.cache_data
def load_simulation_metrics(controller='trafficsense'):
    """Load simulation metrics CSV."""
    import pandas as pd
    path = str(config.SIMULATION_RESULTS_DIR / f'{controller}_metrics.csv')
    if os.path.exists(path):
        try:
            return pd.read_csv(path)
        except Exception:
            return pd.DataFrame()
    return None

@st.cache_data
def load_decisions():
    """Load cooperative decisions JSON."""
    path = str(config.SIMULATION_RESULTS_DIR / 'trafficsense_decisions.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def apply_theme():
    """Apply stunning ultra-modern CSS for a premium dashboard experience."""
    st.markdown("""
    <style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

    /* Global Typography & Background */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #020617 100%);
        color: #f8fafc;
    }
    
    /* Hide top header line */
    header[data-testid="stHeader"] {
        background: transparent !important;
    }
    
    /* Sidebar styling with Glassmorphism */
    [data-testid="stSidebar"] {
        background: rgba(15, 23, 42, 0.7) !important;
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    /* Buttons */
    .stButton>button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(37, 99, 235, 0.4);
        background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%);
        color: white;
    }
    
    /* Dataframes / Tables */
    [data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 8px 32px rgba(0,0,0,0.2);
    }
    
    /* Metric Cards Override */
    [data-testid="stMetricValue"] {
        font-size: 2.2rem !important;
        font-weight: 700 !important;
        background: -webkit-linear-gradient(45deg, #60a5fa, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* Custom Card Classes */
    .glass-card {
        background: rgba(30, 41, 59, 0.5);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 24px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    .glass-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 15px 35px rgba(0,0,0,0.3);
        border: 1px solid rgba(255, 255, 255, 0.15);
    }
    
    .glowing-dot {
        height: 10px;
        width: 10px;
        background-color: #10b981;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 10px #10b981, 0 0 20px #10b981;
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
        100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    </style>
    """, unsafe_allow_html=True)

def render_metric_card(title, value, delta=None, icon="📊", color_theme="blue"):
    """Render a styled metric card with ultra-modern glassmorphism UI."""
    colors = {
        "blue": ("#3b82f6", "rgba(59, 130, 246, 0.1)"),
        "green": ("#10b981", "rgba(16, 185, 129, 0.1)"),
        "purple": ("#8b5cf6", "rgba(139, 92, 246, 0.1)"),
        "red": ("#ef4444", "rgba(239, 68, 68, 0.1)"),
        "amber": ("#f59e0b", "rgba(245, 158, 11, 0.1)")
    }
    border_color, bg_color = colors.get(color_theme, colors["blue"])
    
    delta_html = ""
    if delta:
        is_positive = "+" in str(delta) or (isinstance(delta, (int, float)) and delta > 0)
        d_color = "#10b981" if is_positive else "#ef4444"
        d_icon = "▲" if is_positive else "▼"
        delta_html = f'''
        <div style="background: rgba({ "16, 185, 129" if is_positive else "239, 68, 68" }, 0.15); 
                    color: {d_color}; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; display: inline-flex; align-items: center; gap: 4px;">
            {d_icon} {abs(float(str(delta).replace('+','').replace('%','')))}%
        </div>'''

    st.markdown(f"""
    <div class="glass-card" style="border-left: 4px solid {border_color}; margin-bottom: 1rem;">
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
            <span style="color: #94a3b8; font-size: 14px; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px;">
                {title}
            </span>
            <span style="font-size: 20px; background: {bg_color}; padding: 8px; border-radius: 10px;">
                {icon}
            </span>
        </div>
        <div style="display: flex; align-items: baseline; gap: 12px;">
            <span style="font-size: 32px; font-weight: 700; color: #f8fafc; letter-spacing: -0.5px;">
                {value}
            </span>
            {delta_html}
        </div>
    </div>
    """, unsafe_allow_html=True)
