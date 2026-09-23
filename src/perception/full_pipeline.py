"""
TrafficSense: Full Dataset Pipeline — Download + Augment + Train
================================================================
Run this ONCE. It will:
  1. Download Indian traffic datasets from Roboflow (~15 mins)
  2. Augment the combined dataset (×15 multiplier, ~5 mins)
  3. Launch nuclear YOLOv8m training (~3-5 hours)

Usage:
    python src/perception/full_pipeline.py --api-key GSjHQlBh5cQFV7mhMSPr
"""

import os
import sys
import shutil
import argparse
import glob
import yaml
import time
import random
from pathlib import Path
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src import config

# ─── Our 24 classes ──────────────────────────────────────────
OUR_CLASSES = [
    'car', 'motorcycle', 'bus', 'truck', 'autorickshaw', 'bicycle',
    'ambulance', 'police_vehicle', 'tractor', 'pedestrian', 'traffic_light',
    'traffic_sign', 'scooter', 'e-rickshaw', 'van', 'tempo', 'animal',
    'pushcart', 'water_tanker', 'excavator', 'crane', 'jeep', 'mini_bus', 'fire_engine'
]
CLASS_INDEX = {c: i for i, c in enumerate(OUR_CLASSES)}

REMAP = {
    'car': 'car', 'cars': 'car', 'sedan': 'car', 'hatchback': 'car', 'suv': 'car',
    'cab': 'car', 'taxi': 'car', 'vehicle': 'car',
    'motorcycle': 'motorcycle', 'motorbike': 'motorcycle', 'bike': 'motorcycle',
    'two-wheeler': 'motorcycle', 'two wheeler': 'motorcycle', '2 wheeler': 'motorcycle',
    'bus': 'bus', 'school bus': 'bus',
    'minibus': 'mini_bus', 'mini bus': 'mini_bus', 'mini-bus': 'mini_bus',
    'truck': 'truck', 'lorry': 'truck', 'mini-truck': 'truck', 'minitruck': 'truck',
    'autorickshaw': 'autorickshaw', 'auto': 'autorickshaw',
    'auto-rickshaw': 'autorickshaw', 'auto rickshaw': 'autorickshaw',
    'rickshaw': 'autorickshaw', 'three-wheeler': 'autorickshaw',
    '3 wheeler': 'autorickshaw', '3-wheeler': 'autorickshaw',
    'bicycle': 'bicycle', 'cycle': 'bicycle',
    'ambulance': 'ambulance',
    'police': 'police_vehicle', 'police car': 'police_vehicle',
    'police-van': 'police_vehicle', 'police van': 'police_vehicle',
    'tractor': 'tractor',
    'pedestrian': 'pedestrian', 'person': 'pedestrian', 'people': 'pedestrian',
    'human': 'pedestrian', 'walker': 'pedestrian',
    'traffic light': 'traffic_light', 'traffic-light': 'traffic_light',
    'traffic_light': 'traffic_light', 'signal': 'traffic_light',
    'trafficlight': 'traffic_light', 'red light': 'traffic_light',
    'traffic sign': 'traffic_sign', 'sign': 'traffic_sign',
    'traffic-sign': 'traffic_sign', 'trafficsign': 'traffic_sign',
    'scooter': 'scooter', 'scooty': 'scooter',
    'e-rickshaw': 'e-rickshaw', 'e rickshaw': 'e-rickshaw',
    'erickshaw': 'e-rickshaw', 'electric rickshaw': 'e-rickshaw',
    'van': 'van', 'minivan': 'van', 'mini-van': 'van',
    'tempo': 'tempo', 'tempo traveller': 'tempo',
    'animal': 'animal', 'cow': 'animal', 'dog': 'animal',
    'cattle': 'animal', 'goat': 'animal', 'horse': 'animal',
    'pushcart': 'pushcart', 'cart': 'pushcart', 'handcart': 'pushcart',
    'water tanker': 'water_tanker', 'tanker': 'water_tanker',
    'excavator': 'excavator', 'jcb': 'excavator',
    'crane': 'crane',
    'jeep': 'jeep',
    'fire engine': 'fire_engine', 'fire truck': 'fire_engine',
    'fire-engine': 'fire_engine', 'firetruck': 'fire_engine',
}

# ─── Roboflow datasets to download ──────────────────────────
# ALL verified accessible via Roboflow API
ROBOFLOW_DATASETS = [
    # Verified working (general vehicles, large)
    ("roboflow-100",  "vehicles-q0x2v",                2),
    # Indian vehicles with auto/rickshaw labels
    ("roboflow-100",  "indian-vehicles",                1),
    # Indian traffic with auto-rickshaws (public domain)
    ("shreya-qcnmp",  "indian-traffic-vehicles-oznec",  1),
    # Auto-rickshaw focused dataset
    ("traffic-1vyot", "auto-yolov8",                    1),
]


# ════════════════════════════════════════════════════════
# STAGE 1 — DOWNLOAD
# ════════════════════════════════════════════════════════

def remap_labels(src_lbl_dir, dst_lbl_dir, src_classes):
    os.makedirs(dst_lbl_dir, exist_ok=True)
    mapped = dropped = 0
    for lf in glob.glob(os.path.join(src_lbl_dir, "*.txt")):
        out_lines = []
        for line in open(lf):
            parts = line.strip().split()
            if len(parts) != 5:
                continue
            try:
                cls_id = int(parts[0])
                raw = src_classes[cls_id].lower().strip() if cls_id < len(src_classes) else ""
                our = REMAP.get(raw)
                if our is None:
                    dropped += 1
                    continue
                out_lines.append(f"{CLASS_INDEX[our]} " + " ".join(parts[1:]))
                mapped += 1
            except Exception:
                dropped += 1
        dst = os.path.join(dst_lbl_dir, os.path.basename(lf))
        with open(dst, "w") as f:
            f.write("\n".join(out_lines) + ("\n" if out_lines else ""))
    return mapped, dropped


def stage1_download(api_key, dst_root):
    from roboflow import Roboflow
    rf = Roboflow(api_key=api_key)
    dst_root = Path(dst_root)

    # Seed with existing data first
    base = config.DATA_DIR / "processed" / "unified_indian"
    for split in ["train", "valid", "test"]:
        for sub in ["images", "labels"]:
            (dst_root / split / sub).mkdir(parents=True, exist_ok=True)
            for f in glob.glob(str(base / split / sub / "*")):
                shutil.copy2(f, dst_root / split / sub / Path(f).name)

    total = {"train": 0, "valid": 0, "test": 0}

    for ws, proj, ver in ROBOFLOW_DATASETS:
        print(f"\n  ↓  Downloading {ws}/{proj} v{ver}…")
        tmp = f"C:/tmp/rf_{proj}"
        try:
            dataset = rf.workspace(ws).project(proj).version(ver).download(
                "yolov8", location=tmp, overwrite=True
            )
            dl_yaml = yaml.safe_load(open(f"{tmp}/data.yaml"))
            names_raw = dl_yaml.get("names", [])
            src_classes = list(names_raw.values()) if isinstance(names_raw, dict) else names_raw

            for split in ["train", "valid", "test"]:
                src_lbl = f"{tmp}/{split}/labels"
                dst_lbl = f"{tmp}/{split}/labels_remapped"
                if not os.path.exists(src_lbl):
                    continue
                m, d = remap_labels(src_lbl, dst_lbl, src_classes)
                imgs = glob.glob(f"{tmp}/{split}/images/*.jpg") + glob.glob(f"{tmp}/{split}/images/*.png")
                prefix = f"{ws}_{proj}_"
                for img in imgs:
                    stem = Path(img).stem
                    shutil.copy2(img, dst_root / split / "images" / f"{prefix}{Path(img).name}")
                    lbl = f"{dst_lbl}/{stem}.txt"
                    if os.path.exists(lbl):
                        shutil.copy2(lbl, dst_root / split / "labels" / f"{prefix}{stem}.txt")
                    else:
                        open(str(dst_root / split / "labels" / f"{prefix}{stem}.txt"), "w").close()
                total[split] += len(imgs)
                print(f"     {split}: +{len(imgs)} imgs  ({m} labels mapped, {d} dropped)")
        except Exception as e:
            print(f"     ⚠  Skipped ({e})")
            continue

    # Write data.yaml
    base_yaml = yaml.safe_load(open(str(base / "data.yaml")))
    base_yaml["path"] = str(dst_root).replace("\\", "/")
    with open(str(dst_root / "data.yaml"), "w") as f:
        yaml.dump(base_yaml, f, default_flow_style=False)

    train_imgs = len(glob.glob(str(dst_root / "train" / "images" / "*")))
    print(f"\n  ✅ Stage 1 complete. Total train images: {train_imgs}")
    return dst_root


# ════════════════════════════════════════════════════════
# STAGE 2 — AUGMENTATION
# ════════════════════════════════════════════════════════

def build_aug_pipeline():
    import albumentations as A
    return A.Compose([
        A.OneOf([A.HorizontalFlip(p=1.0), A.NoOp(p=1.0)], p=0.5),
        A.OneOf([
            A.Perspective(scale=(0.03, 0.08), p=1.0),
            A.ShiftScaleRotate(shift_limit=0.04, scale_limit=0.1, rotate_limit=5, border_mode=0, p=1.0),
            A.NoOp(p=1.0),
        ], p=0.6),
        A.OneOf([
            A.RandomBrightnessContrast(brightness_limit=0.35, contrast_limit=0.35, p=1.0),
            A.RandomGamma(gamma_limit=(60, 140), p=1.0),
            A.CLAHE(clip_limit=4.0, p=1.0),
        ], p=0.8),
        A.HueSaturationValue(hue_shift_limit=15, sat_shift_limit=30, val_shift_limit=20, p=0.5),
        A.OneOf([
            A.RandomFog(fog_coef_lower=0.1, fog_coef_upper=0.3, alpha_coef=0.08, p=1.0),
            A.RandomRain(slant_lower=-5, slant_upper=5, drop_length=8, drop_width=1,
                         drop_color=(200, 200, 200), blur_value=3,
                         brightness_coefficient=0.85, rain_type="default", p=1.0),
            A.NoOp(p=1.0),
        ], p=0.3),
        A.OneOf([
            A.GaussNoise(var_limit=(10, 50), p=1.0),
            A.ISONoise(color_shift=(0.01, 0.05), intensity=(0.1, 0.4), p=1.0),
            A.NoOp(p=1.0),
        ], p=0.3),
        A.OneOf([
            A.MotionBlur(blur_limit=(3, 7), p=1.0),
            A.GaussianBlur(blur_limit=(3, 5), p=1.0),
            A.NoOp(p=1.0),
        ], p=0.3),
    ], bbox_params=A.BboxParams(format="yolo", label_fields=["class_labels"], min_visibility=0.3))


def stage2_augment(src_root, copies=15):
    import cv2
    src_root = Path(src_root)
    dst_root = src_root.parent / (src_root.name + "_aug")
    pipeline = build_aug_pipeline()

    for split in ["train", "valid", "test"]:
        n = copies if split == "train" else 0
        src_img_dir = src_root / split / "images"
        src_lbl_dir = src_root / split / "labels"
        dst_img_dir = dst_root / split / "images"
        dst_lbl_dir = dst_root / split / "labels"
        dst_img_dir.mkdir(parents=True, exist_ok=True)
        dst_lbl_dir.mkdir(parents=True, exist_ok=True)

        imgs = sorted(glob.glob(str(src_img_dir / "*.jpg")) + glob.glob(str(src_img_dir / "*.png")))
        print(f"\n  [AUG] {split}: {len(imgs)} → {len(imgs)*(n+1)} images")

        for img_path in tqdm(imgs, desc=f"  Augmenting {split}"):
            stem = Path(img_path).stem
            ext  = Path(img_path).suffix
            lbl_path = src_lbl_dir / f"{stem}.txt"

            # Always copy original
            shutil.copy2(img_path, dst_img_dir / f"{stem}_orig{ext}")
            if lbl_path.exists():
                shutil.copy2(lbl_path, dst_lbl_dir / f"{stem}_orig.txt")
            else:
                open(str(dst_lbl_dir / f"{stem}_orig.txt"), "w").close()

            if n == 0 or not lbl_path.exists():
                continue

            boxes, classes = [], []
            for line in open(lbl_path):
                p = line.strip().split()
                if len(p) == 5:
                    cls = int(p[0]); cx,cy,w,h = map(float,p[1:])
                    boxes.append([cx,cy,w,h]); classes.append(cls)
            if not boxes:
                continue

            img = cv2.imread(img_path)
            if img is None:
                continue
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            for i in range(n):
                random.seed(42 + hash(stem) + i)
                try:
                    r = pipeline(image=img_rgb, bboxes=boxes, class_labels=classes)
                    if not r["bboxes"]:
                        continue
                    aug_img = cv2.cvtColor(r["image"], cv2.COLOR_RGB2BGR)
                    cv2.imwrite(str(dst_img_dir / f"{stem}_aug{i:02d}{ext}"), aug_img)
                    with open(str(dst_lbl_dir / f"{stem}_aug{i:02d}.txt"), "w") as f:
                        for cls, box in zip(r["class_labels"], r["bboxes"]):
                            f.write(f"{cls} {box[0]:.6f} {box[1]:.6f} {box[2]:.6f} {box[3]:.6f}\n")
                except Exception:
                    continue

    # Write data.yaml
    base_yaml = yaml.safe_load(open(str(src_root / "data.yaml")))
    base_yaml["path"] = str(dst_root).replace("\\", "/")
    with open(str(dst_root / "data.yaml"), "w") as f:
        yaml.dump(base_yaml, f, default_flow_style=False)

    train_count = len(list((dst_root / "train" / "images").glob("*")))
    val_count   = len(list((dst_root / "valid" / "images").glob("*")))
    print(f"\n  ✅ Stage 2 complete. Train: {train_count}  Val: {val_count}")
    return dst_root


# ════════════════════════════════════════════════════════
# STAGE 3 — NUCLEAR TRAINING
# ════════════════════════════════════════════════════════

def stage3_train(data_yaml_path):
    import torch
    from ultralytics import YOLO

    print(f"\n  GPU: {torch.cuda.get_device_name(0)}")
    print(f"  VRAM: {torch.cuda.get_device_properties(0).total_memory/1e9:.1f} GB")

    model = YOLO("yolov8m.pt")   # Medium: 25M params, far better than Small

    train_args = {
        "data":          str(data_yaml_path),
        "epochs":        500,
        "imgsz":         832,         # >640 captures small autos & distant vehicles
        "batch":         8,           # Safe for 6GB VRAM at 832px with v8m
        "device":        0 if torch.cuda.is_available() else "cpu",
        "workers":       4,
        "project":       str(config.OUTPUTS_DIR),
        "name":          "yolo_nuclear_v8m",
        "exist_ok":      True,
        "pretrained":    True,
        "optimizer":     "AdamW",
        "lr0":           0.001,
        "lrf":           0.01,
        "momentum":      0.937,
        "weight_decay":  0.0005,
        "warmup_epochs": 5.0,
        "patience":      75,          # Stop if no improvement for 75 epochs
        "save":          True,
        "save_period":   25,
        "plots":         True,
        # Advanced augmentation (in addition to our albumentations preprocessing)
        "mosaic":        1.0,
        "mixup":         0.15,
        "copy_paste":    0.1,
        "hsv_h":         0.015,
        "hsv_s":         0.7,
        "hsv_v":         0.4,
        "degrees":       5.0,
        "translate":     0.1,
        "scale":         0.5,
        "flipud":        0.0,
        "fliplr":        0.5,
        # Box/cls loss weights (slightly more cls weight for 24 classes)
        "box":           7.5,
        "cls":           0.8,
        "dfl":           1.5,
    }

    print("\n  Starting nuclear training run…")
    print(f"  Model:   YOLOv8m (25M params)")
    print(f"  Image:   {train_args['imgsz']}px")
    print(f"  Epochs:  up to {train_args['epochs']} (patience={train_args['patience']})")
    print(f"  Data:    {data_yaml_path}")

    t0 = time.time()
    results = model.train(**train_args)
    elapsed = (time.time() - t0) / 60

    best_src = config.OUTPUTS_DIR / "yolo_nuclear_v8m" / "weights" / "best.pt"
    best_dst = config.MODELS_DIR / "yolo" / "best.pt"
    if best_src.exists():
        os.makedirs(best_dst.parent, exist_ok=True)
        shutil.copy2(best_src, best_dst)
        print(f"\n  ✅ Best model copied → {best_dst}")

    print(f"\n{'='*60}")
    print(f"  Nuclear training complete in {elapsed:.1f} mins")
    print(f"  mAP50:    {results.results_dict.get('metrics/mAP50(B)', 'N/A'):.4f}")
    print(f"  mAP50-95: {results.results_dict.get('metrics/mAP50-95(B)', 'N/A'):.4f}")


# ════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="TrafficSense Full Pipeline")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--skip-download", action="store_true",
                        help="Skip Roboflow download (use existing merged dataset)")
    parser.add_argument("--skip-augment", action="store_true",
                        help="Skip augmentation (go straight to training)")
    args = parser.parse_args()

    print("=" * 60)
    print("  TrafficSense: Full Dataset + Training Pipeline")
    print("=" * 60)

    merged_root = config.DATA_DIR / "processed" / "unified_indian_merged"
    aug_root    = config.DATA_DIR / "processed" / "unified_indian_merged_aug"

    # ── Stage 1 ──────────────────────────────────────────
    if not args.skip_download:
        print("\n[STAGE 1/3] Downloading datasets from Roboflow…")
        stage1_download(args.api_key, merged_root)
    else:
        print("\n[STAGE 1/3] Skipped (--skip-download)")

    # ── Stage 2 ──────────────────────────────────────────
    if not args.skip_augment:
        print("\n[STAGE 2/3] Augmenting dataset (×15)…")
        aug_root = stage2_augment(merged_root, copies=15)
    else:
        print("\n[STAGE 2/3] Skipped (--skip-augment)")
        if not aug_root.exists():
            aug_root = merged_root

    data_yaml = aug_root / "data.yaml"

    # ── Stage 3 ──────────────────────────────────────────
    print("\n[STAGE 3/3] Nuclear training run (this will take hours)…")
    stage3_train(data_yaml)


if __name__ == "__main__":
    main()
