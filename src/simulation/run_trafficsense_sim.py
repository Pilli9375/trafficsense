"""
TrafficSense Network Simulation
Runs CityFlow with cooperative LLM control via perception adapter.
"""
import json
import os
import sys
import time
import csv
from pathlib import Path
from typing import Dict, List

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'orchestration'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'perception'))

from cityflow_env import CityFlowEnv
from perception_adapter import CoLLMLightPerceptionAdapter
from cooperative_reasoning import CooperativeReasoningEngine


class TrafficSenseSimulator:
    def __init__(self, config_path: str, perception_path: str, output_dir: str):
        self.env = CityFlowEnv(config_path)
        self.adapter = CoLLMLightPerceptionAdapter(perception_path)
        self.engine = CooperativeReasoningEngine()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.metrics = []
        self.decisions_log = []
        
    def run_fixed_time_baseline(self, total_steps: int = 360, phase_duration: int = 30):
        """
        Run FixedTime baseline: each phase lasts 30 steps.
        """
        print(f"\n{'='*60}")
        print("Running FixedTime Baseline")
        print(f"{'='*60}")
        
        self.env.reset()
        self.metrics = []
        
        for step in range(total_steps):
            self.env.step()
            
            # FixedTime: switch phase every phase_duration steps
            for iid in self.env.intersection_ids:
                phase = (step // phase_duration) % 4
                self.env.set_phase(iid, phase)
            
            # Log metrics every 10 steps
            if step % 10 == 0:
                self._log_metrics(step, 'FixedTime')
            
            if step % 60 == 0:
                print(f"  Step {step}/{total_steps}")
        
        self._save_results('fixedtime')
        print("FixedTime baseline complete.")
        
    def run_trafficsense(self, total_steps: int = 360, decision_interval: int = 20):
        """
        Run TrafficSense: cooperative LLM decisions every N steps.
        """
        print(f"\n{'='*60}")
        print("Running TrafficSense Cooperative Control")
        print(f"{'='*60}")
        
        self.env.reset()
        self.adapter.reset()
        self.metrics = []
        self.decisions_log = []
        
        current_phases = {iid: 0 for iid in self.env.intersection_ids}
        
        for step in range(total_steps):
            self.env.step()
            
            # Make cooperative decisions at intervals
            if step % decision_interval == 0:
                print(f"\n[Step {step}] Making cooperative decisions...")
                
                # Get states for all intersections
                states = {}
                for iid in self.env.intersection_ids:
                    fallback = self.env.get_state(iid)
                    fallback['phase'] = current_phases[iid]
                    states[iid] = self.adapter.get_state(iid, fallback)
                
                # Make decisions for each intersection
                for iid in self.env.intersection_ids:
                    own = states[iid]
                    neighbors = [states[nid] for nid in self.env.intersection_ids if nid != iid]
                    
                    try:
                        decision = self.engine.decide(iid, own, neighbors)
                        new_phase = decision['recommended_phase']
                        self.env.set_phase(iid, new_phase)
                        current_phases[iid] = new_phase
                        
                        self.decisions_log.append({
                            'step': step,
                            'intersection': iid,
                            'decision': decision,
                            'state': own
                        })
                    except Exception as e:
                        print(f"[WARN] Decision failed for {iid}: {e}")
            
            # Log metrics every 10 steps
            if step % 10 == 0:
                self._log_metrics(step, 'TrafficSense')
            
            if step % 60 == 0:
                print(f"  Step {step}/{total_steps}")
        
        self._save_results('trafficsense')
        print("TrafficSense simulation complete.")
        
    def _log_metrics(self, step: int, controller: str):
        """Log current simulation metrics."""
        for iid in self.env.intersection_ids:
            state = self.env.get_state(iid)
            self.metrics.append({
                'step': step,
                'controller': controller,
                'intersection': iid,
                'total_queued': sum(state['n_queue']),
                'total_moving': sum(state['n_move']),
                'occupancy': state['occupancy'],
                'tau': state['tau'],
                'rho': state['rho']
            })
    
    def _save_results(self, name: str):
        """Save metrics and decisions to CSV/JSON."""
        # Metrics CSV
        metrics_path = self.output_dir / f'{name}_metrics.csv'
        if self.metrics:
            with open(metrics_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.metrics[0].keys())
                writer.writeheader()
                writer.writerows(self.metrics)
            print(f"  Metrics saved: {metrics_path}")
        
        # Decisions JSON
        if self.decisions_log:
            decisions_path = self.output_dir / f'{name}_decisions.json'
            with open(decisions_path, 'w') as f:
                json.dump(self.decisions_log, f, indent=2)
            print(f"  Decisions saved: {decisions_path}")
        
        # Summary
        if self.metrics:
            avg_queue = sum(m['total_queued'] for m in self.metrics) / len(self.metrics)
            avg_tau = sum(m['tau'] for m in self.metrics) / len(self.metrics)
            summary = {
                'controller': name,
                'avg_queue_length': round(avg_queue, 2),
                'avg_wait_time': round(avg_tau, 2),
                'total_steps': len(self.metrics)
            }
            summary_path = self.output_dir / f'{name}_summary.json'
            with open(summary_path, 'w') as f:
                json.dump(summary, f, indent=2)
            print(f"  Summary: {summary}")


def demo():
    """Run a short demo simulation."""
    print("TrafficSense Network Simulation Demo")
    print("=" * 60)
    
    # Use CoLLMLight's Synthetic 4x4 config
    config_path = os.path.expanduser("~/trafficsense/CoLLMLight/data/Synthetic/4_4/config.json")
    
    # If config doesn't exist, create a minimal one
    if not os.path.exists(config_path):
        print(f"[INFO] Config not found at {config_path}, using mock mode")
        config_path = 'dummy_config.json'
    
    # Generate or use existing perception data
    perc_path = r'C:\Pilli\trafficsense\outputs\synthetic_perception.json'
    if not os.path.exists(perc_path):
        sys.path.insert(0, r'C:\Pilli\trafficsense\src\orchestration')
        from perception_adapter import PerceptionStateGenerator
        PerceptionStateGenerator.generate_for_network((2, 2), 200, perc_path)
    
    output_dir = r'C:\Pilli\trafficsense\outputs\simulation_results'
    
    sim = TrafficSenseSimulator(config_path, perc_path, output_dir)
    
    # Run short demos (60 steps each for speed)
    sim.run_fixed_time_baseline(total_steps=60, phase_duration=15)
    sim.run_trafficsense(total_steps=60, decision_interval=20)
    
    print(f"\n{'='*60}")
    print("Demo complete. Check outputs/simulation_results/")
    print(f"{'='*60}")


if __name__ == '__main__':
    demo()
