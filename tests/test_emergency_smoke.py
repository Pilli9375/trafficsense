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
