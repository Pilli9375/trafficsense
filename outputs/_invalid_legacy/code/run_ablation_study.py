"""
Ablation Study Runner
Runs 4 configurations: FixedTime, MaxPressure, Isolated, Simulator-Only, Full
"""

import sys
sys.path.insert(0, '/mnt/c/Pilli/trafficsense/src/simulation')

from run_proper_sim import ProperCityFlowEnv, run_simulation
from maxpressure_controller import MaxPressureController
from isolated_controller import IsolatedController
from simulator_only_controller import SimulatorOnlyController
import os


def main():
    print("TrafficSense Ablation Study")
    print("=" * 70)
    print("Configurations:")
    print("  1. FixedTime (baseline)")
    print("  2. MaxPressure (RL baseline)")
    print("  3. Isolated Agents (no cooperation)")
    print("  4. Simulator-Only (no perception)")
    print("  5. TrafficSense Full")
    print("=" * 70)
    
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
    
    env = ProperCityFlowEnv(config_path)
    print(f"Intersections: {env.intersection_ids}")
    
    # Perception data path
    perception_path = '/mnt/c/Pilli/trafficsense/outputs/synthetic_perception.json'
    
    results = {}
    
    # 1. FixedTime (skip if already exists)
    fixed_csv = '/mnt/c/Pilli/trafficsense/outputs/simulation_results/fixedtime_360_metrics.csv'
    if os.path.exists(fixed_csv):
        print("\n[SKIP] FixedTime already exists")
        import json
        with open('/mnt/c/Pilli/trafficsense/outputs/simulation_results/fixedtime_360_summary.json', 'r') as f:
            results['fixedtime'] = json.load(f)
    else:
        print("\n[RUN] FixedTime")
        fixed = __import__('run_proper_sim', fromlist=['FixedTimeController']).FixedTimeController(30)
        _, summary = run_simulation('FixedTime', fixed, env, total_steps=360)
        results['fixedtime'] = summary
    
    # 2. MaxPressure (skip if already exists)
    mp_csv = '/mnt/c/Pilli/trafficsense/outputs/simulation_results/maxpressure_360_metrics.csv'
    if os.path.exists(mp_csv):
        print("\n[SKIP] MaxPressure already exists")
        import json
        with open('/mnt/c/Pilli/trafficsense/outputs/simulation_results/maxpressure_360_summary.json', 'r') as f:
            results['maxpressure'] = json.load(f)
    else:
        print("\n[RUN] MaxPressure")
        mp = MaxPressureController(decision_interval=10, min_green=5)
        _, summary = run_simulation('maxpressure', mp, env, total_steps=360)
        results['maxpressure'] = summary
    
    # 3. Isolated Agents (no cooperation)
    print("\n[RUN] Isolated Agents (no cooperation)")
    iso = IsolatedController(perception_path, decision_interval=30)
    _, summary = run_simulation('isolated', iso, env, total_steps=360)
    results['isolated'] = summary
    
    # 4. Simulator-Only (no perception)
    print("\n[RUN] Simulator-Only (no perception)")
    sim_only = SimulatorOnlyController(decision_interval=30)
    _, summary = run_simulation('simulatoronly', sim_only, env, total_steps=360)
    results['simulatoronly'] = summary
    
    # 5. TrafficSense Full (skip if already exists)
    ts_csv = '/mnt/c/Pilli/trafficsense/outputs/simulation_results/trafficsense_360_metrics.csv'
    if os.path.exists(ts_csv):
        print("\n[SKIP] TrafficSense Full already exists")
        import json
        with open('/mnt/c/Pilli/trafficsense/outputs/simulation_results/trafficsense_360_summary.json', 'r') as f:
            results['trafficsense'] = json.load(f)
    else:
        print("\n[RUN] TrafficSense Full")
        sys.path.insert(0, '/mnt/c/Pilli/trafficsense/src/orchestration')
        from cooperative_reasoning import CooperativeReasoningEngine
        from perception_adapter import CoLLMLightPerceptionAdapter
        
        class FullController:
            def __init__(self, perception_path, decision_interval=30):
                self.adapter = CoLLMLightPerceptionAdapter(perception_path)
                self.engine = CooperativeReasoningEngine()
                self.decision_interval = decision_interval
                self.current_phases = {}
                
            def decide(self, step, iid, state, all_states):
                if step % self.decision_interval != 0:
                    return self.current_phases.get(iid, 0)
                enhanced = self.adapter.get_state(iid, state)
                enhanced['intersection_id'] = iid
                neighbors = [s for sid, s in all_states.items() if sid != iid]
                try:
                    decision = self.engine.decide(iid, enhanced, neighbors)
                    new_phase = decision.get('recommended_phase', 0)
                    self.current_phases[iid] = new_phase
                    return new_phase
                except:
                    return self.current_phases.get(iid, 0)
        
        full = FullController(perception_path, 30)
        _, summary = run_simulation('trafficsense', full, env, total_steps=360)
        results['trafficsense'] = summary
    
    # Save ablation summary
    import json
    ablation_path = '/mnt/c/Pilli/trafficsense/outputs/simulation_results/ablation_summary.json'
    with open(ablation_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Print table
    print(f"\n{'='*70}")
    print("ABLATION STUDY RESULTS")
    print(f"{'='*70}")
    print(f"{'Configuration':<25} {'ATT':>10} {'AQL':>10} {'AWT':>10}")
    print("-" * 60)
    for name, res in results.items():
        print(f"{name:<25} {res.get('avg_att', 0):>10.2f} {res.get('avg_aql', 0):>10.2f} {res.get('avg_awt', 0):>10.2f}")
    
    print(f"\nAblation summary saved: {ablation_path}")
    print("=" * 70)

if __name__ == '__main__':
    main()
