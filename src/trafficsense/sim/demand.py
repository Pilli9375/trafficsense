"""Seeded traffic demand for generated scenarios (Indian 2x2).

Each vehicle is one CityFlow flow entry (startTime == endTime), so its type and route are
recorded exactly. Generation, all driven by one numpy Generator seeded with `seed`:
  * arrivals: a Poisson process per entry road with rate total_rate * weight / sum(weights),
    over [0, duration_s); CityFlow needs whole-second start times, so times are floored;
  * vehicle type: drawn from the normalised `share` of each type;
  * route: from the entry road, a turn is drawn at every intersection from
    `turn_probabilities` until the vehicle reaches an exit road. A route that would revisit an
    intersection (circling a block) is redrawn; the realised turn counts are reported.
"""
from __future__ import annotations

import collections
import hashlib
import json
from typing import Any

import numpy as np

from trafficsense.sim.roadnet import Movement, Roadnet

VEHICLE_KEYS = ("length", "width", "maxPosAcc", "maxNegAcc", "usualPosAcc", "usualNegAcc",
                "minGap", "maxSpeed", "headwayTime")
MAX_ROUTE_DRAWS = 1000


class Network:
    """Road-level view of a roadnet: which movements leave each road, entry and exit roads."""

    def __init__(self, net: Roadnet):
        self.from_road: dict[str, list[tuple[str, Movement]]] = collections.defaultdict(list)
        out_roads = set()
        for iid, inter in net.intersections.items():
            for m in inter.movements:
                self.from_road[m.in_road].append((iid, m))
                out_roads.add(m.out_road)
        # entry roads: feed an intersection but are not the exit of any movement
        self.entry_roads = sorted(r for r in self.from_road if r not in out_roads)
        self.entry_side = {r: self.from_road[r][0][1].approach for r in self.entry_roads}
        if not self.entry_roads:
            raise ValueError("Roadnet has no entry roads")


def _probabilities(d: dict[str, float], what: str) -> tuple[list[str], np.ndarray]:
    keys = list(d)
    p = np.array([float(d[k]) for k in keys])
    if (p < 0).any() or p.sum() <= 0:
        raise ValueError(f"{what} must be non-negative and not all zero: {d}")
    return keys, p / p.sum()


def draw_route(rng: np.random.Generator, network: Network, entry: str,
               turn_probs: dict[str, float]) -> tuple[list[str], list[str]]:
    turns_k, turns_p = _probabilities(turn_probs, "turn_probabilities")
    for _ in range(MAX_ROUTE_DRAWS):
        route, turns, visited = [entry], [], set()
        ok = True
        while route[-1] in network.from_road:
            options = network.from_road[route[-1]]
            iid = options[0][0]
            if iid in visited:
                ok = False
                break
            visited.add(iid)
            turn = turns_k[rng.choice(len(turns_k), p=turns_p)]
            match = [m for _, m in options if m.turn == turn]
            if len(match) != 1:
                raise ValueError(f"{route[-1]}: expected one {turn} movement, found {len(match)}")
            route.append(match[0].out_road)
            turns.append(turn)
        if ok:
            return route, turns
    raise RuntimeError(f"No loop-free route from {entry} in {MAX_ROUTE_DRAWS} draws")


def generate(net: Roadnet, sc: dict[str, Any], level: str, seed: int) -> tuple[list[dict], dict]:
    """Return (flow entries, metadata) for demand level `level` and `seed`."""
    levels = sc["demand_levels"]
    if level not in levels:
        raise KeyError(f"Unknown demand level {level!r}; known: {list(levels)}")
    rate_h = levels[level].get("veh_per_hour")
    if rate_h is None or float(rate_h) <= 0:
        raise ValueError(f"demand_levels.{level}.veh_per_hour must be set to a positive number")
    rate_h = float(rate_h)
    duration = int(sc["duration_s"])
    types = sc["vehicle_types"]
    for name, t in types.items():
        missing = [k for k in VEHICLE_KEYS + ("share",) if k not in t]
        if missing:
            raise KeyError(f"vehicle_types.{name} is missing {missing}")
    type_k, type_p = _probabilities({k: v["share"] for k, v in types.items()}, "vehicle shares")

    network = Network(net)
    weights = sc["entry_weights"]
    unknown = {network.entry_side[r] for r in network.entry_roads} - set(weights)
    if unknown:
        raise KeyError(f"entry_weights has no entry for sides {sorted(unknown)}")
    w = np.array([float(weights[network.entry_side[r]]) for r in network.entry_roads])
    road_rates = rate_h / 3600.0 * w / w.sum()   # veh/s per entry road

    rng = np.random.default_rng(seed)
    arrivals = []   # (time, entry road)
    for road, lam in zip(network.entry_roads, road_rates):
        t = rng.exponential(1.0 / lam)
        while t < duration:
            arrivals.append((t, road))
            t += rng.exponential(1.0 / lam)
    arrivals.sort()

    flows, vtypes = [], []
    turn_counts: collections.Counter = collections.Counter()
    for t, road in arrivals:
        vt = type_k[rng.choice(len(type_k), p=type_p)]
        route, turns = draw_route(rng, network, road, sc["turn_probabilities"])
        turn_counts.update(turns)
        start = int(t)
        flows.append({
            "vehicle": {k: float(types[vt][k]) for k in VEHICLE_KEYS},
            "route": route,
            "interval": 1.0,
            "startTime": start,
            "endTime": start,
        })
        vtypes.append(vt)

    meta = {
        "level": level,
        "seed": seed,
        "veh_per_hour_target": rate_h,
        "duration_s": duration,
        "vehicles": len(flows),
        "vehicle_type_of_flow": vtypes,   # CityFlow names vehicle k "flow_<k>_0"
        "vehicles_by_type": dict(collections.Counter(vtypes)),
        "vehicles_by_entry_road": dict(collections.Counter(r for _, r in arrivals)),
        "turns_realised": dict(turn_counts),
        "entry_road_rate_veh_per_hour": {r: float(x * 3600) for r, x in zip(network.entry_roads, road_rates)},
        "scenario_config_sha256": config_hash(sc),
    }
    return flows, meta


def add_emergency(net: Roadnet, sc: dict[str, Any], base_flows: list[dict], seed: int) -> tuple[list[dict], dict]:
    """Return (base flows + emergency vehicles, metadata) for flow seed `seed`."""
    em = sc["emergency"]
    name = em["vehicle_type"]
    types = sc["emergency_vehicle_types"]
    if name not in types:
        raise KeyError(f"emergency.vehicle_type {name!r} is not in emergency_vehicle_types")
    vt = types[name]
    missing = [k for k in VEHICLE_KEYS if k not in vt]
    if missing:
        raise KeyError(f"emergency_vehicle_types.{name} is missing {missing}")
    if any(tuple(float(t[k]) for k in VEHICLE_KEYS) == tuple(float(vt[k]) for k in VEHICLE_KEYS)
           for t in sc["vehicle_types"].values()):
        raise ValueError(f"{name} has the same parameters as a normal vehicle type; it could not be told apart")
    rate_h = float(em["veh_per_hour"])
    if rate_h <= 0:
        raise ValueError(f"emergency.veh_per_hour must be positive, got {rate_h}")
    duration = int(sc["duration_s"])
    network = Network(net)
    w = np.array([float(sc["entry_weights"][network.entry_side[r]]) for r in network.entry_roads])
    road_rates = rate_h / 3600.0 * w / w.sum()

    em_seed = seed + int(em["seed_offset"])
    rng = np.random.default_rng(em_seed)
    arrivals = []
    for road, lam in zip(network.entry_roads, road_rates):
        t = rng.exponential(1.0 / lam)
        while t < duration:
            arrivals.append((t, road))
            t += rng.exponential(1.0 / lam)
    arrivals.sort()
    added = []
    for t, road in arrivals:
        route, turns = draw_route(rng, network, road, sc["turn_probabilities"])
        added.append({"vehicle": {k: float(vt[k]) for k in VEHICLE_KEYS}, "route": route, "interval": 1.0,
                      "startTime": int(t), "endTime": int(t)})
    n0 = len(base_flows)
    meta = {"seed": seed, "emergency_seed": em_seed, "vehicle_type": name, "veh_per_hour_target": rate_h,
            "base_vehicles": n0, "emergency_vehicles": len(added),
            "emergency": [{"flow_index": n0 + k, "vehicle_id": f"flow_{n0 + k}_0", "start_time": f["startTime"],
                           "route": f["route"]} for k, f in enumerate(added)]}
    return base_flows + added, meta


def config_hash(sc: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(sc, sort_keys=True).encode()).hexdigest()
