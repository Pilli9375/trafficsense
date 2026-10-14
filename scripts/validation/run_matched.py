"""Run our env + controllers with CoLLMLight-matched (or default) settings and score the run
with BOTH our metrics and CoLLMLight's metric definitions.

Profiles:
  default_fixedtime / default_fixedtime_all_phases / default_maxpressure
                        our configs/default.yaml settings
  matched_fixedtime     4 paired phases, 30 s green, switch checked on a 30 s grid
  matched_maxpressure   4 paired phases, decision every 30 s, np.argmax tie-break, no max green
  replica_fixedtime     matched_fixedtime but cycling phases 1 and 3 only, which is what
                        CoLLMLight's FixedtimeAgent actually does (index off-by-one, see docs)
matched_* and replica_* use laneChange=true like CoLLMLight. Pass --engine-seed to reuse the
CityFlow seed their run drew (recorded in outputs/validation/collmlight/*.json).
Output: outputs/validation/ours/<scenario>_<profile>_s<seed>.json
"""
import argparse
import copy
import json
import sys
from datetime import datetime
from pathlib import Path

from trafficsense.config import load_config, repo_root
from trafficsense.control import make_controller
from trafficsense.experiment import git_info
from trafficsense.sim.env import TrafficEnv
from trafficsense.sim.metrics import MetricsTracker

sys.path.insert(0, str(Path(__file__).resolve().parent))   # sibling validation module
from collmlight_metrics import CoLLMLightMetrics  # noqa: E402

PROFILES = ("default_fixedtime", "default_fixedtime_all_phases", "default_maxpressure", "matched_fixedtime",
            "matched_maxpressure", "replica_fixedtime")


def build(cfg, profile, seed):
    cfg = copy.deepcopy(cfg)
    cfg["sim"]["seed"] = seed
    if profile.startswith("default_"):
        return cfg, profile.removeprefix("default_")
    cfg["sim"]["lane_change"] = True
    cfg["signal"] = {"min_green": 10, "max_green": 3600}     # their env has no max green
    cfg["controllers"]["fixedtime"] = {"green_time": 30, "phases": "paired", "decision_interval": 30}
    cfg["controllers"]["maxpressure"] = {"decision_interval": 30, "phases": "paired",
                                         "tie_break": "lowest_index"}
    return cfg, "maxpressure" if profile == "matched_maxpressure" else "fixedtime"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--profile", required=True, choices=PROFILES)
    ap.add_argument("--engine-seed", type=int, default=0)
    ap.add_argument("--steps", type=int, default=3600)
    args = ap.parse_args()

    cfg, controller = build(load_config("configs/default.yaml"), args.profile, args.engine_seed)
    env = TrafficEnv(cfg, args.scenario)
    ctl = make_controller(controller, cfg)
    if args.profile == "replica_fixedtime":
        ctl._cycles = {iid: [1, 3] for iid in env.intersection_ids}
    ours, theirs = MetricsTracker(env), CoLLMLightMetrics(env)
    phase_log = {iid: [] for iid in env.intersection_ids}
    for t in range(args.steps):
        if t % 30 == 0:
            for iid in env.intersection_ids:
                phase_log[iid].append(env.signals[iid].green_phase)
        ctl.act(env)
        env.step()
        ours.update()
        theirs.update()

    out = {
        "source": "TrafficSense env + controllers, scripts/validation/run_matched.py",
        "git": git_info(),
        "scenario": args.scenario,
        "profile": args.profile,
        "controller_params": ctl.info(),
        "engine_config": {k: env.engine_config[k] for k in ("seed", "laneChange", "interval")},
        "signal": {"min_green": env.min_green, "max_green": env.max_green,
                   "switches": sum(s.switches for s in env.signals.values()),
                   "forced_switches": sum(s.forced_switches for s in env.signals.values())},
        "steps": args.steps,
        "trafficsense_metrics": ours.summary()["network"],
        "collmlight_metrics": theirs.summary(),
        "green_phase_every_30s_first_intersection": phase_log[env.intersection_ids[0]],
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    path = repo_root() / "outputs" / "validation" / "ours" / f"{args.scenario}_{args.profile}_s{args.engine_seed}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {path}")
    print(json.dumps({"collmlight_metrics": out["collmlight_metrics"],
                      "trafficsense_metrics": out["trafficsense_metrics"]}, indent=2))


if __name__ == "__main__":
    main()
