"""Demand analysis of a CityFlow flow file, and the capacity of the busiest entry lane.

Counts vehicles by entry road, by start time (10-minute bins) and by the turn they make at
the first intersection (each lane in the CoLLMLight roadnets serves exactly one turn, so the
turn split is the per-lane demand). Then measures one lane's maximum discharge rate:

  * estimate (analytical, NOT measured): steady car-following flow
        q = v / (L + minGap + v * headwayTime)   [veh/s/lane]
    using the flow file's vehicle parameters. Labelled as an estimate everywhere.
  * measured: a CityFlow run where every signal permanently shows the phase serving the
    busiest lane's movement, fed 1 veh/s along a straight route from that entry road to the
    opposite boundary. The finished-vehicle rate over the last 40 minutes is the measured
    saturation flow (the first 20 minutes are excluded as warm-up).

A few routes list consecutive roads with no movement between them (e.g. a U-turn); CityFlow
treats route roads as waypoints and finds a path, so their first turn is reported as
"non_adjacent" rather than guessed.

Output: outputs/validation/demand_<scenario>.json
"""
import argparse
import collections
import json
import tempfile
from pathlib import Path

import cityflow

from trafficsense.config import load_config, repo_root
from trafficsense.sim.roadnet import load_roadnet


def first_turn(net, route):
    if len(route) < 2:
        return None, None
    for inter in net.intersections.values():
        for m in inter.movements:
            if m.in_road == route[0] and m.out_road == route[1]:
                return inter.id, m
    return None, "non_adjacent"   # CityFlow treats route roads as waypoints and re-routes


def straight_route(net, start_road):
    route = [start_road]
    while True:
        nxt = [m for i in net.intersections.values() for m in i.movements
               if m.in_road == route[-1] and m.turn == "go_straight"]
        if not nxt:
            return route
        route.append(nxt[0].out_road)


def measure_saturation(roadnet_path, flows, start_road, net, steps=3600, warmup=1200):
    route = straight_route(net, start_road)
    vehicle = flows[0]["vehicle"]
    flow = [{"vehicle": vehicle, "route": route, "interval": 1.0, "startTime": 0, "endTime": steps}]
    # phase that serves the straight movement out of start_road, at every intersection on the route
    serve = {}
    for inter in net.intersections.values():
        for m in inter.movements:
            if m.in_road in route and m.turn == "go_straight":
                serve[inter.id] = next(p.index for p in inter.paired_phases if m.index in p.movements)
    with tempfile.TemporaryDirectory() as tmp:
        fpath = Path(tmp) / "flow.json"
        fpath.write_text(json.dumps(flow))
        cpath = Path(tmp) / "config.json"
        cpath.write_text(json.dumps({"interval": 1.0, "seed": 0, "dir": "", "roadnetFile": str(roadnet_path),
                                     "flowFile": str(fpath), "rlTrafficLight": True, "laneChange": False,
                                     "saveReplay": False, "roadnetLogFile": "", "replayLogFile": ""}))
        eng = cityflow.Engine(str(cpath), thread_num=1)
    for iid in net.intersections:
        eng.set_tl_phase(iid, serve.get(iid, net.intersections[iid].green_phases[0].index))
    finished, prev, finished_after_warmup = 0, set(), 0
    for t in range(steps):
        eng.next_step()
        run = set(eng.get_vehicles(include_waiting=False))
        n = len(prev - run)
        finished += n
        if t >= warmup:
            finished_after_warmup += n
        prev = run
    return {
        "route": route,
        "phases_held": serve,
        "finished_total": finished,
        "measured_veh_per_hour": finished_after_warmup * 3600 / (steps - warmup),
        "window_s": [warmup, steps],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="synthetic_4x4")
    args = ap.parse_args()
    cfg = load_config("configs/default.yaml")
    sc = cfg["scenarios"][args.scenario]
    roadnet_path = repo_root() / sc["roadnet"]
    flows = json.loads((repo_root() / sc["flow"]).read_text())
    net = load_roadnet(roadnet_path)
    n = len(flows)
    if not all(f["startTime"] == f["endTime"] for f in flows):
        raise ValueError("Expected one vehicle per flow entry (startTime == endTime)")

    by_road = collections.Counter(f["route"][0] for f in flows)
    by_bin = collections.Counter(int(f["startTime"] // 600) for f in flows)
    turns = collections.defaultdict(collections.Counter)
    for f in flows:
        _, m = first_turn(net, f["route"])
        turns[f["route"][0]][m if isinstance(m, str) else m.turn if m else "exits_immediately"] += 1

    top_road, top_n = by_road.most_common(1)[0]
    top_turn, top_turn_n = turns[top_road].most_common(1)[0]
    v = flows[0]["vehicle"]
    est = v["maxSpeed"] / (v["length"] + v["minGap"] + v["maxSpeed"] * v["headwayTime"]) * 3600
    sat = measure_saturation(roadnet_path, flows, top_road, net)

    out = {
        "scenario": args.scenario,
        "flow_file": sc["flow"],
        "vehicles": n,
        "vehicle_types": len({json.dumps(f["vehicle"], sort_keys=True) for f in flows}),
        "vehicle_params": v,
        "by_entry_road": [{"road": r, "vehicles": c, "share": c / n, "first_turn": dict(turns[r])}
                          for r, c in by_road.most_common()],
        "by_start_time_10min": {f"{b*10}-{b*10+10} min": by_bin[b] for b in sorted(by_bin)},
        "busiest_road": {
            "road": top_road, "vehicles_per_hour": top_n, "share": top_n / n,
            "busiest_lane_movement": top_turn, "busiest_lane_vehicles_per_hour": top_turn_n,
            "lanes": len(next(r for r in json.loads(roadnet_path.read_text())["roads"] if r["id"] == top_road)["lanes"]),
        },
        "lane_capacity": {
            "estimate_veh_per_hour_ESTIMATE": est,
            "estimate_formula": "maxSpeed / (length + minGap + maxSpeed * headwayTime) * 3600",
            "measured_permanent_green": sat,
        },
    }
    out["busiest_road"]["demand_over_measured_capacity"] = top_turn_n / sat["measured_veh_per_hour"]
    path = repo_root() / "outputs" / "validation" / f"demand_{args.scenario}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {path}")
    print(json.dumps({k: out[k] for k in ("vehicles", "busiest_road", "lane_capacity", "by_start_time_10min")}, indent=2))
    for r in out["by_entry_road"]:
        print(f"  {r['road']:12s} {r['vehicles']:5d} {100*r['share']:5.1f}%  {r['first_turn']}")


if __name__ == "__main__":
    main()
