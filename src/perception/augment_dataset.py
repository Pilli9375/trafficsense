"""
TrafficSense: Heavy Augmentation Pipeline
==========================================
Turns 120 training images -> 2,400+ synthetic variants using
albumentations. This is the minimum viable dataset fix while
we wait for a proper Roboflow download.

Each original image generates N augmented copies with randomized:
- Brightness/contrast/saturation (simulate day/night/overcast)
- Motion blur (simulate dashcam shake)
- Rain + fog overlays (Indian monsoon conditions)
- Horizontal flip
- Perspective warp (simulate different camera angles)
- Random crops (simulate partial view occlusion)
"""

import os
import sys
import shutil
import glob
import random
from pathlib import Path
from tqdm import tqdm

import cv2
import numpy as np
import albumentations as A

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src import config

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
COPIES_PER_IMAGE = 20          # 120 imgs × 20 = 2,400 total
RANDOM_SEED = 42
AUG_OUTPUT_DIR = config.DATA_DIR / "processed" / "unified_indian_aug"

# ─────────────────────────────────────────────
# Augmentation Pipeline
# ─────────────────────────────────────────────
def build_pipeline():
    return A.Compose([
        # ── Spatial transforms ────────────────
        A.OneOf([
            A.HorizontalFlip(p=1.0),
            A.NoOp(p=1.0),
        ], p=0.5),

        A.OneOf([
            A.Perspective(scale=(0.03, 0.08), p=1.0),
            A.ShiftScaleRotate(shift_limit=0.04, scale_limit=0.1, rotate_limit=5, border_mode=0, p=1.0),
        ], p=0.6),

        A.RandomResizedCrop(height=640, width=640, scale=(0.75, 1.0), ratio=(0.9, 1.1), p=0.3),

        # ── Lighting / weather ────────────────
        A.OneOf([
            A.RandomBrightnessContrast(brightness_limit=0.35, contrast_limit=0.35, p=1.0),
            A.RandomGamma(gamma_limit=(60, 140), p=1.0),
            A.CLAHE(clip_limit=4.0, tile_grid_size=(8, 8), p=1.0),
        ], p=0.8),

        A.HueSaturationValue(hue_shift_limit=15, sat_shift_limit=30, val_shift_limit=20, p=0.5),

        A.OneOf([
            A.RandomFog(fog_coef_lower=0.1, fog_coef_upper=0.35, alpha_coef=0.08, p=1.0),
            A.RandomRain(slant_lower=-5, slant_upper=5, drop_length=10, drop_width=1, drop_color=(200, 200, 200), blur_value=3, brightness_coefficient=0.85, rain_type="default", p=1.0),
            A.RandomSunFlare(flare_roi=(0, 0, 1, 0.5), angle_lower=0, angle_upper=1, num_flare_circles_lower=3, num_flare_circles_upper=6, src_radius=80, src_color=(255, 255, 200), p=1.0),
            A.NoOp(p=1.0),
        ], p=0.4),

        A.OneOf([
            A.GaussNoise(var_limit=(10, 60), p=1.0),
            A.ISONoise(color_shift=(0.01, 0.05), intensity=(0.1, 0.5), p=1.0),
        ], p=0.35),

        # ── Blur / compression ────────────────
        A.OneOf([
            A.MotionBlur(blur_limit=(3, 7), p=1.0),
            A.GaussianBlur(blur_limit=(3, 5), p=1.0),
            A.ImageCompression(quality_lower=60, quality_upper=95, p=1.0),
            A.NoOp(p=1.0),
        ], p=0.4),

    ], bbox_params=A.BboxParams(format="yolo", label_fields=["class_labels"], min_visibility=0.3))


# ─────────────────────────────────────────────
# YOLO label helpers
# ─────────────────────────────────────────────
def read_yolo_labels(label_path):
    boxes, classes = [], []
    if not os.path.exists(label_path):
        return boxes, classes
    with open(label_path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) == 5:
                cls = int(parts[0])
                cx, cy, w, h = map(float, parts[1:])
                boxes.append([cx, cy, w, h])
                classes.append(cls)
    return boxes, classes


def write_yolo_labels(label_path, boxes, classes):
    with open(label_path, "w") as f:
        for cls, box in zip(classes, boxes):
            f.write(f"{cls} {box[0]:.6f} {box[1]:.6f} {box[2]:.6f} {box[3]:.6f}\n")


# ─────────────────────────────────────────────
# Augment a single split
# ─────────────────────────────────────────────
def augment_split(src_split_dir, dst_split_dir, n_copies, pipeline):
    src_img_dir = Path(src_split_dir) / "images"
    src_lbl_dir = Path(src_split_dir) / "labels"
    dst_img_dir = Path(dst_split_dir) / "images"
    dst_lbl_dir = Path(dst_split_dir) / "labels"
    dst_img_dir.mkdir(parents=True, exist_ok=True)
    dst_lbl_dir.mkdir(parents=True, exist_ok=True)

    image_files = sorted(glob.glob(str(src_img_dir / "*.jpg")) +
                         glob.glob(str(src_img_dir / "*.png")) +
                         glob.glob(str(src_img_dir / "*.jpeg")))

    print(f"\n[AUG] {src_split_dir.split(os.sep)[-2]} split: {len(image_files)} images → {len(image_files) * (n_copies + 1)} total")

    for img_path in tqdm(image_files, desc="Augmenting"):
        stem = Path(img_path).stem
        ext = Path(img_path).suffix
        lbl_path = str(src_lbl_dir / f"{stem}.txt")

        img = cv2.imread(img_path)
        if img is None:
            continue
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = img_rgb.shape[:2]
        boxes, classes = read_yolo_labels(lbl_path)

        # Always copy original
        shutil.copy2(img_path, dst_img_dir / f"{stem}_orig{ext}")
        if boxes:
            write_yolo_labels(str(dst_lbl_dir / f"{stem}_orig.txt"), boxes, classes)
        else:
            open(str(dst_lbl_dir / f"{stem}_orig.txt"), "w").close()

        if not boxes:
            continue  # no point augmenting background images with no labels

        for i in range(n_copies):
            random.seed(RANDOM_SEED + hash(stem) + i)
            try:
                result = pipeline(image=img_rgb, bboxes=boxes, class_labels=classes)
            except Exception:
                continue

            aug_img = cv2.cvtColor(result["image"], cv2.COLOR_RGB2BGR)
            aug_boxes = result["bboxes"]
            aug_classes = result["class_labels"]

            if not aug_boxes:
                continue  # discard augmentation if all boxes were cropped out

            out_img = dst_img_dir / f"{stem}_aug{i:02d}{ext}"
            out_lbl = dst_lbl_dir / f"{stem}_aug{i:02d}.txt"
            cv2.imwrite(str(out_img), aug_img)
            write_yolo_labels(str(out_lbl), list(aug_boxes), list(aug_classes))


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    print("=" * 60)
    print("TrafficSense: Dataset Augmentation Pipeline")
    print("=" * 60)

    src_root = config.DATA_DIR / "processed" / "unified_indian"
    dst_root = AUG_OUTPUT_DIR

    pipeline = build_pipeline()

    # Augment train heavily
    augment_split(str(src_root / "train"), str(dst_root / "train"), COPIES_PER_IMAGE, pipeline)
    # Valid / test: only copy original (no augmentation on eval sets)
    augment_split(str(src_root / "valid"), str(dst_root / "valid"), 0, A.Compose([], bbox_params=A.BboxParams(format="yolo", label_fields=["class_labels"])))
    augment_split(str(src_root / "test"),  str(dst_root / "test"),  0, A.Compose([], bbox_params=A.BboxParams(format="yolo", label_fields=["class_labels"])))

    # Write data.yaml for augmented dataset
    import yaml
    src_yaml = yaml.safe_load(open(str(src_root / "data.yaml")))
    src_yaml["path"] = str(dst_root).replace("\\", "/")
    with open(str(dst_root / "data.yaml"), "w") as f:
        yaml.dump(src_yaml, f, default_flow_style=False)

    # Count results
    train_count = len(list((dst_root / "train" / "images").glob("*")))
    val_count = len(list((dst_root / "valid" / "images").glob("*")))
    print(f"\n{'=' * 60}")
    print(f"Augmentation complete!")
    print(f"  Train: {train_count} images")
    print(f"  Valid: {val_count} images")
    print(f"  Dataset saved to: {dst_root}")


if __name__ == "__main__":
    main()
