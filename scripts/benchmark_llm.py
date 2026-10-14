"""Benchmark local LLMs as the signal controller, then pick a model by a fixed rule.

    python scripts/benchmark_llm.py --arm v2                       # run an arm's models (clean git tree, free GPU)
    python scripts/benchmark_llm.py --arm v2 --models qwen2.5:3b   # (re)run some models only
    python scripts/benchmark_llm.py --report-only    # rebuild benchmark.json and the doc from the run folders
    python scripts/benchmark_llm.py --check          # exit 1 if docs/llm_benchmark.md is out of date

Setup (fixed): indian_2x2_peak, seed 0, 600 steps, decision interval 5 s and min green 15 s
(the tuned MaxPressure's timing, so LLM controllers and MaxPressure differ only in the
decision rule), every other setting from configs/default.yaml. Baselines on the same 600 s:
maxpressure (default) and fixedtime_webster; they are run once (deterministic) when missing.

Arms (one controller each):
  v1      llm_v1: cooperative, prompt v1. Phase 3a; its runs were made when this controller
          was called llm_cooperative (a run of llm_cooperative without a `prompt` parameter is
          v1). Models gemma3:4b, gemma4:e4b, llama3.2:3b, qwen2.5:3b.
  v2      llm_cooperative: cooperative, prompt v2 (Phase 3b). Models gemma4:e4b, llama3.2:3b,
          qwen2.5:3b; gemma3:4b is left out because it does not fit in the 4 GB of VRAM
          (Phase 3a: 1524 of 3308 MiB on the GPU).
  Target for v2, reported but not a criterion: < 300 prompt tokens per call (server count).
  hybrid  llm_guided_mp: MaxPressure ranks the phases, the LLM picks one of its top 2 or
          keeps the current phase; on a failed call MaxPressure's top choice is applied (and
          the failure counted). Cooperative, prompt "guided". Same 3 models as v2. Also
          reported: how often the LLM's choice differs from MaxPressure's top choice.

Final LLM design round (Phase 3b, pre-registered and committed BEFORE any of its runs):
  v3          llm_v3: v2 with the prompt fix v3 (llm/prompt.py: "HIGHER pressure = the phase
              needs green MORE", word limit out of the JSON placeholder). A post-hoc fix of a
              defect found in the v2/hybrid analysis, not part of the original design.
  hybrid_v3   llm_guided_mp_v3: the hybrid with prompt guided_v3 (same two changes).
  guarded_v3  llm_guarded_mp: hybrid_v3 whose answer is applied only if its pressure
              >= top - 0.2 x |top| (= 0.8 x top for top >= 0), else MaxPressure's choice;
              guard overrides are counted.
  Models gemma4:e4b, llama3.2:3b, qwen2.5:3b; same setup and the same selection rule.
  THIS IS THE FINAL LLM DESIGN ROUND. The final decision (benchmark.json "final"):
    1. the selection rule over all (arm, model) pairs of the three final-round arms;
       the chosen pair, with the rule's decision interval, goes to the full experiments,
       even if its queue is worse than MaxPressure's (that is reported, not acted on);
    2. if no final-round pair is eligible, the same rule over every (arm, model) pair of
       every round (v1, v2, hybrid and the final round);
    3. if nothing is eligible at all, no LLM controller goes to the full experiments.
  No further prompt or controller tuning after this round.

GPU: before each model, every model Ollama has loaded is unloaded and the GPU must then show
<= 300 MiB in use (nvidia-smi), else the script stops. The model is loaded with one short
warm-up call (its load time is recorded), so latencies are of a loaded model. VRAM is
measured by sampling nvidia-smi memory.used every second during the run (peak minus the
idle baseline); Ollama's /api/ps size/size_vram are recorded too.
ATT and queue are the simulator's, at step 600 (ATT counts vehicles still in the network up
to t = 600 s), for the LLM runs and the baselines alike.

Model selection rule, fixed and committed BEFORE the Phase 3a benchmark was run, and applied
unchanged in Phase 3b (committed before any v2 run):
  1. Eligible: failure rate < 2% of calls, and p95 latency < 3 s.
  2. Among eligible models, the lowest mean queue per intersection over the 600 s;
     tie-break the lower ATT.
  3. If no model is eligible, no model is recommended by the rule; the table is reported as is.
The rule is applied within each arm once all of the arm's models are run, and, once every
arm is complete, over all (arm, model) pairs together (Phase 3b: v1, v2 and hybrid; reported
as phase3b_selection). For the final round, the final decision above replaces that
recommendation.
Decision interval rule, fixed at the same time: the shortest multiple of the 5 s transition
that is >= (chosen model's p95 latency x number of intersections). On one GPU the calls of a
decision round run one after another, so this is the shortest interval at which a full round
fits in real time on this hardware (simulation itself pauses during calls).

Outputs: outputs/llm_benchmark/runs/<run>/ (summary.json, metrics.csv, decisions.jsonl,
gpu.json), outputs/llm_benchmark/benchmark.json, tables in docs/llm_benchmark.md.
"""
import argparse
import copy
import json
import math
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from trafficsense.config import load_config, repo_root
from trafficsense.experiment import git_info, run_experiment
from trafficsense.llm.client import OllamaClient
from trafficsense.llm.gpu import VramSampler, free_gpu, gpu_name

MODELS = ["gemma3:4b", "gemma4:e4b", "llama3.2:3b", "qwen2.5:3b"]
FITS_VRAM = ["gemma4:e4b", "llama3.2:3b", "qwen2.5:3b"]
ARMS = {"v1": {"controller": "llm_v1", "models": MODELS},
        "v2": {"controller": "llm_cooperative", "models": FITS_VRAM},
        "hybrid": {"controller": "llm_guided_mp", "models": FITS_VRAM},
        "v3": {"controller": "llm_v3", "models": FITS_VRAM},
        "hybrid_v3": {"controller": "llm_guided_mp_v3", "models": FITS_VRAM},
        "guarded_v3": {"controller": "llm_guarded_mp", "models": FITS_VRAM}}
EARLIER_ARMS = ["v1", "v2", "hybrid"]
FINAL_ARMS = ["v3", "hybrid_v3", "guarded_v3"]
LEGACY_V1 = "llm_cooperative"   # name of llm_v1 before prompt versions existed
PROMPT_TOKEN_TARGET = 300
BASELINES = ["maxpressure", "fixedtime_webster"]
SCENARIO, SEED, STEPS = "indian_2x2_peak", 0, 600
DECISION_INTERVAL, MIN_GREEN = 5, 15
MAX_FAILURE_RATE, MAX_P95_S = 0.02, 3.0
TRANSITION_S = 5
RUNS = Path("outputs/llm_benchmark/runs")
OUT = Path("outputs/llm_benchmark/benchmark.json")
DOC = Path("docs/llm_benchmark.md")


# ---- runs -----------------------------------------------------------------------------------
def bench_cfg(cfg: dict, model: str | None) -> dict:
    c = copy.deepcopy(cfg)
    c["llm"].update(model=model, decision_interval=DECISION_INTERVAL, min_green=MIN_GREEN)
    return c


def run_model(cfg: dict, arm: str, model: str, root: Path) -> Path:
    c = bench_cfg(cfg, model)
    client = OllamaClient.from_config(c["llm"])
    idle = free_gpu(client)   # <= 300 MiB used with no model loaded, else SystemExit
    info = client.model_info()
    t0 = time.perf_counter()
    client.chat([{"role": "user", "content": "Reply with JSON."}], {"type": "object"})   # load the model
    load_s = time.perf_counter() - t0
    sampler = VramSampler()
    sampler.start()
    try:
        out = run_experiment(c, SCENARIO, ARMS[arm]["controller"], steps=STEPS, seed=SEED, out_root=root / RUNS)
    finally:
        samples = sampler.stop()
    ps = [m for m in client.loaded_models() if m["name"] == info["name"]]
    gpu = {"gpu": gpu_name(), "idle_used_mib": idle, "samples_mib": samples, "peak_used_mib": max(samples),
           "peak_minus_idle_mib": max(samples) - idle, "sample_period_s": sampler.period,
           "warmup_call_s": load_s,
           "ollama_ps": [{k: m.get(k) for k in ("name", "size", "size_vram", "context_length")} for m in ps],
           "note": "VRAM = nvidia-smi memory.used peak during the run minus the idle baseline before loading"}
    (out / "gpu.json").write_text(json.dumps(gpu, indent=1))
    client.unload()
    return out


# ---- report ---------------------------------------------------------------------------------
def arm_of(pv: dict) -> str | None:
    """Benchmark arm of an LLM run (None for a baseline)."""
    c = pv["controller"]
    if not c.startswith("llm_"):
        return None
    if c == LEGACY_V1 and "prompt" not in pv["controller_params"]:
        return "v1"
    for arm, a in ARMS.items():
        if a["controller"] == c:
            return arm
    raise SystemExit(f"Run of controller {c!r} belongs to no benchmark arm")


def load_runs(root: Path) -> dict:
    """{(arm, model): run} for LLM runs, {(None, controller): run} for baselines."""
    runs = {}
    for p in sorted((root / RUNS).glob("*/summary.json")):
        s = json.loads(p.read_text())
        pv = s["provenance"]
        arm = arm_of(pv)
        key = (arm, pv["model"] if arm else pv["controller"])
        if key in runs:
            raise SystemExit(f"Two runs for {key}: {runs[key]['dir']} and {p.parent.name}; remove the stale one")
        if pv["git_dirty"]:
            raise SystemExit(f"{p}: run from a dirty git tree, not citable")
        if (pv["scenario"], pv["seed"], pv["sim_steps"]) != (SCENARIO, SEED, STEPS):
            raise SystemExit(f"{p}: not a benchmark run ({pv['scenario']}, seed {pv['seed']}, {pv['sim_steps']} steps)")
        if arm:
            cp = pv["controller_params"]
            if (cp["mode"], cp["decision_interval"], cp["min_green"]) != ("cooperative", DECISION_INTERVAL, MIN_GREEN):
                raise SystemExit(f"{p}: not the benchmark setup ({cp})")
            if key[1] not in ARMS[arm]["models"]:
                raise SystemExit(f"{p}: model {key[1]} is not in arm {arm}")
        runs[key] = {"dir": p.parent.name, "summary": s,
                     "gpu": json.loads((p.parent / "gpu.json").read_text()) if (p.parent / "gpu.json").is_file() else None}
    return runs


def row(r: dict) -> dict:
    s = r["summary"]
    m, pv = s["metrics"], s["provenance"]
    e = {"run": r["dir"], "controller": pv["controller"], "att_s": m["att"],
         "queue_mean_per_intersection": m["queue_mean_per_intersection"], "throughput": m["throughput"],
         "waiting_time_mean_s": m["waiting_time_mean"], "switches": s["signal"]["switches"],
         "git_commit": pv["git_commit"]}
    if pv["llm"]:
        l, g = pv["llm"], r["gpu"]
        e.update(model=pv["model"], prompt=pv["controller_params"].get("prompt", "v1"), digest=l["model_digest"], calls=l["calls"], failures=l["failures"],
                 failures_by_type=l["failures_by_type"], failure_rate=l["failure_rate"],
                 latency_mean_s=l["latency_mean_s"], latency_p95_s=l["latency_p95_s"],
                 latency_max_s=l["latency_max_s"], prompt_tokens_mean=l["prompt_tokens_mean"],
                 response_tokens_mean=l["response_tokens_mean"], switches_requested=l["switches_requested"],
                 wall_time_s=pv["wall_time_s"],
                 vram_peak_minus_idle_mib=g["peak_minus_idle_mib"], vram_peak_mib=g["peak_used_mib"],
                 ollama_size_vram_mib=(g["ollama_ps"][0]["size_vram"] / 2**20 if g["ollama_ps"] else None),
                 ollama_size_mib=(g["ollama_ps"][0]["size"] / 2**20 if g["ollama_ps"] else None),
                 warmup_call_s=g["warmup_call_s"], forced_switches=s["signal"]["forced_switches"],
                 mp_disagreement_rate=l.get("mp_disagreement_rate"), mp_disagreements=l.get("mp_disagreements"),
                 mp_disagreements_kept_current=l.get("mp_disagreements_kept_current"),
                 mp_fallbacks=l.get("mp_fallbacks"), guard_overrides=l.get("guard_overrides"),
                 guard_override_rate=l.get("guard_override_rate"),
                 applied_differs_from_mp=l.get("applied_differs_from_mp"))
    return e


def select(models: dict, n_intersections: int) -> dict:
    eligible = {k: v for k, v in models.items()
                if v["failure_rate"] < MAX_FAILURE_RATE and v["latency_p95_s"] < MAX_P95_S}
    out = {"rule": f"eligible: failure rate < {MAX_FAILURE_RATE:.0%} and p95 latency < {MAX_P95_S} s; "
                   "then lowest mean queue per intersection, tie-break lower ATT",
           "eligible": sorted(eligible), "chosen_model": None, "decision_interval_s": None,
           "interval_rule": f"shortest multiple of {TRANSITION_S} s >= p95 latency x {n_intersections} intersections"}
    if eligible:
        best = min(eligible, key=lambda k: (eligible[k]["queue_mean_per_intersection"], eligible[k]["att_s"]))
        need = eligible[best]["latency_p95_s"] * n_intersections
        out.update(chosen_model=best, round_p95_s=need,
                   decision_interval_s=TRANSITION_S * max(1, math.ceil(need / TRANSITION_S)))
    return out


def report(root: Path) -> dict:
    runs = load_runs(root)
    missing = [k for k in BASELINES if (None, k) not in runs]
    if missing:
        raise SystemExit(f"Missing baseline runs: {missing}")
    n_int = len(runs[(None, BASELINES[0])]["summary"]["per_intersection"])
    arms = {}
    for arm, a in ARMS.items():
        models = {m: row(runs[(arm, m)]) for m in a["models"] if (arm, m) in runs}
        done = len(models) == len(a["models"])
        arms[arm] = {"controller": a["controller"], "models": models,
                     "not_run": [m for m in a["models"] if m not in models],
                     "selection": select(models, n_int) if done else None}
    done = {a: arms[a]["selection"] is not None for a in ARMS}
    earlier = {f"{a} {m}": e for a in EARLIER_ARMS for m, e in arms[a]["models"].items()}
    return {"provenance": {"script": "scripts/benchmark_llm.py", "scenario": SCENARIO, "seed": SEED, "steps": STEPS,
                           "decision_interval_s": DECISION_INTERVAL, "min_green_s": MIN_GREEN,
                           "git_commit_of_this_summary": git_info()["commit"]},
            "arms": arms, "baselines": {k: row(runs[(None, k)]) for k in BASELINES},
            "phase3b_selection": select(earlier, n_int) if all(done[a] for a in EARLIER_ARMS) else None,
            "final": final_decision(arms, row(runs[(None, "maxpressure")]), n_int)}


def final_decision(arms: dict, mp: dict, n_int: int) -> dict | None:
    """The pre-registered final decision (docstring); None until the final-round arms are run."""
    if any(arms[a]["selection"] is None for a in FINAL_ARMS):
        return None

    def pool(names):
        return {f"{a} {m}": e for a in names for m, e in arms[a]["models"].items()}
    final = {"step": 1, "pool": "final-round arms", **select(pool(FINAL_ARMS), n_int)}
    if final["chosen_model"] is None:
        if any(arms[a]["selection"] is None for a in arms):
            raise SystemExit("No final-round pair is eligible and not every earlier arm is complete")
        final = {"step": 2, "pool": "every arm of every round", **select(pool(list(arms)), n_int)}
    if final["chosen_model"] is None:
        final["step"] = 3
        return final
    arm, model = final["chosen_model"].split(" ", 1)
    e = arms[arm]["models"][model]
    final.update(arm=arm, controller=ARMS[arm]["controller"], model=model,
                 queue_vs_maxpressure=[e["queue_mean_per_intersection"], mp["queue_mean_per_intersection"]],
                 worse_than_maxpressure=e["queue_mean_per_intersection"] > mp["queue_mean_per_intersection"])
    return final


def fmt(x, nd):
    return "–" if x is None else f"{x:.{nd}f}"


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    return "\n".join(out + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def tables(b: dict) -> dict[str, str]:
    rows = []
    for arm, x in b["arms"].items():
        elig = set(x["selection"]["eligible"]) if x["selection"] else set()
        for k, e in x["models"].items():
            fails = ", ".join(f"{t} {n}" for t, n in e["failures_by_type"].items()) or "none"
            rows.append([arm, f"`{k}`", e["calls"], f"{100 * e['failure_rate']:.1f}% ({fails})",
                         fmt(e["latency_mean_s"], 2), fmt(e["latency_p95_s"], 2), fmt(e["prompt_tokens_mean"], 0),
                         e["vram_peak_minus_idle_mib"],
                         fmt(e["ollama_size_vram_mib"], 0) + " / " + fmt(e["ollama_size_mib"], 0),
                         fmt(e["att_s"], 1), fmt(e["queue_mean_per_intersection"], 2), e["throughput"], e["switches"],
                         disagree(e), guard(e), ("yes" if k in elig else "no") if x["selection"] else "arm incomplete"])
        rows += [[arm, f"`{m}`", "not run"] + [""] * 13 for m in x["not_run"]]
    for k, e in b["baselines"].items():
        rows.append(["baseline", k, "–", "–", "–", "–", "–", "–", "–", fmt(e["att_s"], 1),
                     fmt(e["queue_mean_per_intersection"], 2), e["throughput"], e["switches"], "–", "–", "–"])
    t1 = table(["Arm", "Model", "Calls", "Failures", "Latency mean (s)", "Latency p95 (s)", "Prompt tokens (mean)",
                "VRAM, nvidia-smi peak − idle (MiB)", "Ollama size_vram / size (MiB)", "ATT at 600 s (s)",
                "Queue / int. (veh)", "Finished trips", "Switches", "LLM's answer differs from MaxPressure's choice",
                "Guard replaced the LLM's answer", "Eligible"], rows)

    # same model across arms
    models = list(dict.fromkeys(m for x in b["arms"].values() for m in x["models"]))
    arms = list(b["arms"])

    def grid(cell):
        rows = [[f"`{m}`"] + [cell(b["arms"][a]["models"][m]) if m in b["arms"][a]["models"] else "–" for a in arms]
                for m in models]
        return table(["Model"] + arms, rows)
    t2 = grid(lambda e: f"{fmt(e['queue_mean_per_intersection'], 2)} / {fmt(e['att_s'], 1)}")
    t2b = grid(lambda e: f"{fmt(e['latency_p95_s'], 2)} / {100 * e['failure_rate']:.1f}%")

    rows = []
    for arm, x in b["arms"].items():
        s = x["selection"]
        rows.append([arm, ", ".join(s["eligible"]) or "none" if s else "arm incomplete",
                     (s["chosen_model"] or "none") if s else "–", interval(s)])
    o = b["phase3b_selection"]
    rows.append(["Phase 3b: all of v1, v2, hybrid", ", ".join(o["eligible"]) or "none" if o else "incomplete",
                 (o["chosen_model"] or "none") if o else "–", interval(o)])
    f = b["final"]
    if f is None:
        rows.append(["**Final decision**", "final round incomplete", "–", "–"])
    else:
        where = {1: "final-round arms", 2: "every arm (no final-round pair eligible)",
                 3: "nothing eligible: no LLM controller"}[f["step"]]
        chosen = "none" if f["chosen_model"] is None else (
            f"**{f['chosen_model']}** (`{f['controller']}`); queue {f['queue_vs_maxpressure'][0]:.2f} vs "
            f"MaxPressure {f['queue_vs_maxpressure'][1]:.2f}" + (", worse than MaxPressure"
                                                                 if f["worse_than_maxpressure"] else ""))
        rows.append([f"**Final decision** ({where})", ", ".join(f["eligible"]) or "none", chosen, interval(f)])
    t3 = table(["Applied to", "Eligible", "Chosen", "Decision interval"], rows)
    return {"llm_benchmark": t1, "llm_compare": t2, "llm_compare_latency": t2b, "llm_selection": t3}


def disagree(e: dict) -> str:
    """Hybrid only: successful calls whose phase differs from MaxPressure's top choice."""
    if e.get("mp_disagreement_rate") is None:
        return "–"
    return (f"{100 * e['mp_disagreement_rate']:.1f}% ({e['mp_disagreements']}; "
            f"{e['mp_disagreements_kept_current']} kept current)")


def guard(e: dict) -> str:
    """Guarded arm only: successful calls whose answer the guard replaced by MaxPressure's choice."""
    if e.get("guard_override_rate") is None:
        return "–"
    return f"{100 * e['guard_override_rate']:.1f}% ({e['guard_overrides']})"


def interval(s: dict | None) -> str:
    if not s or s["decision_interval_s"] is None:
        return "–"
    return f"{s['decision_interval_s']} s (p95 × intersections = {s['round_p95_s']:.1f} s)"


def render(doc: str, tabs: dict[str, str]) -> str:
    for name, body in tabs.items():
        begin, end = f"<!-- BEGIN:{name} -->", f"<!-- END:{name} -->"
        pat = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
        if not pat.search(doc):
            raise KeyError(f"Marker for table {name!r} missing in {DOC}")
        doc = pat.sub(lambda m: f"{begin}\n{body}\n{end}", doc)
    return doc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--arm", choices=list(ARMS))
    ap.add_argument("--models", nargs="+", choices=MODELS, help="default: every model of the arm")
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--allow-dirty", action="store_true", help="for testing only; results are not citable")
    args = ap.parse_args()
    root = repo_root()

    if args.check:
        b = json.loads((root / OUT).read_text())
        doc = (root / DOC).read_text()
        fresh = report(root)
        ok = render(doc, tables(b)) == doc and all(fresh[k] == b.get(k) for k in ("arms", "baselines",
                                                                                   "phase3b_selection", "final"))
        print("docs/llm_benchmark.md matches the results" if ok else
              "docs/llm_benchmark.md or benchmark.json is out of date; run scripts/benchmark_llm.py --report-only")
        sys.exit(0 if ok else 1)

    if not args.report_only:
        if not args.arm:
            raise SystemExit("--arm is required to run models")
        bad = [m for m in args.models or [] if m not in ARMS[args.arm]["models"]]
        if bad:
            raise SystemExit(f"{bad} not in arm {args.arm}: {ARMS[args.arm]['models']}")
        if git_info()["dirty"] and not args.allow_dirty:
            raise SystemExit("Git tree is dirty: commit first so the runs' provenance points at the exact code")
        cfg = load_config(args.config)
        have = load_runs(root)
        for ctl in BASELINES:
            if (None, ctl) not in have:
                out = run_experiment(cfg, SCENARIO, ctl, steps=STEPS, seed=SEED, out_root=root / RUNS)
                print(f"Wrote {out.relative_to(root)}", flush=True)
        for m in args.models or ARMS[args.arm]["models"]:
            print(f"[{datetime.now():%H:%M:%S}] {args.arm} {m} ...", flush=True)
            out = run_model(cfg, args.arm, m, root)
            llm = json.loads((out / "summary.json").read_text())["provenance"]["llm"]
            print(f"  {out.relative_to(root)}: {llm['calls']} calls, {llm['failures']} failures, "
                  f"p95 {llm['latency_p95_s']:.2f} s", flush=True)

    b = report(root)
    (root / OUT).parent.mkdir(parents=True, exist_ok=True)
    (root / OUT).write_text(json.dumps(b, indent=1))
    if (root / DOC).is_file():
        (root / DOC).write_text(render((root / DOC).read_text(), tables(b)))
        print(f"Updated {DOC}")
    print(f"Wrote {OUT}")
    print(json.dumps({a: x["selection"] for a, x in b["arms"].items()} | {"final": b["final"]}, indent=1))


if __name__ == "__main__":
    main()
