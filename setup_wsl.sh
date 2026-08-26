#!/bin/bash
set -e
echo "Updating apt..."
sudo apt update && sudo apt upgrade -y
echo "Installing packages..."
sudo apt install -y python3 python3-pip python3-venv git build-essential cmake

mkdir -p ~/trafficsense
cd ~/trafficsense

if [ ! -d "CoLLMLight" ]; then
    echo "Cloning CoLLMLight..."
    git clone https://github.com/usail-hkust/CoLLMLight.git
fi
cd CoLLMLight
echo "Directory listing of CoLLMLight:"
ls -la

echo "Creating venv..."
python3 -m venv venv
source venv/bin/activate
echo "Python version:"
python3 --version

echo "Installing CityFlow..."
pip install --upgrade pip setuptools wheel
if ! pip install cityflow; then
    echo "cityflow pip install failed, building from source..."
    cd ~
    if [ ! -d "CityFlow" ]; then
        git clone https://github.com/cityflow-project/CityFlow.git
    fi
    cd CityFlow
    pip install .
    cd ~/trafficsense/CoLLMLight
fi

echo "Installing CoLLMLight dependencies..."
pip install tensorflow-cpu==2.8.0
pip install torch==2.2.2
pip install transformers==4.48.2
pip install trl==0.9.2
pip install openai

echo "Creating tests directory in WSL..."
mkdir -p ~/trafficsense/tests

cat << 'EOF' > ~/trafficsense/tests/verify_wsl_env.py
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
EOF

echo "Copying to Windows..."
cp ~/trafficsense/tests/verify_wsl_env.py /mnt/c/Pilli/trafficsense/tests/verify_wsl_env.py

echo "Done."