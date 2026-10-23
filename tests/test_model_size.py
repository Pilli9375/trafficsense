"""The pre-registered model-size study (scripts/run_model_size.py): plan, config merge, resume."""
import importlib.util
import json

import pytest

from trafficsense.config import repo_root


@pytest.fixture(scope="module")
def ms():
    spec = importlib.util.spec_from_file_location("run_model_size", repo_root() / "scripts" / "run_model_size.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_plan_is_pinned(ms):
    jobs = ms.jobs()
    assert len(jobs) == 34 and len({ms.job_key(j) for j in jobs}) == 34
    assert ms.CONTROLLER == "llm_guided_mp_v3" and (ms.DECISION_INTERVAL, ms.MIN_GREEN) == (5, 15)
    assert ms.BENCH == ("indian_2x2_peak", 0, 600) and ms.FULL_STEPS == 3600
    bench = [j["model"] for j in jobs if j["step"] == "bench"]
    assert bench == ["llama3.1:8b", "nvidia/nemotron-3-ultra-550b-a55b"]
    full = {m: sum(j["model"] == m for j in jobs if j["step"] == "full") for m in ms.MODELS}
    assert full == {"qwen2.5:3b": 8, "llama3.2:3b": 8, "gemma4:e4b": 0, "llama3.1:8b": 8,
                    "nvidia/nemotron-3-ultra-550b-a55b": 8}
    steps = [j["step"] for j in jobs]
    assert steps == sorted(steps, key=["bench", "full"].index)                   # benchmarks first
    hosted = [i for i, j in enumerate(jobs) if j["step"] == "full" and j["model"] == ms.HOSTED]
    assert hosted == list(range(len(jobs) - 8, len(jobs)))                        # hosted full runs last
    assert {(j["scenario"], j["seed"]) for j in jobs if j["step"] == "full"} == \
        {("indian_2x2_peak", s) for s in range(3)} | {("indian_2x2_peak_amb", s) for s in range(5)}


def test_hosted_run_cfg_merges_and_pins_the_model(ms, cfg):
    c = ms.run_cfg(cfg, ms.HOSTED, 2)
    l = c["llm"]
    assert l["provider"] == "nvidia_nim" and l["model"] == ms.HOSTED and l["seed"] == 2
    assert (l["decision_interval"], l["min_green"]) == (5, 15)
    assert l["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}
    assert l["structured_output"] == "json_schema" and l["temperature"] == 0
    assert l["max_consecutive_failures"] == cfg["llm"]["max_consecutive_failures"]
    assert cfg["llm"]["provider"] == "ollama"                                    # the default is not touched
    local = ms.run_cfg(cfg, "llama3.1:8b", 1)["llm"]
    assert local["provider"] == "ollama" and local["model"] == "llama3.1:8b" and local["seed"] == 1
    bad = json.loads(json.dumps(cfg))
    bad["llm_hosted"]["nvidia_nim"]["model"] = "someone/else"
    with pytest.raises(SystemExit, match="plan says"):
        ms.run_cfg(bad, ms.HOSTED, 0)


def test_resume_keys_on_requested_model(ms, tmp_path):
    def run(name, files, model, served=None, **pv):
        d = tmp_path / ms.RUNS / name
        d.mkdir(parents=True)
        p = dict(scenario="indian_2x2_peak", controller="llm_guided_mp_v3", seed=0, sim_steps=3600,
                 git_dirty=False, model=served or model,
                 controller_params={"client": {"provider": "x", "model": model}}) | pv
        if "summary" in files:
            (d / "summary.json").write_text(json.dumps({"provenance": p}))
        if "metrics" in files:
            (d / "metrics.csv").write_text("x\n")
    run("a", ["summary", "metrics"], ms.HOSTED, served="nvidia/renamed-upstream")   # served id drifted
    run("b", ["metrics"], "llama3.1:8b")                                           # interrupted
    run("c", ["summary", "metrics"], "llama3.1:8b", git_dirty=True)                # not citable
    run("d", ["summary", "metrics"], "llama3.1:8b", controller="llm_guarded_mp")   # other controller
    done = ms.complete_runs(tmp_path)
    assert set(done) == {("indian_2x2_peak", 0, 3600, ms.HOSTED)}
    run("e", ["summary", "metrics"], ms.HOSTED)
    with pytest.raises(SystemExit, match="Two complete runs"):
        ms.complete_runs(tmp_path)


def test_study_runs_are_invisible_to_the_main_results(ms):
    full = importlib.util.spec_from_file_location("rf", repo_root() / "scripts" / "run_full_experiments.py")
    mod = importlib.util.module_from_spec(full)
    full.loader.exec_module(mod)
    assert ms.RUNS not in (mod.FULL_RUNS, mod.EMERGENCY_RUNS)


@pytest.fixture(scope="module")
def mk():
    spec = importlib.util.spec_from_file_location("make_model_size", repo_root() / "scripts" / "make_model_size.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_report_covers_every_model_and_labels_it_exploratory(mk, ms):
    assert list(mk.SIZES) == list(ms.MODELS)                       # one size per model, same order
    assert [mk.SIZES[m]["total_b"] for m in ms.MODELS] == sorted(mk.SIZES[m]["total_b"] for m in ms.MODELS)
    doc = (repo_root() / mk.DOC).read_text()
    assert "exploratory, added after the main results" in doc.lower()
    assert "<!-- BEGIN:model_size_bench -->" in doc


def test_bench_table_marks_models_not_run(mk):
    b = {"sizes": mk.SIZES, "bench": {"models": {}, "not_run": ["llama3.1:8b"],
                                       "maxpressure": {"att_s": 92.5, "queue_mean_per_intersection": 11.85}}}
    t = mk.tables(b)["model_size_bench"]
    rows = t.splitlines()
    assert len({r.count("|") for r in rows}) == 1                  # every row has the header's columns
    assert "`llama3.1:8b` | not run yet" in t and "MaxPressure (baseline)" in t


def write_run(d, decisions, llm):
    d.mkdir(parents=True)
    (d / "decisions.jsonl").write_text("".join(json.dumps(x) + "\n" for x in decisions))
    return llm


def dec(ok, llm_phase, mp_choice, phase=None, retries=()):
    return {"ok": ok, "llm_phase": llm_phase if ok else None, "mp_choice": mp_choice,
            "phase": phase if phase is not None else (llm_phase if ok else mp_choice),
            "allowed": [1, 2, 3], "mp_pressures": {"1": 5, "2": 2, "3": 5}, "retries": list(retries)}


def test_decision_counts_follow_pressure_fallback_and_summary_agreement(mk, tmp_path):
    ds = [dec(True, 1, 1), dec(True, 3, 1, retries=["429"]), dec(True, 2, 1), dec(False, None, 3, retries=["429"] * 5)]
    l = {"calls": 4, "failures": 1, "mp_disagreement_rate": 2 / 3, "retries": 6}
    write_run(tmp_path / "r", ds, l)
    n = mk.decision_counts(tmp_path / "r", l)
    # phases 1 and 3 tie at the highest pressure: both count as following pressure
    assert (n["ok"], n["highest"], n["differs"], n["retries"], n["calls_with_retries"]) == (3, 2, 2, 6, 2)
    with pytest.raises(SystemExit, match="disagrees"):
        mk.decision_counts(tmp_path / "r", dict(l, retries=5))
    write_run(tmp_path / "bad", [dec(False, None, 3, phase=2)], {})
    with pytest.raises(SystemExit, match="fall back"):
        mk.decision_counts(tmp_path / "bad", {"calls": 1, "failures": 1, "mp_disagreement_rate": 0})


def fake_full(mk, ms):
    """A full-run block in which only gemma4 has finished; everything else is still running."""
    amb = {"n": 2, "finished": 2, "travel_time_mean_s": 90.0, "stopped_time_mean_s": 20.0,
           "vs_maxpressure": {"n_paired": 2, "mean_diff_s": -10.0, "faster": 2, "slower": 0},
           "vs_preemption_mp": {"n_paired": 2, "mean_diff_s": 5.0, "faster": 0, "slower": 2}}
    done = {"att_s": [110.0, 1.0], "att_vs_mp": {"mean": -0.01, "min": -0.02, "max": 0.0, "seeds_worse": 0},
            "queue_mean_per_intersection": [17.0, 0.5], "calls": 100, "failures": 1, "failures_by_type": {"timeout": 1},
            "fallback_to_mp_rate": 0.01, "retries": None, "follows_pressure_rate": 0.8,
            "follows_pressure_per_seed": [0.7, 0.9], "mp_disagreement_rate": 0.2, "wall_time_s_mean": 600.0,
            "served_models": ["gemma4:e4b"], "ambulances": amb}
    base = {"att_s": [111.0, 1.0], "queue_mean_per_intersection": [17.5, 0.3], "ambulances": amb}
    out = {}
    for sc in mk.SCENARIOS:
        seeds = [s for c, s in ms.FULL if c == sc]
        out[sc] = {"seeds": seeds, "baselines": {c: base for c in mk.BASELINES[sc]},
                   "models": {m: done if m == "gemma4:e4b" else {"finished_seeds": seeds[:1]} for m in ms.MODELS}}
    return out


def test_full_tables_and_chart_with_unfinished_models(mk, ms):
    full = fake_full(mk, ms)
    b = {"sizes": mk.SIZES, "full": full, "hosted_runs": [],
         "bench": {"models": {}, "not_run": list(ms.MODELS), "maxpressure": {"att_s": 1, "queue_mean_per_intersection": 1}}}
    tabs = mk.tables(b)
    for name in ("model_size_full", "model_size_full_amb", "model_size_ambulances"):
        rows = tabs[name].splitlines()
        assert len({r.count("|") for r in rows}) == 1, name
        assert "`llama3.1:8b` | 8 | not finished (1 of" in tabs[name] or "`llama3.1:8b` | not finished (1 of" in tabs[name]
    assert "-1.0% (-2.0 to +0.0)" in tabs["model_size_full"] and "1 of 100 (1.0%): timeout 1" in tabs["model_size_full"]
    assert "MaxPressure + preemption (baseline)" in tabs["model_size_ambulances"]
    assert tabs["model_size_hosted"].endswith(f"0 of {1 + len(ms.FULL)} arm B runs finished.")
    chart = mk.svg(b)
    assert chart == mk.svg(b)                                                  # deterministic
    assert all(mk.SHORT[m] in chart for m in ms.MODELS) and chart.count("not finished") == 4 * 3          # once per unfinished row and panel
    assert "Exploratory, added after the main results" in chart and "prefers-color-scheme: dark" in chart


def test_nice_ticks_cover_the_data(mk):
    for lo, hi in [(0, 148.5), (-3.1, 81.4), (0, 100), (0, 0.4)]:
        t = mk.nice_ticks(lo, hi)
        assert t[0] <= lo and t[-1] >= hi and len(t) <= 6
