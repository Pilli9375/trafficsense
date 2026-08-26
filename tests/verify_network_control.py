import os
import sys

print("=== TrafficSense Network Control Verification ===")

base = r'C:\Pilli\trafficsense'
checks = {}

# Check page file
page_path = os.path.join(base, 'src', 'dashboard', 'pages', '2_network_control.py')
checks['2_network_control.py exists'] = os.path.exists(page_path)

# Syntax check
syntax_ok = False
if checks['2_network_control.py exists']:
    try:
        with open(page_path, 'r', encoding='utf-8') as f:
            code = f.read()
        compile(code, page_path, 'exec')
        print("[OK] Page syntax is valid Python")
        syntax_ok = True
        
        # Check features
        checks['has_grid_layout'] = 'columns' in code and 'intersection' in code.lower()
        checks['has_phase_display'] = 'phase' in code.lower()
        checks['has_reasoning_trace'] = 'reasoning' in code.lower()
        checks['has_decision_log'] = 'table' in code or 'dataframe' in code
        checks['has_cooperation_map'] = 'cooperat' in code.lower() or 'agent' in code.lower()
        
        print(f"{'[OK]' if checks['has_grid_layout'] else '[FAIL]'} Grid layout")
        print(f"{'[OK]' if checks['has_phase_display'] else '[FAIL]'} Phase display")
        print(f"{'[OK]' if checks['has_reasoning_trace'] else '[FAIL]'} Reasoning trace")
        print(f"{'[OK]' if checks['has_decision_log'] else '[FAIL]'} Decision log")
        print(f"{'[OK]' if checks['has_cooperation_map'] else '[FAIL]'} Cooperation map")
        
    except SyntaxError as e:
        print(f"[FAIL] Syntax error: {e}")

# Check decisions data exists
checks['decisions.json exists'] = os.path.exists(os.path.join(base, 'outputs', 'simulation_results', 'trafficsense_decisions.json'))

# Print results
passed = 0
for name, ok in checks.items():
    status = '[OK]' if ok else '[FAIL]'
    print(f"{status} {name}")
    if ok:
        passed += 1

if syntax_ok: passed += 1

total = len(checks) + 1
print(f"\nNetwork control verification: {passed}/{total} checks passed.")
