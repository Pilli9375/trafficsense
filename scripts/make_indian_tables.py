"""Aggregate the Indian 2x2 runs and generate the tables in docs/indian_scenario.md.

    python scripts/make_indian_tables.py          # write outputs/indian_2x2/results.json, update the doc
    python scripts/make_indian_tables.py --check  # exit 1 if the doc or results.json is out of date

Inputs: outputs/indian_2x2/runs/*/summary.json (scripts/run_indian_experiments.py),
outputs/validation/indian_demand_calibration.json (scripts/calibrate_indian_demand.py) and the
earlier 5 s MaxPressure calibration (indian_demand_calibration_maxpressure_5s.json),
the flow files and their .meta.json, and configs/scenarios/indian_2x2.yaml.
Each table sits between <!-- BEGIN:name --> and <!-- END:name --> markers in the doc.
Mean ± std is over seeds; std is the sample standard deviation (ddof = 1).
"""
import argparse
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path

from trafficsense.config import load_config, repo_root
from trafficsense.sim.capacity import critical_flow_ratio, lane_demand
from trafficsense.sim.demand import Network
from trafficsense.sim.roadnet import load_roadnet

ROOT = repo_root()
DOC = ROOT / "docs" / "indian_scenario.md"
RUNS = ROOT / "outputs" / "indian_2x2" / "runs"
RESULTS = ROOT / "outputs" / "indian_2x2" / "results.json"
CALIB = ROOT / "outputs" / "validation" / "indian_demand_calibration.json"
SC_CFG = "configs/scenarios/indian_2x2.yaml"

CONTROLLERS = [("fixedtime", "FixedTime, 4 paired phases, 30 s"),
               ("fixedtime_all_phases", "FixedTime, all 8 phases, 30 s"),
               ("fixedtime_webster", "FixedTime, 4 paired phases, Webster plan"),
               ("maxpressure", "MaxPressure (8 phases, {decision_interval} s, min {min_green} / max 60)"),
               ("maxpressure_15s", "MaxPressure (8 phases, {decision_interval} s, min {min_green} / max 60)"),
               ("maxpressure_5s", "MaxPressure (8 phases, {decision_interval} s, min {min_green} / max 60)")]
CALIB_5S = ROOT / "outputs" / "validation" / "indian_demand_calibration_maxpressure_5s.json"
LEVELS = ["offpeak", "peak"]
METRICS = [("att", "ATT (s)", 1), ("queue_mean_per_intersection", "Queue / intersection (veh)", 2),
           ("waiting_time_mean", "Waiting time / vehicle (s)", 1), ("throughput", "Throughput (finished trips)", 0),
           ("vehicles_waiting_to_enter_at_end", "Still waiting to enter at 3600 s", 1),
           ("transition_share", "Time in transition phase", 3)]


def metric(summary, m):
    if m == "transition_share":
        # measured: every switch shows the transition phase for its full duration
        sig, n_int = summary["signal"], len(summary["per_intersection"])
        (tr,) = sig["transition_s"]
        return sig["switches"] * tr / (summary["metrics"]["steps"] * n_int)
    return summary["metrics"][m]


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def mean_std(xs, nd):
    m = statistics.mean(xs)
    s = statistics.stdev(xs) if len(xs) > 1 else 0.0
    return f"{m:.{nd}f} ± {s:.{nd}f}"


def load_runs(sc):
    runs = {}
    for p in sorted(RUNS.glob("*/summary.json")):
        s = json.loads(p.read_text())
        pv = s["provenance"]
        key = (pv["scenario"], pv["controller"], pv["seed"])
        if key in runs:
            raise SystemExit(f"Two runs for {key}: {runs[key]['dir']} and {p.parent.name}; remove the stale one")
        flow = ROOT / pv["flow"]
        if hashlib.sha256(flow.read_bytes()).hexdigest() != pv["flow_sha256"]:
            raise SystemExit(f"{p}: flow file {flow} changed since the run")
        if pv["git_dirty"]:
            raise SystemExit(f"{p}: run from a dirty git tree, not citable")
        runs[key] = {"dir": p.parent.name, "summary": s}
    return runs


def label_of(ctl, summary):
    """Label with the settings recorded in the run, so it cannot go stale."""
    return dict(CONTROLLERS)[ctl].format(**controller_settings(summary))


def controller_settings(summary):
    """controller_params, plus min_green from the env's recorded signal settings for runs made
    before MaxPressure had its own min_green (it was then always the env's)."""
    cp = dict(summary["provenance"]["controller_params"])
    cp.setdefault("min_green", summary["signal"]["min_green"])
    return cp


def aggregate(runs):
    res = {}
    for level in LEVELS:
        sc_name = f"indian_2x2_{level}"
        for ctl, _ in CONTROLLERS:
            rs = sorted(((k[2], v) for k, v in runs.items() if k[0] == sc_name and k[1] == ctl))
            if not rs:
                raise SystemExit(f"No runs for {sc_name} / {ctl}; run scripts/run_indian_experiments.py")
            params = {json.dumps([controller_settings(v["summary"]).get(k) for k in ("decision_interval", "min_green")])
                      for _, v in rs}
            if len(params) != 1:
                raise SystemExit(f"{sc_name} / {ctl}: runs with different settings {params}")
            entry = {"seeds": [s for s, _ in rs], "runs": [v["dir"] for _, v in rs],
                     "label": label_of(ctl, rs[0][1]["summary"]),
                     "git_commits": sorted({v["summary"]["provenance"]["git_commit"] for _, v in rs})}
            for m, _, _ in METRICS:
                xs = [metric(v["summary"], m) for _, v in rs]
                entry[m] = {"values": xs, "mean": statistics.mean(xs),
                            "std": statistics.stdev(xs) if len(xs) > 1 else 0.0}
            res.setdefault(level, {})[ctl] = entry
    return res


def results_table(res, level):
    rows = []
    for ctl, _ in CONTROLLERS:
        e = res[level][ctl]
        rows.append([e["label"]] + [mean_std(e[m]["values"], nd) for m, _, nd in METRICS])
    return table(["Controller"] + [h for _, h, _ in METRICS], rows)


def per_seed_table(res):
    rows = []
    for level in LEVELS:
        for ctl, _ in CONTROLLERS:
            e = res[level][ctl]
            for i, seed in enumerate(e["seeds"]):
                rows.append([level, e["label"], seed, f"{e['att']['values'][i]:.1f}",
                             f"{e['queue_mean_per_intersection']['values'][i]:.2f}",
                             f"{e['waiting_time_mean']['values'][i]:.1f}", e["throughput"]["values"][i],
                             e["vehicles_waiting_to_enter_at_end"]["values"][i], e["runs"][i]])
    return table(["Level", "Controller", "Seed", "ATT (s)", "Queue / int.", "Waiting (s)", "Throughput",
                  "Waiting to enter", "Run folder"], rows)


def capacity_table(cal):
    c = cal["capacity"]
    st, lt = c["saturation_flow"]["go_straight"], c["saturation_flow"]["turn_left"]
    a = c["entry_admission"]
    return table(["Quantity (mixed traffic, measured)", "Value", "How"], [
        ["Saturation flow, straight lane", f"{st['fit_saturation_flow_veh_per_hour']:.0f} veh/h",
         f"queue discharge after 900 s red; slope of a line fitted to cumulative departures in green "
         f"s 10–70; mean of {st['reps']} random-order queues"],
        ["Saturation flow, protected-turn lane (Indian right turn)", f"{lt['fit_saturation_flow_veh_per_hour']:.0f} veh/h",
         "same"],
        ["Start-up lost time (mean of both lanes)", f"{c['startup_lost_time_s']:.2f} s",
         "same fit: time at which the line crosses zero departures"],
        ["Entry admission limit (CityFlow insertion)", f"{a['measured_veh_per_hour']:.0f} veh/h",
         f"permanent green, fed {c['feed_veh_per_s']:.0f} veh/s, minutes 20–60"],
    ])


def sweep_table(cal):
    by_rate = {}
    for r in cal["sweep"]:
        by_rate.setdefault(r["veh_per_hour"], []).append(r)
    rows = []
    for rate in sorted(by_rate):
        rs = by_rate[rate]
        mp = [r["maxpressure"] for r in rs]
        drains = [m["drain_s_after_arrivals_stop"] for m in mp]
        rows.append([f"{rate:.0f}",
                     f"{statistics.mean(r['busiest_lane']['demand_over_saturation_flow'] for r in rs):.2f}",
                     f"{statistics.mean(r['Y_max_ANALYTIC'] for r in rs):.2f}",
                     f"{statistics.mean(m['finished_share'] for m in mp):.3f}",
                     f"{max(m['backlog_share'] for m in mp):.3f}",
                     f"{statistics.mean(m['queue_mean_per_intersection'] for m in mp):.1f}",
                     f"{statistics.mean(m['att'] for m in mp):.0f}",
                     " / ".join("–" if d is None else str(d) for d in drains),
                     "yes" if all(m["drains"] for m in mp) else "**no**"])
    return table(["Demand (veh/h)", "Busiest lane demand / s", "Y max (ANALYTIC)", "Finished by 3600 s",
                  "Backlog at 3600 s (worst seed)", "Queue / int.", "ATT (s)",
                  "Time to empty after arrivals stop (s, seeds 0/1/2)", "Drains (all seeds)"], rows)


def selection_table(cal, sc):
    sel = cal["selection"]
    rule = sel["rule"]
    lv = sc["demand_levels"]
    return table(["Item", "Value"], [
        ["Drains = backlog at 3600 s ≤", f"{100 * rule['backlog_max_share']:.0f}% of generated, and empty within "
                                        f"{rule['drain_max_s']} s after arrivals stop (every seed)"],
        ["R* (lowest swept demand that does not drain)", f"{sel['R_star']:.0f} veh/h"],
        ["Peak = largest swept demand ≤ 0.9 R* that drains", f"{sel['peak_veh_per_hour']:.0f} veh/h"],
        ["Off-peak = 0.5 × peak (ASSUMPTION)", f"{sel['offpeak_veh_per_hour']:.0f} veh/h"],
        ["In configs/scenarios/indian_2x2.yaml", f"offpeak {lv['offpeak']['veh_per_hour']}, peak {lv['peak']['veh_per_hour']}"],
    ])


def calibration_compare_table(cal, cal5):
    def by_rate(c):
        out = {}
        for r in c["sweep"]:
            out.setdefault(r["veh_per_hour"], []).append(r["maxpressure"])
        return out
    a, b = by_rate(cal5), by_rate(cal)
    if sorted(a) != sorted(b):
        raise SystemExit("The 5 s and 15 s calibrations swept different demands")
    lab = {k: f"{c['provenance']['controller_params']['decision_interval']} s"
           for k, c in (("a", cal5), ("b", cal))}
    rows = []
    for R in sorted(b):
        cells = [f"{R:.0f}"]
        for mp in (a[R], b[R]):
            cells += [f"{statistics.mean(m['att'] for m in mp):.0f}", f"{max(m['backlog_share'] for m in mp):.3f}",
                      "yes" if all(m["drains"] for m in mp) else "**no**"]
        rows.append(cells)
    hdr = ["Demand (veh/h)"]
    for k in ("a", "b"):
        hdr += [f"{lab[k]}: ATT (s)", f"{lab[k]}: backlog (worst seed)", f"{lab[k]}: drains"]
    sel = [c["selection"] for c in (cal5, cal)]
    rows.append(["**Selected**"] + sum(([f"R* {x['R_star']:.0f}", f"peak {x['peak_veh_per_hour']:.0f}",
                                         f"off-peak {x['offpeak_veh_per_hour']:.0f}"] for x in sel), []))
    return table(hdr, rows)


def webster_reference_table(cal):
    w = cal["selection"]["webster_reference_ANALYTIC"]
    rows = [["Lost time per cycle L = 4 × (5 s transition + start-up lost time)", f"{w['lost_time_L_s']:.1f} s"],
            [f"Webster capacity limit Y_cap = (C − L) / C at the longest allowed cycle C = {w['cycle_max_s']:.0f} s",
             f"{w['Y_cap']:.3f}"],
            ["Demand at which Y max reaches Y_cap (interpolated over the sweep)",
             "not reached in the sweep" if w["R_at_Y_cap_veh_per_hour"] is None
             else f"{w['R_at_Y_cap_veh_per_hour']:.0f} veh/h"]]
    for key, name in (("R_star", "R* (MaxPressure breakdown)"), ("peak_veh_per_hour", "Peak"),
                      ("offpeak_veh_per_hour", "Off-peak")):
        x = w[key]
        note = "" if x["Y_from_swept_rate"] == x["veh_per_hour"] else f", scaled from {x['Y_from_swept_rate']:.0f} veh/h"
        rows.append([f"{name}, {x['veh_per_hour']:.0f} veh/h: Y max (mean over seeds{note}) and Y max / Y_cap",
                     f"{x['Y_max']:.2f} and {x['Y_max_over_Y_cap']:.2f}"])
    return table(["Item (ANALYTIC)", "Value"], rows)


def level_demand_table(cal, sc, net):
    s = {t: cal["capacity"]["saturation_flow"][t]["fit_saturation_flow_veh_per_hour"] for t in ("go_straight", "turn_left")}
    admit = cal["capacity"]["entry_admission"]["measured_veh_per_hour"]
    entry = set(Network(net).entry_roads)
    rows = []
    for level in LEVELS:
        for seed in (0, 1, 2):
            fp = ROOT / sc["output_dir"] / f"flow_{level}_s{seed}.json"
            flows = json.loads(fp.read_text())
            per_h = 3600.0 / sc["duration_s"]
            lanes = lane_demand(net, flows)
            ratio, best, best_entry, right = {}, (0, None), (0, None), (0, None)
            for iid, ls in lanes.items():
                ratio[iid] = {}
                for lane, d in ls.items():
                    vph = d["vehicles"] * per_h
                    if d["turn"] == "turn_right":
                        ratio[iid][lane] = 0.0
                        right = max(right, (vph, lane))
                        continue
                    ratio[iid][lane] = vph / s[d["turn"]]
                    best = max(best, (ratio[iid][lane], f"{lane} ({d['movement']}, {vph:.0f} veh/h)"))
                    if lane.rsplit("_", 1)[0] in entry:
                        best_entry = max(best_entry, (vph, lane))
            y = max(v["Y"] for v in critical_flow_ratio(net, ratio).values())
            rows.append([level, seed, len(flows), best[1], f"{best[0]:.2f}", f"{y:.2f}",
                         f"{best_entry[0] / admit:.2f}", f"{right[0]:.0f}"])
    return table(["Level", "Seed", "Vehicles", "Busiest non-right lane", "Its demand / saturation flow",
                  "Y max (ANALYTIC)", "Busiest entry lane / admission limit",
                  "Busiest free-turn lane (veh/h)"], rows)


def mix_table(sc):
    types = sc["vehicle_types"]
    tot = sum(t["share"] for t in types.values())
    counts = {}
    for level in LEVELS:
        for seed in (0, 1, 2):
            meta = json.loads((ROOT / sc["output_dir"] / f"flow_{level}_s{seed}.meta.json").read_text())
            for k, v in meta["vehicles_by_type"].items():
                counts.setdefault(k, 0)
                counts[k] += v
    n = sum(counts.values())
    rows = []
    for k, t in types.items():
        rows.append([k, f"{100 * t['share'] / tot:.1f}%", f"{100 * counts.get(k, 0) / n:.1f}%",
                     t["length"], t["width"], t["minGap"], t["headwayTime"], t["maxSpeed"],
                     f"{t['usualPosAcc']} / {t['maxPosAcc']}", f"{t['usualNegAcc']} / {t['maxNegAcc']}"])
    return table(["Type", "Share (config, normalised)", "Share (all 6 flow files)", "Length (m)", "Width (m)",
                  "minGap (m)", "headwayTime (s)", "maxSpeed (m/s)", "Acc usual / max (m/s²)",
                  "Dec usual / max (m/s²)"], rows)


def breakdown_table():
    d = json.loads((ROOT / "outputs" / "validation" / "indian_breakdown_5500_s2.json").read_text())
    rows = []
    for s in d["snapshots"]:
        full = ", ".join(f"{x['lane']} ({x['vehicles']}/{x['storage']:.0f}{', entry' if x['entry_road'] else ''})"
                         for x in s["lanes_at_storage"]) or "none"
        rows.append([s["t"], s["running"], s["waiting_to_enter"], full])
    tr = d["transition_phase"]
    share = ", ".join(f"{i} {100 * v[str(tr[i])]:.0f}%" for i, v in d["phase_time_share"].items())
    hops = ", ".join(f"{k} ({v})" for k, v in list(d["backlog_by_first_hop"].items())[:3])
    return (table(["t (s)", "Vehicles running", "Waiting to enter", "Incoming lanes at storage (vehicles / storage)"], rows)
            + f"\n\nTime in the transition phase: {share}. Largest backlogs at 3600 s by first route hop: {hops}.")


def build():
    sc = load_config(SC_CFG)
    net = load_roadnet(ROOT / sc["roadnet"]["file"])
    cal = json.loads(CALIB.read_text())
    runs = load_runs(sc)
    res = aggregate(runs)
    tables = {
        "mix": mix_table(sc),
        "capacity": capacity_table(cal),
        "sweep": sweep_table(cal),
        "selection": selection_table(cal, sc),
        "calibration_compare": calibration_compare_table(cal, json.loads(CALIB_5S.read_text())),
        "webster_reference": webster_reference_table(cal),
        "breakdown": breakdown_table(),
        "level_demand": level_demand_table(cal, sc, net),
        "results_offpeak": results_table(res, "offpeak"),
        "results_peak": results_table(res, "peak"),
        "per_seed": per_seed_table(res),
    }
    return tables, res


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
    tables, res = build()
    doc = DOC.read_text()
    new = render(doc, tables)
    res_text = json.dumps(res, indent=1)
    if args.check:
        ok = new == doc and RESULTS.is_file() and RESULTS.read_text() == res_text
        print("docs/indian_scenario.md and results.json match the runs" if ok else
              "docs/indian_scenario.md or outputs/indian_2x2/results.json is out of date; run scripts/make_indian_tables.py")
        sys.exit(0 if ok else 1)
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(res_text)
    DOC.write_text(new)
    print(f"Updated {DOC} and {RESULTS}")


if __name__ == "__main__":
    main()
