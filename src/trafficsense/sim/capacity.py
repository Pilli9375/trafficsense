"""Lane capacity and lane demand, measured on the simulator.

* measure_discharge: the stop-line SATURATION FLOW. Hold the signal red until the lane is full,
  switch it green, and count vehicles leaving the lane while the queue discharges. This is the
  rate a green phase can serve, so it is the capacity that signal timing works with.
* measure_saturation: the signals on a route permanently show the phase serving it and the
  route is fed far more vehicles than it can carry; the finished-vehicle rate after a warm-up.
  On a route that starts at the network edge this is limited by CityFlow's vehicle INSERTION:
  a waiting vehicle enters the lane (at speed 0) only once the previous one, which also started
  from standstill, is length + minGap ahead (Lane::available). It is therefore the most an
  entry lane can admit per hour, which is lower than the stop-line saturation flow.
  Mixed traffic is fed as CityFlow flows per vehicle type, with intervals giving the shares.
* lane_demand: vehicles per incoming lane per intersection, from the routes in a flow file
  (in these roadnets every incoming lane serves exactly one turn).
* critical_flow_ratio: Y = sum over the paired phases of the largest demand/saturation ratio
  among the non-right-turn lanes the phase serves. This is an ANALYTIC indicator (Webster's
  critical flow ratio), computed from measured saturation flows and flow-file demand; it is not a
  simulation result. Right turns are excluded because they are allowed in every phase.
"""
from __future__ import annotations

import collections
import json
import math
import tempfile
from pathlib import Path
from typing import Any

import cityflow

from trafficsense.sim.roadnet import Roadnet


def straight_route(net: Roadnet, start_road: str) -> list[str]:
    route = [start_road]
    while True:
        nxt = [m for i in net.intersections.values() for m in i.movements
               if m.in_road == route[-1] and m.turn == "go_straight"]
        if not nxt:
            return route
        route.append(nxt[0].out_road)


def turn_route(net: Roadnet, start_road: str, turn: str) -> list[str]:
    """`turn` at the first intersection, then straight on to the network edge."""
    first = [m for i in net.intersections.values() for m in i.movements
             if m.in_road == start_road and m.turn == turn]
    if len(first) != 1:
        raise ValueError(f"{start_road}: expected one {turn} movement, found {len(first)}")
    return [start_road] + straight_route(net, first[0].out_road)


def serving_phases(net: Roadnet, route: list[str]) -> dict[str, int]:
    """For each intersection on the route, the paired phase serving the route's movement there.
    Right turns run in every phase, so any paired phase serves them; the first one is used."""
    hold = {}
    for a, b in zip(route, route[1:]):
        for iid, inter in net.intersections.items():
            for m in inter.movements:
                if m.in_road == a and m.out_road == b:
                    hold[iid] = next(p.index for p in inter.paired_phases if m.index in p.movements)
    return {iid: hold[iid] for iid in net.intersections if iid in hold}


def mixed_feed(vehicle_types: dict[str, dict[str, Any]], rate_veh_per_s: float,
               keys: tuple[str, ...]) -> list[tuple[dict[str, Any], float]]:
    """Feed for measure_saturation: `rate_veh_per_s` in total, split by the types' `share`.
    CityFlow requires flow intervals >= 1 s, so a type needing more than 1 veh/s is fed by
    several identical flows."""
    total = sum(float(t["share"]) for t in vehicle_types.values())
    feed = []
    for t in vehicle_types.values():
        r = rate_veh_per_s * float(t["share"]) / total
        n = max(1, math.ceil(r))
        feed += [({k: float(t[k]) for k in keys}, n / r)] * n
    return feed


def measure_saturation(roadnet_path: Path, net: Roadnet, route: list[str],
                       feed: list[tuple[dict[str, Any], float]],
                       steps: int = 3600, warmup: int = 1200, seed: int = 0) -> dict[str, Any]:
    """feed: (vehicle parameters, interval in s) per flow; all start at t=0."""
    bad = [iv for _, iv in feed if iv < 1]
    if bad:
        raise ValueError(f"CityFlow needs flow intervals >= 1 s, got {bad}; use mixed_feed")
    flow = [{"vehicle": v, "route": route, "interval": float(iv), "startTime": 0, "endTime": steps}
            for v, iv in feed]
    hold = serving_phases(net, route)
    with tempfile.TemporaryDirectory() as tmp:
        fpath = Path(tmp) / "flow.json"
        fpath.write_text(json.dumps(flow))
        cpath = Path(tmp) / "config.json"
        cpath.write_text(json.dumps({"interval": 1.0, "seed": seed, "dir": "", "roadnetFile": str(roadnet_path),
                                     "flowFile": str(fpath), "rlTrafficLight": True, "laneChange": False,
                                     "saveReplay": False, "roadnetLogFile": "", "replayLogFile": ""}))
        eng = cityflow.Engine(str(cpath), thread_num=1)
    for iid in net.intersections:
        eng.set_tl_phase(iid, hold.get(iid, net.intersections[iid].green_phases[0].index))
    finished, prev, finished_after_warmup = 0, set(), 0
    for t in range(steps):
        eng.next_step()
        run = set(eng.get_vehicles(include_waiting=False))
        n = len(prev - run)
        finished += n
        if t >= warmup:
            finished_after_warmup += n
        prev = run
    waiting = len(set(eng.get_vehicles(include_waiting=True)) - prev)
    if waiting == 0:
        raise RuntimeError(f"Route {route} was not oversupplied (no entry queue at the end); "
                           "feed more vehicles to measure saturation")
    return {
        "route": route,
        "phases_held": hold,
        "finished_total": finished,
        "measured_veh_per_hour": finished_after_warmup * 3600 / (steps - warmup),
        "window_s": [warmup, steps],
        "entry_queue_at_end": waiting,
    }


def measure_discharge(roadnet_path: Path, net: Roadnet, route: list[str],
                      feed: list[tuple[dict[str, Any], float]], red: int = 900,
                      window: tuple[int, int] = (10, 70), seed: int = 0) -> dict[str, Any]:
    """Saturation flow (veh/h) of the first stop line on `route`: count vehicles leaving the
    lane during green seconds [window[0], window[1]) after `red` s of red. The first seconds
    (start-up lost time) are excluded, as in the usual saturation-flow definition; the count
    from green onset is reported too. Raises if the queue runs out inside the window."""
    if route[1:] == []:
        raise ValueError("route needs at least two roads")
    first, lane = None, None
    for iid, inter in net.intersections.items():
        for m in inter.movements:
            if m.in_road == route[0] and m.out_road == route[1]:
                first, lane, mv = iid, m.in_lanes[0], m
    if first is None:
        raise ValueError(f"{route[0]} -> {route[1]} is not a movement")
    if mv.turn == "turn_right":
        raise ValueError("right turns run in every phase; they cannot be held red")
    hold = serving_phases(net, route)
    red_phase = next(p.index for p in net.intersections[first].paired_phases if mv.index not in p.movements)
    flow = [{"vehicle": v, "route": route, "interval": float(iv), "startTime": 0, "endTime": red + window[1]}
            for v, iv in feed]
    with tempfile.TemporaryDirectory() as tmp:
        fpath = Path(tmp) / "flow.json"
        fpath.write_text(json.dumps(flow))
        cpath = Path(tmp) / "config.json"
        cpath.write_text(json.dumps({"interval": 1.0, "seed": seed, "dir": "", "roadnetFile": str(roadnet_path),
                                     "flowFile": str(fpath), "rlTrafficLight": True, "laneChange": False,
                                     "saveReplay": False, "roadnetLogFile": "", "replayLogFile": ""}))
        eng = cityflow.Engine(str(cpath), thread_num=1)
    for iid in net.intersections:
        eng.set_tl_phase(iid, hold.get(iid, net.intersections[iid].green_phases[0].index))
    eng.set_tl_phase(first, red_phase)
    for _ in range(red):
        eng.next_step()
    queue_at_green = len(eng.get_lane_vehicles()[lane])
    eng.set_tl_phase(first, hold[first])
    prev = set(eng.get_lane_vehicles()[lane])
    left_per_s = []
    for _ in range(window[1]):
        eng.next_step()
        cur = set(eng.get_lane_vehicles()[lane])
        left_per_s.append(len(prev - cur))
        prev = cur
        if not cur:
            raise RuntimeError(f"Queue on {lane} ran out after {len(left_per_s)} s of green; "
                               "the discharge window is not saturated")
    steady = sum(left_per_s[window[0]:])
    return {
        "route": route,
        "lane": lane,
        "turn": mv.turn,
        "red_s": red,
        "queue_at_green": queue_at_green,
        "window_s": list(window),
        "left_in_window": steady,
        "left_from_green_onset": sum(left_per_s),
        "saturation_flow_veh_per_hour": steady * 3600 / (window[1] - window[0]),
    }


def lane_demand(net: Roadnet, flows: list[dict]) -> dict[str, dict[str, Any]]:
    """{intersection: {in_lane: {"turn", "movement", "vehicles"}}} over every route hop."""
    by_pair = {}
    for iid, inter in net.intersections.items():
        for m in inter.movements:
            if len(m.in_lanes) != 1:
                raise ValueError(f"{iid} {m.name}: expected one incoming lane per movement")
            by_pair[(m.in_road, m.out_road)] = (iid, m)
    out: dict[str, dict[str, Any]] = collections.defaultdict(dict)
    for iid, inter in net.intersections.items():
        for m in inter.movements:
            out[iid][m.in_lanes[0]] = {"turn": m.turn, "movement": m.name, "movement_index": m.index,
                                       "vehicles": 0}
    for f in flows:
        r = f["route"]
        for a, b in zip(r, r[1:]):
            if (a, b) not in by_pair:
                raise ValueError(f"Route hop {a} -> {b} is not a movement")
            iid, m = by_pair[(a, b)]
            out[iid][m.in_lanes[0]]["vehicles"] += 1
    return dict(out)


def critical_flow_ratio(net: Roadnet, ratio_of_lane: dict[str, dict[str, float]]) -> dict[str, Any]:
    """ANALYTIC: Webster's Y per intersection from per-lane demand/saturation ratios."""
    res = {}
    for iid, inter in net.intersections.items():
        per_phase = {}
        for p in inter.paired_phases:
            lanes = [inter.movements[k].in_lanes[0] for k in p.movements
                     if inter.movements[k].turn != "turn_right"]
            per_phase[p.index] = max(ratio_of_lane[iid][l] for l in lanes)
        res[iid] = {"Y": sum(per_phase.values()), "per_phase_max_ratio": per_phase}
    return res
