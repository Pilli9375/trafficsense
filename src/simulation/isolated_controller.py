"""
Isolated Agent Controller — TrafficSense without cooperation.
Each agent decides independently using LLM but NO neighbor context.
"""

import sys
sys.path.insert(0, '/mnt/c/Pilli/trafficsense/src/orchestration')
sys.path.insert(0, '/mnt/c/Pilli/trafficsense/src/perception')

from cooperative_reasoning import CooperativeReasoningEngine
from perception_adapter import CoLLMLightPerceptionAdapter


class IsolatedController:
    """
    TrafficSense without cooperation.
    Each intersection uses LLM with ONLY its own state.
    """
    
    def __init__(self, perception_path, decision_interval=30):
        self.adapter = CoLLMLightPerceptionAdapter(perception_path)
        self.engine = CooperativeReasoningEngine()
        self.decision_interval = decision_interval
        self.current_phases = {}
        self.decisions_log = []
        
    def decide(self, step, intersection_id, state, all_states):
        if step % self.decision_interval != 0:
            return self.current_phases.get(intersection_id, 0)
        
        # Get perception-enhanced state
        enhanced = self.adapter.get_state(intersection_id, state)
        enhanced['intersection_id'] = intersection_id
        
        # NO NEIGHBORS — empty list
        neighbors = []
        
        # Use engine but with no neighbors
        try:
            # Build prompt manually without neighbors
            from prompt_builder import CoLLMLightPromptBuilder
            builder = CoLLMLightPromptBuilder()
            
            prompt = builder.build_sr_prompt(enhanced, neighbors)
            
            # Call LLM directly
            import requests
            response = requests.post(
                "http://localhost:11434/v1/chat/completions",
                headers={"Content-Type": "application/json"},
                json={
                    "model": "gemma3:4b",
                    "messages": [
                        {"role": "system", "content": "You are a traffic signal controller."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.5,
                    "max_tokens": 150
                },
                timeout=60
            )
            
            content = response.json()['choices'][0]['message']['content']
            
            # Parse decision
            import json
            import re
            try:
                decision = json.loads(content)
            except:
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    decision = json.loads(json_match.group(1))
                else:
                    decision = {
                        'recommended_phase': 0,
                        'green_duration_seconds': 30,
                        'reasoning': 'Isolated fallback'
                    }
            
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
            print(f"[WARN] Isolated decision failed for {intersection_id}: {e}")
            return self.current_phases.get(intersection_id, 0)


if __name__ == '__main__':
    print("Isolated Controller loaded successfully")
