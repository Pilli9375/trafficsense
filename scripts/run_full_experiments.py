"""Full experiments (Phase 3c): every run of the pre-registered plan, resumable.

    python scripts/run_full_experiments.py --dry-run   # list the runs: done / to do, and a time estimate
    python scripts/run_full_experiments.py             # run every run not done yet (clean git tree)

Restart after an interruption (laptop restart, crash): start Ollama, then run the same command
again (detached: setsid nohup .venv/bin/python scripts/run_full_experiments.py >/dev/null 2>&1 &). Finished runs are skipped: run_experiment() writes summary.json last (atomic rename), so
a run folder with a readable summary.json is complete; an interrupted run
leaves no summary.json and is simply run again (its partial folder is reported in the log and
left in place). Progress goes to stdout and to outputs/full/batch.log.

Plan, fixed and committed BEFORE any run:
  Arms
    * main:  llm_guarded_mp with llama3.2:3b, decision interval 5 s, min green 15 s. The
             pick of the pre-registered final LLM design round (docs/llm_benchmark.md); the
             script checks that outputs/llm_benchmark/benchmark.json "final" says the same.
    * exploratory, NOT selected by the rule: llm_guided_mp_v3 (hybrid_v3) with gemma4:e4b,
             decision interval 5 s, min green 15 s. The only model whose decisions follow
             pressure after prompt v3; it failed the rule only on latency (p95 4.80 s >= 3 s;
             by the interval rule it would need a 20 s decision interval in real time). It runs
             at 5 s, as benchmarked: the simulation pauses during calls.
    * baselines: maxpressure, fixedtime_webster, fixedtime (4 paired phases, 30 s);
             preemption_mp on the emergency scenario only.
    * LLM runs use the run seed as the LLM sampling seed (llm.seed). At temperature 0 the
      answer should not depend on it; any difference between seeds of a fixed-flow scenario
      (Jinan) then comes from the server, and is reported.
  Runs (3600 s each)
    1. indian_2x2_offpeak and indian_2x2_peak, seeds 0-2: 3 baselines + main + exploratory.
    2. jinan_3x4, seeds 0-2: 3 baselines + main. Not the exploratory arm: gemma4:e4b takes
       ~4.5 s per call, and 12 intersections need ~3x the calls of the 2x2 grid (~3.5 h per run).
       Jinan's flow file is fixed, so the deterministic baselines repeat across seeds.
    3. emergency, the pre-registered design (scripts/run_emergency_experiments.py):
       indian_2x2_peak_amb, seeds 0-4: maxpressure, fixedtime_webster, preemption_mp, main,
       and (added at the user's request after that design was committed) exploratory.
  Order: baselines, then main-arm runs, then exploratory runs (the slowest last).
  Before the first run of each LLM model every Ollama model is unloaded and the GPU must be
  idle (<= 300 MiB, trafficsense.llm.gpu).
Outputs: runs 1-2 in outputs/full/runs/, runs 3 in outputs/emergency/runs/. Tables:
scripts/make_results.py (docs/results.md) and scripts/run_emergency_experiments.py.
"""
import argparse
import copy
import json
import logging
import sys
import time
from pathlib import Path

from trafficsense.config import load_config, repo_root
from trafficsense.experiment import git_info, run_experiment
from trafficsense.llm.client import OllamaClient
from trafficsense.llm.gpu import free_gpu

STEPS = 3600
LLM_MIN_GREEN = 15
MAIN = {"arm": "main", "controller": "llm_guarded_mp", "model": "llama3.2:3b", "decision_interval": 5}
EXPLORATORY = {"arm": "exploratory", "controller": "llm_guided_mp_v3", "model": "gemma4:e4b", "decision_interval": 5}
BASELINES = ["maxpressure", "fixedtime_webster", "fixedtime"]
FULL_RUNS = Path("outputs/full/runs")
EMERGENCY_RUNS = Path("outputs/emergency/runs")
LOG = Path("outputs/full/batch.log")
BENCHMARK = Path("outputs/llm_benchmark/benchmark.json")
# Rough wall time per run (s) for --dry-run, scaled from the 600 s benchmark runs (Indian peak:
# guarded llama 122 s, gemma4 hybrid_v3 673 s) and x3 for Jinan's 12 intersections.
ESTIMATE_S = {"baseline": 30, "main": 730, "exploratory": 4040}
JINAN_FACTOR = 3


def jobs() -> list[dict]:
    out = []
    indian = [(f"indian_2x2_{lv}", s) for lv in ("offpeak", "peak") for s in (0, 1, 2)]
    jinan = [("jinan_3x4", s) for s in (0, 1, 2)]
    emergency = [("indian_2x2_peak_amb", s) for s in range(5)]

    def add(arm, scenarios, out_root, controllers=None):
        for sc, seed in scenarios:
            for c in controllers or [arm["controller"]]:
                out.append({"arm": arm["arm"] if isinstance(arm, dict) else arm, "scenario": sc, "seed": seed,
                            "controller": c, "out_root": out_root,
                            "llm": None if not isinstance(arm, dict) else
                            {"model": arm["model"], "decision_interval": arm["decision_interval"]}})
    add("baseline", indian + jinan, FULL_RUNS, BASELINES)
    add("baseline", emergency, EMERGENCY_RUNS, ["maxpressure", "fixedtime_webster", "preemption_mp"])
    add(MAIN, indian, FULL_RUNS)
    add(MAIN, emergency, EMERGENCY_RUNS)
    add(MAIN, jinan, FULL_RUNS)
    add(EXPLORATORY, indian, FULL_RUNS)
    add(EXPLORATORY, emergency, EMERGENCY_RUNS)
    return out


def key(scenario, controller, seed, model) -> tuple:
    return (scenario, controller, int(seed), model)


def job_key(j: dict) -> tuple:
    return key(j["scenario"], j["controller"], j["seed"], j["llm"]["model"] if j["llm"] else None)


def complete_runs(root: Path, out_root: Path, log=None) -> dict[tuple, Path]:
    """Complete run folders: summary.json readable, clean tree, STEPS long.

    summary.json is written last, so it alone marks a finished run. metrics.csv is not required:
    it is gitignored, and a fresh clone has only the summaries."""
    done = {}
    for d in sorted((root / out_root).glob("*/")):
        s = d / "summary.json"
        if not s.is_file():
            if log:
                log.warning("Incomplete run folder (left in place, run again): %s", d.relative_to(root))
            continue
        pv = json.loads(s.read_text())["provenance"]
        if pv["git_dirty"] or pv["sim_steps"] != STEPS:
            continue
        k = key(pv["scenario"], pv["controller"], pv["seed"], pv["model"])
        if k in done:
            raise SystemExit(f"Two complete runs for {k}: {done[k].name} and {d.name}; remove one")
        done[k] = d
    return done


def estimate_s(j: dict) -> float:
    return ESTIMATE_S[j["arm"]] * (JINAN_FACTOR if j["scenario"].startswith("jinan") else 1)


def check_main_arm(root: Path) -> None:
    f = json.loads((root / BENCHMARK).read_text())["final"]
    got = {"controller": f["controller"], "model": f["model"], "decision_interval": f["decision_interval_s"]}
    want = {k: MAIN[k] for k in got}
    if got != want:
        raise SystemExit(f"benchmark.json final decision {got} differs from the pre-registered main arm {want}")


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
    check_main_arm(root)

    done = {}
    for out_root in (FULL_RUNS, EMERGENCY_RUNS):
        done |= complete_runs(root, out_root, None if args.dry_run else log)
    todo = [j for j in jobs() if job_key(j) not in done]
    left = sum(estimate_s(j) for j in todo)
    log.info("%d runs in the plan, %d done, %d to do; estimated %.1f h left", len(jobs()), len(jobs()) - len(todo),
             len(todo), left / 3600)
    if args.dry_run:
        for j in jobs():
            print(f"{'done' if job_key(j) in done else 'todo'}  {j['arm']:<11} {j['scenario']:<20} s{j['seed']} "
                  f"{j['controller']}" + (f" ({j['llm']['model']})" if j["llm"] else ""))
        return
    if git_info()["dirty"]:
        raise SystemExit("Git tree is dirty: commit first so the runs' provenance points at the exact code")

    cfg = load_config(args.config)
    loaded = None
    for n, j in enumerate(todo, 1):
        c = cfg
        if j["llm"]:
            c = copy.deepcopy(cfg)
            c["llm"].update(model=j["llm"]["model"], decision_interval=j["llm"]["decision_interval"],
                            min_green=LLM_MIN_GREEN, seed=j["seed"])
            if loaded != j["llm"]["model"]:
                free_gpu(OllamaClient.from_config(c["llm"]))
                loaded = j["llm"]["model"]
        log.info("[%d/%d] start %s %s seed %d %s%s", n, len(todo), j["arm"], j["scenario"], j["seed"], j["controller"],
                 f" ({j['llm']['model']})" if j["llm"] else "")
        t0 = time.perf_counter()
        out = run_experiment(c, j["scenario"], j["controller"], steps=STEPS, seed=j["seed"],
                             out_root=root / j["out_root"])
        log.info("[%d/%d] done in %.0f s: %s", n, len(todo), time.perf_counter() - t0, out.relative_to(root))
    log.info("All %d runs of the plan are complete", len(jobs()))


if __name__ == "__main__":
    try:
        main()
    except BaseException:       # also KeyboardInterrupt / SystemExit: the log says why the batch stopped
        logging.getLogger("batch").exception("Batch stopped")
        raise
