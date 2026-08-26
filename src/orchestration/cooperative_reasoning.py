"""
Cooperative Reasoning Engine
Simulates CoLLMLight's async SR + RD pipeline with local LLM.
"""
import json
import requests
import sys
import os
from typing import Dict, List

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'perception'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from perception_adapter import CoLLMLightPerceptionAdapter, PerceptionStateGenerator
from prompt_builder import CoLLMLightPromptBuilder


class CooperativeReasoningEngine:
    def __init__(self, model_name='gemma3:4b', api_url='http://localhost:11434/v1'):
        self.model = model_name
        self.api_url = api_url
        self.builder = CoLLMLightPromptBuilder()
        
    def _call_llm(self, prompt: str, temperature=0.7, max_tokens=200) -> str:
        """Call local Ollama LLM."""
        try:
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers={"Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are an expert traffic signal controller."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens
                },
                timeout=60
            )
            response.raise_for_status()
            return response.json()['choices'][0]['message']['content']
        except Exception as e:
            print(f"[LLM ERROR] {e}")
            return '{"recommended_phase": 0, "green_duration_seconds": 30, "reasoning": "Fallback due to error", "cooperation_needed": false, "neighbor_coordination": "none"}'
    
    def _parse_decision(self, response_text: str) -> Dict:
        """Extract JSON decision from LLM response."""
        try:
            # Try direct JSON parse
            decision = json.loads(response_text)
            required = ['recommended_phase', 'green_duration_seconds', 'reasoning']
            if all(k in decision for k in required):
                return decision
        except json.JSONDecodeError:
            pass
        
        # Try extracting JSON from markdown code block
        import re
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except:
                pass
        
        # Fallback
        print(f"[WARN] Could not parse LLM response: {response_text[:200]}")
        return {
            'recommended_phase': 0,
            'green_duration_seconds': 30,
            'reasoning': 'Parse fallback',
            'cooperation_needed': False,
            'neighbor_coordination': 'none'
        }
    
    def run_sr(self, own_state: Dict, neighbor_states: List[Dict]) -> str:
        """
        Spatiotemporal Reasoning: Analyze neighbors, produce suggestion.
        """
        prompt = self.builder.build_sr_prompt(own_state, neighbor_states)
        response = self._call_llm(prompt, temperature=0.7, max_tokens=250)
        return response
    
    def run_rd(self, own_state: Dict, sr_suggestion: str) -> Dict:
        """
        Real-time Decision: Make final signal decision.
        """
        prompt = self.builder.build_rd_prompt(own_state, sr_suggestion)
        response = self._call_llm(prompt, temperature=0.3, max_tokens=150)
        decision = self._parse_decision(response)
        decision['sr_raw'] = sr_suggestion[:200]  # store for debugging
        return decision
    
    def decide(self, intersection_id: str, own_state: Dict, neighbor_states: List[Dict]) -> Dict:
        """
        Full async pipeline: SR → RD → Decision.
        """
        print(f"\n{'='*60}")
        print(f"Cooperative Decision for {intersection_id}")
        print(f"{'='*60}")
        
        # Step 1: SR (can run in background in real CoLLMLight)
        print("[SR] Running spatiotemporal reasoning...")
        sr_result = self.run_sr(own_state, neighbor_states)
        print(f"[SR] Suggestion received ({len(sr_result)} chars)")
        
        # Step 2: RD (real-time decision)
        print("[RD] Making real-time decision...")
        decision = self.run_rd(own_state, sr_result)
        
        print(f"[DECISION] Phase: {decision['recommended_phase']}, Duration: {decision['green_duration_seconds']}s")
        print(f"[DECISION] Reasoning: {decision['reasoning']}")
        print(f"[DECISION] Cooperation: {decision.get('cooperation_needed', False)}")
        
        return decision


def demo():
    """Run a full cooperative reasoning demo."""
    print("TrafficSense Cooperative Reasoning Demo")
    print("=" * 60)
    
    # Generate synthetic perception for 2 intersections
    gen = PerceptionStateGenerator()
    gen.generate_for_network((1, 2), 10, r'C:\Pilli\trafficsense\outputs\demo_perception.json')
    
    # Load perception adapter
    adapter = CoLLMLightPerceptionAdapter(r'C:\Pilli\trafficsense\outputs\demo_perception.json')
    
    # Create engine
    engine = CooperativeReasoningEngine()
    
    # Simulate 2 intersections
    intersections = ['I0', 'I1']
    decisions = []
    
    for i, iid in enumerate(intersections):
        # Get own state
        fallback = {
            'intersection_id': iid,
            'phase': 0,
            'n_queue': [0, 0, 0, 0],
            'n_move': [0, 0, 0, 0],
            'occupancy': 0.0,
            'tau': 0.0,
            'rho': 0.0
        }
        own = adapter.get_state(iid, fallback)
        own['intersection_id'] = iid  # ensure ID is set
        
        # Get neighbor states (simplified: other intersections)
        neighbors = []
        for other_iid in intersections:
            if other_iid != iid:
                nf = dict(fallback)
                nf['intersection_id'] = other_iid
                # Simulate different congestion for neighbor
                nf['n_queue'] = [2, 1, 1, 0]
                nf['occupancy'] = 0.2
                nf['congestion_level'] = 'low'
                neighbors.append(nf)
        
        # Decide
        decision = engine.decide(iid, own, neighbors)
        decisions.append({
            'intersection_id': iid,
            'decision': decision,
            'state': own
        })
    
    # Save results
    output_path = r'C:\Pilli\trafficsense\outputs\cooperative_decisions.json'
    with open(output_path, 'w') as f:
        json.dump(decisions, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"Demo complete. Decisions saved to: {output_path}")
    print(f"{'='*60}")
    
    # Summary
    for d in decisions:
        print(f"\n{d['intersection_id']}:")
        print(f"  Phase: {d['decision']['recommended_phase']}")
        print(f"  Duration: {d['decision']['green_duration_seconds']}s")
        print(f"  Reasoning: {d['decision']['reasoning']}")


if __name__ == '__main__':
    demo()
