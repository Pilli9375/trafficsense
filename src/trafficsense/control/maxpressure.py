"""Max-pressure control (Varaiya, 2013).

Pressure of a phase = sum over the movements it serves of
(waiting vehicles on the movement's incoming lanes - waiting vehicles on its outgoing lanes).
Every `decision_interval` seconds, each intersection that has met min_green switches to the
phase with the highest pressure. Ties keep the current phase, otherwise the lowest index wins.

The env forces a switch when a green reaches max_green. To keep the choice pressure-based,
the current phase is excluded when keeping it would reach max_green before the next decision;
with a 5 s interval and 60 s max_green this caps a max-pressure green at 55 s.
"""
from __future__ import annotations

from typing import Any

from trafficsense.control.base import Controller
from trafficsense.sim.env import TrafficEnv
from trafficsense.sim.roadnet import Intersection


def phase_pressures(inter: Intersection, state: dict[str, Any]) -> dict[int, float]:
    by_index = {m["index"]: m for m in state["movements"]}
    return {
        p.index: sum(by_index[k]["queue"] - by_index[k]["out_queue"] for k in p.movements)
        for p in inter.green_phases
    }


def choose_phase(pressures: dict[int, float], current: int, exclude_current: bool) -> int:
    cand = {p: v for p, v in pressures.items() if not (exclude_current and p == current)}
    best = max(cand.values())
    if current in cand and cand[current] == best:
        return current
    return min(p for p, v in cand.items() if v == best)


class MaxPressureController(Controller):
    name = "maxpressure"

    def __init__(self, cfg: dict[str, Any]):
        c = cfg["controllers"]["maxpressure"]
        if c.get("decision_interval") is None:
            raise KeyError("Config is missing controllers.maxpressure.decision_interval")
        self.interval = int(c["decision_interval"])
        if self.interval <= 0:
            raise ValueError(f"decision_interval must be positive, got {self.interval}")
        self.max_green = int(cfg["signal"]["max_green"])

    def act(self, env: TrafficEnv) -> None:
        if int(round(env.time)) % self.interval != 0:
            return
        for iid in env.intersection_ids:
            if not env.can_switch(iid):
                continue
            inter = env.intersection(iid)
            pressures = phase_pressures(inter, env.get_state(iid))
            near_max = env.time_in_phase(iid) + self.interval >= self.max_green
            env.request_phase(iid, choose_phase(pressures, env.signals[iid].green_phase, near_max))

    def info(self) -> dict[str, Any]:
        return {"name": self.name, "decision_interval": self.interval}
