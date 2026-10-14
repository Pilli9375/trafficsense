"""CoLLMLight's metric definitions, reimplemented on top of our env for the cross-check.

Mirrors utils/cityflow_env.py and utils/oneline.py in the CoLLMLight repo, including quirks:
  * travel time: per intersection, a vehicle "enters" when it first appears on one of the
    intersection's incoming lanes and "leaves" the last second it disappears from them; a
    vehicle's travel time is the sum over intersections of (leave - enter), with
    leave = RUN_COUNTS (3600) if it never left. If no vehicle was on the intersection's incoming
    lanes the previous second, every vehicle now on them is also marked as left this second
    (their set-difference fallback), which a later real departure overwrites.
  * throughput: vehicles that have left every intersection they entered.
  * queue: waiting vehicles on all incoming lanes summed over the network, sampled once per
    30 s action step (after the step), averaged over steps.
  * waiting time: for each running vehicle with speed < 0.1, the length of its *current*
    stop on its current drivable (reset when it moves or changes lane/link); the mean over
    currently stopped vehicles is sampled once per action step and averaged over steps.
These are NOT the definitions TrafficSense reports; they exist only to compare like with like.
"""
from __future__ import annotations

import math

import numpy as np


class CoLLMLightMetrics:
    def __init__(self, env, step_len: int = 30, run_counts: int = 3600):
        self.env = env
        self.step_len = step_len
        self.run_counts = run_counts
        self.in_lanes = {i: env.intersection(i).incoming_lanes for i in env.intersection_ids}
        self.prev_in: dict[str, list[str]] = {i: [] for i in env.intersection_ids}
        self.arrive_leave: dict[str, dict[str, list[float]]] = {i: {} for i in env.intersection_ids}
        self.waiting: dict[str, dict] = {}
        self.queue_samples: list[int] = []
        self.wait_samples: list[float] = []
        self.seconds = 0
        self._update_lanes()   # their env.reset() measures once before the first step

    def _update_lanes(self) -> None:
        ts = self.env.time
        lane_veh = self.env.eng.get_lane_vehicles()
        for i, lanes in self.in_lanes.items():
            cur = [v for l in lanes for v in lane_veh.get(l, [])]
            prev = self.prev_in[i]
            arrived = set(cur) - set(prev)
            left = (set(cur) - set(prev)) if not prev else (set(prev) - set(cur))
            d = self.arrive_leave[i]
            for v in arrived:
                if v not in d:
                    d[v] = [ts, math.nan]
            for v in left:
                if v not in d:
                    raise RuntimeError(f"{v} left {i} without being recorded entering")
                d[v][1] = ts
            self.prev_in[i] = cur

    def update(self) -> None:
        """Call after every env.step()."""
        eng = self.env.eng
        for v in eng.get_vehicles(include_waiting=False):
            info = eng.get_vehicle_info(v)
            w = self.waiting.get(v)
            if float(info["speed"]) < 0.1:
                if w is None or w["link"] != info["drivable"]:
                    self.waiting[v] = {"time": 1.0, "link": info["drivable"]}
                else:
                    w["time"] += 1.0
            elif w is not None:
                del self.waiting[v]
        self._update_lanes()
        self.seconds += 1
        if self.seconds % self.step_len == 0:
            waiting = eng.get_lane_waiting_vehicle_count()
            self.queue_samples.append(sum(waiting.get(l, 0) for ls in self.in_lanes.values() for l in ls))
            times = [w["time"] for w in self.waiting.values()]
            self.wait_samples.append(float(np.mean(times)) if times else 0.0)

    def summary(self) -> dict[str, float]:
        per_vehicle: dict[str, float] = {}
        not_left, all_veh = set(), set()
        for d in self.arrive_leave.values():
            for v, (enter, leave) in d.items():
                all_veh.add(v)
                if math.isnan(leave):
                    not_left.add(v)
                    leave = self.run_counts
                per_vehicle[v] = per_vehicle.get(v, 0.0) + (leave - enter)
        return {
            "test_avg_travel_time_over": float(np.mean(list(per_vehicle.values()))),
            "test_throughput_over": float(len(all_veh - not_left)),
            "test_avg_queue_len_over": float(np.mean(self.queue_samples)),
            "test_avg_waiting_time_over": float(np.mean(self.wait_samples)),
            "cityflow_att": float(self.env.eng.get_average_travel_time()),
            "vehicles_running_at_end": len(self.env.eng.get_vehicles(include_waiting=False)),
        }
