"""LLMController with an injected fake client (in-process; no server, nothing written to outputs/)."""
import copy
import json

import pytest

from trafficsense.control import make_controller
from trafficsense.control.llm import LLMController
from trafficsense.experiment import run_experiment
from trafficsense.llm.client import ChatResult, LLMServerError, LLMTimeout, LLMUnavailable
from trafficsense.sim.env import TrafficEnv


class FakeClient:
    """`policy(messages, schema)` returns the answer text, or raises."""
    provider = "fake"
    host, endpoint, timeout_s, options, keep_alive = "fake://", "/api/chat", 1.0, {"temperature": 0}, "0"

    def __init__(self, policy):
        self.policy = policy
        self.calls = []

    def model_info(self):
        return {"name": "fake:1b", "digest": "d1g", "size_bytes": 1, "details": {}}

    def server_version(self):
        return "0.0-test"

    def chat(self, messages, schema):
        self.calls.append((messages, schema))
        return ChatResult(self.policy(messages, schema), "fake:1b", 0.5, 400, 20, 0.5, 0.0, "stop")


def lowest_allowed(messages, schema):
    return json.dumps({"phase": min(schema["properties"]["phase"]["enum"]), "reason": "test"})


@pytest.fixture
def lcfg(cfg):
    c = copy.deepcopy(cfg)
    c["llm"].update(model="fake:1b", decision_interval=5, min_green=15)
    return c


def run(cfg, policy, steps=300, name="llm_cooperative", scenario="indian_2x2_peak"):
    env = TrafficEnv(cfg, scenario, seed=0)
    ctl = LLMController(cfg, name, client=FakeClient(policy))
    for _ in range(steps):
        ctl.act(env)
        env.step()
    return env, ctl


def test_asks_only_when_a_switch_is_allowed_and_applies_the_answer(lcfg):
    env, ctl = run(lcfg, lowest_allowed)
    assert ctl.decisions and all(d["ok"] for d in ctl.decisions)
    for d in ctl.decisions:
        assert d["step"] % 5 == 0 and d["time_in_phase"] >= 15
        assert d["phase"] == min(d["allowed"])
    st = ctl.stats()
    assert st["calls"] == len(ctl.decisions) and st["failures"] == 0 and st["latency_mean_s"] == 0.5
    assert all(s.forced_switches == 0 for s in env.signals.values())


def test_cooperative_and_isolated_prompts_differ(lcfg):
    _, coop = run(lcfg, lowest_allowed, 100)
    _, iso = run(lcfg, lowest_allowed, 100, name="llm_isolated")
    assert "Neighbours:" in coop.client.calls[0][0][1]["content"]
    assert "Neighbours:" not in iso.client.calls[0][0][1]["content"]


def test_prompt_versions(lcfg):
    _, v1 = run(lcfg, lowest_allowed, 100, name="llm_v1")
    _, v2 = run(lcfg, lowest_allowed, 100)
    assert (v1.prompt, v2.prompt) == ("v1", "v2") and v1.info()["prompt"] == "v1"
    assert "Neighbouring intersections" in v1.client.calls[0][0][1]["content"]
    assert v1.client.calls[0][1]["properties"]["reason"]["maxLength"] == 200
    assert "phase: pressure, queue" in v2.client.calls[0][0][1]["content"]
    # the same decisions, so the same observations: only the rendering differs
    assert [d["phase"] for d in v1.decisions] == [d["phase"] for d in v2.decisions]
    sixteen = json.dumps({"phase": 1, "reason": " ".join(["w"] * 16)})
    _, v2 = run(lcfg, lambda m, s: sixteen, 30)
    assert v2.stats()["failures_by_type"] == {"reason_too_long": v2.stats()["calls"]}
    bad = copy.deepcopy(lcfg)
    bad["controllers"]["llm_cooperative"]["prompt"] = None
    with pytest.raises(ValueError, match="prompt"):
        LLMController(bad, "llm_cooperative", client=FakeClient(lowest_allowed))


def test_invalid_answers_keep_the_phase_and_are_counted(lcfg):
    lcfg["llm"]["max_consecutive_failures"] = 10_000
    answers = iter(["nonsense", '{"phase": 99, "reason": "x"}'] * 1000)
    env, ctl = run(lcfg, lambda m, s: next(answers), 200)
    assert ctl.decisions and not any(d["ok"] for d in ctl.decisions)
    assert all(d["phase"] == d["current_phase"] for d in ctl.decisions)
    st = ctl.stats()
    assert set(st["failures_by_type"]) == {"invalid_json", "phase_not_allowed"}
    assert st["failures"] == st["calls"] and st["failure_rate"] == 1.0
    # only the env's max-green rotation switches; the LLM never did
    assert all(s.switches == s.forced_switches for s in env.signals.values())


def test_timeouts_count_and_too_many_in_a_row_stop_the_run(lcfg):
    def timeout(m, s):
        raise LLMTimeout("slow")
    lcfg["llm"]["max_consecutive_failures"] = 3
    with pytest.raises(RuntimeError, match="3 LLM calls in a row failed"):
        run(lcfg, timeout, 300)


def test_server_errors_counted_unavailable_raises(lcfg):
    def err(m, s):
        raise LLMServerError("500")
    lcfg["llm"]["max_consecutive_failures"] = 10_000
    _, ctl = run(lcfg, err, 40)
    assert ctl.stats()["failures_by_type"] == {"server_error": ctl.stats()["calls"]}
    assert ctl.stats()["latency_n"] == 0

    def down(m, s):
        raise LLMUnavailable("refused")
    with pytest.raises(LLMUnavailable):
        run(lcfg, down, 40)


def test_current_phase_not_offered_near_max_green(lcfg):
    keep = lambda m, s: json.dumps({"phase": max(s["properties"]["phase"]["enum"]), "reason": "keep"})
    env, ctl = run(lcfg, keep, 400)
    near = [d for d in ctl.decisions if d["time_in_phase"] + 5 >= 60]
    assert near and all(d["current_phase"] not in d["allowed"] for d in near)
    assert all(s.forced_switches == 0 for s in env.signals.values())


def test_config_must_set_timing(cfg):
    with pytest.raises(KeyError, match="decision_interval"):
        LLMController(cfg, "llm_cooperative", client=FakeClient(lowest_allowed))
    c = copy.deepcopy(cfg)
    c["llm"].update(decision_interval=5, min_green=5)
    with pytest.raises(ValueError, match="min_green"):
        LLMController(c, "llm_cooperative", client=FakeClient(lowest_allowed))


def test_run_experiment_records_llm_provenance_and_decisions(lcfg, tmp_path):
    ctl = LLMController(lcfg, "llm_cooperative", client=FakeClient(lowest_allowed))
    out = run_experiment(lcfg, "indian_2x2_peak", "llm_cooperative", steps=120, seed=0, out_root=tmp_path, ctl=ctl)
    s = json.loads((out / "summary.json").read_text())["provenance"]
    assert s["model"] == "fake:1b" and s["provider"] == "fake"
    assert s["llm"]["model_digest"] == "d1g" and s["llm"]["calls"] > 0
    assert {"failures_by_type", "latency_mean_s", "latency_p95_s"} <= set(s["llm"])
    lines = (out / "decisions.jsonl").read_text().splitlines()
    assert len(lines) == s["llm"]["calls"]
    assert {"step", "intersection", "phase", "reason"} <= set(json.loads(lines[0]))


def test_registered_names(lcfg):
    with pytest.raises(Exception):
        make_controller("llm_cooperative", dict(lcfg, llm=dict(lcfg["llm"], host="http://127.0.0.1:9")))
