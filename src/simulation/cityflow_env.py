"""
Simple CityFlow environment wrapper for TrafficSense.
"""
import json
import os
from typing import Dict, List


class CityFlowEnv:
    """
    Wrapper around CityFlow Engine for easy state extraction and action application.
    """
    
    def __init__(self, config_path: str):
        try:
            import cityflow
            self.engine = cityflow.Engine(config_path, thread_num=1)
            self.cityflow = cityflow
            self.has_cityflow = True
        except ImportError:
            print("[WARN] CityFlow not available — running in mock mode")
            self.engine = None
            self.has_cityflow = False
        
        self.config_path = config_path
        self.current_step = 0
        self.intersection_ids = []
        self._load_intersections()
        
    def _load_intersections(self):
        """Extract intersection IDs from roadnet."""
        if not self.has_cityflow:
            # Mock mode: assume 4 intersections
            self.intersection_ids = ['I0', 'I1', 'I2', 'I3']
            return
            
        # Parse roadnet JSON to get intersection IDs
        import os
        config_dir = os.path.dirname(self.config_path)
        with open(self.config_path, 'r') as f:
            config = json.load(f)
        
        roadnet_path = os.path.join(config_dir, config.get('roadnetFile', ''))
        if os.path.exists(roadnet_path):
            with open(roadnet_path, 'r') as f:
                roadnet = json.load(f)
            self.intersection_ids = [
                node['id'] for node in roadnet.get('intersections', [])
                if node.get('trafficLight', None) is not None
            ]
        else:
            self.intersection_ids = ['I0', 'I1', 'I2', 'I3']
    
    def reset(self):
        """Reset simulation."""
        if self.has_cityflow:
            self.engine.reset()
        self.current_step = 0
    
    def step(self):
        """Advance simulation by one step."""
        if self.has_cityflow:
            self.engine.next_step()
        self.current_step += 1
    
    def get_state(self, intersection_id: str) -> Dict:
        """
        Get traffic state for an intersection.
        Returns dict with n_queue, n_move, occupancy, etc.
        """
        if not self.has_cityflow:
            # Mock state for testing
            import random
            return {
                'intersection_id': intersection_id,
                'phase': 0,
                'n_queue': [random.randint(0, 10) for _ in range(4)],
                'n_move': [random.randint(0, 5) for _ in range(4)],
                'occupancy': random.random(),
                'tau': random.random() * 30,
                'rho': random.random() * 10
            }
        
        # Real CityFlow state extraction
        # CityFlow API: get_lane_vehicle_count(), get_lane_waiting_vehicle_count()
        # We approximate n_queue and n_move from lane data
        
        # Get all lane vehicle counts
        lane_vehicles = self.engine.get_lane_vehicle_count()
        lane_waiting = self.engine.get_lane_waiting_vehicle_count()
        
        # For simplicity, aggregate across all lanes connected to this intersection
        # In a real implementation, you'd map lanes to intersection approaches
        total_vehicles = sum(lane_vehicles.values()) if lane_vehicles else 0
        total_waiting = sum(lane_waiting.values()) if lane_waiting else 0
        total_moving = max(0, total_vehicles - total_waiting)
        
        # Distribute across 4 approaches
        def distribute(n):
            if n == 0:
                return [0, 0, 0, 0]
            base = n // 4
            rem = n % 4
            d = [base] * 4
            for i in range(rem):
                d[i] += 1
            return d
        
        occupancy = min(total_vehicles / 50.0, 1.0) if total_vehicles > 0 else 0.0
        
        return {
            'intersection_id': intersection_id,
            'phase': 0,  # Will be tracked externally
            'n_queue': distribute(total_waiting),
            'n_move': distribute(total_moving),
            'occupancy': round(occupancy, 3),
            'tau': round(total_waiting * 2.5, 1),  # heuristic: 2.5s per queued vehicle
            'rho': round(total_waiting * 1.5, 2)
        }
    
    def set_phase(self, intersection_id: str, phase_id: int):
        """Set traffic light phase."""
        if self.has_cityflow:
            self.engine.set_tl_phase(intersection_id, phase_id)
    
    def get_current_time(self) -> int:
        """Get current simulation time."""
        return self.current_step
    
    def get_score(self) -> Dict:
        """Get simulation performance metrics."""
        if not self.has_cityflow:
            return {'average_travel_time': 0, 'total_vehicle': 0}
        
        # CityFlow doesn't have a direct get_score, we compute from vehicle data
        return {
            'total_vehicle': len(self.engine.get_vehicles()),
            'current_time': self.current_step
        }


if __name__ == '__main__':
    # Test with mock mode
    env = CityFlowEnv('dummy_config.json')
    print("CityFlowEnv initialized")
    print(f"Intersections: {env.intersection_ids}")
    state = env.get_state('I0')
    print(f"Sample state: {state}")
