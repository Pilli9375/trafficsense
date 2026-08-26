import json
import os
import csv

print("=== TrafficSense Network Simulation Verification ===")

base = r'C:\Pilli\trafficsense'
out_dir = os.path.join(base, 'outputs', 'simulation_results')
checks = {}

# Check output files
for name in ['fixedtime', 'trafficsense']:
    checks[f'{name}_metrics.csv'] = os.path.exists(os.path.join(out_dir, f'{name}_metrics.csv'))
    checks[f'{name}_summary.json'] = os.path.exists(os.path.join(out_dir, f'{name}_summary.json'))

# Check TrafficSense has decisions
checks['trafficsense_decisions.json'] = os.path.exists(os.path.join(out_dir, 'trafficsense_decisions.json'))

# Validate metrics
metrics_ok = False
if checks.get('trafficsense_metrics.csv'):
    try:
        with open(os.path.join(out_dir, 'trafficsense_metrics.csv'), 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        print(f"[OK] TrafficSense metrics: {len(rows)} rows")
        
        if rows:
            avg_queue = sum(float(r['total_queued']) for r in rows) / len(rows)
            print(f"[INFO] Average queue length: {avg_queue:.2f}")
            metrics_ok = True
    except Exception as e:
        print(f"[FAIL] Metrics error: {e}")

# Validate decisions
decisions_ok = False
if checks.get('trafficsense_decisions.json'):
    try:
        with open(os.path.join(out_dir, 'trafficsense_decisions.json'), 'r') as f:
            decisions = json.load(f)
        print(f"[OK] Decisions logged: {len(decisions)}")
        
        if decisions:
            d = decisions[0]['decision']
            has_keys = all(k in d for k in ['recommended_phase', 'green_duration_seconds', 'reasoning'])
            print(f"{'[OK]' if has_keys else '[FAIL]'} Decision structure valid")
            decisions_ok = has_keys
    except Exception as e:
        print(f"[FAIL] Decisions error: {e}")

# Print results
passed = 0
for name, ok in checks.items():
    status = '[OK]' if ok else '[FAIL]'
    print(f"{status} {name}")
    if ok:
        passed += 1

if metrics_ok: passed += 1
if decisions_ok: passed += 1

total = len(checks) + 2
print(f"\nNetwork simulation verification: {passed}/{total} checks passed.")
