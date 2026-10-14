import json

import pytest

from trafficsense.sim.env import TrafficEnv

IID = "intersection_2_2"


@pytest.fixture
def env(cfg, synthetic_4x4):
    return TrafficEnv(cfg, "synthetic_4x4")


def test_states_differ_between_intersections(env):
    for _ in range(300):
        env.step()
    states = [json.dumps(env.get_state(i)["movements"]) for i in env.intersection_ids]
    assert len(set(states)) > 1
    assert sum(m["vehicles"] for i in env.intersection_ids for m in env.get_state(i)["movements"]) > 0


def test_state_uses_only_own_lanes(env):
    for _ in range(200):
        env.step()
    inter = env.intersection(IID)
    waiting = env.eng.get_lane_waiting_vehicle_count()
    state = env.get_state(IID)
    assert sum(m["queue"] for m in state["movements"]) == sum(waiting[l] for l in inter.incoming_lanes)


def test_starts_on_first_green(env):
    for iid in env.intersection_ids:
        assert env.current_phase(iid) == 1
        assert not env.in_transition(iid)


def test_transition_inserted_with_roadnet_duration(env):
    assert env.transition_time[IID] == 5
    for _ in range(env.min_green):
        env.step()
    assert env.request_phase(IID, 3) is True
    seen = []
    for _ in range(6):
        seen.append(env.current_phase(IID))
        env.step()
    assert seen == [0, 0, 0, 0, 0, 3]
    assert env.time_in_phase(IID) == 1


def test_shown_phase_is_the_phase_during_the_step(cfg, synthetic_4x4):
    """current_phase() after a step is the phase for the NEXT step; shown_phase() is the one
    the engine used. A transition is shown for exactly transition_time steps."""
    e = TrafficEnv(cfg, "synthetic_4x4")
    for _ in range(e.min_green):
        e.step()
    e.request_phase(IID, 3)
    shown, after = [], []
    for _ in range(7):
        e.step()
        shown.append(e.shown_phase(IID))
        after.append(e.current_phase(IID))
    assert shown == [0, 0, 0, 0, 0, 3, 3]
    assert after == [0, 0, 0, 0, 3, 3, 3]


def test_metrics_rows_record_full_transition(cfg, synthetic_4x4):
    from trafficsense.sim.metrics import MetricsTracker
    e = TrafficEnv(cfg, "synthetic_4x4")
    m = MetricsTracker(e)
    for k in range(40):
        if k == e.min_green:
            e.request_phase(IID, 3)
        e.step()
        m.update()
    rows = [r for r in m.rows if r["intersection"] == IID]
    assert sum(r["in_transition"] for r in rows) == e.transition_time[IID]


def test_min_green_enforced(env):
    for _ in range(env.min_green - 1):
        env.step()
    assert not env.can_switch(IID)
    with pytest.raises(RuntimeError):
        env.request_phase(IID, 2)
    env.step()
    assert env.can_switch(IID)


def test_requesting_current_phase_is_noop(env):
    for _ in range(env.min_green):
        env.step()
    assert env.request_phase(IID, 1) is False
    assert not env.in_transition(IID)


def test_transition_phase_cannot_be_requested(env):
    for _ in range(env.min_green):
        env.step()
    with pytest.raises(ValueError):
        env.request_phase(IID, 0)


def test_request_during_transition_raises(env):
    for _ in range(env.min_green):
        env.step()
    env.request_phase(IID, 2)
    with pytest.raises(RuntimeError):
        env.request_phase(IID, 3)


def test_max_green_forces_next_phase(env):
    for _ in range(env.max_green - 1):
        env.step()
    assert not env.in_transition(IID)
    env.step()
    assert env.in_transition(IID)
    assert env.signals[IID].green_phase == 2
    assert env.signals[IID].forced_switches == 1


def test_bad_timing_config_raises(cfg, synthetic_4x4):
    bad = {**cfg, "signal": {"min_green": 30, "max_green": 10}}
    with pytest.raises(ValueError):
        TrafficEnv(bad, "synthetic_4x4")
    missing = {**cfg, "signal": {"max_green": 60}}
    with pytest.raises(KeyError):
        TrafficEnv(missing, "synthetic_4x4")


def test_unknown_scenario_raises(cfg):
    with pytest.raises(KeyError):
        TrafficEnv(cfg, "nope")
