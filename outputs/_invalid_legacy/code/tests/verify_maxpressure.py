import os
import csv
import json

print("=== TrafficSense MaxPressure + Three-Way Comparison Verification ===")

base = r'C:\Pilli\trafficsense'
out_dir = os.path.join(base, 'outputs', 'simulation_results')

controllers = ['fixedtime', 'maxpressure', 'trafficsense']
checks = {}
summaries = {}

for ctrl in controllers:
    csv_path = os.path.join(out_dir, f'{ctrl}_360_metrics.csv')
    json_path = os.path.join(out_dir, f'{ctrl}_360_summary.json')
    
    checks[f'{ctrl}_metrics'] = os.path.exists(csv_path)
    checks[f'{ctrl}_summary'] = os.path.exists(json_path)
    
    if checks[f'{ctrl}_metrics']:
        try:
            with open(csv_path, 'r') as f:
                rows = list(csv.DictReader(f))
            print(f"[OK] {ctrl}_360_metrics.csv: {len(rows)} rows")
            checks[f'{ctrl}_rows_ok'] = len(rows) >= 360
        except Exception as e:
            print(f"[FAIL] {ctrl} metrics: {e}")
    
    if checks[f'{ctrl}_summary']:
        try:
            with open(json_path, 'r') as f:
                summaries[ctrl] = json.load(f)
            print(f"[OK] {ctrl} summary loaded")
        except Exception as e:
            print(f"[FAIL] {ctrl} summary: {e}")

# Three-way comparison table
print(f"\n{'='*70}")
print("THREE-WAY COMPARISON")
print(f"{'='*70}")
print(f"{'Metric':<20} {'FixedTime':>12} {'MaxPressure':>12} {'TrafficSense':>12}")
print("-" * 60)

for metric in ['avg_att', 'avg_aql', 'avg_awt']:
    ft_val = summaries.get('fixedtime', {}).get(metric, 0)
    mp_val = summaries.get('maxpressure', {}).get(metric, 0)
    ts_val = summaries.get('trafficsense', {}).get(metric, 0)
    print(f"{metric:<20} {ft_val:>12.2f} {mp_val:>12.2f} {ts_val:>12.2f}")

# Calculate improvements vs MaxPressure (the stronger baseline)
if 'maxpressure' in summaries and 'trafficsense' in summaries:
    print(f"\nTrafficSense vs MaxPressure:")
    for metric in ['avg_att', 'avg_aql', 'avg_awt']:
        mp_val = summaries['maxpressure'].get(metric, 0)
        ts_val = summaries['trafficsense'].get(metric, 0)
        if mp_val > 0:
            improvement = ((mp_val - ts_val) / mp_val) * 100
            print(f"  {metric}: {improvement:+.1f}%")

# Print results
passed = sum(1 for v in checks.values() if v)
total = len(checks)
print(f"\nMaxPressure verification: {passed}/{total} checks passed.")
