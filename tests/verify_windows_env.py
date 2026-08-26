import sys
import platform
import subprocess

def main():
    print("=== TrafficSense Windows Environment Verification ===")
    print(f"Python executable: {sys.executable}")
    print(f"Python version: {sys.version.split(' ')[0]}")
    
    checks_passed = 0
    total_checks = 11
    
    try:
        import torch
        print(f"PyTorch version: {torch.__version__}")
        cuda_avail = torch.cuda.is_available()
        print(f"CUDA Available: {cuda_avail}")
        if cuda_avail:
            try:
                print(f"CUDA Device: {torch.cuda.get_device_name(0)}")
                print(f"CUDA VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
            except:
                pass
        checks_passed += 1
    except Exception as e:
        print(f"[FAIL] torch: {e}")
        
    try:
        import torchvision
        print(f"torchvision version: {torchvision.__version__}")
        checks_passed += 1
    except Exception as e:
        print(f"[FAIL] torchvision: {e}")
        
    try:
        import ultralytics
        print(f"ultralytics version: {ultralytics.__version__}")
        checks_passed += 1
    except Exception as e:
        print(f"[FAIL] ultralytics: {e}")
        
    try:
        from ultralytics import YOLO
        model = YOLO('yolov8n.pt')
        print("YOLOv8n loaded successfully")
        checks_passed += 1
    except Exception as e:
        print(f"[FAIL] YOLO loading: {e}")
        
    try:
        import cv2
        print(f"OpenCV version: {cv2.__version__}")
        checks_passed += 1
    except Exception as e:
        print(f"[FAIL] opencv-python: {e}")
        
    try:
        import streamlit
        print(f"streamlit version: {streamlit.__version__}")
        checks_passed += 1
    except Exception as e:
        print(f"[FAIL] streamlit: {e}")
        
    try:
        import plotly
        print(f"plotly version: {plotly.__version__}")
        checks_passed += 1
    except Exception as e:
        print(f"[FAIL] plotly: {e}")
        
    try:
        import pandas
        print(f"pandas version: {pandas.__version__}")
        checks_passed += 1
    except Exception as e:
        print(f"[FAIL] pandas: {e}")
        
    try:
        import numpy
        print(f"numpy version: {numpy.__version__}")
        checks_passed += 1
    except Exception as e:
        print(f"[FAIL] numpy: {e}")
        
    try:
        import transformers
        print(f"transformers version: {transformers.__version__}")
        checks_passed += 1
    except Exception as e:
        print(f"[FAIL] transformers: {e}")
        
    try:
        import llama_cpp
        print("llama-cpp-python: OK")
        checks_passed += 1
    except ImportError:
        print("llama-cpp-python: SKIP (optional)")
        checks_passed += 1
    except Exception as e:
        print(f"[FAIL] llama-cpp-python: {e}")
        
    print(f"Windows env verification: {checks_passed}/{total_checks} checks passed.")

if __name__ == "__main__":
    main()
