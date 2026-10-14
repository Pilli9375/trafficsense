"""MaxPressure with rule-based ambulance preemption (`preemption_mp`): the non-LLM baseline
for emergency vehicles.

Same timing and pressures as MaxPressure (decision grid, own min green, current phase left
out near max green). At a decision, if an ambulance is on an incoming lane within
emergency.detection_range_m of the stop line (sim/emergency.py; not on a free turn), the
nearest one gets green: among the green phases that serve its movement, the one with the
highest pressure (ties: keep current, then lowest index). Keeping the current phase when it
already serves the ambulance is part of that rule. Otherwise it is plain MaxPressure.

It sees exactly what llm_guided_mp is told about ambulances (same detection and range) and
acts on the same 5 s grid after the same min green, so the two differ only in the decision.
It does not cut a green short before min green, and does not hold green beyond max green.
Each preemption is logged to preemptions.jsonl; the count goes to summary.json
(provenance.controller_stats).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from trafficsense.control.maxpressure import MaxPressureController, choose_phase
from trafficsense.sim.emergency import EmergencyVehicles
from trafficsense.sim.env import TrafficEnv


class PreemptionMPController(MaxPressureController):
    def __init__(self, cfg: dict[str, Any], name: str = "preemption_mp"):
        super().__init__(cfg, name)
        if cfg.get("emergency", {}).get("detection_range_m") is None:
            raise KeyError("Config is missing emergency.detection_range_m")
        self.range_m = float(cfg["emergency"]["detection_range_m"])
        self._ev: EmergencyVehicles | None = None
        self.log: list[dict[str, Any]] = []

    def _choose(self, env: TrafficEnv, iid: str) -> int:
        if env.emergency_type is None:
            return super()._choose(env, iid)
        if self._ev is None:
            self._ev = EmergencyVehicles(env)
        seen = self._ev.detect(env, iid, self.range_m)
        cur = env.signals[iid].green_phase
        near_max = env.time_in_phase(iid) + self.interval >= self.max_green
        pressures = self._pressures(env, iid)
        mp = choose_phase(pressures, cur, near_max, self.tie_break)
        if not seen:
            return mp
        s = seen[0]
        cand = {p: pressures[p] for p in s.serving_phases if p in pressures and not (near_max and p == cur)}
        if not cand:
            return mp
        phase = choose_phase(cand, cur, False, self.tie_break)
        self.log.append({"step": int(env.time), "intersection": iid, "vehicle": s.vehicle, "distance_m": s.distance_m,
                         "approach": s.approach, "turn": s.turn, "current_phase": cur, "phase": phase,
                         "maxpressure_choice": mp, "changed_decision": phase != mp})
        return phase

    def info(self) -> dict[str, Any]:
        return {**super().info(), "detection_range_m": self.range_m}

    def provenance(self) -> dict[str, Any]:
        return {"controller_stats": {"preemption_decisions": len(self.log),
                                     "changed_maxpressure_decision": sum(1 for x in self.log if x["changed_decision"]),
                                     "log": "preemptions.jsonl"}}

    def write_artifacts(self, out_dir: Path) -> None:
        with (out_dir / "preemptions.jsonl").open("w", encoding="utf-8") as f:
            for rec in self.log:
                f.write(json.dumps(rec) + "\n")
