"""Indian 2x2 scenario: roadnet structure and flow generation."""
import json

import cityflow
import pytest

from trafficsense.config import load_config, repo_root
from trafficsense.sim.roadnet import load_roadnet

SCENARIO_CFG = "configs/scenarios/indian_2x2.yaml"


@pytest.fixture(scope="module")
def sc():
    return load_config(SCENARIO_CFG)


@pytest.fixture(scope="module")
def roadnet_path(sc):
    p = repo_root() / sc["roadnet"]["file"]
    if not p.is_file():
        pytest.fail(f"{p} missing; run scripts/generate_indian_roadnet.py")
    return p


def test_roadnet_matches_generator(sc, roadnet_path):
    """The committed roadnet is exactly what the generator makes from the config."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("gen", repo_root() / "scripts" / "generate_indian_roadnet.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    assert gen.build(sc["roadnet"]) == json.loads(roadnet_path.read_text())


def test_roadnet_structure(sc, roadnet_path):
    net = load_roadnet(roadnet_path)
    assert sorted(net.ids) == ["intersection_1_1", "intersection_1_2", "intersection_2_1", "intersection_2_2"]
    raw = json.loads(roadnet_path.read_text())
    roads = {r["id"]: r for r in raw["roads"]}
    for iid, inter in net.intersections.items():
        # phase 0 is the transition phase, detected (not hardcoded)
        assert inter.transition_phase.index == 0
        assert inter.transition_phase.duration == 5
        assert all(inter.movements[k].turn == "turn_right" for k in inter.transition_phase.movements)
        assert [p.index for p in inter.green_phases] == list(range(1, 9))
        assert len(inter.paired_phases) == 4
        assert len(inter.neighbours) == 2
        # 4 approaches x 3 turns, every movement has lane links (the old roadnet had none)
        assert len(inter.movements) == 12
        assert all(m.lane_links for m in inter.movements)
        for r in inter.incoming_roads:
            lanes = roads[r]["lanes"]
            assert len(lanes) == 3
            assert all(l["width"] == sc["roadnet"]["lane_width_m"] for l in lanes)
            assert all(l["maxSpeed"] == sc["roadnet"]["lane_max_speed_mps"] for l in lanes)


def test_vehicle_crosses_both_intersections(roadnet_path, tmp_path):
    """A vehicle driving straight across the network finishes its trip."""
    route = ["road_0_1_0", "road_1_1_0", "road_2_1_0"]
    veh = {"length": 5.0, "width": 2.0, "maxPosAcc": 2.0, "maxNegAcc": 4.5, "usualPosAcc": 2.0,
           "usualNegAcc": 4.5, "minGap": 2.5, "maxSpeed": 12.5, "headwayTime": 1.5}
    (tmp_path / "flow.json").write_text(json.dumps(
        [{"vehicle": veh, "route": route, "interval": 1.0, "startTime": 0, "endTime": 0}]))
    (tmp_path / "cfg.json").write_text(json.dumps({
        "interval": 1.0, "seed": 0, "dir": "", "roadnetFile": str(roadnet_path),
        "flowFile": str(tmp_path / "flow.json"), "rlTrafficLight": True, "laneChange": False,
        "saveReplay": False, "roadnetLogFile": "", "replayLogFile": ""}))
    eng = cityflow.Engine(str(tmp_path / "cfg.json"), thread_num=1)
    for iid in ("intersection_1_1", "intersection_2_1"):
        eng.set_tl_phase(iid, 1)   # phase 1 = W-E straight
    seen = False
    for _ in range(200):
        eng.next_step()
        seen |= bool(eng.get_vehicles(include_waiting=False))
    assert seen
    assert eng.get_vehicles(include_waiting=True) == []
    assert eng.get_average_travel_time() < 200


# ---- flow generation ---------------------------------------------------------------------

from trafficsense.sim.demand import Network, generate   # noqa: E402


@pytest.fixture(scope="module")
def net(roadnet_path):
    return load_roadnet(roadnet_path)


def with_rate(sc, rate=2000.0):
    levels = {k: {"veh_per_hour": rate} for k in sc["demand_levels"]}
    return {**sc, "demand_levels": levels}


def test_entry_roads(net):
    nw = Network(net)
    assert len(nw.entry_roads) == 8
    assert sorted(nw.entry_side.values()) == sorted("EENNSSWW")


def test_generation_is_seeded(sc, net):
    s = with_rate(sc)
    a, _ = generate(net, s, "peak", 0)
    b, _ = generate(net, s, "peak", 0)
    c, _ = generate(net, s, "peak", 1)
    assert a == b
    assert a != c


def test_unset_demand_level_fails_loudly(sc, net):
    s = {**sc, "demand_levels": {"peak": {"veh_per_hour": None}}}
    with pytest.raises(ValueError):
        generate(net, s, "peak", 0)
    with pytest.raises(KeyError):
        generate(net, with_rate(sc), "rush", 0)


def test_routes_are_valid_and_times_in_range(sc, net):
    flows, meta = generate(net, with_rate(sc), "peak", 0)
    nw = Network(net)
    links = {(m.in_road, m.out_road) for opts in nw.from_road.values() for _, m in opts}
    for f in flows:
        r = f["route"]
        assert r[0] in nw.entry_roads
        assert r[-1] not in nw.from_road                 # ends on an exit road
        assert all((a, b) in links for a, b in zip(r, r[1:]))
        assert f["startTime"] == f["endTime"] and 0 <= f["startTime"] < sc["duration_s"]
        assert isinstance(f["startTime"], int)
    assert len(meta["vehicle_type_of_flow"]) == len(flows)


def test_mix_rate_and_turns_match_config(sc, net):
    flows, meta = generate(net, with_rate(sc, 8000.0), "peak", 0)
    n = len(flows)
    assert abs(n - 8000) < 5 * 8000 ** 0.5               # Poisson count
    shares = {k: v["share"] for k, v in sc["vehicle_types"].items()}
    tot = sum(shares.values())
    for k, c in meta["vehicles_by_type"].items():
        p = shares[k] / tot
        assert abs(c / n - p) < 5 * (p * (1 - p) / n) ** 0.5
        # each flow carries its type's parameters
    for f, vt in zip(flows, meta["vehicle_type_of_flow"]):
        assert f["vehicle"]["length"] == sc["vehicle_types"][vt]["length"]
    turns = meta["turns_realised"]
    tt = sum(turns.values())
    for k, p in sc["turn_probabilities"].items():
        assert abs(turns[k] / tt - p) < 0.02             # loop rejection shifts this only slightly
    side = Network(net).entry_side
    w = sc["entry_weights"]
    per_side = {}
    for road, c in meta["vehicles_by_entry_road"].items():
        per_side[side[road]] = per_side.get(side[road], 0) + c
    wsum = sum(w[s] * 2 for s in w)                       # two entry roads per side
    for s_, c in per_side.items():
        assert abs(c / n - 2 * w[s_] / wsum) < 0.02


def test_env_formats_seed_into_flow_path(cfg, sc, net, tmp_path):
    from trafficsense.sim.env import TrafficEnv
    flows, _ = generate(net, with_rate(sc, 500.0), "peak", 3)
    (tmp_path / "flow_s3.json").write_text(json.dumps(flows))
    c = {**cfg, "scenarios": {"x": {"roadnet": sc["roadnet"]["file"],
                                    "flow": str(tmp_path / "flow_s{seed}.json"),
                                    "generate_hint": "make it"}}}
    env = TrafficEnv(c, "x", seed=3)
    assert env.flow_path == tmp_path / "flow_s3.json" and env.flow_per_seed
    with pytest.raises(FileNotFoundError, match="make it"):
        TrafficEnv(c, "x", seed=4)


@pytest.mark.parametrize("level", ["offpeak", "peak"])
def test_committed_flows_regenerate_exactly(sc, net, level):
    """The flow files used in the experiments are exactly what the config + seed produce."""
    for seed in (0, 1, 2):
        p = repo_root() / sc["output_dir"] / f"flow_{level}_s{seed}.json"
        if not p.is_file():
            pytest.fail(f"{p} missing; run scripts/generate_indian_flow.py --level all --seed 0 1 2")
        flows, _ = generate(net, sc, level, seed)
        assert json.loads(p.read_text()) == flows
