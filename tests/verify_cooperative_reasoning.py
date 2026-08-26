import json
import os
import sys

print("=== TrafficSense Cooperative Reasoning Verification ===")

base = r'C:\Pilli\trafficsense'
checks = {}

# Check files
checks['prompt_builder.py'] = os.path.exists(os.path.join(base, 'src', 'orchestration', 'prompt_builder.py'))
checks['cooperative_reasoning.py'] = os.path.exists(os.path.join(base, 'src', 'orchestration', 'cooperative_reasoning.py'))

# Check decisions output
decisions_path = os.path.join(base, 'outputs', 'cooperative_decisions.json')
checks['cooperative_decisions.json'] = os.path.exists(decisions_path)

# Validate decisions
decision_ok = False
if checks['cooperative_decisions.json']:
    try:
        with open(decisions_path, 'r') as f:
            decisions = json.load(f)
        
        print(f"[OK] Decisions file: {len(decisions)} intersection decisions")
        
        for d in decisions:
            iid = d.get('intersection_id', 'UNKNOWN')
            decision = d.get('decision', {})
            
            # Check required fields
            has_phase = 'recommended_phase' in decision
            has_duration = 'green_duration_seconds' in decision
            has_reasoning = 'reasoning' in decision
            
            print(f"[OK] {iid}: phase={decision.get('recommended_phase')}, duration={decision.get('green_duration_seconds')}s")
            
            if not (has_phase and has_duration and has_reasoning):
                print(f"[FAIL] {iid}: Missing required decision fields")
        
        # Check state has TrafficSense extensions
        if decisions:
            state = decisions[0].get('state', {})
            has_mix = 'vehicle_mix' in state
            has_level = 'congestion_level' in state
            print(f"{'[OK]' if has_mix else '[FAIL]'} State has vehicle_mix")
            print(f"{'[OK]' if has_level else '[FAIL]'} State has congestion_level")
            
            decision_ok = has_phase and has_duration and has_reasoning and has_mix and has_level
            
    except Exception as e:
        print(f"[FAIL] Decision validation error: {e}")

# Check that reasoning mentions cooperation
cooperation_found = False
if checks['cooperative_decisions.json']:
    with open(decisions_path, 'r') as f:
        decisions = json.load(f)
    for d in decisions:
        reasoning = d.get('decision', {}).get('reasoning', '').lower()
        if 'neighbor' in reasoning or 'cooperat' in reasoning or 'congestion' in reasoning:
            cooperation_found = True
            break
    print(f"{'[OK]' if cooperation_found else '[WARN]'} Reasoning mentions traffic concepts")

# Print results
passed = 0
for name, ok in checks.items():
    status = '[OK]' if ok else '[FAIL]'
    print(f"{status} {name}")
    if ok:
        passed += 1

if decision_ok: passed += 1
if cooperation_found: passed += 1

total = len(checks) + 2
print(f"\nCooperative reasoning verification: {passed}/{total} checks passed.")
