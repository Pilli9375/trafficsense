import os
import re

files = [
    'src/dashboard/app.py',
    'src/dashboard/pages/1_live_monitor.py',
    'src/dashboard/pages/2_network_control.py',
    'src/dashboard/pages/3_analytics.py',
]

for f in files:
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    content = content.replace('st.markdown(\"\"\"', 'st.html(\"\"\"')
    content = content.replace(', unsafe_allow_html=True', '')
    content = content.replace('st.markdown(html_content)', 'st.html(html_content)')
    content = content.replace('st.markdown(status_html)', 'st.html(status_html)')
    content = content.replace('st.markdown(summary_html)', 'st.html(summary_html)')
    content = content.replace('st.markdown(coop_html)', 'st.html(coop_html)')
    content = content.replace('st.markdown(class_html)', 'st.html(class_html)')
    content = content.replace('class_chart.markdown(class_html)', 'class_chart.html(class_html)')
    
    content = content.replace('count_metric.markdown(f\"\"\"', 'count_metric.html(f\"\"\"')
    content = content.replace('severity_metric.markdown(f\"\"\"', 'severity_metric.html(f\"\"\"')
    content = content.replace('conf_metric.markdown(f\"\"\"', 'conf_metric.html(f\"\"\"')
    content = content.replace('fps_metric.markdown(f\"\"\"', 'fps_metric.html(f\"\"\"')
    
    content = content.replace('st.markdown(\"<h2 style', 'st.html(\"<h2 style')
    content = content.replace('st.markdown(\"<p style', 'st.html(\"<p style')
    content = content.replace('st.markdown(\"<h3 style', 'st.html(\"<h3 style')
    content = content.replace('st.markdown(\"<br>', 'st.html(\"<br>')
    content = content.replace('st.markdown(\"<br><br>\")', 'st.html(\"<br><br>\")')
    
    with open(f, 'w', encoding='utf-8') as file:
        file.write(content)
