"""
TrafficSense State Exporter
Converts perception analysis outputs to CoLLMLight-compatible states.
"""
import json
from pathlib import Path
from collections import defaultdict


class PerceptionToCoLLMLight:
    """
    Bridge: YOLOv8 perception → CoLLMLight observation
    """
    
    # Congestion severity to occupancy mapping
    SEVERITY_TO_OCCUPANCY = {
        'none': 0.05,
        'low': 0.20,
        'moderate': 0.45,
        'high': 0.70,
        'critical': 0.90
    }
    
    # Congestion severity to average wait time (seconds)
    SEVERITY_TO_TAU = {
        'none': 0.0,
        'low': 5.0,
        'moderate': 15.0,
        'high': 35.0,
        'critical': 60.0
    }
    
    def __init__(self, intersection_id, lane_count=4):
        self.intersection_id = intersection_id
        self.lane_count = lane_count
        
    def convert(self, perception_state, current_phase=0):
        """
        Convert a single perception state to CoLLMLight format.
        
        Args:
            perception_state: dict from inference_pipeline (analysis + tracks)
            current_phase: current signal phase index (0, 1, 2, ...)
        
        Returns:
            dict matching CoLLMLight observation format
        """
        analysis = perception_state.get('analysis', perception_state)
        
        total_vehicles = analysis.get('vehicle_count', 0)
        density = analysis.get('density_veh_per_100m', 0.0)
        severity = analysis.get('congestion_severity', 'none')
        class_dist = analysis.get('class_distribution', {})
        
        # Estimate n_queue and n_move per lane
        # Heuristic: 60% of vehicles are queued, 40% moving (varies by phase)
        # For simplicity, distribute evenly across lanes
        queued_total = int(total_vehicles * 0.6)
        moving_total = total_vehicles - queued_total
        
        n_queue = self._distribute_across_lanes(queued_total)
        n_move = self._distribute_across_lanes(moving_total)
        
        # Occupancy from density or severity fallback
        occupancy = self.SEVERITY_TO_OCCUPANCY.get(severity, 0.0)
        if density > 0:
            # Calibrate: 100 vehicles/100m ≈ 100% occupancy
            occupancy = min(density / 100.0, 1.0)
        
        # Average waiting time
        tau = self.SEVERITY_TO_TAU.get(severity, 0.0)
        
        # Queue pressure: heuristic based on queued vs moving ratio
        if moving_total > 0:
            rho = queued_total / moving_total * 10.0
        else:
            rho = queued_total * 5.0  # high pressure if nobody moving
        
        # Build CoLLMLight state
        collm_state = {
            'intersection_id': self.intersection_id,
            'phase': current_phase,
            'n_queue': n_queue,
            'n_move': n_move,
            'occupancy': round(occupancy, 3),
            'tau': round(tau, 1),
            'rho': round(rho, 2),
            # TrafficSense extensions
            'vehicle_mix': class_dist,
            'congestion_level': severity,
            'density_veh_per_100m': density,
            'total_vehicles': total_vehicles,
            'source': 'TrafficSense_YOLOv8'
        }
        
        return collm_state
    
    def _distribute_across_lanes(self, total):
        """Distribute total vehicles evenly across lanes."""
        if total == 0:
            return [0] * self.lane_count
        
        base = total // self.lane_count
        remainder = total % self.lane_count
        distribution = [base] * self.lane_count
        for i in range(remainder):
            distribution[i] += 1
        return distribution
    
    def convert_batch(self, perception_states, phase_sequence=None):
        """
        Convert a batch of perception states (e.g., one per intersection).
        
        Args:
            perception_states: list of dicts, one per intersection
            phase_sequence: list of current phases, one per intersection
        
        Returns:
            list of CoLLMLight states
        """
        if phase_sequence is None:
            phase_sequence = [0] * len(perception_states)
        
        return [
            self.convert(state, phase_sequence[i])
            for i, state in enumerate(perception_states)
        ]
    
    def save(self, collm_state, output_path):
        """Save state to JSON file."""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(collm_state, f, indent=2)
        return output_path


class CoLLMLightToPerception:
    """
    Reverse bridge: CoLLMLight decision → perception feedback
    (For future use: signal timing decisions fed back to dashboard)
    """
    
    def __init__(self):
        pass
    
    def convert(self, collm_action):
        """
        Convert CoLLMLight action to human-readable signal command.
        
        Args:
            collm_action: dict with 'phase', 'duration', 'reasoning'
        
        Returns:
            dict with signal command for dashboard
        """
        return {
            'signal_phase': collm_action.get('phase', 0),
            'green_duration_sec': collm_action.get('duration', 30),
            'agent_reasoning': collm_action.get('reasoning', ''),
            'timestamp': collm_action.get('timestamp', '')
        }


def demo():
    """Demonstrate the bridge with sample data."""
    print("=" * 60)
    print("TrafficSense State Exporter Demo")
    print("=" * 60)
    
    # Sample perception state (from YOLOv8 pipeline)
    sample_perception = {
        'analysis': {
            'vehicle_count': 24,
            'density_veh_per_100m': 48.0,
            'congestion_severity': 'moderate',
            'class_distribution': {
                'car': 10,
                'autorickshaw': 6,
                'motorcycle': 5,
                'bus': 2,
                'truck': 1
            },
            'avg_confidence': 0.82,
            'queue_estimate': 15
        },
        'frame_idx': 150,
        'timestamp': '2026-08-26T14:30:00'
    }
    
    # Convert
    exporter = PerceptionToCoLLMLight(intersection_id='I0', lane_count=4)
    state = exporter.convert(sample_perception, current_phase=0)
    
    print("\n--- Input: Perception State ---")
    print(json.dumps(sample_perception['analysis'], indent=2))
    
    print("\n--- Output: CoLLMLight State ---")
    print(json.dumps(state, indent=2))
    
    # Save sample
    output = r'C:\Pilli\trafficsense\outputs\perception_demo\collmlight_state.json'
    exporter.save(state, output)
    print(f"\nSaved to: {output}")
    
    # Batch demo
    print("\n--- Batch Conversion (4 intersections) ---")
    batch_perceptions = [sample_perception] * 4
    batch_states = exporter.convert_batch(batch_perceptions, phase_sequence=[0, 1, 0, 1])
    for s in batch_states:
        print(f"  {s['intersection_id']}: phase={s['phase']}, occupancy={s['occupancy']}, severity={s['congestion_level']}")


if __name__ == '__main__':
    demo()
