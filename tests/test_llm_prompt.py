import json

import pytest

from trafficsense.llm.prompt import (FREE_TURN, InvalidResponse, messages, observe, parse_response, render,
                                     response_schema)
from trafficsense.sim.env import TrafficEnv
from trafficsense.sim.vehicles import VehicleTypes


@pytest.mark.parametrize("text,ftype", [
    ("not json", "invalid_json"),
    ('{"phase": 2}', "invalid_schema"),
    ('{"phase": 2, "reason": "ok", "extra": 1}', "invalid_schema"),
    ('{"phase": "2", "reason": "ok"}', "invalid_schema"),
    ('{"phase": true, "reason": "ok"}', "invalid_schema"),
    ('{"phase": 2, "reason": "  "}', "invalid_schema"),
    ('[2, "ok"]', "invalid_schema"),
    ('{"phase": 9, "reason": "ok"}', "phase_not_allowed"),
    ('{"phase": 2, "reason": "' + " ".join(["w"] * 26) + '"}', "reason_too_long"),
])
def test_parse_response_failures(text, ftype):
    with pytest.raises(InvalidResponse) as e:
        parse_response(text, [1, 2, 3])
    assert e.value.failure_type == ftype


def test_parse_response_ok():
    assert parse_response('{"phase": 2, "reason": " ' + " ".join(["w"] * 25) + ' "}', [2]) == (2, " ".join(["w"] * 25))


def test_schema_restricts_phase_to_allowed():
    s = response_schema([3, 1])
    assert s["properties"]["phase"]["enum"] == [1, 3] and s["required"] == ["phase", "reason"]


@pytest.fixture(scope="module")
def peak_env(cfg):
    env = TrafficEnv(cfg, "indian_2x2_peak", seed=0)
    for _ in range(300):
        env.step()
    return env


def test_observation_matches_simulator(peak_env):
    env = peak_env
    iid = env.intersection_ids[0]
    obs = observe(env, iid, [1, 2], "isolated", 15)
    assert "neighbours" not in obs and obs["allowed"] == [1, 2] and obs["min_green"] == 15
    state = {m["name"]: m for m in env.get_state(iid)["movements"]}
    inter = env.intersection(iid)
    assert [p["id"] for p in obs["phases"]] == [p.index for p in inter.green_phases]
    for p in obs["phases"]:
        for m in p["movements"]:
            a, label = m["movement"].split()
            turn = {"straight": "go_straight", "cross-turn": "turn_left"}[label]
            s = state[f"{a}-{turn}"]
            assert (m["queue"], m["moving"], m["downstream"]) == (s["queue"], s["vehicles"] - s["queue"], s["out_queue"])
    # free turns are never listed
    assert all(FREE_TURN not in m["movement"] for p in obs["phases"] for m in p["movements"])
    # vehicle types cover every vehicle on the incoming lanes
    lane_veh = env.eng.get_lane_vehicles()
    assert sum(sum(c.values()) for c in obs["vehicle_types"].values()) == \
        sum(len(lane_veh[l]) for l in inter.incoming_lanes)
    assert sum(sum(c.values()) for c in obs["vehicle_types"].values()) > 0


def test_cooperative_neighbours(peak_env):
    env = peak_env
    iid = env.intersection_ids[0]
    obs = observe(env, iid, [1], "cooperative", 15)
    inter = env.intersection(iid)
    assert {n["id"] for n in obs["neighbours"]} == set(inter.neighbours)
    waiting = env.eng.get_lane_waiting_vehicle_count()
    for n in obs["neighbours"]:
        road_in = (set(env.intersection(n["id"]).outgoing_roads) & set(inter.incoming_roads)).pop()
        nbr = env.intersection(n["id"])
        assert n["queue_heading_to_us"] == sum(waiting[l] for m in nbr.movements if m.out_road == road_in
                                               for l in m.in_lanes)
        assert 0 <= n["of_which_green_now"] <= n["queue_heading_to_us"]
    text = render(obs)
    assert "Neighbouring intersections" in text and "Allowed phases: [1]" in text
    sys = messages(obs)[0]["content"]
    assert "15 s" in sys and "60 s" in sys and "5 s transition" in sys


def test_vehicle_types_named_and_unnamed(tmp_path):
    veh = {"length": 5, "width": 2, "maxPosAcc": 2, "maxNegAcc": 4.5, "usualPosAcc": 2, "usualNegAcc": 4.5,
           "minGap": 2.5, "maxSpeed": 11, "headwayTime": 1.5}
    bike = dict(veh, length=1.7)
    flow = tmp_path / "f.json"
    flow.write_text(json.dumps([{"vehicle": veh}, {"vehicle": bike}, {"vehicle": veh}]))
    vt = VehicleTypes(flow, {"car": veh, "bike": bike})
    assert vt.of("flow_1_0") == "bike" and vt.count(["flow_0_0", "flow_2_3", "flow_1_0"]) == {"car": 2, "bike": 1}
    assert VehicleTypes(flow).names == ["type_0", "type_1"]
    with pytest.raises(ValueError, match="match no named type"):
        VehicleTypes(flow, {"car": veh})
    with pytest.raises(ValueError, match="flow_"):
        vt.of("veh_3")
