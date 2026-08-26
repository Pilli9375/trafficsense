"""
Congestion density and severity analysis for Indian traffic.
"""
from collections import Counter

class CongestionAnalyzer:
    def __init__(self, road_length_m=100, lane_count=2):
        self.road_length_m = road_length_m
        self.lane_count = lane_count
        
    def analyze(self, tracks, frame_shape):
        """
        Analyze congestion from current frame tracks.
        Returns dict with density, severity, vehicle mix, estimates.
        """
        if not tracks:
            return {
                'vehicle_count': 0,
                'density_veh_per_100m': 0.0,
                'congestion_severity': 'none',
                'class_distribution': {},
                'avg_confidence': 0.0,
                'queue_estimate': 0
            }
        
        # Counts
        total = len(tracks)
        class_dist = Counter(t['class_name'] for t in tracks)
        
        # Density: vehicles per 100m (approximate)
        # Assumes road occupies ~60% of frame width
        effective_length = self.road_length_m
        density = (total / effective_length) * 100
        
        # Average confidence
        avg_conf = sum(t['confidence'] for t in tracks) / total
        
        # Congestion severity — Indian urban calibrated
        severity = self._classify_severity(total, density, class_dist)
        
        # Queue estimate: vehicles that are nearly stationary (tracked for >10 frames)
        # Simplified: count all vehicles as potential queue (conservative)
        queue_est = total
        
        return {
            'vehicle_count': total,
            'density_veh_per_100m': round(density, 2),
            'congestion_severity': severity,
            'class_distribution': dict(class_dist),
            'avg_confidence': round(avg_conf, 3),
            'queue_estimate': queue_est
        }
    
    def _classify_severity(self, count, density, class_dist):
        """Indian-specific congestion classification."""
        auto_count = class_dist.get('autorickshaw', 0) + class_dist.get('auto', 0)
        bike_count = class_dist.get('motorcycle', 0) + class_dist.get('bicycle', 0)
        
        # Critical: extreme density or many slow vehicles
        if density > 80 or (auto_count > 15 and density > 50):
            return 'critical'
        if density > 50 or count > 40:
            return 'high'
        if density > 25 or count > 20:
            return 'moderate'
        if density > 10 or count > 5:
            return 'low'
        return 'none'
