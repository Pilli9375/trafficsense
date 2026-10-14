import pytest

from trafficsense.control import make_controller
from trafficsense.control.maxpressure import choose_phase, phase_pressures
from trafficsense.sim.env import TrafficEnv
from trafficsense.sim.roadnet import load_roadnet

IID = "intersection_2_2"


def _run(cfg, name, steps):
    env = TrafficEnv(cfg, "synthetic_4x4")
    ctl = make_controller(name, cfg)
    trace = []
    for _ in range(steps):
        ctl.act(env)
        trace.append({i: (env.current_phase(i), env.time_in_phase(i)) for i in env.intersection_ids})
        env.step()
    return env, trace


def test_fixedtime_cycles_paired_phases(cfg, synthetic_4x4):
    env, trace = _run(cfg, "fixedtime", 2 * 4 * 35)
    phases = [t[IID][0] for t in trace]
    expected = []
    for p in range(1, 5):
        expected += [p] * 30 + [0] * 5
    assert phases == expected * 2
    assert all(s.forced_switches == 0 for s in env.signals.values())


def test_fixedtime_all_phases_cycle(cfg, synthetic_4x4):
    env, trace = _run(cfg, "fixedtime_all_phases", 2 * 8 * 35)
    phases = [t[IID][0] for t in trace]
    expected = []
    for p in range(1, 9):
        expected += [p] * 30 + [0] * 5
    assert phases[:280] == expected
    assert phases[280:560] == expected
    assert all(s.forced_switches == 0 for s in env.signals.values())


def test_maxpressure_respects_min_green_and_never_forced(cfg, synthetic_4x4):
    env, trace = _run(cfg, "maxpressure", 1200)
    assert all(s.forced_switches == 0 for s in env.signals.values())
    assert sum(s.switches for s in env.signals.values()) > 0
    for iid in env.intersection_ids:
        greens, run, prev = [], 0, None
        for ph, _ in (t[iid] for t in trace):
            if ph != prev and prev not in (None, 0):
                greens.append(run)
            run = run + 1 if ph == prev else 1
            prev = ph
        assert greens and min(greens) >= cfg["signal"]["min_green"]
        assert max(greens) <= cfg["signal"]["max_green"]


def test_phase_pressures_and_choice(synthetic_4x4):
    inter = load_roadnet(synthetic_4x4["roadnet"]).intersections[IID]
    movements = [{"index": m.index, "queue": 0, "out_queue": 0} for m in inter.movements]
    # phase 2 serves movements 4 and 11 (N-S straight); put queues there
    movements[4]["queue"] = 7
    movements[11]["queue"] = 3
    movements[11]["out_queue"] = 2
    p = phase_pressures(inter, {"movements": movements})
    assert p[2] == 8 and p[1] == 0
    assert choose_phase(p, current=1, exclude_current=False) == 2
    assert choose_phase({1: 5, 2: 5, 3: 1}, current=2, exclude_current=False) == 2
    assert choose_phase({1: 5, 2: 5, 3: 1}, current=3, exclude_current=False) == 1
    assert choose_phase({1: 5, 2: 3}, current=1, exclude_current=True) == 2


def test_bad_controller_config(cfg):
    with pytest.raises(KeyError):
        make_controller("nope", cfg)
    bad = {**cfg, "controllers": {"fixedtime": {"green_time": 90, "phases": "paired"}}}
    with pytest.raises(ValueError):
        make_controller("fixedtime", bad)
    bad = {**cfg, "controllers": {"fixedtime": {"green_time": 30, "phases": "some"}}}
    with pytest.raises(ValueError):
        make_controller("fixedtime", bad)


def test_fixedtime_decision_interval(cfg, synthetic_4x4):
    # Only switches on a 30 s grid: first green 30 s, later greens 55 s (25 s < 30 at the
    # first check after the 5 s transition), as in CoLLMLight's 30 s action steps.
    c = {**cfg, "controllers": {"fixedtime": {"green_time": 30, "phases": "paired",
                                              "decision_interval": 30}}}
    _, trace = _run(c, "fixedtime", 300)
    phases = [t[IID][0] for t in trace]
    assert phases == [1] * 30 + [0] * 5 + [2] * 55 + [0] * 5 + [3] * 55 + [0] * 5 + [4] * 55 + [0] * 5 + [1] * 55 + [0] * 5 + [2] * 25


def test_maxpressure_tie_break_and_phase_set(synthetic_4x4):
    assert choose_phase({1: 5, 2: 5}, current=2, exclude_current=False, tie_break="lowest_index") == 1
    inter = load_roadnet(synthetic_4x4["roadnet"]).intersections[IID]
    movements = [{"index": m.index, "queue": 0, "out_queue": 0} for m in inter.movements]
    assert set(phase_pressures(inter, {"movements": movements}, [1, 2, 3, 4])) == {1, 2, 3, 4}


def test_lane_change_reaches_engine(cfg, synthetic_4x4):
    on = {**cfg, "sim": {**cfg["sim"], "lane_change": True}}
    assert TrafficEnv(on, "synthetic_4x4").engine_config["laneChange"] is True
    assert TrafficEnv(cfg, "synthetic_4x4").engine_config["laneChange"] is False
