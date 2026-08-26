"""
TrafficSense Perception Pipeline
Processes video → detects → tracks → analyzes → exports state JSON
"""
import cv2
import json
import os
import time
from datetime import datetime
from pathlib import Path

from tracker import VehicleTracker
from congestion_analyzer import CongestionAnalyzer


class TrafficSensePerception:
    def __init__(self, model_path, output_dir, road_length_m=100, lane_count=2):
        self.tracker = VehicleTracker(model_path)
        self.analyzer = CongestionAnalyzer(road_length_m, lane_count)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.states = []  # accumulated frame states
        self.frame_count = 0
        
    def process_video(self, video_path, sample_every_n_frames=1, max_frames=None):
        """
        Process entire video and export states.
        
        Args:
            video_path: path to input video
            sample_every_n_frames: process every Nth frame (1 = all frames)
            max_frames: stop after N frames (None = process all)
        """
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f"Video: {video_path}")
        print(f"  Resolution: {width}x{height}, FPS: {fps}, Total frames: {total_frames}")
        
        # Setup output video writer (with bounding boxes)
        out_video_path = self.output_dir / 'detected_output.mp4'
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_writer = cv2.VideoWriter(str(out_video_path), fourcc, fps, (width, height))
        
        start_time = time.time()
        frame_idx = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_idx += 1
            
            # Skip frames if sampling
            if frame_idx % sample_every_n_frames != 0:
                continue
            
            # Process frame
            tracks = self.tracker.detect_and_track(frame, frame_idx)
            analysis = self.analyzer.analyze(tracks, (height, width))
            
            # Build state
            state = {
                'timestamp': datetime.now().isoformat(),
                'frame_idx': frame_idx,
                'video_path': str(video_path),
                'analysis': analysis,
                'tracks': tracks  # optional: can be large
            }
            self.states.append(state)
            
            # Draw on frame
            annotated = self._draw_tracks(frame, tracks, analysis)
            out_writer.write(annotated)
            
            self.frame_count += 1
            
            # Progress
            if self.frame_count % 30 == 0:
                elapsed = time.time() - start_time
                fps_proc = self.frame_count / elapsed
                print(f"  Processed {self.frame_count} frames @ {fps_proc:.1f} FPS")
            
            if max_frames and self.frame_count >= max_frames:
                break
        
        cap.release()
        out_writer.release()
        
        total_time = time.time() - start_time
        print(f"\nPipeline complete:")
        print(f"  Frames processed: {self.frame_count}")
        print(f"  Time: {total_time:.1f}s")
        print(f"  Avg FPS: {self.frame_count/total_time:.1f}")
        print(f"  Output video: {out_video_path}")
        
        # Export states
        self._export_states()
        
        return self.states
    
    def _draw_tracks(self, frame, tracks, analysis):
        """Draw bounding boxes and info on frame."""
        for t in tracks:
            x1, y1, x2, y2 = map(int, t['bbox'])
            cls_name = t['class_name']
            tid = t['track_id']
            conf = t['confidence']
            
            color = (0, 255, 0)  # green
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = f"{cls_name} #{tid} {conf:.2f}"
            cv2.putText(frame, label, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Draw congestion info
        severity = analysis['congestion_severity']
        count = analysis['vehicle_count']
        density = analysis['density_veh_per_100m']
        
        color_map = {
            'none': (0, 255, 0),
            'low': (0, 255, 255),
            'moderate': (0, 165, 255),
            'high': (0, 0, 255),
            'critical': (0, 0, 139)
        }
        sev_color = color_map.get(severity, (255, 255, 255))
        
        info_text = f"Count: {count} | Density: {density:.1f}/100m | Severity: {severity.upper()}"
        cv2.putText(frame, info_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, sev_color, 2)
        
        return frame
    
    def _export_states(self):
        """Export accumulated states to JSON."""
        json_path = self.output_dir / 'perception_states.json'
        with open(json_path, 'w') as f:
            json.dump(self.states, f, indent=2)
        print(f"  States JSON: {json_path}")
        
        # Also export summary CSV
        import csv
        csv_path = self.output_dir / 'perception_summary.csv'
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'frame_idx', 'vehicle_count', 'density_veh_per_100m',
                'congestion_severity', 'avg_confidence', 'queue_estimate'
            ])
            writer.writeheader()
            for s in self.states:
                a = s['analysis']
                writer.writerow({
                    'frame_idx': s['frame_idx'],
                    'vehicle_count': a['vehicle_count'],
                    'density_veh_per_100m': a['density_veh_per_100m'],
                    'congestion_severity': a['congestion_severity'],
                    'avg_confidence': a['avg_confidence'],
                    'queue_estimate': a['queue_estimate']
                })
        print(f"  Summary CSV: {csv_path}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--video', required=True, help='Input video path')
    parser.add_argument('--model', default=r'C:\Pilli\trafficsense\models\yolo\best.pt')
    parser.add_argument('--output', default=r'C:\Pilli\trafficsense\outputs\perception_demo')
    parser.add_argument('--sample', type=int, default=1, help='Process every Nth frame')
    parser.add_argument('--max-frames', type=int, default=None)
    args = parser.parse_args()
    
    pipeline = TrafficSensePerception(args.model, args.output)
    pipeline.process_video(args.video, args.sample, args.max_frames)
