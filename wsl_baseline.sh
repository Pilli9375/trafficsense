#!/bin/bash
set -e

cd ~/trafficsense/CoLLMLight
source venv/bin/activate
echo "=== Step 1 ==="
pwd
ls -la

echo "=== Step 2 ==="
mkdir -p data/FinetuneData
ls -lh data/Synthetic/4_4/ || echo "Synthetic/4_4 not found"
ls -lh data/FinetuneData/

echo "=== Step 3 ==="
# run_fts.py uses standard output. I will redirect it to a log file and show first/last 20 lines later.
# Wait, let's just run it!
python run_fts.py > run_fts.log 2>&1 || echo "run_fts.py failed with exit code $?"

echo "First 20 lines of run_fts.log:"
head -n 20 run_fts.log
echo "..."
echo "Last 20 lines of run_fts.log:"
tail -n 20 run_fts.log

echo "=== Step 4 ==="
ls -lh data/FinetuneData/SynTrain_sample.json || echo "SynTrain_sample.json not found"
if [ -f "data/FinetuneData/SynTrain_sample.json" ]; then
    head -n 3 data/FinetuneData/SynTrain_sample.json
else
    find data/FinetuneData/ -type f -name "*.json"
fi

echo "=== Step 5 ==="
cat << 'EOF' > ~/trafficsense/tests/verify_baseline.py
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
EOF

python3 ~/trafficsense/tests/verify_baseline.py

echo "=== Step 6 ==="
cp ~/trafficsense/tests/verify_baseline.py /mnt/c/Pilli/trafficsense/tests/verify_baseline.py

echo "Done."