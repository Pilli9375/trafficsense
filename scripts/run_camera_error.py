"""Camera-error experiment (Phase 4c): every run of the pre-registered plan, resumable.

    python scripts/run_camera_error.py --dry-run   # list the runs: done / to do, and a time estimate
    python scripts/run_camera_error.py             # run every run not done yet (clean git tree)

Restart after an interruption: start Ollama, then run the same command again, detached:
    setsid nohup .venv/bin/python scripts/run_camera_error.py >/dev/null 2>&1 < /dev/null &
Finished runs are skipped (a run folder with summary.json and metrics.csv is complete; see
run_experiment). Progress goes to stdout and to outputs/camera_error/batch.log.

Plan (docs/camera_error.md, committed BEFORE any run):
  Observation levels (sim/observation.py; the simulator itself always stays exact)
    perfect   exact counts (as in every earlier experiment)
    junction  camera errors with the detection rates of medium + large objects
    crowded   camera errors with the overall detection rates
    uniform   p_detect for every class, exact labels, no false detections (MaxPressure sweep)
  Runs (3600 s each)
    1. indian_2x2_offpeak and indian_2x2_peak, seeds 0-2, levels perfect / junction / crowded:
       maxpressure, fixedtime_webster, main LLM arm.
    2. Sweep, same scenarios and seeds: maxpressure at uniform p_detect 1.0, 0.9, ..., 0.5.
    3. indian_2x2_peak_amb, seeds 0-4, levels perfect (reference) and junction: maxpressure,
       fixedtime_webster, preemption_mp, main LLM arm.
  Main LLM arm: llm_guarded_mp with llama3.2:3b, 5 s decisions, min green 15 s, llm.seed = run
  seed (the main arm of scripts/run_full_experiments.py; checked against benchmark.json).
  Order: non-LLM runs first, then LLM runs. Before the first LLM run every Ollama model is
  unloaded and the GPU must be idle.
Outputs: outputs/camera_error/runs/. Tables and chart: scripts/make_camera_error.py.
"""
import argparse
import copy
import importlib.util
import json
import logging
import sys
import time
from pathlib import Path

from trafficsense.config import load_config, repo_root
from trafficsense.experiment import git_info, run_experiment
from trafficsense.llm.client import OllamaClient
from trafficsense.llm.gpu import free_gpu
from trafficsense.sim.observation import observation_key

STEPS = 3600
INDIAN = [(f"indian_2x2_{lv}", s) for lv in ("offpeak", "peak") for s in (0, 1, 2)]
EMERGENCY = [("indian_2x2_peak_amb", s) for s in range(5)]
LEVELS = [{"level": "perfect"}, {"level": "junction"}, {"level": "crowded"}]
SWEEP = [{"level": "uniform", "p_detect": p} for p in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5)]
RUNS = Path("outputs/camera_error/runs")
LOG = Path("outputs/camera_error/batch.log")
ESTIMATE_S = {"maxpressure": 5, "preemption_mp": 5, "fixedtime_webster": 35, "llm_guarded_mp": 770}


def full_plan():
    spec = importlib.util.spec_from_file_location("run_full_experiments",
                                                  repo_root() / "scripts" / "run_full_experiments.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FULL = full_plan()
MAIN = FULL.MAIN


def jobs() -> list[dict]:
    out = []

    def add(scenarios, controllers, levels):
        for sc, seed in scenarios:
            for obs in levels:
                for c in controllers:
                    llm = ({"model": MAIN["model"], "decision_interval": MAIN["decision_interval"]}
                           if c == MAIN["controller"] else None)
                    out.append({"scenario": sc, "seed": seed, "controller": c, "observation": obs, "llm": llm})
    add(INDIAN, ["maxpressure", "fixedtime_webster"], LEVELS)
    add(INDIAN, ["maxpressure"], SWEEP)
    add(EMERGENCY, ["maxpressure", "fixedtime_webster", "preemption_mp"], LEVELS[:2])
    add(INDIAN, [MAIN["controller"]], LEVELS)
    add(EMERGENCY, [MAIN["controller"]], LEVELS[:2])
    return out


def job_key(j: dict) -> tuple:
    return (j["scenario"], j["controller"], int(j["seed"]), j["llm"]["model"] if j["llm"] else None,
            observation_key(j["observation"]))


def complete_runs(root: Path, log=None) -> dict[tuple, Path]:
    done = {}
    for d in sorted((root / RUNS).glob("*/")):
        s = d / "summary.json"
        if not s.is_file() or not (d / "metrics.csv").is_file():
            if log:
                log.warning("Incomplete run folder (left in place, run again): %s", d.relative_to(root))
            continue
        summ = json.loads(s.read_text())
        pv = summ["provenance"]
        if pv["git_dirty"] or pv["sim_steps"] != STEPS:
            continue
        k = (pv["scenario"], pv["controller"], int(pv["seed"]), pv["model"], summ["observation"]["key"])
        if k in done:
            raise SystemExit(f"Two complete runs for {k}: {done[k].name} and {d.name}; remove one")
        done[k] = d
    return done


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
    log = logging.getLogger("batch")
    FULL.check_main_arm(root)

    plan = jobs()
    done = complete_runs(root, None if args.dry_run else log)
    todo = [j for j in plan if job_key(j) not in done]
    left = sum(ESTIMATE_S[j["controller"]] for j in todo)
    log.info("%d runs in the plan, %d done, %d to do; estimated %.1f h left", len(plan), len(plan) - len(todo),
             len(todo), left / 3600)
    if args.dry_run:
        for j in plan:
            print(f"{'done' if job_key(j) in done else 'todo'}  {j['scenario']:<20} s{j['seed']} "
                  f"{observation_key(j['observation']):<14} {j['controller']}"
                  + (f" ({j['llm']['model']})" if j["llm"] else ""))
        return
    if git_info()["dirty"]:
        raise SystemExit("Git tree is dirty: commit first so the runs' provenance points at the exact code")

    cfg = load_config(args.config)
    loaded = None
    for n, j in enumerate(todo, 1):
        c = copy.deepcopy(cfg)
        c["observation"] = j["observation"]
        if j["llm"]:
            c["llm"].update(model=j["llm"]["model"], decision_interval=j["llm"]["decision_interval"],
                            min_green=FULL.LLM_MIN_GREEN, seed=j["seed"])
            if loaded != j["llm"]["model"]:
                free_gpu(OllamaClient.from_config(c["llm"]))
                loaded = j["llm"]["model"]
        tag = f"{j['scenario']} seed {j['seed']} {observation_key(j['observation'])} {j['controller']}"
        log.info("[%d/%d] start %s", n, len(todo), tag)
        t0 = time.perf_counter()
        out = run_experiment(c, j["scenario"], j["controller"], steps=STEPS, seed=j["seed"], out_root=root / RUNS)
        log.info("[%d/%d] done in %.0f s: %s", n, len(todo), time.perf_counter() - t0, out.relative_to(root))
    log.info("All %d runs of the plan are complete", len(plan))


if __name__ == "__main__":
    try:
        main()
    except BaseException:       # also KeyboardInterrupt / SystemExit: the log says why the batch stopped
        logging.getLogger("batch").exception("Batch stopped")
        raise
