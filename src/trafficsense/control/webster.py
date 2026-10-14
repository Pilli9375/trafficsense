"""Webster-tuned fixed-time control (Webster, 1958, Road Research Technical Paper 39).

Per intersection, a fixed cycle over the 4 paired phases (as `fixedtime`), with the cycle
length and green splits computed once, at the start of the run, by Webster's method from
quantities measured on this scenario:

  q_l  demand of incoming lane l (veh/h): vehicles routed over the lane in the flow file being
       run, over [0, demand_window_s) (trafficsense.sim.capacity.lane_demand). This equals a
       perfect traffic count of the simulated hour, which favours this controller.
  s_t  saturation flow (veh/h) and l_s start-up lost time (s) of a lane of turn type t
       (straight, protected turn), measured by queue discharge on the simulator with the flow
       file's own vehicle mix in random queue order, averaged over `measurement_reps` queues
       (trafficsense.sim.capacity.measure_discharge_mixed). s_t is the slope and l_s the time
       intercept of a straight line fitted to cumulative departures.
  y_i  = max over the non-right-turn lanes served by phase i of q_l / s_t(l)   (flow ratio;
       right turns run in every phase and are excluded, as in critical_flow_ratio)
  Y    = sum_i y_i                                           (critical flow ratio)
  L    = n * (T + l_s)                                       (lost time per cycle, s)
       n = number of phases, T = transition phase duration (read from the roadnet; it shows
       red to every non-right movement, so all of it is lost), l_s = mean of the measured
       start-up lost times of the turn types.
  C0   = (1.5 L + 5) / (1 - Y)                               (Webster's optimum cycle, s)
  C    = C0 clipped to [cycle_min, cycle_max]; if Y >= 1 there is no finite optimum and
       C = cycle_max (reported as `oversaturated`).
  G_i  = l_s + (C - L) * y_i / Y                             (displayed green, s: effective green
       (C - L) * y_i / Y plus the start-up loss it contains)
Each G_i is then clipped to [min_green, max_green] (the env enforces both); the green the
clipped phases gain or lose is shared among the others in proportion to y_i, repeating until
no phase is clipped. If Y = 0 every phase gets the same green. Greens are rounded to whole
seconds, so the cycle actually run is sum(G_i) + n * T; it is reported per intersection.
"""
from __future__ import annotations

import collections
import json
from typing import Any

from trafficsense.control.base import Controller
from trafficsense.control.fixedtime import phase_cycle
from trafficsense.sim.capacity import critical_flow_ratio, lane_demand, measure_discharge_mixed, turn_route
from trafficsense.sim.demand import VEHICLE_KEYS, Network
from trafficsense.sim.env import TrafficEnv
from trafficsense.sim.roadnet import Roadnet

TURNS = ("go_straight", "turn_left")
REQUIRED = ("cycle_min", "cycle_max", "demand_window_s", "measurement_reps", "measurement_seed")


def webster_cycle(Y: float, L: float, cycle_min: float, cycle_max: float) -> tuple[float | None, float]:
    """(C0, C): Webster's optimum cycle (None if Y >= 1) and the cycle used."""
    if Y >= 1:
        return None, float(cycle_max)
    c0 = (1.5 * L + 5) / (1 - Y)
    return c0, min(max(c0, cycle_min), cycle_max)


def split_greens(y: dict[int, float], cycle: float, transition: float, startup_lost: float,
                 min_green: float, max_green: float) -> dict[int, float]:
    """Displayed greens G_i (unrounded) for cycle C, clipped to [min_green, max_green] with the
    difference shared among unclipped phases in proportion to y_i (see module docstring)."""
    n = len(y)
    total = cycle - n * transition           # displayed green available in the cycle
    fixed: dict[int, float] = {}
    while True:
        free = [p for p in y if p not in fixed]
        if not free:
            return fixed
        avail = total - sum(fixed.values())
        y_free = sum(y[p] for p in free)
        # effective green of the free phases, shared by y (equally if they carry no demand)
        eff = avail - len(free) * startup_lost
        g = {p: startup_lost + eff * (y[p] / y_free if y_free > 0 else 1 / len(free)) for p in free}
        clip = {p: min(max(v, min_green), max_green) for p, v in g.items() if not min_green <= v <= max_green}
        if not clip:
            return {**fixed, **g}
        fixed.update(clip)


def flow_vehicle_types(flows: list[dict]) -> dict[str, dict[str, Any]]:
    """Distinct vehicle parameter sets in a flow file, with their share of vehicles."""
    c = collections.Counter(json.dumps({k: f["vehicle"][k] for k in VEHICLE_KEYS}, sort_keys=True) for f in flows)
    return {f"type_{i}": {**json.loads(k), "share": n} for i, (k, n) in enumerate(c.most_common())}


def measure_inputs(env: TrafficEnv, reps: int, seed: int) -> dict[str, Any]:
    """Saturation flow and start-up lost time per turn type, on this scenario's roadnet."""
    net: Roadnet = env.roadnet
    roads = json.loads(env.roadnet_path.read_text())["roads"]
    speeds = {lane["maxSpeed"] for r in roads for lane in r["lanes"]}
    if len(speeds) != 1:
        raise ValueError(f"Lanes have different speed limits {sorted(speeds)}; one saturation-flow "
                         "measurement per turn type would not represent all of them")
    flows = json.loads(env.flow_path.read_text())
    types = flow_vehicle_types(flows)
    if len(types) == 1:
        reps = 1   # one vehicle type: every queue order is the same, the measurement is exact
    entry = Network(net).entry_roads[0]
    out = {}
    for t in TURNS:
        out[t] = measure_discharge_mixed(env.roadnet_path, net, turn_route(net, entry, t), types,
                                         VEHICLE_KEYS, reps=reps, seed=seed)
    return {"vehicle_types": {k: v["share"] for k, v in types.items()}, "discharge": out}


class WebsterFixedTimeController(Controller):
    name = "fixedtime_webster"

    def __init__(self, cfg: dict[str, Any], name: str = "fixedtime_webster"):
        self.name = name
        if name not in cfg["controllers"]:
            raise KeyError(f"Config is missing controllers.{name}")
        c = cfg["controllers"][name]
        missing = [k for k in REQUIRED if c.get(k) is None]
        if missing:
            raise KeyError(f"Config is missing controllers.{name}.{missing}")
        self.cycle_min, self.cycle_max = float(c["cycle_min"]), float(c["cycle_max"])
        if not 0 < self.cycle_min <= self.cycle_max:
            raise ValueError(f"Need 0 < cycle_min <= cycle_max, got {self.cycle_min}, {self.cycle_max}")
        self.window = int(c["demand_window_s"])
        self.reps = int(c["measurement_reps"])
        self.seed = int(c["measurement_seed"])
        if self.window <= 0 or self.reps <= 0:
            raise ValueError("demand_window_s and measurement_reps must be positive")
        self.min_green = int(cfg["signal"]["min_green"])
        self.max_green = int(cfg["signal"]["max_green"])
        self.inputs: dict[str, Any] | None = None
        self.plans: dict[str, dict[str, Any]] = {}

    def plan(self, env: TrafficEnv) -> None:
        self.inputs = measure_inputs(env, self.reps, self.seed)
        d = self.inputs["discharge"]
        s = {t: d[t]["fit_saturation_flow_veh_per_hour"] for t in TURNS}
        startup = sum(d[t]["startup_lost_time_s"] for t in TURNS) / len(TURNS)
        if startup < 0:
            raise ValueError(f"Measured start-up lost time is negative ({startup:.2f} s)")
        self.inputs["saturation_flow_veh_per_hour"] = s
        self.inputs["startup_lost_time_s"] = startup

        flows = json.loads(env.flow_path.read_text())
        if any(f["startTime"] != f["endTime"] for f in flows):
            raise ValueError("Webster demand needs one vehicle per flow entry (startTime == endTime)")
        used = [f for f in flows if f["startTime"] < self.window]
        self.inputs["demand_window_s"] = self.window
        self.inputs["vehicles_in_window"] = len(used)
        demand = lane_demand(env.roadnet, used)
        ratio = {iid: {lane: (0.0 if v["turn"] == "turn_right"
                              else v["vehicles"] * 3600 / self.window / s[v["turn"]])
                       for lane, v in lanes.items()} for iid, lanes in demand.items()}
        y_all = critical_flow_ratio(env.roadnet, ratio)
        for iid in env.intersection_ids:
            T = env.transition_time[iid]
            cycle = phase_cycle(env.intersection(iid), "paired")
            y = {p: y_all[iid]["per_phase_max_ratio"][p] for p in cycle}
            Y = sum(y.values())
            L = len(cycle) * (T + startup)
            c0, c = webster_cycle(Y, L, self.cycle_min, self.cycle_max)
            g = split_greens(y, c, T, startup, self.min_green, self.max_green)
            greens = {p: int(round(g[p])) for p in cycle}
            self.plans[iid] = {
                "phases": cycle, "y": y, "Y": Y, "lost_time_L_s": L, "C0_s": c0, "cycle_webster_s": c,
                "oversaturated": c0 is None,
                "cycle_clipped": c0 is not None and c != c0,
                "greens_unrounded_s": g, "greens_s": greens,
                "greens_clipped": [p for p in cycle if g[p] in (self.min_green, self.max_green)],
                "cycle_run_s": sum(greens.values()) + len(cycle) * T,
            }

    def act(self, env: TrafficEnv) -> None:
        if not self.plans:
            self.plan(env)
        for iid in env.intersection_ids:
            p = self.plans[iid]
            cur = env.signals[iid].green_phase
            if env.in_transition(iid):
                continue
            if cur not in p["phases"]:
                # the env's initial phase is outside the cycle: start the cycle once allowed
                if env.can_switch(iid):
                    env.request_phase(iid, p["phases"][0])
                continue
            if env.time_in_phase(iid) >= p["greens_s"][cur]:
                k = p["phases"].index(cur)
                env.request_phase(iid, p["phases"][(k + 1) % len(p["phases"])])

    def info(self) -> dict[str, Any]:
        return {"name": self.name, "phases": "paired", "cycle_min": self.cycle_min, "cycle_max": self.cycle_max,
                "demand_window_s": self.window, "measurement_reps": self.reps,
                "measurement_seed": self.seed, "inputs": self.inputs, "plans": self.plans}
