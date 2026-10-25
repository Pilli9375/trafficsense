import os
import json
import csv

print("=== TrafficSense Inference Pipeline Verification ===")

base = r'C:\Pilli\trafficsense'
out_dir = os.path.join(base, 'outputs', 'perception_demo')

checks = {}

# Check output files
checks['output_dir'] = os.path.exists(out_dir)
checks['detected_output.mp4'] = os.path.exists(os.path.join(out_dir, 'detected_output.mp4'))
checks['perception_states.json'] = os.path.exists(os.path.join(out_dir, 'perception_states.json'))
checks['perception_summary.csv'] = os.path.exists(os.path.join(out_dir, 'perception_summary.csv'))

# Validate JSON
json_ok = False
if checks['perception_states.json']:
    try:
        with open(os.path.join(out_dir, 'perception_states.json'), 'r') as f:
            states = json.load(f)
        print(f"[OK] perception_states.json: {len(states)} frames")
        if len(states) > 0:
            first = states[0]
            required_keys = ['timestamp', 'frame_idx', 'analysis', 'tracks']
            has_keys = all(k in first for k in required_keys)
            print(f"{'[OK]' if has_keys else '[FAIL]'} State structure valid")
            json_ok = has_keys
            
            # Check analysis keys
            analysis = first['analysis']
            analysis_keys = ['vehicle_count', 'density_veh_per_100m', 'congestion_severity', 'class_distribution']
            has_analysis = all(k in analysis for k in analysis_keys)
            print(f"{'[OK]' if has_analysis else '[FAIL]'} Analysis structure valid")
    except Exception as e:
        print(f"[FAIL] JSON invalid: {e}")

# Validate CSV
csv_ok = False
if checks['perception_summary.csv']:
    try:
        with open(os.path.join(out_dir, 'perception_summary.csv'), 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        print(f"[OK] perception_summary.csv: {len(rows)} rows")
        csv_ok = len(rows) > 0
    except Exception as e:
        print(f"[FAIL] CSV invalid: {e}")

# Print results
passed = 0
for name, ok in checks.items():
    status = '[OK]' if ok else '[FAIL]'
    print(f"{status} {name}")
    if ok:
        passed += 1

print(f"\nInference pipeline verification: {passed}/{len(checks)} checks passed.")
