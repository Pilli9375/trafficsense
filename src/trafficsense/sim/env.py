"""CityFlow engine wrapper: per-intersection state and signal timing.

CityFlow's set_tl_phase switches instantly, so this wrapper owns the signal logic:
  * a switch to a different green phase first shows the intersection's transition
    phase (read from the roadnet) for its full duration;
  * a green phase cannot be left before min_green;
  * a green phase that reaches max_green is ended by the wrapper, which switches to the
    next green phase in index order. Such forced switches are counted and reported.
"""
from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cityflow
import yaml

from trafficsense.config import repo_root, resolve_path
from trafficsense.sim.observation import make_observer
from trafficsense.sim.roadnet import Intersection, Roadnet, load_roadnet
from trafficsense.sim.vehicles import VehicleTypes


@dataclass
class SignalState:
    green_phase: int            # current green, or the green being switched to during a transition
    in_transition: bool = False
    transition_left: int = 0    # steps of transition still to show
    time_in_phase: int = 0      # seconds the current green has been shown
    forced_switches: int = 0
    switches: int = 0


def _require(section: dict[str, Any], key: str, where: str) -> Any:
    if key not in section or section[key] is None:
        raise KeyError(f"Config is missing {where}.{key}")
    return section[key]


class TrafficEnv:
    def __init__(self, cfg: dict[str, Any], scenario: str, seed: int | None = None,
                 replay_dir: Path | None = None):
        """`replay_dir`: if given, CityFlow writes its replay log (vehicle positions per step) and
        roadnet log there (used by sim/replay.py only; logging does not change the run)."""
        if scenario not in cfg.get("scenarios", {}):
            raise KeyError(f"Unknown scenario {scenario!r}; known: {list(cfg.get('scenarios', {}))}")
        sc = cfg["scenarios"][scenario]
        sim = cfg["sim"]
        sig = cfg["signal"]

        self.scenario = scenario
        self.interval = float(_require(sim, "interval", "sim"))
        if self.interval != 1.0:
            # Timing below counts steps as seconds.
            raise ValueError(f"sim.interval must be 1.0, got {self.interval}")
        self.seed = int(seed if seed is not None else _require(sim, "seed", "sim"))
        self.min_green = int(_require(sig, "min_green", "signal"))
        self.max_green = int(_require(sig, "max_green", "signal"))
        if not 0 < self.min_green <= self.max_green:
            raise ValueError(f"Need 0 < min_green <= max_green, got {self.min_green}, {self.max_green}")

        root = repo_root()
        self.roadnet_path = (root / _require(sc, "roadnet", f"scenarios.{scenario}")).resolve()
        # A flow path may contain "{seed}": generated scenarios have one flow file per seed.
        flow = str(_require(sc, "flow", f"scenarios.{scenario}"))
        self.flow_per_seed = "{seed}" in flow
        self.flow_path = (root / flow.format(seed=self.seed)).resolve()
        for p in (self.roadnet_path, self.flow_path):
            if not p.is_file():
                hint = sc.get("generate_hint", "")
                raise FileNotFoundError(f"Scenario file not found: {p}" + (f" ({hint})" if hint else ""))

        vt = sc.get("vehicle_types")
        self.vehicle_types_path = (root / vt).resolve() if vt else None
        if self.vehicle_types_path is not None and not self.vehicle_types_path.is_file():
            raise FileNotFoundError(f"scenarios.{scenario}.vehicle_types not found: {self.vehicle_types_path}")
        self._vehicle_types: VehicleTypes | None = None
        # Vehicle type tracked as an emergency vehicle (summary.json `emergency`); needs named types.
        self.emergency_type: str | None = sc.get("emergency_vehicle_type")
        if self.emergency_type is not None and self.vehicle_types_path is None:
            raise KeyError(f"scenarios.{scenario}: emergency_vehicle_type needs vehicle_types")

        self.roadnet: Roadnet = load_roadnet(self.roadnet_path)
        self.transition_time: dict[str, int] = {}
        for iid, inter in self.roadnet.intersections.items():
            t = inter.transition_phase.duration
            if t != int(t) or t <= 0:
                raise ValueError(f"{iid}: transition duration {t} is not a positive whole number")
            self.transition_time[iid] = int(t)

        engine_cfg = {
            "interval": self.interval,
            "seed": self.seed,
            "dir": "",
            "roadnetFile": str(self.roadnet_path),
            "flowFile": str(self.flow_path),
            "rlTrafficLight": True,
            "laneChange": bool(_require(sim, "lane_change", "sim")),
            "saveReplay": replay_dir is not None,
            "roadnetLogFile": str(Path(replay_dir).resolve() / "roadnet_log.json") if replay_dir else "",
            "replayLogFile": str(Path(replay_dir).resolve() / "replay_log.txt") if replay_dir else "",
        }
        # CityFlow only reads its config at construction, so a temp file is enough.
        with tempfile.TemporaryDirectory() as tmp:
            cfg_file = Path(tmp) / "cityflow_config.json"
            cfg_file.write_text(json.dumps(engine_cfg), encoding="utf-8")
            self.eng = cityflow.Engine(str(cfg_file), thread_num=int(_require(sim, "threads", "sim")))
        self.engine_config = engine_cfg

        self.signals: dict[str, SignalState] = {}
        for iid, inter in self.roadnet.intersections.items():
            first = inter.green_phases[0].index
            self.eng.set_tl_phase(iid, first)
            self.signals[iid] = SignalState(green_phase=first)

        # What controllers observe (sim/observation.py): exact by default; with camera errors
        # for the camera-error experiment. Metrics always read the engine directly.
        ocfg = cfg.get("observation")
        em = resolve_path(cfg, "camera_error_model") if "camera_error_model" in cfg.get("paths", {}) else None
        self.observer = make_observer(self, ocfg, em, self.seed)

    # ---- topology -------------------------------------------------------------------
    @property
    def intersection_ids(self) -> list[str]:
        return self.roadnet.ids

    def intersection(self, iid: str) -> Intersection:
        return self.roadnet.intersections[iid]

    # ---- time -----------------------------------------------------------------------
    @property
    def time(self) -> float:
        return self.eng.get_current_time()

    def step(self) -> None:
        # Phase in force while the simulator advances; current_phase() read after step()
        # already describes the NEXT step (e.g. the green that follows a finished transition).
        self._shown = {iid: self.current_phase(iid) for iid in self.signals}
        self.eng.next_step()
        for iid, s in self.signals.items():
            if s.in_transition:
                s.transition_left -= 1
                if s.transition_left <= 0:
                    s.in_transition = False
                    s.time_in_phase = 0
                    self.eng.set_tl_phase(iid, s.green_phase)
            else:
                s.time_in_phase += 1
                if s.time_in_phase >= self.max_green:
                    greens = [p.index for p in self.intersection(iid).green_phases]
                    nxt = greens[(greens.index(s.green_phase) + 1) % len(greens)]
                    self._start_transition(iid, nxt)
                    s.forced_switches += 1

    # ---- signal control -------------------------------------------------------------
    def current_phase(self, iid: str) -> int:
        """Phase index currently shown by the simulator (transition phase during a switch)."""
        s = self.signals[iid]
        return self.intersection(iid).transition_phase.index if s.in_transition else s.green_phase

    def shown_phase(self, iid: str) -> int:
        """Phase the simulator showed during the last step()."""
        if not hasattr(self, "_shown"):
            raise RuntimeError("shown_phase() called before the first step()")
        return self._shown[iid]

    def time_in_phase(self, iid: str) -> int:
        return self.signals[iid].time_in_phase

    def in_transition(self, iid: str) -> bool:
        return self.signals[iid].in_transition

    def can_switch(self, iid: str) -> bool:
        s = self.signals[iid]
        return not s.in_transition and s.time_in_phase >= self.min_green

    def request_phase(self, iid: str, phase: int) -> bool:
        """Ask for a green phase. Returns True if a switch was started, False if `phase` is
        already showing. Raises if the phase is not a green phase or a switch is not allowed
        yet (in transition, or min_green not reached)."""
        greens = {p.index for p in self.intersection(iid).green_phases}
        if phase not in greens:
            raise ValueError(f"{iid}: phase {phase} is not a green phase (greens: {sorted(greens)})")
        s = self.signals[iid]
        if s.in_transition:
            raise RuntimeError(f"{iid}: phase requested during a transition")
        if phase == s.green_phase:
            return False
        if s.time_in_phase < self.min_green:
            raise RuntimeError(
                f"{iid}: switch requested after {s.time_in_phase}s of green; min_green is {self.min_green}s"
            )
        self._start_transition(iid, phase)
        return True

    def _start_transition(self, iid: str, target: int) -> None:
        s = self.signals[iid]
        s.in_transition = True
        s.transition_left = self.transition_time[iid]
        s.green_phase = target
        s.switches += 1
        self.eng.set_tl_phase(iid, self.intersection(iid).transition_phase.index)

    # ---- observation ----------------------------------------------------------------
    @property
    def vehicle_types(self) -> VehicleTypes:
        """Type of each vehicle, from the flow file (named by scenarios.<name>.vehicle_types)."""
        if self._vehicle_types is None:
            named = None
            if self.vehicle_types_path is not None:
                with self.vehicle_types_path.open(encoding="utf-8") as f:
                    sc = yaml.safe_load(f)
                named = {**sc["vehicle_types"], **sc.get("emergency_vehicle_types", {})}
            self._vehicle_types = VehicleTypes(self.flow_path, named)
            if self.emergency_type is not None and self.emergency_type not in self._vehicle_types.names:
                raise KeyError(f"emergency_vehicle_type {self.emergency_type!r} is not a named vehicle type")
        return self._vehicle_types

    @property
    def emergency_types(self) -> list[str]:
        """Names of the scenario's emergency vehicle types (never noised by the observer)."""
        if self.vehicle_types_path is None:
            return []
        with self.vehicle_types_path.open(encoding="utf-8") as f:
            return list(yaml.safe_load(f).get("emergency_vehicle_types", {}))

    def lane_view(self):
        """Lane counts as the controllers see them now (exact, or with camera errors)."""
        return self.observer.view()

    def get_state(self, iid: str) -> dict[str, Any]:
        """Per-movement counts for one intersection, computed only from its own lanes, as
        observed (lane_view)."""
        inter = self.intersection(iid)
        view = self.lane_view()
        waiting, count = view.waiting, view.count
        movements = []
        for m in inter.movements:
            movements.append({
                "index": m.index,
                "name": m.name,
                "approach": m.approach,
                "turn": m.turn,
                "queue": sum(waiting[l] for l in m.in_lanes),
                "vehicles": sum(count[l] for l in m.in_lanes),
                "out_queue": sum(waiting[l] for l in m.out_lanes),
            })
        return {
            "intersection": iid,
            "time": self.time,
            "phase": self.current_phase(iid),
            "green_phase": self.signals[iid].green_phase,
            "in_transition": self.signals[iid].in_transition,
            "time_in_phase": self.signals[iid].time_in_phase,
            "movements": movements,
        }
