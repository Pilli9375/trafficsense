"""
TrafficSense Perception Adapter for CoLLMLight
Non-invasive wrapper to inject YOLOv8 perception states.
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional


class CoLLMLightPerceptionAdapter:
    """
    Adapter that replaces simulator state with perception state.
    
    Usage:
        adapter = CoLLMLightPerceptionAdapter(perception_json_path)
        # In CoLLMLight agent loop:
        # Instead of: state = env.get_state()
        # Use:        state = adapter.get_state(intersection_id, fallback_state)
    """
    
    def __init__(self, perception_source: Optional[str] = None):
        """
        Args:
            perception_source: Path to perception_states.json OR 'live' for real-time
        """
        self.perception_source = perception_source
        self.perception_data = None
        self.current_frame = 0
        
        if perception_source and os.path.exists(perception_source):
            with open(perception_source, 'r') as f:
                self.perception_data = json.load(f)
            print(f"[Adapter] Loaded {len(self.perception_data)} perception frames from {perception_source}")
    
    def get_state(self, intersection_id: str, fallback_state: Dict) -> Dict:
        """
        Get state for an intersection.
        
        If perception data is available, inject it.
        Otherwise, return the fallback state (original simulator state).
        
        Args:
            intersection_id: e.g., 'I0', 'I1'
            fallback_state: original CoLLMLight state dict
        
        Returns:
            State dict with perception data merged in
        """
        if self.perception_data is None:
            return fallback_state
        
        # Cycle through perception frames (loop if needed)
        if self.current_frame >= len(self.perception_data):
            self.current_frame = 0
        
        perc_frame = self.perception_data[self.current_frame]
        analysis = perc_frame.get('analysis', {})
        
        # Build TrafficSense-enhanced state
        enhanced_state = dict(fallback_state)  # copy original
        
        # Override with perception data where available
        total_vehicles = analysis.get('vehicle_count', 0)
        density = analysis.get('density_veh_per_100m', 0.0)
        severity = analysis.get('congestion_severity', 'none')
        class_dist = analysis.get('class_distribution', {})
        
        # Map to CoLLMLight fields
        lane_count = len(fallback_state.get('n_queue', [0, 0, 0, 0]))
        
        queued = int(total_vehicles * 0.6)
        moving = total_vehicles - queued
        
        def distribute(n, lanes):
            if n == 0:
                return [0] * lanes
            base = n // lanes
            rem = n % lanes
            dist = [base] * lanes
            for i in range(rem):
                dist[i] += 1
            return dist
        
        enhanced_state['n_queue'] = distribute(queued, lane_count)
        enhanced_state['n_move'] = distribute(moving, lane_count)
        enhanced_state['occupancy'] = min(density / 100.0, 1.0) if density > 0 else 0.0
        
        # Severity-based tau (wait time)
        tau_map = {'none': 0, 'low': 5, 'moderate': 15, 'high': 35, 'critical': 60}
        enhanced_state['tau'] = tau_map.get(severity, 0.0)
        
        # Queue pressure
        if moving > 0:
            enhanced_state['rho'] = round(queued / moving * 10.0, 2)
        else:
            enhanced_state['rho'] = round(queued * 5.0, 2)
        
        # TrafficSense extensions (preserved for downstream use)
        enhanced_state['vehicle_mix'] = class_dist
        enhanced_state['congestion_level'] = severity
        enhanced_state['density_veh_per_100m'] = density
        enhanced_state['source'] = 'TrafficSense_Perception'
        enhanced_state['perception_frame'] = self.current_frame
        
        self.current_frame += 1
        return enhanced_state
    
    def reset(self):
        """Reset to first perception frame."""
        self.current_frame = 0


class PerceptionStateGenerator:
    """
    Generates synthetic perception states for testing when no real video is available.
    Creates a JSON file compatible with the adapter.
    """
    
    @staticmethod
    def generate_for_network(network_size: tuple, num_frames: int, output_path: str):
        """
        Generate fake perception states for a grid network.
        
        Args:
            network_size: (rows, cols) e.g., (2, 2)
            num_frames: number of frames to generate
            output_path: where to save JSON
        """
        rows, cols = network_size
        num_intersections = rows * cols
        
        frames = []
        for f in range(num_frames):
            # Simulate varying congestion
            congestion_cycle = (f // 50) % 4  # 0=low, 1=mod, 2=high, 3=critical
            
            severities = ['low', 'moderate', 'high', 'critical']
            severity = severities[congestion_cycle]
            
            base_count = [8, 20, 35, 55][congestion_cycle]
            variation = (f % 10) - 5
            vehicle_count = max(0, base_count + variation)
            
            frame_state = {
                'timestamp': f'2026-08-26T14:{f//60:02d}:{f%60:02d}',
                'frame_idx': f,
                'analysis': {
                    'vehicle_count': vehicle_count,
                    'density_veh_per_100m': vehicle_count * 2.0,
                    'congestion_severity': severity,
                    'class_distribution': {
                        'car': int(vehicle_count * 0.4),
                        'autorickshaw': int(vehicle_count * 0.25),
                        'motorcycle': int(vehicle_count * 0.2),
                        'bus': int(vehicle_count * 0.1),
                        'truck': int(vehicle_count * 0.05)
                    },
                    'avg_confidence': 0.82,
                    'queue_estimate': int(vehicle_count * 0.6)
                }
            }
            frames.append(frame_state)
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(frames, f, indent=2)
        
        print(f"[Generator] Created {num_frames} synthetic perception frames for {num_intersections} intersections")
        print(f"[Generator] Saved to: {output_path}")
        return output_path


if __name__ == '__main__':
    # Demo: generate synthetic states
    gen = PerceptionStateGenerator()
    gen.generate_for_network((2, 2), 200, r'C:\Pilli\trafficsense\outputs\synthetic_perception.json')
    
    # Demo: load and convert
    adapter = CoLLMLightPerceptionAdapter(r'C:\Pilli\trafficsense\outputs\synthetic_perception.json')
    
    sample_fallback = {
        'intersection_id': 'I0',
        'phase': 0,
        'n_queue': [0, 0, 0, 0],
        'n_move': [0, 0, 0, 0],
        'occupancy': 0.0,
        'tau': 0.0,
        'rho': 0.0
    }
    
    state = adapter.get_state('I0', sample_fallback)
    print("\n--- Converted State ---")
    print(json.dumps(state, indent=2))
