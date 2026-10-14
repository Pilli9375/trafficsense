import pytest

from trafficsense.sim.roadnet import _direction, load_roadnet


@pytest.fixture(scope="module")
def net(synthetic_4x4):
    return load_roadnet(synthetic_4x4["roadnet"])


def test_sixteen_intersections_nine_phases(net):
    assert len(net.intersections) == 16
    for inter in net.intersections.values():
        assert len(inter.phases) == 9


def test_phase0_is_the_only_transition(net):
    for inter in net.intersections.values():
        assert inter.transition_phase.index == 0
        assert inter.transition_phase.duration == 5
        assert [p.index for p in inter.green_phases] == list(range(1, 9))


def test_every_green_phase_serves_a_non_right_movement(net):
    for inter in net.intersections.values():
        for p in inter.green_phases:
            turns = {inter.movements[m].turn for m in p.movements}
            assert turns - {"turn_right"}, f"{inter.id} phase {p.index} serves only right turns"


def test_lanes_and_movements(net):
    inter = net.intersections["intersection_1_1"]
    assert len(inter.incoming_roads) == 4 and len(inter.outgoing_roads) == 4
    assert len(inter.incoming_lanes) == 12 and len(inter.outgoing_lanes) == 12
    assert len(inter.movements) == 12
    # every lane link starts on an incoming lane and ends on an outgoing lane
    for m in inter.movements:
        assert set(m.in_lanes) <= set(inter.incoming_lanes)
        assert set(m.out_lanes) <= set(inter.outgoing_lanes)
    # each approach has exactly one straight, left, right
    for a in "NESW":
        assert sorted(m.turn for m in inter.movements if m.approach == a) == \
            ["go_straight", "turn_left", "turn_right"]


def test_approach_from_geometry(net):
    # road_0_1_0 runs from x=-300 to the intersection at x=0: traffic comes from the west
    m = net.intersections["intersection_1_1"].movements[0]
    assert m.in_road == "road_0_1_0" and m.approach == "W"
    assert _direction(0, 1) == "N" and _direction(-1, 0) == "W" and _direction(0, -1) == "S"


def test_neighbours(net):
    corner = net.intersections["intersection_1_1"]
    assert corner.neighbours == {"intersection_2_1": "E", "intersection_1_2": "N"}
    centre = net.intersections["intersection_2_2"]
    assert len(centre.neighbours) == 4
    # symmetry
    for iid, inter in net.intersections.items():
        for nb in inter.neighbours:
            assert iid in net.intersections[nb].neighbours


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_roadnet(tmp_path / "nope.json")


def test_paired_phases_detected(net):
    for inter in net.intersections.values():
        paired = inter.paired_phases
        assert [p.index for p in paired] == [1, 2, 3, 4]
        names = [sorted(inter.movements[k].name for k in p.movements
                        if inter.movements[k].turn != "turn_right") for p in paired]
        assert names[0] == ["E-go_straight", "W-go_straight"]
        assert names[3] == ["N-turn_left", "S-turn_left"]
