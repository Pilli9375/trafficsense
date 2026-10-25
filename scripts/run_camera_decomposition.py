"""Camera-error experiment, POST-HOC decomposition (added after the results; not pre-registered).

    python scripts/run_camera_decomposition.py --dry-run   # list the runs: done / to do
    python scripts/run_camera_decomposition.py             # run every run not done yet (clean git tree)

The junction-camera level split into its error components, one at a time (sim/observation.py
COMPONENTS; the others exact): misses only, false detections only, class confusion only.
MaxPressure, indian_2x2_offpeak and indian_2x2_peak, seeds 0-2: 18 runs of 3600 s. The "all
components" case and the perfect reference are the junction and perfect runs of the main batch
(scripts/run_camera_error.py), made by the same code path. Outputs:
outputs/camera_error/decomposition/runs/, log decomposition.log next to it. Resumable like the
main batch (a run folder with a summary.json is complete); each run in a child
process with a timeout. Table: scripts/make_camera_error.py (camera_decomposition).
"""
import argparse
import copy
import importlib.util
import logging
import sys
import time
from pathlib import Path

from trafficsense.config import load_config, repo_root
from trafficsense.experiment import git_info, run_experiment_isolated
from trafficsense.sim.observation import COMPONENTS, observation_key

RUNS = Path("outputs/camera_error/decomposition/runs")
LOG = Path("outputs/camera_error/decomposition/decomposition.log")
CONTROLLER = "maxpressure"


def load_plan():
    spec = importlib.util.spec_from_file_location("run_camera_error", repo_root() / "scripts" / "run_camera_error.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan = load_plan()


def jobs() -> list[dict]:
    return [{"scenario": sc, "seed": seed, "controller": CONTROLLER, "observation": {"level": "junction", "only": o},
             "llm": None} for sc, seed in plan.INDIAN for o in COMPONENTS]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    root = repo_root()
    (root / LOG).parent.mkdir(parents=True, exist_ok=True)
    handlers = [logging.StreamHandler(sys.stdout)] + ([] if args.dry_run else [logging.FileHandler(root / LOG)])
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
                        handlers=handlers, force=True)
    log = logging.getLogger("decomposition")
    done = plan.complete_runs(root, None if args.dry_run else log, RUNS)
    todo = [j for j in jobs() if plan.job_key(j) not in done]
    log.info("%d runs in the decomposition, %d done, %d to do", len(jobs()), len(jobs()) - len(todo), len(todo))
    if args.dry_run:
        for j in jobs():
            print(f"{'done' if plan.job_key(j) in done else 'todo'}  {j['scenario']:<20} s{j['seed']} "
                  f"{observation_key(j['observation'])}")
        return
    if git_info()["dirty"]:
        raise SystemExit("Git tree is dirty: commit first so the runs' provenance points at the exact code")
    cfg = load_config(args.config)
    for n, j in enumerate(todo, 1):
        c = copy.deepcopy(cfg)
        c["observation"] = j["observation"]
        tag = f"{j['scenario']} seed {j['seed']} {observation_key(j['observation'])}"
        log.info("[%d/%d] start %s", n, len(todo), tag)
        t0 = time.perf_counter()
        out = run_experiment_isolated(c, j["scenario"], CONTROLLER, plan.STEPS, j["seed"], root / RUNS,
                                      plan.TIMEOUT_S[CONTROLLER], plan.MAX_RETRIES, log)
        log.info("[%d/%d] done in %.0f s: %s", n, len(todo), time.perf_counter() - t0, out.relative_to(root))
    log.info("All %d decomposition runs are complete", len(jobs()))


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        logging.getLogger("decomposition").exception("Decomposition stopped")
        raise
