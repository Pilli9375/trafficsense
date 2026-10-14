"""Max-pressure control (Varaiya, 2013).

Pressure of a phase = sum over the movements it serves of
(waiting vehicles on the movement's incoming lanes - waiting vehicles on its outgoing lanes).
Every `decision_interval` seconds, each intersection that has met min_green switches to the
phase with the highest pressure. Decisions fall on a fixed grid (simulation time a multiple of
the interval), as in CoLLMLight, so the shortest green actually possible is the first grid point
at least min_green after the transition: 10 s for a 5 s or 15 s interval, 15 s for 10 s and 20 s,
25 s for 30 s (with 5 s transitions). `phases` picks the candidate set (all green phases, or the 4
paired phases). With `tie_break: keep_current` a tie keeps the current phase, otherwise the
lowest index wins; `lowest_index` always takes the lowest index (as CoLLMLight's np.argmax).

`min_green` (optional, default signal.min_green) is the controller's own minimum green; it may
be longer than the env's signal.min_green, never shorter. It decouples the shortest green from
the decision grid: with a 5 s interval, the shortest green equals `min_green` exactly.

The env forces a switch when a green reaches max_green. To keep the choice pressure-based,
the current phase is excluded when keeping it would reach max_green before the next decision;
with a 5 s interval and 60 s max_green this caps a max-pressure green at 55 s.
"""
from __future__ import annotations

from typing import Any

from trafficsense.control.base import Controller
from trafficsense.control.fixedtime import PHASE_SETS, phase_cycle
from trafficsense.sim.env import TrafficEnv
from trafficsense.sim.roadnet import Intersection


TIE_BREAKS = ("keep_current", "lowest_index")


def phase_pressures(inter: Intersection, state: dict[str, Any],
                    candidates: list[int] | None = None) -> dict[int, float]:
    by_index = {m["index"]: m for m in state["movements"]}
    phases = [p for p in inter.green_phases if candidates is None or p.index in candidates]
    return {
        p.index: sum(by_index[k]["queue"] - by_index[k]["out_queue"] for k in p.movements)
        for p in phases
    }


def choose_phase(pressures: dict[int, float], current: int, exclude_current: bool,
                 tie_break: str = "keep_current") -> int:
    cand = {p: v for p, v in pressures.items() if not (exclude_current and p == current)}
    best = max(cand.values())
    if tie_break == "keep_current" and current in cand and cand[current] == best:
        return current
    return min(p for p, v in cand.items() if v == best)


class MaxPressureController(Controller):
    name = "maxpressure"

    def __init__(self, cfg: dict[str, Any], name: str = "maxpressure"):
        self.name = name
        if name not in cfg["controllers"]:
            raise KeyError(f"Config is missing controllers.{name}")
        c = cfg["controllers"][name]
        if c.get("decision_interval") is None:
            raise KeyError(f"Config is missing controllers.{name}.decision_interval")
        self.interval = int(c["decision_interval"])
        if self.interval <= 0:
            raise ValueError(f"decision_interval must be positive, got {self.interval}")
        self.phases = c.get("phases", "all")
        if self.phases not in PHASE_SETS:
            raise ValueError(f"{name}.phases must be one of {PHASE_SETS}, got {self.phases!r}")
        self.tie_break = c.get("tie_break", "keep_current")
        if self.tie_break not in TIE_BREAKS:
            raise ValueError(f"{name}.tie_break must be one of {TIE_BREAKS}, got {self.tie_break!r}")
        self.max_green = int(cfg["signal"]["max_green"])
        env_min = int(cfg["signal"]["min_green"])
        self.min_green = int(c.get("min_green", env_min))
        if not env_min <= self.min_green < self.max_green:
            raise ValueError(f"{name}.min_green must be in [signal.min_green {env_min}, max_green "
                             f"{self.max_green}), got {self.min_green}")
        self._candidates: dict[str, list[int]] = {}

    def act(self, env: TrafficEnv) -> None:
        if int(round(env.time)) % self.interval != 0:
            return
        for iid in env.intersection_ids:
            if not env.can_switch(iid) or env.time_in_phase(iid) < self.min_green:
                continue
            inter = env.intersection(iid)
            if iid not in self._candidates:
                self._candidates[iid] = phase_cycle(inter, self.phases)
            pressures = phase_pressures(inter, env.get_state(iid), self._candidates[iid])
            near_max = env.time_in_phase(iid) + self.interval >= self.max_green
            env.request_phase(iid, choose_phase(pressures, env.signals[iid].green_phase, near_max,
                                                self.tie_break))

    def info(self) -> dict[str, Any]:
        return {"name": self.name, "decision_interval": self.interval, "min_green": self.min_green,
                "phases": self.phases, "tie_break": self.tie_break}
