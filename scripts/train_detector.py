"""Train the YOLOv8 detector on our IDD splits (docs/perception.md section 6).

    python scripts/train_detector.py --probe [--batch 16]   # 1 epoch on a random 10% of train
    python scripts/train_detector.py --full                 # pre-registered run; resumes if interrupted

Everything the run writes (weights, Ultralytics logs, our per-epoch log, GPU samples) goes
to paths.detector_runs/detector/<name> (a symlink to D). Settings: perception.train.

--probe draws perception.train.probe_fraction of the train images at random (seed
perception.train.seed) instead of Ultralytics' `fraction`, which takes the first images of
the sorted list (all frontFar). The 50-epoch estimate it prints is an extrapolation.

--full starts the run, or resumes it from weights/last.pt if it was interrupted, or stops if
it already finished. A summary with weight paths and sha256 goes to
paths.perception_outputs/detector_train.json.
"""
import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from trafficsense.config import load_config, resolve_path
from trafficsense.experiment import git_info
from trafficsense.perception import detector


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def pretrained(runs: Path, name: str) -> Path:
    from ultralytics.utils.downloads import attempt_download_asset
    dst = runs / "pretrained" / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.is_file():
        attempt_download_asset(str(dst))
    if not dst.is_file():
        raise FileNotFoundError(f"Could not download {name} to {dst}")
    return dst


def cache_path_for(first_image: str) -> Path:
    """Where Ultralytics puts the label cache for an image list whose first sorted image is this."""
    from ultralytics.data.utils import img2label_paths
    return Path(img2label_paths([first_image])[0]).parent.with_suffix(".cache")


def epoch_records(log: Path) -> list[dict]:
    """Per-epoch records; after a resume an epoch may be logged twice, the last one wins."""
    by_epoch = {r["epoch"]: r for r in detector.read_log(log) if r["event"] == "epoch"}
    return [by_epoch[k] for k in sorted(by_epoch)]


def probe(cfg: dict, args) -> None:
    from ultralytics import YOLO
    tcfg, pcfg = cfg["perception"]["train"], cfg["perception"]
    yolo = resolve_path(cfg, "idd_yolo")
    runs = resolve_path(cfg, "detector_runs")
    overrides = detector.train_overrides(tcfg, pcfg["imgsz"])
    overrides.update(epochs=1, batch=args.batch or overrides["batch"])
    name = f"probe_b{overrides['batch']}"
    run_dir = runs / "detector" / name
    if run_dir.exists():
        raise FileExistsError(f"{run_dir} exists; remove it to re-run this probe")
    run_dir.mkdir(parents=True)

    train_lines = (yolo / "train.txt").read_text().split()
    lines = detector.sample_lines(train_lines, float(tcfg["probe_fraction"]), int(tcfg["seed"]))
    images = [str(yolo / x[2:]) for x in lines]   # through the images symlink, so labels are found
    (run_dir / "probe_train.txt").write_text("\n".join(images) + "\n")
    data = yolo / "data.yaml"
    probe_yaml = run_dir / "data.yaml"
    probe_yaml.write_text(data.read_text().replace("train: train.txt", f"train: {run_dir / 'probe_train.txt'}"))

    # The probe's label cache can land on the full train list's cache file and overwrite it;
    # keep a copy and put it back afterwards.
    cache = cache_path_for(sorted(images)[0])
    backup = run_dir / "label_cache_backup.cache"
    if cache.is_file():
        shutil.copy2(cache, backup)

    git = git_info()
    weights = pretrained(runs, tcfg["model"])
    model = YOLO(str(weights))
    log = run_dir / "train_log.jsonl"
    detector.TrainMonitor(log).attach(model)
    gpu = detector.GpuSampler(run_dir / "gpu.csv").start()
    try:
        model.train(data=str(probe_yaml), project=str(runs / "detector"), name=name, exist_ok=True,
                    plots=False, **overrides)
    finally:
        gpu.stop()
        if backup.is_file():
            shutil.copy2(backup, cache)

    rec = epoch_records(log)[-1]
    n_train = len(train_lines)
    val_s = rec["val_and_save_s"]
    rates = {"measured_steady_img_per_s": rec["steady_img_per_s"],
             "measured_epoch_img_per_s": rec["img_per_s"]}
    estimate = {}
    for k, r in rates.items():
        epoch_s = n_train / r + val_s
        estimate[k] = {"train_epoch_min": round(n_train / r / 60, 1), "val_and_save_min": round(val_s / 60, 1),
                       f"{tcfg['epochs']}_epochs_h": round(tcfg["epochs"] * epoch_s / 3600, 1)}
    summary = {
        "kind": "probe", "run_dir": str(run_dir.resolve()), "settings": overrides,
        "probe_images": len(images), "train_images_full": n_train,
        "pretrained": {"path": str(weights.resolve()), "sha256": detector.sha256(weights)},
        "epoch": rec, "gpu_nvidia_smi": detector.summarize_gpu_csv(run_dir / "gpu.csv"),
        "estimate_note": "ESTIMATE: full epoch time extrapolated from the probe's rates; "
                         "val time measured on the full val split (includes saving last.pt/best.pt)",
        "estimate": estimate,
        "provenance": {"script": "scripts/train_detector.py --probe", "git_commit": git["commit"],
                       "git_dirty": git["dirty"], "timestamp": now()},
    }
    out = resolve_path(cfg, "perception_outputs") / f"detector_{name}.json"
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in ("epoch", "gpu_nvidia_smi", "estimate")}, indent=2))
    print(f"wrote {out}")


def full(cfg: dict) -> None:
    from ultralytics import YOLO
    tcfg, pcfg = cfg["perception"]["train"], cfg["perception"]
    yolo = resolve_path(cfg, "idd_yolo")
    runs = resolve_path(cfg, "detector_runs")
    name = tcfg["run_name"]
    run_dir = runs / "detector" / name
    state = detector.run_state(run_dir)
    if state == "finished":
        print(f"{run_dir} already finished ({detector.DONE_MARKER}); nothing to do")
        return

    git = git_info()
    run_dir.mkdir(parents=True, exist_ok=True)
    with open(run_dir / "segments.jsonl", "a") as f:   # one line per start/resume, for provenance
        f.write(json.dumps({"state": state, "git_commit": git["commit"], "git_dirty": git["dirty"],
                            "timestamp": now()}) + "\n")
    weights = pretrained(runs, tcfg["model"])
    log = run_dir / "train_log.jsonl"
    gpu = detector.GpuSampler(run_dir / "gpu.csv", period=30).start()
    try:
        if state == "resumable":
            last = run_dir / "weights" / "last.pt"
            print(f"resuming from {last}")
            model = YOLO(str(last))
            detector.TrainMonitor(log).attach(model)
            model.train(resume=True)
        else:
            overrides = detector.train_overrides(tcfg, pcfg["imgsz"])
            model = YOLO(str(weights))
            detector.TrainMonitor(log).attach(model)
            model.train(data=str(yolo / "data.yaml"), project=str(runs / "detector"), name=name,
                        exist_ok=True, **overrides)
    finally:
        gpu.stop()

    best, last = run_dir / "weights" / "best.pt", run_dir / "weights" / "last.pt"
    recs = epoch_records(log)
    segments = [json.loads(x) for x in (run_dir / "segments.jsonl").read_text().splitlines()]
    best_rec = max(recs, key=lambda r: r["fitness"])
    summary = {
        "kind": "train", "run_dir": str(run_dir.resolve()),
        "settings": detector.train_overrides(tcfg, pcfg["imgsz"]), "model": tcfg["model"],
        "pretrained": {"path": str(weights.resolve()), "sha256": detector.sha256(weights)},
        "epochs_run": len(recs), "best_epoch": best_rec["epoch"],
        "stopped_early": len(recs) < int(tcfg["epochs"]),
        "best_val_metrics": best_rec["metrics"],
        "weights": {k: {"path": str(p.resolve()), "sha256": detector.sha256(p), "bytes": p.stat().st_size}
                    for k, p in (("best", best), ("last", last))},
        "train_hours": round(sum(r["train_s"] + r["val_and_save_s"] for r in recs) / 3600, 2),
        "epochs": recs, "segments": segments,
        "provenance": {"script": "scripts/train_detector.py --full", "git_commit": segments[0]["git_commit"],
                       "git_dirty": segments[0]["git_dirty"], "timestamp": now()},
    }
    (run_dir / detector.DONE_MARKER).write_text(json.dumps({"timestamp": now()}) + "\n")
    out = resolve_path(cfg, "perception_outputs") / "detector_train.json"
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"done: {len(recs)} epochs, best epoch {best_rec['epoch']}; wrote {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/default.yaml")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--probe", action="store_true")
    mode.add_argument("--full", action="store_true")
    ap.add_argument("--batch", type=int, help="probe only: override perception.train.batch")
    args = ap.parse_args()
    cfg = load_config(args.config)
    if args.full and args.batch:
        raise ValueError("--batch is for the probe; the full run uses perception.train.batch")
    probe(cfg, args) if args.probe else full(cfg)


if __name__ == "__main__":
    main()
