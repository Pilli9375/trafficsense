"""Emergency-vehicle smoke tests (Phase 3b): short runs that check the ambulance extension
end to end. They are NOT results: see "What these runs can show" below.

    python scripts/run_emergency_smoke.py              # run every missing run (clean git tree; free GPU)
    python scripts/run_emergency_smoke.py --report-only
    python scripts/run_emergency_smoke.py --check      # exit 1 if docs/emergency.md is out of date

Design, fixed and committed BEFORE any run:
  * scenario indian_2x2_peak_amb (peak traffic + ambulances, ~6/h), seeds 0, 1, 2, 600 steps;
  * controllers maxpressure (default), fixedtime_webster, preemption_mp (rule-based
    preemption, the non-LLM competitor) and llm_guided_mp (ambulances in the prompt);
  * llm_guided_mp runs with the benchmark timing (decision interval 5 s, min green 15 s) and
    the model the selection rule picks in the benchmark's hybrid arm
    (outputs/llm_benchmark/benchmark.json); if the rule picks none, the hybrid-arm model with
    the lowest failure rate, ties broken by the lower p95 latency. The model is read from
    benchmark.json at run time and recorded in each run's summary.json;
  * before the LLM runs every Ollama model is unloaded and the GPU must be idle (<= 300 MiB).
Reported per run: ATT, mean queue per intersection, finished trips; ambulances scheduled in
the 600 s, finished, their travel and stopped times (each ambulance listed); preemption
decisions (preemption_mp); LLM calls, failures, p95 latency, disagreement with MaxPressure and
decisions with an ambulance in view (llm_guided_mp).

What these runs can show: that ambulances are generated, tracked and measured, and that each
controller sees and acts on them. Not which controller is better: in the first 600 s seed 0
has no ambulance, seed 1 one that leaves by a free turn (no signal can affect it), seed 2 one
that goes straight through two signals. No ranking is made from these runs.

Outputs: outputs/emergency_smoke/runs/<run>/, outputs/emergency_smoke/smoke.json, tables in
docs/emergency.md.
"""
import argparse
import copy
import json
import re
import sys
from pathlib import Path

from trafficsense.config import load_config, repo_root
from trafficsense.experiment import git_info, run_experiment
from trafficsense.llm.client import OllamaClient
from trafficsense.llm.gpu import free_gpu

SCENARIO, SEEDS, STEPS = "indian_2x2_peak_amb", (0, 1, 2), 600
CONTROLLERS = ["maxpressure", "fixedtime_webster", "preemption_mp", "llm_guided_mp"]
LLM_TIMING = {"decision_interval": 5, "min_green": 15}
BENCHMARK = Path("outputs/llm_benchmark/benchmark.json")
RUNS = Path("outputs/emergency_smoke/runs")
OUT = Path("outputs/emergency_smoke/smoke.json")
DOC = Path("docs/emergency.md")


def hybrid_model(root: Path) -> tuple[str, str]:
    """(model, why) for llm_guided_mp, by the rule in the docstring."""
    arm = json.loads((root / BENCHMARK).read_text())["arms"].get("hybrid")
    if not arm or not arm["selection"]:
        raise SystemExit("The benchmark's hybrid arm is not complete; run scripts/benchmark_llm.py --arm hybrid")
    if arm["selection"]["chosen_model"]:
        return arm["selection"]["chosen_model"], "chosen by the selection rule in the benchmark's hybrid arm"
    m = min(arm["models"], key=lambda k: (arm["models"][k]["failure_rate"], arm["models"][k]["latency_p95_s"]))
    return m, "no hybrid model met the selection rule; lowest failure rate, then lower p95 latency"


def load_runs(root: Path) -> dict:
    runs = {}
    for p in sorted((root / RUNS).glob("*/summary.json")):
        s = json.loads(p.read_text())
        pv = s["provenance"]
        key = (pv["controller"], pv["seed"])
        if key in runs:
            raise SystemExit(f"Two runs for {key}: {runs[key]['dir']} and {p.parent.name}; remove the stale one")
        if pv["git_dirty"]:
            raise SystemExit(f"{p}: run from a dirty git tree, not citable")
        if (pv["scenario"], pv["sim_steps"]) != (SCENARIO, STEPS) or pv["controller"] not in CONTROLLERS:
            raise SystemExit(f"{p}: not a smoke-test run")
        runs[key] = {"dir": p.parent.name, "summary": s}
    return runs


def row(r: dict) -> dict:
    s = r["summary"]
    pv, m, e = s["provenance"], s["metrics"], s["emergency"]
    out = {"run": r["dir"], "controller": pv["controller"], "seed": pv["seed"], "git_commit": pv["git_commit"],
           "att_s": m["att"], "queue_mean_per_intersection": m["queue_mean_per_intersection"],
           "throughput": m["throughput"], "switches": s["signal"]["switches"],
           "ambulances_scheduled": e["scheduled_in_run"], "ambulances_finished": e["finished"],
           "ambulance_travel_time_mean_s": e["travel_time_mean_s"],
           "ambulance_stopped_time_mean_s": e["stopped_time_mean_s"], "ambulances": e["vehicles"]}
    if pv.get("controller_stats"):
        out["preemption_decisions"] = pv["controller_stats"]["preemption_decisions"]
        out["preemption_changed_maxpressure"] = pv["controller_stats"]["changed_maxpressure_decision"]
    if pv["llm"]:
        l = pv["llm"]
        out.update(model=pv["model"], calls=l["calls"], failures=l["failures"], failure_rate=l["failure_rate"],
                   latency_p95_s=l["latency_p95_s"], mp_disagreement_rate=l["mp_disagreement_rate"],
                   ambulance_decisions=l.get("ambulance_decisions", 0),
                   ambulance_decisions_serving_nearest=l.get("ambulance_decisions_serving_nearest", 0))
    return out


def report(root: Path) -> dict:
    runs = load_runs(root)
    missing = [(c, s) for c in CONTROLLERS for s in SEEDS if (c, s) not in runs]
    if missing:
        raise SystemExit(f"Missing smoke-test runs: {missing}")
    return {"provenance": {"script": "scripts/run_emergency_smoke.py", "scenario": SCENARIO, "seeds": list(SEEDS),
                           "steps": STEPS, "git_commit_of_this_summary": git_info()["commit"]},
            "runs": [row(runs[(c, s)]) for c in CONTROLLERS for s in SEEDS]}


def fmt(x, nd):
    return "–" if x is None else f"{x:.{nd}f}"


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    return "\n".join(out + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def tables(b: dict) -> dict[str, str]:
    rows = []
    for r in b["runs"]:
        if "preemption_decisions" in r:
            extra = f"{r['preemption_decisions']} preemption decisions ({r['preemption_changed_maxpressure']} " \
                    "differ from MaxPressure)"
        elif "calls" in r:
            pct = lambda x: "–" if x is None else f"{100 * x:.1f}%"
            extra = (f"`{r['model']}`: {r['calls']} calls, {pct(r['failure_rate'])} failed, p95 "
                     f"{fmt(r['latency_p95_s'], 2)} s, {pct(r['mp_disagreement_rate'])} differ from "
                     f"MaxPressure; {r['ambulance_decisions']} decisions with an ambulance in view "
                     f"({r['ambulance_decisions_serving_nearest']} gave it green)")
        else:
            extra = "–"
        rows.append([r["controller"], r["seed"], fmt(r["att_s"], 1), fmt(r["queue_mean_per_intersection"], 2),
                     r["throughput"], f"{r['ambulances_scheduled']} / {r['ambulances_finished']}",
                     fmt(r["ambulance_travel_time_mean_s"], 1), fmt(r["ambulance_stopped_time_mean_s"], 1), extra])
    t1 = table(["Controller", "Seed", "ATT at 600 s (s)", "Queue / int. (veh)", "Finished trips",
                "Ambulances scheduled / finished", "Ambulance travel time, mean (s)",
                "Ambulance stopped time, mean (s)", "Controller notes"], rows)
    rows = []
    for r in b["runs"]:
        for a in r["ambulances"]:
            rows.append([r["controller"], r["seed"], f"`{a['vehicle']}`", a["scheduled_start"],
                         " → ".join(a["route"]), fmt(a["travel_time_s"], 0) if a["finished"] is not None else
                         f"not finished ({fmt(a['time_so_far_s'], 0)} so far)",
                         fmt(a["stopped_s"], 0), fmt(a["entry_wait_s"], 0)])
    t2 = table(["Controller", "Seed", "Ambulance", "Scheduled start (s)", "Route (roads)", "Travel time (s)",
                "Stopped (s)", "Entry wait (s)"], rows)
    return {"emergency_smoke": t1, "emergency_ambulances": t2}


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
    ap.add_argument("--report-only", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    root = repo_root()

    if args.check:
        b = json.loads((root / OUT).read_text())
        doc = (root / DOC).read_text()
        ok = render(doc, tables(b)) == doc and report(root)["runs"] == b["runs"]
        print("docs/emergency.md matches the smoke-test runs" if ok else
              "docs/emergency.md or smoke.json is out of date; run scripts/run_emergency_smoke.py --report-only")
        sys.exit(0 if ok else 1)

    if not args.report_only:
        if git_info()["dirty"]:
            raise SystemExit("Git tree is dirty: commit first so the runs' provenance points at the exact code")
        cfg = load_config(args.config)
        have = load_runs(root)
        for ctl in CONTROLLERS:
            todo = [s for s in SEEDS if (ctl, s) not in have]
            if not todo:
                continue
            c = cfg
            if ctl.startswith("llm_"):
                model, why = hybrid_model(root)
                print(f"{ctl}: model {model} ({why})", flush=True)
                c = copy.deepcopy(cfg)
                c["llm"].update(model=model, **LLM_TIMING)
                free_gpu(OllamaClient.from_config(c["llm"]))
            for seed in todo:
                out = run_experiment(c, SCENARIO, ctl, steps=STEPS, seed=seed, out_root=root / RUNS)
                print(f"Wrote {out.relative_to(root)}", flush=True)

    b = report(root)
    (root / OUT).parent.mkdir(parents=True, exist_ok=True)
    (root / OUT).write_text(json.dumps(b, indent=1))
    (root / DOC).write_text(render((root / DOC).read_text(), tables(b)))
    print(f"Wrote {OUT} and updated {DOC}")


if __name__ == "__main__":
    main()
