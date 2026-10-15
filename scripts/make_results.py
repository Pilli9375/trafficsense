"""Generate the tables of docs/results.md (and the full-run tables of docs/emergency.md) from the
full-experiment runs.

    python scripts/make_results.py            # write outputs/full/results.json, update both docs
    python scripts/make_results.py --check    # exit 1 if a doc or results.json is out of date

Inputs: the complete runs of the plan in scripts/run_full_experiments.py (outputs/full/runs/,
outputs/emergency/runs/); every planned run must be present. Mean ± std is over seeds (sample
std, ddof = 1). LLM decision statistics are pooled over the seeds of a scenario: counts are
summed, mean latency is weighted by the number of answered calls, and p95 is given as the range
of the per-run p95 values. "Reproduces earlier runs" compares each baseline run with the earlier
run of the same scenario, controller, seed, parameters and flow file (outputs/indian_2x2/runs,
outputs/baselines/runs) and reports whether every metric is identical. The paired table gives,
per seed, each arm's ATT minus MaxPressure's ATT on the same seed (same flow file).
"""
import argparse
import importlib.util
import json
import re
import statistics
import sys
from pathlib import Path

from trafficsense.config import repo_root
from trafficsense.experiment import git_info

ROOT = repo_root()
DOC = Path("docs/results.md")
OUT = Path("outputs/full/results.json")
EARLIER = [Path("outputs/indian_2x2/runs"), Path("outputs/baselines/runs")]
SCENARIOS = [("indian_2x2_offpeak", "Indian 2x2, off-peak (2375 veh/h)"),
             ("indian_2x2_peak", "Indian 2x2, peak (4750 veh/h)"),
             ("jinan_3x4", "Jinan 3x4 (CoLLMLight real-world flow)")]
METRICS = [("att", "ATT (s)", 1), ("queue_mean_per_intersection", "Queue / int. (veh)", 2),
           ("waiting_time_mean", "Waiting / vehicle (s)", 1), ("throughput", "Finished trips", 0)]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


batch = load("run_full_experiments")
emergency = load("run_emergency_experiments")


def label(controller: str, model: str | None) -> str:
    if controller == batch.MAIN["controller"] and model == batch.MAIN["model"]:
        return f"LLM main: guarded hybrid, `{model}`"
    if controller == batch.EXPLORATORY["controller"] and model == batch.EXPLORATORY["model"]:
        return f"LLM exploratory, NOT selected by the rule: hybrid_v3, `{model}`"
    return {"maxpressure": "MaxPressure", "fixedtime_webster": "Webster fixed time",
            "fixedtime": "FixedTime (4 phases, 30 s)", "preemption_mp": "Preemption (rule-based)"}[controller]


def runs() -> dict[tuple, dict]:
    done = {}
    for out_root in (batch.FULL_RUNS, batch.EMERGENCY_RUNS):
        for k, d in batch.complete_runs(ROOT, out_root).items():
            done[k] = {"dir": str(d.relative_to(ROOT)), "summary": json.loads((d / "summary.json").read_text())}
    missing = [batch.job_key(j) for j in batch.jobs() if batch.job_key(j) not in done]
    if missing:
        raise SystemExit(f"{len(missing)} planned runs are missing, e.g. {missing[:3]}; the batch is not finished")
    return done


def mean_std(xs):
    return [statistics.mean(xs), statistics.stdev(xs) if len(xs) > 1 else 0.0]


def arms_of(scenario):
    seen = []
    for j in batch.jobs():
        if j["scenario"] == scenario:
            a = (j["controller"], j["llm"]["model"] if j["llm"] else None)
            if a not in seen:
                seen.append(a)
    return seen


def seeds_of(scenario, arm):
    return sorted({j["seed"] for j in batch.jobs() if j["scenario"] == scenario and
                   (j["controller"], j["llm"]["model"] if j["llm"] else None) == arm})


def llm_stats(summaries: list[dict]) -> dict:
    ls = [s["provenance"]["llm"] for s in summaries]
    calls, ok = sum(l["calls"] for l in ls), sum(l["ok"] for l in ls)
    fails: dict[str, int] = {}
    for l in ls:
        for t, n in l["failures_by_type"].items():
            fails[t] = fails.get(t, 0) + n
    lat_n = sum(l["latency_n"] for l in ls)
    out = {"calls": calls, "ok": ok, "failures": sum(fails.values()), "failures_by_type": dict(sorted(fails.items())),
           "failure_rate": sum(fails.values()) / calls,
           "latency_mean_s": sum(l["latency_mean_s"] * l["latency_n"] for l in ls) / lat_n,
           "latency_p95_s_range": [min(l["latency_p95_s"] for l in ls), max(l["latency_p95_s"] for l in ls)],
           "mp_disagreements": sum(l["mp_disagreements"] for l in ls),
           "mp_disagreement_rate": sum(l["mp_disagreements"] for l in ls) / ok,
           "guard_overrides": None, "applied_differs_from_mp": None,
           "wall_time_h": sum(s["provenance"]["wall_time_s"] for s in summaries) / 3600,
           "max_consecutive_failures_reached": False}
    if all("guard_overrides" in l for l in ls):
        out["guard_overrides"] = sum(l["guard_overrides"] for l in ls)
        out["guard_override_rate"] = out["guard_overrides"] / ok
        out["applied_differs_from_mp"] = sum(l["applied_differs_from_mp"] for l in ls)
    else:   # unguarded hybrid: the applied phase is the LLM's answer, or MaxPressure's on a failure
        out["applied_differs_from_mp"] = out["mp_disagreements"]
    out["applied_differs_rate"] = out["applied_differs_from_mp"] / calls
    return out


def paired(rs: dict, scenario: str) -> dict:
    """Per seed: ATT of each arm minus MaxPressure's ATT on the same seed."""
    out = {}
    for arm in arms_of(scenario):
        if arm[0] == "maxpressure":
            continue
        d = [rs[(scenario, arm[0], s, arm[1])]["summary"]["metrics"]["att"]
             - rs[(scenario, "maxpressure", s, None)]["summary"]["metrics"]["att"] for s in seeds_of(scenario, arm)]
        out[label(*arm)] = {"seeds": seeds_of(scenario, arm), "att_minus_mp": d,
                            "seeds_lower_att": sum(x < 0 for x in d), "seeds_higher_att": sum(x > 0 for x in d)}
    return out


def earlier_runs() -> dict[tuple, dict]:
    out = {}
    for root in EARLIER:
        for p in (ROOT / root).glob("*/summary.json"):
            s = json.loads(p.read_text())
            pv = s["provenance"]
            k = (pv["scenario"], pv["controller"], pv["seed"], pv["flow_sha256"],
                 json.dumps(pv["controller_params"], sort_keys=True), pv["sim_steps"])
            out[k] = {"dir": str(p.parent.relative_to(ROOT)), "summary": s}
    return out


def report() -> dict:
    rs = runs()
    res = {"provenance": {"script": "scripts/make_results.py", "git_commit_of_this_summary": git_info()["commit"],
                          "runs": len(rs)},
           "scenarios": {}, "llm": {}, "paired": {}, "reproduction": []}
    for sc, _ in SCENARIOS:
        res["scenarios"][sc] = {}
        for arm in arms_of(sc):
            ss = [rs[(sc, arm[0], s, arm[1])]["summary"] for s in seeds_of(sc, arm)]
            res["scenarios"][sc][label(*arm)] = {
                "controller": arm[0], "model": arm[1], "seeds": seeds_of(sc, arm),
                "runs": [rs[(sc, arm[0], s, arm[1])]["dir"] for s in seeds_of(sc, arm)],
                **{m: mean_std([s["metrics"][m] for s in ss]) for m, _, _ in METRICS},
                "per_seed_att": [s["metrics"]["att"] for s in ss]}
    for sc in [s for s, _ in SCENARIOS] + ["indian_2x2_peak_amb"]:
        res["paired"][sc] = paired(rs, sc)
        for arm in arms_of(sc):
            if arm[1] is None:
                continue
            ss = [rs[(sc, arm[0], s, arm[1])]["summary"] for s in seeds_of(sc, arm)]
            res["llm"][f"{sc} | {label(*arm)}"] = {"scenario": sc, "arm": label(*arm), **llm_stats(ss)}
    old = earlier_runs()
    for (sc, c, seed, model), r in sorted(rs.items(), key=lambda x: str(x[0])):
        if model is not None:
            continue
        pv = r["summary"]["provenance"]
        k = (sc, c, seed, pv["flow_sha256"], json.dumps(pv["controller_params"], sort_keys=True), pv["sim_steps"])
        if k in old:
            res["reproduction"].append({"run": r["dir"], "earlier": old[k]["dir"],
                                        "identical_metrics": old[k]["summary"]["metrics"] == r["summary"]["metrics"]})
    return res


def fmt(x, nd):
    return "–" if x is None else f"{x:.{nd}f}"


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    return "\n".join(out + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def tables(b: dict) -> dict[str, str]:
    out = {}
    for sc, title in SCENARIOS:
        arms = b["scenarios"][sc]
        mp = arms["MaxPressure"]["att"][0]
        rows = []
        for name, a in arms.items():
            rows.append([name, len(a["seeds"])] + [f"{fmt(a[m][0], nd)} ± {fmt(a[m][1], nd)}" for m, _, nd in METRICS]
                        + [f"{100 * (a['att'][0] - mp) / mp:+.1f}%"])
        out[f"results_{sc}"] = table(["Controller", "Seeds"] + [h for _, h, _ in METRICS] + ["ATT vs MaxPressure"], rows)
    rows = []
    for x in b["llm"].values():
        fails = ", ".join(f"{t} {n}" for t, n in x["failures_by_type"].items()) or "none"
        rows.append([x["scenario"], x["arm"], x["calls"], f"{100 * x['failure_rate']:.1f}% ({fails})",
                     f"{x['latency_mean_s']:.2f}", f"{x['latency_p95_s_range'][0]:.2f}–{x['latency_p95_s_range'][1]:.2f}",
                     f"{100 * x['mp_disagreement_rate']:.1f}%",
                     "– (no guard)" if x["guard_overrides"] is None else f"{100 * x['guard_override_rate']:.1f}%",
                     f"{100 * x['applied_differs_rate']:.1f}%", f"{x['wall_time_h']:.1f}"])
    out["results_llm"] = table(["Scenario", "Arm", "Calls", "Failures", "Latency mean (s)", "p95 per run (s)",
                                "LLM's answer differs from MaxPressure", "Guard replaced the answer",
                                "Applied phase differs from MaxPressure", "Wall time, all seeds (h)"], rows)
    rows = []
    for sc, arms in b["paired"].items():
        for name, a in arms.items():
            rows.append([sc, name, " / ".join(f"{x:+.2f}" for x in a["att_minus_mp"]),
                         f"{a['seeds_lower_att']} lower, {a['seeds_higher_att']} higher of {len(a['seeds'])}"])
    out["results_paired"] = table(["Scenario", "Controller", "ATT minus MaxPressure, per seed (s)",
                                   "Seeds with lower / higher ATT than MaxPressure"], rows)
    rep = b["reproduction"]
    out["results_reproduction"] = table(
        ["Baseline runs compared with an earlier identical run", "Identical metrics"],
        [[len(rep), f"{sum(r['identical_metrics'] for r in rep)} of {len(rep)}"]])
    em = emergency.tables(b["emergency"])
    out["results_emergency"] = em["emergency_full"]
    out["results_emergency_ambulances"] = em["emergency_full_ambulances"]
    return out


def render(doc: str, tabs: dict[str, str]) -> str:
    for name, body in tabs.items():
        begin, end = f"<!-- BEGIN:{name} -->", f"<!-- END:{name} -->"
        pat = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
        if not pat.search(doc):
            raise KeyError(f"Marker for table {name!r} missing in {DOC}")
        doc = pat.sub(lambda m: f"{begin}\n{body}\n{end}", doc)
    return doc


def comparable(b: dict) -> dict:
    """The parts of results.json --check compares: the data, not the commit it was generated at."""
    out = {k: b[k] for k in ("scenarios", "llm", "paired", "reproduction")}
    out["emergency"] = {k: v for k, v in b["emergency"].items() if k != "provenance"}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    b = report()
    b["emergency"] = emergency.report(ROOT)
    tabs = tables(b)
    em_doc = ROOT / emergency.DOC
    em_tabs = emergency.tables(b["emergency"])
    if args.check:
        stored = json.loads((ROOT / OUT).read_text())
        same = comparable(stored) == comparable(b)
        ok = (same and render((ROOT / DOC).read_text(), tabs) == (ROOT / DOC).read_text()
              and emergency.render(em_doc.read_text(), em_tabs) == em_doc.read_text())
        print("docs/results.md and docs/emergency.md match the full runs" if ok else
              "results out of date; run scripts/make_results.py")
        sys.exit(0 if ok else 1)
    (ROOT / OUT).write_text(json.dumps(b, indent=1))
    (ROOT / emergency.OUT).write_text(json.dumps(b["emergency"], indent=1))
    (ROOT / DOC).write_text(render((ROOT / DOC).read_text(), tabs))
    em_doc.write_text(emergency.render(em_doc.read_text(), em_tabs))
    print(f"Wrote {OUT}, {emergency.OUT}; updated {DOC} and {emergency.DOC}")


if __name__ == "__main__":
    main()
