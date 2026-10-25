"""The prompts shown in the report's appendix, rendered by the controllers' own code.

System prompts: `prompt.messages` fills each version's template with the timing from
configs/default.yaml. User message: one real simulator state. The Indian 2x2 peak scenario
with ambulances (seed 2) is run under MaxPressure, which is deterministic, to t = EXAMPLE_T; the
observation for intersection EXAMPLE_IID is then built exactly as `llm_guarded_mp` builds it
(MaxPressure's ranking, its top 2 plus keeping the current phase, ambulances within range) and
rendered with the guided_v3 prompt. No LLM is called."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from trafficsense.config import load_config
from trafficsense.control.maxpressure import MaxPressureController, phase_pressures
from trafficsense.control.guided import mp_ranking
from trafficsense.llm import prompt
from trafficsense.sim.emergency import EmergencyVehicles
from trafficsense.sim.env import TrafficEnv

# The first decision of EXAMPLE["iid"] from t0 on at which an ambulance is in range: on the 5 s
# decision grid, with the minimum green met (the moments at which the LLM arms are asked).
EXAMPLE = {"scenario": "indian_2x2_peak_amb", "seed": 2, "t0": 250, "t_max": 900, "iid": "intersection_2_2"}


def system_prompts(root: Path) -> dict[str, str]:
    """Each version's system prompt, filled by `prompt.messages` from the example's observation
    (the timing of the LLM runs: 5 s transition, the tuned min green, max green)."""
    obs = example_observation(root)
    plain = {k: v for k, v in obs.items() if k != "ambulances"}
    out = {v: prompt.messages(plain, v)[0]["content"] for v in ("v1", "v2", "v3", "guided", "guided_v3")}
    out["guided_v3, emergency scenario"] = prompt.messages(obs, "guided_v3")[0]["content"]
    return out


def example_user_message(root: Path) -> str:
    return prompt.messages(example_observation(root), "guided_v3")[1]["content"]


@lru_cache(maxsize=1)
def example_observation(root: Path) -> dict:
    cfg = load_config(root / "configs/default.yaml")
    env = TrafficEnv(cfg, EXAMPLE["scenario"], seed=EXAMPLE["seed"])
    mp = MaxPressureController(cfg)
    iid = EXAMPLE["iid"]
    interval = int(cfg["controllers"]["maxpressure"]["decision_interval"])
    rng = float(cfg["emergency"]["detection_range_m"])
    ev = EmergencyVehicles(env)
    while True:
        t = int(env.time)
        if (t >= EXAMPLE["t0"] and t % interval == 0
                and env.time_in_phase(iid) >= int(cfg["controllers"]["maxpressure"]["min_green"])
                and ev.detect(env, iid, rng)):
            break
        if t >= EXAMPLE["t_max"]:
            raise RuntimeError("no decision with an ambulance in range in the example window")
        mp.act(env)
        env.step()
    c = cfg["controllers"]["llm_guarded_mp"]
    min_green = int(cfg["controllers"]["maxpressure"]["min_green"])
    cur = env.signals[iid].green_phase
    near_max = env.time_in_phase(iid) + int(cfg["controllers"]["maxpressure"]["decision_interval"]) >= env.max_green
    pressures = phase_pressures(env.intersection(iid), env.get_state(iid))
    ranking = mp_ranking(pressures, cur, near_max, c["tie_break"])
    options = ranking[:int(c["options"])]
    if not near_max and cur not in options:
        options.append(cur)
    ambulances = []
    inter = env.intersection(iid)
    for sg in ev.detect(env, iid, rng):
        serving = [p for p in ranking if p in sg.serving_phases]
        if serving and serving[0] not in options:
            options.append(serving[0])
        ambulances.append({"vehicle": sg.vehicle, "approach": sg.approach, "distance_m": sg.distance_m,
                           "movement": prompt.movement_label(inter.movements[sg.movement]), "phases": serving})
    obs = prompt.observe(env, iid, options, c["mode"], min_green)
    obs["ranking"] = ranking
    obs["emergency_range_m"] = rng
    obs["example_time_s"] = t
    obs["ambulances"] = ambulances
    return obs
