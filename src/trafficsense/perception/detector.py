"""YOLO detector training helpers (docs/perception.md section 6).

Ultralytics does the training; this module holds what we add around it: the probe's
random image subset, the run state used for resuming, weight hashes, and a callback that
times every batch (data wait vs GPU compute), records peak VRAM and stops on a
non-finite loss instead of letting Ultralytics silently reload a checkpoint.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

DONE_MARKER = "train_done.json"


def sample_lines(lines: list[str], fraction: float, seed: int) -> list[str]:
    """A random `fraction` of `lines` (at least 1), drawn with random.Random(seed), in input order."""
    if not 0 < fraction <= 1:
        raise ValueError(f"fraction must be in (0, 1], got {fraction}")
    k = max(1, round(len(lines) * fraction))
    keep = set(random.Random(seed).sample(range(len(lines)), k))
    return [x for i, x in enumerate(lines) if i in keep]


def run_state(run_dir: Path) -> str:
    """'new' (nothing to resume), 'resumable' (last.pt, not finished) or 'finished'."""
    if (run_dir / DONE_MARKER).is_file():
        return "finished"
    if (run_dir / "weights" / "last.pt").is_file():
        return "resumable"
    return "new"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def train_overrides(tcfg: dict[str, Any], imgsz: int) -> dict[str, Any]:
    """Ultralytics train() arguments from perception.train; every key must be present."""
    keys = ("epochs", "patience", "batch", "amp", "workers", "cache", "seed", "deterministic")
    missing = [k for k in keys if k not in tcfg]
    if missing:
        raise KeyError(f"perception.train is missing {missing}")
    return {"imgsz": int(imgsz), **{k: tcfg[k] for k in keys}}


def batch_images(i: int, batch_size: int, n_images: int) -> int:
    """Images in batch i (1-based) of an epoch; the last batch holds the remainder.

    Ultralytics keeps the batch in a local variable, so callbacks cannot count it directly.
    """
    return max(0, min(batch_size, n_images - (i - 1) * batch_size))


class GpuSampler:
    """Polls nvidia-smi every `period` s into a CSV (GPU utilisation and memory used, MiB)."""

    def __init__(self, out_csv: Path, period: float = 5.0):
        self.out_csv, self.period = out_csv, period
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        new = not self.out_csv.exists()
        with open(self.out_csv, "a") as f:
            if new:
                f.write("time,gpu_util_pct,mem_used_mib\n")
            while not self._stop.is_set():
                out = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used",
                                      "--format=csv,noheader,nounits"], capture_output=True, text=True)
                if out.returncode == 0:
                    util, mem = (x.strip() for x in out.stdout.strip().splitlines()[0].split(","))
                    f.write(f"{time.time():.0f},{util},{mem}\n")
                    f.flush()
                self._stop.wait(self.period)

    def start(self) -> "GpuSampler":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2 * self.period)


def summarize_gpu_csv(path: Path) -> dict[str, Any]:
    rows = [line.split(",") for line in path.read_text().splitlines()[1:] if line]
    if not rows:
        return {"samples": 0}
    util = [float(r[1]) for r in rows]
    mem = [float(r[2]) for r in rows]
    return {"samples": len(rows), "util_mean_pct": round(sum(util) / len(util), 1),
            "mem_used_max_mib": max(mem)}


class TrainMonitor:
    """Ultralytics callbacks: per-epoch timing, throughput, peak VRAM and loss checks -> JSONL.

    data_wait = time between the end of one batch and the start of the next (the loader);
    gpu = start to end of a batch (forward, backward, optimizer), synchronised with CUDA,
    so gpu_img_per_s is what the GPU alone could sustain. The first `skip` batches of each
    epoch (worker start-up) are left out of the steady-state rates.
    """

    def __init__(self, log_path: Path, skip: int = 20):
        self.log_path, self.skip = log_path, skip

    def attach(self, model) -> None:
        for ev in ("on_train_epoch_start", "on_train_batch_start", "on_train_batch_end",
                   "on_train_epoch_end", "on_fit_epoch_end"):
            model.add_callback(ev, getattr(self, ev))

    def on_train_epoch_start(self, trainer) -> None:
        import torch
        torch.cuda.reset_peak_memory_stats()
        self.t_epoch = time.perf_counter()
        self.t_last_end = self.t_epoch
        self.batches = self.images = self.nonfinite = 0
        self.wait = self.gpu = 0.0
        self.ss_images = 0
        self.ss_wait = self.ss_gpu = 0.0

    def on_train_batch_start(self, trainer) -> None:
        self.t_start = time.perf_counter()

    def on_train_batch_end(self, trainer) -> None:
        import torch
        torch.cuda.synchronize()
        t = time.perf_counter()
        n = batch_images(self.batches + 1, trainer.batch_size, len(trainer.train_loader.dataset))
        wait, gpu = self.t_start - self.t_last_end, t - self.t_start
        self.batches += 1
        self.images += n
        self.wait += wait
        self.gpu += gpu
        if self.batches > self.skip:
            self.ss_images += n
            self.ss_wait += wait
            self.ss_gpu += gpu
        self.t_last_end = t
        if not torch.isfinite(trainer.loss).all() or not torch.isfinite(trainer.loss_items).all():
            self.nonfinite += 1
            self._write({"event": "nonfinite_loss", "epoch": trainer.epoch + 1, "batch": self.batches,
                         "loss_items": [float(x) for x in trainer.loss_items]})
            raise RuntimeError(f"Non-finite training loss at epoch {trainer.epoch + 1}, batch {self.batches}: "
                               f"{trainer.loss_items.tolist()}. Stopping (no silent recovery).")

    def on_train_epoch_end(self, trainer) -> None:
        import torch
        self.t_train_end = time.perf_counter()
        self.peak_alloc = torch.cuda.max_memory_allocated() / 2**20
        self.peak_reserved = torch.cuda.max_memory_reserved() / 2**20

    def on_fit_epoch_end(self, trainer) -> None:
        t = time.perf_counter()
        train_s = self.t_train_end - self.t_epoch
        losses = dict(zip(trainer.loss_names, (float(x) for x in trainer.tloss)))
        rec = {
            "event": "epoch", "epoch": trainer.epoch + 1, "epochs": trainer.epochs,
            "train_images": self.images, "batches": self.batches,
            "train_s": round(train_s, 1), "val_and_save_s": round(t - self.t_train_end, 1),
            "img_per_s": round(self.images / train_s, 1),
            "steady_img_per_s": round(self.ss_images / (self.ss_wait + self.ss_gpu), 1) if self.ss_images else None,
            "steady_gpu_img_per_s": round(self.ss_images / self.ss_gpu, 1) if self.ss_images else None,
            "steady_data_wait_share": round(self.ss_wait / (self.ss_wait + self.ss_gpu), 3) if self.ss_images else None,
            "peak_vram_allocated_mib": round(self.peak_alloc), "peak_vram_reserved_mib": round(self.peak_reserved),
            "train_losses": losses, "losses_finite": all(math.isfinite(v) for v in losses.values()),
            "nonfinite_batches": self.nonfinite,
            "metrics": {k: float(v) for k, v in trainer.metrics.items()},
            "fitness": None if trainer.fitness is None else float(trainer.fitness),
            "time": time.time(),
        }
        self._write(rec)

    def _write(self, rec: dict[str, Any]) -> None:
        with open(self.log_path, "a") as f:
            f.write(json.dumps(rec) + "\n")


def read_log(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.is_file() else []
