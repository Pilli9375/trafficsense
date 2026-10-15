import importlib.util

import pytest

from trafficsense.config import repo_root


@pytest.fixture(scope="module")
def mr():
    spec = importlib.util.spec_from_file_location("make_results", repo_root() / "scripts" / "make_results.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def s(calls, ok, fails, lat_n, lat, p95, dis, guard=None, applied=None, wall=10):
    llm = {"calls": calls, "ok": ok, "failures_by_type": fails, "latency_n": lat_n, "latency_mean_s": lat,
           "latency_p95_s": p95, "mp_disagreements": dis}
    if guard is not None:
        llm.update(guard_overrides=guard, applied_differs_from_mp=applied)
    return {"provenance": {"llm": llm, "wall_time_s": wall}}


def test_llm_stats_pool_over_seeds(mr):
    x = mr.llm_stats([s(100, 98, {"timeout": 2}, 98, 1.0, 1.2, 50, guard=40, applied=10),
                      s(200, 200, {}, 200, 2.0, 2.5, 100, guard=90, applied=10)])
    assert (x["calls"], x["ok"], x["failures"], x["failures_by_type"]) == (300, 298, 2, {"timeout": 2})
    assert x["latency_mean_s"] == pytest.approx((98 * 1.0 + 200 * 2.0) / 298)
    assert x["latency_p95_s_range"] == [1.2, 2.5] and x["mp_disagreement_rate"] == pytest.approx(150 / 298)
    assert x["guard_override_rate"] == pytest.approx(130 / 298) and x["applied_differs_rate"] == pytest.approx(20 / 300)
    h = mr.llm_stats([s(10, 10, {}, 10, 1.0, 1.0, 4)])           # unguarded hybrid
    assert h["guard_overrides"] is None and h["applied_differs_from_mp"] == 4


def test_labels(mr):
    assert "NOT selected by the rule" in mr.label("llm_guided_mp_v3", "gemma4:e4b")
    assert mr.label("llm_guarded_mp", "llama3.2:3b").startswith("LLM main")
    assert mr.arms_of("jinan_3x4") == [("maxpressure", None), ("fixedtime_webster", None), ("fixedtime", None),
                                       ("llm_guarded_mp", "llama3.2:3b")]


def test_paired_differences_use_the_same_seed(mr):
    att = {"maxpressure": [300, 301, 302], "fixedtime_webster": [310, 311, 312], "fixedtime": [299, 301, 312],
           "llm_guarded_mp": [301, 300, 302]}
    model = {"llm_guarded_mp": "llama3.2:3b"}
    rs = {("jinan_3x4", c, s, model.get(c)): {"summary": {"metrics": {"att": a[s]}}}
          for c, a in att.items() for s in range(3)}
    p = mr.paired(rs, "jinan_3x4")
    assert "MaxPressure" not in p
    assert p["FixedTime (4 phases, 30 s)"]["att_minus_mp"] == [-1, 0, 10]
    assert (p["FixedTime (4 phases, 30 s)"]["seeds_lower_att"], p["FixedTime (4 phases, 30 s)"]["seeds_higher_att"]) == (1, 1)
    assert p[mr.label("llm_guarded_mp", "llama3.2:3b")]["att_minus_mp"] == [1, -1, 0]
