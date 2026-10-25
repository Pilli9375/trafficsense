#!/usr/bin/env python3
import sys
print("=== TrafficSense WSL Environment Verification ===")
print(f"Python: {sys.version}")

try:
    import cityflow
    print("[OK] CityFlow imported")
    print(f"    CityFlow version: {cityflow.__version__ if hasattr(cityflow, '__version__') else 'unknown'}")
except Exception as e:
    print(f"[FAIL] CityFlow: {e}")

try:
    import torch
    print(f"[OK] PyTorch: {torch.__version__}")
except Exception as e:
    print(f"[FAIL] PyTorch: {e}")

try:
    import tensorflow as tf
    print(f"[OK] TensorFlow: {tf.__version__}")
except Exception as e:
    print(f"[FAIL] TensorFlow: {e}")

try:
    import transformers
    print(f"[OK] Transformers: {transformers.__version__}")
except Exception as e:
    print(f"[FAIL] Transformers: {e}")

# Check CoLLMLight files exist
import os
collm_path = os.path.expanduser("~/trafficsense/CoLLMLight")
files_to_check = ["run_CoLLMlight.py", "config/", "utils/"]
for f in files_to_check:
    full = os.path.join(collm_path, f)
    exists = os.path.exists(full)
    print(f"{'[OK]' if exists else '[MISSING]'} CoLLMLight/{f}")

print("WSL verification complete.")
