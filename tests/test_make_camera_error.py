"""make_camera_error.py on a complete set of fake run folders (tmp_path only)."""
import importlib.util
import json
import re

import pytest

from trafficsense.config import repo_root
from trafficsense.sim.observation import COUNTED, SIM_TO_DETECTOR, observation_key


@pytest.fixture(scope="module")
def mc():
    spec = importlib.util.spec_from_file_location("make_camera_error", repo_root() / "scripts" / "make_camera_error.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def fake_runs(mc, root, jobs=None, runs_dir=None):
    plan = mc.plan
    p_of = {"junction": 0.9, "crowded": 0.6, "junction_only_misses": 0.9}
    extra = {"junction_only_false": 1.5, "junction_only_confusion": 0.0}     # ATT added by a component
    for n, j in enumerate((jobs or plan.jobs)()):
        key = observation_key(j["observation"])
        noisy = key != "perfect"
        p = j["observation"].get("p_detect", p_of.get(key, 1.0))
        unaffected = j["controller"] == "fixedtime_webster" or key == "uniform_p1.00"
        att = 100 + 10 * j["seed"] + (0 if unaffected else 20 * (1 - p)) + extra.get(key, 0.0)
        llm = None
        if j["llm"]:
            llm = {"calls": 100, "ok": 100, "guard_overrides": 10, "mp_disagreements": 20, "latency_mean_s": 1.0,
                   "latency_n": 100}
        obs = {"key": key, "noised": noisy}
        if noisy:
            snaps = 0 if j["controller"] == "fixedtime_webster" else 10
            obs.update(snapshots=snaps, params={"p_detect": {c: p for c in SIM_TO_DETECTOR.values()},
                                                "false_det_per_road_snapshot": {c: 0.1 for c in COUNTED},
                                                "source": {"file": "/another/clone/outputs/perception/error_model.json",   # absolute, from elsewhere
                                                           "sha256": "ab" * 32, "conf_threshold": 0.3}},
                       realized={"true_vehicle_observations": {c: 1000 * bool(snaps) for c in SIM_TO_DETECTOR.values()},
                                 "detection_rate": {c: p for c in SIM_TO_DETECTOR.values()},
                                 "lost_to_non_vehicle_label": {c: 2 for c in SIM_TO_DETECTOR.values()},
                                 "false_per_road_snapshot": {c: 0.1 for c in COUNTED}})
        s = {"provenance": {"scenario": j["scenario"], "controller": j["controller"], "seed": j["seed"],
                            "model": j["llm"]["model"] if j["llm"] else None, "git_dirty": False, "sim_steps": plan.STEPS,
                            "llm": llm},
             "metrics": {"att": att, "queue_mean_per_intersection": att / 10, "waiting_time_mean": att / 2,
                         "throughput": 4000},
             "observation": obs,
             "emergency": {"vehicles": [{"vehicle": "flow_1_0", "route": ["road_0_1_0", "road_1_1_0"],
                                         "finished": 1.0, "travel_time_s": att}]} if "amb" in j["scenario"] else None}
        d = root / (runs_dir or plan.RUNS) / f"run{n:03d}"
        d.mkdir(parents=True)
        (d / "summary.json").write_text(json.dumps(s))
        (d / "metrics.csv").write_text("t\n")


def test_report_tables_and_chart(mc, tmp_path, monkeypatch):
    fake_runs(mc, tmp_path)
    fake_runs(mc, tmp_path, mc.decomp.jobs, mc.decomp.RUNS)
    monkeypatch.setattr(mc, "signal_relevant", lambda net, route: True)
    b = json.loads(json.dumps(mc.report(tmp_path)))
    mp = b["main"]["indian_2x2_peak"]["maxpressure"]
    assert mp["junction"]["att_vs_perfect"]["mean"] == pytest.approx(2.0)
    assert mp["crowded"]["att_vs_perfect"]["per_seed"] == pytest.approx([8.0] * 3)
    assert b["sweep"]["indian_2x2_peak"]["uniform_p0.50"]["att_vs_perfect"]["mean"] == pytest.approx(10.0)
    assert b["effective_p_detect"]["indian_2x2_offpeak"]["crowded"] == pytest.approx(0.6)
    assert b["params"]["junction"]["source"]["file"] == "outputs/perception/error_model.json"   # not where the runs were made
    ch = b["checks"]
    assert ch["uniform_p1_identical_to_perfect"] and ch["webster_identical_across_levels"]
    assert ch["webster_max_snapshots"] == 0 and ch["realised_within_0_01"]
    assert ch["realised_max_abs_z"] == pytest.approx(0) and ch["realised_largest_miss"]["level"] != "uniform_p1.00"
    assert b["emergency"]["llm_guarded_mp"]["junction"]["ambulances_vs_perfect"]["mean_diff_s"] == pytest.approx(2.0)
    dc = b["decomposition"]
    assert dc["misses"]["att_vs_perfect"]["indian_2x2_peak"]["mean"] == pytest.approx(2.0)
    assert dc["false"]["att_vs_perfect"]["indian_2x2_peak"]["mean"] == pytest.approx(1.5)
    assert dc["all"]["att_vs_perfect"]["indian_2x2_peak"]["mean"] == pytest.approx(2.0)
    assert dc["sum_abc"]["indian_2x2_offpeak"]["mean"] == pytest.approx(3.5)
    assert dc["misses"]["realised"]["detection_rate"] == pytest.approx(0.9)
    tabs = mc.tables(b)
    doc = "\n".join(f"<!-- BEGIN:{k} -->\nX\n<!-- END:{k} -->" for k in tabs)
    new = mc.render(doc, tabs)
    assert mc.render(new, tabs) == new and "+2.0 (+2.0 to +2.0); +1.8%" in new
    chart = mc.svg(b)
    assert chart.startswith("<svg") and chart.count("<polyline") == 2
    assert not re.search(r"nan|inf", chart)


def test_missing_runs_fail(mc, tmp_path):
    with pytest.raises(SystemExit, match="missing"):
        mc.load_runs(tmp_path)
    fake_runs(mc, tmp_path)
    with pytest.raises(SystemExit, match="missing from outputs/camera_error/decomposition"):
        mc.report(tmp_path)
