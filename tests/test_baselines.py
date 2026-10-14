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
    tune = _script("tune_maxpressure")
    assert tune.ranks({5: 10.0, 10: 12.0, 15: 10.0, 20: 30.0}) == {5: 1.5, 15: 1.5, 10: 3, 20: 4}


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
