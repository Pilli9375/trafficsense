"""
TrafficSense: Fast Fine-Tuning (7PM Deadline Mode)
===================================================
Takes the well-initialized last.pt (9 epochs on 40K images) and 
fine-tunes on a curated 1,500-image balanced Indian subset at 640px.
Expected completion: ~60-75 minutes.
"""
import os, sys, shutil, glob, random, yaml, time
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src import config

SEED = 42
random.seed(SEED)

# ─────────────────────────────────────────────
# Step 1: Build a balanced curated subset
# ─────────────────────────────────────────────
def build_curated_subset(src_root, dst_root, target_train=1500, target_val=200):
    src_root = Path(src_root)
    dst_root = Path(dst_root)

    OUR_CLASSES = [
        'car','motorcycle','bus','truck','autorickshaw','bicycle',
        'ambulance','police_vehicle','tractor','pedestrian','traffic_light',
        'traffic_sign','scooter','e-rickshaw','van','tempo','animal',
        'pushcart','water_tanker','excavator','crane','jeep','mini_bus','fire_engine'
    ]

    # PRIORITY classes we care most about — oversample these
    PRIORITY = {4, 5, 6, 7, 12, 13}  # autorickshaw, bicycle, ambulance, police, scooter, e-rickshaw

    for split, target in [("train", target_train), ("valid", target_val)]:
        src_img = src_root / split / "images"
        src_lbl = src_root / split / "labels"
        dst_img = dst_root / split / "images"
        dst_lbl = dst_root / split / "labels"
        dst_img.mkdir(parents=True, exist_ok=True)
        dst_lbl.mkdir(parents=True, exist_ok=True)

        all_imgs = sorted(glob.glob(str(src_img / "*.jpg")) + glob.glob(str(src_img / "*.png")))
        
        # Score each image by whether it has priority classes
        priority_imgs = []
        normal_imgs = []
        
        for img_path in all_imgs:
            stem = Path(img_path).stem
            lbl_path = src_lbl / f"{stem}.txt"
            has_priority = False
            if lbl_path.exists():
                for line in open(lbl_path):
                    p = line.strip().split()
                    if len(p) == 5 and int(float(p[0])) in PRIORITY:
                        has_priority = True
                        break
            if has_priority:
                priority_imgs.append(img_path)
            else:
                normal_imgs.append(img_path)

        random.shuffle(priority_imgs)
        random.shuffle(normal_imgs)

        # Fill 50% with priority images, 50% with normal
        n_priority = min(len(priority_imgs), target // 2)
        n_normal   = min(len(normal_imgs),   target - n_priority)
        selected   = priority_imgs[:n_priority] + normal_imgs[:n_normal]
        random.shuffle(selected)

        print(f"  {split}: {len(selected)} selected ({n_priority} priority + {n_normal} normal)")

        for img_path in selected:
            stem = Path(img_path).stem
            ext  = Path(img_path).suffix
            lbl_path = src_lbl / f"{stem}.txt"
            shutil.copy2(img_path, dst_img / Path(img_path).name)
            if lbl_path.exists():
                shutil.copy2(lbl_path, dst_lbl / f"{stem}.txt")
            else:
                open(str(dst_lbl / f"{stem}.txt"), "w").close()

    # Write data.yaml
    base_yaml = yaml.safe_load(open(str(src_root / "data.yaml")))
    base_yaml["path"] = str(dst_root).replace("\\", "/")
    with open(str(dst_root / "data.yaml"), "w") as f:
        yaml.dump(base_yaml, f, default_flow_style=False)

    print(f"  Saved to: {dst_root}")
    return dst_root


# ─────────────────────────────────────────────
# Step 2: Fast fine-tune from last.pt
# ─────────────────────────────────────────────
def fast_finetune(data_yaml):
    import torch
    from ultralytics import YOLO

    # Start from the well-trained last.pt (9 epochs on 40K images)
    checkpoint = str(config.OUTPUTS_DIR / "yolo_nuclear_v8m" / "weights" / "last.pt")
    print(f"\n  Starting from checkpoint: {checkpoint}")
    print(f"  GPU: {torch.cuda.get_device_name(0)}")

    model = YOLO(checkpoint)

    train_args = {
        "data":          str(data_yaml),
        "epochs":        120,
        "imgsz":         640,          # Faster than 832, still good quality
        "batch":         16,           # Safe at 640px
        "device":        0,
        "workers":       4,
        "project":       str(config.OUTPUTS_DIR),
        "name":          "yolo_finetune_fast",
        "exist_ok":      True,
        "pretrained":    True,
        "optimizer":     "AdamW",
        "lr0":           0.0003,       # Low LR for fine-tuning (don't overwrite what we learned)
        "lrf":           0.01,
        "momentum":      0.937,
        "weight_decay":  0.0005,
        "warmup_epochs": 2.0,
        "patience":      30,           # Stop early if converged
        "save":          True,
        "save_period":   10,
        "plots":         True,
        "mosaic":        1.0,
        "mixup":         0.1,
        "hsv_h":         0.015,
        "hsv_s":         0.7,
        "hsv_v":         0.4,
        "fliplr":        0.5,
        "box":           7.5,
        "cls":           0.8,
        "dfl":           1.5,
    }

    t0 = time.time()
    results = model.train(**train_args)
    elapsed = (time.time() - t0) / 60

    # Auto-deploy best model
    best_src = config.OUTPUTS_DIR / "yolo_finetune_fast" / "weights" / "best.pt"
    best_dst = config.MODELS_DIR / "yolo" / "best.pt"
    if best_src.exists():
        os.makedirs(best_dst.parent, exist_ok=True)
        shutil.copy2(best_src, best_dst)
        print(f"\n  [DEPLOYED] Best model -> {best_dst}")

    print(f"\n{'='*60}")
    print(f"  Done in {elapsed:.1f} minutes")
    try:
        print(f"  mAP50:    {results.results_dict.get('metrics/mAP50(B)', 'N/A'):.4f}")
        print(f"  mAP50-95: {results.results_dict.get('metrics/mAP50-95(B)', 'N/A'):.4f}")
    except Exception:
        pass


if __name__ == "__main__":
    print("=" * 60)
    print("  TrafficSense: Fast Fine-Tune (7PM Mode)")
    print("=" * 60)

    # Source: the massive augmented dataset we built
    aug_src  = config.DATA_DIR / "processed" / "unified_indian_merged_aug"
    fallback = config.DATA_DIR / "processed" / "unified_indian_merged"
    
    if aug_src.exists():
        src = aug_src
    elif fallback.exists():
        src = fallback
    else:
        src = config.DATA_DIR / "processed" / "unified_indian"
    
    print(f"\n  Source dataset: {src}")

    curated = config.DATA_DIR / "processed" / "curated_fast"
    print(f"\n[Step 1/2] Building balanced 1500-image subset...")
    build_curated_subset(src, curated, target_train=1500, target_val=200)

    print(f"\n[Step 2/2] Fast fine-tuning from last.pt checkpoint...")
    fast_finetune(curated / "data.yaml")
