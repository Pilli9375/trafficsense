import streamlit as st

def intersection_card(iid, phase, queued, moving, severity, reasoning=""):
    """Render an intersection status card."""
    severity_colors = {
        'none': '#3fb950',
        'low': '#58a6ff',
        'moderate': '#d29922',
        'high': '#f85149',
        'critical': '#da3633'
    }
    color = severity_colors.get(severity, '#8b949e')
    
    st.markdown(f"""
    <div style="background-color: #1c2128; border-radius: 10px; padding: 20px; margin-bottom: 15px; border: 1px solid #30363d;">
        <h4 style="color: #e6edf3; margin-top: 0;">🚦 Intersection {iid}</h4>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
            <div>
                <p style="color: #8b949e; margin: 0;">Phase</p>
                <p style="color: #e6edf3; font-weight: bold; margin: 0;">{phase}</p>
            </div>
            <div>
                <p style="color: #8b949e; margin: 0;">Queued</p>
                <p style="color: #e6edf3; font-weight: bold; margin: 0;">{queued}</p>
            </div>
            <div>
                <p style="color: #8b949e; margin: 0;">Moving</p>
                <p style="color: #e6edf3; font-weight: bold; margin: 0;">{moving}</p>
            </div>
            <div>
                <p style="color: #8b949e; margin: 0;">Severity</p>
                <p style="color: {color}; font-weight: bold; margin: 0;">{severity.upper()}</p>
            </div>
        </div>
        {f'<p style="color: #8b949e; margin-top: 10px; font-size: 12px;">💡 {reasoning}</p>' if reasoning else ''}
    </div>
    """, unsafe_allow_html=True)
