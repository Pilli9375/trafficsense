import os
import csv
import json

print("=== TrafficSense 360-Step Simulation Verification ===")

base = r'C:\Pilli\trafficsense'
checks = {}
metrics = {}

# Check files
for name in ['fixedtime', 'trafficsense']:
    csv_path = os.path.join(base, 'outputs', 'simulation_results', f'{name}_360_metrics.csv')
    json_path = os.path.join(base, 'outputs', 'simulation_results', f'{name}_360_summary.json')
    
    checks[f'{name}_360_metrics.csv'] = os.path.exists(csv_path)
    checks[f'{name}_360_summary.json'] = os.path.exists(json_path)
    
    if checks[f'{name}_360_metrics.csv']:
        try:
            with open(csv_path, 'r') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            
            print(f"[OK] {name}_360_metrics.csv: {len(rows)} rows")
            checks[f'{name}_rows_360'] = len(rows) >= 360
            
            # Check columns
            if rows:
                has_att = 'att' in rows[0]
                has_aql = 'aql' in rows[0]
                has_awt = 'awt' in rows[0]
                print(f"{'[OK]' if has_att else '[FAIL]'} Has ATT column")
                print(f"{'[OK]' if has_aql else '[FAIL]'} Has AQL column")
                print(f"{'[OK]' if has_awt else '[FAIL]'} Has AWT column")
                checks[f'{name}_has_metrics'] = has_att and has_aql and has_awt
                
        except Exception as e:
            print(f"[FAIL] {name} metrics error: {e}")
    
    if checks[f'{name}_360_summary.json']:
        try:
            with open(json_path, 'r') as f:
                summary = json.load(f)
            print(f"[OK] {name} summary: {summary}")
            metrics[name] = summary
        except Exception as e:
            print(f"[FAIL] {name} summary error: {e}")

# Compare
if 'fixedtime' in metrics and 'trafficsense' in metrics:
    ft = metrics['fixedtime']
    ts = metrics['trafficsense']
    
    print(f"\n--- Comparison ---")
    for m in ['avg_att', 'avg_aql', 'avg_awt']:
        ft_val = ft.get(m, 0)
        ts_val = ts.get(m, 0)
        if ft_val > 0:
            improvement = ((ft_val - ts_val) / ft_val) * 100
            print(f"{m}: FixedTime={ft_val:.2f}, TrafficSense={ts_val:.2f}, Improvement={improvement:+.1f}%")

# Print results
passed = sum(1 for v in checks.values() if v)
total = len(checks)
print(f"\n360-step simulation verification: {passed}/{total} checks passed.")
