"""
ByteTrack-based multi-object tracker wrapper.
"""
from ultralytics import YOLO
import numpy as np
from collections import defaultdict

class VehicleTracker:
    def __init__(self, model_path, conf_threshold=0.3, iou_threshold=0.5):
        self.model = YOLO(model_path)
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.track_history = defaultdict(list)  # track_id -> list of (x, y, frame)
        
    def detect_and_track(self, frame, frame_idx):
        """
        Run detection + tracking on a single frame.
        Returns: list of track dicts with keys:
            track_id, bbox (x1,y1,x2,y2), class_id, class_name, conf, center (cx,cy)
        """
        results = self.model.track(
            frame,
            persist=True,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            verbose=False
        )
        
        tracks = []
        if results[0].boxes is not None and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id.cpu().numpy().astype(int)
            class_ids = results[0].boxes.cls.cpu().numpy().astype(int)
            confs = results[0].boxes.conf.cpu().numpy()
            names = self.model.names
            
            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = box
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                track_id = int(track_ids[i])
                cls_id = int(class_ids[i])
                conf = float(confs[i])
                
                self.track_history[track_id].append((cx, cy, frame_idx))
                
                tracks.append({
                    'track_id': int(track_id),
                    'bbox': (float(x1), float(y1), float(x2), float(y2)),
                    'class_id': int(cls_id),
                    'class_name': names.get(cls_id, f'class_{cls_id}'),
                    'confidence': round(float(conf), 3),
                    'center': (round(float(cx), 1), round(float(cy), 1)),
                    'frame_idx': int(frame_idx)
                })
        
        return tracks
    
    def get_active_tracks(self, current_frame_idx, max_age=30):
        """Return tracks that have been seen recently."""
        active = []
        for tid, history in self.track_history.items():
            if history and (current_frame_idx - history[-1][2]) <= max_age:
                active.append(tid)
        return active
