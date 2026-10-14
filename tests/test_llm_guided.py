"""llm_guided_mp with an injected fake client (in-process; no server, nothing written to outputs/)."""
import copy
import itertools
import json
import re

import pytest

from trafficsense.control import make_controller
from trafficsense.control.guided import LLMGuidedMPController, mp_ranking
from trafficsense.control.maxpressure import choose_phase
from trafficsense.llm.client import LLMTimeout
from trafficsense.sim.env import TrafficEnv
from trafficsense.sim.metrics import MetricsTracker
from test_llm_controller import FakeClient


@pytest.fixture
def gcfg(cfg):
    c = copy.deepcopy(cfg)
    c["llm"].update(model="fake:1b", decision_interval=5, min_green=15)
    return c


def options_in_prompt(messages):
    """Option ids in the order the prompt lists them."""
    text = messages[1]["content"]
    block = text.split("(phase: pressure, queue):\n")[1].split("\nNeighbours:")[0]
    return [int(re.match(r"(\d+) ", l).group(1)) for l in block.splitlines()]


def first_option(messages, schema):
    return json.dumps({"phase": options_in_prompt(messages)[0], "reason": "top"})


def run(cfg, ctl, steps=600):
    env = TrafficEnv(cfg, "indian_2x2_peak", seed=0)
    m = MetricsTracker(env)
    for _ in range(steps):
        ctl.act(env)
        env.step()
        m.update()
    return env, m.summary()["network"]


def test_ranking_starts_with_maxpressure_choice():
    for vals in itertools.product([0, 3, 5], repeat=4):
        pr = dict(zip([1, 2, 3, 4], vals))
        for cur, excl, tb in itertools.product([1, 3], [False, True], ["keep_current", "lowest_index"]):
            r = mp_ranking(pr, cur, excl, tb)
            assert r[0] == choose_phase(pr, cur, excl, tb)
            assert [pr[p] for p in r] == sorted((pr[p] for p in r), reverse=True)
            assert (cur in r) != excl


@pytest.mark.parametrize("policy", ["agree", "fail"])
def test_agreeing_or_failing_llm_reproduces_maxpressure(gcfg, policy):
    """If the LLM always takes MaxPressure's top option, or always fails (fallback = top
    choice), the run is MaxPressure's, step for step."""
    def timeout(m, s):
        raise LLMTimeout("slow")
    gcfg["llm"]["max_consecutive_failures"] = 10_000
    ctl = LLMGuidedMPController(gcfg, client=FakeClient(first_option if policy == "agree" else timeout))
    env_g, g = run(gcfg, ctl)
    env_m, m = run(gcfg, make_controller("maxpressure", gcfg))
    assert (gcfg["controllers"]["maxpressure"]["decision_interval"], gcfg["controllers"]["maxpressure"]["min_green"]) \
        == (5, 15)
    assert g == m
    st = ctl.stats()
    assert st["calls"] > 0 and st["switches_requested"] == sum(s.switches for s in env_g.signals.values())
    if policy == "agree":
        assert st["mp_disagreements"] == 0 and st["mp_disagreement_rate"] == 0 and st["failures"] == 0
    else:
        assert st["failures"] == st["calls"] == st["mp_fallbacks"] and st["mp_disagreement_rate"] is None
        assert all(d["phase"] == d["mp_choice"] and d["disagrees_with_mp"] is None for d in ctl.decisions)


def test_options_are_top2_plus_current(gcfg):
    keep = lambda m, s: json.dumps({"phase": options_in_prompt(m)[-1], "reason": "last option"})
    ctl = LLMGuidedMPController(gcfg, client=FakeClient(keep))
    run(gcfg, ctl, 400)
    for d, (msgs, schema) in zip(ctl.decisions, ctl.client.calls):
        listed = options_in_prompt(msgs)
        near_max = d["time_in_phase"] + 5 >= 60
        assert listed[:2] == d["mp_ranking"][:2] and d["mp_choice"] == d["mp_ranking"][0]
        expect = d["mp_ranking"][:2] + ([] if near_max or d["current_phase"] in d["mp_ranking"][:2]
                                        else [d["current_phase"]])
        assert listed == expect and sorted(listed) == schema["properties"]["phase"]["enum"] == d["allowed"]
        assert ("(keep current)" in msgs[1]["content"]) == (d["current_phase"] in listed)
    st = ctl.stats()
    assert st["mp_disagreements"] > 0
    assert st["mp_disagreements"] == st["mp_disagreements_kept_current"] + st["mp_disagreements_chose_lower_ranked"]
    assert st["mp_disagreements"] == sum(1 for d in ctl.decisions if d["phase"] != d["mp_choice"])


def test_guided_prompt(gcfg):
    ctl = LLMGuidedMPController(gcfg, client=FakeClient(first_option))
    run(gcfg, ctl, 100)
    sys, user = ctl.client.calls[0][0]
    assert "MaxPressure" in sys["content"] and "at most 15 words" in sys["content"] and "waste" not in sys["content"]
    assert "Neighbours:" in user["content"]
    assert ctl.info()["prompt"] == "guided" and ctl.info()["options"] == 2


def test_config_checked(gcfg):
    bad = copy.deepcopy(gcfg)
    bad["controllers"]["llm_guided_mp"]["options"] = 1
    with pytest.raises(ValueError, match="options"):
        LLMGuidedMPController(bad, client=FakeClient(first_option))
    bad = copy.deepcopy(gcfg)
    bad["controllers"]["llm_guided_mp"]["prompt"] = "v2"
    with pytest.raises(ValueError, match="prompt"):
        LLMGuidedMPController(bad, client=FakeClient(first_option))


@pytest.fixture
def gdcfg(gcfg):
    gcfg["controllers"]["llm_guarded_mp"]["guard_ratio"] = 0.8
    return gcfg


def test_guard_threshold():
    from trafficsense.control.guided import LLMGuardedMPController
    g = LLMGuardedMPController.__new__(LLMGuardedMPController)
    g.guard_ratio = 0.8
    obs = lambda pr: {"phases": [{"id": i, "pressure": v} for i, v in pr.items()]}
    for pr, llm, top, applied in [({1: 10, 2: 8, 3: 7}, 2, 1, 2),     # 8 >= 0.8 x 10
                                  ({1: 10, 2: 8, 3: 7}, 3, 1, 1),     # 7 < 8: overridden
                                  ({1: 0, 2: 0, 3: -1}, 2, 1, 2),     # top 0: only pressure >= 0
                                  ({1: 0, 2: 0, 3: -1}, 3, 1, 1),
                                  ({1: -5, 2: -6, 3: -7}, 2, 1, 2),   # top < 0: >= -6 accepted
                                  ({1: -5, 2: -6, 3: -7}, 3, 1, 1)]:
        rec = {}
        assert g._accept(llm, top, obs(pr), [], rec) == applied
        assert rec["guard_override"] == (applied != llm)
    rec = {}
    assert g._accept(3, 1, obs({1: 10, 2: 8, 3: 0}), [{"phases": [3]}], rec) == 3   # serves an ambulance
    assert rec["guard_ambulance_exempt"] and not rec["guard_override"]


def test_guarded_overrides_low_pressure_answers(gdcfg):
    from trafficsense.control.guided import LLMGuardedMPController
    last = lambda m, s: json.dumps({"phase": options_in_prompt(m)[-1], "reason": "last option"})
    ctl = LLMGuardedMPController(gdcfg, client=FakeClient(last))
    run(gdcfg, ctl, 400)
    st = ctl.stats()
    assert st["guard_overrides"] > 0 and st["guard_override_rate"] == st["guard_overrides"] / st["ok"]
    for d in ctl.decisions:
        assert d["phase"] == (d["mp_choice"] if d["guard_override"] else d["llm_phase"])
        assert d["guard_override"] == (d["guard_llm_pressure"] < d["guard_threshold"])
    assert st["applied_differs_from_mp"] == sum(1 for d in ctl.decisions if d["phase"] != d["mp_choice"])


def test_guarded_with_agreeing_llm_is_maxpressure(gdcfg):
    from trafficsense.control.guided import LLMGuardedMPController
    ctl = LLMGuardedMPController(gdcfg, client=FakeClient(first_option))
    _, g = run(gdcfg, ctl)
    _, m = run(gdcfg, make_controller("maxpressure", gdcfg))
    assert g == m and ctl.stats()["guard_overrides"] == 0
    bad = copy.deepcopy(gdcfg)
    bad["controllers"]["llm_guarded_mp"]["guard_ratio"] = 1.5
    with pytest.raises(ValueError, match="guard_ratio"):
        LLMGuardedMPController(bad, client=FakeClient(first_option))
