import streamlit as st
import cv2
import numpy as np
import os
import sys
import time
from pathlib import Path
from collections import Counter, deque

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'perception'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils import apply_theme, render_metric_card

st.set_page_config(page_title="Live Monitor | TrafficSense", layout="wide")
apply_theme()

st.title("📹 Live Traffic Monitor")
st.markdown("Real-time vehicle detection, tracking, and congestion analysis using YOLOv8n.")

# Load model
@st.cache_resource
def get_model():
    from ultralytics import YOLO
    model_path = r'C:\Pilli\trafficsense\models\yolo\best.pt'
    if os.path.exists(model_path):
        return YOLO(model_path)
    return None

model = get_model()

# Sidebar controls
with st.sidebar:
    st.markdown("### ⚙️ Controls")
    
    uploaded_file = st.file_uploader("Upload Traffic Video", type=['mp4', 'avi', 'mov'])
    
    conf_threshold = st.slider("Confidence Threshold", 0.1, 1.0, 0.3, 0.05)
    sample_rate = st.slider("Process Every Nth Frame", 1, 10, 1)
    max_frames = st.number_input("Max Frames (0 = all)", 0, 10000, 300)
    
    st.markdown("---")
    st.markdown("### 📊 Legend")
    st.markdown("🟢 Low | 🟡 Moderate | 🟠 High | 🔴 Critical")

# Main layout
if uploaded_file is None:
    st.info("👆 Upload a traffic video from the sidebar to begin detection.")
    
    # Show demo stats from previous run if available
    st.subheader("Last Run Summary")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metric_card("Vehicles Detected", "--", icon="🚗")
    with col2:
        render_metric_card("Congestion", "--", icon="🚦")
    with col3:
        render_metric_card("Avg Confidence", "--", icon="🎯")
    with col4:
        render_metric_card("Processing FPS", "--", icon="⚡")
    
else:
    # Save uploaded file
    temp_path = r'C:\Pilli\trafficsense\outputs\uploaded_video.mp4'
    with open(temp_path, 'wb') as f:
        f.write(uploaded_file.read())
    
    st.success(f"Video uploaded: {uploaded_file.name}")
    
    # Open video
    cap = cv2.VideoCapture(temp_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    st.markdown(f"**Resolution**: {width}×{height} | **FPS**: {fps:.1f} | **Total Frames**: {total_frames}")
    
    # Layout
    video_col, metrics_col = st.columns([2, 1])
    
    with video_col:
        st.subheader("Detection Feed")
        frame_placeholder = st.empty()
        
    with metrics_col:
        st.subheader("Live Metrics")
        count_metric = st.empty()
        severity_metric = st.empty()
        conf_metric = st.empty()
        fps_metric = st.empty()
        class_dist = st.empty()
        
        st.markdown("---")
        st.subheader("Class Distribution")
        class_chart = st.empty()
        
        st.markdown("---")
        st.subheader("Congestion Timeline")
        timeline_chart = st.empty()
    
    # Processing
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    frame_idx = 0
    processed = 0
    all_counts = []
    all_severities = []
    all_confidences = []
    class_counter = Counter()
    severity_history = deque(maxlen=100)
    
    start_time = time.time()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_idx += 1
        
        if frame_idx % sample_rate != 0:
            continue
        
        if max_frames > 0 and processed >= max_frames:
            break
        
        # Run detection
        results = model(frame, conf=conf_threshold, verbose=False)[0]
        
        boxes = results.boxes.xyxy.cpu().numpy() if results.boxes else []
        confs = results.boxes.conf.cpu().numpy() if results.boxes else []
        cls_ids = results.boxes.cls.cpu().numpy().astype(int) if results.boxes else []
        
        # Draw boxes
        annotated = frame.copy()
        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = map(int, box)
            cls_id = int(cls_ids[i])
            cls_name = model.names.get(cls_id, f'cls_{cls_id}')
            conf = float(confs[i])
            
            color = (0, 255, 0)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            label = f"{cls_name} {conf:.2f}"
            cv2.putText(annotated, label, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Metrics
        count = len(boxes)
        avg_conf = float(np.mean(confs)) if len(confs) > 0 else 0.0
        
        for cid in cls_ids:
            class_counter[model.names.get(int(cid), f'cls_{int(cid)}')] += 1
        
        # Congestion severity
        density = count * 2.0  # rough heuristic
        if density > 80:
            severity = 'critical'
            sev_color = '#da3633'
        elif density > 50:
            severity = 'high'
            sev_color = '#f85149'
        elif density > 25:
            severity = 'moderate'
            sev_color = '#d29922'
        elif density > 10:
            severity = 'low'
            sev_color = '#58a6ff'
        else:
            severity = 'none'
            sev_color = '#3fb950'
        
        all_counts.append(count)
        all_severities.append(severity)
        all_confidences.append(avg_conf)
        severity_history.append({'frame': processed, 'severity': severity, 'count': count})
        
        # Update video frame
        annotated_rgb = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)
        frame_placeholder.image(annotated_rgb, use_container_width=True)
        
        # Update metrics
        count_metric.markdown(f"""
        <div style="background-color: #1c2128; border-radius: 10px; padding: 15px; border-left: 4px solid #3b82f6; margin-bottom: 10px;">
            <div style="font-size: 14px; color: #8b949e;">🚗 Vehicles Detected</div>
            <div style="font-size: 32px; font-weight: bold; color: #e6edf3;">{count}</div>
        </div>
        """, unsafe_allow_html=True)
        
        severity_metric.markdown(f"""
        <div style="background-color: #1c2128; border-radius: 10px; padding: 15px; border-left: 4px solid {sev_color}; margin-bottom: 10px;">
            <div style="font-size: 14px; color: #8b949e;">🚦 Congestion</div>
            <div style="font-size: 32px; font-weight: bold; color: {sev_color};">{severity.upper()}</div>
        </div>
        """, unsafe_allow_html=True)
        
        conf_metric.markdown(f"""
        <div style="background-color: #1c2128; border-radius: 10px; padding: 15px; border-left: 4px solid #a371f7; margin-bottom: 10px;">
            <div style="font-size: 14px; color: #8b949e;">🎯 Avg Confidence</div>
            <div style="font-size: 32px; font-weight: bold; color: #e6edf3;">{avg_conf:.2f}</div>
        </div>
        """, unsafe_allow_html=True)
        
        elapsed = time.time() - start_time
        proc_fps = processed / elapsed if elapsed > 0 else 0
        fps_metric.markdown(f"""
        <div style="background-color: #1c2128; border-radius: 10px; padding: 15px; border-left: 4px solid #3fb950; margin-bottom: 10px;">
            <div style="font-size: 14px; color: #8b949e;">⚡ Processing FPS</div>
            <div style="font-size: 32px; font-weight: bold; color: #e6edf3;">{proc_fps:.1f}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Class distribution
        if class_counter:
            top_classes = class_counter.most_common(5)
            class_html = "<div style='background-color: #1c2128; border-radius: 10px; padding: 15px;'>"
            for cls, cnt in top_classes:
                pct = cnt / sum(class_counter.values()) * 100
                class_html += f"<div style='margin-bottom: 8px;'><span style='color: #8b949e;'>{cls}</span><div style='background: #30363d; border-radius: 4px; height: 20px;'><div style='background: #58a6ff; width: {pct}%; height: 100%; border-radius: 4px;'></div></div><span style='color: #e6edf3; font-size: 12px;'>{cnt} ({pct:.1f}%)</span></div>"
            class_html += "</div>"
            class_chart.markdown(class_html, unsafe_allow_html=True)
        
        # Progress
        target = min(max_frames if max_frames > 0 else total_frames, total_frames)
        progress = min(processed / target, 1.0)
        progress_bar.progress(progress)
        status_text.text(f"Processing frame {processed}/{target} | FPS: {proc_fps:.1f}")
        
        processed += 1
    
    cap.release()
    
    # Final summary
    st.markdown("---")
    st.subheader("📋 Processing Summary")
    
    if all_counts:
        avg_count = sum(all_counts) / len(all_counts)
        avg_conf = sum(all_confidences) / len(all_confidences)
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("Avg Vehicles/Frame", f"{avg_count:.1f}")
        with c2:
            st.metric("Peak Vehicles", max(all_counts))
        with c3:
            st.metric("Avg Confidence", f"{avg_conf:.2f}")
        with c4:
            st.metric("Total Processed", processed)
        
        # Severity distribution
        sev_counts = Counter(all_severities)
        st.bar_chart({k: v for k, v in sev_counts.items()})
        
        # Export button
        if st.button("💾 Export Detection Results"):
            export_dir = r'C:\Pilli\trafficsense\outputs\detection_videos'
            os.makedirs(export_dir, exist_ok=True)
            st.success(f"Results ready for export from {export_dir}")
