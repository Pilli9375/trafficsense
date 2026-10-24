"""Replay a saved run with extra logging, for the dashboard's Network Replay page.

The saved runs keep per-step phase and total queue per intersection (metrics.csv) and every LLM
decision (decisions.jsonl), but no vehicle positions and no queue per approach. A replay drives
the simulator again with the run's own decisions:

  * runs with a decisions.jsonl (LLM controllers): at each logged decision the logged applied
    phase is requested, as scripts/analyze_llm_decisions.py does. No LLM is called;
  * deterministic controllers (MaxPressure, Webster, preemption): the same controller is run
    again, with the parameters recorded in the run (checked).

CityFlow is deterministic for a given phase sequence, so this is the same run. That is checked,
not assumed: `record` raises unless the replay reproduces the saved network metrics and every
emergency vehicle's travel and stopped time exactly.

Logged per step (after env.step(), i.e. the state at the end of second t):
  phase     phase shown during the step at each intersection (as metrics.csv)
  queue     waiting vehicles (CityFlow's waiting count, speed < 0.1 m/s; the queue metric) on the
            incoming lanes of each approach (N/E/S/W) of each intersection
  vehicles  position, heading and type of every vehicle in the network, from CityFlow's own
            replay log (saveReplay)
Deterministic controllers also get a decision log: every request to the signal, with the
MaxPressure pressures of all green phases at that moment (computed from the same exact counts
the controller reads; this does not change the run).
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from trafficsense.config import repo_root
from trafficsense.control import make_controller
from trafficsense.control.maxpressure import phase_pressures
from trafficsense.sim.env import TrafficEnv
from trafficsense.sim.metrics import MetricsTracker

APPROACHES = ("N", "E", "S", "W")
NETWORK_KEYS = ("att", "queue_mean_per_intersection", "queue_mean_total", "waiting_time_mean", "throughput",
                "vehicles_entered", "vehicles_running_at_end", "vehicles_waiting_to_enter_at_end", "steps")
EMERGENCY_KEYS = ("entered", "finished", "travel_time_s", "stopped_s", "entry_wait_s")
_FLOW_ID = re.compile(r"^flow_(\d+)_\d+$")


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def phase_name(inter, phase) -> str:
    """Plain name of a green phase from the movements it serves, e.g. 'E straight + W straight'.
    Right turns are left out (every phase serves them in these roadnets)."""
    ms = [inter.movements[k] for k in phase.movements if inter.movements[k].turn != "turn_right"]
    turn = {"go_straight": "straight", "turn_left": "left"}
    return " + ".join(f"{m.approach} {turn[m.turn]}" for m in ms) or "right turns only"


def _check_source(summary: dict[str, Any]) -> None:
    obs = summary.get("observation")
    if obs is not None and obs.get("key") != "perfect":
        raise ValueError(f"Only runs with exact counts can be replayed, this one observed {obs.get('key')!r}")


class _LoggedDecisions:
    """Applies the phases logged in decisions.jsonl."""

    def __init__(self, path: Path):
        self.at: dict[int, list[dict[str, Any]]] = collections.defaultdict(list)
        with path.open(encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                self.at[int(d["step"])].append(d)
        self.n = sum(len(v) for v in self.at.values())

    def act(self, env: TrafficEnv) -> None:
        for d in self.at.pop(int(env.time), []):
            iid = d["intersection"]
            if env.signals[iid].green_phase != d["current_phase"] or env.time_in_phase(iid) != d["time_in_phase"]:
                raise RuntimeError(f"Replay diverged from the decision log at t={d['step']} {iid}")
            env.request_phase(iid, d["phase"])

    def finish(self) -> None:
        if self.at:
            raise RuntimeError(f"{sum(len(v) for v in self.at.values())} logged decisions after the end of the run")


class _RerunController:
    """Runs the run's own deterministic controller again and logs each request to the signal."""

    def __init__(self, cfg: dict[str, Any], provenance: dict[str, Any], env: TrafficEnv):
        self.ctl = make_controller(provenance["controller"], cfg)
        if self.ctl.info() != provenance["controller_params"]:
            raise ValueError(f"Controller parameters differ from the run's: {self.ctl.info()} vs "
                             f"{provenance['controller_params']}")
        self.log: list[dict[str, Any]] = []
        request = env.request_phase

        def logged_request(iid: str, phase: int) -> bool:
            inter = env.intersection(iid)
            pr = phase_pressures(inter, env.get_state(iid))
            rec = {"step": int(env.time), "intersection": iid, "current_phase": env.signals[iid].green_phase,
                   "time_in_phase": env.time_in_phase(iid), "phase": phase,
                   "mp_pressures": {str(k): v for k, v in pr.items()}}
            switched = request(iid, phase)
            rec["action"] = "switch" if switched else "keep"
            self.log.append(rec)
            return switched

        env.request_phase = logged_request   # instance attribute; the class method is unchanged

    def act(self, env: TrafficEnv) -> None:
        self.ctl.act(env)

    def finish(self) -> None:
        pass


def _parse_cityflow_replay(path: Path, steps: int, type_of) -> dict[str, np.ndarray]:
    offsets = [0]
    xs, ys, ang, fid, typ = [], [], [], [], []
    n_lines = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            n_lines += 1
            cars = line.split(";", 1)[0]
            for c in cars.split(","):
                if not c.strip():
                    continue
                x, y, a, vid, *_ = c.split()
                m = _FLOW_ID.match(vid)
                if not m:
                    raise ValueError(f"Unexpected vehicle id {vid!r} in the CityFlow replay log")
                xs.append(float(x)); ys.append(float(y)); ang.append(float(a))
                fid.append(int(m.group(1))); typ.append(type_of(vid))
            offsets.append(len(xs))
    if n_lines != steps:
        raise RuntimeError(f"CityFlow replay log has {n_lines} steps, expected {steps}")
    return {"veh_offsets": np.array(offsets, dtype=np.int32), "veh_x": np.array(xs, dtype=np.float32),
            "veh_y": np.array(ys, dtype=np.float32), "veh_angle": np.array(ang, dtype=np.float16),
            "veh_flow": np.array(fid, dtype=np.int32), "veh_type": np.array(typ, dtype=np.int8)}


def _compare(saved: dict[str, Any], replayed: dict[str, Any]) -> dict[str, Any]:
    """Exact comparison of the saved and replayed metrics; raises on any difference."""
    checked, bad = {}, []
    for k in NETWORK_KEYS:
        a, b = saved["metrics"][k], replayed["network"][k]
        checked[k] = a
        if a != b:
            bad.append(f"{k}: saved {a}, replay {b}")
    em_saved, em_rep = saved.get("emergency"), replayed.get("emergency")
    if (em_saved is None) != (em_rep is None):
        bad.append("emergency metrics present in only one of saved / replay")
    n_em = 0
    if em_saved is not None:
        rep = {v["vehicle"]: v for v in em_rep["vehicles"]}
        for v in em_saved["vehicles"]:
            r = rep.get(v["vehicle"])
            n_em += 1
            if r is None or any(v[k] != r[k] for k in EMERGENCY_KEYS):
                bad.append(f"emergency vehicle {v['vehicle']} differs")
        if len(rep) != len(em_saved["vehicles"]):
            bad.append("different number of emergency vehicles")
    if bad:
        raise RuntimeError("Replay does not reproduce the saved run: " + "; ".join(bad))
    return {"network_metrics_identical": checked, "emergency_vehicles_identical": n_em}


def record(cfg: dict[str, Any], run_dir: Path, out_dir: Path, git: dict[str, Any]) -> dict[str, Any]:
    """Replay `run_dir` and write replay.npz + meta.json (+ decisions_replay.jsonl) to out_dir."""
    root = repo_root()
    run_dir = Path(run_dir)
    summary = json.loads((run_dir / "summary.json").read_text())
    _check_source(summary)
    pv = summary["provenance"]
    steps = int(pv["sim_steps"])

    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / "_cityflow_log"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir()
    env = TrafficEnv(cfg, pv["scenario"], seed=pv["seed"], replay_dir=tmp)
    if sha256(env.flow_path) != pv["flow_sha256"]:
        raise ValueError(f"Flow file {env.flow_path} changed since the run (sha256 differs)")

    decisions = run_dir / "decisions.jsonl"
    driver = _LoggedDecisions(decisions) if decisions.is_file() else _RerunController(cfg, pv, env)
    metrics = MetricsTracker(env)
    ids = env.intersection_ids
    approach_lanes = []
    for iid in ids:
        inter = env.intersection(iid)
        by_app = {a: [] for a in APPROACHES}
        for m in inter.movements:
            for lane in m.in_lanes:
                if lane not in by_app[m.approach]:
                    by_app[m.approach].append(lane)
        approach_lanes.append([by_app[a] for a in APPROACHES])
    phase = np.zeros((steps, len(ids)), dtype=np.int8)
    queue = np.zeros((steps, len(ids), len(APPROACHES)), dtype=np.int16)
    for t in range(steps):
        driver.act(env)
        env.step()
        metrics.update()
        waiting = env.eng.get_lane_waiting_vehicle_count()
        for i, iid in enumerate(ids):
            phase[t, i] = env.shown_phase(iid)
            for a, lanes in enumerate(approach_lanes[i]):
                queue[t, i, a] = sum(waiting[l] for l in lanes)
    driver.finish()
    verified = _compare(summary, metrics.summary())
    # The per-approach queues must add up to the queue metric's per-step totals.
    if not np.array_equal(queue.sum(axis=2).sum(axis=0), np.array([metrics.queue_sum[i] for i in ids])):
        raise RuntimeError("Per-approach queues do not add up to the queue metric")
    vt, net, emergency_type = env.vehicle_types, env.roadnet, env.emergency_type
    vt_names = vt.names
    env.eng = None    # destroys the engine: CityFlow flushes and closes its replay log only then

    arrays = _parse_cityflow_replay(tmp / "replay_log.txt", steps, lambda v: vt_names.index(vt.of(v)))
    np.savez_compressed(out_dir / "replay.npz", time=np.arange(1, steps + 1, dtype=np.int32),
                        phase=phase, queue=queue, **arrays)
    shutil.rmtree(tmp)
    if isinstance(driver, _RerunController):
        with (out_dir / "decisions_replay.jsonl").open("w", encoding="utf-8") as f:
            for rec in driver.log:
                f.write(json.dumps(rec) + "\n")

    meta = {
        "made_by": "scripts/make_replays.py",
        "git_commit": git["commit"],
        "git_dirty": git["dirty"],
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        # relative to the repo root (runs outside the repo only occur in tests)
        "source_run": str(run_dir.resolve().relative_to(root)) if run_dir.resolve().is_relative_to(root)
        else str(run_dir.resolve()),
        "source_summary_sha256": sha256(run_dir / "summary.json"),
        "source_decisions_sha256": sha256(decisions) if decisions.is_file() else None,
        "drive": "decisions.jsonl (logged applied phases)" if decisions.is_file() else "controller re-run",
        "controller": pv["controller"],
        "model": pv["model"],
        "provider": pv["provider"],
        "scenario": pv["scenario"],
        "seed": pv["seed"],
        "steps": steps,
        "roadnet": pv["roadnet"],
        "intersections": ids,
        "approaches": list(APPROACHES),
        "phase_names": {iid: {str(p.index): phase_name(inter, p) for p in inter.green_phases}
                        for iid, inter in net.intersections.items()},
        "transition_phase": {iid: inter.transition_phase.index for iid, inter in net.intersections.items()},
        "vehicle_types": vt_names,
        "emergency_type": emergency_type,
        "verified": verified,
        "notes": {"time": "state at the end of second t (after env.step())",
                  "phase": "phase shown during second t",
                  "queue": "waiting vehicles (speed < 0.1 m/s) on the incoming lanes of each approach",
                  "vehicles": "CityFlow replay log: x, y (m), heading (rad), flow index, type index"},
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta
