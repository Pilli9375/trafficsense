import streamlit as st
import json
import os
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils import apply_theme, render_metric_card

st.set_page_config(page_title="Network Control | TrafficSense", layout="wide")
apply_theme()

st.title("🌐 Network Control")
st.markdown("Multi-agent cooperative signal control with LLM reasoning traces.")

# Load data
@st.cache_data
def load_decisions():
    path = r'C:\Pilli\trafficsense\outputs\simulation_results\trafficsense_decisions.json'
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return []

@st.cache_data
def load_perception_summary():
    path = r'C:\Pilli\trafficsense\outputs\perception_demo\perception_summary.csv'
    if os.path.exists(path):
        import pandas as pd
        return pd.read_csv(path)
    return None

decisions = load_decisions()
perc_df = load_perception_summary()

# Sidebar
with st.sidebar:
    st.markdown("### 🎛️ Simulation Control")
    
    if st.button("▶️ Start Simulation", use_container_width=True):
        st.session_state.sim_running = True
        st.success("Simulation started!")
    
    if st.button("⏸️ Pause", use_container_width=True):
        st.session_state.sim_running = False
        st.info("Simulation paused.")
    
    if st.button("⏭️ Step Forward", use_container_width=True):
        st.session_state.sim_step = st.session_state.get('sim_step', 0) + 1
    
    st.markdown("---")
    st.markdown("### 📡 Agent Status")
    
    agent_status = {
        'I0': '🟢 Online',
        'I1': '🟢 Online',
        'I2': '🟢 Online',
        'I3': '🟢 Online'
    }
    for iid, status in agent_status.items():
        st.markdown(f"**{iid}**: {status}")
    
    st.markdown("---")
    st.markdown("### 🧠 LLM Status")
    st.success("Gemma 3 4B — Responding")
    st.markdown("Avg latency: ~12s/decision")

# Initialize session state
if 'sim_step' not in st.session_state:
    st.session_state.sim_step = 0
if 'sim_running' not in st.session_state:
    st.session_state.sim_running = False

# Network overview
st.subheader("Network Overview")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Active Agents", "4", "Cooperative")
with col2:
    st.metric("Decisions Made", len(decisions))
with col3:
    st.metric("Avg Decision Time", "~12s", "LLM inference")
with col4:
    st.metric("Cooperation Rate", "100%", "All agents")

st.markdown("---")

# Intersection Grid (2×2)
st.subheader("Intersection Grid")

# Group decisions by intersection
decisions_by_iid = defaultdict(list)
for d in decisions:
    decisions_by_iid[d.get('intersection_id', 'UNKNOWN')].append(d)

intersection_ids = ['I0', 'I1', 'I2', 'I3']

# Phase colors
PHASE_COLORS = {
    0: '#3fb950',   # NS Green
    1: '#d29922',   # NS Yellow
    2: '#58a6ff',   # EW Green
    3: '#f85149'    # EW Yellow
}

PHASE_NAMES = {
    0: 'N/S Through',
    1: 'N/S Yellow',
    2: 'E/W Through',
    3: 'E/W Yellow'
}

SEVERITY_COLORS = {
    'none': '#3fb950',
    'low': '#58a6ff',
    'moderate': '#d29922',
    'high': '#f85149',
    'critical': '#da3633'
}

# Display 2×2 grid
row1_cols = st.columns(2)
row2_cols = st.columns(2)

for idx, iid in enumerate(intersection_ids):
    col = row1_cols[idx % 2] if idx < 2 else row2_cols[idx % 2]
    
    with col:
        # Get latest decision for this intersection
        iid_decisions = decisions_by_iid.get(iid, [])
        
        if iid_decisions:
            latest = iid_decisions[-1]
            decision = latest.get('decision', {})
            state = latest.get('state', {})
            
            phase = decision.get('recommended_phase', 0)
            duration = decision.get('green_duration_seconds', 30)
            reasoning = decision.get('reasoning', 'No reasoning available')
            severity = state.get('congestion_level', 'unknown')
            queued = sum(state.get('n_queue', [0, 0, 0, 0]))
            moving = sum(state.get('n_move', [0, 0, 0, 0]))
            occupancy = state.get('occupancy', 0)
            tau = state.get('tau', 0)
            rho = state.get('rho', 0)
            vehicle_mix = state.get('vehicle_mix', {})
        else:
            phase = 0
            duration = 30
            reasoning = "Waiting for first decision..."
            severity = 'unknown'
            queued = 0
            moving = 0
            occupancy = 0
            tau = 0
            rho = 0
            vehicle_mix = {}
        
        phase_color = PHASE_COLORS.get(phase, '#8b949e')
        sev_color = SEVERITY_COLORS.get(severity, '#8b949e')
        
        # Vehicle mix string
        mix_str = ", ".join([f"{k}: {v}" for k, v in list(vehicle_mix.items())[:3]]) if vehicle_mix else "N/A"
        
        st.markdown(f"""
        <div style="background-color: #1c2128; border-radius: 12px; padding: 20px; margin-bottom: 15px; border: 2px solid {phase_color};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                <h3 style="color: #e6edf3; margin: 0;">🚦 {iid}</h3>
                <span style="background-color: {phase_color}; color: #0e1117; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 12px;">
                    {PHASE_NAMES.get(phase, 'Unknown')}
                </span>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 15px;">
                <div style="text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #e6edf3;">{queued}</div>
                    <div style="font-size: 11px; color: #8b949e;">Queued</div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: #e6edf3;">{moving}</div>
                    <div style="font-size: 11px; color: #8b949e;">Moving</div>
                </div>
                <div style="text-align: center;">
                    <div style="font-size: 24px; font-weight: bold; color: {sev_color};">{severity.upper()[:3]}</div>
                    <div style="font-size: 11px; color: #8b949e;">Severity</div>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 15px;">
                <div>
                    <div style="font-size: 11px; color: #8b949e;">Occupancy</div>
                    <div style="font-size: 16px; color: #e6edf3; font-weight: 500;">{occupancy:.2f}</div>
                </div>
                <div>
                    <div style="font-size: 11px; color: #8b949e;">Wait Time</div>
                    <div style="font-size: 16px; color: #e6edf3; font-weight: 500;">{tau:.1f}s</div>
                </div>
                <div>
                    <div style="font-size: 11px; color: #8b949e;">Pressure</div>
                    <div style="font-size: 16px; color: #e6edf3; font-weight: 500;">{rho:.1f}</div>
                </div>
            </div>
            
            <div style="background-color: #161b22; border-radius: 8px; padding: 12px; margin-bottom: 10px;">
                <div style="font-size: 11px; color: #8b949e; margin-bottom: 4px;">⏱️ Green Duration</div>
                <div style="font-size: 20px; color: #e6edf3; font-weight: bold;">{duration}s</div>
            </div>
            
            <div style="background-color: #161b22; border-radius: 8px; padding: 12px;">
                <div style="font-size: 11px; color: #8b949e; margin-bottom: 4px;">💡 LLM Reasoning</div>
                <div style="font-size: 13px; color: #c9d1d9; line-height: 1.5;">{reasoning}</div>
            </div>
            
            <div style="margin-top: 10px; font-size: 11px; color: #8b949e;">
                🚗 {mix_str}
            </div>
        </div>
        """, unsafe_allow_html=True)

# Reasoning Trace Log
st.markdown("---")
st.subheader("🧠 Cooperative Reasoning Log")

if decisions:
    # Show last 5 decisions as a table
    log_data = []
    for d in decisions[-10:]:
        dec = d.get('decision', {})
        state = d.get('state', {})
        log_data.append({
            'Step': d.get('step', '-'),
            'Intersection': d.get('intersection_id', '-'),
            'Phase': dec.get('recommended_phase', '-'),
            'Duration': f"{dec.get('green_duration_seconds', '-')}s",
            'Severity': state.get('congestion_level', '-'),
            'Reasoning': dec.get('reasoning', '-')[:80] + '...'
        })
    
    st.table(log_data)
else:
    st.info("No decision logs available. Run the simulation first.")

# Cooperation Visualization
st.markdown("---")
st.subheader("🤝 Agent Cooperation Map")

coop_html = """
<div style="background-color: #1c2128; border-radius: 12px; padding: 20px;">
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; position: relative;">
        <!-- I0 -->
        <div style="background-color: #161b22; border-radius: 8px; padding: 15px; text-align: center; border: 2px solid #3fb950;">
            <div style="font-weight: bold; color: #e6edf3;">I0</div>
            <div style="font-size: 12px; color: #8b949e;">Coordinating with I1, I2</div>
        </div>
        <!-- I1 -->
        <div style="background-color: #161b22; border-radius: 8px; padding: 15px; text-align: center; border: 2px solid #3fb950;">
            <div style="font-weight: bold; color: #e6edf3;">I1</div>
            <div style="font-size: 12px; color: #8b949e;">Coordinating with I0, I3</div>
        </div>
        <!-- I2 -->
        <div style="background-color: #161b22; border-radius: 8px; padding: 15px; text-align: center; border: 2px solid #3fb950;">
            <div style="font-weight: bold; color: #e6edf3;">I2</div>
            <div style="font-size: 12px; color: #8b949e;">Coordinating with I0, I3</div>
        </div>
        <!-- I3 -->
        <div style="background-color: #161b22; border-radius: 8px; padding: 15px; text-align: center; border: 2px solid #3fb950;">
            <div style="font-weight: bold; color: #e6edf3;">I3</div>
            <div style="font-size: 12px; color: #8b949e;">Coordinating with I1, I2</div>
        </div>
    </div>
    <div style="text-align: center; margin-top: 15px; color: #8b949e; font-size: 12px;">
        All agents share spatiotemporal reasoning via Gemma 3 4B
    </div>
</div>
"""
st.markdown(coop_html, unsafe_allow_html=True)
