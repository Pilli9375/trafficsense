"""Run one controller on one scenario and write summary.json + metrics.csv with provenance."""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from trafficsense.config import repo_root, resolve_path
from trafficsense.control import make_controller
from trafficsense.control.base import Controller
from trafficsense.sim.env import TrafficEnv
from trafficsense.sim.metrics import MetricsTracker


def git_info() -> dict[str, Any]:
    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=repo_root(), text=True).strip()
    try:
        # Dirty = uncommitted changes to anything except outputs/: result files written by
        # earlier runs in a batch are not code and must not mark later runs as dirty.
        return {"commit": git("rev-parse", "HEAD"),
                "dirty": bool(git("status", "--porcelain", "--", ".", ":!outputs"))}
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        raise RuntimeError(f"Cannot read git commit for provenance: {e}") from e


def run_experiment(cfg: dict[str, Any], scenario: str, controller: str,
                   steps: int | None = None, seed: int | None = None,
                   out_root: Path | None = None, ctl: Controller | None = None) -> Path:
    """`ctl` overrides make_controller(controller, cfg); used by tests to inject a fake LLM client."""
    steps = int(steps if steps is not None else cfg["sim"]["steps"])
    if steps <= 0:
        raise ValueError(f"steps must be positive, got {steps}")
    seed = int(seed if seed is not None else cfg["sim"]["seed"])
    out_root = Path(out_root) if out_root is not None else resolve_path(cfg, "runs")

    started = datetime.now().astimezone()
    out_dir = out_root / f"{started:%Y%m%d-%H%M%S}_{scenario}_{controller}_s{seed}"
    if out_dir.exists():
        raise FileExistsError(f"Run folder already exists: {out_dir}")
    git = git_info()

    env = TrafficEnv(cfg, scenario, seed=seed)
    ctl = ctl if ctl is not None else make_controller(controller, cfg)
    if ctl.name != controller:
        raise ValueError(f"Controller object is {ctl.name!r}, run asked for {controller!r}")
    metrics = MetricsTracker(env)
    t0 = time.perf_counter()
    for _ in range(steps):
        ctl.act(env)
        env.step()
        metrics.update()
    wall = time.perf_counter() - t0

    result = metrics.summary()
    extra = ctl.provenance()
    unknown = set(extra) - {"model", "provider", "llm", "controller_stats"}
    if unknown:
        raise KeyError(f"Controller provenance has unexpected keys {sorted(unknown)}")
    summary = {
        "provenance": {
            "controller": controller,
            "controller_params": ctl.info(),
            "model": extra.get("model"),        # LLM controllers: name as reported by the server
            "provider": extra.get("provider"),
            "llm": extra.get("llm"),            # LLM runs: calls, failures by type, latency mean/p95
            "controller_stats": extra.get("controller_stats"),   # e.g. preemptions
            "seed": seed,
            "scenario": scenario,
            "roadnet": str(env.roadnet_path.relative_to(repo_root())),
            "flow": str(env.flow_path.relative_to(repo_root())),
            "flow_sha256": hashlib.sha256(env.flow_path.read_bytes()).hexdigest(),
            "flow_per_seed": env.flow_per_seed,
            "sim_steps": steps,
            "git_commit": git["commit"],
            "git_dirty": git["dirty"],
            "timestamp": started.isoformat(timespec="seconds"),
            "wall_time_s": round(wall, 2),
            "python": platform.python_version(),
        },
        "signal": {
            "min_green": env.min_green,
            "max_green": env.max_green,
            "transition_s": sorted(set(env.transition_time.values())),
            "switches": sum(s.switches for s in env.signals.values()),
            "forced_switches": sum(s.forced_switches for s in env.signals.values()),
        },
        "metrics": result["network"],
        "per_intersection": result["per_intersection"],
        "emergency": result.get("emergency"),   # scenarios with an emergency_vehicle_type
        "metric_notes": {
            "att": "engine.get_average_travel_time(): all generated vehicles from scheduled start, incl. those still running or still waiting to enter",
            "queue_mean_per_intersection": "waiting vehicles (speed<0.1) on incoming lanes, mean over steps and intersections",
            "queue_mean_total": "same, summed over intersections",
            "waiting_time_mean": "seconds with speed<0.1 per vehicle, mean over vehicles that entered",
            "throughput": "vehicles that finished their trip",
        },
    }

    out_dir.mkdir(parents=True)
    ctl.write_artifacts(out_dir)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (out_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(metrics.rows[0]))
        w.writeheader()
        w.writerows(metrics.rows)
    return out_dir
