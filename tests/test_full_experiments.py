import importlib.util
import json

import pytest

from trafficsense.config import repo_root


@pytest.fixture(scope="module")
def batch():
    spec = importlib.util.spec_from_file_location("run_full", repo_root() / "scripts" / "run_full_experiments.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_plan_is_pinned(batch):
    jobs = batch.jobs()
    assert len(jobs) == 67 and len({batch.job_key(j) for j in jobs}) == 67
    count = lambda **kw: sum(all(j[k] == v for k, v in kw.items()) for j in jobs)
    assert count(arm="baseline") == 42 and count(arm="main") == 14 and count(arm="exploratory") == 11
    assert count(arm="exploratory", scenario="jinan_3x4") == 0 and count(arm="main", scenario="jinan_3x4") == 3
    assert count(controller="preemption_mp") == 5 == count(controller="preemption_mp", scenario="indian_2x2_peak_amb")
    assert batch.MAIN == {"arm": "main", "controller": "llm_guarded_mp", "model": "llama3.2:3b", "decision_interval": 5}
    assert batch.EXPLORATORY["controller"] == "llm_guided_mp_v3" and batch.EXPLORATORY["model"] == "gemma4:e4b"
    arms = [j["arm"] for j in jobs]
    assert arms == sorted(arms, key=["baseline", "main", "exploratory"].index)       # slowest last
    assert all(j["out_root"] == batch.EMERGENCY_RUNS for j in jobs if j["scenario"].endswith("_amb"))
    batch.check_main_arm(repo_root())        # benchmark.json's final decision is the main arm


def test_resume_skips_only_complete_runs(batch, tmp_path):
    def run(name, files, **pv):
        d = tmp_path / batch.FULL_RUNS / name
        d.mkdir(parents=True)
        p = dict(scenario="indian_2x2_peak", controller="maxpressure", seed=0, model=None, git_dirty=False,
                 sim_steps=3600) | pv
        if "summary" in files:
            (d / "summary.json").write_text(json.dumps({"provenance": p}))
        if "metrics" in files:
            (d / "metrics.csv").write_text("x\n")
    run("a", ["summary", "metrics"])
    run("b", ["metrics"], seed=1)                         # interrupted: no summary.json
    run("c", ["summary", "metrics"], seed=2, git_dirty=True)
    run("d", ["summary", "metrics"], seed=0, controller="llm_guarded_mp", model="llama3.2:3b")
    done = batch.complete_runs(tmp_path, batch.FULL_RUNS)
    assert set(done) == {("indian_2x2_peak", "maxpressure", 0, None), ("indian_2x2_peak", "llm_guarded_mp", 0, "llama3.2:3b")}
    run("e", ["summary", "metrics"])                      # a second complete copy is an error
    with pytest.raises(SystemExit, match="Two complete runs"):
        batch.complete_runs(tmp_path, batch.FULL_RUNS)
