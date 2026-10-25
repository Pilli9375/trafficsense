import json
import os
import sys

print("=== TrafficSense Perception Adapter Verification ===")

base = r'C:\Pilli\trafficsense'
checks = {}

# Check files
checks['perception_adapter.py'] = os.path.exists(os.path.join(base, 'src', 'orchestration', 'perception_adapter.py'))
checks['run_collmlight_with_perception.py'] = os.path.exists(os.path.join(base, 'src', 'orchestration', 'run_collmlight_with_perception.py'))

# Check synthetic perception data
syn_path = os.path.join(base, 'outputs', 'synthetic_perception.json')
checks['synthetic_perception.json'] = os.path.exists(syn_path)

# Validate synthetic data
json_ok = False
if checks['synthetic_perception.json']:
    try:
        with open(syn_path, 'r') as f:
            data = json.load(f)
        print(f"[OK] synthetic_perception.json: {len(data)} frames")
        
        if len(data) > 0:
            first = data[0]
            has_analysis = 'analysis' in first
            has_count = 'vehicle_count' in first.get('analysis', {})
            print(f"{'[OK]' if has_analysis else '[FAIL]'} Has 'analysis' key")
            print(f"{'[OK]' if has_count else '[FAIL]'} Has 'vehicle_count' in analysis")
            json_ok = has_analysis and has_count
    except Exception as e:
        print(f"[FAIL] JSON error: {e}")

# Test adapter logic
adapter_ok = False
try:
    sys.path.insert(0, os.path.join(base, 'src', 'orchestration'))
    from perception_adapter import CoLLMLightPerceptionAdapter
    
    adapter = CoLLMLightPerceptionAdapter(syn_path)
    fallback = {
        'intersection_id': 'I0', 'phase': 0,
        'n_queue': [1,1,1,1], 'n_move': [1,1,1,1],
        'occupancy': 0.1, 'tau': 1.0, 'rho': 1.0
    }
    state = adapter.get_state('I0', fallback)
    
    checks['adapter_returns_state'] = isinstance(state, dict)
    checks['adapter_has_n_queue'] = 'n_queue' in state
    checks['adapter_has_extensions'] = 'vehicle_mix' in state and 'congestion_level' in state
    checks['adapter_source_tag'] = state.get('source') == 'TrafficSense_Perception'
    
    print(f"\n--- Sample Converted State ---")
    print(f"  n_queue: {state['n_queue']}")
    print(f"  n_move: {state['n_move']}")
    print(f"  occupancy: {state['occupancy']}")
    print(f"  tau: {state['tau']}")
    print(f"  rho: {state['rho']}")
    print(f"  congestion: {state.get('congestion_level')}")
    print(f"  source: {state.get('source')}")
    
    adapter_ok = all([
        checks['adapter_returns_state'],
        checks['adapter_has_n_queue'],
        checks['adapter_has_extensions'],
        checks['adapter_source_tag']
    ])
    
except Exception as e:
    print(f"[FAIL] Adapter test error: {e}")

# Print results
passed = 0
for name, ok in checks.items():
    status = '[OK]' if ok else '[FAIL]'
    print(f"{status} {name}")
    if ok:
        passed += 1

total = len(checks)
print(f"\nPerception adapter verification: {passed}/{total} checks passed.")
