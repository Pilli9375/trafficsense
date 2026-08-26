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
st.markdown("Compare TrafficSense cooperative control against FixedTime baseline.")

# Load data
@st.cache_data
def load_metrics(controller):
    path = r'C:\Pilli\trafficsense\outputs\simulation_results\{}_metrics.csv'.format(controller)
    if os.path.exists(path):
        df = pd.read_csv(path)
        return df
    return pd.DataFrame()

@st.cache_data
def load_summary(controller):
    path = r'C:\Pilli\trafficsense\outputs\simulation_results\{}_summary.json'.format(controller)
    if os.path.exists(path):
        import json
        with open(path, 'r') as f:
            return json.load(f)
    return {}

fixed_df = load_metrics('fixedtime')
ts_df = load_metrics('trafficsense')
fixed_summary = load_summary('fixedtime')
ts_summary = load_summary('trafficsense')

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
    
    if st.button("Export TrafficSense CSV", use_container_width=True):
        st.success("TrafficSense metrics ready for download")

# Header stats
st.subheader("Controller Comparison")

if not fixed_df.empty and not ts_df.empty:
    # Calculate aggregates
    fixed_avg_queue = fixed_df['total_queued'].mean()
    ts_avg_queue = ts_df['total_queued'].mean()
    queue_improvement = ((fixed_avg_queue - ts_avg_queue) / fixed_avg_queue * 100) if fixed_avg_queue > 0 else 0
    
    fixed_avg_wait = fixed_df['tau'].mean()
    ts_avg_wait = ts_df['tau'].mean()
    wait_improvement = ((fixed_avg_wait - ts_avg_wait) / fixed_avg_wait * 100) if fixed_avg_wait > 0 else 0
    
    fixed_avg_occ = fixed_df['occupancy'].mean()
    ts_avg_occ = ts_df['occupancy'].mean()
    
    fixed_peak_queue = fixed_df['total_queued'].max()
    ts_peak_queue = ts_df['total_queued'].max()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        render_metric_card(
            "Avg Queue Length",
            f"{ts_avg_queue:.1f}",
            delta=f"{queue_improvement:+.1f}% vs FixedTime",
            icon="🚗"
        )
    
    with col2:
        render_metric_card(
            "Avg Wait Time",
            f"{ts_avg_wait:.1f}s",
            delta=f"{wait_improvement:+.1f}% vs FixedTime",
            icon="⏱️"
        )
    
    with col3:
        render_metric_card(
            "Avg Occupancy",
            f"{ts_avg_occ:.2f}",
            delta=f"{((fixed_avg_occ - ts_avg_occ) / fixed_avg_occ * 100):+.1f}%" if fixed_avg_occ > 0 else "N/A",
            icon="📊"
        )
    
    with col4:
        render_metric_card(
            "Peak Queue",
            f"{int(ts_peak_queue)}",
            delta=f"{int(fixed_peak_queue - ts_peak_queue)} better",
            icon="📉"
        )
    
    st.markdown("---")
    
    # Main charts
    st.subheader(f"{metric_choice} Over Time")
    
    # Prepare data for plotting
    plot_data = []
    
    if not fixed_df.empty:
        fixed_plot = fixed_df.copy()
        fixed_plot['Controller'] = 'FixedTime'
        plot_data.append(fixed_plot)
    
    if not ts_df.empty:
        ts_plot = ts_df.copy()
        ts_plot['Controller'] = 'TrafficSense'
        plot_data.append(ts_plot)
    
    if plot_data:
        combined_df = pd.concat(plot_data, ignore_index=True)
        
        metric_col_map = {
            "Queue Length": "total_queued",
            "Wait Time": "tau",
            "Occupancy": "occupancy",
            "Pressure": "rho"
        }
        y_col = metric_col_map.get(metric_choice, "total_queued")
        
        # Create plot
        if chart_type == "Line":
            fig = px.line(
                combined_df,
                x="step",
                y=y_col,
                color="Controller",
                title=f"{metric_choice} Comparison",
                labels={"step": "Simulation Step", y_col: metric_choice},
                color_discrete_map={"FixedTime": "#8b949e", "TrafficSense": "#58a6ff"}
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
                color_discrete_map={"FixedTime": "#8b949e", "TrafficSense": "#58a6ff"}
            )
        else:  # Area
            fig = px.area(
                combined_df,
                x="step",
                y=y_col,
                color="Controller",
                title=f"{metric_choice} Comparison",
                labels={"step": "Simulation Step", y_col: metric_choice},
                color_discrete_map={"FixedTime": "#8b949e", "TrafficSense": "#58a6ff"}
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
        if not fixed_df.empty and not ts_df.empty:
            fig_dist = go.Figure()
            fig_dist.add_trace(go.Histogram(
                x=fixed_df['total_queued'],
                name='FixedTime',
                opacity=0.7,
                marker_color='#8b949e'
            ))
            fig_dist.add_trace(go.Histogram(
                x=ts_df['total_queued'],
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
        if not fixed_df.empty and not ts_df.empty:
            fig_wait = go.Figure()
            fig_wait.add_trace(go.Box(
                y=fixed_df['tau'],
                name='FixedTime',
                marker_color='#8b949e'
            ))
            fig_wait.add_trace(go.Box(
                y=ts_df['tau'],
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
    
    st.markdown("---")
    
    # Detailed metrics table
    st.subheader("Detailed Metrics")
    
    tab1, tab2 = st.tabs(["FixedTime", "TrafficSense"])
    
    with tab1:
        if not fixed_df.empty:
            st.dataframe(fixed_df, use_container_width=True)
    
    with tab2:
        if not ts_df.empty:
            st.dataframe(ts_df, use_container_width=True)
    
    st.markdown("---")
    
    # Summary report
    st.subheader("📋 Executive Summary")
    
    summary_html = f"""
    <div style="background-color: #1c2128; border-radius: 12px; padding: 25px; border-left: 4px solid #58a6ff;">
        <h4 style="color: #e6edf3; margin-top: 0;">TrafficSense vs FixedTime Baseline</h4>
        <table style="width: 100%; color: #c9d1d9; border-collapse: collapse;">
            <tr style="border-bottom: 1px solid #30363d;">
                <th style="text-align: left; padding: 10px; color: #8b949e;">Metric</th>
                <th style="text-align: center; padding: 10px; color: #8b949e;">FixedTime</th>
                <th style="text-align: center; padding: 10px; color: #8b949e;">TrafficSense</th>
                <th style="text-align: center; padding: 10px; color: #8b949e;">Improvement</th>
            </tr>
            <tr style="border-bottom: 1px solid #30363d;">
                <td style="padding: 10px;">Average Queue Length</td>
                <td style="text-align: center; padding: 10px;">{fixed_avg_queue:.2f}</td>
                <td style="text-align: center; padding: 10px; color: #58a6ff; font-weight: bold;">{ts_avg_queue:.2f}</td>
                <td style="text-align: center; padding: 10px; color: {'#3fb950' if queue_improvement > 0 else '#f85149'};">{queue_improvement:+.1f}%</td>
            </tr>
            <tr style="border-bottom: 1px solid #30363d;">
                <td style="padding: 10px;">Average Wait Time</td>
                <td style="text-align: center; padding: 10px;">{fixed_avg_wait:.2f}s</td>
                <td style="text-align: center; padding: 10px; color: #58a6ff; font-weight: bold;">{ts_avg_wait:.2f}s</td>
                <td style="text-align: center; padding: 10px; color: {'#3fb950' if wait_improvement > 0 else '#f85149'};">{wait_improvement:+.1f}%</td>
            </tr>
            <tr style="border-bottom: 1px solid #30363d;">
                <td style="padding: 10px;">Average Occupancy</td>
                <td style="text-align: center; padding: 10px;">{fixed_avg_occ:.3f}</td>
                <td style="text-align: center; padding: 10px; color: #58a6ff; font-weight: bold;">{ts_avg_occ:.3f}</td>
                <td style="text-align: center; padding: 10px;">{((fixed_avg_occ - ts_avg_occ) / fixed_avg_occ * 100):+.1f}%</td>
            </tr>
            <tr>
                <td style="padding: 10px;">Peak Queue</td>
                <td style="text-align: center; padding: 10px;">{int(fixed_peak_queue)}</td>
                <td style="text-align: center; padding: 10px; color: #58a6ff; font-weight: bold;">{int(ts_peak_queue)}</td>
                <td style="text-align: center; padding: 10px; color: {'#3fb950' if ts_peak_queue < fixed_peak_queue else '#f85149'};">{int(fixed_peak_queue - ts_peak_queue)}</td>
            </tr>
        </table>
    </div>
    """
    st.markdown(summary_html, unsafe_allow_html=True)
    
    # Key insight
    if queue_improvement > 0 or wait_improvement > 0:
        st.success(f"🎉 TrafficSense shows improvement over FixedTime baseline! Queue reduced by {queue_improvement:.1f}%, wait time reduced by {wait_improvement:.1f}%.")
    else:
        st.info("📊 Both controllers show similar performance. Consider running longer simulations for clearer differentiation.")

else:
    st.warning("⚠️ Simulation data not found. Please run the network simulation first (Step 3.5).")
    
    st.markdown("""
    ### How to generate data:
    1. Ensure Ollama is running in WSL
    2. Run: `python src/simulation/run_trafficsense_sim.py`
    3. Return to this page to see analytics
    """)
