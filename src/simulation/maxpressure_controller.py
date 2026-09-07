"""
MaxPressure Traffic Signal Controller
Standard RL baseline for traffic signal control.
"""

import json
import os
from typing import Dict, List


class MaxPressureController:
    """
    MaxPressure controller for CityFlow.
    
    Pressure for a phase = sum over all green lanes of (upstream_queue - downstream_queue)
    Select phase with maximum pressure.
    """
    
    def __init__(self, decision_interval=10, min_green=5):
        """
        Args:
            decision_interval: make decisions every N steps
            min_green: minimum green time before switching
        """
        self.decision_interval = decision_interval
        self.min_green = min_green
        self.current_phase = {}
        self.phase_duration = {}
        
        # Phase definitions for standard 4-way intersection
        # Phase 0: N/S through (lanes 0, 2)
        # Phase 1: N/S left (lanes 0, 2 left)
        # Phase 2: E/W through (lanes 1, 3)
        # Phase 3: E/W left (lanes 1, 3 left)
        # For simplicity, we use 2-phase: NS (0) and EW (2)
        self.phase_lanes = {
            0: [0, 2],  # N/S through
            1: [1, 3],  # E/W through
        }
        
    def reset(self):
        self.current_phase = {}
        self.phase_duration = {}
    
    def calculate_pressure(self, state: Dict, phase: int) -> float:
        """
        Calculate pressure for a given phase.
        
        Simplified: pressure = sum of queued vehicles in lanes that would be green
        """
        n_queue = state.get('n_queue', [0, 0, 0, 0])
        n_move = state.get('n_move', [0, 0, 0, 0])
        
        lanes = self.phase_lanes.get(phase, [0, 2])
        
        pressure = 0
        for lane_idx in lanes:
            if lane_idx < len(n_queue):
                # Pressure = queued vehicles - moving vehicles (simplified)
                # Higher queue = higher pressure = more need for green
                upstream = n_queue[lane_idx]
                downstream = n_move[lane_idx]  # proxy for downstream capacity
                pressure += (upstream - downstream)
        
        return pressure
    
    def decide(self, step: int, intersection_id: str, state: Dict, *args, **kwargs) -> int:
        """
        Make signal decision using MaxPressure.
        
        Returns: phase_id (0 or 1 for NS/EW)
        """
        # Initialize
        if intersection_id not in self.current_phase:
            self.current_phase[intersection_id] = 0
            self.phase_duration[intersection_id] = 0
        
        current = self.current_phase[intersection_id]
        duration = self.phase_duration.get(intersection_id, 0)
        
        # Only decide at intervals
        if step % self.decision_interval != 0:
            self.phase_duration[intersection_id] = duration + 1
            return current
        
        # Calculate pressure for each phase
        pressures = {}
        for phase in self.phase_lanes.keys():
            pressures[phase] = self.calculate_pressure(state, phase)
        
        # Find phase with max pressure
        best_phase = max(pressures, key=pressures.get)
        
        # Apply minimum green constraint
        if best_phase != current and duration < self.min_green:
            best_phase = current  # can't switch yet
        
        # Update tracking
        if best_phase == current:
            self.phase_duration[intersection_id] = duration + 1
        else:
            self.phase_duration[intersection_id] = 0
        
        self.current_phase[intersection_id] = best_phase
        
        return best_phase
    
    def get_action(self, step, intersection_id, state):
        """Alias for decide()."""
        return self.decide(step, intersection_id, state)


def demo_maxpressure():
    """Demo MaxPressure with sample states."""
    controller = MaxPressureController(decision_interval=10)
    
    test_states = [
        {'n_queue': [10, 2, 8, 1], 'n_move': [2, 5, 1, 4]},  # High NS queue
        {'n_queue': [3, 12, 2, 9], 'n_move': [4, 1, 5, 2]},   # High EW queue
        {'n_queue': [5, 5, 5, 5], 'n_move': [2, 2, 2, 2]},   # Balanced
    ]
    
    print("MaxPressure Controller Demo")
    print("=" * 50)
    
    for i, state in enumerate(test_states):
        phase = controller.decide(i * 10, 'I0', state)
        pressure_ns = controller.calculate_pressure(state, 0)
        pressure_ew = controller.calculate_pressure(state, 1)
        print(f"\nState {i+1}: queue={state['n_queue']}")
        print(f"  NS Pressure: {pressure_ns:.1f}")
        print(f"  EW Pressure: {pressure_ew:.1f}")
        print(f"  Selected Phase: {phase} ({'N/S' if phase == 0 else 'E/W'})")


if __name__ == '__main__':
    demo_maxpressure()
