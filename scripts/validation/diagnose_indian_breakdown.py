"""Where does the Indian 2x2 network break down under MaxPressure? Diagnostic for the doc.

Runs MaxPressure at one demand level (default: R* from the calibration, 5500 veh/h, seed 2: the seed that failed there) and
records, every 600 s: vehicles running and waiting to enter, and the incoming lanes whose
vehicle count reaches their storage (lane length / share-weighted mean of length + minGap);
at the end: the share of time each intersection spent in the transition phase, the time
share of each green phase, and the backlog by first route hop.

Output: outputs/validation/indian_breakdown_<rate>_s<seed>.json
"""
import argparse
import collections
import copy
import json
import tempfile
from pathlib import Path

from trafficsense.config import load_config, repo_root
from trafficsense.control import make_controller
from trafficsense.experiment import git_info
from trafficsense.sim.demand import generate
from trafficsense.sim.env import TrafficEnv
from trafficsense.sim.roadnet import load_roadnet


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rate", type=float, default=5500)
    ap.add_argument("--seed", type=int, default=2)
    args = ap.parse_args()
    cfg = load_config("configs/default.yaml")
    sc = load_config("configs/scenarios/indian_2x2.yaml")
    rp = repo_root() / sc["roadnet"]["file"]
    net = load_roadnet(rp)
    s2 = copy.deepcopy(sc)
    s2["demand_levels"] = {"x": {"veh_per_hour": args.rate}}
    flows, _ = generate(net, s2, "x", args.seed)

    types = sc["vehicle_types"]
    tot = sum(t["share"] for t in types.values())
    spacing = sum(t["share"] / tot * (t["length"] + t["minGap"]) for t in types.values())

    with tempfile.TemporaryDirectory() as tmp:
        fp = Path(tmp) / "flow.json"
        fp.write_text(json.dumps(flows))
        cfg["scenarios"]["_diag"] = {"roadnet": str(rp), "flow": str(fp)}
        env = TrafficEnv(cfg, "_diag", seed=args.seed)
    ctl = make_controller("maxpressure", cfg)
    roads = {r["id"]: r for r in json.loads(rp.read_text())["roads"]}
    inter_w = {i["id"]: i["width"] for i in json.loads(rp.read_text())["intersections"]}

    def storage(lane):
        r = roads[lane.rsplit("_", 1)[0]]
        (a, b) = r["points"][0], r["points"][-1]
        length = ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5
        length -= inter_w[r["startIntersection"]] + inter_w[r["endIntersection"]]
        return length / spacing

    in_lanes = sorted({l for i in env.intersection_ids for l in env.intersection(i).incoming_lanes})
    store = {l: storage(l) for l in in_lanes}
    phase_time = collections.Counter()
    snapshots = []
    for t in range(1, int(sc["duration_s"]) + 1):
        ctl.act(env)
        env.step()
        for i in env.intersection_ids:
            phase_time[(i, env.current_phase(i))] += 1
        if t % 600 == 0:
            cnt = env.eng.get_lane_vehicle_count()
            running = len(env.eng.get_vehicles())
            full = sorted((l for l in in_lanes if cnt[l] >= store[l] - 1), key=lambda l: -cnt[l])
            snapshots.append({"t": t, "running": running,
                              "waiting_to_enter": len(env.eng.get_vehicles(include_waiting=True)) - running,
                              "lanes_at_storage": [{"lane": l, "vehicles": cnt[l], "storage": round(store[l], 1),
                                                    "entry_road": roads[l.rsplit("_", 1)[0]]["startIntersection"] not in env.intersection_ids}
                                                   for l in full]})
    run = set(env.eng.get_vehicles())
    wait = set(env.eng.get_vehicles(include_waiting=True)) - run
    first_hop = collections.Counter()
    for v in wait:
        r = flows[int(v.split("_")[1])]["route"]
        first_hop[f"{r[0]} -> {r[1]}"] += 1
    shares = {}
    for i in env.intersection_ids:
        n = sum(c for (ii, _), c in phase_time.items() if ii == i)
        shares[i] = {str(p): c / n for (ii, p), c in sorted(phase_time.items()) if ii == i}
    git = git_info()
    out = {
        "provenance": {"script": "scripts/validation/diagnose_indian_breakdown.py", "controller": "maxpressure",
                       "rate_veh_per_hour": args.rate, "seed": args.seed,
                       "git_commit": git["commit"], "git_dirty": git["dirty"]},
        "mean_vehicle_spacing_m": spacing,
        "snapshots": snapshots,
        "phase_time_share": shares,
        "transition_phase": {i: env.intersection(i).transition_phase.index for i in env.intersection_ids},
        "backlog_by_first_hop": dict(first_hop.most_common()),
    }
    p = repo_root() / "outputs" / "validation" / f"indian_breakdown_{args.rate:.0f}_s{args.seed}.json"
    p.write_text(json.dumps(out, indent=1))
    print(f"Wrote {p}")
    for s in snapshots:
        print(s["t"], s["running"], s["waiting_to_enter"], [(x["lane"], x["vehicles"]) for x in s["lanes_at_storage"]])
    print({i: round(v[str(out['transition_phase'][i])], 3) for i, v in shares.items()})
    print(out["backlog_by_first_hop"])


if __name__ == "__main__":
    main()
