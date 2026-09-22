import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src import config
from ultralytics import YOLO
import torch
import yaml

def main():
    print("=" * 60)
    print("TrafficSense: Upgraded YOLOv8s Training on Unified Indian Dataset")
    print("=" * 60)
    
    # Verify GPU
    print(f"\nPyTorch: {torch.__version__}")
    print(f"CUDA: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    
    # Load data config
    data_yaml = str(config.DATA_DIR / 'processed' / 'unified_indian' / 'data.yaml')
    with open(data_yaml, 'r') as f:
        data_config = yaml.safe_load(f)
    print(f"\nDataset: {data_yaml}")
    print(f"Classes: {data_config.get('nc', 'unknown')}")
    print(f"Class names: {data_config.get('names', [])}")
    
    # UPGRADE: Use YOLOv8s (Small) instead of YOLOv8n (Nano) for much better accuracy
    # It still easily fits in 6GB VRAM.
    model = YOLO('yolov8s.pt')
    print("\nModel: YOLOv8s (pre-trained on COCO)")
    
    # Training config optimized for RTX 4050 6GB - High Accuracy
    train_args = {
        'data': data_yaml,
        'epochs': 150,                # UPGRADE: 150 epochs
        'imgsz': 640,
        'batch': 16,                  # UPGRADE: 16 batch size fits in 6GB for v8s
        'device': 0 if torch.cuda.is_available() else 'cpu',
        'workers': 4,
        'project': str(config.OUTPUTS_DIR),
        'name': 'yolo_training_v8s',  # New output folder
        'exist_ok': True,
        'pretrained': True,
        'optimizer': 'AdamW',
        'lr0': 0.001,
        'lrf': 0.01,
        'momentum': 0.937,
        'weight_decay': 0.0005,
        'warmup_epochs': 3.0,
        'box': 7.5,
        'cls': 0.5,
        'dfl': 1.5,
        'patience': 30,               # UPGRADE: Increased from 10 to 30
        'save': True,
        'save_period': 10,
        'plots': True,
        # Data Augmentations
        'mosaic': 1.0,
        'mixup': 0.1,
        'hsv_h': 0.015,
        'hsv_s': 0.7,
        'hsv_v': 0.4
    }
    
    print(f"\nTraining config:")
    for k, v in train_args.items():
        print(f"  {k}: {v}")
    
    # Train
    start = time.time()
    results = model.train(**train_args)
    elapsed = time.time() - start
    
    # Summary
    best_src = os.path.join(train_args['project'], train_args['name'], 'weights', 'best.pt')
    print(f"\n{'=' * 60}")
    print("Training Complete!")
    print(f"Total time: {elapsed / 60:.1f} minutes")
    print(f"Best model: {best_src}")
    print(f"Final mAP50: {results.results_dict.get('metrics/mAP50(B)', 'N/A')}")
    print(f"Final mAP50-95: {results.results_dict.get('metrics/mAP50-95(B)', 'N/A')}")
    
    # Auto-copy the new best model to models/yolo/best.pt
    best_dest = str(config.MODELS_DIR / 'yolo' / 'best.pt')
    import shutil
    if os.path.exists(best_src):
        os.makedirs(os.path.dirname(best_dest), exist_ok=True)
        shutil.copy2(best_src, best_dest)
        print(f"\n[INFO] Auto-copied upgraded model to {best_dest}")
        print("The dashboard will now automatically use this improved model!")
        
    last_src = os.path.join(train_args['project'], train_args['name'], 'weights', 'last.pt')
    if os.path.exists(last_src):
        last_dest = str(config.MODELS_DIR / 'yolo' / 'last.pt')
        shutil.copy2(last_src, last_dest)
        print(f"[INFO] Auto-copied last model to {last_dest}")

if __name__ == '__main__':
    main()
