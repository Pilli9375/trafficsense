import os
import sys

print("=== TrafficSense YOLOv8n Training Verification ===")

checks = {}
base = r'C:\Pilli\trafficsense'

# Check model files
checks['models/yolo/best.pt'] = os.path.exists(os.path.join(base, 'models', 'yolo', 'best.pt'))
checks['models/yolo/last.pt'] = os.path.exists(os.path.join(base, 'models', 'yolo', 'last.pt'))

# Check training outputs
train_dir = os.path.join(base, 'outputs', 'yolo_training')
checks['outputs/yolo_training/'] = os.path.exists(train_dir)

if checks['outputs/yolo_training/']:
    subchecks = ['results.csv', 'args.yaml', 'confusion_matrix.png', 'F1_curve.png']
    for sub in subchecks:
        checks[f'outputs/yolo_training/{sub}'] = os.path.exists(os.path.join(train_dir, sub)) or os.path.exists(os.path.join(train_dir, f'Box{sub}'))
    
    # Check weights subfolder
    checks['outputs/yolo_training/weights/best.pt'] = os.path.exists(os.path.join(train_dir, 'weights', 'best.pt'))

# Check metrics from results.csv
try:
    import pandas as pd
    results_path = os.path.join(train_dir, 'results.csv')
    if os.path.exists(results_path):
        df = pd.read_csv(results_path)
        df.columns = [c.strip() for c in df.columns]
        last_epoch = df.iloc[-1]
        map50 = float(last_epoch.get('metrics/mAP50(B)', 0))
        map50_95 = float(last_epoch.get('metrics/mAP50-95(B)', 0))
        print(f"[INFO] Final mAP50: {map50:.4f}")
        print(f"[INFO] Final mAP50-95: {map50_95:.4f}")
        if map50 > 0.3:
            print("[OK] mAP50 is reasonable (> 0.30)")
        else:
            print("[WARN] mAP50 is low — may need more training data")
except Exception as e:
    print(f"[INFO] Could not read metrics: {e}")

# Print results
passed = 0
for name, ok in checks.items():
    status = '[OK]' if ok else '[FAIL]'
    print(f"{status} {name}")
    if ok:
        passed += 1

print(f"\nYOLO training verification: {passed}/{len(checks)} checks passed.")
