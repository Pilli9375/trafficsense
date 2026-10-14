"""Ambulance flows, detection and metrics."""
import copy
import json

import pytest

from trafficsense.config import load_config, repo_root
from trafficsense.control import make_controller
from trafficsense.sim.demand import add_emergency, generate
from trafficsense.sim.emergency import EmergencyVehicles, lane_lengths
from trafficsense.sim.env import TrafficEnv
from trafficsense.sim.metrics import MetricsTracker
from trafficsense.sim.roadnet import load_roadnet

AMB = "indian_2x2_peak_amb"


def run(cfg, scenario, ctl, steps, seed):
    env = TrafficEnv(cfg, scenario, seed=seed)
    m = MetricsTracker(env)
    for _ in range(steps):
        ctl.act(env)
        env.step()
        m.update()
    return env, m.summary()


@pytest.fixture(scope="module")
def sc():
    return load_config("configs/scenarios/indian_2x2.yaml")


def test_ambulance_flow_extends_the_normal_flow(sc):
    d = repo_root() / sc["output_dir"]
    for level in ("peak", "offpeak"):
        for seed in (0, 1, 2):
            base = json.loads((d / f"flow_{level}_s{seed}.json").read_text())
            amb = json.loads((d / f"flow_{level}_amb_s{seed}.json").read_text())
            assert amb[:len(base)] == base                    # same vehicles, same ids
            meta = json.loads((d / f"flow_{level}_amb_s{seed}.meta.json").read_text())["emergency"]
            assert meta["emergency_seed"] == seed + sc["emergency"]["seed_offset"]
            assert len(amb) - len(base) == meta["emergency_vehicles"] == len(meta["emergency"])
            veh = {k: float(v) for k, v in sc["emergency_vehicle_types"]["ambulance"].items()}
            assert all(f["vehicle"] == veh for f in amb[len(base):])


def test_ambulance_counts(sc):
    """docs/emergency.md quotes these numbers (checked in test_emergency_smoke.py)."""
    d = repo_root() / sc["output_dir"]
    em = {s: json.loads((d / f"flow_peak_amb_s{s}.meta.json").read_text())["emergency"]["emergency"] for s in (0, 1, 2)}
    assert [len(em[s]) for s in (0, 1, 2)] == [3, 14, 6]
    first = {s: [a for a in em[s] if a["start_time"] < 600] for s in (0, 1, 2)}
    assert first[0] == [] and min(a["start_time"] for a in em[0]) == 1670
    assert [(a["start_time"], a["route"]) for a in first[1]] == [(257, ["road_3_2_2", "road_2_2_1"])]
    assert [(a["start_time"], a["route"]) for a in first[2]] == [(253, ["road_3_2_2", "road_2_2_2", "road_1_2_2"])]


def test_add_emergency_is_seeded_separately(sc):
    net = load_roadnet(repo_root() / sc["roadnet"]["file"])
    base, _ = generate(net, sc, "peak", 0)
    a, m = add_emergency(net, sc, base, 0)
    b, _ = add_emergency(net, sc, [], 0)
    assert a[len(base):] == b                           # ambulances do not depend on the normal flow
    rate = sc["emergency"]["veh_per_hour"]
    counts = [add_emergency(net, sc, [], s)[1]["emergency_vehicles"] for s in range(40)]
    assert abs(sum(counts) / len(counts) - rate) < 1.5   # Poisson mean = rate over one hour
    bad = copy.deepcopy(sc)
    bad["emergency_vehicle_types"]["ambulance"] = dict(sc["vehicle_types"]["car"])
    with pytest.raises(ValueError, match="same parameters"):
        add_emergency(net, bad, base, 0)


def test_lane_lengths_match_the_simulator(cfg):
    env = TrafficEnv(cfg, "indian_2x2_peak", seed=0)
    lengths = lane_lengths(env.roadnet_path)
    front = {}
    for _ in range(300):
        env.step()
        dist, speed = env.eng.get_vehicle_distance(), env.eng.get_vehicle_speed()
        for lane, vs in env.eng.get_lane_vehicles().items():
            for v in vs:
                assert dist[v] <= lengths[lane] + 1e-6
                if speed[v] < 0.1:
                    front[lane] = max(front.get(lane, 0), dist[v])
    # the first vehicle of a queue stops within 1 m of the stop line
    queued = [l for l in env.intersection(env.intersection_ids[0]).incoming_lanes if front.get(l, 0) > 150]
    assert queued and all(lengths[l] - front[l] < 1.0 for l in queued)


def test_no_ambulance_yet_means_identical_traffic(cfg):
    """Seed 0's first ambulance starts at t=1670 s: the first 600 s equal the normal scenario."""
    ev = EmergencyVehicles(TrafficEnv(cfg, AMB, seed=0))
    assert min(ev.start.values()) > 600
    _, a = run(cfg, AMB, make_controller("maxpressure", cfg), 600, 0)
    _, b = run(cfg, "indian_2x2_peak", make_controller("maxpressure", cfg), 600, 0)
    assert a["network"] == b["network"] and a["emergency"]["scheduled_in_run"] == 0
    assert "emergency" not in b


def test_ambulance_metrics_and_detection(cfg):
    """Seed 2's first ambulance (t=253 s) goes straight through two intersections; seed 1's
    (t=257 s) turns on a free turn and is never reported."""
    env = TrafficEnv(cfg, AMB, seed=2)
    ev = EmergencyVehicles(env)
    m = MetricsTracker(env)
    ctl = make_controller("maxpressure", cfg)
    seen = []
    for _ in range(600):
        ctl.act(env)
        env.step()
        m.update()
        for iid in env.intersection_ids:
            for s in ev.detect(env, iid, 150):
                info = env.eng.get_vehicle_info(s.vehicle)
                mv = env.intersection(iid).movements[s.movement]
                assert 0 <= s.distance_m <= 150 and mv.in_road == info["road"] and s.turn != "turn_right"
                assert all(s.movement in env.intersection(iid).phases[p].movements for p in s.serving_phases)
                seen.append(s)
    e = m.summary()["emergency"]
    assert e["scheduled_in_run"] >= 1 and seen
    for r in e["vehicles"]:
        assert r["entered"] >= r["scheduled_start"]
        if r["finished"] is not None:
            assert r["travel_time_s"] == r["finished"] - r["scheduled_start"]
            assert 0 <= r["stopped_s"] <= r["travel_time_s"]
    done = [r for r in e["vehicles"] if r["finished"] is not None]
    assert e["finished"] == len(done) and e["travel_time_mean_s"] == pytest.approx(
        sum(r["travel_time_s"] for r in done) / len(done))


def test_free_turn_ambulance_is_not_reported(cfg):
    env = TrafficEnv(cfg, AMB, seed=1)
    ev = EmergencyVehicles(env)
    first = min(ev.start, key=ev.start.get)
    assert ev.route[first] == ["road_3_2_2", "road_2_2_1"]           # a free turn at intersection_2_2
    on_lane = False
    for _ in range(300):
        env.step()
        on_lane |= first in env.eng.get_lane_vehicles()["road_3_2_2_2"]
        assert not any(ev.detect(env, i, 1000) for i in env.intersection_ids)
    assert on_lane


def test_full_run_ambulance_counts(sc):
    """docs/emergency.md and run_emergency_experiments.py quote: seeds 0-4 hold 37 ambulances,
    29 signal-relevant; seeds 3 and 4 have 6 and 8."""
    from trafficsense.sim.emergency import route_movements, signal_relevant
    net = load_roadnet(repo_root() / sc["roadnet"]["file"])
    d = repo_root() / sc["output_dir"]
    em = [json.loads((d / f"flow_peak_amb_s{s}.meta.json").read_text())["emergency"]["emergency"] for s in range(5)]
    assert [len(e) for e in em] == [3, 14, 6, 6, 8]
    routes = [a["route"] for e in em for a in e]
    assert len(routes) == 37 and sum(signal_relevant(net, r) for r in routes) == 29
    assert route_movements(net, ["road_3_2_2", "road_2_2_1"]) == [("intersection_2_2", "turn_right")]
    assert not signal_relevant(net, ["road_3_2_2", "road_2_2_1"])
