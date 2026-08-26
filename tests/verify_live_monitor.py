import os
import sys

print("=== TrafficSense Live Monitor Verification ===")

base = r'C:\Pilli\trafficsense'
checks = {}

# Check page file
page_path = os.path.join(base, 'src', 'dashboard', 'pages', '1_live_monitor.py')
checks['1_live_monitor.py exists'] = os.path.exists(page_path)

# Check imports
import_ok = False
if checks['1_live_monitor.py exists']:
    try:
        # We can't fully import Streamlit pages without running Streamlit,
        # but we can syntax-check by compiling
        with open(page_path, 'r', encoding='utf-8') as f:
            code = f.read()
        compile(code, page_path, 'exec')
        print("[OK] Page syntax is valid Python")
        import_ok = True
        
        # Check for key features
        has_upload = 'file_uploader' in code
        has_model = 'YOLO' in code
        has_metrics = 'metric_card' in code or 'markdown' in code
        has_progress = 'progress' in code
        
        checks['has_video_upload'] = has_upload
        checks['has_yolo_model'] = has_model
        checks['has_metrics_display'] = has_metrics
        checks['has_progress_bar'] = has_progress
        
        print(f"{'[OK]' if has_upload else '[FAIL]'} Video upload widget")
        print(f"{'[OK]' if has_model else '[FAIL]'} YOLO model loading")
        print(f"{'[OK]' if has_metrics else '[FAIL]'} Metrics display")
        print(f"{'[OK]' if has_progress else '[FAIL]'} Progress bar")
        
    except SyntaxError as e:
        print(f"[FAIL] Syntax error: {e}")

# Check model exists
checks['best.pt exists'] = os.path.exists(os.path.join(base, 'models', 'yolo', 'best.pt'))

# Print results
passed = 0
for name, ok in checks.items():
    status = '[OK]' if ok else '[FAIL]'
    print(f"{status} {name}")
    if ok:
        passed += 1

if import_ok: passed += 1

total = len(checks) + 1
print(f"\nLive monitor verification: {passed}/{total} checks passed.")
