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
