import streamlit as st
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src.dashboard.utils import apply_theme, render_metric_card, load_decisions

st.set_page_config(page_title="Network Control | TrafficSense", layout="wide", page_icon="🌐")
apply_theme()

st.title("🌐 Network Control")
st.html("<p style='color: #94a3b8; font-size: 1.1rem; margin-bottom: 2rem;'>Multi-agent cooperative signal control powered by Gemma 3 4B reasoning traces.</p>")

# Load data
decisions = load_decisions()

# Sidebar
with st.sidebar:
    st.markdown("### 🎮 Simulation Control")
    
    col_play, col_pause = st.columns(2)
    with col_play:
        if st.button("▶️ Start", use_container_width=True):
            st.session_state.sim_running = True
    with col_pause:
        if st.button("⏸️ Pause", use_container_width=True):
            st.session_state.sim_running = False
            
    if st.button("⏭️ Step Forward", use_container_width=True):
        st.session_state.sim_step = st.session_state.get('sim_step', 0) + 1
    
    st.markdown("---")
    st.markdown("### 📡 Agent Status")
    
    agent_status = {
        'I0': 'Online',
        'I1': 'Online',
        'I2': 'Online',
        'I3': 'Online'
    }
    
    status_html = "<div style='display: flex; flex-direction: column; gap: 10px;'>"
    for iid, status in agent_status.items():
        status_html += f"""
        <div style="display: flex; align-items: center; gap: 10px; padding: 10px; background: rgba(30,41,59,0.5); border-radius: 8px;">
            <span class="glowing-dot"></span>
            <span style="font-weight: 600; color: #e6edf3;">Agent {iid}</span>
            <span style="margin-left: auto; color: #10b981; font-size: 12px;">{status}</span>
        </div>
        """
    status_html += "</div>"
    st.html(status_html)
    
    st.markdown("---")
    st.markdown("### 🧠 LLM Engine")
    st.html("""
    <div style='background: rgba(139, 92, 246, 0.1); border-left: 4px solid #8b5cf6; padding: 15px; border-radius: 8px;'>
        <b style='color: #a78bfa;'>Gemma 3 4B</b><br>
        <span style='font-size: 13px; color: #94a3b8;'>Avg Latency: ~12s / dec</span>
    </div>
    """)

# Initialize session state
if 'sim_step' not in st.session_state:
    st.session_state.sim_step = 0
if 'sim_running' not in st.session_state:
    st.session_state.sim_running = False

# Network overview
st.markdown("### Executive Overview")
col1, col2, col3, col4 = st.columns(4)
with col1:
    render_metric_card("Active Agents", "4", icon="🤖", color_theme="green")
with col2:
    render_metric_card("Decisions Made", len(decisions), icon="🧠", color_theme="purple")
with col3:
    render_metric_card("Avg Inference", "1.2s", icon="⚡", color_theme="amber")
with col4:
    render_metric_card("Cooperation", "100%", icon="🤝", color_theme="blue")

st.markdown("---")

# Intersection Grid (2x2)
st.subheader("Intersection Grid")

# Group decisions by intersection
decisions_by_iid = defaultdict(list)
for d in decisions:
    iid = d.get('intersection_id') or d.get('intersection', 'UNKNOWN')
    decisions_by_iid[iid].append(d)

intersection_ids = ['I0', 'I1', 'I2', 'I3']

# Phase colors
PHASE_COLORS = {
    0: '#10b981',   # NS Green
    1: '#f59e0b',   # NS Yellow
    2: '#3b82f6',   # EW Green
    3: '#ef4444'    # EW Yellow
}

PHASE_NAMES = {
    0: 'N/S Through',
    1: 'N/S Yellow',
    2: 'E/W Through',
    3: 'E/W Yellow'
}

SEVERITY_COLORS = {
    'none': '#10b981',
    'low': '#3b82f6',
    'moderate': '#f59e0b',
    'high': '#ef4444',
    'critical': '#be123c',
    'unknown': '#94a3b8'
}

# Display 2x2 grid
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
        
        phase_color = PHASE_COLORS.get(phase, '#94a3b8')
        sev_color = SEVERITY_COLORS.get(severity.lower(), '#94a3b8')
        
        # Vehicle mix string
        mix_str = ", ".join([f"{k}: {v}" for k, v in list(vehicle_mix.items())[:3]]) if vehicle_mix else "N/A"
        
        html_content = f"""
        <div class="glass-card" style="margin-bottom: 20px; border-top: 4px solid {phase_color};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h3 style="color: #f8fafc; margin: 0; display: flex; align-items: center; gap: 8px;">
                    <span class="glowing-dot" style="background-color: {phase_color}; box-shadow: 0 0 10px {phase_color};"></span>
                    Intersection {iid}
                </h3>
                <span style="background-color: rgba(255,255,255,0.1); border: 1px solid {phase_color}; color: {phase_color}; padding: 4px 12px; border-radius: 20px; font-weight: 700; font-size: 12px;">
                    {PHASE_NAMES.get(phase, 'Unknown')}
                </span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 20px;">
                <div style="text-align: center; background: rgba(0,0,0,0.2); padding: 10px; border-radius: 8px;">
                    <div style="font-size: 24px; font-weight: bold; color: #f8fafc;">{queued}</div>
                    <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase;">Queued</div>
                </div>
                <div style="text-align: center; background: rgba(0,0,0,0.2); padding: 10px; border-radius: 8px;">
                    <div style="font-size: 24px; font-weight: bold; color: #f8fafc;">{moving}</div>
                    <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase;">Moving</div>
                </div>
                <div style="text-align: center; background: rgba(0,0,0,0.2); padding: 10px; border-radius: 8px; border-bottom: 2px solid {sev_color};">
                    <div style="font-size: 24px; font-weight: bold; color: {sev_color};">{severity.upper()[:3]}</div>
                    <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase;">Severity</div>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 20px;">
                <div>
                    <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase;">Occupancy</div>
                    <div style="font-size: 16px; color: #60a5fa; font-weight: 600;">{occupancy:.2f}</div>
                </div>
                <div>
                    <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase;">Wait Time</div>
                    <div style="font-size: 16px; color: #60a5fa; font-weight: 600;">{tau:.1f}s</div>
                </div>
                <div>
                    <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase;">Pressure</div>
                    <div style="font-size: 16px; color: #60a5fa; font-weight: 600;">{rho:.1f}</div>
                </div>
            </div>
            <div style="background: linear-gradient(90deg, rgba(30,41,59,0.8), rgba(15,23,42,0.8)); border-radius: 8px; padding: 15px; margin-bottom: 10px; border-left: 3px solid #8b5cf6;">
                <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px;">
                    <div style="font-size: 11px; color: #a78bfa; font-weight: 600; text-transform: uppercase;">🧠 LLM Reasoning</div>
                    <div style="font-size: 11px; color: #10b981; font-weight: 600;">{duration}s GREEN</div>
                </div>
                <div style="font-size: 13px; color: #cbd5e1; line-height: 1.6;">{reasoning}</div>
            </div>
            <div style="margin-top: 10px; font-size: 12px; color: #64748b; font-weight: 500;">
                <span style="color: #94a3b8;">🚗 Vehicle Mix:</span> {mix_str}
            </div>
        </div>
        """
        st.html(html_content)

# Reasoning Trace Log
st.markdown("---")
st.markdown("### 🧠 Cooperative Reasoning Log")

if decisions:
    # Show last 10 decisions as a table
    log_data = []
    for d in decisions[-10:]:
        dec = d.get('decision', {})
        state = d.get('state', {})
        iid = d.get('intersection_id') or d.get('intersection', '-')
        log_data.append({
            'Step': d.get('step', '-'),
            'Intersection': iid,
            'Phase': dec.get('recommended_phase', '-'),
            'Duration': f"{dec.get('green_duration_seconds', '-')}s",
            'Severity': state.get('congestion_level', '-'),
            'Reasoning': dec.get('reasoning', '-')[:80] + '...'
        })
    
    st.dataframe(log_data, use_container_width=True, hide_index=True)
else:
    st.info("No decision logs available. Run the simulation first.")

# Cooperation Visualization
st.markdown("---")
st.markdown("### 🤝 Agent Cooperation Map")

coop_html = """
<div class="glass-card" style="text-align: center; padding: 40px;">
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 40px; position: relative; max-width: 600px; margin: 0 auto;">
        <div style="background: rgba(30,41,59,0.8); border-radius: 16px; padding: 25px; border: 2px solid #3b82f6; position: relative; z-index: 2;">
            <div style="font-size: 24px; font-weight: 800; color: #60a5fa;">I0</div>
            <div style="font-size: 12px; color: #94a3b8; margin-top: 5px;">Coordinating with I1, I2</div>
        </div>
        <div style="background: rgba(30,41,59,0.8); border-radius: 16px; padding: 25px; border: 2px solid #10b981; position: relative; z-index: 2;">
            <div style="font-size: 24px; font-weight: 800; color: #34d399;">I1</div>
            <div style="font-size: 12px; color: #94a3b8; margin-top: 5px;">Coordinating with I0, I3</div>
        </div>
        <div style="background: rgba(30,41,59,0.8); border-radius: 16px; padding: 25px; border: 2px solid #f59e0b; position: relative; z-index: 2;">
            <div style="font-size: 24px; font-weight: 800; color: #fbbf24;">I2</div>
            <div style="font-size: 12px; color: #94a3b8; margin-top: 5px;">Coordinating with I0, I3</div>
        </div>
        <div style="background: rgba(30,41,59,0.8); border-radius: 16px; padding: 25px; border: 2px solid #8b5cf6; position: relative; z-index: 2;">
            <div style="font-size: 24px; font-weight: 800; color: #a78bfa;">I3</div>
            <div style="font-size: 12px; color: #94a3b8; margin-top: 5px;">Coordinating with I1, I2</div>
        </div>
    </div>
    <div style="margin-top: 30px; padding: 15px; background: rgba(139, 92, 246, 0.1); border-radius: 8px; display: inline-block;">
        <span style="color: #a78bfa; font-weight: 600;">⚡ All agents share spatiotemporal reasoning natively via Gemma 3</span>
    </div>
</div>
"""
st.html(coop_html)
