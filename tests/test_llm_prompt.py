import hashlib
import json
import re

import pytest

from trafficsense.control.maxpressure import phase_pressures
from trafficsense.llm import prompt
from trafficsense.llm.prompt import (FREE_TURN, InvalidResponse, messages, observe, parse_response, render,
                                     render_v2, response_schema)
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
        parse_response(text, [1, 2, 3], 25)
    assert e.value.failure_type == ftype


def test_parse_response_ok():
    assert parse_response('{"phase": 2, "reason": " ' + " ".join(["w"] * 25) + ' "}', [2], 25) == (2, " ".join(["w"] * 25))
    with pytest.raises(InvalidResponse, match="max 15"):
        parse_response('{"phase": 2, "reason": "' + " ".join(["w"] * 16) + '"}', [2], prompt.MAX_REASON_WORDS["v2"])


def test_schema_restricts_phase_to_allowed():
    s = response_schema([3, 1], "v1")
    assert s["properties"]["phase"]["enum"] == [1, 3] and s["required"] == ["phase", "reason"]
    assert s["properties"]["reason"]["maxLength"] == 200                 # as in Phase 3a
    assert response_schema([1], "v2")["properties"]["reason"]["maxLength"] == 120


def test_v1_prompt_is_unchanged():
    """v1 is kept for the record: its system prompt is the one the Phase 3a benchmark used."""
    assert hashlib.sha256(prompt.SYSTEM_PROMPT.encode()).hexdigest() == \
        "e770540c61684046bae0bb09f444c37ae02d135ed9c5700c09e40e379c61f552"
    assert prompt.MAX_REASON_WORDS["v1"] == 25


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
    sys = messages(obs, "v1")[0]["content"]
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


def test_v2_pressure_matches_maxpressure_ranking(peak_env):
    env = peak_env
    for iid in env.intersection_ids:
        obs = observe(env, iid, [1, 2], "cooperative", 15)
        mp = phase_pressures(env.intersection(iid), env.get_state(iid))
        # free turns run in every green phase: prompt pressure = MaxPressure's minus a constant
        diffs = {mp[p["id"]] - p["pressure"] for p in obs["phases"]}
        assert len(diffs) == 1
        for p in obs["phases"]:
            assert p["queue"] == sum(m["queue"] for m in p["movements"])
            assert p["pressure"] == sum(m["queue"] - m["downstream"] for m in p["movements"])


def test_v2_render(peak_env):
    env = peak_env
    iid = env.intersection_ids[0]
    obs = observe(env, iid, [1, 2, 3, 4, 6, 7, 8], "cooperative", 15)
    text = render_v2(obs)
    for p in obs["phases"]:
        assert f"{p['id']} {p['label']}: {p['pressure']}, {p['queue']}" in text
    assert text.endswith("Allowed: all except 5") and "Neighbours:" in text
    assert "Neighbours:" not in render_v2(observe(env, iid, [1, 2], "isolated", 15))
    assert render_v2(observe(env, iid, list(range(1, 9)), "isolated", 15)).endswith("Allowed: all")
    assert render_v2(observe(env, iid, [2, 7], "isolated", 15)).endswith("Allowed: 2, 7")
    sys = messages(obs, "v2")[0]["content"]
    assert "15 to 60 s" in sys and "5 s transition" in sys and "at most 15 words" in sys
    assert "waste" not in sys                      # no advice against switching
    assert {p["label"] for p in obs["phases"]} == {"W+E straight", "S+N straight", "W+E cross-turn", "S+N cross-turn",
                                                   "W only", "E only", "S only", "N only"}
    with pytest.raises(ValueError, match="version"):
        messages(obs, "v3")


def test_v2_is_much_shorter_than_v1(peak_env):
    """Server token counts are measured in the benchmark (target < 300); here a word-count proxy."""
    obs = observe(peak_env, peak_env.intersection_ids[0], list(range(1, 9)), "cooperative", 15)
    words = {v: sum(len(re.findall(r"\w+|[^\w\s]", m["content"])) for m in messages(obs, v)) for v in ("v1", "v2")}
    assert words["v2"] < 0.55 * words["v1"]
