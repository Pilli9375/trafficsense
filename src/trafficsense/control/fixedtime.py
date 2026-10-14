"""Fixed-time control: cycle through a fixed list of green phases in index order.

`phases: paired` (default) cycles the opposing-approach phases that together serve every
non-right movement once (4 phases in the CoLLMLight roadnets); `phases: all` cycles every
green phase in the roadnet (8 phases, registered as controller `fixedtime_all_phases`).
`decision_interval` (default 1 s) only checks for a switch at multiples of that many seconds;
it exists to reproduce CoLLMLight's 30 s action grid.
"""
from __future__ import annotations

from typing import Any

from trafficsense.control.base import Controller
from trafficsense.sim.env import TrafficEnv
from trafficsense.sim.roadnet import Intersection

PHASE_SETS = ("paired", "all")


def phase_cycle(inter: Intersection, phases: str) -> list[int]:
    if phases == "paired":
        return [p.index for p in inter.paired_phases]
    if phases == "all":
        return [p.index for p in inter.green_phases]
    raise ValueError(f"Unknown phase set {phases!r}; expected one of {PHASE_SETS}")


class FixedTimeController(Controller):
    name = "fixedtime"

    def __init__(self, cfg: dict[str, Any], name: str = "fixedtime"):
        self.name = name
        c = cfg["controllers"][name]
        if c.get("green_time") is None:
            raise KeyError(f"Config is missing controllers.{name}.green_time")
        if c.get("phases") not in PHASE_SETS:
            raise ValueError(f"controllers.{name}.phases must be one of {PHASE_SETS}, got {c.get('phases')!r}")
        self.green_time = int(c["green_time"])
        self.phases = c["phases"]
        self.interval = int(c.get("decision_interval", 1))
        if self.interval <= 0:
            raise ValueError(f"decision_interval must be positive, got {self.interval}")
        lo, hi = cfg["signal"]["min_green"], cfg["signal"]["max_green"]
        if not lo <= self.green_time <= hi:
            raise ValueError(f"{name} green_time {self.green_time} outside [min_green {lo}, max_green {hi}]")
        self._cycles: dict[str, list[int]] = {}

    def act(self, env: TrafficEnv) -> None:
        if int(round(env.time)) % self.interval != 0:
            return
        for iid in env.intersection_ids:
            if env.in_transition(iid) or env.time_in_phase(iid) < self.green_time:
                continue
            if iid not in self._cycles:
                self._cycles[iid] = phase_cycle(env.intersection(iid), self.phases)
            cycle = self._cycles[iid]
            cur = env.signals[iid].green_phase
            # A current phase outside the cycle (e.g. the env's initial phase) restarts it.
            nxt = cycle[(cycle.index(cur) + 1) % len(cycle)] if cur in cycle else cycle[0]
            env.request_phase(iid, nxt)

    def info(self) -> dict[str, Any]:
        return {"name": self.name, "green_time": self.green_time, "phases": self.phases,
                "decision_interval": self.interval}
