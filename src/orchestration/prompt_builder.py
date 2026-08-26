"""
CoLLMLight-style prompt builder with Indian traffic context.
"""
import json
from typing import Dict, List


INDIAN_TRAFFIC_CONTEXT = """You are a cooperative traffic signal controller managing intersections in an Indian urban area.

TRAFFIC CHARACTERISTICS:
- Mixed vehicle types: cars, motorcycles, auto-rickshaws, buses, trucks, bicycles, pushcarts
- Non-lane-disciplined movement is common
- Two-wheelers squeeze between larger vehicles
- Auto-rickshaws are slow to accelerate and block lanes
- Peak hours: 8-10 AM and 5-8 PM with extreme congestion
- Pedestrian crossings are frequent and unpredictable
- Honking and sudden lane changes are normal

YOUR ROLE:
Analyze the current traffic state at your intersection AND neighboring intersections.
Recommend the optimal signal phase and duration.
Consider cooperation with neighbors to prevent gridlock.

OUTPUT FORMAT (STRICT JSON):
{
    "recommended_phase": <integer 0-3>,
    "green_duration_seconds": <integer 15-60>,
    "reasoning": "<one sentence explanation>",
    "cooperation_needed": <true/false>,
    "neighbor_coordination": "<which neighbor and why, or 'none'>"
}
"""


class CoLLMLightPromptBuilder:
    def __init__(self):
        self.context = INDIAN_TRAFFIC_CONTEXT
    
    def build_sr_prompt(self, own_state: Dict, neighbor_states: List[Dict]) -> str:
        """
        Spatiotemporal Reasoning (SR) prompt.
        Analyzes own state + neighbors to produce cooperative suggestions.
        """
        prompt = self.context + "\n\n=== CURRENT STATE ===\n\n"
        prompt += f"YOUR INTERSECTION: {own_state.get('intersection_id', 'I0')}\n"
        prompt += f"Current Phase: {own_state.get('phase', 0)}\n"
        prompt += f"Queued Vehicles: {own_state.get('n_queue', [])}\n"
        prompt += f"Moving Vehicles: {own_state.get('n_move', [])}\n"
        prompt += f"Occupancy: {own_state.get('occupancy', 0):.2f}\n"
        prompt += f"Average Wait: {own_state.get('tau', 0):.1f}s\n"
        prompt += f"Queue Pressure: {own_state.get('rho', 0):.2f}\n"
        
        # TrafficSense extensions
        if 'vehicle_mix' in own_state:
            prompt += f"Vehicle Mix: {json.dumps(own_state['vehicle_mix'])}\n"
        if 'congestion_level' in own_state:
            prompt += f"Congestion: {own_state['congestion_level'].upper()}\n"
        
        prompt += "\n=== NEIGHBORING INTERSECTIONS ===\n"
        for i, neighbor in enumerate(neighbor_states):
            prompt += f"\nNeighbor {i+1} ({neighbor.get('intersection_id', 'N/A')}):\n"
            prompt += f"  Queued: {sum(neighbor.get('n_queue', []))} vehicles\n"
            prompt += f"  Occupancy: {neighbor.get('occupancy', 0):.2f}\n"
            prompt += f"  Congestion: {neighbor.get('congestion_level', 'unknown')}\n"
        
        prompt += "\nProvide your cooperative signal recommendation in the strict JSON format above."
        return prompt
    
    def build_rd_prompt(self, own_state: Dict, sr_suggestion: str) -> str:
        """
        Real-time Decision (RD) prompt.
        Uses SR suggestion to make final rapid decision.
        """
        prompt = self.context + "\n\n=== SPATIOTEMPORAL ANALYSIS ===\n"
        prompt += f"Cooperative suggestion: {sr_suggestion}\n\n"
        prompt += f"=== CURRENT STATE (Real-time) ===\n"
        prompt += f"Intersection: {own_state.get('intersection_id', 'I0')}\n"
        prompt += f"Queued: {sum(own_state.get('n_queue', []))} vehicles\n"
        prompt += f"Moving: {sum(own_state.get('n_move', []))} vehicles\n"
        prompt += f"Occupancy: {own_state.get('occupancy', 0):.2f}\n"
        prompt += "\nMake the FINAL signal decision NOW. Output strict JSON only."
        return prompt


if __name__ == '__main__':
    builder = CoLLMLightPromptBuilder()
    
    own = {
        'intersection_id': 'I0',
        'phase': 0,
        'n_queue': [12, 8, 5, 3],
        'n_move': [2, 1, 4, 0],
        'occupancy': 0.72,
        'tau': 25.0,
        'rho': 15.3,
        'vehicle_mix': {'car': 15, 'autorickshaw': 8, 'motorcycle': 5},
        'congestion_level': 'high'
    }
    
    neighbors = [
        {
            'intersection_id': 'I1',
            'n_queue': [3, 2, 1, 1],
            'n_move': [5, 4, 3, 2],
            'occupancy': 0.25,
            'congestion_level': 'low'
        }
    ]
    
    sr = builder.build_sr_prompt(own, neighbors)
    print("=== SR PROMPT (first 800 chars) ===")
    print(sr[:800] + "...")
    print(f"\nTotal prompt length: {len(sr)} chars")
