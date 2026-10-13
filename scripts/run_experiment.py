"""Run one controller on one scenario. Writes outputs/runs/<timestamp>_<scenario>_<controller>_s<seed>/."""
import argparse
import json

from trafficsense.config import load_config
from trafficsense.control import CONTROLLERS
from trafficsense.experiment import run_experiment


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--controller", required=True, choices=sorted(CONTROLLERS))
    ap.add_argument("--steps", type=int, default=None, help="default: sim.steps from config")
    ap.add_argument("--seed", type=int, default=None, help="default: sim.seed from config")
    args = ap.parse_args()

    cfg = load_config(args.config)
    out = run_experiment(cfg, args.scenario, args.controller, args.steps, args.seed)
    summary = json.loads((out / "summary.json").read_text())
    print(f"Wrote {out}")
    print(json.dumps({"metrics": summary["metrics"], "signal": summary["signal"]}, indent=2))


if __name__ == "__main__":
    main()
