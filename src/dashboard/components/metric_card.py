import streamlit as st

def metric_card(title, value, delta=None, icon="📊"):
    """Render a styled metric card."""
    delta_html = f'<span style="color: #3fb950;">▲ {delta}</span>' if delta else ''
    st.markdown(f"""
    <div style="background-color: #1c2128; border-radius: 10px; padding: 15px; border-left: 4px solid #3b82f6; margin-bottom: 10px;">
        <div style="font-size: 14px; color: #8b949e;">{icon} {title}</div>
        <div style="font-size: 32px; font-weight: bold; color: #e6edf3;">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)
