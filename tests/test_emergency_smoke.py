import importlib.util
import json

import pytest

from trafficsense.config import repo_root


@pytest.fixture(scope="module")
def smoke():
    spec = importlib.util.spec_from_file_location("run_emergency_smoke", repo_root() / "scripts" / "run_emergency_smoke.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def bench(tmp_path, chosen, models):
    p = tmp_path / "outputs/llm_benchmark/benchmark.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"arms": {"hybrid": {"selection": {"chosen_model": chosen}, "models": models}}}))
    return tmp_path


def test_hybrid_model_rule(smoke, tmp_path):
    m = {"a": {"failure_rate": 0.01, "latency_p95_s": 2.0}, "b": {"failure_rate": 0.0, "latency_p95_s": 5.0},
         "c": {"failure_rate": 0.0, "latency_p95_s": 4.0}}
    assert smoke.hybrid_model(bench(tmp_path / "x", "a", m))[0] == "a"
    assert smoke.hybrid_model(bench(tmp_path / "y", None, m))[0] == "c"


def test_design_is_pinned(smoke):
    assert (smoke.SCENARIO, smoke.SEEDS, smoke.STEPS) == ("indian_2x2_peak_amb", (0, 1, 2), 600)
    assert smoke.CONTROLLERS == ["maxpressure", "fixedtime_webster", "preemption_mp", "llm_guided_mp"]
    assert smoke.LLM_TIMING == {"decision_interval": 5, "min_green": 15}


def test_doc_quotes_the_ambulance_counts():
    """The counts are checked against the flow files in test_emergency.py::test_ambulance_counts."""
    doc = (repo_root() / "docs/emergency.md").read_text()
    assert "| 0 | 3 | none (first at t = 1670 s) |" in doc and "| 1 | 14 | one, t = 257 s" in doc
    assert "| 2 | 6 | one, t = 253 s" in doc


@pytest.fixture(scope="module")
def full():
    spec = importlib.util.spec_from_file_location("run_emergency_experiments",
                                                  repo_root() / "scripts" / "run_emergency_experiments.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_full_design_is_pinned(full):
    assert (full.SCENARIO, full.SEEDS, full.STEPS) == ("indian_2x2_peak_amb", (0, 1, 2, 3, 4), 3600)
    assert full.BASE_CONTROLLERS == ["maxpressure", "fixedtime_webster", "preemption_mp"]
    assert full.EXPLORATORY == "llm_guided_mp_v3"
    doc = (repo_root() / "docs/emergency.md").read_text()
    assert "37 ambulances, 29 of them **signal-relevant**" in doc and "| 4 | 8 | (full runs only) |" in doc


def test_full_llm_arm_comes_from_the_final_decision(full, tmp_path):
    p = tmp_path / "outputs/llm_benchmark/benchmark.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"final": {"chosen_model": "hybrid_v3 x", "controller": "llm_guided_mp_v3",
                                       "model": "x", "decision_interval_s": 5}}))
    assert full.llm_arm(tmp_path) == {"controller": "llm_guided_mp_v3", "model": "x", "decision_interval_s": 5}
    assert full.controllers(tmp_path)[-2:] == ["llm_guided_mp_v3", "llm_guided_mp_v3"]
    p.write_text(json.dumps({"final": {"chosen_model": None, "step": 3}}))
    assert full.controllers(tmp_path) == full.BASE_CONTROLLERS + [full.EXPLORATORY]
    p.write_text(json.dumps({"final": None}))
    with pytest.raises(SystemExit):
        full.llm_arm(tmp_path)


def test_full_report_pools_ambulances(full, tmp_path):
    """report() on synthetic run summaries (test fakes in tmp_path, never in outputs/)."""
    (tmp_path / "data/scenarios").mkdir(parents=True)
    (tmp_path / "data/scenarios/indian_2x2").symlink_to(repo_root() / "data/scenarios/indian_2x2")
    b = tmp_path / "outputs/llm_benchmark/benchmark.json"
    b.parent.mkdir(parents=True)
    b.write_text(json.dumps({"final": {"chosen_model": None, "step": 3}}))
    relevant = ["road_3_2_2", "road_2_2_2", "road_1_2_2"]
    free = ["road_3_2_2", "road_2_2_1"]
    for c, base in (("maxpressure", 100), ("fixedtime_webster", 120), ("preemption_mp", 80), (full.EXPLORATORY, 90)):
        for seed in full.SEEDS:
            d = tmp_path / full.RUNS / f"{c}_{seed}"
            d.mkdir(parents=True)
            veh = [{"vehicle": "a", "route": relevant, "finished": 1, "travel_time_s": base + seed, "stopped_s": 10},
                   {"vehicle": "b", "route": free, "finished": 1, "travel_time_s": 37, "stopped_s": 0},
                   {"vehicle": "c", "route": relevant, "finished": None, "travel_time_s": None, "stopped_s": 5}]
            (d / "summary.json").write_text(json.dumps({
                "provenance": {"controller": c, "seed": seed, "git_dirty": False, "scenario": full.SCENARIO,
                               "sim_steps": full.STEPS},
                "metrics": {"att": base, "queue_mean_per_intersection": 10.0, "throughput": 1000},
                "emergency": {"vehicles": veh}}))
    r = full.report(tmp_path)["controllers"]
    assert list(r) == full.BASE_CONTROLLERS + [full.EXPLORATORY]
    rel = r["maxpressure"]["ambulances_relevant"]
    assert (rel["n"], rel["finished"], rel["not_finished"]) == (10, 5, 5)
    assert rel["travel_time_mean_s"] == 102 and r["maxpressure"]["ambulances_all"]["n"] == 15
    v = r["fixedtime_webster"]["vs_preemption_relevant"]
    assert (v["n_paired"], v["mean_diff_s"], v["slower"], v["faster"]) == (5, 40, 5, 0)
    assert r["preemption_mp"]["att_s"] == [80, 0.0]
    assert "40.0 (0 faster, 5 slower of 5)" in full.tables(full.report(tmp_path))["emergency_full_ambulances"]
