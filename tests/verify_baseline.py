#!/usr/bin/env python3
import json
import os

print("=== TrafficSense CoLLMLight Baseline Verification ===")

# Check output file
sample_path = os.path.expanduser("~/trafficsense/CoLLMLight/data/FinetuneData/SynTrain_sample.json")
if os.path.exists(sample_path):
    size_mb = os.path.getsize(sample_path) / (1024 * 1024)
    print(f"[OK] SynTrain_sample.json exists ({size_mb:.2f} MB)")
    with open(sample_path, 'r') as f:
        data = json.load(f)
    print(f"[OK] Valid JSON with {len(data)} records")
    if len(data) > 0:
        print(f"[OK] First record keys: {list(data[0].keys())}")
else:
    print(f"[FAIL] SynTrain_sample.json not found at {sample_path}")

# Check roadnet
roadnet = os.path.expanduser("~/trafficsense/CoLLMLight/data/Synthetic/4_4/roadnet_4_4.json")
if os.path.exists(roadnet):
    print("[OK] Synthetic 4x4 roadnet exists")
else:
    print("[FAIL] Roadnet missing")

# Check CoLLMLight core files
core_files = ["run_CoLLMlight.py", "run_fts.py", "ppo_ft.py"]
for f in core_files:
    path = os.path.expanduser(f"~/trafficsense/CoLLMLight/{f}")
    print(f"{'[OK]' if os.path.exists(path) else '[MISSING]'} {f}")

print("Baseline verification complete.")
