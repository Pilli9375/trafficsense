import os
import sys

print("=== TrafficSense Dashboard Verification ===")

base = r'C:\Pilli\trafficsense'
checks = {}

# Check files
files = [
    'src/dashboard/app.py',
    'src/dashboard/utils.py',
    'src/dashboard/components/metric_card.py',
    'src/dashboard/components/intersection_card.py',
    'src/dashboard/pages/1_live_monitor.py',
    'src/dashboard/pages/2_network_control.py',
    'src/dashboard/pages/3_analytics.py',
]

for f in files:
    checks[f] = os.path.exists(os.path.join(base, f))

# Check imports
import_ok = False
try:
    sys.path.insert(0, os.path.join(base, 'src', 'dashboard'))
    import utils
    import_ok = True
    print("[OK] Dashboard utils import successful")
except Exception as e:
    print(f"[FAIL] Import error: {e}")

# Check Streamlit is available
st_ok = False
try:
    import streamlit as st
    st_ok = True
    print(f"[OK] Streamlit version: {st.__version__}")
except Exception as e:
    print(f"[FAIL] Streamlit not available: {e}")

# Print results
passed = 0
for name, ok in checks.items():
    status = '[OK]' if ok else '[FAIL]'
    print(f"{status} {name}")
    if ok:
        passed += 1

total = len(checks) + (1 if import_ok else 0) + (1 if st_ok else 0)
if import_ok: passed += 1
if st_ok: passed += 1

print(f"\nDashboard verification: {passed}/{total} checks passed.")
