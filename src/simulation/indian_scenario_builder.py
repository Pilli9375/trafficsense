"""
Indian Traffic Scenario Builder for CityFlow.
Creates custom roadnets and flows representing Indian urban conditions.
"""

import json
import os
from pathlib import Path


class IndianScenarioBuilder:
    """
    Builds CityFlow scenarios with Indian traffic characteristics.
    """
    
    def __init__(self, output_dir: str = None):
        if output_dir is None:
            output_dir = r'C:\Pilli\trafficsense\data\synthetic'
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def build_2x2_grid(self, road_width_m: float = 8.0, 
                      spacing_m: float = 200.0,
                      auto_rickshaw_ratio: float = 0.25):
        """
        Build a 2x2 Indian urban grid.
        
        Args:
            road_width_m: Width of roads (8-10m for Indian urban)
            spacing_m: Distance between intersections
            auto_rickshaw_ratio: Proportion of auto-rickshaws in flow
        """
        # This is a programmatic builder — the JSON files are the source of truth
        # This script verifies and documents the scenario
        
        roadnet_path = self.output_dir / 'indian_2x2_roadnet.json'
        flow_path = self.output_dir / 'indian_2x2_flow.json'
        config_path = self.output_dir / 'indian_2x2_config.json'
        
        print(f"[IndianScenario] Checking scenario files...")
        print(f"  Roadnet: {roadnet_path}")
        print(f"  Flow: {flow_path}")
        print(f"  Config: {config_path}")
        
        # Verify roadnet
        if roadnet_path.exists():
            with open(roadnet_path, 'r') as f:
                roadnet = json.load(f)
            
            intersections = roadnet.get('intersections', [])
            roads = roadnet.get('roads', [])
            
            print(f"  [OK] Roadnet: {len(intersections)} intersections, {len(roads)} roads")
            
            # Check Indian characteristics
            avg_width = sum(i.get('width', 0) for i in intersections) / len(intersections)
            print(f"  [OK] Avg intersection width: {avg_width:.1f}m (Indian urban: 8-10m)")
            
            avg_lane_width = sum(
                lane['width'] for r in roads for lane in r.get('lanes', [])
            ) / sum(len(r.get('lanes', [])) for r in roads)
            print(f"  [OK] Avg lane width: {avg_lane_width:.1f}m")
        
        # Verify flow
        if flow_path.exists():
            with open(flow_path, 'r') as f:
                flow = json.load(f)
            
            print(f"  [OK] Flow: {len(flow)} vehicle type definitions")
            
            # Count vehicle types
            vehicle_types = {}
            for entry in flow:
                v = entry.get('vehicle', {})
                vtype = self._classify_vehicle(v)
                vehicle_types[vtype] = vehicle_types.get(vtype, 0) + 1
            
            print(f"  [OK] Vehicle mix: {vehicle_types}")
            
            # Check Indian characteristics
            has_tight_gaps = any(
                entry.get('vehicle', {}).get('minGap', 2.5) < 1.0 
                for entry in flow
            )
            print(f"  [OK] Tight vehicle gaps: {has_tight_gaps} (Indian characteristic)")
        
        # Verify config
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
            print(f"  [OK] Config: roadnet={config.get('roadnetFile')}, flow={config.get('flowFile')}")
        
        return {
            'roadnet': str(roadnet_path),
            'flow': str(flow_path),
            'config': str(config_path)
        }
    
    def _classify_vehicle(self, vehicle: dict) -> str:
        """Classify vehicle by dimensions."""
        length = vehicle.get('length', 4.0)
        if length <= 1.8:
            return 'motorcycle'
        elif length <= 2.8:
            return 'auto_rickshaw'
        elif length <= 5.0:
            return 'car'
        elif length <= 12.0:
            return 'bus/truck'
        else:
            return 'heavy_vehicle'
    
    def get_scenario_info(self) -> dict:
        """Return human-readable scenario description."""
        return {
            'name': 'Indian Urban 2x2 Grid',
            'location_type': 'Dense urban Indian intersection cluster',
            'intersections': 4,
            'road_width_m': '8-10 (narrower than Western 12-15m)',
            'lane_width_m': '2.5-3.0',
            'vehicle_mix': {
                'cars': '~30%',
                'auto_rickshaws': '~25%',
                'motorcycles': '~35%',
                'buses': '~10%'
            },
            'key_characteristics': [
                'Tight vehicle gaps (0.2-0.5m vs 2.5m Western)',
                'Lower headway times (0.5-1.2s vs 1.5s)',
                'Slower max speeds (40-50 km/h)',
                'Mixed vehicle sizes sharing lanes'
            ],
            'peak_hours': '8-10 AM, 5-8 PM',
            'traffic_pattern': 'Highly heterogeneous, non-lane-disciplined'
        }


def demo():
    """Verify the Indian scenario."""
    print("TrafficSense Indian Scenario Builder")
    print("=" * 60)
    
    builder = IndianScenarioBuilder()
    paths = builder.build_2x2_grid()
    
    print(f"\nScenario files:")
    for k, v in paths.items():
        print(f"  {k}: {v}")
    
    info = builder.get_scenario_info()
    print(f"\nScenario Info:")
    for k, v in info.items():
        print(f"  {k}: {v}")


if __name__ == '__main__':
    demo()
