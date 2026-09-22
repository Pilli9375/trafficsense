"""
360-step MaxPressure simulation.
"""

import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src import config
sys.path.insert(0, str(config.SRC_DIR / 'simulation'))

from run_proper_sim import ProperCityFlowEnv, run_simulation
from maxpressure_controller import MaxPressureController

def main():
    print("TrafficSense MaxPressure Baseline Simulation")
    print("=" * 60)
    
    # Config path
    config_path = str(config.INDIAN_CONFIG)
    
    if not os.path.exists(config_path):
        print(f"Error: {config_path} not found.")
    
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
