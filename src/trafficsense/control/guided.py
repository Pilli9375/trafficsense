"""LLM-guided MaxPressure (`llm_guided_mp`): MaxPressure proposes, the LLM picks.

At each decision (same grid and timing as LLMController: llm.decision_interval, llm.min_green)
MaxPressure ranks the green phases by pressure (control/maxpressure.py; ties as its
`tie_break`, with the current phase left out when keeping it would reach max green). The LLM
is offered MaxPressure's top `options` phases (2) and keeping the current phase, which is
always allowed here because an intersection is only asked once min green is met, unless max
green is near. It sees those options with pressure and queue plus, in cooperative mode, the
neighbours (prompt version "guided"), and answers with one of them and a reason.

Emergency scenarios (env.emergency_type set): ambulances detected on the intersection's incoming
lanes within emergency.detection_range_m (sim/emergency.py, the same detection as the
preemption baseline) are listed in the prompt (approach, movement, distance, the phases that
serve it), the system prompt adds that listed ambulances must get through quickly, and the
best-ranked phase serving each such ambulance is added to the options if it is not there yet
(otherwise the LLM could not act on what it is told).

On a failed call (timeout, server error, invalid answer) MaxPressure's top choice is applied
and the failure is counted by type; LLMUnavailable and `max_consecutive_failures` failures in
a row stop the run, as for the other LLM controllers.

Each decision in decisions.jsonl records MaxPressure's ranking and top choice, and whether the
LLM disagreed with it; summary.json gets the disagreement counts.
"""
from __future__ import annotations

from typing import Any

from trafficsense.control.llm import LLMControllerBase
from trafficsense.control.maxpressure import TIE_BREAKS, phase_pressures
from trafficsense.llm import prompt
from trafficsense.sim.emergency import EmergencyVehicles
from trafficsense.sim.env import TrafficEnv


def mp_ranking(pressures: dict[int, float], current: int, exclude_current: bool,
               tie_break: str = "keep_current") -> list[int]:
    """Phases best first, as MaxPressure would choose: highest pressure; among equals the
    current phase first (keep_current), then the lowest index. ranking[0] == choose_phase()."""
    cand = [p for p in pressures if not (exclude_current and p == current)]
    return sorted(cand, key=lambda p: (-pressures[p], not (tie_break == "keep_current" and p == current), p))


class LLMGuidedMPController(LLMControllerBase):
    PROMPTS = ("guided", "guided_v3")

    def __init__(self, cfg: dict[str, Any], name: str = "llm_guided_mp", client: Any = None):
        super().__init__(cfg, name, client)
        c = cfg["controllers"][name]
        self.n_options = int(c.get("options", 0))
        if self.n_options < 2:
            raise ValueError(f"controllers.{name}.options must be >= 2, got {c.get('options')!r}")
        self.tie_break = c.get("tie_break")
        if self.tie_break not in TIE_BREAKS:
            raise ValueError(f"controllers.{name}.tie_break must be one of {TIE_BREAKS}, got {self.tie_break!r}")
        if cfg.get("emergency", {}).get("detection_range_m") is None:
            raise KeyError("Config is missing emergency.detection_range_m")
        self.range_m = float(cfg["emergency"]["detection_range_m"])
        self._ev: EmergencyVehicles | None = None

    def act(self, env: TrafficEnv) -> None:
        for iid in self._due(env):
            self._decide(env, iid)

    def _decide(self, env: TrafficEnv, iid: str) -> None:
        cur = env.signals[iid].green_phase
        near_max = env.time_in_phase(iid) + self.interval >= self.max_green
        pressures = phase_pressures(env.intersection(iid), env.get_state(iid))
        ranking = mp_ranking(pressures, cur, near_max, self.tie_break)
        top = ranking[0]
        options = ranking[:self.n_options]
        if not near_max and cur not in options:
            options.append(cur)
        ambulances = []
        if env.emergency_type is not None:
            if self._ev is None:
                self._ev = EmergencyVehicles(env)
            inter = env.intersection(iid)
            for sg in self._ev.detect(env, iid, self.range_m):
                serving = [p for p in ranking if p in sg.serving_phases]
                if serving and serving[0] not in options:
                    options.append(serving[0])
                ambulances.append({"vehicle": sg.vehicle, "approach": sg.approach, "distance_m": sg.distance_m,
                                   "movement": prompt.movement_label(inter.movements[sg.movement]),
                                   "phases": serving})
        obs = prompt.observe(env, iid, options, self.mode, self.min_green)
        obs["ranking"] = ranking
        if env.emergency_type is not None:
            obs["emergency_range_m"] = self.range_m
            obs["ambulances"] = ambulances
        rec: dict[str, Any] = {"step": int(env.time), "intersection": iid, "current_phase": cur,
                               "time_in_phase": env.time_in_phase(iid), "allowed": sorted(options),
                               "mp_ranking": ranking, "mp_pressures": {str(p): pressures[p] for p in ranking},
                               "mp_choice": top}
        if ambulances:
            rec["ambulances"] = ambulances
        out = self._ask(obs, options, rec)
        phase = top if out is None else out[0]
        switched = env.request_phase(iid, phase)
        if ambulances:
            rec["serves_nearest_ambulance"] = phase in ambulances[0]["phases"]
        rec.update(phase=phase, disagrees_with_mp=None if out is None else phase != top,
                   action=("MaxPressure fallback (failure), " if out is None else "")
                   + ("switch" if switched else "keep"))
        self.decisions.append(rec)

    def stats(self) -> dict[str, Any]:
        st = super().stats()
        ok = [d for d in self.decisions if d["ok"]]
        dis = [d for d in ok if d["disagrees_with_mp"]]
        st.update(
            mp_disagreements=len(dis),
            mp_disagreement_rate=len(dis) / len(ok) if ok else None,
            mp_disagreements_kept_current=sum(1 for d in dis if d["phase"] == d["current_phase"]),
            mp_disagreements_chose_lower_ranked=sum(1 for d in dis if d["phase"] != d["current_phase"]),
            mp_fallbacks=len(self.decisions) - len(ok),
            mp_disagreement_note="over successful calls: LLM's phase != MaxPressure's top choice",
        )
        amb = [d for d in self.decisions if "ambulances" in d]
        if amb:
            st.update(ambulance_decisions=len(amb),
                      ambulance_decisions_serving_nearest=sum(1 for d in amb if d["serves_nearest_ambulance"]))
        # switches_requested in the base counts action == "switch" only; fallbacks also switch
        st["switches_requested"] = sum(1 for d in self.decisions if d["action"].endswith("switch"))
        return st

    def info(self) -> dict[str, Any]:
        return {**super().info(), "options": self.n_options, "tie_break": self.tie_break,
                "detection_range_m": self.range_m,
                "ranking": "maxpressure (phase_pressures over all green phases)"}
