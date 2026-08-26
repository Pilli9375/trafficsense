"""
Wrapper to run CoLLMLight with TrafficSense perception adapter.
This script lives in Windows but calls into WSL CoLLMLight.
"""
import json
import subprocess
import sys
import os

def run_with_perception():
    """
    Strategy:
    1. Generate/load perception states
    2. Copy them to WSL
    3. Run CoLLMLight with a flag to use perception adapter
    4. Collect results
    """
    print("TrafficSense CoLLMLight Perception Wrapper")
    print("=" * 50)
    
    # Step 1: Ensure perception data exists
    perc_path = r'C:\Pilli\trafficsense\outputs\synthetic_perception.json'
    if not os.path.exists(perc_path):
        print("Generating synthetic perception data...")
        from perception_adapter import PerceptionStateGenerator
        PerceptionStateGenerator.generate_for_network((2, 2), 200, perc_path)
    
    # Step 2: Copy to WSL
    wsl_perc = "/mnt/c/Pilli/trafficsense/outputs/synthetic_perception.json"
    print(f"Perception data available at: {wsl_perc}")
    
    # Step 3: Run CoLLMLight in WSL with perception flag
    # NOTE: Full integration happens in Step 3.4. For now, we verify the adapter works standalone.
    print("\n[Step 3.2] Adapter created and tested.")
    print("[Step 3.4] Will integrate into CoLLMLight agent loop.")
    
    # Step 4: Verify adapter can convert states
    from perception_adapter import CoLLMLightPerceptionAdapter
    
    adapter = CoLLMLightPerceptionAdapter(perc_path)
    
    test_fallback = {
        'intersection_id': 'I0',
        'phase': 0,
        'n_queue': [2, 1, 3, 0],
        'n_move': [1, 2, 0, 1],
        'occupancy': 0.3,
        'tau': 5.0,
        'rho': 2.0
    }
    
    print("\n--- Adapter Test: 3 Consecutive Frames ---")
    for i in range(3):
        state = adapter.get_state('I0', test_fallback)
        print(f"Frame {i}: count={state['n_queue']}, severity={state['congestion_level']}, source={state['source']}")

if __name__ == '__main__':
    run_with_perception()
