"""Measure how fast training images can be read from their storage (CPU only, GPU hidden).

    python scripts/bench_image_io.py [--workers 2 4 6 8] [--batches 75] [--threads 1 2 4 8 16]

1. Raw reads: whole files read with N threads, each run on its own random sample of
   test-split images (not read by the Ultralytics label scan, so not warmed by it).
2. Ultralytics training pipeline: YOLODataset of our train split with the training
   augmentations (mosaic etc., imgsz from config, batch 8), through a torch DataLoader
   with `workers` processes. Each run gets its own shuffle seed, so runs read mostly
   different files (Ultralytics' own loader shuffles with a fixed seed, which would make
   later runs read files the earlier ones had just pulled into the Windows file cache).
   Throughput = images per second over --batches batches, after the first batch.
3. Cache check: raw reads of train images that the label scan just read, compared with (1).

Building the train dataset the first time scans every image (Ultralytics' label check) and
writes a .cache next to the labels; that one-time cost is timed and reported as well.
Results: paths.perception_outputs/io_bench.json.
"""
import os

os.environ["CUDA_VISIBLE_DEVICES"] = ""   # before torch is imported: never touch the GPU

import argparse
import json
import random
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import torch
from torch.utils.data import DataLoader, RandomSampler

from trafficsense.config import load_config, resolve_path
from trafficsense.experiment import git_info


def image_paths(yolo: Path, split: str) -> list[Path]:
    return [yolo / line[2:] for line in (yolo / f"{split}.txt").read_text().split()]


def raw_reads(paths: list[Path], threads: int) -> dict:
    def rd(p):
        with open(p, "rb") as f:
            return len(f.read())
    t = time.perf_counter()
    with ThreadPoolExecutor(threads) as ex:
        nbytes = sum(ex.map(rd, paths))
    dt = time.perf_counter() - t
    return {"threads": threads, "images": len(paths), "seconds": round(dt, 2),
            "img_per_s": round(len(paths) / dt, 1), "mb_per_s": round(nbytes / 1e6 / dt, 2)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--threads", type=int, nargs="+", default=[1, 2, 4, 8, 16])
    ap.add_argument("--raw-n", type=int, default=300, help="images per raw-read run")
    ap.add_argument("--workers", type=int, nargs="+", default=[2, 4, 6, 8])
    ap.add_argument("--batches", type=int, default=75)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    if torch.cuda.is_available():
        raise RuntimeError("GPU visible despite CUDA_VISIBLE_DEVICES=''; refusing to run")

    from ultralytics.cfg import get_cfg
    from ultralytics.data import build_yolo_dataset
    from ultralytics.data.utils import check_det_dataset

    cfg = load_config(args.config)
    yolo = resolve_path(cfg, "idd_yolo")
    imgsz = int(cfg["perception"]["imgsz"])
    rng = random.Random(args.seed)
    result = {"image_dir": str((yolo / "images").resolve()), "provenance": {
        "script": "scripts/bench_image_io.py", **{f"git_{k}": v for k, v in git_info().items()},
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds")}}

    # 1. Raw reads on untouched test-split images, a fresh sample per run.
    test = image_paths(yolo, "test")
    rng.shuffle(test)
    result["raw_cold"] = []
    for k, n in enumerate(args.threads):
        r = raw_reads(test[k * args.raw_n:(k + 1) * args.raw_n], n)
        result["raw_cold"].append(r)
        print("raw cold", r, flush=True)

    # 2. Ultralytics training pipeline.
    data = check_det_dataset(str(yolo / "data.yaml"))
    ucfg = get_cfg(overrides={"imgsz": imgsz, "batch": args.batch, "task": "detect", "mode": "train"})
    t = time.perf_counter()
    ds = build_yolo_dataset(ucfg, data["train"], args.batch, data, mode="train", rect=False, stride=32)
    result["dataset_build_s"] = round(time.perf_counter() - t, 1)
    print(f"train dataset: {len(ds)} images, built in {result['dataset_build_s']} s", flush=True)

    result["dataloader"] = []
    for w in args.workers:
        g = torch.Generator().manual_seed(rng.randrange(2**31))
        dl = DataLoader(ds, batch_size=args.batch, sampler=RandomSampler(ds, generator=g), num_workers=w,
                        collate_fn=ds.collate_fn, persistent_workers=False)
        it = iter(dl)
        t0 = time.perf_counter()
        next(it)
        t1 = time.perf_counter()
        for _ in range(args.batches):
            next(it)
        t2 = time.perf_counter()
        del it, dl
        r = {"workers": w, "batch": args.batch, "batches": args.batches, "first_batch_s": round(t1 - t0, 1),
             "seconds": round(t2 - t1, 1), "img_per_s": round(args.batches * args.batch / (t2 - t1), 1)}
        result["dataloader"].append(r)
        print("dataloader", r, flush=True)

    # 3. Did the label scan warm the Windows file cache? Raw reads of just-scanned train images.
    train = image_paths(yolo, "train")
    rng.shuffle(train)
    r = raw_reads(train[:args.raw_n], 8)
    result["raw_after_scan_train"] = r
    print("raw train (scanned) 8 threads", r, flush=True)

    out = resolve_path(cfg, "perception_outputs")
    out.mkdir(parents=True, exist_ok=True)
    (out / "io_bench.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {out / 'io_bench.json'}")


if __name__ == "__main__":
    main()
