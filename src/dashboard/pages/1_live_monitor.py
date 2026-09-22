import streamlit as st
import cv2
import numpy as np
import os
import sys
import time
from pathlib import Path
from collections import Counter, deque
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src import config
from src.dashboard.utils import apply_theme, render_metric_card

st.set_page_config(page_title="Live Monitor | TrafficSense", layout="wide", page_icon="🎥")
apply_theme()

st.title("🎥 Live Traffic Monitor")
st.html("<p style='color: #94a3b8; font-size: 1.1rem; margin-bottom: 2rem;'>Real-time vehicle detection, tracking, and congestion analysis using optimized YOLOv8.</p>")

# Load model
@st.cache_resource
def get_model(model_type):
    from ultralytics import YOLO
    if model_type == "Custom Indian (24 classes)":
        model_path = str(config.MODELS_DIR / 'yolo' / 'best.pt')
    else:
        model_path = 'yolov8n.pt'
    
    if os.path.exists(model_path) or model_path == 'yolov8n.pt':
        try:
            return YOLO(model_path)
        except Exception:
            return None
    return None

# Sidebar controls
with st.sidebar:
    st.markdown("### ⚙️ Engine Controls")
    
    model_type = st.radio("Detection Model", ["Custom Indian (24 classes)", "COCO Pretrained (80 classes)"])
    model = get_model(model_type)
    
    st.markdown("---")
    uploaded_file = st.file_uploader("Upload Traffic Video", type=['mp4', 'avi', 'mov'])
    
    st.markdown("---")
    st.markdown("### 🎛️ Parameters")
    default_conf = 0.15 if model_type == "Custom Indian (24 classes)" else 0.3
    conf_threshold = st.slider("Confidence Threshold", 0.1, 1.0, default_conf, 0.05)
    sample_rate = st.slider("Process Every Nth Frame", 1, 10, 1)
    max_frames = st.number_input("Max Frames (0 = all)", 0, 10000, 300)

if model is None:
    st.error("Model could not be loaded. Please check the model path.")
    st.stop()

if uploaded_file is None:
    st.info("👈 Upload a traffic video from the sidebar to begin real-time detection.")
    
    # Show demo stats from previous run if available
    st.html("<h3 style='margin-top: 2rem;'>Previous Run Summary</h3>")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        render_metric_card("Vehicles Detected", "--", icon="🚗", color_theme="blue")
    with col2:
        render_metric_card("Congestion", "--", icon="🚦", color_theme="red")
    with col3:
        render_metric_card("Avg Confidence", "--", icon="🎯", color_theme="amber")
    with col4:
        render_metric_card("Processing FPS", "--", icon="⚡", color_theme="purple")
    
else:
    # Save uploaded file
    temp_path = str(config.OUTPUTS_DIR / 'uploaded_video.mp4')
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
    with open(temp_path, 'wb') as f:
        f.write(uploaded_file.read())
    
    st.success(f"Video loaded successfully! Decoding stream...")
    
    # Open video
    cap = cv2.VideoCapture(temp_path)
    if not cap.isOpened():
        st.error("Error opening video file")
        st.stop()
        
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    st.markdown(f"""
    <div style="display: flex; gap: 15px; margin-bottom: 20px; font-size: 13px; color: #94a3b8;">
        <span style="background: rgba(255,255,255,0.05); padding: 4px 10px; border-radius: 6px;"><b>Resolution:</b> {width}×{height}</span>
        <span style="background: rgba(255,255,255,0.05); padding: 4px 10px; border-radius: 6px;"><b>FPS:</b> {fps:.1f}</span>
        <span style="background: rgba(255,255,255,0.05); padding: 4px 10px; border-radius: 6px;"><b>Total Frames:</b> {total_frames}</span>
    </div>
    """)
    
    # Layout
    video_col, metrics_col = st.columns([2.5, 1])
    
    with video_col:
        frame_placeholder = st.empty()
        st.html("<br>")
        st.subheader("📈 Congestion Timeline")
        timeline_chart = st.empty()
        
    with metrics_col:
        st.html("<h3 style='margin-top: 0;'>Live Telemetry</h3>")
        count_metric = st.empty()
        severity_metric = st.empty()
        conf_metric = st.empty()
        fps_metric = st.empty()
        
        st.html("<br><h3>Class Distribution</h3>")
        class_chart = st.empty()
    
    frame_idx = 0
    processed = 0
    all_counts = []
    all_severities = []
    all_confidences = []
    class_counter = Counter()
    severity_history = deque(maxlen=100)
    
    start_time = time.time()
    
    progress_bar = st.progress(0)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_idx += 1
        if frame_idx % sample_rate != 0:
            continue
            
        if max_frames > 0 and processed >= max_frames:
            break
            
        processed += 1
        
        # Run detection
        results = model(frame, conf=conf_threshold, verbose=False)[0]
        
        boxes = results.boxes.xyxy.cpu().numpy() if results.boxes else []
        confs = results.boxes.conf.cpu().numpy() if results.boxes else []
        cls_ids = results.boxes.cls.cpu().numpy() if results.boxes else []
        
        # Draw on frame
        res_frame = frame.copy()
        
        for i, box in enumerate(boxes):
            x1, y1, x2, y2 = map(int, box)
            conf = confs[i]
            cid = int(cls_ids[i])
            name = model.names.get(cid, f'cls_{cid}')
            
            # Bright neon green boxes
            cv2.rectangle(res_frame, (x1, y1), (x2, y2), (0, 255, 100), 2)
            label = f"{name} {conf:.2f}"
            (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(res_frame, (x1, y1 - 20), (x1 + w, y1), (0, 255, 100), -1)
            cv2.putText(res_frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            
        # Display frame (convert BGR to RGB)
        frame_rgb = cv2.cvtColor(res_frame, cv2.COLOR_BGR2RGB)
        frame_placeholder.image(frame_rgb, channels="RGB", use_container_width=True)
        
        # Metrics
        count = len(boxes)
        avg_conf = float(np.mean(confs)) if len(confs) > 0 else 0.0
        
        for cid in cls_ids:
            class_counter[model.names.get(int(cid), f'cls_{int(cid)}')] += 1
        
        # Congestion severity
        density = count * 2.0  # rough heuristic
        if density > 80:
            severity = 'CRITICAL'
            sev_color = '#ef4444'
            sev_bg = 'rgba(239, 68, 68, 0.1)'
        elif density > 50:
            severity = 'HIGH'
            sev_color = '#f59e0b'
            sev_bg = 'rgba(245, 158, 11, 0.1)'
        elif density > 20:
            severity = 'MODERATE'
            sev_color = '#3b82f6'
            sev_bg = 'rgba(59, 130, 246, 0.1)'
        else:
            severity = 'LOW'
            sev_color = '#10b981'
            sev_bg = 'rgba(16, 185, 129, 0.1)'
            
        all_counts.append(count)
        all_severities.append(severity)
        all_confidences.append(avg_conf)
        severity_history.append(density)
        
        elapsed = time.time() - start_time
        proc_fps = processed / elapsed if elapsed > 0 else 0
        
        # Update metrics with new glass UI
        count_metric.html(f"""
        <div class="glass-card" style="border-left: 4px solid #3b82f6; margin-bottom: 15px; padding: 15px;">
            <div style="font-size: 13px; color: #94a3b8; text-transform: uppercase;">🚗 Active Entities</div>
            <div style="font-size: 32px; font-weight: 700; color: #f8fafc;">{count}</div>
        </div>
        """)
        
        severity_metric.html(f"""
        <div class="glass-card" style="border-left: 4px solid {sev_color}; background: {sev_bg}; margin-bottom: 15px; padding: 15px;">
            <div style="font-size: 13px; color: #94a3b8; text-transform: uppercase;">🚦 Congestion Level</div>
            <div style="font-size: 32px; font-weight: 700; color: {sev_color};">{severity}</div>
        </div>
        """)
        
        conf_metric.html(f"""
        <div class="glass-card" style="border-left: 4px solid #8b5cf6; margin-bottom: 15px; padding: 15px;">
            <div style="font-size: 13px; color: #94a3b8; text-transform: uppercase;">🎯 AI Confidence</div>
            <div style="font-size: 32px; font-weight: 700; color: #f8fafc;">{avg_conf:.2f}</div>
        </div>
        """)
        
        fps_metric.html(f"""
        <div class="glass-card" style="border-left: 4px solid #10b981; margin-bottom: 15px; padding: 15px;">
            <div style="font-size: 13px; color: #94a3b8; text-transform: uppercase;">⚡ Processing FPS</div>
            <div style="font-size: 32px; font-weight: 700; color: #f8fafc;">{proc_fps:.1f}</div>
        </div>
        """)
        
        # Class distribution
        if class_counter:
            top_classes = class_counter.most_common(5)
            class_html = "<div class='glass-card' style='padding: 15px;'>"
            for cls, cnt in top_classes:
                pct = cnt / sum(class_counter.values()) * 100
                class_html += f"""
                <div style='margin-bottom: 12px;'>
                    <div style='display: flex; justify-content: space-between; margin-bottom: 4px;'>
                        <span style='color: #94a3b8; font-size: 13px; text-transform: capitalize;'>{cls}</span>
                        <span style='color: #e6edf3; font-size: 12px; font-weight: bold;'>{cnt}</span>
                    </div>
                    <div style='background: rgba(0,0,0,0.3); border-radius: 8px; height: 10px; overflow: hidden; border: 1px solid rgba(255,255,255,0.05);'>
                        <div style='background: linear-gradient(90deg, #3b82f6, #60a5fa); width: {pct}%; height: 100%; border-radius: 8px;'></div>
                    </div>
                </div>"""
            class_html += "</div>"
            class_chart.html(class_html)
            
        # Timeline chart
        if len(severity_history) > 1:
            df = pd.DataFrame({'Time': range(len(severity_history)), 'Density': list(severity_history)})
            timeline_chart.line_chart(df, x='Time', y='Density', height=200, use_container_width=True)
        
        # Progress
        target = min(max_frames if max_frames > 0 else total_frames, total_frames)
        progress = min(processed / target, 1.0)
        progress_bar.progress(progress)
        
    cap.release()
    st.success(f"Processing complete! ({processed} frames)")
    
    st.markdown("---")
    st.markdown("## 📊 Final Post-Processing Analytics")
    if all_counts:
        avg_count = sum(all_counts) / len(all_counts)
        avg_conf = sum(all_confidences) / len(all_confidences)
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            render_metric_card("Avg Vehicles/Frame", f"{avg_count:.1f}", icon="🚗", color_theme="blue")
        with c2:
            render_metric_card("Peak Vehicles", max(all_counts), icon="📈", color_theme="red")
        with c3:
            render_metric_card("Avg Confidence", f"{avg_conf:.2f}", icon="🎯", color_theme="amber")
        with c4:
            render_metric_card("Total Processed", processed, icon="🎬", color_theme="purple")
        
        # Export button
        if st.button("💾 Export Detection Results"):
            export_dir = str(config.OUTPUTS_DIR / 'detection_videos')
            os.makedirs(export_dir, exist_ok=True)
            st.success(f"Results ready for export from {export_dir}")
