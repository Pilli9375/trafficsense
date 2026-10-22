"""IDD Detection (Pascal VOC) -> YOLO labels, following docs/perception.md sections 2-4.

Images are not copied: the output folder holds `images` (a symlink to the dataset's
JPEGImages), `labels/` mirroring its layout, one image list per split and data.yaml.
Ultralytics finds a label by replacing the last `/images/` in the image path with
`/labels/`, which is why the image lists go through the `images` symlink.
"""
from __future__ import annotations

import json
import random
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterable

# Our classes, in YOLO index order (docs/perception.md section 2).
CLASSES: tuple[str, ...] = ("car", "motorcycle", "autorickshaw", "bus", "truck", "bicycle", "person")

# Every IDD class must be listed; None = dropped. An unknown name raises.
IDD_TO_OURS: dict[str, str | None] = {
    "car": "car",
    "motorcycle": "motorcycle",
    "autorickshaw": "autorickshaw",
    "bus": "bus",
    "truck": "truck",
    "bicycle": "bicycle",
    "person": "person",
    "rider": None,
    "vehicle fallback": None,
    "caravan": None,
    "trailer": None,
    "train": None,
    "animal": None,
    "traffic sign": None,
    "traffic light": None,
}

CAMERA_GROUPS = ("frontFar", "frontNear", "highquality_16k", "rearNear", "sideLeft", "sideRight")

# our split -> official split it is drawn from (section 3). Official test has no labels.
SPLIT_SOURCES = {"train": "train", "val": "train", "test": "val"}


def parse_voc(path: Path) -> tuple[int, int, list[tuple[str, float, float, float, float]]]:
    """Return (width, height, [(name, xmin, ymin, xmax, ymax), ...]) from one VOC XML."""
    root = ET.parse(path).getroot()
    size = root.find("size")
    if size is None:
        raise ValueError(f"{path}: no <size>")
    w, h = int(size.findtext("width")), int(size.findtext("height"))
    if w <= 0 or h <= 0:
        raise ValueError(f"{path}: invalid size {w}x{h}")
    objs = []
    for o in root.iter("object"):
        b = o.find("bndbox")
        if b is None:
            raise ValueError(f"{path}: object without <bndbox>")
        objs.append((o.findtext("name"), *(float(b.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax"))))
    return w, h, objs


def convert_objects(w: int, h: int, objs: Iterable[tuple[str, float, float, float, float]]
                    ) -> tuple[list[str], Counter]:
    """Map, clip and normalise boxes. Returns (YOLO label lines, stats counter)."""
    lines: list[str] = []
    stats: Counter = Counter()
    for name, x0, y0, x1, y1 in objs:
        if name not in IDD_TO_OURS:
            raise ValueError(f"Unknown IDD class {name!r}; add it to IDD_TO_OURS deliberately")
        ours = IDD_TO_OURS[name]
        if ours is None:
            stats[f"dropped_class:{name}"] += 1
            continue
        cx0, cy0, cx1, cy1 = max(0.0, x0), max(0.0, y0), min(float(w), x1), min(float(h), y1)
        if cx1 - cx0 < 1 or cy1 - cy0 < 1:
            stats["dropped_degenerate"] += 1
            continue
        if (cx0, cy0, cx1, cy1) != (x0, y0, x1, y1):
            stats["clipped"] += 1
        stats[f"box:{ours}"] += 1
        lines.append(f"{CLASSES.index(ours)} {(cx0 + cx1) / 2 / w:.6f} {(cy0 + cy1) / 2 / h:.6f} "
                     f"{(cx1 - cx0) / w:.6f} {(cy1 - cy0) / h:.6f}")
    return lines, stats


def read_split_ids(idd_root: Path, split: str) -> list[str]:
    p = idd_root / f"{split}.txt"
    if not p.is_file():
        raise FileNotFoundError(f"IDD split list not found: {p}")
    ids = [line.strip() for line in p.read_text().splitlines() if line.strip()]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{p} contains duplicate ids")
    return ids


def sequence_of(image_id: str) -> str:
    """'frontFar/BLR-..._frontFar/000702_r' -> 'frontFar/BLR-..._frontFar'."""
    return image_id.rsplit("/", 1)[0]


def holdout_sequences(ids: Iterable[str], fraction: float, seed: int) -> list[str]:
    """Per camera group, sample max(1, round(fraction * n)) sequences (sorted, seeded)."""
    if not 0 < fraction < 1:
        raise ValueError(f"val fraction must be in (0, 1), got {fraction}")
    by_group: dict[str, set[str]] = {}
    for i in ids:
        seq = sequence_of(i)
        group = seq.split("/", 1)[0]
        if group not in CAMERA_GROUPS:
            raise ValueError(f"Unknown camera group {group!r} in id {i!r}")
        by_group.setdefault(group, set()).add(seq)
    rng = random.Random(seed)
    chosen: list[str] = []
    for group in CAMERA_GROUPS:
        seqs = sorted(by_group.get(group, ()))
        if seqs:
            chosen += sorted(rng.sample(seqs, max(1, round(fraction * len(seqs)))))
    return chosen


def our_splits(idd_root: Path, val_fraction: float, seed: int) -> tuple[dict[str, list[str]], list[str]]:
    """Return ({our split: ids}, held-out val sequences)."""
    official_train = read_split_ids(idd_root, "train")
    val_seqs = holdout_sequences(official_train, val_fraction, seed)
    held = set(val_seqs)
    splits = {
        "train": [i for i in official_train if sequence_of(i) not in held],
        "val": [i for i in official_train if sequence_of(i) in held],
        "test": read_split_ids(idd_root, "val"),
    }
    return splits, val_seqs


def label_path_for(image_path: str) -> str:
    """The label path Ultralytics derives from an image path (its img2label_paths rule)."""
    sa, sb = "/images/", "/labels/"
    return sb.join(image_path.rsplit(sa, 1)).rsplit(".", 1)[0] + ".txt"


def convert(idd_root: Path, out_dir: Path, val_fraction: float, seed: int, workers: int = 32,
            images_dir: Path | None = None) -> dict:
    """Write labels, image lists, data.yaml and conversion_report.json to out_dir.

    images_dir: the JPEGImages tree the image lists point to (default: the original one in
    idd_root; the resized copy from scripts/resize_idd.py has the same layout).
    """
    idd_root = idd_root.resolve()
    if not (idd_root / "JPEGImages").is_dir() or not (idd_root / "Annotations").is_dir():
        raise FileNotFoundError(f"{idd_root} is not an IDD_Detection folder (JPEGImages/ and Annotations/)")
    images_src = (images_dir or idd_root / "JPEGImages").resolve()
    if not images_src.is_dir():
        raise FileNotFoundError(f"Image folder not found: {images_src}")
    out_dir.mkdir(parents=True, exist_ok=True)

    link = out_dir / "images"
    if link.is_symlink():
        if link.resolve() != images_src:   # our own link from an earlier run: retarget it
            link.unlink()
            link.symlink_to(images_src, target_is_directory=True)
    elif link.exists():
        raise FileExistsError(f"{link} exists and is not a symlink; refusing to touch it")
    else:
        link.symlink_to(images_src, target_is_directory=True)

    splits, val_seqs = our_splits(idd_root, val_fraction, seed)

    def one(image_id: str) -> tuple[Counter, int]:
        img = images_src / f"{image_id}.jpg"
        if not img.is_file():
            raise FileNotFoundError(f"Image listed in split but missing: {img}")
        w, h, objs = parse_voc(idd_root / "Annotations" / f"{image_id}.xml")
        lines, stats = convert_objects(w, h, objs)
        lbl = out_dir / "labels" / f"{image_id}.txt"
        lbl.parent.mkdir(parents=True, exist_ok=True)
        lbl.write_text("".join(f"{line}\n" for line in lines))
        stats["source_boxes"] += len(objs)
        return stats, len(lines)

    report: dict = {"source": str(idd_root), "images": str(images_src), "classes": list(CLASSES), "mapping": IDD_TO_OURS,
                    "val_fraction": val_fraction, "split_seed": seed, "splits": {}}
    for split, ids in splits.items():
        with ThreadPoolExecutor(workers) as ex:
            results = list(ex.map(one, ids))
        total: Counter = Counter()
        for stats, _ in results:
            total.update(stats)
        report["splits"][split] = {
            "official_split": SPLIT_SOURCES[split],
            "images": len(ids),
            "sequences": len({sequence_of(i) for i in ids}),
            "background_images": sum(n == 0 for _, n in results),
            "boxes": {c: total[f"box:{c}"] for c in CLASSES},
            "boxes_total": sum(total[f"box:{c}"] for c in CLASSES),
            "source_boxes": total["source_boxes"],
            "dropped_by_class": {k.split(":", 1)[1]: v for k, v in sorted(total.items())
                                 if k.startswith("dropped_class:")},
            "dropped_degenerate": total["dropped_degenerate"],
            "clipped": total["clipped"],
        }
        (out_dir / f"{split}.txt").write_text("".join(f"./images/{i}.jpg\n" for i in ids))

    (out_dir / "val_sequences.txt").write_text("".join(f"{s}\n" for s in val_seqs))
    data_yaml = [f"# Generated by scripts/prepare_idd.py. Images: {images_src}",
                 f"path: {out_dir.resolve()}", "train: train.txt", "val: val.txt", "test: test.txt",
                 "names:"] + [f"  {i}: {c}" for i, c in enumerate(CLASSES)]
    (out_dir / "data.yaml").write_text("\n".join(data_yaml) + "\n")
    (out_dir / "conversion_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report
