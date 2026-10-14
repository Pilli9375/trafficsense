"""Capacity measurements on the simulator (trafficsense.sim.capacity)."""
import json

import pytest

from trafficsense.config import repo_root
from trafficsense.sim.capacity import (critical_flow_ratio, lane_demand, measure_discharge,
                                       measure_saturation, mixed_feed, straight_route, turn_route)
from trafficsense.sim.roadnet import load_roadnet


@pytest.fixture(scope="module")
def synth(synthetic_4x4):
    net = load_roadnet(synthetic_4x4["roadnet"])
    veh = json.loads(synthetic_4x4["flow"].read_text())[0]["vehicle"]
    return synthetic_4x4["roadnet"], net, veh


def test_entry_admission_is_cityflow_insertion_limit(synth):
    """5 m car + 2.5 m gap from standstill at 2 m/s^2 takes 3 steps -> 1200 veh/h."""
    rp, net, veh = synth
    s = measure_saturation(rp, net, straight_route(net, "road_2_5_3"), [(veh, 1.0)])
    assert s["measured_veh_per_hour"] == pytest.approx(1200, abs=10)


def test_stop_line_discharge_exceeds_admission(synth):
    rp, net, veh = synth
    d = measure_discharge(rp, net, straight_route(net, "road_2_5_3"), [(veh, 1.0)])
    assert d["queue_at_green"] > d["left_from_green_onset"]
    assert 1300 < d["saturation_flow_veh_per_hour"] < 1600


def test_discharge_rejects_right_turn(synth):
    rp, net, veh = synth
    with pytest.raises(ValueError):
        measure_discharge(rp, net, turn_route(net, "road_2_5_3", "turn_right"), [(veh, 1.0)])


def test_feed_intervals_below_one_second_rejected(synth):
    rp, net, veh = synth
    with pytest.raises(ValueError, match="intervals"):
        measure_saturation(rp, net, straight_route(net, "road_2_5_3"), [(veh, 0.5)])


def test_mixed_feed_splits_fast_types():
    types = {"a": {"share": 3, "x": 1}, "b": {"share": 1, "x": 2}}
    feed = mixed_feed(types, 4.0, ("x",))
    assert all(iv >= 1 for _, iv in feed)
    rate = {}
    for v, iv in feed:
        rate[v["x"]] = rate.get(v["x"], 0) + 1 / iv
    assert rate == {1.0: pytest.approx(3.0), 2.0: pytest.approx(1.0)}


def test_lane_demand_counts_every_hop(synth):
    _, net, veh = synth
    flows = [{"route": straight_route(net, "road_2_5_3")}]
    d = lane_demand(net, flows)
    hops = len(flows[0]["route"]) - 1
    assert sum(l["vehicles"] for i in d.values() for l in i.values()) == hops
    ratio = {i: {l: v["vehicles"] for l, v in lanes.items()} for i, lanes in d.items()}
    y = critical_flow_ratio(net, ratio)
    assert sum(v["Y"] for v in y.values()) == hops     # one straight hop per intersection on the route
