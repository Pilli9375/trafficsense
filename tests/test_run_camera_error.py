"""run_camera_error.py: plan size and the child-process runner with timeout."""
import copy
import importlib.util
import logging

import pytest

from trafficsense.config import repo_root


@pytest.fixture(scope="module")
def rc():
    spec = importlib.util.spec_from_file_location("run_camera_error", repo_root() / "scripts" / "run_camera_error.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_plan(rc):
    jobs = rc.jobs()
    assert len(jobs) == 130 and len({rc.job_key(j) for j in jobs}) == 130
    assert sum(j["llm"] is not None for j in jobs) == 28
    assert {j["controller"] for j in jobs if j["scenario"] != "indian_2x2_peak_amb"} == \
        {"maxpressure", "fixedtime_webster", "llm_guarded_mp"}


def test_child_run_and_timeout(rc, cfg, tmp_path, monkeypatch):
    j = {"scenario": "indian_2x2_peak", "controller": "maxpressure", "seed": 0}
    c = copy.deepcopy(cfg)
    c["observation"] = {"level": "junction"}
    out = rc.run_with_timeout(c, j, tmp_path, logging.getLogger("t"))
    assert (out / "summary.json").is_file() and (out / "noise.jsonl").is_file()
    monkeypatch.setitem(rc.TIMEOUT_S, "maxpressure", 0.2)
    with pytest.raises(RuntimeError, match="hung"):
        rc.run_with_timeout(c, j, tmp_path / "t", logging.getLogger("t"))
