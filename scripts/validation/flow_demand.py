"""Demand analysis of a CityFlow flow file, and the capacity of the busiest entry lane.

Counts vehicles by entry road, by start time (10-minute bins) and by the turn they make at
the first intersection (each lane in the CoLLMLight roadnets serves exactly one turn, so the
turn split is the per-lane demand). Then measures one lane's maximum discharge rate:

  * estimate (analytical, NOT measured): steady car-following flow
        q = v / (L + minGap + v * headwayTime)   [veh/s/lane]
    using the flow file's vehicle parameters. Labelled as an estimate everywhere.
  * measured, permanent green: every signal on a straight route from that entry road
    permanently shows the phase serving it, fed 1 veh/s. The finished-vehicle rate over the
    last 40 minutes (first 20 minutes = warm-up). For an entry road this is limited by
    CityFlow's vehicle insertion (a vehicle enters at speed 0 only once the previous one is
    length + minGap ahead), so it is the most vehicles the entry lane can ADMIT per hour.
  * measured, stop-line saturation flow: hold the lane red for 900 s, then green, and count
    vehicles leaving the queue in green seconds 10-70 (trafficsense.sim.capacity).

A few routes list consecutive roads with no movement between them (e.g. a U-turn); CityFlow
treats route roads as waypoints and finds a path, so their first turn is reported as
"non_adjacent" rather than guessed.

Output: outputs/validation/demand_<scenario>.json
"""
import argparse
import collections
import json
from trafficsense.config import load_config, repo_root
from trafficsense.sim.capacity import measure_discharge, measure_saturation, straight_route
from trafficsense.sim.roadnet import load_roadnet


def first_turn(net, route):
    if len(route) < 2:
        return None, None
    for inter in net.intersections.values():
        for m in inter.movements:
            if m.in_road == route[0] and m.out_road == route[1]:
                return inter.id, m
    return None, "non_adjacent"   # CityFlow treats route roads as waypoints and re-routes


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
    # one vehicle type, fed 1 veh/s straight across from the busiest entry road
    sat = measure_saturation(roadnet_path, net, straight_route(net, top_road), [(v, 1.0)])
    del sat["entry_queue_at_end"]
    dis = measure_discharge(roadnet_path, net, straight_route(net, top_road), [(v, 1.0)])

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
            "measured_permanent_green_note": "limited by CityFlow vehicle insertion at the network edge",
            "measured_stop_line_discharge": dis,
        },
    }
    out["busiest_road"]["demand_over_measured_capacity"] = top_turn_n / sat["measured_veh_per_hour"]
    out["busiest_road"]["demand_over_stop_line_saturation_flow"] = top_turn_n / dis["saturation_flow_veh_per_hour"]
    path = repo_root() / "outputs" / "validation" / f"demand_{args.scenario}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {path}")
    print(json.dumps({k: out[k] for k in ("vehicles", "busiest_road", "lane_capacity", "by_start_time_10min")}, indent=2))
    for r in out["by_entry_road"]:
        print(f"  {r['road']:12s} {r['vehicles']:5d} {100*r['share']:5.1f}%  {r['first_turn']}")


if __name__ == "__main__":
    main()
