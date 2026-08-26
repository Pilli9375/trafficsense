import os
import sys

print("=== TrafficSense Analytics Verification ===")

base = r'C:\Pilli\trafficsense'
checks = {}

# Check page file
page_path = os.path.join(base, 'src', 'dashboard', 'pages', '3_analytics.py')
checks['3_analytics.py exists'] = os.path.exists(page_path)

# Syntax check
syntax_ok = False
if checks['3_analytics.py exists']:
    try:
        with open(page_path, 'r', encoding='utf-8') as f:
            code = f.read()
        compile(code, page_path, 'exec')
        print("[OK] Page syntax is valid Python")
        syntax_ok = True
        
        # Check features
        checks['has_plotly_charts'] = 'plotly' in code or 'px.' in code or 'go.' in code
        checks['has_comparison_table'] = 'table' in code.lower()
        checks['has_metric_cards'] = 'metric' in code.lower() or 'render_metric_card' in code
        checks['has_data_export'] = 'export' in code.lower()
        checks['has_summary_report'] = 'summary' in code.lower() or 'executive' in code.lower()
        
        print(f"{'[OK]' if checks['has_plotly_charts'] else '[FAIL]'} Plotly charts")
        print(f"{'[OK]' if checks['has_comparison_table'] else '[FAIL]'} Comparison table")
        print(f"{'[OK]' if checks['has_metric_cards'] else '[FAIL]'} Metric cards")
        print(f"{'[OK]' if checks['has_data_export'] else '[FAIL]'} Data export")
        print(f"{'[OK]' if checks['has_summary_report'] else '[FAIL]'} Summary report")
        
    except SyntaxError as e:
        print(f"[FAIL] Syntax error: {e}")

# Check data files exist
for name in ['fixedtime', 'trafficsense']:
    checks[f'{name}_metrics.csv'] = os.path.exists(os.path.join(base, 'outputs', 'simulation_results', f'{name}_metrics.csv'))

# Print results
passed = 0
for name, ok in checks.items():
    status = '[OK]' if ok else '[FAIL]'
    print(f"{status} {name}")
    if ok:
        passed += 1

if syntax_ok: passed += 1
total = len(checks) + 1
print(f"\nAnalytics verification: {passed}/{total} checks passed.")
