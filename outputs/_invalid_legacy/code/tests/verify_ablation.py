import os
import json

print("=== TrafficSense Ablation Study Verification ===")

base = r'C:\Pilli\trafficsense'
out_dir = os.path.join(base, 'outputs', 'simulation_results')

configs = ['fixedtime', 'maxpressure', 'isolated', 'simulatoronly', 'trafficsense']
checks = {}
summaries = {}

for cfg in configs:
    csv_path = os.path.join(out_dir, f'{cfg}_360_metrics.csv')
    json_path = os.path.join(out_dir, f'{cfg}_360_summary.json')
    
    checks[f'{cfg}_metrics'] = os.path.exists(csv_path)
    checks[f'{cfg}_summary'] = os.path.exists(json_path)
    
    if checks[f'{cfg}_metrics']:
        print(f"[OK] {cfg}_360_metrics.csv exists")
    else:
        print(f"[FAIL] {cfg}_360_metrics.csv missing")
    
    if checks[f'{cfg}_summary']:
        try:
            with open(json_path, 'r') as f:
                summaries[cfg] = json.load(f)
            print(f"[OK] {cfg} summary loaded")
        except Exception as e:
            print(f"[FAIL] {cfg} summary error: {e}")

# Check ablation summary
ablation_path = os.path.join(out_dir, 'ablation_summary.json')
checks['ablation_summary'] = os.path.exists(ablation_path)
if checks['ablation_summary']:
    print("[OK] ablation_summary.json exists")

# Print comparison table
if len(summaries) >= 3:
    print(f"\n{'='*60}")
    print("ABLATION COMPARISON")
    print(f"{'='*60}")
    print(f"{'Config':<20} {'ATT':>10} {'AQL':>10} {'AWT':>10}")
    print("-" * 55)
    for cfg in configs:
        if cfg in summaries:
            s = summaries[cfg]
            print(f"{cfg:<20} {s.get('avg_att', 0):>10.2f} {s.get('avg_aql', 0):>10.2f} {s.get('avg_awt', 0):>10.2f}")

passed = sum(1 for v in checks.values() if v)
total = len(checks)
print(f"\nAblation verification: {passed}/{total} checks passed.")
