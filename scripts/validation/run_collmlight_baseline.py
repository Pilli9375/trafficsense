"""Run CoLLMLight's own FixedTime / MaxPressure code, unmodified, and record its results.

Run with the separate venv (numpy/pandas/tqdm pinned to CoLLMLight's requirements):
    data/external/collmlight_venv/bin/python scripts/validation/run_collmlight_baseline.py \
        --model Fixedtime --dataset synthetic_4x4 --seed 0

What this harness does NOT change: their env, agents, run loop, metric code and settings.
What it does:
  * stubs imports that FixedTime/MaxPressure never use (tensorflow, torch, transformers, trl,
    peft, vllm, requests via the LLM agents; wandb logging). utils/config.py imports every agent
    class, so these would otherwise be needed just to import it. No stub produces any data.
  * seeds numpy before the run. Their env draws the CityFlow seed from np.random.randint(0, 100)
    on every reset; seeding numpy makes the run reproducible. The engine seeds actually used are
    captured by wrapping cityflow.Engine (read-only: it reads the config file and passes it on).
  * calls their run_fixedtime.main / run_maxpressure.main where the dataset is supported. Their
    run_maxpressure.py has no synthetic_4x4 branch, so for that case the harness builds the same
    config dicts run_maxpressure.py builds, with run_fixedtime.py's synthetic_4x4 paths.
  * after the run, also reads engine.get_average_travel_time() from their engine, so one metric
    is computed by literally the same function in both codebases.
Output: outputs/validation/collmlight/<dataset>_<model>_s<seed>.json
"""
import argparse
import importlib.abc
import importlib.machinery
import io
import json
import os
import subprocess
import sys
import types
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT / "data" / "external" / "collmlight_repo"
OUT = ROOT / "outputs" / "validation" / "collmlight"

STUBBED = ("tensorflow", "keras", "torch", "transformers", "trl", "peft", "vllm", "lmdeploy",
           "wandb", "requests", "datasets", "fire")

DATASETS = {
    "synthetic_4x4": ("anon_4_4_synthetic_8000.json", "4_4", "Synthetic"),
    "jinan": ("anon_3_4_jinan_real_2000.json", "3_4", "Jinan"),
    "hangzhou": ("anon_4_4_hangzhou_real.json", "4_4", "Hangzhou"),
}


class _Anything:
    """Stand-in for unused library objects: any attribute/call/subclass works and returns itself."""
    def __init__(self, *a, **k): pass
    def __call__(self, *a, **k): return _Anything()
    def __getattr__(self, name): return _Anything()
    def __mro_entries__(self, bases): return (object,)


class _StubFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, name, path, target=None):
        if name.split(".")[0] in STUBBED:
            return importlib.machinery.ModuleSpec(name, self, is_package=True)
        return None

    def create_module(self, spec):
        mod = types.ModuleType(spec.name)
        mod.__path__ = []
        mod.__getattr__ = lambda attr: _Anything()
        return mod

    def exec_module(self, module):
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, choices=["Fixedtime", "MaxPressure"])
    ap.add_argument("--dataset", required=True, choices=sorted(DATASETS))
    ap.add_argument("--seed", type=int, default=0, help="numpy seed (their engine seed is drawn from it)")
    args = ap.parse_args()

    if not (REPO / "run_fixedtime.py").is_file():
        raise FileNotFoundError(f"CoLLMLight repo not found at {REPO}")
    sys.meta_path.insert(0, _StubFinder())
    sys.path.insert(0, str(REPO))   # their code uses top-level `utils` / `models` packages
    os.chdir(REPO)                  # and paths relative to its repo root
    (REPO / "results" / "latest_results").mkdir(parents=True, exist_ok=True)

    import numpy as np
    import cityflow
    import utils.cityflow_env as cenv
    import utils.oneline as oneline

    engine_seeds, engines = [], []

    def engine_factory(config_path, thread_num=1):
        cfg = json.loads(Path(config_path).read_text())
        engine_seeds.append({"seed": cfg["seed"], "laneChange": cfg["laneChange"],
                             "interval": cfg["interval"]})
        eng = cityflow.Engine(config_path, thread_num=thread_num)
        engines.append(eng)
        return eng

    cenv.engine = types.SimpleNamespace(Engine=engine_factory)

    results = []
    orig_train = oneline.OneLine.train

    def train(self, round):
        r = orig_train(self, round)
        r = {k: float(v) for k, v in r.items()}
        r["cityflow_att"] = float(self.env.eng.get_average_travel_time())
        r["vehicles_running_at_end"] = len(self.env.eng.get_vehicles(include_waiting=False))
        r["sim_time_end"] = float(self.env.get_current_time())
        results.append(r)
        return r

    oneline.OneLine.train = train

    traffic_file, road_net, template = DATASETS[args.dataset]
    ns = argparse.Namespace(memo=args.model, model=args.model, eightphase=False,
                            proj_name="validation", multi_process=False, workers=1,
                            dataset=args.dataset, traffic_file=traffic_file)
    np.random.seed(args.seed)
    log = io.StringIO()
    with redirect_stdout(log):
        if args.model == "Fixedtime":
            import run_fixedtime
            run_fixedtime.main(ns)
            entry = "run_fixedtime.main"
        elif args.dataset != "synthetic_4x4":
            import run_maxpressure
            run_maxpressure.main(ns)
            entry = "run_maxpressure.main"
        else:
            _maxpressure_synthetic(traffic_file, road_net, template)
            entry = "harness copy of run_maxpressure.py config with synthetic_4x4 paths"
    if len(results) != 1:
        raise RuntimeError(f"Expected one result from their run, got {len(results)}. Log tail:\n"
                           + log.getvalue()[-2000:])

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    out = {
        "source": "CoLLMLight code (unmodified), run via scripts/validation/run_collmlight_baseline.py",
        "collmlight_commit": commit,
        "entry_point": entry,
        "model": args.model,
        "dataset": args.dataset,
        "traffic_file": traffic_file,
        "numpy_seed": args.seed,
        "engine_configs": engine_seeds,   # one per env.reset(); the last one is the evaluated run
        "results": results[0],
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{args.dataset}_{args.model}_s{args.seed}.json"
    path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {path}")
    print(json.dumps(results[0], indent=2))


def _maxpressure_synthetic(traffic_file, road_net, template):
    """Same dicts as run_maxpressure.py builds (4-phase branch), with synthetic_4x4 paths."""
    import time
    from utils.utils import oneline_wrapper
    n_row, n_col = (int(x) for x in road_net.split("_"))
    env_extra = {
        "NUM_AGENTS": n_row * n_col,
        "NUM_INTERSECTIONS": n_row * n_col,
        "MODEL_NAME": "MaxPressure",
        "PROJECT_NAME": "validation",
        "RUN_COUNTS": 3600,
        "NUM_ROW": n_row,
        "NUM_COL": n_col,
        "TRAFFIC_FILE": traffic_file,
        "ROADNET_FILE": f"roadnet_{road_net}.json",
        "LIST_STATE_FEATURE": ["cur_phase", "traffic_movement_pressure_queue"],
        "DIC_REWARD_INFO": {"pressure": 0},
    }
    agent_extra = {"FIXED_TIME": [30, 30, 30, 30]}
    stamp = time.strftime('%m_%d_%H_%M_%S', time.localtime(time.time()))
    path_extra = {
        "PATH_TO_MODEL": os.path.join("model", "MaxPressure", traffic_file + "_" + stamp),
        "PATH_TO_WORK_DIRECTORY": os.path.join("records", "MaxPressure", traffic_file + "_" + stamp),
        "PATH_TO_DATA": os.path.join("data", template, road_net),
    }
    oneline_wrapper(agent_extra, env_extra, path_extra, f"{template}-{road_net}",
                    traffic_file.split(".")[0])


if __name__ == "__main__":
    main()
