"""
Proper 360-step CityFlow simulation with real metric collection.
Runs in WSL, outputs to /mnt/c/Pilli/trafficsense/outputs/simulation_results/
"""

import json
import os
import sys
import time
import csv
from collections import defaultdict
from pathlib import Path

# Add Windows src paths so we can import orchestration code
sys.path.insert(0, '/mnt/c/Pilli/trafficsense/src/orchestration')
sys.path.insert(0, '/mnt/c/Pilli/trafficsense/src/perception')

import cityflow

# Import TrafficSense components
try:
    from perception_adapter import CoLLMLightPerceptionAdapter, PerceptionStateGenerator
    from cooperative_reasoning import CooperativeReasoningEngine
    from prompt_builder import CoLLMLightPromptBuilder
    TRAFFICSENSE_AVAILABLE = True
except Exception as e:
    print(f"[WARN] Could not import TrafficSense modules: {e}")
    TRAFFICSENSE_AVAILABLE = False


class ProperCityFlowEnv:
    """
    Proper CityFlow environment with real metric collection.
    """
    
    def __init__(self, config_path: str):
        self.engine = cityflow.Engine(config_path, thread_num=1)
        self.config_path = config_path
        self.current_step = 0
        
        # Load config to get intersection IDs
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        config_dir = os.path.dirname(config_path)
        roadnet_path = os.path.join(config_dir, config.get('roadnetFile', ''))
        
        with open(roadnet_path, 'r') as f:
            roadnet = json.load(f)
        
        self.intersection_ids = [
            node['id'] for node in roadnet.get('intersections', [])
            if node.get('trafficLight', None) is not None
        ]
        
        self.lane_count_per_intersection = 4  # standard for 4-way
        
        # Metric tracking
        self.att_history = []
        self.aql_history = []
        self.awt_history = []
        self.throughput_history = []
        
    def reset(self):
        self.engine.reset()
        self.current_step = 0
        self.att_history = []
        self.aql_history = []
        self.awt_history = []
        self.throughput_history = []
        
    def step(self):
        self.engine.next_step()
        self.current_step += 1
        
    def get_state(self, intersection_id: str, phase: int = 0) -> dict:
        """
        Get proper state with CityFlow-native metrics.
        """
        # Get lane-level data
        lane_vehicles = self.engine.get_lane_vehicle_count()
        lane_waiting = self.engine.get_lane_waiting_vehicle_count()
        
        # For simplicity, aggregate all lanes (in real implementation, 
        # you'd map lanes to specific intersections)
        total_vehicles = sum(lane_vehicles.values()) if lane_vehicles else 0
        total_waiting = sum(lane_waiting.values()) if lane_waiting else 0
        total_moving = max(0, total_vehicles - total_waiting)
        
        # Distribute across 4 approaches
        def distribute(n, lanes=4):
            if n == 0:
                return [0] * lanes
            base = n // lanes
            rem = n % lanes
            d = [base] * lanes
            for i in range(rem):
                d[i] += 1
            return d
        
        # Occupancy: total vehicles / capacity heuristic
        capacity = 80  # heuristic capacity for 4 lanes
        occupancy = min(total_vehicles / capacity, 1.0) if total_vehicles > 0 else 0.0
        
        # Wait time: heuristic based on waiting vehicles
        # Assume each waiting vehicle waits ~2.5s per step on average
        avg_wait = (total_waiting * 2.5) / max(total_vehicles, 1) * 10
        
        # Queue pressure
        if total_moving > 0:
            rho = (total_waiting / total_moving) * 10.0
        else:
            rho = total_waiting * 5.0
        
        return {
            'intersection_id': intersection_id,
            'phase': phase,
            'n_queue': distribute(total_waiting),
            'n_move': distribute(total_moving),
            'occupancy': round(occupancy, 3),
            'tau': round(avg_wait, 1),
            'rho': round(rho, 2),
            'total_vehicles': total_vehicles,
            'total_waiting': total_waiting
        }
    
    def set_phase(self, intersection_id: str, phase_id: int):
        self.engine.set_tl_phase(intersection_id, phase_id)
    
    def collect_metrics(self):
        """
        Collect real CityFlow metrics after each step.
        """
        # ATT: Average Travel Time (CityFlow native)
        try:
            att = self.engine.get_average_travel_time()
        except:
            att = 0.0
        
        # AQL: Average Queue Length (sum of waiting vehicles across all lanes)
        lane_waiting = self.engine.get_lane_waiting_vehicle_count()
        aql = sum(lane_waiting.values()) / max(len(lane_waiting), 1) if lane_waiting else 0
        
        # AWT: Average Waiting Time (approximate from queue length)
        # Heuristic: AWT ≈ AQL * 2.5 seconds (avg wait per queued vehicle)
        awt = aql * 2.5
        
        # Throughput: vehicles that have finished
        try:
            finished = len(self.engine.get_vehicles(include_running=False))
        except:
            finished = 0
        
        self.att_history.append(att)
        self.aql_history.append(aql)
        self.awt_history.append(awt)
        self.throughput_history.append(finished)
        
        return {
            'step': self.current_step,
            'att': round(att, 2),
            'aql': round(aql, 2),
            'awt': round(awt, 2),
            'throughput': finished
        }
    
    def get_summary(self):
        """Get final simulation summary."""
        if not self.att_history:
            return {}
        
        return {
            'avg_att': round(sum(self.att_history) / len(self.att_history), 2),
            'avg_aql': round(sum(self.aql_history) / len(self.aql_history), 2),
            'avg_awt': round(sum(self.awt_history) / len(self.awt_history), 2),
            'final_throughput': self.throughput_history[-1] if self.throughput_history else 0,
            'total_steps': self.current_step
        }


class FixedTimeController:
    """Fixed-time signal controller."""
    
    def __init__(self, phase_duration=30):
        self.phase_duration = phase_duration
        
    def decide(self, step, intersection_id, state):
        phase = (step // self.phase_duration) % 4
        return phase


class TrafficSenseController:
    """TrafficSense cooperative controller."""
    
    def __init__(self, perception_path, decision_interval=20):
        self.adapter = CoLLMLightPerceptionAdapter(perception_path)
        self.engine = CooperativeReasoningEngine()
        self.decision_interval = decision_interval
        self.current_phases = {}
        self.decisions_log = []
        
    def decide(self, step, intersection_id, state, all_states):
        if step % self.decision_interval != 0:
            return self.current_phases.get(intersection_id, 0)
        
        # Build neighbors
        neighbors = [s for sid, s in all_states.items() if sid != intersection_id]
        
        # Get perception-enhanced state
        enhanced = self.adapter.get_state(intersection_id, state)
        enhanced['intersection_id'] = intersection_id
        
        # Decide
        try:
            decision = self.engine.decide(intersection_id, enhanced, neighbors)
            new_phase = decision.get('recommended_phase', 0)
            self.current_phases[intersection_id] = new_phase
            
            self.decisions_log.append({
                'step': step,
                'intersection_id': intersection_id,
                'decision': decision,
                'state': enhanced
            })
            
            return new_phase
        except Exception as e:
            print(f"[WARN] Decision failed for {intersection_id}: {e}")
            return self.current_phases.get(intersection_id, 0)


def run_simulation(controller_name, controller, env, total_steps=360, output_dir='/mnt/c/Pilli/trafficsense/outputs/simulation_results'):
    """
    Run a full simulation and save metrics.
    """
    print(f"\n{'='*70}")
    print(f"Running {controller_name} Simulation ({total_steps} steps)")
    print(f"{'='*70}")
    
    env.reset()
    metrics = []
    phase_history = {iid: 0 for iid in env.intersection_ids}
    
    start_time = time.time()
    
    for step in range(total_steps):
        # Collect metrics BEFORE stepping
        metric = env.collect_metrics()
        
        # Get states for all intersections
        all_states = {}
        for iid in env.intersection_ids:
            all_states[iid] = env.get_state(iid, phase_history[iid])
        
        # Make decisions
        for iid in env.intersection_ids:
            if controller_name == 'FixedTime':
                new_phase = controller.decide(step, iid, all_states[iid])
            else:
                new_phase = controller.decide(step, iid, all_states[iid], all_states)
            
            env.set_phase(iid, new_phase)
            phase_history[iid] = new_phase
        
        # Step simulation
        env.step()
        
        # Add per-intersection details to metric
        for iid in env.intersection_ids:
            state = all_states[iid]
            metric[f'{iid}_queued'] = sum(state['n_queue'])
            metric[f'{iid}_moving'] = sum(state['n_move'])
            metric[f'{iid}_occupancy'] = state['occupancy']
            metric[f'{iid}_tau'] = state['tau']
        
        metrics.append(metric)
        
        # Progress
        if step % 60 == 0:
            elapsed = time.time() - start_time
            fps = (step + 1) / elapsed if elapsed > 0 else 0
            print(f"  Step {step}/{total_steps} | ATT: {metric['att']:.1f} | AQL: {metric['aql']:.1f} | FPS: {fps:.1f}")
    
    total_time = time.time() - start_time
    print(f"\nSimulation complete in {total_time:.1f}s")
    
    # Save metrics
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    csv_path = os.path.join(output_dir, f'{controller_name.lower()}_360_metrics.csv')
    
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=metrics[0].keys())
        writer.writeheader()
        writer.writerows(metrics)
    
    print(f"Metrics saved: {csv_path}")
    
    # Save summary
    summary = env.get_summary()
    summary['controller'] = controller_name
    summary['simulation_time_sec'] = round(total_time, 1)
    
    summary_path = os.path.join(output_dir, f'{controller_name.lower()}_360_summary.json')
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Summary: {summary}")
    
    # Save decisions if TrafficSense
    if controller_name == 'TrafficSense' and hasattr(controller, 'decisions_log'):
        decisions_path = os.path.join(output_dir, 'trafficsense_360_decisions.json')
        with open(decisions_path, 'w') as f:
            json.dump(controller.decisions_log, f, indent=2)
        print(f"Decisions saved: {decisions_path}")
    
    return metrics, summary


def main():
    print("TrafficSense Proper Simulation Runner")
    print("=" * 70)
    
    # Config path
    config_path = '/home/pilli/trafficsense/CoLLMLight/data/Synthetic/4_4/config.json'
    
    # Check if config exists
    if not os.path.exists(config_path):
        print(f"[ERROR] Config not found: {config_path}")
        print("[INFO] Searching for config...")
        # Try to find it
        for root, dirs, files in os.walk('/home/pilli/trafficsense/CoLLMLight/data'):
            for f in files:
                if f == 'config.json':
                    config_path = os.path.join(root, f)
                    print(f"[INFO] Found: {config_path}")
                    break
            if os.path.exists(config_path):
                break
    
    if not os.path.exists(config_path):
        print("[FATAL] Could not find CityFlow config.json")
        sys.exit(1)
    
    # Initialize environment
    print(f"\nInitializing CityFlow with: {config_path}")
    env = ProperCityFlowEnv(config_path)
    print(f"Intersections: {env.intersection_ids}")
    
    # Generate perception data if needed
    perception_path = '/mnt/c/Pilli/trafficsense/outputs/synthetic_perception.json'
    if not os.path.exists(perception_path):
        print("Generating synthetic perception data...")
        if TRAFFICSENSE_AVAILABLE:
            PerceptionStateGenerator.generate_for_network((2, 2), 400, perception_path)
        else:
            print("[ERROR] Cannot generate perception data")
            sys.exit(1)
    
    # Run FixedTime baseline
    fixed = FixedTimeController(phase_duration=30)
    fixed_metrics, fixed_summary = run_simulation('FixedTime', fixed, env, total_steps=360)
    
    # Run TrafficSense
    if TRAFFICSENSE_AVAILABLE:
        ts = TrafficSenseController(perception_path, decision_interval=30)
        ts_metrics, ts_summary = run_simulation('TrafficSense', ts, env, total_steps=360)
        
        # Print comparison
        print(f"\n{'='*70}")
        print("COMPARISON SUMMARY")
        print(f"{'='*70}")
        print(f"{'Metric':<25} {'FixedTime':>12} {'TrafficSense':>12} {'Improvement':>12}")
        print("-" * 65)
        
        for metric in ['avg_att', 'avg_aql', 'avg_awt']:
            ft_val = fixed_summary.get(metric, 0)
            ts_val = ts_summary.get(metric, 0)
            if ft_val > 0:
                improvement = ((ft_val - ts_val) / ft_val) * 100
            else:
                improvement = 0
            print(f"{metric:<25} {ft_val:>12.2f} {ts_val:>12.2f} {improvement:>11.1f}%")
    else:
        print("[SKIP] TrafficSense modules not available")
    
    print(f"\n{'='*70}")
    print("All simulations complete!")
    print(f"{'='*70}")


if __name__ == '__main__':
    main()
