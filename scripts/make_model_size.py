"""Tables (and, once the full runs exist, the chart) of docs/model_size.md, from the run folders.

    python scripts/make_model_size.py            # write outputs/model_size/model_size.json, update the doc
    python scripts/make_model_size.py --check    # exit 1 if the doc or model_size.json is out of date

Exploratory, added after the main results (scripts/run_model_size.py has the plan).
Benchmark (step 1): for every model of the study, its 600-step hybrid_v3 run on
indian_2x2_peak seed 0: the earlier ones from outputs/llm_benchmark/runs (validated by
scripts/benchmark_llm.py's loader), arms A and B from outputs/model_size/runs; MaxPressure's
600-step run from the same benchmark folder. "Follows pressure" is computed by replaying each
run (scripts/analyze_llm_decisions.py: the replay must reproduce the run's ATT exactly).
"""
import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

from trafficsense.config import load_config, repo_root
from trafficsense.experiment import git_info

ROOT = repo_root()
DOC = Path("docs/model_size.md")
OUT = Path("outputs/model_size/model_size.json")
# Parameter counts (billions) and their source; docs/model_size.md explains them.
SIZES = {"qwen2.5:3b": {"total_b": 3.1, "active": "3.1 (dense)"},
         "llama3.2:3b": {"total_b": 3.2, "active": "3.2 (dense)"},
         "gemma4:e4b": {"total_b": 7.5, "active": "E4B: effective 4"},
         "llama3.1:8b": {"total_b": 8.0, "active": "8.0 (dense)"},
         "nvidia/nemotron-3-ultra-550b-a55b": {"total_b": 550, "active": "55 (MoE)"}}


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


study = load("run_model_size")
bench_mod = load("benchmark_llm")
decisions = load("analyze_llm_decisions")


def bench_runs() -> tuple[dict[str, Path], Path]:
    """{model: run dir} of the 600-step hybrid_v3 runs, and MaxPressure's 600-step run."""
    old = bench_mod.load_runs(ROOT)
    new = study.complete_runs(ROOT)
    out = {}
    for m, spec in study.MODELS.items():
        if spec["bench"] == "existing":
            if ("hybrid_v3", m) in old:
                out[m] = ROOT / bench_mod.RUNS / old[("hybrid_v3", m)]["dir"]
        elif study.key(*study.BENCH, m) in new:
            out[m] = new[study.key(*study.BENCH, m)]
    return out, ROOT / bench_mod.RUNS / old[(None, "maxpressure")]["dir"]


def run_row(run: Path, cfg: dict) -> dict:
    s = json.loads((run / "summary.json").read_text())
    pv, m, l = s["provenance"], s["metrics"], s["provenance"]["llm"]
    if (pv["controller"], pv["scenario"], pv["seed"], pv["sim_steps"]) != (study.CONTROLLER, *study.BENCH):
        raise SystemExit(f"{run}: not a hybrid_v3 benchmark run")
    cp = pv["controller_params"]
    if (cp["prompt"], cp["decision_interval"], cp["min_green"], cp["options"]) != ("guided_v3", 5, 15, 2):
        raise SystemExit(f"{run}: not the study's controller setup ({cp})")
    rp = decisions.replay(cfg, run)
    gpu = json.loads((run / "gpu.json").read_text()) if (run / "gpu.json").is_file() else None
    ps = gpu["ollama_ps"][0] if gpu and gpu["ollama_ps"] else None
    return {"run": str(run.relative_to(ROOT)), "git_commit": pv["git_commit"], "timestamp": pv["timestamp"],
            "provider": pv["provider"], "served_models": l["server_reported_models"],
            "calls": l["calls"], "ok": l["ok"], "failures": l["failures"], "failures_by_type": l["failures_by_type"],
            "failure_rate": l["failure_rate"], "retries": l.get("retries"),
            "retries_by_reason": l.get("retries_by_reason"),
            "calls_with_reasoning_output": l.get("calls_with_reasoning_output"),
            "latency_mean_s": l["latency_mean_s"], "latency_p95_s": l["latency_p95_s"],
            "call_wall_p95_s": l.get("call_wall_p95_s"), "wall_time_s": pv["wall_time_s"],
            "att_s": m["att"], "queue_mean_per_intersection": m["queue_mean_per_intersection"],
            "throughput": m["throughput"],
            "follows_pressure_rate": rp["highest_pressure_rate"], "keep_rate": rp["keep_rate"],
            "mp_disagreement_rate": l["mp_disagreement_rate"],
            "vram_peak_minus_idle_mib": gpu["peak_minus_idle_mib"] if gpu else None,
            "ollama_size_vram_mib": ps["size_vram"] / 2**20 if ps else None,
            "ollama_size_mib": ps["size"] / 2**20 if ps else None}


def report() -> dict:
    cfg = load_config("configs/default.yaml")
    runs, mp_run = bench_runs()
    mp = json.loads((mp_run / "summary.json").read_text())["metrics"]
    bench = {}
    for m in study.MODELS:
        if m in runs:
            r = run_row(runs[m], cfg)
            r["att_vs_mp"] = (r["att_s"] - mp["att"]) / mp["att"]
            bench[m] = r
    return {"provenance": {"script": "scripts/make_model_size.py", "git_commit_of_this_summary": git_info()["commit"],
                           "label": "exploratory, added after the main results"},
            "sizes": SIZES,
            "bench": {"models": bench, "not_run": [m for m in study.MODELS if m not in bench],
                      "maxpressure": {"run": str(mp_run.relative_to(ROOT)), "att_s": mp["att"],
                                      "queue_mean_per_intersection": mp["queue_mean_per_intersection"],
                                      "throughput": mp["throughput"]}}}


def fmt(x, nd, pct=False):
    if x is None:
        return "–"
    return f"{100 * x:.{nd}f}%" if pct else f"{x:.{nd}f}"


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    return "\n".join(out + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def tables(b: dict) -> dict[str, str]:
    rows = []
    for m, e in b["bench"]["models"].items():
        sz = b["sizes"][m]
        fails = ", ".join(f"{t} {n}" for t, n in e["failures_by_type"].items()) or "none"
        retries = ("–" if e["retries"] is None else
                   f"{e['retries']}" + (f" ({', '.join(f'{k}: {v}' for k, v in e['retries_by_reason'].items())})"
                                        if e["retries"] else ""))
        where = "hosted (NIM)" if e["provider"] == "nvidia_nim" else "local (Ollama)"
        vram = ("–" if e["vram_peak_minus_idle_mib"] is None else
                f"{e['vram_peak_minus_idle_mib']} ({fmt(e['ollama_size_vram_mib'], 0)} / {fmt(e['ollama_size_mib'], 0)})")
        served = ", ".join(f"`{x}`" for x in e["served_models"])
        rows.append([f"`{m}`", where, f"{sz['total_b']:g} / {sz['active']}", vram, e["calls"],
                     f"{fmt(e['failure_rate'], 1, True)} ({fails})", retries,
                     f"{fmt(e['latency_mean_s'], 2)} / {fmt(e['latency_p95_s'], 2)}", fmt(e["call_wall_p95_s"], 2),
                     fmt(e["att_s"], 1), f"{100 * e['att_vs_mp']:+.1f}%", fmt(e["queue_mean_per_intersection"], 2),
                     fmt(e["follows_pressure_rate"], 0, True), fmt(e["mp_disagreement_rate"], 0, True),
                     f"{e['wall_time_s'] / 60:.0f}", served])
    rows += [[f"`{m}`", "not run yet"] + [""] * 14 for m in b["bench"]["not_run"]]
    mp = b["bench"]["maxpressure"]
    rows.append(["MaxPressure (baseline)", "–", "–", "–", "–", "–", "–", "–", "–", fmt(mp["att_s"], 1), "+0.0%",
                 fmt(mp["queue_mean_per_intersection"], 2), "–", "–", "–", "–"])
    t = table(["Model", "Where", "Parameters total / active (B)",
               "GPU memory: nvidia-smi peak − idle (Ollama size_vram / size), MiB", "Calls", "Failures", "Retries",
               "Latency mean / p95 (s)", "Whole call p95 (s)", "ATT at 600 s (s)", "ATT vs MaxPressure",
               "Queue / int. (veh)", "Follows pressure", "Answer differs from MaxPressure", "Wall time (min)",
               "Model id the server returned"], rows)
    return {"model_size_bench": t}


def render(doc: str, tabs: dict[str, str]) -> str:
    for name, body in tabs.items():
        begin, end = f"<!-- BEGIN:{name} -->", f"<!-- END:{name} -->"
        pat = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
        if not pat.search(doc):
            raise KeyError(f"Marker for table {name!r} missing in {DOC}")
        doc = pat.sub(lambda m: f"{begin}\n{body}\n{end}", doc)
    return doc


def comparable(b: dict) -> dict:
    return {k: v for k, v in b.items() if k != "provenance"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    b = report()
    tabs = tables(b)
    doc = (ROOT / DOC).read_text()
    if args.check:
        stored = json.loads((ROOT / OUT).read_text())
        ok = comparable(stored) == comparable(json.loads(json.dumps(b))) and render(doc, tabs) == doc
        print("docs/model_size.md matches the runs" if ok else "model-size results out of date; run "
              "scripts/make_model_size.py")
        sys.exit(0 if ok else 1)
    (ROOT / OUT).write_text(json.dumps(b, indent=1))
    (ROOT / DOC).write_text(render(doc, tabs))
    print(f"Wrote {OUT}; updated {DOC}")
    print(tabs["model_size_bench"])


if __name__ == "__main__":
    main()
