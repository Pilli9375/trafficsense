"""
Simulator-Only Controller — TrafficSense without perception.
Uses raw simulator states with NO YOLO data injection.
"""

import sys
sys.path.insert(0, '/mnt/c/Pilli/trafficsense/src/orchestration')

from cooperative_reasoning import CooperativeReasoningEngine


class SimulatorOnlyController:
    """
    TrafficSense without perception adaptation.
    Uses raw CityFlow simulator states directly.
    """
    
    def __init__(self, decision_interval=30):
        self.engine = CooperativeReasoningEngine()
        self.decision_interval = decision_interval
        self.current_phases = {}
        self.decisions_log = []
        
    def decide(self, step, intersection_id, state, all_states):
        if step % self.decision_interval != 0:
            return self.current_phases.get(intersection_id, 0)
        
        # Use raw simulator state (no perception enhancement)
        # Add minimal TrafficSense extensions for compatibility
        raw_state = dict(state)
        raw_state['vehicle_mix'] = {}
        raw_state['congestion_level'] = 'unknown'
        raw_state['source'] = 'Simulator_Only'
        
        # Build neighbors from other states (also raw)
        neighbors = []
        for sid, s in all_states.items():
            if sid != intersection_id:
                ns = dict(s)
                ns['vehicle_mix'] = {}
                ns['congestion_level'] = 'unknown'
                neighbors.append(ns)
        
        try:
            decision = self.engine.decide(intersection_id, raw_state, neighbors)
            new_phase = decision.get('recommended_phase', 0)
            self.current_phases[intersection_id] = new_phase
            
            self.decisions_log.append({
                'step': step,
                'intersection_id': intersection_id,
                'decision': decision,
                'state': raw_state
            })
            
            return new_phase
            
        except Exception as e:
            print(f"[WARN] Simulator-only decision failed: {e}")
            return self.current_phases.get(intersection_id, 0)


if __name__ == '__main__':
    print("Simulator-Only Controller loaded successfully")
