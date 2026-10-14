"""Calibrate the Indian 2x2 demand levels against measured capacity, under MaxPressure.

1. Capacity (trafficsense.sim.capacity), with the scenario's vehicle mix:
   * stop-line saturation flow s of a straight and a protected-turn lane (queue discharge);
   * entry admission limit of an entry lane (CityFlow insertion, permanent green).
2. Sweep total demand R (veh/h). For each R and seed: generate flows, run MaxPressure for
   duration_s steps and record the state at that moment, then keep running with no new
   arrivals (up to --drain-max s) and record when the network is empty.
   Also, from the flow file: the busiest non-right-turn lane's demand / s, Webster's critical
   flow ratio Y (ANALYTIC), and the busiest entry lane's demand / admission limit.
3. Selection rule, fixed before the sweep was run:
   * R "drains" for a seed if, at t = duration_s, vehicles still waiting to enter are <= 2 % of
     those generated, AND the network is empty within 900 s after arrivals stop.
   * R* = the lowest swept R at which any of the seeds does not drain.
   * peak = the largest swept R <= 0.9 * R*, and every seed must drain at it.
   * off-peak = peak / 2 (ASSUMPTION: off-peak demand is half the peak demand).

Output: outputs/validation/indian_demand_calibration.json. The chosen levels are then written
into configs/scenarios/indian_2x2.yaml by hand (the script prints them).
"""
import argparse
import copy
import json
import tempfile
import time
from datetime import datetime
from pathlib import Path

from trafficsense.config import load_config, repo_root
from trafficsense.control import make_controller
from trafficsense.experiment import git_info
from trafficsense.sim.capacity import (critical_flow_ratio, lane_demand, measure_discharge,
                                       measure_saturation, mixed_feed, turn_route)
from trafficsense.sim.demand import VEHICLE_KEYS, Network, generate
from trafficsense.sim.env import TrafficEnv
from trafficsense.sim.metrics import MetricsTracker
from trafficsense.sim.roadnet import load_roadnet

BACKLOG_MAX_SHARE = 0.02
DRAIN_MAX_S = 900
PEAK_FRACTION = 0.9
OFFPEAK_OVER_PEAK = 0.5
FEED_VEH_PER_S = 2.0


def measure_capacity(sc, rp, net):
    nw = Network(net)
    entry = nw.entry_roads[0]
    feed = mixed_feed(sc["vehicle_types"], FEED_VEH_PER_S, VEHICLE_KEYS)
    straight = measure_discharge(rp, net, turn_route(net, entry, "go_straight"), feed)
    left = measure_discharge(rp, net, turn_route(net, entry, "turn_left"), feed)
    admit = measure_saturation(rp, net, turn_route(net, entry, "go_straight"), feed)
    return {
        "feed_veh_per_s": FEED_VEH_PER_S,
        "saturation_flow": {"go_straight": straight, "turn_left": left},
        "entry_admission": admit,
    }


def demand_analysis(net, flows, cap, duration_s):
    s = {t: cap["saturation_flow"][t]["saturation_flow_veh_per_hour"] for t in ("go_straight", "turn_left")}
    admit = cap["entry_admission"]["measured_veh_per_hour"]
    per_h = 3600.0 / duration_s
    lanes = lane_demand(net, flows)
    entry_roads = set(Network(net).entry_roads)
    ratio, busiest, busiest_entry = {}, None, None
    for iid, ls in lanes.items():
        ratio[iid] = {}
        for lane, d in ls.items():
            vph = d["vehicles"] * per_h
            if d["turn"] == "turn_right":
                ratio[iid][lane] = 0.0   # free turn: runs in every phase, not part of Y
            else:
                ratio[iid][lane] = vph / s[d["turn"]]
                if busiest is None or ratio[iid][lane] > busiest["demand_over_saturation_flow"]:
                    busiest = {"intersection": iid, "lane": lane, "movement": d["movement"],
                               "veh_per_hour": vph, "saturation_flow_veh_per_hour": s[d["turn"]],
                               "demand_over_saturation_flow": ratio[iid][lane]}
            road = lane.rsplit("_", 1)[0]
            if road in entry_roads and (busiest_entry is None or vph > busiest_entry["veh_per_hour"]):
                busiest_entry = {"lane": lane, "movement": d["movement"], "veh_per_hour": vph,
                                 "demand_over_admission_limit": vph / admit}
    y = critical_flow_ratio(net, ratio)
    return {
        "busiest_lane": busiest,
        "busiest_entry_lane": busiest_entry,
        "critical_flow_ratio_Y_ANALYTIC": {i: v["Y"] for i, v in y.items()},
        "Y_max_ANALYTIC": max(v["Y"] for v in y.values()),
    }


def run_maxpressure(cfg, rp, flow_path, seed, duration_s, drain_max):
    c = copy.deepcopy(cfg)
    c["scenarios"]["_calibration"] = {"roadnet": str(rp), "flow": str(flow_path)}
    env = TrafficEnv(c, "_calibration", seed=seed)
    ctl = make_controller("maxpressure", c)
    m = MetricsTracker(env)
    for _ in range(duration_s):
        ctl.act(env)
        env.step()
        m.update()
    at_end = m.summary()["network"]
    totals = {}
    for r in m.rows:
        totals[r["time"]] = totals.get(r["time"], 0) + r["queue"]
    drain_s = None
    for k in range(1, drain_max + 1):
        ctl.act(env)
        env.step()
        if not env.eng.get_vehicles(include_waiting=True):
            drain_s = k
            break
    generated = at_end["throughput"] + at_end["vehicles_running_at_end"] + at_end["vehicles_waiting_to_enter_at_end"]
    return {
        "generated": generated,
        "throughput": at_end["throughput"],
        "running_at_end": at_end["vehicles_running_at_end"],
        "waiting_to_enter_at_end": at_end["vehicles_waiting_to_enter_at_end"],
        "finished_share": at_end["throughput"] / generated,
        "backlog_share": at_end["vehicles_waiting_to_enter_at_end"] / generated,
        "att": at_end["att"],
        "queue_mean_per_intersection": at_end["queue_mean_per_intersection"],
        "queue_max_network": max(totals.values()),
        "waiting_time_mean": at_end["waiting_time_mean"],
        "drain_s_after_arrivals_stop": drain_s,
        "drains": (at_end["vehicles_waiting_to_enter_at_end"] <= BACKLOG_MAX_SHARE * generated
                   and drain_s is not None and drain_s <= DRAIN_MAX_S),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--scenario-config", default="configs/scenarios/indian_2x2.yaml")
    ap.add_argument("--rates", type=float, nargs="+", required=True, help="total veh/h to sweep")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--drain-max", type=int, default=1800, help="max s to wait for the network to empty")
    ap.add_argument("--out", default="outputs/validation/indian_demand_calibration.json")
    args = ap.parse_args()

    cfg = load_config(args.config)
    sc = load_config(args.scenario_config)
    rp = repo_root() / sc["roadnet"]["file"]
    net = load_roadnet(rp)
    duration = int(sc["duration_s"])
    git = git_info()
    started = datetime.now().astimezone()

    t0 = time.perf_counter()
    cap = measure_capacity(sc, rp, net)
    print(f"saturation flow straight {cap['saturation_flow']['go_straight']['saturation_flow_veh_per_hour']:.0f}, "
          f"protected turn {cap['saturation_flow']['turn_left']['saturation_flow_veh_per_hour']:.0f}, "
          f"entry admission {cap['entry_admission']['measured_veh_per_hour']:.0f} veh/h", flush=True)

    sweep = []
    with tempfile.TemporaryDirectory() as tmp:
        for rate in sorted(args.rates):
            s2 = copy.deepcopy(sc)
            s2["demand_levels"] = {"sweep": {"veh_per_hour": rate}}
            for seed in args.seeds:
                flows, meta = generate(net, s2, "sweep", seed)
                fp = Path(tmp) / f"flow_{rate}_{seed}.json"
                fp.write_text(json.dumps(flows))
                row = {"veh_per_hour": rate, "seed": seed, "vehicles": meta["vehicles"],
                       **demand_analysis(net, flows, cap, duration),
                       "maxpressure": run_maxpressure(cfg, rp, fp, seed, duration, args.drain_max)}
                mp = row["maxpressure"]
                print(f"R={rate:6.0f} s{seed}: busiest lane d/s={row['busiest_lane']['demand_over_saturation_flow']:.2f} "
                      f"Ymax={row['Y_max_ANALYTIC']:.2f} | finished {mp['finished_share']:.3f} "
                      f"backlog {mp['backlog_share']:.3f} queue/int {mp['queue_mean_per_intersection']:.1f} "
                      f"ATT {mp['att']:.0f} drain {mp['drain_s_after_arrivals_stop']} -> "
                      f"{'drains' if mp['drains'] else 'DOES NOT DRAIN'}", flush=True)
                sweep.append(row)

    rates = sorted({r["veh_per_hour"] for r in sweep})
    drains = {R: all(r["maxpressure"]["drains"] for r in sweep if r["veh_per_hour"] == R) for R in rates}
    failing = [R for R in rates if not drains[R]]
    selection = {"rule": {"backlog_max_share": BACKLOG_MAX_SHARE, "drain_max_s": DRAIN_MAX_S,
                          "peak_fraction_of_R_star": PEAK_FRACTION, "offpeak_over_peak": OFFPEAK_OVER_PEAK},
                 "drains_all_seeds": {str(R): drains[R] for R in rates}}
    if failing:
        r_star = min(failing)
        cands = [R for R in rates if R <= PEAK_FRACTION * r_star and drains[R]]
        selection["R_star"] = r_star
        if cands:
            selection["peak_veh_per_hour"] = max(cands)
            selection["offpeak_veh_per_hour"] = max(cands) * OFFPEAK_OVER_PEAK
    out = {
        "provenance": {"script": "scripts/calibrate_indian_demand.py", "controller": "maxpressure",
                       "controller_params": make_controller("maxpressure", cfg).info(),
                       "scenario_config": args.scenario_config, "seeds": args.seeds,
                       "git_commit": git["commit"], "git_dirty": git["dirty"],
                       "timestamp": started.isoformat(timespec="seconds"),
                       "wall_time_s": round(time.perf_counter() - t0, 1)},
        "capacity": cap,
        "sweep": sweep,
        "selection": selection,
    }
    p = repo_root() / args.out
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1))
    print(f"Wrote {p}")
    print(json.dumps(selection, indent=1))


if __name__ == "__main__":
    main()
