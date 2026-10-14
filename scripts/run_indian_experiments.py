"""Run the Indian 2x2 baseline experiments: controllers x demand levels x seeds.

    python scripts/run_indian_experiments.py            # 3 controllers x {offpeak, peak} x seeds 0 1 2

Each run is a normal run_experiment() folder (summary.json + metrics.csv) under
outputs/indian_2x2/runs/. Refuses to start from a dirty git tree, so every summary.json records
a commit that contains the exact code and flow files used.
"""
import argparse

from trafficsense.config import load_config, repo_root
from trafficsense.experiment import git_info, run_experiment

CONTROLLERS = ["fixedtime", "fixedtime_all_phases", "maxpressure"]
LEVELS = ["offpeak", "peak"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--controllers", nargs="+", default=CONTROLLERS)
    ap.add_argument("--levels", nargs="+", default=LEVELS)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--out-root", default="outputs/indian_2x2/runs")
    ap.add_argument("--allow-dirty", action="store_true", help="for testing only; results are not citable")
    args = ap.parse_args()

    if git_info()["dirty"] and not args.allow_dirty:
        raise SystemExit("Git tree is dirty: commit first so the runs' provenance points at the exact code")
    cfg = load_config(args.config)
    out_root = repo_root() / args.out_root
    for level in args.levels:
        scenario = f"indian_2x2_{level}"
        for controller in args.controllers:
            for seed in args.seeds:
                out = run_experiment(cfg, scenario, controller, seed=seed, out_root=out_root)
                print(f"Wrote {out.relative_to(repo_root())}", flush=True)


if __name__ == "__main__":
    main()
