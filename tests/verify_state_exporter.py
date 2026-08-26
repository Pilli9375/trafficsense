import json
import os

print("=== TrafficSense State Exporter Verification ===")

base = r'C:\Pilli\trafficsense'
checks = {}

# Check source files
checks['state_exporter.py'] = os.path.exists(os.path.join(base, 'src', 'perception', 'state_exporter.py'))
checks['convert_real_states.py'] = os.path.exists(os.path.join(base, 'src', 'perception', 'convert_real_states.py'))

# Check output
state_path = os.path.join(base, 'outputs', 'perception_demo', 'collmlight_state.json')
checks['collmlight_state.json'] = os.path.exists(state_path)

# Validate JSON structure
structure_ok = False
if checks['collmlight_state.json']:
    try:
        with open(state_path, 'r') as f:
            state = json.load(f)
        
        required_keys = ['intersection_id', 'phase', 'n_queue', 'n_move', 
                        'occupancy', 'tau', 'rho']
        has_keys = all(k in state for k in required_keys)
        print(f"{'[OK]' if has_keys else '[FAIL]'} CoLLMLight required keys present")
        
        # Check types
        type_ok = (
            isinstance(state['intersection_id'], str) and
            isinstance(state['phase'], int) and
            isinstance(state['n_queue'], list) and
            isinstance(state['n_move'], list) and
            isinstance(state['occupancy'], (int, float)) and
            isinstance(state['tau'], (int, float)) and
            isinstance(state['rho'], (int, float))
        )
        print(f"{'[OK]' if type_ok else '[FAIL]'} Value types correct")
        
        # Check TrafficSense extensions
        ext_ok = 'vehicle_mix' in state and 'congestion_level' in state
        print(f"{'[OK]' if ext_ok else '[FAIL]'} TrafficSense extensions present")
        
        structure_ok = has_keys and type_ok and ext_ok
        
        # Print summary
        print(f"\n--- Sample State ---")
        print(f"  Intersection: {state['intersection_id']}")
        print(f"  Phase: {state['phase']}")
        print(f"  n_queue: {state['n_queue']}")
        print(f"  n_move: {state['n_move']}")
        print(f"  occupancy: {state['occupancy']}")
        print(f"  tau: {state['tau']}s")
        print(f"  rho: {state['rho']}")
        print(f"  congestion: {state.get('congestion_level', 'N/A')}")
        print(f"  vehicle_mix: {state.get('vehicle_mix', {})}")
        
    except Exception as e:
        print(f"[FAIL] JSON validation error: {e}")

# Print results
passed = 0
for name, ok in checks.items():
    status = '[OK]' if ok else '[FAIL]'
    print(f"{status} {name}")
    if ok:
        passed += 1

print(f"\nState exporter verification: {passed}/{len(checks)} checks passed.")
