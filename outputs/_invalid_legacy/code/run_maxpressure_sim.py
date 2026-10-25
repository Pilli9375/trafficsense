"""
360-step MaxPressure simulation.
"""

import sys
sys.path.insert(0, '/mnt/c/Pilli/trafficsense/src/simulation')

from run_proper_sim import ProperCityFlowEnv, run_simulation
from maxpressure_controller import MaxPressureController
import os

def main():
    print("TrafficSense MaxPressure Baseline Simulation")
    print("=" * 60)
    
    # Config path
    config_path = '/home/pilli/trafficsense/CoLLMLight/data/Synthetic/4_4/config.json'
    
    if not os.path.exists(config_path):
        for root, dirs, files in os.walk('/home/pilli/trafficsense/CoLLMLight/data'):
            for f in files:
                if f == 'config.json':
                    config_path = os.path.join(root, f)
                    break
            if os.path.exists(config_path):
                break
    
    print(f"Using config: {config_path}")
    
    env = ProperCityFlowEnv(config_path)
    print(f"Intersections: {env.intersection_ids}")
    
    # Run MaxPressure
    mp = MaxPressureController(decision_interval=10, min_green=5)
    mp_metrics, mp_summary = run_simulation('MaxPressure', mp, env, total_steps=360)
    
    print("\nMaxPressure simulation complete!")
    print(f"Summary: {mp_summary}")

if __name__ == '__main__':
    main()
