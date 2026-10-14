"""Tune MaxPressure's decision interval: sweep it, then pick one setting by a fixed rule.

    python scripts/tune_maxpressure.py                  # run the sweep (needs a clean git tree)
    python scripts/tune_maxpressure.py --select-only    # recompute the selection from the runs

Sweep: decision_interval in {5, 10, 15, 20, 30} s, every other MaxPressure setting as in
configs/default.yaml (min_green 10, max_green 60, all 8 phases, keep_current tie-break), on
  jinan_3x4, hangzhou_4x4, indian_2x2_offpeak, indian_2x2_peak, seeds 0, 1, 2, 3600 steps.
Each run is a normal run_experiment() folder under outputs/baselines/maxpressure_sweep/di<k>/.

Selection rule, fixed and committed BEFORE the sweep was run:
  1. Each of the 4 scenarios counts once. Its score for an interval is the mean ATT over the
     3 seeds.
  2. Within each scenario the intervals are ranked by that score, 1 = lowest ATT
     (equal scores share the average rank).
  3. The chosen interval has the lowest mean rank over the 4 scenarios.
  4. Tie-break: the lowest mean over scenarios of (score / best score in that scenario);
     if still tied, the shorter interval.
Throughput and transition-time share are reported but not used for selection.

Output: outputs/baselines/maxpressure_sweep.json (every run's metrics, ranks, the choice).
The chosen interval is then written into configs/default.yaml (controllers.maxpressure) by hand.
"""
import argparse
import copy
import json
import statistics
from datetime import datetime
from pathlib import Path

from trafficsense.config import load_config, repo_root
from trafficsense.experiment import git_info, run_experiment

INTERVALS = [5, 10, 15, 20, 30]
SCENARIOS = ["jinan_3x4", "hangzhou_4x4", "indian_2x2_offpeak", "indian_2x2_peak"]
SEEDS = [0, 1, 2]
RUNS = Path("outputs/baselines/maxpressure_sweep")
OUT = Path("outputs/baselines/maxpressure_sweep.json")


def transition_share(summary):
    """Measured: every switch shows the transition phase for its full duration."""
    sig, n_int = summary["signal"], len(summary["per_intersection"])
    (tr,) = sig["transition_s"]
    return sig["switches"] * tr / (summary["metrics"]["steps"] * n_int)


def ranks(scores: dict[int, float]) -> dict[int, float]:
    """1 = lowest score; equal scores share the average rank."""
    order = sorted(scores, key=scores.get)
    out = {}
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        for k in order[i:j + 1]:
            out[k] = (i + j) / 2 + 1
        i = j + 1
    return out


def select(att: dict[str, dict[int, float]]) -> dict:
    """att[scenario][interval] = mean ATT over seeds. Applies the rule in the docstring."""
    intervals = sorted(next(iter(att.values())))
    r = {sc: ranks(v) for sc, v in att.items()}
    rel = {sc: {k: v[k] / min(v.values()) for k in v} for sc, v in att.items()}
    mean_rank = {k: statistics.mean(r[sc][k] for sc in att) for k in intervals}
    mean_rel = {k: statistics.mean(rel[sc][k] for sc in att) for k in intervals}
    chosen = min(intervals, key=lambda k: (mean_rank[k], mean_rel[k], k))
    return {"rank": r, "att_over_best": rel, "mean_rank": mean_rank, "mean_att_over_best": mean_rel,
            "chosen_decision_interval": chosen}


def load_runs(root: Path) -> dict:
    runs = {}
    for p in sorted(root.glob("di*/*/summary.json")):
        s = json.loads(p.read_text())
        pv = s["provenance"]
        k = pv["controller_params"]["decision_interval"]
        key = (pv["scenario"], k, pv["seed"])
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
        for k in INTERVALS:
            c = copy.deepcopy(cfg)
            c["controllers"]["maxpressure"]["decision_interval"] = k
            for sc in SCENARIOS:
                for seed in SEEDS:
                    out = run_experiment(c, sc, "maxpressure", seed=seed, out_root=root / RUNS / f"di{k}")
                    m = json.loads((out / "summary.json").read_text())["metrics"]
                    print(f"di={k:2d} {sc:20s} s{seed}: ATT {m['att']:.1f} throughput {m['throughput']}", flush=True)

    runs = load_runs(root / RUNS)
    expected = {(sc, k, s) for sc in SCENARIOS for k in INTERVALS for s in SEEDS}
    missing = expected - set(runs)
    if missing:
        raise SystemExit(f"Missing runs: {sorted(missing)}")
    table = {}
    for sc in SCENARIOS:
        for k in INTERVALS:
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
    sel = select({sc: {k: table[sc][str(k)]["att"]["mean"] for k in INTERVALS} for sc in SCENARIOS})
    out = {
        "provenance": {"script": "scripts/tune_maxpressure.py", "config": args.config,
                       "intervals": INTERVALS, "scenarios": SCENARIOS, "seeds": SEEDS,
                       "rule": "lowest mean rank of mean-over-seeds ATT across the 4 scenarios; "
                               "tie-break mean ATT/best, then shorter interval",
                       "git_commit_of_this_summary": git_info()["commit"],
                       "timestamp": datetime.now().astimezone().isoformat(timespec="seconds")},
        "results": table,
        "selection": sel,
    }
    (root / OUT).parent.mkdir(parents=True, exist_ok=True)
    (root / OUT).write_text(json.dumps(out, indent=1))
    print(f"Wrote {OUT}")
    print(json.dumps({"mean_rank": sel["mean_rank"], "chosen": sel["chosen_decision_interval"]}, indent=1))


if __name__ == "__main__":
    main()
