"""Fixed-time control: cycle through the roadnet's green phases in index order."""
from __future__ import annotations

from typing import Any

from trafficsense.control.base import Controller
from trafficsense.sim.env import TrafficEnv


class FixedTimeController(Controller):
    name = "fixedtime"

    def __init__(self, cfg: dict[str, Any]):
        c = cfg["controllers"]["fixedtime"]
        if c.get("green_time") is None:
            raise KeyError("Config is missing controllers.fixedtime.green_time")
        self.green_time = int(c["green_time"])
        lo, hi = cfg["signal"]["min_green"], cfg["signal"]["max_green"]
        if not lo <= self.green_time <= hi:
            raise ValueError(f"fixedtime green_time {self.green_time} outside [min_green {lo}, max_green {hi}]")

    def act(self, env: TrafficEnv) -> None:
        for iid in env.intersection_ids:
            if env.in_transition(iid) or env.time_in_phase(iid) < self.green_time:
                continue
            greens = [p.index for p in env.intersection(iid).green_phases]
            cur = env.signals[iid].green_phase
            env.request_phase(iid, greens[(greens.index(cur) + 1) % len(greens)])

    def info(self) -> dict[str, Any]:
        return {"name": self.name, "green_time": self.green_time}
