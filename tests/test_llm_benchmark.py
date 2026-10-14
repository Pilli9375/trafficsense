import importlib.util

import pytest

from trafficsense.config import repo_root


@pytest.fixture(scope="module")
def bench():
    spec = importlib.util.spec_from_file_location("benchmark_llm", repo_root() / "scripts" / "benchmark_llm.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def m(fr, p95, q, att):
    return {"failure_rate": fr, "latency_p95_s": p95, "queue_mean_per_intersection": q, "att_s": att}


def test_select_filters_then_lowest_queue(bench):
    models = {"a": m(0.0, 2.0, 20.0, 120), "b": m(0.01, 2.9, 18.0, 130),
              "c": m(0.05, 1.0, 10.0, 100),    # too many failures
              "d": m(0.0, 3.5, 5.0, 90)}       # too slow
    s = bench.select(models, 4)
    assert s["eligible"] == ["a", "b"] and s["chosen_model"] == "b"
    assert s["decision_interval_s"] == 15          # 2.9 s x 4 = 11.6 s -> 15 s


def test_select_tie_break_and_interval_floor(bench):
    s = bench.select({"a": m(0, 1.0, 10.0, 120), "b": m(0, 1.0, 10.0, 110)}, 4)
    assert s["chosen_model"] == "b" and s["decision_interval_s"] == 5   # 4.0 s -> 5 s
    s = bench.select({"a": m(0, 0.2, 1.0, 1.0)}, 1)
    assert s["decision_interval_s"] == 5


def test_select_none_eligible(bench):
    s = bench.select({"a": m(0.02, 1.0, 1.0, 1.0), "b": m(0.0, 3.0, 1.0, 1.0)}, 4)   # both limits are strict
    assert s["eligible"] == [] and s["chosen_model"] is None and s["decision_interval_s"] is None


def test_benchmark_setup_is_pinned(bench):
    assert bench.MODELS == ["gemma3:4b", "gemma4:e4b", "llama3.2:3b", "qwen2.5:3b"]
    assert bench.ARMS["v1"] == {"controller": "llm_v1", "models": bench.MODELS}
    assert bench.ARMS["v2"] == {"controller": "llm_cooperative", "models": ["gemma4:e4b", "llama3.2:3b", "qwen2.5:3b"]}
    assert (bench.SCENARIO, bench.SEED, bench.STEPS) == ("indian_2x2_peak", 0, 600)
    assert (bench.DECISION_INTERVAL, bench.MIN_GREEN) == (5, 15)
    assert bench.BASELINES == ["maxpressure", "fixedtime_webster"]


def test_vram_sampler_starts_and_stops(bench, monkeypatch):
    monkeypatch.setattr(bench, "gpu_used_mib", lambda: 123)
    s = bench.VramSampler(period_s=0.01)
    s.start()
    import time
    time.sleep(0.05)
    samples = s.stop()
    assert samples and set(samples) == {123} and not s.is_alive()


def test_arm_of_runs(bench):
    assert bench.arm_of({"controller": "maxpressure", "controller_params": {}}) is None
    assert bench.arm_of({"controller": "llm_cooperative", "controller_params": {"mode": "cooperative"}}) == "v1"
    assert bench.arm_of({"controller": "llm_cooperative", "controller_params": {"prompt": "v2"}}) == "v2"
    assert bench.arm_of({"controller": "llm_v1", "controller_params": {"prompt": "v1"}}) == "v1"
    with pytest.raises(SystemExit):
        bench.arm_of({"controller": "llm_isolated", "controller_params": {"prompt": "v2"}})


def test_stored_benchmark_reproduces_phase_3a_selection(bench):
    """The v1 arm, read from the Phase 3a runs, gives the same (empty) selection as before."""
    b = bench.report(repo_root())
    v1 = b["arms"]["v1"]
    assert sorted(v1["models"]) == sorted(bench.MODELS) and v1["selection"]["eligible"] == []
    assert v1["models"]["qwen2.5:3b"]["latency_p95_s"] == pytest.approx(3.34, abs=0.005)
