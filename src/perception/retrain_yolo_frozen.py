import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src import config
from ultralytics import YOLO
import torch

def main():
    print("=" * 60)
    print("TrafficSense: Advanced Fine-Tuning (Frozen Backbone)")
    print("=" * 60)
    
    data_yaml = str(config.DATA_DIR / 'processed' / 'unified_indian' / 'data.yaml')
    model = YOLO('yolov8s.pt')
    
    train_args = {
        'data': data_yaml,
        'epochs': 300,
        'imgsz': 640,
        'batch': 16,
        'device': 0 if torch.cuda.is_available() else 'cpu',
        'workers': 4,
        'project': str(config.OUTPUTS_DIR),
        'name': 'yolo_training_v8s_frozen',
        'exist_ok': True,
        'pretrained': True,
        'optimizer': 'AdamW',
        'lr0': 0.0005,
        'lrf': 0.01,
        'freeze': 10, # FREEZE BACKBONE (LAYERS 0-9)
        'patience': 50,
        'save': True,
        'plots': True,
        'mosaic': 1.0,
        'mixup': 0.2,
        'copy_paste': 0.1
    }
    
    start = time.time()
    results = model.train(**train_args)
    elapsed = time.time() - start
    
    best_src = os.path.join(train_args['project'], train_args['name'], 'weights', 'best.pt')
    best_dest = str(config.MODELS_DIR / 'yolo' / 'best.pt')
    import shutil
    if os.path.exists(best_src):
        os.makedirs(os.path.dirname(best_dest), exist_ok=True)
        shutil.copy2(best_src, best_dest)
        print(f"\n[INFO] Auto-copied improved frozen model to {best_dest}")

if __name__ == '__main__':
    main()
