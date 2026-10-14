"""Tune MaxPressure's minimum green with the decision grid fixed at 5 s; pick one by a fixed rule.

    python scripts/tune_maxpressure_min_green.py                # run the sweep (needs a clean git tree)
    python scripts/tune_maxpressure_min_green.py --select-only  # recompute the selection from the runs

Why: the decision-interval sweep (scripts/tune_maxpressure.py) mostly varied how short a green
can be, because decisions fall on a grid. This sweep sets that directly. With a 5 s interval and
5 s transitions every green starts on the grid, so the shortest possible green equals min_green.

Sweep: controllers.maxpressure with decision_interval 5 s and min_green (controller-level, see
control/maxpressure.py) in {10, 15, 20, 25} s; every other setting as in configs/default.yaml
(env min green 10 s, max green 60 s, all 8 phases, keep_current tie-break), on
  jinan_3x4, hangzhou_4x4, indian_2x2_offpeak, indian_2x2_peak, seeds 0, 1, 2, 3600 steps.
Each run is a normal run_experiment() folder under outputs/baselines/maxpressure_min_green_sweep/mg<k>/.

Selection rule, fixed and committed BEFORE the sweep was run (the same rule as the
decision-interval sweep, trafficsense.selection):
  1. Each of the 4 scenarios counts once. Its score for a min_green is the mean ATT over the
     3 seeds.
  2. Within each scenario the settings are ranked by that score, 1 = lowest ATT
     (equal scores share the average rank).
  3. The chosen min_green has the lowest mean rank over the 4 scenarios.
  4. Tie-break: the lowest mean over scenarios of (score / best score in that scenario);
     if still tied, the shorter min_green.
Throughput and transition-time share are reported but not used for selection.

If the chosen setting differs from the current default MaxPressure (15 s interval, 10 s min
green), it becomes the default (controllers.maxpressure in configs/default.yaml, by hand).

Output: outputs/baselines/maxpressure_min_green_sweep.json (every run's metrics, ranks, the choice).
"""
import argparse
import copy
import json
import statistics
from datetime import datetime
from pathlib import Path

from trafficsense import selection
from trafficsense.config import load_config, repo_root
from trafficsense.experiment import git_info, run_experiment

DECISION_INTERVAL = 5
MIN_GREENS = [10, 15, 20, 25]
SCENARIOS = ["jinan_3x4", "hangzhou_4x4", "indian_2x2_offpeak", "indian_2x2_peak"]
SEEDS = [0, 1, 2]
RUNS = Path("outputs/baselines/maxpressure_min_green_sweep")
OUT = Path("outputs/baselines/maxpressure_min_green_sweep.json")


def transition_share(summary):
    """Measured: every switch shows the transition phase for its full duration."""
    sig, n_int = summary["signal"], len(summary["per_intersection"])
    (tr,) = sig["transition_s"]
    return sig["switches"] * tr / (summary["metrics"]["steps"] * n_int)


def load_runs(root: Path) -> dict:
    runs = {}
    for p in sorted(root.glob("mg*/*/summary.json")):
        s = json.loads(p.read_text())
        pv = s["provenance"]
        cp = pv["controller_params"]
        if cp["decision_interval"] != DECISION_INTERVAL:
            raise SystemExit(f"{p}: decision_interval {cp['decision_interval']}, expected {DECISION_INTERVAL}")
        key = (pv["scenario"], cp["min_green"], pv["seed"])
        if key in runs:
            raise SystemExit(f"Two runs for {key}: {runs[key]['dir']} and {p.parent}; remove the stale one")
        if pv["git_dirty"]:
            raise SystemExit(f"{p}: run from a dirty git tree, not citable")
        runs[key] = {"dir": str(p.parent.relative_to(repo_root())), "summary": s}
    return runs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--select-only", action="store_true", help="skip the runs, recompute from the folders")
    ap.add_argument("--allow-dirty", action="store_true", help="for testing only; results are not citable")
    args = ap.parse_args()

    root = repo_root()
    cfg = load_config(args.config)
    if not args.select_only:
        if git_info()["dirty"] and not args.allow_dirty:
            raise SystemExit("Git tree is dirty: commit first so the runs' provenance points at the exact code")
        for k in MIN_GREENS:
            c = copy.deepcopy(cfg)
            c["controllers"]["maxpressure"]["decision_interval"] = DECISION_INTERVAL
            c["controllers"]["maxpressure"]["min_green"] = k
            for sc in SCENARIOS:
                for seed in SEEDS:
                    out = run_experiment(c, sc, "maxpressure", seed=seed, out_root=root / RUNS / f"mg{k}")
                    m = json.loads((out / "summary.json").read_text())["metrics"]
                    print(f"mg={k:2d} {sc:20s} s{seed}: ATT {m['att']:.1f} throughput {m['throughput']}", flush=True)

    runs = load_runs(root / RUNS)
    expected = {(sc, k, s) for sc in SCENARIOS for k in MIN_GREENS for s in SEEDS}
    missing = expected - set(runs)
    if missing:
        raise SystemExit(f"Missing runs: {sorted(missing)}")
    table = {}
    for sc in SCENARIOS:
        for k in MIN_GREENS:
            rs = [runs[(sc, k, s)] for s in SEEDS]
            e = {"seeds": SEEDS, "runs": [r["dir"] for r in rs],
                 "git_commits": sorted({r["summary"]["provenance"]["git_commit"] for r in rs}),
                 "flow_sha256": [r["summary"]["provenance"]["flow_sha256"] for r in rs]}
            for name, f in (("att", lambda s: s["metrics"]["att"]),
                            ("throughput", lambda s: s["metrics"]["throughput"]),
                            ("waiting_to_enter", lambda s: s["metrics"]["vehicles_waiting_to_enter_at_end"]),
                            ("queue_mean_per_intersection", lambda s: s["metrics"]["queue_mean_per_intersection"]),
                            ("transition_share", transition_share),
                            ("forced_switches", lambda s: s["signal"]["forced_switches"])):
                xs = [f(r["summary"]) for r in rs]
                e[name] = {"values": xs, "mean": statistics.mean(xs), "std": statistics.stdev(xs)}
            table.setdefault(sc, {})[str(k)] = e
    sel = selection.select({sc: {k: table[sc][str(k)]["att"]["mean"] for k in MIN_GREENS} for sc in SCENARIOS})
    sel["chosen_min_green"] = sel.pop("chosen")
    out = {
        "provenance": {"script": "scripts/tune_maxpressure_min_green.py", "config": args.config,
                       "decision_interval": DECISION_INTERVAL, "min_greens": MIN_GREENS,
                       "scenarios": SCENARIOS, "seeds": SEEDS,
                       "rule": "lowest mean rank of mean-over-seeds ATT across the 4 scenarios; "
                               "tie-break mean ATT/best, then shorter min_green",
                       "git_commit_of_this_summary": git_info()["commit"],
                       "timestamp": datetime.now().astimezone().isoformat(timespec="seconds")},
        "results": table,
        "selection": sel,
    }
    (root / OUT).parent.mkdir(parents=True, exist_ok=True)
    (root / OUT).write_text(json.dumps(out, indent=1))
    print(f"Wrote {OUT}")
    print(json.dumps({"mean_rank": sel["mean_rank"], "mean_att_over_best": sel["mean_att_over_best"],
                      "chosen": sel["chosen_min_green"]}, indent=1))


if __name__ == "__main__":
    main()
