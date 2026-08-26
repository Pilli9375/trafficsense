from ultralytics import YOLO
import torch
import yaml
import os
import time

def main():
    print("=" * 60)
    print("TrafficSense: YOLOv8n Training on Unified Indian Dataset")
    print("=" * 60)
    
    # Verify GPU
    print(f"\nPyTorch: {torch.__version__}")
    print(f"CUDA: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")
    
    # Load data config
    data_yaml = r'C:\Pilli\trafficsense\data\processed\unified_indian\data.yaml'
    with open(data_yaml, 'r') as f:
        config = yaml.safe_load(f)
    print(f"\nDataset: {data_yaml}")
    print(f"Classes: {config.get('nc', 'unknown')}")
    print(f"Class names: {config.get('names', [])}")
    
    # Load model
    model = YOLO('yolov8n.pt')
    print("\nModel: YOLOv8n (pre-trained on COCO)")
    
    # Training config optimized for RTX 4050 6GB
    train_args = {
        'data': data_yaml,
        'epochs': 50,
        'imgsz': 640,
        'batch': 8,           # Safe for 6GB VRAM
        'device': 0,          # GPU
        'workers': 4,         # Data loading threads
        'project': r'C:\Pilli\trafficsense\outputs',
        'name': 'yolo_training',
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
        'patience': 10,       # Early stopping if no improvement
        'save': True,
        'save_period': 10,    # Save checkpoint every 10 epochs
        'plots': True,        # Generate training curves
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
    
    # Copy best model to models/yolo/
    os.makedirs(r'C:\Pilli\trafficsense\models\yolo', exist_ok=True)
    import shutil
    best_dst = r'C:\Pilli\trafficsense\models\yolo\best.pt'
    shutil.copy2(best_src, best_dst)
    print(f"\nCopied best model to: {best_dst}")
    
    # Also copy last.pt
    last_src = os.path.join(os.path.dirname(best_src), 'last.pt')
    if os.path.exists(last_src):
        last_dst = r'C:\Pilli\trafficsense\models\yolo\last.pt'
        shutil.copy2(last_src, last_dst)
        print(f"Copied last model to: {last_dst}")

if __name__ == '__main__':
    main()
