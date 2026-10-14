"""Run the baseline controllers on the CoLLMLight real-world datasets.

    python scripts/run_baselines.py      # 5 controllers x {jinan_3x4, hangzhou_4x4} x seeds 0 1 2

Each run is a normal run_experiment() folder (summary.json + metrics.csv) under
outputs/baselines/runs/. The Indian 2x2 baselines are run by scripts/run_indian_experiments.py.
Refuses to start from a dirty git tree, so every summary.json records the exact code used.
"""
import argparse

from trafficsense.config import load_config, repo_root
from trafficsense.experiment import git_info, run_experiment

CONTROLLERS = ["fixedtime", "fixedtime_webster", "maxpressure", "maxpressure_15s", "maxpressure_5s"]
SCENARIOS = ["jinan_3x4", "hangzhou_4x4"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--controllers", nargs="+", default=CONTROLLERS)
    ap.add_argument("--scenarios", nargs="+", default=SCENARIOS)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--out-root", default="outputs/baselines/runs")
    ap.add_argument("--allow-dirty", action="store_true", help="for testing only; results are not citable")
    args = ap.parse_args()

    if git_info()["dirty"] and not args.allow_dirty:
        raise SystemExit("Git tree is dirty: commit first so the runs' provenance points at the exact code")
    cfg = load_config(args.config)
    out_root = repo_root() / args.out_root
    for scenario in args.scenarios:
        for controller in args.controllers:
            for seed in args.seeds:
                out = run_experiment(cfg, scenario, controller, seed=seed, out_root=out_root)
                print(f"Wrote {out.relative_to(repo_root())}", flush=True)


if __name__ == "__main__":
    main()
