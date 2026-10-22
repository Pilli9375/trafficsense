"""Make a resized copy of the IDD images used by our splits (docs/perception.md section 6).

    python scripts/resize_idd.py [--config configs/default.yaml] [--workers 8]

Reads paths.idd_root/JPEGImages (never modified) and writes paths.idd_resized/JPEGImages with
the same layout: long side perception.resize.long_side (aspect kept, never upscaled), Pillow
BOX filter (area averaging, like OpenCV's INTER_AREA that Ultralytics uses to shrink),
JPEG quality perception.resize.jpeg_quality, no EXIF. YOLO labels are normalised by the
original size, so they stay valid. Resumable: existing outputs are kept (each file is
written to a temporary name and renamed, so a partial file never looks finished). At the end
every output is checked for its expected size and a manifest with provenance is written.
"""
import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from PIL import Image

from trafficsense.config import load_config, resolve_path
from trafficsense.experiment import git_info
from trafficsense.perception import idd


def target_size(w: int, h: int, long_side: int) -> tuple[int, int]:
    s = min(1.0, long_side / max(w, h))
    return max(1, round(w * s)), max(1, round(h * s))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    cfg = load_config(args.config)
    rcfg = cfg["perception"]["resize"]
    long_side, quality = int(rcfg["long_side"]), int(rcfg["jpeg_quality"])
    src_root = resolve_path(cfg, "idd_root").resolve()
    dst_root = resolve_path(cfg, "idd_resized")
    if not dst_root.exists():
        raise FileNotFoundError(f"{dst_root} not found. Create the folder on D and link it: "
                                f"ln -s <...>/IDD_Detection_640 {dst_root}")
    dst_root = dst_root.resolve()
    if dst_root == src_root:
        raise ValueError("idd_resized must not be the original dataset folder")
    git = git_info()

    splits, _ = idd.our_splits(src_root, float(cfg["perception"]["val_fraction"]),
                               int(cfg["perception"]["split_seed"]))
    ids = sorted({i for ids in splits.values() for i in ids})   # sorted = folder order on disk

    def one(image_id: str) -> str:
        dst = dst_root / "JPEGImages" / f"{image_id}.jpg"
        if dst.is_file():
            return "kept"
        with Image.open(src_root / "JPEGImages" / f"{image_id}.jpg") as im:
            im = im.convert("RGB")
            out = im.resize(target_size(*im.size, long_side), Image.BOX)
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".part")
        out.save(tmp, format="JPEG", quality=quality)
        os.replace(tmp, dst)
        return "written"

    t0 = time.time()
    counts = {"written": 0, "kept": 0}
    with ThreadPoolExecutor(args.workers) as ex:
        for k, r in enumerate(ex.map(one, ids), 1):
            counts[r] += 1
            if k % 2000 == 0:
                print(f"{k}/{len(ids)} ({counts['written']} written) {time.time() - t0:.0f}s", flush=True)

    # Check every output: decodable header and the expected size.
    def check(image_id: str) -> int:
        with Image.open(src_root / "JPEGImages" / f"{image_id}.jpg") as a, \
                Image.open(dst_root / "JPEGImages" / f"{image_id}.jpg") as b:
            if b.size != target_size(*a.size, long_side):
                raise RuntimeError(f"{image_id}: resized to {b.size}, expected {target_size(*a.size, long_side)}")
        return (dst_root / "JPEGImages" / f"{image_id}.jpg").stat().st_size

    with ThreadPoolExecutor(32) as ex:
        nbytes = sum(ex.map(check, ids))
    manifest = {"source": str(src_root / "JPEGImages"), "dest": str(dst_root / "JPEGImages"),
                "images": len(ids), "bytes": nbytes, "long_side": long_side, "jpeg_quality": quality,
                "filter": "PIL BOX", "this_run": counts, "seconds": round(time.time() - t0),
                "provenance": {"script": "scripts/resize_idd.py", "git_commit": git["commit"],
                               "git_dirty": git["dirty"],
                               "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds")}}
    (dst_root / "resize_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    out = resolve_path(cfg, "perception_outputs")
    out.mkdir(parents=True, exist_ok=True)
    (out / "idd_resize.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"checked {len(ids)} images, {nbytes / 1e9:.2f} GB, {counts}")


if __name__ == "__main__":
    main()
