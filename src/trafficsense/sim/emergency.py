"""Emergency vehicles (ambulances): where they are, and what happens to them.

Which vehicles: those of the scenario's `emergency_vehicle_type`, known from the flow file
(trafficsense.sim.vehicles). CityFlow has no notion of emergency vehicles: they do not
overtake (lane_change is off) and nobody yields to them, so only the signal can help.

Detection (`detect`), used by the preemption baseline and by llm_guided_mp: an ambulance on an
incoming lane of the intersection within `range_m` of the stop line. Distance to the stop
line = lane length - distance driven on the lane (CityFlow's get_vehicle_info). Lane length =
road polyline length minus the width of the intersections at both ends (CityFlow trims lanes
by the intersection width; checked against stopped vehicles in tests). Its movement is read
from its route (current road -> next road). Ambulances on a free turn (served in every
phase) are not reported: the signal cannot help them.

Metrics (`EmergencyTracker`, fed by MetricsTracker every step):
  travel time  finish time - scheduled start (flow file startTime), as CityFlow's ATT counts
               time: entry delay included. Only for ambulances that finished in the run.
  stopped time seconds with speed < 0.1 m/s while in the network.
  entry wait   first step in the network - scheduled start.
Ambulances still in the network at the end are listed with their time so far, and not in the
means.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from trafficsense.sim.env import TrafficEnv

STOP_SPEED = 0.1
FREE_TURN = "turn_right"


def lane_lengths(roadnet_path: str | Path) -> dict[str, float]:
    raw = json.loads(Path(roadnet_path).read_text())
    width = {i["id"]: float(i["width"]) for i in raw["intersections"]}
    out = {}
    for r in raw["roads"]:
        pts = [(p["x"], p["y"]) for p in r["points"]]
        length = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
        length -= width[r["startIntersection"]] + width[r["endIntersection"]]
        for k in range(len(r["lanes"])):
            out[f"{r['id']}_{k}"] = length
    return out


@dataclass(frozen=True)
class Sighting:
    vehicle: str
    intersection: str
    lane: str
    distance_m: float          # to the stop line
    movement: int              # index into the intersection's movements
    approach: str
    turn: str
    serving_phases: tuple[int, ...]   # green phases that serve the movement


class EmergencyVehicles:
    """Ids and scheduled starts of the emergency vehicles of `env`'s flow, plus detection."""

    def __init__(self, env: TrafficEnv):
        if env.emergency_type is None:
            raise ValueError(f"Scenario {env.scenario} has no emergency_vehicle_type")
        flows = json.loads(env.flow_path.read_text())
        vt = env.vehicle_types
        self.type = env.emergency_type
        self.start = {f"flow_{i}_0": int(f["startTime"]) for i, f in enumerate(flows)
                      if vt.of(f"flow_{i}_0") == self.type}
        self.route = {f"flow_{i}_0": f["route"] for i, f in enumerate(flows) if f"flow_{i}_0" in self.start}
        self.lane_length = lane_lengths(env.roadnet_path)

    def detect(self, env: TrafficEnv, iid: str, range_m: float) -> list[Sighting]:
        inter = env.intersection(iid)
        lane_veh = env.eng.get_lane_vehicles()
        out = []
        for lane in inter.incoming_lanes:
            for v in lane_veh[lane]:
                if v not in self.start:
                    continue
                info = env.eng.get_vehicle_info(v)
                dist = self.lane_length[lane] - float(info["distance"])
                if dist > range_m:
                    continue
                route = self.route[v]
                road = info["road"]
                nxt = route[route.index(road) + 1]
                m = next(m for m in inter.movements if m.in_road == road and m.out_road == nxt)
                if m.turn == FREE_TURN:
                    continue
                serving = tuple(p.index for p in inter.green_phases if m.index in p.movements)
                out.append(Sighting(v, iid, lane, round(dist, 1), m.index, m.approach, m.turn, serving))
        return sorted(out, key=lambda s: s.distance_m)


class EmergencyTracker:
    def __init__(self, env: TrafficEnv):
        self.env = env
        self.ev = EmergencyVehicles(env)
        self.entered: dict[str, float] = {}
        self.finished: dict[str, float] = {}
        self.stopped: dict[str, float] = {}

    def update(self, running: set[str], prev_running: set[str], speed: dict[str, float], t: float, dt: float) -> None:
        for v in self.ev.start:
            if v in running:
                self.entered.setdefault(v, t)
                if speed[v] < STOP_SPEED:
                    self.stopped[v] = self.stopped.get(v, 0.0) + dt
            elif v in prev_running and v not in self.finished:
                self.finished[v] = t

    def summary(self, end_time: float) -> dict[str, Any]:
        rows = []
        for v, s in sorted(self.ev.start.items(), key=lambda x: (x[1], x[0])):
            if s >= end_time:
                continue
            fin = self.finished.get(v)
            rows.append({"vehicle": v, "scheduled_start": s, "entered": self.entered.get(v), "finished": fin,
                         "travel_time_s": None if fin is None else fin - s,
                         "time_so_far_s": None if fin is not None else end_time - s,
                         "stopped_s": self.stopped.get(v, 0.0) if v in self.entered else None,
                         "entry_wait_s": None if v not in self.entered else self.entered[v] - s,
                         "route": self.ev.route[v]})
        done = [r for r in rows if r["finished"] is not None]

        def mean(k, rs):
            return float(np.mean([r[k] for r in rs])) if rs else None
        return {
            "vehicle_type": self.ev.type,
            "scheduled_in_run": len(rows),
            "entered": sum(1 for r in rows if r["entered"] is not None),
            "finished": len(done),
            "travel_time_mean_s": mean("travel_time_s", done),
            "stopped_time_mean_s": mean("stopped_s", done),
            "entry_wait_mean_s": mean("entry_wait_s", done),
            "vehicles": rows,
            "notes": "means over ambulances that finished in the run; travel time from scheduled start "
                     "(incl. entry wait); stopped = speed < 0.1 m/s while in the network",
        }
