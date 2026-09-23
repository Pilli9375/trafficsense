import sys, shutil, os, multiprocessing
from pathlib import Path

sys.path.insert(0, 'C:/Pilli/trafficsense')

def main():
    from src import config
    import torch
    from ultralytics import YOLO

    checkpoint = str(config.OUTPUTS_DIR / 'yolo_nuclear_v8m' / 'weights' / 'last.pt')
    data_yaml  = 'C:/Pilli/trafficsense/data/processed/curated_fast/data.yaml'

    print(f'GPU: {torch.cuda.get_device_name(0)}')
    print(f'Checkpoint: {checkpoint}')
    print('Starting fast fine-tune...')

    model = YOLO(checkpoint)
    results = model.train(
        data=data_yaml,
        epochs=120,
        imgsz=640,
        batch=16,
        device=0,
        workers=0,          # 0 workers avoids Windows multiprocessing issues
        project=str(config.OUTPUTS_DIR),
        name='yolo_finetune_fast',
        exist_ok=True,
        pretrained=True,
        optimizer='AdamW',
        lr0=0.0003,
        lrf=0.01,
        warmup_epochs=2.0,
        patience=30,
        save=True,
        save_period=10,
        plots=True,
        mosaic=1.0,
        mixup=0.1,
        fliplr=0.5,
        box=7.5,
        cls=0.8,
        dfl=1.5,
    )

    best_src = config.OUTPUTS_DIR / 'yolo_finetune_fast' / 'weights' / 'best.pt'
    best_dst = config.MODELS_DIR / 'yolo' / 'best.pt'
    if best_src.exists():
        os.makedirs(str(best_dst.parent), exist_ok=True)
        shutil.copy2(str(best_src), str(best_dst))
        print(f'DEPLOYED -> {best_dst}')
    try:
        print(f"mAP50: {results.results_dict.get('metrics/mAP50(B)', 'N/A')}")
    except Exception as e:
        print(f'Done. ({e})')

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
