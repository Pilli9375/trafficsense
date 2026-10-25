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
    assert bench.ARMS["hybrid"] == {"controller": "llm_guided_mp", "models": bench.ARMS["v2"]["models"]}
    assert {a: bench.ARMS[a]["controller"] for a in bench.FINAL_ARMS} == {
        "v3": "llm_v3", "hybrid_v3": "llm_guided_mp_v3", "guarded_v3": "llm_guarded_mp"}
    assert all(bench.ARMS[a]["models"] == bench.FITS_VRAM for a in bench.FINAL_ARMS)
    assert bench.EARLIER_ARMS == ["v1", "v2", "hybrid"]
    assert (bench.SCENARIO, bench.SEED, bench.STEPS) == ("indian_2x2_peak", 0, 600)
    assert (bench.DECISION_INTERVAL, bench.MIN_GREEN) == (5, 15)
    assert bench.BASELINES == ["maxpressure", "fixedtime_webster"]


def test_vram_sampler_starts_and_stops(bench, monkeypatch):
    from trafficsense.llm import gpu
    monkeypatch.setattr(gpu, "gpu_used_mib", lambda: 123)
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
    assert bench.arm_of({"controller": "llm_guided_mp", "controller_params": {"prompt": "guided"}}) == "hybrid"
    with pytest.raises(SystemExit):
        bench.arm_of({"controller": "llm_isolated", "controller_params": {"prompt": "v2"}})


def test_stored_benchmark_reproduces_phase_3a_selection(bench):
    """The v1 arm, read from the Phase 3a runs, gives the same (empty) selection as before."""
    b = bench.report(repo_root())
    v1 = b["arms"]["v1"]
    assert sorted(v1["models"]) == sorted(bench.MODELS) and v1["selection"]["eligible"] == []
    assert v1["models"]["qwen2.5:3b"]["latency_p95_s"] == pytest.approx(3.34, abs=0.005)


def test_decision_replay_reproduces_a_stored_run():
    import importlib.util
    spec = importlib.util.spec_from_file_location("analyze", repo_root() / "scripts" / "analyze_llm_decisions.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from trafficsense.config import load_config
    run = sorted((repo_root() / mod.RUNS).glob("*/decisions.jsonl"))[0].parent
    r = mod.replay(load_config("configs/default.yaml"), run)     # raises if the replay's ATT differs
    assert r["replay_att_matches"] and 0 <= r["keep_rate"] <= 1 and r["ok"] <= r["calls"]


def arms_with(bench, rows):
    """rows: {arm: {model: m(...)}}; every arm present, arms not given are complete and empty."""
    out = {}
    for a in bench.ARMS:
        models = rows.get(a, {})
        out[a] = {"models": models, "selection": bench.select(models, 4)}
    return out


def test_final_decision_takes_final_round_winner_even_if_worse_than_mp(bench):
    arms = arms_with(bench, {"v3": {"x": m(0.0, 1.0, 30.0, 120)}, "hybrid_v3": {"x": m(0.0, 1.0, 20.0, 110)},
                             "guarded_v3": {"x": m(0.0, 5.0, 12.0, 95)},       # best queue but too slow
                             "hybrid": {"x": m(0.0, 1.0, 5.0, 90)}})          # earlier round: not in the pool
    f = bench.final_decision(arms, {"queue_mean_per_intersection": 11.85}, 4)
    assert f["step"] == 1 and (f["arm"], f["model"], f["controller"]) == ("hybrid_v3", "x", "llm_guided_mp_v3")
    assert f["worse_than_maxpressure"] and f["decision_interval_s"] == 5


def test_final_decision_falls_back_to_every_round(bench):
    arms = arms_with(bench, {"v3": {"x": m(0.5, 1.0, 1.0, 1)}, "hybrid": {"x": m(0.0, 1.0, 26.6, 135)},
                             "v2": {"x": m(0.0, 1.5, 42.3, 181)}})
    f = bench.final_decision(arms, {"queue_mean_per_intersection": 11.85}, 4)
    assert f["step"] == 2 and f["chosen_model"] == "hybrid x"
    none = arms_with(bench, {"v3": {"x": m(0.5, 1.0, 1.0, 1)}})
    assert bench.final_decision(none, {"queue_mean_per_intersection": 1}, 4)["step"] == 3
    incomplete = dict(arms, v3={"models": {}, "selection": None})
    assert bench.final_decision(incomplete, {"queue_mean_per_intersection": 1}, 4) is None


def test_trial_run_writes_to_out_and_leaves_the_benchmark_alone(bench, tmp_path, monkeypatch):
    import json
    import sys
    calls = []

    def fake_run_model(cfg, arm, model, root, runs):
        out = root / runs / "trial"
        out.mkdir(parents=True)
        (out / "summary.json").write_text(json.dumps(
            {"provenance": {"llm": {"calls": 3, "failures": 0, "latency_p95_s": 1.0}}}))
        calls.append((arm, model, runs))
        return out

    def no_report(root):
        raise AssertionError("a trial run must not rebuild benchmark.json or the doc")

    monkeypatch.setattr(bench, "repo_root", lambda: tmp_path)
    monkeypatch.setattr(bench, "git_info", lambda: {"dirty": False})
    monkeypatch.setattr(bench, "load_runs", lambda root: {})
    monkeypatch.setattr(bench, "run_experiment", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no baselines")))
    monkeypatch.setattr(bench, "run_model", fake_run_model)
    monkeypatch.setattr(bench, "report", no_report)
    monkeypatch.setattr(sys, "argv", ["benchmark_llm.py", "--arm", "guarded_v3", "--models", "llama3.2:3b",
                                      "--out", "outputs/runs"])
    bench.main()
    assert calls == [("guarded_v3", "llama3.2:3b", bench.Path("outputs/runs"))]
    assert (tmp_path / "outputs/runs/trial/summary.json").is_file()
