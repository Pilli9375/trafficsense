import copy
import importlib.util

import pytest

from trafficsense.config import repo_root
from trafficsense.control import make_controller
from trafficsense.sim.env import TrafficEnv


def _script(name):
    spec = importlib.util.spec_from_file_location(name, repo_root() / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ranks_share_ties():
    from trafficsense.selection import ranks
    assert ranks({5: 10.0, 10: 12.0, 15: 10.0, 20: 30.0}) == {5: 1.5, 15: 1.5, 10: 3, 20: 4}


def test_select_mean_rank_then_relative_att_then_shorter():
    tune = _script("tune_maxpressure")
    # interval 10 is best in 3 of 4 scenarios
    att = {"a": {5: 100, 10: 90}, "b": {5: 100, 10: 90}, "c": {5: 100, 10: 90}, "d": {5: 50, 10: 200}}
    assert tune.select(att)["chosen_decision_interval"] == 10
    # equal mean rank: 5 loses by far less where it loses
    att = {"a": {5: 101, 10: 100}, "b": {5: 100, 10: 150}}
    assert tune.select(att)["chosen_decision_interval"] == 5
    # complete tie: shorter interval
    att = {"a": {5: 100, 10: 100}}
    assert tune.select(att)["chosen_decision_interval"] == 5


def test_maxpressure_5s_is_a_separate_config(cfg):
    c = copy.deepcopy(cfg)
    c["controllers"]["maxpressure"]["decision_interval"] = 20
    assert make_controller("maxpressure_5s", c).info()["decision_interval"] == 5
    assert make_controller("maxpressure_5s", c).info()["name"] == "maxpressure_5s"
    assert make_controller("maxpressure", c).info()["decision_interval"] == 20
    del c["controllers"]["maxpressure_5s"]
    with pytest.raises(KeyError, match="maxpressure_5s"):
        make_controller("maxpressure_5s", c)


@pytest.mark.parametrize("interval,shortest", [(5, 10), (10, 15), (15, 10), (20, 15), (30, 25)])
def test_maxpressure_shortest_green_on_decision_grid(cfg, synthetic_4x4, interval, shortest):
    """The docstring's claim: decisions on a fixed grid make the shortest possible green the
    first grid point at least min_green after the transition ends."""
    c = copy.deepcopy(cfg)
    c["controllers"]["maxpressure"]["decision_interval"] = interval
    env = TrafficEnv(c, "synthetic_4x4")
    ctl = make_controller("maxpressure", c)
    trace = {i: [] for i in env.intersection_ids}
    for _ in range(1800):
        ctl.act(env)
        env.step()
        for i in env.intersection_ids:
            trace[i].append(env.shown_phase(i))
    assert all(s.forced_switches == 0 for s in env.signals.values())
    greens = []
    for i, phases in trace.items():
        tr = env.intersection(i).transition_phase.index
        runs, run = [], 0
        for a, b in zip(phases, phases[1:]):
            run += 1
            if a != tr and b == tr:
                runs.append(run)
            if a == tr:
                run = 0
        greens += runs[1:]   # the first green starts at t=0, off the post-transition pattern
    assert greens and min(greens) == shortest


# ---- Webster FixedTime -------------------------------------------------------------------
from trafficsense.control.webster import split_greens, webster_cycle  # noqa: E402


@pytest.fixture(scope="module")
def indian_flows(cfg):
    p = repo_root() / cfg["scenarios"]["indian_2x2_peak"]["flow"].format(seed=0)
    if not p.is_file():
        pytest.fail(f"{p} missing; run scripts/generate_indian_flow.py --level all --seed 0 1 2")


def test_webster_cycle_formula_and_caps():
    c0, c = webster_cycle(0.5, 20.0, 60, 180)
    assert c0 == pytest.approx((1.5 * 20 + 5) / 0.5) and c == pytest.approx(70.0)
    assert webster_cycle(0.1, 20.0, 60, 180)[1] == 60          # C0 = 38.9 -> cycle_min
    assert webster_cycle(0.9, 20.0, 60, 180)[1] == 180         # C0 = 350 -> cycle_max
    assert webster_cycle(1.0, 20.0, 60, 180) == (None, 180.0)  # no finite optimum


def test_split_greens_proportional_to_y():
    g = split_greens({1: 0.3, 2: 0.1}, cycle=100, transition=5, startup_lost=2, min_green=10, max_green=90)
    # effective green 100 - 2*(5+2) = 86, split 3:1, plus the start-up loss back
    assert g[1] == pytest.approx(2 + 86 * 0.75) and g[2] == pytest.approx(2 + 86 * 0.25)
    assert sum(g.values()) + 2 * 5 == pytest.approx(100)


def test_split_greens_clips_and_redistributes():
    y = {1: 0.40, 2: 0.30, 3: 0.02, 4: 0.01}
    g = split_greens(y, cycle=120, transition=5, startup_lost=2, min_green=10, max_green=60)
    assert g[3] == 10 and g[4] == 10
    assert all(10 <= v <= 60 for v in g.values())
    assert sum(g.values()) + 4 * 5 == pytest.approx(120)               # cycle kept
    assert (g[1] - 2) / (g[2] - 2) == pytest.approx(0.40 / 0.30)       # free phases still by y
    g = split_greens({1: 0.9, 2: 0.0}, cycle=180, transition=5, startup_lost=2, min_green=10, max_green=60)
    assert g == {1: 60, 2: 10}                                          # both clipped: cycle shrinks
    assert split_greens({1: 0.0, 2: 0.0}, 60, 5, 2, 10, 60) == {1: 25.0, 2: 25.0}


def test_random_order_vehicles_are_seeded():
    import numpy as np
    from trafficsense.sim.capacity import random_order_vehicles
    types = {"a": {"share": 3, **{k: 1.0 for k in ("length", "minGap")}},
             "b": {"share": 1, **{k: 2.0 for k in ("length", "minGap")}}}
    v1 = random_order_vehicles(types, ("length", "minGap"), 2, 2000, np.random.default_rng(5))
    v2 = random_order_vehicles(types, ("length", "minGap"), 2, 2000, np.random.default_rng(5))
    assert v1 == v2 and len(v1) == 4000 and v1[-1][1] == 1999
    share_a = sum(1 for v, _ in v1 if v["length"] == 1.0) / len(v1)
    assert share_a == pytest.approx(0.75, abs=0.03)


def test_webster_controller_runs_its_plan(cfg, indian_flows):
    c = copy.deepcopy(cfg)
    c["controllers"]["fixedtime_webster"]["measurement_reps"] = 2   # speed; the plan logic is the same
    env = TrafficEnv(c, "indian_2x2_peak", seed=0)
    ctl = make_controller("fixedtime_webster", c)
    shown = {i: [] for i in env.intersection_ids}
    for _ in range(600):
        ctl.act(env)
        env.step()
        for i in env.intersection_ids:
            shown[i].append(env.shown_phase(i))
    assert all(s.forced_switches == 0 for s in env.signals.values())
    info = ctl.info()
    assert info["inputs"]["startup_lost_time_s"] > 0
    for iid, p in info["plans"].items():
        assert 0 < p["Y"] < 1 and 60 <= p["cycle_webster_s"] <= 180
        assert p["cycle_run_s"] == sum(p["greens_s"].values()) + 4 * 5
        tr = env.intersection(iid).transition_phase.index
        expected = []
        while len(expected) < 600:
            for ph in p["phases"]:
                expected += [ph] * p["greens_s"][ph] + [tr] * 5
        assert shown[iid] == expected[:600]


# ---- MaxPressure min_green (controller-level) ---------------------------------------------
def test_maxpressure_min_green_defaults_to_env_and_is_validated(cfg):
    c = copy.deepcopy(cfg)
    c["controllers"]["maxpressure"].pop("min_green", None)
    assert make_controller("maxpressure", c).info()["min_green"] == c["signal"]["min_green"]
    c["controllers"]["maxpressure"]["min_green"] = c["signal"]["min_green"] - 1
    with pytest.raises(ValueError, match="min_green"):
        make_controller("maxpressure", c)
    c["controllers"]["maxpressure"]["min_green"] = c["signal"]["max_green"]
    with pytest.raises(ValueError, match="min_green"):
        make_controller("maxpressure", c)


@pytest.mark.parametrize("min_green", [10, 15, 20, 25])
def test_maxpressure_shortest_green_equals_min_green_on_5s_grid(cfg, synthetic_4x4, min_green):
    """The sweep's premise: with a 5 s grid the shortest green is exactly the controller's min_green."""
    c = copy.deepcopy(cfg)
    c["controllers"]["maxpressure"]["decision_interval"] = 5
    c["controllers"]["maxpressure"]["min_green"] = min_green
    env = TrafficEnv(c, "synthetic_4x4")
    ctl = make_controller("maxpressure", c)
    trace = {i: [] for i in env.intersection_ids}
    for _ in range(1800):
        ctl.act(env)
        env.step()
        for i in env.intersection_ids:
            trace[i].append(env.shown_phase(i))
    assert all(s.forced_switches == 0 for s in env.signals.values())
    greens = []
    for i, phases in trace.items():
        tr = env.intersection(i).transition_phase.index
        runs, run = [], 0
        for a, b in zip(phases, phases[1:]):
            run += 1
            if a != tr and b == tr:
                runs.append(run)
            if a == tr:
                run = 0
        greens += runs[1:]
    assert greens and min(greens) == min_green


def test_min_green_sweep_uses_the_shared_rule():
    mg = _script("tune_maxpressure_min_green")
    assert mg.DECISION_INTERVAL == 5 and mg.MIN_GREENS == [10, 15, 20, 25]
    from trafficsense.selection import select
    att = {"a": {10: 101, 20: 100}, "b": {10: 100, 20: 150}}
    assert select(att)["chosen"] == 10
