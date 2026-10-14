"""Generate the tables in docs/baselines.md from the baseline result files.

    python scripts/make_baseline_tables.py          # update the doc
    python scripts/make_baseline_tables.py --check  # exit 1 if the doc is out of date

Inputs: outputs/baselines/maxpressure_sweep.json (scripts/tune_maxpressure.py),
outputs/baselines/runs/*/summary.json (scripts/run_baselines.py).
Each table sits between <!-- BEGIN:name --> and <!-- END:name --> markers in the doc.
Mean ± std is over seeds 0, 1, 2; std is the sample standard deviation (ddof = 1).
"""
import argparse
import json
import re
import statistics
import sys

from trafficsense.config import repo_root

ROOT = repo_root()
DOC = ROOT / "docs" / "baselines.md"
SWEEP = ROOT / "outputs" / "baselines" / "maxpressure_sweep.json"
RUNS = ROOT / "outputs" / "baselines" / "runs"
BASELINE_SCENARIOS = ["jinan_3x4", "hangzhou_4x4"]
CONTROLLERS = [("fixedtime", "FixedTime, 4 paired phases, 30 s"),
               ("fixedtime_webster", "FixedTime, Webster plan"),
               ("maxpressure", "MaxPressure, 15 s (tuned default)"),
               ("maxpressure_5s", "MaxPressure, 5 s")]
TRANSITION_S = 5
MIN_GREEN = 10


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def ms(e, nd):
    return f"{e['mean']:.{nd}f} ± {e['std']:.{nd}f}"


def shortest_green(interval):
    """First decision-grid point at least MIN_GREEN after the transition ends (tested in
    tests/test_baselines.py)."""
    k = 1
    while k * interval - TRANSITION_S < MIN_GREEN:
        k += 1
    return k * interval - TRANSITION_S


def sweep_table(sw, sc):
    rows = []
    rank = sw["selection"]["rank"][sc]
    for k, e in sw["results"][sc].items():
        rows.append([f"{k} s", f"{shortest_green(int(k))} s", ms(e["att"], 1), ms(e["throughput"], 0),
                     ms(e["waiting_to_enter"], 1), ms(e["queue_mean_per_intersection"], 2),
                     ms(e["transition_share"], 3), f"{rank[k]:g}"])
    return table(["Decision interval", "Shortest possible green", "ATT (s)", "Throughput",
                  "Waiting to enter at 3600 s", "Queue / int. (veh)", "Time in transition", "ATT rank"], rows)


def selection_table(sw):
    sel = sw["selection"]
    scs = sw["provenance"]["scenarios"]
    rows = []
    for k in map(str, sw["provenance"]["intervals"]):
        rows.append([f"{k} s"] + [f"{sel['rank'][sc][k]:g}" for sc in scs]
                    + [f"{sel['mean_rank'][k]:.2f}", f"{sel['mean_att_over_best'][k]:.3f}",
                       "**chosen**" if int(k) == sel["chosen_decision_interval"] else ""])
    return table(["Interval"] + [f"Rank: {sc}" for sc in scs] + ["Mean rank", "Mean ATT / best", ""], rows)


def transition_share(summary):
    """Measured: every switch shows the transition phase for its full duration."""
    sig, n_int = summary["signal"], len(summary["per_intersection"])
    (tr,) = sig["transition_s"]
    return sig["switches"] * tr / (summary["metrics"]["steps"] * n_int)


def load_runs():
    runs = {}
    for p in sorted(RUNS.glob("*/summary.json")):
        s = json.loads(p.read_text())
        pv = s["provenance"]
        key = (pv["scenario"], pv["controller"], pv["seed"])
        if key in runs:
            raise SystemExit(f"Two runs for {key}: {runs[key]['dir']} and {p.parent.name}; remove the stale one")
        if pv["git_dirty"]:
            raise SystemExit(f"{p}: run from a dirty git tree, not citable")
        runs[key] = {"dir": p.parent.name, "summary": s}
    return runs


def by_seed(runs, sc, ctl):
    rs = [v["summary"] for k, v in sorted(runs.items()) if k[0] == sc and k[1] == ctl]
    if len(rs) != 3:
        raise SystemExit(f"Expected 3 seeds for {sc} / {ctl}, found {len(rs)}; run scripts/run_baselines.py")
    return rs


def stat(xs, nd):
    return f"{statistics.mean(xs):.{nd}f} ± {statistics.stdev(xs):.{nd}f}"


def compare_table(runs, sc):
    rows = []
    for ctl, label in CONTROLLERS:
        rs = by_seed(runs, sc, ctl)
        m = [r["metrics"] for r in rs]
        rows.append([label, stat([x["att"] for x in m], 1), stat([x["throughput"] for x in m], 0),
                     stat([x["queue_mean_per_intersection"] for x in m], 2),
                     stat([x["waiting_time_mean"] for x in m], 1),
                     stat([transition_share(r) for r in rs], 3)])
    return table(["Controller", "ATT (s)", "Throughput", "Queue / int. (veh)", "Waiting time / vehicle (s)",
                  "Time in transition"], rows)


def rng(xs, nd):
    lo, hi = min(xs), max(xs)
    return f"{lo:.{nd}f}" if f"{lo:.{nd}f}" == f"{hi:.{nd}f}" else f"{lo:.{nd}f}–{hi:.{nd}f}"


def webster_rows(label, summaries):
    """One row per scenario (and seed set): ranges over intersections and seeds."""
    params = [r["provenance"]["controller_params"] for r in summaries]
    plans = [p for cp in params for p in cp["plans"].values()]
    inp = [cp["inputs"] for cp in params]
    c0 = [p["C0_s"] for p in plans if p["C0_s"] is not None]
    at_min = sum(1 for p in plans if p["cycle_webster_s"] == params[0]["cycle_min"])
    clipped_g = sum(len(p["greens_clipped"]) for p in plans)
    return [label,
            rng([i["saturation_flow_veh_per_hour"]["go_straight"] for i in inp], 0),
            rng([i["saturation_flow_veh_per_hour"]["turn_left"] for i in inp], 0),
            rng([i["startup_lost_time_s"] for i in inp], 2),
            rng([p["lost_time_L_s"] for p in plans], 1),
            rng([p["Y"] for p in plans], 2),
            rng(c0, 0) if c0 else "–",
            rng([p["cycle_run_s"] for p in plans], 0),
            f"{at_min} / {len(plans)}",
            f"{sum(1 for p in plans if p['oversaturated'])} / {len(plans)}",
            f"{clipped_g} / {4 * len(plans)}"]


WEBSTER_HEADER = ["Scenario", "s straight (veh/h)", "s protected turn (veh/h)", "Start-up lost time (s)",
                  "L (s)", "Y", "C0 (s)", "Cycle run (s)", "Plans at cycle_min", "Plans with Y ≥ 1",
                  "Greens clipped to min/max"]


def webster_table(runs):
    rows = [webster_rows(sc, by_seed(runs, sc, "fixedtime_webster")) for sc in BASELINE_SCENARIOS]
    return table(WEBSTER_HEADER, rows)


def build():
    sw = json.loads(SWEEP.read_text())
    tables = {f"mp_sweep_{sc}": sweep_table(sw, sc) for sc in sw["provenance"]["scenarios"]}
    tables["mp_selection"] = selection_table(sw)
    runs = load_runs()
    tables["webster_plans"] = webster_table(runs)
    for sc in BASELINE_SCENARIOS:
        tables[f"compare_{sc}"] = compare_table(runs, sc)
    return tables


def render(doc, tables):
    for name, body in tables.items():
        begin, end = f"<!-- BEGIN:{name} -->", f"<!-- END:{name} -->"
        pat = re.compile(re.escape(begin) + r".*?" + re.escape(end), re.S)
        if not pat.search(doc):
            raise KeyError(f"Marker for table {name!r} missing in {DOC}")
        doc = pat.sub(lambda m: f"{begin}\n{body}\n{end}", doc)
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    doc = DOC.read_text()
    new = render(doc, build())
    if args.check:
        ok = new == doc
        print("docs/baselines.md matches the results" if ok else
              "docs/baselines.md is out of date; run scripts/make_baseline_tables.py")
        sys.exit(0 if ok else 1)
    DOC.write_text(new)
    print(f"Updated {DOC}")


if __name__ == "__main__":
    main()
