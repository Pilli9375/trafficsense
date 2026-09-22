import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils import apply_theme, render_metric_card

st.set_page_config(page_title="Analytics | TrafficSense", layout="wide")
apply_theme()

st.title("📈 Performance Analytics")
st.markdown("Compare TrafficSense cooperative control against baselines.")

# Load data
@st.cache_data
def load_metrics(controller):
    path = r'C:\Pilli\trafficsense\outputs\simulation_results\{}_360_metrics.csv'.format(controller)
    if not os.path.exists(path):
        path = r'C:\Pilli\trafficsense\outputs\simulation_results\{}_metrics.csv'.format(controller)
    if os.path.exists(path):
        df = pd.read_csv(path)
        return df
    return pd.DataFrame()

@st.cache_data
def load_summary(controller):
    path = r'C:\Pilli\trafficsense\outputs\simulation_results\{}_360_summary.json'.format(controller)
    if not os.path.exists(path):
        path = r'C:\Pilli\trafficsense\outputs\simulation_results\{}_summary.json'.format(controller)
    if os.path.exists(path):
        import json
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

fixed_df = load_metrics('fixedtime')
ts_df = load_metrics('trafficsense')
mp_df = load_metrics('maxpressure')
fixed_summary = load_summary('fixedtime')
ts_summary = load_summary('trafficsense')
mp_summary = load_summary('maxpressure')

# Sidebar
with st.sidebar:
    st.markdown("### 📊 Chart Options")
    
    metric_choice = st.selectbox(
        "Primary Metric",
        ["Queue Length", "Wait Time", "Occupancy", "Pressure"],
        index=0
    )
    
    chart_type = st.radio("Chart Type", ["Line", "Bar", "Area"], index=0)
    
    st.markdown("---")
    st.markdown("### 💾 Export")
    
    if st.button("Export FixedTime CSV", use_container_width=True):
        st.success("FixedTime metrics ready for download")
        
    if st.button("Export MaxPressure CSV", use_container_width=True):
        st.success("MaxPressure metrics ready for download")
    
    if st.button("Export TrafficSense CSV", use_container_width=True):
        st.success("TrafficSense metrics ready for download")

# Header stats
st.subheader("Controller Comparison")

if not fixed_df.empty and not ts_df.empty:
    # Load MaxPressure if available
    has_mp = not mp_df.empty
    
    # Calculate aggregates
    if 'total_queued' in fixed_df.columns:
        fixed_avg_queue = fixed_df['total_queued'].mean()
        ts_avg_queue = ts_df['total_queued'].mean()
        mp_avg_queue = mp_df['total_queued'].mean() if has_mp else 0
        
        fixed_avg_wait = fixed_df['tau'].mean()
        ts_avg_wait = ts_df['tau'].mean()
        mp_avg_wait = mp_df['tau'].mean() if has_mp else 0
        
        fixed_avg_occ = fixed_df['occupancy'].mean()
        ts_avg_occ = ts_df['occupancy'].mean()
        mp_avg_occ = mp_df['occupancy'].mean() if has_mp else 0
        
        fixed_peak_queue = fixed_df['total_queued'].max()
        ts_peak_queue = ts_df['total_queued'].max()
        mp_peak_queue = mp_df['total_queued'].max() if has_mp else 0
    else:
        # Fallback to the new 360-step Native CityFlow metrics
        fixed_avg_queue = fixed_df['aql'].mean() if 'aql' in fixed_df.columns else 0
        ts_avg_queue = ts_df['aql'].mean() if 'aql' in ts_df.columns else 0
        mp_avg_queue = mp_df['aql'].mean() if (has_mp and 'aql' in mp_df.columns) else 0
        
        fixed_avg_wait = fixed_df['awt'].mean() if 'awt' in fixed_df.columns else 0
        ts_avg_wait = ts_df['awt'].mean() if 'awt' in ts_df.columns else 0
        mp_avg_wait = mp_df['awt'].mean() if (has_mp and 'awt' in mp_df.columns) else 0
        
        fixed_avg_occ = fixed_df['att'].mean() if 'att' in fixed_df.columns else 0 # Using ATT as proxy for third stat
        ts_avg_occ = ts_df['att'].mean() if 'att' in ts_df.columns else 0
        mp_avg_occ = mp_df['att'].mean() if (has_mp and 'att' in mp_df.columns) else 0
        
        fixed_peak_queue = fixed_df['aql'].max() if 'aql' in fixed_df.columns else 0
        ts_peak_queue = ts_df['aql'].max() if 'aql' in ts_df.columns else 0
        mp_peak_queue = mp_df['aql'].max() if (has_mp and 'aql' in mp_df.columns) else 0
    
    queue_improvement = ((fixed_avg_queue - ts_avg_queue) / fixed_avg_queue * 100) if fixed_avg_queue > 0 else 0
    wait_improvement = ((fixed_avg_wait - ts_avg_wait) / fixed_avg_wait * 100) if fixed_avg_wait > 0 else 0
    
    # Show 4 metric cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        delta = f"{((fixed_avg_queue - ts_avg_queue) / fixed_avg_queue * 100):+.1f}% vs FT" if fixed_avg_queue > 0 else "N/A"
        render_metric_card("Avg Queue (TS)", f"{ts_avg_queue:.1f}", delta=delta, icon="🚗")
    
    with col2:
        delta = f"{((fixed_avg_wait - ts_avg_wait) / fixed_avg_wait * 100):+.1f}% vs FT" if fixed_avg_wait > 0 else "N/A"
        render_metric_card("Avg Wait (TS)", f"{ts_avg_wait:.1f}s", delta=delta, icon="⏱️")
    
    with col3:
        if has_mp and mp_avg_queue > 0:
            delta_mp = f"{((mp_avg_queue - ts_avg_queue) / mp_avg_queue * 100):+.1f}% vs MP"
        else:
            delta_mp = "N/A"
        render_metric_card("vs MaxPressure", f"{ts_avg_queue:.1f}", delta=delta_mp, icon="🎯")
    
    with col4:
        render_metric_card("Controllers", "3" if has_mp else "2", "FixedTime + MP + TS" if has_mp else "FixedTime + TS", icon="🧪")
    
    st.markdown("---")
    
    # Main charts
    st.subheader(f"{metric_choice} Over Time")
    
    # Prepare data for plotting
    plot_data = []
    
    if not fixed_df.empty:
        fixed_plot = fixed_df.copy()
        fixed_plot['Controller'] = 'FixedTime'
        plot_data.append(fixed_plot)
        
    if has_mp:
        mp_plot = mp_df.copy()
        mp_plot['Controller'] = 'MaxPressure'
        plot_data.append(mp_plot)
    
    if not ts_df.empty:
        ts_plot = ts_df.copy()
        ts_plot['Controller'] = 'TrafficSense'
        plot_data.append(ts_plot)
    
    color_map = {"FixedTime": "#8b949e", "MaxPressure": "#d29922", "TrafficSense": "#58a6ff"}
    
    if plot_data:
        combined_df = pd.concat(plot_data, ignore_index=True)
        
        if 'total_queued' in combined_df.columns:
            metric_col_map = {
                "Queue Length": "total_queued",
                "Wait Time": "tau",
                "Occupancy": "occupancy",
                "Pressure": "rho"
            }
        else:
            metric_col_map = {
                "Queue Length": "aql",
                "Wait Time": "awt",
                "Occupancy": "att", # Proxy
                "Pressure": "throughput" # Proxy
            }
        
        y_col = metric_col_map.get(metric_choice, "total_queued" if 'total_queued' in combined_df.columns else "aql")
        
        # Create plot
        if chart_type == "Line":
            fig = px.line(
                combined_df,
                x="step",
                y=y_col,
                color="Controller",
                title=f"{metric_choice} Comparison",
                labels={"step": "Simulation Step", y_col: metric_choice},
                color_discrete_map=color_map
            )
        elif chart_type == "Bar":
            # Aggregate by step bins for bar chart
            combined_df['step_bin'] = (combined_df['step'] // 20) * 20
            agg_df = combined_df.groupby(['step_bin', 'Controller'])[y_col].mean().reset_index()
            fig = px.bar(
                agg_df,
                x="step_bin",
                y=y_col,
                color="Controller",
                barmode="group",
                title=f"{metric_choice} Comparison (Binned)",
                labels={"step_bin": "Simulation Step", y_col: metric_choice},
                color_discrete_map=color_map
            )
        else:  # Area
            fig = px.area(
                combined_df,
                x="step",
                y=y_col,
                color="Controller",
                title=f"{metric_choice} Comparison",
                labels={"step": "Simulation Step", y_col: metric_choice},
                color_discrete_map=color_map
            )
        
        fig.update_layout(
            plot_bgcolor="#0e1117",
            paper_bgcolor="#0e1117",
            font_color="#e6edf3",
            legend_bgcolor="#161b22",
            xaxis_gridcolor="#30363d",
            yaxis_gridcolor="#30363d"
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Distribution comparison
    st.subheader("Distribution Comparison")
    
    dist_col1, dist_col2 = st.columns(2)
    
    with dist_col1:
        st.markdown("#### Queue Length Distribution")
        queue_col = 'total_queued' if 'total_queued' in fixed_df.columns else 'aql'
        if not fixed_df.empty and not ts_df.empty:
            fig_dist = go.Figure()
            fig_dist.add_trace(go.Histogram(
                x=fixed_df[queue_col],
                name='FixedTime',
                opacity=0.7,
                marker_color='#8b949e'
            ))
            if has_mp:
                fig_dist.add_trace(go.Histogram(
                    x=mp_df[queue_col],
                    name='MaxPressure',
                    opacity=0.7,
                    marker_color='#d29922'
                ))
            fig_dist.add_trace(go.Histogram(
                x=ts_df[queue_col],
                name='TrafficSense',
                opacity=0.7,
                marker_color='#58a6ff'
            ))
            fig_dist.update_layout(
                barmode='overlay',
                plot_bgcolor="#0e1117",
                paper_bgcolor="#0e1117",
                font_color="#e6edf3",
                xaxis_title="Queue Length",
                yaxis_title="Frequency",
                legend_bgcolor="#161b22"
            )
            st.plotly_chart(fig_dist, use_container_width=True)
    
    with dist_col2:
        st.markdown("#### Wait Time Distribution")
        wait_col = 'tau' if 'tau' in fixed_df.columns else 'awt'
        if not fixed_df.empty and not ts_df.empty:
            fig_wait = go.Figure()
            fig_wait.add_trace(go.Box(
                y=fixed_df[wait_col],
                name='FixedTime',
                marker_color='#8b949e'
            ))
            if has_mp:
                fig_wait.add_trace(go.Box(
                    y=mp_df[wait_col],
                    name='MaxPressure',
                    marker_color='#d29922'
                ))
            fig_wait.add_trace(go.Box(
                y=ts_df[wait_col],
                name='TrafficSense',
                marker_color='#58a6ff'
            ))
            fig_wait.update_layout(
                plot_bgcolor="#0e1117",
                paper_bgcolor="#0e1117",
                font_color="#e6edf3",
                yaxis_title="Wait Time (s)",
                legend_bgcolor="#161b22"
            )
            st.plotly_chart(fig_wait, use_container_width=True)
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src import config
from src.dashboard.utils import apply_theme, render_metric_card

st.set_page_config(page_title="Analytics | TrafficSense", layout="wide", page_icon="📈")
apply_theme()

st.title("📈 Performance Analytics")
st.html("<p style='color: #94a3b8; font-size: 1.1rem; margin-bottom: 2rem;'>Comprehensive performance comparison of TrafficSense cooperative control versus traditional baselines.</p>")

# Load data
@st.cache_data
def load_metrics(controller):
    path = config.SIMULATION_RESULTS_DIR / f'{controller}_360_metrics.csv'
    if not path.exists():
        path = config.SIMULATION_RESULTS_DIR / f'{controller}_metrics.csv'
    if path.exists():
        return pd.read_csv(str(path))
    return pd.DataFrame()

@st.cache_data
def load_summary(controller):
    path = config.SIMULATION_RESULTS_DIR / f'{controller}_360_summary.json'
    if not path.exists():
        path = config.SIMULATION_RESULTS_DIR / f'{controller}_summary.json'
    if path.exists():
        import json
        with open(str(path), 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

fixed_df = load_metrics('fixedtime')
ts_df = load_metrics('trafficsense')
mp_df = load_metrics('maxpressure')
fixed_summary = load_summary('fixedtime')
ts_summary = load_summary('trafficsense')
mp_summary = load_summary('maxpressure')

has_data = not ts_df.empty
has_mp = not mp_df.empty

# Sidebar
with st.sidebar:
    st.markdown("### 📊 Chart Options")
    smoothing = st.slider("Smoothing Factor", 1, 20, 5)
    st.markdown("---")
    st.markdown("### 📋 Baselines")
    st.checkbox("FixedTime (Static)", value=True, disabled=True)
    st.checkbox("MaxPressure", value=has_mp, disabled=True)
    st.checkbox("TrafficSense", value=True, disabled=True)

if not has_data:
    st.warning("No analytics data found. Please run the simulation first.")
    st.stop()

# Summary report
st.markdown("### 📊 Executive Summary")

fixed_avg_queue = fixed_summary.get('avg_queue_length', 0)
ts_avg_queue = ts_summary.get('avg_queue_length', 0)
fixed_avg_wait = fixed_summary.get('avg_wait_time', 0)
ts_avg_wait = ts_summary.get('avg_wait_time', 0)
mp_avg_queue = mp_summary.get('avg_queue_length', 0) if has_mp else 0
mp_avg_wait = mp_summary.get('avg_wait_time', 0) if has_mp else 0

queue_improvement = ((fixed_avg_queue - ts_avg_queue) / fixed_avg_queue * 100) if fixed_avg_queue > 0 else 0
wait_improvement = ((fixed_avg_wait - ts_avg_wait) / fixed_avg_wait * 100) if fixed_avg_wait > 0 else 0

col1, col2 = st.columns(2)
with col1:
    render_metric_card("Queue Reduction (vs Fixed)", f"{abs(queue_improvement):.1f}%", queue_improvement, icon="📉", color_theme="green")
with col2:
    render_metric_card("Wait Time Reduction (vs Fixed)", f"{abs(wait_improvement):.1f}%", wait_improvement, icon="⏱️", color_theme="green")

st.markdown("---")
st.markdown("### 📈 Time-Series Analysis")

tab1, tab2 = st.tabs(["Queue Length", "Wait Time"])

with tab1:
    fig_q = go.Figure()
    
    if not fixed_df.empty:
        y_smooth = fixed_df['avg_queue_length'].rolling(window=smoothing, min_periods=1).mean()
        fig_q.add_trace(go.Scatter(x=fixed_df['step'], y=y_smooth, mode='lines', name='FixedTime', line=dict(color='#94a3b8', width=2)))
        
    if has_mp:
        y_smooth = mp_df['avg_queue_length'].rolling(window=smoothing, min_periods=1).mean()
        fig_q.add_trace(go.Scatter(x=mp_df['step'], y=y_smooth, mode='lines', name='MaxPressure', line=dict(color='#f59e0b', width=2)))
        
    if not ts_df.empty:
        y_smooth = ts_df['avg_queue_length'].rolling(window=smoothing, min_periods=1).mean()
        fig_q.add_trace(go.Scatter(x=ts_df['step'], y=y_smooth, mode='lines', name='TrafficSense', line=dict(color='#10b981', width=3)))
    
    fig_q.update_layout(
        title="Average Queue Length Over Time",
        xaxis_title="Simulation Step",
        yaxis_title="Vehicles in Queue",
        template="plotly_dark",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        margin=dict(l=40, r=40, t=40, b=40)
    )
    st.plotly_chart(fig_q, use_container_width=True)

with tab2:
    fig_w = go.Figure()
    
    if not fixed_df.empty:
        y_smooth = fixed_df['avg_wait_time'].rolling(window=smoothing, min_periods=1).mean()
        fig_w.add_trace(go.Scatter(x=fixed_df['step'], y=y_smooth, mode='lines', name='FixedTime', line=dict(color='#94a3b8', width=2)))
        
    if has_mp:
        y_smooth = mp_df['avg_wait_time'].rolling(window=smoothing, min_periods=1).mean()
        fig_w.add_trace(go.Scatter(x=mp_df['step'], y=y_smooth, mode='lines', name='MaxPressure', line=dict(color='#f59e0b', width=2)))
        
    if not ts_df.empty:
        y_smooth = ts_df['avg_wait_time'].rolling(window=smoothing, min_periods=1).mean()
        fig_w.add_trace(go.Scatter(x=ts_df['step'], y=y_smooth, mode='lines', name='TrafficSense', line=dict(color='#10b981', width=3)))
    
    fig_w.update_layout(
        title="Average Wait Time Over Time",
        xaxis_title="Simulation Step",
        yaxis_title="Wait Time (seconds)",
        template="plotly_dark",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01),
        margin=dict(l=40, r=40, t=40, b=40)
    )
    st.plotly_chart(fig_w, use_container_width=True)

st.markdown("---")
st.markdown("### 🗃️ Raw Metric Data")

tabs = st.tabs(["FixedTime", "MaxPressure", "TrafficSense"] if has_mp else ["FixedTime", "TrafficSense"])
if not fixed_df.empty:
    with tabs[0]:
        st.dataframe(fixed_df, use_container_width=True)
            <tr>
                <td style="padding: 10px;">Peak Queue</td>
                <td style="text-align: center; padding: 10px;">{int(fixed_peak_queue)}</td>
                {"<td style='text-align: center; padding: 10px;'>" + f"{int(mp_peak_queue)}" + "</td>" if has_mp else ""}
                <td style="text-align: center; padding: 10px; color: #58a6ff; font-weight: bold;">{int(ts_peak_queue)}</td>
                <td style="text-align: center; padding: 10px; color: {'#3fb950' if ts_peak_queue < fixed_peak_queue else '#f85149'};">{int(fixed_peak_queue - ts_peak_queue)}</td>
            </tr>
        </table>
    </div>
    """
    st.html(summary_html)
    
    # Key insight
    if queue_improvement > 0 or wait_improvement > 0:
        st.success(f"🎉 TrafficSense shows improvement over FixedTime baseline! Queue reduced by {queue_improvement:.1f}%, wait time reduced by {wait_improvement:.1f}%.")
    else:
        st.info("📊 Controllers show comparable performance.")

else:
    st.warning("⚠️ Simulation data not found. Please run the network simulation first (Step 3.5).")
    
    st.html("""
    ### How to generate data:
    1. Ensure Ollama is running in WSL
    2. Run: `python src/simulation/run_trafficsense_sim.py`
    3. Return to this page to see analytics
    """)
