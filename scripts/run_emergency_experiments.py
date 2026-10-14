"""Emergency-vehicle full experiments (pre-registered; NOT run until the user says so).

    python scripts/run_emergency_experiments.py              # run every missing run (clean git tree; free GPU)
    python scripts/run_emergency_experiments.py --report-only
    python scripts/run_emergency_experiments.py --check      # exit 1 if docs/emergency.md is out of date

Design, fixed and committed BEFORE any run:
  * scenario indian_2x2_peak_amb: peak traffic plus ambulances at 6/h (ASSUMPTION), seeds
    0-4, 3600 steps. Seeds 0-4 hold 37 ambulances, 29 of them signal-relevant (their route
    has at least one movement a signal controls; the rest only make free turns);
  * controllers maxpressure, fixedtime_webster, preemption_mp, and the LLM arm chosen by the
    final LLM design round (outputs/llm_benchmark/benchmark.json "final": its controller and
    model, with the rule's decision interval and min green 15 s). If the final round chose
    no LLM controller, only the three others run. If the chosen arm is the plain controller
    (llm_v3), it runs as is: its prompt has no ambulance information (only llm_guided_mp_v3
    and llm_guarded_mp list ambulances);
  * before the LLM runs every Ollama model is unloaded and the GPU must be idle (<= 300 MiB).
Analysis, fixed at the same time:
  * primary ambulance metric: mean travel time of the signal-relevant ambulances that
    finished, pooled over the 5 seeds; also its median, the mean stopped time, and the
    number not finished by t = 3600 s. All ambulances (incl. free-turn-only) reported too;
  * the same ambulances run under every controller (same flow files), so per-ambulance
    differences to preemption_mp are reported (mean and how many were faster/slower);
  * normal traffic: ATT, mean queue per intersection and finished trips, mean ± std over
    the 5 seeds;
  * no significance test is pre-registered: with 29 relevant ambulances the numbers are
    reported as measured, with their spread.

Outputs: outputs/emergency/runs/<run>/, outputs/emergency/results.json, tables in
docs/emergency.md.
"""
import argparse
import copy
import json
import re
import statistics
import sys
from pathlib import Path

from trafficsense.config import load_config, repo_root
from trafficsense.experiment import git_info, run_experiment
from trafficsense.llm.client import OllamaClient
from trafficsense.llm.gpu import free_gpu
from trafficsense.sim.emergency import signal_relevant
from trafficsense.sim.roadnet import load_roadnet

SCENARIO, SEEDS, STEPS = "indian_2x2_peak_amb", (0, 1, 2, 3, 4), 3600
BASE_CONTROLLERS = ["maxpressure", "fixedtime_webster", "preemption_mp"]
LLM_MIN_GREEN = 15
BENCHMARK = Path("outputs/llm_benchmark/benchmark.json")
RUNS = Path("outputs/emergency/runs")
OUT = Path("outputs/emergency/results.json")
DOC = Path("docs/emergency.md")
TABLES = ("emergency_full", "emergency_full_ambulances")


def llm_arm(root: Path) -> dict | None:
    """The final round's LLM choice: {controller, model, decision_interval_s}, or None."""
    final = json.loads((root / BENCHMARK).read_text()).get("final")
    if final is None:
        raise SystemExit("The final LLM design round is not complete (benchmark.json 'final' is empty)")
    if final["chosen_model"] is None:
        return None
    return {"controller": final["controller"], "model": final["model"],
            "decision_interval_s": final["decision_interval_s"]}


def controllers(root: Path) -> list[str]:
    arm = llm_arm(root)
    return BASE_CONTROLLERS + ([arm["controller"]] if arm else [])


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
        if (pv["scenario"], pv["sim_steps"]) != (SCENARIO, STEPS):
            raise SystemExit(f"{p}: not a full emergency run")
        runs[key] = {"dir": p.parent.name, "summary": s}
    return runs


def mean_std(xs):
    return [statistics.mean(xs), statistics.stdev(xs) if len(xs) > 1 else 0.0]


def report(root: Path) -> dict:
    ctls = controllers(root)
    runs = load_runs(root)
    missing = [(c, s) for c in ctls for s in SEEDS if (c, s) not in runs]
    if missing:
        raise SystemExit(f"Missing full emergency runs: {missing}")
    net = load_roadnet(root / "data/scenarios/indian_2x2/roadnet.json")
    out = {"provenance": {"script": "scripts/run_emergency_experiments.py", "scenario": SCENARIO,
                          "seeds": list(SEEDS), "steps": STEPS, "llm_arm": llm_arm(root),
                          "git_commit_of_this_summary": git_info()["commit"]},
           "controllers": {}}
    per_amb = {}
    for c in ctls:
        rs = [runs[(c, s)]["summary"] for s in SEEDS]
        ambs = [dict(a, seed=s["provenance"]["seed"], relevant=signal_relevant(net, a["route"]))
                for s in rs for a in s["emergency"]["vehicles"]]
        per_amb[c] = {(a["seed"], a["vehicle"]): a for a in ambs}
        rel = [a for a in ambs if a["relevant"]]

        def amb_stats(group):
            done = [a for a in group if a["finished"] is not None]
            tt = [a["travel_time_s"] for a in done]
            return {"n": len(group), "finished": len(done), "not_finished": len(group) - len(done),
                    "travel_time_mean_s": statistics.mean(tt) if tt else None,
                    "travel_time_median_s": statistics.median(tt) if tt else None,
                    "stopped_time_mean_s": statistics.mean(a["stopped_s"] for a in done) if done else None}
        out["controllers"][c] = {
            "runs": [r["dir"] for r in (runs[(c, s)] for s in SEEDS)],
            "att_s": mean_std([s["metrics"]["att"] for s in rs]),
            "queue_mean_per_intersection": mean_std([s["metrics"]["queue_mean_per_intersection"] for s in rs]),
            "throughput": mean_std([s["metrics"]["throughput"] for s in rs]),
            "ambulances_relevant": amb_stats(rel), "ambulances_all": amb_stats(ambs)}
    ref = per_amb["preemption_mp"]
    for c in ctls:
        diffs = [per_amb[c][k]["travel_time_s"] - ref[k]["travel_time_s"] for k, a in ref.items()
                 if a["relevant"] and a["finished"] is not None and per_amb[c][k]["finished"] is not None]
        out["controllers"][c]["vs_preemption_relevant"] = {
            "n_paired": len(diffs), "mean_diff_s": statistics.mean(diffs) if diffs else None,
            "faster": sum(d < 0 for d in diffs), "slower": sum(d > 0 for d in diffs)}
    return out


def fmt(x, nd):
    return "–" if x is None else f"{x:.{nd}f}"


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    return "\n".join(out + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def tables(b: dict) -> dict[str, str]:
    pm = lambda v, nd: f"{v[0]:.{nd}f} ± {v[1]:.{nd}f}"
    t1 = table(["Controller", "ATT (s)", "Queue / int. (veh)", "Finished trips"],
               [[c, pm(x["att_s"], 1), pm(x["queue_mean_per_intersection"], 2), pm(x["throughput"], 0)]
                for c, x in b["controllers"].items()])
    rows = []
    for c, x in b["controllers"].items():
        r, a, v = x["ambulances_relevant"], x["ambulances_all"], x["vs_preemption_relevant"]
        rows.append([c, f"{r['finished']} / {r['n']}", fmt(r["travel_time_mean_s"], 1), fmt(r["travel_time_median_s"], 1),
                     fmt(r["stopped_time_mean_s"], 1), fmt(a["travel_time_mean_s"], 1),
                     "–" if c == "preemption_mp" else
                     f"{fmt(v['mean_diff_s'], 1)} ({v['faster']} faster, {v['slower']} slower of {v['n_paired']})"])
    t2 = table(["Controller", "Relevant ambulances finished / total", "Travel time mean (s)", "Median (s)",
                "Stopped mean (s)", "All ambulances: travel time mean (s)",
                "Per ambulance vs preemption_mp (s)"], rows)
    return {"emergency_full": t1, "emergency_full_ambulances": t2}


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
        doc = (root / DOC).read_text()
        if not (root / OUT).is_file():
            empty = all(re.search(rf"<!-- BEGIN:{t} -->\n<!-- END:{t} -->", doc) for t in TABLES)
            print("no full emergency runs yet; doc tables are empty, as they should be" if empty else
                  "docs/emergency.md has full-run tables but outputs/emergency/results.json is missing")
            sys.exit(0 if empty else 1)
        b = json.loads((root / OUT).read_text())
        ok = render(doc, tables(b)) == doc and report(root)["controllers"] == b["controllers"]
        print("docs/emergency.md matches the full emergency runs" if ok else
              "docs/emergency.md or results.json is out of date; run with --report-only")
        sys.exit(0 if ok else 1)

    if not args.report_only:
        if git_info()["dirty"]:
            raise SystemExit("Git tree is dirty: commit first so the runs' provenance points at the exact code")
        cfg = load_config(args.config)
        have = load_runs(root)
        arm = llm_arm(root)
        for ctl in controllers(root):
            todo = [s for s in SEEDS if (ctl, s) not in have]
            if not todo:
                continue
            c = cfg
            if ctl.startswith("llm_"):
                c = copy.deepcopy(cfg)
                c["llm"].update(model=arm["model"], decision_interval=arm["decision_interval_s"],
                                min_green=LLM_MIN_GREEN)
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
