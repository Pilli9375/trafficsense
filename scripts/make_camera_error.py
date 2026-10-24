"""Generate the camera-error results (docs/camera_error.md tables + chart) from the runs.

    python scripts/make_camera_error.py            # write outputs/camera_error/results.json, docs, chart
    python scripts/make_camera_error.py --check    # exit 1 if any of them is out of date

Inputs: the complete runs of scripts/run_camera_error.py (outputs/camera_error/runs/); every
planned run must be present. Mean ± std over seeds (sample std). "vs perfect" is paired by
seed: each noisy run minus the perfect run of the same scenario, controller and seed. The
"effective p_detect" of a level is the realised detection rate pooled over all vehicles and
snapshots of its MaxPressure runs in that scenario (from summary.json `observation`).
Ambulance numbers: signal-relevant ambulances (route crosses at least one signal-controlled
movement), paired by (seed, vehicle) against the perfect run.
"""
import argparse
import importlib.util
import json
import math
import re
import statistics
import sys
from pathlib import Path

from trafficsense.config import repo_root
from trafficsense.experiment import git_info
from trafficsense.sim.emergency import signal_relevant
from trafficsense.sim.observation import SIM_TO_DETECTOR
from trafficsense.sim.roadnet import load_roadnet

ROOT = repo_root()
DOC = Path("docs/camera_error.md")
OUT = Path("outputs/camera_error/results.json")
CHART = Path("docs/figures/camera_error.svg")
FULL_RUNS = [Path("outputs/full/runs"), Path("outputs/emergency/runs")]
LEVELS = ["perfect", "junction", "crowded"]
SWEEP = ["uniform_p1.00", "uniform_p0.90", "uniform_p0.80", "uniform_p0.70", "uniform_p0.60", "uniform_p0.50"]
SCEN = {"indian_2x2_offpeak": "Off-peak", "indian_2x2_peak": "Peak"}
EMERGENCY = "indian_2x2_peak_amb"
LABEL = {"maxpressure": "MaxPressure", "fixedtime_webster": "Webster fixed-time",
         "llm_guarded_mp": "LLM arm (guarded llama3.2:3b)", "preemption_mp": "MaxPressure + preemption"}
SHORT = {"maxpressure": "MaxPressure", "fixedtime_webster": "Webster", "llm_guarded_mp": "LLM arm",
         "preemption_mp": "MP + preemption"}


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan = load("run_camera_error")


def mean_std(xs):
    return [statistics.mean(xs), statistics.stdev(xs) if len(xs) > 1 else 0.0]


def load_runs(root: Path) -> dict[tuple, dict]:
    """(scenario, controller, seed, obs key) -> summary (+ dir); all planned runs must be there."""
    done = plan.complete_runs(root)
    runs = {}
    for k, d in done.items():
        s = json.loads((d / "summary.json").read_text())
        s["dir"] = str(d.relative_to(root))
        runs[(k[0], k[1], k[2], k[4])] = s
    missing = [plan.job_key(j) for j in plan.jobs() if (j["scenario"], j["controller"], j["seed"],
                                                       plan.job_key(j)[4]) not in runs]
    if missing:
        raise SystemExit(f"{len(missing)} planned runs missing, e.g. {missing[:3]}")
    return runs


def paired(runs, sc, ctl, seeds, key, metric="att"):
    d = [runs[(sc, ctl, s, key)]["metrics"][metric] - runs[(sc, ctl, s, "perfect")]["metrics"][metric] for s in seeds]
    rel = [100 * x / runs[(sc, ctl, s, "perfect")]["metrics"][metric] for x, s in zip(d, seeds)]
    return {"mean": statistics.mean(d), "min": min(d), "max": max(d), "per_seed": d,
            "pct_mean": statistics.mean(rel), "pct_min": min(rel), "pct_max": max(rel)}


def level_stats(runs, sc, ctl, seeds, key):
    rs = [runs[(sc, ctl, s, key)] for s in seeds]
    out = {"runs": [r["dir"] for r in rs],
           "att": mean_std([r["metrics"]["att"] for r in rs]),
           "queue_mean_per_intersection": mean_std([r["metrics"]["queue_mean_per_intersection"] for r in rs]),
           "waiting_time_mean": mean_std([r["metrics"]["waiting_time_mean"] for r in rs]),
           "throughput": mean_std([r["metrics"]["throughput"] for r in rs])}
    if key != "perfect":
        out["att_vs_perfect"] = paired(runs, sc, ctl, seeds, key)
    llm = rs[0]["provenance"]["llm"]
    if llm:
        ls = [r["provenance"]["llm"] for r in rs]
        ok = sum(l["ok"] for l in ls)
        out["llm"] = {"calls": sum(l["calls"] for l in ls), "failures": sum(l["calls"] - l["ok"] for l in ls),
                      "guard_overrides": sum(l["guard_overrides"] for l in ls),
                      "guard_override_rate": sum(l["guard_overrides"] for l in ls) / ok if ok else None,
                      "mp_disagreement_rate": sum(l["mp_disagreements"] for l in ls) / ok if ok else None,
                      "latency_mean_s": sum(l["latency_mean_s"] * l["latency_n"] for l in ls)
                      / sum(l["latency_n"] for l in ls)}
    return out


def effective_p(runs, sc, seeds, key):
    """Realised detection rate pooled over the MaxPressure runs of a level (all vehicles, snapshots)."""
    true = det = 0
    for s in seeds:
        r = runs[(sc, "maxpressure", s, key)]["observation"]["realized"]
        for c, n in r["true_vehicle_observations"].items():
            true += n
            det += round(r["detection_rate"][c] * n)
    return det / true


def realised_vs_target(runs) -> dict:
    """Per noisy level and class: target p_detect and realised rate pooled over all runs of that level."""
    out = {}
    for (sc, ctl, seed, key), s in runs.items():
        o = s["observation"]
        if not o["noised"] or not o["snapshots"]:
            continue
        e = out.setdefault(key, {"target": {}, "true": {}, "detected": {}})
        for c in SIM_TO_DETECTOR.values():
            e["target"][c] = o["params"]["p_detect"][c]
            n = o["realized"]["true_vehicle_observations"].get(c, 0)
            e["true"][c] = e["true"].get(c, 0) + n
            e["detected"][c] = e["detected"].get(c, 0) + round(o["realized"]["detection_rate"].get(c, 0) * n)
    for key, e in out.items():
        e["realised"] = {c: e["detected"][c] / e["true"][c] for c in e["true"] if e["true"][c]}
        e["max_abs_diff"] = max(abs(e["realised"][c] - e["target"][c]) for c in e["realised"])
        # Post-hoc (not pre-registered): the difference in binomial standard errors. Every vehicle
        # observation is an independent Bernoulli(p_detect) draw, so realised - target ~ N(0, p(1-p)/n).
        e["z"] = {c: (e["realised"][c] - e["target"][c]) / math.sqrt(e["target"][c] * (1 - e["target"][c]) / e["true"][c])
                  for c in e["realised"] if 0 < e["target"][c] < 1}
    return out


def checks(runs) -> dict:
    seeds = [0, 1, 2]
    same_p1 = all(runs[(sc, "maxpressure", s, "uniform_p1.00")]["metrics"] == runs[(sc, "maxpressure", s, "perfect")]["metrics"]
                  for sc in SCEN for s in seeds)
    web = [(sc, s) for sc in SCEN for s in seeds] + [(EMERGENCY, s) for s in range(5)]
    web_levels = {sc: LEVELS if sc in SCEN else LEVELS[:2] for sc in list(SCEN) + [EMERGENCY]}
    web_same = all(runs[(sc, "fixedtime_webster", s, k)]["metrics"] == runs[(sc, "fixedtime_webster", s, "perfect")]["metrics"]
                   for sc, s in web for k in web_levels[sc])
    web_snaps = max(runs[(sc, "fixedtime_webster", s, k)]["observation"].get("snapshots", 0)
                    for sc, s in web for k in web_levels[sc])
    # (c) deterministic perfect runs vs the full experiments (same scenario, controller, seed)
    full = {}
    for root in FULL_RUNS:
        for d in sorted((ROOT / root).glob("*/summary.json")):
            s = json.loads(d.read_text())
            pv = s["provenance"]
            if pv["model"] is None and not pv["git_dirty"] and pv["sim_steps"] == plan.STEPS:
                full[(pv["scenario"], pv["controller"], pv["seed"])] = s["metrics"]
    compared, mism = 0, []
    for (sc, ctl, s, k), r in runs.items():
        if k == "perfect" and r["provenance"]["model"] is None and (sc, ctl, s) in full:
            compared += 1
            if r["metrics"] != full[(sc, ctl, s)]:
                mism.append([sc, ctl, s])
    rv = realised_vs_target(runs)
    worst = max(((k, c) for k, v in rv.items() for c in v["z"]),
                key=lambda kc: abs(rv[kc[0]]["realised"][kc[1]] - rv[kc[0]]["target"][kc[1]]))
    zs = [abs(z) for v in rv.values() for z in v["z"].values()]
    return {"realised_largest_miss": {"level": worst[0], "class": worst[1], "n": rv[worst[0]]["true"][worst[1]],
                                      "target": rv[worst[0]]["target"][worst[1]],
                                      "realised": rv[worst[0]]["realised"][worst[1]],
                                      "z": rv[worst[0]]["z"][worst[1]]},
            "realised_max_abs_z": max(zs) if zs else None, "realised_n_z": len(zs),
            "realised_n_abs_z_over_2": sum(z > 2 for z in zs),
            "uniform_p1_identical_to_perfect": same_p1, "webster_identical_across_levels": web_same,
            "webster_max_snapshots": web_snaps, "perfect_vs_full_experiments": {"compared": compared, "mismatches": mism},
            "realised_detection_max_abs_diff": {k: round(v["max_abs_diff"], 4) for k, v in rv.items()},
            "realised_within_0_01": all(v["max_abs_diff"] <= 0.01 for v in rv.values())}


def ambulances(runs, ctl, key, net):
    out = {}
    for s in range(5):
        for a in runs[(EMERGENCY, ctl, s, key)]["emergency"]["vehicles"]:
            if signal_relevant(net, a["route"]):
                out[(s, a["vehicle"])] = a
    return out


def report(root: Path = ROOT) -> dict:
    runs = load_runs(root)
    net = load_roadnet(ROOT / "data/scenarios/indian_2x2/roadnet.json")
    seeds = [0, 1, 2]
    b = {"main": {}, "sweep": {}, "emergency": {}, "effective_p_detect": {}}
    for sc in SCEN:
        b["main"][sc] = {c: {k: level_stats(runs, sc, c, seeds, k) for k in LEVELS}
                         for c in ("maxpressure", "fixedtime_webster", "llm_guarded_mp")}
        b["sweep"][sc] = {k: level_stats(runs, sc, "maxpressure", seeds, k) for k in SWEEP}
        b["effective_p_detect"][sc] = {k: effective_p(runs, sc, seeds, k) for k in ("junction", "crowded")}
    for c in ("maxpressure", "fixedtime_webster", "preemption_mp", "llm_guarded_mp"):
        b["emergency"][c] = {}
        for k in LEVELS[:2]:
            st = level_stats(runs, EMERGENCY, c, list(range(5)), k)
            amb = ambulances(runs, c, k, net)
            done = [a for a in amb.values() if a["finished"] is not None]
            st["ambulances_relevant"] = {"n": len(amb), "finished": len(done),
                                         "travel_time_mean_s": statistics.mean(a["travel_time_s"] for a in done)
                                         if done else None}
            if k != "perfect":
                ref = ambulances(runs, c, "perfect", net)
                diffs = [amb[x]["travel_time_s"] - ref[x]["travel_time_s"] for x in amb
                         if x in ref and amb[x]["finished"] is not None and ref[x]["finished"] is not None]
                st["ambulances_vs_perfect"] = {"n_paired": len(diffs), "mean_diff_s": statistics.mean(diffs),
                                               "slower": sum(d > 0 for d in diffs), "faster": sum(d < 0 for d in diffs)}
            b["emergency"][c][k] = st
    params = {}
    for key in ("junction", "crowded"):
        o = runs[("indian_2x2_peak", "maxpressure", 0, key)]["observation"]["params"]
        params[key] = {"p_detect": {c: o["p_detect"][c] for c in SIM_TO_DETECTOR.values()},
                       "false_det_per_road_snapshot": o["false_det_per_road_snapshot"], "source": o["source"]}
    b["params"] = params
    b["realised"] = realised_vs_target(runs)
    b["checks"] = checks(runs)
    b["provenance"] = {"script": "scripts/make_camera_error.py", "runs": len(runs),
                       "git_commit_of_this_summary": git_info()["commit"]}
    return b


# ---- tables -------------------------------------------------------------------------------
def pm(ms, nd=1):
    return f"{ms[0]:.{nd}f} ± {ms[1]:.{nd}f}"


def delta(p, nd=1):
    return f"{p['mean']:+.{nd}f} ({p['min']:+.{nd}f} to {p['max']:+.{nd}f}); {p['pct_mean']:+.1f}%"


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" if i == 0 else "---:" for i in range(len(header))) + "|"]
    return "\n".join(out + ["| " + " | ".join(str(x) for x in r) + " |" for r in rows])


def tables(b: dict) -> dict[str, str]:
    t = {}
    p = b["params"]
    t["camera_params"] = table(
        ["detector class", "junction p_detect", "crowded p_detect", "false det. per road and snapshot"],
        [[c, f"{p['junction']['p_detect'][c]:.3f}", f"{p['crowded']['p_detect'][c]:.3f}",
          f"{p['junction']['false_det_per_road_snapshot'][c]:.3f}"] for c in SIM_TO_DETECTOR.values()]
        + [["bicycle (label only)", "–", "–", f"{p['junction']['false_det_per_road_snapshot']['bicycle']:.3f}"]]) + (
        f"\n\nSource: `{p['junction']['source']['file']}` (sha256 `{p['junction']['source']['sha256'][:16]}…`, "
        f"conf ≥ {p['junction']['source']['conf_threshold']}).")
    for sc, name in SCEN.items():
        rows = []
        for c, lv in b["main"][sc].items():
            for k in LEVELS:
                e = lv[k]
                rows.append([LABEL[c] if k == "perfect" else "", k, pm(e["att"]),
                             "–" if k == "perfect" else delta(e["att_vs_perfect"]),
                             pm(e["queue_mean_per_intersection"], 2), pm(e["waiting_time_mean"]), pm(e["throughput"], 0)])
        t[f"camera_main_{sc}"] = table(["controller", "level", "ATT (s)", "ATT vs perfect, paired (s; range; %)",
                                        "queue / int. (veh)", "waiting / veh (s)", "finished trips"], rows)
    eff = b["effective_p_detect"]
    rows = []
    for k in SWEEP:
        rows.append([k.replace("uniform_p", "")] + [f"{pm(b['sweep'][sc][k]['att'])}"
                                                   + ("" if k == "uniform_p1.00" else
                                                      f" ({b['sweep'][sc][k]['att_vs_perfect']['pct_mean']:+.1f}%)")
                                                   for sc in SCEN])
    t["camera_sweep"] = table(["p_detect (all classes, no false detections)"] + [f"{n}: MaxPressure ATT (s)" for n in SCEN.values()],
                              rows) + "\n\nEffective p_detect of the camera levels (realised, MaxPressure runs): " + "; ".join(
        f"{n} junction {eff[sc]['junction']:.3f}, crowded {eff[sc]['crowded']:.3f}" for sc, n in SCEN.items()) + "."
    rows = []
    for c, lv in b["emergency"].items():
        for k in LEVELS[:2]:
            e = lv[k]
            a = e["ambulances_relevant"]
            v = e.get("ambulances_vs_perfect")
            rows.append([LABEL[c] if k == "perfect" else "", k, pm(e["att"]),
                         "–" if k == "perfect" else delta(e["att_vs_perfect"]),
                         f"{a['finished']} / {a['n']}", f"{a['travel_time_mean_s']:.1f}",
                         "–" if v is None else f"{v['mean_diff_s']:+.1f} (n {v['n_paired']}; {v['slower']} slower, {v['faster']} faster)"])
    t["camera_emergency"] = table(["controller", "level", "ATT (s)", "ATT vs perfect, paired (s; range; %)",
                                   "ambulances finished", "ambulance travel time (s)", "ambulance vs perfect, paired (s)"], rows)
    rows = []
    for sc, name in list(SCEN.items()) + [(EMERGENCY, "Emergency")]:
        src = b["main"][sc]["llm_guarded_mp"] if sc in SCEN else b["emergency"]["llm_guarded_mp"]
        for k, e in src.items():
            l = e["llm"]
            rows.append([name if k == "perfect" else "", k, l["calls"], l["failures"], f"{100 * l['guard_override_rate']:.1f}%",
                         f"{100 * l['mp_disagreement_rate']:.1f}%", f"{l['latency_mean_s']:.2f}"])
    t["camera_llm"] = table(["scenario", "level", "LLM calls", "failures", "guard overrides", "disagrees with MP",
                             "mean latency (s)"], rows)
    ch = b["checks"]
    pf = ch["perfect_vs_full_experiments"]
    rv = b["realised"]
    lm = ch["realised_largest_miss"]
    t["camera_checks"] = table(["check", "result"], [
        ["(a) MaxPressure at uniform p 1.00 identical to perfect (6 runs)", "yes" if ch["uniform_p1_identical_to_perfect"] else "**NO**"],
        ["(b) Webster identical at every level", ("yes" if ch["webster_identical_across_levels"] else "**NO**")
         + f"; at most {ch['webster_max_snapshots']} snapshots drawn"],
        ["(c) deterministic perfect runs reproduce the full experiments", f"{pf['compared'] - len(pf['mismatches'])} of "
         f"{pf['compared']} identical" + (f"; mismatches {pf['mismatches']}" if pf["mismatches"] else "")],
        ["(d) realised detection rate within ±0.01 of target", ("yes" if ch["realised_within_0_01"] else "**NO**") + "; largest abs. diff "
         + ", ".join(f"{k} {v:.4f}" for k, v in ch["realised_detection_max_abs_diff"].items())],
        ["(d') post-hoc: (d) in binomial standard errors", f"largest miss {lm['level']} {lm['class']}: "
         f"{lm['realised']:.4f} vs {lm['target']:.3f}, n {lm['n']:,}, {lm['z']:+.2f} SE; "
         f"largest abs(z) over all {ch['realised_n_z']} level-class pairs {ch['realised_max_abs_z']:.2f}, "
         f"{ch['realised_n_abs_z_over_2']} with abs(z) > 2"],
    ]) + "\n\n" + table(["level", "class", "target p_detect", "realised", "vehicle observations", "diff in binomial SE"],
                        [[k, c, f"{rv[k]['target'][c]:.3f}", f"{rv[k]['realised'][c]:.4f}", f"{rv[k]['true'][c]:,}",
                          f"{rv[k]['z'][c]:+.2f}"]
                         for k in [x for x in rv if x != "uniform_p1.00"] for c in SIM_TO_DETECTOR.values()])
    return t


# ---- chart --------------------------------------------------------------------------------
STYLE = """<style>
  .bg { fill: #fcfcfb; } .t1 { fill: #0b0b0b; } .t2 { fill: #52514e; } .grid { stroke: #e4e3df; }
  .axis { stroke: #8a8985; } .ref { stroke: #52514e; stroke-dasharray: 4 3; }
  .s1 { fill: #2a78d6; stroke: #2a78d6; } .s2 { fill: #eb6834; stroke: #eb6834; } .s3 { fill: #1baf7a; stroke: #1baf7a; }
  .ring { stroke: #fcfcfb; stroke-width: 2; } .ln { stroke-width: 2; fill: none; } .wh { stroke-width: 2; fill: none; }
  text { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; font-size: 12px; }
  .title { font-size: 13px; font-weight: 600; } .small { font-size: 11px; }
  @media (prefers-color-scheme: dark) {
    .bg { fill: #1a1a19; } .t1 { fill: #f0efec; } .t2 { fill: #c3c2b7; } .grid { stroke: #34332f; }
    .ref { stroke: #c3c2b7; } .ring { stroke: #1a1a19; }
    .s1 { fill: #3987e5; stroke: #3987e5; } .s2 { fill: #d95926; stroke: #d95926; } .s3 { fill: #199e70; stroke: #199e70; }
  }
</style>"""
SHAPES = {"s1": "circle", "s2": "square", "s3": "triangle"}


def marker(cls, x, y):
    shape = SHAPES[cls]
    if shape == "circle":
        return f'<circle class="{cls} ring" cx="{x:.1f}" cy="{y:.1f}" r="5"/>'
    if shape == "square":
        return f'<rect class="{cls} ring" x="{x - 5:.1f}" y="{y - 5:.1f}" width="10" height="10" rx="1"/>'
    return f'<path class="{cls} ring" d="M{x:.1f},{y - 6:.1f} L{x + 6:.1f},{y + 5:.1f} L{x - 6:.1f},{y + 5:.1f} Z"/>'


def nice_ticks(lo, hi, n=4):
    span = hi - lo
    step = min((s * 10 ** e for e in range(-2, 4) for s in (1, 2, 2.5, 5) if span / (s * 10 ** e) <= n), default=10 ** 4)
    first = step * int(lo // step)
    ticks = [round(first, 6)]
    while ticks[-1] < hi - 1e-9:
        ticks.append(round(ticks[-1] + step, 6))
    return ticks


def svg(b: dict) -> str:
    """Three panels of paired ATT change vs perfect (%): mean over seeds, whisker = range over seeds."""
    W, H, top, ph, pw = 940, 445, 92, 240, 250
    xs = [70, 70 + pw + 60, 70 + 2 * (pw + 60)]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
           'aria-labelledby="t d">', '<title id="t">Average travel time under camera errors</title>',
           '<desc id="d">ATT change against perfect counts, paired by seed, in percent: mean over 3 seeds, whiskers '
           'the range over seeds. Left: MaxPressure against the detection probability of every vehicle (no false '
           'detections), off-peak solid and peak dashed; J and C mark the junction-camera and crowded/far levels at '
           'their effective detection probability (dashed box: peak). Middle and right: each controller at the junction and crowded '
           'levels. The tables in docs/camera_error.md hold the numbers.</desc>',
           STYLE.replace("</style>", "  .dash { stroke-dasharray: 6 4; } rect.dash { stroke-dasharray: 3 2; }\n</style>"),
           f'<rect class="bg" width="{W}" height="{H}"/>']

    def rel(p):
        return (p["pct_mean"], p["pct_min"], p["pct_max"])

    def axes(x0, title, vals):
        ticks = nice_ticks(min(vals + [0.0]), max(vals + [0.0]))
        ylo, yhi = ticks[0], ticks[-1]
        if yhi - ylo < 1e-9:
            yhi = ylo + 1
        sy = lambda v: top + ph - (v - ylo) / (yhi - ylo) * ph                                 # noqa: E731
        out.append(f'<text class="t1 title" x="{x0}" y="{top - 22}">{title}</text>')
        for tk in ticks:
            cls = "axis" if tk == 0 else "grid"
            out.append(f'<line class="{cls}" x1="{x0}" y1="{sy(tk):.1f}" x2="{x0 + pw}" y2="{sy(tk):.1f}"/>'
                       f'<text class="t2 small" x="{x0 - 6}" y="{sy(tk) + 4:.1f}" text-anchor="end">{tk:+g}%</text>')
        return sy

    # Panel 1: MaxPressure sweep, both scenarios (same series colour: MaxPressure; line style = scenario)
    sweep_p = [float(k.replace("uniform_p", "")) for k in SWEEP]
    pts_all = {sc: [(1.0, (0.0, 0.0, 0.0))] + [(p, rel(b["sweep"][sc][k]["att_vs_perfect"]))
                                               for p, k in zip(sweep_p[1:], SWEEP[1:])] for sc in SCEN}
    marks = {sc: [(b["effective_p_detect"][sc][k], rel(b["main"][sc]["maxpressure"][k]["att_vs_perfect"]), lab)
                  for k, lab in (("junction", "J"), ("crowded", "C"))] for sc in SCEN}
    vals = [v for sc in SCEN for _, r in pts_all[sc] for v in r] + [v for sc in SCEN for _, r, _ in marks[sc] for v in r]
    x0 = xs[0]
    sy = axes(x0, "MaxPressure vs p_detect", vals)
    sx = lambda p: x0 + (1.0 - p) / 0.5 * pw                                                  # noqa: E731
    for p in sweep_p:
        out.append(f'<text class="t2 small" x="{sx(p):.1f}" y="{top + ph + 16}" text-anchor="middle">{p:g}</text>')
    out.append(f'<text class="t2 small" x="{x0 + pw / 2}" y="{top + ph + 32}" text-anchor="middle">p_detect of every '
               'vehicle (no false detections)</text>')
    for sc, dash in zip(SCEN, ("", " dash")):
        pts = [(sx(p), r) for p, r in pts_all[sc]]
        out.append(f'<polyline class="s1 ln{dash}" points="' + " ".join(f"{x:.1f},{sy(r[0]):.1f}" for x, r in pts) + '"/>')
        for x, r in pts:
            out.append(f'<line class="s1 wh" x1="{x:.1f}" y1="{sy(r[1]):.1f}" x2="{x:.1f}" y2="{sy(r[2]):.1f}"/>')
            out.append(marker("s1", x, sy(r[0])))
        for pe, r, lab in marks[sc]:
            x, y = sx(pe), sy(r[0])
            out.append(f'<line class="t1 wh" stroke="currentColor" x1="{x:.1f}" y1="{sy(r[1]):.1f}" x2="{x:.1f}" '
                       f'y2="{sy(r[2]):.1f}" style="stroke:#8a8985"/>')
            out.append(f'<rect class="bg{dash}" x="{x - 7:.1f}" y="{y - 8:.1f}" width="14" height="15" rx="2" '
                       'style="stroke:#8a8985"/>')
            out.append(f'<text class="t1 small" x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle" font-weight="600">'
                       f'{lab}</text>')
    ly = top + ph + 52
    out.append(f'<line class="s1 ln" x1="{x0}" y1="{ly - 4}" x2="{x0 + 24}" y2="{ly - 4}"/>'
               f'<text class="t2 small" x="{x0 + 30}" y="{ly}">Off-peak</text>'
               f'<line class="s1 ln dash" x1="{x0 + 90}" y1="{ly - 4}" x2="{x0 + 114}" y2="{ly - 4}"/>'
               f'<text class="t2 small" x="{x0 + 120}" y="{ly}">Peak</text>'
               f'<text class="t2 small" x="{x0}" y="{ly + 16}">J / C: junction / crowded level (with false '
               'detections; dashed box = peak)</text>')

    # Panels 2-3: controllers at the two noisy levels, per scenario
    ctls = [("maxpressure", "s1"), ("fixedtime_webster", "s2"), ("llm_guarded_mp", "s3")]
    noisy = ["junction", "crowded"]
    allv = [v for sc in SCEN for c, _ in ctls for k in noisy for v in rel(b["main"][sc][c][k]["att_vs_perfect"])]
    for (sc, name), x0 in zip(SCEN.items(), xs[1:]):
        sy = axes(x0, f"{name}: ATT change by level", allv)
        cx = {k: x0 + pw * (i + 0.5) / 2 for i, k in enumerate(noisy)}
        for k in noisy:
            out.append(f'<text class="t2 small" x="{cx[k]:.1f}" y="{top + ph + 16}" text-anchor="middle">{k}</text>')
        for j, (c, cls) in enumerate(ctls):
            off = (j - 1) * 22
            for k in noisy:
                r = rel(b["main"][sc][c][k]["att_vs_perfect"])
                x = cx[k] + off
                out.append(f'<line class="{cls} wh" x1="{x:.1f}" y1="{sy(r[1]):.1f}" x2="{x:.1f}" y2="{sy(r[2]):.1f}"/>')
                out.append(marker(cls, x, sy(r[0])))
    lx = xs[1]
    for c, cls in ctls:
        out.append(marker(cls, lx + 5, 24) + f'<text class="t1" x="{lx + 15}" y="28">{SHORT[c]}</text>')
        lx += 120
    out.append(f'<line class="axis wh" x1="{lx}" y1="18" x2="{lx}" y2="31"/><text class="t2" x="{lx + 8}" y="28">'
               'range over seeds</text>')
    out.append(f'<text class="t2 small" x="16" y="{H - 10}">ATT change vs perfect counts, paired by seed (3 seeds). '
               'Simulator exact; only the controllers\' counts are noised. Generated by scripts/make_camera_error.py.</text>')
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
    b = json.loads(json.dumps(report()))
    tabs = tables(b)
    doc = (ROOT / DOC).read_text()
    chart = svg(b)
    if args.check:
        stored = json.loads((ROOT / OUT).read_text())
        ok = (comparable(stored) == comparable(b) and render(doc, tabs) == doc
              and (ROOT / CHART).is_file() and (ROOT / CHART).read_text() == chart)
        print("docs/camera_error.md and its chart match the runs" if ok else
              "camera-error results out of date; run scripts/make_camera_error.py")
        sys.exit(0 if ok else 1)
    (ROOT / OUT).write_text(json.dumps(b, indent=1))
    (ROOT / DOC).write_text(render(doc, tabs))
    (ROOT / CHART).write_text(chart)
    print(f"Wrote {OUT}, {CHART}; updated {DOC}")
    for name, t in tabs.items():
        print(f"\n## {name}\n{t}")


if __name__ == "__main__":
    main()
