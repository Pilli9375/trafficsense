"""
TrafficSense: Roboflow Dataset Downloader
==========================================
Downloads high-quality Indian traffic datasets from Roboflow Universe.
These datasets contain 1,000–9,000 properly annotated images each.

Usage:
    python src/perception/download_datasets.py --api-key YOUR_KEY_HERE

Get your free API key at: https://roboflow.com → Settings → API Key
"""

import os
import sys
import shutil
import argparse
import yaml
import glob
from pathlib import Path
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from src import config

# ─────────────────────────────────────────────
# Class remapping: Roboflow → our 24 classes
# ─────────────────────────────────────────────
OUR_CLASSES = [
    'car', 'motorcycle', 'bus', 'truck', 'autorickshaw', 'bicycle',
    'ambulance', 'police_vehicle', 'tractor', 'pedestrian', 'traffic_light',
    'traffic_sign', 'scooter', 'e-rickshaw', 'van', 'tempo', 'animal',
    'pushcart', 'water_tanker', 'excavator', 'crane', 'jeep', 'mini_bus', 'fire_engine'
]
CLASS_INDEX = {c: i for i, c in enumerate(OUR_CLASSES)}

# Roboflow dataset class → our class name (best-effort mapping)
REMAP = {
    # Common vehicle names
    'car': 'car', 'cars': 'car', 'sedan': 'car', 'hatchback': 'car',
    'suv': 'car', 'cab': 'car', 'taxi': 'car',
    'motorcycle': 'motorcycle', 'motorbike': 'motorcycle', 'bike': 'motorcycle',
    'two-wheeler': 'motorcycle', 'two wheeler': 'motorcycle',
    'bus': 'bus', 'school bus': 'bus', 'minibus': 'mini_bus',
    'truck': 'truck', 'lorry': 'truck', 'mini-truck': 'truck',
    'autorickshaw': 'autorickshaw', 'auto': 'autorickshaw',
    'auto-rickshaw': 'autorickshaw', 'auto rickshaw': 'autorickshaw',
    'rickshaw': 'autorickshaw', 'three-wheeler': 'autorickshaw',
    'bicycle': 'bicycle', 'cycle': 'bicycle',
    'ambulance': 'ambulance',
    'police': 'police_vehicle', 'police car': 'police_vehicle',
    'police-van': 'police_vehicle',
    'tractor': 'tractor',
    'pedestrian': 'pedestrian', 'person': 'pedestrian', 'people': 'pedestrian',
    'traffic light': 'traffic_light', 'traffic-light': 'traffic_light',
    'traffic_light': 'traffic_light', 'signal': 'traffic_light',
    'traffic sign': 'traffic_sign', 'sign': 'traffic_sign',
    'scooter': 'scooter', 'scooty': 'scooter',
    'e-rickshaw': 'e-rickshaw', 'e rickshaw': 'e-rickshaw', 'erickshaw': 'e-rickshaw',
    'van': 'van', 'minivan': 'van',
    'tempo': 'tempo', 'tempo traveller': 'tempo',
    'animal': 'animal', 'cow': 'animal', 'dog': 'animal', 'cattle': 'animal',
    'pushcart': 'pushcart', 'cart': 'pushcart', 'handcart': 'pushcart',
    'water tanker': 'water_tanker', 'tanker': 'water_tanker',
    'excavator': 'excavator', 'jcb': 'excavator',
    'crane': 'crane',
    'jeep': 'jeep',
    'fire engine': 'fire_engine', 'fire truck': 'fire_engine',
    'fire-engine': 'fire_engine',
}

# ─────────────────────────────────────────────
# Target datasets (workspace, project, version)
# ─────────────────────────────────────────────
DATASETS = [
    # Indian vehicle detection datasets
    ("rahul-gupta27", "indian-vehicle-detection", 3),
    ("roboflow-100", "vehicles-q0x2v",            2),
    ("vit-university", "indian-traffic-1",         1),
    ("roboflow-100", "indian-traffic-sign",        1),
]

def remap_labels(src_labels_dir, dst_labels_dir, src_classes):
    """Remap class IDs from a downloaded dataset to our 24-class scheme."""
    os.makedirs(dst_labels_dir, exist_ok=True)
    label_files = glob.glob(os.path.join(src_labels_dir, "*.txt"))
    mapped = 0
    dropped = 0
    for lf in label_files:
        out_lines = []
        with open(lf) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) != 5:
                    continue
                cls_id = int(parts[0])
                if cls_id >= len(src_classes):
                    dropped += 1
                    continue
                raw_name = src_classes[cls_id].lower().strip()
                our_name = REMAP.get(raw_name)
                if our_name is None:
                    dropped += 1
                    continue
                our_id = CLASS_INDEX[our_name]
                out_lines.append(f"{our_id} " + " ".join(parts[1:]))
                mapped += 1
        dst_lf = os.path.join(dst_labels_dir, os.path.basename(lf))
        with open(dst_lf, "w") as f:
            f.write("\n".join(out_lines) + "\n" if out_lines else "")
    return mapped, dropped


def merge_into_unified(src_root, split, dst_root):
    """Copy images and remapped labels into the unified dataset."""
    src_img = os.path.join(src_root, split, "images")
    src_lbl = os.path.join(src_root, split, "labels_remapped")
    dst_img = dst_root / split / "images"
    dst_lbl = dst_root / split / "labels"
    dst_img.mkdir(parents=True, exist_ok=True)
    dst_lbl.mkdir(parents=True, exist_ok=True)

    imgs = glob.glob(f"{src_img}/*.jpg") + glob.glob(f"{src_img}/*.png")
    for img_path in imgs:
        stem = Path(img_path).stem
        lbl_path = os.path.join(src_lbl, f"{stem}.txt")
        shutil.copy2(img_path, dst_img / Path(img_path).name)
        if os.path.exists(lbl_path):
            shutil.copy2(lbl_path, dst_lbl / f"{stem}.txt")
        else:
            open(str(dst_lbl / f"{stem}.txt"), "w").close()
    return len(imgs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key", required=True, help="Roboflow API key")
    args = parser.parse_args()

    from roboflow import Roboflow
    rf = Roboflow(api_key=args.api_key)

    # Start with existing unified_indian data as base
    base_src = config.DATA_DIR / "processed" / "unified_indian"
    dst_root = config.DATA_DIR / "processed" / "unified_indian_full"
    dst_root.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Copying existing dataset as base...")
    print("=" * 60)
    for split in ["train", "valid", "test"]:
        for subdir in ["images", "labels"]:
            src = base_src / split / subdir
            dst = dst_root / split / subdir
            dst.mkdir(parents=True, exist_ok=True)
            for f in glob.glob(str(src / "*")):
                shutil.copy2(f, dst / Path(f).name)

    total_added = 0
    for workspace, project_name, version in DATASETS:
        print(f"\n{'─'*60}")
        print(f"Downloading: {workspace}/{project_name} v{version}")
        try:
            project = rf.workspace(workspace).project(project_name)
            dataset = project.version(version).download("yolov8", location=f"/tmp/rf_{project_name}")

            # Read classes from downloaded data.yaml
            dl_yaml = yaml.safe_load(open(f"/tmp/rf_{project_name}/data.yaml"))
            src_classes = list(dl_yaml.get("names", {}).values()) if isinstance(dl_yaml["names"], dict) else dl_yaml["names"]
            print(f"  Source classes: {src_classes}")

            for split in ["train", "valid", "test"]:
                src_lbl_dir = f"/tmp/rf_{project_name}/{split}/labels"
                dst_lbl_remap = f"/tmp/rf_{project_name}/{split}/labels_remapped"
                if not os.path.exists(src_lbl_dir):
                    continue
                mapped, dropped = remap_labels(src_lbl_dir, dst_lbl_remap, src_classes)
                added = merge_into_unified(f"/tmp/rf_{project_name}", split, dst_root)
                total_added += added if split == "train" else 0
                print(f"  {split}: +{added} images ({mapped} labels mapped, {dropped} dropped)")

        except Exception as e:
            print(f"  WARNING: Failed to download {project_name}: {e}")
            continue

    # Write final data.yaml
    src_yaml = yaml.safe_load(open(str(base_src / "data.yaml")))
    src_yaml["path"] = str(dst_root).replace("\\", "/")
    with open(str(dst_root / "data.yaml"), "w") as f:
        yaml.dump(src_yaml, f, default_flow_style=False)

    # Final counts
    train_imgs = len(glob.glob(str(dst_root / "train" / "images" / "*")))
    val_imgs   = len(glob.glob(str(dst_root / "valid" / "images" / "*")))
    print(f"\n{'=' * 60}")
    print(f"Dataset download + merge complete!")
    print(f"  Train: {train_imgs} images (was 120)")
    print(f"  Valid: {val_imgs} images (was 30)")
    print(f"  Saved to: {dst_root}")
    print(f"\nNext: run python src/perception/train_yolo_nuclear.py")


if __name__ == "__main__":
    main()
