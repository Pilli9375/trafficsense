"""Model size vs control quality: an EXPLORATORY study, added after the main results.

    python scripts/run_model_size.py --dry-run     # list every run: done / to do, with a time estimate
    python scripts/run_model_size.py --bench       # step 1: the 600-step benchmarks (clean git tree)
    python scripts/run_model_size.py --full        # step 2: the full runs, resumable (clean git tree)
    python scripts/make_model_size.py              # tables + chart in docs/model_size.md
    python scripts/make_model_size.py --check      # exit 1 if docs/model_size.md is out of date

It does NOT change the pre-registered final round (docs/llm_benchmark.md) or the full-experiment
results and conclusions (docs/results.md); none of its runs is read by those scripts (its runs
live in outputs/model_size/runs/). Everything here is labelled "exploratory, added after the
main results".

Plan, fixed and committed BEFORE any run of this study:
  Question: with the controller held fixed, does a larger model control better?
  Controller (identical to the gemma4 exploratory arm of the full experiments, so only the
  model changes): llm_guided_mp_v3 ("hybrid_v3": MaxPressure offers its top 2 phases plus
  keeping the current one, the LLM picks; prompt guided_v3; cooperative; unguarded; on a
  failed call MaxPressure's choice is applied and the failure counted), decision interval 5 s,
  min green 15 s, temperature 0, LLM seed = run seed. Every other setting from
  configs/default.yaml.
  Models (size axis ordered by total parameters):
    qwen2.5:3b, llama3.2:3b   local (Ollama). Benchmark runs exist (final round, ce92a14);
                              full runs added here at the user's request so every model has
                              the same full runs.
    gemma4:e4b                local. Benchmark and full runs exist (final round; full
                              experiments, exploratory arm); reused, not rerun.
    arm A: llama3.1:8b        local. Picked by a rule stated before pulling it: an 8B-tagged
                              general instruct model in the Ollama library from the same
                              family as a 3B model already in the study (llama3.2:3b is
                              pruned and distilled from Llama 3.1 8B), so mainly size
                              changes. Only llama3.1:8b qualifies; it is also the smallest 8B
                              file of the candidates (4692 MiB vs granite3.3:8b 4713,
                              qwen3:8b 4983, ministral-3:8b 5743 MiB). It has no thinking
                              mode (capabilities: completion, tools); think=false is sent
                              anyway and returned reasoning text is counted per call.
                              Ollama's automatic GPU/CPU split (no num_gpu tuning, as for
                              every model): 45% on the GPU at num_ctx 2048.
    arm B: nvidia/nemotron-3-ultra-550b-a55b   HOSTED (NVIDIA NIM, OpenAI-compatible API):
                              NOT local, prompts leave the machine. The user first named
                              deepseek-ai/deepseek-v4.1-flash; it answered 0 of 7 calls
                              (timeouts of 120-300 s, 2026-10-22 11:35-12:23 IST), and the
                              user's second choice nemotron-3-super-120b-a12b answers "404
                              not found for account". The user chose Nemotron 3 Ultra from
                              the models that answer (scripts/probe_hosted.py records).
                              Reasoning off: chat_template_kwargs enable_thinking=false
                              (probe: 0 reasoning characters; reasoning is on by default).
                              Structured output: response_format json_schema (accepted by the
                              endpoint; nvext.guided_json is rejected), and every answer is
                              still validated by prompt.parse_response. Temperature 0 (NVIDIA
                              recommends 1.0; kept at 0 like every other model here). Client
                              rate limiter 30 requests/min (probe: ~20-request burst, then
                              429s; ~30/min sustained got 1 429 in 46), retries with
                              exponential backoff on 429/5xx, counted apart from failures.
                              The model id the API returns is recorded per call and per run,
                              with the run's date: a hosted model can change silently.
  Step 1, benchmark: indian_2x2_peak, seed 0, 600 steps, for arms A and B (the other models'
    benchmark runs exist with the identical setup). Reported per model: calls, failures by
    type, retries (hosted), latency mean / p95 (answered request) and whole-call p95 (incl.
    rate-limit waits and retries), ATT and queue at 600 s and ATT vs MaxPressure's 600 s run,
    "follows pressure" = share of successful calls whose answer is the highest-pressure
    allowed phase (scripts/analyze_llm_decisions.py replay, the run's ATT reproduced exactly),
    and the share whose answer differs from MaxPressure's top choice. Then STOP for the
    user's go; no change to the plan from these numbers.
  Step 2, full runs (3600 s), after the go: indian_2x2_peak seeds 0-2 and indian_2x2_peak_amb
    (emergency) seeds 0-4, for llama3.2:3b, qwen2.5:3b, llama3.1:8b and nemotron-3-ultra
    (32 runs). Local models one at a time, each after every Ollama model is unloaded and the
    GPU is idle (<= 300 MiB); nothing else uses the GPU meanwhile. The hosted model last,
    never in parallel with a local run. Resumable like the full experiments.
  Step 3, report (docs/model_size.md, generated with --check): per model, smallest first:
    total / active parameters (with source), local or hosted; full runs: ATT vs MaxPressure
    at peak (mean over seeds of the per-seed difference, %, and seeds better / worse), ATT vs
    MaxPressure on the emergency scenario, mean travel time of the signal-relevant ambulances
    pooled over seeds 0-4 (as docs/emergency.md; MaxPressure and rule-based preemption as
    references), "follows pressure" pooled over the 8 runs (replay), answer differs from
    MaxPressure, failures, retries, latency, wall time. Baselines are the existing full runs
    (maxpressure, preemption_mp) on the same flow files (checked by sha256). A chart (SVG)
    of the three quality measures against model size, generated from the same data.
  No selection rule, no significance test, no tuning: with 3 and 5 seeds per scenario the
  numbers are reported as measured, with their spread.

Outputs: outputs/model_size/runs/<run>/ (summary.json, metrics.csv, decisions.jsonl; gpu.json
for local benchmark runs, hosted.json for hosted runs), outputs/model_size/batch.log,
outputs/model_size/probes/ (hosted endpoint probes), outputs/model_size/model_size.json,
docs/model_size.md, docs/figures/model_size.svg.
"""
import argparse
import copy
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from trafficsense.config import load_config, repo_root
from trafficsense.experiment import git_info, run_experiment
from trafficsense.llm.client import OllamaClient
from trafficsense.llm.gpu import VramSampler, free_gpu, gpu_name
from trafficsense.llm.hosted import make_client

CONTROLLER = "llm_guided_mp_v3"
DECISION_INTERVAL, MIN_GREEN = 5, 15
BENCH = ("indian_2x2_peak", 0, 600)
FULL_STEPS = 3600
FULL = [("indian_2x2_peak", s) for s in (0, 1, 2)] + [("indian_2x2_peak_amb", s) for s in range(5)]
HOSTED = "nvidia/nemotron-3-ultra-550b-a55b"
# Smallest first. bench / full: "new" = run by this script, "existing" = earlier runs reused.
MODELS = {
    "qwen2.5:3b": {"provider": "ollama", "bench": "existing", "full": "new"},
    "llama3.2:3b": {"provider": "ollama", "bench": "existing", "full": "new"},
    "gemma4:e4b": {"provider": "ollama", "bench": "existing", "full": "existing"},
    "llama3.1:8b": {"provider": "ollama", "bench": "new", "full": "new"},
    HOSTED: {"provider": "nvidia_nim", "bench": "new", "full": "new"},
}
RUNS = Path("outputs/model_size/runs")
LOG = Path("outputs/model_size/batch.log")
BENCH_RUNS = Path("outputs/llm_benchmark/runs")
# Rough wall time per 600 simulated seconds (s) before a model's own benchmark exists: the
# earlier benchmark's hybrid_v3 runs (llama3.2 308 s, qwen2.5 310 s), ~2 s per call for the
# rest. Once a benchmark run exists, its wall time is used instead.
DEFAULT_WALL_PER_600_S = 600


def jobs() -> list[dict]:
    """Every run this script makes: step 1 then step 2, local models before the hosted one."""
    order = sorted(MODELS, key=lambda m: MODELS[m]["provider"] != "ollama")      # stable: local first
    out = [{"step": "bench", "model": m, "scenario": BENCH[0], "seed": BENCH[1], "steps": BENCH[2]}
           for m in order if MODELS[m]["bench"] == "new"]
    out += [{"step": "full", "model": m, "scenario": sc, "seed": s, "steps": FULL_STEPS}
            for m in order if MODELS[m]["full"] == "new" for sc, s in FULL]
    return out


def key(scenario: str, seed: int, steps: int, model: str) -> tuple:
    return (scenario, int(seed), int(steps), model)


def job_key(j: dict) -> tuple:
    return key(j["scenario"], j["seed"], j["steps"], j["model"])


def complete_runs(root: Path, log=None) -> dict[tuple, Path]:
    """Complete, citable runs of this study: summary.json (written last; metrics.csv is gitignored,
    so it is not required), clean tree, our controller."""
    done = {}
    for d in sorted((root / RUNS).glob("*/")):
        s = d / "summary.json"
        if not s.is_file():
            if log:
                log.warning("Incomplete run folder (left in place, run again): %s", d.relative_to(root))
            continue
        pv = json.loads(s.read_text())["provenance"]
        if pv["git_dirty"] or pv["controller"] != CONTROLLER:
            continue
        k = key(pv["scenario"], pv["seed"], pv["sim_steps"], llm_model(pv))
        if k in done:
            raise SystemExit(f"Two complete runs for {k}: {done[k].name} and {d.name}; remove one")
        done[k] = d
    return done


def llm_model(pv: dict) -> str:
    """The model a run was configured with. summary 'model' is what the server reported, which
    for a hosted model could differ; runs before the client recorded it are Ollama runs."""
    return pv["controller_params"]["client"].get("model") or pv["model"]


def run_cfg(cfg: dict, model: str, seed: int) -> dict:
    c = copy.deepcopy(cfg)
    if MODELS[model]["provider"] == "nvidia_nim":
        hosted = cfg["llm_hosted"]["nvidia_nim"]
        if hosted["model"] != model:
            raise SystemExit(f"configs: llm_hosted.nvidia_nim.model is {hosted['model']!r}, the plan says {model!r}")
        c["llm"] = {**cfg["llm"], **hosted}
    c["llm"].update(model=model, decision_interval=DECISION_INTERVAL, min_green=MIN_GREEN, seed=seed)
    return c


def run_one(cfg: dict, j: dict, root: Path, idle_mib: int | None) -> Path:
    c = run_cfg(cfg, j["model"], j["seed"])
    client = make_client(c["llm"])
    info = client.model_info()                   # raises if the server or model is missing
    local = isinstance(client, OllamaClient)
    t0 = time.perf_counter()
    warm = client.chat([{"role": "user", "content": "Reply with JSON."}], {"type": "object"})   # load / wake up
    warm_s = time.perf_counter() - t0
    sampler = VramSampler() if local and j["step"] == "bench" else None
    if sampler:
        sampler.start()
    try:
        out = run_experiment(c, j["scenario"], CONTROLLER, steps=j["steps"], seed=j["seed"], out_root=root / RUNS)
    finally:
        samples = sampler.stop() if sampler else None
    if sampler:
        ps = [m for m in client.loaded_models() if m["name"] == info["name"]]
        (out / "gpu.json").write_text(json.dumps({
            "gpu": gpu_name(), "idle_used_mib": idle_mib, "samples_mib": samples, "peak_used_mib": max(samples),
            "peak_minus_idle_mib": max(samples) - idle_mib,
            "sample_period_s": sampler.period, "warmup_call_s": warm_s,
            "ollama_ps": [{k: m.get(k) for k in ("name", "size", "size_vram", "context_length")} for m in ps],
            "note": "VRAM = nvidia-smi memory.used peak during the run minus the idle baseline before loading; "
                    "size_vram / size = share of the model Ollama placed on the GPU"}, indent=1))
    if not local:
        (out / "hosted.json").write_text(json.dumps({
            "model_requested": j["model"], "listed": info, "warmup_call_s": warm_s,
            "warmup_model_returned": warm.model, "run_finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "privacy": "hosted: every prompt of this run was sent to " + client.host,
            "local": False}, indent=1))
    return out


def estimate_s(j: dict, done: dict) -> float:
    b = done.get(key(*BENCH, j["model"]))
    per600 = json.loads((b / "summary.json").read_text())["provenance"]["wall_time_s"] if b else DEFAULT_WALL_PER_600_S
    if b is None and MODELS[j["model"]]["bench"] == "existing":
        per600 = {"llama3.2:3b": 308, "qwen2.5:3b": 310}.get(j["model"], DEFAULT_WALL_PER_600_S)
    return per600 * j["steps"] / 600


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--bench", action="store_true", help="step 1: the 600-step benchmark runs")
    ap.add_argument("--full", action="store_true", help="step 2: the full runs")
    ap.add_argument("--models", nargs="+", choices=list(MODELS), help="only these models")
    args = ap.parse_args()
    root = repo_root()
    (root / LOG).parent.mkdir(parents=True, exist_ok=True)
    handlers = [logging.StreamHandler(sys.stdout)] + ([] if args.dry_run else [logging.FileHandler(root / LOG)])
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S",
                        handlers=handlers, force=True)
    log = logging.getLogger("model_size")

    done = complete_runs(root, None if args.dry_run else log)
    steps = {s for s, on in (("bench", args.bench), ("full", args.full)) if on} or {"bench", "full"}
    plan = [j for j in jobs() if j["step"] in steps and (not args.models or j["model"] in args.models)]
    todo = [j for j in plan if job_key(j) not in done]
    log.info("%d runs selected, %d done, %d to do; estimated %.1f h left", len(plan), len(plan) - len(todo), len(todo),
             sum(estimate_s(j, done) for j in todo) / 3600)
    if args.dry_run:
        for j in jobs():
            print(f"{'done' if job_key(j) in done else 'todo'}  {j['step']:<5} {j['model']:<36} {j['scenario']:<20} "
                  f"s{j['seed']} {j['steps']} steps  ~{estimate_s(j, done) / 60:.0f} min")
        return
    if not (args.bench or args.full):
        raise SystemExit("Choose --bench (step 1) or --full (step 2)")
    if git_info()["dirty"]:
        raise SystemExit("Git tree is dirty: commit first so the runs' provenance points at the exact code")
    cfg = load_config(args.config)
    loaded, idle = None, None
    for n, j in enumerate(todo, 1):
        if MODELS[j["model"]]["provider"] == "ollama" and loaded != j["model"]:
            idle = free_gpu(OllamaClient.from_config(run_cfg(cfg, j["model"], 0)["llm"]))   # <= 300 MiB or exit
            loaded = j["model"]
        log.info("[%d/%d] start %s %s %s seed %d", n, len(todo), j["step"], j["model"], j["scenario"], j["seed"])
        t0 = time.perf_counter()
        out = run_one(cfg, j, root, idle)
        l = json.loads((out / "summary.json").read_text())["provenance"]["llm"]
        log.info("[%d/%d] done in %.0f s: %s (%d calls, %d failures, %d retries, p95 %.2f s, served %s)", n, len(todo),
                 time.perf_counter() - t0, out.relative_to(root), l["calls"], l["failures"], l["retries"],
                 l["latency_p95_s"] or 0, l["server_reported_models"])
    log.info("All %d selected runs are complete", len(plan))


if __name__ == "__main__":
    try:
        main()
    except BaseException as e:   # also KeyboardInterrupt / SystemExit: the log says why the batch stopped
        if not (isinstance(e, SystemExit) and e.code in (0, None)):
            logging.getLogger("model_size").exception("Batch stopped")
        raise
