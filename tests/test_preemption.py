"""The preemption baseline and llm_guided_mp's ambulance options (fake LLM client injected
in-process; no server)."""
import copy
import json

from trafficsense.control import make_controller
from trafficsense.control.guided import LLMGuidedMPController
from test_emergency import AMB, run
from test_llm_controller import FakeClient


def test_preemption_equals_maxpressure_without_ambulances(cfg):
    _, a = run(cfg, "indian_2x2_peak", make_controller("preemption_mp", cfg), 600, 0)
    _, b = run(cfg, "indian_2x2_peak", make_controller("maxpressure", cfg), 600, 0)
    assert a == b


def test_preemption_gives_the_ambulance_green(cfg):
    ctl = make_controller("preemption_mp", cfg)
    env, _ = run(cfg, AMB, ctl, 600, 2)
    assert ctl.log and ctl.provenance()["controller_stats"]["preemption_decisions"] == len(ctl.log)
    for x in ctl.log:
        assert x["distance_m"] <= cfg["emergency"]["detection_range_m"]
        mv = next(m for m in env.intersection(x["intersection"]).movements
                  if m.approach == x["approach"] and m.turn == x["turn"])
        assert mv.index in env.intersection(x["intersection"]).phases[x["phase"]].movements


def test_guided_offers_a_phase_for_the_ambulance(cfg):
    c = copy.deepcopy(cfg)
    c["llm"].update(model="fake:1b", decision_interval=5, min_green=15)
    first = lambda m, s: json.dumps({"phase": s["properties"]["phase"]["enum"][0], "reason": "x"})
    ctl = LLMGuidedMPController(c, client=FakeClient(first))
    run(c, AMB, ctl, 600, 2)
    amb = [(d, msgs) for d, (msgs, _) in zip(ctl.decisions, ctl.client.calls) if "ambulances" in d]
    assert amb
    for d, msgs in amb:
        assert d["ambulances"][0]["phases"][0] in d["allowed"]
        assert "Ambulances within 150 m:" in msgs[1]["content"]
        assert "Ambulances, if listed" in msgs[0]["content"]
        assert d["serves_nearest_ambulance"] == (d["phase"] in d["ambulances"][0]["phases"])
    assert ctl.stats()["ambulance_decisions"] == len(amb)
    # the normal scenario's system prompt has no ambulance sentence
    ctl2 = LLMGuidedMPController(c, client=FakeClient(first))
    run(c, "indian_2x2_peak", ctl2, 100, 1)
    assert "Ambulance" not in ctl2.client.calls[0][0][0]["content"]
