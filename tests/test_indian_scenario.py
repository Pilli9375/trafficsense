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
