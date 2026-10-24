"""What the controllers observe: exact simulator counts, or counts with camera errors.

The simulator itself always stays exact (metrics read the engine directly). Controllers read
lane counts only through TrafficEnv.lane_view(), which returns a LaneView:

  * ExactObserver: the engine's own lane counts (identical to reading the engine directly).
  * NoisyObserver (camera-error experiment, docs/camera_error.md): one camera per road. At
    each simulator step at which some controller observes, a fresh snapshot is drawn (cached
    for that step, so every intersection sees the same snapshot; the next observation draws
    again, so no vehicle stays "blind"):
      - each vehicle on a lane is detected with p_detect of its detector class;
      - a detected vehicle gets a label drawn from p_label[class]; it is counted as a vehicle
        only if the label is a vehicle class (COUNTED: a vehicle labelled `person` is lost);
      - false detections: per road and per counted class j, a Poisson(false_det[j]) number of
        phantom vehicles, each on a uniformly chosen lane of the road, counted as stopped
        (ASSUMPTION: false positives of a fixed camera are mostly static clutter, and a stopped
        phantom is the case that changes queue-based decisions most);
      - a detected vehicle is stopped if its speed < 0.1 m/s (CityFlow's waiting definition);
      - emergency vehicles (the scenario's emergency types, i.e. ambulances) are never noised:
        IDD has no ambulance class, and their positions are ASSUMED to come from a separate
        channel (GPS/V2X). They are counted exactly, and sim/emergency.py reads the engine.
    Draws use a numpy Generator seeded from (run seed, noise level) and are logged per snapshot.

Simulator vehicle types map to detector classes through SIM_TO_DETECTOR.
"""
from __future__ import annotations

import collections
import hashlib
import json
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from trafficsense.sim.env import TrafficEnv

DETECTOR_CLASSES = ("car", "motorcycle", "autorickshaw", "bus", "truck", "bicycle", "person")
# Indian 2x2 vehicle types -> detector classes (docs/camera_error.md). Every non-emergency
# simulator type must be listed; an unknown type raises.
SIM_TO_DETECTOR = {"car": "car", "motorcycle": "motorcycle", "auto_rickshaw": "autorickshaw",
                   "bus": "bus", "truck": "truck"}
# Detector labels counted as vehicles (person is not a vehicle; bicycle is).
COUNTED = ("car", "motorcycle", "autorickshaw", "bus", "truck", "bicycle")
# Names used in vehicle-type counts: simulator names where one exists.
DETECTOR_TO_NAME = {**{d: s for s, d in SIM_TO_DETECTOR.items()}, "bicycle": "bicycle"}
STOP_SPEED = 0.1
LEVELS = ("perfect", "junction", "crowded", "uniform")


@dataclass
class NoiseParams:
    key: str                                   # e.g. "junction", "uniform_p0.80"
    p_detect: dict[str, float]
    p_label: dict[str, dict[str, float]]
    false_det: dict[str, float]
    source: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {"key": self.key, "p_detect": self.p_detect, "p_label": self.p_label,
                "false_det_per_road_snapshot": self.false_det, "source": self.source}


def observation_key(ocfg: dict[str, Any] | None) -> str:
    ocfg = ocfg or {"level": "perfect"}
    level = ocfg.get("level")
    if level not in LEVELS:
        raise ValueError(f"observation.level must be one of {LEVELS}, got {level!r}")
    if level == "uniform":
        p = float(ocfg["p_detect"])
        if not 0 < p <= 1:
            raise ValueError(f"observation.p_detect must be in (0, 1], got {p}")
        return f"uniform_p{p:.2f}"
    return level


def noise_params(ocfg: dict[str, Any], error_model_path: Path) -> NoiseParams:
    """Parameters of a noisy level. junction: detection rates of medium + large objects
    (pooled over their ground truth); crowded: overall rates; both with the measured label
    probabilities and false detections. uniform: p_detect for every class, exact labels, no
    false detections."""
    key = observation_key(ocfg)
    if ocfg["level"] == "uniform":
        p = float(ocfg["p_detect"])
        return NoiseParams(key, {c: p for c in DETECTOR_CLASSES}, {c: {c: 1.0} for c in DETECTOR_CLASSES},
                           {c: 0.0 for c in COUNTED}, {"kind": "uniform", "p_detect": p})
    em = json.loads(Path(error_model_path).read_text())
    if list(em["classes"]) != list(DETECTOR_CLASSES):
        raise ValueError(f"{error_model_path}: classes {em['classes']} != {DETECTOR_CLASSES}")
    if ocfg["level"] == "crowded":
        p_detect = {c: float(em["p_detect"][c]) for c in DETECTOR_CLASSES}
    else:
        p_detect = {}
        for c in DETECTOR_CLASSES:
            s = em["miss_rate_by_size"][c]
            gt = s["medium"]["gt"] + s["large"]["gt"]
            miss = s["medium"]["miss_rate"] * s["medium"]["gt"] + s["large"]["miss_rate"] * s["large"]["gt"]
            p_detect[c] = round(1 - miss / gt, 4)
    p_label = {c: {j: float(v) for j, v in em["p_label_given_detected"][c].items() if v > 0} for c in DETECTOR_CLASSES}
    for c, row in p_label.items():
        if abs(sum(row.values()) - 1) > 0.01:
            raise ValueError(f"{error_model_path}: label probabilities of {c} sum to {sum(row.values())}")
    false_det = {c: float(em["false_det_per_image"][c]["value"]) for c in COUNTED}
    sha = hashlib.sha256(Path(error_model_path).read_bytes()).hexdigest()
    return NoiseParams(key, p_detect, p_label, false_det,
                       {"kind": "error_model", "file": str(error_model_path), "sha256": sha,
                        "conf_threshold": em["conf_threshold"],
                        "p_detect_from": "medium+large objects" if ocfg["level"] == "junction" else "all objects"})


class LaneView:
    """Lane counts as a controller sees them at one step."""

    def __init__(self, waiting: dict[str, int], count: dict[str, int], types: dict[str, collections.Counter]):
        self.waiting, self.count, self._types = waiting, count, types

    def type_counts(self, lanes: list[str], order: list[str]) -> dict[str, int]:
        """Vehicle-type counts over `lanes`, in `order` (unknown names after it), zeros left out."""
        c: collections.Counter = collections.Counter()
        for l in lanes:
            c.update(self._types.get(l, {}))
        names = list(order) + sorted(n for n in c if n not in order)
        return {n: c[n] for n in names if c[n]}


class ExactLaneView(LaneView):
    """The engine's own counts; type counts straight from the simulator's vehicle types."""

    def __init__(self, env: "TrafficEnv"):
        eng = env.eng
        super().__init__(eng.get_lane_waiting_vehicle_count(), eng.get_lane_vehicle_count(), {})
        self._lane_veh, self._env = eng.get_lane_vehicles(), env

    def type_counts(self, lanes: list[str], order: list[str]) -> dict[str, int]:
        return self._env.vehicle_types.count([v for l in lanes for v in self._lane_veh[l]])


class ExactObserver:
    key = "perfect"

    def __init__(self, env: "TrafficEnv"):
        self.env = env

    def view(self) -> LaneView:
        return ExactLaneView(self.env)

    def summary(self) -> dict[str, Any]:
        return {"key": self.key, "noised": False}

    def write_artifacts(self, out_dir: Path) -> None:
        pass


class NoisyObserver:
    def __init__(self, env: "TrafficEnv", params: NoiseParams, run_seed: int):
        self.env, self.params = env, params
        self.key = params.key
        self.seed_entropy = [int(run_seed), zlib.crc32(params.key.encode())]
        self.rng = np.random.default_rng(np.random.SeedSequence(self.seed_entropy))
        self.exempt = set(env.emergency_types)
        lanes = sorted(env.eng.get_lane_vehicle_count())
        self.roads: dict[str, list[str]] = {}
        for l in lanes:
            self.roads.setdefault(l.rsplit("_", 1)[0], []).append(l)
        self._cache_t: float | None = None
        self._cache: LaneView | None = None
        self.log: list[dict[str, Any]] = []
        self._labels = {c: (list(r), np.array(list(r.values())) / sum(r.values())) for c, r in params.p_label.items()}

    def view(self) -> LaneView:
        t = self.env.time
        if self._cache_t != t:
            self._cache, self._cache_t = self._draw(), t
        return self._cache

    def _draw(self) -> LaneView:
        eng, vt, p = self.env.eng, self.env.vehicle_types, self.params
        lane_veh = eng.get_lane_vehicles()
        speed = eng.get_vehicle_speed()
        waiting: dict[str, int] = {}
        count: dict[str, int] = {}
        types: dict[str, collections.Counter] = {}
        true_n: collections.Counter = collections.Counter()
        detected: collections.Counter = collections.Counter()
        uncounted_label: collections.Counter = collections.Counter()
        phantoms: collections.Counter = collections.Counter()
        for road, lanes in self.roads.items():
            for l in lanes:
                w = n = 0
                tc: collections.Counter = collections.Counter()
                for v in lane_veh[l]:
                    if v.endswith("_shadow"):
                        continue
                    t = vt.of(v)
                    if t in self.exempt:
                        label = t
                    else:
                        if t not in SIM_TO_DETECTOR:
                            raise KeyError(f"Vehicle type {t!r} has no detector class (SIM_TO_DETECTOR)")
                        c = SIM_TO_DETECTOR[t]
                        true_n[c] += 1
                        if self.rng.random() >= p.p_detect[c]:
                            continue
                        detected[c] += 1
                        names, probs = self._labels[c]
                        j = names[int(self.rng.choice(len(names), p=probs))] if len(names) > 1 else names[0]
                        if j not in COUNTED:
                            uncounted_label[c] += 1
                            continue
                        label = DETECTOR_TO_NAME[j]
                    n += 1
                    w += speed[v] < STOP_SPEED
                    tc[label] += 1
                waiting[l], count[l], types[l] = w, n, tc
            for j in COUNTED:
                lam = p.false_det.get(j, 0.0)
                if lam <= 0:
                    continue
                for _ in range(int(self.rng.poisson(lam))):
                    l = lanes[int(self.rng.integers(len(lanes)))]
                    waiting[l] += 1
                    count[l] += 1
                    types[l][DETECTOR_TO_NAME[j]] += 1
                    phantoms[j] += 1
        self.log.append({"t": int(self.env.time), "true": dict(true_n), "detected": dict(detected),
                         "detected_uncounted_label": dict(uncounted_label), "false_added": dict(phantoms)})
        return LaneView(waiting, count, types)

    def summary(self) -> dict[str, Any]:
        tot = {k: collections.Counter() for k in ("true", "detected", "detected_uncounted_label", "false_added")}
        for rec in self.log:
            for k in tot:
                tot[k].update(rec[k])
        snaps = len(self.log)
        return {
            "key": self.key, "noised": True, "params": self.params.as_dict(),
            "seed_entropy": self.seed_entropy, "rng": "numpy default_rng(SeedSequence(seed_entropy))",
            "emergency_types_not_noised": sorted(self.exempt),
            "snapshots": snaps, "roads": len(self.roads),
            "realized": {
                "true_vehicle_observations": dict(tot["true"]),
                "detection_rate": {c: round(tot["detected"][c] / n, 4) for c, n in tot["true"].items() if n},
                "lost_to_non_vehicle_label": dict(tot["detected_uncounted_label"]),
                "false_per_road_snapshot": {j: round(tot["false_added"][j] / (snaps * len(self.roads)), 4)
                                            for j in COUNTED} if snaps else {},
            },
            "log": "noise.jsonl",
        }

    def write_artifacts(self, out_dir: Path) -> None:
        with (out_dir / "noise.jsonl").open("w", encoding="utf-8") as f:
            for rec in self.log:
                f.write(json.dumps(rec) + "\n")


def make_observer(env: "TrafficEnv", ocfg: dict[str, Any] | None, error_model_path: Path | None, run_seed: int):
    key = observation_key(ocfg)
    if key == "perfect":
        return ExactObserver(env)
    if ocfg["level"] != "uniform" and (error_model_path is None or not Path(error_model_path).is_file()):
        raise FileNotFoundError(f"Camera error model not found: {error_model_path} (scripts/eval_detector.py)")
    return NoisyObserver(env, noise_params(ocfg, error_model_path), run_seed)
