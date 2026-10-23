"""Tables and chart of docs/model_size.md, from the run folders.

    python scripts/make_model_size.py            # write outputs/model_size/model_size.json, the doc, the chart
    python scripts/make_model_size.py --check    # exit 1 if any of them is out of date

Exploratory, added after the main results (scripts/run_model_size.py has the plan).
Step 1 (benchmark): for every model of the study, its 600-step hybrid_v3 run on
indian_2x2_peak seed 0: the earlier ones from outputs/llm_benchmark/runs (validated by
scripts/benchmark_llm.py's loader), arms A and B from outputs/model_size/runs; MaxPressure's
600-step run from the same benchmark folder. "Follows pressure" is computed by replaying each
run (scripts/analyze_llm_decisions.py: the replay must reproduce the run's ATT exactly).
Step 2 (full runs, 3600 steps): indian_2x2_peak seeds 0-2 and indian_2x2_peak_amb seeds 0-4;
gemma4's runs and the baselines (MaxPressure; preemption_mp on the emergency scenario) are the
full experiments' (outputs/full/runs, outputs/emergency/runs). "Follows pressure" is counted
from decisions.jsonl, which records MaxPressure's pressures at every decision; on the
benchmark runs that count must equal the replay's, and every count must agree with the run's
summary. A model whose runs are not all finished is listed as not finished, without numbers.
"""
import argparse
import importlib.util
import json
import re
import statistics
import sys
from pathlib import Path

from trafficsense.config import load_config, repo_root
from trafficsense.experiment import git_info
from trafficsense.sim.emergency import signal_relevant
from trafficsense.sim.roadnet import load_roadnet

ROOT = repo_root()
DOC = Path("docs/model_size.md")
OUT = Path("outputs/model_size/model_size.json")
CHART = Path("docs/figures/model_size.svg")
# Parameter counts (billions) and their source; docs/model_size.md explains them.
SIZES = {"qwen2.5:3b": {"total_b": 3.1, "active": "3.1 (dense)"},
         "llama3.2:3b": {"total_b": 3.2, "active": "3.2 (dense)"},
         "gemma4:e4b": {"total_b": 7.5, "active": "E4B: effective 4"},
         "llama3.1:8b": {"total_b": 8.0, "active": "8.0 (dense)"},
         "nvidia/nemotron-3-ultra-550b-a55b": {"total_b": 550, "active": "55 (MoE)"}}
SHORT = {"qwen2.5:3b": "qwen2.5 3B", "llama3.2:3b": "llama3.2 3B", "gemma4:e4b": "gemma4 e4b",
         "llama3.1:8b": "llama3.1 8B", "nvidia/nemotron-3-ultra-550b-a55b": "Nemotron 3 Ultra"}
EMERGENCY = "indian_2x2_peak_amb"
SCENARIOS = {"indian_2x2_peak": "Indian 2x2 peak", EMERGENCY: "Indian 2x2 peak with ambulances (emergency)"}
BASELINES = {"indian_2x2_peak": ["maxpressure"], EMERGENCY: ["maxpressure", "preemption_mp"]}
BASE_LABEL = {"maxpressure": "MaxPressure (baseline)", "preemption_mp": "MaxPressure + preemption (baseline)"}


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


study = load("run_model_size")
bench_mod = load("benchmark_llm")
decisions = load("analyze_llm_decisions")
full_mod = load("run_full_experiments")


def mean_std(xs):
    return [statistics.mean(xs), statistics.stdev(xs) if len(xs) > 1 else 0.0]


def check_setup(run: Path, pv: dict, scenario: str, seed: int, steps: int) -> None:
    if (pv["controller"], pv["scenario"], pv["seed"], pv["sim_steps"]) != (study.CONTROLLER, scenario, seed, steps):
        raise SystemExit(f"{run}: not a hybrid_v3 run of {scenario} seed {seed}, {steps} steps")
    if pv["git_dirty"]:
        raise SystemExit(f"{run}: run from a dirty git tree, not citable")
    cp = pv["controller_params"]
    if (cp["prompt"], cp["decision_interval"], cp["min_green"], cp["options"]) != ("guided_v3", 5, 15, 2):
        raise SystemExit(f"{run}: not the study's controller setup ({cp})")


def decision_counts(run: Path, l: dict) -> dict:
    """Counts from decisions.jsonl, checked against the run summary's LLM block `l`."""
    ds = [json.loads(line) for line in (run / "decisions.jsonl").open(encoding="utf-8")]
    ok = [d for d in ds if d["ok"]]
    failed = [d for d in ds if not d["ok"]]
    if any(d["phase"] != d["mp_choice"] for d in failed):
        raise SystemExit(f"{run}: a failed call did not fall back to MaxPressure's choice")
    highest = 0
    for d in ok:
        pr = {p: d["mp_pressures"][str(p)] for p in d["allowed"]}
        highest += pr[d["llm_phase"]] == max(pr.values())
    differs = sum(d["llm_phase"] != d["mp_choice"] for d in ok)
    retries = [r for d in ds for r in d.get("retries") or []]
    n = {"calls": len(ds), "ok": len(ok), "failures": len(failed), "highest": highest, "differs": differs,
         "retries": len(retries), "calls_with_retries": sum(bool(d.get("retries")) for d in ds)}
    if (n["calls"], n["failures"]) != (l["calls"], l["failures"]) or \
            abs(differs / len(ok) - l["mp_disagreement_rate"]) > 1e-12 or \
            ("retries" in l and n["retries"] != l["retries"]):
        raise SystemExit(f"{run}: decisions.jsonl disagrees with summary.json")
    return n


# ---------------------------------------------------------------- step 1: benchmark

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
    check_setup(run, pv, *study.BENCH)
    rp = decisions.replay(cfg, run)
    n = decision_counts(run, l)
    if n["highest"] / n["ok"] != rp["highest_pressure_rate"]:
        raise SystemExit(f"{run}: follows-pressure count from decisions.jsonl differs from the replay")
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


def bench_report(cfg: dict) -> dict:
    runs, mp_run = bench_runs()
    mp = json.loads((mp_run / "summary.json").read_text())["metrics"]
    bench = {}
    for m in study.MODELS:
        if m in runs:
            r = run_row(runs[m], cfg)
            r["att_vs_mp"] = (r["att_s"] - mp["att"]) / mp["att"]
            bench[m] = r
    return {"models": bench, "not_run": [m for m in study.MODELS if m not in bench],
            "maxpressure": {"run": str(mp_run.relative_to(ROOT)), "att_s": mp["att"],
                            "queue_mean_per_intersection": mp["queue_mean_per_intersection"],
                            "throughput": mp["throughput"]}}


# ---------------------------------------------------------------- step 2: full runs

def full_runs() -> tuple[dict[tuple, Path], dict[tuple, Path]]:
    """{(scenario, seed, model): run dir} of the finished full hybrid_v3 runs (new and reused), and
    {(scenario, seed, controller): run dir} of the baselines (all required)."""
    new = study.complete_runs(ROOT)
    old = full_mod.complete_runs(ROOT, full_mod.FULL_RUNS) | full_mod.complete_runs(ROOT, full_mod.EMERGENCY_RUNS)
    llm, base = {}, {}
    for sc, seed in study.FULL:
        for m, spec in study.MODELS.items():
            d = (old.get(full_mod.key(sc, study.CONTROLLER, seed, m)) if spec["full"] == "existing"
                 else new.get(study.key(sc, seed, study.FULL_STEPS, m)))
            if d is not None:
                llm[(sc, seed, m)] = d
        for c in BASELINES[sc]:
            d = old.get(full_mod.key(sc, c, seed, None))
            if d is None:
                raise SystemExit(f"Missing baseline run: {c} {sc} seed {seed}")
            base[(sc, seed, c)] = d
    return llm, base


def ambulances(s: dict, net) -> dict:
    """{vehicle: record} of the signal-relevant ambulances of one run (docs/emergency.md)."""
    return {a["vehicle"]: a for a in s["emergency"]["vehicles"] if signal_relevant(net, a["route"])}


def amb_stats(per_seed: dict[int, dict], ref: dict[str, dict[int, dict]]) -> dict:
    """Relevant ambulances pooled over the seeds, and paired differences against each reference."""
    ambs = [a for amb in per_seed.values() for a in amb.values()]
    done = [a for a in ambs if a["finished"] is not None]
    out = {"n": len(ambs), "finished": len(done),
           "travel_time_mean_s": statistics.mean(a["travel_time_s"] for a in done) if done else None,
           "stopped_time_mean_s": statistics.mean(a["stopped_s"] for a in done) if done else None}
    for name, other in ref.items():
        diffs = [a["travel_time_s"] - other[seed][v]["travel_time_s"] for seed, amb in per_seed.items()
                 for v, a in amb.items() if a["finished"] is not None and other[seed][v]["finished"] is not None]
        out[f"vs_{name}"] = {"n_paired": len(diffs), "mean_diff_s": statistics.mean(diffs) if diffs else None,
                             "faster": sum(d < 0 for d in diffs), "slower": sum(d > 0 for d in diffs)}
    return out


def full_report(cfg: dict) -> dict:
    llm, base = full_runs()
    net = load_roadnet(ROOT / cfg["scenarios"][EMERGENCY]["roadnet"])
    out = {}
    for sc in SCENARIOS:
        seeds = [s for c, s in study.FULL if c == sc]
        summ = {k: json.loads((d / "summary.json").read_text()) for k, d in base.items() if k[0] == sc}
        bl = {}
        for c in BASELINES[sc]:
            rs = [summ[(sc, s, c)] for s in seeds]
            bl[c] = {"runs": [str(base[(sc, s, c)].relative_to(ROOT)) for s in seeds],
                     "att_s": mean_std([r["metrics"]["att"] for r in rs]),
                     "queue_mean_per_intersection": mean_std([r["metrics"]["queue_mean_per_intersection"] for r in rs]),
                     "throughput": mean_std([r["metrics"]["throughput"] for r in rs])}
        mp_att = {s: summ[(sc, s, "maxpressure")]["metrics"]["att"] for s in seeds}
        if sc == EMERGENCY:
            ref = {c: {s: ambulances(summ[(sc, s, c)], net) for s in seeds} for c in BASELINES[sc]}
            for c in BASELINES[sc]:
                bl[c]["ambulances"] = amb_stats(ref[c], ref)
        models = {}
        for m in study.MODELS:
            done = [s for s in seeds if (sc, s, m) in llm]
            if done != seeds:
                models[m] = {"finished_seeds": done}
                continue
            runs = [llm[(sc, s, m)] for s in seeds]
            ss = [json.loads((d / "summary.json").read_text()) for d in runs]
            for d, s, seed in zip(runs, ss, seeds):
                check_setup(d, s["provenance"], sc, seed, study.FULL_STEPS)
            ls = [s["provenance"]["llm"] for s in ss]
            n = [decision_counts(d, l) for d, l in zip(runs, ls)]
            tot = {k: sum(x[k] for x in n) for k in n[0]}
            rel = [(s["metrics"]["att"] - mp_att[seed]) / mp_att[seed] for s, seed in zip(ss, seeds)]
            by_type = {}
            for l in ls:
                for t, k in l["failures_by_type"].items():
                    by_type[t] = by_type.get(t, 0) + k
            e = {"runs": [str(d.relative_to(ROOT)) for d in runs],
                 "timestamps": [s["provenance"]["timestamp"] for s in ss],
                 "served_models": sorted({x for l in ls for x in l["server_reported_models"]}),
                 "att_s": mean_std([s["metrics"]["att"] for s in ss]),
                 "att_vs_mp": {"mean": statistics.mean(rel), "min": min(rel), "max": max(rel),
                               "seeds_worse": sum(r > 0 for r in rel)},
                 "queue_mean_per_intersection": mean_std([s["metrics"]["queue_mean_per_intersection"] for s in ss]),
                 "throughput": mean_std([s["metrics"]["throughput"] for s in ss]),
                 "calls": tot["calls"], "failures": tot["failures"], "failures_by_type": by_type,
                 "fallback_to_mp_rate": tot["failures"] / tot["calls"],
                 "retries": tot["retries"] if all("retries" in l for l in ls) else None,
                 "calls_with_retries": tot["calls_with_retries"] if all("retries" in l for l in ls) else None,
                 "follows_pressure_rate": tot["highest"] / tot["ok"],
                 "follows_pressure_per_seed": [x["highest"] / x["ok"] for x in n],
                 "mp_disagreement_rate": tot["differs"] / tot["ok"],
                 "wall_time_s_mean": statistics.mean(s["provenance"]["wall_time_s"] for s in ss)}
            if sc == EMERGENCY:
                e["ambulances"] = amb_stats({seed: ambulances(s, net) for s, seed in zip(ss, seeds)}, ref)
            models[m] = e
        out[sc] = {"seeds": seeds, "baselines": bl, "models": models}
    cross_check(out)
    return out


def cross_check(full: dict) -> None:
    """The runs reused from the full experiments must give the numbers docs/results.md and
    docs/emergency.md report."""
    res = json.loads((ROOT / "outputs/full/results.json").read_text())["scenarios"]["indian_2x2_peak"]
    em = json.loads((ROOT / "outputs/emergency/results.json").read_text())["controllers"]
    by = {(v["controller"], v["model"]): v for v in res.values()}
    reused = [m for m, spec in study.MODELS.items() if spec["full"] == "existing"]
    pk, ek = full["indian_2x2_peak"], full[EMERGENCY]
    checks = [(pk["baselines"]["maxpressure"]["att_s"], by[("maxpressure", None)]["att"])]
    for c in BASELINES[EMERGENCY]:
        checks += [(ek["baselines"][c]["att_s"], em[c]["att_s"]),
                   (ek["baselines"][c]["ambulances"]["travel_time_mean_s"],
                    em[c]["ambulances_relevant"]["travel_time_mean_s"])]
    for m in reused:
        if "att_s" in pk["models"][m]:
            checks.append((pk["models"][m]["att_s"], by[(study.CONTROLLER, m)]["att"]))
        if "att_s" in ek["models"][m]:
            checks += [(ek["models"][m]["att_s"], em[study.CONTROLLER]["att_s"]),
                       (ek["models"][m]["ambulances"]["travel_time_mean_s"],
                        em[study.CONTROLLER]["ambulances_relevant"]["travel_time_mean_s"])]
    for ours, theirs in checks:
        if ours != theirs:
            raise SystemExit(f"Reused runs disagree with the full experiments' results: {ours} != {theirs}")


def hosted_runs(bench: dict) -> list[dict]:
    """Every finished run of arm B (benchmark and full), oldest first."""
    new = study.complete_runs(ROOT)
    rows = []
    for (sc, seed, steps, m), d in sorted(new.items(), key=lambda kv: kv[1].name):
        if m != study.HOSTED:
            continue
        s = json.loads((d / "summary.json").read_text())
        pv, l = s["provenance"], s["provenance"]["llm"]
        n = decision_counts(d, l)
        rows.append({"run": str(d.relative_to(ROOT)), "timestamp": pv["timestamp"], "scenario": sc, "seed": seed,
                     "steps": steps, "calls": n["calls"], "calls_with_retries": n["calls_with_retries"],
                     "retries": n["retries"], "retries_by_reason": l["retries_by_reason"],
                     "failures": n["failures"], "failures_by_type": l["failures_by_type"],
                     "fallback_to_mp_rate": n["failures"] / n["calls"], "wall_time_s": pv["wall_time_s"],
                     "wall_s_per_sim_s": pv["wall_time_s"] / steps, "rate_limit_wait_s": l["wait_s_total"],
                     "served_models": l["server_reported_models"]})
    return rows


def report() -> dict:
    cfg = load_config("configs/default.yaml")
    bench = bench_report(cfg)
    return {"provenance": {"script": "scripts/make_model_size.py", "git_commit_of_this_summary": git_info()["commit"],
                           "label": "exploratory, added after the main results"},
            "sizes": SIZES, "bench": bench, "full": full_report(cfg), "hosted_runs": hosted_runs(bench)}


# ---------------------------------------------------------------- rendering

def fmt(x, nd, pct=False):
    if x is None:
        return "–"
    return f"{100 * x:.{nd}f}%" if pct else f"{x:.{nd}f}"


def pm(ms, nd):
    return f"{ms[0]:.{nd}f} ± {ms[1]:.{nd}f}"


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    return "\n".join(out + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def bench_table(b: dict) -> str:
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
    return table(["Model", "Where", "Parameters total / active (B)",
                  "GPU memory: nvidia-smi peak − idle (Ollama size_vram / size), MiB", "Calls", "Failures", "Retries",
                  "Latency mean / p95 (s)", "Whole call p95 (s)", "ATT at 600 s (s)", "ATT vs MaxPressure",
                  "Queue / int. (veh)", "Follows pressure", "Answer differs from MaxPressure", "Wall time (min)",
                  "Model id the server returned"], rows)


def full_table(f: dict, sizes: dict) -> str:
    """One scenario's full runs: control quality and LLM reliability."""
    rows, nseeds = [], len(f["seeds"])
    for m, e in f["models"].items():
        if "att_s" not in e:
            rows.append([f"`{m}`", f"{sizes[m]['total_b']:g}",
                         f"not finished ({len(e['finished_seeds'])} of {nseeds} seeds)"] + [""] * 9)
            continue
        v = e["att_vs_mp"]
        fails = ", ".join(f"{t} {n}" for t, n in sorted(e["failures_by_type"].items()))
        rows.append([f"`{m}`", f"{sizes[m]['total_b']:g}", pm(e["att_s"], 1),
                     f"{100 * v['mean']:+.1f}% ({100 * v['min']:+.1f} to {100 * v['max']:+.1f})",
                     f"{v['seeds_worse']} of {nseeds}", pm(e["queue_mean_per_intersection"], 2),
                     fmt(e["follows_pressure_rate"], 0, True), fmt(e["mp_disagreement_rate"], 0, True),
                     f"{e['failures']} of {e['calls']} ({fmt(e['fallback_to_mp_rate'], 1, True)})"
                     + (f": {fails}" if fails else ""),
                     "–" if e["retries"] is None else e["retries"], f"{e['wall_time_s_mean'] / 60:.0f}",
                     ", ".join(f"`{x}`" for x in e["served_models"])])
    for c, e in f["baselines"].items():
        rows.append([BASE_LABEL[c], "–", pm(e["att_s"], 1), "+0.0%" if c == "maxpressure" else "–", "–",
                     pm(e["queue_mean_per_intersection"], 2)] + ["–"] * 6)
    return table(["Model", "Total params (B)", "ATT (s), mean ± std", "ATT vs MaxPressure, mean (range over seeds)",
                  "Seeds worse than MaxPressure", "Queue / int. (veh)", "Follows pressure",
                  "Answer differs from MaxPressure", "Failed calls → MaxPressure's choice applied", "Retries",
                  "Wall time / run (min)", "Model id the server returned"], rows)


def amb_table(f: dict) -> str:
    def paired(p):
        if p["mean_diff_s"] is None:
            return "–"
        return f"{p['mean_diff_s']:+.1f} s ({p['faster']} faster, {p['slower']} slower, of {p['n_paired']})"

    rows = []
    entries = [(f"`{m}`", e.get("ambulances"), e) for m, e in f["models"].items()] + \
              [(BASE_LABEL[c], e["ambulances"], e) for c, e in f["baselines"].items()]
    for label, a, e in entries:
        if a is None:
            rows.append([label, f"not finished ({len(e['finished_seeds'])} of {len(f['seeds'])} seeds)", "", "", "", ""])
            continue
        rows.append([label, f"{a['finished']} of {a['n']}", fmt(a["travel_time_mean_s"], 1),
                     fmt(a["stopped_time_mean_s"], 1), paired(a["vs_maxpressure"]), paired(a["vs_preemption_mp"])])
    return table(["Controller / model", "Signal-relevant ambulances finished", "Travel time, mean (s)",
                  "Stopped time, mean (s)", "vs MaxPressure, paired", "vs MaxPressure + preemption, paired"], rows)


def hosted_table(runs: list[dict]) -> str:
    rows = []
    for r in runs:
        reasons = ", ".join(f"{k}: {v}" for k, v in sorted(r["retries_by_reason"].items()))
        fails = ", ".join(f"{t} {n}" for t, n in sorted(r["failures_by_type"].items()))
        rows.append([r["timestamp"][:16].replace("T", " "), f"{r['scenario']} s{r['seed']}", r["steps"], r["calls"],
                     f"{r['calls_with_retries']} ({fmt(r['calls_with_retries'] / r['calls'], 0, True)})",
                     f"{r['retries']}" + (f" ({reasons})" if reasons else ""),
                     f"{r['failures']} ({fmt(r['fallback_to_mp_rate'], 1, True)})" + (f": {fails}" if fails else ""),
                     f"{r['wall_time_s'] / 60:.0f}", f"{r['wall_s_per_sim_s']:.2f}", f"{r['rate_limit_wait_s'] / 60:.0f}",
                     ", ".join(f"`{x}`" for x in r["served_models"])])
    t = table(["Started (IST)", "Run", "Sim steps", "Calls", "Calls that needed retries", "Retries (HTTP status)",
               "Failed calls → MaxPressure's choice applied", "Wall time (min)", "Wall s per sim s",
               "Client waits: rate limiter + backoff (min)", "Model id the server returned"], rows)
    return t + f"\n\n{len(runs)} of {1 + len(study.FULL)} arm B runs finished."


def tables(b: dict) -> dict[str, str]:
    full = b.get("full")
    out = {"model_size_bench": bench_table(b)}
    if full is not None:
        out |= {"model_size_full": full_table(full["indian_2x2_peak"], b["sizes"]),
                "model_size_full_amb": full_table(full[EMERGENCY], b["sizes"]),
                "model_size_ambulances": amb_table(full[EMERGENCY]),
                "model_size_hosted": hosted_table(b["hosted_runs"])}
    return out


# ---------------------------------------------------------------- chart (hand-written SVG, deterministic)

SERIES = [("indian_2x2_peak", "Peak (3 seeds)", "s1"), (EMERGENCY, "Emergency (5 seeds)", "s2")]
STYLE = """<style>
  .bg { fill: #fcfcfb; } .t1 { fill: #0b0b0b; } .t2 { fill: #52514e; } .grid { stroke: #e4e3df; }
  .axis { stroke: #8a8985; } .ref { stroke: #52514e; stroke-dasharray: 4 3; }
  .s1 { fill: #2a78d6; stroke: #2a78d6; } .s2 { fill: #eb6834; stroke: #eb6834; }
  .ring { stroke: #fcfcfb; stroke-width: 2; } .wh { stroke-width: 2; fill: none; }
  text { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; font-size: 12px; }
  .title { font-size: 13px; font-weight: 600; } .small { font-size: 11px; }
  @media (prefers-color-scheme: dark) {
    .bg { fill: #1a1a19; } .t1 { fill: #f0efec; } .t2 { fill: #c3c2b7; } .grid { stroke: #34332f; }
    .axis { stroke: #8a8985; } .ref { stroke: #c3c2b7; }
    .s1 { fill: #3987e5; stroke: #3987e5; } .s2 { fill: #d95926; stroke: #d95926; } .ring { stroke: #1a1a19; }
  }
</style>"""


def nice_ticks(lo, hi, n=4):
    span = hi - lo
    step = min((s * 10 ** e for e in range(-2, 4) for s in (1, 2, 2.5, 5) if span / (s * 10 ** e) <= n),
               default=10 ** 4)
    first = step * int(lo // step)
    ticks = [round(first, 6)]
    while ticks[-1] < hi - 1e-9:                     # the last tick covers the largest value
        ticks.append(round(ticks[-1] + step, 6))
    return ticks


def svg(b: dict) -> str:
    full = b["full"]
    models = list(study.MODELS)
    W, left, top, row_h, pw, gap = 900, 190, 78, 40, 210, 26
    H = top + row_h * len(models) + 76
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
           f'role="img" aria-labelledby="t d">',
           '<title id="t">Control quality vs model size</title>',
           '<desc id="d">Exploratory. For each model, ordered by total parameters: ATT relative to MaxPressure, '
           'signal-relevant ambulance travel time, and the share of decisions that pick the highest-pressure '
           'phase. Dots are means over seeds, whiskers the range over seeds. The tables in '
           'docs/model_size.md hold the numbers.</desc>', STYLE, f'<rect class="bg" width="{W}" height="{H}"/>']
    # legend
    x = left
    for _, label, cls in SERIES:
        out.append(f'<circle class="{cls}" cx="{x + 5}" cy="20" r="5"/>'
                   f'<text class="t1" x="{x + 15}" y="24">{label}</text>')
        x += 170
    out.append(f'<line class="axis wh" x1="{x}" y1="20" x2="{x + 18}" y2="20"/>'
               f'<text class="t2" x="{x + 24}" y="24">range over seeds</text>')
    ys = {m: top + row_h * i + row_h / 2 for i, m in enumerate(models)}
    for m in models:
        sz = b["sizes"][m]
        size = (f'{sz["total_b"]:.1f} B' if sz["total_b"] < 100 else f'{sz["total_b"]:g} B') + (f', {sz["active"].split()[0]} B active' if "MoE" in sz["active"] else "")
        out.append(f'<text class="t1" x="16" y="{ys[m] - 2:.1f}">{SHORT[m]}</text>'
                   f'<text class="t2 small" x="16" y="{ys[m] + 12:.1f}">{size}</text>')

    def entry(sc, m):
        e = full[sc]["models"][m]
        return e if "att_s" in e else None

    def att(sc, m):
        e = entry(sc, m)
        return e and (100 * e["att_vs_mp"]["mean"], 100 * e["att_vs_mp"]["min"], 100 * e["att_vs_mp"]["max"])

    def amb(sc, m):
        e = entry(sc, m)
        return e and (e["ambulances"]["travel_time_mean_s"], None, None)

    def follows(sc, m):
        e = entry(sc, m)
        return e and (100 * e["follows_pressure_rate"], 100 * min(e["follows_pressure_per_seed"]),
                      100 * max(e["follows_pressure_per_seed"]))

    em = full[EMERGENCY]["baselines"]
    panels = [("ATT vs MaxPressure (%)", att, SERIES, [(0, "MaxPressure")], None),
              ("Ambulance travel time (s)", amb, SERIES[1:],
               [(em["maxpressure"]["ambulances"]["travel_time_mean_s"], "MaxPressure"),
                (em["preemption_mp"]["ambulances"]["travel_time_mean_s"], "MP + preemption")], 0),
              ("Follows pressure (%)", follows, SERIES, [], (0, 100))]
    for k, (title, get, series, refs, fixed) in enumerate(panels):
        x0 = left + k * (pw + gap)
        vals = [v for sc, _, _ in series for m in models if (p := get(sc, m)) for v in p if v is not None]
        vals += [r for r, _ in refs]
        lo, hi = (fixed if isinstance(fixed, tuple) else
                  ((fixed if fixed is not None else min(vals)), max(vals)))
        ticks = nice_ticks(lo, hi)
        lo, hi = min(lo, ticks[0]), max(hi, ticks[-1])
        sx = lambda v: x0 + (v - lo) / (hi - lo) * pw                                         # noqa: E731
        y_end = top + row_h * len(models)
        out.append(f'<text class="t1 title" x="{x0}" y="{top - 22}">{title}</text>')
        for t in ticks:
            out.append(f'<line class="grid" x1="{sx(t):.1f}" y1="{top - 8}" x2="{sx(t):.1f}" y2="{y_end}"/>'
                       f'<text class="t2 small" x="{sx(t):.1f}" y="{y_end + 16}" text-anchor="middle">{t:g}</text>')
        for i, (r, label) in enumerate(refs):                # staggered so neighbouring labels never overlap
            out.append(f'<line class="ref" x1="{sx(r):.1f}" y1="{top - 8}" x2="{sx(r):.1f}" y2="{y_end}"/>'
                       f'<text class="t2 small" x="{sx(r):.1f}" y="{y_end + 32 + 13 * i}" '
                       f'text-anchor="middle">{label}</text>')
        for m in models:
            if all(get(sc, m) is None for sc, _, _ in series):
                out.append(f'<text class="t2 small" x="{x0 + 4}" y="{ys[m] + 4:.1f}">not finished</text>')
                continue
            for j, (sc, _, cls) in enumerate(series):
                y = ys[m] + (0 if len(series) == 1 else (-6 if j == 0 else 6))
                p = get(sc, m)
                if p is None:
                    out.append(f'<text class="t2 small" x="{x0 + 4}" y="{y + 4:.1f}">not finished</text>')
                    continue
                if p[1] is not None:
                    out.append(f'<line class="{cls} wh" x1="{sx(p[1]):.1f}" y1="{y:.1f}" x2="{sx(p[2]):.1f}" '
                               f'y2="{y:.1f}"/>')
                out.append(f'<circle class="{cls} ring" cx="{sx(p[0]):.1f}" cy="{y:.1f}" r="5"/>')
    out.append(f'<text class="t2 small" x="16" y="{H - 8}">Exploratory, added after the main results. Models '
               'ordered by total parameters (not to scale). Generated by scripts/make_model_size.py.</text>')
    return "\n".join(out + ["</svg>"]) + "\n"


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
    chart = svg(b)
    if args.check:
        stored = json.loads((ROOT / OUT).read_text())
        ok = (comparable(stored) == comparable(json.loads(json.dumps(b))) and render(doc, tabs) == doc
              and (ROOT / CHART).is_file() and (ROOT / CHART).read_text() == chart)
        print("docs/model_size.md and its chart match the runs" if ok else
              "model-size results out of date; run scripts/make_model_size.py")
        sys.exit(0 if ok else 1)
    (ROOT / OUT).write_text(json.dumps(b, indent=1))
    (ROOT / DOC).write_text(render(doc, tabs))
    (ROOT / CHART).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / CHART).write_text(chart)
    print(f"Wrote {OUT}, {CHART}; updated {DOC}")
    for name, t in tabs.items():
        print(f"\n## {name}\n{t}")


if __name__ == "__main__":
    main()
